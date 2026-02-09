"""Health check endpoint."""

from datetime import datetime

from fastapi import APIRouter

from app import __version__
from app.models.responses import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version=__version__,
        timestamp=datetime.utcnow().isoformat()
    )
