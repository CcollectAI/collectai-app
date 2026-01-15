from __future__ import annotations

from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/marketplace/trust2", tags=["marketplace-trust"])


class SellerReputation(BaseModel):
    user_id: str
    score: float = Field(..., description="0-100 trust score")
    badge: str = Field(..., description="new | regular | power | verified")
    total_trades: int
    disputes: int
    dispute_rate: float


class ListingRiskFlag(BaseModel):
    listing_id: str
    risk_level: str = Field(..., description="low | medium | high")
    reasons: List[str]


class MarketplaceTrustSnapshot(BaseModel):
    seller: SellerReputation
    listing_flags: List[ListingRiskFlag] = Field(default_factory=list)


@router.get("/seller/{user_id}", response_model=SellerReputation)
async def get_seller_reputation(user_id: str):
    """
    Simple reputation endpoint, UI can show:
    - badge
    - score
    - total trades / disputes
    """
    # Demo logic; later replace with real stats from DB
    if user_id.startswith("pro"):
        badge = "power"
        score = 92.0
        trades = 80
        disputes = 1
    else:
        badge = "regular"
        score = 78.0
        trades = 37
        disputes = 1

    return SellerReputation(
        user_id=user_id,
        score=score,
        badge=badge,
        total_trades=trades,
        disputes=disputes,
        dispute_rate=disputes / trades if trades else 0.0,
    )


@router.get("/listing/{listing_id}", response_model=MarketplaceTrustSnapshot)
async def get_listing_trust_snapshot(listing_id: str):
    """
    Trust snapshot for a listing.

    Combine later with your marketplace-intel outputs.
    """
    seller = SellerReputation(
        user_id="demo-seller",
        score=88.0,
        badge="verified",
        total_trades=120,
        disputes=2,
        dispute_rate=2 / 120,
    )
    flags = [
        ListingRiskFlag(
            listing_id=listing_id,
            risk_level="low",
            reasons=["Seller verified", "Price within typical range"],
        )
    ]
    return MarketplaceTrustSnapshot(seller=seller, listing_flags=flags)
