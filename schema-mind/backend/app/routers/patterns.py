from fastapi import APIRouter, HTTPException
from app.models.schemas import GeneratePatternsRequest, GeneratePatternsResponse
from app.services.pattern_service import generate_patterns

router = APIRouter(prefix="/api", tags=["Patterns"])


@router.post("/generate-patterns", response_model=GeneratePatternsResponse)
async def generate_patterns_endpoint(req: GeneratePatternsRequest):
    """Generate memory patterns from user text + preferences."""
    try:
        result = await generate_patterns(req.text, req.preferences)
        if not result.patterns:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate patterns. The AI might be unavailable. Try again.",
            )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Pattern generation failed: {str(e)}",
        )