"""
Import anime Blu-ray collector data.

Layer 1 (Catalog):  Curated anime Blu-ray limited editions → category_items (85+ items)
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated catalog of Aniplex USA, JP box sets, Funimation/Crunchyroll LEs
- GKIDS/Shout Factory, Sentai Filmworks, vintage/OOP titles, 4K UHD editions
- Can be augmented with MyAnimeList, AniList, or CDJapan later

Usage:
    python -m pipelines.import_anime_bluray [--dry-run]
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

CATEGORY = "anime_bluray"


def get_curated_catalog() -> list[dict]:
    """Curated anime Blu-ray collector catalog: 87 items across Aniplex, JP imports, Funimation/Crunchyroll, GKIDS, Sentai, vintage/OOP, and 4K UHD."""

    # Format: (publisher, title, format, edition, rarity_tier, price_eur)
    # rarity_tier: grail (>300), high (100-300), mid (50-100), standard (<50)

    releases = [
        # Aniplex USA Limited Editions
        ("Aniplex USA", "Fate/Zero", "Blu-ray", "Aniplex LE Box Set I+II", "high", 350),
        ("Aniplex USA", "Fate/stay night: Unlimited Blade Works", "Blu-ray", "Aniplex LE Box Set", "high", 300),
        ("Aniplex USA", "Demon Slayer: Mugen Train", "Blu-ray", "Aniplex LE", "high", 120),
        ("Aniplex USA", "Demon Slayer Season 1", "Blu-ray", "Aniplex LE Box Set", "high", 250),
        ("Aniplex USA", "Sword Art Online Season 1", "Blu-ray", "Aniplex LE Box Set", "high", 200),
        ("Aniplex USA", "Sword Art Online: Ordinal Scale", "Blu-ray", "Aniplex LE", "mid", 100),
        ("Aniplex USA", "Madoka Magica", "Blu-ray", "Aniplex LE Box Set", "grail", 400),
        ("Aniplex USA", "Madoka Magica: Rebellion", "Blu-ray", "Aniplex LE", "high", 150),
        ("Aniplex USA", "Kimetsu no Yaiba: Swordsmith Village", "Blu-ray", "Aniplex LE", "high", 130),
        ("Aniplex USA", "Your Lie in April", "Blu-ray", "Aniplex LE Box Set", "high", 280),
        ("Aniplex USA", "Monogatari Series", "Blu-ray", "Aniplex LE Box Set", "grail", 380),
        ("Aniplex USA", "Kill la Kill", "Blu-ray", "Aniplex LE Box Set", "high", 250),

        # Japanese BD Box Sets with Limited Extras
        ("JP Import", "Neon Genesis Evangelion", "Blu-ray", "JP BD Box Set", "grail", 450),
        ("JP Import", "Cowboy Bebop", "Blu-ray", "JP BD Box Remix", "grail", 350),
        ("JP Import", "Ghost in the Shell: SAC", "Blu-ray", "JP BD Box Set", "high", 200),
        ("JP Import", "Akira", "4K UHD", "JP 4K Limited Edition", "high", 180),
        ("JP Import", "Dragon Ball Z", "Blu-ray", "JP Dragon Box Set", "grail", 500),
        ("JP Import", "Mobile Suit Gundam", "Blu-ray", "JP Memorial Box Set", "high", 300),
        ("JP Import", "Serial Experiments Lain", "Blu-ray", "JP BD Box Set", "high", 250),
        ("JP Import", "FLCL", "Blu-ray", "JP BD Box Set", "high", 180),
        ("JP Import", "Steins;Gate", "Blu-ray", "JP BD Box Set", "high", 200),
        ("JP Import", "Legend of the Galactic Heroes", "Blu-ray", "JP BD Complete Box", "grail", 480),

        # Funimation / Crunchyroll Limited Editions
        ("Funimation", "My Hero Academia Season 1", "Blu-ray", "Funimation LE", "mid", 80),
        ("Funimation", "Attack on Titan Season 1", "Blu-ray", "Funimation LE Box Set", "high", 120),
        ("Funimation", "Dragon Ball Super: Broly", "Blu-ray", "Funimation LE", "mid", 60),
        ("Funimation", "Fullmetal Alchemist Brotherhood", "Blu-ray", "Funimation Complete Set", "high", 150),
        ("Funimation", "Cowboy Bebop", "Blu-ray", "Funimation Complete Series", "mid", 70),
        ("Crunchyroll", "Jujutsu Kaisen Season 1", "Blu-ray", "Crunchyroll LE", "mid", 90),
        ("Crunchyroll", "Spy x Family Part 1", "Blu-ray", "Crunchyroll LE", "mid", 75),
        ("Crunchyroll", "Chainsaw Man", "Blu-ray", "Crunchyroll LE", "mid", 85),

        # Laserdisc Era Collectibles
        ("Laserdisc", "Akira", "Laserdisc", "Criterion LD", "high", 180),
        ("Laserdisc", "Ghost in the Shell", "Laserdisc", "JP LD Box", "high", 150),
        ("Laserdisc", "Neon Genesis Evangelion", "Laserdisc", "JP LD Complete Set", "grail", 400),
        ("Laserdisc", "Macross: Do You Remember Love?", "Laserdisc", "JP LD", "high", 120),
        ("Laserdisc", "Nausicaa of the Valley of the Wind", "Laserdisc", "JP LD", "mid", 80),
        ("Laserdisc", "My Neighbor Totoro", "Laserdisc", "JP LD", "mid", 60),

        # Key Individual Titles
        ("GKIDS", "Spirited Away", "4K UHD", "GKIDS Collector's", "mid", 45),
        ("GKIDS", "Princess Mononoke", "4K UHD", "GKIDS Collector's", "mid", 42),

        # ── New items below ──────────────────────────────────────────────

        # More Aniplex USA (+6)
        ("Aniplex USA", "Kaguya-sama: Love Is War", "Blu-ray", "Aniplex LE Box Set", "high", 220),
        ("Aniplex USA", "Rascal Does Not Dream of Bunny Girl Senpai", "Blu-ray", "Aniplex LE Box Set", "high", 260),
        ("Aniplex USA", "86: Eighty-Six", "Blu-ray", "Aniplex LE Box Set", "high", 190),
        ("Aniplex USA", "Lycoris Recoil", "Blu-ray", "Aniplex LE Box Set", "high", 170),
        ("Aniplex USA", "My Dress-Up Darling", "Blu-ray", "Aniplex LE Box Set", "high", 160),
        ("Aniplex USA", "Bocchi the Rock!", "Blu-ray", "Aniplex LE Box Set", "high", 175),

        # JP Import Box Sets (+10)
        ("JP Import", "Dragon Ball Z", "Blu-ray", "JP Blu-ray Box Season Set", "grail", 550),
        ("JP Import", "One Piece", "Blu-ray", "JP BD Collection Box", "grail", 480),
        ("JP Import", "Naruto Shippuden", "Blu-ray", "JP BD Box Set", "grail", 420),
        ("JP Import", "Evangelion 3.0+1.0 Thrice Upon a Time", "Blu-ray", "JP Limited Edition", "high", 180),
        ("JP Import", "Cowboy Bebop Remix", "Blu-ray", "JP BD Remix Complete", "grail", 320),
        ("JP Import", "FLCL Complete", "Blu-ray", "JP BD Box Complete", "high", 200),
        ("JP Import", "Serial Experiments Lain Complete", "Blu-ray", "JP BD Restored Edition", "high", 270),
        ("JP Import", "Steins;Gate Complete", "Blu-ray", "JP BD Complete Box", "high", 230),
        ("JP Import", "Ghost in the Shell: SAC 2nd GIG", "Blu-ray", "JP BD Box Set", "high", 210),
        ("JP Import", "Mobile Suit Gundam Unicorn", "Blu-ray", "JP BD Complete Box", "high", 280),

        # Funimation/Crunchyroll LEs (+8)
        ("Funimation", "Attack on Titan Final Season Part 1", "Blu-ray", "Funimation LE", "high", 110),
        ("Funimation", "My Hero Academia Season 5", "Blu-ray", "Funimation LE", "mid", 75),
        ("Crunchyroll", "Dragon Ball Super: Super Hero", "Blu-ray", "Crunchyroll LE", "mid", 55),
        ("Crunchyroll", "One Piece Film Red", "Blu-ray", "Crunchyroll LE", "mid", 65),
        ("Crunchyroll", "Jujutsu Kaisen Season 2", "Blu-ray", "Crunchyroll LE", "mid", 95),
        ("Crunchyroll", "Chainsaw Man Complete", "Blu-ray", "Crunchyroll LE Box Set", "high", 110),
        ("Crunchyroll", "Spy x Family Complete Season 1", "Blu-ray", "Crunchyroll LE Box Set", "high", 105),
        ("Crunchyroll", "Vinland Saga Season 1", "Blu-ray", "Crunchyroll LE Box Set", "high", 115),

        # GKIDS / Shout Factory (+6)
        ("GKIDS", "Studio Ghibli Complete Collection", "Blu-ray", "GKIDS Collector's Box Set", "grail", 450),
        ("GKIDS", "My Neighbor Totoro", "Blu-ray", "GKIDS Steelbook", "mid", 55),
        ("GKIDS", "Princess Mononoke", "Blu-ray", "GKIDS Steelbook", "mid", 55),
        ("GKIDS", "Spirited Away", "Blu-ray", "GKIDS Steelbook", "mid", 58),
        ("Shout Factory", "Akira", "4K UHD", "Shout Factory 4K LE", "high", 120),
        ("Shout Factory", "Perfect Blue", "Blu-ray", "Shout Factory Limited Edition", "high", 140),

        # Vintage / OOP (+8)
        ("Bandai Visual", "Mobile Suit Gundam 0079", "Blu-ray", "Bandai Visual LE Box Set", "grail", 380),
        ("FUNimation", "Dragon Ball Z", "Blu-ray", "Orange Brick Complete Set", "high", 200),
        ("ADV Films", "Neon Genesis Evangelion", "Blu-ray", "Platinum Complete Collection", "grail", 350),
        ("Geneon", "Tenchi Muyo! Ryo-Ohki", "Blu-ray", "Geneon OOP Box Set", "high", 220),
        ("Geneon", "Serial Experiments Lain", "Blu-ray", "Geneon Pioneer LE", "high", 280),
        ("Viz Media", "Dragon Ball Z", "Blu-ray", "Viz Dragon Box Set", "grail", 600),
        ("Discotek Media", "Lupin the Third Part II", "Blu-ray", "Discotek Complete Collection", "high", 160),
        ("Discotek Media", "Mazinger Z", "Blu-ray", "Discotek Complete Collection", "high", 140),

        # Sentai Filmworks (+6)
        ("Sentai Filmworks", "CLANNAD Complete Collection", "Blu-ray", "Sentai LE Box Set", "high", 130),
        ("Sentai Filmworks", "Parasyte -the maxim-", "Blu-ray", "Sentai LE", "mid", 85),
        ("Sentai Filmworks", "No Game No Life", "Blu-ray", "Sentai LE", "mid", 90),
        ("Sentai Filmworks", "Log Horizon Complete", "Blu-ray", "Sentai LE Box Set", "mid", 80),
        ("Sentai Filmworks", "Chihayafuru Complete", "Blu-ray", "Sentai LE Box Set", "high", 110),
        ("Sentai Filmworks", "Made in Abyss", "Blu-ray", "Sentai LE", "mid", 95),

        # 4K UHD Anime (+5)
        ("Funimation", "Dragon Ball Super: Broly", "4K UHD", "Funimation 4K Steelbook", "mid", 65),
        ("GKIDS", "Your Name", "4K UHD", "GKIDS 4K Collector's", "mid", 55),
        ("GKIDS", "Weathering With You", "4K UHD", "GKIDS 4K Collector's", "mid", 50),
        ("Lionsgate", "Ghost in the Shell (1995)", "4K UHD", "Lionsgate 4K LE Steelbook", "high", 100),
        ("Funimation", "Akira", "4K UHD", "Funimation 4K LE", "high", 110),
    ]

    catalog = []
    for publisher, title, fmt, edition, tier, price in releases:
        catalog.append({
            "publisher": publisher,
            "title": title,
            "format": fmt,
            "edition": edition,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    publisher = item["publisher"]
    title = item["title"]
    fmt = item["format"]
    edition = item["edition"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{publisher}-{title}-{edition}"),
        title=f"{title} ({fmt})",
        set_code=publisher.lower().replace(" ", "-"),
        brand=publisher,
        rarity=item["rarity_tier"].title(),
        notes=f"{publisher} | {edition} | {fmt}",
        attributes_json={
            "publisher": publisher,
            "format": fmt,
            "edition": edition,
            "is_jp_import": publisher == "JP Import",
            "is_laserdisc": fmt == "Laserdisc",
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]
    is_limited = any(kw in item["edition"].lower() for kw in ["limited", "le", "box set", "complete"])
    is_jp = item["publisher"] == "JP Import"

    return PriceObservation(
        features={
            "condition_score": 0.9,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": 0.9 if is_limited else 0.4,
            "is_jp_import": 1.0 if is_jp else 0.0,
            "is_laserdisc": 1.0 if item["format"] == "Laserdisc" else 0.0,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import anime Blu-ray catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Anime Blu-ray Import ===")

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

    logger.info(f"\n=== Anime Blu-ray Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
