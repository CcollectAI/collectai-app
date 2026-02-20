"""
Import One Piece collectibles data.

Layer 1 (Catalog):  Curated 100+ items across P.O.P., Figuarts, Ichiban Kuji,
                    Banpresto, Tsume, VAH, WCF, ship models, cards → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated catalog of Portrait of Pirates (Megahouse) incl. NEO-DX, LIMITED,
  Playback Memories, SOC, Maximum lines
- Figuarts ZERO (Extra Battle / extra tall), Variable Action Heroes (VAH)
- Ichiban Kuji Last One prizes, Banpresto DXF / Grandista / King of Artist
- Tsume HQS statues, GEM Series (Megahouse)
- WCF (World Collectable Figure) sets, ship models (Going Merry / Thousand Sunny)
- One Piece Card Game sealed product (booster boxes, promo cards, alt arts)
- Film Red / Stampede special edition figures
- Can be augmented with MyFigureCollection API or scraping later

Usage:
    python -m pipelines.import_one_piece [--dry-run]
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

CATEGORY = "one_piece"


def get_curated_catalog() -> list[dict]:
    """Curated One Piece collectibles catalog (100+ items)."""

    # Format: (line, name, variant, rarity_tier, price_eur)
    # rarity_tier: grail (>200), high (100-200), mid (40-100), standard (<40)

    items = [
        # ── Portrait of Pirates (P.O.P.) Maximum ──────────────────────────
        ("P.O.P. Maximum", "Monkey D. Luffy", "Gear 4 Boundman", "high", 200),
        ("P.O.P. Maximum", "Kaido", "Dragon Form", "grail", 300),
        ("P.O.P. Maximum", "Whitebeard", "Edward Newgate", "grail", 280),
        ("P.O.P. Maximum", "Big Mom", "Charlotte Linlin", "grail", 260),
        ("P.O.P. Maximum", "Monkey D. Luffy", "Gear 5 Sun God Nika", "grail", 320),

        # ── P.O.P. Limited Edition ────────────────────────────────────────
        ("P.O.P. Limited", "Shanks", "Film Red Ver.", "high", 180),
        ("P.O.P. Limited", "Nami", "Wedding Ver.", "high", 190),
        ("P.O.P. Limited", "Nico Robin", "Repaint Ver.", "high", 175),

        # ── P.O.P. Warriors Alliance ──────────────────────────────────────
        ("P.O.P. Warriors Alliance", "Roronoa Zoro", "Wano Country", "high", 160),
        ("P.O.P. Warriors Alliance", "Trafalgar Law", "Wano Country", "high", 140),
        ("P.O.P. Warriors Alliance", "Sanji", "Osoba Mask", "high", 135),

        # ── P.O.P. Sailing Again ──────────────────────────────────────────
        ("P.O.P. Sailing Again", "Nami", "Ver. BB_02", "high", 150),
        ("P.O.P. Sailing Again", "Boa Hancock", "Ver. BB", "high", 170),

        # ── P.O.P. NEO-DX ────────────────────────────────────────────────
        ("P.O.P. NEO-DX", "Portgas D. Ace", "10th Limited", "grail", 250),
        ("P.O.P. NEO-DX", "Crocodile", "", "high", 130),
        ("P.O.P. NEO-DX", "Shanks", "", "grail", 280),
        ("P.O.P. NEO-DX", "Nami", "Ver.2 Repaint", "high", 160),
        ("P.O.P. NEO-DX", "Nico Robin", "", "high", 155),
        ("P.O.P. NEO-DX", "Roronoa Zoro", "10th Limited", "grail", 270),

        # ── P.O.P. SOC (Statue of the Crew) ──────────────────────────────
        ("P.O.P. SOC", "Monkey D. Luffy", "Gear 5", "grail", 280),
        ("P.O.P. SOC", "Jinbe", "", "high", 120),

        # ── P.O.P. Playback Memories ─────────────────────────────────────
        ("P.O.P. Playback Memories", "Portgas D. Ace", "Marineford", "high", 165),
        ("P.O.P. Playback Memories", "Shanks", "Red-Haired Pirates", "high", 170),
        ("P.O.P. Playback Memories", "Koala", "", "mid", 95),
        ("P.O.P. Playback Memories", "Sabo", "Revolutionary Army", "high", 145),
        ("P.O.P. Playback Memories", "Nami", "Arlong Park", "high", 140),

        # ── Figuarts ZERO (Extra Battle / Extra Tall) ─────────────────────
        ("Figuarts ZERO", "Monkey D. Luffy", "Extra Battle Paramount War", "mid", 80),
        ("Figuarts ZERO", "Roronoa Zoro", "Extra Battle", "mid", 70),
        ("Figuarts ZERO", "Sanji", "Extra Battle Diable Jambe", "mid", 65),
        ("Figuarts ZERO", "Portgas D. Ace", "Extra Battle Fire Fist", "high", 100),
        ("Figuarts ZERO", "Marco", "Extra Battle Phoenix", "mid", 75),
        ("Figuarts ZERO", "Eustass Kid", "Extra Battle", "mid", 60),
        ("Figuarts ZERO", "Yamato", "Extra Battle Thunder Bagua", "mid", 85),
        ("Figuarts ZERO", "Kaido", "Extra Battle King of the Beasts", "high", 100),
        ("Figuarts ZERO", "Monkey D. Luffy", "Extra Battle Gear 5 Gigant", "high", 110),
        ("Figuarts ZERO", "Shanks", "Extra Battle Sovereign Haki", "high", 105),
        ("Figuarts ZERO", "Whitebeard", "Extra Battle Paramount War", "high", 115),
        ("Figuarts ZERO", "Kozuki Oden", "Extra Battle", "mid", 75),
        ("Figuarts ZERO", "Sabo", "Extra Battle Fire Fist Inheritance", "mid", 70),

        # ── Variable Action Heroes (VAH) by Megahouse ────────────────────
        ("VAH", "Monkey D. Luffy", "Gear 5", "high", 110),
        ("VAH", "Roronoa Zoro", "Wano Country", "high", 105),
        ("VAH", "Portgas D. Ace", "", "mid", 95),
        ("VAH", "Trafalgar Law", "Wano Country", "mid", 90),
        ("VAH", "Nami", "Punk Hazard Ver.", "mid", 85),

        # ── Ichiban Kuji Prizes ───────────────────────────────────────────
        ("Ichiban Kuji", "Luffy", "Last One Prize Gear 5", "grail", 210),
        ("Ichiban Kuji", "Shanks", "Last One Prize Film Red", "high", 180),
        ("Ichiban Kuji", "Zoro", "Prize A Wano", "high", 120),
        ("Ichiban Kuji", "Kaido", "Prize A Beast Form", "high", 150),
        ("Ichiban Kuji", "Yamato", "Prize B Wano", "mid", 80),
        ("Ichiban Kuji", "Uta", "Last One Prize Film Red", "high", 100),
        ("Ichiban Kuji", "Ace & Luffy", "Prize A Memories", "mid", 90),
        ("Ichiban Kuji", "Law", "Prize B Wano", "mid", 70),
        ("Ichiban Kuji", "Luffy", "Last One Prize Wano Finale", "grail", 220),
        ("Ichiban Kuji", "Roger & Whitebeard", "Last One Prize Legends", "grail", 230),
        ("Ichiban Kuji", "Oden", "Last One Prize Wano", "high", 160),
        ("Ichiban Kuji", "Luffy & Ace & Sabo", "Prize A Brotherhood", "high", 130),

        # ── Banpresto DXF / Grandista / King of Artist ────────────────────
        ("Banpresto", "Monkey D. Luffy", "DXF The Grandline Men", "standard", 20),
        ("Banpresto", "Roronoa Zoro", "DXF The Grandline Men", "standard", 22),
        ("Banpresto", "Sanji", "DXF The Grandline Men", "standard", 18),
        ("Banpresto", "Nami", "Glitter & Glamours", "standard", 25),
        ("Banpresto", "Boa Hancock", "Glitter & Glamours", "standard", 28),
        ("Banpresto", "Monkey D. Luffy", "King of Artist Gear 5", "mid", 40),
        ("Banpresto", "Yamato", "DXF The Grandline Lady", "standard", 25),
        ("Banpresto", "Shanks", "DXF The Grandline Men Film Red", "standard", 30),
        ("Banpresto", "Monkey D. Luffy", "Grandista Manga Dimensions", "mid", 45),
        ("Banpresto", "Roronoa Zoro", "Grandista Manga Dimensions", "mid", 42),
        ("Banpresto", "Portgas D. Ace", "Grandista Manga Dimensions", "mid", 40),
        ("Banpresto", "Trafalgar Law", "DXF The Grandline Men Wano", "standard", 22),
        ("Banpresto", "Nico Robin", "Glitter & Glamours Wano", "standard", 26),

        # ── Tsume HQS Statues ─────────────────────────────────────────────
        ("Tsume HQS", "Monkey D. Luffy", "Red Hawk", "grail", 650),
        ("Tsume HQS", "Roronoa Zoro", "Ashura Ichibugin", "grail", 580),
        ("Tsume HQS", "Portgas D. Ace", "Fire Fist", "grail", 520),
        ("Tsume HQS", "Trafalgar Law", "Gamma Knife", "grail", 480),

        # ── GEM Series by Megahouse ───────────────────────────────────────
        ("GEM Series", "Monkey D. Luffy", "Run! Run! Run!", "high", 120),
        ("GEM Series", "Roronoa Zoro", "Wano Country", "high", 115),
        ("GEM Series", "Sanji", "Wano Country", "high", 110),
        ("GEM Series", "Portgas D. Ace", "15th Anniversary", "high", 135),
        ("GEM Series", "Boa Hancock", "Ver. BB Repaint", "high", 125),

        # ── WCF (World Collectable Figure) Sets ──────────────────────────
        ("WCF", "Straw Hat Crew", "Vol. 1 Complete Set (8 pcs)", "mid", 55),
        ("WCF", "Wano Country", "Vol. 1 Complete Set (6 pcs)", "mid", 48),
        ("WCF", "Film Red", "Complete Set (6 pcs)", "mid", 42),
        ("WCF", "Whole Cake Island", "Complete Set (6 pcs)", "mid", 40),
        ("WCF", "20th Anniversary", "Complete Set (6 pcs)", "mid", 60),
        ("WCF", "Beasts Pirates", "Complete Set (6 pcs)", "mid", 45),

        # ── Ship Models ───────────────────────────────────────────────────
        ("Ship Model", "Going Merry", "Chogokin", "grail", 320),
        ("Ship Model", "Thousand Sunny", "Chogokin", "grail", 350),
        ("Ship Model", "Going Merry", "Grand Ship Collection", "standard", 25),
        ("Ship Model", "Thousand Sunny", "Grand Ship Collection", "standard", 28),
        ("Ship Model", "Polar Tang", "Grand Ship Collection", "standard", 22),
        ("Ship Model", "Going Merry", "Soul of Chogokin Anniversary", "grail", 420),

        # ── One Piece Card Game – Sealed Product & Promo ──────────────────
        ("OP Card Game", "Monkey D. Luffy", "OP01 Leader Alt Art", "mid", 40),
        ("OP Card Game", "Roronoa Zoro", "OP01 SP Alt Art", "high", 120),
        ("OP Card Game", "Shanks", "OP01 SEC Alt Art", "high", 150),
        ("OP Card Game", "Nami", "OP01 SP Alt Art", "high", 100),
        ("OP Card Game", "Trafalgar Law", "OP02 Leader Alt Art", "mid", 50),
        ("OP Card Game", "Yamato", "OP02 SEC", "mid", 60),
        ("OP Card Game", "Monkey D. Luffy", "OP05 Gear 5 SEC", "grail", 210),
        ("OP Card Game", "Charlotte Katakuri", "OP03 Leader Alt Art", "mid", 45),
        ("OP Card Game", "Romance Dawn", "OP01 Booster Box Sealed", "high", 130),
        ("OP Card Game", "Paramount War", "OP02 Booster Box Sealed", "high", 110),
        ("OP Card Game", "Pillars of Strength", "OP03 Booster Box Sealed", "mid", 95),
        ("OP Card Game", "Kingdoms of Intrigue", "OP04 Booster Box Sealed", "mid", 90),
        ("OP Card Game", "Awakening of the New Era", "OP05 Booster Box Sealed", "high", 140),
        ("OP Card Game", "Wings of the Captain", "OP06 Booster Box Sealed", "mid", 85),
        ("OP Card Game", "Monkey D. Luffy", "Promo Tournament Pack", "high", 110),
        ("OP Card Game", "Roronoa Zoro", "Promo Winner Card", "grail", 220),
        ("OP Card Game", "Enel", "OP05 SEC Alt Art", "mid", 65),

        # ── Film Red / Stampede / Special Edition Figures ─────────────────
        ("Film Red", "Uta", "DXF Film Red", "mid", 40),
        ("Film Red", "Shanks", "DXF Film Red Special", "mid", 50),
        ("Film Red", "Luffy", "Figuarts ZERO Film Red", "mid", 65),
        ("Film Red", "Uta", "Ichiban Kuji Prize A", "mid", 75),
        ("Stampede", "Bullet", "DXF Stampede", "mid", 45),
        ("Stampede", "Monkey D. Luffy", "Ichiban Kuji Stampede Last One", "high", 130),
        ("Film Gold", "Luffy Film Gold", "DXF Special", "mid", 40),

        # ── Anniversary / Limited ─────────────────────────────────────────
        ("20th Anniversary", "Monkey D. Luffy", "Ichiban Kuji 20th Anniv", "high", 130),
        ("25th Anniversary", "Straw Hat Crew", "Complete Figure Set", "grail", 250),
    ]

    catalog = []
    for line, name, variant, tier, price in items:
        catalog.append({
            "line": line,
            "name": name,
            "variant": variant,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    line = item["line"]
    name = item["name"]
    variant = item["variant"]

    title_parts = [name]
    if variant:
        title_parts.append(f"({variant})")

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{line}-{name}-{variant}"),
        title=" ".join(title_parts),
        set_code=line.lower().replace(" ", "-").replace(".", ""),
        brand=_line_to_brand(line),
        rarity=item["rarity_tier"].title(),
        notes=f"{line}" + (f" | {variant}" if variant else ""),
        attributes_json={
            "line": line,
            "variant": variant,
            "is_figure": line not in ("OP Card Game", "Ship Model", "WCF"),
            "is_card": line == "OP Card Game",
            "is_prize": line in ("Ichiban Kuji", "Banpresto"),
            "is_model": line == "Ship Model",
            "is_set": line == "WCF",
            "is_statue": line == "Tsume HQS",
        },
    )


def _line_to_brand(line: str) -> str:
    brand_map = {
        "P.O.P.": "Megahouse",
        "Figuarts ZERO": "Bandai",
        "Ichiban Kuji": "Bandai Spirits",
        "Banpresto": "Banpresto",
        "OP Card Game": "Bandai",
        "VAH": "Megahouse",
        "Tsume HQS": "Tsume Art",
        "GEM Series": "Megahouse",
        "WCF": "Banpresto",
        "Ship Model": "Bandai",
        "Film Red": "Banpresto",
        "Film Gold": "Banpresto",
        "Stampede": "Banpresto",
        "20th Anniversary": "Bandai Spirits",
        "25th Anniversary": "Bandai Spirits",
    }
    for prefix, brand in brand_map.items():
        if line.startswith(prefix):
            return brand
    return "Bandai"


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]
    is_limited = (
        item["line"].startswith("P.O.P.")
        or item["line"] == "Tsume HQS"
        or "Last One" in item.get("variant", "")
    )

    return PriceObservation(
        features={
            "condition_score": 0.9,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": 0.85 if is_limited else 0.4,
            "is_figure": 1.0 if item["line"] != "OP Card Game" else 0.0,
            "is_card": 1.0 if item["line"] == "OP Card Game" else 0.0,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import One Piece collectibles catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== One Piece Import ===")

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

    logger.info(f"\n=== One Piece Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
