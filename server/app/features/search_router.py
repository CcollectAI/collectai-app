"""
Unified search router — search across items, users, events, categories.

Endpoints:
- GET /search/unified?q=...&limit=5 — Cross-entity search
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import get_current_user_id
from app.lib.db_helpers import get_db_pool
from app.lib.json_safe import json_safe_rows
from app.rate_limit import per_user_rate_limit

router = APIRouter(prefix="/search", tags=["Search"])
logger = logging.getLogger(__name__)


class UnifiedSearchResponse(BaseModel):
    items: list[dict] = []
    catalog: list[dict] = []
    users: list[dict] = []
    events: list[dict] = []
    categories: list[dict] = []

# Per-user: 60 unified search requests per minute (runs 4 DB queries per call)
_search_user_limit = per_user_rate_limit(60, window_seconds=60, scope="unified_search")

# Category reference list for search (subset of the 36 categories).
#
# EVERY id here is a ROUTE the app pushes as `/categories/<id>`, and the app
# resolves it through `getCategoryById` in `src/data/categories.ts`. An id that
# is not in that file renders "Category not found" — a search result that goes
# nowhere.
#
# Three did, until 2026-08-11: `pokemon_tcg`, `sports_cards` and `kpop`, whose
# real app ids are `pokemon`, `sportscards` and `kpop_merch`. Searching
# "pokemon" — the most likely query this app will ever receive — produced a
# category row that dead-ended.
#
# `scripts/check-search-category-ids.mjs` (npm run check:search-categories,
# wired into verify:prebuild) diffs this list against categories.ts and fails
# on any id the app cannot route to. Add an entry here only if the id exists
# there.
CATEGORY_LIST = [
    {"id": "pokemon", "name": "Pokemon TCG"},
    {"id": "mtg", "name": "Magic: The Gathering"},
    {"id": "yugioh", "name": "Yu-Gi-Oh!"},
    {"id": "sportscards", "name": "Sports Cards"},
    {"id": "funko", "name": "Funko Pop!"},
    {"id": "lego", "name": "LEGO"},
    {"id": "hot_toys", "name": "Hot Toys"},
    {"id": "anime_figures", "name": "Anime Figures"},
    {"id": "gunpla", "name": "Gunpla"},
    {"id": "warhammer", "name": "Warhammer"},
    {"id": "designer_toys", "name": "Designer Toys"},
    {"id": "retro_games", "name": "Retro Games"},
    {"id": "manga", "name": "Manga"},
    {"id": "comic_books", "name": "Comic Books"},
    {"id": "vinyl_records", "name": "Vinyl Records"},
    {"id": "sneakers", "name": "Sneakers"},
    {"id": "watches", "name": "Watches"},
    {"id": "kpop_merch", "name": "K-pop"},
    {"id": "one_piece", "name": "One Piece"},
    {"id": "bluray_steelbook", "name": "Blu-ray Steelbook"},
    {"id": "disney", "name": "Disney"},
    {"id": "taylor_swift", "name": "Taylor Swift"},
    {"id": "nintendo_merch", "name": "Nintendo Merch"},
    {"id": "keycaps", "name": "Keycaps"},
    {"id": "diecast", "name": "Diecast"},
    {"id": "scale_models", "name": "Scale Models"},
    {"id": "anime_bluray", "name": "Anime Blu-ray"},
    {"id": "loungefly", "name": "Loungefly"},
    {"id": "kpop_lightsticks", "name": "K-pop Lightsticks"},
    {"id": "vtuber", "name": "VTuber"},
    {"id": "ghibli", "name": "Studio Ghibli"},
    {"id": "bandai_premium", "name": "Bandai Premium"},
    {"id": "jp_magazine", "name": "Japanese Magazines"},
    {"id": "pop_fandom", "name": "Pop Fandom"},
    {"id": "anime_soundtrack", "name": "Anime Soundtrack"},
    {"id": "theme_park", "name": "Theme Park"},
]


# Upper bound on ANDed search terms. Ten is far past a real product name and
# keeps a pasted paragraph from building a 200-predicate WHERE clause.
LIKE_TERM_LIMIT = 10


@router.get("/unified", response_model=UnifiedSearchResponse)
async def unified_search(
    q: str = "",
    limit: int = 5,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_search_user_limit),
):
    """Search across items, catalog, users, events, and categories."""
    if not q.strip():
        return {"items": [], "catalog": [], "users": [], "events": [], "categories": []}

    query_lower = q.strip().lower()

    # Search categories (static, no DB needed)
    categories = [
        c for c in CATEGORY_LIST
        if query_lower in c["name"].lower() or query_lower in c["id"].lower()
    ][:limit]

    pool = get_db_pool()
    if not pool:
        return {"items": [], "catalog": [], "users": [], "events": [], "categories": categories}

    # Escape LIKE metacharacters to prevent unexpected wildcard matches
    escaped_q = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    like_pattern = f"%{escaped_q}%"

    # EVERY WORD, not the phrase. A single `ILIKE '%rolex daytona%'` requires the
    # words to be adjacent in that order, so it found 5 of the 11 Rolex Daytonas
    # we hold — the 6 it missed are all titled "Rolex COSMOGRAPH Daytona", where
    # one word in between kills the match. Catalogue titles are long and
    # descriptive ("Rolex Cosmograph Daytona Panda Dial Steel (126500LN)"), so
    # this is the normal case, not an edge case.
    #
    # Each term is matched with ILIKE ALL(array) — every term must appear, in any
    # order and anywhere in the title. Bound to LIKE_TERM_LIMIT so a paragraph
    # pasted into the search box cannot turn into an unbounded AND-chain.
    like_terms = [
        f"%{t}%" for t in escaped_q.split() if t
    ][:LIKE_TERM_LIMIT] or [like_pattern]

    # And an ANCHOR term, because `ILIKE ALL(array)` alone cannot use the
    # trigram index. `idx_category_items_title_trgm` (GIN, gin_trgm_ops) is what
    # makes an unanchored `%...%` search viable over 140k catalogue rows; the
    # planner can push a plain `title ILIKE $1` into it, but not an ALL(...)
    # over an array. Measured on prod: ALL-only 229ms, anchor + ALL 24.8ms —
    # the same as the single-phrase query it replaces. A keystroke-driven search
    # cannot afford the difference.
    #
    # The LONGEST term is the anchor: more trigrams means a more selective index
    # probe, and it is the cheapest proxy for selectivity available without
    # statistics. ALL(...) still applies every term, so the anchor only narrows
    # the candidate set — it never changes which rows qualify.
    like_anchor = max(like_terms, key=len)

    items = []
    catalog = []
    users = []
    events = []

    try:
        async with pool.acquire() as conn:
            # Search items (user's own collection). items has no `price`
            # column — `estimated_value` is the FE-facing field.
            item_rows = await conn.fetch(
                """SELECT id, name, category, image_url,
                          estimated_value AS price
                   FROM items
                   WHERE user_id = $1 AND NOT archived AND name ILIKE ALL($2::text[])
                   LIMIT $3""",
                user_id,
                like_terms,
                limit,
            )
            items = [dict(r) for r in item_rows] if item_rows else []

            # Search catalog items (category_items — public catalog)
            # R50k: image_url kept backend-only; API returns has_reference_image only
            # price_eur comes from mv_catalog_item_price — the SAME source the
            # catalog detail page reads (catalog_browser_router). Deliberately not
            # price_predictions: the two disagree (yugioh is dense in predictions
            # and sparse in market hits), and a row that says EUR 12 in search and
            # EUR 30 when tapped is worse than a row with no price.
            #
            # LEFT JOIN, never INNER: filtering to priced rows would make watches
            # and lego return NOTHING, which reads as broken software rather than
            # as missing price data. An unpriced row still tells the user we know
            # the object exists.
            #
            # The matview is a unique-index lookup rebuilt nightly by pg_cron; the
            # lateral over partitioned market_hits it replaced cost ~1.4s for 30
            # items, which a keystroke-driven search cannot afford.
            catalog_rows = await conn.fetch(
                """SELECT ci.id, ci.category, ci.item_key, ci.title, ci.brand,
                          (ci.image_url IS NOT NULL) AS has_reference_image,
                          -- Rounded HERE, not on the client: price_eur is a
                          -- float and asyncpg hands back 642.6399999999999863
                          -- verbatim, which every consumer would have to fix.
                          -- ::float8 is LOAD-BEARING, not cosmetic. round()
                          -- returns numeric, asyncpg maps that to Decimal, and
                          -- `catalog` is an untyped list[dict] so Pydantic would
                          -- have serialised it as the STRING "642.64". The client
                          -- tests `typeof priceEur === 'number'`, so every priced
                          -- row would have rendered "No price yet" — the feature
                          -- would have shipped dead and looked like missing data.
                          round(mp.price_eur::numeric, 2)::float8 AS price_eur
                   FROM category_items ci
                   LEFT JOIN public.mv_catalog_item_price mp
                          ON mp.category = ci.category AND mp.item_key = ci.item_key
                   WHERE ci.title ILIKE $1
                     AND ci.title ILIKE ALL($2::text[])
                   ORDER BY (mp.price_eur IS NULL), ci.title ASC
                   LIMIT $3""",
                like_anchor,
                like_terms,
                limit,
            )
            catalog = [dict(r) for r in catalog_rows] if catalog_rows else []

            # Search users
            user_rows = await conn.fetch(
                """SELECT id, display_name, handle, avatar_url
                   FROM user_public_profiles
                   WHERE display_name ILIKE $1 OR handle ILIKE $1
                   LIMIT $2""",
                like_pattern,
                limit,
            )
            users = [dict(r) for r in user_rows] if user_rows else []

            # Search events. events has no `start_date`; the FE-facing
            # date is `date` (and the precise timestamp is `starts_at`).
            event_rows = await conn.fetch(
                """SELECT id, title, date AS start_date, location, category, status
                   FROM events
                   WHERE title ILIKE ALL($1::text[]) AND status != 'cancelled'
                   LIMIT $2""",
                like_terms,
                limit,
            )
            events = [dict(r) for r in event_rows] if event_rows else []

    except Exception as e:
        logger.warning("unified_search DB error: %s", e)

    # Convert non-serializable types. See app/lib/json_safe.py for why this is
    # a shared helper and not a loop written here: the loop that used to live
    # here tested `hasattr(v, "hex")`, floats have .hex(), and so every price in
    # every search response shipped as a STRING.
    items = json_safe_rows(items)
    catalog = json_safe_rows(catalog)
    users = json_safe_rows(users)
    events = json_safe_rows(events)

    # Record demand signal with geo enrichment (best-effort).
    # If 0 results across every source, ALSO record a separate
    # `no_results_search` signal so search_gap_worker can prioritise it.
    try:
        from app.features.data_moat import record_demand_signal, get_user_geo
        region, country = await get_user_geo(user_id)
        await record_demand_signal(
            signal_type="search_query",
            query_text=q.strip(),
            user_id=user_id,
            region=region,
            country_code=country,
        )
        if not items and not catalog and not users and not events:
            await record_demand_signal(
                signal_type="no_results_search",
                query_text=q.strip(),
                user_id=user_id,
                region=region,
                country_code=country,
            )
    except Exception as e:
        logger.debug("[search] demand signal recording failed: %s", e)

    return {
        "items": items,
        "catalog": catalog,
        "users": users,
        "events": events,
        "categories": categories,
    }
