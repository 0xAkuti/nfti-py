"""
Configuration settings for the NFT Inspector API.
"""

from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Simple settings - just what we actually need."""
    
    ENVIRONMENT: str = "development"
    API_KEYS: str = ""  # Will be converted to list
    
    # Database configuration
    DATABASE_BACKEND: str = "blob"  # "redis" or "blob"
    REDIS_URL: str = ""
    BLOB_READ_WRITE_TOKEN: str = ""
    
    class Config:
        env_file = ".env"

    @property
    def api_keys_list(self) -> List[str]:
        """Convert comma-separated API_KEYS to list."""
        if not self.API_KEYS:
            return []
        return [key.strip() for key in self.API_KEYS.split(",") if key.strip()]

    def is_valid_api_key(self, api_key: str) -> bool:
        """Check if API key is valid."""
        keys = self.api_keys_list
        if not keys:
            return True  # Development mode
        return api_key in keys
    
    def get_database_config(self) -> dict:
        """Get database configuration for the selected backend."""
        if self.DATABASE_BACKEND == "redis":
            return {"redis_url": self.REDIS_URL}
        elif self.DATABASE_BACKEND == "blob":
            return {"blob_read_write_token": self.BLOB_READ_WRITE_TOKEN}
        else:
            raise ValueError(f"Unknown database backend: {self.DATABASE_BACKEND}")


settings = Settings()

# Validate required settings
if settings.ENVIRONMENT == "production":
    if settings.DATABASE_BACKEND == "redis" and not settings.REDIS_URL:
        raise ValueError("REDIS_URL is required for Redis backend in production")
    elif settings.DATABASE_BACKEND == "blob" and not settings.BLOB_READ_WRITE_TOKEN:
        raise ValueError("BLOB_READ_WRITE_TOKEN is required for Blob backend in production")
    elif settings.DATABASE_BACKEND not in ["redis", "blob"]:
        raise ValueError(f"Invalid DATABASE_BACKEND: {settings.DATABASE_BACKEND}. Must be 'redis' or 'blob'")