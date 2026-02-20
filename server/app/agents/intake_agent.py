"""
Intake Agent for CollectAI.

Orchestrates the Snap-to-Logged flow:
  1. Barcode lookup (local catalog -> Open Library -> Google Books)
  2. Vision classification (CLIP -> OpenAI Vision -> heuristic)
  3. Taxonomy resolution with correction pattern awareness
  4. Price estimation from market_hits / price_predictions / catalog

Returns a unified IntakeResult with full provenance of how the item was
identified, categorised, and priced.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse

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

    # Rationale trail
    rationale: list[str] = field(default_factory=list)

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
            "rationale": self.rationale,
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


def _get_db_pool():
    """Get database pool if available."""
    try:
        from app.db import get_pool
        return get_pool()
    except Exception as e:
        logger.debug("Intake agent: DB pool not available: %s", e)
        return None


async def _barcode_lookup_internal(
    barcode: str,
    barcode_type: Optional[str],
    pool,
) -> Optional[dict[str, Any]]:
    """
    Run the 3-tier barcode lookup cascade without going through HTTP.

    Returns a dict with keys:
      title, category_id, subtype_id, attributes, image_url,
      rationale, price_band, identification_method
    or None if nothing was found.
    """
    from app.features.barcode_lookup_router import (
        _lookup_local_catalog,
        _lookup_open_library,
        _lookup_google_books,
        _lookup_market_price,
        _classify_category,
        _is_isbn,
    )

    rationale: list[str] = []
    barcode_clean = barcode.strip()

    # --- Step 1: Local catalog ---
    local = await _lookup_local_catalog(barcode_clean, pool)
    if local:
        rationale.append("Matched in local catalog (category_items)")
        category = local.get("category")
        price_band = None
        if category and local.get("title"):
            price_band = await _lookup_market_price(category, local["title"], pool)
            if price_band:
                rationale.append("Price from recent market data")

        return {
            "title": local.get("title"),
            "category_id": category,
            "subtype_id": local.get("rarity"),
            "attributes": {
                "brand": local.get("brand"),
                "isbn": barcode_clean if _is_isbn(barcode_clean) else None,
                "item_key": local.get("item_key"),
                "source": "local_catalog",
            },
            "image_url": local.get("image_url"),
            "rationale": rationale,
            "price_band": _price_band_to_dict(price_band) if price_band else None,
            "identification_method": "barcode_catalog",
        }

    # --- Step 2 & 3: External ISBN lookup ---
    code_type_lower = (barcode_type or "").lower()
    is_isbn = _is_isbn(barcode_clean) or code_type_lower in ("isbn", "ean13")
    book_data: Optional[dict] = None

    if is_isbn:
        isbn_clean = re.sub(r"[\s-]", "", barcode_clean)

        book_data = await _lookup_open_library(isbn_clean)
        if book_data:
            rationale.append(f"Found via Open Library (ISBN: {isbn_clean})")
            ident_method = "barcode_openlibrary"
        else:
            book_data = await _lookup_google_books(isbn_clean)
            if book_data:
                rationale.append(f"Found via Google Books (ISBN: {isbn_clean})")
                ident_method = "barcode_google"

    if book_data:
        category_id = _classify_category(
            publisher=book_data.get("publisher", ""),
            title=book_data.get("title", ""),
            subjects=book_data.get("subjects", []),
        )

        if category_id:
            rationale.append(f"Classified as '{category_id}' from publisher/subject metadata")
        else:
            rationale.append("Could not auto-classify category from metadata")

        attributes: dict[str, Any] = {
            "isbn": book_data.get("isbn"),
            "publisher": book_data.get("publisher"),
            "authors": book_data.get("authors", []),
            "publish_date": book_data.get("publish_date"),
            "pages": book_data.get("pages"),
            "source": book_data.get("source"),
        }

        price_band = None
        if category_id and book_data.get("title"):
            price_band = await _lookup_market_price(
                category_id, book_data["title"], pool,
            )
            if price_band:
                rationale.append("Price estimated from recent market sales")

        return {
            "title": book_data.get("title"),
            "category_id": category_id,
            "subtype_id": None,
            "attributes": attributes,
            "image_url": book_data.get("cover_url"),
            "rationale": rationale,
            "price_band": _price_band_to_dict(price_band) if price_band else None,
            "identification_method": ident_method,  # type: ignore[possibly-undefined]
        }

    return None


async def _vision_classify_internal(
    image_bytes: bytes,
    filename: str = "",
) -> Optional[dict[str, Any]]:
    """
    Run the 3-tier vision classifier and return structured results.
    """
    try:
        from app.ml.vision_classifier import classify_image

        result = await classify_image(image_bytes, filename)

        method_map = {
            "clip": "vision_clip",
            "openai_vision": "vision_openai",
            "heuristic": "vision_heuristic",
        }
        ident_method = method_map.get(result.classification_method, "vision_heuristic")

        return {
            "category_id": result.category_id,
            "category_confidence": result.category_confidence,
            "condition": result.condition,
            "condition_confidence": result.condition_confidence,
            "suggested_name": result.suggested_name,
            "attributes": result.attributes,
            "identification_method": ident_method,
        }
    except Exception as e:
        logger.warning("Vision classification failed in intake agent: %s", e)
        return None


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
            rows = await conn.fetch(
                """
                SELECT
                    from_category,
                    to_category,
                    COUNT(*) AS frequency,
                    COUNT(DISTINCT user_id) AS user_count
                FROM taxonomy_corrections
                WHERE from_category = $1
                GROUP BY from_category, to_category
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


async def _estimate_price(
    category_id: Optional[str],
    name: Optional[str],
    pool,
) -> tuple[Optional[float], Optional[str], Optional[dict[str, Any]]]:
    """
    Estimate price from multiple sources.

    Returns (estimated_price, price_source, price_band_dict).
    """
    if not pool or not category_id or not name:
        return None, None, None

    # Source 1: market_hits (recent sold prices)
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT price, currency
                FROM market_hits
                WHERE normalized_key ILIKE $1
                  AND price IS NOT NULL
                  AND price > 0
                ORDER BY ended_at DESC NULLS LAST
                LIMIT 20
                """,
                f"%{name[:40]}%",
            )

            if rows and len(rows) >= 3:
                prices = sorted([float(r["price"]) for r in rows])
                n = len(prices)
                q10_idx = max(0, int(n * 0.1))
                q50_idx = int(n * 0.5)
                q90_idx = min(n - 1, int(n * 0.9))

                band = {
                    "q10": round(prices[q10_idx], 2),
                    "q50": round(prices[q50_idx], 2),
                    "q90": round(prices[q90_idx], 2),
                    "confidence": min(0.9, 0.3 + n * 0.03),
                    "currency": rows[0]["currency"] or "EUR",
                }
                return band["q50"], "market_hits", band
    except Exception as e:
        logger.debug("market_hits price lookup error: %s", e)

    # Source 2: price_predictions table (join through items to filter by category + name)
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT pp.q10, pp.q50, pp.q90, pp.conf_score
                FROM price_predictions pp
                JOIN items i ON i.id = pp.item_id
                WHERE i.category = $1
                  AND i.title ILIKE $2
                ORDER BY pp.asof DESC
                LIMIT 1
                """,
                category_id,
                f"%{name[:40]}%",
            )
            if row and row["q50"] is not None:
                band = {
                    "q10": round(float(row["q10"] or 0), 2),
                    "q50": round(float(row["q50"]), 2),
                    "q90": round(float(row["q90"] or 0), 2),
                    "confidence": round(float(row["conf_score"] or 0.5), 4),
                    "currency": "EUR",
                }
                return band["q50"], "model", band
    except Exception as e:
        logger.debug("price_predictions lookup error: %s", e)

    # Source 3: catalog reference price
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT title, notes
                FROM category_items
                WHERE category = $1
                  AND title ILIKE $2
                LIMIT 1
                """,
                category_id,
                f"%{name[:40]}%",
            )
            if row and row.get("notes"):
                # Try to extract a price from the notes field
                price_match = re.search(r"[\d]+\.?\d*", row["notes"])
                if price_match:
                    val = float(price_match.group())
                    if 0 < val < 100_000:
                        return val, "catalog", None
    except Exception as e:
        logger.debug("catalog price lookup error: %s", e)

    return None, None, None


# ---------------------------------------------------------------------------
# Catalog Learning — log misses (best-effort, fire-and-forget)
# ---------------------------------------------------------------------------

def _fire_catalog_miss(**kwargs) -> None:
    """Fire-and-forget wrapper for _log_catalog_miss (non-blocking)."""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_log_catalog_miss(**kwargs))
    except RuntimeError:
        pass  # No running event loop — skip silently


async def _log_catalog_miss(
    user_id: Optional[str],
    source: str,
    input_data: dict[str, Any],
    suggested_name: Optional[str] = None,
) -> None:
    """Best-effort insert into catalog_suggestions for learning pipeline."""
    try:
        from app.config import CATALOG_LEARNING_ENABLED
        if not CATALOG_LEARNING_ENABLED or not user_id:
            return

        import json
        pool = _get_db_pool()
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


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def process_intake(
    image_bytes: Optional[bytes] = None,
    barcode: Optional[str] = None,
    barcode_type: Optional[str] = None,
    user_hints: Optional[dict[str, Any]] = None,
    user_id: Optional[str] = None,
    conn=None,
) -> IntakeResult:
    """
    Unified intake orchestrator.

    Flow:
      1. If barcode provided, try barcode lookup cascade
      2. If no barcode or barcode failed, try vision classification
      3. Resolve taxonomy with correction pattern awareness
      4. Estimate price from available sources
      5. Apply user hints (override if provided)

    Args:
        image_bytes: Raw image bytes for vision classification
        barcode: Scanned barcode string
        barcode_type: Barcode format (ean13, upc_a, isbn, etc.)
        user_hints: User-provided overrides (category, name, condition, etc.)
        conn: Database connection (unused, pool is fetched internally)

    Returns:
        IntakeResult with full provenance
    """
    result = IntakeResult()
    result.barcode = barcode
    result.barcode_type = barcode_type
    hints = user_hints or {}

    pool = _get_db_pool()
    barcode_found = False
    barcode_partial = False

    try:
        # -----------------------------------------------------------------
        # Step 1: Barcode lookup
        # -----------------------------------------------------------------
        if barcode:
            result.rationale.append(f"Barcode provided: {barcode} (type: {barcode_type or 'auto'})")

            barcode_result = await _barcode_lookup_internal(barcode, barcode_type, pool)
            if barcode_result:
                result.name = barcode_result.get("title")
                result.category_id = barcode_result.get("category_id")
                result.subtype_id = barcode_result.get("subtype_id")
                result.attributes = barcode_result.get("attributes", {})
                result.image_url = barcode_result.get("image_url")
                result.identification_method = barcode_result.get(
                    "identification_method", "barcode_catalog"
                )
                result.rationale.extend(barcode_result.get("rationale", []))

                if barcode_result.get("price_band"):
                    result.price_band = barcode_result["price_band"]
                    result.estimated_price = barcode_result["price_band"].get("q50")
                    result.price_source = "market_hits"

                barcode_found = True

                # Check if it's a partial match (name but no category)
                if result.name and not result.category_id:
                    barcode_partial = True
                    result.rationale.append(
                        "Barcode found name but no category - supplementing with vision"
                    )

                # High confidence if both name and category found
                if result.name and result.category_id:
                    result.category_confidence = 0.9
                    result.taxonomy_confidence = 0.9
            else:
                result.rationale.append("Barcode not found in any source")

        # -----------------------------------------------------------------
        # Step 2: Vision classification (if no barcode or partial match)
        # -----------------------------------------------------------------
        if (not barcode_found or barcode_partial) and image_bytes:
            result.rationale.append("Attempting vision classification")

            vision_result = await _vision_classify_internal(image_bytes)

            if vision_result:
                vision_cat = vision_result.get("category_id")
                vision_conf = vision_result.get("category_confidence", 0.0)
                vision_method = vision_result.get("identification_method", "vision_heuristic")

                if barcode_partial:
                    # Supplement: use vision for category only
                    if vision_cat and vision_conf > 0.3:
                        result.category_id = vision_cat
                        result.category_confidence = vision_conf
                        result.identification_method = f"{result.identification_method}+{vision_method}"
                        result.rationale.append(
                            f"Vision supplemented category: {vision_cat} "
                            f"(confidence: {vision_conf:.2f})"
                        )
                else:
                    # Full vision result
                    result.category_id = vision_cat
                    result.category_confidence = vision_conf
                    result.identification_method = vision_method
                    result.name = vision_result.get("suggested_name") or result.name

                    # Merge vision attributes
                    vision_attrs = vision_result.get("attributes", {})
                    result.attributes.update(vision_attrs)

                    condition = vision_result.get("condition")
                    if condition:
                        result.attributes["condition"] = condition
                        result.attributes["condition_confidence"] = vision_result.get(
                            "condition_confidence", 0.0
                        )

                    result.rationale.append(
                        f"Vision classified as {vision_cat} via {vision_method} "
                        f"(confidence: {vision_conf:.2f})"
                    )
            else:
                result.rationale.append("Vision classification returned no result")

        elif not barcode_found and not image_bytes:
            result.rationale.append("No barcode or image provided - manual entry required")
            result.identification_method = "manual"

        # -----------------------------------------------------------------
        # Step 3: Taxonomy resolution
        # -----------------------------------------------------------------
        if result.category_id:
            result.taxonomy_confidence = result.category_confidence

            # Check for correction patterns
            corrections = await _lookup_taxonomy_corrections(result.category_id, pool)
            if corrections:
                result.suggested_corrections = corrections
                result.rationale.append(
                    f"Found {len(corrections)} taxonomy correction pattern(s) "
                    f"for category '{result.category_id}'"
                )

        # -----------------------------------------------------------------
        # Step 4: Price estimation (if not already set from barcode)
        # -----------------------------------------------------------------
        if result.estimated_price is None and result.category_id and result.name:
            price, source, band = await _estimate_price(
                result.category_id, result.name, pool,
            )
            if price is not None:
                result.estimated_price = price
                result.price_source = source
                if band:
                    result.price_band = band
                result.rationale.append(f"Price estimated from {source}: EUR {price:.2f}")

        # -----------------------------------------------------------------
        # Step 5: Apply user hints (trust user over automation)
        # -----------------------------------------------------------------
        if hints.get("category"):
            prev_cat = result.category_id
            result.category_id = hints["category"]
            result.category_confidence = 1.0
            result.taxonomy_confidence = 1.0
            if prev_cat and prev_cat != hints["category"]:
                result.rationale.append(
                    f"User overrode category from '{prev_cat}' to '{hints['category']}'"
                )
            else:
                result.rationale.append(f"User specified category: {hints['category']}")

        if hints.get("name"):
            result.name = hints["name"]
            result.rationale.append(f"User specified name: {hints['name']}")

        if hints.get("condition"):
            result.attributes["condition"] = hints["condition"]
            result.rationale.append(f"User specified condition: {hints['condition']}")

        # Timestamp the intake
        result.attributes["intake_timestamp"] = datetime.now(timezone.utc).isoformat()

        # Mark as catalog miss if no category or low confidence
        # (check BEFORE user hints override, but after all automated steps)
        if not result.category_id or result.category_confidence < 0.3:
            result.catalog_miss = True
            miss_source = "barcode" if barcode else ("photo" if image_bytes else "manual")
            _fire_catalog_miss(
                user_id=user_id,
                source=miss_source,
                input_data={"barcode": barcode, "barcode_type": barcode_type, "name": result.name},
                suggested_name=result.name,
            )

    except Exception as e:
        logger.error("Intake agent error: %s", e, exc_info=True)
        result.rationale.append(f"Intake processing error - partial result returned")

    return result


# ---------------------------------------------------------------------------
# URL Import
# ---------------------------------------------------------------------------

# Extraction schema for Firecrawl structured extraction
COLLECTIBLE_EXTRACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "price": {"type": "number"},
        "currency": {"type": "string"},
        "condition": {"type": "string"},
        "category_hint": {"type": "string"},
        "image_urls": {"type": "array", "items": {"type": "string"}},
        "seller_name": {"type": "string"},
        "listing_date": {"type": "string"},
        "description_summary": {"type": "string"},
        "attributes": {
            "type": "object",
            "properties": {
                "edition": {"type": "string"},
                "rarity": {"type": "string"},
                "grade": {"type": "string"},
                "sealed": {"type": "boolean"},
                "brand": {"type": "string"},
                "set_name": {"type": "string"},
                "artist": {"type": "string"},
            },
        },
    },
}

# URL patterns we recognize for direct extraction
_SUPPORTED_URL_PATTERNS: list[tuple[str, str]] = [
    (r"ebay\.(com|co\.uk|de|fr|it|es|com\.au)/itm/", "ebay"),
    (r"jp\.mercari\.com/", "mercari_jp"),
    (r"mercari\.com/", "mercari"),
    (r"stockx\.com/", "stockx"),
    (r"tcgplayer\.com/product/", "tcgplayer"),
    (r"bricklink\.com/v2/catalog/", "bricklink"),
    (r"myfigurecollection\.net/item/", "mfc"),
    (r"ktown4u\.com/", "ktown4u"),
    (r"weverse\.io/", "weverse"),
]

# FX rate fallback
_FX_TO_EUR: dict[str, float] = {
    "USD": 0.92,
    "GBP": 1.17,
    "JPY": 0.0061,
    "CAD": 0.68,
    "AUD": 0.60,
}


def _detect_url_source(url: str) -> Optional[str]:
    """Detect the marketplace source from a URL."""
    for pattern, source in _SUPPORTED_URL_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return source
    return None


def _convert_price_to_eur(price: Optional[float], currency: Optional[str]) -> Optional[float]:
    """Convert a price to EUR if needed."""
    if price is None:
        return None
    if not currency or currency.upper() == "EUR":
        return price
    rate = _FX_TO_EUR.get(currency.upper())
    if rate:
        return round(price * rate, 2)
    return price


def _guess_category_from_url(url: str, extracted: dict[str, Any]) -> Optional[str]:
    """Guess the collectible category from URL and extracted data."""
    url_lower = url.lower()
    hint = (extracted.get("category_hint") or "").lower()
    title = (extracted.get("title") or "").lower()
    combined = f"{url_lower} {hint} {title}"

    # Category detection patterns (subset of newsletter_scraper patterns)
    patterns: list[tuple[str, str]] = [
        (r"pokemon|pokémon|pikachu|charizard", "pokemon"),
        (r"magic.*gathering|mtg\b", "mtg"),
        (r"yu-?gi-?oh|yugioh", "yugioh"),
        (r"lorcana", "lorcana"),
        (r"funko|pop!?\s*vinyl", "funko"),
        (r"nendoroid|figma|scale\s*figure|good\s*smile", "anime_figures"),
        (r"\blego\b|bricklink", "lego"),
        (r"gunpla|gundam", "gunpla"),
        (r"warhammer|40k|age\s*of\s*sigmar", "warhammer"),
        (r"bts\b|blackpink|stray\s*kids|k-?pop|weverse|hybe|ktown4u|twice|seventeen", "kpop_merch"),
        (r"taylor\s*swift|swiftie|eras\s*tour", "taylor_swift"),
        (r"hot\s*wheels|hotwheels|diecast|matchbox", "diecast"),
        (r"steelbook|criterion|arrow\s*video", "bluray_steelbook"),
        (r"\bmanga\b", "manga"),
        (r"retro.*game|nes\b|snes\b|game\s*boy", "retro_games"),
        (r"one\s*piece|luffy", "one_piece"),
        (r"sports.*card|topps|panini|prizm", "sportscards"),
        (r"loungefly", "loungefly"),
        (r"disney", "disney"),
        (r"stockx", "designer_toys"),
        (r"myfigurecollection", "anime_figures"),
        (r"keycap|mechanical\s*keyboard", "keycaps"),
        (r"vtuber|hololive", "vtuber"),
        (r"hot\s*toys|sideshow", "hot_toys"),
        (r"lightstick|army\s*bomb", "kpop_lightsticks"),
    ]

    for pattern, cat_id in patterns:
        if re.search(pattern, combined, re.IGNORECASE):
            return cat_id

    return None


async def process_url_import(
    url: str,
    user_hints: Optional[dict[str, Any]] = None,
    user_id: Optional[str] = None,
) -> IntakeResult:
    """
    Import a collectible item from a marketplace URL.

    Flow:
      1. Firecrawl /scrape with collectible extraction schema
      2. Map extracted fields to taxonomy
      3. Run taxonomy resolver for corrections
      4. Add price hints
      5. Apply user overrides

    Args:
        url: Marketplace listing URL.
        user_hints: Optional user-provided overrides.

    Returns:
        IntakeResult with full provenance.
    """
    result = IntakeResult()
    result.identification_method = "url_import"
    hints = user_hints or {}

    pool = _get_db_pool()

    try:
        # Validate URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            result.rationale.append(f"Invalid URL: {url}")
            return result

        source = _detect_url_source(url)
        result.rationale.append(f"URL provided: {url}")
        if source:
            result.rationale.append(f"Detected marketplace: {source}")
        else:
            result.rationale.append("Unknown marketplace - attempting generic extraction")

        # --- Step 1: Firecrawl extraction ---
        try:
            from app.lib.firecrawl_client import scrape_url, configured

            if not configured():
                result.rationale.append("Firecrawl not configured (no API key) - cannot extract from URL")
                result.identification_method = "url_import_failed"
                return result

            # Single call with both formats — avoids double HTTP request
            scrape_result = await scrape_url(
                url,
                formats=["markdown", "extract"],
                extract_schema=COLLECTIBLE_EXTRACT_SCHEMA,
            )

            if not scrape_result:
                result.rationale.append("Failed to scrape URL - no data returned")
                result.identification_method = "url_import_failed"
                return result

            # Prefer structured extraction; fall back to markdown metadata
            extracted = scrape_result.get("extract")
            if extracted:
                result.rationale.append("Successfully extracted structured data via Firecrawl")
            else:
                markdown = scrape_result.get("markdown", "")
                metadata = scrape_result.get("metadata", {})
                if markdown or metadata:
                    extracted = {
                        "title": metadata.get("title") or metadata.get("og:title"),
                        "description_summary": markdown[:500],
                        "image_urls": [],
                    }
                    og_image = metadata.get("og:image")
                    if og_image:
                        extracted["image_urls"] = [og_image]
                    result.rationale.append("Structured extraction empty, fell back to page metadata")
                else:
                    result.rationale.append("Scrape returned no usable data")
                    result.identification_method = "url_import_failed"
                    return result

        except ImportError:
            result.rationale.append("Firecrawl client not available")
            result.identification_method = "url_import_failed"
            return result
        except Exception as e:
            logger.error("URL import Firecrawl error: %s", e, exc_info=True)
            result.rationale.append("Firecrawl extraction failed")
            result.identification_method = "url_import_failed"
            return result

        # --- Step 2: Map extracted fields ---
        result.name = extracted.get("title")
        result.attributes["source_url"] = url
        result.attributes["source_marketplace"] = source or "unknown"

        if extracted.get("image_urls"):
            result.image_url = extracted["image_urls"][0]

        if extracted.get("seller_name"):
            result.attributes["seller_name"] = extracted["seller_name"]
        if extracted.get("listing_date"):
            result.attributes["listing_date"] = extracted["listing_date"]
        if extracted.get("description_summary"):
            result.attributes["description_summary"] = extracted["description_summary"][:500]
        if extracted.get("condition"):
            result.attributes["condition"] = extracted["condition"]

        # Merge extracted attributes
        extra_attrs = extracted.get("attributes") or {}
        for key, val in extra_attrs.items():
            if val is not None and val != "":
                result.attributes[key] = val

        # Price from extraction
        raw_price = extracted.get("price")
        raw_currency = extracted.get("currency", "EUR")
        if raw_price is not None:
            eur_price = _convert_price_to_eur(raw_price, raw_currency)
            if eur_price:
                result.estimated_price = eur_price
                result.price_source = f"listing_{source or 'web'}"
                result.rationale.append(
                    f"Listing price: {raw_currency or 'EUR'} {raw_price} "
                    f"(EUR {eur_price:.2f})"
                )

        # --- Step 3: Category resolution ---
        category = _guess_category_from_url(url, extracted)
        if category:
            result.category_id = category
            result.category_confidence = 0.70
            result.taxonomy_confidence = 0.70
            result.rationale.append(f"Auto-classified category: {category}")

            # Check for correction patterns
            corrections = await _lookup_taxonomy_corrections(category, pool)
            if corrections:
                result.suggested_corrections = corrections
                result.rationale.append(
                    f"Found {len(corrections)} taxonomy correction pattern(s)"
                )

        # --- Step 4: Price hints from marketplace agent ---
        if result.estimated_price is None and result.category_id and result.name:
            price, source_str, band = await _estimate_price(
                result.category_id, result.name, pool,
            )
            if price is not None:
                result.estimated_price = price
                result.price_source = source_str
                if band:
                    result.price_band = band
                result.rationale.append(f"Price estimated from {source_str}: EUR {price:.2f}")

        # --- Step 5: Apply user hints ---
        if hints.get("category"):
            prev_cat = result.category_id
            result.category_id = hints["category"]
            result.category_confidence = 1.0
            result.taxonomy_confidence = 1.0
            if prev_cat and prev_cat != hints["category"]:
                result.rationale.append(
                    f"User overrode category from '{prev_cat}' to '{hints['category']}'"
                )

        if hints.get("name"):
            result.name = hints["name"]
            result.rationale.append(f"User specified name: {hints['name']}")

        if hints.get("condition"):
            result.attributes["condition"] = hints["condition"]
            result.rationale.append(f"User specified condition: {hints['condition']}")

        result.attributes["intake_timestamp"] = datetime.now(timezone.utc).isoformat()

        # Mark as catalog miss if no category or low confidence
        if not result.category_id or result.category_confidence < 0.3:
            result.catalog_miss = True
            _fire_catalog_miss(
                user_id=user_id,
                source="url",
                input_data={"url": url, "name": result.name},
                suggested_name=result.name,
            )

    except Exception as e:
        logger.error("URL import error: %s", e, exc_info=True)
        result.rationale.append("URL import processing error - partial result returned")

    return result
