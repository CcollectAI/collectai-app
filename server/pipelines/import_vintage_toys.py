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
- Kenner Sky Commanders (1987)
- Hasbro Air Raiders (1987)
- Mattel Captain Power (1987–1988)
- Tonka Supernaturals (1987)
- Matchbox Ring Raiders (1989)
- Hasbro Battle Beasts (1987–1988)
- 610+ items spanning multiple decades

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
    """Curated 610+ vintage toys catalog: Kenner Star Wars, GI Joe ARAH,
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

        # ─── Kenner M.A.S.K. (Additional) ───────────────────────────
        ("Kenner", "M.A.S.K.", "Raven (with Calhoun Burns)", "vehicle", "1985", "CIB", 75),
        ("Kenner", "M.A.S.K.", "Firecracker (with Hondo MacLean)", "vehicle", "1985", "CIB", 65),
        ("Kenner", "M.A.S.K.", "Gator (with Dusty Hayes)", "vehicle", "1985", "CIB", 70),
        ("Kenner", "M.A.S.K.", "Jackhammer (with Cliff Dagger)", "vehicle", "1985", "CIB", 65),
        ("Kenner", "M.A.S.K.", "Piranha (with Sly Rax)", "vehicle", "1986", "CIB", 60),
        ("Kenner", "M.A.S.K.", "Volcano (with Matt Trakker & Jacques LaFleur)", "vehicle", "1986", "CIB", 90),
        ("Kenner", "M.A.S.K.", "Outlaw (with Miles Mayhem & Nash Gorey)", "vehicle", "1986", "CIB", 80),
        ("Kenner", "M.A.S.K.", "Hurricane (with Hondo MacLean)", "vehicle", "1986", "CIB", 55),
        ("Kenner", "M.A.S.K.", "Buzzard (with Miles Mayhem)", "vehicle", "1986", "CIB", 55),
        ("Kenner", "M.A.S.K.", "Iguana (with Lester Sludge)", "vehicle", "1986", "CIB", 50),
        ("Kenner", "M.A.S.K.", "Pit Stop Catapult (with Sly Rax)", "vehicle", "1986", "CIB", 55),
        ("Kenner", "M.A.S.K.", "Meteor (with Ace Riker)", "vehicle", "1987", "CIB", 75),
        ("Kenner", "M.A.S.K.", "Thunderhawk", "vehicle", "1985", "loose_complete", 65),
        ("Kenner", "M.A.S.K.", "Switchblade", "vehicle", "1985", "loose_complete", 55),
        ("Kenner", "M.A.S.K.", "Rhino", "vehicle", "1985", "loose_complete", 45),
        ("Kenner", "M.A.S.K.", "Condor", "vehicle", "1985", "loose_complete", 30),
        ("Kenner", "M.A.S.K.", "Boulder Hill Playset", "playset", "1985", "loose_complete", 110),
        ("Kenner", "M.A.S.K.", "Collector Station Playset", "playset", "1986", "CIB", 150),
        ("Kenner", "M.A.S.K.", "Slingshot (with Ace Riker)", "vehicle", "1986", "CIB", 55),
        ("Kenner", "M.A.S.K.", "Bulldog (with Boris Bushkin)", "vehicle", "1987", "CIB", 70),

        # ─── Matchbox / LJN Voltron (Additional) ─────────────────────
        ("Matchbox", "Voltron", "Red Lion", "vehicle", "1984", "loose_complete", 65),
        ("Matchbox", "Voltron", "Green Lion", "vehicle", "1984", "loose_complete", 60),
        ("Matchbox", "Voltron", "Blue Lion", "vehicle", "1984", "loose_complete", 60),
        ("Matchbox", "Voltron", "Yellow Lion", "vehicle", "1984", "loose_complete", 55),
        ("Matchbox", "Voltron", "Black Lion", "vehicle", "1984", "loose_complete", 70),
        ("Matchbox", "Voltron", "Lion Force Voltron (Matchbox Combiner)", "figure", "1984", "CIB", 350),
        ("Matchbox", "Voltron", "Lion Force Voltron (Matchbox)", "figure", "1984", "loose_complete", 150),
        ("Matchbox", "Voltron", "Vehicle Voltron (Matchbox Deluxe)", "vehicle", "1985", "CIB", 380),
        ("Matchbox", "Voltron", "Vehicle Voltron (Matchbox)", "vehicle", "1985", "loose_complete", 160),
        ("LJN", "Voltron", "Voltron Miniature Lion Set", "vehicle", "1984", "CIB", 85),
        ("Panosh Place", "Voltron", "Skull Tank", "vehicle", "1985", "CIB", 55),
        ("Panosh Place", "Voltron", "Zarkon", "figure", "1985", "loose_complete", 35),
        ("Panosh Place", "Voltron", "Haggar", "figure", "1985", "loose_complete", 30),
        ("Panosh Place", "Voltron", "Prince Lotor", "figure", "1985", "loose_complete", 32),
        ("Panosh Place", "Voltron", "Robeast Scorpious", "figure", "1985", "loose_complete", 40),

        # ─── Kenner Silverhawks (1986–1987) ──────────────────────────
        ("Kenner", "Silverhawks", "Quicksilver (with Tally-Hawk)", "figure", "1986", "loose_complete", 55),
        ("Kenner", "Silverhawks", "Steelwill", "figure", "1986", "loose_complete", 45),
        ("Kenner", "Silverhawks", "Steelheart", "figure", "1986", "loose_complete", 48),
        ("Kenner", "Silverhawks", "Bluegrass (with Side Man)", "figure", "1986", "loose_complete", 50),
        ("Kenner", "Silverhawks", "Copper Kidd", "figure", "1986", "loose_complete", 40),
        ("Kenner", "Silverhawks", "Mon*Star", "figure", "1986", "loose_complete", 65),
        ("Kenner", "Silverhawks", "Buzz-Saw", "figure", "1986", "loose_complete", 35),
        ("Kenner", "Silverhawks", "Mo-Lec-U-Lar", "figure", "1987", "loose_complete", 55),
        ("Kenner", "Silverhawks", "Windhammer", "figure", "1987", "loose_complete", 50),
        ("Kenner", "Silverhawks", "Mumbo Jumbo", "figure", "1987", "loose_complete", 45),
        ("Kenner", "Silverhawks", "Hardware", "figure", "1987", "loose_complete", 42),
        ("Kenner", "Silverhawks", "Hotwing", "figure", "1987", "loose_complete", 60),
        ("Kenner", "Silverhawks", "Flashback", "figure", "1987", "loose_complete", 65),
        ("Kenner", "Silverhawks", "Miraj", "vehicle", "1986", "CIB", 85),
        ("Kenner", "Silverhawks", "Maraj", "vehicle", "1986", "CIB", 75),

        # ─── Hasbro Visionaries (Additional) ─────────────────────────
        ("Hasbro", "Visionaries", "Witterquick", "figure", "1987", "loose_complete", 35),
        ("Hasbro", "Visionaries", "Arzon", "figure", "1987", "loose_complete", 38),
        ("Hasbro", "Visionaries", "Feryl", "figure", "1987", "loose_complete", 32),
        ("Hasbro", "Visionaries", "Cryotek", "figure", "1987", "loose_complete", 35),
        ("Hasbro", "Visionaries", "Mortdredd", "figure", "1987", "loose_complete", 38),
        ("Hasbro", "Visionaries", "Lexor", "figure", "1987", "loose_complete", 30),
        ("Hasbro", "Visionaries", "Reekon", "figure", "1987", "loose_complete", 32),
        ("Hasbro", "Visionaries", "Lancer Cycle (Vehicle)", "vehicle", "1987", "CIB", 70),
        ("Hasbro", "Visionaries", "Capture Chariot (Vehicle)", "vehicle", "1987", "CIB", 75),
        ("Hasbro", "Visionaries", "Sky Claw (Vehicle)", "vehicle", "1987", "CIB", 80),
        ("Hasbro", "Visionaries", "Iron Mountain Playset", "playset", "1987", "CIB", 200),
        ("Hasbro", "Visionaries", "Leoric", "figure", "1987", "MOC", 150),

        # ─── Tyco Dino-Riders (1988–1990) ────────────────────────────
        ("Tyco", "Dino-Riders", "T-Rex with Krulos", "vehicle", "1988", "CIB", 350),
        ("Tyco", "Dino-Riders", "T-Rex with Krulos", "vehicle", "1988", "loose_complete", 180),
        ("Tyco", "Dino-Riders", "Triceratops with Hammerhead", "vehicle", "1988", "CIB", 200),
        ("Tyco", "Dino-Riders", "Triceratops with Hammerhead", "vehicle", "1988", "loose_complete", 100),
        ("Tyco", "Dino-Riders", "Diplodocus with Questar", "vehicle", "1988", "CIB", 280),
        ("Tyco", "Dino-Riders", "Stegosaurus with Tark", "vehicle", "1988", "CIB", 150),
        ("Tyco", "Dino-Riders", "Pterodactyl with Llahd", "vehicle", "1988", "CIB", 85),
        ("Tyco", "Dino-Riders", "Torosaurus with Gunnur", "vehicle", "1988", "CIB", 120),
        ("Tyco", "Dino-Riders", "Ankylosaurus with Sting", "vehicle", "1989", "CIB", 130),
        ("Tyco", "Dino-Riders", "Styracosaurus with Turret", "vehicle", "1989", "CIB", 110),
        ("Tyco", "Dino-Riders", "Monoclonius with Mako", "vehicle", "1988", "CIB", 75),
        ("Tyco", "Dino-Riders", "Deinonychus with Antor", "vehicle", "1988", "CIB", 65),
        ("Tyco", "Dino-Riders", "Quetzalcoatlus with Yungstar", "vehicle", "1989", "CIB", 95),
        ("Tyco", "Dino-Riders", "Brontosaurus with Ion", "vehicle", "1989", "CIB", 220),
        ("Tyco", "Dino-Riders", "Command Compound Playset", "playset", "1988", "CIB", 180),

        # ─── Mattel Bravestarr (1986–1988) ───────────────────────────
        ("Mattel", "Bravestarr", "Marshal Bravestarr", "figure", "1986", "loose_complete", 35),
        ("Mattel", "Bravestarr", "Thirty/Thirty", "figure", "1986", "loose_complete", 45),
        ("Mattel", "Bravestarr", "Tex Hex", "figure", "1986", "loose_complete", 30),
        ("Mattel", "Bravestarr", "Skuzz", "figure", "1986", "loose_complete", 25),
        ("Mattel", "Bravestarr", "Sand Storm", "figure", "1986", "loose_complete", 28),
        ("Mattel", "Bravestarr", "Handlebar", "figure", "1986", "loose_complete", 22),
        ("Mattel", "Bravestarr", "Outlaw Skuzz", "figure", "1987", "loose_complete", 25),
        ("Mattel", "Bravestarr", "Deputy Fuzz", "figure", "1986", "loose_complete", 28),
        ("Mattel", "Bravestarr", "Laser-Fire Bravestarr", "figure", "1987", "CIB", 80),
        ("Mattel", "Bravestarr", "Neutra-Laser Thirty/Thirty", "figure", "1987", "CIB", 90),
        ("Mattel", "Bravestarr", "Fort Kerium Playset", "playset", "1986", "CIB", 120),
        ("Mattel", "Bravestarr", "Stratocoach", "vehicle", "1986", "CIB", 55),

        # ─── Kenner Centurions (Additional) ──────────────────────────
        ("Kenner", "Centurions", "Ace McCloud (Orbital Interceptor)", "figure", "1986", "loose_complete", 48),
        ("Kenner", "Centurions", "Jake Rockwell (Wild Weasel)", "figure", "1986", "loose_complete", 42),
        ("Kenner", "Centurions", "Max Ray (Tidal Blast)", "figure", "1986", "loose_complete", 45),
        ("Kenner", "Centurions", "Rex Charger (Detonator)", "figure", "1987", "loose_complete", 55),
        ("Kenner", "Centurions", "Ace McCloud (Sky Knight)", "figure", "1986", "CIB", 95),
        ("Kenner", "Centurions", "Jake Rockwell (Fireforce)", "figure", "1986", "CIB", 85),
        ("Kenner", "Centurions", "Power Pack Assault Weapon Systems", "accessory", "1986", "CIB", 45),

        # ─── Mego Micronauts (1976–1980) ─────────────────────────────
        ("Mego", "Micronauts", "Baron Karza", "figure", "1977", "loose_complete", 85),
        ("Mego", "Micronauts", "Baron Karza", "figure", "1977", "CIB", 250),
        ("Mego", "Micronauts", "Acroyear", "figure", "1977", "loose_complete", 55),
        ("Mego", "Micronauts", "Acroyear II", "figure", "1978", "loose_complete", 40),
        ("Mego", "Micronauts", "Time Traveler (Clear)", "figure", "1977", "loose_complete", 35),
        ("Mego", "Micronauts", "Time Traveler (Opaque)", "figure", "1977", "loose_complete", 30),
        ("Mego", "Micronauts", "Space Glider", "figure", "1977", "loose_complete", 40),
        ("Mego", "Micronauts", "Galactic Warrior", "figure", "1977", "loose_complete", 32),
        ("Mego", "Micronauts", "Pharoid", "figure", "1977", "loose_complete", 45),
        ("Mego", "Micronauts", "Biotron", "figure", "1976", "loose_complete", 60),
        ("Mego", "Micronauts", "Biotron", "figure", "1976", "CIB", 150),
        ("Mego", "Micronauts", "Microtron", "figure", "1976", "loose_complete", 50),
        ("Mego", "Micronauts", "Hornetroid", "vehicle", "1979", "CIB", 180),
        ("Mego", "Micronauts", "Battle Cruiser", "vehicle", "1977", "CIB", 120),
        ("Mego", "Micronauts", "Astro Station", "playset", "1977", "CIB", 100),

        # ─── Tomy Starriors (1984) ───────────────────────────────────
        ("Tomy", "Starriors", "Slaughter Steelgrave", "figure", "1984", "loose_complete", 35),
        ("Tomy", "Starriors", "Destructor Deadeye", "figure", "1984", "loose_complete", 28),
        ("Tomy", "Starriors", "Protector Hotshot", "figure", "1984", "loose_complete", 25),
        ("Tomy", "Starriors", "Wastors Gouge", "figure", "1984", "loose_complete", 22),
        ("Tomy", "Starriors", "Wastors Claw", "figure", "1984", "loose_complete", 22),
        ("Tomy", "Starriors", "Protector Cricket", "figure", "1984", "loose_complete", 20),
        ("Tomy", "Starriors", "Destructor Runabout", "figure", "1984", "loose_complete", 20),
        ("Tomy", "Starriors", "Cosmittor", "figure", "1984", "loose_complete", 30),
        ("Tomy", "Starriors", "Armored Battle Station", "vehicle", "1984", "CIB", 65),
        ("Tomy", "Starriors", "Vultor", "figure", "1984", "loose_complete", 28),
        ("Tomy", "Starriors", "Windstorm", "figure", "1984", "loose_complete", 25),
        ("Tomy", "Starriors", "Trashor", "figure", "1984", "loose_complete", 22),

        # ─── Hasbro Transformers G1 (Additional) ────────────────────
        ("Hasbro", "Transformers", "Razorclaw (Predacon, G1)", "figure", "1986", "loose_complete", 45),
        ("Hasbro", "Transformers", "Rampage (Predacon, G1)", "figure", "1986", "loose_complete", 40),
        ("Hasbro", "Transformers", "Divebomb (Predacon, G1)", "figure", "1986", "loose_complete", 40),
        ("Hasbro", "Transformers", "Headstrong (Predacon, G1)", "figure", "1986", "loose_complete", 38),
        ("Hasbro", "Transformers", "Tantrum (Predacon, G1)", "figure", "1986", "loose_complete", 38),
        ("Hasbro", "Transformers", "Motormaster (Stunticon, G1)", "figure", "1986", "loose_complete", 45),
        ("Hasbro", "Transformers", "Drag Strip (Stunticon, G1)", "figure", "1986", "loose_complete", 25),
        ("Hasbro", "Transformers", "Dead End (Stunticon, G1)", "figure", "1986", "loose_complete", 25),
        ("Hasbro", "Transformers", "Breakdown (Stunticon, G1)", "figure", "1986", "loose_complete", 25),
        ("Hasbro", "Transformers", "Wildrider (Stunticon, G1)", "figure", "1986", "loose_complete", 28),
        ("Hasbro", "Transformers", "Silverbolt (Aerialbot, G1)", "figure", "1986", "loose_complete", 40),
        ("Hasbro", "Transformers", "Air Raid (Aerialbot, G1)", "figure", "1986", "loose_complete", 22),
        ("Hasbro", "Transformers", "Fireflight (Aerialbot, G1)", "figure", "1986", "loose_complete", 22),
        ("Hasbro", "Transformers", "Skydive (Aerialbot, G1)", "figure", "1986", "loose_complete", 22),
        ("Hasbro", "Transformers", "Slingshot (Aerialbot, G1)", "figure", "1986", "loose_complete", 22),
        ("Hasbro", "Transformers", "Chromedome (Headmaster, G1)", "figure", "1987", "loose_complete", 55),
        ("Hasbro", "Transformers", "Hardhead (Headmaster, G1)", "figure", "1987", "loose_complete", 50),
        ("Hasbro", "Transformers", "Brainstorm (Headmaster, G1)", "figure", "1987", "loose_complete", 55),
        ("Hasbro", "Transformers", "Highbrow (Headmaster, G1)", "figure", "1987", "loose_complete", 50),
        ("Hasbro", "Transformers", "Cyclonus (Targetmaster, G1)", "figure", "1987", "loose_complete", 60),
        ("Hasbro", "Transformers", "Scourge (Targetmaster, G1)", "figure", "1987", "loose_complete", 55),
        ("Hasbro", "Transformers", "Triggerhappy (Targetmaster, G1)", "figure", "1987", "loose_complete", 45),

        # ─── Hasbro Transformers G1 — More Additions ─────────────────
        ("Hasbro", "Transformers", "Snapdragon (Headmaster, G1)", "figure", "1987", "loose_complete", 55),
        ("Hasbro", "Transformers", "Apeface (Headmaster, G1)", "figure", "1987", "loose_complete", 50),
        ("Hasbro", "Transformers", "Sixshot (G1)", "figure", "1987", "CIB", 280),
        ("Hasbro", "Transformers", "Sixshot (G1)", "figure", "1987", "loose_complete", 120),
        ("Hasbro", "Transformers", "Overlord (G1)", "figure", "1988", "CIB", 350),
        ("Hasbro", "Transformers", "Powermaster Optimus Prime (G1)", "figure", "1988", "CIB", 280),
        ("Hasbro", "Transformers", "Darkwing (Powermaster, G1)", "figure", "1988", "loose_complete", 35),
        ("Hasbro", "Transformers", "Dreadwind (Powermaster, G1)", "figure", "1988", "loose_complete", 35),

        # ─── Tyco Dino-Riders (Additional) ───────────────────────────
        ("Tyco", "Dino-Riders", "Pachycephalosaurus with Tagg", "vehicle", "1989", "CIB", 70),
        ("Tyco", "Dino-Riders", "Edmontonia with Axis", "vehicle", "1989", "CIB", 85),

        # ─── Kenner Sky Commanders (1987) ──────────────────────────────
        ("Kenner", "Sky Commanders", "General Summit with Backpack", "figure", "1987", "loose_complete", 30),
        ("Kenner", "Sky Commanders", "Raider Rath", "figure", "1987", "loose_complete", 28),
        ("Kenner", "Sky Commanders", "Spider Flyer Vehicle", "vehicle", "1987", "CIB", 65),
        ("Kenner", "Sky Commanders", "Cable Car Playset", "playset", "1987", "CIB", 85),
        ("Kenner", "Sky Commanders", "Rapid Deployment Vehicle", "vehicle", "1987", "CIB", 55),
        ("Kenner", "Sky Commanders", "Outrider with Cable", "vehicle", "1987", "loose_complete", 35),
        ("Kenner", "Sky Commanders", "Summit with Command Post", "figure", "1987", "CIB", 75),
        ("Kenner", "Sky Commanders", "Flex Machine", "vehicle", "1987", "loose_complete", 30),

        # ─── Hasbro Air Raiders (1987) ─────────────────────────────────
        ("Hasbro", "Air Raiders", "Man-O-War Battle Fortress", "playset", "1987", "CIB", 120),
        ("Hasbro", "Air Raiders", "Twin Lightning", "vehicle", "1987", "CIB", 65),
        ("Hasbro", "Air Raiders", "Hawkwind", "vehicle", "1987", "CIB", 55),
        ("Hasbro", "Air Raiders", "Battle Dasher", "vehicle", "1987", "loose_complete", 30),
        ("Hasbro", "Air Raiders", "Wind Seeker", "vehicle", "1987", "loose_complete", 28),
        ("Hasbro", "Air Raiders", "Air Refinery Command Outpost", "playset", "1987", "CIB", 95),
        ("Hasbro", "Air Raiders", "Storm Dagger", "vehicle", "1987", "loose_complete", 25),
        ("Hasbro", "Air Raiders", "Thunderclaw", "vehicle", "1987", "CIB", 60),

        # ─── Coleco Sectaurs (Additional) ──────────────────────────────
        ("Coleco", "Sectaurs", "General Spidrax with Spider-Flyer", "figure", "1984", "loose_complete", 60),
        ("Coleco", "Sectaurs", "Waspax with Wing Fighter", "figure", "1984", "loose_complete", 52),
        ("Coleco", "Sectaurs", "Dargon with Dragonflyer", "figure", "1984", "CIB", 140),
        ("Coleco", "Sectaurs", "General Spidrax with Spider-Flyer", "figure", "1984", "CIB", 155),
        ("Coleco", "Sectaurs", "Hyve Playset", "playset", "1984", "CIB", 180),
        ("Coleco", "Sectaurs", "Pinsor with Battle Beetle", "figure", "1984", "CIB", 120),
        ("Coleco", "Sectaurs", "Skulk with Trancula", "figure", "1984", "CIB", 110),
        ("Coleco", "Sectaurs", "Mantor with Raplor", "figure", "1984", "CIB", 115),

        # ─── Mattel Captain Power (1987–1988) ──────────────────────────
        ("Mattel", "Captain Power", "Captain Jonathan Power", "figure", "1987", "loose_complete", 35),
        ("Mattel", "Captain Power", "Major Hawk Masterson", "figure", "1987", "loose_complete", 30),
        ("Mattel", "Captain Power", "Corporal Jennifer 'Pilot' Chase", "figure", "1987", "loose_complete", 32),
        ("Mattel", "Captain Power", "Sergeant Robert 'Tank' Ellis", "figure", "1987", "loose_complete", 28),
        ("Mattel", "Captain Power", "Lord Dread", "figure", "1987", "loose_complete", 40),
        ("Mattel", "Captain Power", "Soaron Sky Sentry", "figure", "1987", "loose_complete", 38),
        ("Mattel", "Captain Power", "Blastarr Ground Guardian", "figure", "1987", "loose_complete", 35),
        ("Mattel", "Captain Power", "Powerjet XT-7 Interactive Vehicle", "vehicle", "1987", "CIB", 110),

        # ─── Tonka Supernaturals (1987) ────────────────────────────────
        ("Tonka", "Supernaturals", "Lionheart", "figure", "1987", "loose_complete", 45),
        ("Tonka", "Supernaturals", "Eagle Eye", "figure", "1987", "loose_complete", 40),
        ("Tonka", "Supernaturals", "Thunderbolt", "figure", "1987", "loose_complete", 38),
        ("Tonka", "Supernaturals", "Skull", "figure", "1987", "loose_complete", 48),
        ("Tonka", "Supernaturals", "Mr. Lucky", "figure", "1987", "loose_complete", 42),
        ("Tonka", "Supernaturals", "Burnheart", "figure", "1987", "loose_complete", 40),
        ("Tonka", "Supernaturals", "Scary Cat", "figure", "1987", "loose_complete", 35),
        ("Tonka", "Supernaturals", "Ghostling", "figure", "1987", "loose_complete", 32),

        # ─── Matchbox Ring Raiders (1989) ──────────────────────────────
        ("Matchbox", "Ring Raiders", "Skull Squadron Commander Ring", "figure", "1989", "loose_complete", 18),
        ("Matchbox", "Ring Raiders", "Freedom Fighter Ace Ring", "figure", "1989", "loose_complete", 15),
        ("Matchbox", "Ring Raiders", "Yakamura Zero Fighter Ring", "figure", "1989", "loose_complete", 16),
        ("Matchbox", "Ring Raiders", "Thunderwing Jet Ring", "figure", "1989", "loose_complete", 14),
        ("Matchbox", "Ring Raiders", "Ring Raiders Battle Set", "playset", "1989", "CIB", 45),
        ("Matchbox", "Ring Raiders", "Air Carrier Playset", "playset", "1989", "CIB", 65),
        ("Matchbox", "Ring Raiders", "Skull Squadron 4-Pack", "figure", "1989", "CIB", 40),
        ("Matchbox", "Ring Raiders", "Freedom Wing 4-Pack", "figure", "1989", "CIB", 38),

        # ─── Hasbro Battle Beasts (1987–1988) ──────────────────────────
        ("Hasbro", "Battle Beasts", "Pirate Lion (Fire)", "figure", "1987", "loose_complete", 22),
        ("Hasbro", "Battle Beasts", "Gruesome Gator (Water)", "figure", "1987", "loose_complete", 20),
        ("Hasbro", "Battle Beasts", "Rubberneck Giraffe (Wood)", "figure", "1987", "loose_complete", 18),
        ("Hasbro", "Battle Beasts", "War Weasel (Fire)", "figure", "1987", "loose_complete", 25),
        ("Hasbro", "Battle Beasts", "Bloodthirsty Bison (Water)", "figure", "1987", "loose_complete", 20),
        ("Hasbro", "Battle Beasts", "Sabre Sword Tiger (Wood)", "figure", "1987", "loose_complete", 22),
        ("Hasbro", "Battle Beasts", "Battling Deer Stalker (Fire)", "figure", "1988", "loose_complete", 28),
        ("Hasbro", "Battle Beasts", "Laser Beasts Triple Threat Snake", "figure", "1988", "CIB", 55),

        # ─── Kenner Star Wars — Last 17 (POTF) ─────────────────────────
        ("Kenner", "Star Wars", "Romba (POTF Last 17)", "figure", "1985", "loose_complete", 120),
        ("Kenner", "Star Wars", "Warok (POTF Last 17)", "figure", "1985", "loose_complete", 110),
        ("Kenner", "Star Wars", "EV-9D9 (POTF Last 17)", "figure", "1985", "loose_complete", 90),
        ("Kenner", "Star Wars", "Imperial Gunner (POTF Last 17)", "figure", "1985", "loose_complete", 150),
        ("Kenner", "Star Wars", "A-Wing Pilot (POTF Last 17)", "figure", "1985", "MOC", 600),
        ("Kenner", "Star Wars", "Luke Stormtrooper (POTF Last 17)", "figure", "1985", "MOC", 800),
        ("Kenner", "Star Wars", "Lando General (POTF Last 17)", "figure", "1985", "loose_complete", 100),
        ("Kenner", "Star Wars", "AT-AT Driver (POTF Last 17)", "figure", "1985", "loose_complete", 80),
        ("Kenner", "Star Wars", "R2-D2 Pop-Up Saber (POTF Last 17)", "figure", "1985", "loose_complete", 180),
        ("Kenner", "Star Wars", "Han Solo Carbonite (POTF Last 17)", "figure", "1985", "loose_complete", 130),

        # ─── Hasbro GI Joe ARAH — Additional Figures ────────────────────
        ("Hasbro", "GI Joe ARAH", "Snake Eyes (v2, Swivel Arm)", "figure", "1985", "loose_complete", 120),
        ("Hasbro", "GI Joe ARAH", "Storm Shadow (v1)", "figure", "1984", "loose_complete", 85),
        ("Hasbro", "GI Joe ARAH", "Firefly (v1)", "figure", "1984", "loose_complete", 75),
        ("Hasbro", "GI Joe ARAH", "Zartan (v1, with Chameleon)", "figure", "1984", "CIB", 180),
        ("Hasbro", "GI Joe ARAH", "Serpentor (v1, with Air Chariot)", "figure", "1986", "CIB", 150),
        ("Hasbro", "GI Joe ARAH", "Cobra Commander (Battle Armor, v2)", "figure", "1984", "loose_complete", 60),
        ("Hasbro", "GI Joe ARAH", "Destro (v1, Iron Grenadiers)", "figure", "1983", "loose_complete", 55),
        ("Hasbro", "GI Joe ARAH", "Baroness (v1)", "figure", "1984", "loose_complete", 90),
        ("Hasbro", "GI Joe ARAH", "Jinx (v1)", "figure", "1987", "loose_complete", 65),
        ("Hasbro", "GI Joe ARAH", "USS Flagg Aircraft Carrier", "playset", "1985", "CIB", 1500),

        # ─── Hasbro Transformers G1 — Additional ────────────────────────
        ("Hasbro", "Transformers", "Jetfire (G1, Complete)", "figure", "1985", "CIB", 500),
        ("Hasbro", "Transformers", "Jetfire (G1, Loose)", "figure", "1985", "loose_complete", 220),
        ("Hasbro", "Transformers", "Shockwave (G1)", "figure", "1985", "CIB", 350),
        ("Hasbro", "Transformers", "Shockwave (G1, Loose)", "figure", "1985", "loose_complete", 150),
        ("Hasbro", "Transformers", "Omega Supreme (G1)", "figure", "1985", "CIB", 450),
        ("Hasbro", "Transformers", "Omega Supreme (G1, Loose)", "figure", "1985", "loose_complete", 200),
        ("Hasbro", "Transformers", "Metroplex (G1)", "figure", "1986", "CIB", 400),
        ("Hasbro", "Transformers", "Trypticon (G1)", "figure", "1986", "CIB", 380),
        ("Hasbro", "Transformers", "Predaking (G1, Gift Set)", "figure", "1986", "CIB", 600),
        ("Hasbro", "Transformers", "Bruticus (G1, Gift Set)", "figure", "1986", "CIB", 350),

        # ─── Mattel MOTU Vintage — Playsets & Vehicles ──────────────────
        ("Mattel", "MOTU", "Castle Grayskull (Complete)", "playset", "1982", "CIB", 350),
        ("Mattel", "MOTU", "Castle Grayskull (Loose)", "playset", "1982", "loose_complete", 180),
        ("Mattel", "MOTU", "Eternia Playset (Complete)", "playset", "1986", "CIB", 2500),
        ("Mattel", "MOTU", "Snake Mountain (Complete)", "playset", "1984", "CIB", 280),
        ("Mattel", "MOTU", "Snake Mountain (Loose)", "playset", "1984", "loose_complete", 140),
        ("Mattel", "MOTU", "Battle Cat (Complete w/ Saddle)", "vehicle", "1982", "loose_complete", 55),
        ("Mattel", "MOTU", "Panthor (Complete w/ Saddle)", "vehicle", "1982", "loose_complete", 65),
        ("Mattel", "MOTU", "Fright Zone Playset", "playset", "1985", "CIB", 200),
        ("Mattel", "MOTU", "Hordak (v1, Complete)", "figure", "1985", "loose_complete", 45),
        ("Mattel", "MOTU", "Grizzlor (Complete)", "figure", "1985", "loose_complete", 35),
        ("Mattel", "MOTU", "Leech (Complete)", "figure", "1985", "loose_complete", 30),
        ("Mattel", "MOTU", "Mantenna (Complete)", "figure", "1985", "loose_complete", 35),

        # ─── Kenner M.A.S.K. — Vehicles ────────────────────────────────
        ("Kenner", "M.A.S.K.", "Thunderhawk (Complete w/ Matt Trakker)", "vehicle", "1985", "CIB", 180),
        ("Kenner", "M.A.S.K.", "Rhino (Complete w/ Bruce Sato)", "vehicle", "1985", "CIB", 150),
        ("Kenner", "M.A.S.K.", "Condor (Complete w/ Brad Turner)", "vehicle", "1985", "CIB", 120),
        ("Kenner", "M.A.S.K.", "Switchblade (Complete w/ Miles Mayhem)", "vehicle", "1985", "CIB", 140),
        ("Kenner", "M.A.S.K.", "Jackhammer (Complete w/ Cliff Dagger)", "vehicle", "1985", "CIB", 110),
        ("Kenner", "M.A.S.K.", "Boulder Hill Playset (Complete)", "playset", "1985", "CIB", 250),
        ("Kenner", "M.A.S.K.", "Outlaw (Complete w/ Nash Gorey)", "vehicle", "1986", "CIB", 100),
        ("Kenner", "M.A.S.K.", "Raven (Complete w/ Calhoun Burns)", "vehicle", "1986", "CIB", 90),

        # ─── Mattel Voltron (1984–1985) ─────────────────────────────────
        ("Mattel", "Voltron", "Voltron Lion Force Deluxe Set (Complete)", "vehicle", "1984", "CIB", 400),
        ("Mattel", "Voltron", "Voltron Lion Force Deluxe Set (Loose)", "vehicle", "1984", "loose_complete", 200),
        ("Mattel", "Voltron", "Black Lion (Complete)", "vehicle", "1984", "loose_complete", 80),
        ("Mattel", "Voltron", "Red Lion (Complete)", "vehicle", "1984", "loose_complete", 60),
        ("Mattel", "Voltron", "Green Lion (Complete)", "vehicle", "1984", "loose_complete", 55),
        ("Mattel", "Voltron", "Blue Lion (Complete)", "vehicle", "1984", "loose_complete", 55),
        ("Mattel", "Voltron", "Yellow Lion (Complete)", "vehicle", "1984", "loose_complete", 55),

        # ─── LJN Thundercats — Additional ───────────────────────────────
        ("LJN", "Thundercats", "Lion-O (Complete w/ Sword)", "figure", "1985", "loose_complete", 80),
        ("LJN", "Thundercats", "Mumm-Ra (Complete)", "figure", "1985", "loose_complete", 60),
        ("LJN", "Thundercats", "Panthro (Complete)", "figure", "1985", "loose_complete", 55),
        ("LJN", "Thundercats", "Tygra (Complete)", "figure", "1985", "loose_complete", 50),
        ("LJN", "Thundercats", "Cheetara (Complete)", "figure", "1986", "loose_complete", 65),
        ("LJN", "Thundercats", "Cat's Lair Playset (Complete)", "playset", "1986", "CIB", 350),
        ("LJN", "Thundercats", "Thundertank (Complete)", "vehicle", "1986", "CIB", 200),

        # ─── Kenner Silverhawks (1986–1988) ─────────────────────────────
        ("Kenner", "Silverhawks", "Quicksilver (Complete w/ Tally-Hawk)", "figure", "1986", "loose_complete", 55),
        ("Kenner", "Silverhawks", "Steelheart (Complete)", "figure", "1986", "loose_complete", 45),
        ("Kenner", "Silverhawks", "Mon*Star (Complete)", "figure", "1986", "loose_complete", 65),
        ("Kenner", "Silverhawks", "Bluegrass (Complete w/ Guitar)", "figure", "1986", "loose_complete", 50),
        ("Kenner", "Silverhawks", "Copper Kidd (Complete)", "figure", "1986", "loose_complete", 40),
        ("Kenner", "Silverhawks", "Buzz-Saw (Complete)", "figure", "1987", "loose_complete", 45),
        ("Kenner", "Silverhawks", "Mirage Hawk Vehicle (Complete)", "vehicle", "1987", "CIB", 120),

        # ─── Vintage Lego Space Sets ─────────────────────────────────────
        ("Lego", "Classic Space", "Galaxy Explorer (497)", "playset", "1979", "CIB", 350),
        ("Lego", "Classic Space", "Space Cruiser (487)", "vehicle", "1979", "CIB", 200),
        ("Lego", "Classic Space", "Space Supply Station (6930)", "playset", "1983", "CIB", 150),
        ("Lego", "Classic Space", "Cosmic Fleet Voyager (6985)", "vehicle", "1986", "CIB", 250),
        ("Lego", "Blacktron", "Invader (6894)", "vehicle", "1987", "CIB", 120),
        ("Lego", "Blacktron", "Renegade (6954)", "vehicle", "1987", "CIB", 180),
        ("Lego", "M-Tron", "Mega Core Magnetizer (6989)", "vehicle", "1990", "CIB", 200),
        ("Lego", "Ice Planet", "Deep Freeze Defender (6973)", "vehicle", "1993", "CIB", 180),

        # ─── Additional Vintage Toys (+5) ──────────────────────────────────
        ("Hasbro", "Transformers G1", "Jetfire (Complete)", "figure", "1985", "loose_complete", 280),
        ("Mattel", "MOTU", "Castle Grayskull (Complete)", "playset", "1982", "CIB", 350),
        ("Kenner", "Star Wars", "Imperial Shuttle (Complete)", "vehicle", "1984", "CIB", 400),
        ("LJN", "Thundercats", "Mumm-Ra (Ever-Living Form)", "figure", "1986", "loose_complete", 120),
        ("Playmates", "TMNT", "Technodrome Playset", "playset", "1990", "CIB", 250),
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
