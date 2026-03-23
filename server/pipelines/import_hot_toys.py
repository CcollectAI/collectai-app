"""
Import Hot Toys & Premium Collectible Statues catalog.

Layer 1 (Catalog):  Curated Hot Toys + Sideshow figures → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Hot Toys Marvel MCU 1/6 scale figures (Iron Man, Spider-Man, Thanos, Doctor Strange,
  Black Panther, Scarlet Witch, Moon Knight, Loki, Deadpool & Wolverine, etc.)
- Hot Toys Star Wars 1/6 scale figures (Mandalorian, Darth Vader, Boba Fett, Clones,
  Ahsoka, Rex, Cad Bane, Grogu Life Size, etc.)
- Hot Toys DC 1/6 scale figures (Batman, Joker, Superman, Aquaman, Wonder Woman, etc.)
- Hot Toys movie icons (John Wick, Terminator, RoboCop, Predator, Alien, Back to the
  Future, Indiana Jones, James Bond)
- Sideshow Premium Format statues (Marvel, DC, Star Wars, Predator)
- Sideshow & Queen Studios life-size busts
- Kotobukiya ARTFX+ and ARTFX Premier statues
- Iron Studios Art Scale and Legacy Replica statues
- XM Studios 1/4 scale premium statues
- Gentle Giant mini busts and Milestones statues
- 500+ items across all tiers (grail / high / mid / standard)

Usage:
    python -m pipelines.import_hot_toys [--dry-run]
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

CATEGORY = "hot_toys"


def get_curated_catalog() -> list[dict]:
    """Curated 500+ item catalog: Hot Toys 1/6 (MCU, Star Wars, DC, movie icons),
    Sideshow Premium Format & Maquettes, Sideshow/Queen Studios life-size busts,
    Gentle Giant, Kotobukiya ARTFX, XM Studios, Iron Studios, Prime 1 Studio,
    threezero, Gecco, and more."""

    # (brand, franchise, name, figure_type, rarity_tier, price_eur)
    # rarity_tier: grail (>1500), high (600-1500), mid (300-600), standard (<300)

    figures = [
        # ─── Marvel MCU — Hot Toys 1/6 ───────────────────────────────────
        ("Hot Toys", "Marvel MCU", "Iron Man Mark LXXXV (Mk 85)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark L (Mk 50)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark VII", "1/6 Figure", "mid", 480),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark III", "1/6 Figure", "high", 600),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark XLVI (Mk 46)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark IV", "1/6 Figure", "mid", 450),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Integrated Suit)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Iron Spider)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Symbiote Suit)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Black & Gold Suit)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Marvel MCU", "Thanos (Endgame)", "1/6 Figure", "mid", 480),
        ("Hot Toys", "Marvel MCU", "Thanos (Infinity War)", "1/6 Figure", "mid", 550),
        ("Hot Toys", "Marvel MCU", "Thanos (Battle Damaged)", "1/6 Figure", "mid", 520),
        ("Hot Toys", "Marvel MCU", "Captain America (Endgame)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Captain America (Stealth Suit)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Marvel MCU", "Thor (Love and Thunder)", "1/6 Figure", "standard", 280),
        ("Hot Toys", "Marvel MCU", "Hulkbuster 1/6 Scale", "1/6 Figure", "high", 900),
        ("Hot Toys", "Marvel MCU", "Black Panther (Original Suit)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Marvel MCU", "Black Panther (Wakanda Forever)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Marvel MCU", "Doctor Strange (Multiverse of Madness)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Marvel MCU", "Doctor Strange (Infinity War)", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Marvel MCU", "Scarlet Witch (WandaVision)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Scarlet Witch (Multiverse of Madness)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Marvel MCU", "Moon Knight", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Marvel MCU", "Moon Knight (Mr. Knight)", "1/6 Figure", "mid", 300),
        ("Hot Toys", "Marvel MCU", "Loki (Avengers Endgame)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Loki (TVA Variant)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Marvel MCU", "Deadpool & Wolverine Set", "1/6 Figure", "mid", 580),
        ("Hot Toys", "Marvel MCU", "War Machine Mark IV", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Marvel MCU", "Vision (WandaVision)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Marvel MCU", "Black Widow (Endgame)", "1/6 Figure", "mid", 320),

        # ─── Star Wars — Hot Toys 1/6 ───────────────────────────────────
        ("Hot Toys", "Star Wars", "The Mandalorian & Grogu Deluxe", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Star Wars", "The Mandalorian (Beskar)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Star Wars", "The Mandalorian (Beskar Staff)", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Star Wars", "Grogu Life-Size", "Life-Size Figure", "high", 620),
        ("Hot Toys", "Star Wars", "Darth Vader (ESB 40th Anniversary)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Star Wars", "Darth Vader (Rogue One)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "Darth Vader (Obi-Wan Kenobi)", "1/6 Figure", "mid", 390),
        ("Hot Toys", "Star Wars", "Boba Fett (Vintage Color)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Star Wars", "Boba Fett (Repaint Armor)", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Star Wars", "Clone Trooper 501st Battalion", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Star Wars", "Clone Trooper Phase II (Deluxe)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Star Wars", "Captain Rex (Ahsoka Series)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Star Wars", "Captain Rex (Clone Wars)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "Ahsoka Tano (The Mandalorian)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Star Wars", "Ahsoka Tano (Ahsoka Series)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Star Wars", "Cad Bane (The Book of Boba Fett)", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Star Wars", "Luke Skywalker (Crait)", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Star Wars", "Luke Skywalker (ROTJ Deluxe)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "Emperor Palpatine Deluxe", "1/6 Figure", "mid", 450),
        ("Hot Toys", "Star Wars", "Stormtrooper (A New Hope)", "1/6 Figure", "standard", 280),
        ("Hot Toys", "Star Wars", "Darth Maul (Solo)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "Obi-Wan Kenobi (Deluxe)", "1/6 Figure", "mid", 350),

        # ─── DC — Hot Toys 1/6 ──────────────────────────────────────────
        ("Hot Toys", "DC", "Batman (The Dark Knight)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "DC", "Batman (Batman Returns)", "1/6 Figure", "high", 650),
        ("Hot Toys", "DC", "Batman (Tactical Batsuit - Zack Snyder)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "DC", "Batman (The Batman 2022)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "DC", "Batman (The Batman 2022 - Batcycle)", "1/6 Figure", "high", 680),
        ("Hot Toys", "DC", "The Joker (The Dark Knight) DX11", "1/6 Figure", "high", 800),
        ("Hot Toys", "DC", "The Joker (The Dark Knight) DX32", "1/6 Figure", "high", 750),
        ("Hot Toys", "DC", "The Joker (Joaquin Phoenix)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "DC", "Harley Quinn (Birds of Prey)", "1/6 Figure", "standard", 280),
        ("Hot Toys", "DC", "Superman (Christopher Reeve)", "1/6 Figure", "high", 650),
        ("Hot Toys", "DC", "Superman (Justice League)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "DC", "Aquaman (Aquaman and the Lost Kingdom)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "DC", "Aquaman (Justice League)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "DC", "Wonder Woman (Justice League)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "DC", "The Flash (The Flash 2023)", "1/6 Figure", "mid", 310),

        # ─── Movie Icons — Hot Toys 1/6 ─────────────────────────────────
        ("Hot Toys", "John Wick", "John Wick (Chapter 4)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "John Wick", "John Wick (Chapter 2)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Terminator", "T-800 (Terminator 2) DX10", "1/6 Figure", "high", 700),
        ("Hot Toys", "Terminator", "T-800 (Battle Damaged)", "1/6 Figure", "mid", 550),
        ("Hot Toys", "RoboCop", "RoboCop (1987)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "RoboCop", "RoboCop (Diecast)", "1/6 Figure", "mid", 500),
        ("Hot Toys", "Predator", "City Hunter Predator", "1/6 Figure", "mid", 450),
        ("Hot Toys", "Predator", "Classic Predator", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Alien", "Alien Warrior", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Alien", "Ellen Ripley (Aliens)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Back to the Future", "Marty McFly", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Back to the Future", "Doc Brown", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Back to the Future", "Marty McFly & DeLorean Set", "1/6 Figure", "high", 850),
        ("Hot Toys", "Indiana Jones", "Indiana Jones (Raiders of the Lost Ark)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Indiana Jones", "Indiana Jones (Dial of Destiny) Deluxe", "1/6 Figure", "mid", 350),
        ("Hot Toys", "James Bond", "James Bond (Goldfinger - Sean Connery)", "1/6 Figure", "high", 650),
        ("Hot Toys", "James Bond", "James Bond (No Time to Die)", "1/6 Figure", "mid", 350),

        # ─── Sideshow Premium Format & Maquettes ────────────────────────
        ("Sideshow", "Marvel", "Spider-Man Premium Format", "Premium Format", "high", 750),
        ("Sideshow", "Marvel", "Wolverine Premium Format", "Premium Format", "high", 700),
        ("Sideshow", "Marvel", "Thanos on Throne Maquette", "Maquette", "grail", 1550),
        ("Sideshow", "Marvel", "Venom Premium Format", "Premium Format", "high", 720),
        ("Sideshow", "Marvel", "Hulk Premium Format", "Premium Format", "high", 800),
        ("Sideshow", "Marvel", "Iron Man Mark XLIII Maquette", "Maquette", "high", 850),
        ("Sideshow", "DC", "Batman Premium Format", "Premium Format", "high", 680),
        ("Sideshow", "DC", "Catwoman Premium Format", "Premium Format", "high", 650),
        ("Sideshow", "DC", "The Joker Premium Format", "Premium Format", "high", 700),
        ("Sideshow", "DC", "Harley Quinn Premium Format", "Premium Format", "high", 660),
        ("Sideshow", "Star Wars", "Darth Vader Premium Format", "Premium Format", "high", 800),
        ("Sideshow", "Star Wars", "Boba Fett Premium Format", "Premium Format", "high", 700),
        ("Sideshow", "Star Wars", "General Grievous Premium Format", "Premium Format", "high", 900),
        ("Sideshow", "Predator", "Predator Maquette", "Maquette", "high", 900),
        ("Sideshow", "Alien", "Alien Queen Maquette", "Maquette", "grail", 1600),
        ("Sideshow", "Mythos", "Frankensteins Monster Premium Format", "Premium Format", "high", 650),

        # ─── Life-Size Busts — Sideshow ─────────────────────────────────
        ("Sideshow", "Marvel", "Iron Man Mark III Life-Size Bust", "Life-Size Bust", "grail", 2200),
        ("Sideshow", "Marvel", "Thanos Life-Size Bust", "Life-Size Bust", "grail", 2800),
        ("Sideshow", "Marvel", "Deadpool Life-Size Bust", "Life-Size Bust", "grail", 1800),
        ("Sideshow", "Marvel", "Wolverine Life-Size Bust", "Life-Size Bust", "grail", 2000),
        ("Sideshow", "Star Wars", "Darth Vader Life-Size Bust", "Life-Size Bust", "grail", 3000),
        ("Sideshow", "Star Wars", "Boba Fett Life-Size Bust", "Life-Size Bust", "grail", 2400),
        ("Sideshow", "DC", "Batman Life-Size Bust", "Life-Size Bust", "grail", 2500),
        ("Sideshow", "DC", "The Joker Life-Size Bust", "Life-Size Bust", "grail", 2200),

        # ─── Life-Size Busts — Queen Studios ─────────────────────────────
        ("Queen Studios", "Marvel", "Iron Man Mark 50 Life-Size Bust", "Life-Size Bust", "grail", 3500),
        ("Queen Studios", "Marvel", "Spider-Man Life-Size Bust", "Life-Size Bust", "grail", 3200),
        ("Queen Studios", "Marvel", "Thanos Life-Size Bust", "Life-Size Bust", "grail", 4000),
        ("Queen Studios", "DC", "The Joker (Heath Ledger) Life-Size Bust", "Life-Size Bust", "grail", 4500),
        ("Queen Studios", "DC", "Batman (The Dark Knight) Life-Size Bust", "Life-Size Bust", "grail", 3800),
        ("Queen Studios", "DC", "Superman Life-Size Bust", "Life-Size Bust", "grail", 3600),

        # ─── Marvel Recent — Hot Toys 1/6 ──────────────────────────────
        ("Hot Toys", "Marvel MCU", "Spider-Man 2099", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Marvel MCU", "Deadpool (Deadpool & Wolverine)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Wolverine (Deadpool & Wolverine)", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Marvel MCU", "Loki (God Loki Crown)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Marvel MCU", "She-Hulk", "1/6 Figure", "standard", 290),
        ("Hot Toys", "Marvel MCU", "Kang the Conqueror", "1/6 Figure", "mid", 310),

        # ─── Star Wars Recent — Hot Toys 1/6 ──────────────────────────
        ("Hot Toys", "Star Wars", "Ahsoka Tano (Rosario Dawson - Ahsoka)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Star Wars", "The Mandalorian S3 (Beskar Spear)", "1/6 Figure", "mid", 370),
        ("Hot Toys", "Star Wars", "Cal Kestis (Jedi: Survivor)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Star Wars", "Bo-Katan Kryze (The Mandalorian S3)", "1/6 Figure", "mid", 320),

        # ─── DC Recent — Hot Toys 1/6 ─────────────────────────────────
        ("Hot Toys", "DC", "Blue Beetle", "1/6 Figure", "standard", 290),
        ("Hot Toys", "DC", "Aquaman (Golden Armor - Lost Kingdom)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "DC", "Batgirl (Cancelled Film Promo)", "1/6 Figure", "mid", 380),

        # ─── Movie Icons Recent — Hot Toys 1/6 ────────────────────────
        ("Hot Toys", "John Wick", "John Wick (Chapter 4 - Deluxe)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Barbie", "Barbie (Margot Robbie)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Oppenheimer", "J. Robert Oppenheimer (Cillian Murphy)", "1/6 Figure", "mid", 350),

        # ─── Cosbaby Sets ──────────────────────────────────────────────
        ("Hot Toys", "Marvel MCU", "Avengers Endgame Cosbaby Set (6 pcs)", "Cosbaby", "mid", 120),
        ("Hot Toys", "Marvel MCU", "Guardians of the Galaxy Vol. 3 Cosbaby Set (5 pcs)", "Cosbaby", "mid", 100),
        ("Hot Toys", "Star Wars", "The Mandalorian & Grogu Cosbaby Set", "Cosbaby", "standard", 50),

        # ─── Artist Mix Figures ────────────────────────────────────────
        ("Hot Toys", "Marvel MCU", "Ultron Mark I Artist Mix Figure", "Artist Mix", "mid", 180),
        ("Hot Toys", "Marvel MCU", "Hulkbuster & Battle-Damaged Iron Man Artist Mix Set", "Artist Mix", "mid", 220),

        # ─── Hot Toys x Marvel Zombie Series ──────────────────────────
        ("Hot Toys", "Marvel Zombies", "Zombie Iron Man", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Marvel Zombies", "Zombie Deadpool", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Marvel Zombies", "Zombie Captain America", "1/6 Figure", "mid", 350),

        # ─── DX (Deluxe) Versions ─────────────────────────────────────
        ("Hot Toys", "Marvel MCU", "Iron Man Mark VII DX (Special Edition)", "1/6 Figure", "high", 620),
        ("Hot Toys", "Star Wars", "Darth Vader DX (ESB 40th - Deluxe)", "1/6 Figure", "high", 650),

        # ─── 1/4 Scale Figures ─────────────────────────────────────────
        ("Hot Toys", "Marvel MCU", "Hulkbuster 1/4 Scale", "1/4 Figure", "grail", 1800),
        ("Hot Toys", "Marvel MCU", "Thanos 1/4 Scale (Infinity War)", "1/4 Figure", "grail", 1500),
        ("Hot Toys", "Star Wars", "Darth Vader 1/4 Scale", "1/4 Figure", "grail", 1600),

        # ─── Marvel MCU — Hot Toys Additional ──────────────────────────────
        ("Hot Toys", "Marvel MCU", "Iron Man Mark I", "1/6 Figure", "high", 650),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark II", "1/6 Figure", "mid", 500),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark V (Suitcase Armor)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark XLII (Mk 42)", "1/6 Figure", "mid", 390),
        ("Hot Toys", "Marvel MCU", "Captain America (The First Avenger)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Marvel MCU", "Hawkeye (Endgame Ronin)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Marvel MCU", "Falcon (Captain America)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Marvel MCU", "Nebula (Endgame)", "1/6 Figure", "standard", 290),
        ("Hot Toys", "Marvel MCU", "Shang-Chi", "1/6 Figure", "standard", 280),
        ("Hot Toys", "Marvel MCU", "Eternals Thena", "1/6 Figure", "standard", 270),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Homemade Suit)", "1/6 Figure", "mid", 300),
        ("Hot Toys", "Marvel MCU", "Groot Life-Size (GotG Vol. 2)", "Life-Size Figure", "high", 580),

        # ─── Star Wars — Hot Toys Additional ──────────────────────────────
        ("Hot Toys", "Star Wars", "Jango Fett", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "General Grievous", "1/6 Figure", "high", 620),
        ("Hot Toys", "Star Wars", "Yoda (Attack of the Clones)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Star Wars", "Count Dooku", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Star Wars", "Anakin Skywalker (Dark Side)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "Padme Amidala (Attack of the Clones)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Star Wars", "R2-D2 (Deluxe)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Star Wars", "C-3PO (A New Hope)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Star Wars", "Scout Trooper & Speeder Bike", "1/6 Figure", "high", 700),
        ("Hot Toys", "Star Wars", "Death Trooper (Rogue One)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Star Wars", "Snowtrooper Commander (ESB)", "1/6 Figure", "mid", 310),

        # ─── DC — Hot Toys Additional ─────────────────────────────────────
        ("Hot Toys", "DC", "Batman (Batman Begins)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "DC", "Catwoman (The Dark Knight Rises)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "DC", "Bane (The Dark Knight Rises)", "1/6 Figure", "mid", 450),
        ("Hot Toys", "DC", "Cyborg (Justice League)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "DC", "Deathstroke", "1/6 Figure", "mid", 360),
        ("Hot Toys", "DC", "Penguin (The Batman 2022)", "1/6 Figure", "mid", 320),

        # ─── Movie Icons — Hot Toys Additional ────────────────────────────
        ("Hot Toys", "The Avengers", "Iron Man Mark VI (Battle Damaged)", "1/6 Figure", "mid", 480),
        ("Hot Toys", "Jurassic World", "Blue (Velociraptor)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Pirates of the Caribbean", "Jack Sparrow DX06", "1/6 Figure", "high", 700),
        ("Hot Toys", "Pirates of the Caribbean", "Jack Sparrow DX15", "1/6 Figure", "high", 650),
        ("Hot Toys", "The Matrix", "Neo (The Matrix Reloaded)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Harry Potter", "Harry Potter (Quidditch Version)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Harry Potter", "Severus Snape", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Harry Potter", "Albus Dumbledore", "1/6 Figure", "mid", 360),

        # ─── Star Ace — Harry Potter ──────────────────────────────────────
        ("Star Ace", "Harry Potter", "Rubeus Hagrid 1/6 Deluxe", "1/6 Figure", "high", 340),
        ("Star Ace", "Harry Potter", "Lord Voldemort (Deathly Hallows)", "1/6 Figure", "mid", 250),
        ("Star Ace", "Harry Potter", "Albus Dumbledore (Richard Harris) Deluxe", "1/6 Figure", "mid", 240),
        ("Star Ace", "Harry Potter", "Harry Potter (Tri-Wizard Tournament)", "1/6 Figure", "mid", 220),
        ("Star Ace", "Harry Potter", "Severus Snape (Half-Blood Prince)", "1/6 Figure", "mid", 220),
        ("Star Ace", "Harry Potter", "Hermione Granger (Teenage)", "1/6 Figure", "mid", 210),
        ("Star Ace", "Harry Potter", "Harry Potter (Sorcerer's Stone)", "1/6 Figure", "mid", 185),
        ("Star Ace", "Harry Potter", "Ron Weasley", "1/6 Figure", "mid", 185),
        ("Star Ace", "Harry Potter", "Sirius Black", "1/6 Figure", "mid", 200),
        ("Star Ace", "Harry Potter", "Sirius Black (Prison Garb)", "1/6 Figure", "mid", 200),
        ("Star Ace", "Harry Potter", "Mad-Eye Moody", "1/6 Figure", "mid", 220),
        ("Star Ace", "Harry Potter", "Bellatrix Lestrange", "1/6 Figure", "mid", 200),
        ("Star Ace", "Harry Potter", "Draco Malfoy (Quidditch)", "1/6 Figure", "mid", 180),
        ("Star Ace", "Harry Potter", "Neville Longbottom", "1/6 Figure", "mid", 180),
        ("Star Ace", "Harry Potter", "Dobby", "1/6 Figure", "mid", 160),
        ("Star Ace", "Harry Potter", "Dementor", "1/6 Figure", "mid", 200),
        ("Star Ace", "Harry Potter", "Newt Scamander (Fantastic Beasts)", "1/6 Figure", "mid", 190),
        ("Star Ace", "Harry Potter", "Grindelwald (Fantastic Beasts)", "1/6 Figure", "mid", 190),
        ("Star Ace", "Harry Potter", "Buckbeak (Deluxe)", "1/6 Scale", "high", 400),
        ("Star Ace", "Harry Potter", "Hedwig (Life-Size)", "Life-Size", "high", 300),

        # ─── Iron Studios — Harry Potter ──────────────────────────────────
        ("Iron Studios", "Harry Potter", "Harry Potter Art Scale 1/10", "Art Scale Statue", "mid", 120),
        ("Iron Studios", "Harry Potter", "Voldemort Art Scale 1/10", "Art Scale Statue", "mid", 130),
        ("Iron Studios", "Harry Potter", "Hermione Art Scale 1/10", "Art Scale Statue", "mid", 110),
        ("Iron Studios", "Harry Potter", "Dumbledore Art Scale 1/10", "Art Scale Statue", "mid", 130),
        ("Iron Studios", "Harry Potter", "Hagrid Art Scale 1/10 Deluxe", "Art Scale Statue", "high", 250),

        # ─── Kotobukiya ARTFX ─────────────────────────────────────────────
        ("Kotobukiya", "Marvel", "Spider-Man ARTFX+ Statue", "ARTFX+ Statue", "standard", 120),
        ("Kotobukiya", "Marvel", "Wolverine ARTFX+ Statue", "ARTFX+ Statue", "standard", 110),
        ("Kotobukiya", "Marvel", "Iron Man ARTFX Premier", "ARTFX Premier", "mid", 320),
        ("Kotobukiya", "DC", "Batman ARTFX+ Statue", "ARTFX+ Statue", "standard", 115),
        ("Kotobukiya", "Star Wars", "Darth Vader ARTFX+ 1/7", "ARTFX+ Statue", "standard", 130),
        ("Kotobukiya", "Star Wars", "The Mandalorian ARTFX 1/7", "ARTFX Statue", "standard", 140),

        # ─── Iron Studios ─────────────────────────────────────────────────
        ("Iron Studios", "Marvel", "Spider-Man vs Villains Diorama 1/6", "Diorama", "high", 800),
        ("Iron Studios", "Marvel", "Thanos Legacy Replica 1/4", "1/4 Statue", "high", 650),
        ("Iron Studios", "DC", "Batman Deluxe Art Scale 1/10", "Art Scale Statue", "mid", 300),
        ("Iron Studios", "DC", "Joker Deluxe Art Scale 1/10", "Art Scale Statue", "mid", 280),
        ("Iron Studios", "Star Wars", "Boba Fett Art Scale 1/10", "Art Scale Statue", "mid", 250),
        ("Iron Studios", "Jurassic Park", "T-Rex Art Scale 1/10", "Art Scale Statue", "mid", 550),

        # ─── XM Studios ───────────────────────────────────────────────────
        ("XM Studios", "Marvel", "Spider-Man 1/4 Premium Collectible", "1/4 Statue", "grail", 1800),
        ("XM Studios", "Marvel", "Wolverine 1/4 Berserker Rage", "1/4 Statue", "grail", 2000),
        ("XM Studios", "DC", "Batman 1/4 Samurai Series", "1/4 Statue", "grail", 1600),
        ("XM Studios", "DC", "Superman 1/4 Classic", "1/4 Statue", "grail", 1500),

        # ─── Gentle Giant ─────────────────────────────────────────────────
        ("Gentle Giant", "Star Wars", "Darth Vader Classic Bust", "Mini Bust", "mid", 180),
        ("Gentle Giant", "Star Wars", "Boba Fett Classic Bust", "Mini Bust", "mid", 160),
        ("Gentle Giant", "Star Wars", "Stormtrooper Milestones Statue", "Milestones Statue", "mid", 350),
        ("Gentle Giant", "Marvel", "Deadpool Mini Bust", "Mini Bust", "standard", 120),

        # ─── Sideshow — Additional Premium Format ─────────────────────────
        ("Sideshow", "Marvel", "Captain America Premium Format", "Premium Format", "high", 750),
        ("Sideshow", "Marvel", "Doctor Doom Premium Format", "Premium Format", "high", 780),
        ("Sideshow", "Marvel", "Carnage Premium Format", "Premium Format", "high", 820),
        ("Sideshow", "DC", "Wonder Woman Premium Format", "Premium Format", "high", 700),
        ("Sideshow", "Star Wars", "Yoda Legendary Scale", "Legendary Scale", "grail", 2200),
        ("Sideshow", "Star Wars", "R2-D2 Legendary Scale", "Legendary Scale", "grail", 1800),

        # ─── Marvel MCU — Iron Man Marks Expanded ────────────────────────
        ("Hot Toys", "Marvel MCU", "Iron Man Mark VI", "1/6 Figure", "mid", 460),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark IX", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark XV (Sneaky)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark XX (Python)", "1/6 Figure", "mid", 390),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark XLIII (Mk 43)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark XLV (Mk 45)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark XLVII (Mk 47)", "1/6 Figure", "mid", 370),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark LXXX (Mk 80) Nanotech", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark LXXXV Battle Damaged", "1/6 Figure", "high", 620),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark LXXXV (I Am Iron Man Edition)", "1/6 Figure", "high", 680),

        # ─── Marvel MCU — Avengers Endgame Expanded ──────────────────────
        ("Hot Toys", "Marvel MCU", "Captain America (Avengers Endgame - Mjolnir)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Marvel MCU", "Thor (Avengers Endgame - Fat Thor)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Hawkeye (Endgame Deluxe)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Marvel MCU", "Pepper Potts (Rescue Armor)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Marvel MCU", "Hulk (Endgame - Nano Gauntlet)", "1/6 Figure", "mid", 450),
        ("Hot Toys", "Marvel MCU", "Nebula (Endgame Deluxe)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Marvel MCU", "Captain Marvel (Endgame)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Marvel MCU", "Thanos (Endgame - Full Armor)", "1/6 Figure", "mid", 500),
        ("Hot Toys", "Marvel MCU", "Nano Gauntlet (Hulk) 1/4 Scale", "1/4 Replica", "mid", 380),
        ("Hot Toys", "Marvel MCU", "Infinity Gauntlet 1/4 Scale", "1/4 Replica", "mid", 400),

        # ─── Marvel MCU — Multiverse & Phase 4-5 ────────────────────────
        ("Hot Toys", "Marvel MCU", "Spider-Man (Upgraded Suit - Far From Home)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Stealth Suit - Far From Home)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Marvel MCU", "Mysterio (Spider-Man: Far From Home)", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Marvel MCU", "Wenwu (Shang-Chi)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Marvel MCU", "Kate Bishop (Hawkeye Series)", "1/6 Figure", "standard", 290),
        ("Hot Toys", "Marvel MCU", "Ms. Marvel (Kamala Khan)", "1/6 Figure", "standard", 280),
        ("Hot Toys", "Marvel MCU", "Namor (Wakanda Forever)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Marvel MCU", "Gorr the God Butcher (Love and Thunder)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Marvel MCU", "Mighty Thor (Jane Foster)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Marvel MCU", "America Chavez (Multiverse of Madness)", "1/6 Figure", "standard", 280),
        ("Hot Toys", "Marvel MCU", "Wong (Multiverse of Madness)", "1/6 Figure", "standard", 290),

        # ─── Star Wars — Clone Wars & Prequel Expanded ───────────────────
        ("Hot Toys", "Star Wars", "Clone Trooper (212th Attack Battalion)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Star Wars", "Clone Trooper (Coruscant Guard)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Star Wars", "Clone Trooper (Wolfpack)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Star Wars", "Commander Cody", "1/6 Figure", "mid", 370),
        ("Hot Toys", "Star Wars", "Commander Wolffe", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Star Wars", "Anakin Skywalker (Clone Wars)", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Star Wars", "Obi-Wan Kenobi (Clone Wars)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Star Wars", "Qui-Gon Jinn", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "Mace Windu", "1/6 Figure", "mid", 370),
        ("Hot Toys", "Star Wars", "Battle Droid (Geonosis)", "1/6 Figure", "standard", 280),

        # ─── Star Wars — Ahsoka Series & Mandalorian Expanded ───────────
        ("Hot Toys", "Star Wars", "Baylan Skoll (Ahsoka Series)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Star Wars", "Shin Hati (Ahsoka Series)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Star Wars", "Grand Admiral Thrawn (Ahsoka Series)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "Sabine Wren (Ahsoka Series)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Star Wars", "Huyang (Ahsoka Series)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Star Wars", "The Armorer (The Mandalorian)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Star Wars", "Moff Gideon (Dark Trooper Armor)", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Star Wars", "Dark Trooper", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Star Wars", "IG-12 with Grogu", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "Paz Vizsla (The Mandalorian S3)", "1/6 Figure", "mid", 370),

        # ─── DC — The Batman 2022 & Recent Expanded ─────────────────────
        ("Hot Toys", "DC", "Batman (The Batman 2022 Deluxe)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "DC", "The Riddler (The Batman 2022)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "DC", "Catwoman (The Batman 2022)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "DC", "Joker (The Dark Knight) DX01", "1/6 Figure", "grail", 1200),
        ("Hot Toys", "DC", "Harley Quinn (Suicide Squad)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "DC", "Harley Quinn (The Suicide Squad 2021)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "DC", "Black Adam", "1/6 Figure", "standard", 280),
        ("Hot Toys", "DC", "Peacemaker", "1/6 Figure", "standard", 290),
        ("Hot Toys", "DC", "Supergirl (The Flash 2023)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "DC", "Batman (Batman Forever - Val Kilmer)", "1/6 Figure", "mid", 380),

        # ─── Movie Icons Expanded ────────────────────────────────────────
        ("Hot Toys", "Alien", "Alien Big Chap", "1/6 Figure", "mid", 450),
        ("Hot Toys", "Predator", "Jungle Hunter Predator", "1/6 Figure", "mid", 430),
        ("Hot Toys", "Predator", "Wolf Predator (Aliens vs Predator)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Rocky", "Rocky Balboa (Rocky IV)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Commando", "John Matrix (Arnold Schwarzenegger)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Mission: Impossible", "Ethan Hunt (Dead Reckoning)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "The Dark Tower", "Pennywise (IT Chapter Two)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Ghostbusters", "Peter Venkman (Ghostbusters: Afterlife)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Top Gun", "Maverick (Top Gun: Maverick)", "1/6 Figure", "mid", 330),

        # ─── Cosbaby Expanded ────────────────────────────────────────────
        ("Hot Toys", "Marvel MCU", "Iron Man Mark LXXXV Cosbaby", "Cosbaby", "standard", 25),
        ("Hot Toys", "Marvel MCU", "Spider-Man (No Way Home) Cosbaby Set (3 pcs)", "Cosbaby", "mid", 80),
        ("Hot Toys", "DC", "Batman (The Batman 2022) Cosbaby", "Cosbaby", "standard", 22),
        ("Hot Toys", "Star Wars", "Darth Vader Cosbaby", "Cosbaby", "standard", 22),
        ("Hot Toys", "Star Wars", "Boba Fett Cosbaby", "Cosbaby", "standard", 22),

        # ─── Sideshow — Additional Statues ───────────────────────────────
        ("Sideshow", "Marvel", "Deadpool Premium Format (Sideshow Exclusive)", "Premium Format", "high", 780),
        ("Sideshow", "Marvel", "Iron Man Mark XLIII Life-Size Bust", "Life-Size Bust", "grail", 2500),
        ("Sideshow", "Marvel", "Gambit Premium Format", "Premium Format", "high", 750),
        ("Sideshow", "Marvel", "Magneto Premium Format", "Premium Format", "high", 780),
        ("Sideshow", "DC", "Darkseid Premium Format", "Premium Format", "high", 850),
        ("Sideshow", "DC", "Batgirl Premium Format", "Premium Format", "high", 680),
        ("Sideshow", "DC", "Poison Ivy Premium Format", "Premium Format", "high", 700),
        ("Sideshow", "Star Wars", "Luke Skywalker Premium Format", "Premium Format", "high", 750),
        ("Sideshow", "Star Wars", "Princess Leia Premium Format", "Premium Format", "high", 700),
        ("Sideshow", "Predator", "Alien vs Predator Maquette", "Maquette", "grail", 1500),

        # ─── Prime 1 Studio ──────────────────────────────────────────────
        ("Prime 1 Studio", "DC", "Batman (Arkham Knight) 1/3 Scale", "1/3 Statue", "grail", 2200),
        ("Prime 1 Studio", "DC", "Joker (Arkham Origins) 1/3 Scale", "1/3 Statue", "grail", 1800),
        ("Prime 1 Studio", "DC", "Superman (New 52) 1/3 Scale", "1/3 Statue", "grail", 2000),
        ("Prime 1 Studio", "DC", "Batman (Hush) 1/3 Scale", "1/3 Statue", "grail", 2400),
        ("Prime 1 Studio", "Transformers", "Optimus Prime (G1) 1/4 Scale", "1/4 Statue", "grail", 2600),
        ("Prime 1 Studio", "LOTR", "Gandalf the White 1/4 Scale", "1/4 Statue", "grail", 1800),
        ("Prime 1 Studio", "Berserk", "Guts Berserker Armor 1/4 Scale", "1/4 Statue", "grail", 2000),

        # ─── XM Studios Expanded ─────────────────────────────────────────
        ("XM Studios", "Marvel", "Iron Man 1/4 Classic", "1/4 Statue", "grail", 1700),
        ("XM Studios", "Marvel", "Captain America 1/4 Sentinel of Liberty", "1/4 Statue", "grail", 1600),
        ("XM Studios", "Marvel", "Hulk 1/4 Transformation", "1/4 Statue", "grail", 2200),
        ("XM Studios", "Marvel", "Thor 1/4 Classic", "1/4 Statue", "grail", 1800),
        ("XM Studios", "DC", "Wonder Woman 1/4 Premium", "1/4 Statue", "grail", 1700),
        ("XM Studios", "DC", "The Flash 1/4 Rebirth", "1/4 Statue", "grail", 1500),

        # ─── Iron Studios Expanded ───────────────────────────────────────
        ("Iron Studios", "Marvel", "Iron Man LXXXV Art Scale 1/10", "Art Scale Statue", "mid", 280),
        ("Iron Studios", "Marvel", "Captain America (Endgame) Art Scale 1/10", "Art Scale Statue", "mid", 250),
        ("Iron Studios", "Marvel", "Spider-Man (No Way Home) Art Scale 1/10", "Art Scale Statue", "mid", 260),
        ("Iron Studios", "Marvel", "Scarlet Witch Art Scale 1/10", "Art Scale Statue", "mid", 250),
        ("Iron Studios", "DC", "Superman Art Scale 1/10", "Art Scale Statue", "mid", 280),
        ("Iron Studios", "DC", "Wonder Woman Art Scale 1/10", "Art Scale Statue", "mid", 260),
        ("Iron Studios", "Star Wars", "Darth Vader Art Scale 1/10", "Art Scale Statue", "mid", 280),
        ("Iron Studios", "Star Wars", "The Mandalorian Art Scale 1/10", "Art Scale Statue", "mid", 250),

        # ─── Kotobukiya Expanded ─────────────────────────────────────────
        ("Kotobukiya", "Marvel", "Captain America ARTFX Premier", "ARTFX Premier", "mid", 300),
        ("Kotobukiya", "Marvel", "Thor ARTFX Premier", "ARTFX Premier", "mid", 310),
        ("Kotobukiya", "Marvel", "Black Panther ARTFX+", "ARTFX+ Statue", "standard", 125),
        ("Kotobukiya", "Marvel", "Venom ARTFX+", "ARTFX+ Statue", "standard", 130),
        ("Kotobukiya", "Marvel", "Carnage ARTFX+", "ARTFX+ Statue", "standard", 135),
        ("Kotobukiya", "DC", "Superman ARTFX+", "ARTFX+ Statue", "standard", 120),
        ("Kotobukiya", "DC", "Wonder Woman ARTFX+", "ARTFX+ Statue", "standard", 120),
        ("Kotobukiya", "DC", "Harley Quinn ARTFX+", "ARTFX+ Statue", "standard", 115),
        ("Kotobukiya", "Star Wars", "Boba Fett ARTFX+ 1/7", "ARTFX+ Statue", "standard", 135),
        ("Kotobukiya", "Star Wars", "Stormtrooper ARTFX+ 2-Pack", "ARTFX+ Statue", "standard", 150),

        # ─── Gentle Giant Expanded ───────────────────────────────────────
        ("Gentle Giant", "Star Wars", "Yoda Classic Bust", "Mini Bust", "mid", 170),
        ("Gentle Giant", "Star Wars", "Ahsoka Tano Mini Bust", "Mini Bust", "mid", 180),
        ("Gentle Giant", "Star Wars", "Darth Maul Classic Bust", "Mini Bust", "mid", 190),
        ("Gentle Giant", "Star Wars", "Luke Skywalker Milestones Statue", "Milestones Statue", "mid", 360),
        ("Gentle Giant", "Marvel", "Spider-Man Mini Bust", "Mini Bust", "standard", 130),
        ("Gentle Giant", "Marvel", "Wolverine Mini Bust", "Mini Bust", "standard", 140),

        # ─── Marvel MCU — Remaining Avengers & Phase 1-3 ───────────────
        ("Hot Toys", "Marvel MCU", "Iron Man Mark XXI (Midas)", "1/6 Figure", "mid", 410),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark XXXIII (Silver Centurion)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark XL (Shotgun)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark XLIV (Hulkbuster)", "1/6 Figure", "high", 900),
        ("Hot Toys", "Marvel MCU", "Ant-Man", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Marvel MCU", "Ant-Man (Ant-Man and the Wasp)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Marvel MCU", "The Wasp (Ant-Man and the Wasp)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Marvel MCU", "Winter Soldier (Civil War)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Falcon (The Falcon and the Winter Soldier)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Marvel MCU", "Gamora (Infinity War)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Marvel MCU", "Star-Lord (Infinity War)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Marvel MCU", "Rocket Raccoon (Endgame)", "1/6 Figure", "standard", 280),
        ("Hot Toys", "Marvel MCU", "Groot (Infinity War)", "1/6 Figure", "standard", 270),
        ("Hot Toys", "Marvel MCU", "Drax (Infinity War)", "1/6 Figure", "standard", 290),
        ("Hot Toys", "Marvel MCU", "Mantis (Infinity War)", "1/6 Figure", "standard", 270),
        ("Hot Toys", "Marvel MCU", "Valkyrie (Thor: Ragnarok)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Marvel MCU", "Hela (Thor: Ragnarok)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Marvel MCU", "Nick Fury (Avengers)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Marvel MCU", "Maria Hill (Avengers: Age of Ultron)", "1/6 Figure", "mid", 300),
        ("Hot Toys", "Marvel MCU", "Ultron Prime (Age of Ultron)", "1/6 Figure", "mid", 400),

        # ─── Marvel MCU — Spider-Man Variants ──────────────────────────
        ("Hot Toys", "Marvel MCU", "Spider-Man (Classic Suit - No Way Home)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Marvel MCU", "Spider-Man (New Red & Blue Suit - NWH)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Negative Suit)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Marvel MCU", "Friendly Neighborhood Spider-Man (NWH)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Marvel MCU", "The Amazing Spider-Man (NWH)", "1/6 Figure", "mid", 340),

        # ─── Star Wars — Original Trilogy Expanded ─────────────────────
        ("Hot Toys", "Star Wars", "Luke Skywalker (A New Hope)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Star Wars", "Luke Skywalker (Bespin)", "1/6 Figure", "mid", 370),
        ("Hot Toys", "Star Wars", "Luke Skywalker (Endor)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Star Wars", "Han Solo (A New Hope)", "1/6 Figure", "mid", 370),
        ("Hot Toys", "Star Wars", "Han Solo (ESB)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "Princess Leia (A New Hope)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Star Wars", "Princess Leia (Endor)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Star Wars", "Chewbacca (A New Hope)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Star Wars", "Lando Calrissian (ESB)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Star Wars", "Boba Fett (ESB 40th Anniversary)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "IG-88", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Star Wars", "Bossk", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Star Wars", "Dengar", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Star Wars", "Royal Guard", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Star Wars", "Emperor Palpatine (ROTJ)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Star Wars", "Wicket the Ewok", "1/6 Figure", "standard", 280),
        ("Hot Toys", "Star Wars", "TIE Fighter Pilot", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Star Wars", "AT-AT Pilot", "1/6 Figure", "mid", 300),

        # ─── Star Wars — Sequel Trilogy ────────────────────────────────
        ("Hot Toys", "Star Wars", "Kylo Ren (The Force Awakens)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Star Wars", "Kylo Ren (The Last Jedi)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Star Wars", "Rey (The Force Awakens)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Star Wars", "Rey (The Last Jedi - Jedi Training)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Star Wars", "Finn (The Force Awakens)", "1/6 Figure", "standard", 280),
        ("Hot Toys", "Star Wars", "Poe Dameron (The Force Awakens)", "1/6 Figure", "standard", 290),
        ("Hot Toys", "Star Wars", "First Order Stormtrooper", "1/6 Figure", "standard", 280),
        ("Hot Toys", "Star Wars", "First Order Flametrooper", "1/6 Figure", "standard", 280),
        ("Hot Toys", "Star Wars", "Captain Phasma", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Star Wars", "Sith Trooper", "1/6 Figure", "standard", 290),
        ("Hot Toys", "Star Wars", "Praetorian Guard (Double Blade)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Star Wars", "Praetorian Guard (Heavy Blade)", "1/6 Figure", "mid", 340),

        # ─── Star Wars — Rogue One & Solo ──────────────────────────────
        ("Hot Toys", "Star Wars", "Jyn Erso (Rogue One)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Star Wars", "Chirrut Imwe (Rogue One)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Star Wars", "K-2SO (Rogue One)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Star Wars", "Director Krennic (Rogue One)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Star Wars", "Shoretrooper (Rogue One)", "1/6 Figure", "mid", 300),
        ("Hot Toys", "Star Wars", "Han Solo (Solo Movie)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Star Wars", "Patrol Trooper (Solo Movie)", "1/6 Figure", "standard", 280),
        ("Hot Toys", "Star Wars", "Range Trooper (Solo Movie)", "1/6 Figure", "standard", 290),

        # ─── Alien & Predator Full Line ────────────────────────────────
        ("Hot Toys", "Alien", "Xenomorph (Alien 1979)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Alien", "Alien Queen (Aliens 1986)", "1/6 Figure", "grail", 1200),
        ("Hot Toys", "Alien", "Newt (Aliens)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Alien", "Alien Dog (Alien 3)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Predator", "Elder Predator (Predator 2)", "1/6 Figure", "mid", 440),
        ("Hot Toys", "Predator", "Tracker Predator (Predators 2010)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Predator", "Berserker Predator (Predators)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Predator", "Fugitive Predator (The Predator 2018)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Alien vs Predator", "Scar Predator (AVP)", "1/6 Figure", "mid", 430),
        ("Hot Toys", "Alien vs Predator", "Celtic Predator (AVP)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Alien vs Predator", "Grid Alien (AVP)", "1/6 Figure", "mid", 380),

        # ─── John Wick Full Line ───────────────────────────────────────
        ("Hot Toys", "John Wick", "John Wick (Chapter 1)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "John Wick", "John Wick (Chapter 3 - Parabellum)", "1/6 Figure", "mid", 370),
        ("Hot Toys", "John Wick", "John Wick (Chapter 4 - Osaka Continental)", "1/6 Figure", "mid", 390),
        ("Hot Toys", "John Wick", "Caine (John Wick Chapter 4)", "1/6 Figure", "mid", 350),

        # ─── The Matrix ────────────────────────────────────────────────
        ("Hot Toys", "The Matrix", "Neo (The Matrix)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "The Matrix", "Trinity (The Matrix)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "The Matrix", "Agent Smith (The Matrix)", "1/6 Figure", "mid", 360),
        ("Hot Toys", "The Matrix", "Morpheus (The Matrix)", "1/6 Figure", "mid", 370),

        # ─── Indiana Jones Full Line ───────────────────────────────────
        ("Hot Toys", "Indiana Jones", "Indiana Jones (Temple of Doom)", "1/6 Figure", "mid", 370),
        ("Hot Toys", "Indiana Jones", "Indiana Jones (Last Crusade)", "1/6 Figure", "mid", 380),

        # ─── Terminator Full Line ──────────────────────────────────────
        ("Hot Toys", "Terminator", "T-800 (Terminator 1)", "1/6 Figure", "high", 680),
        ("Hot Toys", "Terminator", "T-1000 (Terminator 2)", "1/6 Figure", "mid", 500),
        ("Hot Toys", "Terminator", "T-800 (Terminator: Dark Fate)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Terminator", "T-800 Endoskeleton", "1/6 Figure", "mid", 450),

        # ─── RoboCop Full Line ─────────────────────────────────────────
        ("Hot Toys", "RoboCop", "RoboCop (Battle Damaged)", "1/6 Figure", "mid", 480),
        ("Hot Toys", "RoboCop", "ED-209 (RoboCop)", "1/6 Figure", "high", 750),
        ("Hot Toys", "RoboCop", "RoboCop (2014)", "1/6 Figure", "mid", 350),

        # ─── Video Game Characters ─────────────────────────────────────
        ("Hot Toys", "Marvel's Spider-Man", "Spider-Man (Advanced Suit - PS4)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Marvel's Spider-Man", "Spider-Man (Anti-Ock Suit)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Marvel's Spider-Man", "Spider-Man (Scarlet Spider Suit)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Marvel's Spider-Man", "Miles Morales (PS5)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Batman Arkham", "Batman (Arkham Knight)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Batman Arkham", "Batman (Arkham City)", "1/6 Figure", "mid", 370),
        ("Hot Toys", "Batman Arkham", "Harley Quinn (Arkham Knight)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Resident Evil", "Leon S. Kennedy (Resident Evil 6)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Metal Gear Solid", "Solid Snake (Metal Gear Solid 3)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Cyberpunk 2077", "V (Male) Cyberpunk 2077", "1/6 Figure", "mid", 340),

        # ─── Cosbaby Full Lines ────────────────────────────────────────
        ("Hot Toys", "Marvel MCU", "Thanos Cosbaby", "Cosbaby", "standard", 25),
        ("Hot Toys", "Marvel MCU", "Black Panther Cosbaby", "Cosbaby", "standard", 22),
        ("Hot Toys", "Marvel MCU", "Doctor Strange Cosbaby", "Cosbaby", "standard", 22),
        ("Hot Toys", "Marvel MCU", "Captain America Cosbaby", "Cosbaby", "standard", 22),
        ("Hot Toys", "Marvel MCU", "Hulk Cosbaby", "Cosbaby", "standard", 25),
        ("Hot Toys", "Marvel MCU", "Scarlet Witch Cosbaby", "Cosbaby", "standard", 22),
        ("Hot Toys", "Marvel MCU", "Loki Cosbaby", "Cosbaby", "standard", 22),
        ("Hot Toys", "Marvel MCU", "Moon Knight Cosbaby", "Cosbaby", "standard", 22),
        ("Hot Toys", "Marvel MCU", "Deadpool Cosbaby", "Cosbaby", "standard", 22),
        ("Hot Toys", "Marvel MCU", "Wolverine Cosbaby", "Cosbaby", "standard", 22),
        ("Hot Toys", "DC", "Joker (Dark Knight) Cosbaby", "Cosbaby", "standard", 25),
        ("Hot Toys", "DC", "Harley Quinn Cosbaby", "Cosbaby", "standard", 22),
        ("Hot Toys", "DC", "Superman Cosbaby", "Cosbaby", "standard", 22),
        ("Hot Toys", "DC", "Wonder Woman Cosbaby", "Cosbaby", "standard", 22),
        ("Hot Toys", "DC", "Aquaman Cosbaby", "Cosbaby", "standard", 22),
        ("Hot Toys", "Star Wars", "Yoda Cosbaby", "Cosbaby", "standard", 22),
        ("Hot Toys", "Star Wars", "R2-D2 Cosbaby", "Cosbaby", "standard", 22),
        ("Hot Toys", "Star Wars", "Stormtrooper Cosbaby", "Cosbaby", "standard", 20),
        ("Hot Toys", "Star Wars", "Luke Skywalker Cosbaby", "Cosbaby", "standard", 22),
        ("Hot Toys", "Star Wars", "Kylo Ren Cosbaby", "Cosbaby", "standard", 22),

        # ─── Artist Mix Series ─────────────────────────────────────────
        ("Hot Toys", "Marvel MCU", "Ultron Sentry Artist Mix", "Artist Mix", "mid", 160),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark XLIII Artist Mix", "Artist Mix", "mid", 170),
        ("Hot Toys", "Marvel MCU", "Thanos Artist Mix (Touma Design)", "Artist Mix", "mid", 200),
        ("Hot Toys", "Marvel MCU", "Groot Artist Mix (Dancing Groot)", "Artist Mix", "mid", 150),
        ("Hot Toys", "DC", "Batman Artist Mix (Touma Design)", "Artist Mix", "mid", 180),
        ("Hot Toys", "DC", "Joker Artist Mix (Touma Design)", "Artist Mix", "mid", 190),

        # ─── Sideshow Mythos Line ──────────────────────────────────────
        ("Sideshow", "Mythos", "Dracula Premium Format", "Premium Format", "high", 700),
        ("Sideshow", "Mythos", "Creature from the Black Lagoon Premium Format", "Premium Format", "high", 720),
        ("Sideshow", "Mythos", "The Mummy Premium Format", "Premium Format", "high", 680),
        ("Sideshow", "Mythos", "Wolfman Premium Format", "Premium Format", "high", 690),

        # ─── Prime 1 Studio Expanded ───────────────────────────────────
        ("Prime 1 Studio", "DC", "Poison Ivy (Batman: Hush) 1/3 Scale", "1/3 Statue", "grail", 2100),
        ("Prime 1 Studio", "DC", "Harley Quinn (Arkham City) 1/3 Scale", "1/3 Statue", "grail", 1900),
        ("Prime 1 Studio", "DC", "Nightwing 1/3 Scale", "1/3 Statue", "grail", 1800),
        ("Prime 1 Studio", "DC", "Deathstroke 1/3 Scale", "1/3 Statue", "grail", 2000),
        ("Prime 1 Studio", "DC", "Wonder Woman (New 52) 1/3 Scale", "1/3 Statue", "grail", 2200),
        ("Prime 1 Studio", "Alien", "Alien Warrior (Big Chap) 1/3 Scale", "1/3 Statue", "grail", 2400),
        ("Prime 1 Studio", "Predator", "Jungle Hunter Predator 1/3 Scale", "1/3 Statue", "grail", 2500),
        ("Prime 1 Studio", "LOTR", "Aragorn 1/4 Scale", "1/4 Statue", "grail", 1800),
        ("Prime 1 Studio", "LOTR", "Witch-King of Angmar 1/4 Scale", "1/4 Statue", "grail", 2000),
        ("Prime 1 Studio", "Berserk", "Griffith (Hawk of Light) 1/4 Scale", "1/4 Statue", "grail", 1900),
        ("Prime 1 Studio", "Devil May Cry", "Dante 1/4 Scale", "1/4 Statue", "grail", 1700),
        ("Prime 1 Studio", "Batman", "Batman (Detective Comics) 1/3 Scale", "1/3 Statue", "grail", 2300),

        # ─── Queen Studios Expanded ────────────────────────────────────
        ("Queen Studios", "Marvel", "Captain America Life-Size Bust", "Life-Size Bust", "grail", 3400),
        ("Queen Studios", "Marvel", "Wolverine Life-Size Bust", "Life-Size Bust", "grail", 3300),
        ("Queen Studios", "Marvel", "Deadpool Life-Size Bust", "Life-Size Bust", "grail", 3100),
        ("Queen Studios", "DC", "Wonder Woman Life-Size Bust", "Life-Size Bust", "grail", 3500),
        ("Queen Studios", "DC", "Catwoman Life-Size Bust", "Life-Size Bust", "grail", 3200),
        ("Queen Studios", "DC", "Harley Quinn (Suicide Squad) Life-Size Bust", "Life-Size Bust", "grail", 3000),
        ("Queen Studios", "LOTR", "Gollum Life-Size Bust", "Life-Size Bust", "grail", 2800),

        # ─── Iron Studios Expanded ─────────────────────────────────────
        ("Iron Studios", "Marvel", "Hulk (Endgame) Art Scale 1/10", "Art Scale Statue", "mid", 300),
        ("Iron Studios", "Marvel", "Thor (Endgame) Art Scale 1/10", "Art Scale Statue", "mid", 270),
        ("Iron Studios", "Marvel", "Doctor Strange Art Scale 1/10", "Art Scale Statue", "mid", 260),
        ("Iron Studios", "Marvel", "Black Panther Art Scale 1/10", "Art Scale Statue", "mid", 260),
        ("Iron Studios", "Marvel", "Wolverine Art Scale 1/10", "Art Scale Statue", "mid", 270),
        ("Iron Studios", "Marvel", "Deadpool Art Scale 1/10", "Art Scale Statue", "mid", 250),
        ("Iron Studios", "Marvel", "Venom Art Scale 1/10", "Art Scale Statue", "mid", 280),
        ("Iron Studios", "DC", "Flash Art Scale 1/10", "Art Scale Statue", "mid", 250),
        ("Iron Studios", "DC", "Aquaman Art Scale 1/10", "Art Scale Statue", "mid", 250),
        ("Iron Studios", "DC", "Harley Quinn Art Scale 1/10", "Art Scale Statue", "mid", 240),
        ("Iron Studios", "LOTR", "Gandalf Art Scale 1/10", "Art Scale Statue", "mid", 300),
        ("Iron Studios", "LOTR", "Aragorn Art Scale 1/10", "Art Scale Statue", "mid", 280),

        # ─── Asmus Toys — LOTR ────────────────────────────────────────────
        ("Asmus Toys", "LOTR", "Morgul Lord Witch-King 1/6", "1/6 Figure", "high", 900),
        ("Asmus Toys", "LOTR", "Gimli 1/6", "1/6 Figure", "high", 600),
        ("Asmus Toys", "LOTR", "Gandalf the Grey 2.0 1/6", "1/6 Figure", "high", 350),
        ("Asmus Toys", "LOTR", "Galadriel 1/6 (LE 1500)", "1/6 Figure", "high", 500),
        ("Asmus Toys", "LOTR", "Saruman 1/6", "1/6 Figure", "high", 430),
        ("Asmus Toys", "LOTR", "Eowyn 1/6", "1/6 Figure", "high", 325),
        ("Asmus Toys", "LOTR", "Arwen 1/6", "1/6 Figure", "high", 335),
        ("Asmus Toys", "LOTR", "Aragorn at Helm's Deep 1/6", "1/6 Figure", "mid", 300),
        ("Asmus Toys", "LOTR", "Legolas at Helm's Deep 1/6", "1/6 Figure", "mid", 275),
        ("Asmus Toys", "LOTR", "Twilight Witch-King 1/6", "1/6 Figure", "mid", 210),
        ("Asmus Toys", "LOTR", "Faramir 1/6", "1/6 Figure", "mid", 210),
        ("Asmus Toys", "LOTR", "Elven Archer 1/6", "1/6 Figure", "mid", 210),
        ("Asmus Toys", "LOTR", "Gollum Luxury Edition 1/6", "1/6 Figure", "mid", 270),
        ("Asmus Toys", "LOTR", "Boromir 1/6", "1/6 Figure", "mid", 250),
        ("Asmus Toys", "LOTR", "Frodo 1/6", "1/6 Figure", "mid", 220),
        ("Asmus Toys", "LOTR", "Samwise Gamgee 1/6", "1/6 Figure", "mid", 220),
        ("Asmus Toys", "LOTR", "Lurtz 1/6", "1/6 Figure", "mid", 200),
        ("Asmus Toys", "LOTR", "Eomer 1/6", "1/6 Figure", "mid", 230),
        ("Asmus Toys", "LOTR", "Theoden 1/6", "1/6 Figure", "mid", 240),
        ("Asmus Toys", "LOTR", "Mouth of Sauron 1/6", "1/6 Figure", "mid", 250),

        # ─── Sideshow — LOTR ─────────────────────────────────────────────
        ("Sideshow", "LOTR", "Sauron Premium Format 1/4 (LE 1500)", "1/4 Statue", "grail", 1500),
        ("Sideshow", "LOTR", "Gandalf Premium Format 1/4", "1/4 Statue", "high", 800),
        ("Sideshow", "LOTR", "Aragorn Premium Format 1/4", "1/4 Statue", "high", 700),
        ("Sideshow", "LOTR", "Legolas Premium Format 1/4", "1/4 Statue", "high", 650),
        ("Sideshow", "LOTR", "Gollum Premium Format 1/4", "1/4 Statue", "high", 500),

        # ─── Weta Workshop — LOTR ────────────────────────────────────────
        ("Weta Workshop", "LOTR", "Barad-dur Environment Statue", "Environment", "grail", 1500),
        ("Weta Workshop", "LOTR", "Minas Tirith Environment", "Environment", "grail", 600),
        ("Weta Workshop", "LOTR", "Orthanc Black Tower Environment", "Environment", "high", 700),
        ("Weta Workshop", "LOTR", "The Argonath Environment", "Environment", "high", 600),
        ("Weta Workshop", "LOTR", "Rivendell Environment", "Environment", "high", 500),
        ("Weta Workshop", "LOTR", "Bag End Environment", "Environment", "high", 450),
        ("Weta Workshop", "LOTR", "Helm's Deep Environment", "Environment", "high", 500),
        ("Weta Workshop", "LOTR", "Balrog Demon of Shadow & Flame", "Statue", "grail", 3500),
        ("Weta Workshop", "LOTR", "Gandalf the White (Classic Series)", "1:6 Statue", "high", 400),
        ("Weta Workshop", "LOTR", "Aragorn (Classic Series)", "1:6 Statue", "high", 350),
        ("Weta Workshop", "LOTR", "Legolas (Classic Series)", "1:6 Statue", "mid", 300),
        ("Weta Workshop", "LOTR", "Gimli (Classic Series)", "1:6 Statue", "mid", 300),
        ("Weta Workshop", "LOTR", "Boromir (Classic Series)", "1:6 Statue", "high", 400),
        ("Weta Workshop", "LOTR", "Witch-King of Angmar (Classic Series)", "1:6 Statue", "high", 450),
        ("Weta Workshop", "LOTR", "Cave Troll (Classic Series)", "1:6 Statue", "high", 500),

        ("Iron Studios", "Jurassic Park", "Velociraptor Art Scale 1/10", "Art Scale Statue", "mid", 350),

        # ─── threezero Figures ─────────────────────────────────────────
        ("threezero", "Transformers", "Optimus Prime DLX (Bumblebee Movie)", "DLX Figure", "high", 180),
        ("threezero", "Transformers", "Bumblebee DLX (Bumblebee Movie)", "DLX Figure", "high", 170),
        ("threezero", "Transformers", "Megatron DLX (War for Cybertron)", "DLX Figure", "high", 180),
        ("threezero", "Transformers", "Optimus Primal DLX (Rise of the Beasts)", "DLX Figure", "high", 175),
        ("threezero", "Marvel", "Iron Man Mark XLII DLX", "DLX Figure", "high", 170),
        ("threezero", "Marvel", "Iron Man Mark VII DLX", "DLX Figure", "high", 170),
        ("threezero", "Marvel", "War Machine Mark IV DLX", "DLX Figure", "high", 175),
        ("threezero", "Ultraman", "Ultraman (Shin Ultraman) FigZero", "FigZero Figure", "high", 160),
        ("threezero", "Game of Thrones", "Jon Snow 1/6 Scale", "1/6 Figure", "mid", 250),
        ("threezero", "Game of Thrones", "Daenerys Targaryen 1/6 Scale", "1/6 Figure", "mid", 260),

        # ─── Gecco Figures ─────────────────────────────────────────────
        ("Gecco", "Metal Gear Solid", "Raiden (MGS4) 1/6 Scale", "1/6 Statue", "high", 650),
        ("Gecco", "Metal Gear Solid", "Psycho Mantis 1/6 Scale", "1/6 Statue", "high", 700),
        ("Gecco", "Dark Souls", "Black Knight 1/6 Scale", "1/6 Statue", "high", 600),
        ("Gecco", "Dark Souls", "Artorias the Abysswalker 1/6 Scale", "1/6 Statue", "high", 680),
        ("Gecco", "Bloodborne", "Hunter 1/6 Scale", "1/6 Statue", "high", 650),
        ("Gecco", "Silent Hill", "Pyramid Head 1/6 Scale", "1/6 Statue", "high", 720),

        # ── Star Trek Premium Figures & Ship Replicas (15) ───────────────
        ("EXO-6", "Star Trek TOS", "Captain Kirk 1/6 Scale", "1/6 Figure", "high", 200),
        ("EXO-6", "Star Trek TOS", "Mr. Spock 1/6 Scale", "1/6 Figure", "high", 220),
        ("EXO-6", "Star Trek TOS", "Dr. McCoy 1/6 Scale", "1/6 Figure", "high", 200),
        ("EXO-6", "Star Trek TOS", "Uhura 1/6 Scale", "1/6 Figure", "high", 200),
        ("EXO-6", "Star Trek TNG", "Captain Picard 1/6 Scale", "1/6 Figure", "high", 220),
        ("EXO-6", "Star Trek TNG", "Commander Data 1/6 Scale", "1/6 Figure", "high", 200),
        ("EXO-6", "Star Trek TNG", "Worf 1/6 Scale", "1/6 Figure", "high", 200),
        ("EXO-6", "Star Trek TNG", "Locutus of Borg 1/6 Scale", "1/6 Figure", "high", 250),
        ("QMx", "Star Trek TOS", "Kirk & Spock Q-Fig Set", "Q-Fig", "mid", 50),
        ("Diamond Select", "Star Trek", "Enterprise NCC-1701 (Refit) Electronic Ship", "Ship Replica", "high", 180),
        ("Diamond Select", "Star Trek TNG", "Enterprise NCC-1701-D Electronic Ship", "Ship Replica", "high", 200),
        ("Eaglemoss", "Star Trek", "USS Enterprise NCC-1701 XL Edition", "Die-cast Ship", "high", 120),
        ("Eaglemoss", "Star Trek", "USS Enterprise NCC-1701-D XL Edition", "Die-cast Ship", "high", 120),
        ("Eaglemoss", "Star Trek", "Klingon Bird of Prey XL Edition", "Die-cast Ship", "high", 100),
        ("Eaglemoss", "Star Trek", "USS Defiant NX-74205 XL Edition", "Die-cast Ship", "mid", 90),
    ]

    catalog = []
    for brand, franchise, name, figure_type, tier, price in figures:
        catalog.append({
            "brand": brand,
            "franchise": franchise,
            "name": name,
            "figure_type": figure_type,
            "rarity_tier": tier,
            "price_eur": price,
        })

    catalog.extend(_batch_premium_figures_2025())
    catalog.extend(_batch_variant_editions())
    catalog.extend(_batch_expansion_round2())
    # Deduplicate by ('brand', 'name', 'figure_type') (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = (item["brand"], item["name"], item["figure_type"])
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


def _batch_premium_figures_2025() -> list[dict]:
    """Batch 8 — Cosbaby expansion, 1/4 scale, MMS Diecast, Mandalorian,
    Spider-Verse, Deadpool & Wolverine. ~50 items."""

    items = [
        # Hot Toys Cosbaby — Avengers (expanded)
        ("Hot Toys", "Marvel MCU", "Avengers Endgame Iron Man Mark LXXXV Cosbaby", "Cosbaby", "standard", 28),
        ("Hot Toys", "Marvel MCU", "Avengers Endgame Captain America Worthy Cosbaby", "Cosbaby", "standard", 28),
        ("Hot Toys", "Marvel MCU", "Avengers Endgame Thor Fat Thor Cosbaby", "Cosbaby", "standard", 25),
        ("Hot Toys", "Marvel MCU", "Avengers Endgame Nebula Cosbaby", "Cosbaby", "standard", 22),
        ("Hot Toys", "Marvel MCU", "Avengers Endgame Rocket Raccoon Cosbaby", "Cosbaby", "standard", 22),
        ("Hot Toys", "Marvel MCU", "She-Hulk Attorney at Law Cosbaby", "Cosbaby", "standard", 22),

        # Hot Toys Cosbaby — Star Wars (expanded)
        ("Hot Toys", "Star Wars", "The Mandalorian Din Djarin Cosbaby", "Cosbaby", "standard", 25),
        ("Hot Toys", "Star Wars", "Grogu The Child with Pram Cosbaby", "Cosbaby", "standard", 28),
        ("Hot Toys", "Star Wars", "Ahsoka Tano (Ahsoka Series) Cosbaby", "Cosbaby", "standard", 25),
        ("Hot Toys", "Star Wars", "Bo-Katan Kryze Cosbaby", "Cosbaby", "standard", 22),
        ("Hot Toys", "Star Wars", "Darth Maul (Phantom Menace) Cosbaby", "Cosbaby", "standard", 25),

        # Hot Toys 1/4 Scale — Iron Man
        ("Hot Toys", "Marvel MCU", "Iron Man Mark LXXXV 1/4 Scale (Endgame)", "1/4 Figure", "grail", 1200),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark L 1/4 Scale (Infinity War)", "1/4 Figure", "grail", 1100),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark III 1/4 Scale Deluxe", "1/4 Figure", "grail", 1300),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark XLVI 1/4 Scale (Civil War)", "1/4 Figure", "grail", 1150),

        # Hot Toys 1/4 Scale — Thanos & Others
        ("Hot Toys", "Marvel MCU", "Thanos 1/4 Scale (Endgame Battle Damaged)", "1/4 Figure", "grail", 1400),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Integrated Suit) 1/4 Scale", "1/4 Figure", "grail", 900),
        ("Hot Toys", "DC", "Batman (The Dark Knight) 1/4 Scale", "1/4 Figure", "grail", 1100),
        ("Hot Toys", "DC", "Joker (The Dark Knight) 1/4 Scale", "1/4 Figure", "grail", 1050),

        # Movie Masterpiece Diecast — War Machine / Iron Patriot
        ("Hot Toys", "Marvel MCU", "War Machine Mark IV MMS Diecast (Endgame)", "1/6 Figure", "high", 580),
        ("Hot Toys", "Marvel MCU", "War Machine Mark VI MMS Diecast (Armor Wars)", "1/6 Figure", "high", 600),
        ("Hot Toys", "Marvel MCU", "Iron Patriot MMS Diecast (Endgame)", "1/6 Figure", "high", 560),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark XLVII MMS Diecast (Homecoming)", "1/6 Figure", "high", 550),
        ("Hot Toys", "Marvel MCU", "Iron Man Nanotech Suit MMS Diecast (Infinity War)", "1/6 Figure", "high", 570),

        # The Mandalorian — Full Line
        ("Hot Toys", "Star Wars", "Din Djarin (Mandalorian S3 New Armor)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Star Wars", "Grogu 1/6 Scale (Season 3)", "1/6 Figure", "mid", 280),
        ("Hot Toys", "Star Wars", "Bo-Katan Kryze (Mandalorian S3)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "Moff Gideon (Beskar Armor)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Star Wars", "The Armorer (Mandalorian)", "1/6 Figure", "mid", 390),
        ("Hot Toys", "Star Wars", "Paz Vizsla Heavy Infantry (Mandalorian)", "1/6 Figure", "high", 500),

        # Across the Spider-Verse
        ("Hot Toys", "Marvel Spider-Verse", "Miles Morales (Across the Spider-Verse)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Marvel Spider-Verse", "Spider-Gwen (Across the Spider-Verse)", "1/6 Figure", "mid", 370),
        ("Hot Toys", "Marvel Spider-Verse", "Spider-Man 2099 Miguel O'Hara", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Marvel Spider-Verse", "Spider-Punk Hobie Brown", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Marvel Spider-Verse", "The Spot (Across the Spider-Verse)", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Marvel Spider-Verse", "Scarlet Spider Ben Reilly (Spider-Verse)", "1/6 Figure", "mid", 370),

        # Deadpool & Wolverine
        ("Hot Toys", "Marvel MCU", "Lady Deadpool (Deadpool & Wolverine)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Marvel MCU", "Dogpool (Deadpool & Wolverine)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Cassandra Nova (Deadpool & Wolverine)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Marvel MCU", "Nicepool (Deadpool & Wolverine)", "1/6 Figure", "mid", 370),

        # Additional Hot Toys — Recent MCU
        ("Hot Toys", "Marvel MCU", "Kang the Conqueror (Quantumania)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Marvel MCU", "Namor (Black Panther Wakanda Forever)", "1/6 Figure", "mid", 390),
        ("Hot Toys", "Marvel MCU", "Shuri Black Panther Suit (Wakanda Forever)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Marvel MCU", "Loki (Season 2 Finale God of Stories)", "1/6 Figure", "mid", 410),

        # Additional Hot Toys — DC
        ("Hot Toys", "DC", "Batman (Ben Affleck The Flash 2023)", "1/6 Figure", "mid", 400),

        # === EXPANSION ROUND — 55 new items ===

        # ─── Star Wars Hot Toys (+10) ──────────────────────────────────
        ("Hot Toys", "Star Wars", "Clone Commander Cody (Phase II)", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Star Wars", "Clone Trooper 212th Attack Battalion", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Star Wars", "ARC Trooper Echo (The Bad Batch)", "1/6 Figure", "mid", 370),
        ("Hot Toys", "Star Wars", "ARC Trooper Fives (Clone Wars)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "Obi-Wan Kenobi (ROTS Deluxe)", "1/6 Figure", "mid", 410),
        ("Hot Toys", "Star Wars", "Emperor Palpatine (ROTJ Throne Room)", "1/6 Figure", "high", 500),
        ("Hot Toys", "Star Wars", "Grand Admiral Thrawn (Ahsoka)", "1/6 Figure", "mid", 450),

        # ─── Marvel MCU Phase 5/6 & Multiverse (+10) ──────────────────
        ("Hot Toys", "Marvel MCU", "Captain America (Brave New World)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Marvel MCU", "Thunderbolts Winter Soldier (Bucky)", "1/6 Figure", "mid", 370),
        ("Hot Toys", "Marvel MCU", "Agatha Harkness (Agatha All Along)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Marvel MCU", "Echo (Maya Lopez)", "1/6 Figure", "standard", 280),
        ("Hot Toys", "Marvel MCU", "She-Hulk (Jennifer Walters)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Marvel MCU", "Yellowjacket (Ant-Man)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Marvel MCU", "Mysterio (Far From Home)", "1/6 Figure", "mid", 400),

        # ─── DC Hot Toys (+8) ─────────────────────────────────────────
        ("Hot Toys", "DC", "Batman (The Dark Knight DX19)", "1/6 Figure", "high", 650),
        ("Hot Toys", "DC", "The Joker (Heath Ledger DX11)", "1/6 Figure", "high", 800),
        ("Hot Toys", "DC", "The Joker (Joaquin Phoenix 2019)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "DC", "Wonder Woman (Gal Gadot Justice League)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "DC", "Cyborg (Justice League Snyder Cut)", "1/6 Figure", "mid", 370),

        # ─── Video Game Figures (+7) ──────────────────────────────────
        ("Hot Toys", "Resident Evil", "Leon S. Kennedy (RE4 Remake)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Resident Evil", "Ada Wong (RE4 Remake)", "1/6 Figure", "mid", 370),
        ("Hot Toys", "Resident Evil", "Chris Redfield (RE Village)", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Metal Gear", "Naked Snake (MGS3 Snake Eater)", "1/6 Figure", "high", 550),
        ("Hot Toys", "Metal Gear", "Raiden (Metal Gear Rising)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Batman Arkham", "Harley Quinn (Arkham City)", "1/6 Figure", "mid", 380),

        # ─── Horror / Predator / Aliens (+7) ─────────────────────────
        ("Hot Toys", "Alien", "Alien Warrior (35th Anniversary)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Predator", "City Hunter Predator (Predator 2)", "1/6 Figure", "mid", 450),
        ("Hot Toys", "Predator", "Wolf Predator (AVPR)", "1/6 Figure", "mid", 440),
        ("Hot Toys", "Horror", "Michael Myers (Halloween 2018)", "1/6 Figure", "mid", 370),

        # ─── Cosbaby / Artist Mix Series (+7) ────────────────────────
        ("Hot Toys", "Marvel MCU", "Iron Man Mark LXXXV Cosbaby (L)", "Cosbaby", "standard", 45),
        ("Hot Toys", "Marvel MCU", "Spider-Man Cosbaby (Integrated Suit)", "Cosbaby", "standard", 40),
        ("Hot Toys", "Marvel MCU", "Thanos Cosbaby (Infinity Gauntlet)", "Cosbaby", "standard", 42),
        ("Hot Toys", "Star Wars", "Darth Vader Cosbaby (Bobble-Head)", "Cosbaby", "standard", 38),
        ("Hot Toys", "Marvel MCU", "Avengers Artist Mix Set (Ultron Series)", "Artist Mix", "mid", 180),
        ("Hot Toys", "Marvel MCU", "Guardians of the Galaxy Artist Mix Set", "Artist Mix", "mid", 200),

        # ─── Die-Cast Versions (+6) ──────────────────────────────────
        ("Hot Toys", "Marvel MCU", "Iron Man Mark VII (Die-Cast)", "1/6 Figure", "high", 650),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark L (Die-Cast)", "1/6 Figure", "high", 620),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark XLVI (Die-Cast)", "1/6 Figure", "high", 600),
        ("Hot Toys", "Marvel MCU", "War Machine Mark IV (Die-Cast)", "1/6 Figure", "high", 580),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark III (Die-Cast)", "1/6 Figure", "high", 700),
        ("Hot Toys", "Star Wars", "Darth Vader (ESB Die-Cast)", "1/6 Figure", "high", 550),

        # ─── Deadpool & Wolverine Expansion (+10) ───────────────────────
        ("Hot Toys", "Marvel MCU", "Deadpool & Wolverine 2-Pack Set", "1/6 Figure", "high", 850),
        ("Hot Toys", "Marvel MCU", "Kidpool (Deadpool & Wolverine)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Marvel MCU", "Headpool (Deadpool & Wolverine)", "1/6 Figure", "mid", 280),
        ("Hot Toys", "Marvel MCU", "Babypool (Deadpool & Wolverine)", "Cosbaby", "standard", 45),
        ("Hot Toys", "Marvel MCU", "Deadpool (Deadpool & Wolverine) Deluxe", "1/6 Figure", "high", 480),
        ("Hot Toys", "Marvel MCU", "Wolverine (Deadpool & Wolverine) Deluxe", "1/6 Figure", "high", 490),
        ("Hot Toys", "Marvel MCU", "Wolverine (Brown Suit, Deadpool & Wolverine)", "1/6 Figure", "mid", 440),
        ("Hot Toys", "Marvel MCU", "Paradox (Deadpool & Wolverine)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Pyro (Deadpool & Wolverine)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Marvel MCU", "Alioth (Deadpool & Wolverine) Diorama", "Diorama", "high", 700),

        # ─── Thunderbolts* (+8) ──────────────────────────────────────────
        ("Hot Toys", "Marvel MCU", "Thunderbolts Red Guardian", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Marvel MCU", "Thunderbolts Yelena Belova", "1/6 Figure", "mid", 370),
        ("Hot Toys", "Marvel MCU", "Thunderbolts Ghost", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Thunderbolts Taskmaster", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Marvel MCU", "Thunderbolts U.S. Agent", "1/6 Figure", "mid", 370),
        ("Hot Toys", "Marvel MCU", "Thunderbolts Bucky Barnes (Winter Soldier)", "1/6 Figure", "mid", 390),
        ("Hot Toys", "Marvel MCU", "Thunderbolts Sentry (Bob Reynolds)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Marvel MCU", "Thunderbolts Valentina Allegra de Fontaine", "1/6 Figure", "mid", 340),

        # ─── Star Wars Ahsoka Series (+8) ───────────────────────────────
        ("Hot Toys", "Star Wars", "Ahsoka Tano (Ahsoka Series Live Action)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Star Wars", "Hera Syndulla (Ahsoka Series)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "Marrok (Ahsoka Series)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Star Wars", "Chopper Droid (Ahsoka Series)", "1/6 Figure", "standard", 250),

        # ─── Mandalorian Season 3 (+6) ──────────────────────────────────
        ("Hot Toys", "Star Wars", "Din Djarin (Mandalorian S3 Beskar Spear)", "1/6 Figure", "mid", 440),
        ("Hot Toys", "Star Wars", "Grogu (Mandalorian S3 IG-12 Mech)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Star Wars", "Praetorian Guard (Mandalorian S3)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "Greef Karga (Mandalorian S3)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Star Wars", "Ragnar Vizsla (Mandalorian S3)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Star Wars", "Mythosaur Skull Diorama (Mandalorian)", "Diorama", "high", 600),

        # ─── DC — The Batman / Blue Beetle (+8) ─────────────────────────
        ("Hot Toys", "DC", "Batman (Robert Pattinson The Batman)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "DC", "Batman (The Batman Unmasked Version)", "1/6 Figure", "mid", 440),
        ("Hot Toys", "DC", "Catwoman (The Batman Zoe Kravitz)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "DC", "The Riddler (The Batman Paul Dano)", "1/6 Figure", "mid", 360),
        ("Hot Toys", "DC", "Penguin (The Batman Colin Farrell)", "1/6 Figure", "mid", 370),
        ("Hot Toys", "DC", "Blue Beetle (Jaime Reyes)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "DC", "Batgirl (Batgirl 2025)", "1/6 Figure", "mid", 340),

        # ─── Cosbaby Expansion (+10) ─────────────────────────────────────
        ("Hot Toys", "Marvel MCU", "Deadpool & Wolverine Cosbaby 2-Pack", "Cosbaby", "standard", 48),
        ("Hot Toys", "Marvel MCU", "Scarlet Witch (WandaVision) Cosbaby", "Cosbaby", "standard", 25),
        ("Hot Toys", "Marvel MCU", "Ms. Marvel Kamala Khan Cosbaby", "Cosbaby", "standard", 22),
        ("Hot Toys", "Marvel MCU", "Loki (God of Stories) Cosbaby", "Cosbaby", "standard", 25),
        ("Hot Toys", "DC", "The Batman Cosbaby", "Cosbaby", "standard", 24),
        ("Hot Toys", "DC", "Catwoman (The Batman) Cosbaby", "Cosbaby", "standard", 22),
        ("Hot Toys", "DC", "Blue Beetle Cosbaby", "Cosbaby", "standard", 22),
        ("Hot Toys", "Star Wars", "Luke Skywalker (ROTJ) Cosbaby", "Cosbaby", "standard", 25),
        ("Hot Toys", "Star Wars", "Emperor Palpatine Cosbaby", "Cosbaby", "standard", 22),

        # ─── Artist Mix Expansion (+6) ───────────────────────────────────
        ("Hot Toys", "Marvel MCU", "Avengers Endgame Artist Mix Full Set", "Artist Mix", "mid", 250),
        ("Hot Toys", "Marvel MCU", "Spider-Man Rogues Gallery Artist Mix Set", "Artist Mix", "mid", 180),
        ("Hot Toys", "DC", "Batman v Superman Artist Mix Set", "Artist Mix", "mid", 200),
        ("Hot Toys", "Star Wars", "Mandalorian Artist Mix Set", "Artist Mix", "mid", 190),
        ("Hot Toys", "Marvel MCU", "Deadpool & Wolverine Artist Mix Set", "Artist Mix", "mid", 170),
        ("Hot Toys", "Marvel MCU", "Doctor Strange Artist Mix Set", "Artist Mix", "mid", 160),

        # ─── Toy Fair & Convention Exclusives (+8) ───────────────────────
        ("Hot Toys", "Marvel MCU", "Iron Man Mark IV (Holographic Toy Fair)", "1/6 Figure", "grail", 1200),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Negative Suit Toy Fair)", "1/6 Figure", "high", 550),
        ("Hot Toys", "Star Wars", "Shadow Trooper (Toy Fair Exclusive)", "1/6 Figure", "high", 500),
        ("Hot Toys", "Star Wars", "Gold Chrome Stormtrooper (Toy Fair)", "1/6 Figure", "high", 600),
        ("Hot Toys", "Marvel MCU", "Hulk (SDCC 2019 Exclusive Battle Damaged)", "1/6 Figure", "high", 580),
        ("Hot Toys", "DC", "Armored Batman (Black Chrome SDCC)", "1/6 Figure", "high", 650),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark XLII (SDCC Battle Damaged)", "1/6 Figure", "high", 600),
        ("Hot Toys", "Star Wars", "Boba Fett (Vintage Color SDCC)", "1/6 Figure", "high", 520),

        # ─── Back-Catalog Grails (+14) ───────────────────────────────────
        ("Hot Toys", "DC", "DX01 The Dark Knight Batman (Original DX)", "1/6 Figure", "grail", 1500),
        ("Hot Toys", "DC", "DX11 The Joker (Dark Knight, DX Reissue)", "1/6 Figure", "grail", 1800),
        ("Hot Toys", "DC", "DX12 The Dark Knight Rises Batman", "1/6 Figure", "grail", 1400),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark I (Original Release)", "1/6 Figure", "grail", 1200),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark II (Armor Unleashed)", "1/6 Figure", "grail", 1100),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark VI (Die-Cast)", "1/6 Figure", "high", 750),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark XLII (Original Release)", "1/6 Figure", "high", 700),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark XLIII (Age of Ultron)", "1/6 Figure", "high", 650),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark XLIV Hulkbuster (AoU)", "1/6 Figure", "grail", 2000),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark XLV (Age of Ultron)", "1/6 Figure", "high", 620),
        ("Hot Toys", "Star Wars", "Boba Fett (ESB Original 2012)", "1/6 Figure", "grail", 1100),
        ("Hot Toys", "Star Wars", "Darth Vader (ANH Original 2010)", "1/6 Figure", "grail", 1300),
        ("Hot Toys", "DC", "Superman (Man of Steel, Original Release)", "1/6 Figure", "high", 650),

        # ─── Additional Movie Icons (+10) ─────────────────────────────
        ("Hot Toys", "John Wick", "John Wick (Chapter 4 Deluxe)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "John Wick", "John Wick (Chapter 2 Suit)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Indiana Jones", "Indiana Jones (Dial of Destiny)", "1/6 Figure", "mid", 450),
        ("Hot Toys", "Indiana Jones", "Indiana Jones (Raiders Classic Deluxe)", "1/6 Figure", "high", 550),
        ("Hot Toys", "Back to the Future", "Marty McFly (BTTF Part II Hoverboard)", "1/6 Figure", "high", 600),
        ("Hot Toys", "Back to the Future", "Doc Brown (BTTF Part I Lab Coat)", "1/6 Figure", "high", 580),
        ("Hot Toys", "RoboCop", "RoboCop (Die-Cast, Original)", "1/6 Figure", "high", 650),
        ("Hot Toys", "Terminator", "T-800 (Battle Damaged, T2)", "1/6 Figure", "high", 550),
        ("Hot Toys", "James Bond", "James Bond 007 (Goldfinger Sean Connery)", "1/6 Figure", "grail", 1100),
        ("Hot Toys", "Pirates of Caribbean", "Captain Jack Sparrow (DX15 Reissue)", "1/6 Figure", "grail", 1000),
    ]

    catalog = []
    for brand, franchise, name, figure_type, tier, price in items:
        catalog.append({
            "brand": brand,
            "franchise": franchise,
            "name": name,
            "figure_type": figure_type,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def _batch_variant_editions() -> list[dict]:
    """Batch 9 — Standard vs Deluxe, Special/Exclusive, and Die-Cast variant
    editions for key Hot Toys figures. ~120 items covering Iron Man, Spider-Man,
    Captain America, Thor, Thanos, Black Panther, Darth Vader, Mandalorian,
    Boba Fett, Luke Skywalker, Joker, Batman, John Wick, Predator, and Alien."""

    items = [
        # ─── Iron Man — Standard / Deluxe / Die-Cast Variants ─────────────
        ("Hot Toys", "Marvel MCU", "Iron Man MK85 (Endgame) Standard", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Marvel MCU", "Iron Man MK85 (Endgame) Deluxe", "1/6 Figure", "mid", 490),
        ("Hot Toys", "Marvel MCU", "Iron Man MK85 (Endgame) Die-Cast", "1/6 Figure", "high", 580),
        ("Hot Toys", "Marvel MCU", "Iron Man MK50 (Infinity War) Standard", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Marvel MCU", "Iron Man MK50 (Infinity War) Deluxe", "1/6 Figure", "mid", 520),
        ("Hot Toys", "Marvel MCU", "Iron Man MK7 (Avengers) Die-Cast", "1/6 Figure", "high", 650),
        ("Hot Toys", "Marvel MCU", "Iron Man MK4 (Iron Man 2) Die-Cast", "1/6 Figure", "high", 620),
        ("Hot Toys", "Marvel MCU", "Iron Man MK6 (Iron Man 2) Die-Cast", "1/6 Figure", "high", 640),
        ("Hot Toys", "Marvel MCU", "Iron Man Hulkbuster 1.0 (Age of Ultron)", "1/6 Figure", "grail", 1800),
        ("Hot Toys", "Marvel MCU", "Iron Man Hulkbuster 2.0 (Infinity War)", "1/6 Figure", "grail", 1600),
        ("Hot Toys", "Marvel MCU", "Iron Man Nanotech Suit (Infinity War) Standard", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Marvel MCU", "Iron Man Nanotech Suit (Infinity War) Deluxe", "1/6 Figure", "high", 550),
        ("Hot Toys", "Marvel MCU", "Iron Man MK85 (Sideshow Exclusive)", "1/6 Figure", "high", 620),
        ("Hot Toys", "Marvel MCU", "Iron Man MK3 (Die-Cast, Sideshow Exclusive)", "1/6 Figure", "high", 780),
        ("Hot Toys", "Marvel MCU", "Iron Man MK50 (Toy Fair Exclusive)", "1/6 Figure", "high", 680),

        # ─── Spider-Man — Standard / Deluxe / Exclusive Variants ──────────
        ("Hot Toys", "Marvel MCU", "Spider-Man (Homecoming) Standard", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Homecoming) Deluxe", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Marvel MCU", "Spider-Man (No Way Home Integrated Suit) Deluxe", "1/6 Figure", "mid", 430),
        ("Hot Toys", "Marvel MCU", "Spider-Man (No Way Home Black & Gold) Standard", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Marvel MCU", "Spider-Man (No Way Home Upgraded Suit) Standard", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Marvel MCU", "Spider-Man (No Way Home Upgraded Suit) Deluxe", "1/6 Figure", "mid", 440),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Iron Spider) Standard", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Iron Spider) Deluxe", "1/6 Figure", "mid", 460),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Symbiote Suit) Deluxe", "1/6 Figure", "mid", 440),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Iron Spider, Sideshow Exclusive)", "1/6 Figure", "high", 520),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Homecoming, Toy Fair Exclusive)", "1/6 Figure", "high", 550),

        # ─── Captain America — Standard / Deluxe Variants ─────────────────
        ("Hot Toys", "Marvel MCU", "Captain America (Endgame) Standard", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Captain America (Endgame) Deluxe w/ Mjolnir", "1/6 Figure", "mid", 480),
        ("Hot Toys", "Marvel MCU", "Captain America (Stealth Suit) Standard", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Marvel MCU", "Captain America (Stealth Suit) Deluxe", "1/6 Figure", "mid", 430),
        ("Hot Toys", "Marvel MCU", "Sam Wilson Captain America Standard", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Sam Wilson Captain America Deluxe", "1/6 Figure", "mid", 460),
        ("Hot Toys", "Marvel MCU", "Captain America (Endgame, Sideshow Exclusive)", "1/6 Figure", "high", 560),

        # ─── Thor — Standard / Deluxe Variants ────────────────────────────
        ("Hot Toys", "Marvel MCU", "Thor (Endgame) Standard", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Marvel MCU", "Thor (Endgame) Deluxe (Fat Thor)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Marvel MCU", "Thor (Love and Thunder) Standard", "1/6 Figure", "mid", 300),
        ("Hot Toys", "Marvel MCU", "Thor (Love and Thunder) Deluxe", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Marvel MCU", "Thor (Ragnarok Gladiator) Standard", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Marvel MCU", "Thor (Ragnarok Gladiator) Deluxe", "1/6 Figure", "mid", 450),

        # ─── Thanos — Standard / Deluxe Variants ──────────────────────────
        ("Hot Toys", "Marvel MCU", "Thanos (Endgame) Standard", "1/6 Figure", "mid", 480),
        ("Hot Toys", "Marvel MCU", "Thanos (Endgame) Deluxe (Battle Damaged)", "1/6 Figure", "high", 630),
        ("Hot Toys", "Marvel MCU", "Thanos (Infinity War) Standard", "1/6 Figure", "mid", 500),
        ("Hot Toys", "Marvel MCU", "Thanos (Infinity War) Deluxe", "1/6 Figure", "high", 650),
        ("Hot Toys", "Marvel MCU", "Thanos (Endgame, Sideshow Exclusive)", "1/6 Figure", "high", 720),

        # ─── Black Panther — Standard / Deluxe Variants ───────────────────
        ("Hot Toys", "Marvel MCU", "Black Panther (Civil War) Standard", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Marvel MCU", "Black Panther (Civil War) Deluxe", "1/6 Figure", "mid", 470),
        ("Hot Toys", "Marvel MCU", "Black Panther (Wakanda Forever) Deluxe", "1/6 Figure", "mid", 450),
        ("Hot Toys", "Marvel MCU", "Shuri as Black Panther (Wakanda Forever) Standard", "1/6 Figure", "mid", 370),
        ("Hot Toys", "Marvel MCU", "Shuri as Black Panther (Wakanda Forever) Deluxe", "1/6 Figure", "mid", 490),

        # ─── Darth Vader — Standard / Deluxe / Exclusive Variants ─────────
        ("Hot Toys", "Star Wars", "Darth Vader (ESB) Standard", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "Darth Vader (ESB) Deluxe", "1/6 Figure", "high", 520),
        ("Hot Toys", "Star Wars", "Darth Vader (ROTJ) Standard", "1/6 Figure", "mid", 390),
        ("Hot Toys", "Star Wars", "Darth Vader (ROTJ) Deluxe w/ Throne", "1/6 Figure", "high", 600),
        ("Hot Toys", "Star Wars", "Darth Vader (Rogue One) Deluxe", "1/6 Figure", "mid", 500),
        ("Hot Toys", "Star Wars", "Darth Vader (Obi-Wan Show) Standard", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "Darth Vader (Obi-Wan Show) Deluxe", "1/6 Figure", "mid", 500),
        ("Hot Toys", "Star Wars", "Darth Vader (ESB, Sideshow Exclusive)", "1/6 Figure", "high", 650),

        # ─── Mandalorian — Standard / Deluxe Variants ─────────────────────
        ("Hot Toys", "Star Wars", "The Mandalorian (Beskar) Standard", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Star Wars", "The Mandalorian (Beskar) Deluxe w/ Grogu", "1/6 Figure", "mid", 470),
        ("Hot Toys", "Star Wars", "The Mandalorian (S3 Armor) Standard", "1/6 Figure", "mid", 370),
        ("Hot Toys", "Star Wars", "The Mandalorian (S3 Armor) Deluxe", "1/6 Figure", "mid", 490),
        ("Hot Toys", "Star Wars", "The Mandalorian (Hot Toys Exclusive Chrome)", "1/6 Figure", "high", 580),

        # ─── Boba Fett — Standard / Deluxe / Exclusive Variants ──────────
        ("Hot Toys", "Star Wars", "Boba Fett (ESB) Standard", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Star Wars", "Boba Fett (ESB) Deluxe", "1/6 Figure", "mid", 480),
        ("Hot Toys", "Star Wars", "Boba Fett (ROTJ) Standard", "1/6 Figure", "mid", 370),
        ("Hot Toys", "Star Wars", "Boba Fett (ROTJ) Deluxe w/ Sarlacc Base", "1/6 Figure", "high", 550),
        ("Hot Toys", "Star Wars", "Boba Fett (Book of Boba Fett) Standard", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Star Wars", "Boba Fett (Book of Boba Fett) Deluxe w/ Throne", "1/6 Figure", "high", 520),
        ("Hot Toys", "Star Wars", "Boba Fett (ESB, Sideshow Exclusive)", "1/6 Figure", "high", 600),

        # ─── Luke Skywalker — Standard / Deluxe Variants ─────────────────
        ("Hot Toys", "Star Wars", "Luke Skywalker (ESB) Standard", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Star Wars", "Luke Skywalker (ESB) Deluxe w/ Yoda", "1/6 Figure", "mid", 480),
        ("Hot Toys", "Star Wars", "Luke Skywalker (ROTJ) Standard", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Star Wars", "Luke Skywalker (ROTJ) Deluxe w/ Endor Speeder", "1/6 Figure", "high", 580),
        ("Hot Toys", "Star Wars", "Luke Skywalker (The Mandalorian) Standard", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "Luke Skywalker (The Mandalorian) Deluxe w/ Grogu", "1/6 Figure", "mid", 500),

        # ─── Joker — Standard / DX / Exclusive Variants ──────────────────
        ("Hot Toys", "DC", "Joker (Heath Ledger TDK) Standard", "1/6 Figure", "mid", 400),
        ("Hot Toys", "DC", "Joker (Heath Ledger TDK) DX Edition", "1/6 Figure", "grail", 1200),
        ("Hot Toys", "DC", "Joker (Heath Ledger TDK, Toy Fair Exclusive)", "1/6 Figure", "grail", 1500),
        ("Hot Toys", "DC", "Joker (Joaquin Phoenix) Standard", "1/6 Figure", "mid", 370),
        ("Hot Toys", "DC", "Joker (Joaquin Phoenix) Deluxe w/ Stair Diorama", "1/6 Figure", "mid", 500),
        ("Hot Toys", "DC", "Joker (Jack Nicholson Batman 1989) Standard", "1/6 Figure", "high", 650),
        ("Hot Toys", "DC", "Joker (Jack Nicholson Batman 1989) DX Edition", "1/6 Figure", "grail", 1100),

        # ─── Batman — Standard / DX / Deluxe / Exclusive Variants ────────
        ("Hot Toys", "DC", "Batman (TDK) Standard", "1/6 Figure", "mid", 380),
        ("Hot Toys", "DC", "Batman (TDK) DX Edition", "1/6 Figure", "high", 700),
        ("Hot Toys", "DC", "Batman (BvS) Standard", "1/6 Figure", "mid", 350),
        ("Hot Toys", "DC", "Batman (BvS) Deluxe w/ Kryptonite Spear", "1/6 Figure", "mid", 480),
        ("Hot Toys", "DC", "Batman (Ben Affleck, Sideshow Exclusive)", "1/6 Figure", "high", 560),
        ("Hot Toys", "DC", "Batman (Robert Pattinson) Standard", "1/6 Figure", "mid", 340),
        ("Hot Toys", "DC", "Batman (Robert Pattinson) Deluxe w/ Bat-Signal", "1/6 Figure", "mid", 460),
        ("Hot Toys", "DC", "Batman (Michael Keaton 1989) Standard", "1/6 Figure", "high", 620),
        ("Hot Toys", "DC", "Batman (Michael Keaton 1989) Deluxe", "1/6 Figure", "high", 780),
        ("Hot Toys", "DC", "Batman (Michael Keaton 1989, Sideshow Exclusive)", "1/6 Figure", "grail", 950),
        ("Hot Toys", "DC", "Batman (TDK, Toy Fair Exclusive)", "1/6 Figure", "high", 800),

        # ─── John Wick — Chapter Variants ─────────────────────────────────
        ("Hot Toys", "John Wick", "John Wick (Chapter 2) Standard", "1/6 Figure", "mid", 370),
        ("Hot Toys", "John Wick", "John Wick (Chapter 2) Deluxe", "1/6 Figure", "mid", 480),
        ("Hot Toys", "John Wick", "John Wick (Chapter 3) Standard", "1/6 Figure", "mid", 360),
        ("Hot Toys", "John Wick", "John Wick (Chapter 3) Deluxe w/ Dog", "1/6 Figure", "mid", 490),
        ("Hot Toys", "John Wick", "John Wick (Chapter 4) Standard", "1/6 Figure", "mid", 370),
        ("Hot Toys", "John Wick", "John Wick (Chapter 4) Deluxe w/ Dragon's Breath", "1/6 Figure", "mid", 500),
        ("Hot Toys", "John Wick", "John Wick (Chapter 4, Sideshow Exclusive)", "1/6 Figure", "high", 580),

        # ─── Predator — Variant Editions ──────────────────────────────────
        ("Hot Toys", "Predator", "Classic Predator (1987) Standard", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Predator", "Classic Predator (1987) Deluxe w/ Trophy Wall", "1/6 Figure", "high", 580),
        ("Hot Toys", "Predator", "City Hunter Predator Standard", "1/6 Figure", "mid", 440),
        ("Hot Toys", "Predator", "City Hunter Predator Deluxe", "1/6 Figure", "high", 580),
        ("Hot Toys", "Predator", "Jungle Hunter Predator Standard", "1/6 Figure", "mid", 430),
        ("Hot Toys", "Predator", "Jungle Hunter Predator Deluxe w/ Diorama", "1/6 Figure", "high", 600),
        ("Hot Toys", "Predator", "Classic Predator (Sideshow Exclusive)", "1/6 Figure", "high", 650),

        # ─── Alien — Variant Editions ─────────────────────────────────────
        ("Hot Toys", "Alien", "Alien Big Chap Standard", "1/6 Figure", "mid", 440),
        ("Hot Toys", "Alien", "Alien Big Chap Deluxe w/ Facehugger & Egg", "1/6 Figure", "high", 580),
        ("Hot Toys", "Alien", "Xenomorph Warrior (Aliens 1986) Standard", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Alien", "Xenomorph Warrior (Aliens 1986) Deluxe", "1/6 Figure", "high", 540),
        ("Hot Toys", "Alien", "Alien Big Chap (Sideshow Exclusive)", "1/6 Figure", "high", 620),

        # ─── Sideshow Exclusive Editions — Various ────────────────────────
        ("Sideshow", "Marvel", "Spider-Man Premium Format (Sideshow Exclusive)", "Premium Format", "high", 850),
        ("Sideshow", "Marvel", "Wolverine Premium Format (Sideshow Exclusive)", "Premium Format", "high", 800),
        ("Sideshow", "Marvel", "Hulk Premium Format (Sideshow Exclusive)", "Premium Format", "high", 900),
        ("Sideshow", "Marvel", "Venom Premium Format (Sideshow Exclusive)", "Premium Format", "high", 820),
        ("Sideshow", "Marvel", "Captain America Premium Format (Sideshow Exclusive)", "Premium Format", "high", 850),
        ("Sideshow", "DC", "Batman Premium Format (Sideshow Exclusive)", "Premium Format", "high", 780),
        ("Sideshow", "DC", "Joker Premium Format (Sideshow Exclusive)", "Premium Format", "high", 800),
        ("Sideshow", "DC", "Catwoman Premium Format (Sideshow Exclusive)", "Premium Format", "high", 750),
        ("Sideshow", "Star Wars", "Darth Vader Premium Format (Sideshow Exclusive)", "Premium Format", "high", 900),
        ("Sideshow", "Star Wars", "Boba Fett Premium Format (Sideshow Exclusive)", "Premium Format", "high", 800),
        ("Sideshow", "Predator", "Predator Maquette (Sideshow Exclusive)", "Maquette", "grail", 1100),
        ("Sideshow", "Alien", "Alien Queen Maquette (Sideshow Exclusive)", "Maquette", "grail", 1900),

        # ─── McFarlane DC Multiverse — Additional ───────────────────────
        ("McFarlane", "DC", "McFarlane Batman (Hush) 7-inch", "7-inch Figure", "standard", 25),
        ("McFarlane", "DC", "McFarlane Superman (Action Comics #1000) 7-inch", "7-inch Figure", "standard", 25),
        ("McFarlane", "DC", "McFarlane Nightwing (Better Than Batman) 7-inch", "7-inch Figure", "standard", 25),
        ("McFarlane", "DC", "McFarlane Deathstroke (Arkham Origins) 7-inch", "7-inch Figure", "standard", 28),
        ("McFarlane", "DC", "McFarlane Harley Quinn (Classic) 7-inch", "7-inch Figure", "standard", 25),
        ("McFarlane", "DC", "McFarlane Green Lantern (John Stewart) 7-inch", "7-inch Figure", "standard", 25),
        ("McFarlane", "DC", "McFarlane Flash (Wally West) 7-inch", "7-inch Figure", "standard", 25),

        # ─── threezero Transformers — Additional ────────────────────────
        ("threezero", "Transformers", "threezero Optimus Prime DLX (Bumblebee Movie)", "DLX Figure", "mid", 320),
        ("threezero", "Transformers", "threezero Bumblebee DLX (Bumblebee Movie)", "DLX Figure", "mid", 280),
        ("threezero", "Transformers", "threezero Megatron DLX (Bumblebee Movie)", "DLX Figure", "mid", 310),
        ("threezero", "Transformers", "threezero Starscream DLX (Bumblebee Movie)", "DLX Figure", "mid", 300),
        ("threezero", "Transformers", "threezero Soundwave DLX (Bumblebee Movie)", "DLX Figure", "mid", 290),
        ("threezero", "Transformers", "threezero Optimus Prime MDLX (G1)", "MDLX Figure", "mid", 200),

        # ─── Kotobukiya Bishoujo — Additional ──────────────────────────
        ("Kotobukiya", "Marvel", "Kotobukiya Bishoujo Black Cat 1/7", "Bishoujo Statue", "mid", 180),
        ("Kotobukiya", "Marvel", "Kotobukiya Bishoujo Spider-Gwen 1/7", "Bishoujo Statue", "mid", 190),
        ("Kotobukiya", "Marvel", "Kotobukiya Bishoujo Jean Grey 1/7", "Bishoujo Statue", "mid", 170),
        ("Kotobukiya", "DC", "Kotobukiya Bishoujo Catwoman (Returns) 1/7", "Bishoujo Statue", "mid", 180),
        ("Kotobukiya", "DC", "Kotobukiya Bishoujo Poison Ivy 1/7", "Bishoujo Statue", "mid", 175),
        ("Kotobukiya", "DC", "Kotobukiya Bishoujo Batgirl 1/7", "Bishoujo Statue", "mid", 170),

        # ─── Good Smile Nendoroids (Marvel/DC) ─────────────────────────
        ("Good Smile", "Marvel", "Nendoroid Spider-Man (Miles Morales) #1180", "Nendoroid", "standard", 55),
        ("Good Smile", "Marvel", "Nendoroid Deadpool (Orechan Edition) #662", "Nendoroid", "standard", 60),
        ("Good Smile", "DC", "Nendoroid Batman (1989 Ver.) #1694", "Nendoroid", "standard", 58),
        ("Good Smile", "DC", "Nendoroid Wonder Woman (Hero's Edition) #818", "Nendoroid", "standard", 55),
    ]

    catalog = []
    for brand, franchise, name, figure_type, tier, price in items:
        catalog.append({
            "brand": brand,
            "franchise": franchise,
            "name": name,
            "figure_type": figure_type,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def _batch_expansion_round2() -> list[dict]:
    """Batch 10 — ~105 new items: more Marvel (Spider-Man variants, Thanos,
    Doctor Strange, Moon Knight), more Star Wars (Obi-Wan, Boba Fett, Ahsoka),
    more DC (The Batman, Joker), movie icons (John Wick, Indiana Jones,
    Terminator T-800), more 1/4 scale pieces, DX editions, Cosbaby sets."""

    items = [
        # ─── Marvel MCU — Spider-Man Variants ────────────────────────────
        ("Hot Toys", "Marvel MCU", "Spider-Man (Upgraded Suit Far From Home)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Stealth Suit Far From Home)", "1/6 Figure", "mid", 310),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Red & Blue Suit NWH)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Friendly Neighborhood NWH)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Spider-Man (New Red & Blue Suit NWH) Deluxe", "1/6 Figure", "mid", 460),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Classic Suit NWH) 1/4 Scale", "1/4 Figure", "grail", 950),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Cyborg Spider-Man Suit)", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Marvel MCU", "Spider-Man (Velocity Suit PS4)", "1/6 Figure", "mid", 340),

        # ─── Marvel MCU — Thanos Variants ────────────────────────────────
        ("Hot Toys", "Marvel MCU", "Thanos (Infinity War, Full Gauntlet) 1/4 Scale", "1/4 Figure", "grail", 1500),
        ("Hot Toys", "Marvel MCU", "Thanos (Endgame, Nano Gauntlet)", "1/6 Figure", "mid", 500),
        ("Hot Toys", "Marvel MCU", "Thanos (Endgame Throne) Diorama Set", "Diorama", "grail", 1300),

        # ─── Marvel MCU — Doctor Strange Variants ────────────────────────
        ("Hot Toys", "Marvel MCU", "Doctor Strange (MoM, Third Eye)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Doctor Strange (Endgame Final Battle)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Marvel MCU", "Doctor Strange (Battle on Titan IW)", "1/6 Figure", "mid", 370),
        ("Hot Toys", "Marvel MCU", "Defender Strange (MoM)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Marvel MCU", "Doctor Strange (MoM) Deluxe w/ Dreamwalker Book", "1/6 Figure", "mid", 460),
        ("Hot Toys", "Marvel MCU", "Doctor Strange 1/4 Scale (Infinity War)", "1/4 Figure", "high", 900),

        # ─── Marvel MCU — Moon Knight Variants ───────────────────────────
        ("Hot Toys", "Marvel MCU", "Moon Knight (Ceremonial Armor)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Marc Spector (Moon Knight Show)", "1/6 Figure", "mid", 300),
        ("Hot Toys", "Marvel MCU", "Scarlet Scarab (Layla El-Faouly)", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Marvel MCU", "Moon Knight & Scarlet Scarab 2-Pack", "1/6 Figure", "high", 600),

        # ─── Star Wars — Obi-Wan Kenobi Variants ────────────────────────
        ("Hot Toys", "Star Wars", "Obi-Wan Kenobi (Wandering Jedi)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "Obi-Wan Kenobi (Clone Wars Animated)", "1/6 Figure", "mid", 390),
        ("Hot Toys", "Star Wars", "Obi-Wan Kenobi (AOTC)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Star Wars", "Obi-Wan Kenobi (Battle of Mustafar ROTS)", "1/6 Figure", "mid", 430),
        ("Hot Toys", "Star Wars", "Obi-Wan Kenobi (Ewan McGregor) DX Edition", "1/6 Figure", "high", 700),
        ("Hot Toys", "Star Wars", "Obi-Wan Kenobi 1/4 Scale (ROTS)", "1/4 Figure", "grail", 1050),

        # ─── Star Wars — Boba Fett Extended ──────────────────────────────
        ("Hot Toys", "Star Wars", "Boba Fett (Attack of the Clones, Young)", "1/6 Figure", "mid", 300),
        ("Hot Toys", "Star Wars", "Boba Fett (Animation Version, Holiday Special)", "1/6 Figure", "high", 550),
        ("Hot Toys", "Star Wars", "Boba Fett (Retro Color SDCC Exclusive)", "1/6 Figure", "high", 580),
        ("Hot Toys", "Star Wars", "Boba Fett 1/4 Scale (ESB)", "1/4 Figure", "grail", 1100),

        # ─── Star Wars — Ahsoka Extended ─────────────────────────────────
        ("Hot Toys", "Star Wars", "Ahsoka Tano (Clone Wars Season 7)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Star Wars", "Ahsoka Tano (Rebels)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "Ahsoka Tano (Ahsoka Show) DX Edition", "1/6 Figure", "high", 650),
        ("Hot Toys", "Star Wars", "Ahsoka & Sabine Wren 2-Pack (Ahsoka Show)", "1/6 Figure", "high", 750),

        # ─── DC — The Batman Extended ────────────────────────────────────
        ("Hot Toys", "DC", "Batman (The Batman) with Bat-Signal Diorama", "Diorama", "high", 700),
        ("Hot Toys", "DC", "Batman (The Batman) Unmask Version DX", "1/6 Figure", "high", 600),
        ("Hot Toys", "DC", "Selina Kyle (Catwoman The Batman) Deluxe", "1/6 Figure", "mid", 450),
        ("Hot Toys", "DC", "Batman (The Batman 2022) 1/4 Scale", "1/4 Figure", "grail", 1050),
        ("Hot Toys", "DC", "Batmobile (The Batman) 1/6 Vehicle", "1/6 Vehicle", "grail", 1800),

        # ─── DC — Joker Extended ─────────────────────────────────────────
        ("Hot Toys", "DC", "Joker (Jared Leto Suicide Squad)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "DC", "Joker (Jared Leto Purple Coat)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "DC", "Joker (Joaquin Phoenix Folie a Deux)", "1/6 Figure", "mid", 360),
        ("Hot Toys", "DC", "Joker (Heath Ledger TDK) DX Reissue 2024", "1/6 Figure", "grail", 1300),
        ("Hot Toys", "DC", "Joker (Heath Ledger) 1/4 Scale Deluxe", "1/4 Figure", "grail", 1400),

        # ─── Movie Icons — John Wick Extended ───────────────────────────
        ("Hot Toys", "John Wick", "John Wick (Chapter 1) Deluxe w/ Dog", "1/6 Figure", "mid", 500),
        ("Hot Toys", "John Wick", "John Wick (Chapter 4 Tactical Gear)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "John Wick", "John Wick 1/4 Scale (Chapter 4)", "1/4 Figure", "grail", 950),

        # ─── Movie Icons — Indiana Jones Extended ────────────────────────
        ("Hot Toys", "Indiana Jones", "Indiana Jones (Crystal Skull)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Indiana Jones", "Indiana Jones (Raiders) DX Edition", "1/6 Figure", "high", 700),
        ("Hot Toys", "Indiana Jones", "Indiana Jones 1/4 Scale (Raiders Classic)", "1/4 Figure", "grail", 1100),
        ("Hot Toys", "Indiana Jones", "Short Round (Temple of Doom)", "1/6 Figure", "mid", 320),

        # ─── Movie Icons — Terminator T-800 Extended ─────────────────────
        ("Hot Toys", "Terminator", "T-800 (T2, Leather Jacket)", "1/6 Figure", "high", 600),
        ("Hot Toys", "Terminator", "T-800 Endoskeleton (Die-Cast)", "1/6 Figure", "high", 680),
        ("Hot Toys", "Terminator", "T-800 (Terminator 2) 1/4 Scale", "1/4 Figure", "grail", 1200),
        ("Hot Toys", "Terminator", "T-800 (Cyberdyne Showdown T2)", "1/6 Figure", "high", 580),
        ("Hot Toys", "Terminator", "T-1000 (Liquid Metal) Deluxe", "1/6 Figure", "high", 600),

        # ─── 1/4 Scale Pieces — Additional ───────────────────────────────
        ("Hot Toys", "Marvel MCU", "Hulk (Endgame Smart Hulk) 1/4 Scale", "1/4 Figure", "grail", 1300),
        ("Hot Toys", "Marvel MCU", "Black Panther (Civil War) 1/4 Scale", "1/4 Figure", "grail", 950),
        ("Hot Toys", "Marvel MCU", "Captain America (Endgame) 1/4 Scale", "1/4 Figure", "grail", 1100),
        ("Hot Toys", "Marvel MCU", "War Machine Mark III 1/4 Scale", "1/4 Figure", "grail", 1050),
        ("Hot Toys", "DC", "Darkseid 1/4 Scale (Zack Snyder JL)", "1/4 Figure", "grail", 1400),
        ("Hot Toys", "DC", "Superman (Henry Cavill) 1/4 Scale", "1/4 Figure", "grail", 1100),
        ("Hot Toys", "Star Wars", "Darth Vader (ESB) 1/4 Scale", "1/4 Figure", "grail", 1200),
        ("Hot Toys", "Star Wars", "The Mandalorian 1/4 Scale (Beskar)", "1/4 Figure", "grail", 1000),
        ("Hot Toys", "Star Wars", "Darth Maul (TPM) 1/4 Scale", "1/4 Figure", "grail", 1150),

        # ─── DX Editions — Additional ────────────────────────────────────
        ("Hot Toys", "Marvel MCU", "Iron Man Mark V (Suitcase Armor) DX", "1/6 Figure", "high", 750),
        ("Hot Toys", "Marvel MCU", "Captain America (Avengers) DX Edition", "1/6 Figure", "high", 700),
        ("Hot Toys", "Star Wars", "Darth Vader DX07 (ANH)", "1/6 Figure", "grail", 1600),
        ("Hot Toys", "Star Wars", "Luke Skywalker DX25 (Crait Deluxe)", "1/6 Figure", "high", 650),
        ("Hot Toys", "Star Wars", "Emperor Palpatine DX Edition (ROTJ)", "1/6 Figure", "high", 700),
        ("Hot Toys", "DC", "Batman (Begins) DX Edition", "1/6 Figure", "high", 800),
        ("Hot Toys", "DC", "Two-Face (Harvey Dent TDK) DX Edition", "1/6 Figure", "high", 700),

        # ─── Cosbaby Sets — Additional ───────────────────────────────────
        ("Hot Toys", "Marvel MCU", "Guardians of the Galaxy Vol 3 Cosbaby Set", "Cosbaby", "standard", 60),
        ("Hot Toys", "Marvel MCU", "Doctor Strange MoM Cosbaby Set", "Cosbaby", "standard", 55),
        ("Hot Toys", "Marvel MCU", "Eternals Cosbaby Full Set", "Cosbaby", "standard", 75),
        ("Hot Toys", "Marvel MCU", "Shang-Chi Cosbaby Set", "Cosbaby", "standard", 50),
        ("Hot Toys", "Marvel MCU", "Black Widow Cosbaby Set", "Cosbaby", "standard", 48),
        ("Hot Toys", "Star Wars", "Ahsoka Series Cosbaby Set (4-Pack)", "Cosbaby", "standard", 55),
        ("Hot Toys", "Star Wars", "Obi-Wan Kenobi Cosbaby Set", "Cosbaby", "standard", 50),
        ("Hot Toys", "DC", "The Batman Cosbaby Set (4-Pack)", "Cosbaby", "standard", 55),
        ("Hot Toys", "DC", "Joker & Harley Quinn Cosbaby Duo", "Cosbaby", "standard", 42),
        ("Hot Toys", "John Wick", "John Wick Cosbaby (Chapter 4)", "Cosbaby", "standard", 28),
        ("Hot Toys", "Indiana Jones", "Indiana Jones Cosbaby (Raiders)", "Cosbaby", "standard", 28),
        ("Hot Toys", "Terminator", "T-800 Cosbaby (Endoskeleton)", "Cosbaby", "standard", 28),

        # ─── XM Studios 1/4 Scale Expansion ──────────────────────────────
        ("XM Studios", "Marvel", "Spider-Man 1/4 Scale Premium", "1/4 Statue", "grail", 1600),
        ("XM Studios", "Marvel", "Venom 1/4 Scale Premium", "1/4 Statue", "grail", 1700),
        ("XM Studios", "Marvel", "Magneto 1/4 Scale Premium", "1/4 Statue", "grail", 1800),
        ("XM Studios", "DC", "Superman 1/4 Scale Premium", "1/4 Statue", "grail", 1600),
        ("XM Studios", "DC", "Flash 1/4 Scale Premium", "1/4 Statue", "grail", 1500),
        ("XM Studios", "DC", "Green Lantern 1/4 Scale Premium", "1/4 Statue", "grail", 1550),

        # ─── Sideshow Legendary Scale ────────────────────────────────────
        ("Sideshow", "Marvel", "Wolverine Legendary Scale", "Legendary Scale", "grail", 3500),
        ("Sideshow", "Marvel", "Iron Man Legendary Scale", "Legendary Scale", "grail", 4000),
        ("Sideshow", "Star Wars", "Darth Vader Legendary Scale", "Legendary Scale", "grail", 4500),
        ("Sideshow", "Star Wars", "Boba Fett Legendary Scale", "Legendary Scale", "grail", 3800),

        # ─── Gentle Giant Mini Busts Expansion ───────────────────────────
        ("Gentle Giant", "Star Wars", "Grand Admiral Thrawn Mini Bust", "Mini Bust", "mid", 200),
        ("Gentle Giant", "Marvel", "Deadpool & Wolverine Mini Bust Set", "Mini Bust", "mid", 220),

        # ─── Additional Figures to Reach 900+ ────────────────────────────
        ("Hot Toys", "Star Wars", "Sabine Wren (Ahsoka Show)", "1/6 Figure", "mid", 370),
        ("Hot Toys", "Star Wars", "Baylan Skoll (Ahsoka Show)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Star Wars", "Shin Hati (Ahsoka Show)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Star Wars", "Yoda (Episode I The Phantom Menace)", "1/6 Figure", "mid", 300),
        ("Hot Toys", "Star Wars", "R2-D2 (A New Hope)", "1/6 Figure", "standard", 250),
        ("Hot Toys", "Star Wars", "C-3PO (A New Hope)", "1/6 Figure", "standard", 270),
        ("Hot Toys", "Marvel MCU", "Nick Fury (The Marvels)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Marvel MCU", "Ant-Man (Quantumania) Standard", "1/6 Figure", "mid", 330),
        ("Hot Toys", "Marvel MCU", "Wasp (Quantumania)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "DC", "Supergirl (The Flash 2023)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "DC", "General Zod (Man of Steel)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Predator", "Feral Predator (Prey 2022)", "1/6 Figure", "mid", 400),

        # ─── Good Smile Company — Scales ────────────────────────────────
        ("Good Smile Company", "Demon Slayer", "Rengoku 1/8 Scale (Flame Breathing)", "1/8 Statue", "high", 250),
        ("Good Smile Company", "Demon Slayer", "Tanjiro Kamado 1/8 Scale (Hinokami Kagura)", "1/8 Statue", "mid", 200),
        ("Good Smile Company", "Jujutsu Kaisen", "Gojo Satoru 1/7 Scale (Hollow Purple)", "1/7 Statue", "high", 280),
        ("Good Smile Company", "Jujutsu Kaisen", "Sukuna 1/7 Scale (Domain Expansion)", "1/7 Statue", "high", 300),
        ("Good Smile Company", "One Piece", "Luffy Gear 5 1/7 Scale", "1/7 Statue", "high", 250),
        ("Good Smile Company", "Attack on Titan", "Levi Ackerman 1/7 Scale (Final Season)", "1/7 Statue", "high", 280),

        # ─── Alter — Premium Anime Scales ───────────────────────────────
        ("Alter", "Fate/Grand Order", "Saber Altria Pendragon 1/7", "1/7 Statue", "high", 250),
        ("Alter", "Re:Zero", "Rem 1/7 Scale (Crystal Dress)", "1/7 Statue", "high", 300),
        ("Alter", "Re:Zero", "Ram 1/7 Scale (Crystal Dress)", "1/7 Statue", "high", 280),
        ("Alter", "Evangelion", "Asuka Langley 1/7 Scale", "1/7 Statue", "high", 250),

        # ─── MegaHouse — Premium ────────────────────────────────────────
        ("MegaHouse", "One Piece", "Portrait of Pirates Kaido (Dragon Form)", "1/8 Statue", "grail", 800),
        ("MegaHouse", "One Piece", "Portrait of Pirates Luffy (Gear 5) LE", "1/8 Statue", "high", 450),
        ("MegaHouse", "One Piece", "Portrait of Pirates Zoro (Enma)", "1/8 Statue", "high", 350),
        ("MegaHouse", "Dragon Ball", "Goku Ultra Instinct Dimension of Dragonball", "1/8 Statue", "high", 300),
        ("MegaHouse", "Naruto", "Naruto Baryon Mode G.E.M. Series", "1/8 Statue", "high", 280),

        # ─── Tsume Art — HQS/Ikigai ────────────────────────────────────
        ("Tsume Art", "Naruto", "Naruto vs Sasuke HQS 1/6 Diorama", "1/6 Diorama", "grail", 1500),
        ("Tsume Art", "Dragon Ball Z", "Goku vs Vegeta HQS 1/6 Diorama", "1/6 Diorama", "grail", 1800),
        ("Tsume Art", "One Piece", "Luffy vs Kaido HQS 1/6 Diorama", "1/6 Diorama", "grail", 2000),
        ("Tsume Art", "Demon Slayer", "Rengoku vs Akaza HQS 1/6 Diorama", "1/6 Diorama", "grail", 1600),

        # ─── Bandai Spirits — Figuarts ZERO ────────────────────────────
        ("Bandai", "One Piece", "Figuarts ZERO Luffy (Gear 5 Extra Battle)", "Figuarts ZERO", "high", 180),
        ("Bandai", "Dragon Ball Super", "Figuarts ZERO Gogeta (Extra Battle)", "Figuarts ZERO", "mid", 120),
        ("Bandai", "Demon Slayer", "Figuarts ZERO Rengoku (Flame Breathing)", "Figuarts ZERO", "mid", 100),
        ("Bandai", "Naruto", "Figuarts ZERO Naruto (Kurama Susanoo Extra Battle)", "Figuarts ZERO", "high", 200),
        ("Bandai", "Jujutsu Kaisen", "Figuarts ZERO Gojo (Unlimited Void)", "Figuarts ZERO", "high", 150),

        # ─── Hot Toys — Deadpool & Wolverine (~12) ─────────────────────────
        ("Hot Toys", "Marvel MCU", "Deadpool (Deadpool & Wolverine)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Marvel MCU", "Wolverine (Deadpool & Wolverine)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Marvel MCU", "Deadpool (Deadpool & Wolverine Deluxe)", "1/6 Figure", "high", 480),
        ("Hot Toys", "Marvel MCU", "Wolverine (Deadpool & Wolverine Deluxe)", "1/6 Figure", "high", 500),
        ("Hot Toys", "Marvel MCU", "Deadpool Corps (Lady Deadpool)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Dogpool (1/6 Life-Size)", "1/6 Figure", "mid", 300),
        ("Hot Toys", "Marvel MCU", "Nicepool", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Marvel MCU", "Cassandra Nova", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Marvel MCU", "TVA Deadpool & Wolverine 2-Pack", "1/6 Figure", "high", 750),
        ("Hot Toys", "Marvel MCU", "Wolverine (Yellow Suit, Brown Belt)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Marvel MCU", "Kidpool", "1/6 Figure", "mid", 280),
        ("Hot Toys", "Marvel MCU", "Headpool (Life-Size)", "Life-Size Bust", "mid", 350),

        # ─── Hot Toys — More MCU (MoM, NWH, Endgame) (~20) ────────────────
        ("Hot Toys", "Marvel MCU", "Doctor Strange (MoM, Third Eye)", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Marvel MCU", "Scarlet Witch (MoM, Dreamwalking)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Marvel MCU", "America Chavez (MoM)", "1/6 Figure", "standard", 280),
        ("Hot Toys", "Marvel MCU", "Spider-Man (NWH, Tobey Maguire)", "1/6 Figure", "high", 600),
        ("Hot Toys", "Marvel MCU", "Spider-Man (NWH, Andrew Garfield)", "1/6 Figure", "high", 550),
        ("Hot Toys", "Marvel MCU", "Spider-Man (NWH, Tom Holland, Final Swing Suit)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Marvel MCU", "Green Goblin (NWH, Willem Dafoe)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Marvel MCU", "Doctor Octopus (NWH)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Marvel MCU", "Electro (NWH, Jamie Foxx)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Tony Stark (Nano Gauntlet, Endgame)", "1/6 Figure", "high", 600),
        ("Hot Toys", "Marvel MCU", "Tony Stark (Infinity Saga, I Am Iron Man)", "1/6 Figure", "high", 700),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark I (Endgame Concept Art)", "1/6 Figure", "high", 500),
        ("Hot Toys", "Marvel MCU", "Pepper Potts (Rescue Armor)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Marvel MCU", "Nano Gauntlet (1/4 Scale Replica)", "1/4 Replica", "high", 350),
        ("Hot Toys", "Marvel MCU", "Infinity Gauntlet (1/4 Scale Replica)", "1/4 Replica", "high", 380),
        ("Hot Toys", "Marvel MCU", "Namor (Wakanda Forever)", "1/6 Figure", "mid", 320),
        ("Hot Toys", "Marvel MCU", "Kang the Conqueror (Quantumania)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "Marvel MCU", "Loki (Season 2, TVA Suit)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "Marvel MCU", "Ms. Marvel (Kamala Khan)", "1/6 Figure", "standard", 270),

        # ─── Hot Toys — Star Wars (Clone Wars, Expanded) (~18) ────────────
        ("Hot Toys", "Star Wars", "Ahsoka Tano (Clone Wars Animated)", "1/6 Figure", "high", 500),
        ("Hot Toys", "Star Wars", "Ahsoka Tano (Live Action, Rosario Dawson)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Star Wars", "Captain Rex (501st Legion)", "1/6 Figure", "high", 550),
        ("Hot Toys", "Star Wars", "Cad Bane (Book of Boba Fett)", "1/6 Figure", "mid", 450),
        ("Hot Toys", "Star Wars", "Cad Bane (Clone Wars)", "1/6 Figure", "high", 480),
        ("Hot Toys", "Star Wars", "Commander Wolffe", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Star Wars", "212th Attack Battalion Clone Trooper", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "501st Legion Clone Trooper (Deluxe)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Star Wars", "ARC Trooper Echo", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Star Wars", "ARC Trooper Fives", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Star Wars", "General Grievous", "1/6 Figure", "high", 600),
        ("Hot Toys", "Star Wars", "Emperor Palpatine (Deluxe)", "1/6 Figure", "mid", 450),
        ("Hot Toys", "Star Wars", "Luke Skywalker (Return of the Jedi, Deluxe)", "1/6 Figure", "mid", 420),
        ("Hot Toys", "Star Wars", "Luke Skywalker (Dark Side, Concept Art)", "1/6 Figure", "high", 500),
        ("Hot Toys", "Star Wars", "Stormtrooper (Chrome, 40th Anniversary)", "1/6 Figure", "high", 650),
        ("Hot Toys", "Star Wars", "Darth Maul (Solo)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Star Wars", "Grand Inquisitor", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Star Wars", "Baylan Skoll (Ahsoka Series)", "1/6 Figure", "mid", 360),

        # ─── Hot Toys — DC (The Batman, Dark Knight DX) (~12) ─────────────
        ("Hot Toys", "DC", "Batman (The Batman, Battinson)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "DC", "Batman & Batcycle (The Batman Set)", "1/6 Figure", "high", 700),
        ("Hot Toys", "DC", "Batmobile (The Batman, 1/6 Vehicle)", "1/6 Vehicle", "grail", 1200),
        ("Hot Toys", "DC", "The Riddler (The Batman, Paul Dano)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "DC", "Catwoman (The Batman, Zoe Kravitz)", "1/6 Figure", "mid", 350),
        ("Hot Toys", "DC", "The Joker DX (Dark Knight, Heath Ledger)", "1/6 Figure", "grail", 1500),
        ("Hot Toys", "DC", "Batman DX (Dark Knight, Christian Bale)", "1/6 Figure", "high", 800),
        ("Hot Toys", "DC", "The Joker (Nurse Outfit, Dark Knight)", "1/6 Figure", "high", 900),
        ("Hot Toys", "DC", "Batman (Batman v Superman, Armored)", "1/6 Figure", "mid", 450),
        ("Hot Toys", "DC", "Superman (Justice League, Henry Cavill)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "DC", "The Flash (Ezra Miller)", "1/6 Figure", "mid", 340),
        ("Hot Toys", "DC", "Aquaman (Jason Momoa, Gold Suit)", "1/6 Figure", "mid", 360),

        # ─── Cosbaby & Artist Mix (~12) ───────────────────────────────────
        ("Hot Toys", "Marvel MCU", "Avengers Endgame Cosbaby Full Set (10)", "Cosbaby", "high", 250),
        ("Hot Toys", "Marvel MCU", "Spider-Man NWH Cosbaby (3-Pack)", "Cosbaby", "mid", 80),
        ("Hot Toys", "Marvel MCU", "Deadpool & Wolverine Cosbaby 2-Pack", "Cosbaby", "mid", 60),
        ("Hot Toys", "Star Wars", "Mandalorian & Grogu Cosbaby", "Cosbaby", "mid", 45),
        ("Hot Toys", "Star Wars", "Ahsoka Cosbaby Set (3)", "Cosbaby", "mid", 70),
        ("Hot Toys", "DC", "The Batman Cosbaby Set", "Cosbaby", "mid", 50),
        ("Hot Toys", "Marvel MCU", "Iron Man Mark LXXXV Artist Mix", "Artist Mix", "mid", 150),
        ("Hot Toys", "Marvel MCU", "Thanos Artist Mix (Glow Eyes)", "Artist Mix", "mid", 180),
        ("Hot Toys", "Marvel MCU", "Groot Artist Mix (Baby, Dancing)", "Artist Mix", "mid", 120),
        ("Hot Toys", "DC", "Joker Artist Mix (Dark Knight)", "Artist Mix", "high", 250),
        ("Hot Toys", "Star Wars", "Yoda Artist Mix (Force Ghost)", "Artist Mix", "mid", 140),
        ("Hot Toys", "Marvel MCU", "Venom Artist Mix (Lethal Protector)", "Artist Mix", "mid", 160),

        # ─── Sideshow Exclusives (~12) ────────────────────────────────────
        ("Sideshow", "Marvel", "Deadpool Premium Format (Exclusive)", "Premium Format", "high", 700),
        ("Sideshow", "Marvel", "Wolverine Premium Format (Brown Suit)", "Premium Format", "high", 650),
        ("Sideshow", "Marvel", "Spider-Man Premium Format (Symbiote)", "Premium Format", "high", 800),
        ("Sideshow", "DC", "Batman Premium Format (Hush)", "Premium Format", "high", 750),
        ("Sideshow", "DC", "Harley Quinn Premium Format (Animated)", "Premium Format", "high", 600),
        ("Sideshow", "Star Wars", "Darth Vader Legendary Scale (Bust)", "Legendary Scale", "grail", 1800),
        ("Sideshow", "Star Wars", "Boba Fett Legendary Scale (Bust)", "Legendary Scale", "grail", 1500),
        ("Sideshow", "Marvel", "Hulk Legendary Scale (Bust)", "Legendary Scale", "grail", 1600),
        ("Sideshow", "Star Wars", "General Grievous 1/6 Diorama", "1/6 Diorama", "high", 600),
        ("Sideshow", "Marvel", "Galactus Maquette", "Maquette", "grail", 2500),
        ("Sideshow", "DC", "Doomsday Maquette", "Maquette", "grail", 1800),
        ("Sideshow", "Marvel", "Silver Surfer Maquette", "Maquette", "high", 900),

        # ─── Anime Premium Statues (~12) ──────────────────────────────────
        ("Tsume Art", "Dragon Ball Z", "Vegeta Final Flash HQS 1/6", "1/6 Diorama", "grail", 1500),
        ("Tsume Art", "Naruto", "Itachi Uchiha Susanoo HQS 1/6", "1/6 Diorama", "grail", 1800),
        ("Tsume Art", "One Piece", "Zoro Ashura HQS+ 1/4", "1/3 Statue", "grail", 2200),
        ("Tsume Art", "Hunter x Hunter", "Gon Transformation HQS 1/6", "1/6 Diorama", "grail", 1600),
        ("Tsume Art", "Bleach", "Ichigo Vasto Lorde HQS 1/6", "1/6 Diorama", "grail", 1400),
        ("MegaHouse", "Dragon Ball Z", "Goku Spirit Bomb P.O.P. 1/4", "1/3 Statue", "high", 500),
        ("MegaHouse", "One Piece", "Whitebeard Edward Newgate P.O.P. MAX", "1/8 Statue", "high", 400),
        ("MegaHouse", "Naruto", "Minato Namikaze G.E.M. (Yellow Flash)", "1/8 Statue", "high", 300),
        ("Prime 1 Studio", "Dragon Ball Z", "Frieza Final Form 1/4", "1/3 Statue", "grail", 1300),
        ("Prime 1 Studio", "Jujutsu Kaisen", "Gojo Satoru (Hollow Purple) 1/4", "1/3 Statue", "grail", 1500),
        ("Prime 1 Studio", "Attack on Titan", "Levi Ackerman 1/4 (Spinning Slash)", "1/3 Statue", "grail", 1400),
        ("Prime 1 Studio", "Chainsaw Man", "Denji (Chainsaw Devil Form) 1/4", "1/3 Statue", "grail", 1200),

        # ─── Movie Icons — Additional (~12) ──────────────────────────────
        ("Hot Toys", "Movies", "John Wick Chapter 4 (Deluxe)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Movies", "John Wick Chapter 4 (Caine, Donnie Yen)", "1/6 Figure", "mid", 360),
        ("Hot Toys", "Movies", "Indiana Jones (Dial of Destiny)", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Movies", "Indiana Jones (Raiders, 40th Anniversary)", "1/6 Figure", "high", 500),
        ("Hot Toys", "Movies", "Terminator T-800 (Battle Damaged DX)", "1/6 Figure", "high", 600),
        ("Hot Toys", "Movies", "RoboCop (Battle Damaged, Diecast)", "1/6 Figure", "high", 550),
        ("Hot Toys", "Movies", "Predator (Jungle Hunter DX)", "1/6 Figure", "high", 650),
        ("Hot Toys", "Movies", "Alien Warrior (Big Chap DX)", "1/6 Figure", "high", 500),
        ("Hot Toys", "Movies", "Back to the Future Marty McFly (Deluxe)", "1/6 Figure", "mid", 400),
        ("Hot Toys", "Movies", "Back to the Future DeLorean (1/6 Vehicle)", "1/6 Vehicle", "grail", 900),
        ("Hot Toys", "Movies", "Ghostbusters Peter Venkman", "1/6 Figure", "mid", 380),
        ("Hot Toys", "Movies", "Ghostbusters Ecto-1 (1/6 Vehicle)", "1/6 Vehicle", "grail", 1100),
    ]

    catalog = []
    for brand, franchise, name, figure_type, tier, price in items:
        catalog.append({
            "brand": brand,
            "franchise": franchise,
            "name": name,
            "figure_type": figure_type,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    brand = item["brand"]
    name = item["name"]
    franchise = item["franchise"]
    figure_type = item["figure_type"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{brand}-{name}"),
        title=name,
        set_code=slugify(franchise),
        brand=brand,
        rarity=item["rarity_tier"].title(),
        notes=f"{brand} | {franchise} | {figure_type}",
        attributes_json={
            "brand": brand,
            "franchise": franchise,
            "figure_type": figure_type,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    figure_type = item["figure_type"]
    edition_scores = {
        "1/6 Figure": 0.6,
        "1/4 Figure": 0.8,
        "1/4 Statue": 0.8,
        "Cosbaby": 0.4,
        "Artist Mix": 0.55,
        "Premium Format": 0.75,
        "Maquette": 0.85,
        "Life-Size Figure": 0.9,
        "Life-Size Bust": 0.95,
        "ARTFX+ Statue": 0.5,
        "ARTFX Premier": 0.6,
        "ARTFX Statue": 0.55,
        "Art Scale Statue": 0.55,
        "Diorama": 0.7,
        "Mini Bust": 0.45,
        "Milestones Statue": 0.6,
        "Legendary Scale": 0.92,
        "1/3 Statue": 0.9,
        "1/4 Replica": 0.7,
        "1/7 Statue": 0.6,
        "1/8 Statue": 0.55,
        "1/6 Diorama": 0.85,
        "Figuarts ZERO": 0.5,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_scores.get(figure_type, 0.5),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Hot Toys catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Hot Toys Import ===")

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

    logger.info(f"\n=== Hot Toys Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
