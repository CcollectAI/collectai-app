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

# Category reference list for search (subset of the 36 categories)
CATEGORY_LIST = [
    {"id": "pokemon_tcg", "name": "Pokemon TCG"},
    {"id": "mtg", "name": "Magic: The Gathering"},
    {"id": "yugioh", "name": "Yu-Gi-Oh!"},
    {"id": "sports_cards", "name": "Sports Cards"},
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
    {"id": "kpop", "name": "K-pop"},
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

    items = []
    catalog = []
    users = []
    events = []

    try:
        async with pool.acquire() as conn:
            # Search items (user's own collection)
            item_rows = await conn.fetch(
                """SELECT id, name, category, image_url, price
                   FROM items
                   WHERE user_id = $1 AND name ILIKE $2
                   LIMIT $3""",
                user_id,
                like_pattern,
                limit,
            )
            items = [dict(r) for r in item_rows] if item_rows else []

            # Search catalog items (category_items — public catalog)
            # R50k: image_url kept backend-only; API returns has_reference_image only
            catalog_rows = await conn.fetch(
                """SELECT id, category, item_key, title, brand,
                          (image_url IS NOT NULL) AS has_reference_image
                   FROM category_items
                   WHERE title ILIKE $1
                   ORDER BY title ASC
                   LIMIT $2""",
                like_pattern,
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

            # Search events
            event_rows = await conn.fetch(
                """SELECT id, title, start_date, location, category, status
                   FROM events
                   WHERE title ILIKE $1 AND status != 'cancelled'
                   LIMIT $2""",
                like_pattern,
                limit,
            )
            events = [dict(r) for r in event_rows] if event_rows else []

    except Exception as e:
        logger.warning("unified_search DB error: %s", e)

    # Convert non-serializable types
    for lst in [items, catalog, users, events]:
        for row in lst:
            for k, v in row.items():
                if hasattr(v, "isoformat"):
                    row[k] = v.isoformat()
                elif hasattr(v, "hex"):
                    row[k] = str(v)

    # Record demand signal with geo enrichment (best-effort)
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
    except Exception as e:
        logger.debug("[search] demand signal recording failed: %s", e)

    return {
        "items": items,
        "catalog": catalog,
        "users": users,
        "events": events,
        "categories": categories,
    }
