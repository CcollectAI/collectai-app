"""
Curated Fountain Pen Import Pipeline — Collectible Writing Instruments.

Imports a curated catalog of 80+ collectible fountain pens across 10 subcategories:
  Montblanc, Pelikan, Sailor, Pilot, Lamy, Visconti, Aurora, Nakaya,
  Vintage Classics, Japanese Artisan/Maki-e

Each entry has real model names, nib material, nib size, filling system,
limited edition status, and realistic EUR secondary market price.

Pattern follows import_keycaps.py / import_watches.py (get_curated_catalog,
item_to_catalog_item, item_to_price_observation).

Usage:
    python -m pipelines.import_pens [--dry-run]
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

CATEGORY = "pens"

# ---------------------------------------------------------------------------
# Brand tier scoring for ML features
# ---------------------------------------------------------------------------
BRAND_TIER: dict[str, float] = {
    "Montblanc": 1.0,
    "Nakaya": 1.0,
    "Pelikan": 0.9,
    "Sailor": 0.9,
    "Pilot": 0.8,
    "Namiki": 0.8,
    "Aurora": 0.8,
    "Visconti": 0.8,
    "Platinum": 0.8,
    "Lamy": 0.6,
    "Parker": 0.7,
    "Sheaffer": 0.7,
    "Waterman": 0.7,
    "Conklin": 0.6,
}

# ---------------------------------------------------------------------------
# Nib material scoring for ML features
# ---------------------------------------------------------------------------
NIB_MATERIAL_SCORES: dict[str, float] = {
    "18k Gold": 1.0,
    "14k Gold": 1.0,
    "21k Gold": 1.0,
    "Palladium": 1.0,
    "Ruthenium": 0.5,
    "Steel": 0.7,
    "14k Gold (Flex)": 1.0,
    "14k Gold (Soft)": 1.0,
}


def _brand_tier(brand: str) -> float:
    """Map brand to a tier score."""
    return BRAND_TIER.get(brand, 0.6)


def _nib_material_score(material: str) -> float:
    """Map nib material to a 0-1 score."""
    return NIB_MATERIAL_SCORES.get(material, 0.7)


# ---------------------------------------------------------------------------
# Curated catalog — 80+ fountain pens
# Each tuple: (name, brand, model_line, nib_material, nib_size,
#               filling_system, price_eur, is_limited, rarity, notes)
# ---------------------------------------------------------------------------


def _montblanc_pens() -> list[tuple]:
    """15+ Montblanc fountain pens — Meisterstueck, Writers Edition, Heritage, LE."""
    return [
        ("Meisterstueck 149", "Montblanc", "Meisterstueck", "18k Gold", "M",
         "piston", 950, False, "Standard", "Flagship model, celluloid barrel"),
        ("Meisterstueck 146 Le Grand", "Montblanc", "Meisterstueck", "14k Gold", "F",
         "piston", 750, False, "Standard", "Mid-size classic, 14k nib"),
        ("Meisterstueck 145 Classique", "Montblanc", "Meisterstueck", "14k Gold", "M",
         "converter", 580, False, "Standard", "Slim profile, converter fill"),
        ("Writers Edition William Shakespeare", "Montblanc", "Writers Edition", "18k Gold", "M",
         "piston", 1200, True, "Limited Edition", "2016 LE, vermeil clip"),
        ("Writers Edition Antoine de Saint-Exupery", "Montblanc", "Writers Edition", "18k Gold", "F",
         "piston", 1400, True, "Limited Edition", "2017 LE, sand-colored lacquer"),
        ("Writers Edition Homage to Homer", "Montblanc", "Writers Edition", "18k Gold", "M",
         "piston", 1100, True, "Limited Edition", "2018 LE, dark blue lacquer"),
        ("Writers Edition Sir Arthur Conan Doyle", "Montblanc", "Writers Edition", "18k Gold", "B",
         "piston", 1300, True, "Limited Edition", "2021 LE, magnifying glass clip"),
        ("Writers Edition Brothers Grimm", "Montblanc", "Writers Edition", "18k Gold", "M",
         "piston", 1250, True, "Limited Edition", "2022 LE, forest green lacquer"),
        ("StarWalker Ultimate Carbon", "Montblanc", "StarWalker", "14k Gold", "M",
         "converter", 850, False, "Standard", "Carbon fiber barrel, modern design"),
        ("StarWalker Precious Resin", "Montblanc", "StarWalker", "14k Gold", "F",
         "converter", 650, False, "Standard", "Black resin, floating MB emblem"),
        ("Heritage Rouge et Noir", "Montblanc", "Heritage", "14k Gold", "M",
         "piston", 900, False, "Standard", "Art Deco-inspired, coral accent"),
        ("Heritage 1912 Capless", "Montblanc", "Heritage", "18k Gold", "M",
         "piston", 1050, True, "Limited Edition", "Retractable safety pen tribute"),
        ("Meisterstueck 149 Calligraphy", "Montblanc", "Meisterstueck", "18k Gold", "Stub",
         "piston", 1100, True, "Limited Edition", "Flex calligraphy nib"),
        ("Patron of Art Homage to Hadrian 4810", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 2800, True, "Limited Edition", "4810-piece LE, Roman motifs"),
        ("Great Characters Miles Davis", "Montblanc", "Great Characters", "18k Gold", "M",
         "piston", 1500, True, "Limited Edition", "Special edition, trumpet-inspired clip"),
        ("Meisterstueck 149 90th Anniversary", "Montblanc", "Meisterstueck", "18k Gold", "M",
         "piston", 1800, True, "Limited Edition", "Rose gold trim, burgundy lacquer"),
    ]


def _pelikan_pens() -> list[tuple]:
    """10+ Pelikan fountain pens — Souveraen, Toledo, special editions."""
    return [
        ("Souveraen M800 Black", "Pelikan", "Souveraen", "18k Gold", "M",
         "piston", 550, False, "Standard", "Flagship, striped celluloid"),
        ("Souveraen M800 Blue-Black", "Pelikan", "Souveraen", "18k Gold", "B",
         "piston", 550, False, "Standard", "Classic blue stripes"),
        ("Souveraen M1000", "Pelikan", "Souveraen", "18k Gold", "B",
         "piston", 750, False, "Standard", "Largest Souveraen, oversize nib"),
        ("Souveraen M600 Vibrant Green", "Pelikan", "Souveraen", "14k Gold", "F",
         "piston", 400, False, "Standard", "Special edition colorway"),
        ("Souveraen M400 White Tortoiseshell", "Pelikan", "Souveraen", "14k Gold", "EF",
         "piston", 350, False, "Standard", "Classic compact size"),
        ("Toledo M700 Silver", "Pelikan", "Toledo", "18k Gold", "M",
         "piston", 1200, False, "Standard", "Hand-engraved sterling silver"),
        ("Toledo M900", "Pelikan", "Toledo", "18k Gold", "B",
         "piston", 2500, True, "Limited Edition", "Large Toledo, elaborate engraving"),
        ("M800 Stone Garden", "Pelikan", "Souveraen", "18k Gold", "M",
         "piston", 700, True, "Limited Edition", "Special edition, marbled pattern"),
        ("M800 Renaissance Brown", "Pelikan", "Souveraen", "18k Gold", "M",
         "piston", 800, True, "Limited Edition", "Brown tortoiseshell resin"),
        ("M805 Ocean Swirl", "Pelikan", "Souveraen", "18k Gold", "F",
         "piston", 650, True, "Limited Edition", "Blue swirl demonstration barrel"),
        ("M200 Smoky Quartz", "Pelikan", "Classic", "Steel", "M",
         "piston", 130, True, "Limited Edition", "Ink of the Year edition"),
    ]


def _sailor_pens() -> list[tuple]:
    """10+ Sailor fountain pens — King of Pen, Pro Gear, 1911, Realo, Bespoke."""
    return [
        ("King of Pen Black", "Sailor", "King of Pen", "21k Gold", "M",
         "converter", 850, False, "Standard", "Oversized flagship, 21k nib"),
        ("King of Pen Ebonite", "Sailor", "King of Pen", "21k Gold", "B",
         "converter", 1200, True, "Limited Edition", "Ebonite barrel, urushi lacquer"),
        ("Pro Gear Classic Black", "Sailor", "Pro Gear", "21k Gold", "M",
         "converter", 350, False, "Standard", "Flat-top design, RESIN body"),
        ("Pro Gear Slim Shikiori Yonaga", "Sailor", "Pro Gear Slim", "14k Gold", "MF",
         "converter", 280, True, "Limited Edition", "Four Seasons series, autumn night"),
        ("1911 Large Black Gold", "Sailor", "1911", "21k Gold", "M",
         "converter", 400, False, "Standard", "Classic cigar shape"),
        ("1911 Standard Transparent", "Sailor", "1911", "14k Gold", "F",
         "converter", 250, False, "Standard", "Demonstrator model"),
        ("Realo Pro Gear Black", "Sailor", "Realo", "21k Gold", "M",
         "piston", 550, False, "Standard", "Piston-fill Pro Gear"),
        ("Pro Gear Cocktail Series Kure Azur", "Sailor", "Pro Gear", "21k Gold", "M",
         "converter", 450, True, "Limited Edition", "Cocktail-inspired colorway"),
        ("King of Pen Bespoke Tangerine", "Sailor", "Bespoke", "21k Gold", "B",
         "converter", 1500, True, "Limited Edition", "Wancher exclusive, urushi"),
        ("Pro Gear Realo Demonstrator", "Sailor", "Realo", "21k Gold", "MF",
         "piston", 600, True, "Limited Edition", "Transparent piston filler"),
        ("1911 Profit Naginata Togi", "Sailor", "1911", "21k Gold", "Stub",
         "converter", 700, False, "Standard", "Cross-point specialty nib"),
    ]


def _pilot_pens() -> list[tuple]:
    """10+ Pilot fountain pens — Namiki, Custom, VP, Myu."""
    return [
        ("Namiki Falcon", "Pilot", "Namiki", "14k Gold (Soft)", "F",
         "converter", 200, False, "Standard", "Soft semi-flex nib, metal barrel"),
        ("Custom 823 Amber", "Pilot", "Custom", "14k Gold", "M",
         "vacuum", 320, False, "Standard", "Vacuum-fill, large ink capacity"),
        ("Custom 823 Smoke", "Pilot", "Custom", "14k Gold", "F",
         "vacuum", 320, False, "Standard", "Smoke demonstrator variant"),
        ("Custom Urushi Vermillion", "Pilot", "Custom Urushi", "18k Gold", "M",
         "converter", 800, False, "Standard", "Hand-applied urushi lacquer"),
        ("Custom Urushi Black", "Pilot", "Custom Urushi", "18k Gold", "B",
         "converter", 800, False, "Standard", "24-layer urushi finish"),
        ("Vanishing Point Matte Black", "Pilot", "Vanishing Point", "18k Gold", "M",
         "converter", 200, False, "Standard", "Click retractable nib"),
        ("Vanishing Point Decimo Champagne", "Pilot", "Vanishing Point", "18k Gold", "F",
         "converter", 220, False, "Standard", "Slimmer VP variant"),
        ("Myu 701", "Pilot", "Myu", "Steel", "F",
         "converter", 600, False, "Exclusive", "Vintage integrated nib, stainless steel"),
        ("Custom 743 Deep Red", "Pilot", "Custom", "14k Gold", "B",
         "converter", 280, False, "Standard", "Size 15 nib, large barrel"),
        ("Custom Heritage 92 Demonstrator", "Pilot", "Custom Heritage", "14k Gold", "M",
         "piston", 180, False, "Standard", "Clear piston-fill demonstrator"),
        ("Namiki Yukari Nightline Milky Way", "Pilot", "Namiki Yukari", "18k Gold", "M",
         "converter", 2500, True, "Limited Edition", "Maki-e raden art, mother of pearl"),
    ]


def _lamy_pens() -> list[tuple]:
    """6+ Lamy fountain pens — 2000, Dialog, Safari LE."""
    return [
        ("2000 Black Makrolon", "Lamy", "2000", "14k Gold", "EF",
         "piston", 350, False, "Standard", "Bauhaus design icon, hooded nib"),
        ("2000 Stainless Steel", "Lamy", "2000", "14k Gold", "M",
         "piston", 550, False, "Standard", "Brushed steel variant"),
        ("Dialog 3 Piano Black", "Lamy", "Dialog", "14k Gold", "M",
         "converter", 380, False, "Standard", "Twist-retractable nib"),
        ("Safari Dark Lilac", "Lamy", "Safari", "Steel", "F",
         "converter", 80, True, "Limited Edition", "2016 special edition"),
        ("Safari Mango", "Lamy", "Safari", "Steel", "M",
         "converter", 65, True, "Limited Edition", "Annual limited color"),
        ("Safari Petrol", "Lamy", "Safari", "Steel", "F",
         "converter", 90, True, "Limited Edition", "2017 special edition, sought after"),
        ("Studio LX All Black", "Lamy", "Studio", "Steel", "M",
         "converter", 120, False, "Standard", "Matte black propeller clip"),
        ("Al-Star Bronze", "Lamy", "Al-Star", "Steel", "M",
         "converter", 45, True, "Limited Edition", "2019 limited colorway"),
        ("Aion Black", "Lamy", "Aion", "Steel", "M",
         "converter", 75, False, "Standard", "Seamless aluminum barrel"),
    ]


def _visconti_pens() -> list[tuple]:
    """6+ Visconti fountain pens — Homo Sapiens, Opera Master, Wall Street."""
    return [
        ("Homo Sapiens Bronze Age", "Visconti", "Homo Sapiens", "Palladium", "M",
         "vacuum", 750, False, "Standard", "Basaltic lava barrel, power-fill"),
        ("Homo Sapiens Dark Age", "Visconti", "Homo Sapiens", "Palladium", "B",
         "vacuum", 800, False, "Standard", "Matte black lava, dreamtouch nib"),
        ("Homo Sapiens Crystal Dream", "Visconti", "Homo Sapiens", "Palladium", "M",
         "vacuum", 900, True, "Limited Edition", "Clear demonstrator edition"),
        ("Opera Master Typhoon", "Visconti", "Opera Master", "18k Gold", "M",
         "vacuum", 1200, True, "Limited Edition", "Swirling celluloid"),
        ("Opera Master Rainforest", "Visconti", "Opera Master", "18k Gold", "M",
         "vacuum", 1100, True, "Limited Edition", "Green celluloid"),
        ("Wall Street Celluloid", "Visconti", "Wall Street", "Palladium", "F",
         "vacuum", 550, False, "Standard", "Pinstriped celluloid barrel"),
        ("Rembrandt Black", "Visconti", "Rembrandt", "Steel", "M",
         "converter", 200, False, "Standard", "Entry-level Visconti"),
    ]


def _aurora_pens() -> list[tuple]:
    """5+ Aurora fountain pens — 88, Optima, limited editions."""
    return [
        ("88 Black Mamba", "Aurora", "88", "18k Gold", "M",
         "piston", 600, False, "Standard", "Classic Italian design"),
        ("88 Saturno", "Aurora", "88", "18k Gold", "M",
         "piston", 700, True, "Limited Edition", "Limited blue marbled resin"),
        ("Optima Blue", "Aurora", "Optima", "18k Gold", "F",
         "piston", 550, False, "Standard", "Auroloide resin, flexible nib"),
        ("Optima 365 Coral", "Aurora", "Optima", "18k Gold", "M",
         "piston", 650, True, "Limited Edition", "365-piece annual edition"),
        ("Internazionale Black", "Aurora", "Internazionale", "18k Gold", "M",
         "piston", 500, False, "Standard", "Oversize piston filler"),
        ("Talentum Finesse Black", "Aurora", "Talentum", "14k Gold", "M",
         "converter", 280, False, "Standard", "Mid-range Italian pen"),
    ]


def _nakaya_pens() -> list[tuple]:
    """5+ Nakaya fountain pens — Dorsal Fin, Piccolo, Cigar, urushi."""
    return [
        ("Dorsal Fin Version 2 Aka-Tamenuri", "Nakaya", "Dorsal Fin", "14k Gold", "M",
         "converter", 1200, False, "Standard", "Hand-turned ebonite, urushi finish"),
        ("Dorsal Fin Version 2 Kuro-Tamenuri", "Nakaya", "Dorsal Fin", "14k Gold", "F",
         "converter", 1200, False, "Standard", "Black tamenuri urushi"),
        ("Piccolo Long Cigar Shu", "Nakaya", "Piccolo", "14k Gold", "M",
         "converter", 800, False, "Standard", "Vermillion urushi, compact size"),
        ("Cigar Long Midori-Tamenuri", "Nakaya", "Cigar", "14k Gold", "B",
         "converter", 1000, False, "Standard", "Green tamenuri finish"),
        ("Decapod Twist Aka-Tamenuri", "Nakaya", "Decapod", "14k Gold", "M",
         "converter", 1500, False, "Standard", "Twisted faceted barrel"),
        ("Portable Writer Kuro-Roiro", "Nakaya", "Portable", "14k Gold", "F",
         "converter", 900, False, "Standard", "Deep black roiro urushi"),
    ]


def _vintage_pens() -> list[tuple]:
    """8+ vintage fountain pens — Parker, Sheaffer, Waterman, Conklin."""
    return [
        ("Parker 51 Aerometric Navy", "Parker", "51", "14k Gold", "F",
         "aerometric", 250, False, "Exclusive", "1950s icon, hooded nib"),
        ("Parker 51 Vacumatic Burgundy", "Parker", "51", "14k Gold", "M",
         "vacuum", 400, False, "Exclusive", "Early vacumatic fill, celluloid"),
        ("Parker Duofold Centennial Black", "Parker", "Duofold", "18k Gold", "M",
         "converter", 500, False, "Standard", "Modern reissue of classic"),
        ("Sheaffer Snorkel Valiant Green", "Sheaffer", "Snorkel", "14k Gold", "F",
         "snorkel", 350, False, "Exclusive", "1950s pneumatic snorkel fill"),
        ("Sheaffer PFM III Black", "Sheaffer", "PFM", "14k Gold (Flex)", "M",
         "snorkel", 500, False, "Exclusive", "Pen for Men, inlaid nib"),
        ("Waterman 52 Red Ripple", "Waterman", "52", "14k Gold (Flex)", "F",
         "eyedropper", 800, False, "Exclusive", "1920s hard rubber, flex nib"),
        ("Waterman 52V Red Ripple", "Waterman", "52V", "14k Gold (Flex)", "F",
         "eyedropper", 650, False, "Exclusive", "Vest-pocket size, flex nib"),
        ("Conklin Crescent Filler Mark Twain", "Conklin", "Crescent", "Steel", "M",
         "crescent", 150, False, "Standard", "Modern reissue of crescent fill"),
        ("Parker Vacumatic Major Blue Diamond", "Parker", "Vacumatic", "14k Gold", "M",
         "vacuum", 350, False, "Exclusive", "1940s laminated celluloid"),
    ]


def _japanese_artisan_pens() -> list[tuple]:
    """5+ Japanese artisan / maki-e art pens."""
    return [
        ("Namiki Emperor Chinkin Autumn Leaf", "Namiki", "Emperor", "18k Gold", "M",
         "converter", 10000, True, "Limited Edition", "Large maki-e, chinkin technique"),
        ("Namiki Emperor Dragon", "Namiki", "Emperor", "18k Gold", "B",
         "converter", 8500, True, "Limited Edition", "Taka maki-e dragon motif"),
        ("Platinum Izumo Tamenuri", "Platinum", "Izumo", "18k Gold", "M",
         "converter", 1500, False, "Standard", "Yakumo-nuri lacquer, large pen"),
        ("Platinum Izumo Maki-e Pine", "Platinum", "Izumo", "18k Gold", "M",
         "converter", 3500, True, "Limited Edition", "Togidashi maki-e artwork"),
        ("Namiki Yukari Royale Peacock", "Namiki", "Yukari Royale", "18k Gold", "M",
         "converter", 4500, True, "Limited Edition", "Hira maki-e peacock, raden inlay"),
        ("Pilot Custom Urushi Maki-e Crane", "Pilot", "Custom Urushi", "18k Gold", "M",
         "converter", 5000, True, "Limited Edition", "Tsugaru lacquer, crane motif"),
    ]


# ---------------------------------------------------------------------------
# Assemble full catalog
# ---------------------------------------------------------------------------


def get_curated_catalog() -> list[dict]:
    """Return the full curated fountain pen catalog as a list of dicts.

    Each dict has keys: name, brand, model_line, nib_material, nib_size,
    filling_system, price_eur, is_limited, rarity, notes.
    """
    all_tuples: list[tuple] = []
    all_tuples.extend(_montblanc_pens())
    all_tuples.extend(_pelikan_pens())
    all_tuples.extend(_sailor_pens())
    all_tuples.extend(_pilot_pens())
    all_tuples.extend(_lamy_pens())
    all_tuples.extend(_visconti_pens())
    all_tuples.extend(_aurora_pens())
    all_tuples.extend(_nakaya_pens())
    all_tuples.extend(_vintage_pens())
    all_tuples.extend(_japanese_artisan_pens())

    catalog: list[dict] = []
    for (name, brand, model_line, nib_material, nib_size,
         filling_system, price_eur, is_limited, rarity, notes) in all_tuples:
        catalog.append({
            "name": name,
            "brand": brand,
            "model_line": model_line,
            "nib_material": nib_material,
            "nib_size": nib_size,
            "filling_system": filling_system,
            "price_eur": price_eur,
            "is_limited": is_limited,
            "rarity": rarity,
            "notes": notes,
        })
    return catalog


# ---------------------------------------------------------------------------
# Transform helpers
# ---------------------------------------------------------------------------


def item_to_catalog_item(item: dict) -> CatalogItem:
    """Convert a pen dict to a CatalogItem.

    Sets category='pens', item_key from slugify(brand-model_line-name),
    brand from the pen brand.
    """
    brand = item["brand"]
    name = item["name"]
    model_line = item["model_line"]
    nib_material = item["nib_material"]
    nib_size = item["nib_size"]
    filling_system = item["filling_system"]
    is_limited = item["is_limited"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{brand}-{model_line}-{name}"),
        title=f"{brand} {name}",
        set_code=model_line,
        brand=brand,
        rarity=item["rarity"],
        notes=f"{brand} | {model_line} | {nib_material} {nib_size} | {filling_system} | {item['notes']}",
        attributes_json={
            "brand": brand,
            "model_line": model_line,
            "nib_material": nib_material,
            "nib_size": nib_size,
            "filling_system": filling_system,
            "is_limited": is_limited,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    """Convert a pen dict to a PriceObservation.

    Features:
    - condition_score: 0.85 (assumes excellent for catalog baseline)
    - rarity_score: from shared_rarity_score()
    - brand_tier: 1.0 Montblanc/Nakaya, 0.9 Pelikan/Sailor, 0.8 Pilot/Aurora/Visconti, 0.6 Lamy
    - nib_material: 1.0 gold/palladium, 0.7 steel, 0.5 ruthenium
    - is_limited: 1.0 or 0.0
    """
    brand = item["brand"]
    rarity = item["rarity"]
    nib_material = item["nib_material"]
    is_limited = item["is_limited"]

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(rarity),
            "brand_tier": _brand_tier(brand),
            "nib_material": _nib_material_score(nib_material),
            "is_limited": 1.0 if is_limited else 0.0,
        },
        price=item["price_eur"],
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Import curated fountain pen catalog + prices"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Write local files only, skip Supabase upsert")
    args = parser.parse_args()

    logger.info("=== Fountain Pen Import Pipeline ===")

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    catalog = get_curated_catalog()
    logger.info(f"  Curated catalog: {len(catalog)} fountain pens")

    all_items = [item_to_catalog_item(p) for p in catalog]
    all_observations = [item_to_price_observation(p) for p in catalog]

    # Write catalog SQL
    write_catalog_sql(CATEGORY, all_items)
    log_progress(CATEGORY, "catalog SQL written", len(all_items))

    # Write training JSONL
    write_training_jsonl(CATEGORY, all_observations)
    log_progress(CATEGORY, "training JSONL written", len(all_observations))

    # Upsert to Supabase if enabled
    if ingest.enabled:
        inserted = ingest.upsert_catalog(all_items)
        log_progress(CATEGORY, "catalog upserted", inserted)

    ingest.close()
    close_http_client()

    logger.info(f"\n=== Fountain Pen Import Complete ===")
    logger.info(f"  Total catalog items:  {len(all_items)}")
    logger.info(f"  Price observations:   {len(all_observations)}")
    if args.dry_run:
        logger.info("  Mode: DRY RUN (local files only)")


if __name__ == "__main__":
    main()
