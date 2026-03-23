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


def _variant_expansion() -> list[dict]:
    """~100 variant items covering colorways, materials, sizes, profiles,
    group buy rounds, kit types, RAMA collabs, special finishes, and clones."""

    # (maker, keycap_type, name, profile, rarity_tier, price_eur)
    variants = [
        # ── Jelly Key Zen Pond — Colorway Variants ─────────────────────
        ("Jelly Key", "Artisan", "Zen Pond III Koi Emerald Pour", "SA R1", "mid", 95),
        ("Jelly Key", "Artisan", "Zen Pond III Koi Crimson Pour", "SA R1", "mid", 95),
        ("Jelly Key", "Artisan", "Zen Pond III Koi Midnight Pour", "SA R1", "mid", 100),
        ("Jelly Key", "Artisan", "Zen Pond III Koi Golden Pour", "SA R1", "mid", 100),
        ("Jelly Key", "Artisan", "Zen Pond III Koi Lavender Pour", "SA R1", "mid", 95),

        # ── Jelly Key — Size Variants ──────────────────────────────────
        ("Jelly Key", "Artisan", "Zen Pond III Cherry Blossom 1u", "Cherry R1", "mid", 75),
        ("Jelly Key", "Artisan", "Zen Pond III Cherry Blossom 2.25u Enter", "SA R1", "mid", 110),
        ("Jelly Key", "Artisan", "Zen Pond III Cherry Blossom 7u Spacebar", "SA R1", "high", 145),
        ("Jelly Key", "Artisan", "Zen Pond III Ochiba 6.25u Spacebar", "SA R1", "mid", 130),
        ("Jelly Key", "Artisan", "Zen Pond III Ochiba 2u Backspace", "SA R1", "mid", 105),

        # ── Material Variants — Resin / Metal / Wood / Ceramic ─────────
        ("Jelly Key", "Artisan", "Dragon of Eden Resin Standard", "SA R1", "mid", 100),
        ("Jelly Key", "Artisan", "Dragon of Eden Metal Infused Brass", "SA R1", "high", 180),
        ("Jelly Key", "Artisan", "Dragon of Eden Wood Inlay Walnut", "SA R1", "mid", 140),
        ("Dwarf Factory", "Artisan", "Gnarly Drakon Ceramic Edition", "Cherry R1", "mid", 95),
        ("Dwarf Factory", "Artisan", "Gnarly Drakon Metal Cast Bronze", "Cherry R1", "high", 120),
        ("Dwarf Factory", "Artisan", "Gnarly Drakon Resin Clear", "Cherry R1", "mid", 65),
        ("CYSM", "Artisan", "Keyby Resin Translucent", "Cherry R4", "mid", 85),
        ("CYSM", "Artisan", "Keyby Metal Brass Edition", "Cherry R4", "high", 160),
        ("CYSM", "Artisan", "Keyby Ceramic Porcelain White", "Cherry R4", "mid", 120),

        # ── Profile Variants — Same Sculpt, Different Profile ──────────
        ("CYSM", "Artisan", "Keyby Classic Blue SA Profile", "SA R1", "mid", 95),
        ("CYSM", "Artisan", "Keyby Classic Blue DSA Profile", "DSA", "mid", 88),
        ("CYSM", "Artisan", "Keyby Classic Blue OEM Profile", "OEM", "mid", 85),
        ("Dwarf Factory", "Artisan", "Gnarly Drakon Obsidian SA Profile", "SA R1", "mid", 70),
        ("Dwarf Factory", "Artisan", "Gnarly Drakon Obsidian DSA Profile", "DSA", "mid", 62),
        ("Artkey", "Artisan", "Sirius Celestial White SA Profile", "SA R1", "high", 210),

        # ── GMK Group Buy Rounds ──────────────────────────────────────
        ("GMK", "Keycap Set", "GMK Olivia R1 Original Base Kit", "Cherry", "grail", 450),
        ("GMK", "Keycap Set", "GMK Olivia R3 Base Kit", "Cherry", "mid", 180),
        ("GMK", "Keycap Set", "GMK Bento R1 Original Base Kit", "Cherry", "high", 350),
        ("GMK", "Keycap Set", "GMK Bento R3 Base Kit", "Cherry", "mid", 150),
        ("GMK", "Keycap Set", "GMK Botanical R3 Base Kit", "Cherry", "mid", 160),
        ("GMK", "Keycap Set", "GMK Mizu R1 Original Base Kit", "Cherry", "grail", 480),
        ("GMK", "Keycap Set", "GMK Dracula R1 Original Core Kit", "Cherry", "high", 320),
        ("GMK", "Keycap Set", "GMK 8008 R2 Base Kit", "Cherry", "high", 220),
        ("GMK", "Keycap Set", "GMK Laser R1 Original Cyberdeck Base", "Cherry", "high", 350),

        # ── Novelty vs Base vs Extension Kits ─────────────────────────
        ("GMK", "Keycap Set", "GMK Olivia++ Novelties Kit", "Cherry", "mid", 120),
        ("GMK", "Keycap Set", "GMK Olivia++ Spacebar Kit", "Cherry", "mid", 60),
        ("GMK", "Keycap Set", "GMK Olivia++ Extension Kit", "Cherry", "mid", 95),
        ("GMK", "Keycap Set", "GMK Botanical Novelties Kit", "Cherry", "mid", 100),
        ("GMK", "Keycap Set", "GMK Botanical Spacebar Kit", "Cherry", "mid", 55),
        ("GMK", "Keycap Set", "GMK Bento Novelties Kit", "Cherry", "mid", 85),
        ("GMK", "Keycap Set", "GMK Bento Spacebar Kit", "Cherry", "mid", 50),
        ("GMK", "Keycap Set", "GMK Laser Novelties Kit", "Cherry", "mid", 95),
        ("GMK", "Keycap Set", "GMK Mizu Novelties Kit", "Cherry", "mid", 110),
        ("GMK", "Keycap Set", "GMK Mizu Extension Kit", "Cherry", "mid", 90),
        ("GMK", "Keycap Set", "GMK Dracula Novelties Kit", "Cherry", "mid", 80),
        ("GMK", "Keycap Set", "GMK Darling Novelties Kit", "Cherry", "mid", 130),
        ("GMK", "Keycap Set", "GMK 8008 Accent Kit", "Cherry", "mid", 85),

        # ── RAMA Collaboration Artisans — Metal/Finish Variants ────────
        ("RAMA", "Artisan", "RAMA x GMK Olivia Rose Gold PVD", "Cherry R1", "high", 180),
        ("RAMA", "Artisan", "RAMA x GMK Olivia Polished Brass", "Cherry R1", "mid", 120),
        ("RAMA", "Artisan", "RAMA x GMK Olivia Matte Aluminum", "Cherry R1", "mid", 90),
        ("RAMA", "Artisan", "RAMA x GMK Botanical Brass PVD", "Cherry R1", "mid", 110),
        ("RAMA", "Artisan", "RAMA x GMK Botanical Aluminum E-White", "Cherry R1", "mid", 85),
        ("RAMA", "Artisan", "RAMA x GMK Bento Brass Salmon", "Cherry R1", "mid", 120),
        ("RAMA", "Artisan", "RAMA x GMK Bento Stainless Steel", "Cherry R1", "mid", 100),
        ("RAMA", "Artisan", "RAMA x GMK Mizu Wave Brass", "Cherry R1", "high", 150),
        ("RAMA", "Artisan", "RAMA x GMK Mizu Wave Aluminum", "Cherry R1", "mid", 95),
        ("RAMA", "Artisan", "RAMA x GMK Dracula Bat Brass", "Cherry R1", "mid", 110),
        ("RAMA", "Artisan", "RAMA x GMK Dracula Bat Aluminum Black", "Cherry R1", "mid", 85),
        ("RAMA", "Artisan", "RAMA x GMK 8008 Brass PVD Pink", "Cherry R1", "mid", 130),
        ("RAMA", "Artisan", "RAMA x GMK Darling Heart Stainless Steel", "Cherry R1", "high", 160),
        ("RAMA", "Artisan", "RAMA x GMK Laser Synthwave Brass", "Cherry R1", "mid", 120),

        # ── Glow-in-Dark / UV-Reactive / Thermal Variants ─────────────
        ("Lo-Ki Caps", "Artisan", "GiCi Skull Glow-in-Dark Green", "Cherry R1", "mid", 95),
        ("Lo-Ki Caps", "Artisan", "GiCi Skull Glow-in-Dark Blue", "Cherry R1", "mid", 95),
        ("Gothcaps", "Artisan", "Brimcap UV-Reactive Toxic Green", "Cherry R1", "mid", 110),
        ("Gothcaps", "Artisan", "Brimcap UV-Reactive Plasma Blue", "Cherry R1", "mid", 110),
        ("Gothcaps", "Artisan", "Sunken Hellcap UV-Reactive Blood Red", "Cherry R1", "mid", 105),
        ("Lividity", "Artisan", "Observer Thermal Color-Change Blue-Pink", "Cherry R1", "mid", 130),
        ("Lividity", "Artisan", "Observer Thermal Color-Change Black-Green", "Cherry R1", "mid", 130),
        ("Sludgekidd", "Artisan", "Fingychomp Glow-in-Dark Ghost White", "Cherry R1", "mid", 125),
        ("Systematik Kaps", "Artisan", "Cheshire UV-Reactive Neon Grin", "Cherry R1", "mid", 140),
        ("Dwarf Factory", "Artisan", "Gnarly Drakon Thermal Shift Purple-Blue", "Cherry R1", "mid", 85),

        # ── Clone vs Authentic GMK Sets ───────────────────────────────
        ("HK Gaming", "Keycap Set", "HK Gaming Chalk PBT (GMK WoB Clone)", "Cherry", "standard", 40),
        ("HK Gaming", "Keycap Set", "HK Gaming Pegaso PBT (GMK Mizu Clone)", "Cherry", "standard", 45),
        ("HK Gaming", "Keycap Set", "HK Gaming 9009 Retro PBT (GMK 9009 Clone)", "Cherry", "standard", 38),
        ("Yong Qiu", "Keycap Set", "YQ Matcha PBT (GMK Botanical Clone)", "Cherry", "standard", 35),
        ("Yong Qiu", "Keycap Set", "YQ Coral PBT (GMK Darling Clone)", "Cherry", "standard", 38),
        ("BoW Clone", "Keycap Set", "Generic PBT Olivia Clone Pink/White", "Cherry", "standard", 30),
        ("BoW Clone", "Keycap Set", "Generic PBT Bento Clone Blue/Salmon", "Cherry", "standard", 32),
        ("BoW Clone", "Keycap Set", "Generic PBT Dracula Clone Purple/Teal", "Cherry", "standard", 30),
        ("BoW Clone", "Keycap Set", "Generic PBT Laser Clone Purple/Cyan", "Cherry", "standard", 32),

        # ── Size Variants — Spacebars & Modifiers ─────────────────────
        ("CYSM", "Artisan", "Keyby Aurora 6.25u Spacebar", "Cherry R4", "high", 200),
        ("CYSM", "Artisan", "Keyby Aurora 2.25u Shift", "Cherry R4", "mid", 160),
        ("Artkey", "Artisan", "Bull V2 Crimson 1.25u Modifier", "Cherry R4", "high", 270),
        ("Artkey", "Artisan", "Bull V2 Crimson 1.5u Tab", "Cherry R4", "high", 275),
        ("S-Craft", "Artisan", "Pokemon Gengar 2u Backspace", "SA R1", "high", 240),
        ("S-Craft", "Artisan", "Pokemon Pikachu 6.25u Spacebar", "SA R1", "high", 280),

        # ── Profile Variants — GMK Sets in Other Profiles ──────────────
        ("Drop", "Keycap Set", "MT3 Olivia Base Kit (MT3 Profile)", "MT3", "mid", 110),
        ("Drop", "Keycap Set", "MT3 Bento Base Kit (MT3 Profile)", "MT3", "mid", 100),
        ("Signature Plastics", "Keycap Set", "SA Botanical Base Kit (SA Profile)", "SA", "mid", 170),
        ("Keyreative", "Keycap Set", "KAT Mizu Alpha Kit (KAT Profile)", "KAT", "mid", 130),
        ("Signature Plastics", "Keycap Set", "DSA Olivia Base Kit (DSA Profile)", "DSA", "mid", 120),

        # ── Additional RAMA Metal Variants ────────────────────────────
        ("RAMA", "Artisan", "RAMA x GMK Frost Witch Stainless Steel", "Cherry R1", "high", 170),
        ("RAMA", "Artisan", "RAMA x GMK Cafe Brass Latte", "Cherry R1", "mid", 100),
        ("RAMA", "Artisan", "RAMA x GMK Taro Aluminum Purple", "Cherry R1", "mid", 90),
        ("RAMA", "Artisan", "RAMA x GMK Nord Brass PVD", "Cherry R1", "mid", 110),
        ("RAMA", "Artisan", "RAMA x GMK Red Samurai Brass Torii", "Cherry R1", "mid", 130),

        # ── Additional Thermal / GID / Material Variants ──────────────
        ("Jelly Key", "Artisan", "Zen Pond III Ochiba Ceramic Edition", "SA R1", "mid", 130),
        ("Phage Caps", "Artisan", "Clavus Glow-in-Dark Spectral Green", "Cherry R1", "mid", 115),
        ("Keyforge", "Artisan", "Shishi Thermal Shift Red-Gold", "Cherry R1", "high", 340),
        ("ETF (Nightcaps)", "Artisan", "Fugthulhu UV-Reactive Phantom Glow", "Cherry R1", "grail", 580),
    ]

    items = []
    for maker, keycap_type, name, profile, tier, price in variants:
        items.append({
            "maker": maker,
            "keycap_type": keycap_type,
            "name": name,
            "profile": profile,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return items


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

        # ══════════════════════════════════════════════════════════════
        # EXPANSION TO 700+ — 94 additional artisan keycaps & sets
        # ══════════════════════════════════════════════════════════════

        # ── Jelly Key — Additional (+8) ────────────────────────────────
        ("Jelly Key", "Artisan", "Zen Pond III Emerald Koi", "SA R1", "mid", 90),
        ("Jelly Key", "Artisan", "Zen Pond III Winter Frost", "SA R1", "mid", 95),
        ("Jelly Key", "Artisan", "Forbidden Realm Volcanic Gate", "SA R1", "mid", 110),
        ("Jelly Key", "Artisan", "Forbidden Realm Crystal Cavern", "SA R1", "mid", 105),
        ("Jelly Key", "Artisan", "Nature's Rage Lightning Storm", "SA R1", "mid", 100),
        ("Jelly Key", "Artisan", "Arcade Cabinet Street Fighter II", "SA R1", "mid", 95),
        ("Jelly Key", "Artisan", "Mid-Autumn Festival Lantern 2024", "SA R1", "mid", 100),

        # ── Dwarf Factory — Additional (+6) ────────────────────────────
        ("Dwarf Factory", "Artisan", "Gnarly Drakon Frost", "Cherry R1", "mid", 70),
        ("Dwarf Factory", "Artisan", "Gnarly Drakon Ember Gold", "Cherry R1", "mid", 75),
        ("Dwarf Factory", "Artisan", "The Flourish Lavender", "Cherry R1", "standard", 55),
        ("Dwarf Factory", "Artisan", "Anura Frog Emerald", "Cherry R1", "mid", 65),
        ("Dwarf Factory", "Artisan", "Terrarium Keycap Glacier", "Cherry R1", "mid", 80),
        ("Dwarf Factory", "Artisan", "Moondust Cosmos", "Cherry R1", "mid", 85),

        # ── Alpha Keycaps (+8) ─────────────────────────────────────────
        ("Alpha Keycaps", "Artisan", "Keypora Nebula Drift", "Cherry R4", "high", 350),
        ("Alpha Keycaps", "Artisan", "Keypora Sakura Storm", "Cherry R4", "high", 380),
        ("Alpha Keycaps", "Artisan", "Keypora Tidal Wave", "Cherry R4", "high", 320),
        ("Alpha Keycaps", "Artisan", "Salvador Phantom", "Cherry R4", "high", 280),
        ("Alpha Keycaps", "Artisan", "Salvador Inferno", "Cherry R4", "high", 300),
        ("Alpha Keycaps", "Artisan", "Matapora Arctic Fox", "Cherry R4", "high", 260),

        # ── CYSM — Additional (+6) ────────────────────────────────────
        ("CYSM", "Artisan", "Keyby Sunset Beach", "Cherry R4", "mid", 110),
        ("CYSM", "Artisan", "Ice Dragon Thunderstorm", "Cherry R4", "mid", 120),
        ("CYSM", "Artisan", "Boba Strawberry", "Cherry R4", "mid", 90),
        ("CYSM", "Artisan", "Boo Matcha Latte", "Cherry R4", "mid", 85),

        # ── Artkey Universe — Additional (+6) ─────────────────────────
        ("Artkey", "Artisan", "Sirius Midnight Void", "Cherry R4", "high", 230),
        ("Artkey", "Artisan", "Bull V2 Inferno Red", "Cherry R4", "high", 255),
        ("Artkey", "Artisan", "Exmoor Twilight", "Cherry R4", "mid", 170),
        ("Artkey", "Artisan", "Skelekrew Crimson", "Cherry R4", "mid", 185),
        ("Artkey", "Artisan", "Sirius Arctic Frost", "Cherry R4", "high", 240),
        ("Artkey", "Artisan", "Bull V2 Deep Sea Leviathan", "Cherry R4", "high", 270),

        # ── Latrialum — Additional (+6) ───────────────────────────────
        ("Latrialum", "Artisan", "Royal Ethereal Bloom ESC", "Cherry R4", "high", 200),
        ("Latrialum", "Artisan", "Royal Midnight Empress ESC", "Cherry R4", "high", 210),
        ("Latrialum", "Artisan", "Thermal Celestial FN Row", "Cherry R4", "high", 190),
        ("Latrialum", "Artisan", "Thermal Aurora Borealis FN Row", "Cherry R4", "high", 195),
        ("Latrialum", "Artisan", "Royal Void Walker ESC+FN Set", "Cherry R4", "grail", 420),
        ("Latrialum", "Artisan", "Thermal Ocean Depths FN Row", "Cherry R4", "high", 185),

        # ── S-Craft Pokemon (+8) ──────────────────────────────────────
        ("S-Craft", "Artisan", "Pikachu Pokemon Keycap", "Cherry R4", "mid", 80),
        ("S-Craft", "Artisan", "Eevee Pokemon Keycap", "Cherry R4", "mid", 85),
        ("S-Craft", "Artisan", "Gengar Pokemon Keycap", "Cherry R4", "mid", 90),
        ("S-Craft", "Artisan", "Bulbasaur Pokemon Keycap", "Cherry R4", "mid", 80),
        ("S-Craft", "Artisan", "Charmander Pokemon Keycap", "Cherry R4", "mid", 80),
        ("S-Craft", "Artisan", "Squirtle Pokemon Keycap", "Cherry R4", "mid", 80),
        ("S-Craft", "Artisan", "Snorlax Pokemon Keycap", "Cherry R4", "mid", 90),
        ("S-Craft", "Artisan", "Mewtwo Pokemon Keycap", "Cherry R4", "mid", 95),

        # ── GMK Sets — Laser, Botanical, Olivia, Bento (+10) ──────────
        ("GMK", "Keycap Set", "GMK Laser R2 Synthwave Base Kit", "Cherry", "mid", 180),
        ("GMK", "Keycap Set", "GMK Laser R2 Cyberdeck Kit", "Cherry", "mid", 120),
        ("GMK", "Keycap Set", "GMK Botanical R2 Novelties Kit", "Cherry", "mid", 90),
        ("GMK", "Keycap Set", "GMK Bento R2 Traditional Base Kit", "Cherry", "mid", 170),
        ("GMK", "Keycap Set", "GMK Bento R2 Revised Base Kit", "Cherry", "mid", 160),

        # ── GMK — Additional Premium Sets (+8) ────────────────────────
        ("GMK", "Keycap Set", "GMK Frost Witch R2 Base Kit", "Cherry", "high", 260),
        ("GMK", "Keycap Set", "GMK Dracula R2 Core Kit", "Cherry", "high", 240),
        ("GMK", "Keycap Set", "GMK Shoko R2 Base Kit", "Cherry", "mid", 170),
        ("GMK", "Keycap Set", "GMK Mizu R2 Base Kit", "Cherry", "high", 230),
        ("GMK", "Keycap Set", "GMK Striker 2 Base Kit", "Cherry", "mid", 165),

        # ── KAT/KAM Profiles (+8) ─────────────────────────────────────
        ("Keyreative", "Keycap Set", "KAT Milkshake Base Kit", "KAT", "mid", 130),
        ("Keyreative", "Keycap Set", "KAT Atlantis Base Kit", "KAT", "mid", 140),
        ("Keyreative", "Keycap Set", "KAT Refined Base Kit", "KAT", "mid", 120),
        ("Keyreative", "Keycap Set", "KAT Arctic Base Kit", "KAT", "mid", 125),
        ("Keyreative", "Keycap Set", "KAT Space Dust Base Kit", "KAT", "mid", 135),
        ("Keyreative", "Keycap Set", "KAM Superuser Base Kit", "KAM", "mid", 110),
        ("Keyreative", "Keycap Set", "KAM Wraith Base Kit", "KAM", "mid", 115),
        ("Keyreative", "Keycap Set", "KAT Napoleonic Base Kit", "KAT", "mid", 130),

        # ── GSK / Bro Caps / Deag / Other Premium Artisans (+10) ──────
        ("GSK", "Artisan", "Hogzilla Volcanic", "Cherry R4", "high", 300),
        ("GSK", "Artisan", "Hogzilla Frozen Tundra", "Cherry R4", "high", 280),
        ("Bro Caps", "Artisan", "BroBot Defender Class Mecha", "Cherry R4", "grail", 450),
        ("Bro Caps", "Artisan", "BroBot Corrupted Defender", "Cherry R4", "grail", 500),
        ("Deag (Death Caps)", "Artisan", "Cross Cap Spectral", "Cherry R4", "high", 220),
        ("Deag (Death Caps)", "Artisan", "Cross Cap Infernal", "Cherry R4", "high", 240),
        ("Glyco Keycaps", "Artisan", "Glob Strawberry Drip", "Cherry R1", "mid", 65),
        ("Glyco Keycaps", "Artisan", "Glob Blueberry Drip", "Cherry R1", "mid", 65),
        ("Rathcaps", "Artisan", "Potion Bottle Amethyst", "Cherry R1", "mid", 75),
        ("Rathcaps", "Artisan", "Potion Bottle Emerald", "Cherry R1", "mid", 75),

        # ── ePBT / Cherry Original Sets (+4) ──────────────────────────

        # ── Keyboard Builds (+6) ──────────────────────────────────────
        ("Custom Build", "Keyboard Build", "Keycult No. 2/65 TKL Polycarbonate", "N/A", "grail", 1200),
        ("Custom Build", "Keyboard Build", "TGR Jane V2 CE WKL Navy", "N/A", "grail", 2000),
        ("Custom Build", "Keyboard Build", "Geon F1-8X WKL Burgundy", "N/A", "grail", 800),
        ("Custom Build", "Keyboard Build", "ai03 Vega65 E-White", "N/A", "high", 400),
        ("Custom Build", "Keyboard Build", "Mode Envoy 65% Dark", "N/A", "mid", 200),
        ("Custom Build", "Keyboard Build", "Monokei x TGR Tomo Hotswap Silver", "N/A", "high", 350),

        # ── GMK Sets — Additional (+25) ─────────────────────────────────
        ("GMK", "Keycap Set", "GMK Striker R2 Base Kit", "Cherry", "mid", 170),
        ("GMK", "Keycap Set", "GMK 8008 Base Kit + Accent", "Cherry", "mid", 190),
        ("GMK", "Keycap Set", "GMK Metaverse R2 Base Kit", "Cherry", "high", 220),
        ("GMK", "Keycap Set", "GMK Bento R2 Base Kit", "Cherry", "mid", 175),
        ("GMK", "Keycap Set", "GMK Dracula Core Kit", "Cherry", "high", 240),
        ("GMK", "Keycap Set", "GMK Laser R2 Cyberdeck Base Kit", "Cherry", "mid", 160),
        ("GMK", "Keycap Set", "GMK Jamon R2 Base Kit", "Cherry", "mid", 155),
        ("GMK", "Keycap Set", "GMK Copper Base Kit", "Cherry", "mid", 165),
        ("GMK", "Keycap Set", "GMK Rudy Base Kit", "Cherry", "mid", 190),
        ("GMK", "Keycap Set", "GMK Noel Base Kit", "Cherry", "mid", 170),
        ("GMK", "Keycap Set", "GMK Cafe R2 Base Kit", "Cherry", "mid", 185),
        ("GMK", "Keycap Set", "GMK Oblivion V3 Regular Base", "Cherry", "mid", 175),
        ("GMK", "Keycap Set", "GMK Burgundy R3 Base Kit", "Cherry", "mid", 145),
        ("GMK", "Keycap Set", "GMK Apollo Base Kit", "Cherry", "mid", 185),
        ("GMK", "Keycap Set", "GMK Terra Base Kit", "Cherry", "mid", 170),
        ("GMK", "Keycap Set", "GMK Godspeed R2 Base Kit", "Cherry", "mid", 155),
        ("GMK", "Keycap Set", "GMK Space Cadet R2 Base Kit", "Cherry", "mid", 180),
        ("GMK", "Keycap Set", "GMK Camping R2 Base Kit", "Cherry", "mid", 165),
        ("GMK", "Keycap Set", "GMK Dualshot R2 Base Kit", "Cherry", "mid", 150),
        ("GMK", "Keycap Set", "GMK Taro R2 Base Kit", "Cherry", "mid", 175),

        # ── Artisan Keycaps — Additional (+20) ─────────────────────────
        ("Jelly Key", "Artisan", "Zen Pond IV Koi Sakura Pour", "SA R1", "mid", 100),
        ("Jelly Key", "Artisan", "Arcade Cabinets Retro Fighter 1u", "Cherry R1", "mid", 85),
        ("Jelly Key", "Artisan", "Constellation Series Orion 1u", "SA R1", "mid", 90),
        ("Dwarf Factory", "Artisan", "Gnarly Drakon Inferno Colorway", "Cherry R1", "mid", 70),
        ("Dwarf Factory", "Artisan", "Foodie Happy Bao 1u", "Cherry R1", "mid", 55),
        ("CYSM", "Artisan", "Keyby Aurora Borealis Colorway", "Cherry R1", "mid", 130),
        ("CYSM", "Artisan", "Boba Tea Taro Purple", "Cherry R1", "mid", 110),
        ("Bro Caps", "Artisan", "Broshido Ronin Jade Colorway", "Cherry R1", "high", 280),
        ("Bro Caps", "Artisan", "Erebus Crimson Blood Colorway", "Cherry R1", "high", 350),
        ("ETF (Nightcaps)", "Artisan", "Fugthulhu Poisoned Summer III", "Cherry R1", "grail", 500),
        ("ETF (Nightcaps)", "Artisan", "Smeg Spectral Moonlight", "Cherry R1", "high", 380),
        ("ETF (Nightcaps)", "Artisan", "Eggface v2 Hyperfuse Colorway", "Cherry R1", "high", 320),
        ("Latrialum", "Artisan", "Royal Beastlord Sacred Arrow", "Cherry R1", "grail", 600),
        ("Latrialum", "Artisan", "Empress Celestial Flame", "Cherry R1", "grail", 550),
        ("Alpha Keycaps", "Artisan", "Salvador Ocean Depths Colorway", "Cherry R1", "high", 250),
        ("Archetype", "Artisan", "Kolkrabba Midnight Frost", "Cherry R1", "mid", 120),
        ("Artkey", "Artisan", "Sirius V2 Starlight Colorway", "Cherry R1", "high", 200),
        ("Artkey", "Artisan", "Bull V2 Golden Emperor", "Cherry R1", "high", 280),
        ("Artkey", "Artisan", "Voidwalker Eclipse Colorway", "Cherry R1", "high", 220),
        ("S-Craft", "Artisan", "Pokemon Gengar Artisan Keycap", "Cherry R1", "mid", 100),

        # ── Keyboards — Additional (+20) ───────────────────────────────
        ("Custom Build", "Keyboard Build", "Mode Sonnet 65% Ocean Blue", "N/A", "high", 350),
        ("Custom Build", "Keyboard Build", "Mode Envoy 65% E-White Top", "N/A", "mid", 200),
        ("Custom Build", "Keyboard Build", "Keycult No.2 Rev.2 65% Black/Gold", "N/A", "grail", 1500),
        ("Custom Build", "Keyboard Build", "Keycult No.1 Rev.2 TKL Silver", "N/A", "grail", 1800),
        ("Custom Build", "Keyboard Build", "TGR Jane V2 CE WKL Red", "N/A", "grail", 2200),
        ("Custom Build", "Keyboard Build", "TGR Alice WKL E-White", "N/A", "grail", 1600),
        ("Custom Build", "Keyboard Build", "Satisfaction 75 R2 Deep Ocean Blue", "N/A", "grail", 900),
        ("Custom Build", "Keyboard Build", "Iron180 WKL Brass Weight E-White", "N/A", "grail", 800),
        ("Custom Build", "Keyboard Build", "Jelly Epoch 75% Ink Black", "N/A", "high", 400),
        ("Custom Build", "Keyboard Build", "Space65 R3 CyberVoyager Robocop", "N/A", "high", 350),
        ("Custom Build", "Keyboard Build", "Space80 Apollo Edition E-White", "N/A", "high", 380),
        ("Custom Build", "Keyboard Build", "Rama U80-A Seq2 Milk", "N/A", "high", 400),
        ("Custom Build", "Keyboard Build", "Rama Kara Moon", "N/A", "mid", 180),
        ("Custom Build", "Keyboard Build", "Think6.5 V2 2U Cream", "N/A", "high", 350),
        ("Custom Build", "Keyboard Build", "Matrix 2.0 WKL Navy", "N/A", "high", 380),
        ("Custom Build", "Keyboard Build", "Singa Jaguar TKL Polycarbonate", "N/A", "high", 300),
        ("Custom Build", "Keyboard Build", "ai03 Vega65 Navy Blue", "N/A", "high", 420),
        ("Custom Build", "Keyboard Build", "Monokei Standard 65% Forest Green", "N/A", "high", 350),
        ("Custom Build", "Keyboard Build", "Geonworks F1-8X WKL Cream", "N/A", "grail", 850),
        ("Custom Build", "Keyboard Build", "KBDFans Tiger80 Lilac", "N/A", "mid", 180),

        # ── Switches — Rare & Premium (+15) ────────────────────────────
        ("Cherry", "Switch", "Cherry MX Black Vintage (Desoldered, 90x)", "N/A", "high", 250),
        ("Drop", "Switch", "Holy Panda V2 (90x Pack)", "N/A", "mid", 80),
        ("Gateron", "Switch", "Gateron Ink Black V2 (90x)", "N/A", "mid", 55),
        ("Novelkeys", "Switch", "Novelkeys Cream V2 (90x)", "N/A", "standard", 45),
        ("Durock", "Switch", "Durock POM Linear (90x)", "N/A", "standard", 40),
        ("Gazzew", "Switch", "Boba U4T Tactile (90x)", "N/A", "mid", 55),
        ("JWK", "Switch", "Alpaca V2 Linear (90x)", "N/A", "mid", 50),
        ("C3 Equalz", "Switch", "Tangerine V2 62g Light (90x)", "N/A", "mid", 55),
        ("JWK", "Switch", "Lavender Linear (90x)", "N/A", "standard", 45),
        ("C3 Equalz", "Switch", "Banana Split V2 (90x)", "N/A", "mid", 50),
        ("SP Star", "Switch", "SP Star Meteor White (90x)", "N/A", "standard", 40),
        ("Novelkeys", "Switch", "Novelkeys Silk Olivia (90x)", "N/A", "mid", 60),
        ("Gateron", "Switch", "Gateron Oil King Linear (90x)", "N/A", "standard", 45),
        ("Cherry", "Switch", "Cherry MX Nixie Vintage (NOS, 90x)", "N/A", "grail", 800),
        ("KTT", "Switch", "KTT Rose Linear (90x)", "N/A", "standard", 30),

        # ── Desk Mats & Accessories (+15) ──────────────────────────────
        ("Novelkeys", "Deskmat", "Novelkeys Camping Deskmat (Dark)", "N/A", "standard", 30),
        ("GMK", "Deskmat", "GMK Olivia Deskmat (Light)", "N/A", "mid", 55),
        ("GMK", "Deskmat", "GMK Botanical Deskmat (Greenhouse)", "N/A", "mid", 50),
        ("GMK", "Deskmat", "GMK Bento Deskmat (Salmon)", "N/A", "mid", 45),
        ("GMK", "Deskmat", "GMK Mizu Deskmat (Great Wave)", "N/A", "mid", 60),
        ("Custom", "Cable", "Zap Cables Custom Aviator USB-C Olivia Theme", "N/A", "standard", 65),
        ("Custom", "Cable", "Space Cables Lemo USB-C Carbon Black", "N/A", "standard", 70),
        ("Custom", "Cable", "CruzCtrl Custom Coiled Cable Botanical Green", "N/A", "standard", 60),
        ("TX Keyboards", "Stabilizer", "TX AP Stabilizers WK Set (PCB Mount)", "N/A", "standard", 25),
        ("Durock", "Stabilizer", "Durock V2 Stabilizers Smokey Set", "N/A", "standard", 20),
        ("Various", "Switch", "Switch Tester 72-Key Mechanical Switch Sampler", "N/A", "standard", 35),
        ("Kelowna", "Plate", "FR4 Universal 65% Plate", "N/A", "standard", 20),
        ("StupidFish", "Plate", "StupidFish Plate Foam + PCB Foam Kit 65%", "N/A", "standard", 15),
        ("Gateron", "Switch", "Gateron Spring Swap Kit (60-80g, 10 weights)", "N/A", "standard", 25),
        ("Kailh", "Switch", "Lube Station 36-Switch Acrylic", "N/A", "standard", 18),

        # ── In-Stock / Modern Keycap Sets (+15) ───────────────────────
        ("ePBT", "Keycap Set", "ePBT Kavala Base Kit", "Cherry", "mid", 95),
        ("ePBT", "Keycap Set", "ePBT Grand Tour Base Kit", "Cherry", "mid", 100),
        ("ePBT", "Keycap Set", "ePBT Less But Better Base Kit", "Cherry", "mid", 90),
        ("Keyreative", "Keycap Set", "KAT Atlantis Base Kit", "KAT", "mid", 115),
        ("Keyreative", "Keycap Set", "KAT Refined Base Kit", "KAT", "mid", 110),
        ("Drop", "Keycap Set", "MT3 Susuwatari Base Kit", "MT3", "mid", 100),
        ("Drop", "Keycap Set", "MT3 Cyber Muted Base Kit", "MT3", "mid", 95),
        ("Drop", "Keycap Set", "MT3 Dasher Base Kit", "MT3", "mid", 105),
        ("Signature Plastics", "Keycap Set", "DSA Magic Girl Base Kit", "DSA", "mid", 130),
        ("NicePBT", "Keycap Set", "NicePBT Elderberry Base Kit", "Cherry", "standard", 55),
        ("NicePBT", "Keycap Set", "NicePBT Noel Base Kit", "Cherry", "standard", 50),
        ("NicePBT", "Keycap Set", "NicePBT Fuji Base Kit", "Cherry", "standard", 55),
        ("Osume", "Keycap Set", "Osume Tsukimi Dye-Sub PBT", "Cherry", "standard", 70),
        ("Osume", "Keycap Set", "Osume Sakura Dye-Sub PBT", "Cherry", "standard", 70),

        # ── Additional GMK & Premium Sets (+15) ────────────────────────
        ("GMK", "Keycap Set", "GMK WoB Katakana Base Kit", "Cherry", "mid", 140),
        ("GMK", "Keycap Set", "GMK BoW Hiragana Base Kit", "Cherry", "mid", 130),
        ("GMK", "Keycap Set", "GMK Frost Witch 2 Base Kit", "Cherry", "high", 280),
        ("GMK", "Keycap Set", "GMK Dots R2 Base Kit", "Cherry", "mid", 170),
        ("GMK", "Keycap Set", "GMK Red Samurai R2 Base Kit", "Cherry", "mid", 165),
        ("GMK", "Keycap Set", "GMK Darling R2 Base Kit", "Cherry", "mid", 190),
        ("GMK", "Keycap Set", "GMK Hennessey Base Kit", "Cherry", "mid", 175),
        ("GMK", "Keycap Set", "GMK Nord Base Kit", "Cherry", "mid", 155),
        ("GMK", "Keycap Set", "GMK Hallyu Base Kit", "Cherry", "mid", 160),
        ("GMK", "Keycap Set", "GMK Kaiju Base Kit", "Cherry", "mid", 170),
        ("Cherry Original", "Keycap Set", "Cherry Hyperion Base Kit", "Cherry", "mid", 120),
        ("Cherry Original", "Keycap Set", "Cherry Sagittarius Base Kit", "Cherry", "mid", 115),
        ("Cherry Original", "Keycap Set", "Cherry Leviathan Base Kit", "Cherry", "mid", 125),
        ("Signature Plastics", "Keycap Set", "SA Bliss R3 Base Kit", "SA", "mid", 160),
        ("Signature Plastics", "Keycap Set", "SA Godspeed R2 Base Kit", "SA", "mid", 145),

        # ── Additional Artisan Makers (+15) ────────────────────────────
        ("S-Craft", "Artisan", "Pokemon Pikachu Artisan Keycap", "Cherry R1", "mid", 90),
        ("S-Craft", "Artisan", "Pokemon Eevee Artisan Keycap", "Cherry R1", "mid", 90),
        ("S-Craft", "Artisan", "Pokemon Bulbasaur Artisan Keycap", "Cherry R1", "mid", 85),
        ("S-Craft", "Artisan", "Pokemon Charmander Artisan Keycap", "Cherry R1", "mid", 85),
        ("Jelly Key", "Artisan", "Arcade Cabinet Pac-Man Tribute 1u", "Cherry R1", "mid", 80),
        ("Jelly Key", "Artisan", "Born of Forest Owl 1u", "SA R1", "mid", 95),
        ("Dwarf Factory", "Artisan", "The Lighthouse Storm 1u", "Cherry R1", "mid", 65),
        ("Dwarf Factory", "Artisan", "Gnarly Drakon Frost Colorway", "Cherry R1", "mid", 70),
        ("CYSM", "Artisan", "Keyby Sunset Beach Colorway", "Cherry R1", "mid", 125),
        ("Archetype", "Artisan", "Kolkrabba Deep Sea Colorway", "Cherry R1", "mid", 115),
        ("Glyco Keycaps", "Artisan", "Glob Matcha Drip", "Cherry R1", "mid", 65),
        ("Hot Keys Project", "Artisan", "Specter Cross Obsidian", "Cherry R1", "mid", 55),
        ("GSK", "Artisan", "Hogzilla Forest Fire", "Cherry R1", "high", 180),
        ("Systematik Kaps", "Artisan", "Cheshire Cat Grinning Purple", "Cherry R1", "mid", 95),
        ("Lividity", "Artisan", "Moses Dark Ritual", "Cherry R1", "mid", 85),

        # ── Additional Keyboards & Misc (+7) ──────────────────────────
        ("Custom Build", "Keyboard Build", "Owlab Spring 65% E-White", "N/A", "high", 380),
        ("Custom Build", "Keyboard Build", "Parallel Sequence 65% Navy", "N/A", "high", 350),
        ("Custom Build", "Keyboard Build", "Frog Mini TKL F13 Silver", "N/A", "high", 400),
        ("RAMA", "Artisan", "RAMA x GMK Dracula Bat Brass", "Cherry R1", "mid", 120),
        ("RAMA", "Artisan", "RAMA x GMK Bento Salmon PVD", "Cherry R1", "mid", 105),
        ("Drop", "Keycap Set", "MT3 Extended 2048 Base Kit", "MT3", "mid", 110),
        ("NicePBT", "Keycap Set", "NicePBT Lantern Base Kit", "Cherry", "standard", 55),

        # ── KAT Profile Sets — Group Buy ─────────────────────────────────
        ("Keyreative", "Keycap Set", "KAT Milkshake Base Kit", "KAT", "mid", 120),
        ("Keyreative", "Keycap Set", "KAT Milkshake Fruits Kit", "KAT", "mid", 80),
        ("Keyreative", "Keycap Set", "KAT Atlantis Base Kit", "KAT", "mid", 110),
        ("Keyreative", "Keycap Set", "KAT Refined Base Kit", "KAT", "mid", 100),
        ("Keyreative", "Keycap Set", "KAT Arctic Base Kit", "KAT", "mid", 105),
        ("Keyreative", "Keycap Set", "KAT Space Dust Base Kit", "KAT", "mid", 95),
        ("Keyreative", "Keycap Set", "KAT Napoleonic Base Kit", "KAT", "mid", 100),
        ("Keyreative", "Keycap Set", "KAT Oasis Base Kit", "KAT", "mid", 90),

        # ── DSA Profile Sets ─────────────────────────────────────────────
        ("Signature Plastics", "Keycap Set", "DSA Magic Girl Base Kit", "DSA", "mid", 110),
        ("Signature Plastics", "Keycap Set", "DSA Arcane Base Kit", "DSA", "mid", 95),
        ("Signature Plastics", "Keycap Set", "DSA Hana Base Kit", "DSA", "mid", 100),
        ("Signature Plastics", "Keycap Set", "DSA Scientific Base Kit", "DSA", "mid", 90),

        # ── SA Profile Sets ──────────────────────────────────────────────
        ("Signature Plastics", "Keycap Set", "SA Bliss Base Kit (R2)", "SA", "high", 200),
        ("Signature Plastics", "Keycap Set", "SA Dreameater Base Kit", "SA", "high", 180),
        ("Signature Plastics", "Keycap Set", "SA Godspeed Base Kit (R2)", "SA", "mid", 150),
        ("Signature Plastics", "Keycap Set", "SA Mizu Base Kit", "SA", "mid", 160),
        ("Signature Plastics", "Keycap Set", "SA Vilebloom Base Kit", "SA", "mid", 140),
        ("Signature Plastics", "Keycap Set", "SA Oblivion Base Kit (R2)", "SA", "mid", 130),

        # ── Budget PBT Sets — Akko, NicePBT ─────────────────────────────
        ("Akko", "Keycap Set", "Akko Matcha Green PBT Keycap Set", "Cherry", "standard", 35),
        ("Akko", "Keycap Set", "Akko Midnight PBT Keycap Set", "Cherry", "standard", 32),
        ("Akko", "Keycap Set", "Akko Neon PBT Keycap Set", "Cherry", "standard", 35),
        ("Akko", "Keycap Set", "Akko Black & Gold PBT Keycap Set", "Cherry", "standard", 38),
        ("Akko", "Keycap Set", "Akko Clear Translucent PBT Set", "Cherry", "standard", 30),
        ("Akko", "Keycap Set", "Akko Sakura PBT Keycap Set", "Cherry", "standard", 35),
        ("NicePBT", "Keycap Set", "NicePBT Fuji Base Kit", "Cherry", "standard", 58),
        ("NicePBT", "Keycap Set", "NicePBT Retro Cyrillic Base Kit", "Cherry", "standard", 60),

        # ── Keyboard PCBs and Plates ─────────────────────────────────────
        ("ai03", "Plate", "Andromeda FR4 Plate", "N/A", "standard", 30),
        ("ai03", "Plate", "Andromeda PC Plate", "N/A", "standard", 35),
        ("ai03", "Plate", "Andromeda Aluminum Plate", "N/A", "standard", 40),
        ("Hiney", "Plate", "h87a PCB (TKL)", "N/A", "standard", 55),
        ("Hiney", "Plate", "h60 PCB (60%)", "N/A", "standard", 45),
        ("wilba.tech", "Plate", "WT60-D PCB (Hotswap)", "N/A", "standard", 50),
        ("wilba.tech", "Plate", "WT80-A PCB (TKL Hotswap)", "N/A", "standard", 60),

        # ── Stabilizers and Modding Supplies ─────────────────────────────
        ("Durock", "Stabilizer", "Durock V2 Screw-In Stabilizers (Clear, 4x2u + 1x6.25u)", "N/A", "standard", 18),
        ("Durock", "Stabilizer", "Durock V2 Screw-In Stabilizers (Smoky, 4x2u + 1x6.25u)", "N/A", "standard", 20),
        ("TX Keyboards", "Stabilizer", "TX AP Stabilizers Rev. 4 (Full Set)", "N/A", "standard", 22),
        ("C3 Equalz", "Stabilizer", "C3 Equalz V3 Screw-In Stabilizers (Full Set)", "N/A", "standard", 20),
        ("Gateron", "Stabilizer", "Gateron Ink V2 Screw-In Stabilizers", "N/A", "standard", 16),
        ("Krytox", "Stabilizer", "Krytox GPL 205g0 Lube (3ml)", "N/A", "standard", 12),
        ("Kelowna", "Stabilizer", "Kelowna Stab Pads (Full Kit)", "N/A", "standard", 8),

        # ── Vintage Keyboards ────────────────────────────────────────────
        ("IBM", "Keyboard Build", "IBM Model M (1986-1991, Buckling Spring)", "N/A", "high", 200),
        ("IBM", "Keyboard Build", "IBM Model F XT (1981, Capacitive Buckling Spring)", "N/A", "grail", 500),
        ("IBM", "Keyboard Build", "IBM Model F AT (1984, Capacitive Buckling Spring)", "N/A", "grail", 450),
        ("IBM", "Keyboard Build", "IBM Model M SSK (Space Saving, Buckling Spring)", "N/A", "grail", 400),
        ("Apple", "Keyboard Build", "Apple Extended Keyboard II (Alps Cream/Orange)", "N/A", "high", 250),
        ("Apple", "Keyboard Build", "Apple Extended Keyboard I (Alps SKCM Orange)", "N/A", "high", 300),
        ("Unicomp", "Keyboard Build", "Unicomp New Model M (Reissue, Buckling Spring)", "N/A", "mid", 110),
        ("IBM", "Keyboard Build", "IBM Pingmaster (Rare Terminal Keyboard)", "N/A", "grail", 600),
        ("Zenith", "Keyboard Build", "Zenith Z-150 (Green Alps)", "N/A", "high", 200),
        ("Cherry", "Keyboard Build", "Cherry G80-3000 (Vintage MX Black, 1990s)", "N/A", "mid", 150),
        ("Topre", "Keyboard Build", "Topre Realforce 87U (55g, Ivory)", "N/A", "high", 250),
        ("Topre", "Keyboard Build", "Topre HHKB Pro 2 (Black, PFU Limited)", "N/A", "high", 280),

        # ── More GMK Sets ─────────────────────────────────────────────────
        ("GMK", "Keycap Set", "GMK Hammerhead Base Kit", "Cherry", "mid", 160),
        ("GMK", "Keycap Set", "GMK Noel Base Kit", "Cherry", "mid", 180),
        ("GMK", "Keycap Set", "GMK Peach Blossom Base Kit", "Cherry", "mid", 150),
        ("GMK", "Keycap Set", "GMK Civilizations Base Kit", "Cherry", "mid", 170),
        ("GMK", "Keycap Set", "GMK Umbra Base Kit", "Cherry", "mid", 160),
        ("GMK", "Keycap Set", "GMK Yuru Base Kit", "Cherry", "mid", 180),
        ("GMK", "Keycap Set", "GMK Grand Prix Base Kit", "Cherry", "mid", 150),
        ("GMK", "Keycap Set", "GMK Retrocast Base Kit", "Cherry", "mid", 140),
        ("GMK", "Keycap Set", "GMK Shoko Base Kit", "Cherry", "mid", 170),
        ("GMK", "Keycap Set", "GMK Bingsu Base Kit", "Cherry", "mid", 160),
        ("GMK", "Keycap Set", "GMK Cafe Base Kit", "Cherry", "mid", 180),
        ("GMK", "Keycap Set", "GMK Taro Base Kit (R2)", "Cherry", "mid", 140),
        ("GMK", "Keycap Set", "GMK Apollo Base Kit", "Cherry", "mid", 150),
        ("GMK", "Keycap Set", "GMK Pink on Navy Base Kit", "Cherry", "mid", 130),

        # ── More ePBT / Cherry Original Sets ─────────────────────────────
        ("ePBT", "Keycap Set", "ePBT Extended 2048 Base Kit", "Cherry", "mid", 90),
        ("ePBT", "Keycap Set", "ePBT Origami Base Kit", "Cherry", "mid", 85),
        ("ePBT", "Keycap Set", "ePBT Grand Tour Base Kit", "Cherry", "mid", 95),
        ("ePBT", "Keycap Set", "ePBT Less But Better Base Kit", "Cherry", "mid", 80),
        ("Cherry", "Keycap Set", "Cherry Hyperion Base Kit", "Cherry", "mid", 120),
        ("Cherry", "Keycap Set", "Cherry Sagittarius Base Kit", "Cherry", "mid", 110),
        ("Cherry", "Keycap Set", "Cherry Leviathan Base Kit", "Cherry", "mid", 115),

        # ── More Budget Options & Accessories ─────────────────────────────
        ("Akko", "Keycap Set", "Akko Wave Ocean PBT Double-Shot Set", "Cherry", "standard", 32),
        ("Akko", "Keycap Set", "Akko Psittacus PBT Double-Shot Set", "Cherry", "standard", 35),
        ("Akko", "Keycap Set", "Akko 9009 Retro PBT Double-Shot Set", "Cherry", "standard", 30),
        ("KBDfans", "Keycap Set", "KBDfans NP PBT Keycap Set (Blank White)", "NP", "standard", 35),
        ("KBDfans", "Keycap Set", "KBDfans Cherry PBT Black on White Set", "Cherry", "standard", 40),
        ("Drop", "Keycap Set", "MT3 Susuwatari Base Kit (R2)", "MT3", "mid", 100),
        ("Drop", "Keycap Set", "MT3 Cyber Base Kit", "MT3", "mid", 95),
        ("Drop", "Keycap Set", "MT3 Skiidata Base Kit", "MT3", "mid", 105),
        ("Custom Build", "Keyboard Build", "Keychron Q1 Max (Fully Built, Gateron)", "N/A", "mid", 200),
        ("Custom Build", "Keyboard Build", "Keychron Q2 Max (Fully Built, Gateron)", "N/A", "mid", 190),
        ("Custom Build", "Keyboard Build", "Keychron V1 Max (Budget, Pre-Built)", "N/A", "standard", 80),

        # ── Switches (Collectible) ────────────────────────────────────────
        ("Cherry", "Switch", "Cherry MX Black Hyperglide (90 Pack)", "N/A", "standard", 40),
        ("Cherry", "Switch", "Cherry MX Clear (Tactile, 90 Pack)", "N/A", "standard", 45),
        ("Gateron", "Switch", "Gateron Oil King (Linear, 90 Pack)", "N/A", "standard", 35),
        ("Gateron", "Switch", "Gateron CJ (Linear, 90 Pack)", "N/A", "standard", 40),
        ("JWK", "Switch", "JWK Alpaca V2 (Linear, 90 Pack)", "N/A", "standard", 45),
        ("JWK", "Switch", "JWK Durock POM (Linear, 90 Pack)", "N/A", "standard", 38),
        ("TTC", "Switch", "TTC Gold Pink V2 (Linear, 90 Pack)", "N/A", "standard", 30),
        ("SP-Star", "Switch", "SP-Star Meteor Orange (Tactile, 90 Pack)", "N/A", "standard", 35),

        # ── More Artisan Makers ───────────────────────────────────────────
        ("Bowbie Keycaps", "Artisan", "Bowbie Keycaps Peach Cat", "Cherry R4", "mid", 70),
        ("Bowbie Keycaps", "Artisan", "Bowbie Keycaps Strawberry Bunny", "Cherry R4", "mid", 75),
        ("Bowbie Keycaps", "Artisan", "Bowbie Keycaps Blueberry Hamster", "Cherry R4", "mid", 70),
        ("T-Lab Faunacaps", "Artisan", "T-Lab Faunacaps Kitsune Spirit", "Cherry R4", "mid", 90),
        ("T-Lab Faunacaps", "Artisan", "T-Lab Faunacaps Tanuki Autumn", "Cherry R4", "mid", 85),
        ("Rathcaps", "Artisan", "Rathcaps Keyriboh Blood Moon", "Cherry R1", "high", 200),
        ("Rathcaps", "Artisan", "Rathcaps Keyriboh Frozen Tundra", "Cherry R1", "high", 190),
        ("Phage Caps", "Artisan", "Phage Caps Toothy Nebula", "Cherry R1", "mid", 85),
        ("Phage Caps", "Artisan", "Phage Caps Toothy Crimson", "Cherry R1", "mid", 80),
        ("Sludgekidd", "Artisan", "Sludgekidd Bheezleboi Toxic Waste", "Cherry R1", "mid", 95),
        ("Sludgekidd", "Artisan", "Sludgekidd Bheezleboi Radiation", "Cherry R1", "mid", 90),
        ("Sludgekidd", "Artisan", "Sludgekidd Goopi Bubblegum", "Cherry R1", "mid", 80),
        ("Archetype", "Artisan", "Archetype Kolkrabba Abyssal", "Cherry R1", "mid", 110),
        ("Archetype", "Artisan", "Archetype Kolkrabba Volcanic", "Cherry R1", "mid", 115),

        # ── More Keyboard Builds ──────────────────────────────────────────
        ("Custom Build", "Keyboard Build", "Mode Sonnet 65% (E-White)", "N/A", "high", 350),
        ("Custom Build", "Keyboard Build", "Mode Envoy 60% (Black Anodized)", "N/A", "high", 300),
        ("Custom Build", "Keyboard Build", "Monsgeek M1 (Pre-Built, Akko Silver)", "N/A", "mid", 100),
        ("Custom Build", "Keyboard Build", "QK65 (Owlab, E-White, Hotswap)", "N/A", "high", 280),
        ("Custom Build", "Keyboard Build", "GMMK Pro (Glorious, Pre-Built)", "N/A", "mid", 170),
        ("Custom Build", "Keyboard Build", "Zoom65 V3 (Meletrix, Navy)", "N/A", "mid", 160),

        # ── Deskmats ─────────────────────────────────────────────────────
        ("NovelKeys", "Deskmat", "NovelKeys Cherry Blossom Deskmat", "N/A", "standard", 20),
        ("NovelKeys", "Deskmat", "NovelKeys Randomfrankp Collab Deskmat", "N/A", "standard", 22),
        ("Omnitype", "Deskmat", "Omnitype GMK Botanical Deskmat", "N/A", "standard", 25),
        ("Omnitype", "Deskmat", "Omnitype GMK Laser Deskmat", "N/A", "standard", 25),
        ("Dixie Mech", "Deskmat", "Dixie Mech Godspeed Deskmat (Dark)", "N/A", "standard", 25),
        ("Drop", "Deskmat", "Drop Lord of the Rings Deskmat", "N/A", "standard", 30),

        # ── Cables ────────────────────────────────────────────────────────
        ("Zap Cables", "Cable", "Zap Cables Coiled USB-C (Laser Theme)", "N/A", "standard", 50),
        ("Zap Cables", "Cable", "Zap Cables Coiled USB-C (Olivia Theme)", "N/A", "standard", 55),
        ("Space Cables", "Cable", "Space Cables Coiled USB-C (Botanical Theme)", "N/A", "standard", 55),
        ("Summit Cables", "Cable", "Summit Cables Coiled USB-C (Night Runner)", "N/A", "standard", 50),
        ("Custom Cables", "Cable", "Custom Lemo-Style Coiled Cable (GMK Bento)", "N/A", "mid", 80),
        ("Custom Cables", "Cable", "Custom Lemo-Style Coiled Cable (GMK Dracula)", "N/A", "mid", 80),

        # ── More Switches ────────────────────────────────────────────────
        ("Kailh", "Switch", "Kailh Box Jade (Clicky, 90 Pack)", "N/A", "standard", 30),
        ("Kailh", "Switch", "Kailh Box Royal (Tactile, 90 Pack)", "N/A", "standard", 28),
        ("Gateron", "Switch", "Gateron Ink V2 Black (Linear, 90 Pack)", "N/A", "standard", 42),
        ("Gateron", "Switch", "Gateron Milky Yellow Pro (Linear, 90 Pack)", "N/A", "standard", 22),
        ("Durock", "Switch", "Durock T1 Shrimp (Tactile, 90 Pack)", "N/A", "standard", 40),
        ("Durock", "Switch", "Durock L7 Smoky (Linear, 90 Pack)", "N/A", "standard", 38),
        ("JWK", "Switch", "JWK H1 (Linear, 90 Pack)", "N/A", "standard", 45),

        # ── Final items ───────────────────────────────────────────────────
        ("Novelkeys", "Switch", "Novelkeys Cream (Linear, 90 Pack)", "N/A", "standard", 50),
        ("Novelkeys", "Switch", "Novelkeys Blueberry (Tactile, 90 Pack)", "N/A", "standard", 45),
        ("Tecsee", "Switch", "Tecsee Purple Panda (Tactile, 90 Pack)", "N/A", "standard", 28),
        ("Tecsee", "Switch", "Tecsee Ice Candy (Linear, 90 Pack)", "N/A", "standard", 30),
        ("Wuque Studio", "Keyboard Build", "Wuque Studio Mammoth 75 (E-White)", "N/A", "high", 350),

        # ── GMK Sets (Most Searched) ─────────────────────────────────────
        ("GMK", "Keycap Set", "GMK Olivia++ Light Base Kit", "Cherry", "high", 200),
        ("GMK", "Keycap Set", "GMK Olivia++ Dark Base Kit", "Cherry", "high", 220),
        ("GMK", "Keycap Set", "GMK Botanical 2 Base Kit", "Cherry", "high", 180),
        ("GMK", "Keycap Set", "GMK Botanical 2 Novelties Kit", "Cherry", "mid", 80),
        ("GMK", "Keycap Set", "GMK Striker 2 Base Kit", "Cherry", "high", 170),
        ("GMK", "Keycap Set", "GMK Mizu 2 Base Kit", "Cherry", "high", 190),
        ("GMK", "Keycap Set", "GMK Mizu 2 Novelties Kit", "Cherry", "mid", 85),
        ("GMK", "Keycap Set", "GMK Bento R2 Base Kit", "Cherry", "high", 160),
        ("GMK", "Keycap Set", "GMK Bento R2 Salmon Novelties", "Cherry", "mid", 75),
        ("GMK", "Keycap Set", "GMK Dracula V2 Core Kit", "Cherry", "high", 175),
        ("GMK", "Keycap Set", "GMK Dracula V2 ERR! Kit", "Cherry", "mid", 90),
        ("GMK", "Keycap Set", "GMK Dracula V2 Nightmode Kit", "Cherry", "mid", 85),
        ("GMK", "Keycap Set", "GMK Jamon R2 Base Kit", "Cherry", "mid", 150),
        ("GMK", "Keycap Set", "GMK Oblivion V2 Monochrome Base", "Cherry", "high", 180),
        ("GMK", "Keycap Set", "GMK Oblivion V2 Regular Base", "Cherry", "high", 170),
        ("GMK", "Keycap Set", "GMK Oblivion V2 Git Base", "Cherry", "high", 175),
        ("GMK", "Keycap Set", "GMK Frost Witch 2 Base Kit", "Cherry", "grail", 350),
        ("GMK", "Keycap Set", "GMK Noel Base Kit", "Cherry", "high", 200),
        ("GMK", "Keycap Set", "GMK Tuzi Base Kit", "Cherry", "high", 160),
        ("GMK", "Keycap Set", "GMK Honor Base Kit", "Cherry", "mid", 140),
        ("GMK", "Keycap Set", "GMK Apollo Base Kit", "Cherry", "mid", 145),
        ("GMK", "Keycap Set", "GMK Hallyu Base Kit", "Cherry", "mid", 150),
        ("GMK", "Keycap Set", "GMK Rouge Base Kit", "Cherry", "mid", 135),
        ("GMK", "Keycap Set", "GMK Posh Base Kit", "Cherry", "mid", 140),

        # ── Artisan Keycaps by Maker (Most Searched) ─────────────────────
        ("Jelly Key", "Artisan", "Jelly Key Zen Pond IV Koi Autumn Pour", "SA R1", "mid", 100),
        ("Jelly Key", "Artisan", "Jelly Key Zen Pond IV Koi Spring Pour", "SA R1", "mid", 100),
        ("Jelly Key", "Artisan", "Jelly Key Born of Forest Dragon's Eye", "SA R1", "high", 120),
        ("Jelly Key", "Artisan", "Jelly Key Ethereal Realm Celestial Gate", "SA R1", "high", 130),
        ("Jelly Key", "Artisan", "Jelly Key Arcade Cabinet Retro Series", "SA R1", "mid", 95),
        ("Dwarf Factory", "Artisan", "Dwarf Factory Gnarly Drakon Volcanic Red", "SA R1", "high", 120),
        ("Dwarf Factory", "Artisan", "Dwarf Factory Gnarly Drakon Frost Blue", "SA R1", "high", 120),
        ("Dwarf Factory", "Artisan", "Dwarf Factory Gnarly Drakon Emerald", "SA R1", "high", 115),
        ("Dwarf Factory", "Artisan", "Dwarf Factory Terrarium Coral Reef", "SA R1", "mid", 85),
        ("Dwarf Factory", "Artisan", "Dwarf Factory The Fluorescence Deep Sea", "SA R1", "mid", 90),
        ("Artkey", "Artisan", "Artkey Sirius Crimson", "Cherry R1", "high", 180),
        ("Artkey", "Artisan", "Artkey Sirius Glacier", "Cherry R1", "high", 175),
        ("Artkey", "Artisan", "Artkey Bull V2 Inferno", "Cherry R1", "grail", 300),
        ("Artkey", "Artisan", "Artkey Bull V2 Oblivion", "Cherry R1", "grail", 280),
        ("Artkey", "Artisan", "Artkey Voidwalker Nebula", "Cherry R1", "high", 200),
        ("Latrialum", "Artisan", "Latrialum Thermal Shift — Crimson to Gold", "Cherry R1", "grail", 400),
        ("Latrialum", "Artisan", "Latrialum Thermal Shift — Ice to Violet", "Cherry R1", "grail", 380),
        ("Latrialum", "Artisan", "Latrialum Royal Beastlord Gold", "Cherry R1", "grail", 350),
        ("Latrialum", "Artisan", "Latrialum Empress Celestial", "Cherry R1", "high", 250),
        ("Bro Caps", "Artisan", "Bro Caps Reaper V2 Starcluster", "Cherry R1", "grail", 450),
        ("Bro Caps", "Artisan", "Bro Caps Broshido Samurai Red", "Cherry R1", "high", 200),
        ("GAF", "Artisan", "GAF Trash Panda Nightlife", "Cherry R1", "grail", 500),
        ("GAF", "Artisan", "GAF Trash Panda Dignity Dolores", "Cherry R1", "grail", 600),
        ("ETF (Nightcaps)", "Artisan", "ETF Fugthulhu Spalted Nematode", "Cherry R1", "grail", 400),
        ("ETF (Nightcaps)", "Artisan", "ETF Smegface Submarine", "Cherry R1", "high", 250),

        # ── Keyboards (Most Searched Custom Boards) ──────────────────────
        ("Keycult", "Keyboard Build", "Keycult No. 2/65 Black/Gold", "N/A", "grail", 2500),
        ("Keycult", "Keyboard Build", "Keycult No. 2/65 Silver/Red", "N/A", "grail", 2200),
        ("Keycult", "Keyboard Build", "Keycult No. 1/65 Rev. 2 Black", "N/A", "grail", 2000),
        ("Satisfaction75", "Keyboard Build", "Satisfaction75 R2 Deep Ocean Blue", "N/A", "grail", 1200),
        ("Satisfaction75", "Keyboard Build", "Satisfaction75 R2 Cloud White", "N/A", "grail", 1100),
        ("ai03", "Keyboard Build", "ai03 Vega R2 E-White", "N/A", "high", 450),
        ("ai03", "Keyboard Build", "ai03 Vega R2 Navy", "N/A", "high", 480),
        ("ai03", "Keyboard Build", "ai03 Andromeda E-White", "N/A", "grail", 800),
        ("Mode", "Keyboard Build", "Mode Sonnet Silver", "N/A", "high", 350),
        ("Mode", "Keyboard Build", "Mode Envoy Rose Gold", "N/A", "high", 380),
        ("Mode", "Keyboard Build", "Mode Eighty E-White", "N/A", "high", 400),
        ("TGR", "Keyboard Build", "TGR Jane V2 CE Navy", "N/A", "grail", 3000),
        ("TGR", "Keyboard Build", "TGR 910 RE Silver", "N/A", "grail", 1500),
        ("Geon", "Keyboard Build", "Geon F1-8X V2 E-White", "N/A", "high", 500),
        ("Geon", "Keyboard Build", "Geon F2-84 Navy", "N/A", "high", 480),
        ("Lin Works", "Keyboard Build", "Lin Works Whale 75 Silver", "N/A", "high", 450),
        ("Singa", "Keyboard Build", "Singa Jaguar65 Forest Green", "N/A", "high", 400),

        # ── Vintage Keyboards ────────────────────────────────────────────
        ("Cherry", "Vintage Keyboard", "Cherry G80-1000 HAD (Vintage Blacks)", "N/A", "grail", 600),
        ("Cherry", "Vintage Keyboard", "Cherry G80-3000 SAU (Nixdorf Blacks)", "N/A", "grail", 500),
        ("Cherry", "Vintage Keyboard", "Cherry G81-3000 SAU (Dyesub Caps)", "N/A", "high", 350),
        ("IBM", "Vintage Keyboard", "IBM Model F AT (1985)", "N/A", "grail", 800),
        ("IBM", "Vintage Keyboard", "IBM Model F XT (1981)", "N/A", "grail", 700),
        ("IBM", "Vintage Keyboard", "IBM Model M Bolt Mod (1989)", "N/A", "high", 250),
        ("Apple", "Vintage Keyboard", "Apple M0110 (1984 Original)", "N/A", "high", 400),
        ("Apple", "Vintage Keyboard", "Apple Extended Keyboard II (AEK II Alps)", "N/A", "high", 300),
        ("SKCM", "Vintage Switch", "Alps SKCM Blue Switches (100 Pack, Desoldered)", "N/A", "high", 200),
        ("SKCM", "Vintage Switch", "Alps SKCM Orange Switches (100 Pack, NOS)", "N/A", "grail", 350),

        # ── RAMA Collaboration Keycaps ───────────────────────────────────
        ("RAMA", "Artisan", "RAMA x GMK Olivia Rose Gold Enter", "Cherry", "high", 120),
        ("RAMA", "Artisan", "RAMA x GMK Botanical Leaf Brass", "Cherry", "high", 110),
        ("RAMA", "Artisan", "RAMA x GMK Mizu Wave Brass", "Cherry", "high", 115),
        ("RAMA", "Artisan", "RAMA x GMK Bento Salmon Brass", "Cherry", "high", 105),
        ("RAMA", "Artisan", "RAMA x GMK Dracula Bat PVD Black", "Cherry", "high", 120),
        ("RAMA", "Artisan", "RAMA x GMK Striker Soccer Ball Brass", "Cherry", "mid", 95),
        ("RAMA", "Artisan", "RAMA Waves Seq2 Moon Gold", "Cherry", "high", 130),
        ("RAMA", "Artisan", "RAMA Thermal Seq1 ICED", "Cherry", "high", 140),

        # ── Desk Mats ───────────────────────────────────────────────────
        ("Novelkeys", "Desk Mat", "Novelkeys Randomfrankp Deskpad (Dark)", "N/A", "standard", 25),
        ("Novelkeys", "Desk Mat", "GMK Botanical Desk Mat (Green)", "N/A", "mid", 45),
        ("Novelkeys", "Desk Mat", "GMK Olivia Desk Mat (Pink)", "N/A", "mid", 50),
        ("Omnitype", "Desk Mat", "GMK Mizu Desk Mat (Koi)", "N/A", "mid", 55),
        ("Omnitype", "Desk Mat", "GMK Bento Desk Mat (Salmon)", "N/A", "mid", 45),

        # ── GMK R2 Sets ────────────────────────────────────────────────
        ("GMK", "Keycap Set", "GMK Olivia++ R2 (Light Base)", "Cherry", "high", 250),
        ("GMK", "Keycap Set", "GMK Olivia++ R2 (Dark Base)", "Cherry", "high", 260),
        ("GMK", "Keycap Set", "GMK Botanical R2 (Base Kit)", "Cherry", "high", 220),
        ("GMK", "Keycap Set", "GMK Botanical R2 (Novelties)", "Cherry", "mid", 90),
        ("GMK", "Keycap Set", "GMK Mizu R2 (Base Kit)", "Cherry", "high", 230),
        ("GMK", "Keycap Set", "GMK Mizu R2 (Novelties + Spacebar)", "Cherry", "mid", 95),
        ("GMK", "Keycap Set", "GMK Bento R2 (Base Kit)", "Cherry", "high", 200),
        ("GMK", "Keycap Set", "GMK Bento R2 (Salmon Novelties)", "Cherry", "mid", 85),
        ("GMK", "Keycap Set", "GMK Dracula V2 (Core Kit)", "Cherry", "high", 240),
        ("GMK", "Keycap Set", "GMK Dracula V2 (Highlight Kit)", "Cherry", "mid", 80),
        ("GMK", "Keycap Set", "GMK Dracula V2 (ERR! Kit)", "Cherry", "mid", 90),
        ("GMK", "Keycap Set", "GMK Jamon R2 (Base Kit)", "Cherry", "high", 210),
        ("GMK", "Keycap Set", "GMK Jamon R2 (Bars + Spacebars)", "Cherry", "mid", 75),

        # ── Artisan Keycaps (additional) ────────────────────────────────
        ("Jelly Key", "Artisan", "Zen Pond IV Koi Sapphire Pour", "SA R1", "mid", 100),
        ("Jelly Key", "Artisan", "Zen Pond IV Koi Ruby Pour", "SA R1", "mid", 100),
        ("Jelly Key", "Artisan", "Zen Pond IV Koi Pearl Pour", "SA R1", "mid", 105),
        ("Jelly Key", "Artisan", "Zen Pond IV 6.25u Spacebar Emerald", "SA R1", "high", 160),
        ("Dwarf Factory", "Artisan", "Gnarly Drakon II Obsidian Storm", "Cherry R1", "mid", 70),
        ("Dwarf Factory", "Artisan", "Gnarly Drakon II Jade Tempest", "Cherry R1", "mid", 75),
        ("Dwarf Factory", "Artisan", "Gnarly Drakon II Inferno Blaze", "Cherry R1", "mid", 75),
        ("Artkey", "Artisan", "Bull V2 Crimson", "Cherry R1", "high", 200),
        ("Artkey", "Artisan", "Bull V2 Carbon", "Cherry R1", "high", 210),
        ("Artkey", "Artisan", "Bull V2 Glacier", "Cherry R1", "high", 195),
        ("S-Craft", "Artisan", "S-Craft Pokemon Chikorita", "Cherry R1", "mid", 80),
        ("S-Craft", "Artisan", "S-Craft Pokemon Cyndaquil", "Cherry R1", "mid", 80),
        ("S-Craft", "Artisan", "S-Craft Pokemon Totodile", "Cherry R1", "mid", 80),
        ("S-Craft", "Artisan", "S-Craft Pokemon Treecko", "Cherry R1", "mid", 85),
        ("S-Craft", "Artisan", "S-Craft Pokemon Torchic", "Cherry R1", "mid", 85),
        ("S-Craft", "Artisan", "S-Craft Pokemon Mudkip", "Cherry R1", "mid", 85),

        # ── Budget PBT Keycap Sets ─────────────────────────────────────
        ("Akko", "Keycap Set", "Akko Black & Gold ASA Profile (185-key)", "ASA", "standard", 45),
        ("Akko", "Keycap Set", "Akko Macaw PBT Double-Shot (157-key)", "Cherry", "standard", 40),
        ("Akko", "Keycap Set", "Akko Psittacus PBT Double-Shot (185-key)", "ASA", "standard", 45),
        ("Akko", "Keycap Set", "Akko Clear Transparent PC Keycaps", "ASA", "standard", 35),
        ("NicePBT", "Keycap Set", "NicePBT Elderberry", "Cherry", "standard", 55),
        ("NicePBT", "Keycap Set", "NicePBT Fuji", "Cherry", "standard", 55),
        ("NicePBT", "Keycap Set", "NicePBT Noel", "Cherry", "standard", 60),
        ("ePBT", "Keycap Set", "ePBT Blank White PBT (170-key)", "Cherry", "standard", 50),
        ("ePBT", "Keycap Set", "ePBT Blank Black PBT (170-key)", "Cherry", "standard", 50),

        # ── Custom Keyboards ───────────────────────────────────────────
        ("Mode", "Keyboard", "Mode Sonnet (65% Aluminum)", "N/A", "high", 350),
        ("Mode", "Keyboard", "Mode Envoy (75% Aluminum)", "N/A", "high", 400),
        ("Meletrix", "Keyboard", "Zoom65 V3 (Essential Edition)", "N/A", "mid", 120),
        ("Meletrix", "Keyboard", "Zoom65 V3 (Olivia Edition)", "N/A", "mid", 140),
        ("QK", "Keyboard", "QK65 V2 (Anodized Aluminum)", "N/A", "mid", 150),
        ("QK", "Keyboard", "QK65 V2 (E-White)", "N/A", "mid", 155),
        ("CannonKeys", "Keyboard", "Bakeneko65 (Aluminum)", "N/A", "mid", 100),
        ("CannonKeys", "Keyboard", "Bakeneko60 (Aluminum)", "N/A", "mid", 95),
        ("KBDfans", "Keyboard", "KBD67 Lite R4 (Polycarbonate)", "N/A", "standard", 75),
        ("KBDfans", "Keyboard", "KBD67 Lite R4 (Aluminum)", "N/A", "mid", 110),

        # ── Vintage / Rare Keyboards & Keycaps ─────────────────────────
        ("Cherry", "Keyboard", "Cherry G81-3000 (Vintage Doubleshots)", "N/A", "high", 250),
        ("Cherry", "Keyboard", "Cherry G81-1800 (Vintage MX Black)", "N/A", "high", 280),
        ("Honeywell", "Keycap Set", "GMK Honeywell (R1 OG)", "Cherry", "grail", 450),
        ("Cherry", "Keycap Set", "Cherry OG Doubleshots (Full Set Harvest)", "Cherry", "high", 300),
        ("Cherry", "Keycap Set", "Cherry G81 NCR Dyesubs (Full Set)", "Cherry", "grail", 500),
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

    # Merge variant expansion items, dedup by name
    existing_names = {c["name"] for c in catalog}
    for v in _variant_expansion():
        if v["name"] not in existing_names:
            catalog.append(v)
            existing_names.add(v["name"])

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
