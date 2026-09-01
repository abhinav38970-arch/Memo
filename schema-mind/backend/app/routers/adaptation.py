from fastapi import APIRouter, HTTPException
from app.models.schemas import AdaptPatternsRequest, AdaptPatternsResponse
from app.services.adaptation_service import adapt_patterns

router = APIRouter(prefix="/api", tags=["Adaptation"])


@router.post("/adapt-patterns", response_model=AdaptPatternsResponse)
async def adapt_patterns_endpoint(req: AdaptPatternsRequest):
    """Adapt patterns based on user's wrong answers and failed types."""
    try:
        result = await adapt_patterns(req)
        if not result.adapted_patterns:
            raise HTTPException(
                status_code=500,
                detail="Failed to adapt patterns. Try again.",
            )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Adaptation failed: {str(e)}",
        )