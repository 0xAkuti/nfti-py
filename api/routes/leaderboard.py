"""
Leaderboard endpoints.
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional
import logging

from ..database import database_manager
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
    
    # Choose leaderboard based on chain filter
    if chain_id:
        leaderboard_key = f"leaderboard:chain:{chain_id}"
    else:
        leaderboard_key = "leaderboard:global"
    
    # Get entries from Redis sorted set
    entries = await database_manager.redis.zrevrange(leaderboard_key, start, end, withscores=True)
    
    results = []
    for idx, (nft_key, score) in enumerate(entries):
        nft_data = await database_manager.redis.hgetall(nft_key)
        if nft_data:
            results.append(LeaderboardEntry(
                rank=start + idx + 1,
                chain_id=int(nft_data.get("chain_id", "1")),
                contract_address=nft_data.get("contract_address", ""),
                token_id=int(nft_data.get("token_id", "0")),
                score=float(score),
                stored_at=nft_data.get("stored_at", "")
            ))
    
    return LeaderboardResponse(
        data=results,
        pagination=PaginationInfo(
            page=page,
            size=size,
            has_next=len(entries) == size
        )
    )


@router.get("/stats", response_model=StatsResponse)
async def get_stats(api_key: str = Depends(verify_api_key)):
    """Get global statistics."""
    stats = await database_manager.redis.hgetall("stats:global")
    return StatsResponse(
        total_analyses=int(stats.get("total_analyses", "0")),
        average_score=float(stats.get("average_score", "0.0")),
        last_updated=stats.get("last_updated", "")
    )


