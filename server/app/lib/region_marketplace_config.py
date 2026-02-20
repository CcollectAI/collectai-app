"""
Region-aware marketplace routing configuration.

Maps user regions to:
- Which adapters to use (eBay, TCGPlayer, Firecrawl)
- Which eBay marketplace ID to target
- Which Firecrawl site targets to use per category
"""

from __future__ import annotations

from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# eBay marketplace IDs per region
# ---------------------------------------------------------------------------

_REGION_EBAY_MARKETPLACE: Dict[str, str] = {
    "americas": "EBAY_US",
    "europe": "EBAY_DE",
    "japan": "EBAY_JP",
    "korea": "EBAY_US",
    "other": "EBAY_US",
}


def get_ebay_marketplace_id(region: str | None) -> str:
    """Return the eBay marketplace ID for the given region."""
    return _REGION_EBAY_MARKETPLACE.get(region or "other", "EBAY_US")


# ---------------------------------------------------------------------------
# Adapter policy per region
# ---------------------------------------------------------------------------
# True = use this adapter, False = skip

_ADAPTER_POLICY: Dict[str, Dict[str, bool]] = {
    "americas": {"ebay": True, "tcgplayer": True, "firecrawl": True, "crawl4ai": True},
    "europe":   {"ebay": True, "tcgplayer": False, "firecrawl": True, "crawl4ai": True},
    "japan":    {"ebay": True, "tcgplayer": False, "firecrawl": True, "crawl4ai": True},
    "korea":    {"ebay": True, "tcgplayer": False, "firecrawl": True, "crawl4ai": True},
    "other":    {"ebay": True, "tcgplayer": True, "firecrawl": True, "crawl4ai": True},
}


def should_use_adapter(region: str | None, adapter: str) -> bool:
    """Return whether *adapter* should be queried for the given *region*."""
    policy = _ADAPTER_POLICY.get(region or "other", _ADAPTER_POLICY["other"])
    return policy.get(adapter, True)


# ---------------------------------------------------------------------------
# Region-specific Firecrawl site targets
# ---------------------------------------------------------------------------
# Overrides the global CATEGORY_SITE_TARGETS in firecrawl_caller.py when a
# user's region is known.  If a category is not listed here, the global
# defaults from firecrawl_caller.py are used.

_REGION_SITE_TARGETS: Dict[str, Dict[str, List[str]]] = {
    "europe": {
        # TCG → Cardmarket
        "pokemon":          ["cardmarket.com", "ebay.de", "pricecharting.com"],
        "mtg":              ["cardmarket.com", "ebay.de", "scryfall.com"],
        "yugioh":           ["cardmarket.com", "ebay.de", "tcgplayer.com"],
        "lorcana":          ["cardmarket.com", "ebay.de", "tcgplayer.com"],
        # Building
        "lego":             ["bricklink.com", "ebay.de", "brickset.com"],
        "warhammer":        ["thetrolltrader.com", "ebay.de", "blacklibrary.com", "amazon.de"],
        "gunpla":           ["hlj.com", "ebay.de", "amazon.de"],
        "scale_models":     ["scalemates.com", "ebay.de", "amazon.de"],
        # Toys
        "funko":            ["ebay.de", "vinted.de", "poppriceguide.com"],
        "designer_toys":    ["stockx.com", "ebay.de", "vinted.de"],
        "anime_figures":    ["myfigurecollection.net", "ebay.de", "amiami.com"],
        "hot_toys":         ["sideshow.com", "ebay.de", "zavvi.com"],
        # Media
        "manga":            ["mangacollectors.com", "ebay.de", "bookdepository.com"],
        "bluray_steelbook": ["blu-ray.com", "ebay.de", "zavvi.com"],
        "anime_bluray":     ["blu-ray.com", "ebay.de", "zavvi.com"],
        # Gaming
        "retro_games":      ["pricecharting.com", "ebay.de", "retroplace.com"],
        "retro_handhelds":  ["ebay.de", "pricecharting.com", "retroplace.com"],
        # Fandom
        "kpop_merch":       ["ebay.de", "vinted.de", "ktown4u.com", "cokodive.com"],
        "taylor_swift":     ["ebay.de", "vinted.de", "amazon.de"],
        "pop_fandom":       ["ebay.de", "vinted.de", "ktown4u.com", "amazon.de"],
        # Disney
        "disney":           ["shopdisney.com", "ebay.de", "vinted.de"],
        "theme_park":       ["ebay.de", "shopdisney.com", "vinted.de"],
        "ghibli":           ["ebay.de", "myfigurecollection.net", "amazon.de"],
        # Nintendo / Pokemon
        "nintendo_merch":   ["ebay.de", "vinted.de", "amazon.de"],
        "retro_pokemon":    ["ebay.de", "vinted.de", "cardmarket.com"],
        # Other
        "sportscards":      ["cardmarket.com", "ebay.de", "comc.com"],
        "diecast":          ["ebay.de", "diecastmodelswholesale.com", "amazon.de"],
        "one_piece":        ["myfigurecollection.net", "ebay.de", "amazon.de"],
        "loungefly":        ["ebay.de", "vinted.de", "amazon.de"],
        "keycaps":          ["ebay.de", "reddit.com/r/mechmarket", "amazon.de"],
        "vtuber":           ["ebay.de", "buyee.jp", "vinted.de"],
        "bandai_premium":   ["ebay.de", "myfigurecollection.net", "amazon.de"],
        "jp_magazine":      ["ebay.de", "buyee.jp", "amazon.de"],
        "jp_event":         ["ebay.de", "buyee.jp", "vinted.de"],
        "kpop_lightsticks": ["ebay.de", "ktown4u.com", "cokodive.com"],
        "anime_soundtrack": ["vgmdb.net", "ebay.de", "discogs.com"],
        "anime_ost_vinyl":  ["discogs.com", "ebay.de", "amazon.de"],
    },
    "japan": {
        # TCG — Mercari JP / Yahoo Auctions
        "pokemon":          ["mercari.com/jp", "yahoo.co.jp/auctions", "suruga-ya.jp"],
        "mtg":              ["mercari.com/jp", "yahoo.co.jp/auctions", "suruga-ya.jp"],
        "yugioh":           ["mercari.com/jp", "yahoo.co.jp/auctions", "suruga-ya.jp"],
        "lorcana":          ["mercari.com/jp", "yahoo.co.jp/auctions", "suruga-ya.jp"],
        # Figures
        "anime_figures":    ["mandarake.co.jp", "suruga-ya.jp", "amiami.com", "mercari.com/jp"],
        "hot_toys":         ["mandarake.co.jp", "suruga-ya.jp", "amiami.com"],
        "designer_toys":    ["mandarake.co.jp", "mercari.com/jp", "suruga-ya.jp"],
        # Building
        "gunpla":           ["hlj.com", "amiami.com", "suruga-ya.jp", "mercari.com/jp"],
        "lego":             ["bricklink.com", "mercari.com/jp", "yahoo.co.jp/auctions"],
        "warhammer":        ["mercari.com/jp", "suruga-ya.jp", "blacklibrary.com"],
        "scale_models":     ["hlj.com", "suruga-ya.jp", "mercari.com/jp"],
        # Media
        "manga":            ["mandarake.co.jp", "suruga-ya.jp", "mercari.com/jp"],
        "anime_bluray":     ["mandarake.co.jp", "suruga-ya.jp", "mercari.com/jp"],
        "bluray_steelbook": ["suruga-ya.jp", "mercari.com/jp", "mandarake.co.jp"],
        "anime_soundtrack": ["suruga-ya.jp", "mandarake.co.jp", "mercari.com/jp"],
        "anime_ost_vinyl":  ["suruga-ya.jp", "discogs.com", "mandarake.co.jp"],
        # Gaming
        "retro_games":      ["suruga-ya.jp", "mandarake.co.jp", "mercari.com/jp"],
        "retro_handhelds":  ["suruga-ya.jp", "mercari.com/jp", "mandarake.co.jp"],
        # JP Exclusives
        "bandai_premium":   ["mandarake.co.jp", "amiami.com", "mercari.com/jp"],
        "jp_magazine":      ["mandarake.co.jp", "suruga-ya.jp", "mercari.com/jp"],
        "jp_event":         ["mandarake.co.jp", "suruga-ya.jp", "mercari.com/jp"],
        # IP
        "one_piece":        ["mandarake.co.jp", "suruga-ya.jp", "amiami.com"],
        "vtuber":           ["buyee.jp", "mercari.com/jp", "booth.pm"],
        "ghibli":           ["mandarake.co.jp", "suruga-ya.jp", "mercari.com/jp"],
        # Nintendo
        "nintendo_merch":   ["mercari.com/jp", "suruga-ya.jp", "mandarake.co.jp"],
        "retro_pokemon":    ["mandarake.co.jp", "suruga-ya.jp", "mercari.com/jp"],
        # Fandom
        "kpop_merch":       ["mercari.com/jp", "ktown4u.com", "yahoo.co.jp/auctions"],
        "kpop_lightsticks": ["mercari.com/jp", "ktown4u.com", "yahoo.co.jp/auctions"],
        "taylor_swift":     ["mercari.com/jp", "yahoo.co.jp/auctions", "suruga-ya.jp"],
        "pop_fandom":       ["mercari.com/jp", "yahoo.co.jp/auctions", "suruga-ya.jp"],
        # Toys
        "funko":            ["mercari.com/jp", "mandarake.co.jp", "yahoo.co.jp/auctions"],
        # Niche
        "keycaps":          ["mercari.com/jp", "yahoo.co.jp/auctions", "booth.pm"],
        "loungefly":        ["mercari.com/jp", "yahoo.co.jp/auctions", "mandarake.co.jp"],
        # Disney
        "disney":           ["mercari.com/jp", "mandarake.co.jp", "yahoo.co.jp/auctions"],
        "theme_park":       ["mercari.com/jp", "yahoo.co.jp/auctions", "mandarake.co.jp"],
        # Legacy
        "diecast":          ["mercari.com/jp", "yahoo.co.jp/auctions", "suruga-ya.jp"],
        "sportscards":      ["mercari.com/jp", "yahoo.co.jp/auctions", "suruga-ya.jp"],
    },
    "korea": {
        # K-pop — Korean marketplace dominance
        "kpop_merch":       ["yes24.com", "aladin.co.kr", "ktown4u.com", "cokodive.com"],
        "kpop_lightsticks": ["yes24.com", "ktown4u.com", "cokodive.com", "bunjang.co.kr"],
        "pop_fandom":       ["yes24.com", "ktown4u.com", "cokodive.com", "bunjang.co.kr"],
        # TCGs
        "pokemon":          ["yes24.com", "ebay.com", "bunjang.co.kr"],
        "mtg":              ["yes24.com", "ebay.com", "bunjang.co.kr"],
        "yugioh":           ["yes24.com", "ebay.com", "bunjang.co.kr"],
        "lorcana":          ["yes24.com", "ebay.com", "bunjang.co.kr"],
        # Figures & Toys
        "anime_figures":    ["yes24.com", "myfigurecollection.net", "bunjang.co.kr"],
        "funko":            ["yes24.com", "ebay.com", "bunjang.co.kr"],
        "designer_toys":    ["stockx.com", "ebay.com", "bunjang.co.kr"],
        "hot_toys":         ["sideshow.com", "ebay.com", "bunjang.co.kr"],
        # Building / Models
        "lego":             ["bricklink.com", "yes24.com", "bunjang.co.kr"],
        "gunpla":           ["yes24.com", "hlj.com", "bunjang.co.kr"],
        "warhammer":        ["ebay.com", "thetrolltrader.com", "bunjang.co.kr"],
        "scale_models":     ["scalemates.com", "yes24.com", "bunjang.co.kr"],
        # Media
        "manga":            ["yes24.com", "aladin.co.kr", "bunjang.co.kr"],
        "anime_bluray":     ["yes24.com", "cdjapan.co.jp", "aladin.co.kr"],
        "bluray_steelbook": ["yes24.com", "ebay.com", "aladin.co.kr"],
        "anime_soundtrack": ["yes24.com", "vgmdb.net", "aladin.co.kr"],
        "anime_ost_vinyl":  ["yes24.com", "discogs.com", "aladin.co.kr"],
        # Gaming
        "retro_games":      ["yes24.com", "pricecharting.com", "bunjang.co.kr"],
        "retro_handhelds":  ["yes24.com", "ebay.com", "bunjang.co.kr"],
        # Disney / Theme Parks
        "disney":           ["yes24.com", "shopdisney.com", "bunjang.co.kr"],
        "theme_park":       ["yes24.com", "ebay.com", "bunjang.co.kr"],
        "ghibli":           ["yes24.com", "myfigurecollection.net", "bunjang.co.kr"],
        # Japan Exclusives
        "bandai_premium":   ["yes24.com", "myfigurecollection.net", "bunjang.co.kr"],
        "jp_magazine":      ["yes24.com", "buyee.jp", "aladin.co.kr"],
        "jp_event":         ["yes24.com", "buyee.jp", "bunjang.co.kr"],
        # Nintendo
        "nintendo_merch":   ["yes24.com", "ebay.com", "bunjang.co.kr"],
        "retro_pokemon":    ["yes24.com", "ebay.com", "bunjang.co.kr"],
        # IP-Specific
        "one_piece":        ["yes24.com", "myfigurecollection.net", "bunjang.co.kr"],
        "vtuber":           ["yes24.com", "buyee.jp", "bunjang.co.kr"],
        # Niche
        "keycaps":          ["yes24.com", "reddit.com/r/mechmarket", "bunjang.co.kr"],
        "loungefly":        ["yes24.com", "ebay.com", "bunjang.co.kr"],
        # Legacy
        "diecast":          ["yes24.com", "ebay.com", "bunjang.co.kr"],
        "sportscards":      ["yes24.com", "ebay.com", "bunjang.co.kr"],
        "taylor_swift":     ["yes24.com", "ebay.com", "bunjang.co.kr"],
    },
    # "americas" intentionally omitted — falls through to global defaults
    # in firecrawl_caller.py CATEGORY_SITE_TARGETS.
}


def get_firecrawl_sites(
    region: str | None,
    category: str | None,
) -> Optional[List[str]]:
    """Return region-specific Firecrawl site targets, or None to use global defaults."""
    if not region or not category:
        return None
    region_map = _REGION_SITE_TARGETS.get(region)
    if not region_map:
        return None
    return region_map.get(category)


def get_crawl4ai_sites(
    region: str | None,
    category: str | None,
) -> Optional[List[str]]:
    """Return region-specific Crawl4AI site targets.

    Delegates to get_firecrawl_sites() — both adapters target the same sites.
    """
    return get_firecrawl_sites(region, category)
