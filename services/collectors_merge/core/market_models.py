from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MarketHit(BaseModel):
    provider: str
    listing_id: str
    title: str | None = None
    price: float | None = None
    currency: str | None = None
    shipping: float | None = None
    condition: str | None = None
    graded: bool | None = None
    ended_at: str | None = None
    url: str | None = None
    seller_score: float | None = None
    features_json: dict[str, Any] = Field(default_factory=dict)
    normalized_key: str | None = None
