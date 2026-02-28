"""
Price prediction evidence router.

Exposes GET /predict/evidence/{item_id} for the PriceExplanationSheet
in the frontend. Returns the latest price prediction with explanation
and market evidence.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.errors import error_response
from app.db import db_configured, get_conn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predict", tags=["predict"])


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

            # Fetch latest prediction
            pred = await conn.fetchrow(
                """
                SELECT q10, q50, q90, conf_score, explanation,
                       evidence_summary, evidence_hit_ids, asof
                FROM public.price_predictions
                WHERE item_id = $1::uuid
                ORDER BY asof DESC
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

            # Record demand signal (best-effort)
            try:
                from app.features.data_moat import record_demand_signal
                await record_demand_signal(
                    signal_type="item_viewed",
                    item_key=item_id,
                    user_id=user_id,
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
            # Verify item ownership
            owner_check = await conn.fetchval(
                "SELECT 1 FROM public.items WHERE id = $1::uuid AND user_id = $2::uuid",
                item_id, user_id,
            )
            if owner_check is None:
                raise error_response(404, "Item not found")

            # Fetch price history snapshots
            rows = await conn.fetch(
                """
                SELECT price_q50, price_q10, price_q90, snapshot_at
                FROM public.price_history
                WHERE item_ref = $1
                  AND snapshot_at >= now() - ($2 || ' days')::interval
                ORDER BY snapshot_at ASC
                """,
                item_id, str(days),
            )

            if not rows:
                return PriceTrendResponse(item_ref=item_id, period_days=days)

            data_points = [
                TrendDataPoint(
                    date=row["snapshot_at"].strftime("%Y-%m-%d"),
                    q50=float(row["price_q50"]),
                    q10=float(row["price_q10"]) if row.get("price_q10") is not None else None,
                    q90=float(row["price_q90"]) if row.get("price_q90") is not None else None,
                )
                for row in rows
            ]

            earliest_q50 = float(rows[0]["price_q50"])
            current_q50 = float(rows[-1]["price_q50"])

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
