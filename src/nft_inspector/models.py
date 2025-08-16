from typing import Optional, List
from pydantic import BaseModel, Field
from .types import TokenURI, EthereumAddress, DisplayType, MediaProtocol


class NFTAttribute(BaseModel):
    trait_type: str
    value: str | int | float
    display_type: Optional[DisplayType] = None
    max_value: Optional[int | float] = None # only if value is a number


class UrlInfo(BaseModel):
    url: TokenURI
    protocol: MediaProtocol
    is_gateway: bool = False
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    accessible: bool = True
    error: Optional[str] = None


class TokenDataReport(BaseModel):
    token_uri: UrlInfo
    image: Optional[UrlInfo] = None
    animation_url: Optional[UrlInfo] = None
    external_url: Optional[UrlInfo] = None
    image_data: Optional[UrlInfo] = None


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
    data_report: Optional[TokenDataReport] = None
    
    class Config:
        extra = "allow"