from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/marketplace/trust2", tags=["marketplace-trust"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_db_pool():
    """Get database pool if available."""
    try:
        from app.db import get_pool
        return get_pool()
    except Exception as e:
        logger.debug(f"DB pool not available: {e}")
        return None


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
    """Return a stub seller reputation when no trust data is available."""
    return SellerReputation(
        user_id=user_id,
        score=0.0,
        badge="new",
        total_trades=0,
        disputes=0,
        dispute_rate=0.0,
    )


@router.get("/seller/{user_id}", response_model=SellerReputation)
async def get_seller_reputation(user_id: str):
    """
    Seller reputation endpoint.

    TODO: Wire up to a real trades / disputes table once the marketplace
    feature ships.  Until then returns an honest empty stub so the frontend
    knows no data is available yet (score=0, badge='new').
    """
    pool = _get_db_pool()
    if not pool:
        logger.info(f"[trust/seller] No DB pool -- returning empty stub for user_id={user_id}")
        return _empty_seller(user_id)

    try:
        async with pool.acquire() as conn:
            # Attempt to read from a future `marketplace_trades` or similar table.
            # For now, check if seller has market_hits as a rough proxy.
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) AS total_trades,
                    AVG(seller_score) AS avg_score
                FROM market_hits
                WHERE seller_score IS NOT NULL
                  AND url ILIKE '%' || $1 || '%'
                """,
                user_id,
            )

            if not row or row["total_trades"] == 0:
                return _empty_seller(user_id)

            trades = int(row["total_trades"])
            avg_score = float(row["avg_score"] or 0)

            # Map avg marketplace seller_score to a badge
            if avg_score >= 99:
                badge = "verified"
            elif avg_score >= 95:
                badge = "power"
            elif trades >= 10:
                badge = "regular"
            else:
                badge = "new"

            return SellerReputation(
                user_id=user_id,
                score=round(avg_score, 1),
                badge=badge,
                total_trades=trades,
                disputes=0,  # TODO: track disputes in dedicated table
                dispute_rate=0.0,
            )

    except Exception as e:
        logger.error(f"[trust/seller] DB error: {e}")
        return _empty_seller(user_id)


@router.get("/listing/{listing_id}", response_model=MarketplaceTrustSnapshot)
async def get_listing_trust_snapshot(listing_id: str):
    """
    Trust snapshot for a listing.

    Cross-references listing price against market_hits to detect outlier
    pricing (>2 std deviations) and low seller scores.
    """
    pool = _get_db_pool()
    if not pool:
        logger.info(f"[trust/listing] No DB pool -- returning empty stub for listing_id={listing_id}")
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

            seller = SellerReputation(
                user_id=f"{row['provider']}:{listing_id}",
                score=round(seller_score, 1),
                badge=badge,
                total_trades=0,  # TODO: aggregate across listings
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

    except Exception as e:
        logger.error(f"[trust/listing] DB error: {e}")
        return MarketplaceTrustSnapshot(
            seller=_empty_seller("unknown"),
            listing_flags=[],
        )
