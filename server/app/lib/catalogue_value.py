"""
ONE value for a catalogue item, shared by every surface that prices one
(2026-09-27, OPEN_DECISIONS #12).

Before this, Base Set Charizard (`pokemon:base1-base1-4`) had three numbers:
the scan and the catalogue page showed the median of daily medians — with
exactly two sources a day (TCGplayer EUR 825, Cardmarket EUR 1,531) that is
their MIDPOINT, EUR 1,159, nobody's price — while the saved item, portfolio and
analytics read the catalogue model (`price_prediction_daily.q50`) = EUR 825.
Saving a scan changed its price under the member.

Now:
  value  = the model's latest q50 — the number the value chain already uses
           for a catalogue-linked item (items_router.write_quick_valuation) —
           falling back to the median of daily medians (>= 3 comps) or the
           latest comp for the ~12 % of priced items the model has not reached.
  range  = the latest day's cheapest and dearest source (market_hits_daily
           min_price / max_price).
  sources_disagree = that range is wider than DISAGREE_RATIO and at least
           DISAGREE_MIN_GAP_EUR. Surfaces then show the RANGE, not a figure.
"""
from __future__ import annotations

from typing import Any, Optional

DISAGREE_RATIO = 1.5
# ...and at least this far apart in money. Measured 2026-09-27: a EUR 0.56
# common (sm10-101) spanned 0.47-4.20 — 9x, but a range on a bulk card is
# noise, not a warning.
DISAGREE_MIN_GAP_EUR = 5.0


async def catalogue_value(conn, item_ref: str) -> Optional[dict[str, Any]]:
    """Value + source spread for one catalogue item, or None if nothing prices it."""
    model = await conn.fetchrow(
        """
        SELECT q50
        FROM public.price_prediction_daily
        WHERE item_ref = $1 AND q50 IS NOT NULL
        ORDER BY day DESC
        LIMIT 1
        """,
        item_ref,
    )
    daily = await conn.fetchrow(
        """
        SELECT COALESCE(SUM(comps_count), 0) AS comps_count,
               percentile_cont(0.1) WITHIN GROUP (ORDER BY median_price) AS p10,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY median_price) AS median_price,
               percentile_cont(0.9) WITHIN GROUP (ORDER BY median_price) AS p90,
               (ARRAY_AGG(latest_price ORDER BY latest_seen_at DESC))[1] AS latest_price,
               (ARRAY_AGG(min_price ORDER BY day DESC))[1] AS low,
               (ARRAY_AGG(max_price ORDER BY day DESC))[1] AS high
        FROM market_hits_daily
        WHERE item_ref = $1
          AND day > (current_date - interval '180 days')
          AND median_price IS NOT NULL
        """,
        item_ref,
    )
    comps = int(daily["comps_count"]) if daily and daily["comps_count"] else 0
    median = float(daily["median_price"]) if daily and daily["median_price"] is not None else None
    latest = float(daily["latest_price"]) if daily and daily["latest_price"] is not None else None
    low = float(daily["low"]) if daily and daily["low"] is not None else None
    high = float(daily["high"]) if daily and daily["high"] is not None else None

    if model and model["q50"] is not None:
        value, source = float(model["q50"]), "catalog_model"
    elif comps >= 3 and median is not None:
        value, source = median, "market_median"
    elif latest is not None:
        value, source = latest, "latest_comp"
    else:
        return None

    p10 = float(daily["p10"]) if daily and daily["p10"] is not None else None
    p90 = float(daily["p90"]) if daily and daily["p90"] is not None else None
    disagree = bool(
        low and high and low > 0
        and high / low > DISAGREE_RATIO
        and high - low >= DISAGREE_MIN_GAP_EUR
    )
    return {
        "value": round(value, 2),
        "source": source,
        "comps_count": comps,
        "median": median,
        "latest": latest,
        "low": round(low, 2) if low is not None else None,
        "high": round(high, 2) if high is not None else None,
        "p10": round(p10, 2) if p10 is not None else None,
        "p90": round(p90, 2) if p90 is not None else None,
        "sources_disagree": disagree,
    }
