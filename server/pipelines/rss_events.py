"""
RSS/Atom feed event scraper — ZERO COST alternative to Firecrawl/Crawl4AI.

Most brand blogs, news pages, and WordPress sites expose RSS/Atom feeds.
This scraper fetches feeds directly via httpx, parses XML, and extracts
events without needing a headless browser or paid API.

Falls back gracefully — if a feed URL returns non-XML or 404, the target
is skipped (the crawler pipeline will pick it up instead).

Usage:
    from pipelines.rss_events import run_rss_scraper
    events = await run_rss_scraper(since_days=30)

    # Or standalone:
    python -m pipelines.rss_events [--dry-run] [--since 30]
"""

from __future__ import annotations

import asyncio
import argparse
import json
import logging
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Optional

import httpx

from pipelines.import_common import setup_logging

logger = setup_logging("collectai.rss_events")

# Reuse shared event infrastructure
from pipelines.newsletter_scraper import (
    ScrapedEvent,
    EventUpserter,
    _extract_dates,
    _classify_event_kind,
    _category_from_content,
)

# ---------------------------------------------------------------------------
# RSS Feed targets — maps to the same categories as firecrawl_events.py
# Most blogs use /feed, /rss, /blog/feed, or wp-json endpoints
# ---------------------------------------------------------------------------

RSS_FEED_TARGETS: list[dict[str, Any]] = [
    # ── Brand blogs (WordPress / standard RSS) ────────────────────────
    {"feed_url": "https://www.pokemon.com/us/pokemon-news/rss", "fallback_url": "https://www.pokemon.com/us/pokemon-news", "category_id": "pokemon", "kind_default": "release", "description": "Pokemon news"},
    {"feed_url": "https://magic.wizards.com/en/rss/rss.xml", "fallback_url": "https://magic.wizards.com/en/news", "category_id": "mtg", "kind_default": "release", "description": "MTG news"},
    {"feed_url": "https://www.warhammer-community.com/feed/", "fallback_url": "https://www.warhammer-community.com/latest-news/", "category_id": "warhammer", "kind_default": "release", "description": "Warhammer Community"},
    {"feed_url": "https://www.funko.com/blog/rss", "fallback_url": "https://www.funko.com/blog", "category_id": "funko", "kind_default": "collection_drop", "description": "Funko blog"},
    {"feed_url": "https://goodsmile-global.com/news/feed/", "fallback_url": "https://goodsmile-global.com/news/", "category_id": "anime_figures", "kind_default": "release", "description": "Good Smile Company"},
    {"feed_url": "https://www.sideshow.com/blog/feed/", "fallback_url": "https://www.sideshow.com/whats-new", "category_id": "hot_toys", "kind_default": "collection_drop", "description": "Sideshow Collectibles"},
    {"feed_url": "https://hasbropulse.com/blogs/hasbro-pulse-blog.atom", "fallback_url": "https://hasbropulse.com/blogs/hasbro-pulse-blog", "category_id": "action_figures", "kind_default": "collection_drop", "description": "Hasbro Pulse"},
    {"feed_url": "https://news.bandainamco.com/en/feed/", "fallback_url": "https://news.bandainamco.com/en/", "category_id": "gunpla", "kind_default": "release", "description": "Bandai Namco"},
    {"feed_url": "https://www.topps.com/blog/feed/", "fallback_url": "https://www.topps.com/blog", "category_id": "sportscards", "kind_default": "collection_drop", "description": "Topps"},
    {"feed_url": "https://blog.tcgplayer.com/feed/", "fallback_url": "https://tcgplayer.com/blog", "category_id": "pokemon", "kind_default": "release", "description": "TCGPlayer blog"},
    {"feed_url": "https://sneakernews.com/feed/", "fallback_url": "https://sneakernews.com/release-dates/", "category_id": "sneakers", "kind_default": "collection_drop", "description": "Sneaker News"},
    {"feed_url": "https://blog.discogs.com/en/feed/", "fallback_url": "https://www.discogs.com/blog", "category_id": "vinyl", "kind_default": "release", "description": "Discogs blog"},
    {"feed_url": "https://recordstoreday.com/feed/", "fallback_url": "https://recordstoreday.com/", "category_id": "vinyl", "kind_default": "collection_drop", "description": "Record Store Day"},
    {"feed_url": "https://www.hodinkee.com/feed", "fallback_url": "https://www.hodinkee.com/articles", "category_id": "watches", "kind_default": "release", "description": "Hodinkee"},
    {"feed_url": "https://disneyparks.disney.go.com/blog/feed/", "fallback_url": "https://disneyparks.disney.go.com/blog/", "category_id": "disney", "kind_default": "collection_drop", "description": "Disney Parks Blog"},
    {"feed_url": "https://www.fragrantica.com/news/rss.html", "fallback_url": "https://www.fragrantica.com/news/", "category_id": "fragrances", "kind_default": "release", "description": "Fragrantica news"},
    {"feed_url": "https://www.penworld.eu/blog/feed/", "fallback_url": "https://www.penworld.eu/blog/", "category_id": "pens", "kind_default": "release", "description": "Penworld blog"},

    # ── Convention / event pages (try RSS, many have feeds) ───────────
    {"feed_url": "https://www.comic-con.org/feed/", "fallback_url": "https://www.comic-con.org/cci/", "category_id": None, "kind_default": "convention", "description": "SDCC"},
    {"feed_url": "https://www.anime-expo.org/feed/", "fallback_url": "https://www.anime-expo.org/", "category_id": "anime_figures", "kind_default": "convention", "description": "Anime Expo"},
    {"feed_url": "https://www.gencon.com/feed/", "fallback_url": "https://www.gencon.com/", "category_id": "oop_board_games", "kind_default": "convention", "description": "Gen Con"},

    # ── StockX / Catawiki (try, may not have RSS) ────────────────────
    {"feed_url": "https://stockx.com/news/feed/", "fallback_url": "https://stockx.com/news", "category_id": "sneakers", "kind_default": "collection_drop", "description": "StockX news"},
    {"feed_url": "https://www.catawiki.com/en/stories/feed/", "fallback_url": "https://www.catawiki.com/en/stories", "category_id": None, "kind_default": "convention", "description": "Catawiki stories"},

    # ── LEGO (uses structured API, try RSS too) ──────────────────────
    {"feed_url": "https://www.lego.com/en-us/categories/new-sets-and-products/rss", "fallback_url": "https://www.lego.com/en-us/categories/new-sets-and-products", "category_id": "lego", "kind_default": "collection_drop", "description": "LEGO new sets"},

    # ── Watch events ─────────────────────────────────────────────────
    {"feed_url": "https://www.watchesandwonders.com/en/news/feed/", "fallback_url": "https://www.watchesandwonders.com/en/news/", "category_id": "watches", "kind_default": "convention", "description": "Watches & Wonders"},

    # ── Hot Toys ─────────────────────────────────────────────────────
    {"feed_url": "https://www.hottoyscollectibles.com/news/feed/", "fallback_url": "https://www.hottoyscollectibles.com/news", "category_id": "hot_toys", "kind_default": "release", "description": "Hot Toys news"},

    # ── Pokemon Center ───────────────────────────────────────────────
    {"feed_url": "https://www.pokemoncenter.com/blog/feed/", "fallback_url": "https://www.pokemoncenter.com/whats-new", "category_id": "pokemon", "kind_default": "collection_drop", "description": "Pokemon Center"},
]


# ---------------------------------------------------------------------------
# XML parsing helpers
# ---------------------------------------------------------------------------

# Common RSS/Atom namespaces
_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "media": "http://search.yahoo.com/mrss/",
}


def _parse_rss_date(date_str: str | None) -> datetime | None:
    """Parse various RSS/Atom date formats."""
    if not date_str:
        return None
    date_str = date_str.strip()

    # RFC 2822 (standard RSS)
    try:
        return parsedate_to_datetime(date_str)
    except (ValueError, TypeError):
        pass

    # ISO 8601 (Atom)
    for fmt in [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]:
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    return None


def _extract_image_from_xml(item: ET.Element) -> str | None:
    """Try to extract an image URL from RSS item."""
    # media:content or media:thumbnail
    for tag in ["media:content", "media:thumbnail"]:
        el = item.find(tag, _NS)
        if el is not None:
            url = el.get("url")
            if url:
                return url

    # enclosure with image type
    enc = item.find("enclosure")
    if enc is not None and "image" in (enc.get("type", "")):
        return enc.get("url")

    # Look in description/content for img tags
    desc = item.findtext("description") or item.findtext("content:encoded", namespaces=_NS) or ""
    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
    if img_match:
        return img_match.group(1)

    return None


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    return re.sub(r'<[^>]+>', '', text).strip()


def _parse_feed_xml(
    xml_text: str,
    target: dict[str, Any],
    since: datetime,
) -> list[ScrapedEvent]:
    """Parse RSS or Atom XML into ScrapedEvent list."""
    events: list[ScrapedEvent] = []
    seen_titles: set[str] = set()

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return events

    category_id = target["category_id"]
    kind_default = target["kind_default"]

    # Detect feed type: RSS 2.0 or Atom
    items: list[ET.Element] = []

    if root.tag == "rss" or root.find("channel") is not None:
        # RSS 2.0
        channel = root.find("channel")
        if channel is not None:
            items = channel.findall("item")
    elif root.tag.endswith("feed") or root.find("{http://www.w3.org/2005/Atom}entry") is not None:
        # Atom
        items = root.findall("{http://www.w3.org/2005/Atom}entry")
    else:
        # Try generic item/entry
        items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")

    for item in items[:20]:  # Max 20 events per feed
        # Extract title
        title_el = item.find("title") or item.find("{http://www.w3.org/2005/Atom}title")
        title = (title_el.text or "").strip() if title_el is not None else ""
        if not title or len(title) < 5:
            continue

        # Dedup
        title_norm = title.lower()[:60]
        if title_norm in seen_titles:
            continue
        seen_titles.add(title_norm)

        # Extract date
        pub_date = (
            item.findtext("pubDate")
            or item.findtext("{http://purl.org/dc/elements/1.1/}date")
            or item.findtext("{http://www.w3.org/2005/Atom}published")
            or item.findtext("{http://www.w3.org/2005/Atom}updated")
        )
        event_date = _parse_rss_date(pub_date)
        if event_date and event_date < since:
            continue

        # Extract link
        link_el = item.find("link") or item.find("{http://www.w3.org/2005/Atom}link")
        if link_el is not None:
            source_url = link_el.get("href") or link_el.text or ""
        else:
            source_url = ""
        source_url = source_url.strip()

        # Extract description
        desc = (
            item.findtext("description")
            or item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded")
            or item.findtext("{http://www.w3.org/2005/Atom}summary")
            or item.findtext("{http://www.w3.org/2005/Atom}content")
            or ""
        )
        desc_clean = _strip_html(desc)[:500]

        # Extract image
        image_url = _extract_image_from_xml(item)

        # Classify event kind from content
        combined_text = f"{title} {desc_clean}"
        kind = _classify_event_kind(combined_text) or kind_default

        # Auto-detect category from content if not specified
        resolved_category = category_id
        if not resolved_category:
            resolved_category = _category_from_content(combined_text)

        date_str = event_date.strftime("%Y-%m-%d") if event_date else None

        events.append(ScrapedEvent(
            title=title[:200],
            kind=kind,
            category_id=resolved_category,
            date=date_str,
            time=None,
            end_date=None,
            location=None,
            online_url=source_url or None,
            description=desc_clean or None,
            source_url=source_url or target.get("fallback_url", ""),
            image_url=image_url,
        ))

    return events


# ---------------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------------

async def _fetch_feed(
    client: httpx.AsyncClient,
    target: dict[str, Any],
    since: datetime,
) -> list[ScrapedEvent]:
    """Fetch and parse a single RSS feed. Returns empty list on failure."""
    feed_url = target["feed_url"]
    try:
        resp = await client.get(
            feed_url,
            headers={
                "User-Agent": "CollectAI/1.0 (RSS reader; collectai.app)",
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
            },
            follow_redirects=True,
        )

        if resp.status_code != 200:
            logger.debug("Feed %s returned %d", feed_url[:60], resp.status_code)
            return []

        content_type = resp.headers.get("content-type", "")
        if "xml" not in content_type and "rss" not in content_type and "atom" not in content_type:
            # Might be HTML (no RSS feed available)
            if "<html" in resp.text[:500].lower():
                logger.debug("Feed %s returned HTML, skipping", feed_url[:60])
                return []

        events = _parse_feed_xml(resp.text, target, since)
        if events:
            logger.info("RSS %s: %d events", target["description"][:40], len(events))
        return events

    except Exception as e:
        logger.debug("Feed %s failed: %s", feed_url[:60], e)
        return []


async def run_rss_scraper(
    since_days: int = 30,
    dry_run: bool = False,
) -> list[ScrapedEvent]:
    """
    Scrape all RSS feed targets and upsert events to DB.

    Returns list of all scraped events.
    """
    since = datetime.now(timezone.utc) - timedelta(days=since_days)
    all_events: list[ScrapedEvent] = []
    feeds_with_events = 0
    feeds_failed = 0

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Process feeds concurrently (max 5 at a time)
        semaphore = asyncio.Semaphore(5)

        async def fetch_with_semaphore(target: dict[str, Any]) -> list[ScrapedEvent]:
            async with semaphore:
                return await _fetch_feed(client, target, since)

        tasks = [fetch_with_semaphore(t) for t in RSS_FEED_TARGETS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for target, result in zip(RSS_FEED_TARGETS, results):
            if isinstance(result, Exception):
                feeds_failed += 1
                continue
            if result:
                all_events.extend(result)
                feeds_with_events += 1

    logger.info(
        "RSS scraper: %d events from %d/%d feeds (%d failed/empty)",
        len(all_events), feeds_with_events, len(RSS_FEED_TARGETS), feeds_failed,
    )

    # Upsert to DB
    if all_events and not dry_run:
        upserter = EventUpserter()
        try:
            await upserter.upsert_events(all_events, source="rss")
        except Exception as e:
            logger.warning("RSS upsert failed: %s", e)
        finally:
            await upserter.close()

    return all_events


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="RSS feed event scraper")
    parser.add_argument("--dry-run", action="store_true", help="Parse without DB writes")
    parser.add_argument("--since", type=int, default=30, help="Days to look back (default: 30)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("Starting RSS event scraper (since=%d days)", args.since)
    events = asyncio.run(run_rss_scraper(since_days=args.since, dry_run=args.dry_run))
    logger.info("Done. %d events from RSS feeds.", len(events))


if __name__ == "__main__":
    main()
