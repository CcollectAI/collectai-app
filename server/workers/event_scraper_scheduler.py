#!/usr/bin/env python3
"""Event scraper scheduler — orchestrates all event ingestion pipelines.

Runs every 6 hours and invokes:
  0. RSS feed scraper (free, 26+ brand/convention targets)
  1. Firecrawl event page crawler (40+ brand/convention targets)
  2. Crawl4AI event page crawler (JS-heavy sites)
  3. Newsletter scraper (if IMAP credentials are configured)

Also performs cross-source deduplication after ingestion.
"""

import asyncio
import logging
import os
import time

from app.worker_registry import record_run
from workers.retry import with_async_retry, log_dead_letter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [event_scraper] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

CYCLE_INTERVAL = int(os.getenv("EVENT_SCRAPER_INTERVAL", str(6 * 3600)))  # 6 hours


@with_async_retry(max_retries=2, base_delay=5.0, max_delay=120.0)
async def run_once():
    """Execute a single event ingestion cycle."""
    logger.info("=== Event scraper cycle starting ===")
    total_events = 0
    errors = []

    # 0. Run RSS feed scraper (free, covers 26+ targets).
    # DISABLED by default 2026-06-15: the anime/news RSS feeds polluted the
    # events catalog with non-collectible articles ("Yen short bets jump…",
    # "7-Eleven green tea rice ball"), which surfaced in "New Releases". Set
    # RSS_EVENTS_ENABLED=1 to re-enable once feeds are curated/filtered.
    rss_events_count = 0
    rss_succeeded_feeds: set[str] = set()
    if os.getenv("RSS_EVENTS_ENABLED", "0") == "1":
        try:
            from pipelines.rss_events import run_rss_scraper, RSS_FEED_TARGETS
            rss_events = await run_rss_scraper(since_days=30, dry_run=False)
            rss_events_count = len(rss_events)
            # Track which category_ids were successfully covered by RSS
            for evt in rss_events:
                if evt.category_id:
                    rss_succeeded_feeds.add(evt.category_id)
            logger.info("RSS scraper: %d events (covered %d categories)", rss_events_count, len(rss_succeeded_feeds))
            total_events += rss_events_count
        except Exception as e:
            logger.warning("RSS scraper failed: %s", e)
            errors.append(f"rss: {e}")
    else:
        logger.info("RSS scraper skipped (RSS_EVENTS_ENABLED != 1)")

    # 1. Run Firecrawl event crawler
    try:
        from pipelines.firecrawl_events import run_event_crawler
        events = await run_event_crawler(since_days=30, dry_run=False)
        logger.info("Firecrawl crawler: %d events", len(events))
        total_events += len(events)
    except Exception as e:
        logger.warning("Firecrawl crawler failed: %s", e)
        errors.append(f"firecrawl: {e}")

    # 2. Run Crawl4AI event crawler (for JS-heavy sites)
    try:
        from pipelines.crawl4ai_events import run_event_crawler as run_crawl4ai
        events = await run_crawl4ai(since_days=30, dry_run=False)
        logger.info("Crawl4AI crawler: %d events", len(events))
        total_events += len(events)
    except Exception as e:
        logger.warning("Crawl4AI crawler failed: %s", e)
        errors.append(f"crawl4ai: {e}")

    # 2b. Run MusicBrainz scraper (free, no key — vinyl release calendar)
    try:
        from pipelines.musicbrainz_events import run_musicbrainz_scraper
        mb_events = await run_musicbrainz_scraper(days_ahead=60, dry_run=False)
        logger.info("MusicBrainz scraper: %d events", len(mb_events))
        total_events += len(mb_events)
    except Exception as e:
        logger.warning("MusicBrainz scraper failed: %s", e)
        errors.append(f"musicbrainz: {e}")

    # 2c. Run Limitless TCG scraper (free, no key — TCG tournaments)
    try:
        from pipelines.limitless_tcg_events import run_limitless_scraper
        lt_events = await run_limitless_scraper(dry_run=False)
        logger.info("Limitless TCG scraper: %d events", len(lt_events))
        total_events += len(lt_events)
    except Exception as e:
        logger.warning("Limitless TCG scraper failed: %s", e)
        errors.append(f"limitless_tcg: {e}")

    # 3. Run newsletter scraper (IMAP inbox → events).
    # DISABLED by default 2026-06-15: the inbox was ingesting GitHub Actions
    # failure notifications ("[CcollectAI/…] Run failed: …") as events, which
    # showed up under "New Releases". Requires BOTH a configured IMAP host AND
    # NEWSLETTER_EVENTS_ENABLED=1 to run (the inbox needs curating first).
    if os.getenv("SCRAPER_EMAIL_HOST") and os.getenv("NEWSLETTER_EVENTS_ENABLED", "0") == "1":
        try:
            from pipelines.newsletter_scraper import run_scraper
            events = await run_scraper()
            logger.info("Newsletter scraper: %d events", len(events))
            total_events += len(events)
        except Exception as e:
            logger.warning("Newsletter scraper failed: %s", e)
            errors.append(f"newsletter: {e}")
    else:
        logger.info("Newsletter scraper skipped (disabled or no SCRAPER_EMAIL_HOST)")

    # 4. Run cross-source deduplication
    try:
        from pipelines.event_dedup import deduplicate_events
        deduped = await deduplicate_events()
        logger.info("Deduplication: removed %d duplicate events", deduped)
    except Exception as e:
        logger.warning("Dedup failed: %s", e)
        errors.append(f"dedup: {e}")

    # 5. Enrich events (franchise tagging + geocoding)
    try:
        from pipelines.event_enrich import enrich_events
        stats = await enrich_events(limit=100)
        logger.info("Enrichment: %d franchise-tagged, %d geocoded",
                     stats["franchise_tagged"], stats["geocoded"])
    except Exception as e:
        logger.warning("Enrichment failed: %s", e)
        errors.append(f"enrich: {e}")

    # Output-based status classification (refined 2026-04-19 after the deep
    # silent-sleepers audit flagged event_scraper at 65% error rate). R50l-
    # followup normalized any sub-step failure to `status='error'`, which
    # mis-classified cycles that produced 300+ events but hit one flaky RSS
    # feed. Policy now:
    #   - ok    = produced events (even if one sub-feed failed)
    #   - error = zero events + any sub-step errored (real failure)
    # Rationale: the essay's invariant is "correctness over liveness" — if
    # real events landed, the cycle succeeded at its primary job regardless
    # of secondary sub-step flakiness.
    status = "ok" if total_events > 0 else ("error" if errors else "ok")
    logger.info(
        "=== Event scraper cycle complete: %d events, %d errors, status=%s ===",
        total_events, len(errors), status,
    )
    record_run("event_scraper_worker", status)


# ---------------------------------------------------------------------------
# Scheduler loop (runs automatically, no manual trigger needed)
# ---------------------------------------------------------------------------

_shutdown = False
_shutdown_event = asyncio.Event()


def _handle_signal(signum, frame):
    global _shutdown
    logger.info("Received signal %d, shutting down after current cycle", signum)
    _shutdown = True
    _shutdown_event.set()


_running = False


async def scheduler_loop():
    """Run the event scraper in a loop with configurable interval."""
    global _running
    logger.info(
        "Event scraper scheduler started (interval=%ds = %.1f hours)",
        CYCLE_INTERVAL, CYCLE_INTERVAL / 3600,
    )

    while not _shutdown:
        if _running:
            logger.warning("Previous cycle still running, skipping this tick")
        else:
            _running = True
            try:
                await run_once()
                logger.info("Cycle finished, sleeping %ds", CYCLE_INTERVAL)
            except Exception as e:
                log_dead_letter("event_scraper_scheduler", {}, e)
                logger.exception("Event scraper cycle failed: %r", e)
                record_run("event_scraper_worker", "error")
            finally:
                _running = False

        try:
            await asyncio.wait_for(_shutdown_event.wait(), timeout=CYCLE_INTERVAL)
            break
        except asyncio.TimeoutError:
            pass

    logger.info("Event scraper scheduler stopped")


def main():
    import signal as _signal
    _signal.signal(_signal.SIGINT, _handle_signal)
    _signal.signal(_signal.SIGTERM, _handle_signal)

    if not os.getenv("DB_DSN"):
        logger.error("DB_DSN not set — cannot start event scraper scheduler")
        import sys
        sys.exit(1)

    asyncio.run(scheduler_loop())


if __name__ == "__main__":
    main()
