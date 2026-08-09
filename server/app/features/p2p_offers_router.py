"""P2P Stage 2 — offers, two-sided completion, mutual grading.

See docs/P2P_MARKETPLACE_SPEC.md. Stage 1 is listings only; this adds the
negotiation and trust loop AROUND those listings. Sparrow still never touches
funds — accepting an offer opens a conversation, it does not take a payment.

Three decisions are load-bearing, and each is a deliberate refusal to pretend
we have leverage we do not:

1. **Accept reserves softly, it does not lock.** With no payment rail a hard
   reserve is unenforceable, and would let a bad actor serially block
   competitors' listings for free. Walking away is RECORDED instead
   (`withdrawn_by`), which is the only sanction we can honestly apply.

2. **Completion is two-sided.** Seller marks sent, buyer marks received.
   Grading unlocks only when both have. A lone account cannot farm ratings.
   Two colluding accounts still can — that is unavoidable without a payment
   record, and the honest response is to say so, not to add theatre.

3. **Grades are anchored to a completed offer, enforced in the DB**
   (`member_grades.offer_id NOT NULL`, unique per rater). An unanchored grade
   is exactly the farmable rating this design exists to prevent.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app.auth import get_current_user_id
from app.errors import error_response
from app.features.pagination import pagination_params
from app.lib.blocks import raise_if_blocked
from app.lib.db_helpers import get_db_pool
from app.rate_limit import per_user_rate_limit

logger = logging.getLogger(__name__)

# NOTE: this uses `public.p2p_offers`, NOT `public.offers`. The latter belongs
# to the deal/mandate system — its FK points at `public.listings` and
# app/agents/{deal_completion,deal_risk}.py JOIN through it. Sharing the table
# would have broken those agents; the Stage 2 E2E surfaced this as an
# offers_listing_id_fkey violation on the very first run.

router = APIRouter(prefix="/p2p", tags=["P2P Marketplace"])

_offer_limit = per_user_rate_limit(30, window_seconds=60, scope="p2p_offer")
_grade_limit = per_user_rate_limit(20, window_seconds=300, scope="p2p_grade")

# Mirrors p2p_offers_status_check. Verified against pg_constraint — the CHECK is
# narrower than plain English and 'withdrawn' is NOT among them, which is why
# a walk-away sets status='cancelled' plus withdrawn_by, rather than inventing
# a status the DB would reject (learning_db_constraints_narrower_than_code).
_PENDING, _COUNTERED, _ACCEPTED = "pending", "countered", "accepted"
_DECLINED, _CANCELLED, _EXPIRED = "declined", "cancelled", "expired"
_SHIPPED, _COMPLETED = "shipped", "completed"

# Below this many grades a member's score is hidden rather than shown. One bad
# grade out of one is not a reputation, it is a coin flip, and presenting it as
# a percentage would be actively misleading.
_MIN_GRADES_TO_SHOW = 3

# The offer column list, in ONE place. It was duplicated verbatim across three
# queries; adding tracking to two of the three would have produced a KeyError in
# _row_to_offer on whichever path was missed, and only on that path
# (learning_duplicate_impl_silently_drops_the_fix). Static text, never
# user-derived — safe to interpolate.
_OFFER_COLUMNS = """
            o.id, o.listing_id, o.buyer_id, o.seller_id, o.amount,
            o.currency, o.status, o.message, o.counter_count,
            o.created_at, o.seller_confirmed_at, o.buyer_confirmed_at,
            o.tracking_carrier, o.tracking_code, o.tracking_set_at,
            l.listing_title,
            -- The ASKING price, so a counter can be expressed as a percentage of
            -- it. Without this the counter UI could only work off the buyer's own
            -- offer, where "-5%" means "less than they already offered" — a
            -- button no seller would ever press. The client must not guess a
            -- reference price it does not hold.
            l.price AS listing_price
"""

# Carrier key -> (display label, tracking URL template or None).
#
# None means "we know this carrier but cannot build a working link from the
# consignment code alone". PostNL and DPD both require the RECIPIENT'S POSTCODE
# in the URL, and we deliberately do not hold it — so they render a copyable
# code and no button. A link that 404s is the dead-button failure Stage 1's bug
# 0 was fixed to avoid, reintroduced from our own side; an absent link is
# honest, a broken one is not.
#
# Adding a carrier is a change HERE ONLY — deliberately not a DB CHECK, see
# server/migrations/20260807_p2p_offer_tracking.sql.
#
# Nothing in this map may ever be polled. Tracking is display-only; see §5b of
# docs/P2P_MARKETPLACE_SPEC.md.
_CARRIER_TRACKING: dict[str, tuple[str, Optional[str]]] = {
    # NL/BE first — that is where ships_from concentrates.
    "postnl":      ("PostNL", None),          # needs recipient postcode
    "dpd":         ("DPD", None),             # needs recipient postcode
    "gls":         ("GLS", None),             # no stable code-only public URL
    "bpost":       ("bpost", None),
    "dhl":         ("DHL", "https://www.dhl.com/en/express/tracking.html?AWB={code}"),
    "dhl_de":      ("DHL Paket", "https://nolp.dhl.de/nextt-online-public/en/search?piececode={code}"),
    "ups":         ("UPS", "https://www.ups.com/track?tracknum={code}"),
    "fedex":       ("FedEx", "https://www.fedex.com/fedextrack/?trknbr={code}"),
    "other":       ("Other carrier", None),
}


def _tracking_url(carrier: Optional[str], code: Optional[str]) -> Optional[str]:
    """Resolve a carrier + code to the CARRIER's own tracking page, or None.

    Returns None for an unknown carrier as well as a known-but-unlinkable one,
    so a carrier key that predates a registry entry degrades to a copyable code
    rather than to a broken link.
    """
    if not carrier or not code:
        return None
    entry = _CARRIER_TRACKING.get(carrier)
    if entry is None or entry[1] is None:
        return None
    return entry[1].format(code=quote(code, safe=""))


def _carrier_label(carrier: Optional[str]) -> Optional[str]:
    if not carrier:
        return None
    entry = _CARRIER_TRACKING.get(carrier)
    return entry[0] if entry else carrier


class OfferCreate(BaseModel):
    listing_id: str
    amount: float = Field(..., gt=0, le=1_000_000)
    currency: str = Field(default="EUR", max_length=3, pattern=r"^[A-Z]{3}$")
    message: Optional[str] = Field(None, max_length=1000)


class OfferOut(BaseModel):
    id: str
    listing_id: str
    listing_title: Optional[str] = None
    # The listing's ASKING price. The counter UI expresses its presets as a
    # percentage of this; null (a listing row that vanished) means the client
    # falls back to the offer amount and says so, rather than showing a
    # percentage computed from nothing.
    listing_price: Optional[float] = None
    buyer_id: str
    seller_id: str
    amount: float
    currency: str
    status: str
    message: Optional[str] = None
    counter_count: int = 0
    created_at: Optional[datetime] = None
    seller_confirmed_at: Optional[datetime] = None
    buyer_confirmed_at: Optional[datetime] = None
    # Shipment visibility. DISPLAY ONLY — no completion may be derived from it;
    # see docs/P2P_MARKETPLACE_SPEC.md §5b.
    tracking_carrier: Optional[str] = None
    tracking_carrier_label: Optional[str] = None
    tracking_code: Optional[str] = None
    tracking_set_at: Optional[datetime] = None
    # Resolved SERVER-side so the carrier URL table exists once. A second copy
    # in the client would drift, and a stale template there is a dead button we
    # could not fix without an app release.
    tracking_url: Optional[str] = None
    # Convenience for the client so it does not re-derive the rules below.
    i_am_buyer: bool = False
    can_confirm: bool = False
    can_grade: bool = False
    already_graded: bool = False
    # Whether the CALLER may attach tracking right now. Server-computed for the
    # same reason as can_confirm — the client never re-derives the state machine.
    can_add_tracking: bool = False
    # ── Price sanity, ported from the retired Deal Desk (deal_risk.py) ────────
    # The ONE thing that layer had which P2P did not, and it works better here:
    # it compares an offer against the SOLD distribution, and P2P is what
    # produces sold comps in the first place (_sold_comp_hook, spec §1g). Deal
    # Desk never generated one, so its own check had almost nothing to compare
    # against.
    #
    # null = we could not judge (no canonical identity, or too few comps). That
    # is deliberately distinct from "fine": a confident-looking "normal price"
    # computed off two data points is worse than saying nothing.
    price_verdict: Optional[str] = None          # 'low' | 'normal' | 'high'
    price_note: Optional[str] = None             # one human sentence, or null
    price_sample_size: Optional[int] = None


# Ported from the retired Deal Desk (`deal_risk.compute_risk_flags`) — the one
# capability that layer had which P2P did not.
#
# It works BETTER here than it ever did there. The check compares an offer to
# the SOLD distribution, and P2P is what produces sold comps in the first place
# (`_sold_comp_hook`, spec §1g); Deal Desk generated none, so its own check had
# almost nothing to compare against.
#
# Kept from the original: the 2-sigma / 3-sigma test against `market_hits` rows
# with `is_listing IS NOT TRUE` over 180 days. Comparing against ASKING prices
# would just compare hope to hope.
#
# Dropped from the original: its seller-trust half, which counted rows in the
# Deal Desk `offers` table and averaged `deal_ratings`. P2P already answers that
# through `member_grades` / `completed_trades` / `seller_positive_pct`, with a
# 3-grade threshold before a percentage is shown at all. Porting it would have
# been a second implementation of something that already works.
MIN_PRICE_SAMPLE = 5


# ── DAC7 reportable-seller thresholds ───────────────────────────────────────
#
# `app/legal/marketplace-terms.tsx` tells members, in writing, that above 30
# sales or EUR 2,000 in a year we will ask them for reporting details and warn
# them before anything is filed. Until now that sentence had NOTHING behind it:
# no counter, no notice, no way to demonstrate that everyone else was below the
# line. A promise in a legal screen with no code behind it is the worst version
# of this — it is the one we would be held to.
#
# A seller is an EXCLUDED SELLER only if BOTH limbs hold (fewer than 30 sales
# AND at most EUR 2,000), so crossing EITHER makes them reportable. The `or`
# below is the whole rule and the easiest thing to get backwards: `and` would
# miss a member with 40 sales of EUR 20 each.
DAC7_SALES_LIMIT = 30
DAC7_GROSS_EUR_LIMIT = 2000.0


def dac7_reportable(sales_count: int, gross_eur: float) -> bool:
    """Is this seller REPORTABLE for the year?

    An EXCLUDED SELLER is one where BOTH limbs hold — fewer than 30 sales AND at
    most EUR 2,000 — so reportable is **OR**, not AND. Writing `and` here
    under-reports every high-volume/low-value seller (40 sales at EUR 20 is the
    shape that slips through) and nothing else in the system would notice,
    because the failure mode is silence.

    ONE definition, three consumers: the accrual on the completion path, the
    `GET /p2p/dac7/me` status endpoint, and the tests. It used to be inlined in
    the accrual with the test file defining its own mirror of it — so the test
    was asserting a COPY of the rule and could have passed while the real one
    drifted (learning_tests_that_pin_a_stub).
    """
    return sales_count >= DAC7_SALES_LIMIT or gross_eur > DAC7_GROSS_EUR_LIMIT


# ── Trade notifications ─────────────────────────────────────────────────────
#
# Until 2026-08-09 a P2P trade sent NO notifications at all: the only notify_user
# call in this module was the DAC7 threshold notice. An offer arrived as a row on
# a screen the seller had to think to open, and a buyer learned their offer was
# accepted the same way. The listing screen even told the buyer "the seller will
# be notified" — a promise with nothing behind it
# (learning_a_written_promise_to_users_is_a_spec).
#
# Both sides get told about every state change, because a negotiation where one
# party is waiting on news that never arrives is worse than no negotiation.
#
# `category="account"` and `urgent=True`, deliberately:
#   * account maps to the `system` feed icon (docs/alerts-and-insights.md's
#     translation table). These are FACTS about a trade the member is party to,
#     not discovery alerts, and they must not wear a deal-alert badge that reads
#     as "something to act on for profit".
#   * NOT `deal_alerts` — that preference is "when the Smart Deal Agent finds a
#     match". Coupling "your buyer accepted" to that toggle means turning off
#     discovery silently turns off transactional news.
#   * urgent skips the per-plan frequency cap (5/15/30 per 24h). A free user
#     already at their cap must still learn their offer was accepted. Volume is
#     naturally bounded: one live offer per buyer per listing, and the rest are
#     responses to it.
async def _notify_trade(conn, user_id: str, title: str, body: str, offer_id: str) -> None:
    """Tell one party about a trade event. NEVER raises.

    A notification that fails must not roll back or 500 a trade that already
    happened — the offer/accept/confirm is the durable fact, this is the courtesy.
    Logged at error level because warn is stripped in release builds, which is
    exactly where a silently missing notification would be invisible
    (learning_prod_logger_strips_info_warn).
    """
    try:
        from app.lib.notify import notify_user
        await notify_user(
            conn,
            user_id,
            title,
            body,
            category="account",
            data={"kind": "p2p_offer", "offer_id": offer_id},
            deep_link="/offers",
            urgent=True,
        )
    except Exception as exc:  # best-effort: the trade already succeeded
        logger.error("[p2p] trade notification failed for %s: %s", user_id, exc)


async def _settle_completed_trade(conn, offer_id: str, listing_id: str,
                                  buyer_id: str, seller_id: str,
                                  amount: float, currency: str) -> None:
    """Move the object, not just the paperwork.

    Completion used to update `p2p_offers`, mark the listing sold, remove the
    buyable row and write a sold comp — and leave `items` completely untouched.
    The seller kept the thing they had sold in their collection (so their
    portfolio AND their public profile value both still counted it) and the buyer
    had nothing: no price tracking, no set-completion, no way to relist it. Asked
    2026-08-09: "does it get removed from the items of the seller and added to
    buyer items". It did not.

    Four things settle here. A census of prod on 2026-08-09 found the only
    completed trade there had leaked the first three:

    1. The seller's item is retired (or decremented, if they own several).
       Prod: the sold item was still unarchived in the seller's collection.
    2. The buyer gets a NEW item — never the seller's row.
       Prod: the buyer had nothing at all.
    3. The listing's soft reservation is released.
       Prod: `reserved_offer_id` still pointed at the completed offer.
    4. Every OTHER buyer's live offer on that listing is declined, and they are
       told. Without this they sit on an open offer for an object that is gone.
       Prod: 0 rows today, because no listing has yet drawn two live offers.

    WHY A NEW ROW AND NOT A REASSIGNMENT. Handing `items.user_id` to the buyer
    would hand over the seller's `purchase_price`, `purchase_notes`,
    `acquired_from` and `cost_basis` — what they paid and where they got it. The
    buyer receives the PUBLIC facts only: what it is, its catalogue identity, the
    condition and description the listing advertised, and the price THEY paid.

    The photo is copied only when the seller ticked `photo_catalogue_consent`.
    Their photograph is theirs otherwise, so the buyer's item falls back to the
    catalogue image the same way any other item does.

    Never raises. A settled trade is a fact; failing to move an item must not
    500 a completion that already happened, and it is reconstructible from the
    offer row.
    """
    try:
        from app.lib.fx_service import convert_to_eur

        l = await conn.fetchrow(
            """
            SELECT l.item_id, l.canonical_key, l.category, l.condition_label,
                   l.listing_description, l.listing_title,
                   l.photo_catalogue_consent,
                   i.image_url, COALESCE(i.quantity, 1) AS quantity
            FROM public.marketplace_listings l
            LEFT JOIN public.items i ON i.id = l.item_id
            WHERE l.id = $1::uuid
            """,
            listing_id,
        )
        if l is None:
            return

        # 3. Release the soft reserve. Left set, a completed listing still looks
        #    reserved to anything reading that column.
        await conn.execute(
            """
            UPDATE public.marketplace_listings
               SET reserved_offer_id = NULL, reserved_at = NULL, updated_at = now()
             WHERE id = $1::uuid
            """,
            listing_id,
        )

        # 1. Retire the seller's copy. A seller with THREE of something who sells
        #    one still owns two, so archiving the row would delete two items from
        #    their collection. Decrement instead.
        #
        #    `for_sale` is deliberately NOT touched here. The DB owns it: trigger
        #    `trg_sync_item_for_sale` on marketplace_listings recomputes it from
        #    the live listing set (scoped to marketplace_id='sparrow'), and the
        #    caller marks the listing 'sold' BEFORE calling us, so it has already
        #    fired and settled the flag. Verified in prod 2026-08-09: the one
        #    completed trade's item is correctly for_sale=false. Writing it again
        #    here would be a second, narrower implementation of that rule — it
        #    omits the 'sparrow' scope — and the two would drift.
        if l["item_id"]:
            if int(l["quantity"]) > 1:
                await conn.execute(
                    """
                    UPDATE public.items
                       SET quantity = GREATEST(COALESCE(quantity, 1) - 1, 0),
                           updated_at = now()
                     WHERE id = $1::uuid AND user_id = $2::uuid
                    """,
                    str(l["item_id"]), seller_id,
                )
            else:
                # Safe to archive unconditionally: p2p_listing_router enforces one
                # active listing per item, so there is no sibling listing left
                # pointing at a row we just retired.
                await conn.execute(
                    """
                    UPDATE public.items
                       SET archived = TRUE, updated_at = now()
                     WHERE id = $1::uuid AND user_id = $2::uuid
                    """,
                    str(l["item_id"]), seller_id,
                )

        # 2. Give the buyer their own row. `acquired_from` doubles as the
        #    idempotency key: re-running a settled trade must not mint a second
        #    item. `purchased_at` is a timestamptz and the paired-column trigger
        #    derives `purchase_date` from it — never bind a bare date here
        #    (learning_items_paired_columns_trigger).
        marker = f"sparrow:offer:{offer_id}"
        # archived-exempt: an idempotency probe, not a collection read. If the
        # buyer has already archived what they bought, re-running settlement
        # must still find it and NOT mint a second copy.
        already = await conn.fetchval(
            "SELECT 1 FROM public.items WHERE user_id = $1::uuid AND acquired_from = $2",
            buyer_id, marker,
        )
        if not already:
            amount_eur = await convert_to_eur(float(amount), currency or "EUR")
            await conn.execute(
                """
                INSERT INTO public.items
                    (user_id, name, category, canonical_key, condition,
                     description, image_url, source, for_sale, quantity,
                     purchase_price, purchase_currency, purchase_price_eur,
                     purchased_at, acquired_from, acquired_condition,
                     created_at, updated_at)
                VALUES ($1::uuid, $2, $3, $4, $5,
                        $6, $7, 'marketplace', FALSE, 1,
                        $8, $9, $10,
                        now(), $11, $5,
                        now(), now())
                """,
                buyer_id,
                l["listing_title"] or "Bought on Sparrow",
                l["category"],
                l["canonical_key"],
                l["condition_label"],
                l["listing_description"],
                # The seller's photograph is theirs unless they said otherwise.
                l["image_url"] if l["photo_catalogue_consent"] else None,
                float(amount),
                (currency or "EUR").upper(),
                amount_eur,
                marker,
            )

        # 4. Everyone else who was still negotiating for this object.
        losers = await conn.fetch(
            """
            UPDATE public.p2p_offers
               SET status = 'declined', updated_at = now()
             WHERE listing_id = $1::uuid AND id <> $2::uuid
               AND status IN ('pending', 'countered', 'accepted')
            RETURNING buyer_id, amount, currency
            """,
            listing_id, offer_id,
        )
        for r in losers:
            await _notify_trade(
                conn, str(r["buyer_id"]),
                "That item has sold",
                f"\"{l['listing_title'] or 'An item'}\" sold to another buyer, so "
                f"your {r['currency']} {float(r['amount']):.2f} offer was closed.",
                offer_id,
            )
    except Exception as exc:
        logger.error("[p2p] settling completed trade %s failed: %s", offer_id, exc)


async def _dac7_accrue(seller_id: str, amount: float, currency: str) -> None:
    """Accrue one completed sale against the seller's DAC7 year, and warn once.

    Runs on the completion path because completion is the only moment
    consideration becomes KNOWN — which is precisely what triggers DAC7 (spec
    §5a: the obligation is live now, because `p2p_offers.amount` is confirmed by
    both parties even though no money moves through us).

    Deliberate choices:

    * **EUR.** The threshold is denominated in EUR, so a USD sale must be
      converted before it is compared, or a member could sit above the limit
      indefinitely in a weak currency.
    * **Calendar year**, which is the reporting period.
    * **Notify once.** `notified_at` is the guard. Without it every subsequent
      sale re-sends the warning, and the member learns to ignore it.
    * **`reportable_at` is never cleared.** Crossing the threshold is a fact
      about the year; a later refund does not un-cross it.
    * **Swallow failures.** A completed trade must not 500 because a compliance
      counter could not be written. The counter is reconstructible from
      `p2p_offers` (that is the point of deriving it from completed rows);
      a failed completion is not.
    """
    pool = get_db_pool()
    if pool is None:
        return
    try:
        from app.lib.fx_service import convert_to_eur
        from app.lib.notify import notify_user

        amount_eur = await convert_to_eur(float(amount), currency or "EUR")

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO public.dac7_seller_year AS d
                    (user_id, year, sales_count, gross_eur, updated_at)
                VALUES ($1::uuid, EXTRACT(YEAR FROM now())::int, 1, $2, now())
                ON CONFLICT (user_id, year) DO UPDATE
                   SET sales_count = d.sales_count + 1,
                       gross_eur   = d.gross_eur + EXCLUDED.gross_eur,
                       updated_at  = now()
                RETURNING sales_count, gross_eur, year, reportable_at, notified_at
                """,
                seller_id, amount_eur,
            )
            if row is None:
                return

            crossed = dac7_reportable(int(row["sales_count"]), float(row["gross_eur"]))
            if not crossed or row["notified_at"] is not None:
                return

            # Stamp BEFORE sending. If the push fails we have still recorded
            # that the member crossed, and a duplicate warning is a worse
            # outcome than a missed one (the in-app row persists regardless —
            # notify_user writes history even when the push is suppressed).
            await conn.execute(
                """
                UPDATE public.dac7_seller_year
                   SET reportable_at = COALESCE(reportable_at, now()),
                       notified_at   = now(),
                       updated_at    = now()
                 WHERE user_id = $1::uuid AND year = $2
                """,
                seller_id, row["year"],
            )
            await notify_user(
                conn,
                seller_id,
                "About your sales and tax reporting",
                # INFORM, do not promise to collect. The earlier copy said "We'll
                # ask you for a few details first" — a promise with no form behind
                # it and nowhere to put the answer (there is no column for a TIN,
                # an address or an IBAN anywhere in the schema). Sparrow's stance
                # is that the seller handles their own tax position; this message
                # exists so they know the threshold is a real obligation, not a
                # Sparrow policy. Kept in step with marketplace-terms §6 —
                # if one changes, change both.
                (
                    f"You've passed {row['sales_count']} sales / "
                    f"EUR {float(row['gross_eur']):.0f} this year. Above that, "
                    "marketplaces are required to report sellers to tax "
                    "authorities, so this is the point to sort out your own tax "
                    "position. We don't file anything for you, and we'll tell you "
                    "before anything about you is sent."
                ),
                category="account",
                data={"kind": "dac7_threshold", "year": row["year"]},
                deep_link="/legal/marketplace-terms",
                urgent=True,  # a compliance notice must not be frequency-capped
            )
            logger.info(
                "[dac7] seller %s crossed for %s (%s sales, EUR %.0f) — notified",
                seller_id, row["year"], row["sales_count"], float(row["gross_eur"]),
            )
    except Exception as exc:
        logger.warning("[dac7] accrual failed for seller %s: %s", seller_id, exc)


def _verdict_from(stat: tuple[float, float, int], amount: float):
    """(avg, stddev, n) + an amount -> ('low'|'normal'|'high', note, n).

    Returns a NULL verdict rather than 'normal' when it cannot judge. The
    original guarded only on `stddev > 0`, which lets two data points produce a
    confident-looking answer — and a wrong "this price is suspicious" on a fair
    offer costs a sale. MIN_PRICE_SAMPLE is the fix.
    """
    avg, sd, n = stat
    if n < MIN_PRICE_SAMPLE or avg <= 0 or sd <= 0:
        return None, None, n
    delta = amount - avg
    if abs(delta) <= 2 * sd:
        return "normal", None, n
    direction = "above" if delta > 0 else "below"
    return (
        "high" if delta > 0 else "low",
        f"Well {direction} what this usually sells for "
        f"(~{avg:.0f} from {n} recent sales).",
        n,
    )


class TrackingIn(BaseModel):
    """Seller-supplied shipment reference.

    max_length values MUST match p2p_offers_tracking_len_check in
    server/migrations/20260807_p2p_offer_tracking.sql.
    """

    # Charset-constrained but NOT value-constrained: an unknown key degrades to
    # a copyable code with no link, which is a strictly better failure than a
    # 422 the seller cannot act on. The charset still rejects junk — without it
    # a whitespace-only carrier was accepted and rendered as a blank label.
    tracking_carrier: str = Field(..., max_length=40, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    # Consignment codes are alphanumeric with separators across every carrier we
    # list. Bounding the charset keeps the value safe to render as a link path
    # segment and stops the field being used as free text.
    # The upper bound is max_length ALONE. Encoding it in the quantifier too
    # would give two bounds that can disagree at the boundary — the shape of
    # learning_guard_must_match_constraint_type_space.
    tracking_code: str = Field(..., max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9 \-_/]{2,}$")

    @field_validator("tracking_carrier", "tracking_code", mode="before")
    @classmethod
    def _strip(cls, v):
        """Trim BEFORE the pattern runs.

        Carrier emails and tracking pages copy with surrounding whitespace, and
        a leading space made the pattern reject the value with "string does not
        match regex" — an unactionable 422 about an invisible character. A
        trailing space was silently accepted, so the two ends did not even fail
        the same way. Stripping first makes both ends behave identically.
        """
        return v.strip() if isinstance(v, str) else v


class OfferListResponse(BaseModel):
    offers: List[OfferOut]


class GradeCreate(BaseModel):
    verdict: str = Field(..., pattern=r"^(positive|negative)$")
    note: Optional[str] = Field(None, max_length=500)


class MemberReputation(BaseModel):
    user_id: str
    total_grades: int
    positive_grades: int
    # None until _MIN_GRADES_TO_SHOW is reached — see the constant.
    positive_pct: Optional[int] = None
    completed_trades: int = 0
    withdrawn_count: int = 0


def _row_opt(r, key: str):
    """A column that some of the offer queries do not select.

    asyncpg's Record raises KeyError on a missing key, and one of the four offer
    queries is an `INSERT ... RETURNING` that cannot join the listing at all. A
    mapper that reads such a column directly turns "this query selects less"
    into a 500 on whichever path was missed — and only on that path.
    """
    if hasattr(r, "get"):
        return r.get(key)
    try:
        return r[key]
    except (KeyError, IndexError):
        return None


def _row_opt_float(r, key: str) -> Optional[float]:
    v = _row_opt(r, key)
    return float(v) if v is not None else None


def _row_to_offer(r, me: str) -> OfferOut:
    is_buyer = str(r["buyer_id"]) == me
    both_confirmed = r["seller_confirmed_at"] is not None and r["buyer_confirmed_at"] is not None
    mine_confirmed = r["buyer_confirmed_at"] if is_buyer else r["seller_confirmed_at"]
    return OfferOut(
        id=str(r["id"]),
        listing_id=str(r["listing_id"]),
        listing_title=_row_opt(r, "listing_title"),
        # Absent from the create path's RETURNING (an INSERT cannot join the
        # listing), so this MUST tolerate a missing key — reading it directly
        # would be a 500 on the primary Stage 2 entry point, which is the trap
        # the tracking columns document at that RETURNING. create_offer sets it
        # from the listing row it already fetched.
        listing_price=_row_opt_float(r, "listing_price"),
        buyer_id=str(r["buyer_id"]),
        seller_id=str(r["seller_id"]),
        amount=float(r["amount"]),
        currency=r["currency"] or "EUR",
        status=r["status"],
        message=r["message"],
        counter_count=int(r["counter_count"] or 0),
        created_at=r["created_at"],
        seller_confirmed_at=r["seller_confirmed_at"],
        buyer_confirmed_at=r["buyer_confirmed_at"],
        tracking_carrier=r["tracking_carrier"],
        tracking_carrier_label=_carrier_label(r["tracking_carrier"]),
        tracking_code=r["tracking_code"],
        tracking_set_at=r["tracking_set_at"],
        tracking_url=_tracking_url(r["tracking_carrier"], r["tracking_code"]),
        i_am_buyer=is_buyer,
        # You may confirm once accepted and until you personally have.
        can_confirm=r["status"] in (_ACCEPTED, _SHIPPED) and mine_confirmed is None,
        # Grading unlocks ONLY on two-sided completion.
        can_grade=both_confirmed and r["status"] == _COMPLETED,
        already_graded=bool(r["already_graded"]) if "already_graded" in r.keys() else False,
        # Only the seller ships, and only while the trade is live. Editing is
        # allowed (a mistyped code is the common case), so this stays true after
        # tracking is already set.
        can_add_tracking=(not is_buyer) and r["status"] in (_ACCEPTED, _SHIPPED),
    )


@router.post("/offers", response_model=OfferOut, status_code=201,
             summary="Make an offer on a listing")
async def create_offer(
    payload: OfferCreate,
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(_offer_limit),
) -> OfferOut:
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code="DB_UNAVAILABLE")

    async with pool.acquire() as conn:
        listing = await conn.fetchrow(
            """
            SELECT id, user_id AS seller_id, listing_title, price,
                   status, delisted_at
            FROM public.marketplace_listings
            WHERE id = $1::uuid
            """,
            payload.listing_id,
        )
        if listing is None:
            raise error_response(404, "Listing not found", code="LISTING_NOT_FOUND")
        if str(listing["seller_id"]) == user_id:
            raise error_response(400, "You can't make an offer on your own listing",
                                 code="OWN_LISTING")
        if listing["status"] != "active" or listing["delisted_at"] is not None:
            raise error_response(409, "This listing is no longer available",
                                 code="LISTING_INACTIVE")

        # Blocking has to cover the offer path, not just chat and browse.
        # Without this a blocked member still reaches the person who blocked
        # them — an offer creates a notification and a row on their Offers
        # screen, which is precisely the contact blocking is meant to stop.
        # Symmetric, so it also stops YOU from offering on someone you blocked.
        await raise_if_blocked(conn, user_id, str(listing["seller_id"]),
                               "You can't make an offer on this listing")

        # One live offer per buyer per listing. Without this a buyer can spam
        # a seller with a ladder of offers and the seller cannot tell which is
        # current.
        existing = await conn.fetchval(
            """
            SELECT 1 FROM public.p2p_offers
            WHERE listing_id = $1::uuid AND buyer_id = $2::uuid
              AND status IN ($3, $4, $5)
            LIMIT 1
            """,
            payload.listing_id, user_id, _PENDING, _COUNTERED, _ACCEPTED,
        )
        if existing:
            raise error_response(409, "You already have an open offer on this listing",
                                 code="OFFER_EXISTS")

        row = await conn.fetchrow(
            """
            INSERT INTO public.p2p_offers
                (listing_id, buyer_id, seller_id, amount, currency, status,
                 message, counter_count, created_at, updated_at)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, 0, now(), now())
            RETURNING id, listing_id, buyer_id, seller_id, amount, currency,
                      status, message, counter_count, created_at,
                      seller_confirmed_at, buyer_confirmed_at,
                      -- Always NULL on a fresh offer, but _row_to_offer reads
                      -- them unconditionally and a missing key is a KeyError,
                      -- i.e. a 500 on the primary Stage 2 entry point. RETURNING
                      -- cannot use _OFFER_COLUMNS because that list is alias-
                      -- qualified (`o.`), so this is the one place the column
                      -- set is repeated — pinned by
                      -- test_create_offer_returning_carries_tracking.
                      tracking_carrier, tracking_code, tracking_set_at
            """,
            payload.listing_id, user_id, str(listing["seller_id"]),
            payload.amount, payload.currency, _PENDING, payload.message,
        )

    out = _row_to_offer(row, user_id)
    # Both come from the listing row above, because the RETURNING cannot join it.
    out.listing_title = listing["listing_title"]
    out.listing_price = float(listing["price"]) if listing["price"] is not None else None

    # The seller has to LEARN an offer arrived. Deliberately no buyer name: a
    # member's display name may be private (user_privacy_settings.allow_discovery),
    # and the amount plus the listing is what the seller needs to decide.
    async with pool.acquire() as nconn:
        await _notify_trade(
            nconn, str(listing["seller_id"]),
            "New offer on your listing",
            f"{out.currency} {out.amount:.2f} for \"{listing['listing_title'] or 'your item'}\". "
            "Open bids to accept, counter or decline.",
            out.id,
        )
    return out


@router.get("/offers", response_model=OfferListResponse,
            summary="Offers I've made or received")
async def list_offers(
    role: str = Query("all", pattern=r"^(all|buying|selling)$"),
    user_id: str = Depends(get_current_user_id),
    pagination: tuple[int, int] = Depends(pagination_params),
) -> OfferListResponse:
    limit, offset = pagination
    pool = get_db_pool()
    if pool is None:
        return OfferListResponse(offers=[])

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT {_OFFER_COLUMNS},
                   l.canonical_key, l.category,
                   EXISTS (
                       SELECT 1 FROM public.member_grades g
                       WHERE g.offer_id = o.id AND g.rater_id = $1::uuid
                   ) AS already_graded
            FROM public.p2p_offers o
            LEFT JOIN public.marketplace_listings l ON l.id = o.listing_id
            WHERE (o.buyer_id = $1::uuid OR o.seller_id = $1::uuid)
              AND ($2 = 'all'
                   OR ($2 = 'buying'  AND o.buyer_id  = $1::uuid)
                   OR ($2 = 'selling' AND o.seller_id = $1::uuid))
            ORDER BY o.created_at DESC
            LIMIT $3 OFFSET $4
            """,
            user_id, role, limit, offset,
        )
    offers = [_row_to_offer(r, user_id) for r in rows]

    # Price sanity, one distribution fetch per DISTINCT item rather than per
    # offer. A user's offers list is usually several offers across a few items,
    # so N+1 here would be mostly the same query repeated — and this runs on
    # every open of the offers screen.
    refs = {
        f"{r['category']}:{r['canonical_key']}"
        for r in rows if r["canonical_key"] and r["category"]
    }
    if refs:
        async with pool.acquire() as conn:
            dist = {
                d["item_ref"]: (float(d["avg_price"]), float(d["sd"] or 0), int(d["n"]))
                for d in await conn.fetch(
                    """
                    SELECT item_ref, avg(price_eur) AS avg_price,
                           stddev_pop(price_eur) AS sd, count(*) AS n
                    FROM public.market_hits
                    WHERE item_ref = ANY($1::text[])
                      AND price_eur IS NOT NULL
                      AND is_listing IS NOT TRUE
                      AND seen_at > now() - interval '180 days'
                    GROUP BY item_ref
                    """,
                    list(refs),
                )
            }
        for off, r in zip(offers, rows):
            if not (r["canonical_key"] and r["category"]):
                continue
            stat = dist.get(f"{r['category']}:{r['canonical_key']}")
            if not stat:
                off.price_sample_size = 0
                continue
            off.price_verdict, off.price_note, off.price_sample_size = _verdict_from(
                stat, float(off.amount)
            )

    return OfferListResponse(offers=offers)


@router.post("/offers/{offer_id}/respond", response_model=OfferOut,
             summary="Accept, decline, counter or withdraw an offer")
async def respond_to_offer(
    offer_id: str,
    action: str = Query(..., pattern=r"^(accept|decline|counter|withdraw)$"),
    amount: Optional[float] = Query(None, gt=0, le=1_000_000),
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(_offer_limit),
) -> OfferOut:
    """One endpoint for every response so the state machine lives in one place.

    `accept` marks the listing reserved but does NOT take it off the market —
    see the module docstring. `withdraw` is available to either side after an
    accept and records who walked; that record is the only sanction available
    without a payment rail.
    """
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code="DB_UNAVAILABLE")

    async with pool.acquire() as conn:
        o = await conn.fetchrow(
            """
            SELECT o.*, l.listing_title
            FROM public.p2p_offers o
            LEFT JOIN public.marketplace_listings l ON l.id = o.listing_id
            WHERE o.id = $1::uuid
            """,
            offer_id,
        )
        if o is None:
            raise error_response(404, "Offer not found", code="OFFER_NOT_FOUND")

        is_seller = str(o["seller_id"]) == user_id
        is_buyer = str(o["buyer_id"]) == user_id
        if not (is_seller or is_buyer):
            raise error_response(403, "Not your offer", code="NOT_YOUR_OFFER")

        status = o["status"]

        if action in ("accept", "decline", "counter"):
            # Only the seller decides on a live offer. A buyer countering
            # their own offer is just a new offer.
            if not is_seller:
                raise error_response(403, "Only the seller can respond to an offer",
                                     code="SELLER_ONLY")
            if status not in (_PENDING, _COUNTERED):
                raise error_response(409, f"Offer is already {status}",
                                     code="OFFER_NOT_OPEN")

        if action == "counter" and amount is None:
            raise error_response(400, "A counter needs an amount", code="AMOUNT_REQUIRED")

        if action == "accept":
            new_status = _ACCEPTED
            await conn.execute(
                """
                UPDATE public.p2p_offers
                   SET status = $2, updated_at = now()
                 WHERE id = $1::uuid
                """,
                offer_id, new_status,
            )
            # Soft reserve: a marker, not a delist. Browse still shows it.
            await conn.execute(
                """
                UPDATE public.marketplace_listings
                   SET reserved_offer_id = $2::uuid, reserved_at = now(),
                       updated_at = now()
                 WHERE id = $1::uuid
                """,
                str(o["listing_id"]), offer_id,
            )
        elif action == "decline":
            new_status = _DECLINED
            await conn.execute(
                "UPDATE public.p2p_offers SET status = $2, updated_at = now() WHERE id = $1::uuid",
                offer_id, new_status,
            )
        elif action == "counter":
            new_status = _COUNTERED
            await conn.execute(
                """
                UPDATE public.p2p_offers
                   SET status = $2, amount = $3,
                       counter_count = counter_count + 1, updated_at = now()
                 WHERE id = $1::uuid
                """,
                offer_id, new_status, amount,
            )
        else:  # withdraw
            if status not in (_ACCEPTED, _SHIPPED):
                raise error_response(409, "Nothing to withdraw from",
                                     code="NOT_WITHDRAWABLE")
            # 'withdrawn' is NOT a legal status (p2p_offers_status_check). Record the
            # walk-away in withdrawn_by and set the legal 'cancelled'.
            new_status = _CANCELLED
            await conn.execute(
                """
                UPDATE public.p2p_offers
                   SET status = $2, withdrawn_by = $3::uuid,
                       withdrawn_at = now(), updated_at = now()
                 WHERE id = $1::uuid
                """,
                offer_id, new_status, user_id,
            )
            await conn.execute(
                """
                UPDATE public.marketplace_listings
                   SET reserved_offer_id = NULL, reserved_at = NULL, updated_at = now()
                 WHERE id = $1::uuid AND reserved_offer_id = $2::uuid
                """,
                str(o["listing_id"]), offer_id,
            )

        fresh = await conn.fetchrow(
            f"""
            SELECT {_OFFER_COLUMNS}
            FROM public.p2p_offers o
            LEFT JOIN public.marketplace_listings l ON l.id = o.listing_id
            WHERE o.id = $1::uuid
            """,
            offer_id,
        )

        # Tell the OTHER party. Every branch notifies, including decline: a buyer
        # left waiting on silence assumes the app is broken, and "declined" is
        # information they can act on (offer elsewhere, or higher).
        title_ = fresh["listing_title"] or "your item"
        amt = f"{fresh['currency']} {float(fresh['amount']):.2f}"
        if action == "accept":
            other, subject, body = str(o["buyer_id"]), "Your offer was accepted", (
                f"The seller accepted {amt} for \"{title_}\". Arrange the exchange in Open bids."
            )
        elif action == "decline":
            other, subject, body = str(o["buyer_id"]), "Your offer was declined", (
                f"Your {amt} offer on \"{title_}\" was declined. You can make another one."
            )
        elif action == "counter":
            other, subject, body = str(o["buyer_id"]), "You got a counter-offer", (
                f"The seller countered with {amt} for \"{title_}\"."
            )
        else:  # withdraw — whoever did NOT walk away needs to know
            walker_is_buyer = user_id == str(o["buyer_id"])
            other = str(o["seller_id"]) if walker_is_buyer else str(o["buyer_id"])
            subject = "A trade was called off"
            body = (
                f"The {'buyer' if walker_is_buyer else 'seller'} withdrew from the "
                f"{amt} trade on \"{title_}\"."
            )
        await _notify_trade(conn, other, subject, body, offer_id)

    return _row_to_offer(fresh, user_id)


class CarrierOut(BaseModel):
    key: str
    label: str
    # False => we cannot build a working link from the code alone, so the client
    # must render a copyable code instead of a button. Sent rather than inferred
    # so the client never has to know WHY (postcode, no public URL, …).
    linkable: bool


class Dac7YearOut(BaseModel):
    year: int
    sales_count: int
    gross_eur: float
    # True by the SAME predicate the accrual uses, RECOMPUTED from the counters
    # rather than read off `reportable_at`. The stamp records when we noticed;
    # this records whether it is true now. They differ between the counter update
    # and the notify stamp, and reading only the stamp would report a seller as
    # excluded while they are already over.
    #
    # A `#` comment, not a bare string: a string literal here is a no-op
    # expression that LOOKS like a field docstring, and pydantic never sees it.
    reportable: bool
    reportable_at: Optional[datetime] = None
    notified_at: Optional[datetime] = None
    details_provided_at: Optional[datetime] = None
    # Headroom. Null once reportable — "0 sales remaining" invites the reading
    # that one more crosses it, when it has already been crossed.
    sales_remaining: Optional[int] = None
    gross_eur_remaining: Optional[float] = None


class Dac7StatusOut(BaseModel):
    """The thresholds are returned with the data on purpose: a client that
    hardcodes 30/2000 goes stale the moment the rule changes, and this is a
    figure we tell members in writing (marketplace-terms §6)."""
    sales_limit: int
    gross_eur_limit: float
    currency: str = "EUR"
    current_year: Optional[Dac7YearOut] = None
    years: List[Dac7YearOut] = []


def _dac7_year_out(r) -> Dac7YearOut:
    sales = int(r["sales_count"] or 0)
    gross = float(r["gross_eur"] or 0.0)
    reportable = dac7_reportable(sales, gross)
    return Dac7YearOut(
        year=int(r["year"]),
        sales_count=sales,
        gross_eur=round(gross, 2),
        reportable=reportable,
        reportable_at=r["reportable_at"],
        notified_at=r["notified_at"],
        details_provided_at=r["details_provided_at"],
        sales_remaining=None if reportable else max(0, DAC7_SALES_LIMIT - sales),
        gross_eur_remaining=(
            None if reportable else round(max(0.0, DAC7_GROSS_EUR_LIMIT - gross), 2)
        ),
    )


@router.get("/dac7/me", response_model=Dac7StatusOut,
            summary="Your own DAC7 sales counters and reportable status")
async def dac7_status(
    user_id: str = Depends(get_current_user_id),
) -> Dac7StatusOut:
    """What we have counted about YOUR sales, and whether it crosses the line.

    `app/legal/marketplace-terms.tsx` §6 tells members we count their sales
    automatically and will warn them before they are reported. `_dac7_accrue`
    made that true, but there was no way for a member — or the founder — to SEE
    the counter: the only output was a one-time notification. A promise you
    cannot inspect is one you cannot verify you are keeping.

    Own rows only. There is deliberately no "all sellers" variant on this
    router: that is an ops question about other people's tax exposure, and it
    does not belong on an endpoint any authenticated member can call.

    The year comes from `EXTRACT(YEAR FROM now())` — the SAME derivation the
    accrual uses — not from Python's clock. The two disagree for the hours
    around New Year when the server's timezone (Europe/Paris) and UTC are on
    different sides of midnight, which would show a seller a freshly empty year
    while their sales were still landing in the previous one.
    """
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code="DB_UNAVAILABLE")

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT year, sales_count, gross_eur, reportable_at, notified_at,
                   details_provided_at
            FROM public.dac7_seller_year
            WHERE user_id = $1::uuid
            ORDER BY year DESC
            """,
            user_id,
        )
        this_year = await conn.fetchval("SELECT EXTRACT(YEAR FROM now())::int")

    years = [_dac7_year_out(r) for r in rows]
    # None, not a fabricated zero row: "no completed sales recorded this year" is
    # a different statement from "0 sales counted", and only the first is true
    # before anything has completed.
    current = next((y for y in years if y.year == this_year), None)

    return Dac7StatusOut(
        sales_limit=DAC7_SALES_LIMIT,
        gross_eur_limit=DAC7_GROSS_EUR_LIMIT,
        current_year=current,
        years=years,
    )


@router.get("/carriers", response_model=List[CarrierOut],
            summary="Carriers the seller can pick when attaching tracking")
async def list_carriers() -> List[CarrierOut]:
    """Served from `_CARRIER_TRACKING` so the picker cannot drift from the URL
    table. A hardcoded client list would let a seller choose a carrier the
    server does not know, which silently degrades to a code with no link."""
    return [
        CarrierOut(key=k, label=label, linkable=url is not None)
        for k, (label, url) in _CARRIER_TRACKING.items()
    ]


@router.post("/offers/{offer_id}/tracking", response_model=OfferOut,
             summary="Attach a shipment reference to an offer (seller only)")
async def set_tracking(
    offer_id: str,
    payload: TrackingIn,
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(_offer_limit),
) -> OfferOut:
    """Record carrier + consignment code so the buyer can follow the parcel.

    **Display-only, deliberately.** This endpoint writes nothing but the three
    tracking columns: it does not touch `status`, `seller_confirmed_at` or
    `buyer_confirmed_at`, and nothing anywhere may poll the carrier and derive
    completion from delivery. Doing so would substitute our judgment for the
    buyer's, and we would own the outcome when the box arrives empty — the same
    class as labelling a listing "authenticated by Sparrow". See §5b of
    docs/P2P_MARKETPLACE_SPEC.md.

    Separate from /confirm on purpose: a mistyped code is the common case and
    must be fixable without re-running the completion state machine, and if one
    of the two calls fails the seller can retry just that one.
    """
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code="DB_UNAVAILABLE")

    async with pool.acquire() as conn:
        o = await conn.fetchrow(
            "SELECT seller_id, buyer_id, status FROM public.p2p_offers WHERE id = $1::uuid",
            offer_id,
        )
        if o is None:
            raise error_response(404, "Offer not found", code="OFFER_NOT_FOUND")
        # Only the seller ships. Checked here rather than trusted from the
        # client — can_add_tracking is a UI hint, not the enforcement.
        if str(o["seller_id"]) != user_id:
            raise error_response(403, "Only the seller can add tracking",
                                 code="NOT_THE_SELLER")
        if o["status"] not in (_ACCEPTED, _SHIPPED):
            raise error_response(409, "This offer isn't in an exchangeable state",
                                 code="NOT_EXCHANGEABLE")

        await conn.execute(
            """
            UPDATE public.p2p_offers
               SET tracking_carrier = $2,
                   tracking_code    = $3,
                   tracking_set_at  = now(),
                   updated_at       = now()
             WHERE id = $1::uuid
            """,
            # Already stripped by TrackingIn._strip — a second .strip() here
            # would imply the model does not, and invite someone to remove it
            # from the model.
            offer_id, payload.tracking_carrier, payload.tracking_code,
        )

        fresh = await conn.fetchrow(
            f"""
            SELECT {_OFFER_COLUMNS}
            FROM public.p2p_offers o
            LEFT JOIN public.marketplace_listings l ON l.id = o.listing_id
            WHERE o.id = $1::uuid
            """,
            offer_id,
        )
    return _row_to_offer(fresh, user_id)


@router.post("/offers/{offer_id}/confirm", response_model=OfferOut,
             summary="Confirm your side of the exchange")
async def confirm_exchange(
    offer_id: str,
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(_offer_limit),
) -> OfferOut:
    """Seller marks sent; buyer marks received. Both => completed.

    Two-sided by design: this is what grading is anchored to, and a one-sided
    completion would let a single actor with two accounts manufacture trades.
    """
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code="DB_UNAVAILABLE")

    async with pool.acquire() as conn:
        o = await conn.fetchrow("SELECT * FROM public.p2p_offers WHERE id = $1::uuid", offer_id)
        if o is None:
            raise error_response(404, "Offer not found", code="OFFER_NOT_FOUND")

        is_seller = str(o["seller_id"]) == user_id
        is_buyer = str(o["buyer_id"]) == user_id
        if not (is_seller or is_buyer):
            raise error_response(403, "Not your offer", code="NOT_YOUR_OFFER")
        if o["status"] not in (_ACCEPTED, _SHIPPED):
            raise error_response(409, "This offer isn't in an exchangeable state",
                                 code="NOT_EXCHANGEABLE")

        col = "seller_confirmed_at" if is_seller else "buyer_confirmed_at"
        if o[col] is not None:
            raise error_response(409, "You've already confirmed", code="ALREADY_CONFIRMED")

        # Column name is from a fixed 2-value branch above, never user input.
        await conn.execute(
            f"UPDATE public.p2p_offers SET {col} = now(), updated_at = now() "
            f"WHERE id = $1::uuid",
            offer_id,
        )

        fresh = await conn.fetchrow(
            f"""
            SELECT {_OFFER_COLUMNS}
            FROM public.p2p_offers o
            LEFT JOIN public.marketplace_listings l ON l.id = o.listing_id
            WHERE o.id = $1::uuid
            """,
            offer_id,
        )
        both = fresh["seller_confirmed_at"] and fresh["buyer_confirmed_at"]
        if both and fresh["status"] != _COMPLETED:
            await conn.execute(
                "UPDATE public.p2p_offers SET status = $2, updated_at = now() WHERE id = $1::uuid",
                offer_id, _COMPLETED,
            )
            # The listing is genuinely gone now — mark it sold and let the
            # Stage 1 stale-hook remove the buyable market_hits row, otherwise
            # a Target Hit would still point at a completed trade.
            await conn.execute(
                """
                UPDATE public.marketplace_listings
                   SET status = 'sold', delisted_at = now(), updated_at = now()
                 WHERE id = $1::uuid AND delisted_at IS NULL
                """,
                str(fresh["listing_id"]),
            )
            from app.features.p2p_listing_router import (
                _sold_comp_hook, _stale_supply_hook, _ground_truth_hook,
            )
            await _stale_supply_hook(str(fresh["listing_id"]))
            # The closed loop: the trade just completed at a KNOWN, two-sided
            # confirmed price, which is exactly the sold-comp data
            # valuation_worker consumes and cannot get for ~62k catalogue items.
            # Awaited, not fire-and-forget — a lost buyable row is a non-event
            # (the listing is gone anyway), but a lost sale is data we can never
            # reconstruct. `amount` is the AGREED figure after any counter, not
            # the asking price.
            await _sold_comp_hook(
                str(fresh["listing_id"]),
                float(fresh["amount"]),
                fresh["currency"] or "EUR",
            )
            # Same price, different consumer: the sold comp above feeds
            # VALUATION, this feeds model CALIBRATION (prediction vs reality).
            # Rescued from Deal Desk's execute_complete, which was the only
            # thing wiring completion to price_ground_truths.
            await _ground_truth_hook(
                str(fresh["listing_id"]),
                float(fresh["amount"]),
                fresh["currency"] or "EUR",
            )
            # DAC7: this seller's counters just changed. Must run on the
            # completion path — it is the only moment consideration becomes
            # known, and the terms promise notice BEFORE we report anyone.
            await _dac7_accrue(
                str(fresh["seller_id"]),
                float(fresh["amount"]),
                fresh["currency"] or "EUR",
            )
            fresh = dict(fresh)
            fresh["status"] = _COMPLETED

            # Move the OBJECT, release the reservation, and close out the other
            # buyers. Before the notifications below, so a completed trade never
            # announces itself while the item is still in the seller's collection.
            await _settle_completed_trade(
                conn, offer_id, str(fresh["listing_id"]),
                str(fresh["buyer_id"]), str(fresh["seller_id"]),
                float(fresh["amount"]), fresh["currency"] or "EUR",
            )

            # BOTH sides, because completion unlocks grading for both and each
            # needs to know the other confirmed.
            title_ = fresh["listing_title"] or "your item"
            for party in (str(fresh["buyer_id"]), str(fresh["seller_id"])):
                await _notify_trade(
                    conn, party, "Trade completed",
                    f"You both confirmed the exchange of \"{title_}\". "
                    "You can now grade each other in Open bids.",
                    offer_id,
                )
        elif not both:
            # ONE side has confirmed. The other must be told, or the trade stalls
            # on a step nobody knows is waiting for them — the most common way a
            # two-sided flow dies.
            #
            # `elif not both` rather than a bare `else`: the guarded condition is
            # `both and status != completed`, so a plain else would ALSO catch
            # "both confirmed and already completed" and tell someone their
            # counterparty just confirmed when nothing changed. Double-confirm is
            # rejected upstream with ALREADY_CONFIRMED so that state is currently
            # unreachable, but the notification should not depend on that.
            i_am_buyer = user_id == str(fresh["buyer_id"])
            other = str(fresh["seller_id"]) if i_am_buyer else str(fresh["buyer_id"])
            await _notify_trade(
                conn, other,
                "The other party confirmed",
                f"The {'buyer' if i_am_buyer else 'seller'} confirmed the exchange of "
                f"\"{fresh['listing_title'] or 'your item'}\". Confirm your side to "
                "complete the trade.",
                offer_id,
            )

    return _row_to_offer(fresh, user_id)


@router.post("/offers/{offer_id}/grade", status_code=201,
             summary="Grade the other party after a completed trade")
async def grade_counterparty(
    offer_id: str,
    payload: GradeCreate,
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(_grade_limit),
) -> dict:
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code="DB_UNAVAILABLE")

    async with pool.acquire() as conn:
        o = await conn.fetchrow("SELECT * FROM public.p2p_offers WHERE id = $1::uuid", offer_id)
        if o is None:
            raise error_response(404, "Offer not found", code="OFFER_NOT_FOUND")

        is_seller = str(o["seller_id"]) == user_id
        is_buyer = str(o["buyer_id"]) == user_id
        if not (is_seller or is_buyer):
            raise error_response(403, "Not your trade", code="NOT_YOUR_OFFER")

        # THE anchor. Enforced here and again by member_grades.offer_id being
        # NOT NULL — an unanchored grade is the farmable rating this design
        # exists to prevent.
        if o["status"] != _COMPLETED:
            raise error_response(
                409,
                "You can grade once both sides have confirmed the exchange",
                code="TRADE_NOT_COMPLETE",
            )

        ratee = str(o["buyer_id"]) if is_seller else str(o["seller_id"])
        inserted = await conn.fetchval(
            """
            INSERT INTO public.member_grades
                (offer_id, rater_id, ratee_id, verdict, note)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5)
            ON CONFLICT (offer_id, rater_id) DO UPDATE
                SET verdict = EXCLUDED.verdict, note = EXCLUDED.note
            RETURNING id
            """,
            offer_id, user_id, ratee, payload.verdict, payload.note,
        )
    return {"ok": True, "grade_id": str(inserted)}


@router.get("/members/{member_id}/reputation", response_model=MemberReputation,
            summary="A member's trade reputation")
async def member_reputation(
    member_id: str,
    _user_id: str = Depends(get_current_user_id),
) -> MemberReputation:
    """Reputation, deliberately conservative.

    `positive_pct` is None below _MIN_GRADES_TO_SHOW. Showing "0% positive"
    off a single grade is not information, it is a smear; showing "100%" off
    one is not credibility either.
    """
    pool = get_db_pool()
    if pool is None:
        return MemberReputation(user_id=member_id, total_grades=0, positive_grades=0)

    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            """
            SELECT
              (SELECT count(*) FROM public.member_grades WHERE ratee_id = $1::uuid) AS total,
              (SELECT count(*) FROM public.member_grades
                WHERE ratee_id = $1::uuid AND verdict = 'positive') AS positive,
              (SELECT count(*) FROM public.p2p_offers
                WHERE status = 'completed'
                  AND (buyer_id = $1::uuid OR seller_id = $1::uuid)) AS trades,
              (SELECT count(*) FROM public.p2p_offers
                WHERE withdrawn_by = $1::uuid) AS withdrawn
            """,
            member_id,
        )

    total = int(r["total"] or 0)
    positive = int(r["positive"] or 0)
    return MemberReputation(
        user_id=member_id,
        total_grades=total,
        positive_grades=positive,
        positive_pct=round(positive * 100 / total) if total >= _MIN_GRADES_TO_SHOW else None,
        completed_trades=int(r["trades"] or 0),
        withdrawn_count=int(r["withdrawn"] or 0),
    )
