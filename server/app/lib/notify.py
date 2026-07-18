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
    """Fetch notification preferences for a user. Returns defaults if not set.

    user_settings has no notification_preferences column (round-2 silent-
    failure sweep 2026-04-20). Returns empty dict so call sites fall
    through to all-enabled defaults. No DB round-trip — the previous
    probe-for-user-id was dead code the grep flagged in round 4.
    """
    return {}


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


async def _user_follows_category(conn, user_id: str, category_slug: str) -> bool:
    """True if the user follows this collectible category. Used to scope
    discovery-style notifications (deal_alerts, weekly_digest) so we don't
    push noise from categories the user explicitly told us they don't care
    about during onboarding. Fail-open: any DB error returns True so we
    don't silently swallow notifications during outages."""
    try:
        row = await conn.fetchrow(
            "SELECT 1 FROM public.user_category_follows WHERE user_id = $1 AND category_id = $2",
            user_id, category_slug,
        )
        return row is not None
    except Exception:
        return True


# notify_user takes a PREFERENCE key (plural: "price_alerts"); the RN feed maps
# an icon from a notification TYPE (singular: "price_alert", see
# app/notifications.tsx TYPE_ICONS). Those two vocabularies drifted apart, so
# every row written with the raw category fell through to the generic
# "notifications-outline" fallback. Translate here, at the one place that
# writes the type, rather than teaching the FE every server-side spelling.
# Keys here MUST be the preference keys on the right-hand side of
# ALERT_TYPE_TO_PREF above (that's the existing source of truth for what a
# category is called); values MUST be keys of TYPE_ICONS in
# app/notifications.tsx. Anything else silently renders the fallback icon.
_FEED_TYPE_BY_CATEGORY = {
    "price_alerts": "price_alert",
    "deal_alerts": "deal_alert",
    "value_changes": "value_change",
    "item_value_changes": "value_change",
    "weekly_digest": "insight",          # no weekly_digest icon; insight fits
    "chat_messages": "chat",
    "connection_requests": "connection",
    "event_announcements": "event",
}


def _feed_type(category: str) -> str:
    """Map a notify preference category to an FE-renderable notification type.

    Unmapped categories pass through unchanged AND log a warning — the FE falls
    back to a generic icon either way, but a silent fallback is how this drift
    went unnoticed in the first place. A warning here makes the next mismatch
    visible instead of just ugly. (It also surfaces callers passing a
    COLLECTIBLE category like "pokemon" into the notification-category slot.)
    """
    mapped = _FEED_TYPE_BY_CATEGORY.get(category)
    if mapped:
        return mapped
    if category not in ("test",):
        logger.warning(
            "[notify] category %r has no FE icon mapping — feed will show the "
            "generic fallback. Add it to _FEED_TYPE_BY_CATEGORY or fix the caller.",
            category,
        )
    return category


async def _persist_only(
    conn,
    user_id: str,
    title: str,
    body: str,
    category: str,
    data: Optional[dict[str, Any]] = None,
    deep_link: Optional[str] = None,
) -> None:
    """Record a notification in the in-app feed WITHOUT delivering a push.

    Used on the paths where we deliberately decline to interrupt the user
    (followed-category filter, daily frequency cap) but the event is still
    worth showing when they open the inbox themselves. Before this, those
    branches returned early and the event was lost entirely — the cap silenced
    the record, not just the push.

    Reuses app.push._persist_notification so there is exactly ONE INSERT
    statement against notification_history in the codebase. Never raises;
    persistence failures must not break a caller's notification loop.
    """
    try:
        from app.push import _persist_notification
        await _persist_notification(
            conn, user_id, title, body,
            notification_type=_feed_type(category), data=data, deep_link=deep_link,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[notify] in-app persist failed for user %s: %s", user_id[:8], exc)


async def notify_user(
    conn,
    user_id: str,
    title: str,
    body: str,
    category: str = "price_alerts",
    data: Optional[dict[str, Any]] = None,
    deep_link: Optional[str] = None,
    urgent: bool = False,
    collectible_category: Optional[str] = None,
) -> int:  # noqa: D401 — see _persist_only for the in-app/push split
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
        collectible_category: optional collectible category slug (e.g. 'pokemon',
            'lego'). When set AND the user has at least one followed category
            on record, the push is dropped if the slug isn't in the follow list.
            This scopes discovery notifications to onboarding picks without
            affecting "user owns this item" notifications, which already gate
            on item ownership upstream and should leave this argument unset.

    Returns: number of pushes sent (0 if blocked by pref/cap/follow filter)
    """
    try:
        # Check preference (always)
        prefs = await _get_user_prefs(conn, user_id)
        if not prefs.get(category, True):
            logger.debug("[notify] Skipped: user %s disabled %s", user_id[:8], category)
            return 0

        # Discovery-style notifications honor the user's followed categories
        # so onboarding picks actually drive what they see. Skipped when caller
        # doesn't pass a slug (= notification is about something the user
        # already owns / explicitly tracks).
        if collectible_category:
            row = await conn.fetchrow(
                "SELECT count(*)::int AS c FROM public.user_category_follows WHERE user_id = $1",
                user_id,
            )
            has_any_follows = bool(row and row["c"] > 0)
            if has_any_follows:
                if not await _user_follows_category(conn, user_id, collectible_category):
                    logger.debug(
                        "[notify] Skipped push: user %s does not follow category %s",
                        user_id[:8], collectible_category,
                    )
                    # Still record it in the in-app feed. The follow filter is
                    # about what we're willing to interrupt someone with, not
                    # about hiding the event from the inbox they chose to open.
                    await _persist_only(conn, user_id, title, body, category, data, deep_link)
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
                    "[notify] Skipped push: user %s hit daily cap (%d/%d)",
                    user_id[:8], count, cap,
                )
                # The cap exists to stop us spamming someone's lock screen, not
                # to erase the event. Record it in-app so it's waiting for them.
                await _persist_only(conn, user_id, title, body, category, data, deep_link)
                return 0

        # Send via existing push infrastructure. send_push_to_user persists to
        # notification_history itself (before it checks for tokens), so this
        # branch must NOT call _persist_only or the row would be duplicated.
        # notification_type=category so the feed shows the real kind
        # (price_alerts, deal_alerts, …) instead of a uniform 'push'.
        from app.push import send_push_to_user
        sent = await send_push_to_user(
            conn,
            user_id,
            title,
            body,
            data=data,
            notification_type=_feed_type(category),
            deep_link=deep_link,
        )
        if sent > 0:
            logger.debug("[notify] Sent %d push(es) to user %s: %s", sent, user_id[:8], category)
        return sent

    except Exception as exc:
        logger.warning("[notify] Failed for user %s: %s", user_id[:8], exc)
        return 0
