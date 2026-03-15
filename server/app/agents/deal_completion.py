"""
Shipping, delivery confirmation, and rating logic for deal desk.

Contains the business logic for:
- mark_shipped: seller marks offer as shipped with optional tracking
- complete_deal: buyer confirms delivery, rates, awards XP, records ground truth
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.errors import error_response
from app.lib.error_codes import ErrorCode

logger = logging.getLogger(__name__)


async def execute_ship(conn: Any, offer_id: str, user_id: str, tracking_info: str | None) -> dict[str, Any]:
    """
    Mark an offer as shipped.  Caller must have already validated the offer_id UUID.

    Returns parsed RPC response dict.
    Raises error_response on permission/state errors.
    """
    # Pre-flight ownership check: only seller can mark shipped
    is_seller = await conn.fetchval(
        "SELECT 1 FROM offers WHERE id = $1::uuid AND seller_id = $2::uuid",
        offer_id, user_id,
    )
    if not is_seller:
        raise error_response(403, "Only the seller can mark as shipped", code=ErrorCode.FORBIDDEN)

    result = await conn.fetchval(
        "SELECT rpc_mark_shipped_v1($1::uuid, $2::text)",
        offer_id, tracking_info,
    )

    try:
        data = json.loads(result) if isinstance(result, str) else result
    except (json.JSONDecodeError, TypeError) as e:
        logger.error("Invalid JSON from RPC: %s", e)
        raise error_response(500, "Invalid response from database", code=ErrorCode.INTERNAL_ERROR)
    return data


async def execute_complete(
    conn: Any,
    pool: Any,
    offer_id: str,
    user_id: str,
    stars: int,
    comment: str | None,
) -> dict[str, Any]:
    """
    Complete a deal: confirm delivery, leave rating, award XP, record ground truth.

    The conn should already be inside a transaction for XP + completion atomicity.
    pool is needed for the ground truth recording (separate connection, best-effort).

    Returns parsed RPC response dict.
    Raises error_response on permission/state errors.
    """
    # Pre-flight ownership check: only buyer can complete
    is_buyer = await conn.fetchval(
        "SELECT 1 FROM offers WHERE id = $1::uuid AND buyer_id = $2::uuid",
        offer_id, user_id,
    )
    if not is_buyer:
        raise error_response(403, "Only the buyer can complete the deal", code=ErrorCode.FORBIDDEN)

    result = await conn.fetchval(
        "SELECT rpc_complete_deal_v1($1::uuid, $2::smallint, $3::text)",
        offer_id, stars, comment,
    )

    # Award XP for completing a deal (inside the same transaction)
    try:
        from app.features.gamification_router import record_activity_xp
        deal_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM offers
            WHERE (seller_id = $1::uuid OR buyer_id = $1::uuid)
              AND status = 'completed'
            """,
            user_id,
        )
        achievement_checks = []
        deal_milestones = [
            (1, "trader_1"), (5, "trader_5"),
            (10, "trader_10"), (25, "trader_25"),
        ]
        for threshold, ach_id in deal_milestones:
            if deal_count >= threshold:
                achievement_checks.append((ach_id, deal_count))
        await record_activity_xp(conn, user_id, 25, achievement_checks or None)
    except Exception:
        logger.debug("[deal_desk] XP award failed for deal completion (best-effort)")

    try:
        data = json.loads(result) if isinstance(result, str) else result
    except (json.JSONDecodeError, TypeError) as e:
        logger.error("Invalid JSON from RPC: %s", e)
        raise error_response(500, "Invalid response from database", code=ErrorCode.INTERNAL_ERROR)

    # Record ground truth for data moat feedback loop (best-effort, outside transaction)
    try:
        async with pool.acquire() as conn2:
            offer_row = await conn2.fetchrow(
                "SELECT item_id, current_price, currency FROM offers WHERE id = $1::uuid",
                offer_id,
            )
        if offer_row:
            from app.features.data_moat import record_price_ground_truth
            await record_price_ground_truth(
                item_id=str(offer_row["item_id"]),
                actual_price=float(offer_row["current_price"]),
                currency=offer_row["currency"] or "EUR",
                source="deal_desk",
            )
    except Exception:
        logger.debug("[deal_desk] Ground truth recording failed (best-effort)")

    return data
