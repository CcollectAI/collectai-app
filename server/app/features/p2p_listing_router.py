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

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user_id, require_ops_key
from app.errors import error_response
from app.features.pagination import pagination_params
from app.lib.bg_tasks import spawn_bg
from app.lib.blocks import blocked_user_ids, is_blocked
from app.lib.content_filter import find_blocked_term
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

def _row_get(r, key: str):
    """A column not every listing query selects.

    asyncpg's Record raises KeyError on a missing key, so a mapper shared by two
    queries must not read a column directly unless BOTH select it. Both do today;
    this keeps that from becoming a 500 the day a third query is added.
    """
    if hasattr(r, "get"):
        return r.get(key)
    try:
        return r[key]
    except (KeyError, IndexError):
        return None


def _inherit_from_item(
    sent: Optional[str], *from_item: Optional[str],
) -> Optional[str]:
    """What the request said, or else what the item already recorded.

    Module level rather than a closure so it can be tested as behaviour instead
    of grepped for in the source (learning_tests_that_pin_a_stub).

    One direction only. The request WINS wherever it says something, and the
    item only fills a silence — a seller who deliberately cleared a field on the
    listing must not have the item's old value pushed back in behind them.

    `""` is how a cleared field arrives from the client, so blank-after-strip
    counts as silence on the way IN; if the item is blank too, the caller's own
    value (None or "") is handed back unchanged rather than normalised, because
    normalising here would quietly change what a non-inheriting caller stores.
    """
    if sent is not None and sent.strip():
        return sent
    for candidate in from_item:
        if candidate is not None and str(candidate).strip():
            return candidate
    return sent


class ListingCreate(BaseModel):
    """Create a listing from an item the caller owns.

    Two ways in, ONE code path after the first few lines:

    * **`item_id`** — list something already in your collection. It inherits
      `canonical_key` and `category`, which is what lets the listing join Target
      Hit's EXACT-identity arm instead of the fuzzy title arm.

    * **`title`** (no `item_id`) — the marketplace-only seller. Until
      2026-08-07 this was impossible: `item_id` was required and the only entry
      point is the item-detail screen, so someone who wanted to sell a single
      thing had to first add it to a collection they did not want. That is a
      funnel blocker on exactly the people most likely to bring supply.

      The item is created for them, tagged `source='marketplace'` and
      `for_sale=true`. NOT archived — archiving is a user action elsewhere and
      faking it would read as "the app archived my thing". This is deliberately
      an `items` row rather than a nullable `marketplace_listings.item_id`:
      photos (`item_images`), `canonical_ref` resolution, the supply hook and
      the sold-comp hook are all keyed on an item, so giving the seller a real
      one means every downstream feature works unchanged instead of needing a
      second, item-less variant of each.

    Supplying `canonical_key` + `category` on the free-text path is what makes
    the listing reach Target Hit and produce a usable sold comp — see
    `reaches_target_hit` on the response.
    """
    item_id: Optional[str] = Field(
        None, description="items.id the caller owns. Omit to list without a collection item.",
    )
    title: Optional[str] = Field(
        None, max_length=200,
        description="Required when item_id is omitted — what is being sold.",
    )
    category: Optional[str] = Field(None, max_length=64)
    canonical_key: Optional[str] = Field(
        None, max_length=200,
        description="Bare catalogue key. Without it the listing cannot fire a Target Hit.",
    )
    price: float = Field(..., gt=0, le=1_000_000)
    currency: str = Field(default="EUR", max_length=3, pattern=r"^[A-Z]{3}$")
    condition_label: Optional[str] = Field(None, max_length=64)
    condition_notes: Optional[str] = Field(None, max_length=2000)
    description: Optional[str] = Field(None, max_length=4000)
    ships_from: Optional[str] = Field(None, max_length=120)
    shipping_cost: Optional[float] = Field(None, ge=0, le=100_000)
    # Opt-in, default OFF. Absence of a choice is not consent, which is why
    # this defaults false here AND in the column default rather than relying on
    # the client always sending it. ToS §3 carries the grant.
    photo_catalogue_consent: bool = Field(
        False,
        description="Allow this listing's photo to be reused as catalogue art "
                    "for the same product. Opt-in and revocable.",
    )


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
    # Tenure and collection size: meaningful in a collector community, because a
    # 400-item collection maintained over a year is hard to fake cheaply. These
    # are the ONLY signals a brand-new seller has, and they are what the UI falls
    # back to below the reputation threshold.
    seller_name: Optional[str] = None
    seller_since: Optional[datetime] = None
    seller_collection_size: int = 0
    seller_active_listings: int = 0
    # ── Trade reputation ──────────────────────────────────────────────────
    # The original note here said "deliberately NOT ratings — with no payment
    # record we cannot verify a trade happened". That was true in Stage 1 and is
    # no longer the whole story: a grade can only exist against an offer both
    # parties confirmed (p2p_offers.status = 'completed'), and member_grades is
    # unique per (offer_id, rater_id). So a grade is anchored to a real,
    # two-sided event rather than to a drive-by opinion.
    #
    # Still deliberately NOT stars. Completion is two self-confirmations, not a
    # settled payment, so a 4.7/5 would imply a precision the data cannot carry.
    # We publish a trade COUNT (a fact, meaningful at n=1) and a positive
    # percentage only once there are enough grades to mean anything —
    # `seller_positive_pct` is None below p2p_offers_router._MIN_GRADES_TO_SHOW,
    # matching /p2p/members/{id}/reputation exactly so the two cannot drift.
    # True only when a stranger would see this seller's profile. Drives whether
    # the seller row on the listing screen is TAPPABLE — linking to a profile the
    # member did not agree to expose would publish it by navigation.
    seller_profile_public: bool = False
    seller_completed_trades: int = 0
    seller_total_grades: int = 0
    seller_positive_grades: int = 0
    seller_positive_pct: Optional[int] = None
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
    # ── Does this listing actually reach Target Hit? ──────────────────────
    # `_publish_supply_hook` writes the buyable market_hits row ONLY when the
    # listing has a canonical identity; without one it could match only the
    # fuzzy title arm, which is where false positives live, so it is skipped.
    # That skip is right, and it was also completely invisible — the seller got
    # a listing that can never fire an alert and was never told, and the §6
    # go/no-go metric counted the absence as "no demand".
    #
    # Derived, not stored: `canonical_key` IS the record of the skip, so this
    # needs no column and cannot drift from the hook's own precondition.
    # Keep this expression identical to the guard in _publish_supply_hook —
    # pinned by test_reaches_target_hit_matches_the_hook_precondition.
    reaches_target_hit: bool = False
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

def _reaches_target_hit(canonical_key: Optional[str], category: Optional[str]) -> bool:
    """Can a listing with this identity produce a buyable `market_hits` row?

    ONE definition, used by `_publish_supply_hook`'s guard and by every
    `ListingOut`. Two copies would let the API promise a seller their listing
    reaches Target Hit while the hook silently skipped it — which is the exact
    shape of the bug this function was extracted to close.
    """
    return bool(canonical_key) and bool(category)


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
            if row is None or not _reaches_target_hit(row["canonical_key"], row["category"]):
                # No canonical identity => it could only ever match the fuzzy
                # title arm, which is where the false-positive risk lives.
                # Skip rather than write a weakly-identified buyable row.
                #
                # WARNING, not INFO. The line was always written (to
                # /opt/collectors/bake.log — the unit sets StandardOutput to a
                # file, NOT journald, so `journalctl` never shows it), but it
                # sat at INFO inside a 90MB log of INFO. This is not routine:
                # measured 2026-08-07, only 4 of 16 `items` carry a
                # canonical_key, so the hook skips the MAJORITY of listings, and
                # each skip means a listing that can never fire a Target Hit.
                #
                # It matters beyond one missing row: §6 of the spec decides
                # whether Stage 2/3 ever happens by counting buyable `sparrow`
                # rows, and that count reads near-zero whether nobody listed or
                # the hook skipped everyone. A go/no-go metric that cannot
                # distinguish "no supply" from "no canonical key" is worse than
                # no metric. See docs/P2P_MARKETPLACE_SPEC.md §6.
                logger.warning(
                    "[p2p] supply hook SKIPPED for %s — listing has no canonical "
                    "identity (canonical_key=%r category=%r), so it cannot reach "
                    "Target Hit. Not a failure; a coverage gap.",
                    listing_id,
                    row["canonical_key"] if row else None,
                    row["category"] if row else None,
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


# Sold comps written by this hook are tagged with their own source so they stay
# separable from scraped supply forever. That matters twice over: it is the
# lever for excluding them from valuation if P2P prices ever prove unreliable,
# and it is how you measure how much the marketplace is actually contributing.
SPARROW_SOLD_SOURCE = "sparrow_p2p"


async def _sold_comp_hook(listing_id: str, amount: float, currency: str) -> None:
    """Record a COMPLETED trade as a sold comp — the closed loop.

    This is the most valuable datum the marketplace produces and it used to be
    thrown away. On two-sided completion the code deleted the buyable row
    (`_stale_supply_hook`) and wrote nothing about the price the item actually
    changed hands for.

    Why that was expensive: `valuation_worker` selects
    `WHERE is_listing IS NOT TRUE` — it consumes SOLD data and deliberately
    ignores asking prices. Every row P2P wrote was `is_listing = TRUE`. Meanwhile
    ~62,000 catalogue items have no price at all for exactly one reason:
    `ebay_caller.py:387 sold_comps()` returns `[]`, so there is no sold-comp
    source for them. A completed Sparrow trade is a real sale at a known,
    two-sided-confirmed price — precisely the input the valuation pipeline is
    starved of, generated by our own users.

    Deliberate choices:

    * **The AGREED amount, not the asking price.** `p2p_offers.amount` after a
      counter is what was actually paid; `marketplace_listings.price` is what
      was hoped for. Storing the ask as a sale would bias every prediction
      upward.
    * **`is_listing = FALSE`**, which is what makes valuation_worker read it at
      all. Getting this backwards writes a row that looks like supply and feeds
      nothing.
    * **Its own `source`.** See SPARROW_SOLD_SOURCE above.
    * **Idempotent.** A re-confirm must not write a second sale. `market_hits`
      has no usable unique key (id comes from a sequence), so this uses
      WHERE NOT EXISTS, the same guard as the publish hook.

    ⚠️ MANIPULATION SURFACE, stated plainly: two colluding accounts can
    complete a trade at any price they like and inject a comp. For an item with
    many comps the median absorbs it; for one of the 62k items with ZERO other
    comps, a single fake sale becomes the entire price. That is the case where
    manipulation pays best. This writes the row because the data is worth
    having and is fully auditable (`listing_id` traces back to both parties),
    but until there is volume, treat `source = 'sparrow_p2p'` as the filter to
    pull if predictions start looking wrong. See docs/P2P_MARKETPLACE_SPEC.md.
    """
    pool = get_db_pool()
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT listing_title, canonical_key, category, condition_label
                FROM public.marketplace_listings
                WHERE id = $1::uuid
                """,
                listing_id,
            )
            if row is None or not _reaches_target_hit(row["canonical_key"], row["category"]):
                # Without a canonical identity there is no `item_ref`, and
                # valuation_worker requires one — the row would be inert.
                logger.warning(
                    "[p2p] sold comp SKIPPED for %s — no canonical identity, so a "
                    "real completed sale cannot reach the valuation pipeline.",
                    listing_id,
                )
                return

            from app.lib.fx_service import convert_to_eur
            price_eur = await convert_to_eur(float(amount), currency or "EUR")
            item_ref = f"{row['category']}:{row['canonical_key']}"

            await conn.execute(
                """
                INSERT INTO public.market_hits
                    (provider, source, marketplace, listing_id, title,
                     price, currency, price_eur, url, normalized_key, item_ref,
                     category, condition, observed_at, seen_at, is_listing)
                SELECT 'sparrow', $9, 'sparrow', $1, $2,
                       $3, $4, $5, $6, $7, $7,
                       $8, $10, now(), now(), FALSE
                WHERE NOT EXISTS (
                    SELECT 1 FROM public.market_hits
                    WHERE source = $9 AND listing_id = $1
                )
                """,
                str(listing_id),
                row["listing_title"],
                float(amount),
                currency or "EUR",
                price_eur,
                f"https://sparrowcollect.com/l/{listing_id}",
                item_ref,
                row["category"],
                SPARROW_SOLD_SOURCE,
                row["condition_label"],
            )
            logger.info(
                "[p2p] sold comp written for %s (%s @ %.2f %s) — feeds valuation",
                listing_id, item_ref, float(amount), currency or "EUR",
            )
    except Exception as exc:
        logger.warning("[p2p] sold comp hook failed for %s: %s", listing_id, exc)


async def _ground_truth_hook(listing_id: str, amount: float, currency: str) -> None:
    """Feed a completed trade's agreed price back as model CALIBRATION.

    Rescued from the Deal Desk removal (2026-08-09). Deal Desk's
    `execute_complete` called `record_price_ground_truth`; P2P's completion did
    not, so deleting Deal Desk would have quietly dropped the calibration loop
    on the floor. It never actually carried data — Deal Desk shipped disabled
    and completed zero trades — but the WIRING was the good part, and P2P is
    where trades really complete.

    This is NOT a duplicate of `_sold_comp_hook`, which is the neighbouring
    function and easy to confuse with it:

    * `_sold_comp_hook` writes `market_hits` — a SOLD OBSERVATION that
      `valuation_worker` consumes to compute what an item is worth.
    * this writes `price_ground_truths` — a PREDICTION ERROR, comparing what we
      forecast (`price_predictions.q50`) against what the item actually fetched.
      That is what tells us the model is drifting.

    Same input, two different consumers. Dropping either loses something the
    other cannot supply.

    Requires `marketplace_listings.item_id`: `record_price_ground_truth` keys on
    `items.id` and resolves the prediction through `items.canonical_ref`. A
    marketplace-only listing (spec §5c — sell something you do not own a
    collection row for) has no `item_id`, so there is no prediction to score
    against and this correctly does nothing. That is a real limit, not a bug:
    calibration needs a predicted item.

    Fire-and-forget in effect — every failure path is swallowed and logged.
    A lost calibration point is a non-event; a completion that 500s because
    calibration failed is not.
    """
    pool = get_db_pool()
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            item_id = await conn.fetchval(
                "SELECT item_id FROM public.marketplace_listings WHERE id = $1::uuid",
                listing_id,
            )
        if item_id is None:
            logger.info(
                "[p2p] ground truth skipped for %s — marketplace-only listing, "
                "no items row to score a prediction against.",
                listing_id,
            )
            return

        from app.lib.fx_service import convert_to_eur
        from app.features.data_moat import record_price_ground_truth

        # EUR because `price_predictions.q50` is EUR; comparing a USD sale
        # against a EUR forecast would book the FX rate as model error.
        price_eur = await convert_to_eur(float(amount), currency or "EUR")
        await record_price_ground_truth(
            str(item_id), price_eur, "EUR", source="sparrow_p2p",
        )
    except Exception as exc:
        logger.warning("[p2p] ground truth hook failed for %s: %s", listing_id, exc)


async def _catalogue_image_hook(listing_id: str) -> None:
    """Fill a catalogue image gap from a member's listing photo, with consent.

    54,115 of 221,391 `category_items` have no image. A member selling a real
    copy has photographed it. That photo can close the gap — but only under
    conditions that make it lawful and honest:

    * **Consent, per listing.** ToS §3 grants this explicitly, opt-in and
      revocable. `photo_catalogue_consent` defaults FALSE in both the model and
      the column: absence of a choice is not consent.
    * **Gap-filling ONLY — never overwrite.** `WHERE image_url IS NULL` is the
      whole safety story. It bounds the blast radius to items that show a
      placeholder today, and means a contributed photo can never displace a
      licensed catalogue asset or a better one.
    * **The seller's OWN photo**, not the catalogue fallback. Copying the
      fallback back into the catalogue would be a no-op that looks like
      progress; `i.image_url IS NOT NULL` is what makes it a real contribution.
    * **Provenance recorded**, so "stop using my photo" is answerable —
      `image_source`, `image_contributed_by`, `image_contributed_at`.

    Fire-and-forget: a missed enrichment is a non-event, and it must never
    affect whether the seller's listing publishes.
    """
    pool = get_db_pool()
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            # The seller's photo lives in EITHER place and both are legitimate:
            # `items.image_url` is the primary thumbnail (written by the client
            # via PostgREST), `item_images` is the gallery that
            # POST /items/{id}/images writes. Reading only the first would have
            # made this hook near-dead — nothing server-side writes
            # items.image_url, so a photo uploaded through the documented
            # endpoint would never have been seen.
            row = await conn.fetchrow(
                """
                SELECT l.user_id, l.canonical_key, l.category,
                       COALESCE(
                         i.image_url,
                         (SELECT im.image_url FROM public.item_images im
                           WHERE im.item_id = i.id
                           ORDER BY im.position NULLS LAST, im.created_at
                           LIMIT 1)
                       ) AS image_url
                FROM public.marketplace_listings l
                JOIN public.items i ON i.id = l.item_id
                WHERE l.id = $1::uuid
                  AND l.photo_catalogue_consent IS TRUE
                  AND l.canonical_key IS NOT NULL
                  AND l.category IS NOT NULL
                """,
                listing_id,
            )
            # Checked in Python rather than SQL so "no photo yet" is a normal
            # early return: the realistic order is publish -> get item_id ->
            # upload, so at publish time there is usually nothing to contribute.
            if row is None or not row["image_url"]:
                return

            filled = await conn.fetchval(
                """
                UPDATE public.category_items
                   SET image_url = $3,
                       image_source = 'member_listing',
                       image_contributed_by = $4::uuid,
                       image_contributed_at = now()
                 WHERE item_key = $1 AND category = $2
                   AND image_url IS NULL
                RETURNING 1
                """,
                row["canonical_key"], row["category"],
                row["image_url"], str(row["user_id"]),
            )
            if filled:
                logger.info(
                    "[p2p] catalogue image contributed for %s:%s from listing %s",
                    row["category"], row["canonical_key"], listing_id,
                )
    except Exception as exc:
        logger.warning("[p2p] catalogue image hook failed for %s: %s", listing_id, exc)


async def _page_ops_new_report(listing_id: str, reason: str) -> None:
    """Tell the operator a listing was reported, so the 24-hour clock is real.

    Sparrow is one person. There is no rota watching a moderation queue, so a
    promise to act "within 24 hours" only holds if the report finds them rather
    than waiting to be found. This is that push.

    Includes the listing title and the open-report count because the decision
    the operator makes next needs both: a first report on an obscure listing and
    a fifth report on the same one are different situations.

    Never raises — the report is already committed, and a Telegram outage must
    not surface to the member as a failed report.
    """
    pool = get_db_pool()
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT l.listing_title, l.user_id,
                       (SELECT count(*) FROM public.listing_reports r
                         WHERE r.listing_id = l.id AND r.status = 'open') AS open_reports
                FROM public.marketplace_listings l
                WHERE l.id = $1::uuid
                """,
                listing_id,
            )
        if row is None:
            return

        from app.lib.telegram_ops import send_ops_alert
        await send_ops_alert(
            (
                f"<b>{row['listing_title']}</b>\n"
                f"Reason: {reason}\n"
                f"Open reports: {row['open_reports']}\n"
                f"Seller: <code>{row['user_id']}</code>\n"
                f"Listing: <code>{listing_id}</code>\n\n"
                f"Terms promise action within 24h. Decide with:\n"
                f"<code>GET /ops/listing-reports</code> then "
                f"<code>POST /ops/listing-reports/{listing_id}/action</code>"
            ),
            title="\U0001f6a9 Listing reported",
        )
    except Exception as exc:
        logger.warning("[p2p] report paging failed for %s: %s", listing_id, exc)


async def contribute_from_item_photo(item_id: str) -> None:
    """Run the catalogue hook for any consenting live listing on this item.

    Called when a PHOTO lands, which is the moment that actually matters. The
    publish-time call alone was an ordering bug: a seller creates the listing,
    gets `item_id` back, and only THEN uploads — so at publish there is nothing
    to contribute, and without this the consent they gave would never do
    anything. Exactly the "capture without a consumer" shape.
    """
    pool = get_db_pool()
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id FROM public.marketplace_listings
                WHERE item_id = $1::uuid
                  AND photo_catalogue_consent IS TRUE
                  AND status = $2 AND delisted_at IS NULL
                """,
                item_id, _STATUS_ACTIVE,
            )
        for r in rows:
            await _catalogue_image_hook(str(r["id"]))
    except Exception as exc:
        logger.warning("[p2p] contribute-from-photo failed for item %s: %s", item_id, exc)


async def withdraw_contributed_images(conn, user_id: str) -> int:
    """Stop using a member's photos as catalogue art. Returns rows cleared.

    The counterpart to the ToS §3 grant being *revocable*. Without this the
    grant is a promise the code cannot keep. Clears the image rather than
    substituting one, so the catalogue returns to the placeholder it showed
    before the contribution — the honest previous state.
    """
    cleared = await conn.fetch(
        """
        UPDATE public.category_items
           SET image_url = NULL, image_source = NULL,
               image_contributed_by = NULL, image_contributed_at = NULL
         WHERE image_contributed_by = $1::uuid
        RETURNING 1
        """,
        user_id,
    )
    return len(cleared)


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

    # Apple Guideline 1.2: filter objectionable material BEFORE it is posted.
    # Checked here, at the one write path, rather than at each call site — and
    # before the item is created, so a rejected listing leaves nothing behind.
    # The term is returned to the seller: a generic refusal on a listing they
    # believe is fine reads as the app being broken.
    bad = find_blocked_term(payload.title, payload.description, payload.condition_notes)
    if bad:
        raise error_response(
            400,
            f"Your listing contains language we don't allow (\"{bad}\"). "
            f"Edit it and try again.",
            code="OBJECTIONABLE_CONTENT",
        )

    if not payload.item_id and not (payload.title or "").strip():
        raise error_response(
            400, "Give either an item from your collection or a title",
            code="ITEM_OR_TITLE_REQUIRED",
        )

    async with pool.acquire() as conn:
        if payload.item_id:
            # Ownership is enforced HERE, server-side. The client sending an
            # item_id it does not own must not be able to list it.
            # An item in the collection IS the product being sold, so the listing
            # inherits everything the seller already recorded about it — not just
            # its identity. Before 2026-08-09 this SELECT stopped at
            # (name, category, canonical_key) and `condition_label`,
            # `condition_notes` and `listing_description` were taken from the
            # request only, so listing something you own asked you to retype
            # facts you had already entered once ("double work and not useful").
            #
            # Copied field-for-field, never composed: a description assembled
            # out of brand/year/series would be us writing sales copy in the
            # seller's name. Those columns exist and are deliberately left out.
            item = await conn.fetchrow(
                """
                SELECT id, name, category, canonical_key, image_url,
                       condition, condition_grade, condition_notes, description
                FROM public.items
                WHERE id = $1::uuid AND user_id = $2::uuid
                """,
                payload.item_id, user_id,
            )
            if item is None:
                raise error_response(
                    404, "Item not found in your collection", code="ITEM_NOT_FOUND",
                )
        else:
            # Marketplace-only seller: create the item they are selling. They
            # do own it — that is the premise of listing it — so this is not a
            # fiction, it is the record catching up with reality.
            #
            # `canonical_ref` is left to trg_items_canonical_ref rather than set
            # here; that trigger owns the bare -> namespaced resolution and the
            # crosswalk fallback (learning_canonical_key_vs_item_ref_namespace).
            item = await conn.fetchrow(
                """
                INSERT INTO public.items
                    (user_id, name, category, canonical_key, source, for_sale,
                     created_at, updated_at)
                VALUES ($1::uuid, $2, $3, $4, 'marketplace', TRUE, now(), now())
                RETURNING id, name, category, canonical_key, image_url,
                          condition, condition_grade, condition_notes, description
                """,
                user_id, payload.title.strip(), payload.category,
                payload.canonical_key,
            )
            logger.info(
                "[p2p] created marketplace-only item %s for %s (canonical_key=%r)",
                item["id"], user_id, payload.canonical_key,
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
            str(item["id"]), user_id, _STATUS_ACTIVE,
        )
        if dup:
            raise error_response(
                409, "This item is already listed", code="ALREADY_LISTED",
            )

        # condition_grade is the second source because add-manual writes the
        # graded value there ("PSA 9") while `condition` holds the plain label.
        condition_label = _inherit_from_item(
            payload.condition_label, item["condition"], item["condition_grade"],
        )
        condition_notes = _inherit_from_item(payload.condition_notes, item["condition_notes"])
        listing_description = _inherit_from_item(payload.description, item["description"])

        listing_id = str(uuid4())
        await conn.execute(
            """
            INSERT INTO public.marketplace_listings
                (id, user_id, item_id, marketplace_id, listing_title,
                 listing_description, price, currency, condition_label,
                 condition_notes, shipping_cost, ships_from, canonical_key,
                 category, format, quantity, status, listed_at,
                 created_at, updated_at, photo_catalogue_consent)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5,
                    $6, $7, $8, $9,
                    $10, $11, $12, $13,
                    $14, $16, 1, $15, now(),
                    now(), now(), $17)
            """,
            listing_id, user_id, str(item["id"]), SPARROW_MARKETPLACE_KEY,
            item["name"] or "Untitled",
            listing_description, payload.price, payload.currency,
            condition_label, condition_notes,
            payload.shipping_cost, payload.ships_from,
            item["canonical_key"], item["category"], _STATUS_ACTIVE,
            _FORMAT_FIXED, payload.photo_catalogue_consent,
        )

    # Off the critical path — the seller's request returns immediately.
    spawn_bg(_publish_supply_hook(listing_id), "p2p_supply_hook")
    # Enrichment, not a feature of the listing: a missed catalogue image is a
    # non-event and must never affect whether the listing publishes.
    spawn_bg(_catalogue_image_hook(listing_id), "p2p_catalogue_image")

    return ListingOut(
        id=listing_id, user_id=user_id, item_id=str(item["id"]),
        # The INHERITED values, not the request's. Returning payload.* here
        # would hand back a listing with the blank condition and description the
        # seller did not type, while the row just written holds the item's — the
        # screen would show one thing now and another after the next fetch.
        title=item["name"] or "Untitled", description=listing_description,
        price=payload.price, currency=payload.currency,
        condition_label=condition_label,
        category=item["category"], canonical_key=item["canonical_key"],
        ships_from=payload.ships_from, shipping_cost=payload.shipping_cost,
        image_url=item["image_url"],
        reaches_target_hit=_reaches_target_hit(item["canonical_key"], item["category"]),
        status=_STATUS_ACTIVE, created_at=datetime.now(timezone.utc),
        is_mine=True,
    )


@router.get("/listings", response_model=ListingListResponse,
            summary="Browse member listings")
async def browse_listings(
    # Repeatable: ?category=pokemon&category=lego matches ANY of them. The
    # filter sheet has always let you tick several categories at once, but this
    # took a single value, so the screen dropped everything past the first —
    # silently, and the sheet then reopened showing only the survivor.
    category: Optional[List[str]] = Query(None),
    canonical_key: Optional[str] = Query(None, max_length=200),
    # Title search, server-side. It used to be a client-side filter over the
    # loaded page, which is fine for one un-paged block of 50 and wrong the
    # moment the list pages: filtering locally searches only what happens to be
    # downloaded, so "2 listings matching X" meant 2 of the first page, and
    # scrolling for more of them fetched pages the filter then discarded.
    q: Optional[str] = Query(None, max_length=100, description="Title search"),
    mine: bool = Query(False, description="Only my own listings (includes sold/delisted)"),
    sort: str = Query("newest", pattern=r"^(newest|price_asc|price_desc)$"),
    price_min: Optional[float] = Query(None, ge=0, description="Inclusive lower bound"),
    price_max: Optional[float] = Query(None, ge=0, description="Inclusive upper bound"),
    price_currency: str = Query(
        "EUR", max_length=3, pattern=r"^[A-Z]{3}$",
        description="Currency the price bounds are expressed in",
    ),
    user_id: str = Depends(get_current_user_id),
    pagination: tuple[int, int] = Depends(pagination_params),
) -> ListingListResponse:
    limit, offset = pagination

    # Widening `category` to a list dropped the per-value max_length the single
    # string had, so re-assert it here rather than let an unbounded value reach
    # the query. Also cap the count: the filter sheet offers 54 slugs, and a
    # request naming thousands is not a user.
    cats: Optional[List[str]] = None
    if category:
        if len(category) > 54 or any(len(c) > 64 for c in category):
            raise error_response(400, "Too many or overlong category filters",
                                 code="INVALID_CATEGORY_FILTER")
        # De-duplicate but keep it a plain list; = ANY() does not care about
        # order and a repeated slug would only widen the scan for no reason.
        cats = list(dict.fromkeys(category))

    # Escape LIKE metacharacters before wrapping in %…%. Without this a user
    # typing '%' matches everything and '_' matches any character — the search
    # silently stops meaning what they typed.
    term: Optional[str] = None
    if q and q.strip():
        esc = q.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        term = f"%{esc}%"

    # ── Currency normalisation ────────────────────────────────────────────────
    # Sellers list in THEIR currency (SellOnSparrowSection sends the seller's
    # settings.currency), so marketplace_listings.currency is genuinely mixed.
    # Comparing raw `price` across it is wrong in both directions: ¥8000 sorts
    # above €50, and "under 100" keeps a ¥9000 card. Both the price sort and
    # the price bounds therefore run against a EUR-normalised value, using the
    # same rate source as the rest of the server (fx_service, live with a
    # config fallback) rather than a second convention invented here.
    #
    # The conversion has to happen inside the query, because it must apply
    # BEFORE the WHERE and the LIMIT — converting the fetched rows in Python
    # would filter and order the wrong set.
    #
    # Rates travel as two PARALLEL ARRAYS (text[] + numeric[]) rather than as
    # jsonb. That is deliberate: app/db.py registers a jsonb type codec with
    # `encoder=json.dumps`, so handing it an already-serialised string
    # double-encodes it into a JSON *string*, `->> 'JPY'` returns NULL, and
    # COALESCE(..., 1) then silently leaves every foreign price unconverted.
    # That shipped and passed a direct-connection probe, because a raw asyncpg
    # connection has no such codec — only a request through the real pool
    # showed it. Arrays have no custom codec on either, so this cannot diverge
    # between the pool and a bare connection again.
    from app.lib.fx_service import convert_to_eur
    fx_codes, fx_rates = await _fx_arrays()

    # Bounds arrive in the CALLER's display currency and are converted here, so
    # there is exactly one rate source. Compare in numeric space, not float8:
    # `price` is numeric, and a float bound makes Postgres widen it to double
    # precision — which is how a bound lands ~1e-16 off and a listing priced
    # exactly at the boundary silently drops out
    # (learning_guard_must_match_constraint_type_space).
    async def _to_eur_dec(v: Optional[float]) -> Optional[Decimal]:
        if v is None:
            return None
        return Decimal(str(await convert_to_eur(v, price_currency)))

    min_dec = await _to_eur_dec(price_min)
    max_dec = await _to_eur_dec(price_max)
    pool = get_db_pool()
    if pool is None:
        return ListingListResponse(listings=[])

    async with pool.acquire() as conn:
        hidden = await blocked_user_ids(conn, user_id)
        rows = await conn.fetch(
            # archived-exempt: a LISTING browse. items is joined only for the
            # photo; what makes a listing visible is its own status.
            """
            SELECT l.id, l.user_id, l.item_id, l.listing_title,
                   l.listing_description, l.price, l.currency,
                   l.condition_label, l.category, l.canonical_key,
                   l.ships_from, l.shipping_cost, l.status, l.created_at,
                   COALESCE(i.image_url, ci.image_url) AS image_url,
                   (i.image_url IS NULL AND ci.image_url IS NOT NULL) AS image_is_catalog,
                   -- Social proof on the tile. It exists on the detail screen
                   -- already, but a signal a buyer only sees AFTER tapping
                   -- cannot influence whether they tap. Excludes the seller's
                   -- own watchlist row — "1 watching" that is you is a lie.
                   (SELECT count(*) FROM public.watchlist_items w
                     WHERE w.item_id = l.canonical_key
                       AND w.category = l.category
                       AND w.user_id <> l.user_id) AS watchers,
                   p.display_name, p.username,
                   -- EUR-normalised price, computed ONCE and then used by both
                   -- the bounds and the sort below. It used to be the same
                   -- expression repeated four times, which is precisely why a
                   -- rate map that silently resolved to NULL was invisible.
                   l.price * COALESCE(fx.rate, 1) AS price_eur,
                   -- Same predicate as get_listing below, EXISTS against the
                   -- view rather than a copy of its rule. Present in BOTH
                   -- listing queries on purpose: a column in one, read by a
                   -- mapper used from both, is a KeyError on whichever path was
                   -- missed and only on that path
                   -- (learning_duplicate_impl_silently_drops_the_fix).
                   EXISTS (SELECT 1 FROM public.user_public_profiles up
                            WHERE up.user_id = l.user_id) AS seller_profile_public
            FROM public.marketplace_listings l
            -- Rate lookup as a join over two parallel arrays. LEFT JOIN, so an
            -- unknown currency keeps the row at rate 1 (wrong by a few percent)
            -- instead of dropping it, which would make a listing vanish with
            -- nothing on screen to explain it.
            LEFT JOIN unnest($12::text[], $13::numeric[]) AS fx(code, rate)
                   ON fx.code = l.currency
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
            LEFT JOIN public.profiles p ON p.id = l.user_id
            WHERE l.marketplace_id = $1
              -- Public browse shows only live listings. `mine` shows the
              -- seller EVERYTHING they have listed, including sold and
              -- delisted rows: a seller who marks something sold should still
              -- find it, otherwise their history silently disappears and they
              -- cannot tell "sold" from "never saved".
              AND ($5::boolean IS TRUE
                   OR (l.delisted_at IS NULL AND l.status = $2))
              AND ($3::text[] IS NULL OR l.category = ANY($3::text[]))
              AND ($4::text IS NULL OR l.canonical_key = $4)
              AND ($5::boolean IS FALSE OR l.user_id = $6::uuid)
              -- Inclusive bounds, so "max 50" keeps a listing priced exactly 50,
              -- compared against the single price_eur expression in the SELECT.
              AND ($10::numeric IS NULL
                   OR l.price * COALESCE(fx.rate, 1) >= $10::numeric)
              AND ($11::numeric IS NULL
                   OR l.price * COALESCE(fx.rate, 1) <= $11::numeric)
              AND ($14::text IS NULL OR l.listing_title ILIKE $14::text)
              -- Blocking reaches the marketplace, not just chat. Symmetric:
              -- $15 carries blocks in BOTH directions, so neither party sees
              -- the other's listings. An empty array leaves every row (=ANY on
              -- '{}' is FALSE, so NOT ... is TRUE), which is what an anonymous
              -- or block-free caller must get. See app/lib/blocks.py.
              AND NOT (l.user_id = ANY($15::uuid[]))
            -- Whitelisted sort. A CASE over a validated enum rather than
            -- string interpolation: the pattern on the Query already rejects
            -- anything else, but building ORDER BY from a request value is
            -- how injection gets in even when "it's validated upstream".
            ORDER BY
              CASE WHEN $9 = 'price_asc'  THEN l.price * COALESCE(fx.rate, 1) END ASC  NULLS LAST,
              CASE WHEN $9 = 'price_desc' THEN l.price * COALESCE(fx.rate, 1) END DESC NULLS LAST,
              l.created_at DESC
            LIMIT $7 OFFSET $8
            """,
            SPARROW_MARKETPLACE_KEY, _STATUS_ACTIVE,
            cats, canonical_key, mine, user_id, limit, offset, sort,
            min_dec, max_dec, fx_codes, fx_rates, term, hidden,
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
            watchers=int(r["watchers"] or 0),
            seller_name=r["display_name"] or r["username"],
            seller_profile_public=bool(_row_get(r, "seller_profile_public")),
            status=r["status"], created_at=r["created_at"],
            reaches_target_hit=_reaches_target_hit(r["canonical_key"], r["category"]),
            is_mine=str(r["user_id"]) == user_id,
        )
        for r in rows
    ])


class CategoryFacet(BaseModel):
    category: str
    count: int


class CategoryFacetResponse(BaseModel):
    facets: List[CategoryFacet] = []


# Path is /facets/categories, deliberately NOT /listings/facets: the latter
# would sit in the same namespace as /listings/{listing_id} and depend on route
# registration order to not be swallowed as a listing id.
@router.delete("/catalogue-contributions",
               summary="Stop using my photos as catalogue art")
async def withdraw_my_catalogue_photos(
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Revoke the ToS §3 catalogue grant for every photo this member contributed.

    §3 says the grant is revocable — "you can withdraw it at any time". Until
    this endpoint existed that was a promise the code could not keep:
    `withdraw_contributed_images` was written and tested, and nothing called it.
    A licence term the user cannot actually exercise is worse than not offering
    it, because they relied on it when they ticked the box.

    Also clears the consent flag on their listings, so a later photo upload does
    not silently re-contribute what they just withdrew — revoking once should
    mean revoked, not revoked-until-the-next-upload.

    Idempotent: withdrawing twice clears nothing the second time and still
    returns 200. There is no failure mode a user should have to think about
    here.
    """
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code="DB_UNAVAILABLE")

    async with pool.acquire() as conn:
        async with conn.transaction():
            cleared = await withdraw_contributed_images(conn, user_id)
            # Same transaction: if the flag survives while the images are gone,
            # the next upload re-contributes and the withdrawal silently undoes
            # itself.
            await conn.execute(
                """
                UPDATE public.marketplace_listings
                   SET photo_catalogue_consent = FALSE, updated_at = now()
                 WHERE user_id = $1::uuid AND photo_catalogue_consent IS TRUE
                """,
                user_id,
            )
    logger.info("[p2p] catalogue photos withdrawn for %s (%d images)", user_id, cleared)
    return {"ok": True, "images_withdrawn": cleared}


@router.get("/facets/categories", response_model=CategoryFacetResponse,
            summary="Categories that actually have live listings, with counts")
async def category_facets(
    user_id: str = Depends(get_current_user_id),
) -> CategoryFacetResponse:
    """Which categories a buyer can usefully filter by.

    The filter sheet used to offer all 54 app categories regardless of stock, so
    most choices led to a guaranteed empty grid — the user pays a round trip to
    discover the category was never an option. Offering only categories with
    live listings, and showing the count, makes the control self-describing.

    Deliberately ignores the caller's other filters (price, search): these are
    counts of live listings per category, not a full faceted search. A category
    shown as "3" can still yield nothing under a €5 cap — which is why the empty
    state distinguishes "no match for your filters" from "marketplace is empty".
    """
    pool = get_db_pool()
    if pool is None:
        return CategoryFacetResponse(facets=[])

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT l.category, count(*) AS n
            FROM public.marketplace_listings l
            WHERE l.marketplace_id = $1
              AND l.status = $2
              AND l.delisted_at IS NULL
              AND l.category IS NOT NULL
            GROUP BY l.category
            ORDER BY n DESC, l.category ASC
            """,
            SPARROW_MARKETPLACE_KEY, _STATUS_ACTIVE,
        )

    return CategoryFacetResponse(facets=[
        CategoryFacet(category=r["category"], count=int(r["n"])) for r in rows
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
                   -- Trade reputation. Trades this seller COMPLETED on either
                   -- side, and the grades others left them. Counted from
                   -- p2p_offers/member_grades, the same tables
                   -- /p2p/members/{id}/reputation reads, so the listing screen
                   -- and the reputation endpoint cannot disagree.
                   -- Is this seller's profile visible to OTHER members?
                   --
                   -- EXISTS against `user_public_profiles` rather than a copy of
                   -- its rule. That view already encodes the opt-in — a profile
                   -- appears only when it has a display name AND
                   -- `user_privacy_settings.allow_discovery` is not false — and
                   -- because this connection has no `auth.uid()`, the view's
                   -- `id = auth.uid()` limb is false here, so what EXISTS
                   -- answers is exactly "would a STRANGER see this profile".
                   -- Duplicating the predicate would let the tap outlive the
                   -- consent (learning_prove_view_equivalence_with_real_auth_context).
                   EXISTS (SELECT 1 FROM public.user_public_profiles up
                            WHERE up.user_id = l.user_id) AS seller_profile_public,
                   (SELECT count(*) FROM public.p2p_offers so
                     WHERE so.status = 'completed'
                       AND (so.seller_id = l.user_id OR so.buyer_id = l.user_id)
                   ) AS seller_completed_trades,
                   (SELECT count(*) FROM public.member_grades mg
                     WHERE mg.ratee_id = l.user_id) AS seller_total_grades,
                   (SELECT count(*) FROM public.member_grades mg
                     WHERE mg.ratee_id = l.user_id
                       AND mg.verdict = 'positive') AS seller_positive_grades,
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
        # A block hides the listing on the deep-link path too, otherwise the
        # browse filter is cosmetic: a Target Hit URL, a shared link or a
        # guessed id would still open a blocked member's listing.
        #
        # Deliberately the SAME 404 as "no such listing", not a 403. A distinct
        # status would confirm the listing exists to the person who was blocked,
        # which is exactly what they must not learn.
        if r is not None and await is_blocked(conn, user_id, str(r["user_id"])):
            r = None
    if r is None:
        raise error_response(404, "Listing not found", code="LISTING_NOT_FOUND")

    # Imported from the offers router rather than redefined, so the listing
    # screen's "enough grades to show a percentage" rule is the SAME constant the
    # reputation endpoint uses. Two copies of a threshold drift.
    from app.features.p2p_offers_router import _MIN_GRADES_TO_SHOW

    _total_grades = int(r["seller_total_grades"] or 0)

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
        seller_profile_public=bool(_row_get(r, "seller_profile_public")),
        seller_since=r["seller_since"],
        seller_collection_size=int(r["seller_items"] or 0),
        seller_active_listings=int(r["seller_listings"] or 0),
        seller_completed_trades=int(r["seller_completed_trades"] or 0),
        seller_total_grades=_total_grades,
        seller_positive_grades=int(r["seller_positive_grades"] or 0),
        # None below the shared threshold. Rounded to a whole number: a decimal
        # on a sample of four grades is false precision.
        seller_positive_pct=(
            round(100.0 * int(r["seller_positive_grades"] or 0) / _total_grades)
            if _total_grades >= _MIN_GRADES_TO_SHOW else None
        ),
        watchers=int(r["watchers"] or 0),
        watchers_above_price=int(r["watchers_above"] or 0),
        # A delisted row keeps its stored status ('sold'/'delisted'), so the
        # client can render "sold" rather than implying it is still buyable.
        status=r["status"], created_at=r["created_at"],
        reaches_target_hit=_reaches_target_hit(r["canonical_key"], r["category"]),
        is_mine=str(r["user_id"]) == user_id,
    )


async def _fx_arrays() -> tuple[list[str], list[Decimal]]:
    """FX rates as two parallel ARRAYS, for `unnest(...) AS fx(code, rate)`.

    Extracted so the second caller cannot re-derive the trap the first one
    documents: passing the rate map as **jsonb** looks equivalent and is not.
    `app/db.py` registers a jsonb codec with `encoder=json.dumps`, so an
    already-serialised string gets double-encoded into a JSON *string*,
    `->> 'JPY'` returns NULL, and `COALESCE(..., 1)` then silently leaves every
    foreign price unconverted. That shipped, and passed a direct-connection
    probe — a raw asyncpg connection has no such codec, so only a request
    through the real pool showed it. Arrays have no custom codec on either.

    Decimal via `str`: `Decimal(float)` would carry the float's binary error
    into a numeric comparison
    (learning_guard_must_match_constraint_type_space).
    """
    from app.lib.fx_service import get_rates
    rate_map: dict[str, Decimal] = {"EUR": Decimal("1")}
    for cur, rate in (await get_rates()).items():
        if rate and rate > 0:
            rate_map[cur.upper()] = Decimal(str(rate))
    codes = list(rate_map.keys())
    return codes, [rate_map[c] for c in codes]


class WatchlistMatch(BaseModel):
    """A live member listing for something the caller is already watching."""
    # The WATCHLIST row id, not the item's. The client's WatchlistItem type has
    # no item_id field at all (src/data/types.ts) — it never needed one — so
    # keying on the row id lets the watchlist screen join these in without
    # widening that type or re-deriving canonical keys on the client.
    watchlist_id: str
    listing_id: str
    title: str
    price: float
    currency: str
    price_eur: Optional[float] = None
    image_url: Optional[str] = None
    condition_label: Optional[str] = None
    # True when this listing is at or below the target the member set. That is
    # exactly the condition that fires a Target Hit, so the screen can mark the
    # ones that already met the user's own number rather than presenting every
    # match as equally interesting.
    meets_target: bool = False


class WatchlistMatchResponse(BaseModel):
    matches: List[WatchlistMatch] = []


@router.get("/watchlist-matches", response_model=WatchlistMatchResponse,
            summary="Live member listings for items I'm watching")
async def watchlist_matches(
    user_id: str = Depends(get_current_user_id),
) -> WatchlistMatchResponse:
    """Join the caller's watchlist to live `sparrow` listings.

    The marketplace and the watchlist were built as separate features and never
    met on screen. A member could be watching a Bayou while another member had
    one listed, and the only way to find out was a push notification firing at
    the right moment — miss it, and the two halves never connect again.

    This is the pull side of Target Hit: same join, no time window, no alert.
    Someone who opens their watchlist should see what is buyable right now.

    Deliberately reuses the snipe's EXACT-identity arm only
    (`item_ref = category:item_id`), not its trigram title fallback. The fuzzy
    arm exists so free-text watchlist rows can still fire an alert, and it is
    tuned for that with a 0.55 threshold; showing a fuzzy match as "a member is
    selling this" states something stronger than the data supports. An alert
    that is occasionally loose is recoverable — the user reads it and moves on.
    A permanent row on the watchlist screen asserting the wrong item is not.
    """
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code="DB_UNAVAILABLE")

    async with pool.acquire() as conn:
        hidden = await blocked_user_ids(conn, user_id)
        rows = await conn.fetch(
            # archived-exempt: matches WATCHLIST rows to live listings. Keyed
            # off the listing, and items is joined only for the photo.
            """
            SELECT DISTINCT ON (w.id)
                   w.id AS watchlist_id, w.target_price,
                   l.id AS listing_id, l.listing_title, l.price, l.currency,
                   l.condition_label,
                   COALESCE(i.image_url, ci.image_url) AS image_url,
                   l.price * COALESCE(fx.rate, 1) AS price_eur
            FROM public.watchlist_items w
            JOIN public.marketplace_listings l
              -- watchlist_items.item_id is BARE and marketplace_listings
              -- .canonical_key is BARE too, so these join directly. It is
              -- market_hits.item_ref that is namespaced
              -- (learning_canonical_key_vs_item_ref_namespace).
              ON l.canonical_key = w.item_id
             AND l.category = w.category
             AND l.marketplace_id = $2
             AND l.status = $3
             AND l.delisted_at IS NULL
            LEFT JOIN unnest($4::text[], $5::numeric[]) AS fx(code, rate)
                   ON fx.code = l.currency
            LEFT JOIN public.items i ON i.id = l.item_id
            LEFT JOIN public.category_items ci
                   ON ci.item_key = l.canonical_key AND ci.category = l.category
            WHERE w.user_id = $1::uuid
              AND w.item_id IS NOT NULL
              AND w.category IS NOT NULL
              -- Never show a member their OWN listing as something they can
              -- buy. Watching an item you also sell is legitimate, and telling
              -- someone "a member is selling this" about themselves is the same
              -- lie the `watchers` count avoids.
              AND l.user_id <> $1::uuid
              AND NOT (l.user_id = ANY($6::uuid[]))
            -- Cheapest per watchlist row. A watchlist screen has one line per
            -- row, so showing the best available price is the only honest
            -- single number; DISTINCT ON needs the ORDER BY to lead with the
            -- same expression it distinguishes on.
            ORDER BY w.id, l.price * COALESCE(fx.rate, 1) ASC
            """,
            user_id, SPARROW_MARKETPLACE_KEY, _STATUS_ACTIVE,
            *(await _fx_arrays()), hidden,
        )

    return WatchlistMatchResponse(matches=[
        WatchlistMatch(
            watchlist_id=str(r["watchlist_id"]),
            listing_id=str(r["listing_id"]),
            title=r["listing_title"],
            price=float(r["price"]),
            currency=r["currency"] or "EUR",
            price_eur=float(r["price_eur"]) if r["price_eur"] is not None else None,
            image_url=r["image_url"],
            condition_label=r["condition_label"],
            # `price_eur <= target_price` — deliberately the SAME comparison
            # deal_discovery_worker._check_watchlist_snipes makes, character for
            # character. If this screen and the alert disagreed about whether a
            # listing meets a target, one of them would be calling the user a
            # liar about their own number.
            #
            # It does mean both treat target_price as EUR while the column is
            # written in the member's display currency. That is a real
            # cross-currency gap, but it belongs to the alert, not to this
            # endpoint — fixing it HERE alone would create the disagreement this
            # comment exists to prevent. Recorded in docs/alerts-and-insights.md.
            meets_target=(
                r["target_price"] is not None
                and r["price_eur"] is not None
                and float(r["price_eur"]) <= float(r["target_price"])
            ),
        )
        for r in rows
    ])


class ListingPriceUpdate(BaseModel):
    """A seller changing what they are asking.

    Price only, deliberately. Title, category and canonical_key decide what the
    listing IS — editing those after members have watched, favourited and been
    alerted on it turns one listing into a different product with the same
    history. That is the bait-and-switch shape, and it is not worth having
    before there is a reason for it.
    """
    price: float = Field(..., gt=0, le=1_000_000)


async def _price_change_hook(listing_id: str, dropped: bool) -> None:
    """Re-point the buyable `market_hits` row at the new price.

    This is the whole "price drop alerts watchers" feature. There is no new
    alert type, no new worker and no `user_price_alerts` row — the last of those
    is explicitly forbidden by docs/alerts-and-insights.md, which records that
    the Rules tab is empty BY DESIGN and that a watchlist target IS the rule.

    `deal_discovery_worker._check_watchlist_snipes` already selects
    `market_hits` rows where `seen_at > now() - interval '30 minutes'` and
    `price_eur <= w.target_price`. So refreshing this row's price and `seen_at`
    is sufficient: the next cycle sees it, matches it to every watcher whose
    declared target the NEW price now meets, and fires Target Hit with the
    existing 24h-per-watchlist dedupe and plan gating already applied. Nothing
    here needs to know about users at all.

    That is why this is better than Vinted's version of the same feature, which
    notifies everyone who favourited. A watchlist row carries a target price, so
    we notify the people for whom the new price is actually news.

    UPDATE, not INSERT. The publish hook guards with
    `WHERE NOT EXISTS (provider='sparrow' AND listing_id=...)` precisely because
    a second buyable row would make Target Hit surface one listing twice.
    Verified against prod that this works even when `seen_at` moves the row
    across a monthly partition boundary.

    `seen_at` is refreshed ONLY on a drop. A price RISE must not re-enter the
    alert window: "listed below your target" is the promise, and waking someone
    to say an item got more expensive is a notification with no action — the
    exact thing the alert consolidation deleted three workers to stop doing. The
    price is still corrected in place so the row never advertises a stale figure.
    """
    pool = get_db_pool()
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT l.price, l.currency, l.listing_title
                FROM public.marketplace_listings l
                WHERE l.id = $1::uuid AND l.status = $2 AND l.delisted_at IS NULL
                """,
                listing_id, _STATUS_ACTIVE,
            )
            if row is None:
                return

            from app.lib.fx_service import convert_to_eur
            price_eur = await convert_to_eur(float(row["price"]), row["currency"] or "EUR")

            updated = await conn.fetchval(
                """
                UPDATE public.market_hits
                   SET price = $2,
                       price_eur = $3,
                       title = $4,
                       observed_at = now(),
                       -- Only a drop re-enters the 30-minute snipe window.
                       seen_at = CASE WHEN $5 THEN now() ELSE seen_at END
                 WHERE provider = 'sparrow' AND listing_id = $1
                RETURNING 1
                """,
                str(listing_id), float(row["price"]), price_eur,
                row["listing_title"], dropped,
            )
            if updated is None:
                # No buyable row to update. Normal and expected when the listing
                # has no canonical identity — the publish hook skipped it (only
                # 4 of 16 items carry a canonical_key, measured 2026-08-07).
                # Logged at INFO because it is a coverage gap, not a failure;
                # the seller is told the same thing by `reaches_target_hit`.
                logger.info(
                    "[p2p] price change on %s had no buyable row to update "
                    "(listing likely has no canonical identity)", listing_id,
                )
                return
            logger.info(
                "[p2p] price change on %s -> %.2f %s (dropped=%s, alert window %s)",
                listing_id, float(row["price"]), row["currency"], dropped,
                "refreshed" if dropped else "unchanged",
            )
    except Exception as exc:
        logger.warning("[p2p] price change hook failed for %s: %s", listing_id, exc)


@router.patch("/listings/{listing_id}", response_model=ListingOut,
              summary="Change a listing's price")
async def update_listing_price(
    listing_id: str,
    payload: ListingPriceUpdate,
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(_listing_write_limit),
) -> ListingOut:
    """Lower (or raise) the asking price on your own live listing.

    Until this existed there was no price edit of ANY kind — a seller who wanted
    to drop their price had to delist and relist, and forgetting to delist first
    returned 409 ALREADY_LISTED, which reads as the app being broken. Dropping
    the price is the single most effective seller action on Vinted, and we could
    not do it at all. See docs/P2P_MARKETPLACE_SPEC.md §8b.
    """
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code="DB_UNAVAILABLE")

    async with pool.acquire() as conn:
        # Ownership AND liveness in one guarded UPDATE, so there is no window
        # between checking and writing. `status = active AND delisted_at IS NULL`
        # matters beyond tidiness: re-pricing a SOLD listing would push a
        # buyable row back into the snipe window for something that is gone,
        # which is the failure _stale_supply_hook exists to prevent.
        row = await conn.fetchrow(
            """
            UPDATE public.marketplace_listings
               SET price = $3, updated_at = now()
             WHERE id = $1::uuid AND user_id = $2::uuid
               AND status = $4 AND delisted_at IS NULL
            RETURNING id, price, currency,
                      -- The OLD price, captured in the SAME statement. Reading
                      -- it in a separate SELECT would race two concurrent edits
                      -- and could report a drop as a rise — which decides
                      -- whether watchers get alerted.
                      --
                      -- A sub-SELECT in RETURNING is evaluated against the
                      -- statement's snapshot, so it does NOT see this UPDATE's
                      -- own effect. Verified on the server rather than assumed:
                      -- new_price 80, subquery_price 100.
                      (SELECT l2.price FROM public.marketplace_listings l2
                        WHERE l2.id = $1::uuid) AS previous_price
            """,
            listing_id, user_id, payload.price, _STATUS_ACTIVE,
        )

    if row is None:
        # Deliberately ONE 404 for "not yours", "does not exist" and "already
        # sold". Distinguishing the first two would confirm the existence of
        # another member's listing to someone probing ids.
        #
        # Note there is no `price IS DISTINCT FROM` guard in the UPDATE: an
        # unchanged price must be a 200, not this 404. A seller who re-saves the
        # same number has done nothing wrong, and answering "no live listing of
        # yours to update" would be both alarming and false.
        raise error_response(
            404, "No live listing of yours to update", code="LISTING_NOT_FOUND",
        )

    # AWAITED, not fire-and-forget. The publish hook is spawned because a missing
    # buyable row is a non-event, but here the row already exists and is now
    # ADVERTISING A PRICE THE SELLER NO LONGER ASKS. A stale higher price is a
    # missed sale; a stale lower one sends a buyer to a listing that costs more
    # than the alert promised, which is the trust failure this whole stage is
    # scoped to avoid.
    previous = float(row["previous_price"])
    if float(payload.price) != previous:
        await _price_change_hook(listing_id, float(payload.price) < previous)

    return await get_listing(listing_id, user_id=user_id)


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

    # The 24-hour clock has to start somewhere. Both the Marketplace Terms (§5)
    # and the Acceptable Use Policy (§9) now promise action on objectionable or
    # unlawful content "within 24 hours of receiving them" — which was a claim
    # with nothing behind it: reports landed in a table nobody was told about.
    # A commitment that depends on someone happening to check a queue is not a
    # commitment. Only on a NEW report (`inserted`), so re-reports cannot be
    # used to spam the ops channel.
    #
    # Fire-and-forget and never raises: a paging failure must not turn a
    # successful report into an error for the member who filed it. The row is
    # already committed, so the report survives regardless.
    if inserted is not None:
        spawn_bg(_page_ops_new_report(listing_id, payload.reason), "p2p_report_page")

    return {"ok": True}


# ── DSA moderation — Article 16 notice-and-action, Article 17 statement of reasons ──
#
# Article 17 sits in SECTION 2 of the DSA (hosting services), so the Article 19
# micro-enterprise exclusion does NOT reach it — that exclusion only covers
# Section 3 (Arts 20-28). Acting on a report and saying nothing to the seller is
# therefore not an option available to us at any size.
#
# The report intake above already satisfied Art 16. What was missing was the
# other half: `listing_reports` has had `status`, `resolution_note` and
# `resolved_at` columns since Stage 1 and NOTHING ever wrote them, and the
# seller was never told. Storage without a writer and without a reader is the
# exact shape this codebase keeps shipping (learning_silent_fallbacks_hide_dead_features).
#
# Ops Key rather than JWT, and namespaced under /ops/ to match
# /ops/catalog-suggestions/{id}/action — this is an operator action, not a user
# one. See docs/API.md "Operations".

_MODERATION_GROUNDS = {
    # Art 17(3)(d)-(e): the statement must say whether the ground is a legal one
    # or a contractual one, because the redress route differs.
    "illegal_content": "the content is unlawful",
    "terms_breach": "the content breaches the Sparrow marketplace terms",
    "counterfeit": "the item appears to be counterfeit or a replica",
    "prohibited_item": "the item is not permitted on Sparrow",
    "misleading": "the listing description is materially misleading",
}


def _compose_statement(
    listing_title: str,
    removed: bool,
    ground: str,
    explanation: Optional[str],
) -> str:
    """Build the Art 17 statement of reasons.

    A pure function so the required elements can be asserted directly. Art 17(3)
    lists what a statement MUST contain, and an operator typing free text would
    omit one of them sooner or later:

      (a) whether the content was removed / access disabled  -> the verb below
      (c) the facts and circumstances relied on              -> title + ground
                                                                (+ explanation)
      (b) whether AUTOMATED MEANS were used                  -> stated explicitly
      (d)/(e) the legal or contractual ground                -> _MODERATION_GROUNDS
      (f) redress possibilities                              -> the closing line

    The automated-means sentence is true only while every decision comes from a
    human calling this endpoint. If automated moderation is ever added, this
    sentence has to change with it — pinned by
    test_statement_declares_no_automated_means.
    """
    ground_text = _MODERATION_GROUNDS[ground]
    parts = [
        f'Your listing "{listing_title}" was '
        + ("removed" if removed else "reviewed and left online")
        + f" following a report from another member. Ground: {ground_text}."
    ]
    if explanation:
        parts.append(f"Details: {explanation}")
    parts.append(
        "This decision was made by a person, not automatically. "
        "If you believe it is wrong, contact support and it will be reviewed again."
    )
    return " ".join(parts)


class ModerationAction(BaseModel):
    """An operator's decision on a reported listing."""

    # 'remove' takes the listing down; 'dismiss' closes the reports and leaves
    # it up. Both are decisions, and Art 17 is owed for a removal.
    action: str = Field(..., pattern=r"^(remove|dismiss)$")
    ground: str = Field(..., max_length=40)
    # Free text shown verbatim to the seller. Art 17(3)(c) wants the facts and
    # circumstances relied on, not just a category.
    explanation: Optional[str] = Field(None, max_length=1000)


# Prefix-less, so the paths land at /ops/... rather than /p2p/ops/... — the
# convention every other operator endpoint follows (see docs/API.md
# "Operations" and /ops/catalog-suggestions). Registered separately in main.py.
ops_router = APIRouter(tags=["P2P Moderation"])


@ops_router.get("/ops/listing-reports", summary="Open moderation queue (ops)")
async def list_open_reports(
    _: bool = Depends(require_ops_key),
    pagination: tuple[int, int] = Depends(pagination_params),
) -> dict:
    """Reported listings awaiting a decision, oldest first.

    Oldest first on purpose: Art 16 requires timely handling, and a
    newest-first queue lets the oldest complaint starve
    (learning_per_category_fairness_in_select_queues).
    """
    limit, offset = pagination
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code="DB_UNAVAILABLE")

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT r.listing_id,
                   count(*)            AS open_reports,
                   min(r.created_at)   AS first_reported_at,
                   array_agg(DISTINCT r.reason) AS reasons,
                   l.listing_title, l.user_id AS seller_id, l.status
            FROM public.listing_reports r
            JOIN public.marketplace_listings l ON l.id = r.listing_id
            WHERE r.status = 'open'
            GROUP BY r.listing_id, l.listing_title, l.user_id, l.status
            ORDER BY min(r.created_at) ASC
            LIMIT $1 OFFSET $2
            """,
            limit, offset,
        )
    return {"reports": [
        {
            "listing_id": str(r["listing_id"]),
            "listing_title": r["listing_title"],
            "seller_id": str(r["seller_id"]),
            "listing_status": r["status"],
            "open_reports": int(r["open_reports"]),
            "first_reported_at": r["first_reported_at"],
            "reasons": list(r["reasons"] or []),
        }
        for r in rows
    ]}


@ops_router.post("/ops/listing-reports/{listing_id}/action",
                 summary="Decide a reported listing + issue the DSA statement of reasons (ops)")
async def action_listing_reports(
    listing_id: str,
    payload: ModerationAction,
    _: bool = Depends(require_ops_key),
) -> dict:
    """Resolve every open report on a listing, and TELL THE SELLER why.

    The statement of reasons is not a nicety bolted on afterwards — under
    Art 17 it is the thing that makes the removal lawful. It is written in one
    transaction with the takedown so a listing cannot end up removed with the
    seller un-notified.

    Delivered through `notification_history`, which the app already reads and
    badges (`GET /notifications/history`, rendered by app/notifications.tsx).
    Storing it only in `listing_reports.resolution_note` would be capture
    without a consumer — the seller would never see it.
    """
    if payload.ground not in _MODERATION_GROUNDS:
        raise error_response(
            400,
            f"Unknown ground. Expected one of: {', '.join(sorted(_MODERATION_GROUNDS))}",
            code="UNKNOWN_GROUND",
        )

    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code="DB_UNAVAILABLE")

    removed = payload.action == "remove"

    async with pool.acquire() as conn:
        listing = await conn.fetchrow(
            """
            SELECT id, user_id AS seller_id, listing_title, status, delisted_at
            FROM public.marketplace_listings
            WHERE id = $1::uuid AND marketplace_id = $2
            """,
            listing_id, SPARROW_MARKETPLACE_KEY,
        )
        if listing is None:
            raise error_response(404, "Listing not found", code="LISTING_NOT_FOUND")

        statement = _compose_statement(
            listing["listing_title"], removed, payload.ground, payload.explanation
        )

        async with conn.transaction():
            resolved = await conn.fetchval(
                """
                UPDATE public.listing_reports
                   SET status = $2, resolution_note = $3, resolved_at = now()
                 WHERE listing_id = $1::uuid AND status = 'open'
                RETURNING 1
                """,
                listing_id,
                "actioned" if removed else "dismissed",
                statement,
            )

            if removed and listing["delisted_at"] is None:
                await conn.execute(
                    """
                    UPDATE public.marketplace_listings
                       SET status = 'delisted', delisted_at = now(), updated_at = now()
                     WHERE id = $1::uuid
                    """,
                    listing_id,
                )

            # Same transaction as the takedown. If the notification insert
            # fails, the removal rolls back with it — better a listing that is
            # still up than one removed with the seller never told.
            await conn.execute(
                """
                INSERT INTO public.notification_history
                    (user_id, type, title, body, data, deep_link)
                VALUES ($1::uuid, 'moderation', $2, $3, $4::jsonb, $5)
                """,
                str(listing["seller_id"]),
                "Listing removed" if removed else "Report reviewed — no action",
                statement,
                json.dumps({
                    "listing_id": listing_id,
                    "action": payload.action,
                    "ground": payload.ground,
                    "automated": False,
                }),
                f"sparrow://listing/{listing_id}",
            )

    # Awaited, NOT fire-and-forget. A removed listing that keeps its buyable
    # market_hits row still fires Target Hits at content we just took down —
    # the same bug the delist path was fixed for in Stage 1.
    if removed:
        await _stale_supply_hook(listing_id)

    return {
        "ok": True,
        "action": payload.action,
        "reports_resolved": resolved is not None,
        "seller_notified": True,
    }
