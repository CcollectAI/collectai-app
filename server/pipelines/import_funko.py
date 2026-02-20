"""
Import Funko Pop data.

Layer 1 (Catalog):  Curated high-value Funko Pops → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

No official Funko API exists. Data sourced from:
- Curated grail lists (conventions, vaulted, chase variants)
- HobbyDB / Pop Price Guide structure
- Can be augmented with web scraping later

Usage:
    python -m pipelines.import_funko [--dry-run]
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

CATEGORY = "funko"


def get_curated_catalog() -> list[dict]:
    """Curated Funko Pop catalog covering 150+ items across major lines and grails."""

    # Format: (line, number, name, exclusive, rarity_tier, est_price_eur)
    # rarity_tier: grail (>500), high (100-500), mid (30-100), standard (<30)

    pops = [
        # ── DC Comics (6) ─────────────────────────────────────────────
        ("DC Heroes", "01", "Batman (Metallic Blue)", "SDCC 2010", "grail", 12000),
        ("DC Heroes", "01", "Batman", "", "standard", 15),
        ("DC Heroes", "02", "Superman", "", "standard", 12),
        ("DC Heroes", "06", "Green Lantern (Previews)", "NYCC 2012", "grail", 3500),
        ("DC Heroes", "52", "Batgirl", "", "standard", 10),
        ("DC Heroes", "13", "Harley Quinn", "", "mid", 45),

        # ── Marvel (18) ───────────────────────────────────────────────
        ("Marvel", "01", "Spider-Man", "", "mid", 60),
        ("Marvel", "02", "Iron Man", "", "standard", 20),
        ("Marvel", "03", "Hulk", "", "standard", 18),
        ("Marvel", "04", "Thor", "", "mid", 35),
        ("Marvel", "07", "Captain America", "", "mid", 40),
        ("Marvel", "18", "Red Skull (Metallic)", "SDCC 2011", "grail", 2000),
        ("Marvel", "39", "Loki", "", "mid", 50),
        ("Marvel", "65", "Deadpool", "", "standard", 15),
        ("Marvel", "88", "Venom", "", "mid", 45),
        ("Marvel", "18", "Ghost Rider (Metallic)", "SDCC 2013", "grail", 800),
        ("Marvel", "05", "Wolverine", "", "mid", 55),
        ("Marvel", "130", "Black Panther (Glow)", "Target", "high", 120),
        ("Marvel", "169", "Doctor Strange", "", "standard", 18),
        ("Marvel", "308", "Thanos (Metallic)", "Walmart", "high", 110),
        ("Marvel", "402", "Iron Man (Avengers Assemble)", "Amazon", "mid", 65),
        ("Marvel", "499", "Captain America (Glow)", "Entertainment Earth", "high", 140),
        ("Marvel", "580", "Spider-Man (Miles Morales)", "", "standard", 15),
        ("Marvel", "648", "Scarlet Witch (Glow)", "Target", "mid", 75),

        # ── Star Wars (15) ────────────────────────────────────────────
        ("Star Wars", "01", "Darth Vader", "", "mid", 45),
        ("Star Wars", "02", "Yoda", "", "mid", 35),
        ("Star Wars", "03", "Holographic Darth Maul", "Paris Comic Con", "grail", 5000),
        ("Star Wars", "06", "Boba Fett (Droids)", "", "high", 350),
        ("Star Wars", "33", "Boba Fett (Prototype)", "", "high", 300),
        ("Star Wars", "40", "Luke Skywalker (Jedi)", "", "standard", 15),
        ("Star Wars", "130", "Obi-Wan Kenobi", "", "standard", 12),
        ("Star Wars", "326", "The Mandalorian", "", "standard", 18),
        ("Star Wars", "368", "Grogu (The Child)", "", "standard", 14),
        ("Star Wars", "414", "Ahsoka Tano", "", "mid", 40),
        ("Star Wars", "34", "Darth Revan", "GameStop", "high", 250),
        ("Star Wars", "104", "501st Clone Trooper", "GameStop", "high", 180),
        ("Star Wars", "SE", "Shadow Trooper", "Star Wars Celebration", "high", 300),
        ("Star Wars", "13", "C-3PO (Gold Chrome)", "Funko-Shop", "high", 250),
        ("Star Wars", "512", "Grogu (Macy's Parade)", "Amazon", "mid", 55),

        # ── Disney (13) ───────────────────────────────────────────────
        ("Disney", "01", "Mickey Mouse", "", "high", 200),
        ("Disney", "07", "Dumbo (Clown)", "", "high", 400),
        ("Disney", "08", "Cheshire Cat", "", "mid", 80),
        ("Disney", "16", "Lotso (Flocked)", "SDCC 2012", "high", 200),
        ("Haunted Mansion", "12", "Hatbox Ghost", "Disney Parks", "grail", 4000),
        ("Disney Villains", "09", "Maleficent (Flames)", "Hot Topic", "high", 180),
        ("Disney Villains", "231", "Ursula (Diamond)", "Hot Topic", "mid", 55),
        ("Disney Villains", "277", "Cruella de Vil (Glitter)", "", "mid", 40),
        ("Pixar", "02", "Buzz Lightyear (Metallic)", "SDCC 2011", "high", 350),
        ("Pixar", "168", "Woody", "", "standard", 12),
        ("Pixar", "400", "Wall-E (Earth Day)", "BoxLunch", "mid", 65),
        ("Disney", "125", "Stitch (Flocked)", "Hot Topic", "high", 150),
        ("Disney", "352", "Genie (Glow)", "Specialty Series", "mid", 55),

        # ── Anime / DragonBall Z / Expanded Anime (20) ────────────────
        ("Dragon Ball Z", "10", "Planet Arlia Vegeta", "Toy Tokyo", "grail", 8000),
        ("Dragon Ball Z", "14", "Super Saiyan Goku", "", "mid", 40),
        ("Dragon Ball Z", "47", "Goku (Kamehameha)", "", "standard", 15),
        ("Dragon Ball Z", "120", "Vegeta (Galick Gun)", "Chalice", "mid", 60),
        ("Naruto", "71", "Naruto (Six Path)", "Hot Topic", "mid", 65),
        ("Naruto", "73", "Kakashi (Lightning Blade)", "", "mid", 35),
        ("One Piece", "98", "Monkey D. Luffy", "", "mid", 40),
        ("One Piece", "99", "Trafalgar Law", "", "mid", 50),
        ("My Hero Academia", "564", "Deku (Full Cowling)", "Glow", "mid", 70),
        ("My Hero Academia", "248", "All Might (Metallic)", "GameStop", "high", 130),
        ("My Hero Academia", "372", "Todoroki", "", "standard", 18),
        ("Attack on Titan", "239", "Levi Ackerman (Cleaning)", "Hot Topic", "high", 180),
        ("Attack on Titan", "84", "Eren Titan Form", "", "mid", 55),
        ("Demon Slayer", "867", "Tanjiro Kamado", "", "standard", 15),
        ("Demon Slayer", "869", "Nezuko", "", "standard", 18),
        ("Demon Slayer", "1040", "Rengoku (Ninth Form)", "BoxLunch", "mid", 65),
        ("Sailor Moon", "89", "Sailor Moon", "", "mid", 70),
        ("Cowboy Bebop", "145", "Spike Spiegel", "", "high", 150),
        ("Bleach", "59", "Ichigo (Hollow)", "Vaulted", "high", 200),
        ("Jujutsu Kaisen", "1116", "Gojo (Infinite Void)", "Hot Topic", "mid", 45),

        # ── Game of Thrones (7) ───────────────────────────────────────
        ("Game of Thrones", "01", "Ned Stark", "", "mid", 60),
        ("Game of Thrones", "02", "Headless Ned Stark", "SDCC 2013", "grail", 2500),
        ("Game of Thrones", "03", "Daenerys Targaryen", "", "mid", 35),
        ("Game of Thrones", "08", "Khal Drogo", "", "mid", 45),
        ("Game of Thrones", "22", "Night King", "", "standard", 20),
        ("Game of Thrones", "44", "Ramsay Bolton", "", "standard", 25),
        ("Game of Thrones", "61", "Cersei Lannister", "", "standard", 15),

        # ── Horror / Classics (6) ─────────────────────────────────────
        ("Movies", "01", "Clockwork Orange Alex", "Vaulted", "grail", 3000),
        ("Horror", "03", "Michael Myers (Glow)", "Fugitive", "high", 400),
        ("Horror", "19", "Ghostface", "", "mid", 50),
        ("Ad Icons", "02", "Boo Berry (Metallic)", "SDCC 2012", "grail", 1500),
        ("Ad Icons", "01", "Franken Berry (Metallic)", "SDCC 2012", "grail", 1200),
        ("Ad Icons", "03", "Count Chocula (Metallic)", "SDCC 2012", "grail", 1200),

        # ── Pokemon (5) ───────────────────────────────────────────────
        ("Pokemon", "353", "Pikachu", "", "standard", 12),
        ("Pokemon", "843", "Charizard", "", "standard", 15),
        ("Pokemon", "455", "Mewtwo", "", "standard", 15),
        ("Pokemon", "504", "Eevee", "", "standard", 10),
        ("Pokemon", "780", "Bulbasaur (Diamond)", "Hot Topic", "mid", 30),

        # ── Harry Potter (11) ─────────────────────────────────────────
        ("Harry Potter", "01", "Harry Potter", "", "mid", 55),
        ("Harry Potter", "03", "Hermione Granger", "", "mid", 50),
        ("Harry Potter", "04", "Dumbledore (Robes)", "", "mid", 40),
        ("Harry Potter", "06", "Voldemort", "", "mid", 35),
        ("Harry Potter", "71", "Snape (Always - Patronus)", "Hot Topic", "high", 120),
        ("Harry Potter", "76", "Hedwig (Flocked)", "Hot Topic", "high", 110),
        ("Harry Potter", "104", "Harry (Patronus)", "Hot Topic", "mid", 45),
        ("Harry Potter", "127", "Hermione (Patronus)", "", "mid", 35),
        ("Harry Potter", "15", "Sirius Black", "", "mid", 65),
        ("Harry Potter", "09", "Dobby (10-Inch)", "Target", "mid", 45),
        ("Harry Potter", "33", "Dumbledore (Elder Wand)", "NYCC 2017", "high", 200),

        # ── Stranger Things (8) ───────────────────────────────────────
        ("Stranger Things", "421", "Eleven (Underwater)", "Hot Topic", "mid", 35),
        ("Stranger Things", "427", "Eleven (Flocked)", "Benny's Burgers", "high", 180),
        ("Stranger Things", "637", "Eleven (Upside Down)", "ECCC 2017", "high", 250),
        ("Stranger Things", "428", "Demogorgon", "", "mid", 40),
        ("Stranger Things", "1312", "Vecna", "", "standard", 20),
        ("Stranger Things", "475", "Steve Harrington", "", "mid", 60),
        ("Stranger Things", "424", "Dustin Henderson", "", "mid", 35),
        ("Stranger Things", "1250", "Eddie Munson", "Hot Topic", "mid", 55),

        # ── The Office (7) ────────────────────────────────────────────
        ("The Office", "869", "Michael Scott", "", "standard", 12),
        ("The Office", "870", "Dwight Schrute", "", "standard", 12),
        ("The Office", "875", "Prison Mike", "Hot Topic", "high", 140),
        ("The Office", "1060", "Michael Klump", "Target", "mid", 55),
        ("The Office", "938", "Dwight as Recyclops", "SDCC 2020", "high", 200),
        ("The Office", "877", "Andy Bernard (Sumo)", "", "mid", 35),
        ("The Office", "1010", "Date Night Dwight", "Target", "mid", 50),

        # ── Music (8) ─────────────────────────────────────────────────
        ("Rocks", "57", "Metallica - Lars Ulrich", "", "high", 120),
        ("Rocks", "158", "Tupac Shakur (Loyal to the Game)", "", "mid", 55),
        ("Rocks", "87", "Notorious B.I.G. (Crown)", "", "mid", 65),
        ("Rocks", "02", "Elvis Presley (Metallic)", "Hot Topic", "high", 350),
        ("Rocks", "79", "Prince (Purple Rain)", "", "high", 200),
        ("Rocks", "96", "Freddie Mercury (Wembley)", "", "mid", 35),
        ("Rocks", "14", "Jimi Hendrix (Monterey)", "SDCC 2017", "high", 300),
        ("Rocks", "66", "Kurt Cobain (MTV Unplugged)", "", "mid", 80),

        # ── Video Games (8) ───────────────────────────────────────────
        ("Halo", "01", "Master Chief", "", "mid", 80),
        ("Games", "269", "Kratos (Blades of Chaos)", "", "mid", 40),
        ("The Witcher", "151", "Geralt (IGNI)", "GameStop", "mid", 55),
        ("Games", "53", "Vault Boy", "", "standard", 20),
        ("Pokemon", "353", "Pikachu (10-Inch)", "Target", "high", 120),
        ("Games", "103", "Mega Man", "", "mid", 60),
        ("Games", "81", "Pac-Man", "", "mid", 45),
        ("Games", "283", "Sonic the Hedgehog (Gold)", "SDCC 2017", "high", 250),

        # ── Sports (6) ────────────────────────────────────────────────
        ("NBA", "54", "Michael Jordan (Bulls)", "", "mid", 55),
        ("NBA", "11", "Kobe Bryant (Purple Jersey)", "", "high", 400),
        ("NBA", "52", "LeBron James (White Jersey)", "", "mid", 45),
        ("Boxing", "01", "Muhammad Ali", "", "high", 150),
        ("NFL", "137", "Tom Brady (Patriots)", "", "mid", 75),
        ("NBA", "78", "Stephen Curry", "", "standard", 25),

        # ── Soda & Mini Lines (5) ─────────────────────────────────────
        ("Vinyl Soda", "SE", "Batman (Soda Chase)", "Funko-Shop", "high", 110),
        ("Vinyl Soda", "SE", "Spider-Man (Soda)", "", "mid", 35),
        ("Pocket POP Keychain", "SE", "Grogu Keychain", "", "standard", 8),
        ("Bitty Pop", "SE", "Bitty Pop - The Office (4 Pack)", "", "standard", 12),
        ("Bitty Pop", "SE", "Bitty Pop - Harry Potter (4 Pack)", "", "standard", 12),

        # ── Convention Exclusives / Funko Fundays (12) ────────────────
        ("Freddy Funko", "SE", "Freddy Funko (Astronaut)", "Funko HQ", "high", 500),
        ("Freddy Funko", "SE", "Freddy Funko as Pennywise", "Fundays", "grail", 3000),
        ("Freddy Funko", "SE", "Freddy Funko as Skeletor", "Fundays 2016", "grail", 5500),
        ("Freddy Funko", "SE", "Freddy Funko as Boba Fett", "Fundays 2014", "grail", 4000),
        ("Marvel", "SE", "Tony Stark (Metallic)", "SDCC 2013", "grail", 1200),
        ("DC Heroes", "SE", "Batgirl (Metallic Pink)", "SDCC 2012", "grail", 1100),
        ("Disney", "SE", "Winnie the Pooh (Flocked)", "SDCC 2012", "grail", 2200),
        ("Star Wars", "SE", "Holographic Emperor", "SDCC 2012", "grail", 1800),
        ("Animation", "SE", "Glow-in-Dark White Ranger", "SDCC 2013", "grail", 1500),
        ("Games", "SE", "Master Chief (Gold)", "SDCC 2013", "grail", 900),
        ("Freddy Funko", "SE", "Freddy Funko (Neon)", "Fundays 2019", "high", 450),
        ("DC Heroes", "SE", "The Joker (Metallic)", "NYCC 2013", "grail", 1400),

        # ── Television / Other (2) ────────────────────────────────────
        ("Friends", "700", "Monica Geller", "", "standard", 10),
        ("Breaking Bad", "158", "Walter White (Heisenberg)", "", "mid", 60),
    ]

    catalog = []
    for line, number, name, exclusive, tier, price in pops:
        catalog.append({
            "line": line,
            "number": number,
            "name": name,
            "exclusive": exclusive,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    line = item["line"]
    number = item["number"]
    name = item["name"]
    exclusive = item["exclusive"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{line}-{number}-{name}"),
        title=f"{name} #{number}",
        set_code=line.lower().replace(" ", "-"),
        brand="Funko Pop",
        rarity=item["rarity_tier"].title(),
        notes=f"{line} #{number}" + (f" | {exclusive}" if exclusive else ""),
        attributes_json={
            "line": line,
            "number": number,
            "exclusive": exclusive,
            "sticker_variant": exclusive if exclusive else "",
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]
    exclusive_score = 0.9 if item["exclusive"] else 0.3

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": exclusive_score,
            "is_chase": 0.0,
            "is_exclusive": 1.0 if item["exclusive"] else 0.0,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Funko Pop catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Funko Pop Import ===")

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

    logger.info(f"\n=== Funko Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
