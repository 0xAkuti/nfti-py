from typing import List, Optional, Dict
from .types import NFTStandard, RpcResult
from .chains.web3_wrapper import EnhancedWeb3


class InterfaceDetector:
    """Modular ERC-165 interface detection system for extensible standard detection."""
    
    # ERC-165 Interface IDs
    ERC165_INTERFACE_ID = "0x01ffc9a7"  # supportsInterface(bytes4)
    
    # NFT Standard Interface IDs
    ERC721_INTERFACE_ID = "0x80ac58cd"  # ERC-721 core functions
    ERC1155_INTERFACE_ID = "0xd9b67a26"  # ERC-1155 multi-token standard
    
    # Future extension interface IDs (ready for implementation)
    ERC2981_INTERFACE_ID = "0x2a55205a"  # NFT Royalty Standard
    ERC4907_INTERFACE_ID = "0xad092b5c"  # Rental NFT Extension
    ERC4906_INTERFACE_ID = "0x49064906"  # Metadata Update Extension
    
    # supportsInterface ABI
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
        
        # Interface ID to name mapping for future extensibility
        self.interface_names: Dict[str, str] = {
            self.ERC165_INTERFACE_ID: "ERC-165",
            self.ERC721_INTERFACE_ID: "ERC-721", 
            self.ERC1155_INTERFACE_ID: "ERC-1155",
            self.ERC2981_INTERFACE_ID: "ERC-2981",
            self.ERC4907_INTERFACE_ID: "ERC-4907",
            self.ERC4906_INTERFACE_ID: "ERC-4906"
        }
    
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
        erc721_result = await self.supports_interface(contract_address, self.ERC721_INTERFACE_ID)
        if erc721_result.success and erc721_result.result:
            return NFTStandard.ERC721
        
        # Check ERC-1155
        erc1155_result = await self.supports_interface(contract_address, self.ERC1155_INTERFACE_ID)
        if erc1155_result.success and erc1155_result.result:
            return NFTStandard.ERC1155
        
        # If neither is detected, return unknown
        return NFTStandard.UNKNOWN
    
    async def get_supported_interfaces(self, contract_address: str) -> List[str]:
        """
        Get all supported interfaces from the known interface list.
        
        Returns:
            List of interface names that the contract supports
        """
        supported = []
        
        for interface_id, interface_name in self.interface_names.items():
            result = await self.supports_interface(contract_address, interface_id)
            if result.success and result.result:
                supported.append(interface_name)
        
        return supported

