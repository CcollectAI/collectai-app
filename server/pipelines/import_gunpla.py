"""
Import Gunpla (Gundam plastic model kit) catalog.

Layer 1 (Catalog):  Curated Gunpla kits → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers 100+ kits across:
- Perfect Grade (PG) 1/60 scale (incl. Unleashed)
- Master Grade (MG) 1/100 scale (incl. Ver.Ka, Ver.2.0)
- Master Grade Extreme (MGEX) 1/100 scale
- Real Grade (RG) 1/144 scale
- High Grade (HG) 1/144 scale (incl. The Origin, Build series)
- Mega Size 1/48 scale
- SD Gundam / SD Cross Silhouette
- P-Bandai web-shop exclusives (limited runs)
- Metal Build die-cast figures
- Vintage 1/100 and 1/60 kits
- Series coverage: UC, SEED, Wing, 00, IBO, Witch from Mercury, Build

Usage:
    python -m pipelines.import_gunpla [--dry-run]
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

CATEGORY = "gunpla"


def get_curated_catalog() -> list[dict]:
    """Curated Gunpla catalog — 120+ kits across all major grades, series, and formats."""

    # (grade, scale, name, series, variant, rarity_tier, price_eur)
    # rarity_tier: grail (>200), high (100-200), mid (40-100), standard (<40)

    kits = [
        # ── Perfect Grade (PG) 1/60 ──────────────────────────────────────────
        ("PG", "1/60", "RX-78-2 Gundam", "Mobile Suit Gundam", "", "high", 180),
        ("PG", "1/60", "Unicorn Gundam", "Gundam Unicorn", "", "grail", 320),
        ("PG", "1/60", "Strike Freedom Gundam", "Gundam SEED Destiny", "", "grail", 280),
        ("PG", "1/60", "Gundam Exia", "Gundam 00", "", "high", 200),
        ("PG", "1/60", "Zaku II (Char Custom)", "Mobile Suit Gundam", "", "high", 180),
        ("PG", "1/60", "Banshee Norn", "Gundam Unicorn", "", "grail", 350),
        ("PG", "1/60", "Wing Gundam Zero Custom", "Gundam Wing", "", "grail", 250),
        ("PG", "1/60", "Unleashed RX-78-2", "Mobile Suit Gundam", "Unleashed", "grail", 380),
        ("PG", "1/60", "Astray Red Frame", "Gundam SEED Astray", "", "high", 190),
        ("PG", "1/60", "00 Raiser", "Gundam 00", "", "grail", 260),
        ("PG", "1/60", "GP01/Fb Full Burnern", "Gundam 0083", "", "high", 175),

        # ── Master Grade Extreme (MGEX) 1/100 ───────────────────────────────
        ("MGEX", "1/100", "Unicorn Gundam Ver.Ka", "Gundam Unicorn", "MGEX", "grail", 220),
        ("MGEX", "1/100", "Strike Freedom Gundam", "Gundam SEED Destiny", "MGEX", "grail", 210),

        # ── Master Grade (MG) 1/100 ─────────────────────────────────────────
        ("MG", "1/100", "Freedom Gundam Ver.2.0", "Gundam SEED", "", "mid", 55),
        ("MG", "1/100", "RX-78-2 Gundam Ver.3.0", "Mobile Suit Gundam", "", "mid", 50),
        ("MG", "1/100", "Sazabi Ver.Ka", "Char's Counterattack", "Ver.Ka", "mid", 85),
        ("MG", "1/100", "Nu Gundam Ver.Ka", "Char's Counterattack", "Ver.Ka", "mid", 75),
        ("MG", "1/100", "Wing Gundam Zero EW Ver.Ka", "Gundam Wing", "Ver.Ka", "mid", 60),
        ("MG", "1/100", "Sinanju Ver.Ka", "Gundam Unicorn", "Ver.Ka", "mid", 80),
        ("MG", "1/100", "Hi-Nu Gundam Ver.Ka", "Char's Counterattack", "Ver.Ka", "high", 110),
        ("MG", "1/100", "Unicorn Gundam Ver.Ka", "Gundam Unicorn", "Ver.Ka", "mid", 65),
        ("MG", "1/100", "Barbatos", "Iron-Blooded Orphans", "", "mid", 50),
        ("MG", "1/100", "Deathscythe Hell EW", "Gundam Wing", "", "mid", 55),
        ("MG", "1/100", "Full Armor Unicorn Ver.Ka", "Gundam Unicorn", "Ver.Ka", "high", 120),
        ("MG", "1/100", "Zaku II Ver.2.0", "Mobile Suit Gundam", "", "mid", 45),
        ("MG", "1/100", "Epyon EW", "Gundam Wing", "", "mid", 55),
        ("MG", "1/100", "Eclipse Gundam", "Gundam SEED Eclipse", "", "mid", 60),
        ("MG", "1/100", "ZZ Gundam Ver.Ka", "Gundam ZZ", "Ver.Ka", "mid", 70),
        ("MG", "1/100", "Full Armor ZZ Gundam Ver.Ka", "Gundam ZZ", "Ver.Ka", "high", 100),
        ("MG", "1/100", "Tallgeese EW", "Gundam Wing", "", "mid", 50),
        ("MG", "1/100", "Turn A Gundam", "Turn A Gundam", "", "mid", 55),
        ("MG", "1/100", "Gundam Kyrios", "Gundam 00", "", "mid", 48),
        ("MG", "1/100", "Gundam Dynames", "Gundam 00", "", "mid", 48),
        ("MG", "1/100", "Gundam Virtue", "Gundam 00", "", "mid", 55),
        ("MG", "1/100", "00 Raiser", "Gundam 00", "", "mid", 65),
        ("MG", "1/100", "00 Qan[T] Full Saber", "Gundam 00", "Ver.Ka", "mid", 70),
        ("MG", "1/100", "Wing Gundam Ver.Ka", "Gundam Wing", "Ver.Ka", "mid", 55),
        ("MG", "1/100", "Heavyarms EW", "Gundam Wing", "", "mid", 50),
        ("MG", "1/100", "Sandrock EW", "Gundam Wing", "", "mid", 45),
        ("MG", "1/100", "Altron Gundam EW", "Gundam Wing", "", "mid", 50),
        ("MG", "1/100", "Blitz Gundam", "Gundam SEED", "", "mid", 45),
        ("MG", "1/100", "Buster Gundam", "Gundam SEED", "", "mid", 45),
        ("MG", "1/100", "Duel Gundam Assault Shroud", "Gundam SEED", "", "mid", 48),
        ("MG", "1/100", "Justice Gundam", "Gundam SEED", "", "mid", 50),
        ("MG", "1/100", "Aile Strike Gundam Ver.RM", "Gundam SEED", "", "mid", 50),
        ("MG", "1/100", "Strike Rouge Ootori Ver.RM", "Gundam SEED", "", "mid", 65),
        ("MG", "1/100", "Destiny Gundam", "Gundam SEED Destiny", "", "mid", 55),
        ("MG", "1/100", "Infinite Justice Gundam", "Gundam SEED Destiny", "", "mid", 55),
        ("MG", "1/100", "Gundam Barbatos Lupus Rex", "Iron-Blooded Orphans", "", "mid", 55),
        ("MG", "1/100", "Gundam F91 Ver.2.0", "Gundam F91", "", "mid", 50),
        ("MG", "1/100", "V2 Assault Buster Gundam Ver.Ka", "Victory Gundam", "Ver.Ka", "mid", 75),
        ("MG", "1/100", "The-O", "Zeta Gundam", "", "high", 110),
        ("MG", "1/100", "Jesta", "Gundam Unicorn", "", "mid", 45),

        # ── Real Grade (RG) 1/144 ───────────────────────────────────────────
        ("RG", "1/144", "Hi-Nu Gundam", "Char's Counterattack", "", "mid", 48),
        ("RG", "1/144", "Sazabi", "Char's Counterattack", "", "mid", 45),
        ("RG", "1/144", "Wing Gundam Zero EW", "Gundam Wing", "", "standard", 30),
        ("RG", "1/144", "Unicorn Gundam", "Gundam Unicorn", "", "standard", 32),
        ("RG", "1/144", "Nu Gundam", "Char's Counterattack", "", "mid", 42),
        ("RG", "1/144", "God Gundam", "G Gundam", "", "mid", 40),
        ("RG", "1/144", "Force Impulse Gundam", "Gundam SEED Destiny", "", "standard", 28),
        ("RG", "1/144", "Evangelion Unit-01", "Evangelion", "", "mid", 50),
        ("RG", "1/144", "Strike Freedom Gundam", "Gundam SEED Destiny", "", "standard", 35),
        ("RG", "1/144", "Zeong", "Mobile Suit Gundam", "", "mid", 55),
        ("RG", "1/144", "Crossbone Gundam X1", "Crossbone Gundam", "", "standard", 32),
        ("RG", "1/144", "Gundam Exia", "Gundam 00", "", "standard", 28),
        ("RG", "1/144", "00 Raiser", "Gundam 00", "", "standard", 35),
        ("RG", "1/144", "Destiny Gundam", "Gundam SEED Destiny", "", "standard", 30),
        ("RG", "1/144", "Freedom Gundam", "Gundam SEED", "", "standard", 28),
        ("RG", "1/144", "Justice Gundam", "Gundam SEED", "", "standard", 28),
        ("RG", "1/144", "Tallgeese EW", "Gundam Wing", "", "standard", 30),
        ("RG", "1/144", "Gundam Mk-II AEUG", "Zeta Gundam", "", "standard", 28),
        ("RG", "1/144", "Zeta Gundam", "Zeta Gundam", "", "standard", 30),
        ("RG", "1/144", "Char's Zaku II", "Mobile Suit Gundam", "", "standard", 28),

        # ── P-Bandai Exclusives ──────────────────────────────────────────────
        ("MG", "1/100", "Altron Gundam EW (P-Bandai)", "Gundam Wing", "P-Bandai", "high", 120),
        ("MG", "1/100", "Crossbone Gundam X-2 Ver.Ka (P-Bandai)", "Crossbone Gundam", "P-Bandai Ver.Ka", "high", 130),
        ("RG", "1/144", "Tallgeese III (P-Bandai)", "Gundam Wing", "P-Bandai", "high", 65),
        ("MG", "1/100", "Hazel Custom (P-Bandai)", "Advance of Zeta", "P-Bandai", "high", 110),
        ("PG", "1/60", "Unicorn Gundam Perfectibility (P-Bandai)", "Gundam Unicorn", "P-Bandai", "grail", 450),
        ("MG", "1/100", "Providence Gundam (P-Bandai)", "Gundam SEED", "P-Bandai", "high", 100),
        ("HG", "1/144", "Penelope (P-Bandai)", "Hathaway's Flash", "P-Bandai", "mid", 80),
        ("RG", "1/144", "Banshee Norn Final Battle (P-Bandai)", "Gundam Unicorn", "P-Bandai", "mid", 70),
        ("MG", "1/100", "Deathscythe Hell EW (P-Bandai Rousette)", "Gundam Wing", "P-Bandai", "high", 115),
        ("MG", "1/100", "Sandrock EW Armadillo (P-Bandai)", "Gundam Wing", "P-Bandai", "high", 110),
        ("MG", "1/100", "Heavyarms EW Igel (P-Bandai)", "Gundam Wing", "P-Bandai", "high", 115),
        ("RG", "1/144", "Wing Gundam Zero EW Pearl Gloss (P-Bandai)", "Gundam Wing", "P-Bandai", "high", 75),
        ("MG", "1/100", "Gundam Astray Blue Frame D (P-Bandai)", "Gundam SEED Astray", "P-Bandai", "high", 100),
        ("HG", "1/144", "Xi Gundam (P-Bandai)", "Hathaway's Flash", "P-Bandai", "mid", 90),
        ("MG", "1/100", "Gelgoog Cannon (P-Bandai)", "Mobile Suit Gundam", "P-Bandai", "high", 100),

        # ── High Grade (HG) 1/144 ───────────────────────────────────────────
        ("HG", "1/144", "RX-78-2 Gundam (Revive)", "Mobile Suit Gundam", "", "standard", 14),
        ("HG", "1/144", "Barbatos Lupus Rex", "Iron-Blooded Orphans", "", "standard", 16),
        ("HG", "1/144", "Aerial", "Gundam: Witch from Mercury", "", "standard", 15),
        ("HG", "1/144", "Calibarn", "Gundam: Witch from Mercury", "", "standard", 18),
        ("HG", "1/144", "Schwarzette", "Gundam: Witch from Mercury", "", "standard", 20),
        ("HG", "1/144", "Moon Gundam", "Moon Gundam", "", "standard", 30),
        ("HG", "1/144", "Infinite Justice Gundam Type II", "Gundam SEED Freedom", "", "standard", 22),
        ("HG", "1/144", "Mighty Strike Freedom", "Gundam SEED Freedom", "", "standard", 28),
        # HG The Origin
        ("HG", "1/144", "RX-78-02 Gundam (The Origin)", "Mobile Suit Gundam: The Origin", "The Origin", "standard", 18),
        ("HG", "1/144", "MS-06S Zaku II (The Origin)", "Mobile Suit Gundam: The Origin", "The Origin", "standard", 16),
        ("HG", "1/144", "YMS-03 Waff (The Origin)", "Mobile Suit Gundam: The Origin", "The Origin", "standard", 16),
        ("HG", "1/144", "Gouf (The Origin)", "Mobile Suit Gundam: The Origin", "The Origin", "standard", 16),
        ("HG", "1/144", "Bugu (Ramba Ral) (The Origin)", "Mobile Suit Gundam: The Origin", "The Origin", "standard", 18),
        # HG Build series
        ("HG", "1/144", "Build Strike Gundam Full Package", "Gundam Build Fighters", "Build", "standard", 16),
        ("HG", "1/144", "Star Burning Gundam", "Gundam Build Fighters Try", "Build", "standard", 18),
        ("HG", "1/144", "Try Burning Gundam", "Gundam Build Fighters Try", "Build", "standard", 16),
        ("HG", "1/144", "Gundam 00 Diver Ace", "Gundam Build Divers", "Build", "standard", 16),
        ("HG", "1/144", "Earthree Gundam", "Gundam Build Divers Re:RISE", "Build", "standard", 15),
        # HG IBO
        ("HG", "1/144", "Barbatos (1st Form)", "Iron-Blooded Orphans", "", "standard", 12),
        ("HG", "1/144", "Barbatos Lupus", "Iron-Blooded Orphans", "", "standard", 14),
        ("HG", "1/144", "Grimgerde", "Iron-Blooded Orphans", "", "standard", 14),
        ("HG", "1/144", "Vidar", "Iron-Blooded Orphans", "", "standard", 16),
        # HG misc popular
        ("HG", "1/144", "Narrative Gundam A-Packs", "Gundam Narrative", "", "standard", 25),
        ("HG", "1/144", "Xi Gundam", "Hathaway's Flash", "", "standard", 38),
        ("HG", "1/144", "Penelope", "Hathaway's Flash", "", "standard", 38),

        # ── Mega Size 1/48 ───────────────────────────────────────────────────
        ("Mega Size", "1/48", "RX-78-2 Gundam", "Mobile Suit Gundam", "", "mid", 65),
        ("Mega Size", "1/48", "Char's Zaku II", "Mobile Suit Gundam", "", "mid", 65),
        ("Mega Size", "1/48", "Unicorn Gundam (Destroy Mode)", "Gundam Unicorn", "", "mid", 75),
        ("Mega Size", "1/48", "Age-1 Normal", "Gundam AGE", "", "mid", 60),

        # ── SD Gundam ────────────────────────────────────────────────────────
        ("SD CS", "SD", "RX-78-2 Gundam (Cross Silhouette)", "Mobile Suit Gundam", "Cross Silhouette", "standard", 12),
        ("SD CS", "SD", "Unicorn Gundam (Destroy Mode) (Cross Silhouette)", "Gundam Unicorn", "Cross Silhouette", "standard", 14),
        ("SD CS", "SD", "Freedom Gundam (Cross Silhouette)", "Gundam SEED", "Cross Silhouette", "standard", 14),
        ("SD EX-Standard", "SD", "Wing Gundam Zero EW", "Gundam Wing", "EX-Standard", "standard", 8),
        ("SD EX-Standard", "SD", "Strike Freedom Gundam", "Gundam SEED Destiny", "EX-Standard", "standard", 8),

        # ── Metal Build (die-cast figures) ───────────────────────────────────
        ("Metal Build", "1/100", "Strike Freedom Gundam", "Gundam SEED Destiny", "Metal Build", "grail", 350),
        ("Metal Build", "1/100", "Destiny Gundam (Full Package)", "Gundam SEED Destiny", "Metal Build", "grail", 380),
        ("Metal Build", "1/100", "00 Raiser", "Gundam 00", "Metal Build", "grail", 320),
        ("Metal Build", "1/100", "Gundam Barbatos Lupus Rex", "Iron-Blooded Orphans", "Metal Build", "grail", 300),
        ("Metal Build", "1/100", "Freedom Gundam Concept 2", "Gundam SEED", "Metal Build", "grail", 400),
        ("Metal Build", "1/100", "Aile Strike Gundam", "Gundam SEED", "Metal Build", "grail", 280),
        ("Metal Build", "1/100", "Crossbone Gundam X1", "Crossbone Gundam", "Metal Build", "grail", 260),
        ("Metal Build", "1/100", "Hi-Nu Gundam", "Char's Counterattack", "Metal Build", "grail", 420),

        # ── Vintage Kits ─────────────────────────────────────────────────────
        ("Vintage", "1/100", "RX-78-2 Gundam (1980 Original)", "Mobile Suit Gundam", "Vintage", "high", 120),
        ("Vintage", "1/100", "MS-06S Zaku II (1980 Original)", "Mobile Suit Gundam", "Vintage", "high", 100),
        ("Vintage", "1/60", "RX-78-2 Gundam (1980 1/60)", "Mobile Suit Gundam", "Vintage", "high", 150),
        ("Vintage", "1/100", "Z Gundam (1985 Original)", "Zeta Gundam", "Vintage", "high", 110),
        ("Vintage", "1/100", "ZZ Gundam (1986 Original)", "Gundam ZZ", "Vintage", "high", 100),
        ("Vintage", "1/60", "Zaku II (1980 1/60)", "Mobile Suit Gundam", "Vintage", "high", 130),
    ]

    catalog = []
    for grade, scale, name, series, variant, tier, price in kits:
        catalog.append({
            "grade": grade,
            "scale": scale,
            "name": name,
            "series": series,
            "variant": variant,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    grade = item["grade"]
    name = item["name"]
    series = item["series"]
    variant = item["variant"]
    scale = item["scale"]

    title_parts = [grade, name]
    if variant:
        title_parts.append(f"({variant})")

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{grade}-{name}" + (f"-{variant}" if variant else "")),
        title=" ".join(title_parts),
        set_code=slugify(series),
        brand="Bandai",
        rarity=item["rarity_tier"].title(),
        notes=f"{grade} {scale} | {series}" + (f" | {variant}" if variant else ""),
        attributes_json={
            "grade": grade,
            "scale": scale,
            "series": series,
            "variant": variant,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    variant = item["variant"]
    is_p_bandai = "P-Bandai" in variant if variant else False
    is_ver_ka = "Ver.Ka" in variant if variant else False

    grade = item["grade"]
    grade_scores = {
        "PG": 0.85,
        "MG": 0.5,
        "RG": 0.4,
        "HG": 0.2,
    }

    edition_score = grade_scores.get(grade, 0.4)
    if is_p_bandai:
        edition_score = min(1.0, edition_score + 0.3)
    if is_ver_ka:
        edition_score = min(1.0, edition_score + 0.15)

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_score,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Gunpla catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Gunpla Import ===")

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

    logger.info(f"\n=== Gunpla Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
