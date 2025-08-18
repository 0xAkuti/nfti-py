import httpx
from .base import URIParser


class IPFSParser(URIParser):
    def __init__(self, gateway: str = "https://ipfs.io/ipfs/", timeout: float = 30.0):
        self.gateway = gateway
        self.timeout = timeout
    
    def can_handle(self, uri: str) -> bool:
        return uri.startswith("ipfs://")
    
    async def parse(self, uri: str) -> str:
        ipfs_hash = uri.replace("ipfs://", "")
        http_url = f"{self.gateway}{ipfs_hash}"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(http_url)
            response.raise_for_status()
            return response.text