from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    CheckAnswerRequest, CheckAnswerResponse,
    GenerateQuizRequest, GenerateQuizResponse,
)
from app.routers._errors import http_error_from_exception
from app.services.quiz_service import generate_quiz

router = APIRouter(prefix="/api", tags=["Quiz"])


@router.post("/generate-quiz", response_model=GenerateQuizResponse)
async def generate_quiz_endpoint(req: GenerateQuizRequest):
    """Generate quiz questions from the generated patterns."""
    if not req.patterns:
        raise HTTPException(status_code=422, detail="Generate some patterns before starting a quiz.")
    try:
        result = await generate_quiz(req.patterns)
    except Exception as e:
        raise http_error_from_exception(e, action="quiz generation")
    if not result.questions:
        raise HTTPException(
            status_code=502,
            detail="The AI returned no usable quiz questions. Please try again.",
        )
    return result


@router.post("/check-answer", response_model=CheckAnswerResponse)
async def check_answer(req: CheckAnswerRequest):
    """Check if a user's answer is correct (simple string match)."""
    is_correct = req.user_answer.strip().lower() == req.correct_answer.strip().lower()
    return CheckAnswerResponse(
        correct=is_correct,
        explanation="Correct!" if is_correct else f"Expected: {req.correct_answer}",
    )
