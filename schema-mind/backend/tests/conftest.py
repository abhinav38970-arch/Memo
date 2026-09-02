"""Test fixtures: a fake Groq that enforces the free tier's TPM accounting.

Groq charges ``prompt_tokens + max_tokens`` against the tokens-per-minute
window when a request is *admitted*:

  * prompt + max_tokens > limit                -> 413 "Request too large"
  * used + prompt + max_tokens > limit         -> 429 "Rate limit reached"

Both come back with ``code: rate_limit_exceeded``. The fake below reproduces
this, records every request, and lets tests script the responses.
"""
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import groq_client  # noqa: E402


def prompt_tokens_of(body: dict) -> int:
    """The fake's tokenizer: 4 chars/token + 8 per message."""
    total = 0
    for m in body.get("messages", []):
        total += len(m.get("content", "")) // 4 + 8
    return total


def completion(content: str, prompt_tokens: int, completion_tokens: int, finish: str = "stop") -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": "openai/gpt-oss-120b",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": finish}
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def rate_limit_body(message: str) -> dict:
    return {"error": {"message": message, "type": "tokens", "code": "rate_limit_exceeded"}}


@dataclass
class FakeGroq:
    limit: int = 8000
    used: int = 0
    reset_in: float = 42.0
    # Called with the parsed request body to produce the *content* string for a
    # successful completion. Defaults to a small valid JSON object.
    responder: Callable[[dict], Any] = lambda body: '{"patterns": []}'
    requests: List[dict] = field(default_factory=list)
    # Optional scripted responses (consumed in order) — each is either an
    # httpx.Response or a callable(body) -> httpx.Response. When empty, the
    # TPM simulation is used.
    scripted: List[Any] = field(default_factory=list)
    model_list_ok: bool = True

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            if self.model_list_ok:
                return httpx.Response(200, json={"object": "list", "data": []})
            return httpx.Response(401, json={"error": {"message": "Invalid API Key", "type": "invalid_request_error", "code": "invalid_api_key"}})
        body = json.loads(request.content)
        self.requests.append(body)
        if self.scripted:
            nxt = self.scripted.pop(0)
            return nxt(body) if callable(nxt) else nxt
        return self.simulate(body)

    def headers(self, remaining: int) -> Dict[str, str]:
        return {
            "x-ratelimit-limit-tokens": str(self.limit),
            "x-ratelimit-remaining-tokens": str(max(remaining, 0)),
            "x-ratelimit-reset-tokens": f"{self.reset_in}s",
            "x-ratelimit-limit-requests": "1000",
            "x-ratelimit-remaining-requests": "999",
        }

    def simulate(self, body: dict) -> httpx.Response:
        prompt = prompt_tokens_of(body)
        max_tokens = body.get("max_tokens") or body.get("max_completion_tokens") or 1024
        requested = prompt + max_tokens
        if requested > self.limit:
            return httpx.Response(
                413,
                headers=self.headers(self.limit - self.used),
                json=rate_limit_body(
                    f"Request too large for model `openai/gpt-oss-120b` in organization `org_test` "
                    f"service tier `on_demand` on tokens per minute (TPM): Limit {self.limit}, "
                    f"Requested {requested}, please reduce your message size and try again. "
                    "Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing"
                ),
            )
        if self.used + requested > self.limit:
            return httpx.Response(
                429,
                headers={**self.headers(self.limit - self.used), "retry-after": str(int(self.reset_in))},
                json=rate_limit_body(
                    f"Rate limit reached for model `openai/gpt-oss-120b` in organization `org_test` "
                    f"service tier `on_demand` on tokens per minute (TPM): Limit {self.limit}, "
                    f"Used {self.used}, Requested {requested}. Please try again in {self.reset_in}s. "
                    "Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing"
                ),
            )
        content = self.responder(body)
        if isinstance(content, httpx.Response):
            return content
        content_tokens = len(content) // 4
        finish = "stop"
        if content_tokens > max_tokens:
            content = content[: max_tokens * 4]
            content_tokens = max_tokens
            finish = "length"
        # Groq bills prompt + *actual* completion tokens after the fact.
        self.used += prompt + content_tokens
        return httpx.Response(
            200,
            headers=self.headers(self.limit - self.used),
            json=completion(content, prompt, content_tokens, finish),
        )


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in (
        "GROQ_MODEL", "GROQ_TPM_LIMIT", "GROQ_MAX_TOKENS", "GROQ_REASONING_EFFORT",
        "GROQ_MAX_WAIT_SECONDS", "GROQ_BASE_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    groq_client.reset_windows()
    yield
    groq_client.reset_windows()


@pytest.fixture
def fake_groq():
    return FakeGroq()


@pytest.fixture
def no_sleep(monkeypatch):
    """Make asyncio.sleep instant inside groq_client, but record the waits."""
    waits: List[float] = []

    async def _fake_sleep(seconds: float):
        waits.append(seconds)

    monkeypatch.setattr(groq_client.asyncio, "sleep", _fake_sleep)
    return waits


@pytest.fixture
def make_client(fake_groq):
    def _make(**kwargs) -> groq_client.GroqClient:
        transport = httpx.MockTransport(fake_groq.handler)
        return groq_client.GroqClient(http_client=httpx.AsyncClient(transport=transport), **kwargs)

    return _make


@pytest.fixture
def app_client(fake_groq, monkeypatch):
    """A FastAPI TestClient whose GroqClient talks to ``fake_groq``."""
    from fastapi.testclient import TestClient

    from app import main

    original_init = groq_client.GroqClient.__init__

    def patched_init(self, http_client: Optional[httpx.AsyncClient] = None):
        original_init(self, http_client=httpx.AsyncClient(transport=httpx.MockTransport(fake_groq.handler)))

    monkeypatch.setattr(groq_client.GroqClient, "__init__", patched_init)
    with TestClient(main.app) as client:
        yield client
