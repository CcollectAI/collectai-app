"""
Import Funko Pop data.

Layer 1 (Catalog):  Curated high-value Funko Pops → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

No official Funko API exists. Data sourced from:
- Curated grail lists (conventions, vaulted, chase variants)
- HobbyDB / Pop Price Guide structure
- Can be augmented with web scraping later

Usage:
    python -m pipelines.import_funko [--dry-run]
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

CATEGORY = "funko"


def get_curated_catalog() -> list[dict]:
    """Curated Funko Pop catalog covering major lines and grails."""

    # Format: (line, number, name, exclusive, rarity_tier, est_price_eur)
    # rarity_tier: grail (>500), high (100-500), mid (30-100), standard (<30)

    pops = [
        # DC Comics
        ("DC Heroes", "01", "Batman (Metallic Blue)", "SDCC 2010", "grail", 12000),
        ("DC Heroes", "01", "Batman", "", "standard", 15),
        ("DC Heroes", "02", "Superman", "", "standard", 12),
        ("DC Heroes", "06", "Green Lantern (Previews)", "NYCC 2012", "grail", 3500),
        ("DC Heroes", "52", "Batgirl", "", "standard", 10),
        ("DC Heroes", "13", "Harley Quinn", "", "mid", 45),

        # Marvel
        ("Marvel", "01", "Spider-Man", "", "mid", 60),
        ("Marvel", "02", "Iron Man", "", "standard", 20),
        ("Marvel", "03", "Hulk", "", "standard", 18),
        ("Marvel", "04", "Thor", "", "mid", 35),
        ("Marvel", "07", "Captain America", "", "mid", 40),
        ("Marvel", "18", "Red Skull (Metallic)", "SDCC 2011", "grail", 2000),
        ("Marvel", "39", "Loki", "", "mid", 50),
        ("Marvel", "65", "Deadpool", "", "standard", 15),

        # Star Wars
        ("Star Wars", "01", "Darth Vader", "", "mid", 45),
        ("Star Wars", "02", "Yoda", "", "mid", 35),
        ("Star Wars", "03", "Holographic Darth Maul", "Paris Comic Con", "grail", 5000),
        ("Star Wars", "06", "Boba Fett (Droids)", "", "high", 350),
        ("Star Wars", "33", "Boba Fett (Prototype)", "", "high", 300),
        ("Star Wars", "40", "Luke Skywalker (Jedi)", "", "standard", 15),
        ("Star Wars", "130", "Obi-Wan Kenobi", "", "standard", 12),

        # Disney
        ("Disney", "01", "Mickey Mouse", "", "high", 200),
        ("Disney", "07", "Dumbo (Clown)", "", "high", 400),
        ("Disney", "08", "Cheshire Cat", "", "mid", 80),
        ("Disney", "16", "Lotso (Flocked)", "SDCC 2012", "high", 200),
        ("Haunted Mansion", "12", "Hatbox Ghost", "Disney Parks", "grail", 4000),

        # Anime / DragonBall Z
        ("Dragon Ball Z", "10", "Planet Arlia Vegeta", "Toy Tokyo", "grail", 8000),
        ("Dragon Ball Z", "14", "Super Saiyan Goku", "", "mid", 40),
        ("Dragon Ball Z", "47", "Goku (Kamehameha)", "", "standard", 15),
        ("Dragon Ball Z", "120", "Vegeta (Galick Gun)", "Chalice", "mid", 60),
        ("Naruto", "71", "Naruto (Six Path)", "Hot Topic", "mid", 65),
        ("Naruto", "73", "Kakashi (Lightning Blade)", "", "mid", 35),
        ("One Piece", "98", "Monkey D. Luffy", "", "mid", 40),
        ("One Piece", "99", "Trafalgar Law", "", "mid", 50),

        # Game of Thrones
        ("Game of Thrones", "01", "Ned Stark", "", "mid", 60),
        ("Game of Thrones", "02", "Headless Ned Stark", "SDCC 2013", "grail", 2500),
        ("Game of Thrones", "03", "Daenerys Targaryen", "", "mid", 35),
        ("Game of Thrones", "08", "Khal Drogo", "", "mid", 45),
        ("Game of Thrones", "22", "Night King", "", "standard", 20),
        ("Game of Thrones", "44", "Ramsay Bolton", "", "standard", 25),
        ("Game of Thrones", "61", "Cersei Lannister", "", "standard", 15),

        # Horror / Classics
        ("Movies", "01", "Clockwork Orange Alex", "Vaulted", "grail", 3000),
        ("Horror", "03", "Michael Myers (Glow)", "Fugitive", "high", 400),
        ("Horror", "19", "Ghostface", "", "mid", 50),
        ("Ad Icons", "02", "Boo Berry (Metallic)", "SDCC 2012", "grail", 1500),
        ("Ad Icons", "01", "Franken Berry (Metallic)", "SDCC 2012", "grail", 1200),
        ("Ad Icons", "03", "Count Chocula (Metallic)", "SDCC 2012", "grail", 1200),

        # Pokemon
        ("Pokemon", "353", "Pikachu", "", "standard", 12),
        ("Pokemon", "843", "Charizard", "", "standard", 15),
        ("Pokemon", "455", "Mewtwo", "", "standard", 15),
        ("Pokemon", "504", "Eevee", "", "standard", 10),
        ("Pokemon", "780", "Bulbasaur (Diamond)", "Hot Topic", "mid", 30),

        # Television
        ("The Office", "869", "Michael Scott", "", "standard", 12),
        ("The Office", "870", "Dwight Schrute", "", "standard", 12),
        ("Friends", "700", "Monica Geller", "", "standard", 10),
        ("Stranger Things", "421", "Eleven (Underwater)", "Hot Topic", "mid", 35),
        ("Breaking Bad", "158", "Walter White (Heisenberg)", "", "mid", 60),

        # Freddy Funko exclusives
        ("Freddy Funko", "SE", "Freddy Funko (Astronaut)", "Funko HQ", "high", 500),
        ("Freddy Funko", "SE", "Freddy Funko as Pennywise", "Fundays", "grail", 3000),
    ]

    catalog = []
    for line, number, name, exclusive, tier, price in pops:
        catalog.append({
            "line": line,
            "number": number,
            "name": name,
            "exclusive": exclusive,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    line = item["line"]
    number = item["number"]
    name = item["name"]
    exclusive = item["exclusive"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{line}-{number}-{name}"),
        title=f"{name} #{number}",
        set_code=line.lower().replace(" ", "-"),
        brand="Funko Pop",
        rarity=item["rarity_tier"].title(),
        notes=f"{line} #{number}" + (f" | {exclusive}" if exclusive else ""),
        attributes_json={
            "line": line,
            "number": number,
            "exclusive": exclusive,
            "sticker_variant": exclusive if exclusive else "",
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]
    rarity_map = {"grail": 0.95, "high": 0.8, "mid": 0.6, "standard": 0.2}
    exclusive_score = 0.9 if item["exclusive"] else 0.3

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": rarity_map.get(tier, 0.5),
            "edition_score": exclusive_score,
            "is_chase": 0.0,
            "is_exclusive": 1.0 if item["exclusive"] else 0.0,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Funko Pop catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=== Funko Pop Import ===")

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

    print(f"\n=== Funko Import Complete ===")
    print(f"  Catalog items:      {len(all_items)}")
    print(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
