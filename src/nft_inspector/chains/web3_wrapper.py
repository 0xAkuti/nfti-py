import asyncio
from typing import List, Any, Optional
from web3 import Web3
from web3.contract.contract import ContractFunction
from web3.exceptions import (
    Web3RPCError, ContractLogicError, ContractCustomError, 
    ContractPanicError, TransactionNotFound, RequestTimedOut,
    MethodUnavailable, BadFunctionCallOutput, TooManyRequests
)

from ..types import RpcResult, RpcErrorType


class EnhancedWeb3:
    """Web3 wrapper with structured error handling for RPC calls"""
    
    def __init__(self, web3_instance: Web3):
        self.w3 = web3_instance
    
    def _handle_exception(self, e: Exception) -> tuple[RpcErrorType, str, Optional[dict]]:
        """Categorize exceptions and extract error details"""
        error_data = None
        
        if isinstance(e, ContractLogicError):
            error_msg = str(e)
            
            # Extract error data if available
            if hasattr(e, 'data') and e.data:
                error_data = {'raw_data': e.data}
            
            # Check if it's a function not found vs execution reverted
            if "execution reverted" in error_msg.lower():
                if "function selector was not recognized" in error_msg.lower() or \
                   "function not found" in error_msg.lower():
                    return RpcErrorType.FUNCTION_NOT_FOUND, f"Function not found: {error_msg}", error_data
                else:
                    return RpcErrorType.EXECUTION_REVERTED, f"Contract execution reverted: {error_msg}", error_data
            else:
                return RpcErrorType.EXECUTION_REVERTED, f"Contract logic error: {error_msg}", error_data
                
        elif isinstance(e, ContractCustomError):
            error_data = {'raw_data': getattr(e, 'data', None)}
            return RpcErrorType.CUSTOM_ERROR, f"Contract custom error: {str(e)}", error_data
            
        elif isinstance(e, ContractPanicError):
            error_data = {'raw_data': getattr(e, 'data', None)}
            return RpcErrorType.PANIC_ERROR, f"Contract panic error: {str(e)}", error_data
            
        elif isinstance(e, RequestTimedOut):
            return RpcErrorType.TIMEOUT, f"Request timed out: {str(e)}", None
            
        elif isinstance(e, MethodUnavailable):
            return RpcErrorType.RPC_ERROR, f"Method unavailable: {str(e)}", None
            
        elif isinstance(e, Web3RPCError):
            error_msg = str(e)            
            # Check if it indicates contract not found
            if "no code at address" in error_msg.lower():
                return RpcErrorType.CONTRACT_NOT_FOUND, f"Contract not found: {error_msg}", None
            else:
                return RpcErrorType.RPC_ERROR, f"RPC error: {error_msg}", None
                
        elif isinstance(e, BadFunctionCallOutput):
            if 'is contract deployed' in str(e).lower():
                return RpcErrorType.CONTRACT_NOT_FOUND, f"Contract not found: {str(e)}", None
            else:
                return RpcErrorType.RPC_ERROR, f"RPC error: {str(e)}", None
            
        elif isinstance(e, TransactionNotFound):
            return RpcErrorType.RPC_ERROR, f"Transaction not found: {str(e)}", None
            
        elif isinstance(e, TooManyRequests):
            return RpcErrorType.RPC_ERROR, f"Too many requests: {str(e)}", None
            
        else:
            error_msg = str(e)
            if "network" in error_msg.lower() or "connection" in error_msg.lower():
                return RpcErrorType.NETWORK_ERROR, f"Network error: {error_msg}", None
            else:
                return RpcErrorType.UNKNOWN_ERROR, f"Unknown error: {error_msg}", None
    
    def call_contract_function(
        self, 
        contract_function: ContractFunction
    ) -> RpcResult[Any]:
        """Call a contract function with structured error handling"""
        try:
            result = contract_function.call()
            return RpcResult.success_result(result)
            
        except Exception as e:
            error_type, error_message, error_data = self._handle_exception(e)
            return RpcResult.error_result(error_type, error_message, error_data)
    
    def batch_call_contract_functions(
        self, 
        contract_functions: List[ContractFunction]
    ) -> List[RpcResult[Any]]:
        """Batch call contract functions with individual error handling"""
        results = []
        
        try:
            with self.w3.batch_requests() as batch:
                # Add all function calls to batch
                for contract_function in contract_functions:
                    batch.add(contract_function)
                
                # Execute batch and get responses
                responses = batch.execute()
                
                # Process each response
                for response in responses:
                    # Check if response is an error
                    if isinstance(response, dict) and 'error' in response:
                        # Handle JSON-RPC error response
                        error_info = response['error']
                        error_message = error_info.get('message', 'Unknown RPC error')
                        error_code = error_info.get('code', None)
                        
                        # Categorize based on error code/message
                        if error_code == -32000:  # Execution reverted
                            if "no code at address" in error_message.lower():
                                error_type = RpcErrorType.CONTRACT_NOT_FOUND
                            else:
                                error_type = RpcErrorType.EXECUTION_REVERTED
                        else:
                            error_type = RpcErrorType.RPC_ERROR
                        
                        results.append(RpcResult.error_result(
                            error_type, 
                            error_message, 
                            {'error_code': error_code, 'rpc_error': error_info}
                        ))
                    else:
                        # Successful response
                        results.append(RpcResult.success_result(response))
                        
        except Exception as e:
            # If the entire batch fails, return error for all requests
            error_type, error_message, error_data = self._handle_exception(e)
            error_result = RpcResult.error_result(error_type, error_message, error_data)
            results = [error_result] * len(contract_functions)
        
        return results
    
    async def async_call_contract_function(
        self, 
        contract_function: ContractFunction
    ) -> RpcResult[Any]:
        """Async version of call_contract_function"""
        try:
            # Run the blocking call in a thread pool
            result = await asyncio.get_event_loop().run_in_executor(
                None, contract_function.call
            )
            return RpcResult.success_result(result)
            
        except Exception as e:
            error_type, error_message, error_data = self._handle_exception(e)
            return RpcResult.error_result(error_type, error_message, error_data)
    
    async def async_batch_call_contract_functions(
        self, 
        contract_functions: List[ContractFunction]
    ) -> List[RpcResult[Any]]:
        """Async version of batch_call_contract_functions using asyncio.gather for better performance"""
        try:
            # Use individual async calls with gather (recommended by web3.py docs for performance)
            tasks = [
                self.async_call_contract_function(contract_function)
                for contract_function in contract_functions
            ]
            return await asyncio.gather(*tasks)
                
        except Exception as e:
            error_type, error_message, error_data = self._handle_exception(e)
            error_result = RpcResult.error_result(error_type, error_message, error_data)
            return [error_result] * len(contract_functions)
    
    async def async_get_storage_at(self, address: str, slot: str) -> bytes:
        """Async version of eth.get_storage_at"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.w3.eth.get_storage_at, address, slot
        )
    
    async def async_get_code(self, address: str) -> bytes:
        """Async version of eth.get_code"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.w3.eth.get_code, address
        )
    
    @property
    def eth(self):
        """Access to eth module"""
        return self.w3.eth
    
    @property
    def provider(self):
        """Access to provider"""
        return self.w3.provider
    
    def is_connected(self) -> bool:
        """Check if Web3 is connected"""
        return self.w3.is_connected()
    
    def to_checksum_address(self, address: str) -> str:
        """Convert address to checksum format"""
        return self.w3.to_checksum_address(address)
    
    def is_address(self, address: str) -> bool:
        """Check if string is a valid address"""
        return self.w3.is_address(address)