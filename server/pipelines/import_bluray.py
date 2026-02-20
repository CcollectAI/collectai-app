"""
Import Blu-ray Steelbook & boutique label collector data.

Layer 1 (Catalog):  Curated collector Blu-rays → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated catalog of Criterion, Arrow Video, Steelbooks, 4K UHD, boutique labels
- Can be augmented with Blu-ray.com or TMDB later

Usage:
    python -m pipelines.import_bluray [--dry-run]
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

CATEGORY = "bluray_steelbook"


def get_curated_catalog() -> list[dict]:
    """Curated Blu-ray collector catalog (100+ items): Criterion, Arrow Video, Indicator,
    Kino Lorber, Vinegar Syndrome, 88 Films, Shout/Scream Factory, Eureka/Masters of Cinema,
    Second Sight, StudioCanal, Mondo, Best Buy/Walmart/Target exclusives, premium 4K UHD,
    Miyazaki/Ghibli steelbooks, MCU steelbooks, LOTR steelbooks, Star Wars steelbooks,
    Disney Vault steelbooks, and other boutique labels."""

    # Format: (label, title, format, edition, rarity_tier, price_eur)
    # rarity_tier: grail (>150), high (80-150), mid (40-80), standard (<40)

    discs = [
        # ── Criterion Collection ─────────────────────────────────────────
        ("Criterion", "Seven Samurai", "Blu-ray", "Criterion #2", "standard", 28),
        ("Criterion", "Stalker", "Blu-ray", "Criterion #888", "standard", 30),
        ("Criterion", "In the Mood for Love", "Blu-ray", "Criterion #4K", "standard", 35),
        ("Criterion", "Mulholland Dr.", "Blu-ray", "Criterion #779", "standard", 25),
        ("Criterion", "Parasite", "4K UHD", "Criterion 4K", "standard", 38),
        ("Criterion", "Do the Right Thing", "Blu-ray", "Criterion #97", "standard", 22),
        ("Criterion", "Paris, Texas", "Blu-ray", "Criterion #634", "standard", 28),
        ("Criterion", "Eraserhead", "Blu-ray", "Criterion #725", "standard", 35),
        ("Criterion", "The Before Trilogy", "Blu-ray", "Criterion Box Set", "mid", 55),
        ("Criterion", "World of Wong Kar Wai", "Blu-ray", "Criterion Box Set", "high", 90),
        ("Criterion", "Citizen Kane", "4K UHD", "Criterion 4K", "mid", 40),
        ("Criterion", "8 1/2", "Blu-ray", "Criterion #140", "standard", 26),
        ("Criterion", "The 400 Blows", "Blu-ray", "Criterion #5", "standard", 24),
        ("Criterion", "Persona", "Blu-ray", "Criterion #701", "standard", 28),
        ("Criterion", "Tampopo", "Blu-ray", "Criterion #960", "standard", 30),
        ("Criterion", "Menace II Society", "4K UHD", "Criterion 4K", "standard", 38),
        ("Criterion", "All That Jazz", "Blu-ray", "Criterion #1069", "standard", 26),
        ("Criterion", "Close-Up", "Blu-ray", "Criterion #590", "standard", 32),
        ("Criterion", "The Complete Jacques Tati", "Blu-ray", "Criterion Box Set", "high", 110),
        ("Criterion", "Godzilla: The Showa-Era Films", "Blu-ray", "Criterion Box Set", "high", 130),

        # ── Arrow Video ──────────────────────────────────────────────────
        ("Arrow Video", "Suspiria", "4K UHD", "Arrow Limited", "mid", 45),
        ("Arrow Video", "Re-Animator", "Blu-ray", "Arrow Limited", "standard", 35),
        ("Arrow Video", "The Thing", "4K UHD", "Arrow Limited", "mid", 50),
        ("Arrow Video", "Donnie Darko", "4K UHD", "Arrow Limited", "mid", 40),
        ("Arrow Video", "Deep Red", "4K UHD", "Arrow Limited", "mid", 42),
        ("Arrow Video", "Battle Royale", "Blu-ray", "Arrow Limited", "standard", 38),
        ("Arrow Video", "Hellraiser Trilogy", "Blu-ray", "Arrow Box Set", "high", 80),
        ("Arrow Video", "Oldboy", "4K UHD", "Arrow Limited", "mid", 45),
        ("Arrow Video", "Tenebrae", "4K UHD", "Arrow Limited", "mid", 42),
        ("Arrow Video", "The Bird with the Crystal Plumage", "4K UHD", "Arrow Limited", "mid", 44),
        ("Arrow Video", "Demons / Demons 2", "Blu-ray", "Arrow Limited", "mid", 40),
        ("Arrow Video", "Blood and Black Lace", "Blu-ray", "Arrow Limited", "standard", 38),
        ("Arrow Video", "Robocop", "4K UHD", "Arrow Limited", "mid", 48),
        ("Arrow Video", "An American Werewolf in London", "4K UHD", "Arrow Limited", "mid", 55),
        ("Arrow Video", "Flash Gordon", "4K UHD", "Arrow Limited", "mid", 42),

        # ── Indicator / Powerhouse Films ─────────────────────────────────
        ("Indicator", "Columbia Noir Collection Vol 1", "Blu-ray", "Indicator Box Set", "high", 85),
        ("Indicator", "Columbia Noir Collection Vol 2", "Blu-ray", "Indicator Box Set", "high", 85),
        ("Indicator", "Hammer Volume One: Fear Warning!", "Blu-ray", "Indicator Box Set", "high", 95),
        ("Indicator", "Hammer Volume Two: Criminal Intent", "Blu-ray", "Indicator Box Set", "high", 95),
        ("Indicator", "The Alastair Sim Collection", "Blu-ray", "Indicator Box Set", "high", 90),
        ("Indicator", "Samuel Fuller at Columbia", "Blu-ray", "Indicator Box Set", "high", 88),

        # ── Kino Lorber ──────────────────────────────────────────────────
        ("Kino Lorber", "The Cabinet of Dr. Caligari", "4K UHD", "KL Studio Classics", "standard", 34),
        ("Kino Lorber", "Nosferatu (1922)", "4K UHD", "KL Studio Classics", "standard", 36),
        ("Kino Lorber", "Metropolis", "4K UHD", "KL Studio Classics", "standard", 38),
        ("Kino Lorber", "Army of Shadows", "Blu-ray", "KL Studio Classics", "standard", 28),
        ("Kino Lorber", "Le Samourai", "4K UHD", "KL Studio Classics", "standard", 36),

        # ── Vinegar Syndrome ─────────────────────────────────────────────
        ("Vinegar Syndrome", "Tammy and the T-Rex", "4K UHD", "VS Limited", "mid", 40),
        ("Vinegar Syndrome", "Psycho Goreman", "4K UHD", "VS Limited", "standard", 35),
        ("Vinegar Syndrome", "Blood Rage", "Blu-ray", "VS Limited", "standard", 30),
        ("Vinegar Syndrome", "Slaughter High", "Blu-ray", "VS Limited", "standard", 28),
        ("Vinegar Syndrome", "The Mutilator", "4K UHD", "VS Limited", "standard", 36),
        ("Vinegar Syndrome", "Killer Workout", "Blu-ray", "VS Limited", "standard", 26),
        ("Vinegar Syndrome", "Nightmare Beach", "Blu-ray", "VS Limited", "standard", 28),
        ("Vinegar Syndrome", "Pieces", "4K UHD", "VS Limited", "mid", 40),

        # ── 88 Films ─────────────────────────────────────────────────────
        ("88 Films", "Italian Horror Collection", "Blu-ray", "88 Films Box Set", "high", 100),
        ("88 Films", "Shocking Dark", "Blu-ray", "88 Films Limited", "standard", 24),
        ("88 Films", "Killer Crocodile 1 & 2", "Blu-ray", "88 Films Limited", "standard", 26),
        ("88 Films", "The House by the Cemetery", "4K UHD", "88 Films Limited", "standard", 38),
        ("88 Films", "Robowar", "Blu-ray", "88 Films Limited", "standard", 22),

        # ── Shout Factory / Scream Factory ───────────────────────────────
        ("Shout Factory", "The Fog", "4K UHD", "Shout Select", "standard", 35),
        ("Shout Factory", "Escape from New York", "4K UHD", "Shout Select", "standard", 38),
        ("Shout Factory", "They Live", "4K UHD", "Shout Select", "standard", 35),
        ("Scream Factory", "Halloween (1978)", "4K UHD", "Scream Factory Limited", "mid", 42),
        ("Scream Factory", "A Nightmare on Elm Street Collection", "Blu-ray", "Scream Factory Box Set", "high", 85),
        ("Scream Factory", "Child's Play Collection", "Blu-ray", "Scream Factory Box Set", "mid", 55),
        ("Scream Factory", "Phantasm Sphere Collection", "Blu-ray", "Scream Factory Box Set", "high", 80),
        ("Scream Factory", "Creepshow", "4K UHD", "Scream Factory Limited", "mid", 40),

        # ── Eureka / Masters of Cinema ───────────────────────────────────
        ("Eureka", "Buster Keaton: The Saphead", "Blu-ray", "Masters of Cinema", "standard", 30),
        ("Eureka", "Harakiri", "Blu-ray", "Masters of Cinema", "standard", 28),
        ("Eureka", "Rashomon", "Blu-ray", "Masters of Cinema", "standard", 26),
        ("Eureka", "The Human Condition Trilogy", "Blu-ray", "Masters of Cinema Box Set", "high", 80),
        ("Eureka", "Late Spring", "4K UHD", "Masters of Cinema", "standard", 36),

        # ── Second Sight ─────────────────────────────────────────────────
        ("Second Sight", "The Witch", "4K UHD", "Second Sight Limited", "mid", 50),
        ("Second Sight", "The Descent", "4K UHD", "Second Sight Limited", "mid", 48),
        ("Second Sight", "Dog Soldiers", "4K UHD", "Second Sight Limited", "mid", 46),
        ("Second Sight", "Hereditary", "4K UHD", "Second Sight Limited", "mid", 52),
        ("Second Sight", "In Bruges", "4K UHD", "Second Sight Limited", "mid", 50),

        # ── StudioCanal ──────────────────────────────────────────────────
        ("StudioCanal", "Mulholland Drive", "4K UHD", "StudioCanal Collector's", "mid", 45),
        ("StudioCanal", "The Third Man", "4K UHD", "StudioCanal Collector's", "mid", 42),
        ("StudioCanal", "Cinema Paradiso", "4K UHD", "StudioCanal Collector's", "mid", 40),
        ("StudioCanal", "Terminator 2: Judgment Day", "4K UHD", "StudioCanal Collector's", "mid", 44),

        # ── Mondo Steelbooks ─────────────────────────────────────────────
        ("Mondo", "The Iron Giant", "4K UHD", "Mondo Steelbook", "high", 85),
        ("Mondo", "Jurassic Park", "4K UHD", "Mondo Steelbook", "mid", 55),
        ("Mondo", "Alien", "4K UHD", "Mondo Steelbook", "mid", 60),
        ("Mondo", "Drive", "4K UHD", "Mondo Steelbook", "high", 80),

        # ── Best Buy Exclusives ──────────────────────────────────────────
        ("Best Buy Exclusive", "Top Gun: Maverick", "4K UHD", "Best Buy Steelbook", "mid", 38),
        ("Best Buy Exclusive", "The Batman (2022)", "4K UHD", "Best Buy Steelbook", "mid", 36),
        ("Best Buy Exclusive", "Dune: Part Two", "4K UHD", "Best Buy Steelbook", "mid", 40),

        # ── Walmart Exclusives ───────────────────────────────────────────
        ("Walmart Exclusive", "Deadpool & Wolverine", "4K UHD", "Walmart Steelbook", "standard", 34),
        ("Walmart Exclusive", "Barbie", "4K UHD", "Walmart Steelbook", "standard", 30),

        # ── Target Exclusives ────────────────────────────────────────────
        ("Target Exclusive", "Everything Everywhere All at Once", "4K UHD", "Target Steelbook", "mid", 42),
        ("Target Exclusive", "Oppenheimer", "4K UHD", "Target Steelbook", "mid", 40),

        # ── 4K UHD Premium Editions ──────────────────────────────────────
        ("4K UHD", "Blade Runner 2049", "4K UHD", "Limited Collector's", "high", 80),
        ("4K UHD", "2001: A Space Odyssey", "4K UHD", "Titans of Cult", "high", 65),
        ("4K UHD", "The Shining", "4K UHD", "Titans of Cult", "mid", 55),
        ("4K UHD", "Dune (2021)", "4K UHD", "Limited SteelBook", "mid", 40),
        ("4K UHD", "Lawrence of Arabia", "4K UHD", "Columbia Classics Vol 1", "grail", 180),
        ("4K UHD", "Jaws", "4K UHD", "Limited Collector's", "mid", 45),
        ("4K UHD", "The Dark Knight", "4K UHD", "HDZeta Steelbook", "grail", 160),
        ("4K UHD", "Blade Runner: The Final Cut", "4K UHD", "Titans of Cult", "high", 85),
        ("4K UHD", "Interstellar", "4K UHD", "HDZeta Steelbook", "high", 120),
        ("4K UHD", "Mad Max: Fury Road", "4K UHD", "Titans of Cult", "high", 65),
        ("4K UHD", "The Matrix", "4K UHD", "Titans of Cult", "mid", 55),
        ("4K UHD", "Full Metal Jacket", "4K UHD", "Titans of Cult", "mid", 50),

        # ── Steelbooks - Marvel MCU Phase 1-3 ────────────────────────────
        ("Steelbook", "Avengers: Endgame", "4K UHD", "Zavvi Steelbook", "mid", 40),
        ("Steelbook", "Spider-Man: No Way Home", "4K UHD", "Best Buy Steelbook", "mid", 35),
        ("Steelbook", "Black Panther", "4K UHD", "Zavvi Steelbook", "mid", 38),
        ("Steelbook", "Iron Man", "4K UHD", "Zavvi Steelbook", "high", 55),
        ("Steelbook", "Captain America: The Winter Soldier", "4K UHD", "Zavvi Steelbook", "mid", 42),
        ("Steelbook", "Thor: Ragnarok", "4K UHD", "Zavvi Steelbook", "mid", 40),
        ("Steelbook", "Guardians of the Galaxy", "4K UHD", "Zavvi Steelbook", "mid", 44),
        ("Steelbook", "Avengers: Infinity War", "4K UHD", "Zavvi Steelbook", "mid", 42),
        ("Steelbook", "Doctor Strange", "4K UHD", "Zavvi Steelbook", "standard", 36),

        # ── Steelbooks - Nolan ───────────────────────────────────────────
        ("Steelbook", "Inception", "4K UHD", "Manta Lab Steelbook", "high", 100),
        ("Steelbook", "Oppenheimer", "4K UHD", "Zavvi Steelbook", "mid", 45),
        ("Steelbook", "Tenet", "4K UHD", "Zavvi Steelbook", "mid", 42),
        ("Steelbook", "Dunkirk", "4K UHD", "Manta Lab Steelbook", "high", 85),

        # ── Steelbooks - Miyazaki / Studio Ghibli ────────────────────────
        ("Steelbook", "Spirited Away", "Blu-ray", "Zavvi Steelbook", "high", 60),
        ("Steelbook", "Princess Mononoke", "Blu-ray", "Zavvi Steelbook", "mid", 50),
        ("Steelbook", "My Neighbor Totoro", "Blu-ray", "Zavvi Steelbook", "mid", 48),
        ("Steelbook", "Howl's Moving Castle", "Blu-ray", "Zavvi Steelbook", "mid", 55),
        ("Steelbook", "Nausicaa of the Valley of the Wind", "Blu-ray", "Zavvi Steelbook", "mid", 52),
        ("Steelbook", "Castle in the Sky", "Blu-ray", "Zavvi Steelbook", "mid", 48),
        ("Steelbook", "Kiki's Delivery Service", "Blu-ray", "Zavvi Steelbook", "mid", 46),
        ("Steelbook", "Porco Rosso", "Blu-ray", "Zavvi Steelbook", "mid", 44),

        # ── Steelbooks - Lord of the Rings ───────────────────────────────
        ("Steelbook", "LOTR: Fellowship of the Ring Extended", "4K UHD", "Zavvi Steelbook", "high", 85),
        ("Steelbook", "LOTR: The Two Towers Extended", "4K UHD", "Zavvi Steelbook", "high", 85),
        ("Steelbook", "LOTR: Return of the King Extended", "4K UHD", "Zavvi Steelbook", "high", 90),
        ("Steelbook", "LOTR Extended Trilogy", "4K UHD", "HDZeta Box Set", "grail", 280),

        # ── Steelbooks - Star Wars ───────────────────────────────────────
        ("Steelbook", "Star Wars: A New Hope", "4K UHD", "Zavvi Steelbook", "high", 65),
        ("Steelbook", "The Empire Strikes Back", "4K UHD", "Zavvi Steelbook", "high", 65),
        ("Steelbook", "Return of the Jedi", "4K UHD", "Zavvi Steelbook", "high", 60),
        ("Steelbook", "Star Wars Original Trilogy", "4K UHD", "Zavvi Box Set", "grail", 180),
        ("Steelbook", "Rogue One: A Star Wars Story", "4K UHD", "Zavvi Steelbook", "mid", 50),

        # ── Disney Vault Steelbooks ──────────────────────────────────────
        ("Steelbook", "The Lion King (1994)", "4K UHD", "Zavvi Steelbook", "mid", 55),
        ("Steelbook", "Aladdin (1992)", "4K UHD", "Zavvi Steelbook", "mid", 50),
        ("Steelbook", "Beauty and the Beast (1991)", "4K UHD", "Zavvi Steelbook", "mid", 52),
        ("Steelbook", "The Little Mermaid (1989)", "4K UHD", "Zavvi Steelbook", "mid", 48),
        ("Steelbook", "Fantasia", "Blu-ray", "Zavvi Steelbook", "high", 65),
        ("Steelbook", "Bambi", "Blu-ray", "Zavvi Steelbook", "high", 60),
        ("Steelbook", "Snow White and the Seven Dwarfs", "4K UHD", "Zavvi Steelbook", "high", 68),

        # ── Other Boutique Label Box Sets ────────────────────────────────
        ("Imprint", "Film Noir Collection", "Blu-ray", "Imprint Box Set", "high", 120),
        ("Severin", "Fulci Box Set", "Blu-ray", "Severin Limited", "grail", 200),
        ("Severin", "Coffin Joe Trilogy", "Blu-ray", "Severin Limited", "high", 85),
    ]

    catalog = []
    for label, title, fmt, edition, tier, price in discs:
        catalog.append({
            "label": label,
            "title": title,
            "format": fmt,
            "edition": edition,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    label = item["label"]
    title = item["title"]
    fmt = item["format"]
    edition = item["edition"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{label}-{title}-{edition}"),
        title=f"{title} ({fmt})",
        set_code=label.lower().replace(" ", "-"),
        brand=label,
        rarity=item["rarity_tier"].title(),
        notes=f"{label} | {edition} | {fmt}",
        attributes_json={
            "label": label,
            "format": fmt,
            "edition": edition,
            "is_steelbook": "steelbook" in edition.lower(),
            "is_4k": fmt == "4K UHD",
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]
    is_limited = any(kw in item["edition"].lower() for kw in ["limited", "steelbook", "box set"])
    is_4k = item["format"] == "4K UHD"

    return PriceObservation(
        features={
            "condition_score": 0.9,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": 0.85 if is_limited else 0.4,
            "is_steelbook": 1.0 if "steelbook" in item["edition"].lower() else 0.0,
            "is_4k": 1.0 if is_4k else 0.0,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Blu-ray Steelbook catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Blu-ray Steelbook Import ===")

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

    logger.info(f"\n=== Blu-ray Steelbook Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
