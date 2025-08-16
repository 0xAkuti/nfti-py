from typing import Any
from enum import Enum
from pydantic import AnyUrl, GetCoreSchemaHandler
from pydantic.networks import UrlConstraints
from pydantic_core import core_schema
from web3 import Web3


class TokenURI(AnyUrl):
    """A type that will accept token URIs with various schemes"""
    
    _constraints = UrlConstraints(
        allowed_schemes=['http', 'https', 'ipfs', 'ipns', 'ar', 'data']
    )


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
    UNKNOWN = "unknown"