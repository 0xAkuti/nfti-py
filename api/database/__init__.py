"""
Database layer for the NFT Inspector API with support for multiple backends.
"""

import logging
import threading
from typing import TYPE_CHECKING, Optional

from .base import DatabaseManagerInterface

if TYPE_CHECKING:
    from .redis import RedisManager
    from .blob import BlobManager

logger = logging.getLogger(__name__)


class DatabaseSingleton:
    """
    Thread-safe singleton for database manager.
    Provides lazy initialization on first access.
    """
    _instance: Optional['DatabaseSingleton'] = None
    _lock = threading.Lock()
    _database_manager: Optional[DatabaseManagerInterface] = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Singleton pattern - __init__ only runs once
        pass
    
    async def get_manager(self) -> DatabaseManagerInterface:
        """
        Get the database manager instance, initializing if necessary.
        
        Returns:
            DatabaseManagerInterface instance
            
        Raises:
            RuntimeError: If database initialization fails
        """
        if not self._initialized:
            await self._initialize_lazy()
        
        if self._database_manager is None:
            raise RuntimeError("Database manager failed to initialize")
        
        return self._database_manager
    
    async def _initialize_lazy(self):
        """Lazy initialization of the database manager."""
        with self._lock:
            if self._initialized:
                return
            
            try:
                from ..config import settings
                backend = settings.DATABASE_BACKEND
                config = settings.get_database_config()
                
                self._database_manager = create_database_manager(backend, **config)
                await self._database_manager.initialize()
                self._initialized = True
                logger.info(f"Lazy-initialized database with {backend} backend")
                
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                self._database_manager = None
                self._initialized = False
                raise RuntimeError(f"Database initialization failed: {e}")
    
    async def close(self):
        """Close the database manager."""
        with self._lock:
            if self._database_manager is not None:
                await self._database_manager.close()
                self._database_manager = None
                self._initialized = False
                logger.info("Closed database connection")


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


# Global singleton instance
_database_singleton = DatabaseSingleton()


async def initialize_database(backend: str, **kwargs):
    """
    Initialize the global database manager.
    
    Args:
        backend: Database backend type
        **kwargs: Backend-specific configuration
        
    Note: This function is kept for backward compatibility but is no longer required.
    The database will be automatically initialized on first access.
    """
    logger.warning("initialize_database() is deprecated. Database will be auto-initialized.")
    # The singleton will handle initialization automatically


async def close_database():
    """Close the global database manager."""
    await _database_singleton.close()


def get_database_manager() -> DatabaseManagerInterface:
    """
    Get the global database manager instance.
    
    Returns:
        DatabaseManagerInterface instance
        
    Raises:
        RuntimeError: If database is not initialized
    """
    # This function is kept for backward compatibility
    # It will be updated to work with the singleton pattern
    import asyncio
    
    try:
        # Try to get the event loop
        loop = asyncio.get_running_loop()
        # If we're in an async context, we need to handle this differently
        # For now, raise an error to guide users to the async version
        raise RuntimeError(
            "get_database_manager() called in async context. "
            "Use await get_database_manager_async() instead."
        )
    except RuntimeError:
        # No event loop running, this is a sync context
        raise RuntimeError(
            "get_database_manager() cannot be used in sync context. "
            "Use get_database_manager_async() in async functions."
        )


async def get_database_manager_async() -> DatabaseManagerInterface:
    """
    Get the global database manager instance asynchronously.
    
    Returns:
        DatabaseManagerInterface instance
        
    Raises:
        RuntimeError: If database initialization fails
    """
    return await _database_singleton.get_manager()