"""
Vercel Blob database implementation for the NFT Inspector API.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
import asyncio
import vercel_blob

from src.nft_inspector.models import TokenInfo
from .base import DatabaseManagerInterface

logger = logging.getLogger(__name__)


class BlobManager(DatabaseManagerInterface):
    """Vercel Blob database manager implementation."""
    
    def __init__(self, blob_read_write_token: str):
        self.blob_read_write_token = blob_read_write_token
        self.initialized = False
    
    async def initialize(self):
        """Initialize Blob storage connection."""
        if not self.blob_read_write_token:
            raise ValueError("BLOB_READ_WRITE_TOKEN not configured")
        
        # Set the environment variable for vercel_blob
        import os
        os.environ['BLOB_READ_WRITE_TOKEN'] = self.blob_read_write_token
        
        # Test connection by trying to list blobs
        try:
            await asyncio.to_thread(vercel_blob.list, {'limit': '1'})
            logger.info("Connected to Vercel Blob storage")
            self.initialized = True
            
            # Initialize global stats if needed
            await self._ensure_global_stats()
            
        except Exception as e:
            raise ValueError(f"Failed to connect to Vercel Blob: {e}")
    
    async def close(self):
        """Close Blob storage connection (no-op for blob storage)."""
        self.initialized = False
    
    def _get_nft_path(self, chain_id: int, contract_address: str, token_id: int) -> str:
        """Generate blob path for NFT data."""
        from web3 import Web3
        checksum_address = Web3.to_checksum_address(contract_address)
        return f"nft/{chain_id}/{checksum_address}/{token_id}.json"
    
    def _get_leaderboard_path(self, scope: str = "global", chain_id: Optional[int] = None) -> str:
        """Generate blob path for leaderboard."""
        if scope == "global":
            return "leaderboard/global.json"
        elif scope == "chain" and chain_id:
            return f"leaderboard/chain-{chain_id}.json"
        else:
            raise ValueError("Invalid leaderboard scope")
    
    def _get_stats_path(self) -> str:
        """Generate blob path for global stats."""
        return "stats/global.json"
    
    async def _get_blob_json(self, path: str) -> Optional[Dict[str, Any]]:
        """Get and parse JSON blob, returns None if not found."""
        try:
            # Use download_file to get blob content
            content = await asyncio.to_thread(vercel_blob.download_file, path)
            if content:
                return json.loads(content)
            return None
        except Exception as e:
            logger.debug(f"Blob not found or error reading {path}: {e}")
            return None
    
    async def _put_blob_json(self, path: str, data: Dict[str, Any]) -> bool:
        """Store JSON data as blob."""
        try:
            json_content = json.dumps(data, indent=2)
            response = await asyncio.to_thread(
                vercel_blob.put, 
                path, 
                json_content.encode('utf-8'),
                {'content_type': 'application/json'}
            )
            return response is not None
        except Exception as e:
            logger.error(f"Failed to store blob {path}: {e}")
            return False
    
    async def store_nft_analysis(self, token_info: TokenInfo) -> bool:
        """
        Store NFT analysis result in blob storage.
        
        Args:
            token_info: Complete token information including trust analysis
            
        Returns:
            True if stored successfully
        """
        try:
            if not self.initialized:
                raise RuntimeError("Database not initialized")
            
            chain_id = token_info.trust_analysis.chain_trust.chain_id if token_info.trust_analysis else 1
            nft_path = self._get_nft_path(chain_id, token_info.contract_address, token_info.token_id)
            
            # Prepare storage data with metadata
            storage_data = {
                "token_info": token_info.model_dump(mode='json'),
                "stored_at": datetime.now(timezone.utc).isoformat(),
                "analysis_version": token_info.trust_analysis.analysis_version if token_info.trust_analysis else "1.0",
                "chain_id": chain_id,
                "contract_address": token_info.contract_address.lower(),
                "token_id": token_info.token_id
            }
            
            # Store NFT data
            success = await self._put_blob_json(nft_path, storage_data)
            if not success:
                return False
            
            # Update leaderboards if trust analysis exists
            if token_info.trust_analysis:
                score = token_info.trust_analysis.overall_score
                await self._update_leaderboards(chain_id, token_info, score)
            
            # Update global statistics
            await self._update_global_stats_blob(token_info)
            
            logger.info(f"Stored NFT analysis: {nft_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store NFT analysis: {e}")
            raise RuntimeError(f"Failed to store analysis: {e}")
    
    async def get_nft_analysis(self, chain_id: int, contract_address: str, token_id: int) -> Optional[TokenInfo]:
        """
        Retrieve NFT analysis from blob storage.
        
        Args:
            chain_id: Blockchain ID
            contract_address: Contract address
            token_id: Token ID
            
        Returns:
            TokenInfo if found, None otherwise
        """
        try:
            if not self.initialized:
                raise RuntimeError("Database not initialized")
            
            nft_path = self._get_nft_path(chain_id, contract_address, token_id)
            data = await self._get_blob_json(nft_path)
            
            if not data:
                return None
            
            # Parse stored JSON data
            token_info_data = data.get("token_info")
            if not token_info_data:
                return None
            
            return TokenInfo.model_validate(token_info_data)
            
        except Exception as e:
            logger.error(f"Failed to retrieve NFT analysis: {e}")
            raise RuntimeError(f"Failed to retrieve analysis: {e}")
    
    async def _update_leaderboards(self, chain_id: int, token_info: TokenInfo, score: float):
        """Update global and chain-specific leaderboards."""
        try:
            # Create NFT key for consistency with Redis format
            from web3 import Web3
            checksum_address = Web3.to_checksum_address(token_info.contract_address)
            nft_key = f"nft:{chain_id}:{checksum_address}:{token_info.token_id}"
            
            # Update global leaderboard
            await self._update_single_leaderboard("global", None, nft_key, score, {
                "chain_id": chain_id,
                "contract_address": token_info.contract_address.lower(),
                "token_id": token_info.token_id,
                "stored_at": datetime.now(timezone.utc).isoformat()
            })
            
            # Update chain-specific leaderboard  
            await self._update_single_leaderboard("chain", chain_id, nft_key, score, {
                "chain_id": chain_id,
                "contract_address": token_info.contract_address.lower(),
                "token_id": token_info.token_id,
                "stored_at": datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            logger.error(f"Failed to update leaderboards: {e}")
    
    async def _update_single_leaderboard(self, scope: str, chain_id: Optional[int], nft_key: str, score: float, metadata: Dict[str, Any]):
        """Update a single leaderboard with retry logic."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                leaderboard_path = self._get_leaderboard_path(scope, chain_id)
                
                # Get current leaderboard
                leaderboard_data = await self._get_blob_json(leaderboard_path) or {"entries": []}
                entries = leaderboard_data.get("entries", [])
                
                # Remove existing entry if it exists
                entries = [entry for entry in entries if entry.get("nft_key") != nft_key]
                
                # Add new entry
                entries.append({
                    "nft_key": nft_key,
                    "score": score,
                    **metadata
                })
                
                # Sort by score (descending)
                entries.sort(key=lambda x: x.get("score", 0), reverse=True)
                
                # Keep only top 10000 entries to prevent unlimited growth
                entries = entries[:10000]
                
                # Update leaderboard
                leaderboard_data["entries"] = entries
                leaderboard_data["last_updated"] = datetime.now(timezone.utc).isoformat()
                leaderboard_data["total_entries"] = len(entries)
                
                # Store updated leaderboard
                success = await self._put_blob_json(leaderboard_path, leaderboard_data)
                if success:
                    break
                    
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                await asyncio.sleep(0.1 * (attempt + 1))  # Exponential backoff
    
    async def get_leaderboard(
        self,
        scope: str = "global",
        chain_id: Optional[int] = None,
        start: int = 0,
        end: int = -1,
        reverse: bool = True
    ) -> List[Tuple[str, float]]:
        """
        Get leaderboard entries.
        
        Args:
            scope: Leaderboard scope ("global", "chain")
            chain_id: Chain ID for chain-specific leaderboard
            start: Start index
            end: End index (-1 for all)
            reverse: True for highest scores first
            
        Returns:
            List of (nft_key, score) tuples
        """
        try:
            if not self.initialized:
                raise RuntimeError("Database not initialized")
            
            leaderboard_path = self._get_leaderboard_path(scope, chain_id)
            leaderboard_data = await self._get_blob_json(leaderboard_path)
            
            if not leaderboard_data:
                return []
            
            entries = leaderboard_data.get("entries", [])
            
            # Sort if needed (should already be sorted, but ensure)
            entries.sort(key=lambda x: x.get("score", 0), reverse=reverse)
            
            # Apply slicing
            if end == -1:
                entries = entries[start:]
            else:
                entries = entries[start:end+1]
            
            # Convert to expected format
            return [(entry.get("nft_key", ""), entry.get("score", 0.0)) for entry in entries]
            
        except Exception as e:
            logger.error(f"Failed to get leaderboard: {e}")
            raise RuntimeError(f"Failed to get leaderboard: {e}")
    
    async def get_leaderboard_with_filters(
        self,
        filters: Dict[str, Any],
        start: int = 0,
        count: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get filtered leaderboard entries with full NFT data.
        
        Args:
            filters: Filter parameters
            start: Start index
            count: Number of entries to return
            
        Returns:
            List of NFT data dictionaries with scores
        """
        try:
            if not self.initialized:
                raise RuntimeError("Database not initialized")
            
            # Determine leaderboard scope
            scope = "global"
            chain_id = filters.get("chain_id")
            if chain_id:
                scope = "chain"
            
            # Get leaderboard entries
            leaderboard_entries = await self.get_leaderboard(
                scope=scope,
                chain_id=chain_id,
                start=0,  # Get more than needed for filtering
                end=-1
            )
            
            # Get full NFT data for each entry and apply filters
            results = []
            processed = 0
            for nft_key, score in leaderboard_entries:
                try:
                    # Parse nft_key to get path components
                    parts = nft_key.split(':')
                    if len(parts) >= 4:
                        entry_chain_id = int(parts[1])
                        entry_contract = parts[2]
                        entry_token_id = int(parts[3])
                        
                        # Get full NFT data
                        token_info = await self.get_nft_analysis(entry_chain_id, entry_contract, entry_token_id)
                        if token_info:
                            token_info_data = token_info.model_dump(mode='json')
                            
                            # Apply filters
                            if self._matches_filters(token_info_data, filters):
                                if processed >= start and len(results) < count:
                                    entry = {
                                        "nft_key": nft_key,
                                        "score": score,
                                        "chain_id": entry_chain_id,
                                        "contract_address": entry_contract.lower(),
                                        "token_id": entry_token_id,
                                        "stored_at": datetime.now(timezone.utc).isoformat(),
                                        "token_info": token_info_data
                                    }
                                    results.append(entry)
                                processed += 1
                                
                                if len(results) >= count:
                                    break
                            
                except Exception as e:
                    logger.warning(f"Failed to process leaderboard entry {nft_key}: {e}")
                    continue
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get filtered leaderboard: {e}")
            raise RuntimeError(f"Failed to get leaderboard: {e}")
    
    def _matches_filters(self, token_info_data: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Check if token info matches the provided filters."""
        try:
            # Trust level filter
            trust_level = filters.get("trust_level")
            if trust_level:
                analysis = token_info_data.get("trust_analysis", {})
                if analysis.get("overall_level", "").lower() != trust_level:
                    return False
            
            # Score range filters
            min_score = filters.get("min_score")
            max_score = filters.get("max_score")
            if min_score is not None or max_score is not None:
                analysis = token_info_data.get("trust_analysis", {})
                score = analysis.get("overall_score", 0)
                if min_score is not None and score < min_score:
                    return False
                if max_score is not None and score > max_score:
                    return False
            
            # Contract address filter
            contract_filter = filters.get("contract_address")
            if contract_filter:
                contract_address = token_info_data.get("contract_address", "").lower()
                if contract_address != contract_filter:
                    return False
            
            # Collection name filter (partial match)
            collection_name_filter = filters.get("collection_name")
            if collection_name_filter:
                metadata = token_info_data.get("contract_metadata", {}) or token_info_data.get("metadata", {})
                collection_name = metadata.get("name", "").lower()
                if collection_name_filter.lower() not in collection_name:
                    return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Error applying filters: {e}")
            return False
    
    async def _ensure_global_stats(self):
        """Initialize global stats if they don't exist."""
        stats_path = self._get_stats_path()
        stats = await self._get_blob_json(stats_path)
        
        if not stats:
            initial_stats = {
                "total_analyses": 0,
                "total_score": 0.0,
                "average_score": 0.0,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            await self._put_blob_json(stats_path, initial_stats)
    
    async def _update_global_stats_blob(self, token_info: TokenInfo):
        """Update global statistics."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                stats_path = self._get_stats_path()
                
                # Get current stats
                stats_data = await self._get_blob_json(stats_path) or {
                    "total_analyses": 0,
                    "total_score": 0.0,
                    "average_score": 0.0
                }
                
                # Calculate new statistics
                current_analyses = stats_data.get("total_analyses", 0)
                current_total_score = stats_data.get("total_score", 0.0)
                
                new_analyses = current_analyses + 1
                score = token_info.trust_analysis.overall_score if token_info.trust_analysis else 0
                new_total_score = current_total_score + score
                new_average = new_total_score / new_analyses if new_analyses > 0 else 0
                
                # Update stats
                updated_stats = {
                    "total_analyses": new_analyses,
                    "total_score": new_total_score,
                    "average_score": round(new_average, 2),
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }
                
                # Store updated stats
                success = await self._put_blob_json(stats_path, updated_stats)
                if success:
                    break
                    
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to update global stats: {e}")
                    raise e
                await asyncio.sleep(0.1 * (attempt + 1))  # Exponential backoff
    
    async def find_contract_tokens(self, chain_id: int, contract_address: str) -> List[str]:
        """Find any analyzed tokens for a contract (blob backend specific method)."""
        try:
            # For blob storage, we need to list blobs and filter by pattern
            # This is a simplified implementation - in a real system you might 
            # maintain an index of contracts
            from web3 import Web3
            checksum_address = Web3.to_checksum_address(contract_address)
            prefix = f"nft/{chain_id}/{checksum_address}/"
            
            # List blobs with the contract prefix
            # This is a limitation of current vercel_blob SDK - it doesn't support prefix filtering
            # For now, we'll return empty list and let the analysis route handle it gracefully
            logger.warning(f"Contract token search not fully implemented for blob backend: {prefix}")
            return []
            
        except Exception as e:
            logger.error(f"Failed to find contract tokens: {e}")
            return []
    
    async def get_global_stats(self) -> Dict[str, Any]:
        """Get global statistics."""
        try:
            if not self.initialized:
                raise RuntimeError("Database not initialized")
            
            stats_path = self._get_stats_path()
            stats_data = await self._get_blob_json(stats_path) or {
                "total_analyses": 0,
                "average_score": 0.0,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            
            return {
                "total_analyses": stats_data.get("total_analyses", 0),
                "average_score": stats_data.get("average_score", 0.0),
                "last_updated": stats_data.get("last_updated", "")
            }
            
        except Exception as e:
            logger.error(f"Failed to get global stats: {e}")
            raise RuntimeError(f"Failed to get statistics: {e}")