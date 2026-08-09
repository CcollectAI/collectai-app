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


# Per-user tables. category_items + price_predictions are global catalog data
# with no user_id column.
#
# 2026-07-25 audit: the live DB has 126 BASE TABLES carrying user_id. 38 have an
# ON DELETE CASCADE that removes them with the profile row, and 9 were listed
# here — leaving 80 that DELETE /account never touched while still returning
# success. That included chat_messages, item_images, user_push_tokens,
# marketplace_account_defaults, quickscan_history and user_privacy_settings_v1.
#
# Anything holding user content or identifiers now belongs in this list.
# server/scripts/audit_account_deletion.py recomputes the three-way split from
# the live schema and fails if a table is neither cascaded, deleted, nor
# explicitly retained below — so a newly added table cannot silently reopen the
# gap. Do not add a table here without an index on user_id: this runs inside a
# 15s statement_timeout.
_ALLOWED_TABLES = (
    # original nine
    "mandate_deals",
    "purchase_mandates",
    "alert_trigger_history",
    "user_price_alerts",
    "item_provenance_events",
    "watchlist",
    "user_settings",
    "user_category_follows",
    "event_attendees",
    # alerts & notifications
    "alert_endpoints",
    "alert_rules",
    "alert_subscriptions",
    "notification_history",
    "user_alert_preferences",
    "user_notifications",
    "user_push_tokens",
    "user_webhooks",
    "drop_follows",
    # chat — user-authored content
    "chat_messages",
    "chat_messages_v1",
    "chat_message_reactions_v1",
    "chat_presence_v1",
    "chat_typing",
    "chat_typing_v1",
    "chat_thread_members_v1",
    "chat_thread_reads_v1",
    "chat_thread_mutes_v1",
    "chat_thread_bans_v1",
    # collection, items & media
    "collections",
    # item_images is NOT here: it has no user_id column (it is keyed on
    # item_id), so `DELETE FROM item_images WHERE user_id = $1` raised
    # UndefinedColumnError — which the handler below does NOT catch, so the
    # whole transaction aborted and DELETE /account failed for every user.
    # App Store Guideline 5.1.1(v) requires account deletion to work.
    #
    # Its rows still go: item_images_item_id_fkey is ON DELETE CASCADE to
    # items, which IS deleted by user_id. Verified on prod.
    "item_notes_v1",
    "item_valuation_history",
    "item_valuation_keys",
    "listings",
    "watchlist_items",
    "watchlist_valuation",
    "portfolio_valuations_v1",
    "portfolio_values",
    "valuations",
    # scans, predictions & user corrections
    "quickscan_drafts_v1",
    "quickscan_history",
    "quick_predictions",
    "scan_corrections",
    "taxonomy_corrections",
    "predict_sessions",
    "prediction_sessions",
    "prediction_events_v2",
    "prediction_item_map",
    "price_prediction_runs",
    "pricing_traces",
    "forecasts",
    "guidance_runs",
    "suggestion_logs",
    "image_labels",
    "label_events",
    "training_items",
    "on_demand_lookups_audit",
    "ingest_jobs",
    "agent_jobs",
    # build/paint projects
    "build_paint_projects",
    "build_paint_sessions",
    "build_paint_notes",
    "projects_v1",
    "project_steps_v1",
    "project_notes_v1",
    # events, marketplace & commerce
    "events",
    "event_templates",
    "event_tickets",
    "event_announcement_reads",
    "marketplace_account_defaults",
    "buyer_intents",
    "demand_signals",
    "sponsor_subscriptions",
    "subscription_events",
    "twitch_creators",
    # preferences & legacy profile snapshots (personal data)
    "user_badge_preferences_v1",
    "user_category_visibility_v1",
    "user_checklist_state",
    "user_feedback_events_v1",
    "user_privacy_settings_v1",
    "user_public_profile_v1_legacy_20260724",
    "user_public_profiles_legacy_20260724",
)

# Tables carrying user_id that are deliberately NOT deleted, each with the
# reason. Anonymised instead where the row itself is not user content.
# The audit script treats this as the allowlist: an entry here is a decision,
# a missing table is a bug.
_RETAINED_TABLES: dict[str, str] = {
    "market_hits": (
        "Shared market observations, not user content. MEASURED 2026-07-25: 0 of "
        "3,332,124 rows have a non-null user_id -- the column is never written, "
        "so there is no user data here to delete. Deleting would also destroy "
        "price history for every other user, and an unindexed DELETE scans all "
        "monthly partitions past the 15s statement_timeout."
    ),
    # market_hits partitions (market_hits_archive / _default / _yYYYYmMM) are
    # deliberately NOT listed: they are covered by the parent, and the audit
    # filters them out, so naming them here only produces stale entries.
    "comps": "Derived market comparables keyed to catalog refs, not user content.",
}

# market_hits needs NO deletion, anonymisation, or index. Measured 2026-07-25:
# 0 of 3,332,124 rows carry a non-null user_id. The column exists but no writer
# ever populates it, so there is no user data to remove — "anonymous crawl data"
# is literally true, not a euphemism.
#
# Do NOT add an index on market_hits(user_id) to "enable" cleanup. That is the
# table whose 24 indexes at 528k rows timed out PostgREST batch upserts and
# stalled the entire ingest pipeline — the incident docs/DATA_SCALING_PLAN.md
# was written about, and the reason its governance rule 1 is "default = refuse
# to add". An index here would cost write throughput on 3.3M rows to serve
# exactly zero of them.


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
                # A dropped table is fine — there is nothing left to delete.
                pass
            except asyncpg.UndefinedColumnError:
                # A table in this list with no user_id column. Deliberately NOT
                # silent: it means the list is wrong, and the row's data may not
                # be reachable any other way. Swallowing it would turn a broken
                # erasure into a green one, which is the worst possible outcome
                # for a GDPR/App-Store deletion path.
                #
                # Logged at ERROR (info/warn are stripped in release) and then
                # re-raised, so the request fails loudly rather than reporting
                # success on a partial erasure.
                logger.error(
                    "[account] %s is in _ALLOWED_TABLES but has no user_id column — "
                    "account deletion ABORTED. Either remove it from the list (if it "
                    "cascades) or delete it through its owning table.",
                    table,
                )
                raise

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
