"""
Import anime soundtrack / limited media catalog.

Layer 1 (Catalog):  Curated anime OSTs & limited media → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers (65+ items):
- Studio Ghibli soundtracks by Joe Hisaishi (CD, vinyl)
- Evangelion OST limited editions
- Cowboy Bebop / Yoko Kanno
- Makoto Shinkai films (Your Name, Weathering With You, Suzume)
- Hiroyuki Sawano works (AoT, Kill la Kill, Guilty Crown, Aldnoah.Zero)
- Yuki Kajiura works (Madoka Magica, SAO, Fate/Zero, Tsubasa)
- Modern hit anime (JJK, Chainsaw Man, Spy x Family, Frieren, etc.)
- Classic/vintage anime (Urusei Yatsura, City Hunter, Macross, Lupin III, Saint Seiya)
- Limited box sets with art books
- Premium complete box sets (Evangelion 12CD, Bebop Sessions, Gundam UC, etc.)
- Event-exclusive CDs
- Preorder bonus discs

Usage:
    python -m pipelines.import_anime_soundtrack [--dry-run]
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

CATEGORY = "anime_soundtrack"


def get_curated_catalog() -> list[dict]:
    """Curated anime soundtrack / limited media catalog (65+ items)."""

    # (franchise, composer, title, format, edition, rarity_tier, price_eur)
    # rarity_tier: grail (>100), high (50-100), mid (20-50), standard (<20)

    items = [
        # Studio Ghibli – Joe Hisaishi (CD)
        ("Spirited Away", "Joe Hisaishi", "Spirited Away OST", "CD", "Standard", "mid", 22),
        ("Princess Mononoke", "Joe Hisaishi", "Princess Mononoke Symphonic Suite", "CD", "Standard", "mid", 25),
        ("My Neighbor Totoro", "Joe Hisaishi", "Totoro Sound Book", "CD", "Standard", "mid", 20),
        ("Howl's Moving Castle", "Joe Hisaishi", "Howl's Moving Castle Soundtrack", "CD", "Standard", "standard", 18),
        ("Nausicaa", "Joe Hisaishi", "Nausicaa of the Valley of the Wind OST", "CD", "Standard", "mid", 28),
        ("Castle in the Sky", "Joe Hisaishi", "Laputa: Castle in the Sky USA Version Soundtrack", "CD", "Limited", "mid", 40),

        # Studio Ghibli – Joe Hisaishi (Vinyl)
        ("Spirited Away", "Joe Hisaishi", "Spirited Away OST Vinyl (2LP)", "Vinyl", "Japanese Pressing", "high", 90),
        ("Princess Mononoke", "Joe Hisaishi", "Princess Mononoke Symphonic Suite Vinyl", "Vinyl", "Japanese Pressing", "high", 85),
        ("My Neighbor Totoro", "Joe Hisaishi", "Totoro Image Album Vinyl", "Vinyl", "Japanese Pressing", "high", 80),
        ("Nausicaa", "Joe Hisaishi", "Nausicaa OST Vinyl (Tokuma)", "Vinyl", "OG Japanese Pressing", "grail", 150),

        # Evangelion OST limited editions
        ("Evangelion", "Shiro Sagisu", "Evangelion Original Soundtrack", "CD", "Standard", "mid", 25),
        ("Evangelion", "Shiro Sagisu", "Evangelion 3.0+1.0 OST (3CD Box)", "CD Box", "Limited", "high", 75),
        ("Evangelion", "Shiro Sagisu", "Evangelion Finally Vinyl (2LP)", "Vinyl", "Limited Color", "grail", 100),
        ("Evangelion", "Various", "Evangelion Vox Complete Box (6CD)", "CD Box", "Limited", "grail", 120),
        ("Evangelion", "Shiro Sagisu", "Evangelion 2.0 You Can (Not) Advance OST", "CD", "Standard", "mid", 22),

        # Cowboy Bebop / Yoko Kanno
        ("Cowboy Bebop", "Yoko Kanno", "Cowboy Bebop OST 1", "CD", "Standard", "mid", 25),
        ("Cowboy Bebop", "Yoko Kanno", "Cowboy Bebop Vitaminless", "CD", "Standard", "mid", 28),
        ("Cowboy Bebop", "Yoko Kanno", "Cowboy Bebop Blue", "CD", "Standard", "mid", 30),
        ("Cowboy Bebop", "Yoko Kanno", "Cowboy Bebop OST Box Set (4CD)", "CD Box", "Limited", "high", 90),
        ("Cowboy Bebop", "Yoko Kanno", "Cowboy Bebop Vinyl (Seatbelts)", "Vinyl", "Reissue", "high", 55),

        # Makoto Shinkai films
        ("Your Name", "RADWIMPS", "Kimi no Na wa. OST", "CD", "Standard", "standard", 18),
        ("Your Name", "RADWIMPS", "Kimi no Na wa. OST Deluxe (2CD+BD)", "CD Box", "Limited", "high", 50),
        ("Weathering With You", "RADWIMPS", "Tenki no Ko Complete Version", "CD", "Standard", "standard", 16),
        ("Suzume", "RADWIMPS / Kazuma Jinnouchi", "Suzume no Tojimari OST", "CD", "Standard", "standard", 15),
        ("Suzume", "RADWIMPS / Kazuma Jinnouchi", "Suzume OST Vinyl (2LP)", "Vinyl", "Standard", "mid", 40),

        # Limited box sets with art books
        ("Violet Evergarden", "Evan Call", "Violet Evergarden Vocal Album + Art Book Box", "CD Box", "Limited", "high", 80),
        ("Made in Abyss", "Kevin Penkin", "Made in Abyss OST Box (2CD + Art Book)", "CD Box", "Limited", "high", 65),
        ("Attack on Titan", "Hiroyuki Sawano", "AoT Final Season Complete OST Box (4CD)", "CD Box", "Limited", "high", 95),
        ("Demon Slayer", "Yuki Kajiura / Go Shiina", "Demon Slayer Music Collection Box (3CD)", "CD Box", "Limited", "high", 70),

        # Event-exclusive CDs
        ("Macross", "Yoko Kanno", "Macross Frontier Galaxy Live 2023 Event CD", "CD", "Event Exclusive", "high", 55),
        ("Love Live!", "Various", "Aqours Fan Meeting Event CD Single", "CD", "Event Exclusive", "mid", 35),
        ("BanG Dream!", "Various", "BanG Dream! 7th Live Event Limited CD", "CD", "Event Exclusive", "mid", 40),

        # Preorder bonus discs
        ("Jujutsu Kaisen", "Various", "JJK S2 Blu-ray Preorder Bonus CD (Soundtrack Sampler)", "CD", "Preorder Bonus", "mid", 30),
        ("Chainsaw Man", "Kensuke Ushio", "CSM Episode 1-4 Preorder Bonus Sound Collection", "CD", "Preorder Bonus", "mid", 35),
        ("Bocchi the Rock!", "Various", "Bocchi the Rock! BD Vol.1 Bonus Live CD", "CD", "Preorder Bonus", "mid", 25),

        # ── NEW ITEMS BELOW ──────────────────────────────────────────────

        # More Studio Ghibli (+4)
        ("Porco Rosso", "Joe Hisaishi", "Porco Rosso OST", "CD", "Standard", "mid", 24),
        ("The Wind Rises", "Joe Hisaishi", "The Wind Rises Soundtrack", "CD", "Standard", "standard", 18),
        ("Tales from Earthsea", "Tamiya Terashima", "Tales from Earthsea OST", "CD", "Standard", "standard", 16),
        ("The Cat Returns", "Yuji Nomi", "The Cat Returns Soundtrack", "CD", "Standard", "standard", 15),

        # Modern Hit Anime (+8)
        ("Jujutsu Kaisen", "Hiroaki Tsutsumi / Yoshimasa Terui", "Jujutsu Kaisen Season 1 OST", "CD", "Standard", "standard", 18),
        ("Chainsaw Man", "Kensuke Ushio", "Chainsaw Man Original Soundtrack Complete Edition", "CD", "Standard", "mid", 22),
        ("Spy x Family", "K)NoW_NAME", "SPY x FAMILY Original Soundtrack", "CD", "Standard", "standard", 16),
        ("Bocchi the Rock!", "Various", "Bocchi the Rock! Original Soundtrack", "CD", "Standard", "standard", 15),
        ("Frieren", "Evan Call", "Frieren: Beyond Journey's End OST", "CD", "Standard", "mid", 20),
        ("Oshi no Ko", "Masaru Yokoyama", "Oshi no Ko Original Soundtrack", "CD", "Standard", "standard", 17),
        ("Vinland Saga", "Yutaka Yamada", "Vinland Saga Original Soundtrack", "CD", "Standard", "mid", 22),
        ("86: Eighty-Six", "Hiroyuki Sawano / KOHTA YAMAMOTO", "86: Eighty-Six OST", "CD", "Standard", "mid", 24),

        # Classic / Vintage (+5)
        ("Urusei Yatsura", "Various", "Urusei Yatsura Music Capsule (OG Pressing)", "CD", "OG Japanese Pressing", "high", 65),
        ("City Hunter", "Various", "City Hunter Original Soundtrack", "CD", "Standard", "mid", 35),
        ("Macross", "Kentaro Haneda", "Macross: Do You Remember Love? OST", "CD", "Standard", "high", 55),
        ("Lupin III", "Yuji Ohno", "Lupin the Third '79 Original Soundtrack", "CD", "Standard", "mid", 38),
        ("Saint Seiya", "Seiji Yokoyama", "Saint Seiya Original Soundtrack I", "CD", "Standard", "mid", 32),

        # Hiroyuki Sawano (+4)
        ("Attack on Titan", "Hiroyuki Sawano", "Attack on Titan OST Box Set (Season 1-3, 6CD)", "CD Box", "Limited", "grail", 130),
        ("Kill la Kill", "Hiroyuki Sawano", "Kill la Kill Original Soundtrack", "CD", "Standard", "mid", 28),
        ("Guilty Crown", "Hiroyuki Sawano", "Guilty Crown Complete Soundtrack", "CD", "Standard", "mid", 30),
        ("Aldnoah.Zero", "Hiroyuki Sawano", "Aldnoah.Zero Original Soundtrack", "CD", "Standard", "mid", 25),

        # Yuki Kajiura (+4)
        ("Madoka Magica", "Yuki Kajiura", "Puella Magi Madoka Magica Complete OST (3CD)", "CD Box", "Limited", "high", 75),
        ("Sword Art Online", "Yuki Kajiura", "Sword Art Online Music Collection", "CD", "Standard", "mid", 22),
        ("Fate/Zero", "Yuki Kajiura", "Fate/Zero Original Soundtrack (2CD Limited Edition)", "CD", "Limited", "high", 60),
        ("Tsubasa Chronicle", "Yuki Kajiura", "Tsubasa Chronicle Original Soundtrack Future Soundscape", "CD", "Standard", "mid", 28),

        # Box Sets / Premium (+6)
        ("Evangelion", "Shiro Sagisu", "Evangelion Complete Soundtrack Box (12CD)", "CD Box", "Limited", "grail", 250),
        ("Cowboy Bebop", "Yoko Kanno", "Cowboy Bebop Complete Sessions Box (8CD)", "CD Box", "Limited", "grail", 180),
        ("Gundam UC", "Hiroyuki Sawano", "Mobile Suit Gundam Unicorn Complete Soundtrack (5CD)", "CD Box", "Limited", "grail", 140),
        ("Your Name / Weathering With You", "RADWIMPS", "Shinkai x RADWIMPS OST Box (Your Name + Weathering, 3CD)", "CD Box", "Limited", "high", 70),
        ("Dragon Ball Z", "Shunsuke Kikuchi", "Dragon Ball Z Complete Song Collection Box (18CD)", "CD Box", "Limited", "grail", 200),
        ("Naruto Shippuden", "Yasuharu Takanashi / Various", "Naruto Shippuden Complete Soundtrack (10CD)", "CD Box", "Limited", "grail", 160),
    ]

    catalog = []
    for franchise, composer, title, fmt, edition, tier, price in items:
        catalog.append({
            "franchise": franchise,
            "composer": composer,
            "title": title,
            "format": fmt,
            "edition": edition,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    franchise = item["franchise"]
    title = item["title"]
    composer = item["composer"]
    fmt = item["format"]
    edition = item["edition"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{franchise}-{title}-{fmt}"),
        title=title,
        set_code=slugify(franchise),
        brand=composer,
        rarity=item["rarity_tier"].title(),
        notes=f"{franchise} | {composer} | {fmt}" + (f" | {edition}" if edition else ""),
        attributes_json={
            "franchise": franchise,
            "composer": composer,
            "format": fmt,
            "edition": edition,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    edition = item["edition"]
    edition_scores = {
        "Limited": 0.80,
        "Limited Color": 0.85,
        "Event Exclusive": 0.90,
        "Preorder Bonus": 0.75,
        "Japanese Pressing": 0.70,
        "OG Japanese Pressing": 0.95,
        "Reissue": 0.40,
        "Standard": 0.30,
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
    parser = argparse.ArgumentParser(description="Import anime soundtrack catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Anime Soundtrack Import ===")

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

    logger.info(f"\n=== Anime Soundtrack Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
