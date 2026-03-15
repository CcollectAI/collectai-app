"""
Import Marvel Legends catalog.

Layer 1 (Catalog):  Curated Hasbro Marvel Legends 6" figures → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Marvel Legends Series main waves (2014–present) with BAF figures
- Marvel Legends Retro line (vintage cardback packaging)
- Marvel Legends 20th Anniversary Series
- Marvel Legends Deluxe / Rider Series
- Marvel Legends HasLab exclusives (Galactus, Sentinel, Ghost Rider)
- Marvel Legends Fan Channel / Amazon / Target / Walgreens / Pulse exclusives
- X-Men '97 animated tie-in wave
- Spider-Man: No Way Home / Multiverse figures
- Avengers: Endgame / Infinity War waves
- Deadpool & Wolverine wave
- 800+ items across all lines, waves, and variants

Usage:
    python -m pipelines.import_marvel_legends [--dry-run]
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

CATEGORY = "marvel_legends"


def _variant_expansion() -> list[dict]:
    """~100 variant items: chase, retailer exclusive, retro-card repackage,
    deluxe upgrades, 20th Anniversary / Archive reissues, alt head-sculpt /
    accessory-pack variants, and BAF-wave colour swaps."""

    def _v(series, wave, name, baf, packaging, exclusive, sealed, price):
        return {
            "series": series,
            "wave": wave,
            "name": name,
            "baf_figure": baf,
            "packaging_type": packaging,
            "retailer_exclusive": exclusive,
            "sealed": sealed,
            "price_eur": price,
        }

    return [
        # ── Chase Variants (darker paint / metallic finishes) ────────────
        _v("Standard", "No Way Home", "Spider-Man (Integrated Suit, Metallic Chase)", "Armadillo", "Standard", "", True, 65),
        _v("Standard", "No Way Home", "Doc Ock (NWH, Metallic Chase)", "Armadillo", "Standard", "", True, 72),
        _v("Standard", "Endgame", "Iron Man Mark LXXXV (Metallic Chase)", "Thanos", "Standard", "", True, 75),
        _v("Standard", "Endgame", "Thor (Endgame, Stormbreaker Glow Chase)", "Thanos", "Standard", "", True, 68),
        _v("Standard", "Infinity War", "Thanos (Infinity War, Metallic Chase)", "Cull Obsidian", "Standard", "", True, 85),
        _v("Standard", "X-Men '97", "Wolverine (X-Men '97, Metallic Chase)", "Bonebreaker", "Standard", "", True, 70),
        _v("Standard", "X-Men '97", "Magneto (X-Men '97, Metallic Chase)", "Bonebreaker", "Standard", "", True, 78),
        _v("Standard", "Venom", "Venom (Metallic Chase)", "Venompool", "Standard", "", True, 88),
        _v("Standard", "Venom", "Carnage (Metallic Chase)", "Venompool", "Standard", "", True, 95),
        _v("Standard", "Spider-Verse", "Miles Morales (Into the SV, Translucent Chase)", "Stilt-Man", "Standard", "", True, 80),
        _v("Standard", "Spider-Verse", "Spider-Gwen (Ghost-Spider, Unmasked Chase)", "Stilt-Man", "Standard", "", True, 75),
        _v("Standard", "Classic Avengers", "Captain America (Classic, Metallic Shield Chase)", "Giant-Man", "Standard", "", True, 72),
        _v("Standard", "Fantastic Four", "Doctor Doom (Metallic Chase)", "Super Skrull", "Standard", "", True, 90),
        _v("Standard", "Deadpool & Wolverine", "Deadpool (Movie, Metallic Chase)", "Cassandra Nova", "Standard", "", True, 65),
        _v("Standard", "Deadpool & Wolverine", "Wolverine (Movie, Metallic Chase)", "Cassandra Nova", "Standard", "", True, 68),

        # ── Retailer Exclusives (Target) ─────────────────────────────────
        _v("Fan Channel", "Exclusives", "Wolverine (X-Men '97, Target Exclusive)", "", "Standard", "Target", True, 45),
        _v("Fan Channel", "Exclusives", "Captain America (Endgame, Target Exclusive)", "", "Standard", "Target", True, 42),
        _v("Fan Channel", "Exclusives", "Scarlet Witch (WandaVision, Target Exclusive)", "", "Standard", "Target", True, 48),
        _v("Fan Channel", "Exclusives", "Moon Knight (Glow-in-Dark, Target)", "", "Standard", "Target", True, 55),
        _v("Fan Channel", "Exclusives", "Doctor Doom (Infamous Iron Man, Target)", "", "Standard", "Target", True, 52),
        _v("Fan Channel", "Exclusives", "Venom (Retro Card, Target Exclusive)", "", "Retro Card", "Target", True, 55),

        # ── Retailer Exclusives (Walmart) ────────────────────────────────
        _v("Fan Channel", "Exclusives", "Hulk (Immortal, Glow Walmart)", "", "Standard", "Walmart", True, 48),
        _v("Fan Channel", "Exclusives", "Wolverine (Weapon X, Walmart)", "", "Standard", "Walmart", True, 42),
        _v("Fan Channel", "Exclusives", "Thanos (Comic, Walmart Exclusive)", "", "Standard", "Walmart", True, 45),
        _v("Fan Channel", "Exclusives", "Spider-Man (Symbiote, Walmart Exclusive)", "", "Standard", "Walmart", True, 42),
        _v("Fan Channel", "Exclusives", "Punisher (Retro War Machine Armor, Walmart)", "", "Standard", "Walmart", True, 48),

        # ── Retailer Exclusives (Amazon) ─────────────────────────────────
        _v("Fan Channel", "Exclusives", "Deadpool & Hit-Monkey 2-Pack (Amazon)", "", "Standard", "Amazon", True, 62),
        _v("Fan Channel", "Exclusives", "Thor & Sif 2-Pack (Amazon)", "", "Standard", "Amazon", True, 58),
        _v("Fan Channel", "Exclusives", "Venom & Carnage 2-Pack (Amazon)", "", "Standard", "Amazon", True, 65),
        _v("Fan Channel", "Exclusives", "Wolverine (Fang, Amazon Exclusive)", "", "Standard", "Amazon", True, 45),
        _v("Fan Channel", "Exclusives", "Magneto (House of X, Amazon)", "", "Standard", "Amazon", True, 48),

        # ── Retailer Exclusives (Hasbro Pulse) ──────────────────────────
        _v("Fan Channel", "Exclusives", "Deadpool (Chef, Pulse Exclusive)", "", "Standard", "Hasbro Pulse", True, 42),
        _v("Fan Channel", "Exclusives", "Storm (Goddess, Pulse Exclusive)", "", "Standard", "Hasbro Pulse", True, 48),
        _v("Fan Channel", "Exclusives", "Wolverine (Days of Future Past, Pulse)", "", "Standard", "Hasbro Pulse", True, 45),
        _v("Fan Channel", "Exclusives", "Doctor Strange (Astral Form, Pulse)", "", "Standard", "Hasbro Pulse", True, 42),
        _v("Fan Channel", "Exclusives", "Spider-Man (Cyborg Spider-Man, Pulse)", "", "Standard", "Hasbro Pulse", True, 48),

        # ── Retailer Exclusives (Fan Channel General) ────────────────────
        _v("Fan Channel", "Exclusives", "Captain Marvel (Binary, Fan Channel)", "", "Standard", "Fan Channel", True, 38),
        _v("Fan Channel", "Exclusives", "Black Widow (Grey Suit, Fan Channel)", "", "Standard", "Fan Channel", True, 32),
        _v("Fan Channel", "Exclusives", "Nightcrawler (Age of Apocalypse, Fan Channel)", "", "Standard", "Fan Channel", True, 35),

        # ── BAF Wave Variants (different BAF pieces / recolors) ──────────
        _v("Standard", "Endgame", "Captain America (Endgame, Worthy Mjolnir Variant)", "Thanos", "Standard", "", True, 55),
        _v("Standard", "Infinity War", "Iron Man Mark L (Nano Weapons Variant)", "Cull Obsidian", "Standard", "", True, 58),
        _v("Standard", "X-Men Colossus", "Wolverine (Brown Suit, Unmasked Variant)", "Colossus", "Standard", "", True, 62),
        _v("Standard", "Spider-Man Classics", "Green Goblin (Pumpkin Bomb Variant)", "Kingpin", "Standard", "", True, 55),
        _v("Standard", "Classic Avengers", "Thor (Classic, Bearded Variant)", "Giant-Man", "Standard", "", True, 45),
        _v("Standard", "Venom", "Venom (Tongue-Out Open Mouth Variant)", "Venompool", "Standard", "", True, 55),
        _v("Standard", "X-Men '97 Wave 2", "Wolverine (X-Men '97 Wave 2, Berserker Variant)", "Onslaught", "Standard", "", True, 48),
        _v("Standard", "Wakanda Forever", "Namor (Talokan, Feathered Serpent Variant)", "Attuma", "Standard", "", True, 42),

        # ── Retro Card Packaging vs Standard (repackages on retro card) ──
        _v("Retro", "Retro Spider-Man", "Spider-Man (Iron Spider, Retro Card)", "", "Retro Card", "", True, 38),
        _v("Retro", "Retro Spider-Man", "Miles Morales (Retro Card)", "", "Retro Card", "", True, 35),
        _v("Retro", "Retro Spider-Man", "Spider-Man 2099 (Retro Card)", "", "Retro Card", "", True, 40),
        _v("Retro", "Retro X-Men", "Wolverine (X-Force, Retro Card)", "", "Retro Card", "", True, 42),
        _v("Retro", "Retro X-Men", "Mystique (Retro X-Men)", "", "Retro Card", "", True, 35),
        _v("Retro", "Retro X-Men", "Nightcrawler (Bamf, Retro Card)", "", "Retro Card", "", True, 38),
        _v("Retro", "Retro Avengers", "Hulk (Retro Avengers)", "", "Retro Card", "", True, 35),
        _v("Retro", "Retro Avengers", "Black Widow (Retro Avengers)", "", "Retro Card", "", True, 30),
        _v("Retro", "Retro Avengers", "Iron Man (Stealth, Retro Card)", "", "Retro Card", "", True, 38),
        _v("Retro", "Retro FF", "Namor (Retro FF)", "", "Retro Card", "", True, 30),
        _v("Retro", "Retro Daredevil", "Punisher (War Zone, Retro Card)", "", "Retro Card", "", True, 35),
        _v("Retro", "Retro Daredevil", "Kingpin (Retro Daredevil)", "", "Retro Card", "", True, 38),

        # ── Deluxe vs Standard (deluxe releases of standard figures) ─────
        _v("Deluxe", "Deluxe", "Doctor Doom (Deluxe, with Throne)", "", "Deluxe Box", "", True, 65),
        _v("Deluxe", "Deluxe", "Venom (Deluxe, Wings & Tendrils)", "", "Deluxe Box", "", True, 58),
        _v("Deluxe", "Deluxe", "Green Goblin (Deluxe, with Glider)", "", "Deluxe Box", "", True, 55),
        _v("Deluxe", "Deluxe", "Wolverine (Deluxe, Weapon X Pod)", "", "Deluxe Box", "", True, 55),
        _v("Deluxe", "Deluxe", "Doctor Strange (Deluxe, Astral Projection)", "", "Deluxe Box", "", True, 52),
        _v("Deluxe", "Deluxe", "Magneto (Deluxe, Asteroid M)", "", "Deluxe Box", "", True, 58),
        _v("Deluxe", "Deluxe", "Red Skull (Deluxe, Cosmic Cube)", "", "Deluxe Box", "", True, 52),
        _v("Deluxe", "Deluxe", "Storm (Deluxe, Mohawk with Lightning)", "", "Deluxe Box", "", True, 55),

        # ── 20th Anniversary / Archive Reissues ──────────────────────────
        _v("20th Anniversary", "20th Anniversary", "Daredevil (20th Anniversary)", "", "Window Box", "", True, 38),
        _v("20th Anniversary", "20th Anniversary", "Punisher (20th Anniversary)", "", "Window Box", "", True, 38),
        _v("20th Anniversary", "20th Anniversary", "Cyclops (20th Anniversary)", "", "Window Box", "", True, 40),
        _v("20th Anniversary", "20th Anniversary", "Storm (20th Anniversary)", "", "Window Box", "", True, 40),
        _v("20th Anniversary", "20th Anniversary", "Magneto (20th Anniversary)", "", "Window Box", "", True, 42),
        _v("20th Anniversary", "20th Anniversary", "Gambit (20th Anniversary)", "", "Window Box", "", True, 42),
        _v("20th Anniversary", "Archive", "Spider-Man (Archive Series)", "", "Window Box", "", True, 45),
        _v("20th Anniversary", "Archive", "Wolverine (Archive Series)", "", "Window Box", "", True, 48),
        _v("20th Anniversary", "Archive", "Iron Man (Archive Series)", "", "Window Box", "", True, 42),
        _v("20th Anniversary", "Archive", "Captain America (Archive Series)", "", "Window Box", "", True, 42),
        _v("20th Anniversary", "Archive", "Doctor Doom (Archive Series)", "", "Window Box", "", True, 48),
        _v("20th Anniversary", "Archive", "Hulk (Archive Series)", "", "Window Box", "", True, 42),

        # ── Different Head Sculpt / Accessory Pack Variants ──────────────
        _v("Standard", "No Way Home", "Spider-Man (Integrated Suit, Unmasked Head)", "Armadillo", "Standard", "", True, 35),
        _v("Standard", "Endgame", "Captain America (Endgame, Broken Shield Variant)", "Thanos", "Standard", "", True, 45),
        _v("Standard", "Endgame", "Iron Man Mark LXXXV (Snap Gauntlet Variant)", "Thanos", "Standard", "", True, 48),
        _v("Standard", "X-Men Colossus", "Cyclops (Jim Lee, Visor-Up Variant)", "Colossus", "Standard", "", True, 55),
        _v("Standard", "X-Men Colossus", "Psylocke (Armored Variant)", "Colossus", "Standard", "", True, 48),
        _v("Standard", "X-Men Apocalypse", "Storm (Mohawk, Cape Variant)", "Apocalypse", "Standard", "", True, 48),
        _v("Standard", "Spider-Verse", "Spider-Man 2099 (White Suit Variant)", "Stilt-Man", "Standard", "", True, 52),
        _v("Standard", "Fantastic Four", "Mr. Fantastic (Stretched Arms Variant)", "Super Skrull", "Standard", "", True, 48),
        _v("Standard", "Fantastic Four", "The Thing (Trenchcoat Disguise Variant)", "Super Skrull", "Standard", "", True, 50),
        _v("Standard", "Disney+ Wave 1", "Loki (TVA, President Loki Variant)", "Sam Cap BAF", "Standard", "", True, 42),
        _v("Standard", "Disney+ Wave 1", "Scarlet Witch (WandaVision, Halloween Variant)", "Sam Cap BAF", "Standard", "", True, 45),
        _v("Standard", "Daredevil", "Daredevil (Shadowland Black Suit Variant)", "Man-Thing", "Standard", "", True, 52),
        _v("Standard", "Daredevil", "Punisher (Skull Vest, Extra Weapons Variant)", "Man-Thing", "Standard", "", True, 48),
        _v("Standard", "Classic Avengers", "Iron Man (Extremis, Unmasked Variant)", "Giant-Man", "Standard", "", True, 52),
        _v("Standard", "Multiverse of Madness", "Scarlet Witch (MoM, Darkhold Variant)", "Rintrah", "Standard", "", True, 42),
        _v("Standard", "Spider-Man Classics", "Spider-Man (Classic, Unmasked Peter Parker)", "Kingpin", "Standard", "", True, 62),
        _v("Standard", "Villains", "Kang the Conqueror (Pharaoh Helmet Variant)", "Xemnu", "Standard", "", True, 55),
        _v("Standard", "GOTG Vol 3", "Star-Lord (Vol 3, Helmet-On Variant)", "Cosmo", "Standard", "", True, 35),
        _v("Standard", "Midnight Sons", "Ghost Rider (Johnny Blaze, Flame Head Variant)", "", "Standard", "", True, 48),
        _v("Standard", "X-Men '97", "Rogue (X-Men '97, Flight Jacket Variant)", "Bonebreaker", "Standard", "", True, 42),
        _v("Standard", "Deadpool & Wolverine", "Lady Deadpool (Unmasked Head Variant)", "Cassandra Nova", "Standard", "", True, 45),
    ]


def get_curated_catalog() -> list[dict]:
    """Curated 800+ item catalog: Hasbro Marvel Legends 6-inch action figures,
    BAF waves, Retro series, HasLab, Deluxe, retailer exclusives, and variants."""

    # (series, wave_or_line, name, baf_figure, packaging, exclusive, sealed, price_eur)
    # series: Standard / Retro / 20th Anniversary / HasLab / Deluxe / Fan Channel
    # packaging: Standard / Retro Card / Window Box / Deluxe Box / HasLab Box
    # exclusive: "" (mass retail) or retailer name

    items = [
        # ─── Spider-Man: No Way Home Wave (Armadillo BAF) ──────────────
        ("Standard", "No Way Home", "Spider-Man (Integrated Suit)", "Armadillo", "Standard", "", True, 28),
        ("Standard", "No Way Home", "Spider-Man (Black & Gold Suit)", "Armadillo", "Standard", "", True, 28),
        ("Standard", "No Way Home", "Spider-Man (Upgraded Suit)", "Armadillo", "Standard", "", True, 32),
        ("Standard", "No Way Home", "Doctor Strange (NWH)", "Armadillo", "Standard", "", True, 28),
        ("Standard", "No Way Home", "MJ (NWH)", "Armadillo", "Standard", "", True, 28),
        ("Standard", "No Way Home", "Matt Murdock", "Armadillo", "Standard", "", True, 45),
        ("Standard", "No Way Home", "Doc Ock (NWH)", "Armadillo", "Standard", "", True, 38),

        # ─── Avengers: Endgame Wave (Thanos BAF) ──────────────────────
        ("Standard", "Endgame", "Captain America (Endgame)", "Thanos", "Standard", "", True, 35),
        ("Standard", "Endgame", "Iron Man Mark LXXXV", "Thanos", "Standard", "", True, 38),
        ("Standard", "Endgame", "Thor (Endgame Fat Thor)", "Thanos", "Standard", "", True, 30),
        ("Standard", "Endgame", "Black Widow (Endgame)", "Thanos", "Standard", "", True, 28),
        ("Standard", "Endgame", "Hulk (Professor Hulk)", "Thanos", "Standard", "", True, 32),
        ("Standard", "Endgame", "Rescue (Pepper Potts)", "Thanos", "Standard", "", True, 28),
        ("Standard", "Endgame", "Ronin (Hawkeye)", "Thanos", "Standard", "", True, 32),
        ("Standard", "Endgame", "Nebula (Endgame)", "Thanos", "Standard", "", True, 26),

        # ─── Avengers: Infinity War Wave (Cull Obsidian BAF) ──────────
        ("Standard", "Infinity War", "Iron Man Mark L", "Cull Obsidian", "Standard", "", True, 42),
        ("Standard", "Infinity War", "Thanos (Infinity War)", "Cull Obsidian", "Standard", "", True, 45),
        ("Standard", "Infinity War", "Captain America (Infinity War)", "Cull Obsidian", "Standard", "", True, 35),
        ("Standard", "Infinity War", "Doctor Strange (Infinity War)", "Cull Obsidian", "Standard", "", True, 38),
        ("Standard", "Infinity War", "Scarlet Witch (Infinity War)", "Cull Obsidian", "Standard", "", True, 30),
        ("Standard", "Infinity War", "Proxima Midnight", "Cull Obsidian", "Standard", "", True, 28),
        ("Standard", "Infinity War", "Corvus Glaive", "Cull Obsidian", "Standard", "", True, 28),

        # ─── X-Men '97 Wave (Bonebreaker BAF) ─────────────────────────
        ("Standard", "X-Men '97", "Wolverine (X-Men '97)", "Bonebreaker", "Standard", "", True, 32),
        ("Standard", "X-Men '97", "Cyclops (X-Men '97)", "Bonebreaker", "Standard", "", True, 30),
        ("Standard", "X-Men '97", "Jean Grey (X-Men '97)", "Bonebreaker", "Standard", "", True, 30),
        ("Standard", "X-Men '97", "Storm (X-Men '97)", "Bonebreaker", "Standard", "", True, 35),
        ("Standard", "X-Men '97", "Rogue (X-Men '97)", "Bonebreaker", "Standard", "", True, 38),
        ("Standard", "X-Men '97", "Gambit (X-Men '97)", "Bonebreaker", "Standard", "", True, 35),
        ("Standard", "X-Men '97", "Jubilee (X-Men '97)", "Bonebreaker", "Standard", "", True, 28),
        ("Standard", "X-Men '97", "Magneto (X-Men '97)", "Bonebreaker", "Standard", "", True, 40),
        ("Standard", "X-Men '97", "Bishop (X-Men '97)", "Bonebreaker", "Standard", "", True, 28),
        ("Standard", "X-Men '97", "Morph (X-Men '97)", "Bonebreaker", "Standard", "", True, 28),

        # ─── X-Men Wave (Colossus BAF) ────────────────────────────────
        ("Standard", "X-Men Colossus", "Wolverine (Brown Suit)", "Colossus", "Standard", "", True, 55),
        ("Standard", "X-Men Colossus", "Dark Phoenix", "Colossus", "Standard", "", True, 45),
        ("Standard", "X-Men Colossus", "Psylocke", "Colossus", "Standard", "", True, 40),
        ("Standard", "X-Men Colossus", "Cyclops (Jim Lee)", "Colossus", "Standard", "", True, 48),
        ("Standard", "X-Men Colossus", "Mystique", "Colossus", "Standard", "", True, 35),
        ("Standard", "X-Men Colossus", "Sabretooth", "Colossus", "Standard", "", True, 32),
        ("Standard", "X-Men Colossus", "Nightcrawler", "Colossus", "Standard", "", True, 42),

        # ─── X-Men Wave (Apocalypse BAF) ──────────────────────────────
        ("Standard", "X-Men Apocalypse", "Professor X (Hoverchair)", "Apocalypse", "Standard", "", True, 55),
        ("Standard", "X-Men Apocalypse", "Magneto (White)", "Apocalypse", "Standard", "", True, 45),
        ("Standard", "X-Men Apocalypse", "Storm (Mohawk)", "Apocalypse", "Standard", "", True, 42),
        ("Standard", "X-Men Apocalypse", "Archangel", "Apocalypse", "Standard", "", True, 48),
        ("Standard", "X-Men Apocalypse", "Cable", "Apocalypse", "Standard", "", True, 35),
        ("Standard", "X-Men Apocalypse", "Gladiator", "Apocalypse", "Standard", "", True, 32),
        ("Standard", "X-Men Apocalypse", "Multiple Man", "Apocalypse", "Standard", "", True, 38),

        # ─── Deadpool & Wolverine Wave (Cassandra Nova BAF) ───────────
        ("Standard", "Deadpool & Wolverine", "Deadpool (Movie)", "Cassandra Nova", "Standard", "", True, 30),
        ("Standard", "Deadpool & Wolverine", "Wolverine (Movie)", "Cassandra Nova", "Standard", "", True, 32),
        ("Standard", "Deadpool & Wolverine", "Lady Deadpool", "Cassandra Nova", "Standard", "", True, 35),
        ("Standard", "Deadpool & Wolverine", "Dogpool", "Cassandra Nova", "Standard", "", True, 28),
        ("Standard", "Deadpool & Wolverine", "Nicepool", "Cassandra Nova", "Standard", "", True, 25),
        ("Standard", "Deadpool & Wolverine", "Pyro (Deadpool Movie)", "Cassandra Nova", "Standard", "", True, 25),

        # ─── Black Panther: Wakanda Forever (Attuma BAF) ──────────────
        ("Standard", "Wakanda Forever", "Black Panther (Shuri)", "Attuma", "Standard", "", True, 28),
        ("Standard", "Wakanda Forever", "Namor", "Attuma", "Standard", "", True, 32),
        ("Standard", "Wakanda Forever", "Ironheart", "Attuma", "Standard", "", True, 25),
        ("Standard", "Wakanda Forever", "Okoye (Wakanda Forever)", "Attuma", "Standard", "", True, 28),
        ("Standard", "Wakanda Forever", "M'Baku", "Attuma", "Standard", "", True, 26),

        # ─── Thor: Love and Thunder Wave (Korg BAF) ───────────────────
        ("Standard", "Love and Thunder", "Thor (L&T)", "Korg", "Standard", "", True, 28),
        ("Standard", "Love and Thunder", "Mighty Thor (Jane Foster)", "Korg", "Standard", "", True, 32),
        ("Standard", "Love and Thunder", "Gorr the God Butcher", "Korg", "Standard", "", True, 30),
        ("Standard", "Love and Thunder", "King Valkyrie", "Korg", "Standard", "", True, 28),
        ("Standard", "Love and Thunder", "Star-Lord (L&T)", "Korg", "Standard", "", True, 26),
        ("Standard", "Love and Thunder", "Ravager Thor", "Korg", "Standard", "", True, 26),

        # ─── Guardians of the Galaxy Vol 3 Wave (Cosmo BAF) ──────────
        ("Standard", "GOTG Vol 3", "Star-Lord (Vol 3)", "Cosmo", "Standard", "", True, 28),
        ("Standard", "GOTG Vol 3", "Rocket (Vol 3)", "Cosmo", "Standard", "", True, 30),
        ("Standard", "GOTG Vol 3", "Gamora (Vol 3)", "Cosmo", "Standard", "", True, 28),
        ("Standard", "GOTG Vol 3", "Drax (Vol 3)", "Cosmo", "Standard", "", True, 26),
        ("Standard", "GOTG Vol 3", "Adam Warlock", "Cosmo", "Standard", "", True, 32),
        ("Standard", "GOTG Vol 3", "High Evolutionary", "Cosmo", "Standard", "", True, 28),
        ("Standard", "GOTG Vol 3", "Mantis (Vol 3)", "Cosmo", "Standard", "", True, 25),

        # ─── Doctor Strange MoM Wave (Rintrah BAF) ────────────────────
        ("Standard", "Multiverse of Madness", "Doctor Strange (MoM)", "Rintrah", "Standard", "", True, 30),
        ("Standard", "Multiverse of Madness", "Scarlet Witch (MoM)", "Rintrah", "Standard", "", True, 35),
        ("Standard", "Multiverse of Madness", "America Chavez", "Rintrah", "Standard", "", True, 28),
        ("Standard", "Multiverse of Madness", "Wong", "Rintrah", "Standard", "", True, 28),
        ("Standard", "Multiverse of Madness", "D'Spayre", "Rintrah", "Standard", "", True, 25),

        # ─── Moon Knight / She-Hulk / Ms Marvel Wave (Infinity Ultron BAF) ──
        ("Standard", "Disney+ Wave 2", "Moon Knight", "Infinity Ultron", "Standard", "", True, 32),
        ("Standard", "Disney+ Wave 2", "Mr. Knight", "Infinity Ultron", "Standard", "", True, 30),
        ("Standard", "Disney+ Wave 2", "She-Hulk", "Infinity Ultron", "Standard", "", True, 28),
        ("Standard", "Disney+ Wave 2", "Ms. Marvel (Kamala Khan)", "Infinity Ultron", "Standard", "", True, 28),
        ("Standard", "Disney+ Wave 2", "Kate Bishop", "Infinity Ultron", "Standard", "", True, 30),

        # ─── WandaVision / Loki / Falcon & Winter Soldier Wave (Captain America BAF) ──
        ("Standard", "Disney+ Wave 1", "Loki (TVA)", "Sam Cap BAF", "Standard", "", True, 35),
        ("Standard", "Disney+ Wave 1", "Sylvie", "Sam Cap BAF", "Standard", "", True, 30),
        ("Standard", "Disney+ Wave 1", "Scarlet Witch (WandaVision)", "Sam Cap BAF", "Standard", "", True, 38),
        ("Standard", "Disney+ Wave 1", "Vision (WandaVision)", "Sam Cap BAF", "Standard", "", True, 32),
        ("Standard", "Disney+ Wave 1", "US Agent", "Sam Cap BAF", "Standard", "", True, 30),
        ("Standard", "Disney+ Wave 1", "Baron Zemo (Disney+)", "Sam Cap BAF", "Standard", "", True, 28),

        # ─── Spider-Verse Wave (Stilt-Man BAF) ────────────────────────
        ("Standard", "Spider-Verse", "Miles Morales (Into the Spider-Verse)", "Stilt-Man", "Standard", "", True, 42),
        ("Standard", "Spider-Verse", "Spider-Gwen (Ghost-Spider)", "Stilt-Man", "Standard", "", True, 40),
        ("Standard", "Spider-Verse", "Spider-Man 2099", "Stilt-Man", "Standard", "", True, 45),
        ("Standard", "Spider-Verse", "Spider-Punk", "Stilt-Man", "Standard", "", True, 38),
        ("Standard", "Spider-Verse", "Spider-Ham", "Stilt-Man", "Standard", "", True, 35),
        ("Standard", "Spider-Verse", "Spider-Man Noir", "Stilt-Man", "Standard", "", True, 32),

        # ─── Venom Wave (Venompool BAF) ───────────────────────────────
        ("Standard", "Venom", "Venom", "Venompool", "Standard", "", True, 48),
        ("Standard", "Venom", "Carnage", "Venompool", "Standard", "", True, 55),
        ("Standard", "Venom", "Anti-Venom", "Venompool", "Standard", "", True, 38),
        ("Standard", "Venom", "Toxin", "Venompool", "Standard", "", True, 35),
        ("Standard", "Venom", "Scream", "Venompool", "Standard", "", True, 32),
        ("Standard", "Venom", "Phage", "Venompool", "Standard", "", True, 28),
        ("Standard", "Venom", "Morbius", "Venompool", "Standard", "", True, 30),

        # ─── Classic Avengers Wave (Giant-Man BAF) ────────────────────
        ("Standard", "Classic Avengers", "Captain America (Classic)", "Giant-Man", "Standard", "", True, 40),
        ("Standard", "Classic Avengers", "Iron Man (Extremis)", "Giant-Man", "Standard", "", True, 45),
        ("Standard", "Classic Avengers", "Thor (Classic)", "Giant-Man", "Standard", "", True, 38),
        ("Standard", "Classic Avengers", "Hulk (Classic)", "Giant-Man", "Standard", "", True, 42),
        ("Standard", "Classic Avengers", "Hawkeye (Classic)", "Giant-Man", "Standard", "", True, 35),
        ("Standard", "Classic Avengers", "Vision (Classic)", "Giant-Man", "Standard", "", True, 38),
        ("Standard", "Classic Avengers", "Wasp (Classic)", "Giant-Man", "Standard", "", True, 32),

        # ─── Fantastic Four Wave (Super Skrull BAF) ───────────────────
        ("Standard", "Fantastic Four", "Mr. Fantastic", "Super Skrull", "Standard", "", True, 42),
        ("Standard", "Fantastic Four", "Invisible Woman", "Super Skrull", "Standard", "", True, 40),
        ("Standard", "Fantastic Four", "Human Torch", "Super Skrull", "Standard", "", True, 38),
        ("Standard", "Fantastic Four", "The Thing", "Super Skrull", "Standard", "", True, 45),
        ("Standard", "Fantastic Four", "Doctor Doom", "Super Skrull", "Standard", "", True, 55),
        ("Standard", "Fantastic Four", "Silver Surfer", "Super Skrull", "Standard", "", True, 48),

        # ─── Spider-Man Classic Wave (Kingpin BAF) ────────────────────
        ("Standard", "Spider-Man Classics", "Spider-Man (Classic Red & Blue)", "Kingpin", "Standard", "", True, 55),
        ("Standard", "Spider-Man Classics", "Kraven the Hunter", "Kingpin", "Standard", "", True, 35),
        ("Standard", "Spider-Man Classics", "Mysterio", "Kingpin", "Standard", "", True, 42),
        ("Standard", "Spider-Man Classics", "Green Goblin", "Kingpin", "Standard", "", True, 48),
        ("Standard", "Spider-Man Classics", "Doctor Octopus", "Kingpin", "Standard", "", True, 42),
        ("Standard", "Spider-Man Classics", "Electro", "Kingpin", "Standard", "", True, 35),
        ("Standard", "Spider-Man Classics", "Sandman", "Kingpin", "Standard", "", True, 38),
        ("Standard", "Spider-Man Classics", "Vulture", "Kingpin", "Standard", "", True, 32),
        ("Standard", "Spider-Man Classics", "Rhino", "Kingpin", "Standard", "", True, 38),
        ("Standard", "Spider-Man Classics", "Scorpion", "Kingpin", "Standard", "", True, 30),
        ("Standard", "Spider-Man Classics", "Hobgoblin", "Kingpin", "Standard", "", True, 45),
        ("Standard", "Spider-Man Classics", "Black Cat", "Kingpin", "Standard", "", True, 40),

        # ─── Villains Wave (Xemnu BAF) ────────────────────────────────
        ("Standard", "Villains", "Red Skull", "Xemnu", "Standard", "", True, 42),
        ("Standard", "Villains", "Taskmaster", "Xemnu", "Standard", "", True, 30),
        ("Standard", "Villains", "Baron Zemo", "Xemnu", "Standard", "", True, 35),
        ("Standard", "Villains", "Crossbones", "Xemnu", "Standard", "", True, 28),
        ("Standard", "Villains", "Ultron", "Xemnu", "Standard", "", True, 42),
        ("Standard", "Villains", "Kang the Conqueror", "Xemnu", "Standard", "", True, 48),
        ("Standard", "Villains", "MODOK", "Xemnu", "Standard", "", True, 55),
        ("Standard", "Villains", "The Hood", "Xemnu", "Standard", "", True, 28),
        ("Standard", "Villains", "Arcade", "Xemnu", "Standard", "", True, 25),

        # ─── Daredevil Wave (Man-Thing BAF) ───────────────────────────
        ("Standard", "Daredevil", "Daredevil (Classic Red)", "Man-Thing", "Standard", "", True, 45),
        ("Standard", "Daredevil", "Elektra", "Man-Thing", "Standard", "", True, 35),
        ("Standard", "Daredevil", "Bullseye", "Man-Thing", "Standard", "", True, 32),
        ("Standard", "Daredevil", "Punisher", "Man-Thing", "Standard", "", True, 42),
        ("Standard", "Daredevil", "Luke Cage", "Man-Thing", "Standard", "", True, 30),
        ("Standard", "Daredevil", "Iron Fist", "Man-Thing", "Standard", "", True, 28),
        ("Standard", "Daredevil", "Jessica Jones", "Man-Thing", "Standard", "", True, 25),

        # ─── Captain America Wave (Joe Fixit BAF) ─────────────────────
        ("Standard", "Cap Sam Wilson", "Captain America (Sam Wilson)", "Joe Fixit", "Standard", "", True, 38),
        ("Standard", "Cap Sam Wilson", "Winter Soldier (Comic)", "Joe Fixit", "Standard", "", True, 32),
        ("Standard", "Cap Sam Wilson", "Falcon (Classic)", "Joe Fixit", "Standard", "", True, 28),
        ("Standard", "Cap Sam Wilson", "Sharon Carter", "Joe Fixit", "Standard", "", True, 25),
        ("Standard", "Cap Sam Wilson", "USAgent (Comic)", "Joe Fixit", "Standard", "", True, 28),

        # ─── Eternals Wave (Gilgamesh BAF) ────────────────────────────
        ("Standard", "Eternals", "Ikaris", "Gilgamesh", "Standard", "", True, 22),
        ("Standard", "Eternals", "Sersi", "Gilgamesh", "Standard", "", True, 22),
        ("Standard", "Eternals", "Thena", "Gilgamesh", "Standard", "", True, 25),
        ("Standard", "Eternals", "Kingo", "Gilgamesh", "Standard", "", True, 20),
        ("Standard", "Eternals", "Makkari", "Gilgamesh", "Standard", "", True, 22),
        ("Standard", "Eternals", "Druig", "Gilgamesh", "Standard", "", True, 20),

        # ─── Ant-Man & the Wasp: Quantumania Wave (Cassie Lang BAF) ──
        ("Standard", "Quantumania", "Ant-Man (Quantumania)", "Cassie Lang", "Standard", "", True, 25),
        ("Standard", "Quantumania", "The Wasp (Quantumania)", "Cassie Lang", "Standard", "", True, 25),
        ("Standard", "Quantumania", "Kang (Quantumania)", "Cassie Lang", "Standard", "", True, 35),
        ("Standard", "Quantumania", "M.O.D.O.K. (Quantumania)", "Cassie Lang", "Standard", "", True, 30),

        # ─── The Marvels Wave (Totally Awesome Hulk BAF) ─────────────
        ("Standard", "The Marvels", "Captain Marvel (The Marvels)", "Totally Awesome Hulk", "Standard", "", True, 25),
        ("Standard", "The Marvels", "Monica Rambeau", "Totally Awesome Hulk", "Standard", "", True, 25),
        ("Standard", "The Marvels", "Ms. Marvel (Kamala, Marvels)", "Totally Awesome Hulk", "Standard", "", True, 28),

        # ─── Secret Wars Wave (Beyonder BAF) ──────────────────────────
        ("Standard", "Secret Wars", "Spider-Man (Secret Wars)", "Beyonder", "Standard", "", True, 42),
        ("Standard", "Secret Wars", "Doom (Secret Wars)", "Beyonder", "Standard", "", True, 48),
        ("Standard", "Secret Wars", "Wolverine (Secret Wars)", "Beyonder", "Standard", "", True, 40),
        ("Standard", "Secret Wars", "Magneto (Secret Wars)", "Beyonder", "Standard", "", True, 38),
        ("Standard", "Secret Wars", "Iron Man (Secret Wars)", "Beyonder", "Standard", "", True, 35),
        ("Standard", "Secret Wars", "Captain America (Secret Wars)", "Beyonder", "Standard", "", True, 38),

        # ─── Thunderbolts Wave ────────────────────────────────────────
        ("Standard", "Thunderbolts", "Bucky Barnes (Thunderbolts)", "", "Standard", "", True, 28),
        ("Standard", "Thunderbolts", "Yelena Belova (Thunderbolts)", "", "Standard", "", True, 28),
        ("Standard", "Thunderbolts", "Red Guardian (Thunderbolts)", "", "Standard", "", True, 25),
        ("Standard", "Thunderbolts", "Taskmaster (Thunderbolts)", "", "Standard", "", True, 25),
        ("Standard", "Thunderbolts", "Ghost (Thunderbolts)", "", "Standard", "", True, 25),

        # ─── Retro Series (Vintage Card Backs) ────────────────────────
        ("Retro", "Retro Spider-Man", "Spider-Man (Retro)", "", "Retro Card", "", True, 35),
        ("Retro", "Retro Spider-Man", "Symbiote Spider-Man (Retro)", "", "Retro Card", "", True, 40),
        ("Retro", "Retro Spider-Man", "Scarlet Spider (Ben Reilly, Retro)", "", "Retro Card", "", True, 35),
        ("Retro", "Retro Spider-Man", "Green Goblin (Retro)", "", "Retro Card", "", True, 42),
        ("Retro", "Retro Spider-Man", "Electro (Retro)", "", "Retro Card", "", True, 30),
        ("Retro", "Retro Spider-Man", "Shocker (Retro)", "", "Retro Card", "", True, 25),
        ("Retro", "Retro Spider-Man", "Hobgoblin (Retro)", "", "Retro Card", "", True, 38),
        ("Retro", "Retro Spider-Man", "J. Jonah Jameson (Retro)", "", "Retro Card", "", True, 28),
        ("Retro", "Retro X-Men", "Wolverine (Retro X-Men)", "", "Retro Card", "", True, 42),
        ("Retro", "Retro X-Men", "Storm (Retro X-Men)", "", "Retro Card", "", True, 38),
        ("Retro", "Retro X-Men", "Cyclops (Retro X-Men)", "", "Retro Card", "", True, 35),
        ("Retro", "Retro X-Men", "Rogue (Retro X-Men)", "", "Retro Card", "", True, 40),
        ("Retro", "Retro X-Men", "Gambit (Retro X-Men)", "", "Retro Card", "", True, 38),
        ("Retro", "Retro X-Men", "Jean Grey (Retro X-Men)", "", "Retro Card", "", True, 35),
        ("Retro", "Retro X-Men", "Magneto (Retro X-Men)", "", "Retro Card", "", True, 38),
        ("Retro", "Retro X-Men", "Beast (Retro X-Men)", "", "Retro Card", "", True, 32),
        ("Retro", "Retro Avengers", "Captain America (Retro)", "", "Retro Card", "", True, 35),
        ("Retro", "Retro Avengers", "Iron Man (Retro)", "", "Retro Card", "", True, 38),
        ("Retro", "Retro Avengers", "Thor (Retro)", "", "Retro Card", "", True, 35),
        ("Retro", "Retro Avengers", "Hawkeye (Retro)", "", "Retro Card", "", True, 28),
        ("Retro", "Retro Avengers", "Black Panther (Retro)", "", "Retro Card", "", True, 32),
        ("Retro", "Retro Avengers", "Scarlet Witch (Retro)", "", "Retro Card", "", True, 30),
        ("Retro", "Retro FF", "Mr. Fantastic (Retro)", "", "Retro Card", "", True, 30),
        ("Retro", "Retro FF", "Invisible Woman (Retro)", "", "Retro Card", "", True, 28),
        ("Retro", "Retro FF", "Human Torch (Retro)", "", "Retro Card", "", True, 28),
        ("Retro", "Retro FF", "The Thing (Retro)", "", "Retro Card", "", True, 32),
        ("Retro", "Retro Daredevil", "Daredevil (Retro)", "", "Retro Card", "", True, 38),
        ("Retro", "Retro Daredevil", "Punisher (Retro)", "", "Retro Card", "", True, 32),
        ("Retro", "Retro Daredevil", "Elektra (Retro)", "", "Retro Card", "", True, 28),
        ("Retro", "Retro Daredevil", "Bullseye (Retro)", "", "Retro Card", "", True, 25),

        # ─── 20th Anniversary Series ──────────────────────────────────
        ("20th Anniversary", "20th Anniversary", "Iron Man (20th)", "", "Window Box", "", True, 38),
        ("20th Anniversary", "20th Anniversary", "Captain America (20th)", "", "Window Box", "", True, 38),
        ("20th Anniversary", "20th Anniversary", "Spider-Man (20th)", "", "Window Box", "", True, 40),
        ("20th Anniversary", "20th Anniversary", "Wolverine (20th)", "", "Window Box", "", True, 42),
        ("20th Anniversary", "20th Anniversary", "Hulk (20th)", "", "Window Box", "", True, 38),
        ("20th Anniversary", "20th Anniversary", "Thor (20th)", "", "Window Box", "", True, 35),
        ("20th Anniversary", "20th Anniversary", "Black Panther (20th)", "", "Window Box", "", True, 35),
        ("20th Anniversary", "20th Anniversary", "Doctor Strange (20th)", "", "Window Box", "", True, 35),

        # ─── HasLab Exclusives ─────────────────────────────────────────
        ("HasLab", "HasLab", "Galactus (32-inch HasLab)", "", "HasLab Box", "HasLab", True, 550),
        ("HasLab", "HasLab", "Sentinel (26-inch HasLab)", "", "HasLab Box", "HasLab", True, 480),
        ("HasLab", "HasLab", "Ghost Rider Engine of Vengeance", "", "HasLab Box", "HasLab", True, 420),
        ("HasLab", "HasLab", "Robbie Reyes Ghost Rider & Hell Charger", "", "HasLab Box", "HasLab", True, 380),
        ("HasLab", "HasLab", "Giant-Man (HasLab)", "", "HasLab Box", "HasLab", True, 350),

        # ─── Deluxe / Rider Series ─────────────────────────────────────
        ("Deluxe", "Deluxe", "Thanos (Deluxe Endgame)", "", "Deluxe Box", "", True, 55),
        ("Deluxe", "Deluxe", "Hulk (Deluxe Endgame)", "", "Deluxe Box", "", True, 48),
        ("Deluxe", "Deluxe", "Iron Man Mark III (Deluxe)", "", "Deluxe Box", "", True, 52),
        ("Deluxe", "Deluxe", "War Machine (Deluxe)", "", "Deluxe Box", "", True, 48),
        ("Deluxe", "Deluxe", "Venom (Deluxe)", "", "Deluxe Box", "", True, 52),
        ("Deluxe", "Deluxe", "Carnage (Deluxe)", "", "Deluxe Box", "", True, 55),
        ("Deluxe", "Deluxe", "Kingpin (Deluxe)", "", "Deluxe Box", "", True, 48),
        ("Deluxe", "Deluxe", "M.O.D.O.K. (Deluxe)", "", "Deluxe Box", "", True, 50),
        ("Deluxe", "Rider Series", "Cosmic Ghost Rider & Bike", "", "Deluxe Box", "", True, 58),
        ("Deluxe", "Rider Series", "Black Widow with Motorcycle", "", "Deluxe Box", "", True, 50),
        ("Deluxe", "Rider Series", "Punisher with War Machine Armor", "", "Deluxe Box", "", True, 55),
        ("Deluxe", "Deluxe", "Maestro (Deluxe)", "", "Deluxe Box", "", True, 48),
        ("Deluxe", "Deluxe", "Absorbing Man (Deluxe)", "", "Deluxe Box", "", True, 42),
        ("Deluxe", "Deluxe", "The Fallen One (Deluxe)", "", "Deluxe Box", "", True, 45),

        # ─── Fan Channel / Amazon / Target / Walgreens / Pulse Exclusives ──
        ("Fan Channel", "Exclusives", "Wolverine (Brown Suit, Amazon)", "", "Standard", "Amazon", True, 42),
        ("Fan Channel", "Exclusives", "Iron Man Mark I (Pulse Exclusive)", "", "Standard", "Hasbro Pulse", True, 45),
        ("Fan Channel", "Exclusives", "Deadpool (X-Force, Target)", "", "Standard", "Target", True, 38),
        ("Fan Channel", "Exclusives", "Spider-Man (Negative Zone, Walgreens)", "", "Standard", "Walgreens", True, 48),
        ("Fan Channel", "Exclusives", "Mystique (Walgreens)", "", "Standard", "Walgreens", True, 42),
        ("Fan Channel", "Exclusives", "Human Torch (Walgreens)", "", "Standard", "Walgreens", True, 40),
        ("Fan Channel", "Exclusives", "Namor (Walgreens)", "", "Standard", "Walgreens", True, 35),
        ("Fan Channel", "Exclusives", "Moon Knight (Walgreens)", "", "Standard", "Walgreens", True, 42),
        ("Fan Channel", "Exclusives", "Magik (Walgreens)", "", "Standard", "Walgreens", True, 38),
        ("Fan Channel", "Exclusives", "Silver Centurion Iron Man (Target)", "", "Standard", "Target", True, 40),
        ("Fan Channel", "Exclusives", "Hulk Compound Smash 2-Pack (Target)", "", "Standard", "Target", True, 55),
        ("Fan Channel", "Exclusives", "Captain America & Crossbones 2-Pack (Amazon)", "", "Standard", "Amazon", True, 52),
        ("Fan Channel", "Exclusives", "Psylocke (Pulse Exclusive)", "", "Standard", "Hasbro Pulse", True, 42),
        ("Fan Channel", "Exclusives", "Storm & Thunderbird 2-Pack (Target)", "", "Standard", "Target", True, 58),
        ("Fan Channel", "Exclusives", "Jean Grey (Pulse Exclusive)", "", "Standard", "Hasbro Pulse", True, 38),
        ("Fan Channel", "Exclusives", "Rogue & Pyro 2-Pack (Amazon)", "", "Standard", "Amazon", True, 55),
        ("Fan Channel", "Exclusives", "Wolverine vs Sabretooth 2-Pack", "", "Standard", "Amazon", True, 60),
        ("Fan Channel", "Exclusives", "Beta Ray Bill (Fan Channel)", "", "Standard", "Fan Channel", True, 38),
        ("Fan Channel", "Exclusives", "Nova (Richard Rider, Fan Channel)", "", "Standard", "Fan Channel", True, 32),
        ("Fan Channel", "Exclusives", "Iron Fist (Fan Channel)", "", "Standard", "Fan Channel", True, 28),
        ("Fan Channel", "Exclusives", "Silk (Fan Channel)", "", "Standard", "Fan Channel", True, 35),

        # ─── Additional Classic X-Men ─────────────────────────────────
        ("Standard", "X-Men Classic", "Iceman", "", "Standard", "", True, 30),
        ("Standard", "X-Men Classic", "Banshee", "", "Standard", "", True, 28),
        ("Standard", "X-Men Classic", "Polaris", "", "Standard", "", True, 30),
        ("Standard", "X-Men Classic", "Havok", "", "Standard", "", True, 28),
        ("Standard", "X-Men Classic", "Dazzler", "", "Standard", "", True, 25),
        ("Standard", "X-Men Classic", "Kitty Pryde", "", "Standard", "", True, 28),
        ("Standard", "X-Men Classic", "Forge", "", "Standard", "", True, 25),
        ("Standard", "X-Men Classic", "Sunspot", "", "Standard", "", True, 25),
        ("Standard", "X-Men Classic", "Cannonball", "", "Standard", "", True, 25),
        ("Standard", "X-Men Classic", "Emma Frost", "", "Standard", "", True, 35),
        ("Standard", "X-Men Classic", "Colossus", "", "Standard", "", True, 38),
        ("Standard", "X-Men Classic", "Sentinel (Standard Size)", "", "Standard", "", True, 42),

        # ─── Classic Avengers & Iron Man Variations ───────────────────
        ("Standard", "Avengers Classic 2", "War Machine (Classic)", "", "Standard", "", True, 32),
        ("Standard", "Avengers Classic 2", "Wonder Man", "", "Standard", "", True, 28),
        ("Standard", "Avengers Classic 2", "Hercules", "", "Standard", "", True, 30),
        ("Standard", "Avengers Classic 2", "Black Knight", "", "Standard", "", True, 28),
        ("Standard", "Avengers Classic 2", "Tigra", "", "Standard", "", True, 25),
        ("Standard", "Avengers Classic 2", "She-Hulk (Comic)", "", "Standard", "", True, 32),
        ("Standard", "Avengers Classic 2", "Quicksilver", "", "Standard", "", True, 28),
        ("Standard", "Avengers Classic 2", "Sersi (Comic)", "", "Standard", "", True, 25),

        # ─── Cosmic Heroes ────────────────────────────────────────────
        ("Standard", "Cosmic", "Captain Marvel (Classic)", "", "Standard", "", True, 30),
        ("Standard", "Cosmic", "Adam Warlock (Comics)", "", "Standard", "", True, 32),
        ("Standard", "Cosmic", "Quasar", "", "Standard", "", True, 28),
        ("Standard", "Cosmic", "Gladiator (Shi'ar)", "", "Standard", "", True, 30),
        ("Standard", "Cosmic", "Super-Skrull (Cosmic)", "", "Standard", "", True, 28),
        ("Standard", "Cosmic", "Thanos (Comic, Throne)", "", "Standard", "", True, 55),

        # ─── Black Panther & Wakanda ──────────────────────────────────
        ("Standard", "Wakanda", "Black Panther (Comic)", "", "Standard", "", True, 35),
        ("Standard", "Wakanda", "Killmonger (Comic)", "", "Standard", "", True, 28),
        ("Standard", "Wakanda", "Shuri (Comic)", "", "Standard", "", True, 25),
        ("Standard", "Wakanda", "Okoye (Comic)", "", "Standard", "", True, 25),
        ("Standard", "Wakanda", "Nakia", "", "Standard", "", True, 25),

        # ─── Loki / Thunderbolts / Dark Avengers ──────────────────────
        ("Standard", "Dark", "Loki (Classic)", "", "Standard", "", True, 35),
        ("Standard", "Dark", "Enchantress", "", "Standard", "", True, 30),
        ("Standard", "Dark", "Executioner", "", "Standard", "", True, 28),
        ("Standard", "Dark", "Dark Phoenix (Comics)", "", "Standard", "", True, 42),
        ("Standard", "Dark", "Sentry (Dark Avengers)", "", "Standard", "", True, 30),
        ("Standard", "Dark", "Norman Osborn Iron Patriot", "", "Standard", "", True, 35),

        # ─── Thunderbolts (Comics) ────────────────────────────────────
        ("Standard", "Thunderbolts Comics", "Citizen V", "", "Standard", "", True, 25),
        ("Standard", "Thunderbolts Comics", "Songbird", "", "Standard", "", True, 25),
        ("Standard", "Thunderbolts Comics", "Moonstone", "", "Standard", "", True, 22),
        ("Standard", "Thunderbolts Comics", "Atlas", "", "Standard", "", True, 22),
        ("Standard", "Thunderbolts Comics", "Radioactive Man", "", "Standard", "", True, 22),

        # ─── She-Hulk / Hulk Family ──────────────────────────────────
        ("Standard", "Hulk Family", "Red Hulk", "", "Standard", "", True, 42),
        ("Standard", "Hulk Family", "A-Bomb (Rick Jones)", "", "Standard", "", True, 28),
        ("Standard", "Hulk Family", "Skaar", "", "Standard", "", True, 25),
        ("Standard", "Hulk Family", "Maestro", "", "Standard", "", True, 35),
        ("Standard", "Hulk Family", "Hulk (Immortal)", "", "Standard", "", True, 38),
        ("Standard", "Hulk Family", "Abomination", "", "Standard", "", True, 35),
        ("Standard", "Hulk Family", "Leader", "", "Standard", "", True, 28),

        # ─── Doctor Strange / Mystic ──────────────────────────────────
        ("Standard", "Mystic", "Doctor Strange (Comic)", "", "Standard", "", True, 35),
        ("Standard", "Mystic", "Clea", "", "Standard", "", True, 25),
        ("Standard", "Mystic", "Brother Voodoo", "", "Standard", "", True, 28),
        ("Standard", "Mystic", "Dormammu", "", "Standard", "", True, 42),
        ("Standard", "Mystic", "Agatha Harkness", "", "Standard", "", True, 28),

        # ─── Classic Villains Wave ────────────────────────────────────
        ("Standard", "Classic Villains", "Loki (Helmet, Comic)", "", "Standard", "", True, 35),
        ("Standard", "Classic Villains", "Absorbing Man (Standard)", "", "Standard", "", True, 28),
        ("Standard", "Classic Villains", "Wrecker", "", "Standard", "", True, 25),
        ("Standard", "Classic Villains", "Whirlwind", "", "Standard", "", True, 22),
        ("Standard", "Classic Villains", "Constrictor", "", "Standard", "", True, 22),
        ("Standard", "Classic Villains", "Batroc the Leaper", "", "Standard", "", True, 22),
        ("Standard", "Classic Villains", "Living Laser", "", "Standard", "", True, 20),

        # ─── Additional waves & one-offs ──────────────────────────────
        ("Standard", "What If...?", "Captain Carter (What If)", "", "Standard", "", True, 28),
        ("Standard", "What If...?", "T'Challa Star-Lord (What If)", "", "Standard", "", True, 28),
        ("Standard", "What If...?", "Zombie Hunter Spider-Man (What If)", "", "Standard", "", True, 30),
        ("Standard", "What If...?", "Doctor Strange Supreme (What If)", "", "Standard", "", True, 30),
        ("Standard", "Iron Man", "Iron Man (Model 70)", "", "Standard", "", True, 35),
        ("Standard", "Iron Man", "Iron Man (Stealth)", "", "Standard", "", True, 32),
        ("Standard", "Iron Man", "Iron Man (Silver Centurion Comic)", "", "Standard", "", True, 35),
        ("Standard", "Iron Man", "Iron Man (Modular Armor)", "", "Standard", "", True, 32),
        ("Standard", "Iron Man", "Iron Monger", "", "Standard", "", True, 42),
        ("Standard", "Alpha Flight", "Puck", "", "Standard", "", True, 25),
        ("Standard", "Alpha Flight", "Snowbird", "", "Standard", "", True, 22),
        ("Standard", "Alpha Flight", "Vindicator", "", "Standard", "", True, 22),
        ("Standard", "Alpha Flight", "Sasquatch", "", "Standard", "", True, 28),
        ("Standard", "Inhumans", "Black Bolt", "", "Standard", "", True, 35),
        ("Standard", "Inhumans", "Medusa", "", "Standard", "", True, 30),
        ("Standard", "Inhumans", "Karnak", "", "Standard", "", True, 25),
        ("Standard", "Inhumans", "Gorgon", "", "Standard", "", True, 25),
        ("Standard", "New Warriors", "Firestar", "", "Standard", "", True, 28),
        ("Standard", "New Warriors", "Justice", "", "Standard", "", True, 22),
        ("Standard", "New Warriors", "Speedball", "", "Standard", "", True, 22),
        ("Standard", "Midnight Sons", "Blade (Classic)", "", "Standard", "", True, 38),
        ("Standard", "Midnight Sons", "Morbius (Classic)", "", "Standard", "", True, 30),
        ("Standard", "Midnight Sons", "Ghost Rider (Johnny Blaze)", "", "Standard", "", True, 42),
        ("Standard", "Midnight Sons", "Ghost Rider (Danny Ketch)", "", "Standard", "", True, 35),
        ("Standard", "Midnight Sons", "Werewolf by Night", "", "Standard", "", True, 28),
        ("Standard", "Age of Apocalypse", "Apocalypse (AoA)", "", "Standard", "", True, 42),
        ("Standard", "Age of Apocalypse", "Weapon X (AoA)", "", "Standard", "", True, 38),
        ("Standard", "Age of Apocalypse", "Rogue (AoA)", "", "Standard", "", True, 32),
        ("Standard", "Age of Apocalypse", "Sunfire (AoA)", "", "Standard", "", True, 28),
        ("Standard", "Age of Apocalypse", "Morph (AoA)", "", "Standard", "", True, 25),
        ("Standard", "Age of Apocalypse", "Wild Child (AoA)", "", "Standard", "", True, 22),
        ("Standard", "New Mutants", "Dani Moonstar", "", "Standard", "", True, 25),
        ("Standard", "New Mutants", "Magik (Illyana, Comic)", "", "Standard", "", True, 28),
        ("Standard", "New Mutants", "Wolfsbane", "", "Standard", "", True, 22),
        ("Standard", "New Mutants", "Warlock", "", "Standard", "", True, 25),

        # ─── MCU Additional ───────────────────────────────────────────
        ("Standard", "MCU Additional", "Shang-Chi", "", "Standard", "", True, 28),
        ("Standard", "MCU Additional", "Wenwu", "", "Standard", "", True, 30),
        ("Standard", "MCU Additional", "Xu Xialing", "", "Standard", "", True, 25),
        ("Standard", "MCU Additional", "Agatha Harkness (MCU)", "", "Standard", "", True, 28),
        ("Standard", "MCU Additional", "Photon (WandaVision)", "", "Standard", "", True, 25),
        ("Standard", "MCU Additional", "He Who Remains", "", "Standard", "", True, 30),
        ("Standard", "MCU Additional", "Black Knight (Dane Whitman)", "", "Standard", "", True, 25),
        ("Standard", "MCU Additional", "Namor (MCU)", "", "Standard", "", True, 32),

        # ─── Vintage / Toybiz Era Legends (Sought-after older runs) ──
        ("Standard", "Toybiz Era", "Spider-Man (Toybiz Series 1)", "", "Standard", "", False, 85),
        ("Standard", "Toybiz Era", "Iron Man (Toybiz Series 1)", "", "Standard", "", False, 75),
        ("Standard", "Toybiz Era", "Hulk (Toybiz Series 1)", "", "Standard", "", False, 80),
        ("Standard", "Toybiz Era", "Captain America (Toybiz Series 1)", "", "Standard", "", False, 90),
        ("Standard", "Toybiz Era", "Wolverine (Toybiz Series 3)", "", "Standard", "", False, 95),
        ("Standard", "Toybiz Era", "Ghost Rider (Toybiz Series 3)", "", "Standard", "", False, 70),
        ("Standard", "Toybiz Era", "Thor (Toybiz Series 3)", "", "Standard", "", False, 75),
        ("Standard", "Toybiz Era", "Doctor Doom (Toybiz Series 2)", "", "Standard", "", False, 85),
        ("Standard", "Toybiz Era", "Thing (Toybiz Series 2)", "", "Standard", "", False, 80),
        ("Standard", "Toybiz Era", "Namor (Toybiz Series 2)", "", "Standard", "", False, 70),
        ("Standard", "Toybiz Era", "Punisher (Toybiz Series 4)", "", "Standard", "", False, 65),
        ("Standard", "Toybiz Era", "Elektra (Toybiz Series 4)", "", "Standard", "", False, 60),
        ("Standard", "Toybiz Era", "Deadpool (Toybiz Series 6)", "", "Standard", "", False, 120),
        ("Standard", "Toybiz Era", "Cable (Toybiz Series 6)", "", "Standard", "", False, 65),
        ("Standard", "Toybiz Era", "Phoenix (Toybiz Series 6)", "", "Standard", "", False, 70),
        ("Standard", "Toybiz Era", "Juggernaut (Toybiz Series 6)", "", "Standard", "", False, 90),
        ("Standard", "Toybiz Era", "Apocalypse (Toybiz BAF)", "", "Standard", "", False, 150),
        ("Standard", "Toybiz Era", "Sentinel (Toybiz BAF)", "", "Standard", "", False, 180),
        ("Standard", "Toybiz Era", "Galactus (Toybiz BAF)", "", "Standard", "", False, 200),
        ("Standard", "Toybiz Era", "Giant-Man (Toybiz BAF)", "", "Standard", "", False, 120),

        # ─── Recent Waves 2024-2025 (Blob BAF) ──────────────────────
        ("Standard", "X-Men Blob Wave", "Wolverine (Astonishing X-Men)", "Blob", "Standard", "", True, 32),
        ("Standard", "X-Men Blob Wave", "Cyclops (Astonishing X-Men)", "Blob", "Standard", "", True, 30),
        ("Standard", "X-Men Blob Wave", "Emma Frost (Astonishing)", "Blob", "Standard", "", True, 30),
        ("Standard", "X-Men Blob Wave", "Shadowcat (Astonishing)", "Blob", "Standard", "", True, 28),
        ("Standard", "X-Men Blob Wave", "Armor (Hisako Ichiki)", "Blob", "Standard", "", True, 25),
        ("Standard", "X-Men Blob Wave", "Ord", "Blob", "Standard", "", True, 25),
        ("Standard", "X-Men Blob Wave", "Danger", "Blob", "Standard", "", True, 25),

        # ─── Zabu BAF Wave ──────────────────────────────────────────
        ("Standard", "Savage Land", "Ka-Zar", "Zabu", "Standard", "", True, 28),
        ("Standard", "Savage Land", "Shanna the She-Devil", "Zabu", "Standard", "", True, 25),
        ("Standard", "Savage Land", "Savage Wolverine", "Zabu", "Standard", "", True, 32),
        ("Standard", "Savage Land", "Sauron", "Zabu", "Standard", "", True, 30),
        ("Standard", "Savage Land", "Savage Rogue", "Zabu", "Standard", "", True, 30),
        ("Standard", "Savage Land", "High Evolutionary (Comic)", "Zabu", "Standard", "", True, 28),

        # ─── Puff Adder BAF Wave ────────────────────────────────────
        ("Standard", "Serpent Society", "Captain America (Classic Shield)", "Puff Adder", "Standard", "", True, 32),
        ("Standard", "Serpent Society", "Diamondback", "Puff Adder", "Standard", "", True, 28),
        ("Standard", "Serpent Society", "King Cobra", "Puff Adder", "Standard", "", True, 25),
        ("Standard", "Serpent Society", "Bushmaster", "Puff Adder", "Standard", "", True, 25),
        ("Standard", "Serpent Society", "Asp", "Puff Adder", "Standard", "", True, 25),
        ("Standard", "Serpent Society", "Sidewinder", "Puff Adder", "Standard", "", True, 28),

        # ─── Khonshu BAF Wave ───────────────────────────────────────
        ("Standard", "Moon Knight Wave", "Moon Knight (Mr. Knight Suit)", "Khonshu", "Standard", "", True, 35),
        ("Standard", "Moon Knight Wave", "Moon Knight (Fist of Khonshu)", "Khonshu", "Standard", "", True, 32),
        ("Standard", "Moon Knight Wave", "Bushman", "Khonshu", "Standard", "", True, 28),
        ("Standard", "Moon Knight Wave", "Scarlet Scarab", "Khonshu", "Standard", "", True, 25),
        ("Standard", "Moon Knight Wave", "Midnight Man", "Khonshu", "Standard", "", True, 25),

        # ─── Totally Awesome Hulk BAF Wave (Additional) ─────────────
        ("Standard", "The Marvels", "Dar-Benn", "Totally Awesome Hulk", "Standard", "", True, 22),
        ("Standard", "The Marvels", "Goose (Flerken)", "Totally Awesome Hulk", "Standard", "", True, 25),
        ("Standard", "The Marvels", "Binary (Captain Marvel)", "Totally Awesome Hulk", "Standard", "", True, 28),
        ("Standard", "The Marvels", "Prince Yan", "Totally Awesome Hulk", "Standard", "", True, 22),

        # ─── Retro Card (Additional) ────────────────────────────────
        ("Retro", "Retro Spider-Man", "Venom (Retro Card)", "", "Retro Card", "", True, 42),
        ("Retro", "Retro Spider-Man", "Carnage (Retro Card)", "", "Retro Card", "", True, 45),
        ("Retro", "Retro Spider-Man", "Mysterio (Retro Card)", "", "Retro Card", "", True, 35),
        ("Retro", "Retro Spider-Man", "Doctor Octopus (Retro Card)", "", "Retro Card", "", True, 38),
        ("Retro", "Retro Spider-Man", "Kingpin (Retro Card)", "", "Retro Card", "", True, 40),
        ("Retro", "Retro Spider-Man", "Rhino (Retro Card)", "", "Retro Card", "", True, 32),
        ("Retro", "Retro Spider-Man", "Sandman (Retro Card)", "", "Retro Card", "", True, 30),
        ("Retro", "Retro Spider-Man", "Lizard (Retro Card)", "", "Retro Card", "", True, 32),
        ("Retro", "Retro X-Men", "Nightcrawler (Retro X-Men)", "", "Retro Card", "", True, 40),
        ("Retro", "Retro X-Men", "Colossus (Retro X-Men)", "", "Retro Card", "", True, 38),
        ("Retro", "Retro X-Men", "Jubilee (Retro X-Men)", "", "Retro Card", "", True, 32),
        ("Retro", "Retro X-Men", "Cable (Retro X-Men)", "", "Retro Card", "", True, 35),
        ("Retro", "Retro X-Men", "Iceman (Retro X-Men)", "", "Retro Card", "", True, 30),
        ("Retro", "Retro X-Men", "Bishop (Retro X-Men)", "", "Retro Card", "", True, 30),
        ("Retro", "Retro X-Men", "Psylocke (Retro X-Men)", "", "Retro Card", "", True, 38),
        ("Retro", "Retro X-Men", "Apocalypse (Retro X-Men)", "", "Retro Card", "", True, 42),
        ("Retro", "Retro X-Men", "Sabretooth (Retro X-Men)", "", "Retro Card", "", True, 35),
        ("Retro", "Retro X-Men", "Mr. Sinister (Retro X-Men)", "", "Retro Card", "", True, 40),
        ("Retro", "Retro Avengers", "Vision (Retro)", "", "Retro Card", "", True, 32),
        ("Retro", "Retro Avengers", "Wasp (Retro)", "", "Retro Card", "", True, 28),
        ("Retro", "Retro Avengers", "Ant-Man (Retro)", "", "Retro Card", "", True, 28),
        ("Retro", "Retro Avengers", "Falcon (Retro)", "", "Retro Card", "", True, 30),
        ("Retro", "Retro Avengers", "She-Hulk (Retro)", "", "Retro Card", "", True, 30),
        ("Retro", "Retro FF", "Doctor Doom (Retro)", "", "Retro Card", "", True, 42),
        ("Retro", "Retro FF", "Silver Surfer (Retro)", "", "Retro Card", "", True, 38),

        # ─── Exclusive / Fan Channel (Additional) ───────────────────
        ("Fan Channel", "Exclusives", "Dark Phoenix (Pulse Exclusive)", "", "Standard", "Hasbro Pulse", True, 48),
        ("Fan Channel", "Exclusives", "Nimrod (Pulse Exclusive)", "", "Standard", "Hasbro Pulse", True, 45),
        ("Fan Channel", "Exclusives", "Sentinel (Target Exclusive)", "", "Standard", "Target", True, 55),
        ("Fan Channel", "Exclusives", "Old Man Logan (Amazon)", "", "Standard", "Amazon", True, 42),
        ("Fan Channel", "Exclusives", "Emma Frost (Walgreens)", "", "Standard", "Walgreens", True, 40),
        ("Fan Channel", "Exclusives", "Mister Sinister (Walgreens)", "", "Standard", "Walgreens", True, 42),
        ("Fan Channel", "Exclusives", "Daken (Fan Channel)", "", "Standard", "Fan Channel", True, 30),
        ("Fan Channel", "Exclusives", "Multiple Man Army Builder (Amazon)", "", "Standard", "Amazon", True, 55),
        ("Fan Channel", "Exclusives", "Hydra Trooper Army Builder (Amazon)", "", "Standard", "Amazon", True, 48),
        ("Fan Channel", "Exclusives", "AIM Trooper Army Builder (Amazon)", "", "Standard", "Amazon", True, 45),
        ("Fan Channel", "Exclusives", "Hand Ninja Army Builder (Amazon)", "", "Standard", "Amazon", True, 42),
        ("Fan Channel", "Exclusives", "SHIELD Agent Army Builder (Pulse)", "", "Standard", "Hasbro Pulse", True, 38),
        ("Fan Channel", "Exclusives", "Wolverine & Omega Red 2-Pack (Pulse)", "", "Standard", "Hasbro Pulse", True, 58),
        ("Fan Channel", "Exclusives", "Scarlet Witch & Vision 2-Pack (Target)", "", "Standard", "Target", True, 55),
        ("Fan Channel", "Exclusives", "Spider-Man & Venom 2-Pack (Amazon)", "", "Standard", "Amazon", True, 55),
        ("Fan Channel", "Exclusives", "Cyclops & Dark Phoenix 2-Pack (Amazon)", "", "Standard", "Amazon", True, 60),
        ("Fan Channel", "Exclusives", "Iron Man (Modular, Pulse)", "", "Standard", "Hasbro Pulse", True, 42),
        ("Fan Channel", "Exclusives", "Wolverine (Patch, Pulse)", "", "Standard", "Hasbro Pulse", True, 40),
        ("Fan Channel", "Exclusives", "Spider-Man (Ben Reilly, Target)", "", "Standard", "Target", True, 38),
        ("Fan Channel", "Exclusives", "Deadpool (Pirate, Walmart)", "", "Standard", "Walmart", True, 35),
        ("Fan Channel", "Exclusives", "Captain America (Stealth, Walmart)", "", "Standard", "Walmart", True, 35),
        ("Fan Channel", "Exclusives", "Black Panther (Vibranium, Walmart)", "", "Standard", "Walmart", True, 35),
        ("Fan Channel", "Exclusives", "Iron Man (80th Anniversary, Target)", "", "Standard", "Target", True, 48),
        ("Fan Channel", "Exclusives", "Thor (Herald of Galactus, Fan Channel)", "", "Standard", "Fan Channel", True, 35),
        ("Fan Channel", "Exclusives", "Captain America (Ultimate, Fan Channel)", "", "Standard", "Fan Channel", True, 32),
        ("Fan Channel", "Exclusives", "Deadpool (X-Men Costume, Walmart)", "", "Standard", "Walmart", True, 38),
        ("Fan Channel", "Exclusives", "Miles Morales (Into the SV, Target)", "", "Standard", "Target", True, 45),
        ("Fan Channel", "Exclusives", "Wolverine (Tiger Stripe, Target)", "", "Standard", "Target", True, 42),
        ("Fan Channel", "Exclusives", "Punisher (War Journal, Walgreens)", "", "Standard", "Walgreens", True, 38),
        ("Fan Channel", "Exclusives", "Agent Venom (Walgreens)", "", "Standard", "Walgreens", True, 42),

        # ─── Deluxe / Riders (Additional) ───────────────────────────
        ("Deluxe", "Deluxe", "Professor X with Hover Chair (Deluxe)", "", "Deluxe Box", "", True, 55),
        ("Deluxe", "Deluxe", "Hulkbuster (Deluxe)", "", "Deluxe Box", "", True, 65),
        ("Deluxe", "Deluxe", "Thanos (Infinity Gauntlet Deluxe)", "", "Deluxe Box", "", True, 58),
        ("Deluxe", "Deluxe", "Iron Monger (Deluxe)", "", "Deluxe Box", "", True, 52),
        ("Deluxe", "Deluxe", "Rhino (Deluxe)", "", "Deluxe Box", "", True, 48),
        ("Deluxe", "Deluxe", "Juggernaut (Deluxe)", "", "Deluxe Box", "", True, 52),
        ("Deluxe", "Deluxe", "Apocalypse (Deluxe)", "", "Deluxe Box", "", True, 55),
        ("Deluxe", "Deluxe", "Destroyer (Thor, Deluxe)", "", "Deluxe Box", "", True, 48),
        ("Deluxe", "Deluxe", "Skurge (Executioner, Deluxe)", "", "Deluxe Box", "", True, 42),
        ("Deluxe", "Deluxe", "Gladiator Hulk (Deluxe)", "", "Deluxe Box", "", True, 55),
        ("Deluxe", "Rider Series", "Ghost Rider (Johnny Blaze) & Bike", "", "Deluxe Box", "", True, 55),
        ("Deluxe", "Rider Series", "Deadpool & Scooter", "", "Deluxe Box", "", True, 48),
        ("Deluxe", "Rider Series", "Captain America with Motorcycle", "", "Deluxe Box", "", True, 50),
        ("Deluxe", "Rider Series", "Black Panther with Vibranium Bike", "", "Deluxe Box", "", True, 52),
        ("Deluxe", "Deluxe", "Nimrod (Deluxe)", "", "Deluxe Box", "", True, 52),
        ("Deluxe", "Deluxe", "Omega Red (Deluxe)", "", "Deluxe Box", "", True, 48),
        ("Deluxe", "Deluxe", "Mojo (Deluxe)", "", "Deluxe Box", "", True, 55),
        ("Deluxe", "Deluxe", "Sugar Man (Deluxe)", "", "Deluxe Box", "", True, 48),
        ("Deluxe", "Deluxe", "Colossus (Deluxe)", "", "Deluxe Box", "", True, 50),
        ("Deluxe", "Deluxe", "Sabretooth (Deluxe)", "", "Deluxe Box", "", True, 48),

        # ─── Villain Waves ──────────────────────────────────────────
        ("Standard", "Sinister Six", "Doctor Octopus (Sinister Six)", "", "Standard", "", True, 35),
        ("Standard", "Sinister Six", "Vulture (Sinister Six)", "", "Standard", "", True, 30),
        ("Standard", "Sinister Six", "Sandman (Sinister Six)", "", "Standard", "", True, 30),
        ("Standard", "Sinister Six", "Electro (Sinister Six)", "", "Standard", "", True, 28),
        ("Standard", "Sinister Six", "Kraven (Sinister Six)", "", "Standard", "", True, 30),
        ("Standard", "Sinister Six", "Mysterio (Sinister Six)", "", "Standard", "", True, 32),
        ("Standard", "Brotherhood", "Mystique (Brotherhood)", "", "Standard", "", True, 28),
        ("Standard", "Brotherhood", "Sabretooth (Brotherhood)", "", "Standard", "", True, 28),
        ("Standard", "Brotherhood", "Toad", "", "Standard", "", True, 25),
        ("Standard", "Brotherhood", "Pyro (Brotherhood)", "", "Standard", "", True, 25),
        ("Standard", "Brotherhood", "Avalanche", "", "Standard", "", True, 22),
        ("Standard", "Brotherhood", "Blob (Standard)", "", "Standard", "", True, 28),
        ("Standard", "Masters of Evil", "Baron Zemo (Masters)", "", "Standard", "", True, 30),
        ("Standard", "Masters of Evil", "Enchantress (Masters)", "", "Standard", "", True, 28),
        ("Standard", "Masters of Evil", "Executioner (Masters)", "", "Standard", "", True, 28),
        ("Standard", "Masters of Evil", "Wonder Man (Masters Variant)", "", "Standard", "", True, 25),
        ("Standard", "Frightful Four", "Wizard", "", "Standard", "", True, 25),
        ("Standard", "Frightful Four", "Trapster", "", "Standard", "", True, 22),
        ("Standard", "Frightful Four", "Medusa (Frightful Four Variant)", "", "Standard", "", True, 25),
        ("Standard", "Wrecking Crew", "Thunderball", "", "Standard", "", True, 25),
        ("Standard", "Wrecking Crew", "Piledriver", "", "Standard", "", True, 22),
        ("Standard", "Wrecking Crew", "Bulldozer", "", "Standard", "", True, 22),

        # ─── X-Men '97 / Animation (Additional) ────────────────────
        ("Standard", "X-Men '97", "Nightcrawler (X-Men '97)", "Bonebreaker", "Standard", "", True, 30),
        ("Standard", "X-Men '97", "Sunspot (X-Men '97)", "Bonebreaker", "Standard", "", True, 25),
        ("Standard", "X-Men '97", "Cable (X-Men '97)", "Bonebreaker", "Standard", "", True, 32),
        ("Standard", "X-Men '97", "Forge (X-Men '97)", "Bonebreaker", "Standard", "", True, 25),
        ("Standard", "X-Men '97", "Mr. Sinister (X-Men '97)", "Bonebreaker", "Standard", "", True, 38),
        ("Standard", "X-Men '97", "Sentinel (X-Men '97)", "", "Standard", "", True, 42),
        ("Standard", "X-Men '97", "Professor X (X-Men '97)", "", "Standard", "", True, 28),
        ("Standard", "X-Men '97", "Bastion (X-Men '97)", "", "Standard", "", True, 30),
        ("Standard", "X-Men '97", "Madelyne Pryor (X-Men '97)", "", "Standard", "", True, 28),
        ("Standard", "X-Men '97", "Goblin Queen (X-Men '97)", "", "Standard", "", True, 30),
        ("Standard", "What If...?", "Zombie Cap (What If)", "", "Standard", "", True, 28),
        ("Standard", "What If...?", "Zombie Iron Man (What If)", "", "Standard", "", True, 28),
        ("Standard", "What If...?", "Hydra Stomper (What If, Deluxe)", "", "Deluxe Box", "", True, 55),
        ("Standard", "What If...?", "Thanos (What If Gamora)", "", "Standard", "", True, 30),
        ("Standard", "What If...?", "Killmonger (What If)", "", "Standard", "", True, 25),
        ("Standard", "What If...?", "Ultron (Infinity Stones, What If)", "", "Standard", "", True, 35),
        ("Standard", "MCU Animation", "Spider-Man (Freshman Year)", "", "Standard", "", True, 28),
        ("Standard", "MCU Animation", "Norman Osborn (Freshman Year)", "", "Standard", "", True, 25),
        ("Standard", "MCU Animation", "Amadeus Cho (MCU)", "", "Standard", "", True, 22),
        ("Standard", "MCU Animation", "Nico Minoru (MCU)", "", "Standard", "", True, 22),

        # ─── Vintage / Toybiz Era (Additional) ─────────────────────
        ("Standard", "Toybiz Era", "Silver Surfer (Toybiz Series 5)", "", "Standard", "", False, 70),
        ("Standard", "Toybiz Era", "Mr. Fantastic (Toybiz Series 5)", "", "Standard", "", False, 55),
        ("Standard", "Toybiz Era", "Colossus (Toybiz Series 5)", "", "Standard", "", False, 75),
        ("Standard", "Toybiz Era", "Sabretooth (Toybiz Series 6)", "", "Standard", "", False, 60),
        ("Standard", "Toybiz Era", "Wolverine Weapon X (Toybiz Series 6)", "", "Standard", "", False, 65),
        ("Standard", "Toybiz Era", "Magneto (Toybiz Series 3)", "", "Standard", "", False, 70),
        ("Standard", "Toybiz Era", "Storm (Toybiz Series 4)", "", "Standard", "", False, 60),
        ("Standard", "Toybiz Era", "Cyclops (Toybiz Series 10)", "", "Standard", "", False, 55),
        ("Standard", "Toybiz Era", "Thing (Toybiz Fantastic Four)", "", "Standard", "", False, 75),
        ("Standard", "Toybiz Era", "Dr. Strange (Toybiz Series 9)", "", "Standard", "", False, 55),
        ("Standard", "Toybiz Era", "Professor X (Toybiz Series 12)", "", "Standard", "", False, 50),
        ("Standard", "Toybiz Era", "Beast (Toybiz Series 4)", "", "Standard", "", False, 55),
        ("Standard", "Toybiz Era", "Mojo (Toybiz BAF)", "", "Standard", "", False, 110),
        ("Standard", "Toybiz Era", "Onslaught (Toybiz BAF)", "", "Standard", "", False, 140),
        ("Standard", "Toybiz Era", "Modok (Toybiz BAF)", "", "Standard", "", False, 130),

        # ─── Additional Waves & Characters ──────────────────────────
        ("Standard", "Excalibur", "Captain Britain", "", "Standard", "", True, 30),
        ("Standard", "Excalibur", "Meggan", "", "Standard", "", True, 25),
        ("Standard", "Excalibur", "Pete Wisdom", "", "Standard", "", True, 22),
        ("Standard", "X-Force", "Domino", "", "Standard", "", True, 30),
        ("Standard", "X-Force", "Shatterstar", "", "Standard", "", True, 25),
        ("Standard", "X-Force", "Warpath", "", "Standard", "", True, 28),
        ("Standard", "X-Force", "Siryn", "", "Standard", "", True, 22),
        ("Standard", "X-Force", "Rictor", "", "Standard", "", True, 22),
        ("Standard", "X-Force", "Feral", "", "Standard", "", True, 20),
        ("Standard", "Defenders", "Doctor Strange (Defenders)", "", "Standard", "", True, 35),
        ("Standard", "Defenders", "Valkyrie (Defenders)", "", "Standard", "", True, 28),
        ("Standard", "Defenders", "Namor (Defenders)", "", "Standard", "", True, 28),
        ("Standard", "Defenders", "Silver Surfer (Defenders)", "", "Standard", "", True, 32),
        ("Standard", "Defenders", "Hulk (Defenders)", "", "Standard", "", True, 35),
        ("Standard", "Defenders", "Hellcat", "", "Standard", "", True, 22),
        ("Standard", "Thunderbolts Comics", "Mach-I", "", "Standard", "", True, 22),
        ("Standard", "Thunderbolts Comics", "Fixer", "", "Standard", "", True, 20),
        ("Standard", "Thunderbolts Comics", "Jolt", "", "Standard", "", True, 20),
        ("Standard", "Power Pack", "Power Pack 4-Pack Box Set", "", "Deluxe Box", "", True, 85),
        ("Standard", "Spider-Man Classics", "Prowler", "Kingpin", "Standard", "", True, 28),
        ("Standard", "Spider-Man Classics", "Chameleon", "Kingpin", "Standard", "", True, 25),
        ("Standard", "Spider-Man Classics", "Hammerhead", "Kingpin", "Standard", "", True, 25),
        ("Standard", "Spider-Man Classics", "Tombstone", "Kingpin", "Standard", "", True, 28),
        ("Standard", "Spider-Man Classics", "Mister Negative", "Kingpin", "Standard", "", True, 30),

        # ─── Spider-Verse Expansion ───────────────────────────────────
        ("Standard", "Spider-Verse", "Spider-Woman (Jessica Drew)", "Stilt-Man", "Standard", "", True, 35),
        ("Standard", "Spider-Verse", "Madame Web", "Stilt-Man", "Standard", "", True, 30),
        ("Standard", "Spider-Verse", "Superior Spider-Man", "", "Standard", "", True, 42),
        ("Standard", "Spider-Verse", "Ben Reilly Spider-Man", "", "Standard", "", True, 35),
        ("Standard", "Spider-Verse", "Miles Morales (Across the Spider-Verse)", "", "Standard", "", True, 48),
        ("Standard", "Spider-Verse", "Spider-Gwen (Across the Spider-Verse)", "", "Standard", "", True, 45),
        ("Standard", "Spider-Verse", "Spider-Man 2099 (ATSV)", "", "Standard", "", True, 50),
        ("Standard", "Spider-Verse", "Scarlet Spider (Kaine Parker)", "", "Standard", "", True, 32),
        ("Standard", "Spider-Verse", "Spider-Punk (Hobie Brown, ATSV)", "", "Standard", "", True, 45),
        ("Standard", "Spider-Verse", "Spider-Man India", "", "Standard", "", True, 30),
        ("Standard", "Spider-Verse", "Spider-Byte", "", "Standard", "", True, 28),
        ("Standard", "Spider-Verse", "The Spot (Across the Spider-Verse)", "", "Standard", "", True, 38),

        # ─── Avengers Deep Cuts ───────────────────────────────────────
        ("Standard", "Avengers Classic 3", "Crystal (Inhuman)", "", "Standard", "", True, 25),
        ("Standard", "Avengers Classic 3", "Mockingbird", "", "Standard", "", True, 28),
        ("Standard", "Avengers Classic 3", "Jack of Hearts", "", "Standard", "", True, 25),
        ("Standard", "Avengers Classic 3", "Starfox (Eros)", "", "Standard", "", True, 25),
        ("Standard", "Avengers Classic 3", "Jocasta", "", "Standard", "", True, 22),
        ("Standard", "Avengers Classic 3", "Firebird", "", "Standard", "", True, 22),
        ("Standard", "Avengers Classic 3", "Stingray", "", "Standard", "", True, 22),
        ("Standard", "Avengers Classic 3", "Living Lightning", "", "Standard", "", True, 22),
        ("Standard", "Avengers Classic 3", "Two-Gun Kid", "", "Standard", "", True, 20),
        ("Standard", "Avengers Classic 3", "Gilgamesh (Forgotten One)", "", "Standard", "", True, 25),
        ("Standard", "Avengers Classic 3", "Demolition Man (D-Man)", "", "Standard", "", True, 22),
        ("Standard", "Avengers Classic 3", "Machine Man (Aaron Stack)", "", "Standard", "", True, 28),

        # ─── X-Men Deep Cuts ─────────────────────────────────────────
        ("Standard", "X-Men Deep Cuts", "Sage (Tessa)", "", "Standard", "", True, 25),
        ("Standard", "X-Men Deep Cuts", "Karma (Xi'an Coy Manh)", "", "Standard", "", True, 25),
        ("Standard", "X-Men Deep Cuts", "Longshot", "", "Standard", "", True, 28),
        ("Standard", "X-Men Deep Cuts", "Husk (Paige Guthrie)", "", "Standard", "", True, 22),
        ("Standard", "X-Men Deep Cuts", "Chamber (Jonothon Starsmore)", "", "Standard", "", True, 25),
        ("Standard", "X-Men Deep Cuts", "Maggott", "", "Standard", "", True, 22),
        ("Standard", "X-Men Deep Cuts", "Marrow", "", "Standard", "", True, 25),
        ("Standard", "X-Men Deep Cuts", "Cecilia Reyes", "", "Standard", "", True, 22),
        ("Standard", "X-Men Deep Cuts", "Thunderbird (John Proudstar)", "", "Standard", "", True, 28),
        ("Standard", "X-Men Deep Cuts", "Mimic (Calvin Rankin)", "", "Standard", "", True, 25),
        ("Standard", "X-Men Deep Cuts", "Blink (Age of Apocalypse)", "", "Standard", "", True, 30),
        ("Standard", "X-Men Deep Cuts", "Tempo", "", "Standard", "", True, 22),

        # ─── MCU Phase 5-6 ───────────────────────────────────────────
        ("Standard", "MCU Phase 5-6", "Kang Dynasty (Pharaoh Variant)", "", "Standard", "", True, 42),
        ("Standard", "MCU Phase 5-6", "Kang (Council of Kangs, Rama-Tut)", "", "Standard", "", True, 38),
        ("Standard", "MCU Phase 5-6", "Kang (Council of Kangs, Immortus)", "", "Standard", "", True, 38),
        ("Standard", "MCU Phase 5-6", "Echo (Maya Lopez, MCU)", "", "Standard", "", True, 28),
        ("Standard", "MCU Phase 5-6", "Shang-Chi (Ten Rings Armor)", "Mr. Hyde", "Standard", "", True, 32),
        ("Standard", "MCU Phase 5-6", "Xialing (Shang-Chi)", "Mr. Hyde", "Standard", "", True, 25),
        ("Standard", "MCU Phase 5-6", "Death Dealer (Shang-Chi)", "Mr. Hyde", "Standard", "", True, 28),
        ("Standard", "MCU Phase 5-6", "Wenwu (Shang-Chi)", "Mr. Hyde", "Standard", "", True, 30),
        ("Standard", "MCU Phase 5-6", "Ironheart MK 2 (MCU)", "", "Standard", "", True, 30),
        ("Standard", "MCU Phase 5-6", "Namor (Talokan King, Wakanda Forever)", "", "Standard", "", True, 35),

        # ─── HasLab / Premium / Deluxe Expansion ─────────────────────
        ("HasLab", "HasLab", "Doctor Doom (HasLab, Throne)", "", "HasLab Box", "HasLab", True, 400),
        ("Deluxe", "Deluxe", "Sleepwalker (Deluxe)", "", "Deluxe Box", "", True, 42),
        ("Deluxe", "Deluxe", "Darkhawk (Deluxe)", "", "Deluxe Box", "", True, 45),
        ("Deluxe", "Deluxe", "Nova (Rich Rider, Deluxe)", "", "Deluxe Box", "", True, 48),
        ("Deluxe", "Deluxe", "Blue Marvel (Adam Brashear)", "", "Deluxe Box", "", True, 42),
        ("Deluxe", "Deluxe", "Sentry (Void Mode, Deluxe)", "", "Deluxe Box", "", True, 48),
        ("Deluxe", "Deluxe", "Hyperion (Squadron Supreme)", "", "Deluxe Box", "", True, 42),
        ("Deluxe", "Deluxe", "Gladiator (Shi'ar Imperial Guard)", "", "Deluxe Box", "", True, 45),
        ("Deluxe", "Deluxe", "Beta Ray Bill (Deluxe)", "", "Deluxe Box", "", True, 50),
        ("Deluxe", "Deluxe", "Maestro Hulk (Deluxe)", "", "Deluxe Box", "", True, 52),

        # ─── HasLab Exclusives Expansion (+6) ─────────────────────────
        ("HasLab", "HasLab", "Robbie Reyes Ghost Rider (HasLab, Car & Flames)", "", "HasLab Box", "HasLab", True, 450),
        ("HasLab", "HasLab", "Giant-Man (HasLab, 32-Inch)", "", "HasLab Box", "HasLab", True, 500),
        ("HasLab", "HasLab", "Galactus (HasLab) Complete w/ Accessories", "", "HasLab Box", "HasLab", True, 550),
        ("HasLab", "HasLab", "The Sentinel (HasLab, 26-Inch)", "", "HasLab Box", "HasLab", True, 600),
        ("HasLab", "HasLab", "Life-Size Wolverine Helmet (HasLab)", "", "HasLab Box", "HasLab", True, 200),
        ("HasLab", "HasLab", "MODOK (HasLab, Mega Figure)", "", "HasLab Box", "HasLab", True, 350),

        # ─── Fan Channel Exclusives (+10) ─────────────────────────────
        ("Fan Channel", "Fan Channel", "Lady Deathstrike", "", "Standard", "Hasbro Pulse", True, 35),
        ("Fan Channel", "Fan Channel", "Scorpion (Mac Gargan)", "", "Standard", "Amazon", True, 32),
        ("Fan Channel", "Fan Channel", "Justice (Vance Astrovik)", "", "Standard", "Hasbro Pulse", True, 28),
        ("Fan Channel", "Fan Channel", "Speedball (Penance)", "", "Standard", "Hasbro Pulse", True, 28),
        ("Fan Channel", "Fan Channel", "Quasar (Wendell Vaughn)", "", "Standard", "Hasbro Pulse", True, 30),
        ("Fan Channel", "Fan Channel", "Moonstone (Karla Sofen)", "", "Standard", "Amazon", True, 28),
        ("Fan Channel", "Fan Channel", "Dazzler (Classic Disco Outfit)", "", "Standard", "Hasbro Pulse", True, 32),
        ("Fan Channel", "Fan Channel", "Vulture (Classic Green Suit)", "", "Standard", "Target", True, 32),

        # ─── Retro Collection (+10) ──────────────────────────────────
        ("Retro", "Retro Collection", "Retro Spider-Man (Symbiote Black Suit)", "", "Retro Card", "", True, 38),
        ("Retro", "Retro Collection", "Retro Spider-Man (Ben Reilly)", "", "Retro Card", "", True, 35),
        ("Retro", "Retro Collection", "Retro Spider-Man (2099)", "", "Retro Card", "", True, 38),
        ("Retro", "Retro Collection", "Retro Wolverine (Brown Suit)", "", "Retro Card", "", True, 42),
        ("Retro", "Retro Collection", "Retro Storm (Mohawk)", "", "Retro Card", "", True, 45),
        ("Retro", "Retro Collection", "Retro Cyclops (Jim Lee)", "", "Retro Card", "", True, 40),
        ("Retro", "Retro Collection", "Retro Rogue (Jim Lee)", "", "Retro Card", "", True, 55),
        ("Retro", "Retro Collection", "Retro Gambit (Jim Lee)", "", "Retro Card", "", True, 50),
        ("Retro", "Retro Collection", "Retro Jean Grey (Jim Lee)", "", "Retro Card", "", True, 42),
        ("Retro", "Retro Collection", "Retro Daredevil (Classic Red)", "", "Retro Card", "", True, 38),

        # ─── Deluxe Figures Expansion (+8) ────────────────────────────
        ("Deluxe", "Deluxe", "Nimrod (Deluxe, X-Men Villain)", "", "Deluxe Box", "", True, 48),
        ("Deluxe", "Deluxe", "Apocalypse (Deluxe, Classic)", "", "Deluxe Box", "", True, 55),
        ("Deluxe", "Deluxe", "Kingpin (Deluxe, White Suit)", "", "Deluxe Box", "", True, 48),
        ("Deluxe", "Deluxe", "Rhino (Deluxe, Classic)", "", "Deluxe Box", "", True, 50),
        ("Deluxe", "Deluxe", "Hulk (Immortal Hulk, Deluxe)", "", "Deluxe Box", "", True, 52),
        ("Deluxe", "Deluxe", "Thanos (Deluxe, Infinity Gauntlet)", "", "Deluxe Box", "", True, 55),
        ("Deluxe", "Deluxe", "Colossus (Deluxe, X-Men)", "", "Deluxe Box", "", True, 48),
        ("Deluxe", "Deluxe", "Groot (Deluxe, GotG Vol 3)", "", "Deluxe Box", "", True, 45),

        # ─── 2-Packs (+8) ────────────────────────────────────────────
        ("Standard", "2-Packs", "Wolverine & Sabretooth (Rivalry 2-Pack)", "", "Window Box", "", True, 55),
        ("Standard", "2-Packs", "Captain America & Red Skull (Nemesis 2-Pack)", "", "Window Box", "", True, 52),
        ("Standard", "2-Packs", "Spider-Man & Venom (Symbiote Showdown 2-Pack)", "", "Window Box", "", True, 58),
        ("Standard", "2-Packs", "Iron Man & War Machine (Armor Up 2-Pack)", "", "Window Box", "", True, 55),
        ("Standard", "2-Packs", "Storm & Thunderbird (Giant-Size X-Men 2-Pack)", "", "Window Box", "", True, 60),
        ("Standard", "2-Packs", "Daredevil & Elektra (Streets of NYC 2-Pack)", "", "Window Box", "", True, 52),
        ("Standard", "2-Packs", "Black Panther & Killmonger (Wakanda 2-Pack)", "", "Window Box", "", True, 55),
        ("Standard", "2-Packs", "Thor & Loki (Asgardian Brothers 2-Pack)", "", "Window Box", "", True, 58),

        # ─── X-Men '97 Wave Expansion (+8) ───────────────────────────
        ("Standard", "X-Men '97 Wave 2", "Morph (X-Men '97 Wave 2)", "Onslaught", "Standard", "", True, 32),
        ("Standard", "X-Men '97 Wave 2", "Bishop (X-Men '97 Wave 2)", "Onslaught", "Standard", "", True, 35),
        ("Standard", "X-Men '97 Wave 2", "Magneto (X-Men '97 Wave 2 Helmet)", "Onslaught", "Standard", "", True, 38),
        ("Standard", "X-Men '97 Wave 2", "Rogue (X-Men '97 Wave 2 Flight)", "Onslaught", "Standard", "", True, 42),
        ("Standard", "X-Men '97 Wave 2", "Wolverine (X-Men '97 Wave 2 Adamantium)", "Onslaught", "Standard", "", True, 40),
        ("Standard", "X-Men '97 Wave 2", "Jubilee (X-Men '97 Wave 2)", "Onslaught", "Standard", "", True, 30),
        ("Standard", "X-Men '97 Wave 2", "Storm (X-Men '97 Wave 2 Mohawk)", "Onslaught", "Standard", "", True, 38),
        ("Standard", "X-Men '97 Wave 2", "Onslaught BAF Complete (X-Men '97)", "", "Standard", "", True, 90),

        # ─── Spider-Man Renew Your Vows (+6) ─────────────────────────
        ("Standard", "Renew Your Vows", "Spider-Man (Renew Your Vows)", "Stilt-Man Leg", "Standard", "", True, 35),
        ("Standard", "Renew Your Vows", "Spinneret (Mary Jane Watson)", "Stilt-Man Leg", "Standard", "", True, 38),
        ("Standard", "Renew Your Vows", "Spiderling (Annie May Parker)", "Stilt-Man Leg", "Standard", "", True, 32),
        ("Standard", "Renew Your Vows", "Mole Man (Renew Your Vows Wave)", "Stilt-Man Leg", "Standard", "", True, 25),
        ("Standard", "Renew Your Vows", "Regent (Augustus Roman)", "Stilt-Man Leg", "Standard", "", True, 28),
        ("Standard", "Renew Your Vows", "Stilt-Man BAF Complete (Renew Your Vows)", "", "Standard", "", True, 80),

        # ─── Recent MCU Waves (+10) ──────────────────────────────────
        ("Standard", "Thunderbolts* MCU", "Red Guardian (Thunderbolts* MCU)", "Crossbones", "Standard", "", True, 30),
        ("Standard", "Thunderbolts* MCU", "Yelena Belova (Thunderbolts* MCU)", "Crossbones", "Standard", "", True, 32),
        ("Standard", "Thunderbolts* MCU", "Ghost (Thunderbolts* MCU)", "Crossbones", "Standard", "", True, 28),
        ("Standard", "Thunderbolts* MCU", "Taskmaster (Thunderbolts* MCU)", "Crossbones", "Standard", "", True, 30),
        ("Standard", "Thunderbolts* MCU", "Sentry (Thunderbolts* MCU)", "Crossbones", "Standard", "", True, 35),
        ("Standard", "Thunderbolts* MCU", "U.S. Agent (Thunderbolts* MCU)", "Crossbones", "Standard", "", True, 30),
        ("Standard", "Brave New World", "Captain America (Brave New World MCU)", "Leader BAF", "Standard", "", True, 32),
        ("Standard", "Brave New World", "Red Hulk (Brave New World MCU)", "Leader BAF", "Standard", "", True, 38),
        ("Standard", "Brave New World", "Diamondback (Brave New World MCU)", "Leader BAF", "Standard", "", True, 25),
        ("Standard", "Brave New World", "Leader BAF Complete (Brave New World)", "", "Standard", "", True, 75),

        # ─── 20th Anniversary Reissues (+8) ──────────────────────────
        ("20th Anniversary", "20th Anniversary", "Spider-Man (20th Anniversary Retro)", "", "Window Box", "", True, 42),
        ("20th Anniversary", "20th Anniversary", "Wolverine (20th Anniversary Retro)", "", "Window Box", "", True, 45),
        ("20th Anniversary", "20th Anniversary", "Iron Man (20th Anniversary Retro)", "", "Window Box", "", True, 42),
        ("20th Anniversary", "20th Anniversary", "Captain America (20th Anniversary Retro)", "", "Window Box", "", True, 40),
        ("20th Anniversary", "20th Anniversary", "Hulk (20th Anniversary Retro)", "", "Window Box", "", True, 42),
        ("20th Anniversary", "20th Anniversary", "Thor (20th Anniversary Retro)", "", "Window Box", "", True, 40),
        ("20th Anniversary", "20th Anniversary", "Deadpool (20th Anniversary Retro)", "", "Window Box", "", True, 45),
        ("20th Anniversary", "20th Anniversary", "Venom (20th Anniversary Retro)", "", "Window Box", "", True, 48),

        # ─── BAF Complete Sets (+14) ─────────────────────────────────
        ("Standard", "BAF Sets", "Armadillo BAF Complete (NWH Wave)", "", "Standard", "", True, 85),
        ("Standard", "BAF Sets", "Thanos BAF Complete (Endgame Wave)", "", "Standard", "", True, 95),
        ("Standard", "BAF Sets", "Cull Obsidian BAF Complete (IW Wave)", "", "Standard", "", True, 90),
        ("Standard", "BAF Sets", "Kingpin BAF Complete (Spider-Man Wave)", "", "Standard", "", True, 100),
        ("Standard", "BAF Sets", "Dormammu BAF Complete (Doctor Strange Wave)", "", "Standard", "", True, 85),
        ("Standard", "BAF Sets", "Wendigo BAF Complete (Alpha Flight Wave)", "", "Standard", "", True, 80),
        ("Standard", "BAF Sets", "Apocalypse BAF Complete (X-Men Wave)", "", "Standard", "", True, 110),
        ("Standard", "BAF Sets", "Sentinel BAF Complete (X-Men Wave)", "", "Standard", "", True, 120),
        ("Standard", "BAF Sets", "Caliban BAF Complete (X-Force Wave)", "", "Standard", "", True, 75),
        ("Standard", "BAF Sets", "Sugar Man BAF Complete (AoA Wave)", "", "Standard", "", True, 85),
        ("Standard", "BAF Sets", "Super Skrull BAF Complete (Fantastic Four Wave)", "", "Standard", "", True, 90),
        ("Standard", "BAF Sets", "Crimson Dynamo BAF Complete (Iron Man Wave)", "", "Standard", "", True, 80),
        ("Standard", "BAF Sets", "Ultron BAF Complete (Avengers Wave)", "", "Standard", "", True, 95),
        ("Standard", "BAF Sets", "Bonebreaker BAF Complete (X-Men '97 Wave)", "", "Standard", "", True, 88),
    ]

    catalog = []
    for series, wave, name, baf, packaging, exclusive, sealed, price in items:
        catalog.append({
            "series": series,
            "wave": wave,
            "name": name,
            "baf_figure": baf,
            "packaging_type": packaging,
            "retailer_exclusive": exclusive,
            "sealed": sealed,
            "price_eur": price,
        })

    # Add variant items (chase, exclusive, repackage, deluxe, archive, head-sculpt variants)
    variants = _variant_expansion()
    existing_names = {item["name"] for item in catalog}
    for v in variants:
        if v["name"] not in existing_names:
            catalog.append(v)
    # Deduplicate by ('name',) (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = item["name"]
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


def item_to_catalog_item(item: dict) -> CatalogItem:
    name = item["name"]
    series = item["series"]
    wave = item["wave"]
    baf = item["baf_figure"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{series}-{name}"),
        title=name,
        set_code=slugify(wave) if wave else "",
        brand="Hasbro",
        rarity="High" if series == "HasLab" else "Mid" if item["retailer_exclusive"] else "Standard",
        notes=f"{series} | {wave} | BAF: {baf}" if baf else f"{series} | {wave}",
        attributes_json={
            "franchise": "Marvel",
            "series": series,
            "wave": wave,
            "baf_figure": baf,
            "packaging_type": item["packaging_type"],
            "retailer_exclusive": item["retailer_exclusive"],
            "sealed": item["sealed"],
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    series = item["series"]
    price = item["price_eur"]

    series_scores = {
        "Standard": 0.4,
        "Retro": 0.5,
        "20th Anniversary": 0.55,
        "Deluxe": 0.6,
        "Fan Channel": 0.5,
        "HasLab": 0.9,
    }

    exclusive_bonus = 0.1 if item["retailer_exclusive"] else 0.0
    sealed_bonus = 0.1 if item["sealed"] else 0.0

    return PriceObservation(
        features={
            "condition_score": 0.85 if item["sealed"] else 0.7,
            "rarity_score": series_scores.get(series, 0.4) + exclusive_bonus,
            "edition_score": 0.5 + sealed_bonus,
        },
        price=price,
    )


def main():
    parser = argparse.ArgumentParser(description="Import Marvel Legends catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Marvel Legends Import ===")

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

    logger.info(f"\n=== Marvel Legends Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
