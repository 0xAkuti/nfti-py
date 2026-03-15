"""
Supabase Postgres database implementation for the NFT Inspector API.
"""

import copy
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import asyncio

from src.nft_inspector.models import TokenInfo, NFTInspectionResult
from .base import DatabaseManagerInterface
from ..models import LeaderboardEntry, ScoreStatistics, StatsResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data URI deduplication helpers
# ---------------------------------------------------------------------------

def _is_data_uri(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("data:")


def _truncate_data_uri(uri: str) -> str:
    """Replace a data URI with a short marker that preserves the MIME type."""
    after_colon = uri[5:]  # strip "data:"
    sep = len(after_colon)
    for ch in (";", ","):
        idx = after_colon.find(ch)
        if 0 <= idx < sep:
            sep = idx
    mime = after_colon[:sep] if sep > 0 else "unknown"
    return f"data:{mime};truncated"


def deduplicate_data_uris(data: dict) -> dict:
    """Strip redundant large data-URI blobs from an NFT analysis dict.

    Keeps intact the fields the frontend needs for rendering:
      metadata.image / animation_url / image_data,
      contract_metadata.image,
      external_resources[].url_info.url.

    Truncates:
      top-level token_uri / contract_uri,
      data_report.*.url,
      contract_data_report.*.url.
    """
    result = copy.deepcopy(data)

    if _is_data_uri(result.get("token_uri", "")):
        result["token_uri"] = _truncate_data_uri(result["token_uri"])

    if _is_data_uri(result.get("contract_uri", "")):
        result["contract_uri"] = _truncate_data_uri(result["contract_uri"])

    dr = result.get("data_report")
    if isinstance(dr, dict):
        for field in ("token_uri", "image", "animation_url", "external_url", "image_data"):
            info = dr.get(field)
            if isinstance(info, dict) and _is_data_uri(info.get("url", "")):
                info["url"] = _truncate_data_uri(info["url"])

    cdr = result.get("contract_data_report")
    if isinstance(cdr, dict):
        for field in ("contract_uri", "image", "banner_image", "featured_image", "external_link"):
            info = cdr.get(field)
            if isinstance(info, dict) and _is_data_uri(info.get("url", "")):
                info["url"] = _truncate_data_uri(info["url"])

    return result


# ---------------------------------------------------------------------------
# Supabase manager
# ---------------------------------------------------------------------------

class SupabaseManager(DatabaseManagerInterface):
    """Supabase Postgres database manager using the PostgREST client."""

    TABLE = "nft_analyses"

    def __init__(self, supabase_url: str, supabase_key: str):
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.client = None

    async def initialize(self) -> None:
        from supabase import create_client

        self.client = await asyncio.to_thread(
            create_client, self.supabase_url, self.supabase_key
        )
        await asyncio.to_thread(
            lambda: self.client.table(self.TABLE).select("id").limit(1).execute()
        )
        logger.info("Connected to Supabase Postgres")

    async def close(self) -> None:
        self.client = None

    # ------------------------------------------------------------------
    # store
    # ------------------------------------------------------------------
    async def store_nft_analysis(self, token_info: TokenInfo) -> bool:
        if not self.client:
            raise RuntimeError("Database not initialized")

        ta = token_info.trust_analysis
        chain_id = ta.chain_trust.chain_id if ta else 1

        token_dict = token_info.model_dump(mode="json", exclude_defaults=True)
        deduped = deduplicate_data_uris(token_dict)

        row = {
            "chain_id": chain_id,
            "contract_address": token_info.contract_address.lower(),
            "token_id": token_info.token_id,
            "collection_name": self.extract_collection_name(token_info),
            "overall_score": ta.overall_score if ta else 0,
            "permanence_score": ta.permanence.overall_score if ta else 0,
            "trustlessness_score": ta.trustlessness.overall_score if ta else 0,
            "overall_level": ta.overall_level if ta else "",
            "permanence_level": ta.permanence.permanence_level if ta else None,
            "trustlessness_level": ta.trustlessness.trustlessness_level if ta else None,
            "analysis_version": ta.analysis_version if ta else "1.1",
            "stored_at": datetime.now(timezone.utc).isoformat(),
            "token_info": deduped,
        }

        try:
            await asyncio.to_thread(
                lambda: self.client.table(self.TABLE)
                .upsert(row, on_conflict="chain_id,contract_address,token_id")
                .execute()
            )
        except Exception as e:
            logger.error(f"Failed to store NFT analysis: {e}")
            raise RuntimeError(f"Failed to store analysis: {e}")

        logger.info(
            f"Stored NFT analysis: {chain_id}:{token_info.contract_address}:{token_info.token_id}"
        )
        return True

    # ------------------------------------------------------------------
    # get
    # ------------------------------------------------------------------
    async def get_nft_analysis(
        self, chain_id: int, contract_address: str, token_id: int
    ) -> Optional[NFTInspectionResult]:
        if not self.client:
            raise RuntimeError("Database not initialized")

        try:
            resp = await asyncio.to_thread(
                lambda: self.client.table(self.TABLE)
                .select("token_info")
                .eq("chain_id", chain_id)
                .eq("contract_address", contract_address.lower())
                .eq("token_id", token_id)
                .limit(1)
                .execute()
            )
        except Exception as e:
            logger.error(f"Failed to retrieve NFT analysis: {e}")
            raise RuntimeError(f"Failed to retrieve analysis: {e}")

        if not resp.data:
            return None

        token_info_json = resp.data[0].get("token_info")
        if not token_info_json:
            return None

        try:
            return NFTInspectionResult.model_validate(token_info_json)
        except Exception as e:
            logger.warning(
                f"Cached data failed validation "
                f"(chain={chain_id}, contract={contract_address}, token={token_id}), "
                f"treating as cache miss: {e}"
            )
            return None

    # ------------------------------------------------------------------
    # leaderboard
    # ------------------------------------------------------------------
    async def get_leaderboard_items(
        self,
        scope: str = "global",
        chain_id: Optional[int] = None,
        start: int = 0,
        end: int = -1,
        reverse: bool = True,
    ) -> List[LeaderboardEntry]:
        if not self.client:
            raise RuntimeError("Database not initialized")

        try:
            query = self.client.table(self.TABLE).select(
                "chain_id, contract_address, token_id, collection_name, "
                "overall_score, permanence_score, trustlessness_score, stored_at"
            )
            if scope == "chain" and chain_id is not None:
                query = query.eq("chain_id", chain_id)

            query = query.order("overall_score", desc=reverse).limit(10000)
            resp = await asyncio.to_thread(lambda: query.execute())
        except Exception as e:
            logger.error(f"Failed to get leaderboard: {e}")
            raise RuntimeError(f"Failed to get leaderboard: {e}")

        # One entry per (chain_id, contract_address) — keep first (highest score)
        seen: set = set()
        deduped: list = []
        for row in resp.data or []:
            key = (row["chain_id"], row["contract_address"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)

        page = deduped[start:] if end == -1 else deduped[start: end + 1]

        results: List[LeaderboardEntry] = []
        for row in page:
            try:
                stored_at = row.get("stored_at", "")
                if isinstance(stored_at, datetime):
                    stored_at = stored_at.isoformat()
                results.append(
                    LeaderboardEntry(
                        chain_id=row["chain_id"],
                        contract_address=row["contract_address"],
                        token_id=row["token_id"],
                        collection_name=row.get("collection_name", "Unknown Collection"),
                        score=float(row["overall_score"]),
                        permanence_score=row["permanence_score"],
                        trustlessness_score=row["trustlessness_score"],
                        stored_at=stored_at,
                    )
                )
            except Exception:
                continue
        return results

    # ------------------------------------------------------------------
    # find_existing_token_id
    # ------------------------------------------------------------------
    async def find_existing_token_id(
        self, chain_id: int, contract_address: str
    ) -> Optional[int]:
        if not self.client:
            raise RuntimeError("Database not initialized")

        try:
            resp = await asyncio.to_thread(
                lambda: self.client.table(self.TABLE)
                .select("token_id")
                .eq("chain_id", chain_id)
                .eq("contract_address", contract_address.lower())
                .limit(1)
                .execute()
            )
        except Exception as e:
            logger.error(f"Failed to find contract tokens: {e}")
            return None

        if resp.data:
            return resp.data[0]["token_id"]
        return None

    # ------------------------------------------------------------------
    # stats (computed live from rows)
    # ------------------------------------------------------------------
    async def get_global_stats(self) -> Dict[str, Any]:
        if not self.client:
            raise RuntimeError("Database not initialized")

        try:
            resp = await asyncio.to_thread(
                lambda: self.client.table(self.TABLE)
                .select(
                    "overall_score, permanence_score, trustlessness_score, "
                    "chain_id, contract_address, stored_at"
                )
                .execute()
            )
        except Exception as e:
            logger.error(f"Failed to get global stats: {e}")
            raise RuntimeError(f"Failed to get statistics: {e}")

        rows = resp.data or []

        if not rows:
            empty = ScoreStatistics(average=0.0, total=0.0, histogram={})
            return StatsResponse(
                total_analyses=0,
                total_score_stats=empty,
                permanence_score_stats=empty,
                trustlessness_score_stats=empty,
                analyzed_collections=[],
                last_updated=datetime.now(timezone.utc).isoformat(),
            ).model_dump()

        def _build_stats(scores: List[int]) -> ScoreStatistics:
            total = sum(scores)
            avg = round(total / len(scores), 2)
            hist: Dict[int, int] = {}
            for s in scores:
                hist[s] = hist.get(s, 0) + 1
            return ScoreStatistics(average=avg, total=float(total), histogram=hist)

        collections = sorted(
            {f"{r['chain_id']}:{r['contract_address']}" for r in rows}
        )

        last_updated = max((r.get("stored_at", "") for r in rows), default="")
        if isinstance(last_updated, datetime):
            last_updated = last_updated.isoformat()

        return StatsResponse(
            total_analyses=len(collections),
            total_score_stats=_build_stats([r["overall_score"] for r in rows]),
            permanence_score_stats=_build_stats([r["permanence_score"] for r in rows]),
            trustlessness_score_stats=_build_stats([r["trustlessness_score"] for r in rows]),
            analyzed_collections=collections,
            last_updated=last_updated or datetime.now(timezone.utc).isoformat(),
        ).model_dump()
