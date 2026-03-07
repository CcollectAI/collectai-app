"""
Import Artisan Keycaps & Keycap Sets catalog.

Layer 1 (Catalog):  Curated artisan keycaps + group buy sets → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers 600+ items across:
- Artisan makers: Jelly Key, Dwarf Factory, CYSM, Artkey, Latrialum,
  Bro Caps, GAF, ETF (Nightcaps), Alpha Keycaps, GSK, Hot Keys Project,
  Deag (Death Caps), Systematik Kaps, Lividity, Sludgekidd, Glyco Keycaps,
  Rathcaps, Phage Caps, T-Lab Faunacaps, Bowbie Keycaps
- GMK sets: Olivia, Laser, Botanical, Mizu, Bento, Dracula, Darling,
  Demon Sword, Frost Witch, Hennessey, Red Samurai, Dots, WoB, BoW, etc.
- SA profile sets: Bliss, Dreameater, Godspeed, Mizu
- KAT profile sets: Milkshake, Atlantis, Refined, Arctic
- ePBT sets: Kavala, Origami, Grand Tour, Less But Better
- Cherry Original sets: Hyperion, Sagittarius, Leviathan
- Full custom keyboard builds (reference items)

Usage:
    python -m pipelines.import_keycaps [--dry-run]
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

CATEGORY = "keycaps"


def get_curated_catalog() -> list[dict]:
    """Curated keycap catalog (600+ items) covering artisan makers, GMK/SA/KAT/ePBT/Cherry/DSA
    sets, premium grail caps, switches, deskmats, cables, stabilizers, plates,
    and full custom keyboard builds as reference items."""

    # (maker, keycap_type, name, profile, rarity_tier, price_eur)
    # rarity_tier: grail (>400), high (200-400), mid (80-200), standard (<80)

    caps = [
        # ── Jelly Key ──────────────────────────────────────────────────
        ("Jelly Key", "Artisan", "Zen Pond III Cherry Blossom", "SA R1", "mid", 85),
        ("Jelly Key", "Artisan", "Zen Pond III Ochiba", "SA R1", "mid", 90),
        ("Jelly Key", "Artisan", "Zen Pond III Ghost Asagi", "SA R1", "mid", 95),
        ("Jelly Key", "Artisan", "Arcade Cabinet Retro TV", "SA R1", "mid", 95),
        ("Jelly Key", "Artisan", "Arcade Cabinet 8-Bit Nostalgia", "SA R1", "mid", 90),
        ("Jelly Key", "Artisan", "Born of Forest Series Aspen", "SA R1", "mid", 80),
        ("Jelly Key", "Artisan", "Born of Forest Series Birch", "SA R1", "mid", 85),
        ("Jelly Key", "Artisan", "Dragon of Eden Keycap", "SA R1", "mid", 100),
        ("Jelly Key", "Artisan", "Ethereal Reign Trident", "SA R1", "mid", 120),

        # ── Dwarf Factory ──────────────────────────────────────────────
        ("Dwarf Factory", "Artisan", "Gnarly Drakon Obsidian", "Cherry R1", "mid", 65),
        ("Dwarf Factory", "Artisan", "Gnarly Drakon Jade", "Cherry R1", "mid", 70),
        ("Dwarf Factory", "Artisan", "Gnarly Drakon Inferno", "Cherry R1", "mid", 70),
        ("Dwarf Factory", "Artisan", "The Flourish Sakura", "Cherry R1", "standard", 55),
        ("Dwarf Factory", "Artisan", "The Flourish Wisteria", "Cherry R1", "standard", 55),
        ("Dwarf Factory", "Artisan", "Terrarium Keycap Ocean", "Cherry R1", "mid", 75),
        ("Dwarf Factory", "Artisan", "Terrarium Keycap Autumn", "Cherry R1", "mid", 75),
        ("Dwarf Factory", "Artisan", "Moondust Nebula", "Cherry R1", "mid", 80),

        # ── CYSM ──────────────────────────────────────────────────────
        ("CYSM", "Artisan", "Keyby Classic Blue", "Cherry R4", "mid", 90),
        ("CYSM", "Artisan", "Keyby Mermaid", "Cherry R4", "mid", 100),
        ("CYSM", "Artisan", "Keyby Aurora", "Cherry R4", "mid", 140),
        ("CYSM", "Artisan", "Ice Dragon Frost", "Cherry R4", "mid", 110),
        ("CYSM", "Artisan", "Ice Dragon Ember", "Cherry R4", "mid", 115),
        ("CYSM", "Artisan", "Boba Classic Milk Tea", "Cherry R4", "mid", 85),
        ("CYSM", "Artisan", "Boba Taro", "Cherry R4", "mid", 90),
        ("CYSM", "Artisan", "Boo Ice Cream", "Cherry R4", "mid", 85),

        # ── Artkey ─────────────────────────────────────────────────────
        ("Artkey", "Artisan", "Sirius Celestial White", "Cherry R4", "high", 200),
        ("Artkey", "Artisan", "Sirius Nebula Purple", "Cherry R4", "high", 220),
        ("Artkey", "Artisan", "Bull V2 Crimson", "Cherry R4", "high", 250),
        ("Artkey", "Artisan", "Bull V2 Jade", "Cherry R4", "high", 240),
        ("Artkey", "Artisan", "Exmoor Dusk", "Cherry R4", "mid", 160),
        ("Artkey", "Artisan", "Exmoor Dawn", "Cherry R4", "mid", 150),
        ("Artkey", "Artisan", "Sirius Bull V2 Obsidian", "Cherry R4", "high", 260),
        ("Artkey", "Artisan", "Exmor Voidwalker", "Cherry R4", "high", 210),
        ("Artkey", "Artisan", "Exmor Leviathan", "Cherry R4", "high", 230),
        ("Artkey", "Artisan", "Exmor Eon", "Cherry R4", "high", 200),
        ("Artkey", "Artisan", "Skelekrew Bone White", "Cherry R4", "mid", 180),

        # ── Latrialum ─────────────────────────────────────────────────
        ("Latrialum", "Artisan", "Royal Eternal Flame ESC", "Cherry R4", "high", 180),
        ("Latrialum", "Artisan", "Royal Celestial ESC", "Cherry R4", "high", 200),
        ("Latrialum", "Artisan", "Seraphic Bloom ESC", "Cherry R4", "high", 200),
        ("Latrialum", "Artisan", "Imperial Astral WASD Set", "Cherry R4", "high", 350),
        ("Latrialum", "Artisan", "Frostfire ESC + Fn Set", "Cherry R4", "high", 280),
        ("Latrialum", "Artisan", "GMK Olivia Collab ESC", "Cherry R4", "high", 300),
        ("Latrialum", "Artisan", "GMK Botanical Collab ESC", "Cherry R4", "high", 280),

        # ── Bro Caps ──────────────────────────────────────────────────
        ("Bro Caps", "Artisan", "Reaper V1 OG Colorway", "Cherry R1", "grail", 900),
        ("Bro Caps", "Artisan", "Reaper V1 Bloodlust", "Cherry R1", "grail", 750),
        ("Bro Caps", "Artisan", "Broshido Bushido Red", "Cherry R1", "grail", 600),
        ("Bro Caps", "Artisan", "Broshido Ronin", "Cherry R1", "grail", 550),
        ("Bro Caps", "Artisan", "Last Pilot Midnight", "Cherry R1", "high", 400),
        ("Bro Caps", "Artisan", "Last Pilot Eva Unit-01", "Cherry R1", "grail", 450),
        ("Bro Caps", "Artisan", "Brobot V2 Corrupted Defender", "Cherry R1", "grail", 700),
        ("Bro Caps", "Artisan", "Brobot V2 Patriot", "Cherry R1", "grail", 600),

        # ── GAF (Grimey as Fuck) ───────────────────────────────────────
        ("GAF (Grimey as Fuck)", "Artisan", "Trash Panda OG Colorway", "Cherry R4", "grail", 800),
        ("GAF (Grimey as Fuck)", "Artisan", "Trash Panda Garnet", "Cherry R4", "grail", 650),
        ("GAF (Grimey as Fuck)", "Artisan", "Trash Panda V2 Spectral", "Cherry R4", "grail", 700),
        ("GAF (Grimey as Fuck)", "Artisan", "Grimace V2 Hyperfuse", "Cherry R4", "grail", 900),
        ("GAF (Grimey as Fuck)", "Artisan", "Grimace V2 Phosphene", "Cherry R4", "grail", 850),

        # ── ETF (Nightcaps) ────────────────────────────────────────────
        ("ETF (Nightcaps)", "Artisan", "Fugthulhu Vaporwave III", "Cherry R1", "grail", 500),
        ("ETF (Nightcaps)", "Artisan", "Fugthulhu Noface", "Cherry R1", "grail", 550),
        ("ETF (Nightcaps)", "Artisan", "Smegface Galactic Raspberry", "Cherry R1", "grail", 450),
        ("ETF (Nightcaps)", "Artisan", "Smegface Shadowfyre", "Cherry R1", "grail", 420),
        ("ETF (Nightcaps)", "Artisan", "Dental Plan Minty Fresh", "Cherry R1", "high", 350),
        ("ETF (Nightcaps)", "Artisan", "Dental Plan Nightshade", "Cherry R1", "high", 380),

        # ── Alpha Keycaps ──────────────────────────────────────────────
        ("Alpha Keycaps", "Artisan", "Keypora Lunar Eclipse", "Cherry R1", "high", 300),
        ("Alpha Keycaps", "Artisan", "Keypora Solar Flare", "Cherry R1", "high", 280),
        ("Alpha Keycaps", "Artisan", "Salvador Galaxy", "Cherry R1", "high", 250),
        ("Alpha Keycaps", "Artisan", "Salvador Deep Sea", "Cherry R1", "high", 240),
        ("Alpha Keycaps", "Artisan", "Mr.Ed Cosmic Trot", "Cherry R1", "high", 200),
        ("Alpha Keycaps", "Artisan", "Mr.Ed Sakura Gallop", "Cherry R1", "mid", 180),

        # ── GSK (Goldenstar Keycaps) ───────────────────────────────────
        ("GSK", "Artisan", "Hogzilla Verdant", "Cherry R1", "mid", 120),
        ("GSK", "Artisan", "Hogzilla Infernal", "Cherry R1", "mid", 130),
        ("GSK", "Artisan", "Froggo Lily Pad", "Cherry R1", "mid", 100),
        ("GSK", "Artisan", "Froggo Toxic", "Cherry R1", "mid", 110),
        ("GSK", "Artisan", "Velites Nebula", "Cherry R1", "mid", 140),
        ("GSK", "Artisan", "Hogzilla Fire", "Cherry R1", "mid", 135),
        ("GSK", "Artisan", "Mandrill Aurora", "Cherry R1", "mid", 125),
        ("GSK", "Artisan", "Leo Sakura", "Cherry R1", "mid", 115),

        # ── Hot Keys Project (HKP) ────────────────────────────────────
        ("Hot Keys Project", "Artisan", "Specter Toxic", "Cherry R1", "mid", 90),
        ("Hot Keys Project", "Artisan", "Raven Obsidian", "Cherry R1", "mid", 85),
        ("Hot Keys Project", "Artisan", "Berserker Blood", "Cherry R1", "mid", 95),

        # ── Deag (Death Caps) ─────────────────────────────────────────
        ("Deag (Death Caps)", "Artisan", "Revenant Cross", "Cherry R1", "high", 220),
        ("Deag (Death Caps)", "Artisan", "Bad Luck Opal", "Cherry R1", "high", 200),
        ("Deag (Death Caps)", "Artisan", "Koshka Spirit", "Cherry R1", "high", 210),

        # ── More Premium Artisans ─────────────────────────────────────
        ("Systematik Kaps", "Artisan", "Cheshire Wonderland", "Cherry R1", "mid", 130),
        ("Lividity", "Artisan", "Observer Toxic", "Cherry R1", "mid", 110),
        ("Sludgekidd", "Artisan", "Fingychomp OG", "Cherry R1", "mid", 120),
        ("Glyco Keycaps", "Artisan", "Glob Neon Drip", "Cherry R1", "mid", 100),
        ("Rathcaps", "Artisan", "Keyriboh Pharaoh", "Cherry R1", "mid", 95),
        ("Phage Caps", "Artisan", "Clavus Bloodstone", "Cherry R1", "mid", 105),
        ("T-Lab Faunacaps", "Artisan", "Tiger Siberian", "Cherry R1", "mid", 115),
        ("Bowbie Keycaps", "Artisan", "Keebo Pastel Dream", "Cherry R1", "mid", 90),

        # ── GMK Keycap Sets ────────────────────────────────────────────
        ("GMK", "Keycap Set", "GMK Olivia++ Dark Base Kit", "Cherry", "high", 280),
        ("GMK", "Keycap Set", "GMK Olivia++ Light Base Kit", "Cherry", "high", 250),
        ("GMK", "Keycap Set", "GMK Laser Cyberdeck Base", "Cherry", "high", 220),
        ("GMK", "Keycap Set", "GMK Botanical Base Kit", "Cherry", "high", 260),
        ("GMK", "Keycap Set", "GMK Botanical R2 Base Kit", "Cherry", "mid", 180),
        ("GMK", "Keycap Set", "GMK 8008 Base Kit", "Cherry", "high", 300),
        ("GMK", "Keycap Set", "GMK Bento Base Kit", "Cherry", "high", 240),
        ("GMK", "Keycap Set", "GMK Dracula Base Kit", "Cherry", "mid", 200),
        ("GMK", "Keycap Set", "GMK Darling Base Kit", "Cherry", "high", 350),
        ("GMK", "Keycap Set", "GMK Cafe Base Kit", "Cherry", "mid", 190),
        ("GMK", "Keycap Set", "GMK Mizu Base Kit", "Cherry", "high", 320),
        ("GMK", "Keycap Set", "GMK Oblivion V2 Base Kit", "Cherry", "mid", 180),
        ("GMK", "Keycap Set", "GMK Taro R2 Base Kit", "Cherry", "mid", 160),
        ("GMK", "Keycap Set", "GMK Nautilus R2 Base Kit", "Cherry", "mid", 150),
        ("GMK", "Keycap Set", "GMK Modo Light Base Kit", "Cherry", "mid", 140),
        ("GMK", "Keycap Set", "GMK Demon Sword Base Kit", "Cherry", "high", 290),
        ("GMK", "Keycap Set", "GMK Frost Witch Base Kit", "Cherry", "high", 380),
        ("GMK", "Keycap Set", "GMK Hennessey Base Kit", "Cherry", "mid", 170),
        ("GMK", "Keycap Set", "GMK Red Samurai Base Kit", "Cherry", "high", 210),
        ("GMK", "Keycap Set", "GMK Dots Base Kit", "Cherry", "high", 240),
        ("GMK", "Keycap Set", "GMK WoB (White on Black) Base Kit", "Cherry", "mid", 120),
        ("GMK", "Keycap Set", "GMK BoW (Black on White) Base Kit", "Cherry", "mid", 110),

        # ── SA Profile Sets ────────────────────────────────────────────
        ("Signature Plastics", "Keycap Set", "SA Bliss Base Kit", "SA", "mid", 160),
        ("Signature Plastics", "Keycap Set", "SA Dreameater Base Kit", "SA", "mid", 140),
        ("Signature Plastics", "Keycap Set", "SA Godspeed Base Kit", "SA", "mid", 180),
        ("Signature Plastics", "Keycap Set", "SA Mizu Base Kit", "SA", "high", 200),

        # ── KAT Profile Sets ──────────────────────────────────────────
        ("Keyreative", "Keycap Set", "KAT Milkshake Alpha Kit", "KAT", "mid", 120),
        ("Keyreative", "Keycap Set", "KAT Atlantis Alpha Kit", "KAT", "mid", 100),
        ("Keyreative", "Keycap Set", "KAT Refined Alpha Kit", "KAT", "standard", 80),
        ("Keyreative", "Keycap Set", "KAT Arctic Alpha Kit", "KAT", "mid", 110),

        # ── ePBT Sets ─────────────────────────────────────────────────
        ("ePBT", "Keycap Set", "ePBT Kavala Base Kit", "Cherry", "mid", 100),
        ("ePBT", "Keycap Set", "ePBT Origami Base Kit", "Cherry", "mid", 90),
        ("ePBT", "Keycap Set", "ePBT Grand Tour Base Kit", "Cherry", "mid", 110),
        ("ePBT", "Keycap Set", "ePBT Less But Better Base Kit", "Cherry", "mid", 95),

        # ── Cherry Original Sets ──────────────────────────────────────
        ("Cherry", "Keycap Set", "Cherry Original Hyperion Base Kit", "Cherry", "mid", 130),
        ("Cherry", "Keycap Set", "Cherry Original Sagittarius Base Kit", "Cherry", "mid", 120),
        ("Cherry", "Keycap Set", "Cherry Original Leviathan Base Kit", "Cherry", "mid", 140),

        # ── Additional Premium Artisans ─────────────────────────────────
        ("Melonkeys", "Artisan", "Suika Watermelon", "Cherry R1", "mid", 100),
        ("Melonkeys", "Artisan", "Kamikaze Shogun", "Cherry R1", "mid", 120),
        ("Destroyed Caps", "Artisan", "Krakken Deep Ocean", "Cherry R1", "mid", 110),
        ("Binirias", "Artisan", "Mume Sakura Bloom", "Cherry R1", "mid", 95),
        ("Binirias", "Artisan", "Mume Aurora Borealis", "Cherry R1", "mid", 105),
        ("Keycraft", "Artisan", "Sphynx Obsidian", "Cherry R1", "high", 200),

        # ── Additional GMK Sets ──────────────────────────────────────────
        ("GMK", "Keycap Set", "GMK Striker Base Kit", "Cherry", "high", 230),
        ("GMK", "Keycap Set", "GMK Hammerhead Base Kit", "Cherry", "mid", 190),
        ("GMK", "Keycap Set", "GMK Rudy Base Kit", "Cherry", "mid", 170),
        ("GMK", "Keycap Set", "GMK Hallyu Base Kit", "Cherry", "mid", 180),

        # ── Full Custom Keyboard Builds (reference items) ──────────────
        ("Keycult", "Keyboard Build", "Keycult No. 2/65 Full Build", "N/A", "grail", 2800),
        ("TGR", "Keyboard Build", "TGR Jane V2 CE Full Build", "N/A", "grail", 3500),
        ("ai03", "Keyboard Build", "ai03 Vega Full Build", "N/A", "high", 380),
        ("Mode", "Keyboard Build", "Mode Eighty Full Build", "N/A", "high", 350),
        ("Monokei", "Keyboard Build", "Monokei Kara Full Build", "N/A", "mid", 200),
        ("Owlab", "Keyboard Build", "Owlab Spring Full Build", "N/A", "high", 400),

        # ── Jelly Key — Additional ────────────────────────────────────────
        ("Jelly Key", "Artisan", "Mid-Autumn Rabbit Lantern", "SA R1", "mid", 95),
        ("Jelly Key", "Artisan", "Zen Pond III Renraku", "SA R1", "mid", 90),
        ("Jelly Key", "Artisan", "The Abyss Kraken Deep", "SA R1", "mid", 110),
        ("Jelly Key", "Artisan", "Shangri-La Lost City", "SA R1", "mid", 100),

        # ── Dwarf Factory — Additional ────────────────────────────────────
        ("Dwarf Factory", "Artisan", "Anura Poison Dart", "Cherry R1", "mid", 70),
        ("Dwarf Factory", "Artisan", "Foodie Sushi", "Cherry R1", "standard", 55),
        ("Dwarf Factory", "Artisan", "Mystic Dragon Frost", "Cherry R1", "mid", 80),

        # ── CYSM — Additional ────────────────────────────────────────────
        ("CYSM", "Artisan", "Keyby Sakura Storm", "Cherry R4", "mid", 120),
        ("CYSM", "Artisan", "Boba Matcha", "Cherry R4", "mid", 85),
        ("CYSM", "Artisan", "Ice Dragon Tempest", "Cherry R4", "mid", 125),

        # ── Artkey — Additional ───────────────────────────────────────────
        ("Artkey", "Artisan", "Sirius Carbon Black", "Cherry R4", "high", 210),
        ("Artkey", "Artisan", "Bull V2 Phantom", "Cherry R4", "high", 255),
        ("Artkey", "Artisan", "Skelekrew Patina", "Cherry R4", "mid", 190),

        # ── Latrialum — Additional ────────────────────────────────────────
        ("Latrialum", "Artisan", "Ethereal Glacier ESC", "Cherry R4", "high", 220),
        ("Latrialum", "Artisan", "Seraphic Twilight ESC", "Cherry R4", "high", 210),

        # ── Bro Caps — Additional ────────────────────────────────────────
        ("Bro Caps", "Artisan", "Reaper V2 Nightfall", "Cherry R1", "grail", 650),
        ("Bro Caps", "Artisan", "Last Pilot Ultraviolet", "Cherry R1", "grail", 480),

        # ── GAF — Additional ─────────────────────────────────────────────
        ("GAF (Grimey as Fuck)", "Artisan", "Trash Panda V2 Venom", "Cherry R4", "grail", 720),
        ("GAF (Grimey as Fuck)", "Artisan", "Grimace V2 Frost Bite", "Cherry R4", "grail", 800),

        # ── ETF — Additional ─────────────────────────────────────────────
        ("ETF (Nightcaps)", "Artisan", "Fugthulhu Dreamboat", "Cherry R1", "grail", 520),
        ("ETF (Nightcaps)", "Artisan", "Smegface Starfield", "Cherry R1", "grail", 460),

        # ── Alpha Keycaps — Additional ───────────────────────────────────
        ("Alpha Keycaps", "Artisan", "Keypora Nebula Storm", "Cherry R1", "high", 290),
        ("Alpha Keycaps", "Artisan", "Salvador Magma", "Cherry R1", "high", 260),

        # ── GSK — Additional ─────────────────────────────────────────────
        ("GSK", "Artisan", "Hogzilla Emerald", "Cherry R1", "mid", 125),
        ("GSK", "Artisan", "Froggo Crimson", "Cherry R1", "mid", 105),
        ("GSK", "Artisan", "Mandrill Obsidian", "Cherry R1", "mid", 130),

        # ── Additional Premium Artisans ──────────────────────────────────
        ("Destroyer Caps", "Artisan", "Grinix Void", "Cherry R1", "mid", 100),
        ("Systematik Kaps", "Artisan", "Au Revoir Stardust", "Cherry R1", "mid", 125),
        ("Lividity", "Artisan", "Observer Phantom", "Cherry R1", "mid", 115),
        ("Sludgekidd", "Artisan", "Fingychomp Lava", "Cherry R1", "mid", 130),
        ("Glyco Keycaps", "Artisan", "Glob Sunset", "Cherry R1", "mid", 105),
        ("Rathcaps", "Artisan", "Keyriboh Emerald", "Cherry R1", "mid", 100),
        ("Phage Caps", "Artisan", "Clavus Amethyst", "Cherry R1", "mid", 110),
        ("T-Lab Faunacaps", "Artisan", "Tiger Bengal", "Cherry R1", "mid", 120),
        ("Bowbie Keycaps", "Artisan", "Keebo Midnight", "Cherry R1", "mid", 95),
        ("Salvun", "Artisan", "Salvun x GMK Nautilus Copper", "Cherry R1", "high", 200),

        # ── GMK Keycap Sets — Additional ──────────────────────────────────
        ("GMK", "Keycap Set", "GMK Ishtar Base Kit", "Cherry", "high", 240),
        ("GMK", "Keycap Set", "GMK Dualshot Base Kit", "Cherry", "mid", 180),
        ("GMK", "Keycap Set", "GMK Yuru Base Kit", "Cherry", "mid", 170),
        ("GMK", "Keycap Set", "GMK Retrowave Base Kit", "Cherry", "mid", 160),
        ("GMK", "Keycap Set", "GMK Norse Base Kit", "Cherry", "mid", 165),
        ("GMK", "Keycap Set", "GMK Apollo Base Kit", "Cherry", "mid", 175),
        ("GMK", "Keycap Set", "GMK Peaches n Cream Base Kit", "Cherry", "mid", 190),
        ("GMK", "Keycap Set", "GMK Night Runner Base Kit", "Cherry", "high", 210),
        ("GMK", "Keycap Set", "GMK Spirit Base Kit", "Cherry", "mid", 155),
        ("GMK", "Keycap Set", "GMK Kaiju Base Kit", "Cherry", "mid", 180),
        ("GMK", "Keycap Set", "GMK Rainy Day Base Kit", "Cherry", "mid", 145),
        ("GMK", "Keycap Set", "GMK Posh Base Kit", "Cherry", "mid", 170),

        # ── SA Profile Sets — Additional ──────────────────────────────────
        ("Signature Plastics", "Keycap Set", "SA Leviathan Base Kit", "SA", "mid", 170),
        ("Signature Plastics", "Keycap Set", "SA Oblivion Base Kit", "SA", "mid", 150),
        ("Signature Plastics", "Keycap Set", "SA Carbon Base Kit", "SA", "mid", 160),

        # ── KAT Profile Sets — Additional ────────────────────────────────
        ("Keyreative", "Keycap Set", "KAT Cyberspace Alpha Kit", "KAT", "mid", 100),
        ("Keyreative", "Keycap Set", "KAT Lucky Jade Alpha Kit", "KAT", "mid", 110),

        # ── ePBT Sets — Additional ───────────────────────────────────────
        ("ePBT", "Keycap Set", "ePBT Kuro Shiro Base Kit", "Cherry", "mid", 110),
        ("ePBT", "Keycap Set", "ePBT Extended 2048 Base Kit", "Cherry", "mid", 100),

        # ── Additional Keyboard Builds ────────────────────────────────────
        ("Singa", "Keyboard Build", "Singa Unikorn R2.1 Full Build", "N/A", "high", 380),
        ("Geon", "Keyboard Build", "Geon Frog F2 Full Build", "N/A", "mid", 200),
        ("CannonKeys", "Keyboard Build", "CannonKeys Devastating TKL Full Build", "N/A", "high", 350),
        ("Haus", "Keyboard Build", "Haus Haus Full Build", "N/A", "grail", 1200),
        ("Smith + Rune", "Keyboard Build", "Iron180 Full Build", "N/A", "grail", 2200),

        # ── S-Craft Studio ──────────────────────────────────────────────
        ("S-Craft", "Artisan", "Pokemon Gengar SA R1", "SA R1", "high", 200),
        ("S-Craft", "Artisan", "Pokemon Pikachu SA R1", "SA R1", "high", 180),
        ("S-Craft", "Artisan", "Pokemon Bulbasaur SA R1", "SA R1", "high", 170),
        ("S-Craft", "Artisan", "Pokemon Charmander SA R1", "SA R1", "high", 175),
        ("S-Craft", "Artisan", "Pokemon Squirtle SA R1", "SA R1", "high", 170),
        ("S-Craft", "Artisan", "Pokemon Eevee SA R1", "SA R1", "high", 165),
        ("S-Craft", "Artisan", "Pokemon Jigglypuff SA R1", "SA R1", "high", 160),
        ("S-Craft", "Artisan", "Pokemon Snorlax SA R1", "SA R1", "high", 190),

        # ── GMK Popular Colorways (expanded) ─────────────────────────────
        ("GMK", "Keycap Set", "GMK Voyage Base Kit", "Cherry", "mid", 170),
        ("GMK", "Keycap Set", "GMK Minimal R2 Base Kit", "Cherry", "mid", 130),
        ("GMK", "Keycap Set", "GMK Grand Prix Base Kit", "Cherry", "mid", 165),
        ("GMK", "Keycap Set", "GMK Mecha-01 Base Kit", "Cherry", "mid", 180),
        ("GMK", "Keycap Set", "GMK Lux Base Kit", "Cherry", "mid", 155),
        ("GMK", "Keycap Set", "GMK Birch Base Kit", "Cherry", "mid", 145),
        ("GMK", "Keycap Set", "GMK Thai Tea Base Kit", "Cherry", "mid", 160),
        ("GMK", "Keycap Set", "GMK Avanguardia Base Kit", "Cherry", "mid", 175),
        ("GMK", "Keycap Set", "GMK Pharaoh Base Kit", "Cherry", "high", 250),
        ("GMK", "Keycap Set", "GMK Shanshui Base Kit", "Cherry", "mid", 185),
        ("GMK", "Keycap Set", "GMK Bushido Base Kit", "Cherry", "mid", 175),
        ("GMK", "Keycap Set", "GMK Terra Base Kit", "Cherry", "mid", 160),
        ("GMK", "Keycap Set", "GMK Serenity Base Kit", "Cherry", "mid", 150),
        ("GMK", "Keycap Set", "GMK Cream Cheese and Green Onion Base Kit", "Cherry", "mid", 140),
        ("GMK", "Keycap Set", "GMK Willow Base Kit", "Cherry", "mid", 145),
        ("GMK", "Keycap Set", "GMK Eclipse Base Kit", "Cherry", "mid", 185),
        ("GMK", "Keycap Set", "GMK Dolch Base Kit", "Cherry", "mid", 150),
        ("GMK", "Keycap Set", "GMK Space Cadet Base Kit", "Cherry", "high", 280),
        ("GMK", "Keycap Set", "GMK Toxic Base Kit", "Cherry", "mid", 175),
        ("GMK", "Keycap Set", "GMK Evil Dolch Base Kit", "Cherry", "mid", 160),

        # ── Jelly Key — More Sculpts ─────────────────────────────────────
        ("Jelly Key", "Artisan", "Great Wave Kanagawa", "SA R1", "mid", 105),
        ("Jelly Key", "Artisan", "Eternal Lighthouse Beacon", "SA R1", "mid", 100),
        ("Jelly Key", "Artisan", "Constellation Series Orion", "SA R1", "mid", 95),
        ("Jelly Key", "Artisan", "Nature's Rage Volcano", "SA R1", "mid", 110),

        # ── CYSM — More Sculpts ──────────────────────────────────────────
        ("CYSM", "Artisan", "Keyby Coral Reef", "Cherry R4", "mid", 110),
        ("CYSM", "Artisan", "Boba Honeydew", "Cherry R4", "mid", 85),
        ("CYSM", "Artisan", "Noic Classic White", "Cherry R4", "mid", 95),
        ("CYSM", "Artisan", "Keyby Galaxy Purple", "Cherry R4", "mid", 130),

        # ── Artkey — More Sculpts ─────────────────────────────────────────
        ("Artkey", "Artisan", "Sirius Glacier", "Cherry R4", "high", 215),
        ("Artkey", "Artisan", "Bull V2 Sakura", "Cherry R4", "high", 245),
        ("Artkey", "Artisan", "Exmor Ultraviolet", "Cherry R4", "high", 225),
        ("Artkey", "Artisan", "Fulfillment Emerald", "Cherry R4", "high", 200),

        # ── Latrialum — More Sculpts ──────────────────────────────────────
        ("Latrialum", "Artisan", "Nebula Void ESC", "Cherry R4", "high", 230),
        ("Latrialum", "Artisan", "Royal Stardust WASD Set", "Cherry R4", "high", 360),
        ("Latrialum", "Artisan", "Celestial Rose ESC", "Cherry R4", "high", 200),

        # ── Bro Caps — More Sculpts ───────────────────────────────────────
        ("Bro Caps", "Artisan", "Reaper Classic Toxic", "Cherry R1", "grail", 680),
        ("Bro Caps", "Artisan", "Broshido Samurai Gold", "Cherry R1", "grail", 580),
        ("Bro Caps", "Artisan", "Brobot V2 Liberty", "Cherry R1", "grail", 620),

        # ── ETF (Nightcaps) — More Sculpts ────────────────────────────────
        ("ETF (Nightcaps)", "Artisan", "Fugthulhu Spectral Ojum", "Cherry R1", "grail", 530),
        ("ETF (Nightcaps)", "Artisan", "Smegface Lepidopterist", "Cherry R1", "grail", 470),
        ("ETF (Nightcaps)", "Artisan", "Egg V2 Nocticulture", "Cherry R1", "high", 350),
        ("ETF (Nightcaps)", "Artisan", "Dental Plan Crocodile Tears", "Cherry R1", "high", 370),

        # ── Alpha Keycaps — More Sculpts ──────────────────────────────────
        ("Alpha Keycaps", "Artisan", "Keypora Frozen Heart", "Cherry R1", "high", 310),
        ("Alpha Keycaps", "Artisan", "Salvador Aqua Marine", "Cherry R1", "high", 250),
        ("Alpha Keycaps", "Artisan", "Mr.Ed Thunder Stallion", "Cherry R1", "high", 210),

        # ── Premium Switches (reference items) ────────────────────────────
        ("ZealPC", "Switch", "Zealios V2 67g (pack of 90)", "N/A", "mid", 100),
        ("Drop", "Switch", "Holy Panda V2 (pack of 90)", "N/A", "mid", 95),
        ("Gateron", "Switch", "Gateron Ink Black V2 (pack of 90)", "N/A", "mid", 65),
        ("Cherry", "Switch", "Cherry MX Black Hyperglide (pack of 90)", "N/A", "standard", 45),
        ("TTC", "Switch", "TTC Gold Pink V2 (pack of 90)", "N/A", "standard", 55),
        ("JWK", "Switch", "Durock POM Linear (pack of 90)", "N/A", "standard", 50),
        ("Kailh", "Switch", "Kailh Box Navy (pack of 90)", "N/A", "standard", 45),
        ("SP-Star", "Switch", "SP-Star Meteor White (pack of 90)", "N/A", "standard", 55),

        # ── Additional Keyboard Builds (more premium) ─────────────────────
        ("Keycult", "Keyboard Build", "Keycult No. 1/60 Full Build", "N/A", "grail", 3200),
        ("TGR", "Keyboard Build", "TGR Alice Full Build", "N/A", "grail", 2500),
        ("Matrix Lab", "Keyboard Build", "Matrix Lab 2.0add Full Build", "N/A", "high", 400),
        ("Brutal60", "Keyboard Build", "CannonKeys Brutal60 Full Build", "N/A", "mid", 180),
        ("Mode", "Keyboard Build", "Mode Sonnet Full Build", "N/A", "mid", 200),
        ("KBDFans", "Keyboard Build", "KBDFans D65 Full Build", "N/A", "mid", 180),
        ("Qwertykeys", "Keyboard Build", "QK65 Full Build", "N/A", "standard", 150),
        ("Geon", "Keyboard Build", "Geon F1-8X Full Build", "N/A", "grail", 1800),
        ("Lin Works", "Keyboard Build", "Dolphin V3 Full Build", "N/A", "grail", 2800),
        ("OTD", "Keyboard Build", "OTD 360 Corsa Full Build", "N/A", "grail", 4000),

        # ── SA Profile Sets — More ────────────────────────────────────────
        ("Signature Plastics", "Keycap Set", "SA Nantucket Selectric Base Kit", "SA", "mid", 170),
        ("Signature Plastics", "Keycap Set", "SA Dancer Base Kit", "SA", "mid", 150),
        ("Signature Plastics", "Keycap Set", "SA Berserk Base Kit", "SA", "mid", 160),
        ("Signature Plastics", "Keycap Set", "SA 1976 Base Kit", "SA", "mid", 180),

        # ── KAT Profile Sets — More ──────────────────────────────────────
        ("Keyreative", "Keycap Set", "KAT Explosion Alpha Kit", "KAT", "mid", 110),
        ("Keyreative", "Keycap Set", "KAT Eternal Alpha Kit", "KAT", "mid", 100),
        ("Keyreative", "Keycap Set", "KAT Great Wave Alpha Kit", "KAT", "mid", 120),

        # ── ePBT Sets — More ─────────────────────────────────────────────
        ("ePBT", "Keycap Set", "ePBT Dreamscape Base Kit", "Cherry", "mid", 100),
        ("ePBT", "Keycap Set", "ePBT Sniper Base Kit", "Cherry", "mid", 95),
        ("ePBT", "Keycap Set", "ePBT Cool Kids Base Kit", "Cherry", "mid", 105),
        ("ePBT", "Keycap Set", "ePBT Wuyue Base Kit", "Cherry", "mid", 110),

        # ── DSA Profile Sets ──────────────────────────────────────────────
        ("Signature Plastics", "Keycap Set", "DSA Magic Girl Base Kit", "DSA", "mid", 140),
        ("Signature Plastics", "Keycap Set", "DSA Milkshake Base Kit", "DSA", "mid", 130),

        # ── More Artisan Makers ──────────────────────────────────────────
        ("Monstera Keycaps", "Artisan", "Dragon Warrior Obsidian", "Cherry R1", "mid", 120),
        ("Monstera Keycaps", "Artisan", "Dragon Warrior Jade", "Cherry R1", "mid", 125),
        ("KapCave", "Artisan", "Blanktopus Ocean Blue", "Cherry R1", "mid", 85),
        ("KapCave", "Artisan", "Blanktopus Lava", "Cherry R1", "mid", 90),
        ("Clack Factory", "Artisan", "Skull OG Topre", "Topre", "grail", 1500),
        ("Clack Factory", "Artisan", "Skull 420 Green", "Topre", "grail", 1200),
        ("ClickClack", "Artisan", "Skull Tri-Color", "Cherry R1", "grail", 1000),
        ("Suited Up Keycaps", "Artisan", "Keybuto III Ronin", "Cherry R1", "high", 200),
        ("Suited Up Keycaps", "Artisan", "Keybuto III Imperial", "Cherry R1", "high", 220),
        ("JAK", "Artisan", "Birb OG Pink", "Cherry R1", "mid", 150),
        ("JAK", "Artisan", "Kota Deep Space", "Cherry R1", "mid", 130),
        ("Polymer Salon", "Artisan", "Murray Jolly Roger", "Cherry R1", "mid", 120),
        ("Polymer Salon", "Artisan", "Murray Toxic Slime", "Cherry R1", "mid", 110),

        # ── GMK Archive — Extended ──────────────────────────────────────────
        ("GMK", "Keycap Set", "GMK Noel Base Kit", "Cherry", "high", 280),
        ("GMK", "Keycap Set", "GMK Shoko Base Kit", "Cherry", "high", 260),
        ("GMK", "Keycap Set", "GMK Alter Base Kit", "Cherry", "mid", 180),
        ("GMK", "Keycap Set", "GMK Tuzi Base Kit", "Cherry", "mid", 165),
        ("GMK", "Keycap Set", "GMK Masterpiece Base Kit", "Cherry", "mid", 170),
        ("GMK", "Keycap Set", "GMK Pixel Base Kit", "Cherry", "mid", 155),
        ("GMK", "Keycap Set", "GMK Mictlan Base Kit", "Cherry", "mid", 175),
        ("GMK", "Keycap Set", "GMK Deep Navy Base Kit", "Cherry", "mid", 150),
        ("GMK", "Keycap Set", "GMK Redacted Base Kit", "Cherry", "mid", 145),
        ("GMK", "Keycap Set", "GMK Jamon Base Kit", "Cherry", "mid", 165),
        ("GMK", "Keycap Set", "GMK Hero Base Kit", "Cherry", "mid", 160),
        ("GMK", "Keycap Set", "GMK Umbra Base Kit", "Cherry", "mid", 155),
        ("GMK", "Keycap Set", "GMK Shashin Base Kit", "Cherry", "mid", 170),
        ("GMK", "Keycap Set", "GMK Bingsu Base Kit", "Cherry", "mid", 175),
        ("GMK", "Keycap Set", "GMK Fro.Yo Base Kit", "Cherry", "mid", 165),
        ("GMK", "Keycap Set", "GMK Deku Base Kit", "Cherry", "mid", 180),
        ("GMK", "Keycap Set", "GMK Classic Blue Base Kit", "Cherry", "mid", 140),
        ("GMK", "Keycap Set", "GMK Phosphorous Base Kit", "Cherry", "mid", 170),
        ("GMK", "Keycap Set", "GMK Bleached Base Kit", "Cherry", "mid", 130),
        ("GMK", "Keycap Set", "GMK WoB Katakana Base Kit", "Cherry", "mid", 150),
        ("GMK", "Keycap Set", "GMK BoW Hangul Base Kit", "Cherry", "mid", 140),
        ("GMK", "Keycap Set", "GMK Future Funk Base Kit", "Cherry", "high", 220),
        ("GMK", "Keycap Set", "GMK Burgundy Base Kit", "Cherry", "mid", 155),
        ("GMK", "Keycap Set", "GMK Merlin Base Kit", "Cherry", "mid", 165),
        ("GMK", "Keycap Set", "GMK Metaverse Base Kit", "Cherry", "high", 210),
        ("GMK", "Keycap Set", "GMK Yuri Base Kit", "Cherry", "mid", 185),
        ("GMK", "Keycap Set", "GMK Pink on Navy Base Kit", "Cherry", "mid", 170),
        ("GMK", "Keycap Set", "GMK Nord Base Kit", "Cherry", "mid", 160),
        ("GMK", "Keycap Set", "GMK Olive Base Kit", "Cherry", "mid", 175),
        ("GMK", "Keycap Set", "GMK Classic Retro Base Kit", "Cherry", "mid", 165),
        ("GMK", "Keycap Set", "GMK Modern Dolch Base Kit", "Cherry", "mid", 185),
        ("GMK", "Keycap Set", "GMK Modern Dolch Light Base Kit", "Cherry", "mid", 160),
        ("GMK", "Keycap Set", "GMK Skeletor Base Kit", "Cherry", "mid", 165),
        ("GMK", "Keycap Set", "GMK Miami Nights Base Kit", "Cherry", "mid", 170),
        ("GMK", "Keycap Set", "GMK Sumi Base Kit", "Cherry", "mid", 190),
        ("GMK", "Keycap Set", "GMK Fundamentals Base Kit", "Cherry", "mid", 135),
        ("GMK", "Keycap Set", "GMK Bread Base Kit", "Cherry", "mid", 150),
        ("GMK", "Keycap Set", "GMK Prepress Base Kit", "Cherry", "mid", 155),
        ("GMK", "Keycap Set", "GMK Analog Dreams Base Kit", "Cherry", "mid", 170),
        ("GMK", "Keycap Set", "GMK Civilizations Base Kit", "Cherry", "mid", 180),
        ("GMK", "Keycap Set", "GMK Kaonashi Base Kit", "Cherry", "mid", 175),
        ("GMK", "Keycap Set", "GMK Solarized Dark Base Kit", "Cherry", "mid", 145),
        ("GMK", "Keycap Set", "GMK Honor Base Kit", "Cherry", "mid", 170),
        ("GMK", "Keycap Set", "GMK Alpine Base Kit", "Cherry", "mid", 165),
        ("GMK", "Keycap Set", "GMK Iceberg Base Kit", "Cherry", "mid", 160),
        ("GMK", "Keycap Set", "GMK Midnight Rainbow Base Kit", "Cherry", "mid", 175),
        ("GMK", "Keycap Set", "GMK Stargaze Base Kit", "Cherry", "mid", 180),
        ("GMK", "Keycap Set", "GMK Ursa Base Kit", "Cherry", "mid", 155),
        ("GMK", "Keycap Set", "GMK Perestroika Base Kit", "Cherry", "high", 240),
        ("GMK", "Keycap Set", "GMK Maestro Base Kit", "Cherry", "mid", 165),

        # ── More Artisan Makers — Comprehensive ────────────────────────────
        ("Archetype", "Artisan", "Kolkrabba Aurora", "Cherry R1", "mid", 120),
        ("Archetype", "Artisan", "Kolkrabba Void", "Cherry R1", "mid", 130),
        ("Archetype", "Artisan", "Zed Crimson", "Cherry R1", "mid", 110),
        ("Shirouu", "Artisan", "Tsuneko Sakura", "Cherry R1", "mid", 140),
        ("Shirouu", "Artisan", "Tsuneko Galaxy", "Cherry R1", "mid", 150),
        ("Shirouu", "Artisan", "Nekomata Frost", "Cherry R1", "mid", 135),
        ("Shirouu", "Artisan", "Nekomata Ember", "Cherry R1", "mid", 145),
        ("PrimeCaps", "Artisan", "Al Bumen Cosmic Egg", "Cherry R1", "mid", 80),
        ("PrimeCaps", "Artisan", "Deep Field Nebula V2", "Cherry R1", "mid", 90),
        ("PrimeCaps", "Artisan", "Cloud Chaser Sunset", "Cherry R1", "mid", 85),
        ("Loki Studios", "Artisan", "Raijin Thunder God", "Cherry R1", "high", 200),
        ("Loki Studios", "Artisan", "Fujin Wind God", "Cherry R1", "high", 200),
        ("Hammer Works", "Artisan", "Tiki OG Green", "Cherry R1", "mid", 100),
        ("Hammer Works", "Artisan", "Tiki Crimson", "Cherry R1", "mid", 105),
        ("Keyforge", "Artisan", "Shishi Volcanic", "Cherry R1", "high", 300),
        ("Keyforge", "Artisan", "Shishi Glacial", "Cherry R1", "high", 280),
        ("Keyforge", "Artisan", "Orochi Sanguine", "Cherry R1", "high", 250),
        ("Keyforge", "Artisan", "Mulder V3 Nightshade", "Cherry R1", "high", 220),
        ("Ritual Master", "Artisan", "Watcher Obsidian", "Cherry R1", "mid", 110),
        ("Ritual Master", "Artisan", "Watcher Emerald", "Cherry R1", "mid", 115),
        ("Gothcaps", "Artisan", "Brimcap Hellfire", "Cherry R1", "mid", 100),
        ("Gothcaps", "Artisan", "Brimcap Grave Digger", "Cherry R1", "mid", 105),
        ("Gothcaps", "Artisan", "Sunken Hellcap", "Cherry R1", "mid", 95),
        ("Bad Habit Caps", "Artisan", "Shade Obsidian", "Cherry R1", "mid", 90),
        ("Bad Habit Caps", "Artisan", "Tiki Void", "Cherry R1", "mid", 95),
        ("Namong", "Artisan", "No Face Spirited Gold", "Cherry R1", "mid", 130),
        ("Namong", "Artisan", "Totoro Leaf Umbrella", "Cherry R1", "mid", 120),
        ("Dollface", "Artisan", "No Face V2 Shadow", "Cherry R1", "mid", 110),
        ("Artisan Labs", "Artisan", "Appa Yip Yip", "Cherry R1", "mid", 100),
        ("Artisan Labs", "Artisan", "Baby Yoda Grogu", "Cherry R1", "mid", 105),
        ("MMCaps", "Artisan", "Gengar Ghost Purple", "Cherry R1", "mid", 110),
        ("MMCaps", "Artisan", "Bulbasaur Garden", "Cherry R1", "mid", 95),
        ("Tinymakesthings", "Artisan", "Yeti OG White", "Cherry R1", "mid", 85),
        ("Tinymakesthings", "Artisan", "Yeti Berry", "Cherry R1", "mid", 90),

        # ── S-Craft — More Pokemon ──────────────────────────────────────────
        ("S-Craft", "Artisan", "Pokemon Mewtwo SA R1", "SA R1", "high", 195),
        ("S-Craft", "Artisan", "Pokemon Dragonite SA R1", "SA R1", "high", 185),
        ("S-Craft", "Artisan", "Pokemon Togepi SA R1", "SA R1", "high", 165),
        ("S-Craft", "Artisan", "Pokemon Ditto SA R1", "SA R1", "high", 170),
        ("S-Craft", "Artisan", "Pokemon Psyduck SA R1", "SA R1", "high", 175),
        ("S-Craft", "Artisan", "Pokemon Mew SA R1", "SA R1", "high", 200),
        ("S-Craft", "Artisan", "Pokemon Vulpix SA R1", "SA R1", "high", 180),
        ("S-Craft", "Artisan", "Pokemon Magikarp SA R1", "SA R1", "high", 160),

        # ── More Keyboard Builds — Custom Layouts ───────────────────────────
        ("Geon", "Keyboard Build", "Geon F1-8X V2 TKL Full Build", "N/A", "grail", 2000),
        ("Jelly Epoch", "Keyboard Build", "Jelly Epoch 65% Full Build", "N/A", "high", 400),
        ("Mammoth", "Keyboard Build", "Mammoth75 Full Build", "N/A", "mid", 200),
        ("Space65", "Keyboard Build", "Graystudio Space65 R3 Full Build", "N/A", "mid", 180),
        ("Satisfaction 75", "Keyboard Build", "CannonKeys Satisfaction 75 R2 Full Build", "N/A", "high", 350),
        ("Rama", "Keyboard Build", "Rama Works U80-A SEQ2 Full Build", "N/A", "high", 400),
        ("Rama", "Keyboard Build", "Rama Works M65-B Full Build", "N/A", "high", 380),
        ("Geonworks", "Keyboard Build", "Geon Tadpole Full Build", "N/A", "mid", 180),
        ("NK", "Keyboard Build", "NK65 Entry Edition Full Build", "N/A", "standard", 120),
        ("Ikki68", "Keyboard Build", "Ikki68 Aurora R2 Full Build", "N/A", "standard", 140),
        ("Zoom", "Keyboard Build", "Zoom65 V2 Full Build", "N/A", "standard", 130),
        ("Owlab", "Keyboard Build", "Owlab Jelly Epoch SE Full Build", "N/A", "high", 350),
        ("Frog", "Keyboard Build", "Geonworks Frog Mini Full Build", "N/A", "mid", 190),
        ("Percent Studio", "Keyboard Build", "Canoe Gen2 Full Build", "N/A", "mid", 200),
        ("Proto[Typist]", "Keyboard Build", "Proto[Typist] Ciel 65 Full Build", "N/A", "mid", 180),

        # ── Premium Switches — Extended ─────────────────────────────────────
        ("C3 Equalz", "Switch", "Tangerine V2 67g (pack of 90)", "N/A", "mid", 70),
        ("C3 Equalz", "Switch", "Banana Split V2 (pack of 90)", "N/A", "mid", 65),
        ("JWK", "Switch", "Alpaca V2 Linear (pack of 90)", "N/A", "mid", 60),
        ("JWK", "Switch", "Lavender Linear (pack of 90)", "N/A", "mid", 55),
        ("JWK", "Switch", "H1 Linear (pack of 90)", "N/A", "mid", 60),
        ("Gateron", "Switch", "Oil King Linear (pack of 90)", "N/A", "mid", 55),
        ("Cherry", "Switch", "Cherry MX Nixie Linear (pack of 90)", "N/A", "mid", 75),
        ("Tecsee", "Switch", "Ice Candy V2 (pack of 90)", "N/A", "standard", 45),
        ("KTT", "Switch", "KTT Strawberry (pack of 90)", "N/A", "standard", 35),
        ("Akko", "Switch", "Akko Cream Yellow V3 (pack of 90)", "N/A", "standard", 30),
        ("Gazzew", "Switch", "Boba U4T Thocky 62g (pack of 90)", "N/A", "mid", 60),
        ("Gazzew", "Switch", "Boba U4 Silent 62g (pack of 90)", "N/A", "mid", 60),
        ("TTC", "Switch", "TTC Bluish White (pack of 90)", "N/A", "standard", 40),
        ("NovelKeys", "Switch", "NK Cream V2 (pack of 90)", "N/A", "mid", 65),
        ("Kinetic Labs", "Switch", "Hippo Linear (pack of 90)", "N/A", "standard", 50),
        ("Wuque Studio", "Switch", "WS Morandi Linear (pack of 90)", "N/A", "standard", 55),

        # ── Deskmats ────────────────────────────────────────────────────────
        ("NovelKeys", "Deskmat", "NovelKeys Randomfrankp Deskmat", "N/A", "standard", 30),
        ("GMK", "Deskmat", "GMK Botanical Deskmat", "N/A", "mid", 60),
        ("GMK", "Deskmat", "GMK Olivia Deskmat", "N/A", "mid", 65),
        ("GMK", "Deskmat", "GMK Mizu Deskmat Great Wave", "N/A", "mid", 70),
        ("GMK", "Deskmat", "GMK Darling Deskmat", "N/A", "mid", 75),
        ("GMK", "Deskmat", "GMK Bento Deskmat", "N/A", "mid", 55),
        ("GMK", "Deskmat", "GMK Dots Deskmat", "N/A", "mid", 50),
        ("GMK", "Deskmat", "GMK Dracula Deskmat Castle", "N/A", "mid", 55),
        ("Dixie Mech", "Deskmat", "Dixie Mech Laser Deskmat Synthwave", "N/A", "mid", 55),
        ("Omnitype", "Deskmat", "Omnitype Meka Mat V2", "N/A", "standard", 35),
        ("NovelKeys", "Deskmat", "NovelKeys Godspeed Deskmat", "N/A", "mid", 45),
        ("Bolsa Supply", "Deskmat", "Bolsa Supply Taeha Types Deskmat", "N/A", "standard", 40),

        # ── Cables ──────────────────────────────────────────────────────────
        ("Space Cables", "Cable", "Space Cables Laser Theme USB-C Coiled", "N/A", "mid", 75),
        ("Space Cables", "Cable", "Space Cables Botanical Theme USB-C Coiled", "N/A", "mid", 75),
        ("Custom Cables", "Cable", "Mechcables Olivia Theme Coiled", "N/A", "mid", 70),
        ("Custom Cables", "Cable", "Mechcables Bento Theme Coiled", "N/A", "mid", 65),
        ("Zap Cables", "Cable", "Zap Cables Custom USB-C Lemo Connector", "N/A", "mid", 80),
        ("Zap Cables", "Cable", "Zap Cables YC8 Connector Purple", "N/A", "mid", 70),
        ("Cruz Ctrl", "Cable", "Cruz Ctrl Cream Cable Coiled Aviator", "N/A", "mid", 65),

        # ── Stabilizers ─────────────────────────────────────────────────────
        ("Durock", "Stabilizer", "Durock V2 Screw-In Stabilizers (7u Kit)", "N/A", "standard", 25),
        ("C3 Equalz", "Stabilizer", "C3 Equalz x TKC V3 Stabilizers", "N/A", "standard", 30),
        ("Owlab", "Stabilizer", "Owlab Stabilizers V2 (7u Kit)", "N/A", "mid", 35),
        ("TX", "Stabilizer", "TX Stabilizers AP V3 (7u Kit)", "N/A", "standard", 28),
        ("Staebies", "Stabilizer", "Staebies R2 Stabilizers (7u Kit)", "N/A", "standard", 22),
        ("Gateron", "Stabilizer", "Gateron Ink V2 Stabilizers", "N/A", "standard", 20),

        # ── Plate Materials (reference items) ───────────────────────────────
        ("Custom", "Plate", "FR4 Plate Universal 60% Layout", "N/A", "standard", 25),
        ("Custom", "Plate", "Polycarbonate Plate 65% Layout", "N/A", "standard", 30),
        ("Custom", "Plate", "Aluminum Plate TKL Layout", "N/A", "standard", 35),
        ("Custom", "Plate", "Brass Plate 65% Layout", "N/A", "mid", 50),
        ("Custom", "Plate", "POM Plate 60% Layout", "N/A", "standard", 28),
        ("Custom", "Plate", "Carbon Fiber Plate 75% Layout", "N/A", "mid", 60),

        # ── Cherry Profile Clones & Budget Sets ─────────────────────────────
        ("PBTfans", "Keycap Set", "PBTfans Doubleshot BOW Base Kit", "Cherry", "standard", 60),
        ("PBTfans", "Keycap Set", "PBTfans Doubleshot WOB Base Kit", "Cherry", "standard", 60),
        ("PBTfans", "Keycap Set", "PBTfans Retro 100 Base Kit", "Cherry", "standard", 70),
        ("PBTfans", "Keycap Set", "PBTfans Spark Base Kit", "Cherry", "standard", 65),
        ("NicePBT", "Keycap Set", "NicePBT Sugarplum Base Kit", "Cherry", "standard", 55),
        ("NicePBT", "Keycap Set", "NicePBT Elderberry Base Kit", "Cherry", "standard", 50),
        ("NicePBT", "Keycap Set", "NicePBT Noel Base Kit", "Cherry", "standard", 55),
        ("Akko", "Keycap Set", "Akko 9009 Retro Base Kit", "Cherry", "standard", 45),
        ("Akko", "Keycap Set", "Akko Black & Gold Base Kit", "Cherry", "standard", 45),
        ("Akko", "Keycap Set", "Akko Macaw Base Kit", "Cherry", "standard", 40),
        ("Drop", "Keycap Set", "Drop + MiTo XDA Canvas Base Kit", "XDA", "mid", 80),
        ("Drop", "Keycap Set", "Drop + biip MT3 Extended 2048 Base Kit", "MT3", "mid", 90),
        ("Drop", "Keycap Set", "Drop + Matt3o MT3 Susuwatari Base Kit", "MT3", "mid", 85),
        ("Drop", "Keycap Set", "Drop + matt3o MT3 /dev/tty Base Kit", "MT3", "mid", 85),

        # ── More Artisan Grails ─────────────────────────────────────────────
        ("Hunger Work Studio", "Artisan", "Meet Popsi Skull OG", "Cherry R1", "grail", 500),
        ("Hunger Work Studio", "Artisan", "Otterophile Neptunian", "Cherry R1", "high", 350),
        ("Hunger Work Studio", "Artisan", "Skulthulhu Elder God", "Cherry R1", "grail", 450),
        ("KeyKollectiv", "Artisan", "Frankenfurt OG Watermelon", "Cherry R1", "grail", 600),
        ("KeyKollectiv", "Artisan", "Purrkey Calico Cat", "Cherry R1", "high", 380),
        ("Booper", "Artisan", "Colonel Lilac", "Cherry R1", "high", 350),
        ("Booper", "Artisan", "Keywok Sakura", "Cherry R1", "high", 300),
        ("KWK", "Artisan", "Mummy III OG Red", "Cherry R1", "grail", 800),
        ("KWK", "Artisan", "Mummy III Spectral Blue", "Cherry R1", "grail", 700),
        ("Zorbcaps", "Artisan", "Golem V3 Starfield", "Cherry R1", "mid", 120),
        ("Zorbcaps", "Artisan", "Flora Sakura Bloom", "Cherry R1", "mid", 110),
        ("RAMA", "Artisan", "RAMA Wave SEQ2 Moon", "Cherry R1", "mid", 80),
        ("RAMA", "Artisan", "RAMA X Keycult Brass Keycap", "Cherry R1", "high", 200),
        ("RAMA", "Artisan", "RAMA Cherry Liquid Series Gold", "Cherry R1", "mid", 90),

        # ── More GMK Sets — Completing the Archive ──────────────────────────
        ("GMK", "Keycap Set", "GMK Amethyst Base Kit", "Cherry", "mid", 170),
        ("GMK", "Keycap Set", "GMK Frost Base Kit", "Cherry", "mid", 160),
        ("GMK", "Keycap Set", "GMK Copper Base Kit", "Cherry", "mid", 155),
        ("GMK", "Keycap Set", "GMK Belafonte Base Kit", "Cherry", "mid", 165),
        ("GMK", "Keycap Set", "GMK Crimson Cadet Base Kit", "Cherry", "mid", 170),
        ("GMK", "Keycap Set", "GMK First Love Base Kit", "Cherry", "mid", 175),
        ("GMK", "Keycap Set", "GMK Pono Base Kit", "Cherry", "mid", 145),
        ("GMK", "Keycap Set", "GMK Dracula Err! Base Kit", "Cherry", "mid", 195),
        ("GMK", "Keycap Set", "GMK Polaris Base Kit", "Cherry", "mid", 175),
        ("GMK", "Keycap Set", "GMK Boneyard Base Kit", "Cherry", "mid", 160),
        ("GMK", "Keycap Set", "GMK Tiramisu Base Kit", "Cherry", "mid", 155),
        ("GMK", "Keycap Set", "GMK Godspeed Base Kit", "Cherry", "mid", 190),
        ("GMK", "Keycap Set", "GMK Rouge Base Kit", "Cherry", "mid", 165),
        ("GMK", "Keycap Set", "GMK Moonlight Base Kit", "Cherry", "mid", 175),

        # ── Additional Artisan Makers ───────────────────────────────────────
        ("Coconut Keycaps", "Artisan", "Coconut No Face Gold", "Cherry R1", "mid", 100),
        ("Coconut Keycaps", "Artisan", "Coconut Totoro Green", "Cherry R1", "mid", 95),
        ("Lo-Ki Caps", "Artisan", "GiCi Skull Red Eyes", "Cherry R1", "mid", 85),
        ("Lo-Ki Caps", "Artisan", "GiCi Skull UV Reactive", "Cherry R1", "mid", 90),
        ("Trmk", "Artisan", "Nova Nebula Blue", "Cherry R1", "mid", 110),
        ("Trmk", "Artisan", "Nova Solar Flare", "Cherry R1", "mid", 115),
        ("CKC", "Artisan", "Telepunk Vaporwave", "Cherry R1", "mid", 95),
        ("CKC", "Artisan", "Telepunk Cyberpunk", "Cherry R1", "mid", 100),

        # ── Expanded Batch — Dwarf Factory, Jellykey, CYSM, Artkey, Latrialum, Melonkeys, GSK (50) ──

        # Dwarf Factory — Kraken, Terrarium, Foodie
        ("Dwarf Factory", "Artisan", "Kraken Abyss Blue", "Cherry R1", "mid", 75),
        ("Dwarf Factory", "Artisan", "Kraken Inferno Red", "Cherry R1", "mid", 78),
        ("Dwarf Factory", "Artisan", "Kraken Deep Ocean Teal", "Cherry R1", "mid", 80),
        ("Dwarf Factory", "Artisan", "Terrarium Keycap Spring Garden", "Cherry R1", "mid", 82),
        ("Dwarf Factory", "Artisan", "Terrarium Keycap Winter Frost", "Cherry R1", "mid", 80),
        ("Dwarf Factory", "Artisan", "Terrarium Keycap Deep Forest", "Cherry R1", "mid", 78),
        ("Dwarf Factory", "Artisan", "Foodie Bacon & Eggs", "Cherry R1", "standard", 55),
        ("Dwarf Factory", "Artisan", "Foodie Ramen Bowl", "Cherry R1", "standard", 58),
        ("Dwarf Factory", "Artisan", "Foodie Sushi Platter", "Cherry R1", "standard", 55),

        # Jellykey — Zen Pond, Koi Pond, Dragon of Eden, Born of Forest
        ("Jelly Key", "Artisan", "Zen Pond III Emerald Koi 6.25u Spacebar", "SA R1", "mid", 120),
        ("Jelly Key", "Artisan", "Zen Pond III Moonlight Koi", "SA R1", "mid", 95),
        ("Jelly Key", "Artisan", "Koi Pond Autumn Leaves 2.25u Shift", "SA R1", "mid", 110),
        ("Jelly Key", "Artisan", "Koi Pond Summer Breeze", "SA R1", "mid", 105),
        ("Jelly Key", "Artisan", "Dragon of Eden Crimson Flame", "SA R1", "mid", 115),
        ("Jelly Key", "Artisan", "Dragon of Eden Frost Wing", "SA R1", "mid", 110),
        ("Jelly Key", "Artisan", "Born of Forest Series Redwood", "SA R1", "mid", 85),
        ("Jelly Key", "Artisan", "Born of Forest Series Cherry Blossom", "SA R1", "mid", 90),

        # CYSM — Keyby, Boo
        ("CYSM", "Artisan", "Keyby Coral Reef V2", "Cherry R4", "mid", 105),
        ("CYSM", "Artisan", "Keyby Sakura Pink", "Cherry R4", "mid", 110),
        ("CYSM", "Artisan", "Keyby Midnight Galaxy", "Cherry R4", "mid", 130),
        ("CYSM", "Artisan", "Boo Ghost White", "Cherry R4", "mid", 80),
        ("CYSM", "Artisan", "Boo Phantom Purple", "Cherry R4", "mid", 85),
        ("CYSM", "Artisan", "Boo Pumpkin Spice", "Cherry R4", "mid", 82),

        # Artkey — Sirius, Exmor, Fulfillment
        ("Artkey", "Artisan", "Sirius Void Black", "Cherry R4", "high", 230),
        ("Artkey", "Artisan", "Sirius Solar Gold", "Cherry R4", "high", 240),
        ("Artkey", "Artisan", "Exmor Stardust", "Cherry R4", "high", 215),
        ("Artkey", "Artisan", "Exmor Bloodmoon", "Cherry R4", "high", 225),
        ("Artkey", "Artisan", "Fulfillment Serenity", "Cherry R4", "high", 200),
        ("Artkey", "Artisan", "Fulfillment Chaos", "Cherry R4", "high", 210),

        # Latrialum — GMK Royal, Empress
        ("Latrialum", "Artisan", "GMK Royal ESC + Fn (Navy/Gold)", "Cherry R4", "high", 320),
        ("Latrialum", "Artisan", "GMK Royal Arrow Set", "Cherry R4", "grail", 450),
        ("Latrialum", "Artisan", "Empress Aurora ESC", "Cherry R4", "high", 250),
        ("Latrialum", "Artisan", "Empress Midnight ESC + Fn Set", "Cherry R4", "high", 340),
        ("Latrialum", "Artisan", "Ethereal Radiance WASD Set", "Cherry R4", "grail", 420),

        # Melonkeys
        ("Melonkeys", "Artisan", "Suika Watermelon V2", "Cherry R1", "mid", 85),
        ("Melonkeys", "Artisan", "Mango Tango", "Cherry R1", "mid", 80),
        ("Melonkeys", "Artisan", "Grape Soda", "Cherry R1", "mid", 80),
        ("Melonkeys", "Artisan", "Dragon Fruit Pink", "Cherry R1", "mid", 85),

        # GSK — Velites, Hogzilla expansion
        ("GSK", "Artisan", "Velites Crimson Guard", "Cherry R1", "mid", 145),
        ("GSK", "Artisan", "Velites Frost Sentinel", "Cherry R1", "mid", 140),
        ("GSK", "Artisan", "Velites Shadow Legion", "Cherry R1", "mid", 150),
        ("GSK", "Artisan", "Hogzilla Verdant Moss", "Cherry R1", "mid", 125),
        ("GSK", "Artisan", "Hogzilla Obsidian Night", "Cherry R1", "mid", 130),
        ("GSK", "Artisan", "Hogzilla Sakura Bloom", "Cherry R1", "mid", 128),
        ("GSK", "Artisan", "Mandrill Volcanic Red", "Cherry R1", "mid", 130),
        ("GSK", "Artisan", "Leo Midnight Black", "Cherry R1", "mid", 120),
        ("GSK", "Artisan", "Froggo Deep Sea", "Cherry R1", "mid", 108),

        # ── Dwarf Factory — Expanded Artisans (+10) ──────────────────────────
        ("Dwarf Factory", "Artisan", "Gnarly Drakon Phantom Smoke", "Cherry R1", "mid", 72),
        ("Dwarf Factory", "Artisan", "Gnarly Drakon Azure Depths", "Cherry R1", "mid", 68),
        ("Dwarf Factory", "Artisan", "Anura Golden Poison Frog", "Cherry R1", "mid", 72),
        ("Dwarf Factory", "Artisan", "Anura Blue Strawberry", "Cherry R1", "mid", 70),
        ("Dwarf Factory", "Artisan", "The Flourish Lavender Field", "Cherry R1", "standard", 58),
        ("Dwarf Factory", "Artisan", "The Flourish Moonlit Orchid", "Cherry R1", "standard", 55),
        ("Dwarf Factory", "Artisan", "Moondust Solar Eclipse", "Cherry R1", "mid", 82),
        ("Dwarf Factory", "Artisan", "Moondust Cosmic Dawn", "Cherry R1", "mid", 78),
        ("Dwarf Factory", "Artisan", "Foodie Boba Tea", "Cherry R1", "standard", 55),
        ("Dwarf Factory", "Artisan", "Mystic Dragon Thunderstorm", "Cherry R1", "mid", 82),

        # ── CYSM / Systematik — Expanded Artisans (+8) ──────────────────────
        ("CYSM", "Artisan", "Keyby Frozen Tundra", "Cherry R4", "mid", 115),
        ("CYSM", "Artisan", "Keyby Neon Cyberpunk", "Cherry R4", "mid", 125),
        ("CYSM", "Artisan", "Boba Blueberry Burst", "Cherry R4", "mid", 88),
        ("CYSM", "Artisan", "Ice Dragon Verdant Scale", "Cherry R4", "mid", 118),
        ("Systematik Kaps", "Artisan", "Cheshire Phantom Grin", "Cherry R1", "mid", 135),
        ("Systematik Kaps", "Artisan", "Cheshire Neon Acid", "Cherry R1", "mid", 130),
        ("Systematik Kaps", "Artisan", "Au Revoir Midnight Rose", "Cherry R1", "mid", 128),
        ("Systematik Kaps", "Artisan", "Au Revoir Emerald City", "Cherry R1", "mid", 125),

        # ── Jelly Key — Expanded Artisans (+8) ──────────────────────────────
        ("Jelly Key", "Artisan", "Zen Pond III Sapphire Shimmer", "SA R1", "mid", 95),
        ("Jelly Key", "Artisan", "Arcade Cabinet Pixel Quest", "SA R1", "mid", 92),
        ("Jelly Key", "Artisan", "Constellation Series Andromeda", "SA R1", "mid", 98),
        ("Jelly Key", "Artisan", "Constellation Series Cassiopeia", "SA R1", "mid", 95),
        ("Jelly Key", "Artisan", "Ethereal Reign Stormcaller", "SA R1", "mid", 118),
        ("Jelly Key", "Artisan", "Great Wave Tsunami Gold", "SA R1", "mid", 110),
        ("Jelly Key", "Artisan", "Eternal Lighthouse Starfall", "SA R1", "mid", 105),
        ("Jelly Key", "Artisan", "Nature's Rage Thunderbolt", "SA R1", "mid", 108),

        # ── GMK Group Buy Sets — Expanded (+8) ──────────────────────────────
        ("GMK", "Keycap Set", "GMK Chaos Theory Base Kit", "Cherry", "mid", 175),
        ("GMK", "Keycap Set", "GMK Rainy Season Base Kit", "Cherry", "mid", 165),
        ("GMK", "Keycap Set", "GMK Hammerhead Dark Base Kit", "Cherry", "mid", 185),
        ("GMK", "Keycap Set", "GMK Cojiro Base Kit", "Cherry", "mid", 170),
        ("GMK", "Keycap Set", "GMK Awaken Base Kit", "Cherry", "mid", 180),
        ("GMK", "Keycap Set", "GMK Fuyu Base Kit", "Cherry", "mid", 160),
        ("GMK", "Keycap Set", "GMK Yugo Base Kit", "Cherry", "mid", 155),
        ("GMK", "Keycap Set", "GMK Agent 01 Base Kit", "Cherry", "mid", 185),

        # ── ePBT Sets — Expanded (+6) ───────────────────────────────────────
        ("ePBT", "Keycap Set", "ePBT Aesthetic Base Kit", "Cherry", "mid", 100),
        ("ePBT", "Keycap Set", "ePBT Ramune Base Kit", "Cherry", "mid", 95),
        ("ePBT", "Keycap Set", "ePBT Ivory Base Kit", "Cherry", "mid", 90),
        ("ePBT", "Keycap Set", "ePBT Camo Base Kit", "Cherry", "mid", 105),
        ("ePBT", "Keycap Set", "ePBT Dolch Base Kit", "Cherry", "mid", 95),
        ("ePBT", "Keycap Set", "ePBT Spectrum Base Kit", "Cherry", "mid", 100),

        # ── KAT Profile Sets — Expanded (+6) ────────────────────────────────
        ("Keyreative", "Keycap Set", "KAT Monochrome Alpha Kit", "KAT", "mid", 105),
        ("Keyreative", "Keycap Set", "KAT Napoleonic Alpha Kit", "KAT", "mid", 115),
        ("Keyreative", "Keycap Set", "KAT Oasis Alpha Kit", "KAT", "mid", 110),
        ("Keyreative", "Keycap Set", "KAT Space Dust Alpha Kit", "KAT", "mid", 120),
        ("Keyreative", "Keycap Set", "KAT Iron Alpha Kit", "KAT", "mid", 100),
        ("Keyreative", "Keycap Set", "KAT Drifter Alpha Kit", "KAT", "mid", 105),

        # ── Drop + Collaboration Sets — Expanded (+5) ───────────────────────
        ("Drop", "Keycap Set", "Drop + Zambumon MT3 Serika Base Kit", "MT3", "mid", 95),
        ("Drop", "Keycap Set", "Drop + Oblotzky SA Oblivion V2 Base Kit", "SA", "mid", 110),
        ("Drop", "Keycap Set", "Drop + T0mb3ry SA Carbon R2 Base Kit", "SA", "mid", 105),
        ("Drop", "Keycap Set", "Drop + MiTo GMK Laser R2 Base Kit", "Cherry", "mid", 120),
        ("Drop", "Keycap Set", "Drop + biip MT3 Cyber Base Kit", "MT3", "mid", 90),

        # ── SA Profile Sets — Expanded (+4) ─────────────────────────────────
        ("Signature Plastics", "Keycap Set", "SA Arcane Base Kit", "SA", "mid", 165),
        ("Signature Plastics", "Keycap Set", "SA Sunday Morning Base Kit", "SA", "mid", 155),
        ("Signature Plastics", "Keycap Set", "SA Grand Budapest Base Kit", "SA", "mid", 170),
        ("Signature Plastics", "Keycap Set", "SA Espresso Base Kit", "SA", "mid", 145),
    ]

    catalog = []
    for maker, keycap_type, name, profile, tier, price in caps:
        catalog.append({
            "maker": maker,
            "keycap_type": keycap_type,
            "name": name,
            "profile": profile,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    maker = item["maker"]
    name = item["name"]
    keycap_type = item["keycap_type"]
    profile = item["profile"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{maker}-{name}"),
        title=name,
        set_code=slugify(maker),
        brand=maker,
        rarity=item["rarity_tier"].title(),
        notes=f"{maker} | {keycap_type} | {profile}",
        attributes_json={
            "maker": maker,
            "keycap_type": keycap_type,
            "profile": profile,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    keycap_type = item["keycap_type"]
    type_edition_scores = {
        "Artisan": 0.8,
        "Keycap Set": 0.5,
        "Keyboard Build": 0.6,
        "Switch": 0.3,
        "Deskmat": 0.3,
        "Cable": 0.3,
        "Stabilizer": 0.2,
        "Plate": 0.2,
    }

    maker = item["maker"]
    premium_makers = {
        "GAF (Grimey as Fuck)", "ETF (Nightcaps)", "Bro Caps",
        "Alpha Keycaps", "Latrialum", "GSK", "Artkey",
        "Deag (Death Caps)",
    }
    maker_bonus = 0.2 if maker in premium_makers else 0.0

    edition_score = min(1.0, type_edition_scores.get(keycap_type, 0.5) + maker_bonus)

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": round(edition_score, 2),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Keycaps catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Keycaps Import ===")

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

    logger.info(f"\n=== Keycaps Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
