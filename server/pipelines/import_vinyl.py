"""
Curated Vinyl Records Import Pipeline.

Imports a hand-curated catalog of 120+ collectible vinyl records across
10 subcategories: Classic Rock, Hip-Hop/R&B, Jazz, Indie/Alternative,
Electronic/Ambient, Soul/Funk/R&B, Punk/Post-Punk, Modern Collectible
Pressings, Soundtracks & Scores, and Country/Folk/Blues.

Each record has a pressing type, genre, condition grade mapping (Goldmine
standard), and realistic EUR secondary market prices.

Pattern follows import_books_isbn.py (curated catalog -> catalog items +
price observations -> JSONL + SQL output).

Usage:
    python -m pipelines.import_vinyl [--dry-run] [--jsonl-only] [--cache-images]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines.import_common import (
    CatalogItem,
    PriceObservation,
    SupabaseIngest,
    write_training_jsonl,
    write_catalog_sql,
    cache_catalog_images,
    log_progress,
    slugify,
    logger,
    close_http_client,
    MAX_PRICE_EUR,
)

# ---------------------------------------------------------------------------
# Category constant
# ---------------------------------------------------------------------------
CATEGORY = "vinyl_records"

# ---------------------------------------------------------------------------
# Pressing-type rarity scores (0-1)
# ---------------------------------------------------------------------------
PRESSING_TYPE_SCORES: dict[str, float] = {
    "Original 1st Pressing": 0.95,
    "Numbered Limited": 0.90,
    "Colored/Splatter Vinyl": 0.80,
    "Audiophile (MFSL/Half-Speed)": 0.85,
    "Standard Repress": 0.30,
    "Picture Disc": 0.70,
    "Box Set": 0.75,
    "Promo/Test Pressing": 0.92,
    "RSD Exclusive": 0.80,
    "Standard": 0.25,
}

# ---------------------------------------------------------------------------
# Goldmine condition grade scores (0-1)
# ---------------------------------------------------------------------------
CONDITION_GRADE_SCORES: dict[str, float] = {
    "M": 1.0,      # Mint
    "NM": 0.90,    # Near Mint
    "VG+": 0.75,   # Very Good Plus
    "VG": 0.60,    # Very Good
    "G+": 0.40,    # Good Plus
    "G": 0.30,     # Good
    "F": 0.15,     # Fair
    "P": 0.05,     # Poor
}

# ---------------------------------------------------------------------------
# Genre popularity scores (used as a feature for pricing ML)
# ---------------------------------------------------------------------------
GENRE_POPULARITY: dict[str, float] = {
    "Classic Rock": 0.90,
    "Hip-Hop": 0.85,
    "Jazz": 0.75,
    "Indie/Alternative": 0.80,
    "Electronic": 0.65,
    "Soul/Funk": 0.70,
    "Punk/Post-Punk": 0.60,
    "Modern Collectible": 0.75,
    "Soundtrack": 0.55,
    "Country/Folk/Blues": 0.60,
}


# ---------------------------------------------------------------------------
# Per-subcategory curated catalogs
# Each returns list of tuples:
#   (artist, album, pressing_type, genre, price_eur)
# ---------------------------------------------------------------------------


def _classic_rock_icons() -> list[tuple[str, str, str, str, float]]:
    """15 Classic Rock Icons — original pressings and collectible editions."""
    return [
        ("Pink Floyd", "The Dark Side of the Moon",
         "Original 1st Pressing", "Classic Rock", 1200.00),
        ("Led Zeppelin", "Led Zeppelin I",
         "Original 1st Pressing", "Classic Rock", 850.00),
        ("Led Zeppelin", "Led Zeppelin II",
         "Original 1st Pressing", "Classic Rock", 600.00),
        ("Led Zeppelin", "Led Zeppelin IV",
         "Original 1st Pressing", "Classic Rock", 950.00),
        ("The Beatles", "Abbey Road",
         "Original 1st Pressing", "Classic Rock", 1400.00),
        ("The Beatles", "The White Album",
         "Original 1st Pressing", "Classic Rock", 1800.00),
        ("The Beatles", "Sgt. Pepper's Lonely Hearts Club Band",
         "Original 1st Pressing", "Classic Rock", 1600.00),
        ("The Rolling Stones", "Exile on Main St.",
         "Original 1st Pressing", "Classic Rock", 450.00),
        ("The Who", "Who's Next",
         "Original 1st Pressing", "Classic Rock", 380.00),
        ("Jimi Hendrix", "Electric Ladyland",
         "Original 1st Pressing", "Classic Rock", 700.00),
        ("David Bowie", "The Rise and Fall of Ziggy Stardust",
         "Original 1st Pressing", "Classic Rock", 650.00),
        ("Fleetwood Mac", "Rumours",
         "Original 1st Pressing", "Classic Rock", 350.00),
        ("Queen", "A Night at the Opera",
         "Original 1st Pressing", "Classic Rock", 320.00),
        ("Pink Floyd", "Wish You Were Here",
         "Original 1st Pressing", "Classic Rock", 500.00),
        ("Led Zeppelin", "Physical Graffiti",
         "Original 1st Pressing", "Classic Rock", 550.00),
    ]


def _hiphop_rnb_grails() -> list[tuple[str, str, str, str, float]]:
    """15 Hip-Hop & R&B Grails — original pressings and sought-after editions."""
    return [
        ("Wu-Tang Clan", "Enter the Wu-Tang (36 Chambers)",
         "Original 1st Pressing", "Hip-Hop", 450.00),
        ("Nas", "Illmatic",
         "Original 1st Pressing", "Hip-Hop", 600.00),
        ("Madvillain", "Madvillainy",
         "Original 1st Pressing", "Hip-Hop", 350.00),
        ("Kanye West", "My Beautiful Dark Twisted Fantasy",
         "Original 1st Pressing", "Hip-Hop", 280.00),
        ("Kendrick Lamar", "To Pimp a Butterfly",
         "Original 1st Pressing", "Hip-Hop", 200.00),
        ("OutKast", "Aquemini",
         "Original 1st Pressing", "Hip-Hop", 500.00),
        ("Lauryn Hill", "The Miseducation of Lauryn Hill",
         "Original 1st Pressing", "Hip-Hop", 320.00),
        ("A Tribe Called Quest", "Midnight Marauders",
         "Original 1st Pressing", "Hip-Hop", 250.00),
        ("The Notorious B.I.G.", "Ready to Die",
         "Original 1st Pressing", "Hip-Hop", 700.00),
        ("Jay-Z", "Reasonable Doubt",
         "Original 1st Pressing", "Hip-Hop", 1200.00),
        ("Frank Ocean", "Blonde",
         "Original 1st Pressing", "Hip-Hop", 550.00),
        ("Tyler, the Creator", "Igor",
         "Colored/Splatter Vinyl", "Hip-Hop", 65.00),
        ("MF DOOM", "MM..FOOD",
         "Colored/Splatter Vinyl", "Hip-Hop", 75.00),
        ("J Dilla", "Donuts",
         "Original 1st Pressing", "Hip-Hop", 380.00),
        ("De La Soul", "3 Feet High and Rising",
         "Original 1st Pressing", "Hip-Hop", 250.00),
    ]


def _jazz_essentials() -> list[tuple[str, str, str, str, float]]:
    """15 Jazz Essentials — original pressings (Blue Note, Columbia, Impulse)."""
    return [
        ("Miles Davis", "Kind of Blue",
         "Original 1st Pressing", "Jazz", 3500.00),
        ("John Coltrane", "A Love Supreme",
         "Original 1st Pressing", "Jazz", 4500.00),
        ("Thelonious Monk", "Brilliant Corners",
         "Original 1st Pressing", "Jazz", 2800.00),
        ("Bill Evans Trio", "Waltz for Debby",
         "Original 1st Pressing", "Jazz", 3200.00),
        ("Art Blakey & The Jazz Messengers", "Moanin'",
         "Original 1st Pressing", "Jazz", 2500.00),
        ("Charles Mingus", "Mingus Ah Um",
         "Original 1st Pressing", "Jazz", 1800.00),
        ("Dave Brubeck Quartet", "Time Out",
         "Original 1st Pressing", "Jazz", 1500.00),
        ("Herbie Hancock", "Head Hunters",
         "Original 1st Pressing", "Jazz", 600.00),
        ("Wayne Shorter", "Speak No Evil",
         "Original 1st Pressing", "Jazz", 2200.00),
        ("Sonny Rollins", "Saxophone Colossus",
         "Original 1st Pressing", "Jazz", 2000.00),
        ("Eric Dolphy", "Out to Lunch!",
         "Original 1st Pressing", "Jazz", 2600.00),
        ("Lee Morgan", "The Sidewinder",
         "Original 1st Pressing", "Jazz", 1800.00),
        ("Cannonball Adderley", "Somethin' Else",
         "Original 1st Pressing", "Jazz", 2400.00),
        ("Freddie Hubbard", "Red Clay",
         "Original 1st Pressing", "Jazz", 500.00),
        ("Alice Coltrane", "Journey in Satchidananda",
         "Original 1st Pressing", "Jazz", 800.00),
    ]


def _indie_alternative() -> list[tuple[str, str, str, str, float]]:
    """15 Indie/Alternative — original pressings and collectible reissues."""
    return [
        ("Radiohead", "OK Computer",
         "Original 1st Pressing", "Indie/Alternative", 350.00),
        ("Radiohead", "Kid A",
         "Original 1st Pressing", "Indie/Alternative", 280.00),
        ("Radiohead", "In Rainbows",
         "Original 1st Pressing", "Indie/Alternative", 200.00),
        ("Nirvana", "Nevermind",
         "Original 1st Pressing", "Indie/Alternative", 450.00),
        ("Nirvana", "In Utero",
         "Original 1st Pressing", "Indie/Alternative", 300.00),
        ("Nirvana", "MTV Unplugged in New York",
         "Original 1st Pressing", "Indie/Alternative", 350.00),
        ("Pixies", "Doolittle",
         "Original 1st Pressing", "Indie/Alternative", 250.00),
        ("My Bloody Valentine", "Loveless",
         "Original 1st Pressing", "Indie/Alternative", 600.00),
        ("Neutral Milk Hotel", "In the Aeroplane Over the Sea",
         "Original 1st Pressing", "Indie/Alternative", 500.00),
        ("Arcade Fire", "Funeral",
         "Original 1st Pressing", "Indie/Alternative", 280.00),
        ("The Smiths", "The Queen Is Dead",
         "Original 1st Pressing", "Indie/Alternative", 200.00),
        ("Sonic Youth", "Daydream Nation",
         "Original 1st Pressing", "Indie/Alternative", 220.00),
        ("Joy Division", "Unknown Pleasures",
         "Original 1st Pressing", "Indie/Alternative", 400.00),
        ("Pavement", "Slanted and Enchanted",
         "Original 1st Pressing", "Indie/Alternative", 280.00),
        ("The Cure", "Disintegration",
         "Original 1st Pressing", "Indie/Alternative", 250.00),
    ]


def _electronic_ambient() -> list[tuple[str, str, str, str, float]]:
    """10 Electronic/Ambient — original pressings and audiophile editions."""
    return [
        ("Kraftwerk", "Trans-Europe Express",
         "Original 1st Pressing", "Electronic", 400.00),
        ("Aphex Twin", "Selected Ambient Works 85-92",
         "Original 1st Pressing", "Electronic", 350.00),
        ("Boards of Canada", "Music Has the Right to Children",
         "Original 1st Pressing", "Electronic", 300.00),
        ("Burial", "Untrue",
         "Original 1st Pressing", "Electronic", 250.00),
        ("Daft Punk", "Discovery",
         "Original 1st Pressing", "Electronic", 280.00),
        ("Daft Punk", "Random Access Memories",
         "Original 1st Pressing", "Electronic", 200.00),
        ("Tangerine Dream", "Phaedra",
         "Original 1st Pressing", "Electronic", 220.00),
        ("Brian Eno", "Ambient 1: Music for Airports",
         "Original 1st Pressing", "Electronic", 300.00),
        ("Autechre", "Tri Repetae",
         "Original 1st Pressing", "Electronic", 180.00),
        ("Massive Attack", "Mezzanine",
         "Original 1st Pressing", "Electronic", 250.00),
    ]


def _soul_funk_rnb() -> list[tuple[str, str, str, str, float]]:
    """10 Soul/Funk/R&B — original pressings of genre-defining albums."""
    return [
        ("Marvin Gaye", "What's Going On",
         "Original 1st Pressing", "Soul/Funk", 500.00),
        ("Stevie Wonder", "Songs in the Key of Life",
         "Original 1st Pressing", "Soul/Funk", 350.00),
        ("Curtis Mayfield", "Superfly",
         "Original 1st Pressing", "Soul/Funk", 280.00),
        ("Parliament", "Mothership Connection",
         "Original 1st Pressing", "Soul/Funk", 300.00),
        ("Isaac Hayes", "Shaft",
         "Original 1st Pressing", "Soul/Funk", 220.00),
        ("Al Green", "Let's Stay Together",
         "Original 1st Pressing", "Soul/Funk", 180.00),
        ("Sly & the Family Stone", "Stand!",
         "Original 1st Pressing", "Soul/Funk", 250.00),
        ("Funkadelic", "Maggot Brain",
         "Original 1st Pressing", "Soul/Funk", 400.00),
        ("D'Angelo", "Voodoo",
         "Original 1st Pressing", "Soul/Funk", 350.00),
        ("Erykah Badu", "Baduizm",
         "Original 1st Pressing", "Soul/Funk", 200.00),
    ]


def _punk_postpunk() -> list[tuple[str, str, str, str, float]]:
    """10 Punk/Post-Punk — original pressings of seminal records."""
    return [
        ("The Clash", "London Calling",
         "Original 1st Pressing", "Punk/Post-Punk", 350.00),
        ("Sex Pistols", "Never Mind the Bollocks, Here's the Sex Pistols",
         "Original 1st Pressing", "Punk/Post-Punk", 500.00),
        ("Ramones", "Ramones",
         "Original 1st Pressing", "Punk/Post-Punk", 600.00),
        ("Dead Kennedys", "Fresh Fruit for Rotting Vegetables",
         "Original 1st Pressing", "Punk/Post-Punk", 250.00),
        ("Black Flag", "Damaged",
         "Original 1st Pressing", "Punk/Post-Punk", 400.00),
        ("Siouxsie and the Banshees", "Juju",
         "Original 1st Pressing", "Punk/Post-Punk", 180.00),
        ("Wire", "Pink Flag",
         "Original 1st Pressing", "Punk/Post-Punk", 300.00),
        ("Bauhaus", "In the Flat Field",
         "Original 1st Pressing", "Punk/Post-Punk", 220.00),
        ("The Damned", "Damned Damned Damned",
         "Original 1st Pressing", "Punk/Post-Punk", 350.00),
        ("Husker Du", "Zen Arcade",
         "Original 1st Pressing", "Punk/Post-Punk", 200.00),
    ]


def _modern_collectible_pressings() -> list[tuple[str, str, str, str, float]]:
    """15 Modern Collectible Pressings — VMP, Mondo, Third Man, RSD, Newbury."""
    return [
        ("Tyler, the Creator", "Call Me If You Get Lost",
         "Numbered Limited", "Modern Collectible", 75.00),
        ("Khruangbin", "Con Todo El Mundo",
         "Numbered Limited", "Modern Collectible", 65.00),
        ("Tame Impala", "Currents",
         "Colored/Splatter Vinyl", "Modern Collectible", 55.00),
        ("Anderson .Paak", "Malibu",
         "Numbered Limited", "Modern Collectible", 70.00),
        ("Gorillaz", "Demon Days",
         "Colored/Splatter Vinyl", "Modern Collectible", 80.00),
        ("Queens of the Stone Age", "Songs for the Deaf",
         "RSD Exclusive", "Modern Collectible", 65.00),
        ("Run the Jewels", "RTJ4",
         "Colored/Splatter Vinyl", "Modern Collectible", 50.00),
        ("St. Vincent", "Masseduction",
         "Colored/Splatter Vinyl", "Modern Collectible", 45.00),
        ("Phoebe Bridgers", "Punisher",
         "Colored/Splatter Vinyl", "Modern Collectible", 60.00),
        ("Jack White", "Lazaretto (Ultra LP)",
         "Numbered Limited", "Modern Collectible", 55.00),
        ("The White Stripes", "Elephant (Third Man Vault)",
         "Numbered Limited", "Modern Collectible", 120.00),
        ("Mondo", "Blade Runner 2049 Soundtrack",
         "Numbered Limited", "Modern Collectible", 90.00),
        ("Newbury Comics", "Fleetwood Mac - Rumours (Blue Vinyl)",
         "Colored/Splatter Vinyl", "Modern Collectible", 55.00),
        ("VMP", "Amy Winehouse - Back to Black (VMP Exclusive)",
         "Numbered Limited", "Modern Collectible", 70.00),
        ("RSD 2024", "Nirvana - MTV Unplugged (Picture Disc)",
         "Picture Disc", "Modern Collectible", 45.00),
    ]


def _soundtracks_scores() -> list[tuple[str, str, str, str, float]]:
    """10 Soundtracks & Scores — collectible film and game soundtracks."""
    return [
        ("Vangelis", "Blade Runner (Original Soundtrack)",
         "Original 1st Pressing", "Soundtrack", 350.00),
        ("Cliff Martinez", "Drive (Original Motion Picture Soundtrack)",
         "Colored/Splatter Vinyl", "Soundtrack", 65.00),
        ("Various Artists", "Pulp Fiction (Music from the Motion Picture)",
         "Original 1st Pressing", "Soundtrack", 200.00),
        ("Ennio Morricone", "The Good, the Bad and the Ugly (OST)",
         "Original 1st Pressing", "Soundtrack", 400.00),
        ("Geinoh Yamashirogumi", "Akira (Original Soundtrack)",
         "Original 1st Pressing", "Soundtrack", 500.00),
        ("Hans Zimmer", "Interstellar (Original Motion Picture Soundtrack)",
         "Numbered Limited", "Soundtrack", 80.00),
        ("John Williams", "Star Wars: A New Hope (Original Soundtrack)",
         "Original 1st Pressing", "Soundtrack", 600.00),
        ("Howard Shore", "The Lord of the Rings: The Fellowship (Complete Recordings)",
         "Box Set", "Soundtrack", 180.00),
        ("Angelo Badalamenti", "Twin Peaks (Original Soundtrack)",
         "Colored/Splatter Vinyl", "Soundtrack", 55.00),
        ("Trent Reznor & Atticus Ross", "The Social Network (Soundtrack)",
         "Numbered Limited", "Soundtrack", 75.00),
    ]


def _country_folk_blues() -> list[tuple[str, str, str, str, float]]:
    """10 Country/Folk/Blues — original pressings and audiophile reissues."""
    return [
        ("Johnny Cash", "At Folsom Prison",
         "Original 1st Pressing", "Country/Folk/Blues", 400.00),
        ("Bob Dylan", "Highway 61 Revisited",
         "Original 1st Pressing", "Country/Folk/Blues", 900.00),
        ("Bob Dylan", "Blood on the Tracks",
         "Original 1st Pressing", "Country/Folk/Blues", 500.00),
        ("Joni Mitchell", "Blue",
         "Original 1st Pressing", "Country/Folk/Blues", 450.00),
        ("Robert Johnson", "King of the Delta Blues Singers",
         "Original 1st Pressing", "Country/Folk/Blues", 2000.00),
        ("Nick Drake", "Pink Moon",
         "Original 1st Pressing", "Country/Folk/Blues", 1500.00),
        ("Townes Van Zandt", "Townes Van Zandt",
         "Original 1st Pressing", "Country/Folk/Blues", 600.00),
        ("Gillian Welch", "Revival",
         "Original 1st Pressing", "Country/Folk/Blues", 200.00),
        ("John Prine", "John Prine",
         "Original 1st Pressing", "Country/Folk/Blues", 350.00),
        ("Emmylou Harris", "Wrecking Ball",
         "Audiophile (MFSL/Half-Speed)", "Country/Folk/Blues", 120.00),
    ]


# ---------------------------------------------------------------------------
# Aggregate catalog
# ---------------------------------------------------------------------------

SUBCATEGORY_FUNCTIONS = [
    ("Classic Rock Icons", _classic_rock_icons),
    ("Hip-Hop & R&B Grails", _hiphop_rnb_grails),
    ("Jazz Essentials", _jazz_essentials),
    ("Indie/Alternative", _indie_alternative),
    ("Electronic/Ambient", _electronic_ambient),
    ("Soul/Funk/R&B", _soul_funk_rnb),
    ("Punk/Post-Punk", _punk_postpunk),
    ("Modern Collectible Pressings", _modern_collectible_pressings),
    ("Soundtracks & Scores", _soundtracks_scores),
    ("Country/Folk/Blues", _country_folk_blues),
]


def get_curated_catalog() -> list[tuple[str, str, str, str, float]]:
    """Return the full curated catalog as a flat list of all vinyl records.

    Each tuple: (artist, album, pressing_type, genre, price_eur)
    """
    catalog: list[tuple[str, str, str, str, float]] = []
    for _name, fn in SUBCATEGORY_FUNCTIONS:
        catalog.extend(fn())
    return catalog


# ---------------------------------------------------------------------------
# Transform helpers
# ---------------------------------------------------------------------------


def _pressing_type_score(pressing_type: str) -> float:
    """Map a pressing type to a 0-1 rarity score."""
    return PRESSING_TYPE_SCORES.get(pressing_type, 0.25)


def _genre_popularity_score(genre: str) -> float:
    """Map a genre to a 0-1 popularity score."""
    return GENRE_POPULARITY.get(genre, 0.50)


def _collectibility_score(pressing_type: str, price_eur: float) -> float:
    """Compute a 0-1 collectibility score based on pressing type and price.

    Higher for original pressings, limited editions, and high-value records.
    """
    base_scores: dict[str, float] = {
        "Original 1st Pressing": 0.85,
        "Numbered Limited": 0.75,
        "Colored/Splatter Vinyl": 0.60,
        "Audiophile (MFSL/Half-Speed)": 0.70,
        "Standard Repress": 0.25,
        "Picture Disc": 0.50,
        "Box Set": 0.65,
        "Promo/Test Pressing": 0.90,
        "RSD Exclusive": 0.65,
        "Standard": 0.20,
    }
    score = base_scores.get(pressing_type, 0.30)

    # Price tier boost
    if price_eur >= 1000:
        score = min(score + 0.15, 1.0)
    elif price_eur >= 500:
        score = min(score + 0.10, 1.0)
    elif price_eur >= 200:
        score = min(score + 0.05, 1.0)

    return round(score, 2)


def _vinyl_to_catalog_item(
    item: tuple[str, str, str, str, float],
) -> CatalogItem:
    """Convert a vinyl record tuple to a CatalogItem.

    Args:
        item: (artist, album, pressing_type, genre, price_eur)

    Returns:
        CatalogItem with category='vinyl_records', item_key from slugify,
        brand=artist, set_code=genre.
    """
    artist, album, pressing_type, genre, price_eur = item

    title = f"{artist} - {album}"
    item_key = slugify(f"{artist}-{album}-{pressing_type}")

    return CatalogItem(
        category=CATEGORY,
        item_key=item_key,
        title=title,
        set_code=genre,
        brand=artist,
        rarity=pressing_type,
        notes=f"{genre} | {pressing_type} | ~EUR {price_eur:.0f}",
        attributes_json={
            "artist": artist,
            "album": album,
            "pressing_type": pressing_type,
            "genre": genre,
        },
    )


def _vinyl_to_price_observation(
    item: tuple[str, str, str, str, float],
) -> PriceObservation:
    """Convert a vinyl record tuple to a PriceObservation.

    Args:
        item: (artist, album, pressing_type, genre, price_eur)

    Returns:
        PriceObservation with features:
            - condition_score: 0.90 (assumes NM for catalog baseline)
            - pressing_score: from PRESSING_TYPE_SCORES
            - genre_popularity: from GENRE_POPULARITY
            - is_sealed: 1.0 (assumes sealed for baseline pricing)
            - collectibility_score: computed from pressing type + price
    """
    _artist, _album, pressing_type, genre, price_eur = item

    return PriceObservation(
        features={
            "condition_score": CONDITION_GRADE_SCORES["NM"],  # 0.90
            "pressing_score": _pressing_type_score(pressing_type),
            "genre_popularity": _genre_popularity_score(genre),
            "is_sealed": 1.0,
            "collectibility_score": _collectibility_score(pressing_type, price_eur),
        },
        price=price_eur,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Import curated vinyl records catalog + prices"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write local files only, skip Supabase upsert",
    )
    parser.add_argument(
        "--jsonl-only",
        action="store_true",
        help="Only write training JSONL, skip catalog SQL and Supabase",
    )
    parser.add_argument(
        "--cache-images",
        action="store_true",
        help="Cache catalog images to S3 (requires AWS credentials)",
    )
    args = parser.parse_args()

    logger.info("=== Vinyl Records Import (Curated Catalog) ===")

    ingest = SupabaseIngest()
    if args.dry_run or args.jsonl_only:
        ingest.enabled = False

    # Build full catalog
    raw_catalog = get_curated_catalog()
    logger.info(f"Total curated records: {len(raw_catalog)}")

    # Transform to CatalogItem + PriceObservation
    all_items: list[CatalogItem] = []
    all_observations: list[PriceObservation] = []

    for subcategory_name, fn in SUBCATEGORY_FUNCTIONS:
        records = fn()
        logger.info(f"--- {subcategory_name}: {len(records)} records ---")

        for record in records:
            all_items.append(_vinyl_to_catalog_item(record))
            all_observations.append(_vinyl_to_price_observation(record))

        log_progress(CATEGORY, f"{subcategory_name} loaded", len(records))

    logger.info(f"Catalog items: {len(all_items)}")
    logger.info(f"Price observations: {len(all_observations)}")

    # Optionally cache images to S3
    if args.cache_images:
        all_items = cache_catalog_images(all_items, dry_run=args.dry_run)

    # Write training JSONL
    jsonl_path = write_training_jsonl(CATEGORY, all_observations)
    log_progress(CATEGORY, "training JSONL written", len(all_observations))
    logger.info(f"  JSONL path: {jsonl_path}")

    if not args.jsonl_only:
        # Write catalog SQL
        sql_path = write_catalog_sql(CATEGORY, all_items)
        log_progress(CATEGORY, "catalog SQL written", len(all_items))
        logger.info(f"  SQL path: {sql_path}")

        # Upsert to Supabase
        if ingest.enabled:
            inserted = ingest.upsert_catalog(all_items)
            log_progress(CATEGORY, "catalog upserted", inserted)

    ingest.close()
    close_http_client()

    logger.info("\n=== Vinyl Records Import Complete ===")
    logger.info(f"  Subcategories:       {len(SUBCATEGORY_FUNCTIONS)}")
    logger.info(f"  Total catalog items: {len(all_items)}")
    logger.info(f"  Price observations:  {len(all_observations)}")

    if args.dry_run:
        logger.info("  Mode: DRY RUN (local files only)")
    elif args.jsonl_only:
        logger.info("  Mode: JSONL ONLY (training data only)")


if __name__ == "__main__":
    main()
