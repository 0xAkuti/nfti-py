from typing import Dict, Any
from .types import (
    Interface, ComplianceReport, ERC721ComplianceResult, ERC2981ComplianceResult, 
    ERC4907ComplianceResult, ComplianceStatus, EthereumAddress
)
from .chains.web3_wrapper import EnhancedWeb3


class NFTComplianceChecker:
    """Analyzes NFT contract compliance with supported standards using batch calls."""
    
    # Standard test sale price for royalty calculations (1 ETH in wei)
    TEST_SALE_PRICE = 10**18
    
    def __init__(self, w3: EnhancedWeb3, supported_interfaces: Dict[Interface, bool]):
        """Initialize compliance checker with Web3 instance and supported interfaces."""
        self.w3 = w3
        self.supported_interfaces = supported_interfaces

    async def check_compliance(self, contract_address: str, token_id: int) -> ComplianceReport:
        """
        Perform comprehensive compliance checks for supported standards.
        
        Args:
            contract_address: The NFT contract address
            token_id: The token ID to check
            
        Returns:
            ComplianceReport with detailed results for each standard
        """
        contract_address = self.w3.to_checksum_address(contract_address)
        
        report = ComplianceReport()
        overall_status = ComplianceStatus.PASS
        
        # Check ERC721 compliance if supported
        if self.supported_interfaces.get(Interface.ERC721, False):
            report.erc721 = await self._check_erc721_compliance(contract_address, token_id)
            if report.erc721 and self._has_failures(report.erc721):
                overall_status = ComplianceStatus.FAIL
        
        # Check ERC2981 royalty compliance if supported
        if self.supported_interfaces.get(Interface.ERC2981, False):
            report.erc2981 = await self._check_erc2981_compliance(contract_address, token_id)
            if report.erc2981 and self._has_failures(report.erc2981):
                overall_status = ComplianceStatus.FAIL
        
        # Check ERC4907 rental compliance if supported
        if self.supported_interfaces.get(Interface.ERC4907, False):
            report.erc4907 = await self._check_erc4907_compliance(contract_address, token_id)
            if report.erc4907 and self._has_failures(report.erc4907):
                overall_status = ComplianceStatus.FAIL
        
        report.overall_status = overall_status
        return report

    async def _check_erc721_compliance(self, contract_address: str, token_id: int) -> ERC721ComplianceResult:
        """Check ERC721 standard compliance using batch calls."""
        
        # Prepare function calls
        function_calls = []
        abi_functions = []
        
        # Basic ERC721 functions
        name_abi = {"inputs": [], "name": "name", "outputs": [{"type": "string"}], "stateMutability": "view", "type": "function"}
        symbol_abi = {"inputs": [], "name": "symbol", "outputs": [{"type": "string"}], "stateMutability": "view", "type": "function"}
        owner_of_abi = {"inputs": [{"type": "uint256", "name": "tokenId"}], "name": "ownerOf", "outputs": [{"type": "address"}], "stateMutability": "view", "type": "function"}
        
        contract = self.w3.eth.contract(address=contract_address, abi=[name_abi, symbol_abi, owner_of_abi])
        
        function_calls.extend([
            contract.functions.name(),
            contract.functions.symbol(),
            contract.functions.ownerOf(token_id)
        ])
        abi_functions.extend(['name', 'symbol', 'ownerOf'])
        
        # Add totalSupply if enumerable is supported
        if self.supported_interfaces.get(Interface.ERC721_ENUMERABLE, False):
            total_supply_abi = {"inputs": [], "name": "totalSupply", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"}
            contract_with_total = self.w3.eth.contract(address=contract_address, abi=[total_supply_abi])
            function_calls.append(contract_with_total.functions.totalSupply())
            abi_functions.append('totalSupply')
        
        # Execute batch call
        results = await self.w3.async_batch_call_contract_functions(function_calls)
        
        # Process results
        result = ERC721ComplianceResult()
        
        for func_name, rpc_result in zip(abi_functions, results):
            if func_name == 'name':
                if rpc_result.success and rpc_result.result:
                    result.name = str(rpc_result.result)
                    result.name_status = ComplianceStatus.PASS if result.name.strip() else ComplianceStatus.FAIL
                else:
                    result.name_status = ComplianceStatus.ERROR
            
            elif func_name == 'symbol':
                if rpc_result.success and rpc_result.result:
                    result.symbol = str(rpc_result.result)
                    result.symbol_status = ComplianceStatus.PASS if result.symbol.strip() else ComplianceStatus.FAIL
                else:
                    result.symbol_status = ComplianceStatus.ERROR
            
            elif func_name == 'ownerOf':
                if rpc_result.success and rpc_result.result:
                    owner_address = str(rpc_result.result)
                    # Check if owner is not zero address
                    is_valid_owner = owner_address != "0x0000000000000000000000000000000000000000"
                    if is_valid_owner:
                        result.owner_of = EthereumAddress.validate(owner_address)
                        result.owner_of_status = ComplianceStatus.PASS
                    else:
                        result.owner_of_status = ComplianceStatus.FAIL
                else:
                    result.owner_of_status = ComplianceStatus.ERROR
            
            elif func_name == 'totalSupply':
                if rpc_result.success and rpc_result.result is not None:
                    result.total_supply = int(rpc_result.result)
                    result.total_supply_status = ComplianceStatus.PASS if result.total_supply > 0 else ComplianceStatus.FAIL
                else:
                    result.total_supply_status = ComplianceStatus.ERROR
        
        return result

    async def _check_erc2981_compliance(self, contract_address: str, token_id: int) -> ERC2981ComplianceResult:
        """Check ERC2981 royalty standard compliance."""
        
        royalty_info_abi = {
            "inputs": [{"type": "uint256", "name": "tokenId"}, {"type": "uint256", "name": "salePrice"}],
            "name": "royaltyInfo",
            "outputs": [{"type": "address", "name": "receiver"}, {"type": "uint256", "name": "royaltyAmount"}],
            "stateMutability": "view",
            "type": "function"
        }
        
        contract = self.w3.eth.contract(address=contract_address, abi=[royalty_info_abi])
        function_calls = [contract.functions.royaltyInfo(token_id, self.TEST_SALE_PRICE)]
        
        results = await self.w3.async_batch_call_contract_functions(function_calls)
        rpc_result = results[0]
        
        result = ERC2981ComplianceResult()
        result.sale_price_tested = self.TEST_SALE_PRICE
        
        if rpc_result.success and rpc_result.result:
            recipient, royalty_amount = rpc_result.result
            recipient_address = str(recipient)
            result.royalty_amount = int(royalty_amount)
            
            # Validate recipient is not zero address
            is_valid_recipient = recipient_address != "0x0000000000000000000000000000000000000000"
            if is_valid_recipient:
                result.recipient = EthereumAddress.validate(recipient_address)
                result.recipient_status = ComplianceStatus.PASS
            else:
                result.recipient_status = ComplianceStatus.FAIL
            
            # Validate royalty amount is reasonable (≤ sale price and ≤ 50%)
            is_valid_amount = (
                result.royalty_amount <= self.TEST_SALE_PRICE and 
                result.royalty_amount <= (self.TEST_SALE_PRICE // 2)  # Max 50%
            )
            result.amount_status = ComplianceStatus.PASS if is_valid_amount else ComplianceStatus.FAIL
        else:
            result.recipient_status = ComplianceStatus.ERROR
            result.amount_status = ComplianceStatus.ERROR
        
        return result

    async def _check_erc4907_compliance(self, contract_address: str, token_id: int) -> ERC4907ComplianceResult:
        """Check ERC4907 rental extension compliance."""
        
        user_of_abi = {
            "inputs": [{"type": "uint256", "name": "tokenId"}],
            "name": "userOf",
            "outputs": [{"type": "address"}],
            "stateMutability": "view",
            "type": "function"
        }
        
        user_expires_abi = {
            "inputs": [{"type": "uint256", "name": "tokenId"}],
            "name": "userExpires",
            "outputs": [{"type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        }
        
        contract = self.w3.eth.contract(address=contract_address, abi=[user_of_abi, user_expires_abi])
        function_calls = [
            contract.functions.userOf(token_id),
            contract.functions.userExpires(token_id)
        ]
        
        results = await self.w3.async_batch_call_contract_functions(function_calls)
        user_result, expires_result = results
        
        result = ERC4907ComplianceResult()
        
        # Process userOf result
        if user_result.success and user_result.result is not None:
            user_address = str(user_result.result)
            # Zero address is valid (means no user set)
            if user_address != "0x0000000000000000000000000000000000000000":
                result.user_of = EthereumAddress.validate(user_address)
            else:
                result.user_of = None
            result.user_status = ComplianceStatus.PASS
        else:
            result.user_status = ComplianceStatus.ERROR
        
        # Process userExpires result
        if expires_result.success and expires_result.result is not None:
            result.user_expires = int(expires_result.result)
            result.expires_status = ComplianceStatus.PASS
            
            # Determine if rental is currently active
            if result.user_of:  # user_of is now EthereumAddress or None
                current_time = self.w3.eth.get_block('latest')['timestamp']
                result.rental_active = result.user_expires > current_time
            else:
                result.rental_active = False
        else:
            result.expires_status = ComplianceStatus.ERROR
        
        return result

    def _has_failures(self, compliance_result: Any) -> bool:
        """Check if a compliance result contains any failures."""
        if hasattr(compliance_result, '__dict__'):
            for attr_name, attr_value in compliance_result.__dict__.items():
                if attr_name.endswith('_status') and attr_value == ComplianceStatus.FAIL:
                    return True
        return False