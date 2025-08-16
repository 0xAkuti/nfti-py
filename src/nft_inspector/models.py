from typing import Optional, List, Any
from pydantic import BaseModel, Field
from .types import TokenURI, EthereumAddress


class NFTAttribute(BaseModel):
    trait_type: str
    value: Any
    display_type: Optional[str] = None


class NFTMetadata(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    image: Optional[TokenURI] = None
    image_data: Optional[TokenURI] = None
    animation_url: Optional[TokenURI] = None
    external_url: Optional[TokenURI] = None
    background_color: Optional[str] = None
    attributes: Optional[List[NFTAttribute]] = Field(default_factory=list)
    
    class Config:
        extra = "allow"


class TokenInfo(BaseModel):
    contract_address: EthereumAddress
    token_id: int
    token_uri: Optional[TokenURI] = None
    metadata: Optional[NFTMetadata] = None
    
    class Config:
        extra = "allow"