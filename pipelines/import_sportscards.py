"""
Import Sports Cards catalog.

Layer 1 (Catalog):  Iconic cards across sports → category_items
Layer 2 (Prices):   Market estimates → train.jsonl

Sources: Curated database of high-value sports cards.
Can be augmented with eBay API, TCDB.com, 130point.com later.

Usage:
    python -m pipelines.import_sportscards [--dry-run]
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

CATEGORY = "sportscards"


def get_curated_catalog() -> list[dict]:
    """Curated sports cards catalog across major sports."""

    # (sport, year, set_name, player, card_number, variant, raw_price, psa10_price, rarity)
    cards = [
        # Basketball
        ("Basketball", "1986", "Fleer", "Michael Jordan", "57", "Base", 3000, 50000, "Iconic"),
        ("Basketball", "2003", "Topps Chrome", "LeBron James", "111", "Refractor", 5000, 80000, "Iconic"),
        ("Basketball", "2009", "Panini National Treasures", "Stephen Curry", "206", "RPA /99", 15000, 100000, "Ultra Rare"),
        ("Basketball", "1996", "Topps Chrome", "Kobe Bryant", "138", "Refractor", 4000, 60000, "Iconic"),
        ("Basketball", "2018", "Panini Prizm", "Luka Doncic", "280", "Silver Prizm", 500, 8000, "High"),
        ("Basketball", "2019", "Panini Prizm", "Zion Williamson", "248", "Base", 50, 800, "Mid"),
        ("Basketball", "2020", "Panini Prizm", "Anthony Edwards", "258", "Silver Prizm", 200, 3000, "High"),
        ("Basketball", "1969", "Topps", "Lew Alcindor (Kareem)", "25", "Base", 1500, 25000, "Iconic"),
        ("Basketball", "1961", "Fleer", "Wilt Chamberlain", "8", "Base", 2000, 30000, "Iconic"),
        ("Basketball", "2022", "Panini Prizm", "Victor Wembanyama", "275", "Silver Prizm", 300, 5000, "High"),

        # Baseball
        ("Baseball", "1952", "Topps", "Mickey Mantle", "311", "Base", 50000, 500000, "Legendary"),
        ("Baseball", "1909", "T206", "Honus Wagner", "N/A", "Base", 500000, 7000000, "Legendary"),
        ("Baseball", "1989", "Upper Deck", "Ken Griffey Jr.", "1", "Base", 15, 500, "Standard"),
        ("Baseball", "2011", "Topps Update", "Mike Trout", "US175", "Base", 200, 5000, "High"),
        ("Baseball", "1993", "SP", "Derek Jeter", "279", "Foil", 300, 10000, "High"),
        ("Baseball", "2018", "Topps Update", "Shohei Ohtani", "US1", "Base", 50, 2000, "Mid"),
        ("Baseball", "1951", "Bowman", "Willie Mays", "305", "Base", 5000, 50000, "Iconic"),
        ("Baseball", "1954", "Topps", "Hank Aaron", "128", "Base", 3000, 30000, "Iconic"),

        # Football
        ("Football", "2000", "Playoff Contenders", "Tom Brady", "144", "Auto", 30000, 400000, "Legendary"),
        ("Football", "2017", "Panini Prizm", "Patrick Mahomes", "269", "Silver Prizm", 3000, 40000, "Iconic"),
        ("Football", "1958", "Topps", "Jim Brown", "62", "Base", 2000, 25000, "Iconic"),
        ("Football", "2020", "Panini Prizm", "Justin Herbert", "325", "Silver Prizm", 300, 5000, "High"),
        ("Football", "2020", "Panini Prizm", "Joe Burrow", "307", "Silver Prizm", 200, 3000, "High"),

        # Soccer
        ("Soccer", "2018", "Panini Prizm World Cup", "Kylian Mbappe", "80", "Silver Prizm", 500, 8000, "High"),
        ("Soccer", "2004", "Panini Mega Cracks", "Lionel Messi", "71", "Base", 5000, 50000, "Iconic"),
        ("Soccer", "2020", "Topps Chrome UCL", "Erling Haaland", "74", "Refractor", 200, 3000, "High"),
        ("Soccer", "1958", "Alifabolaget", "Pele", "635", "Base", 10000, 100000, "Legendary"),

        # Hockey
        ("Hockey", "1979", "O-Pee-Chee", "Wayne Gretzky", "18", "Base", 3000, 50000, "Iconic"),
        ("Hockey", "2005", "Upper Deck", "Sidney Crosby", "201", "Young Guns", 300, 5000, "High"),
        ("Hockey", "2015", "Upper Deck", "Connor McDavid", "201", "Young Guns", 200, 4000, "High"),

        # Pokemon (crossover with sports card collectors)
        # Excluded - handled in pokemon category

        # Modern parallels & inserts (representative)
        ("Basketball", "2022", "Panini Select", "Various", "N/A", "Courtside", 20, 200, "Standard"),
        ("Football", "2023", "Panini Prizm", "Various", "N/A", "Neon Green", 10, 100, "Standard"),
        ("Baseball", "2023", "Topps Chrome", "Various", "N/A", "Refractor", 5, 50, "Standard"),
    ]

    catalog = []
    for sport, year, set_name, player, card_no, variant, raw_price, graded_price, rarity in cards:
        catalog.append({
            "sport": sport,
            "year": year,
            "set_name": set_name,
            "player": player,
            "card_number": card_no,
            "variant": variant,
            "price_raw": raw_price,
            "price_psa10": graded_price,
            "rarity": rarity,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    player = item["player"]
    year = item["year"]
    set_name = item["set_name"]
    variant = item["variant"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{year}-{set_name}-{player}-{variant}"),
        title=f"{year} {set_name} {player}" + (f" ({variant})" if variant != "Base" else ""),
        set_code=slugify(f"{year}-{set_name}"),
        brand=set_name.split()[0] if set_name else "",
        rarity=item["rarity"],
        notes=f"{item['sport']} | #{item['card_number']}",
        attributes_json={
            "player": player,
            "set": set_name,
            "year": year,
            "variant": variant,
            "sport": item["sport"],
        },
    )


def item_to_price_observations(item: dict) -> list[PriceObservation]:
    rarity_map = {"Standard": 0.2, "Mid": 0.4, "High": 0.6,
                  "Iconic": 0.8, "Ultra Rare": 0.9, "Legendary": 0.95}
    rarity_score = rarity_map.get(item["rarity"], 0.5)

    observations = []
    # Raw (ungraded)
    if item["price_raw"] > 0:
        observations.append(PriceObservation(
            features={
                "condition_score": 0.7,
                "rarity_score": rarity_score,
                "edition_score": 0.5,
                "is_graded": 0.0,
            },
            price=float(item["price_raw"]),
        ))
    # PSA 10 (graded gem mint)
    if item["price_psa10"] > 0:
        observations.append(PriceObservation(
            features={
                "condition_score": 1.0,
                "rarity_score": rarity_score,
                "edition_score": 0.5,
                "is_graded": 1.0,
                "grade_score": 1.0,
            },
            price=float(item["price_psa10"]),
        ))
    return observations


def main():
    parser = argparse.ArgumentParser(description="Import sports cards catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=== Sports Cards Import ===")

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    catalog = get_curated_catalog()

    all_items = [item_to_catalog_item(i) for i in catalog]
    all_observations = []
    for i in catalog:
        all_observations.extend(item_to_price_observations(i))

    write_catalog_sql(CATEGORY, all_items)
    log_progress(CATEGORY, "catalog SQL written", len(all_items))

    write_training_jsonl(CATEGORY, all_observations)
    log_progress(CATEGORY, "training JSONL written", len(all_observations))

    if ingest.enabled:
        inserted = ingest.upsert_catalog(all_items)
        log_progress(CATEGORY, "catalog upserted", inserted)

    ingest.close()

    print(f"\n=== Sports Cards Import Complete ===")
    print(f"  Catalog items:      {len(all_items)}")
    print(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
