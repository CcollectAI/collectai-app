"""P2P marketplace — member-to-member listings (Stage 1: NO payments).

See docs/P2P_MARKETPLACE_SPEC.md.

Stage 1 scope: a member lists an item they own, other members find it and tap
through to chat. Sparrow never touches funds — that is what keeps PSD2,
chargebacks and most of DAC7 out of scope, and it delivers 100% of the supply
benefit, which is the actual reason this exists.

The load-bearing part is `_publish_supply_hook`: publishing a listing writes a
`market_hits` row so member inventory feeds Target Hit exactly like any scraped
marketplace. Without that this is just a classifieds board.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.errors import error_response
from app.features.pagination import pagination_params
from app.lib.bg_tasks import spawn_bg
from app.lib.db_helpers import get_db_pool
from app.rate_limit import per_user_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/p2p", tags=["P2P Marketplace"])

_listing_write_limit = per_user_rate_limit(20, window_seconds=60, scope="p2p_write")
_report_limit = per_user_rate_limit(10, window_seconds=300, scope="p2p_report")

# `marketplace_listings.marketplace_id` is **TEXT** holding a key like 'ebay',
# NOT a foreign key to `marketplaces.id` (which is bigint). Verified against
# prod 2026-08-06 — the name reads like an FK and is not one. The registry row
# added by the migration is still useful for listing/enabling marketplaces, but
# this value is what goes in the column.
SPARROW_MARKETPLACE_KEY = "sparrow"

# Listing lifecycle. Deliberately small: Stage 1 has no payment states.
# These MUST match marketplace_listings_status_check, which allows exactly:
#   draft | active | sold | expired | delisted | error
# 'withdrawn' was the natural word and is NOT legal — the insert raised
# CheckViolationError. Classic constraint-narrower-than-code
# (learning_db_constraints_narrower_than_code); verified against pg_constraint
# rather than assumed.
_STATUS_ACTIVE = "active"
_STATUS_SOLD = "sold"
_STATUS_DELISTED = "delisted"

# marketplace_listings_format_check allows fixed_price | auction | best_offer.
# NOT 'fixed'. Stage 1 is fixed-price only.
_FORMAT_FIXED = "fixed_price"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ListingCreate(BaseModel):
    """Create a listing from an item the caller owns.

    `item_id` is required: a listing derived from an owned item inherits
    `canonical_key` and `category`, which is what lets it join Target Hit's
    EXACT-identity arm instead of the fuzzy title arm. Free-text listings were
    considered and rejected for Stage 1 — see the spec's open questions.
    """
    item_id: str = Field(..., description="items.id the caller owns")
    price: float = Field(..., gt=0, le=1_000_000)
    currency: str = Field(default="EUR", max_length=3, pattern=r"^[A-Z]{3}$")
    condition_label: Optional[str] = Field(None, max_length=64)
    condition_notes: Optional[str] = Field(None, max_length=2000)
    description: Optional[str] = Field(None, max_length=4000)
    ships_from: Optional[str] = Field(None, max_length=120)
    shipping_cost: Optional[float] = Field(None, ge=0, le=100_000)


class ListingOut(BaseModel):
    id: str
    user_id: str
    item_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    price: float
    currency: str
    condition_label: Optional[str] = None
    category: Optional[str] = None
    canonical_key: Optional[str] = None
    ships_from: Optional[str] = None
    shipping_cost: Optional[float] = None
    # Thumbnail for the marketplace grid. Etsy's finding is unambiguous: the
    # first photo drives the click and click-through drives visibility. A grid
    # without images is just a list.
    #
    # Falls back to the CATALOG image when the seller's item has none. Measured
    # 2026-08-07: 167,276 of 221,391 category_items carry an image, versus 3 of
    # 16 user items — without the fallback the grid is almost entirely
    # placeholders.
    image_url: Optional[str] = None
    # TRUE when image_url came from the catalog, not the seller. The UI MUST
    # label it. A stock photo passed off as the actual item hides condition,
    # which is the one thing a second-hand buyer needs to see — that is how a
    # convenience becomes a misrepresentation. TCGplayer/Cardmarket show
    # catalog scans openly; they never imply it is the seller's copy.
    image_is_catalog: bool = False
    # ── Seller credibility ────────────────────────────────────────────────
    # Stage 1 has no transactions, so no transaction-based trust exists. These
    # are the signals we genuinely have, and in a collector community they are
    # meaningful: a 400-item collection maintained over a year is hard to fake
    # cheaply. Deliberately NOT ratings — with no payment record we cannot
    # verify a trade happened, so a rating would be gameable from day one and
    # would imply vetting we do not perform.
    seller_name: Optional[str] = None
    seller_since: Optional[datetime] = None
    seller_collection_size: int = 0
    seller_active_listings: int = 0
    # ── Demand signal — the thing no generic marketplace can show ─────────
    # We know what members WANT (watchlist rows with a target price), so a
    # seller can be told there is real demand before they list. Facebook has
    # to infer intent from a feed; eBay waits for a search. This is
    # pre-declared.
    #
    # `watchers_above_price` counts watchers whose target is >= the asking
    # price, i.e. people who would get a Target Hit for this listing right
    # now. That is the number that actually predicts a sale.
    watchers: int = 0
    watchers_above_price: int = 0
    status: str
    created_at: Optional[datetime] = None
    is_mine: bool = False


class ListingListResponse(BaseModel):
    listings: List[ListingOut]


class ReportCreate(BaseModel):
    reason: str = Field(..., min_length=3, max_length=120)
    detail: Optional[str] = Field(None, max_length=2000)


# ---------------------------------------------------------------------------
# Supply hook — the reason this feature exists
# ---------------------------------------------------------------------------

async def _publish_supply_hook(listing_id: str) -> None:
    """Write a `market_hits` row so a member listing can fire a Target Hit.

    Runs fire-and-forget via spawn_bg AFTER the listing commits: the seller
    should not wait on it, and a supply-hook failure must never fail the
    publish. Never a bare create_task — that GC-drops mid-await.

    Three details that are easy to get wrong:

    * `item_ref` must be **namespaced** (`mtg:sum-283-bayou`) while
      `items.canonical_key` is stored **bare**. Getting this backwards is what
      made 44 joins match nothing for four months
      (learning_canonical_key_vs_item_ref_namespace).
    * `is_listing = TRUE` and a non-NULL `url` are exactly what the snipe query
      requires; without both, the row is invisible to Target Hit.
    * The URL is an https universal link, not `sparrow://`. `build_affiliate_url`
      rejects non-http(s) schemes with a warning, and an https link also works
      when a seller shares it outside the app.
    """
    pool = get_db_pool()
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT l.id, l.listing_title, l.price, l.currency,
                       l.canonical_key, l.category
                FROM public.marketplace_listings l
                WHERE l.id = $1::uuid
                  AND l.status = $2
                  AND l.delisted_at IS NULL
                """,
                listing_id, _STATUS_ACTIVE,
            )
            if row is None or not row["canonical_key"] or not row["category"]:
                # No canonical identity => it could only ever match the fuzzy
                # title arm, which is where the false-positive risk lives.
                # Skip rather than write a weakly-identified buyable row.
                logger.info(
                    "[p2p] supply hook skipped for %s (no canonical identity)",
                    listing_id,
                )
                return

            from app.lib.fx_service import convert_to_eur
            price_eur = await convert_to_eur(float(row["price"]), row["currency"] or "EUR")

            item_ref = f"{row['category']}:{row['canonical_key']}"
            await conn.execute(
                """
                INSERT INTO public.market_hits
                    (provider, source, marketplace, listing_id, title,
                     price, currency, price_eur, url, normalized_key, item_ref,
                     category, observed_at, seen_at, is_listing)
                -- WHERE NOT EXISTS, not ON CONFLICT: market_hits' only unique
                -- key is (id, seen_at) and `id` comes from a sequence, so a
                -- conflict can never fire and a retried publish would write a
                -- SECOND buyable row for the same listing — Target Hit would
                -- then surface one listing twice. Same guard persist_comps_to_db
                -- uses.
                SELECT 'sparrow', 'sparrow', 'sparrow', $1, $2,
                       $3, $4, $5, $6, $7, $7,
                       $8, now(), now(), TRUE
                WHERE NOT EXISTS (
                    SELECT 1 FROM public.market_hits
                    WHERE provider = 'sparrow' AND listing_id = $1
                )
                """,
                str(listing_id),
                row["listing_title"],
                float(row["price"]),
                row["currency"] or "EUR",
                price_eur,
                f"https://sparrowcollect.com/l/{listing_id}",
                item_ref,
                row["category"],
            )
            logger.info("[p2p] supply hook wrote market_hits for %s", listing_id)
    except Exception as exc:
        logger.warning("[p2p] supply hook failed for %s: %s", listing_id, exc)


async def _stale_supply_hook(listing_id: str) -> None:
    """Remove the buyable row when a listing is sold or withdrawn.

    A Target Hit that opens a sold listing is worse than no Target Hit — it
    spends the user's daily alert and their trust. Deleting rather than ageing
    out because `market_hits` retention is 1 day and the snipe reads a
    30-minute window; a sold listing must disappear immediately.
    """
    pool = get_db_pool()
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM public.market_hits "
                "WHERE provider = 'sparrow' AND listing_id = $1",
                str(listing_id),
            )
    except Exception as exc:
        logger.warning("[p2p] stale hook failed for %s: %s", listing_id, exc)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/listings", response_model=ListingOut, status_code=201,
             summary="List an item you own for sale")
async def create_listing(
    payload: ListingCreate,
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(_listing_write_limit),
) -> ListingOut:
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code="DB_UNAVAILABLE")

    async with pool.acquire() as conn:
        # Ownership is enforced HERE, server-side. The client sending an
        # item_id it does not own must not be able to list it.
        item = await conn.fetchrow(
            """
            SELECT id, name, category, canonical_key, image_url
            FROM public.items
            WHERE id = $1::uuid AND user_id = $2::uuid
            """,
            payload.item_id, user_id,
        )
        if item is None:
            raise error_response(
                404, "Item not found in your collection", code="ITEM_NOT_FOUND",
            )

        # One active listing per item — otherwise a member can publish the same
        # item repeatedly and flood Target Hit with duplicates of one object.
        dup = await conn.fetchval(
            """
            SELECT 1 FROM public.marketplace_listings
            WHERE item_id = $1::uuid AND user_id = $2::uuid
              AND status = $3 AND delisted_at IS NULL
            LIMIT 1
            """,
            payload.item_id, user_id, _STATUS_ACTIVE,
        )
        if dup:
            raise error_response(
                409, "This item is already listed", code="ALREADY_LISTED",
            )

        listing_id = str(uuid4())
        await conn.execute(
            """
            INSERT INTO public.marketplace_listings
                (id, user_id, item_id, marketplace_id, listing_title,
                 listing_description, price, currency, condition_label,
                 condition_notes, shipping_cost, ships_from, canonical_key,
                 category, format, quantity, status, listed_at,
                 created_at, updated_at)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5,
                    $6, $7, $8, $9,
                    $10, $11, $12, $13,
                    $14, $16, 1, $15, now(),
                    now(), now())
            """,
            listing_id, user_id, payload.item_id, SPARROW_MARKETPLACE_KEY,
            item["name"] or "Untitled",
            payload.description, payload.price, payload.currency,
            payload.condition_label, payload.condition_notes,
            payload.shipping_cost, payload.ships_from,
            item["canonical_key"], item["category"], _STATUS_ACTIVE,
            _FORMAT_FIXED,
        )

    # Off the critical path — the seller's request returns immediately.
    spawn_bg(_publish_supply_hook(listing_id), "p2p_supply_hook")

    return ListingOut(
        id=listing_id, user_id=user_id, item_id=payload.item_id,
        title=item["name"] or "Untitled", description=payload.description,
        price=payload.price, currency=payload.currency,
        condition_label=payload.condition_label,
        category=item["category"], canonical_key=item["canonical_key"],
        ships_from=payload.ships_from, shipping_cost=payload.shipping_cost,
        image_url=item["image_url"],
        status=_STATUS_ACTIVE, created_at=datetime.now(timezone.utc),
        is_mine=True,
    )


@router.get("/listings", response_model=ListingListResponse,
            summary="Browse member listings")
async def browse_listings(
    category: Optional[str] = Query(None, max_length=64),
    canonical_key: Optional[str] = Query(None, max_length=200),
    mine: bool = Query(False, description="Only my own listings (includes sold/delisted)"),
    user_id: str = Depends(get_current_user_id),
    pagination: tuple[int, int] = Depends(pagination_params),
) -> ListingListResponse:
    limit, offset = pagination
    pool = get_db_pool()
    if pool is None:
        return ListingListResponse(listings=[])

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT l.id, l.user_id, l.item_id, l.listing_title,
                   l.listing_description, l.price, l.currency,
                   l.condition_label, l.category, l.canonical_key,
                   l.ships_from, l.shipping_cost, l.status, l.created_at,
                   COALESCE(i.image_url, ci.image_url) AS image_url,
                   (i.image_url IS NULL AND ci.image_url IS NOT NULL) AS image_is_catalog
            FROM public.marketplace_listings l
            -- LEFT JOIN: a listing must still render if its source item was
            -- deleted. An inner join would silently drop listings, which is
            -- the empty-result failure mode this codebase keeps hitting.
            LEFT JOIN public.items i ON i.id = l.item_id
            -- Catalog fallback image. canonical_key is BARE and
            -- category_items.item_key is BARE too, so this joins directly —
            -- unlike market_hits.item_ref, which is namespaced
            -- (learning_canonical_key_vs_item_ref_namespace).
            LEFT JOIN public.category_items ci
                   ON ci.item_key = l.canonical_key
                  AND ci.category = l.category
            WHERE l.marketplace_id = $1
              -- Public browse shows only live listings. `mine` shows the
              -- seller EVERYTHING they have listed, including sold and
              -- delisted rows: a seller who marks something sold should still
              -- find it, otherwise their history silently disappears and they
              -- cannot tell "sold" from "never saved".
              AND ($5::boolean IS TRUE
                   OR (l.delisted_at IS NULL AND l.status = $2))
              AND ($3::text IS NULL OR l.category = $3)
              AND ($4::text IS NULL OR l.canonical_key = $4)
              AND ($5::boolean IS FALSE OR l.user_id = $6::uuid)
            ORDER BY l.created_at DESC
            LIMIT $7 OFFSET $8
            """,
            SPARROW_MARKETPLACE_KEY, _STATUS_ACTIVE,
            category, canonical_key, mine, user_id, limit, offset,
        )

    return ListingListResponse(listings=[
        ListingOut(
            id=str(r["id"]), user_id=str(r["user_id"]),
            item_id=str(r["item_id"]) if r["item_id"] else None,
            title=r["listing_title"], description=r["listing_description"],
            price=float(r["price"]), currency=r["currency"],
            condition_label=r["condition_label"], category=r["category"],
            canonical_key=r["canonical_key"], ships_from=r["ships_from"],
            shipping_cost=float(r["shipping_cost"]) if r["shipping_cost"] is not None else None,
            image_url=r["image_url"],
            image_is_catalog=bool(r["image_is_catalog"]),
            status=r["status"], created_at=r["created_at"],
            is_mine=str(r["user_id"]) == user_id,
        )
        for r in rows
    ])


class DemandPreview(BaseModel):
    """Demand for an item BEFORE it is listed."""
    watchers: int = 0
    watchers_above_price: int = 0
    # Highest target anyone is watching at. Lets the seller price into real
    # demand instead of guessing — and it is the single most persuasive number
    # we can show them.
    top_target: Optional[float] = None
    is_catalog_matched: bool = False


@router.get("/demand/{item_id}", response_model=DemandPreview,
            summary="Who is waiting for this item (pre-listing)")
async def demand_preview(
    item_id: str,
    price: Optional[float] = Query(None, gt=0, description="Price you're considering"),
    user_id: str = Depends(get_current_user_id),
) -> DemandPreview:
    """Demand for an item the caller owns, before they list it.

    This is the seller-acquisition line: "4 members are watching this, 2 with
    targets above EUR 40." No generic marketplace can say it, because none of
    them know what their users want before they search.

    Requires ownership — demand is competitive information, and exposing "how
    many people want X" for arbitrary items invites scraping.

    Returns zeros when the item has no canonical_key: an unmatched item cannot
    be joined to anyone's watchlist. `is_catalog_matched` tells the UI to show
    the match prompt instead of a discouraging (and meaningless) "0 watching".
    """
    pool = get_db_pool()
    if pool is None:
        return DemandPreview()

    async with pool.acquire() as conn:
        item = await conn.fetchrow(
            """
            SELECT canonical_key, category FROM public.items
            WHERE id = $1::uuid AND user_id = $2::uuid
            """,
            item_id, user_id,
        )
        if item is None:
            raise error_response(404, "Item not found in your collection",
                                 code="ITEM_NOT_FOUND")
        if not item["canonical_key"] or not item["category"]:
            return DemandPreview(is_catalog_matched=False)

        r = await conn.fetchrow(
            """
            SELECT count(*) AS watchers,
                   count(*) FILTER (
                       WHERE $3::numeric IS NOT NULL
                         AND w.target_price IS NOT NULL
                         AND w.target_price >= $3::numeric
                   ) AS above,
                   max(w.target_price) AS top_target
            FROM public.watchlist_items w
            WHERE w.item_id = $1
              AND w.category = $2
              AND w.user_id <> $4::uuid
            """,
            item["canonical_key"], item["category"], price, user_id,
        )

    return DemandPreview(
        watchers=int(r["watchers"] or 0),
        watchers_above_price=int(r["above"] or 0),
        top_target=float(r["top_target"]) if r["top_target"] is not None else None,
        is_catalog_matched=True,
    )


@router.get("/listings/{listing_id}", response_model=ListingOut,
            summary="Get one listing (Target Hit deep-link target)")
async def get_listing(
    listing_id: str,
    user_id: str = Depends(get_current_user_id),
) -> ListingOut:
    """Resolve a single listing.

    This is the target of the `https://sparrowcollect.com/l/<id>` URL written
    into `market_hits.url` by the supply hook. Without it, a Target Hit on a
    member listing opened a URL nothing served — the same dead-button failure
    the snipe query was fixed to avoid, reintroduced from our own side.

    Returns delisted/sold listings too, with their real status, so the client
    can say "this has been sold" instead of showing a bare 404. That
    distinction matters: a buyer who taps an alert deserves to know the item
    went rather than that something broke.
    """
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code="DB_UNAVAILABLE")

    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            """
            SELECT l.id, l.user_id, l.item_id, l.listing_title,
                   l.listing_description, l.price, l.currency,
                   l.condition_label, l.category, l.canonical_key,
                   l.ships_from, l.shipping_cost, l.status, l.created_at,
                   l.delisted_at,
                   COALESCE(i.image_url, ci.image_url) AS image_url,
                   (i.image_url IS NULL AND ci.image_url IS NOT NULL) AS image_is_catalog,
                   p.display_name, p.username, p.created_at AS seller_since,
                   -- Scalar subqueries, not GROUP BY: joining items and
                   -- listings in one query would multiply rows and inflate
                   -- both counts. Cheap here because it is a single listing.
                   (SELECT count(*) FROM public.items si WHERE si.user_id = l.user_id) AS seller_items,
                   (SELECT count(*) FROM public.marketplace_listings sl
                     WHERE sl.user_id = l.user_id AND sl.status = 'active'
                       AND sl.delisted_at IS NULL) AS seller_listings,
                   -- Demand. watchlist_items.item_id holds a BARE canonical
                   -- key, same vocabulary as marketplace_listings.canonical_key
                   -- — this joins directly, unlike market_hits.item_ref which
                   -- is namespaced (learning_canonical_key_vs_item_ref_namespace).
                   -- Excludes the seller's own watchlist row: telling someone
                   -- "1 person is watching" when it is them is a lie.
                   (SELECT count(*) FROM public.watchlist_items w
                     WHERE w.item_id = l.canonical_key
                       AND w.category = l.category
                       AND w.user_id <> l.user_id) AS watchers,
                   (SELECT count(*) FROM public.watchlist_items w
                     WHERE w.item_id = l.canonical_key
                       AND w.category = l.category
                       AND w.user_id <> l.user_id
                       AND w.target_price IS NOT NULL
                       AND w.target_price >= l.price) AS watchers_above
            FROM public.marketplace_listings l
            LEFT JOIN public.items i ON i.id = l.item_id
            LEFT JOIN public.category_items ci
                   ON ci.item_key = l.canonical_key
                  AND ci.category = l.category
            LEFT JOIN public.profiles p ON p.id = l.user_id
            WHERE l.id = $1::uuid AND l.marketplace_id = $2
            """,
            listing_id, SPARROW_MARKETPLACE_KEY,
        )
    if r is None:
        raise error_response(404, "Listing not found", code="LISTING_NOT_FOUND")

    return ListingOut(
        id=str(r["id"]), user_id=str(r["user_id"]),
        item_id=str(r["item_id"]) if r["item_id"] else None,
        title=r["listing_title"], description=r["listing_description"],
        price=float(r["price"]), currency=r["currency"],
        condition_label=r["condition_label"], category=r["category"],
        canonical_key=r["canonical_key"], ships_from=r["ships_from"],
        shipping_cost=float(r["shipping_cost"]) if r["shipping_cost"] is not None else None,
        image_url=r["image_url"],
        image_is_catalog=bool(r["image_is_catalog"]),
        seller_name=r["display_name"] or r["username"],
        seller_since=r["seller_since"],
        seller_collection_size=int(r["seller_items"] or 0),
        seller_active_listings=int(r["seller_listings"] or 0),
        watchers=int(r["watchers"] or 0),
        watchers_above_price=int(r["watchers_above"] or 0),
        # A delisted row keeps its stored status ('sold'/'delisted'), so the
        # client can render "sold" rather than implying it is still buyable.
        status=r["status"], created_at=r["created_at"],
        is_mine=str(r["user_id"]) == user_id,
    )


@router.post("/listings/{listing_id}/delist", status_code=200,
             summary="Mark a listing sold or delisted")
async def delist(
    listing_id: str,
    # Pattern must stay in sync with _STATUS_SOLD / _STATUS_DELISTED above,
    # which in turn mirror marketplace_listings_status_check.
    status: str = Query(_STATUS_SOLD, pattern=r"^(sold|delisted)$"),
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(_listing_write_limit),
) -> dict:
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code="DB_UNAVAILABLE")

    async with pool.acquire() as conn:
        updated = await conn.fetchval(
            """
            UPDATE public.marketplace_listings
               SET status = $3, delisted_at = now(), updated_at = now()
             WHERE id = $1::uuid AND user_id = $2::uuid AND delisted_at IS NULL
            RETURNING id
            """,
            listing_id, user_id, status,
        )
    if updated is None:
        raise error_response(404, "Listing not found", code="LISTING_NOT_FOUND")

    # AWAITED, not fire-and-forget — unlike the publish hook.
    # Asymmetry is deliberate: a missing supply row is a non-event (the listing
    # simply is not surfaced), but a LINGERING one sends a user to something
    # already sold, spends their daily Target Hit and their trust. Verified by
    # the end-to-end test, which caught the row surviving delist when this was
    # spawn_bg. It is a single indexed DELETE, so the latency cost is trivial.
    await _stale_supply_hook(listing_id)
    return {"ok": True, "status": status}


@router.post("/listings/{listing_id}/report", status_code=201,
             summary="Report a listing (DSA notice-and-action)")
async def report_listing(
    listing_id: str,
    payload: ReportCreate,
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(_report_limit),
) -> dict:
    """DSA notice-and-action. The micro-enterprise exemption does not cover
    this obligation, so it ships in Stage 1, not later."""
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code="DB_UNAVAILABLE")

    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM public.marketplace_listings WHERE id = $1::uuid",
            listing_id,
        )
        if not exists:
            raise error_response(404, "Listing not found", code="LISTING_NOT_FOUND")

        # RETURNING id tells us whether the row was actually inserted. The
        # counter must only move on a NEW report — incrementing
        # unconditionally let one user inflate reports_count without limit by
        # re-reporting, which would poison moderation triage.
        inserted = await conn.fetchval(
            """
            INSERT INTO public.listing_reports
                (listing_id, reporter_id, reason, detail)
            VALUES ($1::uuid, $2::uuid, $3, $4)
            ON CONFLICT (listing_id, reporter_id) WHERE status = 'open'
            DO NOTHING
            RETURNING id
            """,
            listing_id, user_id, payload.reason, payload.detail,
        )
        if inserted is not None:
            await conn.execute(
                "UPDATE public.marketplace_listings "
                "SET reports_count = reports_count + 1 WHERE id = $1::uuid",
                listing_id,
            )

    return {"ok": True}
