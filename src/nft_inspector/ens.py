"""
ENS (Ethereum Name Service) resolution utilities.
"""

import asyncio
import aiohttp
from typing import Optional
import logging

logger = logging.getLogger(__name__)


async def resolve_ens_name(address: str) -> Optional[str]:
    """
    Resolve an Ethereum address to its ENS name using ensdata.net API.
    
    Args:
        address: Ethereum address to resolve
        
    Returns:
        ENS name if found, None otherwise
        
    Example:
        >>> ens_name = await resolve_ens_name("0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045")
        >>> print(ens_name)  # "vitalik.eth"
    """
    if not address or address == "0x0000000000000000000000000000000000000000":
        return None
    
    url = f"https://api.ensdata.net/{address}"
    
    try:
        timeout = aiohttp.ClientTimeout(total=2.0)  # 2 second timeout
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 404:
                    # No ENS record found for this address
                    return None
                elif response.status == 200:
                    data = await response.json()
                    return data.get("ens")
                else:
                    logger.warning(f"ENS API returned status {response.status} for address {address}")
                    return None
                    
    except asyncio.TimeoutError:
        logger.warning(f"ENS resolution timeout for address {address}")
        return None
    except Exception as e:
        logger.debug(f"ENS resolution failed for address {address}: {e}")
        return None


async def resolve_multiple_ens_names(addresses: list[str]) -> dict[str, Optional[str]]:
    """
    Resolve multiple Ethereum addresses to their ENS names concurrently.
    
    Args:
        addresses: List of Ethereum addresses to resolve
        
    Returns:
        Dictionary mapping addresses to their ENS names (or None)
        
    Example:
        >>> addresses = ["0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045", "0x1234..."]
        >>> ens_names = await resolve_multiple_ens_names(addresses)
        >>> print(ens_names)  # {"0xd8dA...": "vitalik.eth", "0x1234...": None}
    """
    # Filter out invalid addresses
    valid_addresses = [
        addr for addr in addresses 
        if addr and addr != "0x0000000000000000000000000000000000000000"
    ]
    
    if not valid_addresses:
        return {addr: None for addr in addresses}
    
    # Create concurrent tasks for all addresses
    tasks = [resolve_ens_name(address) for address in valid_addresses]
    
    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Build result dictionary
    result_dict = {}
    for address in addresses:
        if address in valid_addresses:
            valid_index = valid_addresses.index(address)
            result = results[valid_index]
            # Handle exceptions from gather
            if isinstance(result, Exception):
                logger.debug(f"ENS resolution failed for {address}: {result}")
                result_dict[address] = None
            else:
                result_dict[address] = result
        else:
            result_dict[address] = None
            
    return result_dict