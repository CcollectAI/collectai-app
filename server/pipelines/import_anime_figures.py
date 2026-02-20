"""
Import Anime Figures catalog.

Layer 1 (Catalog):  Curated anime figure collection → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers 120+ figures across:
- Scale figures: Good Smile Company, Kotobukiya, Alter, Max Factory, FREEing (1/4 to 1/8)
- Nendoroids: chibi-style collectible figures (20+ characters)
- Figma: articulated action figures (10+ characters)
- S.H.Figuarts: Bandai premium articulated figures
- Prize figures: Banpresto (Grandista, DXF, Vibration Stars)
- Garage kits / resin: unpainted GK kits
- Premium resin: Prime 1 Studio, Tsume Art HQS (ultra grails)
- Robot Spirits: Bandai mecha line (Gundam)
- Series: Demon Slayer, Jujutsu Kaisen, One Piece, Fate, Evangelion,
  Hatsune Miku, Attack on Titan, Chainsaw Man, Spy x Family,
  Dragon Ball Z/Super, Naruto, My Hero Academia, Re:Zero, Bleach, Gundam

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
    rarity_score as shared_rarity_score,
    RARITY_SCORE_MAP,
    logger,
    close_http_client,
)

CATEGORY = "anime_figures"


def get_curated_catalog() -> list[dict]:
    """Curated anime figure catalog covering major manufacturers and series."""

    # (manufacturer, figure_type, character, series, scale, rarity_tier, price_eur)
    # rarity_tier: grail (>400), high (200-400), mid (80-200), standard (<80)

    figures = [
        # ── Demon Slayer - Scale Figures ──────────────────────────────
        ("Good Smile Company", "Scale", "Tanjiro Kamado", "Demon Slayer", "1/8", "mid", 160),
        ("Kotobukiya", "Scale", "Nezuko Kamado", "Demon Slayer", "1/8", "mid", 140),
        ("Aniplex", "Scale", "Rengoku Kyojuro", "Demon Slayer", "1/8", "high", 220),
        ("Alter", "Scale", "Shinobu Kocho", "Demon Slayer", "1/7", "high", 250),
        ("Good Smile Company", "Scale", "Muzan Kibutsuji", "Demon Slayer", "1/8", "high", 280),

        # ── Jujutsu Kaisen ────────────────────────────────────────────
        ("Kotobukiya", "Scale", "Gojo Satoru", "Jujutsu Kaisen", "1/7", "high", 230),
        ("Good Smile Company", "Scale", "Itadori Yuji & Sukuna", "Jujutsu Kaisen", "1/7", "high", 260),
        ("MegaHouse", "Scale", "Fushiguro Megumi", "Jujutsu Kaisen", "1/8", "mid", 180),
        ("FREEing", "Scale", "Gojo Satoru Casual Ver.", "Jujutsu Kaisen", "1/4", "grail", 450),

        # ── One Piece ─────────────────────────────────────────────────
        ("MegaHouse", "Portrait of Pirates", "Monkey D. Luffy Gear 5", "One Piece", "1/8", "high", 280),
        ("MegaHouse", "Portrait of Pirates", "Roronoa Zoro", "One Piece", "1/8", "mid", 180),
        ("MegaHouse", "Portrait of Pirates", "Boa Hancock Ver.BB", "One Piece", "1/8", "high", 350),
        ("Banpresto", "DXF", "Shanks Film Red", "One Piece", "Non-scale", "standard", 25),
        ("Banpresto", "King of Artist", "Portgas D. Ace", "One Piece", "Non-scale", "standard", 35),
        ("Tsume Art", "HQS", "Luffy Gear Fourth Snakeman", "One Piece", "1/4", "grail", 750),

        # ── Fate Series ───────────────────────────────────────────────
        ("Good Smile Company", "Scale", "Saber Altria Pendragon", "Fate/Stay Night", "1/7", "high", 220),
        ("Alter", "Scale", "Saber Alter Dress Ver.", "Fate/Stay Night", "1/7", "grail", 400),
        ("Max Factory", "Scale", "Rider Medusa", "Fate/Stay Night", "1/7", "mid", 180),
        ("Aniplex", "Scale", "Jeanne d'Arc", "Fate/Grand Order", "1/7", "high", 260),
        ("Good Smile Company", "Scale", "Mash Kyrielight", "Fate/Grand Order", "1/7", "mid", 190),

        # ── Evangelion ────────────────────────────────────────────────
        ("Kotobukiya", "Scale", "Rei Ayanami Plugsuit Ver.", "Evangelion", "1/6", "high", 200),
        ("Alter", "Scale", "Asuka Langley Test Plugsuit", "Evangelion", "1/7", "high", 280),
        ("Medicom", "RAH", "Shinji Ikari Plugsuit", "Evangelion", "1/6", "high", 350),
        ("Kotobukiya", "Scale", "Eva Unit-01 Awakening", "Evangelion", "Non-scale", "grail", 500),

        # ── Hatsune Miku / Vocaloid ──────────────────────────────────
        ("Good Smile Company", "Scale", "Hatsune Miku V4X", "Vocaloid", "1/8", "mid", 160),
        ("Max Factory", "Scale", "Hatsune Miku Deep Sea Girl", "Vocaloid", "1/8", "high", 320),
        ("FREEing", "Scale", "Hatsune Miku Bunny Ver.", "Vocaloid", "1/4", "grail", 480),
        ("Good Smile Company", "Scale", "Hatsune Miku Memorial Dress", "Vocaloid", "1/7", "high", 200),
        ("Good Smile Company", "Scale", "Kagamine Rin & Len", "Vocaloid", "1/8", "mid", 180),

        # ── Attack on Titan (8) ───────────────────────────────────────
        ("Good Smile Company", "Scale", "Levi Ackerman", "Attack on Titan", "1/7", "high", 240),
        ("Kotobukiya", "Scale", "Levi Fortitude Ver.", "Attack on Titan", "1/8", "mid", 170),
        ("Sentinel", "Scale", "Levi Brave-Act", "Attack on Titan", "1/8", "high", 210),
        ("Good Smile Company", "Scale", "Eren Yeager Attack Titan", "Attack on Titan", "1/7", "high", 260),
        ("Kotobukiya", "Scale", "Mikasa Ackerman", "Attack on Titan", "1/8", "mid", 160),
        ("Good Smile Company", "Scale", "Colossal Titan", "Attack on Titan", "Non-scale", "grail", 420),
        ("Kotobukiya", "Scale", "Erwin Smith", "Attack on Titan", "1/8", "mid", 150),
        ("Sentinel", "Scale", "Hange Zoe", "Attack on Titan", "1/8", "mid", 185),

        # ── Chainsaw Man (6) ──────────────────────────────────────────
        ("Good Smile Company", "Scale", "Denji", "Chainsaw Man", "1/7", "high", 210),
        ("Kotobukiya", "Scale", "Power", "Chainsaw Man", "1/7", "high", 220),
        ("Good Smile Company", "Scale", "Makima", "Chainsaw Man", "1/7", "high", 230),
        ("FREEing", "Scale", "Power Bunny Ver.", "Chainsaw Man", "1/4", "grail", 460),
        ("Kotobukiya", "Scale", "Pochita Oversized", "Chainsaw Man", "Non-scale", "mid", 85),
        ("Good Smile Company", "Scale", "Denji Chainsaw Devil Form", "Chainsaw Man", "1/8", "high", 280),

        # ── Spy x Family (5) ─────────────────────────────────────────
        ("Good Smile Company", "Scale", "Anya Forger", "Spy x Family", "1/7", "mid", 150),
        ("Alter", "Scale", "Yor Forger Thorn Princess", "Spy x Family", "1/7", "high", 260),
        ("Good Smile Company", "Scale", "Loid Forger", "Spy x Family", "1/8", "mid", 140),
        ("Bandai", "S.H.Figuarts", "Yor Forger Action", "Spy x Family", "Non-scale", "mid", 80),
        ("Kotobukiya", "Scale", "Anya & Bond Forger", "Spy x Family", "1/7", "mid", 170),

        # ── Dragon Ball Z / Super (8) ────────────────────────────────
        ("Banpresto", "Grandista", "Son Goku Super Saiyan", "Dragon Ball Z", "Non-scale", "standard", 40),
        ("Bandai", "S.H.Figuarts", "Goku Ultra Instinct", "Dragon Ball Super", "Non-scale", "mid", 95),
        ("MegaHouse", "Dimension of DRAGONBALL", "Vegeta Galick Gun", "Dragon Ball Z", "Non-scale", "mid", 130),
        ("Tsume Art", "HQS", "Broly Legendary Super Saiyan", "Dragon Ball Z", "1/4", "grail", 850),
        ("Bandai", "S.H.Figuarts", "Vegeta SSBE", "Dragon Ball Super", "Non-scale", "mid", 85),
        ("Banpresto", "Grandista", "Frieza Final Form", "Dragon Ball Z", "Non-scale", "standard", 35),
        ("MegaHouse", "Dimension of DRAGONBALL", "Son Gohan SSJ2", "Dragon Ball Z", "Non-scale", "mid", 140),
        ("Bandai", "S.H.Figuarts", "Goku SSJ4", "Dragon Ball GT", "Non-scale", "mid", 90),

        # ── Naruto (6) ───────────────────────────────────────────────
        ("MegaHouse", "GEM", "Naruto Uzumaki Sage Mode", "Naruto Shippuden", "1/8", "mid", 150),
        ("MegaHouse", "GEM", "Sasuke Uchiha Susanoo", "Naruto Shippuden", "1/8", "high", 200),
        ("Good Smile Company", "Scale", "Kakashi Hatake Anbu Ver.", "Naruto Shippuden", "1/8", "high", 230),
        ("MegaHouse", "GEM", "Itachi Uchiha Tsukuyomi", "Naruto Shippuden", "1/8", "high", 240),
        ("Tsume Art", "HQS", "Naruto Six Paths Sage Mode", "Naruto Shippuden", "1/6", "grail", 680),
        ("Kotobukiya", "Scale", "Minato Namikaze", "Naruto Shippuden", "1/8", "mid", 160),

        # ── My Hero Academia (5) ─────────────────────────────────────
        ("Kotobukiya", "Scale", "Izuku Midoriya Shoot Style", "My Hero Academia", "1/8", "mid", 140),
        ("Good Smile Company", "Scale", "All Might Silver Age", "My Hero Academia", "1/8", "high", 220),
        ("Kotobukiya", "Scale", "Katsuki Bakugo", "My Hero Academia", "1/8", "mid", 135),
        ("Kotobukiya", "Scale", "Shoto Todoroki", "My Hero Academia", "1/8", "mid", 130),
        ("Good Smile Company", "Scale", "Deku Full Cowling Ver.", "My Hero Academia", "1/8", "mid", 180),

        # ── Re:Zero (5) ──────────────────────────────────────────────
        ("Good Smile Company", "Scale", "Rem", "Re:Zero", "1/7", "high", 220),
        ("Good Smile Company", "Scale", "Ram", "Re:Zero", "1/7", "mid", 180),
        ("FREEing", "Scale", "Rem Bunny Ver.", "Re:Zero", "1/4", "grail", 520),
        ("Kadokawa", "Scale", "Emilia Crystal Dress", "Re:Zero", "1/7", "high", 250),
        ("FREEing", "Scale", "Ram Bunny Ver.", "Re:Zero", "1/4", "grail", 480),

        # ── Bleach (4) ───────────────────────────────────────────────
        ("MegaHouse", "GEM", "Ichigo Kurosaki Bankai", "Bleach", "1/8", "mid", 170),
        ("MegaHouse", "GEM", "Rukia Kuchiki", "Bleach", "1/8", "mid", 140),
        ("Banpresto", "Grandista", "Grimmjow Jaegerjaquez", "Bleach", "Non-scale", "standard", 38),
        ("MegaHouse", "GEM", "Aizen Sosuke Hogyoku", "Bleach", "1/8", "mid", 185),

        # ── Gundam (4) ───────────────────────────────────────────────
        ("Bandai", "Robot Spirits", "RX-78-2 Gundam ver. A.N.I.M.E.", "Mobile Suit Gundam", "Non-scale", "mid", 80),
        ("Bandai", "Robot Spirits", "Nu Gundam", "Char's Counterattack", "Non-scale", "mid", 95),
        ("Bandai", "Robot Spirits", "Strike Freedom Gundam", "Gundam SEED Destiny", "Non-scale", "mid", 90),
        ("Bandai", "Metal Build", "Wing Gundam Zero EW", "Gundam Wing", "Non-scale", "high", 280),

        # ── Nendoroids (20) ──────────────────────────────────────────
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
        ("Good Smile Company", "Nendoroid", "Denji Nendoroid", "Chainsaw Man", "Nendoroid", "standard", 55),
        ("Good Smile Company", "Nendoroid", "Makima Nendoroid", "Chainsaw Man", "Nendoroid", "standard", 60),
        ("Good Smile Company", "Nendoroid", "Eren Yeager Nendoroid", "Attack on Titan", "Nendoroid", "standard", 50),
        ("Good Smile Company", "Nendoroid", "Ichigo Kurosaki Nendoroid", "Bleach", "Nendoroid", "standard", 55),
        ("Good Smile Company", "Nendoroid", "Deku Nendoroid", "My Hero Academia", "Nendoroid", "standard", 48),
        ("Good Smile Company", "Nendoroid", "All Might Nendoroid", "My Hero Academia", "Nendoroid", "standard", 55),
        ("Good Smile Company", "Nendoroid", "Goku Nendoroid", "Dragon Ball Z", "Nendoroid", "standard", 50),
        ("Good Smile Company", "Nendoroid", "Emilia Nendoroid", "Re:Zero", "Nendoroid", "standard", 50),
        ("Good Smile Company", "Nendoroid", "Bakugo Nendoroid", "My Hero Academia", "Nendoroid", "standard", 48),
        ("Good Smile Company", "Nendoroid", "Sasuke Uchiha Nendoroid", "Naruto", "Nendoroid", "standard", 55),

        # ── Figma (10) ───────────────────────────────────────────────
        ("Max Factory", "Figma", "Saber 2.0 Figma", "Fate/Stay Night", "Figma", "mid", 80),
        ("Max Factory", "Figma", "Guts Berserker Armor Figma", "Berserk", "Figma", "mid", 120),
        ("Max Factory", "Figma", "Link Twilight Princess Figma", "Zelda", "Figma", "mid", 95),
        ("Max Factory", "Figma", "Mikasa Ackerman Figma", "Attack on Titan", "Figma", "standard", 70),
        ("Max Factory", "Figma", "Denji Figma", "Chainsaw Man", "Figma", "standard", 65),
        ("Max Factory", "Figma", "Levi Ackerman Figma", "Attack on Titan", "Figma", "mid", 85),
        ("Max Factory", "Figma", "Eren Yeager Figma", "Attack on Titan", "Figma", "standard", 70),
        ("Max Factory", "Figma", "Kirito Figma", "Sword Art Online", "Figma", "standard", 65),
        ("Max Factory", "Figma", "Power Figma", "Chainsaw Man", "Figma", "standard", 70),
        ("Max Factory", "Figma", "Naruto Uzumaki Figma", "Naruto Shippuden", "Figma", "standard", 75),

        # ── S.H.Figuarts (6) ─────────────────────────────────────────
        ("Bandai", "S.H.Figuarts", "Goku SSJ God", "Dragon Ball Super", "Non-scale", "mid", 85),
        ("Bandai", "S.H.Figuarts", "Naruto Uzumaki Best Selection", "Naruto Shippuden", "Non-scale", "mid", 80),
        ("Bandai", "S.H.Figuarts", "Monkey D. Luffy Gear 5", "One Piece", "Non-scale", "mid", 90),
        ("Bandai", "S.H.Figuarts", "Broly Full Power", "Dragon Ball Super", "Non-scale", "mid", 100),
        ("Bandai", "S.H.Figuarts", "Kakashi Hatake", "Naruto Shippuden", "Non-scale", "mid", 85),
        ("Bandai", "S.H.Figuarts", "Roronoa Zoro", "One Piece", "Non-scale", "mid", 80),

        # ── Prize Figures - Banpresto ─────────────────────────────────
        ("Banpresto", "Grandista", "Son Goku Manga Dimensions", "Dragon Ball Z", "Non-scale", "standard", 35),
        ("Banpresto", "Grandista", "Vegeta Manga Dimensions", "Dragon Ball Z", "Non-scale", "standard", 30),
        ("Banpresto", "Vibration Stars", "Tanjiro Kamado", "Demon Slayer", "Non-scale", "standard", 22),
        ("Banpresto", "Vibration Stars", "Zenitsu Agatsuma", "Demon Slayer", "Non-scale", "standard", 20),
        ("Banpresto", "Chronicle Master Stars", "Luffy Gear 5", "One Piece", "Non-scale", "standard", 38),

        # ── Garage Kits / Resin ───────────────────────────────────────
        ("E2046", "Garage Kit", "Saber Lily Unpainted GK", "Fate/Stay Night", "1/6", "high", 280),
        ("Hobby Japan", "Garage Kit", "Rei Ayanami GK Unpainted", "Evangelion", "1/6", "high", 320),
        ("Private Studio", "Garage Kit", "Gojo Domain Expansion Resin", "Jujutsu Kaisen", "1/6", "grail", 650),
        ("Private Studio", "Garage Kit", "Luffy Gear 5 Resin Statue", "One Piece", "1/6", "grail", 800),
        ("Private Studio", "Garage Kit", "Tanjiro vs Rui Diorama Resin", "Demon Slayer", "1/8", "grail", 550),

        # ── Prime 1 Studio / Tsume Art - Ultra Grails (5) ────────────
        ("Prime 1 Studio", "Premium Masterline", "Eren Attack Titan", "Attack on Titan", "1/4", "grail", 1200),
        ("Prime 1 Studio", "Premium Masterline", "Guts Berserker Armor", "Berserk", "1/4", "grail", 1350),
        ("Tsume Art", "HQS+", "Naruto vs Sasuke Valley of the End", "Naruto Shippuden", "1/6", "grail", 950),
        ("Tsume Art", "HQS", "All Might United States of Smash", "My Hero Academia", "1/4", "grail", 780),
        ("Prime 1 Studio", "Premium Masterline", "Levi vs Beast Titan", "Attack on Titan", "1/4", "grail", 1100),
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
        "HQS+": 0.97,
        "S.H.Figuarts": 0.6,
        "Robot Spirits": 0.55,
        "Metal Build": 0.75,
        "GEM": 0.7,
        "Dimension of DRAGONBALL": 0.65,
        "Premium Masterline": 0.98,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_scores.get(figure_type, 0.5),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Anime Figures catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Anime Figures Import ===")

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

    logger.info(f"\n=== Anime Figures Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
