"""
Risk flag computation and price outlier detection for deal desk offers.

Contains:
- _compute_trust_badge: determine trust badge from completed deals and rating
- compute_risk_flags: price outlier detection + seller trust scoring
- get_reputation_data: user reputation statistics
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def compute_trust_badge(completed: int, avg_stars: float) -> str:
    """Determine trust badge from completed deals and average rating."""
    if completed >= 50 and avg_stars >= 4.8:
        return "verified"
    if completed >= 20 and avg_stars >= 4.5:
        return "power"
    if completed >= 5:
        return "regular"
    return "new"


def compute_trust_score(avg_stars: float, completed: int) -> float:
    """Compute trust score: avg_stars normalized to 0-100, boosted by trade count."""
    if completed <= 0:
        return 0.0
    return min(100.0, (avg_stars / 5.0) * 80 + min(20.0, completed * 2))


async def get_reputation_data(conn: Any, target_user_id: str) -> dict[str, Any]:
    """Fetch and compute reputation data for a user from the database."""
    row = await conn.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE o.status = 'completed') AS completed_deals,
            COALESCE(AVG(dr.stars), 0) AS avg_stars,
            COUNT(dr.id) AS total_ratings
        FROM offers o
        LEFT JOIN deal_ratings dr ON dr.offer_id = o.id AND dr.rated_id = $1::uuid
        WHERE o.seller_id = $1::uuid OR o.buyer_id = $1::uuid
        """,
        target_user_id,
    )

    completed = int(row["completed_deals"]) if row else 0
    avg_stars = float(row["avg_stars"]) if row and row["avg_stars"] else 0.0
    total_ratings = int(row["total_ratings"]) if row else 0

    trust_score = compute_trust_score(avg_stars, completed)
    badge = compute_trust_badge(completed, avg_stars)

    # Count disputes (cancelled/declined)
    dispute_count = 0
    if completed > 0:
        dispute_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM offers
            WHERE (seller_id = $1::uuid OR buyer_id = $1::uuid)
              AND status IN ('cancelled', 'declined')
            """,
            target_user_id,
        ) or 0

    dispute_rate = dispute_count / (completed + dispute_count) if (completed + dispute_count) > 0 else 0.0

    return {
        "user_id": target_user_id,
        "avg_stars": round(avg_stars, 2),
        "total_ratings": total_ratings,
        "completed_deals": completed,
        "trust_score": round(trust_score, 1),
        "badge": badge,
        "disputes": dispute_count,
        "dispute_rate": round(dispute_rate, 4),
    }


async def compute_risk_flags(conn: Any, offer_id: str, user_id: str) -> dict[str, Any]:
    """
    Risk assessment for an offer — detects price outliers and low seller scores.

    Returns dict with offer_id, risk_flags list, seller_trust_score, and seller_badge.
    """
    # 2026-04-22: rewrote to match canonical schema — offers has no item_id
    # (it has listing_id) nor current_price (it's amount) nor currency
    # (currency is on listings). Join provides item_id + currency.
    offer = await conn.fetchrow(
        """
        SELECT o.id, l.item_id, o.amount AS current_price, l.currency,
               o.seller_id, o.buyer_id
        FROM public.offers o
        JOIN public.listings l ON l.id = o.listing_id
        WHERE o.id = $1::uuid AND (o.seller_id = $2::uuid OR o.buyer_id = $2::uuid)
        """,
        offer_id, user_id,
    )
    if not offer:
        return None  # type: ignore[return-value]

    flags: list[dict[str, str]] = []
    offer_price = float(offer["current_price"]) if offer["current_price"] else None

    # Price outlier check: compare offer price to market_hits for the item.
    # items.normalized_key was renamed to canonical_key; market_hits canonical
    # join column is item_ref (= `{category}:{key}`), not normalized_key.
    if offer_price and offer["item_id"]:
        item_row = await conn.fetchrow(
            "SELECT canonical_key FROM public.items WHERE id = $1::uuid",
            str(offer["item_id"]),
        )
        if item_row and item_row["canonical_key"]:
            avg_row = await conn.fetchrow(
                """
                SELECT AVG(price_eur) AS avg_price,
                       STDDEV_POP(price_eur) AS stddev_price,
                       COUNT(*) AS sample_count
                FROM public.market_hits
                WHERE item_ref = $1 AND price_eur IS NOT NULL
                  AND (is_listing IS NOT TRUE)
                  -- Partition prune: 180d window — risk flags compare
                  -- offer prices against recent sold distribution.
                  -- Older comps drift in value and would skew the
                  -- mean/stddev anyway.
                  AND seen_at > now() - interval '180 days'
                """,
                item_row["canonical_key"],
            )
            if avg_row and avg_row["avg_price"] and avg_row["stddev_price"]:
                avg_price = float(avg_row["avg_price"])
                stddev = float(avg_row["stddev_price"])
                if stddev > 0 and abs(offer_price - avg_price) > 2 * stddev:
                    flags.append({
                        "risk_level": "high" if abs(offer_price - avg_price) > 3 * stddev else "medium",
                        "reason": f"Price ({offer_price:.2f}) is >2 std deviations from avg ({avg_price:.2f})",
                    })

    # Seller trust check
    seller_id = str(offer["seller_id"])
    seller_completed = await conn.fetchval(
        "SELECT COUNT(*) FROM offers WHERE seller_id = $1::uuid AND status = 'completed'",
        seller_id,
    ) or 0
    seller_avg = await conn.fetchval(
        "SELECT COALESCE(AVG(stars), 0) FROM deal_ratings WHERE rated_id = $1::uuid",
        seller_id,
    ) or 0.0
    seller_score = compute_trust_score(float(seller_avg), seller_completed)

    if seller_completed > 0 and seller_score < 60:
        flags.append({
            "risk_level": "medium",
            "reason": f"Seller trust score below threshold ({seller_score:.0f}/100)",
        })

    if seller_completed == 0:
        flags.append({
            "risk_level": "low",
            "reason": "New seller — no completed trades yet",
        })

    return {
        "offer_id": offer_id,
        "risk_flags": flags,
        "seller_trust_score": round(seller_score, 1),
        "seller_badge": compute_trust_badge(seller_completed, float(seller_avg)),
    }
