"""
Import Anime Figures catalog.

Layer 1 (Catalog):  Curated anime figure collection → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Scale figures: Good Smile Company, Kotobukiya, Alter, Max Factory (1/4 to 1/8)
- Nendoroids: chibi-style collectible figures
- Figma: articulated action figures
- Prize figures: Banpresto
- Garage kits / resin: unpainted GK kits
- Series: Demon Slayer, Jujutsu Kaisen, One Piece, Fate, Evangelion, Hatsune Miku

Usage:
    python -m pipelines.import_anime_figures [--dry-run]
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
)

CATEGORY = "anime_figures"


def get_curated_catalog() -> list[dict]:
    """Curated anime figure catalog covering major manufacturers and series."""

    # (manufacturer, figure_type, character, series, scale, rarity_tier, price_eur)
    # rarity_tier: grail (>400), high (200-400), mid (80-200), standard (<80)

    figures = [
        # Demon Slayer - Scale Figures
        ("Good Smile Company", "Scale", "Tanjiro Kamado", "Demon Slayer", "1/8", "mid", 160),
        ("Kotobukiya", "Scale", "Nezuko Kamado", "Demon Slayer", "1/8", "mid", 140),
        ("Aniplex", "Scale", "Rengoku Kyojuro", "Demon Slayer", "1/8", "high", 220),
        ("Alter", "Scale", "Shinobu Kocho", "Demon Slayer", "1/7", "high", 250),
        ("Good Smile Company", "Scale", "Muzan Kibutsuji", "Demon Slayer", "1/8", "high", 280),

        # Jujutsu Kaisen
        ("Kotobukiya", "Scale", "Gojo Satoru", "Jujutsu Kaisen", "1/7", "high", 230),
        ("Good Smile Company", "Scale", "Itadori Yuji & Sukuna", "Jujutsu Kaisen", "1/7", "high", 260),
        ("MegaHouse", "Scale", "Fushiguro Megumi", "Jujutsu Kaisen", "1/8", "mid", 180),
        ("FREEing", "Scale", "Gojo Satoru Casual Ver.", "Jujutsu Kaisen", "1/4", "grail", 450),

        # One Piece
        ("MegaHouse", "Portrait of Pirates", "Monkey D. Luffy Gear 5", "One Piece", "1/8", "high", 280),
        ("MegaHouse", "Portrait of Pirates", "Roronoa Zoro", "One Piece", "1/8", "mid", 180),
        ("MegaHouse", "Portrait of Pirates", "Boa Hancock Ver.BB", "One Piece", "1/8", "high", 350),
        ("Banpresto", "DXF", "Shanks Film Red", "One Piece", "Non-scale", "standard", 25),
        ("Banpresto", "King of Artist", "Portgas D. Ace", "One Piece", "Non-scale", "standard", 35),
        ("Tsume Art", "HQS", "Luffy Gear Fourth Snakeman", "One Piece", "1/4", "grail", 750),

        # Fate Series
        ("Good Smile Company", "Scale", "Saber Altria Pendragon", "Fate/Stay Night", "1/7", "high", 220),
        ("Alter", "Scale", "Saber Alter Dress Ver.", "Fate/Stay Night", "1/7", "grail", 400),
        ("Max Factory", "Scale", "Rider Medusa", "Fate/Stay Night", "1/7", "mid", 180),
        ("Aniplex", "Scale", "Jeanne d'Arc", "Fate/Grand Order", "1/7", "high", 260),
        ("Good Smile Company", "Scale", "Mash Kyrielight", "Fate/Grand Order", "1/7", "mid", 190),

        # Evangelion
        ("Kotobukiya", "Scale", "Rei Ayanami Plugsuit Ver.", "Evangelion", "1/6", "high", 200),
        ("Alter", "Scale", "Asuka Langley Test Plugsuit", "Evangelion", "1/7", "high", 280),
        ("Medicom", "RAH", "Shinji Ikari Plugsuit", "Evangelion", "1/6", "high", 350),
        ("Kotobukiya", "Scale", "Eva Unit-01 Awakening", "Evangelion", "Non-scale", "grail", 500),

        # Hatsune Miku
        ("Good Smile Company", "Scale", "Hatsune Miku V4X", "Vocaloid", "1/8", "mid", 160),
        ("Max Factory", "Scale", "Hatsune Miku Deep Sea Girl", "Vocaloid", "1/8", "high", 320),
        ("FREEing", "Scale", "Hatsune Miku Bunny Ver.", "Vocaloid", "1/4", "grail", 480),
        ("Good Smile Company", "Scale", "Hatsune Miku Memorial Dress", "Vocaloid", "1/7", "high", 200),
        ("Good Smile Company", "Scale", "Kagamine Rin & Len", "Vocaloid", "1/8", "mid", 180),

        # Nendoroids
        ("Good Smile Company", "Nendoroid", "Gojo Satoru Nendoroid", "Jujutsu Kaisen", "Nendoroid", "standard", 55),
        ("Good Smile Company", "Nendoroid", "Tanjiro Kamado Nendoroid", "Demon Slayer", "Nendoroid", "standard", 50),
        ("Good Smile Company", "Nendoroid", "Hatsune Miku 2.0 Nendoroid", "Vocaloid", "Nendoroid", "standard", 45),
        ("Good Smile Company", "Nendoroid", "Link Breath of the Wild Nendoroid", "Zelda", "Nendoroid", "mid", 80),
        ("Good Smile Company", "Nendoroid", "Levi Ackerman Nendoroid", "Attack on Titan", "Nendoroid", "mid", 90),
        ("Good Smile Company", "Nendoroid", "Naruto Uzumaki Nendoroid", "Naruto", "Nendoroid", "standard", 50),
        ("Good Smile Company", "Nendoroid", "Rem Nendoroid", "Re:Zero", "Nendoroid", "standard", 55),
        ("Good Smile Company", "Nendoroid", "Zero Two Nendoroid", "DARLING in the FRANXX", "Nendoroid", "mid", 100),
        ("Good Smile Company", "Nendoroid", "Pochita Nendoroid", "Chainsaw Man", "Nendoroid", "standard", 45),
        ("Good Smile Company", "Nendoroid", "Anya Forger Nendoroid", "Spy x Family", "Nendoroid", "standard", 50),

        # Figma
        ("Max Factory", "Figma", "Saber 2.0 Figma", "Fate/Stay Night", "Figma", "mid", 80),
        ("Max Factory", "Figma", "Guts Berserker Armor Figma", "Berserk", "Figma", "mid", 120),
        ("Max Factory", "Figma", "Link Twilight Princess Figma", "Zelda", "Figma", "mid", 95),
        ("Max Factory", "Figma", "Mikasa Ackerman Figma", "Attack on Titan", "Figma", "standard", 70),
        ("Max Factory", "Figma", "Denji Figma", "Chainsaw Man", "Figma", "standard", 65),

        # Prize Figures - Banpresto
        ("Banpresto", "Grandista", "Son Goku Manga Dimensions", "Dragon Ball Z", "Non-scale", "standard", 35),
        ("Banpresto", "Grandista", "Vegeta Manga Dimensions", "Dragon Ball Z", "Non-scale", "standard", 30),
        ("Banpresto", "Vibration Stars", "Tanjiro Kamado", "Demon Slayer", "Non-scale", "standard", 22),
        ("Banpresto", "Vibration Stars", "Zenitsu Agatsuma", "Demon Slayer", "Non-scale", "standard", 20),
        ("Banpresto", "Chronicle Master Stars", "Luffy Gear 5", "One Piece", "Non-scale", "standard", 38),

        # Garage Kits / Resin
        ("E2046", "Garage Kit", "Saber Lily Unpainted GK", "Fate/Stay Night", "1/6", "high", 280),
        ("Hobby Japan", "Garage Kit", "Rei Ayanami GK Unpainted", "Evangelion", "1/6", "high", 320),
        ("Private Studio", "Garage Kit", "Gojo Domain Expansion Resin", "Jujutsu Kaisen", "1/6", "grail", 650),
        ("Private Studio", "Garage Kit", "Luffy Gear 5 Resin Statue", "One Piece", "1/6", "grail", 800),
        ("Private Studio", "Garage Kit", "Tanjiro vs Rui Diorama Resin", "Demon Slayer", "1/8", "grail", 550),
    ]

    catalog = []
    for manufacturer, figure_type, character, series, scale, tier, price in figures:
        catalog.append({
            "manufacturer": manufacturer,
            "figure_type": figure_type,
            "character": character,
            "series": series,
            "scale": scale,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    manufacturer = item["manufacturer"]
    character = item["character"]
    series = item["series"]
    figure_type = item["figure_type"]
    scale = item["scale"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{manufacturer}-{character}-{scale}"),
        title=character,
        set_code=slugify(series),
        brand=manufacturer,
        rarity=item["rarity_tier"].title(),
        notes=f"{manufacturer} | {series} | {figure_type} | {scale}",
        attributes_json={
            "manufacturer": manufacturer,
            "figure_type": figure_type,
            "series": series,
            "scale": scale,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]
    rarity_map = {"grail": 0.95, "high": 0.8, "mid": 0.6, "standard": 0.2}

    figure_type = item["figure_type"]
    edition_scores = {
        "Scale": 0.7,
        "Portrait of Pirates": 0.8,
        "Nendoroid": 0.4,
        "Figma": 0.5,
        "Grandista": 0.2,
        "Vibration Stars": 0.15,
        "Chronicle Master Stars": 0.25,
        "DXF": 0.15,
        "King of Artist": 0.2,
        "RAH": 0.8,
        "Garage Kit": 0.9,
        "HQS": 0.95,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": rarity_map.get(tier, 0.5),
            "edition_score": edition_scores.get(figure_type, 0.5),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Anime Figures catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=== Anime Figures Import ===")

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

    print(f"\n=== Anime Figures Import Complete ===")
    print(f"  Catalog items:      {len(all_items)}")
    print(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
