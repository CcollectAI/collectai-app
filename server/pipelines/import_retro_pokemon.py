"""
Import retro Pokemon accessories & merchandise data.

Layer 1 (Catalog):  Curated vintage Pokemon accessories → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated catalog of Tiger Electronics, Game Boy accessories,
  TOMY figures, Burger King promos, Hasbro, vintage accessories,
  Bandai figures, fast food promos, vintage plush, electronic toys,
  Japanese exclusives, VHS/DVD media, stationery & school supplies
- Focus on 1990s-2000s era Pokemon merchandise (750+ items)

Usage:
    python -m pipelines.import_retro_pokemon [--dry-run]
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

CATEGORY = "retro_pokemon"


def _variant_expansion() -> list[dict]:
    """Graded, edition, language, sealed-product, and error/misprint variants.

    ~55 items covering:
    - PSA 10 graded versions of key cards
    - 1st Edition vs Unlimited vs Shadowless variants
    - Different language versions (Japanese, English, German, French)
    - Sealed product variants (booster box, booster pack, theme deck)
    - CGC / BGS graded alternatives
    - Error / misprint variants
    """
    # Format matches main catalog: brand, name, condition_note, rarity_tier,
    # price_loose, price_boxed
    _raw = [
        # ── PSA 10 Graded — Key Cards ────────────────────────────────────
        ("PSA", "PSA 10 Base Set 1st Edition Charizard Holo #4", "PSA 10 Gem Mint", "grail", 300000, 420000),
        ("PSA", "PSA 10 Base Set Shadowless Charizard Holo #4", "PSA 10 Gem Mint", "grail", 40000, 55000),
        ("PSA", "PSA 10 Base Set Unlimited Charizard Holo #4", "PSA 10 Gem Mint", "grail", 5000, 8000),
        ("PSA", "PSA 10 Base Set 1st Edition Blastoise Holo #2", "PSA 10 Gem Mint", "grail", 40000, 60000),
        ("PSA", "PSA 10 Base Set 1st Edition Venusaur Holo #15", "PSA 10 Gem Mint", "grail", 30000, 45000),
        ("PSA", "PSA 10 Base Set Shadowless Blastoise Holo #2", "PSA 10 Gem Mint", "grail", 8000, 14000),
        ("PSA", "PSA 10 Base Set Shadowless Venusaur Holo #15", "PSA 10 Gem Mint", "grail", 7000, 12000),
        ("PSA", "PSA 10 Base Set 1st Edition Alakazam Holo #1", "PSA 10 Gem Mint", "grail", 15000, 25000),
        ("PSA", "PSA 10 Base Set 1st Edition Chansey Holo #3", "PSA 10 Gem Mint", "grail", 8000, 14000),
        ("PSA", "PSA 10 Base Set 1st Edition Mewtwo Holo #10", "PSA 10 Gem Mint", "grail", 18000, 28000),
        ("PSA", "PSA 10 Base Set 1st Edition Raichu Holo #14", "PSA 10 Gem Mint", "grail", 6000, 10000),
        ("PSA", "PSA 10 Jungle 1st Edition Flareon Holo #3", "PSA 10 Gem Mint", "grail", 3000, 5500),
        ("PSA", "PSA 10 Fossil 1st Edition Gengar Holo #5", "PSA 10 Gem Mint", "grail", 4000, 7000),
        ("PSA", "PSA 10 Neo Genesis 1st Edition Lugia Holo #9", "PSA 10 Gem Mint", "grail", 15000, 25000),
        ("PSA", "PSA 10 Neo Destiny Shining Charizard 1st Ed #107", "PSA 10 Gem Mint", "grail", 12000, 20000),
        ("PSA", "PSA 10 Gold Star Charizard EX Dragon Frontiers #100", "PSA 10 Gem Mint", "grail", 25000, 40000),

        # ── BGS 9.5 / 10 Graded Alternatives ────────────────────────────
        ("BGS", "BGS 9.5 Base Set 1st Edition Charizard Holo #4", "BGS 9.5 Gem Mint", "grail", 100000, 160000),
        ("BGS", "BGS 10 Base Set 1st Edition Charizard Holo #4 (Pristine)", "BGS 10 Pristine", "grail", 500000, 700000),
        ("BGS", "BGS 9.5 Base Set Shadowless Charizard Holo #4", "BGS 9.5 Gem Mint", "grail", 15000, 25000),
        ("BGS", "BGS 9.5 Neo Genesis 1st Edition Lugia Holo #9", "BGS 9.5 Gem Mint", "grail", 8000, 14000),
        ("BGS", "BGS 9.5 Gold Star Rayquaza EX Deoxys #107", "BGS 9.5 Gem Mint", "grail", 6000, 10000),

        # ── CGC Graded Alternatives ──────────────────────────────────────
        ("CGC", "CGC 9.5 Base Set 1st Edition Charizard Holo #4", "CGC 9.5 Gem Mint", "grail", 80000, 130000),
        ("CGC", "CGC 10 Base Set Shadowless Charizard Holo #4 (Perfect)", "CGC 10 Perfect", "grail", 60000, 90000),
        ("CGC", "CGC 9.5 Neo Destiny Shining Charizard 1st Ed #107", "CGC 9.5 Gem Mint", "grail", 8000, 14000),
        ("CGC", "CGC 9.5 Gym Challenge Blaine's Charizard 1st Ed #2", "CGC 9.5 Gem Mint", "grail", 3000, 5500),
        ("CGC", "CGC 9.5 Skyridge Charizard Holo #H3", "CGC 9.5 Gem Mint", "grail", 4000, 7000),

        # ── 1st Edition vs Unlimited vs Shadowless Variants ──────────────
        ("WOTC", "Base Set 1st Edition Gyarados Holo #6", "Near Mint", "grail", 1000, 2500),
        ("WOTC", "Base Set Shadowless Gyarados Holo #6", "Near Mint", "high", 80, 200),
        ("WOTC", "Base Set Shadowless Mewtwo Holo #10", "Near Mint", "grail", 200, 500),
        ("WOTC", "Base Set Shadowless Alakazam Holo #1", "Near Mint", "grail", 150, 400),
        ("WOTC", "Base Set 1st Edition Ninetales Holo #12", "Near Mint", "grail", 600, 1500),
        ("WOTC", "Base Set Shadowless Ninetales Holo #12", "Near Mint", "high", 60, 160),
        ("WOTC", "Base Set 1st Edition Zapdos Holo #16", "Near Mint", "grail", 800, 2000),
        ("WOTC", "Base Set Shadowless Zapdos Holo #16", "Near Mint", "high", 80, 200),
        ("WOTC", "Base Set 1st Edition Clefairy Holo #5", "Near Mint", "grail", 500, 1200),
        ("WOTC", "Base Set Shadowless Clefairy Holo #5", "Near Mint", "high", 50, 130),

        # ── Language Variants (German, French, Japanese) ─────────────────
        ("WOTC DE", "German Base Set Charizard Holo #4 (Glurak)", "Near Mint", "grail", 400, 1000),
        ("WOTC DE", "German Base Set Blastoise Holo #2 (Turtok)", "Near Mint", "high", 100, 280),
        ("WOTC DE", "German Base Set Venusaur Holo #15 (Bisaflor)", "Near Mint", "high", 80, 220),
        ("WOTC FR", "French Base Set Charizard Holo #4 (Dracaufeu)", "Near Mint", "grail", 350, 900),
        ("WOTC FR", "French Base Set Blastoise Holo #2 (Tortank)", "Near Mint", "high", 90, 250),
        ("WOTC FR", "French Base Set Venusaur Holo #15 (Florizarre)", "Near Mint", "high", 70, 200),
        ("WOTC JP", "Japanese Jungle Flareon Holo #136", "Near Mint", "mid", 25, 65),
        ("WOTC JP", "Japanese Fossil Gengar Holo #94", "Near Mint", "mid", 30, 80),
        ("WOTC JP", "Japanese Team Rocket Dark Charizard Holo #6", "Near Mint", "high", 60, 160),

        # ── Sealed Product Variants ──────────────────────────────────────
        ("WOTC", "Base Set 1st Edition Booster Pack (Light)", "Sealed", "grail", 3000, 5500),
        ("WOTC", "Base Set Theme Deck (2-Player Starter)", "Sealed", "high", 80, 200),
        ("WOTC", "Jungle Theme Deck — Water Blast", "Sealed", "high", 70, 180),
        ("WOTC", "Fossil Theme Deck — Lockdown", "Sealed", "high", 70, 180),
        ("WOTC", "Team Rocket Theme Deck — Trouble", "Sealed", "high", 80, 200),
        ("WOTC", "Neo Genesis Theme Deck — Cold Fusion (Japanese)", "Sealed", "high", 60, 150),
        ("WOTC JP", "Japanese Base Set Booster Box (60 packs)", "Sealed", "grail", 15000, 28000),
        ("WOTC JP", "Japanese Base Set Booster Pack (Sealed)", "Sealed", "grail", 250, 500),
        ("WOTC JP", "Japanese Neo Genesis Booster Box", "Sealed", "grail", 5000, 10000),

        # ── Error / Misprint Variants ────────────────────────────────────
        ("WOTC", "Base Set Vulpix Error (No HP — Stage 1 misprint)", "Near Mint", "grail", 500, 1200),
        ("WOTC", "Jungle Electrode Error (No Symbol 1st Print)", "Near Mint", "high", 80, 200),
        ("WOTC", "Fossil Krabby Error (Prerelease Misprint)", "Near Mint", "grail", 200, 500),
        ("WOTC", "Base Set Red Cheeks Pikachu Error #58", "Near Mint", "high", 60, 160),
        ("WOTC", "Base Set Wartortle Error (Squirtle Stage Misprint)", "Near Mint", "high", 100, 280),
        ("WOTC", "Jungle Butterfree Error ('d' Edition Symbol)", "Near Mint", "high", 60, 160),
    ]

    return [
        {
            "brand": brand,
            "name": name,
            "condition_note": condition_note,
            "rarity_tier": tier,
            "price_loose": price_loose,
            "price_boxed": price_boxed,
        }
        for brand, name, condition_note, tier, price_loose, price_boxed in _raw
    ]


def get_curated_catalog() -> list[dict]:
    """Curated retro Pokemon accessories & merch catalog (750+ items)."""

    # Format: (brand, name, condition_note, rarity_tier, price_loose, price_boxed)
    # rarity_tier: grail (>100), high (50-100), mid (20-50), standard (<20)

    items = [
        # Tiger Electronics Pokedex
        ("Tiger Electronics", "Pokedex (Original 1998)", "Loose working", "mid", 35, 100),
        ("Tiger Electronics", "Pokedex (Deluxe Gold 1999)", "Loose working", "high", 60, 150),
        ("Tiger Electronics", "Pokedex (Johto 2000)", "Loose working", "mid", 30, 90),
        ("Tiger Electronics", "Pokemon Organizer (Pikachu)", "Loose working", "mid", 25, 70),

        # Game Boy Accessories
        ("Nintendo", "Game Boy Link Cable (Original)", "Loose", "standard", 10, 30),
        ("Nintendo", "Game Boy Link Cable (Color/GBC)", "Loose", "standard", 12, 35),
        ("Nintendo", "Game Boy Camera (Yellow)", "Loose", "mid", 25, 60),
        ("Nintendo", "Game Boy Camera (Pokemon Pikachu Ed.)", "Loose", "mid", 40, 80),
        ("Nintendo", "Game Boy Printer", "Loose", "mid", 30, 65),
        ("Nintendo", "Game Boy Carry Case (Pokemon)", "Loose", "standard", 15, 40),
        ("Nintendo", "Game Boy Color (Pokemon Yellow Ed.)", "Loose", "high", 80, 200),
        ("Nintendo", "Game Boy Color (Pokemon Gold/Silver Ed.)", "Loose", "high", 70, 180),
        ("Nintendo", "Game Boy Advance SP (Pikachu Ed.)", "Loose", "high", 100, 250),
        ("Nintendo", "Pokemon Mini Console", "Loose", "high", 60, 150),

        # TOMY Pokemon Figures (Original 151)
        ("TOMY", "Pikachu (TOMY Monster Collection)", "Loose", "standard", 8, 25),
        ("TOMY", "Charizard (TOMY Monster Collection)", "Loose", "mid", 20, 50),
        ("TOMY", "Mewtwo (TOMY Monster Collection)", "Loose", "standard", 12, 35),
        ("TOMY", "Blastoise (TOMY Monster Collection)", "Loose", "standard", 15, 40),
        ("TOMY", "Gengar (TOMY Monster Collection)", "Loose", "mid", 18, 45),
        ("TOMY", "Dragonite (TOMY Monster Collection)", "Loose", "standard", 12, 35),
        ("TOMY", "Mew (TOMY Monster Collection)", "Loose", "mid", 20, 50),
        ("TOMY", "Complete Gen 1 TOMY Set (151 figures)", "Loose", "grail", 400, 1200),

        # Burger King Gold-Plated Pokeball Cards (1999)
        ("Burger King", "Pikachu Gold Card #25 (Pokeball)", "With Pokeball", "mid", 15, 40),
        ("Burger King", "Charizard Gold Card #06 (Pokeball)", "With Pokeball", "mid", 20, 50),
        ("Burger King", "Mewtwo Gold Card #150 (Pokeball)", "With Pokeball", "mid", 15, 40),
        ("Burger King", "Poliwhirl Gold Card #61 (Pokeball)", "With Pokeball", "standard", 10, 30),
        ("Burger King", "Togepi Gold Card #175 (Pokeball)", "With Pokeball", "standard", 12, 35),
        ("Burger King", "Jigglypuff Gold Card #39 (Pokeball)", "With Pokeball", "standard", 10, 30),
        ("Burger King", "Complete Gold Card Set (6 cards)", "All sealed", "high", 60, 150),

        # Pokemon Pikachu Virtual Pet
        ("Nintendo", "Pokemon Pikachu (Virtual Pet Gen 1)", "Loose working", "mid", 25, 80),
        ("Nintendo", "Pokemon Pikachu 2 GS (Color)", "Loose working", "mid", 35, 100),

        # Hasbro Battle Figures
        ("Hasbro", "Pikachu Battle Figure (Electronic)", "Loose", "standard", 12, 35),
        ("Hasbro", "Charizard Battle Figure (Deluxe)", "Loose", "mid", 20, 45),
        ("Hasbro", "Blastoise Battle Figure (Deluxe)", "Loose", "standard", 18, 40),
        ("Hasbro", "Mewtwo Battle Figure (Electronic)", "Loose", "standard", 15, 38),
        ("Hasbro", "Pokemon Battle Arena Playset", "Loose", "mid", 25, 60),
        ("Hasbro", "Pokemon Trainer Belt Set", "Loose", "standard", 15, 40),

        # Card Binders, Playmats & Accessories Vintage
        ("Ultra Pro", "Pokemon Base Set Binder (1999)", "Good condition", "mid", 25, 60),
        ("Ultra Pro", "Pokemon Fossil Set Binder", "Good condition", "mid", 20, 50),
        ("Ultra Pro", "Pokemon Jungle Set Binder", "Good condition", "mid", 20, 50),
        ("Official", "Pokemon League Playmat (1999)", "Good condition", "mid", 30, 70),
        ("Official", "Pokemon TCG Coin Collection Set", "Loose", "standard", 15, 40),
        ("Official", "Pokemon Center Deck Box (Vintage)", "Good condition", "mid", 20, 55),
        ("Official", "Pokemon VHS Cassette: Indigo League Vol 1", "With case", "standard", 10, 25),
        ("Official", "Pokemon Movie 2000 Promo Card Set", "Sealed", "mid", 25, 60),

        # Bandai Pokemon Figures
        ("Bandai", "Pokemon Scale World Kanto Set (10 figures)", "Sealed", "high", 65, 120),
        ("Bandai", "Pokemon Scale World Johto Set (10 figures)", "Sealed", "high", 60, 110),
        ("Bandai", "Shodo Pokemon Vol.1 (Mewtwo/Mew/Pikachu)", "Sealed", "mid", 35, 70),
        ("Bandai", "Shodo Pokemon Vol.2 (Charizard/Dragonite)", "Sealed", "mid", 40, 75),
        ("Bandai", "Pokemon Plamo Mewtwo Model Kit", "Sealed", "mid", 25, 50),
        ("Bandai", "Pokemon Plamo Charizard Model Kit", "Sealed", "mid", 30, 55),
        ("Bandai", "Pokemon Plamo Rayquaza Model Kit", "Sealed", "mid", 35, 60),

        # KFC / McDonald's / Fast Food Promo Items
        ("KFC", "Pokemon Promo Box Set (Australia 1999)", "Complete", "grail", 120, 280),
        ("McDonald's", "Pokemon 25th Anniversary Promo Card Set (Sealed)", "Sealed", "mid", 25, 55),
        ("McDonald's", "Pokemon Happy Meal Toys Complete Set (1999)", "Loose", "mid", 30, 70),
        ("Wendy's", "Pokemon Toys Complete Set (2002)", "Loose", "mid", 20, 50),
        ("McDonald's", "Pikachu Plush (Happy Meal Exclusive 2000)", "With tag", "standard", 10, 30),
        ("Burger King", "Pokemon Beanbag Plush Set (1999)", "Complete set", "mid", 25, 60),

        # Vintage Plush
        ("TOMY", "Talking Pikachu Plush (1998)", "Working", "mid", 25, 65),
        ("Hasbro", "Dancing Pikachu Plush (Electronic)", "Working", "mid", 30, 70),
        ("Hasbro", "Large Pikachu Plush (20 inch, 1999)", "Good condition", "mid", 20, 50),
        ("Pokemon Center", "Mewtwo Plush (Tokyo Exclusive 1999)", "With tag", "high", 60, 140),
        ("Pokemon Center", "Mew Plush (Tokyo Exclusive 1999)", "With tag", "high", 55, 130),
        ("Banpresto", "UFO Catcher Prize Pikachu (Large 1999)", "Good condition", "mid", 30, 70),
        ("Banpresto", "UFO Catcher Prize Eevee (Large 2000)", "Good condition", "mid", 35, 75),
        ("Tomy", "Pocket Monsters Plush Pikachu (Japan 1996)", "With tag", "grail", 100, 250),
        ("Tomy", "Pocket Monsters Plush Charizard (Japan 1996)", "With tag", "grail", 110, 280),

        # Electronic Toys
        ("Tiger Electronics", "Pokemon Cyclone 2 Pinball Game", "Working", "mid", 25, 60),
        ("Tiger Electronics", "Pokemon Thunderbolt Game", "Working", "standard", 18, 45),
        ("Hasbro", "Pokemon Battle Stadium DX", "Working", "mid", 30, 70),
        ("Tiger Electronics", "Pokemon Electronic Catch Em All", "Working", "standard", 15, 40),
        ("Tiger Electronics", "Hit Clips Pokemon (Pikachu Player)", "Working", "mid", 20, 55),

        # Japanese Exclusive Merchandise
        ("Pokemon Center", "Japan Shop Bag (Vintage 1998)", "Good condition", "mid", 25, 55),
        ("Pokemon Center", "Japan Shop Bag (Pikachu Birthday 1999)", "Good condition", "mid", 30, 65),
        ("Shogakukan", "Corocoro Magazine Pokemon Promo Cards (1997)", "Sealed", "high", 50, 120),
        ("Shogakukan", "Corocoro Magazine Mew Promo Attachment", "Sealed", "grail", 80, 200),
        ("TOMY", "Pokemon Zukan 3D Encyclopedia (Kanto Set)", "Complete", "high", 70, 160),
        ("TOMY", "Pokemon Zukan 3D Encyclopedia (Johto Set)", "Complete", "high", 65, 150),
        ("Bandai", "Pokemon Kids Figures Gen 1 Complete Set", "Loose", "grail", 150, 350),
        ("Bandai", "Pokemon Kids Figures (Pikachu/Eevee/Mewtwo)", "Loose", "standard", 8, 25),
        ("Takara Tomy", "MONCOLLE Pikachu (Japan Exclusive)", "Sealed", "standard", 12, 30),
        ("Takara Tomy", "MONCOLLE Charizard (Japan Exclusive)", "Sealed", "standard", 15, 35),
        ("JR East", "Masuda Stamp Rally Prize Pikachu (2001)", "Good condition", "high", 55, 130),

        # VHS / DVD / Media
        ("Viz Video", "Pokemon Indigo League VHS Complete Set (13 tapes)", "With cases", "high", 50, 120),
        ("Warner Bros", "Pokemon The First Movie VHS (Original 1999)", "With case", "standard", 8, 25),
        ("Warner Bros", "Pokemon 2000 The Movie DVD (First Press)", "Sealed", "mid", 20, 45),
        ("Warner Bros", "Mewtwo Returns VHS", "With case", "standard", 10, 30),
        ("Shogakukan", "Pokemon Japanese LaserDisc Box Set", "Complete", "grail", 150, 400),

        # Stationery & School Supplies
        ("Mead", "Pokemon Trapper Keeper Binder (1999)", "Good condition", "mid", 25, 65),
        ("Official", "Pokemon Pencil Case (Japan Exclusive 1998)", "Good condition", "mid", 20, 50),
        ("Merlin", "Pokemon Sticker Album Complete (1999)", "All stickers", "mid", 30, 70),
        ("Topps", "Pokemon Sticker Album Series 1 (Complete)", "All stickers", "mid", 25, 60),
        ("Thermos", "Pokemon Lunchbox (Pikachu 1999)", "Good condition", "mid", 20, 50),
        ("Burger King", "Pokemon Watch (Promo 1999)", "Working", "standard", 12, 35),

        # TOMY Monster Collection: MC line, AG, DX
        ("TOMY", "MC Pikachu (MC-001 Original)", "Loose", "mid", 20, 55),
        ("TOMY", "MC Charizard (MC-006 Original)", "Loose", "mid", 30, 70),
        ("TOMY", "MC Eevee (MC-133)", "Loose", "standard", 12, 35),
        ("TOMY", "MC Lugia (MC-249 Silver)", "Loose", "mid", 25, 60),
        ("TOMY", "AG Blaziken (AG-005)", "Loose", "standard", 15, 40),
        ("TOMY", "AG Rayquaza (AG Series)", "Loose", "mid", 25, 55),
        ("TOMY", "DX Charizard (Deluxe Figure)", "Loose", "mid", 35, 80),
        ("TOMY", "DX Mewtwo (Deluxe Figure)", "Loose", "mid", 30, 70),

        # Pokemon Center Japan exclusives
        ("Pokemon Center", "Monthly Pikachu (January 2015)", "With tag", "mid", 25, 60),
        ("Pokemon Center", "Monthly Pikachu (December 2015 Christmas)", "With tag", "mid", 30, 65),
        ("Pokemon Center", "Costume Pikachu (Kyoto Maiko)", "With tag", "high", 55, 130),
        ("Pokemon Center", "Costume Pikachu (Yokohama Sailor)", "With tag", "high", 50, 120),
        ("Pokemon Center", "Costume Pikachu (Okinawa Shisa)", "With tag", "high", 60, 140),
        ("Pokemon Center", "Life Size Snorlax Plush (150cm)", "Good condition", "grail", 350, 600),
        ("Pokemon Center", "Life Size Eevee Plush (30cm)", "With tag", "high", 80, 150),
        ("Pokemon Center", "Sitting Cuties Pikachu (Original)", "With tag", "standard", 12, 28),
        ("Pokemon Center", "Sitting Cuties Eevee", "With tag", "standard", 12, 28),
        ("Pokemon Center", "Sitting Cuties Complete Kanto Set (151)", "All with tags", "grail", 800, 1500),

        # Pokemon Kids (Bandai finger puppets)
        ("Bandai", "Pokemon Kids Series 1 Pikachu (1996)", "Loose", "mid", 20, 50),
        ("Bandai", "Pokemon Kids Series 1 Charizard (1996)", "Loose", "mid", 25, 60),
        ("Bandai", "Pokemon Kids Series 2 Mewtwo (1997)", "Loose", "mid", 22, 55),
        ("Bandai", "Pokemon Kids Series 3 Lugia (1999)", "Loose", "mid", 20, 50),
        ("Bandai", "Pokemon Kids Series 5 Rayquaza (2003)", "Loose", "standard", 15, 40),
        ("Bandai", "Pokemon Kids Vintage Complete Series 1 (40 figs)", "Loose", "grail", 200, 450),

        # Takara Tomy Arts gashapon
        ("Takara Tomy Arts", "Gashapon Sitting Cuties Pikachu", "Sealed capsule", "standard", 8, 20),
        ("Takara Tomy Arts", "Gashapon Sleeping Pikachu", "Sealed capsule", "standard", 10, 25),
        ("Takara Tomy Arts", "Gashapon Sleeping Eevee", "Sealed capsule", "standard", 10, 25),
        ("Takara Tomy Arts", "Gashapon Sitting Cuties Full Set (Gen 1)", "Sealed", "high", 70, 150),

        # Vintage Western: Hasbro, Jakks Pacific, Electronic Pokedex
        ("Hasbro", "Trainer Figure Ash Ketchum with Pikachu", "Loose", "mid", 20, 50),
        ("Hasbro", "Trainer Figure Misty with Togepi", "Loose", "mid", 22, 55),
        ("Hasbro", "Trainer Figure Brock with Onix", "Loose", "mid", 18, 45),
        ("Jakks Pacific", "Pokemon Diamond & Pearl Figure Set", "Loose", "standard", 15, 35),
        ("Jakks Pacific", "Electronic Pokedex Advanced (2005)", "Working", "mid", 30, 75),
        ("Jakks Pacific", "Deluxe Pikachu Electronic Figure (10 inch)", "Working", "mid", 25, 60),

        # Pokemon stamps & coins
        ("Japan Post", "Pokemon Stamp Sheet (Kanto 151, 2001)", "Mint", "high", 50, 120),
        ("Japan Post", "Pokemon Stamp Sheet (Pikachu New Year 2000)", "Mint", "mid", 30, 70),
        ("Royal Canadian Mint", "Pikachu Silver Coin (2023)", "Sealed", "high", 80, 120),

        # Pokemon Game Boy accessories & consoles
        ("Nintendo", "Pikachu Game Boy Color (Yellow/Blue)", "Loose working", "high", 90, 220),
        ("Nintendo", "Pokemon Mini Console (Pikachu Yellow)", "Loose working", "high", 65, 160),
        ("Nintendo", "e-Reader Cards Pokemon (5 pack sealed)", "Sealed", "mid", 25, 60),
        ("Nintendo", "e-Reader Cards Pokemon Complete Set", "Sealed", "grail", 150, 350),

        # Zukan figures (Bandai Pokemon Zukan)
        ("Bandai", "Pokemon Zukan Charizard Line (1/40 Scale)", "Complete", "high", 60, 130),
        ("Bandai", "Pokemon Zukan Eevee Evolutions Set (1/40 Scale)", "Complete", "grail", 120, 280),
        ("Bandai", "Pokemon Zukan Mewtwo & Mew (1/40 Scale)", "Complete", "high", 55, 120),
        ("Bandai", "Pokemon Zukan Gen 3 Groudon/Kyogre", "Complete", "high", 50, 110),

        # Vintage Japanese 1996-2000 Pocket Monsters items
        ("Tomy", "Pocket Monsters Plush Mew (Japan 1996)", "With tag", "grail", 90, 230),
        ("Tomy", "Pocket Monsters DX Mewtwo (Japan 1998)", "With tag", "high", 70, 170),
        ("Banpresto", "Pocket Monsters Pikachu Diorama (1997)", "Good condition", "high", 60, 140),
        ("Shogakukan", "Pocket Monsters Encyclopedia Book (1996)", "Good condition", "mid", 30, 70),

        # ── Applause & Toy Biz Figures ──────────────────────────────────
        ("Applause", "Pikachu PVC Figure (3 inch, 1999)", "Loose", "standard", 8, 22),
        ("Applause", "Charizard PVC Figure (4 inch, 1999)", "Loose", "standard", 10, 28),
        ("Applause", "Mewtwo PVC Figure (4 inch, 1999)", "Loose", "standard", 10, 25),
        ("Applause", "Jigglypuff PVC Figure (2.5 inch, 1999)", "Loose", "standard", 6, 18),
        ("Toy Biz", "Pokemon Trainer Series Ash & Pikachu", "Loose", "mid", 20, 50),
        ("Toy Biz", "Pokemon Trainer Series Misty & Psyduck", "Loose", "mid", 22, 55),

        # ── Vintage Board Games & Puzzles ────────────────────────────────
        ("Milton Bradley", "Pokemon Master Trainer Board Game (1999)", "Complete", "mid", 25, 65),
        ("Milton Bradley", "Pokemon Master Trainer Board Game (2005 Ed.)", "Complete", "standard", 18, 45),
        ("Hasbro", "Pokemon Yahtzee Jr. (1999)", "Complete", "standard", 12, 30),
        ("Hasbro", "Pokemon Sorry! Board Game (1999)", "Complete", "standard", 15, 40),
        ("Hasbro", "Pokemon Battle Dice Game (2000)", "Complete", "standard", 10, 28),
        ("Buffalo Games", "Pokemon Kanto 151 Puzzle (1000pc, Vintage)", "Sealed", "standard", 15, 35),

        # ── TOMY Pocket Monsters (Japan-only lines) ─────────────────────
        ("TOMY", "Pocket Monsters Wind-Up Pikachu (1996)", "Working", "mid", 25, 60),
        ("TOMY", "Pocket Monsters Wind-Up Charmander (1996)", "Working", "mid", 22, 55),
        ("TOMY", "Pocket Monsters Talking Pokedex JP (1997)", "Working", "high", 50, 120),
        ("TOMY", "Pocket Monsters Battle Dome Playset (1997)", "Complete", "high", 55, 130),
        ("TOMY", "Monster Collection EX Pikachu (Alola Cap)", "Sealed", "standard", 12, 30),

        # ── Topps Chrome & Merlin Cards ──────────────────────────────────
        ("Topps", "Pokemon Series 1 Chrome Complete Set (76 cards)", "Near Mint", "high", 60, 140),
        ("Topps", "Pokemon Series 2 Chrome Complete Set (72 cards)", "Near Mint", "high", 55, 130),
        ("Topps", "Pokemon Series 3 Chrome Complete Set (60 cards)", "Near Mint", "mid", 40, 100),
        ("Merlin", "Pokemon Sticker Collection Series 2 (Complete)", "All stickers", "mid", 25, 55),
        ("Topps", "Pokemon Die-Cut Card Set Series 1", "Near Mint", "mid", 30, 70),

        # ── Jakks Pacific Expanded ──────────────────────────────────────
        ("Jakks Pacific", "Pokemon HeartGold SoulSilver Figure Set", "Loose", "standard", 15, 38),
        ("Jakks Pacific", "Pokemon Black & White Starter 3-Pack", "Sealed", "standard", 18, 42),
        ("Jakks Pacific", "Legendary Dialga Figure (7 inch)", "Loose", "mid", 20, 50),
        ("Jakks Pacific", "Legendary Palkia Figure (7 inch)", "Loose", "mid", 20, 48),
        ("Jakks Pacific", "Ash's Pikachu Talking Figure (2010)", "Working", "mid", 22, 55),

        # ── Pokemon Center Plush Expanded ────────────────────────────────
        ("Pokemon Center", "Charizard Plush (Tokyo DX 2000)", "With tag", "high", 65, 150),
        ("Pokemon Center", "Gengar Plush (Tokyo 1999)", "With tag", "high", 55, 130),
        ("Pokemon Center", "Dragonite Plush (Japan 2001)", "With tag", "mid", 35, 80),
        ("Pokemon Center", "Jolteon Plush (Eevee Collection 2000)", "With tag", "mid", 40, 90),
        ("Pokemon Center", "Vaporeon Plush (Eevee Collection 2000)", "With tag", "mid", 40, 90),
        ("Pokemon Center", "Flareon Plush (Eevee Collection 2000)", "With tag", "mid", 40, 88),
        ("Pokemon Center", "Espeon Plush (Eevee Collection 2001)", "With tag", "mid", 45, 100),
        ("Pokemon Center", "Umbreon Plush (Eevee Collection 2001)", "With tag", "high", 50, 115),

        # ── Vintage Clothing & Accessories ──────────────────────────────
        ("Official", "Pokemon Snap Back Hat (Pikachu 1999)", "Good condition", "mid", 20, 50),
        ("Official", "Pokemon Backpack (Pikachu & Ash 1999)", "Good condition", "mid", 25, 60),
        ("Official", "Pokemon Rain Poncho (Pikachu 1999)", "Good condition", "standard", 12, 30),
        ("Official", "Pokemon Umbrella (Pokeball Design 2000)", "Good condition", "standard", 15, 35),
        ("Official", "Pokemon T-Shirt (Original 151 Vintage 1999)", "Good condition", "mid", 20, 50),

        # ── Banpresto Prize Figures Expanded ─────────────────────────────
        ("Banpresto", "UFO Catcher Charizard (Large 2000)", "Good condition", "mid", 35, 75),
        ("Banpresto", "UFO Catcher Mewtwo (Large 1999)", "Good condition", "mid", 30, 70),
        ("Banpresto", "UFO Catcher Snorlax (XL 2001)", "Good condition", "mid", 40, 85),
        ("Banpresto", "Pokemon Kids DX Lugia Prize (2000)", "Good condition", "mid", 25, 60),
        ("Banpresto", "Pokemon Mega Blastoise Prize Figure (2002)", "Good condition", "mid", 28, 65),

        # ── Trading Figure Series ───────────────────────────────────────
        ("Kaiyodo", "Pokemon Figure Mewtwo Strikes Back Set (2000)", "Complete", "high", 60, 140),
        ("Kaiyodo", "Pokemon Figure Museum Vol.1 (6 figures)", "Complete", "high", 50, 120),
        ("Kaiyodo", "Pokemon Figure Museum Vol.2 (6 figures)", "Complete", "mid", 40, 100),
        ("Kaiyodo", "Pokemon Bottle Cap Collection (Gen 1 Set)", "Complete", "grail", 120, 280),

        # ── Wotc Promo & Misc Cards ─────────────────────────────────────
        ("WOTC", "Ancient Mew Promo Card (Movie 2000)", "Sealed", "mid", 25, 60),
        ("WOTC", "Black Star Promo Pikachu #1", "Near Mint", "mid", 30, 70),
        ("WOTC", "Black Star Promo Mewtwo #3", "Near Mint", "mid", 25, 55),
        ("WOTC", "Black Star Promo Mew #8 (Holo)", "Near Mint", "mid", 35, 80),

        # ── Keychains & Straps ──────────────────────────────────────────
        ("TOMY", "Pokemon Keychain Pikachu (Metal, 1999)", "Good condition", "standard", 8, 22),
        ("TOMY", "Pokemon Keychain Charizard (Metal, 1999)", "Good condition", "standard", 10, 25),
        ("Banpresto", "Pokemon Strap Collection Gen 1 (Gashapon Set)", "Complete", "mid", 30, 70),
        ("Takara Tomy", "Pokemon Netsuke Strap Pikachu (Japan Only)", "Good condition", "standard", 8, 20),

        # ── Miscellaneous Vintage Items ─────────────────────────────────
        ("Official", "Pokemon Center NYC Opening Day Bag (2001)", "Good condition", "high", 60, 140),
        ("Official", "Pokemon League Badge Set (Gen 1 Kanto)", "Complete", "high", 50, 120),
        ("Official", "Pokemon League Badge Set (Gen 2 Johto)", "Complete", "mid", 40, 100),
        ("Official", "Pokemon TCG Damage Counter Dice Set (Vintage)", "Complete", "standard", 10, 25),
        ("Official", "Pokemon Center Osaka Grand Opening Card (2010)", "Sealed", "high", 55, 130),

        # ── WOTC Sealed Product ──────────────────────────────────────────
        ("WOTC", "Base Set Booster Box (Unlimited, 36 packs)", "Sealed", "grail", 8000, 12000),
        ("WOTC", "Base Set 1st Edition Booster Box", "Sealed", "grail", 200000, 350000),
        ("WOTC", "Base Set 1st Edition Booster Pack (Heavy)", "Sealed", "grail", 6000, 10000),
        ("WOTC", "Base Set Unlimited Booster Pack", "Sealed", "grail", 200, 400),
        ("WOTC", "Jungle 1st Edition Booster Box", "Sealed", "grail", 10000, 18000),
        ("WOTC", "Jungle Unlimited Booster Box", "Sealed", "grail", 4000, 7000),
        ("WOTC", "Fossil 1st Edition Booster Box", "Sealed", "grail", 8000, 14000),
        ("WOTC", "Fossil Unlimited Booster Box", "Sealed", "grail", 3500, 6000),
        ("WOTC", "Team Rocket 1st Edition Booster Box", "Sealed", "grail", 12000, 20000),
        ("WOTC", "Base Set 2 Booster Box", "Sealed", "grail", 3000, 5500),
        ("WOTC", "Gym Heroes 1st Edition Booster Box", "Sealed", "grail", 8000, 15000),
        ("WOTC", "Gym Challenge 1st Edition Booster Box", "Sealed", "grail", 10000, 18000),
        ("WOTC", "Neo Genesis 1st Edition Booster Box", "Sealed", "grail", 15000, 25000),
        ("WOTC", "Neo Discovery 1st Edition Booster Box", "Sealed", "grail", 12000, 22000),
        ("WOTC", "Neo Revelation 1st Edition Booster Box", "Sealed", "grail", 10000, 18000),
        ("WOTC", "Neo Destiny 1st Edition Booster Box", "Sealed", "grail", 15000, 28000),
        ("WOTC", "Legendary Collection Booster Box", "Sealed", "grail", 5000, 9000),
        ("WOTC", "Skyridge Booster Box", "Sealed", "grail", 30000, 50000),
        ("WOTC", "Aquapolis Booster Box", "Sealed", "grail", 20000, 35000),
        ("WOTC", "Expedition Base Set Booster Box", "Sealed", "grail", 8000, 15000),

        # ── Japanese Exclusive Promos ────────────────────────────────────
        ("Pokemon Center", "Tropical Mega Battle Trophy Card (Tropical Wind)", "Near Mint", "grail", 30000, 50000),
        ("Pokemon Center", "Tropical Mega Battle Promo Psyduck", "Near Mint", "grail", 5000, 10000),
        ("Pokemon Center", "Grand Party Trophy Card (2000)", "Near Mint", "grail", 8000, 15000),
        ("ANA", "ANA Airlines Pikachu Promo Card (All Nippon)", "Near Mint", "grail", 3000, 6000),
        ("ANA", "ANA Jet Pikachu Promo Set (4 cards)", "Near Mint", "grail", 8000, 14000),
        ("CoroCoro", "CoroCoro Shining Mew Promo", "Near Mint", "grail", 2000, 4000),
        ("CoroCoro", "CoroCoro Promo Imakuni's Doduo", "Near Mint", "high", 80, 200),
        ("CoroCoro", "CoroCoro Comics Promo Mew (Holo)", "Near Mint", "grail", 500, 1200),
        ("CoroCoro", "CoroCoro Promo Porygon (Trade Please)", "Near Mint", "high", 60, 150),
        ("TMB", "Tropical Mega Battle Exeggutor Promo", "Near Mint", "grail", 10000, 20000),

        # ── Pokemon Center Merchandise Expanded ──────────────────────────
        ("Pokemon Center", "Pikachu Pair Plush (Valentine 2000)", "With tag", "mid", 40, 90),
        ("Pokemon Center", "Halloween Pikachu Plush (2001)", "With tag", "mid", 45, 100),
        ("Pokemon Center", "Christmas Pikachu Plush (2000)", "With tag", "mid", 40, 95),
        ("Pokemon Center", "Cherry Blossom Pikachu Plush (2002)", "With tag", "high", 55, 130),
        ("Pokemon Center", "Pokemon Center Tokyo Opening Pikachu (1998)", "With tag", "grail", 200, 450),
        ("Pokemon Center", "Pokemon Center Nagoya Opening Pikachu", "With tag", "high", 80, 180),
        ("Pokemon Center", "Pokemon Center Fukuoka Opening Pikachu", "With tag", "high", 75, 170),
        ("Pokemon Center", "Pokemon Center Sapporo Opening Pikachu", "With tag", "high", 70, 160),
        ("Pokemon Center", "Mew & Mewtwo Strikes Back Pin Set", "Sealed", "mid", 30, 70),
        ("Pokemon Center", "Pokemon Center DX Shibuya Opening Card", "Sealed", "high", 60, 140),

        # ── Burger King Promos Expanded ──────────────────────────────────
        ("Burger King", "Pikachu #25 Plush (Beanbag 1999)", "With tag", "standard", 10, 30),
        ("Burger King", "Charizard Plush (Beanbag 1999)", "With tag", "standard", 12, 35),
        ("Burger King", "Mewtwo Plush (Beanbag 1999)", "With tag", "standard", 10, 28),
        ("Burger King", "Squirtle Squirter Toy (1999)", "Loose", "standard", 6, 18),
        ("Burger King", "Pikachu Light-Up Toy (1999)", "Working", "standard", 8, 22),
        ("Burger King", "Complete Toy Set (57 pieces, 1999)", "Loose", "grail", 120, 300),

        # ── Vintage TOMY Figures Expanded ────────────────────────────────
        ("TOMY", "Gyarados (TOMY Monster Collection)", "Loose", "mid", 25, 60),
        ("TOMY", "Snorlax (TOMY Monster Collection)", "Loose", "standard", 15, 40),
        ("TOMY", "Lapras (TOMY Monster Collection)", "Loose", "standard", 15, 40),
        ("TOMY", "Articuno (TOMY Monster Collection)", "Loose", "standard", 15, 38),
        ("TOMY", "Zapdos (TOMY Monster Collection)", "Loose", "standard", 14, 36),
        ("TOMY", "Moltres (TOMY Monster Collection)", "Loose", "standard", 14, 36),
        ("TOMY", "Machamp (TOMY Monster Collection)", "Loose", "standard", 10, 28),
        ("TOMY", "Alakazam (TOMY Monster Collection)", "Loose", "standard", 12, 32),
        ("TOMY", "Arcanine (TOMY Monster Collection)", "Loose", "standard", 15, 38),
        ("TOMY", "Vaporeon (TOMY Monster Collection)", "Loose", "standard", 12, 35),
        ("TOMY", "Jolteon (TOMY Monster Collection)", "Loose", "standard", 12, 35),
        ("TOMY", "Flareon (TOMY Monster Collection)", "Loose", "standard", 12, 35),
        ("TOMY", "Complete Gen 2 TOMY Set (100 figures)", "Loose", "grail", 300, 900),

        # ── TCG Accessories Expanded ─────────────────────────────────────
        ("Ultra Pro", "Pokemon Team Rocket Binder", "Good condition", "mid", 22, 55),
        ("Ultra Pro", "Pokemon Gym Heroes Binder", "Good condition", "mid", 25, 60),
        ("Ultra Pro", "Pokemon Neo Genesis Binder", "Good condition", "mid", 22, 55),
        ("Official", "Pokemon TCG Booster Box Case (Empty, 1999)", "Good condition", "mid", 30, 70),
        ("Official", "Pokemon League Season 1 Badge Pins Set", "Complete", "mid", 35, 80),
        ("Official", "Pokemon League Energy Card Set (Holo)", "Near Mint", "mid", 20, 50),

        # ── E-Reader Cards ───────────────────────────────────────────────
        ("Nintendo", "e-Reader Pokemon (Expedition Singles Lot)", "Near Mint", "mid", 30, 70),
        ("Nintendo", "e-Reader Pokemon (Aquapolis Singles Lot)", "Near Mint", "mid", 35, 80),
        ("Nintendo", "e-Reader Pokemon (Skyridge Singles Lot)", "Near Mint", "high", 50, 120),
        ("Nintendo", "e-Reader Pokemon Battle-e Card Set", "Sealed", "high", 60, 140),
        ("Nintendo", "e-Reader Pokemon Application Pack", "Sealed", "mid", 40, 90),

        # ── ANA Jet Promos ───────────────────────────────────────────────
        ("ANA", "ANA Jet Pikachu Figure (Limited Edition)", "Sealed", "high", 80, 180),
        ("ANA", "ANA Flying Pikachu Promo Card", "Near Mint", "grail", 1500, 3000),
        ("ANA", "ANA Pikachu Luggage Tag (Promo)", "Good condition", "mid", 30, 70),

        # ── WOTC Black Star Promos Expanded ──────────────────────────────
        ("WOTC", "Black Star Promo Pikachu #4 (Ivy)", "Near Mint", "mid", 25, 55),
        ("WOTC", "Black Star Promo Electabuzz #2 (Movie)", "Near Mint", "mid", 20, 45),
        ("WOTC", "Black Star Promo Dragonite #5 (Movie)", "Near Mint", "mid", 25, 55),
        ("WOTC", "Black Star Promo Jigglypuff #7", "Near Mint", "standard", 15, 35),
        ("WOTC", "Black Star Promo Meowth #10 (GB)", "Near Mint", "standard", 15, 38),
        ("WOTC", "Black Star Promo Eevee #11", "Near Mint", "mid", 20, 50),
        ("WOTC", "Black Star Promo Venusaur #13", "Near Mint", "mid", 30, 70),
        ("WOTC", "Black Star Promo Mewtwo #14 (Movie)", "Near Mint", "mid", 35, 80),
        ("WOTC", "Black Star Promo Cool Porygon #15", "Near Mint", "mid", 20, 50),
        ("WOTC", "Black Star Promo Birthday Pikachu #24", "Near Mint", "high", 80, 200),
        ("WOTC", "Black Star Promo Mew #47 (Lily Pad)", "Near Mint", "high", 50, 120),
        ("WOTC", "Black Star Promo Entei #34 (Reverse Holo)", "Near Mint", "mid", 25, 60),

        # ── Movie Promo Items ────────────────────────────────────────────
        ("Warner Bros", "Pokemon Movie 2000 Promo Ancient Mew (Sealed)", "Sealed", "mid", 30, 70),
        ("Warner Bros", "Pokemon 3 The Movie Unown Promo Set", "Near Mint", "mid", 20, 50),
        ("Warner Bros", "Pokemon Heroes Latias/Latios Promo", "Sealed", "mid", 25, 60),
        ("Official", "Pokemon Movie 4 Celebi Promo Card", "Near Mint", "mid", 25, 55),
        ("Official", "Mewtwo Strikes Back Evolution Promo Set (Japan)", "Sealed", "mid", 30, 70),

        # ── Vintage Japanese Media & Books ───────────────────────────────
        ("Shogakukan", "Pokemon Official Fan Book Vol.1 (1997)", "Good condition", "mid", 25, 60),
        ("Shogakukan", "Pokemon Red/Blue Official Guidebook (1996)", "Good condition", "mid", 20, 50),
        ("Shogakukan", "Pokemon Gold/Silver Official Guidebook", "Good condition", "standard", 15, 40),
        ("MediaFactory", "Pokemon Card GB Official Guidebook", "Good condition", "mid", 25, 55),
        ("Shogakukan", "Pocket Monsters Special Manga Vol.1 (1st Print)", "Good condition", "mid", 35, 80),
        ("JR East", "Pokemon Stamp Rally Complete Set (1998)", "Mint", "high", 60, 140),

        # ── WOTC Era Sets — Booster Packs (All Sets) ──────────────────
        ("WOTC", "Base Set Unlimited Booster Pack (Charizard Art)", "Sealed", "grail", 220, 420),
        ("WOTC", "Base Set Unlimited Booster Pack (Venusaur Art)", "Sealed", "grail", 200, 380),
        ("WOTC", "Base Set Unlimited Booster Pack (Blastoise Art)", "Sealed", "grail", 200, 380),
        ("WOTC", "Jungle 1st Edition Booster Pack", "Sealed", "grail", 300, 600),
        ("WOTC", "Jungle Unlimited Booster Pack", "Sealed", "high", 80, 180),
        ("WOTC", "Fossil 1st Edition Booster Pack", "Sealed", "grail", 250, 500),
        ("WOTC", "Fossil Unlimited Booster Pack", "Sealed", "high", 70, 160),
        ("WOTC", "Team Rocket 1st Edition Booster Pack", "Sealed", "grail", 350, 700),
        ("WOTC", "Team Rocket Unlimited Booster Pack", "Sealed", "high", 80, 180),
        ("WOTC", "Gym Heroes 1st Edition Booster Pack", "Sealed", "grail", 250, 500),
        ("WOTC", "Gym Heroes Unlimited Booster Pack", "Sealed", "high", 70, 160),
        ("WOTC", "Gym Challenge 1st Edition Booster Pack", "Sealed", "grail", 300, 600),
        ("WOTC", "Gym Challenge Unlimited Booster Pack", "Sealed", "high", 80, 180),
        ("WOTC", "Neo Genesis 1st Edition Booster Pack", "Sealed", "grail", 400, 800),
        ("WOTC", "Neo Genesis Unlimited Booster Pack", "Sealed", "high", 100, 220),
        ("WOTC", "Neo Discovery 1st Edition Booster Pack", "Sealed", "grail", 350, 700),
        ("WOTC", "Neo Discovery Unlimited Booster Pack", "Sealed", "high", 90, 200),
        ("WOTC", "Neo Revelation 1st Edition Booster Pack", "Sealed", "grail", 300, 600),
        ("WOTC", "Neo Revelation Unlimited Booster Pack", "Sealed", "high", 80, 180),
        ("WOTC", "Neo Destiny 1st Edition Booster Pack", "Sealed", "grail", 450, 900),
        ("WOTC", "Neo Destiny Unlimited Booster Pack", "Sealed", "high", 100, 220),
        ("WOTC", "Legendary Collection Booster Pack", "Sealed", "grail", 150, 320),
        ("WOTC", "Expedition Booster Pack", "Sealed", "grail", 200, 400),
        ("WOTC", "Aquapolis Booster Pack", "Sealed", "grail", 500, 1000),
        ("WOTC", "Skyridge Booster Pack", "Sealed", "grail", 800, 1600),

        # ── WOTC Theme Decks ───────────────────────────────────────────
        ("WOTC", "Base Set Brushfire Theme Deck", "Sealed", "high", 100, 250),
        ("WOTC", "Base Set Overgrowth Theme Deck", "Sealed", "high", 100, 250),
        ("WOTC", "Base Set Zap! Theme Deck", "Sealed", "high", 100, 250),
        ("WOTC", "Base Set Blackout Theme Deck", "Sealed", "high", 100, 250),
        ("WOTC", "Jungle Power Reserve Theme Deck", "Sealed", "high", 80, 200),
        ("WOTC", "Jungle Water Blast Theme Deck", "Sealed", "high", 80, 200),
        ("WOTC", "Fossil Lockdown Theme Deck", "Sealed", "high", 80, 200),
        ("WOTC", "Fossil Bodyguard Theme Deck", "Sealed", "high", 80, 200),
        ("WOTC", "Team Rocket Trouble Theme Deck", "Sealed", "high", 90, 220),
        ("WOTC", "Team Rocket Devastation Theme Deck", "Sealed", "high", 90, 220),
        ("WOTC", "Gym Heroes Brock Theme Deck", "Sealed", "high", 90, 200),
        ("WOTC", "Gym Heroes Misty Theme Deck", "Sealed", "high", 90, 200),
        ("WOTC", "Gym Challenge Koga Theme Deck", "Sealed", "high", 100, 240),
        ("WOTC", "Gym Challenge Sabrina Theme Deck", "Sealed", "high", 100, 240),
        ("WOTC", "Neo Genesis Cold Fusion Theme Deck", "Sealed", "high", 80, 200),
        ("WOTC", "Neo Genesis Hot Water Theme Deck", "Sealed", "high", 80, 200),

        # ── Japanese Promos — CoroCoro Full ────────────────────────────
        ("CoroCoro", "CoroCoro Promo Legendary Birds Set (Articuno/Zapdos/Moltres)", "Near Mint", "grail", 300, 700),
        ("CoroCoro", "CoroCoro Promo Charizard (Holo)", "Near Mint", "grail", 400, 900),
        ("CoroCoro", "CoroCoro Promo Eevee (Holo)", "Near Mint", "high", 80, 180),
        ("CoroCoro", "CoroCoro Promo Pikachu (Illustrator Style)", "Near Mint", "grail", 600, 1400),
        ("CoroCoro", "CoroCoro Promo Mewtwo (Holo)", "Near Mint", "grail", 200, 500),
        ("CoroCoro", "CoroCoro Promo Slowking (Movie)", "Near Mint", "high", 60, 150),

        # ── Japanese Movie Promos (All Movies) ─────────────────────────
        ("Official", "Mewtwo Strikes Back Promo Card Set (Japan)", "Near Mint", "grail", 150, 350),
        ("Official", "Pokemon Movie 2000 Promo Lugia (Japan)", "Near Mint", "high", 80, 200),
        ("Official", "Pokemon Movie 3 Entei Promo (Japan)", "Near Mint", "high", 70, 170),
        ("Official", "Pokemon Movie 4 Celebi Promo (Japan)", "Near Mint", "high", 60, 150),
        ("Official", "Pokemon Movie 5 Latias/Latios Promo Set (Japan)", "Near Mint", "high", 80, 190),
        ("Official", "Pokemon Movie 6 Jirachi Promo (Japan)", "Near Mint", "high", 55, 140),
        ("Official", "Pokemon Movie 7 Deoxys Promo (Japan)", "Near Mint", "high", 60, 150),
        ("Official", "Pokemon Movie 8 Mew & Lucario Promo Set (Japan)", "Near Mint", "high", 70, 170),

        # ── Pokemon Center Japan Promos ────────────────────────────────
        ("Pokemon Center", "Pokemon Center Birthday Pikachu Promo Card", "Near Mint", "high", 80, 200),
        ("Pokemon Center", "Pokemon Center Yokohama Opening Pikachu Card", "Near Mint", "grail", 200, 450),
        ("Pokemon Center", "Pokemon Center Tokyo DX Reopening Pikachu Card", "Near Mint", "high", 70, 170),
        ("Pokemon Center", "Pokemon Center Online Promo Pikachu", "Near Mint", "mid", 40, 100),
        ("Pokemon Center", "Pokemon Center Nagoya Reopening Promo Card", "Near Mint", "high", 60, 150),

        # ── Vintage Toys — Hasbro Full Line ────────────────────────────
        ("Hasbro", "Charizard Electronic Action Figure (2000)", "Working", "mid", 30, 70),
        ("Hasbro", "Pikachu I Choose You Plush (Talking)", "Working", "mid", 25, 60),
        ("Hasbro", "Pokemon Power Bouncer Pikachu", "Working", "standard", 15, 40),
        ("Hasbro", "Pokemon Deluxe Collectors Figure Set (6 Pack)", "Sealed", "mid", 35, 80),
        ("Hasbro", "Pokemon Catcher Game", "Complete", "standard", 12, 35),
        ("Hasbro", "Pokemon Stadium Battle Set", "Complete", "mid", 25, 60),
        ("Hasbro", "Pokemon Thundershock Challenge Game", "Complete", "standard", 15, 40),
        ("Hasbro", "Pokemon Pokeball Blaster Set", "Loose", "standard", 12, 35),
        ("Hasbro", "Pokemon Bean Bag Plush Pikachu (1998)", "With tag", "standard", 10, 30),
        ("Hasbro", "Pokemon Bean Bag Plush Charizard (1998)", "With tag", "standard", 12, 35),
        ("Hasbro", "Pokemon Bean Bag Plush Mewtwo (1998)", "With tag", "standard", 12, 35),
        ("Hasbro", "Pokemon Bean Bag Plush Jigglypuff (1998)", "With tag", "standard", 8, 25),

        # ── Vintage Toys — TOMY Full Line ──────────────────────────────
        ("TOMY", "Venusaur (TOMY Monster Collection)", "Loose", "mid", 18, 45),
        ("TOMY", "Ninetales (TOMY Monster Collection)", "Loose", "standard", 12, 32),
        ("TOMY", "Raichu (TOMY Monster Collection)", "Loose", "standard", 10, 28),
        ("TOMY", "Slowbro (TOMY Monster Collection)", "Loose", "standard", 10, 28),
        ("TOMY", "Starmie (TOMY Monster Collection)", "Loose", "standard", 10, 28),
        ("TOMY", "Scyther (TOMY Monster Collection)", "Loose", "standard", 12, 32),
        ("TOMY", "Electabuzz (TOMY Monster Collection)", "Loose", "standard", 10, 28),
        ("TOMY", "Magmar (TOMY Monster Collection)", "Loose", "standard", 10, 28),
        ("TOMY", "Pinsir (TOMY Monster Collection)", "Loose", "standard", 10, 28),
        ("TOMY", "Tauros (TOMY Monster Collection)", "Loose", "standard", 10, 28),
        ("TOMY", "Ditto (TOMY Monster Collection)", "Loose", "standard", 15, 38),
        ("TOMY", "Kangaskhan (TOMY Monster Collection)", "Loose", "standard", 12, 32),
        ("TOMY", "Mr. Mime (TOMY Monster Collection)", "Loose", "standard", 10, 28),
        ("TOMY", "Porygon (TOMY Monster Collection)", "Loose", "standard", 12, 32),
        ("TOMY", "Kabutops (TOMY Monster Collection)", "Loose", "standard", 12, 32),
        ("TOMY", "Aerodactyl (TOMY Monster Collection)", "Loose", "standard", 14, 35),
        ("TOMY", "Hitmonlee (TOMY Monster Collection)", "Loose", "standard", 10, 28),
        ("TOMY", "Hitmonchan (TOMY Monster Collection)", "Loose", "standard", 10, 28),

        # ── Vintage Toys — Applause Full Line ──────────────────────────
        ("Applause", "Squirtle PVC Figure (3 inch, 1999)", "Loose", "standard", 6, 18),
        ("Applause", "Bulbasaur PVC Figure (3 inch, 1999)", "Loose", "standard", 6, 18),
        ("Applause", "Psyduck PVC Figure (3 inch, 1999)", "Loose", "standard", 6, 18),
        ("Applause", "Gengar PVC Figure (3 inch, 1999)", "Loose", "standard", 8, 22),
        ("Applause", "Eevee PVC Figure (2.5 inch, 1999)", "Loose", "standard", 8, 22),
        ("Applause", "Snorlax PVC Figure (4 inch, 1999)", "Loose", "standard", 8, 22),

        # ── Vintage Toys — Jakks Pacific Full Line ─────────────────────
        ("Jakks Pacific", "Deluxe Charizard Electronic Figure (12 inch)", "Working", "mid", 30, 70),
        ("Jakks Pacific", "Deluxe Mewtwo Electronic Figure (10 inch)", "Working", "mid", 28, 65),
        ("Jakks Pacific", "Pokemon XY Starter 3-Pack", "Sealed", "standard", 15, 38),
        ("Jakks Pacific", "Pokemon Sun & Moon Figure Set", "Sealed", "standard", 15, 38),
        ("Jakks Pacific", "Legendary Giratina Figure (7 inch)", "Loose", "mid", 22, 52),
        ("Jakks Pacific", "Legendary Rayquaza Figure (12 inch)", "Loose", "mid", 28, 65),
        ("Jakks Pacific", "Legendary Arceus Figure (5 inch)", "Loose", "mid", 20, 48),
        ("Jakks Pacific", "Pikachu Plush with Sound (2007)", "Working", "standard", 15, 38),

        # ── Game Boy Games CIB ─────────────────────────────────────────
        ("Nintendo", "Pokemon Red Version (CIB)", "Complete in Box", "grail", 200, 500),
        ("Nintendo", "Pokemon Blue Version (CIB)", "Complete in Box", "grail", 200, 500),
        ("Nintendo", "Pokemon Yellow Version (CIB)", "Complete in Box", "grail", 250, 600),
        ("Nintendo", "Pokemon Gold Version (CIB)", "Complete in Box", "grail", 150, 400),
        ("Nintendo", "Pokemon Silver Version (CIB)", "Complete in Box", "grail", 150, 400),
        ("Nintendo", "Pokemon Crystal Version (CIB)", "Complete in Box", "grail", 300, 700),
        ("Nintendo", "Pokemon Ruby Version (CIB)", "Complete in Box", "high", 80, 200),
        ("Nintendo", "Pokemon Sapphire Version (CIB)", "Complete in Box", "high", 80, 200),
        ("Nintendo", "Pokemon Emerald Version (CIB)", "Complete in Box", "grail", 200, 500),
        ("Nintendo", "Pokemon FireRed Version (CIB)", "Complete in Box", "grail", 150, 380),
        ("Nintendo", "Pokemon LeafGreen Version (CIB)", "Complete in Box", "grail", 150, 380),
        ("Nintendo", "Pokemon Pinball (CIB)", "Complete in Box", "mid", 40, 100),
        ("Nintendo", "Pokemon Trading Card Game GB (CIB)", "Complete in Box", "mid", 40, 100),
        ("Nintendo", "Pokemon Puzzle Challenge (CIB)", "Complete in Box", "mid", 35, 80),
        ("Nintendo", "Pokemon Stadium (N64 CIB)", "Complete in Box", "high", 60, 150),
        ("Nintendo", "Pokemon Stadium 2 (N64 CIB)", "Complete in Box", "high", 80, 200),
        ("Nintendo", "Pokemon Snap (N64 CIB)", "Complete in Box", "high", 50, 130),
        ("Nintendo", "Pokemon Colosseum (GCN CIB)", "Complete in Box", "high", 80, 200),
        ("Nintendo", "Pokemon XD: Gale of Darkness (GCN CIB)", "Complete in Box", "grail", 150, 350),
        ("Nintendo", "Pokemon Box Ruby & Sapphire (GCN CIB)", "Complete in Box", "grail", 300, 700),

        # ── McDonald's Promos Full ─────────────────────────────────────
        ("McDonald's", "Pokemon Happy Meal Toys Complete Set (2002)", "Loose", "mid", 25, 60),
        ("McDonald's", "Pokemon Happy Meal Toys Complete Set (2003)", "Loose", "mid", 20, 50),
        ("McDonald's", "Pokemon Happy Meal Toys Complete Set (2011)", "Loose", "standard", 15, 40),
        ("McDonald's", "Pokemon Happy Meal Toys Complete Set (2014)", "Loose", "standard", 12, 35),
        ("McDonald's", "Pokemon Happy Meal Toys Complete Set (2015)", "Loose", "standard", 12, 35),
        ("McDonald's", "Pokemon Happy Meal Toys Complete Set (2016)", "Loose", "standard", 12, 35),
        ("McDonald's", "Pokemon Happy Meal Toys Complete Set (2018)", "Loose", "standard", 15, 40),
        ("McDonald's", "Pokemon Happy Meal Toys Complete Set (2019)", "Loose", "standard", 15, 40),
        ("McDonald's", "Pokemon 25th Anniversary Card Complete Set (Sealed)", "Sealed", "mid", 40, 90),
        ("McDonald's", "Pokemon 25th Anniversary Pikachu Holo Card", "Near Mint", "mid", 20, 50),

        # ── Burger King Promos Full ────────────────────────────────────
        ("Burger King", "Eevee Gold Card (Pokeball 1999)", "With Pokeball", "standard", 10, 30),
        ("Burger King", "Complete Beanbag Plush Set (All 57 toys, 1999)", "Loose", "grail", 150, 350),
        ("Burger King", "Mewtwo Keychain (1999)", "Loose", "standard", 6, 18),
        ("Burger King", "Pikachu Spinner Toy (1999)", "Loose", "standard", 5, 15),
        ("Burger King", "Pokeball Launcher Set (1999)", "Complete", "standard", 8, 22),

        # ── TCG Accessories Full ───────────────────────────────────────
        ("Ultra Pro", "Pokemon Expedition Binder", "Good condition", "mid", 25, 60),
        ("Ultra Pro", "Pokemon Aquapolis Binder", "Good condition", "mid", 25, 65),
        ("Ultra Pro", "Pokemon Skyridge Binder", "Good condition", "mid", 30, 70),
        ("Ultra Pro", "Pokemon Neo Discovery Binder", "Good condition", "mid", 22, 55),
        ("Ultra Pro", "Pokemon Neo Revelation Binder", "Good condition", "mid", 22, 55),
        ("Ultra Pro", "Pokemon Neo Destiny Binder", "Good condition", "mid", 25, 60),
        ("Official", "Pokemon TCG Playmat (Base Set Charizard Art)", "Good condition", "mid", 35, 80),
        ("Official", "Pokemon TCG Playmat (Team Rocket)", "Good condition", "mid", 30, 70),
        ("Official", "Pokemon TCG Playmat (Gym Heroes)", "Good condition", "mid", 30, 70),
        ("Official", "Pokemon TCG Damage Counters (Glass Bead Set)", "Complete", "standard", 12, 30),
        ("Official", "Pokemon TCG Official Coin (Pikachu Gold)", "Near Mint", "mid", 20, 50),
        ("Official", "Pokemon TCG Official Coin (Charizard Gold)", "Near Mint", "mid", 25, 60),
        ("Official", "Pokemon League Promo Energy Set (Neo Era)", "Near Mint", "mid", 20, 50),

        # ── Plush Lines — Full Range ───────────────────────────────────
        ("Pokemon Center", "Leafeon Plush (Eevee Collection 2006)", "With tag", "mid", 45, 100),
        ("Pokemon Center", "Glaceon Plush (Eevee Collection 2006)", "With tag", "mid", 45, 100),
        ("Pokemon Center", "Sylveon Plush (Eevee Collection 2013)", "With tag", "mid", 40, 90),
        ("Pokemon Center", "Meowth Plush (Tokyo 1999)", "With tag", "mid", 35, 80),
        ("Pokemon Center", "Psyduck Plush (Tokyo 2000)", "With tag", "mid", 30, 70),
        ("Pokemon Center", "Togepi Plush (Tokyo 1999)", "With tag", "mid", 35, 80),
        ("Pokemon Center", "Pichu Plush (Tokyo 2000)", "With tag", "mid", 30, 70),
        ("Pokemon Center", "Marill Plush (Tokyo 2000)", "With tag", "mid", 30, 70),
        ("Pokemon Center", "Lugia Plush (Japan 2000)", "With tag", "high", 60, 140),
        ("Pokemon Center", "Ho-Oh Plush (Japan 2000)", "With tag", "high", 55, 130),
        ("Pokemon Center", "Suicune Plush (Japan 2001)", "With tag", "mid", 45, 100),
        ("Pokemon Center", "Celebi Plush (Japan 2001)", "With tag", "mid", 40, 95),
        ("Pokemon Center", "Mudkip Plush (Japan 2003)", "With tag", "mid", 30, 70),
        ("Pokemon Center", "Torchic Plush (Japan 2003)", "With tag", "mid", 28, 65),
        ("Pokemon Center", "Treecko Plush (Japan 2003)", "With tag", "mid", 28, 65),

        # ── Banpresto Prize Figures Full ────────────────────────────────
        ("Banpresto", "UFO Catcher Gengar (Large 2001)", "Good condition", "mid", 30, 70),
        ("Banpresto", "UFO Catcher Dragonite (Large 2001)", "Good condition", "mid", 35, 75),
        ("Banpresto", "UFO Catcher Jigglypuff (Large 2000)", "Good condition", "mid", 25, 60),
        ("Banpresto", "UFO Catcher Mew (Large 2000)", "Good condition", "mid", 35, 80),
        ("Banpresto", "UFO Catcher Togepi (Large 1999)", "Good condition", "mid", 25, 60),
        ("Banpresto", "UFO Catcher Psyduck (Large 2000)", "Good condition", "mid", 25, 60),
        ("Banpresto", "Pokemon DX Prize Articuno Figure (2001)", "Good condition", "mid", 25, 60),
        ("Banpresto", "Pokemon DX Prize Zapdos Figure (2001)", "Good condition", "mid", 25, 60),
        ("Banpresto", "Pokemon DX Prize Moltres Figure (2001)", "Good condition", "mid", 25, 60),

        # ── Vintage N64 / GCN Accessories ──────────────────────────────
        ("Hori", "Pokemon Stadium N64 Controller (Pikachu)", "Working", "high", 60, 150),
        ("Nintendo", "Pokemon N64 Transfer Pak", "Loose", "standard", 15, 40),
        ("Nintendo", "Pokemon N64 Transfer Pak (Boxed)", "Complete", "mid", 30, 70),
        ("Nintendo", "Pokemon Memory Card 59 (GCN)", "Loose", "standard", 15, 38),
        ("Hori", "Pokemon Pikachu N64 Controller (Blue)", "Working", "high", 55, 140),
        ("Hori", "Pokemon Pikachu N64 Controller (Yellow)", "Working", "high", 60, 150),

        # ── Japanese Exclusive Vintage Items ───────────────────────────
        ("Takara Tomy", "Pokemon Pikachu Wafer Sticker Set (1998)", "Sealed", "mid", 20, 50),
        ("Bandai", "Pokemon Carddass Complete Set (Part 1, 1997)", "Near Mint", "grail", 150, 350),
        ("Bandai", "Pokemon Carddass Complete Set (Part 2, 1997)", "Near Mint", "grail", 120, 280),
        ("Bandai", "Pokemon Carddass Complete Set (Part 3, 1998)", "Near Mint", "high", 80, 200),
        ("Bandai", "Pokemon Carddass Complete Set (Part 4, 1998)", "Near Mint", "high", 80, 200),
        ("Meiji", "Pokemon Meiji Chocolate Promo Cards Complete Set", "Near Mint", "high", 70, 160),
        ("Meiji", "Pokemon Meiji Silver Emboss Cards Complete Set", "Near Mint", "grail", 100, 240),
        ("Tomy", "Pokemon Pocket Monsters Stadium Playset (Japan 1998)", "Complete", "high", 60, 140),
        ("Tomy", "Pokemon Pocket Monsters Talking Pikachu (Japan 1997)", "Working", "mid", 30, 70),

        # ── Game Boy Games — Loose Cartridges ──────────────────────────
        ("Nintendo", "Pokemon Red Version (Loose Cart)", "Loose", "mid", 40, 80),
        ("Nintendo", "Pokemon Blue Version (Loose Cart)", "Loose", "mid", 40, 80),
        ("Nintendo", "Pokemon Yellow Version (Loose Cart)", "Loose", "mid", 50, 100),
        ("Nintendo", "Pokemon Gold Version (Loose Cart)", "Loose", "mid", 30, 60),
        ("Nintendo", "Pokemon Silver Version (Loose Cart)", "Loose", "mid", 30, 60),
        ("Nintendo", "Pokemon Crystal Version (Loose Cart)", "Loose", "high", 80, 160),
        ("Nintendo", "Pokemon Emerald Version (Loose Cart)", "Loose", "high", 60, 130),
        ("Nintendo", "Pokemon FireRed Version (Loose Cart)", "Loose", "mid", 40, 90),
        ("Nintendo", "Pokemon LeafGreen Version (Loose Cart)", "Loose", "mid", 40, 90),

        # ── Expansion Batch — Neo Genesis Cards ──────────────────────────
        ("WOTC", "Neo Genesis Lugia 1st Edition Holo #9", "Near Mint", "grail", 300, 800),
        ("WOTC", "Neo Genesis Togetic 1st Edition Holo #16", "Near Mint", "high", 60, 150),
        ("WOTC", "Neo Genesis Typhlosion 1st Edition Holo #17", "Near Mint", "high", 80, 200),
        ("WOTC", "Neo Genesis Feraligatr 1st Edition Holo #5", "Near Mint", "high", 55, 140),
        ("WOTC", "Neo Genesis Meganium 1st Edition Holo #10", "Near Mint", "high", 50, 130),
        ("WOTC", "Neo Genesis Pichu 1st Edition Holo #12", "Near Mint", "high", 65, 160),

        # ── Neo Discovery Cards ──────────────────────────────────────────
        ("WOTC", "Neo Discovery Houndoom 1st Edition Holo #4", "Near Mint", "high", 70, 180),
        ("WOTC", "Neo Discovery Umbreon 1st Edition Holo #13", "Near Mint", "grail", 200, 500),
        ("WOTC", "Neo Discovery Espeon 1st Edition Holo #1", "Near Mint", "grail", 180, 450),
        ("WOTC", "Neo Discovery Kabutops 1st Edition Holo #6", "Near Mint", "high", 50, 130),
        ("WOTC", "Neo Discovery Scizor 1st Edition Holo #10", "Near Mint", "high", 55, 140),
        ("WOTC", "Neo Discovery Yanma 1st Edition Holo #17", "Near Mint", "mid", 35, 90),

        # ── Neo Revelation Cards ─────────────────────────────────────────
        ("WOTC", "Neo Revelation Shining Gyarados 1st Edition #65", "Near Mint", "grail", 350, 900),
        ("WOTC", "Neo Revelation Shining Magikarp 1st Edition #66", "Near Mint", "grail", 250, 650),
        ("WOTC", "Neo Revelation Ho-Oh 1st Edition Holo #7", "Near Mint", "high", 80, 200),
        ("WOTC", "Neo Revelation Suicune 1st Edition Holo #14", "Near Mint", "high", 70, 180),
        ("WOTC", "Neo Revelation Celebi 1st Edition Holo #3", "Near Mint", "high", 65, 160),
        ("WOTC", "Neo Revelation Entei 1st Edition Holo #6", "Near Mint", "high", 60, 150),

        # ── Neo Destiny Cards ────────────────────────────────────────────
        ("WOTC", "Neo Destiny Shining Charizard 1st Edition #107", "Near Mint", "grail", 500, 1500),
        ("WOTC", "Neo Destiny Shining Mewtwo 1st Edition #109", "Near Mint", "grail", 200, 550),
        ("WOTC", "Neo Destiny Shining Tyranitar 1st Edition #113", "Near Mint", "grail", 250, 700),
        ("WOTC", "Neo Destiny Shining Noctowl 1st Edition #110", "Near Mint", "grail", 120, 350),
        ("WOTC", "Neo Destiny Shining Steelix 1st Edition #112", "Near Mint", "grail", 150, 400),
        ("WOTC", "Neo Destiny Shining Raichu 1st Edition #111", "Near Mint", "grail", 180, 480),
        ("WOTC", "Neo Destiny Dark Ampharos 1st Edition Holo #1", "Near Mint", "high", 55, 140),
        ("WOTC", "Neo Destiny Dark Donphan 1st Edition Holo #3", "Near Mint", "high", 45, 120),
        ("WOTC", "Neo Destiny Dark Espeon 1st Edition Holo #4", "Near Mint", "high", 80, 200),
        ("WOTC", "Neo Destiny Dark Tyranitar 1st Edition Holo #11", "Near Mint", "grail", 150, 400),
        ("WOTC", "Neo Destiny Dark Houndoom 1st Edition Holo #7", "Near Mint", "high", 60, 160),
        ("WOTC", "Neo Destiny Light Arcanine 1st Edition Holo #12", "Near Mint", "high", 55, 140),

        # ── e-Series Cards ───────────────────────────────────────────────
        ("WOTC", "Expedition Base Set Charizard Holo #6", "Near Mint", "grail", 150, 400),
        ("WOTC", "Expedition Base Set Mewtwo Holo #20", "Near Mint", "high", 60, 150),
        ("WOTC", "Aquapolis Lugia Crystal Type #149", "Near Mint", "grail", 400, 1200),
        ("WOTC", "Aquapolis Kingdra Crystal Type #148", "Near Mint", "grail", 200, 600),
        ("WOTC", "Skyridge Charizard Holo #H3", "Near Mint", "grail", 350, 1000),
        ("WOTC", "Skyridge Celebi Crystal Type #145", "Near Mint", "grail", 300, 900),
        ("WOTC", "Skyridge Ho-Oh Crystal Type #149", "Near Mint", "grail", 350, 1100),

        # ── Legendary Collection Reverses ────────────────────────────────
        ("WOTC", "Legendary Collection Reverse Holo Charizard #3", "Near Mint", "grail", 400, 1200),
        ("WOTC", "Legendary Collection Reverse Holo Dark Blastoise #4", "Near Mint", "grail", 150, 450),
        ("WOTC", "Legendary Collection Reverse Holo Dark Dragonite #5", "Near Mint", "grail", 120, 350),
        ("WOTC", "Legendary Collection Reverse Holo Alakazam #1", "Near Mint", "grail", 100, 300),
        ("WOTC", "Legendary Collection Reverse Holo Zapdos #19", "Near Mint", "high", 80, 220),
        ("WOTC", "Legendary Collection Reverse Holo Mewtwo #29", "Near Mint", "grail", 120, 350),
        ("WOTC", "Legendary Collection Reverse Holo Ninetales #17", "Near Mint", "high", 70, 200),

        # ── e-Series Additional ──────────────────────────────────────────
        ("WOTC", "Expedition Base Set Feraligatr Holo #12", "Near Mint", "high", 50, 130),
        ("WOTC", "Expedition Base Set Typhlosion Holo #28", "Near Mint", "high", 55, 140),
        ("WOTC", "Aquapolis Arcanine Crystal Type #H2", "Near Mint", "grail", 250, 700),
        ("WOTC", "Skyridge Gengar Holo #H9", "Near Mint", "grail", 200, 600),
        ("WOTC", "Skyridge Umbreon Holo #H29", "Near Mint", "grail", 180, 500),
        ("WOTC", "Legendary Collection Reverse Holo Hitmonlee #13", "Near Mint", "high", 55, 160),

        # ── Japanese Exclusive Promos ─────────────────────────────────────
        ("WOTC JP", "Corocoro Shining Mew Promo #151", "Near Mint", "grail", 300, 900),
        ("WOTC JP", "Masaki Gengar Promo", "Near Mint", "grail", 250, 700),
        ("WOTC JP", "Masaki Alakazam Promo", "Near Mint", "grail", 200, 600),
        ("WOTC JP", "Masaki Golem Promo", "Near Mint", "high", 80, 220),
        ("WOTC JP", "Masaki Omastar Promo", "Near Mint", "high", 75, 200),
        ("WOTC JP", "Lucky Stadium Promo Chansey", "Near Mint", "high", 60, 160),
        ("WOTC JP", "Tropical Mega Battle Tropical Wind Promo", "Near Mint", "grail", 800, 2500),
        ("WOTC JP", "Grand Party Trainer Promo", "Near Mint", "grail", 400, 1200),
        ("WOTC JP", "No. 1 Trainer Promo (Regional)", "Near Mint", "grail", 1500, 5000),
        ("WOTC JP", "Fan Club Porygon Promo", "Near Mint", "high", 90, 250),

        # ── Neo Genesis Non-Holo Rares ────────────────────────────────────
        ("WOTC", "Neo Genesis Heracross 1st Edition Non-Holo #6", "Near Mint", "mid", 25, 65),
        ("WOTC", "Neo Genesis Skarmory 1st Edition Non-Holo #13", "Near Mint", "mid", 20, 55),
        ("WOTC", "Neo Genesis Steelix 1st Edition Non-Holo #15", "Near Mint", "mid", 30, 75),
        ("WOTC", "Neo Genesis Kingdra 1st Edition Non-Holo #8", "Near Mint", "mid", 22, 60),
        ("WOTC", "Neo Genesis Azumarill 1st Edition Non-Holo #2", "Near Mint", "mid", 18, 50),

        # ── Neo Revelation Non-Holo Rares ─────────────────────────────────
        ("WOTC", "Neo Revelation Ampharos 1st Edition Holo #1", "Near Mint", "high", 55, 150),
        ("WOTC", "Neo Revelation Houndoom 1st Edition Holo #8", "Near Mint", "high", 65, 170),
        ("WOTC", "Neo Revelation Magneton 1st Edition Holo #10", "Near Mint", "mid", 35, 90),
        ("WOTC", "Neo Revelation Misdreavus 1st Edition Holo #11", "Near Mint", "mid", 40, 100),
        ("WOTC", "Neo Revelation Porygon2 1st Edition Holo #12", "Near Mint", "mid", 35, 95),

        # ── Gym Heroes Holos ──────────────────────────────────────────────
        ("WOTC", "Gym Heroes Erika's Vileplume 1st Edition Holo #5", "Near Mint", "high", 55, 140),
        ("WOTC", "Gym Heroes Lt. Surge's Electabuzz 1st Edition Holo #6", "Near Mint", "high", 50, 130),
        ("WOTC", "Gym Heroes Misty's Tentacruel 1st Edition Holo #10", "Near Mint", "mid", 35, 90),
        ("WOTC", "Gym Heroes Rocket's Hitmonchan 1st Edition Holo #11", "Near Mint", "high", 55, 140),

        # ── Gym Challenge Holos ───────────────────────────────────────────
        ("WOTC", "Gym Challenge Blaine's Charizard 1st Edition Holo #2", "Near Mint", "grail", 350, 1000),
        ("WOTC", "Gym Challenge Giovanni's Gyarados 1st Edition Holo #5", "Near Mint", "high", 70, 180),
        ("WOTC", "Gym Challenge Sabrina's Alakazam 1st Edition Holo #16", "Near Mint", "high", 60, 160),
        ("WOTC", "Gym Challenge Koga's Ditto 1st Edition Holo #10", "Near Mint", "high", 55, 150),

        # ── e-Series Expansion ────────────────────────────────────────────
        ("WOTC", "Expedition Base Set Blastoise Holo #4", "Near Mint", "high", 80, 200),
        ("WOTC", "Expedition Base Set Venusaur Holo #30", "Near Mint", "high", 70, 180),
        ("WOTC", "Aquapolis Suicune Crystal Type #H28", "Near Mint", "grail", 300, 850),
        ("WOTC", "Aquapolis Nidoking Crystal Type #H22", "Near Mint", "grail", 200, 600),
        ("WOTC", "Skyridge Kabutops Holo #H14", "Near Mint", "high", 80, 220),
        ("WOTC", "Skyridge Machamp Holo #H16", "Near Mint", "high", 50, 140),
        ("WOTC", "Skyridge Golem Holo #H8", "Near Mint", "high", 45, 120),

        # ── Vending Machine Series (Japanese) ─────────────────────────────
        ("Bandai JP", "Vending Machine Series 1 Pikachu", "Near Mint", "high", 60, 180),
        ("Bandai JP", "Vending Machine Series 2 Mewtwo", "Near Mint", "high", 55, 160),
        ("Bandai JP", "Vending Machine Series 3 Dragonite", "Near Mint", "high", 50, 140),
        ("Bandai JP", "Vending Machine Series 1 Charizard", "Near Mint", "grail", 120, 350),
        ("Bandai JP", "Vending Machine Series 2 Blastoise", "Near Mint", "high", 80, 220),

        # ── Southern Islands Set ──────────────────────────────────────────
        ("WOTC", "Southern Islands Mew #1", "Near Mint", "grail", 120, 350),
        ("WOTC", "Southern Islands Togepi #6", "Near Mint", "mid", 25, 70),
        ("WOTC", "Southern Islands Slowking #3", "Near Mint", "mid", 30, 80),
        ("WOTC", "Southern Islands Marill #5", "Near Mint", "mid", 20, 60),
        ("WOTC", "Southern Islands Complete Binder Set (18 Cards)", "Near Mint", "grail", 300, 800),

        # ── VS Series (Japanese) ──────────────────────────────────────────
        ("Media Factory JP", "VS Series Lance's Charizard #98", "Near Mint", "grail", 200, 600),
        ("Media Factory JP", "VS Series Karen's Umbreon #91", "Near Mint", "grail", 150, 400),
        ("Media Factory JP", "VS Series Clair's Dragonite #100", "Near Mint", "high", 80, 220),
        ("Media Factory JP", "VS Series Jasmine's Steelix #50", "Near Mint", "high", 60, 160),
        ("Media Factory JP", "VS Series Falkner's Pidgeot #8", "Near Mint", "mid", 35, 90),

        # ── Sealed Vintage Products ───────────────────────────────────────
        ("WOTC", "Base Set Booster Pack (Charizard Art) Sealed", "Sealed", "grail", 500, 800),
        ("WOTC", "Fossil Booster Pack Sealed (Lapras Art)", "Sealed", "grail", 200, 350),
        ("WOTC", "Team Rocket Booster Pack Sealed (Dark Charizard Art)", "Sealed", "grail", 250, 400),
        ("WOTC", "Gym Heroes Booster Pack Sealed (Misty Art)", "Sealed", "grail", 180, 300),
        ("WOTC", "Neo Genesis Booster Pack Sealed (Lugia Art)", "Sealed", "grail", 350, 600),

        # ── Japanese Base Set Cards ──────────────────────────────────────
        ("WOTC JP", "Japanese Base Set Charizard Holo #6", "Near Mint", "grail", 200, 550),
        ("WOTC JP", "Japanese Base Set Blastoise Holo #9", "Near Mint", "high", 80, 200),
        ("WOTC JP", "Japanese Base Set Venusaur Holo #3", "Near Mint", "high", 70, 180),
        ("WOTC JP", "Japanese Base Set Alakazam Holo #65", "Near Mint", "mid", 40, 100),
        ("WOTC JP", "Japanese Base Set Chansey Holo #113", "Near Mint", "mid", 35, 90),
        ("WOTC JP", "Japanese Base Set Mewtwo Holo #150", "Near Mint", "high", 60, 160),
        ("WOTC JP", "Japanese Base Set Raichu Holo #26", "Near Mint", "mid", 40, 100),
        ("WOTC JP", "Japanese Base Set Gyarados Holo #130", "Near Mint", "mid", 35, 95),
        ("WOTC JP", "Japanese Base Set Ninetales Holo #38", "Near Mint", "mid", 30, 80),
        ("WOTC JP", "Japanese Base Set Magneton Holo #82", "Near Mint", "mid", 25, 65),

        # ── Vending Machine Series (Additional Japanese) ─────────────────
        ("Bandai JP", "Vending Machine Series 1 Bulbasaur", "Near Mint", "mid", 30, 80),
        ("Bandai JP", "Vending Machine Series 1 Squirtle", "Near Mint", "mid", 25, 70),
        ("Bandai JP", "Vending Machine Series 2 Mew", "Near Mint", "high", 70, 200),
        ("Bandai JP", "Vending Machine Series 3 Lugia", "Near Mint", "high", 65, 180),
        ("Bandai JP", "Vending Machine Series 2 Eevee", "Near Mint", "mid", 35, 90),
        ("Bandai JP", "Vending Machine Series 3 Ho-Oh", "Near Mint", "high", 55, 150),

        # ── Southern Islands (Additional) ────────────────────────────────
        ("WOTC", "Southern Islands Pidgeot #2", "Near Mint", "mid", 20, 55),
        ("WOTC", "Southern Islands Onix #4", "Near Mint", "mid", 18, 50),
        ("WOTC", "Southern Islands Jigglypuff #7", "Near Mint", "mid", 18, 48),
        ("WOTC", "Southern Islands Butterfree #8", "Near Mint", "mid", 18, 48),
        ("WOTC", "Southern Islands Tentacruel #9", "Near Mint", "mid", 15, 42),
        ("WOTC", "Southern Islands Lickitung #16", "Near Mint", "mid", 15, 40),
        ("WOTC", "Southern Islands Vileplume #17", "Near Mint", "mid", 15, 40),
        ("WOTC", "Southern Islands Primeape #18", "Near Mint", "mid", 15, 42),

        # ── Gym Heroes Holos (Additional) ────────────────────────────────
        ("WOTC", "Gym Heroes Brock's Rhydon 1st Edition Holo #2", "Near Mint", "high", 55, 140),
        ("WOTC", "Gym Heroes Erika's Dragonair 1st Edition Holo #4", "Near Mint", "high", 60, 160),
        ("WOTC", "Gym Heroes Lt. Surge's Fearow 1st Edition Holo #7", "Near Mint", "mid", 35, 90),
        ("WOTC", "Gym Heroes Misty's Seadra 1st Edition Holo #9", "Near Mint", "mid", 30, 80),
        ("WOTC", "Gym Heroes Rocket's Mewtwo 1st Edition Holo #14", "Near Mint", "grail", 120, 300),
        ("WOTC", "Gym Heroes Rocket's Scyther 1st Edition Holo #13", "Near Mint", "high", 55, 140),
        ("WOTC", "Gym Heroes Sabrina's Gengar 1st Edition Holo #14", "Near Mint", "high", 65, 170),
        ("WOTC", "Gym Heroes Blaine's Arcanine 1st Edition Holo #1", "Near Mint", "high", 80, 200),

        # ── Gym Challenge Holos (Additional) ─────────────────────────────
        ("WOTC", "Gym Challenge Blaine's Moltres 1st Edition Holo #1", "Near Mint", "high", 65, 170),
        ("WOTC", "Gym Challenge Erika's Venusaur 1st Edition Holo #4", "Near Mint", "high", 70, 180),
        ("WOTC", "Gym Challenge Lt. Surge's Raichu 1st Edition Holo #11", "Near Mint", "high", 55, 140),
        ("WOTC", "Gym Challenge Misty's Golduck 1st Edition Holo #12", "Near Mint", "mid", 40, 100),
        ("WOTC", "Gym Challenge Rocket's Zapdos 1st Edition Holo #15", "Near Mint", "high", 75, 190),
        ("WOTC", "Gym Challenge Giovanni's Nidoking 1st Edition Holo #7", "Near Mint", "high", 55, 150),
        ("WOTC", "Gym Challenge Giovanni's Persian 1st Edition Holo #8", "Near Mint", "mid", 45, 120),

        # ── VS Series (Additional Japanese) ──────────────────────────────
        ("Media Factory JP", "VS Series Morty's Gengar #74", "Near Mint", "high", 80, 220),
        ("Media Factory JP", "VS Series Will's Espeon #65", "Near Mint", "high", 70, 190),
        ("Media Factory JP", "VS Series Lance's Kingdra #97", "Near Mint", "high", 60, 160),
        ("Media Factory JP", "VS Series Bruno's Hitmontop #42", "Near Mint", "mid", 30, 80),
        ("Media Factory JP", "VS Series Pryce's Piloswine #51", "Near Mint", "mid", 25, 70),
        ("Media Factory JP", "VS Series Sabrina's Espeon #70", "Near Mint", "high", 65, 170),
        ("Media Factory JP", "VS Series Karen's Tyranitar #92", "Near Mint", "grail", 120, 350),

        # ── Gold Star Cards ──────────────────────────────────────────────
        ("Pokemon USA", "Gold Star Charizard (EX Dragon Frontiers #100)", "Near Mint", "grail", 600, 1800),
        ("Pokemon USA", "Gold Star Mewtwo (EX Holon Phantoms #103)", "Near Mint", "grail", 300, 900),
        ("Pokemon USA", "Gold Star Pikachu (EX Holon Phantoms #104)", "Near Mint", "grail", 400, 1200),
        ("Pokemon USA", "Gold Star Rayquaza (EX Deoxys #107)", "Near Mint", "grail", 500, 1500),
        ("Pokemon USA", "Gold Star Gyarados (EX Holon Phantoms #102)", "Near Mint", "grail", 250, 750),
        ("Pokemon USA", "Gold Star Vaporeon (POP Series 5 #17)", "Near Mint", "grail", 200, 600),
        ("Pokemon USA", "Gold Star Jolteon (POP Series 5 #16)", "Near Mint", "grail", 200, 600),
        ("Pokemon USA", "Gold Star Flareon (POP Series 5 #15)", "Near Mint", "grail", 200, 600),
        ("Pokemon USA", "Gold Star Umbreon (POP Series 5 #18)", "Near Mint", "grail", 350, 1000),
        ("Pokemon USA", "Gold Star Espeon (POP Series 5 #16)", "Near Mint", "grail", 300, 900),

        # ── Shining Pokemon (Additional) ─────────────────────────────────
        ("WOTC", "Neo Destiny Shining Celebi 1st Edition #106", "Near Mint", "grail", 180, 500),
        ("WOTC", "Neo Destiny Shining Kabutops 1st Edition #108", "Near Mint", "grail", 140, 380),

        # ── Crystal Type Cards (Additional) ──────────────────────────────
        ("WOTC", "Aquapolis Golem Crystal Type #148", "Near Mint", "grail", 180, 520),
        ("WOTC", "Skyridge Charizard Crystal Type #H3 Reverse", "Near Mint", "grail", 450, 1400),
        ("WOTC", "Skyridge Kabutops Crystal Type #150", "Near Mint", "grail", 250, 700),
        ("WOTC", "Skyridge Crobat Crystal Type #147", "Near Mint", "grail", 200, 600),

        # ── Early WOTC Promos ────────────────────────────────────────────
        ("WOTC", "Pikachu Black Star Promo #1", "Near Mint", "mid", 20, 55),
        ("WOTC", "Electabuzz Black Star Promo #2", "Near Mint", "mid", 15, 40),
        ("WOTC", "Mewtwo Black Star Promo #3", "Near Mint", "mid", 15, 40),
        ("WOTC", "Pikachu Black Star Promo #4 (Ivy Edition)", "Near Mint", "mid", 25, 65),
        ("WOTC", "Dragonite Black Star Promo #5 (Movie)", "Near Mint", "mid", 20, 55),
        ("WOTC", "Ancient Mew Promo (Movie 2000)", "Near Mint", "mid", 30, 80),
        ("WOTC", "Mew Black Star Promo #8 (Wizards)", "Near Mint", "mid", 25, 60),
        ("WOTC", "Mew Black Star Promo #9 (Wizards)", "Near Mint", "mid", 20, 50),

        # ── e-Series (Additional Holos) ──────────────────────────────────
        ("WOTC", "Expedition Base Set Alakazam Holo #1", "Near Mint", "high", 55, 140),
        ("WOTC", "Expedition Base Set Dragonite Holo #9", "Near Mint", "high", 60, 160),
        ("WOTC", "Expedition Base Set Gengar Holo #13", "Near Mint", "high", 65, 170),
        ("WOTC", "Expedition Base Set Machamp Holo #16", "Near Mint", "mid", 40, 100),
        ("WOTC", "Aquapolis Espeon Holo #H10", "Near Mint", "high", 70, 180),
        ("WOTC", "Aquapolis Umbreon Holo #H30", "Near Mint", "high", 75, 200),

        # ── Neo Discovery (Additional) ───────────────────────────────────
        ("WOTC", "Neo Discovery Tyranitar 1st Edition Holo #12", "Near Mint", "grail", 130, 350),
        ("WOTC", "Neo Discovery Poliwrath 1st Edition Holo #9", "Near Mint", "mid", 35, 90),
        ("WOTC", "Neo Discovery Forretress 1st Edition Holo #2", "Near Mint", "mid", 30, 80),
        ("WOTC", "Neo Discovery Magnemite 1st Edition Holo #7", "Near Mint", "mid", 25, 70),

        # ── Japanese Promos (Additional) ─────────────────────────────────
        ("WOTC JP", "Corocoro Mew Lily Pad Promo", "Near Mint", "grail", 150, 450),
        ("WOTC JP", "Corocoro Shining Mew (Glossy)", "Near Mint", "grail", 350, 1000),
        ("WOTC JP", "University Magikarp Promo (TMB Qualifier)", "Near Mint", "grail", 600, 2000),
        ("WOTC JP", "No. 2 Trainer Promo (Regional)", "Near Mint", "grail", 800, 3000),
        ("WOTC JP", "No. 3 Trainer Promo (Regional)", "Near Mint", "grail", 500, 1800),
        ("WOTC JP", "Pokemon Center NY Pikachu Gold Star Promo", "Near Mint", "grail", 400, 1200),
        ("WOTC JP", "ANA Airlines Pikachu Promo (All Nippon)", "Near Mint", "grail", 200, 600),
        ("WOTC JP", "ANA Airlines Articuno Promo (All Nippon)", "Near Mint", "grail", 150, 450),
        ("WOTC JP", "Japanese Gym Promo Erika's Clefable", "Near Mint", "high", 60, 160),
        ("WOTC JP", "Japanese Gym Promo Misty's Psyduck", "Near Mint", "mid", 30, 80),
        ("WOTC JP", "Japanese Quick Starter Pikachu #25", "Near Mint", "mid", 25, 65),
        ("WOTC JP", "Japanese Intro Starter Squirtle #7", "Near Mint", "mid", 20, 50),
        ("WOTC JP", "Japanese Coro Coro Comics Imakuni? Promo", "Near Mint", "high", 80, 220),
        ("WOTC JP", "Japanese Trade Please! Pikachu Promo", "Near Mint", "high", 70, 190),

        # ── Base Set 1st Edition Holos ──────────────────────────────────────
        ("WOTC", "Base Set 1st Edition Charizard Holo #4 (PSA 10 ~$420K)", "Mint", "grail", 5000, 420000),
        ("WOTC", "Base Set 1st Edition Blastoise Holo #2", "Near Mint", "grail", 1500, 45000),
        ("WOTC", "Base Set 1st Edition Venusaur Holo #15", "Near Mint", "grail", 1200, 35000),
        ("WOTC", "Base Set 1st Edition Alakazam Holo #1", "Near Mint", "grail", 800, 20000),
        ("WOTC", "Base Set 1st Edition Chansey Holo #3", "Near Mint", "grail", 600, 15000),
        ("WOTC", "Base Set 1st Edition Clefairy Holo #5", "Near Mint", "grail", 500, 12000),
        ("WOTC", "Base Set 1st Edition Gyarados Holo #6", "Near Mint", "grail", 700, 18000),
        ("WOTC", "Base Set 1st Edition Hitmonchan Holo #7", "Near Mint", "grail", 500, 12000),
        ("WOTC", "Base Set 1st Edition Machamp Holo #8 (1st Ed Stamp)", "Near Mint", "high", 80, 2000),
        ("WOTC", "Base Set 1st Edition Magneton Holo #9", "Near Mint", "grail", 500, 12000),
        ("WOTC", "Base Set 1st Edition Mewtwo Holo #10", "Near Mint", "grail", 900, 25000),
        ("WOTC", "Base Set 1st Edition Nidoking Holo #11", "Near Mint", "grail", 550, 14000),
        ("WOTC", "Base Set 1st Edition Ninetales Holo #12", "Near Mint", "grail", 500, 12000),
        ("WOTC", "Base Set 1st Edition Poliwrath Holo #13", "Near Mint", "grail", 500, 11000),
        ("WOTC", "Base Set 1st Edition Raichu Holo #14", "Near Mint", "grail", 600, 15000),

        # ── Base Set Shadowless ─────────────────────────────────────────────
        ("WOTC", "Base Set Shadowless Charizard Holo #4 (PSA 9/10)", "Mint", "grail", 2000, 150000),
        ("WOTC", "Base Set Shadowless Blastoise Holo #2", "Near Mint", "grail", 500, 12000),
        ("WOTC", "Base Set Shadowless Venusaur Holo #15", "Near Mint", "grail", 400, 10000),
        ("WOTC", "Base Set Shadowless Mewtwo Holo #10", "Near Mint", "grail", 350, 8000),
        ("WOTC", "Base Set Shadowless Alakazam Holo #1", "Near Mint", "grail", 300, 7000),
        ("WOTC", "Base Set Shadowless Chansey Holo #3", "Near Mint", "high", 200, 5000),
        ("WOTC", "Base Set Shadowless Gyarados Holo #6", "Near Mint", "high", 250, 6000),
        ("WOTC", "Base Set Shadowless Hitmonchan Holo #7", "Near Mint", "high", 180, 4500),
        ("WOTC", "Base Set Shadowless Ninetales Holo #12", "Near Mint", "high", 180, 4500),
        ("WOTC", "Base Set Shadowless Poliwrath Holo #13", "Near Mint", "high", 170, 4000),

        # ── Jungle / Fossil 1st Edition ─────────────────────────────────────
        ("WOTC", "Jungle 1st Edition Flareon Holo #3", "Near Mint", "high", 80, 2500),
        ("WOTC", "Jungle 1st Edition Jolteon Holo #4", "Near Mint", "high", 80, 2500),
        ("WOTC", "Jungle 1st Edition Vaporeon Holo #12", "Near Mint", "high", 80, 2500),
        ("WOTC", "Jungle 1st Edition Scyther Holo #10", "Near Mint", "high", 70, 2000),
        ("WOTC", "Jungle 1st Edition Kangaskhan Holo #5", "Near Mint", "high", 60, 1800),
        ("WOTC", "Fossil 1st Edition Gengar Holo #5", "Near Mint", "high", 100, 3500),
        ("WOTC", "Fossil 1st Edition Dragonite Holo #4", "Near Mint", "high", 120, 4000),
        ("WOTC", "Fossil 1st Edition Articuno Holo #2", "Near Mint", "high", 80, 2500),
        ("WOTC", "Fossil 1st Edition Zapdos Holo #15", "Near Mint", "high", 80, 2500),
        ("WOTC", "Fossil 1st Edition Moltres Holo #12", "Near Mint", "high", 70, 2200),

        # ── Team Rocket 1st Edition ─────────────────────────────────────────
        ("WOTC", "Team Rocket 1st Edition Dark Charizard Holo #4", "Near Mint", "grail", 300, 10000),
        ("WOTC", "Team Rocket 1st Edition Dark Blastoise Holo #3", "Near Mint", "high", 100, 3000),
        ("WOTC", "Team Rocket 1st Edition Dark Dragonite Holo #5", "Near Mint", "high", 80, 2500),
        ("WOTC", "Team Rocket 1st Edition Dark Raichu (Secret Rare) #83", "Near Mint", "grail", 200, 6000),
        ("WOTC", "Team Rocket 1st Edition Here Comes Team Rocket Holo #15", "Near Mint", "high", 60, 1800),
        ("WOTC", "Team Rocket 1st Edition Dark Arbok Holo #2", "Near Mint", "high", 50, 1500),
        ("WOTC", "Team Rocket 1st Edition Dark Weezing Holo #14", "Near Mint", "high", 45, 1400),
        ("WOTC", "Team Rocket 1st Edition Dark Hypno Holo #9", "Near Mint", "high", 40, 1200),

        # ── Neo Sets ───────────────────────────────────────────────────────
        ("WOTC", "Neo Genesis 1st Edition Lugia Holo #9", "Near Mint", "grail", 500, 20000),
        ("WOTC", "Neo Discovery 1st Edition Umbreon Holo #13", "Near Mint", "grail", 400, 12000),
        ("WOTC", "Neo Discovery 1st Edition Espeon Holo #1", "Near Mint", "grail", 350, 10000),
        ("WOTC", "Neo Revelation Shining Magikarp #66 (Secret Rare)", "Near Mint", "grail", 200, 6000),
        ("WOTC", "Neo Revelation Shining Gyarados #65 (Secret Rare)", "Near Mint", "grail", 250, 8000),
        ("WOTC", "Neo Destiny Shining Charizard #107 (Secret Rare)", "Near Mint", "grail", 600, 25000),
        ("WOTC", "Neo Destiny Shining Mewtwo #109 (Secret Rare)", "Near Mint", "grail", 200, 6000),
        ("WOTC", "Neo Destiny Light Arcanine #12", "Near Mint", "high", 80, 2500),
        ("WOTC", "Neo Genesis 1st Edition Typhlosion Holo #17", "Near Mint", "high", 100, 3500),
        ("WOTC", "Neo Genesis 1st Edition Feraligatr Holo #5", "Near Mint", "high", 80, 2500),

        # ── Gym Challenge / Gym Heroes ──────────────────────────────────────
        ("WOTC", "Gym Challenge 1st Edition Blaine's Charizard Holo #2", "Near Mint", "grail", 250, 8000),
        ("WOTC", "Gym Heroes Misty's Tentacruel Holo #10", "Near Mint", "high", 50, 1500),
        ("WOTC", "Gym Challenge Erika's Venusaur Holo #4", "Near Mint", "high", 80, 2500),
        ("WOTC", "Gym Challenge Sabrina's Alakazam Holo #16", "Near Mint", "high", 60, 1800),
        ("WOTC", "Gym Challenge Giovanni's Persian Holo #8", "Near Mint", "high", 50, 1500),
        ("WOTC", "Gym Heroes Brock's Onix Holo (1st Edition)", "Near Mint", "high", 40, 1200),
        ("WOTC", "Gym Heroes Lt. Surge's Electabuzz Holo (1st Edition)", "Near Mint", "high", 45, 1400),
        ("WOTC", "Gym Challenge Blaine's Arcanine Holo #1", "Near Mint", "high", 70, 2200),

        # ── E-Series & Ex Era ───────────────────────────────────────────────
        ("WOTC", "Skyridge Charizard Holo #H3 (Crystal Shard Art)", "Near Mint", "grail", 800, 30000),
        ("WOTC", "Aquapolis Crystal Charizard #H28 (Reverse Holo)", "Near Mint", "grail", 1500, 50000),
        ("WOTC", "Aquapolis Crystal Lugia #H29", "Near Mint", "grail", 1200, 40000),
        ("WOTC", "Aquapolis Crystal Nidoking #H22", "Near Mint", "grail", 500, 15000),
        ("WOTC", "Skyridge Charizard Reverse Holo #H3", "Near Mint", "grail", 600, 20000),
        ("Pokemon USA", "EX Ruby & Sapphire Blaziken Holo #3", "Near Mint", "high", 40, 1200),
        ("Pokemon USA", "EX Dragon Frontiers Charizard Gold Star #100", "Near Mint", "grail", 1500, 50000),
        ("Pokemon USA", "EX Deoxys Rayquaza Gold Star #107", "Near Mint", "grail", 1000, 35000),
        ("Pokemon USA", "EX Team Rocket Returns Charizard ex #105", "Near Mint", "grail", 200, 6000),
        ("Pokemon USA", "EX FireRed LeafGreen Charizard ex #105", "Near Mint", "grail", 300, 10000),

        # ── Gold Star Cards ─────────────────────────────────────────────────
        ("Pokemon USA", "Charizard Gold Star (EX Dragon Frontiers #100)", "Near Mint", "grail", 1500, 50000),
        ("Pokemon USA", "Mewtwo Gold Star (EX Holon Phantoms #103)", "Near Mint", "grail", 500, 15000),
        ("Pokemon USA", "Mew Gold Star (EX Dragon Frontiers #101)", "Near Mint", "grail", 600, 18000),
        ("Pokemon USA", "Rayquaza Gold Star (EX Deoxys #107)", "Near Mint", "grail", 1000, 35000),
        ("Pokemon USA", "Pikachu Gold Star (EX Holon Phantoms #104)", "Near Mint", "grail", 800, 25000),
        ("Pokemon USA", "Umbreon Gold Star (POP Series 5 #17)", "Near Mint", "grail", 2000, 60000),
        ("Pokemon USA", "Espeon Gold Star (POP Series 5 #16)", "Near Mint", "grail", 1800, 55000),
        ("Pokemon USA", "Latias Gold Star (EX Deoxys #105)", "Near Mint", "grail", 400, 12000),
        ("Pokemon USA", "Latios Gold Star (EX Deoxys #106)", "Near Mint", "grail", 400, 12000),
        ("Pokemon USA", "Gyarados Gold Star (EX Holon Phantoms #102)", "Near Mint", "grail", 500, 15000),

        # ── Japanese Exclusives (Ultra Premium) ─────────────────────────────
        ("WOTC JP", "Illustrator Pikachu (1998 CoroCoro, ~$5.2M card)", "Mint", "grail", 50000, 5200000),
        ("WOTC JP", "Tropical Mega Battle Tropical Wind Promo (TMB 1999)", "Near Mint", "grail", 5000, 60000),
        ("WOTC JP", "No. 1 Trainer Promo (1999 Secret Super Battle)", "Near Mint", "grail", 10000, 300000),
        ("WOTC JP", "Lucky Stadium Magikarp (Promo)", "Near Mint", "grail", 300, 3000),
        ("WOTC JP", "Masaki Gengar Promo (Trade-for-Evolution)", "Near Mint", "grail", 500, 8000),
        ("WOTC JP", "Masaki Omastar Promo (Trade-for-Evolution)", "Near Mint", "grail", 400, 6000),
        ("WOTC JP", "Masaki Machamp Promo (Trade-for-Evolution)", "Near Mint", "grail", 300, 5000),
        ("WOTC JP", "Masaki Golem Promo (Trade-for-Evolution)", "Near Mint", "grail", 300, 5000),
        ("WOTC JP", "CoroCoro Mew Promo (Original 1996)", "Near Mint", "grail", 200, 4000),
        ("WOTC JP", "ANA Pikachu Promo (All Nippon Airways 1998)", "Near Mint", "grail", 300, 5000),
        ("WOTC JP", "ANA Pikachu Promo (All Nippon Airways 1999 — Flying)", "Near Mint", "grail", 250, 4000),
        ("WOTC JP", "World Championship Promo Set (2004 Pikachu)", "Near Mint", "grail", 500, 8000),
        ("WOTC JP", "World Championship Promo Set (2005 Pikachu)", "Near Mint", "grail", 400, 6000),
        ("WOTC JP", "Snap Pikachu Promo (Best Photo Contest 1999)", "Near Mint", "grail", 3000, 40000),
        ("WOTC JP", "Tamamushi University Magikarp (TMB Qualifier)", "Near Mint", "grail", 800, 15000),

        # ── Sealed Product ──────────────────────────────────────────────────
        ("WOTC", "Base Set Booster Box (Unlimited, 36 packs)", "Factory Sealed", "grail", 8000, 15000),
        ("WOTC", "Base Set 1st Edition Booster Box (36 packs)", "Factory Sealed", "grail", 200000, 400000),
        ("WOTC", "Jungle Booster Box (36 packs, Unlimited)", "Factory Sealed", "grail", 5000, 10000),
        ("WOTC", "Fossil Booster Box (36 packs, Unlimited)", "Factory Sealed", "grail", 4500, 9000),
        ("WOTC", "Team Rocket Booster Box (36 packs, Unlimited)", "Factory Sealed", "grail", 5000, 10000),
        ("WOTC", "Neo Genesis Booster Box (36 packs)", "Factory Sealed", "grail", 8000, 16000),
        ("WOTC", "Base Set Theme Deck — Overgrowth (Sealed)", "Factory Sealed", "grail", 200, 600),
        ("WOTC", "Base Set Theme Deck — Zap! (Sealed)", "Factory Sealed", "grail", 200, 600),
        ("WOTC", "Base Set Theme Deck — Brushfire (Sealed)", "Factory Sealed", "grail", 200, 600),
        ("WOTC", "Base Set 2 Booster Box (36 packs)", "Factory Sealed", "grail", 3000, 6000),

        # ── Modern Vintage (High-Value Modern Cards) ────────────────────────
        ("Pokemon TCG", "Hidden Fates Shiny Charizard GX #SV49", "Near Mint", "grail", 200, 5000),
        ("Pokemon TCG", "Champions Path Charizard V #79 (Full Art)", "Near Mint", "high", 40, 800),
        ("Pokemon TCG", "Champions Path Charizard VMAX #74 (Rainbow Rare)", "Near Mint", "grail", 150, 3000),
        ("Pokemon TCG", "Evolving Skies Umbreon VMAX Alt Art #215", "Near Mint", "grail", 250, 6000),
        ("Pokemon TCG", "Evolving Skies Rayquaza VMAX Alt Art #218", "Near Mint", "grail", 150, 3500),
        ("Pokemon TCG", "Evolving Skies Sylveon VMAX Alt Art #212", "Near Mint", "grail", 120, 2500),
        ("Pokemon TCG", "Brilliant Stars Charizard VSTAR Rainbow #174", "Near Mint", "high", 80, 1800),
        ("Pokemon TCG", "Obsidian Flames Charizard ex #223 (Special Art)", "Near Mint", "high", 60, 1200),
        ("Pokemon TCG", "151 Charizard ex SAR #185", "Near Mint", "high", 80, 1800),
        ("Pokemon TCG", "151 Mew ex SAR #186", "Near Mint", "high", 50, 1000),
        ("Pokemon TCG", "Crown Zenith Galarian Gallery Pikachu VMAX #GG30", "Near Mint", "high", 40, 800),
        ("Pokemon TCG", "Paldea Evolved Iono SAR #237", "Near Mint", "grail", 100, 2500),
        ("Pokemon TCG", "Evolving Skies Espeon VMAX Alt Art #214", "Near Mint", "grail", 100, 2200),
        ("Pokemon TCG", "Evolving Skies Leafeon VMAX Alt Art #216", "Near Mint", "high", 80, 1800),
        ("Pokemon TCG", "Surging Sparks Pikachu ex SAR (Special Art Rare)", "Near Mint", "high", 60, 1500),

        # ── Gym Heroes / Gym Challenge Holos ─────────────────────────────
        ("WOTC", "Erika's Venusaur Holo (Gym Heroes)", "Near Mint", "high", 50, 800),
        ("WOTC", "Misty's Tentacruel Holo (Gym Heroes)", "Near Mint", "mid", 20, 300),
        ("WOTC", "Lt. Surge's Electabuzz Holo (Gym Heroes)", "Near Mint", "mid", 18, 250),
        ("WOTC", "Brock's Rhydon Holo (Gym Heroes)", "Near Mint", "mid", 20, 280),
        ("WOTC", "Rocket's Scyther Holo (Gym Heroes)", "Near Mint", "mid", 22, 320),
        ("WOTC", "Sabrina's Gengar Holo (Gym Heroes)", "Near Mint", "high", 40, 600),
        ("WOTC", "Rocket's Moltres Holo (Gym Challenge)", "Near Mint", "mid", 25, 350),
        ("WOTC", "Blaine's Arcanine Holo (Gym Challenge)", "Near Mint", "high", 55, 900),
        ("WOTC", "Giovanni's Gyarados Holo (Gym Challenge)", "Near Mint", "mid", 30, 450),
        ("WOTC", "Erika's Dragonair Holo (Gym Heroes)", "Near Mint", "mid", 25, 400),
        ("WOTC", "Misty's Golduck Holo (Gym Heroes)", "Near Mint", "mid", 15, 200),
        ("WOTC", "Koga's Beedrill Holo (Gym Challenge)", "Near Mint", "mid", 15, 200),
        ("WOTC", "Blaine's Charizard Holo (Gym Challenge)", "Near Mint", "grail", 100, 2000),
        ("WOTC", "Sabrina's Alakazam Holo (Gym Challenge)", "Near Mint", "mid", 30, 400),
        ("WOTC", "Giovanni's Persian Holo (Gym Challenge)", "Near Mint", "mid", 18, 250),

        # ── Legendary Collection Reverse Holos ────────────────────────────
        ("WOTC", "Charizard Reverse Holo (Legendary Collection)", "Near Mint", "grail", 300, 8000),
        ("WOTC", "Dark Blastoise Reverse Holo (Legendary Collection)", "Near Mint", "grail", 120, 3000),
        ("WOTC", "Dark Dragonite Reverse Holo (Legendary Collection)", "Near Mint", "grail", 100, 2500),
        ("WOTC", "Ninetales Reverse Holo (Legendary Collection)", "Near Mint", "high", 60, 1500),
        ("WOTC", "Dark Raichu Reverse Holo (Legendary Collection)", "Near Mint", "high", 50, 1200),
        ("WOTC", "Alakazam Reverse Holo (Legendary Collection)", "Near Mint", "high", 60, 1400),
        ("WOTC", "Gengar Reverse Holo (Legendary Collection)", "Near Mint", "high", 80, 1800),
        ("WOTC", "Machamp Reverse Holo (Legendary Collection)", "Near Mint", "mid", 30, 600),
        ("WOTC", "Flareon Reverse Holo (Legendary Collection)", "Near Mint", "high", 50, 1000),
        ("WOTC", "Jolteon Reverse Holo (Legendary Collection)", "Near Mint", "high", 45, 900),
        ("WOTC", "Vaporeon Reverse Holo (Legendary Collection)", "Near Mint", "high", 45, 900),
        ("WOTC", "Mewtwo Reverse Holo (Legendary Collection)", "Near Mint", "grail", 150, 4000),

        # ── Expedition / Aquapolis / Skyridge Non-Holo Rares ──────────────
        ("WOTC", "Tyranitar Holo (Expedition)", "Near Mint", "high", 60, 1200),
        ("WOTC", "Meganium Holo (Expedition)", "Near Mint", "mid", 25, 400),
        ("WOTC", "Feraligatr Holo (Expedition)", "Near Mint", "mid", 30, 500),
        ("WOTC", "Typhlosion Holo (Expedition)", "Near Mint", "mid", 35, 600),
        ("WOTC", "Arcanine Holo (Aquapolis)", "Near Mint", "high", 50, 800),
        ("WOTC", "Umbreon Holo (Aquapolis)", "Near Mint", "grail", 100, 2500),
        ("WOTC", "Espeon Holo (Aquapolis)", "Near Mint", "high", 80, 2000),
        ("WOTC", "Lugia Holo (Aquapolis)", "Near Mint", "grail", 150, 4000),
        ("WOTC", "Celebi Holo (Aquapolis)", "Near Mint", "high", 50, 1000),
        ("WOTC", "Charizard Holo (Skyridge)", "Near Mint", "grail", 250, 8000),
        ("WOTC", "Kabutops Holo (Skyridge)", "Near Mint", "high", 60, 1200),
        ("WOTC", "Gengar Holo (Skyridge)", "Near Mint", "grail", 120, 3000),
        ("WOTC", "Alakazam Holo (Skyridge)", "Near Mint", "high", 80, 1800),
        ("WOTC", "Gyarados Holo (Skyridge)", "Near Mint", "high", 60, 1200),

        # ── EX Era Key Cards ─────────────────────────────────────────────
        ("Pokemon TCG", "Rayquaza ex Gold Star (EX Deoxys)", "Near Mint", "grail", 500, 15000),
        ("Pokemon TCG", "Mew ex (EX Legend Maker)", "Near Mint", "high", 40, 800),
        ("Pokemon TCG", "Espeon Gold Star (EX Unseen Forces)", "Near Mint", "grail", 200, 6000),
        ("Pokemon TCG", "Umbreon Gold Star (EX Unseen Forces)", "Near Mint", "grail", 250, 8000),
        ("Pokemon TCG", "Rocket's Persian ex (EX Unseen Forces)", "Near Mint", "mid", 20, 300),
        ("Pokemon TCG", "Deoxys ex (EX Deoxys #99)", "Near Mint", "high", 40, 700),
        ("Pokemon TCG", "Jirachi ex (EX Deoxys)", "Near Mint", "mid", 25, 350),
        ("Pokemon TCG", "Arcanine ex (EX Legend Maker)", "Near Mint", "mid", 30, 400),
        ("Pokemon TCG", "Gengar ex (EX Fire Red Leaf Green)", "Near Mint", "mid", 30, 500),
        ("Pokemon TCG", "Charizard ex (EX Fire Red Leaf Green #105)", "Near Mint", "grail", 100, 3000),
        ("Pokemon TCG", "Blastoise ex (EX Fire Red Leaf Green #104)", "Near Mint", "high", 50, 1200),
        ("Pokemon TCG", "Venusaur ex (EX Fire Red Leaf Green #112)", "Near Mint", "high", 40, 900),
        ("Pokemon TCG", "Latias Gold Star (EX Deoxys)", "Near Mint", "grail", 150, 5000),
        ("Pokemon TCG", "Latios Gold Star (EX Deoxys)", "Near Mint", "grail", 150, 5000),
        ("Pokemon TCG", "Pikachu Gold Star (EX Holon Phantoms)", "Near Mint", "grail", 200, 7000),
        ("Pokemon TCG", "Mewtwo Gold Star (EX Holon Phantoms)", "Near Mint", "grail", 200, 6000),

        # ── Japanese Promos ──────────────────────────────────────────────
        ("Pokemon TCG JP", "Corocoro Mew Promo (No. 151)", "Near Mint", "high", 40, 600),
        ("Pokemon TCG JP", "Corocoro Shining Mew (Promo)", "Near Mint", "high", 80, 1500),
        ("Pokemon TCG JP", "McDonald's e-Card Pikachu (Japan)", "Near Mint", "high", 60, 1000),
        ("Pokemon TCG JP", "ANA Airlines Pikachu Promo", "Near Mint", "high", 50, 800),
        ("Pokemon TCG JP", "Masaki Gengar (Trade Please)", "Near Mint", "grail", 150, 5000),
        ("Pokemon TCG JP", "Masaki Alakazam (Trade Please)", "Near Mint", "grail", 100, 3000),
        ("Pokemon TCG JP", "Masaki Golem (Trade Please)", "Near Mint", "high", 60, 1500),
        ("Pokemon TCG JP", "Fan Club Porygon Promo", "Near Mint", "high", 80, 2000),
        ("Pokemon TCG JP", "University Magikarp Promo", "Near Mint", "grail", 200, 5000),
        ("Pokemon TCG JP", "Pikachu Illustrator (2016 Reprint)", "Near Mint", "grail", 500, 10000),
        ("Pokemon TCG JP", "Pokemon Center Mew Promo (2005)", "Near Mint", "mid", 25, 400),
        ("Pokemon TCG JP", "Pokemon Center Celebi Promo (2001)", "Near Mint", "mid", 30, 500),
        ("Pokemon TCG JP", "Lucky Stadium Pikachu (Nagoya)", "Near Mint", "high", 50, 800),
        ("Pokemon TCG JP", "Tropical Mega Battle Tropical Wind (2004)", "Near Mint", "grail", 300, 8000),
        ("Pokemon TCG JP", "Shiny Rayquaza V Promo (Japan PC)", "Near Mint", "high", 40, 600),

        # ── Graded Card Price Points (PSA 8, BGS 9) ─────────────────────
        ("PSA Graded", "Base Set Charizard Holo PSA 8", "PSA 8 NM-MT", "grail", 300, 300),
        ("PSA Graded", "Base Set Blastoise Holo PSA 8", "PSA 8 NM-MT", "high", 80, 80),
        ("PSA Graded", "Base Set Venusaur Holo PSA 8", "PSA 8 NM-MT", "high", 60, 60),
        ("PSA Graded", "1st Edition Machamp Holo PSA 9", "PSA 9 MINT", "mid", 40, 40),
        ("BGS Graded", "Base Set Charizard Holo BGS 9", "BGS 9 MINT", "grail", 400, 400),
        ("BGS Graded", "Neo Genesis Lugia Holo BGS 9", "BGS 9 MINT", "grail", 500, 500),
        ("PSA Graded", "Jungle Flareon Holo PSA 9", "PSA 9 MINT", "mid", 30, 30),
        ("PSA Graded", "Fossil Gengar Holo PSA 9", "PSA 9 MINT", "mid", 35, 35),
        ("PSA Graded", "Team Rocket Dark Charizard Holo PSA 9", "PSA 9 MINT", "high", 120, 120),
        ("PSA Graded", "Neo Destiny Shining Charizard PSA 8", "PSA 8 NM-MT", "grail", 600, 600),
        ("PSA Graded", "Neo Destiny Shining Mewtwo PSA 8", "PSA 8 NM-MT", "high", 100, 100),
        ("PSA Graded", "Neo Discovery Umbreon Holo PSA 9", "PSA 9 MINT", "high", 80, 80),
        ("BGS Graded", "Skyridge Charizard Holo BGS 9", "BGS 9 MINT", "grail", 1500, 1500),
        ("PSA Graded", "Aquapolis Lugia Holo PSA 8", "PSA 8 NM-MT", "grail", 300, 300),
        ("PSA Graded", "Expedition Tyranitar Holo PSA 8", "PSA 8 NM-MT", "high", 80, 80),
        ("PSA Graded", "Crystal Charizard (Skyridge) PSA 7", "PSA 7 NM", "grail", 2000, 2000),
        ("PSA Graded", "Gold Star Rayquaza PSA 8", "PSA 8 NM-MT", "grail", 1000, 1000),
        ("BGS Graded", "Shadowless Charizard BGS 8.5", "BGS 8.5 NM-MT+", "grail", 800, 800),
        ("PSA Graded", "Evolving Skies Umbreon VMAX Alt Art PSA 10", "PSA 10 GEM MT", "grail", 500, 500),
        ("PSA Graded", "Hidden Fates Shiny Charizard GX PSA 10", "PSA 10 GEM MT", "grail", 400, 400),

        # ── Sealed Booster Packs (Individual) ────────────────────────────
        ("WOTC", "Base Set Booster Pack (Charizard Art, Unlimited)", "Factory Sealed", "grail", 300, 300),
        ("WOTC", "Jungle Booster Pack (Flareon Art)", "Factory Sealed", "high", 80, 80),
        ("WOTC", "Fossil Booster Pack (Lapras Art)", "Factory Sealed", "high", 70, 70),
        ("WOTC", "Team Rocket Booster Pack (Jesse Art)", "Factory Sealed", "high", 90, 90),
        ("WOTC", "Gym Heroes Booster Pack (Misty Art)", "Factory Sealed", "high", 100, 100),
        ("WOTC", "Gym Challenge Booster Pack (Blaine Art)", "Factory Sealed", "high", 100, 100),
        ("WOTC", "Neo Genesis Booster Pack (Lugia Art)", "Factory Sealed", "grail", 150, 150),
        ("WOTC", "Expedition Booster Pack (Mewtwo Art)", "Factory Sealed", "grail", 200, 200),
        ("WOTC", "Aquapolis Booster Pack (Suicune Art)", "Factory Sealed", "grail", 250, 250),
        ("WOTC", "Skyridge Booster Pack (Umbreon Art)", "Factory Sealed", "grail", 400, 400),
        ("Pokemon TCG", "EX Fire Red Leaf Green Booster Pack (Sealed)", "Factory Sealed", "high", 80, 80),
        ("Pokemon TCG", "EX Deoxys Booster Pack (Sealed)", "Factory Sealed", "high", 100, 100),
        ("Pokemon TCG", "EX Unseen Forces Booster Pack (Sealed)", "Factory Sealed", "high", 90, 90),
        ("Pokemon TCG", "EX Dragon Frontiers Booster Pack (Sealed)", "Factory Sealed", "high", 100, 100),
        ("Pokemon TCG", "EX Holon Phantoms Booster Pack (Sealed)", "Factory Sealed", "high", 80, 80),

        # ── Additional WOTC & e-Series Cards ──────────────────────────────
        ("WOTC", "Blaine's Moltres Holo (Gym Challenge)", "Near Mint", "mid", 30, 450),
        ("WOTC", "Sabrina's Gengar Holo (Gym Challenge)", "Near Mint", "high", 45, 700),
        ("WOTC", "Misty's Seadra Holo (Gym Heroes)", "Near Mint", "mid", 15, 200),
        ("WOTC", "Lt. Surge's Magneton Holo (Gym Heroes)", "Near Mint", "mid", 18, 250),
        ("WOTC", "Erika's Clefable Holo (Gym Heroes)", "Near Mint", "mid", 15, 200),
        ("WOTC", "Giovanni's Nidoking Holo (Gym Challenge)", "Near Mint", "mid", 25, 350),
        ("WOTC", "Ampharos Holo (Expedition)", "Near Mint", "mid", 25, 400),
        ("WOTC", "Arbok Holo (Skyridge)", "Near Mint", "mid", 30, 500),
        ("WOTC", "Crystal Nidoking (Aquapolis)", "Near Mint", "grail", 200, 6000),
        ("WOTC", "Crystal Lugia (Aquapolis)", "Near Mint", "grail", 300, 10000),
        ("WOTC", "Crystal Charizard (Skyridge)", "Near Mint", "grail", 500, 15000),
        ("WOTC", "Crystal Ho-Oh (Aquapolis)", "Near Mint", "grail", 200, 5000),
        ("WOTC", "Crystal Celebi (Skyridge)", "Near Mint", "grail", 200, 5000),
        ("WOTC", "Crystal Kingdra (Aquapolis)", "Near Mint", "grail", 150, 3500),
        ("WOTC", "Crystal Golem (Skyridge)", "Near Mint", "high", 80, 2000),
        ("WOTC", "Crystal Kabutops (Skyridge)", "Near Mint", "high", 80, 2000),

        # ── More Japanese Promos & Tournament Cards ───────────────────────
        ("Pokemon TCG JP", "Grand Party Pikachu (2000 Promo)", "Near Mint", "high", 80, 1500),
        ("Pokemon TCG JP", "Birthday Pikachu (Promo #025)", "Near Mint", "high", 60, 1000),
        ("Pokemon TCG JP", "Mario Pikachu Promo (Luigi Pikachu)", "Near Mint", "high", 80, 1500),
        ("Pokemon TCG JP", "Lillie Full Art Promo (SM-P #052)", "Near Mint", "high", 50, 800),
        ("Pokemon TCG JP", "Kanazawa Pikachu Promo (Opening)", "Near Mint", "high", 40, 600),
        ("Pokemon TCG JP", "Pretend Boss Pikachu Set (5 cards)", "Near Mint", "grail", 150, 3000),
        ("Pokemon TCG JP", "Natta Wake Pikachu (CoroCoro 1997)", "Near Mint", "high", 60, 1200),
        ("Pokemon TCG JP", "Southern Islands Complete Set (18 cards)", "Near Mint", "grail", 200, 4000),
        ("Pokemon TCG JP", "Pokemon VS Series Booster Pack (Sealed)", "Factory Sealed", "high", 50, 50),

        # ── More Graded Cards ─────────────────────────────────────────────
        ("PSA Graded", "Base Set Mewtwo Holo PSA 9", "PSA 9 MINT", "high", 100, 100),
        ("PSA Graded", "Neo Revelation Shining Gyarados PSA 8", "PSA 8 NM-MT", "high", 80, 80),
        ("PSA Graded", "Neo Revelation Shining Magikarp PSA 8", "PSA 8 NM-MT", "mid", 40, 40),
        ("PSA Graded", "Gym Heroes Rocket's Scyther PSA 9", "PSA 9 MINT", "mid", 30, 30),
        ("PSA Graded", "Expedition Charizard (Holo) PSA 8", "PSA 8 NM-MT", "grail", 200, 200),
        ("BGS Graded", "Aquapolis Umbreon Holo BGS 9", "BGS 9 MINT", "grail", 300, 300),
        ("BGS Graded", "Gold Star Mewtwo BGS 9", "BGS 9 MINT", "grail", 500, 500),
        ("PSA Graded", "Crystal Charizard (Skyridge) PSA 8", "PSA 8 NM-MT", "grail", 2500, 2500),
        ("PSA Graded", "Tropical Mega Battle Tropical Wind PSA 9", "PSA 9 MINT", "grail", 5000, 5000),
        ("PSA Graded", "Pikachu Illustrator (Reprint) PSA 9", "PSA 9 MINT", "grail", 2000, 2000),
        ("CGC Graded", "Base Set Charizard Holo CGC 9", "CGC 9 MINT", "grail", 350, 350),
        ("CGC Graded", "Shining Charizard (Neo Destiny) CGC 8", "CGC 8 NM-MT", "grail", 500, 500),
        ("CGC Graded", "1st Edition Shadowless Blastoise CGC 8.5", "CGC 8.5", "grail", 400, 400),
        ("PSA Graded", "Fossil Dragonite Holo PSA 9", "PSA 9 MINT", "mid", 35, 35),
        ("PSA Graded", "Jungle Jolteon Holo PSA 9", "PSA 9 MINT", "mid", 30, 30),
    ]

    catalog = []
    for brand, name, condition_note, tier, price_loose, price_boxed in items:
        catalog.append({
            "brand": brand,
            "name": name,
            "condition_note": condition_note,
            "rarity_tier": tier,
            "price_loose": price_loose,
            "price_boxed": price_boxed,
        })

    # Inject graded / variant / language / sealed expansions
    catalog.extend(_variant_expansion())

    # Deduplicate by ('brand', 'name') (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = (item["brand"], item["name"])
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


def item_to_catalog_item(item: dict) -> CatalogItem:
    brand = item["brand"]
    name = item["name"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{brand}-{name}"),
        title=name,
        set_code=brand.lower().replace(" ", "-"),
        brand=brand,
        rarity=item["rarity_tier"].title(),
        notes=f"{brand} | {item['condition_note']}",
        attributes_json={
            "brand": brand,
            "condition_note": item["condition_note"],
            "era": "1990s-2000s",
            "is_electronic": any(kw in name.lower() for kw in ["electronic", "pokedex", "virtual pet", "camera", "printer", "mini console"]),
        },
    )


def item_to_price_observations(item: dict) -> list[PriceObservation]:
    """Create observations for loose and boxed conditions."""
    tier = item["rarity_tier"]
    rarity_score = shared_rarity_score(tier)

    observations = []

    # Loose price
    observations.append(PriceObservation(
        features={
            "condition_score": 0.5,
            "rarity_score": rarity_score,
            "edition_score": 0.5,
            "is_boxed": 0.0,
            "is_vintage": 1.0,
        },
        price=float(item["price_loose"]),
    ))

    # Boxed / complete price
    observations.append(PriceObservation(
        features={
            "condition_score": 0.9,
            "rarity_score": rarity_score,
            "edition_score": 0.5,
            "is_boxed": 1.0,
            "is_vintage": 1.0,
        },
        price=float(item["price_boxed"]),
    ))

    return observations


def main():
    parser = argparse.ArgumentParser(description="Import retro Pokemon accessories catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Retro Pokemon Import ===")

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

    logger.info(f"\n=== Retro Pokemon Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
