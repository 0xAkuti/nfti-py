from typing import Optional
from web3 import Web3

from .models import AccessControlInfo, ProxyInfo, TokenInfo, NFTMetadata, ContractURI
from .uri_parsers import URIResolver
from .analyzer import UrlAnalyzer
from .chains import ChainProvider
from .chains.web3_wrapper import EnhancedWeb3
from .types import Interface, RpcResult, NFTStandard, ComplianceReport
from .interface_detector import InterfaceDetector
from .proxy_detector import ProxyDetector
from .access_control_detector import AccessControlDetector
from .trust_analyzer import TrustAnalyzer
from .compliance_checker import NFTComplianceChecker


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
    },
    # uri(uint256 tokenId), ERC1155
    {
        "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
        "name": "uri",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function"
    }
]


def substitute_erc1155_id(uri: str, token_id: int) -> str:
    """
    Substitute {id} placeholder in ERC-1155 URI with actual token ID.
    
    According to ERC-1155 spec, the {id} should be replaced with the actual 
    token ID in hexadecimal form (lowercase, without 0x prefix).
    
    Args:
        uri: The URI template potentially containing {id} or {ID}
        token_id: The token ID to substitute
        
    Returns:
        URI with {id} replaced by hex token ID
    """
    if '{id}' not in uri and '{ID}' not in uri:
        return uri
    
    # Convert token ID to lowercase hex without 0x prefix
    hex_id = format(token_id, '064x')  # 64-character hex string (32 bytes)
    
    # Replace both {id} and {ID} variants
    uri = uri.replace('{id}', hex_id)
    uri = uri.replace('{ID}', hex_id)
    
    return uri


class NFTInspector:
    def __init__(self, rpc_url: Optional[str] = None, chain_id: Optional[int] = None, analyze_media: bool = True, analyze_trust: bool = True):
        self.chain_provider = ChainProvider()
        self.chain_id = chain_id or 1  # Default to Ethereum mainnet
        self.rpc_url = rpc_url
        self.w3: Optional[EnhancedWeb3] = None
        self.uri_resolver = URIResolver()
        self.url_analyzer = UrlAnalyzer()
        self.interface_detector = InterfaceDetector(self.w3) # web3 is still none
        self.analyze_media = analyze_media
        self.analyze_trust = analyze_trust
        
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

        self.interface_detector = InterfaceDetector(self.w3)
        self._connection_initialized = True
    
    async def set_chain(self, chain_id: int):
        """Switch to a different blockchain"""
        self.chain_id = chain_id
        self._connection_initialized = False
        await self._ensure_connection()

    async def get_contract_uri(self, contract_address: str) -> RpcResult[str]:
        await self._ensure_connection()
        contract = self.w3.eth.contract(address=contract_address, abi=NFT_ABI)
        
        result = await self.w3.async_call_contract_function(
            contract.functions.contractURI()
        )
        return result
    
    async def fetch_metadata(self, token_uri: str) -> Optional[NFTMetadata]:
        try:
            metadata_json = await self.uri_resolver.resolve_json(token_uri)
            return NFTMetadata.model_validate(metadata_json)
            
        except Exception as e:
            print(f"Error fetching metadata: {e}")
            return None
    
    async def fetch_token_and_contract_uri(self, contract_address: str, token_id: int) -> list[RpcResult[str]]:
        await self._ensure_connection()
        contract_address = self.w3.to_checksum_address(contract_address)

        nft_standard = await self.interface_detector.detect_nft_standard(contract_address)

        contract = self.w3.eth.contract(address=contract_address, abi=NFT_ABI)
        results = await self.w3.async_batch_call_contract_functions(
            [
                contract.functions.uri(token_id) if nft_standard == NFTStandard.ERC1155 else contract.functions.tokenURI(token_id),
                contract.functions.contractURI()
            ]
        )
        if nft_standard == NFTStandard.ERC1155 and results[0].success and results[0].result:
            results[0].result = substitute_erc1155_id(results[0].result, token_id)

        # TODO: handle if interface detection fails

        return results

    async def fetch_contract_metadata(self, contract_uri: str) -> Optional[ContractURI]:
        try:
            metadata_json = await self.uri_resolver.resolve_json(contract_uri)
            return ContractURI.model_validate(metadata_json)
            
        except Exception as e:
            print(f"Error fetching contract metadata: {e}")
            return None
    
    async def inspect_token(self, contract_address: str, token_id: int) -> TokenInfo:
        batch_results = await self.fetch_token_and_contract_uri(contract_address, token_id)
        token_uri_result, contract_uri_result = batch_results
        metadata = None
        contract_metadata = None
        data_report = None
        contract_data_report = None
        
        # Handle token URI result
        token_uri = token_uri_result.result if token_uri_result.success else None
        if token_uri:
            metadata = await self.fetch_metadata(token_uri)
            
            if metadata and self.analyze_media:
                data_report = await self.url_analyzer.analyze(token_uri, metadata)
        
        # Handle contract URI result  
        contract_uri = contract_uri_result.result if contract_uri_result.success else None
        if contract_uri:
            contract_metadata = await self.fetch_contract_metadata(contract_uri)
            
            if contract_metadata and self.analyze_media:
                contract_data_report = await self.url_analyzer.analyze_contract(contract_uri, contract_metadata)
        
        # Detect proxy information
        proxy_detector = ProxyDetector(self.w3, contract_address)
        proxy_info = await proxy_detector.detect_proxy_standard()
        
        # Detect access control information (separate service)
        access_control_detector = AccessControlDetector(self.w3, contract_address)
        access_control_info = await access_control_detector.analyze_access_control()
        
        # Detect supported interfaces
        supported_interfaces = await self.interface_detector.get_supported_interfaces(contract_address)
        
        # Check compliance with supported standards
        compliance_checker = NFTComplianceChecker(self.w3, supported_interfaces)
        compliance_report = await compliance_checker.check_compliance(contract_address, token_id)
        
        # Create TokenInfo first
        token_info = TokenInfo(
            contract_address=contract_address,
            token_id=token_id,
            token_uri=token_uri,
            metadata=metadata,
            data_report=data_report,
            contract_uri=contract_uri,
            contract_metadata=contract_metadata,
            contract_data_report=contract_data_report,
            proxy_info=proxy_info,
            access_control_info=access_control_info,
            supported_interfaces=supported_interfaces,
            compliance_report=compliance_report
        )
        
        # Perform trust analysis if enabled
        if self.analyze_trust:
            try:
                chain_info = self.get_current_chain_info()
                trust_analyzer = TrustAnalyzer(chain_info)
                token_info.trust_analysis = trust_analyzer.analyze_token_trust(token_info)
            except Exception:
                # Trust analysis is optional - don't fail the entire request
                pass
        
        return token_info
    
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
    
    async def get_supported_interfaces(self, contract_address: str) -> dict[Interface, bool]:
        await self._ensure_connection()
        return await self.interface_detector.get_supported_interfaces(contract_address)
    
    async def get_proxy_info(self, contract_address: str) -> ProxyInfo:
        await self._ensure_connection()
        proxy_detector = ProxyDetector(self.w3, contract_address)
        return await proxy_detector.detect_proxy_standard()
    
    async def check_compliance(self, contract_address: str, token_id: int) -> ComplianceReport:
        """Check NFT contract compliance with supported standards."""
        await self._ensure_connection()
        
        # First get supported interfaces
        supported_interfaces = await self.interface_detector.get_supported_interfaces(contract_address)
        
        # Then check compliance
        compliance_checker = NFTComplianceChecker(self.w3, supported_interfaces)
        return await compliance_checker.check_compliance(contract_address, token_id)

    async def get_access_control_info(self, contract_address: str) -> AccessControlInfo:
        await self._ensure_connection()
        access_control_detector = AccessControlDetector(self.w3, contract_address)
        return await access_control_detector.analyze_access_control()

    def get_current_chain_info(self):
        """Get information about the currently selected chain"""
        return self.chain_provider.get_chain_info(self.chain_id)
    
    def get_current_rpc_url(self) -> Optional[str]:
        """Get the currently used RPC URL"""
        if self.w3:
            return self.w3.provider.endpoint_uri
        return None
