"""
Import anime OST vinyl records catalog.

Layer 1 (Catalog):  Curated anime vinyl releases → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers 70+ items across labels and eras:
- Tiger Lab Vinyl releases (Cowboy Bebop, Samurai Champloo, FLCL)
- Milan Records anime vinyl (Studio Ghibli: Spirited Away, Mononoke, Totoro, etc.)
- Data Discs (game/anime crossover: Jet Set Radio, Shenmue, NieR, etc.)
- Mondo (Akira, GiTS, Dragon Ball Z, Attack on Titan, Demon Slayer, etc.)
- Aniplex / Sony Music Japan (Demon Slayer, SAO, Fate, Madoka Magica, etc.)
- King Records / Japanese labels (classic anime: Dragon Ball, Sailor Moon, Yu Yu Hakusho)
- Crunchyroll / new labels (Jujutsu Kaisen, Chainsaw Man, Spy x Family, etc.)
- Classic/vintage anime OST (Lupin III, Yamato, Gundam, Bubblegum Crisis, etc.)
- Japanese pressings: King Records, Flying Dog, Tokuma, Nippon Columbia
- Event-exclusive color variants (anime expos, RSD, numbered pressings)
- City pop / anime crossover vinyl

Usage:
    python -m pipelines.import_anime_ost_vinyl [--dry-run]
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

CATEGORY = "anime_ost_vinyl"


def get_curated_catalog() -> list[dict]:
    """Curated anime OST vinyl records catalog — 80+ items across 12 label groups."""

    # (label, title, franchise, pressing, variant, rarity_tier, price_eur)
    # rarity_tier: grail (>100), high (50-100), mid (25-50), standard (<25)

    items = [
        # ── Tiger Lab Vinyl ──────────────────────────────────────────────
        ("Tiger Lab Vinyl", "Cowboy Bebop OST 1 (Seatbelts)", "Cowboy Bebop", "US Pressing", "Black", "mid", 40),
        ("Tiger Lab Vinyl", "Cowboy Bebop OST 1 (Seatbelts)", "Cowboy Bebop", "US Pressing", "Red Translucent", "high", 70),
        ("Tiger Lab Vinyl", "Cowboy Bebop Vitaminless", "Cowboy Bebop", "US Pressing", "Black", "mid", 38),
        ("Tiger Lab Vinyl", "Cowboy Bebop Blue", "Cowboy Bebop", "US Pressing", "Blue Translucent", "high", 65),
        ("Tiger Lab Vinyl", "Samurai Champloo: The Way of the Samurai", "Samurai Champloo", "US Pressing", "Black", "mid", 35),
        ("Tiger Lab Vinyl", "Samurai Champloo: The Way of the Samurai", "Samurai Champloo", "US Pressing", "Red/White Splatter", "high", 80),
        ("Tiger Lab Vinyl", "Samurai Champloo: Departure", "Samurai Champloo", "US Pressing", "Black", "mid", 38),
        ("Tiger Lab Vinyl", "Samurai Champloo: Impression", "Samurai Champloo", "US Pressing", "Black", "mid", 38),

        # ── Milan Records – Studio Ghibli ────────────────────────────────
        ("Milan Records", "Spirited Away Soundtrack (Joe Hisaishi)", "Spirited Away", "EU/US Pressing", "Black", "mid", 35),
        ("Milan Records", "Princess Mononoke Soundtrack", "Princess Mononoke", "EU/US Pressing", "Black", "mid", 32),
        ("Milan Records", "My Neighbor Totoro Image Album", "My Neighbor Totoro", "EU/US Pressing", "Black", "mid", 30),
        ("Milan Records", "Howl's Moving Castle Soundtrack", "Howl's Moving Castle", "EU/US Pressing", "Black", "mid", 30),
        ("Milan Records", "Nausicaa Soundtrack", "Nausicaa", "EU/US Pressing", "Black", "mid", 35),
        ("Milan Records", "Castle in the Sky Soundtrack", "Castle in the Sky", "EU/US Pressing", "Black", "mid", 30),
        ("Milan Records", "Kiki's Delivery Service Soundtrack", "Kiki's Delivery Service", "EU/US Pressing", "Black", "mid", 30),
        ("Milan Records", "Laputa: Castle in the Sky Image Album", "Castle in the Sky", "EU/US Pressing", "Black", "mid", 32),
        ("Milan Records", "Ponyo on the Cliff Soundtrack", "Ponyo", "EU/US Pressing", "Black", "mid", 28),
        ("Milan Records", "The Wind Rises Soundtrack", "The Wind Rises", "EU/US Pressing", "Black", "mid", 30),

        # ── Japanese pressings – King Records, Flying Dog, Tokuma ────────
        ("King Records", "Macross Frontier Vocal Collection (2LP)", "Macross Frontier", "Japanese Pressing", "Black", "high", 75),
        ("Flying Dog", "Cowboy Bebop OST (Original Japanese)", "Cowboy Bebop", "Japanese Pressing", "Black", "grail", 130),
        ("King Records", "Evangelion Original Soundtrack (2LP)", "Evangelion", "Japanese Pressing", "Black", "high", 85),
        ("Tokuma Japan", "Nausicaa OST (Original 1984 Pressing)", "Nausicaa", "Japanese OG Pressing", "Black", "grail", 150),
        ("King Records", "Ghost in the Shell OST (Kenji Kawai)", "Ghost in the Shell", "Japanese Pressing", "Black", "high", 95),
        ("Flying Dog", "Macross Plus OST (Yoko Kanno)", "Macross Plus", "Japanese Pressing", "Black", "high", 80),

        # ── King Records / Japanese Labels (additional) ──────────────────
        ("King Records", "Dragon Ball Z: Cha-La Head-Cha-La (7\" Single)", "Dragon Ball Z", "Japanese OG Pressing", "Black", "high", 55),
        ("Columbia Japan", "Sailor Moon Original Soundtrack (2LP)", "Sailor Moon", "Japanese OG Pressing", "Black", "high", 75),
        ("Victor", "Yu Yu Hakusho Original Soundtrack", "Yu Yu Hakusho", "Japanese OG Pressing", "Black", "high", 65),
        ("Aniplex", "Rurouni Kenshin Original Soundtrack", "Rurouni Kenshin", "Japanese Pressing", "Black", "high", 60),
        ("Sunrise Music", "Inuyasha Original Soundtrack", "Inuyasha", "Japanese Pressing", "Black", "high", 55),
        ("Kitty Records", "Ranma 1/2 Original Soundtrack", "Ranma 1/2", "Japanese OG Pressing", "Black", "high", 50),

        # ── Event-exclusive color variants (original) ────────────────────
        ("Mondo", "Akira Symphonic Suite (2LP)", "Akira", "Event Exclusive", "Tetsuo Splatter", "grail", 140),
        ("Tiger Lab Vinyl", "Cowboy Bebop OST 1 (Record Store Day)", "Cowboy Bebop", "RSD Exclusive", "Gold", "grail", 110),
        ("Milan Records", "Spirited Away (Anime Expo Exclusive)", "Spirited Away", "Event Exclusive", "Clear Blue", "grail", 120),
        ("Mondo", "Ghost in the Shell OST (Deluxe)", "Ghost in the Shell", "Event Exclusive", "Cyber Green Marble", "grail", 150),

        # ── Event Exclusive / Limited Color Variants (expanded) ──────────
        ("Tiger Lab Vinyl", "Samurai Champloo: The Way of the Samurai (RSD)", "Samurai Champloo", "RSD Exclusive", "Cherry Blossom Pink", "grail", 115),
        ("Milan Records", "Princess Mononoke (Anime NYC Exclusive)", "Princess Mononoke", "Event Exclusive", "Forest Green Marble", "grail", 125),
        ("Mondo", "Akira OST (Numbered /500)", "Akira", "Event Exclusive", "Picture Disc", "grail", 160),
        ("Tiger Lab Vinyl", "FLCL OST (Anime Expo Exclusive)", "FLCL", "Event Exclusive", "Orange Splatter", "grail", 105),
        ("Data Discs", "Jet Set Radio OST (Crunchyroll Expo Exclusive)", "Jet Set Radio", "Event Exclusive", "Clear Yellow", "grail", 110),
        ("Mondo", "Dragon Ball Z: Fusion Reborn (RSD)", "Dragon Ball Z", "RSD Exclusive", "Fusion Splatter", "grail", 130),
        ("Aniplex", "Demon Slayer OST (AnimeJapan Exclusive)", "Demon Slayer", "Event Exclusive", "Flame Red/Orange Splatter", "grail", 140),
        ("Crunchyroll Records", "Jujutsu Kaisen OST (Numbered /1000)", "Jujutsu Kaisen", "Event Exclusive", "Cursed Purple Marble", "grail", 120),

        # ── City pop / anime crossover vinyl ─────────────────────────────
        ("Nippon Columbia", "Kimagure Orange Road: Singing Heart", "Kimagure Orange Road", "Japanese OG Pressing", "Black", "high", 65),
        ("Canyon Records", "Dirty Pair Original Soundtrack", "Dirty Pair", "Japanese OG Pressing", "Black", "high", 55),
        ("Victor", "Urusei Yatsura: Music Capsule", "Urusei Yatsura", "Japanese OG Pressing", "Black", "high", 60),
        ("King Records", "Megazone 23 Soundtrack", "Megazone 23", "Japanese OG Pressing", "Black", "high", 70),
        ("Canyon Records", "City Hunter OST (Get Wild)", "City Hunter", "Japanese OG Pressing", "Black", "high", 55),

        # ── Key titles – modern pressings ────────────────────────────────
        ("Mondo", "Akira OST (Geinoh Yamashirogumi)", "Akira", "Reissue", "Black", "mid", 45),
        ("Milan Records", "Your Name OST (RADWIMPS)", "Your Name", "EU Pressing", "Black", "mid", 35),
        ("Tiger Lab Vinyl", "FLCL OST (The Pillows)", "FLCL", "US Pressing", "Black", "mid", 40),

        # ── Data Discs (game/anime crossover) ────────────────────────────
        ("Data Discs", "Streets of Rage 2 OST (Yuzo Koshiro)", "Streets of Rage", "EU Pressing", "Red Translucent", "high", 55),
        ("Data Discs", "Shenmue OST (2LP)", "Shenmue", "EU Pressing", "Blue Translucent", "high", 60),
        ("Data Discs", "Sonic the Hedgehog 1&2 OST", "Sonic the Hedgehog", "EU Pressing", "Blue", "mid", 45),
        ("Data Discs", "Panzer Dragoon OST", "Panzer Dragoon", "EU Pressing", "Clear", "high", 55),
        ("Data Discs", "Jet Set Radio OST (2LP)", "Jet Set Radio", "EU Pressing", "Green Translucent", "high", 65),
        ("Data Discs", "Streets of Rage 2 OST (Yuzo Koshiro)", "Streets of Rage", "EU Pressing", "Black", "mid", 40),
        ("Data Discs", "Shenmue OST (2LP)", "Shenmue", "EU Pressing", "Black", "mid", 42),
        ("Data Discs", "Sonic the Hedgehog 1&2 OST", "Sonic the Hedgehog", "EU Pressing", "Classic Gold", "high", 60),
        ("Square Enix Music", "NieR: Automata Vinyl Box Set (4LP)", "NieR: Automata", "Japanese Pressing", "Black", "grail", 180),
        ("Square Enix Music", "NieR: Automata OST (Weight of the World)", "NieR: Automata", "EU Pressing", "White", "high", 65),

        # ── Mondo (expanded beyond Akira/GiTS) ──────────────────────────
        ("Mondo", "Dragon Ball Z: Fusion Reborn OST", "Dragon Ball Z", "US Pressing", "Black", "mid", 38),
        ("Mondo", "My Hero Academia OST (Yuki Hayashi)", "My Hero Academia", "US Pressing", "Red/White/Blue Tricolor", "high", 55),
        ("Mondo", "Spirited Away Soundtrack (Alternate Art)", "Spirited Away", "US Pressing", "Clear Blue", "high", 60),
        ("Mondo", "Attack on Titan Season 1 OST (Hiroyuki Sawano)", "Attack on Titan", "US Pressing", "Crimson Red", "high", 65),
        ("Mondo", "Demon Slayer: Mugen Train OST", "Demon Slayer", "US Pressing", "Flame Orange", "high", 55),
        ("Mondo", "One Punch Man OST (Makoto Miyazaki)", "One Punch Man", "US Pressing", "Yellow", "mid", 42),

        # ── Aniplex / Sony Music Japan ───────────────────────────────────
        ("Aniplex", "Demon Slayer OST (Yuki Kajiura / Go Shiina)", "Demon Slayer", "Japanese Pressing", "Black", "high", 70),
        ("Aniplex", "Sword Art Online OST (Yuki Kajiura)", "Sword Art Online", "Japanese Pressing", "Black", "high", 60),
        ("Aniplex", "Fate/Stay Night: Unlimited Blade Works OST", "Fate/Stay Night", "Japanese Pressing", "Black", "high", 65),
        ("Aniplex", "Madoka Magica OST (Yuki Kajiura)", "Madoka Magica", "Japanese Pressing", "Black", "high", 75),
        ("Aniplex", "Monogatari Series OST (Satoru Kosaki)", "Monogatari", "Japanese Pressing", "Black", "high", 70),
        ("Aniplex", "Your Lie in April OST (Masaru Yokoyama)", "Your Lie in April", "Japanese Pressing", "Black", "high", 55),
        ("Aniplex", "Fullmetal Alchemist: Brotherhood OST (Akira Senju)", "Fullmetal Alchemist", "Japanese Pressing", "Black", "high", 80),
        ("Sony Music Japan", "Demon Slayer OST (2LP Deluxe)", "Demon Slayer", "Japanese Pressing", "Red/Black Split", "grail", 110),

        # ── Crunchyroll / New Labels ─────────────────────────────────────
        ("Crunchyroll Records", "Jujutsu Kaisen OST (Hiroaki Tsutsumi)", "Jujutsu Kaisen", "US Pressing", "Black", "mid", 35),
        ("Crunchyroll Records", "Chainsaw Man OST (Kensuke Ushio)", "Chainsaw Man", "US Pressing", "Blood Red", "mid", 38),
        ("Crunchyroll Records", "Spy x Family OST (K)NoW_NAME", "Spy x Family", "US Pressing", "Pink", "standard", 24),
        ("Crunchyroll Records", "Bocchi the Rock! OST", "Bocchi the Rock!", "US Pressing", "Pink Splatter", "mid", 32),
        ("Crunchyroll Records", "Vinland Saga OST (Yutaka Yamada)", "Vinland Saga", "US Pressing", "Black", "mid", 30),

        # ── Classic / Vintage Anime OST ──────────────────────────────────
        ("Nippon Columbia", "Lupin III '77 Original Soundtrack (Yuji Ohno)", "Lupin III", "Japanese OG Pressing", "Black", "grail", 120),
        ("Nippon Columbia", "Space Battleship Yamato OST (1974)", "Space Battleship Yamato", "Japanese OG Pressing", "Black", "grail", 140),
        ("King Records", "Mobile Suit Gundam OST (Takeo Watanabe)", "Mobile Suit Gundam", "Japanese OG Pressing", "Black", "grail", 130),
        ("Invitation", "Akira OST (Geinoh Yamashirogumi) Original Japan", "Akira", "Japanese OG Pressing", "Black", "grail", 200),
        ("Youmex", "Bubblegum Crisis OST", "Bubblegum Crisis", "Japanese OG Pressing", "Black", "high", 85),
        ("Avex Trax", "Initial D: Super Eurobeat Selection", "Initial D", "Japanese OG Pressing", "Black", "high", 75),
        ("Columbia Japan", "Dragon Ball OST (Shunsuke Kikuchi)", "Dragon Ball", "Japanese OG Pressing", "Black", "grail", 110),
        ("Columbia Japan", "Saint Seiya Original Soundtrack", "Saint Seiya", "Japanese OG Pressing", "Black", "high", 90),
    ]

    catalog = []
    for label, title, franchise, pressing, variant, tier, price in items:
        catalog.append({
            "label": label,
            "title": title,
            "franchise": franchise,
            "pressing": pressing,
            "variant": variant,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    label = item["label"]
    title = item["title"]
    franchise = item["franchise"]
    pressing = item["pressing"]
    variant = item["variant"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{label}-{title}-{variant}"),
        title=f"{title} ({variant})",
        set_code=slugify(label),
        brand=label,
        rarity=item["rarity_tier"].title(),
        notes=f"{label} | {franchise} | {pressing} | {variant}",
        attributes_json={
            "label": label,
            "franchise": franchise,
            "pressing": pressing,
            "variant": variant,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    pressing = item["pressing"]
    edition_scores = {
        "Japanese OG Pressing": 0.95,
        "Japanese Pressing": 0.80,
        "Event Exclusive": 0.90,
        "RSD Exclusive": 0.85,
        "US Pressing": 0.50,
        "EU/US Pressing": 0.45,
        "EU Pressing": 0.45,
        "Reissue": 0.35,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_scores.get(pressing, 0.5),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import anime OST vinyl catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Anime OST Vinyl Import ===")

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

    logger.info(f"\n=== Anime OST Vinyl Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
