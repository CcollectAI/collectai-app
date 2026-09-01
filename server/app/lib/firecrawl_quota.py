"""Firecrawl credit guard — stop calling when the plan is spent.

WHY THIS EXISTS (2026-09-01)

The watchdog reported bake erroring for 30 minutes straight. It had actually
been erroring for two days: `[Firecrawl] /search HTTP 402` first appeared
2026-08-30 00:00 and ran **79 times on 2026-09-01 alone**.

402 is Payment Required — the plan is spent. Measured:

    {"remaining_credits": -2, "plan_credits": 1000,
     "billing_period_end": "2026-09-04T20:03:15.505Z"}

Overdrawn, and three days from resetting. `firecrawl_client` special-cases
**429** and nothing else, so a 402 fell through to `raise_for_status()`, was
logged, returned None — and the next cycle tried again. Nothing anywhere
recorded that the credits were gone.

A rate limit is transient and worth retrying. **A spent plan is not**, and
retrying it produces a log full of identical errors that trains people to
ignore the channel — the cost this repo already records for a permanently-red
gate.

Mirrors app/lib/scrapedo_quota.py: the source of truth is THEIRS, read from
their own endpoint rather than counted locally, because a local counter resets
on deploy and their credit balance does not.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.cache import cache_get, cache_set
from app.config import FIRECRAWL_API_KEY

logger = logging.getLogger(__name__)

_USAGE_URL = "https://api.firecrawl.dev/v1/team/credit-usage"
_CACHE_KEY = "firecrawl:credits"
_EXHAUSTED_KEY = "firecrawl:exhausted_until"
_CACHE_TTL = 900          # 15 min, same reasoning as scrapedo_quota
_RESERVE = 20             # stop before zero; our view is up to _CACHE_TTL stale
# Cap on how long a single 402 silences calls. The billing date from the API is
# preferred; this is the fallback when the response cannot be parsed, and it is
# deliberately short so a MISREAD cannot mute Firecrawl for a month.
_MAX_BACKOFF_S = 6 * 3600


async def fetch_credits() -> Optional[dict]:
    """Ask Firecrawl what is left. None when it cannot be asked."""
    if not FIRECRAWL_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(_USAGE_URL, headers={"Authorization": f"Bearer {FIRECRAWL_API_KEY}"})
            r.raise_for_status()
            data = (r.json() or {}).get("data") or {}
        if not isinstance(data.get("remaining_credits"), int):
            logger.error("[firecrawl_quota] credit-usage returned no integer "
                         "remaining_credits (got %r) — cannot meter",
                         data.get("remaining_credits"))
            return None
        return data
    except Exception as e:
        logger.warning("[firecrawl_quota] credit-usage unreachable: %s: %s", type(e).__name__, e)
        return None


def note_exhausted(billing_period_end: Optional[str] = None) -> None:
    """Called on a 402. Silences further calls until the plan resets.

    The billing date comes from Firecrawl when we have it; otherwise a short
    backoff. Never an unbounded mute — a misparsed date that silenced scraping
    for a month would be a worse failure than the one being fixed.
    """
    ttl = _MAX_BACKOFF_S
    if billing_period_end:
        try:
            end = datetime.fromisoformat(billing_period_end.replace("Z", "+00:00"))
            secs = int((end - datetime.now(timezone.utc)).total_seconds())
            if 0 < secs < 40 * 24 * 3600:
                ttl = secs
        except (ValueError, TypeError):
            pass
    cache_set(_EXHAUSTED_KEY, True, ttl=ttl)
    logger.error(
        "[firecrawl_quota] PLAN SPENT (HTTP 402). Suppressing Firecrawl calls "
        "for %.1f hours. This is not a rate limit — retrying it just fills the "
        "log until the plan resets.", ttl / 3600.0,
    )


async def allow() -> bool:
    """Whether a Firecrawl call may be made right now."""
    if cache_get(_EXHAUSTED_KEY):
        return False
    cached = cache_get(_CACHE_KEY)
    if isinstance(cached, int):
        return cached > _RESERVE
    data = await fetch_credits()
    if data is None:
        # Unknown is NOT "plenty". But unlike Scrape.do's hard monthly cap, an
        # over-spend here bills rather than silently truncating, so failing
        # closed on one unreachable request would take scraping down for a
        # transient. Allow, and let a real 402 latch the suppression above.
        return True
    remaining = data["remaining_credits"]
    cache_set(_CACHE_KEY, remaining, ttl=_CACHE_TTL)
    if remaining <= _RESERVE:
        note_exhausted(data.get("billing_period_end"))
        return False
    return True
