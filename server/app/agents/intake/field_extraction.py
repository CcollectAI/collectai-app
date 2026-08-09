"""
Vision/OpenAI field extraction and barcode lookup for the intake pipeline.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from .helpers import _price_band_to_dict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Barcode lookup cascade
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Vision classification
# ---------------------------------------------------------------------------

async def _vision_classify_internal(
    image_bytes: bytes,
    filename: str = "",
    category_hint: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """
    Run the 2-tier vision classifier and return structured results.

    `category_hint` is the category the user already chose in the intake UI
    (user_hints["category"]). It narrows the extraction prompt to that
    category's field list and enables the B3.2b confusion hint. It is
    allow-listed against ALL_CATEGORIES inside build_system_prompt, so an
    arbitrary user string cannot reach the LLM prompt.
    """
    try:
        from app.ml.vision_classifier import classify_image

        result = await classify_image(image_bytes, filename, category_hint)

        # "clip" is gone (the fal.ai tier was removed 2026-07-27) but stays in
        # the map: historical rows in vision_queue.classification_method still
        # carry it, and dropping the key would silently relabel them heuristic.
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
            "defect_annotations": result.attributes.get("defect_annotations", []),
            "suggested_grade": result.attributes.get("suggested_grade"),
        }
    except Exception as e:
        logger.warning("Vision classification failed in intake agent: %s", e)
        return None
