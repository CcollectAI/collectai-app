"""Tests for app.lib.region_marketplace_config — region-aware routing."""

import os

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("DATABASE_URL", "mock://localhost")

from app.lib.region_marketplace_config import (
    get_ebay_marketplace_id,
    should_use_adapter,
    get_firecrawl_sites,
    get_crawl4ai_sites,
)


# ---------------------------------------------------------------------------
# get_ebay_marketplace_id
# ---------------------------------------------------------------------------

def test_ebay_marketplace_americas():
    assert get_ebay_marketplace_id("americas") == "EBAY_US"


def test_ebay_marketplace_europe():
    assert get_ebay_marketplace_id("europe") == "EBAY_DE"


def test_ebay_marketplace_japan():
    assert get_ebay_marketplace_id("japan") == "EBAY_JP"


def test_ebay_marketplace_other():
    assert get_ebay_marketplace_id("other") == "EBAY_US"


def test_ebay_marketplace_none():
    assert get_ebay_marketplace_id(None) == "EBAY_US"


def test_ebay_marketplace_unknown():
    assert get_ebay_marketplace_id("mars") == "EBAY_US"


# ---------------------------------------------------------------------------
# should_use_adapter
# ---------------------------------------------------------------------------

def test_americas_uses_all_adapters():
    assert should_use_adapter("americas", "ebay") is True
    assert should_use_adapter("americas", "tcgplayer") is True
    assert should_use_adapter("americas", "firecrawl") is True


def test_europe_skips_tcgplayer():
    assert should_use_adapter("europe", "ebay") is True
    assert should_use_adapter("europe", "tcgplayer") is False
    assert should_use_adapter("europe", "firecrawl") is True


def test_japan_skips_tcgplayer():
    assert should_use_adapter("japan", "ebay") is True
    assert should_use_adapter("japan", "tcgplayer") is False
    assert should_use_adapter("japan", "firecrawl") is True


def test_other_uses_all_adapters():
    assert should_use_adapter("other", "ebay") is True
    assert should_use_adapter("other", "tcgplayer") is True
    assert should_use_adapter("other", "firecrawl") is True


def test_none_region_defaults_to_other():
    assert should_use_adapter(None, "ebay") is True
    assert should_use_adapter(None, "tcgplayer") is True


def test_unknown_adapter_defaults_to_true():
    assert should_use_adapter("americas", "newadapter") is True


# ---------------------------------------------------------------------------
# get_firecrawl_sites
# ---------------------------------------------------------------------------

def test_europe_pokemon_uses_cardmarket():
    sites = get_firecrawl_sites("europe", "pokemon")
    assert sites is not None
    assert "cardmarket.com" in sites


def test_europe_lego_uses_bricklink():
    sites = get_firecrawl_sites("europe", "lego")
    assert sites is not None
    assert "bricklink.com" in sites


def test_japan_anime_figures_uses_mandarake():
    sites = get_firecrawl_sites("japan", "anime_figures")
    assert sites is not None
    assert "mandarake.co.jp" in sites


def test_japan_manga_uses_surugaya():
    """suruga-ya should be in the combined firecrawl + crawl4ai target set."""
    fc_sites = get_firecrawl_sites("japan", "manga") or []
    c4_sites = get_crawl4ai_sites("japan", "manga") or []
    all_sites = fc_sites + c4_sites
    assert len(all_sites) > 0
    assert any("suruga-ya" in s for s in all_sites)


def test_americas_returns_none_uses_global_defaults():
    """Americas has no override — returns None so firecrawl_caller uses global defaults."""
    sites = get_firecrawl_sites("americas", "pokemon")
    assert sites is None


def test_none_region_returns_none():
    sites = get_firecrawl_sites(None, "pokemon")
    assert sites is None


def test_none_category_returns_none():
    sites = get_firecrawl_sites("europe", None)
    assert sites is None


def test_unknown_category_returns_none():
    sites = get_firecrawl_sites("europe", "nonexistent_category")
    assert sites is None


def test_all_europe_categories_have_ebay_de():
    """Every European override should include ebay.de as a fallback."""
    from app.lib.region_marketplace_config import _REGION_SITE_TARGETS

    eu_map = _REGION_SITE_TARGETS.get("europe", {})
    for cat, sites in eu_map.items():
        assert any("ebay.de" in s for s in sites), f"europe/{cat} missing ebay.de"


def test_all_japan_categories_have_jp_site():
    """Every Japanese override should include a .jp domain."""
    from app.lib.region_marketplace_config import _REGION_SITE_TARGETS

    jp_map = _REGION_SITE_TARGETS.get("japan", {})
    for cat, sites in jp_map.items():
        has_jp = any(
            ".jp" in s or ".co.jp" in s or "mercari.com/jp" in s
            for s in sites
        )
        assert has_jp, f"japan/{cat} missing .jp domain: {sites}"
