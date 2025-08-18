import httpx
from .base import URIParser


class HTTPParser(URIParser):
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
    
    def can_handle(self, uri: str) -> bool:
        return uri.startswith(("http://", "https://"))
    
    async def parse(self, uri: str) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(uri)
            response.raise_for_status()
            return response.text