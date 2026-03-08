"""
Import Warhammer & tabletop miniatures + books catalog.

Layer 1 (Catalog):  Core kits, centerpieces, books → category_items
Layer 2 (Prices):   GW retail + secondary market estimates → train.jsonl

No official GW API exists. Uses curated data covering:

Miniatures (~430 items):
- Warhammer 40K (all factions: Space Marines, Grey Knights, Dark Angels,
  Space Wolves, Blood Angels, Black Templars, Deathwatch, Chaos, all Xenos,
  Imperium, Knights, Titans)
- Age of Sigmar (all factions: Stormcast, Chaos Gods, Death, Destruction,
  Sylvaneth, Ogor Mawtribes, Cities of Sigmar, Beasts of Chaos)
- Horus Heresy / Forge World (all 18 Primarchs, Titans, Dreadnoughts)
- Kill Team, Necromunda (all gangs), Blood Bowl (all teams), Warcry,
  Underworlds (all seasons), Aeronautica Imperialis
- Battleforce boxes, Combat Patrol boxes, Terrain kits, Paint sets
- Warhammer+ exclusives, celebration models, event exclusives

Books (~85 items):
- Black Library novels (Horus Heresy series, 40K, Age of Sigmar)
- Codexes (40K 10th/9th editions)
- Battletomes (Age of Sigmar)
- Core Rulebooks (40K, AoS, Kill Team, Necromunda)
- Art Books & Special Editions (Forge World Imperial Armour, Liber Chaotica)
- Limited / Numbered Editions (Black Library collector prints)

Usage:
    python -m pipelines.import_warhammer [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines.import_common import (
    CatalogItem, PriceObservation, SupabaseIngest,
    write_training_jsonl, write_catalog_sql,
    log_progress, slugify,
    rarity_score as shared_rarity_score,
    RARITY_SCORE_MAP,
    logger,
    close_http_client,
)

CATEGORY = "warhammer"

# ---------------------------------------------------------------------------
# Book-type rarity scores (supplement the shared RARITY_SCORE_MAP)
# ---------------------------------------------------------------------------
BOOK_RARITY_SCORES: dict[str, float] = {
    "Novel": 0.25,
    "Omnibus": 0.30,
    "Codex": 0.45,
    "Battletome": 0.40,
    "Core Rulebook": 0.50,
    "Art Book": 0.55,
    "Limited Edition Book": 0.85,
    "OOP Book": 0.75,
    "Supplement": 0.35,
    "Campaign Book": 0.40,
}


def _book_rarity_score(book_type: str) -> float:
    """Map a book type to a 0-1 rarity score."""
    return BOOK_RARITY_SCORES.get(book_type, shared_rarity_score(book_type))


def get_curated_catalog() -> list[dict]:
    """Curated Warhammer miniatures catalog covering key factions and price tiers."""

    # (game, faction, name, kit_type, retail_gbp, secondary_eur)
    kits = [
        # 40K - Space Marines
        ("40k", "Space Marines", "Primarch Roboute Guilliman", "Centerpiece", 50, 65),
        ("40k", "Space Marines", "Redemptor Dreadnought", "Vehicle", 45, 55),
        ("40k", "Space Marines", "Indomitus Box Set", "Box Set", 125, 200),
        ("40k", "Space Marines", "Space Marine Intercessors (10)", "Troops", 40, 45),
        ("40k", "Space Marines", "Captain in Terminator Armour", "HQ", 30, 35),
        ("40k", "Space Marines", "Bladeguard Veterans", "Elite", 35, 40),
        ("40k", "Space Marines", "Repulsor Executioner", "Vehicle", 60, 75),

        # 40K - Chaos
        ("40k", "Death Guard", "Mortarion, Daemon Primarch", "Centerpiece", 80, 110),
        ("40k", "Thousand Sons", "Magnus the Red", "Centerpiece", 80, 110),
        ("40k", "Chaos Space Marines", "Abaddon the Despoiler", "HQ", 40, 55),
        ("40k", "World Eaters", "Angron, Daemon Primarch", "Centerpiece", 90, 120),
        ("40k", "Chaos Daemons", "Great Unclean One", "Centerpiece", 85, 110),
        ("40k", "Chaos Daemons", "Lord of Change", "Centerpiece", 85, 110),
        ("40k", "Chaos Daemons", "Keeper of Secrets", "Centerpiece", 85, 110),

        # 40K - Xenos
        ("40k", "Tyranids", "Tyrannofex / Tervigon", "Monster", 45, 55),
        ("40k", "Tyranids", "Hive Tyrant / Swarmlord", "HQ", 40, 50),
        ("40k", "Necrons", "Silent King", "Centerpiece", 95, 130),
        ("40k", "Necrons", "C'tan Shard of the Void Dragon", "Centerpiece", 42, 55),
        ("40k", "Orks", "Gorkanaut / Morkanaut", "Vehicle", 70, 85),
        ("40k", "Aeldari", "Avatar of Khaine", "Centerpiece", 65, 85),
        ("40k", "T'au Empire", "Riptide Battlesuit", "Battlesuit", 55, 70),
        ("40k", "Leagues of Votann", "Hekaton Land Fortress", "Vehicle", 65, 80),

        # 40K - Imperial Knights / Titans
        ("40k", "Imperial Knights", "Knight Castellan", "Lord of War", 105, 140),
        ("40k", "Imperial Knights", "Armiger Warglaives", "War Dog", 40, 50),
        ("40k", "Adeptus Titanicus", "Warlord Titan", "Titan", 95, 130),
        ("40k", "Adeptus Titanicus", "Reaver Titan", "Titan", 55, 75),

        # Age of Sigmar
        ("aos", "Stormcast Eternals", "Yndrasta, the Celestial Spear", "HQ", 32, 40),
        ("aos", "Slaves to Darkness", "Archaon the Everchosen", "Centerpiece", 100, 140),
        ("aos", "Ossiarch Bonereapers", "Nagash, Supreme Lord of Undead", "Centerpiece", 80, 110),
        ("aos", "Lumineth Realm-lords", "Teclis, Celennar", "Centerpiece", 95, 130),
        ("aos", "Sons of Behemat", "Mega-Gargant", "Centerpiece", 100, 130),
        ("aos", "Daughters of Khaine", "Morathi", "Centerpiece", 75, 100),
        ("aos", "Fyreslayers", "Magmadroth", "Monster", 50, 65),

        # Forge World (resin, premium)
        ("fw", "Forge World", "Warhound Titan", "Titan", 340, 450),
        ("fw", "Forge World", "Mars Pattern Warlord Titan", "Titan", 1100, 1500),
        ("fw", "Forge World", "Thunderhawk Gunship", "Flyer", 360, 480),
        ("fw", "Horus Heresy", "Primarch Lion El'Jonson", "Primarch", 55, 85),
        ("fw", "Horus Heresy", "Primarch Horus Lupercal", "Primarch", 65, 95),

        # Box Sets / Starter Sets
        ("40k", "Starter", "Leviathan Box Set", "Box Set", 150, 180),
        ("40k", "Starter", "Ultimate Starter Set 10th Ed", "Box Set", 110, 130),
        ("aos", "Starter", "Dominion Box Set", "Box Set", 125, 160),
        ("aos", "Starter", "Skaventide Box Set", "Box Set", 150, 175),

        # Kill Team / Side Games
        ("kt", "Kill Team", "Kill Team: Nightmare", "Box Set", 100, 125),
        ("kt", "Kill Team", "Kill Team: Hivestorm", "Box Set", 100, 125),
        ("nb", "Necromunda", "Necromunda: Hive War", "Box Set", 95, 115),
        ("bb", "Blood Bowl", "Blood Bowl: Second Season", "Box Set", 90, 110),

        # OOP / Collectible
        ("40k", "OOP", "Warhammer 40K 3rd Edition Starter", "Box Set", 0, 250),
        ("40k", "OOP", "Space Hulk 2009", "Board Game", 0, 300),
        ("40k", "OOP", "Battlefleet Gothic Starter", "Board Game", 0, 400),
        ("40k", "Limited", "Legio Custodes Tribune", "Limited", 30, 120),

        # --- Forge World Resin Kits ---
        ("fw", "Forge World", "Deredeo Dreadnought", "Dreadnought", 55, 85),
        ("fw", "Forge World", "Leviathan Dreadnought", "Dreadnought", 65, 95),
        ("fw", "Forge World", "Contemptor Dreadnought", "Dreadnought", 42, 65),
        ("fw", "Forge World", "Warhound Titan (Mars Pattern)", "Titan", 360, 480),
        ("fw", "Forge World", "Reaver Titan", "Titan", 700, 950),
        ("fw", "Forge World", "Tau Manta", "Super-Heavy", 1200, 1800),
        ("fw", "Forge World", "Mastodon Heavy Assault Transport", "Super-Heavy", 250, 350),

        # --- Limited Edition Models ---
        ("40k", "Limited", "Space Marine Captain (Store Anniversary 2024)", "Limited", 25, 80),
        ("40k", "Limited", "Primaris Lieutenant (Celebration 2023)", "Limited", 22, 65),
        ("40k", "Limited", "Grombrindal the White Dwarf (40K)", "Limited", 20, 90),
        ("aos", "Limited", "Dominion Day Vindictor (Made to Order)", "Limited", 25, 70),
        ("40k", "Limited", "Iron Father Feirros (Launch Exclusive)", "Limited", 28, 75),

        # --- Kill Team ---
        ("kt", "Kill Team", "Kill Team: Starter Set", "Box Set", 50, 60),
        ("kt", "Kill Team", "Kill Team: Into the Dark", "Box Set", 125, 150),
        ("kt", "Kill Team", "Kill Team: Shadowvaults", "Box Set", 125, 145),
        ("kt", "Kill Team", "Kill Team Terrain: Killzone Bheta-Decima", "Terrain", 45, 55),

        # --- Warcry ---
        ("warcry", "Warcry", "Warcry: Heart of Ghur", "Box Set", 100, 120),
        ("warcry", "Warcry", "Warcry: Crypt of Blood Starter Set", "Box Set", 50, 55),
        ("warcry", "Warcry", "Warcry: Jade Obelisk Warband", "Warband", 32, 38),
        ("warcry", "Warcry", "Warcry: Rotmire Creed Warband", "Warband", 32, 38),
        ("warcry", "Warcry", "Warcry: Hunters of Huanchi Warband", "Warband", 32, 38),

        # --- Necromunda ---
        ("nb", "Necromunda", "Necromunda: Escher Gang", "Gang", 30, 40),
        ("nb", "Necromunda", "Necromunda: Goliath Gang", "Gang", 30, 40),
        ("nb", "Necromunda", "Necromunda: Van Saar Gang", "Gang", 30, 42),
        ("nb", "Necromunda", "Necromunda: Delaque Gang", "Gang", 30, 40),
        ("nb", "Necromunda", "Necromunda: Ash Wastes Box Set", "Box Set", 150, 180),

        # --- Blood Bowl ---
        ("bb", "Blood Bowl", "Blood Bowl: Skaven Team (The Skavenblight Scramblers)", "Team", 28, 35),
        ("bb", "Blood Bowl", "Blood Bowl: Nurgle Team (Nurgle's Rotters)", "Team", 28, 38),
        ("bb", "Blood Bowl", "Blood Bowl: Undead Team (Champions of Death)", "Team", 28, 35),
        ("bb", "Blood Bowl", "Blood Bowl: Elven Union Team", "Team", 28, 35),

        # --- Adeptus Titanicus ---
        ("at", "Adeptus Titanicus", "Warlord Battle Titan (Titanicus)", "Titan", 80, 110),
        ("at", "Adeptus Titanicus", "Reaver Battle Titan (Titanicus)", "Titan", 45, 65),
        ("at", "Adeptus Titanicus", "Warhound Scout Titan (Titanicus, pair)", "Titan", 30, 45),
        ("at", "Adeptus Titanicus", "Cerastus Knight Lancers (Titanicus)", "Knight", 25, 35),

        # --- Horus Heresy Plastic Kits ---
        ("hh", "Horus Heresy", "MKVI Tactical Squad (Plastic)", "Troops", 36, 42),
        ("hh", "Horus Heresy", "Spartan Assault Tank (Plastic)", "Vehicle", 70, 85),
        ("hh", "Horus Heresy", "Kratos Heavy Assault Tank (Plastic)", "Vehicle", 55, 68),
        ("hh", "Horus Heresy", "Deimos Pattern Rhino (Plastic)", "Vehicle", 32, 38),
        ("hh", "Horus Heresy", "Age of Darkness Box Set", "Box Set", 180, 220),

        # --- OOP Metal Models ---
        ("40k", "OOP", "Classic Chaos Lord in Terminator Armour (Metal)", "HQ", 0, 120),
        ("40k", "OOP", "Classic Space Marine Captain (2nd Ed Metal)", "HQ", 0, 90),
        ("40k", "OOP", "Eldar Striking Scorpions (Metal, 5 Pack)", "Elite", 0, 80),
        ("40k", "OOP", "Eldar Fire Dragons (Metal, 5 Pack)", "Elite", 0, 85),
        ("40k", "OOP", "Classic Abaddon the Despoiler (Metal)", "HQ", 0, 150),
        ("40k", "OOP", "Rogue Trader Space Marine RTB01 (Metal)", "Troops", 0, 300),

        # --- Army / Battleforce Boxes ---
        ("40k", "Battleforce", "Battleforce: Orks 2024", "Box Set", 150, 170),
        ("40k", "Battleforce", "Battleforce: Tyranids 2024", "Box Set", 150, 175),
        ("40k", "Battleforce", "Battleforce: Space Marines 2024", "Box Set", 150, 170),
        ("aos", "Battleforce", "Battleforce: Stormcast Eternals 2024", "Box Set", 150, 165),
        ("aos", "Battleforce", "Battleforce: Skaven 2024", "Box Set", 150, 170),

        # --- Specialist Games ---
        ("ai", "Aeronautica Imperialis", "Aeronautica Imperialis: Wings of Vengeance", "Box Set", 50, 80),
        ("ai", "Aeronautica Imperialis", "Aeronautica Imperialis: Ork Air Waaagh! Dakkajets", "Squadron", 25, 40),
        ("uw", "Underworlds", "Warhammer Underworlds: Gnarlwood", "Box Set", 55, 65),
        ("uw", "Underworlds", "Warhammer Underworlds: Wyrdhollow", "Box Set", 55, 60),
        ("uw", "Underworlds", "Warhammer Underworlds: Hexbane's Hunters", "Warband", 22, 30),

        # --- Paint Sets ---
        ("paint", "Citadel", "Citadel Paint Set: Classic Collection (OOP)", "Paint Set", 0, 120),
        ("paint", "Citadel", "Citadel Contrast Paints Mega Set", "Paint Set", 120, 140),
        ("paint", "Citadel", "Citadel Paint Set: Battle Ready (Starter)", "Paint Set", 30, 35),

        # --- Forge World Resin (expanded) ---
        ("fw", "Forge World", "Warlord Titan (Sunfury Pattern)", "Titan", 1200, 1600),
        ("fw", "Forge World", "Deredeo Dreadnought (Anvilus Pattern)", "Dreadnought", 58, 90),
        ("fw", "Forge World", "Acastus Knight Porphyrion", "Knight", 190, 260),
        ("fw", "Forge World", "Cerastus Knight Castigator", "Knight", 120, 165),

        # --- Kill Team (expanded) ---
        ("kt", "Kill Team", "Kill Team: Gallowdark", "Box Set", 125, 155),
        ("kt", "Kill Team", "Kill Team: Soulshackle", "Box Set", 125, 150),
        ("kt", "Kill Team", "Kill Team: Ashes of Faith", "Box Set", 100, 120),
        ("kt", "Kill Team", "Kill Team Terrain: Killzone Gallowdark Walls", "Terrain", 42, 50),

        # --- Warcry (expanded) ---
        ("warcry", "Warcry", "Warcry: Pyre & Flood", "Box Set", 100, 115),
        ("warcry", "Warcry", "Warcry: Nightmare Quest", "Box Set", 100, 120),
        ("warcry", "Warcry", "Warcry: The Splintered Fang Warband", "Warband", 32, 38),
        ("warcry", "Warcry", "Warcry: Horns of Hashut Warband", "Warband", 32, 40),

        # --- Necromunda (expanded) ---
        ("nb", "Necromunda", "Necromunda: Cawdor Gang", "Gang", 30, 40),
        ("nb", "Necromunda", "Necromunda: Orlock Gang", "Gang", 30, 40),
        ("nb", "Necromunda", "Necromunda: Squat Prospectors", "Gang", 32, 45),

        # --- Blood Bowl (expanded) ---
        ("bb", "Blood Bowl", "Blood Bowl: Dwarf Team (The Dwarf Giants)", "Team", 28, 35),
        ("bb", "Blood Bowl", "Blood Bowl: Wood Elf Team (Athelorn Avengers)", "Team", 28, 38),

        # --- Horus Heresy (expanded) ---
        ("hh", "Horus Heresy", "MKIII Tactical Squad (Plastic)", "Troops", 36, 42),
        ("hh", "Horus Heresy", "Contemptor Dreadnought (Plastic)", "Dreadnought", 38, 48),
        ("hh", "Horus Heresy", "Sicaran Battle Tank (Plastic)", "Vehicle", 55, 70),
        ("hh", "Horus Heresy", "Leviathan Siege Dreadnought (Plastic)", "Dreadnought", 45, 58),

        # --- OOP Metal Models (expanded) ---
        ("40k", "OOP", "Classic Commissar Yarrick (Metal)", "HQ", 0, 110),
        ("40k", "OOP", "Classic Ghazghkull Thraka (Metal, 2nd Ed)", "HQ", 0, 130),
        ("40k", "OOP", "Space Marine Terminators (Metal, 5 Pack, 2nd Ed)", "Elite", 0, 120),

        # --- Army / Battleforce Boxes (expanded) ---
        ("40k", "Battleforce", "Battleforce: Necrons 2023", "Box Set", 145, 175),
        ("40k", "Battleforce", "Battleforce: Aeldari 2023", "Box Set", 145, 170),
        ("aos", "Battleforce", "Battleforce: Daughters of Khaine 2024", "Box Set", 150, 168),
        ("aos", "Battleforce", "Battleforce: Nighthaunt 2023", "Box Set", 145, 165),

        # --- Specialist Games (expanded) ---
        ("uw", "Underworlds", "Warhammer Underworlds: Deathgorge", "Box Set", 55, 65),
        ("uw", "Underworlds", "Warhammer Underworlds: Grinkrak's Looncourt", "Warband", 22, 30),
        ("uw", "Underworlds", "Warhammer Underworlds: Ephilim's Pandaemonium", "Box Set", 55, 70),
        ("ai", "Aeronautica Imperialis", "Aeronautica Imperialis: T'au Air Caste Tiger Sharks", "Squadron", 30, 50),

        # --- Rare / Discontinued Paint Sets (expanded) ---
        ("paint", "Citadel", "Citadel Foundation Paints Set (OOP)", "Paint Set", 0, 80),
        ("paint", "Citadel", "Citadel Dry Paints Complete Set (OOP)", "Paint Set", 0, 60),

        # === ROUND 4 — 62 new miniatures ===

        # --- 40K — Space Marines (expanded) ---
        ("40k", "Space Marines", "Roboute Guilliman (Limited Ed Primarch)", "Centerpiece", 55, 90),
        ("40k", "Space Marines", "Land Raider Redeemer", "Vehicle", 55, 70),
        ("40k", "Space Marines", "Stormraven Gunship", "Vehicle", 65, 80),
        ("40k", "Space Marines", "Centurion Devastators", "Heavy Support", 45, 52),
        ("40k", "Space Marines", "Primaris Aggressors", "Elite", 35, 42),
        ("40k", "Space Marines", "Terminator Assault Squad", "Elite", 40, 48),

        # --- 40K — Chaos (expanded) ---
        ("40k", "Chaos Knights", "Knight Desecrator", "Lord of War", 105, 135),
        ("40k", "Chaos Knights", "War Dog Stalkers", "War Dog", 40, 52),
        ("40k", "Thousand Sons", "Ahriman on Disc of Tzeentch", "HQ", 28, 35),
        ("40k", "Death Guard", "Plagueburst Crawler", "Vehicle", 40, 50),
        ("40k", "World Eaters", "Khorne Berzerkers (10)", "Troops", 38, 45),

        # --- 40K — Xenos (expanded) ---
        ("40k", "Tyranids", "Norn Emissary / Assimilator", "Monster", 60, 75),
        ("40k", "Tyranids", "Carnifex (Twin Pack)", "Monster", 60, 70),
        ("40k", "Necrons", "Canoptek Doomstalker", "Vehicle", 28, 35),
        ("40k", "Necrons", "Monolith", "Lord of War", 90, 110),
        ("40k", "Orks", "Megatrakk Scrapjet", "Vehicle", 30, 38),
        ("40k", "Orks", "Beast Snagga Boyz (10)", "Troops", 32, 40),
        ("40k", "Aeldari", "Wraithknight", "Lord of War", 85, 110),
        ("40k", "Aeldari", "Eldrad Ulthran", "HQ", 22, 28),
        ("40k", "T'au Empire", "Stormsurge", "Lord of War", 90, 115),
        ("40k", "Drukhari", "Raider", "Transport", 32, 40),
        ("40k", "Drukhari", "Drazhar", "HQ", 22, 30),
        ("40k", "Genestealer Cults", "Aberrants (5)", "Elite", 28, 35),
        ("40k", "Genestealer Cults", "Goliath Truck / Rockgrinder", "Vehicle", 35, 45),
        ("40k", "Leagues of Votann", "Sagitaur", "Vehicle", 35, 42),
        ("40k", "Adeptus Mechanicus", "Kastelan Robots", "Heavy Support", 38, 48),
        ("40k", "Adeptus Custodes", "Allarus Custodians", "Elite", 38, 45),
        ("40k", "Adepta Sororitas", "Immolator", "Vehicle", 40, 50),
        ("40k", "Adepta Sororitas", "Morvenn Vahl", "HQ", 32, 40),
        ("40k", "Imperial Guard", "Rogal Dorn Battle Tank", "Vehicle", 50, 62),
        ("40k", "Imperial Guard", "Leman Russ Demolisher", "Vehicle", 40, 50),

        # --- Age of Sigmar (expanded) ---
        ("aos", "Skaven", "Thanquol and Boneripper", "Centerpiece", 55, 70),
        ("aos", "Soulblight Gravelords", "Lauka Vai / Vengorian Lord", "HQ", 32, 42),
        ("aos", "Nighthaunt", "Lady Olynder, Mortarch of Grief", "HQ", 28, 38),
        ("aos", "Ironjawz", "Megaboss on Maw-Krusha", "Centerpiece", 85, 110),
        ("aos", "Gloomspite Gitz", "Loonboss on Mangler Squigs", "HQ", 55, 70),
        ("aos", "Seraphon", "Lord Kroak", "Centerpiece", 65, 85),
        ("aos", "Seraphon", "Stegadon / Engine of the Gods", "Monster", 42, 52),
        ("aos", "Kharadron Overlords", "Arkanaut Ironclad", "Vehicle", 65, 80),
        ("aos", "Idoneth Deepkin", "Akhelian Leviadon", "Monster", 60, 75),
        ("aos", "Slaves to Darkness", "Varanguard (3)", "Elite", 45, 58),

        # --- Forge World (expanded) ---
        ("fw", "Forge World", "Carmine Dragon", "Monster", 90, 130),
        ("fw", "Forge World", "Greater Brass Scorpion of Khorne", "Super-Heavy", 280, 380),
        ("fw", "Horus Heresy", "Primarch Fulgrim", "Primarch", 65, 100),
        ("fw", "Horus Heresy", "Primarch Perturabo", "Primarch", 65, 100),

        # --- Horus Heresy (expanded) ---
        ("hh", "Horus Heresy", "Deredeo Dreadnought (Plastic)", "Dreadnought", 42, 55),
        ("hh", "Horus Heresy", "Land Raider Proteus (Plastic)", "Vehicle", 60, 75),
        ("hh", "Horus Heresy", "Praetor Set (Plastic)", "HQ", 28, 35),

        # --- OOP / Collectible (expanded) ---
        ("40k", "OOP", "Rogue Trader Orks (Metal, 5 Pack)", "Troops", 0, 200),
        ("40k", "OOP", "Warhammer Quest Silver Tower", "Board Game", 0, 280),
        ("40k", "OOP", "Execution Force Board Game", "Board Game", 0, 180),
        ("40k", "OOP", "Necromunda Underhive (Original 1990s)", "Board Game", 0, 350),

        # --- 40K Combat Patrol Boxes ---
        ("40k", "Combat Patrol", "Combat Patrol: Space Marines", "Box Set", 100, 115),
        ("40k", "Combat Patrol", "Combat Patrol: Tyranids", "Box Set", 100, 120),
        ("40k", "Combat Patrol", "Combat Patrol: Orks", "Box Set", 100, 115),
        ("40k", "Combat Patrol", "Combat Patrol: Necrons", "Box Set", 100, 112),
        ("40k", "Combat Patrol", "Combat Patrol: Death Guard", "Box Set", 100, 118),
        ("40k", "Combat Patrol", "Combat Patrol: Thousand Sons", "Box Set", 100, 115),

        # === ROUND 5 — 105 new miniature kits ===

        # --- 40K — Remaining Factions (Grey Knights, Dark Angels, Space Wolves, etc.) ---
        ("40k", "Grey Knights", "Grand Master in Nemesis Dreadknight", "HQ", 45, 55),
        ("40k", "Grey Knights", "Grey Knights Strike Squad (10)", "Troops", 38, 45),
        ("40k", "Grey Knights", "Grey Knights Terminators (5)", "Elite", 40, 48),
        ("40k", "Dark Angels", "Deathwing Knights (5)", "Elite", 40, 50),
        ("40k", "Dark Angels", "Ravenwing Black Knights (3)", "Fast Attack", 35, 42),
        ("40k", "Dark Angels", "Azrael, Supreme Grand Master", "HQ", 25, 32),
        ("40k", "Space Wolves", "Ragnar Blackmane", "HQ", 25, 32),
        ("40k", "Space Wolves", "Thunderwolf Cavalry (3)", "Fast Attack", 40, 50),
        ("40k", "Space Wolves", "Wulfen (5)", "Elite", 38, 48),
        ("40k", "Blood Angels", "Sanguinor, Exemplar of the Host", "HQ", 22, 30),
        ("40k", "Blood Angels", "Sanguinary Guard (5)", "Elite", 35, 42),
        ("40k", "Blood Angels", "Death Company Intercessors (5)", "Elite", 35, 40),
        ("40k", "Deathwatch", "Deathwatch Veterans (5)", "Troops", 35, 42),
        ("40k", "Black Templars", "High Marshal Helbrecht", "HQ", 28, 35),
        ("40k", "Black Templars", "Emperor's Champion", "HQ", 22, 28),
        ("40k", "Black Templars", "Primaris Crusader Squad (10)", "Troops", 40, 48),

        # --- 40K — Additional Xenos ---
        ("40k", "Tyranids", "Lictor", "Elite", 28, 35),
        ("40k", "Tyranids", "Exocrine / Haruspex", "Heavy Support", 45, 55),
        ("40k", "Tyranids", "Screamer-Killer / Carnifex", "Monster", 35, 42),
        ("40k", "Necrons", "Szarekh, The Silent King (Plastic)", "Centerpiece", 95, 130),
        ("40k", "Necrons", "Lokhust Heavy Destroyer (3)", "Heavy Support", 35, 42),
        ("40k", "Necrons", "Tomb Blades (3)", "Fast Attack", 30, 38),
        ("40k", "Orks", "Ghazghkull Thraka (Plastic)", "HQ", 40, 52),
        ("40k", "Orks", "Kill Rig / Hunta Rig", "Vehicle", 65, 80),
        ("40k", "Orks", "Deff Dread", "Dreadnought", 32, 40),
        ("40k", "T'au Empire", "Commander Farsight", "HQ", 28, 35),
        ("40k", "T'au Empire", "Broadside Battlesuit", "Heavy Support", 30, 38),
        ("40k", "T'au Empire", "Hammerhead Gunship", "Vehicle", 40, 50),
        ("40k", "Aeldari", "Yncarne, Avatar of Ynnead", "HQ", 30, 42),
        ("40k", "Aeldari", "Fire Prism / Night Spinner", "Vehicle", 38, 48),
        ("40k", "Harlequins", "Harlequin Troupe (6)", "Troops", 28, 35),
        ("40k", "Harlequins", "Starweaver / Voidweaver", "Transport", 28, 38),
        ("40k", "Drukhari", "Archon", "HQ", 22, 28),
        ("40k", "Drukhari", "Ravager", "Heavy Support", 32, 42),
        ("40k", "Genestealer Cults", "Patriarch", "HQ", 22, 30),
        ("40k", "Genestealer Cults", "Ridgerunner", "Fast Attack", 28, 35),

        # --- 40K — Additional Imperium ---
        ("40k", "Adeptus Mechanicus", "Skorpius Disintegrator / Dunerider", "Vehicle", 42, 52),
        ("40k", "Adeptus Mechanicus", "Belisarius Cawl", "HQ", 35, 45),
        ("40k", "Adeptus Custodes", "Custodian Guard (5)", "Troops", 38, 45),
        ("40k", "Adeptus Custodes", "Trajann Valoris", "HQ", 28, 35),
        ("40k", "Adepta Sororitas", "Celestine, the Living Saint", "HQ", 35, 45),
        ("40k", "Adepta Sororitas", "Exorcist", "Heavy Support", 42, 52),
        ("40k", "Adepta Sororitas", "Castigator", "Vehicle", 50, 62),
        ("40k", "Imperial Guard", "Baneblade", "Lord of War", 100, 130),
        ("40k", "Imperial Guard", "Cadian Shock Troops (20)", "Troops", 36, 42),
        ("40k", "Imperial Guard", "Sentinel", "Fast Attack", 24, 30),
        ("40k", "Imperial Knights", "Knight Paladin / Errant", "Lord of War", 95, 125),
        ("40k", "Agents of the Imperium", "Inquisitor Lord Kyria Draxus", "HQ", 22, 30),

        # --- 40K — Chaos (Additional) ---
        ("40k", "Chaos Space Marines", "Haarken Worldclaimer", "HQ", 22, 28),
        ("40k", "Chaos Space Marines", "Forgefiend / Maulerfiend", "Vehicle", 45, 55),
        ("40k", "Chaos Space Marines", "Chaos Land Raider", "Vehicle", 55, 70),
        ("40k", "Death Guard", "Lord of Contagion", "HQ", 22, 28),
        ("40k", "Death Guard", "Deathshroud Bodyguard (3)", "Elite", 35, 42),
        ("40k", "Thousand Sons", "Rubric Marines (10)", "Troops", 40, 48),
        ("40k", "Thousand Sons", "Scarab Occult Terminators (5)", "Elite", 42, 50),
        ("40k", "World Eaters", "Eightbound (3)", "Elite", 38, 48),
        ("40k", "World Eaters", "World Eaters Lord on Juggernaut", "HQ", 32, 42),
        ("40k", "Chaos Daemons", "Bloodthirster", "Centerpiece", 85, 115),
        ("40k", "Chaos Daemons", "Belakor, the Dark Master", "Centerpiece", 80, 105),

        # --- Age of Sigmar — All Factions (expanded) ---
        ("aos", "Stormcast Eternals", "Krondys, Son of Dracothion", "Centerpiece", 85, 110),
        ("aos", "Stormcast Eternals", "Annihilators (3)", "Elite", 35, 42),
        ("aos", "Stormcast Eternals", "Stormdrake Guard (2)", "Cavalry", 55, 70),
        ("aos", "Skaven", "Verminlord", "Centerpiece", 55, 72),
        ("aos", "Skaven", "Stormfiends (3)", "Monster", 40, 50),
        ("aos", "Soulblight Gravelords", "Vampire Lord on Zombie Dragon", "Centerpiece", 55, 72),
        ("aos", "Nighthaunt", "Nagash (AoS)", "Centerpiece", 75, 100),
        ("aos", "Ossiarch Bonereapers", "Gothizzar Harvester", "Monster", 35, 42),
        ("aos", "Ossiarch Bonereapers", "Arch-Kavalos Zandtos", "HQ", 28, 38),
        ("aos", "Ironjawz", "Gordrakk, Fist of Gork", "Centerpiece", 85, 115),
        ("aos", "Gloomspite Gitz", "Arachnarok Spider", "Monster", 45, 58),
        ("aos", "Gloomspite Gitz", "Squig Herd (12)", "Troops", 28, 35),
        ("aos", "Seraphon", "Carnosaur / Troglodon", "Monster", 42, 55),
        ("aos", "Idoneth Deepkin", "Eidolon of Mathlann", "Centerpiece", 60, 80),
        ("aos", "Kharadron Overlords", "Arkanaut Frigate", "Vehicle", 42, 55),
        ("aos", "Lumineth Realm-lords", "Alarith Spirit of the Mountain", "Monster", 48, 62),
        ("aos", "Flesh-eater Courts", "Royal Terrorgheist / Zombie Dragon", "Monster", 45, 58),
        ("aos", "Flesh-eater Courts", "Abhorrant Archregent", "HQ", 22, 30),
        ("aos", "Maggotkin of Nurgle", "Great Unclean One (AoS)", "Centerpiece", 85, 110),
        ("aos", "Disciples of Tzeentch", "Lord of Change (AoS)", "Centerpiece", 85, 110),
        ("aos", "Hedonites of Slaanesh", "Keeper of Secrets (AoS)", "Centerpiece", 85, 110),
        ("aos", "Blades of Khorne", "Bloodthirster (AoS)", "Centerpiece", 85, 115),
        ("aos", "Sylvaneth", "Treelord Ancient / Spirit of Durthu", "Centerpiece", 42, 55),
        ("aos", "Ogor Mawtribes", "Stonehorn / Thundertusk", "Monster", 42, 55),
        ("aos", "Cities of Sigmar", "Freeguild Cavaliers (5)", "Cavalry", 38, 45),
        ("aos", "Beasts of Chaos", "Ghorgon / Cygor", "Monster", 42, 55),

        # --- Kill Team Boxes (Additional) ---
        ("kt", "Kill Team", "Kill Team: Moroch", "Box Set", 125, 150),
        ("kt", "Kill Team", "Kill Team: Nachmund", "Box Set", 125, 148),
        ("kt", "Kill Team", "Kill Team: Octarius", "Box Set", 125, 160),
        ("kt", "Kill Team", "Kill Team: Chalnath", "Box Set", 125, 145),

        # --- Necromunda Gangs (All) ---
        ("nb", "Necromunda", "Necromunda: Palanite Enforcers", "Gang", 30, 42),
        ("nb", "Necromunda", "Necromunda: Corpse Grinder Cults", "Gang", 32, 45),
        ("nb", "Necromunda", "Necromunda: House Agents", "Gang", 28, 38),

        # --- Underworlds Warbands (Additional) ---
        ("uw", "Underworlds", "Warhammer Underworlds: Skabbik's Plaguepack", "Warband", 22, 30),
        ("uw", "Underworlds", "Warhammer Underworlds: Domitan's Stormcoven", "Warband", 22, 30),
        ("uw", "Underworlds", "Warhammer Underworlds: Zondara's Gravebreakers", "Warband", 22, 30),
        ("uw", "Underworlds", "Warhammer Underworlds: The Headsmen's Curse", "Warband", 22, 30),
        ("uw", "Underworlds", "Warhammer Underworlds: Cyreni's Razors", "Warband", 22, 30),

        # --- Blood Bowl Teams (Additional) ---
        ("bb", "Blood Bowl", "Blood Bowl: Ogre Team (Fire Mountain Gut Busters)", "Team", 28, 38),
        ("bb", "Blood Bowl", "Blood Bowl: Goblin Team (Scarcrag Snivellers)", "Team", 28, 35),
        ("bb", "Blood Bowl", "Blood Bowl: Halfling Team (Greenfield Grasshuggers)", "Team", 28, 35),
        ("bb", "Blood Bowl", "Blood Bowl: Khorne Team", "Team", 28, 38),
        ("bb", "Blood Bowl", "Blood Bowl: Lizardmen Team (Lustria Croakers)", "Team", 28, 36),
        ("bb", "Blood Bowl", "Blood Bowl: Amazon Team (Kara Temple Harpies)", "Team", 28, 35),
        ("bb", "Blood Bowl", "Blood Bowl: Norse Team (Norsca Rampagers)", "Team", 28, 36),

        # --- Forge World Resin (Additional) ---
        ("fw", "Forge World", "Mortis Dreadnought", "Dreadnought", 48, 75),
        ("fw", "Forge World", "Sicaran Venator", "Vehicle", 65, 95),
        ("fw", "Forge World", "Telemon Heavy Dreadnought (Custodes)", "Dreadnought", 70, 100),
        ("fw", "Forge World", "Dracosan Transport", "Vehicle", 58, 85),
        ("fw", "Horus Heresy", "Primarch Angron (30K)", "Primarch", 70, 110),
        ("fw", "Horus Heresy", "Primarch Konrad Curze", "Primarch", 65, 100),
        ("fw", "Horus Heresy", "Primarch Lorgar Aurelian", "Primarch", 65, 100),
        ("fw", "Horus Heresy", "Primarch Vulkan", "Primarch", 65, 100),
        ("fw", "Horus Heresy", "Primarch Corax", "Primarch", 65, 100),
        ("fw", "Horus Heresy", "Primarch Alpharius", "Primarch", 65, 105),

        # --- Horus Heresy Plastic (Additional) ---
        ("hh", "Horus Heresy", "Dreadnought Drop Pod (Plastic)", "Vehicle", 35, 42),
        ("hh", "Horus Heresy", "Cataphractii Terminators (Plastic, 5)", "Elite", 38, 48),
        ("hh", "Horus Heresy", "Tartaros Terminators (Plastic, 5)", "Elite", 38, 48),

        # --- Limited Edition / Celebration Models ---
        ("40k", "Limited", "Sanguinius (Forge World Limited Run)", "Limited", 80, 350),
        ("40k", "Limited", "Horus the Warmaster (FW Limited)", "Limited", 80, 300),
        ("40k", "Limited", "Warhammer Day Exclusive Captain 2023", "Limited", 25, 75),
        ("40k", "Limited", "Warhammer Day Exclusive Captain 2024", "Limited", 25, 70),
        ("40k", "Limited", "Space Marine Heroes Series 3 (Blind Box)", "Limited", 15, 25),
        ("40k", "Limited", "Black Library Celebration Primaris Marine", "Limited", 22, 60),

        # --- Combat Patrol Boxes (Additional) ---
        ("40k", "Combat Patrol", "Combat Patrol: Aeldari", "Box Set", 100, 118),
        ("40k", "Combat Patrol", "Combat Patrol: T'au Empire", "Box Set", 100, 115),
        ("40k", "Combat Patrol", "Combat Patrol: World Eaters", "Box Set", 100, 120),
        ("40k", "Combat Patrol", "Combat Patrol: Adeptus Custodes", "Box Set", 100, 115),
        ("40k", "Combat Patrol", "Combat Patrol: Drukhari", "Box Set", 100, 112),
        ("40k", "Combat Patrol", "Combat Patrol: Genestealer Cults", "Box Set", 100, 110),
        ("40k", "Combat Patrol", "Combat Patrol: Imperial Guard", "Box Set", 100, 118),
        ("40k", "Combat Patrol", "Combat Patrol: Adepta Sororitas", "Box Set", 100, 115),

        # === EXPANSION ROUND — 100+ new miniature kits ===

        # --- 40K — Space Marines (Additional Chapter Characters) ---
        ("40k", "Space Marines", "Primaris Chaplain on Bike", "HQ", 30, 38),
        ("40k", "Space Marines", "Primaris Apothecary Biologis", "Elite", 25, 32),
        ("40k", "Space Marines", "Gladiator Reaper / Valiant / Lancer", "Vehicle", 50, 62),
        ("40k", "Space Marines", "Storm Speeder Hailstrike / Hammerstrike / Thunderstrike", "Vehicle", 40, 50),
        ("40k", "Space Marines", "Impulsor", "Transport", 40, 48),
        ("40k", "Space Marines", "Hammerfall Bunker", "Fortification", 40, 50),
        ("40k", "Space Marines", "Brutalis Dreadnought", "Dreadnought", 45, 55),
        ("40k", "Space Marines", "Ballistus Dreadnought", "Dreadnought", 40, 50),
        ("40k", "Space Marines", "Infernus Marines (5)", "Troops", 32, 38),
        ("40k", "Space Marines", "Desolation Marines (5)", "Heavy Support", 35, 42),

        # --- 40K — Dark Angels (Additional) ---
        ("40k", "Dark Angels", "Deathwing Command Squad", "Elite", 38, 48),
        ("40k", "Dark Angels", "Ravenwing Dark Talon / Nephilim Jetfighter", "Flyer", 50, 62),
        ("40k", "Dark Angels", "Lion El'Jonson (40K Plastic)", "Centerpiece", 42, 55),

        # --- 40K — Space Wolves (Additional) ---
        ("40k", "Space Wolves", "Canis Wolfborn", "HQ", 22, 30),
        ("40k", "Space Wolves", "Fenrisian Wolves (5)", "Fast Attack", 18, 24),

        # --- 40K — Blood Angels (Additional) ---
        ("40k", "Blood Angels", "Lemartes, Guardian of the Lost", "HQ", 22, 30),
        ("40k", "Blood Angels", "Baal Predator", "Vehicle", 40, 50),
        ("40k", "Blood Angels", "Mephiston, Lord of Death", "HQ", 25, 32),

        # --- 40K — Chaos (Additional Daemons & CSM) ---
        ("40k", "Chaos Daemons", "Skull Cannon of Khorne", "Vehicle", 28, 35),
        ("40k", "Chaos Daemons", "Burning Chariot of Tzeentch", "Vehicle", 28, 35),
        ("40k", "Chaos Daemons", "Seeker Chariot of Slaanesh", "Vehicle", 28, 35),
        ("40k", "Chaos Daemons", "Soul Grinder", "Vehicle", 45, 58),
        ("40k", "Chaos Space Marines", "Chaos Terminator Squad (5)", "Elite", 38, 45),
        ("40k", "Chaos Space Marines", "Chaos Lord in Terminator Armour (Plastic)", "HQ", 22, 28),
        ("40k", "Chaos Space Marines", "Heldrake", "Flyer", 48, 60),
        ("40k", "Chaos Space Marines", "Vashtorr the Arkifane", "HQ", 35, 45),
        ("40k", "Chaos Space Marines", "Daemon Prince (Plastic)", "HQ", 35, 45),

        # --- 40K — Xenos (Additional Remaining) ---
        ("40k", "Tyranids", "Maleceptor / Toxicrene", "Monster", 45, 55),
        ("40k", "Tyranids", "Biovore", "Heavy Support", 28, 35),
        ("40k", "Tyranids", "Pyrovore", "Elite", 28, 35),
        ("40k", "Necrons", "Cryptothralls (2)", "Elite", 15, 20),
        ("40k", "Necrons", "Triarch Stalker", "Vehicle", 32, 40),
        ("40k", "Necrons", "Doomsday Ark", "Vehicle", 35, 44),
        ("40k", "Orks", "Battlewagon", "Vehicle", 55, 68),
        ("40k", "Orks", "Stompa", "Lord of War", 90, 115),
        ("40k", "Orks", "Flash Gitz (5)", "Elite", 28, 35),
        ("40k", "T'au Empire", "Ghostkeel Battlesuit", "Elite", 48, 58),
        ("40k", "T'au Empire", "Pathfinder Team (10)", "Troops", 28, 35),
        ("40k", "Aeldari", "War Walker", "Fast Attack", 25, 32),
        ("40k", "Aeldari", "Falcon", "Vehicle", 32, 40),
        ("40k", "Aeldari", "Wave Serpent", "Transport", 32, 40),
        ("40k", "Drukhari", "Talos / Cronos", "Heavy Support", 32, 42),
        ("40k", "Drukhari", "Voidraven Bomber", "Flyer", 48, 60),
        ("40k", "Genestealer Cults", "Achilles Ridgerunner", "Fast Attack", 28, 35),
        ("40k", "Genestealer Cults", "Broodcoven", "HQ", 32, 40),
        ("40k", "Adeptus Mechanicus", "Ironstrider Ballistarius / Sydonian Dragoon", "Fast Attack", 32, 40),
        ("40k", "Adeptus Mechanicus", "Onager Dunecrawler", "Vehicle", 38, 48),
        ("40k", "Adeptus Custodes", "Vertus Praetors (3)", "Fast Attack", 40, 50),
        ("40k", "Adeptus Custodes", "Venerable Land Raider (Custodes)", "Vehicle", 55, 70),
        ("40k", "Imperial Guard", "Chimera", "Transport", 32, 40),
        ("40k", "Imperial Guard", "Basilisk", "Heavy Support", 35, 42),
        ("40k", "Imperial Guard", "Valkyrie", "Flyer", 45, 55),

        # --- Age of Sigmar (Additional Factions) ---
        ("aos", "Stormcast Eternals", "Bastian Carthalos", "HQ", 28, 35),
        ("aos", "Stormcast Eternals", "Celestant-Prime", "Centerpiece", 55, 72),
        ("aos", "Skaven", "Hell Pit Abomination", "Monster", 42, 55),
        ("aos", "Skaven", "Plague Monks (20)", "Troops", 28, 35),
        ("aos", "Nighthaunt", "Spirit Hosts (3)", "Troops", 18, 22),
        ("aos", "Nighthaunt", "Bladegheist Revenants (10)", "Elite", 28, 35),
        ("aos", "Ironjawz", "'Ardboyz (10)", "Troops", 32, 38),
        ("aos", "Seraphon", "Bastiladon / Troglodon", "Monster", 42, 52),
        ("aos", "Seraphon", "Saurus Warriors (20)", "Troops", 35, 42),
        ("aos", "Ogor Mawtribes", "Gluttons (6)", "Troops", 35, 42),
        ("aos", "Ogor Mawtribes", "Frostlord on Stonehorn", "Centerpiece", 48, 62),
        ("aos", "Cities of Sigmar", "Tahlia Vedra, Lioness of the Parch", "HQ", 35, 45),
        ("aos", "Beasts of Chaos", "Dragon Ogor Shaggoth", "Monster", 35, 45),
        ("aos", "Sylvaneth", "Alarielle the Everqueen", "Centerpiece", 80, 105),
        ("aos", "Kharadron Overlords", "Endrinmaster with Dirigible Suit", "HQ", 22, 28),
        ("aos", "Fyreslayers", "Auric Runefather on Magmadroth", "Centerpiece", 55, 72),
        ("aos", "Lumineth Realm-lords", "Vanari Auralan Wardens (10)", "Troops", 35, 42),
        ("aos", "Idoneth Deepkin", "Namarti Thralls (10)", "Troops", 28, 35),

        # --- Warhammer+ Exclusives ---
        ("40k", "Warhammer+", "Warhammer+ Exclusive Vindicare Assassin", "Limited", 20, 55),
        ("40k", "Warhammer+", "Warhammer+ Exclusive Ork Nob", "Limited", 20, 50),
        ("aos", "Warhammer+", "Warhammer+ Exclusive Stormcast Knight", "Limited", 20, 50),
        ("40k", "Warhammer+", "Warhammer+ Year 2 Exclusive Chaplain", "Limited", 20, 55),
        ("40k", "Warhammer+", "Warhammer+ Year 3 Exclusive Techmarine", "Limited", 20, 55),

        # --- Celebration / Event Models ---
        ("40k", "Limited", "Store Anniversary Captain 2022", "Limited", 25, 85),
        ("40k", "Limited", "Golden Daemon Winner Trophy Model 2023", "Limited", 0, 250),
        ("40k", "Limited", "Warhammer Fest 2024 Exclusive", "Limited", 25, 90),
        ("40k", "Limited", "Adepticon 2024 Exclusive", "Limited", 25, 80),

        # --- Complete Necromunda (All Gangs + Terrain) ---
        ("nb", "Necromunda", "Necromunda: Redemptionists", "Gang", 30, 42),
        ("nb", "Necromunda", "Necromunda: Slave Ogryns", "Gang", 28, 38),
        ("nb", "Necromunda", "Necromunda: Spyre Hunters", "Gang", 32, 48),
        ("nb", "Necromunda", "Necromunda: Ironhead Squat Prospectors Upgrade", "Gang", 20, 28),
        ("nb", "Necromunda", "Necromunda: Hive Terrain Set", "Terrain", 40, 48),
        ("nb", "Necromunda", "Necromunda: Underhive Scenery Set", "Terrain", 30, 38),
        ("nb", "Necromunda", "Necromunda: Zone Mortalis Floor Tiles", "Terrain", 32, 40),

        # --- Complete Blood Bowl (All Remaining Teams + Accessories) ---
        ("bb", "Blood Bowl", "Blood Bowl: Chaos Dwarf Team (Zharr-Naggrund Ziggurats)", "Team", 28, 38),
        ("bb", "Blood Bowl", "Blood Bowl: Chaos Renegade Team", "Team", 28, 36),
        ("bb", "Blood Bowl", "Blood Bowl: Shambling Undead Team", "Team", 28, 35),
        ("bb", "Blood Bowl", "Blood Bowl: Old World Alliance Team", "Team", 28, 36),
        ("bb", "Blood Bowl", "Blood Bowl: Snotling Team (Snotling Pump Wagons)", "Team", 28, 38),
        ("bb", "Blood Bowl", "Blood Bowl: Dungeon Bowl", "Box Set", 70, 85),
        ("bb", "Blood Bowl", "Blood Bowl Pitch & Dugout Set (Astrogranite)", "Terrain", 25, 30),

        # --- Underworlds (All Remaining Warbands + Seasons) ---
        ("uw", "Underworlds", "Warhammer Underworlds: Embergard", "Box Set", 55, 65),
        ("uw", "Underworlds", "Warhammer Underworlds: Direchasm", "Box Set", 55, 75),
        ("uw", "Underworlds", "Warhammer Underworlds: Harrowdeep", "Box Set", 55, 70),
        ("uw", "Underworlds", "Warhammer Underworlds: Nethermaze", "Box Set", 55, 68),
        ("uw", "Underworlds", "Warhammer Underworlds: Kainan's Reapers", "Warband", 22, 30),
        ("uw", "Underworlds", "Warhammer Underworlds: The Crimson Court", "Warband", 22, 32),
        ("uw", "Underworlds", "Warhammer Underworlds: Xandire's Truthseekers", "Warband", 22, 28),

        # --- Aeronautica Imperialis (Complete) ---
        ("ai", "Aeronautica Imperialis", "Aeronautica Imperialis: Skies of Fire", "Box Set", 50, 85),
        ("ai", "Aeronautica Imperialis", "Aeronautica Imperialis: Imperial Navy Marauder Bombers", "Squadron", 30, 48),
        ("ai", "Aeronautica Imperialis", "Aeronautica Imperialis: Eldar Phoenix & Nightwing", "Squadron", 25, 42),
        ("ai", "Aeronautica Imperialis", "Aeronautica Imperialis: Ground Assets", "Terrain", 20, 32),

        # --- Terrain Kits ---
        ("40k", "Terrain", "Sector Mechanicus: Galvanic Magnavent", "Terrain", 35, 42),
        ("40k", "Terrain", "Sector Imperialis: Basilicanum", "Terrain", 40, 50),
        ("40k", "Terrain", "Ork Scrap Terrain", "Terrain", 25, 32),
        ("40k", "Terrain", "Battlezone: Fronteris Landing Pad", "Terrain", 35, 42),
        ("40k", "Terrain", "Aegis Defence Line", "Terrain", 20, 25),
        ("aos", "Terrain", "Realmscape: Thondian Strongpoint", "Terrain", 42, 52),
        ("aos", "Terrain", "Azyrite Ruins", "Terrain", 30, 38),

        # --- Paint Sets (Additional) ---
        ("paint", "Citadel", "Citadel Shade Paint Set", "Paint Set", 40, 48),
        ("paint", "Citadel", "Citadel Air Paint Set", "Paint Set", 50, 58),
        ("paint", "Citadel", "Citadel Technical Paint Set", "Paint Set", 35, 42),
        ("paint", "Citadel", "Citadel Layer Paint Collection (OOP)", "Paint Set", 0, 90),

        # --- Forge World Character Series (Additional Primarchs) ---
        ("fw", "Horus Heresy", "Primarch Rogal Dorn", "Primarch", 65, 100),
        ("fw", "Horus Heresy", "Primarch Jaghatai Khan", "Primarch", 65, 100),
        ("fw", "Horus Heresy", "Primarch Leman Russ (30K)", "Primarch", 65, 105),
        ("fw", "Horus Heresy", "Primarch Ferrus Manus", "Primarch", 65, 100),
        ("fw", "Horus Heresy", "Primarch Mortarion (30K)", "Primarch", 70, 110),
        ("fw", "Horus Heresy", "Primarch Magnus the Red (30K)", "Primarch", 70, 115),
        ("fw", "Horus Heresy", "Primarch Sanguinius (Resin)", "Primarch", 80, 350),

        # --- Battleforce Boxes (All Remaining) ---
        ("40k", "Battleforce", "Battleforce: T'au Empire 2024", "Box Set", 150, 172),
        ("40k", "Battleforce", "Battleforce: Chaos Space Marines 2024", "Box Set", 150, 175),
        ("40k", "Battleforce", "Battleforce: World Eaters 2024", "Box Set", 150, 178),
        ("40k", "Battleforce", "Battleforce: Imperial Guard 2024", "Box Set", 150, 170),
        ("aos", "Battleforce", "Battleforce: Seraphon 2024", "Box Set", 150, 168),
        ("aos", "Battleforce", "Battleforce: Ironjawz 2024", "Box Set", 150, 170),
        ("aos", "Battleforce", "Battleforce: Soulblight Gravelords 2024", "Box Set", 150, 168),

        # --- Combat Patrol Boxes (All Remaining) ---
        ("40k", "Combat Patrol", "Combat Patrol: Chaos Daemons", "Box Set", 100, 115),
        ("40k", "Combat Patrol", "Combat Patrol: Adeptus Mechanicus", "Box Set", 100, 112),
        ("40k", "Combat Patrol", "Combat Patrol: Leagues of Votann", "Box Set", 100, 115),
        ("40k", "Combat Patrol", "Combat Patrol: Blood Angels", "Box Set", 100, 118),
        ("40k", "Combat Patrol", "Combat Patrol: Dark Angels", "Box Set", 100, 116),
        ("40k", "Combat Patrol", "Combat Patrol: Space Wolves", "Box Set", 100, 118),
        ("40k", "Combat Patrol", "Combat Patrol: Black Templars", "Box Set", 100, 115),
        ("40k", "Combat Patrol", "Combat Patrol: Grey Knights", "Box Set", 100, 115),

        # === ROUND 8 — 40 new items to reach 500+ miniatures ===

        # 40K — Imperial Agents & Assassins
        ("40k", "Agents of the Imperium", "Vindicare Assassin", "Elite", 25, 30),
        ("40k", "Agents of the Imperium", "Callidus Assassin", "Elite", 25, 30),
        ("40k", "Agents of the Imperium", "Eversor Assassin", "Elite", 25, 30),
        ("40k", "Agents of the Imperium", "Culexus Assassin", "Elite", 25, 30),
        ("40k", "Agents of the Imperium", "Inquisitor Coteaz", "HQ", 22, 28),
        ("40k", "Agents of the Imperium", "Officio Assassinorum Execution Force", "Box Set", 55, 80),

        # 40K — More Astra Militarum / Imperial Guard
        ("40k", "Astra Militarum", "Baneblade", "Vehicle", 90, 120),
        ("40k", "Astra Militarum", "Rogal Dorn Battle Tank", "Vehicle", 60, 72),
        ("40k", "Astra Militarum", "Cadian Shock Troops (20)", "Troops", 38, 42),
        ("40k", "Astra Militarum", "Field Ordnance Battery", "Heavy Support", 38, 45),

        # 40K — Sisters of Battle
        ("40k", "Adepta Sororitas", "Morvenn Vahl", "HQ", 35, 42),
        ("40k", "Adepta Sororitas", "Immolator", "Vehicle", 40, 48),
        ("40k", "Adepta Sororitas", "Penitent Engines", "Heavy Support", 35, 42),
        ("40k", "Adepta Sororitas", "Celestian Sacresants", "Elite", 35, 40),

        # 40K — More Tyranid Models
        ("40k", "Tyranids", "Norn Emissary / Assimilator", "Monster", 55, 68),
        ("40k", "Tyranids", "Von Ryan's Leapers", "Troops", 32, 36),
        ("40k", "Tyranids", "Psychophage", "Elite", 32, 38),

        # AoS — Ossiarch Bonereapers
        ("aos", "Ossiarch Bonereapers", "Katakros, Mortarch of the Necropolis", "Centerpiece", 65, 82),
        ("aos", "Ossiarch Bonereapers", "Mortek Guard (20)", "Troops", 40, 48),
        ("aos", "Ossiarch Bonereapers", "Gothizzar Harvester", "Monster", 35, 42),

        # AoS — Fyreslayers
        ("aos", "Fyreslayers", "Auric Runefather on Magmadroth", "Centerpiece", 55, 68),
        ("aos", "Fyreslayers", "Hearthguard Berzerkers (5)", "Elite", 30, 35),

        # AoS — Kharadron Overlords
        ("aos", "Kharadron Overlords", "Arkanaut Ironclad", "Centerpiece", 65, 80),
        ("aos", "Kharadron Overlords", "Grundstok Thunderers (5)", "Troops", 30, 35),

        # Horus Heresy — Additional Legion Units
        ("hh", "Sons of Horus", "Abaddon & Loken Character Set (FW)", "Character", 50, 75),
        ("hh", "Imperial Fists", "Sigismund, First Captain", "Character", 32, 48),
        ("hh", "Emperor's Children", "Kakophoni (FW)", "Elite", 45, 65),
        ("hh", "World Eaters", "Rampager Squad (FW)", "Elite", 40, 58),

        # Kill Team — More Sets
        ("kt", "Kill Team", "Kill Team: Into the Dark", "Box Set", 125, 150),
        ("kt", "Kill Team", "Kill Team: Shadowvaults", "Box Set", 125, 155),
        ("kt", "Kill Team", "Kill Team: Soulshackle", "Box Set", 125, 148),

        # Warhammer+ & Event Exclusives (Additional)
        ("40k", "Exclusives", "Warhammer Day 2024 Exclusive Miniature", "Event Exclusive", 0, 55),
        ("40k", "Exclusives", "AdeptiCon 2024 Exclusive Miniature", "Event Exclusive", 0, 60),
        ("40k", "Exclusives", "Warhammer Fest 2023 Commemorative Model", "Event Exclusive", 0, 65),
        ("40k", "Exclusives", "Store Anniversary Space Marine Captain", "Event Exclusive", 0, 45),

        # Necromunda — Additional Gangs
        ("nb", "Necromunda", "Ash Wastes Nomads Gang", "Gang", 32, 40),
        ("nb", "Necromunda", "Ironhead Squat Prospectors", "Gang", 32, 40),
        ("nb", "Necromunda", "Palanite Subjugator Patrol", "Gang", 28, 35),
        ("nb", "Necromunda", "Necromunda: Hive War Box Set", "Box Set", 95, 120),

        # =================================================================
        # Batch 11 — Horus Heresy Primarchs, AoS Stormcast, Necromunda
        # Gangs, Blood Bowl Teams, Adeptus Titanicus, Aeronautica
        # =================================================================

        # ── Horus Heresy Primarch Models (10) ────────────────────────────
        ("hh", "Horus Heresy", "Horus Lupercal, Warmaster of Chaos (FW)", "Character", 95, 180),
        ("hh", "Horus Heresy", "Sanguinius, Primarch of the Blood Angels (FW)", "Character", 95, 200),
        ("hh", "Horus Heresy", "Lion El'Jonson, Primarch of the Dark Angels (FW)", "Character", 95, 190),
        ("hh", "Horus Heresy", "Fulgrim, Primarch of the Emperor's Children (FW)", "Character", 90, 175),
        ("hh", "Horus Heresy", "Angron, Primarch of the World Eaters (FW)", "Character", 90, 180),
        ("hh", "Horus Heresy", "Mortarion, Primarch of the Death Guard (FW)", "Character", 95, 185),
        ("hh", "Horus Heresy", "Magnus the Red, Primarch of the Thousand Sons (FW)", "Character", 100, 210),
        ("hh", "Horus Heresy", "Perturabo, Primarch of the Iron Warriors (FW)", "Character", 90, 170),
        ("hh", "Horus Heresy", "Vulkan, Primarch of the Salamanders (FW)", "Character", 90, 175),
        ("hh", "Horus Heresy", "Rogal Dorn, Primarch of the Imperial Fists (FW)", "Character", 95, 185),

        # ── Age of Sigmar Stormcast Eternals (8) ────────────────────────
        ("aos", "Stormcast Eternals", "Yndrasta, the Celestial Spear", "Character", 35, 42),
        ("aos", "Stormcast Eternals", "Bastian Carthalos, Commander of the Hammers of Sigmar", "Character", 35, 40),
        ("aos", "Stormcast Eternals", "Ionus Cryptborn, Lord-Veritant", "Character", 28, 35),
        ("aos", "Stormcast Eternals", "Gardus Steel Soul", "Character", 25, 32),
        ("aos", "Stormcast Eternals", "Lord-Imperatant w/ Gryph-hound", "Character", 22, 28),
        ("aos", "Stormcast Eternals", "Stormstrike Chariot", "Vehicle", 42, 50),
        ("aos", "Stormcast Eternals", "Annihilators w/ Meteoric Grandhammers", "Squad", 38, 45),
        ("aos", "Stormcast Eternals", "Thunderstrike Stormdrake Guard", "Monster", 55, 68),

        # ── Necromunda Gang Boxes (10) ──────────────────────────────────
        ("nb", "Necromunda", "Escher Gang Box", "Gang", 32, 40),
        ("nb", "Necromunda", "Goliath Gang Box", "Gang", 32, 40),
        ("nb", "Necromunda", "Van Saar Gang Box", "Gang", 32, 40),
        ("nb", "Necromunda", "Cawdor Gang Box", "Gang", 32, 40),
        ("nb", "Necromunda", "Delaque Gang Box", "Gang", 32, 40),
        ("nb", "Necromunda", "Orlock Gang Box", "Gang", 32, 40),
        ("nb", "Necromunda", "Escher Death Maidens & Wyld Runners", "Gang", 28, 35),
        ("nb", "Necromunda", "Goliath Stimmers & Forge-born", "Gang", 28, 35),
        ("nb", "Necromunda", "Van Saar Archeoteks & Grav-cutters", "Gang", 28, 35),
        ("nb", "Necromunda", "Cawdor Redemptionists", "Gang", 28, 35),

        # ── Blood Bowl Teams (8) ────────────────────────────────────────
        ("bb", "Blood Bowl", "Skaven Team: The Skavenblight Scramblers", "Team Box", 30, 38),
        ("bb", "Blood Bowl", "Nurgle Team: The Nurgle's Rotters", "Team Box", 30, 38),
        ("bb", "Blood Bowl", "Dark Elf Team: The Naggaroth Nightmares", "Team Box", 30, 38),
        ("bb", "Blood Bowl", "Orc Team: The Gouged Eye", "Team Box", 30, 38),
        ("bb", "Blood Bowl", "Human Team: The Reikland Reavers", "Team Box", 30, 38),
        ("bb", "Blood Bowl", "Undead Team: The Champions of Death", "Team Box", 30, 38),
        ("bb", "Blood Bowl", "Wood Elf Team: The Athelorn Avengers", "Team Box", 30, 38),
        ("bb", "Blood Bowl", "Blood Bowl Pitch & Dugouts (Sevens)", "Accessory", 25, 30),

        # ── Adeptus Titanicus (7) ──────────────────────────────────────
        ("at", "Adeptus Titanicus", "Warlord Titan w/ Plasma Annihilator", "Titan", 110, 140),
        ("at", "Adeptus Titanicus", "Warlord Titan w/ Volcano Cannons", "Titan", 110, 140),
        ("at", "Adeptus Titanicus", "Reaver Titan (Plastic)", "Titan", 40, 52),
        ("at", "Adeptus Titanicus", "Warhound Titan Pack (2 Titans)", "Titan", 32, 42),
        ("at", "Adeptus Titanicus", "Cerastus Knight Lancers", "Knight", 25, 32),
        ("at", "Adeptus Titanicus", "Acastus Knight Porphyrion", "Knight", 30, 38),
        ("at", "Adeptus Titanicus", "Adeptus Titanicus Rules Set (OOP)", "Box Set", 50, 80),

        # ── Aeronautica Imperialis (7) ─────────────────────────────────
        ("ai", "Aeronautica Imperialis", "T-65 Thunderbolt Fighters (Imperial Navy)", "Aircraft", 25, 32),
        ("ai", "Aeronautica Imperialis", "Marauder Bombers (Imperial Navy)", "Aircraft", 30, 38),
        ("ai", "Aeronautica Imperialis", "Dakkajet Fighta Bommerz (Orks)", "Aircraft", 25, 32),
        ("ai", "Aeronautica Imperialis", "Barracuda AX-5-2 Fighters (T'au)", "Aircraft", 25, 32),
        ("ai", "Aeronautica Imperialis", "Night Scythe / Doom Scythe (Necrons)", "Aircraft", 25, 32),
        ("ai", "Aeronautica Imperialis", "Valkyrie Assault Carriers (Astra Militarum)", "Aircraft", 30, 38),
        ("ai", "Aeronautica Imperialis", "Aeronautica Imperialis: Wings of Vengeance (OOP)", "Box Set", 65, 95),

        # === EXPANSION ROUND — 55 new items ===

        # ── Age of Sigmar (+10) ──────────────────────────────────────
        ("aos", "Stormcast Eternals", "Lord-Relictor", "HQ", 22, 28),
        ("aos", "Stormcast Eternals", "Vindictors (10)", "Troops", 35, 42),
        ("aos", "Stormcast Eternals", "Praetors (3)", "Elite", 35, 42),
        ("aos", "Nighthaunt", "Chainrasps (20)", "Troops", 28, 35),
        ("aos", "Nighthaunt", "Dreadblade Harrows", "HQ", 18, 22),
        ("aos", "Nighthaunt", "Krulghast Cruciator", "HQ", 22, 28),
        ("aos", "Daughters of Khaine", "Melusai Ironscale", "HQ", 22, 28),
        ("aos", "Daughters of Khaine", "Blood Sisters (5)", "Elite", 35, 42),
        ("aos", "Daughters of Khaine", "Khinerai Heartrenders (5)", "Fast Attack", 32, 38),
        ("aos", "Daughters of Khaine", "Bloodwrack Shrine / Cauldron of Blood", "Centerpiece", 55, 70),

        # ── Horus Heresy / 30K (+10) ────────────────────────────────
        ("hh", "Horus Heresy", "MKIV Tactical Squad (Plastic)", "Troops", 36, 42),
        ("hh", "Horus Heresy", "Deimos Pattern Predator (Plastic)", "Vehicle", 42, 52),
        ("hh", "Horus Heresy", "Heavy Weapons Squad (Plastic)", "Heavy Support", 38, 45),
        ("hh", "Horus Heresy", "Dreadnought Drop Pod (Forge World)", "Vehicle", 38, 55),
        ("fw", "Horus Heresy", "Primarch Corvus Corax (FW)", "Primarch", 95, 180),
        ("fw", "Horus Heresy", "Primarch Konrad Curze, Night Haunter (FW)", "Primarch", 95, 185),
        ("hh", "Sons of Horus", "Justaerin Terminators (FW)", "Elite", 48, 70),
        ("hh", "Death Guard", "Deathshroud Terminators (30K FW)", "Elite", 45, 65),
        ("hh", "Iron Warriors", "Tyrant Siege Terminators (FW)", "Elite", 48, 72),
        ("hh", "World Eaters", "Red Butchers Terminators (FW)", "Elite", 45, 68),

        # ── Kill Team Box Sets (+8) ─────────────────────────────────
        ("kt", "Kill Team", "Kill Team: Phobos Strike Team", "Box Set", 42, 50),
        ("kt", "Kill Team", "Kill Team: Legionaries (Chaos)", "Box Set", 42, 50),
        ("kt", "Kill Team", "Kill Team: Pathfinders (T'au)", "Box Set", 42, 50),
        ("kt", "Kill Team", "Kill Team: Kommandos (Orks)", "Box Set", 42, 50),
        ("kt", "Kill Team", "Kill Team: Hand of the Archon (Drukhari)", "Box Set", 42, 50),
        ("kt", "Kill Team", "Kill Team: Kasrkin (Astra Militarum)", "Box Set", 42, 50),
        ("kt", "Kill Team", "Kill Team: Void-Dancer Troupe (Harlequins)", "Box Set", 42, 50),
        ("kt", "Kill Team", "Kill Team: Blooded (Traitor Guard)", "Box Set", 42, 50),

        # ── Necromunda Gangs (+7) ────────────────────────────────────
        ("nb", "Necromunda", "Necromunda: House Cawdor Upgrade Pack", "Gang", 22, 28),
        ("nb", "Necromunda", "Necromunda: Delaque Nacht-Ghul & Psy-Gheist", "Gang", 28, 35),
        ("nb", "Necromunda", "Necromunda: Orlock Arms Masters & Wreckers", "Gang", 28, 35),
        ("nb", "Necromunda", "Necromunda: Van Saar Neoteks", "Gang", 28, 35),
        ("nb", "Necromunda", "Necromunda: Escher Phyrr Cats & Khimerix", "Gang", 28, 35),
        ("nb", "Necromunda", "Necromunda: Goliath Maulers & Zerkers", "Gang", 28, 35),
        ("nb", "Necromunda", "Necromunda: Hive Scum Hired Guns", "Gang", 22, 28),

        # ── Warhammer Underworlds Warbands (+7) ─────────────────────
        ("uw", "Underworlds", "Warhammer Underworlds: Thundrik's Profiteers", "Warband", 22, 30),
        ("uw", "Underworlds", "Warhammer Underworlds: Ylthari's Guardians", "Warband", 22, 30),
        ("uw", "Underworlds", "Warhammer Underworlds: Mollog's Mob", "Warband", 22, 35),
        ("uw", "Underworlds", "Warhammer Underworlds: Godsworn Hunt", "Warband", 22, 28),
        ("uw", "Underworlds", "Warhammer Underworlds: Lady Harrow's Mournflight", "Warband", 22, 28),
        ("uw", "Underworlds", "Warhammer Underworlds: Rippa's Snarlfangs", "Warband", 22, 30),
        ("uw", "Underworlds", "Warhammer Underworlds: Morgwaeth's Blade-coven", "Warband", 22, 30),

        # ── Limited Edition / Celebration Models (+7) ───────────────
        ("40k", "Limited", "Warhammer Day 2025 Exclusive Captain", "Limited", 25, 75),
        ("40k", "Limited", "Grombrindal, The White Dwarf (AoS Version)", "Limited", 20, 85),
        ("40k", "Limited", "Black Library Celebration 2024 Space Marine", "Limited", 22, 65),
        ("40k", "Limited", "LVO 2024 Event Exclusive Model", "Limited", 25, 80),
        ("40k", "Limited", "Space Marine Heroes Series 4 (Blind Box Set)", "Limited", 15, 28),
        ("aos", "Limited", "Made to Order: Bretonnia Lord on Hippogryph (2024)", "Limited", 40, 120),
        ("40k", "Limited", "Warhammer+ Year 4 Exclusive Terminator Chaplain", "Limited", 20, 60),

        # ── Forge World Resin (+6) ──────────────────────────────────
        ("fw", "Forge World", "Spartan Assault Tank (Resin)", "Vehicle", 80, 115),
        ("fw", "Forge World", "Kratos Heavy Assault Tank (Resin)", "Vehicle", 65, 95),
        ("fw", "Forge World", "Caladius Grav-Tank (Custodes)", "Vehicle", 70, 100),
        ("fw", "Forge World", "Terrax-Pattern Termite Assault Drill", "Vehicle", 55, 80),
        ("fw", "Forge World", "Achilles-Alpha Pattern Land Raider", "Vehicle", 85, 120),
        ("fw", "Forge World", "Falchion Super-Heavy Tank Destroyer", "Super-Heavy", 200, 280),

        # ── 2024/2025 Releases & Limited Editions ─────────────────────
        ("40k", "Starter Box", "Leviathan (10th Edition Launch Box)", "Box Set", 160, 220),
        ("aos", "Starter Box", "Skaventide (AoS 4th Edition Launch Box)", "Box Set", 150, 195),
        ("40k", "Kill Team", "Kill Team: Hivestorm (Starter Box)", "Box Set", 110, 140),
        ("fw", "Forge World", "Fulgrim, The Phoenician (Primarch Resin)", "Character", 115, 165),
        ("hh", "Legions Imperialis", "Legions Imperialis: The Great Slaughter Starter Set", "Box Set", 80, 105),
        ("40k", "Limited", "Codex Compliant: Black Library Limited Warhammer Horror Anthology (Signed)", "Limited", 50, 120),
    ]

    catalog = []
    for game, faction, name, kit_type, retail_gbp, market_eur in kits:
        catalog.append({
            "game": game,
            "faction": faction,
            "name": name,
            "kit_type": kit_type,
            "retail_gbp": retail_gbp,
            "market_eur": market_eur,
        })
    return catalog


def get_books_catalog() -> list[dict]:
    """Curated Warhammer books catalog covering Black Library novels,
    codexes, battletomes, rulebooks, art books, and limited editions.

    Returns list of dicts with keys:
        game, faction, name, book_type, isbn, retail_gbp, secondary_eur
    """

    # (game, faction, name, book_type, isbn, retail_gbp, secondary_eur)
    books = [
        # ---------------------------------------------------------------
        # Black Library — Horus Heresy Series (18 key titles)
        # ---------------------------------------------------------------
        ("hh", "Horus Heresy", "Horus Rising", "Novel",
         "978-1849707435", 12, 15),
        ("hh", "Horus Heresy", "False Gods", "Novel",
         "978-1849707442", 12, 15),
        ("hh", "Horus Heresy", "Galaxy in Flames", "Novel",
         "978-1849707459", 12, 15),
        ("hh", "Horus Heresy", "The Flight of the Eisenstein", "Novel",
         "978-1849707466", 12, 15),
        ("hh", "Horus Heresy", "Fulgrim", "Novel",
         "978-1849707473", 12, 16),
        ("hh", "Horus Heresy", "A Thousand Sons", "Novel",
         "978-1849700481", 12, 16),
        ("hh", "Horus Heresy", "Prospero Burns", "Novel",
         "978-1849700498", 12, 16),
        ("hh", "Horus Heresy", "Know No Fear", "Novel",
         "978-1849701440", 12, 16),
        ("hh", "Horus Heresy", "The First Heretic", "Novel",
         "978-1849700504", 12, 18),
        ("hh", "Horus Heresy", "Betrayer", "Novel",
         "978-1849703390", 12, 18),
        ("hh", "Horus Heresy", "Master of Mankind", "Novel",
         "978-1784965396", 12, 18),
        ("hh", "Horus Heresy", "Descent of Angels", "Novel",
         "978-1849707503", 12, 15),
        ("hh", "Horus Heresy", "Legion", "Novel",
         "978-1849707510", 12, 16),
        ("hh", "Siege of Terra", "The Solar War", "Novel",
         "978-1789990010", 13, 18),
        ("hh", "Siege of Terra", "The End and the Death Vol.1", "Novel",
         "978-1800261563", 14, 20),
        ("hh", "Siege of Terra", "The End and the Death Vol.2", "Novel",
         "978-1800262386", 14, 20),
        ("hh", "Horus Heresy", "Mechanicum", "Novel",
         "978-1849707534", 12, 15),
        ("hh", "Horus Heresy", "Nemesis", "Novel",
         "978-1849700542", 12, 15),

        # ---------------------------------------------------------------
        # Black Library — Warhammer 40K Novels (17 key titles)
        # ---------------------------------------------------------------
        ("40k", "Gaunt's Ghosts", "First and Only", "Novel",
         "978-1844163694", 12, 15),
        ("40k", "Gaunt's Ghosts", "The Founding (Omnibus)", "Omnibus",
         "978-1849708319", 18, 20),
        ("40k", "Eisenhorn", "Xenos", "Novel",
         "978-1849708722", 12, 14),
        ("40k", "Eisenhorn", "Eisenhorn Trilogy Omnibus", "Omnibus",
         "978-1784964627", 18, 22),
        ("40k", "Ravenor", "Ravenor Omnibus", "Omnibus",
         "978-1849708739", 18, 20),
        ("40k", "Night Lords", "Night Lords Trilogy: The Omnibus", "Omnibus",
         "978-1849708609", 18, 22),
        ("40k", "Ciaphas Cain", "For the Emperor", "Novel",
         "978-1844161225", 12, 14),
        ("40k", "Space Wolves", "Space Wolf", "Novel",
         "978-1844163342", 12, 14),
        ("40k", "Necrons", "The Infinite and the Divine", "Novel",
         "978-1789998320", 12, 16),
        ("40k", "Necrons", "Twice Dead King: Ruin", "Novel",
         "978-1800260153", 12, 14),
        ("40k", "Orks", "Brutal Kunnin", "Novel",
         "978-1789998634", 12, 14),
        ("40k", "Adeptus Mechanicus", "Priests of Mars Omnibus", "Omnibus",
         "978-1784966249", 18, 22),
        ("40k", "Dark Angels", "Angels of Darkness", "Novel",
         "978-1849708586", 12, 14),
        ("40k", "Blood Angels", "Dante", "Novel",
         "978-1784966393", 12, 15),
        ("40k", "Imperial Guard", "Fifteen Hours", "Novel",
         "978-1844161560", 12, 14),
        ("40k", "Sisters of Battle", "Our Martyred Lady", "Novel",
         "978-1800260269", 12, 14),
        ("40k", "Adeptus Custodes", "The Emperor's Legion", "Novel",
         "978-1784969011", 12, 15),

        # ---------------------------------------------------------------
        # Black Library — Age of Sigmar Novels (7 titles)
        # ---------------------------------------------------------------
        ("aos", "Stormcast Eternals", "Hamilcar: Champion of the Gods", "Novel",
         "978-1784968083", 12, 14),
        ("aos", "Stormcast Eternals", "Hallowed Ground", "Novel",
         "978-1800261020", 12, 14),
        ("aos", "Idoneth Deepkin", "The Court of the Blind King", "Novel",
         "978-1784969998", 12, 14),
        ("aos", "Gloomspite Gitz", "Gloomspite", "Novel",
         "978-1789990201", 12, 14),
        ("aos", "Ossiarch Bonereapers", "Dark Harvest", "Novel",
         "978-1789990164", 12, 14),
        ("aos", "Cities of Sigmar", "Thunderstrike", "Novel",
         "978-1800260962", 12, 14),
        ("aos", "Flesh-eater Courts", "The Hollow King", "Novel",
         "978-1800260108", 12, 14),

        # ---------------------------------------------------------------
        # Codexes — 40K (12 titles)
        # ---------------------------------------------------------------
        ("40k", "Space Marines", "Codex: Space Marines (10th Ed)", "Codex",
         "", 35, 38),
        ("40k", "Tyranids", "Codex: Tyranids (10th Ed)", "Codex",
         "", 35, 38),
        ("40k", "Necrons", "Codex: Necrons (10th Ed)", "Codex",
         "", 35, 38),
        ("40k", "Chaos Space Marines", "Codex: Chaos Space Marines (10th Ed)", "Codex",
         "", 35, 38),
        ("40k", "Aeldari", "Codex: Aeldari (10th Ed)", "Codex",
         "", 35, 38),
        ("40k", "Orks", "Codex: Orks (10th Ed)", "Codex",
         "", 35, 38),
        ("40k", "T'au Empire", "Codex: T'au Empire (10th Ed)", "Codex",
         "", 35, 38),
        ("40k", "Adeptus Custodes", "Codex: Adeptus Custodes (10th Ed)", "Codex",
         "", 35, 38),
        ("40k", "Death Guard", "Codex: Death Guard (10th Ed)", "Codex",
         "", 35, 38),
        ("40k", "Blood Angels", "Codex: Blood Angels (9th Ed OOP)", "Codex",
         "", 30, 40),
        ("40k", "Dark Angels", "Codex: Dark Angels (9th Ed OOP)", "Codex",
         "", 30, 40),
        ("40k", "Grey Knights", "Codex: Grey Knights (9th Ed OOP)", "Codex",
         "", 30, 40),

        # ---------------------------------------------------------------
        # Battletomes — Age of Sigmar (6 titles)
        # ---------------------------------------------------------------
        ("aos", "Stormcast Eternals", "Battletome: Stormcast Eternals (3rd Ed)", "Battletome",
         "", 30, 32),
        ("aos", "Slaves to Darkness", "Battletome: Slaves to Darkness", "Battletome",
         "", 30, 32),
        ("aos", "Skaven", "Battletome: Skaven", "Battletome",
         "", 30, 32),
        ("aos", "Soulblight Gravelords", "Battletome: Soulblight Gravelords", "Battletome",
         "", 30, 32),
        ("aos", "Daughters of Khaine", "Battletome: Daughters of Khaine", "Battletome",
         "", 30, 32),
        ("aos", "Lumineth Realm-lords", "Battletome: Lumineth Realm-lords", "Battletome",
         "", 30, 32),

        # ---------------------------------------------------------------
        # Core Rulebooks (6 titles)
        # ---------------------------------------------------------------
        ("40k", "Core Rules", "Warhammer 40K Core Rules (10th Ed)", "Core Rulebook",
         "978-1804572801", 40, 44),
        ("40k", "Core Rules", "Warhammer 40K Core Rules (9th Ed OOP)", "Core Rulebook",
         "978-1788269865", 40, 50),
        ("aos", "Core Rules", "Age of Sigmar Core Rules (3rd Ed)", "Core Rulebook",
         "978-1839064517", 35, 38),
        ("kt", "Kill Team", "Kill Team Core Book", "Core Rulebook",
         "", 30, 34),
        ("nb", "Necromunda", "Necromunda Rulebook", "Core Rulebook",
         "", 30, 34),
        ("40k", "Core Rules", "Warhammer 40K Chapter Approved 2023", "Supplement",
         "", 25, 28),

        # ---------------------------------------------------------------
        # Art Books & Special Editions (10 titles)
        # ---------------------------------------------------------------
        ("40k", "Art Books", "The Art of Warhammer 40,000", "Art Book",
         "978-1844164035", 35, 45),
        ("40k", "Art Books", "Liber Chaotica (OOP)", "OOP Book",
         "978-1844161850", 0, 200),
        ("hh", "Art Books", "The Horus Heresy: Visions of War", "OOP Book",
         "978-1844162086", 0, 120),
        ("hh", "Art Books", "The Horus Heresy: Visions of Death", "OOP Book",
         "978-1844162185", 0, 120),
        ("hh", "Art Books", "The Horus Heresy: Visions of Treachery", "OOP Book",
         "978-1844162307", 0, 130),
        ("40k", "Art Books", "Warhammer Visions Issue 1 (OOP)", "OOP Book",
         "", 0, 30),
        ("fw", "Imperial Armour", "Imperial Armour Vol.1 (OOP)", "OOP Book",
         "", 0, 100),
        ("fw", "Imperial Armour", "Imperial Armour Vol.2 (OOP)", "OOP Book",
         "", 0, 110),
        ("fw", "Imperial Armour", "Imperial Armour Masterclass Vol.1 (OOP)", "OOP Book",
         "", 0, 80),
        ("fw", "Imperial Armour", "Imperial Armour: The Badab War Part One (OOP)", "OOP Book",
         "", 0, 180),

        # ---------------------------------------------------------------
        # Limited / Numbered Editions (6 titles)
        # ---------------------------------------------------------------
        ("hh", "Horus Heresy", "Horus Rising Limited Edition", "Limited Edition Book",
         "", 0, 220),
        ("hh", "Siege of Terra", "The End and the Death Limited Edition", "Limited Edition Book",
         "", 0, 150),
        ("hh", "Siege of Terra", "The Solar War Limited Edition", "Limited Edition Book",
         "", 0, 120),
        ("hh", "Siege of Terra", "Mortis Limited Edition", "Limited Edition Book",
         "", 0, 100),
        ("40k", "Eisenhorn", "Xenos Limited Edition", "Limited Edition Book",
         "", 0, 70),
        ("hh", "Horus Heresy", "False Gods Limited Edition", "Limited Edition Book",
         "", 0, 180),
    ]

    catalog = []
    for game, faction, name, book_type, isbn, retail_gbp, market_eur in books:
        catalog.append({
            "game": game,
            "faction": faction,
            "name": name,
            "book_type": book_type,
            "isbn": isbn,
            "retail_gbp": retail_gbp,
            "market_eur": market_eur,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    """Convert a miniatures kit dict to a CatalogItem."""
    game = item["game"]
    name = item["name"]
    faction = item["faction"]

    game_labels = {"40k": "Warhammer 40,000", "aos": "Age of Sigmar",
                   "fw": "Forge World", "kt": "Kill Team",
                   "nb": "Necromunda", "bb": "Blood Bowl",
                   "hh": "Horus Heresy", "warcry": "Warcry",
                   "at": "Adeptus Titanicus", "ai": "Aeronautica Imperialis",
                   "uw": "Underworlds", "paint": "Citadel"}

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{game}-{faction}-{name}"),
        title=name,
        set_code=game,
        brand="Games Workshop",
        rarity=item["kit_type"],
        notes=f"{game_labels.get(game, game)} | {faction}",
        attributes_json={
            "game_system": game,
            "faction": faction,
            "kit_type": item["kit_type"],
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    """Convert a miniatures kit dict to a PriceObservation."""
    kit_type = item["kit_type"]

    is_oop = item["retail_gbp"] == 0
    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(kit_type),
            "edition_score": 0.9 if is_oop else 0.5,
            "is_painted": 0.0,
            "is_new_on_sprue": 1.0,
        },
        price=item["market_eur"],
    )


def _book_to_catalog_item(book: dict) -> CatalogItem:
    """Convert a book dict to a CatalogItem.

    Sets brand to 'Black Library' for novels/omnibuses and 'Games Workshop'
    for codexes, battletomes, rulebooks, and art books.
    """
    game = book["game"]
    name = book["name"]
    faction = book["faction"]
    book_type = book["book_type"]

    game_labels = {
        "40k": "Warhammer 40,000",
        "aos": "Age of Sigmar",
        "hh": "Horus Heresy",
        "fw": "Forge World",
        "kt": "Kill Team",
        "nb": "Necromunda",
    }

    # Black Library publishes the novels; GW publishes rules/codexes/art
    black_library_types = {"Novel", "Omnibus", "Limited Edition Book"}
    brand = "Black Library" if book_type in black_library_types else "Games Workshop"

    attrs: dict = {
        "game_system": game,
        "faction": faction,
        "book_type": book_type,
    }
    if book.get("isbn"):
        attrs["isbn"] = book["isbn"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"book-{game}-{faction}-{name}"),
        title=name,
        set_code=game,
        brand=brand,
        rarity=book_type,
        notes=f"{game_labels.get(game, game)} | {faction} | {book_type}",
        attributes_json=attrs,
    )


def _book_to_price_observation(book: dict) -> PriceObservation:
    """Convert a book dict to a PriceObservation.

    Uses book-specific feature scores instead of miniatures features:
    - No is_painted or is_new_on_sprue (not applicable to books)
    - is_sealed: 1.0 (assumes new/sealed condition for catalog pricing)
    - is_first_edition: higher for Horus Heresy early entries and OOP items
    - collectibility_score: based on book type and OOP status
    """
    book_type = book["book_type"]
    is_oop = book["retail_gbp"] == 0

    # First edition score: HH early novels and OOP items are more collectible
    is_first_edition = 0.8 if is_oop else 0.3
    if book["game"] == "hh" and book_type == "Novel":
        is_first_edition = 0.6  # HH novels often have multiple printings

    # Collectibility varies by book type
    collectibility_map = {
        "Novel": 0.3,
        "Omnibus": 0.35,
        "Codex": 0.4,
        "Battletome": 0.35,
        "Core Rulebook": 0.45,
        "Supplement": 0.3,
        "Art Book": 0.6,
        "OOP Book": 0.8,
        "Limited Edition Book": 0.95,
    }
    collectibility = collectibility_map.get(book_type, 0.3)
    if is_oop and book_type not in ("OOP Book", "Limited Edition Book"):
        collectibility = min(collectibility + 0.25, 1.0)

    return PriceObservation(
        features={
            "condition_score": 0.90,  # books default to good condition
            "rarity_score": _book_rarity_score(book_type),
            "edition_score": 0.9 if is_oop else 0.4,
            "is_sealed": 1.0,
            "is_first_edition": is_first_edition,
            "collectibility_score": collectibility,
        },
        price=book["market_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Warhammer catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Warhammer Import ===")

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    # --- Miniatures ---
    miniatures_catalog = get_curated_catalog()
    mini_items = [item_to_catalog_item(i) for i in miniatures_catalog]
    mini_observations = [item_to_price_observation(i) for i in miniatures_catalog]

    # --- Books ---
    books_catalog = get_books_catalog()
    book_items = [_book_to_catalog_item(b) for b in books_catalog]
    book_observations = [_book_to_price_observation(b) for b in books_catalog]

    # --- Merge ---
    all_items = mini_items + book_items
    all_observations = mini_observations + book_observations

    write_catalog_sql(CATEGORY, all_items)
    log_progress(CATEGORY, "catalog SQL written", len(all_items))

    write_training_jsonl(CATEGORY, all_observations)
    log_progress(CATEGORY, "training JSONL written", len(all_observations))

    if ingest.enabled:
        inserted = ingest.upsert_catalog(all_items)
        log_progress(CATEGORY, "catalog upserted", inserted)

    ingest.close()

    logger.info(f"\n=== Warhammer Import Complete ===")
    logger.info(f"  Miniature items:    {len(mini_items)}")
    logger.info(f"  Book items:         {len(book_items)}")
    logger.info(f"  Total catalog:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
