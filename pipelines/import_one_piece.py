"""
Import One Piece collectibles data.

Layer 1 (Catalog):  Curated P.O.P., Figuarts, Ichiban Kuji, cards → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated catalog of Portrait of Pirates (Megahouse), Figuarts ZERO,
  Ichiban Kuji, Banpresto prize figures, One Piece Card Game
- Can be augmented with MyFigureCollection API or scraping later

Usage:
    python -m pipelines.import_one_piece [--dry-run]
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

CATEGORY = "one_piece"


def get_curated_catalog() -> list[dict]:
    """Curated One Piece collectibles catalog."""

    # Format: (line, name, variant, rarity_tier, price_eur)
    # rarity_tier: grail (>200), high (100-200), mid (40-100), standard (<40)

    items = [
        # Portrait of Pirates (P.O.P.) by Megahouse
        ("P.O.P. Maximum", "Monkey D. Luffy", "Gear 4 Boundman", "high", 200),
        ("P.O.P. Maximum", "Kaido", "Dragon Form", "grail", 300),
        ("P.O.P. Maximum", "Whitebeard", "Edward Newgate", "grail", 280),
        ("P.O.P. Limited", "Shanks", "Film Red Ver.", "high", 180),
        ("P.O.P. Warriors Alliance", "Roronoa Zoro", "Wano Country", "high", 160),
        ("P.O.P. Warriors Alliance", "Trafalgar Law", "Wano Country", "high", 140),
        ("P.O.P. Sailing Again", "Nami", "Ver. BB_02", "high", 150),
        ("P.O.P. Sailing Again", "Boa Hancock", "Ver. BB", "high", 170),
        ("P.O.P. NEO-DX", "Portgas D. Ace", "10th Limited", "grail", 250),
        ("P.O.P. NEO-DX", "Crocodile", "", "high", 130),
        ("P.O.P. SOC", "Monkey D. Luffy", "Gear 5", "grail", 280),
        ("P.O.P. SOC", "Jinbe", "", "high", 120),

        # Figuarts ZERO
        ("Figuarts ZERO", "Monkey D. Luffy", "Extra Battle Paramount War", "mid", 80),
        ("Figuarts ZERO", "Roronoa Zoro", "Extra Battle", "mid", 70),
        ("Figuarts ZERO", "Sanji", "Extra Battle Diable Jambe", "mid", 65),
        ("Figuarts ZERO", "Portgas D. Ace", "Extra Battle Fire Fist", "high", 100),
        ("Figuarts ZERO", "Marco", "Extra Battle Phoenix", "mid", 75),
        ("Figuarts ZERO", "Eustass Kid", "Extra Battle", "mid", 60),
        ("Figuarts ZERO", "Yamato", "Extra Battle Thunder Bagua", "mid", 85),
        ("Figuarts ZERO", "Kaido", "Extra Battle King of the Beasts", "high", 100),

        # Ichiban Kuji Prizes
        ("Ichiban Kuji", "Luffy", "Last One Prize Gear 5", "grail", 200),
        ("Ichiban Kuji", "Shanks", "Last One Prize Film Red", "high", 180),
        ("Ichiban Kuji", "Zoro", "Prize A Wano", "high", 120),
        ("Ichiban Kuji", "Kaido", "Prize A Beast Form", "high", 150),
        ("Ichiban Kuji", "Yamato", "Prize B Wano", "mid", 80),
        ("Ichiban Kuji", "Uta", "Last One Prize Film Red", "high", 100),
        ("Ichiban Kuji", "Ace & Luffy", "Prize A Memories", "mid", 90),
        ("Ichiban Kuji", "Law", "Prize B Wano", "mid", 70),

        # Banpresto Prize Figures
        ("Banpresto", "Monkey D. Luffy", "DXF The Grandline Men", "standard", 20),
        ("Banpresto", "Roronoa Zoro", "DXF The Grandline Men", "standard", 22),
        ("Banpresto", "Sanji", "DXF The Grandline Men", "standard", 18),
        ("Banpresto", "Nami", "Glitter & Glamours", "standard", 25),
        ("Banpresto", "Boa Hancock", "Glitter & Glamours", "standard", 28),
        ("Banpresto", "Monkey D. Luffy", "King of Artist Gear 5", "mid", 35),
        ("Banpresto", "Yamato", "DXF The Grandline Lady", "standard", 25),
        ("Banpresto", "Shanks", "DXF The Grandline Men Film Red", "standard", 30),

        # One Piece Card Game - Notable Cards
        ("OP Card Game", "Monkey D. Luffy", "OP01 Leader Alt Art", "mid", 40),
        ("OP Card Game", "Roronoa Zoro", "OP01 SP Alt Art", "high", 120),
        ("OP Card Game", "Shanks", "OP01 SEC Alt Art", "high", 150),
        ("OP Card Game", "Nami", "OP01 SP Alt Art", "high", 100),
        ("OP Card Game", "Trafalgar Law", "OP02 Leader Alt Art", "mid", 50),
        ("OP Card Game", "Yamato", "OP02 SEC", "mid", 60),
        ("OP Card Game", "Monkey D. Luffy", "OP05 Gear 5 SEC", "grail", 200),
        ("OP Card Game", "Charlotte Katakuri", "OP03 Leader Alt Art", "mid", 45),

        # Film / Special Edition Items
        ("Film Red", "Uta Figure", "DXF Film Red", "mid", 35),
        ("Film Red", "Shanks Figure", "DXF Film Red Special", "mid", 50),
        ("Film Gold", "Luffy Film Gold", "DXF Special", "mid", 40),
        ("Stampede", "Bullet", "DXF Stampede", "mid", 45),
        ("20th Anniversary", "Monkey D. Luffy", "Ichiban Kuji 20th Anniv", "high", 130),
        ("25th Anniversary", "Straw Hat Crew", "Complete Figure Set", "grail", 250),
    ]

    catalog = []
    for line, name, variant, tier, price in items:
        catalog.append({
            "line": line,
            "name": name,
            "variant": variant,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    line = item["line"]
    name = item["name"]
    variant = item["variant"]

    title_parts = [name]
    if variant:
        title_parts.append(f"({variant})")

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{line}-{name}-{variant}"),
        title=" ".join(title_parts),
        set_code=line.lower().replace(" ", "-").replace(".", ""),
        brand=_line_to_brand(line),
        rarity=item["rarity_tier"].title(),
        notes=f"{line}" + (f" | {variant}" if variant else ""),
        attributes_json={
            "line": line,
            "variant": variant,
            "is_figure": line not in ("OP Card Game",),
            "is_card": line == "OP Card Game",
            "is_prize": line in ("Ichiban Kuji", "Banpresto"),
        },
    )


def _line_to_brand(line: str) -> str:
    brand_map = {
        "P.O.P.": "Megahouse",
        "Figuarts ZERO": "Bandai",
        "Ichiban Kuji": "Bandai Spirits",
        "Banpresto": "Banpresto",
        "OP Card Game": "Bandai",
    }
    for prefix, brand in brand_map.items():
        if line.startswith(prefix):
            return brand
    return "Bandai"


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]
    rarity_map = {"grail": 0.95, "high": 0.8, "mid": 0.6, "standard": 0.2}
    is_limited = item["line"].startswith("P.O.P.") or "Last One" in item.get("variant", "")

    return PriceObservation(
        features={
            "condition_score": 0.9,
            "rarity_score": rarity_map.get(tier, 0.5),
            "edition_score": 0.85 if is_limited else 0.4,
            "is_figure": 1.0 if item["line"] != "OP Card Game" else 0.0,
            "is_card": 1.0 if item["line"] == "OP Card Game" else 0.0,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import One Piece collectibles catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=== One Piece Import ===")

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

    print(f"\n=== One Piece Import Complete ===")
    print(f"  Catalog items:      {len(all_items)}")
    print(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
