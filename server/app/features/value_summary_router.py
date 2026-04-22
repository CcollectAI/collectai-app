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
    deal_savings: float = 0.0          # Sum of (initial_ask - final_price) on deals
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
        scan_row = await conn.fetchrow(
            "SELECT COUNT(*) AS cnt FROM quickscan_history WHERE user_id = $1",
            user_id,
        )
        total_scans = scan_row["cnt"] if scan_row else 0

        # -- Items tracked --
        items_row = await conn.fetchrow(
            "SELECT COUNT(*) AS cnt FROM portfolio_items WHERE user_id = $1",
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

        # -- Deal Desk savings --
        deals_row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS deal_count,
                COALESCE(SUM(initial_ask_price - final_price), 0) AS total_savings
            FROM deals
            WHERE buyer_id = $1
              AND status = 'completed'
              AND initial_ask_price > final_price
            """,
            user_id,
        )
        deal_count = deals_row["deal_count"] if deals_row else 0
        deal_savings = float(deals_row["total_savings"]) if deals_row else 0.0

        # -- Smart buys: items where purchase_price < q50 market estimate --
        smart_buys_rows = await conn.fetch(
            """
            SELECT
                pi.name AS item_name,
                pi.category,
                pi.purchase_price,
                pp.q50 AS market_value,
                (pp.q50 - pi.purchase_price) AS saved
            FROM portfolio_items pi
            JOIN LATERAL (
                SELECT q50 FROM price_predictions
                WHERE item_id = pi.id
                ORDER BY created_at DESC
                LIMIT 1
            ) pp ON true
            WHERE pi.user_id = $1
              AND pi.purchase_price IS NOT NULL
              AND pi.purchase_price > 0
              AND pp.q50 > pi.purchase_price
            ORDER BY (pp.q50 - pi.purchase_price) DESC
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
