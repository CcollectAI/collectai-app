"""
Import Bandai Premium / P-Bandai exclusive figures catalog (700+ items).

Layer 1 (Catalog):  Curated P-Bandai exclusives → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Gundam model kits (MG, PG, RG, HG P-Bandai exclusives, Clear/Coating/Titanium)
- S.H.Figuarts web exclusives (Dragon Ball, Kamen Rider, Naruto, One Piece, Ultraman,
  Marvel, Star Wars, Bleach, JoJo, Jujutsu Kaisen, Demon Slayer, My Hero Academia)
- Robot Spirits (Gundam UC/Hathaway/WfM/SEED/SEED Freedom/00, Evangelion, Code Geass,
  Full Metal Panic)
- Super Robot Chogokin / Soul of Chogokin vintage super robot
- Tamashii Nations event exclusives (TNE/SDCC/Tamashii World Tour)
- Metal Build premium Gundam figures
- DX Chogokin Macross Valkyries (all eras)
- Figuarts ZERO Extra Battle (One Piece, Dragon Ball)
- MG/PG/RG/HG P-Bandai web exclusive model kits
- Complete Selection Modification (CSM) Kamen Rider belts
- Proplica prop replicas (Sailor Moon, Demon Slayer, Bleach, Dragon Ball)
- S.H.MonsterArts (Godzilla, kaiju exclusives)
- Figure-rise Standard / Figure-rise LABO
- Premium candy toys (Super MiniPla/SMP), gashapon, Ichiban Kuji

Usage:
    python -m pipelines.import_bandai_premium [--dry-run]
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

CATEGORY = "bandai_premium"


def _additional_metal_build() -> list[tuple]:
    """More Metal Build — Freedom 2.0, Strike Freedom Soul Blue, Crossbone X-2."""
    return [
        ("Metal Build", "Freedom Gundam Concept 2", "Gundam SEED", "P-Bandai", "grail", 420),
        ("Metal Build", "Crossbone Gundam X-2", "Crossbone Gundam", "P-Bandai", "high", 300),
        ("Metal Build", "Aile Strike Gundam", "Gundam SEED", "Standard", "high", 260),
        ("Metal Build", "Gundam Exia Repair IV", "Gundam 00", "P-Bandai", "grail", 380),
        ("Metal Build", "Wing Gundam Zero (EW) Snow White Prelude", "Gundam Wing", "P-Bandai", "grail", 450),
    ]


def _additional_dx_chogokin() -> list[tuple]:
    """More DX Chogokin — VF-1S Strike Valkyrie, YF-29 Durandal, VF-25F Renewal."""
    return [
        ("DX Chogokin", "VF-1S Strike Valkyrie (Ichijo Hikaru) Renewal", "Macross", "P-Bandai", "grail", 350),
        ("DX Chogokin", "VF-1J Valkyrie (Maximilian Jenius)", "Macross", "P-Bandai", "high", 280),
        ("DX Chogokin", "VF-1A Valkyrie (Mass Production)", "Macross", "Standard", "high", 220),
        ("DX Chogokin", "YF-29 Durandal Valkyrie Full Set Pack", "Macross Frontier", "P-Bandai", "grail", 380),
        ("DX Chogokin", "VF-25F Messiah Valkyrie Renewal Ver.", "Macross Frontier", "P-Bandai", "high", 300),
        ("DX Chogokin", "VF-31J Siegfried (Hayate Immelman)", "Macross Delta", "Standard", "high", 240),
    ]


def _additional_tamashii_event() -> list[tuple]:
    """Tamashii Nations exclusive event items."""
    return [
        ("S.H.Figuarts", "Son Goku Ultra Instinct (TNE 2024)", "Dragon Ball Super", "TNE", "high", 175),
        ("S.H.Figuarts", "Perfect Cell (SDCC 2023 Exclusive)", "Dragon Ball Z", "Event Exclusive", "high", 165),
        ("S.H.Figuarts", "Broly Full Power (Tamashii Nations Osaka)", "Dragon Ball Super: Broly", "Event Exclusive", "high", 190),
        ("Robot Spirits", "RX-0 Unicorn Gundam (Destroy Mode) Pearl Coating", "Gundam Unicorn", "TNE", "high", 150),
    ]


def _additional_shf_db_exclusives() -> list[tuple]:
    """S.H.Figuarts Dragon Ball exclusives — SDCC, event exclusives."""
    return [
        ("S.H.Figuarts", "Son Gohan Beast", "Dragon Ball Super: Super Hero", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Cell Max", "Dragon Ball Super: Super Hero", "P-Bandai", "mid", 110),
        ("S.H.Figuarts", "Gamma 1 & Gamma 2 Set", "Dragon Ball Super: Super Hero", "P-Bandai", "high", 155),
        ("S.H.Figuarts", "Orange Piccolo", "Dragon Ball Super: Super Hero", "P-Bandai", "mid", 100),
    ]


def _additional_robot_spirits() -> list[tuple]:
    """Robot Spirits — Gundam NT, Hathaway's Flash units."""
    return [
        ("Robot Spirits", "Narrative Gundam A-Packs ver. A.N.I.M.E.", "Gundam NT", "P-Bandai", "mid", 90),
        ("Robot Spirits", "Sinanju Stein (Narrative Ver.) ver. A.N.I.M.E.", "Gundam NT", "P-Bandai", "mid", 85),
        ("Robot Spirits", "Xi Gundam ver. A.N.I.M.E.", "Hathaway's Flash", "P-Bandai", "high", 160),
        ("Robot Spirits", "Penelope ver. A.N.I.M.E.", "Hathaway's Flash", "P-Bandai", "high", 170),
        ("Robot Spirits", "Messer Type-F01 ver. A.N.I.M.E.", "Hathaway's Flash", "P-Bandai", "mid", 80),
    ]


def _additional_figuarts_zero_chogokin() -> list[tuple]:
    """Figuarts ZERO Extra Battle, Chogokin Mazinger/Getter."""
    return [
        ("Figuarts ZERO", "Edward Newgate (Whitebeard) -Pirate Captain-", "One Piece", "Standard", "mid", 110),
        ("Figuarts ZERO", "Shanks -Sovereign Haki-", "One Piece", "Standard", "mid", 95),
        ("Figuarts ZERO", "Yamato -Thunder Bagua-", "One Piece", "Standard", "mid", 85),
        ("Soul of Chogokin", "GX-01R Mazinger Z (OG Chogokin Revival)", "Mazinger Z", "Standard", "high", 200),
        ("Soul of Chogokin", "GX-87 Getter Emperor", "Getter Robo", "Standard", "grail", 380),
        ("Soul of Chogokin", "GX-100 Gaiking (The Legend of Daiku-Maryu)", "Gaiking", "Standard", "high", 250),
        ("Metal Build", "Laevatein Ver.IV (Full Metal Panic!)", "Full Metal Panic!", "Standard", "high", 280),
    ]


def _additional_pbandai_kits() -> list[tuple]:
    """P-Bandai web exclusive kits and figures."""
    return [
        ("S.H.Figuarts", "Trunks -Super Saiyan- (Premium Color)", "Dragon Ball Z", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "Kamen Rider Zero-One Realizing Hopper", "Kamen Rider Zero-One", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Ultraman Trigger Multi Type", "Ultraman Trigger", "P-Bandai", "mid", 75),
        ("Robot Spirits", "Gundam Aerial Rebuild ver. A.N.I.M.E.", "Gundam: Witch from Mercury", "P-Bandai", "mid", 85),
    ]


def _additional_shf_jojo_dbsuper() -> list[tuple]:
    """S.H.Figuarts — JoJo's Bizarre Adventure, Dragon Ball Super expansion."""
    return [
        ("S.H.Figuarts", "Jotaro Kujo", "JoJo's Bizarre Adventure", "Standard", "mid", 85),
        ("S.H.Figuarts", "DIO", "JoJo's Bizarre Adventure", "Standard", "mid", 90),
        ("S.H.Figuarts", "Giorno Giovanna", "JoJo's Bizarre Adventure", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Bruno Bucciarati", "JoJo's Bizarre Adventure", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "Jolyne Cujoh", "JoJo's Bizarre Adventure", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Son Goku Super Hero", "Dragon Ball Super: Super Hero", "Standard", "mid", 75),
        ("S.H.Figuarts", "Piccolo Power Awakening", "Dragon Ball Super: Super Hero", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Black Frieza", "Dragon Ball Super", "P-Bandai", "high", 150),
    ]


def _additional_robot_spirits_expanded() -> list[tuple]:
    """Robot Spirits — Code Geass, Gundam SEED, 00, Build."""
    return [
        ("Robot Spirits", "Lancelot Albion ver. A.N.I.M.E.", "Code Geass", "P-Bandai", "mid", 95),
        ("Robot Spirits", "Guren Type-08 Elements ver. A.N.I.M.E.", "Code Geass", "P-Bandai", "mid", 90),
        ("Robot Spirits", "Strike Freedom Gundam ver. A.N.I.M.E.", "Gundam SEED Destiny", "P-Bandai", "high", 130),
        ("Robot Spirits", "Destiny Gundam ver. A.N.I.M.E.", "Gundam SEED Destiny", "P-Bandai", "mid", 110),
        ("Robot Spirits", "00 Raiser + GN Sword III ver. A.N.I.M.E.", "Gundam 00", "P-Bandai", "high", 125),
        ("Robot Spirits", "Reborns Gundam ver. A.N.I.M.E.", "Gundam 00", "P-Bandai", "mid", 95),
        ("Robot Spirits", "Gundam Barbatos Lupus Rex ver. A.N.I.M.E.", "Iron-Blooded Orphans", "P-Bandai", "mid", 100),
        ("Robot Spirits", "Build Strike Gundam Full Package ver. A.N.I.M.E.", "Gundam Build Fighters", "P-Bandai", "mid", 80),
    ]


def _additional_mg_rg_kits() -> list[tuple]:
    """MG/RG/HG P-Bandai exclusive kits — expanded."""
    return [
        ("RG 1/144", "Sinanju (Titanium Finish)", "Gundam Unicorn", "P-Bandai", "mid", 75),
        ("RG 1/144", "Wing Gundam Zero EW (Pearl Gloss)", "Gundam Wing", "P-Bandai", "mid", 70),
        ("RG 1/144", "Crossbone Gundam X1", "Crossbone Gundam", "P-Bandai", "mid", 65),
        ("RG 1/144", "Gundam Mk-II Titans (Premium Bandai)", "Zeta Gundam", "P-Bandai", "mid", 60),
        ("MG 1/100", "Altron Gundam EW (P-Bandai)", "Gundam Wing EW", "P-Bandai", "mid", 85),
        ("MG 1/100", "Gundam F91 Ver.2.0 (Afterimage Clear)", "Gundam F91", "P-Bandai", "mid", 90),
        ("MG 1/100", "Jesta Cannon", "Gundam Unicorn", "P-Bandai", "mid", 80),
        ("MG 1/100", "Gundam Sandrock EW (Armadillo Unit)", "Gundam Wing EW", "P-Bandai", "mid", 85),
        ("HG 1/144", "Penelope vs. Xi Gundam Funnel Missile Effect Set", "Hathaway's Flash", "P-Bandai", "mid", 110),
        ("HG 1/144", "Gundam Lfrith Ur", "Gundam: Witch from Mercury", "P-Bandai", "mid", 45),
    ]


def _additional_shf_kamen_rider_expanded() -> list[tuple]:
    """S.H.Figuarts — additional Kamen Rider entries."""
    return [
        ("S.H.Figuarts", "Kamen Rider Build RabbitTank Sparkling", "Kamen Rider Build", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Kamen Rider Ex-Aid Muteki Gamer", "Kamen Rider Ex-Aid", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Kamen Rider Geats Magnum Boost", "Kamen Rider Geats", "Standard", "mid", 70),
        ("S.H.Figuarts", "Kamen Rider Gotchard Appareskebow", "Kamen Rider Gotchard", "Standard", "mid", 68),
        ("S.H.Figuarts", "Kamen Rider Revice Rex Genome", "Kamen Rider Revice", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Kamen Rider Zi-O Grand Zi-O", "Kamen Rider Zi-O", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Kamen Rider Saber Emotional Dragon", "Kamen Rider Saber", "P-Bandai", "mid", 75),
        ("S.H.Figuarts", "Kamen Rider Amazon Alpha", "Kamen Rider Amazons", "P-Bandai", "mid", 90),
    ]


def _additional_super_sentai_ultraman() -> list[tuple]:
    """S.H.Figuarts — Super Sentai, Ultraman lines."""
    return [
        ("S.H.Figuarts", "Ultraman Zero", "Ultraman", "Standard", "mid", 65),
        ("S.H.Figuarts", "Ultraman Tiga Multi Type", "Ultraman Tiga", "Standard", "mid", 70),
        ("S.H.Figuarts", "Ultraman Blazar", "Ultraman Blazar", "Standard", "mid", 65),
        ("S.H.Figuarts", "Zyuoh Eagle", "Super Sentai Zyuohger", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Abare Killer", "Super Sentai Abaranger", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Dekaranger Complete Set (5 Figures)", "Super Sentai Dekaranger", "P-Bandai", "grail", 400),
        ("Ultra-Act", "Ultraman (Type A)", "Ultraman", "Standard", "high", 150),
        ("Ultra-Act", "Ultraman Ace", "Ultraman Ace", "P-Bandai", "high", 160),
        ("S.H.Figuarts", "Ultraman Decker Flash Type", "Ultraman Decker", "Standard", "mid", 65),
        ("S.H.Figuarts", "Kamen Rider Agito Ground Form (Renewal)", "Kamen Rider Agito", "P-Bandai", "mid", 85),
    ]


def _additional_metal_build_expanded() -> list[tuple]:
    """Metal Build — additional premium figures."""
    return [
        ("Metal Build", "Wing Gundam (TV Ver.)", "Gundam Wing", "Standard", "high", 250),
        ("Metal Build", "Gundam Astray Blue Frame (Full Weapon Set)", "Gundam SEED Astray", "P-Bandai", "high", 300),
        ("Metal Build", "Qan[T] Full Saber", "Gundam 00 Movie", "P-Bandai", "grail", 380),
        ("Metal Build", "Strike Rouge + Ootori Striker", "Gundam SEED", "P-Bandai", "high", 290),
        ("Metal Build", "Gundam F91 (Harrison Maddin Custom)", "Gundam F91", "P-Bandai", "high", 280),
        ("Metal Build", "Avalanche Exia", "Gundam 00V", "P-Bandai", "grail", 400),
        ("Metal Build", "Great Mazinger (Infinity Ver.)", "Mazinger", "Standard", "high", 260),
        ("Metal Build", "Dragon Scale Destiny Gundam", "Gundam SEED Destiny", "P-Bandai", "grail", 520),
    ]


def _additional_figuarts_zero_expanded() -> list[tuple]:
    """Figuarts ZERO — additional One Piece, Demon Slayer, Dragon Ball."""
    return [
        ("Figuarts ZERO", "Roronoa Zoro -Three Sword Style-", "One Piece", "Standard", "mid", 80),
        ("Figuarts ZERO", "Nico Robin -Devil Child-", "One Piece", "P-Bandai", "mid", 85),
        ("Figuarts ZERO", "Gear 5 Luffy -Drums of Liberation-", "One Piece", "Standard", "high", 160),
        ("Figuarts ZERO", "Tanjiro Kamado -Water Breathing-", "Demon Slayer", "Standard", "mid", 75),
        ("Figuarts ZERO", "Rengoku Kyojuro -Flame Hashira-", "Demon Slayer", "Standard", "mid", 85),
        ("Figuarts ZERO", "Vegeta Final Flash", "Dragon Ball Z", "Standard", "mid", 80),
        ("Figuarts ZERO", "Trafalgar Law -Gamma Knife-", "One Piece", "Standard", "mid", 90),
        ("Figuarts ZERO", "Sanji -Diable Jambe-", "One Piece", "P-Bandai", "mid", 85),
        ("Figuarts ZERO", "Zenitsu Agatsuma -Thunderclap and Flash-", "Demon Slayer", "Standard", "mid", 80),
        ("Figuarts ZERO", "Inosuke Hashibira -Beast Breathing-", "Demon Slayer", "Standard", "mid", 75),
    ]


def _additional_bandai_items() -> list[tuple]:
    """Additional Bandai Premium items — Metal Build, DX Chogokin, Robot Spirits, Figuarts, kits."""
    return [
        # Metal Build — Freedom 2.0, Strike Freedom Soul Blue, Laevatein, Destiny Heine
        ("Metal Build", "Freedom Gundam 2.0", "Gundam SEED", "P-Bandai", "grail", 400),
        ("Metal Build", "Strike Freedom Gundam Soul Blue Ver.", "Gundam SEED Destiny", "P-Bandai", "grail", 480),
        ("Metal Build", "Crossbone Gundam X-2 Kai", "Crossbone Gundam", "P-Bandai", "high", 320),
        ("Metal Build", "Destiny Gundam Heine Westenfluss Custom", "Gundam SEED Destiny", "P-Bandai", "high", 310),
        ("Metal Build", "Laevatein (Full Metal Panic! IV)", "Full Metal Panic!", "P-Bandai", "high", 290),

        # DX Chogokin — Valkyrie variants
        ("DX Chogokin", "VF-1S Strike Valkyrie (Roy Focker Special)", "Macross", "P-Bandai", "grail", 380),
        ("DX Chogokin", "YF-29 Durandal Valkyrie (Isamu Dyson)", "Macross Frontier", "P-Bandai", "grail", 360),
        ("DX Chogokin", "VF-25F Messiah Valkyrie Renewal Ver. (Tornado Pack)", "Macross Frontier", "P-Bandai", "high", 310),
        ("DX Chogokin", "VF-31J Siegfried (Hayate) Kairos Plus", "Macross Delta", "P-Bandai", "high", 270),

        # Robot Spirits — Xi, Penelope, Nightingale, RX-93ff
        ("Robot Spirits", "Xi Gundam Missile Pod Equipment ver. A.N.I.M.E.", "Hathaway's Flash", "P-Bandai", "high", 175),
        ("Robot Spirits", "Penelope (Odysseus Gundam) ver. A.N.I.M.E.", "Hathaway's Flash", "P-Bandai", "high", 180),
        ("Robot Spirits", "Nightingale (Heavy Paint Spec.) ver. A.N.I.M.E.", "Gundam CCA-MSV", "P-Bandai", "high", 175),
        ("Robot Spirits", "RX-93ff Nu Gundam (Fukuoka Ver.)", "Gundam CCA", "P-Bandai", "high", 165),

        # S.H.Figuarts — Dragon Ball event exclusives
        ("S.H.Figuarts", "Son Goku Ultra Instinct -Perfected- (TNE 2023)", "Dragon Ball Super", "TNE", "high", 185),
        ("S.H.Figuarts", "Vegeta Super Saiyan God SS Evolved", "Dragon Ball Super", "P-Bandai", "mid", 100),
        ("S.H.Figuarts", "Broly Full Power (Event Color)", "Dragon Ball Super: Broly", "Event Exclusive", "high", 200),

        # Figuarts ZERO — One Piece Extra Battle
        ("Figuarts ZERO", "Kaido -King of the Beasts- Extra Battle", "One Piece", "Standard", "mid", 130),
        ("Figuarts ZERO", "Big Mom Charlotte Linlin -Heavenly Fire-", "One Piece", "Standard", "mid", 115),
        ("Figuarts ZERO", "Monkey D. Luffy Gear 5 -Gigant-", "One Piece", "Standard", "high", 150),

        # Chogokin / Soul of Chogokin — classic super robots
        ("Soul of Chogokin", "GX-70D Mazinger Z D.C. (Damaged Ver.)", "Mazinger Z", "P-Bandai", "high", 250),
        ("Soul of Chogokin", "GX-94 Getter Robo Arc (Super Robot)", "Getter Robo Arc", "Standard", "high", 230),
        ("Soul of Chogokin", "GX-105 Combattler V", "Combattler V", "Standard", "high", 240),
        ("Soul of Chogokin", "GX-71 Voltron (Beast King GoLion)", "Beast King GoLion", "Standard", "high", 300),
        ("Soul of Chogokin", "GX-59R Daltanious", "Future Robo Daltanious", "Standard", "high", 260),

        # Tamashii Nations event exclusives (TNT2023, TNT2024)
        ("S.H.Figuarts", "Frieza First Form & Pod (TNT 2023)", "Dragon Ball Z", "Event Exclusive", "high", 190),
        ("Robot Spirits", "Gundam Aerial (TNT 2024 Limited Color)", "Gundam: Witch from Mercury", "Event Exclusive", "high", 155),
        ("S.H.Figuarts", "Kamen Rider Geats Boost Mark IX (TNT 2024)", "Kamen Rider Geats", "Event Exclusive", "mid", 120),
        ("Metal Build", "Freedom Gundam Concept 2.0 (TNT 2024 Ver.)", "Gundam SEED", "Event Exclusive", "grail", 500),

        # P-Bandai MG/PG web exclusives
        ("MG 1/100", "Gundam Barbatos (P-Bandai Clear Color)", "Iron-Blooded Orphans", "P-Bandai", "mid", 85),
        ("MG 1/100", "Tallgeese II (Premium Bandai)", "Gundam Wing", "P-Bandai", "mid", 80),
        ("PG 1/60", "Unleashed Strike Freedom Gundam (Clear Armor)", "Gundam SEED Destiny", "P-Bandai", "grail", 450),
        ("PG 1/60", "RX-0 Unicorn Gundam 03 Phenex (Gold Coating)", "Gundam Unicorn", "P-Bandai", "grail", 520),
        ("MG 1/100", "Gundam Deathscythe Hell EW (Roussette Unit)", "Gundam Wing EW", "P-Bandai", "mid", 90),
        ("MG 1/100", "Hi-Nu Gundam Ver.Ka (Premium Decal)", "Gundam CCA", "P-Bandai", "mid", 95),
    ]


def _additional_shf_naruto_op() -> list[tuple]:
    """S.H.Figuarts — Naruto & One Piece expanded."""
    return [
        ("S.H.Figuarts", "Naruto Uzumaki Sage Mode", "Naruto Shippuden", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Sasuke Uchiha (Boruto)", "Boruto", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Pain Tendo", "Naruto Shippuden", "Standard", "mid", 75),
        ("S.H.Figuarts", "Obito Uchiha", "Naruto Shippuden", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "Gaara (Kazekage)", "Naruto Shippuden", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Madara Uchiha Edo Tensei", "Naruto Shippuden", "P-Bandai", "high", 120),
        ("S.H.Figuarts", "Hinata Hyuga", "Naruto Shippuden", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Rock Lee", "Naruto", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Sanji -Wano Kuni-", "One Piece", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Nico Robin -Wano Kuni-", "One Piece", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Trafalgar Law -Wano Kuni-", "One Piece", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Yamato", "One Piece", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "Nami -Wano Kuni-", "One Piece", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Shanks", "One Piece", "Standard", "mid", 75),
        ("S.H.Figuarts", "Franky -Wano Kuni-", "One Piece", "P-Bandai", "mid", 90),
    ]


def _additional_shf_db_complete() -> list[tuple]:
    """S.H.Figuarts — Dragon Ball complete roster expansion."""
    return [
        ("S.H.Figuarts", "Frieza Final Form (Resurrection F)", "Dragon Ball Z", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Son Gohan Teen (Cell Saga)", "Dragon Ball Z", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "Future Trunks Super Saiyan", "Dragon Ball Z", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Piccolo Daimao (King Piccolo)", "Dragon Ball", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Android 17 (Universe Survival)", "Dragon Ball Super", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Android 18 (Universe Survival)", "Dragon Ball Super", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Master Roshi (MAX Power)", "Dragon Ball", "P-Bandai", "mid", 75),
        ("S.H.Figuarts", "Yamcha (Earth's Foremost Fighter)", "Dragon Ball Z", "P-Bandai", "mid", 70),
        ("S.H.Figuarts", "Bulma (Adventure Begins)", "Dragon Ball", "Standard", "mid", 65),
        ("S.H.Figuarts", "Cell First Form", "Dragon Ball Z", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Nappa", "Dragon Ball Z", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Raditz", "Dragon Ball Z", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Son Goku (A Saiyan Raised On Earth)", "Dragon Ball Z", "Standard", "mid", 70),
        ("S.H.Figuarts", "Cooler Final Form", "Dragon Ball Z", "P-Bandai", "high", 110),
        ("S.H.Figuarts", "Turles", "Dragon Ball Z", "P-Bandai", "mid", 95),
    ]


def _additional_shf_kamen_rider_heisei() -> list[tuple]:
    """S.H.Figuarts — Kamen Rider Heisei era expansion."""
    return [
        ("S.H.Figuarts", "Kamen Rider Ryuki", "Kamen Rider Ryuki", "Standard", "mid", 70),
        ("S.H.Figuarts", "Kamen Rider Knight", "Kamen Rider Ryuki", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Kamen Rider Blade King Form", "Kamen Rider Blade", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Kamen Rider Hibiki", "Kamen Rider Hibiki", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "Kamen Rider Kabuto Hyper Form", "Kamen Rider Kabuto", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "Kamen Rider Den-O Sword Form", "Kamen Rider Den-O", "Standard", "mid", 70),
        ("S.H.Figuarts", "Kamen Rider Kiva Emperor Form", "Kamen Rider Kiva", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Kamen Rider Fourze Base States", "Kamen Rider Fourze", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Kamen Rider Wizard Flame Style", "Kamen Rider Wizard", "P-Bandai", "mid", 75),
        ("S.H.Figuarts", "Kamen Rider Gaim Orange Arms", "Kamen Rider Gaim", "Standard", "mid", 70),
        ("S.H.Figuarts", "Kamen Rider Drive Type Speed", "Kamen Rider Drive", "Standard", "mid", 70),
        ("S.H.Figuarts", "Kamen Rider Ghost Ore Damashii", "Kamen Rider Ghost", "P-Bandai", "mid", 75),
        ("S.H.Figuarts", "Kamen Rider Ichigo (Shin Kamen Rider)", "Shin Kamen Rider", "Standard", "mid", 75),
        ("S.H.Figuarts", "Kamen Rider Nigo (Shin Kamen Rider)", "Shin Kamen Rider", "P-Bandai", "mid", 85),
    ]


def _additional_shf_kamen_rider_showa() -> list[tuple]:
    """S.H.Figuarts — Kamen Rider Showa era."""
    return [
        ("S.H.Figuarts", "Kamen Rider Ichigo (Original 1971)", "Kamen Rider", "P-Bandai", "high", 120),
        ("S.H.Figuarts", "Kamen Rider Nigo (Original)", "Kamen Rider", "P-Bandai", "high", 110),
        ("S.H.Figuarts", "Kamen Rider V3", "Kamen Rider V3", "P-Bandai", "high", 100),
        ("S.H.Figuarts", "Kamen Rider Amazon", "Kamen Rider Amazon", "P-Bandai", "high", 110),
        ("S.H.Figuarts", "Kamen Rider Stronger", "Kamen Rider Stronger", "P-Bandai", "high", 100),
        ("S.H.Figuarts", "Kamen Rider Black", "Kamen Rider Black", "Standard", "mid", 80),
        ("S.H.Figuarts", "Kamen Rider Black RX", "Kamen Rider Black RX", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Kamen Rider Super-1", "Kamen Rider Super-1", "P-Bandai", "high", 110),
    ]


def _additional_sentai_expanded() -> list[tuple]:
    """S.H.Figuarts — Super Sentai expanded."""
    return [
        ("S.H.Figuarts", "Aka Ranger", "Super Sentai Gorenger", "P-Bandai", "high", 110),
        ("S.H.Figuarts", "GaoRed", "Super Sentai Gaoranger", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "MagiRed", "Super Sentai Magiranger", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Shinken Red", "Super Sentai Shinkenger", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Gokai Red", "Super Sentai Gokaiger", "Standard", "mid", 75),
        ("S.H.Figuarts", "Gokai Silver", "Super Sentai Gokaiger", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "Red Buster", "Super Sentai Go-Busters", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Zyuoh Eagle", "Super Sentai Zyuohger", "Standard", "mid", 70),
        ("S.H.Figuarts", "Don Momotaro", "Super Sentai DonBrothers", "Standard", "mid", 70),
        ("S.H.Figuarts", "King-Ohger Kuwagata Ohger", "Super Sentai King-Ohger", "Standard", "mid", 70),
    ]


def _additional_ultraman_expanded() -> list[tuple]:
    """S.H.Figuarts & Ultra-Act — Ultraman expanded."""
    return [
        ("S.H.Figuarts", "Ultraman Jack", "Return of Ultraman", "P-Bandai", "mid", 75),
        ("S.H.Figuarts", "Ultraman Leo", "Ultraman Leo", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Ultraman 80", "Ultraman 80", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Ultraman Geed Primitive", "Ultraman Geed", "Standard", "mid", 65),
        ("S.H.Figuarts", "Ultraman Z Original", "Ultraman Z", "Standard", "mid", 65),
        ("S.H.Figuarts", "Ultraman Regulos", "Ultra Galaxy Fight", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Ultraseven", "Ultraseven", "Standard", "mid", 75),
        ("Ultra-Act", "Ultraman Taro", "Ultraman Taro", "P-Bandai", "high", 140),
        ("Ultra-Act", "Ultraman Zero Ultimate Shining", "Ultraman Zero", "P-Bandai", "high", 155),
        ("S.H.Figuarts", "Ultraman Cosmos Luna Mode", "Ultraman Cosmos", "P-Bandai", "mid", 80),
    ]


def _additional_robot_spirits_eva() -> list[tuple]:
    """Robot Spirits — Evangelion expanded."""
    return [
        ("Robot Spirits", "EVA Unit-00 Prototype", "Evangelion", "Standard", "mid", 65),
        ("Robot Spirits", "EVA Unit-02 Beast Mode Second Awakening", "Evangelion 3.0+1.0", "P-Bandai", "high", 120),
        ("Robot Spirits", "EVA Unit-08 Beta (ICC)", "Evangelion 3.0+1.0", "P-Bandai", "mid", 95),
        ("Robot Spirits", "EVA Mark.06", "Evangelion 2.0", "P-Bandai", "mid", 90),
        ("Robot Spirits", "EVA Unit-03", "Evangelion", "P-Bandai", "mid", 85),
        ("Robot Spirits", "EVA Unit-01 (Night Combat Ver.)", "Evangelion", "P-Bandai", "mid", 90),
    ]


def _additional_robot_spirits_gundam_uc() -> list[tuple]:
    """Robot Spirits — Gundam Universal Century expanded."""
    return [
        ("Robot Spirits", "Zeta Gundam ver. A.N.I.M.E.", "Zeta Gundam", "Standard", "mid", 85),
        ("Robot Spirits", "ZZ Gundam ver. A.N.I.M.E.", "Gundam ZZ", "P-Bandai", "high", 110),
        ("Robot Spirits", "Hyaku Shiki ver. A.N.I.M.E.", "Zeta Gundam", "Standard", "mid", 80),
        ("Robot Spirits", "The-O ver. A.N.I.M.E.", "Zeta Gundam", "P-Bandai", "high", 130),
        ("Robot Spirits", "Qubeley ver. A.N.I.M.E.", "Zeta Gundam", "Standard", "mid", 85),
        ("Robot Spirits", "Rick Dias ver. A.N.I.M.E.", "Zeta Gundam", "P-Bandai", "mid", 80),
        ("Robot Spirits", "Gelgoog Commander ver. A.N.I.M.E.", "Mobile Suit Gundam", "P-Bandai", "mid", 75),
        ("Robot Spirits", "Gouf Custom ver. A.N.I.M.E.", "08th MS Team", "P-Bandai", "mid", 80),
        ("Robot Spirits", "Ez-8 ver. A.N.I.M.E.", "08th MS Team", "P-Bandai", "mid", 85),
        ("Robot Spirits", "Dom Tropen ver. A.N.I.M.E.", "Gundam 0083", "P-Bandai", "mid", 75),
        ("Robot Spirits", "GP-01 Zephyranthes ver. A.N.I.M.E.", "Gundam 0083", "P-Bandai", "mid", 85),
        ("Robot Spirits", "GP-02 Physalis ver. A.N.I.M.E.", "Gundam 0083", "P-Bandai", "high", 110),
        ("Robot Spirits", "Jegan ver. A.N.I.M.E.", "Gundam CCA", "P-Bandai", "mid", 70),
        ("Robot Spirits", "Kshatriya ver. A.N.I.M.E.", "Gundam Unicorn", "P-Bandai", "high", 130),
        ("Robot Spirits", "Sinanju ver. A.N.I.M.E.", "Gundam Unicorn", "Standard", "mid", 90),
    ]


def _additional_robot_spirits_wfm() -> list[tuple]:
    """Robot Spirits — Gundam Witch from Mercury & IBO."""
    return [
        ("Robot Spirits", "Gundam Aerial ver. A.N.I.M.E.", "Gundam: Witch from Mercury", "Standard", "mid", 70),
        ("Robot Spirits", "Gundam Pharact ver. A.N.I.M.E.", "Gundam: Witch from Mercury", "P-Bandai", "mid", 80),
        ("Robot Spirits", "Gundam Lfrith ver. A.N.I.M.E.", "Gundam: Witch from Mercury", "P-Bandai", "mid", 75),
        ("Robot Spirits", "Darilbalde ver. A.N.I.M.E.", "Gundam: Witch from Mercury", "P-Bandai", "mid", 85),
        ("Robot Spirits", "Gundam Calibarn ver. A.N.I.M.E.", "Gundam: Witch from Mercury", "P-Bandai", "mid", 90),
        ("Robot Spirits", "Gundam Barbatos ver. A.N.I.M.E.", "Iron-Blooded Orphans", "Standard", "mid", 70),
        ("Robot Spirits", "Gusion Rebake Full City ver. A.N.I.M.E.", "Iron-Blooded Orphans", "P-Bandai", "mid", 85),
        ("Robot Spirits", "Bael ver. A.N.I.M.E.", "Iron-Blooded Orphans", "P-Bandai", "mid", 80),
        ("Robot Spirits", "Vidar ver. A.N.I.M.E.", "Iron-Blooded Orphans", "P-Bandai", "mid", 85),
    ]


def _additional_figure_rise() -> list[tuple]:
    """Figure-rise Standard — model kits with figure quality."""
    return [
        ("Figure-rise Standard", "Son Goku (Ultra Instinct)", "Dragon Ball Super", "P-Bandai", "mid", 50),
        ("Figure-rise Standard", "Vegeta (Super Saiyan God)", "Dragon Ball Super", "P-Bandai", "mid", 45),
        ("Figure-rise Standard", "Kamen Rider W CycloneJoker", "Kamen Rider W", "Standard", "mid", 40),
        ("Figure-rise Standard", "Kamen Rider Build RabbitTank", "Kamen Rider Build", "Standard", "mid", 40),
        ("Figure-rise Standard", "Ultraman Suit Ver. 7.5", "Ultraman", "Standard", "mid", 45),
        ("Figure-rise Standard", "Amplified Imperialdramon", "Digimon", "Standard", "mid", 55),
        ("Figure-rise Standard", "Amplified WarGreymon", "Digimon", "Standard", "mid", 50),
        ("Figure-rise Standard", "Amplified MetalGarurumon", "Digimon", "Standard", "mid", 50),
        ("Figure-rise Standard", "Amplified BlackWarGreymon", "Digimon", "P-Bandai", "mid", 60),
        ("Figure-rise Standard", "Liger Zero", "Zoids", "Standard", "mid", 55),
    ]


def _additional_pbandai_hg_expanded() -> list[tuple]:
    """HG P-Bandai exclusive kits — expanded."""
    return [
        ("HG 1/144", "Moon Gundam", "Gundam Moon", "P-Bandai", "mid", 55),
        ("HG 1/144", "Gundam G-Self Perfect Pack", "Gundam Reconguista", "P-Bandai", "mid", 50),
        ("HG 1/144", "Barzam", "Zeta Gundam", "P-Bandai", "mid", 40),
        ("HG 1/144", "Byarlant Custom", "Gundam Unicorn", "P-Bandai", "mid", 45),
        ("HG 1/144", "Dijeh", "Zeta Gundam", "P-Bandai", "mid", 45),
        ("HG 1/144", "Methuss", "Zeta Gundam", "P-Bandai", "mid", 40),
        ("HG 1/144", "Gundam TR-1 Hazel Custom", "Advance of Zeta", "P-Bandai", "mid", 55),
        ("HG 1/144", "Galbaldy Beta", "Zeta Gundam", "P-Bandai", "mid", 40),
        ("HG 1/144", "Gaza-C (Haman Custom)", "Zeta Gundam", "P-Bandai", "mid", 45),
        ("HG 1/144", "Pale Rider (Space Type)", "Missing Link", "P-Bandai", "mid", 50),
        ("HG 1/144", "Gustav Karl (Unicorn Ver.)", "Gundam Unicorn", "P-Bandai", "mid", 40),
        ("HG 1/144", "Silver Bullet Suppressor", "Gundam NT", "P-Bandai", "mid", 45),
    ]


def _additional_mg_expanded() -> list[tuple]:
    """MG 1/100 P-Bandai — expanded catalog."""
    return [
        ("MG 1/100", "Gundam Heavyarms Custom EW", "Gundam Wing EW", "P-Bandai", "mid", 80),
        ("MG 1/100", "Gundam Nataku EW (Shenlong)", "Gundam Wing EW", "P-Bandai", "mid", 80),
        ("MG 1/100", "GM Sniper II", "Gundam 0080", "P-Bandai", "mid", 75),
        ("MG 1/100", "Geara Doga", "Gundam CCA", "P-Bandai", "mid", 80),
        ("MG 1/100", "Full Armor Gundam (Thunderbolt)", "Gundam Thunderbolt", "Standard", "mid", 85),
        ("MG 1/100", "Psycho Zaku (Thunderbolt)", "Gundam Thunderbolt", "Standard", "high", 110),
        ("MG 1/100", "Providence Gundam (Premium Edition)", "Gundam SEED", "P-Bandai", "mid", 90),
        ("MG 1/100", "Blaze Zaku Phantom (Rey Za Burrel)", "Gundam SEED Destiny", "P-Bandai", "mid", 80),
        ("MG 1/100", "Eclipse Gundam", "Gundam SEED Eclipse", "P-Bandai", "mid", 85),
        ("MG 1/100", "Gundam AGE-2 Dark Hound", "Gundam AGE", "P-Bandai", "mid", 75),
    ]


def _additional_shf_misc_anime() -> list[tuple]:
    """S.H.Figuarts — misc anime & tokusatsu."""
    return [
        ("S.H.Figuarts", "Tanjiro Kamado", "Demon Slayer", "Standard", "mid", 65),
        ("S.H.Figuarts", "Rengoku Kyojuro", "Demon Slayer", "Standard", "mid", 70),
        ("S.H.Figuarts", "Zenitsu Agatsuma", "Demon Slayer", "Standard", "mid", 65),
        ("S.H.Figuarts", "Inosuke Hashibira", "Demon Slayer", "Standard", "mid", 65),
        ("S.H.Figuarts", "Tengen Uzui", "Demon Slayer", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Gojo Satoru", "Jujutsu Kaisen", "Standard", "mid", 75),
        ("S.H.Figuarts", "Itadori Yuji", "Jujutsu Kaisen", "Standard", "mid", 70),
        ("S.H.Figuarts", "Fushiguro Megumi", "Jujutsu Kaisen", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Denji (Chainsaw Man Form)", "Chainsaw Man", "Standard", "mid", 75),
        ("S.H.Figuarts", "Power", "Chainsaw Man", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Anya Forger", "Spy x Family", "Standard", "mid", 60),
        ("S.H.Figuarts", "Loid Forger", "Spy x Family", "P-Bandai", "mid", 75),
    ]


def _additional_dx_chogokin_expanded() -> list[tuple]:
    """DX Chogokin — more Macross Valkyries."""
    return [
        ("DX Chogokin", "VF-1A Valkyrie (Hikaru Ichijo)", "Macross", "P-Bandai", "high", 250),
        ("DX Chogokin", "VF-1S Super Parts Set (Roy Focker)", "Macross", "P-Bandai", "high", 150),
        ("DX Chogokin", "VF-1J Armored Valkyrie", "Macross", "P-Bandai", "high", 280),
        ("DX Chogokin", "VF-25S Messiah Valkyrie (Ozma Lee)", "Macross Frontier", "P-Bandai", "high", 270),
        ("DX Chogokin", "VF-27 Lucifer Valkyrie (Grace O'Connor)", "Macross Frontier", "P-Bandai", "high", 260),
        ("DX Chogokin", "VF-31AX Kairos Plus (Hayate Custom)", "Macross Delta", "P-Bandai", "high", 290),
        ("DX Chogokin", "VF-31S Siegfried (Arad Molders)", "Macross Delta", "P-Bandai", "high", 250),
        ("DX Chogokin", "YF-19 Full Set Pack", "Macross Plus", "P-Bandai", "grail", 350),
        ("DX Chogokin", "YF-21", "Macross Plus", "P-Bandai", "high", 300),
    ]


def _additional_soul_chogokin_expanded() -> list[tuple]:
    """Soul of Chogokin — more classic super robot."""
    return [
        ("Soul of Chogokin", "GX-85 King Brachion", "Super Sentai Zyuranger", "Standard", "high", 280),
        ("Soul of Chogokin", "GX-88 Dairugger XV", "Armored Fleet Dairugger XV", "Standard", "high", 260),
        ("Soul of Chogokin", "GX-68 GaoGaiGar", "GaoGaiGar", "Standard", "high", 250),
        ("Soul of Chogokin", "GX-69 Goldion Hammer", "GaoGaiGar", "Standard", "high", 200),
        ("Soul of Chogokin", "GX-82 Muteki Shogun", "Super Sentai Kakuranger", "Standard", "high", 240),
        ("Soul of Chogokin", "GX-86 King of Braves GaoGaiGar", "GaoGaiGar", "Standard", "grail", 350),
        ("Soul of Chogokin", "GX-75 Mazinkaiser", "Mazinkaiser", "Standard", "high", 220),
        ("Soul of Chogokin", "GX-99 Getter Arc", "Getter Robo Arc", "Standard", "high", 230),
        ("Soul of Chogokin", "GX-04S UFO Robot Grendizer & Spazer", "UFO Robot Grendizer", "P-Bandai", "grail", 350),
        ("Soul of Chogokin", "GX-91 Getter 2&3 D.C.", "Getter Robo", "Standard", "high", 200),
    ]


def _additional_metal_robot_spirits() -> list[tuple]:
    """Metal Robot Spirits — premium metal die-cast figures."""
    return [
        ("Metal Robot Spirits", "Freedom Gundam", "Gundam SEED", "Standard", "high", 200),
        ("Metal Robot Spirits", "Strike Freedom Gundam", "Gundam SEED Destiny", "Standard", "high", 220),
        ("Metal Robot Spirits", "Destiny Gundam", "Gundam SEED Destiny", "P-Bandai", "high", 210),
        ("Metal Robot Spirits", "Wing Gundam Zero (EW)", "Gundam Wing EW", "Standard", "high", 180),
        ("Metal Robot Spirits", "Tallgeese III", "Gundam Wing EW", "P-Bandai", "high", 190),
        ("Metal Robot Spirits", "00 Raiser + GN Sword III", "Gundam 00", "Standard", "high", 200),
        ("Metal Robot Spirits", "Qan[T] Full Saber", "Gundam 00 Movie", "P-Bandai", "high", 220),
        ("Metal Robot Spirits", "Nu Gundam", "Gundam CCA", "Standard", "high", 200),
        ("Metal Robot Spirits", "Sazabi", "Gundam CCA", "P-Bandai", "high", 210),
        ("Metal Robot Spirits", "Gundam Barbatos Lupus Rex", "Iron-Blooded Orphans", "P-Bandai", "high", 190),
        ("Metal Robot Spirits", "Providence Gundam", "Gundam SEED", "P-Bandai", "high", 200),
        ("Metal Robot Spirits", "Knight Gundam (Real Type)", "SD Gundam", "P-Bandai", "high", 180),
    ]


def _additional_rg_expanded() -> list[tuple]:
    """RG 1/144 P-Bandai exclusive kits — expanded."""
    return [
        ("RG 1/144", "Tallgeese II", "Gundam Wing", "P-Bandai", "mid", 55),
        ("RG 1/144", "Tallgeese III", "Gundam Wing EW", "P-Bandai", "mid", 60),
        ("RG 1/144", "Zeta Gundam (Biosensor Image Color)", "Zeta Gundam", "P-Bandai", "mid", 65),
        ("RG 1/144", "Full Burnern", "Gundam 0083", "P-Bandai", "mid", 60),
        ("RG 1/144", "Nu Gundam HWS (Heavy Weapon System)", "Gundam CCA", "P-Bandai", "mid", 80),
        ("RG 1/144", "Hi-Nu Gundam", "Gundam CCA", "Standard", "mid", 65),
        ("RG 1/144", "Zeong", "Mobile Suit Gundam", "Standard", "mid", 70),
        ("RG 1/144", "Wing Gundam", "Gundam Wing", "Standard", "mid", 40),
        ("RG 1/144", "God Gundam", "G Gundam", "Standard", "mid", 50),
        ("RG 1/144", "Impulse Gundam (Force Silhouette)", "Gundam SEED Destiny", "P-Bandai", "mid", 55),
        ("RG 1/144", "Justice Gundam", "Gundam SEED", "P-Bandai", "mid", 55),
        ("RG 1/144", "Gundam Mk-II (AEUG) (Premium Bandai)", "Zeta Gundam", "P-Bandai", "mid", 55),
    ]


def _additional_pg_expanded() -> list[tuple]:
    """PG 1/60 — premium grade expanded."""
    return [
        ("PG 1/60", "Unicorn Gundam (Full Armor Equipment)", "Gundam Unicorn", "P-Bandai", "grail", 500),
        ("PG 1/60", "Zeta Gundam", "Zeta Gundam", "Standard", "grail", 350),
        ("PG 1/60", "Strike Freedom Gundam", "Gundam SEED Destiny", "Standard", "grail", 380),
        ("PG 1/60", "Exia (Lighting Model)", "Gundam 00", "Standard", "grail", 400),
        ("PG 1/60", "Wing Gundam Zero (EW) Pearl Mirror Coating", "Gundam Wing EW", "P-Bandai", "grail", 450),
        ("PG 1/60", "Char's Zaku II (Premium Bandai)", "Mobile Suit Gundam", "P-Bandai", "grail", 350),
    ]


def _additional_shf_dbgt_movies() -> list[tuple]:
    """S.H.Figuarts — Dragon Ball GT & Movies expansion."""
    return [
        ("S.H.Figuarts", "Son Goku SSJ4", "Dragon Ball GT", "Standard", "mid", 80),
        ("S.H.Figuarts", "Vegeta SSJ4", "Dragon Ball GT", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Gogeta SSJ4", "Dragon Ball GT", "P-Bandai", "high", 120),
        ("S.H.Figuarts", "Super Baby 2", "Dragon Ball GT", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Pan", "Dragon Ball GT", "P-Bandai", "mid", 70),
        ("S.H.Figuarts", "Broly (DBZ Movie)", "Dragon Ball Z", "P-Bandai", "high", 110),
        ("S.H.Figuarts", "Super Saiyan Vegito", "Dragon Ball Z", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Beerus", "Dragon Ball Super", "Standard", "mid", 75),
        ("S.H.Figuarts", "Whis", "Dragon Ball Super", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Hit", "Dragon Ball Super", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "Jiren", "Dragon Ball Super", "Standard", "mid", 75),
        ("S.H.Figuarts", "Zamasu (Fused)", "Dragon Ball Super", "P-Bandai", "high", 110),
    ]


def _additional_figuarts_zero_op() -> list[tuple]:
    """Figuarts ZERO — More One Piece Extra Battle."""
    return [
        ("Figuarts ZERO", "Jinbe -Knight of the Sea-", "One Piece", "Standard", "mid", 85),
        ("Figuarts ZERO", "Sabo -Fire Fist Inheritance-", "One Piece", "Standard", "mid", 90),
        ("Figuarts ZERO", "Marco The Phoenix", "One Piece", "P-Bandai", "mid", 95),
        ("Figuarts ZERO", "Donquixote Doflamingo -Overheat-", "One Piece", "Standard", "mid", 90),
        ("Figuarts ZERO", "Eustass Kid -Punk Gibson-", "One Piece", "P-Bandai", "mid", 85),
        ("Figuarts ZERO", "Kozuki Oden -Paradise Totsuka-", "One Piece", "Standard", "mid", 100),
        ("Figuarts ZERO", "Whitebeard -Last Captain-", "One Piece", "Standard", "high", 130),
        ("Figuarts ZERO", "Monkey D. Luffy -Bound Man- King Cobra", "One Piece", "Standard", "high", 120),
        ("Figuarts ZERO", "Katakuri -Mochi Tsuki-", "One Piece", "Standard", "mid", 95),
        ("Figuarts ZERO", "Boa Hancock -Love Hurricane-", "One Piece", "P-Bandai", "mid", 85),
    ]


def _additional_gunpla_special() -> list[tuple]:
    """Special Gunpla — MGEX, Full Mechanics, RE/100."""
    return [
        ("MGEX 1/100", "Unicorn Gundam Ver.Ka (MGEX)", "Gundam Unicorn", "Standard", "grail", 320),
        ("MGEX 1/100", "Strike Freedom Gundam (MGEX)", "Gundam SEED Destiny", "Standard", "grail", 350),
        ("Full Mechanics 1/100", "Gundam Aerial", "Gundam: Witch from Mercury", "Standard", "mid", 55),
        ("Full Mechanics 1/100", "Gundam Barbatos Lupus Rex", "Iron-Blooded Orphans", "Standard", "mid", 50),
        ("Full Mechanics 1/100", "Calamity Gundam", "Gundam SEED", "Standard", "mid", 50),
        ("RE/100 1/100", "Vigna Ghina", "Crossbone Gundam", "P-Bandai", "mid", 60),
        ("RE/100 1/100", "Hamma Hamma", "Gundam ZZ", "P-Bandai", "mid", 55),
        ("RE/100 1/100", "Nightingale", "Gundam CCA-MSV", "Standard", "mid", 70),
    ]


def _additional_shf_tokusatsu_misc() -> list[tuple]:
    """S.H.Figuarts — Additional tokusatsu & misc lines."""
    return [
        ("S.H.Figuarts", "Kamen Rider Geats IX (Desire Grand Prix)", "Kamen Rider Geats", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Kamen Rider Gotchard (Fire Form)", "Kamen Rider Gotchard", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Kamen Rider Gavv", "Kamen Rider Gavv", "Standard", "mid", 70),
        ("S.H.Figuarts", "Kamen Rider OOO TaJaDor Combo Eternity", "Kamen Rider OOO", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "SSSS.GRIDMAN", "SSSS.GRIDMAN", "Standard", "mid", 75),
        ("S.H.Figuarts", "SSSS.DYNAZENON", "SSSS.DYNAZENON", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Ultraman Arc", "Ultraman Arc", "Standard", "mid", 65),
        ("S.H.Figuarts", "Kamen Rider Agito Storm Form", "Kamen Rider Agito", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Kamen Rider Agito Burning Form", "Kamen Rider Agito", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "Kamen Rider Faiz Axel Form", "Kamen Rider 555", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Kamen Rider Double HeatMetal", "Kamen Rider W", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Kamen Rider Double LunaTrigger", "Kamen Rider W", "P-Bandai", "mid", 80),
    ]


def _additional_tamashii_event_expanded() -> list[tuple]:
    """Tamashii Nations event exclusives — expanded."""
    return [
        ("S.H.Figuarts", "Cell (1st Form) TNE 2024", "Dragon Ball Z", "TNE", "high", 160),
        ("S.H.Figuarts", "Kamen Rider Decade Neo Decade Driver (TNE)", "Kamen Rider Decade", "TNE", "high", 140),
        ("Metal Build", "Destiny Gundam (Heine) TNT 2024 Color", "Gundam SEED Destiny", "Event Exclusive", "grail", 450),
        ("Robot Spirits", "Sazabi ver. A.N.I.M.E. (Pearl Coating TNE)", "Gundam CCA", "TNE", "high", 160),
        ("S.H.Figuarts", "Ultraman Tiga (Glitter Tiga) TNE", "Ultraman Tiga", "TNE", "high", 130),
        ("Figuarts ZERO", "Luffy Gear 5 (TNE 2024 White Ver.)", "One Piece", "TNE", "high", 180),
        ("Metal Build", "Crossbone X1 (SDCC 2023)", "Crossbone Gundam", "Event Exclusive", "grail", 380),
        ("S.H.Figuarts", "Frieza (1st Form) Full Power (SDCC)", "Dragon Ball Z", "Event Exclusive", "high", 170),
        ("Robot Spirits", "Turn A Gundam ver. A.N.I.M.E. (TNE)", "Turn A Gundam", "TNE", "high", 140),
        ("S.H.Figuarts", "Gokai Red 10th Anniversary (TNE)", "Super Sentai Gokaiger", "TNE", "high", 130),
    ]


def _additional_metal_build_more() -> list[tuple]:
    """Metal Build — more premium figures."""
    return [
        ("Metal Build", "00 Gundam Seven Sword/G", "Gundam 00", "P-Bandai", "high", 300),
        ("Metal Build", "Gundam Dynames Repair III", "Gundam 00", "P-Bandai", "high", 280),
        ("Metal Build", "Gundam Kyrios", "Gundam 00", "P-Bandai", "high", 270),
        ("Metal Build", "Infinite Justice Gundam", "Gundam SEED Destiny", "Standard", "high", 280),
        ("Metal Build", "Providence Gundam", "Gundam SEED", "P-Bandai", "grail", 380),
        ("Metal Build", "Gundam F91 Chronicle White", "Gundam F91", "P-Bandai", "high", 300),
        ("Metal Build", "Crossbone Gundam X3", "Crossbone Gundam", "P-Bandai", "high", 290),
        ("Metal Build", "Gundam Seed Astray Gold Frame Amatsu Mina", "Gundam SEED Astray", "P-Bandai", "grail", 420),
        ("Metal Build", "EVA Unit-01 (Metal Build)", "Evangelion", "Standard", "grail", 350),
        ("Metal Build", "EVA Unit-02 (Metal Build)", "Evangelion", "P-Bandai", "grail", 380),
    ]


def _additional_miscellaneous_bandai() -> list[tuple]:
    """Miscellaneous Bandai Premium lines — Proplica, S.H.MonsterArts."""
    return [
        ("Proplica", "Tanjiro Nichirin Blade (1/1)", "Demon Slayer", "Standard", "high", 120),
        ("Proplica", "Rengoku Nichirin Blade (1/1)", "Demon Slayer", "P-Bandai", "high", 130),
        ("Proplica", "Moon Stick (Sailor Moon)", "Sailor Moon", "Standard", "mid", 85),
        ("Proplica", "Crisis Moon Compact (Sailor Moon)", "Sailor Moon", "P-Bandai", "mid", 95),
        ("Proplica", "Zanpakuto Tensa Zangetsu", "Bleach", "P-Bandai", "high", 140),
        ("S.H.MonsterArts", "Godzilla (2023 Minus One)", "Godzilla Minus One", "Standard", "high", 130),
        ("S.H.MonsterArts", "Godzilla (2019 King of the Monsters)", "Godzilla", "Standard", "high", 150),
        ("S.H.MonsterArts", "King Ghidorah (2019)", "Godzilla", "Standard", "grail", 350),
        ("S.H.MonsterArts", "Mechagodzilla (2021)", "Godzilla vs Kong", "Standard", "high", 160),
        ("S.H.MonsterArts", "Godzilla Ultima", "Godzilla Singular Point", "P-Bandai", "high", 120),
        ("S.H.MonsterArts", "Kong (2021)", "Godzilla vs Kong", "Standard", "high", 130),
        ("S.H.MonsterArts", "Destoroyah", "Godzilla vs Destoroyah", "Standard", "grail", 300),
        ("S.H.MonsterArts", "Biollante", "Godzilla vs Biollante", "Standard", "grail", 350),
        ("S.H.MonsterArts", "Space Godzilla", "Godzilla vs SpaceGodzilla", "P-Bandai", "high", 200),
        ("S.H.MonsterArts", "Shin Godzilla 4th Form", "Shin Godzilla", "Standard", "high", 180),
        ("S.H.MonsterArts", "Godzilla Terrestris", "Godzilla Singular Point", "P-Bandai", "high", 140),
        ("Proplica", "Dragon Radar (Dragon Ball)", "Dragon Ball", "Standard", "mid", 60),
        ("Proplica", "Sailor Moon Eternal Tiare", "Sailor Moon", "P-Bandai", "mid", 100),
    ]


def _additional_csm_proplica_sailor() -> list[tuple]:
    """CSM belt replicas, Proplica prop replicas, Sailor Moon line."""
    return [
        # Complete Selection Modification (CSM) — Kamen Rider belt replicas
        ("CSM", "Decadriver (Kamen Rider Decade)", "Kamen Rider Decade", "P-Bandai", "grail", 380),
        ("CSM", "Faizdriver (Kamen Rider 555)", "Kamen Rider 555", "P-Bandai", "grail", 350),
        ("CSM", "OOO Driver Complete Set", "Kamen Rider OOO", "P-Bandai", "grail", 400),
        ("CSM", "Double Driver (Ver. 1.5)", "Kamen Rider W", "P-Bandai", "grail", 380),
        ("CSM", "Fourze Driver", "Kamen Rider Fourze", "P-Bandai", "grail", 350),
        ("CSM", "Gamer Driver (Kamen Rider Ex-Aid)", "Kamen Rider Ex-Aid", "P-Bandai", "grail", 360),
        ("CSM", "Sengoku Driver (Kamen Rider Gaim)", "Kamen Rider Gaim", "P-Bandai", "grail", 370),
        ("CSM", "Arcle (Kamen Rider Kuuga)", "Kamen Rider Kuuga", "P-Bandai", "grail", 400),
        ("CSM", "V-Buckle & Dragvisor (Kamen Rider Ryuki)", "Kamen Rider Ryuki", "P-Bandai", "grail", 380),
        ("CSM", "Henshin Belt Typhoon (Kamen Rider Ichigo)", "Kamen Rider", "P-Bandai", "grail", 420),
        ("CSM", "Build Driver", "Kamen Rider Build", "P-Bandai", "grail", 340),
        ("CSM", "Ziku-Driver (Kamen Rider Zi-O)", "Kamen Rider Zi-O", "P-Bandai", "grail", 350),

        # Proplica — prop replicas
        ("Proplica", "Spiral Heart Moon Rod", "Sailor Moon S", "Standard", "high", 135),
        ("Proplica", "Kaleidomoon Scope", "Sailor Moon SuperS", "P-Bandai", "high", 150),
        ("Proplica", "Giyu Tomioka Nichirin Blade", "Demon Slayer", "P-Bandai", "high", 135),
        ("Proplica", "Inosuke Hashibira Nichirin Blades (Pair)", "Demon Slayer", "P-Bandai", "high", 160),
        ("Proplica", "Zenitsu Agatsuma Nichirin Blade", "Demon Slayer", "P-Bandai", "high", 130),
        ("Proplica", "Cosmic Heart Compact", "Sailor Moon S", "Standard", "high", 120),

        # S.H.Figuarts — Sailor Moon
        ("S.H.Figuarts", "Sailor Moon (Animation Color Edition)", "Sailor Moon", "Standard", "mid", 70),
        ("S.H.Figuarts", "Sailor Mercury (Animation Color Edition)", "Sailor Moon", "Standard", "mid", 65),
        ("S.H.Figuarts", "Sailor Mars (Animation Color Edition)", "Sailor Moon", "Standard", "mid", 65),
        ("S.H.Figuarts", "Sailor Jupiter (Animation Color Edition)", "Sailor Moon", "Standard", "mid", 65),
        ("S.H.Figuarts", "Sailor Venus (Animation Color Edition)", "Sailor Moon", "Standard", "mid", 65),
        ("S.H.Figuarts", "Super Sailor Moon", "Sailor Moon SuperS", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Sailor Saturn (Animation Color Edition)", "Sailor Moon S", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Sailor Uranus (Animation Color Edition)", "Sailor Moon S", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Sailor Neptune (Animation Color Edition)", "Sailor Moon S", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Sailor Pluto (Animation Color Edition)", "Sailor Moon S", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Tuxedo Mask (Animation Color Edition)", "Sailor Moon", "P-Bandai", "mid", 75),
        ("S.H.Figuarts", "Sailor Chibi Moon (Animation Color Edition)", "Sailor Moon SuperS", "P-Bandai", "mid", 70),
    ]


def _additional_sdcs_and_misc_kits() -> list[tuple]:
    """SD, Entry Grade, 30MM, and other Bandai kit lines."""
    return [
        ("SD Gundam EX-Standard", "Unicorn Gundam (Destroy Mode)", "Gundam Unicorn", "Standard", "standard", 15),
        ("SD Gundam EX-Standard", "Wing Gundam Zero (EW)", "Gundam Wing EW", "Standard", "standard", 15),
        ("SD Gundam Cross Silhouette", "RX-78-2 Gundam (Cross Silhouette)", "Mobile Suit Gundam", "Standard", "standard", 22),
        ("SD Gundam Cross Silhouette", "Zeta Gundam (Cross Silhouette)", "Zeta Gundam", "P-Bandai", "mid", 30),
        ("Entry Grade", "RX-78-2 Gundam (Entry Grade)", "Mobile Suit Gundam", "Standard", "standard", 10),
        ("Entry Grade", "Strike Gundam (Entry Grade)", "Gundam SEED", "Standard", "standard", 10),
        ("Entry Grade", "Lah Gundam (Entry Grade)", "Gundam Build Metaverse", "Standard", "standard", 12),
        ("30MM", "eEXM-17 Alto Green", "30 Minutes Missions", "Standard", "standard", 15),
        ("30MM", "eEXM-21 Rabiot White", "30 Minutes Missions", "Standard", "standard", 18),
        ("30MM", "Option Armor Commander Type (Portanova)", "30 Minutes Missions", "P-Bandai", "standard", 12),
        ("HG 1/144", "Gundam Calibarn", "Gundam: Witch from Mercury", "Standard", "mid", 35),
        ("HG 1/144", "Darilbalde", "Gundam: Witch from Mercury", "Standard", "mid", 30),
        ("HG 1/144", "Schwarzette", "Gundam: Witch from Mercury", "Standard", "mid", 30),
        ("HG 1/144", "Gundam Pharact", "Gundam: Witch from Mercury", "Standard", "mid", 30),
        ("HG 1/144", "Michaelis", "Gundam: Witch from Mercury", "Standard", "mid", 30),
        ("HG 1/144", "Beguir-Beu", "Gundam: Witch from Mercury", "P-Bandai", "mid", 40),
        ("HG 1/144", "Zowort Heavy", "Gundam: Witch from Mercury", "P-Bandai", "mid", 35),
        ("MG 1/100", "Gundam Aerial", "Gundam: Witch from Mercury", "Standard", "mid", 65),
        ("MG 1/100", "Freedom Gundam Ver.2.0", "Gundam SEED", "Standard", "mid", 55),
        ("MG 1/100", "Justice Gundam", "Gundam SEED", "Standard", "mid", 55),
    ]


def _additional_tamashii_2025_expansion() -> list[tuple]:
    """50 more: SHF Film Red/Naruto, CSM Kamen Rider, Ultra-Act, Robot Spirits Eva, Proplica."""
    return [
        # ── S.H.Figuarts — Dragon Ball Super Hero / Daima ──────────────────
        ("S.H.Figuarts", "Son Goku (Daima Mini Ver.)", "Dragon Ball Daima", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Vegeta (Daima Mini Ver.)", "Dragon Ball Daima", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Supreme Kai (Daima)", "Dragon Ball Daima", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Gomah (Daima)", "Dragon Ball Daima", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Son Gohan (Beast) Event Color", "Dragon Ball Super: Super Hero", "TNE", "high", 165),

        # ── S.H.Figuarts — Naruto Shippuden Expansion ─────────────────────
        ("S.H.Figuarts", "Uchiha Itachi -Anbu Black Ops-", "Naruto Shippuden", "P-Bandai", "high", 130),
        ("S.H.Figuarts", "Pain (Tendo/Deva Path) -Chibaku Tensei-", "Naruto Shippuden", "P-Bandai", "high", 140),
        ("S.H.Figuarts", "Uchiha Madara -Edo Tensei-", "Naruto Shippuden", "P-Bandai", "high", 135),
        ("S.H.Figuarts", "Hatake Kakashi -Anbu-", "Naruto Shippuden", "P-Bandai", "mid", 110),
        ("S.H.Figuarts", "Namikaze Minato -Yellow Flash-", "Naruto Shippuden", "P-Bandai", "high", 125),

        # ── S.H.Figuarts — One Piece Film Red ─────────────────────────────
        ("S.H.Figuarts", "Shanks (Film Red) Battle Ver.", "One Piece Film Red", "Standard", "mid", 90),
        ("S.H.Figuarts", "Uta (Film Red)", "One Piece Film Red", "P-Bandai", "mid", 100),
        ("S.H.Figuarts", "Monkey D. Luffy (Film Red)", "One Piece Film Red", "Standard", "mid", 85),
        ("Figuarts ZERO", "Uta -Concert Ver.- Extra Battle", "One Piece Film Red", "Standard", "mid", 110),

        # ── Complete Selection Modification (CSM) — Kamen Rider ────────────
        ("CSM", "Decadriver (Ver. 2)", "Kamen Rider Decade", "P-Bandai", "grail", 380),
        ("CSM", "Fourze Driver", "Kamen Rider Fourze", "P-Bandai", "grail", 350),
        ("CSM", "Build Driver", "Kamen Rider Build", "P-Bandai", "grail", 340),
        ("CSM", "Sengoku Driver (Gaim)", "Kamen Rider Gaim", "P-Bandai", "grail", 360),
        ("CSM", "Faiz Gear (Ver. 2)", "Kamen Rider 555", "P-Bandai", "grail", 400),
        ("CSM", "Kaixa Gear", "Kamen Rider 555", "P-Bandai", "grail", 380),
        ("CSM", "Gatack Zecter", "Kamen Rider Kabuto", "P-Bandai", "high", 280),
        ("CSM", "Lost Driver", "Kamen Rider W", "P-Bandai", "high", 260),
        ("CSM", "Buggle Driver II (God Maximum Gamer)", "Kamen Rider Ex-Aid", "P-Bandai", "high", 300),

        # ── Ultra-Act / S.H.Figuarts (Ultraman) ───────────────────────────
        ("S.H.Figuarts", "Ultraman Tiga Multi Type", "Ultraman Tiga", "Standard", "mid", 80),
        ("S.H.Figuarts", "Ultraman Tiga Sky Type", "Ultraman Tiga", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Ultraman Zero Beyond", "Ultraman Zero", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "Ultraman Geed Primitive", "Ultraman Geed", "Standard", "mid", 75),
        ("S.H.Figuarts", "Ultraman Geed Royal Mega Master", "Ultraman Geed", "P-Bandai", "high", 120),
        ("S.H.Figuarts", "Ultraman Blazar", "Ultraman Blazar", "Standard", "mid", 75),
        ("S.H.Figuarts", "Ultraman Arc", "Ultraman Arc", "Standard", "mid", 75),
        ("S.H.Figuarts", "Ultraman Decker Flash Type", "Ultraman Decker", "Standard", "mid", 80),

        # ── Robot Spirits — Evangelion ─────────────────────────────────────
        ("Robot Spirits", "Evangelion Unit-01 (Awakened Ver.)", "Evangelion: 3.0", "P-Bandai", "high", 145),
        ("Robot Spirits", "Evangelion Unit-02 (Production Model) Type S", "Evangelion: 3.0+1.0", "P-Bandai", "high", 140),
        ("Robot Spirits", "Evangelion Unit-08 Gamma", "Evangelion: 3.0+1.0", "P-Bandai", "high", 135),
        ("Robot Spirits", "Evangelion Unit-13", "Evangelion: 3.0+1.0", "P-Bandai", "high", 150),
        ("Robot Spirits", "Evangelion Mark.06", "Evangelion: 2.0", "P-Bandai", "high", 130),

        # ── Robot Spirits — Code Geass ─────────────────────────────────────
        ("Robot Spirits", "Lancelot siN ver. A.N.I.M.E.", "Code Geass: Rozé", "P-Bandai", "mid", 100),
        ("Robot Spirits", "Guren S.E.I.T.E.N. Eight Elements ver. A.N.I.M.E.", "Code Geass R2", "P-Bandai", "mid", 95),
        ("Robot Spirits", "Shinkirou ver. A.N.I.M.E.", "Code Geass R2", "P-Bandai", "mid", 100),

        # ── Proplica ──────────────────────────────────────────────────────
        ("Proplica", "Moon Stick -Brilliant Color Edition-", "Sailor Moon", "Standard", "high", 120),
        ("Proplica", "Cutie Moon Rod -Brilliant Color Edition-", "Sailor Moon R", "Standard", "high", 130),
        ("Proplica", "Tanjiro Kamado Earrings (Hanafuda)", "Demon Slayer", "Standard", "mid", 65),
        ("Proplica", "Nichirin Sword (Tanjiro Kamado)", "Demon Slayer", "Standard", "high", 140),
        ("Proplica", "Jujutsu Kaisen Playback -Ryomen Sukuna Finger-", "Jujutsu Kaisen", "Standard", "mid", 55),
        ("Proplica", "Sailor Moon Eternal Moon Article", "Sailor Moon Eternal", "P-Bandai", "high", 160),
        ("Proplica", "Holy Grail -Brilliant Color Edition-", "Sailor Moon S", "P-Bandai", "high", 145),
        ("Proplica", "Zanpakuto Zangetsu (Tensa) -Final Form-", "Bleach TYBW", "Standard", "high", 135),
    ]


def _round7_bandai_expansion() -> list[tuple]:
    """Round 7 expansion: 88 items — Metal Build, Chogokin, CSM, Proplica, S.I.C.,
    Figuarts ZERO Extra Battle, more S.H.Figuarts."""
    return [
        # ── Metal Build Releases (12) ─────────────────────────────────────
        ("Metal Build", "Gundam Astray Red Frame Kai", "Gundam SEED Astray", "P-Bandai", "grail", 380),
        ("Metal Build", "Gundam Astray Blue Frame Full Weapons", "Gundam SEED Astray", "P-Bandai", "grail", 400),
        ("Metal Build", "Gundam Astray Gold Frame Amatsu Mina", "Gundam SEED Astray", "P-Bandai", "grail", 420),
        ("Metal Build", "Freedom Gundam Concept 2 (Full Burst)", "Gundam SEED", "P-Bandai", "grail", 450),
        ("Metal Build", "Strike Freedom Gundam (Full Burst Mode)", "Gundam SEED Destiny", "Standard", "grail", 380),
        ("Metal Build", "Strike Gundam + IWSP", "Gundam SEED", "P-Bandai", "grail", 350),
        ("Metal Build", "Destiny Gundam (Full Package)", "Gundam SEED Destiny", "P-Bandai", "grail", 400),
        ("Metal Build", "Infinite Justice Gundam", "Gundam SEED Destiny", "Standard", "high", 280),
        ("Metal Build", "00 Raiser (Designer's Blue)", "Gundam 00", "P-Bandai", "grail", 420),
        ("Metal Build", "00 Qan[T] Full Saber", "Gundam 00: Trailblazer", "P-Bandai", "grail", 400),
        ("Metal Build", "Hi-Nu Gundam", "Char's Counterattack", "Standard", "grail", 380),
        ("Metal Build", "Gundam F91 (Harrison Maddin)", "Gundam F91", "P-Bandai", "high", 300),

        # ── Chogokin Specials (10) ────────────────────────────────────────
        ("Soul of Chogokin", "GX-105 Daitarn 3 F.A.", "Daitarn 3", "Standard", "high", 250),
        ("Soul of Chogokin", "GX-100 Gaiking", "Gaiking", "Standard", "high", 280),
        ("Soul of Chogokin", "GX-99 Getter Dragon", "Getter Robo G", "Standard", "high", 220),
        ("Soul of Chogokin", "GX-98 Getter Poseidon", "Getter Robo G", "P-Bandai", "high", 240),
        ("Soul of Chogokin", "GX-97 Daimos", "Daimos", "Standard", "high", 260),
        ("Soul of Chogokin", "GX-96 Getter Liger", "Getter Robo G", "P-Bandai", "high", 230),
        ("Chogokin", "Toy Story Super Combined Buzz the Space Ranger Robo", "Toy Story", "Standard", "mid", 120),
        ("Chogokin", "Voltron (30th Anniversary)", "Voltron", "Standard", "high", 280),
        ("Chogokin", "Grendizer (Dynamic Classics)", "UFO Robot Grendizer", "Standard", "high", 200),
        ("Chogokin", "Mazinger Z (Dynamic Classics)", "Mazinger Z", "Standard", "high", 200),

        # ── CSM (Complete Selection Modification) Kamen Rider (12) ────────
        ("CSM", "OOO Driver Complete Set", "Kamen Rider OOO", "P-Bandai", "grail", 450),
        ("CSM", "W Driver (ver. 1.5)", "Kamen Rider W", "P-Bandai", "grail", 380),
        ("CSM", "Faiz Gear (ver. 2)", "Kamen Rider 555", "P-Bandai", "grail", 400),
        ("CSM", "Delta Gear", "Kamen Rider 555", "P-Bandai", "high", 280),
        ("CSM", "Kaixa Gear", "Kamen Rider 555", "P-Bandai", "high", 280),
        ("CSM", "Decadriver (ver. 2)", "Kamen Rider Decade", "P-Bandai", "grail", 350),
        ("CSM", "DiEnd Driver", "Kamen Rider Decade", "P-Bandai", "high", 280),
        ("CSM", "Arcle", "Kamen Rider Kuuga", "P-Bandai", "grail", 380),
        ("CSM", "Blade Rouzer & Rouse Absorber", "Kamen Rider Blade", "P-Bandai", "grail", 420),
        ("CSM", "Kabuto Zecter", "Kamen Rider Kabuto", "P-Bandai", "grail", 350),
        ("CSM", "Buggle Driver II", "Kamen Rider Ex-Aid", "P-Bandai", "high", 250),
        ("CSM", "V Buckle & Dragvisor", "Kamen Rider Ryuki", "P-Bandai", "grail", 400),

        # ── Proplica (10) ────────────────────────────────────────────────
        ("Proplica", "Moon Stick -Brilliant Color Edition-", "Sailor Moon", "P-Bandai", "high", 130),
        ("Proplica", "Spiral Heart Moon Rod", "Sailor Moon S", "Standard", "mid", 95),
        ("Proplica", "Kaleidomoon Scope", "Sailor Moon SuperS", "Standard", "mid", 100),
        ("Proplica", "Tanjiro Kamado Earrings (Demon Slayer)", "Demon Slayer", "P-Bandai", "mid", 65),
        ("Proplica", "Nezuko Bamboo Mouthpiece", "Demon Slayer", "Standard", "mid", 55),
        ("Proplica", "Nichirin Blade (Rengoku Kyojuro)", "Demon Slayer", "P-Bandai", "high", 140),
        ("Proplica", "Communicator -Mercury-", "Sailor Moon", "P-Bandai", "mid", 80),
        ("Proplica", "Crystal Star -Brilliant Color Edition-", "Sailor Moon R", "P-Bandai", "high", 140),
        ("Proplica", "Jujutsu Kaisen Slaughter Demon (Toji)", "Jujutsu Kaisen", "Standard", "mid", 90),
        ("Proplica", "Zanpakuto Senbonzakura Kageyoshi (Byakuya)", "Bleach TYBW", "P-Bandai", "high", 150),

        # ── S.I.C. Figures (10) ──────────────────────────────────────────
        ("S.I.C.", "Kamen Rider Kuuga Mighty Form", "Kamen Rider Kuuga", "Standard", "mid", 90),
        ("S.I.C.", "Kamen Rider Agito Ground Form", "Kamen Rider Agito", "Standard", "mid", 85),
        ("S.I.C.", "Kamen Rider Faiz", "Kamen Rider 555", "Standard", "mid", 90),
        ("S.I.C.", "Kamen Rider Blade", "Kamen Rider Blade", "Standard", "mid", 85),
        ("S.I.C.", "Kamen Rider Kabuto", "Kamen Rider Kabuto", "Standard", "mid", 90),
        ("S.I.C.", "Kamen Rider Den-O Sword Form", "Kamen Rider Den-O", "Standard", "mid", 85),
        ("S.I.C.", "Kamen Rider W CycloneJoker", "Kamen Rider W", "Standard", "mid", 95),
        ("S.I.C.", "Kamen Rider OOO Tatoba Combo", "Kamen Rider OOO", "Standard", "mid", 90),
        ("S.I.C.", "Kamen Rider Gaim Orange Arms", "Kamen Rider Gaim", "Standard", "mid", 85),
        ("S.I.C.", "Kamen Rider Build RabbitTank", "Kamen Rider Build", "Standard", "mid", 90),

        # ── Figuarts ZERO Extra Battle (12) ──────────────────────────────
        ("Figuarts ZERO", "Portgas D. Ace -Fire Fist-", "One Piece", "Standard", "mid", 85),
        ("Figuarts ZERO", "Monkey D. Luffy -Gear 5- Gigant", "One Piece", "Standard", "high", 160),
        ("Figuarts ZERO", "Sanji -Diable Jambe-", "One Piece", "Standard", "mid", 75),
        ("Figuarts ZERO", "Trafalgar Law -Gamma Knife-", "One Piece", "Standard", "mid", 80),
        ("Figuarts ZERO", "Kaido King of the Beasts -Twin Dragons-", "One Piece", "Standard", "high", 200),
        ("Figuarts ZERO", "Shanks -Conqueror's Haki-", "One Piece", "Standard", "high", 180),
        ("Figuarts ZERO", "Son Goku -SSJ- Burning Battles", "Dragon Ball Z", "Standard", "mid", 70),
        ("Figuarts ZERO", "Vegeta -Galick Gun-", "Dragon Ball Z", "Standard", "mid", 70),
        ("Figuarts ZERO", "Gogeta SSB -Burning Battles-", "Dragon Ball Super: Broly", "Standard", "mid", 80),
        ("Figuarts ZERO", "Boa Hancock -Love Hurricane-", "One Piece", "Standard", "mid", 75),
        ("Figuarts ZERO", "Yamato -Thunder Bagua-", "One Piece", "Standard", "mid", 85),
        ("Figuarts ZERO", "Nico Robin -Demonio Fleur-", "One Piece", "Standard", "mid", 80),

        # ── S.H.Figuarts Additional (10) ─────────────────────────────────
        ("S.H.Figuarts", "Vegito Super Saiyan Blue", "Dragon Ball Super", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Piccolo (Power Awakening)", "Dragon Ball Super: Super Hero", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Gohan Beast", "Dragon Ball Super: Super Hero", "Standard", "mid", 75),
        ("S.H.Figuarts", "Kamen Rider Zero-One Rising Hopper", "Kamen Rider Zero-One", "Standard", "mid", 70),
        ("S.H.Figuarts", "Kamen Rider Saber Brave Dragon", "Kamen Rider Saber", "Standard", "mid", 70),
        ("S.H.Figuarts", "Kamen Rider Revice Rex Genome", "Kamen Rider Revice", "Standard", "mid", 70),
        ("S.H.Figuarts", "Kamen Rider Geats Magnum Boost", "Kamen Rider Geats", "Standard", "mid", 70),
        ("S.H.Figuarts", "Kamen Rider Gotchard", "Kamen Rider Gotchard", "Standard", "mid", 70),
        ("S.H.Figuarts", "Ultraman Trigger Multi Type", "Ultraman Trigger", "Standard", "mid", 70),
        ("S.H.Figuarts", "Ultraman Decker Flash Type", "Ultraman Decker", "Standard", "mid", 70),

        # ── Robot Spirits Additional (12) ─────────────────────────────────
        ("Robot Spirits", "Gundam Aerial (Permet Score 5)", "Gundam: Witch from Mercury", "P-Bandai", "high", 155),
        ("Robot Spirits", "Gundam Lfrith Jiu", "Gundam: Witch from Mercury", "P-Bandai", "mid", 85),
        ("Robot Spirits", "Gundam Schwarzette", "Gundam: Witch from Mercury", "Standard", "mid", 75),
        ("Robot Spirits", "Gundam Pharact", "Gundam: Witch from Mercury", "Standard", "mid", 75),
        ("Robot Spirits", "Michaelis", "Gundam: Witch from Mercury", "P-Bandai", "mid", 80),
        ("Robot Spirits", "Gundam Calibarn", "Gundam: Witch from Mercury", "P-Bandai", "high", 150),
        ("Robot Spirits", "Xi Gundam ver. A.N.I.M.E.", "Gundam Hathaway", "Standard", "high", 180),
        ("Robot Spirits", "Penelope ver. A.N.I.M.E.", "Gundam Hathaway", "Standard", "high", 200),
        ("Robot Spirits", "Hyaku Shiki ver. A.N.I.M.E.", "Zeta Gundam", "Standard", "mid", 80),
        ("Robot Spirits", "Rick Dias ver. A.N.I.M.E.", "Zeta Gundam", "P-Bandai", "mid", 80),
        ("Robot Spirits", "Full Armor ZZ Gundam ver. A.N.I.M.E.", "Gundam ZZ", "P-Bandai", "high", 160),
        ("Robot Spirits", "Kshatriya ver. A.N.I.M.E.", "Gundam Unicorn", "Standard", "high", 180),
    ]


def _expansion_700_gunpla_pbandai() -> list[tuple]:
    """P-Bandai exclusive Gunpla kits — MG/RG/HG coating, clear, titanium variants."""
    return [
        # MG P-Bandai exclusives
        ("MG 1/100", "Wing Gundam Zero EW Ver.Ka (Special Coating)", "Gundam Wing EW", "P-Bandai", "high", 130),
        ("MG 1/100", "Sazabi Ver.Ka (Special Coating)", "Gundam CCA", "P-Bandai", "high", 160),
        ("MG 1/100", "Nu Gundam Ver.Ka (Titanium Finish)", "Gundam CCA", "P-Bandai", "high", 165),
        ("MG 1/100", "Sinanju (Mechanical Clear)", "Gundam Unicorn", "P-Bandai", "high", 140),
        ("MG 1/100", "Unicorn Gundam (Red/Green Frame Titanium)", "Gundam Unicorn", "P-Bandai", "high", 150),
        ("MG 1/100", "Crossbone Gundam X1 Ver.Ka", "Crossbone Gundam", "P-Bandai", "mid", 85),
        ("MG 1/100", "Gundam Mk-V", "Gundam Sentinel", "P-Bandai", "mid", 95),
        ("MG 1/100", "Hazel Custom (Titans Color)", "Advance of Zeta", "P-Bandai", "mid", 90),
        ("MG 1/100", "Powered GM", "Gundam 0083", "P-Bandai", "mid", 75),
        ("MG 1/100", "Gundam Alex NT-1 Ver.2.0", "Gundam 0080", "P-Bandai", "mid", 80),
        ("MG 1/100", "Rick Dom", "Mobile Suit Gundam", "P-Bandai", "mid", 75),
        ("MG 1/100", "Zaku Cannon", "MSV", "P-Bandai", "mid", 70),
        ("MG 1/100", "Gundam Exia Repair II", "Gundam 00", "P-Bandai", "mid", 85),
        ("MG 1/100", "Gundam Kyrios", "Gundam 00", "P-Bandai", "mid", 80),
        ("MG 1/100", "Gundam Virtue", "Gundam 00", "P-Bandai", "mid", 85),
        ("MG 1/100", "Gundam Dynames", "Gundam 00", "P-Bandai", "mid", 80),
        ("MG 1/100", "Gundam Astray Turn Red", "Gundam SEED Astray", "P-Bandai", "mid", 90),
        ("MG 1/100", "Duel Gundam Assault Shroud", "Gundam SEED", "P-Bandai", "mid", 80),
        ("MG 1/100", "Buster Gundam", "Gundam SEED", "P-Bandai", "mid", 75),
        ("MG 1/100", "Blitz Gundam", "Gundam SEED", "P-Bandai", "mid", 75),
        # RG P-Bandai exclusives
        ("RG 1/144", "Strike Freedom Gundam (Titanium Finish)", "Gundam SEED Destiny", "P-Bandai", "mid", 80),
        ("RG 1/144", "Destiny Gundam (Titanium Finish)", "Gundam SEED Destiny", "P-Bandai", "mid", 75),
        ("RG 1/144", "00 Raiser (Trans-Am Clear)", "Gundam 00", "P-Bandai", "mid", 70),
        ("RG 1/144", "Unicorn Gundam (Luminous Crystal)", "Gundam Unicorn", "P-Bandai", "mid", 80),
        ("RG 1/144", "Banshee Norn (Final Battle Ver.)", "Gundam Unicorn", "P-Bandai", "mid", 75),
        ("RG 1/144", "Nu Gundam (Metallic Coating)", "Gundam CCA", "P-Bandai", "mid", 80),
        ("RG 1/144", "Sazabi (Special Coating)", "Gundam CCA", "P-Bandai", "mid", 80),
        ("RG 1/144", "Gundam Astray Gold Frame Amatsu Hana", "Gundam SEED Astray", "P-Bandai", "mid", 70),
        ("RG 1/144", "Freedom Gundam (Deactive Mode)", "Gundam SEED", "P-Bandai", "mid", 60),
        # HG P-Bandai exclusives (Advance of Zeta, MSV, etc.)
        ("HG 1/144", "Woundwort", "Advance of Zeta", "P-Bandai", "mid", 55),
        ("HG 1/144", "Hazel II", "Advance of Zeta", "P-Bandai", "mid", 50),
        ("HG 1/144", "Kehaar II", "Advance of Zeta", "P-Bandai", "mid", 50),
        ("HG 1/144", "Hrududu II", "Advance of Zeta", "P-Bandai", "mid", 45),
        ("HG 1/144", "Gaplant TR-5 Hrairoo", "Advance of Zeta", "P-Bandai", "mid", 55),
        ("HG 1/144", "GM Quel", "Gundam 0083", "P-Bandai", "mid", 40),
        ("HG 1/144", "Zaku I Sniper (Yonem Kirks)", "Gundam Thunderbolt", "P-Bandai", "mid", 40),
        ("HG 1/144", "Atlas Gundam (Thunderbolt)", "Gundam Thunderbolt", "P-Bandai", "mid", 50),
        ("HG 1/144", "Guncannon Detector", "Gundam Unicorn", "P-Bandai", "mid", 40),
        ("HG 1/144", "Anksha", "Gundam Unicorn", "P-Bandai", "mid", 40),
        ("HG 1/144", "Dreissen (Sleeves Custom)", "Gundam Unicorn", "P-Bandai", "mid", 45),
    ]


def _expansion_700_super_robot_chogokin() -> list[tuple]:
    """Super Robot Chogokin & Soul of Chogokin exclusives."""
    return [
        ("Super Robot Chogokin", "Mazinger Z (Iron Cutter Edition)", "Mazinger Z", "P-Bandai", "high", 180),
        ("Super Robot Chogokin", "Great Mazinger (Premium Edition)", "Great Mazinger", "P-Bandai", "high", 190),
        ("Super Robot Chogokin", "Shin Getter 1 OVA Version", "Getter Robo", "P-Bandai", "high", 200),
        ("Super Robot Chogokin", "Mazinkaiser SKL", "Mazinkaiser SKL", "Standard", "high", 170),
        ("Super Robot Chogokin", "Genesic GaoGaiGar", "GaoGaiGar", "P-Bandai", "grail", 320),
        ("Super Robot Chogokin", "Shin Mazinger Z (Gold Ver.)", "Shin Mazinger", "P-Bandai", "high", 200),
        ("Super Robot Chogokin", "GaoFighGar", "GaoGaiGar FINAL", "P-Bandai", "high", 250),
        ("Super Robot Chogokin", "Gravion Zwei Sol Gravion", "Gravion Zwei", "P-Bandai", "high", 220),
        ("Soul of Chogokin", "GX-93 Space Pirate Captain Harlock", "Captain Harlock", "Standard", "high", 260),
        ("Soul of Chogokin", "GX-92 Ideon", "Space Runaway Ideon", "Standard", "grail", 350),
        ("Soul of Chogokin", "GX-79 Voltes V F.A.", "Voltes V", "Standard", "high", 270),
        ("Soul of Chogokin", "GX-95 Gordian Warrior", "Gordian Warrior", "Standard", "high", 250),
        ("Soul of Chogokin", "GX-81 Zamboace/Zambull/King Bial Set", "Zambot 3", "P-Bandai", "grail", 380),
    ]


def _expansion_700_shf_marvel_starwars() -> list[tuple]:
    """S.H.Figuarts — Marvel & Star Wars exclusives."""
    return [
        # Marvel
        ("S.H.Figuarts", "Iron Man Mark 50 Nano Weapon Set 2", "Avengers: Infinity War", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Iron Man Mark 85 (Final Battle Edition)", "Avengers: Endgame", "P-Bandai", "mid", 100),
        ("S.H.Figuarts", "Captain America (Endgame Final Battle)", "Avengers: Endgame", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "Thor (Endgame Final Battle)", "Avengers: Endgame", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Thanos (Final Battle Edition)", "Avengers: Endgame", "Standard", "mid", 110),
        ("S.H.Figuarts", "Spider-Man (No Way Home Integrated Suit)", "Spider-Man: No Way Home", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Spider-Man (No Way Home Final Swing Suit)", "Spider-Man: No Way Home", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "Doctor Strange (Multiverse of Madness)", "Doctor Strange MoM", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Black Panther (Wakanda Forever)", "Black Panther: Wakanda Forever", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "Hulk (Avengers: Endgame)", "Avengers: Endgame", "P-Bandai", "mid", 100),
        # Star Wars
        ("S.H.Figuarts", "Darth Vader (Return of the Jedi)", "Star Wars", "Standard", "mid", 85),
        ("S.H.Figuarts", "Darth Maul (Episode I)", "Star Wars", "Standard", "mid", 80),
        ("S.H.Figuarts", "Luke Skywalker (Return of the Jedi)", "Star Wars", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "Boba Fett (The Book of Boba Fett)", "Star Wars", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "The Mandalorian (Beskar Armor 2.0)", "Star Wars: The Mandalorian", "Standard", "mid", 85),
        ("S.H.Figuarts", "Obi-Wan Kenobi (Revenge of the Sith)", "Star Wars", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "Clone Trooper (Phase II)", "Star Wars", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Stormtrooper (A New Hope)", "Star Wars", "Standard", "mid", 70),
        ("S.H.Figuarts", "Kylo Ren (The Rise of Skywalker)", "Star Wars", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Ahsoka Tano (The Mandalorian)", "Star Wars: The Mandalorian", "P-Bandai", "mid", 95),
    ]


def _expansion_700_shmonsterarts() -> list[tuple]:
    """S.H.MonsterArts — Godzilla, Ultraman, and kaiju exclusives."""
    return [
        ("S.H.MonsterArts", "Godzilla (1954) First Generation", "Godzilla", "Standard", "high", 180),
        ("S.H.MonsterArts", "Godzilla (1995 Burning)", "Godzilla vs. Destoroyah", "P-Bandai", "grail", 320),
        ("S.H.MonsterArts", "Godzilla (2016 Shin Godzilla 2nd Form)", "Shin Godzilla", "P-Bandai", "high", 160),
        ("S.H.MonsterArts", "Godzilla (2016 Shin Godzilla Frozen)", "Shin Godzilla", "P-Bandai", "high", 170),
        ("S.H.MonsterArts", "Mothra (2019 King of the Monsters)", "Godzilla", "Standard", "high", 150),
        ("S.H.MonsterArts", "Rodan (2019 King of the Monsters)", "Godzilla", "Standard", "high", 140),
        ("S.H.MonsterArts", "Godzilla Earth (Planet of the Monsters)", "Godzilla Anime Trilogy", "P-Bandai", "high", 180),
        ("S.H.MonsterArts", "Mechagodzilla (1974 Classic)", "Godzilla vs. Mechagodzilla", "P-Bandai", "high", 200),
        ("S.H.MonsterArts", "Gigan (1972)", "Godzilla vs. Gigan", "P-Bandai", "high", 180),
        ("S.H.MonsterArts", "Hedorah", "Godzilla vs. Hedorah", "P-Bandai", "high", 170),
        ("S.H.MonsterArts", "Godzilla Junior", "Godzilla vs. Destoroyah", "P-Bandai", "mid", 120),
        ("S.H.MonsterArts", "Kong (Godzilla x Kong: The New Empire)", "Godzilla x Kong", "Standard", "high", 140),
        ("S.H.MonsterArts", "Skar King", "Godzilla x Kong", "P-Bandai", "high", 150),
        ("S.H.MonsterArts", "Godzilla Evolved (Godzilla x Kong)", "Godzilla x Kong", "Standard", "high", 160),
        ("S.H.MonsterArts", "Shimo", "Godzilla x Kong", "P-Bandai", "high", 150),
    ]


def _expansion_700_dx_chogokin_metal_build() -> list[tuple]:
    """DX Chogokin Macross & Metal Build additions."""
    return [
        # DX Chogokin — Macross
        ("DX Chogokin", "VF-0S Phoenix (Roy Focker)", "Macross Zero", "P-Bandai", "grail", 350),
        ("DX Chogokin", "VF-0A Phoenix (Shin Kudo)", "Macross Zero", "P-Bandai", "high", 300),
        ("DX Chogokin", "SV-51 Gamma (Nora Polyansky)", "Macross Zero", "P-Bandai", "high", 290),
        ("DX Chogokin", "VF-171 Nightmare Plus (Armored)", "Macross Frontier", "P-Bandai", "high", 240),
        ("DX Chogokin", "VF-25G Messiah (Michael Blanc)", "Macross Frontier", "P-Bandai", "high", 260),
        ("DX Chogokin", "VF-19 Advance (Macross Frontier)", "Macross Frontier", "P-Bandai", "high", 280),
        ("DX Chogokin", "VF-31F Siegfried (Messer Ihlefeld)", "Macross Delta", "P-Bandai", "high", 250),
        ("DX Chogokin", "VF-31C Siegfried (Mirage Farina Jenius)", "Macross Delta", "P-Bandai", "high", 250),
        ("DX Chogokin", "VF-31E Siegfried (Chuck Mustang)", "Macross Delta", "P-Bandai", "high", 240),
        # Metal Build — Gundam SEED Freedom (2024 movie)
        ("Metal Build", "Strike Freedom Gundam Type II", "Gundam SEED Freedom", "P-Bandai", "grail", 480),
        ("Metal Build", "Mighty Strike Freedom Gundam", "Gundam SEED Freedom", "P-Bandai", "grail", 520),
        ("Metal Build", "Immortal Justice Gundam", "Gundam SEED Freedom", "P-Bandai", "grail", 400),
        ("Metal Build", "Rising Freedom Gundam", "Gundam SEED Freedom", "Standard", "high", 280),
        ("Metal Build", "Destiny Gundam Spec II", "Gundam SEED Freedom", "P-Bandai", "grail", 420),
        ("Metal Build", "Gundam Aerial (Full Weapons)", "Gundam: Witch from Mercury", "P-Bandai", "grail", 380),
    ]


def _expansion_700_robot_spirits_fmp() -> list[tuple]:
    """Robot Spirits — Full Metal Panic, Gundam SEED Freedom, misc."""
    return [
        # Full Metal Panic
        ("Robot Spirits", "ARX-7 Arbalest (Lambda Driver)", "Full Metal Panic! TSR", "P-Bandai", "mid", 95),
        ("Robot Spirits", "ARX-8 Laevatein (Last Battle)", "Full Metal Panic! IV", "P-Bandai", "mid", 100),
        ("Robot Spirits", "M9 Gernsback (Mao Custom)", "Full Metal Panic!", "P-Bandai", "mid", 80),
        ("Robot Spirits", "M9D Falke", "Full Metal Panic!", "P-Bandai", "mid", 85),
        ("Robot Spirits", "Plan-1055 Belial", "Full Metal Panic! IV", "P-Bandai", "mid", 90),
        ("Robot Spirits", "Codarl (Venom)", "Full Metal Panic!", "P-Bandai", "mid", 80),
        # Gundam SEED Freedom movie
        ("Robot Spirits", "Rising Freedom Gundam ver. A.N.I.M.E.", "Gundam SEED Freedom", "P-Bandai", "high", 120),
        ("Robot Spirits", "Immortal Justice Gundam ver. A.N.I.M.E.", "Gundam SEED Freedom", "P-Bandai", "high", 120),
        ("Robot Spirits", "Destiny Gundam Spec II ver. A.N.I.M.E.", "Gundam SEED Freedom", "P-Bandai", "high", 130),
        ("Robot Spirits", "Black Knight Squad Shi-ve.A ver. A.N.I.M.E.", "Gundam SEED Freedom", "P-Bandai", "mid", 90),
        # Gundam misc
        ("Robot Spirits", "Gundam Mk-III ver. A.N.I.M.E.", "Z-MSV", "P-Bandai", "mid", 90),
        ("Robot Spirits", "Dijeh ver. A.N.I.M.E.", "Zeta Gundam", "P-Bandai", "mid", 85),
        ("Robot Spirits", "Methuss ver. A.N.I.M.E.", "Zeta Gundam", "P-Bandai", "mid", 75),
        ("Robot Spirits", "Barzam ver. A.N.I.M.E.", "Zeta Gundam", "P-Bandai", "mid", 70),
        ("Robot Spirits", "Hamma Hamma ver. A.N.I.M.E.", "Gundam ZZ", "P-Bandai", "mid", 85),
    ]


def _expansion_700_csm_proplica_candy() -> list[tuple]:
    """CSM Kamen Rider belts, Proplica props, candy toys & gashapon."""
    return [
        # CSM — Kamen Rider
        ("CSM", "Amazon Driver", "Kamen Rider Amazon", "P-Bandai", "grail", 380),
        ("CSM", "Typhoon Belt (Kamen Rider V3)", "Kamen Rider V3", "P-Bandai", "grail", 380),
        ("CSM", "Accel Driver", "Kamen Rider W", "P-Bandai", "high", 300),
        ("CSM", "Wizard Driver", "Kamen Rider Wizard", "P-Bandai", "grail", 340),
        ("CSM", "Ghost Driver", "Kamen Rider Ghost", "P-Bandai", "high", 280),
        ("CSM", "Drive Driver", "Kamen Rider Drive", "P-Bandai", "grail", 350),
        ("CSM", "Sclashjelly & Sclash Driver", "Kamen Rider Build", "P-Bandai", "high", 280),
        ("CSM", "Beyondriver", "Kamen Rider Zi-O", "P-Bandai", "high", 260),
        ("CSM", "Shotriser (Kamen Rider Vulcan)", "Kamen Rider Zero-One", "P-Bandai", "high", 260),
        ("CSM", "Revice Driver", "Kamen Rider Revice", "P-Bandai", "grail", 350),
        # Proplica
        ("Proplica", "Shinobu Kocho Nichirin Blade", "Demon Slayer", "P-Bandai", "high", 135),
        ("Proplica", "Muichiro Tokito Nichirin Blade", "Demon Slayer", "P-Bandai", "high", 130),
        ("Proplica", "Obanai Iguro Nichirin Blade", "Demon Slayer", "P-Bandai", "high", 130),
        ("Proplica", "Mitsuri Kanroji Nichirin Blade", "Demon Slayer", "P-Bandai", "high", 140),
        ("Proplica", "Sanemi Shinazugawa Nichirin Blade", "Demon Slayer", "P-Bandai", "high", 135),
        ("Proplica", "Dragon Ball", "Dragon Ball", "Standard", "mid", 75),
        ("Proplica", "Super Dragon Ball (Namekian)", "Dragon Ball Z", "P-Bandai", "mid", 85),
        ("Proplica", "Demon Slayer Mark Sword (Yoriichi)", "Demon Slayer", "P-Bandai", "grail", 200),
        ("Proplica", "Silver Crystal -Brilliant Color-", "Sailor Moon", "P-Bandai", "high", 130),
        ("Proplica", "Chibi Moon Compact", "Sailor Moon SuperS", "P-Bandai", "mid", 95),
        # Premium candy toys & gashapon
        ("Shokugan", "Super MiniPla Gaogaigar Set", "GaoGaiGar", "Standard", "mid", 80),
        ("Shokugan", "Super MiniPla Daizyujin (Megazord)", "Super Sentai Zyuranger", "Standard", "mid", 75),
        ("Shokugan", "Super MiniPla Victory Robo", "Super Sentai GoGoV", "Standard", "mid", 70),
        ("Shokugan", "Super MiniPla Dairen-Oh", "Super Sentai Dairanger", "Standard", "mid", 75),
        ("Shokugan", "Super MiniPla Bio Robo", "Super Sentai Bioman", "P-Bandai", "mid", 80),
        ("Shokugan", "SMP Dancouga (Full Set)", "Dancouga", "Standard", "mid", 90),
        ("Shokugan", "SMP Godmars (Full Set)", "Six God Combination Godmars", "Standard", "mid", 85),
        ("Shokugan", "SMP Baldios (Full Set)", "Space Warrior Baldios", "P-Bandai", "mid", 90),
        ("Gashapon", "HG Gacha Evangelion Set (Complete)", "Evangelion", "Standard", "standard", 30),
        ("Gashapon", "HG Gacha Godzilla 2024 Set", "Godzilla", "Standard", "standard", 25),
    ]


def _expansion_700_figurerise_misc() -> list[tuple]:
    """Figure-rise Standard/LABO, misc Tamashii lines."""
    return [
        # Figure-rise Standard
        ("Figure-rise Standard", "Kamen Rider Kuuga Mighty Form", "Kamen Rider Kuuga", "Standard", "mid", 40),
        ("Figure-rise Standard", "Kamen Rider Faiz", "Kamen Rider 555", "Standard", "mid", 40),
        ("Figure-rise Standard", "Kamen Rider Den-O Sword Form", "Kamen Rider Den-O", "Standard", "mid", 40),
        ("Figure-rise Standard", "Kamen Rider OOO TaToBa Combo", "Kamen Rider OOO", "Standard", "mid", 40),
        ("Figure-rise Standard", "Kamen Rider Double CycloneJoker (Gold Frame)", "Kamen Rider W", "P-Bandai", "mid", 55),
        ("Figure-rise Standard", "Son Goku (New Spec Ver.)", "Dragon Ball Z", "Standard", "mid", 45),
        ("Figure-rise Standard", "Vegeta (New Spec Ver.)", "Dragon Ball Z", "P-Bandai", "mid", 50),
        ("Figure-rise Standard", "Cell Perfect Form", "Dragon Ball Z", "P-Bandai", "mid", 55),
        ("Figure-rise Standard", "Frieza Final Form", "Dragon Ball Z", "Standard", "mid", 45),
        ("Figure-rise Standard", "Amplified Dukemon (Gallantmon)", "Digimon", "Standard", "mid", 55),
        ("Figure-rise Standard", "Amplified Magnamon", "Digimon", "P-Bandai", "mid", 65),
        ("Figure-rise Standard", "Amplified Alphamon", "Digimon", "P-Bandai", "mid", 65),
        # Figure-rise LABO
        ("Figure-rise LABO", "Hatsune Miku V4X", "Vocaloid", "Standard", "mid", 50),
        ("Figure-rise LABO", "Fumina Hoshino", "Gundam Build Fighters Try", "Standard", "mid", 45),
        ("Figure-rise LABO", "Ladybug (Miraculous)", "Miraculous Ladybug", "Standard", "mid", 45),
        # Ichiban Kuji / Lottery prizes
        ("Ichiban Kuji", "Luffy Gear 5 Last One Prize", "One Piece", "Lottery Prize", "high", 180),
        ("Ichiban Kuji", "Goku Ultra Instinct Last One Prize", "Dragon Ball Super", "Lottery Prize", "high", 160),
        ("Ichiban Kuji", "Gojo Satoru Last One Prize", "Jujutsu Kaisen", "Lottery Prize", "high", 150),
        ("Ichiban Kuji", "Tanjiro Kamado Last One Prize", "Demon Slayer", "Lottery Prize", "high", 140),
        ("Ichiban Kuji", "Vegeta (Cell Saga) A Prize", "Dragon Ball Z", "Lottery Prize", "mid", 100),
    ]


def _expansion_700_shf_anime_tokusatsu() -> list[tuple]:
    """S.H.Figuarts — additional anime, Bleach TYBW, My Hero Academia, misc."""
    return [
        # Bleach TYBW
        ("S.H.Figuarts", "Ichigo Kurosaki (TYBW Bankai)", "Bleach TYBW", "Standard", "mid", 80),
        ("S.H.Figuarts", "Byakuya Kuchiki (TYBW)", "Bleach TYBW", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "Kenpachi Zaraki (TYBW)", "Bleach TYBW", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Sosuke Aizen (TYBW)", "Bleach TYBW", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Uryu Ishida (TYBW)", "Bleach TYBW", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Renji Abarai (TYBW)", "Bleach TYBW", "P-Bandai", "mid", 85),
        # My Hero Academia
        ("S.H.Figuarts", "Izuku Midoriya (Full Cowling)", "My Hero Academia", "Standard", "mid", 70),
        ("S.H.Figuarts", "All Might (Weakened Form)", "My Hero Academia", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Katsuki Bakugo", "My Hero Academia", "Standard", "mid", 70),
        ("S.H.Figuarts", "Shoto Todoroki", "My Hero Academia", "P-Bandai", "mid", 80),
        # Dragon Ball Daima (2024)
        ("S.H.Figuarts", "Piccolo (Daima Mini Ver.)", "Dragon Ball Daima", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Glorio (Daima)", "Dragon Ball Daima", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Masked Majin (Daima)", "Dragon Ball Daima", "P-Bandai", "mid", 90),
        # One Piece (Film Red / Egghead)
        ("S.H.Figuarts", "Zoro (Egghead Arc)", "One Piece", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "Sanji (Egghead Arc)", "One Piece", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Jinbe (Wano)", "One Piece", "P-Bandai", "mid", 85),
        # Kamen Rider (2024-2025 shows)
        ("S.H.Figuarts", "Kamen Rider Gavv Gummy Form", "Kamen Rider Gavv", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Kamen Rider Gavv Chocolate Form", "Kamen Rider Gavv", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Kamen Rider Gotchard (Platinum Chemistry)", "Kamen Rider Gotchard", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "Kamen Rider Gotchard (Tornado Hawk)", "Kamen Rider Gotchard", "P-Bandai", "mid", 80),
    ]


def get_curated_catalog() -> list[dict]:
    """Curated Bandai Premium / P-Bandai exclusives catalog (700+ items)."""

    # (line, name, franchise, exclusive_type, rarity_tier, price_eur)
    # rarity_tier: grail (>300), high (150-300), mid (60-150), standard (<60)

    items = [
        # S.H.Figuarts – Dragon Ball
        ("S.H.Figuarts", "Super Saiyan God Vegeta", "Dragon Ball Super", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Majin Vegeta", "Dragon Ball Z", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Full Power Frieza", "Dragon Ball Z", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Android 19 & 20 Set", "Dragon Ball Z", "P-Bandai", "high", 160),
        ("S.H.Figuarts", "Bardock", "Dragon Ball Z", "P-Bandai", "mid", 110),
        ("S.H.Figuarts", "Super Saiyan God Super Saiyan Gogeta", "Dragon Ball Super: Broly", "P-Bandai", "mid", 90),

        # S.H.Figuarts – Kamen Rider
        ("S.H.Figuarts", "Kamen Rider Kuuga Amazing Mighty", "Kamen Rider Kuuga", "P-Bandai", "mid", 75),
        ("S.H.Figuarts", "Kamen Rider Faiz Blaster Form", "Kamen Rider 555", "P-Bandai", "mid", 80),
        ("S.H.Figuarts", "Kamen Rider OOO Super Tatoba Combo", "Kamen Rider OOO", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Kamen Rider W FangJoker", "Kamen Rider W", "P-Bandai", "mid", 70),

        # S.H.Figuarts – Naruto
        ("S.H.Figuarts", "Itachi Uchiha Edo Tensei", "Naruto Shippuden", "P-Bandai", "mid", 75),
        ("S.H.Figuarts", "Minato Namikaze", "Naruto Shippuden", "P-Bandai", "mid", 90),

        # Robot Spirits – Gundam
        ("Robot Spirits", "RX-78GP03S Stamen ver. A.N.I.M.E.", "Gundam 0083", "P-Bandai", "mid", 80),
        ("Robot Spirits", "MS-06R-2 Zaku II High Mobility Type", "Gundam MSV", "P-Bandai", "mid", 75),
        ("Robot Spirits", "Nightingale ver. A.N.I.M.E.", "Gundam CCA-MSV", "P-Bandai", "high", 155),

        # Robot Spirits – Evangelion
        ("Robot Spirits", "EVA Unit-01 Awakening Ver.", "Evangelion", "P-Bandai", "mid", 95),
        ("Robot Spirits", "EVA Unit-13", "Evangelion 3.0+1.0", "P-Bandai", "mid", 90),

        # Chogokin / Soul of Chogokin
        ("Soul of Chogokin", "GX-72 Megazord", "Super Sentai", "Standard", "high", 250),
        ("Soul of Chogokin", "GX-105 Mazinkaiser Infinitism", "Mazinkaiser", "Standard", "high", 220),
        ("Soul of Chogokin", "GX-70SP Mazinger Z D.C. Anime Color", "Mazinger Z", "P-Bandai", "high", 280),
        ("Soul of Chogokin", "GX-76X2 Grendizer D.C. Drill Spazer", "UFO Robot Grendizer", "P-Bandai", "high", 200),
        ("Soul of Chogokin", "GX-01R+ Mazinger Z (40th Anniversary)", "Mazinger Z", "Event Exclusive", "grail", 350),

        # Tamashii Nations Event Exclusives
        ("S.H.Figuarts", "Son Goku Ultra Instinct -Sign-", "Dragon Ball Super", "TNE", "high", 160),
        ("S.H.Figuarts", "Kamen Rider Decade Complete 21", "Kamen Rider Decade", "TNE", "mid", 120),
        ("Robot Spirits", "Full Armor Unicorn Gundam", "Gundam Unicorn", "TNE", "mid", 100),

        # Metal Build
        ("Metal Build", "Strike Freedom Gundam", "Gundam SEED Destiny", "Standard", "grail", 380),
        ("Metal Build", "00 Raiser", "Gundam 00", "Standard", "high", 280),
        ("Metal Build", "Destiny Gundam (Full Package)", "Gundam SEED Destiny", "P-Bandai", "grail", 400),
        ("Metal Build", "Astray Red Frame Kai", "Gundam SEED Astray", "Standard", "high", 300),
        ("Metal Build", "Hi-Nu Gundam", "Gundam CCA", "Standard", "grail", 420),
        ("Metal Build", "Crossbone Gundam X1", "Crossbone Gundam", "P-Bandai", "high", 280),

        # ── New items below ──────────────────────────────────────────────

        # S.H.Figuarts – Kamen Rider (additional)
        ("S.H.Figuarts", "Kamen Rider Black Sun", "Kamen Rider Black Sun", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Kamen Rider Kuuga Ultimate Form", "Kamen Rider Kuuga", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "Kamen Rider Decade Violent Emotion", "Kamen Rider Decade", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Kamen Rider W CycloneJokerXtreme", "Kamen Rider W", "P-Bandai", "mid", 80),

        # S.H.Figuarts – Naruto (additional)
        ("S.H.Figuarts", "Itachi Uchiha -Narutop99-", "Naruto Shippuden", "P-Bandai", "mid", 85),
        ("S.H.Figuarts", "Kakashi Hatake Anbu Black Ops", "Naruto Shippuden", "P-Bandai", "mid", 95),

        # S.H.Figuarts – One Piece
        ("S.H.Figuarts", "Monkey D. Luffy Gear 5", "One Piece", "Standard", "mid", 75),
        ("S.H.Figuarts", "Roronoa Zoro -Wano Kuni-", "One Piece", "P-Bandai", "mid", 80),

        # S.H.Figuarts – Ultraman
        ("S.H.Figuarts", "Ultraman (Shin Ultraman)", "Shin Ultraman", "P-Bandai", "mid", 70),

        # Robot Spirits – Gundam (additional)
        ("Robot Spirits", "RX-78-2 Gundam ver. A.N.I.M.E.", "Mobile Suit Gundam", "Standard", "mid", 65),
        ("Robot Spirits", "MS-06S Zaku II Char Custom ver. A.N.I.M.E.", "Mobile Suit Gundam", "Standard", "mid", 65),
        ("Robot Spirits", "RX-93 Nu Gundam ver. A.N.I.M.E.", "Gundam CCA", "Standard", "mid", 85),
        ("Robot Spirits", "MSN-04 Sazabi ver. A.N.I.M.E.", "Gundam CCA", "Standard", "mid", 90),

        # Robot Spirits – Evangelion (additional)
        ("Robot Spirits", "EVA Unit-01 Test Type", "Evangelion", "Standard", "mid", 70),
        ("Robot Spirits", "EVA Unit-02 Production Model", "Evangelion", "Standard", "mid", 70),

        # Metal Build (additional)
        ("Metal Build", "Strike Freedom Gundam Soul Blue Ver.", "Gundam SEED Destiny", "P-Bandai", "grail", 450),
        ("Metal Build", "00 Raiser Designer's Blue Ver.", "Gundam 00", "P-Bandai", "grail", 350),
        ("Metal Build", "Destiny Gundam Heine Custom", "Gundam SEED Destiny", "P-Bandai", "high", 300),
        ("Metal Build", "Crossbone Gundam X1 Full Cloth", "Crossbone Gundam", "P-Bandai", "grail", 380),
        ("Metal Build", "Hi-Nu Gundam Marking Plus Ver.", "Gundam CCA", "P-Bandai", "grail", 480),

        # Soul of Chogokin (additional)
        ("Soul of Chogokin", "GX-70 Mazinger Z D.C.", "Mazinger Z", "Standard", "high", 180),
        ("Soul of Chogokin", "GX-73 Great Mazinger D.C.", "Great Mazinger", "Standard", "high", 200),
        ("Soul of Chogokin", "GX-76 Grendizer D.C.", "UFO Robot Grendizer", "Standard", "high", 190),
        ("Soul of Chogokin", "GX-71SP GoLion (Voltron)", "Beast King GoLion", "P-Bandai", "grail", 380),
        ("Soul of Chogokin", "GX-72B Daizyujin (Megazord) Black Ver.", "Super Sentai", "P-Bandai", "high", 290),

        # Tamashii Nations Event Exclusives (additional)
        ("S.H.Figuarts", "Vegito Super Saiyan Blue (SDCC)", "Dragon Ball Super", "Event Exclusive", "high", 180),
        ("S.H.Figuarts", "Son Goku Super Saiyan (SDCC 2019)", "Dragon Ball Z", "Event Exclusive", "high", 170),
        ("S.H.Figuarts", "Kamen Rider Ichigo (50th Anniversary)", "Kamen Rider", "TNE", "high", 150),
        ("Robot Spirits", "Wing Gundam Zero (EW) Pearl Coating", "Gundam Wing", "TNE", "high", 160),
        ("Metal Build", "Strike Gundam (Tamashii Nations Tokyo)", "Gundam SEED", "Event Exclusive", "grail", 400),

        # DX Chogokin – Macross
        ("DX Chogokin", "VF-1S Strike Valkyrie (Hikaru)", "Macross", "Standard", "high", 280),
        ("DX Chogokin", "VF-25F Messiah Valkyrie (Alto)", "Macross Frontier", "Standard", "high", 250),
        ("DX Chogokin", "YF-29 Durandal Valkyrie (Alto)", "Macross Frontier", "Standard", "high", 260),

        # Figuarts ZERO – One Piece
        ("Figuarts ZERO", "Monkey D. Luffy -Gomu Gomu no Red Roc-", "One Piece", "Standard", "mid", 90),
        ("Figuarts ZERO", "Kaido King of the Beasts -Twin Dragons-", "One Piece", "Standard", "mid", 120),
        ("Figuarts ZERO", "Portgas D. Ace -Fire Fist-", "One Piece", "Standard", "mid", 85),

        # Figuarts ZERO – Dragon Ball
        ("Figuarts ZERO", "Super Saiyan Son Goku -The Burning Battles-", "Dragon Ball Z", "Standard", "mid", 75),
        ("Figuarts ZERO", "Vegeta Galick Gun", "Dragon Ball Z", "Standard", "mid", 70),

        # ── Additional S.H.Figuarts — Dragon Ball ────────────────────────
        ("S.H.Figuarts", "Vegeta (Saiyan Saga) Galick Gun Pose", "Dragon Ball Z", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Krillin (Battle Damaged)", "Dragon Ball Z", "P-Bandai", "mid", 70),
        ("S.H.Figuarts", "Tien Shinhan & Chiaotzu Set", "Dragon Ball Z", "P-Bandai", "high", 155),
        ("S.H.Figuarts", "Son Goku Kaioken", "Dragon Ball Z", "P-Bandai", "mid", 90),

        # ── Additional Robot Spirits — Gundam Wing ───────────────────────
        ("Robot Spirits", "Wing Gundam Zero Custom ver. A.N.I.M.E.", "Gundam Wing", "P-Bandai", "high", 120),
        ("Robot Spirits", "Tallgeese III ver. A.N.I.M.E.", "Gundam Wing", "P-Bandai", "mid", 95),
        ("Robot Spirits", "Deathscythe Hell Custom ver. A.N.I.M.E.", "Gundam Wing", "P-Bandai", "mid", 100),
        ("Robot Spirits", "Altron Gundam ver. A.N.I.M.E.", "Gundam Wing", "P-Bandai", "mid", 90),

        # ── Additional PG Kits ───────────────────────────────────────────
        ("PG 1/60", "Perfect Strike Gundam (P-Bandai)", "Gundam SEED", "P-Bandai", "grail", 400),
        ("PG 1/60", "Banshee Norn (Final Battle Ver.)", "Gundam Unicorn", "P-Bandai", "grail", 480),

        # === ROUND 2 — S.H.Figuarts Web Exclusives, Robot Spirits, Tamashii Nations, Figure-rise, Other ===

        # ── S.H.Figuarts Web Exclusives (8 items) ─────────────────────────
        ("S.H.Figuarts", "Son Goku Super Saiyan 3 (Renewal)", "Dragon Ball Z", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Vegeta Great Ape (Special Color)", "Dragon Ball Z", "P-Bandai", "high", 180),
        ("S.H.Figuarts", "Kamen Rider Decade Complete 21 (Renewal)", "Kamen Rider Decade", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Kamen Rider Zero-Two IS", "Kamen Rider Zero-One", "P-Bandai", "mid", 90),
        ("S.H.Figuarts", "Roronoa Zoro -King of Hell Three-Sword-", "One Piece", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Monkey D. Luffy (Gear 5 Joy Boy)", "One Piece", "P-Bandai", "high", 130),
        ("S.H.Figuarts", "Sukuna (Jujutsu Kaisen Season 2)", "Jujutsu Kaisen", "P-Bandai", "mid", 95),
        ("S.H.Figuarts", "Gojo Satoru (Hollow Purple)", "Jujutsu Kaisen", "P-Bandai", "mid", 100),

        # ── Robot Spirits Exclusives (7 items) ─────────────────────────────
        ("Robot Spirits", "Freedom Gundam Type F (SEED Freedom)", "Gundam SEED Freedom", "P-Bandai", "high", 130),
        ("Robot Spirits", "Mighty Strike Freedom Gundam ver. A.N.I.M.E.", "Gundam SEED Freedom", "P-Bandai", "high", 145),
        ("Robot Spirits", "Schwarzette ver. A.N.I.M.E.", "Gundam: Witch from Mercury", "P-Bandai", "mid", 85),
        ("Robot Spirits", "Gundam Aerial (Permet Score 6) ver. A.N.I.M.E.", "Gundam: Witch from Mercury", "P-Bandai", "high", 120),
        ("Robot Spirits", "Turn A Gundam Moonlight Butterfly ver. A.N.I.M.E.", "Turn A Gundam", "P-Bandai", "high", 135),
        ("Robot Spirits", "Unicorn Gundam (Perfectibility) ver. A.N.I.M.E.", "Gundam Unicorn", "P-Bandai", "high", 160),
        ("Robot Spirits", "Nu Gundam (Double Fin Funnel) ver. A.N.I.M.E.", "Gundam CCA", "P-Bandai", "high", 150),

        # ── Tamashii Nations Exclusives (5 items) ──────────────────────────
        ("S.H.Figuarts", "Son Goku Ultra Instinct (TNE 2025)", "Dragon Ball Super", "TNE", "high", 175),
        ("S.H.Figuarts", "Kamen Rider Black Sun (SDCC 2024)", "Kamen Rider Black Sun", "Event Exclusive", "high", 165),
        ("Robot Spirits", "Strike Freedom Gundam (TNE 2025 Pearl Coating)", "Gundam SEED Destiny", "TNE", "high", 180),
        ("Figuarts ZERO", "Roronoa Zoro -King of Hell- (TNE 2025)", "One Piece", "TNE", "high", 165),
        ("Metal Build", "Wing Gundam Zero (EW) Snow White (SDCC 2024)", "Gundam Wing", "Event Exclusive", "grail", 520),

        # ── Figure-rise Standard Exclusives (5 items) ──────────────────────
        ("Figure-rise Standard", "Kamen Rider Geats Magnum Boost (Clear)", "Kamen Rider Geats", "P-Bandai", "mid", 55),
        ("Figure-rise Standard", "Amplified Omnimon X-Antibody", "Digimon", "P-Bandai", "mid", 65),
        ("Figure-rise Standard", "Son Goku SSJ4 (GT)", "Dragon Ball GT", "P-Bandai", "mid", 55),
        ("Figure-rise Standard", "Ultraman Suit Zero Action Ver.", "Ultraman", "P-Bandai", "mid", 50),
        ("Figure-rise Standard", "Amplified Gallantmon Crimson Mode", "Digimon", "P-Bandai", "mid", 65),

        # ── Other Bandai Premium Exclusives (5 items) ──────────────────────
        ("S.H.MonsterArts", "Godzilla (2023 Minus One) Thermae Form", "Godzilla Minus One", "P-Bandai", "high", 160),
        ("S.H.MonsterArts", "Mechagodzilla (Ready Player One)", "Ready Player One", "P-Bandai", "high", 170),
        ("Proplica", "Muzan Kibutsuji Nichirin Blade (Tanjiro)", "Demon Slayer", "P-Bandai", "high", 145),
        ("CSM", "Desire Driver (Kamen Rider Geats)", "Kamen Rider Geats", "P-Bandai", "grail", 380),
        ("Metal Build", "Gundam Calibarn", "Gundam: Witch from Mercury", "P-Bandai", "grail", 350),
    ]

    # Merge helper functions
    items += _additional_metal_build()
    items += _additional_dx_chogokin()
    items += _additional_tamashii_event()
    items += _additional_shf_db_exclusives()
    items += _additional_robot_spirits()
    items += _additional_figuarts_zero_chogokin()
    items += _additional_pbandai_kits()
    items += _additional_shf_jojo_dbsuper()
    items += _additional_robot_spirits_expanded()
    items += _additional_mg_rg_kits()
    items += _additional_shf_kamen_rider_expanded()
    items += _additional_super_sentai_ultraman()
    items += _additional_metal_build_expanded()
    items += _additional_figuarts_zero_expanded()
    items += _additional_bandai_items()
    items += _additional_shf_naruto_op()
    items += _additional_shf_db_complete()
    items += _additional_shf_kamen_rider_heisei()
    items += _additional_shf_kamen_rider_showa()
    items += _additional_sentai_expanded()
    items += _additional_ultraman_expanded()
    items += _additional_robot_spirits_eva()
    items += _additional_robot_spirits_gundam_uc()
    items += _additional_robot_spirits_wfm()
    items += _additional_figure_rise()
    items += _additional_pbandai_hg_expanded()
    items += _additional_mg_expanded()
    items += _additional_shf_misc_anime()
    items += _additional_dx_chogokin_expanded()
    items += _additional_soul_chogokin_expanded()
    items += _additional_metal_robot_spirits()
    items += _additional_rg_expanded()
    items += _additional_pg_expanded()
    items += _additional_shf_dbgt_movies()
    items += _additional_figuarts_zero_op()
    items += _additional_gunpla_special()
    items += _additional_shf_tokusatsu_misc()
    items += _additional_tamashii_event_expanded()
    items += _additional_metal_build_more()
    items += _additional_miscellaneous_bandai()
    items += _additional_csm_proplica_sailor()
    items += _additional_sdcs_and_misc_kits()
    items += _additional_tamashii_2025_expansion()
    items += _round7_bandai_expansion()
    items += _expansion_700_gunpla_pbandai()
    items += _expansion_700_super_robot_chogokin()
    items += _expansion_700_shf_marvel_starwars()
    items += _expansion_700_shmonsterarts()
    items += _expansion_700_dx_chogokin_metal_build()
    items += _expansion_700_robot_spirits_fmp()
    items += _expansion_700_csm_proplica_candy()
    items += _expansion_700_figurerise_misc()
    items += _expansion_700_shf_anime_tokusatsu()

    catalog = []
    for line, name, franchise, exclusive_type, tier, price in items:
        catalog.append({
            "line": line,
            "name": name,
            "franchise": franchise,
            "exclusive_type": exclusive_type,
            "rarity_tier": tier,
            "price_eur": price,
        })
    # Deduplicate by ('line', 'name', 'exclusive_type') (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = (item["line"], item["name"], item["exclusive_type"])
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


def item_to_catalog_item(item: dict) -> CatalogItem:
    line = item["line"]
    name = item["name"]
    franchise = item["franchise"]
    exclusive_type = item["exclusive_type"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{line}-{name}"),
        title=f"{line} {name}",
        set_code=slugify(line),
        brand="Bandai",
        rarity=item["rarity_tier"].title(),
        notes=f"{line} | {franchise}" + (f" | {exclusive_type}" if exclusive_type else ""),
        attributes_json={
            "line": line,
            "franchise": franchise,
            "exclusive_type": exclusive_type,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    exclusive_type = item["exclusive_type"]
    edition_scores = {
        "P-Bandai": 0.80,
        "TNE": 0.90,
        "Event Exclusive": 0.95,
        "Standard": 0.40,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_scores.get(exclusive_type, 0.5),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Bandai Premium catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Bandai Premium Import ===")

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

    logger.info(f"\n=== Bandai Premium Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
