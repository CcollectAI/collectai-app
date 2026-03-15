"""
Curated Niche & High-End Perfumery Import Pipeline — Inventory/Collection Tracking.

This category is focused on COLLECTION INVENTORY TRACKING rather than resale/trading.
Users track their fragrance wardrobes — bottle counts, fill levels, notes, and ratings.

Imports a curated catalog of 700+ fragrances across major niche and designer houses:
  - Maison Francis Kurkdjian (Baccarat Rouge 540, Grand Soir, etc.)
  - Tom Ford Private Blend (Oud Wood, Tobacco Vanille, Lost Cherry, etc.)
  - Creed (Aventus, Green Irish Tweed, Silver Mountain Water, etc.)
  - Parfums de Marly (Layton, Herod, Pegasus, etc.)
  - Xerjoff (Naxos, Renaissance, Erba Pura, etc.)
  - Amouage (Interlude Man, Jubilation XXV, etc.)
  - Byredo, Le Labo, Diptyque, Penhaligon's, Frederic Malle, etc.
  - Indie houses (Zoologist, Imaginary Authors, Tauer, etc.)

Pattern follows import_whiskey.py.

Usage:
    python -m pipelines.import_niche_perfumery [--dry-run] [--jsonl-only] [--cache-images]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines.import_common import (
    CatalogItem,
    PriceObservation,
    SupabaseIngest,
    write_training_jsonl,
    write_catalog_sql,
    cache_catalog_images,
    log_progress,
    slugify,
    rarity_score as shared_rarity_score,
    logger,
    close_http_client,
)

CATEGORY = "niche_perfumery"

HOUSE_TIER: dict[str, float] = {
    # Ultra-premium (1.0)
    "Clive Christian": 1.0,
    "Roja Parfums": 1.0,
    "Xerjoff": 0.95,
    "Amouage": 0.95,
    "Tiziana Terenzi": 0.9,
    # Premium niche (0.9)
    "Maison Francis Kurkdjian": 0.9,
    "Tom Ford": 0.9,
    "Creed": 0.9,
    "Frederic Malle": 0.9,
    "Kilian": 0.9,
    "Initio": 0.85,
    "Ex Nihilo": 0.85,
    "Parfums de Marly": 0.85,
    "Nishane": 0.85,
    "Memo Paris": 0.85,
    "Penhaligon's": 0.85,
    # High niche (0.8)
    "Byredo": 0.8,
    "Le Labo": 0.8,
    "Diptyque": 0.8,
    "Aesop": 0.8,
    "Acqua di Parma": 0.8,
    "Serge Lutens": 0.8,
    "Comme des Garçons": 0.8,
    "Histoires de Parfums": 0.8,
    "Juliette Has A Gun": 0.8,
    "Vilhelm Parfumerie": 0.8,
    # Mid niche (0.7)
    "Montale": 0.7,
    "Mancera": 0.7,
    "Maison Margiela": 0.7,
    "Clean Reserve": 0.7,
    "D.S. & Durga": 0.75,
    "Zoologist": 0.75,
    "Imaginary Authors": 0.7,
    "Gallivant": 0.7,
    "Tauer Perfumes": 0.75,
    "Ormonde Jayne": 0.75,
    "Papillon Artisan Perfumes": 0.75,
    "Masque Milano": 0.75,
    "Jul et Mad": 0.75,
    "BDK Parfums": 0.75,
    "Parfums de Nicolai": 0.75,
    "Atelier Cologne": 0.75,
    "Maison Crivelli": 0.7,
    "Goldfield & Banks": 0.75,
    "Escentric Molecules": 0.75,
}


def _house_tier(house: str) -> float:
    return HOUSE_TIER.get(house, 0.6)


def _mfk() -> list[dict]:
    """Maison Francis Kurkdjian fragrances."""
    return [
        {"name": "Baccarat Rouge 540 EDP 70ml", "house": "Maison Francis Kurkdjian", "fragrance_name": "Baccarat Rouge 540", "concentration": "EDP", "size_ml": 70, "gender": "unisex", "fragrance_family": "amber floral", "top_notes": "saffron, jasmine", "heart_notes": "amberwood, ambergris", "base_notes": "fir resin, cedar", "price_eur": 255, "rarity": "Common", "year": 2015, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Baccarat Rouge 540 Extrait 70ml", "house": "Maison Francis Kurkdjian", "fragrance_name": "Baccarat Rouge 540", "concentration": "Extrait", "size_ml": 70, "gender": "unisex", "fragrance_family": "amber floral", "top_notes": "bitter almond, saffron", "heart_notes": "ambergris, cedar", "base_notes": "fir balsam", "price_eur": 355, "rarity": "Common", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Grand Soir EDP 70ml", "house": "Maison Francis Kurkdjian", "fragrance_name": "Grand Soir", "concentration": "EDP", "size_ml": 70, "gender": "unisex", "fragrance_family": "amber", "top_notes": "amber, benzoin", "heart_notes": "tonka bean, vanilla", "base_notes": "amber, labdanum", "price_eur": 220, "rarity": "Common", "year": 2016, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Oud Satin Mood EDP 70ml", "house": "Maison Francis Kurkdjian", "fragrance_name": "Oud Satin Mood", "concentration": "EDP", "size_ml": 70, "gender": "unisex", "fragrance_family": "oriental", "top_notes": "Bulgarian rose, violet", "heart_notes": "oud, benzoin", "base_notes": "vanilla, white musk", "price_eur": 295, "rarity": "Common", "year": 2018, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Aqua Universalis EDT 70ml", "house": "Maison Francis Kurkdjian", "fragrance_name": "Aqua Universalis", "concentration": "EDT", "size_ml": 70, "gender": "unisex", "fragrance_family": "citrus white floral", "top_notes": "bergamot, lemon", "heart_notes": "lily of the valley, white flowers", "base_notes": "white musk", "price_eur": 175, "rarity": "Common", "year": 2009, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Gentle Fluidity Gold EDP 70ml", "house": "Maison Francis Kurkdjian", "fragrance_name": "Gentle Fluidity Gold", "concentration": "EDP", "size_ml": 70, "gender": "unisex", "fragrance_family": "amber vanilla", "top_notes": "juniper berry, coriander", "heart_notes": "musks, amber", "base_notes": "vanilla, sandalwood", "price_eur": 215, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Gentle Fluidity Silver EDP 70ml", "house": "Maison Francis Kurkdjian", "fragrance_name": "Gentle Fluidity Silver", "concentration": "EDP", "size_ml": 70, "gender": "unisex", "fragrance_family": "woody aromatic", "top_notes": "juniper berry, nutmeg", "heart_notes": "amber, musks", "base_notes": "vanilla, woods", "price_eur": 215, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
    ]


def _tom_ford() -> list[dict]:
    """Tom Ford Private Blend."""
    return [
        {"name": "Oud Wood EDP 50ml", "house": "Tom Ford", "fragrance_name": "Oud Wood", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "woody oud", "top_notes": "oud, rosewood", "heart_notes": "cardamom, sandalwood", "base_notes": "tonka bean, vetiver", "price_eur": 250, "rarity": "Common", "year": 2007, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Tobacco Vanille EDP 50ml", "house": "Tom Ford", "fragrance_name": "Tobacco Vanille", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "tobacco vanilla", "top_notes": "tobacco leaf, spices", "heart_notes": "vanilla, cacao", "base_notes": "dried fruits, wood sap", "price_eur": 250, "rarity": "Common", "year": 2007, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Lost Cherry EDP 50ml", "house": "Tom Ford", "fragrance_name": "Lost Cherry", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "fruity gourmand", "top_notes": "black cherry, cherry liqueur", "heart_notes": "bitter almond, Turkish rose", "base_notes": "Peru balsam, roasted tonka", "price_eur": 290, "rarity": "Common", "year": 2018, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Tuscan Leather EDP 50ml", "house": "Tom Ford", "fragrance_name": "Tuscan Leather", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "leather", "top_notes": "raspberry, saffron", "heart_notes": "olibanum, jasmine", "base_notes": "leather, amber, suede", "price_eur": 250, "rarity": "Common", "year": 2007, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Neroli Portofino EDP 50ml", "house": "Tom Ford", "fragrance_name": "Neroli Portofino", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "citrus aromatic", "top_notes": "neroli, bergamot, lemon", "heart_notes": "neroli, orange blossom", "base_notes": "amber, musk", "price_eur": 230, "rarity": "Common", "year": 2011, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Bitter Peach EDP 50ml", "house": "Tom Ford", "fragrance_name": "Bitter Peach", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "fruity sweet", "top_notes": "peach, blood orange", "heart_notes": "cardamom, rum", "base_notes": "patchouli, vanilla, cashmeran", "price_eur": 290, "rarity": "Common", "year": 2020, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "F*cking Fabulous EDP 50ml", "house": "Tom Ford", "fragrance_name": "F*cking Fabulous", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "leather amber", "top_notes": "lavender, bitter almond", "heart_notes": "orris, leather", "base_notes": "amber, tonka, cashmeran", "price_eur": 310, "rarity": "Uncommon", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
    ]


def _creed() -> list[dict]:
    """Creed fragrances."""
    return [
        {"name": "Aventus EDP 100ml", "house": "Creed", "fragrance_name": "Aventus", "concentration": "EDP", "size_ml": 100, "gender": "masculine", "fragrance_family": "fruity woody", "top_notes": "pineapple, bergamot, apple", "heart_notes": "birch, patchouli, jasmine", "base_notes": "musk, oakmoss, ambergris, vanilla", "price_eur": 410, "rarity": "Common", "year": 2010, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Green Irish Tweed EDP 100ml", "house": "Creed", "fragrance_name": "Green Irish Tweed", "concentration": "EDP", "size_ml": 100, "gender": "masculine", "fragrance_family": "green aromatic", "top_notes": "lemon verbena, iris", "heart_notes": "violet leaves", "base_notes": "ambergris, sandalwood", "price_eur": 330, "rarity": "Common", "year": 1985, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Silver Mountain Water EDP 100ml", "house": "Creed", "fragrance_name": "Silver Mountain Water", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "green tea citrus", "top_notes": "bergamot, mandarin, green tea", "heart_notes": "black currant, jasmine", "base_notes": "musk, sandalwood, galbanum", "price_eur": 330, "rarity": "Common", "year": 1995, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Viking EDP 100ml", "house": "Creed", "fragrance_name": "Viking", "concentration": "EDP", "size_ml": 100, "gender": "masculine", "fragrance_family": "aromatic spicy", "top_notes": "bergamot, lemon, pepper", "heart_notes": "rose, olibanum", "base_notes": "vetiver, sandalwood", "price_eur": 380, "rarity": "Common", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Millesime Imperial EDP 100ml", "house": "Creed", "fragrance_name": "Millesime Imperial", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "marine citrus", "top_notes": "sea salt, bergamot, lemon", "heart_notes": "iris, marine notes", "base_notes": "musk, amber, woody notes", "price_eur": 330, "rarity": "Common", "year": 1995, "image_url": "https://fimgs.net/mdimg/placeholder"},
    ]


def _pdm() -> list[dict]:
    """Parfums de Marly."""
    return [
        {"name": "Layton EDP 125ml", "house": "Parfums de Marly", "fragrance_name": "Layton", "concentration": "EDP", "size_ml": 125, "gender": "masculine", "fragrance_family": "aromatic vanilla", "top_notes": "apple, bergamot, lavender", "heart_notes": "jasmine, violet, geranium", "base_notes": "vanilla, cardamom, sandalwood, pepper", "price_eur": 240, "rarity": "Common", "year": 2016, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Herod EDP 125ml", "house": "Parfums de Marly", "fragrance_name": "Herod", "concentration": "EDP", "size_ml": 125, "gender": "masculine", "fragrance_family": "tobacco vanilla", "top_notes": "cinnamon, pepper, incense", "heart_notes": "tobacco, osmanthus", "base_notes": "vanilla, musk, vetiver, cedar", "price_eur": 240, "rarity": "Common", "year": 2012, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Pegasus EDP 125ml", "house": "Parfums de Marly", "fragrance_name": "Pegasus", "concentration": "EDP", "size_ml": 125, "gender": "masculine", "fragrance_family": "almond vanilla", "top_notes": "heliotrope, bitter almond, bergamot", "heart_notes": "jasmine, vanilla", "base_notes": "sandalwood, amber, musk", "price_eur": 240, "rarity": "Common", "year": 2014, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Delina EDP 75ml", "house": "Parfums de Marly", "fragrance_name": "Delina", "concentration": "EDP", "size_ml": 75, "gender": "feminine", "fragrance_family": "floral fruity", "top_notes": "litchi, rhubarb, bergamot", "heart_notes": "Turkish rose, peony, lily of the valley", "base_notes": "musk, cashmeran, vanilla, cedar", "price_eur": 260, "rarity": "Common", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Sedley EDP 125ml", "house": "Parfums de Marly", "fragrance_name": "Sedley", "concentration": "EDP", "size_ml": 125, "gender": "unisex", "fragrance_family": "green aromatic", "top_notes": "mint, bergamot, mandarin", "heart_notes": "geranium, lavender", "base_notes": "sandalwood, musk", "price_eur": 215, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
    ]


def _xerjoff_amouage() -> list[dict]:
    """Xerjoff and Amouage."""
    return [
        {"name": "Naxos EDP 100ml", "house": "Xerjoff", "fragrance_name": "Naxos", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "tobacco honey", "top_notes": "lavender, bergamot, cinnamon", "heart_notes": "honey, tobacco, cashmeran", "base_notes": "tonka bean, vanilla", "price_eur": 220, "rarity": "Common", "year": 2015, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Renaissance EDP 100ml", "house": "Xerjoff", "fragrance_name": "Renaissance", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "citrus leather", "top_notes": "citrus, leather", "heart_notes": "jasmine, rose", "base_notes": "musk, amber", "price_eur": 250, "rarity": "Uncommon", "year": 2008, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Erba Pura EDP 100ml", "house": "Xerjoff", "fragrance_name": "Erba Pura", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "fruity amber", "top_notes": "orange, Sicilian lemon, calabrian bergamot", "heart_notes": "white fruits", "base_notes": "musk, amber, Madagascar vanilla", "price_eur": 200, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Alexandria II EDP 100ml", "house": "Xerjoff", "fragrance_name": "Alexandria II", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "citrus amber", "top_notes": "mandarin, bergamot", "heart_notes": "jasmine, peach", "base_notes": "musk, amber, vanilla, caramel", "price_eur": 300, "rarity": "Uncommon", "year": 2011, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Interlude Man EDP 100ml", "house": "Amouage", "fragrance_name": "Interlude Man", "concentration": "EDP", "size_ml": 100, "gender": "masculine", "fragrance_family": "smoky woody", "top_notes": "oregano, bergamot, opoponax", "heart_notes": "olibanum, amber, labdanum", "base_notes": "agarwood, sandalwood, patchouli", "price_eur": 310, "rarity": "Common", "year": 2012, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Jubilation XXV Man EDP 100ml", "house": "Amouage", "fragrance_name": "Jubilation XXV Man", "concentration": "EDP", "size_ml": 100, "gender": "masculine", "fragrance_family": "oriental woody", "top_notes": "orange, frankincense, blackberry", "heart_notes": "rose, orchid, guaiac wood", "base_notes": "oud, musk, myrrh, amber", "price_eur": 350, "rarity": "Uncommon", "year": 2007, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Reflection Man EDP 100ml", "house": "Amouage", "fragrance_name": "Reflection Man", "concentration": "EDP", "size_ml": 100, "gender": "masculine", "fragrance_family": "floral woody", "top_notes": "rosemary, pink pepper, neroli", "heart_notes": "jasmine, rose, orris", "base_notes": "sandalwood, cedarwood, vetiver", "price_eur": 290, "rarity": "Common", "year": 2007, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Memoir Man EDP 100ml", "house": "Amouage", "fragrance_name": "Memoir Man", "concentration": "EDP", "size_ml": 100, "gender": "masculine", "fragrance_family": "green smoky", "top_notes": "basil, chamomile, bitter orange", "heart_notes": "incense, oud", "base_notes": "cedar, leather, vetiver", "price_eur": 290, "rarity": "Common", "year": 2010, "image_url": "https://fimgs.net/mdimg/placeholder"},
    ]


def _byredo_lelabo() -> list[dict]:
    """Byredo and Le Labo."""
    return [
        {"name": "Gypsy Water EDP 100ml", "house": "Byredo", "fragrance_name": "Gypsy Water", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "woody aromatic", "top_notes": "bergamot, lemon, pepper", "heart_notes": "incense, pine needle, orris", "base_notes": "amber, vanilla, sandalwood", "price_eur": 190, "rarity": "Common", "year": 2008, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Bal d'Afrique EDP 100ml", "house": "Byredo", "fragrance_name": "Bal d'Afrique", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "floral woody musk", "top_notes": "bergamot, lemon, neroli", "heart_notes": "violet, jasmine, cyclamen", "base_notes": "vetiver, amber, musk", "price_eur": 190, "rarity": "Common", "year": 2009, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Mojave Ghost EDP 100ml", "house": "Byredo", "fragrance_name": "Mojave Ghost", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "woody aromatic", "top_notes": "sapodilla, ambrette", "heart_notes": "violet, sandalwood", "base_notes": "choya, musk, cedar", "price_eur": 190, "rarity": "Common", "year": 2014, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Santal 33 EDP 100ml", "house": "Le Labo", "fragrance_name": "Santal 33", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "woody aromatic", "top_notes": "cardamom, iris, violet", "heart_notes": "Australian sandalwood, papyrus", "base_notes": "cedarwood, leather, amber, musk", "price_eur": 230, "rarity": "Common", "year": 2011, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Rose 31 EDP 100ml", "house": "Le Labo", "fragrance_name": "Rose 31", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "floral woody", "top_notes": "cumin, rose", "heart_notes": "cedar, guaiac wood, vetiver", "base_notes": "cistus, musk, amber", "price_eur": 230, "rarity": "Common", "year": 2006, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Another 13 EDP 100ml", "house": "Le Labo", "fragrance_name": "Another 13", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "musky woody", "top_notes": "ambroxan, animal musk", "heart_notes": "jasmine, moss, ambrette", "base_notes": "white musk", "price_eur": 260, "rarity": "Common", "year": 2010, "image_url": "https://fimgs.net/mdimg/placeholder"},
    ]


def _indie_niche() -> list[dict]:
    """Indie and artisan houses."""
    return [
        {"name": "T-Rex EDP 60ml", "house": "Zoologist", "fragrance_name": "T-Rex", "concentration": "EDP", "size_ml": 60, "gender": "unisex", "fragrance_family": "smoky animalic", "top_notes": "black pepper, pink pepper, aldehydes", "heart_notes": "smoke, leather, saffron", "base_notes": "oud, labdanum, amber", "price_eur": 180, "rarity": "Uncommon", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Bat EDP 60ml", "house": "Zoologist", "fragrance_name": "Bat", "concentration": "EDP", "size_ml": 60, "gender": "unisex", "fragrance_family": "dark fruity", "top_notes": "green banana, tropical fruits", "heart_notes": "fig, cave moss", "base_notes": "guano, animalic, earth", "price_eur": 180, "rarity": "Uncommon", "year": 2015, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Bee EDP 60ml", "house": "Zoologist", "fragrance_name": "Bee", "concentration": "EDP", "size_ml": 60, "gender": "unisex", "fragrance_family": "honey floral", "top_notes": "honey, lemon", "heart_notes": "royal jelly, beeswax", "base_notes": "amber, sandalwood, musk", "price_eur": 165, "rarity": "Common", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Saint Julep EDP 50ml", "house": "Imaginary Authors", "fragrance_name": "Saint Julep", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "fresh sweet", "top_notes": "mint, tangerine", "heart_notes": "vanilla, bourbon", "base_notes": "sugar cane, musk", "price_eur": 95, "rarity": "Common", "year": 2013, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Yesterday Haze EDP 50ml", "house": "Imaginary Authors", "fragrance_name": "Yesterday Haze", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "fig green", "top_notes": "fig, pulp", "heart_notes": "ivy, meadow", "base_notes": "blonde wood, musk", "price_eur": 95, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Every Storm A Serenade EDP 50ml", "house": "Imaginary Authors", "fragrance_name": "Every Storm A Serenade", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "marine woody", "top_notes": "eucalyptus, Dutch iris", "heart_notes": "vetiver, seaweed", "base_notes": "cedar, salt water, musk", "price_eur": 95, "rarity": "Common", "year": 2012, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "L'Air du Désert Marocain EDP 50ml", "house": "Tauer Perfumes", "fragrance_name": "L'Air du Désert Marocain", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "oriental woody", "top_notes": "coriander, petitgrain", "heart_notes": "dried spices, incense", "base_notes": "ambergris, vetiver, cedar, tolu balsam", "price_eur": 140, "rarity": "Uncommon", "year": 2005, "image_url": "https://fimgs.net/mdimg/placeholder"},
    ]


def _initio_kilian() -> list[dict]:
    """Initio and Kilian fragrances."""
    return [
        {"name": "Side Effect EDP 90ml", "house": "Initio", "fragrance_name": "Side Effect", "concentration": "EDP", "size_ml": 90, "gender": "unisex", "fragrance_family": "tobacco vanilla", "top_notes": "rum, cinnamon", "heart_notes": "tobacco, vanilla", "base_notes": "musk, guaiac wood, benzoin", "price_eur": 260, "rarity": "Common", "year": 2018, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Oud for Greatness EDP 90ml", "house": "Initio", "fragrance_name": "Oud for Greatness", "concentration": "EDP", "size_ml": 90, "gender": "unisex", "fragrance_family": "oud woody", "top_notes": "oud, nutmeg", "heart_notes": "saffron, agarwood", "base_notes": "musk, patchouli, lavender", "price_eur": 280, "rarity": "Common", "year": 2018, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Atomic Rose EDP 90ml", "house": "Initio", "fragrance_name": "Atomic Rose", "concentration": "EDP", "size_ml": 90, "gender": "unisex", "fragrance_family": "floral oriental", "top_notes": "rose, saffron", "heart_notes": "oud, musk", "base_notes": "amber, benzoin", "price_eur": 260, "rarity": "Common", "year": 2018, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Angels' Share EDP 50ml", "house": "Kilian", "fragrance_name": "Angels' Share", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "boozy gourmand", "top_notes": "cognac, cinnamon", "heart_notes": "praline, tonka bean, oak", "base_notes": "sandalwood, vanilla, cedar", "price_eur": 255, "rarity": "Common", "year": 2020, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Love Don't Be Shy EDP 50ml", "house": "Kilian", "fragrance_name": "Love Don't Be Shy", "concentration": "EDP", "size_ml": 50, "gender": "feminine", "fragrance_family": "sweet floral", "top_notes": "neroli, pink pepper", "heart_notes": "orange blossom, iris", "base_notes": "marshmallow, sugar, vanilla, civet", "price_eur": 255, "rarity": "Common", "year": 2007, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Black Phantom EDP 50ml", "house": "Kilian", "fragrance_name": "Black Phantom", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "boozy woody", "top_notes": "rum, dark chocolate", "heart_notes": "coffee, vetiver, cane sugar", "base_notes": "sandalwood, ebony, almond", "price_eur": 255, "rarity": "Common", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
    ]


def _diptyque_penhaligons_malle() -> list[dict]:
    """Diptyque, Penhaligon's, Frederic Malle."""
    return [
        {"name": "Philosykos EDP 75ml", "house": "Diptyque", "fragrance_name": "Philosykos", "concentration": "EDP", "size_ml": 75, "gender": "unisex", "fragrance_family": "green fig", "top_notes": "fig leaf, green sap", "heart_notes": "fig, coconut milk", "base_notes": "cedar, white musk", "price_eur": 145, "rarity": "Common", "year": 1996, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Tam Dao EDP 75ml", "house": "Diptyque", "fragrance_name": "Tam Dao", "concentration": "EDP", "size_ml": 75, "gender": "unisex", "fragrance_family": "woody spicy", "top_notes": "Italian cypress, myrtle", "heart_notes": "sandalwood, rosewood", "base_notes": "cedar, amber, musk", "price_eur": 145, "rarity": "Common", "year": 2003, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Do Son EDP 75ml", "house": "Diptyque", "fragrance_name": "Do Son", "concentration": "EDP", "size_ml": 75, "gender": "feminine", "fragrance_family": "white floral", "top_notes": "orange leaf, pink pepper", "heart_notes": "tuberose", "base_notes": "benzoin, musk", "price_eur": 145, "rarity": "Common", "year": 2005, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Halfeti EDP 100ml", "house": "Penhaligon's", "fragrance_name": "Halfeti", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "oriental spicy", "top_notes": "grapefruit, bergamot, green cardamom", "heart_notes": "rose, jasmine, Sichuan pepper", "base_notes": "oud, leather, amber, sandalwood", "price_eur": 210, "rarity": "Common", "year": 2015, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Sartorial EDT 100ml", "house": "Penhaligon's", "fragrance_name": "Sartorial", "concentration": "EDT", "size_ml": 100, "gender": "masculine", "fragrance_family": "fougère", "top_notes": "beeswax, bergamot", "heart_notes": "lavender, metallic notes", "base_notes": "musk, oak, woods", "price_eur": 140, "rarity": "Common", "year": 2010, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Portrait of a Lady EDP 100ml", "house": "Frederic Malle", "fragrance_name": "Portrait of a Lady", "concentration": "EDP", "size_ml": 100, "gender": "feminine", "fragrance_family": "floral oriental", "top_notes": "rose, raspberry, clove", "heart_notes": "patchouli, incense, benzoin", "base_notes": "sandalwood, musk, amber", "price_eur": 300, "rarity": "Common", "year": 2010, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Musc Ravageur EDP 100ml", "house": "Frederic Malle", "fragrance_name": "Musc Ravageur", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "amber musk", "top_notes": "bergamot, lavender", "heart_notes": "musk, amber", "base_notes": "vanilla, sandalwood, guaiac wood", "price_eur": 280, "rarity": "Common", "year": 2000, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Carnal Flower EDP 100ml", "house": "Frederic Malle", "fragrance_name": "Carnal Flower", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "white floral", "top_notes": "melon, eucalyptus", "heart_notes": "tuberose", "base_notes": "musk, coconut, white floral", "price_eur": 320, "rarity": "Uncommon", "year": 2005, "image_url": "https://fimgs.net/mdimg/placeholder"},
    ]


def _montale_mancera_replica() -> list[dict]:
    """Montale, Mancera, Maison Margiela Replica."""
    return [
        {"name": "Intense Cafe EDP 100ml", "house": "Montale", "fragrance_name": "Intense Cafe", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "coffee rose", "top_notes": "coffee, rose", "heart_notes": "amber, floral notes", "base_notes": "vanilla, white musk", "price_eur": 120, "rarity": "Common", "year": 2013, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Chocolate Greedy EDP 100ml", "house": "Montale", "fragrance_name": "Chocolate Greedy", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "gourmand", "top_notes": "chocolate, coffee, cocoa", "heart_notes": "tonka bean, vanilla", "base_notes": "dried fruit, white musk", "price_eur": 115, "rarity": "Common", "year": 2006, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Roses Vanille EDP 120ml", "house": "Mancera", "fragrance_name": "Roses Vanille", "concentration": "EDP", "size_ml": 120, "gender": "feminine", "fragrance_family": "floral gourmand", "top_notes": "lemon, sweet rose", "heart_notes": "Damask rose, white peach", "base_notes": "vanilla, amber, white musk, cedar", "price_eur": 100, "rarity": "Common", "year": 2011, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Cedrat Boise EDP 120ml", "house": "Mancera", "fragrance_name": "Cedrat Boise", "concentration": "EDP", "size_ml": 120, "gender": "masculine", "fragrance_family": "citrus woody", "top_notes": "citron, bergamot, black currant", "heart_notes": "cardamom, fruity notes", "base_notes": "white musk, sandalwood, cedar, patchouli", "price_eur": 100, "rarity": "Common", "year": 2011, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "By the Fireplace EDT 100ml", "house": "Maison Margiela", "fragrance_name": "By the Fireplace", "concentration": "EDT", "size_ml": 100, "gender": "unisex", "fragrance_family": "smoky woody", "top_notes": "clove, pink pepper, orange", "heart_notes": "chestnut, guaiac wood", "base_notes": "vanilla, Peru balsam, cashmeran", "price_eur": 120, "rarity": "Common", "year": 2015, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Jazz Club EDT 100ml", "house": "Maison Margiela", "fragrance_name": "Jazz Club", "concentration": "EDT", "size_ml": 100, "gender": "masculine", "fragrance_family": "aromatic tobacco", "top_notes": "pink pepper, neroli, lemon", "heart_notes": "rum, clary sage, Java vetiver", "base_notes": "tobacco, styrax, vanilla, tonka", "price_eur": 120, "rarity": "Common", "year": 2013, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Bubble Bath EDT 100ml", "house": "Maison Margiela", "fragrance_name": "Bubble Bath", "concentration": "EDT", "size_ml": 100, "gender": "unisex", "fragrance_family": "clean musk", "top_notes": "soap, lavender", "heart_notes": "rose, coconut", "base_notes": "musk, white cedar, tonka bean", "price_eur": 120, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
    ]


def _roja_nishane_tiziana() -> list[dict]:
    """Roja Parfums, Nishane, Tiziana Terenzi."""
    return [
        {"name": "Elysium Parfum Cologne 100ml", "house": "Roja Parfums", "fragrance_name": "Elysium", "concentration": "Parfum", "size_ml": 100, "gender": "masculine", "fragrance_family": "citrus aromatic", "top_notes": "grapefruit, bergamot, lemon", "heart_notes": "jasmine, rose, lily of the valley", "base_notes": "vanilla, amber, musk, cedar, vetiver", "price_eur": 290, "rarity": "Common", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Enigma Parfum 100ml", "house": "Roja Parfums", "fragrance_name": "Enigma (Creation-E)", "concentration": "Parfum", "size_ml": 100, "gender": "masculine", "fragrance_family": "amber woody", "top_notes": "bergamot, white pepper, clary sage", "heart_notes": "jasmine, orris, rose", "base_notes": "oud, amber, vanilla, labdanum, musk", "price_eur": 600, "rarity": "Uncommon", "year": 2016, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Hacivat EDP 100ml", "house": "Nishane", "fragrance_name": "Hacivat", "concentration": "Extrait", "size_ml": 100, "gender": "unisex", "fragrance_family": "fruity woody", "top_notes": "pineapple, bergamot, grapefruit", "heart_notes": "jasmine, patchouli, birch", "base_notes": "oakmoss, musk, cedar", "price_eur": 180, "rarity": "Common", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Ani EDP 100ml", "house": "Nishane", "fragrance_name": "Ani", "concentration": "Extrait", "size_ml": 100, "gender": "unisex", "fragrance_family": "amber vanilla", "top_notes": "bergamot, cardamom, pink pepper", "heart_notes": "jasmine, rose, orris", "base_notes": "vanilla, sandalwood, tonka, benzoin", "price_eur": 185, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Kirke Extrait 100ml", "house": "Tiziana Terenzi", "fragrance_name": "Kirke", "concentration": "Extrait", "size_ml": 100, "gender": "unisex", "fragrance_family": "fruity floral", "top_notes": "peach, passion fruit, raspberry", "heart_notes": "heliotrope, lily of the valley, rose", "base_notes": "musk, vanilla, amber", "price_eur": 270, "rarity": "Common", "year": 2013, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Andromeda Extrait 100ml", "house": "Tiziana Terenzi", "fragrance_name": "Andromeda", "concentration": "Extrait", "size_ml": 100, "gender": "unisex", "fragrance_family": "green floral", "top_notes": "lavender, pink pepper", "heart_notes": "jasmine, magnolia, gardenia", "base_notes": "musk, vanilla, amber", "price_eur": 250, "rarity": "Common", "year": 2016, "image_url": "https://fimgs.net/mdimg/placeholder"},
    ]


def _clive_christian_memo() -> list[dict]:
    """Clive Christian, Memo Paris, BDK, and others."""
    return [
        {"name": "No. 1 for Men Parfum 50ml", "house": "Clive Christian", "fragrance_name": "No. 1 for Men", "concentration": "Parfum", "size_ml": 50, "gender": "masculine", "fragrance_family": "oriental woody", "top_notes": "lime, bergamot, thyme", "heart_notes": "carnation, nutmeg, jasmine", "base_notes": "sandalwood, cedar, oud, vanilla, vetiver", "price_eur": 650, "rarity": "Rare", "year": 2001, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "X for Men Parfum 50ml", "house": "Clive Christian", "fragrance_name": "X for Men", "concentration": "Parfum", "size_ml": 50, "gender": "masculine", "fragrance_family": "oriental spicy", "top_notes": "cardamom, bergamot, green apple", "heart_notes": "orris, jasmine, rose", "base_notes": "sandalwood, oud, amber, musk", "price_eur": 400, "rarity": "Uncommon", "year": 2009, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "African Leather EDP 75ml", "house": "Memo Paris", "fragrance_name": "African Leather", "concentration": "EDP", "size_ml": 75, "gender": "unisex", "fragrance_family": "leather oud", "top_notes": "bergamot, cardamom, geranium", "heart_notes": "oud, cumin, saffron", "base_notes": "leather, musk, vetiver", "price_eur": 240, "rarity": "Common", "year": 2016, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Winter Palace EDP 75ml", "house": "Memo Paris", "fragrance_name": "Winter Palace", "concentration": "EDP", "size_ml": 75, "gender": "unisex", "fragrance_family": "citrus tea", "top_notes": "mandarin, bergamot", "heart_notes": "Russian tea, jasmine", "base_notes": "amber, musk, leather", "price_eur": 220, "rarity": "Common", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Gris Charnel Extrait EDP 100ml", "house": "BDK Parfums", "fragrance_name": "Gris Charnel Extrait", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "warm spicy", "top_notes": "cardamom, fig, pink pepper", "heart_notes": "iris, vetiver, tonka", "base_notes": "sandalwood, musk", "price_eur": 195, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
    ]




def _more_niche_houses() -> list[dict]:
    """Additional niche houses — Nicolai, Atelier Cologne, Mancera, Montale, Serge Lutens, etc."""
    return [
        # Parfums de Nicolai
        {"name": "New York Intense EDP 100ml", "house": "Parfums de Nicolai", "fragrance_name": "New York Intense", "concentration": "EDP", "size_ml": 100, "gender": "masculine", "fragrance_family": "amber woody", "top_notes": "bergamot, artemisia", "heart_notes": "cinnamon, patchouli", "base_notes": "amber, vanilla, tonka bean", "price_eur": 135, "rarity": "Common", "year": 2011, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Maharani d'Or EDP 100ml", "house": "Parfums de Nicolai", "fragrance_name": "Maharani d'Or", "concentration": "EDP", "size_ml": 100, "gender": "feminine", "fragrance_family": "oriental floral", "top_notes": "bergamot, pink pepper", "heart_notes": "jasmine, tuberose, ylang-ylang", "base_notes": "sandalwood, amber, vanilla", "price_eur": 125, "rarity": "Common", "year": 2018, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Fig Tea EDT 100ml", "house": "Parfums de Nicolai", "fragrance_name": "Fig Tea", "concentration": "EDT", "size_ml": 100, "gender": "unisex", "fragrance_family": "green fresh", "top_notes": "bergamot, fig leaf", "heart_notes": "green tea, fig", "base_notes": "musk, cedar", "price_eur": 110, "rarity": "Common", "year": 2014, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Atelier Cologne
        {"name": "Cedre Atlas Cologne Absolue 100ml", "house": "Atelier Cologne", "fragrance_name": "Cedre Atlas", "concentration": "EDC", "size_ml": 100, "gender": "unisex", "fragrance_family": "woody fresh", "top_notes": "atlas cedar, lemon", "heart_notes": "papyrus, green tea", "base_notes": "vetiver, amber, musk", "price_eur": 130, "rarity": "Common", "year": 2015, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Orange Sanguine Cologne Absolue 100ml", "house": "Atelier Cologne", "fragrance_name": "Orange Sanguine", "concentration": "EDC", "size_ml": 100, "gender": "unisex", "fragrance_family": "citrus fresh", "top_notes": "blood orange, mandarin", "heart_notes": "jasmine, geranium", "base_notes": "sandalwood, tonka bean, amber", "price_eur": 130, "rarity": "Common", "year": 2011, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Vetiver Fatal Cologne Absolue 100ml", "house": "Atelier Cologne", "fragrance_name": "Vetiver Fatal", "concentration": "EDC", "size_ml": 100, "gender": "unisex", "fragrance_family": "woody vetiver", "top_notes": "bergamot, basil", "heart_notes": "vetiver, green violet leaf", "base_notes": "cedar, amber, musk", "price_eur": 130, "rarity": "Common", "year": 2014, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Maison Crivelli
        {"name": "Iris Malikhan EDP 100ml", "house": "Maison Crivelli", "fragrance_name": "Iris Malikhan", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "powdery floral", "top_notes": "grapefruit, pink pepper", "heart_notes": "iris, violet, orris", "base_notes": "leather, sandalwood, musk", "price_eur": 175, "rarity": "Common", "year": 2018, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Oud Maracuja EDP 100ml", "house": "Maison Crivelli", "fragrance_name": "Oud Maracuja", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "oud fruity", "top_notes": "passion fruit, bergamot", "heart_notes": "oud, saffron", "base_notes": "amber, vanilla, musk", "price_eur": 175, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Goldfield & Banks
        {"name": "Pacific Rock Moss EDP 100ml", "house": "Goldfield & Banks", "fragrance_name": "Pacific Rock Moss", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "aromatic green", "top_notes": "bergamot, green mandarin", "heart_notes": "rock moss, geranium", "base_notes": "amber, sandalwood, musk", "price_eur": 160, "rarity": "Common", "year": 2018, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Bohemian Lime EDP 100ml", "house": "Goldfield & Banks", "fragrance_name": "Bohemian Lime", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "citrus aromatic", "top_notes": "lime, bergamot, lemon", "heart_notes": "lemon myrtle, white flowers", "base_notes": "cedar, sandalwood, musk", "price_eur": 160, "rarity": "Common", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Mancera (more)
        {"name": "Red Tobacco EDP 120ml", "house": "Mancera", "fragrance_name": "Red Tobacco", "concentration": "EDP", "size_ml": 120, "gender": "unisex", "fragrance_family": "tobacco spicy", "top_notes": "saffron, cinnamon", "heart_notes": "tobacco, oud, patchouli", "base_notes": "vanilla, white musk, amber, sandalwood", "price_eur": 115, "rarity": "Common", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Lemon Line EDP 120ml", "house": "Mancera", "fragrance_name": "Lemon Line", "concentration": "EDP", "size_ml": 120, "gender": "unisex", "fragrance_family": "citrus fresh", "top_notes": "lemon, lime, bergamot", "heart_notes": "ginger, white flowers", "base_notes": "musk, amber, vanilla", "price_eur": 95, "rarity": "Common", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Instant Crush EDP 120ml", "house": "Mancera", "fragrance_name": "Instant Crush", "concentration": "EDP", "size_ml": 120, "gender": "unisex", "fragrance_family": "amber vanilla", "top_notes": "bergamot, pink pepper", "heart_notes": "rose, jasmine, oud", "base_notes": "vanilla, amber, sandalwood, musk", "price_eur": 110, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Aoud Lemon Mint EDP 120ml", "house": "Mancera", "fragrance_name": "Aoud Lemon Mint", "concentration": "EDP", "size_ml": 120, "gender": "unisex", "fragrance_family": "citrus oud", "top_notes": "lemon, mint, bergamot", "heart_notes": "oud, saffron", "base_notes": "amber, musk, sandalwood", "price_eur": 100, "rarity": "Common", "year": 2014, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Wild Leather EDP 120ml", "house": "Mancera", "fragrance_name": "Wild Leather", "concentration": "EDP", "size_ml": 120, "gender": "unisex", "fragrance_family": "leather aromatic", "top_notes": "bergamot, grapefruit, pink pepper", "heart_notes": "leather, jasmine, heliotrope", "base_notes": "vanilla, sandalwood, musk, amber", "price_eur": 105, "rarity": "Common", "year": 2018, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Montale (more)
        {"name": "Aoud Forest EDP 100ml", "house": "Montale", "fragrance_name": "Aoud Forest", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "woody oud", "top_notes": "oud, ginger", "heart_notes": "pine, cypress", "base_notes": "musk, amber, guaiac wood", "price_eur": 120, "rarity": "Common", "year": 2011, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Black Aoud EDP 100ml", "house": "Montale", "fragrance_name": "Black Aoud", "concentration": "EDP", "size_ml": 100, "gender": "masculine", "fragrance_family": "oud rose", "top_notes": "agarwood, rose", "heart_notes": "oud, patchouli", "base_notes": "musk, amber, sandalwood", "price_eur": 125, "rarity": "Common", "year": 2006, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Arabians EDP 100ml", "house": "Montale", "fragrance_name": "Arabians", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "oriental spicy", "top_notes": "saffron, cumin", "heart_notes": "oud, amber, incense", "base_notes": "sandalwood, musk, vanilla", "price_eur": 125, "rarity": "Common", "year": 2010, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Roses Musk EDP 100ml", "house": "Montale", "fragrance_name": "Roses Musk", "concentration": "EDP", "size_ml": 100, "gender": "feminine", "fragrance_family": "floral musk", "top_notes": "rose", "heart_notes": "Bulgarian rose, Turkish rose", "base_notes": "white musk, amber", "price_eur": 115, "rarity": "Common", "year": 2009, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Oud Edition EDP 100ml", "house": "Montale", "fragrance_name": "Oud Edition", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "oud leather", "top_notes": "oud, saffron", "heart_notes": "leather, patchouli", "base_notes": "amber, musk, sandalwood", "price_eur": 130, "rarity": "Uncommon", "year": 2011, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Starry Nights EDP 100ml", "house": "Montale", "fragrance_name": "Starry Nights", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "amber oriental", "top_notes": "bergamot, saffron", "heart_notes": "oud, orris, incense", "base_notes": "vanilla, amber, musk, sandalwood", "price_eur": 135, "rarity": "Common", "year": 2015, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Serge Lutens
        {"name": "Chergui EDP 50ml", "house": "Serge Lutens", "fragrance_name": "Chergui", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "amber tobacco", "top_notes": "honey, hay", "heart_notes": "tobacco, incense, iris", "base_notes": "amber, musk, sandalwood, vanilla", "price_eur": 140, "rarity": "Common", "year": 2005, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Ambre Sultan EDP 50ml", "house": "Serge Lutens", "fragrance_name": "Ambre Sultan", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "amber resinous", "top_notes": "coriander, bay leaf, oregano", "heart_notes": "amber, benzoin, labdanum", "base_notes": "sandalwood, vanilla, patchouli", "price_eur": 140, "rarity": "Common", "year": 2000, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "La Fille de Berlin EDP 50ml", "house": "Serge Lutens", "fragrance_name": "La Fille de Berlin", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "floral woody", "top_notes": "rose, fruity notes", "heart_notes": "Damask rose, geranium", "base_notes": "cedar, musk, incense, wax", "price_eur": 140, "rarity": "Common", "year": 2013, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Jeux de Peau EDP 50ml", "house": "Serge Lutens", "fragrance_name": "Jeux de Peau", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "gourmand warm", "top_notes": "bread crust, wheat", "heart_notes": "apricot, licorice", "base_notes": "sandalwood, musk, vanilla", "price_eur": 140, "rarity": "Uncommon", "year": 2003, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Datura Noir EDP 50ml", "house": "Serge Lutens", "fragrance_name": "Datura Noir", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "floral tropical", "top_notes": "mandarin, lemon", "heart_notes": "datura, tuberose, coconut", "base_notes": "almond, tonka bean, vanilla, musk", "price_eur": 140, "rarity": "Common", "year": 2001, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Comme des Garçons
        {"name": "Wonderwood EDP 100ml", "house": "Comme des Garçons", "fragrance_name": "Wonderwood", "concentration": "EDP", "size_ml": 100, "gender": "masculine", "fragrance_family": "woody", "top_notes": "Moroccan cedar", "heart_notes": "Georgian oak, cashmir wood", "base_notes": "sandalwood, gaiac wood, musk", "price_eur": 110, "rarity": "Common", "year": 2010, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Blackpepper EDP 100ml", "house": "Comme des Garçons", "fragrance_name": "Blackpepper", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "spicy woody", "top_notes": "black pepper, pink pepper", "heart_notes": "cedar, sandalwood", "base_notes": "vetiver, musk, patchouli", "price_eur": 115, "rarity": "Common", "year": 2016, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "CDG 2 EDP 100ml", "house": "Comme des Garçons", "fragrance_name": "CDG 2", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "aldehyde floral", "top_notes": "aldehydes, ink", "heart_notes": "iris, magnolia", "base_notes": "vetiver, musk, incense", "price_eur": 105, "rarity": "Common", "year": 2002, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # D.S. & Durga
        {"name": "Debaser EDP 50ml", "house": "D.S. & Durga", "fragrance_name": "Debaser", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "green fig", "top_notes": "fig, bergamot", "heart_notes": "coconut, iris", "base_notes": "blonde wood, musk", "price_eur": 175, "rarity": "Common", "year": 2015, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "I Don't Know What EDP 50ml", "house": "D.S. & Durga", "fragrance_name": "I Don't Know What", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "amber musk", "top_notes": "black pepper, bergamot", "heart_notes": "hemp, wood resin", "base_notes": "amber, musk, hemp", "price_eur": 185, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Bowmakers EDP 50ml", "house": "D.S. & Durga", "fragrance_name": "Bowmakers", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "woody resinous", "top_notes": "violin varnish, maple syrup", "heart_notes": "Mahogany, wood resin", "base_notes": "amber, musk", "price_eur": 175, "rarity": "Common", "year": 2015, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Histoires de Parfums
        {"name": "1725 EDP 120ml", "house": "Histoires de Parfums", "fragrance_name": "1725", "concentration": "EDP", "size_ml": 120, "gender": "masculine", "fragrance_family": "amber vanilla", "top_notes": "lemon, cinnamon", "heart_notes": "jasmine, ylang-ylang", "base_notes": "vanilla, sandalwood, amber, tonka", "price_eur": 170, "rarity": "Common", "year": 2003, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "1899 EDP 120ml", "house": "Histoires de Parfums", "fragrance_name": "1899", "concentration": "EDP", "size_ml": 120, "gender": "masculine", "fragrance_family": "oriental woody", "top_notes": "myrtle, pink pepper", "heart_notes": "cedar, patchouli", "base_notes": "leather, oud, musk", "price_eur": 170, "rarity": "Common", "year": 2004, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "This Is Not A Blue Bottle 1.1 EDP 120ml", "house": "Histoires de Parfums", "fragrance_name": "This Is Not A Blue Bottle 1.1", "concentration": "EDP", "size_ml": 120, "gender": "unisex", "fragrance_family": "floral green", "top_notes": "neroli, petitgrain", "heart_notes": "jasmine, orange blossom", "base_notes": "musk, amber", "price_eur": 155, "rarity": "Common", "year": 2016, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Aesop
        {"name": "Hwyl EDP 50ml", "house": "Aesop", "fragrance_name": "Hwyl", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "woody smoky", "top_notes": "thyme, elemi", "heart_notes": "cypress, guaiac wood", "base_notes": "vetiver, frankincense, cedar", "price_eur": 150, "rarity": "Common", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Tacit EDP 50ml", "house": "Aesop", "fragrance_name": "Tacit", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "green herbal", "top_notes": "yuzu, basil grand vert", "heart_notes": "clary sage, jasmine sambac", "base_notes": "vetiver, cedar", "price_eur": 120, "rarity": "Common", "year": 2015, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Marrakech Intense EDT 50ml", "house": "Aesop", "fragrance_name": "Marrakech Intense", "concentration": "EDT", "size_ml": 50, "gender": "unisex", "fragrance_family": "spicy floral", "top_notes": "clove, cardamom, neroli", "heart_notes": "rose, jasmine", "base_notes": "sandalwood, cedar, patchouli", "price_eur": 110, "rarity": "Common", "year": 2014, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Juliette Has A Gun
        {"name": "Not a Perfume EDP 100ml", "house": "Juliette Has A Gun", "fragrance_name": "Not a Perfume", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "clean musk", "top_notes": "ambroxan", "heart_notes": "ambroxan", "base_notes": "ambroxan, musk", "price_eur": 115, "rarity": "Common", "year": 2010, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Lady Vengeance EDP 100ml", "house": "Juliette Has A Gun", "fragrance_name": "Lady Vengeance", "concentration": "EDP", "size_ml": 100, "gender": "feminine", "fragrance_family": "floral oriental", "top_notes": "Bulgarian rose, bergamot", "heart_notes": "rose, patchouli", "base_notes": "vanilla, musk", "price_eur": 120, "rarity": "Common", "year": 2006, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Gentlewoman EDP 100ml", "house": "Juliette Has A Gun", "fragrance_name": "Gentlewoman", "concentration": "EDP", "size_ml": 100, "gender": "feminine", "fragrance_family": "floral woody", "top_notes": "neroli, orange blossom", "heart_notes": "tuberose, white flowers", "base_notes": "musk, amber, cedar", "price_eur": 115, "rarity": "Common", "year": 2014, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Ormonde Jayne
        {"name": "Ormonde Man EDP 120ml", "house": "Ormonde Jayne", "fragrance_name": "Ormonde Man", "concentration": "EDP", "size_ml": 120, "gender": "masculine", "fragrance_family": "woody green", "top_notes": "juniper berry, coriander, bergamot", "heart_notes": "hemlock, oud, cedar", "base_notes": "vetiver, amber, musk", "price_eur": 165, "rarity": "Common", "year": 2003, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Tolu EDP 120ml", "house": "Ormonde Jayne", "fragrance_name": "Tolu", "concentration": "EDP", "size_ml": 120, "gender": "unisex", "fragrance_family": "oriental balsamic", "top_notes": "bergamot, pink pepper", "heart_notes": "tolu balsam, jasmine, rose", "base_notes": "amber, benzoin, vanilla, musk", "price_eur": 165, "rarity": "Common", "year": 2002, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Montabaco EDP 120ml", "house": "Ormonde Jayne", "fragrance_name": "Montabaco", "concentration": "EDP", "size_ml": 120, "gender": "unisex", "fragrance_family": "tobacco oriental", "top_notes": "bergamot, rum, cinnamon", "heart_notes": "tobacco, ylang-ylang, jasmine", "base_notes": "amber, oud, vanilla, musk", "price_eur": 175, "rarity": "Common", "year": 2016, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Vilhelm Parfumerie
        {"name": "Dear Polly EDP 100ml", "house": "Vilhelm Parfumerie", "fragrance_name": "Dear Polly", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "fruity tea", "top_notes": "apple, green notes", "heart_notes": "black tea, wild strawberry", "base_notes": "vanilla, musk, amber", "price_eur": 175, "rarity": "Common", "year": 2015, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Mango Skin EDP 100ml", "house": "Vilhelm Parfumerie", "fragrance_name": "Mango Skin", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "fruity floral", "top_notes": "mango, bergamot", "heart_notes": "neroli, jasmine, ylang-ylang", "base_notes": "sandalwood, musk, amber", "price_eur": 175, "rarity": "Common", "year": 2016, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Morning Chess EDP 100ml", "house": "Vilhelm Parfumerie", "fragrance_name": "Morning Chess", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "woody amber", "top_notes": "black pepper, strawberry", "heart_notes": "orris, white flowers", "base_notes": "sandalwood, musk, amber", "price_eur": 175, "rarity": "Common", "year": 2015, "image_url": "https://fimgs.net/mdimg/placeholder"},
    ]




def _additional_niche() -> list[dict]:
    """Additional niche houses and popular fragrances for catalog depth."""
    return [
        # Xerjoff (more)
        {"name": "Nio EDP 100ml", "house": "Xerjoff", "fragrance_name": "Nio", "concentration": "EDP", "size_ml": 100, "gender": "masculine", "fragrance_family": "citrus aromatic", "top_notes": "lemon, bergamot, grapefruit", "heart_notes": "lavender, geranium", "base_notes": "musk, cedar, amber", "price_eur": 210, "rarity": "Common", "year": 2011, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Mefisto EDP 100ml", "house": "Xerjoff", "fragrance_name": "Mefisto", "concentration": "EDP", "size_ml": 100, "gender": "masculine", "fragrance_family": "citrus fresh", "top_notes": "bergamot, ginger, elemi", "heart_notes": "violet, lavender", "base_notes": "musk, cedar, sandalwood", "price_eur": 210, "rarity": "Common", "year": 2009, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Richwood EDP 100ml", "house": "Xerjoff", "fragrance_name": "Richwood", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "woody leather", "top_notes": "bergamot, cardamom", "heart_notes": "oud, leather, saffron", "base_notes": "amber, sandalwood, musk", "price_eur": 350, "rarity": "Uncommon", "year": 2010, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Opera EDP 100ml", "house": "Xerjoff", "fragrance_name": "Opera", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "floral fruity", "top_notes": "mandarin, bergamot, black currant", "heart_notes": "rose, jasmine, violet", "base_notes": "musk, amber, patchouli", "price_eur": 240, "rarity": "Common", "year": 2012, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Parfums de Marly (more)
        {"name": "Carlisle EDP 125ml", "house": "Parfums de Marly", "fragrance_name": "Carlisle", "concentration": "EDP", "size_ml": 125, "gender": "unisex", "fragrance_family": "amber woody", "top_notes": "green apple, nutmeg, bergamot", "heart_notes": "rose, patchouli, tonka", "base_notes": "oud, vanilla, musk", "price_eur": 285, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Haltane EDP 125ml", "house": "Parfums de Marly", "fragrance_name": "Haltane", "concentration": "EDP", "size_ml": 125, "gender": "masculine", "fragrance_family": "oriental spicy", "top_notes": "pink pepper, lavender, bergamot", "heart_notes": "iris, oud", "base_notes": "vanilla, musk, amber, benzoin", "price_eur": 285, "rarity": "Common", "year": 2021, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Oajan EDP 125ml", "house": "Parfums de Marly", "fragrance_name": "Oajan", "concentration": "EDP", "size_ml": 125, "gender": "unisex", "fragrance_family": "oriental spicy", "top_notes": "cinnamon, clove, ginger", "heart_notes": "honey, benzoin, amber", "base_notes": "agarwood, vanilla, sandalwood, tonka", "price_eur": 265, "rarity": "Common", "year": 2016, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Kalan EDP 125ml", "house": "Parfums de Marly", "fragrance_name": "Kalan", "concentration": "EDP", "size_ml": 125, "gender": "masculine", "fragrance_family": "citrus spicy", "top_notes": "orange, grapefruit, bergamot", "heart_notes": "pink pepper, rose, jasmine", "base_notes": "vanilla, musk, tonka", "price_eur": 240, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Kilian (more)
        {"name": "Straight to Heaven EDP 50ml", "house": "Kilian", "fragrance_name": "Straight to Heaven", "concentration": "EDP", "size_ml": 50, "gender": "masculine", "fragrance_family": "woody amber", "top_notes": "rum, cinnamon", "heart_notes": "cedar, vetiver, patchouli", "base_notes": "dry wood, tonka bean, musk", "price_eur": 255, "rarity": "Common", "year": 2007, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Intoxicated EDP 50ml", "house": "Kilian", "fragrance_name": "Intoxicated", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "spicy oriental", "top_notes": "Turkish coffee, cardamom", "heart_notes": "cinnamon, nutmeg, pepper", "base_notes": "sandalwood, vanilla, musk", "price_eur": 255, "rarity": "Common", "year": 2014, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Good Girl Gone Bad EDP 50ml", "house": "Kilian", "fragrance_name": "Good Girl Gone Bad", "concentration": "EDP", "size_ml": 50, "gender": "feminine", "fragrance_family": "floral fruity", "top_notes": "osmanthus, jasmine", "heart_notes": "May rose, tuberose, narcissus", "base_notes": "amber, cedar, vetiver, musk", "price_eur": 255, "rarity": "Common", "year": 2012, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Rolling in Love EDP 50ml", "house": "Kilian", "fragrance_name": "Rolling in Love", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "floral musk", "top_notes": "almond, iris", "heart_notes": "Turkish rose, amber", "base_notes": "musk, sandalwood, tonka", "price_eur": 245, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Initio (more)
        {"name": "Musk Therapy EDP 90ml", "house": "Initio", "fragrance_name": "Musk Therapy", "concentration": "EDP", "size_ml": 90, "gender": "unisex", "fragrance_family": "musk amber", "top_notes": "white musk, bergamot", "heart_notes": "violet, iris", "base_notes": "amber, sandalwood, cashmeran", "price_eur": 250, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Rehab EDP 90ml", "house": "Initio", "fragrance_name": "Rehab", "concentration": "EDP", "size_ml": 90, "gender": "unisex", "fragrance_family": "aromatic lavender", "top_notes": "lavender, lemon, bergamot", "heart_notes": "geranium, cinnamon, cardamom", "base_notes": "cashmeran, vanilla, musk", "price_eur": 260, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Nishane (more)
        {"name": "Hundred Silent Ways Extrait 100ml", "house": "Nishane", "fragrance_name": "Hundred Silent Ways", "concentration": "Extrait", "size_ml": 100, "gender": "unisex", "fragrance_family": "powdery floral", "top_notes": "pear, mandarin, bergamot", "heart_notes": "rose, violet, heliotrope", "base_notes": "musk, amber, sandalwood, tonka", "price_eur": 185, "rarity": "Common", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Fan Your Flames Extrait 100ml", "house": "Nishane", "fragrance_name": "Fan Your Flames", "concentration": "Extrait", "size_ml": 100, "gender": "unisex", "fragrance_family": "amber oriental", "top_notes": "saffron, cardamom, pink pepper", "heart_notes": "labdanum, tobacco, oud", "base_notes": "vanilla, amber, benzoin, musk", "price_eur": 195, "rarity": "Common", "year": 2020, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Wulong Cha Extrait 100ml", "house": "Nishane", "fragrance_name": "Wulong Cha", "concentration": "Extrait", "size_ml": 100, "gender": "unisex", "fragrance_family": "tea citrus", "top_notes": "grapefruit, mandarin", "heart_notes": "oolong tea, jasmine", "base_notes": "musk, amber, cedar", "price_eur": 170, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Byredo (more)
        {"name": "Bibliothèque EDP 100ml", "house": "Byredo", "fragrance_name": "Bibliothèque", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "woody aromatic", "top_notes": "peach, plum", "heart_notes": "violet, peony, leather", "base_notes": "patchouli, vanilla, musk", "price_eur": 195, "rarity": "Common", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Blanche EDP 100ml", "house": "Byredo", "fragrance_name": "Blanche", "concentration": "EDP", "size_ml": 100, "gender": "feminine", "fragrance_family": "white floral", "top_notes": "white rose, pink pepper", "heart_notes": "peony, violet, neroli", "base_notes": "sandalwood, musk, blonde wood", "price_eur": 190, "rarity": "Common", "year": 2009, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Oud Immortel EDP 100ml", "house": "Byredo", "fragrance_name": "Oud Immortel", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "woody oud", "top_notes": "incense, papyrus", "heart_notes": "limoncello, patchouli", "base_notes": "oud, Brazilian rosewood, moss", "price_eur": 210, "rarity": "Common", "year": 2012, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Super Cedar EDP 100ml", "house": "Byredo", "fragrance_name": "Super Cedar", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "woody", "top_notes": "Virginian cedar, rose", "heart_notes": "vetiver, musk", "base_notes": "cedar wood, cashmeran", "price_eur": 190, "rarity": "Common", "year": 2016, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Le Labo (more)
        {"name": "Thé Noir 29 EDP 100ml", "house": "Le Labo", "fragrance_name": "Thé Noir 29", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "tea smoky", "top_notes": "bergamot, bay leaf", "heart_notes": "black tea, fig, cedar", "base_notes": "vetiver, musk, amber", "price_eur": 230, "rarity": "Common", "year": 2015, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Bergamote 22 EDP 100ml", "house": "Le Labo", "fragrance_name": "Bergamote 22", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "citrus aromatic", "top_notes": "bergamot, grapefruit, petitgrain", "heart_notes": "amber, vetiver", "base_notes": "cedar, musk, vanilla", "price_eur": 230, "rarity": "Common", "year": 2006, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Tonka 25 EDP 100ml", "house": "Le Labo", "fragrance_name": "Tonka 25", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "amber gourmand", "top_notes": "cedar, musk", "heart_notes": "tonka bean, benzoin", "base_notes": "amber, vanilla, styrax", "price_eur": 280, "rarity": "Common", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Frederic Malle (more)
        {"name": "The Night EDP 100ml", "house": "Frederic Malle", "fragrance_name": "The Night", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "oud rose", "top_notes": "saffron, Turkish rose", "heart_notes": "oud, incense", "base_notes": "amber, musk, sandalwood", "price_eur": 450, "rarity": "Uncommon", "year": 2016, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "French Lover EDP 100ml", "house": "Frederic Malle", "fragrance_name": "French Lover", "concentration": "EDP", "size_ml": 100, "gender": "masculine", "fragrance_family": "woody chypre", "top_notes": "galbanum, cardamom, angelica", "heart_notes": "iris, olibanum", "base_notes": "vetiver, oakmoss, white musk", "price_eur": 280, "rarity": "Common", "year": 2007, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Superstitious EDP 100ml", "house": "Frederic Malle", "fragrance_name": "Superstitious", "concentration": "EDP", "size_ml": 100, "gender": "feminine", "fragrance_family": "floral aldehyde", "top_notes": "rose, Turkish rose", "heart_notes": "ylang-ylang, jasmine, tuberose", "base_notes": "musk, amber, patchouli, vetiver", "price_eur": 300, "rarity": "Common", "year": 2015, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Roja Parfums (more)
        {"name": "Aoud Parfum 100ml", "house": "Roja Parfums", "fragrance_name": "Aoud", "concentration": "Parfum", "size_ml": 100, "gender": "unisex", "fragrance_family": "oud amber", "top_notes": "bergamot, saffron, lemon", "heart_notes": "oud, rose, jasmine", "base_notes": "musk, amber, sandalwood, cedar", "price_eur": 750, "rarity": "Uncommon", "year": 2009, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Diaghilev Parfum 100ml", "house": "Roja Parfums", "fragrance_name": "Diaghilev", "concentration": "Parfum", "size_ml": 100, "gender": "unisex", "fragrance_family": "chypre floral", "top_notes": "bergamot, tarragon, aldehydes", "heart_notes": "rose, jasmine, orris, ylang-ylang", "base_notes": "oakmoss, vetiver, amber, musk", "price_eur": 850, "rarity": "Rare", "year": 2011, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Scandal Parfum 100ml", "house": "Roja Parfums", "fragrance_name": "Scandal", "concentration": "Parfum", "size_ml": 100, "gender": "feminine", "fragrance_family": "oriental tuberose", "top_notes": "bergamot, orange blossom", "heart_notes": "tuberose, jasmine, rose", "base_notes": "amber, musk, patchouli, vanilla", "price_eur": 600, "rarity": "Uncommon", "year": 2008, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Tiziana Terenzi (more)
        {"name": "Foconero Extrait 100ml", "house": "Tiziana Terenzi", "fragrance_name": "Foconero", "concentration": "Extrait", "size_ml": 100, "gender": "unisex", "fragrance_family": "smoky woody", "top_notes": "citrus, pink pepper", "heart_notes": "birch, cedarwood", "base_notes": "leather, oud, musk, amber", "price_eur": 265, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Saiph Extrait 100ml", "house": "Tiziana Terenzi", "fragrance_name": "Saiph", "concentration": "Extrait", "size_ml": 100, "gender": "unisex", "fragrance_family": "amber spicy", "top_notes": "saffron, black pepper", "heart_notes": "Turkish rose, cinnamon", "base_notes": "amber, vanilla, oud, musk", "price_eur": 275, "rarity": "Common", "year": 2016, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Orion Extrait 100ml", "house": "Tiziana Terenzi", "fragrance_name": "Orion", "concentration": "Extrait", "size_ml": 100, "gender": "unisex", "fragrance_family": "amber vanilla", "top_notes": "mango, papaya", "heart_notes": "heliotrope, iris, jasmine", "base_notes": "vanilla, amber, musk, sandalwood", "price_eur": 260, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Memo Paris (more)
        {"name": "Irish Leather EDP 75ml", "house": "Memo Paris", "fragrance_name": "Irish Leather", "concentration": "EDP", "size_ml": 75, "gender": "unisex", "fragrance_family": "leather green", "top_notes": "juniper, elemi, galbanum", "heart_notes": "leather, clove", "base_notes": "cedar, amber, musk, moss", "price_eur": 240, "rarity": "Common", "year": 2013, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "French Leather EDP 75ml", "house": "Memo Paris", "fragrance_name": "French Leather", "concentration": "EDP", "size_ml": 75, "gender": "unisex", "fragrance_family": "leather woody", "top_notes": "bergamot, lavender, thyme", "heart_notes": "leather, styrax, iris", "base_notes": "amber, vanilla, musk", "price_eur": 240, "rarity": "Common", "year": 2014, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Marfa EDP 75ml", "house": "Memo Paris", "fragrance_name": "Marfa", "concentration": "EDP", "size_ml": 75, "gender": "unisex", "fragrance_family": "floral woody", "top_notes": "freesia, cassis", "heart_notes": "Egyptian jasmine, orange blossom", "base_notes": "cedar, sandalwood, musk", "price_eur": 230, "rarity": "Common", "year": 2012, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Clive Christian (more)
        {"name": "L for Men Parfum 50ml", "house": "Clive Christian", "fragrance_name": "L for Men", "concentration": "Parfum", "size_ml": 50, "gender": "masculine", "fragrance_family": "woody aromatic", "top_notes": "bergamot, black pepper", "heart_notes": "orris, leather, labdanum", "base_notes": "cedar, vetiver, musk", "price_eur": 450, "rarity": "Uncommon", "year": 2012, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "V for Women Parfum 50ml", "house": "Clive Christian", "fragrance_name": "V for Women", "concentration": "Parfum", "size_ml": 50, "gender": "feminine", "fragrance_family": "oriental floral", "top_notes": "bergamot, plum", "heart_notes": "orris, rose, jasmine", "base_notes": "amber, sandalwood, vanilla, musk", "price_eur": 450, "rarity": "Uncommon", "year": 2015, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Diptyque (more)
        {"name": "Eau Duelle EDP 75ml", "house": "Diptyque", "fragrance_name": "Eau Duelle", "concentration": "EDP", "size_ml": 75, "gender": "unisex", "fragrance_family": "amber vanilla", "top_notes": "pink pepper, cardamom, elemi", "heart_notes": "frankincense, juniper", "base_notes": "vanilla, benzoin, calamus", "price_eur": 145, "rarity": "Common", "year": 2010, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Orphéon EDP 75ml", "house": "Diptyque", "fragrance_name": "Orphéon", "concentration": "EDP", "size_ml": 75, "gender": "unisex", "fragrance_family": "floral woody", "top_notes": "juniper berry", "heart_notes": "jasmine, tonka bean", "base_notes": "cedar, patchouli", "price_eur": 155, "rarity": "Common", "year": 2021, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Fleur de Peau EDP 75ml", "house": "Diptyque", "fragrance_name": "Fleur de Peau", "concentration": "EDP", "size_ml": 75, "gender": "unisex", "fragrance_family": "musk floral", "top_notes": "iris, pink pepper", "heart_notes": "musk, ambrette", "base_notes": "musks, ambroxan", "price_eur": 155, "rarity": "Common", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Penhaligon's (more)
        {"name": "Lothair EDT 100ml", "house": "Penhaligon's", "fragrance_name": "Lothair", "concentration": "EDT", "size_ml": 100, "gender": "masculine", "fragrance_family": "citrus tea", "top_notes": "bergamot, lemon, black tea", "heart_notes": "lavender, orris", "base_notes": "benzoin, musk, cedar", "price_eur": 155, "rarity": "Common", "year": 2016, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Endymion EDC 100ml", "house": "Penhaligon's", "fragrance_name": "Endymion", "concentration": "EDC", "size_ml": 100, "gender": "masculine", "fragrance_family": "aromatic spicy", "top_notes": "sage, coffee, pepper", "heart_notes": "lavender, geranium", "base_notes": "suede, musk, incense", "price_eur": 165, "rarity": "Common", "year": 2008, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "The Tragedy of Lord George EDP 75ml", "house": "Penhaligon's", "fragrance_name": "The Tragedy of Lord George", "concentration": "EDP", "size_ml": 75, "gender": "masculine", "fragrance_family": "oriental brandy", "top_notes": "brandy, lavender", "heart_notes": "Tonkin musk, orris, jasmine", "base_notes": "myrrh, amber, vanilla, oud", "price_eur": 200, "rarity": "Common", "year": 2016, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # BDK Parfums (more)
        {"name": "Rouge Smoking EDP 100ml", "house": "BDK Parfums", "fragrance_name": "Rouge Smoking", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "fruity amber", "top_notes": "raspberry, saffron, bergamot", "heart_notes": "iris, rose, oud", "base_notes": "amber, vanilla, musk, cedar", "price_eur": 195, "rarity": "Common", "year": 2018, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Sel d'Argent EDP 100ml", "house": "BDK Parfums", "fragrance_name": "Sel d'Argent", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "amber marine", "top_notes": "sea salt, ambergris, lemon", "heart_notes": "iris, violet, cacao", "base_notes": "sandalwood, musk, amber", "price_eur": 195, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Zoologist (more)
        {"name": "Elephant EDP 60ml", "house": "Zoologist", "fragrance_name": "Elephant", "concentration": "EDP", "size_ml": 60, "gender": "unisex", "fragrance_family": "earthy green", "top_notes": "green leaf, cardamom, pepper", "heart_notes": "cacao, coffee, frangipani", "base_notes": "vetiver, patchouli, earth, hay", "price_eur": 165, "rarity": "Uncommon", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Macaque EDP 60ml", "house": "Zoologist", "fragrance_name": "Macaque", "concentration": "EDP", "size_ml": 60, "gender": "unisex", "fragrance_family": "fruity tropical", "top_notes": "yuzu, mandarin, ginger", "heart_notes": "peach, sake, jasmine", "base_notes": "hinoki, sandalwood, musk, amber", "price_eur": 180, "rarity": "Uncommon", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Civet EDP 60ml", "house": "Zoologist", "fragrance_name": "Civet", "concentration": "EDP", "size_ml": 60, "gender": "unisex", "fragrance_family": "animalic oriental", "top_notes": "bergamot, rose, geranium", "heart_notes": "oud, civet, labdanum", "base_notes": "amber, musk, castoreum, vanilla", "price_eur": 180, "rarity": "Uncommon", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Masque Milano
        {"name": "Tango Nero EDP 100ml", "house": "Masque Milano", "fragrance_name": "Tango Nero", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "leather aromatic", "top_notes": "bergamot, pink pepper, mate tea", "heart_notes": "leather, iris, violet", "base_notes": "vetiver, amber, musk", "price_eur": 160, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Russian Tea EDP 100ml", "house": "Masque Milano", "fragrance_name": "Russian Tea", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "tea smoky", "top_notes": "bergamot, lapsang souchong", "heart_notes": "osmanthus, cinnamon", "base_notes": "leather, amber, musk, birch", "price_eur": 160, "rarity": "Common", "year": 2016, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Jul et Mad
        {"name": "Nin-Shar Extrait 50ml", "house": "Jul et Mad", "fragrance_name": "Nin-Shar", "concentration": "Extrait", "size_ml": 50, "gender": "unisex", "fragrance_family": "floral oriental", "top_notes": "neroli, grapefruit", "heart_notes": "tuberose, jasmine", "base_notes": "amber, sandalwood, musk, vanilla", "price_eur": 250, "rarity": "Uncommon", "year": 2014, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "The Cobra & The Canary Extrait 50ml", "house": "Jul et Mad", "fragrance_name": "The Cobra & The Canary", "concentration": "Extrait", "size_ml": 50, "gender": "unisex", "fragrance_family": "chypre woody", "top_notes": "bergamot, juniper", "heart_notes": "labdanum, osmanthus", "base_notes": "oakmoss, patchouli, amber, musk", "price_eur": 260, "rarity": "Uncommon", "year": 2014, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Papillon
        {"name": "Artisan of Dreams Parfum 50ml", "house": "Papillon Artisan Perfumes", "fragrance_name": "Artisan of Dreams", "concentration": "Parfum", "size_ml": 50, "gender": "unisex", "fragrance_family": "amber vanilla", "top_notes": "bergamot, saffron", "heart_notes": "orris, jasmine, benzoin", "base_notes": "vanilla, amber, sandalwood, musk", "price_eur": 175, "rarity": "Common", "year": 2020, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Anubis Parfum 50ml", "house": "Papillon Artisan Perfumes", "fragrance_name": "Anubis", "concentration": "Parfum", "size_ml": 50, "gender": "unisex", "fragrance_family": "oriental resinous", "top_notes": "frankincense, labdanum", "heart_notes": "myrrh, rose, oud", "base_notes": "amber, musk, sandalwood, civet", "price_eur": 175, "rarity": "Uncommon", "year": 2015, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Maison Margiela (more)
        {"name": "Coffee Break EDT 100ml", "house": "Maison Margiela", "fragrance_name": "Coffee Break", "concentration": "EDT", "size_ml": 100, "gender": "unisex", "fragrance_family": "gourmand coffee", "top_notes": "pepper, lavender", "heart_notes": "coffee, milk mousse", "base_notes": "cedar, vanilla, tonka bean", "price_eur": 120, "rarity": "Common", "year": 2018, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Whispers in the Library EDT 100ml", "house": "Maison Margiela", "fragrance_name": "Whispers in the Library", "concentration": "EDT", "size_ml": 100, "gender": "unisex", "fragrance_family": "woody vanilla", "top_notes": "pepper", "heart_notes": "cedar, vanilla", "base_notes": "benzoin, tonka, musk", "price_eur": 120, "rarity": "Common", "year": 2015, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Autumn Vibes EDT 100ml", "house": "Maison Margiela", "fragrance_name": "Autumn Vibes", "concentration": "EDT", "size_ml": 100, "gender": "unisex", "fragrance_family": "woody spicy", "top_notes": "nutmeg, cardamom, pink pepper", "heart_notes": "cedar, styrax", "base_notes": "cashmeran, amber, musk", "price_eur": 120, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Tauer (more)
        {"name": "Au Cœur du Désert Extrait 50ml", "house": "Tauer Perfumes", "fragrance_name": "Au Cœur du Désert", "concentration": "Extrait", "size_ml": 50, "gender": "unisex", "fragrance_family": "oriental woody", "top_notes": "spices, herbs", "heart_notes": "dried fruits, incense, amber", "base_notes": "tolu balsam, oud, vetiver", "price_eur": 200, "rarity": "Uncommon", "year": 2012, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Lonestar Memories EDP 50ml", "house": "Tauer Perfumes", "fragrance_name": "Lonestar Memories", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "smoky leather", "top_notes": "birch tar, bergamot", "heart_notes": "leather, labdanum", "base_notes": "amber, vetiver, musk", "price_eur": 140, "rarity": "Common", "year": 2007, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Imaginary Authors (more)
        {"name": "The Cobra & The Canary EDP 50ml", "house": "Imaginary Authors", "fragrance_name": "Memoirs of a Trespasser", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "amber vanilla", "top_notes": "vanilla, myrrh", "heart_notes": "guaiac wood, beeswax", "base_notes": "amber, musk", "price_eur": 95, "rarity": "Common", "year": 2012, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "A City on Fire EDP 50ml", "house": "Imaginary Authors", "fragrance_name": "A City on Fire", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "smoky woody", "top_notes": "smoke, cade oil", "heart_notes": "burning wood, paper", "base_notes": "benzoin, guaiac wood", "price_eur": 95, "rarity": "Common", "year": 2014, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Slow Explosions EDP 50ml", "house": "Imaginary Authors", "fragrance_name": "Slow Explosions", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "amber saffron", "top_notes": "saffron, green apple", "heart_notes": "orris, suede", "base_notes": "amber, sandalwood, musk", "price_eur": 95, "rarity": "Common", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
    ]


def _expanded_niche_houses() -> list[dict]:
    """Expanded niche houses — Ex Nihilo, more Serge Lutens, CdG, DS&D, etc."""
    return [
        # Ex Nihilo
        {"name": "Fleur Narcotique EDP 100ml", "house": "Ex Nihilo", "fragrance_name": "Fleur Narcotique", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "floral musk", "top_notes": "peach blossom, bergamot", "heart_notes": "peony, rose, jasmine", "base_notes": "white musk, ambroxan, moss", "price_eur": 250, "rarity": "Common", "year": 2014, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "French Affair EDP 100ml", "house": "Ex Nihilo", "fragrance_name": "French Affair", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "oriental floral", "top_notes": "pink pepper, bergamot", "heart_notes": "Turkish rose, oud", "base_notes": "amber, musk, sandalwood", "price_eur": 260, "rarity": "Common", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Venenum Kiss EDP 100ml", "house": "Ex Nihilo", "fragrance_name": "Venenum Kiss", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "fruity floral", "top_notes": "raspberry, pink pepper", "heart_notes": "rose, osmanthus, orris", "base_notes": "vanilla, amber, musk", "price_eur": 250, "rarity": "Common", "year": 2018, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Bois d'Hiver EDP 100ml", "house": "Ex Nihilo", "fragrance_name": "Bois d'Hiver", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "woody amber", "top_notes": "ginger, bergamot", "heart_notes": "cedar, iris, violet", "base_notes": "amber, sandalwood, musk", "price_eur": 250, "rarity": "Common", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Musc Infini EDP 100ml", "house": "Ex Nihilo", "fragrance_name": "Musc Infini", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "musk floral", "top_notes": "bergamot, saffron", "heart_notes": "iris, jasmine, cashmeran", "base_notes": "white musk, amber, cedar", "price_eur": 255, "rarity": "Common", "year": 2016, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Amber Sky EDP 100ml", "house": "Ex Nihilo", "fragrance_name": "Amber Sky", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "amber woody", "top_notes": "saffron, cardamom", "heart_notes": "amber, oud, incense", "base_notes": "vanilla, sandalwood, musk", "price_eur": 260, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Serge Lutens (additions)
        {"name": "Feminite du Bois EDP 50ml", "house": "Serge Lutens", "fragrance_name": "Feminite du Bois", "concentration": "EDP", "size_ml": 50, "gender": "feminine", "fragrance_family": "woody spicy", "top_notes": "plum, orange, clove", "heart_notes": "cedar, cinnamon", "base_notes": "musk, vanilla, honey, beeswax", "price_eur": 140, "rarity": "Common", "year": 1992, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Un Bois Vanille EDP 50ml", "house": "Serge Lutens", "fragrance_name": "Un Bois Vanille", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "amber vanilla", "top_notes": "benzoin, coconut", "heart_notes": "vanilla, guaiac wood", "base_notes": "sandalwood, musk, tonka bean", "price_eur": 140, "rarity": "Common", "year": 2003, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Comme des Garçons (additions)
        {"name": "Amazingreen EDP 100ml", "house": "Comme des Garçons", "fragrance_name": "Amazingreen", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "green woody", "top_notes": "green pepper, palm tree leaves", "heart_notes": "ivy, orris, silex", "base_notes": "vetiver, musk, white amber", "price_eur": 105, "rarity": "Common", "year": 2012, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Concrete EDP 80ml", "house": "Comme des Garçons", "fragrance_name": "Concrete", "concentration": "EDP", "size_ml": 80, "gender": "unisex", "fragrance_family": "mineral woody", "top_notes": "white pepper, sandalwood", "heart_notes": "cyclamen, rose, hyacinth", "base_notes": "cedar, cashmeran, musk", "price_eur": 115, "rarity": "Common", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # D.S. & Durga (additions)
        {"name": "Radio Bombay EDP 50ml", "house": "D.S. & Durga", "fragrance_name": "Radio Bombay", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "woody warm", "top_notes": "radish, copper", "heart_notes": "sandalwood, cedar", "base_notes": "cashmeran, amber, coconut", "price_eur": 175, "rarity": "Common", "year": 2014, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Burning Barbershop EDP 50ml", "house": "D.S. & Durga", "fragrance_name": "Burning Barbershop", "concentration": "EDP", "size_ml": 50, "gender": "masculine", "fragrance_family": "aromatic smoky", "top_notes": "spearmint, lavender, hemp", "heart_notes": "smoke, embers", "base_notes": "vanilla, tonka, musk", "price_eur": 175, "rarity": "Common", "year": 2008, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Rose Atlantic EDP 50ml", "house": "D.S. & Durga", "fragrance_name": "Rose Atlantic", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "floral marine", "top_notes": "bergamot, lemon, sea salt", "heart_notes": "rose, orris, green moss", "base_notes": "musk, ambergris", "price_eur": 175, "rarity": "Common", "year": 2015, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Histoires de Parfums (additions)
        {"name": "Noir Patchouli EDP 120ml", "house": "Histoires de Parfums", "fragrance_name": "Noir Patchouli", "concentration": "EDP", "size_ml": 120, "gender": "unisex", "fragrance_family": "woody earthy", "top_notes": "elemi, bergamot", "heart_notes": "patchouli, labdanum", "base_notes": "amber, musk, vetiver", "price_eur": 170, "rarity": "Common", "year": 2010, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Vert Pivoine EDP 120ml", "house": "Histoires de Parfums", "fragrance_name": "Vert Pivoine", "concentration": "EDP", "size_ml": 120, "gender": "feminine", "fragrance_family": "green floral", "top_notes": "green notes, galbanum", "heart_notes": "peony, rose, jasmine", "base_notes": "musk, cedar, amber", "price_eur": 160, "rarity": "Common", "year": 2012, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Aesop (addition)
        {"name": "Rozu EDP 50ml", "house": "Aesop", "fragrance_name": "Rozu", "concentration": "EDP", "size_ml": 50, "gender": "unisex", "fragrance_family": "floral green", "top_notes": "shiso, pink pepper", "heart_notes": "Damask rose, guaiac wood", "base_notes": "vetiver, patchouli, musk", "price_eur": 150, "rarity": "Common", "year": 2020, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Juliette Has A Gun (addition)
        {"name": "Vanilla Vibes EDP 100ml", "house": "Juliette Has A Gun", "fragrance_name": "Vanilla Vibes", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "amber vanilla", "top_notes": "sea salt, orchid", "heart_notes": "vanilla, jasmine", "base_notes": "sandalwood, tonka, musk", "price_eur": 115, "rarity": "Common", "year": 2018, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Ormonde Jayne (addition)
        {"name": "Isfarkand EDP 120ml", "house": "Ormonde Jayne", "fragrance_name": "Isfarkand", "concentration": "EDP", "size_ml": 120, "gender": "unisex", "fragrance_family": "floral fruity", "top_notes": "litchi, pink pepper, bergamot", "heart_notes": "iris, jasmine, violet", "base_notes": "sandalwood, cedar, musk, amber", "price_eur": 165, "rarity": "Common", "year": 2012, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Vilhelm Parfumerie (addition)
        {"name": "Poets of Berlin EDP 100ml", "house": "Vilhelm Parfumerie", "fragrance_name": "Poets of Berlin", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "citrus gourmand", "top_notes": "bamboo, mandarin", "heart_notes": "raspberry, rhubarb", "base_notes": "vanilla, sandalwood, musk", "price_eur": 175, "rarity": "Common", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Atelier Cologne (additions)
        {"name": "Clementine California Cologne Absolue 100ml", "house": "Atelier Cologne", "fragrance_name": "Clementine California", "concentration": "EDC", "size_ml": 100, "gender": "unisex", "fragrance_family": "citrus aromatic", "top_notes": "clementine, juniper berry, star anise", "heart_notes": "cypress, vetiver", "base_notes": "cedar, sandalwood, musk", "price_eur": 130, "rarity": "Common", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Vanille Insensee Cologne Absolue 100ml", "house": "Atelier Cologne", "fragrance_name": "Vanille Insensee", "concentration": "EDC", "size_ml": 100, "gender": "unisex", "fragrance_family": "amber vanilla", "top_notes": "lime, coriander", "heart_notes": "jasmine, vanilla", "base_notes": "oak moss, vetiver, musk", "price_eur": 130, "rarity": "Common", "year": 2011, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Goldfield & Banks (addition)
        {"name": "Southern Bloom EDP 100ml", "house": "Goldfield & Banks", "fragrance_name": "Southern Bloom", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "floral green", "top_notes": "green leaves, bergamot", "heart_notes": "boronia flower, osmanthus", "base_notes": "sandalwood, musk, amber", "price_eur": 160, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Mancera (addition)
        {"name": "Hindu Kush EDP 120ml", "house": "Mancera", "fragrance_name": "Hindu Kush", "concentration": "EDP", "size_ml": 120, "gender": "unisex", "fragrance_family": "woody aromatic", "top_notes": "cannabis, ginger, citrus", "heart_notes": "oud, lavender, geranium", "base_notes": "amber, musk, patchouli, cedar", "price_eur": 110, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Byredo (additions)
        {"name": "Black Saffron EDP 100ml", "house": "Byredo", "fragrance_name": "Black Saffron", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "spicy woody", "top_notes": "saffron, juniper berry, pomelo", "heart_notes": "black violet, leather accord", "base_notes": "vetiver, blonde wood, raspberry", "price_eur": 195, "rarity": "Common", "year": 2012, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Pulp EDP 100ml", "house": "Byredo", "fragrance_name": "Pulp", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "fruity sweet", "top_notes": "black currant, red apple, bergamot", "heart_notes": "cardamom, fig, cedar", "base_notes": "praline, tonka bean, vanilla", "price_eur": 190, "rarity": "Common", "year": 2008, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Le Labo (addition)
        {"name": "Lys 41 EDP 100ml", "house": "Le Labo", "fragrance_name": "Lys 41", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "white floral", "top_notes": "lily, iris, orange blossom", "heart_notes": "tuberose, jasmine, ylang-ylang", "base_notes": "musk, vanilla, cedar", "price_eur": 340, "rarity": "Uncommon", "year": 2006, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Papillon Artisan (additions)
        {"name": "Dryad Parfum 50ml", "house": "Papillon Artisan Perfumes", "fragrance_name": "Dryad", "concentration": "Parfum", "size_ml": 50, "gender": "unisex", "fragrance_family": "green chypre", "top_notes": "galbanum, bergamot, petitgrain", "heart_notes": "oakmoss, rose, jasmine", "base_notes": "patchouli, amber, musk", "price_eur": 175, "rarity": "Uncommon", "year": 2016, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Tobacco Rose Parfum 50ml", "house": "Papillon Artisan Perfumes", "fragrance_name": "Tobacco Rose", "concentration": "Parfum", "size_ml": 50, "gender": "unisex", "fragrance_family": "tobacco floral", "top_notes": "Bulgarian rose, raspberry", "heart_notes": "tobacco, dried fruit, hay", "base_notes": "amber, vanilla, musk, sandalwood", "price_eur": 175, "rarity": "Common", "year": 2016, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Masque Milano (additions)
        {"name": "Romanza EDP 100ml", "house": "Masque Milano", "fragrance_name": "Romanza", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "floral green", "top_notes": "violet leaf, bergamot, grapefruit", "heart_notes": "iris, rose, jasmine", "base_notes": "sandalwood, amber, musk", "price_eur": 160, "rarity": "Common", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Madeleine EDP 100ml", "house": "Masque Milano", "fragrance_name": "Madeleine", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "gourmand floral", "top_notes": "lemon, bergamot, butter", "heart_notes": "jasmine, heliotrope, almond", "base_notes": "vanilla, amber, musk, tonka", "price_eur": 165, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # BDK Parfums (additions)
        {"name": "Pas Ce Soir EDP 100ml", "house": "BDK Parfums", "fragrance_name": "Pas Ce Soir", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "oriental spicy", "top_notes": "saffron, pink pepper, bergamot", "heart_notes": "oud, Turkish rose", "base_notes": "amber, vanilla, musk, sandalwood", "price_eur": 195, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Bouquet de Hongrie EDP 100ml", "house": "BDK Parfums", "fragrance_name": "Bouquet de Hongrie", "concentration": "EDP", "size_ml": 100, "gender": "feminine", "fragrance_family": "floral fruity", "top_notes": "raspberry, pink pepper, bergamot", "heart_notes": "rose, peony, magnolia", "base_notes": "musk, amber, cedar", "price_eur": 185, "rarity": "Common", "year": 2016, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Tabac Rose EDP 100ml", "house": "BDK Parfums", "fragrance_name": "Tabac Rose", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "tobacco floral", "top_notes": "cinnamon, pink pepper", "heart_notes": "Turkish rose, tobacco", "base_notes": "patchouli, vanilla, amber, musk", "price_eur": 195, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Nishane (addition)
        {"name": "Safran Colognise EDC 100ml", "house": "Nishane", "fragrance_name": "Safran Colognise", "concentration": "EDC", "size_ml": 100, "gender": "unisex", "fragrance_family": "spicy citrus", "top_notes": "saffron, bergamot, lemon", "heart_notes": "rose, geranium, cinnamon", "base_notes": "amber, musk, sandalwood, cedar", "price_eur": 145, "rarity": "Common", "year": 2015, "image_url": "https://fimgs.net/mdimg/placeholder"},
    ]


def _ex_nihilo_crivelli_escentric() -> list[dict]:
    """Ex Nihilo, Maison Crivelli, Escentric Molecules, extra Frederic Malle & Parfums de Marly."""
    return [
        # Ex Nihilo (7)
        {"name": "Fleur Narcotique EDP 100ml", "house": "Ex Nihilo", "fragrance_name": "Fleur Narcotique", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "floral musk", "top_notes": "bergamot, lychee, black peony", "heart_notes": "rose, peach blossom", "base_notes": "white musk, moss, ambroxan", "price_eur": 290, "rarity": "Common", "year": 2013, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "French Affair EDP 100ml", "house": "Ex Nihilo", "fragrance_name": "French Affair", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "amber spicy", "top_notes": "pink pepper, saffron", "heart_notes": "iris, jasmine, oud", "base_notes": "amber, musk, benzoin", "price_eur": 295, "rarity": "Common", "year": 2014, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Venenum Kiss EDP 100ml", "house": "Ex Nihilo", "fragrance_name": "Venenum Kiss", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "floral woody", "top_notes": "bergamot, pink pepper", "heart_notes": "rose, jasmine, saffron", "base_notes": "sandalwood, amber, musk", "price_eur": 290, "rarity": "Common", "year": 2018, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Bois d'Hiver EDP 100ml", "house": "Ex Nihilo", "fragrance_name": "Bois d'Hiver", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "woody amber", "top_notes": "bergamot, cardamom", "heart_notes": "cedar, vetiver, iris", "base_notes": "amber, musk, sandalwood", "price_eur": 285, "rarity": "Common", "year": 2016, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Musc Infini EDP 100ml", "house": "Ex Nihilo", "fragrance_name": "Musc Infini", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "musk floral", "top_notes": "pear, bergamot", "heart_notes": "jasmine, musk", "base_notes": "ambroxan, sandalwood, cedar", "price_eur": 285, "rarity": "Common", "year": 2015, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Amber Sky EDP 100ml", "house": "Ex Nihilo", "fragrance_name": "Amber Sky", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "amber citrus", "top_notes": "bergamot, mandarin, neroli", "heart_notes": "orange blossom, saffron", "base_notes": "amber, vanilla, musk, benzoin", "price_eur": 290, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Outlaw EDP 100ml", "house": "Ex Nihilo", "fragrance_name": "Outlaw", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "leather woody", "top_notes": "bergamot, elemi", "heart_notes": "leather, styrax, labdanum", "base_notes": "patchouli, cedar, musk", "price_eur": 290, "rarity": "Common", "year": 2017, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Maison Crivelli (5 — Iris Malikhan & Oud Maracuja already in _more_niche_houses)
        {"name": "Absinthe Boreale EDP 100ml", "house": "Maison Crivelli", "fragrance_name": "Absinthe Boreale", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "aromatic green", "top_notes": "absinthe, star anise, cardamom", "heart_notes": "artemisia, geranium", "base_notes": "vetiver, cedar, musk", "price_eur": 185, "rarity": "Common", "year": 2018, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Hibiscus Mahajad EDP 100ml", "house": "Maison Crivelli", "fragrance_name": "Hibiscus Mahajad", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "floral spicy", "top_notes": "pink pepper, ginger", "heart_notes": "hibiscus, saffron", "base_notes": "sandalwood, musk, amber", "price_eur": 185, "rarity": "Common", "year": 2018, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Rose Saltifolia EDP 100ml", "house": "Maison Crivelli", "fragrance_name": "Rose Saltifolia", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "floral marine", "top_notes": "sea salt, pink pepper", "heart_notes": "rose, driftwood", "base_notes": "musk, ambroxan, cedar", "price_eur": 185, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Papyrus Moléculaire EDP 100ml", "house": "Maison Crivelli", "fragrance_name": "Papyrus Moléculaire", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "woody papyrus", "top_notes": "pink pepper, elemi", "heart_notes": "papyrus, violet leaf", "base_notes": "cedar, vetiver, musk", "price_eur": 185, "rarity": "Common", "year": 2020, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Santal Volcanique EDP 100ml", "house": "Maison Crivelli", "fragrance_name": "Santal Volcanique", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "woody smoky", "top_notes": "lapsang souchong, pink pepper", "heart_notes": "sandalwood, guaiac wood", "base_notes": "amber, musk, vanilla", "price_eur": 185, "rarity": "Common", "year": 2021, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Escentric Molecules (6)
        {"name": "Molecule 01 EDT 100ml", "house": "Escentric Molecules", "fragrance_name": "Molecule 01", "concentration": "EDT", "size_ml": 100, "gender": "unisex", "fragrance_family": "molecular woody", "top_notes": "Iso E Super", "heart_notes": "Iso E Super", "base_notes": "Iso E Super, cedar", "price_eur": 95, "rarity": "Common", "year": 2006, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Molecule 01 EDT 30ml", "house": "Escentric Molecules", "fragrance_name": "Molecule 01", "concentration": "EDT", "size_ml": 30, "gender": "unisex", "fragrance_family": "molecular woody", "top_notes": "Iso E Super", "heart_notes": "Iso E Super", "base_notes": "Iso E Super, cedar", "price_eur": 50, "rarity": "Common", "year": 2006, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Molecule 02 EDP 100ml", "house": "Escentric Molecules", "fragrance_name": "Molecule 02", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "molecular musk", "top_notes": "Ambroxan", "heart_notes": "Ambroxan", "base_notes": "Ambroxan, musk", "price_eur": 95, "rarity": "Common", "year": 2008, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Escentric 01 EDT 100ml", "house": "Escentric Molecules", "fragrance_name": "Escentric 01", "concentration": "EDT", "size_ml": 100, "gender": "unisex", "fragrance_family": "woody fresh", "top_notes": "pink pepper, lime", "heart_notes": "Iso E Super, iris", "base_notes": "cedar, musk", "price_eur": 105, "rarity": "Common", "year": 2006, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Escentric 02 EDP 100ml", "house": "Escentric Molecules", "fragrance_name": "Escentric 02", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "musky amber", "top_notes": "elemi, hedione", "heart_notes": "Ambroxan, violet, orris", "base_notes": "musk, vetiver", "price_eur": 105, "rarity": "Common", "year": 2008, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Molecule 03 EDP 100ml", "house": "Escentric Molecules", "fragrance_name": "Molecule 03", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "molecular vetiver", "top_notes": "Vetiveryl Acetate", "heart_notes": "vetiver, ginger", "base_notes": "Vetiveryl Acetate", "price_eur": 95, "rarity": "Common", "year": 2010, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Extra Frederic Malle (5)
        {"name": "Bigarade Concentrée EDT 100ml", "house": "Frederic Malle", "fragrance_name": "Bigarade Concentrée", "concentration": "EDT", "size_ml": 100, "gender": "unisex", "fragrance_family": "citrus aromatic", "top_notes": "bitter orange, cardamom, nutmeg", "heart_notes": "cedar, incense", "base_notes": "amber, musk, patchouli", "price_eur": 220, "rarity": "Common", "year": 2002, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "En Passant EDT 100ml", "house": "Frederic Malle", "fragrance_name": "En Passant", "concentration": "EDT", "size_ml": 100, "gender": "unisex", "fragrance_family": "floral green", "top_notes": "cucumber, wheat, green", "heart_notes": "lilac, white musk", "base_notes": "bread, heliotrope, musk", "price_eur": 230, "rarity": "Common", "year": 2000, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Lipstick Rose EDP 100ml", "house": "Frederic Malle", "fragrance_name": "Lipstick Rose", "concentration": "EDP", "size_ml": 100, "gender": "feminine", "fragrance_family": "floral powdery", "top_notes": "grapefruit, violet", "heart_notes": "rose, iris", "base_notes": "vanilla, musk, amber, white wood", "price_eur": 260, "rarity": "Common", "year": 2000, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Vetiver Extraordinaire EDP 100ml", "house": "Frederic Malle", "fragrance_name": "Vetiver Extraordinaire", "concentration": "EDP", "size_ml": 100, "gender": "masculine", "fragrance_family": "woody vetiver", "top_notes": "bergamot, bitter orange, pink pepper", "heart_notes": "Haitian vetiver, sandalwood", "base_notes": "cedar, musk, amber", "price_eur": 280, "rarity": "Common", "year": 2002, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Noir Epices EDP 100ml", "house": "Frederic Malle", "fragrance_name": "Noir Epices", "concentration": "EDP", "size_ml": 100, "gender": "unisex", "fragrance_family": "spicy oriental", "top_notes": "black pepper, clove, nutmeg", "heart_notes": "geranium, saffron, coffee", "base_notes": "sandalwood, patchouli, musk", "price_eur": 280, "rarity": "Common", "year": 2000, "image_url": "https://fimgs.net/mdimg/placeholder"},
        # Extra Parfums de Marly (5)
        {"name": "Greenley EDP 125ml", "house": "Parfums de Marly", "fragrance_name": "Greenley", "concentration": "EDP", "size_ml": 125, "gender": "masculine", "fragrance_family": "citrus green", "top_notes": "green apple, bergamot, grapefruit", "heart_notes": "green tea, violet leaf", "base_notes": "vetiver, musk, cedar, amber", "price_eur": 215, "rarity": "Common", "year": 2021, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Percival EDP 125ml", "house": "Parfums de Marly", "fragrance_name": "Percival", "concentration": "EDP", "size_ml": 125, "gender": "masculine", "fragrance_family": "aromatic fresh", "top_notes": "bergamot, mandarin, lavender", "heart_notes": "geranium, jasmine, rose", "base_notes": "amber, musk, cashmeran, cedar", "price_eur": 240, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Galloway EDP 125ml", "house": "Parfums de Marly", "fragrance_name": "Galloway", "concentration": "EDP", "size_ml": 125, "gender": "masculine", "fragrance_family": "citrus aromatic", "top_notes": "lemon, bergamot, orange", "heart_notes": "nutmeg, rose, cinnamon", "base_notes": "amber, oud, vanilla, musk", "price_eur": 240, "rarity": "Common", "year": 2014, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Cassili EDP 75ml", "house": "Parfums de Marly", "fragrance_name": "Cassili", "concentration": "EDP", "size_ml": 75, "gender": "feminine", "fragrance_family": "floral fruity", "top_notes": "peach, bergamot, cassis", "heart_notes": "jasmine, rose, orange blossom", "base_notes": "sandalwood, vanilla, musk, amber", "price_eur": 260, "rarity": "Common", "year": 2019, "image_url": "https://fimgs.net/mdimg/placeholder"},
        {"name": "Meliora EDP 75ml", "house": "Parfums de Marly", "fragrance_name": "Meliora", "concentration": "EDP", "size_ml": 75, "gender": "feminine", "fragrance_family": "floral woody", "top_notes": "red fruits, Egyptian jasmine", "heart_notes": "Turkish rose, iris", "base_notes": "sandalwood, vanilla, white musk", "price_eur": 240, "rarity": "Common", "year": 2016, "image_url": "https://fimgs.net/mdimg/placeholder"},
    ]


def _variant_expansion() -> list[dict]:
    """Create size and concentration variants for popular fragrances."""
    variants: list[dict] = []
    base_frags = [
        ("Maison Francis Kurkdjian", "Baccarat Rouge 540", "EDP", "unisex", "amber floral", 255, "Common"),
        ("Tom Ford", "Oud Wood", "EDP", "unisex", "woody oud", 250, "Common"),
        ("Tom Ford", "Tobacco Vanille", "EDP", "unisex", "tobacco vanilla", 250, "Common"),
        ("Tom Ford", "Lost Cherry", "EDP", "unisex", "fruity gourmand", 290, "Common"),
        ("Creed", "Aventus", "EDP", "masculine", "fruity woody", 410, "Common"),
        ("Creed", "Green Irish Tweed", "EDP", "masculine", "green aromatic", 330, "Common"),
        ("Parfums de Marly", "Layton", "EDP", "masculine", "aromatic vanilla", 240, "Common"),
        ("Parfums de Marly", "Herod", "EDP", "masculine", "tobacco vanilla", 240, "Common"),
        ("Xerjoff", "Naxos", "EDP", "unisex", "tobacco honey", 220, "Common"),
        ("Initio", "Side Effect", "EDP", "unisex", "tobacco vanilla", 260, "Common"),
        ("Kilian", "Angels' Share", "EDP", "unisex", "boozy gourmand", 255, "Common"),
        ("Le Labo", "Santal 33", "EDP", "unisex", "woody aromatic", 230, "Common"),
        ("Byredo", "Gypsy Water", "EDP", "unisex", "woody aromatic", 190, "Common"),
        ("Frederic Malle", "Portrait of a Lady", "EDP", "feminine", "floral oriental", 300, "Common"),
        ("Amouage", "Interlude Man", "EDP", "masculine", "smoky woody", 310, "Common"),
        ("Roja Parfums", "Elysium", "Parfum", "masculine", "citrus aromatic", 290, "Common"),
        ("Diptyque", "Philosykos", "EDP", "unisex", "green fig", 145, "Common"),
        ("Montale", "Intense Cafe", "EDP", "unisex", "coffee rose", 120, "Common"),
        ("Nishane", "Hacivat", "Extrait", "unisex", "fruity woody", 180, "Common"),
        ("Tiziana Terenzi", "Kirke", "Extrait", "unisex", "fruity floral", 270, "Common"),
        # More niche houses
        ("Serge Lutens", "Chergui", "EDP", "unisex", "amber tobacco", 140, "Common"),
        ("Serge Lutens", "Ambre Sultan", "EDP", "unisex", "amber resinous", 140, "Common"),
        ("D.S. & Durga", "Debaser", "EDP", "unisex", "green fig", 175, "Common"),
        ("Mancera", "Red Tobacco", "EDP", "unisex", "tobacco spicy", 115, "Common"),
        ("Montale", "Black Aoud", "EDP", "masculine", "oud rose", 125, "Common"),
        ("Comme des Garçons", "Wonderwood", "EDP", "masculine", "woody", 110, "Common"),
        ("Juliette Has A Gun", "Not a Perfume", "EDP", "unisex", "clean musk", 115, "Common"),
        ("Ormonde Jayne", "Ormonde Man", "EDP", "masculine", "woody green", 165, "Common"),
        ("Vilhelm Parfumerie", "Dear Polly", "EDP", "unisex", "fruity tea", 175, "Common"),
        ("Histoires de Parfums", "1725", "EDP", "masculine", "amber vanilla", 170, "Common"),
        ("Aesop", "Hwyl", "EDP", "unisex", "woody smoky", 150, "Common"),
        # Additional popular
        ("Parfums de Marly", "Delina", "EDP", "feminine", "floral fruity", 260, "Common"),
        ("Kilian", "Black Phantom", "EDP", "unisex", "boozy woody", 255, "Common"),
        ("Initio", "Oud for Greatness", "EDP", "unisex", "oud woody", 280, "Common"),
        ("Xerjoff", "Erba Pura", "EDP", "unisex", "fruity amber", 200, "Common"),
        ("Byredo", "Bal d'Afrique", "EDP", "unisex", "floral woody musk", 190, "Common"),
        ("Le Labo", "Rose 31", "EDP", "unisex", "floral woody", 230, "Common"),
        ("Le Labo", "Another 13", "EDP", "unisex", "musky woody", 260, "Common"),
        ("Frederic Malle", "Musc Ravageur", "EDP", "unisex", "amber musk", 280, "Common"),
        ("Maison Margiela", "By the Fireplace", "EDT", "unisex", "smoky woody", 120, "Common"),
        ("Maison Margiela", "Jazz Club", "EDT", "masculine", "aromatic tobacco", 120, "Common"),
        ("Nishane", "Ani", "Extrait", "unisex", "amber vanilla", 185, "Common"),
        ("Penhaligon's", "Halfeti", "EDP", "unisex", "oriental spicy", 210, "Common"),
        ("Tom Ford", "Tuscan Leather", "EDP", "unisex", "leather", 250, "Common"),
        ("Tom Ford", "Neroli Portofino", "EDP", "unisex", "citrus aromatic", 230, "Common"),
        # Additional variant bases
        ("Parfums de Marly", "Carlisle", "EDP", "unisex", "amber woody", 285, "Common"),
        ("Parfums de Marly", "Oajan", "EDP", "unisex", "oriental spicy", 265, "Common"),
        ("Kilian", "Straight to Heaven", "EDP", "masculine", "woody amber", 255, "Common"),
        ("Kilian", "Good Girl Gone Bad", "EDP", "feminine", "floral fruity", 255, "Common"),
        ("Initio", "Rehab", "EDP", "unisex", "aromatic lavender", 260, "Common"),
        ("Nishane", "Wulong Cha", "Extrait", "unisex", "tea citrus", 170, "Common"),
        ("Nishane", "Fan Your Flames", "Extrait", "unisex", "amber oriental", 195, "Common"),
        ("Byredo", "Bibliothèque", "EDP", "unisex", "woody aromatic", 195, "Common"),
        ("Byredo", "Oud Immortel", "EDP", "unisex", "woody oud", 210, "Common"),
        ("Le Labo", "Thé Noir 29", "EDP", "unisex", "tea smoky", 230, "Common"),
        ("Le Labo", "Tonka 25", "EDP", "unisex", "amber gourmand", 280, "Common"),
        ("Frederic Malle", "The Night", "EDP", "unisex", "oud rose", 450, "Uncommon"),
        ("Frederic Malle", "French Lover", "EDP", "masculine", "woody chypre", 280, "Common"),
        ("Tiziana Terenzi", "Saiph", "Extrait", "unisex", "amber spicy", 275, "Common"),
        ("Tiziana Terenzi", "Orion", "Extrait", "unisex", "amber vanilla", 260, "Common"),
        ("Memo Paris", "African Leather", "EDP", "unisex", "leather oud", 240, "Common"),
        ("Roja Parfums", "Enigma (Creation-E)", "Parfum", "masculine", "amber woody", 600, "Uncommon"),
        ("Xerjoff", "Alexandria II", "EDP", "unisex", "citrus amber", 300, "Uncommon"),
        ("Xerjoff", "Mefisto", "EDP", "masculine", "citrus fresh", 210, "Common"),
        ("Clive Christian", "No. 1 for Men", "Parfum", "masculine", "oriental woody", 650, "Rare"),
        ("Montale", "Starry Nights", "EDP", "unisex", "amber oriental", 135, "Common"),
        ("Montale", "Roses Musk", "EDP", "feminine", "floral musk", 115, "Common"),
        ("Mancera", "Instant Crush", "EDP", "unisex", "amber vanilla", 110, "Common"),
        ("Mancera", "Wild Leather", "EDP", "unisex", "leather aromatic", 105, "Common"),
        ("Serge Lutens", "La Fille de Berlin", "EDP", "unisex", "floral woody", 140, "Common"),
        ("Serge Lutens", "Datura Noir", "EDP", "unisex", "floral tropical", 140, "Common"),
        ("Amouage", "Reflection Man", "EDP", "masculine", "floral woody", 290, "Common"),
        ("Amouage", "Memoir Man", "EDP", "masculine", "green smoky", 290, "Common"),
        # Expanded niche houses
        ("Ex Nihilo", "Fleur Narcotique", "EDP", "unisex", "floral musk", 250, "Common"),
        ("Ex Nihilo", "French Affair", "EDP", "unisex", "oriental floral", 260, "Common"),
        ("Ex Nihilo", "Musc Infini", "EDP", "unisex", "musk floral", 255, "Common"),
        ("Serge Lutens", "Un Bois Vanille", "EDP", "unisex", "amber vanilla", 140, "Common"),
        ("Serge Lutens", "Feminite du Bois", "EDP", "feminine", "woody spicy", 140, "Common"),
        ("Comme des Garçons", "Amazingreen", "EDP", "unisex", "green woody", 105, "Common"),
        ("D.S. & Durga", "Radio Bombay", "EDP", "unisex", "woody warm", 175, "Common"),
        ("D.S. & Durga", "Burning Barbershop", "EDP", "masculine", "aromatic smoky", 175, "Common"),
        ("Atelier Cologne", "Clementine California", "EDC", "unisex", "citrus aromatic", 130, "Common"),
        ("Atelier Cologne", "Vanille Insensee", "EDC", "unisex", "amber vanilla", 130, "Common"),
        ("Goldfield & Banks", "Southern Bloom", "EDP", "unisex", "floral green", 160, "Common"),
        ("Juliette Has A Gun", "Vanilla Vibes", "EDP", "unisex", "amber vanilla", 115, "Common"),
        ("BDK Parfums", "Pas Ce Soir", "EDP", "unisex", "oriental spicy", 195, "Common"),
        ("BDK Parfums", "Tabac Rose", "EDP", "unisex", "tobacco floral", 195, "Common"),
        ("Nishane", "Safran Colognise", "EDC", "unisex", "spicy citrus", 145, "Common"),
        ("Mancera", "Hindu Kush", "EDP", "unisex", "woody aromatic", 110, "Common"),
        ("Byredo", "Black Saffron", "EDP", "unisex", "spicy woody", 195, "Common"),
        ("Byredo", "Pulp", "EDP", "unisex", "fruity sweet", 190, "Common"),
        ("Le Labo", "Lys 41", "EDP", "unisex", "white floral", 340, "Uncommon"),
        # Ex Nihilo / Maison Crivelli / Escentric Molecules / extra FM & PdM
        ("Ex Nihilo", "Fleur Narcotique", "EDP", "unisex", "floral musk", 290, "Common"),
        ("Ex Nihilo", "French Affair", "EDP", "unisex", "amber spicy", 295, "Common"),
        ("Maison Crivelli", "Absinthe Boreale", "EDP", "unisex", "aromatic green", 185, "Common"),
        ("Escentric Molecules", "Molecule 01", "EDT", "unisex", "molecular woody", 95, "Common"),
        ("Frederic Malle", "Noir Epices", "EDP", "unisex", "spicy oriental", 280, "Common"),
        ("Parfums de Marly", "Percival", "EDP", "masculine", "aromatic fresh", 240, "Common"),
        ("Parfums de Marly", "Greenley", "EDP", "masculine", "citrus green", 215, "Common"),
    ]
    size_variants = [
        (30, 0.50, "travel"),
        (50, 0.75, "standard"),
        (200, 1.80, "jumbo"),
    ]
    conc_variants = [
        ("EDT", 0.70),
        ("Extrait", 1.40),
        ("Parfum", 1.50),
    ]
    for house, frag, base_conc, gender, family, base_price, _ in base_frags:
        for size, size_mult, size_label in size_variants:
            variants.append({
                "name": f"{frag} {base_conc} {size}ml",
                "house": house,
                "fragrance_name": frag,
                "concentration": base_conc,
                "size_ml": size,
                "gender": gender,
                "fragrance_family": family,
                "top_notes": "", "heart_notes": "", "base_notes": "",
                "price_eur": int(base_price * size_mult),
                "rarity": "Common",
                "year": 2020,
                "image_url": "https://fimgs.net/mdimg/placeholder",
            })
        for conc, conc_mult in conc_variants:
            if conc != base_conc:
                variants.append({
                    "name": f"{frag} {conc} 100ml",
                    "house": house,
                    "fragrance_name": frag,
                    "concentration": conc,
                    "size_ml": 100,
                    "gender": gender,
                    "fragrance_family": family,
                    "top_notes": "", "heart_notes": "", "base_notes": "",
                    "price_eur": int(base_price * conc_mult),
                    "rarity": "Common",
                    "year": 2020,
                    "image_url": "https://fimgs.net/mdimg/placeholder",
                })
    return variants


# ---------------------------------------------------------------------------
# Catalog assembler
# ---------------------------------------------------------------------------

def get_curated_catalog() -> list[dict]:
    """Return the full curated niche perfumery catalog."""
    catalog: list[dict] = []
    catalog.extend(_mfk())
    catalog.extend(_tom_ford())
    catalog.extend(_creed())
    catalog.extend(_pdm())
    catalog.extend(_xerjoff_amouage())
    catalog.extend(_byredo_lelabo())
    catalog.extend(_indie_niche())
    catalog.extend(_initio_kilian())
    catalog.extend(_diptyque_penhaligons_malle())
    catalog.extend(_montale_mancera_replica())
    catalog.extend(_roja_nishane_tiziana())
    catalog.extend(_clive_christian_memo())
    catalog.extend(_more_niche_houses())
    catalog.extend(_additional_niche())
    catalog.extend(_ex_nihilo_crivelli_escentric())
    catalog.extend(_expanded_niche_houses())
    catalog.extend(_variant_expansion())
    # Deduplicate by (house, fragrance_name, concentration, size_ml)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = (item.get("house", ""), item.get("fragrance_name", ""),
                item.get("concentration", ""), item.get("size_ml", ""))
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


# ---------------------------------------------------------------------------
# Converters
# ---------------------------------------------------------------------------

def item_to_catalog_item(item: dict) -> CatalogItem:
    house = item.get("house", "")
    frag = item.get("fragrance_name", "")
    conc = item.get("concentration", "")
    size = item.get("size_ml", "")
    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{house}-{frag}-{conc}-{size}ml"),
        title=f"{house} {frag} {conc} {size}ml",
        set_code=conc,
        brand=house,
        rarity=item.get("rarity", "Common"),
        notes=f"Family: {item.get('fragrance_family', '')}. "
              f"Top: {item.get('top_notes', '')}. "
              f"Heart: {item.get('heart_notes', '')}. "
              f"Base: {item.get('base_notes', '')}.",
        attributes_json={
            "house": house,
            "fragrance_name": frag,
            "concentration": conc,
            "size_ml": size,
            "gender": item.get("gender", ""),
            "fragrance_family": item.get("fragrance_family", ""),
            "year": item.get("year", ""),
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    house = item.get("house", "")
    rarity = item.get("rarity", "Common")
    price = item["price_eur"]
    return PriceObservation(
        features={
            "condition_score": 0.95,
            "rarity_score": shared_rarity_score(rarity),
            "house_tier": _house_tier(house),
            "is_extrait": 1.0 if item.get("concentration") in ("Extrait", "Parfum") else 0.0,
        },
        price=float(price),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Import curated niche perfumery catalog + prices"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Write local files only, skip Supabase upsert")
    parser.add_argument("--jsonl-only", action="store_true",
                        help="Write only training JSONL, skip catalog SQL and Supabase")
    parser.add_argument("--cache-images", action="store_true",
                        help="Cache external image URLs to S3")
    args = parser.parse_args()

    logger.info("=== Niche Perfumery Import Pipeline ===")

    catalog = get_curated_catalog()
    logger.info(f"Curated catalog: {len(catalog)} fragrances")

    items = [item_to_catalog_item(f) for f in catalog]
    observations = [item_to_price_observation(f) for f in catalog]

    log_progress(CATEGORY, "items transformed", len(items))
    log_progress(CATEGORY, "price observations", len(observations))

    jsonl_path = write_training_jsonl(CATEGORY, observations)
    logger.info(f"Training JSONL written: {jsonl_path}")

    if args.jsonl_only:
        logger.info("  Mode: JSONL-ONLY (skipping catalog SQL and Supabase)")
        close_http_client()
        return

    sql_path = write_catalog_sql(CATEGORY, items)
    logger.info(f"Catalog SQL written: {sql_path}")

    if args.cache_images:
        items = cache_catalog_images(items, dry_run=args.dry_run)
        log_progress(CATEGORY, "images cached", len([i for i in items if i.image_url]))

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    if ingest.enabled:
        inserted = ingest.upsert_catalog(items)
        log_progress(CATEGORY, "catalog upserted", inserted)

    ingest.close()
    close_http_client()

    logger.info(f"\n=== Niche Perfumery Import Complete ===")
    logger.info(f"  Total catalog items:  {len(items)}")
    logger.info(f"  Price observations:   {len(observations)}")
    logger.info(f"  Price range:          EUR {min(o.price for o in observations):.0f} "
                f"- EUR {max(o.price for o in observations):.0f}")

    if args.dry_run:
        logger.info("  Mode: DRY RUN (local files only)")


if __name__ == "__main__":
    main()
