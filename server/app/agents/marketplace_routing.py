"""
Marketplace adapter routing configuration.

Maps adapter names to the set of categories they serve.
Adapters with ``None`` as their category set are unrestricted (all categories).
"""

from __future__ import annotations

from typing import Dict, Optional, Set


# ---------------------------------------------------------------------------
# Source reliability weights
# ---------------------------------------------------------------------------

SOURCE_RELIABILITY: Dict[str, float] = {
    "ebay_sold": 0.95,
    "tcgplayer": 0.90,
    "mavin": 0.80,
    "mavin_sold": 0.85,
    "mercari_us": 0.70,
    "mercari_us_sold": 0.75,
    "ebay_listed": 0.70,
    "whatnot": 0.65,
    "whatnot_sold": 0.75,
    "vinted": 0.65,
    "vinted_sold": 0.70,
    "firecrawl": 0.65,
    "firecrawl_sold": 0.70,
    "crawl4ai": 0.60,
    "crawl4ai_sold": 0.65,
    "catawiki": 0.80,
    "catawiki_sold": 0.90,
    "whisky_auctioneer": 0.85,
    "whisky_auctioneer_sold": 0.95,
    "mandarake": 0.75,
    "bezel": 0.80,
    "bezel_sold": 0.85,
    "chrono24": 0.70,
    "chrono24_sold": 0.75,
    "keh": 0.85,
    "mpb": 0.80,
    "drop": 0.75,
    "gouletpens": 0.80,
    "brickeconomy": 0.85,
    "brickeconomy_sold": 0.90,
    "popmart": 0.75,
    "booth": 0.70,
    "scalemates": 0.75,
    "ktown4u": 0.75,
    "comicbookrealm": 0.80,
    "comicbookrealm_sold": 0.85,
    "masterofmalt": 0.80,
    "pricecharting": 0.85,
    "pricecharting_sold": 0.90,
    "yahoo_auctions": 0.75,
    "yahoo_auctions_sold": 0.80,
    "stockx": 0.85,
    "stockx_sold": 0.90,
    "discogs": 0.80,
    "discogs_sold": 0.85,
    "cardmarket": 0.85,
    "cardmarket_sold": 0.90,
    "bricklink": 0.90,
    "bricklink_sold": 0.95,
    "scrapedo": 0.70,
    "scrapedo_sold": 0.75,
    "grailed": 0.70,
    "grailed_sold": 0.75,
    "google_shopping": 0.75,
    "etsy": 0.75,
    "etsy_sold": 0.65,
    "comc": 0.80,
    "comc_sold": 0.85,
    "reverb": 0.80,
    "reverb_sold": 0.85,
    "abebooks": 0.80,
    "abebooks_sold": 0.80,
    "leboncoin": 0.65,
    "marktplaats": 0.60,
    "wallapop": 0.60,
    "gumtree": 0.55,
    "depop": 0.65,
    "kleinanzeigen": 0.65,
}

# Bonus scores
RECENCY_7D_BOOST = 0.10
RECENCY_30D_BOOST = 0.05
SOLD_BONUS = 0.15
CONDITION_MATCH_BONUS = 0.10


# ---------------------------------------------------------------------------
# Category routing matrix
#
# Keys = adapter names (matching the attribute names on MarketplaceAgent,
# without the leading underscore).
# Values = set of categories the adapter serves, or None for unrestricted.
# ---------------------------------------------------------------------------

ADAPTER_CATEGORY_ROUTING: Dict[str, Optional[Set[str]]] = {
    # Unrestricted (all categories)
    "ebay": None,
    "firecrawl": None,
    "crawl4ai": None,
    "scrapedo": None,
    "google_shopping": None,
    "mercari_us": None,
    "vinted": None,
    "mavin": None,
    # Category-routed
    "tcgplayer": {"pokemon", "mtg", "yugioh", "lorcana", "digimon", "one_piece_tcg"},
    "grailed": {"sneakers", "hot_toys", "funko", "designer_toys", "pop_fandom"},
    "whatnot": {
        "pokemon", "mtg", "yugioh", "lorcana", "funko", "sportscards",
        "designer_toys", "hot_toys", "anime_figures", "kpop_merch",
        "action_figures", "vintage_toys", "marvel_legends", "nintendo_merch",
        "blind_box", "plush_collectibles", "disney", "lego", "comic_books",
        "digimon", "one_piece_tcg", "sneakers", "retro_games", "warhammer",
        "oop_board_games", "city_pop_vinyl",
    },
    "catawiki": {
        "watches", "comic_books", "vintage_toys", "designer_toys", "pens",
        "whiskey", "fragrances", "anime_figures", "sportscards", "vinyl_records",
        "diecast", "art", "coins", "vintage_cameras", "loungefly",
        "oop_board_games",
    },
    "whisky_auctioneer": {"whiskey"},
    "mandarake": {
        "anime_figures", "bandai_premium", "ghibli", "jp_event", "jp_magazine",
        "hot_toys", "gunpla", "designer_toys", "manga", "vtuber",
        "nintendo_merch", "one_piece", "digimon", "blind_box", "plush_collectibles",
    },
    "bezel": {"watches"},
    "chrono24": {"watches"},
    "keh": {"vintage_cameras"},
    "mpb": {"vintage_cameras"},
    "drop": {"keycaps"},
    "gouletpens": {"pens"},
    "brickeconomy": {"lego"},
    "popmart": {"blind_box", "designer_toys"},
    "booth": {"vtuber", "jp_event", "designer_toys", "kpop_lightsticks"},
    "scalemates": {"scale_models", "gunpla", "diecast"},
    "ktown4u": {"kpop", "kpop_lightsticks", "blind_box"},
    "comicbookrealm": {"comic_books"},
    "masterofmalt": {"whiskey"},
    "pricecharting": {"retro_games", "retro_handhelds", "pokemon", "nintendo_merch", "sportscards"},
    "yahoo_auctions": {
        "bandai_premium", "jp_event", "jp_magazine", "ghibli", "anime_figures",
        "retro_pokemon", "vtuber", "gunpla", "anime_bluray", "anime_soundtrack",
        "anime_ost_vinyl", "one_piece", "hot_toys", "nintendo_merch", "kpop_merch",
        "keycaps", "scale_models", "warhammer", "digimon", "one_piece_tcg",
        "manga", "designer_toys", "blind_box", "plush_collectibles",
        "city_pop_vinyl", "oop_board_games",
    },
    "stockx": {
        "sneakers", "designer_toys", "funko", "kpop_merch", "taylor_swift",
        "pop_fandom", "loungefly", "hot_toys", "nintendo_merch", "blind_box",
    },
    "discogs": {
        "vinyl_records", "anime_ost_vinyl", "anime_soundtrack", "kpop_merch",
        "taylor_swift", "pop_fandom", "bluray_steelbook", "kpop_lightsticks",
        "city_pop_vinyl",
    },
    "cardmarket": {"pokemon", "mtg", "yugioh", "lorcana", "digimon", "one_piece_tcg"},
    "bricklink": {"lego"},
    "etsy": {
        "vintage_toys", "watches", "pens", "plush_collectibles", "blind_box",
        "vintage_cameras", "keycaps", "diorama", "custom_builds", "scale_models",
        "designer_toys", "funko",
    },
    "comc": {"sportscards", "pokemon", "mtg", "yugioh"},
    "reverb": {"vinyl_records", "anime_ost_vinyl"},
    "abebooks": {"comic_books", "manga"},
    "leboncoin": None,  # unrestricted — France's largest general classifieds
    "marktplaats": None,  # unrestricted — Netherlands' largest classifieds (eBay-owned)
    "wallapop": None,  # unrestricted — Spain's largest second-hand marketplace
    "gumtree": None,  # unrestricted — UK's largest classifieds
    "depop": {"sneakers", "vintage_toys", "designer_toys", "kpop_merch", "streetwear", "funko"},  # UK fashion/streetwear resale
    "kleinanzeigen": None,  # unrestricted — Germany's largest classifieds (50M+ users)
}


def adapter_serves_category(adapter_name: str, category: Optional[str]) -> bool:
    """Return True if *adapter_name* should be queried for *category*.

    When *category* is ``None`` (i.e. the caller didn't specify one),
    every adapter is eligible.
    """
    cats = ADAPTER_CATEGORY_ROUTING.get(adapter_name)
    if cats is None:
        return True  # unrestricted adapter
    if category is None:
        return True  # no category filter — query everything
    return category in cats
