"""Tests for marketplace adapter routing configuration.

Verifies:
- SOURCE_RELIABILITY has entries for all 37+ adapters
- ADAPTER_CATEGORY_ROUTING has entries for all expected adapters
- adapter_serves_category returns True for known adapter-category pairs
- adapter_serves_category returns False for mismatched pairs
- Unrestricted adapters serve any category
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from app.agents.marketplace_routing import (
    SOURCE_RELIABILITY,
    ADAPTER_CATEGORY_ROUTING,
    DISABLED_ADAPTERS,
    adapter_serves_category,
)


# ---------------------------------------------------------------------------
# SOURCE_RELIABILITY
# ---------------------------------------------------------------------------

class TestSourceReliability:
    def test_has_at_least_37_entries(self):
        # 37 adapters, many have _sold variants too
        assert len(SOURCE_RELIABILITY) >= 37

    def test_all_values_between_0_and_1(self):
        for key, val in SOURCE_RELIABILITY.items():
            assert 0.0 < val <= 1.0, f"{key} has invalid reliability: {val}"

    def test_known_adapters_present(self):
        expected_keys = [
            "ebay_sold", "tcgplayer", "mavin", "mercari_us", "whatnot",
            "bezel", "chrono24", "keh", "mpb", "drop", "gouletpens",
            "brickeconomy", "popmart", "booth", "scalemates", "ktown4u",
            "comicbookrealm", "masterofmalt", "pricecharting",
            "yahoo_auctions", "stockx", "discogs", "cardmarket",
            "bricklink", "scrapedo", "grailed", "google_shopping",
            "etsy", "comc", "reverb", "abebooks",
        ]
        for key in expected_keys:
            assert key in SOURCE_RELIABILITY, f"Missing key: {key}"

    def test_sold_variants_higher_than_listed(self):
        """Sold data is generally more reliable than listed data."""
        pairs = [
            ("ebay_listed", "ebay_sold"),
            ("firecrawl", "firecrawl_sold"),
            ("crawl4ai", "crawl4ai_sold"),
            ("whatnot", "whatnot_sold"),
        ]
        for listed, sold in pairs:
            if listed in SOURCE_RELIABILITY and sold in SOURCE_RELIABILITY:
                assert SOURCE_RELIABILITY[sold] >= SOURCE_RELIABILITY[listed], (
                    f"{sold} ({SOURCE_RELIABILITY[sold]}) should be >= "
                    f"{listed} ({SOURCE_RELIABILITY[listed]})"
                )


# ---------------------------------------------------------------------------
# ADAPTER_CATEGORY_ROUTING
# ---------------------------------------------------------------------------

class TestAdapterCategoryRouting:
    EXPECTED_UNRESTRICTED = {
        "ebay", "firecrawl", "crawl4ai",
        "google_shopping", "mercari_us", "vinted", "mavin",
    }

    EXPECTED_ROUTED = {
        "tcgplayer", "whatnot", "catawiki", "whisky_auctioneer",
        "gouletpens", "brickeconomy", "popmart", "booth",
        "scalemates", "ktown4u", "comicbookrealm", "masterofmalt",
        "pricecharting", "yahoo_auctions", "stockx", "discogs",
        "cardmarket", "bricklink", "etsy", "comc", "reverb",
        "abebooks", "grailed",
        # MOVED from UNRESTRICTED on 2026-08-31. `None` means every category,
        # which was right while scrapedo was an unmetered generic fetcher and is
        # wrong now that it runs on a 1,000-request monthly free tier: pointed at
        # everything, the budget goes to pokemon (831,303 comps) and mtg (1.6M)
        # instead of the categories with no sold comps at all. Narrowed to 11 of
        # those. See docs/SCRAPEDO_PLAN.md.
        "scrapedo",
    }

    def test_has_all_expected_adapters(self):
        # Some adapters were de-registered 2026-04-25 (DISABLED_ADAPTERS)
        # and removed from ADAPTER_CATEGORY_ROUTING. Only check live ones.
        all_expected = (self.EXPECTED_UNRESTRICTED | self.EXPECTED_ROUTED) - DISABLED_ADAPTERS
        for adapter in all_expected:
            assert adapter in ADAPTER_CATEGORY_ROUTING, f"Missing adapter: {adapter}"

    def test_unrestricted_adapters_have_none_categories(self):
        for adapter in self.EXPECTED_UNRESTRICTED:
            assert ADAPTER_CATEGORY_ROUTING[adapter] is None, (
                f"{adapter} should be unrestricted (None)"
            )

    def test_routed_adapters_have_set_categories(self):
        for adapter in self.EXPECTED_ROUTED - DISABLED_ADAPTERS:
            cats = ADAPTER_CATEGORY_ROUTING[adapter]
            assert isinstance(cats, set), f"{adapter} should have a set of categories"
            assert len(cats) > 0, f"{adapter} has empty category set"

    def test_total_adapter_count(self):
        assert len(ADAPTER_CATEGORY_ROUTING) >= 37


# ---------------------------------------------------------------------------
# adapter_serves_category
# ---------------------------------------------------------------------------

class TestAdapterServesCategory:
    """Test the routing lookup function."""

    # --- Unrestricted adapters serve any category ---

    @pytest.mark.parametrize("adapter", [
        "ebay", "firecrawl", "crawl4ai", "vinted",
        # scrapedo, mercari_us, mavin, google_shopping disabled per
        # DISABLED_ADAPTERS (2026-04-25 audit — zero hits in 7d).
    ])
    def test_unrestricted_serves_any_category(self, adapter):
        assert adapter_serves_category(adapter, "pokemon") is True
        assert adapter_serves_category(adapter, "watches") is True
        assert adapter_serves_category(adapter, "nonexistent_category") is True

    # --- Known true pairs ---

    # Only live adapters here — disabled ones tested separately in
    # test_disabled_adapters_return_false below.
    @pytest.mark.parametrize("adapter,category", [
        ("tcgplayer", "pokemon"),
        ("tcgplayer", "mtg"),
        ("tcgplayer", "yugioh"),
        ("gouletpens", "pens"),
        ("comicbookrealm", "comic_books"),
        ("discogs", "vinyl_records"),
        ("cardmarket", "pokemon"),
        ("reverb", "vinyl_records"),
        ("grailed", "sneakers"),
        # RE-ENABLED 2026-07-22: the caller scrapes the free public website
        # (loose/CIB/new/graded) when there is no API key, which landed sold
        # comps for retro_games / retro_handhelds / etc. — categories that had
        # ZERO price_predictions before it. It sat in the disabled list below
        # for a month after that, so the suite asserted the opposite of the
        # routing table it was testing.
        ("pricecharting", "retro_games"),
        ("pricecharting", "retro_handhelds"),
    ])
    def test_known_true_pairs(self, adapter, category):
        assert adapter_serves_category(adapter, category) is True

    # 2026-04-25 + 2026-05-10: adapters de-registered after live probes.
    # adapter_serves_category returns False even for their declared cats.
    @pytest.mark.parametrize("adapter,category", [
        ("bezel", "watches"),
        ("chrono24", "watches"),
        ("bricklink", "lego"),
        ("brickeconomy", "lego"),
        ("keh", "vintage_cameras"),
        ("whisky_auctioneer", "whiskey"),
        ("masterofmalt", "whiskey"),
        ("stockx", "sneakers"),
        ("comc", "sportscards"),
        # 2026-05-10: catawiki Akamai WAF (HTTP 403),
        # abebooks JS-rendered prices (0 price tokens in HTML).
        ("catawiki", "whiskey"),
        ("catawiki", "diecast"),
        ("abebooks", "comic_books"),
    ])
    def test_disabled_adapters_return_false(self, adapter, category):
        assert adapter in DISABLED_ADAPTERS
        assert adapter_serves_category(adapter, category) is False

    # --- Known false pairs ---

    @pytest.mark.parametrize("adapter,category", [
        ("tcgplayer", "watches"),
        ("bezel", "pokemon"),
        ("bricklink", "watches"),
        ("gouletpens", "sneakers"),
        ("keh", "pokemon"),
        ("whisky_auctioneer", "lego"),
        ("comicbookrealm", "watches"),
        ("drop", "pokemon"),
        ("masterofmalt", "sneakers"),
    ])
    def test_known_false_pairs(self, adapter, category):
        assert adapter_serves_category(adapter, category) is False

    # --- None category means everything matches ---

    def test_none_category_returns_true_for_routed(self):
        assert adapter_serves_category("tcgplayer", None) is True
        assert adapter_serves_category("cardmarket", None) is True
        assert adapter_serves_category("discogs", None) is True
        # bezel/bricklink now in DISABLED_ADAPTERS — return False even for
        # category=None per the post-2026-04-25 audit.

    def test_none_category_returns_true_for_unrestricted(self):
        assert adapter_serves_category("ebay", None) is True

    # --- Unknown adapter defaults to True (not in routing dict) ---

    def test_unknown_adapter_returns_true(self):
        # adapter_serves_category does .get() which returns None for unknown
        # None means unrestricted
        assert adapter_serves_category("totally_fake_adapter", "pokemon") is True
