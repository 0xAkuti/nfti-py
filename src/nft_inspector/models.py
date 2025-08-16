from typing import Optional, List, Any, Dict
from pydantic import BaseModel, HttpUrl, Field
from .types import TokenURI


class NFTAttribute(BaseModel):
    trait_type: str
    value: Any
    display_type: Optional[str] = None


class NFTMetadata(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    image: Optional[TokenURI] = None
    external_url: Optional[TokenURI] = None
    animation_url: Optional[TokenURI] = None
    background_color: Optional[str] = None
    attributes: Optional[List[NFTAttribute]] = Field(default_factory=list)
    properties: Optional[Dict[str, Any]] = None
    
    class Config:
        extra = "allow"


class TokenInfo(BaseModel):
    contract_address: str
    token_id: str
    token_uri: Optional[TokenURI] = None
    metadata: Optional[NFTMetadata] = None
    
    class Config:
        extra = "allow"