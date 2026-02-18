"""
Import Warhammer & tabletop miniatures catalog.

Layer 1 (Catalog):  Core kits + centerpieces → category_items
Layer 2 (Prices):   GW retail + secondary market estimates → train.jsonl

No official GW API exists. Uses curated data covering:
- Warhammer 40K (Space Marines, Chaos, Xenos, Knights, Titans)
- Age of Sigmar (Stormcast, Chaos, Death, Destruction)
- Horus Heresy / Forge World
- Kill Team, Necromunda, Blood Bowl

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


def get_curated_catalog() -> list[dict]:
    """Curated Warhammer catalog covering key factions and price tiers."""

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


def item_to_catalog_item(item: dict) -> CatalogItem:
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


def main():
    parser = argparse.ArgumentParser(description="Import Warhammer catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Warhammer Import ===")

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    catalog = get_curated_catalog()

    all_items = [item_to_catalog_item(i) for i in catalog]
    all_observations = [item_to_price_observation(i) for i in catalog]

    write_catalog_sql(CATEGORY, all_items)
    log_progress(CATEGORY, "catalog SQL written", len(all_items))

    write_training_jsonl(CATEGORY, all_observations)
    log_progress(CATEGORY, "training JSONL written", len(all_observations))

    if ingest.enabled:
        inserted = ingest.upsert_catalog(all_items)
        log_progress(CATEGORY, "catalog upserted", inserted)

    ingest.close()

    logger.info(f"\n=== Warhammer Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
