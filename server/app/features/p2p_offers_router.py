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
            l.listing_title
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


def _row_to_offer(r, me: str) -> OfferOut:
    is_buyer = str(r["buyer_id"]) == me
    both_confirmed = r["seller_confirmed_at"] is not None and r["buyer_confirmed_at"] is not None
    mine_confirmed = r["buyer_confirmed_at"] if is_buyer else r["seller_confirmed_at"]
    return OfferOut(
        id=str(r["id"]),
        listing_id=str(r["listing_id"]),
        listing_title=r.get("listing_title") if hasattr(r, "get") else r["listing_title"],
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
            SELECT id, user_id AS seller_id, listing_title, status, delisted_at
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
    out.listing_title = listing["listing_title"]
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
    return OfferListResponse(offers=[_row_to_offer(r, user_id) for r in rows])


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
    return _row_to_offer(fresh, user_id)


class CarrierOut(BaseModel):
    key: str
    label: str
    # False => we cannot build a working link from the code alone, so the client
    # must render a copyable code instead of a button. Sent rather than inferred
    # so the client never has to know WHY (postcode, no public URL, …).
    linkable: bool


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
            from app.features.p2p_listing_router import _stale_supply_hook
            await _stale_supply_hook(str(fresh["listing_id"]))
            fresh = dict(fresh)
            fresh["status"] = _COMPLETED

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
