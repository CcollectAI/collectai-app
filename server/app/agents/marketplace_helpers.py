"""
Shared adapter utilities for the marketplace agent.

Contains data classes, scoring functions, dedup helpers, and date parsing
used by the main MarketplaceAgent orchestrator.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .marketplace_routing import (
    SOURCE_RELIABILITY,
    RECENCY_7D_BOOST,
    RECENCY_30D_BOOST,
    SOLD_BONUS,
    CONDITION_MATCH_BONUS,
)

logger = logging.getLogger(__name__)

# In-flight request dedup — concurrent identical searches wait for the first
# caller to finish rather than issuing duplicate adapter calls.
_inflight: Dict[str, asyncio.Future] = {}


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


def dedup_and_score(
    all_hits: List[Dict[str, Any]],
    condition: Optional[str] = None,
) -> tuple[List[ScoredMarketHit], int]:
    """Deduplicate hits by content hash, then score each one.

    Returns (scored_hits sorted by provenance desc, dedup_count).
    """
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
    return scored_hits, dedup_count
