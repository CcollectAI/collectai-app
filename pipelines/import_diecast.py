"""
Import diecast vehicle collectibles data.

Layer 1 (Catalog):  Curated Hot Wheels, Matchbox, AUTOart, Kyosho, etc. → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated catalog of Hot Wheels RLC, Super Treasure Hunts, Matchbox vintage,
  AUTOart 1:18, Kyosho 1:43, Minichamps F1, Greenlight chase
- Can be augmented with hobbyDB or eBay sold listings later

Usage:
    python -m pipelines.import_diecast [--dry-run]
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

CATEGORY = "diecast"


def get_curated_catalog() -> list[dict]:
    """Curated diecast vehicle collector catalog."""

    # Format: (brand, name, scale, variant, rarity_tier, price_eur)
    # rarity_tier: grail (>200), high (100-200), mid (40-100), standard (<40)

    vehicles = [
        # Hot Wheels Red Line Club (RLC) Exclusives
        ("Hot Wheels RLC", "'55 Chevy Bel Air Gasser", "1:64", "RLC Exclusive 2023", "high", 120),
        ("Hot Wheels RLC", "'71 Datsun 510", "1:64", "RLC Exclusive", "high", 150),
        ("Hot Wheels RLC", "Porsche 993 GT2", "1:64", "RLC Exclusive", "grail", 200),
        ("Hot Wheels RLC", "'69 Dodge Charger R/T", "1:64", "RLC Exclusive", "high", 130),
        ("Hot Wheels RLC", "Nissan Skyline GT-R (R34)", "1:64", "RLC Exclusive", "grail", 180),
        ("Hot Wheels RLC", "Custom Mustang (Spectraflame)", "1:64", "RLC Exclusive", "high", 100),
        ("Hot Wheels RLC", "'64 Impala", "1:64", "RLC Exclusive", "high", 110),
        ("Hot Wheels RLC", "Lamborghini Countach LP500S", "1:64", "RLC Exclusive", "high", 140),

        # Hot Wheels Super Treasure Hunts ($TH)
        ("Hot Wheels $TH", "Toyota AE86 Sprinter Trueno", "1:64", "Super Treasure Hunt", "high", 80),
        ("Hot Wheels $TH", "Porsche 911 GT3 RS", "1:64", "Super Treasure Hunt", "mid", 60),
        ("Hot Wheels $TH", "Nissan Skyline GT-R (BNR32)", "1:64", "Super Treasure Hunt", "mid", 70),
        ("Hot Wheels $TH", "'92 BMW M3", "1:64", "Super Treasure Hunt", "mid", 55),
        ("Hot Wheels $TH", "Tesla Model S", "1:64", "Super Treasure Hunt", "mid", 50),
        ("Hot Wheels $TH", "'70 Chevelle SS", "1:64", "Super Treasure Hunt 2022", "mid", 45),
        ("Hot Wheels $TH", "McLaren Senna", "1:64", "Super Treasure Hunt", "high", 100),
        ("Hot Wheels $TH", "Mazda RX-7 (FD)", "1:64", "Super Treasure Hunt", "mid", 65),

        # Matchbox Vintage
        ("Matchbox", "No. 75 Ferrari Berlinetta", "1:64", "Lesney Vintage 1965", "high", 80),
        ("Matchbox", "No. 41 Ford GT40", "1:64", "Lesney Vintage 1966", "mid", 60),
        ("Matchbox", "No. 5 Lotus Europa", "1:64", "Lesney Vintage 1969", "mid", 50),
        ("Matchbox", "No. 1 Mercedes Benz Lorry", "1:64", "Lesney Vintage 1968", "mid", 45),
        ("Matchbox", "No. 67 Volkswagen 1600 TL", "1:64", "Lesney Vintage 1967", "mid", 55),
        ("Matchbox", "Superfast No. 20 Lamborghini Marzal", "1:64", "Superfast 1969", "mid", 50),
        ("Matchbox", "Models of Yesteryear Y-1 Allchin", "1:64", "Yesteryear Vintage", "standard", 25),
        ("Matchbox", "Models of Yesteryear Y-16 Spyker", "1:64", "Yesteryear Vintage", "standard", 20),

        # AUTOart 1:18 Scale
        ("AUTOart", "Porsche 911 (993) Carrera", "1:18", "Composite", "high", 200),
        ("AUTOart", "Lamborghini Aventador SVJ", "1:18", "Composite", "grail", 350),
        ("AUTOart", "Nissan GT-R (R35) Nismo", "1:18", "Composite", "grail", 300),
        ("AUTOart", "McLaren 720S", "1:18", "Composite", "high", 250),
        ("AUTOart", "Toyota 2000GT", "1:18", "Composite", "grail", 380),
        ("AUTOart", "Ford GT (2017)", "1:18", "Composite", "high", 200),
        ("AUTOart", "Koenigsegg One:1", "1:18", "Composite", "grail", 400),
        ("AUTOart", "Bugatti Chiron", "1:18", "Composite", "grail", 350),

        # Kyosho 1:43 Scale
        ("Kyosho", "Ferrari F40", "1:43", "High-End", "mid", 60),
        ("Kyosho", "Lamborghini Miura SV", "1:43", "High-End", "mid", 70),
        ("Kyosho", "Nissan Skyline 2000 GT-R (KPGC10)", "1:43", "High-End", "mid", 55),
        ("Kyosho", "Toyota Supra (A80)", "1:43", "High-End", "mid", 50),
        ("Kyosho", "Shelby Cobra 427 S/C", "1:43", "High-End", "high", 80),
        ("Kyosho", "Ferrari 250 GTO", "1:43", "High-End", "high", 120),

        # Minichamps F1 Cars
        ("Minichamps", "Red Bull RB19 Verstappen 2023", "1:43", "F1 Collection", "high", 100),
        ("Minichamps", "Mercedes W11 Hamilton 2020", "1:43", "F1 Collection", "high", 120),
        ("Minichamps", "Ferrari SF90 Leclerc 2019", "1:43", "F1 Collection", "mid", 80),
        ("Minichamps", "McLaren MP4/4 Senna 1988", "1:43", "F1 Collection", "grail", 200),
        ("Minichamps", "Williams FW14B Mansell 1992", "1:43", "F1 Collection", "high", 150),
        ("Minichamps", "Ferrari F2004 Schumacher 2004", "1:43", "F1 Collection", "high", 130),
        ("Minichamps", "Red Bull RB16B Verstappen 2021", "1:18", "F1 1:18 Collection", "grail", 300),
        ("Minichamps", "Mercedes W12 Hamilton Abu Dhabi 2021", "1:18", "F1 1:18 Collection", "grail", 280),

        # Greenlight Chase Variants
        ("Greenlight", "1967 Ford Mustang GT Fastback", "1:64", "Chase Green Machine", "mid", 40),
        ("Greenlight", "1970 Dodge Challenger R/T", "1:64", "Chase Green Machine", "mid", 45),
        ("Greenlight", "1969 Chevrolet Camaro Z/28", "1:64", "Chase Green Machine", "standard", 30),
        ("Greenlight", "Jeep Wrangler Rubicon", "1:64", "Chase Green Machine", "standard", 25),
        ("Greenlight", "1979 Pontiac Firebird Trans Am", "1:64", "Chase Green Machine", "mid", 50),
        ("Greenlight", "1971 Plymouth Hemi Cuda", "1:64", "Chase Green Machine", "mid", 55),
        ("Greenlight", "Ford Bronco (2021)", "1:64", "Chase Green Machine", "standard", 35),
    ]

    catalog = []
    for brand, name, scale, variant, tier, price in vehicles:
        catalog.append({
            "brand": brand,
            "name": name,
            "scale": scale,
            "variant": variant,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    brand = item["brand"]
    name = item["name"]
    scale = item["scale"]
    variant = item["variant"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{brand}-{name}-{variant}"),
        title=f"{name} ({scale})",
        set_code=brand.lower().replace(" ", "-").replace("$", "sth"),
        brand=brand.split(" $")[0] if "$" in brand else brand,
        rarity=item["rarity_tier"].title(),
        notes=f"{brand} | {scale} | {variant}",
        attributes_json={
            "brand": brand,
            "scale": scale,
            "variant": variant,
            "is_chase": "chase" in variant.lower() or "$th" in brand.lower(),
            "is_vintage": "vintage" in variant.lower() or "lesney" in variant.lower(),
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]
    rarity_map = {"grail": 0.95, "high": 0.8, "mid": 0.6, "standard": 0.2}
    is_limited = any(kw in item["variant"].lower() for kw in ["exclusive", "chase", "treasure hunt", "limited"])

    return PriceObservation(
        features={
            "condition_score": 0.9,
            "rarity_score": rarity_map.get(tier, 0.5),
            "edition_score": 0.85 if is_limited else 0.4,
            "is_chase": 1.0 if "chase" in item["variant"].lower() or "$th" in item["brand"].lower() else 0.0,
            "is_vintage": 1.0 if "vintage" in item["variant"].lower() or "lesney" in item["variant"].lower() else 0.0,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import diecast vehicles catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=== Diecast Import ===")

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

    print(f"\n=== Diecast Import Complete ===")
    print(f"  Catalog items:      {len(all_items)}")
    print(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
