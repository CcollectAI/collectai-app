"""
Import Taylor Swift collectibles catalog.

Layer 1 (Catalog):  Curated vinyl variants, signed CDs, tour merch,
                    cassettes, picture discs, magazine covers, Blu-rays,
                    RSD/Target/Japan exclusives & holiday collections → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated data from secondary market (Discogs, eBay sold listings)
- Covers 80+ items: vinyl variants, signed editions, Eras Tour exclusives,
  RSD releases, Target exclusives, Japan editions, cassette tapes,
  picture discs, magazine covers, concert film Blu-rays, limited merch
  collabs, and holiday collections

Usage:
    python -m pipelines.import_taylor_swift [--dry-run]
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

CATEGORY = "taylor_swift"


def get_curated_catalog() -> list[dict]:
    """Curated Taylor Swift collectibles catalog (80+ items).

    Covers vinyl variants (standard, Target, RSD, Japan, picture disc),
    signed CDs, Eras Tour merch (era outfits, posters, VIP, wristbands,
    guitar picks), cassette tapes, magazine covers, concert film Blu-rays,
    limited merch collabs, and holiday collections.
    """

    # (album, item_type, name, variant, rarity_tier, price_eur)
    # rarity_tier: grail (>150), high (60-150), mid (30-60), standard (<30)

    items = [
        # ── Midnights Vinyl Variants ──────────────────────────────────
        ("Midnights", "vinyl", "Midnights Moonstone Blue Vinyl", "Moonstone Blue", "mid", 35),
        ("Midnights", "vinyl", "Midnights Jade Green Vinyl", "Jade Green", "mid", 38),
        ("Midnights", "vinyl", "Midnights Mahogany Vinyl", "Mahogany", "mid", 32),
        ("Midnights", "vinyl", "Midnights Blood Moon Vinyl", "Blood Moon", "mid", 40),
        ("Midnights", "vinyl", "Midnights Lavender Marbled Vinyl", "Lavender (Target)", "mid", 55),
        ("Midnights", "vinyl", "Midnights Clock Set (4 Vinyl)", "Clock Set", "high", 140),

        # ── Folklore / Evermore Vinyl ─────────────────────────────────
        ("Folklore", "vinyl", "Folklore In the Trees Vinyl", "In the Trees", "mid", 40),
        ("Folklore", "vinyl", "Folklore Running Like Water Vinyl", "Running Like Water", "mid", 38),
        ("Folklore", "vinyl", "Folklore Meet Me Behind the Mall Vinyl", "Meet Me Behind the Mall", "mid", 42),
        ("Folklore", "vinyl", "Folklore Hide and Seek Vinyl", "Hide and Seek", "mid", 35),
        ("Evermore", "vinyl", "Evermore Green Vinyl", "Green (Target)", "mid", 45),
        ("Evermore", "vinyl", "Evermore Deluxe Vinyl", "Deluxe", "mid", 38),

        # ── Lover Vinyl ───────────────────────────────────────────────
        ("Lover", "vinyl", "Lover Pink + Blue Vinyl", "Standard", "standard", 28),
        ("Lover", "vinyl", "Lover Live From Paris Vinyl", "Limited", "mid", 40),

        # ── Reputation Vinyl ──────────────────────────────────────────
        ("Reputation", "vinyl", "Reputation Picture Disc Vinyl", "Picture Disc", "mid", 55),
        ("Reputation", "vinyl", "Reputation Orange Vinyl (FYE)", "FYE Exclusive", "high", 75),

        # ── 1989 (Taylor's Version) Vinyl ─────────────────────────────
        ("1989 TV", "vinyl", "1989 TV Sunrise Boulevard Yellow", "Sunrise Boulevard", "mid", 32),
        ("1989 TV", "vinyl", "1989 TV Rose Garden Pink", "Rose Garden Pink", "mid", 35),
        ("1989 TV", "vinyl", "1989 TV Aquamarine Green", "Aquamarine Green", "mid", 33),
        ("1989 TV", "vinyl", "1989 TV Crystal Skies Blue", "Crystal Skies", "mid", 34),

        # ── Tortured Poets Department Vinyl ───────────────────────────
        ("TTPD", "vinyl", "TTPD Phantom Clear Vinyl", "Phantom Clear (Target)", "mid", 38),
        ("TTPD", "vinyl", "TTPD The Bolter Vinyl", "The Bolter", "mid", 35),
        ("TTPD", "vinyl", "TTPD The Albatross Vinyl", "The Albatross", "mid", 36),
        ("TTPD", "vinyl", "TTPD The Manuscript Vinyl", "The Manuscript", "mid", 37),
        ("TTPD", "vinyl", "TTPD The Black Dog Vinyl", "The Black Dog", "mid", 36),

        # ── Speak Now (Taylor's Version) Vinyl ────────────────────────
        ("Speak Now TV", "vinyl", "Speak Now TV Orchid Marbled Vinyl", "Orchid Marbled", "mid", 34),
        ("Speak Now TV", "vinyl", "Speak Now TV Violet Vinyl", "Violet (Target)", "mid", 42),
        ("Speak Now TV", "vinyl", "Speak Now TV Lilac Vinyl", "Lilac", "mid", 33),

        # ── Red (Taylor's Version) Vinyl ──────────────────────────────
        ("Red TV", "vinyl", "Red TV Standard Red Vinyl", "Standard", "standard", 28),
        ("Red TV", "vinyl", "Red TV Target Exclusive Red Vinyl", "Red (Target)", "mid", 40),

        # ── Fearless (Taylor's Version) Vinyl ─────────────────────────
        ("Fearless TV", "vinyl", "Fearless TV Gold Vinyl", "Gold", "standard", 28),
        ("Fearless TV", "vinyl", "Fearless TV Target Exclusive Vinyl", "Target Exclusive", "mid", 38),

        # ── Signed CDs (all albums) ──────────────────────────────────
        ("Midnights", "signed_cd", "Midnights Signed CD with Heart", "Signed + Heart", "high", 130),
        ("Folklore", "signed_cd", "Folklore Signed CD", "Signed", "high", 90),
        ("Evermore", "signed_cd", "Evermore Signed CD", "Signed", "high", 85),
        ("Lover", "signed_cd", "Lover Signed Booklet CD", "Signed", "high", 140),
        ("Reputation", "signed_cd", "Reputation Signed CD (Magazine)", "Signed", "grail", 180),
        ("1989 TV", "signed_cd", "1989 Taylor's Version Signed CD", "Signed", "high", 110),
        ("TTPD", "signed_cd", "The Tortured Poets Department Signed CD", "Signed", "high", 65),
        ("TTPD", "signed_cd", "TTPD Signed CD with Heart", "Signed + Heart", "high", 130),
        ("Speak Now TV", "signed_cd", "Speak Now TV Signed CD", "Signed", "high", 95),
        ("Red TV", "signed_cd", "Red TV Signed CD", "Signed", "high", 100),
        ("Fearless TV", "signed_cd", "Fearless TV Signed CD", "Signed", "high", 85),

        # ── Record Store Day Exclusives ───────────────────────────────
        ("RSD", "vinyl", "Folklore Long Pond Sessions RSD", "RSD Exclusive", "high", 85),
        ("RSD", "vinyl", "Lakes 7-inch RSD", "RSD Exclusive", "high", 70),
        ("RSD", "vinyl", "All Too Well 10 Min RSD 7-inch", "RSD Exclusive", "high", 65),
        ("RSD", "vinyl", "Cardigan RSD 7-inch", "RSD Exclusive", "high", 60),
        ("RSD", "vinyl", "Christmas Tree Farm RSD 7-inch", "RSD Exclusive", "high", 75),

        # ── Target Exclusives ─────────────────────────────────────────
        ("Midnights", "vinyl", "Midnights Target Lavender Deluxe", "Lavender Deluxe (Target)", "high", 65),
        ("TTPD", "vinyl", "TTPD Smoke Swirl Target Vinyl", "Smoke Swirl (Target)", "mid", 42),

        # ── Japan-Exclusive Editions ──────────────────────────────────
        ("Midnights", "cd", "Midnights Japan Deluxe CD (Bonus Track)", "Japan Exclusive", "high", 60),
        ("1989 TV", "cd", "1989 TV Japan Deluxe CD (Bonus Track)", "Japan Exclusive", "mid", 55),
        ("TTPD", "cd", "TTPD Japan Deluxe CD (Bonus Track)", "Japan Exclusive", "mid", 50),
        ("Lover", "cd", "Lover Japan Deluxe CD (Bonus Track)", "Japan Exclusive", "high", 65),
        ("Folklore", "cd", "Folklore Japan Deluxe CD (Bonus Track)", "Japan Exclusive", "mid", 55),

        # ── Picture Discs ─────────────────────────────────────────────
        ("Lover", "vinyl", "Lover Picture Disc Vinyl", "Picture Disc", "high", 70),
        ("Midnights", "vinyl", "Midnights Picture Disc Vinyl", "Picture Disc", "high", 75),
        ("1989 TV", "vinyl", "1989 TV Picture Disc Vinyl", "Picture Disc", "high", 65),

        # ── Cassette Tapes ────────────────────────────────────────────
        ("Midnights", "cassette", "Midnights Cassette (Lavender)", "Lavender Cassette", "standard", 18),
        ("Midnights", "cassette", "Midnights Cassette (Jade Green)", "Jade Green Cassette", "standard", 18),
        ("Folklore", "cassette", "Folklore Cassette (Clandestine)", "Limited Cassette", "standard", 22),
        ("Evermore", "cassette", "Evermore Cassette (Green)", "Limited Cassette", "standard", 22),
        ("Lover", "cassette", "Lover Cassette (Pink Heart)", "Limited Cassette", "standard", 20),
        ("TTPD", "cassette", "TTPD Cassette (Ink Black)", "Limited Cassette", "standard", 20),
        ("1989 TV", "cassette", "1989 TV Cassette (Rose Garden)", "Limited Cassette", "standard", 18),
        ("Speak Now TV", "cassette", "Speak Now TV Cassette (Orchid)", "Limited Cassette", "standard", 18),
        ("Red TV", "cassette", "Red TV Cassette", "Limited Cassette", "standard", 20),
        ("Reputation", "cassette", "Reputation Cassette (Snake)", "Limited Cassette", "mid", 35),

        # ── Eras Tour Merch (Era Outfit Sets) ─────────────────────────
        ("Eras Tour", "merch", "Eras Tour Lover Era Bodysuit Set", "Tour Exclusive", "high", 110),
        ("Eras Tour", "merch", "Eras Tour Folklore Era Cardigan", "Tour Exclusive", "high", 95),
        ("Eras Tour", "merch", "Eras Tour Reputation Era Bodysuit", "Tour Exclusive", "high", 120),
        ("Eras Tour", "merch", "Eras Tour Midnights Era Outfit Set", "Tour Exclusive", "high", 115),
        ("Eras Tour", "merch", "Eras Tour 1989 Era Crop Top Set", "Tour Exclusive", "high", 100),
        ("Eras Tour", "merch", "Eras Tour Speak Now Era Gown Replica", "Tour Exclusive", "grail", 180),

        # ── Eras Tour Merch (General) ─────────────────────────────────
        ("Eras Tour", "merch", "Eras Tour Blue Crewneck", "Tour Exclusive", "high", 120),
        ("Eras Tour", "merch", "Eras Tour Poster (City Specific)", "Tour Exclusive", "high", 80),
        ("Eras Tour", "merch", "Eras Tour Friendship Bracelet Set", "Tour Exclusive", "standard", 20),
        ("Eras Tour", "merch", "Eras Tour Light-Up Wristband", "Tour Exclusive", "mid", 35),
        ("Eras Tour", "merch", "Eras Tour VIP Box", "VIP Exclusive", "grail", 200),
        ("Eras Tour", "merch", "Eras Tour Japan Exclusive Tee", "Japan Exclusive", "high", 90),
        ("Eras Tour", "merch", "Eras Tour VIP Lanyard + Laminate", "VIP Exclusive", "high", 65),
        ("Eras Tour", "merch", "Eras Tour Guitar Pick Set (5-pack)", "Tour Exclusive", "mid", 40),
        ("Eras Tour", "merch", "Eras Tour Opening Night Poster", "Tour Exclusive", "grail", 160),
        ("Eras Tour", "merch", "Eras Tour Confetti (Sealed Bag)", "Tour Exclusive", "standard", 15),

        # ── Magazine Covers ───────────────────────────────────────────
        ("Magazine", "collectible", "Vogue US September 2019 (Lover)", "Magazine Cover", "high", 60),
        ("Magazine", "collectible", "Rolling Stone Midnights Cover 2022", "Magazine Cover", "mid", 45),
        ("Magazine", "collectible", "Time Person of the Year 2023", "Magazine Cover", "high", 70),
        ("Magazine", "collectible", "British Vogue January 2020", "Magazine Cover", "mid", 55),
        ("Magazine", "collectible", "NME Folklore Cover 2020", "Magazine Cover", "mid", 35),
        ("Magazine", "collectible", "Elle US April 2019 (4-Cover Set)", "Magazine Cover", "high", 80),

        # ── Concert Film Blu-rays ─────────────────────────────────────
        ("Eras Tour", "bluray", "Eras Tour Concert Film Blu-ray", "Standard", "standard", 25),
        ("Eras Tour", "bluray", "Eras Tour Concert Film Blu-ray Steelbook", "Limited", "mid", 45),
        ("Reputation", "bluray", "Reputation Stadium Tour Netflix Blu-ray", "Limited", "mid", 55),
        ("1989", "bluray", "1989 World Tour Live Blu-ray", "Limited", "high", 60),

        # ── Limited Merch Collabs ─────────────────────────────────────
        ("Collaboration", "merch", "Stella McCartney x Lover Jacket", "Limited", "grail", 280),
        ("Collaboration", "merch", "Keds x Taylor Swift Champion Sneakers", "Limited", "high", 90),
        ("Collaboration", "merch", "Taylor x NFL (Chiefs) Friendship Bracelet Kit", "Limited", "mid", 35),

        # ── Holiday Collections ───────────────────────────────────────
        ("Holiday", "merch", "Taylor Swift Holiday Snowglobe (2023)", "Limited", "high", 75),
        ("Holiday", "merch", "Midnights Holiday Ornament Set", "Limited", "mid", 40),
        ("Holiday", "merch", "Taylor Swift Advent Calendar (2024)", "Limited", "high", 65),
        ("Holiday", "merch", "Christmas Tree Farm Knit Sweater", "Limited", "high", 85),
    ]

    catalog = []
    for album, item_type, name, variant, tier, price in items:
        catalog.append({
            "album": album,
            "item_type": item_type,
            "name": name,
            "variant": variant,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    album = item["album"]
    name = item["name"]
    variant = item["variant"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{album}-{name}"),
        title=name,
        set_code=slugify(album),
        brand="Taylor Swift",
        rarity=item["rarity_tier"].title(),
        notes=f"{album} | {item['item_type']} | {variant}",
        attributes_json={
            "album": album,
            "item_type": item["item_type"],
            "variant": variant,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    variant = item["variant"]
    edition_map = {
        "Signed": 0.85, "Signed + Heart": 0.95, "Signed CD": 0.85,
        "RSD Exclusive": 0.8, "VIP Exclusive": 0.9, "Tour Exclusive": 0.7,
        "Japan Exclusive": 0.75, "FYE Exclusive": 0.7,
        "Picture Disc": 0.65, "Clock Set": 0.7,
        "Magazine Cover": 0.55, "Cassette": 0.4,
        "Limited": 0.6, "Deluxe": 0.5, "Target": 0.5,
        "Standard": 0.2,
    }
    # Find best matching edition score
    edition_score = 0.4
    for key, score in edition_map.items():
        if key in variant:
            edition_score = score
            break

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_score,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Taylor Swift collectibles catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Taylor Swift Import ===")

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

    logger.info(f"\n=== Taylor Swift Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
