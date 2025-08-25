"""
NFT analysis endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Body, Path, Query
import logging
from datetime import datetime

from src.nft_inspector.client import NFTInspector
from ..database import database_manager
from ..dependencies import validate_address, validate_token_id
from ..models import AnalysisRequest
from ..auth import verify_api_key

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze")
async def analyze_nft(
    request: AnalysisRequest,
    api_key: str = Depends(verify_api_key)
):
    """Analyze an NFT and store results."""
    contract_address = validate_address(request.contract_address)
    token_id = validate_token_id(request.token_id)
    
    # Check if already exists
    if not request.force_refresh:
        existing = await database_manager.get_nft_analysis(request.chain_id, contract_address, token_id)
        if existing:
            return {"data": existing.model_dump(), "from_storage": True}
    
    # Analyze
    inspector = NFTInspector(chain_id=request.chain_id, analyze_media=True, analyze_trust=True)
    token_info = await inspector.inspect_token(contract_address, token_id)
    
    if not token_info:
        raise HTTPException(status_code=404, detail="NFT not found")
    
    # Store
    await database_manager.store_nft_analysis(token_info)
    return {"data": token_info.model_dump(), "from_storage": False}


@router.get("/analyze/{chain_id}/{contract_address}/{token_id}")
async def get_nft_analysis(
    chain_id: int,
    contract_address: str, 
    token_id: int,
    api_key: str = Depends(verify_api_key)
):
    """Get stored NFT analysis."""
    contract_address = validate_address(contract_address)
    token_id = validate_token_id(token_id)
    
    result = await database_manager.get_nft_analysis(chain_id, contract_address, token_id)
    if not result:
        raise HTTPException(status_code=404, detail="NFT analysis not found")
    
    return {"data": result.model_dump()}


@router.post("/contract/{contract_address}")
async def analyze_contract(
    contract_address: str,
    chain_id: int = Query(1),
    api_key: str = Depends(verify_api_key)
):
    """Analyze contract metadata only."""
    contract_address = validate_address(contract_address)
    
    inspector = NFTInspector(chain_id=chain_id, analyze_media=True, analyze_trust=True)
    contract_data = await inspector.inspect_contract(contract_address)
    
    if not contract_data:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    return {"data": contract_data}


@router.get("/collection/{chain_id}/{contract_address}/stats")
async def get_collection_stats(
    chain_id: int,
    contract_address: str,
    api_key: str = Depends(verify_api_key)
):
    """Get collection statistics."""
    contract_address = validate_address(contract_address)
    collection_key = f"collection:{chain_id}:{contract_address}"
    
    collection_data = await database_manager.redis.hgetall(collection_key)
    if not collection_data:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    return {
        "chain_id": int(collection_data.get("chain_id", chain_id)),
        "contract_address": collection_data.get("contract_address", contract_address),
        "collection_name": collection_data.get("collection_name", ""),
        "token_count": int(collection_data.get("token_count", "0")),
        "average_score": float(collection_data.get("average_score", "0.0")),
        "last_updated": collection_data.get("last_updated", "")
    }