"""
Sell Timing / Seasonal Analysis — helps collectors optimize when to sell.

Analyzes market_hits for a given item_ref, groups by month, identifies
the peak selling month, and recommends whether to sell now or wait.

Premium-only feature.
"""
from __future__ import annotations

import calendar
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.lib.db_helpers import get_db_pool
from app.rate_limit import per_user_rate_limit
from app.subscription import require_plan

router = APIRouter(prefix="/sell-timing", tags=["Sell Timing"])
logger = logging.getLogger(__name__)

_rate_limit = per_user_rate_limit(30, window_seconds=60, scope="sell_timing")

# Minimum observations needed for a meaningful recommendation
MIN_OBSERVATIONS = 50


class SellTimingResponse(BaseModel):
    peak_month: Optional[str] = Field(None, description="Month name with highest avg price")
    peak_avg_price: Optional[float] = Field(None, description="Average price in peak month (EUR)")
    current_month_avg: Optional[float] = Field(None, description="Average price in current month (EUR)")
    recommendation: str = Field(..., description="Human-readable sell timing recommendation")
    confidence: float = Field(0.0, description="Confidence score 0-1")
    observation_count: int = Field(0, description="Total observations used")
    monthly_data: Optional[list[dict]] = Field(
        None, description="Per-month average prices"
    )


@router.get(
    "/items/{item_ref}",
    response_model=SellTimingResponse,
    dependencies=[Depends(_rate_limit)],
)
async def get_sell_timing(
    item_ref: str,
    user_id: str = Depends(get_current_user_id),
    _plan: str = Depends(require_plan("premium")),
):
    """Get sell timing analysis for an item based on historical market data."""
    pool = get_db_pool()
    if pool is None:
        raise HTTPException(503, "Database unavailable")

    async with pool.acquire() as conn:
        # Query market_hits grouped by month
        rows = await conn.fetch(
            """
            SELECT
                EXTRACT(MONTH FROM created_at)::int AS month_num,
                AVG(price_eur) AS avg_price,
                COUNT(*) AS cnt
            FROM public.market_hits
            WHERE item_ref = $1
              AND price_eur IS NOT NULL
              AND price_eur > 0
              AND (is_listing IS NOT TRUE)
            GROUP BY month_num
            ORDER BY month_num
            """,
            item_ref,
        )

        # Also get total count
        total_count = sum(r["cnt"] for r in rows) if rows else 0

        if total_count < MIN_OBSERVATIONS:
            return SellTimingResponse(
                recommendation="Not enough data yet",
                confidence=0.0,
                observation_count=total_count,
            )

        # Build monthly data
        monthly_data = []
        peak_month_num = None
        peak_avg = 0.0

        for row in rows:
            month_num = row["month_num"]
            avg_price = float(row["avg_price"])
            month_name = calendar.month_name[month_num]
            monthly_data.append({
                "month": month_name,
                "month_num": month_num,
                "avg_price": round(avg_price, 2),
                "observation_count": row["cnt"],
            })
            if avg_price > peak_avg:
                peak_avg = avg_price
                peak_month_num = month_num

        if peak_month_num is None:
            return SellTimingResponse(
                recommendation="Not enough data yet",
                confidence=0.0,
                observation_count=total_count,
            )

        peak_month_name = calendar.month_name[peak_month_num]
        current_month = datetime.now(timezone.utc).month
        current_month_name = calendar.month_name[current_month]

        # Find current month avg
        current_avg = None
        for md in monthly_data:
            if md["month_num"] == current_month:
                current_avg = md["avg_price"]
                break

        # Compute confidence based on observation count and month coverage
        months_with_data = len(monthly_data)
        confidence = min(1.0, (total_count / 200) * (months_with_data / 12))
        confidence = round(confidence, 2)

        # Generate recommendation
        if current_month == peak_month_num:
            recommendation = (
                f"Now is the best time to sell! {current_month_name} is historically "
                f"the peak month for this item."
            )
        elif current_avg is not None and peak_avg > 0:
            pct_diff = ((peak_avg - current_avg) / current_avg) * 100
            if pct_diff > 5:
                recommendation = (
                    f"Wait \u2014 prices typically peak in {peak_month_name} "
                    f"(+{pct_diff:.0f}%)"
                )
            elif pct_diff < -5:
                recommendation = (
                    f"Consider selling now \u2014 {current_month_name} prices are "
                    f"above the {peak_month_name} average."
                )
            else:
                recommendation = (
                    f"Current prices are close to the {peak_month_name} peak. "
                    f"Selling now is reasonable."
                )
        else:
            recommendation = (
                f"Peak month is {peak_month_name} (avg \u20ac{peak_avg:.2f}). "
                f"No data for {current_month_name} yet."
            )

        return SellTimingResponse(
            peak_month=peak_month_name,
            peak_avg_price=round(peak_avg, 2),
            current_month_avg=round(current_avg, 2) if current_avg else None,
            recommendation=recommendation,
            confidence=confidence,
            observation_count=total_count,
            monthly_data=monthly_data,
        )
