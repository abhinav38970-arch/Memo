"""Unit tests for the budget-aware Groq client."""
import json

import httpx
import pytest

from app.services import groq_client as g
from app.services.groq_client import (
    GroqBadOutputError,
    GroqError,
    GroqRateLimitError,
    GroqRequestTooLargeError,
    extract_json,
    parse_duration_seconds,
    parse_json_lenient,
    reasoning_params,
    repair_truncated_json,
)
from tests.conftest import completion, rate_limit_body

SYSTEM = "You are a JSON generator. " * 40  # ~1000 chars
USER = "Memorize this: " + "the mitochondria is the powerhouse of the cell. " * 30


def patterns_json(n: int = 4) -> str:
    return json.dumps({
        "patterns": [
            {"type": "acronym", "label": f"L{i}", "content": "Some content " * 10, "variation": i}
            for i in range(1, n + 1)
        ]
    })


# ── Pure helpers ────────────────────────────────────────────────────────────


def test_parse_duration_seconds():
    assert parse_duration_seconds("7.66s") == pytest.approx(7.66)
    assert parse_duration_seconds("1m2.5s") == pytest.approx(62.5)
    assert parse_duration_seconds("2h3m") == pytest.approx(7380)
    assert parse_duration_seconds("500ms") == pytest.approx(0.5)
    assert parse_duration_seconds("12") == pytest.approx(12)
    assert parse_duration_seconds(None) is None
    assert parse_duration_seconds("soon") is None


def test_reasoning_params_per_model(monkeypatch):
    assert reasoning_params("openai/gpt-oss-120b") == {"reasoning_effort": "low", "include_reasoning": False}
    assert reasoning_params("llama-3.3-70b-versatile") == {}
    assert reasoning_params("qwen/qwen3.6-27b") == {"reasoning_effort": "none", "reasoning_format": "hidden"}
    assert reasoning_params("qwen/qwen3.8-27b") == {"reasoning_effort": "low", "reasoning_format": "hidden"}
    monkeypatch.setenv("GROQ_REASONING_EFFORT", "medium")
    assert reasoning_params("openai/gpt-oss-20b")["reasoning_effort"] == "medium"
    monkeypatch.setenv("GROQ_REASONING_EFFORT", "off")
    assert reasoning_params("openai/gpt-oss-20b") == {}


def test_extract_json_handles_think_blocks_and_fences():
    assert json.loads(extract_json('<think>hmm</think>```json\n{"a": 1}\n```')) == {"a": 1}
    assert json.loads(extract_json('Sure! Here: {"a": [1, 2]} enjoy')) == {"a": [1, 2]}
    assert json.loads(extract_json('```json\n{"a": "b"}')) == {"a": "b"}


def test_repair_truncated_json_keeps_complete_elements():
    full = patterns_json(4)
    cut = full[: full.index('"label": "L4"')]  # chopped mid 4th object
    repaired = repair_truncated_json(cut)
    assert repaired is not None
    data = json.loads(repaired)
    assert [p["variation"] for p in data["patterns"]] == [1, 2, 3]


def test_repair_truncated_json_inside_string():
    cut = '{"patterns": [{"type": "story", "label": "x", "content": "once upon a ti'
    assert repair_truncated_json(cut) in (None, '{"patterns": []}')
    cut2 = '{"patterns": [{"type": "story", "label": "x", "content": "done"}, {"type": "sto'
    assert json.loads(repair_truncated_json(cut2)) == {"patterns": [{"type": "story", "label": "x", "content": "done"}]}


def test_parse_json_lenient_prefers_intact_json():
    assert parse_json_lenient('{"a": 1}') == '{"a": 1}'
    assert json.loads(parse_json_lenient('text before {"a": 1} after')) == {"a": 1}
    assert parse_json_lenient("no json here") is None
    assert parse_json_lenient("") is None


def test_parse_rate_limit_error_413_and_429():
    def make(status, msg):
        req = httpx.Request("POST", "http://x")
        resp = httpx.Response(status, request=req, json=rate_limit_body(msg))
        return g.APIStatusError(msg, response=resp, body=rate_limit_body(msg)["error"])

    info = g.parse_rate_limit_error(make(413, "Request too large for model `m` in organization `o` service tier `on_demand` on tokens per minute (TPM): Limit 8000, Requested 8665, please reduce your message size and try again."))
    assert info.kind == "too_large" and info.scope == "TPM" and info.limit == 8000 and info.requested == 8665

    info = g.parse_rate_limit_error(make(429, "Rate limit reached for model `m` in organization `o` service tier `on_demand` on tokens per minute (TPM): Limit 8000, Used 6200, Requested ~2500. Please try again in 12.5s."))
    assert info.kind == "exhausted" and info.used == 6200 and info.requested == 2500 and info.retry_in == pytest.approx(12.5)

    info = g.parse_rate_limit_error(make(429, "Rate limit reached for model `m` in organization `o` on requests per day (RPD): Limit 1000, Used 1000, Requested 1. Please try again in 2h3m4.5s."))
    assert info.scope == "RPD" and info.retry_in == pytest.approx(7384.5)


# ── The production bug: 413 on every request ────────────────────────────────


@pytest.mark.asyncio
async def test_first_request_fits_free_tier_budget(fake_groq, make_client):
    """With an 8000 TPM limit the very first request must already fit."""
    fake_groq.responder = lambda body: patterns_json()
    client = make_client()
    out = await client.chat_json(SYSTEM, USER, max_tokens=4096, min_tokens=512)
    assert json.loads(out)["patterns"]
    assert len(fake_groq.requests) == 1, "must succeed on the first try — no 413 round-trip"
    sent = fake_groq.requests[0]
    assert sent["max_tokens"] + g.estimate_prompt_tokens(SYSTEM, USER) <= 8000
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["reasoning_effort"] == "low"
    assert sent["include_reasoning"] is False
    assert "reasoning_format" not in sent  # unsupported by gpt-oss on Groq


@pytest.mark.asyncio
async def test_413_is_recovered_by_shrinking(fake_groq, make_client, monkeypatch):
    """If our estimate is too optimistic and Groq 413s, we shrink and retry once."""
    # Reproduce the old production config: a big completion budget on a tier
    # we wrongly believe is generous -> Groq answers 413.
    monkeypatch.setenv("GROQ_TPM_LIMIT", "30000")
    monkeypatch.setenv("GROQ_MAX_TOKENS", "8192")
    fake_groq.responder = lambda body: patterns_json()
    client = make_client()
    out = await client.chat_json(SYSTEM, USER, max_tokens=8192)
    assert json.loads(out)["patterns"]
    assert len(fake_groq.requests) == 2
    assert fake_groq.requests[0]["max_tokens"] + g.estimate_prompt_tokens(SYSTEM, USER) > 8000
    assert fake_groq.requests[1]["max_tokens"] + g.estimate_prompt_tokens(SYSTEM, USER) <= 8000
    assert client.window.limit == 8000 and client.window.limit_source in ("error", "header")


@pytest.mark.asyncio
async def test_limit_learned_from_headers_is_reused(fake_groq, make_client, monkeypatch):
    monkeypatch.setenv("GROQ_TPM_LIMIT", "30000")
    monkeypatch.setenv("GROQ_MAX_TOKENS", "8192")
    fake_groq.responder = lambda body: patterns_json()
    client = make_client()
    await client.chat_json(SYSTEM, USER, max_tokens=8192)
    assert len(fake_groq.requests) == 2  # 413 + fitted retry
    fake_groq.requests.clear()
    fake_groq.used = 0
    # Second call (new client instance, same process) must not 413 again.
    client2 = make_client()
    await client2.chat_json(SYSTEM, USER, max_tokens=8192)
    assert len(fake_groq.requests) == 1
    assert fake_groq.requests[0]["max_tokens"] + g.estimate_prompt_tokens(SYSTEM, USER) <= 8000


@pytest.mark.asyncio
async def test_input_too_large_gives_413_error_not_crash(fake_groq, make_client):
    huge = "word " * 7000  # ~35k chars -> ~10k tokens, can never fit 8000 TPM
    client = make_client()
    with pytest.raises(GroqRequestTooLargeError) as exc:
        await client.chat_json(SYSTEM, huge, max_tokens=4096, min_tokens=512)
    assert exc.value.status_code == 413
    assert "shorten" in str(exc.value).lower()
    assert fake_groq.requests == [], "we should not even send a request we know can't fit"


@pytest.mark.asyncio
async def test_429_partial_window_shrinks_to_fit(fake_groq, make_client, no_sleep):
    """Window partly used: shrink completion to what's left instead of failing."""
    fake_groq.used = 4500  # 3500 left this minute
    fake_groq.reset_in = 42.0
    fake_groq.responder = lambda body: patterns_json()
    client = make_client()
    out = await client.chat_json(SYSTEM, USER, max_tokens=4096, min_tokens=512)
    assert json.loads(out)["patterns"]
    assert len(fake_groq.requests) == 2  # 429, then a fitted retry
    assert fake_groq.requests[1]["max_tokens"] < fake_groq.requests[0]["max_tokens"]
    assert no_sleep == []  # no need to wait


@pytest.mark.asyncio
async def test_429_window_nearly_empty_waits_for_reset(fake_groq, make_client, no_sleep):
    fake_groq.used = 7900
    fake_groq.reset_in = 20.0
    fake_groq.responder = lambda body: patterns_json()

    real_simulate = fake_groq.simulate

    def simulate(body):
        resp = real_simulate(body)
        if resp.status_code == 429:
            # after the (fake) sleep the window resets
            fake_groq.used = 0
        return resp

    fake_groq.simulate = simulate
    client = make_client()
    out = await client.chat_json(SYSTEM, USER, max_tokens=4096, min_tokens=512)
    assert json.loads(out)["patterns"]
    assert len(no_sleep) == 1 and no_sleep[0] >= 20.0
    assert len(fake_groq.requests) == 2


@pytest.mark.asyncio
async def test_429_too_long_to_wait_raises_rate_limit_error(fake_groq, make_client, no_sleep, monkeypatch):
    monkeypatch.setenv("GROQ_MAX_WAIT_SECONDS", "5")
    fake_groq.used = 7900
    fake_groq.reset_in = 50.0
    client = make_client()
    with pytest.raises(GroqRateLimitError) as exc:
        await client.chat_json(SYSTEM, USER, max_tokens=4096, min_tokens=512)
    assert exc.value.status_code == 429
    assert exc.value.retry_after == pytest.approx(50.0, abs=1.0)
    assert "try again" in str(exc.value).lower()
    assert no_sleep == []


@pytest.mark.asyncio
async def test_daily_limit_is_reported_clearly(fake_groq, make_client, no_sleep):
    msg = ("Rate limit reached for model `openai/gpt-oss-120b` in organization `org_test` service tier "
           "`on_demand` on requests per day (RPD): Limit 1000, Used 1000, Requested 1. Please try again in 3h12m5s.")
    fake_groq.scripted = [httpx.Response(429, json=rate_limit_body(msg))]
    client = make_client()
    with pytest.raises(GroqRateLimitError) as exc:
        await client.chat_json(SYSTEM, USER)
    assert "daily request limit" in str(exc.value)
    assert "hours" in str(exc.value)


# ── JSON recovery paths ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_truncated_json_mode_output_is_repaired(fake_groq, make_client):
    full = patterns_json(4)
    fake_groq.responder = lambda body: full[: full.index('"label": "L4"')]
    client = make_client()
    out = await client.chat_json(SYSTEM, USER)
    assert [p["variation"] for p in json.loads(out)["patterns"]] == [1, 2, 3]
    assert len(fake_groq.requests) == 1


@pytest.mark.asyncio
async def test_json_validate_failed_salvage(fake_groq, make_client):
    fake_groq.scripted = [
        httpx.Response(400, json={"error": {
            "message": "Failed to generate JSON. Please adjust your prompt.",
            "type": "invalid_request_error",
            "code": "json_validate_failed",
            "failed_generation": "```json\n" + patterns_json(2) + "\n```",
        }})
    ]
    client = make_client()
    out = await client.chat_json(SYSTEM, USER)
    assert len(json.loads(out)["patterns"]) == 2
    assert len(fake_groq.requests) == 1


@pytest.mark.asyncio
async def test_json_validate_failed_falls_back_to_plain_mode(fake_groq, make_client):
    fake_groq.scripted = [
        httpx.Response(400, json={"error": {
            "message": "Failed to generate JSON.",
            "type": "invalid_request_error",
            "code": "json_validate_failed",
            "failed_generation": "I'm sorry, I cannot do that.",
        }})
    ]
    fake_groq.responder = lambda body: "Here you go:\n" + patterns_json(1)
    client = make_client()
    out = await client.chat_json(SYSTEM, USER)
    assert len(json.loads(out)["patterns"]) == 1
    assert len(fake_groq.requests) == 2
    assert "response_format" not in fake_groq.requests[1]
    assert "REMINDER" in fake_groq.requests[1]["messages"][0]["content"]


@pytest.mark.asyncio
async def test_unparseable_twice_raises_bad_output(fake_groq, make_client):
    fake_groq.responder = lambda body: "nope"
    client = make_client()
    with pytest.raises(GroqBadOutputError):
        await client.chat_json(SYSTEM, USER)
    assert len(fake_groq.requests) == 2


@pytest.mark.asyncio
async def test_reasoning_params_dropped_if_model_rejects_them(fake_groq, make_client):
    def reject_reasoning(body):
        if "reasoning_effort" in body:
            return httpx.Response(400, json={"error": {
                "message": "property 'reasoning_effort' is unsupported",
                "type": "invalid_request_error"}})
        return fake_groq.simulate(body)

    fake_groq.scripted = [reject_reasoning]
    fake_groq.responder = lambda body: patterns_json(1)
    client = make_client()
    out = await client.chat_json(SYSTEM, USER)
    assert json.loads(out)["patterns"]
    assert "reasoning_effort" not in fake_groq.requests[-1]


# ── Other failures surface as clear GroqErrors ──────────────────────────────


@pytest.mark.asyncio
async def test_auth_error_is_clear(fake_groq, make_client):
    fake_groq.scripted = [httpx.Response(401, json={"error": {"message": "Invalid API Key", "type": "invalid_request_error", "code": "invalid_api_key"}})]
    client = make_client()
    with pytest.raises(GroqError) as exc:
        await client.chat_json(SYSTEM, USER)
    assert "GROQ_API_KEY" in str(exc.value)


@pytest.mark.asyncio
async def test_decommissioned_model_is_clear(fake_groq, make_client):
    fake_groq.scripted = [httpx.Response(400, json={"error": {
        "message": "The model `llama-3.3-70b-versatile` has been decommissioned and is no longer supported.",
        "type": "invalid_request_error", "code": "model_decommissioned"}})]
    client = make_client()
    with pytest.raises(GroqError) as exc:
        await client.chat_json(SYSTEM, USER)
    assert "GROQ_MODEL" in str(exc.value)


@pytest.mark.asyncio
async def test_server_error_retried_once_then_reported(fake_groq, make_client, no_sleep):
    fake_groq.scripted = [
        httpx.Response(503, json={"error": {"message": "Service Unavailable", "type": "internal_server_error"}}),
        httpx.Response(503, json={"error": {"message": "Service Unavailable", "type": "internal_server_error"}}),
    ]
    client = make_client()
    with pytest.raises(GroqError):
        await client.chat_json(SYSTEM, USER)
    assert len(fake_groq.requests) == 2


@pytest.mark.asyncio
async def test_server_error_then_success(fake_groq, make_client, no_sleep):
    fake_groq.scripted = [httpx.Response(500, json={"error": {"message": "boom", "type": "internal_server_error"}})]
    fake_groq.responder = lambda body: patterns_json(1)
    client = make_client()
    out = await client.chat_json(SYSTEM, USER)
    assert json.loads(out)["patterns"]


@pytest.mark.asyncio
async def test_env_max_tokens_caps_budget(fake_groq, make_client, monkeypatch):
    monkeypatch.setenv("GROQ_MAX_TOKENS", "900")
    fake_groq.responder = lambda body: patterns_json(1)
    client = make_client()
    await client.chat_json(SYSTEM, USER, max_tokens=4096)
    assert fake_groq.requests[0]["max_tokens"] == 900


@pytest.mark.asyncio
async def test_plain_chat_is_budgeted_too(fake_groq, make_client):
    fake_groq.responder = lambda body: "hello"
    client = make_client()
    assert await client.chat(SYSTEM, USER) == "hello"
    assert fake_groq.requests[0]["max_tokens"] + g.estimate_prompt_tokens(SYSTEM, USER) <= 8000
    assert "response_format" not in fake_groq.requests[0]
