"""
Vercel Blob database implementation for the NFT Inspector API.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
import asyncio
import vercel_blob

from src.nft_inspector.models import TokenInfo, NFTInspectionResult
from .base import DatabaseManagerInterface
from ..models import LeaderboardEntry

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
            # Use head to check if blob exists
            blob_info = await asyncio.to_thread(vercel_blob.head, path)
            if not blob_info:
                return None
                
            # Use the blob URL to fetch content
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(blob_info['url'])
                if response.status_code == 200:
                    return json.loads(response.text)
                return None
        except Exception as e:
            logger.debug(f"Blob not found or error reading {path}: {e}")
            return None
    
    async def _put_blob_json(self, path: str, data: Dict[str, Any]) -> bool:
        """Store JSON data as blob."""
        try:
            json_content = json.dumps(data, indent=2)
            # Base options for all JSON writes
            options = {
                'content_type': 'application/json',
                # Keep deterministic keys by default (no random suffix)
                'add_random_suffix': False,
            }
            # Apply overwrite and cache headers only for stats/leaderboard blobs
            if path.startswith("leaderboard/") or path.startswith("stats/"):
                options['allow_overwrite'] = True
                options['cache_control_max_age'] = 60

            response = await asyncio.to_thread(
                vercel_blob.put, 
                path, 
                json_content.encode('utf-8'),
                options
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
                "token_info": token_info.model_dump(mode='json', exclude_defaults=True),
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
    
    async def get_nft_analysis(self, chain_id: int, contract_address: str, token_id: int) -> Optional[NFTInspectionResult]:
        """
        Retrieve NFT analysis from blob storage.
        
        Args:
            chain_id: Blockchain ID
            contract_address: Contract address
            token_id: Token ID
            
        Returns:
            NFTInspectionResult if found (with guaranteed core fields), None otherwise
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
            
            return NFTInspectionResult.model_validate(token_info_data)
            
        except Exception as e:
            logger.error(f"Failed to retrieve NFT analysis: {e}")
            raise RuntimeError(f"Failed to retrieve analysis: {e}")
    
    async def _update_leaderboards(self, chain_id: int, token_info: TokenInfo, score: float):
        """Update global and chain-specific leaderboards using LeaderboardEntry."""
        try:
            # Extract individual scores from trust analysis
            permanence_score = token_info.trust_analysis.permanence.overall_score
            trustlessness_score = token_info.trust_analysis.trustlessness.overall_score
            # Extract collection name using consistent logic
            collection_name = self.extract_collection_name(token_info)
            
            now_iso = datetime.now(timezone.utc).isoformat()
            item = LeaderboardEntry(
                chain_id=chain_id,
                contract_address=token_info.contract_address.lower(),
                token_id=token_info.token_id,
                collection_name=collection_name,
                score=float(score),
                permanence_score=permanence_score,
                trustlessness_score=trustlessness_score,
                stored_at=now_iso,
            )

            # Update global leaderboard
            await self._update_single_leaderboard("global", None, item)

            # Update chain-specific leaderboard
            await self._update_single_leaderboard("chain", chain_id, item)
            
        except Exception as e:
            logger.error(f"Failed to update leaderboards: {e}")
    
    async def _update_single_leaderboard(self, scope: str, chain_id: Optional[int], item: LeaderboardEntry):
        """Update a single leaderboard with retry logic using a typed item."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                leaderboard_path = self._get_leaderboard_path(scope, chain_id)
                
                # Get current leaderboard
                leaderboard_data = await self._get_blob_json(leaderboard_path) or {"entries": []}
                entries = leaderboard_data.get("entries", [])
                
                # Remove existing entry for same contract/token
                def _matches(e: Dict[str, Any]) -> bool:
                    try:
                        return (
                            int(e.get("chain_id", -1)) == item.chain_id and
                            str(e.get("contract_address", "")).lower() == item.contract_address.lower() and
                            int(e.get("token_id", -1)) == item.token_id
                        )
                    except Exception:
                        return False

                entries = [e for e in entries if not _matches(e)]

                # Append validated item dump
                entries.append(item.model_dump(mode='json', exclude_defaults=True))
                
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
    
    # Tuple-based leaderboard removed; use get_leaderboard_items

    async def get_leaderboard_items(
        self,
        scope: str = "global",
        chain_id: Optional[int] = None,
        start: int = 0,
        end: int = -1,
        reverse: bool = True
    ) -> List[LeaderboardEntry]:
        """Return lightweight leaderboard items from stored leaderboard JSON."""
        try:
            if not self.initialized:
                raise RuntimeError("Database not initialized")

            leaderboard_path = self._get_leaderboard_path(scope, chain_id)
            leaderboard_data = await self._get_blob_json(leaderboard_path)
            if not leaderboard_data:
                return []

            entries = leaderboard_data.get("entries", [])

            # Ensure sort order if requested
            entries.sort(key=lambda x: x.get("score", 0), reverse=reverse)

            # Apply slicing like start/end
            if end == -1:
                sliced = entries[start:]
            else:
                sliced = entries[start:end+1]

            results: List[LeaderboardEntry] = []
            for entry in sliced:
                try:
                    # Load via Pydantic for validation/coercion
                    item = LeaderboardEntry.model_validate(entry)
                    results.append(item)
                except Exception:
                    continue

            return results
        except Exception as e:
            logger.error(f"Failed to get lightweight leaderboard: {e}")
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
                            token_info_data = token_info.model_dump(mode='json', exclude_defaults=True)
                            
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
    
    async def find_existing_token_id(self, chain_id: int, contract_address: str) -> Optional[int]:
        """Return a token id for the contract if one exists in storage.

        Strategy:
        1) Check chain leaderboard entries for a matching contract and return its token_id
        2) Fallback: list blobs and filter by nft/{chain}/{checksum_address}/ prefix, parse filename
        """
        try:
            if not self.initialized:
                raise RuntimeError("Database not initialized")

            from web3 import Web3
            from urllib.parse import urlparse

            checksum_address = Web3.to_checksum_address(contract_address)

            # 1) Try chain-specific leaderboard
            try:
                leaderboard_path = self._get_leaderboard_path("chain", chain_id)
                leaderboard = await self._get_blob_json(leaderboard_path) or {}
                for entry in leaderboard.get("entries", []):
                    # Prefer explicit fields if present
                    entry_addr = (entry.get("contract_address") or "").lower()
                    if entry_addr == checksum_address.lower():
                        token_id_val = entry.get("token_id")
                        if isinstance(token_id_val, int):
                            return token_id_val
                        # Fallback: parse from nft_key if present
                        nft_key = entry.get("nft_key") or ""
                        parts = nft_key.split(":")
                        if len(parts) >= 4 and parts[2].lower() == checksum_address.lower():
                            try:
                                return int(parts[3])
                            except ValueError:
                                pass
            except Exception:
                # Ignore leaderboard errors and fallback to listing
                pass

            # 2) Fallback to listing blobs and filtering by prefix
            prefix = f"nft/{chain_id}/{checksum_address}/"

            def extract_path(blob_item: Dict[str, Any]) -> Optional[str]:
                path = blob_item.get("pathname") or blob_item.get("key") or blob_item.get("path")
                if not path:
                    url = blob_item.get("url")
                    if url:
                        return urlparse(url).path.lstrip("/")
                return path

            blobs = None
            try:
                # Try with prefix support if available
                blobs = await asyncio.to_thread(vercel_blob.list, {"prefix": prefix, "limit": "1000"})
            except Exception:
                try:
                    # Without prefix param, list a larger set and filter client-side
                    blobs = await asyncio.to_thread(vercel_blob.list, {"limit": "1000"})
                except Exception:
                    blobs = []

            # Some SDKs return {"blobs": [...]}
            if isinstance(blobs, dict) and "blobs" in blobs:
                blobs_iter = blobs.get("blobs") or []
            else:
                blobs_iter = blobs or []

            for item in blobs_iter:
                try:
                    path = extract_path(item) or ""
                    if not path.startswith(prefix):
                        continue
                    filename = path.rsplit("/", 1)[-1]
                    if not filename.endswith(".json"):
                        continue
                    token_str = filename[:-5]
                    return int(token_str)
                except Exception:
                    continue

            return None

        except Exception as e:
            logger.error(f"Failed to find contract tokens: {e}")
            return None
    
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