"""
Import Blind Box / Mystery Figure catalog (80+ items).

Layer 1 (Catalog):  Curated blind box figures → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Pop Mart (Labubu, Dimoo, Molly, Skullpanda, Hirono, Crybaby, Zsiga)
- Sonny Angels (fruit, animal, marine, dream, Christmas, Halloween, limited)
- tokidoki (Unicorno, Mermicorno, SANDy, Donutella)
- Kidrobot Dunny (various artists/series)
- Medicom Bearbrick blind box series
- BAIT / Secret Base collaborations
- Regional exclusives (China, Japan, Thailand)
- Vintage / discontinued (early Pop Mart, rare Sonny Angels)

Usage:
    python -m pipelines.import_blind_box [--dry-run]
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

CATEGORY = "blind_box"


def get_curated_catalog() -> list[dict]:
    """Curated blind box catalog covering major brands and subcategories."""

    # (name, brand, series, variant, rarity, price_eur, is_secret, notes)
    # Rarity tiers: Common, Uncommon, Rare, Secret, Ultra Rare, Grail
    # Prices in EUR, reflecting real secondary market values (2024-2026)

    items_raw = [
        # ── Pop Mart — Labubu ───────────────────────────────────────────
        ("Labubu The Monsters Tasty Life", "Pop Mart", "Labubu", "Tasty Life Series", "Common", 14, False, "Standard blind box figure, 12 designs"),
        ("Labubu The Monsters Have a Seat", "Pop Mart", "Labubu", "Have a Seat Series", "Common", 16, False, "Sitting pose series, 12 designs"),
        ("Labubu The Monsters Celebration", "Pop Mart", "Labubu", "Celebration Series", "Common", 15, False, "Party theme series"),
        ("Labubu Macaron Miffy Collab", "Pop Mart", "Labubu", "Miffy Collaboration", "Rare", 85, False, "Pop Mart x Miffy limited collab"),
        ("Labubu The Monsters Space Series Secret", "Pop Mart", "Labubu", "Space Series Secret", "Secret", 180, True, "Secret chase figure, glow-in-dark astronaut"),
        ("Labubu Zimomo Large Artist Series", "Pop Mart", "Labubu", "Artist Collab 400%", "Ultra Rare", 650, False, "Large format artist collaboration"),
        ("Labubu The Monsters Candy Series Secret", "Pop Mart", "Labubu", "Candy Secret", "Secret", 220, True, "Translucent candy variant chase"),
        ("Labubu Exciting Macaron Full Case", "Pop Mart", "Labubu", "Exciting Macaron", "Common", 12, False, "Standard series, 9+1 designs"),

        # ── Pop Mart — Dimoo ────────────────────────────────────────────
        ("Dimoo World Heritage Series", "Pop Mart", "Dimoo", "World Heritage", "Common", 14, False, "Landmark-themed figures"),
        ("Dimoo Fairy Tale Series", "Pop Mart", "Dimoo", "Fairy Tale", "Common", 13, False, "Classic fairy tale designs"),
        ("Dimoo Dating Day Series", "Pop Mart", "Dimoo", "Dating Day", "Common", 14, False, "Romantic theme blind box"),
        ("Dimoo Aquarium Series Secret Whale", "Pop Mart", "Dimoo", "Aquarium Secret", "Secret", 160, True, "Secret whale figure, highly sought"),
        ("Dimoo Midnight Circus Secret", "Pop Mart", "Dimoo", "Midnight Circus Secret", "Secret", 145, True, "Ringmaster secret chase"),

        # ── Pop Mart — Molly ────────────────────────────────────────────
        ("Molly Anniversary Statues Series", "Pop Mart", "Molly", "Anniversary Statues", "Common", 15, False, "Iconic series, 12 designs"),
        ("Molly x Instinctoy Erosion Molly", "Pop Mart", "Molly", "Instinctoy Erosion", "Rare", 180, False, "Artist collab limited edition"),
        ("Space Molly 400% Pinkerton", "Pop Mart", "Molly", "Space Molly 400%", "Ultra Rare", 650, False, "Large format, Pinkerton colorway"),
        ("Space Molly 1000% Jasmine", "Pop Mart", "Molly", "Space Molly 1000%", "Grail", 1800, False, "Mega size, Jasmine theme, extremely limited"),
        ("Molly Bug's World Secret Mantis", "Pop Mart", "Molly", "Bug's World Secret", "Secret", 130, True, "Metallic mantis chase figure"),

        # ── Pop Mart — Skullpanda ───────────────────────────────────────
        ("Skullpanda Night City Series", "Pop Mart", "Skullpanda", "Night City", "Common", 14, False, "Cyberpunk-themed series"),
        ("Skullpanda Tell Me What You Want", "Pop Mart", "Skullpanda", "Tell Me What You Want", "Common", 15, False, "Fashion-themed blind box"),
        ("Skullpanda Ancient Castle Secret", "Pop Mart", "Skullpanda", "Ancient Castle Secret", "Secret", 200, True, "Gothic castle secret chase"),

        # ── Pop Mart — Hirono ───────────────────────────────────────────
        ("Hirono The Other One Series", "Pop Mart", "Hirono", "The Other One", "Common", 16, False, "Dark fantasy theme, 9 designs"),
        ("Hirono Mime Series Secret", "Pop Mart", "Hirono", "Mime Secret", "Secret", 250, True, "Mime secret figure with mirror base"),
        ("Hirono Little Mischief Series", "Pop Mart", "Hirono", "Little Mischief", "Common", 15, False, "Playful mischief theme"),

        # ── Pop Mart — Crybaby ──────────────────────────────────────────
        ("Crybaby Crying in the Rain", "Pop Mart", "Crybaby", "Crying in the Rain", "Common", 14, False, "Rain theme series by Molly's creator"),
        ("Crybaby Monster Tears Secret", "Pop Mart", "Crybaby", "Monster Tears Secret", "Secret", 170, True, "Monster variant secret figure"),
        ("Crybaby Jungle Adventure Series", "Pop Mart", "Crybaby", "Jungle Adventure", "Common", 14, False, "Jungle explorer theme"),

        # ── Pop Mart — Zsiga ────────────────────────────────────────────
        ("Zsiga Walking Into the Forest", "Pop Mart", "Zsiga", "Forest Series", "Common", 15, False, "Forest creature designs"),
        ("Zsiga Second Generation I'm Not Me", "Pop Mart", "Zsiga", "I'm Not Me", "Common", 15, False, "Identity theme, 12 designs"),

        # ── Sonny Angels — Fruit ────────────────────────────────────────
        ("Sonny Angel Fruit Series Watermelon", "Sonny Angel", "Fruit Series", "Watermelon", "Common", 10, False, "Classic fruit hat figure"),
        ("Sonny Angel Fruit Series Strawberry", "Sonny Angel", "Fruit Series", "Strawberry", "Common", 10, False, "Iconic pink strawberry hat"),
        ("Sonny Angel Fruit Series Banana", "Sonny Angel", "Fruit Series", "Banana", "Common", 10, False, "Yellow banana hat figure"),
        ("Sonny Angel Fruit Series Robbie Secret", "Sonny Angel", "Fruit Series", "Robbie Secret", "Secret", 120, True, "Secret Robbie figure from fruit series"),

        # ── Sonny Angels — Animal ───────────────────────────────────────
        ("Sonny Angel Animal Series 4 Cat", "Sonny Angel", "Animal Series 4", "Cat", "Common", 11, False, "Cat costume angel baby"),
        ("Sonny Angel Animal Series 4 Rabbit", "Sonny Angel", "Animal Series 4", "Rabbit", "Common", 11, False, "Rabbit costume figure"),
        ("Sonny Angel Animal Series 4 Panda", "Sonny Angel", "Animal Series 4", "Panda", "Common", 11, False, "Panda costume figure"),
        ("Sonny Angel Animal Series 3 Elephant Robbie", "Sonny Angel", "Animal Series 3", "Elephant Robbie Secret", "Secret", 100, True, "Secret Robbie elephant variant"),

        # ── Sonny Angels — Marine ───────────────────────────────────────
        ("Sonny Angel Marine Series Clownfish", "Sonny Angel", "Marine Series", "Clownfish", "Common", 11, False, "Ocean creature hat"),
        ("Sonny Angel Marine Series Sea Otter", "Sonny Angel", "Marine Series", "Sea Otter", "Common", 11, False, "Otter costume figure"),
        ("Sonny Angel Marine Series Whale Shark Secret", "Sonny Angel", "Marine Series", "Whale Shark Secret", "Secret", 110, True, "Secret whale shark chase figure"),

        # ── Sonny Angels — Dream / Seasonal / Limited ───────────────────
        ("Sonny Angel Dream Series Cloud", "Sonny Angel", "Dream Series", "Cloud", "Uncommon", 18, False, "Dreamy cloud hat, pastel colors"),
        ("Sonny Angel Christmas 2023 Reindeer", "Sonny Angel", "Christmas 2023", "Reindeer", "Rare", 35, False, "Seasonal Christmas edition"),
        ("Sonny Angel Christmas 2023 Santa Secret", "Sonny Angel", "Christmas 2023", "Santa Secret", "Secret", 140, True, "Secret Santa chase figure"),
        ("Sonny Angel Halloween 2023 Pumpkin", "Sonny Angel", "Halloween 2023", "Pumpkin", "Rare", 30, False, "Seasonal Halloween edition"),
        ("Sonny Angel Halloween 2023 Ghost Secret", "Sonny Angel", "Halloween 2023", "Ghost Secret", "Secret", 130, True, "Translucent ghost secret figure"),
        ("Sonny Angel 20th Anniversary Crown", "Sonny Angel", "20th Anniversary", "Crown Limited", "Ultra Rare", 280, False, "Gold crown limited anniversary edition"),
        ("Sonny Angel Hippers Looking Back Cat", "Sonny Angel", "Hippers Series", "Looking Back Cat", "Rare", 45, False, "Hippers sitting pose series"),

        # ── tokidoki — Unicorno ─────────────────────────────────────────
        ("Unicorno Series 12 Starlight", "tokidoki", "Unicorno Series 12", "Starlight", "Common", 12, False, "Galaxy-themed unicorn blind box"),
        ("Unicorno Series 12 Cosmo Chase", "tokidoki", "Unicorno Series 12", "Cosmo Chase", "Rare", 55, True, "Chase variant with metallic finish"),
        ("Unicorno Metallico Series Chrome Pegasus", "tokidoki", "Unicorno Metallico", "Chrome Pegasus", "Rare", 65, False, "Full chrome metallic figure"),
        ("Unicorno Cherry Blossom Series Sakura", "tokidoki", "Unicorno Cherry Blossom", "Sakura", "Common", 13, False, "Japanese cherry blossom theme"),
        ("Unicorno x Hello Kitty Collab", "tokidoki", "Unicorno x Sanrio", "Hello Kitty", "Rare", 70, False, "Sanrio crossover limited edition"),

        # ── tokidoki — Mermicorno ───────────────────────────────────────
        ("Mermicorno Series 7 Coral", "tokidoki", "Mermicorno Series 7", "Coral", "Common", 12, False, "Mermaid unicorn ocean theme"),
        ("Mermicorno Series 7 Abyssal Chase", "tokidoki", "Mermicorno Series 7", "Abyssal Chase", "Rare", 50, True, "Deep sea chase variant"),
        ("Mermicorno Series 6 Pearl", "tokidoki", "Mermicorno Series 6", "Pearl", "Common", 11, False, "Pearl shimmer finish"),

        # ── tokidoki — SANDy / Donutella ────────────────────────────────
        ("SANDy Fantasy Series Castle", "tokidoki", "SANDy Fantasy", "Castle", "Common", 13, False, "Sand castle character figure"),
        ("Donutella and Her Sweet Friends Series 3 Choco", "tokidoki", "Donutella Series 3", "Choco", "Common", 11, False, "Donut-themed character"),
        ("Donutella Series 3 Golden Glaze Chase", "tokidoki", "Donutella Series 3", "Golden Glaze Chase", "Rare", 60, True, "Gold metallic donut chase"),

        # ── Kidrobot Dunny ──────────────────────────────────────────────
        ("Dunny Series 2024 Full Case", "Kidrobot", "Dunny Series 2024", "Full Case", "Common", 85, False, "20-piece sealed case, 16 designs + chases"),
        ("Dunny 8-inch Huck Gee Gold Life", "Kidrobot", "Dunny Artist", "Huck Gee Gold Life", "Rare", 280, False, "Artist series by Huck Gee"),
        ("Dunny 8-inch Kronk Wild Ones", "Kidrobot", "Dunny Artist", "Kronk Wild Ones", "Rare", 180, False, "Kronk artist collaboration"),
        ("Dunny 3-inch Azteca II Chase", "Kidrobot", "Dunny Azteca II", "Chase Figure", "Secret", 150, True, "Azteca II secret chase figure"),
        ("Dunny 3-inch Andy Warhol Series 2", "Kidrobot", "Dunny Warhol", "Series 2 Blind Box", "Common", 18, False, "Warhol pop art designs"),
        ("Dunny 8-inch Jean-Michel Basquiat", "Kidrobot", "Dunny Artist", "Basquiat Masterpiece", "Rare", 220, False, "Basquiat art collaboration"),
        ("Dunny 3-inch City Cryptid Mothman Chase", "Kidrobot", "Dunny City Cryptid", "Mothman Chase", "Secret", 130, True, "Glow-in-dark Mothman secret"),
        ("Dunny Evolved Series Full Case", "Kidrobot", "Dunny Evolved", "Full Case", "Common", 90, False, "Evolution theme, sealed case"),

        # ── Medicom Bearbrick Blind Boxes ───────────────────────────────
        ("Bearbrick Series 46 Sealed Case", "Medicom", "Bearbrick Series 46", "Sealed Case", "Common", 95, False, "24-piece sealed case, 100% size"),
        ("Bearbrick Series 45 Sealed Case", "Medicom", "Bearbrick Series 45", "Sealed Case", "Common", 90, False, "24-piece sealed case"),
        ("Bearbrick Series 44 Artist Chase", "Medicom", "Bearbrick Series 44", "Artist Chase", "Secret", 160, True, "Secret artist collaboration piece"),
        ("Bearbrick Series 43 Horror Chase", "Medicom", "Bearbrick Series 43", "Horror Chase", "Secret", 140, True, "Horror theme secret figure"),
        ("Bearbrick Series 42 SF Chase", "Medicom", "Bearbrick Series 42", "Science Fiction Chase", "Secret", 135, True, "Sci-fi theme secret figure"),

        # ── BAIT / Secret Base Collaborations ───────────────────────────
        ("BAIT x Secret Base Skull Bee Clear Blue", "BAIT", "Secret Base Collab", "Skull Bee Clear Blue", "Rare", 350, False, "BAIT exclusive clear blue colorway"),
        ("BAIT x Kidrobot Dunny Street Fighter Akuma", "BAIT", "Kidrobot Collab", "Street Fighter Akuma", "Rare", 180, False, "BAIT exclusive SF collab"),
        ("Secret Base Ghost Bear BAIT Glow Edition", "Secret Base", "Ghost Bear", "BAIT Glow Edition", "Ultra Rare", 450, False, "Glow-in-dark BAIT exclusive"),
        ("BAIT x tokidoki Unicorno SDCC Black", "BAIT", "tokidoki Collab", "Unicorno SDCC Black", "Rare", 120, False, "San Diego Comic Con exclusive"),
        ("Secret Base Honey Bear Gold Chrome", "Secret Base", "Honey Bear", "Gold Chrome", "Grail", 900, False, "Limited gold chrome colorway, 100 pieces"),

        # ── Regional Exclusives — China ─────────────────────────────────
        ("Pop Mart Dimoo Hanfu Series China Exclusive", "Pop Mart", "Dimoo Hanfu", "China Exclusive", "Rare", 45, False, "China mainland exclusive Hanfu theme"),
        ("Pop Mart Labubu Year of Dragon Gold", "Pop Mart", "Labubu Zodiac", "Dragon Gold China", "Ultra Rare", 380, False, "Chinese New Year 2024, gold dragon, China-only"),
        ("52TOYS Panda Roll Beach Series", "52TOYS", "Panda Roll", "Beach Series", "Common", 10, False, "Chinese brand, panda theme blind box"),
        ("FINDING UNICORN Shinwoo Ghost Bear Pink", "Finding Unicorn", "Shinwoo Ghost Bear", "Pink China Exclusive", "Rare", 55, False, "Chinese designer toy brand exclusive"),

        # ── Regional Exclusives — Japan ─────────────────────────────────
        ("Sonny Angel Kewpie Collab Japan Only", "Sonny Angel", "Kewpie Collab", "Japan Exclusive", "Rare", 65, False, "Japan domestic market only release"),
        ("Pop Mart Labubu Maneki Neko Japan Exclusive", "Pop Mart", "Labubu Maneki Neko", "Japan Pop-Up Exclusive", "Rare", 85, False, "Lucky cat theme, Japan pop-up store only"),
        ("Medicom Bearbrick Series 44 Fujiko F Fujio Japan", "Medicom", "Bearbrick Japan", "Fujiko F Fujio", "Rare", 75, False, "Japan-exclusive Doraemon artist figure"),

        # ── Regional Exclusives — Thailand / SEA ────────────────────────
        ("Pop Mart Crybaby Songkran Festival Thailand", "Pop Mart", "Crybaby Songkran", "Thailand Exclusive", "Rare", 70, False, "Thai Songkran water festival edition"),
        ("Pop Mart Labubu Thai Tea Series Bangkok", "Pop Mart", "Labubu Thai Tea", "Bangkok Pop-Up", "Rare", 60, False, "Bangkok store exclusive, milk tea theme"),
        ("Sank Toys Good Night Series Thailand Release", "Sank Toys", "Good Night", "Thailand Release", "Uncommon", 25, False, "Thai market exclusive sleeping figures"),

        # ── Vintage / Discontinued — Early Pop Mart ─────────────────────
        ("Molly Kennyswork 1st Edition 2006 OG", "Pop Mart", "Molly OG", "1st Edition 2006", "Grail", 1200, False, "Original Molly by Kenny Wong before Pop Mart, extremely rare"),
        ("Dimoo World Series 1st Run 2019", "Pop Mart", "Dimoo World V1", "1st Run 2019", "Rare", 120, False, "First Dimoo blind box run, discontinued"),
        ("Pucky Sleeping Forest 1st Edition", "Pop Mart", "Pucky Sleeping Forest V1", "1st Edition", "Rare", 95, False, "First Pucky series, 2019 original run"),
        ("Labubu The Monsters Series 1 OG 2019", "Pop Mart", "Labubu OG", "Series 1 Original 2019", "Ultra Rare", 350, False, "First Labubu blind box, now discontinued"),
        ("Space Molly 1000% Shark 2021", "Pop Mart", "Space Molly 1000%", "Shark 2021 Edition", "Grail", 2000, False, "Sold out instantly, extreme secondary market premium"),

        # ── Vintage / Discontinued — Rare Sonny Angels ──────────────────
        ("Sonny Angel Mini Figure 2004 1st Release Cupid", "Sonny Angel", "Original 2004", "Cupid 1st Release", "Grail", 450, False, "First-ever Sonny Angel release, museum piece"),
        ("Sonny Angel Valentine 2012 Chocolate", "Sonny Angel", "Valentine 2012", "Chocolate", "Ultra Rare", 200, False, "Early Valentine limited, long discontinued"),
        ("Sonny Angel Cherry Blossom 2015 Limited", "Sonny Angel", "Cherry Blossom 2015", "Sakura Limited", "Ultra Rare", 180, False, "Japan spring limited, highly collectible"),
        ("Sonny Angel Artist Collection Isetan Mitsukoshi", "Sonny Angel", "Artist Collection", "Isetan Exclusive", "Grail", 380, False, "Department store exclusive artist collab, 500 pcs"),
        ("Sonny Angel Robbie Angel Crown Gold", "Sonny Angel", "Robbie Angel", "Crown Gold", "Grail", 550, False, "Rarest Robbie variant, gold crown, under 200 made"),
    ]

    catalog = []
    for name, brand, series, variant, rarity, price_eur, is_secret, notes in items_raw:
        catalog.append({
            "name": name,
            "brand": brand,
            "series": series,
            "variant": variant,
            "rarity": rarity,
            "price_eur": price_eur,
            "is_secret": is_secret,
            "notes": notes,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    brand = item["brand"]
    series = item["series"]
    name = item["name"]
    variant = item["variant"]
    rarity = item["rarity"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{brand}-{series}-{name}"),
        title=name,
        set_code=slugify(series),
        brand=brand,
        rarity=rarity,
        notes=item["notes"],
        attributes_json={
            "brand": brand,
            "series": series,
            "variant": variant,
            "is_secret": item["is_secret"],
        },
    )


_BLIND_BOX_RARITY: dict[str, float] = {
    "Common": 0.1,
    "Uncommon": 0.3,
    "Rare": 0.5,
    "Secret": 0.85,
    "Ultra Rare": 0.8,
    "Grail": 0.95,
}


def _blind_box_rarity_score(rarity: str) -> float:
    """Map blind-box rarity tiers to 0-1 score, falling back to shared map."""
    if rarity in _BLIND_BOX_RARITY:
        return _BLIND_BOX_RARITY[rarity]
    return shared_rarity_score(rarity)


def item_to_price_observation(item: dict) -> PriceObservation:
    rarity = item["rarity"]
    is_secret = item["is_secret"]

    return PriceObservation(
        features={
            "condition_score": 0.90,
            "rarity_score": _blind_box_rarity_score(rarity),
            "edition_score": 0.8 if is_secret else 0.3,
            "is_secret": 1.0 if is_secret else 0.0,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Blind Box catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Blind Box Import ===")

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
    close_http_client()

    logger.info(f"\n=== Blind Box Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
