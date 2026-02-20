"""
Import Artisan Keycaps & Keycap Sets catalog.

Layer 1 (Catalog):  Curated artisan keycaps + group buy sets → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers 135+ items across:
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
    """Curated keycap catalog (135+ items) covering artisan makers, GMK/SA/KAT/ePBT/Cherry
    sets, premium grail caps, and full custom keyboard builds as reference items."""

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

        # ── Full Custom Keyboard Builds (reference items) ──────────────
        ("Keycult", "Keyboard Build", "Keycult No. 2/65 Full Build", "N/A", "grail", 2800),
        ("TGR", "Keyboard Build", "TGR Jane V2 CE Full Build", "N/A", "grail", 3500),
        ("ai03", "Keyboard Build", "ai03 Vega Full Build", "N/A", "high", 380),
        ("Mode", "Keyboard Build", "Mode Eighty Full Build", "N/A", "high", 350),
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
