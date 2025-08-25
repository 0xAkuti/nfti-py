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
    REDIS_URL: str = ""
    
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


settings = Settings()

# Validate required settings
if settings.ENVIRONMENT == "production" and not settings.REDIS_URL:
    raise ValueError("REDIS_URL is required in production")