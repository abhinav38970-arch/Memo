from fastapi import APIRouter, HTTPException

from app.models.schemas import GeneratePatternsRequest, GeneratePatternsResponse
from app.routers._errors import http_error_from_exception
from app.services.pattern_service import generate_patterns

router = APIRouter(prefix="/api", tags=["Patterns"])


@router.post("/generate-patterns", response_model=GeneratePatternsResponse)
async def generate_patterns_endpoint(req: GeneratePatternsRequest):
    """Generate memory patterns from user text + preferences."""
    try:
        result = await generate_patterns(req.text, req.preferences)
    except Exception as e:
        raise http_error_from_exception(e, action="pattern generation")
    if not result.patterns:
        raise HTTPException(
            status_code=502,
            detail="The AI returned no usable patterns. Please try again (or shorten the text).",
        )
    return result
