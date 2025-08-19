from typing import Optional, List
from pydantic import BaseModel, Field, AliasChoices, model_validator
from .types import TokenURI, EthereumAddress, DisplayType, MediaProtocol, DataEncoding, WeakTokenURI, ProxyStandard


class NFTAttribute(BaseModel):
    trait_type: str
    value: str | int | float
    display_type: Optional[DisplayType] = None
    max_value: Optional[int | float] = None # only if value is a number


class ExternalResource(BaseModel):
    """Represents an external resource found in SVG or HTML content"""
    url: WeakTokenURI
    element_type: str  # e.g., "image", "use", "script", "style", "img", "iframe"
    attribute: str     # e.g., "href", "xlink:href", "src", "data"
    url_info: 'UrlInfo'


class DependencyReport(BaseModel):
    """Analysis report for external dependencies in SVG or HTML content"""
    is_fully_onchain: bool
    min_protocol_score: int
    min_protocol: Optional[MediaProtocol] = None
    external_resources: List[ExternalResource] = Field(default_factory=list)
    total_dependencies: int = 0


class UrlInfo(BaseModel):
    url: WeakTokenURI
    protocol: MediaProtocol
    is_gateway: bool = False
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    accessible: bool = True
    encoding: Optional[DataEncoding] = None
    error: Optional[str] = None
    external_dependencies: Optional[DependencyReport] = None


class TokenDataReport(BaseModel):
    token_uri: UrlInfo
    image: Optional[UrlInfo] = None
    animation_url: Optional[UrlInfo] = None
    external_url: Optional[UrlInfo] = None
    image_data: Optional[UrlInfo] = None


class ContractDataReport(BaseModel):
    contract_uri: UrlInfo
    image: Optional[UrlInfo] = None
    banner_image: Optional[UrlInfo] = None
    featured_image: Optional[UrlInfo] = None
    external_link: Optional[UrlInfo] = None


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


class ProxyInfo(BaseModel):
    """Information about proxy contract detection and configuration"""
    is_proxy: bool
    proxy_standard: ProxyStandard
    implementation_address: Optional[EthereumAddress] = None
    admin_address: Optional[EthereumAddress] = None
    beacon_address: Optional[EthereumAddress] = None
    
    # Diamond-specific fields
    facet_addresses: Optional[List[EthereumAddress]] = None
    
    # Additional metadata
    is_upgradeable: bool = False


class TokenInfo(BaseModel):
    contract_address: EthereumAddress
    token_id: int
    token_uri: Optional[TokenURI] = None
    metadata: Optional[NFTMetadata] = None
    data_report: Optional[TokenDataReport] = None
    contract_uri: Optional[TokenURI] = None
    contract_metadata: Optional["ContractURI"] = None
    contract_data_report: Optional[ContractDataReport] = None
    proxy_info: Optional[ProxyInfo] = None
    
    class Config:
        extra = "allow"

class ContractURI(BaseModel):
    name: str
    symbol: Optional[str] = None # prefer ERC721 metadata over this
    description: Optional[str] = None
    image: Optional[WeakTokenURI] = Field(
        default=None,
        validation_alias=AliasChoices('image', 'imageURI', 'image_url', 'logo', 'logo_url')
    )
    banner_image: Optional[WeakTokenURI] = None
    featured_image: Optional[WeakTokenURI] = None
    external_link: Optional[WeakTokenURI] = None
    seller_fee_basis_points: Optional[int] = None # prefer royalties standard over this
    fee_recipient: Optional[EthereumAddress] = None # prefer royalties standard over this
    collaborators: Optional[List[EthereumAddress]] = Field(default_factory=list)
    
    @model_validator(mode='before')
    @classmethod
    def capture_image_field(cls, data):
        if isinstance(data, dict):
            # Check which image field was actually used and store it
            for field_name in ['image', 'imageURI', 'image_url', 'logo', 'logo_url']:
                if field_name in data and data[field_name] is not None:
                    # Store the original field name in the instance
                    if not hasattr(cls, '_original_image_field'):
                        data['__pydantic_private__'] = {'image_field_used': field_name}
                    break
        return data

    def get_image_field_used(self) -> Optional[str]:
        """Returns the original field name that was used for the image"""
        private_attrs = getattr(self, '__pydantic_private__', None)
        if private_attrs and isinstance(private_attrs, dict):
            return private_attrs.get('image_field_used')
        return None

    class Config:
        extra = "allow"