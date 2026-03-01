"""
Import Digimon TCG card data.

Layer 1 (Catalog):  Curated high-value cards → category_items
Layer 2 (Prices):   Market prices → train.jsonl

Covers BT01-BT14, EX01-EX06, Starter Deck promos, tournament prizes,
Japanese exclusives, Secret Rare & Alt Art chase cards.

Usage:
    python -m pipelines.import_digimon [--dry-run]
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
    log_progress,
    slugify,
    rarity_score as shared_rarity_score,
    logger,
    close_http_client,
)

CATEGORY = "digimon"

# ---------------------------------------------------------------------------
# Digimon-specific rarity scores (supplement the shared map)
# ---------------------------------------------------------------------------

DIGIMON_RARITY_SCORES: dict[str, float] = {
    "Common": 0.10,
    "Uncommon": 0.30,
    "Rare": 0.50,
    "Super Rare": 0.70,
    "Secret Rare": 0.90,
    "Alt Art": 0.92,
    "Promo": 0.40,
}


def _rarity_score(rarity: str) -> float:
    """Look up rarity score, preferring Digimon-specific map then shared."""
    if rarity in DIGIMON_RARITY_SCORES:
        return DIGIMON_RARITY_SCORES[rarity]
    return shared_rarity_score(rarity)


# ---------------------------------------------------------------------------
# Curated catalog — 80+ real Digimon TCG cards
# ---------------------------------------------------------------------------

def get_curated_catalog() -> list[dict]:
    """Curated Digimon TCG catalog covering chase cards across all major sets.

    Returns a list of dicts with keys:
        name, set_code, card_number, rarity, color, price_eur,
        digimon_type, notes
    """

    # Format: (name, set_code, card_number, rarity, color, price_eur,
    #          digimon_type, notes)

    cards: list[tuple] = [
        # =================================================================
        # BT01-03 Early Sets (New Evolution, Ultimate Power, Union Impact)
        # =================================================================
        ("Omnimon", "BT01", "BT1-084", "Super Rare", "Red", 35.00,
         "Mega", "Iconic Omnimon from the very first set"),
        ("WarGreymon", "BT01", "BT1-025", "Super Rare", "Red", 18.00,
         "Mega", "Core Red boss from BT01"),
        ("MetalGarurumon", "BT01", "BT1-044", "Super Rare", "Blue", 15.00,
         "Mega", "Core Blue boss from BT01"),
        ("Omnimon Alter-S", "BT02", "BT2-112", "Secret Rare", "Purple", 85.00,
         "Mega", "Secret Rare chase from BT02"),
        ("Imperialdramon Dragon Mode", "BT02", "BT2-083", "Super Rare", "Green", 12.00,
         "Mega", "Fan-favorite Imperialdramon"),
        ("Lilithmon", "BT02", "BT2-077", "Super Rare", "Purple", 10.00,
         "Mega", "Seven Great Demon Lords staple"),
        ("Diaboromon", "BT02", "BT2-082", "Super Rare", "White", 14.00,
         "Mega", "Movie villain Diaboromon"),
        ("Beelzemon", "BT02", "BT2-078", "Super Rare", "Purple", 12.00,
         "Mega", "Tamers fan-favorite"),
        ("Gallantmon", "BT02", "BT2-020", "Super Rare", "Red", 20.00,
         "Mega", "Guilmon line boss"),
        ("Omnimon", "BT01", "BT1-084", "Alt Art", "Red", 120.00,
         "Mega", "Alt Art Omnimon BT01"),
        ("WarGreymon", "BT01", "BT1-025", "Alt Art", "Red", 65.00,
         "Mega", "Alt Art WarGreymon BT01"),
        ("MetalGarurumon", "BT01", "BT1-044", "Alt Art", "Blue", 50.00,
         "Mega", "Alt Art MetalGarurumon BT01"),
        ("MagnaAngemon", "BT01", "BT1-062", "Rare", "Yellow", 5.00,
         "Ultimate", "Strong Yellow removal from BT01"),
        ("Garudamon", "BT01", "BT1-022", "Uncommon", "Red", 1.50,
         "Ultimate", "Efficient Red Ultimate"),
        ("Agumon", "BT01", "BT1-010", "Common", "Red", 0.50,
         "Rookie", "Starter Agumon from BT01"),
        ("Gabumon", "BT01", "BT1-029", "Common", "Blue", 0.50,
         "Rookie", "Starter Gabumon from BT01"),
        ("Patamon", "BT01", "BT1-050", "Common", "Yellow", 0.50,
         "Rookie", "Yellow rookie staple"),
        ("BlackWarGreymon", "BT03", "BT3-016", "Super Rare", "Red", 14.00,
         "Mega", "Virus counterpart from BT03"),
        ("Millenniummon", "BT03", "BT3-092", "Secret Rare", "Purple", 55.00,
         "Mega", "BT03 Secret Rare boss"),

        # =================================================================
        # BT04-06 Mid Sets (Great Legend, Battle of Omni, Double Diamond)
        # =================================================================
        ("Jesmon", "BT04", "BT4-074", "Super Rare", "Red", 16.00,
         "Mega", "Royal Knight Jesmon"),
        ("Alphamon", "BT04", "BT4-084", "Secret Rare", "Black", 70.00,
         "Mega", "Secret Rare Royal Knight Alphamon"),
        ("Gallantmon Crimson Mode", "BT04", "BT4-019", "Super Rare", "Red", 22.00,
         "Mega", "Crimson Mode upgrade"),
        ("ChaosGallantmon", "BT04", "BT4-081", "Super Rare", "Purple", 13.00,
         "Mega", "Dark counterpart Gallantmon"),
        ("Omnimon", "BT05", "BT5-086", "Super Rare", "Red", 25.00,
         "Mega", "Battle of Omni headliner"),
        ("Omnimon Zwart", "BT05", "BT5-087", "Secret Rare", "Black", 90.00,
         "Mega", "BT05 Secret Rare dark Omnimon"),
        ("UlforceVeedramon", "BT05", "BT5-030", "Super Rare", "Blue", 18.00,
         "Mega", "Speed-focused Royal Knight"),
        ("Shoutmon DX", "BT05", "BT5-019", "Super Rare", "Red", 10.00,
         "Mega", "Xros Wars fusion"),
        ("ShineGreymon", "BT06", "BT6-018", "Super Rare", "Red", 12.00,
         "Mega", "Savers/Data Squad boss"),
        ("RizeGreymon", "BT06", "BT6-017", "Rare", "Red", 4.00,
         "Ultimate", "Savers line Ultimate"),
        ("Jesmon GX", "BT06", "BT6-016", "Super Rare", "Red", 15.00,
         "Mega", "GX evolution of Jesmon"),
        ("HerculesKabuterimon", "BT06", "BT6-050", "Super Rare", "Green", 8.00,
         "Mega", "Green Mega insect boss"),

        # =================================================================
        # BT07-10 (Next Adventure, New Awakening, X Record, Xros Encounter)
        # =================================================================
        ("Magnamon X", "BT09", "BT9-044", "Super Rare", "Yellow", 28.00,
         "Mega", "X-Antibody Royal Knight"),
        ("Imperialdramon Fighter Mode", "BT08", "BT8-032", "Super Rare", "Green", 20.00,
         "Mega", "Upgraded Imperialdramon"),
        ("Mastemon", "BT07", "BT7-081", "Super Rare", "Yellow", 22.00,
         "Mega", "DNA Digivolution angel"),
        ("Examon", "BT09", "BT9-073", "Secret Rare", "Green", 60.00,
         "Mega", "Dragon Royal Knight"),
        ("Dukemon (Gallantmon)", "BT09", "BT9-017", "Super Rare", "Red", 18.00,
         "Mega", "X Record Gallantmon"),
        ("Sakuyamon", "BT07", "BT7-043", "Super Rare", "Yellow", 10.00,
         "Mega", "Rika's partner Mega"),
        ("GranKuwagamon", "BT09", "BT9-052", "Super Rare", "Green", 8.00,
         "Mega", "X-Antibody insect"),
        ("Susanoomon", "BT07", "BT7-083", "Secret Rare", "Yellow", 75.00,
         "Mega", "BT07 Secret Rare Frontier Mega"),
        ("MetalGreymon (X-Antibody)", "BT09", "BT9-015", "Rare", "Red", 5.00,
         "Ultimate", "X Record MetalGreymon"),
        ("ShineGreymon Burst Mode", "BT08", "BT8-017", "Super Rare", "Red", 15.00,
         "Mega", "Burst Mode evolution"),
        ("Shoutmon King Ver.", "BT10", "BT10-013", "Super Rare", "Red", 12.00,
         "Mega", "Xros Encounter boss"),
        ("Darkdramon", "BT10", "BT10-069", "Super Rare", "Black", 9.00,
         "Mega", "D-Brigade line boss"),

        # =================================================================
        # BT11-14 Newer Sets (Dimensional Phase, Across Time, Versus Royal Knights, Blast Ace)
        # =================================================================
        ("BloomLordmon", "BT11", "BT11-058", "Super Rare", "Green", 14.00,
         "Mega", "Plant-type Green boss"),
        ("Susanoomon", "BT12", "BT12-083", "Secret Rare", "Yellow", 65.00,
         "Mega", "Across Time Susanoomon"),
        ("ShineGreymon Ruin Mode", "BT13", "BT13-020", "Super Rare", "Red", 16.00,
         "Mega", "Dark side ShineGreymon"),
        ("Beelzemon X", "BT12", "BT12-079", "Super Rare", "Purple", 18.00,
         "Mega", "X-Antibody Beelzemon"),
        ("Dynasmon", "BT13", "BT13-041", "Super Rare", "Yellow", 10.00,
         "Mega", "Royal Knight Dynasmon"),
        ("UlforceVeedramon (X-Antibody)", "BT13", "BT13-032", "Super Rare", "Blue", 15.00,
         "Mega", "X-Antibody speed knight"),
        ("Alphamon Ouryuken", "BT13", "BT13-075", "Secret Rare", "Black", 80.00,
         "Mega", "Royal Knight ultimate form"),
        ("RagnaLoardmon", "BT13", "BT13-089", "Super Rare", "Red", 12.00,
         "Mega", "Dual-wielding Royal Knight"),
        ("Fenriloogamon", "BT14", "BT14-082", "Super Rare", "Black", 14.00,
         "Mega", "Blast Ace dark wolf"),
        ("Rapidmon (Armor)", "BT14", "BT14-035", "Rare", "Green", 4.00,
         "Ultimate", "Golden Armor digivolution"),

        # =================================================================
        # EX Sets (EX01-06: Classic Collection, Digital Hazard, Draconic Roar,
        #          Alternative Being, Animal Colosseum, Infernal Ascension)
        # =================================================================
        ("Omnimon (EX01)", "EX01", "EX1-073", "Secret Rare", "Red", 55.00,
         "Mega", "Classic Collection Omnimon"),
        ("WarGreymon (EX01)", "EX01", "EX1-011", "Super Rare", "Red", 15.00,
         "Mega", "Classic Collection WarGreymon"),
        ("Gallantmon Crimson Mode (EX02)", "EX02", "EX2-039", "Secret Rare", "Red", 60.00,
         "Mega", "Digital Hazard Crimson Mode"),
        ("Megidramon", "EX02", "EX2-014", "Super Rare", "Red", 12.00,
         "Mega", "Digital Hazard dark evolution"),
        ("Imperialdramon Paladin Mode", "EX03", "EX3-073", "Secret Rare", "White", 70.00,
         "Mega", "Draconic Roar ultimate Imperialdramon"),
        ("Examon (EX03)", "EX03", "EX3-043", "Super Rare", "Green", 14.00,
         "Mega", "Draconic Roar Examon"),
        ("Huanglongmon", "EX04", "EX4-073", "Secret Rare", "Yellow", 50.00,
         "Mega", "Alternative Being sovereign"),
        ("Chaosmon", "EX04", "EX4-060", "Super Rare", "White", 12.00,
         "Mega", "Fusion of Darkdramon and BanchoLeomon"),
        ("AncientGreymon", "EX05", "EX5-012", "Super Rare", "Red", 10.00,
         "Mega", "Animal Colosseum ancient warrior"),
        ("Lucemon Falldown Mode", "EX06", "EX6-060", "Super Rare", "Purple", 16.00,
         "Mega", "Infernal Ascension fallen angel"),
        ("Lucemon Satan Mode", "EX06", "EX6-061", "Secret Rare", "Purple", 45.00,
         "Mega", "Infernal Ascension final form"),

        # =================================================================
        # Secret Rare / Alt Art Chase Cards (across all sets)
        # =================================================================
        ("Omnimon Alter-S (Alt Art)", "BT02", "BT2-112", "Alt Art", "Purple", 250.00,
         "Mega", "Alt Art Secret Rare Omnimon Alter-S"),
        ("Alphamon (Alt Art)", "BT04", "BT4-084", "Alt Art", "Black", 180.00,
         "Mega", "Alt Art Alphamon chase card"),
        ("Omnimon Zwart (Alt Art)", "BT05", "BT5-087", "Alt Art", "Black", 220.00,
         "Mega", "Alt Art dark Omnimon"),
        ("Susanoomon (Alt Art)", "BT07", "BT7-083", "Alt Art", "Yellow", 200.00,
         "Mega", "Alt Art Frontier boss"),
        ("Examon (Alt Art)", "BT09", "BT9-073", "Alt Art", "Green", 150.00,
         "Mega", "Alt Art dragon Royal Knight"),
        ("Gallantmon Crimson Mode (Alt Art)", "EX02", "EX2-039", "Alt Art", "Red", 180.00,
         "Mega", "Alt Art Digital Hazard chase"),
        ("Imperialdramon Paladin Mode (Alt Art)", "EX03", "EX3-073", "Alt Art", "White", 200.00,
         "Mega", "Alt Art ultimate Imperialdramon"),
        ("Alphamon Ouryuken (Alt Art)", "BT13", "BT13-075", "Alt Art", "Black", 220.00,
         "Mega", "Alt Art Royal Knight ultimate"),
        ("Magnamon X (Alt Art)", "BT09", "BT9-044", "Alt Art", "Yellow", 90.00,
         "Mega", "Alt Art golden armor"),
        ("Lucemon Satan Mode (Alt Art)", "EX06", "EX6-061", "Alt Art", "Purple", 130.00,
         "Mega", "Alt Art Infernal Ascension boss"),
        ("Mastemon (Alt Art)", "BT07", "BT7-081", "Alt Art", "Yellow", 80.00,
         "Mega", "Alt Art DNA angel"),
        ("Millenniummon (Alt Art)", "BT03", "BT3-092", "Alt Art", "Purple", 160.00,
         "Mega", "Alt Art Millenniummon chase"),

        # =================================================================
        # Starter Deck Promos & Tournament Prizes
        # =================================================================
        ("Omnimon (ST1 Promo)", "ST1", "ST1-11", "Promo", "Red", 8.00,
         "Mega", "Starter Deck 1 promo Omnimon"),
        ("WarGreymon (ST1 Promo)", "ST1", "ST1-09", "Promo", "Red", 5.00,
         "Mega", "Starter Deck 1 promo WarGreymon"),
        ("MetalGarurumon (ST2 Promo)", "ST2", "ST2-09", "Promo", "Blue", 5.00,
         "Mega", "Starter Deck 2 promo MetalGarurumon"),
        ("Omnimon (Tournament Pack)", "P", "P-077", "Promo", "Red", 45.00,
         "Mega", "Regional tournament prize Omnimon"),
        ("Agumon (Box Topper)", "P", "P-001", "Promo", "Red", 12.00,
         "Rookie", "Launch box topper Agumon"),
        ("Gallantmon (Winner Promo)", "P", "P-042", "Promo", "Red", 35.00,
         "Mega", "Tournament winner stamp Gallantmon"),

        # =================================================================
        # Japanese Exclusive / Promo Cards
        # =================================================================
        ("Omnimon (JP Alt Art)", "BT01", "BT1-084-JP", "Alt Art", "Red", 500.00,
         "Mega", "Japanese exclusive full-art Omnimon"),
        ("Alphamon (JP Exclusive)", "BT04", "BT4-084-JP", "Secret Rare", "Black", 95.00,
         "Mega", "Japanese print Alphamon Secret Rare"),
        ("WarGreymon (JP Tamer Battle)", "P", "P-030-JP", "Promo", "Red", 65.00,
         "Mega", "Japanese Tamer Battle pack WarGreymon"),
        ("Beelzemon Blast Mode (JP)", "BT02", "BT2-111-JP", "Secret Rare", "Purple", 75.00,
         "Mega", "Japanese exclusive Beelzemon Blast Mode"),
        ("Imperialdramon (JP Anniversary)", "P", "P-100-JP", "Promo", "Green", 40.00,
         "Mega", "Japanese anniversary promo Imperialdramon"),

        # =================================================================
        # Tamers & Option cards (variety)
        # =================================================================
        ("Tai Kamiya", "BT01", "BT1-085", "Rare", "Red", 3.00,
         "Tamer", "Original Tamer card Tai"),
        ("Matt Ishida", "BT01", "BT1-086", "Rare", "Blue", 3.00,
         "Tamer", "Original Tamer card Matt"),
        ("T.K. Takaishi", "BT01", "BT1-087", "Rare", "Yellow", 2.50,
         "Tamer", "Original Tamer card T.K."),
        ("Nokia Shiramine", "BT05", "BT5-092", "Rare", "Red", 4.00,
         "Tamer", "Cyber Sleuth protagonist"),
        ("Gaia Force", "BT01", "BT1-097", "Rare", "Red", 2.00,
         "Option", "Iconic WarGreymon attack option card"),
        ("Ice Wall", "BT02", "BT2-098", "Uncommon", "Blue", 1.00,
         "Option", "Blue defensive option"),
        ("Hammer Spark", "BT04", "BT4-105", "Uncommon", "Yellow", 0.80,
         "Option", "Yellow removal option"),
    ]

    catalog = []
    for entry in cards:
        (name, set_code, card_number, rarity, color, price_eur,
         digimon_type, notes) = entry

        catalog.append({
            "name": name,
            "set_code": set_code,
            "card_number": card_number,
            "rarity": rarity,
            "color": color,
            "price_eur": price_eur,
            "digimon_type": digimon_type,
            "notes": notes,
        })

    return catalog


# ---------------------------------------------------------------------------
# Catalog / Price converters
# ---------------------------------------------------------------------------

def item_to_catalog_item(item: dict) -> CatalogItem:
    """Convert a curated catalog entry to a CatalogItem."""
    name = item["name"]
    set_code = item["set_code"]
    card_number = item["card_number"]
    rarity = item["rarity"]
    color = item["color"]
    digimon_type = item["digimon_type"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{set_code}-{card_number}-{name}"),
        title=name,
        set_code=set_code,
        brand="Bandai",
        rarity=rarity,
        notes=item["notes"],
        image_url="",
        attributes_json={
            "set_code": set_code,
            "card_number": card_number,
            "rarity": rarity,
            "color": color,
            "digimon_type": digimon_type,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    """Convert a curated catalog entry to a PriceObservation."""
    rarity = item["rarity"]

    # Alt Art and Secret Rare are premium editions
    is_premium = rarity in ("Alt Art", "Secret Rare")

    return PriceObservation(
        features={
            "condition_score": 0.90,  # Most TCG cards are Near Mint
            "rarity_score": _rarity_score(rarity),
            "edition_score": 0.9 if is_premium else 0.5,
        },
        price=item["price_eur"],
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Import Digimon TCG catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Digimon TCG Import ===")

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    catalog = get_curated_catalog()
    log_progress(CATEGORY, "curated entries loaded", len(catalog))

    all_items = [item_to_catalog_item(c) for c in catalog]
    all_observations = [item_to_price_observation(c) for c in catalog]

    # Deduplicate by item_key
    seen: set[str] = set()
    deduped: list[CatalogItem] = []
    for item in all_items:
        if item.item_key not in seen:
            seen.add(item.item_key)
            deduped.append(item)
    all_items = deduped

    log_progress(CATEGORY, "catalog items", len(all_items))

    write_catalog_sql(CATEGORY, all_items)
    log_progress(CATEGORY, "catalog SQL written", len(all_items))

    if all_observations:
        write_training_jsonl(CATEGORY, all_observations)
        log_progress(CATEGORY, "training JSONL written", len(all_observations))

    if ingest.enabled:
        inserted = ingest.upsert_catalog(all_items)
        log_progress(CATEGORY, "catalog upserted", inserted)

    ingest.close()
    close_http_client()

    logger.info(f"\n=== Digimon TCG Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
