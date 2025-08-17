from typing import Optional
from web3 import Web3

from .models import TokenInfo, NFTMetadata
from .uri_parsers import URIResolver
from .analyzer import UrlAnalyzer


ERC721_ABI = [
    {
        "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
        "name": "tokenURI",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function"
    }
]


class NFTInspector:
    def __init__(self, rpc_url: Optional[str] = None, analyze_media: bool = True):
        self.rpc_url = rpc_url or "https://eth.llamarpc.com"
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        self.uri_resolver = URIResolver()
        self.url_analyzer = UrlAnalyzer()
    
    def get_token_uri(self, contract_address: str, token_id: int) -> Optional[str]:
        try:
            contract_address = Web3.to_checksum_address(contract_address)
            contract = self.w3.eth.contract(address=contract_address, abi=ERC721_ABI)
            
            token_uri = contract.functions.tokenURI(token_id).call()
            return token_uri if token_uri else None
            
        except Exception as e:
            print(f"Error getting tokenURI: {e}")
            return None
    
    async def fetch_metadata(self, token_uri: str) -> Optional[NFTMetadata]:
        try:
            metadata_json = await self.uri_resolver.resolve(token_uri)
            return NFTMetadata.model_validate(metadata_json)
            
        except Exception as e:
            print(f"Error fetching metadata: {e}")
            return None
    
    async def inspect_token(self, contract_address: str, token_id: int) -> TokenInfo:
        token_uri = self.get_token_uri(contract_address, token_id)
        metadata = None
        data_report = None
        
        if token_uri:
            metadata = await self.fetch_metadata(token_uri)
            
            if metadata:
                data_report = await self.url_analyzer.analyze(token_uri, metadata)
        
        return TokenInfo(
            contract_address=contract_address,
            token_id=token_id,
            token_uri=token_uri,
            metadata=metadata,
            data_report=data_report
        )