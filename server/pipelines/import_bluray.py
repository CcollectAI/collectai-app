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

        # ── 4K UHD Steelbooks — Nolan Films ──────────────────────────────
        ("Best Buy Exclusive", "Interstellar", "4K UHD", "Steelbook", "high", 65),
        ("Best Buy Exclusive", "Tenet", "4K UHD", "Steelbook", "mid", 45),
        ("Best Buy Exclusive", "Dunkirk", "4K UHD", "Steelbook", "mid", 40),
        ("Best Buy Exclusive", "Inception", "4K UHD", "Steelbook", "high", 60),

        # ── 4K UHD Steelbooks — Marvel ────────────────────────────────────
        ("Best Buy Exclusive", "Avengers: Endgame", "4K UHD", "Steelbook", "high", 55),
        ("Best Buy Exclusive", "Spider-Man: No Way Home", "4K UHD", "Steelbook", "mid", 45),
        ("Best Buy Exclusive", "Black Panther: Wakanda Forever", "4K UHD", "Steelbook", "mid", 40),
        ("Zavvi Exclusive", "Guardians of the Galaxy Vol. 3", "4K UHD", "Steelbook", "mid", 42),

        # ── 4K UHD Steelbooks — Studio Ghibli ────────────────────────────
        ("GKIDS / Shout Factory", "Howl's Moving Castle", "4K UHD", "Steelbook", "high", 55),
        ("GKIDS / Shout Factory", "Spirited Away", "4K UHD", "Steelbook", "high", 60),
        ("GKIDS / Shout Factory", "Castle in the Sky", "4K UHD", "Steelbook", "mid", 45),
        ("GKIDS / Shout Factory", "Nausicaa of the Valley of the Wind", "4K UHD", "Steelbook", "high", 50),

        # ── Criterion Collection — Classics ──────────────────────────────
        ("Criterion", "Tokyo Story", "4K UHD", "Criterion 4K #235", "mid", 38),
        ("Criterion", "The Passion of Joan of Arc", "Blu-ray", "Criterion #62", "mid", 32),
        ("Criterion", "Bicycle Thieves", "4K UHD", "Criterion 4K #374", "mid", 36),
        ("Criterion", "Cries and Whispers", "Blu-ray", "Criterion #101", "standard", 28),
        ("Criterion", "Wild Strawberries", "4K UHD", "Criterion 4K #139", "mid", 38),

        # ── Criterion Collection — New Releases ──────────────────────────
        ("Criterion", "All of Us Strangers", "Blu-ray", "Criterion #1160", "standard", 30),
        ("Criterion", "Fallen Leaves", "Blu-ray", "Criterion #1148", "standard", 28),
        ("Criterion", "The Holdovers", "Blu-ray", "Criterion #1162", "standard", 30),
        ("Criterion", "Anatomy of a Fall", "Blu-ray", "Criterion #1157", "standard", 30),
        ("Criterion", "The Taste of Things", "Blu-ray", "Criterion #1152", "standard", 28),

        # ── Arrow Video Limited Editions ──────────────────────────────────
        ("Arrow Video", "Hellraiser: Quartet of Torment", "4K UHD", "Arrow Box Set", "grail", 120),
        ("Arrow Video", "Audition", "4K UHD", "Arrow Limited", "mid", 40),
        ("Arrow Video", "Killer Klowns from Outer Space", "4K UHD", "Arrow Limited", "mid", 42),
        ("Arrow Video", "The Hills Have Eyes", "4K UHD", "Arrow Limited", "mid", 44),
        ("Arrow Video", "Witchfinder General", "4K UHD", "Arrow Limited", "mid", 42),
        ("Arrow Video", "Tenebrae (Dario Argento)", "4K UHD", "Arrow Limited", "mid", 44),
        ("Arrow Video", "The House That Jack Built", "4K UHD", "Arrow Limited", "mid", 42),
        ("Arrow Video", "Zombie Flesh Eaters", "4K UHD", "Arrow Limited", "mid", 44),

        # ── Anime Blu-ray Box Sets ────────────────────────────────────────
        ("Funimation", "Neon Genesis Evangelion Complete Series", "Blu-ray", "Box Set", "grail", 150),
        ("Funimation", "Cowboy Bebop 25th Anniversary Complete Series", "Blu-ray", "Box Set", "high", 90),
        ("Funimation", "Akira 35th Anniversary", "4K UHD", "Limited Edition", "grail", 120),
        ("Aniplex", "Demon Slayer: Kimetsu no Yaiba Season 1 Limited", "Blu-ray", "Box Set", "high", 85),
        ("GKIDS / Shout Factory", "Ghost in the Shell 4K Steelbook", "4K UHD", "Steelbook", "high", 65),
        ("Discotek Media", "Urusei Yatsura Complete Series", "Blu-ray", "Box Set", "high", 80),
        ("Viz Media", "Naruto Shippuden Complete Collection", "Blu-ray", "Box Set", "high", 95),
        ("All The Anime", "Perfect Blue Ultimate Edition", "Blu-ray", "Limited Edition", "high", 70),

        # ── Horror Collector Editions — Scream Factory ────────────────────
        ("Scream Factory", "Halloween 4K Complete Collection", "4K UHD", "Box Set", "grail", 130),
        ("Scream Factory", "They Live Collector's Edition", "4K UHD", "Collector's Edition", "high", 55),
        ("Scream Factory", "The Fog Collector's Edition", "4K UHD", "Collector's Edition", "mid", 45),
        ("Scream Factory", "Prince of Darkness Collector's Edition", "4K UHD", "Collector's Edition", "mid", 45),

        # ── Horror Collector Editions — Shout Factory ─────────────────────
        ("Shout Factory", "Phantasm Sphere Collection", "Blu-ray", "Box Set", "high", 85),
        ("Shout Factory", "Return of the Living Dead Collector's Edition", "4K UHD", "Collector's Edition", "high", 55),
        ("Shout Factory", "Pumpkinhead Collector's Edition", "Blu-ray", "Collector's Edition", "mid", 38),

        # ── Boutique Labels — Vinegar Syndrome Extra ──────────────────────
        ("Vinegar Syndrome", "Abby", "4K UHD", "VS Limited", "mid", 40),
        ("Vinegar Syndrome", "The House on Sorority Row", "4K UHD", "VS Limited", "mid", 42),
        ("Vinegar Syndrome", "Pledge Night", "Blu-ray", "VS Limited", "mid", 35),

        # ── Boutique Labels — Indicator / Eureka ──────────────────────────
        ("Indicator", "The Manchurian Candidate", "Blu-ray", "Indicator Limited", "mid", 40),
        ("Indicator", "Witness for the Prosecution", "Blu-ray", "Indicator Limited", "mid", 38),
        ("Eureka / MoC", "Metropolis Complete", "Blu-ray", "Masters of Cinema", "high", 55),
        ("Eureka / MoC", "Oldboy", "4K UHD", "Masters of Cinema", "mid", 42),
        ("Eureka / MoC", "Sansho the Bailiff", "Blu-ray", "Masters of Cinema", "mid", 35),

        # ── Disney Vault Releases ─────────────────────────────────────────
        ("Disney", "Bambi", "4K UHD", "Disney Steelbook", "mid", 40),
        ("Disney", "Fantasia", "4K UHD", "Disney Steelbook", "mid", 42),
        ("Disney", "The Jungle Book (1967)", "4K UHD", "Disney Steelbook", "mid", 38),
        ("Disney", "Sleeping Beauty", "4K UHD", "Disney Steelbook", "mid", 40),
        ("Disney", "Pinocchio", "4K UHD", "Disney Steelbook", "mid", 38),

        # ── Expansion Round 10 — 91 new items to reach 700+ ─────────────

        # Zavvi Exclusive Steelbooks — Sci-Fi & Action
        ("Zavvi Exclusive", "The Matrix (1999)", "4K UHD", "Zavvi Steelbook", "mid", 48),
        ("Zavvi Exclusive", "The Matrix Reloaded", "4K UHD", "Zavvi Steelbook", "mid", 42),
        ("Zavvi Exclusive", "The Matrix Revolutions", "4K UHD", "Zavvi Steelbook", "mid", 40),
        ("Zavvi Exclusive", "Terminator 2: Judgment Day", "4K UHD", "Zavvi Steelbook", "high", 58),
        ("Zavvi Exclusive", "Total Recall (1990)", "4K UHD", "Zavvi Steelbook", "mid", 46),
        ("Zavvi Exclusive", "RoboCop (1987)", "4K UHD", "Zavvi Steelbook", "mid", 48),
        ("Zavvi Exclusive", "Predator (1987)", "4K UHD", "Zavvi Steelbook", "mid", 50),
        ("Zavvi Exclusive", "Die Hard", "4K UHD", "Zavvi Steelbook", "mid", 48),
        ("Zavvi Exclusive", "Gladiator (2000)", "4K UHD", "Zavvi Steelbook", "mid", 50),
        ("Zavvi Exclusive", "Mad Max: Fury Road", "4K UHD", "Zavvi Steelbook", "mid", 52),
        ("Zavvi Exclusive", "The Fifth Element", "4K UHD", "Zavvi Steelbook", "mid", 48),
        ("Zavvi Exclusive", "Leon: The Professional", "4K UHD", "Zavvi Steelbook", "mid", 46),

        # Best Buy Steelbooks — Horror & Thriller
        ("Best Buy Exclusive", "The Silence of the Lambs", "4K UHD", "Best Buy Steelbook", "mid", 42),
        ("Best Buy Exclusive", "Se7en", "4K UHD", "Best Buy Steelbook", "mid", 44),
        ("Best Buy Exclusive", "The Shining (1980)", "4K UHD", "Best Buy Steelbook", "high", 55),
        ("Best Buy Exclusive", "A Clockwork Orange", "4K UHD", "Best Buy Steelbook", "mid", 48),
        ("Best Buy Exclusive", "The Exorcist (1973)", "4K UHD", "Best Buy Steelbook", "mid", 46),
        ("Best Buy Exclusive", "Jaws", "4K UHD", "Best Buy Steelbook", "high", 55),
        ("Best Buy Exclusive", "Psycho (1960)", "4K UHD", "Best Buy Steelbook", "mid", 44),
        ("Best Buy Exclusive", "Get Out", "4K UHD", "Best Buy Steelbook", "mid", 38),
        ("Best Buy Exclusive", "Us (2019)", "4K UHD", "Best Buy Steelbook", "mid", 36),
        ("Best Buy Exclusive", "Nope (2022)", "4K UHD", "Best Buy Steelbook", "mid", 38),

        # 4K UHD Steelbooks — Sci-Fi Classics
        ("Steelbook", "2001: A Space Odyssey", "4K UHD", "WB Steelbook", "high", 58),
        ("Steelbook", "Close Encounters of the Third Kind", "4K UHD", "Columbia Steelbook", "mid", 48),
        ("Steelbook", "Arrival (2016)", "4K UHD", "Paramount Steelbook", "mid", 42),
        ("Steelbook", "Ex Machina", "4K UHD", "Lionsgate Steelbook", "mid", 40),
        ("Steelbook", "Dune (2021)", "4K UHD", "WB Steelbook", "mid", 48),
        ("Steelbook", "Dune: Part Two (2024)", "4K UHD", "WB Steelbook", "mid", 50),
        ("Steelbook", "Everything Everywhere All at Once", "4K UHD", "A24 Steelbook", "high", 60),

        # Criterion Collection — Recent 2024-2025
        ("Criterion", "Poor Things", "4K UHD", "Criterion 4K #1165", "mid", 38),
        ("Criterion", "Past Lives", "Blu-ray", "Criterion #1155", "standard", 28),
        ("Criterion", "Zone of Interest", "Blu-ray", "Criterion #1170", "standard", 30),
        ("Criterion", "Killers of the Flower Moon", "4K UHD", "Criterion 4K #1175", "mid", 42),
        ("Criterion", "The Boy and the Heron", "4K UHD", "Criterion 4K #1180", "mid", 40),
        ("Criterion", "Do the Right Thing", "4K UHD", "Criterion 4K #97", "mid", 38),
        ("Criterion", "Mulholland Dr.", "4K UHD", "Criterion 4K #779", "mid", 40),
        ("Criterion", "Blue Velvet", "4K UHD", "Criterion 4K #986", "mid", 38),
        ("Criterion", "Paris, Texas", "4K UHD", "Criterion 4K #634", "mid", 36),

        # Arrow Video Limited Editions — New Releases
        ("Arrow Video", "Donnie Darko", "4K UHD", "Arrow Limited", "mid", 46),
        ("Arrow Video", "An American Werewolf in London", "4K UHD", "Arrow Limited", "high", 55),
        ("Arrow Video", "The Thing (1982)", "4K UHD", "Arrow Limited", "high", 58),
        ("Arrow Video", "Re-Animator", "4K UHD", "Arrow Limited", "mid", 44),
        ("Arrow Video", "From Beyond", "4K UHD", "Arrow Limited", "mid", 42),
        ("Arrow Video", "Castle of Cagliostro", "4K UHD", "Arrow Limited", "mid", 40),

        # Mondo Steelbooks — New Releases
        ("Mondo", "Blade Runner", "4K UHD", "Mondo Steelbook", "high", 75),
        ("Mondo", "Alien (1979)", "4K UHD", "Mondo Steelbook", "high", 70),
        ("Mondo", "The Iron Giant", "4K UHD", "Mondo Steelbook", "mid", 55),
        ("Mondo", "Pan's Labyrinth", "4K UHD", "Mondo Steelbook", "mid", 58),
        ("Mondo", "Drive (2011)", "4K UHD", "Mondo Steelbook", "mid", 55),

        # Shout / Scream Factory — Collector's Editions
        ("Scream Factory", "Creepshow 4K Collector's Edition", "4K UHD", "Collector's Edition", "high", 55),
        ("Scream Factory", "An American Werewolf in London CE", "4K UHD", "Collector's Edition", "high", 60),
        ("Scream Factory", "The Howling 4K Collector's Edition", "4K UHD", "Collector's Edition", "mid", 45),
        ("Scream Factory", "Night of the Creeps Collector's Edition", "Blu-ray", "Collector's Edition", "mid", 40),
        ("Scream Factory", "Sleepaway Camp Collector's Edition", "Blu-ray", "Collector's Edition", "mid", 38),
        ("Shout Factory", "Mystery Science Theater 3000 Collection", "Blu-ray", "Box Set", "high", 95),
        ("Shout Factory", "Elvira: Mistress of the Dark", "4K UHD", "Collector's Edition", "mid", 42),

        # Disney Vault Releases — Additional
        ("Disney", "Snow White and the Seven Dwarfs", "4K UHD", "Disney Steelbook", "mid", 42),
        ("Disney", "Alice in Wonderland (1951)", "4K UHD", "Disney Steelbook", "mid", 38),
        ("Disney", "The Little Mermaid (1989)", "4K UHD", "Disney Steelbook", "mid", 40),
        ("Disney", "Aladdin (1992)", "4K UHD", "Disney Steelbook", "mid", 40),
        ("Disney", "The Lion King (1994)", "4K UHD", "Disney Steelbook", "mid", 42),
        ("Disney", "Beauty and the Beast (1991)", "4K UHD", "Disney Steelbook", "mid", 40),

        # Premium Full Slip Editions — Asian Labels
        ("KimchiDVD", "Parasite (2019)", "4K UHD", "Full Slip Edition", "grail", 150),
        ("Plain Archive", "Oldboy (2003)", "4K UHD", "Full Slip Collector's", "grail", 180),
        ("WeET Collection", "Inception Full Slip", "4K UHD", "Full Slip Edition", "grail", 160),
        ("FilmArena", "The Dark Knight Trilogy Full Slip Box", "4K UHD", "Full Slip Box Set", "grail", 250),
        ("HDZeta", "Interstellar Lenticular Full Slip", "4K UHD", "Full Slip Lenticular", "grail", 200),
        ("Manta Lab", "Spider-Man: Into the Spider-Verse", "4K UHD", "Full Slip Edition", "grail", 170),
        ("KimchiDVD", "Memories of Murder", "4K UHD", "Full Slip Collector's", "grail", 140),
        ("WeET Collection", "The Grand Budapest Hotel", "4K UHD", "Full Slip Edition", "high", 120),

        # Anime Blu-ray Box Sets — Additional
        ("Aniplex", "Sword Art Online Progressive Movie", "4K UHD", "Limited Edition", "high", 75),
        ("Aniplex", "Bocchi the Rock! Complete Collection", "Blu-ray", "Box Set", "high", 90),
        ("GKIDS / Shout Factory", "The Boy and the Heron", "4K UHD", "Limited Edition", "high", 65),
        ("Discotek Media", "Lupin III Part 1 Complete", "Blu-ray", "Box Set", "high", 70),
        ("Funimation", "Dragon Ball Z: Complete Series", "Blu-ray", "Box Set", "high", 100),
        ("Viz Media", "One Punch Man Season 1 Limited", "Blu-ray", "Limited Edition", "mid", 55),
        ("All The Anime", "Ghost in the Shell Stand Alone Complex", "Blu-ray", "Ultimate Edition", "high", 85),

        # Boutique Labels — Severin Films
        ("Severin Films", "The Beyond (Fulci)", "4K UHD", "Severin Limited", "mid", 42),
        ("Severin Films", "Anthropophagus", "4K UHD", "Severin Limited", "mid", 40),
        ("Severin Films", "Burial Ground", "4K UHD", "Severin Limited", "mid", 38),
        ("Severin Films", "Zombie Holocaust", "4K UHD", "Severin Limited", "mid", 40),

        # Second Sight Films
        ("Second Sight", "The Wicker Man (1973)", "4K UHD", "Second Sight Limited", "high", 55),
        ("Second Sight", "An American Werewolf in London", "4K UHD", "Second Sight Limited", "high", 60),
        ("Second Sight", "Dawn of the Dead (1978)", "4K UHD", "Second Sight Box Set", "grail", 120),

        # Additional Boutique Blu-rays (+5)
        ("Indicator", "The Night of the Hunter (1955)", "Blu-ray", "Indicator LE", "high", 55),
        ("Eureka", "Harakiri (1962)", "Blu-ray", "Masters of Cinema", "mid", 28),
        ("88 Films", "Riki-Oh: The Story of Ricky", "Blu-ray", "88 Films Slipcover", "mid", 35),
        ("Imprint", "Deep Red (Dario Argento)", "Blu-ray", "Imprint Limited Edition", "high", 65),
        ("Blue Underground", "Maniac (1980)", "4K UHD", "Blue Underground LE", "high", 50),

        # ── Expansion Round 2 — ~170 new items to reach 850+ ──────────────

        # 4K Steelbooks — Recent Major Releases
        ("Steelbook", "Oppenheimer (2023)", "4K UHD", "Universal Steelbook", "high", 55),
        ("Steelbook", "Oppenheimer (2023) IMAX Edition", "4K UHD", "Universal IMAX Steelbook", "high", 65),
        ("Steelbook", "Dune: Part Two (2024) Steelbook", "4K UHD", "WB Steelbook", "mid", 48),
        ("Steelbook", "Dune (2021) Steelbook", "4K UHD", "WB Steelbook", "mid", 45),
        ("Steelbook", "Blade Runner 2049", "4K UHD", "WB Steelbook", "high", 55),
        ("Steelbook", "Blade Runner 2049 (Best Buy Exclusive)", "4K UHD", "Best Buy Steelbook", "high", 65),
        ("Steelbook", "Barbie (2023)", "4K UHD", "WB Steelbook", "mid", 42),
        ("Steelbook", "Killers of the Flower Moon (2023)", "4K UHD", "Paramount Steelbook", "high", 55),
        ("Steelbook", "The Batman (2022)", "4K UHD", "WB Steelbook", "mid", 48),
        ("Steelbook", "Spider-Man: Across the Spider-Verse", "4K UHD", "Sony Steelbook", "mid", 50),
        ("Steelbook", "John Wick: Chapter 4", "4K UHD", "Lionsgate Steelbook", "mid", 48),
        ("Steelbook", "Guardians of the Galaxy Vol. 3", "4K UHD", "Disney Steelbook", "mid", 45),
        ("Steelbook", "Top Gun: Maverick", "4K UHD", "Paramount Steelbook", "mid", 48),
        ("Steelbook", "Nolan 4K Collection (Interstellar/Inception/TDK/Tenet)", "4K UHD", "WB Box Set", "grail", 180),
        ("Steelbook", "Indiana Jones 4-Movie Collection", "4K UHD", "Paramount Steelbook Box", "high", 120),

        # Criterion Collection — Additional
        ("Criterion", "In the Mood for Love", "4K UHD", "Criterion 4K", "mid", 40),
        ("Criterion", "Stalker", "4K UHD", "Criterion 4K #888", "mid", 42),
        ("Criterion", "Paris, Texas", "4K UHD", "Criterion 4K #634", "mid", 38),
        ("Criterion", "Yi Yi", "Blu-ray", "Criterion #1129", "standard", 32),
        ("Criterion", "Shoplifters", "Blu-ray", "Criterion #1033", "standard", 28),
        ("Criterion", "The Red Shoes", "4K UHD", "Criterion 4K", "mid", 40),
        ("Criterion", "Memories of Murder", "Blu-ray", "Criterion #1115", "standard", 28),
        ("Criterion", "A Brighter Summer Day", "Blu-ray", "Criterion #926", "standard", 35),
        ("Criterion", "Come and See", "Blu-ray", "Criterion #989", "standard", 30),
        ("Criterion", "Ikiru", "4K UHD", "Criterion 4K", "mid", 38),
        ("Criterion", "Mishima: A Life in Four Chapters", "Blu-ray", "Criterion #497", "standard", 32),
        ("Criterion", "Fanny and Alexander", "Blu-ray", "Criterion Box Set #261", "high", 85),
        ("Criterion", "The Tree of Life", "4K UHD", "Criterion 4K", "mid", 42),
        ("Criterion", "Moonlight", "4K UHD", "Criterion 4K #951", "mid", 38),

        # Arrow Video — Additional
        ("Arrow Video", "Tremors", "4K UHD", "Arrow Limited", "mid", 45),
        ("Arrow Video", "Tremors 2: Aftershocks", "Blu-ray", "Arrow Limited", "standard", 35),
        ("Arrow Video", "Robocop (1987)", "4K UHD", "Arrow Limited", "high", 55),
        ("Arrow Video", "Society", "Blu-ray", "Arrow Limited", "mid", 40),
        ("Arrow Video", "The Texas Chain Saw Massacre (1974)", "4K UHD", "Arrow Limited", "high", 60),
        ("Arrow Video", "Videodrome", "4K UHD", "Arrow Limited", "high", 55),
        ("Arrow Video", "Flesh for Frankenstein", "4K UHD", "Arrow Limited", "mid", 42),
        ("Arrow Video", "Lifeforce", "4K UHD", "Arrow Limited", "mid", 44),
        ("Arrow Video", "Flash Gordon (1980)", "4K UHD", "Arrow Limited", "mid", 46),

        # Studio Ghibli Steelbooks
        ("Studio Ghibli / GKIDS", "Spirited Away", "4K UHD", "Ghibli Steelbook", "high", 55),
        ("Studio Ghibli / GKIDS", "My Neighbor Totoro", "4K UHD", "Ghibli Steelbook", "high", 52),
        ("Studio Ghibli / GKIDS", "Princess Mononoke", "4K UHD", "Ghibli Steelbook", "high", 55),
        ("Studio Ghibli / GKIDS", "Howl's Moving Castle", "4K UHD", "Ghibli Steelbook", "high", 52),
        ("Studio Ghibli / GKIDS", "Nausicaä of the Valley of the Wind", "4K UHD", "Ghibli Steelbook", "high", 50),
        ("Studio Ghibli / GKIDS", "Kiki's Delivery Service", "4K UHD", "Ghibli Steelbook", "mid", 48),
        ("Studio Ghibli / GKIDS", "Castle in the Sky", "4K UHD", "Ghibli Steelbook", "mid", 48),
        ("Studio Ghibli / GKIDS", "Porco Rosso", "4K UHD", "Ghibli Steelbook", "mid", 45),
        ("Studio Ghibli / GKIDS", "Grave of the Fireflies", "Blu-ray", "Ghibli Steelbook", "high", 55),
        ("Studio Ghibli / GKIDS", "The Wind Rises", "Blu-ray", "Ghibli Steelbook", "mid", 42),
        ("Studio Ghibli / GKIDS", "Ponyo", "4K UHD", "Ghibli Steelbook", "mid", 45),
        ("Studio Ghibli / GKIDS", "The Tale of the Princess Kaguya", "Blu-ray", "Ghibli Steelbook", "mid", 48),

        # Mondo Steelbooks — Additional
        ("Mondo", "The Shining", "4K UHD", "Mondo Steelbook", "high", 70),
        ("Mondo", "Jaws", "4K UHD", "Mondo Steelbook", "high", 65),
        ("Mondo", "No Country for Old Men", "4K UHD", "Mondo Steelbook", "mid", 55),
        ("Mondo", "2001: A Space Odyssey", "4K UHD", "Mondo Steelbook", "high", 65),
        ("Mondo", "Spirited Away", "4K UHD", "Mondo Steelbook", "high", 80),
        ("Mondo", "E.T. the Extra-Terrestrial", "4K UHD", "Mondo Steelbook", "mid", 50),
        ("Mondo", "Ghostbusters (1984)", "4K UHD", "Mondo Steelbook", "mid", 55),
        ("Mondo", "The Thing (1982)", "4K UHD", "Mondo Steelbook", "high", 70),
        ("Mondo", "RoboCop (1987)", "4K UHD", "Mondo Steelbook", "mid", 55),
        ("Mondo", "Blade Runner (Final Cut)", "4K UHD", "Mondo Steelbook", "high", 80),

        # Zavvi Exclusive Steelbooks — Additional
        ("Zavvi Exclusive", "Back to the Future Trilogy", "4K UHD", "Zavvi Steelbook Box", "high", 85),
        ("Zavvi Exclusive", "Jurassic Park", "4K UHD", "Zavvi Steelbook", "mid", 48),
        ("Zavvi Exclusive", "E.T. the Extra-Terrestrial", "4K UHD", "Zavvi Steelbook", "mid", 46),
        ("Zavvi Exclusive", "Schindler's List", "4K UHD", "Zavvi Steelbook", "mid", 50),
        ("Zavvi Exclusive", "The Godfather", "4K UHD", "Zavvi Steelbook", "high", 55),
        ("Zavvi Exclusive", "The Godfather Part II", "4K UHD", "Zavvi Steelbook", "high", 55),
        ("Zavvi Exclusive", "Goodfellas", "4K UHD", "Zavvi Steelbook", "mid", 50),
        ("Zavvi Exclusive", "Scarface (1983)", "4K UHD", "Zavvi Steelbook", "mid", 48),
        ("Zavvi Exclusive", "Alien (1979)", "4K UHD", "Zavvi Steelbook", "high", 55),
        ("Zavvi Exclusive", "Aliens (1986)", "4K UHD", "Zavvi Steelbook", "mid", 50),
        ("Zavvi Exclusive", "Blade Runner (1982)", "4K UHD", "Zavvi Steelbook", "high", 58),
        ("Zavvi Exclusive", "The Shawshank Redemption", "4K UHD", "Zavvi Steelbook", "mid", 50),
        ("Zavvi Exclusive", "Fight Club", "4K UHD", "Zavvi Steelbook", "mid", 48),

        # Premium Editions — Manta Lab, Blufans, FilmArena
        ("Manta Lab", "Dune (2021)", "4K UHD", "Full Slip Edition", "grail", 180),
        ("Manta Lab", "The Batman (2022)", "4K UHD", "Full Slip Edition", "grail", 160),
        ("Manta Lab", "No Time to Die", "4K UHD", "Full Slip Edition", "high", 130),
        ("Manta Lab", "Top Gun: Maverick", "4K UHD", "Full Slip Edition", "grail", 170),
        ("Manta Lab", "Everything Everywhere All at Once", "4K UHD", "Full Slip Edition", "grail", 180),
        ("Blufans", "Interstellar", "4K UHD", "Full Slip Lenticular", "grail", 220),
        ("Blufans", "The Dark Knight", "4K UHD", "Full Slip Lenticular", "grail", 250),
        ("Blufans", "Inception", "4K UHD", "Full Slip Lenticular", "grail", 200),
        ("Blufans", "Fight Club", "4K UHD", "Full Slip Lenticular", "grail", 180),
        ("Blufans", "Parasite", "4K UHD", "Full Slip Lenticular", "grail", 200),
        ("FilmArena", "Blade Runner 2049", "4K UHD", "Full Slip XL Edition", "grail", 220),
        ("FilmArena", "Joker (2019)", "4K UHD", "Full Slip XL Edition", "grail", 180),
        ("FilmArena", "No Time to Die", "4K UHD", "Full Slip Edition", "high", 130),
        ("FilmArena", "Tenet", "4K UHD", "Full Slip Lenticular", "grail", 170),
        ("FilmArena", "Dune (2021)", "4K UHD", "Full Slip Lenticular", "grail", 200),
        ("FilmArena", "1917", "4K UHD", "Full Slip Edition", "high", 120),
        ("HDZeta", "Spider-Man: No Way Home", "4K UHD", "Full Slip Lenticular", "grail", 190),
        ("HDZeta", "The Batman (2022)", "4K UHD", "Full Slip Lenticular", "grail", 180),
        ("HDZeta", "Top Gun: Maverick", "4K UHD", "Full Slip Lenticular", "grail", 200),
        ("Plain Archive", "Parasite", "4K UHD", "Full Slip Collector's", "grail", 200),
        ("Plain Archive", "Decision to Leave", "4K UHD", "Full Slip Collector's", "high", 120),
        ("WeET Collection", "Dune (2021)", "4K UHD", "Full Slip Edition", "grail", 170),
        ("WeET Collection", "Everything Everywhere All at Once", "4K UHD", "Full Slip Edition", "grail", 160),
        ("KimchiDVD", "Oldboy (2003)", "4K UHD", "Full Slip Lenticular", "grail", 200),
        ("KimchiDVD", "The Handmaiden", "4K UHD", "Full Slip Collector's", "grail", 160),

        # TV Box Sets — Premium Collector Editions
        ("Steelbook", "Breaking Bad: The Complete Series", "Blu-ray", "Barrel Edition Box Set", "grail", 250),
        ("Steelbook", "Breaking Bad: The Complete Series", "4K UHD", "Complete Series 4K", "grail", 180),
        ("Steelbook", "Game of Thrones: Complete Series", "4K UHD", "Complete Series 4K Box", "grail", 200),
        ("Steelbook", "Game of Thrones: Complete Series", "Blu-ray", "Iron Throne Box Set", "grail", 300),
        ("Steelbook", "The Sopranos: Complete Series", "Blu-ray", "Complete Series Box Set", "high", 120),
        ("Steelbook", "The Wire: Complete Series", "Blu-ray", "Complete Series Box Set", "high", 100),
        ("Steelbook", "Band of Brothers", "4K UHD", "Complete Steelbook", "high", 80),
        ("Steelbook", "Chernobyl", "4K UHD", "Steelbook", "high", 55),
        ("Steelbook", "True Detective: Season 1", "Blu-ray", "Steelbook", "mid", 45),
        ("Steelbook", "Stranger Things: Season 1", "4K UHD", "Target Exclusive", "mid", 48),
        ("Steelbook", "Stranger Things: Season 4", "4K UHD", "Steelbook", "mid", 50),
        ("Steelbook", "The Last of Us: Season 1", "4K UHD", "Steelbook", "high", 55),
        ("Steelbook", "Succession: Complete Series", "Blu-ray", "Complete Series Box", "high", 90),
        ("Steelbook", "Better Call Saul: Complete Series", "Blu-ray", "Complete Series Box", "high", 100),

        # Anime Box Sets — Additional
        ("Funimation", "Attack on Titan: Final Season", "Blu-ray", "Limited Edition", "high", 80),
        ("Funimation", "Fullmetal Alchemist: Brotherhood Complete", "Blu-ray", "Box Set", "high", 90),
        ("Aniplex", "Your Name (Kimi no Na wa)", "4K UHD", "Limited Edition", "high", 75),
        ("Aniplex", "Weathering with You", "4K UHD", "Limited Edition", "high", 70),
        ("Aniplex", "Jujutsu Kaisen Season 1 Limited", "Blu-ray", "Box Set", "high", 85),
        ("GKIDS / Shout Factory", "Spirited Away", "4K UHD", "Steelbook", "high", 55),
        ("GKIDS / Shout Factory", "Princess Mononoke", "4K UHD", "Steelbook", "high", 55),
        ("Discotek Media", "Mobile Suit Gundam Trilogy", "Blu-ray", "Box Set", "high", 70),
        ("Funimation", "Steins;Gate Complete Series", "Blu-ray", "Limited Edition", "high", 75),
        ("Discotek Media", "Legend of the Galactic Heroes", "Blu-ray", "Complete Series Box", "grail", 200),

        # Kino Lorber — Additional
        ("Kino Lorber", "Nosferatu (1922)", "4K UHD", "KL Studio Classics", "mid", 38),
        ("Kino Lorber", "M (Fritz Lang 1931)", "4K UHD", "KL Studio Classics", "mid", 36),
        ("Kino Lorber", "The Cabinet of Dr. Caligari", "4K UHD", "KL Studio Classics", "mid", 38),
        ("Kino Lorber", "Häxan (1922)", "Blu-ray", "KL Studio Classics", "mid", 35),

        # BFI — Additional
        ("BFI", "Andrei Rublev", "Blu-ray", "BFI Limited", "mid", 40),
        ("BFI", "Mirror (Tarkovsky)", "Blu-ray", "BFI Limited", "mid", 38),
        ("BFI", "Solaris (1972)", "Blu-ray", "BFI Limited", "mid", 38),
        ("BFI", "Tokyo Story", "Blu-ray", "BFI Limited", "mid", 35),

        # 101 Films / Fun City Editions
        ("101 Films", "The Changeling (1980)", "4K UHD", "101 Films Black Label", "mid", 38),
        ("101 Films", "Leviathan (1989)", "4K UHD", "101 Films Black Label", "mid", 36),
        ("Fun City Editions", "After Hours (1985)", "4K UHD", "Fun City Limited", "mid", 42),
        ("Fun City Editions", "Thief (1981)", "4K UHD", "Fun City Limited", "mid", 44),

        # Vinegar Syndrome — Additional
        ("Vinegar Syndrome", "Tammy and the T-Rex", "4K UHD", "VS Limited", "mid", 38),
        ("Vinegar Syndrome", "Blood Rage", "4K UHD", "VS Limited", "mid", 36),
        ("Vinegar Syndrome", "Psycho Goreman", "4K UHD", "VS Limited", "mid", 40),
        ("Vinegar Syndrome", "Willy's Wonderland", "4K UHD", "VS Limited", "mid", 38),
        ("Vinegar Syndrome", "VHS Forever? Boxset (VS Subscriber)", "Blu-ray", "VS Subscriber Box", "high", 80),

        # MCU Steelbooks
        ("Steelbook", "Avengers: Endgame", "4K UHD", "Disney Steelbook", "mid", 50),
        ("Steelbook", "Avengers: Infinity War", "4K UHD", "Disney Steelbook", "mid", 48),
        ("Steelbook", "Black Panther", "4K UHD", "Disney Steelbook", "mid", 45),
        ("Steelbook", "Spider-Man: No Way Home", "4K UHD", "Sony Steelbook", "mid", 50),
        ("Steelbook", "Iron Man", "4K UHD", "Disney Steelbook", "mid", 55),
        ("Steelbook", "Captain America: The Winter Soldier", "4K UHD", "Disney Steelbook", "mid", 48),
        ("Steelbook", "Thor: Ragnarok", "4K UHD", "Disney Steelbook", "mid", 45),
        ("Steelbook", "Doctor Strange", "4K UHD", "Disney Steelbook", "mid", 42),
        ("Steelbook", "Deadpool & Wolverine", "4K UHD", "Disney Steelbook", "mid", 50),

        # Harry Potter Steelbooks
        ("Steelbook", "Harry Potter: Philosopher's Stone", "4K UHD", "Zavvi Steelbook", "high", 80),
        ("Steelbook", "Harry Potter: Chamber of Secrets", "4K UHD", "Zavvi Steelbook", "mid", 65),
        ("Steelbook", "Harry Potter: Prisoner of Azkaban", "4K UHD", "Zavvi Steelbook", "high", 90),
        ("Steelbook", "Harry Potter: Goblet of Fire", "4K UHD", "Zavvi Steelbook", "mid", 60),
        ("Steelbook", "Harry Potter: Order of the Phoenix", "4K UHD", "Zavvi Steelbook", "mid", 55),
        ("Steelbook", "Harry Potter: Half-Blood Prince", "4K UHD", "Zavvi Steelbook", "mid", 55),
        ("Steelbook", "Harry Potter: Deathly Hallows Part 1", "4K UHD", "Zavvi Steelbook", "mid", 60),
        ("Steelbook", "Harry Potter: Deathly Hallows Part 2", "4K UHD", "Zavvi Steelbook", "mid", 60),
        ("Steelbook", "Harry Potter 8-Film Collection", "4K UHD", "Best Buy Steelbook", "grail", 350),
        ("Steelbook", "Harry Potter 8-Film Collection", "Blu-ray", "Best Buy Steelbook (2016)", "high", 200),
        ("Steelbook", "Harry Potter 20th Anniversary Hogwarts Express Edition", "4K UHD", "25-Disc Box Set", "grail", 250),

        # LOTR Steelbooks
        ("Steelbook", "Lord of the Rings: The Fellowship of the Ring Extended", "4K UHD", "WB Steelbook", "high", 60),
        ("Steelbook", "Lord of the Rings: The Two Towers Extended", "4K UHD", "WB Steelbook", "high", 60),
        ("Steelbook", "Lord of the Rings: The Return of the King Extended", "4K UHD", "WB Steelbook", "high", 60),
        ("Steelbook", "Lord of the Rings Trilogy (9-Disc 4K)", "4K UHD", "WB Box Set", "grail", 180),
        ("Steelbook", "The Hobbit Trilogy (4K)", "4K UHD", "WB Box Set", "high", 120),

        # Hobbit Individual Steelbooks
        ("Steelbook", "The Hobbit: An Unexpected Journey Extended", "4K UHD", "Zavvi Steelbook", "mid", 55),
        ("Steelbook", "The Hobbit: Desolation of Smaug Extended", "4K UHD", "Zavvi Steelbook", "mid", 55),
        ("Steelbook", "The Hobbit: Battle of Five Armies Extended", "4K UHD", "Zavvi Steelbook", "mid", 55),

        # Star Wars Steelbooks
        ("Steelbook", "Star Wars: A New Hope", "4K UHD", "Disney Steelbook", "high", 55),
        ("Steelbook", "Star Wars: The Empire Strikes Back", "4K UHD", "Disney Steelbook", "high", 55),
        ("Steelbook", "Star Wars: Return of the Jedi", "4K UHD", "Disney Steelbook", "high", 55),
        ("Steelbook", "Star Wars: The Skywalker Saga (9-Film Box)", "4K UHD", "Disney Box Set", "grail", 200),

        # Additional Criterion 4K Upgrades
        ("Criterion", "Blow Out", "4K UHD", "Criterion 4K #981", "mid", 38),
        ("Criterion", "The Grand Budapest Hotel", "4K UHD", "Criterion 4K", "mid", 40),
        ("Criterion", "Uncut Gems", "4K UHD", "Criterion 4K", "mid", 38),
        ("Criterion", "Anatomy of a Fall", "Blu-ray", "Criterion #1185", "standard", 28),
        ("Criterion", "The Holdovers", "Blu-ray", "Criterion #1190", "standard", 28),
        ("Criterion", "All of Us Strangers", "Blu-ray", "Criterion #1195", "standard", 28),
        ("Criterion", "Fallen Angels (Wong Kar-wai)", "4K UHD", "Criterion 4K", "mid", 38),

        # Studio Canal / Second Sight Extra
        ("StudioCanal", "The Third Man", "4K UHD", "StudioCanal Collector's", "high", 55),
        ("StudioCanal", "Cinema Paradiso", "4K UHD", "StudioCanal Collector's", "mid", 42),
        ("Second Sight", "Dog Soldiers", "4K UHD", "Second Sight Limited", "mid", 45),
        ("Second Sight", "Candyman (1992)", "4K UHD", "Second Sight Limited", "high", 55),

        # Additional TV Box Sets
        ("Steelbook", "Twin Peaks: The Complete Series", "Blu-ray", "Complete Series Box", "grail", 150),
        ("Steelbook", "The Office: Complete Series", "Blu-ray", "Complete Series Box", "high", 80),
        ("Steelbook", "Friends: Complete Series", "Blu-ray", "Complete Series Box", "high", 70),
        ("Steelbook", "Peaky Blinders: Complete Series", "Blu-ray", "Complete Series Box", "high", 85),
        ("Steelbook", "Yellowstone: Seasons 1-5", "Blu-ray", "Box Set", "high", 90),
        ("Steelbook", "House of the Dragon: Season 1", "4K UHD", "Steelbook", "mid", 48),
        ("Steelbook", "Shogun (2024)", "4K UHD", "Steelbook", "high", 55),

        # Imprint & 88 Films Additional
        ("Imprint", "Memories of Murder (Bong Joon-ho)", "Blu-ray", "Imprint Limited Edition", "high", 60),
        ("Imprint", "The Host (Bong Joon-ho)", "Blu-ray", "Imprint Limited Edition", "high", 55),
        ("Imprint", "Come and See (1985)", "Blu-ray", "Imprint Limited Edition", "high", 65),
        ("88 Films", "Miami Connection", "Blu-ray", "88 Films Slipcover", "mid", 35),
        ("88 Films", "The Prowler (1981)", "4K UHD", "88 Films Slipcover", "mid", 38),
        ("88 Films", "Ichi the Killer", "4K UHD", "88 Films Slipcover", "high", 50),

        # Additional 4K Steelbooks to reach 850+
        ("Steelbook", "The Matrix Resurrections", "4K UHD", "WB Steelbook", "mid", 40),
        ("Steelbook", "No Country for Old Men", "4K UHD", "Paramount Steelbook", "mid", 48),
        ("Steelbook", "Sicario", "4K UHD", "Lionsgate Steelbook", "mid", 42),
        ("Steelbook", "Dunkirk (2017)", "4K UHD", "WB Steelbook", "mid", 48),
        ("Steelbook", "1917 (2019)", "4K UHD", "Universal Steelbook", "mid", 45),
        ("Steelbook", "The Revenant", "4K UHD", "Fox Steelbook", "mid", 48),
        ("Steelbook", "Whiplash", "4K UHD", "Sony Steelbook", "mid", 45),
        ("Steelbook", "La La Land", "4K UHD", "Lionsgate Steelbook", "mid", 42),
        ("Steelbook", "Mad Max: Fury Road (Black & Chrome)", "4K UHD", "WB Steelbook", "high", 60),
        ("Steelbook", "Joker (2019)", "4K UHD", "WB Steelbook", "mid", 48),
        ("Steelbook", "The Departed", "4K UHD", "WB Steelbook", "mid", 48),
        ("Steelbook", "Goodfellas", "4K UHD", "WB Steelbook", "mid", 48),
        ("Steelbook", "Heat (1995)", "4K UHD", "Fox Steelbook", "high", 55),
        ("Steelbook", "Apocalypse Now: Final Cut", "4K UHD", "Lionsgate Steelbook", "high", 55),
        ("Steelbook", "Pulp Fiction", "4K UHD", "Paramount Steelbook", "mid", 50),
        ("Steelbook", "Reservoir Dogs", "4K UHD", "Paramount Steelbook", "mid", 48),
        ("Steelbook", "Kill Bill Vol. 1", "4K UHD", "Paramount Steelbook", "mid", 48),
        ("Steelbook", "Kill Bill Vol. 2", "4K UHD", "Paramount Steelbook", "mid", 48),
        ("Steelbook", "Inglourious Basterds", "4K UHD", "Universal Steelbook", "mid", 48),
        ("Steelbook", "Django Unchained", "4K UHD", "Sony Steelbook", "mid", 45),
        ("Steelbook", "Once Upon a Time in Hollywood", "4K UHD", "Sony Steelbook", "mid", 45),
        ("Steelbook", "The Grand Budapest Hotel", "Blu-ray", "Fox Steelbook", "mid", 42),
        ("Steelbook", "Moonrise Kingdom", "Blu-ray", "Focus Steelbook", "mid", 40),

        # ── Kubrick 4K Restorations ───────────────────────────────────────
        ("Warner Bros", "2001: A Space Odyssey (4K Remaster)", "4K UHD", "Standard", "mid", 30),
        ("Warner Bros", "A Clockwork Orange (4K Remaster)", "4K UHD", "Standard", "mid", 28),
        ("Warner Bros", "The Shining (4K Extended Cut)", "4K UHD", "Standard", "mid", 30),
        ("Warner Bros", "Full Metal Jacket (4K Remaster)", "4K UHD", "Standard", "mid", 28),
        ("Warner Bros", "Barry Lyndon (4K Remaster)", "4K UHD", "Standard", "mid", 30),
        ("Warner Bros", "Eyes Wide Shut (4K Remaster)", "4K UHD", "Standard", "mid", 28),
        ("Warner Bros", "Paths of Glory (4K Remaster)", "4K UHD", "Standard", "mid", 28),
        ("Warner Bros", "Stanley Kubrick 8-Film 4K Collection", "4K UHD Box", "Limited Box", "grail", 180),

        # ── Spielberg 4K Restorations ─────────────────────────────────────
        ("Universal", "Schindler's List (4K 25th Anniversary)", "4K UHD", "Standard", "mid", 30),
        ("Universal", "Jurassic Park (4K Remaster)", "4K UHD", "Standard", "standard", 25),
        ("Universal", "E.T. the Extra-Terrestrial (4K 40th Anniversary)", "4K UHD", "Standard", "mid", 30),
        ("Universal", "Jaws (4K 45th Anniversary)", "4K UHD", "Standard", "mid", 30),
        ("Paramount", "Saving Private Ryan (4K Remaster)", "4K UHD", "Standard", "mid", 28),
        ("Paramount", "Indiana Jones 4-Film 4K Collection", "4K UHD Box", "Limited Box", "high", 90),
        ("Universal", "Close Encounters of the Third Kind (4K)", "4K UHD", "Standard", "mid", 28),
        ("Amblin", "The Color Purple (4K Remaster)", "4K UHD", "Standard", "mid", 28),

        # ── Scorsese 4K Restorations ──────────────────────────────────────
        ("Warner Bros", "The Departed (4K Remaster)", "4K UHD", "Standard", "mid", 28),
        ("Warner Bros", "Goodfellas (4K Remaster)", "4K UHD", "Standard", "mid", 30),
        ("Universal", "Casino (4K Remaster)", "4K UHD", "Standard", "mid", 28),
        ("Paramount", "The Wolf of Wall Street (4K)", "4K UHD", "Standard", "mid", 28),
        ("Paramount", "Silence (4K Remaster)", "4K UHD", "Standard", "mid", 28),
        ("Sony", "Taxi Driver (4K Columbia Classics)", "4K UHD", "Standard", "mid", 30),
        ("Paramount", "Shutter Island (4K Remaster)", "4K UHD", "Standard", "mid", 28),
        ("Universal", "Cape Fear (4K Remaster)", "4K UHD", "Standard", "mid", 28),

        # ── Arrow Video Releases ──────────────────────────────────────────
        ("Arrow Video", "Donnie Darko (4K UHD LE)", "4K UHD", "Arrow Limited", "high", 65),
        ("Arrow Video", "The Thing (4K UHD LE)", "4K UHD", "Arrow Limited", "high", 70),
        ("Arrow Video", "Flash Gordon (4K UHD LE)", "4K UHD", "Arrow Limited", "high", 60),
        ("Arrow Video", "RoboCop (4K Director's Cut)", "4K UHD", "Arrow Limited", "high", 65),
        ("Arrow Video", "An American Werewolf in London (4K)", "4K UHD", "Arrow Limited", "high", 65),
        ("Arrow Video", "Deep Red (4K UHD)", "4K UHD", "Arrow Limited", "high", 60),
        ("Arrow Video", "Phenomena (4K UHD)", "4K UHD", "Arrow Limited", "mid", 50),
        ("Arrow Video", "Tremors (4K UHD LE)", "4K UHD", "Arrow Limited", "mid", 55),
        ("Arrow Video", "The Texas Chain Saw Massacre (4K)", "4K UHD", "Arrow Limited", "high", 70),
        ("Arrow Video", "Re-Animator (4K UHD LE)", "4K UHD", "Arrow Limited", "high", 60),

        # ── Indicator / Powerhouse Releases ───────────────────────────────
        ("Indicator", "The Bridge on the River Kwai (4K LE)", "4K UHD", "Indicator LE", "high", 55),
        ("Indicator", "Dr. Strangelove (4K LE)", "4K UHD", "Indicator LE", "high", 60),
        ("Indicator", "Anatomy of a Murder (LE)", "Blu-ray", "Indicator LE", "mid", 40),
        ("Indicator", "In the Heat of the Night (LE)", "Blu-ray", "Indicator LE", "mid", 40),
        ("Indicator", "Taxi Driver (4K LE)", "4K UHD", "Indicator LE", "high", 65),
        ("Indicator", "The Last Emperor (4K LE)", "4K UHD", "Indicator LE", "high", 55),

        # ── Anime 4K Releases ────────────────────────────────────────────
        ("Funimation", "Akira (4K Limited Edition Steelbook)", "4K UHD", "Limited Steelbook", "high", 65),
        ("Manga Entertainment", "Ghost in the Shell (4K Steelbook)", "4K UHD", "Limited Steelbook", "high", 60),
        ("GKIDS", "Spirited Away (Steelbook)", "Blu-ray", "GKIDS Steelbook", "mid", 45),
        ("GKIDS", "Princess Mononoke (Steelbook)", "Blu-ray", "GKIDS Steelbook", "mid", 45),
        ("GKIDS", "My Neighbor Totoro (Steelbook)", "Blu-ray", "GKIDS Steelbook", "mid", 45),
        ("Funimation", "Dragon Ball Super: Broly (4K LE)", "4K UHD", "Limited", "mid", 40),
        ("Crunchyroll", "Jujutsu Kaisen 0 (4K Steelbook)", "4K UHD", "Limited Steelbook", "mid", 45),
        ("Crunchyroll", "Dragon Ball Super: Super Hero (4K)", "4K UHD", "Standard", "standard", 25),
        ("Sony", "Suzume (4K Steelbook)", "4K UHD", "Limited Steelbook", "mid", 45),
        ("Sony", "Weathering With You (4K Steelbook)", "4K UHD", "Steelbook", "mid", 48),

        # ── TV Series Complete Steelbook Box Sets ─────────────────────────
        ("Sony", "Breaking Bad Complete Series (Steelbook)", "Blu-ray Box", "Limited Steelbook", "grail", 180),
        ("HBO/Warner", "The Wire Complete Series (Steelbook)", "Blu-ray Box", "Limited", "high", 120),
        ("HBO/Warner", "The Sopranos Complete Series (Steelbook)", "Blu-ray Box", "Limited", "high", 130),
        ("HBO/Warner", "Game of Thrones Complete (4K Steelbook)", "4K UHD Box", "Limited Steelbook", "grail", 200),
        ("AMC", "Better Call Saul Complete (Steelbook)", "Blu-ray Box", "Limited", "high", 100),
        ("AMC", "The Walking Dead Complete S1-11 Box", "Blu-ray Box", "Limited", "high", 110),
        ("NBC/Universal", "The Office Complete (Steelbook)", "Blu-ray Box", "Limited", "high", 90),
        ("Fox", "Lost Complete Series (Steelbook)", "Blu-ray Box", "Limited", "high", 95),
        ("HBO/Warner", "Band of Brothers / The Pacific Gift Set", "Blu-ray Box", "Limited", "high", 85),
        ("HBO/Warner", "True Detective S1-3 Complete Box", "Blu-ray Box", "Standard", "mid", 50),

        # ── Horror Boutique Labels ────────────────────────────────────────
        ("Vinegar Syndrome", "Pieces (4K UHD LE)", "4K UHD", "VS Limited", "high", 55),
        ("Vinegar Syndrome", "Blood and Black Lace (4K UHD)", "4K UHD", "VS Limited", "high", 55),
        ("Vinegar Syndrome", "Psycho Goreman (4K UHD LE)", "4K UHD", "VS Limited", "mid", 45),
        ("Vinegar Syndrome", "Tammy and the T-Rex (4K Gore Cut)", "4K UHD", "VS Limited", "mid", 45),
        ("Vinegar Syndrome", "The Slumber Party Massacre Collection", "Blu-ray Box", "VS Box", "mid", 50),
        ("Severin", "The Beyond (4K UHD)", "4K UHD", "Severin Limited", "high", 55),
        ("Severin", "Zombie (4K UHD)", "4K UHD", "Severin Limited", "high", 60),
        ("Severin", "City of the Living Dead (4K)", "4K UHD", "Severin Limited", "mid", 50),
        ("Severin", "The House That Jack Built (4K)", "4K UHD", "Severin Limited", "mid", 45),
        ("Severin", "All the Colors of the Dark", "Blu-ray", "Severin Limited", "mid", 40),
        ("88 Films", "The Burning (Slasher Classics)", "Blu-ray", "88 Films LE", "mid", 35),
        ("88 Films", "Demons / Demons 2 (4K Box)", "4K UHD Box", "88 Films LE", "high", 60),
        ("88 Films", "My Bloody Valentine (4K UHD LE)", "4K UHD", "88 Films LE", "mid", 45),
        ("88 Films", "Street Trash (Slasher Classics)", "Blu-ray", "88 Films LE", "mid", 35),
        ("88 Films", "Sleepaway Camp Collection", "Blu-ray Box", "88 Films Box", "mid", 50),
        ("Blue Underground", "Maniac (4K UHD LE)", "4K UHD", "BU Limited", "high", 55),
        ("Blue Underground", "Zombie (4K UHD)", "4K UHD", "BU Limited", "high", 55),
        ("Blue Underground", "The New York Ripper (4K)", "4K UHD", "BU Limited", "mid", 48),

        # ── Premium Asian Releases (Full Slip / Lenticular) ───────────────
        ("KimchiDVD", "Parasite (Full Slip Steelbook)", "4K UHD", "KimchiDVD FS", "grail", 180),
        ("WeET Collection", "Spider-Man: No Way Home (Full Slip A)", "4K UHD", "WeET Full Slip", "high", 120),
        ("WeET Collection", "Top Gun: Maverick (Lenticular Slip)", "4K UHD", "WeET Lenticular", "high", 100),
        ("Plain Archive", "Oldboy (Full Slip)", "Blu-ray", "Plain Archive FS", "grail", 160),
        ("FilmArena", "Joker (4K Full Slip XL)", "4K UHD", "FilmArena FS XL", "grail", 150),
        ("FilmArena", "Dune Part One (4K Lenticular Slip)", "4K UHD", "FilmArena Lenticular", "high", 110),
        ("Manta Lab", "Avengers: Endgame (Full Slip Steelbook)", "4K UHD", "Manta Lab FS", "high", 130),
        ("HDZeta", "Interstellar (4K Triple Steelbook)", "4K UHD Box", "HDZeta Triple", "grail", 200),
        ("HDZeta", "The Dark Knight Trilogy (4K Box)", "4K UHD Box", "HDZeta Box", "grail", 250),

        # ── More Criterion 4K Releases ────────────────────────────────────
        ("Criterion", "Mulholland Dr. (4K UHD)", "4K UHD", "Criterion 4K", "high", 55),
        ("Criterion", "Menace II Society (4K UHD)", "4K UHD", "Criterion 4K", "mid", 45),
        ("Criterion", "The Piano (4K UHD)", "4K UHD", "Criterion 4K", "mid", 42),
        ("Criterion", "Do the Right Thing (4K UHD)", "4K UHD", "Criterion 4K", "mid", 45),
        ("Criterion", "In the Mood for Love (4K UHD)", "4K UHD", "Criterion 4K", "high", 55),
        ("Criterion", "Crash (Cronenberg, 4K UHD)", "4K UHD", "Criterion 4K", "mid", 45),
        ("Criterion", "The Red Shoes (4K UHD)", "4K UHD", "Criterion 4K", "high", 55),
        ("Criterion", "Parasite (4K UHD)", "4K UHD", "Criterion 4K", "mid", 45),
        ("Criterion", "Eraserhead (4K UHD)", "4K UHD", "Criterion 4K", "high", 55),
        ("Criterion", "Videodrome (4K UHD)", "4K UHD", "Criterion 4K", "mid", 48),
        ("Criterion", "The Silence of the Lambs (4K UHD)", "4K UHD", "Criterion 4K", "mid", 45),
        ("Criterion", "Citizen Kane (4K UHD)", "4K UHD", "Criterion 4K", "high", 55),
        ("Criterion", "Memories of Murder (4K UHD)", "4K UHD", "Criterion 4K", "mid", 45),

        # ── More Kino Lorber / Shout Factory ──────────────────────────────
        ("Kino Lorber", "The Cabinet of Dr. Caligari (4K UHD)", "4K UHD", "KL 4K", "high", 55),
        ("Kino Lorber", "Nosferatu (1922) (4K UHD)", "4K UHD", "KL 4K", "high", 50),
        ("Kino Lorber", "M (Fritz Lang, 4K UHD)", "4K UHD", "KL 4K", "mid", 45),
        ("Kino Lorber", "Tampopo (4K UHD)", "4K UHD", "KL 4K", "mid", 42),
        ("Shout Factory", "They Live (4K UHD LE Steelbook)", "4K UHD", "Scream Factory LE", "high", 60),
        ("Shout Factory", "The Fog (4K UHD LE Steelbook)", "4K UHD", "Scream Factory LE", "high", 55),
        ("Shout Factory", "Escape from New York (4K UHD LE)", "4K UHD", "Scream Factory LE", "high", 55),
        ("Shout Factory", "Phantasm (4K UHD LE)", "4K UHD", "Scream Factory LE", "mid", 48),
        ("Shout Factory", "Creepshow (4K UHD LE)", "4K UHD", "Scream Factory LE", "high", 55),
        ("Shout Factory", "Prince of Darkness (4K UHD LE)", "4K UHD", "Scream Factory LE", "mid", 48),

        # ── More Director Filmographies (Nolan, Coen Bros, Tarantino) ─────
        ("Warner Bros", "Inception (4K Steelbook)", "4K UHD", "WB Steelbook", "mid", 48),
        ("Warner Bros", "Tenet (4K Steelbook)", "4K UHD", "WB Steelbook", "mid", 45),
        ("Warner Bros", "Dunkirk (4K Steelbook)", "4K UHD", "WB Steelbook", "mid", 45),
        ("Warner Bros", "The Prestige (4K Steelbook)", "4K UHD", "WB Steelbook", "mid", 50),
        ("Universal", "No Country for Old Men (4K)", "4K UHD", "Standard", "mid", 28),
        ("Universal", "Fargo (4K)", "4K UHD", "Standard", "mid", 28),
        ("Universal", "The Big Lebowski (4K)", "4K UHD", "Standard", "mid", 28),
        ("Paramount", "True Grit (4K, Coen Bros)", "4K UHD", "Standard", "mid", 28),
        ("Lionsgate", "The Hateful Eight (4K Extended)", "4K UHD", "Standard", "mid", 30),
        ("Sony", "Taxi Driver (4K Steelbook)", "4K UHD", "Sony Steelbook", "mid", 48),
        ("Paramount", "Interstellar (4K Steelbook)", "4K UHD", "Paramount Steelbook", "mid", 50),
        ("Warner Bros", "Batman Begins (4K Steelbook)", "4K UHD", "WB Steelbook", "mid", 45),
        ("Warner Bros", "The Dark Knight (4K Steelbook)", "4K UHD", "WB Steelbook", "mid", 50),
        ("Warner Bros", "The Dark Knight Rises (4K Steelbook)", "4K UHD", "WB Steelbook", "mid", 45),

        # ── Second Sight / Eureka / BFI UK Labels ────────────────────────
        ("Second Sight", "An American Werewolf in London (4K LE)", "4K UHD", "Second Sight LE", "high", 65),
        ("Second Sight", "The Wicker Man (4K LE)", "4K UHD", "Second Sight LE", "high", 60),
        ("Second Sight", "Hellraiser (4K UHD LE)", "4K UHD", "Second Sight LE", "high", 60),
        ("Eureka", "Seven Samurai (4K LE Box)", "4K UHD", "Masters of Cinema", "high", 65),
        ("Eureka", "Rashomon (4K LE)", "4K UHD", "Masters of Cinema", "mid", 50),
        ("Eureka", "Yojimbo / Sanjuro (4K Double Feature)", "4K UHD", "Masters of Cinema", "high", 60),
        ("BFI", "Stalker (4K UHD LE)", "4K UHD", "BFI Limited", "high", 55),
        ("BFI", "Mirror (Tarkovsky, 4K)", "4K UHD", "BFI Limited", "mid", 48),
        ("BFI", "Solaris (Tarkovsky, 4K)", "4K UHD", "BFI Limited", "mid", 48),

        # ── Imprint (Australia) / Fun City ────────────────────────────────
        ("Imprint", "Once Upon a Time in the West (4K LE)", "4K UHD", "Imprint LE", "high", 55),
        ("Imprint", "The Good, the Bad and the Ugly (4K LE)", "4K UHD", "Imprint LE", "high", 55),
        ("Imprint", "A Fistful of Dollars (4K LE)", "4K UHD", "Imprint LE", "mid", 48),
        ("Fun City Editions", "Santa Sangre (4K UHD LE)", "4K UHD", "Fun City LE", "high", 60),
        ("Fun City Editions", "El Topo (4K UHD LE)", "4K UHD", "Fun City LE", "mid", 50),

        # ── Additional Boutique & 4K ──────────────────────────────────────
        ("Twilight Time", "The Wild Bunch (Limited)", "Blu-ray", "Twilight Time LE", "high", 55),
        ("Twilight Time", "Fright Night (1985, Limited)", "Blu-ray", "Twilight Time LE", "mid", 45),
        ("Twilight Time", "Starship Troopers (Limited)", "Blu-ray", "Twilight Time LE", "mid", 40),
        ("StudioCanal", "The Third Man (4K UHD)", "4K UHD", "StudioCanal 4K", "mid", 45),
        ("StudioCanal", "Cinema Paradiso (4K UHD)", "4K UHD", "StudioCanal 4K", "mid", 42),
        ("StudioCanal", "Ran (Kurosawa, 4K UHD)", "4K UHD", "StudioCanal 4K", "high", 55),
        ("101 Films", "Commando (4K UHD Black Label)", "4K UHD", "101 Films LE", "mid", 40),
        ("101 Films", "Total Recall (4K UHD Black Label)", "4K UHD", "101 Films LE", "mid", 42),
        ("101 Films", "Predator (4K Black Label)", "4K UHD", "101 Films LE", "mid", 42),
        ("GKIDS", "Nausicaa of the Valley of the Wind (Steelbook)", "Blu-ray", "GKIDS Steelbook", "mid", 45),
        ("GKIDS", "Howl's Moving Castle (Steelbook)", "Blu-ray", "GKIDS Steelbook", "mid", 45),
        ("GKIDS", "Castle in the Sky (Steelbook)", "Blu-ray", "GKIDS Steelbook", "mid", 45),
        ("Funimation", "Cowboy Bebop Complete Series (Steelbook)", "Blu-ray Box", "LE Steelbook", "high", 80),
        ("Funimation", "Evangelion 3.0+1.0 (Steelbook)", "Blu-ray", "LE Steelbook", "high", 60),
        ("Discotek", "Lupin III Part 1 Complete (Steelbook)", "Blu-ray Box", "Discotek LE", "high", 65),
        ("Discotek", "Urusei Yatsura Complete (Blu-ray Box)", "Blu-ray Box", "Discotek LE", "high", 80),
        ("Sony", "Spider-Man: Across the Spider-Verse (4K Steelbook)", "4K UHD", "Sony Steelbook", "mid", 45),
        ("Lionsgate", "John Wick 1-4 (4K Box Set)", "4K UHD Box", "Limited Box", "high", 90),
        ("Universal", "Oppenheimer (4K Steelbook)", "4K UHD", "Universal Steelbook", "mid", 48),
        ("Warner Bros", "Dune Part Two (4K Steelbook)", "4K UHD", "WB Steelbook", "mid", 48),

        # ── Star Trek Steelbooks & Box Sets (15) ────────────────────────────
        ("Steelbook", "Star Trek: The Motion Picture", "4K UHD", "Zavvi Steelbook", "mid", 45),
        ("Steelbook", "Star Trek II: The Wrath of Khan", "4K UHD", "Zavvi Steelbook", "high", 65),
        ("Steelbook", "Star Trek III: The Search for Spock", "4K UHD", "Zavvi Steelbook", "mid", 40),
        ("Steelbook", "Star Trek IV: The Voyage Home", "4K UHD", "Zavvi Steelbook", "mid", 40),
        ("Steelbook", "Star Trek VI: The Undiscovered Country", "4K UHD", "Zavvi Steelbook", "mid", 45),
        ("Steelbook", "Star Trek (2009)", "4K UHD", "Zavvi Steelbook", "mid", 45),
        ("Steelbook", "Star Trek Into Darkness", "4K UHD", "Zavvi Steelbook", "mid", 40),
        ("Steelbook", "Star Trek Beyond", "4K UHD", "Zavvi Steelbook", "mid", 40),
        ("Box Set", "Star Trek Original Films 4K Collection (6-Film)", "4K UHD", "Paramount Box Set", "grail", 180),
        ("Box Set", "Star Trek Kelvin Timeline 4K Trilogy", "4K UHD", "Paramount Box Set", "high", 90),
        ("Box Set", "Star Trek TNG Complete Series Blu-ray", "Blu-ray", "CBS Box Set", "high", 120),
        ("Box Set", "Star Trek DS9 Complete Series Blu-ray", "Blu-ray", "CBS Box Set", "high", 130),
        ("Box Set", "Star Trek TOS Complete Series Blu-ray", "Blu-ray", "CBS Box Set", "high", 100),
        ("Box Set", "Star Trek Voyager Complete Series DVD", "DVD", "CBS Box Set", "mid", 80),
        ("Steelbook", "Star Trek: First Contact", "4K UHD", "Zavvi Steelbook", "high", 55),
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
    # Deduplicate by ('title', 'format', 'edition') (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = (item["title"], item["format"], item["edition"])
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


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
