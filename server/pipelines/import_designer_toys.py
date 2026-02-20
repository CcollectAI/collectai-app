"""
Import Designer Toys / Art Toys catalog (120+ items).

Layer 1 (Catalog):  Curated designer toy figures → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- KAWS Companions, Gone, Clean Slate, Share, Seeing/Watching, Astro Boy, Sesame Street, Pinocchio, Chum
- Bearbrick 100%+400% sets (BAPE, Stussy, Neighborhood, Atmos, Nike SB, Cleverin, Kith),
  1000% (Andy Warhol, Jackson Pollock, Stussy), Bearbrick Series blind boxes
- Pop Mart (Molly, Dimoo, PUCKY, LABUBU, Hirono, Zsiga, The Monsters, Space Molly 400%)
- Superplastic (Janky, Guggimon)
- Coarse figures
- Ron English, Takashi Murakami complexcon figures
- Kidrobot Dunny series (Huck Gee, Kronk, JPK), Munny, Mega Man, South Park, Simpsons
- BAIT exclusives (Astro Boy, Street Fighter, Ultraman)
- Mighty Jaxx XXRay (Batman, Elmo, Spongebob), Mightyverse, Jason Freeny collabs
- Unruly Industries (Spider-Gwen, Batman, Joker, Wolverine, Venom)
- Secret Base (Skull Bee, Honey Bear, Ghost Bear)
- Hot Toys Cosbaby (Marvel, Star Wars, DC)
- Fools Paradise (Astro Boy homage, Pinocchio, Mad Dog)
- Vinyl Collectibles Dolls / VCD by Medicom (Snoopy, Mickey, Ultraman)
- Daniel Arsham (Eroded Pikachu, Future Relic, Crystal Relic)
- A Bathing Ape / BAPE figures (Baby Milo, Star Wars, Dragon Ball)
- FigureComplex / Revoltech Amazing Yamaguchi (Batman, Spider-Man, Deadpool, Wolverine)

Usage:
    python -m pipelines.import_designer_toys [--dry-run]
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

CATEGORY = "designer_toys"


def get_curated_catalog() -> list[dict]:
    """Curated designer toy catalog covering major artists and brands."""

    # (brand, line, name, edition, rarity_tier, price_eur)
    # rarity_tier: grail (>1500), high (500-1500), mid (100-500), standard (<100)

    toys = [
        # ── KAWS Companions ──────────────────────────────────────────────
        ("KAWS", "Companion", "Companion Open Edition Grey", "Open Edition", "mid", 280),
        ("KAWS", "Companion", "Companion Open Edition Black", "Open Edition", "mid", 300),
        ("KAWS", "Companion", "Companion Open Edition Brown", "Open Edition", "mid", 320),
        ("KAWS", "Companion", "Companion Open Edition Pink", "Open Edition", "mid", 350),
        ("KAWS", "Companion", "Companion Flayed Grey", "Open Edition", "mid", 300),
        ("KAWS", "Companion", "Companion Flayed Black", "Open Edition", "mid", 320),
        ("KAWS", "Companion", "Companion Flayed Brown", "Open Edition", "mid", 340),
        ("KAWS", "Companion", "Dissected Companion Grey 2006", "Limited", "grail", 2800),
        ("KAWS", "Companion", "Dissected Companion Brown 2006", "Limited", "grail", 2600),
        ("KAWS", "Companion", "Resting Place Companion", "Limited", "high", 1200),
        ("KAWS", "Small Lie", "Small Lie Grey", "Open Edition", "mid", 250),
        ("KAWS", "Small Lie", "Small Lie Black", "Open Edition", "mid", 270),
        ("KAWS", "BFF", "BFF Pink", "Open Edition", "mid", 350),
        ("KAWS", "BFF", "BFF Blue", "Open Edition", "mid", 380),
        ("KAWS", "Together", "Together Grey", "Open Edition", "mid", 450),
        ("KAWS", "Holiday", "Holiday Japan (Mount Fuji)", "Limited", "high", 900),
        ("KAWS", "Holiday", "Holiday Singapore", "Limited", "high", 800),
        ("KAWS", "What Party", "What Party White", "Open Edition", "mid", 150),
        # KAWS expanded
        ("KAWS", "Gone", "Gone Companion Grey", "Open Edition", "mid", 400),
        ("KAWS", "Gone", "Gone Companion Black", "Open Edition", "mid", 420),
        ("KAWS", "Clean Slate", "Clean Slate Grey", "Open Edition", "mid", 380),
        ("KAWS", "Clean Slate", "Clean Slate Brown", "Open Edition", "mid", 400),
        ("KAWS", "Share", "Share Companion Grey", "Open Edition", "mid", 420),
        ("KAWS", "Share", "Share Companion Black", "Open Edition", "mid", 440),
        ("KAWS", "Seeing/Watching", "Seeing/Watching Grey", "Limited", "high", 850),
        ("KAWS", "Astro Boy", "KAWS Astro Boy Companion", "Collab", "grail", 2200),
        ("KAWS", "Sesame Street", "KAWS x Sesame Street Ernie", "Collab", "mid", 350),
        ("KAWS", "Sesame Street", "KAWS x Sesame Street BFF Elmo", "Collab", "mid", 380),
        ("KAWS", "Pinocchio", "KAWS Pinocchio & Jiminy Cricket", "Limited", "high", 1100),
        ("KAWS", "Chum", "Chum White", "Limited", "high", 950),

        # ── Bearbrick 1000% ──────────────────────────────────────────────
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Basquiat V1", "Collab", "high", 1400),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Basquiat V2", "Collab", "high", 1200),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Banksy Flower Bomber", "Collab", "grail", 3500),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% fragment design", "Collab", "grail", 4200),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Keith Haring V1", "Collab", "high", 1100),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% BAPE Camo Green", "Collab", "grail", 3800),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Hajime Sorayama Sexy Robot", "Collab", "grail", 4800),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Karimoku Carved Wood", "Collab", "grail", 5000),
        ("Medicom", "Bearbrick 400%", "Bearbrick 400% Basquiat V1", "Collab", "mid", 350),
        ("Medicom", "Bearbrick 400%", "Bearbrick 400% Banksy Flower Bomber", "Collab", "high", 500),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% fragment design", "Collab", "high", 550),
        # Bearbrick expanded — 100%+400% sets
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% BAPE Camo Green", "Collab", "high", 600),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Stussy Black", "Collab", "high", 520),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Neighborhood Black", "Collab", "high", 500),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Atmos Elephant", "Collab", "mid", 450),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Nike SB Dunk", "Collab", "high", 580),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Cleverin Blue", "Collab", "mid", 200),
        ("Medicom", "Bearbrick 100%+400%", "Bearbrick 100%+400% Kith Treats", "Collab", "mid", 420),
        # Bearbrick expanded — 1000%
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Andy Warhol Flowers", "Collab", "grail", 3200),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Jackson Pollock Studio", "Collab", "grail", 2800),
        ("Medicom", "Bearbrick 1000%", "Bearbrick 1000% Stussy 30th Anniversary", "Collab", "grail", 3500),
        # Bearbrick Series blind boxes
        ("Medicom", "Bearbrick Series", "Bearbrick Series 44 Sealed Case", "Blind Box Set", "standard", 95),
        ("Medicom", "Bearbrick Series", "Bearbrick Series 43 Sealed Case", "Blind Box Set", "standard", 90),

        # ── Pop Mart ─────────────────────────────────────────────────────
        ("Pop Mart", "Molly", "Molly Anniversary Statues Series", "Blind Box Set", "standard", 75),
        ("Pop Mart", "Molly", "Molly x Instinctoy Erosion", "Collab", "mid", 180),
        ("Pop Mart", "Dimoo", "Dimoo World Heritage Series", "Blind Box Set", "standard", 65),
        ("Pop Mart", "Dimoo", "Dimoo Fairy Tale Series", "Blind Box Set", "standard", 55),
        ("Pop Mart", "Skullpanda", "Skullpanda Night City Series", "Blind Box Set", "standard", 60),
        ("Pop Mart", "The Monsters", "The Monsters Circus Series", "Blind Box Set", "standard", 55),
        ("Pop Mart", "Mega Collection", "Mega Collection 1000% Space Molly Jasmine", "Mega", "high", 900),
        ("Pop Mart", "Mega Collection", "Mega Collection 1000% Space Molly Christmas", "Mega", "high", 1100),
        # Pop Mart expanded
        ("Pop Mart", "PUCKY", "PUCKY Sleeping Forest Series", "Blind Box Set", "standard", 60),
        ("Pop Mart", "PUCKY", "PUCKY Pool Babies Series", "Blind Box Set", "standard", 55),
        ("Pop Mart", "LABUBU", "LABUBU The Monsters Tasty Life Series", "Blind Box Set", "standard", 65),
        ("Pop Mart", "LABUBU", "LABUBU Have a Seat Series", "Blind Box Set", "standard", 70),
        ("Pop Mart", "Hirono", "Hirono The Other One Series", "Blind Box Set", "standard", 75),
        ("Pop Mart", "Zsiga", "Zsiga Walking Into the Forest Series", "Blind Box Set", "standard", 65),
        ("Pop Mart", "The Monsters", "The Monsters Toys Series Full Case", "Blind Box Set", "standard", 80),
        ("Pop Mart", "Space Molly", "Space Molly 400% Pinkerton", "Limited", "high", 650),

        # ── Superplastic ─────────────────────────────────────────────────
        ("Superplastic", "Janky", "Janky Series 1 Full Case", "Blind Box Set", "standard", 90),
        ("Superplastic", "Janky", "Janky x Guggimon OG", "Standard", "standard", 25),
        ("Superplastic", "Guggimon", "Guggimon Supervillain 8-inch", "Standard", "mid", 120),
        ("Superplastic", "Guggimon", "Guggimon x Fortnite Edition", "Collab", "mid", 200),
        ("Superplastic", "Kranky", "Kranky Superplastic 8-inch Glow", "Limited", "mid", 180),
        ("Superplastic", "Janky", "Janky x BAIT Edition", "Collab", "mid", 350),

        # ── Coarse ───────────────────────────────────────────────────────
        ("Coarse", "Omen", "Omen Fade 10-inch", "Limited", "mid", 350),
        ("Coarse", "Omen", "Omen Rise 10-inch", "Limited", "mid", 380),
        ("Coarse", "Noop", "Noop Blackout Edition", "Limited", "high", 600),
        ("Coarse", "Pain", "Pain Ignite 14-inch", "Limited", "high", 750),

        # ── Ron English ──────────────────────────────────────────────────
        ("Ron English", "MC Supersized", "MC Supersized Original Colorway", "Limited", "mid", 400),
        ("Ron English", "MC Supersized", "MC Supersized Glow-in-Dark", "Limited", "high", 600),
        ("Ron English", "Temper Tot", "Temper Tot OG Red", "Limited", "mid", 250),
        ("Ron English", "Telegrinnies", "Telegrinnies Full Set", "Limited", "mid", 350),

        # ── Takashi Murakami ─────────────────────────────────────────────
        ("Takashi Murakami", "ComplexCon", "Flower Parent and Child (Blue/White)", "ComplexCon Exclusive", "grail", 1800),
        ("Takashi Murakami", "ComplexCon", "Murakami x KAWS Flower", "ComplexCon Exclusive", "grail", 2200),
        ("Takashi Murakami", "Kaikai Kiki", "Mr. DOB Figure Gold", "Limited", "high", 900),
        ("Takashi Murakami", "Kaikai Kiki", "Flower Ball 3D Magnet Set", "Standard", "mid", 200),

        # ── Kidrobot ─────────────────────────────────────────────────────
        ("Kidrobot", "Dunny", "Dunny 8-inch Huck Gee Gold Life", "Limited", "high", 550),
        ("Kidrobot", "Dunny", "Dunny 8-inch Kronk Wild Ones", "Limited", "mid", 300),
        ("Kidrobot", "Dunny", "Dunny 8-inch Jon-Paul Kaiser Noir", "Limited", "mid", 350),
        ("Kidrobot", "Dunny", "Dunny 3-inch Series 2012 Full Case", "Blind Box Set", "standard", 85),
        ("Kidrobot", "Dunny", "Dunny 3-inch Azteca II Full Case", "Blind Box Set", "standard", 90),
        ("Kidrobot", "Munny", "Munny DIY 7-inch Blank White", "Standard", "standard", 30),
        ("Kidrobot", "Dunny", "Mega Man 8-inch Dunny Blue", "Collab", "mid", 250),
        ("Kidrobot", "South Park", "South Park Cartman 6-inch Vinyl", "Collab", "mid", 120),
        ("Kidrobot", "South Park", "South Park Kenny 6-inch Vinyl", "Collab", "mid", 110),
        ("Kidrobot", "Simpsons", "Simpsons Homer Buddha 7-inch", "Collab", "mid", 180),

        # ── BAIT Exclusives ──────────────────────────────────────────────
        ("BAIT", "Astro Boy", "BAIT x Astro Boy Mechanics 10-inch", "Collab", "high", 500),
        ("BAIT", "Astro Boy", "BAIT x Astro Boy Atom Glow-in-Dark", "Collab", "high", 550),
        ("BAIT", "Street Fighter", "BAIT x Street Fighter Ryu 10-inch", "Collab", "mid", 350),
        ("BAIT", "Street Fighter", "BAIT x Street Fighter Akuma 10-inch", "Collab", "mid", 380),
        ("BAIT", "Ultraman", "BAIT x Ultraman Diecast 8-inch", "Collab", "high", 600),

        # ── Mighty Jaxx ──────────────────────────────────────────────────
        ("Mighty Jaxx", "XXRay", "XXRay Batman 10-inch by Jason Freeny", "Collab", "mid", 250),
        ("Mighty Jaxx", "XXRay", "XXRay Elmo 10-inch by Jason Freeny", "Collab", "mid", 200),
        ("Mighty Jaxx", "XXRay", "XXRay Spongebob 10-inch by Jason Freeny", "Collab", "mid", 220),
        ("Mighty Jaxx", "XXRay", "XXRay Pikachu 4-inch by Jason Freeny", "Collab", "mid", 180),
        ("Mighty Jaxx", "XXRay Plus", "XXRay Plus Dissected Kaws Companion", "Collab", "mid", 280),
        ("Mighty Jaxx", "Mightyverse", "Mightyverse COTE Blind Box Set", "Blind Box Set", "standard", 55),
        ("Mighty Jaxx", "Mightyverse", "Mightyverse Freeny Hidden Dissectibles One Piece", "Blind Box Set", "standard", 65),
        ("Mighty Jaxx", "Jason Freeny", "Balloon Dog Anatomy Red by Jason Freeny", "Limited", "mid", 320),

        # ── Unruly Industries ────────────────────────────────────────────
        ("Unruly Industries", "Marvel", "Spider-Gwen Designer Statue", "Limited", "high", 550),
        ("Unruly Industries", "DC", "Batman Designer Statue by Joe DellaGatta", "Limited", "high", 600),
        ("Unruly Industries", "DC", "Joker Designer Statue", "Limited", "high", 580),
        ("Unruly Industries", "Marvel", "Wolverine Designer Statue", "Limited", "high", 520),
        ("Unruly Industries", "Marvel", "Venom Designer Statue", "Limited", "high", 650),

        # ── Secret Base ──────────────────────────────────────────────────
        ("Secret Base", "Skull Bee", "Skull Bee OG Black Edition", "Limited", "high", 700),
        ("Secret Base", "Skull Bee", "Skull Bee Gold Chrome Edition", "Limited", "grail", 1600),
        ("Secret Base", "Honey Bear", "Honey Bear Clear Blue Edition", "Limited", "high", 550),
        ("Secret Base", "Ghost Bear", "Ghost Bear Collab x BAIT", "Collab", "high", 800),
        ("Secret Base", "Ghost Bear", "Ghost Bear OG Glow-in-Dark", "Limited", "high", 650),

        # ── Hot Toys Cosbaby ─────────────────────────────────────────────
        ("Hot Toys", "Cosbaby Marvel", "Cosbaby Iron Man Mark L", "Standard", "standard", 45),
        ("Hot Toys", "Cosbaby Marvel", "Cosbaby Spider-Man Integrated Suit", "Standard", "standard", 40),
        ("Hot Toys", "Cosbaby Star Wars", "Cosbaby The Mandalorian & Grogu", "Standard", "standard", 50),
        ("Hot Toys", "Cosbaby Star Wars", "Cosbaby Darth Vader Lightsaber", "Standard", "standard", 40),
        ("Hot Toys", "Cosbaby DC", "Cosbaby Batman The Dark Knight", "Standard", "standard", 45),
        ("Hot Toys", "Cosbaby DC", "Cosbaby Joker The Dark Knight", "Standard", "standard", 45),

        # ── Fools Paradise ───────────────────────────────────────────────
        ("Fools Paradise", "Astro Boy", "Astro Boy Homage OG Edition", "Limited", "high", 750),
        ("Fools Paradise", "Astro Boy", "Astro Boy Homage Stealth Black", "Limited", "high", 800),
        ("Fools Paradise", "Pinocchio", "Pinocchio Cool Kid Edition", "Limited", "high", 700),
        ("Fools Paradise", "Mad Dog", "Michael Mad Dog Scarface Edition", "Limited", "high", 650),
        ("Fools Paradise", "Mad Dog", "Michael Mad Dog OG White Suit", "Limited", "high", 680),

        # ── Vinyl Collectibles Dolls (VCD) by Medicom ────────────────────
        ("Medicom", "VCD", "VCD Snoopy & Woodstock 1997", "Limited", "high", 800),
        ("Medicom", "VCD", "VCD Snoopy Joe Cool", "Standard", "mid", 250),
        ("Medicom", "VCD", "VCD Mickey Mouse Standard", "Standard", "mid", 200),
        ("Medicom", "VCD", "VCD Mickey Mouse Vintage B&W", "Limited", "mid", 350),
        ("Medicom", "VCD", "VCD Ultraman Type A", "Limited", "high", 600),

        # ── Daniel Arsham ────────────────────────────────────────────────
        ("Daniel Arsham", "Eroded", "Eroded Pikachu 2020 (Blue)", "Limited", "grail", 2500),
        ("Daniel Arsham", "Eroded", "Eroded Pikachu 2020 (Pink)", "Limited", "grail", 2800),
        ("Daniel Arsham", "Future Relic", "Future Relic 09 Eroded Turntable", "Limited", "grail", 3500),
        ("Daniel Arsham", "Future Relic", "Future Relic 06 Eroded Camera", "Limited", "grail", 2000),
        ("Daniel Arsham", "Crystal Relic", "Crystal Relic 002 Porsche 911", "Limited", "grail", 4500),

        # ── A Bathing Ape / BAPE Figures ─────────────────────────────────
        ("BAPE", "Baby Milo", "Baby Milo 10-inch Vinyl OG Green", "Standard", "mid", 180),
        ("BAPE", "Baby Milo", "Baby Milo 10-inch Vinyl Camo", "Limited", "mid", 350),
        ("BAPE", "Star Wars", "BAPE x Star Wars Stormtrooper 12-inch", "Collab", "high", 700),
        ("BAPE", "Star Wars", "BAPE x Star Wars Darth Vader 12-inch", "Collab", "high", 750),
        ("BAPE", "Dragon Ball", "BAPE x Dragon Ball Z Son Goku Figure", "Collab", "high", 500),

        # ── FigureComplex / Revoltech Amazing Yamaguchi ──────────────────
        ("Kaiyodo", "Amazing Yamaguchi", "Amazing Yamaguchi Batman No.009", "Standard", "mid", 120),
        ("Kaiyodo", "Amazing Yamaguchi", "Amazing Yamaguchi Spider-Man No.002", "Standard", "mid", 130),
        ("Kaiyodo", "Amazing Yamaguchi", "Amazing Yamaguchi Deadpool No.001", "Standard", "mid", 110),
        ("Kaiyodo", "Amazing Yamaguchi", "Amazing Yamaguchi Wolverine No.005", "Standard", "mid", 140),
        ("Kaiyodo", "Amazing Yamaguchi", "Amazing Yamaguchi Iron Man Bleeding Edge", "Standard", "mid", 150),
    ]

    catalog = []
    for brand, line, name, edition, tier, price in toys:
        catalog.append({
            "brand": brand,
            "line": line,
            "name": name,
            "edition": edition,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    brand = item["brand"]
    line = item["line"]
    name = item["name"]
    edition = item["edition"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{brand}-{name}"),
        title=name,
        set_code=slugify(line),
        brand=brand,
        rarity=item["rarity_tier"].title(),
        notes=f"{brand} | {line}" + (f" | {edition}" if edition else ""),
        attributes_json={
            "brand": brand,
            "line": line,
            "edition": edition,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    edition = item["edition"]
    edition_scores = {
        "Limited": 0.85,
        "Collab": 0.75,
        "ComplexCon Exclusive": 0.95,
        "Mega": 0.80,
        "Open Edition": 0.3,
        "Standard": 0.2,
        "Blind Box Set": 0.2,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_scores.get(edition, 0.5),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Designer Toys catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Designer Toys Import ===")

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

    logger.info(f"\n=== Designer Toys Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
