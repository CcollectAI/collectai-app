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
