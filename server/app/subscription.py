"""
Subscription gating — FastAPI dependency for checking feature access.

Usage in routers:
    from app.subscription import require_plan

    @router.post("/some-premium-feature")
    async def premium_feature(
        user_id: str = Depends(get_current_user_id),
        _plan: str = Depends(require_plan("pro")),
    ):
        ...
"""

from __future__ import annotations

import logging

from fastapi import Depends

from app.auth import get_current_user_id
from app.config import DB_ENABLED, DEV_MODE
from app.db import get_pool
from app.errors import error_response

_log = logging.getLogger("collectai.subscription")

# Plan hierarchy: free < pro < premium
_PLAN_RANK = {"free": 0, "pro": 1, "premium": 2}


async def get_user_plan(user_id: str) -> str:
    """Return the user's current subscription plan ('free', 'pro', or 'premium')."""
    if DEV_MODE and not DB_ENABLED:
        return "premium"  # Dev mode gets full access

    if not DB_ENABLED:
        return "free"

    pool = get_pool()
    if pool is None:
        return "free"

    row = await pool.fetchrow(
        "SELECT plan FROM subscriptions WHERE user_id = $1 AND status IN ('active', 'trialing')",
        user_id,
    )
    return row["plan"] if row else "free"


async def get_user_mandate_limit(user_id: str) -> int:
    """Return the maximum number of mandates the user can have."""
    from app.routes.billing_router import PLAN_LIMITS

    plan = await get_user_plan(user_id)
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])["max_mandates"]


def require_plan(min_plan: str):
    """FastAPI dependency that rejects requests if the user's plan is below min_plan.

    Usage: Depends(require_plan("pro"))
    """
    min_rank = _PLAN_RANK.get(min_plan, 0)

    async def _check(user_id: str = Depends(get_current_user_id)) -> str:
        plan = await get_user_plan(user_id)
        rank = _PLAN_RANK.get(plan, 0)
        if rank < min_rank:
            raise error_response(
                403,
                f"This feature requires {min_plan} plan or higher. "
                f"Your current plan: {plan}.",
                code="PLAN_REQUIRED",
            )
        return plan

    return _check
