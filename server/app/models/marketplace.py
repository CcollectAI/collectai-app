"""Marketplace response models."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class MarketHit(BaseModel):
    """Single marketplace listing result."""
    provider: str = Field(..., description="Marketplace source (ebay, tcgplayer, cardmarket)")
    title: str = Field(..., description="Listing title")
    price: Optional[float] = Field(None, description="Price in EUR")
    currency: str = Field("EUR", description="Price currency")
    url: str = Field("", description="Listing URL")
    image_url: Optional[str] = Field(None, description="Thumbnail image URL")
    condition: Optional[str] = Field(None, description="Item condition")
    seller: Optional[str] = Field(None, description="Seller name")
    seller_score: Optional[float] = Field(None, description="Seller reputation score")
    listing_id: Optional[str] = Field(None, description="Marketplace-specific listing ID")


class MarketplaceSearchResponse(BaseModel):
    """GET /marketplace/search response."""
    query: str = Field(..., description="Original search query")
    hits: list[MarketHit] = Field(default_factory=list, description="Marketplace listings")
    total: int = Field(0, description="Total results found")
    providers_queried: list[str] = Field(default_factory=list, description="Providers that were queried")
