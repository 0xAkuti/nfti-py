"""
Database layer for the NFT Inspector API with support for multiple backends.
"""

import logging
import asyncio
from typing import TYPE_CHECKING, Optional

from .base import DatabaseManagerInterface

if TYPE_CHECKING:
    from .redis import RedisManager
    from .blob import BlobManager

logger = logging.getLogger(__name__)

# Module-level async lazy initialization
_database_manager: Optional[DatabaseManagerInterface] = None
_init_lock = asyncio.Lock()

async def _ensure_initialized() -> None:
    global _database_manager
    if _database_manager is not None:
        return
    async with _init_lock:
        if _database_manager is not None:
            return
        try:
            from ..config import settings
            backend = settings.DATABASE_BACKEND
            config = settings.get_database_config()
            manager = create_database_manager(backend, **config)
            await manager.initialize()
            _database_manager = manager
            logger.info(f"Initialized database with {backend} backend")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            _database_manager = None
            raise


def create_database_manager(backend: str, **kwargs) -> DatabaseManagerInterface:
    """
    Factory function to create database manager instances.
    
    Args:
        backend: Database backend type ("redis" or "blob")
        **kwargs: Backend-specific configuration parameters
        
    Returns:
        DatabaseManagerInterface instance
        
    Raises:
        ValueError: If backend is not supported
        ImportError: If required dependencies are missing
    """
    if backend == "redis":
        try:
            from .redis import RedisManager
            redis_url = kwargs.get('redis_url')
            if not redis_url:
                raise ValueError("redis_url is required for Redis backend")
            return RedisManager(redis_url=redis_url)
        except ImportError as e:
            raise ImportError(f"Redis backend requires 'redis' package: {e}")
    
    elif backend == "blob":
        try:
            from .blob import BlobManager
            blob_token = kwargs.get('blob_read_write_token')
            if not blob_token:
                raise ValueError("blob_read_write_token is required for Blob backend")
            return BlobManager(blob_read_write_token=blob_token)
        except ImportError as e:
            raise ImportError(f"Blob backend requires 'vercel_blob' package: {e}")
    
    else:
        supported = ["redis", "blob"]
        raise ValueError(f"Unsupported backend '{backend}'. Supported: {supported}")


async def initialize_database(backend: str, **kwargs):
    """
    Initialize the global database manager.
    
    Args:
        backend: Database backend type
        **kwargs: Backend-specific configuration
    """
    # Optional pre-initialization; retained for backward compatibility
    await _ensure_initialized()


async def close_database():
    """Close the global database manager."""
    global _database_manager
    if _database_manager is not None:
        await _database_manager.close()
        _database_manager = None
        logger.info("Closed database connection")


async def get_database_manager_async() -> DatabaseManagerInterface:
    """
    Get the global database manager instance asynchronously.
    
    Returns:
        DatabaseManagerInterface instance
        
    Raises:
        RuntimeError: If database initialization fails
    """
    await _ensure_initialized()
    assert _database_manager is not None
    return _database_manager