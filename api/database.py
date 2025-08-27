"""
Compatibility layer for database access.
This module provides backward compatibility for existing imports.
"""

# Import everything from the new database package
from .database import (
    DatabaseManagerInterface,
    create_database_manager,
    initialize_database,
    close_database,
    get_database_manager_async,
)

# For backward compatibility, maintain the old import pattern
# Import the specific backend classes if needed
try:
    from .database.redis import RedisManager
except ImportError:
    RedisManager = None

try:
    from .database.blob import BlobManager  
except ImportError:
    BlobManager = None

__all__ = [
    'DatabaseManagerInterface',
    'create_database_manager', 
    'initialize_database',
    'close_database',
    'get_database_manager_async',
    'RedisManager',
    'BlobManager'
]