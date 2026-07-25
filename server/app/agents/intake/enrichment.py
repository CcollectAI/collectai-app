"""
Price enrichment and URL import for the intake pipeline.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse

from app.lib.db_helpers import get_db_pool

from .helpers import (
    IntakeResult,
    _fire_catalog_miss,
    _lookup_taxonomy_corrections,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Price estimation
# ---------------------------------------------------------------------------

async def _estimate_price(
    category_id: Optional[str],
    name: Optional[str],
    pool,
    catalog_match_key: Optional[str] = None,
) -> tuple[Optional[float], Optional[str], Optional[dict[str, Any]]]:
    """
    Estimate price from multiple sources.

    When catalog_match_key is provided, uses it for precise market_hits
    lookup instead of fuzzy name matching.

    Returns (estimated_price, price_source, price_band_dict).
    """
    if not pool or not category_id or not name:
        return None, None, None

    # Use catalog_match_key for precise lookup, fall back to fuzzy name
    search_key = catalog_match_key if catalog_match_key else name[:40]

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
                  AND (is_listing IS NOT TRUE)
                  -- Partition prune: intake price-estimate from market
                  -- hits only needs recent comps; 180d matches the
                  -- model decay tail. Without this filter every intake
                  -- without a barcode walks all monthly partitions.
                  AND seen_at > now() - interval '180 days'
                ORDER BY ended_at DESC NULLS LAST
                LIMIT 20
                """,
                f"%{search_key}%",
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
                JOIN items i ON i.canonical_ref = pp.item_ref
                WHERE i.category = $1
                  AND i.title ILIKE $2
                ORDER BY pp.generated_at DESC
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

    pool = get_db_pool()

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

        # --- Step 1: Smart scrape (Crawl4AI first, Firecrawl fallback) ---
        try:
            from app.lib.smart_scrape import smart_scrape

            scrape_result = await smart_scrape(
                url,
                formats=["markdown", "extract"],
                extract_schema=COLLECTIBLE_EXTRACT_SCHEMA,
            )

            if not scrape_result:
                result.rationale.append("No scraper returned data for URL")
                result.identification_method = "url_import_failed"
                return result

            # Prefer structured extraction; fall back to markdown metadata
            extracted = scrape_result.get("extract")
            if extracted:
                result.rationale.append("Successfully extracted structured data via scraper")
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
            result.rationale.append("Scraper client not available")
            result.identification_method = "url_import_failed"
            return result
        except Exception as e:
            logger.error("URL import scrape error: %s", e, exc_info=True)
            result.rationale.append("Scrape extraction failed")
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
