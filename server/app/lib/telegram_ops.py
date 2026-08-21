"""
Telegram Ops Alert — sends budget and system alerts to a Telegram chat.

Usage:
    from app.lib.telegram_ops import send_ops_alert

    await send_ops_alert("Budget at 90%: 135.00/150.00 EUR")

Env vars:
    TELEGRAM_BOT_TOKEN  - Bot token from @BotFather
    TELEGRAM_CHAT_ID    - Chat/group ID to send alerts to
"""

from __future__ import annotations

import re
import logging
from typing import Optional

import httpx

from app.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

def configured() -> bool:
    """Return True if Telegram bot credentials are set."""
    return bool(TELEGRAM_BOT_TOKEN) and bool(TELEGRAM_CHAT_ID)


async def send_ops_alert(
    message: str,
    title: str | None = None,
    silent: bool = False,
) -> bool:
    """Send a message to the configured Telegram ops chat.

    Returns True on success, False on failure (never raises).

    Note: a fresh httpx.AsyncClient is created per call. Caching the client
    globally caused "Event loop is closed" errors when called from short-lived
    asyncio.run() contexts (e.g. spend_tracker._fire_telegram_alert from a
    background worker thread). We send ~3 alerts per month — the per-call
    client cost is negligible.
    """
    if not configured():
        logger.debug("Telegram ops not configured — skipping alert")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    # `title` lets routine reports opt out of the siren. A daily green digest
    # prefixed with 🚨 trains you to ignore the channel, which defeats the
    # point of having it — reserve the alarm for genuine pages.
    header = title if title is not None else "\U0001f6a8 Sparrow Ops"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": f"{header}\n\n{message}" if header else message,
        "parse_mode": "HTML",
        # Long digests are unreadable when Telegram expands every link.
        "disable_web_page_preview": True,
        "disable_notification": bool(silent),
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info("Telegram ops alert sent")
                return True
            body_text = resp.text or ""
            logger.warning("Telegram API returned %d: %s", resp.status_code, body_text[:200])
            # A malformed-HTML rejection must not cost us the MESSAGE. The
            # watchdog digest is the only daily channel, and it failed exactly
            # this way on 2026-08-19 ("Can't find end tag corresponding to
            # start tag \"code\"") — losing the whole report, silently. Retry
            # once as plain text: a readable digest with the tags stripped
            # beats no digest at all.
            if resp.status_code == 400 and "parse entities" in body_text:
                plain = dict(payload)
                plain.pop("parse_mode", None)
                plain["text"] = re.sub(r"<[^>]+>", "", payload["text"])
                retry = await client.post(url, json=plain)
                if retry.status_code == 200:
                    logger.warning("Telegram ops alert sent as PLAIN TEXT "
                                   "after an HTML parse rejection")
                    return True
                logger.warning("Telegram plain-text retry also failed: %d %s",
                               retry.status_code, (retry.text or "")[:200])
            return False
    except Exception as exc:
        logger.warning("Telegram ops alert failed: %s", exc)
        return False


async def send_budget_warning(pct: float, spent: float, budget: float) -> bool:
    """Send a formatted budget warning."""
    if pct >= 100:
        emoji = "\U0001f6d1"  # stop sign
        label = "BUDGET EXCEEDED"
    elif pct >= 90:
        emoji = "\U0001f534"  # red circle
        label = "BUDGET CRITICAL"
    elif pct >= 75:
        emoji = "\U0001f7e0"  # orange circle
        label = "BUDGET WARNING"
    else:
        return False

    msg = (
        f"{emoji} <b>{label}</b>\n\n"
        f"Spent: <b>\u20ac{spent:.2f}</b> / \u20ac{budget:.2f}\n"
        f"Usage: <b>{pct:.0f}%</b>\n"
        f"Remaining: \u20ac{budget - spent:.2f}"
    )
    return await send_ops_alert(msg)
