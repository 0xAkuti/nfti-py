"""
Leaderboard endpoints.
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional
import json
import logging
from datetime import datetime

from ..database import get_database_manager_async
from ..models import LeaderboardResponse, LeaderboardEntry, PaginationInfo, StatsResponse
from ..auth import verify_api_key

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    chain_id: Optional[int] = Query(None),
    api_key: str = Depends(verify_api_key)
):
    """Get NFT leaderboard."""
    # Simple pagination
    start = (page - 1) * size
    end = start + size - 1
    
    # Get entries from DB
    db_manager = await get_database_manager_async()
    # Use the generic leaderboard interface
    scope = "chain" if chain_id else "global"
    items = await db_manager.get_leaderboard_items(
        scope=scope,
        chain_id=chain_id,
        start=start,
        end=end,
        reverse=True
    )

    results = []
    for idx, item in enumerate(items):
        entry = LeaderboardEntry.model_validate(item.model_dump())
        entry.rank = start + idx + 1
        results.append(entry)
    
    return LeaderboardResponse(
        data=results,
        pagination=PaginationInfo(
            page=page,
            size=size,
            has_next=len(items) == size
        )
    )


@router.get("/stats", response_model=StatsResponse)
async def get_stats(api_key: str = Depends(verify_api_key)):
    """Get global statistics."""
    db_manager = await get_database_manager_async()
    stats_data = await db_manager.get_global_stats()
    return StatsResponse.model_validate(stats_data)


