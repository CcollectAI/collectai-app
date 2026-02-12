"""
Marketplace Aggregation Agent.

Orchestrates multiple market source adapters (eBay, TCGPlayer, future sources),
normalizes results, deduplicates hits, and computes provenance/confidence scores.

Usage:
    agent = MarketplaceAgent()
    result = await agent.aggregate_search("Charizard Base Set Holo", category="pokemon")
    comps  = await agent.find_sold_comps("Charizard Base Set Holo", category="pokemon")
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from app.agents.adapters.ebay_caller import EbayCaller
from app.agents.adapters.tcgplayer_caller import TCGPlayerCaller
from app.agents.adapters.firecrawl_caller import FirecrawlCaller
from app.lib.region_marketplace_config import (
    should_use_adapter,
    get_ebay_marketplace_id,
    get_firecrawl_sites,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Source reliability weights
# ---------------------------------------------------------------------------

SOURCE_RELIABILITY: Dict[str, float] = {
    "ebay_sold": 0.95,
    "tcgplayer": 0.90,
    "ebay_listed": 0.70,
    "firecrawl": 0.65,
    "firecrawl_sold": 0.70,
}

# Bonus scores
RECENCY_7D_BOOST = 0.10
RECENCY_30D_BOOST = 0.05
SOLD_BONUS = 0.15
CONDITION_MATCH_BONUS = 0.10


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ScoredMarketHit:
    """A market hit enriched with provenance scoring."""
    hit: Dict[str, Any]
    provenance_score: float
    source_reliability: float
    recency_score: float
    is_sold: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hit": self.hit,
            "provenance_score": round(self.provenance_score, 4),
            "source_reliability": round(self.source_reliability, 4),
            "recency_score": round(self.recency_score, 4),
            "is_sold": self.is_sold,
        }


@dataclass
class AggregationResult:
    """Result of an aggregated marketplace search."""
    hits: List[ScoredMarketHit]
    total_sources_queried: int
    successful_sources: int
    aggregate_confidence: float
    dedup_count: int
    query_metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hits": [h.to_dict() for h in self.hits],
            "total_sources_queried": self.total_sources_queried,
            "successful_sources": self.successful_sources,
            "aggregate_confidence": round(self.aggregate_confidence, 4),
            "dedup_count": self.dedup_count,
            "query_metadata": self.query_metadata,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _content_hash(source: str, raw_id: str) -> str:
    """Compute a SHA-256 content hash for deduplication."""
    payload = f"{source}:{raw_id}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_sold_date(sold_at: Optional[str]) -> Optional[datetime]:
    """Attempt to parse a sold/end date string into a datetime."""
    if not sold_at:
        return None
    # Try ISO 8601 first, then common variations
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(sold_at, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _compute_recency_score(sold_at: Optional[str]) -> float:
    """Compute recency score based on when the item sold."""
    if not sold_at:
        return 0.0
    dt = _parse_sold_date(sold_at)
    if not dt:
        return 0.0

    now = datetime.now(timezone.utc)
    age = now - dt
    if age <= timedelta(days=7):
        return RECENCY_7D_BOOST
    elif age <= timedelta(days=30):
        return RECENCY_30D_BOOST
    return 0.0


def _compute_provenance_score(
    hit: Dict[str, Any],
    query_condition: Optional[str] = None,
) -> tuple[float, float, float, bool]:
    """Compute provenance score for a single market hit.

    Returns (provenance_score, source_reliability, recency_score, is_sold).
    """
    source = hit.get("source", "")
    is_sold = bool(hit.get("is_sold", False))

    # Determine source reliability key
    if source == "ebay":
        reliability_key = "ebay_sold" if is_sold else "ebay_listed"
    elif source == "tcgplayer":
        reliability_key = "tcgplayer"
    else:
        reliability_key = source

    source_reliability = SOURCE_RELIABILITY.get(reliability_key, 0.50)

    # Recency boost
    recency_score = _compute_recency_score(hit.get("sold_at"))

    # Sold bonus
    sold_bonus = SOLD_BONUS if is_sold else 0.0

    # Condition match bonus
    condition_bonus = 0.0
    if query_condition and hit.get("condition"):
        hit_cond = str(hit.get("condition", "")).lower().strip()
        query_cond = query_condition.lower().strip()
        if query_cond in hit_cond or hit_cond in query_cond:
            condition_bonus = CONDITION_MATCH_BONUS

    provenance_score = min(
        1.0,
        source_reliability + recency_score + sold_bonus + condition_bonus,
    )

    return provenance_score, source_reliability, recency_score, is_sold


def _compute_aggregate_confidence(
    scored_hits: List[ScoredMarketHit],
    total_sources: int,
    successful_sources: int,
) -> float:
    """Compute aggregate confidence for the entire search.

    Weighted by provenance scores, source coverage, and result count.
    """
    if not scored_hits or total_sources == 0:
        return 0.0

    # Source coverage factor (0-0.4)
    coverage = (successful_sources / total_sources) * 0.4

    # Result depth factor (0-0.3) — more results = higher confidence, caps at 20
    result_depth = min(len(scored_hits) / 20.0, 1.0) * 0.3

    # Average provenance quality (0-0.3)
    avg_provenance = sum(h.provenance_score for h in scored_hits) / len(scored_hits)
    quality = avg_provenance * 0.3

    return min(1.0, coverage + result_depth + quality)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class MarketplaceAgent:
    """Marketplace Aggregation Agent.

    Orchestrates multiple adapters, deduplicates, scores, and returns
    structured AggregationResult objects.
    """

    def __init__(self) -> None:
        self._ebay = EbayCaller()
        self._tcgplayer = TCGPlayerCaller()
        self._firecrawl = FirecrawlCaller()

    @property
    def adapters_configured(self) -> Dict[str, bool]:
        """Return which adapters are configured."""
        return {
            "ebay": self._ebay.configured,
            "tcgplayer": self._tcgplayer.configured,
            "firecrawl": self._firecrawl.configured,
        }

    async def close(self) -> None:
        """Close all adapter HTTP clients."""
        await self._ebay.close()
        await self._tcgplayer.close()
        await self._firecrawl.close()

    # ------------------------------------------------------------------
    # Core search
    # ------------------------------------------------------------------

    async def aggregate_search(
        self,
        query: str,
        category: Optional[str] = None,
        condition: Optional[str] = None,
        limit: int = 20,
        include_sold: bool = True,
        region: Optional[str] = None,
    ) -> AggregationResult:
        """Search across all configured marketplace adapters.

        Deduplicates results, computes provenance scores, and returns
        an AggregationResult with aggregate confidence.

        *region* (americas/europe/japan/other) gates adapters and targets
        region-specific eBay marketplaces and Firecrawl sites.
        """
        all_hits: List[Dict[str, Any]] = []
        total_sources = 0
        successful_sources = 0
        source_errors: List[str] = []

        ebay_mktplace = get_ebay_marketplace_id(region)
        fc_sites = get_firecrawl_sites(region, category)

        # Determine which adapters to query
        tasks = []

        # eBay active listings
        if self._ebay.configured and should_use_adapter(region, "ebay"):
            total_sources += 1
            tasks.append(("ebay_listed", self._ebay.search(query, category=category, limit=limit, marketplace_id=ebay_mktplace)))

        # eBay sold comps
        if self._ebay.configured and include_sold and should_use_adapter(region, "ebay"):
            total_sources += 1
            tasks.append(("ebay_sold", self._ebay.sold_comps(query, category=category, limit=limit, marketplace_id=ebay_mktplace)))

        # TCGPlayer (only for TCG categories or if no category specified)
        tcg_categories = {"pokemon", "mtg", "yugioh", "lorcana"}
        if self._tcgplayer.configured and should_use_adapter(region, "tcgplayer") and (category is None or category in tcg_categories):
            total_sources += 1
            tasks.append(("tcgplayer", self._tcgplayer.search(query, category=category, limit=limit)))

        # Firecrawl (web search for sites without direct APIs)
        if self._firecrawl.configured and should_use_adapter(region, "firecrawl"):
            total_sources += 1
            tasks.append(("firecrawl", self._firecrawl.search(query, category=category, limit=limit, region_sites=fc_sites)))

        if not tasks:
            logger.warning("[MarketplaceAgent] No adapters configured for query: %s", query)
            return AggregationResult(
                hits=[],
                total_sources_queried=0,
                successful_sources=0,
                aggregate_confidence=0.0,
                dedup_count=0,
                query_metadata={"query": query, "category": category, "region": region},
            )

        # Execute all adapter queries concurrently
        results = await asyncio.gather(
            *[task for _, task in tasks],
            return_exceptions=True,
        )

        for (source_name, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.error("[MarketplaceAgent] %s failed: %s", source_name, result)
                source_errors.append(source_name)
            elif isinstance(result, list):
                successful_sources += 1
                all_hits.extend(result)
            else:
                logger.warning("[MarketplaceAgent] %s returned unexpected type: %s", source_name, type(result))

        # Deduplicate by content hash
        seen_hashes: set[str] = set()
        unique_hits: List[Dict[str, Any]] = []
        dedup_count = 0

        for hit in all_hits:
            ch = _content_hash(hit.get("source", ""), hit.get("raw_id", ""))
            if ch in seen_hashes:
                dedup_count += 1
                continue
            seen_hashes.add(ch)
            hit["content_hash"] = ch
            unique_hits.append(hit)

        # Score each hit
        scored_hits: List[ScoredMarketHit] = []
        for hit in unique_hits:
            prov, reliability, recency, is_sold = _compute_provenance_score(
                hit, query_condition=condition,
            )
            scored_hits.append(ScoredMarketHit(
                hit=hit,
                provenance_score=prov,
                source_reliability=reliability,
                recency_score=recency,
                is_sold=is_sold,
            ))

        # Sort by provenance score descending, then by price descending
        scored_hits.sort(key=lambda h: (h.provenance_score, h.hit.get("price", 0)), reverse=True)

        # Compute aggregate confidence
        aggregate_confidence = _compute_aggregate_confidence(
            scored_hits, total_sources, successful_sources,
        )

        return AggregationResult(
            hits=scored_hits,
            total_sources_queried=total_sources,
            successful_sources=successful_sources,
            aggregate_confidence=aggregate_confidence,
            dedup_count=dedup_count,
            query_metadata={
                "query": query,
                "category": category,
                "condition": condition,
                "limit": limit,
                "include_sold": include_sold,
                "region": region,
                "source_errors": source_errors,
            },
        )

    # ------------------------------------------------------------------
    # Sold comps + DB persistence
    # ------------------------------------------------------------------

    async def find_sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        condition: Optional[str] = None,
        limit: int = 20,
        region: Optional[str] = None,
    ) -> AggregationResult:
        """Find sold comparables across all adapters.

        Only returns sold/completed items for price estimation.
        """
        all_hits: List[Dict[str, Any]] = []
        total_sources = 0
        successful_sources = 0
        source_errors: List[str] = []

        ebay_mktplace = get_ebay_marketplace_id(region)
        fc_sites = get_firecrawl_sites(region, category)

        tasks = []

        # eBay sold comps
        if self._ebay.configured and should_use_adapter(region, "ebay"):
            total_sources += 1
            tasks.append(("ebay_sold", self._ebay.sold_comps(query, category=category, limit=limit, marketplace_id=ebay_mktplace)))

        # TCGPlayer sold comps
        tcg_categories = {"pokemon", "mtg", "yugioh", "lorcana"}
        if self._tcgplayer.configured and should_use_adapter(region, "tcgplayer") and (category is None or category in tcg_categories):
            total_sources += 1
            tasks.append(("tcgplayer_sold", self._tcgplayer.sold_comps(query, category=category, limit=limit)))

        # Firecrawl sold comps (web search)
        if self._firecrawl.configured and should_use_adapter(region, "firecrawl"):
            total_sources += 1
            tasks.append(("firecrawl_sold", self._firecrawl.sold_comps(query, category=category, limit=limit, region_sites=fc_sites)))

        if not tasks:
            return AggregationResult(
                hits=[],
                total_sources_queried=0,
                successful_sources=0,
                aggregate_confidence=0.0,
                dedup_count=0,
                query_metadata={"query": query, "category": category, "region": region, "mode": "sold_comps"},
            )

        results = await asyncio.gather(
            *[task for _, task in tasks],
            return_exceptions=True,
        )

        for (source_name, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.error("[MarketplaceAgent] %s failed: %s", source_name, result)
                source_errors.append(source_name)
            elif isinstance(result, list):
                successful_sources += 1
                all_hits.extend(result)

        # Deduplicate
        seen_hashes: set[str] = set()
        unique_hits: List[Dict[str, Any]] = []
        dedup_count = 0

        for hit in all_hits:
            ch = _content_hash(hit.get("source", ""), hit.get("raw_id", ""))
            if ch in seen_hashes:
                dedup_count += 1
                continue
            seen_hashes.add(ch)
            hit["content_hash"] = ch
            unique_hits.append(hit)

        # Score
        scored_hits: List[ScoredMarketHit] = []
        for hit in unique_hits:
            prov, reliability, recency, is_sold = _compute_provenance_score(
                hit, query_condition=condition,
            )
            scored_hits.append(ScoredMarketHit(
                hit=hit,
                provenance_score=prov,
                source_reliability=reliability,
                recency_score=recency,
                is_sold=is_sold,
            ))

        scored_hits.sort(key=lambda h: (h.provenance_score, h.hit.get("price", 0)), reverse=True)

        aggregate_confidence = _compute_aggregate_confidence(
            scored_hits, total_sources, successful_sources,
        )

        return AggregationResult(
            hits=scored_hits,
            total_sources_queried=total_sources,
            successful_sources=successful_sources,
            aggregate_confidence=aggregate_confidence,
            dedup_count=dedup_count,
            query_metadata={
                "query": query,
                "category": category,
                "condition": condition,
                "limit": limit,
                "region": region,
                "mode": "sold_comps",
                "source_errors": source_errors,
            },
        )

    async def persist_comps_to_db(
        self,
        result: AggregationResult,
        normalized_key: Optional[str] = None,
    ) -> int:
        """Persist scored market hits to the market_hits table.

        Returns the number of rows inserted.
        """
        try:
            from app.db import get_conn, db_configured
        except ImportError:
            logger.warning("[MarketplaceAgent] DB module not available")
            return 0

        if not db_configured():
            logger.info("[MarketplaceAgent] DB not configured, skipping persistence")
            return 0

        inserted = 0
        try:
            async with get_conn() as conn:
                for scored in result.hits:
                    hit = scored.hit
                    try:
                        await conn.execute(
                            """
                            INSERT INTO market_hits
                                (provider, listing_id, title, price, currency,
                                 condition, ended_at, url, normalized_key, features_json)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                            ON CONFLICT (provider, listing_id) DO NOTHING
                            """,
                            hit.get("source", ""),
                            hit.get("raw_id", ""),
                            hit.get("title", ""),
                            hit.get("price"),
                            hit.get("currency", "EUR"),
                            hit.get("condition"),
                            _parse_sold_date(hit.get("sold_at")),
                            hit.get("url"),
                            normalized_key,
                            {
                                "content_hash": hit.get("content_hash", ""),
                                "provenance_score": scored.provenance_score,
                                "source_reliability": scored.source_reliability,
                                "is_sold": scored.is_sold,
                            },
                        )
                        inserted += 1
                    except Exception:
                        logger.warning(
                            "[MarketplaceAgent] Failed to insert hit %s:%s",
                            hit.get("source"), hit.get("raw_id"),
                            exc_info=True,
                        )
        except RuntimeError as e:
            logger.warning("[MarketplaceAgent] DB connection error: %s", e)
        except Exception:
            logger.error("[MarketplaceAgent] DB persistence failed", exc_info=True)

        logger.info("[MarketplaceAgent] Persisted %d/%d hits to market_hits", inserted, len(result.hits))
        return inserted

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> Dict[str, Any]:
        """Check health of all configured adapters."""
        checks: Dict[str, Any] = {}

        tasks = []
        if self._ebay.configured:
            tasks.append(("ebay", self._ebay.health_check()))
        else:
            checks["ebay"] = {"configured": False, "healthy": False}

        if self._tcgplayer.configured:
            tasks.append(("tcgplayer", self._tcgplayer.health_check()))
        else:
            checks["tcgplayer"] = {"configured": False, "healthy": False}

        if self._firecrawl.configured:
            tasks.append(("firecrawl", self._firecrawl.health_check()))
        else:
            checks["firecrawl"] = {"configured": False, "healthy": False}

        if tasks:
            results = await asyncio.gather(
                *[task for _, task in tasks],
                return_exceptions=True,
            )
            for (name, _), result in zip(tasks, results):
                if isinstance(result, Exception):
                    checks[name] = {"configured": True, "healthy": False, "error": str(result)}
                else:
                    checks[name] = {"configured": True, "healthy": bool(result)}

        return {
            "adapters": checks,
            "any_healthy": any(
                v.get("healthy", False) for v in checks.values()
            ),
        }
