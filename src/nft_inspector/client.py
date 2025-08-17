from typing import Optional
from web3 import Web3

from .models import TokenInfo, NFTMetadata, ContractURI
from .uri_parsers import URIResolver
from .analyzer import UrlAnalyzer
from .chains import ChainProvider
from .chains.web3_wrapper import EnhancedWeb3
from .types import RpcResult


NFT_ABI = [
    # tokenURI(uint256 tokenId), ERC721
    {
        "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
        "name": "tokenURI",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function"
    },
    # contractURI()
    {
        "inputs": [],
        "name": "contractURI",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function"
    }
]


class NFTInspector:
    def __init__(self, rpc_url: Optional[str] = None, chain_id: Optional[int] = None, analyze_media: bool = True):
        self.chain_provider = ChainProvider()
        self.chain_id = chain_id or 1  # Default to Ethereum mainnet
        self.rpc_url = rpc_url
        self.w3: Optional[EnhancedWeb3] = None
        self.uri_resolver = URIResolver()
        self.url_analyzer = UrlAnalyzer()
        
        # Initialize Web3 connection (will be set up lazily in _ensure_connection)
        self._connection_initialized = False
    
    async def _ensure_connection(self):
        """Ensure Web3 connection is initialized"""
        if self._connection_initialized:
            return
        
        if self.rpc_url:
            # Use provided RPC URL
            self.w3 = EnhancedWeb3(Web3(Web3.HTTPProvider(self.rpc_url)))
        else:
            # Get working enhanced Web3 connection for the chain
            self.w3 = await self.chain_provider.get_enhanced_web3_connection(self.chain_id)
            if not self.w3:
                raise ValueError(f"No working RPC found for chain ID {self.chain_id}")
        
        self._connection_initialized = True
    
    async def set_chain(self, chain_id: int):
        """Switch to a different blockchain"""
        self.chain_id = chain_id
        self._connection_initialized = False
        await self._ensure_connection()
    
    async def get_token_uri(self, contract_address: str, token_id: int) -> RpcResult[str]:
        await self._ensure_connection()
        contract_address = self.w3.to_checksum_address(contract_address)
        contract = self.w3.eth.contract(address=contract_address, abi=NFT_ABI)
        
        result = await self.w3.async_call_contract_function(
            contract.functions.tokenURI(token_id),
            context=f"tokenURI for contract {contract_address} token {token_id}"
        )
        return result
    
    async def get_contract_uri(self, contract_address: str) -> RpcResult[str]:
        await self._ensure_connection()
        contract_address = self.w3.to_checksum_address(contract_address)
        contract = self.w3.eth.contract(address=contract_address, abi=NFT_ABI)
        
        result = await self.w3.async_call_contract_function(
            contract.functions.contractURI(),
            context=f"contractURI for contract {contract_address}"
        )
        return result
    
    async def fetch_metadata(self, token_uri: str) -> Optional[NFTMetadata]:
        try:
            metadata_json = await self.uri_resolver.resolve(token_uri)
            return NFTMetadata.model_validate(metadata_json)
            
        except Exception as e:
            print(f"Error fetching metadata: {e}")
            return None
    
    async def fetch_contract_metadata(self, contract_uri: str) -> Optional[ContractURI]:
        try:
            metadata_json = await self.uri_resolver.resolve(contract_uri)
            return ContractURI.model_validate(metadata_json)
            
        except Exception as e:
            print(f"Error fetching contract metadata: {e}")
            return None
    
    async def inspect_token(self, contract_address: str, token_id: int) -> TokenInfo:
        token_uri_result = await self.get_token_uri(contract_address, token_id)
        contract_uri_result = await self.get_contract_uri(contract_address)
        metadata = None
        contract_metadata = None
        data_report = None
        contract_data_report = None
        
        # Handle token URI result
        token_uri = token_uri_result.result if token_uri_result.success else None
        if token_uri:
            metadata = await self.fetch_metadata(token_uri)
            
            if metadata:
                data_report = await self.url_analyzer.analyze(token_uri, metadata)
        
        # Handle contract URI result  
        contract_uri = contract_uri_result.result if contract_uri_result.success else None
        if contract_uri:
            contract_metadata = await self.fetch_contract_metadata(contract_uri)
            
            if contract_metadata:
                contract_data_report = await self.url_analyzer.analyze_contract(contract_uri, contract_metadata)
        
        return TokenInfo(
            contract_address=contract_address,
            token_id=token_id,
            token_uri=token_uri,
            metadata=metadata,
            data_report=data_report,
            contract_uri=contract_uri,
            contract_metadata=contract_metadata,
            contract_data_report=contract_data_report
        )
    
    async def inspect_contract(self, contract_address: str) -> dict:
        """Inspect contract metadata only"""
        contract_uri_result = await self.get_contract_uri(contract_address)
        contract_metadata = None
        contract_data_report = None
        
        # Handle contract URI result
        contract_uri = contract_uri_result.result if contract_uri_result.success else None
        if contract_uri:
            contract_metadata = await self.fetch_contract_metadata(contract_uri)
            
            if contract_metadata:
                contract_data_report = await self.url_analyzer.analyze_contract(contract_uri, contract_metadata)
        
        return {
            "contract_address": contract_address,
            "contract_uri": contract_uri,
            "contract_metadata": contract_metadata,
            "contract_data_report": contract_data_report
        }
    
    def get_current_chain_info(self):
        """Get information about the currently selected chain"""
        return self.chain_provider.get_chain_info(self.chain_id)
    
    def get_current_rpc_url(self) -> Optional[str]:
        """Get the currently used RPC URL"""
        if self.w3:
            return self.w3.provider.endpoint_uri
        return None
