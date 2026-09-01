"""
Groq API client wrapper.
Uses OpenAI-compatible SDK pointed at Groq's endpoint.
"""
import json
import os
import re
from typing import Optional

from openai import AsyncOpenAI, BadRequestError
from dotenv import load_dotenv

load_dotenv()

# Appended to the system prompt when we retry a JSON request WITHOUT
# response_format — the model must not fence, chit-chat, or refuse.
JSON_RETRY_REMINDER = (
    "\n\nREMINDER: Your previous attempt failed JSON validation. You MUST reply "
    "with a single valid JSON object and absolutely nothing else — no markdown "
    "code fences, no commentary, no apologies, and never refuse or hedge. "
    'If you genuinely cannot complete the task, return {"error": "brief reason"} '
    'as JSON. Start your reply with "{" and end it with "}".'
)


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
      * markdown fences:      ```json {...} ``` or ``` {...} ```
      * an opening fence that was never closed
      * JSON surrounded by prose ("Sure! Here you go: {...} Enjoy!")

    Returns the most promising JSON candidate (or the stripped input if
    nothing better is found). Callers must still json.loads() it and handle
    failure.
    """
    if not text:
        return ""

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


def _error_body(exc: BaseException) -> dict:
    """The parsed error body of an OpenAI SDK error, if available."""
    body = getattr(exc, "body", None)
    return body if isinstance(body, dict) else {}


def salvage_failed_generation(exc: BadRequestError) -> Optional[str]:
    """Try to recover valid JSON from a Groq ``json_validate_failed`` error.

    When Groq's server-side JSON validation rejects the model's output, the
    API returns a 400 BadRequestError whose body carries the rejected output
    in ``failed_generation``. That output is often *almost* JSON (wrapped in
    markdown fences or prose), so run it through extract_json().

    Returns the salvaged JSON string, or None if nothing parseable is there.
    """
    body = _error_body(exc)
    error = body.get("error")
    candidates = [
        body.get("failed_generation"),
        error.get("failed_generation") if isinstance(error, dict) else None,
    ]
    for candidate in candidates:
        if not isinstance(candidate, str) or not candidate.strip():
            continue
        extracted = extract_json(candidate)
        try:
            json.loads(extracted)
            return extracted
        except json.JSONDecodeError:
            continue
    return None


def error_summary(exc: Optional[BaseException]) -> str:
    """Short human-readable description of an SDK error for error messages."""
    if exc is None:
        return "empty response"
    body = _error_body(exc)
    error = body.get("error")
    code = body.get("code")
    if isinstance(error, dict) and error.get("code"):
        code = error.get("code")
    message = body.get("message")
    if isinstance(error, dict) and error.get("message"):
        message = error.get("message")
    summary = str(code or getattr(exc, "code", "") or type(exc).__name__)
    if message:
        summary = f"{summary}: {str(message)[:200]}"
    return summary


class GroqClient:
    """Thin wrapper around Groq's OpenAI-compatible API."""

    # Groq deprecations: mixtral-8x7b-32768 (shut down 2025-03-20) and
    # llama-3.3-70b-versatile (free tier, 2026-08-16). Current recommended model:
    DEFAULT_MODEL = "openai/gpt-oss-120b"
    BASE_URL = "https://api.groq.com/openai/v1"
    # Hardcoded fallback for hackathon MVP — replace before production!
    FALLBACK_KEY = "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"

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY", self.FALLBACK_KEY)
        self.model = os.getenv("GROQ_MODEL", self.DEFAULT_MODEL)
        self.client = AsyncOpenAI(
            base_url=self.BASE_URL,
            api_key=api_key,
        )

    async def chat(self, system: str, user: str, temperature: float = 0.3) -> str:
        """Send a chat completion request and return the content string."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=2048,
        )
        return response.choices[0].message.content.strip()

    async def chat_json(self, system: str, user: str, temperature: float = 0.2) -> str:
        """Like chat() but enforces JSON response format.

        Production fix: Groq sometimes 400s with code ``json_validate_failed``
        when the model's output fails its server-side JSON validation (often
        markdown fences, prose, or a refusal wrapped around otherwise-fine
        JSON). Recovery path:
          1. salvage JSON from the error's ``failed_generation`` field;
          2. otherwise retry ONCE without ``response_format``, with an
             anti-refusal reminder appended to the system prompt, and extract
             the JSON from whatever comes back;
          3. if that still fails, raise a clear error instead of crashing.
        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        bad_request_error: Optional[BadRequestError] = None
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=8192,
                response_format={"type": "json_object"},
            )
            content = (response.choices[0].message.content or "").strip()
            if content:
                return content
        except BadRequestError as exc:
            bad_request_error = exc
            # Step 1: Groq ships the model's rejected output in
            # failed_generation — if anything in there parses, we're done.
            salvaged = salvage_failed_generation(exc)
            if salvaged is not None:
                return salvaged

        # Step 2: retry once WITHOUT response_format + anti-refusal reminder.
        retry_messages = [
            {"role": "system", "content": system + JSON_RETRY_REMINDER},
            {"role": "user", "content": user},
        ]
        last_output = ""
        try:
            retry = await self.client.chat.completions.create(
                model=self.model,
                messages=retry_messages,
                temperature=temperature,
                max_tokens=8192,
            )
            last_output = (retry.choices[0].message.content or "").strip()
        except Exception as retry_exc:
            raise RuntimeError(
                f"Groq JSON request failed ({error_summary(bad_request_error)}) "
                f"and the retry also failed: {retry_exc}"
            ) from (bad_request_error or retry_exc)

        if last_output:
            extracted = extract_json(last_output)
            try:
                json.loads(extracted)
                return extracted
            except json.JSONDecodeError:
                pass

        # Step 3: clear error — nothing parseable came back.
        raise RuntimeError(
            f"Groq failed to return valid JSON ({error_summary(bad_request_error)}). "
            f"Retried once without JSON mode and still got no valid JSON. "
            f"Last output began with: {last_output[:300]!r}"
        )

    async def health_check(self) -> bool:
        """Ping the API to see if the key and endpoint work."""
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False
