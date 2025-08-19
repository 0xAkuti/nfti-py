from typing import List, Optional, Dict, Any
from .types import ProxyStandard, EthereumAddress, RpcResult
from .models import ProxyInfo
from .chains.web3_wrapper import EnhancedWeb3


class ProxyDetector:
    """Efficient proxy detection system supporting all major proxy standards."""
    
    # EIP-1967 Standard Proxy Storage Slots
    EIP1967_IMPLEMENTATION_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
    EIP1967_ADMIN_SLOT = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103" 
    EIP1967_BEACON_SLOT = "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50"
    
    # EIP-1822 UUPS Storage Slot
    EIP1822_PROXIABLE_SLOT = "0xc5f16f0fcc639fa48a6947836d9850f504798523bf8c9a3a87d5876cf622bcf7"
    
    # EIP-1167 Minimal Proxy Bytecode Pattern (55 bytes total)
    # Pattern: 363d3d373d3d3d363d73[20-byte-address]5af43d82803e903d91602b57fd5bf3
    EIP1167_BYTECODE_PREFIX = "363d3d373d3d3d363d73"
    EIP1167_BYTECODE_SUFFIX = "5af43d82803e903d91602b57fd5bf3"
    
    # Diamond (EIP-2535) Interface IDs
    DIAMOND_LOUPE_INTERFACE_ID = "0x48e2b093"  # facets ^ facetFunctionSelectors ^ facetAddresses ^ facetAddress
    DIAMOND_CUT_INTERFACE_ID = "0x1f931c1c"    # diamondCut selector
    
    # Function selectors for detection
    FUNCTION_SELECTORS = {
        "facets": "0x7a0ed627",                    # facets() - Diamond loupe
        "facetFunctionSelectors": "0xadfca15e",    # facetFunctionSelectors(address)
        "facetAddresses": "0x52ef6b2c",           # facetAddresses()
        "facetAddress": "0xcdffacc6",             # facetAddress(bytes4)
        "diamondCut": "0x1f931c1c",               # diamondCut function
        "implementation": "0x5c60da1b",           # implementation() - common proxy
        "upgradeTo": "0x3659cfe6",                # upgradeTo(address) - UUPS
        "admin": "0xf851a440",                    # admin() - transparent proxy
        "beacon": "0x59659e90",                   # beacon() - beacon proxy
    }
    
    # Standard ABIs for proxy detection
    PROXY_DETECTION_ABI = [
        # ERC-165 supportsInterface
        {
            "inputs": [{"internalType": "bytes4", "name": "interfaceId", "type": "bytes4"}],
            "name": "supportsInterface",
            "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
            "stateMutability": "view",
            "type": "function"
        },
        # Diamond Loupe functions
        {
            "inputs": [],
            "name": "facets",
            "outputs": [{"components": [{"name": "facetAddress", "type": "address"}, {"name": "functionSelectors", "type": "bytes4[]"}], "name": "", "type": "tuple[]"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "facetAddresses",
            "outputs": [{"internalType": "address[]", "name": "", "type": "address[]"}],
            "stateMutability": "view",
            "type": "function"
        },
        # Common proxy functions
        {
            "inputs": [],
            "name": "implementation",
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
        {
            "inputs": [],
            "name": "beacon",
            "outputs": [{"internalType": "address", "name": "", "type": "address"}],
            "stateMutability": "view",
            "type": "function"
        }
    ]
    
    def __init__(self, w3: EnhancedWeb3, contract_address: str):
        """Initialize proxy detector with Web3 instance and contract address."""
        self.w3 = w3
        self.contract_address = w3.to_checksum_address(contract_address)
        self.contract = w3.eth.contract(address=self.contract_address, abi=self.PROXY_DETECTION_ABI)
    
    async def detect_proxy_standard(self) -> ProxyInfo:
        """
        Efficiently detect proxy standard using optimal detection order.
        Returns comprehensive proxy information in single function call.
        """
        # Step 1: Quick bytecode check for EIP-1167 (minimal proxy)
        bytecode_result = await self._check_minimal_proxy_bytecode()
        if bytecode_result:
            return bytecode_result
        
        # Step 2: Batch storage slot reading for EIP-1967/1822
        storage_result = await self._check_storage_based_proxies()
        if storage_result:
            return storage_result
        
        # Step 3: Diamond proxy detection
        diamond_result = await self._check_diamond_proxy()
        if diamond_result:
            return diamond_result
        
        # Step 4: Function signature detection (fallback)
        function_result = await self._check_function_based_proxies()
        if function_result:
            return function_result
        
        # Not a proxy
        return ProxyInfo(
            is_proxy=False,
            proxy_standard=ProxyStandard.NOT_PROXY
        )
    
    async def _check_minimal_proxy_bytecode(self) -> Optional[ProxyInfo]:
        """Check for EIP-1167 minimal proxy via bytecode pattern analysis."""
        try:
            # Get contract bytecode
            bytecode = await self.w3.async_get_code(self.contract_address)
            bytecode_hex = bytecode.hex()
            
            # Check for EIP-1167 pattern
            if (len(bytecode_hex) == 90 and  # 45 bytes runtime = 90 hex chars
                bytecode_hex.startswith(self.EIP1167_BYTECODE_PREFIX) and
                bytecode_hex.endswith(self.EIP1167_BYTECODE_SUFFIX)):
                
                # Extract implementation address (bytes 10-29, positions 20-59 in hex)
                impl_hex = bytecode_hex[20:60]  # 40 hex chars = 20 bytes
                impl_address = f"0x{impl_hex}"
                
                return ProxyInfo(
                    is_proxy=True,
                    proxy_standard=ProxyStandard.EIP_1167_MINIMAL,
                    implementation_address=EthereumAddress.validate(impl_address),
                    is_upgradeable=False
                )
        except Exception:
            pass
        
        return None
    
    async def _check_storage_based_proxies(self) -> Optional[ProxyInfo]:
        """Check for EIP-1967/1822 proxies via storage slot analysis."""
        try:
            # Batch read all relevant storage slots
            slots_to_read = [
                self.EIP1967_IMPLEMENTATION_SLOT,
                self.EIP1967_ADMIN_SLOT, 
                self.EIP1967_BEACON_SLOT,
                self.EIP1822_PROXIABLE_SLOT
            ]
            
            # Read all slots in parallel
            storage_values = []
            for slot in slots_to_read:
                value = await self.w3.async_get_storage_at(self.contract_address, slot)
                storage_values.append(value)
            
            impl_1967, admin_1967, beacon_1967, impl_1822 = storage_values
            
            def extract_address_from_storage(storage_bytes: bytes) -> Optional[str]:
                """Extract address from storage slot bytes, return None if zero address."""
                if len(storage_bytes) != 32:
                    return None
                # Address is in the last 20 bytes of the 32-byte slot
                address_bytes = storage_bytes[-20:]
                # Check if it's a zero address
                if address_bytes == b'\x00' * 20:
                    return None
                # Convert to checksummed address
                return self.w3.to_checksum_address(address_bytes)
            
            # Check EIP-1967 implementation slot
            impl_address = extract_address_from_storage(impl_1967)
            if impl_address:
                admin_address = extract_address_from_storage(admin_1967)
                beacon_address = extract_address_from_storage(beacon_1967)
                
                # Check if this is a beacon proxy
                if beacon_address:
                    return ProxyInfo(
                        is_proxy=True,
                        proxy_standard=ProxyStandard.BEACON_PROXY,
                        implementation_address=EthereumAddress.validate(impl_address),
                        beacon_address=EthereumAddress.validate(beacon_address),
                        is_upgradeable=True
                    )
                
                # Standard EIP-1967 transparent proxy
                return ProxyInfo(
                    is_proxy=True,
                    proxy_standard=ProxyStandard.EIP_1967_TRANSPARENT,
                    implementation_address=EthereumAddress.validate(impl_address),
                    admin_address=EthereumAddress.validate(admin_address) if admin_address else None,
                    is_upgradeable=True
                )
            
            # Check EIP-1822 UUPS slot
            uups_impl_address = extract_address_from_storage(impl_1822)
            if uups_impl_address:
                return ProxyInfo(
                    is_proxy=True,
                    proxy_standard=ProxyStandard.EIP_1822_UUPS,
                    implementation_address=EthereumAddress.validate(uups_impl_address),
                    is_upgradeable=True
                )
        except Exception:
            pass
        
        return None
    
    async def _check_diamond_proxy(self) -> Optional[ProxyInfo]:
        """Check for EIP-2535 Diamond proxy via interface and function detection."""
        try:
            # Check DiamondLoupe interface via ERC-165
            supports_loupe = await self.w3.async_call_contract_function(
                self.contract.functions.supportsInterface(self.DIAMOND_LOUPE_INTERFACE_ID)
            )
            
            # Try calling facets() function directly as fallback
            facets_result = None
            try:
                facets_result = await self.w3.async_call_contract_function(
                    self.contract.functions.facets()
                )
            except Exception:
                pass
            
            # Check if either interface detection or facets() call succeeded
            if (supports_loupe.success and supports_loupe.result) or (facets_result and facets_result.success):
                # Get facet information
                facet_addresses = []
                
                if facets_result and facets_result.success:
                    facets = facets_result.result
                    facet_addresses = [facet[0] for facet in facets]  # Extract addresses
                else:
                    # Try facetAddresses() as alternative
                    try:
                        addresses_result = await self.w3.async_call_contract_function(
                            self.contract.functions.facetAddresses()
                        )
                        if addresses_result.success:
                            facet_addresses = addresses_result.result
                    except Exception:
                        pass
                
                # Check for diamondCut capability
                has_diamond_cut = False
                try:
                    supports_cut = await self.w3.async_call_contract_function(
                        self.contract.functions.supportsInterface(self.DIAMOND_CUT_INTERFACE_ID)
                    )
                    has_diamond_cut = supports_cut.success and supports_cut.result
                except Exception:
                    pass
                
                return ProxyInfo(
                    is_proxy=True,
                    proxy_standard=ProxyStandard.EIP_2535_DIAMOND,
                    facet_addresses=[EthereumAddress.validate(addr) for addr in facet_addresses],
                    is_upgradeable=has_diamond_cut
                )
                
        except Exception:
            pass
        
        return None
    
    async def _check_function_based_proxies(self) -> Optional[ProxyInfo]:
        """Fallback detection via function signature probing."""
        try:
            # Try common proxy functions
            functions_found = []
            
            # Check implementation()
            try:
                impl_result = await self.w3.async_call_contract_function(
                    self.contract.functions.implementation()
                )
                if impl_result.success and impl_result.result:
                    functions_found.append("implementation")
                    return ProxyInfo(
                        is_proxy=True,
                        proxy_standard=ProxyStandard.CUSTOM_PROXY,
                        implementation_address=EthereumAddress.validate(impl_result.result),
                        is_upgradeable=True
                    )
            except Exception:
                pass
            
            # Check admin()
            try:
                admin_result = await self.w3.async_call_contract_function(
                    self.contract.functions.admin()
                )
                if admin_result.success:
                    functions_found.append("admin")
            except Exception:
                pass
            
            # Check beacon()
            try:
                beacon_result = await self.w3.async_call_contract_function(
                    self.contract.functions.beacon()
                )
                if beacon_result.success:
                    functions_found.append("beacon")
                    return ProxyInfo(
                        is_proxy=True,
                        proxy_standard=ProxyStandard.BEACON_PROXY,
                        beacon_address=EthereumAddress.validate(beacon_result.result),
                        is_upgradeable=True
                    )
            except Exception:
                pass
            
            # If we found proxy-like functions but couldn't classify, it's a custom proxy
            if functions_found:
                return ProxyInfo(
                    is_proxy=True,
                    proxy_standard=ProxyStandard.CUSTOM_PROXY,
                    is_upgradeable=True
                )
                
        except Exception:
            pass
        
        return None