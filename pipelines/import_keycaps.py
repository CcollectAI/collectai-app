"""
Import Artisan Keycaps & Keycap Sets catalog.

Layer 1 (Catalog):  Curated artisan keycaps + group buy sets → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Artisan makers: Jelly Key, Dwarf Factory, CYSM, Latrialum
- GMK sets: popular group buy colorways (Olivia, Laser, Botanical, etc.)
- Premium one-offs: GAF, ETF, Bro Caps
- SA / KAT profile sets

Usage:
    python -m pipelines.import_keycaps [--dry-run]
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

CATEGORY = "keycaps"


def get_curated_catalog() -> list[dict]:
    """Curated keycap catalog covering artisan makers, GMK sets, and premium caps."""

    # (maker, keycap_type, name, profile, rarity_tier, price_eur)
    # rarity_tier: grail (>400), high (200-400), mid (80-200), standard (<80)

    caps = [
        # Jelly Key
        ("Jelly Key", "Artisan", "Zen Pond III Cherry Blossom", "SA R1", "mid", 85),
        ("Jelly Key", "Artisan", "Zen Pond III Ochiba", "SA R1", "mid", 90),
        ("Jelly Key", "Artisan", "Arcade Cabinet Retro TV", "SA R1", "mid", 95),
        ("Jelly Key", "Artisan", "Born of Forest Series Aspen", "SA R1", "mid", 80),
        ("Jelly Key", "Artisan", "Dragon of Eden Keycap", "SA R1", "mid", 100),
        ("Jelly Key", "Artisan", "Ethereal Reign Trident", "SA R1", "high", 120),

        # Dwarf Factory
        ("Dwarf Factory", "Artisan", "Gnarly Drakon Obsidian", "Cherry R1", "mid", 65),
        ("Dwarf Factory", "Artisan", "Gnarly Drakon Jade", "Cherry R1", "mid", 70),
        ("Dwarf Factory", "Artisan", "The Flourish Sakura", "Cherry R1", "standard", 55),
        ("Dwarf Factory", "Artisan", "Terrarium Keycap Ocean", "Cherry R1", "mid", 75),
        ("Dwarf Factory", "Artisan", "Moondust Nebula", "Cherry R1", "mid", 80),

        # CYSM
        ("CYSM", "Artisan", "Keyby Classic Blue", "Cherry R4", "mid", 90),
        ("CYSM", "Artisan", "Keyby Mermaid", "Cherry R4", "mid", 100),
        ("CYSM", "Artisan", "Boo Ice Cream", "Cherry R4", "mid", 85),
        ("CYSM", "Artisan", "Keyby Aurora", "Cherry R4", "high", 140),

        # Latrialum
        ("Latrialum", "Artisan", "Royal Eternal Flame ESC", "Cherry R4", "high", 180),
        ("Latrialum", "Artisan", "Seraphic Bloom ESC", "Cherry R4", "high", 200),
        ("Latrialum", "Artisan", "Imperial Astral WASD Set", "Cherry R4", "high", 350),
        ("Latrialum", "Artisan", "Frostfire ESC + Fn Set", "Cherry R4", "high", 280),

        # GMK Sets
        ("GMK", "Keycap Set", "GMK Olivia++ Dark Base Kit", "Cherry", "high", 280),
        ("GMK", "Keycap Set", "GMK Olivia++ Light Base Kit", "Cherry", "high", 250),
        ("GMK", "Keycap Set", "GMK Laser Cyberdeck Base", "Cherry", "high", 220),
        ("GMK", "Keycap Set", "GMK Botanical Base Kit", "Cherry", "high", 260),
        ("GMK", "Keycap Set", "GMK Botanical R2 Base Kit", "Cherry", "mid", 180),
        ("GMK", "Keycap Set", "GMK 8008 Base Kit", "Cherry", "high", 300),
        ("GMK", "Keycap Set", "GMK Bento Base Kit", "Cherry", "high", 240),
        ("GMK", "Keycap Set", "GMK Dracula Base Kit", "Cherry", "mid", 200),
        ("GMK", "Keycap Set", "GMK Cafe Base Kit", "Cherry", "mid", 190),
        ("GMK", "Keycap Set", "GMK Mizu Base Kit", "Cherry", "high", 320),
        ("GMK", "Keycap Set", "GMK Oblivion V2 Base Kit", "Cherry", "mid", 180),
        ("GMK", "Keycap Set", "GMK Taro R2 Base Kit", "Cherry", "mid", 160),
        ("GMK", "Keycap Set", "GMK Nautilus R2 Base Kit", "Cherry", "mid", 150),
        ("GMK", "Keycap Set", "GMK Modo Light Base Kit", "Cherry", "mid", 140),

        # Premium One-offs / Grails
        ("GAF (Grimey as Fuck)", "Artisan", "Trash Panda OG Colorway", "Cherry R4", "grail", 800),
        ("GAF (Grimey as Fuck)", "Artisan", "Trash Panda Garnet", "Cherry R4", "grail", 650),
        ("ETF (Nightcaps)", "Artisan", "Fugthulhu Vaporwave III", "Cherry R1", "grail", 500),
        ("ETF (Nightcaps)", "Artisan", "Smegface Galactic Raspberry", "Cherry R1", "grail", 450),
        ("Bro Caps", "Artisan", "Brobot V2 Corrupted Defender", "Cherry R1", "grail", 700),
        ("Bro Caps", "Artisan", "Brobot V2 Patriot", "Cherry R1", "grail", 600),
        ("Bro Caps", "Artisan", "Last Pilot Midnight", "Cherry R1", "high", 400),
        ("Alpha Keycaps", "Artisan", "Salvador Galaxy", "Cherry R1", "high", 250),

        # SA Profile Sets
        ("Signature Plastics", "Keycap Set", "SA Bliss Base Kit", "SA", "mid", 160),
        ("Signature Plastics", "Keycap Set", "SA Dreameater Base Kit", "SA", "mid", 140),
        ("Signature Plastics", "Keycap Set", "SA Godspeed Base Kit", "SA", "mid", 180),
        ("Signature Plastics", "Keycap Set", "SA Mizu Base Kit", "SA", "high", 200),

        # KAT Profile Sets
        ("Keyreative", "Keycap Set", "KAT Milkshake Alpha Kit", "KAT", "mid", 120),
        ("Keyreative", "Keycap Set", "KAT Atlantis Alpha Kit", "KAT", "mid", 100),
        ("Keyreative", "Keycap Set", "KAT Refined Alpha Kit", "KAT", "standard", 80),
        ("Keyreative", "Keycap Set", "KAT Arctic Alpha Kit", "KAT", "mid", 110),
    ]

    catalog = []
    for maker, keycap_type, name, profile, tier, price in caps:
        catalog.append({
            "maker": maker,
            "keycap_type": keycap_type,
            "name": name,
            "profile": profile,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    maker = item["maker"]
    name = item["name"]
    keycap_type = item["keycap_type"]
    profile = item["profile"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{maker}-{name}"),
        title=name,
        set_code=slugify(maker),
        brand=maker,
        rarity=item["rarity_tier"].title(),
        notes=f"{maker} | {keycap_type} | {profile}",
        attributes_json={
            "maker": maker,
            "keycap_type": keycap_type,
            "profile": profile,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]
    rarity_map = {"grail": 0.95, "high": 0.8, "mid": 0.6, "standard": 0.2}

    keycap_type = item["keycap_type"]
    type_edition_scores = {
        "Artisan": 0.8,
        "Keycap Set": 0.5,
    }

    maker = item["maker"]
    premium_makers = {
        "GAF (Grimey as Fuck)", "ETF (Nightcaps)", "Bro Caps",
        "Alpha Keycaps", "Latrialum",
    }
    maker_bonus = 0.2 if maker in premium_makers else 0.0

    edition_score = min(1.0, type_edition_scores.get(keycap_type, 0.5) + maker_bonus)

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": rarity_map.get(tier, 0.5),
            "edition_score": round(edition_score, 2),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Keycaps catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=== Keycaps Import ===")

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

    print(f"\n=== Keycaps Import Complete ===")
    print(f"  Catalog items:      {len(all_items)}")
    print(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
