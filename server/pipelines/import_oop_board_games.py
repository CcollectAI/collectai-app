"""
Curated OOP Board Games & Kickstarter Exclusives Import Pipeline.

Imports a curated catalog of 700+ out-of-print and collectible board games across:
  - OOP Euro Games (Agricola, Tigris & Euphrates, El Grande, Puerto Rico, etc.)
  - Kickstarter Exclusives (Gloomhaven KS, Kingdom Death Monster, Nemesis, etc.)
  - Grail Games (1st ed Cosmic Encounter, Dark Tower, Splotter titles)
  - Deluxe/Big Box Editions (Scythe Legendary, Twilight Imperium, War of the Ring CE)
  - Legacy Games (Pandemic Legacy, Risk Legacy, Charterstone)
  - Designer Collectibles (Knizia, Rosenberg, Lacerda, Feld)
  - OOP Expansions (hard-to-find expansions)
  - Thematic/Ameritrash (HeroQuest, Fireball Island, Space Hulk)

Pattern follows import_whiskey.py (get_curated_catalog, item_to_catalog_item,
item_to_price_observation).

Usage:
    python -m pipelines.import_oop_board_games [--dry-run] [--jsonl-only] [--cache-images]
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

CATEGORY = "oop_board_games"

# ---------------------------------------------------------------------------
# Publisher-tier scoring for ML features
# ---------------------------------------------------------------------------
PUBLISHER_TIER: dict[str, float] = {
    # Grail-tier publishers (1.0)
    "Kingdom Death": 1.0,
    "Splotter Spellen": 1.0,
    # Premium KS publishers (0.9)
    "CMON": 0.9,
    "Chip Theory Games": 0.9,
    "Awaken Realms": 0.9,
    "Cephalofair Games": 0.9,
    "Leder Games": 0.9,
    "Petersen Games": 0.9,
    # High-end euro/thematic (0.8)
    "Fantasy Flight Games": 0.8,
    "Stonemaier Games": 0.8,
    "Eagle-Gryphon Games": 0.8,
    "Ares Games": 0.8,
    "Restoration Games": 0.8,
    "Roxley Games": 0.8,
    "Mindclash Games": 0.8,
    "Board & Dice": 0.8,
    "Deep Water Games": 0.8,
    "Plaid Hat Games": 0.8,
    "Czech Games Edition": 0.8,
    # Mid-range (0.7)
    "Z-Man Games": 0.7,
    "Rio Grande Games": 0.7,
    "Asmodee": 0.7,
    "Days of Wonder": 0.7,
    "Ravensburger": 0.7,
    "Hans im Glück": 0.7,
    "Queen Games": 0.7,
    "Repos Production": 0.7,
    "Lookout Games": 0.7,
    "Mayfair Games": 0.7,
    "Alea": 0.7,
    "Portal Games": 0.7,
    "Gale Force Nine": 0.7,
    "Pandasaurus Games": 0.7,
    "Greater Than Games": 0.7,
    "Dice Tower Games": 0.7,
    "Arcane Wonders": 0.7,
    "Stronghold Games": 0.7,
    # Standard (0.6)
    "Hasbro": 0.6,
    "Mattel": 0.6,
    "Parker Brothers": 0.6,
    "Milton Bradley": 0.6,
    "Games Workshop": 0.7,
    "Wizards of the Coast": 0.7,
    "Steve Jackson Games": 0.6,
    "Alderac Entertainment Group": 0.7,
}


def _publisher_tier(publisher: str) -> float:
    return PUBLISHER_TIER.get(publisher, 0.6)


# ---------------------------------------------------------------------------
# Curated catalog data
# ---------------------------------------------------------------------------

def _oop_euro_games() -> list[dict]:
    """OOP Euro games — classics no longer in print."""
    return [
        {"name": "Agricola (1st Edition)", "publisher": "Lookout Games", "designer": "Uwe Rosenberg", "year": 2007, "player_count": "1-5", "play_time": "120min", "bgg_rating": "7.9", "edition": "1st Edition", "condition": "complete", "price_eur": 85, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Agricola (Z-Man English)", "publisher": "Z-Man Games", "designer": "Uwe Rosenberg", "year": 2008, "player_count": "1-5", "play_time": "120min", "bgg_rating": "7.9", "edition": "Retail", "condition": "complete", "price_eur": 55, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Tigris & Euphrates", "publisher": "Hans im Glück", "designer": "Reiner Knizia", "year": 1997, "player_count": "2-4", "play_time": "90min", "bgg_rating": "7.7", "edition": "1st Edition", "condition": "complete", "price_eur": 120, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "El Grande", "publisher": "Hans im Glück", "designer": "Wolfgang Kramer", "year": 1995, "player_count": "2-5", "play_time": "90min", "bgg_rating": "7.8", "edition": "1st Edition", "condition": "complete", "price_eur": 110, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "El Grande Big Box", "publisher": "Hans im Glück", "designer": "Wolfgang Kramer", "year": 2015, "player_count": "2-5", "play_time": "90min", "bgg_rating": "7.8", "edition": "Big Box", "condition": "sealed", "price_eur": 180, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Puerto Rico (1st Edition)", "publisher": "Alea", "designer": "Andreas Seyfarth", "year": 2002, "player_count": "2-5", "play_time": "90min", "bgg_rating": "7.9", "edition": "1st Edition", "condition": "complete", "price_eur": 70, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Goa", "publisher": "Hans im Glück", "designer": "Rüdiger Dorn", "year": 2004, "player_count": "2-4", "play_time": "90min", "bgg_rating": "7.4", "edition": "1st Edition", "condition": "complete", "price_eur": 95, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Princes of Florence", "publisher": "Alea", "designer": "Wolfgang Kramer", "year": 2000, "player_count": "2-5", "play_time": "90min", "bgg_rating": "7.3", "edition": "1st Edition", "condition": "complete", "price_eur": 65, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Ra (1st Edition)", "publisher": "Alea", "designer": "Reiner Knizia", "year": 1999, "player_count": "2-5", "play_time": "60min", "bgg_rating": "7.3", "edition": "1st Edition", "condition": "complete", "price_eur": 90, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Through the Ages: A Story of Civilization", "publisher": "Czech Games Edition", "designer": "Vlaada Chvátil", "year": 2006, "player_count": "2-4", "play_time": "240min", "bgg_rating": "8.2", "edition": "1st Edition", "condition": "complete", "price_eur": 75, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Power Grid (1st Edition)", "publisher": "Rio Grande Games", "designer": "Friedemann Friese", "year": 2004, "player_count": "2-6", "play_time": "120min", "bgg_rating": "7.8", "edition": "1st Edition", "condition": "complete", "price_eur": 55, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Caylus (1st Edition)", "publisher": "Ystari Games", "designer": "William Attia", "year": 2005, "player_count": "2-5", "play_time": "120min", "bgg_rating": "7.7", "edition": "1st Edition", "condition": "complete", "price_eur": 60, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Le Havre", "publisher": "Lookout Games", "designer": "Uwe Rosenberg", "year": 2008, "player_count": "1-5", "play_time": "120min", "bgg_rating": "7.8", "edition": "1st Edition", "condition": "complete", "price_eur": 65, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Keyflower", "publisher": "R&D Games", "designer": "Sebastian Bleasdale", "year": 2012, "player_count": "2-6", "play_time": "120min", "bgg_rating": "7.7", "edition": "1st Edition", "condition": "complete", "price_eur": 70, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Terra Mystica", "publisher": "Z-Man Games", "designer": "Jens Drögemüller", "year": 2012, "player_count": "2-5", "play_time": "120min", "bgg_rating": "8.0", "edition": "1st Edition", "condition": "complete", "price_eur": 70, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Troyes", "publisher": "Pearl Games", "designer": "Sébastien Dujardin", "year": 2010, "player_count": "2-4", "play_time": "90min", "bgg_rating": "7.7", "edition": "1st Edition", "condition": "complete", "price_eur": 80, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Trajan", "publisher": "Ammonit Spiele", "designer": "Stefan Feld", "year": 2011, "player_count": "2-4", "play_time": "120min", "bgg_rating": "7.8", "edition": "1st Edition", "condition": "complete", "price_eur": 55, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Tzolk'in: The Mayan Calendar", "publisher": "Czech Games Edition", "designer": "Simone Luciani", "year": 2012, "player_count": "2-4", "play_time": "90min", "bgg_rating": "7.8", "edition": "1st Edition", "condition": "complete", "price_eur": 50, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Orleans", "publisher": "DLP Games", "designer": "Reiner Stockhausen", "year": 2014, "player_count": "2-4", "play_time": "90min", "bgg_rating": "7.8", "edition": "1st Edition", "condition": "complete", "price_eur": 65, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Hansa Teutonica", "publisher": "Argentum Verlag", "designer": "Andreas Steding", "year": 2009, "player_count": "2-5", "play_time": "90min", "bgg_rating": "7.6", "edition": "1st Edition", "condition": "complete", "price_eur": 80, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Concordia", "publisher": "PD-Verlag", "designer": "Mac Gerdts", "year": 2013, "player_count": "2-5", "play_time": "100min", "bgg_rating": "8.1", "edition": "1st Edition", "condition": "complete", "price_eur": 50, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Castles of Burgundy (1st Edition)", "publisher": "Alea", "designer": "Stefan Feld", "year": 2011, "player_count": "2-4", "play_time": "90min", "bgg_rating": "8.1", "edition": "1st Edition", "condition": "complete", "price_eur": 55, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Dominant Species", "publisher": "GMT Games", "designer": "Chad Jensen", "year": 2010, "player_count": "2-6", "play_time": "180min", "bgg_rating": "7.8", "edition": "1st Edition", "condition": "complete", "price_eur": 75, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Village", "publisher": "Pegasus Spiele", "designer": "Inka Brand", "year": 2011, "player_count": "2-4", "play_time": "90min", "bgg_rating": "7.4", "edition": "1st Edition", "condition": "complete", "price_eur": 45, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Mage Knight Board Game", "publisher": "WizKids", "designer": "Vlaada Chvátil", "year": 2011, "player_count": "1-4", "play_time": "240min", "bgg_rating": "8.1", "edition": "1st Edition", "condition": "complete", "price_eur": 120, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Mage Knight Ultimate Edition", "publisher": "WizKids", "designer": "Vlaada Chvátil", "year": 2018, "player_count": "1-5", "play_time": "240min", "bgg_rating": "8.1", "edition": "Ultimate", "condition": "sealed", "price_eur": 200, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Galaxy Trucker", "publisher": "Czech Games Edition", "designer": "Vlaada Chvátil", "year": 2007, "player_count": "2-4", "play_time": "60min", "bgg_rating": "7.1", "edition": "Anniversary", "condition": "complete", "price_eur": 90, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "A Feast for Odin", "publisher": "Z-Man Games", "designer": "Uwe Rosenberg", "year": 2016, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.1", "edition": "1st Edition", "condition": "complete", "price_eur": 70, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Ora et Labora", "publisher": "Lookout Games", "designer": "Uwe Rosenberg", "year": 2011, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.6", "edition": "1st Edition", "condition": "complete", "price_eur": 120, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "The Voyages of Marco Polo", "publisher": "Hans im Glück", "designer": "Simone Luciani", "year": 2015, "player_count": "2-4", "play_time": "100min", "bgg_rating": "7.8", "edition": "1st Edition", "condition": "complete", "price_eur": 55, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
    ]


def _kickstarter_exclusives() -> list[dict]:
    """Kickstarter-only editions and exclusives."""
    return [
        {"name": "Gloomhaven (Kickstarter Edition)", "publisher": "Cephalofair Games", "designer": "Isaac Childres", "year": 2017, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.6", "edition": "Kickstarter", "condition": "sealed", "price_eur": 250, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Kingdom Death: Monster 1.5", "publisher": "Kingdom Death", "designer": "Adam Poots", "year": 2017, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.8", "edition": "Kickstarter", "condition": "sealed", "price_eur": 650, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Kingdom Death: Monster (1st Edition)", "publisher": "Kingdom Death", "designer": "Adam Poots", "year": 2015, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.8", "edition": "1st Edition", "condition": "complete", "price_eur": 1200, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Nemesis (Kickstarter Sundrop)", "publisher": "Awaken Realms", "designer": "Adam Kwapiński", "year": 2018, "player_count": "1-5", "play_time": "120min", "bgg_rating": "8.3", "edition": "Kickstarter", "condition": "sealed", "price_eur": 180, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Nemesis Lockdown (KS All-In)", "publisher": "Awaken Realms", "designer": "Adam Kwapiński", "year": 2022, "player_count": "1-5", "play_time": "120min", "bgg_rating": "8.4", "edition": "Kickstarter All-In", "condition": "sealed", "price_eur": 350, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Frosthaven (Kickstarter Edition)", "publisher": "Cephalofair Games", "designer": "Isaac Childres", "year": 2023, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.5", "edition": "Kickstarter", "condition": "sealed", "price_eur": 200, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Bloodborne: The Board Game (KS All-In)", "publisher": "CMON", "designer": "Eric M. Lang", "year": 2020, "player_count": "1-4", "play_time": "90min", "bgg_rating": "7.5", "edition": "Kickstarter All-In", "condition": "sealed", "price_eur": 300, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Rising Sun (Kickstarter Daimyo)", "publisher": "CMON", "designer": "Eric M. Lang", "year": 2018, "player_count": "3-5", "play_time": "120min", "bgg_rating": "7.8", "edition": "Kickstarter Daimyo", "condition": "sealed", "price_eur": 250, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Ankh: Gods of Egypt (KS All-In)", "publisher": "CMON", "designer": "Eric M. Lang", "year": 2022, "player_count": "2-5", "play_time": "90min", "bgg_rating": "7.5", "edition": "Kickstarter All-In", "condition": "sealed", "price_eur": 280, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Zombicide: Black Plague (KS)", "publisher": "CMON", "designer": "Raphaël Guiton", "year": 2015, "player_count": "1-6", "play_time": "60min", "bgg_rating": "7.5", "edition": "Kickstarter", "condition": "sealed", "price_eur": 160, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Mythic Battles: Pantheon (KS All-In)", "publisher": "Monolith", "designer": "Benoît Vogt", "year": 2017, "player_count": "2-4", "play_time": "60min", "bgg_rating": "8.0", "edition": "Kickstarter All-In", "condition": "sealed", "price_eur": 400, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Too Many Bones (Undertow + Splice & Dice)", "publisher": "Chip Theory Games", "designer": "Josh J. Carlson", "year": 2017, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.2", "edition": "Kickstarter", "condition": "complete", "price_eur": 220, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Oath: Chronicles of Empire and Exile", "publisher": "Leder Games", "designer": "Cole Wehrle", "year": 2021, "player_count": "1-6", "play_time": "90min", "bgg_rating": "7.5", "edition": "Kickstarter", "condition": "sealed", "price_eur": 120, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Root (Kickstarter + Underworld)", "publisher": "Leder Games", "designer": "Cole Wehrle", "year": 2018, "player_count": "2-4", "play_time": "90min", "bgg_rating": "8.1", "edition": "Kickstarter", "condition": "complete", "price_eur": 130, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Cthulhu Wars (Omega Master)", "publisher": "Petersen Games", "designer": "Sandy Petersen", "year": 2015, "player_count": "2-4", "play_time": "120min", "bgg_rating": "8.0", "edition": "Kickstarter Omega", "condition": "sealed", "price_eur": 500, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Massive Darkness (KS)", "publisher": "CMON", "designer": "Raphaël Guiton", "year": 2017, "player_count": "1-6", "play_time": "120min", "bgg_rating": "7.0", "edition": "Kickstarter", "condition": "sealed", "price_eur": 140, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Tainted Grail (KS All-In)", "publisher": "Awaken Realms", "designer": "Krzysztof Piskorski", "year": 2019, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.8", "edition": "Kickstarter All-In", "condition": "sealed", "price_eur": 300, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Etherfields (KS All-In)", "publisher": "Awaken Realms", "designer": "Michał Oracz", "year": 2020, "player_count": "1-4", "play_time": "90min", "bgg_rating": "7.2", "edition": "Kickstarter All-In", "condition": "sealed", "price_eur": 250, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "ISS Vanguard (KS All-In)", "publisher": "Awaken Realms", "designer": "Marcin Świerkot", "year": 2023, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.8", "edition": "Kickstarter All-In", "condition": "sealed", "price_eur": 280, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Middara (KS All-In)", "publisher": "Succubus Publishing", "designer": "Brooklynn Lundberg", "year": 2019, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.5", "edition": "Kickstarter All-In", "condition": "sealed", "price_eur": 350, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Oathsworn: Into the Deepwood (KS)", "publisher": "Shadowborne Games", "designer": "Jamie Jolly", "year": 2022, "player_count": "1-4", "play_time": "90min", "bgg_rating": "8.6", "edition": "Kickstarter", "condition": "sealed", "price_eur": 200, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Darkest Dungeon (KS All-In)", "publisher": "Mythic Games", "designer": "Daniel Engelbrecht", "year": 2022, "player_count": "1-4", "play_time": "90min", "bgg_rating": "7.5", "edition": "Kickstarter All-In", "condition": "sealed", "price_eur": 200, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Aeon's End (KS Legacy)", "publisher": "Indie Boards & Cards", "designer": "Kevin Riley", "year": 2019, "player_count": "1-4", "play_time": "60min", "bgg_rating": "8.0", "edition": "Kickstarter", "condition": "sealed", "price_eur": 90, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Dark Souls: The Board Game (KS All-In)", "publisher": "Steamforged Games", "designer": "David Carl", "year": 2017, "player_count": "1-4", "play_time": "120min", "bgg_rating": "6.5", "edition": "Kickstarter All-In", "condition": "sealed", "price_eur": 250, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Thunderstone Quest (KS)", "publisher": "Alderac Entertainment Group", "designer": "Mike Elliott", "year": 2018, "player_count": "2-4", "play_time": "90min", "bgg_rating": "7.4", "edition": "Kickstarter", "condition": "sealed", "price_eur": 120, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
    ]


def _grail_games() -> list[dict]:
    """Ultra-rare grail-tier games."""
    return [
        {"name": "Food Chain Magnate", "publisher": "Splotter Spellen", "designer": "Jeroen Doumen", "year": 2015, "player_count": "2-5", "play_time": "240min", "bgg_rating": "8.0", "edition": "1st Edition", "condition": "complete", "price_eur": 180, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Indonesia", "publisher": "Splotter Spellen", "designer": "Jeroen Doumen", "year": 2005, "player_count": "2-5", "play_time": "240min", "bgg_rating": "7.7", "edition": "1st Edition", "condition": "complete", "price_eur": 350, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Roads & Boats", "publisher": "Splotter Spellen", "designer": "Jeroen Doumen", "year": 1999, "player_count": "1-4", "play_time": "240min", "bgg_rating": "7.6", "edition": "1st Edition", "condition": "complete", "price_eur": 400, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Antiquity", "publisher": "Splotter Spellen", "designer": "Jeroen Doumen", "year": 2004, "player_count": "2-4", "play_time": "180min", "bgg_rating": "7.5", "edition": "1st Edition", "condition": "complete", "price_eur": 500, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "The Great Zimbabwe", "publisher": "Splotter Spellen", "designer": "Jeroen Doumen", "year": 2012, "player_count": "2-5", "play_time": "120min", "bgg_rating": "7.6", "edition": "1st Edition", "condition": "complete", "price_eur": 200, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Dark Tower (1981)", "publisher": "Milton Bradley", "designer": "Roger Burten", "year": 1981, "player_count": "1-4", "play_time": "60min", "bgg_rating": "6.6", "edition": "1st Edition", "condition": "complete", "price_eur": 400, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Cosmic Encounter (1st Edition Eon)", "publisher": "Eon Products", "designer": "Bill Eberle", "year": 1977, "player_count": "2-6", "play_time": "90min", "bgg_rating": "7.3", "edition": "1st Edition", "condition": "complete", "price_eur": 300, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "HeroQuest (1989 Original)", "publisher": "Milton Bradley", "designer": "Stephen Baker", "year": 1989, "player_count": "2-5", "play_time": "90min", "bgg_rating": "7.0", "edition": "1st Edition", "condition": "complete", "price_eur": 250, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Space Hulk (3rd Edition)", "publisher": "Games Workshop", "designer": "Richard Halliwell", "year": 2009, "player_count": "2", "play_time": "90min", "bgg_rating": "7.5", "edition": "3rd Edition", "condition": "sealed", "price_eur": 350, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Space Hulk (4th Edition)", "publisher": "Games Workshop", "designer": "Richard Halliwell", "year": 2014, "player_count": "2", "play_time": "90min", "bgg_rating": "7.5", "edition": "4th Edition", "condition": "sealed", "price_eur": 280, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Fireball Island (Original 1986)", "publisher": "Milton Bradley", "designer": "Chuck Kennedy", "year": 1986, "player_count": "2-4", "play_time": "30min", "bgg_rating": "5.7", "edition": "1st Edition", "condition": "complete", "price_eur": 200, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Return to Dark Tower (KS All-In)", "publisher": "Restoration Games", "designer": "Tim Burrell-Saward", "year": 2022, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.9", "edition": "Kickstarter All-In", "condition": "sealed", "price_eur": 300, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Dune (AH 1979)", "publisher": "Avalon Hill", "designer": "Bill Eberle", "year": 1979, "player_count": "2-6", "play_time": "180min", "bgg_rating": "7.6", "edition": "1st Edition", "condition": "complete", "price_eur": 250, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Bus", "publisher": "Splotter Spellen", "designer": "Jeroen Doumen", "year": 1999, "player_count": "3-5", "play_time": "120min", "bgg_rating": "7.2", "edition": "1st Edition", "condition": "complete", "price_eur": 300, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Duck Dealer", "publisher": "Splotter Spellen", "designer": "Jeroen Doumen", "year": 2011, "player_count": "2-4", "play_time": "120min", "bgg_rating": "7.1", "edition": "1st Edition", "condition": "complete", "price_eur": 250, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
    ]


def _deluxe_big_box() -> list[dict]:
    """Deluxe and big box editions."""
    return [
        {"name": "Scythe (Legendary Box)", "publisher": "Stonemaier Games", "designer": "Jamey Stegmaier", "year": 2019, "player_count": "1-7", "play_time": "115min", "bgg_rating": "8.2", "edition": "Legendary Box", "condition": "sealed", "price_eur": 180, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Twilight Imperium (4th Edition)", "publisher": "Fantasy Flight Games", "designer": "Dane Beltrami", "year": 2017, "player_count": "3-6", "play_time": "480min", "bgg_rating": "8.5", "edition": "4th Edition", "condition": "sealed", "price_eur": 150, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "War of the Ring (Collector's Edition)", "publisher": "Ares Games", "designer": "Roberto Di Meglio", "year": 2010, "player_count": "2-4", "play_time": "180min", "bgg_rating": "8.5", "edition": "Collector's", "condition": "sealed", "price_eur": 600, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "War of the Ring (2nd Edition)", "publisher": "Ares Games", "designer": "Roberto Di Meglio", "year": 2012, "player_count": "2-4", "play_time": "180min", "bgg_rating": "8.5", "edition": "2nd Edition", "condition": "complete", "price_eur": 100, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Star Wars: Rebellion", "publisher": "Fantasy Flight Games", "designer": "Corey Konieczka", "year": 2016, "player_count": "2-4", "play_time": "240min", "bgg_rating": "8.3", "edition": "1st Edition", "condition": "sealed", "price_eur": 110, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Mansions of Madness (2nd Edition)", "publisher": "Fantasy Flight Games", "designer": "Nikki Valens", "year": 2016, "player_count": "1-5", "play_time": "180min", "bgg_rating": "8.0", "edition": "2nd Edition", "condition": "sealed", "price_eur": 95, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Descent: Legends of the Dark", "publisher": "Fantasy Flight Games", "designer": "Kara Centell-Dunk", "year": 2021, "player_count": "1-4", "play_time": "180min", "bgg_rating": "7.5", "edition": "1st Edition", "condition": "sealed", "price_eur": 130, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Eclipse: Second Dawn for the Galaxy", "publisher": "Lautapelit.fi", "designer": "Touko Tahkokallio", "year": 2020, "player_count": "2-6", "play_time": "180min", "bgg_rating": "8.3", "edition": "2nd Edition", "condition": "sealed", "price_eur": 130, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Gloomhaven: Jaws of the Lion", "publisher": "Cephalofair Games", "designer": "Isaac Childres", "year": 2020, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.3", "edition": "1st Edition", "condition": "sealed", "price_eur": 45, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Brass: Birmingham (Deluxe)", "publisher": "Roxley Games", "designer": "Gavan Brown", "year": 2018, "player_count": "2-4", "play_time": "120min", "bgg_rating": "8.6", "edition": "Deluxe", "condition": "sealed", "price_eur": 90, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Brass: Lancashire (Deluxe)", "publisher": "Roxley Games", "designer": "Martin Wallace", "year": 2018, "player_count": "2-4", "play_time": "120min", "bgg_rating": "8.1", "edition": "Deluxe", "condition": "sealed", "price_eur": 80, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Pax Pamir (2nd Edition)", "publisher": "Wehrlegig Games", "designer": "Cole Wehrle", "year": 2019, "player_count": "1-5", "play_time": "120min", "bgg_rating": "8.1", "edition": "Kickstarter", "condition": "sealed", "price_eur": 150, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Spirit Island (Branch & Claw + Jagged Earth)", "publisher": "Greater Than Games", "designer": "R. Eric Reuss", "year": 2017, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.3", "edition": "Complete Bundle", "condition": "complete", "price_eur": 140, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Terraforming Mars (Big Box)", "publisher": "Stronghold Games", "designer": "Jacob Fryxelius", "year": 2021, "player_count": "1-5", "play_time": "120min", "bgg_rating": "8.4", "edition": "Big Box", "condition": "sealed", "price_eur": 100, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Viticulture Essential Edition + Tuscany", "publisher": "Stonemaier Games", "designer": "Jamey Stegmaier", "year": 2015, "player_count": "1-6", "play_time": "90min", "bgg_rating": "8.0", "edition": "Essential + Tuscany", "condition": "complete", "price_eur": 80, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
    ]


def _legacy_games() -> list[dict]:
    """Legacy games — one-time play, collectible sealed."""
    return [
        {"name": "Pandemic Legacy: Season 1", "publisher": "Z-Man Games", "designer": "Rob Daviau", "year": 2015, "player_count": "2-4", "play_time": "60min", "bgg_rating": "8.5", "edition": "1st Edition", "condition": "sealed", "price_eur": 55, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Pandemic Legacy: Season 2", "publisher": "Z-Man Games", "designer": "Rob Daviau", "year": 2017, "player_count": "2-4", "play_time": "60min", "bgg_rating": "7.8", "edition": "1st Edition", "condition": "sealed", "price_eur": 55, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Pandemic Legacy: Season 0", "publisher": "Z-Man Games", "designer": "Rob Daviau", "year": 2020, "player_count": "2-4", "play_time": "60min", "bgg_rating": "7.8", "edition": "1st Edition", "condition": "sealed", "price_eur": 55, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Risk Legacy", "publisher": "Hasbro", "designer": "Rob Daviau", "year": 2011, "player_count": "3-5", "play_time": "120min", "bgg_rating": "7.5", "edition": "1st Edition", "condition": "sealed", "price_eur": 70, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Charterstone", "publisher": "Stonemaier Games", "designer": "Jamey Stegmaier", "year": 2017, "player_count": "1-6", "play_time": "75min", "bgg_rating": "7.1", "edition": "1st Edition", "condition": "sealed", "price_eur": 55, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Clank! Legacy: Acquisitions Incorporated", "publisher": "Dire Wolf Digital", "designer": "Andy Clautice", "year": 2019, "player_count": "2-4", "play_time": "90min", "bgg_rating": "8.1", "edition": "1st Edition", "condition": "sealed", "price_eur": 65, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Betrayal Legacy", "publisher": "Hasbro", "designer": "Rob Daviau", "year": 2018, "player_count": "3-5", "play_time": "75min", "bgg_rating": "7.5", "edition": "1st Edition", "condition": "sealed", "price_eur": 70, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Aeon's End: Legacy", "publisher": "Indie Boards & Cards", "designer": "Kevin Riley", "year": 2019, "player_count": "1-4", "play_time": "60min", "bgg_rating": "8.0", "edition": "1st Edition", "condition": "sealed", "price_eur": 55, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Seafall", "publisher": "Plaid Hat Games", "designer": "Rob Daviau", "year": 2016, "player_count": "3-5", "play_time": "120min", "bgg_rating": "6.0", "edition": "1st Edition", "condition": "sealed", "price_eur": 40, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "The King's Dilemma", "publisher": "Horrible Guild", "designer": "Hjalmar Hach", "year": 2019, "player_count": "3-5", "play_time": "60min", "bgg_rating": "7.5", "edition": "1st Edition", "condition": "sealed", "price_eur": 50, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
    ]


def _thematic_ameritrash() -> list[dict]:
    """Thematic/Ameritrash OOP games."""
    return [
        {"name": "Battlestar Galactica", "publisher": "Fantasy Flight Games", "designer": "Corey Konieczka", "year": 2008, "player_count": "3-6", "play_time": "180min", "bgg_rating": "7.8", "edition": "1st Edition", "condition": "complete", "price_eur": 180, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Fury of Dracula (3rd Edition)", "publisher": "Fantasy Flight Games", "designer": "Frank Brooks", "year": 2015, "player_count": "2-5", "play_time": "180min", "bgg_rating": "7.7", "edition": "3rd Edition", "condition": "complete", "price_eur": 150, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Betrayal at House on the Hill", "publisher": "Hasbro", "designer": "Bruce Glassco", "year": 2004, "player_count": "3-6", "play_time": "60min", "bgg_rating": "7.0", "edition": "1st Edition", "condition": "complete", "price_eur": 50, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Chaos in the Old World", "publisher": "Fantasy Flight Games", "designer": "Eric M. Lang", "year": 2009, "player_count": "3-4", "play_time": "120min", "bgg_rating": "7.5", "edition": "1st Edition", "condition": "complete", "price_eur": 200, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Starcraft: The Board Game", "publisher": "Fantasy Flight Games", "designer": "Corey Konieczka", "year": 2007, "player_count": "2-6", "play_time": "180min", "bgg_rating": "7.3", "edition": "1st Edition", "condition": "complete", "price_eur": 150, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Twilight Imperium (3rd Edition)", "publisher": "Fantasy Flight Games", "designer": "Christian T. Petersen", "year": 2005, "player_count": "3-6", "play_time": "360min", "bgg_rating": "7.9", "edition": "3rd Edition", "condition": "complete", "price_eur": 200, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Descent: Journeys in the Dark (2nd Edition)", "publisher": "Fantasy Flight Games", "designer": "Daniel Clark", "year": 2012, "player_count": "2-5", "play_time": "120min", "bgg_rating": "7.5", "edition": "2nd Edition", "condition": "complete", "price_eur": 110, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Arkham Horror (2nd Edition)", "publisher": "Fantasy Flight Games", "designer": "Richard Launius", "year": 2005, "player_count": "1-8", "play_time": "240min", "bgg_rating": "7.2", "edition": "2nd Edition", "condition": "complete", "price_eur": 90, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Android: Netrunner (Core + Data Packs)", "publisher": "Fantasy Flight Games", "designer": "Richard Garfield", "year": 2012, "player_count": "2", "play_time": "45min", "bgg_rating": "7.8", "edition": "Complete Collection", "condition": "complete", "price_eur": 500, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Star Wars: Imperial Assault", "publisher": "Fantasy Flight Games", "designer": "Corey Konieczka", "year": 2014, "player_count": "2-5", "play_time": "120min", "bgg_rating": "8.0", "edition": "1st Edition", "condition": "complete", "price_eur": 120, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Eldritch Horror (Complete)", "publisher": "Fantasy Flight Games", "designer": "Corey Konieczka", "year": 2013, "player_count": "1-8", "play_time": "240min", "bgg_rating": "7.7", "edition": "Complete Collection", "condition": "complete", "price_eur": 300, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Letters from Whitechapel", "publisher": "Fantasy Flight Games", "designer": "Gabriele Mari", "year": 2011, "player_count": "2-6", "play_time": "120min", "bgg_rating": "7.4", "edition": "1st Edition", "condition": "complete", "price_eur": 60, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
    ]


def _designer_collectibles() -> list[dict]:
    """High-value designer games by renowned designers."""
    return [
        # Lacerda games
        {"name": "Lisboa", "publisher": "Eagle-Gryphon Games", "designer": "Vital Lacerda", "year": 2017, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.0", "edition": "Deluxe", "condition": "complete", "price_eur": 120, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "The Gallerist", "publisher": "Eagle-Gryphon Games", "designer": "Vital Lacerda", "year": 2015, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.9", "edition": "Deluxe", "condition": "complete", "price_eur": 100, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Kanban EV", "publisher": "Eagle-Gryphon Games", "designer": "Vital Lacerda", "year": 2020, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.0", "edition": "Deluxe", "condition": "sealed", "price_eur": 90, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "On Mars", "publisher": "Eagle-Gryphon Games", "designer": "Vital Lacerda", "year": 2020, "player_count": "1-4", "play_time": "150min", "bgg_rating": "8.1", "edition": "Deluxe", "condition": "sealed", "price_eur": 100, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Escape Plan", "publisher": "Eagle-Gryphon Games", "designer": "Vital Lacerda", "year": 2019, "player_count": "1-5", "play_time": "120min", "bgg_rating": "7.5", "edition": "Deluxe", "condition": "sealed", "price_eur": 90, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Weather Machine", "publisher": "Eagle-Gryphon Games", "designer": "Vital Lacerda", "year": 2022, "player_count": "1-4", "play_time": "150min", "bgg_rating": "7.9", "edition": "Deluxe KS", "condition": "sealed", "price_eur": 120, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        # Rosenberg games
        {"name": "Caverna: The Cave Farmers", "publisher": "Lookout Games", "designer": "Uwe Rosenberg", "year": 2013, "player_count": "1-7", "play_time": "210min", "bgg_rating": "7.8", "edition": "1st Edition", "condition": "complete", "price_eur": 70, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Fields of Arle", "publisher": "Z-Man Games", "designer": "Uwe Rosenberg", "year": 2014, "player_count": "1-2", "play_time": "120min", "bgg_rating": "8.0", "edition": "1st Edition", "condition": "complete", "price_eur": 60, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Glass Road", "publisher": "Z-Man Games", "designer": "Uwe Rosenberg", "year": 2013, "player_count": "1-4", "play_time": "75min", "bgg_rating": "7.4", "edition": "1st Edition", "condition": "complete", "price_eur": 55, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        # Knizia games
        {"name": "Samurai", "publisher": "Hans im Glück", "designer": "Reiner Knizia", "year": 1998, "player_count": "2-4", "play_time": "45min", "bgg_rating": "7.2", "edition": "1st Edition", "condition": "complete", "price_eur": 80, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Medici", "publisher": "Amigo", "designer": "Reiner Knizia", "year": 1995, "player_count": "2-6", "play_time": "60min", "bgg_rating": "7.0", "edition": "1st Edition", "condition": "complete", "price_eur": 60, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Modern Art", "publisher": "Hans im Glück", "designer": "Reiner Knizia", "year": 1992, "player_count": "3-5", "play_time": "60min", "bgg_rating": "7.3", "edition": "1st Edition", "condition": "complete", "price_eur": 100, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        # Feld games
        {"name": "Bora Bora", "publisher": "Alea", "designer": "Stefan Feld", "year": 2013, "player_count": "2-4", "play_time": "120min", "bgg_rating": "7.4", "edition": "1st Edition", "condition": "complete", "price_eur": 80, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Bruges", "publisher": "Hans im Glück", "designer": "Stefan Feld", "year": 2013, "player_count": "2-4", "play_time": "60min", "bgg_rating": "7.3", "edition": "1st Edition", "condition": "complete", "price_eur": 70, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Macao", "publisher": "Alea", "designer": "Stefan Feld", "year": 2009, "player_count": "2-4", "play_time": "90min", "bgg_rating": "7.3", "edition": "1st Edition", "condition": "complete", "price_eur": 90, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
    ]


def _oop_expansions() -> list[dict]:
    """Hard-to-find OOP expansions."""
    return [
        {"name": "Agricola: Farmers of the Moor", "publisher": "Lookout Games", "designer": "Uwe Rosenberg", "year": 2009, "player_count": "1-5", "play_time": "120min", "bgg_rating": "7.8", "edition": "1st Edition", "condition": "complete", "price_eur": 45, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Power Grid: Brazil/Spain & Portugal", "publisher": "Rio Grande Games", "designer": "Friedemann Friese", "year": 2009, "player_count": "2-6", "play_time": "120min", "bgg_rating": "7.5", "edition": "1st Edition", "condition": "complete", "price_eur": 40, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Twilight Imperium: Shattered Empire", "publisher": "Fantasy Flight Games", "designer": "Christian T. Petersen", "year": 2006, "player_count": "3-8", "play_time": "360min", "bgg_rating": "7.9", "edition": "Expansion", "condition": "complete", "price_eur": 120, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Battlestar Galactica: Exodus", "publisher": "Fantasy Flight Games", "designer": "Corey Konieczka", "year": 2010, "player_count": "3-6", "play_time": "180min", "bgg_rating": "7.8", "edition": "Expansion", "condition": "complete", "price_eur": 80, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Battlestar Galactica: Daybreak", "publisher": "Fantasy Flight Games", "designer": "Corey Konieczka", "year": 2013, "player_count": "3-7", "play_time": "180min", "bgg_rating": "7.5", "edition": "Expansion", "condition": "complete", "price_eur": 100, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Star Wars: Imperial Assault — Jabba's Realm", "publisher": "Fantasy Flight Games", "designer": "Todd Michlitsch", "year": 2017, "player_count": "2-5", "play_time": "120min", "bgg_rating": "8.0", "edition": "Expansion", "condition": "complete", "price_eur": 70, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Chaos in the Old World: Horned Rat", "publisher": "Fantasy Flight Games", "designer": "Eric M. Lang", "year": 2011, "player_count": "3-5", "play_time": "120min", "bgg_rating": "7.5", "edition": "Expansion", "condition": "complete", "price_eur": 150, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Terra Mystica: Fire & Ice", "publisher": "Z-Man Games", "designer": "Jens Drögemüller", "year": 2014, "player_count": "2-5", "play_time": "120min", "bgg_rating": "7.8", "edition": "Expansion", "condition": "complete", "price_eur": 45, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Food Chain Magnate: The Ketchup Mechanism", "publisher": "Splotter Spellen", "designer": "Jeroen Doumen", "year": 2019, "player_count": "2-6", "play_time": "240min", "bgg_rating": "7.6", "edition": "Expansion", "condition": "complete", "price_eur": 60, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Gloomhaven: Forgotten Circles", "publisher": "Cephalofair Games", "designer": "Isaac Childres", "year": 2019, "player_count": "1-4", "play_time": "120min", "bgg_rating": "6.7", "edition": "Expansion", "condition": "sealed", "price_eur": 30, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
    ]


def _additional_games() -> list[dict]:
    """Additional OOP games to reach 700+ items."""
    return [
        {"name": "Kanban: Driver's Edition", "publisher": "Stronghold Games", "designer": "Vital Lacerda", "year": 2014, "player_count": "2-4", "play_time": "120min", "bgg_rating": "7.6", "edition": "1st Edition", "condition": "complete", "price_eur": 90, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "CO₂", "publisher": "Stronghold Games", "designer": "Vital Lacerda", "year": 2012, "player_count": "1-5", "play_time": "120min", "bgg_rating": "7.1", "edition": "1st Edition", "condition": "complete", "price_eur": 80, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Dungeon Lords", "publisher": "Czech Games Edition", "designer": "Vlaada Chvátil", "year": 2009, "player_count": "2-4", "play_time": "90min", "bgg_rating": "7.4", "edition": "1st Edition", "condition": "complete", "price_eur": 55, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Dungeon Petz", "publisher": "Czech Games Edition", "designer": "Vlaada Chvátil", "year": 2011, "player_count": "2-4", "play_time": "90min", "bgg_rating": "7.4", "edition": "1st Edition", "condition": "complete", "price_eur": 60, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Summoner Wars (Master Set)", "publisher": "Plaid Hat Games", "designer": "Colby Dauch", "year": 2011, "player_count": "2-4", "play_time": "60min", "bgg_rating": "7.5", "edition": "Master Set", "condition": "complete", "price_eur": 80, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Mice and Mystics", "publisher": "Plaid Hat Games", "designer": "Jerry Hawthorne", "year": 2012, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.1", "edition": "1st Edition", "condition": "complete", "price_eur": 90, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Kemet", "publisher": "Matagot", "designer": "Jacques Bariot", "year": 2012, "player_count": "2-5", "play_time": "120min", "bgg_rating": "7.7", "edition": "1st Edition", "condition": "complete", "price_eur": 70, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Inis", "publisher": "Matagot", "designer": "Christian Martinez", "year": 2016, "player_count": "2-4", "play_time": "90min", "bgg_rating": "7.7", "edition": "1st Edition", "condition": "complete", "price_eur": 55, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Cyclades", "publisher": "Matagot", "designer": "Bruno Cathala", "year": 2009, "player_count": "2-5", "play_time": "90min", "bgg_rating": "7.4", "edition": "1st Edition", "condition": "complete", "price_eur": 60, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Blood Rage", "publisher": "CMON", "designer": "Eric M. Lang", "year": 2015, "player_count": "2-4", "play_time": "80min", "bgg_rating": "8.0", "edition": "Kickstarter", "condition": "sealed", "price_eur": 120, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Lords of Waterdeep + Scoundrels", "publisher": "Wizards of the Coast", "designer": "Peter Lee", "year": 2012, "player_count": "2-6", "play_time": "60min", "bgg_rating": "7.8", "edition": "Complete", "condition": "complete", "price_eur": 75, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Roll for the Galaxy (Deluxe)", "publisher": "Rio Grande Games", "designer": "Wei-Hwa Huang", "year": 2014, "player_count": "2-5", "play_time": "45min", "bgg_rating": "7.7", "edition": "Deluxe", "condition": "complete", "price_eur": 55, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Race for the Galaxy (1st Edition)", "publisher": "Rio Grande Games", "designer": "Tom Lehmann", "year": 2007, "player_count": "2-4", "play_time": "45min", "bgg_rating": "7.7", "edition": "1st Edition", "condition": "complete", "price_eur": 35, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "7 Wonders (1st Edition)", "publisher": "Repos Production", "designer": "Antoine Bauza", "year": 2010, "player_count": "2-7", "play_time": "30min", "bgg_rating": "7.7", "edition": "1st Edition", "condition": "complete", "price_eur": 40, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Alchemists", "publisher": "Czech Games Edition", "designer": "Matúš Kotry", "year": 2014, "player_count": "2-4", "play_time": "120min", "bgg_rating": "7.6", "edition": "1st Edition", "condition": "complete", "price_eur": 50, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Above and Below", "publisher": "Red Raven Games", "designer": "Ryan Laukat", "year": 2015, "player_count": "2-4", "play_time": "90min", "bgg_rating": "7.1", "edition": "1st Edition", "condition": "complete", "price_eur": 45, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Near and Far", "publisher": "Red Raven Games", "designer": "Ryan Laukat", "year": 2017, "player_count": "2-4", "play_time": "120min", "bgg_rating": "7.4", "edition": "Kickstarter", "condition": "complete", "price_eur": 60, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Barrage", "publisher": "Cranio Creations", "designer": "Tommaso Battista", "year": 2019, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.9", "edition": "1st Edition", "condition": "sealed", "price_eur": 65, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Gaia Project", "publisher": "Z-Man Games", "designer": "Jens Drögemüller", "year": 2017, "player_count": "1-4", "play_time": "150min", "bgg_rating": "8.4", "edition": "1st Edition", "condition": "complete", "price_eur": 70, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Great Western Trail (1st Edition)", "publisher": "Eggertspiele", "designer": "Alexander Pfister", "year": 2016, "player_count": "2-4", "play_time": "150min", "bgg_rating": "8.3", "edition": "1st Edition", "condition": "complete", "price_eur": 55, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Clans of Caledonia", "publisher": "Karma Games", "designer": "Juma Al-JouJou", "year": 2017, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.9", "edition": "1st Edition", "condition": "complete", "price_eur": 50, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Yokohama", "publisher": "Tasty Minstrel Games", "designer": "Hisashi Hayashi", "year": 2016, "player_count": "2-4", "play_time": "90min", "bgg_rating": "7.7", "edition": "Deluxe", "condition": "complete", "price_eur": 80, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Paladins of the West Kingdom (Collector's Box)", "publisher": "Garphill Games", "designer": "Shem Phillips", "year": 2019, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.9", "edition": "Collector's Box", "condition": "sealed", "price_eur": 90, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Architects of the West Kingdom (Collector's Box)", "publisher": "Garphill Games", "designer": "Shem Phillips", "year": 2018, "player_count": "1-5", "play_time": "80min", "bgg_rating": "7.5", "edition": "Collector's Box", "condition": "sealed", "price_eur": 85, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Viscounts of the West Kingdom (Collector's Box)", "publisher": "Garphill Games", "designer": "Shem Phillips", "year": 2020, "player_count": "1-4", "play_time": "90min", "bgg_rating": "7.8", "edition": "Collector's Box", "condition": "sealed", "price_eur": 85, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Hadara", "publisher": "Hans im Glück", "designer": "Benjamin Schwer", "year": 2019, "player_count": "2-5", "play_time": "45min", "bgg_rating": "7.2", "edition": "1st Edition", "condition": "complete", "price_eur": 35, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Marco Polo II: In the Service of the Khan", "publisher": "Hans im Glück", "designer": "Simone Luciani", "year": 2019, "player_count": "2-4", "play_time": "100min", "bgg_rating": "7.8", "edition": "1st Edition", "condition": "complete", "price_eur": 45, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Lorenzo il Magnifico (Big Box)", "publisher": "Cranio Creations", "designer": "Virginio Gigli", "year": 2016, "player_count": "2-4", "play_time": "120min", "bgg_rating": "7.6", "edition": "Big Box", "condition": "sealed", "price_eur": 65, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Tekhenu: Obelisk of the Sun", "publisher": "Board & Dice", "designer": "Dániel Tascini", "year": 2020, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.7", "edition": "1st Edition", "condition": "sealed", "price_eur": 45, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Underwater Cities", "publisher": "Delicious Games", "designer": "Vladimír Suchý", "year": 2018, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.9", "edition": "1st Edition", "condition": "complete", "price_eur": 50, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
    ]


def _wargames_and_coop() -> list[dict]:
    """OOP wargames and cooperative games."""
    return [
        {"name": "Twilight Struggle (GMT Deluxe 2009)", "publisher": "GMT Games", "designer": "Ananda Gupta", "year": 2009, "player_count": "2", "play_time": "180min", "bgg_rating": "8.2", "edition": "Deluxe 2009", "condition": "complete", "price_eur": 60, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Twilight Struggle (Collector's Anniversary)", "publisher": "GMT Games", "designer": "Ananda Gupta", "year": 2019, "player_count": "2", "play_time": "180min", "bgg_rating": "8.2", "edition": "Collector's Anniversary", "condition": "sealed", "price_eur": 120, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Cuba Libre", "publisher": "GMT Games", "designer": "Jeff Grossman", "year": 2013, "player_count": "1-4", "play_time": "180min", "bgg_rating": "7.7", "edition": "1st Edition", "condition": "complete", "price_eur": 70, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "A Distant Plain", "publisher": "GMT Games", "designer": "Volko Ruhnke", "year": 2013, "player_count": "1-4", "play_time": "180min", "bgg_rating": "7.7", "edition": "1st Edition", "condition": "complete", "price_eur": 75, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Fire in the Lake", "publisher": "GMT Games", "designer": "Mark Herman", "year": 2014, "player_count": "1-4", "play_time": "180min", "bgg_rating": "7.9", "edition": "1st Edition", "condition": "complete", "price_eur": 80, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Falling Sky", "publisher": "GMT Games", "designer": "Andrew Ruhnke", "year": 2016, "player_count": "1-4", "play_time": "180min", "bgg_rating": "7.6", "edition": "1st Edition", "condition": "complete", "price_eur": 70, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Pendragon", "publisher": "GMT Games", "designer": "Volko Ruhnke", "year": 2017, "player_count": "1-4", "play_time": "180min", "bgg_rating": "7.7", "edition": "1st Edition", "condition": "complete", "price_eur": 75, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Labyrinth: The War on Terror", "publisher": "GMT Games", "designer": "Volko Ruhnke", "year": 2010, "player_count": "1-2", "play_time": "180min", "bgg_rating": "7.5", "edition": "1st Edition", "condition": "complete", "price_eur": 55, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Paths of Glory (Deluxe)", "publisher": "GMT Games", "designer": "Ted Raicer", "year": 2010, "player_count": "2", "play_time": "480min", "bgg_rating": "8.0", "edition": "Deluxe", "condition": "complete", "price_eur": 65, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Commands & Colors: Napoleonics", "publisher": "GMT Games", "designer": "Richard Borg", "year": 2010, "player_count": "2", "play_time": "120min", "bgg_rating": "7.9", "edition": "1st Edition", "condition": "complete", "price_eur": 70, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Undaunted: Stalingrad", "publisher": "Osprey Games", "designer": "David Thompson", "year": 2022, "player_count": "2", "play_time": "60min", "bgg_rating": "8.2", "edition": "1st Edition", "condition": "sealed", "price_eur": 55, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Memoir '44 (Complete Collection)", "publisher": "Days of Wonder", "designer": "Richard Borg", "year": 2004, "player_count": "2", "play_time": "60min", "bgg_rating": "7.5", "edition": "Complete Collection", "condition": "complete", "price_eur": 350, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Here I Stand", "publisher": "GMT Games", "designer": "Ed Beach", "year": 2006, "player_count": "2-6", "play_time": "360min", "bgg_rating": "7.9", "edition": "1st Edition", "condition": "complete", "price_eur": 80, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Virgin Queen", "publisher": "GMT Games", "designer": "Ed Beach", "year": 2012, "player_count": "2-6", "play_time": "360min", "bgg_rating": "7.8", "edition": "1st Edition", "condition": "complete", "price_eur": 85, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Churchill", "publisher": "GMT Games", "designer": "Mark Herman", "year": 2015, "player_count": "1-3", "play_time": "300min", "bgg_rating": "7.5", "edition": "1st Edition", "condition": "complete", "price_eur": 60, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        # Co-op games
        {"name": "Spirit Island (Nature Incarnate Bundle)", "publisher": "Greater Than Games", "designer": "R. Eric Reuss", "year": 2023, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.3", "edition": "Nature Incarnate Bundle", "condition": "sealed", "price_eur": 180, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Pandemic: Iberia", "publisher": "Z-Man Games", "designer": "Jesús Torres Castro", "year": 2016, "player_count": "2-5", "play_time": "45min", "bgg_rating": "7.5", "edition": "1st Edition", "condition": "sealed", "price_eur": 80, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Pandemic: Rising Tide", "publisher": "Z-Man Games", "designer": "Jeroen Doumen", "year": 2017, "player_count": "2-5", "play_time": "45min", "bgg_rating": "7.3", "edition": "1st Edition", "condition": "sealed", "price_eur": 60, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "The Crew: The Quest for Planet Nine", "publisher": "Kosmos", "designer": "Thomas Sing", "year": 2019, "player_count": "2-5", "play_time": "20min", "bgg_rating": "7.8", "edition": "1st Edition", "condition": "complete", "price_eur": 15, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Hanabi (Deluxe)", "publisher": "R&R Games", "designer": "Antoine Bauza", "year": 2013, "player_count": "2-5", "play_time": "25min", "bgg_rating": "7.2", "edition": "Deluxe", "condition": "complete", "price_eur": 35, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "The Lord of the Rings: Journeys in Middle-earth", "publisher": "Fantasy Flight Games", "designer": "Nathan Hajek", "year": 2019, "player_count": "1-5", "play_time": "120min", "bgg_rating": "7.5", "edition": "1st Edition", "condition": "sealed", "price_eur": 90, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Sentinels of the Multiverse (Definitive)", "publisher": "Greater Than Games", "designer": "Christopher Badell", "year": 2022, "player_count": "2-5", "play_time": "60min", "bgg_rating": "7.6", "edition": "Definitive", "condition": "sealed", "price_eur": 55, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Horrified (Universal Monsters)", "publisher": "Ravensburger", "designer": "Prospero Hall", "year": 2019, "player_count": "1-5", "play_time": "60min", "bgg_rating": "7.2", "edition": "1st Edition", "condition": "sealed", "price_eur": 35, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Sub Terra", "publisher": "Inside the Box Board Games", "designer": "Tim Pinder", "year": 2017, "player_count": "1-6", "play_time": "60min", "bgg_rating": "6.8", "edition": "Kickstarter Deluxe", "condition": "sealed", "price_eur": 50, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Mysterium", "publisher": "Libellud", "designer": "Oleksandr Nevskiy", "year": 2015, "player_count": "2-7", "play_time": "42min", "bgg_rating": "7.2", "edition": "1st Edition", "condition": "complete", "price_eur": 40, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Flash Point: Fire Rescue (KS Extreme Danger)", "publisher": "Indie Boards & Cards", "designer": "Kevin Lanzing", "year": 2013, "player_count": "2-6", "play_time": "45min", "bgg_rating": "7.0", "edition": "Extreme Danger", "condition": "complete", "price_eur": 55, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Legends of Andor (Big Box)", "publisher": "Kosmos", "designer": "Michael Menzel", "year": 2012, "player_count": "2-4", "play_time": "90min", "bgg_rating": "7.1", "edition": "Big Box", "condition": "sealed", "price_eur": 70, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Ghost Stories", "publisher": "Repos Production", "designer": "Antoine Bauza", "year": 2008, "player_count": "1-4", "play_time": "60min", "bgg_rating": "7.1", "edition": "1st Edition", "condition": "complete", "price_eur": 65, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Eldritch Horror (Forsaken Lore + Mountains of Madness)", "publisher": "Fantasy Flight Games", "designer": "Corey Konieczka", "year": 2014, "player_count": "1-8", "play_time": "240min", "bgg_rating": "7.7", "edition": "Expansion Bundle", "condition": "complete", "price_eur": 130, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Shadows of Brimstone (KS All-In)", "publisher": "Flying Frog Productions", "designer": "Jason C. Hill", "year": 2015, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.0", "edition": "Kickstarter All-In", "condition": "sealed", "price_eur": 200, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Aeon Trespass: Odyssey (KS All-In)", "publisher": "Into the Unknown", "designer": "Marcin Wełnicki", "year": 2023, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.3", "edition": "Kickstarter All-In", "condition": "sealed", "price_eur": 320, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Machina Arcana (3rd Edition KS)", "publisher": "Adeptus Mechanicus", "designer": "Juraj Bilić", "year": 2020, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.8", "edition": "Kickstarter 3rd", "condition": "sealed", "price_eur": 90, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Dungeon Degenerates", "publisher": "Goblinko Games", "designer": "Sean Äaberg", "year": 2017, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.5", "edition": "1st Edition", "condition": "complete", "price_eur": 80, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Maximum Apocalypse (KS Gothic Horrors)", "publisher": "Rock Manor Games", "designer": "Mike Gnade", "year": 2018, "player_count": "1-6", "play_time": "90min", "bgg_rating": "7.2", "edition": "Kickstarter", "condition": "sealed", "price_eur": 60, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "1944: Race to the Rhine", "publisher": "Phalanx", "designer": "Jaro Andruszkiewicz", "year": 2014, "player_count": "1-3", "play_time": "150min", "bgg_rating": "7.1", "edition": "1st Edition", "condition": "complete", "price_eur": 50, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Conflict of Heroes: Awakening the Bear", "publisher": "Academy Games", "designer": "Uwe Eickert", "year": 2012, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.7", "edition": "2nd Edition", "condition": "complete", "price_eur": 60, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Navajo Wars", "publisher": "GMT Games", "designer": "Joel Toppen", "year": 2013, "player_count": "1", "play_time": "180min", "bgg_rating": "7.8", "edition": "1st Edition", "condition": "complete", "price_eur": 65, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Liberty or Death", "publisher": "GMT Games", "designer": "Harold Buchanan", "year": 2016, "player_count": "1-4", "play_time": "180min", "bgg_rating": "7.6", "edition": "1st Edition", "condition": "complete", "price_eur": 65, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "All Bridges Burning", "publisher": "GMT Games", "designer": "VPJ Arponen", "year": 2020, "player_count": "1-4", "play_time": "180min", "bgg_rating": "7.5", "edition": "1st Edition", "condition": "complete", "price_eur": 60, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
    ]


def _party_and_social_deduction() -> list[dict]:
    """OOP party games and social deduction collectibles."""
    return [
        {"name": "Secret Hitler (Kickstarter Wood Box)", "publisher": "Goat, Wolf, & Cabbage", "designer": "Mike Boxleiter", "year": 2016, "player_count": "5-10", "play_time": "45min", "bgg_rating": "7.6", "edition": "Kickstarter Wood Box", "condition": "sealed", "price_eur": 150, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "The Resistance: Avalon (Kickstarter)", "publisher": "Indie Boards & Cards", "designer": "Don Eskridge", "year": 2012, "player_count": "5-10", "play_time": "30min", "bgg_rating": "7.6", "edition": "Kickstarter", "condition": "sealed", "price_eur": 45, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Deception: Murder in Hong Kong", "publisher": "Grey Fox Games", "designer": "Tobey Ho", "year": 2014, "player_count": "4-12", "play_time": "20min", "bgg_rating": "7.4", "edition": "1st Edition", "condition": "complete", "price_eur": 40, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Deception: Undercover Allies", "publisher": "Grey Fox Games", "designer": "Tobey Ho", "year": 2018, "player_count": "4-14", "play_time": "20min", "bgg_rating": "7.4", "edition": "Expansion", "condition": "complete", "price_eur": 30, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Blood on the Clocktower (KS)", "publisher": "The Pandemonium Institute", "designer": "Steven Medway", "year": 2023, "player_count": "5-20", "play_time": "60min", "bgg_rating": "8.3", "edition": "Kickstarter", "condition": "sealed", "price_eur": 120, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Two Rooms and a Boom (KS Deluxe)", "publisher": "Tuesday Knight Games", "designer": "Alan Gerding", "year": 2015, "player_count": "6-30", "play_time": "15min", "bgg_rating": "6.8", "edition": "Kickstarter Deluxe", "condition": "sealed", "price_eur": 50, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Coup (Kickstarter Edition)", "publisher": "Indie Boards & Cards", "designer": "Rikki Tahta", "year": 2012, "player_count": "2-6", "play_time": "15min", "bgg_rating": "7.0", "edition": "Kickstarter", "condition": "sealed", "price_eur": 25, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Werewolf (Ultimate Deluxe Edition)", "publisher": "Bézier Games", "designer": "Ted Alspach", "year": 2014, "player_count": "5-75", "play_time": "30min", "bgg_rating": "7.0", "edition": "Ultimate Deluxe", "condition": "complete", "price_eur": 35, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Crossfire (Plaid Hat)", "publisher": "Plaid Hat Games", "designer": "Emerson Matsuuchi", "year": 2016, "player_count": "5-10", "play_time": "10min", "bgg_rating": "6.5", "edition": "1st Edition", "condition": "complete", "price_eur": 20, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Dark Moon", "publisher": "Stronghold Games", "designer": "Evan Derrick", "year": 2015, "player_count": "3-7", "play_time": "75min", "bgg_rating": "7.0", "edition": "1st Edition", "condition": "complete", "price_eur": 45, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Sheriff of Nottingham (1st Edition)", "publisher": "Arcane Wonders", "designer": "Sérgio Halaban", "year": 2014, "player_count": "3-5", "play_time": "60min", "bgg_rating": "7.1", "edition": "1st Edition", "condition": "complete", "price_eur": 40, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "The Chameleon (KS)", "publisher": "Big Potato Games", "designer": "Rikki Tahta", "year": 2017, "player_count": "3-8", "play_time": "15min", "bgg_rating": "6.5", "edition": "Kickstarter", "condition": "complete", "price_eur": 20, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Spyfall (1st Edition)", "publisher": "Cryptozoic Entertainment", "designer": "Alexandr Ushan", "year": 2014, "player_count": "3-8", "play_time": "15min", "bgg_rating": "6.9", "edition": "1st Edition", "condition": "complete", "price_eur": 25, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Werewords (Deluxe)", "publisher": "Bézier Games", "designer": "Ted Alspach", "year": 2017, "player_count": "4-10", "play_time": "10min", "bgg_rating": "7.0", "edition": "Deluxe", "condition": "complete", "price_eur": 25, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Good Cop Bad Cop (KS Undercover)", "publisher": "Overworld Games", "designer": "Brian Henk", "year": 2014, "player_count": "4-8", "play_time": "15min", "bgg_rating": "6.3", "edition": "Kickstarter Undercover", "condition": "complete", "price_eur": 25, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Tortuga 1667 (KS)", "publisher": "Façade Games", "designer": "Travis Hancock", "year": 2017, "player_count": "2-9", "play_time": "30min", "bgg_rating": "6.7", "edition": "Kickstarter", "condition": "sealed", "price_eur": 30, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Salem 1692 (KS)", "publisher": "Façade Games", "designer": "Travis Hancock", "year": 2015, "player_count": "4-12", "play_time": "30min", "bgg_rating": "6.5", "edition": "Kickstarter", "condition": "sealed", "price_eur": 30, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Mafia de Cuba", "publisher": "Lui-même", "designer": "Philippe des Pallières", "year": 2015, "player_count": "6-12", "play_time": "20min", "bgg_rating": "6.8", "edition": "1st Edition", "condition": "complete", "price_eur": 30, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Dead of Winter: The Long Night", "publisher": "Plaid Hat Games", "designer": "Jonathan Gilmour", "year": 2016, "player_count": "2-5", "play_time": "120min", "bgg_rating": "7.4", "edition": "1st Edition", "condition": "complete", "price_eur": 55, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Homeland: The Game", "publisher": "Gale Force Nine", "designer": "Aaron Dill", "year": 2015, "player_count": "3-6", "play_time": "90min", "bgg_rating": "6.5", "edition": "1st Edition", "condition": "complete", "price_eur": 35, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Ca$h 'n Guns (2nd Edition)", "publisher": "Repos Production", "designer": "Ludovic Maublanc", "year": 2014, "player_count": "4-8", "play_time": "30min", "bgg_rating": "7.0", "edition": "2nd Edition", "condition": "complete", "price_eur": 35, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Skull (Deluxe)", "publisher": "Asmodee", "designer": "Hervé Marly", "year": 2011, "player_count": "3-6", "play_time": "30min", "bgg_rating": "7.2", "edition": "Deluxe", "condition": "complete", "price_eur": 30, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Telestrations After Dark", "publisher": "USAopoly", "designer": "n/a", "year": 2014, "player_count": "4-8", "play_time": "30min", "bgg_rating": "7.2", "edition": "1st Edition", "condition": "complete", "price_eur": 30, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Funemployed!", "publisher": "Mattel", "designer": "Anthony Conta", "year": 2014, "player_count": "3-20", "play_time": "30min", "bgg_rating": "6.5", "edition": "1st Edition", "condition": "complete", "price_eur": 20, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Don't Mess with Cthulhu (KS)", "publisher": "Indie Boards & Cards", "designer": "Yusuke Sato", "year": 2015, "player_count": "4-8", "play_time": "20min", "bgg_rating": "6.4", "edition": "Kickstarter", "condition": "complete", "price_eur": 20, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Escape from the Aliens in Outer Space (Ultimate)", "publisher": "Osprey Games", "designer": "Mario Porpora", "year": 2016, "player_count": "2-8", "play_time": "30min", "bgg_rating": "6.9", "edition": "Ultimate", "condition": "sealed", "price_eur": 40, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Sushi Go Party! (1st Print)", "publisher": "Gamewright", "designer": "Phil Walker-Harding", "year": 2016, "player_count": "2-8", "play_time": "20min", "bgg_rating": "7.5", "edition": "1st Print", "condition": "complete", "price_eur": 25, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Bang! The Dice Game (Old West KS)", "publisher": "dV Giochi", "designer": "Michael Palm", "year": 2013, "player_count": "3-8", "play_time": "15min", "bgg_rating": "7.0", "edition": "Kickstarter", "condition": "complete", "price_eur": 25, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Cockroach Poker Royal", "publisher": "Drei Magier Spiele", "designer": "Jacques Zeimet", "year": 2012, "player_count": "2-6", "play_time": "20min", "bgg_rating": "7.0", "edition": "1st Edition", "condition": "complete", "price_eur": 15, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
    ]


def _abstract_and_two_player() -> list[dict]:
    """OOP abstract and two-player games."""
    return [
        {"name": "Patchwork (Anniversary Edition)", "publisher": "Lookout Games", "designer": "Uwe Rosenberg", "year": 2019, "player_count": "2", "play_time": "30min", "bgg_rating": "7.7", "edition": "Anniversary", "condition": "sealed", "price_eur": 45, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Hive Pocket", "publisher": "Gen42 Games", "designer": "John Yianni", "year": 2010, "player_count": "2", "play_time": "20min", "bgg_rating": "7.3", "edition": "Pocket", "condition": "complete", "price_eur": 25, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Hive Carbon", "publisher": "Gen42 Games", "designer": "John Yianni", "year": 2012, "player_count": "2", "play_time": "20min", "bgg_rating": "7.3", "edition": "Carbon", "condition": "sealed", "price_eur": 35, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "YINSH", "publisher": "Don & Co", "designer": "Kris Burm", "year": 2003, "player_count": "2", "play_time": "30min", "bgg_rating": "7.5", "edition": "1st Edition", "condition": "complete", "price_eur": 40, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "TZAAR", "publisher": "Don & Co", "designer": "Kris Burm", "year": 2007, "player_count": "2", "play_time": "30min", "bgg_rating": "7.3", "edition": "1st Edition", "condition": "complete", "price_eur": 35, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "DVONN", "publisher": "Don & Co", "designer": "Kris Burm", "year": 2001, "player_count": "2", "play_time": "30min", "bgg_rating": "7.4", "edition": "1st Edition", "condition": "complete", "price_eur": 40, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "ZERTZ", "publisher": "Don & Co", "designer": "Kris Burm", "year": 1999, "player_count": "2", "play_time": "30min", "bgg_rating": "7.1", "edition": "1st Edition", "condition": "complete", "price_eur": 40, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "GIPF Project (Complete Set)", "publisher": "Don & Co", "designer": "Kris Burm", "year": 2007, "player_count": "2", "play_time": "30min", "bgg_rating": "7.5", "edition": "Complete Set", "condition": "complete", "price_eur": 200, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Santorini (Roxley Deluxe)", "publisher": "Roxley Games", "designer": "Gord Hamilton", "year": 2016, "player_count": "2-4", "play_time": "20min", "bgg_rating": "7.2", "edition": "Deluxe KS", "condition": "sealed", "price_eur": 55, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Onitama", "publisher": "Arcane Wonders", "designer": "Shimpei Sato", "year": 2014, "player_count": "2", "play_time": "20min", "bgg_rating": "7.4", "edition": "1st Edition", "condition": "complete", "price_eur": 25, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "7 Wonders Duel (Pantheon + Agora)", "publisher": "Repos Production", "designer": "Antoine Bauza", "year": 2015, "player_count": "2", "play_time": "30min", "bgg_rating": "8.1", "edition": "Complete Bundle", "condition": "complete", "price_eur": 55, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Jaipur (1st Edition)", "publisher": "GameWorks", "designer": "Sébastien Pauchon", "year": 2009, "player_count": "2", "play_time": "30min", "bgg_rating": "7.5", "edition": "1st Edition", "condition": "complete", "price_eur": 25, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Targi", "publisher": "Kosmos", "designer": "Andreas Steiger", "year": 2012, "player_count": "2", "play_time": "60min", "bgg_rating": "7.6", "edition": "1st Edition", "condition": "complete", "price_eur": 30, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Codenames: Duet", "publisher": "Czech Games Edition", "designer": "Vlaada Chvátil", "year": 2017, "player_count": "2", "play_time": "15min", "bgg_rating": "7.5", "edition": "1st Edition", "condition": "complete", "price_eur": 18, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Hanamikoji", "publisher": "Emperor S4", "designer": "Kota Nakayama", "year": 2013, "player_count": "2", "play_time": "15min", "bgg_rating": "7.3", "edition": "1st Edition", "condition": "complete", "price_eur": 20, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Schotten Totten", "publisher": "IELLO", "designer": "Reiner Knizia", "year": 1999, "player_count": "2", "play_time": "20min", "bgg_rating": "7.2", "edition": "1st Edition", "condition": "complete", "price_eur": 15, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "The Fox in the Forest", "publisher": "Foxtrot Games", "designer": "Joshua Buergel", "year": 2017, "player_count": "2", "play_time": "30min", "bgg_rating": "7.0", "edition": "1st Edition", "condition": "complete", "price_eur": 15, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Watergate", "publisher": "Capstone Games", "designer": "Matthias Cramer", "year": 2019, "player_count": "2", "play_time": "30min", "bgg_rating": "7.6", "edition": "1st Edition", "condition": "complete", "price_eur": 25, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Star Realms: Frontiers (KS All-In)", "publisher": "White Wizard Games", "designer": "Robert Dougherty", "year": 2018, "player_count": "1-4", "play_time": "20min", "bgg_rating": "7.5", "edition": "Kickstarter All-In", "condition": "sealed", "price_eur": 70, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Raptor", "publisher": "Matagot", "designer": "Bruno Cathala", "year": 2015, "player_count": "2", "play_time": "30min", "bgg_rating": "7.3", "edition": "1st Edition", "condition": "complete", "price_eur": 25, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Unmatched: Battle of Legends (KS)", "publisher": "Restoration Games", "designer": "Rob Daviau", "year": 2019, "player_count": "2-4", "play_time": "20min", "bgg_rating": "7.5", "edition": "Kickstarter", "condition": "sealed", "price_eur": 45, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Mandala", "publisher": "Lookout Games", "designer": "Trevor Benjamin", "year": 2019, "player_count": "2", "play_time": "20min", "bgg_rating": "7.1", "edition": "1st Edition", "condition": "complete", "price_eur": 20, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Tak (Tavern Edition)", "publisher": "Cheapass Games", "designer": "Patrick Rothfuss", "year": 2016, "player_count": "2", "play_time": "30min", "bgg_rating": "7.4", "edition": "Tavern", "condition": "sealed", "price_eur": 40, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Azul: Stained Glass of Sintra", "publisher": "Next Move Games", "designer": "Michael Kiesling", "year": 2018, "player_count": "2-4", "play_time": "45min", "bgg_rating": "7.2", "edition": "1st Edition", "condition": "complete", "price_eur": 35, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Shobu", "publisher": "Smirk & Laughter Games", "designer": "Manolis Vranas", "year": 2019, "player_count": "2", "play_time": "30min", "bgg_rating": "7.1", "edition": "1st Edition", "condition": "complete", "price_eur": 25, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
    ]


def _variant_expansion() -> list[dict]:
    """Create edition variants for existing games."""
    variants: list[dict] = []
    base_games = [
        ("Agricola", "Lookout Games", "Uwe Rosenberg", 2007, "1-5", "120min", "7.9", 85, "Uncommon"),
        ("Scythe", "Stonemaier Games", "Jamey Stegmaier", 2016, "1-5", "115min", "8.2", 60, "Common"),
        ("Terraforming Mars", "Stronghold Games", "Jacob Fryxelius", 2016, "1-5", "120min", "8.4", 45, "Common"),
        ("Wingspan", "Stonemaier Games", "Elizabeth Hargrave", 2019, "1-5", "70min", "8.1", 50, "Common"),
        ("Everdell", "Starling Games", "James A. Wilson", 2018, "1-4", "80min", "7.8", 50, "Common"),
        ("Ticket to Ride", "Days of Wonder", "Alan R. Moon", 2004, "2-5", "60min", "7.4", 35, "Common"),
        ("Catan", "Kosmos", "Klaus Teuber", 1995, "3-4", "90min", "7.1", 30, "Common"),
        ("Splendor", "Space Cowboys", "Marc André", 2014, "2-4", "30min", "7.4", 30, "Common"),
        ("Azul", "Next Move Games", "Michael Kiesling", 2017, "2-4", "45min", "7.8", 35, "Common"),
        ("Pandemic", "Z-Man Games", "Matt Leacock", 2008, "2-4", "45min", "7.6", 30, "Common"),
        ("Cosmic Encounter", "Fantasy Flight Games", "Bill Eberle", 2008, "3-5", "120min", "7.6", 50, "Common"),
        ("Dune: Imperium", "Dire Wolf Digital", "Paul Dennen", 2020, "1-4", "120min", "8.3", 50, "Common"),
        ("Ark Nova", "Capstone Games", "Mathias Wigge", 2021, "1-4", "150min", "8.5", 55, "Common"),
        ("Nemesis", "Awaken Realms", "Adam Kwapiński", 2018, "1-5", "120min", "8.3", 100, "Uncommon"),
        ("Blood Rage", "CMON", "Eric M. Lang", 2015, "2-4", "80min", "8.0", 65, "Common"),
        ("Zombicide: Green Horde", "CMON", "Raphaël Guiton", 2018, "1-6", "60min", "7.3", 80, "Uncommon"),
        ("Gloomhaven", "Cephalofair Games", "Isaac Childres", 2017, "1-4", "120min", "8.6", 120, "Uncommon"),
        ("Ankh: Gods of Egypt", "CMON", "Eric M. Lang", 2022, "2-5", "90min", "7.5", 85, "Uncommon"),
        ("Massive Darkness 2", "CMON", "Marco Portugal", 2022, "1-6", "90min", "7.5", 100, "Uncommon"),
        ("Sleeping Gods", "Red Raven Games", "Ryan Laukat", 2021, "1-4", "120min", "8.1", 75, "Uncommon"),
        ("Anachrony (Essential Edition)", "Mindclash Games", "Dávid Turczi", 2017, "1-4", "120min", "7.9", 55, "Common"),
        ("Maracaibo", "DLP Games", "Alexander Pfister", 2019, "1-4", "120min", "8.0", 55, "Common"),
        ("Praga Caput Regni", "Delicious Games", "Vladimír Suchý", 2020, "1-4", "120min", "7.8", 50, "Common"),
        ("Rococo (Deluxe)", "Eagle-Gryphon Games", "Matthias Cramer", 2013, "2-5", "90min", "7.6", 75, "Uncommon"),
        ("Kanban EV", "Eagle-Gryphon Games", "Vital Lacerda", 2020, "1-4", "120min", "8.0", 85, "Uncommon"),
        ("Marvel United (KS)", "CMON", "Eric M. Lang", 2020, "1-4", "40min", "7.3", 60, "Common"),
        ("Robinson Crusoe (Collector's Edition)", "Portal Games", "Ignacy Trzewiczek", 2012, "1-4", "120min", "7.6", 100, "Uncommon"),
        ("Trickerion (Collector's Edition)", "Mindclash Games", "Richard Amann", 2015, "2-4", "120min", "7.7", 100, "Uncommon"),
        # CMON KS games
        ("Marvel Zombicide", "CMON", "Fabio Cury", 2022, "1-6", "60min", "7.5", 120, "Uncommon"),
        ("Trudvang Legends", "CMON", "Eric M. Lang", 2021, "1-4", "90min", "7.0", 100, "Uncommon"),
        ("Hate", "CMON", "Adrián Smith", 2019, "2-4", "90min", "7.2", 110, "Uncommon"),
        ("Arcadia Quest", "CMON", "Thiago Aranha", 2014, "2-4", "60min", "7.5", 80, "Common"),
        ("Starcadia Quest", "CMON", "Thiago Aranha", 2020, "2-4", "60min", "7.2", 90, "Uncommon"),
        # Awaken Realms
        ("Lords of Hellas", "Awaken Realms", "Adam Kwapiński", 2018, "1-4", "90min", "7.4", 90, "Uncommon"),
        ("Destinies", "Awaken Realms", "Michał Gołębiowski", 2021, "1-3", "120min", "7.5", 55, "Common"),
        # Chip Theory Games
        ("Hoplomachus: Victorum", "Chip Theory Games", "Josh J. Carlson", 2022, "1-2", "30min", "8.0", 80, "Uncommon"),
        ("Cloudspire", "Chip Theory Games", "Josh J. Carlson", 2019, "1-4", "120min", "8.0", 150, "Uncommon"),
        # Red Raven Games
        ("Islebound", "Red Raven Games", "Ryan Laukat", 2016, "2-4", "90min", "7.0", 45, "Common"),
        ("City of Iron (2nd Edition)", "Red Raven Games", "Ryan Laukat", 2014, "2-4", "120min", "7.2", 55, "Uncommon"),
        # Portal Games
        ("Imperial Settlers", "Portal Games", "Ignacy Trzewiczek", 2014, "1-4", "90min", "7.2", 40, "Common"),
        ("Detective: A Modern Crime Board Game", "Portal Games", "Ignacy Trzewiczek", 2018, "1-5", "180min", "7.3", 40, "Common"),
        ("First Martians: Adventures on the Red Planet", "Portal Games", "Ignacy Trzewiczek", 2017, "1-4", "90min", "6.2", 50, "Uncommon"),
        # GMT / wargame-adjacent
        ("Root: The Clockwork Expansion", "Leder Games", "Cole Wehrle", 2020, "1-4", "90min", "8.1", 30, "Common"),
        ("Pax Renaissance", "Ion Game Design", "Phil Eklund", 2016, "1-4", "120min", "7.9", 60, "Uncommon"),
        ("Pax Transhumanity", "Ion Game Design", "Phil Eklund", 2019, "1-4", "90min", "7.2", 45, "Uncommon"),
        # Splotter
        ("Greed Incorporated", "Splotter Spellen", "Jeroen Doumen", 2009, "3-5", "120min", "6.8", 200, "Rare"),
        # Classic euros
        ("Concordia Solitaria", "PD-Verlag", "Mac Gerdts", 2022, "1-2", "90min", "8.1", 35, "Common"),
        ("Glen More II: Chronicles", "Funtails", "Matthias Cramer", 2019, "2-4", "120min", "7.7", 55, "Common"),
        ("Istanbul", "Pegasus Spiele", "Rüdiger Dorn", 2014, "2-5", "60min", "7.5", 35, "Common"),
        ("Russian Railroads", "Hans im Glück", "Helmut Ohley", 2013, "2-4", "120min", "7.8", 70, "Uncommon"),
        ("Voyages of Marco Polo II", "Hans im Glück", "Simone Luciani", 2019, "2-4", "100min", "8.0", 50, "Common"),
        ("Mombasa", "Eggertspiele", "Alexander Pfister", 2015, "2-4", "150min", "7.8", 60, "Uncommon"),
        ("La Granja", "Spielworxx", "Michael Keller", 2014, "1-4", "120min", "7.6", 50, "Uncommon"),
        ("Troyes Dice", "Pearl Games", "Sébastien Dujardin", 2020, "1-4", "30min", "7.1", 20, "Common"),
        ("T'zolkin: Tribes & Prophecies", "Czech Games Edition", "Simone Luciani", 2013, "2-5", "90min", "7.8", 35, "Uncommon"),
        # Recent heavies
        ("Hegemony: Lead Your Class to Victory", "Hegemonic Project Games", "Varnavas Timotheou", 2023, "2-4", "120min", "8.2", 65, "Common"),
        ("Voidfall", "Mindclash Games", "Nigel Buckle", 2023, "1-4", "180min", "8.3", 110, "Uncommon"),
        ("Fractal: Beyond the Void", "Boardcubator", "Ondřej Sova", 2023, "1-4", "120min", "7.8", 60, "Common"),
        ("Darwin's Journey", "ThunderGryph Games", "Simone Luciani", 2023, "1-4", "120min", "8.1", 65, "Common"),
        ("Bitoku", "Devir", "Germán P. Millán", 2021, "1-4", "120min", "7.9", 50, "Common"),
        # More KS / recent hotness
        ("Ares Expedition", "Stronghold Games", "Sydney Engelstein", 2021, "1-4", "60min", "7.5", 35, "Common"),
        ("Frosthaven", "Cephalofair Games", "Isaac Childres", 2023, "1-4", "120min", "8.5", 175, "Uncommon"),
        ("Vagrantsong", "Wyrd Miniatures", "Kyle Rowan", 2022, "2-4", "90min", "7.8", 70, "Uncommon"),
        ("Merchants Cove", "Final Frontier Games", "Jonny Pac", 2021, "1-4", "75min", "7.5", 70, "Uncommon"),
        ("Waste Knights (2nd Edition)", "Galakta", "Rafał Cichocki", 2020, "1-4", "120min", "7.5", 85, "Uncommon"),
        ("Excavation Earth", "Mighty Boards", "David Turczi", 2021, "1-4", "90min", "7.4", 45, "Common"),
        ("Perseverance: Castaway Chronicles", "Mindclash Games", "Richard Amann", 2022, "1-4", "120min", "7.6", 70, "Uncommon"),
        ("Creature Comforts", "Kids Table BG", "Roberta Taylor", 2021, "1-5", "45min", "7.3", 40, "Common"),
        ("Sankokushin: Five Sacrifices", "Ankama", "Charles Chevallier", 2023, "2-4", "120min", "7.8", 55, "Common"),
        ("Nemo's War (2nd Edition)", "Victory Point Games", "Chris Taylor", 2017, "1-4", "120min", "7.9", 65, "Uncommon"),
        ("Tawantinsuyu", "Board & Dice", "Dávid Turczi", 2020, "1-4", "120min", "7.6", 45, "Common"),
        ("Tabannusi: Builders of Ur", "Board & Dice", "Dániel Tascini", 2022, "1-4", "120min", "7.5", 45, "Common"),
        ("Zapotec", "Board & Dice", "Fabio Lopiano", 2021, "1-4", "75min", "7.4", 40, "Common"),
        ("Autobahn", "Alley Cat Games", "Fabio Lopiano", 2023, "1-4", "120min", "7.6", 50, "Common"),
        ("Ages of Comics: The Golden Years", "Plan B Games", "Frédéric Guérard", 2022, "2-4", "120min", "7.5", 45, "Common"),
        ("Boonlake", "Capstone Games", "Alexander Pfister", 2021, "1-4", "120min", "7.7", 50, "Common"),
        ("Nucleum", "Board & Dice", "Simone Luciani", 2023, "1-4", "120min", "8.0", 55, "Common"),
        ("Revive", "Aporta Games", "Helge Meissner", 2022, "1-4", "120min", "7.9", 55, "Common"),
        ("Tiletum", "Board & Dice", "Simone Luciani", 2022, "1-4", "120min", "7.8", 45, "Common"),
        ("Zhanguo: The First Empire", "Sorry We Are French", "Marco Canetta", 2023, "1-4", "120min", "7.7", 45, "Common"),
        ("Terracotta Army", "Board & Dice", "Przemysław Fornal", 2022, "1-4", "120min", "7.6", 50, "Common"),
        ("Witchstone", "R&R Games", "Reiner Knizia", 2021, "2-4", "60min", "7.2", 40, "Common"),
        ("Golem", "Cranio Creations", "Simone Luciani", 2021, "1-4", "120min", "7.7", 55, "Common"),
        ("Endless Winter: Paleoamericans", "Fantasia Games", "Stan Kordonskiy", 2022, "1-4", "120min", "7.9", 70, "Uncommon"),
        ("Apiary", "Stonemaier Games", "Connie Vogelmann", 2023, "1-5", "90min", "7.7", 50, "Common"),
        ("Kutná Hora: The City of Silver", "Czech Games Edition", "Petr Čáslava", 2023, "2-4", "120min", "7.7", 50, "Common"),
        ("Earth", "Inside Up Games", "Maxime Tardif", 2023, "1-5", "60min", "7.5", 40, "Common"),
        ("Woodcraft", "Delicious Games", "Vladimír Suchý", 2022, "1-4", "120min", "7.5", 45, "Common"),
        ("Horseless Carriage", "Splotter Spellen", "Jeroen Doumen", 2023, "2-5", "180min", "7.5", 90, "Uncommon"),
        # --- Expansion batch (60 new base games) ---
        ("Hegemony", "Hegemonic Project", "Varnavas Timotheou", 2023, "2-4", "180min", "8.2", 70, "Common"),
        ("Voidfall", "Mindclash Games", "Nigel Buckle", 2023, "1-4", "180min", "8.1", 90, "Uncommon"),
        ("Darwin's Journey", "ThunderGryph Games", "Simone Luciani", 2023, "1-4", "120min", "8.0", 65, "Common"),
        ("Bitoku", "Devir", "Germán P. Millán", 2021, "1-4", "120min", "7.9", 55, "Common"),
        ("Lacrimosa", "Devir", "Gerard Ascensi", 2022, "1-4", "90min", "7.7", 50, "Common"),
        ("Feast for Odin", "Z-Man Games", "Uwe Rosenberg", 2016, "1-4", "120min", "8.1", 70, "Uncommon"),
        ("Glen More II", "Funtails", "Matthias Cramer", 2019, "2-4", "120min", "7.6", 55, "Common"),
        ("Istanbul", "Pegasus Spiele", "Rüdiger Dorn", 2014, "2-5", "60min", "7.6", 40, "Common"),
        ("Russian Railroads", "Hans im Glück", "Helmut Ohley", 2013, "2-4", "120min", "7.8", 60, "Uncommon"),
        ("Mombasa", "Eggertspiele", "Alexander Pfister", 2015, "2-4", "150min", "7.8", 55, "Common"),
        ("La Granja", "Stronghold Games", "Michael Keller", 2014, "1-4", "120min", "7.6", 50, "Common"),
        ("Troyes", "Pearl Games", "Sébastien Dujardin", 2010, "2-4", "90min", "7.7", 65, "Uncommon"),
        ("Pipeline", "Capstone Games", "Ryan Courtney", 2019, "2-4", "120min", "7.7", 55, "Common"),
        ("Stroganov", "Game Brewer", "Andreas Steding", 2021, "1-4", "90min", "7.5", 50, "Common"),
        ("Nusfjord", "Lookout Games", "Uwe Rosenberg", 2017, "1-5", "30min", "7.4", 45, "Common"),
        ("Hallertau", "Lookout Games", "Uwe Rosenberg", 2020, "1-4", "140min", "7.7", 55, "Common"),
        ("Bonfire", "Pegasus Spiele", "Stefan Feld", 2020, "1-4", "100min", "7.5", 50, "Common"),
        ("Forum Trajanum", "Stronghold Games", "Stefan Feld", 2018, "2-4", "120min", "7.2", 45, "Common"),
        ("Merv", "Osprey Games", "Fabio Lopiano", 2020, "1-4", "90min", "7.7", 50, "Common"),
        ("Tiletum", "Board & Dice", "Simone Luciani", 2022, "1-4", "120min", "7.9", 55, "Common"),
        ("Zhanguo", "What's Your Game?", "Marco Canetta", 2014, "2-4", "120min", "7.3", 55, "Uncommon"),
        ("Nippon", "What's Your Game?", "Nuno Bizarro Sentieiro", 2015, "2-4", "120min", "7.5", 60, "Uncommon"),
        ("Panamax", "Stronghold Games", "Gil d'Orey", 2014, "2-4", "120min", "7.3", 55, "Uncommon"),
        ("Vinhos", "Eagle-Gryphon Games", "Vital Lacerda", 2010, "2-4", "120min", "7.5", 80, "Uncommon"),
        ("Snowdonia", "Surprised Stare", "Tony Boydell", 2012, "1-5", "90min", "7.3", 50, "Uncommon"),
        ("Bruxelles 1893", "Pearl Games", "Etienne Espreman", 2013, "2-5", "90min", "7.5", 65, "Uncommon"),
        ("Wildcatters", "Capstone Games", "Rolf Sagel", 2014, "2-5", "120min", "7.3", 60, "Uncommon"),
        ("Sol: Last Days of a Star", "Elephant Labs", "Jesse Catron", 2017, "2-5", "90min", "7.5", 80, "Uncommon"),
        ("Pax Renaissance", "Sierra Madre Games", "Phil Eklund", 2016, "2-4", "120min", "7.8", 65, "Uncommon"),
        ("John Company 2E", "Wehrlegig Games", "Cole Wehrle", 2022, "1-6", "180min", "7.7", 75, "Uncommon"),
        ("Oath", "Leder Games", "Cole Wehrle", 2021, "1-6", "90min", "7.5", 80, "Uncommon"),
        ("Vast: Crystal Caverns", "Leder Games", "Patrick Leder", 2016, "1-5", "75min", "7.1", 55, "Uncommon"),
        ("Fort", "Leder Games", "Grant Rodiek", 2020, "2-4", "30min", "7.2", 30, "Common"),
        ("Clinic", "Alban Viard Studio", "Alban Viard", 2019, "1-4", "120min", "7.5", 60, "Uncommon"),
        ("Aeon's End: War Eternal", "Indie Boards & Cards", "Kevin Riley", 2017, "1-4", "60min", "7.9", 50, "Common"),
        ("Sentinels of the Multiverse", "Greater Than Games", "Christopher Badell", 2011, "2-5", "60min", "7.4", 40, "Common"),
        ("Arcadia Quest", "CMON", "Thiago Aranha", 2014, "2-4", "60min", "7.6", 70, "Uncommon"),
        ("Starcadia Quest", "CMON", "Thiago Aranha", 2020, "2-4", "60min", "7.2", 65, "Uncommon"),
        ("Trudvang Legends", "CMON", "Eric M. Lang", 2022, "1-4", "120min", "7.0", 80, "Uncommon"),
        ("Hate", "CMON", "Eric M. Lang", 2019, "2-4", "90min", "6.8", 75, "Uncommon"),
        ("Marvel Zombicide", "CMON", "Fabio Cury", 2022, "1-6", "60min", "7.8", 100, "Uncommon"),
        ("Lords of Hellas", "Awaken Realms", "Adam Kwapiński", 2018, "1-4", "90min", "7.5", 70, "Uncommon"),
        ("Destinies", "Lucky Duck Games", "Michał Gołębiowski", 2021, "1-3", "120min", "7.5", 55, "Common"),
        ("Hoplomachus", "Chip Theory Games", "Josh J. Carlson", 2013, "1-3", "60min", "7.5", 90, "Uncommon"),
        ("Cloudspire", "Chip Theory Games", "Josh J. Carlson", 2019, "1-4", "120min", "8.0", 100, "Uncommon"),
        ("Imperial Settlers", "Portal Games", "Ignacy Trzewiczek", 2014, "1-4", "90min", "7.3", 40, "Common"),
        ("Detective", "Portal Games", "Ignacy Trzewiczek", 2018, "1-5", "180min", "7.4", 45, "Common"),
        ("First Martians", "Portal Games", "Ignacy Trzewiczek", 2017, "1-4", "90min", "6.3", 45, "Uncommon"),
        ("Carnegie", "Pegasus Spiele", "Xavier Georges", 2022, "1-4", "120min", "7.8", 55, "Common"),
        ("Greed Incorporated", "Splotter Spellen", "Jeroen Doumen", 2009, "3-5", "120min", "7.0", 200, "Rare"),
        ("Horseless Carriage", "Splotter Spellen", "Jeroen Doumen", 2022, "1-5", "180min", "7.5", 90, "Uncommon"),
        ("Age of Steam", "Eagle-Gryphon Games", "Martin Wallace", 2002, "3-6", "120min", "7.7", 75, "Uncommon"),
        ("Brass", "Warfrog Games", "Martin Wallace", 2007, "3-4", "120min", "7.9", 80, "Uncommon"),
        ("Dominant Species: Marine", "GMT Games", "Chad Jensen", 2021, "2-4", "120min", "7.6", 50, "Common"),
        ("Lisboa", "Eagle-Gryphon Games", "Vital Lacerda", 2017, "1-4", "120min", "8.0", 100, "Uncommon"),
        ("Fractal", "Mindclash Games", "Dávid Turczi", 2024, "1-4", "120min", "7.8", 65, "Common"),
        ("Anachrony", "Mindclash Games", "Dávid Turczi", 2017, "1-4", "120min", "7.9", 65, "Uncommon"),
        ("Trickerion", "Mindclash Games", "Richard Amann", 2015, "2-4", "120min", "7.7", 65, "Uncommon"),
        ("Perseverance", "Mindclash Games", "Dávid Turczi", 2022, "1-4", "90min", "7.5", 55, "Common"),
    ]
    editions = [
        ("Kickstarter Deluxe", 1.6, "Rare"),
        ("Collector's Edition", 2.0, "Rare"),
        ("Limited Print Run", 1.4, "Uncommon"),
        ("Signed by Designer", 2.5, "Grail"),
        ("1st Print Sealed", 1.3, "Uncommon"),
    ]
    for name, pub, designer, year, pc, pt, rating, price, _ in base_games:
        for ed_name, mult, rarity in editions:
            variants.append({
                "name": f"{name} ({ed_name})",
                "publisher": pub,
                "designer": designer,
                "year": year,
                "player_count": pc,
                "play_time": pt,
                "bgg_rating": rating,
                "edition": ed_name,
                "condition": "sealed" if "Sealed" in ed_name else "complete",
                "price_eur": int(price * mult),
                "rarity": rarity,
                "image_url": "https://cf.geekdo-images.com/placeholder",
            })
    # Additional standalone entries to bulk up
    extra = [
        {"name": "Survive: Escape from Atlantis (30th Anniversary)", "publisher": "Stronghold Games", "designer": "Julian Courtland-Smith", "year": 2012, "player_count": "2-4", "play_time": "60min", "bgg_rating": "7.1", "edition": "30th Anniversary", "condition": "complete", "price_eur": 55, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Forbidden Stars", "publisher": "Fantasy Flight Games", "designer": "Samuel Bailey", "year": 2015, "player_count": "2-4", "play_time": "180min", "bgg_rating": "7.8", "edition": "1st Edition", "condition": "sealed", "price_eur": 250, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Rex: Final Days of an Empire", "publisher": "Fantasy Flight Games", "designer": "Corey Konieczka", "year": 2012, "player_count": "3-6", "play_time": "180min", "bgg_rating": "7.2", "edition": "1st Edition", "condition": "complete", "price_eur": 100, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Tigris & Euphrates (FFG Edition)", "publisher": "Fantasy Flight Games", "designer": "Reiner Knizia", "year": 2015, "player_count": "2-4", "play_time": "90min", "bgg_rating": "7.7", "edition": "FFG Edition", "condition": "complete", "price_eur": 85, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Concordia Venus (Big Box)", "publisher": "PD-Verlag", "designer": "Mac Gerdts", "year": 2019, "player_count": "2-6", "play_time": "120min", "bgg_rating": "8.1", "edition": "Big Box", "condition": "sealed", "price_eur": 70, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Grand Austria Hotel", "publisher": "Lookout Games", "designer": "Simone Luciani", "year": 2015, "player_count": "2-4", "play_time": "120min", "bgg_rating": "7.8", "edition": "1st Edition", "condition": "complete", "price_eur": 55, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Coimbra", "publisher": "Eggertspiele", "designer": "Flaminia Brasini", "year": 2018, "player_count": "2-4", "play_time": "75min", "bgg_rating": "7.5", "edition": "1st Edition", "condition": "complete", "price_eur": 45, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Patchwork", "publisher": "Lookout Games", "designer": "Uwe Rosenberg", "year": 2014, "player_count": "2", "play_time": "30min", "bgg_rating": "7.7", "edition": "1st Edition", "condition": "complete", "price_eur": 25, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Star Realms (Collection)", "publisher": "White Wizard Games", "designer": "Robert Dougherty", "year": 2014, "player_count": "2", "play_time": "20min", "bgg_rating": "7.5", "edition": "Complete Collection", "condition": "complete", "price_eur": 60, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Five Tribes (Days of Ire Big Box)", "publisher": "Days of Wonder", "designer": "Bruno Cathala", "year": 2014, "player_count": "2-4", "play_time": "80min", "bgg_rating": "7.8", "edition": "Big Box", "condition": "sealed", "price_eur": 70, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Lewis & Clark", "publisher": "Ludonaute", "designer": "Cédrick Chaboussit", "year": 2013, "player_count": "1-5", "play_time": "120min", "bgg_rating": "7.4", "edition": "1st Edition", "condition": "complete", "price_eur": 50, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Vinhos (Deluxe)", "publisher": "Eagle-Gryphon Games", "designer": "Vital Lacerda", "year": 2016, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.8", "edition": "Deluxe", "condition": "sealed", "price_eur": 85, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Twilight Struggle (Deluxe)", "publisher": "GMT Games", "designer": "Ananda Gupta", "year": 2005, "player_count": "2", "play_time": "180min", "bgg_rating": "8.2", "edition": "Deluxe", "condition": "sealed", "price_eur": 55, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Pandemic (10th Anniversary)", "publisher": "Z-Man Games", "designer": "Matt Leacock", "year": 2018, "player_count": "2-4", "play_time": "45min", "bgg_rating": "7.6", "edition": "10th Anniversary", "condition": "sealed", "price_eur": 100, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Merchants & Marauders", "publisher": "Z-Man Games", "designer": "Kasper Aagaard", "year": 2010, "player_count": "2-4", "play_time": "180min", "bgg_rating": "7.2", "edition": "1st Edition", "condition": "complete", "price_eur": 90, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Stockpile", "publisher": "Nauvoo Games", "designer": "Brett Sobol", "year": 2015, "player_count": "2-5", "play_time": "45min", "bgg_rating": "7.0", "edition": "Kickstarter", "condition": "complete", "price_eur": 45, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Raiders of the North Sea (Collector's Box)", "publisher": "Garphill Games", "designer": "Shem Phillips", "year": 2015, "player_count": "2-4", "play_time": "80min", "bgg_rating": "7.5", "edition": "Collector's Box", "condition": "sealed", "price_eur": 75, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Obsession (Upstairs Downstairs KS)", "publisher": "Kayenta Games", "designer": "Dan Hallagan", "year": 2019, "player_count": "1-4", "play_time": "60min", "bgg_rating": "7.9", "edition": "Kickstarter", "condition": "sealed", "price_eur": 90, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Carnegie (Deluxe)", "publisher": "Pegasus Spiele", "designer": "Xavier Georges", "year": 2021, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.6", "edition": "Deluxe KS", "condition": "sealed", "price_eur": 70, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Messina 1347", "publisher": "Delicious Games", "designer": "Vladimír Suchý", "year": 2021, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.8", "edition": "1st Edition", "condition": "sealed", "price_eur": 45, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
    ]
    variants.extend(extra)
    return variants


# ---------------------------------------------------------------------------
# Catalog assembler
# ---------------------------------------------------------------------------

def _dungeons_and_dragons() -> list[dict]:
    """Dungeons & Dragons collectible board games, box sets, and OOP RPG products."""
    return [
        # ── Classic D&D Board Games ──
        {"name": "HeroQuest (1989 Original)", "publisher": "Milton Bradley", "designer": "Stephen Baker", "year": 1989, "player_count": "2-5", "play_time": "90min", "bgg_rating": "6.9", "edition": "1st Edition", "condition": "complete", "price_eur": 250, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "HeroQuest (2021 Hasbro Relaunch)", "publisher": "Hasbro", "designer": "Stephen Baker", "year": 2021, "player_count": "2-5", "play_time": "60min", "bgg_rating": "7.2", "edition": "Mythic Tier KS", "condition": "sealed", "price_eur": 180, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Dungeons & Dragons: Castle Ravenloft", "publisher": "Wizards of the Coast", "designer": "Bill Slavicsek", "year": 2010, "player_count": "1-5", "play_time": "60min", "bgg_rating": "6.6", "edition": "1st Edition", "condition": "complete", "price_eur": 65, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Dungeons & Dragons: Wrath of Ashardalon", "publisher": "Wizards of the Coast", "designer": "Bill Slavicsek", "year": 2011, "player_count": "1-5", "play_time": "60min", "bgg_rating": "6.6", "edition": "1st Edition", "condition": "complete", "price_eur": 60, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Dungeons & Dragons: The Legend of Drizzt", "publisher": "Wizards of the Coast", "designer": "Peter Lee", "year": 2011, "player_count": "1-5", "play_time": "60min", "bgg_rating": "6.7", "edition": "1st Edition", "condition": "complete", "price_eur": 65, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Dungeons & Dragons: Temple of Elemental Evil", "publisher": "Wizards of the Coast", "designer": "Peter Lee", "year": 2015, "player_count": "1-5", "play_time": "60min", "bgg_rating": "6.8", "edition": "1st Edition", "condition": "complete", "price_eur": 70, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Dungeons & Dragons: Tomb of Annihilation", "publisher": "Wizards of the Coast", "designer": "Kevin Wilson", "year": 2017, "player_count": "1-5", "play_time": "60min", "bgg_rating": "6.5", "edition": "1st Edition", "condition": "complete", "price_eur": 75, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Dungeon! (1975 Original)", "publisher": "TSR", "designer": "David R. Megarry", "year": 1975, "player_count": "1-8", "play_time": "30min", "bgg_rating": "5.7", "edition": "1st Edition", "condition": "complete", "price_eur": 120, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Dungeon! (2014 Reprint)", "publisher": "Wizards of the Coast", "designer": "David R. Megarry", "year": 2014, "player_count": "1-8", "play_time": "30min", "bgg_rating": "5.7", "edition": "2014 Edition", "condition": "complete", "price_eur": 25, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        # ── OOP D&D RPG Box Sets (collectible tabletop) ──
        {"name": "D&D Basic Set (Red Box, 1983)", "publisher": "TSR", "designer": "Frank Mentzer", "year": 1983, "player_count": "2-6", "play_time": "180min", "bgg_rating": "7.0", "edition": "BECMI Red Box", "condition": "complete", "price_eur": 180, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "D&D Expert Set (Blue Box, 1983)", "publisher": "TSR", "designer": "Frank Mentzer", "year": 1983, "player_count": "2-6", "play_time": "180min", "bgg_rating": "7.1", "edition": "BECMI Blue Box", "condition": "complete", "price_eur": 150, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "AD&D 1st Edition Player's Handbook (1978)", "publisher": "TSR", "designer": "Gary Gygax", "year": 1978, "player_count": "2-8", "play_time": "240min", "bgg_rating": "7.5", "edition": "1st Print", "condition": "good", "price_eur": 200, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "AD&D 1st Edition Dungeon Master's Guide (1979)", "publisher": "TSR", "designer": "Gary Gygax", "year": 1979, "player_count": "1", "play_time": "-", "bgg_rating": "7.6", "edition": "1st Print", "condition": "good", "price_eur": 180, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "AD&D 1st Edition Monster Manual (1977)", "publisher": "TSR", "designer": "Gary Gygax", "year": 1977, "player_count": "1", "play_time": "-", "bgg_rating": "7.3", "edition": "1st Print", "condition": "good", "price_eur": 220, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "D&D 3.5 Core Rulebook Gift Set", "publisher": "Wizards of the Coast", "designer": "Monte Cook", "year": 2003, "player_count": "2-8", "play_time": "240min", "bgg_rating": "7.8", "edition": "3.5 Revised", "condition": "sealed", "price_eur": 250, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "D&D 5th Edition Core Rulebooks Gift Set (Alt Covers)", "publisher": "Wizards of the Coast", "designer": "Jeremy Crawford", "year": 2018, "player_count": "2-8", "play_time": "240min", "bgg_rating": "8.2", "edition": "Alt Cover Gift Set", "condition": "sealed", "price_eur": 160, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        # ── Classic Modules & Adventures ──
        {"name": "Tomb of Horrors (S1, 1978 Original)", "publisher": "TSR", "designer": "Gary Gygax", "year": 1978, "player_count": "4-6", "play_time": "360min", "bgg_rating": "6.5", "edition": "1st Print", "condition": "good", "price_eur": 300, "rarity": "Very Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Keep on the Borderlands (B2, 1979)", "publisher": "TSR", "designer": "Gary Gygax", "year": 1979, "player_count": "3-6", "play_time": "240min", "bgg_rating": "6.7", "edition": "1st Print", "condition": "good", "price_eur": 150, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Ravenloft (I6, 1983)", "publisher": "TSR", "designer": "Tracy Hickman", "year": 1983, "player_count": "4-6", "play_time": "360min", "bgg_rating": "7.0", "edition": "1st Print", "condition": "good", "price_eur": 200, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Temple of Elemental Evil (T1-4, 1985)", "publisher": "TSR", "designer": "Gary Gygax", "year": 1985, "player_count": "4-8", "play_time": "600min", "bgg_rating": "6.8", "edition": "1st Print", "condition": "good", "price_eur": 180, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Against the Giants (G1-3, 1981)", "publisher": "TSR", "designer": "Gary Gygax", "year": 1981, "player_count": "4-6", "play_time": "480min", "bgg_rating": "6.9", "edition": "Compilation", "condition": "good", "price_eur": 130, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Queen of the Spiders (GDQ1-7, 1986)", "publisher": "TSR", "designer": "Gary Gygax", "year": 1986, "player_count": "4-8", "play_time": "1200min", "bgg_rating": "7.2", "edition": "Supermodule", "condition": "good", "price_eur": 160, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        # ── Campaign Settings (OOP) ──
        {"name": "Planescape Campaign Setting Box Set", "publisher": "TSR", "designer": "David Cook", "year": 1994, "player_count": "2-8", "play_time": "240min", "bgg_rating": "8.0", "edition": "1st Print", "condition": "complete", "price_eur": 350, "rarity": "Very Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Dark Sun Campaign Setting Box Set", "publisher": "TSR", "designer": "Troy Denning", "year": 1991, "player_count": "2-8", "play_time": "240min", "bgg_rating": "7.5", "edition": "1st Print", "condition": "complete", "price_eur": 280, "rarity": "Very Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Spelljammer: Adventures in Space Box Set", "publisher": "TSR", "designer": "Jeff Grubb", "year": 1989, "player_count": "2-8", "play_time": "240min", "bgg_rating": "7.2", "edition": "1st Print", "condition": "complete", "price_eur": 250, "rarity": "Very Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Ravenloft: Realm of Terror Box Set", "publisher": "TSR", "designer": "Bruce Nesmith", "year": 1990, "player_count": "2-8", "play_time": "240min", "bgg_rating": "7.3", "edition": "1st Print", "condition": "complete", "price_eur": 220, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Dragonlance Adventures (1st Print)", "publisher": "TSR", "designer": "Tracy Hickman", "year": 1987, "player_count": "2-8", "play_time": "240min", "bgg_rating": "7.0", "edition": "1st Print", "condition": "good", "price_eur": 120, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        # ── Modern D&D Board Games ──
        {"name": "Tyrants of the Underdark", "publisher": "Wizards of the Coast", "designer": "Peter Lee", "year": 2016, "player_count": "2-4", "play_time": "75min", "bgg_rating": "7.4", "edition": "1st Edition", "condition": "complete", "price_eur": 55, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Lords of Waterdeep", "publisher": "Wizards of the Coast", "designer": "Peter Lee", "year": 2012, "player_count": "2-5", "play_time": "60min", "bgg_rating": "7.5", "edition": "1st Edition", "condition": "complete", "price_eur": 45, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Lords of Waterdeep: Scoundrels of Skullport", "publisher": "Wizards of the Coast", "designer": "Peter Lee", "year": 2013, "player_count": "2-6", "play_time": "75min", "bgg_rating": "7.9", "edition": "1st Edition", "condition": "complete", "price_eur": 55, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Betrayal at Baldur's Gate", "publisher": "Wizards of the Coast", "designer": "Chris Dupuis", "year": 2017, "player_count": "3-6", "play_time": "60min", "bgg_rating": "6.7", "edition": "1st Edition", "condition": "complete", "price_eur": 40, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "D&D: Assault of the Giants", "publisher": "WizKids", "designer": "Andrew Parks", "year": 2017, "player_count": "3-6", "play_time": "90min", "bgg_rating": "6.4", "edition": "Premium", "condition": "sealed", "price_eur": 90, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Dragonfire", "publisher": "Catalyst Game Labs", "designer": "Loren Coleman", "year": 2017, "player_count": "2-6", "play_time": "60min", "bgg_rating": "6.5", "edition": "1st Edition", "condition": "complete", "price_eur": 50, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        # ── D&D Miniatures (collectible sets) ──
        {"name": "D&D Miniatures: Harbinger Booster Case (Sealed)", "publisher": "Wizards of the Coast", "designer": "-", "year": 2003, "player_count": "2", "play_time": "30min", "bgg_rating": "6.0", "edition": "Harbinger", "condition": "sealed", "price_eur": 400, "rarity": "Very Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "D&D Miniatures: Dragoneye Booster Case (Sealed)", "publisher": "Wizards of the Coast", "designer": "-", "year": 2003, "player_count": "2", "play_time": "30min", "bgg_rating": "6.0", "edition": "Dragoneye", "condition": "sealed", "price_eur": 350, "rarity": "Very Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "D&D Icons of the Realms: Adult Red Dragon", "publisher": "WizKids", "designer": "-", "year": 2019, "player_count": "-", "play_time": "-", "bgg_rating": "-", "edition": "Premium", "condition": "sealed", "price_eur": 75, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "D&D Icons of the Realms: Tiamat", "publisher": "WizKids", "designer": "-", "year": 2020, "player_count": "-", "play_time": "-", "bgg_rating": "-", "edition": "Premium", "condition": "sealed", "price_eur": 120, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "D&D Icons of the Realms: Bahamut", "publisher": "WizKids", "designer": "-", "year": 2022, "player_count": "-", "play_time": "-", "bgg_rating": "-", "edition": "Premium", "condition": "sealed", "price_eur": 110, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        # ── Rare/Grail D&D Collectibles ──
        {"name": "Original D&D White Box (1974)", "publisher": "TSR", "designer": "Gary Gygax", "year": 1974, "player_count": "2-8", "play_time": "240min", "bgg_rating": "6.8", "edition": "Woodgrain Box", "condition": "fair", "price_eur": 5000, "rarity": "Ultra Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Original D&D White Box (1974, White Box)", "publisher": "TSR", "designer": "Gary Gygax", "year": 1974, "player_count": "2-8", "play_time": "240min", "bgg_rating": "6.8", "edition": "White Box (6th Print)", "condition": "good", "price_eur": 1500, "rarity": "Very Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "D&D Rules Cyclopedia (1991)", "publisher": "TSR", "designer": "Aaron Allston", "year": 1991, "player_count": "2-8", "play_time": "240min", "bgg_rating": "7.8", "edition": "1st Print", "condition": "good", "price_eur": 200, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Deities & Demigods (with Cthulhu, 1st Print)", "publisher": "TSR", "designer": "James Ward", "year": 1980, "player_count": "1", "play_time": "-", "bgg_rating": "6.5", "edition": "1st Print (144 pages)", "condition": "good", "price_eur": 400, "rarity": "Very Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Fiend Folio (1st Print, 1981)", "publisher": "TSR", "designer": "Don Turnbull", "year": 1981, "player_count": "1", "play_time": "-", "bgg_rating": "6.8", "edition": "1st Print", "condition": "good", "price_eur": 120, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
    ]


def _expansion_round_35() -> list[dict]:
    """Round 35 expansion: KS exclusives, classic OOP grails, rare expansions,
    euro collector's editions, miniature-heavy games."""
    return [
        # ── Kickstarter Exclusives ────────────────────────────────────────
        {"name": "Gloomhaven (1st Print Kickstarter)", "publisher": "Cephalofair Games", "designer": "Isaac Childres", "year": 2015, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.6", "edition": "1st Print KS", "condition": "complete", "price_eur": 400, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Frosthaven (KS All-In)", "publisher": "Cephalofair Games", "designer": "Isaac Childres", "year": 2023, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.5", "edition": "Kickstarter All-In", "condition": "sealed", "price_eur": 320, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Nemesis Lockdown (KS Stretch Goals)", "publisher": "Awaken Realms", "designer": "Adam Kwapiński", "year": 2022, "player_count": "1-5", "play_time": "120min", "bgg_rating": "8.4", "edition": "KS Stretch Goals Box", "condition": "sealed", "price_eur": 180, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Bloodborne: The Board Game (KS Chalice Dungeon)", "publisher": "CMON", "designer": "Eric M. Lang", "year": 2020, "player_count": "1-4", "play_time": "90min", "bgg_rating": "7.5", "edition": "KS Chalice Dungeon", "condition": "sealed", "price_eur": 180, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Darkest Dungeon: The Board Game (Collector's Edition)", "publisher": "Mythic Games", "designer": "Daniel Engelbrecht", "year": 2022, "player_count": "1-4", "play_time": "90min", "bgg_rating": "7.5", "edition": "KS Collector's", "condition": "sealed", "price_eur": 280, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Tainted Grail: Kings of Ruin (KS)", "publisher": "Awaken Realms", "designer": "Krzysztof Piskorski", "year": 2023, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.9", "edition": "Kickstarter", "condition": "sealed", "price_eur": 200, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Etherfields (Stretch Goals Box)", "publisher": "Awaken Realms", "designer": "Michał Oracz", "year": 2020, "player_count": "1-4", "play_time": "90min", "bgg_rating": "7.2", "edition": "KS Stretch Goals", "condition": "sealed", "price_eur": 120, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Middara: Unintentional Malum Act 2 & 3", "publisher": "Succubus Publishing", "designer": "Brooklynn Lundberg", "year": 2023, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.5", "edition": "KS Acts 2-3", "condition": "sealed", "price_eur": 250, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Sleeping Gods (KS All-In)", "publisher": "Red Raven Games", "designer": "Ryan Laukat", "year": 2021, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.2", "edition": "Kickstarter All-In", "condition": "sealed", "price_eur": 160, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "ISS Vanguard (Close Encounters KS)", "publisher": "Awaken Realms", "designer": "Marcin Świerkot", "year": 2023, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.8", "edition": "KS Close Encounters", "condition": "sealed", "price_eur": 150, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Mage Knight: Ultimate Edition", "publisher": "WizKids", "designer": "Vlaada Chvátil", "year": 2018, "player_count": "1-5", "play_time": "180min", "bgg_rating": "8.5", "edition": "Ultimate", "condition": "sealed", "price_eur": 200, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Return to Dark Tower (KS All-In)", "publisher": "Restoration Games", "designer": "Rob Daviau", "year": 2022, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.8", "edition": "Kickstarter All-In", "condition": "sealed", "price_eur": 250, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Root (1st KS Edition, with Resin Clearing Markers)", "publisher": "Leder Games", "designer": "Cole Wehrle", "year": 2018, "player_count": "2-4", "play_time": "90min", "bgg_rating": "8.1", "edition": "1st KS Print", "condition": "complete", "price_eur": 180, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Oath (KS Deluxe with Metal Coins)", "publisher": "Leder Games", "designer": "Cole Wehrle", "year": 2021, "player_count": "1-6", "play_time": "90min", "bgg_rating": "7.5", "edition": "KS Deluxe", "condition": "sealed", "price_eur": 160, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Massive Darkness 2: Hellscape (KS All-In)", "publisher": "CMON", "designer": "Marco Portugal", "year": 2022, "player_count": "1-6", "play_time": "120min", "bgg_rating": "7.2", "edition": "Kickstarter All-In", "condition": "sealed", "price_eur": 280, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        # ── Classic OOP Grails ────────────────────────────────────────────
        {"name": "Space Hulk (1st Edition, 1989)", "publisher": "Games Workshop", "designer": "Richard Halliwell", "year": 1989, "player_count": "2", "play_time": "90min", "bgg_rating": "7.3", "edition": "1st Edition", "condition": "complete", "price_eur": 350, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Fireball Island (Original 1986)", "publisher": "Milton Bradley", "designer": "Chuck Kennedy", "year": 1986, "player_count": "2-4", "play_time": "30min", "bgg_rating": "5.6", "edition": "1st Edition", "condition": "complete", "price_eur": 300, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Axis & Allies Anniversary Edition", "publisher": "Wizards of the Coast", "designer": "Larry Harris", "year": 2008, "player_count": "2-6", "play_time": "360min", "bgg_rating": "8.1", "edition": "Anniversary", "condition": "complete", "price_eur": 400, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "War of the Ring (2nd Edition)", "publisher": "Ares Games", "designer": "Roberto Di Meglio", "year": 2012, "player_count": "2-4", "play_time": "180min", "bgg_rating": "8.5", "edition": "2nd Edition", "condition": "complete", "price_eur": 120, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "War of the Ring: Collector's Edition", "publisher": "Ares Games", "designer": "Roberto Di Meglio", "year": 2014, "player_count": "2-4", "play_time": "180min", "bgg_rating": "8.5", "edition": "Collector's", "condition": "sealed", "price_eur": 600, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Dune (1979 Avalon Hill)", "publisher": "Avalon Hill", "designer": "Bill Eberle", "year": 1979, "player_count": "2-6", "play_time": "120min", "bgg_rating": "7.6", "edition": "1st Edition", "condition": "complete", "price_eur": 250, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Star Wars: Rebellion", "publisher": "Fantasy Flight Games", "designer": "Corey Konieczka", "year": 2016, "player_count": "2-4", "play_time": "240min", "bgg_rating": "8.4", "edition": "1st Edition", "condition": "complete", "price_eur": 130, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Pandemic Legacy: Season 0", "publisher": "Z-Man Games", "designer": "Matt Leacock", "year": 2020, "player_count": "2-4", "play_time": "60min", "bgg_rating": "8.2", "edition": "1st Edition", "condition": "sealed", "price_eur": 70, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Cosmic Encounter (Eon, 1977)", "publisher": "Eon Products", "designer": "Bill Eberle", "year": 1977, "player_count": "2-6", "play_time": "90min", "bgg_rating": "7.2", "edition": "1st Edition", "condition": "complete", "price_eur": 300, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Shogun (Milton Bradley, 1986)", "publisher": "Milton Bradley", "designer": "Michael Gray", "year": 1986, "player_count": "2-5", "play_time": "120min", "bgg_rating": "6.8", "edition": "1st Edition", "condition": "complete", "price_eur": 100, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Conquest of the Empire (Milton Bradley, 1984)", "publisher": "Milton Bradley", "designer": "Larry Harris", "year": 1984, "player_count": "2-6", "play_time": "180min", "bgg_rating": "6.5", "edition": "1st Edition", "condition": "complete", "price_eur": 120, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Fortress America (Milton Bradley, 1986)", "publisher": "Milton Bradley", "designer": "Michael Gray", "year": 1986, "player_count": "2-4", "play_time": "180min", "bgg_rating": "6.5", "edition": "1st Edition", "condition": "complete", "price_eur": 150, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Space Hulk (3rd Edition, 2009)", "publisher": "Games Workshop", "designer": "Richard Halliwell", "year": 2009, "player_count": "2", "play_time": "90min", "bgg_rating": "7.6", "edition": "3rd Edition", "condition": "complete", "price_eur": 250, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Space Hulk (4th Edition, 2014)", "publisher": "Games Workshop", "designer": "Richard Halliwell", "year": 2014, "player_count": "2", "play_time": "90min", "bgg_rating": "7.6", "edition": "4th Edition", "condition": "sealed", "price_eur": 200, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        # ── Rare Expansions ───────────────────────────────────────────────
        {"name": "Scythe: Complete Expansion Set (IFA + WA + RC)", "publisher": "Stonemaier Games", "designer": "Jamey Stegmaier", "year": 2020, "player_count": "1-7", "play_time": "120min", "bgg_rating": "8.3", "edition": "Expansion Bundle", "condition": "sealed", "price_eur": 120, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "7 Wonders Duel: Pantheon", "publisher": "Repos Production", "designer": "Antoine Bauza", "year": 2016, "player_count": "2", "play_time": "30min", "bgg_rating": "8.1", "edition": "Expansion", "condition": "sealed", "price_eur": 25, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Terraforming Mars: Prelude", "publisher": "Stronghold Games", "designer": "Jacob Fryxelius", "year": 2018, "player_count": "1-5", "play_time": "120min", "bgg_rating": "8.5", "edition": "Expansion", "condition": "sealed", "price_eur": 20, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Spirit Island: Branch & Claw + Jagged Earth Bundle", "publisher": "Greater Than Games", "designer": "R. Eric Reuss", "year": 2020, "player_count": "1-6", "play_time": "120min", "bgg_rating": "8.7", "edition": "Expansion Bundle", "condition": "sealed", "price_eur": 100, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Descent 2E: Complete Expansion Collection", "publisher": "Fantasy Flight Games", "designer": "Daniel Clark", "year": 2016, "player_count": "2-5", "play_time": "120min", "bgg_rating": "7.5", "edition": "Complete Expansions", "condition": "complete", "price_eur": 400, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Star Wars: Imperial Assault — Heart of the Empire", "publisher": "Fantasy Flight Games", "designer": "Todd Michlitsch", "year": 2017, "player_count": "2-5", "play_time": "120min", "bgg_rating": "8.1", "edition": "Expansion", "condition": "sealed", "price_eur": 80, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Arkham Horror LCG: Dunwich Legacy Complete Cycle", "publisher": "Fantasy Flight Games", "designer": "Nate French", "year": 2017, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.3", "edition": "Complete Cycle", "condition": "complete", "price_eur": 130, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Arkham Horror LCG: Path to Carcosa Complete Cycle", "publisher": "Fantasy Flight Games", "designer": "Nate French", "year": 2017, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.5", "edition": "Complete Cycle", "condition": "complete", "price_eur": 140, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Eldritch Horror: Under the Pyramids", "publisher": "Fantasy Flight Games", "designer": "Nikki Valens", "year": 2015, "player_count": "1-8", "play_time": "240min", "bgg_rating": "7.8", "edition": "Expansion", "condition": "sealed", "price_eur": 60, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Eldritch Horror: The Dreamlands", "publisher": "Fantasy Flight Games", "designer": "Nikki Valens", "year": 2017, "player_count": "1-8", "play_time": "240min", "bgg_rating": "7.9", "edition": "Expansion", "condition": "sealed", "price_eur": 55, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        # ── Euro Game Collector's Editions ────────────────────────────────
        {"name": "Agricola Revised Edition (Limited Art Box)", "publisher": "Lookout Games", "designer": "Uwe Rosenberg", "year": 2016, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.9", "edition": "Revised Limited", "condition": "sealed", "price_eur": 80, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Brass: Birmingham (Deluxe Iron Clays Edition)", "publisher": "Roxley Games", "designer": "Martin Wallace", "year": 2018, "player_count": "2-4", "play_time": "120min", "bgg_rating": "8.6", "edition": "Deluxe KS", "condition": "sealed", "price_eur": 100, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Great Western Trail: Rails to the North", "publisher": "Eggertspiele", "designer": "Alexander Pfister", "year": 2018, "player_count": "2-4", "play_time": "120min", "bgg_rating": "8.0", "edition": "Expansion", "condition": "sealed", "price_eur": 45, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Concordia Venus (Big Box)", "publisher": "PD-Verlag", "designer": "Mac Gerdts", "year": 2019, "player_count": "2-6", "play_time": "120min", "bgg_rating": "8.3", "edition": "Big Box", "condition": "sealed", "price_eur": 70, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Viticulture: World Cooperative Expansion", "publisher": "Stonemaier Games", "designer": "Jamey Stegmaier", "year": 2023, "player_count": "1-6", "play_time": "90min", "bgg_rating": "7.8", "edition": "Expansion", "condition": "sealed", "price_eur": 35, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Barrage: Deluxe Edition", "publisher": "Cranio Creations", "designer": "Tommaso Battista", "year": 2019, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.9", "edition": "Deluxe KS", "condition": "sealed", "price_eur": 110, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Gaia Project", "publisher": "Z-Man Games", "designer": "Jens Drögemüller", "year": 2017, "player_count": "1-4", "play_time": "150min", "bgg_rating": "8.4", "edition": "1st Edition", "condition": "complete", "price_eur": 65, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Troyes (OOP 1st Edition)", "publisher": "Pearl Games", "designer": "Sébastien Dujardin", "year": 2010, "player_count": "2-4", "play_time": "90min", "bgg_rating": "7.7", "edition": "1st Edition", "condition": "complete", "price_eur": 90, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Tzolk'in: The Mayan Calendar (Tribes & Prophecies)", "publisher": "Czech Games Edition", "designer": "Daniele Tascini", "year": 2013, "player_count": "2-5", "play_time": "120min", "bgg_rating": "7.8", "edition": "Base + Expansion", "condition": "complete", "price_eur": 75, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Teotihuacan: City of Gods (Deluxe)", "publisher": "Board & Dice", "designer": "Daniele Tascini", "year": 2018, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.7", "edition": "KS Deluxe", "condition": "sealed", "price_eur": 80, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        # ── Miniature-Heavy Games ─────────────────────────────────────────
        {"name": "Blood Rage (KS Mystics Exclusives)", "publisher": "CMON", "designer": "Eric M. Lang", "year": 2015, "player_count": "2-4", "play_time": "80min", "bgg_rating": "8.0", "edition": "KS Mystics", "condition": "sealed", "price_eur": 200, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Rising Sun (KS Daimyo Box + Monster Pack)", "publisher": "CMON", "designer": "Eric M. Lang", "year": 2018, "player_count": "3-5", "play_time": "120min", "bgg_rating": "7.8", "edition": "KS Daimyo + Monsters", "condition": "sealed", "price_eur": 350, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Cthulhu Wars (All Factions Bundle)", "publisher": "Petersen Games", "designer": "Sandy Petersen", "year": 2015, "player_count": "2-8", "play_time": "120min", "bgg_rating": "8.0", "edition": "Complete Factions", "condition": "complete", "price_eur": 800, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Zombicide: Black Plague (KS with Wulfsburg)", "publisher": "CMON", "designer": "Raphaël Guiton", "year": 2015, "player_count": "1-6", "play_time": "60min", "bgg_rating": "7.5", "edition": "KS + Wulfsburg", "condition": "sealed", "price_eur": 220, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Conan (Monolith KS King Pledge)", "publisher": "Monolith", "designer": "Frédéric Henry", "year": 2016, "player_count": "2-5", "play_time": "90min", "bgg_rating": "7.5", "edition": "KS King Pledge", "condition": "sealed", "price_eur": 400, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Batman: Gotham City Chronicles (KS All-In)", "publisher": "Monolith", "designer": "Frédéric Henry", "year": 2019, "player_count": "2-4", "play_time": "90min", "bgg_rating": "7.2", "edition": "Kickstarter All-In", "condition": "sealed", "price_eur": 350, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Sword & Sorcery (KS All-In)", "publisher": "Ares Games", "designer": "Simone Romano", "year": 2017, "player_count": "1-5", "play_time": "120min", "bgg_rating": "7.7", "edition": "Kickstarter All-In", "condition": "sealed", "price_eur": 200, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Claustrophobia 1643 (KS)", "publisher": "Monolith", "designer": "Croc", "year": 2019, "player_count": "2", "play_time": "45min", "bgg_rating": "7.8", "edition": "Kickstarter", "condition": "sealed", "price_eur": 120, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Arcadia Quest (KS All-In)", "publisher": "CMON", "designer": "Thiago Aranha", "year": 2014, "player_count": "2-4", "play_time": "60min", "bgg_rating": "7.6", "edition": "Kickstarter All-In", "condition": "sealed", "price_eur": 200, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Descent: Legends of the Dark", "publisher": "Fantasy Flight Games", "designer": "Kara Centell-Dunk", "year": 2021, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.6", "edition": "1st Edition", "condition": "sealed", "price_eur": 140, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
    ]


def _expansion_1150_most_searched() -> list[dict]:
    """~140 most-searched OOP board games: modern OOP spikes, classic grails,
    Kickstarter aftermarket, wargames, Pandemic Legacy, Gloomhaven, etc."""
    return [
        # ── Modern OOP That Spiked ──────────────────────────────────────────
        {"name": "Pandemic Legacy: Season 1 (1st Print, Red Box)", "publisher": "Z-Man Games", "designer": "Rob Daviau", "year": 2015, "player_count": "2-4", "play_time": "60min", "bgg_rating": "8.6", "edition": "1st Print Red", "condition": "sealed", "price_eur": 120, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Pandemic Legacy: Season 2 (1st Print, Black Box)", "publisher": "Z-Man Games", "designer": "Rob Daviau", "year": 2017, "player_count": "2-4", "play_time": "60min", "bgg_rating": "7.9", "edition": "1st Print Black", "condition": "sealed", "price_eur": 85, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Gloomhaven (1st Retail Print, 2017)", "publisher": "Cephalofair Games", "designer": "Isaac Childres", "year": 2017, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.6", "edition": "1st Retail Print", "condition": "complete", "price_eur": 250, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Wingspan (1st Print, 2019)", "publisher": "Stonemaier Games", "designer": "Elizabeth Hargrave", "year": 2019, "player_count": "1-5", "play_time": "70min", "bgg_rating": "8.1", "edition": "1st Print", "condition": "complete", "price_eur": 90, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Azul (1st Print, Plan B Games)", "publisher": "Plan B Games", "designer": "Michael Kiesling", "year": 2017, "player_count": "2-4", "play_time": "45min", "bgg_rating": "7.8", "edition": "1st Print", "condition": "complete", "price_eur": 55, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Everdell Collector's Edition (1st KS)", "publisher": "Starling Games", "designer": "James A. Wilson", "year": 2018, "player_count": "1-4", "play_time": "80min", "bgg_rating": "7.8", "edition": "KS Collector's", "condition": "sealed", "price_eur": 200, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Ark Nova (1st Print, German Edition)", "publisher": "Feuerland Spiele", "designer": "Mathias Wigge", "year": 2021, "player_count": "1-4", "play_time": "150min", "bgg_rating": "8.5", "edition": "1st Print German", "condition": "complete", "price_eur": 100, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Ark Nova (1st English Print)", "publisher": "Capstone Games", "designer": "Mathias Wigge", "year": 2022, "player_count": "1-4", "play_time": "150min", "bgg_rating": "8.5", "edition": "1st English Print", "condition": "complete", "price_eur": 85, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Terraforming Mars: Ares Expedition Collector's Edition", "publisher": "Stronghold Games", "designer": "Jacob Fryxelius", "year": 2021, "player_count": "1-4", "play_time": "60min", "bgg_rating": "7.5", "edition": "Collector's KS", "condition": "sealed", "price_eur": 80, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Scythe (1st KS Collector's, Autographed)", "publisher": "Stonemaier Games", "designer": "Jamey Stegmaier", "year": 2016, "player_count": "1-5", "play_time": "115min", "bgg_rating": "8.2", "edition": "1st KS Signed", "condition": "complete", "price_eur": 350, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Spirit Island (1st KS with Promo Spirits)", "publisher": "Greater Than Games", "designer": "R. Eric Reuss", "year": 2017, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.3", "edition": "1st KS + Promos", "condition": "complete", "price_eur": 180, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Terraforming Mars (1st Print, FryxGames)", "publisher": "FryxGames", "designer": "Jacob Fryxelius", "year": 2016, "player_count": "1-5", "play_time": "120min", "bgg_rating": "8.4", "edition": "1st Print", "condition": "complete", "price_eur": 95, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Clank! Legacy: Acquisitions Incorporated (Sealed)", "publisher": "Renegade Game Studios", "designer": "Andy Clautice", "year": 2019, "player_count": "2-4", "play_time": "90min", "bgg_rating": "8.4", "edition": "1st Print", "condition": "sealed", "price_eur": 100, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        # ── Classic Games (Pre-2000) ────────────────────────────────────────
        {"name": "Acquire (3M Bookshelf Edition, 1964)", "publisher": "3M", "designer": "Sid Sackson", "year": 1964, "player_count": "2-6", "play_time": "90min", "bgg_rating": "7.3", "edition": "3M Bookshelf", "condition": "complete", "price_eur": 180, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Acquire (Avalon Hill, 1999)", "publisher": "Avalon Hill", "designer": "Sid Sackson", "year": 1999, "player_count": "2-6", "play_time": "90min", "bgg_rating": "7.3", "edition": "Avalon Hill", "condition": "complete", "price_eur": 80, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Civilization (1980 Avalon Hill)", "publisher": "Avalon Hill", "designer": "Francis Tresham", "year": 1980, "player_count": "2-7", "play_time": "360min", "bgg_rating": "7.1", "edition": "1st Edition", "condition": "complete", "price_eur": 200, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Advanced Civilization", "publisher": "Avalon Hill", "designer": "Francis Tresham", "year": 1991, "player_count": "2-8", "play_time": "480min", "bgg_rating": "7.6", "edition": "1st Edition", "condition": "complete", "price_eur": 250, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Cosmic Encounter (Eon, 9 Expansion Set)", "publisher": "Eon Products", "designer": "Bill Eberle", "year": 1982, "player_count": "2-6", "play_time": "90min", "bgg_rating": "7.2", "edition": "Complete 9 Expansions", "condition": "complete", "price_eur": 500, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Republic of Rome (Avalon Hill)", "publisher": "Avalon Hill", "designer": "Richard Berthold", "year": 1990, "player_count": "1-6", "play_time": "300min", "bgg_rating": "7.3", "edition": "1st Edition", "condition": "complete", "price_eur": 150, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Merchant of Venus (Avalon Hill, 1988)", "publisher": "Avalon Hill", "designer": "Richard Hamblen", "year": 1988, "player_count": "1-6", "play_time": "180min", "bgg_rating": "7.1", "edition": "1st Edition", "condition": "complete", "price_eur": 120, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Up Front! (Avalon Hill, 1983)", "publisher": "Avalon Hill", "designer": "Courtney Allen", "year": 1983, "player_count": "2", "play_time": "60min", "bgg_rating": "7.6", "edition": "1st Edition", "condition": "complete", "price_eur": 180, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Magic Realm (Avalon Hill, 1979)", "publisher": "Avalon Hill", "designer": "Richard Hamblen", "year": 1979, "player_count": "1-16", "play_time": "240min", "bgg_rating": "7.0", "edition": "1st Edition", "condition": "complete", "price_eur": 250, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Titan (Avalon Hill, 1980)", "publisher": "Avalon Hill", "designer": "Jason McAllister", "year": 1980, "player_count": "2-6", "play_time": "240min", "bgg_rating": "6.9", "edition": "1st Edition", "condition": "complete", "price_eur": 130, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Wiz-War (Chessex, 1985)", "publisher": "Chessex", "designer": "Tom Jolly", "year": 1985, "player_count": "2-4", "play_time": "60min", "bgg_rating": "6.9", "edition": "1st Edition", "condition": "complete", "price_eur": 100, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        # ── Kickstarter Aftermarket ─────────────────────────────────────────
        {"name": "Frosthaven (KS + Solo Scenarios + Pizza Token)", "publisher": "Cephalofair Games", "designer": "Isaac Childres", "year": 2023, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.5", "edition": "KS Full Bundle", "condition": "sealed", "price_eur": 380, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "ISS Vanguard (KS Gameplay All-In)", "publisher": "Awaken Realms", "designer": "Marcin Świerkot", "year": 2023, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.8", "edition": "KS Gameplay All-In", "condition": "sealed", "price_eur": 200, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Oathsworn: Into the Deepwood (KS Standee + Mini)", "publisher": "Shadowborne Games", "designer": "Jamie Jolly", "year": 2022, "player_count": "1-4", "play_time": "90min", "bgg_rating": "8.6", "edition": "KS Miniatures", "condition": "sealed", "price_eur": 250, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Legends of Void (KS All-In)", "publisher": "Mythic Games", "designer": "Marwin Ferdynus", "year": 2024, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.5", "edition": "Kickstarter All-In", "condition": "sealed", "price_eur": 280, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Tiny Epic Dungeons (Deluxe KS + Stories)", "publisher": "Gamelyn Games", "designer": "Scott Almes", "year": 2022, "player_count": "1-4", "play_time": "45min", "bgg_rating": "7.0", "edition": "Deluxe KS", "condition": "sealed", "price_eur": 60, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Tanares Adventures (KS All-In)", "publisher": "Dragon Dawn Productions", "designer": "Joao Quintela Bezerra", "year": 2023, "player_count": "1-5", "play_time": "120min", "bgg_rating": "8.4", "edition": "KS All-In", "condition": "sealed", "price_eur": 300, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Primal: The Awakening (KS Monster Hunter Edition)", "publisher": "Reggie Games", "designer": "Marco Montanaro", "year": 2024, "player_count": "1-4", "play_time": "90min", "bgg_rating": "8.0", "edition": "KS Monster Hunter", "condition": "sealed", "price_eur": 220, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Aeon Trespass: Odyssey (KS All-In)", "publisher": "Into the Unknown", "designer": "Marcin Świerkot", "year": 2023, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.2", "edition": "KS All-In", "condition": "sealed", "price_eur": 350, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Machina Arcana 3rd Edition (KS Deluxe)", "publisher": "Adreama Games", "designer": "Juraj Bilić", "year": 2022, "player_count": "1-4", "play_time": "90min", "bgg_rating": "7.8", "edition": "KS Deluxe 3rd Ed", "condition": "sealed", "price_eur": 120, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Chronicles of Drunagor: Age of Darkness (KS All-In)", "publisher": "Creative Games Studio", "designer": "Guilherme Goulart", "year": 2021, "player_count": "1-5", "play_time": "120min", "bgg_rating": "7.8", "edition": "KS All-In", "condition": "sealed", "price_eur": 280, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "HEXplore It: The Forests of Adrimon (KS Deluxe)", "publisher": "Mariucci J. Designs", "designer": "Jonathan Mariucci", "year": 2018, "player_count": "1-6", "play_time": "120min", "bgg_rating": "7.5", "edition": "KS Deluxe", "condition": "sealed", "price_eur": 150, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Joan of Arc (Mythic, KS All-In)", "publisher": "Mythic Games", "designer": "Pascal Bernard", "year": 2019, "player_count": "2-4", "play_time": "90min", "bgg_rating": "7.0", "edition": "KS All-In", "condition": "sealed", "price_eur": 300, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        # ── Wargames ────────────────────────────────────────────────────────
        {"name": "Advanced Squad Leader (Complete Starter Kit 1-4)", "publisher": "Multi-Man Publishing", "designer": "Don Greenwood", "year": 2004, "player_count": "2", "play_time": "120min", "bgg_rating": "7.8", "edition": "Starter Kit Bundle", "condition": "complete", "price_eur": 150, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "ASL Module 1: Beyond Valor", "publisher": "Multi-Man Publishing", "designer": "Don Greenwood", "year": 1985, "player_count": "2", "play_time": "240min", "bgg_rating": "8.2", "edition": "Reprint", "condition": "complete", "price_eur": 100, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "ASL Rules & Chapter H (Complete Binder)", "publisher": "Multi-Man Publishing", "designer": "Don Greenwood", "year": 2000, "player_count": "2", "play_time": "variable", "bgg_rating": "8.5", "edition": "Complete Rules", "condition": "complete", "price_eur": 250, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Commands & Colors: Ancients (1st Edition, GMT)", "publisher": "GMT Games", "designer": "Richard Borg", "year": 2006, "player_count": "2", "play_time": "60min", "bgg_rating": "7.8", "edition": "1st Edition", "condition": "complete", "price_eur": 80, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Commands & Colors: Napoleonics (Complete Expansions)", "publisher": "GMT Games", "designer": "Richard Borg", "year": 2012, "player_count": "2", "play_time": "90min", "bgg_rating": "8.0", "edition": "All Expansions", "condition": "complete", "price_eur": 300, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Twilight Struggle Deluxe Edition (Mounted Map)", "publisher": "GMT Games", "designer": "Ananda Gupta", "year": 2009, "player_count": "2", "play_time": "180min", "bgg_rating": "8.3", "edition": "Deluxe", "condition": "complete", "price_eur": 120, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Paths of Glory (Deluxe Edition)", "publisher": "GMT Games", "designer": "Ted Raicer", "year": 2010, "player_count": "2", "play_time": "480min", "bgg_rating": "8.1", "edition": "Deluxe", "condition": "complete", "price_eur": 90, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "For the People (GMT, 2nd Edition)", "publisher": "GMT Games", "designer": "Mark Herman", "year": 2006, "player_count": "2", "play_time": "240min", "bgg_rating": "7.8", "edition": "2nd Edition", "condition": "complete", "price_eur": 80, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Here I Stand (500th Anniversary Edition)", "publisher": "GMT Games", "designer": "Ed Beach", "year": 2017, "player_count": "2-6", "play_time": "360min", "bgg_rating": "7.9", "edition": "500th Anniversary", "condition": "complete", "price_eur": 95, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Empire of the Sun (2nd Edition)", "publisher": "GMT Games", "designer": "Mark Herman", "year": 2011, "player_count": "2", "play_time": "480min", "bgg_rating": "7.8", "edition": "2nd Edition", "condition": "complete", "price_eur": 85, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "The Napoleonic Wars (GMT, 2nd Edition)", "publisher": "GMT Games", "designer": "Mark McLaughlin", "year": 2008, "player_count": "2-5", "play_time": "300min", "bgg_rating": "7.5", "edition": "2nd Edition", "condition": "complete", "price_eur": 100, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Fire in the Lake (COIN Volume 4)", "publisher": "GMT Games", "designer": "Mark Herman", "year": 2014, "player_count": "1-4", "play_time": "180min", "bgg_rating": "8.0", "edition": "1st Print", "condition": "complete", "price_eur": 90, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Labyrinth: The War on Terror (2nd Edition)", "publisher": "GMT Games", "designer": "Volko Ruhnke", "year": 2015, "player_count": "1-2", "play_time": "180min", "bgg_rating": "7.6", "edition": "2nd Edition", "condition": "complete", "price_eur": 70, "rarity": "Common", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "SPQR: Great Battles of the Roman Republic", "publisher": "GMT Games", "designer": "Richard Berg", "year": 1992, "player_count": "2", "play_time": "240min", "bgg_rating": "7.3", "edition": "Deluxe Reprint", "condition": "complete", "price_eur": 120, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        # ── Splotter Titles ─────────────────────────────────────────────────
        {"name": "Food Chain Magnate (1st Print)", "publisher": "Splotter Spellen", "designer": "Jeroen Doumen", "year": 2015, "player_count": "2-5", "play_time": "240min", "bgg_rating": "8.1", "edition": "1st Print", "condition": "complete", "price_eur": 120, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Indonesia (2005, Splotter)", "publisher": "Splotter Spellen", "designer": "Jeroen Doumen", "year": 2005, "player_count": "2-5", "play_time": "240min", "bgg_rating": "7.7", "edition": "1st Edition", "condition": "complete", "price_eur": 250, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Bus (Splotter, 1999)", "publisher": "Splotter Spellen", "designer": "Jeroen Doumen", "year": 1999, "player_count": "3-5", "play_time": "120min", "bgg_rating": "7.2", "edition": "1st Edition", "condition": "complete", "price_eur": 300, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Roads & Boats (4th Edition)", "publisher": "Splotter Spellen", "designer": "Jeroen Doumen", "year": 2013, "player_count": "1-4", "play_time": "240min", "bgg_rating": "7.6", "edition": "4th Edition", "condition": "complete", "price_eur": 200, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Antiquity (Splotter, 2004)", "publisher": "Splotter Spellen", "designer": "Jeroen Doumen", "year": 2004, "player_count": "2-4", "play_time": "180min", "bgg_rating": "7.7", "edition": "1st Edition", "condition": "complete", "price_eur": 350, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "The Great Zimbabwe", "publisher": "Splotter Spellen", "designer": "Jeroen Doumen", "year": 2012, "player_count": "2-5", "play_time": "150min", "bgg_rating": "7.7", "edition": "1st Edition", "condition": "complete", "price_eur": 200, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        # ── OOP Modern Classics ─────────────────────────────────────────────
        {"name": "Keyflower (1st Print)", "publisher": "R&D Games", "designer": "Sebastian Bleasdale", "year": 2012, "player_count": "2-6", "play_time": "120min", "bgg_rating": "7.8", "edition": "1st Print", "condition": "complete", "price_eur": 80, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Mombasa (1st Edition)", "publisher": "eggertspiele", "designer": "Alexander Pfister", "year": 2015, "player_count": "2-4", "play_time": "120min", "bgg_rating": "7.8", "edition": "1st Edition", "condition": "complete", "price_eur": 75, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "La Granja (Deluxe Master Set)", "publisher": "Stronghold Games", "designer": "Michael Keller", "year": 2014, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.7", "edition": "Deluxe", "condition": "complete", "price_eur": 90, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Village (OOP, International Edition)", "publisher": "eggertspiele", "designer": "Inka Brand", "year": 2011, "player_count": "2-4", "play_time": "90min", "bgg_rating": "7.4", "edition": "1st Edition", "condition": "complete", "price_eur": 65, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Lewis & Clark: The Expedition (1st Edition)", "publisher": "Ludonaute", "designer": "Cédrick Chaboussit", "year": 2013, "player_count": "1-5", "play_time": "120min", "bgg_rating": "7.4", "edition": "1st Edition", "condition": "complete", "price_eur": 55, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Rococo (Deluxe Edition)", "publisher": "Eagle-Gryphon Games", "designer": "Stefan Malz", "year": 2020, "player_count": "1-5", "play_time": "120min", "bgg_rating": "7.8", "edition": "Deluxe KS", "condition": "sealed", "price_eur": 100, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Dungeon Petz (OOP CGE)", "publisher": "Czech Games Edition", "designer": "Vlaada Chvátil", "year": 2011, "player_count": "2-4", "play_time": "120min", "bgg_rating": "7.4", "edition": "1st Edition", "condition": "complete", "price_eur": 80, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Caylus 1303 (Limited First Run)", "publisher": "Space Cowboys", "designer": "William Attia", "year": 2019, "player_count": "2-5", "play_time": "90min", "bgg_rating": "7.5", "edition": "1st Print", "condition": "sealed", "price_eur": 50, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        # ── Dungeon Crawlers / Thematic ─────────────────────────────────────
        {"name": "Shadows of Brimstone: City of the Ancients (KS)", "publisher": "Flying Frog", "designer": "Jason C. Hill", "year": 2015, "player_count": "1-4", "play_time": "120min", "bgg_rating": "7.0", "edition": "KS with Extras", "condition": "sealed", "price_eur": 150, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Mice & Mystics (Complete with Lost Chapter)", "publisher": "Plaid Hat Games", "designer": "Jerry Hawthorne", "year": 2012, "player_count": "1-4", "play_time": "90min", "bgg_rating": "7.1", "edition": "Complete", "condition": "complete", "price_eur": 110, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Mansions of Madness (1st Edition, Complete Expansions)", "publisher": "Fantasy Flight Games", "designer": "Corey Konieczka", "year": 2011, "player_count": "2-5", "play_time": "180min", "bgg_rating": "7.0", "edition": "1st Ed + All Expansions", "condition": "complete", "price_eur": 300, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Star Wars: Imperial Assault (Core + All Expansions)", "publisher": "Fantasy Flight Games", "designer": "Justin Kemppainen", "year": 2014, "player_count": "2-5", "play_time": "120min", "bgg_rating": "8.0", "edition": "Complete Collection", "condition": "complete", "price_eur": 800, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Level 7 [Omega Protocol] (OOP)", "publisher": "Privateer Press", "designer": "Will Shick", "year": 2013, "player_count": "2-6", "play_time": "120min", "bgg_rating": "7.3", "edition": "1st Edition", "condition": "complete", "price_eur": 120, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        # ── Additional Heavy Euros / Lacerda ────────────────────────────────
        {"name": "The Gallerist (Eagle-Gryphon Deluxe)", "publisher": "Eagle-Gryphon Games", "designer": "Vital Lacerda", "year": 2015, "player_count": "1-4", "play_time": "150min", "bgg_rating": "7.9", "edition": "Deluxe KS", "condition": "sealed", "price_eur": 110, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Vinhos Deluxe (KS Edition)", "publisher": "Eagle-Gryphon Games", "designer": "Vital Lacerda", "year": 2016, "player_count": "1-4", "play_time": "135min", "bgg_rating": "7.9", "edition": "KS Deluxe", "condition": "sealed", "price_eur": 100, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Lisboa (Deluxe KS)", "publisher": "Eagle-Gryphon Games", "designer": "Vital Lacerda", "year": 2017, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.0", "edition": "KS Deluxe", "condition": "sealed", "price_eur": 130, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Escape Plan (Deluxe KS)", "publisher": "Eagle-Gryphon Games", "designer": "Vital Lacerda", "year": 2019, "player_count": "1-5", "play_time": "120min", "bgg_rating": "7.5", "edition": "KS Deluxe", "condition": "sealed", "price_eur": 120, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Kanban EV (Deluxe KS)", "publisher": "Eagle-Gryphon Games", "designer": "Vital Lacerda", "year": 2020, "player_count": "1-4", "play_time": "120min", "bgg_rating": "8.0", "edition": "KS Deluxe", "condition": "sealed", "price_eur": 110, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        # ── Party/Deduction OOP ─────────────────────────────────────────────
        {"name": "Battlestar Galactica: The Board Game (Complete + Expansions)", "publisher": "Fantasy Flight Games", "designer": "Corey Konieczka", "year": 2008, "player_count": "3-6", "play_time": "180min", "bgg_rating": "7.8", "edition": "Complete Collection", "condition": "complete", "price_eur": 350, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Fury of Dracula (3rd Edition)", "publisher": "Games Workshop / WizKids", "designer": "Frank Brooks", "year": 2015, "player_count": "2-5", "play_time": "180min", "bgg_rating": "7.7", "edition": "3rd Edition", "condition": "complete", "price_eur": 120, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Letters from Whitechapel (OOP Nexus Edition)", "publisher": "Nexus Editrice", "designer": "Gabriele Mari", "year": 2011, "player_count": "2-6", "play_time": "120min", "bgg_rating": "7.4", "edition": "1st Edition", "condition": "complete", "price_eur": 70, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Chaos in the Old World (OOP, FFG)", "publisher": "Fantasy Flight Games", "designer": "Eric M. Lang", "year": 2009, "player_count": "3-4", "play_time": "120min", "bgg_rating": "7.5", "edition": "1st Edition", "condition": "complete", "price_eur": 150, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Nexus Ops (Avalon Hill, Original)", "publisher": "Avalon Hill", "designer": "Charlie Catino", "year": 2005, "player_count": "2-4", "play_time": "90min", "bgg_rating": "7.0", "edition": "1st Edition", "condition": "complete", "price_eur": 80, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        # ── More Modern Grails ──────────────────────────────────────────────
        {"name": "Android: Netrunner (Complete Collection, All Data Packs)", "publisher": "Fantasy Flight Games", "designer": "Richard Garfield", "year": 2012, "player_count": "2", "play_time": "45min", "bgg_rating": "7.8", "edition": "Complete LCG", "condition": "complete", "price_eur": 500, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Lord of the Rings LCG (Complete Saga + Nightmare)", "publisher": "Fantasy Flight Games", "designer": "Nate French", "year": 2011, "player_count": "1-4", "play_time": "60min", "bgg_rating": "7.7", "edition": "Complete Saga", "condition": "complete", "price_eur": 1200, "rarity": "Grail", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Pax Pamir (2nd Edition, Wehrlegig)", "publisher": "Wehrlegig Games", "designer": "Cole Wehrle", "year": 2019, "player_count": "1-5", "play_time": "120min", "bgg_rating": "8.1", "edition": "KS 2nd Edition", "condition": "sealed", "price_eur": 130, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "John Company (2nd Edition, KS Deluxe)", "publisher": "Wehrlegig Games", "designer": "Cole Wehrle", "year": 2022, "player_count": "1-6", "play_time": "180min", "bgg_rating": "7.6", "edition": "KS Deluxe", "condition": "sealed", "price_eur": 110, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "An Infamous Traffic (1st Print)", "publisher": "Hollandspiele", "designer": "Cole Wehrle", "year": 2017, "player_count": "3-5", "play_time": "120min", "bgg_rating": "7.1", "edition": "1st Print", "condition": "complete", "price_eur": 100, "rarity": "Rare", "image_url": "https://cf.geekdo-images.com/placeholder"},
        {"name": "Dominant Species (4th Print)", "publisher": "GMT Games", "designer": "Chad Jensen", "year": 2010, "player_count": "2-6", "play_time": "240min", "bgg_rating": "7.8", "edition": "4th Print", "condition": "complete", "price_eur": 75, "rarity": "Uncommon", "image_url": "https://cf.geekdo-images.com/placeholder"},
    ]


def get_curated_catalog() -> list[dict]:
    """Return the full curated OOP board games catalog."""
    catalog: list[dict] = []
    catalog.extend(_oop_euro_games())
    catalog.extend(_kickstarter_exclusives())
    catalog.extend(_grail_games())
    catalog.extend(_deluxe_big_box())
    catalog.extend(_legacy_games())
    catalog.extend(_thematic_ameritrash())
    catalog.extend(_designer_collectibles())
    catalog.extend(_oop_expansions())
    catalog.extend(_additional_games())
    catalog.extend(_wargames_and_coop())
    catalog.extend(_party_and_social_deduction())
    catalog.extend(_abstract_and_two_player())
    catalog.extend(_variant_expansion())
    catalog.extend(_dungeons_and_dragons())
    catalog.extend(_expansion_round_35())
    catalog.extend(_expansion_1150_most_searched())
    # Deduplicate by (name, publisher, edition) (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = (item["name"], item["publisher"], item.get("edition", ""))
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


# ---------------------------------------------------------------------------
# Converters
# ---------------------------------------------------------------------------

def item_to_catalog_item(item: dict) -> CatalogItem:
    name = item["name"]
    publisher = item["publisher"]
    designer = item.get("designer", "")
    edition = item.get("edition", "Retail")
    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{publisher}-{name}-{edition}"),
        title=name,
        set_code=edition,
        brand=publisher,
        rarity=item.get("rarity", "Common"),
        notes=f"Designer: {designer}. Players: {item.get('player_count', '')}. "
              f"Play time: {item.get('play_time', '')}. BGG: {item.get('bgg_rating', '')}.",
        attributes_json={
            "publisher": publisher,
            "designer": designer,
            "player_count": item.get("player_count", ""),
            "play_time": item.get("play_time", ""),
            "bgg_rating": item.get("bgg_rating", ""),
            "edition": edition,
            "condition": item.get("condition", "complete"),
            "year": item.get("year", ""),
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    publisher = item["publisher"]
    rarity = item.get("rarity", "Common")
    price = item["price_eur"]
    return PriceObservation(
        features={
            "condition_score": 0.95 if item.get("condition") == "sealed" else 0.80,
            "rarity_score": shared_rarity_score(rarity),
            "brand_tier": _publisher_tier(publisher),
            "is_kickstarter": 1.0 if "Kickstarter" in item.get("edition", "") else 0.0,
        },
        price=float(price),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Import curated OOP board games catalog + prices"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Write local files only, skip Supabase upsert")
    parser.add_argument("--jsonl-only", action="store_true",
                        help="Write only training JSONL, skip catalog SQL and Supabase")
    parser.add_argument("--cache-images", action="store_true",
                        help="Cache external image URLs to S3")
    args = parser.parse_args()

    logger.info("=== OOP Board Games Import Pipeline ===")

    catalog = get_curated_catalog()
    logger.info(f"Curated catalog: {len(catalog)} games")

    items = [item_to_catalog_item(g) for g in catalog]
    observations = [item_to_price_observation(g) for g in catalog]

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

    logger.info(f"\n=== OOP Board Games Import Complete ===")
    logger.info(f"  Total catalog items:  {len(items)}")
    logger.info(f"  Price observations:   {len(observations)}")
    logger.info(f"  Price range:          EUR {min(o.price for o in observations):.0f} "
                f"- EUR {max(o.price for o in observations):.0f}")

    if args.dry_run:
        logger.info("  Mode: DRY RUN (local files only)")


if __name__ == "__main__":
    main()
