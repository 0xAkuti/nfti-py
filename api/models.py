"""
Request and response models for the NFT Inspector API.
"""

from typing import List, Optional, Union, Dict
from datetime import datetime
from pydantic import BaseModel, Field

from src.nft_inspector.models import TokenInfo, NFTInspectionResult


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
    data: NFTInspectionResult
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
    rank: Optional[int] = None
    chain_id: int
    contract_address: str
    token_id: int
    collection_name: str
    score: float
    permanence_score: int
    trustlessness_score: int
    stored_at: str


class LeaderboardResponse(BaseModel):
    """Leaderboard response with pagination."""
    data: List[LeaderboardEntry]
    pagination: PaginationInfo


class ScoreStatistics(BaseModel):
    """Statistics for a specific score type with full granularity."""
    average: float
    total: float  # sum of all scores for accurate average calculation
    histogram: Dict[int, int]  # score -> count mapping (0-100)
    
    def add_score(self, score: int, current_count: int) -> 'ScoreStatistics':
        """Return a new ScoreStatistics with the score added."""
        new_count = current_count + 1
        new_total = self.total + score
        new_average = round(new_total / new_count, 2)
        
        # Update histogram
        new_histogram = self.histogram.copy()
        if 0 <= score <= 100:
            new_histogram[score] = new_histogram.get(score, 0) + 1
        
        return ScoreStatistics(
            average=new_average,
            total=new_total,
            histogram=new_histogram
        )


class StatsResponse(BaseModel):
    """Global statistics response with detailed score distributions."""
    total_analyses: int

    # Detailed score statistics with full granularity
    total_score_stats: ScoreStatistics
    permanence_score_stats: ScoreStatistics
    trustlessness_score_stats: ScoreStatistics

    # Track analyzed collections to avoid double-counting
    analyzed_collections: List[str] = Field(default_factory=list)

    last_updated: str
