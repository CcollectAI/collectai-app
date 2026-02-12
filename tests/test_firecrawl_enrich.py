"""
Tests for pipelines/firecrawl_enrich.py — catalog enrichment pipeline.
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


# ---------------------------------------------------------------------------
# Price extraction unit tests
# ---------------------------------------------------------------------------

class TestExtractPriceFromText:
    """Tests for _extract_price_from_text()."""

    def test_usd_price(self):
        from pipelines.firecrawl_enrich import _extract_price_from_text

        price, currency = _extract_price_from_text("Item $29.99 shipped")
        assert price == pytest.approx(29.99, abs=0.01)
        assert currency == "USD"

    def test_eur_price(self):
        from pipelines.firecrawl_enrich import _extract_price_from_text

        price, currency = _extract_price_from_text("€45.00 total")
        assert price == pytest.approx(45.0)
        assert currency == "EUR"

    def test_gbp_price(self):
        from pipelines.firecrawl_enrich import _extract_price_from_text

        price, currency = _extract_price_from_text("£19.50 only")
        assert price == pytest.approx(19.5)
        assert currency == "GBP"

    def test_jpy_price(self):
        from pipelines.firecrawl_enrich import _extract_price_from_text

        price, currency = _extract_price_from_text("¥3500 tax included")
        assert price == pytest.approx(3500.0)
        assert currency == "JPY"

    def test_no_price(self):
        from pipelines.firecrawl_enrich import _extract_price_from_text

        price, currency = _extract_price_from_text("No price here")
        assert price is None

    def test_empty_string(self):
        from pipelines.firecrawl_enrich import _extract_price_from_text

        price, currency = _extract_price_from_text("")
        assert price is None

    def test_comma_separated_price(self):
        from pipelines.firecrawl_enrich import _extract_price_from_text

        price, currency = _extract_price_from_text("$1,299.99")
        assert price == pytest.approx(1299.99, abs=0.01)


# ---------------------------------------------------------------------------
# Enrichment targets validation
# ---------------------------------------------------------------------------

class TestEnrichmentTargets:
    """Validate enrichment target configuration."""

    def test_all_targets_have_required_fields(self):
        from pipelines.firecrawl_enrich import ENRICHMENT_TARGETS

        for cat, config in ENRICHMENT_TARGETS.items():
            assert "site" in config, f"Missing 'site' for {cat}"
            assert "search_queries" in config, f"Missing 'search_queries' for {cat}"
            assert len(config["search_queries"]) >= 1, f"No queries for {cat}"

    def test_kpop_merch_target(self):
        from pipelines.firecrawl_enrich import ENRICHMENT_TARGETS

        assert "kpop_merch" in ENRICHMENT_TARGETS
        config = ENRICHMENT_TARGETS["kpop_merch"]
        assert "ktown4u.com" in config["site"]
        # BTS queries should be present
        queries = " ".join(config["search_queries"]).lower()
        assert "bts" in queries

    def test_taylor_swift_target(self):
        from pipelines.firecrawl_enrich import ENRICHMENT_TARGETS

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
        from pipelines.firecrawl_enrich import _enrich_category, ENRICHMENT_TARGETS
        from pipelines.import_common import IngestStats

        stats = IngestStats()
        with patch("app.lib.firecrawl_client.FIRECRAWL_API_KEY", ""):
            items = await _enrich_category(
                "anime_figures",
                ENRICHMENT_TARGETS["anime_figures"],
                limit=10,
                stats=stats,
            )
        assert items == []

    @pytest.mark.asyncio
    async def test_enriches_from_search_results(self):
        from pipelines.firecrawl_enrich import _enrich_category, ENRICHMENT_TARGETS
        from pipelines.import_common import IngestStats

        stats = IngestStats()
        mock_search = AsyncMock(return_value=[
            {
                "url": "https://myfigurecollection.net/item/12345",
                "title": "Nendoroid Hatsune Miku",
                "markdown": "Price: $39.99 shipped",
                "description": "Nendoroid figure",
                "metadata": {"og:image": "https://img.example.com/miku.jpg"},
            },
            {
                "url": "https://myfigurecollection.net/item/67890",
                "title": "Scale Figure Rem 1/7",
                "markdown": "USD 120.00 in box",
                "description": "Scale figure",
                "metadata": {},
            },
        ])

        with patch("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "fc-test"):
            with patch("app.lib.firecrawl_client.search_web", mock_search):
                items = await _enrich_category(
                    "anime_figures",
                    ENRICHMENT_TARGETS["anime_figures"],
                    limit=10,
                    stats=stats,
                )

        assert len(items) >= 1
        assert items[0].category == "anime_figures"
        assert items[0].title == "Nendoroid Hatsune Miku"
        assert "firecrawl" in items[0].attributes_json.get("source", "")

    @pytest.mark.asyncio
    async def test_respects_limit(self):
        from pipelines.firecrawl_enrich import _enrich_category, ENRICHMENT_TARGETS
        from pipelines.import_common import IngestStats

        stats = IngestStats()

        # Return many results
        results = [
            {"url": f"https://example.com/{i}", "title": f"Item {i}", "markdown": f"${i * 10}.00", "description": "", "metadata": {}}
            for i in range(20)
        ]
        mock_search = AsyncMock(return_value=results)

        with patch("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "fc-test"):
            with patch("app.lib.firecrawl_client.search_web", mock_search):
                items = await _enrich_category(
                    "scale_models",
                    ENRICHMENT_TARGETS["scale_models"],
                    limit=3,
                    stats=stats,
                )

        assert len(items) <= 3

    @pytest.mark.asyncio
    async def test_deduplicates_by_key(self):
        from pipelines.firecrawl_enrich import _enrich_category, ENRICHMENT_TARGETS
        from pipelines.import_common import IngestStats

        stats = IngestStats()

        # Two results with the same title (same slug)
        results = [
            {"url": "https://example.com/1", "title": "Duplicate Title", "markdown": "$10.00", "description": "", "metadata": {}},
            {"url": "https://example.com/2", "title": "Duplicate Title", "markdown": "$15.00", "description": "", "metadata": {}},
        ]
        mock_search = AsyncMock(return_value=results)

        with patch("app.lib.firecrawl_client.FIRECRAWL_API_KEY", "fc-test"):
            with patch("app.lib.firecrawl_client.search_web", mock_search):
                items = await _enrich_category(
                    "scale_models",
                    ENRICHMENT_TARGETS["scale_models"],
                    limit=50,
                    stats=stats,
                )

        # Should only have 1 unique item
        keys = [it.item_key for it in items]
        assert len(keys) == len(set(keys))


# ---------------------------------------------------------------------------
# CLI parser tests
# ---------------------------------------------------------------------------

class TestBuildParser:
    """Tests for CLI argument parsing."""

    def test_default_args(self):
        from pipelines.firecrawl_enrich import _build_parser

        parser = _build_parser()
        args = parser.parse_args([])
        assert args.dry_run is False
        assert args.category is None
        assert args.limit == 50
        assert args.verbose is False
        assert args.output is None

    def test_dry_run_flag(self):
        from pipelines.firecrawl_enrich import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_category_filter(self):
        from pipelines.firecrawl_enrich import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["--category", "kpop_merch"])
        assert args.category == "kpop_merch"

    def test_limit_override(self):
        from pipelines.firecrawl_enrich import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["--limit", "10"])
        assert args.limit == 10
