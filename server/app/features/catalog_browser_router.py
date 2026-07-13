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
    set_code: Optional[str] = Query(
        None,
        max_length=200,
        description="Filter to a single set/collection (raw set_code). Drives the set-detail grid.",
    ),
    brand: Optional[str] = Query(
        None,
        max_length=200,
        description="Filter to a single brand. Drives the brand-detail grid (e.g. watches).",
    ),
    priced_only: bool = Query(
        False,
        description=(
            "Only return items that have a recent (<=180d) market comp in "
            "market_hits. Used by the New-in-Catalog carousel so it never "
            "renders price-less items."
        ),
    ),
    sort: Optional[str] = Query(
        None,
        pattern=r"^(title|value|newest|set)$",
        description=(
            "Sort order. `value` (highest estimated price first) implies "
            "priced_only — only items with a recent comp can be ranked by "
            "price. `newest` = catalog ingest recency, `set` = set_code "
            "grouping, default `title`. Drives the category-page overview "
            "rail chips (All / Most valuable / Newest / By set)."
        ),
    ),
):
    """Browse items in the category_items catalog for a given category."""
    pool = get_pool()
    if pool is None:
        raise error_response(503, "Database not available", code="DB_UNAVAILABLE")

    # ORDER BY whitelist (never interpolate user input directly).
    _ci_order = {
        "title": "ci.title ASC",
        "newest": "ci.created_at DESC NULLS LAST, ci.title ASC",
        "set": "ci.set_code ASC NULLS LAST, ci.title ASC",
    }
    order_by = _ci_order.get(sort or "title", "ci.title ASC")

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

    if set_code and set_code.strip():
        conditions.append(f"ci.set_code = ${idx}")
        params.append(set_code.strip())
        idx += 1

    if brand and brand.strip():
        conditions.append(f"ci.brand = ${idx}")
        params.append(brand.strip())
        idx += 1

    where = " AND ".join(conditions)

    if sort == "value":
        # "Most valuable" reads the precomputed top-60-per-category matview
        # (mv_category_top_value, refreshed daily 03:10 UTC by pg_cron job
        # 'refresh-mv-category-top-value'). The naive per-request approach —
        # a price lateral evaluated for EVERY catalog item before sorting —
        # was O(catalog size × partition probes): pokemon 21s, mtg 25k items
        # blew the pooler's 30s cap and 500'd (measured 2026-06-05). The
        # matview read is O(limit). Depth is capped at 60 ranked items per
        # category; `total` stays the full catalog count ("what exists").
        total = await pool.fetchval(
            f"SELECT count(*) FROM category_items ci WHERE {where}",
            *params,
        ) or 0
        rows = await pool.fetch(
            f"""
            SELECT ci.id, ci.category, ci.item_key, ci.title, ci.brand,
                   ci.rarity, ci.notes, ci.image_url, ci.external_id,
                   ci.set_code, tv.price_eur AS estimated_price
            FROM public.mv_category_top_value tv
            JOIN category_items ci ON ci.id = tv.catalog_item_id
            WHERE tv.category = $1 AND {where}
            ORDER BY tv.rn ASC
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
            total=total,
            limit=limit,
            offset=offset,
            category_id=category_id,
        )

    if priced_only:
        # INNER-join the precomputed price matview so ONLY items with a price
        # within 180d are returned — the price becomes a filter, not a
        # post-fetch decoration. Only title/newest/set sorts reach this branch
        # (sort=value returns from mv_category_top_value above).
        #
        # mv_catalog_item_price (category, item_key, price_eur) holds the latest
        # comp per catalog item, rebuilt nightly at 00:00 UTC by pg_cron job
        # 'refresh-mv-catalog-item-price'. Reading it is an index lookup on the
        # matview's unique (category, item_key) key — NOT a per-row lateral over
        # the partitioned market_hits table on every request (that was the
        # 1.4s-per-30-items hot path; replaced 2026-06-15). `total` is the full
        # catalog size for the category (cheap index-only count) — the overview
        # rail displays "what exists" and its callers do not paginate.
        total = await pool.fetchval(
            f"SELECT count(*) FROM category_items ci WHERE {where}",
            *params,
        ) or 0
        rows = await pool.fetch(
            f"""
            SELECT ci.id, ci.category, ci.item_key, ci.title, ci.brand,
                   ci.rarity, ci.notes, ci.image_url, ci.external_id,
                   ci.set_code, mp.price_eur AS estimated_price
            FROM category_items ci
            JOIN public.mv_catalog_item_price mp
              ON mp.category = ci.category AND mp.item_key = ci.item_key
            WHERE {where}
            ORDER BY {order_by}
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
            total=total,
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
        ORDER BY {order_by}
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
                -- Prices come from mv_catalog_item_price (category, item_key,
                -- price_eur) — the latest comp per catalog item, rebuilt
                -- nightly at 00:00 UTC by pg_cron 'refresh-mv-catalog-item-price'.
                -- This is a unique-index lookup on the matview, replacing the
                -- former per-request lateral over the partitioned market_hits
                -- table (~1.4s for 30 items). Items absent from the matview
                -- simply have no recent comp; they fall back to null price.
                SELECT mp.item_key, mp.price_eur AS price
                FROM public.mv_catalog_item_price mp
                WHERE mp.category = $1
                  AND mp.item_key = ANY($2)
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


@router.get(
    "/catalog/{category_id}/items/{item_key}/price",
    summary="Market-value detail (median + comp count) for a single catalog item",
)
async def get_catalog_item_price(category_id: str, item_key: str) -> dict:
    """Return market-value detail for one catalog item.

    Backs the museum detail screen's MARKET VALUE block. Rather than a single
    latest comp (which can be an outlier — e.g. a cheap listing), this returns
    a robust MEDIAN over the last 180d of comps plus the comp COUNT that backs
    it, so the screen can show "Based on N recent comps" for credibility. Falls
    back to the latest comp when there aren't enough (<3) to median.

    Reads the compact `market_hits_daily` rollup (one row per item/day) rather
    than raw `market_hits`, so the 180d pricing window survives raw-partition
    retention (which now drops market_hits sooner). comps_count is the exact sum
    of daily counts; median_price is the median-of-daily-medians (robust, and a
    negligible shift from median-of-all-comps for a market-value display); latest
    is the most recent day's latest comp. Rollup lags live comps by ≤1 day (the
    nightly job re-rolls the last 2 days), which is fine for a 180d value.
    """
    pool = get_pool()
    if pool is None:
        raise error_response(503, "Database not available", code="DB_UNAVAILABLE")
    item_ref = f"{category_id}:{item_key}"
    row = await pool.fetchrow(
        """
        SELECT
            COALESCE(SUM(comps_count), 0) AS comps_count,
            percentile_cont(0.5) WITHIN GROUP (ORDER BY median_price) AS median_price,
            (ARRAY_AGG(latest_price ORDER BY latest_seen_at DESC))[1] AS latest_price
        FROM market_hits_daily
        WHERE item_ref = $1
          AND day > (current_date - interval '180 days')
          AND median_price IS NOT NULL
        """,
        item_ref,
    )
    comps = int(row["comps_count"]) if row and row["comps_count"] else 0
    median = float(row["median_price"]) if row and row["median_price"] is not None else None
    latest = float(row["latest_price"]) if row and row["latest_price"] is not None else None
    # Prefer the robust median once enough comps back it; else the latest comp.
    estimated = median if (comps >= 3 and median is not None) else latest
    return {
        "category": category_id,
        "item_key": item_key,
        "estimated_price": estimated,
        "median_price": median,
        "latest_price": latest,
        "comps_count": comps,
    }


# ---------------------------------------------------------------------------
# GET /catalog/top-movers — biggest market price movers (gainers/losers)
# ---------------------------------------------------------------------------

class TopMoverItem(BaseModel):
    item_ref: str
    category: str
    item_key: Optional[str] = None
    title: Optional[str] = None
    brand: Optional[str] = None
    set_code: Optional[str] = None
    image_url: Optional[str] = None
    last_price: float
    med_7d: Optional[float] = None
    med_30d: Optional[float] = None
    delta_pct_7d: Optional[float] = None
    delta_pct_30d: Optional[float] = None
    comps_30d: int = 0
    in_catalog: bool = False


class TopMoversResponse(BaseModel):
    movers: list[TopMoverItem]
    direction: str
    window: str


@router.get(
    "/catalog/top-movers",
    response_model=TopMoversResponse,
    summary="Biggest market price movers (gainers/losers) from the market_hits_daily rollup",
)
async def get_top_movers(
    direction: str = Query(
        "gainers",
        pattern=r"^(gainers|losers)$",
        description="`gainers` = biggest price increases, `losers` = biggest decreases.",
    ),
    window: str = Query(
        "7d",
        pattern=r"^(7d|30d)$",
        description="Change window used for ranking and the headline delta.",
    ),
    categories: Optional[str] = Query(
        None,
        max_length=500,
        description=(
            "Comma-separated category filter (e.g. `mtg,pokemon`). Drives the "
            "app's followed-categories default; omit for a whole-catalog list."
        ),
    ),
    limit: int = Query(20, ge=1, le=100),
):
    """Ranked market movers, served from the `mv_market_top_movers` MV.

    The MV pre-computes per-item 7d/30d median deltas off the `market_hits_daily`
    rollup (credibility floors: >=5 comps, >=3 active days, recent activity,
    swings capped at +/-500%) and LEFT JOINs `category_items` for display
    metadata. `gainers` orders by the window delta DESC (positive only),
    `losers` ASC (negative only). Refreshed nightly (cron `refresh-mv-market-top-movers`).
    """
    pool = get_pool()
    if pool is None:
        raise error_response(503, "Database not available", code="DB_UNAVAILABLE")

    delta_col = "delta_pct_7d" if window == "7d" else "delta_pct_30d"
    if direction == "gainers":
        order, sign = "DESC", ">"
    else:
        order, sign = "ASC", "<"

    where = [f"{delta_col} IS NOT NULL", f"{delta_col} {sign} 0"]
    params: list[Any] = []
    if categories:
        cats = [c.strip().lower() for c in categories.split(",") if c.strip()]
        if cats:
            params.append(cats)
            where.append(f"category = ANY(${len(params)})")
    params.append(limit)

    sql = f"""
        SELECT item_ref, category, item_key, title, brand, set_code, image_url,
               last_price, med_7d, med_30d, delta_pct_7d, delta_pct_30d,
               comps_30d, in_catalog
        FROM mv_market_top_movers
        WHERE {' AND '.join(where)}
        ORDER BY {delta_col} {order}
        LIMIT ${len(params)}
    """
    rows = await pool.fetch(sql, *params)

    def _f(v: Any) -> Optional[float]:
        return float(v) if v is not None else None

    movers = [
        TopMoverItem(
            item_ref=r["item_ref"],
            category=r["category"],
            item_key=r["item_key"],
            title=r["title"],
            brand=r["brand"],
            set_code=r["set_code"],
            image_url=r["image_url"],
            last_price=_f(r["last_price"]) or 0.0,
            med_7d=_f(r["med_7d"]),
            med_30d=_f(r["med_30d"]),
            delta_pct_7d=_f(r["delta_pct_7d"]),
            delta_pct_30d=_f(r["delta_pct_30d"]),
            comps_30d=int(r["comps_30d"]) if r["comps_30d"] is not None else 0,
            in_catalog=bool(r["in_catalog"]),
        )
        for r in rows
    ]
    return TopMoversResponse(movers=movers, direction=direction, window=window)


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
    group_by: str = Query(
        "set",
        pattern=r"^(set|brand)$",
        description=(
            "Grouping dimension: 'set' (set_code, default) or 'brand'. "
            "Brand-centric categories (e.g. watches, where set_code is "
            "near-unique per item) group by brand instead."
        ),
    ),
):
    """Catalog-derived collections for a category, grouped by set_code or brand.

    Drives the category page's "Browse by Set / Brand" rail. This is a
    DISCOVERY view computed from the curated catalog (category_items),
    NOT from any single user's ownership — category pages are
    exploratory by design. Counts are live item counts; cover_image is
    the first available reference image in the group (may be null for
    categories without catalog images).
    """
    pool = get_pool()
    if pool is None:
        raise error_response(503, "Database not available", code="DB_UNAVAILABLE")

    # Read the pre-aggregated mv_catalog_collections rollup instead of a live
    # GROUP BY over all of a category's items. The live aggregate cold-hits at
    # 1.6-2.1s (scans ~20K rows) vs <60ms indexed read here; the MV refreshes
    # nightly (pg_cron refresh-mv-catalog-collections, 00:05 UTC) — the catalog
    # only changes on nightly ingest, so the <=1d lag is invisible. Mirrors
    # mv_catalog_item_price. dim is pattern-validated (set|brand).
    dim = "brand" if group_by == "brand" else "set"
    rows = await pool.fetch(
        """
        SELECT grp, total_items, cover_image
        FROM mv_catalog_collections
        WHERE category = $1 AND dim = $2
        ORDER BY total_items DESC, grp
        LIMIT $3
        """,
        category_id,
        dim,
        limit,
    )

    collections = [
        CatalogCollection(
            collection_key=r["grp"],
            # Brands are already display-ready; only set codes need humanizing.
            display_name=r["grp"] if group_by == "brand" else _humanize_set_code(r["grp"]),
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
