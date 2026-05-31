"""
Catalog Browser Router.

Public endpoints for browsing the category_items catalog:
  GET /catalog/{category_id}/items  — paginated, searchable catalog browse

Progress tracking (authenticated):
  PATCH /items/{item_id}/progress   — update progress_status, progress_pct, progress_notes
  GET   /items/{item_id}/progress   — get progress for an item
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.db import get_pool
from app.errors import error_response
from app.rate_limit import per_user_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Catalog Browser"])

# Note: browse_catalog_items is public (no auth) and protected by the global
# IP-based rate limit middleware. per_user_rate_limit is used only on
# authenticated endpoints below.
_catalog_progress_limit = per_user_rate_limit(60, window_seconds=60, scope="catalog_progress")


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class CatalogItem(BaseModel):
    id: str
    category: str
    item_key: str
    title: str
    brand: Optional[str] = None
    rarity: Optional[str] = None
    notes: Optional[str] = None
    has_reference_image: bool = False  # retained for back-compat with older clients
    # image_url is a canonical card-CDN reference (Scryfall / ygoprodeck /
    # pokemontcg.io). Re-exposed to the app so catalog browse + New-in-Catalog
    # can render thumbnails. ~61% of the catalog is populated; null otherwise
    # (clients fall back to a placeholder).
    image_url: Optional[str] = None
    external_id: Optional[str] = None
    set_code: Optional[str] = None
    estimated_price: Optional[float] = None


class CatalogBrowseResponse(BaseModel):
    items: list[CatalogItem]
    total: int
    limit: int
    offset: int
    category_id: str


class CatalogCollection(BaseModel):
    # collection_key is the raw set_code; display_name is humanized for the UI.
    collection_key: str
    display_name: str
    total_items: int = 0
    cover_image: Optional[str] = None


class CatalogCollectionsResponse(BaseModel):
    collections: list[CatalogCollection]
    total: int
    category_id: str


class ProgressUpdateRequest(BaseModel):
    progress_status: Optional[str] = Field(
        None,
        pattern=r"^(unread|reading|read|unplayed|playing|played|completed)$",
    )
    progress_pct: Optional[int] = Field(None, ge=0, le=100)
    progress_notes: Optional[str] = Field(None, max_length=2000)


class ProgressResponse(BaseModel):
    item_id: str
    progress_status: Optional[str] = None
    progress_pct: Optional[int] = None
    progress_notes: Optional[str] = None


# ---------------------------------------------------------------------------
# GET /catalog/{category_id}/items — browse catalog items
# ---------------------------------------------------------------------------

@router.get(
    "/catalog/{category_id}/items",
    response_model=CatalogBrowseResponse,
)
async def browse_catalog_items(
    category_id: str,
    q: Optional[str] = Query(None, max_length=200, description="Search query"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    rarity: Optional[str] = Query(None, description="Filter by rarity tier"),
    priced_only: bool = Query(
        False,
        description=(
            "Only return items that have a recent (<=180d) market comp in "
            "market_hits. Used by the New-in-Catalog carousel so it never "
            "renders price-less items."
        ),
    ),
):
    """Browse items in the category_items catalog for a given category."""
    pool = get_pool()
    if pool is None:
        raise error_response(503, "Database not available", code="DB_UNAVAILABLE")

    # Build query conditions (all qualified with the `ci` alias so the
    # priced_only branch below can join market_hits on the same predicate set).
    conditions = ["ci.category = $1"]
    params: list[Any] = [category_id]
    idx = 2

    if q and q.strip():
        conditions.append(f"ci.title ILIKE ${idx}")
        params.append(f"%{q.strip()}%")
        idx += 1

    if rarity and rarity.strip():
        conditions.append(f"ci.rarity = ${idx}")
        params.append(rarity.strip())
        idx += 1

    where = " AND ".join(conditions)

    if priced_only:
        # INNER-join the latest-comp lateral so ONLY items with a price within
        # 180d are returned — the price becomes a filter, not a post-fetch
        # decoration. LIMIT lets the planner short-circuit the scan. The
        # seen_at floor + category filter keep partition pruning intact (see
        # the price-map query below). Exact total is intentionally skipped:
        # the only caller (New-in-Catalog) does not paginate, so total just
        # reflects the returned page.
        rows = await pool.fetch(
            f"""
            SELECT ci.id, ci.category, ci.item_key, ci.title, ci.brand,
                   ci.rarity, ci.notes, ci.image_url, ci.external_id,
                   ci.set_code, mp.price_eur AS estimated_price
            FROM category_items ci
            JOIN LATERAL (
                SELECT price_eur FROM market_hits mh
                WHERE mh.item_ref = (ci.category || ':' || ci.item_key)
                  AND mh.seen_at > now() - interval '180 days'
                ORDER BY mh.seen_at DESC
                LIMIT 1
            ) mp ON TRUE
            WHERE {where}
            ORDER BY ci.title ASC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
            limit,
            offset,
        )
        items = [
            CatalogItem(
                id=str(r["id"]),
                category=r["category"],
                item_key=r["item_key"],
                title=r["title"],
                brand=r["brand"],
                rarity=r["rarity"],
                notes=r["notes"],
                has_reference_image=bool(r["image_url"]),
                image_url=r["image_url"],
                external_id=r["external_id"],
                set_code=r["set_code"],
                estimated_price=float(r["estimated_price"]),
            )
            for r in rows
        ]
        try:
            from app.features.data_moat import record_demand_signal
            await record_demand_signal(
                signal_type="catalog_browsed",
                category=category_id,
                query_text=q,
            )
        except Exception as e:
            logger.debug("[catalog_browser] demand signal recording failed: %s", e)
        return CatalogBrowseResponse(
            items=items,
            total=offset + len(items),
            limit=limit,
            offset=offset,
            category_id=category_id,
        )

    # Count total matching
    total = await pool.fetchval(
        f"SELECT count(*) FROM category_items ci WHERE {where}",
        *params,
    ) or 0

    # Fetch page
    rows = await pool.fetch(
        f"""
        SELECT ci.id, ci.category, ci.item_key, ci.title, ci.brand, ci.rarity,
               ci.notes, ci.image_url, ci.external_id, ci.set_code
        FROM category_items ci
        WHERE {where}
        ORDER BY ci.title ASC
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *params,
        limit,
        offset,
    )

    # Try to fetch estimated prices from price_predictions or market_observations
    item_keys = [r["item_key"] for r in rows]
    price_map: dict[str, float] = {}
    if item_keys:
        try:
            price_rows = await pool.fetch(
                """
                -- market_observations is vestigial (1 row); market_hits is the
                -- canonical comp source (~900K rows). category_items has
                -- (category, item_key); market_hits.item_ref is the
                -- `category:item_key` concatenation.
                --
                -- The `seen_at` floor is load-bearing: market_hits is
                -- partitioned by month, so without a partition-key predicate
                -- the planner Merge-Appends across every monthly partition for
                -- each item_key (~1.4s for 30 items). The 180-day floor lets
                -- it prune to recent partitions only (~96ms). The category
                -- filter both prevents item_key collisions across categories
                -- and narrows the ci scan.
                SELECT ci.item_key, mp.price_eur AS price
                FROM category_items ci
                JOIN LATERAL (
                    SELECT price_eur FROM market_hits mh
                    WHERE mh.item_ref = (ci.category || ':' || ci.item_key)
                      AND mh.seen_at > now() - interval '180 days'
                    ORDER BY mh.seen_at DESC
                    LIMIT 1
                ) mp ON TRUE
                WHERE ci.category = $1
                  AND ci.item_key = ANY($2)
                """,
                category_id,
                item_keys,
            )
            for pr in price_rows:
                price_map[pr["item_key"]] = float(pr["price"])
        except Exception as exc:
            logger.debug("Could not fetch estimated prices: %s", exc)

    items = [
        CatalogItem(
            id=str(r["id"]),
            category=r["category"],
            item_key=r["item_key"],
            title=r["title"],
            brand=r["brand"],
            rarity=r["rarity"],
            notes=r["notes"],
            has_reference_image=bool(r["image_url"]),
            image_url=r["image_url"],
            external_id=r["external_id"],
            set_code=r["set_code"],
            estimated_price=price_map.get(r["item_key"]),
        )
        for r in rows
    ]

    # Record demand signal (best-effort; no user_id/geo — public endpoint)
    try:
        from app.features.data_moat import record_demand_signal
        await record_demand_signal(
            signal_type="catalog_browsed",
            category=category_id,
            query_text=q,
        )
    except Exception as e:
        logger.debug("[catalog_browser] demand signal recording failed: %s", e)

    return CatalogBrowseResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        category_id=category_id,
    )


# ---------------------------------------------------------------------------
# GET /catalog/{category_id}/collections — discovery "Featured Collections"
# ---------------------------------------------------------------------------

def _humanize_set_code(set_code: str) -> str:
    """gundam-wing -> Gundam Wing; base-set-2 -> Base Set 2."""
    return " ".join(w.capitalize() for w in set_code.replace("_", "-").split("-") if w)


@router.get(
    "/catalog/{category_id}/collections",
    response_model=CatalogCollectionsResponse,
)
async def browse_catalog_collections(
    category_id: str,
    limit: int = Query(20, ge=1, le=100),
):
    """Catalog-derived collections for a category, grouped by set_code.

    Drives the category page's "Featured Collections" rail. This is a
    DISCOVERY view computed from the curated catalog (category_items),
    NOT from any single user's ownership — category pages are
    exploratory by design. Counts are live item counts; cover_image is
    the first available reference image in the set (may be null for
    categories without catalog images).
    """
    pool = get_pool()
    if pool is None:
        raise error_response(503, "Database not available", code="DB_UNAVAILABLE")

    rows = await pool.fetch(
        """
        SELECT set_code,
               COUNT(*) AS total_items,
               (ARRAY_AGG(image_url) FILTER (
                   WHERE image_url IS NOT NULL AND image_url <> ''
               ))[1] AS cover_image
        FROM category_items
        WHERE category = $1
          AND set_code IS NOT NULL
          AND set_code <> ''
        GROUP BY set_code
        ORDER BY COUNT(*) DESC, set_code
        LIMIT $2
        """,
        category_id,
        limit,
    )

    collections = [
        CatalogCollection(
            collection_key=r["set_code"],
            display_name=_humanize_set_code(r["set_code"]),
            total_items=int(r["total_items"]),
            cover_image=r["cover_image"],
        )
        for r in rows
    ]
    return CatalogCollectionsResponse(
        collections=collections,
        total=len(collections),
        category_id=category_id,
    )


# ---------------------------------------------------------------------------
# PATCH /items/{item_id}/progress — update progress tracking
# ---------------------------------------------------------------------------

@router.patch(
    "/items/{item_id}/progress",
    response_model=ProgressResponse,
)
async def update_item_progress(
    item_id: str,
    req: ProgressUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_catalog_progress_limit),
):
    """Update reading/play progress for an item owned by the current user."""
    pool = get_pool()
    if pool is None:
        raise error_response(503, "Database not available", code="DB_UNAVAILABLE")

    # Verify item belongs to user
    owner = await pool.fetchval(
        "SELECT user_id FROM items WHERE id = $1::uuid",
        item_id,
    )
    if not owner:
        raise error_response(404, "Item not found", code="NOT_FOUND")
    if str(owner) != user_id:
        raise error_response(403, "Not your item", code="FORBIDDEN")

    # Build SET clause
    sets: list[str] = []
    params: list[Any] = []
    idx = 1

    if req.progress_status is not None:
        sets.append(f"progress_status = ${idx}")
        params.append(req.progress_status)
        idx += 1
    if req.progress_pct is not None:
        sets.append(f"progress_pct = ${idx}")
        params.append(req.progress_pct)
        idx += 1
    if req.progress_notes is not None:
        sets.append(f"progress_notes = ${idx}")
        params.append(req.progress_notes)
        idx += 1

    if not sets:
        raise error_response(400, "No fields to update", code="VALIDATION_ERROR")

    sets.append(f"updated_at = now()")

    await pool.execute(
        f"UPDATE items SET {', '.join(sets)} WHERE id = ${idx}::uuid AND user_id = ${idx + 1}::uuid",
        *params,
        item_id,
        user_id,
    )

    # Fetch updated values
    row = await pool.fetchrow(
        "SELECT progress_status, progress_pct, progress_notes FROM items WHERE id = $1::uuid",
        item_id,
    )

    return ProgressResponse(
        item_id=item_id,
        progress_status=row["progress_status"] if row else None,
        progress_pct=row["progress_pct"] if row else None,
        progress_notes=row["progress_notes"] if row else None,
    )


# ---------------------------------------------------------------------------
# GET /items/{item_id}/progress — get progress for an item
# ---------------------------------------------------------------------------

@router.get(
    "/items/{item_id}/progress",
    response_model=ProgressResponse,
)
async def get_item_progress(
    item_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get reading/play progress for an item owned by the current user."""
    pool = get_pool()
    if pool is None:
        raise error_response(503, "Database not available", code="DB_UNAVAILABLE")

    row = await pool.fetchrow(
        "SELECT user_id, progress_status, progress_pct, progress_notes FROM items WHERE id = $1::uuid",
        item_id,
    )
    if not row:
        raise error_response(404, "Item not found", code="NOT_FOUND")
    if str(row["user_id"]) != user_id:
        raise error_response(403, "Not your item", code="FORBIDDEN")

    return ProgressResponse(
        item_id=item_id,
        progress_status=row["progress_status"],
        progress_pct=row["progress_pct"],
        progress_notes=row["progress_notes"],
    )


# ---------------------------------------------------------------------------
# POST /catalog/match — match a user-supplied (title, category) against the
# catalog and return the best-scoring item_key. Used by app/add-manual.tsx
# so manually-added items can populate items.canonical_key the same way
# QuickScan-added items do (via the catalog_match_key route param). Without
# this, manual items ship with canonical_key=null and every Premium JOIN
# (price_trend, item_history, dossier) returns empty for them. Wired
# 2026-05-02 to close the second leg of the canonical_key writer story.
# ---------------------------------------------------------------------------

_catalog_match_limit = per_user_rate_limit(30, window_seconds=60, scope="catalog_match")


class CatalogMatchRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    category: str = Field(..., min_length=1, max_length=64)
    # Optional hints from the FE form to improve match accuracy
    brand: Optional[str] = Field(None, max_length=128)
    set_code: Optional[str] = Field(None, max_length=64)


class CatalogMatchHit(BaseModel):
    item_key: Optional[str] = None
    catalog_item_id: Optional[str] = None
    title: Optional[str] = None
    match_score: float = 0.0
    brand: Optional[str] = None
    set_code: Optional[str] = None
    rarity: Optional[str] = None
    image_url: Optional[str] = None


class CatalogMatchResponse(BaseModel):
    # Top match — the FE writes this to canonical_key when match_score >= 0.6.
    # null when no match (FE writes canonical_key=null).
    best: Optional[CatalogMatchHit] = None
    alternatives: list[CatalogMatchHit] = Field(default_factory=list)


@router.post(
    "/catalog/match",
    response_model=CatalogMatchResponse,
    dependencies=[Depends(_catalog_match_limit)],
    summary="Match a manual item entry against the catalog",
)
async def match_catalog(
    payload: CatalogMatchRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Match (title, category) against category_items via the same
    catalog-matching pipeline that QuickScan uses. Returns the best hit
    plus up to 4 alternatives. Score >= 0.75 = strong, >= 0.6 = probable."""
    pool = get_pool()
    if pool is None:
        return CatalogMatchResponse()

    try:
        # Lazy import — catalog_matching pulls in heavy intake dependencies.
        from app.agents.intake.catalog_matching import _match_catalog_items
    except Exception as e:
        logger.warning("[catalog_match] import failed: %s", e)
        return CatalogMatchResponse()

    try:
        matches = await _match_catalog_items(
            category_id=payload.category,
            suggested_name=payload.title,
            search_keywords=[],
            brand=payload.brand,
            set_code=payload.set_code,
            pool=pool,
            extracted_attributes=None,
        )
    except Exception as e:
        # Don't fail the form save just because matching errored. The FE
        # falls back to canonical_key=null gracefully (Premium features
        # remain dark for that item until it's matched another way).
        logger.warning("[catalog_match] match call failed: %s", e)
        return CatalogMatchResponse()

    if not matches:
        return CatalogMatchResponse()

    def _to_hit(m: dict) -> CatalogMatchHit:
        return CatalogMatchHit(
            item_key=m.get("item_key"),
            catalog_item_id=m.get("catalog_item_id"),
            title=m.get("title"),
            match_score=float(m.get("match_score", 0.0)),
            brand=m.get("brand"),
            set_code=m.get("set_code"),
            rarity=m.get("rarity"),
            image_url=m.get("image_url"),
        )

    return CatalogMatchResponse(
        best=_to_hit(matches[0]),
        alternatives=[_to_hit(m) for m in matches[1:5]],
    )
