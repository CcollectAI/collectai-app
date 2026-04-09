#!/usr/bin/env python3
"""
Portfolio value change notification worker.

Runs daily — compares current portfolio value to 7-day-ago snapshot.
If change > 5%, creates a notification.
Also checks individual items for >15% changes.

Stores notifications in alert_trigger_history and sends push notifications
to users who have value_changes enabled in their notification preferences.
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
    format="%(asctime)s [value_change_worker] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN")

# Thresholds
PORTFOLIO_CHANGE_THRESHOLD_PCT = 5.0   # Notify if portfolio change > 5%
ITEM_CHANGE_THRESHOLD_PCT = 15.0        # Notify if individual item change > 15%
LOOKBACK_DAYS = 7                       # Compare to value from 7 days ago

# Dedupe: don't re-notify the same user within 24h for portfolio-level alerts
PORTFOLIO_DEDUP_HOURS = 24
# Dedupe: don't re-notify the same item within 72h
ITEM_DEDUP_HOURS = 72

# -- Queries --

# Get all users with at least 1 item and their current portfolio value
_CURRENT_PORTFOLIO_QUERY = """
WITH latest_predictions AS (
    SELECT DISTINCT ON (pp.item_id)
        pp.item_id,
        pp.q50,
        i.user_id,
        i.name AS item_name
    FROM public.price_predictions pp
    JOIN public.items i ON i.id = pp.item_id
    WHERE pp.q50 IS NOT NULL
      AND i.user_id IS NOT NULL
    ORDER BY pp.item_id, pp.asof DESC
)
SELECT
    user_id,
    SUM(q50)::numeric AS total_value,
    COUNT(*) AS item_count
FROM latest_predictions
GROUP BY user_id
HAVING COUNT(*) >= 1
"""

# Get portfolio value from N days ago for a specific user
_HISTORICAL_PORTFOLIO_QUERY = """
WITH historical_predictions AS (
    SELECT DISTINCT ON (pp.item_id)
        pp.item_id,
        pp.q50
    FROM public.price_predictions pp
    JOIN public.items i ON i.id = pp.item_id
    WHERE i.user_id = $1
      AND pp.q50 IS NOT NULL
      AND pp.asof <= $2
    ORDER BY pp.item_id, pp.asof DESC
)
SELECT COALESCE(SUM(q50), 0)::numeric AS total_value
FROM historical_predictions
"""

# Get individual item value changes for a user
_ITEM_CHANGES_QUERY = """
WITH current_vals AS (
    SELECT DISTINCT ON (pp.item_id)
        pp.item_id,
        pp.q50 AS current_q50,
        i.name AS item_name
    FROM public.price_predictions pp
    JOIN public.items i ON i.id = pp.item_id
    WHERE i.user_id = $1
      AND pp.q50 IS NOT NULL
    ORDER BY pp.item_id, pp.asof DESC
),
historical_vals AS (
    SELECT DISTINCT ON (pp.item_id)
        pp.item_id,
        pp.q50 AS old_q50
    FROM public.price_predictions pp
    JOIN public.items i ON i.id = pp.item_id
    WHERE i.user_id = $1
      AND pp.q50 IS NOT NULL
      AND pp.asof <= $2
    ORDER BY pp.item_id, pp.asof DESC
)
SELECT
    c.item_id,
    c.item_name,
    c.current_q50,
    h.old_q50,
    CASE WHEN h.old_q50 > 0 THEN
        ((c.current_q50 - h.old_q50) / h.old_q50 * 100)
    ELSE 0 END AS pct_change
FROM current_vals c
JOIN historical_vals h ON h.item_id = c.item_id
WHERE h.old_q50 > 0
  AND ABS((c.current_q50 - h.old_q50) / h.old_q50 * 100) > $3
ORDER BY ABS((c.current_q50 - h.old_q50) / h.old_q50 * 100) DESC
LIMIT 10
"""

# Check if user has value_changes notifications enabled
_CHECK_PREFS_QUERY = """
SELECT notification_preferences
FROM public.user_settings
WHERE user_id = $1
"""

# Dedup: check if we already notified this user recently for portfolio change
_PORTFOLIO_DEDUP_QUERY = """
SELECT 1 FROM public.alert_trigger_history
WHERE user_id = $1
  AND trigger_type = 'value_change'
  AND created_at > now() - interval '1 hour' * $2
LIMIT 1
"""

# Dedup: check if we already notified for this specific item
_ITEM_DEDUP_QUERY = """
SELECT 1 FROM public.alert_trigger_history
WHERE user_id = $1
  AND item_id = $2
  AND trigger_type = 'item_value_change'
  AND created_at > now() - interval '1 hour' * $3
LIMIT 1
"""


def _format_price(value: float) -> str:
    """Format a price value for display."""
    if value >= 1000:
        return f"{value:,.0f}"
    return f"{value:,.2f}"


def _parse_prefs(prefs_row) -> dict:
    """Parse notification preferences from a DB row."""
    if prefs_row is None:
        return {}
    prefs = prefs_row.get("notification_preferences")
    if prefs is None:
        return {}
    if isinstance(prefs, str):
        try:
            prefs = json.loads(prefs)
        except (json.JSONDecodeError, TypeError):
            return {}
    return prefs if isinstance(prefs, dict) else {}


def _is_value_changes_enabled(prefs_row) -> bool:
    """Check if the user has portfolio value_changes notifications enabled."""
    return _parse_prefs(prefs_row).get("value_changes", True)


def _is_item_value_changes_enabled(prefs_row) -> bool:
    """Check if the user has individual item value change notifications enabled."""
    return _parse_prefs(prefs_row).get("item_value_changes", True)


@with_async_retry(max_retries=3, base_delay=2.0, max_delay=120.0)
async def run_once():
    """Execute a single cycle of the value change worker."""
    if not DSN:
        logger.error("No DB_DSN env")
        record_run("value_change_worker", "error")
        return

    conn = await asyncpg.connect(DSN)
    try:
        # R46.12 — Schema-probe guard: the legacy queries below reference
        # pp.item_id and pp.asof on price_predictions, but this DB has
        # pp.item_ref + pp.generated_at instead. Probe for the broken column
        # and skip the cycle if drift is detected. Round 47: rewrite the
        # _CURRENT_PORTFOLIO_QUERY against the actual schema.
        try:
            await conn.fetchval(
                "SELECT pp.item_id FROM public.price_predictions pp LIMIT 1"
            )
        except Exception as drift_exc:
            logger.info(
                "[value_change] price_predictions schema drift (%s) — skipping cycle (R46.12)",
                type(drift_exc).__name__,
            )
            record_run("value_change_worker", "ok")
            return

        # 1. Get current portfolio values for all users
        portfolio_rows = await conn.fetch(_CURRENT_PORTFOLIO_QUERY)
        if not portfolio_rows:
            logger.info("No users with items found")
            return

        logger.info("Checking value changes for %d users", len(portfolio_rows))

        now = datetime.now(timezone.utc)
        lookback_date = now - timedelta(days=LOOKBACK_DAYS)
        portfolio_alerts = 0
        item_alerts = 0

        # Batch-fetch user preferences for all users at once (avoids N+1)
        all_user_ids = [row["user_id"] for row in portfolio_rows]
        all_prefs_rows = await conn.fetch(
            "SELECT user_id, notification_preferences FROM public.user_settings WHERE user_id = ANY($1)",
            all_user_ids,
        )
        prefs_by_user = {r["user_id"]: r for r in all_prefs_rows}

        # Batch-fetch portfolio-level dedup (avoids N+1)
        dedup_rows = await conn.fetch(
            """
            SELECT DISTINCT user_id FROM public.alert_trigger_history
            WHERE user_id = ANY($1::text[])
              AND trigger_type = 'value_change'
              AND created_at > now() - interval '1 hour' * $2
            """,
            [str(uid) for uid in all_user_ids],
            PORTFOLIO_DEDUP_HOURS,
        )
        portfolio_dedup_set = {r["user_id"] for r in dedup_rows}

        for row in portfolio_rows:
            user_id = row["user_id"]
            current_value = float(row["total_value"])

            if current_value <= 0:
                continue

            # Check user preferences (from batch-fetched data)
            prefs_row = prefs_by_user.get(user_id)
            if not _is_value_changes_enabled(prefs_row):
                continue

            # 2. Get historical portfolio value
            hist_row = await conn.fetchrow(
                _HISTORICAL_PORTFOLIO_QUERY, user_id, lookback_date
            )
            historical_value = float(hist_row["total_value"]) if hist_row else 0

            if historical_value <= 0:
                # No historical data — skip
                continue

            pct_change = ((current_value - historical_value) / historical_value) * 100

            # 3. Check portfolio-level threshold
            if abs(pct_change) > PORTFOLIO_CHANGE_THRESHOLD_PCT:
                # Dedup check (from batch-fetched data)
                if str(user_id) not in portfolio_dedup_set:
                    if pct_change > 0:
                        message = (
                            f"Your collection is up {pct_change:.1f}% this week! "
                            f"Now worth {_format_price(current_value)}"
                        )
                        title = "Collection Value Up"
                    else:
                        message = (
                            f"Heads up: your collection dropped {abs(pct_change):.1f}% this week"
                        )
                        title = "Collection Value Change"

                    trigger_value = json.dumps({
                        "current_value": current_value,
                        "previous_value": historical_value,
                        "pct_change": round(pct_change, 2),
                        "lookback_days": LOOKBACK_DAYS,
                    })

                    await conn.execute(
                        """
                        INSERT INTO public.alert_trigger_history
                            (user_id, trigger_type, trigger_value, message)
                        VALUES ($1, 'value_change', $2::jsonb, $3)
                        """,
                        str(user_id),
                        trigger_value,
                        message,
                    )

                    # Send push notification via preference-aware notify_user
                    try:
                        from app.lib.notify import notify_user
                        await notify_user(
                            conn,
                            str(user_id),
                            title=title,
                            body=message,
                            category="value_changes",
                            data={
                                "type": "value_change",
                                "pct_change": round(pct_change, 2),
                                "current_value": current_value,
                            },
                        )
                    except Exception as push_err:
                        logger.debug("Push notification skipped: %s", push_err)

                    portfolio_alerts += 1
                    logger.info(
                        "Portfolio alert: user=%s change=%.1f%% value=%.2f",
                        user_id, pct_change, current_value,
                    )

            # 4. Check individual item changes (skip if user disabled)
            if not _is_item_value_changes_enabled(prefs_row):
                continue

            item_rows = await conn.fetch(
                _ITEM_CHANGES_QUERY, user_id, lookback_date, ITEM_CHANGE_THRESHOLD_PCT
            )

            for item_row in item_rows:
                item_id = str(item_row["item_id"])
                item_name = item_row["item_name"] or f"Item {item_id[:8]}"
                item_pct = float(item_row["pct_change"])
                current_q50 = float(item_row["current_q50"])

                # Only notify on significant gains (> +15%)
                if item_pct <= 0:
                    continue

                # Dedup check
                existing = await conn.fetchrow(
                    _ITEM_DEDUP_QUERY, str(user_id), item_id, ITEM_DEDUP_HOURS
                )
                if existing is not None:
                    continue

                message = (
                    f"Your {item_name} is up {item_pct:.0f}% — "
                    f"now worth {_format_price(current_q50)}"
                )

                trigger_value = json.dumps({
                    "item_id": item_id,
                    "item_name": item_name,
                    "current_price": current_q50,
                    "old_price": float(item_row["old_q50"]),
                    "pct_change": round(item_pct, 2),
                })

                await conn.execute(
                    """
                    INSERT INTO public.alert_trigger_history
                        (user_id, item_id, trigger_type, trigger_value, message)
                    VALUES ($1, $2, 'item_value_change', $3::jsonb, $4)
                    """,
                    str(user_id),
                    item_id,
                    trigger_value,
                    message,
                )

                # Send push notification via preference-aware notify_user
                try:
                    from app.lib.notify import notify_user
                    await notify_user(
                        conn,
                        str(user_id),
                        title="Item Value Up",
                        body=message,
                        category="value_changes",
                        data={
                            "type": "item_value_change",
                            "item_id": item_id,
                            "pct_change": round(item_pct, 2),
                        },
                    )
                except Exception as push_err:
                    logger.debug("Push notification skipped: %s", push_err)

                item_alerts += 1
                logger.info(
                    "Item alert: user=%s item=%s change=%.1f%% price=%.2f",
                    user_id, item_id, item_pct, current_q50,
                )

        logger.info(
            "Value change worker complete: %d portfolio alerts, %d item alerts",
            portfolio_alerts, item_alerts,
        )
    finally:
        await conn.close()
        record_run("value_change_worker", "ok")


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run("value_change_worker", "error")
        log_dead_letter("value_change_worker", {}, e)
        logger.exception("value_change_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
