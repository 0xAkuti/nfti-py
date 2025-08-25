"""
Simple validation helpers.
"""

from fastapi import HTTPException


def validate_address(address: str) -> str:
    """Validate Ethereum address format and return checksum address."""
    if not address or not address.startswith("0x") or len(address) != 42:
        raise HTTPException(status_code=400, detail="Invalid address format")
    
    # Convert to checksum format for consistency with storage keys
    from web3 import Web3
    return Web3.to_checksum_address(address)


def validate_token_id(token_id: int) -> int:
    """Validate token ID."""
    if token_id < 0:
        raise HTTPException(status_code=400, detail="Token ID must be non-negative")
    return token_id