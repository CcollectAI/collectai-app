"""
Tests for pipelines/crawl4ai_events.py — Crawl4AI event page crawler.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ["CRAWL4AI_ENABLED"] = "false"


# ---------------------------------------------------------------------------
# Event extraction unit tests
# ---------------------------------------------------------------------------

class TestExtractEventsFromMarkdown:
    """Tests for _extract_events_from_markdown()."""

    def test_extracts_events_from_headers(self):
        from pipelines.crawl4ai_events import _extract_events_from_markdown

        markdown = """
## Pokemon Regional Championship 2026
January 15, 2026

## Pokemon League Challenge
February 20, 2026

Some description text.
"""
        events = _extract_events_from_markdown(
            markdown, "https://pokemon.com/events", "pokemon", "release",
        )
        assert len(events) >= 1
        assert events[0].category_id == "pokemon"

    def test_no_events_without_dates(self):
        from pipelines.crawl4ai_events import _extract_events_from_markdown

        markdown = """
## Some Title
Just text with no dates at all.
"""
        events = _extract_events_from_markdown(
            markdown, "https://example.com", None, "release",
        )
        assert events == []

    def test_limits_to_20_events(self):
        from pipelines.crawl4ai_events import _extract_events_from_markdown

        lines = []
        for i in range(30):
            lines.append(f"## Event Number {i}")
            lines.append(f"January {(i % 28) + 1}, 2026")
            lines.append("")

        markdown = "\n".join(lines)
        events = _extract_events_from_markdown(
            markdown, "https://example.com", "funko", "collection_drop",
        )
        assert len(events) <= 20

    def test_deduplicates_titles(self):
        from pipelines.crawl4ai_events import _extract_events_from_markdown

        markdown = """
## Same Event Title Here
January 15, 2026

## Same Event Title Here
February 20, 2026
"""
        events = _extract_events_from_markdown(
            markdown, "https://example.com", "mtg", "release",
        )
        titles = [e.title for e in events]
        assert len(set(t.lower()[:60] for t in titles)) == len(titles)


# ---------------------------------------------------------------------------
# Event page targets validation
# ---------------------------------------------------------------------------

class TestEventPageTargets:
    """Validate event page target configuration."""

    def test_has_pokemon_target(self):
        from pipelines.crawl4ai_events import EVENT_PAGE_TARGETS

        urls = [t["url"] for t in EVENT_PAGE_TARGETS]
        assert any("pokemon" in u for u in urls)

    def test_has_bts_weverse_target(self):
        from pipelines.crawl4ai_events import EVENT_PAGE_TARGETS

        urls = [t["url"] for t in EVENT_PAGE_TARGETS]
        assert any("weverse" in u and "bts" in u for u in urls)

    def test_has_taylor_swift_target(self):
        from pipelines.crawl4ai_events import EVENT_PAGE_TARGETS

        urls = [t["url"] for t in EVENT_PAGE_TARGETS]
        assert any("taylorswift" in u for u in urls)

    def test_has_eventbrite_targets(self):
        from pipelines.crawl4ai_events import EVENT_PAGE_TARGETS

        urls = [t["url"] for t in EVENT_PAGE_TARGETS]
        eventbrite_count = sum(1 for u in urls if "eventbrite" in u)
        assert eventbrite_count >= 3

    def test_all_targets_have_required_fields(self):
        from pipelines.crawl4ai_events import EVENT_PAGE_TARGETS

        for target in EVENT_PAGE_TARGETS:
            assert "url" in target
            assert "kind_default" in target
            assert target["url"].startswith("http")

    def test_js_heavy_targets_have_wait_for(self):
        from pipelines.crawl4ai_events import EVENT_PAGE_TARGETS

        weverse_targets = [t for t in EVENT_PAGE_TARGETS if "weverse" in t["url"]]
        assert len(weverse_targets) >= 1
        assert weverse_targets[0].get("wait_for") is not None


# ---------------------------------------------------------------------------
# Crawler tests
# ---------------------------------------------------------------------------

class TestCrawlEventPages:
    """Tests for _crawl_event_pages()."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_not_configured(self):
        from pipelines.crawl4ai_events import _crawl_event_pages

        with patch("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", False):
            events = await _crawl_event_pages([], 30)
        assert events == []

    @pytest.mark.asyncio
    async def test_crawls_and_extracts(self):
        from pipelines.crawl4ai_events import _crawl_event_pages

        targets = [
            {
                "url": "https://pokemon.com/events",
                "category_id": "pokemon",
                "kind_default": "release",
                "description": "Pokemon events",
            },
        ]

        mock_scrape = AsyncMock(return_value={
            "markdown": """
## Pokemon World Championships 2026
August 15, 2026

The biggest Pokemon event of the year!
Location: Anaheim Convention Center
""",
            "metadata": {"title": "Pokemon Events"},
            "url": "https://pokemon.com/events",
        })

        with patch("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", True):
            with patch("app.lib.crawl4ai_client.scrape_url", mock_scrape):
                events = await _crawl_event_pages(targets, since_days=365)

        assert len(events) >= 1
        assert events[0].category_id == "pokemon"

    @pytest.mark.asyncio
    async def test_passes_wait_for_to_scraper(self):
        from pipelines.crawl4ai_events import _crawl_event_pages

        targets = [
            {
                "url": "https://weverse.io/bts/feed",
                "category_id": "kpop_merch",
                "kind_default": "collection_drop",
                "description": "BTS Weverse",
                "wait_for": "[class*='feed']",
            },
        ]

        mock_scrape = AsyncMock(return_value={
            "markdown": "## BTS Concert Announcement\nMarch 10, 2026",
            "metadata": {"title": "BTS Feed"},
            "url": "https://weverse.io/bts/feed",
        })

        with patch("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", True):
            with patch("app.lib.crawl4ai_client.scrape_url", mock_scrape):
                await _crawl_event_pages(targets, since_days=365)

        # Verify wait_for was passed
        call_kwargs = mock_scrape.call_args
        assert call_kwargs.kwargs.get("wait_for") == "[class*='feed']"

    @pytest.mark.asyncio
    async def test_handles_scrape_failure(self):
        from pipelines.crawl4ai_events import _crawl_event_pages

        targets = [
            {
                "url": "https://example.com",
                "category_id": "funko",
                "kind_default": "release",
                "description": "Test",
            },
        ]

        mock_scrape = AsyncMock(side_effect=RuntimeError("Connection failed"))

        with patch("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", True):
            with patch("app.lib.crawl4ai_client.scrape_url", mock_scrape):
                events = await _crawl_event_pages(targets, since_days=30)

        assert events == []


# ---------------------------------------------------------------------------
# CLI parser tests
# ---------------------------------------------------------------------------

class TestBuildParser:
    """Tests for CLI argument parsing."""

    def test_default_args(self):
        from pipelines.crawl4ai_events import _build_parser

        parser = _build_parser()
        args = parser.parse_args([])
        assert args.dry_run is False
        assert args.since == 30
        assert args.verbose is False
        assert args.output is None

    def test_dry_run_flag(self):
        from pipelines.crawl4ai_events import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_since_override(self):
        from pipelines.crawl4ai_events import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["--since", "7"])
        assert args.since == 7
