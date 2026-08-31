"""
PriceCharting API caller for the Marketplace Aggregation Agent.

PriceCharting is the industry standard for retro video game pricing.
Also covers consoles, handhelds, and some trading cards.

API docs: https://www.pricecharting.com/api-documentation

Env vars:
    PRICECHARTING_API_KEY - API key from PriceCharting account
"""

from __future__ import annotations

import datetime
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from app.config import PRICECHARTING_API_KEY as _CFG_KEY
from workers.circuit_breaker import pricecharting_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PRICECHARTING_BASE = "https://www.pricecharting.com/api"

# Categories that benefit from PriceCharting data
# ⚠️ THIS LIST ROUTES NOTHING. Verified 2026-08-31: no module reads it. The list
# that actually gates a PriceCharting call is
# `ADAPTER_CATEGORIES["pricecharting"]` in app/agents/marketplace_routing.py,
# and the two are pinned to each other by
# tests/test_pricecharting_categories.py::test_the_two_lists_agree.
#
# Editing this one alone is exactly the mistake that produced it: a list that
# shares the concept but is not the one consumed
# (feedback_same_name_is_not_the_same_thing). Kept as documentation of what the
# adapter can answer, never as a gate.
SUPPORTED_CATEGORIES = [
    "retro_games",
    "retro_handhelds",
    "pokemon",  # Pokemon game cartridges
    "nintendo_merch",  # amiibo pricing
    # Added 2026-08-31. PriceCharting is the ONLY source in this repo whose rows
    # carry a real `ended_at` — an actual completed sale — and it was reaching
    # four categories. Everything below was PROBED before being allowlisted
    # (learning_dont_allowlist_dead_assert_dead), with the `console` value read
    # from the live response rather than guessed:
    #   mtg            "Magic Alpha"                          Black Lotus EUR 61,888
    #   yugioh         "Yugioh Legend Of Blue Eyes..."        Blue-Eyes 1st Ed
    #   lorcana        "Lorcana Fabled" / "Lorcana Promo"     Elsa Snow Queen
    #   one_piece_tcg  "One Piece Promo"                      Monkey D. Luffy
    #   comic_books    "Comic Books Amazing Spider Man"       ASM #300 EUR 425
    #   funko          "Funko Pop Heroes"                     Batman #41
    #
    # ⛔ sportscards was probed and returned ZERO results for
    # "1986 Fleer Michael Jordan". Deliberately NOT added: an allowlist entry
    # for a dead source is indistinguishable from one that works until someone
    # measures it.
    "mtg",
    "yugioh",
    "lorcana",
    "one_piece_tcg",
    "comic_books",
    "funko",
]

# Console name mapping for PriceCharting queries
PLATFORM_MAP: Dict[str, str] = {
    "NES": "nes",
    "SNES": "super-nintendo",
    "N64": "nintendo-64",
    "GameCube": "gamecube",
    "Game Boy": "gameboy",
    "GBA": "gameboy-advance",
    "DS": "nintendo-ds",
    "Genesis": "sega-genesis",
    "Saturn": "sega-saturn",
    "Dreamcast": "sega-dreamcast",
    "PS1": "playstation",
    "PS2": "playstation-2",
    "Xbox": "xbox",
    "Atari": "atari-2600",
    "Wii": "wii",
    "PSP": "psp",
    "PS Vita": "playstation-vita",
}

PRICECHARTING_SOURCE_RELIABILITY = 0.90

# ---------------------------------------------------------------------------
# Free public-website fallback (no API key required)
#
# The PriceCharting *API* needs a paid key. But the public product pages expose
# the same loose/CIB/new/graded prices in HTML, and they serve fine to our EC2
# IP (verified 2026-07-22, HTTP 200). PriceCharting prices are rolling *sold*
# aggregates, so we emit them as sold comps — with sold_at stamped so persist
# writes is_listing=false (market_hits.is_listing = "sold_at IS NULL"). This
# lights up retro_games/retro_handhelds, which had 0 price_predictions because
# the API caller was inert without a key.
# ---------------------------------------------------------------------------

PRICECHARTING_WEB_BASE = "https://www.pricecharting.com"
_WEB_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
# Product-page price cells: <td id="{id}"><span class="price js-price">$X.XX</span></td>
# (id, price_key, condition_label) — one market_hit per priced condition so the
# ridge model gets a condition→price signal.
_PRICE_CELLS = [
    ("used_price", "loose", "used"),
    ("complete_price", "cib", "complete-in-box"),
    ("new_price", "new", "new"),
    ("graded_price", "graded", "graded"),
]
_GAME_LINK_RE = re.compile(r"/game/([a-z0-9\-]+)/([a-z0-9\-]+)")
_TITLE_RE = re.compile(r'itemprop="name"\s+content="([^"]+)"')
_MAX_PRODUCTS_PER_QUERY = 3  # top few search candidates; bounds requests/item

# Relevance guard, layer 1 (database). The fuzzy /search-products endpoint returns
# the closest products across ALL PriceCharting databases, so a query that has no
# exact match in the target database silently returns cross-category junk (a Funko
# search → a Pokemon card, a comic search → a Yugioh card). For categories whose
# PriceCharting `console` path segment carries an unambiguous keyword, we require
# it — a product whose console doesn't contain an allowed token is dropped before
# we fetch its page. Categories absent here rely on layer 2 alone.
_CATEGORY_CONSOLE_ALLOW: Dict[str, tuple[str, ...]] = {
    "funko": ("funko",),
    "comic_books": ("comic",),
    # Added with the categories themselves, 2026-08-31. Every token below was
    # taken from an OBSERVED `console` value, not guessed — a guard built from a
    # guess either drops everything or admits everything, and both look like a
    # working adapter from the outside.
    "mtg": ("magic",),                  # "Magic Alpha"
    "yugioh": ("yugioh",),              # "Yugioh Legend Of Blue Eyes White Dragon"
    "lorcana": ("lorcana",),            # "Lorcana Fabled", "Lorcana Promo"
    "one_piece_tcg": ("one piece", "one-piece"),   # "One Piece Promo"
}

# Relevance guard, layer 2 (product). Layer 1 only proves the result came from the
# right *database* — it says nothing about whether it is the right *product*, and
# within-database fuzzy misses are both common and expensive. Verified 2026-07-23:
# query "Dragon Ball Z - Piccolo (Metallic) #SE" returned "Spider-Man [Metallic] #3
# (Funko Pop Marvel)" — console `funko-pop-marvel` passes layer 1, the match is on
# the single word "Metallic", and its three price cells landed as sold comps worth
# €1369/€1997/€2282 against eBay actives of €8.78. price_predictions then valued an
# €9 Funko at €1997. A wrong comp is worse than no comp: require that the candidate
# actually covers the query's distinctive words.
_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")
_MIN_TOKEN_COVERAGE = 0.5

# Tokens that identify the *database* or are otherwise carried by nearly every
# title, so matching on them proves nothing about product identity. Excluded from
# both sides of the comparison — without this, a query beginning "Funko Pop!
# Animation:" scores 2 free tokens against every console named `funko-pop-*`.
_NOISE_TOKENS = frozenset({
    # Database / format words
    "funko", "pop", "pops", "vinyl", "figure", "figures", "animation", "comic",
    "comics", "book", "books", "card", "cards", "game", "games", "console",
    "edition", "ed", "version", "ver", "the", "and", "for", "with", "official",
    "limited", "exclusive", "collectible", "collectibles", "series", "vol",
    "volume", "no", "new", "set",
    # Variant qualifiers. These describe a FINISH or RELEASE, never the subject,
    # and they are the most repeated words in the catalog — so they are exactly
    # what a fuzzy search latches onto when it cannot find the real product.
    # Probe 2026-07-24: "Piccolo (Metallic) #SE" matched
    # "Freddy Funko as Loki [Metallic] SE" on {metallic, se} alone and passed the
    # guard at 0.67 coverage. Excluding them forces the match onto the subject
    # ("piccolo" vs "loki"), which is the only thing that identifies the product.
    "se", "chase", "metallic", "flocked", "chrome", "diamond", "glitter",
    "glow", "gitd", "sepia", "blacklight", "translucent", "clear", "gold",
    "silver", "special", "variant", "reprint", "newsstand", "signed",
    "cgc", "psa", "bgs", "wata", "vga", "sgc", "graded", "slab", "cib",
    "sealed", "loose", "complete", "boxed", "pal", "ntsc", "jp", "us", "eu",
})

# Graded prices are a different market: a WATA/CGC slab routinely sells for 10-100×
# the loose copy of the same product. Persisting the graded cell as an unqualified
# sold comp is a systematic inflator (condition_grade is not carried through to
# market_hits, so the model cannot tell the tiers apart). Only take it when the
# query is itself asking about a graded copy.
_GRADED_QUERY_RE = re.compile(
    r"\b(psa|cgc|bgs|wata|vga|sgc|graded|slab|slabbed|gem\s*mint)\b", re.IGNORECASE
)


def _significant_tokens(text: str) -> set[str]:
    """Lowercase alphanumeric tokens worth matching on.

    Words need >=2 chars; bare digits are kept at any length. A single digit is
    usually the whole product identity in this domain ("Super Mario Bros 3" vs
    "New Super Mario Bros 2"), and dropping it as "too short" is what let a
    $674 Nintendo 3DS XL bundle match a $11 Famicom cartridge (probe 2026-07-24).
    """
    return {
        tok for tok in _TOKEN_SPLIT_RE.split((text or "").lower())
        if tok and tok not in _NOISE_TOKENS and (len(tok) >= 2 or tok.isdigit())
    }


def _is_relevant(query: str, candidate: str) -> bool:
    """True when `candidate` plausibly IS the product `query` asked for.

    Two conditions:

    1. **Numbers must survive.** Every bare number in the query has to appear in
       the candidate. Issue numbers, Pop numbers and sequel numbers are the
       identity of the product, not a qualifier — "#300" vs "#301" is a different
       comic at a different price, and coverage alone happily accepts the wrong
       one because all the words still match.
    2. **Coverage over the QUERY's tokens** (not Jaccard) must clear
       _MIN_TOKEN_COVERAGE. PriceCharting titles carry extra qualifiers we don't
       want to penalise, but a candidate missing most of what we asked for is a
       different product. At least one non-numeric token must overlap, so a bare
       number can never carry a match on its own.
    """
    q_tokens = _significant_tokens(query)
    if not q_tokens:
        return False
    c_tokens = _significant_tokens(candidate)

    q_nums = {tok for tok in q_tokens if tok.isdigit()}
    if q_nums and not q_nums <= {tok for tok in c_tokens if tok.isdigit()}:
        return False

    overlap = q_tokens & c_tokens
    if not any(not tok.isdigit() for tok in overlap):
        return False
    return len(overlap) / len(q_tokens) >= _MIN_TOKEN_COVERAGE


def _price_from_cell(html: str, td_id: str) -> float:
    """Extract the first $ price inside the <td id={td_id}> cell (0 if none)."""
    cell = re.search(rf'id="{td_id}"[^>]*>(.*?)</td>', html, re.DOTALL)
    if not cell:
        return 0.0
    pm = re.search(r"\$([0-9][0-9,]*\.[0-9]{2})", cell.group(1))
    if not pm:
        return 0.0
    try:
        return float(pm.group(1).replace(",", ""))
    except ValueError:
        return 0.0


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _normalize_product(product: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a PriceCharting product into a standard MarketHit dict."""
    product_name = product.get("product-name", "Unknown")
    console = product.get("console-name", "")

    # PriceCharting prices are in USD cents
    loose = product.get("loose-price", 0) / 100.0 if product.get("loose-price") else 0
    cib = product.get("cib-price", 0) / 100.0 if product.get("cib-price") else 0
    new_price = product.get("new-price", 0) / 100.0 if product.get("new-price") else 0
    graded = product.get("graded-price", 0) / 100.0 if product.get("graded-price") else 0

    # Use CIB as primary price, fall back to loose
    primary_price = cib if cib > 0 else loose

    return {
        "source": "pricecharting",
        "raw_id": f"pricecharting-{product.get('id', '')}",
        "title": f"{product_name} ({console})" if console else product_name,
        "price": primary_price,
        "currency": "USD",
        "source_price": primary_price,
        "source_currency": "USD",
        "url": f"https://www.pricecharting.com/game/{product.get('id', '')}",
        "condition": None,
        "image_url": "",
        "is_sold": False,
        "price_loose": loose,
        "price_cib": cib,
        "price_new": new_price,
        "price_graded": graded,
        "console": console,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class PriceChartingCaller:
    """Async PriceCharting API caller for the marketplace aggregation agent."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or _CFG_KEY
        self._http: Optional[httpx.AsyncClient] = None

    @property
    def configured(self) -> bool:
        # Always usable: with an API key we hit the official API; without one we
        # scrape the free public website (see _search_web). Returning True here
        # is what makes the agent route retro_games/retro_handhelds/etc. to us
        # even with no key — previously this returned bool(api_key)=False and the
        # adapter was silently skipped in _build_search_tasks, so those cats got
        # 0 PriceCharting sold comps (and 0 price_predictions).
        return True

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=20.0)
        return self._http

    async def search(
        self,
        query: str,
        category: str = "retro_games",
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """Search PriceCharting for products matching a query.

        With an API key, uses the official API. Without one, falls back to the
        free public-website scrape (loose/CIB/new/graded prices), so the caller
        is useful out of the box for retro_games et al.
        """
        if not self.has_api_key:
            return await self._search_web(query, category, limit)

        try:
            pricecharting_circuit.check()
        except CircuitOpenError:
            logger.warning("PriceCharting circuit open — skipping")
            return []

        try:
            client = await self._client()
            resp = await client.get(
                f"{PRICECHARTING_BASE}/products",
                params={
                    "t": self.api_key,
                    "q": query,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            pricecharting_circuit.record_success()

            products = data.get("products", [])
            if isinstance(products, dict):
                products = [products]

            return [_normalize_product(p) for p in products[:limit]]

        except Exception as exc:
            pricecharting_circuit.record_failure()
            logger.warning("PriceCharting search error: %s", exc)
            return []

    async def _search_web(
        self,
        query: str,
        category: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Free fallback: scrape the public PriceCharting website (no API key).

        Search → collect /game/{console}/{slug} product links → fetch the top
        few product pages → emit one sold comp per priced condition. sold_at is
        stamped now() (PriceCharting has no per-sale date; the value is a current
        rolling sold aggregate) so persist writes is_listing=false.
        """
        try:
            client = await self._client()
        except Exception as exc:  # pragma: no cover
            logger.warning("PriceCharting web client init failed: %s", exc)
            return []

        headers = {"User-Agent": _WEB_UA}
        try:
            sresp = await client.get(
                f"{PRICECHARTING_WEB_BASE}/search-products",
                params={"q": query, "type": "prices"},
                headers=headers,
                follow_redirects=True,
            )
            sresp.raise_for_status()
            shtml = sresp.text
        except Exception as exc:
            logger.warning("PriceCharting web search error (%s): %s", query[:40], exc)
            return []

        # Search may redirect straight to a product page on an exact match, else
        # it lists results — collect unique (console, slug) either way.
        paths: List[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        redirect_match = _GAME_LINK_RE.search(str(sresp.url))
        if redirect_match:
            key = (redirect_match.group(1), redirect_match.group(2))
            paths.append(key)
            seen.add(key)
        for console, slug in _GAME_LINK_RE.findall(shtml):
            key = (console, slug)
            if key in seen:
                continue
            seen.add(key)
            paths.append(key)
            if len(paths) >= _MAX_PRODUCTS_PER_QUERY:
                break

        # Drop cross-category false positives before fetching product pages: for
        # guarded categories the console path segment must carry an allowed token
        # (see _CATEGORY_CONSOLE_ALLOW). `console` is the raw lowercase-hyphenated
        # segment, e.g. "funko-pop-animation" (kept) vs "pokemon-fusion-strike"
        # (dropped for a funko query).
        allow = _CATEGORY_CONSOLE_ALLOW.get(category)
        if allow:
            paths = [(c, s) for (c, s) in paths if any(tok in c for tok in allow)]

        # Layer 2 — product relevance, pre-fetch. The URL slug carries the product
        # identity, so a mismatch is dropped without spending a page fetch.
        #
        # Scored on the SLUG ALONE, deliberately. Including the console segment
        # lets every product on a platform match a query that names the platform:
        # catalog item "Nintendo Wii" (the console) scored 0.5 against
        # `wii/lego-star-wars-complete-saga` on the shared token "wii" and was
        # valued at Wii *game* prices (€16) — observed in prod 2026-07-24. The
        # console still gates the database via _CATEGORY_CONSOLE_ALLOW above; it
        # must not also vouch for product identity.
        dropped = [
            (c, s) for (c, s) in paths
            if not _is_relevant(query, s)
        ]
        if dropped:
            logger.info(
                "PriceCharting relevance guard dropped %d/%d candidate(s) for %r: %s",
                len(dropped), len(paths), query[:60],
                ", ".join(f"{c}/{s}" for c, s in dropped[:3]),
            )
        paths = [p for p in paths if p not in dropped]
        if not paths:
            return []

        # Graded cells only when the query is about a graded copy — see
        # _GRADED_QUERY_RE. Otherwise a slab price masquerades as a raw sold comp.
        price_cells = [
            cell for cell in _PRICE_CELLS
            if cell[1] != "graded" or _GRADED_QUERY_RE.search(query)
        ]

        # Date-only ISO (YYYY-MM-DD). MUST match one of _parse_sold_date's
        # accepted formats — its full isoformat() "+00:00" variant is NOT parsed
        # there, so sold_at would come back None → is_listing=true (the sold rows
        # would masquerade as listings and the model would ignore them).
        # PriceCharting has no per-sale timestamp anyway; the date is enough.
        sold_at = datetime.date.today().isoformat()
        hits: List[Dict[str, Any]] = []
        for console, slug in paths[:_MAX_PRODUCTS_PER_QUERY]:
            url = f"{PRICECHARTING_WEB_BASE}/game/{console}/{slug}"
            try:
                presp = await client.get(url, headers=headers, follow_redirects=True)
                presp.raise_for_status()
                phtml = presp.text
            except Exception:
                continue
            title_match = _TITLE_RE.search(phtml)
            console_name = console.replace("-", " ").title()
            title = title_match.group(1) if title_match else slug.replace("-", " ").title()

            # Layer 2 again, post-fetch. The rendered product name is the
            # authoritative identity — the slug can be abbreviated or stale, and a
            # search redirect can land on a page whose path never went through the
            # pre-fetch check.
            if not _is_relevant(query, f"{title} {console_name}"):
                logger.info(
                    "PriceCharting relevance guard dropped product %r for query %r",
                    title[:60], query[:60],
                )
                continue

            for td_id, price_key, cond_label in price_cells:
                price = _price_from_cell(phtml, td_id)
                if price <= 0:
                    continue
                hits.append({
                    "source": "pricecharting",
                    # Distinct listing_id per condition so all conditions persist
                    # (dedup is on provider+listing_id) and re-scrapes of the same
                    # product/condition dedup rather than duplicate.
                    "raw_id": f"pricecharting-{console}-{slug}-{price_key}",
                    "title": f"{title} ({console_name})",
                    "price": price,
                    "currency": "USD",
                    "source_price": price,
                    "source_currency": "USD",
                    "url": url,
                    "condition": cond_label,
                    "image_url": "",
                    "is_sold": True,
                    "sold_at": sold_at,
                    "console": console_name,
                })
                if len(hits) >= limit:
                    return hits
        return hits

    async def lookup(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Look up a specific product by PriceCharting ID (API-only)."""
        if not self.has_api_key:
            return None

        try:
            pricecharting_circuit.check()
        except CircuitOpenError:
            return None

        try:
            client = await self._client()
            resp = await client.get(
                f"{PRICECHARTING_BASE}/product",
                params={"t": self.api_key, "id": product_id},
            )
            resp.raise_for_status()
            data = resp.json()
            pricecharting_circuit.record_success()
            return _normalize_product(data)

        except Exception as exc:
            pricecharting_circuit.record_failure()
            logger.warning("PriceCharting lookup error: %s", exc)
            return None

    async def sold_comps(
        self,
        query: str,
        category: str = "retro_games",
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """PriceCharting prices are aggregated from sold data — return as sold comps."""
        results = await self.search(query, category, limit)
        for r in results:
            r["is_sold"] = True
        return results

    async def health_check(self) -> bool:
        if not self.has_api_key:
            return False
        try:
            client = await self._client()
            resp = await client.get(
                f"{PRICECHARTING_BASE}/products",
                params={"t": self.api_key, "q": "mario"},
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
