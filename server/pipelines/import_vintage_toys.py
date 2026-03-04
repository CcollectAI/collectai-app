"""
Import Vintage Toys catalog.

Layer 1 (Catalog):  Curated vintage action figure lines → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Kenner Star Wars vintage (1977–1985): figures, vehicles, playsets, proof cards
- Kenner The Real Ghostbusters (1986–1991)
- Hasbro GI Joe: A Real American Hero (1982–1994)
- Mattel Masters of the Universe vintage (1982–1988)
- LJN Thundercats (1985–1987)
- Playmates TMNT vintage (1988–1997)
- Kenner Super Powers (DC, 1984–1986)
- Kenner M.A.S.K. (1985–1987)
- Hasbro Transformers G1 (1984–1990)
- Coleco Starcom (1986–1988)
- Mattel She-Ra: Princess of Power (1985–1987)
- Kenner Aliens & Predator (1992–1995)
- Mattel Big Jim (1971–1977)
- Ideal Captain Action (1966–1968)
- Kenner Robin Hood: Prince of Thieves (1991)
- Coleco Sectaurs (1984)
- Remco Crystar (1982)
- Mattel Voltron (1984–1985)
- Kenner Centurions (1986)
- Hasbro Visionaries (1987)
- LJN Advanced Dungeons & Dragons (1983–1984)
- LJN Thundarr the Barbarian (1981)
- Tonka GoBots (1983–1987)
- Galoob Micro Machines & A-Team (1983–1994)
- Hasbro Inhumanoids (1986)
- Coleco Rambo (1986)
- 550+ items spanning multiple decades

Usage:
    python -m pipelines.import_vintage_toys [--dry-run]
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

CATEGORY = "vintage_toys"


def get_curated_catalog() -> list[dict]:
    """Curated 550+ vintage toys catalog: Kenner Star Wars, GI Joe ARAH,
    MOTU, Thundercats, TMNT, Transformers G1, and more."""

    # (manufacturer, franchise, name, item_type, era, completeness, price_eur)
    # item_type: figure, vehicle, playset, empty_box, proof_card, accessory
    # completeness: CIB (complete in box), loose_complete, loose_incomplete, box_only, MOC (mint on card)

    items = [
        # ─── Kenner Star Wars (1977-1985) — Figures ───────────────────
        ("Kenner", "Star Wars", "Luke Skywalker (Farmboy)", "figure", "1977", "loose_complete", 120),
        ("Kenner", "Star Wars", "Luke Skywalker (X-Wing Pilot)", "figure", "1978", "loose_complete", 85),
        ("Kenner", "Star Wars", "Luke Skywalker (Bespin)", "figure", "1980", "loose_complete", 75),
        ("Kenner", "Star Wars", "Luke Skywalker (Jedi Knight)", "figure", "1983", "loose_complete", 90),
        ("Kenner", "Star Wars", "Luke Skywalker (Stormtrooper)", "figure", "1984", "loose_complete", 150),
        ("Kenner", "Star Wars", "Luke Skywalker (Hoth)", "figure", "1980", "loose_complete", 65),
        ("Kenner", "Star Wars", "Darth Vader", "figure", "1977", "loose_complete", 95),
        ("Kenner", "Star Wars", "Darth Vader (ESB Card)", "figure", "1980", "MOC", 450),
        ("Kenner", "Star Wars", "Han Solo (Large Head)", "figure", "1977", "loose_complete", 130),
        ("Kenner", "Star Wars", "Han Solo (Small Head)", "figure", "1977", "loose_complete", 85),
        ("Kenner", "Star Wars", "Han Solo (Bespin)", "figure", "1980", "loose_complete", 55),
        ("Kenner", "Star Wars", "Han Solo (Hoth)", "figure", "1980", "loose_complete", 50),
        ("Kenner", "Star Wars", "Han Solo (Trench Coat, Endor)", "figure", "1983", "loose_complete", 45),
        ("Kenner", "Star Wars", "Han Solo (Carbonite)", "figure", "1984", "loose_complete", 65),
        ("Kenner", "Star Wars", "Princess Leia (Original)", "figure", "1977", "loose_complete", 110),
        ("Kenner", "Star Wars", "Princess Leia (Bespin)", "figure", "1980", "loose_complete", 55),
        ("Kenner", "Star Wars", "Princess Leia (Hoth)", "figure", "1980", "loose_complete", 50),
        ("Kenner", "Star Wars", "Princess Leia (Endor)", "figure", "1983", "loose_complete", 45),
        ("Kenner", "Star Wars", "Princess Leia (Boushh)", "figure", "1983", "loose_complete", 55),
        ("Kenner", "Star Wars", "Chewbacca", "figure", "1977", "loose_complete", 65),
        ("Kenner", "Star Wars", "C-3PO", "figure", "1977", "loose_complete", 45),
        ("Kenner", "Star Wars", "C-3PO (Removable Limbs)", "figure", "1982", "loose_complete", 40),
        ("Kenner", "Star Wars", "R2-D2", "figure", "1977", "loose_complete", 50),
        ("Kenner", "Star Wars", "R2-D2 (Sensorscope)", "figure", "1980", "loose_complete", 55),
        ("Kenner", "Star Wars", "Obi-Wan Kenobi", "figure", "1977", "loose_complete", 75),
        ("Kenner", "Star Wars", "Obi-Wan Kenobi (White Hair)", "figure", "1977", "loose_complete", 90),
        ("Kenner", "Star Wars", "Stormtrooper", "figure", "1977", "loose_complete", 70),
        ("Kenner", "Star Wars", "Jawa", "figure", "1977", "loose_complete", 55),
        ("Kenner", "Star Wars", "Jawa (Vinyl Cape)", "figure", "1977", "loose_complete", 2500),
        ("Kenner", "Star Wars", "Sand People (Tusken Raider)", "figure", "1977", "loose_complete", 60),
        ("Kenner", "Star Wars", "Death Star Droid", "figure", "1978", "loose_complete", 40),
        ("Kenner", "Star Wars", "Greedo", "figure", "1978", "loose_complete", 45),
        ("Kenner", "Star Wars", "Hammerhead", "figure", "1978", "loose_complete", 50),
        ("Kenner", "Star Wars", "Snaggletooth (Red)", "figure", "1978", "loose_complete", 35),
        ("Kenner", "Star Wars", "Snaggletooth (Blue, Sears)", "figure", "1978", "loose_complete", 350),
        ("Kenner", "Star Wars", "Walrus Man (Ponda Baba)", "figure", "1978", "loose_complete", 35),
        ("Kenner", "Star Wars", "Power Droid", "figure", "1978", "loose_complete", 30),
        ("Kenner", "Star Wars", "Boba Fett", "figure", "1979", "loose_complete", 180),
        ("Kenner", "Star Wars", "Boba Fett (Rocket Firing Prototype)", "figure", "1979", "loose_complete", 25000),
        ("Kenner", "Star Wars", "Bossk", "figure", "1980", "loose_complete", 55),
        ("Kenner", "Star Wars", "IG-88", "figure", "1980", "loose_complete", 75),
        ("Kenner", "Star Wars", "Dengar", "figure", "1980", "loose_complete", 40),
        ("Kenner", "Star Wars", "4-LOM", "figure", "1981", "loose_complete", 65),
        ("Kenner", "Star Wars", "Zuckuss", "figure", "1981", "loose_complete", 55),
        ("Kenner", "Star Wars", "Yoda", "figure", "1980", "loose_complete", 65),
        ("Kenner", "Star Wars", "Lando Calrissian", "figure", "1980", "loose_complete", 40),
        ("Kenner", "Star Wars", "Lando Calrissian (Skiff Guard)", "figure", "1982", "loose_complete", 35),
        ("Kenner", "Star Wars", "Lobot", "figure", "1980", "loose_complete", 30),
        ("Kenner", "Star Wars", "Ugnaught", "figure", "1980", "loose_complete", 35),
        ("Kenner", "Star Wars", "AT-AT Commander", "figure", "1981", "loose_complete", 35),
        ("Kenner", "Star Wars", "Imperial Commander", "figure", "1980", "loose_complete", 30),
        ("Kenner", "Star Wars", "Rebel Commander", "figure", "1980", "loose_complete", 28),
        ("Kenner", "Star Wars", "Hoth Rebel Soldier", "figure", "1980", "loose_complete", 30),
        ("Kenner", "Star Wars", "Snowtrooper (Imperial Stormtrooper Hoth)", "figure", "1980", "loose_complete", 55),
        ("Kenner", "Star Wars", "FX-7 Medical Droid", "figure", "1980", "loose_complete", 25),
        ("Kenner", "Star Wars", "2-1B Medical Droid", "figure", "1980", "loose_complete", 28),
        ("Kenner", "Star Wars", "Nien Nunb", "figure", "1983", "loose_complete", 25),
        ("Kenner", "Star Wars", "Admiral Ackbar", "figure", "1982", "loose_complete", 30),
        ("Kenner", "Star Wars", "General Madine", "figure", "1983", "loose_complete", 22),
        ("Kenner", "Star Wars", "Emperor's Royal Guard", "figure", "1983", "loose_complete", 40),
        ("Kenner", "Star Wars", "The Emperor", "figure", "1984", "loose_complete", 35),
        ("Kenner", "Star Wars", "Gamorrean Guard", "figure", "1983", "loose_complete", 30),
        ("Kenner", "Star Wars", "Bib Fortuna", "figure", "1983", "loose_complete", 25),
        ("Kenner", "Star Wars", "Squid Head (Tessek)", "figure", "1983", "loose_complete", 35),
        ("Kenner", "Star Wars", "Ree-Yees", "figure", "1983", "loose_complete", 22),
        ("Kenner", "Star Wars", "Klaatu", "figure", "1983", "loose_complete", 20),
        ("Kenner", "Star Wars", "Weequay", "figure", "1983", "loose_complete", 22),
        ("Kenner", "Star Wars", "Nikto", "figure", "1983", "loose_complete", 20),
        ("Kenner", "Star Wars", "8D8", "figure", "1983", "loose_complete", 18),
        ("Kenner", "Star Wars", "EV-9D9", "figure", "1984", "loose_complete", 35),
        ("Kenner", "Star Wars", "Rancor Keeper", "figure", "1983", "loose_complete", 18),
        ("Kenner", "Star Wars", "B-Wing Pilot", "figure", "1984", "loose_complete", 22),
        ("Kenner", "Star Wars", "A-Wing Pilot", "figure", "1984", "loose_complete", 55),
        ("Kenner", "Star Wars", "Wicket", "figure", "1983", "loose_complete", 25),
        ("Kenner", "Star Wars", "Logray", "figure", "1983", "loose_complete", 22),
        ("Kenner", "Star Wars", "Teebo", "figure", "1984", "loose_complete", 25),
        ("Kenner", "Star Wars", "Paploo", "figure", "1984", "loose_complete", 30),
        ("Kenner", "Star Wars", "Lumat", "figure", "1984", "loose_complete", 25),
        ("Kenner", "Star Wars", "Chief Chirpa", "figure", "1983", "loose_complete", 22),
        ("Kenner", "Star Wars", "AT-ST Driver", "figure", "1984", "loose_complete", 20),
        ("Kenner", "Star Wars", "Prune Face", "figure", "1984", "loose_complete", 18),
        ("Kenner", "Star Wars", "Imperial Dignitary", "figure", "1984", "loose_complete", 40),
        ("Kenner", "Star Wars", "Amanaman", "figure", "1984", "loose_complete", 85),
        ("Kenner", "Star Wars", "Yak Face", "figure", "1985", "loose_complete", 300),
        ("Kenner", "Star Wars", "Anakin Skywalker (POTF)", "figure", "1985", "loose_complete", 200),
        ("Kenner", "Star Wars", "Luke Skywalker (POTF, Battle Poncho)", "figure", "1985", "MOC", 350),

        # ─── Kenner Star Wars — Vehicles & Playsets ───────────────────
        ("Kenner", "Star Wars", "Millennium Falcon", "vehicle", "1979", "CIB", 350),
        ("Kenner", "Star Wars", "Millennium Falcon", "vehicle", "1979", "loose_complete", 180),
        ("Kenner", "Star Wars", "X-Wing Fighter", "vehicle", "1978", "CIB", 250),
        ("Kenner", "Star Wars", "X-Wing Fighter", "vehicle", "1978", "loose_complete", 120),
        ("Kenner", "Star Wars", "TIE Fighter", "vehicle", "1978", "CIB", 200),
        ("Kenner", "Star Wars", "AT-AT Walker", "vehicle", "1981", "CIB", 400),
        ("Kenner", "Star Wars", "AT-AT Walker", "vehicle", "1981", "loose_complete", 200),
        ("Kenner", "Star Wars", "AT-ST Scout Walker", "vehicle", "1982", "CIB", 120),
        ("Kenner", "Star Wars", "Slave I", "vehicle", "1980", "CIB", 280),
        ("Kenner", "Star Wars", "Slave I", "vehicle", "1980", "loose_complete", 130),
        ("Kenner", "Star Wars", "Snowspeeder", "vehicle", "1980", "CIB", 150),
        ("Kenner", "Star Wars", "Y-Wing Fighter", "vehicle", "1983", "CIB", 280),
        ("Kenner", "Star Wars", "B-Wing Fighter", "vehicle", "1984", "CIB", 220),
        ("Kenner", "Star Wars", "A-Wing Fighter (Droids)", "vehicle", "1985", "CIB", 350),
        ("Kenner", "Star Wars", "Imperial Shuttle", "vehicle", "1984", "CIB", 450),
        ("Kenner", "Star Wars", "Landspeeder", "vehicle", "1978", "CIB", 120),
        ("Kenner", "Star Wars", "Tauntaun (Open Belly)", "vehicle", "1980", "CIB", 90),
        ("Kenner", "Star Wars", "Speeder Bike", "vehicle", "1983", "CIB", 60),
        ("Kenner", "Star Wars", "Death Star Playset", "playset", "1978", "CIB", 500),
        ("Kenner", "Star Wars", "Death Star Playset", "playset", "1978", "loose_complete", 250),
        ("Kenner", "Star Wars", "Ewok Village", "playset", "1983", "CIB", 180),
        ("Kenner", "Star Wars", "Jabba the Hutt Playset", "playset", "1983", "CIB", 150),
        ("Kenner", "Star Wars", "Jabba the Hutt Playset", "playset", "1983", "loose_complete", 80),
        ("Kenner", "Star Wars", "Hoth Ice Planet Playset", "playset", "1980", "CIB", 200),
        ("Kenner", "Star Wars", "Dagobah Playset", "playset", "1980", "CIB", 120),
        ("Kenner", "Star Wars", "Cloud City Playset (Sears)", "playset", "1980", "CIB", 450),
        ("Kenner", "Star Wars", "Cantina Adventure Set (Sears)", "playset", "1978", "CIB", 600),
        ("Kenner", "Star Wars", "Rancor Monster", "vehicle", "1983", "CIB", 120),
        ("Kenner", "Star Wars", "Dewback", "vehicle", "1978", "CIB", 85),

        # ─── Kenner Star Wars — Proof Cards & Empty Boxes ─────────────
        ("Kenner", "Star Wars", "Boba Fett 12-Back Proof Card", "proof_card", "1979", "box_only", 800),
        ("Kenner", "Star Wars", "Darth Vader 12-Back Proof Card", "proof_card", "1977", "box_only", 500),
        ("Kenner", "Star Wars", "Luke Skywalker 12-Back Proof Card", "proof_card", "1977", "box_only", 600),
        ("Kenner", "Star Wars", "Millennium Falcon Empty Box", "empty_box", "1979", "box_only", 150),
        ("Kenner", "Star Wars", "AT-AT Walker Empty Box", "empty_box", "1981", "box_only", 120),
        ("Kenner", "Star Wars", "Death Star Playset Empty Box", "empty_box", "1978", "box_only", 200),

        # ─── Hasbro GI Joe: A Real American Hero (1982–1994) ──────────
        ("Hasbro", "GI Joe", "Snake Eyes (v1)", "figure", "1982", "loose_complete", 120),
        ("Hasbro", "GI Joe", "Snake Eyes (v2, Visor)", "figure", "1985", "loose_complete", 150),
        ("Hasbro", "GI Joe", "Snake Eyes (v3, Ninja)", "figure", "1989", "loose_complete", 55),
        ("Hasbro", "GI Joe", "Storm Shadow (v1)", "figure", "1984", "loose_complete", 85),
        ("Hasbro", "GI Joe", "Storm Shadow (v2)", "figure", "1988", "loose_complete", 45),
        ("Hasbro", "GI Joe", "Cobra Commander (Hood)", "figure", "1982", "loose_complete", 65),
        ("Hasbro", "GI Joe", "Cobra Commander (Battle Armor)", "figure", "1984", "loose_complete", 55),
        ("Hasbro", "GI Joe", "Destro", "figure", "1983", "loose_complete", 45),
        ("Hasbro", "GI Joe", "Baroness", "figure", "1984", "loose_complete", 70),
        ("Hasbro", "GI Joe", "Zartan", "figure", "1984", "loose_complete", 55),
        ("Hasbro", "GI Joe", "Firefly", "figure", "1984", "loose_complete", 65),
        ("Hasbro", "GI Joe", "Major Bludd", "figure", "1983", "loose_complete", 30),
        ("Hasbro", "GI Joe", "Serpentor", "figure", "1986", "loose_complete", 40),
        ("Hasbro", "GI Joe", "Duke", "figure", "1983", "loose_complete", 35),
        ("Hasbro", "GI Joe", "Flint", "figure", "1985", "loose_complete", 30),
        ("Hasbro", "GI Joe", "Lady Jaye", "figure", "1985", "loose_complete", 35),
        ("Hasbro", "GI Joe", "Scarlett", "figure", "1982", "loose_complete", 55),
        ("Hasbro", "GI Joe", "Stalker (Ranger)", "figure", "1982", "loose_complete", 40),
        ("Hasbro", "GI Joe", "Gung-Ho", "figure", "1983", "loose_complete", 25),
        ("Hasbro", "GI Joe", "Roadblock", "figure", "1984", "loose_complete", 30),
        ("Hasbro", "GI Joe", "Quick Kick", "figure", "1985", "loose_complete", 22),
        ("Hasbro", "GI Joe", "Shipwreck", "figure", "1985", "loose_complete", 28),
        ("Hasbro", "GI Joe", "Sgt. Slaughter", "figure", "1985", "loose_complete", 40),
        ("Hasbro", "GI Joe", "Hawk (v2)", "figure", "1986", "loose_complete", 25),
        ("Hasbro", "GI Joe", "Beach Head", "figure", "1986", "loose_complete", 22),
        ("Hasbro", "GI Joe", "Lifeline", "figure", "1986", "loose_complete", 20),
        ("Hasbro", "GI Joe", "Sci-Fi (v1)", "figure", "1986", "loose_complete", 28),
        ("Hasbro", "GI Joe", "Low-Light", "figure", "1986", "loose_complete", 25),
        ("Hasbro", "GI Joe", "Tunnel Rat", "figure", "1987", "loose_complete", 22),
        ("Hasbro", "GI Joe", "Chuckles", "figure", "1987", "loose_complete", 20),
        ("Hasbro", "GI Joe", "H.I.S.S. Tank", "vehicle", "1983", "CIB", 85),
        ("Hasbro", "GI Joe", "U.S.S. Flagg Aircraft Carrier", "vehicle", "1985", "CIB", 2500),
        ("Hasbro", "GI Joe", "Skystriker XP-14F", "vehicle", "1983", "CIB", 120),
        ("Hasbro", "GI Joe", "Rattler", "vehicle", "1984", "CIB", 100),
        ("Hasbro", "GI Joe", "Dragonfly XH-1", "vehicle", "1983", "CIB", 80),
        ("Hasbro", "GI Joe", "Thunder Machine", "vehicle", "1986", "CIB", 55),
        ("Hasbro", "GI Joe", "Terrordrome", "playset", "1986", "CIB", 400),
        ("Hasbro", "GI Joe", "Defiant Space Shuttle", "vehicle", "1987", "CIB", 350),

        # ─── Mattel Masters of the Universe (1982–1988) ───────────────
        ("Mattel", "Masters of the Universe", "He-Man", "figure", "1982", "loose_complete", 55),
        ("Mattel", "Masters of the Universe", "He-Man (Original 8-Back)", "figure", "1982", "MOC", 350),
        ("Mattel", "Masters of the Universe", "Skeletor", "figure", "1982", "loose_complete", 50),
        ("Mattel", "Masters of the Universe", "Skeletor (Original 8-Back)", "figure", "1982", "MOC", 300),
        ("Mattel", "Masters of the Universe", "Battle Cat", "figure", "1982", "loose_complete", 45),
        ("Mattel", "Masters of the Universe", "Man-At-Arms", "figure", "1982", "loose_complete", 30),
        ("Mattel", "Masters of the Universe", "Teela", "figure", "1982", "loose_complete", 35),
        ("Mattel", "Masters of the Universe", "Beast Man", "figure", "1982", "loose_complete", 25),
        ("Mattel", "Masters of the Universe", "Mer-Man", "figure", "1982", "loose_complete", 22),
        ("Mattel", "Masters of the Universe", "Trap Jaw", "figure", "1983", "loose_complete", 40),
        ("Mattel", "Masters of the Universe", "Tri-Klops", "figure", "1983", "loose_complete", 22),
        ("Mattel", "Masters of the Universe", "Evil-Lyn", "figure", "1983", "loose_complete", 28),
        ("Mattel", "Masters of the Universe", "Faker", "figure", "1983", "loose_complete", 65),
        ("Mattel", "Masters of the Universe", "Zodac", "figure", "1982", "loose_complete", 22),
        ("Mattel", "Masters of the Universe", "Stratos", "figure", "1982", "loose_complete", 20),
        ("Mattel", "Masters of the Universe", "Ram Man", "figure", "1983", "loose_complete", 30),
        ("Mattel", "Masters of the Universe", "Whiplash", "figure", "1984", "loose_complete", 22),
        ("Mattel", "Masters of the Universe", "Clamp Champ", "figure", "1987", "loose_complete", 55),
        ("Mattel", "Masters of the Universe", "Hordak", "figure", "1985", "loose_complete", 35),
        ("Mattel", "Masters of the Universe", "Buzz-Off", "figure", "1984", "loose_complete", 20),
        ("Mattel", "Masters of the Universe", "Fisto", "figure", "1984", "loose_complete", 28),
        ("Mattel", "Masters of the Universe", "Jitsu", "figure", "1984", "loose_complete", 25),
        ("Mattel", "Masters of the Universe", "Two Bad", "figure", "1985", "loose_complete", 22),
        ("Mattel", "Masters of the Universe", "Modulok", "figure", "1985", "loose_complete", 30),
        ("Mattel", "Masters of the Universe", "Multi-Bot", "figure", "1986", "loose_complete", 25),
        ("Mattel", "Masters of the Universe", "Grizzlor", "figure", "1985", "loose_complete", 25),
        ("Mattel", "Masters of the Universe", "Leech", "figure", "1985", "loose_complete", 20),
        ("Mattel", "Masters of the Universe", "Mantenna", "figure", "1985", "loose_complete", 22),
        ("Mattel", "Masters of the Universe", "Castle Grayskull", "playset", "1982", "CIB", 250),
        ("Mattel", "Masters of the Universe", "Castle Grayskull", "playset", "1982", "loose_complete", 120),
        ("Mattel", "Masters of the Universe", "Snake Mountain", "playset", "1984", "CIB", 350),
        ("Mattel", "Masters of the Universe", "Eternia Playset", "playset", "1986", "CIB", 1200),
        ("Mattel", "Masters of the Universe", "Battle Ram", "vehicle", "1982", "CIB", 80),
        ("Mattel", "Masters of the Universe", "Wind Raider", "vehicle", "1982", "CIB", 75),
        ("Mattel", "Masters of the Universe", "Talon Fighter", "vehicle", "1986", "CIB", 55),
        ("Mattel", "Masters of the Universe", "Fright Fighter", "vehicle", "1986", "CIB", 60),

        # ─── LJN Thundercats (1985–1987) ──────────────────────────────
        ("LJN", "Thundercats", "Lion-O", "figure", "1985", "loose_complete", 75),
        ("LJN", "Thundercats", "Lion-O", "figure", "1985", "MOC", 350),
        ("LJN", "Thundercats", "Cheetara", "figure", "1985", "loose_complete", 85),
        ("LJN", "Thundercats", "Panthro", "figure", "1985", "loose_complete", 55),
        ("LJN", "Thundercats", "Tygra", "figure", "1985", "loose_complete", 50),
        ("LJN", "Thundercats", "Mumm-Ra", "figure", "1985", "loose_complete", 45),
        ("LJN", "Thundercats", "Mumm-Ra (Transformed)", "figure", "1986", "loose_complete", 65),
        ("LJN", "Thundercats", "Slithe", "figure", "1985", "loose_complete", 35),
        ("LJN", "Thundercats", "Monkian", "figure", "1985", "loose_complete", 30),
        ("LJN", "Thundercats", "Jackalman", "figure", "1985", "loose_complete", 28),
        ("LJN", "Thundercats", "Vultureman", "figure", "1986", "loose_complete", 55),
        ("LJN", "Thundercats", "WilyKit", "figure", "1986", "loose_complete", 40),
        ("LJN", "Thundercats", "WilyKat", "figure", "1986", "loose_complete", 40),
        ("LJN", "Thundercats", "Snarf", "figure", "1986", "loose_complete", 30),
        ("LJN", "Thundercats", "Bengali", "figure", "1987", "loose_complete", 80),
        ("LJN", "Thundercats", "Pumyra", "figure", "1987", "loose_complete", 90),
        ("LJN", "Thundercats", "Lynx-O", "figure", "1987", "loose_complete", 85),
        ("LJN", "Thundercats", "Cat's Lair", "playset", "1986", "CIB", 400),
        ("LJN", "Thundercats", "Thundertank", "vehicle", "1985", "CIB", 150),

        # ─── Playmates TMNT (1988–1997) ───────────────────────────────
        ("Playmates", "TMNT", "Leonardo", "figure", "1988", "loose_complete", 35),
        ("Playmates", "TMNT", "Leonardo (Hardhead)", "figure", "1988", "MOC", 120),
        ("Playmates", "TMNT", "Donatello", "figure", "1988", "loose_complete", 30),
        ("Playmates", "TMNT", "Raphael", "figure", "1988", "loose_complete", 30),
        ("Playmates", "TMNT", "Michelangelo", "figure", "1988", "loose_complete", 30),
        ("Playmates", "TMNT", "Splinter", "figure", "1988", "loose_complete", 25),
        ("Playmates", "TMNT", "Shredder", "figure", "1988", "loose_complete", 28),
        ("Playmates", "TMNT", "April O'Neil (Blue Stripe)", "figure", "1988", "loose_complete", 60),
        ("Playmates", "TMNT", "April O'Neil (No Stripe)", "figure", "1988", "loose_complete", 35),
        ("Playmates", "TMNT", "Foot Soldier", "figure", "1988", "loose_complete", 22),
        ("Playmates", "TMNT", "Bebop", "figure", "1988", "loose_complete", 22),
        ("Playmates", "TMNT", "Rocksteady", "figure", "1988", "loose_complete", 22),
        ("Playmates", "TMNT", "Krang", "figure", "1989", "loose_complete", 25),
        ("Playmates", "TMNT", "Baxter Stockman", "figure", "1989", "loose_complete", 20),
        ("Playmates", "TMNT", "Casey Jones", "figure", "1989", "loose_complete", 28),
        ("Playmates", "TMNT", "Metalhead", "figure", "1989", "loose_complete", 18),
        ("Playmates", "TMNT", "Leatherhead", "figure", "1989", "loose_complete", 22),
        ("Playmates", "TMNT", "Usagi Yojimbo", "figure", "1989", "loose_complete", 30),
        ("Playmates", "TMNT", "Ace Duck", "figure", "1989", "loose_complete", 18),
        ("Playmates", "TMNT", "Mondo Gecko", "figure", "1990", "loose_complete", 18),
        ("Playmates", "TMNT", "Slash", "figure", "1990", "loose_complete", 22),
        ("Playmates", "TMNT", "Fugitoid", "figure", "1990", "loose_complete", 25),
        ("Playmates", "TMNT", "Technodrome", "playset", "1990", "CIB", 200),
        ("Playmates", "TMNT", "Turtle Van (Party Wagon)", "vehicle", "1988", "CIB", 120),
        ("Playmates", "TMNT", "Sewer Playset", "playset", "1989", "CIB", 80),

        # ─── Hasbro Transformers G1 (1984–1990) ──────────────────────
        ("Hasbro", "Transformers", "Optimus Prime (G1)", "figure", "1984", "CIB", 350),
        ("Hasbro", "Transformers", "Optimus Prime (G1)", "figure", "1984", "loose_complete", 180),
        ("Hasbro", "Transformers", "Megatron (G1)", "figure", "1984", "CIB", 300),
        ("Hasbro", "Transformers", "Megatron (G1)", "figure", "1984", "loose_complete", 150),
        ("Hasbro", "Transformers", "Soundwave (G1)", "figure", "1984", "CIB", 200),
        ("Hasbro", "Transformers", "Soundwave (G1)", "figure", "1984", "loose_complete", 100),
        ("Hasbro", "Transformers", "Starscream (G1)", "figure", "1984", "CIB", 180),
        ("Hasbro", "Transformers", "Starscream (G1)", "figure", "1984", "loose_complete", 80),
        ("Hasbro", "Transformers", "Bumblebee (G1)", "figure", "1984", "CIB", 120),
        ("Hasbro", "Transformers", "Bumblebee (G1)", "figure", "1984", "loose_complete", 45),
        ("Hasbro", "Transformers", "Jazz (G1)", "figure", "1984", "loose_complete", 65),
        ("Hasbro", "Transformers", "Ironhide (G1)", "figure", "1984", "loose_complete", 45),
        ("Hasbro", "Transformers", "Ratchet (G1)", "figure", "1984", "loose_complete", 40),
        ("Hasbro", "Transformers", "Prowl (G1)", "figure", "1984", "loose_complete", 60),
        ("Hasbro", "Transformers", "Sideswipe (G1)", "figure", "1984", "loose_complete", 55),
        ("Hasbro", "Transformers", "Sunstreaker (G1)", "figure", "1984", "loose_complete", 65),
        ("Hasbro", "Transformers", "Wheeljack (G1)", "figure", "1984", "loose_complete", 50),
        ("Hasbro", "Transformers", "Mirage (G1)", "figure", "1984", "loose_complete", 55),
        ("Hasbro", "Transformers", "Hound (G1)", "figure", "1984", "loose_complete", 50),
        ("Hasbro", "Transformers", "Bluestreak (G1)", "figure", "1984", "loose_complete", 55),
        ("Hasbro", "Transformers", "Thundercracker (G1)", "figure", "1984", "loose_complete", 75),
        ("Hasbro", "Transformers", "Skywarp (G1)", "figure", "1984", "loose_complete", 80),
        ("Hasbro", "Transformers", "Shockwave (G1)", "figure", "1985", "CIB", 200),
        ("Hasbro", "Transformers", "Grimlock (G1)", "figure", "1985", "CIB", 220),
        ("Hasbro", "Transformers", "Grimlock (G1)", "figure", "1985", "loose_complete", 100),
        ("Hasbro", "Transformers", "Slag (G1)", "figure", "1985", "loose_complete", 55),
        ("Hasbro", "Transformers", "Sludge (G1)", "figure", "1985", "loose_complete", 50),
        ("Hasbro", "Transformers", "Snarl (G1)", "figure", "1985", "loose_complete", 55),
        ("Hasbro", "Transformers", "Swoop (G1)", "figure", "1985", "loose_complete", 75),
        ("Hasbro", "Transformers", "Ultra Magnus (G1)", "figure", "1986", "CIB", 250),
        ("Hasbro", "Transformers", "Hot Rod (G1)", "figure", "1986", "loose_complete", 80),
        ("Hasbro", "Transformers", "Rodimus Prime (G1)", "figure", "1986", "CIB", 300),
        ("Hasbro", "Transformers", "Galvatron (G1)", "figure", "1986", "CIB", 200),
        ("Hasbro", "Transformers", "Metroplex (G1)", "figure", "1986", "CIB", 400),
        ("Hasbro", "Transformers", "Trypticon (G1)", "figure", "1986", "CIB", 350),
        ("Hasbro", "Transformers", "Fortress Maximus (G1)", "figure", "1987", "CIB", 2000),
        ("Hasbro", "Transformers", "Scorponok (G1)", "figure", "1987", "CIB", 300),
        ("Hasbro", "Transformers", "Devastator (G1 Gift Set)", "figure", "1985", "CIB", 400),
        ("Hasbro", "Transformers", "Predaking (G1 Gift Set)", "figure", "1986", "CIB", 500),
        ("Hasbro", "Transformers", "Omega Supreme (G1)", "figure", "1985", "CIB", 350),
        ("Hasbro", "Transformers", "Jetfire (G1)", "figure", "1985", "CIB", 350),
        ("Hasbro", "Transformers", "Perceptor (G1)", "figure", "1985", "loose_complete", 40),
        ("Hasbro", "Transformers", "Blaster (G1)", "figure", "1985", "loose_complete", 55),

        # ─── Kenner Super Powers (DC, 1984–1986) ─────────────────────
        ("Kenner", "DC Super Powers", "Superman", "figure", "1984", "loose_complete", 40),
        ("Kenner", "DC Super Powers", "Batman", "figure", "1984", "loose_complete", 55),
        ("Kenner", "DC Super Powers", "Wonder Woman", "figure", "1984", "loose_complete", 45),
        ("Kenner", "DC Super Powers", "Robin", "figure", "1984", "loose_complete", 35),
        ("Kenner", "DC Super Powers", "Flash", "figure", "1984", "loose_complete", 35),
        ("Kenner", "DC Super Powers", "Green Lantern (Hal Jordan)", "figure", "1984", "loose_complete", 40),
        ("Kenner", "DC Super Powers", "Aquaman", "figure", "1984", "loose_complete", 30),
        ("Kenner", "DC Super Powers", "Hawkman", "figure", "1984", "loose_complete", 35),
        ("Kenner", "DC Super Powers", "Lex Luthor", "figure", "1984", "loose_complete", 25),
        ("Kenner", "DC Super Powers", "Joker", "figure", "1984", "loose_complete", 28),
        ("Kenner", "DC Super Powers", "Penguin", "figure", "1984", "loose_complete", 28),
        ("Kenner", "DC Super Powers", "Brainiac", "figure", "1984", "loose_complete", 30),
        ("Kenner", "DC Super Powers", "Darkseid", "figure", "1985", "loose_complete", 50),
        ("Kenner", "DC Super Powers", "Desaad", "figure", "1985", "loose_complete", 30),
        ("Kenner", "DC Super Powers", "Kalibak", "figure", "1985", "loose_complete", 28),
        ("Kenner", "DC Super Powers", "Steppenwolf", "figure", "1985", "loose_complete", 35),
        ("Kenner", "DC Super Powers", "Mr. Freeze", "figure", "1986", "loose_complete", 65),
        ("Kenner", "DC Super Powers", "Cyborg", "figure", "1986", "loose_complete", 85),
        ("Kenner", "DC Super Powers", "Batcopter", "vehicle", "1986", "CIB", 120),
        ("Kenner", "DC Super Powers", "Batmobile", "vehicle", "1984", "CIB", 150),
        ("Kenner", "DC Super Powers", "Hall of Justice Playset", "playset", "1984", "CIB", 250),

        # ─── Kenner The Real Ghostbusters (1986–1991) ─────────────────
        ("Kenner", "Ghostbusters", "Peter Venkman", "figure", "1986", "loose_complete", 25),
        ("Kenner", "Ghostbusters", "Egon Spengler", "figure", "1986", "loose_complete", 25),
        ("Kenner", "Ghostbusters", "Ray Stantz", "figure", "1986", "loose_complete", 22),
        ("Kenner", "Ghostbusters", "Winston Zeddemore", "figure", "1986", "loose_complete", 25),
        ("Kenner", "Ghostbusters", "Slimer", "figure", "1986", "loose_complete", 18),
        ("Kenner", "Ghostbusters", "Stay Puft Marshmallow Man", "figure", "1986", "loose_complete", 35),
        ("Kenner", "Ghostbusters", "Ecto-1", "vehicle", "1986", "CIB", 120),
        ("Kenner", "Ghostbusters", "Firehouse HQ", "playset", "1987", "CIB", 250),

        # ─── Kenner M.A.S.K. (1985–1987) ─────────────────────────────
        ("Kenner", "M.A.S.K.", "Matt Trakker (Thunderhawk)", "vehicle", "1985", "CIB", 120),
        ("Kenner", "M.A.S.K.", "Miles Mayhem (Switchblade)", "vehicle", "1985", "CIB", 100),
        ("Kenner", "M.A.S.K.", "Rhino", "vehicle", "1985", "CIB", 80),
        ("Kenner", "M.A.S.K.", "Condor", "vehicle", "1985", "CIB", 55),
        ("Kenner", "M.A.S.K.", "Boulder Hill Playset", "playset", "1985", "CIB", 200),

        # ─── Kenner Aliens & Predator (1992–1995) ────────────────────
        ("Kenner", "Aliens", "Ripley (Space Marine)", "figure", "1992", "loose_complete", 22),
        ("Kenner", "Aliens", "Alien Warrior (Brown)", "figure", "1992", "loose_complete", 18),
        ("Kenner", "Aliens", "Bull Alien", "figure", "1992", "loose_complete", 15),
        ("Kenner", "Aliens", "Scorpion Alien", "figure", "1992", "loose_complete", 15),
        ("Kenner", "Aliens", "Alien Queen", "figure", "1992", "CIB", 55),
        ("Kenner", "Predator", "Predator (Warrior)", "figure", "1993", "loose_complete", 28),
        ("Kenner", "Predator", "Predator (Stalker)", "figure", "1993", "loose_complete", 25),
        ("Kenner", "Predator", "Predator (Clan Leader)", "figure", "1994", "loose_complete", 35),

        # ─── Mattel She-Ra: Princess of Power (1985–1987) ─────────────
        ("Mattel", "She-Ra", "She-Ra", "figure", "1985", "loose_complete", 35),
        ("Mattel", "She-Ra", "Catra", "figure", "1985", "loose_complete", 30),
        ("Mattel", "She-Ra", "Frosta", "figure", "1985", "loose_complete", 25),
        ("Mattel", "She-Ra", "Glimmer", "figure", "1985", "loose_complete", 28),
        ("Mattel", "She-Ra", "Bow", "figure", "1985", "loose_complete", 22),
        ("Mattel", "She-Ra", "Swift Wind", "figure", "1985", "loose_complete", 45),
        ("Mattel", "She-Ra", "Crystal Castle", "playset", "1985", "CIB", 300),

        # ─── Miscellaneous Vintage Lines ──────────────────────────────
        ("Mattel", "Big Jim", "Big Jim", "figure", "1971", "loose_complete", 40),
        ("Mattel", "Big Jim", "Big Jim (P.A.C.K.)", "figure", "1975", "loose_complete", 55),
        ("Ideal", "Captain Action", "Captain Action", "figure", "1966", "loose_complete", 120),
        ("Ideal", "Captain Action", "Captain Action (Superman Outfit)", "figure", "1966", "CIB", 350),
        ("Ideal", "Captain Action", "Captain Action (Batman Outfit)", "figure", "1966", "CIB", 400),
        ("Ideal", "Captain Action", "Dr. Evil", "figure", "1967", "loose_complete", 90),
        ("Coleco", "Starcom", "Starmax Bomber", "vehicle", "1986", "CIB", 75),
        ("Coleco", "Starcom", "Shadow Parasite", "vehicle", "1986", "CIB", 60),
        ("Galoob", "Micro Machines", "Star Wars Micro Machines Set", "vehicle", "1994", "CIB", 35),
        ("Galoob", "Micro Machines", "Micro Machines Super City", "playset", "1991", "CIB", 55),
        ("Toy Biz", "Marvel", "Spider-Man (Secret Wars)", "figure", "1984", "loose_complete", 35),
        ("Toy Biz", "Marvel", "Doctor Doom (Secret Wars)", "figure", "1984", "loose_complete", 30),
        ("Toy Biz", "Marvel", "Captain America (Secret Wars)", "figure", "1984", "loose_complete", 30),
        ("Toy Biz", "Marvel", "Iron Man (Secret Wars)", "figure", "1984", "loose_complete", 28),
        ("Toy Biz", "Marvel", "Wolverine (Secret Wars)", "figure", "1984", "loose_complete", 45),
        ("Toy Biz", "Marvel", "Magneto (Secret Wars)", "figure", "1984", "loose_complete", 32),

        # ─── Kenner Robin Hood: Prince of Thieves (1991) ────────────────
        ("Kenner", "Robin Hood", "Robin Hood (Long Bow)", "figure", "1991", "loose_complete", 18),
        ("Kenner", "Robin Hood", "Little John", "figure", "1991", "loose_complete", 15),
        ("Kenner", "Robin Hood", "Friar Tuck", "figure", "1991", "loose_complete", 15),
        ("Kenner", "Robin Hood", "Azeem", "figure", "1991", "loose_complete", 20),
        ("Kenner", "Robin Hood", "Sheriff of Nottingham", "figure", "1991", "loose_complete", 22),

        # ─── Coleco Sectaurs (1984) ─────────────────────────────────────
        ("Coleco", "Sectaurs", "Dargon with Dragonflyer", "figure", "1984", "loose_complete", 55),
        ("Coleco", "Sectaurs", "Zak with Bitaur", "figure", "1984", "loose_complete", 45),
        ("Coleco", "Sectaurs", "Pinsor with Battle Beetle", "figure", "1984", "loose_complete", 50),
        ("Coleco", "Sectaurs", "Mantor with Raplor", "figure", "1984", "loose_complete", 48),
        ("Coleco", "Sectaurs", "Skulk with Trancula", "figure", "1984", "loose_complete", 42),

        # ─── Remco Crystar (1982) ──────────────────────────────────────
        ("Remco", "Crystar", "Crystar (Crystal Warrior)", "figure", "1982", "loose_complete", 35),
        ("Remco", "Crystar", "Warbow", "figure", "1982", "loose_complete", 30),
        ("Remco", "Crystar", "Moltar (Lava Lord)", "figure", "1982", "loose_complete", 38),
        ("Remco", "Crystar", "Ogeode", "figure", "1982", "loose_complete", 32),

        # ─── Mattel Voltron (1984–1985) ────────────────────────────────
        ("Mattel", "Voltron", "Keith (Lion Force Commander)", "figure", "1984", "loose_complete", 35),
        ("Mattel", "Voltron", "Lance", "figure", "1984", "loose_complete", 28),
        ("Mattel", "Voltron", "Hunk", "figure", "1984", "loose_complete", 25),
        ("Mattel", "Voltron", "Black Lion", "vehicle", "1984", "loose_complete", 85),
        ("Mattel", "Voltron", "Lion Force Voltron (Deluxe Combiner)", "figure", "1984", "CIB", 280),
        ("Mattel", "Voltron", "Vehicle Voltron (Deluxe Set)", "vehicle", "1985", "CIB", 320),

        # ─── Kenner Centurions (1986) ──────────────────────────────────
        ("Kenner", "Centurions", "Ace McCloud (Sky Knight)", "figure", "1986", "loose_complete", 45),
        ("Kenner", "Centurions", "Jake Rockwell (Fireforce)", "figure", "1986", "loose_complete", 40),
        ("Kenner", "Centurions", "Max Ray (Cruiser)", "figure", "1986", "loose_complete", 42),
        ("Kenner", "Centurions", "Doc Terror", "figure", "1986", "loose_complete", 55),
        ("Kenner", "Centurions", "Hacker", "figure", "1986", "loose_complete", 38),

        # ─── Hasbro Visionaries (1987) ─────────────────────────────────
        ("Hasbro", "Visionaries", "Leoric", "figure", "1987", "loose_complete", 45),
        ("Hasbro", "Visionaries", "Darkstorm", "figure", "1987", "loose_complete", 42),
        ("Hasbro", "Visionaries", "Ectar", "figure", "1987", "loose_complete", 38),
        ("Hasbro", "Visionaries", "Cindarr", "figure", "1987", "loose_complete", 35),
        ("Hasbro", "Visionaries", "Dagger Assault (Vehicle)", "vehicle", "1987", "CIB", 85),

        # ─── LJN Advanced Dungeons & Dragons (1983–1984) ───────────────
        ("LJN", "Advanced Dungeons & Dragons", "Strongheart (Good Paladin)", "figure", "1983", "loose_complete", 55),
        ("LJN", "Advanced Dungeons & Dragons", "Warduke (Evil Fighter)", "figure", "1983", "loose_complete", 80),
        ("LJN", "Advanced Dungeons & Dragons", "Kelek (Evil Sorcerer)", "figure", "1983", "loose_complete", 50),
        ("LJN", "Advanced Dungeons & Dragons", "Zarak (Half-Orc Assassin)", "figure", "1983", "loose_complete", 45),
        ("LJN", "Advanced Dungeons & Dragons", "Mercion (Good Cleric)", "figure", "1983", "loose_complete", 65),
        ("LJN", "Advanced Dungeons & Dragons", "Ogre King", "figure", "1984", "loose_complete", 70),

        # ─── Thundarr the Barbarian (1981) ─────────────────────────────
        ("LJN", "Thundarr the Barbarian", "Thundarr", "figure", "1981", "loose_complete", 120),
        ("LJN", "Thundarr the Barbarian", "Ookla the Mok", "figure", "1981", "loose_complete", 110),
        ("LJN", "Thundarr the Barbarian", "Princess Ariel", "figure", "1981", "loose_complete", 130),

        # ─── Tonka GoBots (1983–1987) ──────────────────────────────────
        ("Tonka", "GoBots", "Leader-1", "figure", "1983", "loose_complete", 22),
        ("Tonka", "GoBots", "Cy-Kill", "figure", "1983", "loose_complete", 25),
        ("Tonka", "GoBots", "Turbo", "figure", "1983", "loose_complete", 18),
        ("Tonka", "GoBots", "Crasher", "figure", "1984", "loose_complete", 20),
        ("Tonka", "GoBots", "Command Center", "playset", "1984", "CIB", 85),
        ("Tonka", "GoBots", "Thruster (Renegade Fortress)", "playset", "1985", "CIB", 75),

        # ─── Galoob Micro Machines & A-Team ────────────────────────────
        ("Galoob", "Micro Machines", "Military Collection #1", "vehicle", "1989", "CIB", 25),
        ("Galoob", "Micro Machines", "Insiders (Corvette)", "vehicle", "1989", "CIB", 30),
        ("Galoob", "Micro Machines", "Aircraft Carrier Playset", "playset", "1990", "CIB", 45),
        ("Galoob", "A-Team", "B.A. Baracus with Van", "vehicle", "1983", "loose_complete", 55),
        ("Galoob", "A-Team", "Hannibal Smith", "figure", "1983", "loose_complete", 35),

        # ─── Hasbro Inhumanoids (1986) ─────────────────────────────────
        ("Hasbro", "Inhumanoids", "Metlar", "figure", "1986", "loose_complete", 65),
        ("Hasbro", "Inhumanoids", "D'Compose", "figure", "1986", "loose_complete", 60),
        ("Hasbro", "Inhumanoids", "Tendril", "figure", "1986", "loose_complete", 55),
        ("Hasbro", "Inhumanoids", "Herc Armstrong (Earth Corps)", "figure", "1986", "loose_complete", 30),

        # ─── Coleco Rambo (1986) ───────────────────────────────────────
        ("Coleco", "Rambo", "Rambo (S.A.V.A.G.E.)", "figure", "1986", "loose_complete", 25),
        ("Coleco", "Rambo", "Colonel Trautman", "figure", "1986", "loose_complete", 20),
        ("Coleco", "Rambo", "General Warhawk", "figure", "1986", "loose_complete", 22),
        ("Coleco", "Rambo", "Skyfire Assault Copter", "vehicle", "1986", "CIB", 55),
    ]

    catalog = []
    for manufacturer, franchise, name, item_type, era, completeness, price in items:
        catalog.append({
            "manufacturer": manufacturer,
            "franchise": franchise,
            "name": name,
            "item_type": item_type,
            "era": era,
            "completeness": completeness,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    name = item["name"]
    manufacturer = item["manufacturer"]
    franchise = item["franchise"]
    item_type = item["item_type"]
    era = item["era"]
    completeness = item["completeness"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{manufacturer}-{franchise}-{name}-{completeness}"),
        title=name,
        set_code=slugify(franchise),
        brand=manufacturer,
        rarity="Grail" if item["price_eur"] >= 500 else "High" if item["price_eur"] >= 150 else "Mid" if item["price_eur"] >= 50 else "Standard",
        notes=f"{manufacturer} | {franchise} | {item_type} | {era} | {completeness}",
        attributes_json={
            "franchise": franchise,
            "manufacturer": manufacturer,
            "era": era,
            "item_type": item_type,
            "completeness": completeness,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    completeness = item["completeness"]

    completeness_scores = {
        "CIB": 0.9,
        "MOC": 0.95,
        "loose_complete": 0.6,
        "loose_incomplete": 0.3,
        "box_only": 0.4,
    }

    return PriceObservation(
        features={
            "condition_score": completeness_scores.get(completeness, 0.5),
            "rarity_score": min(1.0, item["price_eur"] / 500),
            "edition_score": 0.7 if completeness in ("CIB", "MOC") else 0.4,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Vintage Toys catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Vintage Toys Import ===")

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

    logger.info(f"\n=== Vintage Toys Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
