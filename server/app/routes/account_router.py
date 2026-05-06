"""
Account management router.

Endpoints:
- DELETE /account - Request account deletion (soft-delete + Supabase auth removal)
"""

from __future__ import annotations

import asyncio
import logging

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from fastapi import Query

from app.auth import get_current_user_id
from app.errors import error_response
from app.lib.db_helpers import get_db_pool
from app.rate_limit import per_user_rate_limit

router = APIRouter(prefix="/account", tags=["Account"])
logger = logging.getLogger(__name__)

# Mandatory confirmation phrase to prevent accidental account deletion.
# Pre-2026-05-03 the endpoint deleted on the bare DELETE call with no body
# check — a single accidental client request wiped the account.
_DELETE_CONFIRM_PHRASE = "DELETE_MY_ACCOUNT"


def _get_supabase_admin():
    """Get Supabase admin client for auth operations."""
    try:
        from app.config import SUPABASE_URL, SUPABASE_SERVICE_KEY
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            return None
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    except (ImportError, Exception) as e:
        logger.debug("Supabase admin client not available: %s", e)
        return None


# Per-user tables only. category_items + price_predictions are global
# catalog data with no user_id column. market_hits is anonymous crawl
# data (no index on user_id; DELETE scans all monthly partitions and
# times out — leave it).
_ALLOWED_TABLES = (
    "mandate_deals",
    "purchase_mandates",
    "alert_trigger_history",
    "user_price_alerts",
    "item_provenance_events",
    "watchlist",
    "user_settings",
    "user_category_follows",
    "event_attendees",
)


async def _do_account_delete(conn: asyncpg.Connection, user_id: str) -> None:
    async with conn.transaction():
        # Cap any single statement so a stray row-lock or saturated IO
        # can't stall the whole HTTP request indefinitely. Higher than
        # 5s because bake's market_hits readers can saturate disk IO.
        await conn.execute("SET LOCAL statement_timeout = '15s'")

        for table in _ALLOWED_TABLES:
            assert table.isidentifier(), f"Invalid table name: {table}"
            try:
                await conn.execute(
                    f'DELETE FROM "{table}" WHERE user_id = $1',
                    user_id,
                )
            except asyncpg.UndefinedTableError:
                pass

        try:
            await conn.execute("DELETE FROM profiles WHERE id = $1", user_id)
        except asyncpg.UndefinedTableError:
            pass

        try:
            await conn.execute(
                "DELETE FROM user_public_profiles WHERE user_id = $1",
                user_id,
            )
        except asyncpg.UndefinedTableError:
            pass


class AccountDeleteResponse(BaseModel):
    """Response from account deletion."""
    success: bool
    message: str


@router.delete(
    "",
    response_model=AccountDeleteResponse,
    summary="Delete user account",
    description=(
        "Soft-deletes user data and removes Supabase auth. Required by App "
        "Store and Play Store policies. **REQUIRES** "
        "`?confirm=DELETE_MY_ACCOUNT` query param — without it, returns 400. "
        "This guards against accidental destructive calls; the FE wraps the "
        "call in a typed-confirmation modal."
    ),
)
async def delete_account(
    user_id: str = Depends(get_current_user_id),
    confirm: str = Query(
        "",
        description=f"Must equal '{_DELETE_CONFIRM_PHRASE}' to proceed",
    ),
    _rl=Depends(per_user_rate_limit(3, 3600, scope="account_delete")),
):
    if confirm != _DELETE_CONFIRM_PHRASE:
        raise error_response(
            400,
            f"Account deletion requires explicit confirmation. Pass "
            f"?confirm={_DELETE_CONFIRM_PHRASE} as a query parameter.",
            code="CONFIRMATION_REQUIRED",
        )
    """
    Delete the current user's account.

    This performs:
    1. Soft-delete user data in the database (cascade-friendly)
    2. Delete the user from Supabase Auth

    Required by Apple App Store and Google Play Store policies.
    """
    pool = get_db_pool()
    if pool is None:
        raise error_response(
            503,
            "Account deletion is not available in offline mode",
            code="SERVICE_UNAVAILABLE",
        )

    # Pooled API path. Each DELETE has its own short statement_timeout
    # (set inside the txn) so a stuck row-lock can't stall the request,
    # and the whole transaction is wrapped in asyncio.wait_for to bound
    # total time end-to-end.
    try:
        async with pool.acquire() as conn:
            await asyncio.wait_for(
                _do_account_delete(conn, user_id),
                timeout=60.0,
            )
        logger.info("[account] Deleted database data for user=%s", user_id)

    except HTTPException:
        raise
    except asyncio.TimeoutError:
        logger.error("[account] Deletion exceeded 60s for user=%s", user_id)
        raise error_response(500, "Failed to delete account data", code="DB_ERROR")
    except asyncpg.PostgresError as e:
        logger.error("[account] DB error during deletion for user=%s: %s", user_id, e)
        raise error_response(500, "Failed to delete account data", code="DB_ERROR")

    # Remove from Supabase Auth
    supabase_admin = _get_supabase_admin()
    if supabase_admin:
        try:
            supabase_admin.auth.admin.delete_user(user_id)
            logger.info("[account] Deleted Supabase auth for user=%s", user_id)
        except Exception as e:
            logger.error(
                "[account] Supabase auth deletion failed for user=%s: %s",
                user_id, e,
            )
            # Data is already deleted — don't fail the whole request.
            # The orphaned auth record can be cleaned up manually.

    return AccountDeleteResponse(
        success=True,
        message="Your account and all associated data have been deleted.",
    )
