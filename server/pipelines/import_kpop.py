"""
Import K-pop merchandise catalog.

Layer 1 (Catalog):  Curated K-pop photocards, albums & exclusives → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated data from secondary market (Mercari, eBay, ktown4u resale)
- 570+ items covering 31 groups: BTS, Blackpink, Stray Kids, ATEEZ, Enhypen,
  Seventeen, NewJeans, EXO, TWICE, NCT, aespa, Le Sserafim, IVE, ITZY,
  Red Velvet, GOT7, TXT, (G)I-DLE, NMIXX, Dreamcatcher, Mamamoo, SHINee,
  BIGBANG, 2NE1, Super Junior, ZEROBASEONE, BOYNEXTDOOR, RIIZE
  — albums, photocards, merch, tour exclusives, vinyl, original pressings

Usage:
    python -m pipelines.import_kpop [--dry-run]
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

CATEGORY = "kpop_merch"


def get_curated_catalog() -> list[dict]:
    """Curated K-pop merchandise catalog covering albums, photocards & exclusives."""

    # (group, item_type, name, variant, rarity_tier, price_eur)
    # rarity_tier: grail (>200), high (80-200), mid (30-80), standard (<30)

    items = [
        # ═══════════════════════════════════════════════════════════════════
        # BTS — Photocards
        # ═══════════════════════════════════════════════════════════════════
        ("BTS", "photocard", "Jungkook Fansign Photocard", "Fansign Event", "grail", 450),
        ("BTS", "photocard", "V Fansign Photocard", "Fansign Event", "grail", 420),
        ("BTS", "photocard", "Jimin Butter Lucky Draw", "Lucky Draw", "grail", 380),
        ("BTS", "photocard", "SUGA D-Day POB Photocard", "Pre-order Benefit", "high", 120),
        ("BTS", "photocard", "Jin The Astronaut Photocard", "Album POB", "high", 90),
        ("BTS", "photocard", "RM Indigo Weverse POB", "Weverse Exclusive", "mid", 55),
        ("BTS", "photocard", "J-Hope Jack In The Box POB", "Album POB", "mid", 50),
        ("BTS", "photocard", "BTS Proof Standard Photocard", "Standard", "standard", 8),

        # BTS — Albums
        ("BTS", "album", "BTS Proof Collector's Edition", "Collector's Edition", "high", 180),
        ("BTS", "album", "BTS Proof Standard", "Standard", "standard", 22),
        ("BTS", "album", "Map of the Soul: 7 (Version 4)", "Limited Version", "high", 85),
        ("BTS", "album", "Map of the Soul: 7", "Standard", "standard", 20),
        ("BTS", "album", "BE Deluxe Edition", "Deluxe", "high", 95),
        ("BTS", "album", "BE Essential Edition", "Standard", "standard", 18),
        ("BTS", "album", "BTS Wings", "Standard", "mid", 45),
        ("BTS", "album", "BTS Young Forever Night Version", "Night Ver.", "high", 120),

        # BTS — Solo Albums (NEW)
        ("BTS", "album", "V - Layover", "Standard", "standard", 20),
        ("BTS", "album", "V - Layover Weverse Albums Ver.", "Weverse Exclusive", "mid", 35),
        ("BTS", "album", "Jimin - FACE", "Standard", "standard", 18),
        ("BTS", "album", "Jimin - FACE Weverse Albums Ver.", "Weverse Exclusive", "mid", 32),
        ("BTS", "album", "SUGA - D-Day", "Standard", "standard", 20),
        ("BTS", "album", "SUGA - D-Day Weverse Albums Ver.", "Weverse Exclusive", "mid", 35),
        ("BTS", "album", "j-hope - Jack In The Box", "Standard", "standard", 22),
        ("BTS", "album", "j-hope - Jack In The Box LP", "Limited Vinyl", "high", 95),
        ("BTS", "album", "RM - Indigo", "Standard", "standard", 20),
        ("BTS", "album", "RM - Indigo Postcard Edition", "Limited", "mid", 40),
        ("BTS", "album", "Jin - The Astronaut", "Standard", "standard", 18),
        ("BTS", "album", "Jungkook - GOLDEN", "Standard", "standard", 20),
        ("BTS", "album", "Jungkook - GOLDEN Weverse Albums Ver.", "Weverse Exclusive", "mid", 38),

        # BTS — Merch & Collectibles
        ("BTS", "merch", "BTS Artist Made Collection V Bag", "Weverse Exclusive", "high", 80),
        ("BTS", "merch", "BTS Official Light Stick SE", "Weverse Exclusive", "mid", 65),
        ("BTS", "merch", "BTS Season's Greetings 2024", "Official", "mid", 55),
        ("BTS", "merch", "BTS Memories of 2022 DVD", "Limited", "high", 85),
        ("BTS", "merch", "BTS Memories of 2021 Blu-ray", "Limited", "high", 95),
        ("BTS", "merch", "BTS Season's Greetings 2023", "Official", "mid", 50),
        ("BTS", "merch", "BTS Map of the Soul ON:E DVD", "Limited", "high", 80),
        ("BTS", "merch", "BTS Permission to Dance Concert DVD", "Limited", "high", 75),

        # BTS — Vinyl & Original Pressings
        ("BTS", "album", "BTS Map of the Soul: 7 Vinyl LP", "Limited Vinyl", "high", 140),
        ("BTS", "album", "BTS Wings (Sealed, Original Pressing)", "Original Pressing", "high", 160),
        ("BTS", "album", "BTS HYYH Pt.1 (Original Pressing)", "Original Pressing", "high", 180),
        ("BTS", "album", "BTS HYYH Pt.2 (Original Pressing)", "Original Pressing", "high", 175),
        ("BTS", "album", "BTS Love Yourself: Tear Y Version Vinyl", "Limited Vinyl", "high", 110),
        ("BTS", "album", "BTS Love Yourself: Tear O Version Vinyl", "Limited Vinyl", "high", 110),
        ("BTS", "album", "BTS Love Yourself: Tear U Version Vinyl", "Limited Vinyl", "high", 115),
        ("BTS", "album", "BTS Love Yourself: Tear R Version Vinyl", "Limited Vinyl", "high", 120),
        ("BTS", "album", "BTS BE Deluxe Edition w/ Photocard Set", "Deluxe", "high", 105),

        # BTS — Lightstick & Membership
        ("BTS", "merch", "BTS Official Light Stick Map of the Soul SE", "Limited", "high", 95),
        ("BTS", "merch", "BTS Official Light Stick Ver. 4 (Army Bomb SE)", "Limited", "high", 85),
        ("BTS", "merch", "BTS ARMY Membership Kit 3rd Term", "Limited", "high", 130),
        ("BTS", "merch", "BTS ARMY Membership Kit 4th Term", "Limited", "high", 110),

        # BTS — Season's Greetings & Memories
        ("BTS", "merch", "BTS Season's Greetings 2020", "Official", "mid", 65),
        ("BTS", "merch", "BTS Season's Greetings 2021", "Official", "mid", 60),
        ("BTS", "merch", "BTS Season's Greetings 2022", "Official", "mid", 55),
        ("BTS", "merch", "BTS Memories of 2019 DVD", "Limited", "high", 100),
        ("BTS", "merch", "BTS Memories of 2020 Blu-ray", "Limited", "high", 110),

        # BTS — Concert Films
        ("BTS", "merch", "BTS Permission to Dance On Stage Blu-ray", "Limited", "high", 90),
        ("BTS", "merch", "BTS Yet To Come in Busan Blu-ray", "Limited", "high", 80),

        # BTS — Solo Vinyl Editions
        ("BTS", "album", "Jin - The Astronaut Vinyl LP", "Limited Vinyl", "high", 85),
        ("BTS", "album", "RM - Right Place, Wrong Person", "Standard", "standard", 22),
        ("BTS", "album", "RM - Right Place, Wrong Person Weverse Ver.", "Weverse Exclusive", "mid", 38),
        ("BTS", "album", "V - Layover Vinyl LP", "Limited Vinyl", "high", 90),
        ("BTS", "album", "Jimin - FACE Vinyl LP", "Limited Vinyl", "high", 88),
        ("BTS", "album", "j-hope - Jack In The Box LP (Limited Ed.)", "Limited Vinyl", "high", 100),
        ("BTS", "album", "SUGA - D-DAY Vinyl LP", "Limited Vinyl", "high", 95),

        # BTS — Pop-Up & Promo Exclusives
        ("BTS", "merch", "BTS Pop-Up: Space of BTS Mini Figure Set", "Limited", "high", 75),
        ("BTS", "merch", "BTS Pop-Up: Space of BTS Poster Collection", "Limited", "mid", 45),
        ("BTS", "photocard", "BTS x McDonald's Meal Photocard Set", "Collaboration", "mid", 55),

        # ═══════════════════════════════════════════════════════════════════
        # Blackpink — Albums
        # ═══════════════════════════════════════════════════════════════════
        ("Blackpink", "album", "The Album Version 3 (Lisa)", "Limited", "mid", 55),
        ("Blackpink", "album", "The Album Standard", "Standard", "standard", 20),
        ("Blackpink", "album", "Born Pink Digipack Lisa", "Digipack", "mid", 35),
        ("Blackpink", "album", "Born Pink Limited Edition Vinyl", "Limited Vinyl", "high", 130),
        ("Blackpink", "album", "Born Pink Standard", "Standard", "standard", 18),

        # Blackpink — Photocards
        ("Blackpink", "photocard", "Jennie Fansign Photocard", "Fansign Event", "grail", 500),
        ("Blackpink", "photocard", "Lisa Signed Polaroid", "Signed", "grail", 350),

        # Blackpink — Solo Albums (NEW)
        ("Blackpink", "album", "ROSE - R", "Standard", "standard", 22),
        ("Blackpink", "album", "ROSE - R Vinyl LP", "Limited Vinyl", "high", 85),
        ("Blackpink", "album", "Lisa - LALISA", "Standard", "standard", 20),
        ("Blackpink", "album", "Lisa - LALISA Vinyl LP", "Limited Vinyl", "high", 90),
        ("Blackpink", "album", "Jennie - Solo Photobook Special Ed.", "Limited", "high", 110),
        ("Blackpink", "album", "Jisoo - ME (Red Ver.)", "Limited", "mid", 40),
        ("Blackpink", "album", "Jisoo - ME Standard", "Standard", "standard", 20),

        # Blackpink — Photocards (NEW)
        ("Blackpink", "photocard", "Rose Video Call Fansign", "Fansign Event", "grail", 400),
        ("Blackpink", "photocard", "Jisoo ME Lucky Draw", "Lucky Draw", "high", 150),
        ("Blackpink", "photocard", "Lisa LALISA POB Photocard", "Pre-order Benefit", "mid", 60),
        ("Blackpink", "photocard", "Blackpink Born Pink Standard Photocard", "Standard", "standard", 12),

        # Blackpink — Merch (NEW)
        ("Blackpink", "merch", "Blackpink Official Lightstick Ver.2", "Official", "mid", 55),
        ("Blackpink", "merch", "Born Pink World Tour Hoodie", "Tour Exclusive", "mid", 75),
        ("Blackpink", "merch", "Born Pink World Tour Photobook", "Tour Exclusive", "high", 90),
        ("Blackpink", "merch", "Blackpink The Movie DVD", "Limited", "mid", 45),

        # ═══════════════════════════════════════════════════════════════════
        # Stray Kids — Albums
        # ═══════════════════════════════════════════════════════════════════
        ("Stray Kids", "album", "ATE Limited Edition", "Limited", "mid", 45),
        ("Stray Kids", "album", "ATE Standard", "Standard", "standard", 18),
        ("Stray Kids", "album", "5-STAR Limited Star Ver.", "Limited Star", "mid", 42),
        ("Stray Kids", "album", "5-STAR Standard", "Standard", "standard", 18),
        ("Stray Kids", "album", "MAXIDENT Limited Edition", "Limited", "mid", 40),
        ("Stray Kids", "album", "MAXIDENT Standard", "Standard", "standard", 16),
        ("Stray Kids", "album", "ODDINARY Limited Edition", "Limited", "mid", 38),
        ("Stray Kids", "album", "ODDINARY Jewel Case", "Jewel Case", "standard", 15),
        ("Stray Kids", "album", "NOEASY Limited Edition", "Limited", "high", 85),
        ("Stray Kids", "album", "NOEASY Standard", "Standard", "standard", 20),
        ("Stray Kids", "album", "IN LIFE Limited Edition", "Limited", "high", 95),
        ("Stray Kids", "album", "GO LIVE Limited Edition", "Limited", "high", 90),
        ("Stray Kids", "album", "Clé: LEVANTER Limited", "Limited", "high", 110),
        ("Stray Kids", "album", "I am NOT Standard", "Standard", "mid", 45),
        ("Stray Kids", "album", "Mixtape Standard", "Standard", "high", 130),

        # Stray Kids — Photocards (by member)
        ("Stray Kids", "photocard", "Bang Chan Video Call Fansign", "Fansign Event", "grail", 250),
        ("Stray Kids", "photocard", "Bang Chan POB Photocard", "Pre-order Benefit", "mid", 40),
        ("Stray Kids", "photocard", "Lee Know Video Call Fansign", "Fansign Event", "grail", 320),
        ("Stray Kids", "photocard", "Lee Know Lucky Draw", "Lucky Draw", "high", 150),
        ("Stray Kids", "photocard", "Changbin Fansign Photocard", "Fansign Event", "high", 180),
        ("Stray Kids", "photocard", "Changbin POB Photocard", "Pre-order Benefit", "mid", 35),
        ("Stray Kids", "photocard", "Hyunjin Video Call Fansign", "Fansign Event", "grail", 380),
        ("Stray Kids", "photocard", "Hyunjin POB Photocard", "Pre-order Benefit", "mid", 45),
        ("Stray Kids", "photocard", "Hyunjin Lucky Draw", "Lucky Draw", "high", 200),
        ("Stray Kids", "photocard", "Han Video Call Fansign", "Fansign Event", "grail", 260),
        ("Stray Kids", "photocard", "Han POB Photocard", "Pre-order Benefit", "mid", 38),
        ("Stray Kids", "photocard", "Felix Video Call Fansign", "Fansign Event", "grail", 350),
        ("Stray Kids", "photocard", "Felix Lucky Draw", "Lucky Draw", "high", 180),
        ("Stray Kids", "photocard", "Felix POB Photocard", "Pre-order Benefit", "mid", 50),
        ("Stray Kids", "photocard", "Seungmin Fansign Photocard", "Fansign Event", "high", 170),
        ("Stray Kids", "photocard", "Seungmin POB Photocard", "Pre-order Benefit", "mid", 30),
        ("Stray Kids", "photocard", "I.N Fansign Photocard", "Fansign Event", "high", 160),
        ("Stray Kids", "photocard", "I.N POB Photocard", "Pre-order Benefit", "standard", 25),

        # Stray Kids — Merch & Collectibles
        ("Stray Kids", "merch", "SKZ Nachibong Ver.2 Lightstick", "Official", "mid", 45),
        ("Stray Kids", "merch", "MANIAC World Tour Photobook", "Tour Exclusive", "high", 80),
        ("Stray Kids", "merch", "Stray Kids x SLBS Skzoo Plush", "Collaboration", "mid", 35),
        ("Stray Kids", "merch", "Stray Kids 2nd World Tour Merch Set", "Tour Exclusive", "high", 120),
        ("Stray Kids", "merch", "SKZ REPLAY DVD Limited", "Limited", "high", 90),
        ("Stray Kids", "merch", "Stray Kids SKZOO Standing Doll Set", "Official", "mid", 55),

        # ═══════════════════════════════════════════════════════════════════
        # ATEEZ
        # ═══════════════════════════════════════════════════════════════════
        ("ATEEZ", "album", "The World EP.2: Outlaw", "Standard", "standard", 18),
        ("ATEEZ", "album", "Treasure EP.FIN Limited", "Limited", "mid", 35),
        ("ATEEZ", "photocard", "Hongjoong Fansign Photocard", "Fansign Event", "high", 180),
        ("ATEEZ", "album", "The World EP.1: Movement", "Standard", "standard", 18),
        ("ATEEZ", "album", "ZERO: FEVER Part.3", "Standard", "standard", 16),
        ("ATEEZ", "album", "ZERO: FEVER Epilogue", "Standard", "standard", 16),
        ("ATEEZ", "album", "Treasure EP.3 Limited", "Limited", "mid", 40),
        ("ATEEZ", "album", "GOLDEN HOUR Part.1", "Standard", "standard", 20),
        ("ATEEZ", "album", "GOLDEN HOUR Part.1 Diary Ver.", "Limited", "mid", 38),
        ("ATEEZ", "photocard", "San Video Call Fansign", "Fansign Event", "grail", 280),
        ("ATEEZ", "photocard", "Wooyoung Video Call Fansign", "Fansign Event", "grail", 260),
        ("ATEEZ", "photocard", "Seonghwa Lucky Draw", "Lucky Draw", "high", 140),
        ("ATEEZ", "photocard", "Mingi POB Photocard", "Pre-order Benefit", "mid", 45),
        ("ATEEZ", "photocard", "ATEEZ Standard Album Photocard", "Standard", "standard", 8),
        ("ATEEZ", "merch", "ATEEZ Official Lightstick Ver.2", "Official", "mid", 50),
        ("ATEEZ", "merch", "THE FELLOWSHIP Tour Photobook", "Tour Exclusive", "high", 85),
        ("ATEEZ", "merch", "ATEEZ x ANITEEZ Plush Set", "Collaboration", "mid", 40),

        # ═══════════════════════════════════════════════════════════════════
        # Enhypen (expanded)
        # ═══════════════════════════════════════════════════════════════════
        ("Enhypen", "album", "Dark Blood ENGENE Ver.", "Limited", "mid", 30),
        ("Enhypen", "album", "Dimension: Dilemma", "Standard", "standard", 16),
        ("Enhypen", "photocard", "Sunghoon Lucky Draw", "Lucky Draw", "high", 100),
        ("Enhypen", "album", "DARK BLOOD Standard", "Standard", "standard", 18),
        ("Enhypen", "album", "ORANGE BLOOD Standard", "Standard", "standard", 18),
        ("Enhypen", "album", "ORANGE BLOOD ENGENE Ver.", "Limited", "mid", 32),
        ("Enhypen", "album", "ROMANCE: UNTOLD", "Standard", "standard", 20),
        ("Enhypen", "album", "ROMANCE: UNTOLD Weverse Albums Ver.", "Weverse Exclusive", "mid", 35),
        ("Enhypen", "album", "Dimension: Answer Limited", "Limited", "mid", 35),
        ("Enhypen", "album", "BORDER: CARNIVAL", "Standard", "standard", 16),
        ("Enhypen", "album", "BORDER: DAY ONE", "Standard", "standard", 18),
        ("Enhypen", "photocard", "Ni-ki Video Call Fansign", "Fansign Event", "grail", 220),
        ("Enhypen", "photocard", "Sunoo Video Call Fansign", "Fansign Event", "grail", 200),
        ("Enhypen", "photocard", "Heeseung Lucky Draw", "Lucky Draw", "high", 120),
        ("Enhypen", "photocard", "Jay POB Photocard", "Pre-order Benefit", "mid", 40),
        ("Enhypen", "photocard", "Jake POB Photocard", "Pre-order Benefit", "mid", 45),
        ("Enhypen", "photocard", "Jungwon POB Photocard", "Pre-order Benefit", "mid", 42),
        ("Enhypen", "photocard", "Enhypen Standard Photocard", "Standard", "standard", 7),
        ("Enhypen", "merch", "Enhypen Official Lightstick", "Official", "mid", 48),
        ("Enhypen", "merch", "MANIFESTO World Tour Merch Set", "Tour Exclusive", "high", 85),

        # ═══════════════════════════════════════════════════════════════════
        # Seventeen (expanded)
        # ═══════════════════════════════════════════════════════════════════
        ("Seventeen", "album", "FML Weverse Albums Ver.", "Weverse Exclusive", "standard", 22),
        ("Seventeen", "album", "FML Standard", "Standard", "standard", 20),
        ("Seventeen", "album", "FML Deluxe Ver.", "Deluxe", "mid", 45),
        ("Seventeen", "album", "SEVENTEENTH HEAVEN Standard", "Standard", "standard", 20),
        ("Seventeen", "album", "SEVENTEENTH HEAVEN Carat Ver.", "Limited", "mid", 42),
        ("Seventeen", "album", "Attacca Standard", "Standard", "standard", 18),
        ("Seventeen", "album", "Attacca Op.3", "Limited", "mid", 35),
        ("Seventeen", "album", "Face the Sun Carat Ver.", "Limited", "mid", 40),
        ("Seventeen", "album", "Face the Sun Standard", "Standard", "standard", 18),
        ("Seventeen", "album", "Sector 17 Compact Ver.", "Standard", "standard", 16),
        ("Seventeen", "album", "An Ode Limited", "Limited", "high", 80),
        ("Seventeen", "album", "You Make My Day Follow Ver.", "Standard", "standard", 22),
        ("Seventeen", "album", "SEVENTEEN BEST ALBUM 17 IS RIGHT HERE", "Standard", "standard", 22),
        ("Seventeen", "photocard", "Mingyu Video Call Fansign", "Fansign Event", "grail", 350),
        ("Seventeen", "photocard", "Wonwoo Video Call Fansign", "Fansign Event", "grail", 320),
        ("Seventeen", "photocard", "Vernon Video Call Fansign", "Fansign Event", "grail", 280),
        ("Seventeen", "photocard", "Jeonghan Lucky Draw", "Lucky Draw", "high", 180),
        ("Seventeen", "photocard", "Joshua Lucky Draw", "Lucky Draw", "high", 150),
        ("Seventeen", "photocard", "S.Coups POB Photocard", "Pre-order Benefit", "mid", 45),
        ("Seventeen", "photocard", "Hoshi POB Photocard", "Pre-order Benefit", "mid", 50),
        ("Seventeen", "photocard", "Woozi POB Photocard", "Pre-order Benefit", "mid", 48),
        ("Seventeen", "photocard", "DK POB Photocard", "Pre-order Benefit", "mid", 35),
        ("Seventeen", "photocard", "Seventeen Standard Photocard", "Standard", "standard", 8),
        ("Seventeen", "merch", "Caratbong Ver.3 Lightstick", "Official", "mid", 55),
        ("Seventeen", "merch", "FOLLOW AGAIN Tour Photobook", "Tour Exclusive", "high", 85),
        ("Seventeen", "merch", "Going Seventeen 2024 DVD", "Limited", "mid", 60),
        ("Seventeen", "merch", "Seventeen x Bongbongee Plush Set", "Collaboration", "mid", 40),

        # ═══════════════════════════════════════════════════════════════════
        # NewJeans (expanded)
        # ═══════════════════════════════════════════════════════════════════
        ("NewJeans", "album", "Get Up Bunny Beach Bag Ver.", "Weverse Exclusive", "mid", 45),
        ("NewJeans", "album", "NewJeans 1st EP", "Standard", "standard", 20),
        ("NewJeans", "album", "NewJeans 1st EP Bluebook Ver.", "Limited", "mid", 55),
        ("NewJeans", "album", "Get Up Standard", "Standard", "standard", 18),
        ("NewJeans", "album", "How Sweet Weverse Albums Ver.", "Weverse Exclusive", "mid", 32),
        ("NewJeans", "album", "How Sweet Standard", "Standard", "standard", 18),
        ("NewJeans", "album", "Supernatural Weverse Ver.", "Weverse Exclusive", "mid", 35),
        ("NewJeans", "photocard", "Minji Video Call Fansign", "Fansign Event", "grail", 400),
        ("NewJeans", "photocard", "Hanni Video Call Fansign", "Fansign Event", "grail", 450),
        ("NewJeans", "photocard", "Danielle Lucky Draw", "Lucky Draw", "high", 180),
        ("NewJeans", "photocard", "Haerin Lucky Draw", "Lucky Draw", "high", 200),
        ("NewJeans", "photocard", "Hyein POB Photocard", "Pre-order Benefit", "mid", 55),
        ("NewJeans", "photocard", "NewJeans Standard Photocard", "Standard", "standard", 10),
        ("NewJeans", "merch", "NewJeans Bunnies Official Plush", "Official", "mid", 35),
        ("NewJeans", "merch", "NewJeans Fan Meeting Merch Set", "Tour Exclusive", "high", 90),

        # NewJeans — Additional (expanded)
        ("NewJeans", "album", "NewJeans 1st EP Bluebook Hanni Ver.", "Limited", "mid", 65),
        ("NewJeans", "album", "Get Up Bunny Beach Bag Haerin Ver.", "Weverse Exclusive", "mid", 50),
        ("NewJeans", "photocard", "How Sweet Weverse POB Minji", "Pre-order Benefit", "mid", 60),
        ("NewJeans", "photocard", "OMG Ditto Photocard Danielle Pull", "Album POB", "mid", 55),
        ("NewJeans", "photocard", "OMG Ditto Photocard Haerin Pull", "Album POB", "mid", 65),

        # ═══════════════════════════════════════════════════════════════════
        # EXO
        # ═══════════════════════════════════════════════════════════════════
        ("EXO", "album", "XOXO Repackage Growl", "Standard", "mid", 55),
        ("EXO", "album", "Exodus Korean Ver.", "Standard", "mid", 40),
        ("EXO", "album", "The War Regular A", "Standard", "standard", 22),
        ("EXO", "album", "The War Private Ver.", "Limited", "mid", 50),
        ("EXO", "album", "Don't Mess Up My Tempo Vivace Ver.", "Standard", "standard", 20),
        ("EXO", "album", "Don't Mess Up My Tempo Moderato Ver.", "Limited", "mid", 35),
        ("EXO", "album", "Obsession EXO Ver.", "Standard", "standard", 22),
        ("EXO", "album", "Obsession X-EXO Ver.", "Limited", "mid", 38),
        ("EXO", "album", "Don't Fight the Feeling Expansion Ver.", "Limited", "mid", 45),
        ("EXO", "album", "EXIST Standard", "Standard", "standard", 20),
        ("EXO", "album", "EXIST Photobook Ver.", "Limited", "mid", 40),
        ("EXO", "album", "Love Shot Repackage", "Standard", "standard", 24),
        ("EXO", "album", "Sing for You Winter Special", "Limited", "mid", 55),
        ("EXO", "photocard", "Baekhyun Fansign Photocard", "Fansign Event", "grail", 400),
        ("EXO", "photocard", "Kai Fansign Photocard", "Fansign Event", "grail", 380),
        ("EXO", "photocard", "D.O. Fansign Photocard", "Fansign Event", "grail", 350),
        ("EXO", "photocard", "Sehun Lucky Draw", "Lucky Draw", "high", 160),
        ("EXO", "photocard", "Chanyeol Lucky Draw", "Lucky Draw", "high", 150),
        ("EXO", "photocard", "Suho EXIST POB", "Pre-order Benefit", "mid", 45),
        ("EXO", "photocard", "Xiumin POB Photocard", "Pre-order Benefit", "mid", 40),
        ("EXO", "photocard", "Chen POB Photocard", "Pre-order Benefit", "mid", 38),
        ("EXO", "photocard", "EXO Standard Photocard", "Standard", "standard", 10),
        ("EXO", "merch", "EXO Official Lightstick Ver.3", "Official", "mid", 55),
        ("EXO", "merch", "EXO Planet #5 Concert Photobook", "Tour Exclusive", "high", 90),
        ("EXO", "merch", "EXO Fanmeeting Merch Set", "Tour Exclusive", "high", 80),

        # ═══════════════════════════════════════════════════════════════════
        # TWICE
        # ═══════════════════════════════════════════════════════════════════
        ("TWICE", "album", "Formula of Love Standard", "Standard", "standard", 18),
        ("TWICE", "album", "Formula of Love Result File Ver.", "Limited", "mid", 35),
        ("TWICE", "album", "Between 1&2 Standard", "Standard", "standard", 18),
        ("TWICE", "album", "Between 1&2 Archive Ver.", "Limited", "mid", 38),
        ("TWICE", "album", "Ready to Be Standard", "Standard", "standard", 20),
        ("TWICE", "album", "Ready to Be TO Ver.", "Limited", "mid", 40),
        ("TWICE", "album", "With YOU-th Standard", "Standard", "standard", 20),
        ("TWICE", "album", "With YOU-th Digipack", "Digipack", "standard", 16),
        ("TWICE", "album", "STRATEGY Standard", "Standard", "standard", 20),
        ("TWICE", "album", "Eyes Wide Open Standard", "Standard", "standard", 18),
        ("TWICE", "album", "Taste of Love Standard", "Standard", "standard", 18),
        ("TWICE", "album", "More & More Standard", "Standard", "standard", 20),
        ("TWICE", "album", "Feel Special Standard", "Standard", "standard", 22),
        ("TWICE", "album", "Twicetagram Standard", "Standard", "mid", 35),
        ("TWICE", "photocard", "Nayeon Video Call Fansign", "Fansign Event", "grail", 350),
        ("TWICE", "photocard", "Momo Video Call Fansign", "Fansign Event", "grail", 300),
        ("TWICE", "photocard", "Sana Video Call Fansign", "Fansign Event", "grail", 380),
        ("TWICE", "photocard", "Dahyun Lucky Draw", "Lucky Draw", "high", 140),
        ("TWICE", "photocard", "Tzuyu Lucky Draw", "Lucky Draw", "high", 160),
        ("TWICE", "photocard", "Jihyo POB Photocard", "Pre-order Benefit", "mid", 45),
        ("TWICE", "photocard", "Mina POB Photocard", "Pre-order Benefit", "mid", 50),
        ("TWICE", "photocard", "Chaeyoung POB Photocard", "Pre-order Benefit", "mid", 38),
        ("TWICE", "photocard", "Jeongyeon POB Photocard", "Pre-order Benefit", "mid", 35),
        ("TWICE", "photocard", "TWICE Standard Photocard", "Standard", "standard", 8),
        ("TWICE", "merch", "Candybong Infinity Lightstick", "Official", "mid", 60),
        ("TWICE", "merch", "READY TO BE World Tour Photobook", "Tour Exclusive", "high", 85),
        ("TWICE", "merch", "TWICE 5th World Tour Merch Set", "Tour Exclusive", "high", 95),
        ("TWICE", "merch", "TWICE x Lovelys Official Plush", "Collaboration", "mid", 35),

        # ═══════════════════════════════════════════════════════════════════
        # NCT (NCT 127, NCT Dream, WayV)
        # ═══════════════════════════════════════════════════════════════════
        ("NCT 127", "album", "Sticker Standard", "Standard", "standard", 18),
        ("NCT 127", "album", "Sticker Sticky Ver.", "Limited", "mid", 38),
        ("NCT 127", "album", "2 Baddies Standard", "Standard", "standard", 18),
        ("NCT 127", "album", "2 Baddies Digipack", "Digipack", "standard", 14),
        ("NCT 127", "album", "Fact Check Storage Ver.", "Limited", "mid", 42),
        ("NCT 127", "album", "Fact Check Standard", "Standard", "standard", 20),
        ("NCT 127", "album", "Ay-Yo Repackage", "Standard", "standard", 18),
        ("NCT 127", "album", "Walk Standard", "Standard", "standard", 20),
        ("NCT 127", "photocard", "Taeyong Video Call Fansign", "Fansign Event", "grail", 300),
        ("NCT 127", "photocard", "Jaehyun Video Call Fansign", "Fansign Event", "grail", 280),
        ("NCT 127", "photocard", "Mark Lucky Draw", "Lucky Draw", "high", 140),
        ("NCT 127", "photocard", "Haechan Lucky Draw", "Lucky Draw", "high", 180),
        ("NCT 127", "photocard", "Doyoung POB Photocard", "Pre-order Benefit", "mid", 45),
        ("NCT 127", "photocard", "Jungwoo POB Photocard", "Pre-order Benefit", "mid", 38),
        ("NCT 127", "photocard", "NCT 127 Standard Photocard", "Standard", "standard", 8),
        ("NCT Dream", "album", "ISTJ Standard", "Standard", "standard", 18),
        ("NCT Dream", "album", "ISTJ Poster Ver.", "Limited", "mid", 35),
        ("NCT Dream", "album", "Glitch Mode Digipack", "Digipack", "standard", 14),
        ("NCT Dream", "album", "Hot Sauce Boring Jalapeño Ver.", "Limited", "mid", 38),
        ("NCT Dream", "album", "Beatbox Digipack", "Digipack", "standard", 14),
        ("NCT Dream", "album", "Dream( )Scape Standard", "Standard", "standard", 20),
        ("NCT Dream", "photocard", "Jaemin Video Call Fansign", "Fansign Event", "grail", 350),
        ("NCT Dream", "photocard", "Haechan Dream Lucky Draw", "Lucky Draw", "high", 170),
        ("NCT Dream", "photocard", "Jeno Lucky Draw", "Lucky Draw", "high", 130),
        ("NCT Dream", "photocard", "Renjun POB Photocard", "Pre-order Benefit", "mid", 40),
        ("NCT Dream", "photocard", "Chenle POB Photocard", "Pre-order Benefit", "mid", 38),
        ("NCT Dream", "photocard", "Jisung POB Photocard", "Pre-order Benefit", "mid", 35),
        ("NCT Dream", "photocard", "NCT Dream Standard Photocard", "Standard", "standard", 8),
        ("WayV", "album", "On My Youth Standard", "Standard", "standard", 18),
        ("WayV", "album", "Phantom Standard", "Standard", "standard", 20),
        ("WayV", "album", "Give Me That Standard", "Standard", "standard", 18),
        ("WayV", "photocard", "Xiaojun Video Call Fansign", "Fansign Event", "high", 180),
        ("WayV", "photocard", "Ten Lucky Draw", "Lucky Draw", "high", 120),
        ("NCT", "merch", "NCT Official Lightstick", "Official", "mid", 50),
        ("NCT", "album", "Universe Standard", "Standard", "standard", 18),
        ("NCT", "album", "Golden Age Standard", "Standard", "standard", 20),
        ("NCT", "album", "Golden Age Collecting Ver.", "Limited", "mid", 42),

        # ═══════════════════════════════════════════════════════════════════
        # aespa
        # ═══════════════════════════════════════════════════════════════════
        ("aespa", "album", "MY WORLD Poster Ver.", "Limited", "mid", 38),
        ("aespa", "album", "MY WORLD Standard", "Standard", "standard", 18),
        ("aespa", "album", "Drama Standard", "Standard", "standard", 18),
        ("aespa", "album", "Drama Giant Ver.", "Limited", "mid", 45),
        ("aespa", "album", "Armageddon Standard", "Standard", "standard", 20),
        ("aespa", "album", "Armageddon Warn Ver.", "Limited", "mid", 40),
        ("aespa", "album", "Savage Standard", "Standard", "standard", 22),
        ("aespa", "album", "Girls Standard", "Standard", "standard", 18),
        ("aespa", "album", "Girls Real World Ver.", "Limited", "mid", 35),
        ("aespa", "album", "Whiplash Standard", "Standard", "standard", 20),
        ("aespa", "photocard", "Karina Video Call Fansign", "Fansign Event", "grail", 450),
        ("aespa", "photocard", "Winter Video Call Fansign", "Fansign Event", "grail", 380),
        ("aespa", "photocard", "Giselle Lucky Draw", "Lucky Draw", "high", 130),
        ("aespa", "photocard", "NingNing Lucky Draw", "Lucky Draw", "high", 120),
        ("aespa", "photocard", "Karina POB Photocard", "Pre-order Benefit", "mid", 60),
        ("aespa", "photocard", "Winter POB Photocard", "Pre-order Benefit", "mid", 55),
        ("aespa", "photocard", "aespa Standard Photocard", "Standard", "standard", 10),
        ("aespa", "merch", "aespa Official Lightstick", "Official", "mid", 50),
        ("aespa", "merch", "SYNK: HYPER LINE Concert Photobook", "Tour Exclusive", "high", 80),
        ("aespa", "merch", "aespa ae-Key Ring Set", "Official", "mid", 30),

        # aespa — Additional (expanded)
        ("aespa", "album", "MY WORLD Tabloid Ver.", "Limited", "mid", 42),
        ("aespa", "album", "MY WORLD Collectible Karina Ver.", "Limited", "mid", 45),
        ("aespa", "album", "Armageddon Vinyl LP", "Limited Vinyl", "high", 90),
        ("aespa", "merch", "aespa Official Lightstick Ver.2", "Official", "mid", 55),
        ("aespa", "photocard", "Karina Armageddon Lucky Draw", "Lucky Draw", "high", 170),

        # ═══════════════════════════════════════════════════════════════════
        # Le Sserafim
        # ═══════════════════════════════════════════════════════════════════
        ("Le Sserafim", "album", "FEARLESS Standard", "Standard", "standard", 18),
        ("Le Sserafim", "album", "FEARLESS Blue Chypre Ver.", "Limited", "mid", 35),
        ("Le Sserafim", "album", "ANTIFRAGILE Standard", "Standard", "standard", 18),
        ("Le Sserafim", "album", "UNFORGIVEN Standard", "Standard", "standard", 20),
        ("Le Sserafim", "album", "UNFORGIVEN Compact Ver.", "Digipack", "standard", 14),
        ("Le Sserafim", "album", "EASY Standard", "Standard", "standard", 20),
        ("Le Sserafim", "album", "EASY Compact Ver.", "Digipack", "standard", 14),
        ("Le Sserafim", "album", "CRAZY Standard", "Standard", "standard", 20),
        ("Le Sserafim", "album", "CRAZY Compact Ver.", "Digipack", "standard", 14),
        ("Le Sserafim", "photocard", "Kazuha Video Call Fansign", "Fansign Event", "grail", 350),
        ("Le Sserafim", "photocard", "Sakura Video Call Fansign", "Fansign Event", "grail", 320),
        ("Le Sserafim", "photocard", "Chaewon Lucky Draw", "Lucky Draw", "high", 180),
        ("Le Sserafim", "photocard", "Yunjin Lucky Draw", "Lucky Draw", "high", 150),
        ("Le Sserafim", "photocard", "Eunchae POB Photocard", "Pre-order Benefit", "mid", 45),
        ("Le Sserafim", "photocard", "Kazuha POB Photocard", "Pre-order Benefit", "mid", 55),
        ("Le Sserafim", "photocard", "Le Sserafim Standard Photocard", "Standard", "standard", 10),
        ("Le Sserafim", "merch", "Le Sserafim Official Lightstick", "Official", "mid", 52),
        ("Le Sserafim", "merch", "FLAME RISES Tour Merch Set", "Tour Exclusive", "high", 85),

        # Le Sserafim — Additional (expanded)
        ("Le Sserafim", "album", "UNFORGIVEN Vinyl LP", "Limited Vinyl", "high", 85),
        ("Le Sserafim", "album", "EASY Weverse POB Ver.", "Weverse Exclusive", "mid", 35),
        ("Le Sserafim", "album", "ANTIFRAGILE Compact Ver. (First Press)", "Limited", "mid", 32),
        ("Le Sserafim", "photocard", "Chaewon EASY POB Photocard", "Pre-order Benefit", "mid", 58),
        ("Le Sserafim", "photocard", "Sakura UNFORGIVEN Lucky Draw", "Lucky Draw", "high", 165),

        # ═══════════════════════════════════════════════════════════════════
        # IVE
        # ═══════════════════════════════════════════════════════════════════
        ("IVE", "album", "ELEVEN Standard", "Standard", "standard", 18),
        ("IVE", "album", "After Like Standard", "Standard", "standard", 18),
        ("IVE", "album", "I've IVE Standard", "Standard", "standard", 20),
        ("IVE", "album", "I've IVE Photobook Ver.", "Limited", "mid", 42),
        ("IVE", "album", "I WANT Standard", "Standard", "standard", 20),
        ("IVE", "album", "IVE SWITCH Standard", "Standard", "standard", 20),
        ("IVE", "album", "IVE SWITCH Plve Ver.", "Weverse Exclusive", "mid", 32),
        ("IVE", "photocard", "Wonyoung Video Call Fansign", "Fansign Event", "grail", 500),
        ("IVE", "photocard", "Yujin Video Call Fansign", "Fansign Event", "grail", 350),
        ("IVE", "photocard", "Gaeul Lucky Draw", "Lucky Draw", "high", 130),
        ("IVE", "photocard", "Rei Lucky Draw", "Lucky Draw", "high", 140),
        ("IVE", "photocard", "Liz POB Photocard", "Pre-order Benefit", "mid", 40),
        ("IVE", "photocard", "Leeseo POB Photocard", "Pre-order Benefit", "mid", 38),
        ("IVE", "photocard", "Wonyoung POB Photocard", "Pre-order Benefit", "mid", 65),
        ("IVE", "photocard", "IVE Standard Photocard", "Standard", "standard", 10),
        ("IVE", "merch", "IVE Official Lightstick", "Official", "mid", 50),
        ("IVE", "merch", "IVE THE 1ST WORLD TOUR Merch Set", "Tour Exclusive", "high", 85),

        # ═══════════════════════════════════════════════════════════════════
        # ITZY
        # ═══════════════════════════════════════════════════════════════════
        ("ITZY", "album", "Crazy in Love Standard", "Standard", "standard", 18),
        ("ITZY", "album", "Crazy in Love Special Ed.", "Limited", "mid", 40),
        ("ITZY", "album", "CHECKMATE Standard", "Standard", "standard", 18),
        ("ITZY", "album", "CHECKMATE Limited", "Limited", "mid", 35),
        ("ITZY", "album", "KILL MY DOUBT Standard", "Standard", "standard", 20),
        ("ITZY", "album", "KILL MY DOUBT Limited Ver.", "Limited", "mid", 38),
        ("ITZY", "album", "BORN TO BE Standard", "Standard", "standard", 20),
        ("ITZY", "album", "IT'z ME Standard", "Standard", "standard", 22),
        ("ITZY", "album", "IT'z ICY Standard", "Standard", "standard", 24),
        ("ITZY", "album", "GUESS WHO Standard", "Standard", "standard", 20),
        ("ITZY", "photocard", "Yeji Video Call Fansign", "Fansign Event", "grail", 280),
        ("ITZY", "photocard", "Ryujin Video Call Fansign", "Fansign Event", "grail", 320),
        ("ITZY", "photocard", "Yuna Lucky Draw", "Lucky Draw", "high", 140),
        ("ITZY", "photocard", "Lia Lucky Draw", "Lucky Draw", "high", 110),
        ("ITZY", "photocard", "Chaeryeong POB Photocard", "Pre-order Benefit", "mid", 35),
        ("ITZY", "photocard", "ITZY Standard Photocard", "Standard", "standard", 8),
        ("ITZY", "merch", "ITZY Official Lightstick", "Official", "mid", 48),
        ("ITZY", "merch", "ITZY 2nd World Tour Merch Set", "Tour Exclusive", "high", 80),

        # ═══════════════════════════════════════════════════════════════════
        # Red Velvet
        # ═══════════════════════════════════════════════════════════════════
        ("Red Velvet", "album", "The ReVe Festival Day 1", "Standard", "standard", 22),
        ("Red Velvet", "album", "The ReVe Festival Finale", "Standard", "standard", 25),
        ("Red Velvet", "album", "Queendom Standard", "Standard", "standard", 20),
        ("Red Velvet", "album", "Queendom Queens Ver.", "Limited", "mid", 38),
        ("Red Velvet", "album", "Chill Kill Standard", "Standard", "standard", 20),
        ("Red Velvet", "album", "Chill Kill Special Ver.", "Limited", "mid", 40),
        ("Red Velvet", "album", "Cosmic Standard", "Standard", "standard", 20),
        ("Red Velvet", "album", "The Red Standard", "Standard", "mid", 40),
        ("Red Velvet", "album", "Perfect Velvet Standard", "Standard", "mid", 35),
        ("Red Velvet", "album", "RBB Standard", "Standard", "standard", 22),
        ("Red Velvet", "photocard", "Irene Video Call Fansign", "Fansign Event", "grail", 350),
        ("Red Velvet", "photocard", "Joy Video Call Fansign", "Fansign Event", "grail", 280),
        ("Red Velvet", "photocard", "Seulgi Lucky Draw", "Lucky Draw", "high", 150),
        ("Red Velvet", "photocard", "Wendy Lucky Draw", "Lucky Draw", "high", 130),
        ("Red Velvet", "photocard", "Yeri POB Photocard", "Pre-order Benefit", "mid", 40),
        ("Red Velvet", "photocard", "Red Velvet Standard Photocard", "Standard", "standard", 8),
        ("Red Velvet", "merch", "Red Velvet Official Lightstick", "Official", "mid", 55),
        ("Red Velvet", "merch", "R to V Concert Photobook", "Tour Exclusive", "high", 85),

        # ═══════════════════════════════════════════════════════════════════
        # GOT7
        # ═══════════════════════════════════════════════════════════════════
        ("GOT7", "album", "DYE Standard", "Standard", "standard", 22),
        ("GOT7", "album", "DYE Limited Ver.", "Limited", "mid", 45),
        ("GOT7", "album", "Breath of Love: Last Piece", "Standard", "standard", 22),
        ("GOT7", "album", "GOT7 Self-Titled Standard", "Standard", "standard", 22),
        ("GOT7", "album", "Present: YOU Standard", "Standard", "standard", 20),
        ("GOT7", "album", "Spinning Top Standard", "Standard", "standard", 22),
        ("GOT7", "album", "Eyes On You Standard", "Standard", "standard", 24),
        ("GOT7", "album", "Flight Log: Arrival Standard", "Standard", "mid", 35),
        ("GOT7", "album", "7 for 7 Standard", "Standard", "standard", 22),
        ("GOT7", "photocard", "Jackson Video Call Fansign", "Fansign Event", "grail", 350),
        ("GOT7", "photocard", "Jinyoung Video Call Fansign", "Fansign Event", "grail", 300),
        ("GOT7", "photocard", "BamBam Lucky Draw", "Lucky Draw", "high", 130),
        ("GOT7", "photocard", "Yugyeom Lucky Draw", "Lucky Draw", "high", 110),
        ("GOT7", "photocard", "Mark POB Photocard", "Pre-order Benefit", "mid", 45),
        ("GOT7", "photocard", "Youngjae POB Photocard", "Pre-order Benefit", "mid", 35),
        ("GOT7", "photocard", "JB/Jay B POB Photocard", "Pre-order Benefit", "mid", 50),
        ("GOT7", "photocard", "GOT7 Standard Photocard", "Standard", "standard", 10),
        ("GOT7", "merch", "GOT7 Official Lightstick Ver.3", "Official", "mid", 55),
        ("GOT7", "merch", "GOT7 Homecoming Fanmeet Photobook", "Tour Exclusive", "high", 80),

        # ═══════════════════════════════════════════════════════════════════
        # TXT (Tomorrow X Together)
        # ═══════════════════════════════════════════════════════════════════
        ("TXT", "album", "minisode 3: TOMORROW Standard", "Standard", "standard", 20),
        ("TXT", "album", "minisode 3: TOMORROW Weverse Ver.", "Weverse Exclusive", "mid", 35),
        ("TXT", "album", "The Name Chapter: FREEFALL Standard", "Standard", "standard", 20),
        ("TXT", "album", "The Name Chapter: FREEFALL Gravity Ver.", "Limited", "mid", 42),
        ("TXT", "album", "The Name Chapter: TEMPTATION Standard", "Standard", "standard", 20),
        ("TXT", "album", "DREAM CHAPTER: MAGIC Standard", "Standard", "standard", 22),
        ("TXT", "album", "DREAM CHAPTER: ETERNITY Standard", "Standard", "standard", 22),
        ("TXT", "album", "DREAM CHAPTER: STAR Standard", "Standard", "mid", 35),
        ("TXT", "album", "The Chaos Chapter: FREEZE Standard", "Standard", "standard", 20),
        ("TXT", "album", "minisode 2: Thursday's Child Standard", "Standard", "standard", 18),
        ("TXT", "photocard", "Yeonjun Video Call Fansign", "Fansign Event", "grail", 320),
        ("TXT", "photocard", "Soobin Video Call Fansign", "Fansign Event", "grail", 300),
        ("TXT", "photocard", "Beomgyu Lucky Draw", "Lucky Draw", "high", 160),
        ("TXT", "photocard", "Taehyun Lucky Draw", "Lucky Draw", "high", 130),
        ("TXT", "photocard", "Hueningkai POB Photocard", "Pre-order Benefit", "mid", 45),
        ("TXT", "photocard", "TXT Standard Photocard", "Standard", "standard", 8),
        ("TXT", "merch", "TXT Official Lightstick (MOA Bong)", "Official", "mid", 50),
        ("TXT", "merch", "ACT: PROMISE Tour Photobook", "Tour Exclusive", "high", 85),
        ("TXT", "merch", "TXT Memories: Second Story DVD", "Limited", "mid", 60),

        # ═══════════════════════════════════════════════════════════════════
        # (G)I-DLE
        # ═══════════════════════════════════════════════════════════════════
        ("(G)I-DLE", "album", "I FEEL Standard", "Standard", "standard", 18),
        ("(G)I-DLE", "album", "I FEEL Queen Ver.", "Limited", "mid", 38),
        ("(G)I-DLE", "album", "I burn Standard", "Standard", "standard", 20),
        ("(G)I-DLE", "album", "2 Standard", "Standard", "standard", 20),
        ("(G)I-DLE", "album", "2 (2-2 Ver.)", "Limited", "mid", 38),
        ("(G)I-DLE", "album", "I LOVE Standard", "Standard", "standard", 18),
        ("(G)I-DLE", "album", "I SWAY Standard", "Standard", "standard", 20),
        ("(G)I-DLE", "album", "I MADE Standard", "Standard", "standard", 22),
        ("(G)I-DLE", "album", "I AM Standard", "Standard", "standard", 22),
        ("(G)I-DLE", "photocard", "Miyeon Video Call Fansign", "Fansign Event", "grail", 280),
        ("(G)I-DLE", "photocard", "Shuhua Video Call Fansign", "Fansign Event", "grail", 250),
        ("(G)I-DLE", "photocard", "Minnie Lucky Draw", "Lucky Draw", "high", 140),
        ("(G)I-DLE", "photocard", "Yuqi Lucky Draw", "Lucky Draw", "high", 150),
        ("(G)I-DLE", "photocard", "Soyeon POB Photocard", "Pre-order Benefit", "mid", 40),
        ("(G)I-DLE", "photocard", "(G)I-DLE Standard Photocard", "Standard", "standard", 8),
        ("(G)I-DLE", "merch", "(G)I-DLE Official Lightstick Ver.2", "Official", "mid", 50),
        ("(G)I-DLE", "merch", "(G)I-DLE World Tour Merch Set", "Tour Exclusive", "high", 80),

        # ═══════════════════════════════════════════════════════════════════
        # NMIXX
        # ═══════════════════════════════════════════════════════════════════
        ("NMIXX", "album", "expergo Standard", "Standard", "standard", 18),
        ("NMIXX", "album", "expergo Digipack", "Digipack", "standard", 14),
        ("NMIXX", "album", "Fe3O4: BREAK Standard", "Standard", "standard", 18),
        ("NMIXX", "album", "Fe3O4: BREAK Limited", "Limited", "mid", 35),
        ("NMIXX", "album", "A Midsummer NMIXX's Dream Standard", "Standard", "standard", 18),
        ("NMIXX", "album", "ENTWURF Standard", "Standard", "standard", 18),
        ("NMIXX", "album", "Fe3O4: STICK Standard", "Standard", "standard", 20),
        ("NMIXX", "photocard", "Sullyoon Video Call Fansign", "Fansign Event", "grail", 280),
        ("NMIXX", "photocard", "Haewon Video Call Fansign", "Fansign Event", "grail", 250),
        ("NMIXX", "photocard", "Lily Lucky Draw", "Lucky Draw", "high", 120),
        ("NMIXX", "photocard", "Bae Lucky Draw", "Lucky Draw", "high", 110),
        ("NMIXX", "photocard", "Kyujin POB Photocard", "Pre-order Benefit", "mid", 40),
        ("NMIXX", "photocard", "Jiwoo POB Photocard", "Pre-order Benefit", "mid", 35),
        ("NMIXX", "photocard", "NMIXX Standard Photocard", "Standard", "standard", 8),
        ("NMIXX", "merch", "NMIXX Official Lightstick", "Official", "mid", 48),

        # ═══════════════════════════════════════════════════════════════════
        # Dreamcatcher
        # ═══════════════════════════════════════════════════════════════════
        ("Dreamcatcher", "album", "Apocalypse: Save Us Standard", "Standard", "standard", 22),
        ("Dreamcatcher", "album", "Apocalypse: Follow Us Standard", "Standard", "standard", 22),
        ("Dreamcatcher", "album", "Apocalypse: From Us Limited", "Limited", "mid", 50),
        ("Dreamcatcher", "album", "VillainS Standard", "Standard", "standard", 22),
        ("Dreamcatcher", "album", "VillainS Limited", "Limited", "mid", 45),
        ("Dreamcatcher", "album", "Dystopia: The Tree of Language", "Standard", "mid", 40),
        ("Dreamcatcher", "album", "Dystopia: Lose Myself", "Standard", "standard", 25),
        ("Dreamcatcher", "album", "Raid of Dream Standard", "Standard", "mid", 55),
        ("Dreamcatcher", "album", "Nightmare: Escape The ERA", "Standard", "mid", 60),
        ("Dreamcatcher", "album", "SSTORM Standard", "Standard", "standard", 20),
        ("Dreamcatcher", "photocard", "JiU Video Call Fansign", "Fansign Event", "grail", 250),
        ("Dreamcatcher", "photocard", "Yoohyeon Video Call Fansign", "Fansign Event", "grail", 230),
        ("Dreamcatcher", "photocard", "SuA Lucky Draw", "Lucky Draw", "high", 120),
        ("Dreamcatcher", "photocard", "Siyeon POB Photocard", "Pre-order Benefit", "mid", 40),
        ("Dreamcatcher", "photocard", "Handong POB Photocard", "Pre-order Benefit", "mid", 35),
        ("Dreamcatcher", "photocard", "Dami POB Photocard", "Pre-order Benefit", "mid", 35),
        ("Dreamcatcher", "photocard", "Gahyeon POB Photocard", "Pre-order Benefit", "mid", 32),
        ("Dreamcatcher", "photocard", "Dreamcatcher Standard Photocard", "Standard", "standard", 10),
        ("Dreamcatcher", "merch", "Dreamcatcher Official Lightstick", "Official", "mid", 55),

        # ═══════════════════════════════════════════════════════════════════
        # Mamamoo
        # ═══════════════════════════════════════════════════════════════════
        ("Mamamoo", "album", "reality in BLACK Standard", "Standard", "standard", 22),
        ("Mamamoo", "album", "Travel Standard", "Standard", "standard", 20),
        ("Mamamoo", "album", "MIC ON Standard", "Standard", "standard", 20),
        ("Mamamoo", "album", "WAW Standard", "Standard", "standard", 22),
        ("Mamamoo", "album", "White Wind Standard", "Standard", "standard", 22),
        ("Mamamoo", "album", "Red Moon Standard", "Standard", "standard", 24),
        ("Mamamoo", "album", "Hwasa - Maria", "Standard", "standard", 20),
        ("Mamamoo", "album", "Hwasa - Guilty Pleasure", "Standard", "standard", 18),
        ("Mamamoo", "album", "Solar - COLOURS", "Standard", "standard", 18),
        ("Mamamoo", "album", "Solar - FACE", "Standard", "standard", 20),
        ("Mamamoo", "album", "Moonbyul - Starlit of Muse", "Standard", "standard", 20),
        ("Mamamoo", "album", "Wheein - WHEE", "Standard", "standard", 18),
        ("Mamamoo", "photocard", "Hwasa Video Call Fansign", "Fansign Event", "grail", 250),
        ("Mamamoo", "photocard", "Solar Video Call Fansign", "Fansign Event", "grail", 220),
        ("Mamamoo", "photocard", "Moonbyul Lucky Draw", "Lucky Draw", "high", 110),
        ("Mamamoo", "photocard", "Wheein Lucky Draw", "Lucky Draw", "high", 100),
        ("Mamamoo", "photocard", "Mamamoo Standard Photocard", "Standard", "standard", 8),
        ("Mamamoo", "merch", "Mamamoo Official Lightstick Ver.2.5", "Official", "mid", 50),
        ("Mamamoo", "merch", "Mamamoo My Con Tour Photobook", "Tour Exclusive", "high", 80),

        # ═══════════════════════════════════════════════════════════════════
        # SHINee
        # ═══════════════════════════════════════════════════════════════════
        ("SHINee", "album", "Don't Call Me Standard", "Standard", "standard", 22),
        ("SHINee", "album", "Don't Call Me Jewel Case", "Jewel Case", "standard", 14),
        ("SHINee", "album", "Atlantis Standard", "Standard", "standard", 22),
        ("SHINee", "album", "HARD Standard", "Standard", "standard", 20),
        ("SHINee", "album", "HARD Photobook Ver.", "Limited", "mid", 40),
        ("SHINee", "album", "1 of 1 Limited", "Limited", "high", 90),
        ("SHINee", "album", "Lucifer Standard", "Standard", "mid", 55),
        ("SHINee", "album", "The Misconceptions of Us", "Standard", "mid", 45),
        ("SHINee", "album", "Odd Standard", "Standard", "mid", 35),
        ("SHINee", "photocard", "Taemin Fansign Photocard", "Fansign Event", "grail", 380),
        ("SHINee", "photocard", "Key Fansign Photocard", "Fansign Event", "grail", 280),
        ("SHINee", "photocard", "Minho Lucky Draw", "Lucky Draw", "high", 150),
        ("SHINee", "photocard", "Onew Lucky Draw", "Lucky Draw", "high", 130),
        ("SHINee", "photocard", "SHINee Vintage Replay PC", "Vintage", "high", 180),
        ("SHINee", "photocard", "SHINee Standard Photocard", "Standard", "standard", 12),
        ("SHINee", "merch", "SHINee Official Lightstick", "Official", "mid", 55),
        ("SHINee", "merch", "SHINee World VI Concert DVD", "Tour Exclusive", "high", 85),

        # ═══════════════════════════════════════════════════════════════════
        # BIGBANG
        # ═══════════════════════════════════════════════════════════════════
        ("BIGBANG", "album", "MADE Standard", "Standard", "mid", 50),
        ("BIGBANG", "album", "MADE Full Album Limited", "Limited", "high", 120),
        ("BIGBANG", "album", "Still Life Single", "Standard", "mid", 35),
        ("BIGBANG", "album", "ALIVE Standard", "Standard", "mid", 45),
        ("BIGBANG", "album", "BIGBANG (Self-Titled) Standard", "Standard", "mid", 55),
        ("BIGBANG", "album", "G-Dragon - KWON JI YONG USB", "Limited", "high", 150),
        ("BIGBANG", "album", "G-Dragon - Coup D'Etat", "Standard", "mid", 45),
        ("BIGBANG", "album", "Taeyang - SOLAR International", "Standard", "mid", 40),
        ("BIGBANG", "album", "T.O.P - DOOM DADA Single", "Standard", "mid", 35),
        ("BIGBANG", "photocard", "G-Dragon Vintage Photocard", "Vintage", "grail", 350),
        ("BIGBANG", "photocard", "T.O.P Vintage Photocard", "Vintage", "grail", 300),
        ("BIGBANG", "photocard", "Taeyang Vintage Photocard", "Vintage", "high", 200),
        ("BIGBANG", "photocard", "Daesung Vintage Photocard", "Vintage", "high", 150),
        ("BIGBANG", "photocard", "Seungri Vintage Photocard", "Vintage", "high", 80),
        ("BIGBANG", "merch", "BIGBANG Official Lightstick Ver.4", "Official", "high", 80),
        ("BIGBANG", "merch", "BIGBANG MADE World Tour DVD", "Tour Exclusive", "high", 95),

        # ═══════════════════════════════════════════════════════════════════
        # 2NE1 (all OOP/collector tier)
        # ═══════════════════════════════════════════════════════════════════
        ("2NE1", "album", "Crush Standard", "OOP", "high", 120),
        ("2NE1", "album", "Crush Pink Edition", "OOP Limited", "high", 180),
        ("2NE1", "album", "To Anyone Standard", "OOP", "high", 110),
        ("2NE1", "album", "2NE1 1st Mini Album", "OOP", "high", 150),
        ("2NE1", "album", "2NE1 Collection", "OOP", "high", 130),
        ("2NE1", "photocard", "CL Vintage Photocard", "Vintage", "grail", 300),
        ("2NE1", "photocard", "Park Bom Vintage Photocard", "Vintage", "grail", 250),
        ("2NE1", "photocard", "Dara Vintage Photocard", "Vintage", "high", 180),
        ("2NE1", "photocard", "Minzy Vintage Photocard", "Vintage", "high", 150),
        ("2NE1", "merch", "2NE1 Official Lightstick", "OOP", "high", 120),
        ("2NE1", "merch", "2NE1 2014 World Tour DVD", "OOP", "high", 100),
        ("2NE1", "merch", "2NE1 Crush Era Poster Set", "OOP", "mid", 60),

        # ═══════════════════════════════════════════════════════════════════
        # Super Junior
        # ═══════════════════════════════════════════════════════════════════
        ("Super Junior", "album", "The Renaissance Standard", "Standard", "standard", 22),
        ("Super Junior", "album", "The Renaissance Passion Ver.", "Limited", "mid", 40),
        ("Super Junior", "album", "House Party Standard", "Standard", "standard", 20),
        ("Super Junior", "album", "Timeless Standard", "Standard", "standard", 22),
        ("Super Junior", "album", "Time Slip Standard", "Standard", "standard", 22),
        ("Super Junior", "album", "Play Standard", "Standard", "standard", 24),
        ("Super Junior", "album", "Devil Standard", "Standard", "mid", 35),
        ("Super Junior", "album", "Sorry Sorry Repackage", "Standard", "mid", 55),
        ("Super Junior", "album", "Super Show 9 Concert Album", "Tour Exclusive", "mid", 45),
        ("Super Junior", "photocard", "Heechul Fansign Photocard", "Fansign Event", "grail", 280),
        ("Super Junior", "photocard", "Leeteuk Fansign Photocard", "Fansign Event", "grail", 250),
        ("Super Junior", "photocard", "Donghae Lucky Draw", "Lucky Draw", "high", 130),
        ("Super Junior", "photocard", "Eunhyuk Lucky Draw", "Lucky Draw", "high", 120),
        ("Super Junior", "photocard", "Siwon Vintage Photocard", "Vintage", "high", 160),
        ("Super Junior", "photocard", "Kyuhyun POB Photocard", "Pre-order Benefit", "mid", 40),
        ("Super Junior", "photocard", "Ryeowook POB Photocard", "Pre-order Benefit", "mid", 35),
        ("Super Junior", "photocard", "Super Junior Standard Photocard", "Standard", "standard", 10),
        ("Super Junior", "merch", "Super Junior Official Lightstick", "Official", "mid", 55),
        ("Super Junior", "merch", "Super Show 8 DVD", "Tour Exclusive", "high", 85),

        # ═══════════════════════════════════════════════════════════════════
        # ZEROBASEONE (4th gen — debut 2023)
        # ═══════════════════════════════════════════════════════════════════
        ("ZEROBASEONE", "album", "YOUTH IN THE SHADE Standard", "Standard", "standard", 20),
        ("ZEROBASEONE", "album", "YOUTH IN THE SHADE Digipack", "Digipack", "standard", 14),
        ("ZEROBASEONE", "album", "MELTING POINT Standard", "Standard", "standard", 20),
        ("ZEROBASEONE", "album", "MELTING POINT Fairytale Ver.", "Limited", "mid", 38),
        ("ZEROBASEONE", "album", "CINEMA PARADISE Standard", "Standard", "standard", 20),
        ("ZEROBASEONE", "photocard", "Sung Hanbin Video Call Fansign", "Fansign Event", "grail", 300),
        ("ZEROBASEONE", "photocard", "Zhang Hao Video Call Fansign", "Fansign Event", "grail", 350),
        ("ZEROBASEONE", "photocard", "Kim Jiwoong Lucky Draw", "Lucky Draw", "high", 130),
        ("ZEROBASEONE", "photocard", "ZEROBASEONE Standard Photocard", "Standard", "standard", 8),
        ("ZEROBASEONE", "merch", "ZEROBASEONE Official Lightstick", "Official", "mid", 48),

        # ═══════════════════════════════════════════════════════════════════
        # BOYNEXTDOOR (5th gen — debut 2023)
        # ═══════════════════════════════════════════════════════════════════
        ("BOYNEXTDOOR", "album", "WHO! Standard", "Standard", "standard", 18),
        ("BOYNEXTDOOR", "album", "WHY.. Standard", "Standard", "standard", 18),
        ("BOYNEXTDOOR", "album", "HOW? Standard", "Standard", "standard", 20),
        ("BOYNEXTDOOR", "album", "19.99 Standard", "Standard", "standard", 20),
        ("BOYNEXTDOOR", "photocard", "Sungho Video Call Fansign", "Fansign Event", "grail", 220),
        ("BOYNEXTDOOR", "photocard", "Riwoo Lucky Draw", "Lucky Draw", "high", 110),
        ("BOYNEXTDOOR", "photocard", "BOYNEXTDOOR Standard Photocard", "Standard", "standard", 7),

        # ═══════════════════════════════════════════════════════════════════
        # RIIZE (5th gen — debut 2023)
        # ═══════════════════════════════════════════════════════════════════
        ("RIIZE", "album", "Get A Guitar Standard", "Standard", "standard", 18),
        ("RIIZE", "album", "RIIZING Standard", "Standard", "standard", 20),
        ("RIIZE", "album", "RIIZING Collect Book Ver.", "Limited", "mid", 42),
        ("RIIZE", "photocard", "Wonbin Video Call Fansign", "Fansign Event", "grail", 380),
        ("RIIZE", "photocard", "Sohee Video Call Fansign", "Fansign Event", "grail", 300),
        ("RIIZE", "photocard", "Anton Lucky Draw", "Lucky Draw", "high", 120),
        ("RIIZE", "photocard", "Shotaro POB Photocard", "Pre-order Benefit", "mid", 45),
        ("RIIZE", "photocard", "RIIZE Standard Photocard", "Standard", "standard", 8),
        ("RIIZE", "merch", "RIIZE Official Lightstick", "Official", "mid", 48),

        # ═══════════════════════════════════════════════════════════════════
        # NewJeans — Albums, Photocards & Merch
        # ═══════════════════════════════════════════════════════════════════
        ("NewJeans", "album", "NewJeans 'Get Up' Bunny Edition", "Bunny Edition", "high", 85),
        ("NewJeans", "album", "NewJeans 'Get Up' The POWERPUFF GIRLS x NJ Box Ver.", "Powerpuff Collab", "high", 95),
        ("NewJeans", "album", "NewJeans 'How Sweet' Weverse Albums Ver.", "Weverse Exclusive", "mid", 35),
        ("NewJeans", "album", "NewJeans 'How Sweet' Standard", "Standard", "standard", 18),
        ("NewJeans", "album", "NewJeans 'Super Shy' Single CD", "Japanese Edition", "mid", 30),
        ("NewJeans", "photocard", "Minji Fansign Photocard", "Fansign Event", "grail", 380),
        ("NewJeans", "photocard", "Hanni Super Shy Lucky Draw", "Lucky Draw", "grail", 350),
        ("NewJeans", "photocard", "Haerin Get Up POB", "Pre-order Benefit", "high", 110),
        ("NewJeans", "merch", "NewJeans Bunnies Official Plush Set (5pc)", "Official", "high", 120),

        # ═══════════════════════════════════════════════════════════════════
        # LE SSERAFIM — Albums & Photocards
        # ═══════════════════════════════════════════════════════════════════
        ("LE SSERAFIM", "album", "LE SSERAFIM 'UNFORGIVEN' Limited Compact Ver.", "Compact Limited", "high", 90),
        ("LE SSERAFIM", "album", "LE SSERAFIM 'EASY' Vol. 1", "Standard", "standard", 20),
        ("LE SSERAFIM", "album", "LE SSERAFIM 'EASY' Weverse Albums Ver.", "Weverse Exclusive", "mid", 32),
        ("LE SSERAFIM", "photocard", "Kazuha UNFORGIVEN Fansign", "Fansign Event", "grail", 320),
        ("LE SSERAFIM", "photocard", "Sakura EASY Lucky Draw", "Lucky Draw", "high", 150),
        ("LE SSERAFIM", "merch", "LE SSERAFIM Official Lightstick", "Official", "mid", 52),

        # ═══════════════════════════════════════════════════════════════════
        # ILLIT — Debut
        # ═══════════════════════════════════════════════════════════════════
        ("ILLIT", "album", "ILLIT 'SUPER REAL ME' 1st Mini Album", "Standard", "standard", 18),
        ("ILLIT", "album", "ILLIT 'SUPER REAL ME' Weverse Albums Ver.", "Weverse Exclusive", "mid", 30),
        ("ILLIT", "photocard", "Wonhee SUPER REAL ME POB", "Pre-order Benefit", "mid", 45),
        ("ILLIT", "photocard", "Minju Lucky Draw Photocard", "Lucky Draw", "high", 120),

        # ═══════════════════════════════════════════════════════════════════
        # BABYMONSTER — Debut
        # ═══════════════════════════════════════════════════════════════════
        ("BABYMONSTER", "album", "BABYMONSTER 'DRIP' 1st Mini Album", "Standard", "standard", 20),
        ("BABYMONSTER", "album", "BABYMONSTER 'DRIP' YG Tag Album", "YG Tag Ver.", "mid", 28),
        ("BABYMONSTER", "photocard", "Ahyeon Debut Fansign", "Fansign Event", "grail", 280),
        ("BABYMONSTER", "photocard", "Ruka Lucky Draw Photocard", "Lucky Draw", "high", 100),

        # ═══════════════════════════════════════════════════════════════════
        # TWS — Debut
        # ═══════════════════════════════════════════════════════════════════
        ("TWS", "album", "TWS 'Sparkling Blue' 1st Mini Album", "Standard", "standard", 18),
        ("TWS", "album", "TWS 'Sparkling Blue' Weverse Albums Ver.", "Weverse Exclusive", "mid", 28),
        ("TWS", "photocard", "Shinyu Fansign Photocard", "Fansign Event", "high", 150),
        ("TWS", "photocard", "Dohoon POB Photocard", "Pre-order Benefit", "mid", 40),

        # ═══════════════════════════════════════════════════════════════════
        # ZEROBASEONE — Additional Versions
        # ═══════════════════════════════════════════════════════════════════
        ("ZEROBASEONE", "album", "ZEROBASEONE 'Melting Point' Fairytale Ver.", "Fairytale Ver.", "mid", 35),
        ("ZEROBASEONE", "album", "ZEROBASEONE 'Melting Point' Loyalty Ver.", "Loyalty Ver.", "mid", 35),
        ("ZEROBASEONE", "album", "ZEROBASEONE 'Melting Point' Fascination Ver.", "Fascination Ver.", "mid", 35),
        ("ZEROBASEONE", "photocard", "Sung Hanbin Melting Point Fansign", "Fansign Event", "grail", 300),

        # ═══════════════════════════════════════════════════════════════════
        # BOYNEXTDOOR — Albums
        # ═══════════════════════════════════════════════════════════════════
        ("BOYNEXTDOOR", "album", "BOYNEXTDOOR 'WHO!' 1st Single", "Standard", "standard", 18),
        ("BOYNEXTDOOR", "album", "BOYNEXTDOOR 'WHY..' 2nd EP", "Standard", "standard", 20),
        ("BOYNEXTDOOR", "photocard", "Sungho Fansign Photocard", "Fansign Event", "high", 130),

        # ═══════════════════════════════════════════════════════════════════
        # Xikers — Albums & Photocards
        # ═══════════════════════════════════════════════════════════════════
        ("Xikers", "album", "xikers 'HOUSE OF TRICKY: Doorbell Ringing'", "Standard", "standard", 18),
        ("Xikers", "album", "xikers 'HOUSE OF TRICKY: How to Play'", "Standard", "standard", 18),
        ("Xikers", "photocard", "Xikers Minjae Lucky Draw", "Lucky Draw", "high", 90),

        # ═══════════════════════════════════════════════════════════════════
        # Kiss of Life — Albums
        # ═══════════════════════════════════════════════════════════════════
        ("Kiss of Life", "album", "Kiss of Life 'Midas Touch' 1st Mini Album", "Standard", "standard", 18),
        ("Kiss of Life", "album", "Kiss of Life 'Born to be XX' 2nd Mini Album", "Standard", "standard", 20),
        ("Kiss of Life", "photocard", "Natty Midas Touch Lucky Draw", "Lucky Draw", "high", 110),
        ("Kiss of Life", "photocard", "Julie Born to be XX POB", "Pre-order Benefit", "mid", 45),

        # ═══════════════════════════════════════════════════════════════════
        # ENHYPEN — Additional Goods
        # ═══════════════════════════════════════════════════════════════════
        ("ENHYPEN", "album", "ENHYPEN 'ROMANCE : UNTOLD' Standard", "Standard", "standard", 22),
        ("ENHYPEN", "album", "ENHYPEN 'ROMANCE : UNTOLD' Weverse Ver.", "Weverse Exclusive", "mid", 35),
        ("ENHYPEN", "photocard", "Heeseung ROMANCE UNTOLD Lucky Draw", "Lucky Draw", "grail", 220),
        ("ENHYPEN", "photocard", "Jay ROMANCE UNTOLD Weverse POB", "Pre-order Benefit", "mid", 55),
        ("ENHYPEN", "photocard", "Sunghoon Dusk Till Dawn Fan Sign", "Fan Sign", "high", 140),
        ("ENHYPEN", "merch", "ENHYPEN Official Light Stick Ver. 2", "Official", "mid", 65),
        ("ENHYPEN", "merch", "ENHYPEN World Tour Finale Hoodie", "Tour Exclusive", "mid", 75),

        # ═══════════════════════════════════════════════════════════════════
        # ATEEZ — Additional Items
        # ═══════════════════════════════════════════════════════════════════
        ("ATEEZ", "album", "ATEEZ 'GOLDEN HOUR : Part.2'", "Standard", "standard", 20),
        ("ATEEZ", "merch", "ATEEZ Official Lightstick Ver. 3", "Official", "mid", 68),
        ("ATEEZ", "photocard", "Hongjoong Golden Hour Lucky Draw", "Lucky Draw", "grail", 200),
        ("ATEEZ", "photocard", "San Towards The Light POB", "Pre-order Benefit", "mid", 50),
        ("ATEEZ", "merch", "ATEEZ Break the Wall Tour Towel", "Tour Exclusive", "mid", 42),

        # ═══════════════════════════════════════════════════════════════════
        # IVE — Photo Cards & Albums
        # ═══════════════════════════════════════════════════════════════════
        ("IVE", "album", "IVE 'IVE MINE' 1st Full Album", "Standard", "standard", 20),
        ("IVE", "album", "IVE 'SWITCH' 2nd EP", "Standard", "standard", 22),
        ("IVE", "photocard", "Wonyoung IVE MINE Lucky Draw", "Lucky Draw", "grail", 250),
        ("IVE", "photocard", "Yujin SWITCH Weverse POB", "Pre-order Benefit", "mid", 55),
        ("IVE", "photocard", "Rei IVE MINE Fan Sign", "Fan Sign", "high", 130),
        ("IVE", "merch", "IVE 1st Fan Meeting DIVE Keyring Set", "Fan Meeting", "mid", 45),

        # ═══════════════════════════════════════════════════════════════════
        # LE SSERAFIM — Merchandise
        # ═══════════════════════════════════════════════════════════════════
        ("LE SSERAFIM", "album", "LE SSERAFIM 'CRAZY' 4th Mini Album", "Standard", "standard", 20),
        ("LE SSERAFIM", "photocard", "Kazuha CRAZY Lucky Draw", "Lucky Draw", "grail", 210),
        ("LE SSERAFIM", "photocard", "Chaewon EASY Weverse POB", "Pre-order Benefit", "mid", 60),
        ("LE SSERAFIM", "merch", "LE SSERAFIM FLAME RISES Tour Cap", "Tour Exclusive", "mid", 48),
        ("LE SSERAFIM", "merch", "LE SSERAFIM Official Lightstick", "Official", "mid", 62),

        # ═══════════════════════════════════════════════════════════════════
        # (G)I-DLE — Items
        # ═══════════════════════════════════════════════════════════════════
        ("(G)I-DLE", "album", "(G)I-DLE '2' 2nd Full Album", "Standard", "standard", 20),
        ("(G)I-DLE", "photocard", "Miyeon Super Lady Lucky Draw", "Lucky Draw", "high", 160),
        ("(G)I-DLE", "photocard", "Shuhua Heat Fan Sign", "Fan Sign", "high", 110),
        ("(G)I-DLE", "merch", "(G)I-DLE Official Lightstick", "Official", "mid", 58),

        # ═══════════════════════════════════════════════════════════════════
        # ITZY — Official Goods
        # ═══════════════════════════════════════════════════════════════════
        ("ITZY", "album", "ITZY 'BORN TO BE' 2nd Album", "Standard", "standard", 18),
        ("ITZY", "photocard", "Ryujin BORN TO BE Lucky Draw", "Lucky Draw", "high", 150),
        ("ITZY", "photocard", "Yeji CHECKMATE Fan Sign", "Fan Sign", "high", 120),
        ("ITZY", "merch", "ITZY 2nd World Tour Lightstick Strap", "Tour Exclusive", "mid", 35),

        # ═══════════════════════════════════════════════════════════════════
        # TXT — Merch & Photocards
        # ═══════════════════════════════════════════════════════════════════
        ("TXT", "album", "TXT 'The Name Chapter: FREEFALL'", "Standard", "standard", 20),
        ("TXT", "photocard", "Yeonjun FREEFALL Lucky Draw", "Lucky Draw", "high", 170),
        ("TXT", "photocard", "Soobin Good Boy Gone Bad POB", "Pre-order Benefit", "mid", 55),
        ("TXT", "merch", "TXT MOA-DONG Official Plush", "Official", "mid", 40),

        # ═══════════════════════════════════════════════════════════════════
        # Stray Kids — Maxident & More
        # ═══════════════════════════════════════════════════════════════════
        ("Stray Kids", "album", "Stray Kids 'ATE' Standard", "Standard", "standard", 22),
        ("Stray Kids", "photocard", "Felix ATE Lucky Draw", "Lucky Draw", "grail", 240),
        ("Stray Kids", "photocard", "Hyunjin Maxident Fan Sign", "Fan Sign", "high", 180),
        ("Stray Kids", "merch", "Stray Kids Maniac Encore Tour Hoodie", "Tour Exclusive", "mid", 78),

        # ═══════════════════════════════════════════════════════════════════
        # NMIXX — Albums & Photocards
        # ═══════════════════════════════════════════════════════════════════
        ("NMIXX", "album", "NMIXX 'Fe3O4: BREAK' 2nd EP", "Standard", "standard", 18),
        ("NMIXX", "photocard", "Sullyoon Fe3O4 Lucky Draw", "Lucky Draw", "high", 140),
        ("NMIXX", "photocard", "Haewon DASH POB", "Pre-order Benefit", "mid", 48),

        # ═══════════════════════════════════════════════════════════════════
        # aespa — MY World & Beyond
        # ═══════════════════════════════════════════════════════════════════
        ("aespa", "album", "aespa 'Whiplash' 5th Mini Album", "Standard", "standard", 20),
        ("aespa", "photocard", "Karina Whiplash Lucky Draw", "Lucky Draw", "grail", 230),
        ("aespa", "photocard", "Winter MY WORLD Fan Sign", "Fan Sign", "high", 135),
        ("aespa", "merch", "aespa SYNK: PARALLEL Official Towel", "Tour Exclusive", "mid", 38),

        # ═══════════════════════════════════════════════════════════════════
        # NewJeans — Bunnies Collection
        # ═══════════════════════════════════════════════════════════════════
        ("NewJeans", "merch", "NewJeans Bunny Tokki Plush (Full Set)", "Limited", "high", 120),
        ("NewJeans", "merch", "NewJeans x LINE FRIENDS Bunini Cushion", "Collab", "mid", 55),
        ("NewJeans", "photocard", "Minji How Sweet Lucky Draw", "Lucky Draw", "grail", 260),
        ("NewJeans", "photocard", "Hanni Get Up Fan Sign", "Fan Sign", "high", 180),

        # ═══════════════════════════════════════════════════════════════════
        # Additional K-pop Items (+8)
        # ═══════════════════════════════════════════════════════════════════
        ("ILLIT", "album", "ILLIT SUPER REAL ME Weverse POB Album", "Pre-order Benefit", "mid", 35),
        ("ILLIT", "photocard", "Wonhee Magnetic Lucky Draw", "Lucky Draw", "high", 150),
        ("KISS OF LIFE", "album", "KISS OF LIFE Midas Touch Digipack", "Standard", "standard", 22),
        ("KISS OF LIFE", "photocard", "Julie Born to be XX Fan Sign", "Fan Sign", "high", 130),
        ("TWS", "album", "TWS Sparkling Blue Limited Edition", "Limited", "mid", 38),
        ("TWS", "photocard", "Shinyu Plot Twist Lucky Draw", "Lucky Draw", "high", 140),
        ("RIIZE", "merch", "RIIZE Get a Guitar Tour Towel Set", "Tour Exclusive", "mid", 42),
        ("RIIZE", "photocard", "Sungchan Impossible Fan Sign", "Fan Sign", "high", 120),
    ]

    catalog = []
    for group, item_type, name, variant, tier, price in items:
        catalog.append({
            "group": group,
            "item_type": item_type,
            "name": name,
            "variant": variant,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    group = item["group"]
    name = item["name"]
    variant = item["variant"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{group}-{name}"),
        title=f"{group} - {name}",
        set_code=group.lower().replace(" ", "-"),
        brand=group,
        rarity=item["rarity_tier"].title(),
        notes=f"{group} | {item['item_type']} | {variant}",
        attributes_json={
            "group": group,
            "item_type": item["item_type"],
            "variant": variant,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    variant = item["variant"]
    edition_map = {
        "Fansign Event": 0.95, "Lucky Draw": 0.9, "Signed": 0.95,
        "Collector's Edition": 0.85, "Limited Vinyl": 0.8,
        "Original Pressing": 0.85,
        "Limited": 0.7, "Limited Version": 0.7, "Deluxe": 0.65,
        "Weverse Exclusive": 0.6, "Pre-order Benefit": 0.55,
        "Night Ver.": 0.65, "Digipack": 0.4, "Jewel Case": 0.3,
        "Standard": 0.2, "Album POB": 0.5,
        "Vintage": 0.9, "OOP": 0.8, "OOP Limited": 0.85,
        "Limited Star": 0.7, "Official": 0.5,
        "Tour Exclusive": 0.75, "Collaboration": 0.55,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_map.get(variant, 0.4),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import K-pop merchandise catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== K-pop Merch Import ===")

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

    logger.info(f"\n=== K-pop Merch Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
