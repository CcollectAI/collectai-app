from __future__ import annotations

import logging
from typing import List
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.errors import error_response
from app.lib.db_helpers import get_db_pool
from app.lib.error_codes import ErrorCode

router = APIRouter(prefix="/marketplace/trust2", tags=["marketplace-trust"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response models (unchanged)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

def _empty_seller(user_id: str) -> SellerReputation:
    """Return a default seller reputation when no trust data is available."""
    return SellerReputation(
        user_id=user_id,
        score=0.0,
        badge="new",
        total_trades=0,
        disputes=0,
        dispute_rate=0.0,
    )


def _compute_badge(completed: int, avg_stars: float) -> str:
    """Determine trust badge from completed deals and average rating."""
    if completed >= 50 and avg_stars >= 4.8:
        return "verified"
    elif completed >= 20 and avg_stars >= 4.5:
        return "power"
    elif completed >= 5:
        return "regular"
    return "new"


@router.get("/seller/{user_id}", response_model=SellerReputation)
async def get_seller_reputation(user_id: str, _caller: str = Depends(get_current_user_id)):
    """
    Seller reputation endpoint.

    Computes trust score from completed P2P offers and deal_ratings.
    Falls back to empty stub if no trade data exists.
    """
    try:
        UUID(user_id)
    except ValueError:
        raise error_response(400, "Invalid user_id format", code=ErrorCode.VALIDATION_ERROR)

    pool = get_db_pool()
    if not pool:
        return _empty_seller(user_id)

    try:
        async with pool.acquire() as conn:
            # Query real offers + ratings for this user as seller
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) FILTER (WHERE o.status = 'completed') AS completed_deals,
                    COUNT(*) FILTER (WHERE o.status IN ('completed', 'accepted', 'proposed', 'countered')) AS total_deals,
                    COALESCE(AVG(dr.stars), 0) AS avg_stars,
                    COUNT(dr.id) AS total_ratings
                FROM offers o
                LEFT JOIN deal_ratings dr ON dr.offer_id = o.id AND dr.rated_id = $1::uuid
                WHERE o.seller_id = $1::uuid OR o.buyer_id = $1::uuid
                """,
                user_id,
            )

            if not row or row["completed_deals"] == 0:
                return _empty_seller(user_id)

            completed = int(row["completed_deals"])
            avg_stars = float(row["avg_stars"])
            total_ratings = int(row["total_ratings"])

            # Trust score: weighted blend of completion rate and rating
            # Base: avg_stars normalized to 0-100, boosted by completion count
            score = min(100.0, (avg_stars / 5.0) * 80 + min(20.0, completed * 2))
            badge = _compute_badge(completed, avg_stars)

            # Count disputed/cancelled offers as disputes
            dispute_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM offers
                WHERE (seller_id = $1::uuid OR buyer_id = $1::uuid)
                  AND status IN ('cancelled', 'declined')
                """,
                user_id,
            ) or 0

            dispute_rate = dispute_count / (completed + dispute_count) if (completed + dispute_count) > 0 else 0.0

            return SellerReputation(
                user_id=user_id,
                score=round(score, 1),
                badge=badge,
                total_trades=completed,
                disputes=dispute_count,
                dispute_rate=round(dispute_rate, 4),
            )

    except asyncpg.PostgresError as e:
        logger.error("[trust/seller] DB error: %s", e)
        return _empty_seller(user_id)


@router.get("/listing/{listing_id}", response_model=MarketplaceTrustSnapshot)
async def get_listing_trust_snapshot(listing_id: str, _caller: str = Depends(get_current_user_id)):
    """
    Trust snapshot for a listing.

    Cross-references listing price against market_hits to detect outlier
    pricing (>2 std deviations) and low seller scores.
    """
    pool = get_db_pool()
    if not pool:
        logger.info("[trust/listing] No DB pool -- returning empty stub for listing_id=%s", listing_id)
        return MarketplaceTrustSnapshot(
            seller=_empty_seller("unknown"),
            listing_flags=[],
        )

    try:
        async with pool.acquire() as conn:
            # Look up listing in market_hits
            row = await conn.fetchrow(
                """
                SELECT
                    provider,
                    listing_id,
                    title,
                    price,
                    currency,
                    seller_score,
                    normalized_key,
                    created_at
                FROM market_hits
                WHERE listing_id = $1
                LIMIT 1
                """,
                listing_id,
            )

            if not row:
                return MarketplaceTrustSnapshot(
                    seller=_empty_seller("unknown"),
                    listing_flags=[],
                )

            # Build seller stub from this listing's seller_score
            seller_score = float(row["seller_score"]) if row["seller_score"] else 0.0
            badge = "new"
            if seller_score >= 99:
                badge = "verified"
            elif seller_score >= 95:
                badge = "power"
            elif seller_score >= 80:
                badge = "regular"

            # TODO: Replace with real trades table once P2P marketplace ships
            trade_count = 0
            try:
                trade_row = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM market_hits
                    WHERE provider = $1 AND seller_score IS NOT NULL
                    """,
                    row["provider"],
                )
                trade_count = trade_row or 0
            except Exception:
                pass

            seller = SellerReputation(
                user_id=f"{row['provider']}:{listing_id}",
                score=round(seller_score, 1),
                badge=badge,
                total_trades=trade_count,
                disputes=0,
                dispute_rate=0.0,
            )

            # ---- Price outlier check ----
            flags: List[ListingRiskFlag] = []
            if row["normalized_key"] and row["price"]:
                avg_row = await conn.fetchrow(
                    """
                    SELECT
                        AVG(price)                   AS avg_price,
                        STDDEV_POP(price)            AS stddev_price,
                        COUNT(*)                     AS sample_count
                    FROM market_hits
                    WHERE normalized_key = $1
                      AND price IS NOT NULL
                    """,
                    row["normalized_key"],
                )
                if avg_row and avg_row["avg_price"] and avg_row["stddev_price"]:
                    avg_price = float(avg_row["avg_price"])
                    stddev = float(avg_row["stddev_price"])
                    listing_price = float(row["price"])
                    reasons: List[str] = []

                    if stddev > 0 and abs(listing_price - avg_price) > 2 * stddev:
                        reasons.append(
                            f"Price ({listing_price:.2f}) is >2 std deviations from "
                            f"avg ({avg_price:.2f})"
                        )
                    if seller_score < 80:
                        reasons.append(f"Seller score below threshold ({seller_score:.0f})")

                    if reasons:
                        risk = "high" if len(reasons) >= 2 else "medium"
                        flags.append(
                            ListingRiskFlag(
                                listing_id=listing_id,
                                risk_level=risk,
                                reasons=reasons,
                            )
                        )

            return MarketplaceTrustSnapshot(seller=seller, listing_flags=flags)

    except asyncpg.PostgresError as e:
        logger.error("[trust/listing] DB error: %s", e)
        return MarketplaceTrustSnapshot(
            seller=_empty_seller("unknown"),
            listing_flags=[],
        )
