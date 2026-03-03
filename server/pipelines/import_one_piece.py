"""
Import One Piece collectibles data (500+ items).

Layer 1 (Catalog):  Curated 500+ items across P.O.P., Figuarts, Ichiban Kuji,
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
    """Curated One Piece collectibles catalog (500+ items)."""

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

    catalog = []
    for line, name, variant, tier, price in items:
        catalog.append({
            "line": line,
            "name": name,
            "variant": variant,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


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
