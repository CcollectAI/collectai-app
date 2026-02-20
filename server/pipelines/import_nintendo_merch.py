"""
Import Nintendo & Pokemon merchandise data (non-cards).

Layer 1 (Catalog):  Curated plush, amiibo, figures, exclusives → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated catalog of 80+ items across all major Nintendo franchises
- Pokemon Center exclusives (plush, figures, TCG accessories)
- Amiibo (common + rare/out-of-print: Gold Mario, Qbby, Mega Yarn Yoshi, etc.)
- Zelda collectibles (Master Sword replicas, Hyrule Historia, steelbooks)
- Mario merchandise (Super Nintendo World, movie merch)
- Animal Crossing, Splatoon, Kirby, Fire Emblem, Metroid collectibles
- Club Nintendo & My Nintendo physical rewards
- Nintendo Store Tokyo/NY exclusives

Usage:
    python -m pipelines.import_nintendo_merch [--dry-run]
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

CATEGORY = "nintendo_merch"


def get_curated_catalog() -> list[dict]:
    """Curated Nintendo / Pokemon merchandise catalog (80+ items).

    Covers all major franchises: Pokemon, Mario, Zelda, Kirby, Splatoon,
    Animal Crossing, Fire Emblem, Metroid.  Includes amiibo (common + rare),
    Pokemon Center exclusives, Club Nintendo / My Nintendo physical rewards,
    Nintendo Store Tokyo/NY exclusives, and limited event items.
    """

    # Format: (franchise, product_type, name, exclusive, rarity_tier, price_eur)
    # rarity_tier: grail (>200), high (80-200), mid (30-80), standard (<30)

    merch = [
        # ── Pokemon Center Plush - Standard ──────────────────────────────
        ("Pokemon", "Plush", "Pikachu Sitting Plush 8in", "", "standard", 18),
        ("Pokemon", "Plush", "Eevee Sitting Plush 8in", "", "standard", 18),
        ("Pokemon", "Plush", "Charizard Plush 12in", "", "standard", 28),
        ("Pokemon", "Plush", "Gengar Plush 8in", "", "standard", 20),
        ("Pokemon", "Plush", "Snorlax Plush 12in", "", "standard", 25),

        # ── Pokemon Center Plush - Exclusive / Limited ────────────────────
        ("Pokemon", "Plush", "Pikachu Halloween Costume Plush", "Pokemon Center", "mid", 45),
        ("Pokemon", "Plush", "Mimikyu Giant Plush 24in", "Pokemon Center", "high", 120),
        ("Pokemon", "Plush", "Snorlax Bean Bag Chair 60in", "Pokemon Center", "grail", 280),
        ("Pokemon", "Plush", "Life-Size Arcanine Plush", "Pokemon Center JP", "grail", 300),
        ("Pokemon", "Plush", "Ditto Transform Pikachu Plush", "Pokemon Center", "mid", 35),
        ("Pokemon", "Plush", "Eeveelution Collection Box Set", "Pokemon Center", "high", 180),
        ("Pokemon", "Plush", "Sitting Cuties Full Kanto Set", "Pokemon Center", "grail", 250),
        ("Pokemon", "Plush", "Scarlet & Violet Starter Set", "Pokemon Center", "mid", 50),

        # ── Pokemon Center Exclusive Figures ──────────────────────────────
        ("Pokemon", "Figure", "Charizard Premium Figure", "Pokemon Center", "mid", 65),
        ("Pokemon", "Figure", "Mewtwo Gallery Figure DX", "Pokemon Center", "mid", 55),
        ("Pokemon", "Figure", "Pikachu VMAX Premium Figure", "Pokemon Center", "mid", 45),
        ("Pokemon", "Figure", "Rayquaza Gallery Figure", "Pokemon Center", "mid", 60),
        ("Pokemon", "Figure", "Legendary Birds Articuno Set", "Pokemon Center", "high", 80),

        # ── Pokemon Center TCG Accessories ────────────────────────────────
        ("Pokemon", "TCG Accessory", "Pikachu Leather Deck Box", "Pokemon Center", "mid", 38),
        ("Pokemon", "TCG Accessory", "Eevee Evolution Premium Sleeves 65ct", "Pokemon Center", "standard", 12),
        ("Pokemon", "TCG Accessory", "Charizard Playmat Premium", "Pokemon Center", "mid", 32),
        ("Pokemon", "TCG Accessory", "Ultra Ball Flip Deck Box", "Pokemon Center", "standard", 22),
        ("Pokemon", "TCG Accessory", "Scarlet & Violet Elite Trainer Box Plus", "Pokemon Center", "mid", 55),

        # ── Amiibo - Common ───────────────────────────────────────────────
        ("Mario", "Amiibo", "Mario (Super Smash Bros.)", "", "standard", 15),
        ("Zelda", "Amiibo", "Link (Breath of the Wild)", "", "standard", 18),
        ("Pokemon", "Amiibo", "Pikachu (Super Smash Bros.)", "", "standard", 15),
        ("Splatoon", "Amiibo", "Inkling Girl (Splatoon 3)", "", "standard", 14),
        ("Kirby", "Amiibo", "Kirby (Kirby Series)", "", "standard", 16),

        # ── Amiibo - Rare / Out of Print ──────────────────────────────────
        ("Mario", "Amiibo", "Gold Mario", "Walmart Exclusive", "high", 80),
        ("Mario", "Amiibo", "Silver Mario", "Exclusive", "high", 90),
        ("Animal Crossing", "Amiibo", "Villager (1st Print)", "", "high", 100),
        ("Zelda", "Amiibo", "Guardian (Breath of the Wild)", "", "high", 90),
        ("Splatoon", "Amiibo", "Callie & Marie 2-Pack", "", "high", 120),
        ("Zelda", "Amiibo", "Link (Skyward Sword)", "", "mid", 50),
        ("Kirby", "Amiibo", "Meta Knight", "Best Buy Exclusive", "high", 80),
        ("Pokemon", "Amiibo", "Mewtwo (Super Smash Bros.)", "", "mid", 45),
        ("Metroid", "Amiibo", "Samus (Metroid Dread)", "", "mid", 40),
        ("Zelda", "Amiibo", "Zelda & Loftwing", "", "high", 85),
        ("Zelda", "Amiibo", "Link (Tears of the Kingdom)", "", "mid", 35),
        ("Mario", "Amiibo", "Qbby (BoxBoy!)", "JP Exclusive", "grail", 250),
        ("Mario", "Amiibo", "Mega Yarn Yoshi", "Toys R Us Exclusive", "grail", 220),
        ("Monster Hunter", "Amiibo", "Navirou (Monster Hunter Stories)", "JP Exclusive", "high", 150),
        ("Dark Souls", "Amiibo", "Solaire of Astora", "", "high", 110),
        ("Monster Hunter", "Amiibo", "Rathalos & Rider (Monster Hunter Stories)", "JP Exclusive", "high", 130),

        # ── Zelda Collectibles ────────────────────────────────────────────
        ("Zelda", "Merch", "Master Sword Replica Light", "Nintendo Store", "mid", 55),
        ("Zelda", "Replica", "Master Sword Full-Size Metal Replica", "", "high", 180),
        ("Zelda", "Replica", "Hylian Shield Replica Wall Mount", "", "high", 160),
        ("Zelda", "Book", "Hyrule Historia Collector's Edition", "", "high", 85),
        ("Zelda", "Book", "Art & Artifacts Limited Edition", "", "high", 95),
        ("Zelda", "Book", "Creating a Champion Hero's Edition", "", "mid", 70),
        ("Zelda", "Steelbook", "Tears of the Kingdom Steelbook", "Nintendo Store", "mid", 45),
        ("Zelda", "Steelbook", "Breath of the Wild Steelbook", "Limited Edition", "mid", 60),
        ("Zelda", "Steelbook", "Skyward Sword HD Steelbook", "Nintendo Store", "mid", 40),
        ("Zelda", "Merch", "Tears of the Kingdom Collector Pin Set", "Nintendo Store", "mid", 50),

        # ── Mario Merchandise ─────────────────────────────────────────────
        ("Mario", "Merch", "Super Mario Odyssey Coin Set", "Nintendo Store", "mid", 40),
        ("Mario", "Merch", "Mario Red Joy-Con Set", "Nintendo Store", "mid", 65),
        ("Mario", "Merch", "Super Nintendo World Mario Hat", "Universal Studios JP", "mid", 60),
        ("Mario", "Merch", "Super Nintendo World Power-Up Band Mario", "Universal Studios", "mid", 42),
        ("Mario", "Merch", "Super Nintendo World Bowser Popcorn Bucket", "Universal Studios JP", "mid", 55),
        ("Mario", "Figure", "Super Mario Movie 5in Mario Figure", "", "standard", 18),
        ("Mario", "Figure", "Super Mario Movie 7in DK Figure", "", "standard", 22),
        ("Mario", "Figure", "Super Mario Movie Peach Castle Playset", "", "mid", 45),
        ("Mario", "Merch", "Mario Kart Trophy Replica", "Nintendo Store", "mid", 75),

        # ── Animal Crossing Merchandise ───────────────────────────────────
        ("Animal Crossing", "Merch", "Tom Nook Ceramic Mug Set", "Nintendo Store", "standard", 25),
        ("Animal Crossing", "Figure", "K.K. Slider Totakeke Figure", "Nintendo Store", "mid", 48),
        ("Animal Crossing", "Plush", "Isabelle Plush 10in", "", "standard", 22),
        ("Animal Crossing", "Plush", "Tom Nook Plush 12in", "", "standard", 24),
        ("Animal Crossing", "Merch", "Animal Crossing New Horizons Journal & Pen Set", "Nintendo Store", "standard", 28),

        # ── Splatoon Merchandise ──────────────────────────────────────────
        ("Splatoon", "Merch", "Splatoon 3 Tableturf Battle Cards", "Nintendo Store", "mid", 30),
        ("Splatoon", "Plush", "Splatoon 3 Smallfry Plush", "", "standard", 20),
        ("Splatoon", "Merch", "Splatoon Squid Sisters Concert Poster Set", "Nintendo JP", "mid", 35),
        ("Splatoon", "Figure", "Splatoon 3 Shiver Figma", "", "mid", 65),

        # ── Kirby Merchandise ─────────────────────────────────────────────
        ("Kirby", "Merch", "Kirby Cafe Menu Plate Set", "Nintendo Store JP", "high", 85),
        ("Kirby", "Plush", "Kirby 30th Anniversary Plush Set", "Nintendo Store JP", "mid", 55),
        ("Kirby", "Plush", "Waddle Dee Plush 8in", "", "standard", 18),
        ("Kirby", "Figure", "Kirby Nendoroid 30th Anniversary", "", "mid", 50),
        ("Kirby", "Merch", "Kirby Cafe Ceramic Mug & Saucer", "Kirby Cafe JP", "mid", 38),

        # ── Fire Emblem Figures ───────────────────────────────────────────
        ("Fire Emblem", "Figure", "Marth Figma", "", "mid", 65),
        ("Fire Emblem", "Figure", "Byleth (Male) 1/7 Scale Figure", "", "high", 140),
        ("Fire Emblem", "Figure", "Edelgard von Hresvelg 1/7 Scale Figure", "", "high", 150),
        ("Fire Emblem", "Figure", "Lucina Figma", "", "mid", 70),
        ("Fire Emblem", "Amiibo", "Corrin Player 2 (Female)", "Exclusive", "high", 95),

        # ── Metroid Collectibles ──────────────────────────────────────────
        ("Metroid", "Figure", "Samus Aran Varia Suit Figma", "", "high", 90),
        ("Metroid", "Replica", "Metroid Dread Special Edition Artbook + Steelbook", "", "mid", 75),
        ("Metroid", "Figure", "Metroid Prime Samus 1/4 Scale Statue", "First 4 Figures", "grail", 450),
        ("Metroid", "Merch", "Baby Metroid Prop Replica Light", "", "mid", 55),

        # ── Club Nintendo Rewards (Retired) ───────────────────────────────
        ("Mario", "Club Nintendo", "Club Nintendo Gold Nunchuk", "Club Nintendo", "grail", 350),
        ("Zelda", "Club Nintendo", "Zelda 25th Anniversary Poster Set", "Club Nintendo", "high", 90),
        ("Mario", "Club Nintendo", "Super Mario Galaxy Original Soundtrack", "Club Nintendo", "high", 85),
        ("Mario", "Club Nintendo", "Hanafuda Playing Cards Mario Edition", "Club Nintendo", "mid", 60),
        ("Zelda", "Club Nintendo", "Majora's Mask Soundtrack CD", "Club Nintendo", "high", 100),
        ("Mario", "Club Nintendo", "Club Nintendo Platinum Playing Cards", "Club Nintendo", "mid", 45),

        # ── My Nintendo Physical Rewards ──────────────────────────────────
        ("Mario", "My Nintendo", "My Nintendo Mario Pin Set", "My Nintendo", "mid", 35),
        ("Zelda", "My Nintendo", "My Nintendo Zelda TOTK Poster Set", "My Nintendo", "mid", 30),
        ("Animal Crossing", "My Nintendo", "My Nintendo AC Tote Bag", "My Nintendo", "standard", 25),
        ("Splatoon", "My Nintendo", "My Nintendo Splatoon 3 Sticker Sheet", "My Nintendo", "standard", 15),

        # ── Nintendo Store Tokyo / NY Exclusives ──────────────────────────
        ("Mario", "Store Exclusive", "Nintendo Tokyo Grand Opening Mario Tee", "Nintendo Store Tokyo", "high", 80),
        ("Zelda", "Store Exclusive", "Nintendo NY Hyrule Crest Hoodie", "Nintendo Store NY", "mid", 65),
        ("Pokemon", "Store Exclusive", "Nintendo Tokyo Pikachu Mascot Plush", "Nintendo Store Tokyo", "mid", 40),
        ("Mario", "Store Exclusive", "Nintendo Store Tokyo 1st Anniversary Pin Badge Set", "Nintendo Store Tokyo", "high", 95),
        ("Kirby", "Store Exclusive", "Nintendo Store Tokyo Kirby Bento Box Set", "Nintendo Store Tokyo", "mid", 48),

        # ── Limited Event Items ───────────────────────────────────────────
        ("Pokemon", "Event", "Worlds 2023 Pikachu Plush", "Pokemon Worlds", "high", 150),
        ("Pokemon", "Event", "Pokemon Center 25th Anniversary Box", "Pokemon Center", "grail", 250),
        ("Pokemon", "Event", "GO Fest 2023 Exclusive Plush", "Pokemon GO Fest", "high", 100),
        ("Splatoon", "Event", "Splatoon Koshien Trophy Replica", "Nintendo JP", "grail", 200),
    ]

    catalog = []
    for franchise, product_type, name, exclusive, tier, price in merch:
        catalog.append({
            "franchise": franchise,
            "product_type": product_type,
            "name": name,
            "exclusive": exclusive,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    franchise = item["franchise"]
    product_type = item["product_type"]
    name = item["name"]
    exclusive = item["exclusive"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{franchise}-{product_type}-{name}"),
        title=name,
        set_code=franchise.lower().replace(" ", "-"),
        brand="Nintendo" if franchise in ("Mario", "Zelda", "Kirby", "Splatoon", "Animal Crossing", "Fire Emblem", "Metroid", "Monster Hunter", "Dark Souls") else "Pokemon Company",
        rarity=item["rarity_tier"].title(),
        notes=f"{franchise} | {product_type}" + (f" | {exclusive}" if exclusive else ""),
        attributes_json={
            "franchise": franchise,
            "product_type": product_type,
            "exclusive": exclusive,
            "is_amiibo": product_type == "Amiibo",
            "is_plush": product_type == "Plush",
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]
    exclusive_score = 0.85 if item["exclusive"] else 0.3

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": exclusive_score,
            "is_amiibo": 1.0 if item["product_type"] == "Amiibo" else 0.0,
            "is_plush": 1.0 if item["product_type"] == "Plush" else 0.0,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Nintendo / Pokemon merch catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Nintendo Merch Import ===")

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

    logger.info(f"\n=== Nintendo Merch Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
