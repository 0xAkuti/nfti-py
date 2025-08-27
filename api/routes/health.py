"""
Health check endpoint.
"""

from fastapi import APIRouter
from datetime import datetime, timezone

from ..database import get_database_manager_async
from ..models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check."""
    try:
        db_manager = await get_database_manager_async()
        # Try to get stats as a health check for any backend
        await db_manager.get_global_stats()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        timestamp=datetime.now(timezone.utc),
        database=db_status
    )