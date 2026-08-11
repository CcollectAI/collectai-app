"""Favorites — "I saved this", and nothing more.

The whole point of this router is what it does NOT do. It does not write a
watchlist row, it does not set a target price, and it never causes a
notification. See docs/alerts-and-insights.md, "A one-tap 'watch this' control
must set a target": a favourite heart wired to `addWatchlistItem` was built on
the marketplace grid 2026-08-08 and removed the same day, because every row it
wrote had no target and `_check_watchlist_snipes` filters
`WHERE target_price IS NOT NULL AND target_price > 0` — so the rows were inert
while the control's accessibility label promised price-drop alerts. That was the
fourth instance of that writer bug.

Favouriting and watching are therefore two different verbs on two different
tables, which is what lets each one tell the truth:

    heart / favorites   → saved. Promises nothing. Free, unlimited.
    eye   / watchlist   → a target price and a Target Hit alert. Plan-gated.

A row points at a marketplace listing OR a catalogue item, never both
(`favorites_one_target`). The two are genuinely different lifetimes: a listing
is gone when the seller delists it, a catalogue item outlives every listing of
it, which is why the screen has to render a "no longer available" state rather
than dropping the row.
"""
from __future__ import annotations

import logging

import asyncpg
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator, model_validator

from app.auth import get_current_user_id
from app.errors import error_response
from app.lib.db_helpers import get_db_pool
from app.rate_limit import per_user_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/favorites", tags=["Favorites"])

# The heart is a toggle on a scrolling grid, so a member can realistically fire
# a dozen of these in a few seconds without doing anything wrong.
_favorite_limit = per_user_rate_limit(60, window_seconds=60, scope="favorite")


class FavoriteIn(BaseModel):
    """What the heart sends. Exactly one target, mirroring the DB CHECK.

    Validated here as well as in the database because a 422 naming the field is
    a better failure than a 500 carrying a constraint name the client cannot
    read — but the CHECK stays, because this is not the only possible writer.
    """

    listing_id: Optional[str] = None
    # BARE. `canonical_key` is never namespaced; it is `*.item_ref` that carries
    # the `source:` prefix (learning_canonical_key_vs_item_ref_namespace).
    canonical_key: Optional[str] = None
    # SLUG ('mtg'), never a display name ('Magic: The Gathering'). The watchlist
    # writers shipped display names into a slug column and the join died
    # silently for months (learning_join_vocabulary_slug_vs_display_name).
    category: Optional[str] = Field(default=None, max_length=64)

    @field_validator("listing_id")
    @classmethod
    def _listing_id_is_uuid(cls, v: Optional[str]) -> Optional[str]:
        """Reject a malformed id HERE, as 422, rather than letting asyncpg
        raise on the uuid column and surface it as a 500.

        Client input must never be a server error: a 500 says "we broke",
        pollutes error monitoring, and tells the caller nothing about the
        field that was actually wrong.
        """
        if v is None:
            return v
        try:
            UUID(v)
        except (ValueError, AttributeError, TypeError):
            raise ValueError("listing_id must be a UUID")
        return v

    @model_validator(mode="after")
    def _exactly_one_target(self) -> "FavoriteIn":
        targets = [t for t in (self.listing_id, self.canonical_key) if t]
        if len(targets) != 1:
            raise ValueError(
                "provide exactly one of listing_id or canonical_key"
            )
        return self


class FavoriteOut(BaseModel):
    id: str
    listing_id: Optional[str] = None
    canonical_key: Optional[str] = None
    category: Optional[str] = None
    created_at: Optional[str] = None

    # Denormalised for the Favorites screen, so rendering a row costs no second
    # round trip. All three are nullable on purpose: a favourited listing that
    # the seller has since delisted still has a row here, and the screen must be
    # able to say "no longer available" rather than silently dropping something
    # the member saved.
    title: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    image_url: Optional[str] = None
    listing_status: Optional[str] = None


@router.get("", response_model=List[FavoriteOut])
async def list_favorites(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[FavoriteOut]:
    """Everything this member has saved, newest first.

    LEFT JOIN, never INNER: an inner join would make a delisted listing's row
    vanish from the member's own saved list with no explanation. The row is
    theirs; only the listing went away.
    """
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code="DB_UNAVAILABLE")
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT f.id, f.listing_id, f.canonical_key, f.category, f.created_at,
                       -- A catalogue favourite has no listing, so it has no
                       -- listing_title. Without the fallback every such row
                       -- renders as an untitled card — saved, and unreadable.
                       COALESCE(l.listing_title, ci.title) AS listing_title,
                       l.price, l.currency, l.status AS listing_status,
                       -- The SAME image expression the listing browse uses in
                       -- p2p_listing_router (`COALESCE(i.image_url, ci.image_url)`),
                       -- not a second one. `marketplace_listings` has NO
                       -- image_url column of its own: the seller's photo lives
                       -- on items, the catalogue fallback on category_items.
                       -- Two copies of a photo rule drift, and the copy that
                       -- drifts is the one nobody is looking at.
                       COALESCE(i.image_url, ci.image_url) AS image_url
                  FROM public.favorites f
                  LEFT JOIN public.marketplace_listings l ON l.id = f.listing_id
                  -- LEFT JOIN throughout: a favourite must still render when the
                  -- listing is delisted, and when its source item is gone.
                  --
                  -- archived-exempt: items is joined ONLY for the photo, exactly
                  -- as in the listing browse in p2p_listing_router. This read
                  -- counts nothing and owns nothing — it returns the member's
                  -- own favourites, and whether the seller later archived the
                  -- source item has no bearing on whether YOU saved the
                  -- listing. `AND NOT i.archived` here would blank the
                  -- thumbnail rather than drop the row.
                  LEFT JOIN public.items i ON i.id = l.item_id
                  -- item_key/category, and canonical_key is BARE here
                  -- (learning_canonical_key_vs_item_ref_namespace).
                  LEFT JOIN public.category_items ci
                         ON ci.item_key = COALESCE(l.canonical_key, f.canonical_key)
                        AND ci.category = COALESCE(l.category, f.category)
                 WHERE f.user_id = $1
                 ORDER BY f.created_at DESC
                 LIMIT $2 OFFSET $3
                """,
                user_id,
                limit,
                offset,
            )
    except Exception as exc:  # pragma: no cover - surfaced via logs
        logger.error("[favorites] list failed user=%s: %s", user_id, exc)
        raise error_response(500, "Could not load favourites", code="FAVORITES_LIST_FAILED")

    return [
        FavoriteOut(
            id=str(r["id"]),
            listing_id=str(r["listing_id"]) if r["listing_id"] else None,
            canonical_key=r["canonical_key"],
            category=r["category"],
            created_at=r["created_at"].isoformat() if r["created_at"] else None,
            title=r["listing_title"],
            price=float(r["price"]) if r["price"] is not None else None,
            currency=r["currency"],
            image_url=r["image_url"],
            listing_status=r["listing_status"],
        )
        for r in rows
    ]


@router.post("", response_model=FavoriteOut, dependencies=[Depends(_favorite_limit)])
async def add_favorite(
    payload: FavoriteIn,
    user_id: str = Depends(get_current_user_id),
) -> FavoriteOut:
    """Save it. Idempotent — the heart is a toggle, not a counter.

    ON CONFLICT DO UPDATE rather than DO NOTHING: DO NOTHING returns no row, so
    a double-tap would 500 on the RETURNING. Updating `category` in place also
    means a re-favourite repairs a row written before the category was known.
    """
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code="DB_UNAVAILABLE")

    conflict = (
        "(user_id, listing_id) WHERE listing_id IS NOT NULL"
        if payload.listing_id
        else "(user_id, canonical_key) WHERE canonical_key IS NOT NULL"
    )
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                INSERT INTO public.favorites (user_id, listing_id, canonical_key, category)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT {conflict}
                DO UPDATE SET category = COALESCE(EXCLUDED.category, public.favorites.category)
                RETURNING id, listing_id, canonical_key, category, created_at
                """,
                user_id,
                payload.listing_id,
                payload.canonical_key,
                payload.category,
            )
    except asyncpg.exceptions.ForeignKeyViolationError:
        # The listing does not exist. That is the caller naming something that
        # is not there — 404, not "we broke". Reached by favouriting a listing
        # hard-deleted between the grid rendering and the tap landing.
        raise error_response(404, "Listing not found", code="LISTING_NOT_FOUND")
    except Exception as exc:  # pragma: no cover - surfaced via logs
        logger.error("[favorites] add failed user=%s: %s", user_id, exc)
        raise error_response(500, "Could not save favourite", code="FAVORITE_ADD_FAILED")

    return FavoriteOut(
        id=str(row["id"]),
        listing_id=str(row["listing_id"]) if row["listing_id"] else None,
        canonical_key=row["canonical_key"],
        category=row["category"],
        created_at=row["created_at"].isoformat() if row["created_at"] else None,
    )


@router.delete("", status_code=204, dependencies=[Depends(_favorite_limit)])
async def remove_favorite(
    listing_id: Optional[str] = Query(default=None),
    canonical_key: Optional[str] = Query(default=None),
    user_id: str = Depends(get_current_user_id),
) -> None:
    """Un-save it, addressed by TARGET rather than by row id.

    The heart on a card knows what it is looking at; it does not know the id of
    a favorites row it never fetched. Making the client find that id first would
    turn one tap into two round trips, and the miss case — untoggling something
    already gone — is a no-op either way.
    """
    if bool(listing_id) == bool(canonical_key):
        raise error_response(
            422,
            "provide exactly one of listing_id or canonical_key",
            code="FAVORITE_TARGET_INVALID",
        )

    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code="DB_UNAVAILABLE")
    try:
        async with pool.acquire() as conn:
            if listing_id:
                await conn.execute(
                    "DELETE FROM public.favorites WHERE user_id = $1 AND listing_id = $2",
                    user_id,
                    listing_id,
                )
            else:
                await conn.execute(
                    "DELETE FROM public.favorites WHERE user_id = $1 AND canonical_key = $2",
                    user_id,
                    canonical_key,
                )
    except Exception as exc:  # pragma: no cover - surfaced via logs
        logger.error("[favorites] delete failed user=%s: %s", user_id, exc)
        raise error_response(500, "Could not remove favourite", code="FAVORITE_DELETE_FAILED")


@router.get("/ids", response_model=List[str])
async def favorite_ids(
    user_id: str = Depends(get_current_user_id),
) -> List[str]:
    """Just the targets, for filling in the hearts on a grid.

    The marketplace card needs to know whether ITS listing is favourited, and
    asking per card is N requests for one screen. One call, and the client holds
    the set.
    """
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code="DB_UNAVAILABLE")
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT COALESCE(listing_id::text, canonical_key) AS target
                  FROM public.favorites
                 WHERE user_id = $1
                """,
                user_id,
            )
    except Exception as exc:  # pragma: no cover - surfaced via logs
        logger.error("[favorites] ids failed user=%s: %s", user_id, exc)
        raise error_response(500, "Could not load favourites", code="FAVORITE_IDS_FAILED")
    return [r["target"] for r in rows if r["target"]]
