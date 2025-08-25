"""
Health check endpoint.
"""

from fastapi import APIRouter
from datetime import datetime

from ..database import database_manager
from ..models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check."""
    try:
        if database_manager.redis:
            await database_manager.redis.ping()
            db_status = "connected"
        else:
            db_status = "disconnected"
    except:
        db_status = "error"
    
    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        timestamp=datetime.utcnow(),
        database=db_status
    )