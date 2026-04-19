"""
Dossier Factory -- generates professional item reports / sales memos.

Each dossier aggregates data from multiple tables:
  - items (identity, attributes)
  - price_predictions (valuation)
  - item_provenance_events (provenance timeline)
  - price_history (price trends)
  - market_hits (comparable sales)

The output is a single ``ItemDossier`` dataclass that can be serialised
to JSON (for the API) or rendered into a self-contained HTML report
(for export / sharing).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DossierSection:
    title: str
    content: dict


@dataclass
class ItemDossier:
    item_id: str
    generated_at: str
    version: str = "1.0"

    # Sections
    identity: Dict[str, Any] = field(default_factory=dict)
    valuation: Dict[str, Any] = field(default_factory=dict)
    provenance: List[Dict[str, Any]] = field(default_factory=list)
    price_history: List[Dict[str, Any]] = field(default_factory=list)
    market_comps: List[Dict[str, Any]] = field(default_factory=list)
    photos: List[str] = field(default_factory=list)
    collections: List[str] = field(default_factory=list)

    # Meta
    authenticity_signals: List[str] = field(default_factory=list)
    completeness_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json_field(value: Any) -> Any:
    """Safely parse a JSON string or return the value as-is."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    return value


def _ts(dt: Any) -> str:
    """Convert a datetime / string to ISO-8601 string."""
    if dt is None:
        return ""
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def _compute_authenticity_signals(provenance_events: list) -> List[str]:
    """Derive authenticity signals from provenance event types/sources."""
    signals: List[str] = []
    event_types = {e.get("event_type") for e in provenance_events}
    sources = {e.get("source") for e in provenance_events}

    if "verified" in event_types:
        signals.append("owner_verified")
    if "graded" in event_types:
        signals.append("professionally_graded")
    if "receipt" in sources:
        signals.append("receipt_on_file")
    if "purchase" in event_types:
        signals.append("purchase_recorded")
    return signals


def _compute_completeness(
    *,
    has_photo: bool,
    has_provenance: bool,
    has_prediction: bool,
    has_attributes: bool,
    has_comps: bool,
) -> float:
    """Each flag is worth 0.2 -- returns a float 0.0 .. 1.0."""
    score = 0.0
    if has_photo:
        score += 0.2
    if has_provenance:
        score += 0.2
    if has_prediction:
        score += 0.2
    if has_attributes:
        score += 0.2
    if has_comps:
        score += 0.2
    return round(score, 2)


# ---------------------------------------------------------------------------
# Main generation function
# ---------------------------------------------------------------------------

async def generate_dossier(
    item_id: str,
    user_id: str,
    conn,
) -> ItemDossier:
    """
    Assemble a full dossier for *item_id* owned by *user_id*.

    ``conn`` must be an asyncpg Connection (already acquired from a pool).
    """
    now = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # 1. Identity -- items table
    # ------------------------------------------------------------------
    # Column drift: items only has id, user_id, title, category, condition,
    # attributes_json, canonical_key, created_at on this schema. The other
    # fields (grade, graded_by, sealed, taxonomy_version, subtype_id,
    # collections, images) live elsewhere or don't exist yet — pull what we
    # have and default the rest so the dossier renders.
    # items column names on this schema: attrs (jsonb, not attributes_json),
    # no updated_at. Selecting what actually exists so the query doesn't crash.
    item_row = await conn.fetchrow(
        """
        SELECT id, user_id, title, category, condition, attrs AS attributes_json,
               canonical_key, created_at, image_url
        FROM public.items
        WHERE id = $1::uuid AND user_id = $2::uuid
        """,
        item_id,
        user_id,
    )

    if item_row is None:
        raise ValueError("Item not found or not owned by user")

    canonical_key: Optional[str] = item_row.get("canonical_key")

    attributes = _parse_json_field(item_row["attributes_json"])
    collections_list: List[Any] = []  # `collections` column not present on items; left empty

    # image_url column holds the single user-uploaded photo; no separate images array
    first_image_url: Optional[str] = item_row.get("image_url")
    images_raw = [first_image_url] if first_image_url else []

    # Pull grading fields from attributes_json if present (kept as dossier
    # fields for back-compat with the response schema).
    attrs_dict = attributes if isinstance(attributes, dict) else {}

    identity = {
        "name": item_row["title"],
        "category": item_row["category"],
        "condition": item_row["condition"],
        "grade": attrs_dict.get("grade"),
        "graded_by": attrs_dict.get("graded_by"),
        "sealed": attrs_dict.get("sealed"),
        "subtype_id": attrs_dict.get("subtype_id"),
        "taxonomy_version": attrs_dict.get("taxonomy_version"),
        "attributes": attributes or {},
        "image_url": first_image_url,
        "created_at": _ts(item_row.get("created_at")),
        "updated_at": _ts(item_row.get("updated_at")) if item_row.get("updated_at") else None,
    }

    # Photos list from the images JSONB array + S3 object_pointers
    photos: List[str] = []
    if isinstance(images_raw, list):
        for img in images_raw:
            if isinstance(img, str) and img and img not in photos:
                photos.append(img)

    try:
        pointer_rows = await conn.fetch(
            """
            SELECT s3_key FROM public.object_pointers
            WHERE related_item_id = $1 AND content_type LIKE 'image/%'
            ORDER BY created_at ASC
            """,
            item_id,
        )
        for pr in pointer_rows:
            if pr["s3_key"] and pr["s3_key"] not in photos:
                photos.append(pr["s3_key"])
    except Exception as e:
        logger.warning("[dossier] Could not fetch object_pointers: %s", e)

    # ------------------------------------------------------------------
    # 2. Valuation -- price_predictions
    # ------------------------------------------------------------------
    valuation: Dict[str, Any] = {}
    try:
        # Column drift fix 2026-04-19: price_predictions has item_ref (text)
        # and generated_at, not item_id (uuid) and asof. Look up by the
        # user's canonical catalog key.
        pred_row = await conn.fetchrow(
            """
            SELECT q10, q50, q90, conf_score, explanation,
                   evidence_summary, evidence_hit_ids, generated_at
            FROM public.price_predictions
            WHERE item_ref = $1
            ORDER BY generated_at DESC
            LIMIT 1
            """,
            canonical_key,
        ) if canonical_key else None
        if pred_row:
            valuation = {
                "q10": float(pred_row["q10"]) if pred_row["q10"] is not None else None,
                "q50": float(pred_row["q50"]) if pred_row["q50"] is not None else None,
                "q90": float(pred_row["q90"]) if pred_row["q90"] is not None else None,
                "confidence_score": (
                    float(pred_row["conf_score"])
                    if pred_row["conf_score"] is not None
                    else None
                ),
                "explanation": pred_row.get("explanation"),
                "evidence_summary": _parse_json_field(pred_row.get("evidence_summary")),
                "evidence_hit_ids": _parse_json_field(pred_row.get("evidence_hit_ids")) or [],
                "predicted_at": _ts(pred_row.get("generated_at")),
            }
    except Exception as e:
        logger.warning("[dossier] Could not fetch price_predictions: %s", e)

    # ------------------------------------------------------------------
    # 3. Provenance -- item_provenance_events
    # ------------------------------------------------------------------
    provenance: List[Dict[str, Any]] = []
    try:
        prov_rows = await conn.fetch(
            """
            SELECT id, event_type, note, source, metadata, created_at
            FROM public.item_provenance_events
            WHERE item_id = $1
            ORDER BY created_at ASC
            """,
            item_id,
        )
        for row in prov_rows:
            provenance.append({
                "event_id": str(row["id"]),
                "event_type": row["event_type"],
                "note": row["note"],
                "source": row["source"],
                "metadata": _parse_json_field(row["metadata"]) or {},
                "timestamp": _ts(row["created_at"]),
            })
    except Exception as e:
        logger.warning("[dossier] Could not fetch provenance events: %s", e)

    # ------------------------------------------------------------------
    # 4. Price history -- price_history
    # ------------------------------------------------------------------
    price_history: List[Dict[str, Any]] = []
    try:
        # Look up by canonical catalog key, not user's items.id UUID (2026-04-19 fix)
        ph_rows = await conn.fetch(
            """
            SELECT price_q50, price_q10, price_q90, source, snapshot_at
            FROM public.price_history
            WHERE item_ref = $1
            ORDER BY snapshot_at ASC
            """,
            canonical_key,
        ) if canonical_key else []
        for row in ph_rows:
            price_history.append({
                "price": float(row["price_q50"]) if row["price_q50"] is not None else None,
                "price_q10": float(row["price_q10"]) if row["price_q10"] is not None else None,
                "price_q90": float(row["price_q90"]) if row["price_q90"] is not None else None,
                "currency": "EUR",
                "source": row.get("source"),
                "recorded_at": _ts(row.get("snapshot_at")),
            })
    except Exception as e:
        logger.warning("[dossier] Could not fetch price_history: %s", e)

    # ------------------------------------------------------------------
    # 5. Market comparables -- market_hits
    # ------------------------------------------------------------------
    market_comps: List[Dict[str, Any]] = []
    try:
        # Use normalized_key ILIKE to find comps matching this item's title
        item_title = item_row.get("title") or ""
        search_key = f"%{item_title[:40]}%" if item_title else "%"
        mh_rows = await conn.fetch(
            """
            SELECT title, price, currency, provider, ended_at, url, condition
            FROM public.market_hits
            WHERE normalized_key ILIKE $1
              AND (is_listing IS NOT TRUE)
            ORDER BY ended_at DESC NULLS LAST
            LIMIT 10
            """,
            search_key,
        )
        from app.lib.affiliate import build_affiliate_url

        for row in mh_rows:
            raw_url = row.get("url") or ""
            source = row.get("provider") or ""
            aff_url, _aff_source = build_affiliate_url(raw_url, source)
            market_comps.append({
                "title": row["title"],
                "price": float(row["price"]) if row["price"] is not None else None,
                "currency": row.get("currency", "EUR"),
                "source": source,
                "sold_date": _ts(row.get("ended_at")),
                "url": raw_url,
                "affiliate_url": aff_url if aff_url != raw_url else None,
                "condition": row.get("condition"),
            })
    except Exception as e:
        logger.warning("[dossier] Could not fetch market_hits: %s", e)

    # ------------------------------------------------------------------
    # 6. Compute meta fields
    # ------------------------------------------------------------------
    authenticity_signals = _compute_authenticity_signals(provenance)

    completeness = _compute_completeness(
        has_photo=len(photos) > 0,
        has_provenance=len(provenance) > 0,
        has_prediction=bool(valuation),
        has_attributes=bool(attributes),
        has_comps=len(market_comps) > 0,
    )

    return ItemDossier(
        item_id=item_id,
        generated_at=now.isoformat(),
        identity=identity,
        valuation=valuation,
        provenance=provenance,
        price_history=price_history,
        market_comps=market_comps,
        photos=photos,
        collections=collections_list,
        authenticity_signals=authenticity_signals,
        completeness_score=completeness,
    )
