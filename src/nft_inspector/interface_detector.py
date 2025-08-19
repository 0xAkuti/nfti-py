from .types import Interface, NFTStandard, RpcResult
from .chains.web3_wrapper import EnhancedWeb3


class InterfaceDetector:
    """Modular ERC-165 interface detection system for extensible standard detection."""
    SUPPORTS_INTERFACE_ABI = [
        {
            "inputs": [{"internalType": "bytes4", "name": "interfaceId", "type": "bytes4"}],
            "name": "supportsInterface",
            "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
            "stateMutability": "view",
            "type": "function"
        }
    ]
    
    def __init__(self, w3: EnhancedWeb3):
        """Initialize interface detector with Web3 instance and contract address."""
        self.w3 = w3
    
    async def supports_interface(self, contract_address: str, interface_id: str) -> RpcResult[bool]:
        """
        Check if contract supports a specific interface.
        
        Args:
            interface_id: The 4-byte interface ID (e.g., "0x80ac58cd")
            
        Returns:
            RpcResult containing boolean result or error information
        """
        contract_address = self.w3.to_checksum_address(contract_address)
        contract = self.w3.eth.contract(address=contract_address, abi=self.SUPPORTS_INTERFACE_ABI)

        try:
            return await self.w3.async_call_contract_function(
                contract.functions.supportsInterface(interface_id)
            )
        except Exception as e:
            # If supportsInterface itself is not supported, assume interface is not supported
            return RpcResult.success_result(False)
    
    async def detect_nft_standard(self, contract_address: str) -> NFTStandard:
        """
        Detect which NFT standard (ERC-721 or ERC-1155) the contract implements.
        
        Returns:
            NFTStandard enum value indicating the detected standard
        """
        # Check ERC-721 first (more common)
        erc721_result = await self.supports_interface(contract_address, Interface.ERC721.value)
        if erc721_result.success and erc721_result.result:
            return NFTStandard.ERC721
        
        # Check ERC-1155
        erc1155_result = await self.supports_interface(contract_address, Interface.ERC1155.value)
        if erc1155_result.success and erc1155_result.result:
            return NFTStandard.ERC1155
        
        # If neither is detected, return unknown
        return NFTStandard.UNKNOWN
    
    async def get_supported_interfaces(self, contract_address: str) -> dict[Interface, bool]:
        """
        Get all supported interfaces from the known interface list.
        
        Returns:
            List of interface names that the contract supports
        """
        contract_address = self.w3.to_checksum_address(contract_address)
        contract = self.w3.eth.contract(address=contract_address, abi=self.SUPPORTS_INTERFACE_ABI)        
        results = await self.w3.async_batch_call_contract_functions(
            [
                contract.functions.supportsInterface(interface.value)
                for interface in Interface
            ]
        )
        
        return {
            interface: result.success and result.result 
                for interface, result in zip(Interface, results)
        }
