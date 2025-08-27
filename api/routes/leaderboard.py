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
    
    # Choose leaderboard based on chain filter
    if chain_id:
        leaderboard_key = f"leaderboard:chain:{chain_id}"
    else:
        leaderboard_key = "leaderboard:global"
    
    # Get entries from DB
    db_manager = await get_database_manager_async()
    # Use the generic leaderboard interface
    scope = "chain" if chain_id else "global"
    entries = await db_manager.get_leaderboard(
        scope=scope,
        chain_id=chain_id,
        start=start,
        end=end,
        reverse=True
    )
    
    results = []
    for idx, (nft_key, score) in enumerate(entries):
        # Parse NFT key to get components
        try:
            parts = nft_key.split(':')
            if len(parts) >= 4:
                entry_chain_id = int(parts[1])
                entry_contract = parts[2]
                entry_token_id = int(parts[3])
                
                # Get the full token info
                token_info = await db_manager.get_nft_analysis(entry_chain_id, entry_contract, entry_token_id)
                if not token_info:
                    continue
                
                # Convert to dict format expected by the rest of the code
                nft_data = {
                    "chain_id": str(entry_chain_id),
                    "contract_address": entry_contract.lower(),
                    "token_id": str(entry_token_id),
                    "stored_at": datetime.now().isoformat(),
                    "token_info": json.dumps(token_info.model_dump(mode='json'))
                }
            else:
                continue
        except (ValueError, IndexError):
            continue
        if nft_data:
            # Extract individual scores from trust analysis
            permanence_score = None
            trustlessness_score = None
            
            try:
                import json
                token_info_data = json.loads(nft_data.get("token_info", "{}"))
                trust_analysis = token_info_data.get("trust_analysis")
                if trust_analysis:
                    permanence_score = trust_analysis.get("permanence", {}).get("overall_score")
                    trustlessness_score = trust_analysis.get("trustlessness", {}).get("overall_score")
            except (json.JSONDecodeError, AttributeError, KeyError):
                # If we can't parse trust analysis, individual scores remain None
                pass
            
            results.append(LeaderboardEntry(
                rank=start + idx + 1,
                chain_id=int(nft_data.get("chain_id", "1")),
                contract_address=nft_data.get("contract_address", ""),
                token_id=int(nft_data.get("token_id", "0")),
                score=float(score),
                permanence_score=permanence_score,
                trustlessness_score=trustlessness_score,
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
    db_manager = await get_database_manager_async()
    stats_data = await db_manager.get_global_stats()
    return StatsResponse(
        total_analyses=stats_data.get("total_analyses", 0),
        average_score=stats_data.get("average_score", 0.0),
        last_updated=stats_data.get("last_updated", "")
    )


