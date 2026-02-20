"""
Import Sports Cards catalog — 120+ items across 9 categories.

Layer 1 (Catalog):  Iconic cards across sports → category_items
Layer 2 (Prices):   Market estimates → train.jsonl

Categories: Basketball, Baseball, Football, Soccer, Hockey,
            UFC/MMA, F1/Racing, Sealed Product/Boxes.

Sources: Curated database of high-value sports cards.
Can be augmented with eBay API, TCDB.com, 130point.com later.

Usage:
    python -m pipelines.import_sportscards [--dry-run]
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

CATEGORY = "sportscards"


def get_curated_catalog() -> list[dict]:
    """Curated sports cards catalog — 120+ items across 9 categories.

    Sports covered: Basketball, Baseball, Football (NFL), Soccer,
    Hockey (NHL), UFC/MMA, F1/Racing, and Sealed Product/Boxes.
    All prices in EUR.
    """

    # (sport, year, set_name, player, card_number, variant, raw_price, psa10_price, rarity)
    cards = [
        # ── Basketball (30 items) ────────────────────────────────────────
        ("Basketball", "1986", "Fleer", "Michael Jordan", "57", "Base", 3000, 50000, "Iconic"),
        ("Basketball", "2003", "Topps Chrome", "LeBron James", "111", "Refractor", 5000, 80000, "Iconic"),
        ("Basketball", "2009", "Panini National Treasures", "Stephen Curry", "206", "RPA /99", 15000, 100000, "Ultra Rare"),
        ("Basketball", "1996", "Topps Chrome", "Kobe Bryant", "138", "Refractor", 4000, 60000, "Iconic"),
        ("Basketball", "2018", "Panini Prizm", "Luka Doncic", "280", "Silver Prizm", 500, 8000, "High"),
        ("Basketball", "2019", "Panini Prizm", "Zion Williamson", "248", "Base", 50, 800, "Mid"),
        ("Basketball", "2020", "Panini Prizm", "Anthony Edwards", "258", "Silver Prizm", 200, 3000, "High"),
        ("Basketball", "1969", "Topps", "Lew Alcindor (Kareem)", "25", "Base", 1500, 25000, "Iconic"),
        ("Basketball", "1961", "Fleer", "Wilt Chamberlain", "8", "Base", 2000, 30000, "Iconic"),
        ("Basketball", "2022", "Panini Prizm", "Victor Wembanyama", "275", "Silver Prizm", 300, 5000, "High"),
        ("Basketball", "2013", "Panini Prizm", "Giannis Antetokounmpo", "290", "Silver Prizm RC", 800, 12000, "High"),
        ("Basketball", "2019", "Panini Prizm", "Ja Morant", "249", "Silver Prizm RC", 300, 5000, "High"),
        ("Basketball", "2017", "Panini Prizm", "Jayson Tatum", "16", "Silver Prizm RC", 400, 6000, "High"),
        ("Basketball", "2015", "Panini Prizm", "Devin Booker", "308", "Silver Prizm RC", 250, 4000, "High"),
        ("Basketball", "2007", "Topps Chrome", "Kevin Durant", "131", "Refractor RC", 2000, 30000, "Iconic"),
        ("Basketball", "1997", "Topps Chrome", "Tim Duncan", "115", "Refractor RC", 1000, 15000, "Iconic"),
        ("Basketball", "1992", "Topps", "Shaquille O'Neal", "362", "Base RC", 30, 800, "Mid"),
        ("Basketball", "1980", "Topps", "Larry Bird", "34", "Base RC", 500, 8000, "Iconic"),
        ("Basketball", "1980", "Topps", "Magic Johnson", "139", "Base RC", 400, 7000, "Iconic"),
        ("Basketball", "1957", "Topps", "Bill Russell", "77", "Base RC", 5000, 60000, "Legendary"),
        ("Basketball", "1996", "Topps Chrome", "Allen Iverson", "171", "Refractor RC", 600, 10000, "High"),
        ("Basketball", "1998", "Topps Chrome", "Dirk Nowitzki", "154", "Refractor RC", 500, 8000, "High"),
        ("Basketball", "1995", "Topps Chrome", "Kevin Garnett", "237", "Refractor RC", 400, 6000, "High"),
        ("Basketball", "1997", "Topps Chrome", "Tracy McGrady", "125", "Refractor RC", 300, 5000, "High"),
        ("Basketball", "2002", "Topps Chrome", "Yao Ming", "146", "Refractor RC", 200, 3000, "Mid"),
        ("Basketball", "2023", "Panini National Treasures", "Victor Wembanyama", "101", "RPA /99", 25000, 150000, "Ultra Rare"),
        ("Basketball", "2003", "Upper Deck Exquisite", "LeBron James", "78", "RPA /99", 20000, 200000, "Ultra Rare"),
        ("Basketball", "2012", "Panini National Treasures", "Kawhi Leonard", "151", "RPA /99", 3000, 25000, "Ultra Rare"),
        ("Basketball", "1986", "Fleer", "Charles Barkley", "7", "Base RC", 50, 1500, "Mid"),
        ("Basketball", "1986", "Fleer", "Patrick Ewing", "32", "Base RC", 30, 800, "Mid"),

        # ── Baseball (23 items) ──────────────────────────────────────────
        ("Baseball", "1952", "Topps", "Mickey Mantle", "311", "Base", 50000, 500000, "Legendary"),
        ("Baseball", "1909", "T206", "Honus Wagner", "N/A", "Base", 500000, 999000, "Legendary"),
        ("Baseball", "1989", "Upper Deck", "Ken Griffey Jr.", "1", "Base", 15, 500, "Standard"),
        ("Baseball", "2011", "Topps Update", "Mike Trout", "US175", "Base", 200, 5000, "High"),
        ("Baseball", "1993", "SP", "Derek Jeter", "279", "Foil", 300, 10000, "High"),
        ("Baseball", "2018", "Topps Update", "Shohei Ohtani", "US1", "Base", 50, 2000, "Mid"),
        ("Baseball", "1951", "Bowman", "Willie Mays", "305", "Base", 5000, 50000, "Iconic"),
        ("Baseball", "1954", "Topps", "Hank Aaron", "128", "Base", 3000, 30000, "Iconic"),
        ("Baseball", "1933", "Goudey", "Babe Ruth", "53", "Base", 30000, 300000, "Legendary"),
        ("Baseball", "1955", "Topps", "Roberto Clemente", "164", "Base RC", 5000, 50000, "Iconic"),
        ("Baseball", "1948", "Leaf", "Jackie Robinson", "79", "Base RC", 15000, 150000, "Legendary"),
        ("Baseball", "1955", "Topps", "Sandy Koufax", "123", "Base RC", 3000, 30000, "Iconic"),
        ("Baseball", "1968", "Topps", "Nolan Ryan", "177", "Base RC", 2000, 25000, "Iconic"),
        ("Baseball", "1982", "Topps Traded", "Cal Ripken Jr.", "98T", "Base RC", 100, 3000, "High"),
        ("Baseball", "2001", "Topps Chrome", "Ichiro Suzuki", "T266", "Refractor RC", 500, 8000, "High"),
        ("Baseball", "2019", "Topps Chrome", "Juan Soto", "155", "Refractor", 150, 2500, "High"),
        ("Baseball", "2019", "Topps Chrome", "Fernando Tatis Jr.", "203", "Refractor RC", 200, 3500, "High"),
        ("Baseball", "2022", "Topps Chrome", "Adley Rutschman", "USC50", "Refractor RC", 80, 1500, "Mid"),
        ("Baseball", "2019", "Topps Chrome", "Ronald Acuna Jr.", "117", "Refractor", 150, 2500, "High"),
        ("Baseball", "2022", "Topps Chrome", "Julio Rodriguez", "USC100", "Refractor RC", 100, 2000, "High"),
        ("Baseball", "1956", "Topps", "Ted Williams", "5", "Base", 2000, 20000, "Iconic"),
        ("Baseball", "1963", "Topps", "Pete Rose", "537", "Base RC", 1500, 15000, "Iconic"),
        ("Baseball", "2001", "Topps Chrome", "Albert Pujols", "596", "Refractor RC", 400, 6000, "High"),

        # ── Football / NFL (21 items) ────────────────────────────────────
        ("Football", "2000", "Playoff Contenders", "Tom Brady", "144", "Auto", 30000, 400000, "Legendary"),
        ("Football", "2017", "Panini Prizm", "Patrick Mahomes", "269", "Silver Prizm", 3000, 40000, "Iconic"),
        ("Football", "1958", "Topps", "Jim Brown", "62", "Base", 2000, 25000, "Iconic"),
        ("Football", "2020", "Panini Prizm", "Justin Herbert", "325", "Silver Prizm", 300, 5000, "High"),
        ("Football", "2020", "Panini Prizm", "Joe Burrow", "307", "Silver Prizm", 200, 3000, "High"),
        ("Football", "1998", "Playoff Contenders", "Peyton Manning", "87", "Auto RC", 5000, 60000, "Iconic"),
        ("Football", "2005", "Topps Chrome", "Aaron Rodgers", "190", "Refractor RC", 1500, 20000, "Iconic"),
        ("Football", "2012", "Panini Prizm", "Russell Wilson", "230", "Silver Prizm RC", 300, 5000, "High"),
        ("Football", "2018", "Panini Prizm", "Josh Allen", "205", "Silver Prizm RC", 800, 12000, "High"),
        ("Football", "2018", "Panini Prizm", "Lamar Jackson", "212", "Silver Prizm RC", 400, 6000, "High"),
        ("Football", "1981", "Topps", "Joe Montana", "216", "Base RC", 500, 8000, "Iconic"),
        ("Football", "1989", "Score", "Barry Sanders", "257", "Base RC", 20, 600, "Mid"),
        ("Football", "1986", "Topps", "Jerry Rice", "161", "Base RC", 200, 4000, "Iconic"),
        ("Football", "1981", "Topps", "Lawrence Taylor", "216", "Base RC", 150, 3000, "High"),
        ("Football", "1984", "Topps", "Dan Marino", "123", "Base RC", 200, 4000, "High"),
        ("Football", "1984", "Topps", "John Elway", "63", "Base RC", 150, 3000, "High"),
        ("Football", "2020", "Panini Prizm", "Jalen Hurts", "343", "Silver Prizm RC", 200, 3500, "High"),
        ("Football", "2023", "Panini Prizm", "CJ Stroud", "301", "Silver Prizm RC", 150, 2500, "High"),
        ("Football", "2024", "Panini Prizm", "Caleb Williams", "305", "Silver Prizm RC", 100, 2000, "Mid"),
        ("Football", "2023", "Panini Prizm", "Brock Purdy", "330", "Silver Prizm", 200, 3000, "High"),
        ("Football", "1965", "Topps", "Joe Namath", "122", "Base RC", 1500, 15000, "Iconic"),

        # ── Soccer (14 items) ────────────────────────────────────────────
        ("Soccer", "2018", "Panini Prizm World Cup", "Kylian Mbappe", "80", "Silver Prizm", 500, 8000, "High"),
        ("Soccer", "2004", "Panini Mega Cracks", "Lionel Messi", "71", "Base RC", 5000, 50000, "Iconic"),
        ("Soccer", "2020", "Topps Chrome UCL", "Erling Haaland", "74", "Refractor", 200, 3000, "High"),
        ("Soccer", "1958", "Alifabolaget", "Pele", "635", "Base", 10000, 100000, "Legendary"),
        ("Soccer", "2003", "Panini Mega Cracks", "Cristiano Ronaldo", "148", "Base RC", 3000, 30000, "Iconic"),
        ("Soccer", "2010", "Panini Adrenalyn XL", "Neymar Jr.", "N/A", "Base RC", 500, 6000, "High"),
        ("Soccer", "2020", "Topps Chrome UCL", "Jude Bellingham", "86", "Refractor RC", 300, 5000, "High"),
        ("Soccer", "2023", "Topps Chrome UCL", "Lamine Yamal", "198", "Refractor RC", 400, 6000, "High"),
        ("Soccer", "2022", "Topps Chrome Bundesliga", "Florian Wirtz", "25", "Refractor RC", 200, 3000, "High"),
        ("Soccer", "2018", "Topps Chrome UCL", "Vinicius Jr.", "74", "Refractor RC", 250, 4000, "High"),
        ("Soccer", "1986", "Panini World Cup", "Diego Maradona", "84", "Sticker", 2000, 15000, "Iconic"),
        ("Soccer", "1996", "Panini Calcio", "Zinedine Zidane", "193", "Sticker", 300, 3000, "High"),
        ("Soccer", "1996", "Panini Voetbal", "Ronaldo Nazario", "100", "Sticker RC", 400, 5000, "High"),
        ("Soccer", "1999", "Panini Mega Cracks", "Ronaldinho", "138", "Base RC", 600, 7000, "High"),

        # ── Hockey / NHL (11 items) ──────────────────────────────────────
        ("Hockey", "1979", "O-Pee-Chee", "Wayne Gretzky", "18", "Base RC", 3000, 50000, "Iconic"),
        ("Hockey", "2005", "Upper Deck", "Sidney Crosby", "201", "Young Guns RC", 300, 5000, "High"),
        ("Hockey", "2015", "Upper Deck", "Connor McDavid", "201", "Young Guns RC", 200, 4000, "High"),
        ("Hockey", "1985", "O-Pee-Chee", "Mario Lemieux", "9", "Base RC", 500, 8000, "Iconic"),
        ("Hockey", "1966", "Topps", "Bobby Orr", "35", "Base RC", 3000, 35000, "Iconic"),
        ("Hockey", "1986", "O-Pee-Chee", "Patrick Roy", "53", "Base RC", 200, 3000, "High"),
        ("Hockey", "2016", "Upper Deck", "Auston Matthews", "201", "Young Guns RC", 200, 3500, "High"),
        ("Hockey", "2019", "Upper Deck", "Jack Hughes", "201", "Young Guns RC", 50, 800, "Mid"),
        ("Hockey", "2023", "Upper Deck", "Connor Bedard", "201", "Young Guns RC", 300, 5000, "High"),
        ("Hockey", "2005", "Upper Deck", "Alexander Ovechkin", "443", "Young Guns RC", 200, 3500, "High"),
        ("Hockey", "1968", "Topps", "Gordie Howe", "29", "Base", 600, 8000, "Iconic"),

        # ── UFC / MMA (6 items) ──────────────────────────────────────────
        ("UFC", "2016", "Topps Chrome UFC", "Conor McGregor", "50", "Refractor", 500, 6000, "High"),
        ("UFC", "2019", "Topps Chrome UFC", "Khabib Nurmagomedov", "60", "Refractor", 200, 3000, "High"),
        ("UFC", "2019", "Topps Chrome UFC", "Jon Jones", "24", "Refractor", 150, 2000, "High"),
        ("UFC", "2019", "Topps Chrome UFC", "Amanda Nunes", "31", "Refractor", 80, 1000, "Mid"),
        ("UFC", "2020", "Topps Chrome UFC", "Israel Adesanya", "55", "Refractor", 150, 2500, "High"),
        ("UFC", "2021", "Panini Select UFC", "Francis Ngannou", "45", "Silver Prizm", 100, 1500, "Mid"),

        # ── F1 / Racing (5 items) ────────────────────────────────────────
        ("F1", "2020", "Topps Chrome F1", "Max Verstappen", "1", "Refractor", 400, 5000, "High"),
        ("F1", "2020", "Topps Chrome F1", "Lewis Hamilton", "44", "Refractor", 300, 4000, "High"),
        ("F1", "2022", "Topps Chrome F1", "Charles Leclerc", "16", "Refractor", 150, 2000, "High"),
        ("F1", "2022", "Topps Chrome F1", "Lando Norris", "4", "Refractor", 100, 1500, "Mid"),
        ("F1", "1989", "Salvat", "Ayrton Senna", "N/A", "Vintage Sticker", 800, 5000, "Iconic"),

        # ── Sealed Product / Boxes (8 items) ─────────────────────────────
        ("Basketball", "1986", "Fleer", "Sealed Wax Box (36 packs)", "N/A", "Factory Sealed", 150000, 200000, "Legendary"),
        ("Basketball", "2003", "Topps Chrome", "Sealed Hobby Box", "N/A", "Factory Sealed", 30000, 40000, "Ultra Rare"),
        ("Football", "2017", "Panini Prizm", "Sealed Hobby Box", "N/A", "Factory Sealed", 15000, 20000, "Ultra Rare"),
        ("Baseball", "2011", "Topps Update", "Sealed Hobby Box", "N/A", "Factory Sealed", 10000, 15000, "Ultra Rare"),
        ("Basketball", "2018", "Panini Prizm", "Sealed Hobby Box", "N/A", "Factory Sealed", 5000, 8000, "High"),
        ("Hockey", "2005", "Upper Deck", "Sealed Hobby Box", "N/A", "Factory Sealed", 8000, 12000, "Ultra Rare"),
        ("Football", "2000", "Playoff Contenders", "Sealed Hobby Box", "N/A", "Factory Sealed", 50000, 70000, "Legendary"),
        ("Baseball", "1952", "Topps", "Sealed Wax Pack (single)", "N/A", "Factory Sealed", 25000, 35000, "Legendary"),

        # ── Modern Parallels & Inserts (representative) ──────────────────
        ("Basketball", "2022", "Panini Select", "Various", "N/A", "Courtside", 20, 200, "Standard"),
        ("Football", "2023", "Panini Prizm", "Various", "N/A", "Neon Green", 10, 100, "Standard"),
        ("Baseball", "2023", "Topps Chrome", "Various", "N/A", "Refractor", 5, 50, "Standard"),
    ]

    catalog = []
    for sport, year, set_name, player, card_no, variant, raw_price, graded_price, rarity in cards:
        catalog.append({
            "sport": sport,
            "year": year,
            "set_name": set_name,
            "player": player,
            "card_number": card_no,
            "variant": variant,
            "price_raw": raw_price,
            "price_psa10": graded_price,
            "rarity": rarity,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    player = item["player"]
    year = item["year"]
    set_name = item["set_name"]
    variant = item["variant"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{year}-{set_name}-{player}-{variant}"),
        title=f"{year} {set_name} {player}" + (f" ({variant})" if variant != "Base" else ""),
        set_code=slugify(f"{year}-{set_name}"),
        brand=set_name.split()[0] if set_name else "",
        rarity=item["rarity"],
        notes=f"{item['sport']} | #{item['card_number']}",
        attributes_json={
            "player": player,
            "set": set_name,
            "year": year,
            "variant": variant,
            "sport": item["sport"],
        },
    )


def item_to_price_observations(item: dict) -> list[PriceObservation]:
    rarity_score = shared_rarity_score(item["rarity"])

    observations = []
    # Raw (ungraded)
    if item["price_raw"] > 0:
        observations.append(PriceObservation(
            features={
                "condition_score": 0.7,
                "rarity_score": rarity_score,
                "edition_score": 0.5,
                "is_graded": 0.0,
            },
            price=float(item["price_raw"]),
        ))
    # PSA 10 (graded gem mint)
    if item["price_psa10"] > 0:
        observations.append(PriceObservation(
            features={
                "condition_score": 1.0,
                "rarity_score": rarity_score,
                "edition_score": 0.5,
                "is_graded": 1.0,
                "grade_score": 1.0,
            },
            price=float(item["price_psa10"]),
        ))
    return observations


def main():
    parser = argparse.ArgumentParser(description="Import sports cards catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Sports Cards Import ===")

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    catalog = get_curated_catalog()

    all_items = [item_to_catalog_item(i) for i in catalog]
    all_observations = []
    for i in catalog:
        all_observations.extend(item_to_price_observations(i))

    write_catalog_sql(CATEGORY, all_items)
    log_progress(CATEGORY, "catalog SQL written", len(all_items))

    write_training_jsonl(CATEGORY, all_observations)
    log_progress(CATEGORY, "training JSONL written", len(all_observations))

    if ingest.enabled:
        inserted = ingest.upsert_catalog(all_items)
        log_progress(CATEGORY, "catalog upserted", inserted)

    ingest.close()

    logger.info(f"\n=== Sports Cards Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
