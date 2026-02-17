"""
Tests for pipelines/crawl4ai_enrich.py — Crawl4AI catalog enrichment pipeline.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ["CRAWL4AI_ENABLED"] = "false"


# ---------------------------------------------------------------------------
# Price extraction unit tests
# ---------------------------------------------------------------------------

class TestExtractPriceFromText:
    """Tests for _extract_price_from_text()."""

    def test_usd_price(self):
        from pipelines.crawl4ai_enrich import _extract_price_from_text

        price, currency = _extract_price_from_text("Item $29.99 shipped")
        assert price == pytest.approx(29.99, abs=0.01)
        assert currency == "USD"

    def test_eur_price(self):
        from pipelines.crawl4ai_enrich import _extract_price_from_text

        price, currency = _extract_price_from_text("€45.00 total")
        assert price == pytest.approx(45.0)
        assert currency == "EUR"

    def test_gbp_price(self):
        from pipelines.crawl4ai_enrich import _extract_price_from_text

        price, currency = _extract_price_from_text("£19.50 only")
        assert price == pytest.approx(19.5)
        assert currency == "GBP"

    def test_jpy_price(self):
        from pipelines.crawl4ai_enrich import _extract_price_from_text

        price, currency = _extract_price_from_text("¥3500 tax included")
        assert price == pytest.approx(3500.0)
        assert currency == "JPY"

    def test_no_price(self):
        from pipelines.crawl4ai_enrich import _extract_price_from_text

        price, currency = _extract_price_from_text("No price here")
        assert price is None

    def test_empty_string(self):
        from pipelines.crawl4ai_enrich import _extract_price_from_text

        price, currency = _extract_price_from_text("")
        assert price is None

    def test_comma_separated_price(self):
        from pipelines.crawl4ai_enrich import _extract_price_from_text

        price, currency = _extract_price_from_text("$1,299.99")
        assert price == pytest.approx(1299.99, abs=0.01)


# ---------------------------------------------------------------------------
# Search URL construction
# ---------------------------------------------------------------------------

class TestBuildSearchUrl:
    """Tests for _build_search_url()."""

    def test_known_site(self):
        from pipelines.crawl4ai_enrich import _build_search_url

        url = _build_search_url("scalemates.com", "Tamiya 1/48")
        assert "scalemates.com" in url
        assert "Tamiya" in url

    def test_unknown_site_falls_back_to_google(self):
        from pipelines.crawl4ai_enrich import _build_search_url

        url = _build_search_url("unknown-shop.com", "rare item")
        assert "google.com/search" in url
        assert "unknown-shop.com" in url


# ---------------------------------------------------------------------------
# Enrichment targets validation
# ---------------------------------------------------------------------------

class TestEnrichmentTargets:
    """Validate enrichment target configuration."""

    def test_all_targets_have_required_fields(self):
        from pipelines.crawl4ai_enrich import ENRICHMENT_TARGETS

        for cat, config in ENRICHMENT_TARGETS.items():
            assert "site" in config, f"Missing 'site' for {cat}"
            assert "search_queries" in config, f"Missing 'search_queries' for {cat}"
            assert len(config["search_queries"]) >= 1, f"No queries for {cat}"

    def test_kpop_merch_target(self):
        from pipelines.crawl4ai_enrich import ENRICHMENT_TARGETS

        assert "kpop_merch" in ENRICHMENT_TARGETS
        config = ENRICHMENT_TARGETS["kpop_merch"]
        assert "ktown4u.com" in config["site"]
        queries = " ".join(config["search_queries"]).lower()
        assert "bts" in queries

    def test_taylor_swift_target(self):
        from pipelines.crawl4ai_enrich import ENRICHMENT_TARGETS

        assert "taylor_swift" in ENRICHMENT_TARGETS
        config = ENRICHMENT_TARGETS["taylor_swift"]
        queries = " ".join(config["search_queries"]).lower()
        assert "taylor swift" in queries or "eras tour" in queries


# ---------------------------------------------------------------------------
# Enrichment logic tests
# ---------------------------------------------------------------------------

class TestEnrichCategory:
    """Tests for _enrich_category()."""

    @pytest.mark.asyncio
    async def test_skips_when_not_configured(self):
        from pipelines.crawl4ai_enrich import _enrich_category, ENRICHMENT_TARGETS
        from pipelines.import_common import IngestStats

        stats = IngestStats()
        with patch("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", False):
            items = await _enrich_category(
                "anime_figures",
                ENRICHMENT_TARGETS["anime_figures"],
                limit=10,
                stats=stats,
            )
        assert items == []

    @pytest.mark.asyncio
    async def test_enriches_from_crawl_results(self):
        from pipelines.crawl4ai_enrich import _enrich_category, ENRICHMENT_TARGETS
        from pipelines.import_common import IngestStats

        stats = IngestStats()
        mock_scrape = AsyncMock(return_value={
            "markdown": (
                "## Nendoroid Hatsune Miku\n"
                "Price: $39.99 shipped\n"
                "![img](https://img.example.com/miku.jpg)\n\n\n"
                "## Scale Figure Rem 1/7\n"
                "USD 120.00 in box\n"
            ),
            "metadata": {"title": "Search Results"},
            "url": "https://myfigurecollection.net/browse",
        })

        with patch("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", True):
            with patch("app.lib.crawl4ai_client.scrape_url", mock_scrape):
                items = await _enrich_category(
                    "anime_figures",
                    ENRICHMENT_TARGETS["anime_figures"],
                    limit=10,
                    stats=stats,
                )

        assert len(items) >= 1
        assert items[0].category == "anime_figures"
        assert "crawl4ai" in items[0].attributes_json.get("source", "")

    @pytest.mark.asyncio
    async def test_respects_limit(self):
        from pipelines.crawl4ai_enrich import _enrich_category, ENRICHMENT_TARGETS
        from pipelines.import_common import IngestStats

        stats = IngestStats()

        # Return many results via rich markdown
        listings = "\n\n\n".join([
            f"## Item Number {i}\nPrice: ${i * 10}.00"
            for i in range(20)
        ])
        mock_scrape = AsyncMock(return_value={
            "markdown": listings,
            "metadata": {"title": "Results"},
            "url": "https://example.com/search",
        })

        with patch("app.lib.crawl4ai_client.CRAWL4AI_ENABLED", True):
            with patch("app.lib.crawl4ai_client.scrape_url", mock_scrape):
                items = await _enrich_category(
                    "scale_models",
                    ENRICHMENT_TARGETS["scale_models"],
                    limit=3,
                    stats=stats,
                )

        assert len(items) <= 3


# ---------------------------------------------------------------------------
# CLI parser tests
# ---------------------------------------------------------------------------

class TestBuildParser:
    """Tests for CLI argument parsing."""

    def test_default_args(self):
        from pipelines.crawl4ai_enrich import _build_parser

        parser = _build_parser()
        args = parser.parse_args([])
        assert args.dry_run is False
        assert args.category is None
        assert args.limit == 50
        assert args.verbose is False
        assert args.output is None

    def test_dry_run_flag(self):
        from pipelines.crawl4ai_enrich import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_category_filter(self):
        from pipelines.crawl4ai_enrich import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["--category", "kpop_merch"])
        assert args.category == "kpop_merch"

    def test_limit_override(self):
        from pipelines.crawl4ai_enrich import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["--limit", "10"])
        assert args.limit == 10
