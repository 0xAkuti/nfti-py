"""
Simple authentication for the NFT Inspector API.
"""

from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

from .config import settings

# API key header
api_key_header = APIKeyHeader(name="X-API-Key")


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Verify API key or raise 401."""
    if not api_key or not settings.is_valid_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key