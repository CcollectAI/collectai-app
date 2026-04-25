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


async def _check_global_rate_limit(conn) -> None:
    """Raise 429 if global daily on-demand cap is hit. Per-user limits
    will land in a follow-up once we wire user-scoped tracking; for v1
    a global daily cap is enough to prevent runaway spend."""
    used = await conn.fetchval(
        """
        SELECT COUNT(*) FROM public.on_demand_lookups
        WHERE last_fetched_at > now() - interval '1 day'
        """
    ) or 0
    cap = int(RATE_LIMITS_BY_TIER.get("free", 5)) * 1000  # 5,000/day global
    if used >= cap:
        raise HTTPException(429, "Daily on-demand quota exceeded — try again tomorrow")


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

        await _check_global_rate_limit(conn)

        result = await enrich_item(
            conn,
            item_ref=payload.item_ref,
            query=payload.query,
            category=payload.category,
            force=payload.force,
        )
        return EnrichResponse(**result)
