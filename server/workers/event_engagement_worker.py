#!/usr/bin/env python3
"""Event engagement worker — turns event demand signals into a numeric
score on the events table that ranking can ORDER BY.

Closes the loop:
  user views/follows/RSVPs/clicks-ticket → demand_signals + event_follows_v1
  + event_attendees → event_engagement_worker recomputes
  events.engagement_score → events feed ranks by combined engagement

Why a separate column from quality_score:
  events.quality_score is a RULE-BASED trust metric set at ingest by
  app/lib/event_quality.py (verified source, has dates, has location,
  etc.). Conflating it with engagement would let a popular but unverified
  event outrank a trusted one — bad. Two columns, two concepts:
    quality_score   (0-100)  — "is this event real and well-formed?"
    engagement_score (0-N)   — "are users actually interacting with it?"

Schema: lazy-ensure at run_once. Adds engagement_score numeric column on
first run if absent (matches catalog_crawler._ensure_last_crawled_column
pattern). No external migration needed.

Formula (weighted; weights tuned to put a single ticket-click ≈ 20 views):
  engagement = views + 5*follows + 10*rsvps + 20*ticket_clicks

Lookback: last 30 days of demand signals; follows + attendees are
lifetime (not time-windowed) to capture deferred interest.
"""

from __future__ import annotations

import asyncio
import logging
import os

import asyncpg

from app.worker_registry import record_run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [event_engagement] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN_DIRECT") or os.getenv("DB_DSN")
LOOKBACK_DAYS = int(os.getenv("EVENT_ENGAGEMENT_LOOKBACK_DAYS", "30"))

W_VIEW = float(os.getenv("EVENT_W_VIEW", "1.0"))
W_FOLLOW = float(os.getenv("EVENT_W_FOLLOW", "5.0"))
W_RSVP = float(os.getenv("EVENT_W_RSVP", "10.0"))
W_TICKET_CLICK = float(os.getenv("EVENT_W_TICKET_CLICK", "20.0"))


async def _ensure_engagement_column(conn) -> None:
    """Idempotently add engagement_score column to events if missing."""
    exists = await conn.fetchval(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'events'
              AND column_name = 'engagement_score'
        )
        """
    )
    if not exists:
        await conn.execute(
            "ALTER TABLE public.events ADD COLUMN engagement_score numeric DEFAULT 0"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_engagement_score "
            "ON public.events (engagement_score DESC NULLS LAST) "
            "WHERE status != 'cancelled'"
        )
        logger.info("Added engagement_score column + index to events")


async def run_once() -> dict[str, int]:
    if not DSN:
        logger.warning("DB_DSN not set — skipping")
        record_run("event_engagement_worker", "error")
        return {"updated": 0}

    conn = await asyncpg.connect(DSN)
    try:
        await _ensure_engagement_column(conn)

        # Single grouped UPDATE: compute engagement per event from the four
        # source tables (demand_signals for views + ticket_clicks,
        # event_follows_v1 for follows, event_attendees for RSVPs) and
        # write it back. Done as a CTE-aggregated UPDATE so we don't
        # round-trip per event.
        result = await conn.execute(
            """
            WITH
            views AS (
                SELECT item_key AS event_id, COUNT(*) AS n
                FROM public.demand_signals
                WHERE signal_type = 'event_viewed'
                  AND item_key IS NOT NULL
                  AND created_at >= now() - ($1 || ' days')::interval
                GROUP BY item_key
            ),
            ticket_clicks AS (
                SELECT item_key AS event_id, COUNT(*) AS n
                FROM public.demand_signals
                WHERE signal_type = 'ticket_clicked'
                  AND item_key IS NOT NULL
                  AND created_at >= now() - ($1 || ' days')::interval
                GROUP BY item_key
            ),
            follows AS (
                SELECT canonical_key, COUNT(DISTINCT user_id) AS n
                FROM public.event_follows_v1
                WHERE enabled IS NOT FALSE
                GROUP BY canonical_key
            ),
            rsvps AS (
                SELECT event_id::text AS event_id, COUNT(*) AS n
                FROM public.event_attendees
                GROUP BY event_id
            )
            UPDATE public.events e
            SET engagement_score = (
                COALESCE((SELECT n FROM views        v WHERE v.event_id = e.id::text), 0) * $2
              + COALESCE((SELECT n FROM follows      f WHERE f.canonical_key = e.canonical_key), 0) * $3
              + COALESCE((SELECT n FROM rsvps        r WHERE r.event_id = e.id::text), 0) * $4
              + COALESCE((SELECT n FROM ticket_clicks t WHERE t.event_id = e.id::text), 0) * $5
            )
            WHERE e.status != 'cancelled'
            """,
            str(LOOKBACK_DAYS), W_VIEW, W_FOLLOW, W_RSVP, W_TICKET_CLICK,
        )
        # asyncpg .execute returns "UPDATE N"
        n_updated = int(result.split()[-1]) if result and result.split() else 0
        logger.info(
            "event_engagement cycle complete: scored %d events "
            "(weights view=%.1f follow=%.1f rsvp=%.1f ticket=%.1f, lookback=%dd)",
            n_updated, W_VIEW, W_FOLLOW, W_RSVP, W_TICKET_CLICK, LOOKBACK_DAYS,
        )
        record_run("event_engagement_worker", "ok")
        return {"updated": n_updated}
    finally:
        await conn.close()


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run("event_engagement_worker", "error")
        logger.exception("event_engagement_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
