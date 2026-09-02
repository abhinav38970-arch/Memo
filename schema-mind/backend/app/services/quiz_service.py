"""
Quiz generation service.
Takes generated patterns → returns cloze + multiple-choice questions.
"""
import json
import re
from typing import Any, Dict, List, Optional

from app.models.schemas import GeneratedPattern, GenerateQuizResponse, QuizQuestion
from app.services.groq_client import GroqClient

MAX_QUESTIONS = 6
# Cap how much pattern text we send back to the model — the user may have 20+
# patterns (4 variations × 5 types) and the free tier budget is only 8K TPM.
MAX_PATTERNS_CHARS = 6000
OPTION_PREFIX = re.compile(r"^\s*[A-Da-d]\s*[\)\.:\-]\s*")


SYSTEM_PROMPT = """You are SchemaMind Quizzer. You take memory patterns and turn them into test questions.

Your output MUST be valid JSON matching:
{
  "questions": [
    {
      "type": "cloze" | "multiple_choice",
      "pattern_type": "which pattern type this tests (acronym, analogy, story, ...)",
      "question": "Question text with ____ for the blank (cloze) or a full question (multiple_choice)",
      "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
      "correct_answer": "the exact answer text"
    }
  ]
}

RULES:
1. Generate 4-6 questions total.
2. Mix cloze (fill-in-blank) and multiple-choice roughly 50/50.
3. Each question tests recall of something important from the patterns.
4. For cloze questions, use exactly ____ (4 underscores) to mark the blank, set "options" to null, and make "correct_answer" the single word or short phrase (1-3 words) that fills the blank.
5. For multiple_choice, provide exactly 4 options prefixed "A) ", "B) ", "C) ", "D) ", and set "correct_answer" to the text of the correct option WITHOUT the letter prefix (e.g. "Mitochondria", not "B) Mitochondria").
6. The answer must be clearly derivable from the patterns provided.
7. Every question MUST include a non-empty "correct_answer".
8. Output only the JSON object — no markdown, no commentary."""


def _patterns_text(patterns: List[GeneratedPattern]) -> str:
    text = ""
    for p in patterns:
        block = f"\n## {p.label} ({p.type})\n{p.content.strip()}\n"
        if len(text) + len(block) > MAX_PATTERNS_CHARS:
            break
        text += block
    return text or "\n(no patterns)\n"


def _clean_str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _normalize_options(value: Any) -> Optional[List[str]]:
    if not isinstance(value, list):
        return None
    options = [_clean_str(o) for o in value if _clean_str(o)]
    if len(options) < 2:
        return None
    letters = "ABCD"
    normalized = []
    for i, opt in enumerate(options[:4]):
        body = OPTION_PREFIX.sub("", opt).strip() or opt
        normalized.append(f"{letters[i]}) {body}")
    return normalized


def _normalize_answer(answer: str, options: Optional[List[str]]) -> str:
    """Make the answer comparable to what the frontend submits.

    The frontend strips the "A) " prefix from a chosen option and compares
    case-insensitively, so the correct answer must be the bare option text.
    A bare letter ("B") or a prefixed option ("B) Foo") is resolved to "Foo".
    """
    answer = answer.strip()
    if options:
        letter = re.fullmatch(r"\(?([A-Da-d])[\)\.]?", answer)
        if letter:
            idx = "ABCD".index(letter.group(1).upper())
            if idx < len(options):
                return OPTION_PREFIX.sub("", options[idx]).strip()
        stripped = OPTION_PREFIX.sub("", answer).strip()
        for opt in options:
            body = OPTION_PREFIX.sub("", opt).strip()
            if body.lower() == stripped.lower():
                return body
        return stripped
    return answer.strip().strip(".").strip()


def parse_questions(raw: str) -> List[QuizQuestion]:
    """Turn the model's JSON into validated questions, dropping unusable ones."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("questions")
        if not isinstance(items, list):
            items = next((v for v in data.values() if isinstance(v, list)), [])
    else:
        items = []

    questions: List[QuizQuestion] = []
    for q in items:
        if not isinstance(q, dict):
            continue
        question = _clean_str(q.get("question"))
        if not question:
            continue
        options = _normalize_options(q.get("options"))
        qtype = _clean_str(q.get("type")).lower().replace("-", "_").replace(" ", "_")
        if qtype in ("mcq", "multiple", "multiplechoice", "multiple_choice"):
            qtype = "multiple_choice"
        elif qtype != "cloze":
            qtype = "multiple_choice" if options else "cloze"
        if qtype == "multiple_choice" and not options:
            qtype = "cloze"
        if qtype == "cloze":
            options = None
            if "____" not in question:
                question = re.sub(r"_{2,}", "____", question)
        answer = _normalize_answer(_clean_str(q.get("correct_answer") or q.get("answer")), options)
        if not answer:
            continue
        questions.append(QuizQuestion(
            id=f"q-{len(questions)}",
            type=qtype,
            pattern_type=_clean_str(q.get("pattern_type")) or "general",
            question=question,
            options=options,
            correct_answer=answer,
            context=_clean_str(q.get("context")) or None,
        ))
        if len(questions) >= MAX_QUESTIONS:
            break
    return questions


async def generate_quiz(patterns: List[GeneratedPattern]) -> GenerateQuizResponse:
    client = GroqClient()

    user = f"""Here are the memory patterns to quiz on:
{_patterns_text(patterns)}

Generate 4-6 questions (mix of cloze and multiple-choice) that test understanding and recall of this material. Include the correct_answer for every question."""

    raw = await client.chat_json(SYSTEM_PROMPT, user, max_tokens=1536, min_tokens=640)
    return GenerateQuizResponse(questions=parse_questions(raw))
