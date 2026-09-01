"""
Quiz generation service.
Takes generated patterns → returns cloze + multiple-choice questions.
"""
import json
from typing import List
from app.models.schemas import GeneratedPattern, QuizQuestion, GenerateQuizResponse
from app.services.groq_client import GroqClient


SYSTEM_PROMPT = """You are SchemaMind Quizzer. You take memory patterns and turn them into test questions.

Your output MUST be valid JSON matching:
{
  "questions": [
    {
      "type": "cloze" | "multiple_choice",
      "pattern_type": "which pattern this tests",
      "question": "Question text with ____ for the blank (cloze) or full question (MCQ)",
      "options": ["A) ...", "B) ...", "C) ...", "D) ..."]  // only for multiple_choice, null for cloze
    }
  ]
}

RULES:
1. Generate 4-6 questions total.
2. Mix cloze (fill-in-blank) and multiple-choice roughly 50/50.
3. Each question tests recall of something important from the patterns.
4. For cloze questions, use exactly ____ (4 underscores) to mark the blank.
5. For MCQ, provide exactly 4 options with A) B) C) D) prefixes.
6. The answer must be clearly derivable from the patterns provided."""


async def generate_quiz(patterns: List[GeneratedPattern]) -> GenerateQuizResponse:
    client = GroqClient()

    patterns_text = ""
    for p in patterns:
        patterns_text += f"\n## {p.label} ({p.type})\n{p.content}\n"

    user = f"""Here are the memory patterns to quiz on:
{patterns_text}

Generate 4-6 questions (mix of cloze and multiple-choice) that test understanding and recall of this material."""

    raw = await client.chat_json(SYSTEM_PROMPT, user)

    try:
        data = json.loads(raw)
        questions_data = data.get("questions", [])
    except (json.JSONDecodeError, KeyError):
        questions_data = []

    questions = []
    for i, q in enumerate(questions_data):
        questions.append(QuizQuestion(
            id=f"q-{i}",
            type=q.get("type", "cloze"),
            pattern_type=q.get("pattern_type", "general"),
            question=q.get("question", ""),
            options=q.get("options"),
            correct_answer=q.get("correct_answer", ""),
        ))

    return GenerateQuizResponse(questions=questions)