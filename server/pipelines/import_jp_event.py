"""
Import Japanese event exclusives catalog.

Layer 1 (Catalog):  Curated JP event-exclusive goods → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Wonder Festival (WonFes): garage kits, exclusive figures
- Comiket: doujinshi, tapestries, acrylic stands, exclusive goods
- AnimeJapan: exclusive goods, clear files, badges, stage goods
- Tamashii Nations event: exclusive figures, anniversary items
- Jump Festa exclusives
- Tokyo Game Show (TGS): game merch, collab goods
- Character1 / Chara Expo: acrylic stands, trading cards
- Anime Expo (US crossover): JP publisher collab exclusives
- Key franchises: Fate, Vocaloid, Love Live, Gundam, Hololive, Touhou

Usage:
    python -m pipelines.import_jp_event [--dry-run]
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

CATEGORY = "jp_event"


def get_curated_catalog() -> list[dict]:
    """Curated Japanese event exclusives catalog (65+ items)."""

    # (event, franchise, item_type, name, rarity_tier, price_eur)
    # rarity_tier: grail (>300), high (100-300), mid (30-100), standard (<30)

    items = [
        # Wonder Festival (WonFes) – garage kits & exclusive figures
        ("WonFes", "Fate/Grand Order", "Garage Kit", "Saber Artoria Pendragon 1/6 GK (Unpainted)", "grail", 350),
        ("WonFes", "Evangelion", "Garage Kit", "EVA Unit-02 Beast Mode 1/8 GK (Unpainted)", "high", 280),
        ("WonFes", "Vocaloid", "Exclusive Figure", "Hatsune Miku WonFes 2023 Exclusive Nendoroid", "high", 120),
        ("WonFes", "Fate/Grand Order", "Exclusive Figure", "Mash Kyrielight WonFes Limited 1/7", "high", 180),
        ("WonFes", "Gundam", "Garage Kit", "Sazabi Ver.Ka 1/100 Resin Conversion GK", "grail", 450),
        ("WonFes", "Original", "Garage Kit", "WonFes Original Character 1/6 GK Limited 20pcs", "grail", 500),
        ("WonFes", "Chainsaw Man", "Exclusive Figure", "Power WonFes Limited Painted GK", "high", 250),

        # Comiket – doujinshi, tapestries, acrylic stands
        ("Comiket", "Fate/Grand Order", "Tapestry", "FGO Comiket 103 Exclusive B2 Tapestry Castoria", "mid", 45),
        ("Comiket", "Touhou Project", "Doujinshi Set", "Touhou C103 Popular Circle Doujinshi Bundle (5)", "mid", 40),
        ("Comiket", "Hololive", "Acrylic Stand", "Hololive C103 Exclusive Acrylic Stand Set", "mid", 35),
        ("Comiket", "Love Live!", "Tapestry", "Love Live! Sunshine!! Comiket Summer Tapestry", "mid", 40),
        ("Comiket", "Vocaloid", "Art Book", "Hatsune Miku 15th Anniversary Doujin Art Book", "mid", 30),
        ("Comiket", "Original", "Tapestry", "Comiket Limited Original Character B2 Tapestry", "standard", 25),
        ("Comiket", "Various", "Badge Set", "Comiket Corporate Booth Badge Random Set (10)", "standard", 15),
        ("Comiket", "Fate/Grand Order", "Acrylic Stand", "FGO Comiket Exclusive Acrylic Diorama Set", "high", 100),

        # AnimeJapan – exclusive goods
        ("AnimeJapan", "Demon Slayer", "Clear File", "Demon Slayer AnimeJapan Exclusive Clear File Set", "standard", 15),
        ("AnimeJapan", "Spy x Family", "Acrylic Stand", "Spy x Family AnimeJapan 2024 Acrylic Stand Trio", "standard", 20),
        ("AnimeJapan", "Jujutsu Kaisen", "Badge Set", "JJK AnimeJapan Random Badge Collection (8pc)", "standard", 18),
        ("AnimeJapan", "Gundam", "Clear File", "Gundam Seed Freedom AnimeJapan Clear File Pair", "standard", 10),
        ("AnimeJapan", "My Hero Academia", "Mini Poster Set", "MHA AnimeJapan Exclusive Mini Poster Set (5)", "mid", 30),
        ("AnimeJapan", "Attack on Titan", "Acrylic Stand", "AoT Final Season AnimeJapan Acrylic Diorama", "mid", 45),

        # Tamashii Nations Event – exclusive figures
        ("Tamashii Nations", "Dragon Ball Z", "S.H.Figuarts", "SSJ Vegito Event Exclusive S.H.Figuarts", "high", 150),
        ("Tamashii Nations", "Kamen Rider", "S.H.Figuarts", "Kamen Rider Black Sun Event Exclusive", "high", 130),
        ("Tamashii Nations", "Gundam", "Robot Spirits", "Gundam Aerial Permet Score 6 Event Exclusive", "high", 110),
        ("Tamashii Nations", "One Piece", "Figuarts ZERO", "Kaido Dragon Form Event Exclusive", "high", 180),
        ("Tamashii Nations", "Evangelion", "Metal Build", "EVA Unit-01 Metal Build Event Color Ver.", "grail", 350),

        # Jump Festa exclusives
        ("Jump Festa", "One Piece", "Figure", "Luffy Gear 5 Jump Festa Exclusive Figure", "high", 100),
        ("Jump Festa", "Dragon Ball Super", "Clear File", "DBS Super Hero Jump Festa Clear File Set", "standard", 15),
        ("Jump Festa", "My Hero Academia", "Acrylic Stand", "Deku vs Shigaraki Jump Festa Acrylic Stand", "mid", 35),
        ("Jump Festa", "Jujutsu Kaisen", "Poster Set", "JJK Jump Festa 2024 Exclusive Poster Set", "mid", 40),
        ("Jump Festa", "Chainsaw Man", "Badge Set", "CSM Jump Festa Random Badge Set (6pc)", "standard", 20),

        # === NEW ITEMS (35+) ===

        # More WonFes – garage kits & exclusive figures (+6)
        ("WonFes", "Touhou Project", "Garage Kit", "Reimu Hakurei 1/6 Resin GK WonFes Limited", "grail", 380),
        ("WonFes", "Kantai Collection", "Exclusive Figure", "Shimakaze WonFes Exclusive 1/7 Painted GK", "high", 220),
        ("WonFes", "Re:Zero", "Garage Kit", "Rem Oni Form 1/6 GK WonFes Unpainted", "high", 260),
        ("WonFes", "Chainsaw Man", "Garage Kit", "Makima Control Devil 1/7 Resin GK Limited 30pcs", "grail", 420),
        ("WonFes", "Spy x Family", "Exclusive Figure", "Yor Forger Thorn Princess WonFes Exclusive 1/7", "high", 190),
        ("WonFes", "Jujutsu Kaisen", "Exclusive Figure", "Gojo Satoru Hollow Purple WonFes Limited GK", "high", 280),

        # More Comiket – doujinshi, music, tapestries, exclusive goods (+6)
        ("Comiket", "Hololive", "Doujinshi Set", "Hololive C104 Popular Circle Doujinshi Bundle (5)", "mid", 50),
        ("Comiket", "Touhou Project", "Music Album", "Touhou Arrange Album C103 Compilation CD Set (3)", "mid", 35),
        ("Comiket", "Fate/Grand Order", "Doujinshi Set", "FGO Comiket 104 Top Circle Doujinshi Bundle (5)", "mid", 55),
        ("Comiket", "Various", "Tapestry", "Comiket C104 Corporate Exclusive B1 Tapestry", "high", 100),
        ("Comiket", "Type-Moon", "Exclusive Goods", "Type-Moon C103 Limited Goods Set (Poster + Clearfile + Badge)", "high", 120),
        ("Comiket", "Various", "Goods Set", "C104 Limited Corporate Booth Exclusive Goods Bag", "mid", 65),

        # Jump Festa – exclusive figures, cards, goods (+5)
        ("Jump Festa", "One Piece", "Exclusive Figure", "Shanks Film Red Jump Festa 2024 Exclusive Figure", "high", 130),
        ("Jump Festa", "Dragon Ball Super", "Exclusive Card", "DBS Card Game Jump Festa Promo SP Pack (5 cards)", "mid", 60),
        ("Jump Festa", "My Hero Academia", "Exclusive Figure", "All Might Jump Festa 2024 Exclusive Mini Figure", "mid", 45),
        ("Jump Festa", "Jujutsu Kaisen", "Goods Set", "JJK Jump Festa 2024 Exclusive Goods Set (Towel + Badge + Clearfile)", "mid", 50),
        ("Jump Festa", "Bleach", "Exclusive Figure", "Ichigo TYBW Bankai Jump Festa Exclusive Figure", "high", 110),

        # AnimeJapan – stage goods, clear files, exhibit goods (+5)
        ("AnimeJapan", "Demon Slayer", "Stage Goods", "Demon Slayer Hashira Stage Event Exclusive Towel Set", "mid", 40),
        ("AnimeJapan", "Chainsaw Man", "Clear File Set", "CSM AnimeJapan 2024 Clear File Collection (6pc)", "standard", 22),
        ("AnimeJapan", "Spy x Family", "Exclusive Figure", "Anya Forger AnimeJapan Exclusive Chibi Figure", "mid", 55),
        ("AnimeJapan", "Gundam", "Exhibit Goods", "Gundam NEXT FUTURE Exhibition Exclusive Model Kit", "high", 150),
        ("AnimeJapan", "Attack on Titan", "Exhibit Goods", "AoT Final Exhibition Memorial Acrylic Art Panel", "high", 120),

        # Tamashii Nations Event – exclusive figures, anniversary items (+4)
        ("Tamashii Nations", "Dragon Ball Z", "S.H.Figuarts", "SSGSS Gogeta Event Exclusive S.H.Figuarts", "high", 160),
        ("Tamashii Nations", "Gundam", "Metal Build", "Strike Freedom Metal Build Event Prototype Color", "grail", 400),
        ("Tamashii Nations", "Kamen Rider", "Robot Spirits", "Kamen Rider Geats Boost Mk.IX Robot Spirits Limited", "high", 120),
        ("Tamashii Nations", "Various", "Anniversary Figure", "Tamashii Nations 25th Anniversary Exclusive Figure Set", "grail", 320),

        # Tokyo Game Show (TGS) – game merch, figure exclusives, collab goods (+4)
        ("Tokyo Game Show", "Final Fantasy", "Exclusive Figure", "Cloud Strife TGS 2024 Exclusive Play Arts Kai Mini", "high", 140),
        ("Tokyo Game Show", "Persona 5", "Exclusive Merch", "Persona 5 Royal TGS Exclusive Acrylic Stand Set (4)", "mid", 35),
        ("Tokyo Game Show", "Monster Hunter", "Collab Goods", "Monster Hunter Wilds TGS Limited Plush Palico", "mid", 45),
        ("Tokyo Game Show", "NieR:Automata", "Exclusive Figure", "2B TGS Exclusive Mini Figure with Base", "high", 110),

        # Character1 / Chara Expo – cosplay prizes, acrylic stands, trading cards (+3)
        ("Character1", "Various", "Acrylic Stand Set", "Character1 2024 Limited Acrylic Stand Collection (8pc)", "mid", 40),
        ("Character1", "Various", "Trading Cards", "Character1 Exclusive Trading Card Sealed Box (20 packs)", "mid", 55),
        ("Chara Expo", "Various", "Cosplay Prize", "Chara Expo Grand Prix Winner Exclusive Signed Print", "high", 180),

        # Anime Expo (US crossover with JP publishers) (+2)
        ("Anime Expo", "Fate/Grand Order", "Exclusive Figure", "Saber Alter AX 2024 Exclusive 1/7 (Aniplex Booth)", "high", 200),
        ("Anime Expo", "Demon Slayer", "Collab Goods", "Demon Slayer x Anime Expo Exclusive Art Print Set (3)", "mid", 65),
    ]

    catalog = []
    for event, franchise, item_type, name, tier, price in items:
        catalog.append({
            "event": event,
            "franchise": franchise,
            "item_type": item_type,
            "name": name,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    event = item["event"]
    name = item["name"]
    franchise = item["franchise"]
    item_type = item["item_type"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{event}-{name}"),
        title=name,
        set_code=slugify(event),
        brand=event,
        rarity=item["rarity_tier"].title(),
        notes=f"{event} | {franchise} | {item_type}",
        attributes_json={
            "event": event,
            "franchise": franchise,
            "item_type": item_type,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    event = item["event"]
    edition_scores = {
        "WonFes": 0.90,
        "Comiket": 0.70,
        "AnimeJapan": 0.50,
        "Tamashii Nations": 0.85,
        "Jump Festa": 0.65,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_scores.get(event, 0.5),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import JP event exclusives catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== JP Event Exclusives Import ===")

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

    logger.info(f"\n=== JP Event Exclusives Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
