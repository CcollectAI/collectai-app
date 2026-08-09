"""
Shared utilities, types, and constants for the intake pipeline.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import CATALOG_LEARNING_ENABLED
from app.lib.bg_tasks import spawn_bg
from app.lib.db_helpers import get_db_pool

logger = logging.getLogger(__name__)

# Current taxonomy version — must stay in sync with src/ingest/types.py
TAXONOMY_VERSION = "v1.0"

# Minimum number of user corrections before we surface a suggestion
CORRECTION_THRESHOLD = 5


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class IntakeResult:
    """Unified result of the intake agent pipeline."""

    # Identification
    name: Optional[str] = None
    category_id: Optional[str] = None
    category_confidence: float = 0.0
    subtype_id: Optional[str] = None

    # Attributes
    attributes: dict[str, Any] = field(default_factory=dict)

    # Source tracking
    identification_method: str = "manual"
    barcode: Optional[str] = None
    barcode_type: Optional[str] = None

    # Taxonomy
    taxonomy_version: str = TAXONOMY_VERSION
    taxonomy_confidence: float = 0.0
    suggested_corrections: list[dict[str, Any]] = field(default_factory=list)

    # Price hint
    estimated_price: Optional[float] = None
    price_source: Optional[str] = None
    price_band: Optional[dict[str, Any]] = None

    # Image
    image_url: Optional[str] = None

    # Catalog learning
    catalog_miss: bool = False

    # Catalog matching (RAG)
    catalog_match_id: Optional[str] = None
    catalog_match_key: Optional[str] = None
    alternatives: list[dict[str, Any]] = field(default_factory=list)
    field_confidence: Optional[dict[str, float]] = None
    chain_of_thought: Optional[str] = None

    # Rationale trail
    rationale: list[str] = field(default_factory=list)

    # Scan session (F9)
    scan_session_id: Optional[str] = None

    # Condition grading (F6)
    defect_annotations: list[dict[str, Any]] = field(default_factory=list)
    suggested_grade: Optional[dict[str, Any]] = None

    # Social proof (F10)
    social_proof: Optional[dict[str, Any]] = None

    # Duplicate detection (F7)
    duplicate_info: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category_id": self.category_id,
            "category_confidence": round(self.category_confidence, 4),
            "subtype_id": self.subtype_id,
            "attributes": self.attributes,
            "identification_method": self.identification_method,
            "barcode": self.barcode,
            "barcode_type": self.barcode_type,
            "taxonomy_version": self.taxonomy_version,
            "taxonomy_confidence": round(self.taxonomy_confidence, 4),
            "suggested_corrections": self.suggested_corrections,
            "estimated_price": self.estimated_price,
            "price_source": self.price_source,
            "price_band": self.price_band,
            "image_url": self.image_url,
            "catalog_miss": self.catalog_miss,
            "catalog_match_id": self.catalog_match_id,
            "catalog_match_key": self.catalog_match_key,
            "alternatives": self.alternatives,
            "field_confidence": self.field_confidence,
            "chain_of_thought": self.chain_of_thought,
            "rationale": self.rationale,
            "scan_session_id": self.scan_session_id,
            "defect_annotations": self.defect_annotations,
            "suggested_grade": self.suggested_grade,
            "social_proof": self.social_proof,
            "duplicate_info": self.duplicate_info,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _price_band_to_dict(price_band) -> dict[str, Any]:
    """Convert a PriceBand Pydantic model to a plain dict."""
    try:
        # Pydantic v2
        return price_band.model_dump()
    except AttributeError:
        pass
    try:
        # Pydantic v1
        return price_band.dict()
    except AttributeError:
        # Already a dict or unknown type
        if isinstance(price_band, dict):
            return price_band
        return {
            "q10": getattr(price_band, "q10", 0),
            "q50": getattr(price_band, "q50", 0),
            "q90": getattr(price_band, "q90", 0),
            "confidence": getattr(price_band, "confidence", 0),
            "currency": getattr(price_band, "currency", "EUR"),
        }


def _normalize_for_search(text: str) -> str:
    """Lowercase, strip punctuation, truncate to 100 chars."""
    t = text.lower().strip()
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:100]


def _text_similarity(a: str, b: str) -> float:
    """Jaccard token overlap (word-level) between two strings."""
    tokens_a = set(_normalize_for_search(a).split())
    tokens_b = set(_normalize_for_search(b).split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


# ---------------------------------------------------------------------------
# Taxonomy correction lookup
# ---------------------------------------------------------------------------

async def _lookup_taxonomy_corrections(
    category_id: str,
    pool,
) -> list[dict[str, Any]]:
    """
    Query taxonomy_corrections table for strong correction patterns.

    Returns a list of suggested corrections where the correction count
    meets the threshold.
    """
    if not pool or not category_id:
        return []

    try:
        async with pool.acquire() as conn:
            # taxonomy_corrections columns are original_category /
            # corrected_category (not from_/to_). Aliasing back to the
            # caller-facing names so the response shape stays stable.
            rows = await conn.fetch(
                """
                SELECT
                    original_category AS from_category,
                    corrected_category AS to_category,
                    COUNT(*) AS frequency,
                    COUNT(DISTINCT user_id) AS user_count
                FROM taxonomy_corrections
                WHERE original_category = $1
                GROUP BY original_category, corrected_category
                HAVING COUNT(*) >= $2
                ORDER BY COUNT(*) DESC
                LIMIT 5
                """,
                category_id,
                CORRECTION_THRESHOLD,
            )
            return [
                {
                    "from_category": row["from_category"],
                    "to_category": row["to_category"],
                    "frequency": row["frequency"],
                    "user_count": row["user_count"],
                }
                for row in rows
            ]
    except Exception as e:
        logger.debug("Taxonomy corrections lookup error: %s", e)
        return []


# ---------------------------------------------------------------------------
# Catalog Learning — log misses (best-effort, fire-and-forget)
# ---------------------------------------------------------------------------

def _fire_catalog_miss(**kwargs) -> None:
    """Fire-and-forget wrapper for _log_catalog_miss (non-blocking).

    spawn_bg holds a ref (so the task can't be GC'd mid-INSERT) and logs any
    failure at WARNING; it no-ops cleanly when there's no running loop.
    """
    spawn_bg(_log_catalog_miss(**kwargs), "catalog_miss")


async def _log_catalog_miss(
    user_id: Optional[str],
    source: str,
    input_data: dict[str, Any],
    suggested_name: Optional[str] = None,
) -> None:
    """Best-effort insert into catalog_suggestions for learning pipeline."""
    try:
        if not CATALOG_LEARNING_ENABLED or not user_id:
            return

        pool = get_db_pool()
        if pool is None:
            return

        name = (suggested_name or "").strip() or "Unknown item"
        input_json = json.dumps(input_data, sort_keys=True, default=str)

        await pool.execute(
            """
            INSERT INTO catalog_suggestions (
                id, user_id, source, input_data, suggested_name, status
            ) VALUES (
                gen_random_uuid(), $1::uuid, $2, $3::jsonb, $4, 'pending'
            )
            ON CONFLICT (user_id, source, md5(input_data::text)) DO NOTHING
            """,
            user_id,
            source,
            input_json,
            name[:500],
        )
        logger.debug("[catalog-miss] Logged %s miss for user %s", source, user_id)
    except Exception as exc:
        logger.debug("[catalog-miss] Failed to log miss: %s", exc)
