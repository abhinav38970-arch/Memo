from fastapi import APIRouter, HTTPException

from app.models.schemas import AdaptPatternsRequest, AdaptPatternsResponse
from app.routers._errors import http_error_from_exception
from app.services.adaptation_service import adapt_patterns

router = APIRouter(prefix="/api", tags=["Adaptation"])


@router.post("/adapt-patterns", response_model=AdaptPatternsResponse)
async def adapt_patterns_endpoint(req: AdaptPatternsRequest):
    """Adapt patterns based on user's wrong answers and failed types."""
    try:
        result = await adapt_patterns(req)
    except Exception as e:
        raise http_error_from_exception(e, action="pattern adaptation")
    if not result.adapted_patterns:
        raise HTTPException(
            status_code=502,
            detail="The AI returned no usable adapted patterns. Please try again.",
        )
    return result
