"""
NFT analysis endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Body, Path, Query
import logging
from datetime import datetime

from src.nft_inspector.client import NFTInspector
from ..database import get_database_manager_async
from ..dependencies import validate_address, validate_token_id
from ..models import AnalysisRequest, AnalysisResponse, ContractAnalysisResponse
from ..auth import verify_api_key

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_nft(
    request: AnalysisRequest,
    api_key: str = Depends(verify_api_key)
):
    """Analyze an NFT and store results."""
    contract_address = validate_address(request.contract_address)
    token_id = validate_token_id(request.token_id)
    
    # Access DB once per handler
    db_manager = await get_database_manager_async()
    if not request.force_refresh:
        existing = await db_manager.get_nft_analysis(request.chain_id, contract_address, token_id)
        if existing:
            return AnalysisResponse(data=existing, from_storage=True)
    
    # Analyze
    inspector = NFTInspector(chain_id=request.chain_id, analyze_media=True, analyze_trust=True)
    token_info = await inspector.inspect_token(contract_address, token_id)
    
    if not token_info:
        raise HTTPException(status_code=404, detail="NFT not found")
    
    # Store
    await db_manager.store_nft_analysis(token_info)
    return AnalysisResponse(data=token_info, from_storage=False)


@router.get("/analyze/{chain_id}/{contract_address}/{token_id}", response_model=AnalysisResponse)
async def get_nft_analysis(
    chain_id: int,
    contract_address: str, 
    token_id: int,
    api_key: str = Depends(verify_api_key)
):
    """Get stored NFT analysis."""
    contract_address = validate_address(contract_address)
    token_id = validate_token_id(token_id)
    
    db_manager = await get_database_manager_async()
    result = await db_manager.get_nft_analysis(chain_id, contract_address, token_id)
    if not result:
        raise HTTPException(status_code=404, detail="NFT analysis not found")
    
    return AnalysisResponse(data=result, from_storage=True)


@router.get("/collection/{chain_id}/{contract_address}", response_model=AnalysisResponse)
async def get_collection_analysis(
    chain_id: int,
    contract_address: str,
    api_key: str = Depends(verify_api_key)
):
    """Get any analyzed token from this contract."""
    contract_address = validate_address(contract_address)
    
    # Find any analyzed token from this contract
    pattern = f"nft:{chain_id}:{contract_address}:*"
    db_manager = await get_database_manager_async()
    
    # Use the backend-agnostic method to find contract tokens
    token_id = await db_manager.find_existing_token_id(chain_id, contract_address)
    
    if not token_id:
        raise HTTPException(status_code=404, detail="No analyzed tokens found for this contract")
    
    # Get analysis
    result = await db_manager.get_nft_analysis(chain_id, contract_address, token_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Token analysis data corrupted")
    
    return AnalysisResponse(data=result, from_storage=True)