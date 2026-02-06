"""
Import Japanese magazine exclusives catalog.

Layer 1 (Catalog):  Curated JP magazine inserts & exclusives → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Dengeki G's Magazine (Love Live, idol game inserts)
- Newtype magazine (anime posters, production art)
- Famitsu (game codes, mini figures)
- Animedia / Animage (classic anime inserts)
- Limited clear files, shikishi boards, acrylic stands
- Vintage 80s/90s anime magazine inserts

Usage:
    python -m pipelines.import_jp_magazine [--dry-run]
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

CATEGORY = "jp_magazine"


def get_curated_catalog() -> list[dict]:
    """Curated Japanese magazine exclusives catalog."""

    # (magazine, franchise, item_type, name, era, rarity_tier, price_eur)
    # rarity_tier: grail (>100), high (50-100), mid (15-50), standard (<15)

    items = [
        # Dengeki G's Magazine – Love Live / idol inserts
        ("Dengeki G's Magazine", "Love Live!", "Insert Poster", "Love Live! Muse Final Live A2 Poster Insert", "2010s", "mid", 25),
        ("Dengeki G's Magazine", "Love Live! Sunshine!!", "Insert Poster", "Aqours 2nd Live A2 Poster Insert", "2010s", "mid", 20),
        ("Dengeki G's Magazine", "Love Live!", "Clear File", "Muse Valentine Clear File Set", "2010s", "mid", 18),
        ("Dengeki G's Magazine", "Love Live! Superstar!!", "Acrylic Stand", "Liella! 1st Anniversary Acrylic Stand", "2020s", "mid", 22),
        ("Dengeki G's Magazine", "The Idolmaster", "Insert Card", "iM@S Shiny Colors Insert Bromide Set", "2020s", "standard", 12),
        ("Dengeki G's Magazine", "Love Live!", "Shikishi Board", "Muse 9th Anniversary Shikishi Board", "2010s", "mid", 30),

        # Newtype magazine – anime posters & production art
        ("Newtype", "Evangelion", "B2 Poster", "Evangelion 3.0+1.0 Key Visual B2 Poster", "2020s", "mid", 28),
        ("Newtype", "Fate/stay night", "B2 Poster", "Fate/stay night HF III Key Art Poster", "2020s", "mid", 22),
        ("Newtype", "Gundam: Witch from Mercury", "Clear File", "Suletta Mercury Clear File Insert", "2020s", "standard", 8),
        ("Newtype", "Code Geass", "Insert Poster", "Code Geass 15th Anniversary A3 Insert", "2020s", "mid", 18),
        ("Newtype", "Mobile Suit Gundam", "Production Art", "Original Gundam Production Settei Reprint", "2010s", "mid", 35),

        # Famitsu – game codes & mini figures
        ("Famitsu", "Final Fantasy VII Remake", "DLC Code", "FF7R Exclusive Weapon DLC Code Card", "2020s", "standard", 10),
        ("Famitsu", "Persona 5", "Clear File", "Persona 5 Royal Clear File Insert", "2010s", "standard", 12),
        ("Famitsu", "Monster Hunter", "Mini Figure", "Monster Hunter Rise Palamute Mini Figure", "2020s", "mid", 18),
        ("Famitsu", "Dragon Quest", "Insert Poster", "Dragon Quest XII Reveal A3 Poster", "2020s", "standard", 8),
        ("Famitsu", "Xenoblade Chronicles 3", "Acrylic Stand", "Xenoblade 3 Mio Acrylic Stand Insert", "2020s", "mid", 15),

        # Animedia / Animage – classic anime inserts
        ("Animage", "Nausicaa", "B3 Poster", "Nausicaa Theatrical Release Poster Reprint", "1980s", "high", 80),
        ("Animage", "Castle in the Sky", "Insert Poster", "Laputa Original Insert Poster 1986", "1980s", "grail", 150),
        ("Animedia", "Dragon Ball Z", "Pin-up Poster", "DBZ Cell Saga A3 Pin-up Set (3 sheets)", "1990s", "mid", 35),
        ("Animedia", "Sailor Moon", "Insert Poster", "Sailor Moon S Character Poster Insert", "1990s", "mid", 40),
        ("Animage", "Mobile Suit Gundam", "Settei Sheet", "Gundam 0083 Settei Sheet Insert", "1990s", "mid", 30),

        # Limited clear files, shikishi boards, acrylic stands
        ("Various", "Demon Slayer", "Clear File", "Demon Slayer Magazine Exclusive Clear File 5-Set", "2020s", "mid", 20),
        ("Various", "Spy x Family", "Shikishi Board", "Spy x Family Anime Festa Shikishi Board", "2020s", "standard", 12),
        ("Various", "Chainsaw Man", "Clear File", "Chainsaw Man Newtype x Animedia Clear File Pair", "2020s", "standard", 10),
        ("Various", "My Hero Academia", "Acrylic Stand", "MHA Magazine Insert Acrylic Stand Deku", "2020s", "standard", 12),

        # Vintage 80s/90s anime magazine inserts
        ("Animage", "Macross", "B2 Poster", "Macross DYRL Minmay B2 Poster Insert 1984", "1980s", "grail", 180),
        ("Newtype", "Akira", "Insert Poster", "Akira Theatrical A2 Poster Insert 1988", "1980s", "grail", 200),
        ("Animage", "Saint Seiya", "Pin-up Set", "Saint Seiya Gold Saints Pin-up Set 1988", "1980s", "high", 65),
        ("Newtype", "Ghost in the Shell", "Insert Poster", "Ghost in the Shell Movie A3 Poster 1995", "1990s", "high", 75),
        ("Animedia", "Neon Genesis Evangelion", "Pin-up Poster", "EVA Rei & Asuka Double-Sided A3 Poster", "1990s", "high", 55),
    ]

    catalog = []
    for magazine, franchise, item_type, name, era, tier, price in items:
        catalog.append({
            "magazine": magazine,
            "franchise": franchise,
            "item_type": item_type,
            "name": name,
            "era": era,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    magazine = item["magazine"]
    name = item["name"]
    franchise = item["franchise"]
    item_type = item["item_type"]
    era = item["era"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{magazine}-{name}"),
        title=name,
        set_code=slugify(magazine),
        brand=magazine,
        rarity=item["rarity_tier"].title(),
        notes=f"{magazine} | {franchise} | {item_type} | {era}",
        attributes_json={
            "magazine": magazine,
            "franchise": franchise,
            "item_type": item_type,
            "era": era,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]
    rarity_map = {"grail": 0.95, "high": 0.8, "mid": 0.6, "standard": 0.2}

    era = item["era"]
    edition_scores = {
        "1980s": 0.90,
        "1990s": 0.75,
        "2000s": 0.55,
        "2010s": 0.45,
        "2020s": 0.30,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": rarity_map.get(tier, 0.5),
            "edition_score": edition_scores.get(era, 0.5),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import JP magazine exclusives catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=== JP Magazine Exclusives Import ===")

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

    print(f"\n=== JP Magazine Exclusives Import Complete ===")
    print(f"  Catalog items:      {len(all_items)}")
    print(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
