from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/analytics", tags=["analytics"])


class TimeseriesPoint(BaseModel):
    ts: datetime
    value: float


class ItemTrendResponse(BaseModel):
    item_id: str
    currency: str = "EUR"
    history: List[TimeseriesPoint]
    model_confidence: Optional[List[TimeseriesPoint]] = None


class CollectionTrendResponse(BaseModel):
    currency: str = "EUR"
    total_history: List[TimeseriesPoint]
    dca_history: Optional[List[TimeseriesPoint]] = None
    per_category_gain_loss: dict = Field(default_factory=dict)


class CategoryDeepDiveResponse(BaseModel):
    category: str
    currency: str = "EUR"
    avg_market_price: float
    value_distribution: List[TimeseriesPoint]
    volume_trend: List[TimeseriesPoint]
    top_traded_items: List[dict]
    top_movers: List[dict]


def _demo_series(days: int = 30, base: float = 100.0) -> List[TimeseriesPoint]:
    now = datetime.utcnow()
    return [
        TimeseriesPoint(ts=now - timedelta(days=i), value=base + i * 2.5)
        for i in reversed(range(days))
    ]


@router.get("/collection/trends", response_model=CollectionTrendResponse)
async def get_collection_trends(
    days: int = Query(30, ge=1, le=365),
    currency: str = Query("EUR"),
):
    """
    Collection trend graph:
    - total value over time
    - DCA vs market
    - per-category gain/loss
    """
    history = _demo_series(days=days, base=1200.0)
    dca = _demo_series(days=days, base=900.0)
    per_category = {
        "mtg": {"gain_pct": 0.12},
        "gunpla": {"gain_pct": 0.07},
        "funko": {"gain_pct": -0.03},
    }
    return CollectionTrendResponse(
        currency=currency,
        total_history=history,
        dca_history=dca,
        per_category_gain_loss=per_category,
    )


@router.get("/items/{item_id}/trends", response_model=ItemTrendResponse)
async def get_item_trends(
    item_id: str,
    days: int = Query(30, ge=1, le=365),
    currency: str = Query("EUR"),
):
    """
    Item-level trend for detail screen:
    - historical predicted value
    - model confidence over time
    """
    history = _demo_series(days=days, base=80.0)
    confidence = _demo_series(days=days, base=0.8)
    return ItemTrendResponse(
        item_id=item_id,
        currency=currency,
        history=history,
        model_confidence=confidence,
    )


@router.get("/categories/{category}/deep-dive", response_model=CategoryDeepDiveResponse)
async def get_category_deep_dive(
    category: str,
    days: int = Query(30, ge=7, le=365),
    currency: str = Query("EUR"),
):
    """
    Category deep dive:
    - avg market price
    - value distribution
    - volume trends
    - most-traded items
    - top movers
    """
    value_distribution = _demo_series(days=days, base=50.0)
    volume_trend = _demo_series(days=days, base=20.0)

    top_traded = [
        {"item_id": "demo-1", "name": "Sample Grail #1", "trades": 42},
        {"item_id": "demo-2", "name": "Sample Grail #2", "trades": 31},
    ]

    top_movers = [
        {"item_id": "demo-3", "name": "Rising Gunpla", "change_pct": 0.25},
        {"item_id": "demo-4", "name": "Falling Funko", "change_pct": -0.18},
    ]

    return CategoryDeepDiveResponse(
        category=category,
        currency=currency,
        avg_market_price=123.45,
        value_distribution=value_distribution,
        volume_trend=volume_trend,
        top_traded_items=top_traded,
        top_movers=top_movers,
    )
