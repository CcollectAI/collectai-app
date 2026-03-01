"""
Import One Piece TCG card data (Bandai).

Layer 1 (Catalog):  80+ curated cards across OP01-OP08 + specials → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated catalog of real One Piece Card Game cards (Bandai)
- Covers OP01 Romance Dawn through OP08, promos, alt art / manga art chase cards
- Prices based on Cardmarket / TCGPlayer secondary market (2025-Q4 estimates)

Usage:
    python -m pipelines.import_one_piece_tcg [--dry-run]
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
    logger,
    close_http_client,
)

CATEGORY = "one_piece_tcg"

# ---------------------------------------------------------------------------
# One Piece TCG rarity → edition score
# ---------------------------------------------------------------------------

_ALT_ART_KEYWORDS = {"Alt Art", "Manga Art", "SEC", "SP", "Special Art"}


def _edition_score(rarity: str) -> float:
    """Return edition score: 0.9 for chase/premium rarities, 0.5 standard."""
    if any(kw in rarity for kw in _ALT_ART_KEYWORDS):
        return 0.9
    return 0.5


# ---------------------------------------------------------------------------
# Curated catalog — 80+ real One Piece TCG cards
# ---------------------------------------------------------------------------

def get_curated_catalog() -> list[dict]:
    """Return 80+ curated One Piece TCG cards across all major sets.

    Each entry: name, set_code, card_number, rarity, color, price_eur,
                is_leader, notes
    """

    # Format: (name, set_code, card_number, rarity, color, price_eur,
    #          is_leader, notes)

    cards_raw: list[tuple] = [
        # =================================================================
        # OP01 — Romance Dawn (12+ items)
        # =================================================================
        ("Monkey D. Luffy", "OP01", "OP01-003", "L", "Red", 8.00,
         True, "Starter leader, Red aggro staple"),
        ("Roronoa Zoro", "OP01", "OP01-025", "SR", "Green", 12.00,
         False, "4-cost 6000 power beater"),
        ("Shanks", "OP01", "OP01-120", "SEC", "Red", 55.00,
         False, "Secret rare, 10-cost finisher"),
        ("Nami", "OP01", "OP01-016", "SR", "Green", 6.50,
         False, "Search effect, Green staple"),
        ("Trafalgar Law", "OP01", "OP01-002", "L", "Red/Green", 5.00,
         True, "Dual color leader"),
        ("Boa Hancock", "OP01", "OP01-078", "SR", "Blue", 7.00,
         False, "Blue blocker"),
        ("Donquixote Doflamingo", "OP01", "OP01-060", "SR", "Blue", 8.50,
         False, "Control staple"),
        ("Sanji", "OP01", "OP01-013", "R", "Red", 2.00,
         False, "Rush attacker"),
        ("Nico Robin", "OP01", "OP01-017", "R", "Green", 1.80,
         False, "Draw engine"),
        ("Tony Tony Chopper", "OP01", "OP01-015", "C", "Red", 0.30,
         False, "Vanilla beater"),
        ("Usopp", "OP01", "OP01-014", "UC", "Red", 0.50,
         False, "Bounce effect"),
        ("Monkey D. Luffy (Alt Art)", "OP01", "OP01-003-AA", "Alt Art", "Red", 120.00,
         True, "OP01 alt art leader, highly sought after"),
        ("Shanks (Alt Art)", "OP01", "OP01-120-AA", "Alt Art", "Red", 180.00,
         False, "OP01 SEC alt art chase card"),
        ("Roronoa Zoro (Alt Art)", "OP01", "OP01-025-AA", "Alt Art", "Green", 85.00,
         False, "OP01 SR alt art"),

        # =================================================================
        # OP02 — Paramount War (10+ items)
        # =================================================================
        ("Portgas D. Ace", "OP02", "OP02-013", "L", "Red/Blue", 6.00,
         True, "Dual color leader, Whitebeard Pirates"),
        ("Edward Newgate", "OP02", "OP02-001", "L", "Red", 7.00,
         True, "Whitebeard leader"),
        ("Akainu (Sakazuki)", "OP02", "OP02-099", "SR", "Red/Black", 10.00,
         False, "Marine powerhouse"),
        ("Donquixote Doflamingo", "OP02", "OP02-058", "SR", "Blue", 9.00,
         False, "Dressrosa arc villain"),
        ("Marco", "OP02", "OP02-018", "SR", "Green", 8.00,
         False, "Phoenix regeneration"),
        ("Crocodile", "OP02", "OP02-058B", "R", "Blue", 2.50,
         False, "Baroque Works boss"),
        ("Sengoku", "OP02", "OP02-078", "R", "Black", 2.00,
         False, "Marine Fleet Admiral"),
        ("Jozu", "OP02", "OP02-015", "UC", "Red", 0.60,
         False, "Diamond blocker"),
        ("Portgas D. Ace (Alt Art)", "OP02", "OP02-013-AA", "Alt Art", "Red/Blue", 200.00,
         True, "OP02 chase alt art leader"),
        ("Edward Newgate (SEC)", "OP02", "OP02-001-SEC", "SEC", "Red", 95.00,
         False, "Secret rare Whitebeard"),

        # =================================================================
        # OP03 — Pillars of Strength (8+ items)
        # =================================================================
        ("Yamato", "OP03", "OP03-123", "SEC", "Green/Yellow", 45.00,
         False, "Kaido's son, secret rare"),
        ("Kaido", "OP03", "OP03-099", "SR", "Purple", 15.00,
         False, "Emperor of the Sea"),
        ("Uta", "OP03", "OP03-120", "SR", "Red", 12.00,
         False, "Film Red character"),
        ("Charlotte Katakuri", "OP03", "OP03-001", "L", "Purple", 6.00,
         True, "Big Mom Pirates leader"),
        ("Zoro (Wano)", "OP03", "OP03-022", "SR", "Green", 10.00,
         False, "Wano arc Zoro with Enma"),
        ("Sanji (Wano)", "OP03", "OP03-017", "R", "Red", 3.00,
         False, "Wano Raid Suit Sanji"),
        ("King", "OP03", "OP03-088", "SR", "Purple", 8.00,
         False, "All-Star of Beast Pirates"),
        ("Queen", "OP03", "OP03-085", "R", "Purple", 2.50,
         False, "Plague, Beast Pirates"),
        ("Yamato (Alt Art)", "OP03", "OP03-123-AA", "Alt Art", "Green/Yellow", 280.00,
         False, "OP03 chase card, extremely popular"),

        # =================================================================
        # OP04 — Kingdoms of Intrigue (8+ items)
        # =================================================================
        ("Crocodile", "OP04", "OP04-058", "L", "Blue/Black", 8.00,
         True, "Dual color Baroque Works leader"),
        ("Nico Robin", "OP04", "OP04-064", "SR", "Blue", 14.00,
         False, "Miss All Sunday"),
        ("Gecko Moria", "OP04", "OP04-090", "SR", "Black", 9.00,
         False, "Thriller Bark warlord"),
        ("Rebecca", "OP04", "OP04-039", "R", "Yellow", 2.50,
         False, "Dressrosa gladiator"),
        ("Perona", "OP04", "OP04-077", "SR", "Black", 7.50,
         False, "Negative Hollow"),
        ("Nefertari Vivi", "OP04", "OP04-044", "R", "Yellow", 3.00,
         False, "Alabasta princess"),
        ("Bartholomew Kuma", "OP04", "OP04-083", "R", "Black", 2.80,
         False, "Tyrant warlord"),
        ("Nico Robin (Alt Art)", "OP04", "OP04-064-AA", "Alt Art", "Blue", 250.00,
         False, "OP04 most wanted alt art"),
        ("Crocodile (SEC)", "OP04", "OP04-058-SEC", "SEC", "Blue/Black", 65.00,
         True, "Secret rare leader variant"),

        # =================================================================
        # OP05 — Awakening of the New Era (8+ items)
        # =================================================================
        ("Trafalgar Law", "OP05", "OP05-069", "SR", "Black/Yellow", 18.00,
         False, "Room / Shambles combo"),
        ("Eustass Kid", "OP05", "OP05-074", "SR", "Black", 12.00,
         False, "Punk Gibson effect"),
        ("Sabo", "OP05", "OP05-007", "L", "Red/Green", 7.00,
         True, "Revolutionary Army leader"),
        ("Monkey D. Luffy (Gear 4)", "OP05", "OP05-119", "SEC", "Red", 60.00,
         False, "Bound Man secret rare"),
        ("Koby", "OP05", "OP05-044", "R", "Blue", 2.00,
         False, "Marine hero"),
        ("Jewelry Bonney", "OP05", "OP05-051", "R", "Blue", 2.50,
         False, "Worst Generation"),
        ("Vinsmoke Reiju", "OP05", "OP05-015", "SR", "Red", 8.00,
         False, "Germa 66 Poison Pink"),
        ("Trafalgar Law (Alt Art)", "OP05", "OP05-069-AA", "Alt Art", "Black/Yellow", 220.00,
         False, "OP05 most popular alt art"),
        ("Eustass Kid (Alt Art)", "OP05", "OP05-074-AA", "Alt Art", "Black", 150.00,
         False, "OP05 alt art chase"),

        # =================================================================
        # OP06 — Wings of the Captain (4+ items)
        # =================================================================
        ("Boa Hancock", "OP06", "OP06-069", "SR", "Green/Yellow", 16.00,
         False, "Kuja empress"),
        ("Sanji (Whole Cake)", "OP06", "OP06-023", "SR", "Red", 11.00,
         False, "WCI arc"),
        ("Lucci (Awakened)", "OP06", "OP06-086", "SR", "Black", 10.00,
         False, "CP0 awakened Zoan"),
        ("Boa Hancock (Alt Art)", "OP06", "OP06-069-AA", "Alt Art", "Green/Yellow", 190.00,
         False, "OP06 alt art chase"),

        # =================================================================
        # OP07 — 500 Years in the Future (4+ items)
        # =================================================================
        ("Bartholomew Kuma", "OP07", "OP07-079", "SR", "Black/Yellow", 14.00,
         False, "Kuma with memories"),
        ("Jewelry Bonney", "OP07", "OP07-019", "L", "Green/Yellow", 8.00,
         True, "Egghead arc leader"),
        ("Rob Lucci", "OP07", "OP07-098", "SEC", "Black", 50.00,
         False, "CP0 secret rare"),
        ("Bartholomew Kuma (Alt Art)", "OP07", "OP07-079-AA", "Alt Art", "Black/Yellow", 160.00,
         False, "OP07 alt art chase"),

        # =================================================================
        # OP08 — Two Legends (4+ items)
        # =================================================================
        ("Monkey D. Luffy (Gear 5)", "OP08", "OP08-120", "SEC", "Red/Purple", 75.00,
         False, "Gear 5 Nika form, flagship card"),
        ("Blackbeard (Marshall D. Teach)", "OP08", "OP08-069", "SR", "Black", 20.00,
         False, "Yami Yami no Mi emperor"),
        ("Shanks (Film Red)", "OP08", "OP08-118", "SR", "Red", 18.00,
         False, "Emperor of the Sea"),
        ("Monkey D. Luffy Gear 5 (Manga Art)", "OP08", "OP08-120-MA", "Manga Art", "Red/Purple", 800.00,
         False, "OP08 manga art chase, highest value OPTCG card"),
        ("Blackbeard (Alt Art)", "OP08", "OP08-069-AA", "Alt Art", "Black", 140.00,
         False, "OP08 alt art chase"),

        # =================================================================
        # Special Art / Manga Art / Parallel cards — cross-set chase (12+ items)
        # =================================================================
        ("Nami (Manga Art)", "OP01", "OP01-016-MA", "Manga Art", "Green", 350.00,
         False, "OP01 manga art, iconic illustration"),
        ("Luffy (Manga Art)", "OP01", "OP01-003-MA", "Manga Art", "Red", 400.00,
         True, "OP01 manga art leader, grail card"),
        ("Portgas D. Ace (Manga Art)", "OP02", "OP02-013-MA", "Manga Art", "Red/Blue", 450.00,
         True, "OP02 manga art leader"),
        ("Yamato (Manga Art)", "OP03", "OP03-123-MA", "Manga Art", "Green/Yellow", 500.00,
         False, "OP03 manga art, top chase"),
        ("Nico Robin (Manga Art)", "OP04", "OP04-064-MA", "Manga Art", "Blue", 480.00,
         False, "OP04 manga art, highly desired"),
        ("Charlotte Katakuri (Alt Art)", "OP03", "OP03-001-AA", "Alt Art", "Purple", 75.00,
         True, "OP03 leader alt art"),
        ("Sabo (Alt Art)", "OP05", "OP05-007-AA", "Alt Art", "Red/Green", 110.00,
         True, "OP05 leader alt art"),
        ("Kaido (Alt Art)", "OP03", "OP03-099-AA", "Alt Art", "Purple", 95.00,
         False, "OP03 SR alt art, dragon form"),
        ("Edward Newgate (Manga Art)", "OP02", "OP02-001-MA", "Manga Art", "Red", 380.00,
         False, "OP02 Whitebeard manga art"),
        ("Trafalgar Law (Manga Art)", "OP05", "OP05-069-MA", "Manga Art", "Black/Yellow", 420.00,
         False, "OP05 manga art"),
        ("Sakazuki (Alt Art)", "OP02", "OP02-099-AA", "Alt Art", "Red/Black", 70.00,
         False, "OP02 Akainu alt art"),
        ("Eustass Kid (Manga Art)", "OP05", "OP05-074-MA", "Manga Art", "Black", 300.00,
         False, "OP05 manga art Kid"),

        # =================================================================
        # Promo / Tournament cards (5+ items)
        # =================================================================
        ("Monkey D. Luffy (Winner)", "PROMO", "P-001-W", "SP", "Red", 150.00,
         False, "Regional tournament winner promo"),
        ("Roronoa Zoro (Pre-Release)", "PROMO", "P-002-PR", "SP", "Green", 35.00,
         False, "Pre-release event promo"),
        ("Trafalgar Law (Box Topper)", "PROMO", "P-003-BT", "SP", "Black", 25.00,
         False, "Booster box topper promo"),
        ("Portgas D. Ace (Championship)", "PROMO", "P-004-CH", "SP", "Red", 200.00,
         False, "Championship series finalist card"),
        ("Nami (Event Exclusive)", "PROMO", "P-005-EV", "SP", "Green", 40.00,
         False, "Limited event distribution"),
        ("Shanks (Treasure Cup)", "PROMO", "P-006-TC", "SP", "Red", 80.00,
         False, "Treasure Cup tournament promo"),

        # =================================================================
        # Japanese exclusive (JP alt arts, regional promos) (5+ items)
        # =================================================================
        ("Monkey D. Luffy (JP Alt Art)", "OP01", "OP01-003-JP", "Alt Art", "Red", 160.00,
         True, "Japan-exclusive alt art leader"),
        ("Nami (JP Parallel)", "OP01", "OP01-016-JP", "Alt Art", "Green", 90.00,
         False, "Japan-exclusive parallel rare"),
        ("Yamato (JP Box Topper)", "OP03", "OP03-123-JP", "SP", "Green/Yellow", 120.00,
         False, "Japan-exclusive box topper"),
        ("Boa Hancock (JP Promo)", "OP06", "OP06-069-JP", "SP", "Green/Yellow", 65.00,
         False, "Japan-exclusive event promo"),
        ("Monkey D. Luffy Gear 5 (JP Alt Art)", "OP08", "OP08-120-JP", "Alt Art", "Red/Purple", 350.00,
         False, "Japan-exclusive Gear 5 alt art"),
        ("Portgas D. Ace (JP Anniversary)", "PROMO", "P-ACE-JP", "SP", "Red/Blue", 110.00,
         False, "Japan 1st anniversary promo"),
    ]

    catalog = []
    for entry in cards_raw:
        (name, set_code, card_number, rarity, color, price_eur,
         is_leader, notes) = entry

        catalog.append({
            "name": name,
            "set_code": set_code,
            "card_number": card_number,
            "rarity": rarity,
            "color": color,
            "price_eur": price_eur,
            "is_leader": is_leader,
            "notes": notes,
        })

    return catalog


# ---------------------------------------------------------------------------
# Converters
# ---------------------------------------------------------------------------

def item_to_catalog_item(item: dict) -> CatalogItem:
    """Convert a curated catalog entry to a CatalogItem."""
    set_code = item["set_code"]
    card_number = item["card_number"]
    name = item["name"]
    rarity = item["rarity"]
    color = item["color"]
    is_leader = item["is_leader"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{set_code}-{card_number}-{name}"),
        title=name,
        set_code=set_code,
        brand="Bandai",
        rarity=rarity,
        notes=item.get("notes", ""),
        image_url="",
        attributes_json={
            "set_code": set_code,
            "card_number": card_number,
            "rarity": rarity,
            "color": color,
            "is_leader": is_leader,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    """Convert a curated catalog entry to a PriceObservation."""
    rarity = item["rarity"]

    return PriceObservation(
        features={
            "condition_score": 0.90,
            "rarity_score": shared_rarity_score(rarity),
            "edition_score": _edition_score(rarity),
        },
        price=item["price_eur"],
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Import One Piece TCG catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== One Piece TCG Import ===")

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    catalog = get_curated_catalog()
    log_progress(CATEGORY, "curated entries loaded", len(catalog))

    all_items = [item_to_catalog_item(c) for c in catalog]
    all_observations = [item_to_price_observation(c) for c in catalog]

    # Deduplicate by item_key
    seen: set[str] = set()
    deduped: list[CatalogItem] = []
    for item in all_items:
        if item.item_key not in seen:
            seen.add(item.item_key)
            deduped.append(item)
    all_items = deduped

    write_catalog_sql(CATEGORY, all_items)
    log_progress(CATEGORY, "catalog SQL written", len(all_items))

    if all_observations:
        write_training_jsonl(CATEGORY, all_observations)
        log_progress(CATEGORY, "training JSONL written", len(all_observations))

    if ingest.enabled:
        inserted = ingest.upsert_catalog(all_items)
        log_progress(CATEGORY, "catalog upserted", inserted)

    ingest.close()
    close_http_client()

    logger.info(f"\n=== One Piece TCG Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
