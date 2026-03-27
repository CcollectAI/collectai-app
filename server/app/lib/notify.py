"""
Shared notification helper — preference-aware, frequency-capped push delivery.

Usage:
    from app.lib.notify import notify_user

    await notify_user(
        conn, user_id,
        title="Price Alert",
        body="Your Charizard dropped to €150",
        category="price_alerts",       # matches user preference key
        data={"type": "price_alert", "item_id": "..."},
        urgent=False,                   # urgent=True bypasses send-time optimization
    )
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Frequency caps per 24h window
FREE_DAILY_CAP = 3
PRO_DAILY_CAP = 15
PREMIUM_DAILY_CAP = 30

# Preference key → notification category mapping
ALERT_TYPE_TO_PREF = {
    "price_alert": "price_alerts",
    "watchlist_target_met": "price_alerts",
    "below_threshold": "price_alerts",
    "price_spike": "price_alerts",
    "price_drop": "price_alerts",
    "completeness": "price_alerts",
    "low_value": "price_alerts",
    "deal_alert": "deal_alerts",
    "value_change": "value_changes",
    "item_value_change": "item_value_changes",
    "weekly_digest": "weekly_digest",
    "chat_message": "chat_messages",
    "connection_request": "connection_requests",
    "event_announcement": "event_announcements",
}


async def _get_user_prefs(conn, user_id: str) -> dict:
    """Fetch notification preferences for a user. Returns defaults if not set."""
    row = await conn.fetchrow(
        "SELECT notification_preferences FROM public.user_settings WHERE user_id = $1",
        user_id,
    )
    if row and row["notification_preferences"]:
        import json
        prefs = row["notification_preferences"]
        if isinstance(prefs, str):
            prefs = json.loads(prefs)
        return prefs
    return {}  # empty = use defaults (all True)


async def _get_daily_push_count(conn, user_id: str) -> int:
    """Count push notifications sent to user in last 24 hours."""
    row = await conn.fetchrow(
        """
        SELECT count(*) AS cnt FROM public.notification_history
        WHERE user_id = $1
          AND created_at > now() - interval '24 hours'
        """,
        user_id,
    )
    return row["cnt"] if row else 0


async def _get_user_tier(conn, user_id: str) -> str:
    """Get user subscription tier. Returns 'free', 'pro', or 'premium'."""
    row = await conn.fetchrow(
        "SELECT subscription_tier FROM public.user_settings WHERE user_id = $1",
        user_id,
    )
    if row and row["subscription_tier"]:
        return row["subscription_tier"]
    return "free"


async def should_notify(
    conn,
    user_id: str,
    category: str,
) -> tuple[bool, str]:
    """
    Check if we should send a push notification to this user.

    Returns (allowed: bool, reason: str).
    """
    # 1. Check user preference
    prefs = await _get_user_prefs(conn, user_id)
    if not prefs.get(category, True):  # Default True if key missing
        return False, f"user disabled {category}"

    # 2. Check frequency cap
    count = await _get_daily_push_count(conn, user_id)
    tier = await _get_user_tier(conn, user_id)
    cap = {
        "free": FREE_DAILY_CAP,
        "pro": PRO_DAILY_CAP,
        "premium": PREMIUM_DAILY_CAP,
    }.get(tier, FREE_DAILY_CAP)

    if count >= cap:
        return False, f"daily cap reached ({count}/{cap} for {tier})"

    return True, "ok"


async def notify_user(
    conn,
    user_id: str,
    title: str,
    body: str,
    category: str = "price_alerts",
    data: Optional[dict[str, Any]] = None,
    deep_link: Optional[str] = None,
    urgent: bool = False,
) -> int:
    """
    Send a preference-aware, frequency-capped push notification.

    Args:
        conn: asyncpg connection
        user_id: target user UUID string
        title: notification title
        body: notification body text
        category: preference key (price_alerts, deal_alerts, etc.)
        data: custom data payload for the push
        deep_link: optional deep link URL
        urgent: if True, skip frequency cap (but still check preference)

    Returns: number of pushes sent (0 if blocked by pref/cap)
    """
    try:
        # Check preference (always)
        prefs = await _get_user_prefs(conn, user_id)
        if not prefs.get(category, True):
            logger.debug("[notify] Skipped: user %s disabled %s", user_id[:8], category)
            return 0

        # Check frequency cap (skip for urgent)
        if not urgent:
            count = await _get_daily_push_count(conn, user_id)
            tier = await _get_user_tier(conn, user_id)
            cap = {
                "free": FREE_DAILY_CAP,
                "pro": PRO_DAILY_CAP,
                "premium": PREMIUM_DAILY_CAP,
            }.get(tier, FREE_DAILY_CAP)

            if count >= cap:
                logger.debug(
                    "[notify] Skipped: user %s hit daily cap (%d/%d)",
                    user_id[:8], count, cap,
                )
                return 0

        # Send via existing push infrastructure
        from app.push import send_push_to_user
        sent = await send_push_to_user(
            conn,
            user_id,
            title,
            body,
            data=data,
            deep_link=deep_link,
        )
        if sent > 0:
            logger.debug("[notify] Sent %d push(es) to user %s: %s", sent, user_id[:8], category)
        return sent

    except Exception as exc:
        logger.warning("[notify] Failed for user %s: %s", user_id[:8], exc)
        return 0
