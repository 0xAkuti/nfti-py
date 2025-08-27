"""
Redis database implementation for the NFT Inspector API.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
import redis.asyncio as redis

from src.nft_inspector.models import TokenInfo
from .base import DatabaseManagerInterface
from ..models import LeaderboardEntry

logger = logging.getLogger(__name__)


class RedisManager(DatabaseManagerInterface):
    """Redis database manager implementation."""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis = None
    
    async def initialize(self):
        """Initialize Redis connection."""
        if not self.redis_url:
            raise ValueError("REDIS_URL not configured")
        
        self.redis = redis.from_url(self.redis_url, encoding="utf-8", decode_responses=True)
        await self.redis.ping()
        logger.info("Connected to Redis")
        
        # Initialize basic stats if needed
        if not await self.redis.exists("stats:global"):
            await self.redis.hset("stats:global", mapping={
                "total_analyses": "0",
                "average_score": "0.0",
                "last_updated": datetime.now(timezone.utc).isoformat()
            })
    
    async def close(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
    
    
    def _get_nft_key(self, chain_id: int, contract_address: str, token_id: int) -> str:
        """Generate Redis key for NFT data."""
        # Use checksum address format for consistency with EthereumAddress type
        from web3 import Web3
        checksum_address = Web3.to_checksum_address(contract_address)
        return f"nft:{chain_id}:{checksum_address}:{token_id}"
    
    def _get_collection_key(self, chain_id: int, contract_address: str) -> str:
        """Generate Redis key for collection data."""
        # Use checksum address format for consistency with EthereumAddress type
        from web3 import Web3
        checksum_address = Web3.to_checksum_address(contract_address)
        return f"collection:{chain_id}:{checksum_address}"
    
    def _get_leaderboard_key(self, scope: str = "global", chain_id: Optional[int] = None) -> str:
        """Generate Redis key for leaderboard."""
        if scope == "global":
            return "leaderboard:global"
        elif scope == "chain" and chain_id:
            return f"leaderboard:chain:{chain_id}"
        else:
            raise ValueError("Invalid leaderboard scope")
    
    async def store_nft_analysis(self, token_info: TokenInfo) -> bool:
        """
        Store NFT analysis result in the database.
        
        Args:
            token_info: Complete token information including trust analysis
            
        Returns:
            True if stored successfully
        """
        try:
            if not self.redis:
                raise RuntimeError("Database not initialized")
            
            chain_id = token_info.trust_analysis.chain_trust.chain_id if token_info.trust_analysis else 1
            nft_key = self._get_nft_key(chain_id, token_info.contract_address, token_info.token_id)
            collection_key = self._get_collection_key(chain_id, token_info.contract_address)
            
            # Prepare storage data with metadata
            token_info_json = token_info.model_dump(mode='json')
            # Extract individual scores from trust analysis for lightweight reads
            try:
                ta = token_info_json.get("trust_analysis") or {}
                permanence_score = (ta.get("permanence") or {}).get("overall_score")
                trustlessness_score = (ta.get("trustlessness") or {}).get("overall_score")
            except Exception:
                permanence_score = None
                trustlessness_score = None

            storage_data = {
                "token_info": token_info_json,
                "stored_at": datetime.now(timezone.utc).isoformat(),
                "analysis_version": token_info.trust_analysis.analysis_version if token_info.trust_analysis else "1.0",
                "chain_id": chain_id,
                "contract_address": token_info.contract_address.lower(),
                "token_id": token_info.token_id,
                "permanence_score": permanence_score,
                "trustlessness_score": trustlessness_score,
            }
            
            # Use pipeline for atomic operations
            pipe = self.redis.pipeline()
            
            # Store NFT data
            pipe.hset(nft_key, mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in storage_data.items()})
            
            # Update leaderboard if trust analysis exists
            if token_info.trust_analysis:
                score = token_info.trust_analysis.overall_score
                
                # Global leaderboard
                pipe.zadd("leaderboard:global", {nft_key: score})
                
                # Chain-specific leaderboard
                chain_leaderboard_key = f"leaderboard:chain:{chain_id}"
                pipe.zadd(chain_leaderboard_key, {nft_key: score})
                
                # Collection-specific leaderboard
                collection_leaderboard_key = f"leaderboard:collection:{chain_id}:{token_info.contract_address.lower()}"
                pipe.zadd(collection_leaderboard_key, {nft_key: score})
            
            # Update collection statistics
            await self._update_collection_stats(collection_key, token_info, pipe)
            
            # Update global statistics
            await self._update_global_stats(token_info, pipe)
            
            # Execute all operations
            await pipe.execute()
            
            logger.info(f"Stored NFT analysis: {nft_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store NFT analysis: {e}")
            raise RuntimeError(f"Failed to store analysis: {e}")
    
    async def get_nft_analysis(self, chain_id: int, contract_address: str, token_id: int) -> Optional[TokenInfo]:
        """
        Retrieve NFT analysis from database.
        
        Args:
            chain_id: Blockchain ID
            contract_address: Contract address
            token_id: Token ID
            
        Returns:
            TokenInfo if found, None otherwise
        """
        try:
            if not self.redis:
                raise RuntimeError("Database not initialized")
            
            nft_key = self._get_nft_key(chain_id, contract_address, token_id)
            data = await self.redis.hgetall(nft_key)
            
            if not data:
                return None
            
            # Parse stored JSON data
            token_info_data = json.loads(data.get("token_info", "{}"))
            if not token_info_data:
                return None
            
            return TokenInfo.model_validate(token_info_data)
            
        except Exception as e:
            logger.error(f"Failed to retrieve NFT analysis: {e}")
            raise RuntimeError(f"Failed to retrieve analysis: {e}")
    
    async def _update_collection_stats(self, collection_key: str, token_info: TokenInfo, pipe):
        """Update collection statistics."""
        try:
            # Get current collection data
            collection_data = await self.redis.hgetall(collection_key)
            
            # Extract collection info from token
            collection_name = ""
            if token_info.contract_metadata and hasattr(token_info.contract_metadata, 'name'):
                collection_name = token_info.contract_metadata.name
            elif token_info.metadata and hasattr(token_info.metadata, 'name'):
                collection_name = token_info.metadata.name[:50]  # Truncate if too long
            
            # Calculate new statistics
            current_count = int(collection_data.get("token_count", "0"))
            current_total_score = float(collection_data.get("total_score", "0.0"))
            
            new_count = current_count + 1
            score = token_info.trust_analysis.overall_score if token_info.trust_analysis else 0
            new_total_score = current_total_score + score
            new_average_score = new_total_score / new_count
            
            # Update collection data
            pipe.hset(
                collection_key,
                mapping={
                    "chain_id": str(token_info.trust_analysis.chain_trust.chain_id if token_info.trust_analysis else 1),
                    "contract_address": str(token_info.contract_address),
                    "collection_name": collection_name,
                    "token_count": str(new_count),
                    "total_score": str(new_total_score),
                    "average_score": str(round(new_average_score, 2)),
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to update collection stats: {e}")
    
    async def _update_global_stats(self, token_info: TokenInfo, pipe):
        """Update global statistics."""
        try:
            # Increment analysis counter
            pipe.incr("analysis_count")
            
            # Update global stats
            stats_data = await self.redis.hgetall("stats:global")
            current_analyses = int(stats_data.get("total_analyses", "0"))
            current_total_score = float(stats_data.get("total_score", "0.0"))
            
            new_analyses = current_analyses + 1
            score = token_info.trust_analysis.overall_score if token_info.trust_analysis else 0
            new_total_score = current_total_score + score
            new_average = new_total_score / new_analyses if new_analyses > 0 else 0
            
            pipe.hset(
                "stats:global",
                mapping={
                    "total_analyses": str(new_analyses),
                    "total_score": str(new_total_score),
                    "average_score": str(round(new_average, 2)),
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to update global stats: {e}")
    
    # Detailed tuple-based leaderboard removed; use get_leaderboard_items

    async def get_leaderboard_items(
        self,
        scope: str = "global",
        chain_id: Optional[int] = None,
        start: int = 0,
        end: int = -1,
        reverse: bool = True
    ) -> List[LeaderboardEntry]:
        """Return lightweight leaderboard items using stored metadata only."""
        try:
            if not self.redis:
                raise RuntimeError("Database not initialized")

            leaderboard_key = self._get_leaderboard_key(scope, chain_id)

            if reverse:
                entries = await self.redis.zrevrange(leaderboard_key, start, end, withscores=True)
            else:
                entries = await self.redis.zrange(leaderboard_key, start, end, withscores=True)

            results: List[LeaderboardEntry] = []
            for key, score in entries:
                nft_key = key.decode() if isinstance(key, bytes) else key
                # Fetch minimal metadata from the NFT hash without loading token_info
                nft_hash = await self.redis.hgetall(nft_key)
                if not nft_hash:
                    continue
                try:
                    chain_val = int(nft_hash.get("chain_id", "0"))
                    contract_val = (nft_hash.get("contract_address") or "").lower()
                    token_val = int(nft_hash.get("token_id", "0"))
                    stored_at = nft_hash.get("stored_at", "")

                    # Prefer precomputed individual scores (avoid loading full token_info)
                    permanence_score = nft_hash.get("permanence_score")
                    trustlessness_score = nft_hash.get("trustlessness_score")
                    permanence_score = int(permanence_score) if permanence_score not in (None, "", "null") else None
                    trustlessness_score = int(trustlessness_score) if trustlessness_score not in (None, "", "null") else None

                    results.append(LeaderboardEntry(
                        chain_id=chain_val,
                        contract_address=contract_val,
                        token_id=token_val,
                        score=float(score),
                        permanence_score=permanence_score,
                        trustlessness_score=trustlessness_score,
                        stored_at=stored_at,
                    ))
                except Exception:
                    continue

            return results
        except Exception as e:
            logger.error(f"Failed to get lightweight leaderboard: {e}")
            raise RuntimeError(f"Failed to get leaderboard: {e}")
    
    # Filtered leaderboard removed; consumers should filter client-side or extend items
    
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
    
    async def find_existing_token_id(self, chain_id: int, contract_address: str) -> Optional[int]:
        """Return a token id for the contract if one exists in Redis."""
        try:
            if not self.redis:
                raise RuntimeError("Database not initialized")
            
            from web3 import Web3
            checksum_address = Web3.to_checksum_address(contract_address)
            pattern = f"nft:{chain_id}:{checksum_address}:*"
            keys = await self.redis.keys(pattern)
            if not keys:
                return None
            first_key = keys[0]
            return int(first_key.split(':')[-1])
            
        except Exception as e:
            logger.error(f"Failed to find contract tokens: {e}")
            return None
    
    async def get_global_stats(self) -> Dict[str, Any]:
        """Get global statistics."""
        try:
            if not self.redis:
                raise RuntimeError("Database not initialized")
            
            stats_data = await self.redis.hgetall("stats:global")
            return {
                "total_analyses": int(stats_data.get("total_analyses", "0")),
                "average_score": float(stats_data.get("average_score", "0.0")),
                "last_updated": stats_data.get("last_updated", "")
            }
            
        except Exception as e:
            logger.error(f"Failed to get global stats: {e}")
            raise RuntimeError(f"Failed to get statistics: {e}")