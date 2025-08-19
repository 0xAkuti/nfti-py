from typing import Any, Optional, Generic, TypeVar
from enum import Enum
from pydantic import AnyUrl, GetCoreSchemaHandler, BaseModel
from pydantic.networks import UrlConstraints
from pydantic_core import core_schema
from web3 import Web3

T = TypeVar('T')


class TokenURI(AnyUrl):
    """A type that will accept token URIs with various schemes"""
    
    _constraints = UrlConstraints(
        allowed_schemes=['http', 'https', 'ipfs', 'ipns', 'ar', 'data']
    )

WeakTokenURI = TokenURI | str

class EthereumAddress(str):
    """A type that validates Ethereum addresses"""
    
    @classmethod
    def __get_pydantic_core_schema__(
        cls, 
        source_type: Any, 
        handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.str_schema(),
        )
    
    @classmethod
    def validate(cls, value: str) -> 'EthereumAddress':
        if not isinstance(value, str):
            raise ValueError("Ethereum address must be a string")
        
        if not Web3.is_address(value):
            raise ValueError(f"Invalid Ethereum address: {value}")
        
        return cls(Web3.to_checksum_address(value))
    
    def __repr__(self) -> str:
        return f"EthereumAddress('{self}')"


class DisplayType(str, Enum):
    """Enum for NFT attribute display types"""
    NUMBER = "number"
    BOOST_NUMBER = "boost_number"
    BOOST_PERCENTAGE = "boost_percentage"
    DATE = "date"


class MediaProtocol(str, Enum):
    """Enum for media protocols"""
    HTTP = "http"
    HTTPS = "https"
    IPFS = "ipfs"
    IPNS = "ipns"
    ARWEAVE = "ar"
    DATA_URI = "data"
    NONE = "none"
    UNKNOWN = "unknown"

    def get_score(self) -> int:
        """Get a score for the media protocol"""
        return {
            MediaProtocol.DATA_URI: 10,
            MediaProtocol.ARWEAVE: 8,
            MediaProtocol.IPFS: 6,
            MediaProtocol.IPNS: 4,
            MediaProtocol.HTTPS: 2,
            MediaProtocol.HTTP: 1,
            MediaProtocol.NONE: 0,
            MediaProtocol.UNKNOWN: 0
        }[self]


class DataEncoding(str, Enum):
    """Enum for data URI encoding types"""
    BASE64 = "base64"
    PERCENT = "percent"
    PLAIN = "plain"


class NFTStandard(str, Enum):
    """Enum for NFT standards"""
    ERC721 = "ERC-721"
    ERC1155 = "ERC-1155"
    UNKNOWN = "unknown"


class ProxyStandard(str, Enum):
    """Enum for proxy standards"""
    EIP_897 = "EIP-897"                    # DelegateProxy (legacy)
    EIP_1967_TRANSPARENT = "EIP-1967-Transparent"  # Transparent Proxy
    EIP_1822_UUPS = "EIP-1822-UUPS"       # Universal Upgradeable Proxy
    EIP_1167_MINIMAL = "EIP-1167-Minimal" # Clone/Minimal Proxy
    EIP_2535_DIAMOND = "EIP-2535-Diamond" # Diamond/Multi-Facet Proxy
    BEACON_PROXY = "Beacon"               # Beacon Proxy Pattern
    CUSTOM_PROXY = "Custom"               # Non-standard proxy
    NOT_PROXY = "not_proxy"               # Regular contract


class AccessControlType(str, Enum):
    """Core access control patterns - optimized for essential detection"""
    NONE = "none"
    SIMPLE_OWNER = "simple_owner"        # Basic owner() function
    OWNABLE = "ownable"                  # OpenZeppelin Ownable pattern
    ROLE_BASED = "role_based"            # AccessControl pattern
    TIMELOCK = "timelock"                # TimelockController governance
    CUSTOM = "custom"                    # Non-standard pattern


class GovernanceType(str, Enum):
    """Governance classification"""
    EOA = "eoa"                          # Externally Owned Account
    CONTRACT = "contract"                # Smart contract control
    MULTISIG = "multisig"                # Multi-signature control
    TIMELOCK = "timelock"                # Time-delayed execution
    UNKNOWN = "unknown"

class Interface(str, Enum):
    """Enum for ERC-165 interfaces"""
    ERC165 = "0x01ffc9a7" # ERC-165 interface
    ERC173 = "0x7f5828d0" # ownership standard
    ERC721 = "0x80ac58cd"

    ERC721_METADATA = "0x5b5e139f"
    ERC721_TOKEN_RECEIVER = "0x150b7a02"
    ERC721_ENUMERABLE = "0x780e9d63"

    ERC1155 = "0xd9b67a26"
    ERC1155_TOKEN_RECEIVER = "0x4e2312e0"
    ERC1155_METADATA_URI = "0x0e89341c"

    ERC2981 = "0x2a55205a" # royalty standard
    ERC4906 = "0x49064906" # metadata update events
    ERC4907 = "0xad092b5c" # rental extension
    ERC7572 = "0xe8a3d485" # contract metadata (not officially mentions ERC-165)
    ERC5192 = "0xb45a3c0e" # Minimal Soulbound NFT

    # less common
    # ERC5006 = "0xc26d96cc" # rental NFT, user extension, ERC-1155
    # ERC5007 = "0xf140be0d" # Time NFT, add start and end time to the NFT
    # ERC5007_COMPOSABLE = "0x75cf3842" # allows to mint from existing or merge two NFTs
    # ERC5521 = "" # Referable NFTs
    # ERC5725 = "" # transferable vesting NFTs


class RpcErrorType(str, Enum):
    """Enum for RPC error types"""
    SUCCESS = "success"
    RPC_ERROR = "rpc_error"
    CONTRACT_NOT_FOUND = "contract_not_found"
    FUNCTION_NOT_FOUND = "function_not_found"
    EXECUTION_REVERTED = "execution_reverted"
    CUSTOM_ERROR = "custom_error"
    PANIC_ERROR = "panic_error"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    UNKNOWN_ERROR = "unknown_error"


class RpcResult(BaseModel, Generic[T]):
    """Generic result wrapper for RPC calls with error handling"""
    success: bool
    error_type: Optional[RpcErrorType] = None
    error_message: Optional[str] = None
    error_data: Optional[dict] = None
    result: Optional[T] = None
    
    @classmethod
    def success_result(cls, result: T) -> 'RpcResult[T]':
        """Create a successful result"""
        return cls(success=True, error_type=RpcErrorType.SUCCESS, result=result)
    
    @classmethod
    def error_result(
        cls, 
        error_type: RpcErrorType, 
        error_message: str, 
        error_data: Optional[dict] = None
    ) -> 'RpcResult[T]':
        """Create an error result"""
        return cls(
            success=False,
            error_type=error_type,
            error_message=error_message,
            error_data=error_data
        )