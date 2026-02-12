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
    "americas": {"ebay": True, "tcgplayer": True, "firecrawl": True},
    "europe":   {"ebay": True, "tcgplayer": False, "firecrawl": True},
    "japan":    {"ebay": True, "tcgplayer": False, "firecrawl": True},
    "other":    {"ebay": True, "tcgplayer": True, "firecrawl": True},
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
        "pokemon":          ["cardmarket.com", "ebay.de"],
        "mtg":              ["cardmarket.com", "ebay.de"],
        "yugioh":           ["cardmarket.com", "ebay.de"],
        "lorcana":          ["cardmarket.com", "ebay.de"],
        # Building
        "lego":             ["bricklink.com", "ebay.de"],
        "warhammer":        ["thetrolltrader.com", "ebay.de"],
        "gunpla":           ["hlj.com", "ebay.de"],
        "scale_models":     ["scalemates.com", "ebay.de"],
        # Toys
        "funko":            ["ebay.de", "vinted.de"],
        "designer_toys":    ["stockx.com", "ebay.de"],
        "anime_figures":    ["myfigurecollection.net", "ebay.de"],
        "hot_toys":         ["sideshow.com", "ebay.de"],
        # Media
        "manga":            ["mangacollectors.com", "ebay.de"],
        "bluray_steelbook": ["blu-ray.com", "ebay.de"],
        "anime_bluray":     ["blu-ray.com", "ebay.de"],
        # Gaming
        "retro_games":      ["pricecharting.com", "ebay.de"],
        "retro_handhelds":  ["ebay.de", "pricecharting.com"],
        # Fandom
        "kpop_merch":       ["ebay.de", "vinted.de"],
        "taylor_swift":     ["ebay.de", "vinted.de"],
        "pop_fandom":       ["ebay.de", "vinted.de"],
        # Disney
        "disney":           ["shopdisney.com", "ebay.de"],
        "theme_park":       ["ebay.de", "shopdisney.com"],
        "ghibli":           ["ebay.de", "myfigurecollection.net"],
        # Nintendo / Pokemon
        "nintendo_merch":   ["ebay.de", "vinted.de"],
        "retro_pokemon":    ["ebay.de", "vinted.de"],
        # Other
        "sportscards":      ["cardmarket.com", "ebay.de"],
        "diecast":          ["ebay.de", "diecastmodelswholesale.com"],
        "one_piece":        ["myfigurecollection.net", "ebay.de"],
        "loungefly":        ["ebay.de", "vinted.de"],
        "keycaps":          ["ebay.de", "reddit.com/r/mechmarket"],
        "vtuber":           ["ebay.de", "buyee.jp"],
        "bandai_premium":   ["ebay.de", "myfigurecollection.net"],
        "jp_magazine":      ["ebay.de", "buyee.jp"],
        "jp_event":         ["ebay.de", "buyee.jp"],
        "kpop_lightsticks": ["ebay.de", "ktown4u.com"],
        "anime_soundtrack": ["vgmdb.net", "ebay.de"],
        "anime_ost_vinyl":  ["discogs.com", "ebay.de"],
    },
    "japan": {
        # TCG — Mercari JP / Yahoo Auctions
        "pokemon":          ["mercari.com/jp", "yahoo.co.jp/auctions"],
        "mtg":              ["mercari.com/jp", "yahoo.co.jp/auctions"],
        "yugioh":           ["mercari.com/jp", "yahoo.co.jp/auctions"],
        "lorcana":          ["mercari.com/jp", "yahoo.co.jp/auctions"],
        # Figures
        "anime_figures":    ["mandarake.co.jp", "suruga-ya.jp", "amiami.com"],
        "hot_toys":         ["mandarake.co.jp", "suruga-ya.jp"],
        "designer_toys":    ["mandarake.co.jp", "mercari.com/jp"],
        # Building
        "gunpla":           ["hlj.com", "amiami.com", "suruga-ya.jp"],
        "lego":             ["bricklink.com", "mercari.com/jp"],
        "warhammer":        ["mercari.com/jp", "suruga-ya.jp"],
        "scale_models":     ["hlj.com", "suruga-ya.jp"],
        # Media
        "manga":            ["mandarake.co.jp", "suruga-ya.jp"],
        "anime_bluray":     ["mandarake.co.jp", "suruga-ya.jp"],
        "bluray_steelbook": ["suruga-ya.jp", "mercari.com/jp"],
        "anime_soundtrack": ["suruga-ya.jp", "mandarake.co.jp"],
        "anime_ost_vinyl":  ["suruga-ya.jp", "discogs.com"],
        # Gaming
        "retro_games":      ["suruga-ya.jp", "mandarake.co.jp"],
        "retro_handhelds":  ["suruga-ya.jp", "mercari.com/jp"],
        # JP Exclusives
        "bandai_premium":   ["mandarake.co.jp", "amiami.com"],
        "jp_magazine":      ["mandarake.co.jp", "suruga-ya.jp"],
        "jp_event":         ["mandarake.co.jp", "suruga-ya.jp"],
        # IP
        "one_piece":        ["mandarake.co.jp", "suruga-ya.jp"],
        "vtuber":           ["buyee.jp", "mercari.com/jp"],
        "ghibli":           ["mandarake.co.jp", "suruga-ya.jp"],
        # Nintendo
        "nintendo_merch":   ["mercari.com/jp", "suruga-ya.jp"],
        "retro_pokemon":    ["mandarake.co.jp", "suruga-ya.jp"],
        # Fandom
        "kpop_merch":       ["mercari.com/jp", "ktown4u.com"],
        "kpop_lightsticks": ["mercari.com/jp", "ktown4u.com"],
        "taylor_swift":     ["mercari.com/jp", "yahoo.co.jp/auctions"],
        "pop_fandom":       ["mercari.com/jp", "yahoo.co.jp/auctions"],
        # Toys
        "funko":            ["mercari.com/jp", "mandarake.co.jp"],
        # Niche
        "keycaps":          ["mercari.com/jp", "yahoo.co.jp/auctions"],
        "loungefly":        ["mercari.com/jp", "yahoo.co.jp/auctions"],
        # Disney
        "disney":           ["mercari.com/jp", "mandarake.co.jp"],
        "theme_park":       ["mercari.com/jp", "yahoo.co.jp/auctions"],
        # Legacy
        "diecast":          ["mercari.com/jp", "yahoo.co.jp/auctions"],
        "sportscards":      ["mercari.com/jp", "yahoo.co.jp/auctions"],
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
