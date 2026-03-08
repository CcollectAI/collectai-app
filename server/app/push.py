"""
Expo Push Notification helper.

Usage:
    from app.push import send_push, send_push_to_user

    # Send to a specific token
    await send_push("ExponentPushToken[xxx]", "Title", "Body")

    # Send to all active tokens for a user
    await send_push_to_user(conn, user_id, "Title", "Body", data={"item_id": "..."})
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


async def send_push(
    token: str,
    title: str,
    body: str,
    data: Optional[dict[str, Any]] = None,
    badge: Optional[int] = None,
    sound: str = "default",
) -> bool:
    """
    Send a single push notification via Expo Push API.

    Returns True if the API accepted the message (does not guarantee delivery).
    """
    message: dict[str, Any] = {
        "to": token,
        "title": title,
        "body": body,
        "sound": sound,
    }
    if data:
        message["data"] = data
    if badge is not None:
        message["badge"] = badge

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                EXPO_PUSH_URL,
                json=message,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
            if resp.status_code != 200:
                logger.warning("[push] Expo API returned %d: %s", resp.status_code, resp.text[:200])
                return False

            result = resp.json()
            ticket = result.get("data", {})
            if ticket.get("status") == "error":
                logger.warning("[push] Expo error: %s — %s", ticket.get("message"), token)
                # Deactivate invalid tokens
                if ticket.get("details", {}).get("error") == "DeviceNotRegistered":
                    logger.info("[push] Token no longer valid, should deactivate: %s", token[:20])
                return False

            return True

    except (httpx.HTTPError, OSError) as exc:
        logger.warning("[push] Failed to send push to %s: %s", token[:20], exc)
        return False


async def _persist_notification(
    conn,
    user_id: str,
    title: str,
    body: str,
    notification_type: str = "push",
    data: Optional[dict[str, Any]] = None,
    deep_link: Optional[str] = None,
) -> None:
    """
    Best-effort INSERT into notification_history table.

    Never raises — errors are logged and swallowed so push delivery
    is not blocked by persistence failures.
    """
    try:
        import json as _json

        await conn.execute(
            """
            INSERT INTO notification_history (user_id, type, title, body, data, deep_link)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6)
            """,
            user_id,
            notification_type,
            title,
            body,
            _json.dumps(data) if data else "{}",
            deep_link,
        )
    except Exception as exc:
        logger.warning("[push] Failed to persist notification for user %s: %s", user_id, exc)


async def send_push_to_user(
    conn,
    user_id: str,
    title: str,
    body: str,
    data: Optional[dict[str, Any]] = None,
    notification_type: str = "push",
    deep_link: Optional[str] = None,
) -> int:
    """
    Send push notification to all active tokens for a user.

    Also persists the notification to the notification_history table
    (best-effort — failures are logged but do not block delivery).

    Returns the number of successfully sent notifications.
    """
    # Best-effort persistence to notification_history
    await _persist_notification(
        conn,
        user_id,
        title,
        body,
        notification_type=notification_type,
        data=data,
        deep_link=deep_link,
    )

    rows = await conn.fetch(
        "SELECT push_token FROM public.user_push_tokens WHERE user_id = $1 AND active = true",
        user_id,
    )

    if not rows:
        return 0

    sent = 0
    for row in rows:
        ok = await send_push(row["push_token"], title, body, data=data)
        if ok:
            sent += 1

    return sent
