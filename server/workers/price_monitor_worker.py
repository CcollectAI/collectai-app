#!/usr/bin/env python3
"""Price monitor worker — proactive price alerts with anomaly detection.

Implements the "Monitored" pillar:
  1. Threshold alerts — fires when price_predictions.q50 drops below user threshold
  2. Anomaly detection — rolling z-score on price_history for spike/drop detection
  3. Set completion suggestions — nudges users toward completing partial sets
"""

import asyncio
import json
import logging
import math
import os
from datetime import datetime, timezone

import asyncpg

from app.worker_registry import record_run
from workers.retry import with_async_retry, log_dead_letter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [price_monitor] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN")

# Anomaly detection configuration
Z_SCORE_THRESHOLD = float(os.getenv("ANOMALY_Z_THRESHOLD", "2.0"))
MIN_HISTORY_POINTS = int(os.getenv("ANOMALY_MIN_POINTS", "5"))
HISTORY_WINDOW = int(os.getenv("ANOMALY_HISTORY_WINDOW", "30"))

# Dedup window in hours
DEDUP_HOURS = int(os.getenv("ALERT_DEDUP_HOURS", "24"))

# Set completion threshold (suggest only when user owns >50% of a set)
SET_COMPLETION_MIN_PCT = float(os.getenv("SET_COMPLETION_MIN_PCT", "0.50"))

# Maximum alerts per user per monitoring cycle (prevents alert spam)
MAX_ALERTS_PER_USER = int(os.getenv("MAX_ALERTS_PER_USER", "10"))


async def _already_fired(conn, user_id, item_id, trigger_type):
    """Check if an alert of this type already fired for this user+item in the last DEDUP_HOURS."""
    row = await conn.fetchrow(
        """
        SELECT 1 FROM public.alert_trigger_history
        WHERE user_id = $1
          AND item_id = $2
          AND trigger_type = $3
          AND created_at > now() - ($4 || ' hours')::interval
        LIMIT 1
        """,
        user_id,
        item_id,
        trigger_type,
        str(DEDUP_HOURS),
    )
    return row is not None


async def _already_fired_by_alert(conn, alert_id):
    """Check if a specific alert_id already fired in the dedup window."""
    row = await conn.fetchrow(
        """
        SELECT 1 FROM public.alert_trigger_history
        WHERE alert_id = $1
          AND created_at > now() - ($2 || ' hours')::interval
        LIMIT 1
        """,
        alert_id,
        str(DEDUP_HOURS),
    )
    return row is not None


# ── 1. Threshold Alerts ─────────────────────────────────────────────────────


async def check_threshold_alerts(conn):
    """Check all active below_threshold alerts against latest price predictions."""
    alerts = await conn.fetch(
        """
        SELECT
            a.id AS alert_id,
            a.user_id,
            a.item_id,
            a.category,
            a.threshold_value
        FROM public.user_price_alerts a
        WHERE a.active = true
          AND a.trigger_type = 'below_threshold'
          AND a.threshold_value IS NOT NULL
          AND a.item_id IS NOT NULL
        """
    )

    if not alerts:
        logger.info("No active threshold alerts to check")
        return 0

    logger.info("Checking %d threshold alerts", len(alerts))
    fired = 0
    alerts_per_user: dict[str, int] = {}

    # Batch dedup: fetch all recently-fired alert_ids in one query
    all_alert_ids = [a["alert_id"] for a in alerts]
    fired_rows = await conn.fetch(
        """
        SELECT DISTINCT alert_id FROM public.alert_trigger_history
        WHERE alert_id = ANY($1)
          AND created_at > now() - ($2 || ' hours')::interval
        """,
        all_alert_ids,
        str(DEDUP_HOURS),
    )
    fired_alert_set = {row["alert_id"] for row in fired_rows}

    for alert in alerts:
        alert_id = alert["alert_id"]
        user_id = alert["user_id"]
        item_id = alert["item_id"]
        threshold = float(alert["threshold_value"])

        # Skip if user already received MAX_ALERTS_PER_USER this cycle
        if alerts_per_user.get(str(user_id), 0) >= MAX_ALERTS_PER_USER:
            continue

        # Skip if already fired recently (batch lookup)
        if alert_id in fired_alert_set:
            continue

        # Get the latest price prediction for this item
        pred = await conn.fetchrow(
            """
            SELECT q50, q10, q90
            FROM public.price_predictions
            WHERE item_id = $1
            ORDER BY asof DESC
            LIMIT 1
            """,
            item_id,
        )

        if pred is None or pred["q50"] is None:
            continue

        q50 = float(pred["q50"])

        if q50 < threshold:
            trigger_value = json.dumps({
                "current_price": q50,
                "threshold": threshold,
                "q10": float(pred["q10"]) if pred["q10"] is not None else None,
                "q90": float(pred["q90"]) if pred["q90"] is not None else None,
            })
            message = (
                f"Price dropped to {q50:.2f} EUR, below your threshold of "
                f"{threshold:.2f} EUR"
            )

            await conn.execute(
                """
                INSERT INTO public.alert_trigger_history
                    (alert_id, user_id, item_id, trigger_type, trigger_value, message)
                VALUES ($1, $2, $3, 'below_threshold', $4::jsonb, $5)
                """,
                alert_id,
                user_id,
                str(item_id),
                trigger_value,
                message,
            )

            # Update last_triggered_at on the alert itself
            await conn.execute(
                """
                UPDATE public.user_price_alerts
                SET last_triggered_at = now()
                WHERE id = $1
                """,
                alert_id,
            )

            # Send push notification (P0)
            try:
                from app.lib.notify import notify_user
                await notify_user(
                    conn,
                    str(user_id),
                    title="Price Alert",
                    body=message,
                    category="price_alerts",
                    data={
                        "type": "below_threshold",
                        "alert_id": str(alert_id),
                        "item_id": str(item_id),
                        "price_q50": round(q50, 2),
                    },
                )
            except Exception as push_err:
                logger.debug("Push skipped for threshold alert: %s", push_err)

            fired += 1
            alerts_per_user[str(user_id)] = alerts_per_user.get(str(user_id), 0) + 1
            logger.info(
                "Threshold alert fired: alert_id=%s item=%s q50=%.2f threshold=%.2f",
                alert_id, item_id, q50, threshold,
            )

    return fired


# ── 2. Anomaly Detection ────────────────────────────────────────────────────


async def detect_anomalies(conn):
    """Compute rolling z-scores on price_history and alert item owners on anomalies."""

    # Only check items that are actively relevant: owned by users (updated in
    # last 7 days) or on active watchlists.  This avoids scanning every item
    # with price history, reducing load by ~80-90%.
    item_refs = await conn.fetch(
        """
        SELECT ph.item_ref, count(*) AS cnt
        FROM public.price_history ph
        WHERE ph.snapshot_at > now() - ($1 || ' days')::interval
          AND (
            EXISTS (
              SELECT 1 FROM public.items i
              WHERE i.normalized_key = ph.item_ref
                AND i.updated_at > now() - interval '7 days'
            )
            OR EXISTS (
              SELECT 1 FROM public.watchlist w
              WHERE w.item_ref = ph.item_ref
            )
          )
        GROUP BY ph.item_ref
        HAVING count(*) >= $2
        """,
        str(HISTORY_WINDOW),
        MIN_HISTORY_POINTS,
    )

    if not item_refs:
        logger.info("No item_refs with sufficient price history for anomaly detection")
        return 0

    logger.info("Checking %d item_refs for price anomalies", len(item_refs))
    fired = 0
    anomaly_alerts_per_user: dict[str, int] = {}

    for row in item_refs:
        item_ref = row["item_ref"]

        # Get the last HISTORY_WINDOW snapshots
        snapshots = await conn.fetch(
            """
            SELECT price_q50
            FROM public.price_history
            WHERE item_ref = $1
            ORDER BY snapshot_at DESC
            LIMIT $2
            """,
            item_ref,
            HISTORY_WINDOW,
        )

        prices = [float(s["price_q50"]) for s in snapshots if s["price_q50"] is not None]

        if len(prices) < MIN_HISTORY_POINTS:
            continue

        latest_price = prices[0]
        # Use all but the latest for computing baseline stats
        # (prevents the anomaly itself from inflating the mean/std)
        baseline = prices[1:]
        n = len(baseline)
        mean_price = sum(baseline) / n
        variance = sum((p - mean_price) ** 2 for p in baseline) / n
        std_dev = math.sqrt(variance) if variance > 0 else 0.0

        if std_dev == 0:
            # All historical prices identical; skip (no variation to detect)
            continue

        z_score = (latest_price - mean_price) / std_dev
        pct_change = ((latest_price - mean_price) / mean_price) * 100.0 if mean_price != 0 else 0.0

        if abs(z_score) <= Z_SCORE_THRESHOLD:
            continue

        # Determine direction
        if z_score > 0:
            trigger_type = "price_spike"
            direction_label = "spiked up"
        else:
            trigger_type = "price_drop"
            direction_label = "dropped"

        trigger_value = json.dumps({
            "current_price": round(latest_price, 2),
            "mean_price": round(mean_price, 2),
            "std_dev": round(std_dev, 2),
            "z_score": round(z_score, 2),
            "pct_change": round(pct_change, 1),
            "history_points": n,
        })

        message = (
            f"Price {direction_label} to {latest_price:.2f} EUR "
            f"({pct_change:+.1f}% vs {mean_price:.2f} average). "
            f"Z-score: {z_score:.2f}"
        )

        # Find all users who own items with this item_ref (via normalized_key or id)
        owners = await conn.fetch(
            """
            SELECT DISTINCT user_id, id AS item_id
            FROM public.items
            WHERE normalized_key = $1
               OR id::text = $1
            """,
            item_ref,
        )

        if not owners:
            continue

        # Batch dedup: fetch recently-fired (user_id, item_id, trigger_type) tuples
        owner_ids = [str(o["item_id"]) for o in owners]
        owner_user_ids = [o["user_id"] for o in owners]
        fired_anomaly_rows = await conn.fetch(
            """
            SELECT user_id, item_id, trigger_type
            FROM public.alert_trigger_history
            WHERE user_id = ANY($1)
              AND item_id = ANY($2)
              AND trigger_type = ANY($3)
              AND created_at > now() - ($4 || ' hours')::interval
            """,
            owner_user_ids,
            owner_ids,
            ["price_spike", "price_drop"],
            str(DEDUP_HOURS),
        )
        anomaly_fired_set = {
            (r["user_id"], r["item_id"], r["trigger_type"])
            for r in fired_anomaly_rows
        }

        for owner in owners:
            user_id = owner["user_id"]
            item_id = str(owner["item_id"])

            # Per-user alert cap
            if anomaly_alerts_per_user.get(str(user_id), 0) >= MAX_ALERTS_PER_USER:
                continue

            # Dedup check (batch lookup)
            if (user_id, item_id, trigger_type) in anomaly_fired_set:
                continue

            await conn.execute(
                """
                INSERT INTO public.alert_trigger_history
                    (user_id, item_id, trigger_type, trigger_value, message)
                VALUES ($1, $2, $3, $4::jsonb, $5)
                """,
                user_id,
                item_id,
                trigger_type,
                trigger_value,
                message,
            )

            # Send push notification (P0)
            try:
                from app.lib.notify import notify_user
                await notify_user(
                    conn,
                    str(user_id),
                    title="Price Anomaly Detected",
                    body=message,
                    category="price_alerts",
                    data={
                        "type": trigger_type,
                        "item_id": item_id,
                        "price": round(latest_price, 2),
                        "z_score": round(z_score, 2),
                        "pct_change": round(pct_change, 1),
                    },
                )
            except Exception as push_err:
                logger.debug("Push skipped for anomaly alert: %s", push_err)

            fired += 1
            anomaly_alerts_per_user[str(user_id)] = anomaly_alerts_per_user.get(str(user_id), 0) + 1
            logger.info(
                "Anomaly alert fired: user=%s item_ref=%s type=%s z=%.2f pct=%.1f%%",
                user_id, item_ref, trigger_type, z_score, pct_change,
            )

    return fired


# ── 3. Set Completion Suggestions ───────────────────────────────────────────


async def check_set_completions(conn):
    """For each set in set_registry, check user ownership and suggest completions."""

    sets = await conn.fetch(
        """
        SELECT id, category_id, set_name, total_items, items_json
        FROM public.set_registry
        WHERE total_items > 0
        """
    )

    if not sets:
        logger.info("No sets in set_registry to check")
        return 0

    logger.info("Checking %d sets for completion suggestions", len(sets))
    fired = 0

    for s in sets:
        set_id = s["id"]
        category_id = s["category_id"]
        set_name = s["set_name"]
        total_items = s["total_items"]

        # Parse the items_json — list of item dicts
        try:
            if isinstance(s["items_json"], str):
                set_items = json.loads(s["items_json"])
            else:
                set_items = s["items_json"]
        except (json.JSONDecodeError, TypeError):
            logger.warning("Invalid items_json for set %s", set_id)
            continue

        if not set_items or not isinstance(set_items, list):
            continue

        # Extract the item keys from the set definition
        set_item_keys = []
        set_item_names = {}
        for item in set_items:
            key = item.get("key") or item.get("name", "")
            name = item.get("name", key)
            if key:
                set_item_keys.append(key)
                set_item_names[key] = name

        if not set_item_keys:
            continue

        # Find all users who own at least one item in this category
        users = await conn.fetch(
            """
            SELECT DISTINCT user_id
            FROM public.items
            WHERE category = $1
            """,
            category_id,
        )

        for user_row in users:
            user_id = user_row["user_id"]

            # Find which set items this user owns (match by normalized_key or title)
            owned_rows = await conn.fetch(
                """
                SELECT normalized_key, title
                FROM public.items
                WHERE user_id = $1
                  AND category = $2
                """,
                user_id,
                category_id,
            )

            # Build a set of owned keys (check both normalized_key and title)
            owned_keys = set()
            for orow in owned_rows:
                nk = orow["normalized_key"]
                title = orow["title"]
                for sk in set_item_keys:
                    sk_lower = sk.lower()
                    if (nk and sk_lower in nk.lower()) or (title and sk_lower in title.lower()):
                        owned_keys.add(sk)

            owned_count = len(owned_keys)
            completion_pct = owned_count / total_items if total_items > 0 else 0.0

            # Only suggest if partially complete (above minimum, below 100%)
            if completion_pct < SET_COMPLETION_MIN_PCT or completion_pct >= 1.0:
                continue

            # Build the "missing" list
            missing_keys = [k for k in set_item_keys if k not in owned_keys]
            missing_names = [set_item_names.get(k, k) for k in missing_keys[:5]]
            missing_suffix = ""
            if len(missing_keys) > 5:
                missing_suffix = f" and {len(missing_keys) - 5} more"

            item_id_for_dedup = f"set:{set_id}"

            # Dedup check
            if await _already_fired(conn, user_id, item_id_for_dedup, "completeness"):
                continue

            message = (
                f"You have {owned_count}/{total_items} {set_name} items. "
                f"Missing: {', '.join(missing_names)}{missing_suffix}."
            )

            trigger_value = json.dumps({
                "set_id": set_id,
                "set_name": set_name,
                "total_items": total_items,
                "owned_count": owned_count,
                "completion_pct": round(completion_pct * 100, 1),
                "missing_items": missing_keys[:10],
            })

            await conn.execute(
                """
                INSERT INTO public.alert_trigger_history
                    (user_id, item_id, trigger_type, trigger_value, message)
                VALUES ($1, $2, 'completeness', $3::jsonb, $4)
                """,
                user_id,
                item_id_for_dedup,
                trigger_value,
                message,
            )

            # Send push notification (P0)
            try:
                from app.lib.notify import notify_user
                await notify_user(
                    conn,
                    str(user_id),
                    title="Complete Your Set!",
                    body=message,
                    category="price_alerts",
                    data={
                        "type": "set_completion",
                        "set_id": str(set_id),
                        "progress": f"{owned_count}/{total_items}",
                    },
                )
            except Exception as push_err:
                logger.debug("Push skipped for completion alert: %s", push_err)

            fired += 1
            logger.info(
                "Set completion alert: user=%s set=%s owned=%d/%d (%.0f%%)",
                user_id, set_id, owned_count, total_items, completion_pct * 100,
            )

    return fired


# ── Main Entry Points ────────────────────────────────────────────────────────


@with_async_retry(max_retries=3, base_delay=1.0, max_delay=60.0)
async def run_once():
    """Execute a single monitoring cycle."""
    if not DSN:
        logger.error("DB_DSN not set in environment")
        record_run("price_monitor", "error")
        return

    conn = await asyncpg.connect(DSN)
    logger.info("Connected to DB — starting price monitor cycle")
    try:
        threshold_count = await check_threshold_alerts(conn)
        anomaly_count = await detect_anomalies(conn)
        completion_count = await check_set_completions(conn)

        logger.info(
            "Price monitor cycle complete: threshold=%d anomaly=%d completion=%d",
            threshold_count,
            anomaly_count,
            completion_count,
        )
    finally:
        await conn.close()
        record_run("price_monitor", "ok")


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run("price_monitor", "error")
        log_dead_letter("price_monitor_worker", {}, e)
        logger.exception("price_monitor_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
