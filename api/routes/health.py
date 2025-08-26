"""
Health check endpoint.
"""

from time import timezone
from fastapi import APIRouter
from datetime import datetime

from ..database import get_database_manager
from ..models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check."""
    try:
        db_manager = get_database_manager()
        # Try to get stats as a health check for any backend
        await db_manager.get_global_stats()
        db_status = "connected"
    except Exception as e:
        db_status = "error"
    
    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        timestamp=datetime.now(timezone.utc).isoformat(),
        database=db_status
    )