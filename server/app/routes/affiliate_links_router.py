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
from app.lib.fx_service import get_rates_from_eur
from app.rate_limit import per_ip_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketplace", tags=["Marketplace"])

# Per-IP: 100 requests per minute for public affiliate links
_affiliate_ip_limit = per_ip_rate_limit(100, scope="affiliate")

# Categories that include TCG-specific marketplaces
_TCG_CATEGORIES = {"pokemon", "mtg", "yugioh", "lorcana", "digimon", "one_piece_tcg"}

# Categories suited for specific marketplaces
_VINYL_MUSIC_CATEGORIES = {"vinyl_records", "anime_soundtrack", "anime_ost_vinyl", "city_pop_vinyl"}
_SNEAKER_STREETWEAR_CATEGORIES = {"sneakers", "designer_toys"}
_LEGO_CATEGORIES = {"lego"}

# Categories where a HIGH-VALUE example stops being credibly sold on a general
# classifieds site. The category alone is not the test — price is.
#
# A EUR 45 Casio and a EUR 184,194 Rolex Cosmograph Daytona Le Mans are both
# "watches", and the first genuinely trades on eBay every day. Gating the whole
# category would strip the honest answer from the cheap end to protect the
# expensive end. So the rule is: these categories, ABOVE the threshold.
_HIGH_VALUE_CATEGORIES = {"watches", "jewellery", "pens"}

# Where "expensive enough that provenance beats reach" starts, in EUR.
# Above this, an authentication guarantee IS the product: Chrono24 holds funds
# until the buyer authenticates, Catawiki has expert vetting per lot. Below it,
# eBay's reach is worth more than a specialist's assurance.
_HIGH_VALUE_EUR = 1000.0

# Sources offered instead, per category, once past the threshold.
_HIGH_VALUE_SOURCES = {
    "watches": ("chrono24", "catawiki", "google"),
    "jewellery": ("catawiki", "google"),
    # Pens keep eBay even at the top end — a grail Montblanc or Nakaya is
    # genuinely traded there, which is not true of a six-figure watch.
    "pens": ("catawiki", "ebay", "google"),
}
_FIGURE_CATEGORIES = {"anime_figures", "hot_toys", "gunpla", "bandai_premium", "one_piece", "ghibli", "vtuber"}
_JP_CATEGORIES = {
    "anime_figures", "hot_toys", "gunpla", "bandai_premium", "one_piece",
    "ghibli", "vtuber", "manga", "jp_magazine", "jp_event", "anime_bluray",
    "anime_soundtrack", "anime_ost_vinyl",
}


# ---------------------------------------------------------------------------
# Per-category shopping profile
# ---------------------------------------------------------------------------
#
# A bare title is not a shoppable query. "Bayou" on eBay returns swamp photos
# and Louisiana hot sauce; the buyer wanted a Revised dual land. Three things
# turn a title into a shortlist, and all three are per-category:
#
#   ebay_sacat    eBay browse-category id, used as ``_sacat``. Restricts the
#                 search to the right part of the catalogue.
#   suffix        Disambiguating words appended to the query for titles that
#                 collide across franchises ("Bayou", "Shining", "Alpha").
#   sources       Preferred marketplace order. The response used to be
#                 eBay-first for every category, and `app/(tabs)/wishlist.tsx`
#                 opened ``links[0]`` blind — so a EUR-priced MTG single always
#                 routed to eBay US even though Cardmarket was in the payload.
#
# ⚠️ The ``ebay_sacat`` values are NOT guesses. They were read out of eBay's own
# Taxonomy API (``/commerce/taxonomy/v1/category_tree/0/get_category_suggestions``)
# on 2026-08-04, then widened by hand to the browse level that contains the
# whole collectible type. A too-narrow leaf silently returns nothing: the API's
# top suggestion for gunpla was ``261068`` (Action Figures) and for pens
# ``14000`` (Montblanc), both of which would have hidden most real listings.
# Re-derive with the Taxonomy API rather than editing these by intuition.

# Only these nine have a *search* URL builder below. `affiliate.py` tags six more
# networks (chrono24, keh, mpb, masterofmalt, drop, popmart) but only for concrete
# listing URLs, which is what deal discovery hands it — there is no way to deep-link
# a search on them yet. Do not name a source here without adding its builder, or
# it silently drops out of the response.
# The final allowlist: `get_affiliate_links` intersects eligibility with this,
# so a source missing here is silently dropped from the response no matter what
# _eligible_sources or a category profile says. Adding a source in three places
# and forgetting the fourth returns an EMPTY rail, not an error — which is
# exactly what watches and jewellery did until this line was updated.
_SEARCHABLE_SOURCES = frozenset({
    "ebay", "tcgplayer", "cardmarket", "mercari", "discogs",
    "stockx", "bricklink", "yahoo_auctions_jp", "amiami",
    "chrono24", "catawiki", "google",
})

_DEFAULT_SOURCES = ("ebay", "mercari")


class _CategoryProfile(BaseModel):
    ebay_sacat: Optional[str] = None
    suffix: str = ""
    sources: tuple[str, ...] = _DEFAULT_SOURCES


# TCG singles + sealed both live under eBay 2536 / 182982, so the parent node is
# used rather than the "Individual Cards" leaf.
_TCG_SOURCES = ("cardmarket", "tcgplayer", "ebay", "mercari")
_JP_SOURCES = ("amiami", "yahoo_auctions_jp", "mercari", "ebay")

_CATEGORY_PROFILES: dict[str, _CategoryProfile] = {
    # --- Trading card games -------------------------------------------------
    "mtg": _CategoryProfile(ebay_sacat="2536", suffix="MTG", sources=_TCG_SOURCES),
    "pokemon": _CategoryProfile(ebay_sacat="2536", suffix="Pokemon", sources=_TCG_SOURCES),
    "retro_pokemon": _CategoryProfile(ebay_sacat="2536", suffix="Pokemon", sources=_TCG_SOURCES),
    "yugioh": _CategoryProfile(ebay_sacat="2536", suffix="Yu-Gi-Oh", sources=_TCG_SOURCES),
    "digimon": _CategoryProfile(ebay_sacat="2536", suffix="Digimon", sources=_TCG_SOURCES),
    "one_piece_tcg": _CategoryProfile(ebay_sacat="2536", suffix="One Piece TCG", sources=_TCG_SOURCES),
    "lorcana": _CategoryProfile(ebay_sacat="182982", suffix="Lorcana", sources=_TCG_SOURCES),
    "sportscards": _CategoryProfile(ebay_sacat="212"),
    # --- Print --------------------------------------------------------------
    "comic_books": _CategoryProfile(ebay_sacat="259103"),
    "manga": _CategoryProfile(ebay_sacat="33346", suffix="manga"),
    "jp_magazine": _CategoryProfile(ebay_sacat="280", sources=_JP_SOURCES),
    # --- Build / model ------------------------------------------------------
    "lego": _CategoryProfile(ebay_sacat="183447", suffix="LEGO", sources=("bricklink", "ebay", "mercari")),
    "warhammer": _CategoryProfile(ebay_sacat="31398", suffix="Warhammer"),
    "gunpla": _CategoryProfile(ebay_sacat="1188", suffix="Gundam model kit", sources=_JP_SOURCES),
    "scale_models": _CategoryProfile(ebay_sacat="1188", suffix="model kit"),
    # --- Figures ------------------------------------------------------------
    "anime_figures": _CategoryProfile(ebay_sacat="1344", sources=_JP_SOURCES),
    "hot_toys": _CategoryProfile(ebay_sacat="246", suffix="Hot Toys"),
    "action_figures": _CategoryProfile(ebay_sacat="246"),
    "marvel_legends": _CategoryProfile(ebay_sacat="246", suffix="Marvel Legends"),
    "designer_toys": _CategoryProfile(ebay_sacat="246", sources=("stockx", "ebay", "mercari")),
    "blind_box": _CategoryProfile(ebay_sacat="246"),
    "vintage_toys": _CategoryProfile(ebay_sacat="717"),
    "plush_collectibles": _CategoryProfile(ebay_sacat="436"),
    "funko": _CategoryProfile(ebay_sacat="149372", suffix="Funko Pop"),
    "one_piece": _CategoryProfile(ebay_sacat="1344", suffix="One Piece", sources=_JP_SOURCES),
    "ghibli": _CategoryProfile(ebay_sacat="1344", suffix="Ghibli", sources=_JP_SOURCES),
    "vtuber": _CategoryProfile(ebay_sacat="1344", sources=_JP_SOURCES),
    "bandai_premium": _CategoryProfile(ebay_sacat="1344", sources=_JP_SOURCES),
    "jp_event": _CategoryProfile(ebay_sacat="1344", sources=_JP_SOURCES),
    "diecast": _CategoryProfile(ebay_sacat="222"),
    # --- Games / hardware ---------------------------------------------------
    "retro_games": _CategoryProfile(ebay_sacat="139973"),
    "retro_handhelds": _CategoryProfile(ebay_sacat="139971"),
    "nintendo_merch": _CategoryProfile(ebay_sacat="38583"),
    "oop_board_games": _CategoryProfile(ebay_sacat="2550"),
    "keycaps": _CategoryProfile(ebay_sacat="33963", suffix="keycap"),
    # --- Media --------------------------------------------------------------
    "bluray_steelbook": _CategoryProfile(ebay_sacat="617", suffix="steelbook"),
    "anime_bluray": _CategoryProfile(ebay_sacat="617", suffix="anime Blu-ray"),
    "vinyl_records": _CategoryProfile(ebay_sacat="176985", sources=("discogs", "ebay", "mercari")),
    "city_pop_vinyl": _CategoryProfile(ebay_sacat="176985", suffix="vinyl", sources=("discogs", "ebay", "mercari")),
    "anime_ost_vinyl": _CategoryProfile(ebay_sacat="176985", suffix="vinyl", sources=("discogs", "ebay", "mercari")),
    "anime_soundtrack": _CategoryProfile(ebay_sacat="11233", suffix="soundtrack", sources=("discogs", "ebay", "mercari")),
    # --- Fandom / memorabilia ----------------------------------------------
    "kpop_merch": _CategoryProfile(ebay_sacat="2329"),
    "kpop_lightsticks": _CategoryProfile(ebay_sacat="2329", suffix="lightstick"),
    "taylor_swift": _CategoryProfile(ebay_sacat="2329", suffix="Taylor Swift"),
    "pop_fandom": _CategoryProfile(ebay_sacat="2329"),
    "disney": _CategoryProfile(ebay_sacat="137", suffix="Disney"),
    "theme_park": _CategoryProfile(ebay_sacat="1369"),
    "loungefly": _CategoryProfile(ebay_sacat="169291", suffix="Loungefly"),
    # --- Lifestyle ----------------------------------------------------------
    # Ordering covers BOTH paths: below the high-value threshold the specialist
    # names are simply not eligible and drop out, leaving eBay/Mercari; above
    # it, the general ones drop out. One tuple, filtered by _eligible_sources.
    "watches": _CategoryProfile(
        ebay_sacat="31387", sources=("chrono24", "catawiki", "ebay", "mercari", "google")),
    "jewellery": _CategoryProfile(sources=("catawiki", "ebay", "mercari", "google")),
    "vintage_cameras": _CategoryProfile(ebay_sacat="15230"),
    "whiskey": _CategoryProfile(ebay_sacat="13916"),
    "fragrances": _CategoryProfile(ebay_sacat="180345"),
    "sneakers": _CategoryProfile(ebay_sacat="15709", sources=("stockx", "ebay", "mercari")),
    "pens": _CategoryProfile(ebay_sacat="966", sources=("catawiki", "ebay", "mercari", "google")),
}

_FALLBACK_PROFILE = _CategoryProfile()


def _profile_for(category: str) -> _CategoryProfile:
    return _CATEGORY_PROFILES.get(category, _FALLBACK_PROFILE)


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
#
# Each takes the *qualified* query (title + category suffix) and, where the
# marketplace supports it, the buyer's price ceiling. `max_price` is always in
# the currency the destination site quotes — the caller converts.

# Cardmarket namespaces its catalogue per game in the PATH. The single builder
# used to hardcode `/en/Pokemon/`, so every MTG, Yu-Gi-Oh and Lorcana search was
# run against the Pokémon catalogue and returned nothing.
_CARDMARKET_GAME_PATHS = {
    "mtg": "Magic",
    "pokemon": "Pokemon",
    "retro_pokemon": "Pokemon",
    "yugioh": "YuGiOh",
    "lorcana": "Lorcana",
    "one_piece_tcg": "OnePiece",
    "digimon": "Digimon",
}

# TCGPlayer likewise scopes by product line in the path; `/all/` works but ranks
# unrelated games alongside the one the user actually collects.
_TCGPLAYER_PRODUCT_LINES = {
    "mtg": "magic",
    "pokemon": "pokemon",
    "retro_pokemon": "pokemon",
    "yugioh": "yugioh",
    "lorcana": "lorcana",
    "one_piece_tcg": "one-piece-card-game",
    "digimon": "digimon-card-game",
}


def _build_ebay_search_url(
    query: str,
    sacat: Optional[str] = None,
    max_price: Optional[float] = None,
) -> str:
    """eBay search, narrowed to something a buyer can act on.

    Beyond the keyword: restrict to the right browse category, drop auctions
    the user cannot act on right now, cap at their target, and sort cheapest
    first including shipping. Without these a watchlist title like "Bayou"
    returns swamp photography.
    """
    params = [f"_nkw={quote_plus(query)}"]
    if sacat:
        params.append(f"_sacat={sacat}")
    params.append("LH_BIN=1")   # Buy It Now only
    params.append("_sop=15")    # price + shipping: lowest first
    if max_price and max_price > 0:
        params.append(f"_udhi={max_price:.2f}")
    return "https://www.ebay.com/sch/i.html?" + "&".join(params)


def _build_tcgplayer_search_url(query: str, category: str = "") -> str:
    line = _TCGPLAYER_PRODUCT_LINES.get(category, "all")
    return f"https://www.tcgplayer.com/search/{line}/product?q={quote_plus(query)}"


def _build_cardmarket_search_url(query: str, category: str = "") -> str:
    game = _CARDMARKET_GAME_PATHS.get(category, "Magic")
    return f"https://www.cardmarket.com/en/{game}/Products/Search?searchString={quote_plus(query)}"


def _build_mercari_search_url(query: str, max_price: Optional[float] = None) -> str:
    url = f"https://www.mercari.com/search/?keyword={quote_plus(query)}"
    if max_price and max_price > 0:
        url += f"&maxPrice={int(max_price)}"
    return url


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


def _build_chrono24_search_url(query: str) -> str:
    return f"https://www.chrono24.com/search/index.htm?query={quote_plus(query)}"


def _build_catawiki_search_url(query: str) -> str:
    return f"https://www.catawiki.com/en/s?q={quote_plus(query)}"


def _build_google_shopping_search_url(query: str) -> str:
    """Last-resort pointer for high-value categories with no trusted marketplace.

    Not an affiliate link and not a marketplace — it is the honest answer to
    "where do I buy a EUR 180k Daytona", which is: not from a general
    classifieds site. Google surfaces the brand and the authorised dealers,
    which is where that purchase actually happens.

    It exists so removing eBay and Mercari from luxury categories cannot leave
    the "WHERE TO BUY" rail rendering as an empty section.
    """
    return f"https://www.google.com/search?tbm=shop&q={quote_plus(query)}"


def _qualify(query: str, suffix: str) -> str:
    """Append the category's disambiguating words, unless already present."""
    q = query.strip()
    if not suffix:
        return q
    if suffix.lower() in q.lower():
        return q
    return f"{q} {suffix}"


async def _to_site_currency(amount: float, from_currency: str, to_currency: str) -> Optional[float]:
    """Convert a price ceiling into the destination site's quote currency.

    eBay reads ``_udhi`` in the currency of the site being searched — we search
    ebay.com, which quotes USD. Sending a EUR figure unconverted silently moves
    the ceiling by whatever EUR/USD happens to be, which is worse than no
    ceiling at all. Returns None when the rate is unavailable so the caller can
    omit the cap rather than apply a wrong one.
    """
    src = (from_currency or "EUR").upper()
    dst = (to_currency or "USD").upper()
    if src == dst:
        return amount
    try:
        from_eur = await get_rates_from_eur()
    except Exception:
        logger.warning("[affiliate-links] FX lookup failed; omitting price cap", exc_info=True)
        return None
    # Rates are EUR→X. Go through EUR: amount(src) → EUR → dst.
    src_rate = 1.0 if src == "EUR" else from_eur.get(src)
    dst_rate = 1.0 if dst == "EUR" else from_eur.get(dst)
    if not src_rate or not dst_rate:
        logger.warning("[affiliate-links] no FX rate for %s→%s; omitting price cap", src, dst)
        return None
    return round(amount / src_rate * dst_rate, 2)


_SOURCE_LABELS = {
    "ebay": "eBay",
    "tcgplayer": "TCGPlayer",
    "cardmarket": "Cardmarket",
    "mercari": "Mercari",
    "discogs": "Discogs",
    "stockx": "StockX",
    "bricklink": "BrickLink",
    "yahoo_auctions_jp": "Yahoo Auctions JP",
    "amiami": "AmiAmi",
    "chrono24": "Chrono24",
    "catawiki": "Catawiki",
    # Labels are rendered as "Find on {label}", so this must be a NOUN, not a
    # verb phrase — "Find on Search the web" shipped for one deploy.
    "google": "Google Shopping",
}


def _is_high_value(cat: str, value_eur: Optional[float]) -> bool:
    """A high-value example of a category where provenance beats reach.

    PRICE is the test, not the category. Unknown value falls through to the
    normal path deliberately: most watches, pens and jewellery in a collection
    are ordinary, so guessing "luxury" on missing data would strip eBay from
    the common case to protect the rare one.
    """
    return (
        cat in _HIGH_VALUE_CATEGORIES
        and value_eur is not None
        and value_eur >= _HIGH_VALUE_EUR
    )


def _eligible_sources(cat: str, rgn: str, value_eur: Optional[float] = None) -> set[str]:
    """Which marketplaces make sense at all for this category/region/price.

    eBay and Mercari are the floor for almost everything — reach is genuinely
    what a buyer wants for a EUR 30 Funko. They stop being the right answer at
    the top of a few categories: offering a general classifieds search for a
    EUR 184,194 Daytona is worse than offering nothing, because it attaches our
    recommendation to the venue where that price point is least verifiable.
    Above the threshold an authentication guarantee IS the product.

    Chrono24 and Catawiki already have taggers in app/lib/affiliate.py
    (CATAWIKI_AFFILIATE_ID ~7-10%, CHRONO24_AFFILIATE_ID), so the swap is not a
    revenue sacrifice — an unset env var emits the link untagged and working,
    per docs/AFFILIATE_SWITCH_ON.md.
    """
    if _is_high_value(cat, value_eur):
        return set(_HIGH_VALUE_SOURCES[cat])

    eligible = {"ebay", "mercari"}
    if cat in _TCG_CATEGORIES:
        eligible.add("cardmarket")
        if rgn != "japan":
            eligible.add("tcgplayer")
    if cat in _VINYL_MUSIC_CATEGORIES:
        eligible.add("discogs")
    if cat in _SNEAKER_STREETWEAR_CATEGORIES:
        eligible.add("stockx")
    if cat in _LEGO_CATEGORIES:
        eligible.add("bricklink")
    if rgn == "japan" or cat in _JP_CATEGORIES:
        eligible.add("yahoo_auctions_jp")
    if cat in _FIGURE_CATEGORIES:
        eligible.add("amiami")
    return eligible


@router.get("/affiliate-links", response_model=AffiliateLinksResponse, dependencies=[Depends(_affiliate_ip_limit)], summary="Get affiliate search links")
async def get_affiliate_links(
    query: str = Query(..., min_length=1, max_length=500, description="Search query"),
    category: Optional[str] = Query(None, max_length=64, description="Item category"),
    limit: int = Query(default=6, ge=1, le=10, description="Max links to return"),
    region: Optional[str] = Query(None, max_length=32, description="User region"),
    max_price: Optional[float] = Query(
        None, gt=0, description="Buyer's price ceiling (e.g. a watchlist target price)"
    ),
    max_price_currency: str = Query(
        "EUR", max_length=3, description="Currency of max_price; converted per destination site"
    ),
    item_value_eur: Optional[float] = Query(
        None,
        gt=0,
        description=(
            "The item's own estimated market value in EUR. Distinct from max_price "
            "(the buyer's ceiling): this describes the THING. Above a threshold, "
            "watches/jewellery/pens route to authenticated specialists instead of "
            "general classifieds. Omit and the normal sources are returned."
        ),
    ),
    user_id: Optional[str] = Depends(get_optional_user_id),
):
    """Build affiliate-tagged marketplace search URLs.

    No auth required — works for free and paid users alike.
    Region-aware: includes region-specific marketplaces when region is provided.

    **Ordering is meaningful.** `links[0]` is the marketplace that best fits the
    category, not always eBay. `app/(tabs)/wishlist.tsx` opens `links[0]`
    directly, so putting eBay first unconditionally sent every EUR-priced MTG
    single to eBay US while Cardmarket sat unused further down the list.
    """
    cat = (category or "").lower().strip()
    rgn = (region or "").lower().strip()
    profile = _profile_for(cat)

    q = _qualify(query, profile.suffix)

    # eBay quotes ebay.com in USD; Mercari US in USD. Convert once.
    usd_cap = (
        await _to_site_currency(max_price, max_price_currency, "USD") if max_price else None
    )

    eligible = _eligible_sources(cat, rgn, item_value_eur) & _SEARCHABLE_SOURCES

    builders = {
        "ebay": lambda: _build_ebay_search_url(q, profile.ebay_sacat, usd_cap),
        "tcgplayer": lambda: _build_tcgplayer_search_url(q, cat),
        "cardmarket": lambda: _build_cardmarket_search_url(q, cat),
        "mercari": lambda: _build_mercari_search_url(q, usd_cap),
        "discogs": lambda: _build_discogs_search_url(q),
        "stockx": lambda: _build_stockx_search_url(q),
        "bricklink": lambda: _build_bricklink_search_url(q),
        "yahoo_auctions_jp": lambda: _build_yahoo_auctions_jp_search_url(q),
        "amiami": lambda: _build_amiami_search_url(q),
        "chrono24": lambda: _build_chrono24_search_url(q),
        "catawiki": lambda: _build_catawiki_search_url(q),
        "google": lambda: _build_google_shopping_search_url(q),
    }

    # Category preference first, then anything else eligible, so a category with
    # a partial preference list still surfaces its remaining marketplaces.
    ordered = [s for s in profile.sources if s in eligible]
    ordered += [s for s in builders if s in eligible and s not in ordered]

    links: list[AffiliateLink] = []
    for source in ordered:
        url = builders[source]()
        affiliate_url, _ = build_affiliate_url(url, source)
        links.append(AffiliateLink(
            source=source,
            url=url,
            affiliate_url=affiliate_url or url,
            label=f"Find on {_SOURCE_LABELS.get(source, source)}",
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


class AffiliateClickRequest(BaseModel):
    source: str  # ebay|tcgplayer|cardmarket|mercari|...
    query: Optional[str] = None
    item_key: Optional[str] = None
    category: Optional[str] = None


@router.post("/affiliate-click", dependencies=[Depends(_affiliate_ip_limit)], summary="Record an affiliate-link click for intelligence")
async def record_affiliate_click(
    payload: AffiliateClickRequest,
    user_id: Optional[str] = Depends(get_optional_user_id),
):
    """Record that the user actually tapped an affiliate link.

    Click != /affiliate-links request — the FE renders multiple options and
    the user only opens one. Without this signal we can't tell which
    marketplaces/queries actually convert. Writes to demand_signals.
    """
    try:
        from app.features.data_moat import record_demand_signal
        await record_demand_signal(
            signal_type="affiliate_click",
            category=payload.category,
            item_key=payload.item_key or payload.source,
            query_text=payload.query,
            user_id=user_id,
        )
    except Exception as e:
        logger.debug("[affiliate-click] demand_signal record failed: %s", e)
    return {"ok": True}
