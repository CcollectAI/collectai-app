"""
Import One Piece collectibles data (900+ items).

Layer 1 (Catalog):  Curated 600+ items across P.O.P., Figuarts, Ichiban Kuji,
                    Banpresto, Tsume, VAH, WCF, ship models, cards → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated catalog of Portrait of Pirates (Megahouse) incl. NEO-DX, LIMITED,
  Playback Memories, SOC, Maximum lines
- Figuarts ZERO (Extra Battle / extra tall), Variable Action Heroes (VAH)
- Ichiban Kuji Last One prizes, Banpresto DXF / Grandista / King of Artist
- Tsume HQS statues, GEM Series (Megahouse)
- WCF (World Collectable Figure) sets, ship models (Going Merry / Thousand Sunny)
- One Piece Card Game sealed product (booster boxes, promo cards, alt arts)
- Film Red / Stampede special edition figures
- Can be augmented with MyFigureCollection API or scraping later

Usage:
    python -m pipelines.import_one_piece [--dry-run]
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

CATEGORY = "one_piece"


def get_curated_catalog() -> list[dict]:
    """Curated One Piece collectibles catalog (900+ items)."""

    # Format: (line, name, variant, rarity_tier, price_eur)
    # rarity_tier: grail (>200), high (100-200), mid (40-100), standard (<40)

    items = [
        # ── Portrait of Pirates (P.O.P.) Maximum ──────────────────────────
        ("P.O.P. Maximum", "Monkey D. Luffy", "Gear 4 Boundman", "high", 200),
        ("P.O.P. Maximum", "Kaido", "Dragon Form", "grail", 300),
        ("P.O.P. Maximum", "Whitebeard", "Edward Newgate", "grail", 280),
        ("P.O.P. Maximum", "Big Mom", "Charlotte Linlin", "grail", 260),
        ("P.O.P. Maximum", "Monkey D. Luffy", "Gear 5 Sun God Nika", "grail", 320),

        # ── P.O.P. Limited Edition ────────────────────────────────────────
        ("P.O.P. Limited", "Shanks", "Film Red Ver.", "high", 180),
        ("P.O.P. Limited", "Nami", "Wedding Ver.", "high", 190),
        ("P.O.P. Limited", "Nico Robin", "Repaint Ver.", "high", 175),

        # ── P.O.P. Warriors Alliance ──────────────────────────────────────
        ("P.O.P. Warriors Alliance", "Roronoa Zoro", "Wano Country", "high", 160),
        ("P.O.P. Warriors Alliance", "Trafalgar Law", "Wano Country", "high", 140),
        ("P.O.P. Warriors Alliance", "Sanji", "Osoba Mask", "high", 135),

        # ── P.O.P. Sailing Again ──────────────────────────────────────────
        ("P.O.P. Sailing Again", "Nami", "Ver. BB_02", "high", 150),
        ("P.O.P. Sailing Again", "Boa Hancock", "Ver. BB", "high", 170),

        # ── P.O.P. NEO-DX ────────────────────────────────────────────────
        ("P.O.P. NEO-DX", "Portgas D. Ace", "10th Limited", "grail", 250),
        ("P.O.P. NEO-DX", "Crocodile", "", "high", 130),
        ("P.O.P. NEO-DX", "Shanks", "", "grail", 280),
        ("P.O.P. NEO-DX", "Nami", "Ver.2 Repaint", "high", 160),
        ("P.O.P. NEO-DX", "Nico Robin", "", "high", 155),
        ("P.O.P. NEO-DX", "Roronoa Zoro", "10th Limited", "grail", 270),

        # ── P.O.P. SOC (Statue of the Crew) ──────────────────────────────
        ("P.O.P. SOC", "Monkey D. Luffy", "Gear 5", "grail", 280),
        ("P.O.P. SOC", "Jinbe", "", "high", 120),

        # ── P.O.P. Playback Memories ─────────────────────────────────────
        ("P.O.P. Playback Memories", "Portgas D. Ace", "Marineford", "high", 165),
        ("P.O.P. Playback Memories", "Shanks", "Red-Haired Pirates", "high", 170),
        ("P.O.P. Playback Memories", "Koala", "", "mid", 95),
        ("P.O.P. Playback Memories", "Sabo", "Revolutionary Army", "high", 145),
        ("P.O.P. Playback Memories", "Nami", "Arlong Park", "high", 140),

        # ── Figuarts ZERO (Extra Battle / Extra Tall) ─────────────────────
        ("Figuarts ZERO", "Monkey D. Luffy", "Extra Battle Paramount War", "mid", 80),
        ("Figuarts ZERO", "Roronoa Zoro", "Extra Battle", "mid", 70),
        ("Figuarts ZERO", "Sanji", "Extra Battle Diable Jambe", "mid", 65),
        ("Figuarts ZERO", "Portgas D. Ace", "Extra Battle Fire Fist", "high", 100),
        ("Figuarts ZERO", "Marco", "Extra Battle Phoenix", "mid", 75),
        ("Figuarts ZERO", "Eustass Kid", "Extra Battle", "mid", 60),
        ("Figuarts ZERO", "Yamato", "Extra Battle Thunder Bagua", "mid", 85),
        ("Figuarts ZERO", "Kaido", "Extra Battle King of the Beasts", "high", 100),
        ("Figuarts ZERO", "Monkey D. Luffy", "Extra Battle Gear 5 Gigant", "high", 110),
        ("Figuarts ZERO", "Shanks", "Extra Battle Sovereign Haki", "high", 105),
        ("Figuarts ZERO", "Whitebeard", "Extra Battle Paramount War", "high", 115),
        ("Figuarts ZERO", "Kozuki Oden", "Extra Battle", "mid", 75),
        ("Figuarts ZERO", "Sabo", "Extra Battle Fire Fist Inheritance", "mid", 70),

        # ── Variable Action Heroes (VAH) by Megahouse ────────────────────
        ("VAH", "Monkey D. Luffy", "Gear 5", "high", 110),
        ("VAH", "Roronoa Zoro", "Wano Country", "high", 105),
        ("VAH", "Portgas D. Ace", "", "mid", 95),
        ("VAH", "Trafalgar Law", "Wano Country", "mid", 90),
        ("VAH", "Nami", "Punk Hazard Ver.", "mid", 85),

        # ── Ichiban Kuji Prizes ───────────────────────────────────────────
        ("Ichiban Kuji", "Luffy", "Last One Prize Gear 5", "grail", 210),
        ("Ichiban Kuji", "Shanks", "Last One Prize Film Red", "high", 180),
        ("Ichiban Kuji", "Zoro", "Prize A Wano", "high", 120),
        ("Ichiban Kuji", "Kaido", "Prize A Beast Form", "high", 150),
        ("Ichiban Kuji", "Yamato", "Prize B Wano", "mid", 80),
        ("Ichiban Kuji", "Uta", "Last One Prize Film Red", "high", 100),
        ("Ichiban Kuji", "Ace & Luffy", "Prize A Memories", "mid", 90),
        ("Ichiban Kuji", "Law", "Prize B Wano", "mid", 70),
        ("Ichiban Kuji", "Luffy", "Last One Prize Wano Finale", "grail", 220),
        ("Ichiban Kuji", "Roger & Whitebeard", "Last One Prize Legends", "grail", 230),
        ("Ichiban Kuji", "Oden", "Last One Prize Wano", "high", 160),
        ("Ichiban Kuji", "Luffy & Ace & Sabo", "Prize A Brotherhood", "high", 130),

        # ── Banpresto DXF / Grandista / King of Artist ────────────────────
        ("Banpresto", "Monkey D. Luffy", "DXF The Grandline Men", "standard", 20),
        ("Banpresto", "Roronoa Zoro", "DXF The Grandline Men", "standard", 22),
        ("Banpresto", "Sanji", "DXF The Grandline Men", "standard", 18),
        ("Banpresto", "Nami", "Glitter & Glamours", "standard", 25),
        ("Banpresto", "Boa Hancock", "Glitter & Glamours", "standard", 28),
        ("Banpresto", "Monkey D. Luffy", "King of Artist Gear 5", "mid", 40),
        ("Banpresto", "Yamato", "DXF The Grandline Lady", "standard", 25),
        ("Banpresto", "Shanks", "DXF The Grandline Men Film Red", "standard", 30),
        ("Banpresto", "Monkey D. Luffy", "Grandista Manga Dimensions", "mid", 45),
        ("Banpresto", "Roronoa Zoro", "Grandista Manga Dimensions", "mid", 42),
        ("Banpresto", "Portgas D. Ace", "Grandista Manga Dimensions", "mid", 40),
        ("Banpresto", "Trafalgar Law", "DXF The Grandline Men Wano", "standard", 22),
        ("Banpresto", "Nico Robin", "Glitter & Glamours Wano", "standard", 26),

        # ── Tsume HQS Statues ─────────────────────────────────────────────
        ("Tsume HQS", "Monkey D. Luffy", "Red Hawk", "grail", 650),
        ("Tsume HQS", "Roronoa Zoro", "Ashura Ichibugin", "grail", 580),
        ("Tsume HQS", "Portgas D. Ace", "Fire Fist", "grail", 520),
        ("Tsume HQS", "Trafalgar Law", "Gamma Knife", "grail", 480),

        # ── GEM Series by Megahouse ───────────────────────────────────────
        ("GEM Series", "Monkey D. Luffy", "Run! Run! Run!", "high", 120),
        ("GEM Series", "Roronoa Zoro", "Wano Country", "high", 115),
        ("GEM Series", "Sanji", "Wano Country", "high", 110),
        ("GEM Series", "Portgas D. Ace", "15th Anniversary", "high", 135),
        ("GEM Series", "Boa Hancock", "Ver. BB Repaint", "high", 125),

        # ── WCF (World Collectable Figure) Sets ──────────────────────────
        ("WCF", "Straw Hat Crew", "Vol. 1 Complete Set (8 pcs)", "mid", 55),
        ("WCF", "Wano Country", "Vol. 1 Complete Set (6 pcs)", "mid", 48),
        ("WCF", "Film Red", "Complete Set (6 pcs)", "mid", 42),
        ("WCF", "Whole Cake Island", "Complete Set (6 pcs)", "mid", 40),
        ("WCF", "20th Anniversary", "Complete Set (6 pcs)", "mid", 60),
        ("WCF", "Beasts Pirates", "Complete Set (6 pcs)", "mid", 45),

        # ── Ship Models ───────────────────────────────────────────────────
        ("Ship Model", "Going Merry", "Chogokin", "grail", 320),
        ("Ship Model", "Thousand Sunny", "Chogokin", "grail", 350),
        ("Ship Model", "Going Merry", "Grand Ship Collection", "standard", 25),
        ("Ship Model", "Thousand Sunny", "Grand Ship Collection", "standard", 28),
        ("Ship Model", "Polar Tang", "Grand Ship Collection", "standard", 22),
        ("Ship Model", "Going Merry", "Soul of Chogokin Anniversary", "grail", 420),

        # ── One Piece Card Game – Sealed Product & Promo ──────────────────
        ("OP Card Game", "Monkey D. Luffy", "OP01 Leader Alt Art", "mid", 40),
        ("OP Card Game", "Roronoa Zoro", "OP01 SP Alt Art", "high", 120),
        ("OP Card Game", "Shanks", "OP01 SEC Alt Art", "high", 150),
        ("OP Card Game", "Nami", "OP01 SP Alt Art", "high", 100),
        ("OP Card Game", "Trafalgar Law", "OP02 Leader Alt Art", "mid", 50),
        ("OP Card Game", "Yamato", "OP02 SEC", "mid", 60),
        ("OP Card Game", "Monkey D. Luffy", "OP05 Gear 5 SEC", "grail", 210),
        ("OP Card Game", "Charlotte Katakuri", "OP03 Leader Alt Art", "mid", 45),
        ("OP Card Game", "Romance Dawn", "OP01 Booster Box Sealed", "high", 130),
        ("OP Card Game", "Paramount War", "OP02 Booster Box Sealed", "high", 110),
        ("OP Card Game", "Pillars of Strength", "OP03 Booster Box Sealed", "mid", 95),
        ("OP Card Game", "Kingdoms of Intrigue", "OP04 Booster Box Sealed", "mid", 90),
        ("OP Card Game", "Awakening of the New Era", "OP05 Booster Box Sealed", "high", 140),
        ("OP Card Game", "Wings of the Captain", "OP06 Booster Box Sealed", "mid", 85),
        ("OP Card Game", "Monkey D. Luffy", "Promo Tournament Pack", "high", 110),
        ("OP Card Game", "Roronoa Zoro", "Promo Winner Card", "grail", 220),
        ("OP Card Game", "Enel", "OP05 SEC Alt Art", "mid", 65),

        # ── Film Red / Stampede / Special Edition Figures ─────────────────
        ("Film Red", "Uta", "DXF Film Red", "mid", 40),
        ("Film Red", "Shanks", "DXF Film Red Special", "mid", 50),
        ("Film Red", "Luffy", "Figuarts ZERO Film Red", "mid", 65),
        ("Film Red", "Uta", "Ichiban Kuji Prize A", "mid", 75),
        ("Stampede", "Bullet", "DXF Stampede", "mid", 45),
        ("Stampede", "Monkey D. Luffy", "Ichiban Kuji Stampede Last One", "high", 130),
        ("Film Gold", "Luffy Film Gold", "DXF Special", "mid", 40),

        # ── Anniversary / Limited ─────────────────────────────────────────
        ("20th Anniversary", "Monkey D. Luffy", "Ichiban Kuji 20th Anniv", "high", 130),
        ("25th Anniversary", "Straw Hat Crew", "Complete Figure Set", "grail", 250),

        # ── Gear 5 Luffy Figures (Various Makers) ───────────────────────
        ("Banpresto", "Monkey D. Luffy", "King of Artist Gear 5 Special", "mid", 55),
        ("Banpresto", "Monkey D. Luffy", "DXF Gear 5 Nika Form", "mid", 42),
        ("S.H.Figuarts", "Monkey D. Luffy", "Gear 5 Nika", "high", 120),
        ("MegaHouse", "Monkey D. Luffy", "Look Up Series Gear 5", "standard", 28),

        # ── Film Red Merchandise ────────────────────────────────────────
        ("Film Red", "Uta", "S.H.Figuarts Film Red", "high", 100),
        ("Film Red", "Uta", "Glitter & Glamours Film Red", "standard", 30),
        ("Film Red", "Shanks", "Figuarts ZERO Film Red Extra Battle", "high", 110),

        # ── One Piece Card Game Accessories ─────────────────────────────
        ("OP Card Game", "Playmat", "Official OP01 Tournament Playmat", "mid", 55),
        ("OP Card Game", "Deck Box", "Official Monkey D. Luffy Deck Box", "standard", 22),
        ("OP Card Game", "Sleeves", "Official Nami Art Sleeves 70ct", "standard", 15),
        ("OP Card Game", "Playmat", "Official OP05 Gear 5 Playmat", "mid", 65),

        # ── Ichiban Kuji — Additional Prizes ────────────────────────────
        ("Ichiban Kuji", "Luffy", "Prize A Gear 5 Full Power", "high", 140),
        ("Ichiban Kuji", "Zoro", "Last One Prize King of Hell", "grail", 250),
        ("Ichiban Kuji", "Sanji", "Prize A Ifrit Jambe", "high", 110),
        ("Ichiban Kuji", "Nami", "Prize B Zeus Weather Art", "mid", 70),

        # ── One Piece x Uniqlo UT Collaboration ────────────────────────
        ("Uniqlo UT", "Luffy", "Gear 5 Graphic Tee", "standard", 20),
        ("Uniqlo UT", "Straw Hat Crew", "25th Anniversary Box Set (5 Tees)", "mid", 80),

        # ── WCF (World Collectable Figure) — Additional Sets ───────────
        ("WCF", "Egg Head", "Vol. 1 Complete Set (6 pcs)", "mid", 50),
        ("WCF", "Gear 5 Series", "Complete Set (5 pcs)", "mid", 55),

        # ── Figuarts ZERO Extra Battle — Additional ─────────────────────
        ("Figuarts ZERO", "Kaido", "Extra Battle King of Beasts (Man-Beast Form)", "high", 130),
        ("Figuarts ZERO", "Big Mom", "Extra Battle Soul Pocus", "high", 120),

        # ── One Piece Magazine Figures ──────────────────────────────────
        ("Magazine Figure", "Monkey D. Luffy", "Special Episode Vol. 1", "mid", 45),
        ("Magazine Figure", "Portgas D. Ace", "Special Episode Vol. 2", "mid", 48),
        ("Magazine Figure", "Nami", "Special Episode Vol. 1 Dress", "mid", 40),

        # ── Ship Models — Additional ───────────────────────────────────
        ("Ship Model", "Thousand Sunny", "Flying Model Grand Ship Collection", "standard", 32),
        ("Ship Model", "Red Force", "Grand Ship Collection", "standard", 25),
        ("Ship Model", "Going Merry", "Memorial Log Grand Ship", "mid", 55),

        # ── Treasure Cruise / Bounty Rush Collab Merch ──────────────────
        ("Collab Merch", "Monkey D. Luffy", "Bounty Rush 5th Anniversary Acrylic Stand", "standard", 18),
        ("Collab Merch", "Roronoa Zoro", "Treasure Cruise 10th Anniv. Figure", "mid", 45),

        # ── Vintage / Early Collectibles ────────────────────────────────
        ("Gashapon", "Monkey D. Luffy", "Original Bandai Gashapon 2000 Set", "high", 150),
        ("Gashapon", "Roronoa Zoro", "Original Bandai Gashapon 2001", "high", 130),
        ("MFSP", "Monkey D. Luffy", "Master Stars Piece Original Release", "high", 110),
        ("MFSP", "Roronoa Zoro", "Master Stars Piece Original Release", "high", 105),

        # ── P.O.P. I.R.O (In Resin Option) ────────────────────────────────
        ("P.O.P. I.R.O", "Monkey D. Luffy", "Gear 4 Snakeman", "grail", 350),
        ("P.O.P. I.R.O", "Roronoa Zoro", "Enma Wano", "grail", 320),

        # ── P.O.P. SA-MAXIMUM ─────────────────────────────────────────────
        ("P.O.P. SA-MAXIMUM", "Portgas D. Ace", "Fire Fist Cross", "grail", 280),
        ("P.O.P. SA-MAXIMUM", "Sabo", "Dragon Claw Fire Fist", "grail", 260),

        # ── S.H.Figuarts Additional ────────────────────────────────────────
        ("S.H.Figuarts", "Roronoa Zoro", "King of Hell Three Sword Style", "high", 130),
        ("S.H.Figuarts", "Sanji", "Ifrit Jambe Wano", "high", 110),
        ("S.H.Figuarts", "Nami", "Zou Arc", "mid", 90),
        ("S.H.Figuarts", "Nico Robin", "Wano Country", "mid", 95),

        # ── Figuarts ZERO — Demon Slayer Battle Set ────────────────────────
        ("Figuarts ZERO", "Jinbe", "Extra Battle Fish-Man Karate", "mid", 70),
        ("Figuarts ZERO", "Nico Robin", "Extra Battle Demonio Fleur", "mid", 75),
        ("Figuarts ZERO", "Chopper", "Extra Battle Monster Point", "mid", 60),
        ("Figuarts ZERO", "Brook", "Extra Battle Soul King", "mid", 65),
        ("Figuarts ZERO", "Franky", "Extra Battle General Franky", "high", 110),
        ("Figuarts ZERO", "Nami", "Extra Battle Zeus Breeze Tempo", "mid", 70),

        # ── VAH Additional ─────────────────────────────────────────────────
        ("VAH", "Sanji", "Wano Country", "mid", 95),
        ("VAH", "Boa Hancock", "Ver. Blue", "mid", 90),
        ("VAH", "Shanks", "Film Red Ver.", "high", 115),
        ("VAH", "Yamato", "Wano Country", "high", 110),

        # ── Banpresto DXF / Grandista Additional ──────────────────────────
        ("Banpresto", "Chopper", "DXF The Grandline Children", "standard", 18),
        ("Banpresto", "Jinbe", "DXF The Grandline Men Wano", "standard", 25),
        ("Banpresto", "Brook", "DXF The Grandline Men", "standard", 20),
        ("Banpresto", "Franky", "DXF The Grandline Men", "standard", 22),
        ("Banpresto", "Nico Robin", "Grandista Manga Dimensions", "mid", 45),
        ("Banpresto", "Boa Hancock", "Grandista Manga Dimensions", "mid", 48),

        # ── GEM Series Additional ──────────────────────────────────────────
        ("GEM Series", "Nami", "Wano Country", "high", 120),
        ("GEM Series", "Yamato", "Thunder Bagua", "high", 130),
        ("GEM Series", "Boa Hancock", "Wano Country", "high", 125),

        # ── Ichiban Kuji — Egg Head Arc ────────────────────────────────────
        ("Ichiban Kuji", "Luffy", "Prize A Gear 5 Egg Head", "high", 150),
        ("Ichiban Kuji", "Kizaru", "Last One Prize Egg Head", "grail", 200),
        ("Ichiban Kuji", "Vegapunk (Stella)", "Prize B Egg Head", "mid", 80),
        ("Ichiban Kuji", "Bonney", "Prize C Egg Head", "mid", 65),

        # ── Tsume HQS+ Additional ─────────────────────────────────────────
        ("Tsume HQS+", "Shanks", "Gryphon Slash", "grail", 750),
        ("Tsume HQS+", "Kaido", "Dragon Form Statue", "grail", 800),

        # ── One Piece Card Game — OP07 / OP08 ─────────────────────────────
        ("OP Card Game", "Rob Lucci", "OP07 Leader Alt Art", "mid", 40),
        ("OP Card Game", "Jewelry Bonney", "OP07 SEC Alt Art", "high", 120),
        ("OP Card Game", "Vegapunk", "OP08 Leader Alt Art", "mid", 45),
        ("OP Card Game", "Monkey D. Luffy", "OP07 SEC Gear 5 Nika Alt Art", "grail", 250),
        ("OP Card Game", "500 Years in the Future", "OP07 Booster Box Sealed", "mid", 85),
        ("OP Card Game", "Two Legends", "OP08 Booster Box Sealed", "mid", 90),
        ("OP Card Game", "Shanks", "OP01 SEC Manga Art", "grail", 220),

        # ── WCF — Additional Sets ─────────────────────────────────────────
        ("WCF", "Wano Country", "Vol. 2 Complete Set (6 pcs)", "mid", 50),
        ("WCF", "Reverie Arc", "Complete Set (6 pcs)", "mid", 45),
        ("WCF", "Straw Hat Crew", "Chibi Wano Set (9 pcs)", "mid", 65),

        # ── One Piece Manga Box Sets ──────────────────────────────────────
        ("Manga Box Set", "East Blue", "Box Set 1 Vols. 1-23", "mid", 95),
        ("Manga Box Set", "Skypiea-Thriller Bark", "Box Set 2 Vols. 24-46", "mid", 95),
        ("Manga Box Set", "Dressrosa", "Box Set 3 Vols. 47-70", "mid", 95),
        ("Manga Box Set", "Wano", "Box Set 4 Vols. 71-90", "mid", 95),

        # ── Ship Models — Premium ─────────────────────────────────────────
        ("Ship Model", "Moby Dick", "Grand Ship Collection", "standard", 25),
        ("Ship Model", "Ark Maxim", "Grand Ship Collection", "standard", 28),
        ("Ship Model", "Thousand Sunny", "Perfect Grade 1/144", "high", 180),

        # ── One Piece Live-Action Merchandise ──────────────────────────────
        ("Live-Action", "Straw Hat Crew", "Netflix Live-Action Figure Set (5 pcs)", "mid", 80),
        ("Live-Action", "Monkey D. Luffy", "Netflix Straw Hat Prop Replica", "mid", 55),

        # ── Nendoroid Series ──────────────────────────────────────────────
        ("Nendoroid", "Monkey D. Luffy", "Nendoroid Film Red Ver.", "mid", 50),
        ("Nendoroid", "Roronoa Zoro", "Nendoroid Wano Ver.", "mid", 55),

        # ── P.O.P. MAS (Mild & Sweet) ──────────────────────────────────────
        ("P.O.P. MAS", "Nami", "Ver. A", "high", 140),
        ("P.O.P. MAS", "Nico Robin", "Ver. BB", "high", 155),
        ("P.O.P. MAS", "Boa Hancock", "Ver. 3D2Y", "high", 165),
        ("P.O.P. MAS", "Vivi", "Alabasta Ver.", "high", 130),
        ("P.O.P. MAS", "Perona", "Thriller Bark Ver.", "high", 145),
        ("P.O.P. MAS", "Shirahoshi", "Mermaid Princess", "high", 180),
        ("P.O.P. MAS", "Rebecca", "Gladiator Ver.", "high", 125),

        # ── P.O.P. DX ──────────────────────────────────────────────────────
        ("P.O.P. DX", "Monkey D. Luffy", "Marineford Ver.", "high", 180),
        ("P.O.P. DX", "Trafalgar Law", "Water Seven", "high", 160),
        ("P.O.P. DX", "Smoker", "Marine Ver.", "high", 140),
        ("P.O.P. DX", "Dracule Mihawk", "World's Strongest Swordsman", "high", 175),
        ("P.O.P. DX", "Boa Hancock", "Ver. BB_02", "high", 170),

        # ── P.O.P. Limited — Additional ─────────────────────────────────────
        ("P.O.P. Limited", "Nico Robin", "Dereshi! Ver.", "high", 180),
        ("P.O.P. Limited", "Nami", "Swim Wear Ver. Pink", "high", 190),
        ("P.O.P. Limited", "Boa Hancock", "Wedding Ver.", "high", 200),
        ("P.O.P. Limited", "Vinsmoke Reiju", "Germa 66", "high", 160),

        # ── Ichiban Kuji — Full Sets & Additional Prizes ─────────────────────
        ("Ichiban Kuji", "Straw Hat Crew", "Wano Full Set (A-G + Last One)", "grail", 450),
        ("Ichiban Kuji", "Gear 5 Luffy", "Prize A - In Memory of Legends", "high", 140),
        ("Ichiban Kuji", "Shanks", "Last One Prize - Red Hair Pirates", "grail", 200),
        ("Ichiban Kuji", "Kaido vs Luffy", "Last One Prize - New Dawn", "grail", 250),
        ("Ichiban Kuji", "Boa Hancock", "Prize A - Girl's Collection", "high", 120),
        ("Ichiban Kuji", "Uta", "Prize A - Film Red Full Power", "high", 110),
        ("Ichiban Kuji", "Yamato", "Last One Prize - Wano Thunder", "high", 180),
        ("Ichiban Kuji", "Luffy & Shanks", "Prize A - New Chapter", "high", 150),
        ("Ichiban Kuji", "Zoro & Sanji", "Prize B - New Chapter", "high", 130),
        ("Ichiban Kuji", "Robin", "Prize C - Girls Colosseum", "mid", 85),
        ("Ichiban Kuji", "Nami", "Prize A - Girls Colosseum", "high", 100),

        # ── One Piece Card Game — OP09 / OP10 / OP11 ────────────────────────
        ("OP Card Game", "Monkey D. Luffy", "OP09 Leader Alt Art (4th Gear)", "mid", 50),
        ("OP Card Game", "Nico Robin", "OP09 SEC Alt Art", "high", 110),
        ("OP Card Game", "Roronoa Zoro", "OP09 SEC King of Hell Alt Art", "grail", 200),
        ("OP Card Game", "Edward Newgate", "OP09 Leader Alt Art", "mid", 45),
        ("OP Card Game", "Shanks", "OP10 SEC Film Red Alt Art", "high", 150),
        ("OP Card Game", "Portgas D. Ace", "OP10 SEC Alt Art", "high", 130),
        ("OP Card Game", "Nami", "OP10 Leader Alt Art (Zeus)", "mid", 55),
        ("OP Card Game", "Yamato", "OP10 SEC Dragon Form Alt Art", "high", 120),
        ("OP Card Game", "Sanji", "OP11 SEC Ifrit Jambe Alt Art", "high", 110),
        ("OP Card Game", "Monkey D. Luffy", "OP11 SEC Nika Joy Boy Alt Art", "grail", 280),
        ("OP Card Game", "Jinbe", "OP11 Leader Alt Art", "mid", 40),
        ("OP Card Game", "500 Years in the Future", "OP07 Booster Box Sealed JP", "mid", 80),
        ("OP Card Game", "Two Legends", "OP08 Booster Box Sealed JP", "mid", 85),
        ("OP Card Game", "Memorial Collection", "OP09 Booster Box Sealed", "mid", 90),
        ("OP Card Game", "Royal Bloodlines", "OP10 Booster Box Sealed", "mid", 85),
        ("OP Card Game", "Emperors on the March", "OP11 Booster Box Sealed", "mid", 90),

        # ── One Piece Card Game — Starter Decks & Promo ──────────────────────
        ("OP Card Game", "Straw Hat Crew", "ST-01 Starter Deck Sealed", "standard", 22),
        ("OP Card Game", "Worst Generation", "ST-02 Starter Deck Sealed", "standard", 20),
        ("OP Card Game", "Big Mom Pirates", "ST-07 Starter Deck Sealed", "standard", 18),
        ("OP Card Game", "Monkey D. Luffy", "Championship 2023 Promo Card", "grail", 300),
        ("OP Card Game", "Roronoa Zoro", "Pre-Release Promo Foil", "high", 100),
        ("OP Card Game", "Eustass Kid", "OP06 SEC Alt Art", "high", 100),

        # ── One Piece Card Game — Accessories Additional ──────────────────────
        ("OP Card Game", "Playmat", "Official OP09 Gear 5 Nika Playmat", "mid", 70),
        ("OP Card Game", "Playmat", "Official OP02 Ace vs Akainu Playmat", "mid", 55),
        ("OP Card Game", "Deck Box", "Official Shanks Premium Deck Box", "standard", 25),
        ("OP Card Game", "Sleeves", "Official Gear 5 Art Sleeves 70ct", "standard", 18),

        # ── Manga First Printings ────────────────────────────────────────────
        ("Manga", "One Piece Vol. 1", "First Print (Japanese, 1997)", "grail", 500),
        ("Manga", "One Piece Vol. 1", "First Print (English, 2003)", "grail", 350),
        ("Manga", "One Piece Vol. 61", "First Print (Japanese, 600M Copy)", "high", 120),
        ("Manga", "One Piece Vol. 100", "First Print (Japanese, Commemoration)", "high", 100),
        ("Manga", "One Piece Vol. 100", "Limited Collector's Edition (JP)", "high", 150),
        ("Manga", "Weekly Shonen Jump", "Issue #34 1997 (OP Chapter 1)", "grail", 800),

        # ── Film Gold / Film Z Merchandise ────────────────────────────────────
        ("Film Gold", "Luffy Film Gold", "Figuarts ZERO Gold", "mid", 60),
        ("Film Gold", "Sabo Film Gold", "DXF Film Gold", "mid", 45),
        ("Film Gold", "Tesoro Film Gold", "DXF Film Gold Special", "mid", 50),
        ("Film Z", "Luffy Film Z", "Figuarts ZERO Film Z", "mid", 55),
        ("Film Z", "Zephyr", "DXF Film Z", "mid", 45),
        ("Film Z", "Ain", "DXF Film Z", "mid", 40),

        # ── Stampede Merchandise — Additional ─────────────────────────────────
        ("Stampede", "Sabo", "Ichiban Kuji Stampede Prize A", "high", 100),
        ("Stampede", "Hancock", "DXF Stampede", "mid", 40),
        ("Stampede", "Douglas Bullet", "Ichiban Kuji Stampede Prize B", "mid", 80),

        # ── DXF Figures — Additional ─────────────────────────────────────────
        ("Banpresto", "Yamato", "King of Artist Wano", "mid", 45),
        ("Banpresto", "Sanji", "King of Artist Wano", "mid", 42),
        ("Banpresto", "Portgas D. Ace", "King of Artist Fire Fist", "mid", 48),
        ("Banpresto", "Kaido", "DXF The Grandline Men Beast Form", "mid", 40),
        ("Banpresto", "Kozuki Oden", "DXF The Grandline Men Wano", "standard", 28),
        ("Banpresto", "Luffy", "DXF The Grandline Children Gear 5", "standard", 22),

        # ── GEM Series — Additional ─────────────────────────────────────────
        ("GEM Series", "Trafalgar Law", "Punk Hazard Ver.", "high", 115),
        ("GEM Series", "Shanks", "Film Red Ver.", "high", 135),
        ("GEM Series", "Marco", "Phoenix Form", "high", 130),
        ("GEM Series", "Nico Robin", "Dereshi! Ver.", "high", 120),
        ("GEM Series", "Crocodile", "Reverie Ver.", "high", 110),

        # ── WCF — Remaining Sets ─────────────────────────────────────────────
        ("WCF", "Fishman Island", "Complete Set (6 pcs)", "mid", 45),
        ("WCF", "Dressrosa", "Complete Set (6 pcs)", "mid", 48),
        ("WCF", "Marineford", "Complete Set (8 pcs)", "mid", 65),
        ("WCF", "Impel Down", "Complete Set (6 pcs)", "mid", 50),
        ("WCF", "Sabaody", "Complete Set (6 pcs)", "mid", 45),
        ("WCF", "Zou", "Complete Set (5 pcs)", "mid", 42),

        # ── Ship Models — Additional ─────────────────────────────────────────
        ("Ship Model", "Oro Jackson", "Grand Ship Collection", "standard", 28),
        ("Ship Model", "Miss Love Duck", "Grand Ship Collection", "standard", 22),
        ("Ship Model", "Going Merry", "One Piece Mega WCF Ship", "mid", 60),
        ("Ship Model", "Thousand Sunny", "Real McCoy 01 LED Edition", "grail", 280),

        # ── Figuarts ZERO — Additional ───────────────────────────────────────
        ("Figuarts ZERO", "Trafalgar Law", "Extra Battle Gamma Knife", "mid", 80),
        ("Figuarts ZERO", "Monkey D. Luffy", "Extra Battle One Piece Film Red", "mid", 75),
        ("Figuarts ZERO", "Dracule Mihawk", "Extra Battle Cross Guild", "mid", 85),
        ("Figuarts ZERO", "Buggy", "Extra Battle Cross Guild Emperor", "mid", 70),
        ("Figuarts ZERO", "Crocodile", "Extra Battle Cross Guild", "mid", 75),

        # ── VAH — Additional ────────────────────────────────────────────────
        ("VAH", "Monkey D. Luffy", "Wano Country", "high", 100),
        ("VAH", "Nico Robin", "Wano Country", "mid", 95),
        ("VAH", "Jinbe", "Wano Country", "mid", 90),
        ("VAH", "Brook", "Whole Cake Island", "mid", 85),

        # ── Tsume Additional Statues ─────────────────────────────────────────
        ("Tsume HQS", "Sanji", "Diable Jambe", "grail", 500),
        ("Tsume HQS", "Whitebeard", "Supreme Quake", "grail", 700),
        ("Tsume HQS", "Boa Hancock", "Slave Arrow", "grail", 450),

        # ── Nendoroid — Additional ──────────────────────────────────────────
        ("Nendoroid", "Nami", "Nendoroid Whole Cake Island", "mid", 50),
        ("Nendoroid", "Sanji", "Nendoroid Wano Ver.", "mid", 55),
        ("Nendoroid", "Chopper", "Nendoroid Cotton Candy Lover", "mid", 45),
        ("Nendoroid", "Trafalgar Law", "Nendoroid Dressrosa Ver.", "mid", 55),
        ("Nendoroid", "Boa Hancock", "Nendoroid Amazon Lily Ver.", "mid", 50),

        # ── S.H.Figuarts — Additional ────────────────────────────────────────
        ("S.H.Figuarts", "Portgas D. Ace", "Fire Fist", "high", 120),
        ("S.H.Figuarts", "Monkey D. Luffy", "Wano Country", "high", 110),
        ("S.H.Figuarts", "Trafalgar Law", "Wano Country", "high", 115),
        ("S.H.Figuarts", "Shanks", "Red Hair Pirates", "high", 130),
        ("S.H.Figuarts", "Kaido", "Man-Beast Form", "high", 150),

        # ── Banpresto Chronicle Master Stars — Additional ─────────────────────
        ("Banpresto", "Monkey D. Luffy", "Chronicle Master Stars Piece", "mid", 55),
        ("Banpresto", "Roronoa Zoro", "Chronicle Master Stars Piece", "mid", 50),
        ("Banpresto", "Portgas D. Ace", "Chronicle Master Stars Piece", "mid", 52),

        # ── Live-Action — Additional ─────────────────────────────────────────
        ("Live-Action", "Roronoa Zoro", "Netflix Prop Replica Wado Ichimonji", "mid", 75),
        ("Live-Action", "Nami", "Netflix Figure (Season 1)", "mid", 45),
        ("Live-Action", "Sanji", "Netflix Figure (Season 1)", "mid", 45),
        ("Live-Action", "Buggy", "Netflix Figure (Season 1)", "mid", 50),

        # ── One Piece x Uniqlo — Additional ──────────────────────────────────
        ("Uniqlo UT", "Roronoa Zoro", "Enma Graphic Tee", "standard", 20),
        ("Uniqlo UT", "Nami", "Zeus Graphic Tee", "standard", 18),
        ("Uniqlo UT", "Shanks", "Film Red Graphic Tee", "standard", 20),

        # ── P.O.P. Maximum — Additional ──────────────────────────────────────
        ("P.O.P. Maximum", "Shanks", "Red-Haired Pirates Captain", "grail", 350),
        ("P.O.P. Maximum", "Trafalgar Law", "Ope Ope no Mi Awakening", "grail", 280),
        ("P.O.P. Maximum", "Roronoa Zoro", "King of Hell Three Swords", "grail", 300),
        ("P.O.P. Maximum", "Sanji", "Ifrit Jambe", "grail", 260),
        ("P.O.P. Maximum", "Yamato", "Thunder Bagua Okuchi no Makami", "grail", 290),

        # ── P.O.P. SA-MAXIMUM — Additional ──────────────────────────────────
        ("P.O.P. SA-MAXIMUM", "Monkey D. Luffy", "Gear 4 Snakeman", "grail", 300),
        ("P.O.P. SA-MAXIMUM", "Charlotte Katakuri", "Mochi Mochi no Mi", "grail", 280),
        ("P.O.P. SA-MAXIMUM", "Marco", "Phoenix Form", "grail", 260),
        ("P.O.P. SA-MAXIMUM", "Jinbe", "Fish-Man Karate", "grail", 240),
        ("P.O.P. SA-MAXIMUM", "Enel", "God of Skypiea 200M Volt", "grail", 320),

        # ── P.O.P. Warriors Alliance — Additional ───────────────────────────
        ("P.O.P. Warriors Alliance", "Kaido", "Man-Beast Form", "grail", 250),
        ("P.O.P. Warriors Alliance", "Yamato", "Okuchi no Makami", "high", 170),
        ("P.O.P. Warriors Alliance", "Kin'emon", "Foxfire Style", "high", 130),
        ("P.O.P. Warriors Alliance", "Marco", "Phoenix Wano", "high", 160),
        ("P.O.P. Warriors Alliance", "Killer", "Punisher", "high", 135),
        ("P.O.P. Warriors Alliance", "Queen", "Brachio Bomber", "high", 145),
        ("P.O.P. Warriors Alliance", "King", "Lunarian Form", "high", 170),

        # ── P.O.P. NEO-DX — Additional ──────────────────────────────────────
        ("P.O.P. NEO-DX", "Dracule Mihawk", "World's Strongest Swordsman", "grail", 300),
        ("P.O.P. NEO-DX", "Sanji", "Black Leg", "high", 150),
        ("P.O.P. NEO-DX", "Franky", "Super", "high", 140),
        ("P.O.P. NEO-DX", "Brook", "Soul King", "high", 135),

        # ── P.O.P. Playback Memories — Additional ───────────────────────────
        ("P.O.P. Playback Memories", "Vivi", "Alabasta Princess", "high", 130),
        ("P.O.P. Playback Memories", "Chopper", "Drum Island", "mid", 90),
        ("P.O.P. Playback Memories", "Robin", "Ohara Scholar", "high", 145),

        # ── Ichiban Kuji — Full Lottery Sets ─────────────────────────────────
        ("Ichiban Kuji", "One Piece EX Legends Over Time", "Full Set (A-G + Last One)", "grail", 500),
        ("Ichiban Kuji", "One Piece EX Devil Fruit Users", "Full Set (A-F + Last One)", "grail", 480),
        ("Ichiban Kuji", "One Piece Great Banquet", "Full Set (A-H + Last One)", "grail", 420),
        ("Ichiban Kuji", "Luffy", "Prize A - Reverie Arc", "high", 130),
        ("Ichiban Kuji", "Sabo", "Last One Prize - Flame Emperor", "grail", 210),
        ("Ichiban Kuji", "Whitebeard", "Prize A - Paramount War Memorial", "high", 160),
        ("Ichiban Kuji", "Big Mom", "Prize B - Whole Cake Celebration", "high", 120),
        ("Ichiban Kuji", "Chopper", "Prize C - Cotton Candy Lover Special", "mid", 60),
        ("Ichiban Kuji", "Franky", "Prize D - General Franky Limited", "mid", 75),
        ("Ichiban Kuji", "Brook", "Prize C - Soul King Performance", "mid", 65),

        # ── OP Card Game — OP01 Complete SEC/Alt Arts ────────────────────────
        ("OP Card Game", "Trafalgar Law", "OP01 SEC Alt Art", "high", 130),
        ("OP Card Game", "Donquixote Doflamingo", "OP01 SR Alt Art", "mid", 45),
        ("OP Card Game", "Boa Hancock", "OP01 SR Alt Art", "mid", 50),
        ("OP Card Game", "Kaido", "OP01 SR Alt Art", "mid", 55),

        # ── OP Card Game — OP02 Complete SEC/Alt Arts ────────────────────────
        ("OP Card Game", "Portgas D. Ace", "OP02 SEC Alt Art", "high", 120),
        ("OP Card Game", "Edward Newgate", "OP02 SEC Alt Art", "high", 140),
        ("OP Card Game", "Sanji", "OP02 SR Alt Art", "mid", 40),

        # ── OP Card Game — OP03 Complete SEC/Alt Arts ────────────────────────
        ("OP Card Game", "Monkey D. Luffy", "OP03 SEC Gear 4 Alt Art", "high", 150),
        ("OP Card Game", "Yamato", "OP03 SEC Alt Art", "high", 110),
        ("OP Card Game", "Nami", "OP03 SR Alt Art", "mid", 40),

        # ── OP Card Game — OP04 Complete SEC/Alt Arts ────────────────────────
        ("OP Card Game", "Monkey D. Luffy", "OP04 SEC Alt Art", "high", 130),
        ("OP Card Game", "Boa Hancock", "OP04 SEC Alt Art", "high", 100),
        ("OP Card Game", "Sabo", "OP04 SR Alt Art", "mid", 55),

        # ── OP Card Game — OP05 Complete SEC/Alt Arts ────────────────────────
        ("OP Card Game", "Trafalgar Law", "OP05 SEC Alt Art", "high", 120),
        ("OP Card Game", "Sabo", "OP05 SEC Alt Art", "high", 110),

        # ── OP Card Game — OP06 Complete SEC/Alt Arts ────────────────────────
        ("OP Card Game", "Roronoa Zoro", "OP06 SEC Alt Art", "high", 140),
        ("OP Card Game", "Monkey D. Luffy", "OP06 SEC Red Hawk Alt Art", "high", 160),
        ("OP Card Game", "Sanji", "OP06 SR Alt Art", "mid", 45),

        # ── OP Card Game — Premium Booster Sets ─────────────────────────────
        ("OP Card Game", "Premium Card Collection", "Best Selection Vol. 1", "mid", 65),
        ("OP Card Game", "Premium Card Collection", "Film Red Edition", "mid", 60),
        ("OP Card Game", "Premium Card Collection", "25th Anniversary Edition", "high", 100),
        ("OP Card Game", "Premium Card Collection", "Live Action Edition", "mid", 55),

        # ── Figuarts ZERO — Devil Fruit Series ──────────────────────────────
        ("Figuarts ZERO", "Enel", "Extra Battle 200M Volt", "mid", 80),
        ("Figuarts ZERO", "Akainu", "Extra Battle Magma Fist", "mid", 85),
        ("Figuarts ZERO", "Aokiji", "Extra Battle Ice Age", "mid", 80),
        ("Figuarts ZERO", "Kizaru", "Extra Battle Sacred Treasure", "mid", 75),
        ("Figuarts ZERO", "Blackbeard", "Extra Battle Yami Yami", "high", 100),
        ("Figuarts ZERO", "Rob Lucci", "Extra Battle Leopard Form", "mid", 75),

        # ── S.H.Figuarts — Complete Straw Hat Crew ──────────────────────────
        ("S.H.Figuarts", "Chopper", "Monster Point Wano", "high", 100),
        ("S.H.Figuarts", "Brook", "Soul King Wano", "high", 105),
        ("S.H.Figuarts", "Franky", "General Franky Wano", "high", 120),
        ("S.H.Figuarts", "Jinbe", "Fish-Man Karate Wano", "high", 110),
        ("S.H.Figuarts", "Yamato", "Thunder Bagua", "high", 130),
        ("S.H.Figuarts", "Boa Hancock", "Amazon Lily Queen", "high", 115),
        ("S.H.Figuarts", "Dracule Mihawk", "Cross Guild", "high", 140),

        # ── Banpresto King of Artist — Additional ───────────────────────────
        ("Banpresto", "Trafalgar Law", "King of Artist Wano", "mid", 45),
        ("Banpresto", "Shanks", "King of Artist Film Red", "mid", 50),
        ("Banpresto", "Boa Hancock", "King of Artist Amazon Lily", "mid", 48),
        ("Banpresto", "Nami", "King of Artist Wano", "mid", 42),
        ("Banpresto", "Nico Robin", "King of Artist Wano Demon Form", "mid", 48),

        # ── Banpresto Chronicle Master Stars — Additional ────────────────────
        ("Banpresto", "Sanji", "Chronicle Master Stars Piece Ifrit", "mid", 52),
        ("Banpresto", "Trafalgar Law", "Chronicle Master Stars Piece", "mid", 50),
        ("Banpresto", "Shanks", "Chronicle Master Stars Piece", "mid", 55),

        # ── Banpresto Grandista — Additional ─────────────────────────────────
        ("Banpresto", "Shanks", "Grandista Nero", "mid", 48),
        ("Banpresto", "Nami", "Grandista Manga Dimensions Wano", "mid", 45),
        ("Banpresto", "Sanji", "Grandista Manga Dimensions Wano", "mid", 42),

        # ── Nendoroid — Complete Line ────────────────────────────────────────
        ("Nendoroid", "Portgas D. Ace", "Nendoroid Fire Fist", "mid", 55),
        ("Nendoroid", "Shanks", "Nendoroid Film Red Ver.", "mid", 55),
        ("Nendoroid", "Uta", "Nendoroid Film Red Ver.", "mid", 50),
        ("Nendoroid", "Yamato", "Nendoroid Wano Ver.", "mid", 55),
        ("Nendoroid", "Nico Robin", "Nendoroid Wano Ver.", "mid", 50),
        ("Nendoroid", "Kaido", "Nendoroid Beast Form", "mid", 60),

        # ── GEM Series — Additional ──────────────────────────────────────────
        ("GEM Series", "Kozuki Oden", "Two Sword Style", "high", 140),
        ("GEM Series", "Dracule Mihawk", "Night Black Blade", "high", 135),
        ("GEM Series", "Jinbe", "Fish-Man Karate", "high", 110),
        ("GEM Series", "Chopper", "Monster Point", "high", 100),

        # ── Tsume HQS / HQS+ — Additional ───────────────────────────────────
        ("Tsume HQS", "Nico Robin", "Mil Fleur Gigantesco Mano", "grail", 550),
        ("Tsume HQS", "Sabo", "Fire Fist Inheritance", "grail", 500),
        ("Tsume HQS", "Dracule Mihawk", "World's Strongest Slash", "grail", 600),
        ("Tsume HQS+", "Monkey D. Luffy", "Gear 5 Nika Joy Boy", "grail", 900),
        ("Tsume HQS+", "Roronoa Zoro", "King of Hell Ashura", "grail", 850),

        # ── Ship Models — Complete Grand Ship Collection ─────────────────────
        ("Ship Model", "Victoria Punk", "Grand Ship Collection", "standard", 25),
        ("Ship Model", "Nostra Castello", "Grand Ship Collection", "standard", 25),
        ("Ship Model", "Baratie", "Grand Ship Collection", "standard", 28),
        ("Ship Model", "Marshall D. Teach's Raft", "Grand Ship Collection", "standard", 22),
        ("Ship Model", "Thriller Bark", "Grand Ship Collection", "standard", 30),
        ("Ship Model", "Thousand Sunny", "Bandai MG 1/100 Model Kit", "high", 120),

        # ── WCF — Additional Sets ────────────────────────────────────────────
        ("WCF", "Alabasta", "Complete Set (6 pcs)", "mid", 50),
        ("WCF", "Skypiea", "Complete Set (6 pcs)", "mid", 48),
        ("WCF", "Water Seven", "Complete Set (8 pcs)", "mid", 60),
        ("WCF", "Thriller Bark", "Complete Set (6 pcs)", "mid", 48),
        ("WCF", "Punk Hazard", "Complete Set (6 pcs)", "mid", 45),
        ("WCF", "Egg Head", "Vol. 2 Complete Set (6 pcs)", "mid", 52),

        # ── Manga — First Prints & Specials ──────────────────────────────────
        ("Manga", "One Piece Vol. 25", "First Print (Japanese)", "mid", 50),
        ("Manga", "One Piece Vol. 41", "First Print (Japanese, Enies Lobby)", "mid", 55),
        ("Manga", "One Piece Vol. 59", "First Print (Japanese, Marineford)", "mid", 60),
        ("Manga", "One Piece Color Walk Compendium 1", "Art Book", "high", 100),
        ("Manga", "One Piece Color Walk Compendium 2", "Art Book", "high", 100),
        ("Manga", "One Piece Vivre Card Databook Complete Set", "Collector's Edition", "high", 120),
        ("Manga", "One Piece Magazine Vol. 1-15 Complete", "Complete Set", "high", 150),

        # ── Film Red — Additional Merchandise ────────────────────────────────
        ("Film Red", "Uta", "World Collectable Figure Film Red", "standard", 22),
        ("Film Red", "Shanks", "World Collectable Figure Film Red", "standard", 25),
        ("Film Red", "Luffy", "King of Artist Film Red Ver.", "mid", 45),
        ("Film Red", "Uta", "King of Artist Film Red", "mid", 42),
        ("Film Red", "Shanks", "King of Artist Film Red", "mid", 48),

        # ── One Piece x Collaboration Figures ────────────────────────────────
        ("Collab Merch", "Luffy x Goku", "50th Jump Anniversary Figure", "high", 130),
        ("Collab Merch", "Luffy x Naruto x Goku", "Jump Force Triple Figure Set", "high", 150),
        ("Collab Merch", "One Piece x adidas", "Ultra Boost Straw Hat Edition", "high", 180),

        # ── VAH — Additional ─────────────────────────────────────────────────
        ("VAH", "Kaido", "Dragon Form", "high", 130),
        ("VAH", "Chopper", "Monster Point", "mid", 80),
        ("VAH", "Franky", "General Franky", "high", 105),
        ("VAH", "Law", "Room Operation", "mid", 95),

        # ── MegaHouse / Look Up Series ───────────────────────────────────────
        ("MegaHouse", "Roronoa Zoro", "Look Up Series Wano", "standard", 25),
        ("MegaHouse", "Nami", "Look Up Series Wano", "standard", 22),
        ("MegaHouse", "Sanji", "Look Up Series Wano", "standard", 22),
        ("MegaHouse", "Chopper", "Look Up Series Cotton Candy", "standard", 20),
        ("MegaHouse", "Shanks", "Look Up Series Film Red", "standard", 25),
        ("MegaHouse", "Uta", "Look Up Series Film Red", "standard", 22),

        # ── P.O.P. MAS — Additional ─────────────────────────────────────────
        ("P.O.P. MAS", "Nami", "Ver. BB 3D2Y", "high", 160),
        ("P.O.P. MAS", "Nico Robin", "Miss All Sunday", "high", 155),
        ("P.O.P. MAS", "Boa Hancock", "Wedding Ver.", "high", 170),
        ("P.O.P. MAS", "Carrot", "Sulong Form", "high", 140),
        ("P.O.P. MAS", "Yamato", "Wano Country", "high", 165),

        # ── P.O.P. DX — Additional ──────────────────────────────────────────
        ("P.O.P. DX", "Roronoa Zoro", "Shishi Sonson", "high", 170),
        ("P.O.P. DX", "Sanji", "Black Leg Diable Jambe", "high", 155),
        ("P.O.P. DX", "Rob Lucci", "CP9 Leopard Form", "high", 150),
        ("P.O.P. DX", "Kizaru", "Borsalino", "high", 160),
        ("P.O.P. DX", "Akainu", "Sakazuki", "high", 165),
        ("P.O.P. DX", "Aokiji", "Kuzan", "high", 155),

        # ── Banpresto Glitter & Glamours — Additional ───────────────────────
        ("Banpresto", "Nico Robin", "Glitter & Glamours Ver. A", "standard", 28),
        ("Banpresto", "Yamato", "Glitter & Glamours Wano", "standard", 30),
        ("Banpresto", "Uta", "Glitter & Glamours Film Red", "standard", 26),
        ("Banpresto", "Nami", "Glitter & Glamours Wano Ver. B", "standard", 25),
        ("Banpresto", "Vivi", "Glitter & Glamours Alabasta", "standard", 24),
        ("Banpresto", "Shirahoshi", "Glitter & Glamours Mermaid", "standard", 28),

        # ── One Piece Card Game — Starter Decks Additional ──────────────────
        ("OP Card Game", "Animal Kingdom Pirates", "ST-04 Starter Deck Sealed", "standard", 20),
        ("OP Card Game", "Film Edition", "ST-05 Starter Deck Sealed", "standard", 18),
        ("OP Card Game", "Navy", "ST-06 Starter Deck Sealed", "standard", 18),
        ("OP Card Game", "Monkey D. Luffy", "ST-08 Starter Deck Sealed", "standard", 22),
        ("OP Card Game", "Yamato", "ST-09 Starter Deck Sealed", "standard", 20),
        ("OP Card Game", "Ultimate Deck", "ST-10 Starter Deck Sealed", "standard", 25),
        ("OP Card Game", "Uta", "ST-11 Starter Deck Film Red", "standard", 18),
        ("OP Card Game", "Zoro & Sanji", "ST-12 Starter Deck Sealed", "standard", 20),
        ("OP Card Game", "Three Brothers", "Ultra Deck Sealed", "standard", 28),

        # ── Figuarts ZERO — Devil Fruit / Haki Series ───────────────────────
        ("Figuarts ZERO", "Luffy", "Gear 5 Extra Battle Nika Gigant", "high", 120),
        ("Figuarts ZERO", "Shanks", "Haki Clash Extra Battle", "high", 110),
        ("Figuarts ZERO", "Luffy vs Kaido", "Extra Battle Thunder Bagua", "high", 140),
        ("Figuarts ZERO", "Doflamingo", "Extra Battle Bird Cage", "mid", 80),

        # ── Magazine Figure — Additional ─────────────────────────────────────
        ("Magazine Figure", "Roronoa Zoro", "Special Episode Vol. 2", "mid", 48),
        ("Magazine Figure", "Sanji", "Special Episode Vol. 3", "mid", 45),
        ("Magazine Figure", "Trafalgar Law", "Special Episode Vol. 3", "mid", 48),
        ("Magazine Figure", "Boa Hancock", "Special Episode Vol. 2 Dress", "mid", 50),
        ("Magazine Figure", "Yamato", "Special Episode Vol. 4", "mid", 50),

        # ── Live-Action Season 2 — Additional ───────────────────────────────
        ("Live-Action", "Tony Tony Chopper", "Netflix Figure (Season 2)", "mid", 50),
        ("Live-Action", "Monkey D. Luffy", "Netflix Season 2 Alabasta Figure", "mid", 55),
        ("Live-Action", "Nico Robin", "Netflix Season 2 Miss All Sunday", "mid", 50),
        ("Live-Action", "Crocodile", "Netflix Season 2 Figure", "mid", 55),
        ("Live-Action", "Vivi", "Netflix Season 2 Alabasta Princess", "mid", 45),

        # ── One Piece Stamps / Stationery ────────────────────────────────────
        ("Collab Merch", "Straw Hat Crew", "Japan Post One Piece Stamp Set 2024", "standard", 25),
        ("Collab Merch", "Luffy", "One Piece Premium Stationery Set", "standard", 18),
        ("Collab Merch", "One Piece", "Ichiban Kuji Towel Set (Prize F)", "standard", 15),

        # ── Gashapon / Capsule Toys — Additional ─────────────────────────────
        ("Gashapon", "Straw Hat Crew", "Chara Fortune Complete Set (10 pcs)", "mid", 60),
        ("Gashapon", "Wano Country", "Desktop Series Complete Set (6 pcs)", "mid", 45),
        ("Gashapon", "Gear 5 Luffy", "Capsule Figure Swing Collection", "standard", 15),
    ]

    # ── Expansion Batch 6 — 50 more One Piece collectibles ──
    items += _expanded_batch_6()

    # ── Expansion Batch 7 — 55 more One Piece collectibles ──
    items += _expanded_batch_7()

    # ── Expansion Batch 8 — 95 more One Piece collectibles (to 700+) ──
    items += _expanded_batch_8()

    # ── Expansion Batch 9 — 200 more One Piece collectibles (to 900+) ──
    items += _expanded_batch_9()

    catalog = []
    for line, name, variant, tier, price in items:
        catalog.append({
            "line": line,
            "name": name,
            "variant": variant,
            "rarity_tier": tier,
            "price_eur": price,
        })
    # Deduplicate by ('line', 'name', 'variant') (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = (item["line"], item["name"], item["variant"])
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


def _expanded_batch_6() -> list[tuple]:
    """50 additional One Piece collectibles — P.O.P., Figuarts, Card Game ultra rares, Ichiban Kuji, DXF, Banpresto WCF."""
    return [
        # ── P.O.P. (Portrait of Pirates) — Premium Figures ──
        ("P.O.P.", "Monkey D. Luffy", "Gear 5 Nika SA-MAXIMUM", "grail", 320),
        ("P.O.P.", "Yamato", "Warriors Alliance Limited Edition", "grail", 280),
        ("P.O.P.", "Kaido", "Dragon Form SA-MAXIMUM", "grail", 350),
        ("P.O.P.", "Red-Haired Shanks", "Playback Memories", "grail", 260),
        ("P.O.P.", "Roronoa Zoro", "SA-MAXIMUM Wano Country Enma", "high", 180),
        ("P.O.P.", "Boa Hancock", "Limited Edition ver.BB_02", "high", 200),
        ("P.O.P.", "Trafalgar Law", "SA-MAXIMUM Room Shambles", "high", 190),
        ("P.O.P.", "Nami", "Playback Memories Arlong Park", "high", 170),
        ("P.O.P.", "Portgas D. Ace", "NEO-DX 10th Limited Ver.", "grail", 400),
        ("P.O.P.", "Carrot", "Sulong Form Limited Edition", "high", 160),
        ("P.O.P.", "Sanji", "SA-MAXIMUM Ifrit Jambe", "high", 175),
        ("P.O.P.", "Nico Robin", "Playback Memories Miss All Sunday", "high", 165),

        # ── Figuarts ZERO — Extra Battle / Statue Line ──
        ("Figuarts ZERO", "Luffy", "Gear 5 Extra Battle Drum of Liberation", "high", 130),
        ("Figuarts ZERO", "Kaido", "Extra Battle King of the Beasts Dragon Form", "high", 145),
        ("Figuarts ZERO", "Roronoa Zoro", "Extra Battle King of Hell Three-Sword Style", "high", 125),
        ("Figuarts ZERO", "Yamato", "Extra Battle Okuchi-no-Makami", "high", 135),
        ("Figuarts ZERO", "Sanji", "Extra Battle Diable Jambe Premier Hache", "high", 120),
        ("Figuarts ZERO", "Trafalgar Law", "Extra Battle Gamma Knife", "high", 115),
        ("Figuarts ZERO", "Big Mom", "Extra Battle Charlotte Linlin", "high", 140),

        # ── One Piece Card Game — Ultra Rares / Manga Art ──
        ("OP Card Game", "Monkey D. Luffy", "OP05-119 Manga Rare Gear 5", "grail", 280),
        ("OP Card Game", "Portgas D. Ace", "OP02-013 Alternate Art Leader", "grail", 220),
        ("OP Card Game", "Roronoa Zoro", "OP01-025 Comic Art Secret Rare", "grail", 250),
        ("OP Card Game", "Yamato", "OP04-112 Manga Rare", "high", 150),
        ("OP Card Game", "Boa Hancock", "OP03-114 Secret Rare Alternate Art", "high", 180),
        ("OP Card Game", "Shanks", "OP01-120 Secret Rare Film Red", "grail", 300),
        ("OP Card Game", "Nami", "OP01-016 Alternate Art SP", "high", 140),
        ("OP Card Game", "Uta", "OP02-120 Secret Rare Film Red", "high", 120),
        ("OP Card Game", "Enel", "OP05-098 Secret Rare Thunder God", "high", 110),
        ("OP Card Game", "Trafalgar Law", "OP04-099 Comic Art Secret Rare", "high", 160),

        # ── Ichiban Kuji — Last One / A Prize Figures ──
        ("Ichiban Kuji", "Luffy", "Film Red A Prize Gear 5", "high", 95),
        ("Ichiban Kuji", "Shanks", "Film Red Last One Prize", "grail", 200),
        ("Ichiban Kuji", "Uta", "Film Red B Prize Full Figure", "high", 80),
        ("Ichiban Kuji", "Kaido", "Wano Country Last One Prize Dragon", "grail", 180),
        ("Ichiban Kuji", "Yamato", "Wano Country A Prize Thunder Bagua", "high", 90),
        ("Ichiban Kuji", "Roronoa Zoro", "EX Devils Vol. 2 Last One Ashura", "grail", 170),
        ("Ichiban Kuji", "Luffy", "Legends Over Time A Prize Joy Boy", "high", 85),
        ("Ichiban Kuji", "Ace", "Memorial Vow Last One Prize", "grail", 190),

        # ── DXF / Grandline Men Series ──
        ("DXF", "Monkey D. Luffy", "The Grandline Men Wano Country Vol. 1", "mid", 35),
        ("DXF", "Roronoa Zoro", "The Grandline Men Wano Country Vol. 2", "mid", 35),
        ("DXF", "Sanji", "The Grandline Men Wano Country Vol. 3", "mid", 32),
        ("DXF", "Yamato", "The Grandline Lady Wano Country Vol. 6", "mid", 38),
        ("DXF", "Nico Robin", "The Grandline Lady Wano Country Vol. 5", "mid", 35),

        # ── Banpresto World Colosseum Figures ──
        ("BWFC", "Monkey D. Luffy", "World Colosseum 2 Champion Gear 4", "high", 95),
        ("BWFC", "Roronoa Zoro", "World Colosseum 2 Vol. 1 Santoryu", "high", 85),
        ("BWFC", "Portgas D. Ace", "World Colosseum Vol. 6 Fire Fist", "high", 90),
        ("BWFC", "Trafalgar Law", "World Colosseum 2 Vol. 6 Room", "high", 80),
        ("BWFC", "Sanji", "World Colosseum Vol. 2 Diable Jambe", "high", 75),
        ("BWFC", "Boa Hancock", "World Colosseum 2 Vol. 5 Love Hurricane", "high", 88),
    ]


def _expanded_batch_7() -> list[tuple]:
    """55 additional One Piece collectibles — Film Red, Egghead Arc, Wano Arc,
    Card Game accessories/playmats, Stampede/Strong World movie items, East Blue Saga."""
    return [
        # ── Film Red Merchandise (+10) ──────────────────────────────────────
        ("Film Red", "Uta", "Figuarts ZERO Concert Dress Ver.", "high", 110),
        ("Film Red", "Shanks", "S.H.Figuarts Film Red Final Battle", "high", 140),
        ("Film Red", "Gordon", "DXF Film Red", "standard", 22),
        ("Film Red", "Luffy", "Glitter & Glamours Film Red Gear 5", "mid", 45),
        ("Film Red", "Uta", "Nendoroid Film Red Concert Ver.", "mid", 55),
        ("Film Red", "Shanks & Uta", "Ichiban Kuji Prize A Music Duo", "high", 130),
        ("Film Red", "Tot Musica", "Figuarts ZERO Extra Battle Tot Musica", "high", 150),
        ("Film Red", "Uta", "P.O.P. Limited Film Red Diva Ver.", "grail", 220),
        ("Film Red", "Koby", "DXF Film Red Marine Ver.", "standard", 25),
        ("Film Red", "Straw Hat Crew", "Film Red Premium Figure Set (5 pcs)", "high", 120),

        # ── Egghead Arc Figures (+10) ──────────────────────────────────────
        ("Egghead Arc", "Vegapunk (Stella)", "DXF The Grandline Men Egghead", "mid", 35),
        ("Egghead Arc", "Vegapunk (Lilith)", "DXF The Grandline Lady Egghead", "mid", 38),
        ("Egghead Arc", "Vegapunk (Shaka)", "Figuarts ZERO Extra Battle", "mid", 80),
        ("Egghead Arc", "Kizaru", "S.H.Figuarts Egghead Yata no Kagami", "high", 140),
        ("Egghead Arc", "Saturn", "Figuarts ZERO Extra Battle Gorosei", "high", 120),
        ("Egghead Arc", "Jewelry Bonney", "DXF The Grandline Lady Egghead Nika", "mid", 40),
        ("Egghead Arc", "Luffy", "Figuarts ZERO Gear 5 Egghead Battle", "high", 130),
        ("Egghead Arc", "Dorry & Brogy", "Ichiban Kuji Prize A Giant Warriors", "high", 110),
        ("Egghead Arc", "Lucci", "S.H.Figuarts Egghead Awakened Leopard", "high", 135),
        ("Egghead Arc", "Stussy", "DXF The Grandline Lady Egghead", "mid", 38),

        # ── Wano Arc Collectibles (+10) ────────────────────────────────────
        ("Wano Arc", "Luffy", "Figuarts ZERO Snakeman Extra Battle Wano", "high", 115),
        ("Wano Arc", "Zoro", "GEM Series Enma Black Blade Wano", "high", 140),
        ("Wano Arc", "Kin'emon", "DXF The Grandline Men Wano Samurai", "standard", 28),
        ("Wano Arc", "Momonosuke", "DXF Dragon Form Wano Finale", "mid", 45),
        ("Wano Arc", "Kaido vs Luffy", "Figuarts ZERO Extra Battle Rooftop Clash", "grail", 200),
        ("Wano Arc", "Queen", "DXF The Grandline Men Beast Pirates", "standard", 30),
        ("Wano Arc", "King", "Figuarts ZERO Extra Battle Lunarian Fire", "high", 110),
        ("Wano Arc", "Sanji", "GEM Series Germa Raid Suit Wano", "high", 130),
        ("Wano Arc", "Kozuki Hiyori", "Glitter & Glamours Wano", "standard", 28),
        ("Wano Arc", "Tama", "DXF The Grandline Children Wano", "standard", 20),

        # ── One Piece Card Game Accessories/Playmats (+8) ──────────────────
        ("OP Card Game", "Playmat", "Official Egghead Arc Tournament Playmat", "mid", 75),
        ("OP Card Game", "Playmat", "Official Wano Finale Zoro vs King Playmat", "mid", 70),
        ("OP Card Game", "Playmat", "Official 1st Anniversary Luffy Playmat", "high", 100),
        ("OP Card Game", "Deck Box", "Official Yamato Premium Deck Box", "standard", 25),
        ("OP Card Game", "Deck Box", "Official Portgas D. Ace Premium Deck Box", "standard", 25),
        ("OP Card Game", "Sleeves", "Official Egghead Vegapunk Sleeves 70ct", "standard", 18),
        ("OP Card Game", "Sleeves", "Official Wano Zoro Enma Sleeves 70ct", "standard", 18),
        ("OP Card Game", "Playmat", "Regional Championship Shanks Prize Playmat", "high", 130),

        # ── Stampede / Strong World Movie Items (+7) ───────────────────────
        ("Stampede", "Monkey D. Luffy", "DXF Stampede Festival Outfit", "mid", 40),
        ("Stampede", "Roger", "Ichiban Kuji Stampede Prize A Pirate King", "high", 120),
        ("Stampede", "Straw Hat Crew", "Stampede DXF Complete Set (9 pcs)", "high", 150),
        ("Strong World", "Monkey D. Luffy", "DXF Strong World Black Suit", "mid", 50),
        ("Strong World", "Nami", "DXF Strong World Cowgirl Ver.", "mid", 45),
        ("Strong World", "Shiki", "DXF Strong World Golden Lion", "mid", 55),
        ("Strong World", "Straw Hat Crew", "Strong World Styling Complete Set (9 pcs)", "high", 140),

        # ── Classic East Blue Saga Items (+10) ─────────────────────────────
        ("East Blue Saga", "Monkey D. Luffy", "P.O.P. Sailing Again Romance Dawn", "high", 160),
        ("East Blue Saga", "Roronoa Zoro", "P.O.P. Sailing Again Pirate Hunter", "high", 155),
        ("East Blue Saga", "Nami", "P.O.P. Playback Memories Arlong Park Tears", "high", 145),
        ("East Blue Saga", "Sanji", "P.O.P. Sailing Again Baratie Chef", "high", 150),
        ("East Blue Saga", "Usopp", "P.O.P. Sailing Again Syrup Village", "high", 130),
        ("East Blue Saga", "Arlong", "Figuarts ZERO Shark on Darts", "mid", 75),
        ("East Blue Saga", "Buggy", "Figuarts ZERO Chop Chop Festival", "mid", 65),
        ("East Blue Saga", "Captain Kuro", "DXF East Blue Pirate Captains", "standard", 30),
        ("East Blue Saga", "Don Krieg", "DXF East Blue Pirate Captains", "standard", 28),
        ("East Blue Saga", "Mihawk vs Zoro", "Ichiban Kuji Prize A Baratie Encounter", "high", 140),
    ]


def _expanded_batch_8() -> list[tuple]:
    """95 additional One Piece collectibles — P.O.P. deep cuts, Ichiban Kuji, WCF sets,
    Film Red, Gear 5, Log Collection, Grandista, Card Game accessories."""
    return [
        # ── Portrait of Pirates — Deep Cuts & Reissues (+15) ────────────
        ("P.O.P.", "Tony Tony Chopper", "SA-MAXIMUM Monster Point Ver.", "grail", 280),
        ("P.O.P.", "Brook", "Sailing Again Soul King Ver.", "high", 145),
        ("P.O.P.", "Franky", "SA-MAXIMUM General Franky", "grail", 310),
        ("P.O.P.", "Donquixote Doflamingo", "SA-MAXIMUM Heavenly Demon", "grail", 290),
        ("P.O.P.", "Katakuri", "SA-MAXIMUM Mochi Mochi no Mi", "grail", 300),
        ("P.O.P.", "Kuzan (Aokiji)", "NEO-DX Ice Age Ver.", "grail", 260),
        ("P.O.P.", "Sabo", "SA-MAXIMUM Fire Dragon Claw", "high", 195),
        ("P.O.P.", "Perona", "Sailing Again Gothic Ver.", "high", 180),
        ("P.O.P.", "Koala", "Playback Memories Revolutionary Army", "high", 140),
        ("P.O.P.", "Vivi", "Playback Memories Arabasta Princess Ver.", "high", 155),
        ("P.O.P.", "Marco", "Playback Memories Phoenix Ver.", "high", 175),
        ("P.O.P.", "Jinbe", "SA-MAXIMUM Fish-Man Karate", "high", 170),
        ("P.O.P.", "Crocodile", "NEO-DX Revival Ver.", "high", 185),
        ("P.O.P.", "Smoker", "NEO-DX Marine Captain Ver.", "high", 150),
        ("P.O.P.", "Mihawk", "SA-MAXIMUM Black Blade Yoru", "grail", 320),

        # ── Ichiban Kuji — Last One / Prize A (+12) ────────────────────
        ("Ichiban Kuji", "Gear 5 Luffy", "Legends Over Time Last One Prize Joy Boy", "grail", 220),
        ("Ichiban Kuji", "Nika Luffy", "EX One Piece Anime 25th Last One", "grail", 250),
        ("Ichiban Kuji", "Sabo", "Revolutionary Sabo A Prize Flame Emperor", "high", 100),
        ("Ichiban Kuji", "Marco", "Marineford A Prize Phoenix Dive", "high", 95),
        ("Ichiban Kuji", "Law", "Room A Prize Wano Ver.", "high", 85),
        ("Ichiban Kuji", "Nami", "One Piece Girls Collection Last One Zeus", "high", 130),
        ("Ichiban Kuji", "Robin", "One Piece Girls Collection A Prize Demon Child", "high", 95),
        ("Ichiban Kuji", "Whitebeard", "Legends Over Time B Prize Quake Man", "high", 110),
        ("Ichiban Kuji", "Blackbeard", "EX Devils Vol. 1 A Prize Yami Yami", "high", 105),
        ("Ichiban Kuji", "Luffy vs Kaido", "EX Wano Decisive Battle Last One Clash", "grail", 240),
        ("Ichiban Kuji", "Kid & Law", "Wano Alliance A Prize Triple Captain", "high", 90),
        ("Ichiban Kuji", "Hancock", "One Piece Girls Collection B Prize Snake Princess", "high", 88),

        # ── World Collectible Figure Sets (+10) ────────────────────────
        ("WCF", "Wano Country Arc", "WCF Vol. 1 Complete Set (6 figs)", "mid", 50),
        ("WCF", "Wano Country Arc", "WCF Vol. 2 Complete Set (6 figs)", "mid", 50),
        ("WCF", "Wano Country Arc", "WCF Vol. 3 Complete Set (6 figs)", "mid", 48),
        ("WCF", "Egghead Arc", "WCF Vol. 1 Vegapunk Set (6 figs)", "mid", 55),
        ("WCF", "Film Red", "WCF Film Red Complete Set (6 figs)", "mid", 55),
        ("WCF", "Straw Hat Crew", "WCF Chibi Straw Hat Crew 20th Anniv (10 figs)", "high", 120),
        ("WCF", "Marine Ford", "WCF Vol. 35 Marineford Complete Set (8 figs)", "high", 100),
        ("WCF", "Dressrosa", "WCF Dressrosa Complete Set (6 figs)", "mid", 45),
        ("WCF", "Fishman Island", "WCF Vol. 25 Fisher Tiger & Sun Pirates (6 figs)", "mid", 55),
        ("WCF", "Thriller Bark", "WCF Vol. 20 Complete Set (6 figs)", "mid", 48),

        # ── Gear 5 / Nika Items (+8) ──────────────────────────────────
        ("Gear 5", "Monkey D. Luffy", "S.H.Figuarts Gear 5 Nika White", "high", 140),
        ("Gear 5", "Monkey D. Luffy", "King of Artist Gear 5 Sun God", "mid", 55),
        ("Gear 5", "Monkey D. Luffy", "DXF Gear 5 Lightning God Pose", "mid", 40),
        ("Gear 5", "Monkey D. Luffy", "Grandista Gear 5 Joy Boy 30cm", "high", 95),
        ("Gear 5", "Monkey D. Luffy", "GEM Series Gear 5 Drums of Liberation", "high", 160),
        ("Gear 5", "Monkey D. Luffy", "Banpresto Chronicle Master Stars Gear 5", "mid", 65),
        ("Gear 5", "Monkey D. Luffy", "Figuarts ZERO Extra Battle Nika Rooftop", "high", 145),
        ("Gear 5", "Monkey D. Luffy", "Nendoroid Gear 5 Joyful Ver.", "mid", 55),

        # ── Log Collection / Grandista (+10) ──────────────────────────
        ("Log Collection", "Monkey D. Luffy", "Log Collection Large Figure Rubber Pistol", "high", 95),
        ("Log Collection", "Roronoa Zoro", "Log Collection Large Figure Onigiri", "high", 90),
        ("Log Collection", "Sanji", "Log Collection Large Figure Diable Jambe", "high", 85),
        ("Log Collection", "Portgas D. Ace", "Log Collection Large Figure Fire Fist", "high", 100),
        ("Log Collection", "Shanks", "Log Collection Large Figure Gryphon Slash", "high", 105),
        ("Grandista", "Monkey D. Luffy", "Grandista Manga Dimensions Luffy", "mid", 60),
        ("Grandista", "Roronoa Zoro", "Grandista Manga Dimensions Zoro", "mid", 55),
        ("Grandista", "Portgas D. Ace", "Grandista Manga Dimensions Ace", "mid", 55),
        ("Grandista", "Trafalgar Law", "Grandista Manga Dimensions Law", "mid", 50),
        ("Grandista", "Boa Hancock", "Grandista Manga Dimensions Hancock", "mid", 58),

        # ── One Piece Card Game — OP06/OP07 Ultra Rares (+10) ──────────
        ("OP Card Game", "Monkey D. Luffy", "OP07-109 Manga Rare Gear 5 Nika Full Art", "grail", 320),
        ("OP Card Game", "Shanks", "OP06-118 Secret Rare Full Art Emperor", "grail", 280),
        ("OP Card Game", "Nico Robin", "OP06-086 Alternate Art SP Miss All Sunday", "high", 160),
        ("OP Card Game", "Nefertari Vivi", "OP07-051 Manga Rare Arabasta Princess", "high", 140),
        ("OP Card Game", "Sabo", "OP05-081 Secret Rare Dragon Claw", "high", 130),
        ("OP Card Game", "Kaido", "OP03-099 Secret Rare Dragon Form", "high", 170),
        ("OP Card Game", "Charlotte Katakuri", "OP06-070 Secret Rare Mochi Buzzcut", "high", 120),
        ("OP Card Game", "Jewelry Bonney", "OP07-019 Alternate Art Egghead Nika", "high", 110),
        ("OP Card Game", "Sanji", "OP07-064 Secret Rare Ifrit Jambe Full Art", "high", 140),
        ("OP Card Game", "Crocodile", "OP04-058 Alternate Art Cross Guild", "high", 100),

        # ── Tsume HQS / Premium Statues (+8) ──────────────────────────
        ("Tsume HQS", "Monkey D. Luffy", "HQS Gear 4 Snakeman vs Katakuri", "grail", 800),
        ("Tsume HQS", "Roronoa Zoro", "HQS Ashura Ichibugin", "grail", 700),
        ("Tsume HQS", "Portgas D. Ace", "HQS Fire Fist Last Stand", "grail", 750),
        ("Tsume HQS", "Trafalgar Law", "HQS Gamma Knife Dressrosa", "grail", 650),
        ("Tsume HQS+", "Kaido vs Luffy", "HQS+ Wano Rooftop Ultimate Clash", "grail", 1200),
        ("Tsume HQS", "Whitebeard", "HQS Edward Newgate Paramount War", "grail", 900),
        ("Tsume HQS", "Shanks", "HQS Red Hair Conqueror's Haki", "grail", 850),
        ("Tsume HQS", "Sanji", "HQS Diable Jambe Anti-Manner Kick", "grail", 680),

        # ── Nendoroid / S.H.Figuarts (+8) ─────────────────────────────
        ("Nendoroid", "Monkey D. Luffy", "Nendoroid Film Red Concert Ver.", "mid", 50),
        ("Nendoroid", "Roronoa Zoro", "Nendoroid Wano Country Enma Ver.", "mid", 55),
        ("Nendoroid", "Nami", "Nendoroid Wano Kunoichi Ver.", "mid", 50),
        ("Nendoroid", "Chopper", "Nendoroid Cotton Candy Lover Ver.", "mid", 45),
        ("S.H.Figuarts", "Monkey D. Luffy", "S.H.Figuarts Dressrosa Gear 4 Bounce Man", "high", 110),
        ("S.H.Figuarts", "Roronoa Zoro", "S.H.Figuarts Wano Country Three-Sword Style", "high", 120),
        ("S.H.Figuarts", "Sanji", "S.H.Figuarts Whole Cake Island Raid Suit", "high", 100),
        ("S.H.Figuarts", "Rob Lucci", "S.H.Figuarts Egghead Awakened Leopard Form", "high", 130),

        # ── Collab / GEM / VAH (+8) ───────────────────────────────────
        ("GEM Series", "Boa Hancock", "GEM Series Palm Sized Boa Hancock", "mid", 65),
        ("GEM Series", "Nami", "GEM Series Run! Run! Run! Nami", "mid", 70),
        ("GEM Series", "Roronoa Zoro", "GEM Series Wano Samurai Zoro", "high", 135),
        ("VAH", "Boa Hancock", "Variable Action Heroes Boa Hancock Blue Ver.", "high", 120),
        ("VAH", "Trafalgar Law", "Variable Action Heroes Law Room", "high", 110),
        ("VAH", "Portgas D. Ace", "Variable Action Heroes Ace Flame Commandant", "high", 115),
        ("Collab Merch", "Luffy", "BAIT x One Piece Gear 5 T-Shirt (LE 500)", "mid", 80),
        ("Collab Merch", "Straw Hat Crew", "Uniqlo UT x One Piece 25th Anniversary Full Set (8 tees)", "mid", 70),

        # ── Ship Models / Dioramas (+6) ───────────────────────────────
        ("Ship Model", "Going Merry", "Grand Ship Collection Going Merry Memorial Color", "mid", 45),
        ("Ship Model", "Thousand Sunny", "Grand Ship Collection Thousand Sunny Film Red", "mid", 48),
        ("Ship Model", "Oro Jackson", "Grand Ship Collection Oro Jackson Roger's Ship", "mid", 40),
        ("Ship Model", "Red Force", "Grand Ship Collection Red Force Shanks", "mid", 42),
        ("Ship Model", "Polar Tang", "Grand Ship Collection Polar Tang Law's Sub", "mid", 38),
        ("Ship Model", "Moby Dick", "Grand Ship Collection Moby Dick Whitebeard", "mid", 40),
    ]


def _expanded_batch_9() -> list[tuple]:
    """200 additional One Piece collectibles — P.O.P. Megahouse deep cuts, FiguartsZERO,
    Ichiban Kuji, manga volumes, One Piece TCG, merch, vinyl/music, collabs, anniversary."""
    return [
        # ── P.O.P. Megahouse — Additional Lines (~30) ────────────────────
        ("P.O.P. Maximum", "Monkey D. Luffy", "Gear 5 Joy Boy Awakening", "grail", 350),
        ("P.O.P. Maximum", "Shanks", "Film Red Full Power", "grail", 300),
        ("P.O.P. Maximum", "Roronoa Zoro", "Enma & Wado Ichimonji Dual Wield", "grail", 280),
        ("P.O.P. Maximum", "Sanji", "Ifrit Jambe Blue Flames", "high", 200),
        ("P.O.P. Maximum", "Trafalgar Law", "K-Room Puncture Wille", "high", 195),
        ("P.O.P. Maximum", "Eustass Kid", "Punk Assign Awakened", "high", 190),
        ("P.O.P. Maximum", "Marco", "Phoenix Full Transformation", "grail", 260),
        ("P.O.P. Maximum", "Yamato", "Okuchi no Makami Divine Wolf", "grail", 280),
        ("P.O.P.", "Charlotte Katakuri", "NEO-MAXIMUM Mochi Buzzcut", "grail", 310),
        ("P.O.P.", "Donquixote Doflamingo", "NEO-MAXIMUM Birdcage Awakening", "grail", 290),
        ("P.O.P.", "Sabo", "NEO-MAXIMUM Flame Emperor Dragon Claw", "high", 195),
        ("P.O.P. Playback Memories", "Nami", "Weatheria Sky Island Study", "high", 150),
        ("P.O.P. Playback Memories", "Nico Robin", "Ohara Buster Call Survivor", "high", 165),
        ("P.O.P. Playback Memories", "Chopper", "Drum Island Doctor Training", "high", 130),
        ("P.O.P. Limited", "Boa Hancock", "Amazon Lily Empress Ver.", "high", 185),
        ("P.O.P. Limited", "Nami", "Zou Mink Tribe Outfit", "high", 170),
        ("P.O.P. Limited", "Robin", "Wano Country Oiran Ver.", "high", 175),
        ("P.O.P. Warriors Alliance", "Kid", "Wano Country Punk Rotten", "high", 145),
        ("P.O.P. Warriors Alliance", "Killer", "Wano Country Kamazo", "high", 135),
        ("P.O.P. Warriors Alliance", "Jinbe", "Wano Country Knight of the Sea", "high", 140),
        ("P.O.P. SOC", "Monkey D. Luffy", "20th Anniversary Straw Hat Captain", "grail", 250),
        ("P.O.P. SOC", "Roronoa Zoro", "20th Anniversary First Mate", "grail", 240),
        ("P.O.P. SOC", "Nami", "20th Anniversary Navigator", "high", 200),
        ("P.O.P. SOC", "Sanji", "20th Anniversary Chef", "high", 195),
        ("P.O.P. SOC", "Chopper", "20th Anniversary Doctor", "high", 160),
        ("P.O.P. SOC", "Robin", "20th Anniversary Archaeologist", "high", 190),
        ("P.O.P. SOC", "Franky", "20th Anniversary Shipwright", "high", 180),
        ("P.O.P. SOC", "Brook", "20th Anniversary Musician", "high", 170),
        ("P.O.P. SOC", "Usopp", "20th Anniversary Sniper", "high", 165),
        ("P.O.P. SOC", "Jinbe", "20th Anniversary Helmsman", "high", 175),

        # ── Figuarts ZERO — Extra Battle & Effects (~20) ──────────────────
        ("Figuarts ZERO", "Monkey D. Luffy", "Extra Battle Gear 5 Drums of Liberation Full", "high", 140),
        ("Figuarts ZERO", "Sanji", "Extra Battle Ifrit Jambe Hell Memories", "high", 125),
        ("Figuarts ZERO", "Trafalgar Law", "Extra Battle ROOM Shambles Amputate", "high", 120),
        ("Figuarts ZERO", "Big Mom", "Extra Battle Charlotte Linlin Prometheus Zeus Napoleon", "high", 155),
        ("Figuarts ZERO", "Whitebeard", "Extra Battle Edward Newgate Quake Shockwave", "high", 150),
        ("Figuarts ZERO", "Gol D. Roger", "Extra Battle Pirate King Roger Kamusari", "high", 145),
        ("Figuarts ZERO", "Silvers Rayleigh", "Extra Battle Dark King Haki Coating", "high", 135),
        ("Figuarts ZERO", "Akainu", "Extra Battle Sakazuki Magma Fist", "high", 130),
        ("Figuarts ZERO", "Sabo", "Extra Battle Flame Emperor Entei", "high", 125),
        ("Figuarts ZERO", "Oden", "Extra Battle Kozuki Oden Two-Sword Paradise Totsuka", "high", 140),
        ("Figuarts ZERO", "Yamato", "Extra Battle Okuchi no Makami Ice Breath", "high", 135),
        ("Figuarts ZERO", "Rob Lucci", "Extra Battle Awakened Leopard Form CP0", "high", 120),
        ("Figuarts ZERO", "Luffy vs Lucci", "Extra Battle Egghead Clash", "grail", 220),
        ("Figuarts ZERO", "Roronoa Zoro", "Devil Aura King of Hell", "high", 130),
        ("Figuarts ZERO", "Nami", "Zeus Lightning Tempo", "mid", 85),
        ("Figuarts ZERO", "Usopp", "Elbaf Giant Warrior Impact Wolf", "mid", 75),
        ("Figuarts ZERO", "Franky", "General Franky Radical Beam", "high", 115),
        ("Figuarts ZERO", "Brook", "Soul King Blizzard Slice", "mid", 90),
        ("Figuarts ZERO", "Chopper", "Monster Point Kunfu Point Combo", "mid", 80),
        ("Figuarts ZERO", "Jinbe", "Fish-Man Karate Vagabond Drill", "high", 105),

        # ── Ichiban Kuji / Lottery Prizes (~15) ──────────────────────────
        ("Ichiban Kuji", "Shanks", "Film Red Last One Prize Emperor's Haki", "grail", 260),
        ("Ichiban Kuji", "Monkey D. Luffy", "ONE PIECE FILM RED A Prize Concert Luffy", "high", 120),
        ("Ichiban Kuji", "Uta", "ONE PIECE FILM RED B Prize New Genesis Uta", "high", 100),
        ("Ichiban Kuji", "Ace & Sabo & Luffy", "Brotherhood A Prize Three Brothers Oath", "high", 130),
        ("Ichiban Kuji", "Roger vs Whitebeard", "Legends A Prize Pirate Kings' Duel", "grail", 200),
        ("Ichiban Kuji", "Yamato", "Wano Country Last One Okuchi no Makami Sulong", "grail", 210),
        ("Ichiban Kuji", "Oden", "Wano Legends B Prize Kozuki Oden Togen Totsuka", "high", 115),
        ("Ichiban Kuji", "Gear 5 Luffy", "Egghead Arc A Prize Sun God Transformation", "high", 140),
        ("Ichiban Kuji", "Luffy", "25th Anniversary Memorial Last One Straw Hat", "grail", 230),
        ("Ichiban Kuji", "Zoro vs King", "Wano Final Battle Prize A Enma Black Blade", "high", 130),
        ("Ichiban Kuji", "Sanji vs Queen", "Wano Final Battle Prize B Ifrit Jambe", "high", 110),
        ("Ichiban Kuji", "Doflamingo", "Dressrosa Last One Bird Cage Awakening", "high", 160),
        ("Ichiban Kuji", "Crocodile & Mihawk", "Cross Guild A Prize Buggy's Delivery", "high", 125),
        ("Ichiban Kuji", "Big Mom vs Kid & Law", "Wano Climax Last One Electromagnetic Cannon", "grail", 200),
        ("Ichiban Kuji", "Straw Hat Crew", "25th Anniversary Complete Set (10 prizes)", "grail", 350),

        # ── Manga — Key Volumes & Box Sets (~15) ─────────────────────────
        ("Manga", "Volume 1", "Japanese First Print (1997 Shonen Jump)", "grail", 500),
        ("Manga", "Volume 1", "English First Print (Viz Media 2003)", "grail", 300),
        ("Manga", "Weekly Shonen Jump", "Chapter 1000 Issue (WSJ #5-6 2021)", "high", 120),
        ("Manga", "Weekly Shonen Jump", "Romance Dawn One-Shot Original (WSJ 1996)", "grail", 800),
        ("Manga Box Set", "East Blue", "Box Set 1 (Vol 1-23)", "high", 180),
        ("Manga Box Set", "Baroque Works", "Box Set 2 (Vol 24-46)", "high", 175),
        ("Manga Box Set", "Thriller Bark", "Box Set 3 (Vol 47-70)", "high", 170),
        ("Manga Box Set", "Dressrosa", "Box Set 4 (Vol 71-90)", "high", 165),
        ("Manga", "Volume 1000", "Commemorative Gold Foil Cover Edition", "high", 150),
        ("Manga", "Color Walk", "Eiichiro Oda Color Walk Complete Set (1-9)", "grail", 350),
        ("Manga", "Vivre Card", "Vivre Card Databook Complete Collection", "high", 200),
        ("Manga", "ONE PIECE Magazine", "Complete Set (Vol. 1-17)", "high", 180),
        ("Manga", "Volume 100", "Collector's Edition Gold Foil (JP)", "high", 100),
        ("Manga", "Volume 25", "Wanted! Oda Short Story Collection", "mid", 60),
        ("Manga", "Volume 1-106", "JP Complete Collection (106 tankobon)", "grail", 800),

        # ── One Piece TCG — Cards & Sealed Product (~20) ─────────────────
        ("OP Card Game", "Shanks", "OP01-120 Leader Parallel Art", "grail", 280),
        ("OP Card Game", "Roronoa Zoro", "OP01-025 ALT Art Secret Rare", "grail", 250),
        ("OP Card Game", "Nami", "OP02-036 Leader Parallel Art", "high", 160),
        ("OP Card Game", "Charlotte Katakuri", "OP03-099 ALT Art Secret Rare", "high", 180),
        ("OP Card Game", "Yamato", "OP04-112 Leader ALT Art Parallel", "grail", 220),
        ("OP Card Game", "Monkey D. Luffy", "OP05-119 Nika Secret Rare", "grail", 350),
        ("OP Card Game", "Portgas D. Ace", "OP02-013 ALT Art Fire Fist", "high", 140),
        ("OP Card Game", "Trafalgar Law", "OP05-069 Secret Rare Room Shambles", "high", 130),
        ("OP Card Game", "Boa Hancock", "OP03-052 Secret Rare Love-Love Beam", "high", 120),
        ("OP Card Game", "Eustass Kid", "OP05-074 Secret Rare Punk Gibson", "high", 110),
        ("OP Card Game", "Sealed", "OP01 Romance Dawn Booster Box (24 packs)", "high", 180),
        ("OP Card Game", "Sealed", "OP02 Paramount War Booster Box (24 packs)", "high", 170),
        ("OP Card Game", "Sealed", "OP03 Pillars of Strength Booster Box", "high", 160),
        ("OP Card Game", "Sealed", "OP04 Kingdoms of Intrigue Booster Box", "high", 155),
        ("OP Card Game", "Sealed", "OP05 Awakening of the New Era Booster Box", "high", 190),
        ("OP Card Game", "Sealed", "OP06 Wings of the Captain Booster Box", "high", 150),
        ("OP Card Game", "Sealed", "OP07 500 Years in the Future Booster Box", "high", 200),
        ("OP Card Game", "Sealed", "ST01 Straw Hat Crew Starter Deck", "mid", 50),
        ("OP Card Game", "Sealed", "Promotion Pack Vol.1 Sealed Case (50 packs)", "high", 120),
        ("OP Card Game", "Don!!", "Championship 2024 Winner Trophy Card", "grail", 500),

        # ── Merch / Collectibles (~20) ───────────────────────────────────
        ("Film Red", "Uta", "Banpresto DXF Uta Concert Stage", "mid", 45),
        ("Film Red", "Shanks", "DXF Film Red Emperor's Return", "mid", 55),
        ("Film Red", "Luffy", "DXF Film Red Straw Hat Concert", "mid", 40),
        ("Film Red", "Uta", "Ichiban Kuji Film Red A Prize New Genesis", "high", 100),
        ("Film Red", "Tot Musica", "Ichiban Kuji Film Red Last One Awakened Form", "high", 150),
        ("Replica", "Straw Hat", "Luffy's Straw Hat 1:1 Premium Replica", "high", 120),
        ("Replica", "Going Merry", "Soul of Chogokin Going Merry (Bandai)", "grail", 350),
        ("Replica", "Thousand Sunny", "Soul of Chogokin Thousand Sunny (Bandai)", "grail", 380),
        ("Replica", "Log Pose", "Premium Bandai Log Pose Replica (New World)", "high", 100),
        ("Replica", "Den Den Mushi", "Premium Bandai Baby Den Den Mushi Phone Stand", "mid", 55),
        ("Replica", "Devil Fruit", "Gomu Gomu no Mi Resin Prop Replica", "mid", 75),
        ("Replica", "Devil Fruit", "Mera Mera no Mi Resin Prop Replica", "mid", 70),
        ("Replica", "Devil Fruit", "Ope Ope no Mi Resin Prop Replica", "mid", 70),
        ("Replica", "Wado Ichimonji", "Roronoa Zoro Katana Foam Prop Replica", "mid", 65),
        ("Replica", "Enma", "Roronoa Zoro Enma Katana Metal Prop Replica", "high", 130),
        ("Collab Merch", "Straw Hat Crew", "One Piece x Casio G-Shock GA-110 Collaboration", "high", 200),
        ("Collab Merch", "Luffy", "One Piece x Seiko 25th Anniversary Watch (LE 5000)", "grail", 450),
        ("Collab Merch", "One Piece", "One Piece x BAPE Baby Milo Full Crew T-Shirt Set", "high", 180),
        ("Collab Merch", "One Piece", "One Piece x Uniqlo UT Wano Arc Complete Set (10 tees)", "mid", 90),
        ("Collab Merch", "One Piece", "One Piece x adidas Ultra Boost Luffy Gear 5", "high", 200),

        # ── Vinyl / Music (~10) ──────────────────────────────────────────
        ("Music", "One Piece OST", "New World Original Soundtrack Vinyl 2LP (Milan Records)", "high", 80),
        ("Music", "One Piece Film Red", "Uta's Songs — ONE PIECE FILM RED Vinyl LP", "high", 90),
        ("Music", "One Piece OST", "Over the Top / We Are! 7\" Vinyl Single", "mid", 35),
        ("Music", "One Piece OST", "Bink's Sake / We Go! 7\" Vinyl Single", "mid", 35),
        ("Music", "One Piece", "Opening Theme Collection CD Box Set (25 years)", "high", 120),
        ("Music", "One Piece", "Character Song Collection Complete CD Box (10 CD)", "high", 150),
        ("Music", "One Piece Film Red", "UTA Complete Best CD + Blu-ray LE", "high", 100),
        ("Music", "We Are!", "Hiroshi Kitadani We Are! 7\" Vinyl Anniversary Press", "mid", 40),
        ("Music", "One Piece", "Overtaken / The Very Very Very Strongest 7\" Vinyl", "mid", 45),
        ("Music", "One Piece Film Red", "New Genesis / Backlight 12\" Single Vinyl", "mid", 50),

        # ── Clothing / Accessories (~10) ─────────────────────────────────
        ("Collab Merch", "One Piece", "One Piece x BAPE Shark Hoodie Luffy Full Zip", "grail", 350),
        ("Collab Merch", "One Piece", "One Piece x Swatch Gear 5 Watch", "high", 150),
        ("Collab Merch", "One Piece", "One Piece x New Era 59FIFTY Straw Hat Crew Cap Set (10)", "high", 200),
        ("Collab Merch", "One Piece", "One Piece x XLARGE Wano Arc Collection (5 pieces)", "high", 120),
        ("Collab Merch", "One Piece", "ONEPIECE x Crocs Luffy Clog (LE)", "mid", 80),
        ("Collab Merch", "One Piece", "One Piece x Puma Suede Luffy Gear 5", "high", 160),
        ("Collab Merch", "One Piece", "One Piece x CLOT Royale Shanks Jacket", "high", 180),
        ("Collab Merch", "One Piece", "One Piece Stampede Premium Bomber Jacket (LE 1000)", "high", 200),
        ("Collab Merch", "One Piece", "One Piece x Anti Social Social Club Hoodie Set", "high", 140),
        ("Collab Merch", "One Piece", "One Piece Film Red x BEAMS Collab T-Shirt Set", "mid", 90),

        # ── Anniversary / Special (~15) ──────────────────────────────────
        ("Anniversary", "One Piece", "25th Anniversary Gold DEN DEN Mushi (LE 2500)", "grail", 300),
        ("Anniversary", "One Piece", "25th Anniversary Premium Card Set (TCG Promo)", "high", 120),
        ("Anniversary", "One Piece", "25th Anniversary Ichiban Kuji Complete Set", "grail", 400),
        ("Anniversary", "One Piece", "Jump Festa 2024 Exclusive Gear 5 Acrylic Stand", "mid", 50),
        ("Anniversary", "One Piece", "Jump Festa 2024 Exclusive Promo Card Pack", "mid", 60),
        ("Anniversary", "One Piece", "One Piece Tower Tokyo Final Memorial Goods Set", "grail", 250),
        ("Anniversary", "One Piece", "Tokyo One Piece Tower Cafe Final Day Plate Set", "high", 150),
        ("Anniversary", "One Piece", "One Piece Exhibition Osaka 2024 Exclusive Art Print Set", "high", 120),
        ("Anniversary", "One Piece", "One Piece Exhibition Tokyo 2024 Exclusive Poster Set", "high", 110),
        ("Anniversary", "One Piece", "One Piece Day 2024 Exclusive Merch Bundle", "high", 100),
        ("Anniversary", "One Piece", "One Piece Great Banquet Themed Cafe Plate & Cup Set", "mid", 80),
        ("Anniversary", "One Piece", "WJ 25th Anniversary Cover Collection Art Book", "high", 130),
        ("Anniversary", "One Piece", "Treasure Cruise 10th Anniv. Acrylic Diorama", "mid", 65),
        ("Anniversary", "One Piece", "20th Anniversary Ichiban Kuji Last One Gold Luffy", "grail", 280),
        ("Anniversary", "One Piece", "25th Anniversary Premium Bandai Straw Hat Set (10 figs)", "grail", 400),

        # ── Banpresto Additional (~15) ───────────────────────────────────
        ("Banpresto", "Monkey D. Luffy", "King of Artist Wano Luffy Bound Man", "mid", 50),
        ("Banpresto", "Roronoa Zoro", "King of Artist Wano Zoro Enma", "mid", 50),
        ("Banpresto", "Portgas D. Ace", "King of Artist Ace Fire Fist", "mid", 45),
        ("Banpresto", "Shanks", "King of Artist Shanks Film Red", "mid", 55),
        ("Banpresto", "Trafalgar Law", "DXF Wano Country Law Room", "mid", 40),
        ("Banpresto", "Charlotte Katakuri", "DXF Whole Cake Island Mochi Man", "mid", 45),
        ("Banpresto", "Donquixote Doflamingo", "DXF Dressrosa Heavenly Demon", "mid", 42),
        ("Banpresto", "Sabo", "DXF Dressrosa Flame Emperor", "mid", 40),
        ("Banpresto", "Boa Hancock", "DXF Grandline Lady Hancock Ver.", "mid", 48),
        ("Banpresto", "Nami", "DXF Grandline Lady Nami Wano Ver.", "mid", 42),
        ("Banpresto", "Nico Robin", "DXF Grandline Lady Robin Wano Ver.", "mid", 42),
        ("Banpresto", "Kaido", "DXF Wano Country Beast Form", "mid", 55),
        ("Banpresto", "Yamato", "DXF Wano Country Okuchi no Makami", "mid", 45),
        ("Banpresto", "Big Mom", "DXF Whole Cake Island Charlotte Linlin", "mid", 50),
        ("Banpresto", "Gol D. Roger", "DXF Grandline Men Roger Laugh Tale", "mid", 48),

        # ── Artbooks / Special Editions (~10) ────────────────────────────
        ("Artbook", "Eiichiro Oda", "ONE PIECE Illustration COLORWALK 1 (Signed LE)", "grail", 500),
        ("Artbook", "Eiichiro Oda", "ONE PIECE Film Design Works", "high", 120),
        ("Artbook", "Eiichiro Oda", "ONE PIECE 1000 LOGS (Commemorative Art Book)", "high", 150),
        ("Artbook", "One Piece", "Shonen Jump Cover Art Collection Poster Set", "mid", 80),
        ("Artbook", "One Piece", "Animation 25th Anniversary Art Book", "high", 130),
        ("Artbook", "One Piece", "Film Red Official Visual Guide Book", "mid", 55),
        ("Artbook", "One Piece", "Stampede Official Guide Book", "mid", 45),
        ("Artbook", "One Piece", "Treasure Cruise Official Art Works", "mid", 50),
        ("Artbook", "One Piece", "Strong World Eiichiro Oda Artbook Vol. 0", "mid", 65),
        ("Artbook", "One Piece", "One Piece Pirate Recipes Official Cookbook", "standard", 30),

        # ── G.E.M. Series Figures ──────────────────────────────────────────
        ("G.E.M. Series", "Monkey D. Luffy", "G.E.M. Run! Run! Run! Luffy", "high", 180),
        ("G.E.M. Series", "Roronoa Zoro", "G.E.M. Run! Run! Run! Zoro", "high", 175),
        ("G.E.M. Series", "Portgas D. Ace", "G.E.M. Run! Run! Run! Ace", "high", 185),
        ("G.E.M. Series", "Sabo", "G.E.M. Run! Run! Run! Sabo", "high", 170),
        ("G.E.M. Series", "Nami", "G.E.M. Costume Change Nami (Wano)", "high", 160),
        ("G.E.M. Series", "Nico Robin", "G.E.M. Costume Change Robin (Wano)", "high", 165),
        ("G.E.M. Series", "Trafalgar Law", "G.E.M. Run! Run! Run! Law", "high", 175),
        ("G.E.M. Series", "Shanks", "G.E.M. Red-Haired Shanks (Film Red Ver.)", "grail", 250),
        ("G.E.M. Series", "Boa Hancock", "G.E.M. Boa Hancock Love Hurricane", "high", 190),
        ("G.E.M. Series", "Yamato", "G.E.M. Yamato Okiku Nari", "high", 185),
        ("G.E.M. Series", "Kaido", "G.E.M. Kaido Dragon Form (Oversized)", "grail", 320),
        ("G.E.M. Series", "Monkey D. Luffy", "G.E.M. Gear 5 Luffy (Nika Pose)", "grail", 280),

        # ── World Collectable Figure Complete Waves ────────────────────────
        ("WCF", "Straw Hat Crew", "WCF Vol. 35 Complete Set (8 pcs)", "mid", 65),
        ("WCF", "Wano Country", "WCF Wano Country Vol. 1 Complete (6 pcs)", "mid", 55),
        ("WCF", "Wano Country", "WCF Wano Country Vol. 2 Complete (6 pcs)", "mid", 55),
        ("WCF", "Wano Country", "WCF Wano Country Vol. 3 Complete (6 pcs)", "mid", 55),
        ("WCF", "Wano Country", "WCF Wano Country Vol. 4 Complete (6 pcs)", "mid", 55),
        ("WCF", "Film Red", "WCF Film Red Vol. 1 Complete (6 pcs)", "mid", 50),
        ("WCF", "Film Red", "WCF Film Red Vol. 2 Complete (6 pcs)", "mid", 50),
        ("WCF", "Egghead", "WCF Egghead Arc Vol. 1 Complete (6 pcs)", "mid", 60),
        ("WCF", "Egghead", "WCF Egghead Arc Vol. 2 Complete (6 pcs)", "mid", 60),
        ("WCF", "Straw Hat Crew", "WCF Mugiwara56 Vol. 1 Complete (6 pcs)", "mid", 50),
        ("WCF", "Straw Hat Crew", "WCF Mugiwara56 Vol. 2 Complete (6 pcs)", "mid", 50),
        ("WCF", "Anniversary", "WCF 25th Anniversary Complete (8 pcs)", "high", 80),

        # ── One Piece Card Game Expansion Sets ─────────────────────────────
        ("Card Game", "One Piece Card Game", "OP-01 Romance Dawn Booster Box (24 packs)", "high", 120),
        ("Card Game", "One Piece Card Game", "OP-02 Paramount War Booster Box", "high", 110),
        ("Card Game", "One Piece Card Game", "OP-03 Pillars of Strength Booster Box", "high", 100),
        ("Card Game", "One Piece Card Game", "OP-04 Kingdoms of Intrigue Booster Box", "mid", 90),
        ("Card Game", "One Piece Card Game", "OP-05 Awakening of the New Era Booster Box", "high", 130),
        ("Card Game", "One Piece Card Game", "OP-06 Wings of the Captain Booster Box", "mid", 85),
        ("Card Game", "One Piece Card Game", "OP-07 500 Years in the Future Booster Box", "mid", 80),
        ("Card Game", "One Piece Card Game", "OP-08 Two Legends Booster Box", "mid", 85),
        ("Card Game", "One Piece Card Game", "ST-01 Straw Hat Crew Starter Deck", "standard", 20),
        ("Card Game", "One Piece Card Game", "ST-02 Worst Generation Starter Deck", "standard", 18),
        ("Card Game", "One Piece Card Game", "ST-10 Ultimate Deck The Three Captains", "mid", 40),
        ("Card Game", "One Piece Card Game", "Premium Card Collection Best Selection Vol. 1", "high", 60),
        ("Card Game", "One Piece Card Game", "Premium Card Collection Film Red Edition", "high", 55),
        ("Card Game", "One Piece Card Game", "1st Anniversary Set", "high", 75),

        # ── One Piece x Fashion Collabs ────────────────────────────────────
        ("Collab Merch", "One Piece", "One Piece x BAPE Luffy Camo Tee", "high", 120),
        ("Collab Merch", "One Piece", "One Piece x BAPE Zoro Shark Hoodie", "high", 180),
        ("Collab Merch", "One Piece", "One Piece x Uniqlo UT Wano Arc Tee (Luffy)", "standard", 25),
        ("Collab Merch", "One Piece", "One Piece x Uniqlo UT Wano Arc Tee (Zoro)", "standard", 25),
        ("Collab Merch", "One Piece", "One Piece x Adidas Ultra Boost Luffy", "high", 160),
        ("Collab Merch", "One Piece", "One Piece x Casio G-Shock GA-110 Straw Hat", "high", 200),
        ("Collab Merch", "One Piece", "One Piece x New Era 59FIFTY Jolly Roger Cap", "mid", 55),
        ("Collab Merch", "One Piece", "One Piece x Vans Sk8-Hi Luffy Print", "mid", 95),
        ("Collab Merch", "One Piece", "One Piece x Seiko 5 Sports SRPK37 Luffy Limited", "grail", 450),
        ("Collab Merch", "One Piece", "One Piece x Seiko 5 Sports SRPK39 Zoro Limited", "grail", 450),

        # ── Grand Ship Collection Model Kits ──────────────────────────────
        ("Ship Model", "Straw Hat Crew", "Grand Ship Collection #01 Thousand Sunny", "mid", 35),
        ("Ship Model", "Straw Hat Crew", "Grand Ship Collection #02 Going Merry", "mid", 35),
        ("Ship Model", "Straw Hat Crew", "Grand Ship Collection #03 Thousand Sunny (Film Gold)", "mid", 40),
        ("Ship Model", "Whitebeard Pirates", "Grand Ship Collection #04 Moby Dick", "mid", 35),
        ("Ship Model", "Trafalgar Law", "Grand Ship Collection #05 Polar Tang Submarine", "mid", 35),
        ("Ship Model", "Red Hair Pirates", "Grand Ship Collection #06 Red Force", "mid", 38),
        ("Ship Model", "Heart Pirates", "Grand Ship Collection #07 Thousand Sunny (Wano)", "mid", 40),
        ("Ship Model", "Straw Hat Crew", "Grand Ship Collection #08 Thousand Sunny (Flying Model)", "mid", 42),
        ("Ship Model", "Boa Hancock", "Grand Ship Collection #09 Kuja Pirates Ship", "mid", 38),
        ("Ship Model", "Navy", "Grand Ship Collection #10 Marine Warship", "mid", 35),
        ("Ship Model", "Straw Hat Crew", "Grand Ship Collection Going Merry (Memorial Color)", "high", 55),
        ("Ship Model", "Baroque Works", "Grand Ship Collection Full Force Baratie", "mid", 40),

        # ── Food-Themed Merch ──────────────────────────────────────────────
        ("Food Merch", "Sanji", "One Piece Baratie Restaurant Plate Set (4 pcs)", "mid", 55),
        ("Food Merch", "Sanji", "One Piece Sanji's Kitchen Apron (Official)", "standard", 30),
        ("Food Merch", "Chopper", "One Piece Chopper Cotton Candy Tin", "standard", 18),
        ("Food Merch", "Luffy", "One Piece Luffy Meat Bone Chopstick Rest Set", "standard", 15),
        ("Food Merch", "Straw Hat Crew", "One Piece Devil Fruit Replica Set (3 fruits)", "high", 120),
        ("Food Merch", "Straw Hat Crew", "One Piece Premium Sake Cup Set (Wano)", "mid", 65),
        ("Food Merch", "Straw Hat Crew", "One Piece Jolly Roger Beer Glass Set (4 crews)", "mid", 50),
        ("Food Merch", "Luffy", "One Piece Gomu Gomu no Mi Replica Fruit", "mid", 45),
        ("Food Merch", "Trafalgar Law", "One Piece Ope Ope no Mi Replica Fruit", "mid", 48),
        ("Food Merch", "Ace", "One Piece Mera Mera no Mi Replica Fruit", "mid", 48),

        # ── Additional FiguartsZERO ────────────────────────────────────────
        ("FiguartsZERO", "Monkey D. Luffy", "FiguartsZERO Extra Battle Luffy Gear 5 Thunder", "grail", 280),
        ("FiguartsZERO", "Kaido", "FiguartsZERO Extra Battle Kaido Blast Breath", "grail", 250),
        ("FiguartsZERO", "Roronoa Zoro", "FiguartsZERO Extra Battle Zoro Purgatory Onigiri", "high", 180),
        ("FiguartsZERO", "Sanji", "FiguartsZERO Extra Battle Sanji Diable Jambe", "high", 160),
        ("FiguartsZERO", "Trafalgar Law", "FiguartsZERO Extra Battle Law K-Room", "high", 170),
        ("FiguartsZERO", "Eustass Kid", "FiguartsZERO Extra Battle Kid Punk Gibson", "high", 175),
        ("FiguartsZERO", "Shanks", "FiguartsZERO Extra Battle Shanks Haki", "grail", 300),
        ("FiguartsZERO", "Whitebeard", "FiguartsZERO Extra Battle Whitebeard Quake", "grail", 280),
        ("FiguartsZERO", "Portgas D. Ace", "FiguartsZERO Extra Battle Ace Fire Fist", "high", 200),
        ("FiguartsZERO", "Yamato", "FiguartsZERO Extra Battle Yamato Thunder Bagua", "high", 185),

        # ── Ichiban Kuji Prizes ────────────────────────────────────────────
        ("Ichiban Kuji", "Monkey D. Luffy", "Ichiban Kuji Legends A Prize Luffy Gear 5", "high", 120),
        ("Ichiban Kuji", "Roronoa Zoro", "Ichiban Kuji Legends B Prize Zoro Enma", "high", 100),
        ("Ichiban Kuji", "Sanji", "Ichiban Kuji Legends C Prize Sanji Ifrit", "mid", 80),
        ("Ichiban Kuji", "Yamato", "Ichiban Kuji Wano D Prize Yamato", "mid", 75),
        ("Ichiban Kuji", "Monkey D. Luffy", "Ichiban Kuji Film Red Last One Prize Luffy", "grail", 200),
        ("Ichiban Kuji", "Shanks", "Ichiban Kuji Film Red A Prize Shanks", "high", 150),
        ("Ichiban Kuji", "Uta", "Ichiban Kuji Film Red B Prize Uta", "high", 130),
        ("Ichiban Kuji", "Straw Hat Crew", "Ichiban Kuji Egghead Full Set (A-F + Last One)", "grail", 400),
        ("Ichiban Kuji", "Nami", "Ichiban Kuji Wano E Prize Nami Kimono", "mid", 60),
        ("Ichiban Kuji", "Nico Robin", "Ichiban Kuji Wano F Prize Robin Kimono", "mid", 65),

        # ── One Piece Manga Volumes (Key Issues) ──────────────────────────
        ("Manga", "One Piece", "One Piece Vol. 1 (1st Print Japanese)", "grail", 500),
        ("Manga", "One Piece", "One Piece Vol. 1 (English, 1st Print Viz)", "high", 150),
        ("Manga", "One Piece", "One Piece Box Set 1 (Vols 1-23, English)", "high", 180),
        ("Manga", "One Piece", "One Piece Box Set 2 (Vols 24-46, English)", "high", 180),
        ("Manga", "One Piece", "One Piece Box Set 3 (Vols 47-70, English)", "high", 180),
        ("Manga", "One Piece", "One Piece Box Set 4 (Vols 71-90, English)", "high", 180),
        ("Manga", "One Piece", "One Piece Vol. 100 (Anniversary Cover, Japanese)", "mid", 40),
        ("Manga", "One Piece", "One Piece Color Walk 9 TIGER (Oda Artbook)", "mid", 55),

        # ── One Piece Music / Vinyl ────────────────────────────────────────
        ("Music", "One Piece", "One Piece Film Red OST (Ado, 2-LP Vinyl)", "high", 120),
        ("Music", "One Piece", "One Piece Opening Theme Collection CD Box (20 CDs)", "grail", 250),
        ("Music", "One Piece", "We Are! (Single CD, Hiroshi Kitadani)", "mid", 35),
        ("Music", "One Piece", "One Piece Film Z OST (CD)", "mid", 40),
        ("Music", "One Piece", "One Piece Stampede OST (CD)", "mid", 38),

        # ── Additional Collabs & Anniversary ───────────────────────────────
        ("Collab Merch", "One Piece", "One Piece x Swatch Big Bold Watch Luffy", "high", 180),
        ("Collab Merch", "One Piece", "One Piece x Swatch Big Bold Watch Zoro", "high", 180),
        ("Collab Merch", "One Piece", "One Piece x Moleskine Notebook Set (3 pcs)", "mid", 45),
        ("Collab Merch", "One Piece", "One Piece 25th Anniversary Ichiban Kuji Full Set", "grail", 350),
        ("Collab Merch", "One Piece", "One Piece x Crocs Classic Clog Luffy", "mid", 75),
        ("Collab Merch", "One Piece", "One Piece Mugiwara Store Exclusive Straw Hat (Real)", "high", 120),
        ("Collab Merch", "One Piece", "One Piece x Monopoly Board Game (Collector)", "mid", 55),
        ("Collab Merch", "One Piece", "One Piece x Funko Pop 4-Pack Straw Hat Crew", "mid", 60),
        ("Collab Merch", "One Piece", "One Piece Film Red Premium Card Case (Gold)", "mid", 45),
        ("Collab Merch", "One Piece", "One Piece Jump Shop Exclusive Clear File Set (10)", "standard", 25),

        # ── Variable Action Heroes (VAH) ───────────────────────────────────
        ("VAH", "Monkey D. Luffy", "VAH Luffy (Wano Country)", "high", 120),
        ("VAH", "Roronoa Zoro", "VAH Zoro (Wano Country)", "high", 120),
        ("VAH", "Sanji", "VAH Sanji (Wano Country)", "high", 115),
        ("VAH", "Trafalgar Law", "VAH Law (Wano Country)", "high", 115),
        ("VAH", "Portgas D. Ace", "VAH Ace (Fire Fist)", "high", 125),
        ("VAH", "Sabo", "VAH Sabo (Dragon Claw)", "high", 120),
        ("VAH", "Boa Hancock", "VAH Hancock (Amazon Lily)", "high", 130),
        ("VAH", "Nami", "VAH Nami (Clima-Tact)", "high", 110),

        # ── DXF / Grandista ────────────────────────────────────────────────
        ("DXF", "Monkey D. Luffy", "Grandista Nero Luffy", "mid", 55),
        ("DXF", "Roronoa Zoro", "Grandista Nero Zoro", "mid", 55),
        ("DXF", "Monkey D. Luffy", "DXF The Grandline Men Luffy Gear 5", "mid", 40),
        ("DXF", "Yamato", "DXF The Grandline Lady Yamato", "mid", 45),
        ("DXF", "Uta", "DXF The Grandline Lady Uta (Film Red)", "mid", 42),
        ("DXF", "Shanks", "Grandista Shanks (Film Red)", "mid", 60),

        # ── Plush / Cushions ───────────────────────────────────────────────
        ("Plush", "Chopper", "One Piece Chopper Premium Plush (30cm)", "standard", 35),
        ("Plush", "Luffy", "One Piece Luffy Chibi Plush Keychain", "standard", 12),
        ("Plush", "Bepo", "One Piece Bepo the Bear Plush (40cm)", "mid", 45),
        ("Plush", "Thousand Sunny", "One Piece Thousand Sunny Ship Cushion (50cm)", "mid", 55),
        ("Plush", "Going Merry", "One Piece Going Merry Ship Cushion (50cm)", "mid", 55),
        ("Plush", "Straw Hat Crew", "One Piece Straw Hat Crew Mini Plush Set (10 pcs)", "high", 80),

        # ── Stamps / Coins / Medals ────────────────────────────────────────
        ("Collectible", "One Piece", "One Piece 25th Anniversary Silver Coin Set", "grail", 250),
        ("Collectible", "One Piece", "One Piece Japan Post Stamp Sheet (2023)", "mid", 40),
        ("Collectible", "One Piece", "One Piece Ichibankuji Metal Medal Set", "mid", 35),
        ("Collectible", "Monkey D. Luffy", "One Piece Gear 5 Luffy Gold Foil Card", "mid", 50),
        ("Collectible", "Straw Hat Crew", "One Piece Wanted Poster Premium Metal Set (10)", "high", 90),

        # ── One Piece Clothing & Accessories ───────────────────────────────
        ("Collab Merch", "One Piece", "One Piece x Champion Straw Hat Crew Hoodie", "mid", 75),
        ("Collab Merch", "One Piece", "One Piece x Crocs Jibbitz Charm Set (10 pcs)", "standard", 25),
        ("Collab Merch", "One Piece", "One Piece Mugiwara Store Luffy Snapback Cap", "standard", 30),
        ("Collab Merch", "One Piece", "One Piece x Primitive Skate Deck (Luffy)", "mid", 65),
        ("Collab Merch", "One Piece", "One Piece x Primitive Skate Deck (Zoro)", "mid", 65),
        ("Collab Merch", "One Piece", "One Piece Egghead Arc Official Keychain Set (6)", "standard", 20),
        ("Collab Merch", "One Piece", "One Piece x Reebok Club C 85 Straw Hat", "high", 130),
        ("Collab Merch", "One Piece", "One Piece Film Red Theatrical Program Book", "standard", 15),
    ]


def item_to_catalog_item(item: dict) -> CatalogItem:
    line = item["line"]
    name = item["name"]
    variant = item["variant"]

    title_parts = [name]
    if variant:
        title_parts.append(f"({variant})")

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{line}-{name}-{variant}"),
        title=" ".join(title_parts),
        set_code=line.lower().replace(" ", "-").replace(".", ""),
        brand=_line_to_brand(line),
        rarity=item["rarity_tier"].title(),
        notes=f"{line}" + (f" | {variant}" if variant else ""),
        attributes_json={
            "line": line,
            "variant": variant,
            "is_figure": line not in ("OP Card Game", "Ship Model", "WCF", "Manga", "Manga Box Set"),
            "is_card": line == "OP Card Game",
            "is_prize": line in ("Ichiban Kuji", "Banpresto"),
            "is_model": line == "Ship Model",
            "is_set": line == "WCF",
            "is_statue": line in ("Tsume HQS", "Tsume HQS+"),
            "is_manga": line in ("Manga", "Manga Box Set"),
        },
    )


def _line_to_brand(line: str) -> str:
    brand_map = {
        "P.O.P.": "Megahouse",
        "Figuarts ZERO": "Bandai",
        "S.H.Figuarts": "Bandai",
        "Ichiban Kuji": "Bandai Spirits",
        "Banpresto": "Banpresto",
        "OP Card Game": "Bandai",
        "VAH": "Megahouse",
        "MegaHouse": "Megahouse",
        "Tsume HQS": "Tsume Art",
        "GEM Series": "Megahouse",
        "WCF": "Banpresto",
        "Ship Model": "Bandai",
        "Film Red": "Banpresto",
        "Film Gold": "Banpresto",
        "Film Z": "Banpresto",
        "Stampede": "Banpresto",
        "Manga": "Shueisha",
        "Magazine Figure": "Banpresto",
        "Uniqlo UT": "Uniqlo",
        "Collab Merch": "Bandai Namco",
        "Gashapon": "Bandai",
        "MFSP": "Banpresto",
        "20th Anniversary": "Bandai Spirits",
        "25th Anniversary": "Bandai Spirits",
        "Manga Box Set": "Shueisha",
        "Live-Action": "Netflix / Bandai",
        "Nendoroid": "Good Smile Company",
        "Tsume HQS+": "Tsume Art",
    }
    for prefix, brand in brand_map.items():
        if line.startswith(prefix):
            return brand
    return "Bandai"


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]
    is_limited = (
        item["line"].startswith("P.O.P.")
        or item["line"] == "Tsume HQS"
        or "Last One" in item.get("variant", "")
    )

    return PriceObservation(
        features={
            "condition_score": 0.9,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": 0.85 if is_limited else 0.4,
            "is_figure": 1.0 if item["line"] != "OP Card Game" else 0.0,
            "is_card": 1.0 if item["line"] == "OP Card Game" else 0.0,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import One Piece collectibles catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== One Piece Import ===")

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

    logger.info(f"\n=== One Piece Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
