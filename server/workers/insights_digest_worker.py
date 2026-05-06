#!/usr/bin/env python3
"""
Weekly insights digest worker.

Runs once per week — compiles portfolio highlights for each user:
  - Total portfolio value and change
  - Top gainer item
  - Top loser item
  - New items added this week

Creates a single digest notification per user.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone

import asyncpg

from app.worker_registry import record_run
from workers.retry import with_async_retry, log_dead_letter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [insights_digest_worker] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN")

LOOKBACK_DAYS = 7

# -- Queries --

# Users with items
_USERS_WITH_ITEMS_QUERY = """
SELECT DISTINCT user_id
FROM public.items
WHERE user_id IS NOT NULL
"""

# Current portfolio value for a user.
# Partition prune: latest predictions are always within the last 60 days.
_CURRENT_VALUE_QUERY = """
SELECT COALESCE(SUM(lp.q50), 0)::numeric AS total_value
FROM (
    SELECT DISTINCT ON (pp.item_ref)
        pp.q50
    FROM public.price_predictions pp
    JOIN public.items i ON i.canonical_key = pp.item_ref
    WHERE i.user_id = $1
      AND pp.q50 IS NOT NULL
      AND pp.generated_at > now() - interval '60 days'
    ORDER BY pp.item_ref, pp.generated_at DESC
) lp
"""

# Historical portfolio value.
# Partition prune: bound both edges so the planner picks one partition.
_HISTORICAL_VALUE_QUERY = """
SELECT COALESCE(SUM(hp.q50), 0)::numeric AS total_value
FROM (
    SELECT DISTINCT ON (pp.item_ref)
        pp.q50
    FROM public.price_predictions pp
    JOIN public.items i ON i.canonical_key = pp.item_ref
    WHERE i.user_id = $1
      AND pp.q50 IS NOT NULL
      AND pp.generated_at > $2 - interval '30 days'
      AND pp.generated_at <= $2
    ORDER BY pp.item_ref, pp.generated_at DESC
) hp
"""

# Top gainer and loser for a user this week
_TOP_MOVERS_QUERY = """
WITH current_vals AS (
    SELECT DISTINCT ON (pp.item_ref)
        pp.item_ref,
        pp.q50 AS current_q50,
        i.title AS item_name
    FROM public.price_predictions pp
    JOIN public.items i ON i.canonical_key = pp.item_ref
    WHERE i.user_id = $1
      AND pp.q50 IS NOT NULL
      -- Partition prune: latest predictions are always within last 60d.
      AND pp.generated_at > now() - interval '60 days'
    ORDER BY pp.item_ref, pp.generated_at DESC
),
historical_vals AS (
    SELECT DISTINCT ON (pp.item_ref)
        pp.item_ref,
        pp.q50 AS old_q50
    FROM public.price_predictions pp
    JOIN public.items i ON i.canonical_key = pp.item_ref
    WHERE i.user_id = $1
      AND pp.q50 IS NOT NULL
      AND pp.generated_at <= $2
    ORDER BY pp.item_ref, pp.generated_at DESC
)
SELECT
    c.item_ref,
    c.item_name,
    c.current_q50,
    h.old_q50,
    CASE WHEN h.old_q50 > 0 THEN
        ((c.current_q50 - h.old_q50) / h.old_q50 * 100)
    ELSE 0 END AS pct_change
FROM current_vals c
JOIN historical_vals h ON h.item_ref = c.item_ref
WHERE h.old_q50 > 0
ORDER BY pct_change DESC
LIMIT 50
"""

# New items added this week
_NEW_ITEMS_QUERY = """
SELECT COUNT(*) AS new_count
FROM public.items
WHERE user_id = $1
  AND created_at >= $2
"""

# Check user notification preferences.
# user_settings has no notification_preferences column — cross-worker fix
# with value_change_worker during 2026-04-20 silent-fail sweep. Caller's
# _is_digest_enabled() returns True when the row is empty, so default-on
# behaviour preserves prior (broken) semantics.
_CHECK_PREFS_QUERY = """
SELECT user_id
FROM public.user_settings
WHERE user_id = $1
"""

# Dedup: don't send digest twice in the same week
_DIGEST_DEDUP_QUERY = """
SELECT 1 FROM public.alert_trigger_history
WHERE user_id = $1
  AND trigger_type = 'weekly_digest'
  AND created_at > now() - interval '7 days'
LIMIT 1
"""


def _format_price(value: float) -> str:
    """Format a price value for display."""
    if value >= 1000:
        return f"{value:,.0f}"
    return f"{value:,.2f}"


def _is_digest_enabled(prefs_row) -> bool:
    """Check if the user has weekly_digest notifications enabled."""
    if prefs_row is None:
        return True
    prefs = prefs_row.get("notification_preferences")
    if prefs is None:
        return True
    if isinstance(prefs, str):
        try:
            prefs = json.loads(prefs)
        except (json.JSONDecodeError, TypeError):
            return True
    return prefs.get("weekly_digest", True)


@with_async_retry(max_retries=3, base_delay=2.0, max_delay=120.0)
async def run_once():
    """Execute a single cycle of the insights digest worker."""
    if not DSN:
        logger.error("No DB_DSN env")
        record_run("insights_digest_worker", "error")
        return

    status = "ok"
    conn = await asyncpg.connect(DSN)
    try:
        # R46.13 guard removed — user_settings table now exists (R49 schema cleanup).
        # Queries rewritten against actual schema (R49): pp.item_ref, pp.generated_at,
        # i.canonical_key, i.title.

        # Get all users with items
        user_rows = await conn.fetch(_USERS_WITH_ITEMS_QUERY)
        if not user_rows:
            logger.info("No users with items found")
            return

        logger.info("Generating weekly digests for %d users", len(user_rows))

        now = datetime.now(timezone.utc)
        lookback_date = now - timedelta(days=LOOKBACK_DAYS)
        digests_sent = 0

        # Batch-fetch preferences for all users at once (avoids N+1).
        # See _CHECK_PREFS_QUERY comment — no notification_preferences
        # column exists; this just probes user existence. _is_digest_enabled
        # defaults True when the row lacks the field.
        all_user_ids = [row["user_id"] for row in user_rows]
        all_prefs_rows = await conn.fetch(
            "SELECT user_id FROM public.user_settings WHERE user_id = ANY($1)",
            all_user_ids,
        )
        prefs_by_user = {r["user_id"]: r for r in all_prefs_rows}

        # Batch-fetch dedup check for all users at once (avoids N+1).
        # alert_trigger_history.user_id is uuid, not text — casting the param
        # array to ::text[] raises "operator does not exist: uuid = text".
        # Was masked by the notification_preferences error until round 3
        # fixed that. Learning #46 type-mismatch class.
        dedup_rows = await conn.fetch(
            """
            SELECT DISTINCT user_id FROM public.alert_trigger_history
            WHERE user_id = ANY($1::uuid[])
              AND trigger_type = 'weekly_digest'
              AND created_at > now() - interval '7 days'
            """,
            [str(uid) for uid in all_user_ids],
        )
        digest_dedup_set = {r["user_id"] for r in dedup_rows}

        for user_row in user_rows:
            user_id = user_row["user_id"]

            # Check preferences (from batch-fetched data)
            prefs_row = prefs_by_user.get(user_id)
            if not _is_digest_enabled(prefs_row):
                continue

            # Dedup check (from batch-fetched data)
            if str(user_id) in digest_dedup_set:
                continue

            # Get current value
            current_row = await conn.fetchrow(_CURRENT_VALUE_QUERY, user_id)
            current_value = float(current_row["total_value"]) if current_row else 0

            if current_value <= 0:
                continue

            # Get historical value
            hist_row = await conn.fetchrow(
                _HISTORICAL_VALUE_QUERY, user_id, lookback_date
            )
            historical_value = float(hist_row["total_value"]) if hist_row else 0

            # Calculate change
            pct_change = 0.0
            if historical_value > 0:
                pct_change = ((current_value - historical_value) / historical_value) * 100

            # Get top movers
            movers = await conn.fetch(_TOP_MOVERS_QUERY, user_id, lookback_date)
            top_gainer = None
            top_loser = None
            if movers:
                first = movers[0]
                if float(first["pct_change"]) > 0:
                    top_gainer = {
                        "item_ref": str(first["item_ref"]),
                        "item_name": first["item_name"] or f"Item {str(first['item_id'])[:8]}",
                        "pct_change": round(float(first["pct_change"]), 1),
                    }
                last = movers[-1]
                if float(last["pct_change"]) < 0:
                    top_loser = {
                        "item_ref": str(last["item_ref"]),
                        "item_name": last["item_name"] or f"Item {str(last['item_id'])[:8]}",
                        "pct_change": round(float(last["pct_change"]), 1),
                    }

            # Get new items count
            new_items_row = await conn.fetchrow(
                _NEW_ITEMS_QUERY, user_id, lookback_date
            )
            new_items_count = new_items_row["new_count"] if new_items_row else 0

            # Build digest message
            change_str = f"+{pct_change:.1f}%" if pct_change >= 0 else f"{pct_change:.1f}%"

            parts = [
                f"Weekly digest: Collection worth {_format_price(current_value)} ({change_str})."
            ]

            if top_gainer:
                parts.append(
                    f"Top gainer: {top_gainer['item_name']} (+{top_gainer['pct_change']:.0f}%)"
                )

            if top_loser:
                parts.append(
                    f"Top loser: {top_loser['item_name']} ({top_loser['pct_change']:.0f}%)"
                )

            if new_items_count > 0:
                parts.append(
                    f"{new_items_count} new item{'s' if new_items_count != 1 else ''} added"
                )

            message = " ".join(parts)

            # Build trigger value for storage
            trigger_data = {
                "current_value": current_value,
                "previous_value": historical_value,
                "pct_change": round(pct_change, 2),
                "new_items_count": new_items_count,
                "top_gainer": top_gainer,
                "top_loser": top_loser,
                "lookback_days": LOOKBACK_DAYS,
                "generated_at": now.isoformat(),
            }

            await conn.execute(
                """
                INSERT INTO public.alert_trigger_history
                    (user_id, trigger_type, trigger_value, message)
                VALUES ($1, 'weekly_digest', $2::jsonb, $3)
                """,
                str(user_id),
                json.dumps(trigger_data),
                message,
            )

            # Send push notification via preference-aware notify_user
            try:
                from app.lib.notify import notify_user
                await notify_user(
                    conn,
                    str(user_id),
                    title="Weekly Collection Digest",
                    body=message,
                    category="weekly_digest",
                    data={
                        "type": "weekly_digest",
                        "pct_change": round(pct_change, 2),
                        "current_value": current_value,
                    },
                )
            except Exception as push_err:
                logger.debug("Push notification skipped: %s", push_err)

            digests_sent += 1
            logger.info(
                "Digest sent: user=%s value=%.2f change=%.1f%%",
                user_id, current_value, pct_change,
            )

        logger.info("Insights digest worker complete: %d digests sent", digests_sent)
    except Exception:
        status = "error"
        raise
    finally:
        await conn.close()
        record_run("insights_digest_worker", status)


async def main():
    try:
        await run_once()
    except Exception as e:
        log_dead_letter("insights_digest_worker", {}, e)
        logger.exception("insights_digest_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
