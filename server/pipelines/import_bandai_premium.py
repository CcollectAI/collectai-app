"""
Import Bandai Premium / P-Bandai exclusive figures catalog.

Layer 1 (Catalog):  Curated P-Bandai exclusives → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- S.H.Figuarts web exclusives (Dragon Ball, Kamen Rider, Naruto)
- Robot Spirits (Gundam, Evangelion)
- Chogokin / Soul of Chogokin vintage super robot
- Tamashii Nations event exclusives
- Metal Build premium Gundam figures

Usage:
    python -m pipelines.import_bandai_premium [--dry-run]
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

CATEGORY = "bandai_premium"


def get_curated_catalog() -> list[dict]:
    """Curated Bandai Premium / P-Bandai exclusives catalog (65+ items)."""

    # (line, name, franchise, exclusive_type, rarity_tier, price_eur)
    # rarity_tier: grail (>300), high (150-300), mid (60-150), standard (<60)

    items = [
        # S.H.Figuarts – Dragon Ball
        ("S.H.Figuarts", "Super Saiyan God Vegeta", "Dragon Ball Super", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Majin Vegeta", "Dragon Ball Z", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Full Power Frieza", "Dragon Ball Z", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Android 19 & 20 Set", "Dragon Ball Z", "P-Bandai", "high", 160),
        ("S.H.Figuarts", "Bardock", "Dragon Ball Z", "P-Bandai", "mid", 110),
        ("S.H.Figuarts", "Super Saiyan God Super Saiyan Gogeta", "Dragon Ball Super: Broly", "P-Bandai", "mid", 90),

        # S.H.Figuarts – Kamen Rider
        ("S.H.Figuarts", "Kamen Rider Kuuga Amazing Mighty", "Kamen Rider Kuuga", "P-Bandai", "mid", 75),
        ("S.H.Figuarts", "Kamen Rider Faiz Blaster Form", "Kamen Rider 555", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Kamen Rider OOO Super Tatoba Combo", "Kamen Rider OOO", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Kamen Rider W FangJoker", "Kamen Rider W", "P-Bandai", "mid", 70),

        # S.H.Figuarts – Naruto
        ("S.H.Figuarts", "Itachi Uchiha Edo Tensei", "Naruto Shippuden", "P-Bandai", "mid", 75),
        ("S.H.Figuarts", "Minato Namikaze", "Naruto Shippuden", "P-Bandai", "mid", 90),

        # Robot Spirits – Gundam
        ("Robot Spirits", "RX-78GP03S Stamen ver. A.N.I.M.E.", "Gundam 0083", "P-Bandai", "mid", 80),
        ("Robot Spirits", "MS-06R-2 Zaku II High Mobility Type", "Gundam MSV", "P-Bandai", "mid", 75),
        ("Robot Spirits", "Nightingale ver. A.N.I.M.E.", "Gundam CCA-MSV", "P-Bandai", "high", 155),

        # Robot Spirits – Evangelion
        ("Robot Spirits", "EVA Unit-01 Awakening Ver.", "Evangelion", "P-Bandai", "mid", 95),
        ("Robot Spirits", "EVA Unit-13", "Evangelion 3.0+1.0", "P-Bandai", "mid", 90),

        # Chogokin / Soul of Chogokin
        ("Soul of Chogokin", "GX-72 Megazord", "Super Sentai", "Standard", "high", 250),
        ("Soul of Chogokin", "GX-105 Mazinkaiser Infinitism", "Mazinkaiser", "Standard", "high", 220),
        ("Soul of Chogokin", "GX-70SP Mazinger Z D.C. Anime Color", "Mazinger Z", "P-Bandai", "high", 280),
        ("Soul of Chogokin", "GX-76X2 Grendizer D.C. Drill Spazer", "UFO Robot Grendizer", "P-Bandai", "high", 200),
        ("Soul of Chogokin", "GX-01R+ Mazinger Z (40th Anniversary)", "Mazinger Z", "Event Exclusive", "grail", 350),

        # Tamashii Nations Event Exclusives
        ("S.H.Figuarts", "Son Goku Ultra Instinct -Sign-", "Dragon Ball Super", "TNE", "high", 160),
        ("S.H.Figuarts", "Kamen Rider Decade Complete 21", "Kamen Rider Decade", "TNE", "mid", 120),
        ("Robot Spirits", "Full Armor Unicorn Gundam", "Gundam Unicorn", "TNE", "mid", 100),

        # Metal Build
        ("Metal Build", "Strike Freedom Gundam", "Gundam SEED Destiny", "Standard", "grail", 380),
        ("Metal Build", "00 Raiser", "Gundam 00", "Standard", "high", 280),
        ("Metal Build", "Destiny Gundam (Full Package)", "Gundam SEED Destiny", "P-Bandai", "grail", 400),
        ("Metal Build", "Astray Red Frame Kai", "Gundam SEED Astray", "Standard", "high", 300),
        ("Metal Build", "Hi-Nu Gundam", "Gundam CCA", "Standard", "grail", 420),
        ("Metal Build", "Crossbone Gundam X1", "Crossbone Gundam", "P-Bandai", "high", 280),

        # ── New items below ──────────────────────────────────────────────

        # S.H.Figuarts – Kamen Rider (additional)
        ("S.H.Figuarts", "Kamen Rider Black Sun", "Kamen Rider Black Sun", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Kamen Rider Kuuga Ultimate Form", "Kamen Rider Kuuga", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "Kamen Rider Decade Violent Emotion", "Kamen Rider Decade", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Kamen Rider W CycloneJokerXtreme", "Kamen Rider W", "P-Bandai", "mid", 80),

        # S.H.Figuarts – Naruto (additional)
        ("S.H.Figuarts", "Itachi Uchiha -Narutop99-", "Naruto Shippuden", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Kakashi Hatake Anbu Black Ops", "Naruto Shippuden", "P-Bandai", "mid", 95),

        # S.H.Figuarts – One Piece
        ("S.H.Figuarts", "Monkey D. Luffy Gear 5", "One Piece", "Standard", "mid", 75),
        ("S.H.Figuarts", "Roronoa Zoro -Wano Kuni-", "One Piece", "P-Bandai", "mid", 80),

        # S.H.Figuarts – Ultraman
        ("S.H.Figuarts", "Ultraman (Shin Ultraman)", "Shin Ultraman", "P-Bandai", "mid", 70),

        # Robot Spirits – Gundam (additional)
        ("Robot Spirits", "RX-78-2 Gundam ver. A.N.I.M.E.", "Mobile Suit Gundam", "Standard", "mid", 65),
        ("Robot Spirits", "MS-06S Zaku II Char Custom ver. A.N.I.M.E.", "Mobile Suit Gundam", "Standard", "mid", 65),
        ("Robot Spirits", "RX-93 Nu Gundam ver. A.N.I.M.E.", "Gundam CCA", "Standard", "mid", 85),
        ("Robot Spirits", "MSN-04 Sazabi ver. A.N.I.M.E.", "Gundam CCA", "Standard", "mid", 90),

        # Robot Spirits – Evangelion (additional)
        ("Robot Spirits", "EVA Unit-01 Test Type", "Evangelion", "Standard", "mid", 70),
        ("Robot Spirits", "EVA Unit-02 Production Model", "Evangelion", "Standard", "mid", 70),

        # Metal Build (additional)
        ("Metal Build", "Strike Freedom Gundam Soul Blue Ver.", "Gundam SEED Destiny", "P-Bandai", "grail", 450),
        ("Metal Build", "00 Raiser Designer's Blue Ver.", "Gundam 00", "P-Bandai", "grail", 350),
        ("Metal Build", "Destiny Gundam Heine Custom", "Gundam SEED Destiny", "P-Bandai", "high", 300),
        ("Metal Build", "Crossbone Gundam X1 Full Cloth", "Crossbone Gundam", "P-Bandai", "grail", 380),
        ("Metal Build", "Hi-Nu Gundam Marking Plus Ver.", "Gundam CCA", "P-Bandai", "grail", 480),

        # Soul of Chogokin (additional)
        ("Soul of Chogokin", "GX-70 Mazinger Z D.C.", "Mazinger Z", "Standard", "high", 180),
        ("Soul of Chogokin", "GX-73 Great Mazinger D.C.", "Great Mazinger", "Standard", "high", 200),
        ("Soul of Chogokin", "GX-76 Grendizer D.C.", "UFO Robot Grendizer", "Standard", "high", 190),
        ("Soul of Chogokin", "GX-71SP GoLion (Voltron)", "Beast King GoLion", "P-Bandai", "grail", 380),
        ("Soul of Chogokin", "GX-72B Daizyujin (Megazord) Black Ver.", "Super Sentai", "P-Bandai", "high", 290),

        # Tamashii Nations Event Exclusives (additional)
        ("S.H.Figuarts", "Vegito Super Saiyan Blue (SDCC)", "Dragon Ball Super", "Event Exclusive", "high", 180),
        ("S.H.Figuarts", "Son Goku Super Saiyan (SDCC 2019)", "Dragon Ball Z", "Event Exclusive", "high", 170),
        ("S.H.Figuarts", "Kamen Rider Ichigo (50th Anniversary)", "Kamen Rider", "TNE", "high", 150),
        ("Robot Spirits", "Wing Gundam Zero (EW) Pearl Coating", "Gundam Wing", "TNE", "high", 160),
        ("Metal Build", "Strike Gundam (Tamashii Nations Tokyo)", "Gundam SEED", "Event Exclusive", "grail", 400),

        # DX Chogokin – Macross
        ("DX Chogokin", "VF-1S Strike Valkyrie (Hikaru)", "Macross", "Standard", "high", 280),
        ("DX Chogokin", "VF-25F Messiah Valkyrie (Alto)", "Macross Frontier", "Standard", "high", 250),
        ("DX Chogokin", "YF-29 Durandal Valkyrie (Alto)", "Macross Frontier", "Standard", "high", 260),

        # Figuarts ZERO – One Piece
        ("Figuarts ZERO", "Monkey D. Luffy -Gomu Gomu no Red Roc-", "One Piece", "Standard", "mid", 90),
        ("Figuarts ZERO", "Kaido King of the Beasts -Twin Dragons-", "One Piece", "Standard", "mid", 120),
        ("Figuarts ZERO", "Portgas D. Ace -Fire Fist-", "One Piece", "Standard", "mid", 85),

        # Figuarts ZERO – Dragon Ball
        ("Figuarts ZERO", "Super Saiyan Son Goku -The Burning Battles-", "Dragon Ball Z", "Standard", "mid", 75),
        ("Figuarts ZERO", "Vegeta Galick Gun", "Dragon Ball Z", "Standard", "mid", 70),
    ]

    catalog = []
    for line, name, franchise, exclusive_type, tier, price in items:
        catalog.append({
            "line": line,
            "name": name,
            "franchise": franchise,
            "exclusive_type": exclusive_type,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    line = item["line"]
    name = item["name"]
    franchise = item["franchise"]
    exclusive_type = item["exclusive_type"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{line}-{name}"),
        title=f"{line} {name}",
        set_code=slugify(line),
        brand="Bandai",
        rarity=item["rarity_tier"].title(),
        notes=f"{line} | {franchise}" + (f" | {exclusive_type}" if exclusive_type else ""),
        attributes_json={
            "line": line,
            "franchise": franchise,
            "exclusive_type": exclusive_type,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    exclusive_type = item["exclusive_type"]
    edition_scores = {
        "P-Bandai": 0.80,
        "TNE": 0.90,
        "Event Exclusive": 0.95,
        "Standard": 0.40,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_scores.get(exclusive_type, 0.5),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Bandai Premium catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Bandai Premium Import ===")

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

    logger.info(f"\n=== Bandai Premium Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
