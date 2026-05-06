"""On-demand enrichment endpoint.

POST /enrich/on-demand — fires one paid-scraper call for the given item
to fetch fresh comps. Cached + spend-gated; safe to call from item-detail
screens whenever fresh data would help.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.agents.on_demand_enrich import enrich_item
from app.auth import get_current_user_id
from app.lib.db_helpers import get_db_pool

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/enrich", tags=["Enrich"])

# Per-day caps to prevent abuse / runaway spend per user
RATE_LIMITS_BY_TIER: Dict[str, int] = {"free": 5, "pro": 50, "premium": 200}

# Categories where on-demand is most valuable. Outside this list we still
# allow it but the FE shouldn't surface the prompt aggressively.
ON_DEMAND_PRIORITY_CATEGORIES = {
    "watches", "whiskey", "ghibli", "pens", "pop_fandom",
    "action_figures", "keycaps", "blind_box", "taylor_swift",
    "art", "vintage_cameras", "fragrances",
}


class EnrichRequest(BaseModel):
    item_ref: str = Field(..., min_length=3, max_length=200,
                          description="Canonical {category}:{key} item ref")
    query: str = Field(..., min_length=2, max_length=200,
                       description="Search query (usually item title)")
    category: str = Field(..., min_length=2, max_length=50)
    force: bool = Field(default=False,
                        description="Bypass cache (admin/debug only)")


class EnrichResponse(BaseModel):
    skipped: bool
    reason: str
    hits_persisted: int
    cost_cents: int


async def _check_per_user_daily_cap(conn, user_id: str) -> tuple[int, int]:
    """Enforce the documented per-tier daily caps (5/50/200 by plan).

    Pre-2026-05-02 only a global 5000/day cap was enforced — a single
    Pro user could lock the whole org out. Now: count this user's
    rows in `on_demand_lookups_audit` over the last 24h and reject if
    above the tier cap.

    Returns (used, cap) so the caller can include the headroom in
    response headers / FE quota indicators if it wants to.
    """
    from app.subscription import get_user_plan
    plan = await get_user_plan(user_id)
    cap = int(RATE_LIMITS_BY_TIER.get(plan, RATE_LIMITS_BY_TIER["free"]))
    used = await conn.fetchval(
        """
        SELECT COUNT(*) FROM public.on_demand_lookups_audit
        WHERE user_id = $1::uuid
          AND fetched_at > now() - interval '1 day'
        """,
        user_id,
    ) or 0
    if used >= cap:
        raise HTTPException(
            429,
            f"Daily on-demand quota exceeded ({used}/{cap} for {plan} tier). "
            f"Resets in 24h.",
        )
    return used, cap


@router.post(
    "/on-demand",
    response_model=EnrichResponse,
    summary="Fetch fresh comps for an item via paid scraper (cached + budget-gated)",
)
async def enrich_on_demand(
    payload: EnrichRequest,
    user_id: str = Depends(get_current_user_id),
    pool=Depends(get_db_pool),
) -> EnrichResponse:
    async with pool.acquire() as conn:
        # force=true is admin-only. Until we have a role check on user_id,
        # silently ignore force from unauthenticated callers (treat as false).
        if payload.force:
            payload.force = False  # disabled until admin-role wired

        await _check_per_user_daily_cap(conn, user_id)

        result = await enrich_item(
            conn,
            item_ref=payload.item_ref,
            query=payload.query,
            category=payload.category,
            force=payload.force,
        )

        # Audit row — count it ONLY when the call did real work
        # (cache hits don't count against the tier cap, since they're
        # free and we want to encourage cache reuse).
        if not result.get("skipped"):
            try:
                await conn.execute(
                    """
                    INSERT INTO public.on_demand_lookups_audit
                        (user_id, item_ref, cost_cents, provider)
                    VALUES ($1::uuid, $2, $3, $4)
                    """,
                    user_id,
                    payload.item_ref,
                    int(result.get("cost_cents", 0)),
                    result.get("provider", "unknown"),
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("[enrich] audit insert failed: %s", e)

        return EnrichResponse(**result)
