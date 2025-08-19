from typing import List, Optional, Dict, Any, Tuple
from .types import AccessControlType, GovernanceType, EthereumAddress, RpcResult
from .models import AccessControlInfo
from .chains.web3_wrapper import EnhancedWeb3


class AccessControlDetector:
    """Ultra-efficient access control detection service - minimal RPC calls"""
    
    # Interface IDs for standard detection
    ERC173_INTERFACE_ID = "0x7f5828d0"         # ERC-173 Ownership Standard
    ACCESS_CONTROL_INTERFACE_ID = "0x7965db0b"  # OpenZeppelin AccessControl
    
    # Common constants
    ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
    ZERO_BYTES32 = "0x0000000000000000000000000000000000000000000000000000000000000000"
    
    # Optimized ABI for batch detection
    BATCH_DETECTION_ABI = [
        # ERC-165 supportsInterface
        {
            "inputs": [{"internalType": "bytes4", "name": "interfaceId", "type": "bytes4"}],
            "name": "supportsInterface",
            "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
            "stateMutability": "view",
            "type": "function"
        },
        # Common ownership functions
        {
            "inputs": [],
            "name": "owner",
            "outputs": [{"internalType": "address", "name": "", "type": "address"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "admin",
            "outputs": [{"internalType": "address", "name": "", "type": "address"}],
            "stateMutability": "view",
            "type": "function"
        },
        # AccessControl hasRole with DEFAULT_ADMIN_ROLE (0x00)
        {
            "inputs": [{"internalType": "bytes32", "name": "role", "type": "bytes32"}, {"internalType": "address", "name": "account", "type": "address"}],
            "name": "hasRole",
            "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
            "stateMutability": "view",
            "type": "function"
        },
        # TimelockController getMinDelay
        {
            "inputs": [],
            "name": "getMinDelay",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        }
    ]
    
    def __init__(self, w3: EnhancedWeb3, contract_address: str):
        """Initialize access control detector"""
        self.w3 = w3
        self.contract_address = w3.to_checksum_address(contract_address)
        self.contract = w3.eth.contract(address=self.contract_address, abi=self.BATCH_DETECTION_ABI)
    
    async def analyze_access_control(self) -> AccessControlInfo:
        """Single batch call strategy for maximum efficiency"""
        try:
            # Step 1: Single batch call to gather all essential information
            batch_results = await self._single_batch_detection()
            
            # Step 2: Local analysis of results (no additional RPC calls)
            return await self._analyze_batch_results(batch_results)
            
        except Exception:
            # Fallback to safe default if batch detection fails
            return AccessControlInfo(
                access_control_type=AccessControlType.NONE,
                governance_type=GovernanceType.UNKNOWN
            )
    
    async def _single_batch_detection(self) -> List[RpcResult[Any]]:
        """ONE batch call to gather all essential information"""
        
        # Essential function calls - carefully chosen for maximum info/call ratio
        essential_calls = [
            # ERC-165 interface checks (2 calls - high value)
            self.contract.functions.supportsInterface(self.ERC173_INTERFACE_ID),
            self.contract.functions.supportsInterface(self.ACCESS_CONTROL_INTERFACE_ID),
            
            # Core ownership functions (3 calls - essential)
            self.contract.functions.owner(),                    # Most common
            self.contract.functions.admin(),                    # Proxy admin
            self.contract.functions.hasRole(self.ZERO_BYTES32, self.contract_address),  # Check AccessControl with DEFAULT_ADMIN_ROLE
            
            # Timelock detection (1 call - high value if present)
            self.contract.functions.getMinDelay(),              # TimelockController
        ]
        
        # Single batch call - all results in one RPC request
        return await self.w3.async_batch_call_contract_functions(essential_calls)
    
    async def _analyze_batch_results(self, results: List[RpcResult[Any]]) -> AccessControlInfo:
        """Analyze all results locally - no additional RPC calls needed"""
        
        # Unpack batch results
        erc173_support, access_control_support, owner_result, admin_result, role_result, delay_result = results
        
        # Extract addresses and values from successful results
        owner_address = owner_result.result if owner_result.success else None
        admin_address = admin_result.result if admin_result.success else None
        has_roles = role_result.success and role_result.result
        timelock_delay = delay_result.result if delay_result.success else None
        supports_erc173 = erc173_support.success and erc173_support.result
        
        # Determine access control type from batch results
        access_type, governance_type = self._classify_access_control(
            owner_address, admin_address, has_roles, timelock_delay
        )
        
        # Determine primary control address
        primary_address = self._get_primary_control_address(owner_address, admin_address)
        
        return AccessControlInfo(
            access_control_type=access_type,
            governance_type=governance_type,
            has_owner=bool(owner_address and owner_address != self.ZERO_ADDRESS),
            owner_address=EthereumAddress.validate(primary_address) if primary_address else None,
            has_roles=has_roles,
            admin_address=EthereumAddress.validate(admin_address) if admin_address and admin_address != self.ZERO_ADDRESS else None,
            timelock_delay=timelock_delay,
            supports_erc173=supports_erc173
        )
    
    def _classify_access_control(
        self, 
        owner_address: Optional[str], 
        admin_address: Optional[str], 
        has_roles: bool, 
        timelock_delay: Optional[int]
    ) -> Tuple[AccessControlType, GovernanceType]:
        """Classify access control type and governance type from batch results"""
        
        # Priority-based classification
        if timelock_delay is not None:
            return AccessControlType.TIMELOCK, GovernanceType.TIMELOCK
        
        if has_roles:
            return AccessControlType.ROLE_BASED, self._classify_governance_from_address(admin_address or owner_address)
        
        if owner_address and owner_address != self.ZERO_ADDRESS:
            return AccessControlType.OWNABLE, self._classify_governance_from_address(owner_address)
        
        if admin_address and admin_address != self.ZERO_ADDRESS:
            return AccessControlType.SIMPLE_OWNER, self._classify_governance_from_address(admin_address)
        
        return AccessControlType.NONE, GovernanceType.UNKNOWN
    
    def _classify_governance_from_address(self, address: Optional[str]) -> GovernanceType:
        """Classify governance type from address characteristics"""
        if not address or address == self.ZERO_ADDRESS:
            return GovernanceType.UNKNOWN
        
        # This would ideally check if address is EOA vs contract
        # For now, we'll do a simple heuristic based on the address
        # Real implementation would check bytecode length
        return GovernanceType.CONTRACT  # Conservative assumption
    
    def _get_primary_control_address(self, owner_address: Optional[str], admin_address: Optional[str]) -> Optional[str]:
        """Get the primary control address from available addresses"""
        # Prioritize owner over admin
        if owner_address and owner_address != self.ZERO_ADDRESS:
            return owner_address
        if admin_address and admin_address != self.ZERO_ADDRESS:
            return admin_address
        return None
    
    async def _is_address_eoa(self, address: str) -> bool:
        """Check if address is an EOA (Externally Owned Account) vs contract"""
        try:
            # Get bytecode to determine if it's a contract
            bytecode = await self.w3.async_get_code(address)
            # EOA has no bytecode (empty or just '0x')
            return len(bytecode) <= 2
        except Exception:
            # If we can't determine, assume it's a contract (safer assumption)
            return False