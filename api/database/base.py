"""
Abstract base class for database backends.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from src.nft_inspector.models import TokenInfo


class DatabaseManagerInterface(ABC):
    """Abstract interface for database operations."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the database connection/client."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the database connection/client."""
        pass

    @abstractmethod
    async def store_nft_analysis(self, token_info: TokenInfo) -> bool:
        """
        Store NFT analysis result in the database.
        
        Args:
            token_info: Complete token information including trust analysis
            
        Returns:
            True if stored successfully
        """
        pass

    @abstractmethod
    async def get_nft_analysis(self, chain_id: int, contract_address: str, token_id: int) -> Optional[TokenInfo]:
        """
        Retrieve NFT analysis from database.
        
        Args:
            chain_id: Blockchain ID
            contract_address: Contract address
            token_id: Token ID
            
        Returns:
            TokenInfo if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_leaderboard(
        self,
        scope: str = "global",
        chain_id: Optional[int] = None,
        start: int = 0,
        end: int = -1,
        reverse: bool = True
    ) -> List[Tuple[str, float]]:
        """
        Get leaderboard entries.
        
        Args:
            scope: Leaderboard scope ("global", "chain")
            chain_id: Chain ID for chain-specific leaderboard
            start: Start index
            end: End index (-1 for all)
            reverse: True for highest scores first
            
        Returns:
            List of (nft_key, score) tuples
        """
        pass

    @abstractmethod
    async def get_leaderboard_with_filters(
        self,
        filters: Dict[str, Any],
        start: int = 0,
        count: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get filtered leaderboard entries with full NFT data.
        
        Args:
            filters: Filter parameters
            start: Start index
            count: Number of entries to return
            
        Returns:
            List of NFT data dictionaries with scores
        """
        pass

    @abstractmethod
    async def find_existing_token_id(self, chain_id: int, contract_address: str) -> Optional[int]:
        """Find a token id for analyzed tokens of a contract.
        
        Args:
            chain_id: Blockchain ID
            contract_address: Contract address
            
        Returns:
            Token id or None if not found
        """
        pass

    @abstractmethod
    async def get_global_stats(self) -> Dict[str, Any]:
        """
        Get global statistics.
        
        Returns:
            Dictionary with total_analyses, average_score, last_updated
        """
        pass

    # Context manager support
    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()