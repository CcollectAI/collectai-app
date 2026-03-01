"""
Import Plush Collectibles catalog (80+ items).

Layer 1 (Catalog):  Curated collectible plush → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Squishmallows (Archie Axolotl, Emily Bat, Malcolm Mushroom, Benny Bigfoot,
  select exclusives, HTF, jumbo, clips)
- Jellycat (Bashful Bunny, Amuseable, Bartholomew Bear, retired/discontinued,
  London exclusive)
- Sanrio (Hello Kitty, Cinnamoroll, My Melody, Kuromi, Pompompurin,
  limited/collaboration)
- Build-A-Bear (Pokémon, licensed, limited edition, online exclusive)
- Pokémon Center plush (sitting cuties, special editions, large scale,
  Japanese exclusive)
- Vintage/Grail plush (Beanie Babies grails, TY Princess Diana bear,
  vintage Care Bears, 1980s-90s)
- Disney plush (park exclusives, nuiMOs, Stitch, limited release)

Usage:
    python -m pipelines.import_plush_collectibles [--dry-run]
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
    logger,
    close_http_client,
)

CATEGORY = "plush_collectibles"

# ---------------------------------------------------------------------------
# Plush-specific rarity overrides (supplement shared RARITY_SCORE_MAP)
# ---------------------------------------------------------------------------
_PLUSH_RARITY: dict[str, float] = {
    "Common": 0.1,
    "Uncommon": 0.3,
    "Rare": 0.5,
    "HTF": 0.75,       # Hard To Find — between Rare and Grail
    "Grail": 0.95,
}

# Brand prestige scores
_BRAND_SCORE: dict[str, float] = {
    "Jellycat": 0.9,
    "Squishmallows": 0.8,
    "Sanrio": 0.7,
    "Pokémon Center": 0.6,
    "Build-A-Bear": 0.6,
    "Disney": 0.6,
    "TY": 0.6,
    "Care Bears": 0.6,
    "Steiff": 0.6,
}


def _plush_rarity_score(rarity: str) -> float:
    """Map plush rarity to 0-1, using local overrides then shared map."""
    return _PLUSH_RARITY.get(rarity, shared_rarity_score(rarity))


def get_curated_catalog() -> list[dict]:
    """Curated plush collectibles catalog: 81 items across 7 sub-categories."""

    # Format: (name, brand, series, size, price_eur, rarity, is_retired, notes)

    items = [
        # ── Squishmallows (22) ──────────────────────────────────────────
        ("Archie the Axolotl", "Squishmallows", "Original Squad", '12"', 35, "Uncommon", False, "Fan-favourite axolotl"),
        ("Emily the Bat", "Squishmallows", "Halloween Squad", '12"', 45, "Uncommon", False, "Halloween 2021 release"),
        ("Malcolm the Mushroom", "Squishmallows", "Original Squad", '12"', 55, "Rare", False, "Highly sought-after design"),
        ("Benny the Bigfoot", "Squishmallows", "Original Squad", '12"', 40, "Uncommon", False, "Brown bigfoot plush"),
        ("Brina the Bigfoot", "Squishmallows", "Original Squad", '12"', 65, "Rare", True, "Pink bigfoot, retired 2021"),
        ("Jack the Black Cat", "Squishmallows", "Halloween Squad", '12"', 70, "Rare", True, "Halloween exclusive, retired"),
        ("Phillipe the Frog", "Squishmallows", "Original Squad", '12"', 80, "HTF", True, "Canadian exclusive, retired"),
        ("Avery the Mallard Duck", "Squishmallows", "Original Squad", '12"', 30, "Uncommon", False, "Green mallard"),
        ("Wendy the Frog", "Squishmallows", "Original Squad", '12"', 25, "Common", False, "Green frog, widely available"),
        ("Connor the Cow", "Squishmallows", "Original Squad", '12"', 55, "Rare", False, "Black and white cow"),
        ("Caedyn the Pink Cow", "Squishmallows", "Valentine Squad", '12"', 90, "HTF", False, "Pink cow, Valentine exclusive"),
        ("Ronnie the Cow", "Squishmallows", "Original Squad", '12"', 45, "Uncommon", False, "Brown spotted cow"),
        ("Reshma the Pink Strawberry", "Squishmallows", "Fruit Squad", '8"', 25, "Common", False, "Small strawberry plush"),
        ("Belana the Cow", "Squishmallows", "Easter Squad", '16"', 60, "Rare", False, "Blue cow, Easter 2022"),
        ("Archie the Axolotl Jumbo", "Squishmallows", "Original Squad", '24" Jumbo', 110, "HTF", False, "Jumbo size, limited stock"),
        ("Emily the Bat Clip", "Squishmallows", "Halloween Squad", 'Clip 3.5"', 12, "Common", False, "Backpack clip version"),
        ("Malcolm the Mushroom Clip", "Squishmallows", "Original Squad", 'Clip 3.5"', 15, "Common", False, "Backpack clip version"),
        ("Benny the Bigfoot Mini", "Squishmallows", "Original Squad", '5"', 8, "Common", False, "Mini size, widely available"),
        ("Santino the Platypus", "Squishmallows", "Learning Squad", '12"', 35, "Uncommon", False, "Teal platypus"),
        ("Fifi the Fox", "Squishmallows", "Original Squad", '12"', 95, "HTF", True, "2018 original run, retired"),
        ("Dawn the Deer", "Squishmallows", "Holiday Squad", '12"', 75, "Rare", True, "2019 holiday exclusive, retired"),
        ("Heather the Dragonfly", "Squishmallows", "Select Series", '12"', 120, "HTF", True, "Five Below exclusive, retired 2020"),

        # ── Jellycat (15) ───────────────────────────────────────────────
        ("Bashful Bunny Beige", "Jellycat", "Bashful", 'Medium 31cm', 28, "Common", False, "Classic Jellycat bunny"),
        ("Bashful Bunny Blush", "Jellycat", "Bashful", 'Medium 31cm', 30, "Common", False, "Pink variant"),
        ("Bashful Bunny Lilac", "Jellycat", "Bashful", 'Medium 31cm', 55, "Uncommon", True, "Retired colour"),
        ("Bartholomew Bear", "Jellycat", "Bartholomew", 'Medium 28cm', 35, "Common", False, "Brown bear with scarf"),
        ("Bartholomew Bear Really Big", "Jellycat", "Bartholomew", 'Really Big 46cm', 80, "Uncommon", False, "Oversized Bartholomew"),
        ("Amuseable Avocado", "Jellycat", "Amuseable", 'Small 20cm', 22, "Common", False, "TikTok-viral avocado"),
        ("Amuseable Toast", "Jellycat", "Amuseable", 'Small 17cm', 22, "Common", False, "Bread slice with face"),
        ("Amuseable Pineapple", "Jellycat", "Amuseable", 'Medium 25cm', 35, "Uncommon", True, "Retired Amuseable"),
        ("Fuddlewuddle Elephant", "Jellycat", "Fuddlewuddle", 'Medium 23cm', 30, "Common", False, "Grey elephant, textured fur"),
        ("Odell Octopus", "Jellycat", "Marine", 'Medium 23cm', 32, "Common", False, "Teal octopus with corduroy tentacles"),
        ("Blossom Bunny Silver", "Jellycat", "Blossom", 'Medium 31cm', 32, "Common", False, "Floral-ear bunny"),
        ("Scrumptious Dragon", "Jellycat", "Scrumptious", 'Medium 26cm', 120, "HTF", True, "Discontinued 2019, collector favourite"),
        ("Bashful Bunny Lavender", "Jellycat", "Bashful", 'Huge 51cm', 95, "Rare", True, "Retired huge size, hard to find"),
        ("London Bus", "Jellycat", "London Collection", 'Medium 17cm', 75, "Rare", False, "London flagship exclusive"),
        ("Jellycat London Bear", "Jellycat", "London Collection", 'Medium 22cm', 85, "Rare", False, "London store-only exclusive"),

        # ── Sanrio (12) ─────────────────────────────────────────────────
        ("Hello Kitty Classic Plush", "Sanrio", "Hello Kitty", 'Medium 25cm', 25, "Common", False, "Classic seated Hello Kitty"),
        ("Hello Kitty 50th Anniversary Gold", "Sanrio", "Hello Kitty", 'Medium 25cm', 65, "Rare", False, "2024 50th anniversary limited"),
        ("Cinnamoroll Large Plush", "Sanrio", "Cinnamoroll", 'Large 40cm', 45, "Uncommon", False, "White puppy with blue eyes"),
        ("Cinnamoroll x Miniso Collab", "Sanrio", "Cinnamoroll", 'Medium 30cm', 35, "Uncommon", False, "Miniso collaboration exclusive"),
        ("My Melody Classic Plush", "Sanrio", "My Melody", 'Medium 25cm', 25, "Common", False, "Pink hood rabbit"),
        ("My Melody x Laduree Paris", "Sanrio", "My Melody", 'Medium 28cm', 85, "Rare", False, "Laduree Paris collaboration"),
        ("Kuromi Gothic Plush", "Sanrio", "Kuromi", 'Medium 25cm', 30, "Common", False, "Black jester hood character"),
        ("Kuromi x Anna Sui Collab", "Sanrio", "Kuromi", 'Medium 28cm', 95, "Rare", False, "Anna Sui fashion collab"),
        ("Pompompurin Classic Plush", "Sanrio", "Pompompurin", 'Medium 25cm', 25, "Common", False, "Golden retriever with beret"),
        ("Pompompurin Pancake Stack", "Sanrio", "Pompompurin", 'Medium 30cm', 55, "Uncommon", False, "Stacking pancake design"),
        ("Little Twin Stars Kiki & Lala Set", "Sanrio", "Little Twin Stars", 'Pair 20cm each', 60, "Uncommon", True, "Retired pair set"),
        ("Sanrio Characters Dream Collab", "Sanrio", "All Stars", 'Large 35cm', 110, "HTF", False, "Sanrio Puroland event exclusive"),

        # ── Build-A-Bear (8) ────────────────────────────────────────────
        ("Pikachu Build-A-Bear", "Build-A-Bear", "Pokémon", 'Standard 40cm', 55, "Uncommon", False, "Pokémon collab, online exclusive"),
        ("Eevee Build-A-Bear", "Build-A-Bear", "Pokémon", 'Standard 40cm', 55, "Uncommon", False, "Pokémon collab, online exclusive"),
        ("Charmander Build-A-Bear", "Build-A-Bear", "Pokémon", 'Standard 40cm', 60, "Uncommon", True, "Retired Pokémon collab"),
        ("Toothless Build-A-Bear", "Build-A-Bear", "How to Train Your Dragon", 'Standard 40cm', 45, "Uncommon", False, "DreamWorks licensed"),
        ("Grogu Build-A-Bear", "Build-A-Bear", "Star Wars", 'Standard 35cm', 50, "Uncommon", False, "The Child / Baby Yoda"),
        ("Baby Yoda Sound Build-A-Bear", "Build-A-Bear", "Star Wars", 'Standard 35cm', 75, "Rare", True, "With sound chip, limited run"),
        ("Spider-Man Build-A-Bear", "Build-A-Bear", "Marvel", 'Standard 40cm', 50, "Uncommon", False, "Marvel licensed"),
        ("Stitch Build-A-Bear", "Build-A-Bear", "Disney", 'Standard 40cm', 65, "Rare", True, "Online exclusive, retired 2023"),

        # ── Pokémon Center Plush (10) ───────────────────────────────────
        ("Pikachu Sitting Cuties", "Pokémon Center", "Sitting Cuties", 'Small 15cm', 15, "Common", False, "Pokémon Fit / Sitting Cuties line"),
        ("Eevee Sitting Cuties", "Pokémon Center", "Sitting Cuties", 'Small 15cm', 15, "Common", False, "Pokémon Fit / Sitting Cuties line"),
        ("Snorlax Large Plush", "Pokémon Center", "Large Scale", '60cm', 120, "Rare", False, "Oversized sleeping Snorlax"),
        ("Life-Size Mewtwo Plush", "Pokémon Center", "Life-Size", '150cm', 450, "HTF", False, "Japan-exclusive life-size, limited stock"),
        ("Charizard Premium Plush", "Pokémon Center", "Premium Collection", '35cm', 55, "Uncommon", False, "Detailed premium quality"),
        ("Gengar Night Parade Plush", "Pokémon Center", "Halloween Collection", 'Medium 25cm', 40, "Uncommon", True, "Halloween 2022, retired"),
        ("Mimikyu Special Edition", "Pokémon Center", "Special Edition", 'Medium 25cm', 45, "Uncommon", False, "Ghost-type fan favourite"),
        ("Lucario Poseable Plush", "Pokémon Center", "Poseable Series", '30cm', 60, "Rare", False, "Articulated plush figure"),
        ("Ditto Transform Pikachu", "Pokémon Center", "Ditto Transform", 'Small 15cm', 20, "Common", False, "Ditto-face Pikachu"),
        ("Rayquaza Long Plush", "Pokémon Center", "Japanese Exclusive", '180cm', 350, "HTF", True, "Japan-only mega-size, retired"),

        # ── Vintage / Grail Plush (8) ──────────────────────────────────
        ("Princess Diana Bear (1st Edition)", "TY", "Beanie Babies", '22cm', 5000, "Grail", True, "PVC pellets, 1st edition, no space in poem"),
        ("Peanut the Royal Blue Elephant", "TY", "Beanie Babies", '20cm', 3000, "Grail", True, "1995 colour error, extremely rare"),
        ("Valentino Bear (Brown Nose Error)", "TY", "Beanie Babies", '20cm', 1800, "Grail", True, "Manufacturing error variant"),
        ("Brownie the Bear", "TY", "Beanie Babies", '20cm', 2500, "Grail", True, "Original 1993 name, pre-Cubbie"),
        ("Tenderheart Bear (1983 Original)", "Care Bears", "Vintage Care Bears", '33cm', 250, "HTF", True, "1983 Kenner original with tag"),
        ("Bedtime Bear (1983 Original)", "Care Bears", "Vintage Care Bears", '33cm', 200, "Rare", True, "1983 Kenner original"),
        ("Good Luck Bear (1983 Original)", "Care Bears", "Vintage Care Bears", '33cm', 220, "Rare", True, "1983 Kenner original, green"),
        ("Steiff Teddy Bear 1902 Replica", "Steiff", "Vintage Replica", '35cm', 450, "HTF", True, "Limited numbered replica of the 1902 original"),

        # ── Disney Plush (8) ────────────────────────────────────────────
        ("Stitch Crashes Disney (Beauty and the Beast)", "Disney", "Stitch Crashes Disney", 'Medium 30cm', 65, "Rare", True, "Monthly limited series, retired"),
        ("Stitch Crashes Disney (The Lion King)", "Disney", "Stitch Crashes Disney", 'Medium 30cm', 70, "Rare", True, "Monthly limited series, retired"),
        ("Mickey Mouse nuiMOs Plush", "Disney", "nuiMOs", 'Small 16cm', 28, "Common", False, "Poseable plush with outfit system"),
        ("Stitch nuiMOs Plush", "Disney", "nuiMOs", 'Small 16cm', 30, "Common", False, "Poseable plush with outfit system"),
        ("Spirit Jersey Bear (50th Anniversary)", "Disney", "Walt Disney World 50th", 'Medium 30cm', 85, "Rare", True, "WDW 50th anniversary park exclusive"),
        ("Orange Bird Plush", "Disney", "EPCOT Flower & Garden", 'Medium 25cm', 55, "Uncommon", True, "EPCOT festival exclusive, retired"),
        ("Figment Plush (EPCOT)", "Disney", "EPCOT", 'Medium 30cm', 45, "Uncommon", False, "EPCOT park exclusive dragon"),
        ("Wishables Dumbo (Mystery)", "Disney", "Wishables", 'Micro 12cm', 18, "Common", False, "Blind bag micro plush"),
    ]

    catalog = []
    for name, brand, series, size, price, rarity, is_retired, notes in items:
        catalog.append({
            "name": name,
            "brand": brand,
            "series": series,
            "size": size,
            "price_eur": price,
            "rarity": rarity,
            "is_retired": is_retired,
            "notes": notes,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    brand = item["brand"]
    series = item["series"]
    name = item["name"]
    size = item["size"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{brand}-{series}-{name}"),
        title=f"{name} ({size})",
        set_code=slugify(series),
        brand=brand,
        rarity=item["rarity"],
        notes=f"{brand} | {series}" + (f" | {item['notes']}" if item["notes"] else ""),
        attributes_json={
            "brand": brand,
            "series": series,
            "size": size,
            "is_retired": item["is_retired"],
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    rarity = item["rarity"]
    brand = item["brand"]

    brand_score = _BRAND_SCORE.get(brand, 0.6)

    return PriceObservation(
        features={
            "condition_score": 0.85,           # most plush NWT (New With Tags)
            "rarity_score": _plush_rarity_score(rarity),
            "brand_score": brand_score,
            "is_retired": 1.0 if item["is_retired"] else 0.0,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Plush Collectibles catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Plush Collectibles Import ===")

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
    close_http_client()

    logger.info(f"\n=== Plush Collectibles Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
