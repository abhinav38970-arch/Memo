from fastapi import APIRouter

from app.models.schemas import HealthResponse
from app.services.groq_client import GroqClient

router = APIRouter(tags=["Health"])


@router.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Liveness + effective Groq configuration (handy for debugging deploys)."""
    client = GroqClient()
    return HealthResponse(
        status="ok",
        model=client.model,
        groq=client.describe(),
    )
