"""
Value Summary — calculates what CollectAI has saved the user in time and money.

Used by the in-app retention notification (Instacart-style "you saved X").
Focuses on loss aversion: time saved + money saved through smart decisions.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.auth import get_current_user_id
from app.lib.db_helpers import get_db_pool
from app.rate_limit import per_user_rate_limit

router = APIRouter(prefix="/value-summary", tags=["Value Summary"])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Estimated minutes saved per action (based on manual research time)
MINUTES_PER_SCAN = 15        # Manual price lookup + comparison shopping
MINUTES_PER_ITEM_TRACKED = 5  # Spreadsheet / manual inventory management
MINUTES_PER_ALERT = 10       # Checking prices manually across marketplaces
MINUTES_PER_DUPLICATE = 20   # Time wasted on a duplicate purchase (return/resell)


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------

class SmartBuy(BaseModel):
    item_name: str
    category: str
    purchase_price: float
    market_value: float
    saved: float


class ValueSummaryResponse(BaseModel):
    # Time saved
    total_scans: int = 0
    total_items_tracked: int = 0
    total_alerts_triggered: int = 0
    duplicates_prevented: int = 0
    hours_saved: float = 0.0

    # Money saved
    deal_savings: float = 0.0          # Sum of (predicted_q50 - price paid) on PURCHASED deals, EUR only, never negative
    deal_count: int = 0
    smart_buy_savings: float = 0.0     # Sum of (market_value - purchase_price) where purchase < market
    smart_buy_count: int = 0
    total_money_saved: float = 0.0     # deal_savings + smart_buy_savings

    # Best find
    best_find_name: str | None = None
    best_find_category: str | None = None
    best_find_value: float = 0.0
    best_find_saved: float = 0.0       # How much below market they got it

    # Context
    member_since: str | None = None
    days_as_member: int = 0
    currency: str = "EUR"

    # Top smart buys (up to 3)
    top_smart_buys: list[SmartBuy] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

_value_summary_limit = per_user_rate_limit(5, 60)


@router.get("", response_model=ValueSummaryResponse)
async def get_value_summary(
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_value_summary_limit),
):
    """
    Calculate what CollectAI has saved this user in time and money.

    Money saved sources:
    1. Deal Desk savings: (initial_ask - final_price) on completed deals
    2. Smart buys: items bought below our q50 market estimate

    Time saved:
    - Scans × 15min (manual price research)
    - Items tracked × 5min (manual inventory)
    - Alerts × 10min (manual marketplace monitoring)
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # -- Member since --
        member_row = await conn.fetchrow(
            "SELECT created_at FROM auth.users WHERE id = $1",
            user_id,
        )
        member_since = None
        days_as_member = 0
        if member_row and member_row["created_at"]:
            member_since = member_row["created_at"].isoformat()
            days_as_member = (datetime.now(timezone.utc) - member_row["created_at"]).days

        # -- Scan count --
        # 2026-07-25: was `quickscan_history`, a table with 0 rows and NO writer
        # anywhere in the codebase — so "scans" on the value screen was pinned to
        # 0 for every user forever. Scan history actually lands in
        # `predict_sessions` (101 rows / 47 distinct users at repoint time),
        # written by the predict pipeline. Same shape as the device_tokens ->
        # user_push_tokens repoint: an empty parallel schema shadowing the real
        # one. quickscan_history is now unreferenced and can be dropped.
        scan_row = await conn.fetchrow(
            "SELECT COUNT(*) AS cnt FROM public.predict_sessions WHERE user_id = $1::uuid",
            user_id,
        )
        total_scans = scan_row["cnt"] if scan_row else 0

        # -- Items tracked --
        # portfolio_items is vestigial demo data (owner_tag='local_demo', 2 rows
        # at audit time). Real user portfolio lives in `items` with user_id.
        items_row = await conn.fetchrow(
            "SELECT COUNT(*) AS cnt FROM items WHERE user_id = $1::uuid AND NOT archived",
            user_id,
        )
        total_items = items_row["cnt"] if items_row else 0

        # -- Alerts triggered --
        alerts_row = await conn.fetchrow(
            "SELECT COUNT(*) AS cnt FROM notification_history WHERE user_id = $1 AND type = 'price_alert'",
            user_id,
        )
        total_alerts = alerts_row["cnt"] if alerts_row else 0

        # -- Duplicates prevented (tracked via analytics events) --
        dupes_row = await conn.fetchrow(
            "SELECT COUNT(*) AS cnt FROM notification_history WHERE user_id = $1 AND type = 'duplicate_detected'",
            user_id,
        )
        duplicates_prevented = dupes_row["cnt"] if dupes_row else 0

        # -- Deal savings: market median vs what you actually paid --
        #
        # This returned a hardcoded `0::numeric` until 2026-08-12, on the
        # grounds that "mandate_deals tracks listing_price only — no
        # negotiation delta". That stopped being true: the table now carries
        # `predicted_q50`, `price_vs_q50_pct` and `confirmed_price`, so the
        # saving on a purchased deal is measurable without any offer flow.
        # Every user reading "Sparrow saved you X" was getting the smart-buy
        # half only, with the deal half silently contributing zero.
        #
        # The definition is deliberately the SAME shape as smart_buy_savings
        # below — market q50 minus what you paid — so one banner never adds two
        # different meanings of "saved" together:
        #
        #   `confirmed_price` over `listing_price` — what they actually paid
        #     beats the asking price; falls back when unconfirmed.
        #   `GREATEST(…, 0)` — buying ABOVE market is not a negative saving.
        #     Summing signed deltas would let one bad buy silently cancel out
        #     real savings and quietly understate the total.
        #   `predicted_q50 IS NOT NULL` — no model estimate, no claim.
        #   EUR only — `q50` is EUR (valuation_worker trains on
        #     `COALESCE(price_eur, price)`, and the smart-buy query below
        #     already compares it against `purchase_price_eur`), while
        #     `listing_price` is in `listing_currency`. `fx_rates_v1` holds a
        #     single row, EUR=1.0, so a non-EUR deal cannot be converted
        #     honestly today. Undercounting is the only safe direction for a
        #     number shown to a user as money we saved them.
        deals_row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS deal_count,
                COALESCE(SUM(
                    GREATEST(
                        d.predicted_q50 - COALESCE(d.confirmed_price, d.listing_price),
                        0
                    )
                ) FILTER (
                    WHERE d.predicted_q50 IS NOT NULL
                      AND d.listing_currency = 'EUR'
                ), 0)::numeric AS total_savings
            FROM mandate_deals d
            WHERE d.user_id = $1
              -- 'completed' is NOT in the mandate_deals status CHECK
              -- (discovered, notified, clicked, purchased, declined, expired),
              -- so this counted a value that can never exist and reported 0
              -- deals forever. A read, so it never errored. 'purchased' is the
              -- terminal state. Found by check-constraint-drift.mjs 2026-07-25.
              AND d.status = 'purchased'
            """,
            user_id,
        )
        deal_count = deals_row["deal_count"] if deals_row else 0
        deal_savings = float(deals_row["total_savings"]) if deals_row else 0.0

        # -- Smart buys: items where purchase_price < q50 market estimate --
        # Source table corrected from vestigial portfolio_items → items.
        # price_predictions canonical join columns: item_ref + generated_at
        # (learnings.md §42), not item_id + created_at.
        smart_buys_rows = await conn.fetch(
            """
            SELECT
                COALESCE(i.title, i.manual_name, i.name, '') AS item_name,
                i.category,
                -- EUR half throughout: pp.q50 is EUR, while purchase_price is
                -- raw in purchase_currency. Comparing them treated a USD 100
                -- purchase as EUR 100, which both mis-filtered the "smart buy"
                -- test (pp.q50 > purchase_price) and overstated the saving for
                -- any user not on EUR. See the paired-columns note in
                -- docs/ARCHITECTURE.md.
                i.purchase_price_eur AS purchase_price,
                pp.q50 AS market_value,
                (pp.q50 - i.purchase_price_eur) AS saved
            FROM items i
            JOIN LATERAL (
                SELECT q50 FROM price_predictions
                WHERE item_ref = i.canonical_ref
                ORDER BY generated_at DESC
                LIMIT 1
            ) pp ON true
            WHERE i.user_id = $1::uuid AND NOT i.archived
              AND i.purchase_price_eur IS NOT NULL
              AND i.purchase_price_eur > 0
              AND pp.q50 > i.purchase_price_eur
            ORDER BY (pp.q50 - i.purchase_price_eur) DESC
            LIMIT 20
            """,
            user_id,
        )

        smart_buy_savings = 0.0
        smart_buy_count = 0
        top_smart_buys: list[SmartBuy] = []
        best_find_name = None
        best_find_category = None
        best_find_value = 0.0
        best_find_saved = 0.0

        for row in smart_buys_rows:
            saved = float(row["saved"])
            smart_buy_savings += saved
            smart_buy_count += 1

            if saved > best_find_saved:
                best_find_saved = saved
                best_find_name = row["item_name"]
                best_find_category = row["category"]
                best_find_value = float(row["market_value"])

            if len(top_smart_buys) < 3:
                top_smart_buys.append(SmartBuy(
                    item_name=row["item_name"],
                    category=row["category"],
                    purchase_price=float(row["purchase_price"]),
                    market_value=float(row["market_value"]),
                    saved=saved,
                ))

        # -- User currency preference --
        settings_row = await conn.fetchrow(
            "SELECT currency FROM user_settings WHERE user_id = $1",
            user_id,
        )
        currency = settings_row["currency"] if settings_row and settings_row["currency"] else "EUR"

        # -- Calculate time saved --
        total_minutes = (
            total_scans * MINUTES_PER_SCAN
            + total_items * MINUTES_PER_ITEM_TRACKED
            + total_alerts * MINUTES_PER_ALERT
            + duplicates_prevented * MINUTES_PER_DUPLICATE
        )
        hours_saved = round(total_minutes / 60, 1)

        total_money_saved = deal_savings + smart_buy_savings

        return ValueSummaryResponse(
            total_scans=total_scans,
            total_items_tracked=total_items,
            total_alerts_triggered=total_alerts,
            duplicates_prevented=duplicates_prevented,
            hours_saved=hours_saved,
            deal_savings=round(deal_savings, 2),
            deal_count=deal_count,
            smart_buy_savings=round(smart_buy_savings, 2),
            smart_buy_count=smart_buy_count,
            total_money_saved=round(total_money_saved, 2),
            best_find_name=best_find_name,
            best_find_category=best_find_category,
            best_find_value=round(best_find_value, 2),
            best_find_saved=round(best_find_saved, 2),
            member_since=member_since,
            days_as_member=days_as_member,
            currency=currency,
            top_smart_buys=top_smart_buys,
        )
