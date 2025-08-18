from abc import ABC, abstractmethod


class URIParser(ABC):
    @abstractmethod
    def can_handle(self, uri: str) -> bool:
        """Check if this parser can handle the given URI"""
        pass
    
    @abstractmethod
    async def parse(self, uri: str) -> str:
        """Parse the URI and return raw content as a string"""
        pass