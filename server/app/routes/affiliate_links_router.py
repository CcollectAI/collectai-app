"""
Affiliate links router — marketplace search URLs with affiliate tags for all users.

Endpoints:
    GET /marketplace/affiliate-links — Build affiliate-tagged marketplace URLs for a query
"""

from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.auth import get_optional_user_id
from app.lib.affiliate import build_affiliate_url
from app.rate_limit import per_ip_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketplace", tags=["Marketplace"])

# Per-IP: 100 requests per minute for public affiliate links
_affiliate_ip_limit = per_ip_rate_limit(100, scope="affiliate")

# Categories that include TCG-specific marketplaces
_TCG_CATEGORIES = {"pokemon", "mtg", "yugioh", "lorcana", "digimon", "one_piece_tcg"}

# Categories suited for specific marketplaces
_VINYL_MUSIC_CATEGORIES = {"vinyl_records", "anime_soundtrack", "anime_ost_vinyl"}
_SNEAKER_STREETWEAR_CATEGORIES = {"sneakers", "designer_toys"}
_LEGO_CATEGORIES = {"lego"}
_FIGURE_CATEGORIES = {"anime_figures", "hot_toys", "gunpla", "bandai_premium", "one_piece", "ghibli", "vtuber"}
_JP_CATEGORIES = {
    "anime_figures", "hot_toys", "gunpla", "bandai_premium", "one_piece",
    "ghibli", "vtuber", "manga", "jp_magazine", "jp_event", "anime_bluray",
    "anime_soundtrack", "anime_ost_vinyl",
}


class AffiliateLink(BaseModel):
    source: str
    url: str
    affiliate_url: str
    label: str


class AffiliateLinksResponse(BaseModel):
    links: list[AffiliateLink]


# ---------------------------------------------------------------------------
# URL builders per marketplace
# ---------------------------------------------------------------------------

def _build_ebay_search_url(query: str) -> str:
    return f"https://www.ebay.com/sch/i.html?_nkw={quote_plus(query)}"


def _build_tcgplayer_search_url(query: str) -> str:
    return f"https://www.tcgplayer.com/search/all/product?q={quote_plus(query)}"


def _build_cardmarket_search_url(query: str) -> str:
    return f"https://www.cardmarket.com/en/Pokemon/Products/Search?searchString={quote_plus(query)}"


def _build_mercari_search_url(query: str) -> str:
    return f"https://www.mercari.com/search/?keyword={quote_plus(query)}"


def _build_discogs_search_url(query: str) -> str:
    return f"https://www.discogs.com/search/?q={quote_plus(query)}&type=all"


def _build_stockx_search_url(query: str) -> str:
    return f"https://stockx.com/search?s={quote_plus(query)}"


def _build_bricklink_search_url(query: str) -> str:
    return f"https://www.bricklink.com/v2/search.page?q={quote_plus(query)}"


def _build_yahoo_auctions_jp_search_url(query: str) -> str:
    return f"https://auctions.yahoo.co.jp/search/search?p={quote_plus(query)}"


def _build_amiami_search_url(query: str) -> str:
    return f"https://www.amiami.com/eng/search/list/?s_keywords={quote_plus(query)}"


@router.get("/affiliate-links", response_model=AffiliateLinksResponse, dependencies=[Depends(_affiliate_ip_limit)], summary="Get affiliate search links")
async def get_affiliate_links(
    query: str = Query(..., min_length=1, max_length=500, description="Search query"),
    category: Optional[str] = Query(None, max_length=64, description="Item category"),
    limit: int = Query(default=6, ge=1, le=10, description="Max links to return"),
    region: Optional[str] = Query(None, max_length=32, description="User region"),
    user_id: Optional[str] = Depends(get_optional_user_id),
):
    """Build affiliate-tagged marketplace search URLs.

    No auth required — works for free and paid users alike.
    Returns deterministic links (no external API calls).
    Region-aware: includes region-specific marketplaces when region is provided.
    """
    links: list[AffiliateLink] = []
    cat = (category or "").lower().strip()
    rgn = (region or "").lower().strip()

    # eBay — always included
    ebay_url = _build_ebay_search_url(query)
    ebay_aff, _ = build_affiliate_url(ebay_url, "ebay")
    links.append(AffiliateLink(
        source="ebay",
        url=ebay_url,
        affiliate_url=ebay_aff,
        label="Find on eBay",
    ))

    # TCGPlayer — for TCG categories (primarily Americas)
    if cat in _TCG_CATEGORIES and rgn != "japan":
        tcg_url = _build_tcgplayer_search_url(query)
        tcg_aff, _ = build_affiliate_url(tcg_url, "tcgplayer")
        links.append(AffiliateLink(
            source="tcgplayer",
            url=tcg_url,
            affiliate_url=tcg_aff,
            label="Find on TCGPlayer",
        ))

    # Cardmarket — for TCG categories (primarily Europe)
    if cat in _TCG_CATEGORIES:
        cm_url = _build_cardmarket_search_url(query)
        cm_aff, _ = build_affiliate_url(cm_url, "cardmarket")
        links.append(AffiliateLink(
            source="cardmarket",
            url=cm_url,
            affiliate_url=cm_aff,
            label="Find on Cardmarket",
        ))

    # Mercari — general marketplace, strong in JP + US
    mercari_url = _build_mercari_search_url(query)
    mercari_aff, _ = build_affiliate_url(mercari_url, "mercari")
    links.append(AffiliateLink(
        source="mercari",
        url=mercari_url,
        affiliate_url=mercari_aff,
        label="Find on Mercari",
    ))

    # Discogs — vinyl & music categories
    if cat in _VINYL_MUSIC_CATEGORIES:
        discogs_url = _build_discogs_search_url(query)
        discogs_aff, _ = build_affiliate_url(discogs_url, "discogs")
        links.append(AffiliateLink(
            source="discogs",
            url=discogs_url,
            affiliate_url=discogs_aff,
            label="Find on Discogs",
        ))

    # StockX — sneakers & streetwear
    if cat in _SNEAKER_STREETWEAR_CATEGORIES:
        stockx_url = _build_stockx_search_url(query)
        stockx_aff, _ = build_affiliate_url(stockx_url, "stockx")
        links.append(AffiliateLink(
            source="stockx",
            url=stockx_url,
            affiliate_url=stockx_aff,
            label="Find on StockX",
        ))

    # BrickLink — LEGO
    if cat in _LEGO_CATEGORIES:
        bl_url = _build_bricklink_search_url(query)
        bl_aff, _ = build_affiliate_url(bl_url, "bricklink")
        links.append(AffiliateLink(
            source="bricklink",
            url=bl_url,
            affiliate_url=bl_aff,
            label="Find on BrickLink",
        ))

    # Yahoo Auctions JP — JP categories or Japan region
    if rgn == "japan" or cat in _JP_CATEGORIES:
        ya_url = _build_yahoo_auctions_jp_search_url(query)
        links.append(AffiliateLink(
            source="yahoo_auctions_jp",
            url=ya_url,
            affiliate_url=ya_url,
            label="Find on Yahoo Auctions JP",
        ))

    # AmiAmi — anime figures & JP exclusives
    if cat in _FIGURE_CATEGORIES:
        ami_url = _build_amiami_search_url(query)
        links.append(AffiliateLink(
            source="amiami",
            url=ami_url,
            affiliate_url=ami_url,
            label="Find on AmiAmi",
        ))

    return AffiliateLinksResponse(links=links[:limit])


class TagAffiliateUrlRequest(BaseModel):
    url: str
    source: str


class TagAffiliateUrlResponse(BaseModel):
    url: str
    affiliate_url: str
    source: str


@router.post("/affiliate-url", response_model=TagAffiliateUrlResponse, dependencies=[Depends(_affiliate_ip_limit)], summary="Tag URL with affiliate params")
async def tag_affiliate_url(
    payload: TagAffiliateUrlRequest,
    user_id: Optional[str] = Depends(get_optional_user_id),
):
    """Tag any raw listing URL with affiliate parameters.

    Accepts a URL and marketplace source, returns the affiliate-tagged version.
    No auth required.
    """
    affiliate_url, affiliate_source = build_affiliate_url(payload.url, payload.source)
    return TagAffiliateUrlResponse(
        url=payload.url,
        affiliate_url=affiliate_url,
        source=affiliate_source or payload.source,
    )
