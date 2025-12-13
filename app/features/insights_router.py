from __future__ import annotations

from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/insights", tags=["insights"])


class CategoryExposure(BaseModel):
    category: str
    share_pct: float
    risk_level: str = Field(..., description="low | medium | high")


class RareSetAlert(BaseModel):
    category: str
    item_name: str
    note: str


class TrendingItem(BaseModel):
    category: str
    item_name: str
    change_pct: float


class PersonalizedInsightsResponse(BaseModel):
    overexposed_categories: List[CategoryExposure]
    diversification_suggestions: List[str]
    rare_set_alerts: List[RareSetAlert]
    trending_items: List[TrendingItem]


class HomeWidgetResponse(BaseModel):
    collection_value: float
    today_change: float
    biggest_mover_name: str
    biggest_mover_change: float
    currency: str = "EUR"
    quickscan_shortcut: str = Field(
        "/quickscan-advanced/single", description="Relative path for one-tap scan"
    )


@router.get("/personalized", response_model=PersonalizedInsightsResponse)
async def get_personalized_insights() -> PersonalizedInsightsResponse:
    overexposed = [
        CategoryExposure(category="gunpla", share_pct=0.45, risk_level="medium"),
        CategoryExposure(category="mtg", share_pct=0.35, risk_level="high"),
    ]
    diversification = [
        "Consider adding more Warhammer minis to reduce TCG concentration.",
        "Your Gunpla exposure is high vs. Funko and Designer Toys.",
    ]
    rare_alerts = [
        RareSetAlert(
            category="gunpla",
            item_name="Wave 1 RX-78 (Launch)",
            note="Likely to retire in the next cycle.",
        )
    ]
    trending = [
        TrendingItem(
            category="designer-toys",
            item_name="Labubu-style collab drop",
            change_pct=0.32,
        )
    ]
    return PersonalizedInsightsResponse(
        overexposed_categories=overexposed,
        diversification_suggestions=diversification,
        rare_set_alerts=rare_alerts,
        trending_items=trending,
    )


@router.get("/home-widget", response_model=HomeWidgetResponse)
async def get_home_widget() -> HomeWidgetResponse:
    """
    'What's it worth today?' home widget snapshot.
    """
    return HomeWidgetResponse(
        collection_value=12450.0,
        today_change=+145.0,
        biggest_mover_name="Demo Charizard",
        biggest_mover_change=+12.5,
        currency="EUR",
    )
