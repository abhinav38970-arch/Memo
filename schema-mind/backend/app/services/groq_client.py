"""
Groq API client wrapper (OpenAI-compatible SDK pointed at Groq's endpoint).

Why this is more than a thin wrapper
------------------------------------
Groq's free tier gives ``openai/gpt-oss-120b`` an 8,000 tokens-per-minute (TPM)
budget, and it charges ``prompt_tokens + max_tokens`` against that budget *up
front*, when the request is admitted:

  * prompt + max_tokens > limit
        -> HTTP 413 "Request too large ... Limit L, Requested R"
           (can never succeed, no matter how long you wait)
  * used_this_minute + prompt + max_tokens > limit
        -> HTTP 429 "Rate limit reached ... Limit L, Used U, Requested R.
           Please try again in Xs"

So a request with ``max_tokens=8192`` is rejected with a 413 every single time
on an 8,000-TPM org — even with a 400-token prompt — which is exactly what the
production logs showed.

This client therefore:
  1. Sizes ``max_tokens`` for every request so prompt + completion fits the
     budget that is actually available right now. The limit is learned from
     Groq's ``x-ratelimit-*`` response headers and error messages (default
     8,000, override with ``GROQ_TPM_LIMIT``).
  2. On a 413 learns the exact prompt size, shrinks the completion budget and
     retries immediately.
  3. On a 429 either shrinks to fit what is left of the minute and retries, or
     — if the window is nearly empty — waits for the reset (bounded) and retries.
  4. Asks gpt-oss for ``reasoning_effort: low`` so hidden reasoning tokens
     don't eat the budget (they count as completion tokens).
  5. Repairs truncated / fenced / prose-wrapped JSON instead of failing.
  6. Raises typed errors with actionable messages, which the routers map to
     proper HTTP status codes instead of leaking raw SDK tracebacks.

Environment variables (all optional):
  GROQ_API_KEY            API key
  GROQ_MODEL              model id (default openai/gpt-oss-120b)
  GROQ_BASE_URL           API base URL (default https://api.groq.com/openai/v1)
  GROQ_TPM_LIMIT          assumed tokens-per-minute limit before we learn the
                          real one from Groq (default 8000 = free tier)
  GROQ_MAX_TOKENS         hard cap on completion tokens per request (default 4096)
  GROQ_REASONING_EFFORT   low | medium | high (gpt-oss), or "off" to not send
                          any reasoning parameters (default low)
  GROQ_MAX_WAIT_SECONDS   longest we will wait for the TPM window to reset
                          inside one request (default 40)
"""
import asyncio
import json
import math
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx
from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, AsyncOpenAI, BadRequestError

load_dotenv()

# ── Defaults ─────────────────────────────────────────────────────────────────

DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_TPM_LIMIT = 8000  # Groq free tier for openai/gpt-oss-120b and -20b
DEFAULT_MAX_COMPLETION_TOKENS = 4096
DEFAULT_MIN_COMPLETION_TOKENS = 512
DEFAULT_REASONING_EFFORT = "low"
DEFAULT_MAX_WAIT_SECONDS = 40.0
HARD_MIN_COMPLETION_TOKENS = 384  # below this we never send (output would be useless)
TPM_MARGIN = 256  # headroom between the reservation and the limit
PROMPT_TOKEN_OVERHEAD = 64  # chat template / role tokens
CHARS_PER_TOKEN = 3.5  # deliberately pessimistic (English ≈ 4 chars/token)
REQUEST_TIMEOUT_SECONDS = 90.0

# Appended to the system prompt when we retry a JSON request WITHOUT
# response_format — the model must not fence, chit-chat, or refuse.
JSON_RETRY_REMINDER = (
    "\n\nREMINDER: Your previous attempt failed JSON validation. You MUST reply "
    "with a single valid JSON object and absolutely nothing else — no markdown "
    "code fences, no commentary, no apologies, and never refuse or hedge. "
    'If you genuinely cannot complete the task, return {"error": "brief reason"} '
    'as JSON. Start your reply with "{" and end it with "}".'
)


def _log(msg: str) -> None:
    print(f"[groq] {msg}", flush=True)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


# ── Errors (routers map these to HTTP status codes) ─────────────────────────


class GroqError(RuntimeError):
    """A Groq failure with a user-facing, actionable message."""

    status_code = 502

    def __init__(self, message: str, *, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class GroqRateLimitError(GroqError):
    """The per-minute / per-day budget is used up; try again later."""

    status_code = 429


class GroqRequestTooLargeError(GroqError):
    """The input can never fit this tier's budget; shorten it."""

    status_code = 413


class GroqBadOutputError(GroqError):
    """The model did not return usable JSON even after retries."""

    status_code = 502


# ── Token-budget bookkeeping ────────────────────────────────────────────────


def estimate_prompt_tokens(*parts: str) -> int:
    """Pessimistic prompt-token estimate from character counts."""
    chars = sum(len(p) for p in parts if p)
    return int(chars / CHARS_PER_TOKEN) + PROMPT_TOKEN_OVERHEAD


def parse_duration_seconds(value: Optional[str]) -> Optional[float]:
    """Parse the Go-style durations Groq uses: '7.66s', '1m2.5s', '2h3m', '500ms'.

    A bare number (e.g. a ``retry-after`` header) is treated as seconds.
    """
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    parts = re.findall(r"(\d+(?:\.\d+)?)\s*(ms|h|m|s)", text)
    if not parts:
        return None
    factors = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}
    return sum(float(n) * factors[unit] for n, unit in parts)


def _header_int(headers: Any, name: str) -> Optional[int]:
    if headers is None:
        return None
    try:
        raw = headers.get(name)
    except Exception:
        return None
    if raw is None:
        return None
    try:
        return int(float(str(raw).replace(",", "")))
    except ValueError:
        return None


@dataclass
class TokenWindow:
    """What we currently know about the org's TPM window for one model."""

    limit: int = DEFAULT_TPM_LIMIT
    limit_source: str = "default"  # default | header | error
    remaining: Optional[int] = None
    reset_at: Optional[float] = None  # time.monotonic() timestamp

    def learn_limit(self, limit: int, source: str) -> None:
        if limit <= 0:
            return
        if limit != self.limit or self.limit_source == "default":
            _log(f"tokens-per-minute limit = {limit} (from {source})")
        self.limit = limit
        self.limit_source = source

    def update_from_headers(self, headers: Any) -> None:
        limit = _header_int(headers, "x-ratelimit-limit-tokens")
        if limit:
            self.learn_limit(limit, "header")
        remaining = _header_int(headers, "x-ratelimit-remaining-tokens")
        if remaining is None:
            return
        reset = None
        try:
            reset = parse_duration_seconds(headers.get("x-ratelimit-reset-tokens"))
        except Exception:
            reset = None
        self.remaining = max(0, remaining)
        self.reset_at = time.monotonic() + reset if reset else None

    def note_exhausted(self, used: int, retry_in: Optional[float]) -> None:
        """Record a 429: ``used`` tokens consumed, window resets in ``retry_in``."""
        self.remaining = max(0, self.limit - max(0, used))
        self.reset_at = time.monotonic() + (retry_in if retry_in and retry_in > 0 else 30.0)

    def assume_reset(self) -> None:
        self.remaining = None
        self.reset_at = None

    def available(self) -> int:
        if self.remaining is None or self.reset_at is None:
            return self.limit
        if time.monotonic() >= self.reset_at:
            return self.limit
        return max(0, min(self.remaining, self.limit))

    def seconds_until_reset(self) -> float:
        if self.reset_at is None:
            return 0.0
        return max(0.0, self.reset_at - time.monotonic())


_WINDOWS: Dict[str, TokenWindow] = {}


def window_for(model: str) -> TokenWindow:
    """One shared window per model for the whole process (limits are per model)."""
    window = _WINDOWS.get(model)
    if window is None:
        window = TokenWindow(limit=max(_env_int("GROQ_TPM_LIMIT", DEFAULT_TPM_LIMIT), 1024))
        _WINDOWS[model] = window
    return window


def reset_windows() -> None:
    """Forget everything learned about rate limits (tests / hot reload)."""
    _WINDOWS.clear()


# ── Reasoning parameters ────────────────────────────────────────────────────


def reasoning_params(model: str) -> Dict[str, Any]:
    """Extra request params that keep reasoning models cheap and JSON clean.

    * gpt-oss: ``reasoning_effort`` low|medium|high (default in Groq is
      medium). Reasoning tokens count as completion tokens — and against the
      TPM budget — so low effort is a big saving. ``include_reasoning: false``
      keeps the reasoning out of the response. (``reasoning_format`` is NOT
      supported by gpt-oss on Groq, so it is deliberately not sent.)
    * Qwen 3.x: ``reasoning_format: hidden`` (required with JSON mode) plus
      ``reasoning_effort`` where supported.
    * Anything else: nothing.

    If a model rejects these, the client retries once without them.
    """
    effort = (os.getenv("GROQ_REASONING_EFFORT") or DEFAULT_REASONING_EFFORT).strip().lower()
    if effort in ("off", "disabled", "unset"):
        return {}
    name = model.lower()
    if "gpt-oss" in name:
        if effort not in ("low", "medium", "high"):
            effort = DEFAULT_REASONING_EFFORT
        return {"reasoning_effort": effort, "include_reasoning": False}
    if "qwen3.8" in name or "qwen3-8" in name:
        if effort not in ("none", "default", "low", "medium", "high"):
            effort = DEFAULT_REASONING_EFFORT
        return {"reasoning_effort": effort, "reasoning_format": "hidden"}
    if "qwen3.6" in name or "qwen3-6" in name:
        return {"reasoning_effort": "none", "reasoning_format": "hidden"}
    return {}


# ── Error-body helpers ──────────────────────────────────────────────────────


def _error_body(exc: BaseException) -> dict:
    """The parsed error body of an OpenAI SDK error, if available.

    The SDK usually unwraps ``{"error": {...}}`` to the inner dict, but we
    accept both shapes.
    """
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        inner = body.get("error")
        if isinstance(inner, dict):
            merged = dict(body)
            merged.update(inner)
            return merged
        return body
    return {}


def _error_code(exc: BaseException) -> str:
    body = _error_body(exc)
    code = body.get("code") or getattr(exc, "code", None) or ""
    return str(code)


def _error_message(exc: BaseException) -> str:
    body = _error_body(exc)
    message = body.get("message")
    if isinstance(message, str) and message:
        return message
    return str(exc)


def error_summary(exc: Optional[BaseException]) -> str:
    """Short human-readable description of an SDK error for error messages."""
    if exc is None:
        return "empty response"
    code = _error_code(exc) or type(exc).__name__
    message = _error_message(exc)
    return f"{code}: {message[:200]}" if message else code


def _api_error_hint(exc: APIStatusError) -> str:
    """Actionable hint for non-budget API errors."""
    code = _error_code(exc)
    message = _error_message(exc).lower()
    status = getattr(exc, "status_code", None)
    if code == "rate_limit_exceeded":
        return "Groq's rate limit is reached; wait a minute and try again."
    if status == 401 or "invalid api key" in message or "authentication" in message:
        return "The GROQ_API_KEY on the server is missing or invalid."
    if "decommissioned" in message or code in ("model_decommissioned", "model_not_found") or status == 404:
        return (
            "The configured model is not available anymore. Set GROQ_MODEL to a "
            "current model such as openai/gpt-oss-120b."
        )
    return "Check the Groq API key, quota, and model availability, then try again."


def _mentions_reasoning(exc: BaseException) -> bool:
    return "reasoning" in _error_message(exc).lower()


def _is_json_validation_error(exc: BaseException) -> bool:
    body = _error_body(exc)
    return _error_code(exc) == "json_validate_failed" or "failed_generation" in body


@dataclass
class RateLimitInfo:
    kind: str  # "too_large" (the request alone exceeds the limit) | "exhausted"
    scope: str  # TPM | RPM | RPD | TPD | ... | "" (unknown)
    limit: Optional[int]
    used: Optional[int]
    requested: Optional[int]
    retry_in: Optional[float]


def _int_after(label: str, message: str) -> Optional[int]:
    match = re.search(label + r"\s*:?\s*~?\s*(\d[\d,]*)", message, re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group(1).replace(",", ""))
    except ValueError:
        return None


def parse_rate_limit_error(exc: APIStatusError) -> Optional[RateLimitInfo]:
    """Parse Groq's 413/429 rate-limit messages.

    413: ``Request too large for model X ... on tokens per minute (TPM):
         Limit 8000, Requested 8665, please reduce your message size``
    429: ``Rate limit reached for model X ... on tokens per minute (TPM):
         Limit 8000, Used 6200, Requested ~2500. Please try again in 12.5s.``
    """
    code = _error_code(exc)
    message = _error_message(exc)
    lowered = message.lower()
    status = getattr(exc, "status_code", None)
    if code != "rate_limit_exceeded" and "rate limit" not in lowered and "request too large" not in lowered:
        if status != 429:
            return None
    scope_match = re.search(r"\((TPM|RPM|RPD|TPD|ASH|ASD|ITPM|OTPM)\)", message)
    scope = scope_match.group(1) if scope_match else ""
    limit = _int_after("Limit", message)
    used = _int_after("Used", message)
    requested = _int_after("Requested", message)
    retry_in = None
    retry_match = re.search(r"try again in\s+([0-9hms.]+)", message, re.IGNORECASE)
    if retry_match:
        retry_in = parse_duration_seconds(retry_match.group(1))
    if retry_in is None:
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None)
        if headers is not None:
            retry_in = parse_duration_seconds(headers.get("retry-after"))
    too_large = status == 413 or "request too large" in lowered
    if not too_large and used is None and limit is not None and requested is not None and requested > limit:
        too_large = True
    return RateLimitInfo(
        kind="too_large" if too_large else "exhausted",
        scope=scope,
        limit=limit,
        used=used,
        requested=requested,
        retry_in=retry_in,
    )


# ── JSON extraction / repair ────────────────────────────────────────────────


def _first_balanced_block(text: str) -> str:
    """Return the first balanced {...} or [...] block in text, or "" if none.

    Only the root bracket type is counted — valid JSON nests brackets, so a
    block that re-balances its opener is a complete JSON candidate. Contents
    of string literals (and escapes) are skipped so braces inside quotes
    don't confuse the count.
    """
    start = -1
    for i, ch in enumerate(text):
        if ch == "{" or ch == "[":
            start = i
            break
    if start == -1:
        return ""

    opener = text[start]
    closer = "}" if opener == "{" else "]"
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return ""


def extract_json(text: str) -> str:
    """Best-effort extraction of a JSON payload from raw model output.

    Handles the common ways models wrap JSON:
      * <think>...</think> reasoning blocks before the answer
      * markdown fences:      ```json {...} ``` or ``` {...} ```
      * an opening fence that was never closed
      * JSON surrounded by prose ("Sure! Here you go: {...} Enjoy!")

    Returns the most promising JSON candidate (or the stripped input if
    nothing better is found). Callers must still json.loads() it and handle
    failure.
    """
    if not text:
        return ""

    # 0. Drop reasoning blocks (closed or truncated-open).
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    if "<think>" in text.lower() and "</think>" not in text.lower():
        text = re.split(r"<think>", text, maxsplit=1, flags=re.IGNORECASE)[0] or text

    # 1. A complete markdown-fenced block wins.
    fenced = re.search(r"```(?:json)?[ \t]*\n?(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fenced and fenced.group(1).strip():
        return fenced.group(1).strip()

    # 2. An opening fence that was never closed: take everything after it.
    if "```" in text:
        tail = text.rsplit("```", 1)[1]
        tail = re.sub(r"^(?:json|JSON)\b", "", tail).strip()
        if tail:
            return tail

    # 3. A balanced {...} / [...] block embedded in prose.
    balanced = _first_balanced_block(text)
    if balanced:
        return balanced

    return text.strip()


def repair_truncated_json(text: str) -> Optional[str]:
    """Best-effort repair of JSON that was cut off mid-stream.

    Walks the text tracking the bracket stack (string-aware) and remembers
    every position where a complete object/array *element* ended. Then, newest
    first, tries ``prefix + missing closers`` until something parses. For a
    payload like ``{"patterns": [{...}, {...}, {"type": "sto`` this yields the
    complete patterns and drops the half-written one.
    """
    if not text:
        return None
    start = -1
    for i, ch in enumerate(text):
        if ch in "{[":
            start = i
            break
    if start == -1:
        return None

    stack: List[str] = []
    cuts: List[Tuple[int, str]] = []
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if not stack:
                break
            opener = stack.pop()
            if (opener == "{") != (ch == "}"):
                break
            if not stack:
                candidate = text[start : i + 1]
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    break
            closers = "".join("}" if o == "{" else "]" for o in reversed(stack))
            cuts.append((i, closers))

    for i, closers in reversed(cuts[-80:]):
        candidate = text[start : i + 1] + closers
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            continue
    return None


def parse_json_lenient(text: str) -> Optional[str]:
    """Return a valid JSON object/array string extracted from ``text``, or None.

    Tries, in order: the text as-is, extract_json() (fences / prose / think
    blocks), and finally repair_truncated_json() on both.
    """
    if not text or not text.strip():
        return None
    candidates = [text.strip()]
    extracted = extract_json(text)
    if extracted and extracted not in candidates:
        candidates.append(extracted)
    for candidate in candidates:
        if candidate[:1] not in "{[":
            continue
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            continue
    for candidate in candidates:
        repaired = repair_truncated_json(candidate)
        if repaired is not None:
            return repaired
    return None


def salvage_failed_generation(exc: BadRequestError) -> Optional[str]:
    """Recover JSON from a Groq ``json_validate_failed`` error.

    When Groq's server-side JSON validation rejects the model's output (fences,
    prose, or — most often — output truncated by ``max_tokens``), the 400 body
    carries the rejected text in ``failed_generation``. Run it through the
    lenient parser / truncation repair.
    """
    body = _error_body(exc)
    candidate = body.get("failed_generation")
    if not isinstance(candidate, str) or not candidate.strip():
        return None
    return parse_json_lenient(candidate)


# ── Client ──────────────────────────────────────────────────────────────────


class GroqClient:
    """Budget-aware wrapper around Groq's OpenAI-compatible API."""

    # Groq deprecations: mixtral-8x7b-32768 (2025-03-20), llama-3.3-70b-versatile
    # (2026-08-16). Current recommended model:
    DEFAULT_MODEL = DEFAULT_MODEL
    BASE_URL = DEFAULT_BASE_URL
    # Hardcoded fallback for hackathon MVP — replace before production!
    FALLBACK_KEY = "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"

    def __init__(self, http_client: Optional[httpx.AsyncClient] = None):
        api_key = os.getenv("GROQ_API_KEY") or self.FALLBACK_KEY
        self.model = (os.getenv("GROQ_MODEL") or self.DEFAULT_MODEL).strip()
        self.base_url = (os.getenv("GROQ_BASE_URL") or self.BASE_URL).strip().rstrip("/")
        self.max_completion_tokens = max(_env_int("GROQ_MAX_TOKENS", DEFAULT_MAX_COMPLETION_TOKENS), 64)
        self.max_wait_seconds = max(_env_float("GROQ_MAX_WAIT_SECONDS", DEFAULT_MAX_WAIT_SECONDS), 0.0)
        self.reasoning_params = reasoning_params(self.model)
        self.window = window_for(self.model)
        kwargs: Dict[str, Any] = dict(
            base_url=self.base_url,
            api_key=api_key,
            max_retries=0,  # we do our own, budget-aware retries
            timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=10.0),
        )
        if http_client is not None:
            kwargs["http_client"] = http_client
        self.client = AsyncOpenAI(**kwargs)

    # ── Introspection ────────────────────────────────────────────────────

    def describe(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "base_url": self.base_url,
            "tpm_limit": self.window.limit,
            "tpm_limit_source": self.window.limit_source,
            "max_completion_tokens": self.max_completion_tokens,
            "reasoning": self.reasoning_params or None,
            "max_wait_seconds": self.max_wait_seconds,
        }

    # ── Budgeting ────────────────────────────────────────────────────────

    def _too_large(self, prompt_tokens: int, floor: int) -> GroqRequestTooLargeError:
        limit = self.window.limit
        max_prompt = max(limit - floor - TPM_MARGIN, 0)
        max_chars = int(max_prompt * CHARS_PER_TOKEN * 0.8)
        return GroqRequestTooLargeError(
            "Your text is too long for the Groq plan this server is on: the prompt is "
            f"about {prompt_tokens} tokens and the model needs at least {floor} tokens to "
            f"answer, but the tokens-per-minute limit is {limit}. Please shorten the text "
            f"to roughly {max_chars:,} characters or less, or upgrade the Groq plan."
        )

    async def _fit_budget(self, prompt_tokens: int, desired: int, floor: int) -> int:
        """Pick ``max_tokens`` so prompt + completion fits the TPM window.

        May sleep (bounded by ``GROQ_MAX_WAIT_SECONDS``) when the current
        minute is nearly used up. Raises a typed error when the request can
        never fit or the wait would be too long.
        """
        window = self.window
        full_room = window.limit - prompt_tokens - TPM_MARGIN
        if full_room < floor:
            raise self._too_large(prompt_tokens, floor)

        room = window.available() - prompt_tokens - TPM_MARGIN
        if room >= floor:
            return min(desired, room)

        wait = window.seconds_until_reset()
        if wait <= 0:
            window.assume_reset()
            return min(desired, full_room)

        # Not enough left this minute for a complete answer. Prefer a bounded
        # wait (complete output) over a shrunken request (truncated output).
        if wait <= self.max_wait_seconds:
            _log(
                f"TPM window nearly used up (available={window.available()}, "
                f"need≈{prompt_tokens + floor + TPM_MARGIN}); waiting {wait:.1f}s for it to reset"
            )
            await asyncio.sleep(wait + 0.25)
            window.assume_reset()
            return min(desired, full_room)
        if room >= HARD_MIN_COMPLETION_TOKENS:
            _log(
                f"TPM window is tight (available={window.available()}) and the reset is {wait:.0f}s away; "
                f"sending with a reduced completion budget of {room} tokens (partial output is possible)"
            )
            return room
        raise GroqRateLimitError(
            "Groq's per-minute token budget for this model is used up right now. "
            f"Please try again in about {int(math.ceil(wait))} seconds.",
            retry_after=wait,
        )

    # ── Low-level request ────────────────────────────────────────────────

    async def _create(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
        extras: Dict[str, Any],
    ) -> Tuple[str, Optional[str]]:
        kwargs: Dict[str, Any] = dict(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if extras:
            kwargs["extra_body"] = dict(extras)
        raw = await self.client.chat.completions.with_raw_response.create(**kwargs)
        self.window.update_from_headers(raw.headers)
        completion = raw.parse()
        choice = completion.choices[0] if getattr(completion, "choices", None) else None
        message = getattr(choice, "message", None)
        content = ((getattr(message, "content", None) if message else None) or "").strip()
        finish = getattr(choice, "finish_reason", None) if choice else None
        usage = getattr(completion, "usage", None)
        if usage is not None:
            _log(
                f"ok model={self.model} prompt={usage.prompt_tokens} completion={usage.completion_tokens} "
                f"max_tokens={max_tokens} finish={finish} tpm_remaining={self.window.remaining}"
            )
        return content, finish

    async def _request(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float,
        prompt_tokens: int,
        desired: int,
        floor: int,
        json_mode: bool,
        extras: Dict[str, Any],
    ) -> Tuple[str, Optional[str]]:
        """Send one logical request, handling budget / rate-limit / transient errors.

        ``BadRequestError`` (400) is re-raised for the caller (JSON salvage).
        """
        extras = dict(extras)
        budget_retries = rate_retries = transient_retries = reasoning_retries = 0
        for _ in range(8):
            max_tokens = await self._fit_budget(prompt_tokens, desired, floor)
            try:
                return await self._create(messages, temperature, max_tokens, json_mode, extras)
            except BadRequestError as exc:
                if extras and reasoning_retries == 0 and _mentions_reasoning(exc):
                    reasoning_retries += 1
                    _log(f"model rejected reasoning params ({error_summary(exc)}); retrying without them")
                    extras = {}
                    continue
                raise
            except APIStatusError as exc:
                response = getattr(exc, "response", None)
                self.window.update_from_headers(getattr(response, "headers", None))
                info = parse_rate_limit_error(exc)
                if info is not None:
                    if info.limit:
                        self.window.learn_limit(info.limit, "error")
                    if info.kind == "too_large":
                        learned = (info.requested - max_tokens) if info.requested else None
                        if learned and learned > 0 and 0.25 * prompt_tokens <= learned <= 4 * prompt_tokens:
                            prompt_tokens = learned
                        else:
                            prompt_tokens = int(prompt_tokens * 1.5) + PROMPT_TOKEN_OVERHEAD
                        if budget_retries == 0:
                            budget_retries += 1
                            _log(
                                f"413 request too large (limit={info.limit}, requested={info.requested}); "
                                f"prompt≈{prompt_tokens} tokens — shrinking completion budget and retrying"
                            )
                            continue
                        raise self._too_large(prompt_tokens, floor) from exc
                    # 429: the window is (partly) used up.
                    if info.scope in ("TPM", "") and info.used is not None:
                        self.window.note_exhausted(info.used, info.retry_in)
                        learned = (info.requested - max_tokens) if info.requested else None
                        if learned and learned > 0 and 0.5 * prompt_tokens <= learned <= 2 * prompt_tokens:
                            prompt_tokens = learned
                    elif info.retry_in is not None:
                        # Request-count or daily limits: nothing to shrink, only wait.
                        if info.retry_in <= self.max_wait_seconds and rate_retries < 2:
                            rate_retries += 1
                            _log(f"429 ({info.scope or 'rate limit'}); waiting {info.retry_in:.1f}s then retrying")
                            await asyncio.sleep(info.retry_in + 0.25)
                            continue
                        raise GroqRateLimitError(
                            _rate_limit_message(info),
                            retry_after=info.retry_in,
                        ) from exc
                    else:
                        self.window.note_exhausted(self.window.limit, None)
                    if rate_retries < 2:
                        rate_retries += 1
                        _log(
                            f"429 tokens-per-minute (limit={info.limit}, used={info.used}, requested={info.requested}, "
                            f"reset≈{info.retry_in}s); re-budgeting and retrying"
                        )
                        continue
                    raise GroqRateLimitError(_rate_limit_message(info), retry_after=info.retry_in) from exc
                status = getattr(exc, "status_code", 0) or 0
                if status >= 500 and transient_retries == 0:
                    transient_retries += 1
                    _log(f"Groq returned {status}; retrying once")
                    await asyncio.sleep(1.5)
                    continue
                raise GroqError(f"Groq request failed ({error_summary(exc)}). {_api_error_hint(exc)}") from exc
            except APIConnectionError as exc:  # includes timeouts
                if transient_retries == 0:
                    transient_retries += 1
                    _log(f"connection problem talking to Groq ({type(exc).__name__}); retrying once")
                    await asyncio.sleep(1.5)
                    continue
                raise GroqError(
                    f"Could not reach the Groq API ({type(exc).__name__}). Please try again in a moment."
                ) from exc
        raise GroqError("Groq request failed after several retries. Please try again.")

    # ── Public API ───────────────────────────────────────────────────────

    def _budgets(self, max_tokens: Optional[int], min_tokens: Optional[int]) -> Tuple[int, int]:
        desired = min(max_tokens or DEFAULT_MAX_COMPLETION_TOKENS, self.max_completion_tokens)
        floor = min(min_tokens or DEFAULT_MIN_COMPLETION_TOKENS, desired)
        floor = max(floor, 64)
        return max(desired, floor), floor

    async def chat(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        *,
        max_tokens: Optional[int] = None,
        min_tokens: Optional[int] = None,
    ) -> str:
        """Plain (non-JSON) chat completion; returns the content string."""
        desired, floor = self._budgets(max_tokens, min_tokens)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        try:
            content, _ = await self._request(
                messages,
                temperature=temperature,
                prompt_tokens=estimate_prompt_tokens(system, user),
                desired=desired,
                floor=floor,
                json_mode=False,
                extras=self.reasoning_params,
            )
        except BadRequestError as exc:
            raise GroqError(f"Groq rejected the request ({error_summary(exc)}). {_api_error_hint(exc)}") from exc
        return content

    async def chat_json(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
        *,
        max_tokens: Optional[int] = None,
        min_tokens: Optional[int] = None,
    ) -> str:
        """Chat completion that returns a valid JSON string (object or array).

        ``max_tokens`` is the completion budget we would like (it is clamped to
        what the TPM window allows); ``min_tokens`` is the smallest budget that
        still produces a useful answer — below it we wait for the window to
        reset instead of sending a request that would be truncated.

        Recovery path when Groq's JSON validation rejects the output
        (``json_validate_failed``, typically fences, prose or truncation):
          1. salvage/repair the JSON in the error's ``failed_generation``;
          2. otherwise retry ONCE without ``response_format`` (still budgeted)
             with an anti-refusal reminder, and extract the JSON;
          3. if that still fails, raise a clear GroqBadOutputError.
        """
        desired, floor = self._budgets(max_tokens, min_tokens)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        bad_request: Optional[BadRequestError] = None
        try:
            content, finish = await self._request(
                messages,
                temperature=temperature,
                prompt_tokens=estimate_prompt_tokens(system, user),
                desired=desired,
                floor=floor,
                json_mode=True,
                extras=self.reasoning_params,
            )
        except BadRequestError as exc:
            bad_request = exc
            salvaged = salvage_failed_generation(exc)
            if salvaged is not None:
                _log("recovered JSON from json_validate_failed payload")
                return salvaged
            if not _is_json_validation_error(exc):
                raise GroqError(
                    f"Groq rejected the request ({error_summary(exc)}). {_api_error_hint(exc)}"
                ) from exc
            _log(f"json_validate_failed without recoverable output ({error_summary(exc)}); retrying without JSON mode")
        else:
            parsed = parse_json_lenient(content)
            if parsed is not None:
                if finish == "length" and parsed != content.strip():
                    _log("output hit max_tokens; returning repaired partial JSON")
                return parsed
            _log(f"JSON mode returned unparseable content (finish={finish}); retrying without JSON mode")

        retry_messages = [
            {"role": "system", "content": system + JSON_RETRY_REMINDER},
            {"role": "user", "content": user},
        ]
        try:
            content, _ = await self._request(
                retry_messages,
                temperature=temperature,
                prompt_tokens=estimate_prompt_tokens(system, JSON_RETRY_REMINDER, user),
                desired=desired,
                floor=floor,
                json_mode=False,
                extras=self.reasoning_params,
            )
        except BadRequestError as exc:
            raise GroqBadOutputError(
                f"Groq could not produce a valid response ({error_summary(exc)}). Please try again."
            ) from exc
        parsed = parse_json_lenient(content)
        if parsed is not None:
            return parsed
        raise GroqBadOutputError(
            "Groq failed to return valid JSON "
            f"({error_summary(bad_request) if bad_request else 'empty or unparseable output'}). "
            "Retried once without JSON mode and still got nothing usable — please try again."
        )

    async def health_check(self) -> bool:
        """Ping the API to see if the key and endpoint work."""
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False


def _rate_limit_message(info: RateLimitInfo) -> str:
    scope_names = {
        "TPM": "per-minute token budget",
        "RPM": "per-minute request limit",
        "RPD": "daily request limit",
        "TPD": "daily token budget",
    }
    what = scope_names.get(info.scope, "rate limit")
    if info.retry_in and info.retry_in > 0:
        if info.retry_in >= 3600:
            when = f"about {info.retry_in / 3600:.1f} hours"
        elif info.retry_in >= 90:
            when = f"about {int(math.ceil(info.retry_in / 60))} minutes"
        else:
            when = f"about {int(math.ceil(info.retry_in))} seconds"
        return f"Groq's {what} for this model is used up. Please try again in {when}."
    return f"Groq's {what} for this model is used up. Please wait a minute and try again."
