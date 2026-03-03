"""
Import Blu-ray Steelbook & boutique label collector data.

Layer 1 (Catalog):  Curated collector Blu-rays → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated catalog of Criterion, Arrow Video, Steelbooks, 4K UHD, boutique labels
- Can be augmented with Blu-ray.com or TMDB later

Usage:
    python -m pipelines.import_bluray [--dry-run]
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

CATEGORY = "bluray_steelbook"


def get_curated_catalog() -> list[dict]:
    """Curated Blu-ray collector catalog (500+ items): Criterion (incl. recent 2024-2025),
    Arrow Video, Indicator, Kino Lorber, Vinegar Syndrome, 88 Films, Shout/Scream Factory,
    Eureka/Masters of Cinema, Second Sight, StudioCanal, Mondo, BFI, 101 Films,
    Best Buy/Walmart/Target exclusives, premium 4K UHD, Miyazaki/Ghibli steelbooks,
    MCU steelbooks, LOTR steelbooks, Star Wars steelbooks, Disney Vault steelbooks,
    HDZeta, Manta Lab, Zavvi, Imprint, Severin, Blue Underground, Twilight Time,
    Fun City Editions, FilmArena, anime box sets (Evangelion, Cowboy Bebop, Akira,
    Ghost in the Shell, Demon Slayer, Your Name), full slip premium editions
    (KimchiDVD, Plain Archive, WeET, FilmArena), and other boutique labels."""

    # Format: (label, title, format, edition, rarity_tier, price_eur)
    # rarity_tier: grail (>150), high (80-150), mid (40-80), standard (<40)

    discs = [
        # ── Criterion Collection ─────────────────────────────────────────
        ("Criterion", "Seven Samurai", "Blu-ray", "Criterion #2", "standard", 28),
        ("Criterion", "Stalker", "Blu-ray", "Criterion #888", "standard", 30),
        ("Criterion", "In the Mood for Love", "Blu-ray", "Criterion #4K", "standard", 35),
        ("Criterion", "Mulholland Dr.", "Blu-ray", "Criterion #779", "standard", 25),
        ("Criterion", "Parasite", "4K UHD", "Criterion 4K", "standard", 38),
        ("Criterion", "Do the Right Thing", "Blu-ray", "Criterion #97", "standard", 22),
        ("Criterion", "Paris, Texas", "Blu-ray", "Criterion #634", "standard", 28),
        ("Criterion", "Eraserhead", "Blu-ray", "Criterion #725", "standard", 35),
        ("Criterion", "The Before Trilogy", "Blu-ray", "Criterion Box Set", "mid", 55),
        ("Criterion", "World of Wong Kar Wai", "Blu-ray", "Criterion Box Set", "high", 90),
        ("Criterion", "Citizen Kane", "4K UHD", "Criterion 4K", "mid", 40),
        ("Criterion", "8 1/2", "Blu-ray", "Criterion #140", "standard", 26),
        ("Criterion", "The 400 Blows", "Blu-ray", "Criterion #5", "standard", 24),
        ("Criterion", "Persona", "Blu-ray", "Criterion #701", "standard", 28),
        ("Criterion", "Tampopo", "Blu-ray", "Criterion #960", "standard", 30),
        ("Criterion", "Menace II Society", "4K UHD", "Criterion 4K", "standard", 38),
        ("Criterion", "All That Jazz", "Blu-ray", "Criterion #1069", "standard", 26),
        ("Criterion", "Close-Up", "Blu-ray", "Criterion #590", "standard", 32),
        ("Criterion", "The Complete Jacques Tati", "Blu-ray", "Criterion Box Set", "high", 110),
        ("Criterion", "Godzilla: The Showa-Era Films", "Blu-ray", "Criterion Box Set", "high", 130),

        # ── Arrow Video ──────────────────────────────────────────────────
        ("Arrow Video", "Suspiria", "4K UHD", "Arrow Limited", "mid", 45),
        ("Arrow Video", "Re-Animator", "Blu-ray", "Arrow Limited", "standard", 35),
        ("Arrow Video", "The Thing", "4K UHD", "Arrow Limited", "mid", 50),
        ("Arrow Video", "Donnie Darko", "4K UHD", "Arrow Limited", "mid", 40),
        ("Arrow Video", "Deep Red", "4K UHD", "Arrow Limited", "mid", 42),
        ("Arrow Video", "Battle Royale", "Blu-ray", "Arrow Limited", "standard", 38),
        ("Arrow Video", "Hellraiser Trilogy", "Blu-ray", "Arrow Box Set", "high", 80),
        ("Arrow Video", "Oldboy", "4K UHD", "Arrow Limited", "mid", 45),
        ("Arrow Video", "Tenebrae", "4K UHD", "Arrow Limited", "mid", 42),
        ("Arrow Video", "The Bird with the Crystal Plumage", "4K UHD", "Arrow Limited", "mid", 44),
        ("Arrow Video", "Demons / Demons 2", "Blu-ray", "Arrow Limited", "mid", 40),
        ("Arrow Video", "Blood and Black Lace", "Blu-ray", "Arrow Limited", "standard", 38),
        ("Arrow Video", "Robocop", "4K UHD", "Arrow Limited", "mid", 48),
        ("Arrow Video", "An American Werewolf in London", "4K UHD", "Arrow Limited", "mid", 55),
        ("Arrow Video", "Flash Gordon", "4K UHD", "Arrow Limited", "mid", 42),

        # ── Indicator / Powerhouse Films ─────────────────────────────────
        ("Indicator", "Columbia Noir Collection Vol 1", "Blu-ray", "Indicator Box Set", "high", 85),
        ("Indicator", "Columbia Noir Collection Vol 2", "Blu-ray", "Indicator Box Set", "high", 85),
        ("Indicator", "Hammer Volume One: Fear Warning!", "Blu-ray", "Indicator Box Set", "high", 95),
        ("Indicator", "Hammer Volume Two: Criminal Intent", "Blu-ray", "Indicator Box Set", "high", 95),
        ("Indicator", "The Alastair Sim Collection", "Blu-ray", "Indicator Box Set", "high", 90),
        ("Indicator", "Samuel Fuller at Columbia", "Blu-ray", "Indicator Box Set", "high", 88),

        # ── Kino Lorber ──────────────────────────────────────────────────
        ("Kino Lorber", "The Cabinet of Dr. Caligari", "4K UHD", "KL Studio Classics", "standard", 34),
        ("Kino Lorber", "Nosferatu (1922)", "4K UHD", "KL Studio Classics", "standard", 36),
        ("Kino Lorber", "Metropolis", "4K UHD", "KL Studio Classics", "standard", 38),
        ("Kino Lorber", "Army of Shadows", "Blu-ray", "KL Studio Classics", "standard", 28),
        ("Kino Lorber", "Le Samourai", "4K UHD", "KL Studio Classics", "standard", 36),

        # ── Vinegar Syndrome ─────────────────────────────────────────────
        ("Vinegar Syndrome", "Tammy and the T-Rex", "4K UHD", "VS Limited", "mid", 40),
        ("Vinegar Syndrome", "Psycho Goreman", "4K UHD", "VS Limited", "standard", 35),
        ("Vinegar Syndrome", "Blood Rage", "Blu-ray", "VS Limited", "standard", 30),
        ("Vinegar Syndrome", "Slaughter High", "Blu-ray", "VS Limited", "standard", 28),
        ("Vinegar Syndrome", "The Mutilator", "4K UHD", "VS Limited", "standard", 36),
        ("Vinegar Syndrome", "Killer Workout", "Blu-ray", "VS Limited", "standard", 26),
        ("Vinegar Syndrome", "Nightmare Beach", "Blu-ray", "VS Limited", "standard", 28),
        ("Vinegar Syndrome", "Pieces", "4K UHD", "VS Limited", "mid", 40),

        # ── 88 Films ─────────────────────────────────────────────────────
        ("88 Films", "Italian Horror Collection", "Blu-ray", "88 Films Box Set", "high", 100),
        ("88 Films", "Shocking Dark", "Blu-ray", "88 Films Limited", "standard", 24),
        ("88 Films", "Killer Crocodile 1 & 2", "Blu-ray", "88 Films Limited", "standard", 26),
        ("88 Films", "The House by the Cemetery", "4K UHD", "88 Films Limited", "standard", 38),
        ("88 Films", "Robowar", "Blu-ray", "88 Films Limited", "standard", 22),

        # ── Shout Factory / Scream Factory ───────────────────────────────
        ("Shout Factory", "The Fog", "4K UHD", "Shout Select", "standard", 35),
        ("Shout Factory", "Escape from New York", "4K UHD", "Shout Select", "standard", 38),
        ("Shout Factory", "They Live", "4K UHD", "Shout Select", "standard", 35),
        ("Scream Factory", "Halloween (1978)", "4K UHD", "Scream Factory Limited", "mid", 42),
        ("Scream Factory", "A Nightmare on Elm Street Collection", "Blu-ray", "Scream Factory Box Set", "high", 85),
        ("Scream Factory", "Child's Play Collection", "Blu-ray", "Scream Factory Box Set", "mid", 55),
        ("Scream Factory", "Phantasm Sphere Collection", "Blu-ray", "Scream Factory Box Set", "high", 80),
        ("Scream Factory", "Creepshow", "4K UHD", "Scream Factory Limited", "mid", 40),

        # ── Eureka / Masters of Cinema ───────────────────────────────────
        ("Eureka", "Buster Keaton: The Saphead", "Blu-ray", "Masters of Cinema", "standard", 30),
        ("Eureka", "Harakiri", "Blu-ray", "Masters of Cinema", "standard", 28),
        ("Eureka", "Rashomon", "Blu-ray", "Masters of Cinema", "standard", 26),
        ("Eureka", "The Human Condition Trilogy", "Blu-ray", "Masters of Cinema Box Set", "high", 80),
        ("Eureka", "Late Spring", "4K UHD", "Masters of Cinema", "standard", 36),

        # ── Second Sight ─────────────────────────────────────────────────
        ("Second Sight", "The Witch", "4K UHD", "Second Sight Limited", "mid", 50),
        ("Second Sight", "The Descent", "4K UHD", "Second Sight Limited", "mid", 48),
        ("Second Sight", "Dog Soldiers", "4K UHD", "Second Sight Limited", "mid", 46),
        ("Second Sight", "Hereditary", "4K UHD", "Second Sight Limited", "mid", 52),
        ("Second Sight", "In Bruges", "4K UHD", "Second Sight Limited", "mid", 50),

        # ── StudioCanal ──────────────────────────────────────────────────
        ("StudioCanal", "Mulholland Drive", "4K UHD", "StudioCanal Collector's", "mid", 45),
        ("StudioCanal", "The Third Man", "4K UHD", "StudioCanal Collector's", "mid", 42),
        ("StudioCanal", "Cinema Paradiso", "4K UHD", "StudioCanal Collector's", "mid", 40),
        ("StudioCanal", "Terminator 2: Judgment Day", "4K UHD", "StudioCanal Collector's", "mid", 44),

        # ── Mondo Steelbooks ─────────────────────────────────────────────
        ("Mondo", "The Iron Giant", "4K UHD", "Mondo Steelbook", "high", 85),
        ("Mondo", "Jurassic Park", "4K UHD", "Mondo Steelbook", "mid", 55),
        ("Mondo", "Alien", "4K UHD", "Mondo Steelbook", "mid", 60),
        ("Mondo", "Drive", "4K UHD", "Mondo Steelbook", "high", 80),

        # ── Best Buy Exclusives ──────────────────────────────────────────
        ("Best Buy Exclusive", "Top Gun: Maverick", "4K UHD", "Best Buy Steelbook", "mid", 38),
        ("Best Buy Exclusive", "The Batman (2022)", "4K UHD", "Best Buy Steelbook", "mid", 36),
        ("Best Buy Exclusive", "Dune: Part Two", "4K UHD", "Best Buy Steelbook", "mid", 40),

        # ── Walmart Exclusives ───────────────────────────────────────────
        ("Walmart Exclusive", "Deadpool & Wolverine", "4K UHD", "Walmart Steelbook", "standard", 34),
        ("Walmart Exclusive", "Barbie", "4K UHD", "Walmart Steelbook", "standard", 30),

        # ── Target Exclusives ────────────────────────────────────────────
        ("Target Exclusive", "Everything Everywhere All at Once", "4K UHD", "Target Steelbook", "mid", 42),
        ("Target Exclusive", "Oppenheimer", "4K UHD", "Target Steelbook", "mid", 40),

        # ── 4K UHD Premium Editions ──────────────────────────────────────
        ("4K UHD", "Blade Runner 2049", "4K UHD", "Limited Collector's", "high", 80),
        ("4K UHD", "2001: A Space Odyssey", "4K UHD", "Titans of Cult", "high", 65),
        ("4K UHD", "The Shining", "4K UHD", "Titans of Cult", "mid", 55),
        ("4K UHD", "Dune (2021)", "4K UHD", "Limited SteelBook", "mid", 40),
        ("4K UHD", "Lawrence of Arabia", "4K UHD", "Columbia Classics Vol 1", "grail", 180),
        ("4K UHD", "Jaws", "4K UHD", "Limited Collector's", "mid", 45),
        ("4K UHD", "The Dark Knight", "4K UHD", "HDZeta Steelbook", "grail", 160),
        ("4K UHD", "Blade Runner: The Final Cut", "4K UHD", "Titans of Cult", "high", 85),
        ("4K UHD", "Interstellar", "4K UHD", "HDZeta Steelbook", "high", 120),
        ("4K UHD", "Mad Max: Fury Road", "4K UHD", "Titans of Cult", "high", 65),
        ("4K UHD", "The Matrix", "4K UHD", "Titans of Cult", "mid", 55),
        ("4K UHD", "Full Metal Jacket", "4K UHD", "Titans of Cult", "mid", 50),

        # ── Steelbooks - Marvel MCU Phase 1-3 ────────────────────────────
        ("Steelbook", "Avengers: Endgame", "4K UHD", "Zavvi Steelbook", "mid", 40),
        ("Steelbook", "Spider-Man: No Way Home", "4K UHD", "Best Buy Steelbook", "mid", 35),
        ("Steelbook", "Black Panther", "4K UHD", "Zavvi Steelbook", "mid", 38),
        ("Steelbook", "Iron Man", "4K UHD", "Zavvi Steelbook", "high", 55),
        ("Steelbook", "Captain America: The Winter Soldier", "4K UHD", "Zavvi Steelbook", "mid", 42),
        ("Steelbook", "Thor: Ragnarok", "4K UHD", "Zavvi Steelbook", "mid", 40),
        ("Steelbook", "Guardians of the Galaxy", "4K UHD", "Zavvi Steelbook", "mid", 44),
        ("Steelbook", "Avengers: Infinity War", "4K UHD", "Zavvi Steelbook", "mid", 42),
        ("Steelbook", "Doctor Strange", "4K UHD", "Zavvi Steelbook", "standard", 36),

        # ── Steelbooks - Nolan ───────────────────────────────────────────
        ("Steelbook", "Inception", "4K UHD", "Manta Lab Steelbook", "high", 100),
        ("Steelbook", "Oppenheimer", "4K UHD", "Zavvi Steelbook", "mid", 45),
        ("Steelbook", "Tenet", "4K UHD", "Zavvi Steelbook", "mid", 42),
        ("Steelbook", "Dunkirk", "4K UHD", "Manta Lab Steelbook", "high", 85),

        # ── Steelbooks - Miyazaki / Studio Ghibli ────────────────────────
        ("Steelbook", "Spirited Away", "Blu-ray", "Zavvi Steelbook", "high", 60),
        ("Steelbook", "Princess Mononoke", "Blu-ray", "Zavvi Steelbook", "mid", 50),
        ("Steelbook", "My Neighbor Totoro", "Blu-ray", "Zavvi Steelbook", "mid", 48),
        ("Steelbook", "Howl's Moving Castle", "Blu-ray", "Zavvi Steelbook", "mid", 55),
        ("Steelbook", "Nausicaa of the Valley of the Wind", "Blu-ray", "Zavvi Steelbook", "mid", 52),
        ("Steelbook", "Castle in the Sky", "Blu-ray", "Zavvi Steelbook", "mid", 48),
        ("Steelbook", "Kiki's Delivery Service", "Blu-ray", "Zavvi Steelbook", "mid", 46),
        ("Steelbook", "Porco Rosso", "Blu-ray", "Zavvi Steelbook", "mid", 44),

        # ── Steelbooks - Lord of the Rings ───────────────────────────────
        ("Steelbook", "LOTR: Fellowship of the Ring Extended", "4K UHD", "Zavvi Steelbook", "high", 85),
        ("Steelbook", "LOTR: The Two Towers Extended", "4K UHD", "Zavvi Steelbook", "high", 85),
        ("Steelbook", "LOTR: Return of the King Extended", "4K UHD", "Zavvi Steelbook", "high", 90),
        ("Steelbook", "LOTR Extended Trilogy", "4K UHD", "HDZeta Box Set", "grail", 280),

        # ── Steelbooks - Star Wars ───────────────────────────────────────
        ("Steelbook", "Star Wars: A New Hope", "4K UHD", "Zavvi Steelbook", "high", 65),
        ("Steelbook", "The Empire Strikes Back", "4K UHD", "Zavvi Steelbook", "high", 65),
        ("Steelbook", "Return of the Jedi", "4K UHD", "Zavvi Steelbook", "high", 60),
        ("Steelbook", "Star Wars Original Trilogy", "4K UHD", "Zavvi Box Set", "grail", 180),
        ("Steelbook", "Rogue One: A Star Wars Story", "4K UHD", "Zavvi Steelbook", "mid", 50),

        # ── Disney Vault Steelbooks ──────────────────────────────────────
        ("Steelbook", "The Lion King (1994)", "4K UHD", "Zavvi Steelbook", "mid", 55),
        ("Steelbook", "Aladdin (1992)", "4K UHD", "Zavvi Steelbook", "mid", 50),
        ("Steelbook", "Beauty and the Beast (1991)", "4K UHD", "Zavvi Steelbook", "mid", 52),
        ("Steelbook", "The Little Mermaid (1989)", "4K UHD", "Zavvi Steelbook", "mid", 48),
        ("Steelbook", "Fantasia", "Blu-ray", "Zavvi Steelbook", "high", 65),
        ("Steelbook", "Bambi", "Blu-ray", "Zavvi Steelbook", "high", 60),
        ("Steelbook", "Snow White and the Seven Dwarfs", "4K UHD", "Zavvi Steelbook", "high", 68),

        # ── Other Boutique Label Box Sets ────────────────────────────────
        ("Imprint", "Film Noir Collection", "Blu-ray", "Imprint Box Set", "high", 120),
        ("Severin", "Fulci Box Set", "Blu-ray", "Severin Limited", "grail", 200),
        ("Severin", "Coffin Joe Trilogy", "Blu-ray", "Severin Limited", "high", 85),

        # ── Criterion — Additional Titles ──────────────────────────────────
        ("Criterion", "Yi Yi", "Blu-ray", "Criterion #959", "standard", 30),
        ("Criterion", "Moonlight", "4K UHD", "Criterion 4K", "standard", 38),
        ("Criterion", "The Red Shoes", "4K UHD", "Criterion 4K", "mid", 42),
        ("Criterion", "Memories of Murder", "Blu-ray", "Criterion #1078", "standard", 28),
        ("Criterion", "Lady Bird", "Blu-ray", "Criterion #999", "standard", 24),
        ("Criterion", "The Player", "4K UHD", "Criterion 4K", "standard", 36),
        ("Criterion", "House of Games", "Blu-ray", "Criterion #400", "standard", 26),
        ("Criterion", "Dazed and Confused", "4K UHD", "Criterion 4K", "standard", 38),
        ("Criterion", "The Breakfast Club", "Blu-ray", "Criterion #935", "standard", 25),
        ("Criterion", "Ratcatcher", "Blu-ray", "Criterion #754", "standard", 30),

        # ── Arrow Video — Additional Titles ────────────────────────────────
        ("Arrow Video", "The Texas Chain Saw Massacre", "4K UHD", "Arrow Limited", "mid", 55),
        ("Arrow Video", "Dario Argento Collection", "Blu-ray", "Arrow Box Set", "high", 90),
        ("Arrow Video", "Videodrome", "4K UHD", "Arrow Limited", "mid", 48),
        ("Arrow Video", "Phenomena", "4K UHD", "Arrow Limited", "mid", 42),
        ("Arrow Video", "Society", "Blu-ray", "Arrow Limited", "standard", 32),
        ("Arrow Video", "Basket Case", "Blu-ray", "Arrow Limited", "standard", 28),
        ("Arrow Video", "Withnail & I", "Blu-ray", "Arrow Academy", "standard", 30),

        # ── Vinegar Syndrome — Additional Titles ───────────────────────────
        ("Vinegar Syndrome", "Houseboat Horror", "Blu-ray", "VS Limited", "standard", 26),
        ("Vinegar Syndrome", "Deadly Games", "4K UHD", "VS Limited", "standard", 34),
        ("Vinegar Syndrome", "Sorority Babes in the Slimeball Bowl-O-Rama", "4K UHD", "VS Limited", "mid", 38),
        ("Vinegar Syndrome", "The Room (Tommy Wiseau)", "Blu-ray", "VS Limited", "mid", 42),

        # ── Shout/Scream Factory — Additional Titles ───────────────────────
        ("Scream Factory", "The Fly (1986)", "4K UHD", "Scream Factory Limited", "mid", 44),
        ("Scream Factory", "Night of the Creeps", "Blu-ray", "Scream Factory Limited", "mid", 40),
        ("Shout Factory", "Big Trouble in Little China", "4K UHD", "Shout Select", "mid", 42),
        ("Scream Factory", "Re-Animator", "4K UHD", "Scream Factory Limited", "mid", 48),
        ("Scream Factory", "Pumpkinhead", "4K UHD", "Scream Factory Limited", "standard", 36),

        # ── 88 Films — Additional Titles ───────────────────────────────────
        ("88 Films", "City of the Living Dead", "4K UHD", "88 Films Limited", "standard", 36),
        ("88 Films", "The Beyond", "4K UHD", "88 Films Limited", "standard", 38),
        ("88 Films", "Zombie Flesh Eaters", "4K UHD", "88 Films Limited", "mid", 42),

        # ── Indicator — Additional Titles ──────────────────────────────────
        ("Indicator", "Film Noir Collection Vol 3", "Blu-ray", "Indicator Box Set", "high", 88),
        ("Indicator", "Hammer Volume Three", "Blu-ray", "Indicator Box Set", "high", 95),
        ("Indicator", "The Ealing Studios Rarities Collection", "Blu-ray", "Indicator Box Set", "high", 100),

        # ── HDZeta Premium Steelbooks ──────────────────────────────────────
        ("HDZeta", "Joker (2019)", "4K UHD", "HDZeta Steelbook", "grail", 180),
        ("HDZeta", "Avengers: Endgame", "4K UHD", "HDZeta Steelbook", "grail", 200),
        ("HDZeta", "Spider-Man: No Way Home", "4K UHD", "HDZeta Steelbook", "high", 130),
        ("HDZeta", "The Batman (2022)", "4K UHD", "HDZeta Steelbook", "high", 120),

        # ── Manta Lab Premium Steelbooks ───────────────────────────────────
        ("Manta Lab", "Parasite", "4K UHD", "Manta Lab Steelbook", "high", 110),
        ("Manta Lab", "The Godfather", "4K UHD", "Manta Lab Steelbook", "grail", 160),
        ("Manta Lab", "Goodfellas", "4K UHD", "Manta Lab Steelbook", "high", 100),
        ("Manta Lab", "Fight Club", "4K UHD", "Manta Lab Steelbook", "high", 95),

        # ── Steelbooks — Additional MCU Phase 4-5 ─────────────────────────
        ("Steelbook", "Black Panther: Wakanda Forever", "4K UHD", "Zavvi Steelbook", "mid", 38),
        ("Steelbook", "Guardians of the Galaxy Vol. 3", "4K UHD", "Zavvi Steelbook", "mid", 40),
        ("Steelbook", "Deadpool & Wolverine", "4K UHD", "Best Buy Steelbook", "mid", 42),
        ("Steelbook", "The Marvels", "4K UHD", "Zavvi Steelbook", "standard", 32),

        # ── Steelbooks — Additional Sci-Fi / Action ────────────────────────
        ("Steelbook", "Aliens", "4K UHD", "Zavvi Steelbook", "high", 58),
        ("Steelbook", "Terminator 2: Judgment Day", "4K UHD", "Zavvi Steelbook", "mid", 50),
        ("Steelbook", "Total Recall (1990)", "4K UHD", "Zavvi Steelbook", "mid", 44),
        ("Steelbook", "The Matrix Resurrections", "4K UHD", "Zavvi Steelbook", "standard", 35),
        ("Steelbook", "Dune: Part Two", "4K UHD", "Zavvi Steelbook", "mid", 48),

        # ── Steelbooks — Horror ────────────────────────────────────────────
        ("Steelbook", "The Shining", "4K UHD", "Zavvi Steelbook", "mid", 52),
        ("Steelbook", "Midsommar", "4K UHD", "A24 Limited Steelbook", "mid", 55),
        ("Steelbook", "Hereditary", "4K UHD", "A24 Limited Steelbook", "mid", 52),
        ("Steelbook", "The Exorcist", "4K UHD", "Zavvi Steelbook", "mid", 48),

        # ── Steelbooks — Classic Film ──────────────────────────────────────
        ("Steelbook", "Casablanca", "4K UHD", "Zavvi Steelbook", "high", 60),
        ("Steelbook", "Psycho (1960)", "4K UHD", "Zavvi Steelbook", "high", 58),
        ("Steelbook", "Rear Window", "4K UHD", "Zavvi Steelbook", "mid", 50),
        ("Steelbook", "Vertigo", "4K UHD", "Zavvi Steelbook", "mid", 52),

        # ── Mondo — Additional Steelbooks ──────────────────────────────────
        ("Mondo", "The Thing", "4K UHD", "Mondo Steelbook", "high", 75),
        ("Mondo", "Robocop", "4K UHD", "Mondo Steelbook", "mid", 55),
        ("Mondo", "Blade Runner", "4K UHD", "Mondo Steelbook", "high", 85),

        # ── Kino Lorber — Additional Titles ────────────────────────────────
        ("Kino Lorber", "M (1931)", "4K UHD", "KL Studio Classics", "standard", 36),
        ("Kino Lorber", "Diabolique", "Blu-ray", "KL Studio Classics", "standard", 28),
        ("Kino Lorber", "Wages of Fear", "4K UHD", "KL Studio Classics", "standard", 38),

        # ── Eureka — Additional Titles ─────────────────────────────────────
        ("Eureka", "Tokyo Story", "4K UHD", "Masters of Cinema", "standard", 36),
        ("Eureka", "Ikiru", "4K UHD", "Masters of Cinema", "standard", 34),
        ("Eureka", "Sansho the Bailiff", "Blu-ray", "Masters of Cinema", "standard", 28),

        # ── Criterion — Recent Additions ───────────────────────────────────
        ("Criterion", "Decision to Leave", "4K UHD", "Criterion 4K", "standard", 38),
        ("Criterion", "Past Lives", "Blu-ray", "Criterion #1131", "standard", 28),
        ("Criterion", "The Zone of Interest", "4K UHD", "Criterion 4K", "standard", 38),
        ("Criterion", "Fallen Angels", "4K UHD", "Criterion 4K", "standard", 36),
        ("Criterion", "Anatomy of a Fall", "Blu-ray", "Criterion #1140", "standard", 28),
        ("Criterion", "Killers of the Flower Moon", "4K UHD", "Criterion 4K", "mid", 40),
        ("Criterion", "The Holdovers", "Blu-ray", "Criterion #1145", "standard", 26),
        ("Criterion", "Aftersun", "Blu-ray", "Criterion #1120", "standard", 26),
        ("Criterion", "Showing Up", "Blu-ray", "Criterion #1118", "standard", 24),
        ("Criterion", "The Killer (2023)", "4K UHD", "Criterion 4K", "standard", 38),
        ("Criterion", "Merrily We Roll Along", "Blu-ray", "Criterion #1155", "standard", 28),
        ("Criterion", "Challengers", "Blu-ray", "Criterion #1160", "standard", 26),
        ("Criterion", "La Chimera", "Blu-ray", "Criterion #1152", "standard", 28),
        ("Criterion", "The Substance", "4K UHD", "Criterion 4K", "standard", 38),
        ("Criterion", "Shogun Assassin", "Blu-ray", "Criterion #640", "standard", 30),

        # ── Arrow Video — Additional Titles ────────────────────────────────
        ("Arrow Video", "Lifeforce", "4K UHD", "Arrow Limited", "mid", 45),
        ("Arrow Video", "The Changeling", "4K UHD", "Arrow Limited", "mid", 48),
        ("Arrow Video", "Dressed to Kill", "4K UHD", "Arrow Limited", "mid", 44),
        ("Arrow Video", "The Long Good Friday", "Blu-ray", "Arrow Academy", "standard", 30),
        ("Arrow Video", "Island of Death", "Blu-ray", "Arrow Limited", "standard", 28),
        ("Arrow Video", "Phantom of the Paradise", "4K UHD", "Arrow Limited", "mid", 46),
        ("Arrow Video", "The Vengeance Trilogy", "Blu-ray", "Arrow Box Set", "high", 85),
        ("Arrow Video", "Female Prisoner Scorpion Collection", "Blu-ray", "Arrow Box Set", "high", 80),
        ("Arrow Video", "Sartana Collection", "Blu-ray", "Arrow Box Set", "mid", 55),
        ("Arrow Video", "Nikkatsu Diamond Guys Vol. 1", "Blu-ray", "Arrow Box Set", "mid", 50),
        ("Arrow Video", "Seijun Suzuki: The Early Years Vol. 1", "Blu-ray", "Arrow Box Set", "high", 80),

        # ── Vinegar Syndrome — Additional Titles ──────────────────────────
        ("Vinegar Syndrome", "The Sadist", "4K UHD", "VS Limited", "mid", 38),
        ("Vinegar Syndrome", "Spookies", "Blu-ray", "VS Limited", "standard", 28),
        ("Vinegar Syndrome", "Miami Connection", "4K UHD", "VS Limited", "mid", 42),
        ("Vinegar Syndrome", "Night of the Demons", "4K UHD", "VS Limited", "mid", 44),
        ("Vinegar Syndrome", "Sledgehammer", "Blu-ray", "VS Limited", "standard", 26),
        ("Vinegar Syndrome", "Doom Asylum", "Blu-ray", "VS Limited", "standard", 24),
        ("Vinegar Syndrome", "Things", "4K UHD", "VS Limited", "mid", 40),
        ("Vinegar Syndrome", "Censor", "4K UHD", "VS Limited", "standard", 36),

        # ── Boutique Labels — Twilight Time ───────────────────────────────
        ("Twilight Time", "Fright Night (1985)", "Blu-ray", "Twilight Time Limited", "high", 80),
        ("Twilight Time", "The Alamo (1960)", "Blu-ray", "Twilight Time Limited", "mid", 55),
        ("Twilight Time", "Farewell, My Lovely", "Blu-ray", "Twilight Time Limited", "mid", 50),
        ("Twilight Time", "Wait Until Dark", "Blu-ray", "Twilight Time Limited", "high", 70),
        ("Twilight Time", "Night of the Iguana", "Blu-ray", "Twilight Time Limited", "mid", 60),

        # ── Boutique Labels — Fun City Editions ────────────────────────────
        ("Fun City Editions", "Liquid Sky", "4K UHD", "Fun City Limited", "mid", 48),
        ("Fun City Editions", "Variety", "Blu-ray", "Fun City Limited", "standard", 32),
        ("Fun City Editions", "Polyester", "4K UHD", "Fun City Limited", "mid", 45),

        # ── Boutique Labels — Severin Films ───────────────────────────────
        ("Severin", "The House That Jack Built", "4K UHD", "Severin Limited", "mid", 44),
        ("Severin", "All the Colors of the Dark", "4K UHD", "Severin Limited", "mid", 42),
        ("Severin", "Burial Ground", "4K UHD", "Severin Limited", "standard", 36),
        ("Severin", "Nightmare City", "Blu-ray", "Severin Limited", "standard", 30),
        ("Severin", "The Beyond", "4K UHD", "Severin Limited", "mid", 42),
        ("Severin", "Blood for Dracula / Flesh for Frankenstein", "Blu-ray", "Severin Box Set", "high", 85),
        ("Severin", "Jess Franco Collection", "Blu-ray", "Severin Box Set", "high", 110),

        # ── Boutique Labels — Blue Underground ─────────────────────────────
        ("Blue Underground", "Zombie (Lucio Fulci)", "4K UHD", "Blue Underground Limited", "mid", 45),
        ("Blue Underground", "Maniac (1980)", "4K UHD", "Blue Underground Limited", "mid", 48),
        ("Blue Underground", "The New York Ripper", "4K UHD", "Blue Underground Limited", "mid", 42),
        ("Blue Underground", "The Stendhal Syndrome", "4K UHD", "Blue Underground Limited", "mid", 40),
        ("Blue Underground", "Inferno (Dario Argento)", "4K UHD", "Blue Underground Limited", "mid", 44),

        # ── Anime Blu-ray Box Sets ──────────────────────────────────────────
        ("Anime", "Neon Genesis Evangelion Complete Series", "Blu-ray", "GKIDS Box Set", "high", 90),
        ("Anime", "Neon Genesis Evangelion: The End of Evangelion", "Blu-ray", "GKIDS Limited", "mid", 45),
        ("Anime", "Cowboy Bebop Complete Series", "Blu-ray", "Funimation Box Set", "high", 85),
        ("Anime", "Cowboy Bebop: The Movie", "4K UHD", "Funimation Limited", "mid", 48),
        ("Anime", "Akira", "4K UHD", "Funimation Limited", "high", 65),
        ("Anime", "Ghost in the Shell (1995)", "4K UHD", "Lionsgate Limited", "mid", 55),
        ("Anime", "Perfect Blue", "Blu-ray", "GKIDS Limited", "mid", 42),
        ("Anime", "Paprika", "Blu-ray", "Sony Limited", "mid", 38),
        ("Anime", "FLCL Complete Collection", "Blu-ray", "Funimation Limited", "mid", 45),
        ("Anime", "Samurai Champloo Complete Series", "Blu-ray", "Funimation Box Set", "high", 80),
        ("Anime", "Serial Experiments Lain Complete Series", "Blu-ray", "Funimation Limited", "high", 75),
        ("Anime", "Berserk: The Golden Age Arc Trilogy", "Blu-ray", "Viz Media Box Set", "mid", 55),

        # ── Studio Ghibli Box Sets ──────────────────────────────────────────
        ("Anime", "Studio Ghibli Complete Collection", "Blu-ray", "GKIDS Box Set", "grail", 280),
        ("Anime", "The Wind Rises", "Blu-ray", "GKIDS Limited", "standard", 30),
        ("Anime", "When Marnie Was There", "Blu-ray", "GKIDS Limited", "standard", 28),
        ("Anime", "The Tale of the Princess Kaguya", "Blu-ray", "GKIDS Limited", "standard", 32),
        ("Anime", "Grave of the Fireflies", "Blu-ray", "Sentai Limited", "mid", 45),
        ("Anime", "Pom Poko", "Blu-ray", "GKIDS Limited", "standard", 28),
        ("Anime", "Only Yesterday", "Blu-ray", "GKIDS Limited", "standard", 26),

        # ── Full Slip Premium Editions — KimchiDVD ──────────────────────────
        ("KimchiDVD", "Interstellar", "4K UHD", "KimchiDVD Full Slip", "grail", 180),
        ("KimchiDVD", "Inception", "4K UHD", "KimchiDVD Full Slip", "grail", 160),
        ("KimchiDVD", "Parasite", "4K UHD", "KimchiDVD Full Slip", "grail", 170),
        ("KimchiDVD", "La La Land", "4K UHD", "KimchiDVD Full Slip", "high", 120),
        ("KimchiDVD", "Oldboy", "4K UHD", "KimchiDVD Full Slip", "grail", 150),

        # ── Full Slip Premium Editions — Plain Archive ──────────────────────
        ("Plain Archive", "Drive (2011)", "4K UHD", "Plain Archive Full Slip", "grail", 180),
        ("Plain Archive", "The Handmaiden", "4K UHD", "Plain Archive Full Slip", "grail", 200),
        ("Plain Archive", "Memories of Murder", "4K UHD", "Plain Archive Full Slip", "grail", 160),
        ("Plain Archive", "Burning (2018)", "4K UHD", "Plain Archive Full Slip", "high", 130),
        ("Plain Archive", "Whiplash", "4K UHD", "Plain Archive Full Slip", "high", 140),

        # ── Full Slip Premium Editions — WeET Collection ────────────────────
        ("WeET", "Spider-Man: Into the Spider-Verse", "4K UHD", "WeET Full Slip", "grail", 200),
        ("WeET", "Blade Runner 2049", "4K UHD", "WeET Full Slip", "grail", 190),
        ("WeET", "Joker (2019)", "4K UHD", "WeET Full Slip", "grail", 170),
        ("WeET", "The Dark Knight", "4K UHD", "WeET Full Slip", "grail", 220),
        ("WeET", "Mad Max: Fury Road", "4K UHD", "WeET Full Slip", "high", 140),

        # ── 4K UHD Steelbooks (Additional) ──────────────────────────────────
        ("Steelbook", "Gladiator", "4K UHD", "Zavvi Steelbook", "mid", 48),
        ("Steelbook", "The Godfather", "4K UHD", "Zavvi Steelbook", "high", 58),
        ("Steelbook", "The Godfather Part II", "4K UHD", "Zavvi Steelbook", "high", 55),
        ("Steelbook", "Goodfellas", "4K UHD", "Zavvi Steelbook", "mid", 50),
        ("Steelbook", "Scarface", "4K UHD", "Zavvi Steelbook", "mid", 46),
        ("Steelbook", "Fight Club", "4K UHD", "Zavvi Steelbook", "mid", 48),
        ("Steelbook", "Pulp Fiction", "4K UHD", "Zavvi Steelbook", "mid", 50),
        ("Steelbook", "The Silence of the Lambs", "4K UHD", "Zavvi Steelbook", "mid", 46),
        ("Steelbook", "Se7en", "4K UHD", "Zavvi Steelbook", "mid", 48),
        ("Steelbook", "No Country for Old Men", "4K UHD", "Zavvi Steelbook", "mid", 50),
        ("Steelbook", "There Will Be Blood", "4K UHD", "Zavvi Steelbook", "high", 58),
        ("Steelbook", "Apocalypse Now: Final Cut", "4K UHD", "Zavvi Steelbook", "high", 62),
        ("Steelbook", "The Revenant", "4K UHD", "Zavvi Steelbook", "mid", 44),
        ("Steelbook", "Fury Road: Furiosa", "4K UHD", "Best Buy Steelbook", "mid", 42),

        # === EXPANSION ROUND — 190+ new items ===

        # ── Criterion Collection (Additional Titles) ──────────────────────
        ("Criterion", "The Piano", "Blu-ray", "Criterion #1050", "standard", 28),
        ("Criterion", "Thelma & Louise", "4K UHD", "Criterion 4K", "standard", 38),
        ("Criterion", "Blue Velvet", "4K UHD", "Criterion 4K", "standard", 38),
        ("Criterion", "A Room with a View", "Blu-ray", "Criterion #1015", "standard", 26),
        ("Criterion", "The Thin Red Line", "4K UHD", "Criterion 4K", "mid", 40),
        ("Criterion", "Fanny and Alexander", "Blu-ray", "Criterion #261", "mid", 48),
        ("Criterion", "Amarcord", "Blu-ray", "Criterion #4", "standard", 26),
        ("Criterion", "The Leopard", "4K UHD", "Criterion 4K", "mid", 42),
        ("Criterion", "Wings of Desire", "Blu-ray", "Criterion #490", "standard", 28),
        ("Criterion", "The Double Life of Veronique", "Blu-ray", "Criterion #576", "standard", 30),
        ("Criterion", "Three Colors Trilogy", "Blu-ray", "Criterion Box Set", "high", 85),
        ("Criterion", "The Virgin Suicides", "4K UHD", "Criterion 4K", "standard", 38),
        ("Criterion", "Uncut Gems", "4K UHD", "Criterion 4K", "standard", 36),
        ("Criterion", "Punch-Drunk Love", "Blu-ray", "Criterion #1070", "standard", 28),
        ("Criterion", "The Grand Budapest Hotel", "Blu-ray", "Criterion #856", "standard", 26),
        ("Criterion", "Moonrise Kingdom", "Blu-ray", "Criterion #776", "standard", 24),
        ("Criterion", "The Royal Tenenbaums", "Blu-ray", "Criterion #157", "standard", 26),
        ("Criterion", "Rushmore", "Blu-ray", "Criterion #65", "standard", 24),
        ("Criterion", "Solaris (1972)", "Blu-ray", "Criterion #164", "standard", 30),
        ("Criterion", "Mirror (Tarkovsky)", "Blu-ray", "Criterion #1047", "standard", 32),
        ("Criterion", "Come and See", "Blu-ray", "Criterion #1058", "standard", 30),
        ("Criterion", "Night of the Living Dead", "4K UHD", "Criterion 4K", "standard", 36),
        ("Criterion", "Andrei Rublev", "Blu-ray", "Criterion #34", "standard", 30),
        ("Criterion", "Tokyo Story", "Blu-ray", "Criterion #217", "standard", 28),
        ("Criterion", "A Brighter Summer Day", "Blu-ray", "Criterion #893", "mid", 42),
        ("Criterion", "Yi Yi", "4K UHD", "Criterion 4K", "standard", 38),
        ("Criterion", "The Tree of Life", "4K UHD", "Criterion 4K", "mid", 40),
        ("Criterion", "Badlands", "Blu-ray", "Criterion #651", "standard", 28),
        ("Criterion", "Days of Heaven", "Blu-ray", "Criterion #409", "standard", 26),
        ("Criterion", "Mulholland Dr.", "4K UHD", "Criterion 4K", "standard", 38),

        # ── Arrow Video (Additional Titles) ───────────────────────────────
        ("Arrow Video", "Candyman (1992)", "4K UHD", "Arrow Limited", "mid", 48),
        ("Arrow Video", "A Bay of Blood", "Blu-ray", "Arrow Limited", "standard", 30),
        ("Arrow Video", "Opera (Dario Argento)", "4K UHD", "Arrow Limited", "mid", 44),
        ("Arrow Video", "The Beyond (Fulci)", "4K UHD", "Arrow Limited", "mid", 46),
        ("Arrow Video", "Bride of Re-Animator", "4K UHD", "Arrow Limited", "mid", 42),
        ("Arrow Video", "Tremors", "4K UHD", "Arrow Limited", "mid", 44),
        ("Arrow Video", "Crash (Cronenberg)", "4K UHD", "Arrow Limited", "mid", 46),
        ("Arrow Video", "The Burning", "Blu-ray", "Arrow Limited", "standard", 32),
        ("Arrow Video", "Carnival of Souls", "4K UHD", "Arrow Limited", "standard", 36),
        ("Arrow Video", "The Wicker Man", "4K UHD", "Arrow Limited", "mid", 48),
        ("Arrow Video", "Maniac (1980)", "4K UHD", "Arrow Limited", "mid", 44),
        ("Arrow Video", "J-Horror Rising Collection", "Blu-ray", "Arrow Box Set", "high", 85),
        ("Arrow Video", "Shawscope Vol. 1", "Blu-ray", "Arrow Box Set", "high", 110),
        ("Arrow Video", "Shawscope Vol. 2", "Blu-ray", "Arrow Box Set", "high", 110),
        ("Arrow Video", "Montage of Heck: Kurt Cobain", "Blu-ray", "Arrow Limited", "standard", 28),
        ("Arrow Video", "Stray Cat Rock Collection", "Blu-ray", "Arrow Box Set", "mid", 60),
        ("Arrow Video", "Prom Night", "Blu-ray", "Arrow Limited", "standard", 30),
        ("Arrow Video", "Inferno (Argento)", "4K UHD", "Arrow Limited", "mid", 44),
        ("Arrow Video", "Day of the Dead", "4K UHD", "Arrow Limited", "mid", 50),
        ("Arrow Video", "Cat o' Nine Tails", "4K UHD", "Arrow Limited", "mid", 42),

        # ── Vinegar Syndrome (Additional Titles) ─────────────────────────
        ("Vinegar Syndrome", "Xtro", "4K UHD", "VS Limited", "mid", 40),
        ("Vinegar Syndrome", "Sleepaway Camp", "4K UHD", "VS Limited", "mid", 44),
        ("Vinegar Syndrome", "Basket Case", "4K UHD", "VS Limited", "mid", 42),
        ("Vinegar Syndrome", "Frankenhooker", "4K UHD", "VS Limited", "mid", 38),
        ("Vinegar Syndrome", "Class of 1984", "4K UHD", "VS Limited", "standard", 36),
        ("Vinegar Syndrome", "Terrorvision", "4K UHD", "VS Limited", "standard", 34),
        ("Vinegar Syndrome", "Microwave Massacre", "Blu-ray", "VS Limited", "standard", 26),
        ("Vinegar Syndrome", "The Nesting", "Blu-ray", "VS Limited", "standard", 26),

        # ── Severin Films (Additional Titles) ─────────────────────────────
        ("Severin", "The Changeling (1980)", "4K UHD", "Severin Limited", "mid", 44),
        ("Severin", "The Slumber Party Massacre Collection", "Blu-ray", "Severin Box Set", "high", 80),
        ("Severin", "Anthropophagus", "4K UHD", "Severin Limited", "mid", 42),
        ("Severin", "City of the Living Dead (Fulci)", "4K UHD", "Severin Limited", "mid", 44),
        ("Severin", "Don't Torture a Duckling", "4K UHD", "Severin Limited", "mid", 42),
        ("Severin", "Cannibal Holocaust", "4K UHD", "Severin Limited", "mid", 46),
        ("Severin", "The House by the Cemetery (Fulci)", "4K UHD", "Severin Limited", "mid", 42),

        # ── Shout/Scream Factory (Additional Titles) ──────────────────────
        ("Scream Factory", "Prince of Darkness", "4K UHD", "Scream Factory Limited", "mid", 42),
        ("Scream Factory", "From Beyond", "4K UHD", "Scream Factory Limited", "mid", 44),
        ("Scream Factory", "The Blob (1988)", "4K UHD", "Scream Factory Limited", "mid", 40),
        ("Scream Factory", "Night of the Living Dead (1990)", "4K UHD", "Scream Factory Limited", "mid", 42),
        ("Scream Factory", "Army of Darkness", "4K UHD", "Scream Factory Limited", "mid", 44),
        ("Shout Factory", "Sleepwalkers", "Blu-ray", "Shout Select", "standard", 28),
        ("Scream Factory", "Silver Bullet", "4K UHD", "Scream Factory Limited", "standard", 38),
        ("Scream Factory", "Poltergeist (1982)", "4K UHD", "Scream Factory Limited", "mid", 46),

        # ── Kino Lorber (Additional Titles) ───────────────────────────────
        ("Kino Lorber", "The Man Who Laughs", "4K UHD", "KL Studio Classics", "standard", 36),
        ("Kino Lorber", "The Phantom of the Opera (1925)", "4K UHD", "KL Studio Classics", "standard", 36),
        ("Kino Lorber", "Sunrise: A Song of Two Humans", "4K UHD", "KL Studio Classics", "standard", 38),
        ("Kino Lorber", "Detour (1945)", "Blu-ray", "KL Studio Classics", "standard", 26),
        ("Kino Lorber", "Touch of Evil", "4K UHD", "KL Studio Classics", "standard", 38),
        ("Kino Lorber", "Night of the Hunter", "4K UHD", "KL Studio Classics", "standard", 38),
        ("Kino Lorber", "The Killing", "4K UHD", "KL Studio Classics", "standard", 36),

        # ── Eureka / Masters of Cinema (Additional) ──────────────────────
        ("Eureka", "Hausu (House)", "4K UHD", "Masters of Cinema", "mid", 40),
        ("Eureka", "Onibaba", "Blu-ray", "Masters of Cinema", "standard", 28),
        ("Eureka", "Kwaidan", "Blu-ray", "Masters of Cinema", "standard", 30),
        ("Eureka", "Woman in the Dunes", "Blu-ray", "Masters of Cinema", "standard", 28),
        ("Eureka", "Branded to Kill", "Blu-ray", "Masters of Cinema", "standard", 26),
        ("Eureka", "Ugetsu", "4K UHD", "Masters of Cinema", "standard", 36),

        # ── BFI (British Film Institute) ──────────────────────────────────
        ("BFI", "The Red Shoes", "Blu-ray", "BFI Limited", "standard", 32),
        ("BFI", "Black Narcissus", "Blu-ray", "BFI Limited", "standard", 30),
        ("BFI", "A Matter of Life and Death", "Blu-ray", "BFI Limited", "standard", 30),
        ("BFI", "Peeping Tom", "Blu-ray", "BFI Limited", "standard", 28),
        ("BFI", "The Wicker Man", "4K UHD", "BFI Limited", "mid", 42),
        ("BFI", "Performance", "4K UHD", "BFI Limited", "mid", 40),
        ("BFI", "Don't Look Now", "4K UHD", "BFI Limited", "mid", 44),
        ("BFI", "Kes", "4K UHD", "BFI Limited", "standard", 36),

        # ── 101 Films / 101 Films Black Label ────────────────────────────
        ("101 Films", "Hardware", "4K UHD", "101 Films Black Label", "standard", 32),
        ("101 Films", "Death Line", "4K UHD", "101 Films Black Label", "standard", 30),
        ("101 Films", "The Changeling (1980)", "Blu-ray", "101 Films Black Label", "standard", 26),
        ("101 Films", "Theatre of Blood", "Blu-ray", "101 Films Black Label", "standard", 24),

        # ── Second Sight (Additional) ────────────────────────────────────
        ("Second Sight", "Suspiria (2018)", "4K UHD", "Second Sight Limited", "mid", 52),
        ("Second Sight", "Possum", "4K UHD", "Second Sight Limited", "mid", 44),
        ("Second Sight", "A Field in England", "4K UHD", "Second Sight Limited", "mid", 44),
        ("Second Sight", "Kill List", "4K UHD", "Second Sight Limited", "mid", 48),
        ("Second Sight", "The Lighthouse", "4K UHD", "Second Sight Limited", "mid", 52),

        # ── HDZeta Premium (Additional) ──────────────────────────────────
        ("HDZeta", "Inception", "4K UHD", "HDZeta Steelbook", "grail", 190),
        ("HDZeta", "Interstellar (One Click)", "4K UHD", "HDZeta Steelbook", "grail", 250),
        ("HDZeta", "Blade Runner 2049", "4K UHD", "HDZeta Steelbook", "grail", 180),
        ("HDZeta", "Mad Max: Fury Road", "4K UHD", "HDZeta Steelbook", "high", 140),
        ("HDZeta", "It (2017)", "4K UHD", "HDZeta Steelbook", "high", 120),
        ("HDZeta", "Wonder Woman", "4K UHD", "HDZeta Steelbook", "high", 110),

        # ── Manta Lab Premium (Additional) ───────────────────────────────
        ("Manta Lab", "Joker (2019)", "4K UHD", "Manta Lab Steelbook", "grail", 170),
        ("Manta Lab", "Spider-Man: No Way Home", "4K UHD", "Manta Lab Steelbook", "high", 130),
        ("Manta Lab", "The Shawshank Redemption", "4K UHD", "Manta Lab Steelbook", "grail", 150),
        ("Manta Lab", "Forrest Gump", "4K UHD", "Manta Lab Steelbook", "high", 110),
        ("Manta Lab", "Schindler's List", "4K UHD", "Manta Lab Steelbook", "high", 120),

        # ── KimchiDVD Premium (Additional) ───────────────────────────────
        ("KimchiDVD", "The Dark Knight", "4K UHD", "KimchiDVD Full Slip", "grail", 200),
        ("KimchiDVD", "Avengers: Endgame", "4K UHD", "KimchiDVD Full Slip", "grail", 180),
        ("KimchiDVD", "Joker (2019)", "4K UHD", "KimchiDVD Full Slip", "grail", 160),
        ("KimchiDVD", "Spider-Man: Into the Spider-Verse", "4K UHD", "KimchiDVD Full Slip", "grail", 170),

        # ── Plain Archive Premium (Additional) ───────────────────────────
        ("Plain Archive", "Oldboy", "4K UHD", "Plain Archive Full Slip", "grail", 190),
        ("Plain Archive", "Parasite (Black & White)", "4K UHD", "Plain Archive Full Slip", "grail", 180),
        ("Plain Archive", "A Taxi Driver", "4K UHD", "Plain Archive Full Slip", "high", 130),
        ("Plain Archive", "Joint Security Area", "4K UHD", "Plain Archive Full Slip", "high", 120),

        # ── WeET Collection (Additional) ─────────────────────────────────
        ("WeET", "Avengers: Endgame", "4K UHD", "WeET Full Slip", "grail", 210),
        ("WeET", "Inception", "4K UHD", "WeET Full Slip", "grail", 190),
        ("WeET", "Interstellar", "4K UHD", "WeET Full Slip", "grail", 200),
        ("WeET", "Spider-Man: No Way Home", "4K UHD", "WeET Full Slip", "grail", 180),

        # ── FilmArena Premium ────────────────────────────────────────────
        ("FilmArena", "Blade Runner 2049", "4K UHD", "FilmArena Steelbook", "grail", 200),
        ("FilmArena", "Joker (2019)", "4K UHD", "FilmArena Steelbook", "grail", 180),
        ("FilmArena", "Interstellar", "4K UHD", "FilmArena Steelbook", "grail", 190),
        ("FilmArena", "The Batman (2022)", "4K UHD", "FilmArena Steelbook", "high", 130),
        ("FilmArena", "Dune (2021)", "4K UHD", "FilmArena Steelbook", "high", 120),
        ("FilmArena", "Tenet", "4K UHD", "FilmArena Steelbook", "high", 110),

        # ── Anime Blu-ray (Additional Releases) ─────────────────────────
        ("Anime", "Demon Slayer: Mugen Train", "4K UHD", "Aniplex Limited", "mid", 55),
        ("Anime", "Your Name (Kimi no Na wa)", "4K UHD", "Funimation Limited", "mid", 50),
        ("Anime", "Weathering with You", "4K UHD", "GKIDS Limited", "mid", 48),
        ("Anime", "Suzume", "4K UHD", "Crunchyroll Limited", "mid", 45),
        ("Anime", "Attack on Titan: Final Season Box Set", "Blu-ray", "Funimation Box Set", "high", 90),
        ("Anime", "Fullmetal Alchemist: Brotherhood Complete", "Blu-ray", "Funimation Box Set", "high", 85),
        ("Anime", "Steins;Gate Complete Series", "Blu-ray", "Funimation Box Set", "high", 75),
        ("Anime", "Neon Genesis Evangelion 3.0+1.0", "4K UHD", "GKIDS Limited", "mid", 50),
        ("Anime", "Dragon Ball Z: Complete Series", "Blu-ray", "Funimation Box Set", "high", 120),
        ("Anime", "One Piece Film: Red", "Blu-ray", "Crunchyroll Limited", "standard", 35),
        ("Anime", "Jujutsu Kaisen 0", "4K UHD", "Crunchyroll Limited", "mid", 42),
        ("Anime", "Ghost in the Shell: Stand Alone Complex Complete", "Blu-ray", "Manga UK Box Set", "high", 90),
        ("Anime", "Redline", "Blu-ray", "Manga UK Limited", "mid", 55),
        ("Anime", "Memories (Katsuhiro Otomo)", "Blu-ray", "Discotek Limited", "mid", 45),
        ("Anime", "Vampire Hunter D: Bloodlust", "4K UHD", "Discotek Limited", "mid", 48),
        ("Anime", "Ninja Scroll", "Blu-ray", "Sentai Limited", "mid", 42),
        ("Anime", "Trigun: Badlands Rumble", "Blu-ray", "Funimation Limited", "standard", 32),
        ("Anime", "Millennium Actress", "4K UHD", "GKIDS Limited", "mid", 48),
        ("Anime", "Tokyo Godfathers", "4K UHD", "GKIDS Limited", "mid", 46),
        ("Anime", "Magnetic Rose (Memories)", "Blu-ray", "Discotek Limited", "mid", 40),

        # ── Steelbooks — Franchise Essentials ────────────────────────────
        ("Steelbook", "Indiana Jones: Raiders of the Lost Ark", "4K UHD", "Zavvi Steelbook", "high", 60),
        ("Steelbook", "Indiana Jones: Last Crusade", "4K UHD", "Zavvi Steelbook", "mid", 52),
        ("Steelbook", "Batman Begins", "4K UHD", "Zavvi Steelbook", "mid", 48),
        ("Steelbook", "Jurassic Park", "4K UHD", "Zavvi Steelbook", "mid", 50),
        ("Steelbook", "Back to the Future Trilogy", "4K UHD", "Zavvi Steelbook Box Set", "high", 85),
        ("Steelbook", "The Godfather Trilogy", "4K UHD", "Zavvi Steelbook Box Set", "high", 90),
        ("Steelbook", "E.T. the Extra-Terrestrial", "4K UHD", "Zavvi Steelbook", "mid", 48),
        ("Steelbook", "Schindler's List", "4K UHD", "Zavvi Steelbook", "mid", 52),
        ("Steelbook", "Forrest Gump", "4K UHD", "Zavvi Steelbook", "mid", 46),
        ("Steelbook", "The Shawshank Redemption", "4K UHD", "Zavvi Steelbook", "mid", 50),
        ("Steelbook", "Saving Private Ryan", "4K UHD", "Zavvi Steelbook", "mid", 48),
        ("Steelbook", "Braveheart", "4K UHD", "Zavvi Steelbook", "mid", 46),
        ("Steelbook", "The Green Mile", "4K UHD", "Zavvi Steelbook", "mid", 48),
        ("Steelbook", "Heat (1995)", "4K UHD", "Zavvi Steelbook", "mid", 50),
        ("Steelbook", "Casino (1995)", "4K UHD", "Zavvi Steelbook", "mid", 46),
        ("Steelbook", "Taxi Driver", "4K UHD", "Zavvi Steelbook", "mid", 50),
        ("Steelbook", "Raging Bull", "4K UHD", "Zavvi Steelbook", "mid", 48),
        ("Steelbook", "Reservoir Dogs", "4K UHD", "Zavvi Steelbook", "mid", 46),
        ("Steelbook", "Kill Bill Vol. 1", "4K UHD", "Zavvi Steelbook", "mid", 48),
        ("Steelbook", "Kill Bill Vol. 2", "4K UHD", "Zavvi Steelbook", "mid", 46),

        # ── Mondo Steelbooks (Additional) ────────────────────────────────
        ("Mondo", "Ghostbusters", "4K UHD", "Mondo Steelbook", "mid", 55),
        ("Mondo", "Teenage Mutant Ninja Turtles", "4K UHD", "Mondo Steelbook", "mid", 50),
        ("Mondo", "Labyrinth", "4K UHD", "Mondo Steelbook", "high", 70),
        ("Mondo", "The Princess Bride", "4K UHD", "Mondo Steelbook", "mid", 55),

        # ── Imprint (Additional) ─────────────────────────────────────────
        ("Imprint", "The Hitcher (1986)", "Blu-ray", "Imprint Limited", "mid", 45),
        ("Imprint", "Death Wish (1974)", "Blu-ray", "Imprint Limited", "mid", 42),
        ("Imprint", "Dressed to Kill", "Blu-ray", "Imprint Limited", "mid", 44),
        ("Imprint", "Body Double", "Blu-ray", "Imprint Limited", "mid", 42),
        ("Imprint", "Blow Out", "4K UHD", "Imprint Limited", "mid", 48),

        # ── Blue Underground (Additional) ────────────────────────────────
        ("Blue Underground", "Bird with the Crystal Plumage", "4K UHD", "Blue Underground Limited", "mid", 42),
        ("Blue Underground", "Torso", "4K UHD", "Blue Underground Limited", "mid", 40),
        ("Blue Underground", "Cat o' Nine Tails", "4K UHD", "Blue Underground Limited", "mid", 42),
        ("Blue Underground", "Shock (Mario Bava)", "4K UHD", "Blue Underground Limited", "mid", 40),
        ("Blue Underground", "Twitch of the Death Nerve", "4K UHD", "Blue Underground Limited", "mid", 44),
        ("Blue Underground", "The House on the Edge of the Park", "4K UHD", "Blue Underground Limited", "mid", 40),

        # ── Best Buy Exclusive (Additional) ──────────────────────────────
        ("Best Buy Exclusive", "Gladiator II", "4K UHD", "Best Buy Steelbook", "mid", 38),
        ("Best Buy Exclusive", "Alien: Romulus", "4K UHD", "Best Buy Steelbook", "mid", 40),

        # ── Expansion Batch — 4K Steelbook Franchise Editions ────────────
        ("Steelbook", "The Lord of the Rings: Fellowship (Extended)", "4K UHD", "WB Steelbook", "high", 65),
        ("Steelbook", "The Lord of the Rings: Two Towers (Extended)", "4K UHD", "WB Steelbook", "high", 65),
        ("Steelbook", "The Lord of the Rings: Return of the King (Extended)", "4K UHD", "WB Steelbook", "high", 65),
        ("Steelbook", "The Lord of the Rings: 4K Trilogy Box Set", "4K UHD", "WB Steelbook Box Set", "grail", 180),
        ("Steelbook", "The Dark Knight Trilogy 4K Box Set", "4K UHD", "WB Steelbook Box Set", "grail", 160),
        ("Steelbook", "Batman (1989) 4K Steelbook", "4K UHD", "WB Steelbook", "mid", 48),
        ("Steelbook", "Batman Returns 4K Steelbook", "4K UHD", "WB Steelbook", "mid", 45),
        ("Steelbook", "Blade Runner: The Final Cut 4K Steelbook", "4K UHD", "WB Steelbook", "high", 60),
        ("Steelbook", "Blade Runner 2049 4K Steelbook", "4K UHD", "WB Steelbook", "mid", 52),
        ("Steelbook", "Alien 4K Steelbook (40th Anniversary)", "4K UHD", "Fox Steelbook", "high", 60),
        ("Steelbook", "Aliens 4K Steelbook", "4K UHD", "Fox Steelbook", "mid", 50),
        ("Steelbook", "Indiana Jones 4-Film 4K Steelbook Collection", "4K UHD", "Paramount Steelbook Box Set", "grail", 170),

        # ── Criterion Collection — Kurosawa ──────────────────────────────
        ("Criterion", "Rashomon", "Blu-ray", "Criterion #138", "standard", 26),
        ("Criterion", "Ikiru", "Blu-ray", "Criterion #221", "standard", 28),
        ("Criterion", "Yojimbo / Sanjuro (Double Feature)", "Blu-ray", "Criterion Box Set", "mid", 45),
        ("Criterion", "Throne of Blood", "Blu-ray", "Criterion #190", "standard", 28),
        ("Criterion", "High and Low", "Blu-ray", "Criterion #24", "standard", 30),
        ("Criterion", "Ran", "4K UHD", "Criterion 4K", "mid", 40),

        # ── Criterion Collection — Bergman ───────────────────────────────
        ("Criterion", "Ingmar Bergman's Cinema (Box Set)", "Blu-ray", "Criterion Box Set", "grail", 220),
        ("Criterion", "The Seventh Seal", "Blu-ray", "Criterion #11", "standard", 26),
        ("Criterion", "Wild Strawberries", "Blu-ray", "Criterion #139", "standard", 26),
        ("Criterion", "Fanny and Alexander", "Blu-ray", "Criterion #261", "standard", 30),

        # ── Criterion Collection — Tarkovsky ─────────────────────────────
        ("Criterion", "Andrei Rublev", "Blu-ray", "Criterion #34", "standard", 30),
        ("Criterion", "Solaris (1972)", "Blu-ray", "Criterion #164", "standard", 30),
        ("Criterion", "Mirror", "Blu-ray", "Criterion #1047", "standard", 28),
        ("Criterion", "The Sacrifice", "Blu-ray", "Criterion #1059", "standard", 28),

        # ── Criterion Collection — Wong Kar-wai Singles ──────────────────
        ("Criterion", "Chungking Express", "Blu-ray", "Criterion #453", "standard", 30),
        ("Criterion", "Happy Together", "Blu-ray", "Criterion #1079", "standard", 28),
        ("Criterion", "Fallen Angels", "Blu-ray", "Criterion #1080", "standard", 28),

        # ── Arrow Video Limited Editions Extended ────────────────────────
        ("Arrow Video", "Phenomena (Dario Argento)", "4K UHD", "Arrow Limited", "mid", 45),
        ("Arrow Video", "Inferno (Dario Argento)", "4K UHD", "Arrow Limited", "mid", 44),
        ("Arrow Video", "Opera (Dario Argento)", "4K UHD", "Arrow Limited", "mid", 42),
        ("Arrow Video", "The Beyond (Lucio Fulci)", "4K UHD", "Arrow Limited", "mid", 44),
        ("Arrow Video", "Zombie Flesh Eaters (Lucio Fulci)", "4K UHD", "Arrow Limited", "mid", 42),
        ("Arrow Video", "Society (Brian Yuzna)", "Blu-ray", "Arrow Limited", "mid", 40),
        ("Arrow Video", "Videodrome", "4K UHD", "Arrow Limited", "mid", 48),
        ("Arrow Video", "The Fly (Cronenberg)", "4K UHD", "Arrow Limited", "mid", 46),

        # ── Vinegar Syndrome Releases ────────────────────────────────────
        ("Vinegar Syndrome", "Slumber Party Massacre", "4K UHD", "VS Limited", "mid", 42),
        ("Vinegar Syndrome", "Sorority Babes", "Blu-ray", "VS Limited", "standard", 35),
        ("Vinegar Syndrome", "Tammy and the T-Rex", "4K UHD", "VS Limited", "mid", 45),
        ("Vinegar Syndrome", "Blood Rage", "4K UHD", "VS Limited", "mid", 40),
        ("Vinegar Syndrome", "Psycho Goreman", "4K UHD", "VS Limited", "mid", 42),
        ("Vinegar Syndrome", "Pieces", "4K UHD", "VS Limited", "mid", 44),
        ("Vinegar Syndrome", "Silent Night Deadly Night Collection", "Blu-ray", "VS Box Set", "high", 85),
        ("Vinegar Syndrome", "Night of the Demons", "4K UHD", "VS Limited", "mid", 42),
        ("Vinegar Syndrome", "Maniac Cop Trilogy", "4K UHD", "VS Box Set", "high", 90),
        ("Vinegar Syndrome", "The Mutilator", "4K UHD", "VS Limited", "mid", 40),

        # ── Vinegar Syndrome Additional ──────────────────────────────────
        ("Vinegar Syndrome", "The Slumber Party Massacre Collection", "Blu-ray", "VS Box Set", "high", 80),
        ("Vinegar Syndrome", "Dead Heat", "4K UHD", "VS Limited", "mid", 42),
        ("Vinegar Syndrome", "The Prowler", "4K UHD", "VS Limited", "mid", 42),
    ]

    catalog = []
    for label, title, fmt, edition, tier, price in discs:
        catalog.append({
            "label": label,
            "title": title,
            "format": fmt,
            "edition": edition,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    label = item["label"]
    title = item["title"]
    fmt = item["format"]
    edition = item["edition"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{label}-{title}-{edition}"),
        title=f"{title} ({fmt})",
        set_code=label.lower().replace(" ", "-"),
        brand=label,
        rarity=item["rarity_tier"].title(),
        notes=f"{label} | {edition} | {fmt}",
        attributes_json={
            "label": label,
            "format": fmt,
            "edition": edition,
            "is_steelbook": "steelbook" in edition.lower(),
            "is_4k": fmt == "4K UHD",
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]
    is_limited = any(kw in item["edition"].lower() for kw in ["limited", "steelbook", "box set"])
    is_4k = item["format"] == "4K UHD"

    return PriceObservation(
        features={
            "condition_score": 0.9,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": 0.85 if is_limited else 0.4,
            "is_steelbook": 1.0 if "steelbook" in item["edition"].lower() else 0.0,
            "is_4k": 1.0 if is_4k else 0.0,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Blu-ray Steelbook catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Blu-ray Steelbook Import ===")

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

    logger.info(f"\n=== Blu-ray Steelbook Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
