"""
Simple request models for the NFT Inspector API.
"""

from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    """Request to analyze an NFT."""
    chain_id: int
    contract_address: str
    token_id: int = Field(ge=0)
    force_refresh: bool = False