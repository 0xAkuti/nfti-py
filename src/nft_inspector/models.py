from typing import Optional, List
from pydantic import BaseModel, Field
from .types import TokenURI, EthereumAddress, DisplayType, MediaProtocol, DataEncoding, WeakTokenURI


class NFTAttribute(BaseModel):
    trait_type: str
    value: str | int | float
    display_type: Optional[DisplayType] = None
    max_value: Optional[int | float] = None # only if value is a number


class UrlInfo(BaseModel):
    url: WeakTokenURI
    protocol: MediaProtocol
    is_gateway: bool = False
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    accessible: bool = True
    encoding: Optional[DataEncoding] = None
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
    image: Optional[WeakTokenURI] = None
    image_data: Optional[WeakTokenURI] = None
    animation_url: Optional[WeakTokenURI] = None
    external_url: Optional[WeakTokenURI] = None
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

class ContractURI(BaseModel):
    name: str
    symbol: Optional[str] = None # prefer ERC721 metadata over this
    description: Optional[str] = None
    image: Optional[WeakTokenURI] = None
    banner_image: Optional[WeakTokenURI] = None
    featured_image: Optional[WeakTokenURI] = None
    external_link: Optional[WeakTokenURI] = None
    seller_fee_basis_points: Optional[int] = None # prefer royalties standard over this
    fee_recipient: Optional[EthereumAddress] = None # prefer royalties standard over this
    collaborators: Optional[List[EthereumAddress]] = Field(default_factory=list)

    class Config:
        extra = "allow"