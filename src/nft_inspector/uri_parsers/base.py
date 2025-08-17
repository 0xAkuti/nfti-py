from abc import ABC, abstractmethod
from typing import Dict, Any


class URIParser(ABC):
    @abstractmethod
    def can_handle(self, uri: str) -> bool:
        """Check if this parser can handle the given URI"""
        pass
    
    @abstractmethod
    async def parse(self, uri: str) -> Dict[str, Any]:
        """Parse the URI and return metadata as a dictionary"""
        pass