"""
Import VTuber merchandise catalog.

Layer 1 (Catalog):  Curated VTuber merch → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Hololive: acrylic stands, tapestries, badges per talent
- Hololive anniversary/birthday sets
- Nijisanji: merch drops
- Hololive x Lawson collabs
- Concert/event limited goods
- Key talents: Gawr Gura, Pekora, Marine, Subaru, Mori Calliope, Suisei

Usage:
    python -m pipelines.import_vtuber [--dry-run]
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

CATEGORY = "vtuber"


def get_curated_catalog() -> list[dict]:
    """Curated VTuber merchandise catalog."""

    # (agency, talent, item_type, name, exclusive_type, rarity_tier, price_eur)
    # rarity_tier: grail (>100), high (50-100), mid (20-50), standard (<20)

    items = [
        # Hololive – Acrylic stands
        ("Hololive", "Gawr Gura", "Acrylic Stand", "Gawr Gura Birthday 2022 Acrylic Stand", "Birthday", "mid", 28),
        ("Hololive", "Usada Pekora", "Acrylic Stand", "Usada Pekora 3rd Anniversary Acrylic Stand", "Anniversary", "mid", 30),
        ("Hololive", "Houshou Marine", "Acrylic Stand", "Houshou Marine Birthday 2023 Acrylic Stand", "Birthday", "mid", 25),
        ("Hololive", "Oozora Subaru", "Acrylic Stand", "Oozora Subaru New Outfit Acrylic Stand", "Outfit Reveal", "mid", 22),
        ("Hololive", "Mori Calliope", "Acrylic Stand", "Mori Calliope UnAlive Acrylic Stand", "Album Release", "mid", 25),
        ("Hololive", "Hoshimachi Suisei", "Acrylic Stand", "Hoshimachi Suisei Stellar into the Galaxy Stand", "Concert", "mid", 30),

        # Hololive – Tapestries
        ("Hololive", "Gawr Gura", "Tapestry", "Gawr Gura 3rd Anniversary B2 Tapestry", "Anniversary", "mid", 40),
        ("Hololive", "Houshou Marine", "Tapestry", "Houshou Marine Shion Summer B2 Tapestry", "Seasonal", "mid", 38),
        ("Hololive", "Shiranui Flare", "Tapestry", "Shiranui Flare Birthday B2 Tapestry", "Birthday", "standard", 18),

        # Hololive – Anniversary/Birthday sets
        ("Hololive", "Gawr Gura", "Birthday Set", "Gawr Gura Birthday 2023 Full Merch Set", "Birthday", "high", 90),
        ("Hololive", "Usada Pekora", "Birthday Set", "Usada Pekora Birthday 2023 Complete Set", "Birthday", "high", 85),
        ("Hololive", "Hoshimachi Suisei", "Birthday Set", "Suisei Birthday 2023 Merch Set", "Birthday", "high", 80),
        ("Hololive", "Mori Calliope", "Anniversary Set", "Mori Calliope 3rd Anniversary Box", "Anniversary", "high", 95),

        # Hololive – Badges & small goods
        ("Hololive", "Various", "Badge Set", "Hololive Gen 3 Random Badge Collection", "Standard", "standard", 12),
        ("Hololive", "Various", "Badge Set", "Hololive EN Myth Badge Set Complete", "Generation", "mid", 35),

        # Nijisanji merch drops
        ("Nijisanji", "Vox Akuma", "Acrylic Stand", "Vox Akuma Birthday 2023 Acrylic Stand", "Birthday", "mid", 25),
        ("Nijisanji", "Luca Kaneshiro", "Acrylic Stand", "Luca Kaneshiro Anniversary Acrylic Stand", "Anniversary", "mid", 22),
        ("Nijisanji", "Elira Pendora", "Tapestry", "Elira Pendora Debut Anniversary Tapestry", "Anniversary", "mid", 30),
        ("Nijisanji", "Selen Tatsuki", "Badge Set", "Selen Tatsuki Random Badge Collection", "Standard", "standard", 10),
        ("Nijisanji", "Various", "Merch Box", "Nijisanji EN Luxiem Voice Pack + Goods Set", "Group", "high", 65),

        # Hololive x Lawson collabs
        ("Hololive", "Various", "Collab Clear File", "Hololive x Lawson Summer Clear File Set", "Lawson Collab", "mid", 25),
        ("Hololive", "Gawr Gura", "Collab Acrylic", "Gura x Lawson Limited Acrylic Stand", "Lawson Collab", "mid", 35),
        ("Hololive", "Usada Pekora", "Collab Snack", "Pekora x Lawson Collab Chips + Card", "Lawson Collab", "standard", 15),
        ("Hololive", "Various", "Collab Tapestry", "Hololive x Lawson Valentine Tapestry Set", "Lawson Collab", "high", 55),

        # Concert/event limited goods
        ("Hololive", "Various", "Concert Goods", "Hololive 4th Fes. Our Bright Parade Penlight", "Concert", "mid", 40),
        ("Hololive", "Various", "Concert Goods", "Hololive 4th Fes. T-Shirt", "Concert", "mid", 45),
        ("Hololive", "Hoshimachi Suisei", "Concert Goods", "Suisei Stellar into the Galaxy Penlight", "Solo Concert", "high", 55),
        ("Hololive", "Various", "Concert Goods", "Hololive 3rd Fes. Link Your Wish Full Merch Set", "Concert", "grail", 140),
        ("Hololive", "Mori Calliope", "Concert Goods", "Mori Calliope New Underworld Order Tour Hoodie", "Solo Concert", "high", 70),
        ("Hololive", "Various", "Concert Goods", "HoloEN Connect the World Stage Acrylic Set", "Concert", "high", 60),
    ]

    catalog = []
    for agency, talent, item_type, name, exclusive_type, tier, price in items:
        catalog.append({
            "agency": agency,
            "talent": talent,
            "item_type": item_type,
            "name": name,
            "exclusive_type": exclusive_type,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    agency = item["agency"]
    talent = item["talent"]
    name = item["name"]
    item_type = item["item_type"]
    exclusive_type = item["exclusive_type"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{agency}-{name}"),
        title=name,
        set_code=slugify(f"{agency}-{talent}"),
        brand=agency,
        rarity=item["rarity_tier"].title(),
        notes=f"{agency} | {talent} | {item_type}" + (f" | {exclusive_type}" if exclusive_type else ""),
        attributes_json={
            "agency": agency,
            "talent": talent,
            "item_type": item_type,
            "exclusive_type": exclusive_type,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    exclusive_type = item["exclusive_type"]
    edition_scores = {
        "Birthday": 0.70,
        "Anniversary": 0.75,
        "Concert": 0.80,
        "Solo Concert": 0.85,
        "Lawson Collab": 0.75,
        "Outfit Reveal": 0.65,
        "Album Release": 0.60,
        "Seasonal": 0.50,
        "Generation": 0.55,
        "Group": 0.60,
        "Standard": 0.30,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_scores.get(exclusive_type, 0.5),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import VTuber merch catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== VTuber Merch Import ===")

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

    logger.info(f"\n=== VTuber Merch Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
