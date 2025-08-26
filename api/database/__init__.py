"""
Database layer for the NFT Inspector API with support for multiple backends.
"""

import logging
from typing import TYPE_CHECKING

from .base import DatabaseManagerInterface

if TYPE_CHECKING:
    from .redis import RedisManager
    from .blob import BlobManager

logger = logging.getLogger(__name__)


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


# Global database manager instance
database_manager: DatabaseManagerInterface = None


async def initialize_database(backend: str, **kwargs):
    """
    Initialize the global database manager.
    
    Args:
        backend: Database backend type
        **kwargs: Backend-specific configuration
    """
    global database_manager
    
    if database_manager is not None:
        logger.warning("Database already initialized, closing existing connection")
        await database_manager.close()
    
    database_manager = create_database_manager(backend, **kwargs)
    await database_manager.initialize()
    logger.info(f"Initialized database with {backend} backend")


async def close_database():
    """Close the global database manager."""
    global database_manager
    if database_manager is not None:
        await database_manager.close()
        database_manager = None
        logger.info("Closed database connection")


def get_database_manager() -> DatabaseManagerInterface:
    """
    Get the global database manager instance.
    
    Returns:
        DatabaseManagerInterface instance
        
    Raises:
        RuntimeError: If database is not initialized
    """
    if database_manager is None:
        raise RuntimeError("Database not initialized. Call initialize_database() first.")
    return database_manager