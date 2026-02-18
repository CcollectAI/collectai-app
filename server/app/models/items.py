"""Item response models."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class ItemResponse(BaseModel):
    """Single item in the user's collection."""
    id: str = Field(..., description="Item UUID")
    title: str = Field(..., description="Item name/title")
    category: Optional[str] = Field(None, description="Category slug")
    condition: Optional[str] = Field(None, description="Condition grade")
    purchase_price: Optional[float] = Field(None, description="Purchase price in EUR")
    estimated_value: Optional[float] = Field(None, description="Current estimated value in EUR")
    image_url: Optional[str] = Field(None, description="Primary image URL")
    attributes: Optional[dict[str, Any]] = Field(None, description="Category-specific attributes")
    created_at: Optional[str] = Field(None, description="ISO 8601 creation timestamp")


class ItemListResponse(BaseModel):
    """GET /items response."""
    items: list[ItemResponse] = Field(default_factory=list)
    total: int = Field(0, description="Total items matching filter")
