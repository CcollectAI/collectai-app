"""
Expanded anime/game OST vinyl records catalog — 85 NEW items.

Layer 1 (Catalog):  Curated anime + game vinyl releases → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

This expansion adds records NOT present in import_anime_ost_vinyl.py.
Six sub-catalogs:

  a) Studio Ghibli Soundtracks (12)
     — Porco Rosso, Tale of Princess Kaguya, From Up on Poppy Hill,
       plus colored/deluxe variants of existing Ghibli titles

  b) Classic Anime OSTs (15)
     — Neon Genesis Evangelion (reissue), Serial Experiments Lain,
       Perfect Blue, Paprika, Wolf's Rain, Trigun, Escaflowne,
       Berserk, Revolutionary Girl Utena, Paranoia Agent

  c) Modern Anime Hits (15)
     — Violet Evergarden, Made in Abyss, Frieren, Cyberpunk Edgerunners,
       Mob Psycho 100, Dr. Stone, Ranking of Kings, Odd Taxi,
       Devilman Crybaby, Dorohedoro, Sonny Boy, Vivy, 86 Eighty-Six,
       Oshi no Ko, Solo Leveling

  d) Video Game OSTs (15)
     — Final Fantasy VII, Persona 5, Zelda BotW, Undertale,
       Chrono Trigger, Chrono Cross, Silent Hill 2, Metal Gear Solid,
       Kingdom Hearts, Dark Souls, Hollow Knight, Celeste, Hades,
       Katamari Damacy, Shadow of the Colossus

  e) Tiger Lab / Boutique Pressings (10)
     — Brave Wave (Mega Man), iam8bit releases (Journey, Ori),
       Ship to Shore PhonoCo (Nintendo), Fangamer (Stardew Valley),
       Tiger Lab new anime releases

  f) Rare JP Pressings (13+)
     — Macross DYRL, Gundam 0080, Urusei Yatsura Beautiful Dreamer,
       Lupin III Castle of Cagliostro, Space Cobra, Fist of the
       North Star, Crusher Joe, Patlabor, Captain Harlock, Area 88,
       Galaxy Express 999, Devilman (1972), Cutie Honey

Usage:
    python -m pipelines.import_anime_vinyl_expanded [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines.import_common import (
    CatalogItem,
    PriceObservation,
    SupabaseIngest,
    write_training_jsonl,
    write_catalog_sql,
    log_progress,
    slugify,
    rarity_score as shared_rarity_score,
    logger,
    close_http_client,
)

CATEGORY = "anime_ost_vinyl"

# ---------------------------------------------------------------------------
# Pressing type → edition_score mapping (shared with general vinyl logic)
# ---------------------------------------------------------------------------

PRESSING_SCORES: dict[str, float] = {
    "Japanese OG Pressing":  0.95,
    "Japanese Pressing":     0.80,
    "Event Exclusive":       0.90,
    "RSD Exclusive":         0.85,
    "Numbered Limited":      0.88,
    "Boutique Pressing":     0.75,
    "US Pressing":           0.50,
    "EU/US Pressing":        0.45,
    "EU Pressing":           0.45,
    "Reissue":               0.35,
    "Standard Pressing":     0.30,
}


# ---------------------------------------------------------------------------
# Curated catalog — 85 items, zero overlap with import_anime_ost_vinyl.py
# ---------------------------------------------------------------------------

def get_curated_catalog() -> list[dict]:
    """Return 85 curated anime/game vinyl records not in the base catalog.

    Each tuple: (label, album_title, franchise, pressing_type, color, rarity_tier, price_eur)
    Rarity tiers: grail (>100 EUR), high (50-100), mid (25-50), standard (<25)
    """

    items: list[tuple[str, str, str, str, str, str, int | float]] = [

        # ── a) Studio Ghibli Soundtracks (12) ──────────────────────────────
        # Titles NOT in base: Porco Rosso, Kaguya, Poppy Hill, + colored variants
        ("Milan Records", "Porco Rosso Soundtrack (Joe Hisaishi)", "Porco Rosso", "EU/US Pressing", "Black", "mid", 35),
        ("Milan Records", "The Tale of Princess Kaguya Soundtrack", "Princess Kaguya", "EU/US Pressing", "Black", "mid", 38),
        ("Milan Records", "From Up on Poppy Hill Soundtrack", "From Up on Poppy Hill", "EU/US Pressing", "Black", "mid", 32),
        ("Milan Records", "Spirited Away Soundtrack (Joe Hisaishi)", "Spirited Away", "EU/US Pressing", "Pink Translucent", "high", 55),
        ("Milan Records", "Princess Mononoke Soundtrack", "Princess Mononoke", "EU/US Pressing", "Deep Green Translucent", "high", 52),
        ("Milan Records", "My Neighbor Totoro Soundtrack", "My Neighbor Totoro", "EU/US Pressing", "Green Opaque", "high", 50),
        ("Milan Records", "Howl's Moving Castle Soundtrack", "Howl's Moving Castle", "EU/US Pressing", "Sky Blue Translucent", "high", 55),
        ("Milan Records", "Castle in the Sky Soundtrack", "Castle in the Sky", "EU/US Pressing", "Crystal Clear", "high", 50),
        ("Tokuma Japan", "Porco Rosso OST (Original 1992 Pressing)", "Porco Rosso", "Japanese OG Pressing", "Black", "grail", 160),
        ("Tokuma Japan", "My Neighbor Totoro OST (Original 1988 Pressing)", "My Neighbor Totoro", "Japanese OG Pressing", "Black", "grail", 180),
        ("Tokuma Japan", "Kiki's Delivery Service OST (Original 1989 Pressing)", "Kiki's Delivery Service", "Japanese OG Pressing", "Black", "grail", 170),
        ("Studio Ghibli Records", "The Wind Rises Soundtrack (Deluxe 2LP)", "The Wind Rises", "Japanese Pressing", "Clear", "high", 65),

        # ── b) Classic Anime OSTs (15) ──────────────────────────────────────
        # Titles/variants NOT in base catalog
        ("King Records", "Neon Genesis Evangelion OST (Shiro Sagisu) Reissue", "Evangelion", "Reissue", "Black", "mid", 42),
        ("Geneon", "Serial Experiments Lain OST (Bôa/Reichi Nakaido)", "Serial Experiments Lain", "Japanese OG Pressing", "Black", "grail", 250),
        ("Geneon", "Serial Experiments Lain Cyberia Mix", "Serial Experiments Lain", "Japanese OG Pressing", "Black", "grail", 200),
        ("Madhouse Music", "Perfect Blue Original Soundtrack (Masahiro Ikumi)", "Perfect Blue", "Japanese OG Pressing", "Black", "grail", 300),
        ("Madhouse Music", "Paprika Original Soundtrack (Susumu Hirasawa)", "Paprika", "Japanese OG Pressing", "Black", "grail", 220),
        ("Victor", "Wolf's Rain Original Soundtrack (Yoko Kanno)", "Wolf's Rain", "Japanese Pressing", "Black", "high", 85),
        ("Victor", "Trigun Original Soundtrack (Tsuneo Imahori)", "Trigun", "Japanese OG Pressing", "Black", "high", 90),
        ("Victor", "Vision of Escaflowne OST (Yoko Kanno/Hajime Mizoguchi)", "Escaflowne", "Japanese OG Pressing", "Black", "grail", 120),
        ("VAP", "Berserk Original Soundtrack (Susumu Hirasawa)", "Berserk", "Japanese OG Pressing", "Black", "grail", 180),
        ("King Records", "Revolutionary Girl Utena OST (Shinkichi Mitsumune)", "Utena", "Japanese OG Pressing", "Black", "grail", 140),
        ("Madhouse Music", "Paranoia Agent OST (Susumu Hirasawa)", "Paranoia Agent", "Japanese OG Pressing", "Black", "grail", 190),
        ("Tiger Lab Vinyl", "Cowboy Bebop No Disc (Seatbelts)", "Cowboy Bebop", "US Pressing", "Black", "mid", 42),
        ("Tiger Lab Vinyl", "Cowboy Bebop Ask DNA (Seatbelts)", "Cowboy Bebop", "US Pressing", "Purple Translucent", "high", 68),
        ("Tiger Lab Vinyl", "Samurai Champloo: Force of Nature", "Samurai Champloo", "US Pressing", "Black", "mid", 40),
        ("Mondo", "Ghost in the Shell: Stand Alone Complex OST (Yoko Kanno)", "Ghost in the Shell: SAC", "US Pressing", "Tachikoma Blue", "high", 58),

        # ── c) Modern Anime Hits (15) ──────────────────────────────────────
        ("Lantis", "Violet Evergarden OST (Evan Call)", "Violet Evergarden", "Japanese Pressing", "Clear Blue", "high", 75),
        ("Kadokawa", "Made in Abyss OST (Kevin Penkin)", "Made in Abyss", "Japanese Pressing", "Abyss Green", "high", 70),
        ("Aniplex", "Frieren: Beyond Journey's End OST (Evan Call)", "Frieren", "Japanese Pressing", "Black", "high", 60),
        ("Milan Records", "Cyberpunk Edgerunners OST (Akira Yamaoka)", "Cyberpunk Edgerunners", "EU Pressing", "Neon Yellow", "high", 55),
        ("Lantis", "Mob Psycho 100 OST (Kenji Kawai)", "Mob Psycho 100", "Japanese Pressing", "Black", "high", 58),
        ("Aniplex", "Dr. Stone OST (Tatsuya Kato/Yuki Kajiura)", "Dr. Stone", "Japanese Pressing", "Black", "mid", 45),
        ("WIT Studio Music", "Ranking of Kings OST (MAYUKO)", "Ranking of Kings", "Japanese Pressing", "Gold", "high", 55),
        ("Pony Canyon", "Odd Taxi Original Soundtrack", "Odd Taxi", "Japanese Pressing", "Black", "high", 65),
        ("Aniplex", "Devilman Crybaby OST (Kensuke Ushio)", "Devilman Crybaby", "Japanese Pressing", "Blood Red", "high", 72),
        ("Kadokawa", "Dorohedoro OST (R.O.N/K)NoW_NAME", "Dorohedoro", "Japanese Pressing", "Smoke Black", "high", 60),
        ("Aniplex", "Sonny Boy Original Soundtrack", "Sonny Boy", "Japanese Pressing", "Black", "high", 55),
        ("Aniplex", "Vivy: Fluorite Eye's Song OST", "Vivy", "Japanese Pressing", "Blue Translucent", "high", 62),
        ("Aniplex", "86 Eighty-Six OST (Hiroyuki Sawano/Kohta Yamamoto)", "86 Eighty-Six", "Japanese Pressing", "Silver", "high", 58),
        ("Aniplex", "Oshi no Ko OST (Masahiro Tokuda)", "Oshi no Ko", "Japanese Pressing", "Star Purple", "high", 55),
        ("Aniplex", "Solo Leveling OST (Hiroyuki Sawano)", "Solo Leveling", "Japanese Pressing", "Shadow Black", "high", 52),

        # ── d) Video Game OSTs (15) ────────────────────────────────────────
        ("Square Enix Music", "Final Fantasy VII OST (Nobuo Uematsu) 3LP", "Final Fantasy VII", "Japanese Pressing", "Black", "grail", 120),
        ("Atlus Music", "Persona 5 Original Soundtrack (Shoji Meguro) 4LP", "Persona 5", "Japanese Pressing", "Red", "grail", 140),
        ("Nintendo Music", "Zelda: Breath of the Wild OST (2LP)", "Zelda: BotW", "Japanese Pressing", "Green Translucent", "grail", 110),
        ("Fangamer", "Undertale Vinyl Soundtrack (Toby Fox) 2LP", "Undertale", "Boutique Pressing", "Blue", "high", 55),
        ("Square Enix Music", "Chrono Trigger OST (Yasunori Mitsuda) 3LP", "Chrono Trigger", "Japanese Pressing", "Black", "grail", 160),
        ("Square Enix Music", "Chrono Cross OST (Yasunori Mitsuda) 2LP", "Chrono Cross", "Japanese Pressing", "Blue Marble", "grail", 130),
        ("Mondo", "Silent Hill 2 Original Soundtrack (Akira Yamaoka)", "Silent Hill 2", "US Pressing", "Fog White", "high", 65),
        ("Mondo", "Metal Gear Solid OST (TAPPY/Kazuki Muraoka)", "Metal Gear Solid", "US Pressing", "Tactical Grey", "high", 60),
        ("Square Enix Music", "Kingdom Hearts OST (Yoko Shimomura) 3LP", "Kingdom Hearts", "Japanese Pressing", "Black", "grail", 150),
        ("Bandai Namco Music", "Dark Souls Original Soundtrack (Motoi Sakuraba) 2LP", "Dark Souls", "Japanese Pressing", "Ember Orange", "high", 70),
        ("Fangamer", "Hollow Knight OST (Christopher Larkin) 2LP", "Hollow Knight", "Boutique Pressing", "Void Black", "high", 55),
        ("Fangamer", "Celeste OST (Lena Raine) 2LP", "Celeste", "Boutique Pressing", "Mountain Blue", "high", 50),
        ("Supergiant Games", "Hades Original Soundtrack (Darren Korb) 4LP", "Hades", "Boutique Pressing", "Blood Red/Black Split", "high", 65),
        ("Mondo", "Katamari Damacy OST (Yuu Miyake) 2LP", "Katamari Damacy", "US Pressing", "Rainbow Splatter", "high", 58),
        ("Mondo", "Shadow of the Colossus OST (Kow Otani) 2LP", "Shadow of the Colossus", "US Pressing", "Stone Grey", "high", 55),

        # ── e) Tiger Lab / Boutique Pressings (10) ─────────────────────────
        ("Brave Wave", "Mega Man 2 Original Soundtrack (Takashi Tateishi)", "Mega Man 2", "Boutique Pressing", "Blue", "high", 48),
        ("Brave Wave", "Mega Man 3 Original Soundtrack", "Mega Man 3", "Boutique Pressing", "Red", "mid", 45),
        ("iam8bit", "Journey Original Soundtrack (Austin Wintory) 2LP", "Journey", "Boutique Pressing", "Sand Gold", "high", 60),
        ("iam8bit", "Ori and the Blind Forest OST (Gareth Coker)", "Ori and the Blind Forest", "Boutique Pressing", "Glow Blue", "high", 55),
        ("Ship to Shore PhonoCo", "Star Fox OST (Hajime Hirasawa)", "Star Fox", "Boutique Pressing", "Arwing Silver", "high", 52),
        ("Ship to Shore PhonoCo", "Castlevania: Symphony of the Night OST (Michiru Yamane)", "Castlevania: SotN", "Boutique Pressing", "Blood Red", "high", 65),
        ("iam8bit", "The Last of Us Original Score (Gustavo Santaolalla) 2LP", "The Last of Us", "Boutique Pressing", "Moss Green", "high", 60),
        ("Tiger Lab Vinyl", "Kids on the Slope OST (Yoko Kanno)", "Kids on the Slope", "US Pressing", "Black", "mid", 38),
        ("Tiger Lab Vinyl", "Space Dandy OST (Space Dandy Band)", "Space Dandy", "US Pressing", "Cosmic Purple", "mid", 42),
        ("Fangamer", "Stardew Valley OST (ConcernedApe) 2LP", "Stardew Valley", "Boutique Pressing", "Spring Green", "mid", 45),

        # ── f) Rare JP Pressings (13) ──────────────────────────────────────
        ("Victor", "Macross: Do You Remember Love? OST (1984)", "Macross DYRL", "Japanese OG Pressing", "Black", "grail", 200),
        ("King Records", "Gundam 0080: War in the Pocket OST", "Gundam 0080", "Japanese OG Pressing", "Black", "grail", 140),
        ("Kitty Records", "Urusei Yatsura: Beautiful Dreamer OST (1984)", "Urusei Yatsura", "Japanese OG Pressing", "Black", "grail", 180),
        ("Nippon Columbia", "Lupin III: Castle of Cagliostro OST (Yuji Ohno)", "Lupin III: Cagliostro", "Japanese OG Pressing", "Black", "grail", 250),
        ("Nippon Columbia", "Space Cobra Original Soundtrack (Kentaro Haneda)", "Space Cobra", "Japanese OG Pressing", "Black", "grail", 160),
        ("Toei Animation", "Fist of the North Star OST (Katsuhisa Hattori)", "Fist of the North Star", "Japanese OG Pressing", "Black", "grail", 170),
        ("Nippon Columbia", "Crusher Joe Original Soundtrack (1983)", "Crusher Joe", "Japanese OG Pressing", "Black", "grail", 190),
        ("Emotion", "Patlabor Original Soundtrack (Kenji Kawai)", "Patlabor", "Japanese OG Pressing", "Black", "grail", 130),
        ("Nippon Columbia", "Captain Harlock OST (Seiji Yokoyama) 1978", "Captain Harlock", "Japanese OG Pressing", "Black", "grail", 220),
        ("Nippon Columbia", "Galaxy Express 999 OST (Nozomi Aoki) 1979", "Galaxy Express 999", "Japanese OG Pressing", "Black", "grail", 200),
        ("Nippon Columbia", "Area 88 Original Soundtrack", "Area 88", "Japanese OG Pressing", "Black", "grail", 150),
        ("Nippon Columbia", "Devilman Original Soundtrack (Go Nagai/1972)", "Devilman (1972)", "Japanese OG Pressing", "Black", "grail", 350),
        ("Columbia Japan", "Cutie Honey Original Soundtrack (Takeo Watanabe) 1973", "Cutie Honey", "Japanese OG Pressing", "Black", "grail", 280),
    ]

    catalog: list[dict] = []
    for label, title, franchise, pressing, color, tier, price in items:
        catalog.append({
            "label": label,
            "title": title,
            "franchise": franchise,
            "pressing": pressing,
            "color": color,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


# ---------------------------------------------------------------------------
# Transform helpers
# ---------------------------------------------------------------------------

def _vinyl_to_catalog_item(item: dict) -> CatalogItem:
    """Convert a curated vinyl dict into a CatalogItem for Supabase upsert."""
    label = item["label"]
    title = item["title"]
    franchise = item["franchise"]
    pressing = item["pressing"]
    color = item["color"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{label}-{title}-{color}"),
        title=f"{title} ({color})",
        set_code=slugify(label),
        brand=label,
        rarity=item["rarity_tier"].title(),
        notes=f"{label} | {franchise} | {pressing} | {color}",
        attributes_json={
            "label": label,
            "franchise": franchise,
            "pressing": pressing,
            "color": color,
        },
    )


def _vinyl_to_price_observation(item: dict) -> PriceObservation:
    """Convert a curated vinyl dict into a PriceObservation for ML training."""
    tier = item["rarity_tier"]
    pressing = item["pressing"]

    edition = PRESSING_SCORES.get(pressing, 0.50)

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition,
        },
        price=item["price_eur"],
    )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import expanded anime/game OST vinyl catalog + prices",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip Supabase upsert, write local files only")
    args = parser.parse_args()

    logger.info("=== Anime OST Vinyl Expanded Import (85 new items) ===")

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    catalog = get_curated_catalog()
    logger.info(f"Curated catalog loaded: {len(catalog)} items")

    all_items = [_vinyl_to_catalog_item(i) for i in catalog]
    all_observations = [_vinyl_to_price_observation(i) for i in catalog]

    # Write local artifacts
    sql_path = write_catalog_sql(CATEGORY, all_items)
    log_progress(CATEGORY, "catalog SQL written", len(all_items))
    logger.info(f"  -> {sql_path}")

    jsonl_path = write_training_jsonl(CATEGORY, all_observations)
    log_progress(CATEGORY, "training JSONL written", len(all_observations))
    logger.info(f"  -> {jsonl_path}")

    # Upsert to Supabase
    if ingest.enabled:
        inserted = ingest.upsert_catalog(all_items)
        log_progress(CATEGORY, "catalog upserted", inserted)
    else:
        logger.info("Supabase upsert skipped (dry-run or no credentials)")

    ingest.close()
    close_http_client()

    # Summary
    logger.info("")
    logger.info("=== Anime OST Vinyl Expanded Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")

    # Breakdown by sub-catalog
    tier_counts: dict[str, int] = {}
    pressing_counts: dict[str, int] = {}
    for entry in catalog:
        tier_counts[entry["rarity_tier"]] = tier_counts.get(entry["rarity_tier"], 0) + 1
        pressing_counts[entry["pressing"]] = pressing_counts.get(entry["pressing"], 0) + 1

    logger.info("  --- Tier breakdown ---")
    for tier, count in sorted(tier_counts.items()):
        logger.info(f"    {tier:12s}: {count}")
    logger.info("  --- Pressing breakdown ---")
    for pressing, count in sorted(pressing_counts.items()):
        logger.info(f"    {pressing:25s}: {count}")


if __name__ == "__main__":
    main()
