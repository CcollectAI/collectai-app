"""
Curated Vinyl Records Import Pipeline.

Imports a hand-curated catalog of 500+ collectible vinyl records across
14 subcategories: Classic Rock, Hip-Hop/R&B, Jazz, Indie/Alternative,
Electronic/Ambient, Soul/Funk/R&B, Punk/Post-Punk, Modern Collectible
Pressings, Soundtracks & Scores, Country/Folk/Blues, Metal/Heavy,
Audiophile Pressings (MFSL/AP/Tone Poet/Japanese OBI),
RSD Exclusives/Colored Variants/Box Sets, and Modern Pop/World/Classical.

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
    """55 Classic Rock Icons — original pressings and collectible editions."""
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
        ("The Beatles", "Revolver",
         "Original 1st Pressing", "Classic Rock", 1200.00),
        ("Pink Floyd", "The Wall",
         "Original 1st Pressing", "Classic Rock", 400.00),
        ("The Rolling Stones", "Let It Bleed",
         "Original 1st Pressing", "Classic Rock", 500.00),
        ("David Bowie", "Low",
         "Original 1st Pressing", "Classic Rock", 350.00),
        ("Deep Purple", "Machine Head",
         "Original 1st Pressing", "Classic Rock", 280.00),
        ("Black Sabbath", "Paranoid",
         "Original 1st Pressing", "Classic Rock", 550.00),
        ("Cream", "Disraeli Gears",
         "Original 1st Pressing", "Classic Rock", 320.00),
        ("The Doors", "The Doors",
         "Original 1st Pressing", "Classic Rock", 500.00),
        ("The Doors", "L.A. Woman",
         "Original 1st Pressing", "Classic Rock", 380.00),
        ("Neil Young", "After the Gold Rush",
         "Original 1st Pressing", "Classic Rock", 300.00),
        ("AC/DC", "Back in Black",
         "Original 1st Pressing", "Classic Rock", 250.00),
        ("Jimi Hendrix", "Are You Experienced",
         "Original 1st Pressing", "Classic Rock", 800.00),
        ("The Velvet Underground & Nico", "The Velvet Underground & Nico",
         "Original 1st Pressing", "Classic Rock", 3500.00),
        ("King Crimson", "In the Court of the Crimson King",
         "Original 1st Pressing", "Classic Rock", 600.00),
        ("Yes", "Close to the Edge",
         "Original 1st Pressing", "Classic Rock", 220.00),
        # ── Additional Classic Rock ───────────────────────────────────────
        ("The Beatles", "Let It Be",
         "Original 1st Pressing", "Classic Rock", 900.00),
        ("The Beatles", "Rubber Soul",
         "Original 1st Pressing", "Classic Rock", 800.00),
        ("The Beatles", "A Hard Day's Night",
         "Original 1st Pressing", "Classic Rock", 750.00),
        ("The Rolling Stones", "Sticky Fingers",
         "Original 1st Pressing", "Classic Rock", 400.00),
        ("The Rolling Stones", "Beggars Banquet",
         "Original 1st Pressing", "Classic Rock", 350.00),
        ("Led Zeppelin", "Houses of the Holy",
         "Original 1st Pressing", "Classic Rock", 450.00),
        ("Led Zeppelin", "Led Zeppelin III",
         "Original 1st Pressing", "Classic Rock", 500.00),
        ("Pink Floyd", "Animals",
         "Original 1st Pressing", "Classic Rock", 350.00),
        ("Pink Floyd", "Meddle",
         "Original 1st Pressing", "Classic Rock", 300.00),
        ("Pink Floyd", "Atom Heart Mother",
         "Original 1st Pressing", "Classic Rock", 250.00),
        ("David Bowie", "Heroes",
         "Original 1st Pressing", "Classic Rock", 300.00),
        ("David Bowie", "Hunky Dory",
         "Original 1st Pressing", "Classic Rock", 400.00),
        ("David Bowie", "Aladdin Sane",
         "Original 1st Pressing", "Classic Rock", 350.00),
        ("Queen", "News of the World",
         "Original 1st Pressing", "Classic Rock", 280.00),
        ("Queen", "A Day at the Races",
         "Original 1st Pressing", "Classic Rock", 250.00),
        ("Black Sabbath", "Black Sabbath",
         "Original 1st Pressing", "Classic Rock", 600.00),
        ("Black Sabbath", "Master of Reality",
         "Original 1st Pressing", "Classic Rock", 400.00),
        ("Steely Dan", "Aja",
         "Original 1st Pressing", "Classic Rock", 200.00),
        ("Steely Dan", "Gaucho",
         "Original 1st Pressing", "Classic Rock", 180.00),
        ("The Allman Brothers Band", "At Fillmore East",
         "Original 1st Pressing", "Classic Rock", 300.00),
        ("Lynyrd Skynyrd", "Pronounced Leh-Nerd Skin-Nerd",
         "Original 1st Pressing", "Classic Rock", 250.00),
        ("Crosby, Stills, Nash & Young", "Deja Vu",
         "Original 1st Pressing", "Classic Rock", 200.00),
        ("Neil Young", "Harvest",
         "Original 1st Pressing", "Classic Rock", 250.00),
        ("The Who", "Tommy",
         "Original 1st Pressing", "Classic Rock", 320.00),
        ("Genesis", "Selling England by the Pound",
         "Original 1st Pressing", "Classic Rock", 200.00),
    ]


def _hiphop_rnb_grails() -> list[tuple[str, str, str, str, float]]:
    """30 Hip-Hop & R&B Grails — original pressings and sought-after editions."""
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
        ("2Pac", "All Eyez on Me",
         "Original 1st Pressing", "Hip-Hop", 800.00),
        ("Eminem", "The Slim Shady LP",
         "Original 1st Pressing", "Hip-Hop", 350.00),
        ("Dr. Dre", "The Chronic",
         "Original 1st Pressing", "Hip-Hop", 500.00),
        ("Kendrick Lamar", "good kid, m.A.A.d city",
         "Original 1st Pressing", "Hip-Hop", 180.00),
        ("Travis Scott", "Astroworld",
         "Colored/Splatter Vinyl", "Hip-Hop", 120.00),
        ("Mobb Deep", "The Infamous",
         "Original 1st Pressing", "Hip-Hop", 400.00),
        ("GZA", "Liquid Swords",
         "Original 1st Pressing", "Hip-Hop", 300.00),
        ("Raekwon", "Only Built 4 Cuban Linx...",
         "Original 1st Pressing", "Hip-Hop", 450.00),
        ("Snoop Dogg", "Doggystyle",
         "Original 1st Pressing", "Hip-Hop", 350.00),
        ("Ice Cube", "AmeriKKKa's Most Wanted",
         "Original 1st Pressing", "Hip-Hop", 280.00),
        ("Fugees", "The Score",
         "Original 1st Pressing", "Hip-Hop", 220.00),
        ("Scarface", "The Diary",
         "Original 1st Pressing", "Hip-Hop", 300.00),
        ("Eric B. & Rakim", "Paid in Full",
         "Original 1st Pressing", "Hip-Hop", 350.00),
        ("Slick Rick", "The Great Adventures of Slick Rick",
         "Original 1st Pressing", "Hip-Hop", 400.00),
        ("Kanye West", "The College Dropout",
         "Original 1st Pressing", "Hip-Hop", 250.00),
        # ── Additional Hip-Hop ─────────────────────────────────────────────
        ("Kanye West", "Late Registration",
         "Original 1st Pressing", "Hip-Hop", 200.00),
        ("Kanye West", "808s & Heartbreak",
         "Original 1st Pressing", "Hip-Hop", 180.00),
        ("Kanye West", "Yeezus",
         "Original 1st Pressing", "Hip-Hop", 150.00),
        ("Kendrick Lamar", "DAMN.",
         "Original 1st Pressing", "Hip-Hop", 120.00),
        ("Kendrick Lamar", "Section.80",
         "Original 1st Pressing", "Hip-Hop", 250.00),
        ("Tyler, the Creator", "Flower Boy",
         "Original 1st Pressing", "Hip-Hop", 150.00),
        ("Tyler, the Creator", "Chromakopia",
         "Colored/Splatter Vinyl", "Hip-Hop", 55.00),
        ("Mac Miller", "Swimming",
         "Original 1st Pressing", "Hip-Hop", 200.00),
        ("Mac Miller", "Circles",
         "Colored/Splatter Vinyl", "Hip-Hop", 80.00),
        ("Nipsey Hussle", "Victory Lap",
         "Original 1st Pressing", "Hip-Hop", 300.00),
        ("Beastie Boys", "Paul's Boutique",
         "Original 1st Pressing", "Hip-Hop", 350.00),
        ("Beastie Boys", "Licensed to Ill",
         "Original 1st Pressing", "Hip-Hop", 250.00),
        ("Run-DMC", "Raising Hell",
         "Original 1st Pressing", "Hip-Hop", 200.00),
        ("N.W.A", "Straight Outta Compton",
         "Original 1st Pressing", "Hip-Hop", 400.00),
        ("Public Enemy", "It Takes a Nation of Millions to Hold Us Back",
         "Original 1st Pressing", "Hip-Hop", 300.00),
        ("Wu-Tang Clan", "Wu-Tang Forever",
         "Original 1st Pressing", "Hip-Hop", 250.00),
        ("Method Man", "Tical",
         "Original 1st Pressing", "Hip-Hop", 200.00),
        ("Ghostface Killah", "Supreme Clientele",
         "Original 1st Pressing", "Hip-Hop", 280.00),
        ("Mos Def", "Black on Both Sides",
         "Original 1st Pressing", "Hip-Hop", 250.00),
        ("Talib Kweli & Hi-Tek", "Train of Thought",
         "Original 1st Pressing", "Hip-Hop", 180.00),
        ("Common", "Be",
         "Original 1st Pressing", "Hip-Hop", 150.00),
        ("The Roots", "Things Fall Apart",
         "Original 1st Pressing", "Hip-Hop", 200.00),
        ("Lil Wayne", "Tha Carter III",
         "Original 1st Pressing", "Hip-Hop", 150.00),
        ("50 Cent", "Get Rich or Die Tryin'",
         "Original 1st Pressing", "Hip-Hop", 180.00),
        ("Drake", "Take Care",
         "Original 1st Pressing", "Hip-Hop", 120.00),
        ("J. Cole", "2014 Forest Hills Drive",
         "Original 1st Pressing", "Hip-Hop", 100.00),
        ("Freddie Gibbs & Madlib", "Pinata",
         "Original 1st Pressing", "Hip-Hop", 150.00),
        ("Danny Brown", "Atrocity Exhibition",
         "Colored/Splatter Vinyl", "Hip-Hop", 65.00),
        ("Pusha T", "Daytona",
         "Original 1st Pressing", "Hip-Hop", 120.00),
    ]


def _jazz_essentials() -> list[tuple[str, str, str, str, float]]:
    """28 Jazz Essentials — original pressings (Blue Note, Columbia, Impulse)."""
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
        ("Miles Davis", "Bitches Brew",
         "Original 1st Pressing", "Jazz", 1200.00),
        ("John Coltrane", "Blue Train",
         "Original 1st Pressing", "Jazz", 3800.00),
        ("Dexter Gordon", "Go!",
         "Original 1st Pressing", "Jazz", 1600.00),
        ("Ornette Coleman", "The Shape of Jazz to Come",
         "Original 1st Pressing", "Jazz", 2000.00),
        ("Grant Green", "Idle Moments",
         "Original 1st Pressing", "Jazz", 1400.00),
        ("Pharoah Sanders", "Karma",
         "Original 1st Pressing", "Jazz", 900.00),
        ("Clifford Brown & Max Roach", "Clifford Brown and Max Roach",
         "Original 1st Pressing", "Jazz", 1800.00),
        ("Hank Mobley", "Soul Station",
         "Original 1st Pressing", "Jazz", 2200.00),
        ("Horace Silver", "Song for My Father",
         "Original 1st Pressing", "Jazz", 1500.00),
        ("McCoy Tyner", "The Real McCoy",
         "Original 1st Pressing", "Jazz", 1800.00),
        ("Bobby Hutcherson", "Happenings",
         "Original 1st Pressing", "Jazz", 1600.00),
        ("Andrew Hill", "Point of Departure",
         "Original 1st Pressing", "Jazz", 2400.00),
        ("Joe Henderson", "Page One",
         "Original 1st Pressing", "Jazz", 2000.00),
        # ── Additional Jazz ────────────────────────────────────────────────
        ("Miles Davis", "Sketches of Spain",
         "Original 1st Pressing", "Jazz", 800.00),
        ("Miles Davis", "In a Silent Way",
         "Original 1st Pressing", "Jazz", 600.00),
        ("Miles Davis", "Miles Smiles",
         "Original 1st Pressing", "Jazz", 1200.00),
        ("John Coltrane", "My Favorite Things",
         "Original 1st Pressing", "Jazz", 1500.00),
        ("John Coltrane", "Giant Steps",
         "Original 1st Pressing", "Jazz", 2500.00),
        ("John Coltrane", "Crescent",
         "Original 1st Pressing", "Jazz", 1800.00),
        ("Thelonious Monk", "Monk's Music",
         "Original 1st Pressing", "Jazz", 2000.00),
        ("Thelonious Monk", "Thelonious Monk Trio",
         "Original 1st Pressing", "Jazz", 1600.00),
        ("Bill Evans Trio", "Sunday at the Village Vanguard",
         "Original 1st Pressing", "Jazz", 2800.00),
        ("Bill Evans Trio", "Portrait in Jazz",
         "Original 1st Pressing", "Jazz", 2200.00),
        ("Chet Baker", "Chet Baker Sings",
         "Original 1st Pressing", "Jazz", 1800.00),
        ("Stan Getz & Joao Gilberto", "Getz/Gilberto",
         "Original 1st Pressing", "Jazz", 1200.00),
        ("Wes Montgomery", "The Incredible Jazz Guitar",
         "Original 1st Pressing", "Jazz", 1500.00),
        ("Charles Mingus", "The Black Saint and the Sinner Lady",
         "Original 1st Pressing", "Jazz", 2400.00),
        ("Art Pepper", "Art Pepper Meets the Rhythm Section",
         "Original 1st Pressing", "Jazz", 2000.00),
        ("Freddie Hubbard", "Hub-Tones",
         "Original 1st Pressing", "Jazz", 1800.00),
        ("Wayne Shorter", "JuJu",
         "Original 1st Pressing", "Jazz", 1600.00),
        ("Jackie McLean", "Let Freedom Ring",
         "Original 1st Pressing", "Jazz", 2200.00),
        ("Kenny Dorham", "Afro-Cuban",
         "Original 1st Pressing", "Jazz", 3000.00),
        ("Lee Morgan", "Search for the New Land",
         "Original 1st Pressing", "Jazz", 1400.00),
        ("Herbie Hancock", "Empyrean Isles",
         "Original 1st Pressing", "Jazz", 1500.00),
        ("Donald Byrd", "A New Perspective",
         "Original 1st Pressing", "Jazz", 1600.00),
        ("Ahmad Jamal", "At the Pershing: But Not for Me",
         "Original 1st Pressing", "Jazz", 800.00),
        ("Kamasi Washington", "The Epic",
         "Original 1st Pressing", "Jazz", 120.00),
        ("Robert Glasper Experiment", "Black Radio",
         "Original 1st Pressing", "Jazz", 100.00),
        ("Nubya Garcia", "Source",
         "Original 1st Pressing", "Jazz", 80.00),
        ("Shabaka Hutchings", "Wisdom of Elders",
         "Original 1st Pressing", "Jazz", 90.00),
        ("Esperanza Spalding", "Emily's D+Evolution",
         "Original 1st Pressing", "Jazz", 70.00),
        ("Sun Ra", "Space Is the Place",
         "Original 1st Pressing", "Jazz", 1800.00),
        ("John Coltrane", "Ascension",
         "Original 1st Pressing", "Jazz", 1200.00),
    ]


def _indie_alternative() -> list[tuple[str, str, str, str, float]]:
    """21 Indie/Alternative — original pressings and collectible reissues."""
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
        ("Deafheaven", "Sunbather",
         "Original 1st Pressing", "Indie/Alternative", 180.00),
        ("Slowdive", "Souvlaki",
         "Original 1st Pressing", "Indie/Alternative", 350.00),
        ("The National", "Boxer",
         "Original 1st Pressing", "Indie/Alternative", 150.00),
        ("Sufjan Stevens", "Illinois",
         "Original 1st Pressing", "Indie/Alternative", 200.00),
        ("Bon Iver", "For Emma, Forever Ago",
         "Original 1st Pressing", "Indie/Alternative", 250.00),
        ("Elliott Smith", "Either/Or",
         "Original 1st Pressing", "Indie/Alternative", 300.00),
        # ── Additional Indie/Alternative ───────────────────────────────────
        ("Radiohead", "The Bends",
         "Original 1st Pressing", "Indie/Alternative", 250.00),
        ("Radiohead", "Amnesiac",
         "Original 1st Pressing", "Indie/Alternative", 180.00),
        ("My Bloody Valentine", "Isn't Anything",
         "Original 1st Pressing", "Indie/Alternative", 400.00),
        ("Pixies", "Surfer Rosa",
         "Original 1st Pressing", "Indie/Alternative", 300.00),
        ("Pixies", "Bossanova",
         "Original 1st Pressing", "Indie/Alternative", 200.00),
        ("The Smiths", "Meat Is Murder",
         "Original 1st Pressing", "Indie/Alternative", 180.00),
        ("The Smiths", "The Smiths",
         "Original 1st Pressing", "Indie/Alternative", 200.00),
        ("R.E.M.", "Murmur",
         "Original 1st Pressing", "Indie/Alternative", 200.00),
        ("R.E.M.", "Automatic for the People",
         "Original 1st Pressing", "Indie/Alternative", 150.00),
        ("Smashing Pumpkins", "Siamese Dream",
         "Original 1st Pressing", "Indie/Alternative", 280.00),
        ("Smashing Pumpkins", "Mellon Collie and the Infinite Sadness",
         "Original 1st Pressing", "Indie/Alternative", 350.00),
        ("Weezer", "Weezer (Blue Album)",
         "Original 1st Pressing", "Indie/Alternative", 200.00),
        ("Weezer", "Pinkerton",
         "Original 1st Pressing", "Indie/Alternative", 350.00),
        ("Jeff Buckley", "Grace",
         "Original 1st Pressing", "Indie/Alternative", 400.00),
        ("Modest Mouse", "The Moon & Antarctica",
         "Original 1st Pressing", "Indie/Alternative", 250.00),
    ]


def _electronic_ambient() -> list[tuple[str, str, str, str, float]]:
    """26 Electronic/Ambient — original pressings and audiophile editions."""
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
        ("Portishead", "Dummy",
         "Original 1st Pressing", "Electronic", 220.00),
        ("The Prodigy", "The Fat of the Land",
         "Original 1st Pressing", "Electronic", 180.00),
        ("Aphex Twin", "Drukqs",
         "Original 1st Pressing", "Electronic", 280.00),
        ("Underworld", "Dubnobasswithmyheadman",
         "Original 1st Pressing", "Electronic", 200.00),
        ("The Chemical Brothers", "Dig Your Own Hole",
         "Original 1st Pressing", "Electronic", 180.00),
        ("Bjork", "Homogenic",
         "Original 1st Pressing", "Electronic", 250.00),
        ("Four Tet", "Rounds",
         "Original 1st Pressing", "Electronic", 150.00),
        ("Squarepusher", "Feed Me Weird Things",
         "Original 1st Pressing", "Electronic", 300.00),
        ("Kraftwerk", "Computer World",
         "Original 1st Pressing", "Electronic", 350.00),
        ("Brian Eno", "Another Green World",
         "Original 1st Pressing", "Electronic", 280.00),
        ("Depeche Mode", "Violator",
         "Original 1st Pressing", "Electronic", 200.00),
        ("New Order", "Technique",
         "Original 1st Pressing", "Electronic", 180.00),
        ("Orbital", "Orbital (Green Album)",
         "Original 1st Pressing", "Electronic", 150.00),
        ("Boards of Canada", "Geogaddi",
         "Original 1st Pressing", "Electronic", 280.00),
        ("Aphex Twin", "Richard D. James Album",
         "Original 1st Pressing", "Electronic", 220.00),
        ("Burial", "Burial",
         "Original 1st Pressing", "Electronic", 200.00),
        # ── Additional Electronic ──────────────────────────────────────────
        ("Kraftwerk", "Autobahn",
         "Original 1st Pressing", "Electronic", 300.00),
        ("Kraftwerk", "The Man-Machine",
         "Original 1st Pressing", "Electronic", 280.00),
        ("Aphex Twin", "...I Care Because You Do",
         "Original 1st Pressing", "Electronic", 250.00),
        ("Aphex Twin", "Syro",
         "Original 1st Pressing", "Electronic", 120.00),
        ("Daft Punk", "Homework",
         "Original 1st Pressing", "Electronic", 250.00),
        ("Daft Punk", "Human After All",
         "Original 1st Pressing", "Electronic", 150.00),
        ("Boards of Canada", "The Campfire Headphase",
         "Original 1st Pressing", "Electronic", 200.00),
        ("Brian Eno", "Discreet Music",
         "Original 1st Pressing", "Electronic", 200.00),
        ("Tangerine Dream", "Rubycon",
         "Original 1st Pressing", "Electronic", 180.00),
        ("Klaus Schulze", "Timewind",
         "Original 1st Pressing", "Electronic", 220.00),
        ("Jean-Michel Jarre", "Oxygene",
         "Original 1st Pressing", "Electronic", 150.00),
        ("Vangelis", "Spiral",
         "Original 1st Pressing", "Electronic", 180.00),
        ("Portishead", "Third",
         "Original 1st Pressing", "Electronic", 180.00),
        ("Massive Attack", "Blue Lines",
         "Original 1st Pressing", "Electronic", 300.00),
    ]


def _soul_funk_rnb() -> list[tuple[str, str, str, str, float]]:
    """24 Soul/Funk/R&B — original pressings of genre-defining albums."""
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
        ("Otis Redding", "Otis Blue/Otis Redding Sings Soul",
         "Original 1st Pressing", "Soul/Funk", 450.00),
        ("James Brown", "Live at the Apollo",
         "Original 1st Pressing", "Soul/Funk", 600.00),
        ("Aretha Franklin", "I Never Loved a Man the Way I Love You",
         "Original 1st Pressing", "Soul/Funk", 380.00),
        ("Earth, Wind & Fire", "That's the Way of the World",
         "Original 1st Pressing", "Soul/Funk", 200.00),
        ("Prince", "Purple Rain",
         "Original 1st Pressing", "Soul/Funk", 250.00),
        ("Whitney Houston", "Whitney Houston",
         "Original 1st Pressing", "Soul/Funk", 150.00),
        ("The Temptations", "Cloud Nine",
         "Original 1st Pressing", "Soul/Funk", 280.00),
        ("Gil Scott-Heron", "Pieces of a Man",
         "Original 1st Pressing", "Soul/Funk", 350.00),
        ("Donny Hathaway", "Donny Hathaway Live",
         "Original 1st Pressing", "Soul/Funk", 200.00),
        ("Chaka Khan", "Chaka",
         "Original 1st Pressing", "Soul/Funk", 120.00),
        ("The Isley Brothers", "3 + 3",
         "Original 1st Pressing", "Soul/Funk", 150.00),
        ("Roy Ayers", "Everybody Loves the Sunshine",
         "Original 1st Pressing", "Soul/Funk", 280.00),
        ("Bobby Womack", "Across 110th Street (OST)",
         "Original 1st Pressing", "Soul/Funk", 300.00),
        ("Terry Callier", "What Color Is Love",
         "Original 1st Pressing", "Soul/Funk", 350.00),
        # ── Additional Soul/Funk ───────────────────────────────────────────
        ("Stevie Wonder", "Innervisions",
         "Original 1st Pressing", "Soul/Funk", 300.00),
        ("Stevie Wonder", "Talking Book",
         "Original 1st Pressing", "Soul/Funk", 250.00),
        ("Prince", "Sign o' the Times",
         "Original 1st Pressing", "Soul/Funk", 300.00),
        ("Prince", "1999",
         "Original 1st Pressing", "Soul/Funk", 200.00),
        ("Sade", "Diamond Life",
         "Original 1st Pressing", "Soul/Funk", 150.00),
        ("Michael Jackson", "Thriller",
         "Original 1st Pressing", "Soul/Funk", 200.00),
        ("Michael Jackson", "Off the Wall",
         "Original 1st Pressing", "Soul/Funk", 180.00),
        ("Marvin Gaye", "Let's Get It On",
         "Original 1st Pressing", "Soul/Funk", 350.00),
        ("Curtis Mayfield", "Curtis",
         "Original 1st Pressing", "Soul/Funk", 300.00),
        ("Bill Withers", "Still Bill",
         "Original 1st Pressing", "Soul/Funk", 250.00),
    ]


def _punk_postpunk() -> list[tuple[str, str, str, str, float]]:
    """22 Punk/Post-Punk — original pressings of seminal records."""
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
        ("Minor Threat", "Complete Discography",
         "Original 1st Pressing", "Punk/Post-Punk", 280.00),
        ("Gang of Four", "Entertainment!",
         "Original 1st Pressing", "Punk/Post-Punk", 250.00),
        ("Talking Heads", "Remain in Light",
         "Original 1st Pressing", "Punk/Post-Punk", 300.00),
        ("Television", "Marquee Moon",
         "Original 1st Pressing", "Punk/Post-Punk", 450.00),
        ("Fugazi", "Repeater",
         "Original 1st Pressing", "Punk/Post-Punk", 200.00),
        ("New Order", "Power, Corruption & Lies",
         "Original 1st Pressing", "Punk/Post-Punk", 280.00),
        ("Misfits", "Walk Among Us",
         "Original 1st Pressing", "Punk/Post-Punk", 500.00),
        ("Bad Brains", "Bad Brains",
         "Original 1st Pressing", "Punk/Post-Punk", 600.00),
        ("Crass", "The Feeding of the 5000",
         "Original 1st Pressing", "Punk/Post-Punk", 350.00),
        ("Cocteau Twins", "Heaven or Las Vegas",
         "Original 1st Pressing", "Punk/Post-Punk", 250.00),
        ("Buzzcocks", "Singles Going Steady",
         "Original 1st Pressing", "Punk/Post-Punk", 200.00),
        ("Echo & the Bunnymen", "Ocean Rain",
         "Original 1st Pressing", "Punk/Post-Punk", 180.00),
        # ── Additional Punk/Post-Punk ──────────────────────────────────────
        ("The Stooges", "Fun House",
         "Original 1st Pressing", "Punk/Post-Punk", 500.00),
        ("The Stooges", "Raw Power",
         "Original 1st Pressing", "Punk/Post-Punk", 400.00),
        ("Suicide", "Suicide",
         "Original 1st Pressing", "Punk/Post-Punk", 350.00),
        ("Descendents", "Milo Goes to College",
         "Original 1st Pressing", "Punk/Post-Punk", 250.00),
        ("The Fall", "This Nation's Saving Grace",
         "Original 1st Pressing", "Punk/Post-Punk", 200.00),
        ("Sonic Youth", "Goo",
         "Original 1st Pressing", "Punk/Post-Punk", 180.00),
        ("Dinosaur Jr.", "You're Living All Over Me",
         "Original 1st Pressing", "Punk/Post-Punk", 220.00),
        ("IDLES", "Joy as an Act of Resistance",
         "Original 1st Pressing", "Punk/Post-Punk", 80.00),
        ("Fontaines D.C.", "Dogrel",
         "Original 1st Pressing", "Punk/Post-Punk", 65.00),
        ("Turnstile", "Glow On",
         "Colored/Splatter Vinyl", "Punk/Post-Punk", 55.00),
    ]


def _modern_collectible_pressings() -> list[tuple[str, str, str, str, float]]:
    """25 Modern Collectible Pressings — VMP, Mondo, Third Man, RSD, Newbury."""
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
        ("VMP", "Solange - A Seat at the Table (VMP Exclusive)",
         "Numbered Limited", "Modern Collectible", 85.00),
        ("Mac DeMarco", "2",
         "Colored/Splatter Vinyl", "Modern Collectible", 40.00),
        ("Japanese Breakfast", "Jubilee",
         "Colored/Splatter Vinyl", "Modern Collectible", 35.00),
        ("Mondo", "Hereditary (Original Soundtrack)",
         "Numbered Limited", "Modern Collectible", 65.00),
        ("VMP", "Erykah Badu - Mama's Gun (VMP Exclusive)",
         "Numbered Limited", "Modern Collectible", 80.00),
        ("Newbury Comics", "Radiohead - OK Computer (Translucent Blue)",
         "Colored/Splatter Vinyl", "Modern Collectible", 65.00),
        ("RSD 2024", "David Bowie - Aladdin Sane (50th Anniversary Picture Disc)",
         "Picture Disc", "Modern Collectible", 50.00),
        ("VMP", "Miles Davis - Kind of Blue (VMP Audiophile Edition)",
         "Audiophile (MFSL/Half-Speed)", "Modern Collectible", 95.00),
        ("Third Man Records", "The Dead Weather - Dodge and Burn (Vault #26)",
         "Numbered Limited", "Modern Collectible", 85.00),
        ("MFSL", "The Beatles - Abbey Road (Mobile Fidelity Half-Speed)",
         "Audiophile (MFSL/Half-Speed)", "Modern Collectible", 120.00),
    ]


def _soundtracks_scores() -> list[tuple[str, str, str, str, float]]:
    """18 Soundtracks & Scores — collectible film and game soundtracks."""
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
        ("Koji Kondo", "The Legend of Zelda: Ocarina of Time (OST)",
         "Numbered Limited", "Soundtrack", 120.00),
        ("Goblin", "Suspiria (Original Soundtrack)",
         "Original 1st Pressing", "Soundtrack", 450.00),
        ("Joe Hisaishi", "Spirited Away (Soundtrack)",
         "Original 1st Pressing", "Soundtrack", 300.00),
        ("Hans Zimmer", "Dune (Original Motion Picture Soundtrack)",
         "Colored/Splatter Vinyl", "Soundtrack", 55.00),
        ("Disasterpeace", "It Follows (Original Soundtrack)",
         "Colored/Splatter Vinyl", "Soundtrack", 60.00),
        ("Nobuo Uematsu", "Final Fantasy VII Remake (Original Soundtrack)",
         "Box Set", "Soundtrack", 200.00),
        ("John Carpenter", "Halloween (Original Soundtrack)",
         "Colored/Splatter Vinyl", "Soundtrack", 55.00),
        ("Joe Hisaishi", "My Neighbor Totoro (Soundtrack)",
         "Original 1st Pressing", "Soundtrack", 250.00),
    ]


def _country_folk_blues() -> list[tuple[str, str, str, str, float]]:
    """16 Country/Folk/Blues — original pressings and audiophile reissues."""
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
        ("Muddy Waters", "Folk Singer",
         "Original 1st Pressing", "Country/Folk/Blues", 800.00),
        ("Hank Williams", "Moanin' the Blues",
         "Original 1st Pressing", "Country/Folk/Blues", 700.00),
        ("Willie Nelson", "Red Headed Stranger",
         "Original 1st Pressing", "Country/Folk/Blues", 300.00),
        ("B.B. King", "Live at the Regal",
         "Original 1st Pressing", "Country/Folk/Blues", 500.00),
        ("Simon & Garfunkel", "Bridge over Troubled Water",
         "Original 1st Pressing", "Country/Folk/Blues", 200.00),
        ("Leonard Cohen", "Songs of Leonard Cohen",
         "Original 1st Pressing", "Country/Folk/Blues", 350.00),
        ("Leadbelly", "Last Sessions",
         "Original 1st Pressing", "Country/Folk/Blues", 900.00),
        ("Woody Guthrie", "Dust Bowl Ballads",
         "Original 1st Pressing", "Country/Folk/Blues", 800.00),
        ("Gram Parsons", "Grievous Angel",
         "Original 1st Pressing", "Country/Folk/Blues", 450.00),
        ("Howlin' Wolf", "Moanin' in the Moonlight",
         "Original 1st Pressing", "Country/Folk/Blues", 1200.00),
    ]


def _metal_heavy() -> list[tuple[str, str, str, str, float]]:
    """20 Metal/Heavy — original pressings and colored variants of essential metal records."""
    return [
        ("Metallica", "Master of Puppets",
         "Original 1st Pressing", "Punk/Post-Punk", 500.00),
        ("Metallica", "Ride the Lightning",
         "Original 1st Pressing", "Punk/Post-Punk", 600.00),
        ("Iron Maiden", "The Number of the Beast",
         "Original 1st Pressing", "Punk/Post-Punk", 350.00),
        ("Slayer", "Reign in Blood",
         "Original 1st Pressing", "Punk/Post-Punk", 400.00),
        ("Megadeth", "Rust in Peace",
         "Original 1st Pressing", "Punk/Post-Punk", 280.00),
        ("Judas Priest", "Screaming for Vengeance",
         "Original 1st Pressing", "Punk/Post-Punk", 200.00),
        ("Pantera", "Vulgar Display of Power",
         "Original 1st Pressing", "Punk/Post-Punk", 250.00),
        ("Tool", "Lateralus",
         "Original 1st Pressing", "Punk/Post-Punk", 350.00),
        ("Tool", "Aenima",
         "Original 1st Pressing", "Punk/Post-Punk", 500.00),
        ("Opeth", "Blackwater Park",
         "Original 1st Pressing", "Punk/Post-Punk", 200.00),
        ("Mastodon", "Leviathan",
         "Original 1st Pressing", "Punk/Post-Punk", 180.00),
        ("Converge", "Jane Doe",
         "Original 1st Pressing", "Punk/Post-Punk", 300.00),
        ("Neurosis", "Through Silver in Blood",
         "Original 1st Pressing", "Punk/Post-Punk", 250.00),
        ("Electric Wizard", "Dopethrone",
         "Original 1st Pressing", "Punk/Post-Punk", 350.00),
        ("Sleep", "Dopesmoker",
         "Original 1st Pressing", "Punk/Post-Punk", 280.00),
        ("Meshuggah", "Destroy Erase Improve",
         "Original 1st Pressing", "Punk/Post-Punk", 220.00),
        ("Isis", "Oceanic",
         "Original 1st Pressing", "Punk/Post-Punk", 200.00),
        ("Boris", "Pink",
         "Original 1st Pressing", "Punk/Post-Punk", 180.00),
        ("Sunn O)))", "Monoliths & Dimensions",
         "Original 1st Pressing", "Punk/Post-Punk", 150.00),
        ("Gojira", "From Mars to Sirius",
         "Original 1st Pressing", "Punk/Post-Punk", 200.00),
        # ── Additional Metal ───────────────────────────────────────────────
        ("Metallica", "...And Justice for All",
         "Original 1st Pressing", "Punk/Post-Punk", 400.00),
        ("Metallica", "Kill 'Em All",
         "Original 1st Pressing", "Punk/Post-Punk", 500.00),
        ("Iron Maiden", "Powerslave",
         "Original 1st Pressing", "Punk/Post-Punk", 250.00),
        ("Iron Maiden", "Piece of Mind",
         "Original 1st Pressing", "Punk/Post-Punk", 220.00),
        ("Slayer", "South of Heaven",
         "Original 1st Pressing", "Punk/Post-Punk", 300.00),
        ("Sepultura", "Arise",
         "Original 1st Pressing", "Punk/Post-Punk", 200.00),
        ("Death", "Symbolic",
         "Original 1st Pressing", "Punk/Post-Punk", 350.00),
        ("At the Gates", "Slaughter of the Soul",
         "Original 1st Pressing", "Punk/Post-Punk", 280.00),
        ("Emperor", "In the Nightside Eclipse",
         "Original 1st Pressing", "Punk/Post-Punk", 350.00),
        ("Darkthrone", "A Blaze in the Northern Sky",
         "Original 1st Pressing", "Punk/Post-Punk", 400.00),
        ("Burzum", "Filosofem",
         "Original 1st Pressing", "Punk/Post-Punk", 300.00),
        ("Mayhem", "De Mysteriis Dom Sathanas",
         "Original 1st Pressing", "Punk/Post-Punk", 500.00),
    ]


def _audiophile_pressings() -> list[tuple[str, str, str, str, float]]:
    """20 Audiophile Pressings — MFSL, Analogue Productions, half-speed masters, Japanese pressings."""
    return [
        ("MFSL", "Pink Floyd - The Dark Side of the Moon (UHQR)",
         "Audiophile (MFSL/Half-Speed)", "Modern Collectible", 400.00),
        ("MFSL", "Nirvana - Nevermind (MFSL Silver Label)",
         "Audiophile (MFSL/Half-Speed)", "Modern Collectible", 250.00),
        ("MFSL", "Miles Davis - Kind of Blue (One-Step)",
         "Audiophile (MFSL/Half-Speed)", "Modern Collectible", 150.00),
        ("Analogue Productions", "John Coltrane - A Love Supreme (45rpm)",
         "Audiophile (MFSL/Half-Speed)", "Modern Collectible", 180.00),
        ("Analogue Productions", "Art Pepper - Meets the Rhythm Section (45rpm)",
         "Audiophile (MFSL/Half-Speed)", "Modern Collectible", 120.00),
        ("Analogue Productions", "Bill Evans - Waltz for Debby (45rpm)",
         "Audiophile (MFSL/Half-Speed)", "Modern Collectible", 140.00),
        ("Analogue Productions", "Sonny Rollins - Way Out West (45rpm)",
         "Audiophile (MFSL/Half-Speed)", "Modern Collectible", 130.00),
        ("Japanese Pressing", "Led Zeppelin - Led Zeppelin II (Japanese OBI)",
         "Original 1st Pressing", "Classic Rock", 400.00),
        ("Japanese Pressing", "Pink Floyd - Wish You Were Here (Japanese OBI)",
         "Original 1st Pressing", "Classic Rock", 350.00),
        ("Japanese Pressing", "The Beatles - Abbey Road (Japanese Red Vinyl)",
         "Colored/Splatter Vinyl", "Classic Rock", 300.00),
        ("Japanese Pressing", "Miles Davis - Bitches Brew (Japanese OBI)",
         "Original 1st Pressing", "Jazz", 500.00),
        ("Japanese Pressing", "Steely Dan - Aja (Japanese OBI)",
         "Original 1st Pressing", "Classic Rock", 280.00),
        ("Japanese Pressing", "Queen - A Night at the Opera (Japanese OBI)",
         "Original 1st Pressing", "Classic Rock", 250.00),
        ("Half-Speed Master", "Fleetwood Mac - Rumours (Abbey Road Half-Speed)",
         "Audiophile (MFSL/Half-Speed)", "Modern Collectible", 65.00),
        ("Half-Speed Master", "Nirvana - In Utero (Original Master Recording)",
         "Audiophile (MFSL/Half-Speed)", "Modern Collectible", 80.00),
        ("Half-Speed Master", "Radiohead - OK Computer (OKNOTOK UHQ)",
         "Audiophile (MFSL/Half-Speed)", "Modern Collectible", 90.00),
        ("Blue Note", "Art Blakey - Moanin' (Blue Note 75th Anniversary)",
         "Audiophile (MFSL/Half-Speed)", "Jazz", 55.00),
        ("Blue Note", "Wayne Shorter - Speak No Evil (Tone Poet)",
         "Audiophile (MFSL/Half-Speed)", "Jazz", 45.00),
        ("Blue Note", "Herbie Hancock - Maiden Voyage (Tone Poet)",
         "Audiophile (MFSL/Half-Speed)", "Jazz", 45.00),
        ("Blue Note", "Lee Morgan - The Sidewinder (Classic Vinyl)",
         "Audiophile (MFSL/Half-Speed)", "Jazz", 40.00),
        # ── Additional Audiophile ──────────────────────────────────────────
        ("MFSL", "Steely Dan - Aja (One-Step)",
         "Audiophile (MFSL/Half-Speed)", "Modern Collectible", 200.00),
        ("MFSL", "The Beatles - Sgt. Pepper's (One-Step)",
         "Audiophile (MFSL/Half-Speed)", "Modern Collectible", 300.00),
        ("MFSL", "Led Zeppelin - Led Zeppelin II (UHQR)",
         "Audiophile (MFSL/Half-Speed)", "Modern Collectible", 350.00),
        ("Analogue Productions", "Miles Davis - Kind of Blue (45rpm UHQR)",
         "Audiophile (MFSL/Half-Speed)", "Modern Collectible", 200.00),
        ("Analogue Productions", "Dave Brubeck - Time Out (45rpm)",
         "Audiophile (MFSL/Half-Speed)", "Modern Collectible", 130.00),
        ("Analogue Productions", "Nat King Cole - Love Is the Thing (45rpm)",
         "Audiophile (MFSL/Half-Speed)", "Modern Collectible", 110.00),
        ("Japanese Pressing", "King Crimson - In the Court (Japanese OBI)",
         "Original 1st Pressing", "Classic Rock", 400.00),
        ("Japanese Pressing", "Fleetwood Mac - Rumours (Japanese OBI)",
         "Original 1st Pressing", "Classic Rock", 300.00),
        ("Japanese Pressing", "Jimi Hendrix - Electric Ladyland (Japanese OBI)",
         "Original 1st Pressing", "Classic Rock", 450.00),
        ("Japanese Pressing", "Bill Evans - Waltz for Debby (Japanese OBI King)",
         "Original 1st Pressing", "Jazz", 600.00),
        ("Blue Note", "Hank Mobley - Soul Station (Tone Poet)",
         "Audiophile (MFSL/Half-Speed)", "Jazz", 50.00),
        ("Blue Note", "Horace Silver - Song for My Father (Tone Poet)",
         "Audiophile (MFSL/Half-Speed)", "Jazz", 45.00),
        ("Blue Note", "Bobby Hutcherson - Happenings (Tone Poet)",
         "Audiophile (MFSL/Half-Speed)", "Jazz", 50.00),
        ("Blue Note", "Andrew Hill - Point of Departure (Tone Poet)",
         "Audiophile (MFSL/Half-Speed)", "Jazz", 50.00),
    ]


def _rsd_colored_boxsets() -> list[tuple[str, str, str, str, float]]:
    """15 RSD Exclusives, Colored Variants & Box Sets — limited retail editions."""
    return [
        ("RSD 2025", "Pink Floyd - Animals (2025 Remix Picture Disc)",
         "Picture Disc", "Modern Collectible", 45.00),
        ("RSD 2025", "Radiohead - Amnesiac (Scarlet Red Vinyl)",
         "Colored/Splatter Vinyl", "Modern Collectible", 55.00),
        ("RSD 2024", "Wu-Tang Clan - 36 Chambers (Gold Vinyl)",
         "Colored/Splatter Vinyl", "Modern Collectible", 50.00),
        ("RSD 2024", "The Cure - Wish (Picture Disc)",
         "Picture Disc", "Modern Collectible", 40.00),
        ("RSD 2023", "Daft Punk - Homework (Orange Vinyl)",
         "Colored/Splatter Vinyl", "Modern Collectible", 55.00),
        ("The Beatles", "The Beatles in Mono (Box Set)",
         "Box Set", "Classic Rock", 450.00),
        ("The Rolling Stones", "Exile on Main St. (Super Deluxe Box Set)",
         "Box Set", "Classic Rock", 200.00),
        ("Bob Dylan", "The Bootleg Series Vol. 1-3 (Box Set)",
         "Box Set", "Country/Folk/Blues", 280.00),
        ("Miles Davis", "The Complete Bitches Brew Sessions (Box Set)",
         "Box Set", "Jazz", 350.00),
        ("Radiohead", "OK Computer OKNOTOK (Blue Vinyl Box Set)",
         "Box Set", "Indie/Alternative", 180.00),
        ("Kendrick Lamar", "DAMN. (Autographed Red Vinyl)",
         "Colored/Splatter Vinyl", "Hip-Hop", 150.00),
        ("Taylor Swift", "Midnights (Lavender Marbled Vinyl)",
         "Colored/Splatter Vinyl", "Modern Collectible", 45.00),
        ("Billie Eilish", "When We All Fall Asleep... (Glow-in-the-Dark Vinyl)",
         "Colored/Splatter Vinyl", "Modern Collectible", 55.00),
        ("Olivia Rodrigo", "SOUR (Blue/Pink Split Vinyl)",
         "Colored/Splatter Vinyl", "Modern Collectible", 40.00),
        ("Lana Del Rey", "Norman Fucking Rockwell! (Lime Green Vinyl)",
         "Colored/Splatter Vinyl", "Modern Collectible", 65.00),
        ("Arctic Monkeys", "AM (Gold Vinyl RSD)",
         "RSD Exclusive", "Modern Collectible", 55.00),
        ("Tame Impala", "Lonerism (10th Anniversary Splatter)",
         "Colored/Splatter Vinyl", "Modern Collectible", 70.00),
    ]


def _modern_pop_world_classical() -> list[tuple[str, str, str, str, float]]:
    """42 Modern Pop, World Music & Classical — collectible pressings."""
    return [
        # ── Modern Pop ─────────────────────────────────────────────────────
        ("Taylor Swift", "Folklore (In the Trees Edition)",
         "Colored/Splatter Vinyl", "Modern Collectible", 55.00),
        ("Taylor Swift", "1989 (Taylor's Version Rose Garden Pink)",
         "Colored/Splatter Vinyl", "Modern Collectible", 45.00),
        ("Taylor Swift", "Red (Taylor's Version)",
         "Colored/Splatter Vinyl", "Modern Collectible", 50.00),
        ("Taylor Swift", "Evermore (Green Vinyl)",
         "Colored/Splatter Vinyl", "Modern Collectible", 45.00),
        ("Adele", "21",
         "Original 1st Pressing", "Modern Collectible", 80.00),
        ("Adele", "30",
         "Colored/Splatter Vinyl", "Modern Collectible", 40.00),
        ("Harry Styles", "Harry's House (Sea Glass Green)",
         "Colored/Splatter Vinyl", "Modern Collectible", 40.00),
        ("Harry Styles", "Fine Line (Black & White Splatter)",
         "Colored/Splatter Vinyl", "Modern Collectible", 55.00),
        ("Dua Lipa", "Future Nostalgia (Pink Vinyl)",
         "Colored/Splatter Vinyl", "Modern Collectible", 35.00),
        ("The Weeknd", "After Hours (Holographic Vinyl)",
         "Colored/Splatter Vinyl", "Modern Collectible", 50.00),
        ("The Weeknd", "Dawn FM (Collector's Edition)",
         "Numbered Limited", "Modern Collectible", 60.00),
        ("SZA", "SOS (Lenticular Cover)",
         "Colored/Splatter Vinyl", "Modern Collectible", 45.00),
        ("Beyonce", "Lemonade (Yellow Vinyl)",
         "Colored/Splatter Vinyl", "Modern Collectible", 70.00),
        ("Beyonce", "Renaissance",
         "Colored/Splatter Vinyl", "Modern Collectible", 45.00),
        ("Bad Bunny", "Un Verano Sin Ti",
         "Original 1st Pressing", "Modern Collectible", 50.00),
        ("Rosalia", "Motomami",
         "Colored/Splatter Vinyl", "Modern Collectible", 40.00),
        ("Charli XCX", "Brat (Green Vinyl)",
         "Colored/Splatter Vinyl", "Modern Collectible", 35.00),
        ("Sabrina Carpenter", "Short n' Sweet (Pink Vinyl)",
         "Colored/Splatter Vinyl", "Modern Collectible", 35.00),
        ("Chappell Roan", "The Rise and Fall of a Midwest Princess",
         "Colored/Splatter Vinyl", "Modern Collectible", 40.00),
        ("Billie Eilish", "Hit Me Hard and Soft (Sea Blue)",
         "Colored/Splatter Vinyl", "Modern Collectible", 40.00),
        # ── World Music ────────────────────────────────────────────────────
        ("Fela Kuti", "Zombie",
         "Original 1st Pressing", "Soul/Funk", 450.00),
        ("Fela Kuti", "Expensive Shit",
         "Original 1st Pressing", "Soul/Funk", 350.00),
        ("Ali Farka Toure", "The River",
         "Original 1st Pressing", "Soul/Funk", 180.00),
        ("Buena Vista Social Club", "Buena Vista Social Club",
         "Original 1st Pressing", "Soul/Funk", 200.00),
        ("Tinariwen", "Amassakoul",
         "Original 1st Pressing", "Soul/Funk", 120.00),
        ("Youssou N'Dour", "The Guide (Wommat)",
         "Original 1st Pressing", "Soul/Funk", 100.00),
        ("Mulatu Astatke", "Mulatu of Ethiopia",
         "Original 1st Pressing", "Soul/Funk", 500.00),
        ("Os Mutantes", "Os Mutantes",
         "Original 1st Pressing", "Soul/Funk", 800.00),
        ("Caetano Veloso", "Transa",
         "Original 1st Pressing", "Soul/Funk", 350.00),
        ("Ravi Shankar", "Three Ragas",
         "Original 1st Pressing", "Soul/Funk", 200.00),
        # ── Classical ──────────────────────────────────────────────────────
        ("Glenn Gould", "Bach: Goldberg Variations (1955)",
         "Original 1st Pressing", "Soundtrack", 600.00),
        ("Herbert von Karajan", "Beethoven: Symphony No. 9 (DG)",
         "Original 1st Pressing", "Soundtrack", 200.00),
        ("Leonard Bernstein", "Mahler: Symphony No. 2 (Columbia)",
         "Original 1st Pressing", "Soundtrack", 250.00),
        ("Karl Bohm", "Mozart: Requiem (DG)",
         "Original 1st Pressing", "Soundtrack", 180.00),
        ("Vladimir Horowitz", "Horowitz at Carnegie Hall (Columbia)",
         "Original 1st Pressing", "Soundtrack", 300.00),
        ("Georg Solti", "Wagner: Der Ring des Nibelungen (Decca)",
         "Box Set", "Soundtrack", 800.00),
        ("Jacqueline du Pre", "Elgar: Cello Concerto (EMI)",
         "Original 1st Pressing", "Soundtrack", 350.00),
        ("Fritz Reiner", "Bartok: Concerto for Orchestra (RCA Living Stereo)",
         "Original 1st Pressing", "Soundtrack", 400.00),
        ("Pierre Boulez", "Stravinsky: The Rite of Spring (Columbia)",
         "Original 1st Pressing", "Soundtrack", 250.00),
        ("Sviatoslav Richter", "Mussorgsky: Pictures at an Exhibition (Philips)",
         "Original 1st Pressing", "Soundtrack", 280.00),
        ("Carlos Kleiber", "Beethoven: Symphony No. 5 (DG)",
         "Original 1st Pressing", "Soundtrack", 200.00),
        ("Yo-Yo Ma", "Bach: Unaccompanied Cello Suites (CBS)",
         "Original 1st Pressing", "Soundtrack", 150.00),
    ]


def _vmp_rsd2024_limited_color() -> list[tuple[str, str, str, str, float]]:
    """50 VMP exclusives, RSD 2024 releases, limited color pressings, vault packages & artist variants."""
    return [
        # ── Vinyl Me Please (VMP) Exclusives ──
        ("Erykah Badu", "Baduizm (VMP Essentials)",
         "Colored/Splatter Vinyl", "Hip-Hop", 85.00),
        ("Amy Winehouse", "Back to Black (VMP Essentials)",
         "Colored/Splatter Vinyl", "Soul/Funk", 90.00),
        ("Solange", "A Seat at the Table (VMP Essentials)",
         "Colored/Splatter Vinyl", "Hip-Hop", 75.00),
        ("Anderson .Paak", "Malibu (VMP Essentials)",
         "Colored/Splatter Vinyl", "Hip-Hop", 80.00),
        ("Aretha Franklin", "I Never Loved a Man (VMP Classics)",
         "Audiophile (MFSL/Half-Speed)", "Soul/Funk", 65.00),
        ("Bill Withers", "Still Bill (VMP Classics)",
         "Audiophile (MFSL/Half-Speed)", "Soul/Funk", 60.00),
        ("Wu-Tang Clan", "Enter the Wu-Tang (VMP Hip-Hop)",
         "Colored/Splatter Vinyl", "Hip-Hop", 95.00),
        ("Outkast", "Aquemini (VMP Hip-Hop)",
         "Colored/Splatter Vinyl", "Hip-Hop", 100.00),
        ("Thundercat", "Drunk (VMP Essentials)",
         "Colored/Splatter Vinyl", "Hip-Hop", 70.00),
        ("Fiona Apple", "Fetch the Bolt Cutters (VMP Essentials)",
         "Colored/Splatter Vinyl", "Indie/Alternative", 65.00),

        # ── Record Store Day 2024 Exclusives ──
        ("Nirvana", "MTV Unplugged in New York (RSD 2024 Picture Disc)",
         "Picture Disc", "Indie/Alternative", 55.00),
        ("Pearl Jam", "No Code (RSD 2024 Clear Vinyl)",
         "RSD Exclusive", "Classic Rock", 50.00),
        ("David Bowie", "Aladdin Sane 50th Anniversary (RSD 2024 Red Vinyl)",
         "RSD Exclusive", "Classic Rock", 60.00),
        ("Gorillaz", "Demon Days (RSD 2024 Red Vinyl)",
         "RSD Exclusive", "Indie/Alternative", 65.00),
        ("The Cure", "Disintegration (RSD 2024 Marble Vinyl)",
         "RSD Exclusive", "Indie/Alternative", 70.00),
        ("Fleetwood Mac", "Tango in the Night (RSD 2024 Green Vinyl)",
         "RSD Exclusive", "Classic Rock", 55.00),
        ("Miles Davis", "In a Silent Way (RSD 2024 White Vinyl)",
         "RSD Exclusive", "Jazz", 50.00),
        ("Prince", "Purple Rain Deluxe (RSD 2024 Purple/Gold Splatter)",
         "RSD Exclusive", "Soul/Funk", 75.00),
        ("Sade", "Diamond Life (RSD 2024 Crystal Clear)",
         "RSD Exclusive", "Soul/Funk", 45.00),
        ("Talking Heads", "Stop Making Sense (RSD 2024 Live)",
         "RSD Exclusive", "Indie/Alternative", 55.00),

        # ── Jack White Vault Packages ──
        ("Jack White", "Vault Package #48 (Live at Cain's Ballroom)",
         "Numbered Limited", "Indie/Alternative", 120.00),
        ("Jack White", "Vault Package #50 (Boarding House Reach Sessions)",
         "Numbered Limited", "Indie/Alternative", 130.00),
        ("The White Stripes", "Vault Package #45 (Peel Sessions)",
         "Numbered Limited", "Indie/Alternative", 150.00),
        ("The Raconteurs", "Vault Package #42 (Live at Third Man)",
         "Numbered Limited", "Indie/Alternative", 110.00),
        ("Jack White", "No Name (Vault Tri-Color Edition)",
         "Colored/Splatter Vinyl", "Indie/Alternative", 95.00),

        # ── Radiohead Special Editions ──
        ("Radiohead", "In Rainbows (Deluxe Box Set 2LP+2CD)",
         "Box Set", "Indie/Alternative", 180.00),
        ("Radiohead", "Kid A Mnesia (Scarry Book Edition Red Vinyl)",
         "Colored/Splatter Vinyl", "Indie/Alternative", 85.00),
        ("Radiohead", "OK Computer OKNOTOK (Blue Opaque Vinyl)",
         "Colored/Splatter Vinyl", "Indie/Alternative", 70.00),
        ("Radiohead", "A Moon Shaped Pool (White Vinyl Deluxe)",
         "Colored/Splatter Vinyl", "Indie/Alternative", 65.00),

        # ── Tyler, the Creator — IGOR Variants ──
        ("Tyler, the Creator", "IGOR (Mint Green Vinyl)",
         "Colored/Splatter Vinyl", "Hip-Hop", 90.00),
        ("Tyler, the Creator", "IGOR (Pink Vinyl Limited)",
         "Colored/Splatter Vinyl", "Hip-Hop", 120.00),
        ("Tyler, the Creator", "Call Me If You Get Lost (Estate Sale Deluxe Vinyl)",
         "Numbered Limited", "Hip-Hop", 85.00),
        ("Tyler, the Creator", "Flower Boy (Bee Yellow Vinyl)",
         "Colored/Splatter Vinyl", "Hip-Hop", 95.00),
        ("Tyler, the Creator", "Chromakopia (Forest Green Vinyl)",
         "Colored/Splatter Vinyl", "Hip-Hop", 55.00),

        # ── Frank Ocean Bootlegs / Limited ──
        ("Frank Ocean", "Blonde (Black Friday Clear Vinyl)",
         "Colored/Splatter Vinyl", "Hip-Hop", 350.00),
        ("Frank Ocean", "Blonde (Bootleg Amber Vinyl)",
         "Colored/Splatter Vinyl", "Hip-Hop", 80.00),
        ("Frank Ocean", "Endless (Bootleg Purple Vinyl)",
         "Colored/Splatter Vinyl", "Hip-Hop", 75.00),
        ("Frank Ocean", "Channel Orange (Bootleg Orange Splatter)",
         "Colored/Splatter Vinyl", "Hip-Hop", 70.00),
        ("Frank Ocean", "Nostalgia, Ultra (Bootleg Pink Vinyl)",
         "Colored/Splatter Vinyl", "Hip-Hop", 65.00),

        # ── Khruangbin Colored Vinyl ──
        ("Khruangbin", "Con Todo El Mundo (White Vinyl)",
         "Colored/Splatter Vinyl", "Indie/Alternative", 55.00),
        ("Khruangbin", "Mordechai (Pink Translucent Vinyl)",
         "Colored/Splatter Vinyl", "Indie/Alternative", 50.00),
        ("Khruangbin", "A La Sala (Gold Metallic Vinyl)",
         "Colored/Splatter Vinyl", "Indie/Alternative", 45.00),
        ("Khruangbin & Leon Bridges", "Texas Sun (Orange Translucent EP)",
         "Colored/Splatter Vinyl", "Indie/Alternative", 40.00),
        ("Khruangbin", "Hasta El Cielo (Dub Version Green Vinyl)",
         "Colored/Splatter Vinyl", "Indie/Alternative", 60.00),

        # ── Additional Limited Color Pressings ──
        ("Billie Eilish", "Hit Me Hard and Soft (Sea Blue Vinyl)",
         "Colored/Splatter Vinyl", "Modern Collectible", 45.00),
        ("Lana Del Rey", "Did You Know That There's a Tunnel Under Ocean Blvd (Alt Cover Green Vinyl)",
         "Colored/Splatter Vinyl", "Modern Collectible", 50.00),
        ("Olivia Rodrigo", "GUTS (Spilled Purple/Red Splatter)",
         "Colored/Splatter Vinyl", "Modern Collectible", 40.00),
        ("Taylor Swift", "1989 (Taylor's Version) (Tangerine Vinyl)",
         "Colored/Splatter Vinyl", "Modern Collectible", 55.00),
        ("Beyonce", "Renaissance (Club Edition Silver Vinyl)",
         "Colored/Splatter Vinyl", "Hip-Hop", 65.00),
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
    ("Metal/Heavy", _metal_heavy),
    ("Audiophile Pressings", _audiophile_pressings),
    ("RSD, Colored & Box Sets", _rsd_colored_boxsets),
    ("Modern Pop, World & Classical", _modern_pop_world_classical),
    ("VMP, RSD 2024 & Limited Color Pressings", _vmp_rsd2024_limited_color),
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
