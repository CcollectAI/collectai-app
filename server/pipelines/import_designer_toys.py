"""
Import Designer Toys / Art Toys catalog.

Layer 1 (Catalog):  Curated designer toy figures → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- KAWS Companions (open / dissected editions)
- Bearbrick 1000% collaborations
- Pop Mart (Molly, Dimoo blind box sets)
- Superplastic (Janky, Guggimon)
- Coarse figures
- Ron English, Takashi Murakami complexcon figures

Usage:
    python -m pipelines.import_designer_toys [--dry-run]
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

CATEGORY = "designer_toys"


def get_curated_catalog() -> list[dict]:
    """Curated designer toy catalog covering major artists and brands."""

    # (brand, line, name, edition, rarity_tier, price_eur)
    # rarity_tier: grail (>1500), high (500-1500), mid (100-500), standard (<100)

    toys = [
        # KAWS Companions
        ("KAWS", "Companion", "Companion Open Edition Grey", "Open Edition", "mid", 280),
        ("KAWS", "Companion", "Companion Open Edition Black", "Open Edition", "mid", 300),
        ("KAWS", "Companion", "Companion Open Edition Brown", "Open Edition", "mid", 320),
        ("KAWS", "Companion", "Companion Open Edition Pink", "Open Edition", "mid", 350),
        ("KAWS", "Companion", "Companion Flayed Grey", "Open Edition", "mid", 300),
        ("KAWS", "Companion", "Companion Flayed Black", "Open Edition", "mid", 320),
        ("KAWS", "Companion", "Companion Flayed Brown", "Open Edition", "mid", 340),
        ("KAWS", "Companion", "Dissected Companion Grey 2006", "Limited", "grail", 2800),
        ("KAWS", "Companion", "Dissected Companion Brown 2006", "Limited", "grail", 2600),
        ("KAWS", "Companion", "Resting Place Companion", "Limited", "high", 1200),
        ("KAWS", "Small Lie", "Small Lie Grey", "Open Edition", "mid", 250),
        ("KAWS", "Small Lie", "Small Lie Black", "Open Edition", "mid", 270),
        ("KAWS", "BFF", "BFF Pink", "Open Edition", "mid", 350),
        ("KAWS", "BFF", "BFF Blue", "Open Edition", "mid", 380),
        ("KAWS", "Together", "Together Grey", "Open Edition", "mid", 450),
        ("KAWS", "Holiday", "Holiday Japan (Mount Fuji)", "Limited", "high", 900),
        ("KAWS", "Holiday", "Holiday Singapore", "Limited", "high", 800),
        ("KAWS", "What Party", "What Party White", "Open Edition", "mid", 150),

        # Bearbrick 1000%
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Basquiat V1", "Collab", "high", 1400),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Basquiat V2", "Collab", "high", 1200),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Banksy Flower Bomber", "Collab", "grail", 3500),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% fragment design", "Collab", "grail", 4200),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Keith Haring V1", "Collab", "high", 1100),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% BAPE Camo Green", "Collab", "grail", 3800),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Hajime Sorayama Sexy Robot", "Collab", "grail", 4800),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Karimoku Carved Wood", "Collab", "grail", 5000),
        ("Medicom", "Bearbrick 400%", "Bearbrick 400% Basquiat V1", "Collab", "mid", 350),
        ("Medicom", "Bearbrick 400%", "Bearbrick 400% Banksy Flower Bomber", "Collab", "high", 500),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% fragment design", "Collab", "high", 550),

        # Pop Mart
        ("Pop Mart", "Molly", "Molly Anniversary Statues Series", "Blind Box Set", "standard", 75),
        ("Pop Mart", "Molly", "Molly x Instinctoy Erosion", "Collab", "mid", 180),
        ("Pop Mart", "Dimoo", "Dimoo World Heritage Series", "Blind Box Set", "standard", 65),
        ("Pop Mart", "Dimoo", "Dimoo Fairy Tale Series", "Blind Box Set", "standard", 55),
        ("Pop Mart", "Skullpanda", "Skullpanda Night City Series", "Blind Box Set", "standard", 60),
        ("Pop Mart", "The Monsters", "The Monsters Circus Series", "Blind Box Set", "standard", 55),
        ("Pop Mart", "Mega Collection", "Mega Collection 1000% Space Molly Jasmine", "Mega", "high", 900),
        ("Pop Mart", "Mega Collection", "Mega Collection 1000% Space Molly Christmas", "Mega", "high", 1100),

        # Superplastic
        ("Superplastic", "Janky", "Janky Series 1 Full Case", "Blind Box Set", "standard", 90),
        ("Superplastic", "Janky", "Janky x Guggimon OG", "Standard", "standard", 25),
        ("Superplastic", "Guggimon", "Guggimon Supervillain 8-inch", "Standard", "mid", 120),
        ("Superplastic", "Guggimon", "Guggimon x Fortnite Edition", "Collab", "mid", 200),
        ("Superplastic", "Kranky", "Kranky Superplastic 8-inch Glow", "Limited", "mid", 180),
        ("Superplastic", "Janky", "Janky x BAIT Edition", "Collab", "mid", 350),

        # Coarse
        ("Coarse", "Omen", "Omen Fade 10-inch", "Limited", "mid", 350),
        ("Coarse", "Omen", "Omen Rise 10-inch", "Limited", "mid", 380),
        ("Coarse", "Noop", "Noop Blackout Edition", "Limited", "high", 600),
        ("Coarse", "Pain", "Pain Ignite 14-inch", "Limited", "high", 750),

        # Ron English
        ("Ron English", "MC Supersized", "MC Supersized Original Colorway", "Limited", "mid", 400),
        ("Ron English", "MC Supersized", "MC Supersized Glow-in-Dark", "Limited", "high", 600),
        ("Ron English", "Temper Tot", "Temper Tot OG Red", "Limited", "mid", 250),
        ("Ron English", "Telegrinnies", "Telegrinnies Full Set", "Limited", "mid", 350),

        # Takashi Murakami
        ("Takashi Murakami", "ComplexCon", "Flower Parent and Child (Blue/White)", "ComplexCon Exclusive", "grail", 1800),
        ("Takashi Murakami", "ComplexCon", "Murakami x KAWS Flower", "ComplexCon Exclusive", "grail", 2200),
        ("Takashi Murakami", "Kaikai Kiki", "Mr. DOB Figure Gold", "Limited", "high", 900),
        ("Takashi Murakami", "Kaikai Kiki", "Flower Ball 3D Magnet Set", "Standard", "mid", 200),
    ]

    catalog = []
    for brand, line, name, edition, tier, price in toys:
        catalog.append({
            "brand": brand,
            "line": line,
            "name": name,
            "edition": edition,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    brand = item["brand"]
    line = item["line"]
    name = item["name"]
    edition = item["edition"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{brand}-{name}"),
        title=name,
        set_code=slugify(line),
        brand=brand,
        rarity=item["rarity_tier"].title(),
        notes=f"{brand} | {line}" + (f" | {edition}" if edition else ""),
        attributes_json={
            "brand": brand,
            "line": line,
            "edition": edition,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    edition = item["edition"]
    edition_scores = {
        "Limited": 0.85,
        "Collab": 0.75,
        "ComplexCon Exclusive": 0.95,
        "Mega": 0.80,
        "Open Edition": 0.3,
        "Standard": 0.2,
        "Blind Box Set": 0.2,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_scores.get(edition, 0.5),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Designer Toys catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Designer Toys Import ===")

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

    logger.info(f"\n=== Designer Toys Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
