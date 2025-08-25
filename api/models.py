"""
Request and response models for the NFT Inspector API.
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from src.nft_inspector.models import TokenInfo


class AnalysisRequest(BaseModel):
    """Request to analyze an NFT."""
    chain_id: int
    contract_address: str
    token_id: int = Field(ge=0)
    force_refresh: bool = False


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: datetime
    database: str


class AnalysisResponse(BaseModel):
    """NFT analysis response."""
    data: TokenInfo
    from_storage: bool = False


class ContractAnalysisResponse(BaseModel):
    """Contract analysis response."""
    data: dict  # Contract metadata structure varies


class PaginationInfo(BaseModel):
    """Pagination information."""
    page: int
    size: int
    has_next: bool


class LeaderboardEntry(BaseModel):
    """Individual leaderboard entry."""
    rank: int
    chain_id: int
    contract_address: str
    token_id: int
    score: float
    stored_at: str


class LeaderboardResponse(BaseModel):
    """Leaderboard response with pagination."""
    data: List[LeaderboardEntry]
    pagination: PaginationInfo


class StatsResponse(BaseModel):
    """Global statistics response."""
    total_analyses: int
    average_score: float
    last_updated: str
