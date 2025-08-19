from typing import List, Optional, Dict, Any, Tuple
from .types import AccessControlType, GovernanceType, EthereumAddress, RpcResult
from .models import AccessControlInfo
from .chains.web3_wrapper import EnhancedWeb3


class AccessControlDetector:
    """Ultra-efficient access control detection service - minimal RPC calls"""
    
    # Interface IDs for standard detection
    ERC173_INTERFACE_ID = "0x7f5828d0"         # ERC-173 Ownership Standard
    ACCESS_CONTROL_INTERFACE_ID = "0x7965db0b"  # OpenZeppelin AccessControl
    ACCESS_CONTROL_ENUMS_INTERFACE_ID = "0x2360c304"  # OpenZeppelin AccessControl Enums
    
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
        },
        # AccessControlEnumerable getRoleMember
        {
            "inputs": [{"internalType": "bytes32", "name": "role", "type": "bytes32"}, {"internalType": "uint256", "name": "index", "type": "uint256"}],
            "name": "getRoleMember",
            "outputs": [{"internalType": "address", "name": "", "type": "address"}],
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
        
        essential_calls = [
            # Core ownership functions
            self.contract.functions.owner(),                    # Most common
            self.contract.functions.admin(),                    # Proxy admin
            
            # ERC-165 interface detection for AccessControl
            self.contract.functions.supportsInterface(self.ACCESS_CONTROL_INTERFACE_ID),     # Basic AccessControl
            self.contract.functions.supportsInterface(self.ACCESS_CONTROL_ENUMS_INTERFACE_ID), # AccessControl Enumerable
        ]
        
        # Single batch call - all results in one RPC request
        return await self.w3.async_batch_call_contract_functions(essential_calls)
    
    async def _analyze_batch_results(self, results: List[RpcResult[Any]]) -> AccessControlInfo:
        """Analyze all results locally - no additional RPC calls needed"""
        
        # Unpack batch results
        owner_result, admin_result, access_control_result, access_control_enum_result = results
        
        # Extract addresses and values from successful results
        owner_address = owner_result.result if owner_result.success else None
        admin_address = admin_result.result if admin_result.success else None
        has_access_control = access_control_result.success and access_control_result.result
        has_enumerable_access_control = access_control_enum_result.success and access_control_enum_result.result
        
        # Track whether functions succeeded (important for renounced ownership detection)
        owner_function_exists = owner_result.success
        admin_function_exists = admin_result.success
        
        # Determine access control type from batch results  
        access_type, governance_type = await self._classify_access_control(
            owner_address, admin_address, has_access_control, owner_function_exists, admin_function_exists
        )
        
        # Get role admin if AccessControl Enumerable is supported
        role_admin_address = None
        if has_enumerable_access_control and access_type == AccessControlType.ROLE_BASED:
            role_admin_address = await self._get_default_admin_role_member()
        
        # Determine primary control address (prioritize role admin for role-based systems)
        primary_address = role_admin_address or self._get_primary_control_address(owner_address, admin_address)
        
        # Get timelock delay if governance is timelock
        timelock_delay = None
        if governance_type == GovernanceType.TIMELOCK and primary_address:
            timelock_delay = await self.__get_timelock_delay(primary_address)
        
        return AccessControlInfo(
            access_control_type=access_type,
            governance_type=governance_type,
            has_owner=bool(owner_address and owner_address != self.ZERO_ADDRESS),
            owner_address=EthereumAddress.validate(primary_address) if primary_address else None,
            has_roles=has_access_control,
            admin_address=EthereumAddress.validate(role_admin_address or admin_address) if (role_admin_address or admin_address) and (role_admin_address or admin_address) != self.ZERO_ADDRESS else None,
            timelock_delay=timelock_delay
        )
    
    async def _classify_access_control(
        self, 
        owner_address: Optional[str], 
        admin_address: Optional[str], 
        has_access_control: bool,
        owner_function_exists: bool,
        admin_function_exists: bool
    ) -> Tuple[AccessControlType, GovernanceType]:
        """Classify access control type and governance type from batch results"""
        
        # Priority-based classification  
        if has_access_control:
            governance = await self._classify_governance_from_address(admin_address or owner_address)
            return AccessControlType.ROLE_BASED, governance
        
        # Check for ownership patterns (including renounced)
        if owner_function_exists:
            if owner_address and owner_address != self.ZERO_ADDRESS:
                # Owner function exists and returns non-zero address
                governance = await self._classify_governance_from_address(owner_address)
                return AccessControlType.OWNABLE, governance
            else:
                # Owner function exists but returns zero address (renounced ownership)
                return AccessControlType.OWNABLE, GovernanceType.RENOUNCED
        
        # Check for admin patterns
        if admin_function_exists:
            if admin_address and admin_address != self.ZERO_ADDRESS:
                governance = await self._classify_governance_from_address(admin_address)
                return AccessControlType.SIMPLE_OWNER, governance
            else:
                # Admin function exists but returns zero address
                return AccessControlType.SIMPLE_OWNER, GovernanceType.RENOUNCED
        
        # No access control functions found
        return AccessControlType.NONE, GovernanceType.UNKNOWN
    
    async def _classify_governance_from_address(self, address: Optional[str]) -> GovernanceType:
        """Classify governance type from address characteristics"""
        if not address or address == self.ZERO_ADDRESS:
            return GovernanceType.UNKNOWN
        
        try:
            # Get bytecode to determine if it's a contract or EOA
            bytecode = await self.w3.async_get_code(address)
            
            if len(bytecode) <= 2:  # EOA has no bytecode (empty or just '0x')
                return GovernanceType.EOA
            
            # For contracts, try specific pattern detection
            # Keep it fast - only check high-confidence patterns
            
            # Quick timelock check (single function call)
            if await self.__get_timelock_delay(address) is not None:
                return GovernanceType.TIMELOCK
            
            # Quick multisig check (single function call) 
            if await self._quick_multisig_check(address):
                return GovernanceType.MULTISIG
            
            # Default to generic contract
            return GovernanceType.CONTRACT
            
        except Exception:
            return GovernanceType.UNKNOWN
    
    async def _get_default_admin_role_member(self) -> Optional[str]:
        """Get the first member of DEFAULT_ADMIN_ROLE from AccessControlEnumerable"""
        try:
            result = await self.w3.async_call_contract_function(
                self.contract.functions.getRoleMember(self.ZERO_BYTES32, 0)  # DEFAULT_ADMIN_ROLE, index 0
            )
            return result.result if result.success else None
        except Exception:
            return None

    async def __get_timelock_delay(self, address: str) -> Optional[int]:
        """Quick check if address is a timelock contract, returns delay if found"""
        try:
            # Try calling getMinDelay() - TimelockController signature
            timelock_contract = self.w3.eth.contract(
                address=address, 
                abi=[{
                    "inputs": [],
                    "name": "getMinDelay",
                    "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                    "stateMutability": "view",
                    "type": "function"
                }]
            )
            result = await self.w3.async_call_contract_function(
                timelock_contract.functions.getMinDelay()
            )
            return result.result if result.success else None
        except Exception:
            return None
    
    
    async def _quick_multisig_check(self, address: str) -> bool:
        """Quick check if address is a multisig contract (single function call)"""
        try:
            # Check for Gnosis Safe getThreshold() function
            multisig_contract = self.w3.eth.contract(
                address=address,
                abi=[{
                    "inputs": [],
                    "name": "getThreshold", 
                    "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                    "stateMutability": "view",
                    "type": "function"
                }]
            )
            result = await self.w3.async_call_contract_function(
                multisig_contract.functions.getThreshold()
            )
            return result.success
        except Exception:
            return False
    
    def _get_primary_control_address(self, owner_address: Optional[str], admin_address: Optional[str]) -> Optional[str]:
        """Get the primary control address from available addresses"""
        # Prioritize owner over admin
        if owner_address and owner_address != self.ZERO_ADDRESS:
            return owner_address
        if admin_address and admin_address != self.ZERO_ADDRESS:
            return admin_address
        return None