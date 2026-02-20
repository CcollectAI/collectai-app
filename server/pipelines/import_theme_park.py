"""
Import theme park exclusives catalog.

Layer 1 (Catalog):  Curated park-only merch & resale collectibles → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated data from secondary market (eBay, Mercari, Yahoo Auctions JP)
- Covers Disney Parks popcorn buckets, Tokyo Disney, Universal Studios Japan,
  pin events, park-exclusive Funko Pops, grand opening merch

Usage:
    python -m pipelines.import_theme_park [--dry-run]
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

CATEGORY = "theme_park"


def get_curated_catalog() -> list[dict]:
    """Curated theme park exclusives catalog (66 items)."""

    # (park, subcategory, name, edition, rarity_tier, price_eur)
    # rarity_tier: grail (>150), high (60-150), mid (25-60), standard (<25)

    items = [
        # Disney Parks Popcorn Buckets
        ("Disney Parks", "popcorn_bucket", "Figment Popcorn Bucket (Epcot)", "Limited Release", "high", 120),
        ("Disney Parks", "popcorn_bucket", "Purple Wall Popcorn Bucket", "Park Exclusive", "high", 80),
        ("Disney Parks", "popcorn_bucket", "Mickey Balloon Popcorn Bucket", "Park Exclusive", "mid", 55),
        ("Disney Parks", "popcorn_bucket", "R2-D2 Popcorn Bucket (Galaxy's Edge)", "Park Exclusive", "mid", 45),
        ("Disney Parks", "popcorn_bucket", "Cinderella Carriage Popcorn Bucket (TDL)", "Tokyo Exclusive", "high", 90),
        ("Disney Parks", "popcorn_bucket", "Slinky Dog Popcorn Bucket", "Park Exclusive", "mid", 40),
        ("Disney Parks", "popcorn_bucket", "Haunted Mansion Doom Buggy Popcorn Bucket", "LE", "grail", 150),

        # Tokyo Disney Exclusives
        ("Tokyo Disney", "snack_case", "Duffy Snack Case (TDS)", "Tokyo Exclusive", "mid", 45),
        ("Tokyo Disney", "snack_case", "StellaLou Candy Case", "Tokyo Exclusive", "mid", 40),
        ("Tokyo Disney", "plush", "Duffy 20th Anniversary Plush Set", "Anniversary LE", "high", 130),
        ("Tokyo Disney", "plush", "LinaBell Plush (TDS Exclusive)", "Tokyo Exclusive", "high", 85),
        ("Tokyo Disney", "plush", "Olu Mel Plush (Hawaii Exclusive)", "Park Exclusive", "high", 70),
        ("Tokyo Disney", "pins", "Tokyo Disney 40th Anniversary Pin Set", "Anniversary LE", "high", 95),
        ("Tokyo Disney", "merch", "Fantasy Springs Grand Opening Tee", "Grand Opening", "high", 65),
        ("Tokyo Disney", "merch", "TDL 40th Anniversary Popcorn Tin", "Anniversary LE", "mid", 50),

        # Universal Studios Japan
        ("USJ", "merch", "Super Nintendo World Grand Opening Set", "Grand Opening", "grail", 180),
        ("USJ", "merch", "Mario Power-Up Band (Gold Star)", "Park Exclusive", "mid", 35),
        ("USJ", "merch", "Mario Kart Popcorn Bucket", "Park Exclusive", "mid", 55),
        ("USJ", "merch", "USJ Jujutsu Kaisen Collab Tee", "Collab Exclusive", "mid", 40),
        ("USJ", "merch", "Donkey Kong Country Grand Opening Set", "Grand Opening", "high", 140),
        ("USJ", "figure", "USJ Exclusive Mewtwo Figure", "Park Exclusive", "high", 65),
        ("USJ", "figure", "Nintendo World Pikmin Exclusive Figure Set", "Park Exclusive", "mid", 50),

        # Disney Pin Events
        ("Disney Parks", "pin_event", "Disney Pin Trading Night LE 300", "LE 300", "grail", 180),
        ("Disney Parks", "pin_event", "EPCOT Festival Pin Board Complete Set", "Festival LE", "high", 100),
        ("Disney Parks", "pin_event", "Disneyland AP Exclusive Pin Set (2024)", "AP Exclusive", "high", 70),

        # Park-Exclusive Funko Pops
        ("Disney Parks", "funko", "Funko Pop Haunted Mansion Hitchhiking Ghosts", "Park Exclusive", "high", 85),
        ("Disney Parks", "funko", "Funko Pop Orange Bird (Disney Parks)", "Park Exclusive", "high", 65),
        ("Disney Parks", "funko", "Funko Pop Figment (Epcot)", "Park Exclusive", "mid", 45),
        ("USJ", "funko", "Funko Pop Mario (USJ Exclusive)", "Park Exclusive", "high", 75),

        # Grand Opening / Anniversary
        ("Disney Parks", "anniversary", "Walt Disney World 50th Anniversary Spirit Jersey", "Anniversary LE", "high", 90),
        ("Disney Parks", "anniversary", "Disneyland 70th Anniversary Poster Set", "Anniversary LE", "high", 80),
        ("Disney Parks", "anniversary", "EPCOT 40th Anniversary Figment Figure", "Anniversary LE", "high", 95),
        ("Disney Parks", "anniversary", "Disney100 Platinum Celebration Pin", "D100 Exclusive", "mid", 45),
        ("USJ", "anniversary", "USJ 20th Anniversary Exclusive Pin Set", "Anniversary LE", "high", 70),

        # --- Additional Disney Parks Popcorn Buckets ---
        ("Disney Parks", "popcorn_bucket", "Dumbo Popcorn Bucket (Magic Kingdom)", "Park Exclusive", "high", 75),
        ("Disney Parks", "popcorn_bucket", "Little Mermaid Shell Popcorn Bucket", "Park Exclusive", "mid", 50),
        ("Disney Parks", "popcorn_bucket", "Ratatouille Remy Popcorn Bucket (Epcot)", "Park Exclusive", "high", 65),
        ("Disney Parks", "popcorn_bucket", "Nightmare Before Christmas Popcorn Bucket", "Limited Release", "high", 110),

        # --- Universal Studios (expanded) ---
        ("USJ", "popcorn_bucket", "USJ Jaws Popcorn Bucket", "Park Exclusive", "high", 70),
        ("USJ", "merch", "Super Nintendo World Power Star Popcorn Tin", "Park Exclusive", "mid", 45),
        ("Universal Orlando", "merch", "Wizarding World Butterbeer Stein Mug", "Park Exclusive", "mid", 35),
        ("Universal Orlando", "merch", "Jurassic World Raptor Popcorn Bucket", "Park Exclusive", "mid", 40),
        ("Universal Orlando", "merch", "Halloween Horror Nights 2024 Exclusive Tee", "Limited Release", "high", 60),
        ("Universal Orlando", "merch", "VelociCoaster Grand Opening Pin Set", "Grand Opening", "high", 85),

        # --- Tokyo DisneySea (expanded) ---
        ("Tokyo Disney", "plush", "Duffy Exclusive Plush (TDS 2024)", "Tokyo Exclusive", "high", 95),
        ("Tokyo Disney", "plush", "ShellieMay Plush (TDS Exclusive)", "Tokyo Exclusive", "high", 80),
        ("Tokyo Disney", "plush", "Gelatoni Plush (TDS Exclusive)", "Tokyo Exclusive", "high", 75),
        ("Tokyo Disney", "plush", "StellaLou Plush (TDS Exclusive)", "Tokyo Exclusive", "high", 80),
        ("Tokyo Disney", "merch", "Tokyo DisneySea 20th Anniversary Exclusive Set", "Anniversary LE", "grail", 160),

        # --- Shanghai Disneyland ---
        ("Shanghai Disney", "merch", "Shanghai Disneyland Grand Opening Pin Set (2016)", "Grand Opening", "grail", 200),
        ("Shanghai Disney", "merch", "Zootopia Land Grand Opening Exclusive Set", "Grand Opening", "high", 110),
        ("Shanghai Disney", "merch", "Chinese New Year Exclusive Mickey Plush", "Limited Release", "high", 65),

        # --- Disney Pin Events (expanded) ---
        ("Disney Parks", "pin_event", "Epcot International Food & Wine Festival Pin Set", "Festival LE", "high", 85),
        ("Disney Parks", "pin_event", "Mickey's Not-So-Scary Halloween Party Pin Set", "LE", "high", 95),
        ("Disney Parks", "pin_event", "Disney After Hours BOO Bash Event Pin", "LE", "high", 75),
        ("Disney Parks", "pin_event", "runDisney Marathon Weekend Medal Set", "Limited Release", "high", 110),

        # --- Vintage Park Collectibles ---
        ("Disney Parks", "vintage", "Vintage Disneyland Ticket Book (A-E Tickets)", "Vintage", "grail", 350),
        ("Disney Parks", "vintage", "1971 Walt Disney World Opening Day Guide Map", "Vintage", "grail", 280),
        ("Disney Parks", "vintage", "Vintage Disney Park Souvenir Glass Set (1970s)", "Vintage", "high", 90),
        ("Disney Parks", "vintage", "Disney on Ice Program Booklet (1980s)", "Vintage", "mid", 30),
        ("Disney Parks", "vintage", "Disneyland Hotel Vintage Ashtray (1960s)", "Vintage", "high", 120),

        # --- Grand Opening / Anniversary (expanded) ---
        ("Disney Parks", "anniversary", "Star Wars Galaxy's Edge Grand Opening Pin Set", "Grand Opening", "high", 130),
        ("Disney Parks", "anniversary", "Pandora World of Avatar Grand Opening Banshee Figure", "Grand Opening", "high", 100),
        ("Disney Parks", "anniversary", "Tron Lightcycle Run Grand Opening Tee", "Grand Opening", "high", 70),
        ("Disney Parks", "anniversary", "Guardians Cosmic Rewind Grand Opening Pin", "Grand Opening", "high", 65),
        ("Disney Parks", "anniversary", "Disney100 Celebration Exclusive Collectible Set", "D100 Exclusive", "grail", 175),
    ]

    catalog = []
    for park, subcategory, name, edition, tier, price in items:
        catalog.append({
            "park": park,
            "subcategory": subcategory,
            "name": name,
            "edition": edition,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    park = item["park"]
    name = item["name"]
    edition = item["edition"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{park}-{name}"),
        title=name,
        set_code=slugify(park),
        brand=park,
        rarity=item["rarity_tier"].title(),
        notes=f"{park} | {item['subcategory']} | {edition}",
        attributes_json={
            "park": park,
            "subcategory": item["subcategory"],
            "edition": edition,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    edition = item["edition"]
    edition_map = {
        "LE 300": 0.95, "LE": 0.85, "Grand Opening": 0.85,
        "Anniversary LE": 0.8, "D100 Exclusive": 0.75,
        "Festival LE": 0.75, "AP Exclusive": 0.7,
        "Tokyo Exclusive": 0.7, "Collab Exclusive": 0.6,
        "Park Exclusive": 0.6, "Limited Release": 0.65,
        "Standard": 0.2,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_map.get(edition, 0.4),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import theme park exclusives catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Theme Park Exclusives Import ===")

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

    logger.info(f"\n=== Theme Park Exclusives Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
