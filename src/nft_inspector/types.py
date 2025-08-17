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


class DataEncoding(str, Enum):
    """Enum for data URI encoding types"""
    BASE64 = "base64"
    PERCENT = "percent"
    PLAIN = "plain"


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