import httpx
from typing import Dict, Any
from .base import URIParser


class ArweaveParser(URIParser):
    def __init__(self, gateway: str = "https://arweave.net/", timeout: float = 30.0):
        self.gateway = gateway
        self.timeout = timeout
    
    def can_handle(self, uri: str) -> bool:
        return uri.startswith("ar://")
    
    async def parse(self, uri: str) -> Dict[str, Any]:
        arweave_id = uri.replace("ar://", "")
        http_url = f"{self.gateway}{arweave_id}"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(http_url)
            response.raise_for_status()
            return response.json()