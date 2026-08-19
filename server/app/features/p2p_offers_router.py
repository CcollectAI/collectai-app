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
from app.lib.payment_rails import (
    DISCLAIMER as PAYMENT_DISCLAIMER,
    REGIONS,
    PaymentRail,
    build_deep_link,
    carries_amount,
    clean_handle,
    rails_for_region,
)
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


def who_may_respond(action: str, status: str) -> str:
    """Which side may take `action` on an offer in `status` — "buyer" or "seller".

    ONE RULE: whoever did not set the current number is the one who answers it.

    A `counter` overwrites `p2p_offers.amount` with the seller's figure, so a
    `countered` offer is the SELLER's offer sitting in front of the BUYER, and
    the buyer is the one who accepts or declines it. A `pending` offer is the
    buyer's, so the seller answers that one.

    `counter` is seller-only in both states: a buyer raising their own bid is
    just a new offer, and letting both sides write `amount` makes "whose number
    is this?" unanswerable.

    Extracted 2026-08-15. All three actions used to be unconditionally
    seller-only, which left a buyer facing a counter with no accept and no
    decline — while the app's own `offerNeedsMyAction` stamped YOUR MOVE on
    exactly that card. Caller checks membership; this decides the side.
    """
    if action == "counter":
        return "seller"
    return "buyer" if status == _COUNTERED else "seller"

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
            o.created_at,
            -- LAST ACTIVITY, added 2026-08-19. The card showed `created_at` as
            -- the offer's age, so a haggle opened three weeks ago and countered
            -- yesterday read "3 weeks ago" — exactly backwards for judging
            -- whether a bid has gone stale, which is the judgement that line
            -- exists to support. Every respond/confirm/tracking write already
            -- touches `updated_at`; nothing was reading it.
            o.updated_at,
            o.seller_confirmed_at, o.buyer_confirmed_at,
            o.withdrawn_by,
            o.tracking_carrier, o.tracking_code, o.tracking_set_at,
            l.listing_title,
            -- The ASKING price, so a counter can be expressed as a percentage of
            -- it. Without this the counter UI could only work off the buyer's own
            -- offer, where "-5%" means "less than they already offered" — a
            -- button no seller would ever press. The client must not guess a
            -- reference price it does not hold.
            l.price AS listing_price,
            -- WHICH offer this listing is reserved for, if any (2026-08-19).
            -- §1d is explicit that accept is an AGREEMENT, NOT A LOCK: the
            -- listing stays live and browsable, and the rival offers stay
            -- `pending` on purpose, because with no payment rail a hard reserve
            -- is unenforceable and killing the fallback bids would leave a
            -- seller with nothing if the accepted buyer ghosts.
            --
            -- The cost was borne on the seller's screen. `offerNeedsMyAction`
            -- returns true for any pending offer you received, so every rival
            -- bid kept stamping YOUR MOVE for an object already promised to
            -- somebody — and `_settle_completed_trade` only closes them at
            -- COMPLETION, which can be a week of shipping later. The bids must
            -- stay actionable (that is the whole point) and stop being urgent.
            -- The client cannot infer this: it never saw the reservation.
            l.reserved_offer_id,
            -- The listing photo. Every row on app/offers.tsx was text, which is
            -- what made a screen of negotiations read as a spreadsheet — a
            -- thumbnail is the single change that makes a stacked list
            -- scannable.
            --
            -- Sourced from `item_images`, NOT from `marketplace_listings`. This
            -- read `l.image_url` from 2026-08-15 (commit e6f5f32) until the
            -- same day: that column has never existed on that table, and no
            -- migration ever added it. The router simply had not been deployed,
            -- so the query was never executed until it was — and then every
            -- /p2p/offers call 500'd with UndefinedColumnError. A committed
            -- query against a column that does not exist is undeployable code
            -- sitting in main, which only a live call can catch.
            --
            -- A correlated subquery rather than a JOIN because _OFFER_COLUMNS
            -- is shared by five queries and each would otherwise need the same
            -- join added by hand — one of them would eventually be missed.
            (SELECT ii.image_url
               FROM public.item_images ii
              WHERE ii.item_id = l.item_id
              ORDER BY ii.position NULLS LAST, ii.created_at
              LIMIT 1) AS listing_image_url,
            -- Recipient postcode + country, for the carriers whose tracking URL
            -- needs them (PostNL). NULL until the buyer supplies an address, and
            -- `_tracking_url` then returns None rather than a half-built link,
            -- which is the same copyable-code fallback as before addresses
            -- existed. Every query using this list joins p2p_offer_addresses —
            -- verified, all four — so adding it here cannot orphan a caller.
            a.postcode AS delivery_postcode,
            a.country AS delivery_country
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
    # PostNL's public page takes barcode-COUNTRY-POSTCODE. It was `None` for as
    # long as we held no address; `_tracking_url` now passes one when the buyer
    # has supplied it, and still falls back to a copyable code when they have
    # not. DPD stays None: its consumer URL also wants a postcode but the format
    # is not documented well enough to guess, and a guessed link 404s at the
    # worst possible moment.
    "postnl":      ("PostNL", "https://jouw.postnl.nl/track-and-trace/{code}-{country}-{postcode}"),
    "dpd":         ("DPD", None),             # needs recipient postcode
    "gls":         ("GLS", None),             # no stable code-only public URL
    "bpost":       ("bpost", None),
    "dhl":         ("DHL", "https://www.dhl.com/en/express/tracking.html?AWB={code}"),
    "dhl_de":      ("DHL Paket", "https://nolp.dhl.de/nextt-online-public/en/search?piececode={code}"),
    "ups":         ("UPS", "https://www.ups.com/track?tracknum={code}"),
    "fedex":       ("FedEx", "https://www.fedex.com/fedextrack/?trknbr={code}"),
    "other":       ("Other carrier", None),
    # Added 2026-08-14 with the regional handoff. Tracking URLs are the
    # carrier's OWN public pages; keys are new, so no stored
    # `p2p_offers.tracking_carrier` value changes meaning.
    "royal_mail":  ("Royal Mail", "https://www.royalmail.com/track-your-item#/tracking-results/{code}"),
    "colissimo":   ("Colissimo", "https://www.laposte.fr/outils/suivre-vos-envois?code={code}"),
    "usps":        ("USPS", "https://tools.usps.com/go/TrackConfirmAction?tLabels={code}"),
    "canada_post": ("Canada Post", "https://www.canadapost-postescanada.ca/track-reperage/en#/search?searchFor={code}"),
    "auspost":     ("Australia Post", "https://auspost.com.au/mypost/track/#/details/{code}"),
    "japan_post":  ("Japan Post", "https://trackings.post.japanpost.jp/services/srv/search/direct?reqCodeNo1={code}&searchKind=S002&locale=en"),
    "cj_logistics": ("CJ Logistics", None),   # no stable code-only public URL
}

# Where the SELLER books the shipment, and which regions each carrier serves.
#
# The booking link opens the CARRIER's own flow. The seller buys carriage in
# their own name, from their own account, and pays the carrier directly — which
# is the whole compliance point. Spec §5a: generating labels under a Sparrow
# carrier account "makes us the contracting party for carriage", and arranging
# insurance would be insurance distribution under IDD. A hyperlink is neither.
#
# Regions mirror `Region` in src/lib/settings.tsx. A carrier may appear in more
# than one; `other` gets the global integrators only.
_CARRIER_BOOKING: dict[str, tuple[Optional[str], tuple[str, ...]]] = {
    "postnl":       ("https://www.postnl.nl/en/send-a-parcel/", ("europe",)),
    "dpd":          ("https://www.dpd.com/", ("europe",)),
    "gls":          ("https://gls-group.com/", ("europe",)),
    "bpost":        ("https://www.bpost.be/en/send-parcel", ("europe",)),
    "royal_mail":   ("https://www.royalmail.com/sending", ("europe",)),
    "colissimo":    ("https://www.laposte.fr/envoi-colis", ("europe",)),
    "dhl_de":       ("https://www.dhl.de/en/privatkunden/pakete-versenden.html", ("europe",)),
    "dhl":          ("https://www.dhl.com/", ("europe", "americas", "japan", "korea", "oceania", "other")),
    "ups":          ("https://www.ups.com/ship", ("europe", "americas", "japan", "korea", "oceania", "other")),
    "fedex":        ("https://www.fedex.com/en-us/shipping.html", ("europe", "americas", "japan", "korea", "oceania", "other")),
    "usps":         ("https://www.usps.com/ship/", ("americas",)),
    "canada_post":  ("https://www.canadapost-postescanada.ca/cpc/en/personal/sending/", ("americas",)),
    "auspost":      ("https://auspost.com.au/sending", ("oceania",)),
    "japan_post":   ("https://www.post.japanpost.jp/int/index_en.html", ("japan",)),
    "cj_logistics": ("https://www.cjlogistics.com/en/main", ("korea",)),
    "other":        (None, ("europe", "americas", "japan", "korea", "oceania", "other")),
}


def _tracking_url(
    carrier: Optional[str],
    code: Optional[str],
    *,
    postcode: Optional[str] = None,
    country: Optional[str] = None,
) -> Optional[str]:
    """The carrier's own tracking page, or None when we cannot build a real one.

    Some carriers need the RECIPIENT's postcode in the URL. Those templates
    carry `{postcode}`/`{country}` and are only usable once the buyer has given
    a delivery address for this trade — before that we return None, and the
    client renders a copyable code with "search this on the carrier's site",
    exactly as it did when we held no addresses at all.

    Returning a half-built URL would be the worse failure: it looks tappable and
    lands on a 404, which reads as "Sparrow lost my parcel".
    """
    if not carrier or not code:
        return None
    entry = _CARRIER_TRACKING.get(carrier)
    if entry is None or entry[1] is None:
        return None
    template = entry[1]
    needs_postcode = "{postcode}" in template
    if needs_postcode and not (postcode and country):
        return None
    return template.format(
        code=quote(code, safe=""),
        postcode=quote((postcode or "").replace(" ", ""), safe=""),
        country=quote((country or "").upper(), safe=""),
    )


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
    listing_image_url: Optional[str] = None
    buyer_id: str
    seller_id: str
    amount: float
    currency: str
    status: str
    message: Optional[str] = None
    counter_count: int = 0
    created_at: Optional[datetime] = None
    #: Last activity — a counter, a confirmation, a tracking code. The card
    #: judges staleness on this; `created_at` answers "when did this start",
    #: which is a different question and was being used for both.
    updated_at: Optional[datetime] = None
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
    # Who walked away, reduced to the only question the reader has.
    # `withdraw` is available to EITHER side (a seller may retract a
    # counter), so a client that only knows `status='cancelled'` cannot
    # say who did it — and app/offers.tsx briefly claimed the buyer always
    # had. The row has carried `withdrawn_by` since Stage 2; nothing
    # returned it.
    # Optional[bool], NOT bool. `None` = nobody is recorded as having
    # walked (withdrawn_by IS NULL, e.g. a row cancelled before that
    # column was written). Sending False there would let the client say
    # "the other side withdrew" on the strength of a missing value —
    # learning_empty_answer_rendered_as_zero, in boolean form.
    i_withdrew: Optional[bool] = None
    # This listing has ACCEPTED a different offer (2026-08-19).
    #
    # Not "this offer is dead" — §1d keeps rival bids alive on purpose, because
    # accept is an agreement and not a lock, and a seller whose buyer ghosts
    # needs their fallbacks. It means "not your move right now": the client
    # stops stamping YOUR MOVE on it and stops counting it in the badge, while
    # every control stays exactly where it was.
    #
    # False, never None: this is computed from a column the server always has,
    # so "we could not tell" is not a state that exists here.
    superseded: bool = False
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
#: How many times ONE offer may be countered before the ladder is closed.
#: Only the seller may counter (`who_may_respond`), so this counts the whole
#: ladder rather than one side of it. eBay's equivalent is 5 per side.
MAX_COUNTERS = 5

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
async def _notify_trade(conn, user_id: str, title: str, body: str, offer_id: str,
                        kind: str = "p2p_offer") -> None:
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
            data={"kind": kind, "offer_id": offer_id},
            # The specific offer, not the list. A member with six trades open
            # who is told "rate your trade" and lands on a flat list has been
            # handed a search task, not a link. `app/offers.tsx` reads
            # `offerId` and opens that card (npm run check:params covers the
            # in-app pushes to this route; a server deep link is the same
            # contract arriving from outside).
            #
            # STAYS on `/offers?offerId=` until the build carrying
            # `/offer/[offerId]` is live. Repointing it now is §5e's
            # deploy-order trap: the server ships in minutes, an app build
            # takes a day, and in between every trade push would land on a
            # route that does not exist. Repoint in the deploy AFTER that
            # build. `test_trade_pushes_deep_link_to_the_offer_not_the_list`
            # holds it here.
            deep_link=f"/offers?offerId={offer_id}",
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
    #: How many offers match `role` in TOTAL, before limit/offset.
    #:
    #: The client sent no limit, so `pagination_params` defaulted to 50 and the
    #: query is `ORDER BY o.created_at DESC LIMIT 50` — the 50 NEWEST. An active
    #: seller with fifty newer trades silently lost an older-but-live bid off
    #: the bottom, and "needs you" includes ungraded completed trades, which are
    #: old by construction. Nothing on screen said anything had been dropped:
    #: a truncation that reads as completeness. The screen can now say
    #: "showing 50 of 73" instead of quietly lying.
    total: int = 0


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
        listing_image_url=_row_opt(r, "listing_image_url"),
        buyer_id=str(r["buyer_id"]),
        seller_id=str(r["seller_id"]),
        amount=float(r["amount"]),
        currency=r["currency"] or "EUR",
        status=r["status"],
        message=r["message"],
        counter_count=int(r["counter_count"] or 0),
        # `_row_opt`, not `r[...]`: create_offer's INSERT ... RETURNING does
        # not select this, and a direct read would be a 500 on the primary
        # Stage 2 entry point only — the trap this file's tests pin.
        i_withdrew=(
            None if _row_opt(r, "withdrawn_by") is None
            else str(_row_opt(r, "withdrawn_by")) == me
        ),
        created_at=r["created_at"],
        # `_row_opt`: create_offer's INSERT ... RETURNING cannot join the
        # listing and does not select this, and reading a missing key directly
        # is a 500 on that path only — the exact shape that broke the primary
        # Stage 2 entry point once already.
        updated_at=_row_opt(r, "updated_at"),
        seller_confirmed_at=r["seller_confirmed_at"],
        buyer_confirmed_at=r["buyer_confirmed_at"],
        tracking_carrier=r["tracking_carrier"],
        tracking_carrier_label=_carrier_label(r["tracking_carrier"]),
        tracking_code=r["tracking_code"],
        tracking_set_at=r["tracking_set_at"],
        # Address columns are read OPTIONALLY: a query that joins
        # p2p_offer_addresses yields a real PostNL link, one that does not
        # yields None and the client shows a copyable code. That is the same
        # fallback that existed when we held no addresses at all, so no query
        # becomes wrong by not joining — it just gets the older behaviour.
        tracking_url=_tracking_url(
            r["tracking_carrier"],
            r["tracking_code"],
            postcode=_row_opt(r, "delivery_postcode"),
            country=_row_opt(r, "delivery_country"),
        ),
        i_am_buyer=is_buyer,
        # A live bid on a listing that has already accepted a DIFFERENT one.
        # `_row_opt` because create_offer's INSERT..RETURNING cannot join the
        # listing — the same trap the tracking columns document there. Bidding
        # on a reserved listing IS allowed (that is the point of a soft
        # reserve), so False on that one path is a display default rather than
        # a claim, and the next list call corrects it.
        superseded=(
            _row_opt(r, "reserved_offer_id") is not None
            and str(_row_opt(r, "reserved_offer_id")) != str(r["id"])
            and r["status"] in (_PENDING, _COUNTERED)
        ),
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
        # Counted in the SAME acquire and with the SAME predicate as the page
        # below it. A second helper spelling out "mine, filtered by role" is
        # how the count and the page drift apart, and a total that disagrees
        # with the list is worse than no total at all.
        total = await conn.fetchval(
            """
            SELECT count(*)
            FROM public.p2p_offers o
            WHERE (o.buyer_id = $1::uuid OR o.seller_id = $1::uuid)
              AND ($2 = 'all'
                   OR ($2 = 'buying'  AND o.buyer_id  = $1::uuid)
                   OR ($2 = 'selling' AND o.seller_id = $1::uuid))
            """,
            user_id, role,
        )
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
            LEFT JOIN public.p2p_offer_addresses a ON a.offer_id = o.id
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

    return OfferListResponse(offers=offers, total=int(total or 0))


@router.get("/offers/{offer_id}", response_model=OfferOut,
            summary="One offer, for the trade screen")
async def get_offer(
    offer_id: str,
    user_id: str = Depends(get_current_user_id),
) -> OfferOut:
    """A single trade, for `/offer/[offerId]`.

    Added 2026-08-19 with the trade screen. Every action endpoint already
    RETURNS an OfferOut, but nothing could LOAD one — the client could only
    fetch the whole list and search it, which breaks on a trade older than the
    200-row page and costs a full list read (plus its market_hits price-sanity
    aggregate) to render one row.

    Uses `_OFFER_COLUMNS` and `_row_to_offer`, so this row is identical to the
    one the list returns — `superseded`, the tracking URL, the price verdict
    and the two confirm flags all follow the same rules. A second hand-rolled
    mapper here is exactly how the list and the detail screen would come to
    disagree about whether a trade needs you.

    `already_graded` is selected the same way the list does it. Without it
    `_row_to_offer` defaults the flag to False, and the screen would offer
    "Rate the seller" on a trade you had already rated.
    """
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code="DB_UNAVAILABLE")

    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            f"""
            SELECT {_OFFER_COLUMNS},
                   EXISTS (
                       SELECT 1 FROM public.member_grades g
                       WHERE g.offer_id = o.id AND g.rater_id = $2::uuid
                   ) AS already_graded
            FROM public.p2p_offers o
            LEFT JOIN public.marketplace_listings l ON l.id = o.listing_id
            LEFT JOIN public.p2p_offer_addresses a ON a.offer_id = o.id
            WHERE o.id = $1::uuid
            """,
            offer_id, user_id,
        )
        if r is None:
            raise error_response(404, "Offer not found", code="OFFER_NOT_FOUND")
        # A trade is private to its two parties. 404, not 403: telling a
        # stranger "that offer exists but is not yours" confirms the id.
        if str(r["buyer_id"]) != user_id and str(r["seller_id"]) != user_id:
            raise error_response(404, "Offer not found", code="OFFER_NOT_FOUND")

    return _row_to_offer(r, user_id)


@router.get("/offers/{offer_id}", response_model=OfferOut,
            summary="One offer, for the trade screen")
async def get_offer(
    offer_id: str,
    user_id: str = Depends(get_current_user_id),
) -> OfferOut:
    """A single trade, for `/offer/[offerId]`.

    Added 2026-08-19 with the trade screen. Every action endpoint already
    RETURNS an OfferOut, but nothing could LOAD one — the client could only
    fetch the whole list and search it, which breaks for a trade older than the
    200-row page and costs a full list read (plus its per-item `market_hits`
    price-sanity aggregate) to render a single row.

    Built on `_OFFER_COLUMNS` + `_row_to_offer`, so this row is IDENTICAL to
    the one the list returns: `superseded`, the resolved tracking URL, the
    price verdict and both confirm flags follow the same rules. A second
    hand-rolled mapper here is precisely how the list and the trade screen
    would come to disagree about whether a trade needs you.

    `already_graded` is selected the same way the list selects it. Without it
    `_row_to_offer` defaults the flag to False and the screen would offer
    "Rate the seller" on a trade the member had already rated.

    NOTE: the trade pushes still deep-link to `/offers?offerId=…`, NOT here.
    §5e's deploy-order trap — repointing them before the build carrying
    `/offer/[offerId]` is live would land every trade push on a route that
    does not exist. Repoint them in the deploy AFTER that build ships.
    """
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable", code="DB_UNAVAILABLE")

    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            f"""
            SELECT {_OFFER_COLUMNS},
                   EXISTS (
                       SELECT 1 FROM public.member_grades g
                       WHERE g.offer_id = o.id AND g.rater_id = $2::uuid
                   ) AS already_graded
            FROM public.p2p_offers o
            LEFT JOIN public.marketplace_listings l ON l.id = o.listing_id
            LEFT JOIN public.p2p_offer_addresses a ON a.offer_id = o.id
            WHERE o.id = $1::uuid
            """,
            offer_id, user_id,
        )
        if r is None:
            raise error_response(404, "Offer not found", code="OFFER_NOT_FOUND")
        # A trade is private to its two parties. 404 rather than 403: telling a
        # stranger "that offer exists but is not yours" confirms the id.
        if str(r["buyer_id"]) != user_id and str(r["seller_id"]) != user_id:
            raise error_response(404, "Offer not found", code="OFFER_NOT_FOUND")

    return _row_to_offer(r, user_id)


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
            SELECT o.*, l.listing_title,
                   a.postcode AS delivery_postcode, a.country AS delivery_country
            FROM public.p2p_offers o
            LEFT JOIN public.marketplace_listings l ON l.id = o.listing_id
            LEFT JOIN public.p2p_offer_addresses a ON a.offer_id = o.id
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
            if status not in (_PENDING, _COUNTERED):
                raise error_response(409, f"Offer is already {status}",
                                     code="OFFER_NOT_OPEN")

            # WHOEVER DID NOT SET THE CURRENT NUMBER IS THE ONE WHO ANSWERS IT.
            #
            # `counter` overwrites `amount` with the seller's figure (see the
            # counter branch below), so a countered offer is the SELLER's offer
            # sitting in front of the BUYER. Until 2026-08-15 all three actions
            # were seller-only, which meant a buyer looking at a counter had no
            # accept and no decline — only `withdraw`. The app knew better and
            # said so: `offerNeedsMyAction` returns true for a buyer on a
            # countered offer, so the card was stamped YOUR MOVE and the badge
            # counted it, while the only control rendered was Delete. Reported
            # as *"where is the accept button for example / or reject"*.
            #
            # `counter` itself stays seller-only: a buyer raising their own bid
            # is just a new offer, and letting both sides write `amount` makes
            # "whose number is this?" unanswerable.
            #
            # The rule lives in `who_may_respond` rather than in this branch so
            # it can be tested as a rule. The tests around this router inspect
            # SOURCE, which is why the seller-only bug survived 30 green tests:
            # nothing could call the decision, so nothing checked it.
            side = who_may_respond(action, status)
            if side == "buyer" and not is_buyer:
                raise error_response(
                    403,
                    "The counter is yours to answer — the buyer accepts or declines it",
                    code="BUYER_ONLY",
                )
            if side == "seller" and not is_seller:
                raise error_response(
                    403,
                    "Only the seller can counter an offer" if action == "counter"
                    else "Only the seller can respond to an offer",
                    code="SELLER_ONLY",
                )

        if action == "counter" and amount is None:
            raise error_response(400, "A counter needs an amount", code="AMOUNT_REQUIRED")

        # A haggle has to end somewhere. `counter` was uncapped, so two people
        # could ping-pong an offer forever — and every round rewrites `amount`,
        # so there is no history to look back on, just a number that keeps
        # moving. eBay stops at five counters per side for the same reason.
        #
        # Only the seller may counter (`who_may_respond`), so `counter_count`
        # counts seller counters and MAX_COUNTERS is the whole ladder. Checked
        # before the write, not after, so the cap is the last legal counter
        # rather than the first illegal one.
        if action == "counter" and int(o["counter_count"] or 0) >= MAX_COUNTERS:
            raise error_response(
                409,
                f"This offer has been countered {MAX_COUNTERS} times — accept it, "
                "decline it, or let the buyer make a fresh offer",
                code="COUNTER_LIMIT",
            )

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
            # PENDING and COUNTERED included since 2026-08-15. Before that a
            # buyer could not retract an offer the seller had not answered:
            # `withdraw` required accepted/shipped, `decline` and `accept` are
            # the seller's, and `counter` raises your own bid. A five-day-old
            # "Awaiting seller" was a resting bid with no cancel — money
            # notionally committed with no way out but for the other side to
            # act. That is the one thing every order book lets you do.
            #
            # Either party, deliberately: a seller who countered may want to
            # retract that counter for the same reason. `withdrawn_by` already
            # records WHO walked, which is the only honest sanction we apply,
            # and it works the same from any of these states.
            if status not in (_PENDING, _COUNTERED, _ACCEPTED, _SHIPPED):
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
            LEFT JOIN public.p2p_offer_addresses a ON a.offer_id = o.id
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
            # WHO accepted decides who is told. Since 2026-08-15 a COUNTER is the
            # buyer's to answer, so this branch fires for both directions — and
            # until 2026-08-16 it always notified the buyer with "The seller
            # accepted", which meant a buyer accepting a counter got a message
            # about their own tap while the SELLER, who now has to post the item,
            # was told nothing at all. Found by the Stage 2 E2E, which had been
            # left un-run since the permission change: the guard was updated,
            # the notification beside it was not.
            accepter_is_buyer = user_id == str(o["buyer_id"])
            if accepter_is_buyer:
                other, subject, body = str(o["seller_id"]), "Your counter was accepted", (
                    f"The buyer accepted {amt} for \"{title_}\". Arrange the exchange in Open bids."
                )
            else:
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
    #: The carrier's OWN "send a parcel" page. The seller contracts with them
    #: directly — Sparrow never books carriage (spec §5a). Null = no public
    #: consumer booking page we can link to.
    book_url: Optional[str] = None
    #: Regions this carrier serves, for filtering the booking list.
    regions: List[str] = []


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
async def list_carriers(
    region: Optional[str] = Query(
        None,
        max_length=32,
        description=(
            "Filter to carriers serving a region. Omit to use the caller's "
            "`user_settings.region`; pass `all` for the unfiltered list."
        ),
    ),
    user_id: str = Depends(get_current_user_id),
) -> List[CarrierOut]:
    """Served from `_CARRIER_TRACKING` so the picker cannot drift from the URL
    table. A hardcoded client list would let a seller choose a carrier the
    server does not know, which silently degrades to a code with no link.

    **Region resolves HERE, from `user_settings`.** The booking list used to be
    filtered on the client against the DEVICE's settings, while
    `/p2p/payment-rails` resolved region from the database — two sources for one
    question, which drift the moment a member changes region on another device.
    One source, server-side, for both halves of settle-up.

    `region=all` is the escape hatch, and the tracking picker uses it: a seller
    may legitimately ship with a carrier outside their own region, and hiding it
    there would leave them unable to record a code they are holding.
    """
    resolved = (region or "").strip().lower()
    if resolved != "all":
        if not resolved:
            pool = get_db_pool()
            if pool is not None:
                row = await pool.fetchrow(
                    "SELECT region FROM public.user_settings WHERE user_id = $1::uuid",
                    user_id,
                )
                resolved = ((row or {}).get("region") or "").strip().lower()
        if resolved not in REGIONS:
            # Unknown region filters nothing rather than everything. An empty
            # carrier list reads as "Sparrow does not ship where I live".
            resolved = "all"

    def serves(key: str) -> bool:
        if resolved == "all":
            return True
        return resolved in _CARRIER_BOOKING.get(key, (None, ()))[1]

    return [
        CarrierOut(
            key=k,
            label=label,
            linkable=url is not None,
            book_url=_CARRIER_BOOKING.get(k, (None, ()))[0],
            regions=list(_CARRIER_BOOKING.get(k, (None, ()))[1]),
        )
        for k, (label, url) in _CARRIER_TRACKING.items()
        if serves(k)
    ]


class PaymentRailOut(BaseModel):
    """The PUBLIC shape of a rail.

    Deliberately NOT `PaymentRail` subclassed. Inheriting shipped
    `deep_link_template` to every client — an internal format string that
    invites a client to build its own links, which is precisely where the two
    invented Revolut and Cash App URLs came from. The server builds links; the
    client is handed finished ones.
    """
    key: str
    label: str
    url: str
    coverage: str
    reversible: Optional[bool] = None
    note: Optional[str] = None
    #: What to ask the SELLER for. The settings screen reads this, so it stays.
    handle_label: Optional[str] = None
    #: The rail's own URL built from the SELLER's handle. Null whenever one
    #: could not be built — no template, no handle, or a handle that failed
    #: validation. Callers fall back to `url`; a half-substituted link is never
    #: returned.
    pay_url: Optional[str] = None
    #: True only when `pay_url` actually contains the figure. PayPal and Venmo
    #: publish an amount-carrying format; Revolut and Cash App do not, so their
    #: links land on the right person and the buyer types the amount. Without
    #: this the client promised "amount filled in" for all of them.
    pay_url_has_amount: bool = False


class PaymentRailsOut(BaseModel):
    region: str
    rails: List[PaymentRailOut]
    #: Rendered with the list every time, not once at onboarding.
    disclaimer: str


class DeliveryAddressIn(BaseModel):
    """Where the parcel goes. Supplied by the BUYER, for one trade.

    Built for Europe and the US, which differ in one field: `state` is required
    for US addresses and absent from most European ones. Validated in the
    router rather than as a CHECK, because baking one country's postal grammar
    into the schema is how the next country becomes a migration.
    """
    recipient_name: str = Field(..., min_length=2, max_length=120)
    line1: str = Field(..., min_length=2, max_length=200)
    line2: Optional[str] = Field(None, max_length=200)
    postcode: str = Field(..., min_length=2, max_length=16)
    city: str = Field(..., min_length=1, max_length=120)
    state: Optional[str] = Field(None, max_length=64)
    country: str = Field(..., min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")


class DeliveryAddressOut(BaseModel):
    recipient_name: str
    line1: str
    line2: Optional[str] = None
    postcode: str
    city: str
    state: Optional[str] = None
    country: str


class PaymentHandleIn(BaseModel):
    rail_key: str = Field(..., min_length=2, max_length=32)
    #: Empty string deletes. A member removing their PayPal handle should not
    #: need a second endpoint, and DELETE-with-a-body is a bad time.
    handle: str = Field("", max_length=64)


class PaymentHandleOut(BaseModel):
    rail_key: str
    handle: str


async def _offer_for_address(pool, offer_id: str):
    return await pool.fetchrow(
        "SELECT buyer_id, seller_id, status FROM public.p2p_offers WHERE id = $1::uuid",
        offer_id,
    )


@router.put("/offers/{offer_id}/address", response_model=DeliveryAddressOut,
            summary="Buyer supplies the delivery address for an accepted trade")
async def set_delivery_address(
    offer_id: str,
    payload: DeliveryAddressIn,
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(_offer_limit),
) -> DeliveryAddressOut:
    """Buyer-only, and only once the trade is live.

    Gated on `accepted`/`shipped` deliberately: §5a permits handing addresses
    between parties **after `accepted`**, and collecting one earlier would mean
    holding a home address for a trade that may never happen. A pending offer is
    a conversation, not a shipment.
    """
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database not available", code="DB_UNAVAILABLE")

    offer = await _offer_for_address(pool, offer_id)
    if offer is None:
        raise error_response(404, "Offer not found", code="OFFER_NOT_FOUND")
    if str(offer["buyer_id"]) != str(user_id):
        # The SELLER cannot write the buyer's address. Obvious, and worth
        # enforcing: this is the one endpoint where the wrong actor writing
        # would send someone else's parcel somewhere.
        raise error_response(403, "Only the buyer sets the delivery address", code="NOT_BUYER")
    if offer["status"] not in (_ACCEPTED, _SHIPPED):
        raise error_response(
            409,
            "Add the delivery address once the seller has accepted.",
            code="OFFER_NOT_LIVE",
        )

    country = payload.country.upper()
    state = (payload.state or "").strip() or None
    if country == "US" and not state:
        # A US parcel without a state is undeliverable. Rejecting here beats a
        # carrier rejecting it after the seller has paid for postage.
        raise error_response(400, "US addresses need a state.", code="STATE_REQUIRED")

    row = await pool.fetchrow(
        """
        INSERT INTO public.p2p_offer_addresses
            (offer_id, buyer_id, recipient_name, line1, line2, postcode, city, state, country)
        VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (offer_id) DO UPDATE SET
            recipient_name = EXCLUDED.recipient_name,
            line1 = EXCLUDED.line1, line2 = EXCLUDED.line2,
            postcode = EXCLUDED.postcode, city = EXCLUDED.city,
            state = EXCLUDED.state, country = EXCLUDED.country,
            updated_at = now()
        RETURNING recipient_name, line1, line2, postcode, city, state, country
        """,
        offer_id, user_id, payload.recipient_name.strip(), payload.line1.strip(),
        (payload.line2 or "").strip() or None, payload.postcode.strip(),
        payload.city.strip(), state, country,
    )
    return DeliveryAddressOut(**dict(row))


@router.get("/offers/{offer_id}/address", response_model=Optional[DeliveryAddressOut],
            summary="The delivery address for a trade — buyer or seller")
async def get_delivery_address(
    offer_id: str,
    user_id: str = Depends(get_current_user_id),
) -> Optional[DeliveryAddressOut]:
    """Both parties of a LIVE trade, nobody else.

    This is the only path by which a seller sees the address: the table is
    buyer-only under RLS. Returns null rather than 404 when none has been
    supplied yet — "not given" is a normal state the seller has to be able to
    see, so they know to ask.
    """
    pool = get_db_pool()
    if pool is None:
        return None
    offer = await _offer_for_address(pool, offer_id)
    if offer is None:
        raise error_response(404, "Offer not found", code="OFFER_NOT_FOUND")
    me = str(user_id)
    if me not in (str(offer["buyer_id"]), str(offer["seller_id"])):
        raise error_response(403, "Not your trade", code="NOT_A_PARTY")
    # The SELLER only sees it once the trade is live. The buyer always sees
    # their own, so they can review what they gave.
    if me == str(offer["seller_id"]) and offer["status"] not in (_ACCEPTED, _SHIPPED):
        raise error_response(403, "Not your trade", code="NOT_A_PARTY")

    row = await pool.fetchrow(
        "SELECT recipient_name, line1, line2, postcode, city, state, country "
        "FROM public.p2p_offer_addresses WHERE offer_id = $1::uuid",
        offer_id,
    )
    return DeliveryAddressOut(**dict(row)) if row else None


@router.get("/payment-handles", response_model=List[PaymentHandleOut],
            summary="The caller's own payment handles")
async def list_payment_handles(
    user_id: str = Depends(get_current_user_id),
) -> List[PaymentHandleOut]:
    """Owner-only. The counterparty never reads this — see `set_payment_handle`."""
    pool = get_db_pool()
    if pool is None:
        return []
    rows = await pool.fetch(
        "SELECT rail_key, handle FROM public.user_payment_handles "
        "WHERE user_id = $1::uuid ORDER BY rail_key",
        user_id,
    )
    return [PaymentHandleOut(rail_key=r["rail_key"], handle=r["handle"]) for r in rows]


@router.put("/payment-handles", response_model=List[PaymentHandleOut],
            summary="Set or clear one of the caller's payment handles")
async def set_payment_handle(
    payload: PaymentHandleIn,
    user_id: str = Depends(get_current_user_id),
    # Every other write in this router carries a limit; these two shipped
    # without one. A handle write is cheap, but an unbounded write endpoint is
    # a free amplifier and the inconsistency is the kind that survives review.
    _rl=Depends(_offer_limit),
) -> List[PaymentHandleOut]:
    """Store a PUBLIC identifier a buyer could already be given in chat.

    Validated with the same `clean_handle` that builds the link, so a handle
    that would be rejected at link time is rejected at write time instead —
    otherwise a member saves something, sees no error, and their buyers
    silently get the un-prefilled fallback forever.
    """
    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database not available", code="DB_UNAVAILABLE")

    rail_key = payload.rail_key.strip().lower()
    known = {r.key for r in rails_for_region(None)} | {
        r.key for reg in REGIONS for r in rails_for_region(reg)
    }
    if rail_key not in known:
        raise error_response(400, "Unknown payment rail", code="UNKNOWN_RAIL")

    raw = (payload.handle or "").strip()
    if not raw:
        await pool.execute(
            "DELETE FROM public.user_payment_handles WHERE user_id = $1::uuid AND rail_key = $2",
            user_id, rail_key,
        )
    else:
        cleaned = clean_handle(raw)
        if not cleaned:
            raise error_response(
                400,
                "That handle contains characters we cannot put in a link. "
                "Use letters, numbers, dots, dashes or underscores.",
                code="INVALID_HANDLE",
            )
        await pool.execute(
            """
            INSERT INTO public.user_payment_handles (user_id, rail_key, handle)
            VALUES ($1::uuid, $2, $3)
            ON CONFLICT (user_id, rail_key)
            DO UPDATE SET handle = EXCLUDED.handle, updated_at = now()
            """,
            user_id, rail_key, cleaned,
        )
    return await list_payment_handles(user_id)


@router.get("/payment-rails", response_model=PaymentRailsOut,
            summary="Payment rails the two members can settle up on, by region")
async def list_payment_rails(
    region: Optional[str] = Query(
        None,
        max_length=32,
        description="Override the caller's stored region. Omit to use user_settings.region.",
    ),
    offer_id: Optional[str] = Query(
        None,
        description=(
            "An ACCEPTED offer the caller is the BUYER of. Supplying it resolves "
            "the seller's handles and returns `pay_url` per rail, prefilled with "
            "the agreed amount."
        ),
    ),
    user_id: str = Depends(get_current_user_id),
) -> PaymentRailsOut:
    """A DIRECTORY, not a payment service.

    Sparrow never touches the money: this returns names, coverage, whether each
    rail is reversible, and a link to the rail's own site. The members transact
    there under their own accounts. See `app/lib/payment_rails.py` for the §5a
    rules this is bound by — in particular that the order is alphabetical
    because any other order is a representation about a payment provider.

    Region comes from `user_settings` rather than the client so two members
    reading the same screen cannot be shown different lists because one of them
    has a stale build.
    """
    resolved = (region or "").strip().lower()
    if not resolved:
        pool = get_db_pool()
        if pool is not None:
            row = await pool.fetchrow(
                "SELECT region FROM public.user_settings WHERE user_id = $1::uuid",
                user_id,
            )
            resolved = ((row or {}).get("region") or "").strip().lower()
    if resolved not in REGIONS:
        # Unknown or unset falls back to the global rails only. Showing a Dutch
        # member Zelle is worse than showing them fewer options.
        resolved = "other"
    # The SOURCE rails keep their templates; the public objects never see them.
    # Keyed so the prefill loop below can reach a source rail to build from —
    # `build_deep_link` reads `deep_link_template`, which PaymentRailOut
    # deliberately does not carry, so passing a public object would silently
    # return None for every rail.
    source = {r.key: r for r in rails_for_region(resolved)}
    # Explicit field pick, not **model_dump(): a splat would have to be trusted
    # to keep omitting the template as either model grows.
    rails = [
        PaymentRailOut(
            key=r.key, label=r.label, url=r.url, coverage=r.coverage,
            reversible=r.reversible, note=r.note, handle_label=r.handle_label,
        )
        for r in source.values()
    ]

    # Prefill, but only for the buyer of a live trade with THIS seller. The
    # handle table is owner-only under RLS and is never exposed directly: this
    # is the one path that reads someone else's handle, and it reads it to build
    # a link rather than to return the handle itself.
    if offer_id:
        pool = get_db_pool()
        if pool is not None:
            offer = await pool.fetchrow(
                """
                SELECT seller_id, buyer_id, amount, currency, status
                FROM public.p2p_offers WHERE id = $1::uuid
                """,
                offer_id,
            )
            # Silent no-prefill rather than a 403 on every mismatch: the rail
            # list is still correct and useful, and a seller opening their own
            # trade is not an error worth failing the screen for.
            if (
                offer is not None
                and str(offer["buyer_id"]) == str(user_id)
                and offer["status"] in ("accepted", "shipped")
            ):
                handles = {
                    r["rail_key"]: r["handle"]
                    for r in await pool.fetch(
                        "SELECT rail_key, handle FROM public.user_payment_handles "
                        "WHERE user_id = $1::uuid",
                        str(offer["seller_id"]),
                    )
                }
                amount = float(offer["amount"] or 0)
                currency = offer["currency"] or "EUR"
                # A reference the seller can recognise. Short, and it names the
                # item rather than the offer id, because the seller reads this
                # in their banking app next to two other payments.
                note = f"Sparrow {str(offer_id)[:8]}"
                for r in rails:
                    src = source[r.key]
                    r.pay_url = build_deep_link(
                        src, handles.get(r.key), amount, currency, note=note,
                    )
                    r.pay_url_has_amount = bool(r.pay_url) and carries_amount(src)

    return PaymentRailsOut(
        region=resolved,
        rails=rails,
        disclaimer=PAYMENT_DISCLAIMER,
    )


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
            LEFT JOIN public.p2p_offer_addresses a ON a.offer_id = o.id
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
            LEFT JOIN public.p2p_offer_addresses a ON a.offer_id = o.id
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
            #
            # This is the REVIEW ASK, not a receipt. Completion is the only
            # moment both members are still thinking about the trade, and a
            # rating asked for later is a rating not left — so the one push
            # completion sends is the one that asks for it, rather than a
            # "Trade completed" whose last sentence happens to mention grading.
            # Still ONE push per party: a receipt plus a rating prompt fired
            # together is two notifications for one event, and the second is
            # what gets muted.
            #
            # The wording names the OTHER side's role, because who you rate
            # depends on which side you were on — the same rule
            # `statusLabel(status, iAmBuyer)` follows on screen.
            title_ = fresh["listing_title"] or "your item"
            for party, other_role in (
                (str(fresh["buyer_id"]), "seller"),
                (str(fresh["seller_id"]), "buyer"),
            ):
                await _notify_trade(
                    conn, party, "Trade complete — how did it go?",
                    f"You both confirmed the exchange of \"{title_}\". "
                    f"Rate the {other_role} so other members know what to expect.",
                    offer_id,
                    kind="p2p_grade_request",
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
