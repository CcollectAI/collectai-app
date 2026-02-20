"""
Import Warhammer & tabletop miniatures + books catalog.

Layer 1 (Catalog):  Core kits, centerpieces, books → category_items
Layer 2 (Prices):   GW retail + secondary market estimates → train.jsonl

No official GW API exists. Uses curated data covering:

Miniatures (~50 items):
- Warhammer 40K (Space Marines, Chaos, Xenos, Knights, Titans)
- Age of Sigmar (Stormcast, Chaos, Death, Destruction)
- Horus Heresy / Forge World
- Kill Team, Necromunda, Blood Bowl

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
                   "nb": "Necromunda", "bb": "Blood Bowl"}

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
