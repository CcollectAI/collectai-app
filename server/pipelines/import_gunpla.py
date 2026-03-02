"""
Import Gunpla (Gundam plastic model kit) catalog (500+ items).

Layer 1 (Catalog):  Curated Gunpla kits → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers 300+ kits across:
- Perfect Grade (PG) 1/60 scale (incl. Unleashed)
- Master Grade (MG) 1/100 scale (incl. Ver.Ka, Ver.2.0)
- Master Grade Extreme (MGEX) 1/100 scale
- Real Grade (RG) 1/144 scale
- High Grade (HG) 1/144 scale (incl. The Origin, Build series, HGUC)
- Mega Size 1/48 scale
- SD Gundam / SD Cross Silhouette
- P-Bandai web-shop exclusives (limited runs)
- Metal Build die-cast figures
- Metal Robot Spirits
- Vintage 1/100 and 1/60 kits (1980s originals)
- Full Mechanics 1/100 scale
- Series coverage: UC, SEED, Wing, 00, IBO, Witch from Mercury, Build,
  Hathaway's Flash, Thunderbolt, Narrative, SEED Freedom, Turn A, G Gundam

Usage:
    python -m pipelines.import_gunpla [--dry-run]
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

CATEGORY = "gunpla"


def get_curated_catalog() -> list[dict]:
    """Curated Gunpla catalog — 500+ kits across all major grades, series, and formats."""

    # (grade, scale, name, series, variant, rarity_tier, price_eur)
    # rarity_tier: grail (>200), high (100-200), mid (40-100), standard (<40)

    kits = [
        # ── Perfect Grade (PG) 1/60 ──────────────────────────────────────────
        ("PG", "1/60", "RX-78-2 Gundam", "Mobile Suit Gundam", "", "high", 180),
        ("PG", "1/60", "Unicorn Gundam", "Gundam Unicorn", "", "grail", 320),
        ("PG", "1/60", "Strike Freedom Gundam", "Gundam SEED Destiny", "", "grail", 280),
        ("PG", "1/60", "Gundam Exia", "Gundam 00", "", "high", 200),
        ("PG", "1/60", "Zaku II (Char Custom)", "Mobile Suit Gundam", "", "high", 180),
        ("PG", "1/60", "Banshee Norn", "Gundam Unicorn", "", "grail", 350),
        ("PG", "1/60", "Wing Gundam Zero Custom", "Gundam Wing", "", "grail", 250),
        ("PG", "1/60", "Unleashed RX-78-2", "Mobile Suit Gundam", "Unleashed", "grail", 380),
        ("PG", "1/60", "Astray Red Frame", "Gundam SEED Astray", "", "high", 190),
        ("PG", "1/60", "00 Raiser", "Gundam 00", "", "grail", 260),
        ("PG", "1/60", "GP01/Fb Full Burnern", "Gundam 0083", "", "high", 175),

        # ── Master Grade Extreme (MGEX) 1/100 ───────────────────────────────
        ("MGEX", "1/100", "Unicorn Gundam Ver.Ka", "Gundam Unicorn", "MGEX", "grail", 220),
        ("MGEX", "1/100", "Strike Freedom Gundam", "Gundam SEED Destiny", "MGEX", "grail", 210),

        # ── Master Grade (MG) 1/100 ─────────────────────────────────────────
        ("MG", "1/100", "Freedom Gundam Ver.2.0", "Gundam SEED", "", "mid", 55),
        ("MG", "1/100", "RX-78-2 Gundam Ver.3.0", "Mobile Suit Gundam", "", "mid", 50),
        ("MG", "1/100", "Sazabi Ver.Ka", "Char's Counterattack", "Ver.Ka", "mid", 85),
        ("MG", "1/100", "Nu Gundam Ver.Ka", "Char's Counterattack", "Ver.Ka", "mid", 75),
        ("MG", "1/100", "Wing Gundam Zero EW Ver.Ka", "Gundam Wing", "Ver.Ka", "mid", 60),
        ("MG", "1/100", "Sinanju Ver.Ka", "Gundam Unicorn", "Ver.Ka", "mid", 80),
        ("MG", "1/100", "Hi-Nu Gundam Ver.Ka", "Char's Counterattack", "Ver.Ka", "high", 110),
        ("MG", "1/100", "Unicorn Gundam Ver.Ka", "Gundam Unicorn", "Ver.Ka", "mid", 65),
        ("MG", "1/100", "Barbatos", "Iron-Blooded Orphans", "", "mid", 50),
        ("MG", "1/100", "Deathscythe Hell EW", "Gundam Wing", "", "mid", 55),
        ("MG", "1/100", "Full Armor Unicorn Ver.Ka", "Gundam Unicorn", "Ver.Ka", "high", 120),
        ("MG", "1/100", "Zaku II Ver.2.0", "Mobile Suit Gundam", "", "mid", 45),
        ("MG", "1/100", "Epyon EW", "Gundam Wing", "", "mid", 55),
        ("MG", "1/100", "Eclipse Gundam", "Gundam SEED Eclipse", "", "mid", 60),
        ("MG", "1/100", "ZZ Gundam Ver.Ka", "Gundam ZZ", "Ver.Ka", "mid", 70),
        ("MG", "1/100", "Full Armor ZZ Gundam Ver.Ka", "Gundam ZZ", "Ver.Ka", "high", 100),
        ("MG", "1/100", "Tallgeese EW", "Gundam Wing", "", "mid", 50),
        ("MG", "1/100", "Turn A Gundam", "Turn A Gundam", "", "mid", 55),
        ("MG", "1/100", "Gundam Kyrios", "Gundam 00", "", "mid", 48),
        ("MG", "1/100", "Gundam Dynames", "Gundam 00", "", "mid", 48),
        ("MG", "1/100", "Gundam Virtue", "Gundam 00", "", "mid", 55),
        ("MG", "1/100", "00 Raiser", "Gundam 00", "", "mid", 65),
        ("MG", "1/100", "00 Qan[T] Full Saber", "Gundam 00", "Ver.Ka", "mid", 70),
        ("MG", "1/100", "Wing Gundam Ver.Ka", "Gundam Wing", "Ver.Ka", "mid", 55),
        ("MG", "1/100", "Heavyarms EW", "Gundam Wing", "", "mid", 50),
        ("MG", "1/100", "Sandrock EW", "Gundam Wing", "", "mid", 45),
        ("MG", "1/100", "Altron Gundam EW", "Gundam Wing", "", "mid", 50),
        ("MG", "1/100", "Blitz Gundam", "Gundam SEED", "", "mid", 45),
        ("MG", "1/100", "Buster Gundam", "Gundam SEED", "", "mid", 45),
        ("MG", "1/100", "Duel Gundam Assault Shroud", "Gundam SEED", "", "mid", 48),
        ("MG", "1/100", "Justice Gundam", "Gundam SEED", "", "mid", 50),
        ("MG", "1/100", "Aile Strike Gundam Ver.RM", "Gundam SEED", "", "mid", 50),
        ("MG", "1/100", "Strike Rouge Ootori Ver.RM", "Gundam SEED", "", "mid", 65),
        ("MG", "1/100", "Destiny Gundam", "Gundam SEED Destiny", "", "mid", 55),
        ("MG", "1/100", "Infinite Justice Gundam", "Gundam SEED Destiny", "", "mid", 55),
        ("MG", "1/100", "Gundam Barbatos Lupus Rex", "Iron-Blooded Orphans", "", "mid", 55),
        ("MG", "1/100", "Gundam F91 Ver.2.0", "Gundam F91", "", "mid", 50),
        ("MG", "1/100", "V2 Assault Buster Gundam Ver.Ka", "Victory Gundam", "Ver.Ka", "mid", 75),
        ("MG", "1/100", "The-O", "Zeta Gundam", "", "high", 110),
        ("MG", "1/100", "Jesta", "Gundam Unicorn", "", "mid", 45),

        # ── Real Grade (RG) 1/144 ───────────────────────────────────────────
        ("RG", "1/144", "Hi-Nu Gundam", "Char's Counterattack", "", "mid", 48),
        ("RG", "1/144", "Sazabi", "Char's Counterattack", "", "mid", 45),
        ("RG", "1/144", "Wing Gundam Zero EW", "Gundam Wing", "", "standard", 30),
        ("RG", "1/144", "Unicorn Gundam", "Gundam Unicorn", "", "standard", 32),
        ("RG", "1/144", "Nu Gundam", "Char's Counterattack", "", "mid", 42),
        ("RG", "1/144", "God Gundam", "G Gundam", "", "mid", 40),
        ("RG", "1/144", "Force Impulse Gundam", "Gundam SEED Destiny", "", "standard", 28),
        ("RG", "1/144", "Evangelion Unit-01", "Evangelion", "", "mid", 50),
        ("RG", "1/144", "Strike Freedom Gundam", "Gundam SEED Destiny", "", "standard", 35),
        ("RG", "1/144", "Zeong", "Mobile Suit Gundam", "", "mid", 55),
        ("RG", "1/144", "Crossbone Gundam X1", "Crossbone Gundam", "", "standard", 32),
        ("RG", "1/144", "Gundam Exia", "Gundam 00", "", "standard", 28),
        ("RG", "1/144", "00 Raiser", "Gundam 00", "", "standard", 35),
        ("RG", "1/144", "Destiny Gundam", "Gundam SEED Destiny", "", "standard", 30),
        ("RG", "1/144", "Freedom Gundam", "Gundam SEED", "", "standard", 28),
        ("RG", "1/144", "Justice Gundam", "Gundam SEED", "", "standard", 28),
        ("RG", "1/144", "Tallgeese EW", "Gundam Wing", "", "standard", 30),
        ("RG", "1/144", "Gundam Mk-II AEUG", "Zeta Gundam", "", "standard", 28),
        ("RG", "1/144", "Zeta Gundam", "Zeta Gundam", "", "standard", 30),
        ("RG", "1/144", "Char's Zaku II", "Mobile Suit Gundam", "", "standard", 28),

        # ── P-Bandai Exclusives ──────────────────────────────────────────────
        ("MG", "1/100", "Altron Gundam EW (P-Bandai)", "Gundam Wing", "P-Bandai", "high", 120),
        ("MG", "1/100", "Crossbone Gundam X-2 Ver.Ka (P-Bandai)", "Crossbone Gundam", "P-Bandai Ver.Ka", "high", 130),
        ("RG", "1/144", "Tallgeese III (P-Bandai)", "Gundam Wing", "P-Bandai", "high", 65),
        ("MG", "1/100", "Hazel Custom (P-Bandai)", "Advance of Zeta", "P-Bandai", "high", 110),
        ("PG", "1/60", "Unicorn Gundam Perfectibility (P-Bandai)", "Gundam Unicorn", "P-Bandai", "grail", 450),
        ("MG", "1/100", "Providence Gundam (P-Bandai)", "Gundam SEED", "P-Bandai", "high", 100),
        ("HG", "1/144", "Penelope (P-Bandai)", "Hathaway's Flash", "P-Bandai", "mid", 80),
        ("RG", "1/144", "Banshee Norn Final Battle (P-Bandai)", "Gundam Unicorn", "P-Bandai", "mid", 70),
        ("MG", "1/100", "Deathscythe Hell EW (P-Bandai Rousette)", "Gundam Wing", "P-Bandai", "high", 115),
        ("MG", "1/100", "Sandrock EW Armadillo (P-Bandai)", "Gundam Wing", "P-Bandai", "high", 110),
        ("MG", "1/100", "Heavyarms EW Igel (P-Bandai)", "Gundam Wing", "P-Bandai", "high", 115),
        ("RG", "1/144", "Wing Gundam Zero EW Pearl Gloss (P-Bandai)", "Gundam Wing", "P-Bandai", "high", 75),
        ("MG", "1/100", "Gundam Astray Blue Frame D (P-Bandai)", "Gundam SEED Astray", "P-Bandai", "high", 100),
        ("HG", "1/144", "Xi Gundam (P-Bandai)", "Hathaway's Flash", "P-Bandai", "mid", 90),
        ("MG", "1/100", "Gelgoog Cannon (P-Bandai)", "Mobile Suit Gundam", "P-Bandai", "high", 100),

        # ── High Grade (HG) 1/144 ───────────────────────────────────────────
        ("HG", "1/144", "RX-78-2 Gundam (Revive)", "Mobile Suit Gundam", "", "standard", 14),
        ("HG", "1/144", "Barbatos Lupus Rex", "Iron-Blooded Orphans", "", "standard", 16),
        ("HG", "1/144", "Aerial", "Gundam: Witch from Mercury", "", "standard", 15),
        ("HG", "1/144", "Calibarn", "Gundam: Witch from Mercury", "", "standard", 18),
        ("HG", "1/144", "Schwarzette", "Gundam: Witch from Mercury", "", "standard", 20),
        ("HG", "1/144", "Moon Gundam", "Moon Gundam", "", "standard", 30),
        ("HG", "1/144", "Infinite Justice Gundam Type II", "Gundam SEED Freedom", "", "standard", 22),
        ("HG", "1/144", "Mighty Strike Freedom", "Gundam SEED Freedom", "", "standard", 28),
        # HG The Origin
        ("HG", "1/144", "RX-78-02 Gundam (The Origin)", "Mobile Suit Gundam: The Origin", "The Origin", "standard", 18),
        ("HG", "1/144", "MS-06S Zaku II (The Origin)", "Mobile Suit Gundam: The Origin", "The Origin", "standard", 16),
        ("HG", "1/144", "YMS-03 Waff (The Origin)", "Mobile Suit Gundam: The Origin", "The Origin", "standard", 16),
        ("HG", "1/144", "Gouf (The Origin)", "Mobile Suit Gundam: The Origin", "The Origin", "standard", 16),
        ("HG", "1/144", "Bugu (Ramba Ral) (The Origin)", "Mobile Suit Gundam: The Origin", "The Origin", "standard", 18),
        # HG Build series
        ("HG", "1/144", "Build Strike Gundam Full Package", "Gundam Build Fighters", "Build", "standard", 16),
        ("HG", "1/144", "Star Burning Gundam", "Gundam Build Fighters Try", "Build", "standard", 18),
        ("HG", "1/144", "Try Burning Gundam", "Gundam Build Fighters Try", "Build", "standard", 16),
        ("HG", "1/144", "Gundam 00 Diver Ace", "Gundam Build Divers", "Build", "standard", 16),
        ("HG", "1/144", "Earthree Gundam", "Gundam Build Divers Re:RISE", "Build", "standard", 15),
        # HG IBO
        ("HG", "1/144", "Barbatos (1st Form)", "Iron-Blooded Orphans", "", "standard", 12),
        ("HG", "1/144", "Barbatos Lupus", "Iron-Blooded Orphans", "", "standard", 14),
        ("HG", "1/144", "Grimgerde", "Iron-Blooded Orphans", "", "standard", 14),
        ("HG", "1/144", "Vidar", "Iron-Blooded Orphans", "", "standard", 16),
        # HG misc popular
        ("HG", "1/144", "Narrative Gundam A-Packs", "Gundam Narrative", "", "standard", 25),
        ("HG", "1/144", "Xi Gundam", "Hathaway's Flash", "", "standard", 38),
        ("HG", "1/144", "Penelope", "Hathaway's Flash", "", "standard", 38),

        # ── Mega Size 1/48 ───────────────────────────────────────────────────
        ("Mega Size", "1/48", "RX-78-2 Gundam", "Mobile Suit Gundam", "", "mid", 65),
        ("Mega Size", "1/48", "Char's Zaku II", "Mobile Suit Gundam", "", "mid", 65),
        ("Mega Size", "1/48", "Unicorn Gundam (Destroy Mode)", "Gundam Unicorn", "", "mid", 75),
        ("Mega Size", "1/48", "Age-1 Normal", "Gundam AGE", "", "mid", 60),

        # ── SD Gundam ────────────────────────────────────────────────────────
        ("SD CS", "SD", "RX-78-2 Gundam (Cross Silhouette)", "Mobile Suit Gundam", "Cross Silhouette", "standard", 12),
        ("SD CS", "SD", "Unicorn Gundam (Destroy Mode) (Cross Silhouette)", "Gundam Unicorn", "Cross Silhouette", "standard", 14),
        ("SD CS", "SD", "Freedom Gundam (Cross Silhouette)", "Gundam SEED", "Cross Silhouette", "standard", 14),
        ("SD EX-Standard", "SD", "Wing Gundam Zero EW", "Gundam Wing", "EX-Standard", "standard", 8),
        ("SD EX-Standard", "SD", "Strike Freedom Gundam", "Gundam SEED Destiny", "EX-Standard", "standard", 8),

        # ── Metal Build (die-cast figures) ───────────────────────────────────
        ("Metal Build", "1/100", "Strike Freedom Gundam", "Gundam SEED Destiny", "Metal Build", "grail", 350),
        ("Metal Build", "1/100", "Destiny Gundam (Full Package)", "Gundam SEED Destiny", "Metal Build", "grail", 380),
        ("Metal Build", "1/100", "00 Raiser", "Gundam 00", "Metal Build", "grail", 320),
        ("Metal Build", "1/100", "Gundam Barbatos Lupus Rex", "Iron-Blooded Orphans", "Metal Build", "grail", 300),
        ("Metal Build", "1/100", "Freedom Gundam Concept 2", "Gundam SEED", "Metal Build", "grail", 400),
        ("Metal Build", "1/100", "Aile Strike Gundam", "Gundam SEED", "Metal Build", "grail", 280),
        ("Metal Build", "1/100", "Crossbone Gundam X1", "Crossbone Gundam", "Metal Build", "grail", 260),
        ("Metal Build", "1/100", "Hi-Nu Gundam", "Char's Counterattack", "Metal Build", "grail", 420),

        # ── Vintage Kits ─────────────────────────────────────────────────────
        ("Vintage", "1/100", "RX-78-2 Gundam (1980 Original)", "Mobile Suit Gundam", "Vintage", "high", 120),
        ("Vintage", "1/100", "MS-06S Zaku II (1980 Original)", "Mobile Suit Gundam", "Vintage", "high", 100),
        ("Vintage", "1/60", "RX-78-2 Gundam (1980 1/60)", "Mobile Suit Gundam", "Vintage", "high", 150),
        ("Vintage", "1/100", "Z Gundam (1985 Original)", "Zeta Gundam", "Vintage", "high", 110),
        ("Vintage", "1/100", "ZZ Gundam (1986 Original)", "Gundam ZZ", "Vintage", "high", 100),
        ("Vintage", "1/60", "Zaku II (1980 1/60)", "Mobile Suit Gundam", "Vintage", "high", 130),

        # ── Full Mechanics 1/100 ────────────────────────────────────────────
        ("Full Mechanics", "1/100", "Barbatos Lupus Rex", "Iron-Blooded Orphans", "", "mid", 40),
        ("Full Mechanics", "1/100", "Aerial", "Gundam: Witch from Mercury", "", "mid", 45),
        ("Full Mechanics", "1/100", "Forbidden Gundam", "Gundam SEED", "", "mid", 42),
        ("Full Mechanics", "1/100", "Calamity Gundam", "Gundam SEED", "", "mid", 42),
        ("Full Mechanics", "1/100", "Raider Gundam", "Gundam SEED", "", "mid", 42),

        # ── More MG kits ───────────────────────────────────────────────────
        ("MG", "1/100", "Strike Noir Gundam", "Gundam SEED Stargazer", "", "mid", 50),
        ("MG", "1/100", "Gundam AGE-1 Normal", "Gundam AGE", "", "mid", 42),
        ("MG", "1/100", "Gundam AGE-2 Normal", "Gundam AGE", "", "mid", 42),
        ("MG", "1/100", "GM Sniper II", "Gundam 0080", "", "mid", 45),
        ("MG", "1/100", "Geara Doga", "Char's Counterattack", "", "mid", 48),
        ("MG", "1/100", "ReZEL", "Gundam Unicorn", "", "mid", 55),
        ("MG", "1/100", "ReZEL Commander Type", "Gundam Unicorn", "", "mid", 58),
        ("MG", "1/100", "Delta Plus", "Gundam Unicorn", "", "mid", 55),
        ("MG", "1/100", "Gundam Alex Ver.2.0", "Gundam 0080", "", "mid", 50),
        ("MG", "1/100", "Ball Ver.Ka", "Mobile Suit Gundam", "Ver.Ka", "mid", 40),
        ("MG", "1/100", "Dom", "Mobile Suit Gundam", "", "mid", 50),
        ("MG", "1/100", "Gouf Ver.2.0", "Mobile Suit Gundam", "", "mid", 45),
        ("MG", "1/100", "Gelgoog Ver.2.0", "Mobile Suit Gundam", "", "mid", 48),
        ("MG", "1/100", "Guncannon", "Mobile Suit Gundam", "", "mid", 45),
        ("MG", "1/100", "Guntank", "Mobile Suit Gundam", "", "mid", 45),
        ("MG", "1/100", "Hyaku Shiki Ver.2.0", "Zeta Gundam", "", "mid", 60),
        ("MG", "1/100", "Rick Dias", "Zeta Gundam", "", "mid", 50),
        ("MG", "1/100", "Gundam Mk-II Ver.2.0 (AEUG)", "Zeta Gundam", "", "mid", 48),
        ("MG", "1/100", "Gundam Mk-II Ver.2.0 (Titans)", "Zeta Gundam", "", "mid", 48),
        ("MG", "1/100", "Zeta Gundam Ver.Ka", "Zeta Gundam", "Ver.Ka", "mid", 65),
        ("MG", "1/100", "Super Gundam", "Zeta Gundam", "", "mid", 55),
        ("MG", "1/100", "Ex-S Gundam", "Gundam Sentinel", "", "high", 120),
        ("MG", "1/100", "S Gundam", "Gundam Sentinel", "", "high", 100),
        ("MG", "1/100", "FAZZ Ver.Ka", "Gundam Sentinel", "Ver.Ka", "high", 110),
        ("MG", "1/100", "Psycho Zaku Ver.Ka", "Gundam Thunderbolt", "Ver.Ka", "high", 130),
        ("MG", "1/100", "Full Armor Gundam Ver.Ka (Thunderbolt)", "Gundam Thunderbolt", "Ver.Ka", "high", 100),
        ("MG", "1/100", "Gundam Stormbringer", "Gundam Thunderbolt", "", "mid", 60),
        ("MG", "1/100", "Providence Gundam", "Gundam SEED", "", "mid", 60),
        ("MG", "1/100", "Aegis Gundam", "Gundam SEED", "", "mid", 50),
        ("MG", "1/100", "Impulse Gundam", "Gundam SEED Destiny", "", "mid", 50),
        ("MG", "1/100", "Legend Gundam", "Gundam SEED Destiny", "", "mid", 55),
        ("MG", "1/100", "Akatsuki Gundam (Oowashi)", "Gundam SEED Destiny", "", "mid", 65),

        # ── More RG kits ───────────────────────────────────────────────────
        ("RG", "1/144", "Full Armor Unicorn Gundam", "Gundam Unicorn", "", "mid", 45),
        ("RG", "1/144", "Banshee Norn", "Gundam Unicorn", "", "mid", 40),
        ("RG", "1/144", "Sinanju", "Gundam Unicorn", "", "mid", 42),
        ("RG", "1/144", "Gundam Aerial", "Gundam: Witch from Mercury", "", "standard", 32),
        ("RG", "1/144", "Evangelion Unit-02", "Evangelion", "", "mid", 50),
        ("RG", "1/144", "Evangelion Unit-00 DX Positron Cannon Set", "Evangelion", "", "mid", 65),
        ("RG", "1/144", "MSN-04 Sazabi", "Char's Counterattack", "", "mid", 45),
        ("RG", "1/144", "Gundam Astray Red Frame", "Gundam SEED Astray", "", "standard", 30),
        ("RG", "1/144", "Gundam Astray Gold Frame Amatsu Mina", "Gundam SEED Astray", "", "standard", 35),
        ("RG", "1/144", "RX-78-2 Gundam", "Mobile Suit Gundam", "", "standard", 25),
        ("RG", "1/144", "Char's Z'Gok", "Mobile Suit Gundam", "", "standard", 28),
        ("RG", "1/144", "Aile Strike Gundam", "Gundam SEED", "", "standard", 28),
        ("RG", "1/144", "Skygrasper + Aile Striker", "Gundam SEED", "", "standard", 30),

        # ── More HG kits ──────────────────────────────────────────────────
        ("HG", "1/144", "Aerial Rebuild", "Gundam: Witch from Mercury", "", "standard", 18),
        ("HG", "1/144", "Darilbalde", "Gundam: Witch from Mercury", "", "standard", 18),
        ("HG", "1/144", "Pharact", "Gundam: Witch from Mercury", "", "standard", 20),
        ("HG", "1/144", "Lfrith", "Gundam: Witch from Mercury", "", "standard", 16),
        ("HG", "1/144", "Beguir-Beu", "Gundam: Witch from Mercury", "", "standard", 16),
        ("HG", "1/144", "Michaelis", "Gundam: Witch from Mercury", "", "standard", 18),
        ("HG", "1/144", "Gundam Lfrith Ur", "Gundam: Witch from Mercury", "", "standard", 18),
        ("HG", "1/144", "Zowort Heavy", "Gundam: Witch from Mercury", "", "standard", 20),
        ("HG", "1/144", "Rising Freedom Gundam", "Gundam SEED Freedom", "", "standard", 18),
        ("HG", "1/144", "Immortal Justice Gundam", "Gundam SEED Freedom", "", "standard", 20),
        ("HG", "1/144", "Gyan Strom", "Gundam SEED Freedom", "", "standard", 16),
        ("HG", "1/144", "Destiny Gundam Spec II", "Gundam SEED Freedom", "", "standard", 22),
        ("HG", "1/144", "Barzam", "Zeta Gundam", "", "standard", 14),
        ("HG", "1/144", "Galbaldy Beta", "Zeta Gundam", "", "standard", 16),
        ("HG", "1/144", "Messer", "Hathaway's Flash", "", "standard", 18),
        ("HG", "1/144", "Gustav Karl", "Hathaway's Flash", "", "standard", 16),
        ("HG", "1/144", "Gundam TR-1 Hazel Custom", "Advance of Zeta", "", "standard", 20),
        ("HG", "1/144", "Gundam TR-6 Woundwort", "Advance of Zeta", "", "standard", 22),
        ("HG", "1/144", "Atlas Gundam", "Gundam Thunderbolt", "", "standard", 25),
        ("HG", "1/144", "Psycho Zaku (Thunderbolt)", "Gundam Thunderbolt", "", "standard", 28),
        ("HG", "1/144", "Sinanju Stein (Narrative)", "Gundam Narrative", "", "standard", 22),
        ("HG", "1/144", "Jegan", "Char's Counterattack", "", "standard", 14),
        ("HG", "1/144", "ReGZ", "Char's Counterattack", "", "standard", 16),

        # ── More P-Bandai Exclusives ───────────────────────────────────────
        ("MG", "1/100", "Gundam Nataku EW (P-Bandai)", "Gundam Wing", "P-Bandai", "high", 105),
        ("MG", "1/100", "Tallgeese III (P-Bandai)", "Gundam Wing", "P-Bandai", "high", 100),
        ("RG", "1/144", "Sinanju (Special Coating) (P-Bandai)", "Gundam Unicorn", "P-Bandai", "high", 80),
        ("RG", "1/144", "Crossbone Gundam X2 (P-Bandai)", "Crossbone Gundam", "P-Bandai", "high", 65),
        ("HG", "1/144", "Pale Rider Cavalry (P-Bandai)", "Missing Link", "P-Bandai", "mid", 40),
        ("MG", "1/100", "Gundam Fenice Rinascita (P-Bandai)", "Gundam Build Fighters", "P-Bandai", "high", 95),

        # ── More Metal Build ───────────────────────────────────────────────
        ("Metal Build", "1/100", "Wing Gundam Zero EW", "Gundam Wing", "Metal Build", "grail", 350),
        ("Metal Build", "1/100", "Gundam Exia Repair IV", "Gundam 00", "Metal Build", "grail", 300),
        ("Metal Build", "1/100", "Destiny Gundam Soul Red", "Gundam SEED Destiny", "Metal Build", "grail", 450),
        ("Metal Build", "1/100", "Gundam Astray Red Frame Kai", "Gundam SEED Astray", "Metal Build", "grail", 350),

        # ── Metal Robot Spirits ────────────────────────────────────────────
        ("Metal Robot Spirits", "N/A", "Lancelot Albion", "Code Geass", "Metal Robot Spirits", "grail", 180),
        ("Metal Robot Spirits", "N/A", "Gundam Vidar", "Iron-Blooded Orphans", "Metal Robot Spirits", "high", 120),
        ("Metal Robot Spirits", "N/A", "Versal Knight Gundam", "SD Gundam", "Metal Robot Spirits", "high", 150),
        ("Metal Robot Spirits", "N/A", "Liu Bei Gundam", "SD Gundam World Heroes", "Metal Robot Spirits", "high", 140),

        # ── SD Gundam (additional) ─────────────────────────────────────────
        ("SD CS", "SD", "Nightingale (Cross Silhouette)", "Char's Counterattack", "Cross Silhouette", "standard", 16),
        ("SD CS", "SD", "Tornado Gundam (Cross Silhouette)", "Gundam Build Divers", "Cross Silhouette", "standard", 14),
        ("SD EX-Standard", "SD", "Nu Gundam", "Char's Counterattack", "EX-Standard", "standard", 8),
        ("SD EX-Standard", "SD", "Unicorn Gundam (Destroy Mode)", "Gundam Unicorn", "EX-Standard", "standard", 8),

        # ── PG Expanded ──────────────────────────────────────────────────
        ("PG", "1/60", "Strike Gundam", "Gundam SEED", "", "grail", 240),
        ("PG", "1/60", "Mk-II Gundam (AEUG)", "Zeta Gundam", "", "high", 200),
        ("PG", "1/60", "Mk-II Gundam (Titans)", "Zeta Gundam", "", "high", 195),
        ("PG", "1/60", "Red Frame Kai", "Gundam SEED Astray", "", "grail", 280),
        ("PG", "1/60", "Zaku II (Green)", "Mobile Suit Gundam", "", "high", 175),

        # ── PG Unleashed & LED ────────────────────────────────────────────
        ("PG", "1/60", "Unleashed RX-78-2 LED Unit Set", "Mobile Suit Gundam", "Unleashed LED", "grail", 420),
        ("PG", "1/60", "Strike Freedom LED Add-On", "Gundam SEED Destiny", "LED Unit", "high", 120),
        ("PG", "1/60", "Unicorn Gundam LED Unit", "Gundam Unicorn", "LED Unit", "high", 100),
        ("PG", "1/60", "Exia LED Unit", "Gundam 00", "LED Unit", "high", 100),
        ("PG", "1/60", "Banshee Norn LED Unit", "Gundam Unicorn", "LED Unit", "high", 110),

        # ── MG Ver.Ka Favorites Expanded ─────────────────────────────────
        ("MG", "1/100", "RX-78-2 Gundam Ver.Ka", "Mobile Suit Gundam", "Ver.Ka", "mid", 55),
        ("MG", "1/100", "Crossbone Gundam X1 Ver.Ka", "Crossbone Gundam", "Ver.Ka", "mid", 60),
        ("MG", "1/100", "Crossbone Gundam X1 Full Cloth Ver.Ka", "Crossbone Gundam", "Ver.Ka", "mid", 75),
        ("MG", "1/100", "Gundam Double X", "Gundam X", "", "mid", 55),
        ("MG", "1/100", "Gundam X", "Gundam X", "", "mid", 50),
        ("MG", "1/100", "Jegan", "Char's Counterattack", "", "mid", 45),
        ("MG", "1/100", "Kampfer", "Gundam 0080", "", "mid", 50),
        ("MG", "1/100", "Jagd Doga (Quess Custom)", "Char's Counterattack", "", "mid", 55),
        ("MG", "1/100", "Shenlong Gundam EW", "Gundam Wing", "", "mid", 48),
        ("MG", "1/100", "Gundam Heavyarms Custom EW", "Gundam Wing", "", "mid", 55),
        ("MG", "1/100", "God Gundam", "G Gundam", "", "mid", 55),
        ("MG", "1/100", "Master Gundam", "G Gundam", "", "mid", 50),
        ("MG", "1/100", "Shining Gundam", "G Gundam", "", "mid", 48),

        # ── RG New Releases & Popular ────────────────────────────────────
        ("RG", "1/144", "Wing Gundam", "Gundam Wing", "", "standard", 28),
        ("RG", "1/144", "Crossbone Gundam X1", "Crossbone Gundam", "", "standard", 32),
        ("RG", "1/144", "Gundam Mk-II (Titans)", "Zeta Gundam", "", "standard", 28),
        ("RG", "1/144", "Kampfer (P-Bandai)", "Gundam 0080", "P-Bandai", "mid", 60),
        ("RG", "1/144", "Impulse Gundam", "Gundam SEED Destiny", "", "standard", 30),
        ("RG", "1/144", "Perfect Strike Gundam", "Gundam SEED", "", "standard", 38),
        ("RG", "1/144", "Epyon", "Gundam Wing", "", "standard", 35),
        ("RG", "1/144", "Char's Gelgoog", "Mobile Suit Gundam", "", "standard", 28),

        # ── HG IBO Full Lineup ───────────────────────────────────────────
        ("HG", "1/144", "Gusion Rebake Full City", "Iron-Blooded Orphans", "", "standard", 16),
        ("HG", "1/144", "Flauros (Ryusei-Go)", "Iron-Blooded Orphans", "", "standard", 16),
        ("HG", "1/144", "Bael", "Iron-Blooded Orphans", "", "standard", 18),
        ("HG", "1/144", "Kimaris Vidar", "Iron-Blooded Orphans", "", "standard", 18),
        ("HG", "1/144", "Astaroth Origin", "Iron-Blooded Orphans", "", "standard", 14),
        ("HG", "1/144", "Marchosias", "Iron-Blooded Orphans: Urdr-Hunt", "", "standard", 16),
        ("HG", "1/144", "Hashmal", "Iron-Blooded Orphans", "", "standard", 30),
        ("HG", "1/144", "Reginlaze Julia", "Iron-Blooded Orphans", "", "standard", 16),

        # ── HG Witch from Mercury Full Lineup ────────────────────────────
        ("HG", "1/144", "Gundam Lfrith Thorn", "Gundam: Witch from Mercury", "", "standard", 18),
        ("HG", "1/144", "Gundam Lfrith Jiu", "Gundam: Witch from Mercury", "", "standard", 16),
        ("HG", "1/144", "Heindree", "Gundam: Witch from Mercury", "", "standard", 15),
        ("HG", "1/144", "Demi Trainer", "Gundam: Witch from Mercury", "", "standard", 14),
        ("HG", "1/144", "Dilanza", "Gundam: Witch from Mercury", "", "standard", 16),
        ("HG", "1/144", "Chuchu's Demi Trainer", "Gundam: Witch from Mercury", "", "standard", 15),
        ("HG", "1/144", "Beguir-Pente", "Gundam: Witch from Mercury", "", "standard", 18),
        ("HG", "1/144", "Guel's Dilanza", "Gundam: Witch from Mercury", "", "standard", 16),
        ("HG", "1/144", "Gundam Calibarn", "Gundam: Witch from Mercury", "", "standard", 20),
        ("HG", "1/144", "Typhoeus Gundam Chimera", "Gundam: Witch from Mercury", "", "standard", 22),

        # ── SD Gundam World Heroes ───────────────────────────────────────
        ("SD World Heroes", "SD", "Wukong Impulse Gundam", "SD Gundam World Heroes", "", "standard", 12),
        ("SD World Heroes", "SD", "Arthur Gundam Mk-III", "SD Gundam World Heroes", "", "standard", 14),
        ("SD World Heroes", "SD", "Sergeant Verde Buster Gundam", "SD Gundam World Heroes", "", "standard", 12),
        ("SD World Heroes", "SD", "Nobunaga Gundam Epyon", "SD Gundam World Heroes", "", "standard", 14),
        ("SD World Heroes", "SD", "Benjamin V2 Gundam", "SD Gundam World Heroes", "", "standard", 12),
        ("SD World Heroes", "SD", "Caesar Legend Gundam", "SD Gundam World Heroes", "", "standard", 12),

        # ── Mega Size Expanded ───────────────────────────────────────────
        ("Mega Size", "1/48", "Zaku II (Green)", "Mobile Suit Gundam", "", "mid", 60),
        ("Mega Size", "1/48", "Gundam AGE-2 Normal", "Gundam AGE", "", "mid", 55),

        # ── Entry Grade ──────────────────────────────────────────────────
        ("Entry Grade", "1/144", "RX-78-2 Gundam", "Mobile Suit Gundam", "Entry Grade", "standard", 8),
        ("Entry Grade", "1/144", "Strike Gundam", "Gundam SEED", "Entry Grade", "standard", 8),
        ("Entry Grade", "1/144", "Nu Gundam", "Char's Counterattack", "Entry Grade", "standard", 10),
        ("Entry Grade", "1/144", "Lah Gundam", "Gundam Build Metaverse", "Entry Grade", "standard", 10),
        ("Entry Grade", "1/144", "Gundam Aerial", "Gundam: Witch from Mercury", "Entry Grade", "standard", 8),

        # ── 30 Minutes Missions Crossovers ───────────────────────────────
        ("30MM", "1/144", "eEXM-17 Alto (White)", "30 Minutes Missions", "", "standard", 10),
        ("30MM", "1/144", "eEXM-17 Alto (Dark Gray)", "30 Minutes Missions", "", "standard", 10),
        ("30MM", "1/144", "eEXM-21 Rabiot (White)", "30 Minutes Missions", "", "standard", 12),
        ("30MM", "1/144", "bEXM-15 Portanova (Marine)", "30 Minutes Missions", "", "standard", 12),
        ("30MM", "1/144", "eEXM-30 Espossito (Alpha)", "30 Minutes Missions", "", "standard", 14),

        # ── P-Bandai Exclusives Expanded ─────────────────────────────────
        ("MG", "1/100", "Gundam Bael (P-Bandai)", "Iron-Blooded Orphans", "P-Bandai", "high", 110),
        ("MG", "1/100", "Blaze Zaku Phantom (P-Bandai)", "Gundam SEED Destiny", "P-Bandai", "high", 100),
        ("MG", "1/100", "Gundam Astray Turn Red (P-Bandai)", "Gundam SEED Astray", "P-Bandai", "high", 115),
        ("RG", "1/144", "Destiny Gundam (Titanium Finish) (P-Bandai)", "Gundam SEED Destiny", "P-Bandai", "high", 70),
        ("RG", "1/144", "00 Raiser (Trans-Am Clear) (P-Bandai)", "Gundam 00", "P-Bandai", "high", 75),
        ("HG", "1/144", "Gundam Gremory (P-Bandai)", "Iron-Blooded Orphans", "P-Bandai", "mid", 35),
        ("HG", "1/144", "Gundam Dantalion (P-Bandai)", "Iron-Blooded Orphans", "P-Bandai", "mid", 38),
        ("PG", "1/60", "Gundam Exia (Lighting Model) (P-Bandai)", "Gundam 00", "P-Bandai", "grail", 400),
        ("MG", "1/100", "Rick Dom (P-Bandai)", "Mobile Suit Gundam", "P-Bandai", "high", 95),
        ("MG", "1/100", "Gundam Storm Bringer (P-Bandai)", "Gundam Thunderbolt", "P-Bandai", "high", 100),

        # ── More Metal Build ─────────────────────────────────────────────
        ("Metal Build", "1/100", "Gundam F91 (Harrison Maddin)", "Gundam F91", "Metal Build", "grail", 320),
        ("Metal Build", "1/100", "Destiny Gundam (Heine)", "Gundam SEED Destiny", "Metal Build", "grail", 360),
        ("Metal Build", "1/100", "Infinite Justice Gundam", "Gundam SEED Destiny", "Metal Build", "grail", 340),
        ("Metal Build", "1/100", "Strike Rouge Ootori", "Gundam SEED", "Metal Build", "grail", 330),
        ("Metal Build", "1/100", "Eva-01", "Evangelion", "Metal Build", "grail", 280),

        # ── PG Complete Lineup ──────────────────────────────────────────
        ("PG", "1/60", "Gundam Mk-II (Titans)", "Zeta Gundam", "", "high", 195),
        ("PG", "1/60", "RX-0 Unicorn Gundam 03 Phenex (Gold Plating)", "Gundam Narrative", "", "grail", 500),
        ("PG", "1/60", "Perfect Strike Gundam", "Gundam SEED", "", "grail", 280),

        # ── MG Ver.Ka Complete ──────────────────────────────────────────
        ("MG", "1/100", "Gundam F91 Ver.Ka", "Gundam F91", "Ver.Ka", "mid", 55),
        ("MG", "1/100", "Victory Gundam Ver.Ka", "Victory Gundam", "Ver.Ka", "mid", 55),
        ("MG", "1/100", "Turn A Gundam (Moonlight Butterfly) Ver.Ka", "Turn A Gundam", "Ver.Ka", "mid", 70),
        ("MG", "1/100", "Assault Buster Gundam Ver.Ka", "Victory Gundam", "Ver.Ka", "mid", 80),
        ("MG", "1/100", "Gundam Alex Ver.Ka (NT-1)", "Gundam 0080", "Ver.Ka", "mid", 55),
        ("MG", "1/100", "Unicorn Gundam 02 Banshee Ver.Ka", "Gundam Unicorn", "Ver.Ka", "mid", 70),
        ("MG", "1/100", "Phenex Gundam Ver.Ka", "Gundam Narrative", "Ver.Ka", "high", 130),
        ("MG", "1/100", "Gundam Barbatos Ver.Ka", "Iron-Blooded Orphans", "Ver.Ka", "mid", 65),
        ("MG", "1/100", "Jesta Cannon Ver.Ka", "Gundam Unicorn", "Ver.Ka", "mid", 60),
        ("MG", "1/100", "Narrative Gundam Ver.Ka", "Gundam Narrative", "Ver.Ka", "mid", 70),

        # ── MG — UC Series Complete ────────────────────────────────────
        ("MG", "1/100", "Kshatriya", "Gundam Unicorn", "", "high", 120),
        ("MG", "1/100", "Sinanju Stein Ver.Ka", "Gundam Narrative", "Ver.Ka", "mid", 75),
        ("MG", "1/100", "Sinanju Stein (Narrative)", "Gundam Narrative", "", "mid", 70),
        ("MG", "1/100", "Rozen Zulu", "Gundam Unicorn", "", "mid", 65),
        ("MG", "1/100", "Dreissen", "Gundam Unicorn", "", "mid", 55),
        ("MG", "1/100", "Gundam NT-1 Full Armor", "Gundam 0080", "", "mid", 60),
        ("MG", "1/100", "GM Command Colony Type", "Gundam 0080", "", "mid", 42),
        ("MG", "1/100", "RGM-79N GM Custom", "Gundam 0083", "", "mid", 45),
        ("MG", "1/100", "GP01 Gundam Zephyranthes", "Gundam 0083", "", "mid", 48),
        ("MG", "1/100", "GP02A Gundam Physalis", "Gundam 0083", "", "mid", 55),
        ("MG", "1/100", "GP03S Gundam Stamen", "Gundam 0083", "", "mid", 50),
        ("MG", "1/100", "Powered GM", "Gundam 0083", "", "mid", 42),

        # ── MG — SEED Complete ──────────────────────────────────────────
        ("MG", "1/100", "Astray Blue Frame 2nd Revise", "Gundam SEED Astray", "", "mid", 55),
        ("MG", "1/100", "Astray Gold Frame Amatsu Mina", "Gundam SEED Astray", "", "mid", 60),
        ("MG", "1/100", "Astray Green Frame", "Gundam SEED Astray", "", "mid", 55),
        ("MG", "1/100", "Sword Impulse Gundam", "Gundam SEED Destiny", "", "mid", 52),
        ("MG", "1/100", "Blast Impulse Gundam", "Gundam SEED Destiny", "", "mid", 52),
        ("MG", "1/100", "Saviour Gundam", "Gundam SEED Destiny", "", "mid", 50),
        ("MG", "1/100", "Chaos Gundam", "Gundam SEED Destiny", "", "mid", 48),
        ("MG", "1/100", "Gaia Gundam", "Gundam SEED Destiny", "", "mid", 48),
        ("MG", "1/100", "Abyss Gundam", "Gundam SEED Destiny", "", "mid", 48),
        ("MG", "1/100", "Destiny Gundam Extreme Blast Mode", "Gundam SEED Destiny", "", "mid", 65),
        ("MG", "1/100", "Strike Freedom Gundam Full Burst Mode", "Gundam SEED Destiny", "", "mid", 70),

        # ── MG — Wing Complete ──────────────────────────────────────────
        ("MG", "1/100", "Tallgeese II", "Gundam Wing", "", "mid", 50),
        ("MG", "1/100", "Tallgeese III", "Gundam Wing", "", "mid", 55),
        ("MG", "1/100", "Wing Gundam (TV Version)", "Gundam Wing", "", "mid", 45),
        ("MG", "1/100", "Gundam Nataku", "Gundam Wing", "", "mid", 48),
        ("MG", "1/100", "Mercurius", "Gundam Wing", "", "mid", 45),
        ("MG", "1/100", "Vayeate", "Gundam Wing", "", "mid", 45),
        ("MG", "1/100", "Gundam Deathscythe EW Ver.Ka", "Gundam Wing", "Ver.Ka", "mid", 60),

        # ── MG — 00 Complete ───────────────────────────────────────────
        ("MG", "1/100", "GN-X", "Gundam 00", "", "mid", 48),
        ("MG", "1/100", "Cherudim Gundam", "Gundam 00", "", "mid", 55),
        ("MG", "1/100", "Arios Gundam", "Gundam 00", "", "mid", 52),
        ("MG", "1/100", "Seravee Gundam", "Gundam 00", "", "mid", 60),
        ("MG", "1/100", "Gundam Exia (Dark Matter)", "Gundam 00", "", "mid", 55),
        ("MG", "1/100", "Gundam Exia (Ignition Mode)", "Gundam 00", "", "mid", 58),
        ("MG", "1/100", "00 Qan[T]", "Gundam 00", "", "mid", 55),

        # ── MG — G Gundam Complete ──────────────────────────────────────
        ("MG", "1/100", "Bolt Gundam", "G Gundam", "", "mid", 50),
        ("MG", "1/100", "Dragon Gundam", "G Gundam", "", "mid", 48),
        ("MG", "1/100", "Gundam Maxter", "G Gundam", "", "mid", 48),
        ("MG", "1/100", "Gundam Rose", "G Gundam", "", "mid", 48),
        ("MG", "1/100", "Nobel Gundam", "G Gundam", "", "mid", 45),

        # ── RG All Remaining Releases ───────────────────────────────────
        ("RG", "1/144", "Gundam MKII (A.E.U.G.) Ver.2", "Zeta Gundam", "", "standard", 30),
        ("RG", "1/144", "Zeta Gundam (Biosensor)", "Zeta Gundam", "", "mid", 40),
        ("RG", "1/144", "Johnny Ridden's Zaku II", "MSV", "", "standard", 30),
        ("RG", "1/144", "Shin Matsunaga's Zaku II", "MSV", "", "standard", 30),
        ("RG", "1/144", "Unicorn Gundam (Lighting Model)", "Gundam Unicorn", "", "mid", 60),
        ("RG", "1/144", "Banshee Norn (Final Battle)", "Gundam Unicorn", "", "mid", 45),
        ("RG", "1/144", "Full Armor Unicorn Gundam (Psycho Frame)", "Gundam Unicorn", "", "mid", 50),
        ("RG", "1/144", "Gundam Deathscythe Hell EW", "Gundam Wing", "", "standard", 35),
        ("RG", "1/144", "Tallgeese II", "Gundam Wing", "", "standard", 32),
        ("RG", "1/144", "Tallgeese III", "Gundam Wing", "", "standard", 35),
        ("RG", "1/144", "Wing Gundam Zero EW (Pearl Gloss)", "Gundam Wing", "", "mid", 50),
        ("RG", "1/144", "Destiny Gundam (Heine Custom)", "Gundam SEED Destiny", "", "standard", 32),
        ("RG", "1/144", "Aile Strike + Skygrasper", "Gundam SEED", "", "standard", 38),
        ("RG", "1/144", "Mighty Strike Freedom", "Gundam SEED Freedom", "", "standard", 38),

        # ── HG — SEED Freedom Full Lineup ──────────────────────────────
        ("HG", "1/144", "Freedom Gundam (SEED Freedom Ver.)", "Gundam SEED Freedom", "", "standard", 18),
        ("HG", "1/144", "Justice Gundam (SEED Freedom Ver.)", "Gundam SEED Freedom", "", "standard", 18),
        ("HG", "1/144", "Strike Freedom (SEED Freedom Ver.)", "Gundam SEED Freedom", "", "standard", 20),
        ("HG", "1/144", "Akatsuki Gundam (SEED Freedom)", "Gundam SEED Freedom", "", "standard", 22),
        ("HG", "1/144", "Black Knight Squad Shi-ve.A", "Gundam SEED Freedom", "", "standard", 20),

        # ── HG — Build Series Full ─────────────────────────────────────
        ("HG", "1/144", "Wing Gundam Sky Zero", "Gundam Build Metaverse", "Build", "standard", 18),
        ("HG", "1/144", "Lah Gundam", "Gundam Build Metaverse", "Build", "standard", 16),
        ("HG", "1/144", "Typhoeus Gundam", "Gundam Build Metaverse", "Build", "standard", 18),
        ("HG", "1/144", "Blazing Gundam", "Gundam Build Fighters Try", "Build", "standard", 16),
        ("HG", "1/144", "Beginning Gundam", "Gundam Build Fighters", "Build", "standard", 14),
        ("HG", "1/144", "Kamiki Burning Gundam", "Gundam Build Fighters Try", "Build", "standard", 18),
        ("HG", "1/144", "Amazing Red Warrior", "Gundam Build Fighters Try", "Build", "standard", 18),
        ("HG", "1/144", "Gundam 00 Sky", "Gundam Build Divers", "Build", "standard", 16),
        ("HG", "1/144", "Core Gundam II", "Gundam Build Divers Re:RISE", "Build", "standard", 14),
        ("HG", "1/144", "Uraven Gundam", "Gundam Build Divers Re:RISE", "Build", "standard", 16),
        ("HG", "1/144", "Gundam Helios", "Gundam Breaker Battlogue", "Build", "standard", 18),

        # ── HG — Thunderbolt Full ──────────────────────────────────────
        ("HG", "1/144", "Full Armor Gundam (Thunderbolt)", "Gundam Thunderbolt", "", "standard", 30),
        ("HG", "1/144", "Psycho Zaku Mk-II (Thunderbolt)", "Gundam Thunderbolt", "", "standard", 35),
        ("HG", "1/144", "Acguy (Thunderbolt)", "Gundam Thunderbolt", "", "standard", 22),
        ("HG", "1/144", "GM (Thunderbolt)", "Gundam Thunderbolt", "", "standard", 18),

        # ── HG — HGUC Popular ──────────────────────────────────────────
        ("HG", "1/144", "Sinanju", "Gundam Unicorn", "HGUC", "standard", 28),
        ("HG", "1/144", "Unicorn Gundam (Destroy Mode)", "Gundam Unicorn", "HGUC", "standard", 22),
        ("HG", "1/144", "Full Armor Unicorn Gundam (HGUC)", "Gundam Unicorn", "HGUC", "standard", 30),
        ("HG", "1/144", "Kshatriya", "Gundam Unicorn", "HGUC", "standard", 38),
        ("HG", "1/144", "Rozen Zulu", "Gundam Unicorn", "HGUC", "standard", 28),
        ("HG", "1/144", "Byarlant Custom", "Gundam Unicorn", "HGUC", "standard", 25),
        ("HG", "1/144", "Zaku I Sniper Type", "Gundam Unicorn", "HGUC", "standard", 16),
        ("HG", "1/144", "Gouf Custom", "08th MS Team", "HGUC", "standard", 16),
        ("HG", "1/144", "GM Ground Type", "08th MS Team", "HGUC", "standard", 14),
        ("HG", "1/144", "Ez-8 Gundam", "08th MS Team", "HGUC", "standard", 16),
        ("HG", "1/144", "Gundam Ground Type", "08th MS Team", "HGUC", "standard", 16),
        ("HG", "1/144", "Blue Destiny Unit 1", "Blue Destiny", "HGUC", "standard", 16),
        ("HG", "1/144", "Blue Destiny Unit 2", "Blue Destiny", "HGUC", "standard", 16),
        ("HG", "1/144", "Blue Destiny Unit 3", "Blue Destiny", "HGUC", "standard", 16),
        ("HG", "1/144", "Zeta Gundam", "Zeta Gundam", "HGUC", "standard", 18),
        ("HG", "1/144", "The-O", "Zeta Gundam", "HGUC", "standard", 35),
        ("HG", "1/144", "Psycho Gundam", "Zeta Gundam", "HGUC", "mid", 60),
        ("HG", "1/144", "Nu Gundam", "Char's Counterattack", "HGUC", "standard", 20),
        ("HG", "1/144", "Sazabi", "Char's Counterattack", "HGUC", "standard", 32),
        ("HG", "1/144", "Nightingale", "Char's Counterattack", "HGUC", "mid", 55),

        # ── SD Full Lines ───────────────────────────────────────────────
        ("SD CS", "SD", "Zeta Gundam (Cross Silhouette)", "Zeta Gundam", "Cross Silhouette", "standard", 14),
        ("SD CS", "SD", "Sisquiede (Cross Silhouette)", "SD Gundam G Generation", "Cross Silhouette", "standard", 14),
        ("SD CS", "SD", "Gundam Aerial (Cross Silhouette)", "Gundam: Witch from Mercury", "Cross Silhouette", "standard", 14),
        ("SD CS", "SD", "Zaku II (Cross Silhouette)", "Mobile Suit Gundam", "Cross Silhouette", "standard", 12),
        ("SD CS", "SD", "Silhouette Booster (White)", "SD Gundam", "Cross Silhouette", "standard", 6),
        ("SD CS", "SD", "Silhouette Booster (Gray)", "SD Gundam", "Cross Silhouette", "standard", 6),
        ("SD EX-Standard", "SD", "RX-78-2 Gundam", "Mobile Suit Gundam", "EX-Standard", "standard", 8),
        ("SD EX-Standard", "SD", "Destiny Gundam", "Gundam SEED Destiny", "EX-Standard", "standard", 8),
        ("SD EX-Standard", "SD", "00 Gundam", "Gundam 00", "EX-Standard", "standard", 8),
        ("SD EX-Standard", "SD", "Gundam Aerial", "Gundam: Witch from Mercury", "EX-Standard", "standard", 8),
        ("SD EX-Standard", "SD", "Sazabi", "Char's Counterattack", "EX-Standard", "standard", 8),

        # ── 30 Minutes Missions Full Range ──────────────────────────────
        ("30MM", "1/144", "eEXM-17 Alto (Green)", "30 Minutes Missions", "", "standard", 10),
        ("30MM", "1/144", "eEXM-17 Alto (Brown)", "30 Minutes Missions", "", "standard", 10),
        ("30MM", "1/144", "eEXM-17 Alto (Red)", "30 Minutes Missions", "", "standard", 10),
        ("30MM", "1/144", "eEXM-21 Rabiot (Red)", "30 Minutes Missions", "", "standard", 12),
        ("30MM", "1/144", "eEXM-21 Rabiot (Purple)", "30 Minutes Missions", "", "standard", 12),
        ("30MM", "1/144", "bEXM-15 Portanova (White)", "30 Minutes Missions", "", "standard", 12),
        ("30MM", "1/144", "bEXM-15 Portanova (Dark Gray)", "30 Minutes Missions", "", "standard", 12),
        ("30MM", "1/144", "bEXM-14T Cielnova (White)", "30 Minutes Missions", "", "standard", 12),
        ("30MM", "1/144", "bEXM-14T Cielnova (Green)", "30 Minutes Missions", "", "standard", 12),
        ("30MM", "1/144", "eEXM-30 Espossito (Beta)", "30 Minutes Missions", "", "standard", 14),
        ("30MM", "1/144", "eEXM-GIG-01 Provedel Type-Rex01", "30 Minutes Missions", "", "standard", 20),
        ("30MM", "1/144", "eEXM-GIG-02 Provedel Type-Rex02", "30 Minutes Missions", "", "standard", 20),
        ("30MM", "1/144", "Option Armor for Commander (Alto)", "30 Minutes Missions", "Option", "standard", 6),
        ("30MM", "1/144", "Option Weapon Set 1", "30 Minutes Missions", "Option", "standard", 6),
        ("30MM", "1/144", "Extended Armament Vehicle (Tank)", "30 Minutes Missions", "EAV", "standard", 14),
        ("30MM", "1/144", "Extended Armament Vehicle (Attack Sub)", "30 Minutes Missions", "EAV", "standard", 14),

        # ── Entry Grade Expanded ────────────────────────────────────────
        ("Entry Grade", "1/144", "Gundam Barbatos", "Iron-Blooded Orphans", "Entry Grade", "standard", 8),
        ("Entry Grade", "1/144", "Wing Gundam Zero EW", "Gundam Wing", "Entry Grade", "standard", 10),
        ("Entry Grade", "1/144", "Freedom Gundam", "Gundam SEED", "Entry Grade", "standard", 10),
        ("Entry Grade", "1/144", "Unicorn Gundam (Destroy Mode)", "Gundam Unicorn", "Entry Grade", "standard", 10),
        ("Entry Grade", "1/144", "RX-93 Nu Gundam", "Char's Counterattack", "Entry Grade", "standard", 10),

        # ── RE/100 Grade ───────────────────────────────────────────────
        ("RE/100", "1/100", "Nightingale", "Char's Counterattack", "RE/100", "mid", 65),
        ("RE/100", "1/100", "Dijeh", "Zeta Gundam", "RE/100", "mid", 45),
        ("RE/100", "1/100", "Bawoo", "Gundam ZZ", "RE/100", "mid", 48),
        ("RE/100", "1/100", "Hamma Hamma", "Gundam ZZ", "RE/100", "mid", 50),
        ("RE/100", "1/100", "GP04G Gerbera", "Gundam 0083", "RE/100", "mid", 48),
        ("RE/100", "1/100", "Efreet Kai", "Blue Destiny", "RE/100", "mid", 45),
        ("RE/100", "1/100", "Vigna Ghina", "Gundam F91", "RE/100", "mid", 42),
        ("RE/100", "1/100", "Gun EZ", "Victory Gundam", "RE/100", "mid", 42),
        ("RE/100", "1/100", "Jagd Doga", "Char's Counterattack", "RE/100", "mid", 48),
        ("RE/100", "1/100", "Zaku II FZ (Kai)", "Gundam 0080", "RE/100", "mid", 42),
        ("RE/100", "1/100", "Haze'n-thley II", "Advance of Zeta", "RE/100", "mid", 50),
        ("RE/100", "1/100", "Gundam Mark III", "Z-MSV", "RE/100", "mid", 48),

        # ── Full Mechanics Expanded ────────────────────────────────────
        ("Full Mechanics", "1/100", "Mighty Strike Freedom", "Gundam SEED Freedom", "", "mid", 55),
        ("Full Mechanics", "1/100", "Rising Freedom Gundam", "Gundam SEED Freedom", "", "mid", 48),
        ("Full Mechanics", "1/100", "Immortal Justice Gundam", "Gundam SEED Freedom", "", "mid", 48),
        ("Full Mechanics", "1/100", "Schwarzette", "Gundam: Witch from Mercury", "", "mid", 45),
        ("Full Mechanics", "1/100", "Gundam Calibarn", "Gundam: Witch from Mercury", "", "mid", 50),

        # ── Metal Build Full Line ──────────────────────────────────────
        ("Metal Build", "1/100", "Gundam Seed Providence", "Gundam SEED", "Metal Build", "grail", 340),
        ("Metal Build", "1/100", "Justice Gundam", "Gundam SEED", "Metal Build", "grail", 320),
        ("Metal Build", "1/100", "Blitz Gundam", "Gundam SEED", "Metal Build", "grail", 280),
        ("Metal Build", "1/100", "Buster Gundam", "Gundam SEED", "Metal Build", "grail", 280),
        ("Metal Build", "1/100", "Duel Gundam Assault Shroud", "Gundam SEED", "Metal Build", "grail", 290),
        ("Metal Build", "1/100", "Gundam Dynames Repair III", "Gundam 00", "Metal Build", "grail", 320),
        ("Metal Build", "1/100", "Gundam Kyrios", "Gundam 00", "Metal Build", "grail", 300),
        ("Metal Build", "1/100", "Gundam Virtue", "Gundam 00", "Metal Build", "grail", 330),
        ("Metal Build", "1/100", "00 Qan[T] Full Saber", "Gundam 00", "Metal Build", "grail", 380),
        ("Metal Build", "1/100", "Great Mazinger", "Mazinger", "Metal Build", "grail", 300),
        ("Metal Build", "1/100", "Mazinger Z", "Mazinger", "Metal Build", "grail", 300),
        ("Metal Build", "1/100", "Lancelot Albion", "Code Geass", "Metal Build", "grail", 350),
        ("Metal Build", "1/100", "Crossbone Gundam X3", "Crossbone Gundam", "Metal Build", "grail", 280),

        # ── Robot Damashii / Metal Robot Spirits Expanded ───────────────
        ("Metal Robot Spirits", "N/A", "Strike Freedom Gundam", "Gundam SEED Destiny", "Metal Robot Spirits", "high", 130),
        ("Metal Robot Spirits", "N/A", "Destiny Gundam", "Gundam SEED Destiny", "Metal Robot Spirits", "high", 120),
        ("Metal Robot Spirits", "N/A", "Wing Gundam Zero", "Gundam Wing", "Metal Robot Spirits", "high", 130),
        ("Metal Robot Spirits", "N/A", "00 Raiser + GN Sword III", "Gundam 00", "Metal Robot Spirits", "high", 140),
        ("Metal Robot Spirits", "N/A", "Nu Gundam", "Char's Counterattack", "Metal Robot Spirits", "high", 150),
        ("Metal Robot Spirits", "N/A", "Sazabi", "Char's Counterattack", "Metal Robot Spirits", "high", 140),
        ("Metal Robot Spirits", "N/A", "Crossbone Gundam X1 Full Cloth", "Crossbone Gundam", "Metal Robot Spirits", "high", 130),
        ("Metal Robot Spirits", "N/A", "Knight Gundam", "SD Gundam", "Metal Robot Spirits", "high", 140),
        ("Metal Robot Spirits", "N/A", "Full Armor Knight Gundam", "SD Gundam", "Metal Robot Spirits", "high", 160),
        ("Metal Robot Spirits", "N/A", "Mighty Strike Freedom Gundam", "Gundam SEED Freedom", "Metal Robot Spirits", "high", 150),
        ("Robot Spirits", "N/A", "RX-78-2 Gundam ver. A.N.I.M.E.", "Mobile Suit Gundam", "Robot Spirits", "mid", 50),
        ("Robot Spirits", "N/A", "Zaku II ver. A.N.I.M.E.", "Mobile Suit Gundam", "Robot Spirits", "mid", 48),
        ("Robot Spirits", "N/A", "Char's Zaku II ver. A.N.I.M.E.", "Mobile Suit Gundam", "Robot Spirits", "mid", 50),
        ("Robot Spirits", "N/A", "Gouf ver. A.N.I.M.E.", "Mobile Suit Gundam", "Robot Spirits", "mid", 48),
        ("Robot Spirits", "N/A", "Dom ver. A.N.I.M.E.", "Mobile Suit Gundam", "Robot Spirits", "mid", 48),
        ("Robot Spirits", "N/A", "Guncannon ver. A.N.I.M.E.", "Mobile Suit Gundam", "Robot Spirits", "mid", 48),
        ("Robot Spirits", "N/A", "Gundam NT-1 ver. A.N.I.M.E.", "Gundam 0080", "Robot Spirits", "mid", 55),
        ("Robot Spirits", "N/A", "Kampfer ver. A.N.I.M.E.", "Gundam 0080", "Robot Spirits", "mid", 55),

        # ── P-Bandai Exclusives Full ────────────────────────────────────
        ("MG", "1/100", "Wing Gundam Zero EW (P-Bandai Special Coating)", "Gundam Wing", "P-Bandai", "high", 130),
        ("MG", "1/100", "Turn A Gundam (Moonlight Butterfly) (P-Bandai)", "Turn A Gundam", "P-Bandai", "high", 110),
        ("MG", "1/100", "Gundam AGE-1 Full Glansa (P-Bandai)", "Gundam AGE", "P-Bandai", "high", 100),
        ("MG", "1/100", "Gundam AGE-2 Dark Hound (P-Bandai)", "Gundam AGE", "P-Bandai", "high", 105),
        ("MG", "1/100", "Zeta Plus C1 (P-Bandai)", "Gundam Sentinel", "P-Bandai", "high", 110),
        ("MG", "1/100", "Gundam TR-1 Advanced Hazel (P-Bandai)", "Advance of Zeta", "P-Bandai", "high", 120),
        ("RG", "1/144", "Astray Gold Frame Amatsu Hana (P-Bandai)", "Gundam SEED Astray", "P-Bandai", "high", 70),
        ("RG", "1/144", "Nu Gundam HWS (P-Bandai)", "Char's Counterattack", "P-Bandai", "high", 80),
        ("RG", "1/144", "Freedom Gundam (Deactive Mode) (P-Bandai)", "Gundam SEED", "P-Bandai", "mid", 55),
        ("HG", "1/144", "Advanced GN-X (P-Bandai)", "Gundam 00", "P-Bandai", "mid", 38),
        ("HG", "1/144", "Reborns Gundam (P-Bandai)", "Gundam 00", "P-Bandai", "mid", 40),
        ("HG", "1/144", "Gundam Barbatos Complete Form (P-Bandai)", "Iron-Blooded Orphans", "P-Bandai", "mid", 42),
        ("PG", "1/60", "Strike Rouge + Skygrasper (P-Bandai)", "Gundam SEED", "P-Bandai", "grail", 350),
    ]

    catalog = []
    for grade, scale, name, series, variant, tier, price in kits:
        catalog.append({
            "grade": grade,
            "scale": scale,
            "name": name,
            "series": series,
            "variant": variant,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    grade = item["grade"]
    name = item["name"]
    series = item["series"]
    variant = item["variant"]
    scale = item["scale"]

    title_parts = [grade, name]
    if variant:
        title_parts.append(f"({variant})")

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{grade}-{name}" + (f"-{variant}" if variant else "")),
        title=" ".join(title_parts),
        set_code=slugify(series),
        brand="Bandai",
        rarity=item["rarity_tier"].title(),
        notes=f"{grade} {scale} | {series}" + (f" | {variant}" if variant else ""),
        attributes_json={
            "grade": grade,
            "scale": scale,
            "series": series,
            "variant": variant,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    variant = item["variant"]
    is_p_bandai = "P-Bandai" in variant if variant else False
    is_ver_ka = "Ver.Ka" in variant if variant else False

    grade = item["grade"]
    grade_scores = {
        "PG": 0.85,
        "MGEX": 0.8,
        "MG": 0.5,
        "RG": 0.4,
        "HG": 0.2,
        "SD CS": 0.15,
        "SD EX-Standard": 0.12,
        "SD World Heroes": 0.15,
        "Mega Size": 0.55,
        "Metal Build": 0.9,
        "Metal Robot Spirits": 0.7,
        "Full Mechanics": 0.45,
        "Vintage": 0.6,
        "Entry Grade": 0.1,
        "30MM": 0.15,
        "RE/100": 0.45,
        "Robot Spirits": 0.6,
    }

    edition_score = grade_scores.get(grade, 0.4)
    if is_p_bandai:
        edition_score = min(1.0, edition_score + 0.3)
    if is_ver_ka:
        edition_score = min(1.0, edition_score + 0.15)

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_score,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Gunpla catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Gunpla Import ===")

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

    logger.info(f"\n=== Gunpla Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
