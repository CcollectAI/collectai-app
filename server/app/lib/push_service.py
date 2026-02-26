"""
Push notification service.

Sends notifications via Expo Push Notifications API.
Requires push tokens registered via POST /notifications/register.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app import config as _config  # noqa: F401 – kept for future config access

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


async def send_push(
    push_token: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
    channel_id: str | None = None,
    badge: int | None = None,
) -> bool:
    """Send a single push notification via Expo.

    Returns True if sent successfully, False otherwise.
    """
    payload: dict[str, Any] = {
        "to": push_token,
        "title": title,
        "body": body,
        "sound": "default",
    }
    if data:
        payload["data"] = data
    if channel_id:
        payload["channelId"] = channel_id
    if badge is not None:
        payload["badge"] = badge

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(EXPO_PUSH_URL, json=payload)
            resp.raise_for_status()
            result = resp.json()
            if result.get("data", {}).get("status") == "error":
                logger.warning("Push notification error: %s", result["data"].get("message"))
                return False
            return True
    except Exception:
        logger.exception("Failed to send push notification")
        return False


async def send_push_batch(
    tokens: list[str],
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
    channel_id: str | None = None,
) -> int:
    """Send push notification to multiple tokens.

    Returns count of successfully sent notifications.
    """
    if not tokens:
        return 0

    messages = []
    for token in tokens:
        msg: dict[str, Any] = {
            "to": token,
            "title": title,
            "body": body,
            "sound": "default",
        }
        if data:
            msg["data"] = data
        if channel_id:
            msg["channelId"] = channel_id
        messages.append(msg)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(EXPO_PUSH_URL, json=messages)
            resp.raise_for_status()
            result = resp.json()
            # Expo returns {"data": [...]} for batch
            items = result.get("data", [])
            return sum(1 for item in items if item.get("status") == "ok")
    except Exception:
        logger.exception("Failed to send batch push notifications")
        return 0


# Convenience helpers for common notification types


async def notify_chat_message(push_token: str, sender_name: str, preview: str, thread_id: str) -> bool:
    return await send_push(
        push_token,
        title=f"Message from {sender_name}",
        body=preview[:100],
        data={"thread_id": thread_id},
        channel_id="chat",
    )


async def notify_price_alert(push_token: str, item_name: str, alert_type: str, item_id: str) -> bool:
    return await send_push(
        push_token,
        title="Price Alert",
        body=f"{item_name}: {alert_type}",
        data={"item_id": item_id, "alert_id": "price"},
        channel_id="alerts",
    )


async def notify_connection_request(push_token: str, from_name: str, request_id: str) -> bool:
    return await send_push(
        push_token,
        title="Connection Request",
        body=f"{from_name} wants to connect",
        data={"connection_request_id": request_id},
        channel_id="social",
    )


async def notify_event_announcement(
    push_token: str, event_title: str, announcement_title: str, event_id: str, announcement_id: str
) -> bool:
    return await send_push(
        push_token,
        title=f"Announcement: {event_title}",
        body=announcement_title[:100],
        data={"event_id": event_id, "announcement_id": announcement_id},
        channel_id="events",
    )
