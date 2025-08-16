from typing import Any
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
        
        # Return checksummed address
        return cls(Web3.to_checksum_address(value))
    
    def __repr__(self) -> str:
        return f"EthereumAddress('{self}')"