"""
Seed-user management endpoints.

Endpoints:
    POST   /ops/seed-users  — Create 8 beta-test personas (idempotent)
    DELETE /ops/seed-users  — Remove all seed users (is_seed metadata flag)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.auth import require_ops_key

router = APIRouter(prefix="/ops", tags=["ops"])
_log = logging.getLogger("collectai.seed_router")


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class SeedUserEntry(BaseModel):
    email: str
    handle: str
    user_id: str | None = None
    skipped: bool = False


class SeedResponse(BaseModel):
    success: bool
    created: int = 0
    skipped: int = 0
    total: int = 0
    users: list[SeedUserEntry] = []
    dry_run: bool = False
    error: str | None = None


class CleanupResponse(BaseModel):
    success: bool
    deleted: int = 0
    message: str = ""


# ---------------------------------------------------------------------------
# POST /ops/seed-users
# ---------------------------------------------------------------------------

@router.post("/seed-users", response_model=SeedResponse)
async def seed_users(
    dry_run: bool = Query(False, description="Preview without creating anything"),
    _: bool = Depends(require_ops_key),
):
    """Create 8 beta-test user personas with collections.

    Idempotent: existing users are skipped.
    """
    from pipelines.seed_beta_users import seed_users as do_seed

    result = await do_seed(dry_run=dry_run)
    status_code = 200 if result.get("success") else 500
    return SeedResponse(**{k: v for k, v in result.items() if k in SeedResponse.model_fields})


# ---------------------------------------------------------------------------
# DELETE /ops/seed-users
# ---------------------------------------------------------------------------

@router.delete("/seed-users", response_model=CleanupResponse)
async def delete_seed_users(
    _: bool = Depends(require_ops_key),
):
    """Remove all seed users (identified by ``user_metadata.is_seed = true``).

    Only touches seed data — never deletes real user accounts.
    """
    from pipelines.seed_beta_users import cleanup_seed_users

    result = await cleanup_seed_users()
    return CleanupResponse(**{k: v for k, v in result.items() if k in CleanupResponse.model_fields})
