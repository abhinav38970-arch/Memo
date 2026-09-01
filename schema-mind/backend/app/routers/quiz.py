from fastapi import APIRouter, HTTPException
from app.models.schemas import (
    GenerateQuizRequest, GenerateQuizResponse,
    CheckAnswerRequest, CheckAnswerResponse,
)
from app.services.quiz_service import generate_quiz

router = APIRouter(prefix="/api", tags=["Quiz"])


@router.post("/generate-quiz", response_model=GenerateQuizResponse)
async def generate_quiz_endpoint(req: GenerateQuizRequest):
    """Generate quiz questions from the generated patterns."""
    try:
        result = await generate_quiz(req.patterns)
        if not result.questions:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate quiz questions. Try again.",
            )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Quiz generation failed: {str(e)}",
        )


@router.post("/check-answer", response_model=CheckAnswerResponse)
async def check_answer(req: CheckAnswerRequest):
    """Check if a user's answer is correct (simple string match)."""
    is_correct = req.user_answer.strip().lower() == req.correct_answer.strip().lower()
    return CheckAnswerResponse(
        correct=is_correct,
        explanation="Correct!" if is_correct else f"Expected: {req.correct_answer}",
    )