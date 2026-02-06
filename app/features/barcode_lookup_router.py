"""
Barcode / ISBN Lookup Router

Endpoints:
- POST /barcode/lookup - Look up a product by barcode or ISBN

Lookup cascade:
  1. Local catalog (category_items table) — fast, no network
  2. Open Library API (free, no key) — books, manga, art books
  3. Google Books API (free tier) — fallback for ISBNs
  4. Category classifier — maps publisher/subject to our 36 categories
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/barcode", tags=["barcode"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_db_pool():
    """Get database pool if available."""
    try:
        from app.db import get_pool
        return get_pool()
    except Exception as e:
        logger.debug(f"DB pool not available: {e}")
        return None


# ---------------------------------------------------------------------------
# Category classification rules
# ---------------------------------------------------------------------------

# Publisher → category mapping (case-insensitive substring match)
PUBLISHER_CATEGORY_MAP: list[tuple[str, str]] = [
    # Warhammer / Games Workshop
    ("games workshop", "warhammer"),
    ("black library", "warhammer"),
    ("citadel", "warhammer"),
    ("forge world", "warhammer"),
    # Manga publishers
    ("viz media", "manga"),
    ("viz llc", "manga"),
    ("kodansha", "manga"),
    ("shogakukan", "manga"),
    ("shueisha", "manga"),
    ("seven seas", "manga"),
    ("yen press", "manga"),
    ("dark horse manga", "manga"),
    ("square enix", "manga"),
    ("vertical", "manga"),
    ("tokyopop", "manga"),
    # One Piece (specific before generic manga)
    ("one piece", "one_piece"),
    # Pokemon
    ("pokemon company", "pokemon"),
    ("the pokémon company", "pokemon"),
    # LEGO
    ("lego", "lego"),
    # Nintendo
    ("nintendo", "nintendo_merch"),
    # Disney / Ghibli
    ("disney", "disney"),
    ("studio ghibli", "ghibli"),
    ("ghibli", "ghibli"),
    # Bandai
    ("bandai", "bandai_premium"),
    # K-pop
    ("hybe", "kpop_merch"),
    ("sm entertainment", "kpop_merch"),
    ("jyp entertainment", "kpop_merch"),
    ("yg entertainment", "kpop_merch"),
    ("weverse", "kpop_merch"),
    # Taylor Swift
    ("taylor swift", "taylor_swift"),
]

# Subject keyword → category mapping
SUBJECT_CATEGORY_MAP: list[tuple[str, str]] = [
    ("warhammer", "warhammer"),
    ("age of sigmar", "warhammer"),
    ("40,000", "warhammer"),
    ("40k", "warhammer"),
    ("games workshop", "warhammer"),
    ("manga", "manga"),
    ("graphic novel", "manga"),
    ("anime", "anime_figures"),
    ("pokemon", "pokemon"),
    ("pokémon", "pokemon"),
    ("magic the gathering", "mtg"),
    ("magic: the gathering", "mtg"),
    ("yu-gi-oh", "yugioh"),
    ("yugioh", "yugioh"),
    ("lego", "lego"),
    ("funko", "funko"),
    ("sports card", "sportscards"),
    ("baseball card", "sportscards"),
    ("football card", "sportscards"),
    ("basketball card", "sportscards"),
    ("retro game", "retro_games"),
    ("video game", "retro_games"),
    ("one piece", "one_piece"),
    ("gundam", "gunpla"),
    ("gunpla", "gunpla"),
    ("model kit", "scale_models"),
    ("scale model", "scale_models"),
    ("diecast", "diecast"),
    ("hot wheels", "diecast"),
    ("disney", "disney"),
    ("studio ghibli", "ghibli"),
    ("nintendo", "nintendo_merch"),
    ("k-pop", "kpop_merch"),
    ("kpop", "kpop_merch"),
    ("taylor swift", "taylor_swift"),
    ("blu-ray", "bluray_steelbook"),
    ("steelbook", "bluray_steelbook"),
    ("vinyl record", "anime_ost_vinyl"),
    ("soundtrack", "anime_soundtrack"),
    ("vtuber", "vtuber"),
    ("hololive", "vtuber"),
    ("loungefly", "loungefly"),
    ("keycap", "keycaps"),
    ("theme park", "theme_park"),
]


def _classify_category(
    publisher: str,
    title: str,
    subjects: list[str],
) -> Optional[str]:
    """Classify a book into one of our 36 categories based on metadata."""
    combined_text = f"{publisher} {title} {' '.join(subjects)}".lower()

    # Check publisher first (more specific)
    pub_lower = publisher.lower()
    for pattern, cat in PUBLISHER_CATEGORY_MAP:
        if pattern in pub_lower:
            return cat

    # Check subjects + title
    for pattern, cat in SUBJECT_CATEGORY_MAP:
        if pattern in combined_text:
            return cat

    # Fallback: if it's clearly a book but no category matched
    return None


def _is_isbn(code: str) -> bool:
    """Check if a barcode looks like an ISBN (10 or 13 digits, 978/979 prefix)."""
    cleaned = re.sub(r"[\s-]", "", code)
    if len(cleaned) == 13 and cleaned.startswith(("978", "979")):
        return True
    if len(cleaned) == 10:
        return True
    return False


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class BarcodeLookupRequest(BaseModel):
    barcode: str
    code_type: Optional[str] = None


class PriceBand(BaseModel):
    q10: float
    q50: float
    q90: float
    confidence: float
    currency: str = "EUR"


class BarcodeLookupResponse(BaseModel):
    title: Optional[str] = None
    category_id: Optional[str] = None
    subtype_id: Optional[str] = None
    taxonomy_version: str = "v1.0"
    collections: list[str] = []
    attributes: dict[str, Any] = {}
    missing_required: list[str] = []
    price_band: Optional[PriceBand] = None
    rationale: list[str] = []
    image_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Lookup providers
# ---------------------------------------------------------------------------

async def _lookup_local_catalog(barcode: str, pool) -> Optional[dict]:
    """Check category_items table for a matching external_id or item_key."""
    if not pool:
        return None

    try:
        async with pool.acquire() as conn:
            # Search by external_id (where we store ISBNs/barcodes)
            row = await conn.fetchrow(
                """
                SELECT category, item_key, title, brand, rarity, notes, image_url, external_id
                FROM category_items
                WHERE external_id = $1
                LIMIT 1
                """,
                barcode,
            )
            if not row:
                # Also try item_key (some imports use ISBN as key)
                row = await conn.fetchrow(
                    """
                    SELECT category, item_key, title, brand, rarity, notes, image_url, external_id
                    FROM category_items
                    WHERE item_key = $1
                    LIMIT 1
                    """,
                    barcode,
                )
            if row:
                return dict(row)
    except Exception as e:
        logger.warning(f"[barcode] Local catalog lookup error: {e}")

    return None


async def _lookup_open_library(isbn: str) -> Optional[dict]:
    """Query Open Library for book data by ISBN."""
    url = f"https://openlibrary.org/isbn/{isbn}.json"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code != 200:
                logger.debug(f"[barcode] Open Library {resp.status_code} for ISBN {isbn}")
                return None
            data = resp.json()

            title = data.get("title", "")
            subtitle = data.get("subtitle")
            if subtitle:
                title = f"{title}: {subtitle}"

            # Get publisher info
            publishers = data.get("publishers", [])
            publisher = publishers[0] if publishers else ""

            # Get subjects
            subjects = [s.get("name", s) if isinstance(s, dict) else str(s)
                        for s in data.get("subjects", [])]

            # Get cover image
            covers = data.get("covers", [])
            cover_url = None
            if covers:
                cover_id = covers[0]
                cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"

            # Number of pages
            pages = data.get("number_of_pages")

            # Try to get author info from works
            authors = []
            for author_ref in data.get("authors", []):
                author_key = author_ref.get("key", "")
                if author_key:
                    try:
                        author_resp = await client.get(
                            f"https://openlibrary.org{author_key}.json",
                            follow_redirects=True,
                        )
                        if author_resp.status_code == 200:
                            author_data = author_resp.json()
                            authors.append(author_data.get("name", ""))
                    except Exception:
                        pass

            # Also check works for subjects if edition has none
            if not subjects:
                works = data.get("works", [])
                if works:
                    work_key = works[0].get("key", "")
                    if work_key:
                        try:
                            work_resp = await client.get(
                                f"https://openlibrary.org{work_key}.json",
                                follow_redirects=True,
                            )
                            if work_resp.status_code == 200:
                                work_data = work_resp.json()
                                subjects = [
                                    s if isinstance(s, str) else s.get("name", "")
                                    for s in work_data.get("subjects", [])
                                ]
                        except Exception:
                            pass

            return {
                "title": title,
                "publisher": publisher,
                "publishers": publishers,
                "authors": authors,
                "subjects": subjects,
                "cover_url": cover_url,
                "pages": pages,
                "isbn": isbn,
                "publish_date": data.get("publish_date"),
                "source": "open_library",
            }

    except httpx.TimeoutException:
        logger.warning(f"[barcode] Open Library timeout for ISBN {isbn}")
    except Exception as e:
        logger.warning(f"[barcode] Open Library error for ISBN {isbn}: {e}")

    return None


async def _lookup_google_books(isbn: str) -> Optional[dict]:
    """Fallback: query Google Books API for ISBN data."""
    url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            data = resp.json()
            items = data.get("items", [])
            if not items:
                return None

            vol = items[0].get("volumeInfo", {})
            title = vol.get("title", "")
            subtitle = vol.get("subtitle")
            if subtitle:
                title = f"{title}: {subtitle}"

            publisher = vol.get("publisher", "")
            authors = vol.get("authors", [])
            categories = vol.get("categories", [])
            pages = vol.get("pageCount")

            # Cover image
            cover_url = None
            image_links = vol.get("imageLinks", {})
            cover_url = image_links.get("thumbnail") or image_links.get("smallThumbnail")

            return {
                "title": title,
                "publisher": publisher,
                "publishers": [publisher] if publisher else [],
                "authors": authors,
                "subjects": categories,
                "cover_url": cover_url,
                "pages": pages,
                "isbn": isbn,
                "publish_date": vol.get("publishedDate"),
                "source": "google_books",
            }

    except httpx.TimeoutException:
        logger.warning(f"[barcode] Google Books timeout for ISBN {isbn}")
    except Exception as e:
        logger.warning(f"[barcode] Google Books error for ISBN {isbn}: {e}")

    return None


async def _lookup_market_price(category: str, title: str, pool) -> Optional[PriceBand]:
    """Look up recent market prices from market_hits for similar items."""
    if not pool or not category:
        return None

    try:
        async with pool.acquire() as conn:
            # Search market_hits for title matches in the same category
            # Use trigram or simple LIKE match
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
                f"%{title[:40]}%",
            )
            if not rows or len(rows) < 3:
                return None

            prices = sorted([float(r["price"]) for r in rows])
            n = len(prices)
            q10_idx = max(0, int(n * 0.1))
            q50_idx = int(n * 0.5)
            q90_idx = min(n - 1, int(n * 0.9))

            return PriceBand(
                q10=round(prices[q10_idx], 2),
                q50=round(prices[q50_idx], 2),
                q90=round(prices[q90_idx], 2),
                confidence=min(0.9, 0.3 + n * 0.03),
                currency=rows[0]["currency"] or "EUR",
            )
    except Exception as e:
        logger.debug(f"[barcode] Market price lookup error: {e}")

    return None


# ---------------------------------------------------------------------------
# Main endpoint
# ---------------------------------------------------------------------------

@router.post("/lookup", response_model=BarcodeLookupResponse)
async def barcode_lookup(req: BarcodeLookupRequest) -> BarcodeLookupResponse:
    """
    Look up a product by barcode or ISBN.

    Cascade:
      1. Local catalog (category_items)
      2. Open Library (ISBN books)
      3. Google Books (fallback)
      4. Category classification from metadata
    """
    barcode = req.barcode.strip()
    code_type = (req.code_type or "").lower()

    if not barcode:
        raise HTTPException(status_code=400, detail="Barcode is required")

    pool = _get_db_pool()
    rationale: list[str] = []

    # ------------------------------------------------------------------
    # Step 1: Local catalog lookup
    # ------------------------------------------------------------------
    local = await _lookup_local_catalog(barcode, pool)
    if local:
        rationale.append("Matched in local catalog (category_items)")
        category = local["category"]

        # Try to get market price
        price_band = await _lookup_market_price(category, local["title"], pool)
        if price_band:
            rationale.append("Price from recent market data")

        return BarcodeLookupResponse(
            title=local["title"],
            category_id=category,
            subtype_id=local.get("rarity"),
            collections=[],
            attributes={
                "brand": local.get("brand"),
                "isbn": barcode if _is_isbn(barcode) else None,
                "item_key": local.get("item_key"),
                "source": "local_catalog",
            },
            missing_required=[],
            price_band=price_band,
            rationale=rationale,
            image_url=local.get("image_url"),
        )

    # ------------------------------------------------------------------
    # Step 2 & 3: External ISBN lookup (Open Library → Google Books)
    # ------------------------------------------------------------------
    is_isbn = _is_isbn(barcode) or code_type in ("isbn", "ean13")
    book_data: Optional[dict] = None

    if is_isbn:
        # Clean ISBN
        isbn_clean = re.sub(r"[\s-]", "", barcode)

        book_data = await _lookup_open_library(isbn_clean)
        if book_data:
            rationale.append(f"Found via Open Library (ISBN: {isbn_clean})")
        else:
            book_data = await _lookup_google_books(isbn_clean)
            if book_data:
                rationale.append(f"Found via Google Books (ISBN: {isbn_clean})")

    if book_data:
        # Classify into our category system
        category_id = _classify_category(
            publisher=book_data.get("publisher", ""),
            title=book_data.get("title", ""),
            subjects=book_data.get("subjects", []),
        )

        if category_id:
            rationale.append(f"Classified as '{category_id}' from publisher/subject metadata")
        else:
            rationale.append("Could not auto-classify category — user can select manually")

        # Build attributes
        attributes: dict[str, Any] = {
            "isbn": book_data.get("isbn"),
            "publisher": book_data.get("publisher"),
            "authors": book_data.get("authors", []),
            "publish_date": book_data.get("publish_date"),
            "pages": book_data.get("pages"),
            "source": book_data.get("source"),
        }

        # Try market price if we have a category
        price_band = None
        if category_id:
            price_band = await _lookup_market_price(
                category_id, book_data["title"], pool,
            )
            if price_band:
                rationale.append("Price estimated from recent market sales")

        missing = []
        if not category_id:
            missing.append("categoryId")

        return BarcodeLookupResponse(
            title=book_data["title"],
            category_id=category_id,
            subtype_id=None,
            collections=[],
            attributes=attributes,
            missing_required=missing,
            price_band=price_band,
            rationale=rationale,
            image_url=book_data.get("cover_url"),
        )

    # ------------------------------------------------------------------
    # Step 4: Not found anywhere
    # ------------------------------------------------------------------
    rationale.append(f"No match found for barcode {barcode}")
    if is_isbn:
        rationale.append("ISBN not found in Open Library or Google Books")
    else:
        rationale.append("Non-ISBN barcodes require catalog data — try QuickScan instead")

    return BarcodeLookupResponse(
        title=None,
        category_id=None,
        missing_required=["title", "categoryId"],
        rationale=rationale,
    )
