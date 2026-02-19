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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketplace", tags=["marketplace"])

# Categories that include TCG-specific marketplaces
_TCG_CATEGORIES = {"pokemon", "mtg", "yugioh", "lorcana", "digimon", "one_piece_tcg"}


class AffiliateLink(BaseModel):
    source: str
    url: str
    affiliate_url: str
    label: str


class AffiliateLinksResponse(BaseModel):
    links: list[AffiliateLink]


def _build_ebay_search_url(query: str) -> str:
    return f"https://www.ebay.com/sch/i.html?_nkw={quote_plus(query)}"


def _build_tcgplayer_search_url(query: str) -> str:
    return f"https://www.tcgplayer.com/search/all/product?q={quote_plus(query)}"


def _build_cardmarket_search_url(query: str) -> str:
    return f"https://www.cardmarket.com/en/Pokemon/Products/Search?searchString={quote_plus(query)}"


@router.get("/affiliate-links", response_model=AffiliateLinksResponse)
async def get_affiliate_links(
    query: str = Query(..., min_length=1, max_length=500, description="Search query"),
    category: Optional[str] = Query(None, max_length=64, description="Item category"),
    limit: int = Query(default=3, ge=1, le=10, description="Max links to return"),
    user_id: Optional[str] = Depends(get_optional_user_id),
):
    """Build affiliate-tagged marketplace search URLs.

    No auth required — works for free and paid users alike.
    Returns deterministic links (no external API calls).
    """
    links: list[AffiliateLink] = []
    cat = (category or "").lower().strip()

    # eBay — always included
    ebay_url = _build_ebay_search_url(query)
    ebay_aff, _ = build_affiliate_url(ebay_url, "ebay")
    links.append(AffiliateLink(
        source="ebay",
        url=ebay_url,
        affiliate_url=ebay_aff,
        label="Find on eBay",
    ))

    # TCGPlayer — only for TCG categories
    if cat in _TCG_CATEGORIES:
        tcg_url = _build_tcgplayer_search_url(query)
        tcg_aff, _ = build_affiliate_url(tcg_url, "tcgplayer")
        links.append(AffiliateLink(
            source="tcgplayer",
            url=tcg_url,
            affiliate_url=tcg_aff,
            label="Find on TCGPlayer",
        ))

    # Cardmarket — only for TCG categories
    if cat in _TCG_CATEGORIES:
        cm_url = _build_cardmarket_search_url(query)
        cm_aff, _ = build_affiliate_url(cm_url, "cardmarket")
        links.append(AffiliateLink(
            source="cardmarket",
            url=cm_url,
            affiliate_url=cm_aff,
            label="Find on Cardmarket",
        ))

    return AffiliateLinksResponse(links=links[:limit])
