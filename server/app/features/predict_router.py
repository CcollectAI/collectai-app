"""
Price prediction evidence router.

Exposes GET /predict/evidence/{item_id} for the PriceExplanationSheet
in the frontend. Returns the latest price prediction with explanation
and market evidence.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.errors import error_response
from app.db import db_configured, get_conn
from app.rate_limit import per_user_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predict", tags=["Predictions"])


class TrendDataPoint(BaseModel):
    date: str
    q50: float
    q10: Optional[float] = None
    q90: Optional[float] = None


class PriceTrendResponse(BaseModel):
    item_ref: str
    period_days: int = 90
    data_points: list[TrendDataPoint] = Field(default_factory=list)
    direction: Optional[str] = None  # "up", "down", "flat"
    pct_change: Optional[float] = None  # % change over period
    current_q50: Optional[float] = None
    earliest_q50: Optional[float] = None


class EvidenceSourceResponse(BaseModel):
    source: str
    count: int
    avg_price: float
    date_range: Optional[str] = None


class EvidenceSummaryResponse(BaseModel):
    sources: list[EvidenceSourceResponse] = Field(default_factory=list)
    total_comps: int = 0


class PriceEvidenceResponse(BaseModel):
    explanation: Optional[str] = None
    evidence_summary: Optional[EvidenceSummaryResponse] = None
    evidence_hit_ids: list[str] = Field(default_factory=list)
    prediction_at: Optional[str] = None
    q10: Optional[float] = None
    q50: Optional[float] = None
    q90: Optional[float] = None
    confidence_score: Optional[float] = None


def _parse_json(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val
    return val


@router.get("/evidence/{item_id}", response_model=PriceEvidenceResponse)
async def get_price_evidence(
    item_id: str,
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(per_user_rate_limit(30, window_seconds=60, scope="predict")),
):
    """
    Return the latest price prediction with explanation and evidence
    for the given item.

    The frontend PriceExplanationSheet uses this to show:
      - explanation text
      - evidence_summary (sources, counts, avg prices)
      - evidence_hit_ids (for linking to comparable sales)
    """
    if not db_configured():
        # Return empty evidence in DB-disabled mode
        return PriceEvidenceResponse()

    try:
        async with get_conn() as conn:
            # Verify item ownership (single query — no info leak)
            owner_check = await conn.fetchval(
                "SELECT 1 FROM public.items WHERE id = $1::uuid AND user_id = $2::uuid",
                item_id,
                user_id,
            )
            if owner_check is None:
                raise error_response(404, "Item not found")

            # Fetch latest prediction. price_predictions has no `asof`
            # column; the equivalent is generated_at. price_predictions
            # also doesn't have item_id — it has item_ref (the canonical
            # key), so this lookup needs the item's canonical_key first.
            pred = await conn.fetchrow(
                """
                SELECT q10, q50, q90, conf_score, explanation,
                       evidence_summary, evidence_hit_ids,
                       generated_at AS asof
                FROM public.price_predictions
                WHERE item_ref = (SELECT canonical_ref FROM items WHERE id = $1::uuid)
                ORDER BY generated_at DESC
                LIMIT 1
                """,
                item_id,
            )

            if not pred:
                return PriceEvidenceResponse()

            # Parse evidence fields
            raw_summary = _parse_json(pred.get("evidence_summary"))
            raw_hit_ids = _parse_json(pred.get("evidence_hit_ids")) or []

            evidence_summary = None
            if isinstance(raw_summary, dict) and raw_summary.get("sources"):
                evidence_summary = EvidenceSummaryResponse(
                    sources=[
                        EvidenceSourceResponse(**s)
                        for s in raw_summary["sources"]
                    ],
                    total_comps=raw_summary.get("total_comps", 0),
                )

            explanation = pred.get("explanation")

            # If no explanation stored, try to generate one on the fly
            if not explanation:
                try:
                    item_row = await conn.fetchrow(
                        "SELECT title, category, attributes_json FROM public.items WHERE id = $1::uuid",
                        item_id,
                    )
                    if item_row:
                        from app.ml.explainer import generate_simple_explanation

                        explanation = generate_simple_explanation(
                            category=item_row.get("category") or "unknown",
                        )
                except Exception as e:
                    logger.warning("[predict] fallback explanation failed: %s", e)

            # Record demand signal with geo enrichment (best-effort)
            try:
                from app.features.data_moat import record_demand_signal, get_user_geo
                region, country = await get_user_geo(user_id)
                await record_demand_signal(
                    signal_type="item_viewed",
                    item_key=item_id,
                    user_id=user_id,
                    region=region,
                    country_code=country,
                )
            except Exception:
                pass

            return PriceEvidenceResponse(
                explanation=explanation,
                evidence_summary=evidence_summary,
                evidence_hit_ids=[str(h) for h in raw_hit_ids],
                prediction_at=pred["asof"].isoformat() if pred.get("asof") else None,
                q10=float(pred["q10"]) if pred.get("q10") is not None else None,
                q50=float(pred["q50"]) if pred.get("q50") is not None else None,
                q90=float(pred["q90"]) if pred.get("q90") is not None else None,
                confidence_score=float(pred["conf_score"]) if pred.get("conf_score") is not None else None,
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("[predict] DB error for evidence: %s", exc)
        return PriceEvidenceResponse()


@router.get("/trend/{item_id}", response_model=PriceTrendResponse)
async def get_price_trend(
    item_id: str,
    days: int = Query(default=90, ge=7, le=365, description="Lookback period in days"),
    user_id: str = Depends(get_current_user_id),
):
    """Return price history trend for an item over the specified period.

    Returns data points, direction (up/down/flat), and percentage change.
    """
    if not db_configured():
        return PriceTrendResponse(item_ref=item_id, period_days=days)

    try:
        async with get_conn() as conn:
            # Verify item ownership AND resolve the canonical_key used by
            # price_history. Pre-fix 2026-04-19 the query did WHERE
            # item_ref = <user's item uuid> which never matched
            # (price_history.item_ref is a catalog key like 'mtg:black-lotus-415',
            # not a user-item UUID). Result: paid users always saw an empty
            # Price Trend chart.
            owner_row = await conn.fetchrow(
                "SELECT canonical_key FROM public.items "
                "WHERE id = $1::uuid AND user_id = $2::uuid",
                item_id, user_id,
            )
            if owner_row is None:
                raise error_response(404, "Item not found")
            canonical = owner_row["canonical_key"]
            if not canonical:
                # User item not linked to a catalog entry — no trend data possible
                return PriceTrendResponse(item_ref=item_id, period_days=days)

            # ── Warm-tier read path: merge price history across storage tiers ──
            # All three tiers are the SAME q-series (valuation_worker writes the
            # same q10/q50/q90 to price_history and price_predictions; the rollup
            # is the daily average of price_predictions). We collapse every tier
            # to one point per day so the merged line is continuous with no seam:
            #   Tier 1 (hot):    price_history            — last ~2 months, per-snapshot
            #   Tier 2 (rollup): price_prediction_daily   — up to its retention (180d)
            #   Tier 3 (cold):   S3 Parquet via warm_tier — older than Postgres retains
            # Priority hot > rollup > cold for any overlapping day.
            by_day: dict[str, TrendDataPoint] = {}

            def _point(date_str: str, q50, q10, q90) -> TrendDataPoint | None:
                if q50 is None:
                    return None
                return TrendDataPoint(
                    date=date_str,
                    q50=float(q50),
                    q10=float(q10) if q10 is not None else None,
                    q90=float(q90) if q90 is not None else None,
                )

            # Tier 2 (rollup) first — lowest of the two Postgres tiers, so hot
            # overwrites it below for any day both cover.
            rollup_rows = await conn.fetch(
                """
                SELECT day, q50, q10, q90
                FROM public.price_prediction_daily
                WHERE item_ref = $1
                  AND day >= (current_date - ($2 || ' days')::interval)
                ORDER BY day ASC
                """,
                canonical, str(days),
            )
            for r in rollup_rows:
                d = r["day"].strftime("%Y-%m-%d")
                p = _point(d, r["q50"], r["q10"], r["q90"])
                if p is not None:
                    by_day[d] = p

            # Tier 1 (hot) — highest priority; ASC order means the last write for
            # a day is the latest snapshot that day (daily collapse).
            hot_rows = await conn.fetch(
                """
                SELECT price_q50, price_q10, price_q90, snapshot_at
                FROM public.price_history
                WHERE item_ref = $1
                  AND snapshot_at >= now() - ($2 || ' days')::interval
                ORDER BY snapshot_at ASC
                """,
                canonical, str(days),
            )
            for r in hot_rows:
                d = r["snapshot_at"].strftime("%Y-%m-%d")
                p = _point(d, r["price_q50"], r["price_q10"], r["price_q90"])
                if p is not None:
                    by_day[d] = p

            # Tier 3 (cold, S3 Parquet via DuckDB) — only when the requested
            # window reaches before what hot+rollup already cover. As the rollup
            # fills toward its 180d retention, short windows stop hitting S3 at
            # all, so this is a genuinely cold/rare path at steady state.
            window_start = (datetime.now(timezone.utc) - timedelta(days=days)).date()
            covered_earliest = (
                datetime.strptime(min(by_day), "%Y-%m-%d").date()
                if by_day
                else datetime.now(timezone.utc).date()
            )
            if window_start < covered_earliest:
                try:
                    from app.lib.warm_tier import warm_tier_read

                    # `canonical` is a DB-resolved catalog key (items.canonical_key),
                    # never user input — but warm_tier concatenates `where` into SQL,
                    # so escape quotes defensively before crossing that boundary.
                    safe_ref = canonical.replace("'", "''")
                    # Sync DuckDB/S3 call → run off the event loop so it can't block
                    # other requests. Failure must never break the chart (degrade to
                    # the Postgres tiers we already have).
                    s3_rows = await asyncio.to_thread(
                        warm_tier_read,
                        "price_history",
                        year_from=window_start.year,
                        month_from=window_start.month,
                        year_to=covered_earliest.year,
                        month_to=covered_earliest.month,
                        where=(
                            f"item_ref = '{safe_ref}' "
                            f"AND snapshot_at >= (now() - INTERVAL '{int(days)} days')"
                        ),
                        select="price_q10, price_q50, price_q90, snapshot_at",
                        limit=100_000,
                    )
                    for r in s3_rows:
                        sa = r.get("snapshot_at")
                        d = sa.strftime("%Y-%m-%d") if hasattr(sa, "strftime") else str(sa)[:10]
                        p = _point(d, r.get("price_q50"), r.get("price_q10"), r.get("price_q90"))
                        if p is not None:
                            by_day.setdefault(d, p)  # never overwrite hot/rollup
                except Exception as exc:
                    logger.warning(
                        "[predict] warm-tier S3 read failed, using hot+rollup only: %s", exc
                    )

            data_points = [by_day[d] for d in sorted(by_day)]

            if not data_points:
                return PriceTrendResponse(item_ref=item_id, period_days=days)

            earliest_q50 = data_points[0].q50
            current_q50 = data_points[-1].q50

            # Calculate trend
            if earliest_q50 > 0:
                pct_change = round(((current_q50 - earliest_q50) / earliest_q50) * 100.0, 1)
            else:
                pct_change = 0.0

            if pct_change > 2.0:
                direction = "up"
            elif pct_change < -2.0:
                direction = "down"
            else:
                direction = "flat"

            return PriceTrendResponse(
                item_ref=item_id,
                period_days=days,
                data_points=data_points,
                direction=direction,
                pct_change=pct_change,
                current_q50=current_q50,
                earliest_q50=earliest_q50,
            )

    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("[predict] DB error for trend: %s", exc)
        return PriceTrendResponse(item_ref=item_id, period_days=days)
