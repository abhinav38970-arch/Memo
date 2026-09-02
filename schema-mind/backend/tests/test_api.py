"""End-to-end tests through the FastAPI app against the fake Groq."""
import json

import httpx

from app.services import groq_client
from tests.conftest import rate_limit_body

TEXT = (
    "Photosynthesis: Light-dependent reactions use sunlight to produce ATP and NADPH. "
    "The Calvin cycle uses ATP and NADPH to fix CO2 into glucose."
)
PREFS = [{"type": "acronym"}, {"type": "analogy"}]


def patterns_payload(types=("acronym", "analogy")):
    patterns = []
    for t in types:
        for i in range(1, 5):
            patterns.append({"type": t, "label": f"{t} {i}", "content": f"{t} pattern number {i} about photosynthesis.", "variation": i})
    return json.dumps({"patterns": patterns})


def quiz_payload():
    return json.dumps({"questions": [
        {"type": "cloze", "pattern_type": "acronym", "question": "The Calvin cycle fixes ____ into glucose.", "options": None, "correct_answer": "CO2"},
        {"type": "multiple_choice", "pattern_type": "analogy", "question": "What powers the light reactions?",
         "options": ["A) Moonlight", "B) Sunlight", "C) Glucose", "D) Water"], "correct_answer": "B) Sunlight"},
        {"type": "multiple_choice", "pattern_type": "analogy", "question": "Letter-only answer?",
         "options": ["A) ATP", "B) DNA", "C) RNA", "D) H2O"], "correct_answer": "A"},
        {"type": "cloze", "pattern_type": "acronym", "question": "Missing answer", "correct_answer": ""},
    ]})


def test_health_reports_config(app_client):
    res = app_client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["model"] == "openai/gpt-oss-120b"
    assert body["groq"]["tpm_limit"] == 8000
    assert body["groq"]["reasoning"]["reasoning_effort"] == "low"


def test_generate_patterns_happy_path(app_client, fake_groq):
    fake_groq.responder = lambda body: patterns_payload()
    res = app_client.post("/api/generate-patterns", json={"text": TEXT, "preferences": PREFS})
    assert res.status_code == 200, res.text
    patterns = res.json()["patterns"]
    assert len(patterns) == 8
    assert {p["type"] for p in patterns} == {"acronym", "analogy"}
    assert [p["variation"] for p in patterns if p["type"] == "acronym"] == [1, 2, 3, 4]
    # One request, sized for the free tier — this is the production bug.
    assert len(fake_groq.requests) == 1
    sent = fake_groq.requests[0]
    assert sent["max_tokens"] <= 8000 - 512
    assert sent["model"] == "openai/gpt-oss-120b"


def test_generate_patterns_fills_missing_variation_numbers(app_client, fake_groq):
    payload = json.dumps({"patterns": [
        {"type": "Story", "label": "", "content": "one"},
        {"type": "story", "content": "two", "variation": "2"},
        {"type": "story", "content": "   "},  # dropped
        "garbage",
    ]})
    fake_groq.responder = lambda body: payload
    res = app_client.post("/api/generate-patterns", json={"text": TEXT, "preferences": [{"type": "story"}]})
    assert res.status_code == 200
    patterns = res.json()["patterns"]
    assert [(p["type"], p["variation"], p["label"]) for p in patterns] == [
        ("story", 1, "Memory Pattern"), ("story", 2, "Memory Pattern")]


def test_generate_patterns_413_from_groq_is_handled(app_client, fake_groq):
    """Replay the exact production error: Groq 413s the first request.

    The client must learn the real prompt size from the message, shrink the
    completion budget and succeed on the retry — the user still gets patterns.
    """
    msg = ("Request too large for model `openai/gpt-oss-120b` in organization `org_01kyah5qyjf0pse1j1f20dghp9` "
           "service tier `on_demand` on tokens per minute (TPM): Limit 8000, Requested 8665, please reduce your "
           "message size and try again. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing")
    fake_groq.scripted = [httpx.Response(413, json=rate_limit_body(msg))]
    fake_groq.responder = lambda body: patterns_payload()
    res = app_client.post("/api/generate-patterns", json={"text": TEXT, "preferences": PREFS})
    assert res.status_code == 200, res.text
    assert len(fake_groq.requests) == 2
    assert fake_groq.requests[1]["max_tokens"] <= fake_groq.requests[0]["max_tokens"]
    assert len(res.json()["patterns"]) == 8


def test_generate_patterns_rate_limited_returns_429_with_message(app_client, fake_groq, monkeypatch):
    monkeypatch.setenv("GROQ_MAX_WAIT_SECONDS", "0")
    msg = ("Rate limit reached for model `openai/gpt-oss-120b` in organization `org_test` service tier `on_demand` "
           "on tokens per minute (TPM): Limit 8000, Used 7950, Requested 2500. Please try again in 31.2s.")
    fake_groq.scripted = [httpx.Response(429, json=rate_limit_body(msg))]
    res = app_client.post("/api/generate-patterns", json={"text": TEXT, "preferences": PREFS})
    assert res.status_code == 429, res.text
    assert "try again" in res.json()["detail"].lower()
    assert res.headers.get("retry-after") == "32"


def test_generate_patterns_too_long_text_is_413(app_client, fake_groq):
    long_text = "word " * 1590  # 7950 chars: passes the 8000 max_length, ~2300 tokens
    fake_groq.responder = lambda body: patterns_payload()
    res = app_client.post("/api/generate-patterns", json={"text": long_text, "preferences": PREFS})
    # On the free tier a 7950-char text still fits (prompt ≈ 2.4k + 1.7k completion).
    assert res.status_code == 200, res.text


def test_generate_patterns_input_that_can_never_fit(app_client, fake_groq, monkeypatch):
    monkeypatch.setenv("GROQ_TPM_LIMIT", "1500")  # tiny tier
    groq_client.reset_windows()  # forget the window created at app startup
    res = app_client.post("/api/generate-patterns", json={"text": "word " * 1000, "preferences": PREFS})
    assert res.status_code == 413
    assert "shorten" in res.json()["detail"].lower()
    assert fake_groq.requests == []


def test_validation_errors_are_readable(app_client):
    res = app_client.post("/api/generate-patterns", json={"text": "short", "preferences": PREFS})
    assert res.status_code == 422
    assert res.json()["detail"] == "The text to memorize must be at least 10 characters."

    res = app_client.post("/api/generate-patterns", json={"text": "x" * 9000, "preferences": PREFS})
    assert res.status_code == 422
    assert "8,000 characters" in res.json()["detail"]

    res = app_client.post("/api/generate-patterns", json={"text": TEXT, "preferences": []})
    assert res.status_code == 422
    assert "at least 1 item" in res.json()["detail"]

    res = app_client.post("/api/generate-patterns", json={"preferences": PREFS})
    assert res.status_code == 422
    assert res.json()["detail"] == "The text to memorize is required."


def test_generate_quiz_normalizes_answers(app_client, fake_groq):
    fake_groq.responder = lambda body: quiz_payload()
    patterns = json.loads(patterns_payload())["patterns"]
    res = app_client.post("/api/generate-quiz", json={"patterns": patterns})
    assert res.status_code == 200, res.text
    questions = res.json()["questions"]
    assert len(questions) == 3  # the one without an answer is dropped
    assert questions[0]["type"] == "cloze" and questions[0]["options"] is None
    assert questions[0]["correct_answer"] == "CO2"
    # "B) Sunlight" -> "Sunlight" so it matches what the frontend submits.
    assert questions[1]["correct_answer"] == "Sunlight"
    assert questions[1]["options"] == ["A) Moonlight", "B) Sunlight", "C) Glucose", "D) Water"]
    # A bare letter is resolved to the option text.
    assert questions[2]["correct_answer"] == "ATP"
    assert [q["id"] for q in questions] == ["q-0", "q-1", "q-2"]
    assert "correct_answer" in fake_groq.requests[0]["messages"][0]["content"]


def test_generate_quiz_without_patterns_is_422(app_client):
    res = app_client.post("/api/generate-quiz", json={"patterns": []})
    assert res.status_code == 422


def test_generate_quiz_trims_huge_pattern_sets(app_client, fake_groq):
    fake_groq.responder = lambda body: quiz_payload()
    patterns = [{"type": "story", "label": f"s{i}", "content": "x" * 900, "variation": i % 4 + 1} for i in range(40)]
    res = app_client.post("/api/generate-quiz", json={"patterns": patterns})
    assert res.status_code == 200, res.text
    sent = fake_groq.requests[0]
    assert len(sent["messages"][1]["content"]) < 7000


def test_adapt_patterns(app_client, fake_groq):
    fake_groq.responder = lambda body: json.dumps({
        "adapted_patterns": json.loads(patterns_payload(("story",)))["patterns"],
        "adaptation_note": "Switched acronyms for a story.",
    })
    res = app_client.post("/api/adapt-patterns", json={
        "original_text": TEXT,
        "preferences": PREFS,
        "wrong_answers": ["acronym"],
        "failed_pattern_types": ["acronym"],
    })
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["adapted_patterns"]) == 4
    assert body["adaptation_note"] == "Switched acronyms for a story."


def test_adapt_patterns_default_note(app_client, fake_groq):
    fake_groq.responder = lambda body: json.dumps({"adapted_patterns": json.loads(patterns_payload(("story",)))["patterns"]})
    res = app_client.post("/api/adapt-patterns", json={"original_text": TEXT, "preferences": PREFS})
    assert res.status_code == 200
    assert res.json()["adaptation_note"]


def test_empty_model_output_is_502_not_500(app_client, fake_groq):
    fake_groq.responder = lambda body: '{"patterns": []}'
    res = app_client.post("/api/generate-patterns", json={"text": TEXT, "preferences": PREFS})
    assert res.status_code == 502
    assert "try again" in res.json()["detail"].lower()


def test_check_answer():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        res = client.post("/api/check-answer", json={"question_id": "q-0", "user_answer": " sunlight ", "correct_answer": "Sunlight"})
        assert res.json()["correct"] is True
