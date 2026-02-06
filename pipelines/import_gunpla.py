"""
Import Gunpla (Gundam plastic model kit) catalog.

Layer 1 (Catalog):  Curated Gunpla kits → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Perfect Grade (PG) 1/60 scale
- Master Grade (MG) 1/100 scale
- Real Grade (RG) 1/144 scale
- High Grade (HG) 1/144 scale
- P-Bandai web exclusives
- Ver.Ka editions by Katoki Hajime

Usage:
    python -m pipelines.import_gunpla [--dry-run]
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
)

CATEGORY = "gunpla"


def get_curated_catalog() -> list[dict]:
    """Curated Gunpla catalog covering key grades and popular mobile suits."""

    # (grade, scale, name, series, variant, rarity_tier, price_eur)
    # rarity_tier: grail (>200), high (100-200), mid (40-100), standard (<40)

    kits = [
        # Perfect Grade (PG) 1/60
        ("PG", "1/60", "RX-78-2 Gundam", "Mobile Suit Gundam", "", "high", 180),
        ("PG", "1/60", "Unicorn Gundam", "Gundam Unicorn", "", "grail", 320),
        ("PG", "1/60", "Strike Freedom Gundam", "Gundam SEED Destiny", "", "grail", 280),
        ("PG", "1/60", "Gundam Exia", "Gundam 00", "", "high", 200),
        ("PG", "1/60", "Zaku II (Char Custom)", "Mobile Suit Gundam", "", "high", 180),
        ("PG", "1/60", "Banshee Norn", "Gundam Unicorn", "", "grail", 350),
        ("PG", "1/60", "Wing Gundam Zero Custom", "Gundam Wing", "", "grail", 250),
        ("PG", "1/60", "Unleashed RX-78-2", "Mobile Suit Gundam", "Unleashed", "grail", 380),

        # Master Grade (MG) 1/100
        ("MG", "1/100", "Freedom Gundam Ver.2.0", "Gundam SEED", "", "mid", 55),
        ("MG", "1/100", "RX-78-2 Gundam Ver.3.0", "Mobile Suit Gundam", "", "mid", 50),
        ("MG", "1/100", "Sazabi Ver.Ka", "Char's Counterattack", "Ver.Ka", "mid", 85),
        ("MG", "1/100", "Nu Gundam Ver.Ka", "Char's Counterattack", "Ver.Ka", "mid", 75),
        ("MG", "1/100", "Wing Gundam Zero EW Ver.Ka", "Gundam Wing", "Ver.Ka", "mid", 60),
        ("MG", "1/100", "Sinanju Ver.Ka", "Gundam Unicorn", "Ver.Ka", "mid", 80),
        ("MG", "1/100", "Hi-Nu Gundam Ver.Ka", "Char's Counterattack", "Ver.Ka", "high", 110),
        ("MG", "1/100", "Unicorn Gundam Ver.Ka", "Gundam Unicorn", "Ver.Ka", "mid", 65),
        ("MG", "1/100", "Barbatos", "Iron-Blooded Orphans", "", "mid", 50),
        ("MG", "1/100", "Deathscythe Hell EW", "Gundam Wing", "", "mid", 55),
        ("MG", "1/100", "Full Armor Unicorn Ver.Ka", "Gundam Unicorn", "Ver.Ka", "high", 120),
        ("MG", "1/100", "Zaku II Ver.2.0", "Mobile Suit Gundam", "", "mid", 45),
        ("MG", "1/100", "Epyon EW", "Gundam Wing", "", "mid", 55),
        ("MG", "1/100", "Eclipse Gundam", "Gundam SEED Eclipse", "", "mid", 60),

        # Real Grade (RG) 1/144
        ("RG", "1/144", "Hi-Nu Gundam", "Char's Counterattack", "", "mid", 48),
        ("RG", "1/144", "Sazabi", "Char's Counterattack", "", "mid", 45),
        ("RG", "1/144", "Wing Gundam Zero EW", "Gundam Wing", "", "standard", 30),
        ("RG", "1/144", "Unicorn Gundam", "Gundam Unicorn", "", "standard", 32),
        ("RG", "1/144", "Nu Gundam", "Char's Counterattack", "", "mid", 42),
        ("RG", "1/144", "God Gundam", "G Gundam", "", "mid", 40),
        ("RG", "1/144", "Force Impulse Gundam", "Gundam SEED Destiny", "", "standard", 28),
        ("RG", "1/144", "Evangelion Unit-01", "Evangelion", "", "mid", 50),
        ("RG", "1/144", "Strike Freedom Gundam", "Gundam SEED Destiny", "", "standard", 35),

        # P-Bandai Exclusives
        ("MG", "1/100", "Altron Gundam EW (P-Bandai)", "Gundam Wing", "P-Bandai", "high", 120),
        ("MG", "1/100", "Crossbone Gundam X-2 Ver.Ka (P-Bandai)", "Crossbone Gundam", "P-Bandai Ver.Ka", "high", 130),
        ("RG", "1/144", "Tallgeese III (P-Bandai)", "Gundam Wing", "P-Bandai", "high", 65),
        ("MG", "1/100", "Hazel Custom (P-Bandai)", "Advance of Zeta", "P-Bandai", "high", 110),
        ("PG", "1/60", "Unicorn Gundam Perfectibility (P-Bandai)", "Gundam Unicorn", "P-Bandai", "grail", 450),
        ("MG", "1/100", "Providence Gundam (P-Bandai)", "Gundam SEED", "P-Bandai", "high", 100),
        ("HG", "1/144", "Penelope (P-Bandai)", "Hathaway's Flash", "P-Bandai", "mid", 80),
        ("RG", "1/144", "Banshee Norn Final Battle (P-Bandai)", "Gundam Unicorn", "P-Bandai", "mid", 70),

        # High Grade (HG) 1/144
        ("HG", "1/144", "RX-78-2 Gundam (Revive)", "Mobile Suit Gundam", "", "standard", 14),
        ("HG", "1/144", "Barbatos Lupus Rex", "Iron-Blooded Orphans", "", "standard", 16),
        ("HG", "1/144", "Aerial", "Gundam: Witch from Mercury", "", "standard", 15),
        ("HG", "1/144", "Calibarn", "Gundam: Witch from Mercury", "", "standard", 18),
        ("HG", "1/144", "Schwarzette", "Gundam: Witch from Mercury", "", "standard", 20),
        ("HG", "1/144", "Moon Gundam", "Moon Gundam", "", "standard", 30),
        ("HG", "1/144", "Infinite Justice Gundam Type II", "Gundam SEED Freedom", "", "standard", 22),
        ("HG", "1/144", "Mighty Strike Freedom", "Gundam SEED Freedom", "", "standard", 28),
    ]

    catalog = []
    for grade, scale, name, series, variant, tier, price in kits:
        catalog.append({
            "grade": grade,
            "scale": scale,
            "name": name,
            "series": series,
            "variant": variant,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    grade = item["grade"]
    name = item["name"]
    series = item["series"]
    variant = item["variant"]
    scale = item["scale"]

    title_parts = [grade, name]
    if variant:
        title_parts.append(f"({variant})")

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{grade}-{name}" + (f"-{variant}" if variant else "")),
        title=" ".join(title_parts),
        set_code=slugify(series),
        brand="Bandai",
        rarity=item["rarity_tier"].title(),
        notes=f"{grade} {scale} | {series}" + (f" | {variant}" if variant else ""),
        attributes_json={
            "grade": grade,
            "scale": scale,
            "series": series,
            "variant": variant,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]
    rarity_map = {"grail": 0.95, "high": 0.8, "mid": 0.6, "standard": 0.2}

    variant = item["variant"]
    is_p_bandai = "P-Bandai" in variant if variant else False
    is_ver_ka = "Ver.Ka" in variant if variant else False

    grade = item["grade"]
    grade_scores = {
        "PG": 0.85,
        "MG": 0.5,
        "RG": 0.4,
        "HG": 0.2,
    }

    edition_score = grade_scores.get(grade, 0.4)
    if is_p_bandai:
        edition_score = min(1.0, edition_score + 0.3)
    if is_ver_ka:
        edition_score = min(1.0, edition_score + 0.15)

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": rarity_map.get(tier, 0.5),
            "edition_score": edition_score,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Gunpla catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=== Gunpla Import ===")

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

    print(f"\n=== Gunpla Import Complete ===")
    print(f"  Catalog items:      {len(all_items)}")
    print(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
