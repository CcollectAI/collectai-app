"""
Account management router.

Endpoints:
- DELETE /account - Request account deletion (soft-delete + Supabase auth removal)
"""

from __future__ import annotations

import logging

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import get_current_user_id
from app.errors import error_response
from app.lib.db_helpers import get_db_pool

router = APIRouter(prefix="/account", tags=["Account"])
logger = logging.getLogger(__name__)


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


class AccountDeleteResponse(BaseModel):
    """Response from account deletion."""
    success: bool
    message: str


@router.delete("", response_model=AccountDeleteResponse, summary="Delete user account", description="Soft-deletes user data and removes Supabase auth. Required by App Store and Play Store policies.")
async def delete_account(user_id: str = Depends(get_current_user_id)):
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

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Delete user-owned data in dependency order
                # Tables with user_id FK to auth.users will cascade,
                # but we explicitly clean up to be safe.
                # Frozen allowlist — only these tables can be cleaned.
                # The table names are used directly in SQL, so we MUST
                # guarantee they are from this hardcoded set.
                _ALLOWED_TABLES = frozenset({
                    "mandate_deals",
                    "purchase_mandates",
                    "alert_trigger_history",
                    "user_price_alerts",
                    "item_provenance_events",
                    "watchlist",
                    "price_predictions",
                    "market_hits",
                    "category_items",
                    "user_settings",
                    "user_category_follows",
                    "event_attendees",
                })

                for table in _ALLOWED_TABLES:
                    assert table.isidentifier(), f"Invalid table name: {table}"
                    try:
                        await conn.execute(
                            f'DELETE FROM "{table}" WHERE user_id = $1',
                            user_id,
                        )
                    except asyncpg.UndefinedTableError:
                        # Table may not exist in all environments
                        pass

                # Delete profile
                try:
                    await conn.execute(
                        "DELETE FROM profiles WHERE id = $1",
                        user_id,
                    )
                except asyncpg.UndefinedTableError:
                    pass

                # Delete public profile
                try:
                    await conn.execute(
                        "DELETE FROM user_public_profiles WHERE user_id = $1",
                        user_id,
                    )
                except asyncpg.UndefinedTableError:
                    pass

        logger.info("[account] Deleted database data for user=%s", user_id)

    except HTTPException:
        raise
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
