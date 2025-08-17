import json
import httpx
from typing import Optional, List, Dict
from pathlib import Path
from web3 import Web3

from .chain_models import ChainInfo
from .web3_wrapper import EnhancedWeb3


class ChainProvider:
    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            # Default to data directory relative to this file
            self.data_dir = Path(__file__).parent.parent.parent.parent / "data"
        else:
            self.data_dir = Path(data_dir)
        
        self.chains: Dict[int, ChainInfo] = {}
        self._load_chains()
    
    def _load_chains(self):
        """Load chains from both chainlist_rpcs.json and custom_chains.json"""
        # Load main chainlist
        chainlist_file = self.data_dir / "chainlist_rpcs.json"
        if chainlist_file.exists():
            with open(chainlist_file, 'r') as f:
                chainlist = json.load(f)
                for chain_data in chainlist:
                    chain_info = ChainInfo.model_validate(chain_data)
                    self.chains[chain_info.chainId] = chain_info
        
        # Load custom chains (these can override chainlist entries)
        custom_file = self.data_dir / "custom_chains.json"
        if custom_file.exists():
            with open(custom_file, 'r') as f:
                custom_chains = json.load(f)
                for _, chain_data in custom_chains.items():
                    chain_info = ChainInfo.model_validate(chain_data)
                    self.chains[chain_info.chainId] = chain_info
    
    async def _test_rpc_endpoint(self, rpc_url: str) -> bool:
        """Test if RPC endpoint works by getting block number"""
        # Skip WebSocket URLs
        if rpc_url.startswith('wss://') or rpc_url.startswith('ws://'):
            return False
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(rpc_url, json={
                    "jsonrpc": "2.0",
                    "method": "eth_blockNumber",
                    "params": [],
                    "id": 1
                })
                if response.status_code == 200:
                    result = response.json()
                    return "result" in result and result["result"] is not None
                return False
        except Exception:
            return False
    
    def _extract_rpc_url(self, rpc_entry) -> str:
        """Extract URL from RPC entry (handles both string and object formats)"""
        if isinstance(rpc_entry, str):
            return rpc_entry
        elif isinstance(rpc_entry, dict) and "url" in rpc_entry:
            return rpc_entry["url"]
        elif hasattr(rpc_entry, 'url'):
            return rpc_entry.url
        else:
            return str(rpc_entry)  # Fallback
    
    async def get_working_rpc_url(self, chain_id: int) -> Optional[str]:
        """Get first working RPC URL for the given chain ID"""
        chain_info = self.get_chain_info(chain_id)
        if not chain_info or not chain_info.rpc:
            return None
        
        for rpc_entry in chain_info.rpc:
            rpc_url = self._extract_rpc_url(rpc_entry)
            if await self._test_rpc_endpoint(rpc_url):
                return rpc_url
        
        return None
    
    async def get_web3_connection(self, chain_id: int) -> Optional[Web3]:
        """Get a working Web3 connection for the given chain ID"""
        rpc_url = await self.get_working_rpc_url(chain_id)
        if rpc_url:
            return Web3(Web3.HTTPProvider(rpc_url))
        return None
    
    async def get_enhanced_web3_connection(self, chain_id: int) -> Optional[EnhancedWeb3]:
        """Get a working EnhancedWeb3 connection for the given chain ID"""
        rpc_url = await self.get_working_rpc_url(chain_id)
        if rpc_url:
            web3_instance = Web3(Web3.HTTPProvider(rpc_url))
            return EnhancedWeb3(web3_instance)
        return None
    
    def get_chain_info(self, chain_id: int) -> Optional[ChainInfo]:
        """Get chain information by chain ID"""
        return self.chains.get(chain_id)
    
    def list_chains(self) -> List[ChainInfo]:
        """Get list of all available chains"""
        return list(self.chains.values())
    
    def is_testnet(self, chain_id: int) -> bool:
        """Check if chain is a testnet"""
        chain_info = self.get_chain_info(chain_id)
        return chain_info.isTestnet if chain_info and chain_info.isTestnet is not None else False
    
    def get_chain_name(self, chain_id: int) -> Optional[str]:
        """Get chain name by chain ID"""
        chain_info = self.get_chain_info(chain_id)
        return chain_info.name if chain_info else None