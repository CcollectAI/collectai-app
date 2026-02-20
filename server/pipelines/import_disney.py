"""
Import Disney collectibles catalog.

Layer 1 (Catalog):  Curated 130+ items across 20 subcategories → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated data from secondary market (eBay, Mercari, ShopDisney, Cardmarket)
- Covers Disney pins (LE, Fantasy, Hidden Mickey, park-exclusive, Loungefly pin sets),
  Loungefly bags, D23 figures, Jim Shore / Disney Traditions, WDCC (Walt Disney
  Classics Collection), Disney Sorcerer's Arena, Disney Lorcana crossover cards,
  Vinylmation, Disney Infinity, designer ears & spirit jerseys, vintage animation
  cels, Disney Animator's Collection, Disney Designer dolls, Disney Store vintage
  plush, vintage Disneyland/WDW park maps, runDisney medals, Disney100 celebration
  items, Shanghai/Tokyo Disney exclusives, and limited ornaments

Usage:
    python -m pipelines.import_disney [--dry-run]
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

CATEGORY = "disney"


def get_curated_catalog() -> list[dict]:
    """Curated Disney collectibles catalog — 130+ items across 20 subcategories."""

    # (subcategory, name, edition, rarity_tier, price_eur)
    # rarity_tier: grail (>200), high (80-200), mid (30-80), standard (<30)

    items = [
        # ── Disney Pins — Limited Edition ──────────────────────────────
        ("pins", "Haunted Mansion 50th Anniversary LE 2500 Pin", "LE 2500", "high", 120),
        ("pins", "Nightmare Before Christmas 30th LE 3000 Pin", "LE 3000", "high", 95),
        ("pins", "Walt Disney Portrait LE 1000 Pin", "LE 1000", "grail", 200),
        ("pins", "Figment Epcot 40th Anniversary LE 4000 Pin", "LE 4000", "high", 80),
        ("pins", "Stitch Crashes Disney Complete Set (12 Pins)", "LE Monthly", "grail", 450),
        ("pins", "Stitch Crashes Disney Single Pin", "LE Monthly", "mid", 40),
        ("pins", "Disney Villains LE 5000 Pin Set", "LE 5000", "high", 90),
        ("pins", "Disney Princess LE 2000 Jumbo Pin", "LE 2000", "high", 140),
        ("pins", "Frozen 10th Anniversary LE 3000 Pin", "LE 3000", "high", 85),
        ("pins", "Cinderella Castle LE 1500 Jumbo Pin", "LE 1500", "grail", 220),

        # ── Disney Pins — Park Exclusive ───────────────────────────────
        ("pins", "Disneyland 70th Anniversary Park Pin", "Park Exclusive", "mid", 35),
        ("pins", "EPCOT Festival of the Arts Pin", "Park Exclusive", "mid", 30),
        ("pins", "Magic Kingdom 50th Anniversary Pin", "Park Exclusive", "mid", 45),
        ("pins", "Disney Pin Trading Starter Set", "Standard", "standard", 15),
        ("pins", "Disney Cast Member Exclusive Pin", "Cast Exclusive", "high", 80),
        ("pins", "Disney Parks Annual Passholder Pin 2025", "Park Exclusive", "mid", 38),

        # ── Disney Pins — Hidden Mickey ────────────────────────────────
        ("pins", "Hidden Mickey Pin (Rare Character)", "Park Exclusive", "mid", 25),
        ("pins", "Hidden Mickey Chaser Pin (Gold Variant)", "Park Exclusive", "high", 85),
        ("pins", "Hidden Mickey Attractions Series Pin", "Park Exclusive", "standard", 18),
        ("pins", "Hidden Mickey Sidekicks Series Pin", "Park Exclusive", "standard", 15),
        ("pins", "Hidden Mickey Villains Series Completer Pin", "Park Exclusive", "mid", 45),

        # ── Disney Pins — Fantasy Pins ─────────────────────────────────
        ("pins", "Fantasy Pin Maleficent Stained Glass", "Fantasy", "mid", 35),
        ("pins", "Fantasy Pin Ursula Art Nouveau", "Fantasy", "mid", 40),
        ("pins", "Fantasy Pin Sorcerer Mickey Jumbo", "Fantasy", "mid", 50),
        ("pins", "Fantasy Pin Villain Mashup Slider", "Fantasy", "mid", 55),
        ("pins", "Fantasy Pin Figment Rainbow Glitter", "Fantasy", "mid", 60),

        # ── Loungefly Pin Sets ─────────────────────────────────────────
        ("pins", "Loungefly Disney Villains Blind Box Pin Set", "Loungefly Set", "mid", 45),
        ("pins", "Loungefly Disney Princess Enamel Pin Set (6pc)", "Loungefly Set", "mid", 38),
        ("pins", "Loungefly Pixar Alien Remix Pin Set", "Loungefly Set", "mid", 35),
        ("pins", "Loungefly Haunted Mansion Ghost Host Pin", "Loungefly Set", "mid", 32),

        # ── Loungefly Bags ─────────────────────────────────────────────
        ("loungefly", "Loungefly Haunted Mansion Mini Backpack", "Standard", "mid", 65),
        ("loungefly", "Loungefly Villains AOP Backpack", "Standard", "mid", 55),
        ("loungefly", "Loungefly Enchanted Tiki Room Crossbody", "Park Exclusive", "high", 85),
        ("loungefly", "Loungefly Figment Epcot Backpack", "Park Exclusive", "high", 95),
        ("loungefly", "Loungefly Disney Princess Wallet Set", "Standard", "mid", 40),
        ("loungefly", "Loungefly NYCC Exclusive Maleficent Bag", "NYCC Exclusive", "high", 130),
        ("loungefly", "Loungefly Disney100 Platinum Backpack", "D100 Exclusive", "high", 110),

        # ── Jim Shore / Disney Traditions ──────────────────────────────
        ("jim_shore", "Jim Shore Fantasia 80th Anniversary Figure", "Limited", "high", 95),
        ("jim_shore", "Jim Shore Cinderella Romantic Waltz Figurine", "Standard", "mid", 65),
        ("jim_shore", "Jim Shore Mickey Mouse Statement Figure (17in)", "Limited", "high", 130),
        ("jim_shore", "Jim Shore Stitch Ohana Figurine", "Standard", "mid", 55),
        ("jim_shore", "Jim Shore Villain Maleficent Dragon Figure", "Limited", "high", 110),
        ("jim_shore", "Jim Shore Disney Traditions Carousel (Musical)", "Premium", "high", 160),
        ("jim_shore", "Jim Shore Frozen Elsa Ice Castle Figurine", "Standard", "mid", 70),
        ("jim_shore", "Jim Shore Winnie the Pooh & Friends Figurine", "Standard", "mid", 50),

        # ── WDCC — Walt Disney Classics Collection ────────────────────
        ("wdcc", "WDCC Cinderella 'A Lovely Dress for Cinderelly'", "WDCC", "grail", 350),
        ("wdcc", "WDCC Fantasia Sorcerer Mickey 'Mischievous Apprentice'", "WDCC", "grail", 280),
        ("wdcc", "WDCC Bambi 'The Young Prince'", "WDCC", "high", 180),
        ("wdcc", "WDCC Sleeping Beauty Maleficent 'Evil Enchantress'", "WDCC", "grail", 320),
        ("wdcc", "WDCC Pinocchio Jiminy Cricket 'Official Conscience'", "WDCC", "high", 150),
        ("wdcc", "WDCC The Little Mermaid Ariel 'Seahorse Surprise'", "WDCC", "grail", 250),

        # ── Figures — D23 & Limited ────────────────────────────────────
        ("figures", "D23 Exclusive Sorcerer Mickey Figure", "D23 Exclusive", "grail", 200),
        ("figures", "D23 Exclusive Villain Designer Doll", "D23 Exclusive", "high", 180),
        ("figures", "Walt Disney Archives Figure (50th)", "Park Exclusive", "mid", 65),

        # ── Disney Designer Dolls ──────────────────────────────────────
        ("designer_dolls", "Disney Designer Collection Ariel Doll", "Designer LE", "high", 150),
        ("designer_dolls", "Disney Designer Collection Belle Doll", "Designer LE", "high", 140),
        ("designer_dolls", "Disney Designer Collection Jasmine Doll", "Designer LE", "high", 145),
        ("designer_dolls", "Disney Designer Collection Rapunzel Doll", "Designer LE", "high", 135),
        ("designer_dolls", "Disney Designer Midnight Masquerade Tiana Doll", "Designer LE", "high", 170),
        ("designer_dolls", "Disney Designer Fairytale Couples Ariel & Eric Set", "Designer LE", "grail", 280),

        # ── Disney Animator's Collection ───────────────────────────────
        ("animators", "Disney Animators' Collection Rapunzel Doll", "Standard", "standard", 25),
        ("animators", "Disney Animators' Collection Moana Doll", "Standard", "standard", 22),
        ("animators", "Disney Animators' Collection Elsa Doll (1st Edition)", "Limited", "mid", 55),
        ("animators", "Disney Animators' Collection Mulan Doll", "Standard", "standard", 22),
        ("animators", "Disney Animators' Collection Gift Set (5 Dolls)", "Limited", "high", 95),

        # ── Vinylmation ───────────────────────────────────────────────
        ("vinylmation", "Vinylmation Park Series 1 (Sealed Case 24pc)", "Standard", "high", 120),
        ("vinylmation", "Vinylmation Nightmare Before Christmas 9in", "Limited", "high", 90),
        ("vinylmation", "Vinylmation Mickey Through the Years Set", "Limited", "high", 85),
        ("vinylmation", "Vinylmation Urban Redux Series Chaser", "Standard", "mid", 45),
        ("vinylmation", "Vinylmation Star Wars Jedi Mickey 3in", "Standard", "mid", 30),
        ("vinylmation", "Vinylmation Villains Series Maleficent 9in", "Limited", "high", 100),

        # ── Disney Infinity Figures ────────────────────────────────────
        ("infinity", "Disney Infinity 3.0 Crystal Sorcerer Mickey", "Crystal Variant", "high", 85),
        ("infinity", "Disney Infinity 1.0 Sorcerer Mickey (Sealed)", "Standard", "mid", 35),
        ("infinity", "Disney Infinity 2.0 Marvel Complete Set (Sealed)", "Standard", "high", 120),
        ("infinity", "Disney Infinity 3.0 Star Wars Boba Fett", "Standard", "mid", 40),
        ("infinity", "Disney Infinity 3.0 Inside Out Joy (Sealed)", "Standard", "standard", 20),

        # ── Disney Sorcerer's Arena ────────────────────────────────────
        ("sorcerers_arena", "Disney Sorcerer's Arena Epic Alliances Core Set", "Standard", "mid", 40),
        ("sorcerers_arena", "Sorcerer's Arena Turning the Tide Expansion", "Standard", "mid", 30),
        ("sorcerers_arena", "Sorcerer's Arena Promo Sorcerer Mickey Card", "Promo", "mid", 35),
        ("sorcerers_arena", "Sorcerer's Arena Into the Inklands Expansion", "Standard", "mid", 32),

        # ── Disney Lorcana (Disney Crossover Cards) ────────────────────
        ("lorcana", "Lorcana Elsa Spirit of Winter Enchanted", "Enchanted Rare", "grail", 350),
        ("lorcana", "Lorcana Mickey Mouse Brave Little Tailor Enchanted", "Enchanted Rare", "grail", 280),
        ("lorcana", "Lorcana Stitch Rock Star Super Rare", "Super Rare", "high", 80),
        ("lorcana", "Lorcana Maui Demigod Legendary", "Legendary", "high", 95),
        ("lorcana", "Lorcana Maleficent Monstrous Dragon Enchanted", "Enchanted Rare", "grail", 220),
        ("lorcana", "Lorcana Robin Hood Champion of Sherwood Enchanted", "Enchanted Rare", "grail", 250),
        ("lorcana", "Lorcana Simba Returned King Super Rare", "Super Rare", "mid", 55),
        ("lorcana", "Lorcana Belle Strange but Special Legendary", "Legendary", "high", 85),
        ("lorcana", "Lorcana Booster Box The First Chapter (Sealed)", "Sealed Product", "high", 180),

        # ── Vintage Disney ─────────────────────────────────────────────
        ("vintage", "Vintage Disneyland 1960s Park Map", "Vintage", "grail", 350),
        ("vintage", "Vintage Walt Disney World Opening Day Ticket", "Vintage", "grail", 500),
        ("vintage", "Vintage Disney Pin-back Button Set (1970s)", "Vintage", "high", 80),
        ("vintage", "Vintage EPCOT Center Opening Poster", "Vintage", "high", 150),
        ("vintage", "Vintage Disneyland 1955 Opening Year Guidebook", "Vintage", "grail", 600),
        ("vintage", "Vintage Walt Disney World 1971 Souvenir Map", "Vintage", "grail", 280),
        ("vintage", "Vintage Tokyo Disneyland 1983 Opening Day Map", "Vintage", "grail", 250),

        # ── Vintage Animation Cels ─────────────────────────────────────
        ("animation_cels", "Original Production Cel The Little Mermaid Ariel", "Vintage", "grail", 1200),
        ("animation_cels", "Original Production Cel The Lion King Simba", "Vintage", "grail", 900),
        ("animation_cels", "Original Production Cel Sleeping Beauty Maleficent", "Vintage", "grail", 1500),
        ("animation_cels", "Sericel Beauty and the Beast LE 5000", "LE 5000", "high", 180),
        ("animation_cels", "Sericel Aladdin LE 5000", "LE 5000", "high", 150),
        ("animation_cels", "Hand-Painted Cel Fantasia Sorcerer Mickey", "Vintage", "grail", 800),

        # ── Disney Store Vintage Plush ─────────────────────────────────
        ("plush", "Disney Store Vintage Winnie the Pooh Giant Plush (1990s)", "Vintage", "mid", 55),
        ("plush", "Disney Store Vintage Stitch Plush (2002 Release)", "Vintage", "mid", 45),
        ("plush", "Disney Store Vintage Lion King Simba Jumbo Plush", "Vintage", "mid", 60),
        ("plush", "Disney Store Limited Sorcerer Mickey Plush (D23)", "D23 Exclusive", "high", 85),
        ("plush", "Disney Store nuiMOs Plush Complete Set (8pc)", "Standard", "mid", 65),

        # ── Disney Ears & Spirit Jerseys ───────────────────────────────
        ("ears", "Designer Minnie Ears by Vera Wang", "Designer", "high", 95),
        ("ears", "50th Anniversary Gold Ears", "LE Park", "mid", 55),
        ("ears", "Spirit Jersey Matching Ears Set", "Seasonal", "mid", 40),
        ("ears", "Disney Parks Loungefly Ears (Haunted Mansion)", "Park Exclusive", "mid", 45),
        ("ears", "Disney Parks Sequin Ears Rose Gold", "Park Exclusive", "mid", 35),
        ("ears", "Walt Disney World Marathon Ears", "Event Exclusive", "high", 80),
        ("ears", "Disney Parks Spirit Jersey Tie-Dye Pastel", "Park Exclusive", "mid", 65),
        ("ears", "Disney Parks Spirit Jersey Phantom Manor (DLP Exclusive)", "Park Exclusive", "high", 85),
        ("ears", "Disney Parks Coral Spirit Jersey", "Seasonal", "mid", 50),

        # ── runDisney Medals ───────────────────────────────────────────
        ("rundisney", "runDisney Walt Disney World Marathon Medal 2025", "Event Exclusive", "high", 80),
        ("rundisney", "runDisney Dopey Challenge Medal Set (4 Medals)", "Event Exclusive", "high", 180),
        ("rundisney", "runDisney Disneyland Half Marathon Medal 2025", "Event Exclusive", "mid", 55),
        ("rundisney", "runDisney Princess Half Marathon Medal", "Event Exclusive", "mid", 50),
        ("rundisney", "runDisney Wine & Dine Half Marathon Medal", "Event Exclusive", "mid", 45),

        # ── Disney100 Celebration Items ────────────────────────────────
        ("disney100", "Disney100 Platinum Celebration Figurine (Mickey)", "D100 Exclusive", "high", 95),
        ("disney100", "Disney100 Years of Wonder Pin Set (Boxed)", "D100 Exclusive", "high", 110),
        ("disney100", "Disney100 Decades Complete Pin Collection (10pc)", "D100 Exclusive", "grail", 280),
        ("disney100", "Disney100 Swarovski Crystal Mickey Figurine", "Premium", "grail", 250),
        ("disney100", "Disney100 Anniversary Dooney & Bourke Tote", "D100 Exclusive", "high", 180),
        ("disney100", "Disney100 Celebration Loungefly Backpack", "D100 Exclusive", "high", 90),

        # ── Shanghai Disney Exclusives ─────────────────────────────────
        ("shanghai_disney", "Shanghai Disney Grand Opening LE 1000 Pin", "LE 1000", "grail", 220),
        ("shanghai_disney", "Shanghai Disney StellaLou Plush (Park Exclusive)", "Park Exclusive", "mid", 45),
        ("shanghai_disney", "Shanghai Disney LinaBell First Edition Plush", "Park Exclusive", "high", 90),
        ("shanghai_disney", "Shanghai Disney Tron Lightcycle Merchandise Set", "Park Exclusive", "mid", 55),

        # ── Tokyo Disney Exclusives ────────────────────────────────────
        ("tokyo_disney", "Tokyo DisneySea Duffy Bear (Original 2005)", "Vintage", "high", 130),
        ("tokyo_disney", "Tokyo Disney ShellieMay Plush (Park Exclusive)", "Park Exclusive", "mid", 50),
        ("tokyo_disney", "Tokyo Disney 40th Anniversary LE Pin Set", "LE 2000", "high", 150),
        ("tokyo_disney", "Tokyo DisneySea 20th Anniversary Poster Set", "Park Exclusive", "mid", 65),
        ("tokyo_disney", "Tokyo Disney Cookie Ann Plush (First Release)", "Park Exclusive", "mid", 55),

        # ── Ornaments ──────────────────────────────────────────────────
        ("ornaments", "Hallmark Disney Castle LE Ornament", "LE", "mid", 50),
        ("ornaments", "Disney Sketchbook Legacy Ornament Set", "Limited", "mid", 45),
        ("ornaments", "Disney Parks 50th Anniversary Ornament", "Park Exclusive", "mid", 35),
        ("ornaments", "Swarovski Disney Castle Ornament", "Premium", "high", 80),
        ("ornaments", "Radko Disney Ornament (Vintage)", "Vintage", "high", 75),
    ]

    catalog = []
    for subcategory, name, edition, tier, price in items:
        catalog.append({
            "subcategory": subcategory,
            "name": name,
            "edition": edition,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    name = item["name"]
    edition = item["edition"]
    subcategory = item["subcategory"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{subcategory}-{name}"),
        title=name,
        set_code=subcategory,
        brand="Disney",
        rarity=item["rarity_tier"].title(),
        notes=f"{subcategory} | {edition}",
        attributes_json={
            "subcategory": subcategory,
            "edition": edition,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    edition = item["edition"]
    edition_map = {
        "LE 1000": 0.95, "LE 1500": 0.9, "LE 2000": 0.88,
        "LE 2500": 0.85, "LE 3000": 0.8,
        "LE 4000": 0.75, "LE 5000": 0.7, "LE Monthly": 0.7,
        "D23 Exclusive": 0.9, "Designer LE": 0.85, "NYCC Exclusive": 0.85,
        "D100 Exclusive": 0.8, "Cast Exclusive": 0.8,
        "Park Exclusive": 0.65, "LE Park": 0.65,
        "Designer": 0.7, "Event Exclusive": 0.7,
        "Vintage": 0.8, "Premium": 0.7, "WDCC": 0.85,
        "Crystal Variant": 0.75, "Sealed Product": 0.7,
        "Enchanted Rare": 0.95, "Super Rare": 0.75, "Legendary": 0.8,
        "Fantasy": 0.5, "Loungefly Set": 0.55, "Promo": 0.55,
        "Limited": 0.6, "LE": 0.6, "Seasonal": 0.4,
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
    parser = argparse.ArgumentParser(description="Import Disney collectibles catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Disney Import ===")

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

    logger.info(f"\n=== Disney Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
