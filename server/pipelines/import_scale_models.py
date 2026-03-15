"""
Import Scale Model Kits catalog.

Layer 1 (Catalog):  Curated scale model kits (619+ items) → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Aircraft: Tamiya 1/32 & 1/48, Hasegawa, Eduard, Trumpeter, Revell, Airfix, Academy, ICM
- Armor: Tamiya, Trumpeter, Dragon, Meng, Rye Field, Takom 1/35 tanks
- Ships: Tamiya, Trumpeter, Revell, Fujimi, Academy 1/200–1/570
- Cars: Tamiya 1/12 & 1/24, Hasegawa, Beemax, NuNu, Aoshima, Fujimi
- Sci-fi: Bandai Star Wars, Moebius, Pegasus, Kotobukiya, Fine Molds
- Figures: Tamiya, MasterBox, Alpine Miniatures, Nutsplanet
- Diorama/Accessories: Tamiya, MiniArt

Usage:
    python -m pipelines.import_scale_models [--dry-run]
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

CATEGORY = "scale_models"


def _variant_expansion() -> list[tuple]:
    """Scale variants (1/72 vs 1/48 vs 1/32), limited edition boxings, and photo-etch detail sets."""
    return [
        # ── Scale Variants — Same Aircraft in Different Scales ────────────
        ("Tamiya", "Aircraft", "Spitfire Mk.IXc", "1/32", "high", 85),
        ("Tamiya", "Aircraft", "P-51D Mustang", "1/32", "high", 90),
        ("Tamiya", "Aircraft", "Bf 109 G-6", "1/32", "high", 82),
        ("Tamiya", "Aircraft", "Fw 190 D-9", "1/32", "high", 88),
        ("Tamiya", "Aircraft", "P-51D Mustang", "1/72", "standard", 22),
        ("Tamiya", "Aircraft", "Bf 109 G-6", "1/72", "standard", 20),
        ("Hasegawa", "Aircraft", "P-47D Thunderbolt", "1/32", "high", 80),
        ("Hasegawa", "Aircraft", "P-47D Thunderbolt", "1/72", "standard", 18),
        ("Eduard", "Aircraft", "Spitfire Mk.I Profipack", "1/72", "mid", 35),
        ("Eduard", "Aircraft", "Bf 109 E-4 Profipack", "1/72", "mid", 32),

        # ── Limited Edition Boxings ───────────────────────────────────────
        ("Eduard", "Aircraft", "Spitfire Mk.IXc (Royal Class)", "1/48", "high", 95),
        ("Eduard", "Aircraft", "Bf 109 G-6 (Dual Combo)", "1/48", "high", 75),
        ("Eduard", "Aircraft", "Fw 190 A-8 (Royal Class)", "1/48", "grail", 110),
        ("Tamiya", "Armor", "Tiger I (Late Version) Ace Commander", "1/35", "high", 80),
        ("Tamiya", "Armor", "Panther Ausf.D (Special Edition)", "1/35", "high", 85),
        ("Meng Model", "Armor", "Panther Ausf.A (Late) (Special Edition)", "1/35", "high", 90),
        ("Wingnut Wings", "Aircraft", "Fokker D.VII (Dual Combo)", "1/32", "grail", 140),
        ("Trumpeter", "Ship", "Bismarck (Deluxe Edition)", "1/350", "grail", 180),

        # ── Photo-Etch Detail Sets ────────────────────────────────────────
        ("Eduard", "Accessories", "Spitfire Mk.IX PE Detail Set", "1/48", "standard", 22),
        ("Eduard", "Accessories", "Bf 109 G-6 PE Detail Set", "1/48", "standard", 20),
        ("Eduard", "Accessories", "P-51D Mustang PE Detail Set", "1/48", "standard", 24),
        ("Eduard", "Accessories", "B-17G Flying Fortress PE Interior", "1/48", "mid", 38),
        ("Eduard", "Accessories", "Tiger I PE Detail Set", "1/35", "standard", 28),
        ("Eduard", "Accessories", "Panther Ausf.G PE Detail Set", "1/35", "standard", 26),
        ("Voyager Model", "Accessories", "King Tiger PE Detail Set", "1/35", "mid", 42),
        ("Voyager Model", "Accessories", "M4A3 Sherman PE Detail Set", "1/35", "mid", 40),
    ]


def get_curated_catalog() -> list[dict]:
    """Curated scale model kit catalog — 619 items across 7 subcategories."""

    # (manufacturer, model_type, name, scale, rarity_tier, price_eur)
    # rarity_tier: grail (>150), high (80-150), mid (40-80), standard (<40)

    kits = [
        # Aircraft - WWII Fighters
        ("Tamiya", "Aircraft", "Spitfire Mk.IXc", "1/48", "mid", 42),
        ("Tamiya", "Aircraft", "P-51D Mustang", "1/48", "mid", 45),
        ("Tamiya", "Aircraft", "Bf 109 G-6", "1/48", "mid", 40),
        ("Tamiya", "Aircraft", "Fw 190 D-9", "1/48", "mid", 42),
        ("Tamiya", "Aircraft", "Zero Fighter Type 52 (Zeke)", "1/48", "mid", 38),
        ("Hasegawa", "Aircraft", "P-47D Thunderbolt", "1/48", "mid", 35),
        ("Hasegawa", "Aircraft", "Ki-84 Hayate (Frank)", "1/48", "standard", 32),
        ("Eduard", "Aircraft", "Spitfire Mk.I Profipack", "1/48", "mid", 48),
        ("Eduard", "Aircraft", "Bf 109 E-4 Profipack", "1/48", "mid", 45),
        ("Eduard", "Aircraft", "Fw 190 A-8 Profipack", "1/48", "mid", 50),

        # Aircraft - Jets
        ("Tamiya", "Aircraft", "F-14A Tomcat", "1/48", "high", 95),
        ("Tamiya", "Aircraft", "F-16CJ Fighting Falcon", "1/48", "mid", 55),
        ("Hasegawa", "Aircraft", "F-4E Phantom II", "1/48", "mid", 50),
        ("Tamiya", "Aircraft", "F-35A Lightning II", "1/48", "high", 85),
        ("GWH (Great Wall Hobby)", "Aircraft", "Su-27 Flanker B", "1/48", "high", 90),
        ("Tamiya", "Aircraft", "A-10 Thunderbolt II", "1/48", "high", 110),

        # Armor - Tanks
        ("Tamiya", "Armor", "Tiger I Late Production", "1/35", "mid", 55),
        ("Tamiya", "Armor", "King Tiger (Production Turret)", "1/35", "mid", 60),
        ("Tamiya", "Armor", "M4A3E8 Sherman Easy Eight", "1/35", "mid", 45),
        ("Tamiya", "Armor", "Panther Ausf.G", "1/35", "mid", 50),
        ("Tamiya", "Armor", "Leopard 2A6", "1/35", "mid", 65),
        ("Tamiya", "Armor", "M1A2 SEP Abrams TUSK II", "1/35", "mid", 70),
        ("Tamiya", "Armor", "T-34/85", "1/35", "standard", 30),
        ("Meng Model", "Armor", "Merkava Mk.4M w/ Trophy APS", "1/35", "high", 80),
        ("RFM (Rye Field Model)", "Armor", "Tiger I Early w/ Full Interior", "1/35", "high", 85),
        ("Takom", "Armor", "Maus V1 Super Heavy Tank", "1/35", "high", 75),

        # Ships
        ("Tamiya", "Ship", "Yamato (Premium Edition)", "1/350", "grail", 200),
        ("Tamiya", "Ship", "Bismarck", "1/350", "high", 120),
        ("Tamiya", "Ship", "USS Enterprise CV-6", "1/350", "high", 130),
        ("Tamiya", "Ship", "King George V", "1/350", "high", 100),
        ("Fujimi", "Ship", "IJN Akagi", "1/350", "high", 150),
        ("Trumpeter", "Ship", "USS Nimitz CVN-68", "1/350", "grail", 180),

        # Cars
        ("Tamiya", "Car", "Toyota GR Supra", "1/24", "standard", 32),
        ("Tamiya", "Car", "Nissan GT-R (R35)", "1/24", "standard", 35),
        ("Tamiya", "Car", "Ferrari FXX K", "1/24", "mid", 45),
        ("Tamiya", "Car", "Porsche 911 GT3 RS", "1/24", "mid", 42),
        ("Tamiya", "Car", "Mercedes-AMG GT3", "1/24", "mid", 40),
        ("Tamiya", "Car", "Ford GT", "1/24", "standard", 35),
        ("Tamiya", "Car", "LaFerrari", "1/24", "mid", 48),
        ("Hasegawa", "Car", "Toyota 2000GT", "1/24", "mid", 55),

        # Sci-fi
        ("Bandai", "Sci-fi", "Star Wars X-Wing Starfighter", "1/72", "mid", 40),
        ("Bandai", "Sci-fi", "Star Wars Millennium Falcon", "1/144", "high", 85),
        ("Bandai", "Sci-fi", "Star Wars Star Destroyer", "1/5000", "high", 100),
        ("Bandai", "Sci-fi", "Star Wars AT-AT", "1/144", "mid", 55),
        ("Bandai", "Sci-fi", "Star Wars TIE Fighter", "1/72", "standard", 28),
        ("Moebius", "Sci-fi", "Battlestar Galactica", "1/4105", "high", 120),
        ("Moebius", "Sci-fi", "1966 Batmobile", "1/25", "mid", 45),
        ("Bandai", "Sci-fi", "Star Wars Y-Wing Starfighter", "1/72", "mid", 42),

        # === NEW ITEMS (38 additions below) ===

        # More Aircraft (+8)
        ("Tamiya", "Aircraft", "Supermarine Spitfire Mk.I", "1/32", "high", 95),
        ("Hasegawa", "Aircraft", "F-14A Tomcat High Visibility", "1/48", "mid", 52),
        ("Trumpeter", "Aircraft", "Su-27 Flanker B", "1/32", "grail", 160),
        ("Eduard", "Aircraft", "Bf 109 G-6 Late ProfiPACK", "1/48", "mid", 46),
        ("Revell", "Aircraft", "B-17G Flying Fortress", "1/72", "mid", 42),
        ("Airfix", "Aircraft", "Supermarine Spitfire Mk.IXc", "1/24", "high", 130),
        ("Academy", "Aircraft", "F-22A Raptor", "1/72", "standard", 28),
        ("ICM", "Aircraft", "P-51D-15 Mustang", "1/48", "mid", 38),

        # More Armor (+6)
        ("Tamiya", "Armor", "Panther Ausf.D", "1/35", "mid", 52),
        ("Trumpeter", "Armor", "T-34/76 Model 1943", "1/35", "mid", 42),
        ("Dragon", "Armor", "King Tiger Henschel Turret", "1/35", "high", 85),
        ("Meng Model", "Armor", "Merkava Mk.4/4LIC", "1/35", "high", 82),
        ("RFM (Rye Field Model)", "Armor", "M1A1 Abrams w/ Full Interior", "1/35", "high", 90),
        ("Takom", "Armor", "Panzer III Ausf.M w/ Schurzen", "1/35", "mid", 55),

        # More Ships (+6)
        ("Tamiya", "Ship", "USS Enterprise CVN-65", "1/350", "grail", 190),
        ("Trumpeter", "Ship", "HMS Hood", "1/200", "grail", 250),
        ("Revell", "Ship", "RMS Titanic", "1/570", "mid", 45),
        ("Pontos", "Ship", "Yamato Detail-Up Set", "1/350", "grail", 280),
        ("Fujimi", "Ship", "IJN Akagi (Full Hull)", "1/350", "grail", 165),
        ("Academy", "Ship", "USS Missouri BB-63", "1/350", "high", 110),

        # More Cars (+6)
        ("Tamiya", "Car", "Ferrari 312T", "1/12", "grail", 220),
        ("Hasegawa", "Car", "Lancia Stratos HF", "1/24", "mid", 48),
        ("Beemax", "Car", "Audi Quattro S1 E2", "1/24", "mid", 55),
        ("NuNu", "Car", "BMW M3 E30 Gr.A 1988 Spa", "1/24", "mid", 45),
        ("Aoshima", "Car", "Toyota AE86 Sprinter Trueno", "1/24", "standard", 35),
        ("Fujimi", "Car", "Honda Civic EF9 Gr.A", "1/24", "mid", 40),

        # More Sci-Fi (+6)
        ("Bandai", "Sci-fi", "Star Wars X-Wing Starfighter (Red Five)", "1/72", "mid", 44),
        ("Bandai", "Sci-fi", "Star Wars AT-AT (Empire Strikes Back)", "1/144", "mid", 58),
        ("Moebius", "Sci-fi", "USS Enterprise NCC-1701 Refit", "1/350", "high", 140),
        ("Pegasus", "Sci-fi", "War of the Worlds Alien Machine", "1/32", "high", 85),
        ("Kotobukiya", "Sci-fi", "Frame Arms Baselard", "1/100", "mid", 52),
        ("Fine Molds", "Sci-fi", "Millennium Falcon", "1/72", "grail", 195),

        # Figures (+4)
        ("Tamiya", "Figure", "German Infantry Set (Late WWII)", "1/35", "standard", 18),
        ("MasterBox", "Figure", "US Paratroopers 1944", "1/35", "standard", 22),
        ("Alpine Miniatures", "Figure", "WSS Panzer Officer Resin Bust", "1/16", "high", 85),
        ("Nutsplanet", "Figure", "Fantasy Barbarian Resin Bust", "1/10", "high", 95),

        # Diorama / Accessories (+2)
        ("Tamiya", "Diorama", "Diorama Texture Paint Soil Effect Set", "N/A", "standard", 15),
        ("MiniArt", "Diorama", "European Village Building Ruins", "1/35", "standard", 32),

        # === ROUND 2 — 35 new items ===

        # 1:32 Aircraft
        ("Tamiya", "Aircraft", "P-51D Mustang", "1/32", "high", 110),
        ("Revell", "Aircraft", "B-17G Flying Fortress", "1/32", "grail", 180),
        ("Hasegawa", "Aircraft", "F-14A Tomcat", "1/32", "grail", 170),

        # 1:35 Modern Military
        ("Meng Model", "Armor", "M1A2 SEP Abrams TUSK I/II", "1/35", "high", 85),
        ("RFM (Rye Field Model)", "Armor", "Tiger I Late w/ Full Interior & Zimmerit", "1/35", "high", 95),
        ("Takom", "Armor", "Panther Ausf.A Late w/ Full Interior", "1/35", "high", 80),
        ("Tamiya", "Armor", "Challenger 2 (Desertised)", "1/35", "mid", 60),
        ("Meng Model", "Armor", "PLA ZTQ-15 Light Tank", "1/35", "mid", 65),

        # 1:700 Warships
        ("Fujimi", "Ship", "IJN Yamato Next Generation", "1/700", "mid", 55),
        ("Pitroad", "Ship", "IJN Destroyer Yukikaze", "1/700", "standard", 28),
        ("Pitroad", "Ship", "IJN Destroyer Shimakaze", "1/700", "standard", 30),
        ("Tamiya", "Ship", "USS Fletcher DD-445", "1/700", "standard", 22),

        # Sci-fi Kits
        ("Bandai", "Sci-fi", "Star Wars AT-AT (1/144 Scale Empire Strikes Back)", "1/144", "high", 85),
        ("Moebius", "Sci-fi", "Battlestar Galactica (New Series)", "1/4105", "high", 130),
        ("Bandai", "Sci-fi", "Star Wars Razor Crest (The Mandalorian)", "1/72", "mid", 55),
        ("Bandai", "Sci-fi", "Star Wars Slave I (Boba Fett)", "1/144", "mid", 48),

        # 1:24 Car Kits
        ("Tamiya", "Car", "Ferrari F40", "1/24", "mid", 48),
        ("Hasegawa", "Car", "Lancia 037 Rally", "1/24", "mid", 52),
        ("Tamiya", "Car", "Nissan Skyline GT-R (R32) Nismo", "1/24", "mid", 42),
        ("Aoshima", "Car", "Nissan Silvia S15 Spec-R", "1/24", "standard", 32),

        # Short Run / Limited — Eduard Profipack & Special Hobby
        ("Eduard", "Aircraft", "MiG-21MF Profipack", "1/48", "mid", 52),
        ("Eduard", "Aircraft", "Tempest Mk.V Series 2 Profipack", "1/48", "mid", 55),
        ("Special Hobby", "Aircraft", "Gloster Meteor FR.9", "1/48", "mid", 42),
        ("Special Hobby", "Aircraft", "Fairey Firefly FR.Mk.I", "1/48", "mid", 40),

        # Resin / Large-Scale — HobbyBoss & Trumpeter
        ("HobbyBoss", "Aircraft", "F-14D Super Tomcat", "1/32", "grail", 155),
        ("Trumpeter", "Aircraft", "MiG-29A Fulcrum", "1/32", "high", 130),
        ("Trumpeter", "Armor", "Soviet IS-7 Heavy Tank", "1/35", "high", 80),

        # Diorama Accessories
        ("MiniArt", "Diorama", "Street Section with Tram Line & Cobblestones", "1/35", "standard", 28),
        ("MiniArt", "Diorama", "Soviet Tank Crew at Rest (Figures)", "1/35", "standard", 20),
        ("Italeri", "Diorama", "Checkpoint (Afghan War)", "1/35", "standard", 35),

        # Vintage / OOP Classics
        ("Monogram", "Aircraft", "B-29 Superfortress (Pro Modeler)", "1/48", "high", 120),
        ("Monogram", "Car", "Tom Daniel Red Baron", "1/24", "high", 90),
        ("Aurora", "Sci-fi", "Creature from the Black Lagoon", "1/8", "grail", 250),
        ("Aurora", "Sci-fi", "Frankenstein Monster", "1/8", "grail", 220),

        # === ROUND 3 — 22 new items ===

        # Wingnut Wings — WWI Aircraft (OOP/Collectors)
        ("Wingnut Wings", "Aircraft", "Fokker Dr.I Triplane", "1/32", "grail", 200),
        ("Wingnut Wings", "Aircraft", "SE.5a (Hisso)", "1/32", "grail", 190),
        ("Wingnut Wings", "Aircraft", "Sopwith Camel (Clerget)", "1/32", "grail", 210),

        # Zoukei-Mura Super Wing Series
        ("Zoukei-Mura", "Aircraft", "Ta 152 H-1", "1/32", "high", 120),
        ("Zoukei-Mura", "Aircraft", "Horten Ho 229", "1/32", "high", 140),

        # Bronco Models — Light Vehicles & Artillery
        ("Bronco", "Armor", "British 17pdr Anti-Tank Gun Mk.I", "1/35", "mid", 45),
        ("Bronco", "Armor", "Humber Armoured Car Mk.IV", "1/35", "mid", 50),

        # Hobby Boss — Helicopters
        ("HobbyBoss", "Aircraft", "UH-60A Black Hawk", "1/72", "standard", 25),
        ("HobbyBoss", "Aircraft", "AH-1W Super Cobra", "1/72", "standard", 28),

        # Trumpeter 1:200 Ship Kits
        ("Trumpeter", "Ship", "USS Arizona BB-39 1941", "1/200", "grail", 230),
        ("Trumpeter", "Ship", "Bismarck", "1/200", "grail", 260),

        # 1:24 Rally Cars
        ("Hasegawa", "Car", "Toyota Celica GT-Four ST205 Safari Rally", "1/24", "mid", 58),
        ("NuNu", "Car", "Porsche 911 SC RS 1984 Oman Rally", "1/24", "mid", 50),
        ("Beemax", "Car", "Mitsubishi Lancer Turbo 1982 1000 Lakes Rally", "1/24", "mid", 52),

        # Tamiya 1:12 Motorcycle
        ("Tamiya", "Car", "Ducati Panigale 1199 S Tricolore", "1/12", "high", 85),
        ("Tamiya", "Car", "Kawasaki Ninja H2R", "1/12", "high", 80),

        # AMT / MPC Classic American
        ("AMT", "Car", "1967 Shelby GT-350 USPS Stamp Series", "1/25", "mid", 40),
        ("MPC", "Car", "1969 Dodge Charger R/T", "1/25", "mid", 42),

        # Zvezda Russian Military
        ("Zvezda", "Armor", "T-90MS Russian MBT", "1/35", "mid", 45),
        ("Zvezda", "Ship", "Borodino Russian Battleship", "1/350", "high", 95),

        # Italeri Aircraft
        ("Italeri", "Aircraft", "F-104G Starfighter", "1/32", "high", 100),

        # Kinetic — Modern Jets
        ("Kinetic", "Aircraft", "F/A-18C Hornet", "1/48", "mid", 55),

        # === ROUND 4 — 68 new items ===

        # 1/48 Modern Military Aircraft
        ("Tamiya", "Aircraft", "F/A-18E Super Hornet", "1/48", "mid", 65),
        ("Kinetic", "Aircraft", "F-16D Block 52+ Fighting Falcon", "1/48", "mid", 52),
        ("Hasegawa", "Aircraft", "Su-33 Flanker D", "1/48", "high", 85),
        ("Academy", "Aircraft", "F-15E Strike Eagle", "1/48", "mid", 48),
        ("Tamiya", "Aircraft", "Grumman F-14D Tomcat", "1/48", "high", 100),
        ("GWH (Great Wall Hobby)", "Aircraft", "MiG-29 Fulcrum 9-12 Late Type", "1/48", "high", 85),

        # 1/72 Aircraft (Accessible Kits)
        ("Airfix", "Aircraft", "Avro Vulcan B.2", "1/72", "high", 85),
        ("Airfix", "Aircraft", "BAe Hawk T.1 Red Arrows", "1/72", "standard", 20),
        ("Revell", "Aircraft", "Eurofighter Typhoon", "1/72", "standard", 22),
        ("Hasegawa", "Aircraft", "F-15J Eagle JASDF", "1/72", "standard", 28),
        ("Eduard", "Aircraft", "Spitfire Mk.Vb ProfiPACK", "1/72", "standard", 30),
        ("Airfix", "Aircraft", "Messerschmitt Bf 110C/D", "1/72", "standard", 25),

        # 1/35 Armor — Modern & Cold War
        ("Meng Model", "Armor", "Leopard 2A7+", "1/35", "high", 85),
        ("Takom", "Armor", "Chieftain Mk.5", "1/35", "mid", 55),
        ("Trumpeter", "Armor", "M48A5 Patton", "1/35", "mid", 48),
        ("RFM (Rye Field Model)", "Armor", "Panzer IV Ausf.J Late w/ Full Interior", "1/35", "high", 90),
        ("Dragon", "Armor", "StuG III Ausf.G Early Production", "1/35", "mid", 55),
        ("Tamiya", "Armor", "Type 10 MBT (JGSDF)", "1/35", "mid", 60),
        ("Meng Model", "Armor", "Russian T-72B3M", "1/35", "mid", 65),
        ("Zvezda", "Armor", "T-14 Armata", "1/35", "mid", 50),

        # 1/350 & 1/700 Ships
        ("Tamiya", "Ship", "IJN Mogami Heavy Cruiser", "1/350", "high", 90),
        ("Trumpeter", "Ship", "USS Hornet CV-8", "1/350", "grail", 175),
        ("Fujimi", "Ship", "IJN Zuikaku", "1/350", "high", 140),
        ("Tamiya", "Ship", "USS Indianapolis CA-35", "1/350", "high", 100),
        ("Fujimi", "Ship", "IJN Kongo", "1/700", "mid", 45),
        ("Tamiya", "Ship", "IJN Shokaku", "1/700", "mid", 40),
        ("Pitroad", "Ship", "IJN Destroyer Fubuki", "1/700", "standard", 25),
        ("Academy", "Ship", "USS Kitty Hawk CV-63", "1/800", "high", 95),

        # 1/24 Car Kits — Le Mans & Touring
        ("Tamiya", "Car", "Porsche 935 Martini", "1/24", "high", 80),
        ("NuNu", "Car", "Audi R8 LMS GT3", "1/24", "mid", 48),
        ("Hasegawa", "Car", "Mazda 787B 1991 Le Mans Winner", "1/24", "high", 85),
        ("Tamiya", "Car", "Ford GT40 Mk.II 1966 Le Mans", "1/24", "mid", 55),
        ("Aoshima", "Car", "Honda NSX-R (NA1)", "1/24", "mid", 38),
        ("Fujimi", "Car", "Toyota Supra A80 (Mk.IV)", "1/24", "mid", 42),
        ("Tamiya", "Car", "McLaren Senna", "1/24", "mid", 55),
        ("Beemax", "Car", "Nissan Skyline GT-R R32 Group A", "1/24", "mid", 52),

        # 1/12 Motorcycles
        ("Tamiya", "Car", "Honda RC213V 2014", "1/12", "high", 90),
        ("Tamiya", "Car", "Yamaha YZF-R1M", "1/12", "high", 80),
        ("Tamiya", "Car", "Suzuki GSX-R750 Yoshimura", "1/12", "mid", 65),

        # Sci-fi — Gundam & Mecha
        ("Bandai", "Sci-fi", "Star Wars A-Wing Starfighter", "1/72", "mid", 38),
        ("Bandai", "Sci-fi", "Star Wars Snowspeeder", "1/48", "mid", 48),
        ("Bandai", "Sci-fi", "Star Wars B-Wing Starfighter", "1/72", "mid", 42),
        ("Fine Molds", "Sci-fi", "TIE Fighter (Sullustan)", "1/72", "mid", 55),
        ("Moebius", "Sci-fi", "Lost in Space Jupiter 2", "1/35", "high", 130),
        ("Pegasus", "Sci-fi", "The Martian Hermes Spacecraft", "1/200", "high", 95),
        ("Kotobukiya", "Sci-fi", "Frame Arms Girl Stylet", "1/1", "mid", 52),

        # Figures — Military & Fantasy
        ("Tamiya", "Figure", "British Infantry Set (WWII)", "1/35", "standard", 18),
        ("MasterBox", "Figure", "Soviet Marines Attack 1941", "1/35", "standard", 20),
        ("MasterBox", "Figure", "German Tank Crew Normandy 1944", "1/35", "standard", 22),
        ("Alpine Miniatures", "Figure", "US Tanker WWII Resin Bust", "1/16", "high", 80),
        ("Nutsplanet", "Figure", "Samurai Warrior Resin Bust", "1/10", "high", 90),
        ("Nutsplanet", "Figure", "Viking Chieftain Resin Bust", "1/10", "high", 95),

        # Diorama Accessories
        ("MiniArt", "Diorama", "European City Block Ruins", "1/35", "standard", 35),
        ("Tamiya", "Diorama", "Brick Wall & Sandbag Set", "1/35", "standard", 12),
        ("MiniArt", "Diorama", "Middle East Village Diorama Base", "1/35", "standard", 30),
        ("Italeri", "Diorama", "WWII Battle Set — Battle of Berlin", "1/72", "mid", 45),

        # Vintage / OOP — More Classics
        ("Monogram", "Sci-fi", "Voyage to the Bottom of the Sea Seaview", "1/350", "high", 110),
        ("Aurora", "Sci-fi", "Dracula (Original Box Art Reissue)", "1/8", "grail", 200),
        ("Revell", "Aircraft", "SR-71 Blackbird", "1/48", "high", 85),
        ("Italeri", "Aircraft", "C-130J Hercules", "1/72", "mid", 55),

        # === ROUND 5 — 300+ new items to reach 500+ total ===

        # 1/48 WWII Fighters — More Brands
        ("Tamiya", "Aircraft", "P-38J Lightning", "1/48", "mid", 55),
        ("Tamiya", "Aircraft", "Corsair F4U-1D", "1/48", "mid", 48),
        ("Hasegawa", "Aircraft", "A6M5 Zero Fighter Type 52", "1/48", "mid", 38),
        ("Hasegawa", "Aircraft", "Bf 109 K-4", "1/48", "mid", 36),
        ("Eduard", "Aircraft", "P-39 Airacobra ProfiPACK", "1/48", "mid", 45),
        ("Eduard", "Aircraft", "La-5FN ProfiPACK", "1/48", "mid", 44),
        ("ICM", "Aircraft", "Yak-9T Soviet Fighter", "1/48", "mid", 35),
        ("ICM", "Aircraft", "Bf 109 F-4 WWII Luftwaffe", "1/48", "mid", 36),
        ("Airfix", "Aircraft", "Hawker Typhoon Mk.Ib", "1/24", "grail", 160),
        ("Academy", "Aircraft", "P-40E Warhawk", "1/48", "standard", 28),
        ("Trumpeter", "Aircraft", "P-47N Thunderbolt", "1/48", "mid", 42),

        # 1/48 Modern Jets — Expanded
        ("Tamiya", "Aircraft", "McDonnell Douglas F-4B Phantom II", "1/48", "high", 95),
        ("Kinetic", "Aircraft", "F/A-18A+ Hornet", "1/48", "mid", 50),
        ("Kinetic", "Aircraft", "EA-6B Prowler", "1/48", "mid", 58),
        ("Academy", "Aircraft", "F-35B Lightning II STOVL", "1/48", "mid", 50),
        ("Academy", "Aircraft", "F/A-18F Super Hornet", "1/48", "mid", 48),
        ("Hasegawa", "Aircraft", "F-2A Viper Zero JASDF", "1/48", "mid", 55),
        ("GWH (Great Wall Hobby)", "Aircraft", "F-15I Ra'am Israeli Air Force", "1/48", "high", 90),
        ("Tamiya", "Aircraft", "F-4EJ Phantom II JASDF", "1/48", "high", 85),
        ("HobbyBoss", "Aircraft", "Su-34 Fullback", "1/48", "high", 95),
        ("Trumpeter", "Aircraft", "J-20 Mighty Dragon", "1/48", "high", 88),

        # 1/32 Aircraft — Large Scale
        ("Tamiya", "Aircraft", "Bf 109 G-6", "1/32", "high", 100),
        ("Revell", "Aircraft", "F/A-18E Super Hornet", "1/32", "high", 120),
        ("Trumpeter", "Aircraft", "F-14B Tomcat", "1/32", "grail", 165),
        ("Trumpeter", "Aircraft", "A-10A Thunderbolt II", "1/32", "grail", 170),
        ("HobbyBoss", "Aircraft", "F-84G Thunderjet", "1/32", "high", 110),
        ("Zoukei-Mura", "Aircraft", "J2M3 Raiden (Jack)", "1/32", "high", 130),
        ("Zoukei-Mura", "Aircraft", "Do 335 A Pfeil", "1/32", "grail", 150),
        ("Wingnut Wings", "Aircraft", "Albatros D.Va", "1/32", "grail", 185),
        ("Wingnut Wings", "Aircraft", "Nieuport 17", "1/32", "grail", 195),

        # 1/72 Aircraft — Accessible Kits Expanded
        ("Airfix", "Aircraft", "Lancaster B.III Special (Dambuster)", "1/72", "high", 80),
        ("Airfix", "Aircraft", "English Electric Lightning F.6", "1/72", "mid", 30),
        ("Airfix", "Aircraft", "Handley Page Victor B.2", "1/72", "high", 85),
        ("Revell", "Aircraft", "Panavia Tornado IDS", "1/72", "standard", 22),
        ("Revell", "Aircraft", "Dassault Rafale C", "1/72", "standard", 20),
        ("Hasegawa", "Aircraft", "Kawasaki T-4 Blue Impulse", "1/72", "standard", 25),
        ("Hasegawa", "Aircraft", "F-4EJ Phantom II JASDF", "1/72", "standard", 28),
        ("Eduard", "Aircraft", "MiG-21bis ProfiPACK", "1/72", "standard", 28),
        ("Eduard", "Aircraft", "Bf 110E/F ProfiPACK", "1/72", "standard", 32),
        ("Italeri", "Aircraft", "B-52G Stratofortress", "1/72", "high", 80),
        ("Italeri", "Aircraft", "EF-2000 Typhoon", "1/72", "standard", 22),
        ("Academy", "Aircraft", "B-2 Spirit", "1/72", "mid", 50),
        ("ICM", "Aircraft", "He 111 H-6", "1/72", "mid", 35),

        # 1/144 Aircraft
        ("Revell", "Aircraft", "Airbus A380 Lufthansa", "1/144", "high", 85),
        ("Revell", "Aircraft", "Boeing 747-8 Lufthansa", "1/144", "mid", 65),
        ("Revell", "Aircraft", "Boeing 787-8 Dreamliner", "1/144", "mid", 55),
        ("Minicraft", "Aircraft", "Boeing 737-800 Southwest", "1/144", "standard", 28),

        # 1/35 Armor — WWII More Brands
        ("Tamiya", "Armor", "Churchill Mk.VII", "1/35", "mid", 48),
        ("Tamiya", "Armor", "Matilda Mk.III/IV", "1/35", "mid", 42),
        ("Tamiya", "Armor", "M26 Pershing", "1/35", "mid", 55),
        ("Tamiya", "Armor", "SdKfz 222", "1/35", "standard", 28),
        ("Tamiya", "Armor", "M3 Stuart Late Production", "1/35", "standard", 30),
        ("Dragon", "Armor", "Panzer IV Ausf.H Mid Production", "1/35", "mid", 55),
        ("Dragon", "Armor", "Tiger I Early Production", "1/35", "mid", 60),
        ("Dragon", "Armor", "Panzer III Ausf.L", "1/35", "mid", 50),
        ("Meng Model", "Armor", "Mark V British Heavy Tank", "1/35", "mid", 65),
        ("Meng Model", "Armor", "Sd.Kfz.171 Panther Ausf.A Early", "1/35", "high", 80),
        ("RFM (Rye Field Model)", "Armor", "Panther Ausf.G w/ Full Interior", "1/35", "high", 95),
        ("RFM (Rye Field Model)", "Armor", "Sherman M4A3 76W HVSS", "1/35", "mid", 65),
        ("Takom", "Armor", "Flakpanzer Panzer IV Wirbelwind", "1/35", "mid", 55),
        ("Takom", "Armor", "King Tiger Henschel w/ Full Interior", "1/35", "high", 85),

        # 1/35 Armor — Modern Continued
        ("Trumpeter", "Armor", "T-72B3 MBT with 4S24 ERA", "1/35", "mid", 55),
        ("Trumpeter", "Armor", "M1126 Stryker ICV", "1/35", "mid", 50),
        ("Meng Model", "Armor", "Russian BMR-3M Mine Clearing Vehicle", "1/35", "mid", 60),
        ("Meng Model", "Armor", "Chinese PLZ-05 155mm SP Howitzer", "1/35", "mid", 65),
        ("Zvezda", "Armor", "BMP-3 Infantry Fighting Vehicle", "1/35", "mid", 42),
        ("Zvezda", "Armor", "Russian MSTA-S 152mm SP Howitzer", "1/35", "mid", 48),
        ("HobbyBoss", "Armor", "Leopard 2A4 Dutch Army", "1/35", "mid", 55),
        ("HobbyBoss", "Armor", "AAVP-7A1 Assault Amphibious Vehicle", "1/35", "mid", 50),
        ("Bronco", "Armor", "Sd.Kfz.221 Leichter Panzerspahwagen", "1/35", "mid", 45),
        ("ICM", "Armor", "Panhard 178 AMD-35 French Armored Car", "1/35", "mid", 38),

        # 1/16 Armor — Large Scale Tanks
        ("Tamiya", "Armor", "Tiger I Early Production", "1/16", "grail", 350),
        ("Tamiya", "Armor", "Panther Ausf.G", "1/16", "grail", 380),
        ("Trumpeter", "Armor", "King Tiger Full Interior", "1/16", "grail", 450),

        # 1/350 Ships — Expanded
        ("Tamiya", "Ship", "Musashi (Premium Edition)", "1/350", "grail", 220),
        ("Tamiya", "Ship", "Prince of Wales", "1/350", "high", 120),
        ("Trumpeter", "Ship", "USS Yorktown CV-5", "1/350", "grail", 170),
        ("Trumpeter", "Ship", "USS Lexington CV-2", "1/350", "grail", 175),
        ("Trumpeter", "Ship", "HMS Warspite", "1/350", "high", 130),
        ("Fujimi", "Ship", "IJN Shokaku", "1/350", "high", 140),
        ("Fujimi", "Ship", "IJN Fuso 1944", "1/350", "high", 120),
        ("Academy", "Ship", "USS Enterprise CV-6 Battle of Midway", "1/350", "high", 135),
        ("Revell", "Ship", "HMS Ark Royal & Tribal Class Destroyer", "1/720", "mid", 35),

        # 1/700 Ships — Expanded
        ("Tamiya", "Ship", "IJN Kaga Aircraft Carrier", "1/700", "mid", 55),
        ("Tamiya", "Ship", "IJN Zuikaku", "1/700", "mid", 42),
        ("Tamiya", "Ship", "USS Hornet CV-8", "1/700", "mid", 40),
        ("Fujimi", "Ship", "IJN Nagato 1944", "1/700", "mid", 48),
        ("Fujimi", "Ship", "IJN Akagi 1941", "1/700", "mid", 45),
        ("Fujimi", "Ship", "IJN Shokaku 1941", "1/700", "mid", 42),
        ("Pitroad", "Ship", "IJN Agano Light Cruiser", "1/700", "standard", 28),
        ("Pitroad", "Ship", "IJN Tone Heavy Cruiser", "1/700", "standard", 30),
        ("Aoshima", "Ship", "IJN Heavy Cruiser Takao", "1/700", "standard", 25),
        ("Aoshima", "Ship", "IJN Destroyer Kagero", "1/700", "standard", 20),
        ("Hasegawa", "Ship", "IJN Aircraft Carrier Junyo", "1/700", "mid", 40),
        ("Hasegawa", "Ship", "IJN Battleship Mikasa", "1/700", "mid", 38),

        # 1/200 Ships — Large Scale
        ("Trumpeter", "Ship", "Tirpitz German Battleship", "1/200", "grail", 280),
        ("Trumpeter", "Ship", "HMS Prince of Wales", "1/200", "grail", 250),
        ("Revell", "Ship", "HMS Victory (Trafalgar)", "1/225", "mid", 55),

        # 1/24 Cars — JDM & European Sports
        ("Tamiya", "Car", "Mazda MX-5 Miata (NA)", "1/24", "standard", 32),
        ("Tamiya", "Car", "Honda NSX", "1/24", "mid", 42),
        ("Tamiya", "Car", "Lamborghini Countach LP500S", "1/24", "mid", 48),
        ("Tamiya", "Car", "BMW M3 (E30)", "1/24", "mid", 45),
        ("Tamiya", "Car", "Toyota Celica GT-Four RC", "1/24", "standard", 35),
        ("Hasegawa", "Car", "Subaru Impreza WRC 1997", "1/24", "mid", 52),
        ("Hasegawa", "Car", "Nissan Fairlady 240ZG", "1/24", "mid", 55),
        ("Hasegawa", "Car", "Mitsubishi Lancer GSR Evolution III", "1/24", "mid", 48),
        ("Aoshima", "Car", "Mazda FD3S RX-7 Spirit R Type A", "1/24", "mid", 38),
        ("Aoshima", "Car", "Nissan R34 Skyline GT-R V-Spec II", "1/24", "mid", 40),
        ("Aoshima", "Car", "Honda Civic EK9 Type R", "1/24", "standard", 32),
        ("Fujimi", "Car", "Nissan Fairlady Z (S30)", "1/24", "mid", 42),
        ("Fujimi", "Car", "Honda S2000 (AP1)", "1/24", "mid", 40),
        ("Fujimi", "Car", "Mazda Savanna RX-3", "1/24", "mid", 45),
        ("NuNu", "Car", "Ford Sierra Cosworth RS500 Group A", "1/24", "mid", 50),
        ("NuNu", "Car", "Toyota Corolla Levin AE92 Group A", "1/24", "mid", 48),
        ("Beemax", "Car", "BMW M3 E30 Rally Monte Carlo", "1/24", "mid", 55),
        ("Beemax", "Car", "Volvo 240 Turbo ETCC 1986", "1/24", "mid", 52),

        # 1/24 Cars — Supercars & Classics
        ("Tamiya", "Car", "Enzo Ferrari", "1/24", "mid", 50),
        ("Tamiya", "Car", "Lamborghini Aventador LP700-4", "1/24", "mid", 48),
        ("Tamiya", "Car", "Porsche Carrera GT", "1/24", "mid", 42),
        ("Tamiya", "Car", "Nissan 300ZX (Z32)", "1/24", "mid", 40),
        ("Tamiya", "Car", "Mercedes CLK-GTR", "1/24", "mid", 45),
        ("Revell", "Car", "Ford GT (2017) Le Mans", "1/24", "mid", 42),
        ("Revell", "Car", "BMW i8", "1/24", "standard", 30),
        ("Revell", "Car", "Porsche 918 Spyder", "1/24", "standard", 35),

        # 1/12 Cars & Motorcycles — Large Scale
        ("Tamiya", "Car", "Porsche 935 Martini", "1/12", "grail", 250),
        ("Tamiya", "Car", "Lotus Type 79 1978", "1/12", "grail", 240),
        ("Tamiya", "Car", "Honda RC166 GP Racer", "1/12", "high", 95),
        ("Tamiya", "Car", "Ducati Desmosedici GP4", "1/12", "high", 85),
        ("Tamiya", "Car", "Yamaha YZR-M1 2004", "1/12", "high", 82),
        ("Tamiya", "Car", "Honda CBR1000RR-R Fireblade SP", "1/12", "high", 80),

        # 1/25 American Classics
        ("AMT", "Car", "1969 Dodge Charger Daytona", "1/25", "mid", 42),
        ("AMT", "Car", "1970 Chevrolet Chevelle SS 454", "1/25", "mid", 38),
        ("AMT", "Car", "1969 Camaro Z/28 RS", "1/25", "mid", 40),
        ("MPC", "Car", "1970 Plymouth Barracuda", "1/25", "mid", 42),
        ("MPC", "Car", "1977 Pontiac Firebird Trans Am", "1/25", "mid", 40),
        ("Revell", "Car", "1968 Ford Mustang GT 2+2 Fastback", "1/25", "standard", 32),
        ("Revell", "Car", "'69 Corvette Stingray Convertible", "1/25", "standard", 30),
        ("Revell", "Car", "1970 Dodge Challenger T/A", "1/25", "standard", 32),

        # Sci-fi — Star Wars Expanded
        ("Bandai", "Sci-fi", "Star Wars Imperial Star Destroyer", "1/5000", "high", 100),
        ("Bandai", "Sci-fi", "Star Wars Blockade Runner (Tantive IV)", "1/1000", "mid", 55),
        ("Bandai", "Sci-fi", "Star Wars U-Wing Fighter", "1/72", "mid", 40),
        ("Bandai", "Sci-fi", "Star Wars Jedi Starfighter", "1/72", "standard", 30),
        ("Bandai", "Sci-fi", "Star Wars Naboo Starfighter", "1/72", "standard", 28),
        ("Bandai", "Sci-fi", "Star Wars Republic Gunship", "1/144", "mid", 52),
        ("Bandai", "Sci-fi", "Star Wars AT-ST (Return of the Jedi)", "1/48", "mid", 42),
        ("Bandai", "Sci-fi", "Star Wars Sandcrawler", "1/144", "mid", 55),
        ("Bandai", "Sci-fi", "Star Wars TIE Interceptor", "1/72", "standard", 28),
        ("Bandai", "Sci-fi", "Star Wars TIE Advanced x1", "1/72", "standard", 30),
        ("Bandai", "Sci-fi", "Star Wars Death Star II (Attack Phase)", "1/2700000", "mid", 45),

        # Sci-fi — Star Trek & Other Franchises
        ("Bandai", "Sci-fi", "Star Wars The Mandalorian N-1 Starfighter", "1/72", "mid", 48),
        ("Moebius", "Sci-fi", "Star Trek USS Enterprise NCC-1701-A", "1/350", "high", 145),
        ("Moebius", "Sci-fi", "Star Trek USS Reliant NCC-1864", "1/1000", "mid", 65),
        ("Moebius", "Sci-fi", "Star Trek Klingon Bird of Prey", "1/350", "high", 100),
        ("Pegasus", "Sci-fi", "Nautilus (20,000 Leagues Under the Sea)", "1/144", "high", 90),
        ("Pegasus", "Sci-fi", "War of the Worlds Tripod 1953", "1/48", "high", 85),
        ("AMT", "Sci-fi", "Star Trek USS Enterprise NCC-1701 Refit", "1/537", "mid", 45),
        ("AMT", "Sci-fi", "Star Trek Klingon Bird of Prey", "1/350", "mid", 40),

        # Sci-fi — Mecha & Anime
        ("Kotobukiya", "Sci-fi", "Armored Core White Glint", "1/72", "mid", 60),
        ("Kotobukiya", "Sci-fi", "Metal Gear REX", "1/100", "high", 85),
        ("Kotobukiya", "Sci-fi", "Evangelion Unit-01 Test Type", "1/100", "mid", 55),
        ("Fine Molds", "Sci-fi", "Star Wars Slave I (Jango Fett)", "1/72", "high", 120),
        ("Fine Molds", "Sci-fi", "Star Wars X-Wing Fighter (Red Five)", "1/48", "grail", 180),
        ("Hasegawa", "Sci-fi", "Macross VF-1S Valkyrie Roy Focker", "1/48", "high", 80),
        ("Hasegawa", "Sci-fi", "Macross VF-1J Valkyrie", "1/72", "mid", 55),

        # Figures — Expanded
        ("Tamiya", "Figure", "US Infantry (Normandy)", "1/35", "standard", 18),
        ("Tamiya", "Figure", "German Panzer Grenadiers", "1/35", "standard", 18),
        ("Tamiya", "Figure", "JGSDF Modern Infantry", "1/35", "standard", 20),
        ("Tamiya", "Figure", "Soviet Infantry (Winter)", "1/35", "standard", 18),
        ("MasterBox", "Figure", "Russian-Ukrainian War Territorial Defense", "1/35", "standard", 22),
        ("MasterBox", "Figure", "SAS Jeep Crew North Africa 1942", "1/35", "standard", 22),
        ("MasterBox", "Figure", "German Tankmen Kursk 1943", "1/35", "standard", 20),
        ("Alpine Miniatures", "Figure", "German Tiger Ace Resin Bust", "1/16", "high", 85),
        ("Alpine Miniatures", "Figure", "DAK Panzer Commander 1942", "1/16", "high", 82),
        ("Nutsplanet", "Figure", "Roman Legionnaire Resin Bust", "1/10", "high", 90),
        ("Nutsplanet", "Figure", "Japanese Samurai General", "1/10", "high", 95),
        ("Nutsplanet", "Figure", "WWII British Paratrooper", "1/10", "high", 88),
        ("MiniArt", "Figure", "German Tank Crew Winter 1943-45", "1/35", "standard", 18),
        ("MiniArt", "Figure", "Soviet Soldiers at Rest", "1/35", "standard", 16),

        # Diorama & Accessories — Expanded
        ("MiniArt", "Diorama", "Railway Station Platform", "1/35", "standard", 35),
        ("MiniArt", "Diorama", "German Tank Repair Crew", "1/35", "standard", 22),
        ("MiniArt", "Diorama", "Normandy Hedgerow Section", "1/35", "standard", 30),
        ("MiniArt", "Diorama", "Eastern Front Church Ruin", "1/35", "mid", 40),
        ("Tamiya", "Diorama", "German Field Maintenance Team & Equipment", "1/35", "standard", 25),
        ("Tamiya", "Diorama", "Sand Bag Set", "1/35", "standard", 10),
        ("Tamiya", "Diorama", "Jerry Can Set", "1/35", "standard", 8),
        ("Italeri", "Diorama", "D-Day Normandy Beach Set", "1/72", "mid", 48),
        ("Italeri", "Diorama", "Stalingrad Factory Ruin", "1/72", "mid", 42),

        # Helicopters — Expanded
        ("HobbyBoss", "Aircraft", "AH-64D Apache Longbow", "1/72", "standard", 28),
        ("HobbyBoss", "Aircraft", "Mi-24V Hind E", "1/72", "standard", 30),
        ("HobbyBoss", "Aircraft", "Ka-50 Black Shark", "1/72", "standard", 25),
        ("Italeri", "Aircraft", "CH-47F Chinook", "1/48", "mid", 55),
        ("Italeri", "Aircraft", "UH-1D Iroquois Huey", "1/48", "mid", 45),
        ("Revell", "Aircraft", "AH-64D Apache Longbow", "1/48", "mid", 45),
        ("Hasegawa", "Aircraft", "AH-1S Cobra Chopper JGSDF", "1/72", "standard", 25),
        ("Academy", "Aircraft", "MH-60G Pave Hawk", "1/72", "standard", 28),

        # WWI Aircraft
        ("Revell", "Aircraft", "Fokker Dr.I (Red Baron)", "1/72", "standard", 15),
        ("Eduard", "Aircraft", "Fokker D.VII ProfiPACK", "1/48", "mid", 45),
        ("Eduard", "Aircraft", "SPAD XIII ProfiPACK", "1/48", "mid", 42),
        ("Eduard", "Aircraft", "Albatros D.III OEFFAG ProfiPACK", "1/48", "mid", 44),
        ("Roden", "Aircraft", "Sopwith Triplane", "1/32", "mid", 55),
        ("Roden", "Aircraft", "Fokker E.III Eindecker", "1/32", "mid", 50),

        # WWII Bombers — Expanded
        ("HK Models", "Aircraft", "B-17G Flying Fortress", "1/32", "grail", 350),
        ("HK Models", "Aircraft", "Lancaster B Mk.I", "1/32", "grail", 380),
        ("HK Models", "Aircraft", "B-25J Mitchell", "1/32", "grail", 300),
        ("Revell", "Aircraft", "Avro Lancaster Mk.III", "1/72", "mid", 55),
        ("Airfix", "Aircraft", "Boeing B-17G Flying Fortress", "1/72", "mid", 60),
        ("Italeri", "Aircraft", "B-24D Liberator", "1/72", "mid", 48),
        ("Academy", "Aircraft", "B-29A Superfortress", "1/72", "mid", 55),

        # Vintage / OOP — More Classics
        ("Frog", "Aircraft", "Hawker Hurricane Mk.I", "1/72", "high", 85),
        ("Matchbox", "Aircraft", "Supermarine Walrus", "1/72", "mid", 55),
        ("Airfix", "Aircraft", "Concorde (Vintage Edition)", "1/144", "high", 80),
        ("Aurora", "Sci-fi", "Wolfman (Classic Monster)", "1/8", "grail", 210),
        ("Aurora", "Sci-fi", "Phantom of the Opera (Original)", "1/8", "grail", 230),
        ("Monogram", "Car", "Paddy Wagon (Show Rod)", "1/24", "high", 95),
        ("Monogram", "Sci-fi", "Space Shuttle (1/72)", "1/72", "mid", 65),

        # More Modern Armor
        ("Tamiya", "Armor", "French Main Battle Tank Leclerc Series 2", "1/35", "mid", 65),
        ("Tamiya", "Armor", "Centurion Mk.III", "1/35", "mid", 55),
        ("Tamiya", "Armor", "Cromwell Mk.IV", "1/35", "mid", 48),
        ("Trumpeter", "Armor", "Russian T-80BV MBT", "1/35", "mid", 50),
        ("Trumpeter", "Armor", "JGSDF Type 16 MCV", "1/35", "mid", 55),
        ("Dragon", "Armor", "M4A1 Sherman (75mm) Normandy", "1/35", "mid", 55),
        ("Dragon", "Armor", "SdKfz 251/1 Ausf.D Hanomag", "1/35", "mid", 50),
        ("Meng Model", "Armor", "Israeli Merkava Mk.3D Early", "1/35", "high", 80),
        ("Meng Model", "Armor", "D9R Armored Bulldozer", "1/35", "high", 85),
        ("Takom", "Armor", "SdKfz 182 King Tiger Porsche Turret", "1/35", "high", 78),
        ("Academy", "Armor", "M2A2 Bradley IFV Iraq 2003", "1/35", "mid", 42),
        ("Academy", "Armor", "K2 Black Panther Korean MBT", "1/35", "mid", 48),

        # Artillery & Softskins
        ("Tamiya", "Armor", "German 88mm Gun Flak 36/37", "1/35", "mid", 45),
        ("Tamiya", "Armor", "US M40 155mm SP Gun", "1/35", "mid", 50),
        ("Tamiya", "Armor", "German 3-Ton 4x2 Cargo Truck", "1/35", "standard", 35),
        ("Tamiya", "Armor", "US 2.5 Ton 6x6 Cargo Truck", "1/35", "standard", 35),
        ("Italeri", "Armor", "Sd.Kfz.7 German Half Track", "1/35", "standard", 38),
        ("MiniArt", "Armor", "GAZ-AAA Mod. 1943 Cargo Truck", "1/35", "standard", 30),
        ("ICM", "Armor", "Sd.Kfz.251/6 Ausf.A Command Vehicle", "1/35", "mid", 40),

        # === ROUND 6 — 70 new items to reach 500+ ===

        # 1/48 WWII — Twin-Engine Aircraft
        ("Tamiya", "Aircraft", "De Havilland Mosquito FB Mk.VI", "1/48", "mid", 55),
        ("Tamiya", "Aircraft", "Bristol Beaufighter Mk.VI", "1/48", "mid", 52),
        ("HobbyBoss", "Aircraft", "Me 262 A-1a/U4 Bomber Interceptor", "1/48", "mid", 48),
        ("Hasegawa", "Aircraft", "Kawanishi N1K2-J Shiden-Kai (George)", "1/48", "mid", 40),
        ("Eduard", "Aircraft", "Tempest Mk.V Series 1 ProfiPACK", "1/48", "mid", 52),

        # 1/48 Cold War — Additional Jets
        ("Tamiya", "Aircraft", "Douglas A-1H Skyraider", "1/48", "mid", 60),
        ("Kinetic", "Aircraft", "Mirage 2000C Multi-Role Combat Fighter", "1/48", "mid", 48),
        ("Academy", "Aircraft", "F-4J Phantom II VF-84 Jolly Rogers", "1/48", "mid", 50),
        ("HobbyBoss", "Aircraft", "A-7E Corsair II", "1/48", "mid", 45),
        ("Trumpeter", "Aircraft", "F-105G Thunderchief Wild Weasel", "1/48", "high", 80),

        # 1/32 WWII — More Fighters
        ("Tamiya", "Aircraft", "F4U-1 Corsair Birdcage", "1/32", "high", 110),
        ("Revell", "Aircraft", "Focke Wulf Fw 190 A-8 Sturmbock", "1/32", "high", 95),
        ("Hasegawa", "Aircraft", "Ki-61 Hien (Tony)", "1/32", "high", 90),

        # 1/35 Armor — WWII Self-Propelled Guns & Tank Destroyers
        ("Tamiya", "Armor", "Jagdpanther Late Production", "1/35", "mid", 55),
        ("Tamiya", "Armor", "Sturmgeschutz III Ausf.G (Finland)", "1/35", "mid", 48),
        ("Dragon", "Armor", "Jagdtiger Sd.Kfz.186", "1/35", "high", 75),
        ("Dragon", "Armor", "Nashorn Sd.Kfz.164", "1/35", "mid", 60),
        ("Tamiya", "Armor", "SU-76M Soviet Self-Propelled Gun", "1/35", "standard", 35),
        ("Tamiya", "Armor", "M10 IIC Achilles Tank Destroyer", "1/35", "mid", 48),

        # 1/35 Armor — Modern IFVs & APCs
        ("Meng Model", "Armor", "Russian BMP-3 IFV w/ ERA", "1/35", "mid", 58),
        ("Trumpeter", "Armor", "BTR-80A APC", "1/35", "mid", 45),
        ("HobbyBoss", "Armor", "LAV-25 USMC Light Armored Vehicle", "1/35", "mid", 48),
        ("Tamiya", "Armor", "Type 90 Tank (JGSDF)", "1/35", "mid", 60),
        ("Academy", "Armor", "ROK Army K1A1 MBT", "1/35", "mid", 45),

        # 1/350 Ships — More Aircraft Carriers
        ("Trumpeter", "Ship", "USS Ranger CV-4", "1/350", "high", 145),
        ("Fujimi", "Ship", "IJN Hiryu 1942", "1/350", "high", 135),
        ("Academy", "Ship", "USS Carl Vinson CVN-70", "1/350", "grail", 190),

        # 1/700 Ships — Modern Warships
        ("Trumpeter", "Ship", "USS Arleigh Burke DDG-51", "1/700", "standard", 28),
        ("Fujimi", "Ship", "JMSDF Kongo DDG-173", "1/700", "standard", 30),
        ("Pitroad", "Ship", "JMSDF Izumo Helicopter Destroyer", "1/700", "mid", 42),
        ("Tamiya", "Ship", "JMSDF Defense Ship LST-4001 Ohsumi", "1/700", "standard", 25),
        ("Hasegawa", "Ship", "JMSDF Aegis Destroyer Atago", "1/700", "standard", 30),

        # 1/24 Cars — More GT / Endurance Racing
        ("Tamiya", "Car", "Toyota TS050 Hybrid Gazoo Racing", "1/24", "mid", 55),
        ("Tamiya", "Car", "Porsche 911 RSR (2017 Le Mans)", "1/24", "mid", 52),
        ("NuNu", "Car", "McLaren F1 GTR Long Tail 1997 Le Mans", "1/24", "high", 80),
        ("NuNu", "Car", "BMW 320i E46 ETCC 2004", "1/24", "mid", 48),
        ("Hasegawa", "Car", "Jaguar XJR-9 1988 Le Mans", "1/24", "high", 85),

        # 1/12 and 1/20 — F1 and Open Wheel
        ("Tamiya", "Car", "Renault RE-20 Turbo", "1/12", "grail", 260),
        ("Hasegawa", "Car", "Lotus 79 1978 German GP", "1/20", "mid", 52),
        ("Tamiya", "Car", "Ferrari SF70H", "1/20", "mid", 55),

        # 1/24-1/25 — Trucks and Commercial Vehicles
        ("Italeri", "Car", "Scania R730 V8 Topline Imperial", "1/24", "high", 90),
        ("Italeri", "Car", "Mercedes-Benz Actros MP4 Gigaspace", "1/24", "high", 85),
        ("Revell", "Car", "Kenworth W-900 Conventional", "1/25", "mid", 48),
        ("AMT", "Car", "Peterbilt 352 Pacemaker COE", "1/25", "mid", 42),

        # Sci-fi — More Bandai Star Wars Vehicle Kits
        ("Bandai", "Sci-fi", "Star Wars AT-M6 First Order Walker", "1/144", "mid", 55),
        ("Bandai", "Sci-fi", "Star Wars Poe's X-Wing Fighter (Rise of Skywalker)", "1/72", "mid", 40),
        ("Bandai", "Sci-fi", "Star Wars Resistance A-Wing Fighter", "1/72", "standard", 30),
        ("Bandai", "Sci-fi", "Star Wars Kylo Ren TIE Silencer", "1/72", "mid", 38),
        ("Bandai", "Sci-fi", "Star Wars Y-Wing (The Mandalorian)", "1/72", "mid", 45),

        # Sci-fi — Polar Lights & Round 2 Kits
        ("Polar Lights", "Sci-fi", "Star Trek USS Enterprise NCC-1701 (Original Series)", "1/350", "high", 110),
        ("Polar Lights", "Sci-fi", "Star Trek Klingon K't'inga Class Battle Cruiser", "1/350", "high", 90),
        ("Polar Lights", "Sci-fi", "Forbidden Planet C-57D Starcruiser", "1/144", "high", 85),

        # Figures — More Manufacturers
        ("Tamiya", "Figure", "French Infantry Set (WWII)", "1/35", "standard", 18),
        ("ICM", "Figure", "WWII Soviet Female Snipers", "1/35", "standard", 22),
        ("ICM", "Figure", "WWII US Infantry (1942)", "1/35", "standard", 20),
        ("MasterBox", "Figure", "Desert Battle — Skull Clan Warriors (Fantasy)", "1/35", "standard", 22),
        ("Alpine Miniatures", "Figure", "German Panzer Commander Resin", "1/35", "mid", 45),

        # Diorama & Accessories — More
        ("MiniArt", "Diorama", "French City Building", "1/35", "mid", 40),
        ("Italeri", "Diorama", "WWII Battlefield Buildings", "1/72", "standard", 28),
        ("Tamiya", "Diorama", "Barricade Set", "1/35", "standard", 12),
        ("MiniArt", "Diorama", "Tank Workshop Equipment & Tools", "1/35", "standard", 18),

        # Additional kits to reach 500+
        ("Tamiya", "Aircraft", "North American B-25J Mitchell", "1/48", "mid", 60),
        ("Trumpeter", "Aircraft", "Su-25 Frogfoot", "1/32", "high", 120),
        ("Tamiya", "Armor", "Elefant Sd.Kfz.184", "1/35", "mid", 55),
        ("Meng Model", "Armor", "Leopard 2A4 German MBT", "1/35", "mid", 65),
        ("Tamiya", "Ship", "IJN Mikuma Heavy Cruiser", "1/350", "high", 95),

        # === ROUND 7 — 75 new items to reach 575+ total ===

        # 1/48 WWII — More Pacific Theater
        ("Tamiya", "Aircraft", "Mitsubishi J2M3 Raiden (Jack)", "1/48", "mid", 42),
        ("Hasegawa", "Aircraft", "Nakajima Ki-43 Hayabusa (Oscar)", "1/48", "standard", 32),
        ("Eduard", "Aircraft", "P-40N Warhawk ProfiPACK", "1/48", "mid", 46),
        ("Academy", "Aircraft", "SBD-2 Dauntless Battle of Midway", "1/48", "mid", 40),
        ("Hasegawa", "Aircraft", "Aichi D3A1 Val", "1/48", "mid", 38),

        # 1/48 Modern Jets — More NATO & Eastern Bloc
        ("Kinetic", "Aircraft", "Mirage IIIS Swiss Air Force", "1/48", "mid", 48),
        ("Academy", "Aircraft", "KF-21 Boramae Korean Fighter", "1/48", "mid", 52),
        ("Trumpeter", "Aircraft", "MiG-23MLD Flogger-K", "1/48", "mid", 55),
        ("HobbyBoss", "Aircraft", "F-111A Aardvark", "1/48", "high", 90),
        ("Tamiya", "Aircraft", "BAe Harrier GR.3", "1/48", "mid", 55),

        # 1/72 WWII Bombers
        ("Airfix", "Aircraft", "Handley Page Halifax B.III", "1/72", "mid", 55),
        ("Revell", "Aircraft", "De Havilland Mosquito B.IV", "1/72", "standard", 25),
        ("Airfix", "Aircraft", "Short Stirling B.I/III", "1/72", "mid", 50),

        # 1/35 Armor — WWII Rarities
        ("Dragon", "Armor", "Brummbar Late Production", "1/35", "mid", 58),
        ("Tamiya", "Armor", "Marder III M Sd.Kfz.138", "1/35", "mid", 45),
        ("Meng Model", "Armor", "A39 Tortoise British Heavy Assault Tank", "1/35", "high", 85),
        ("Takom", "Armor", "SMK Soviet Heavy Tank", "1/35", "mid", 60),
        ("RFM (Rye Field Model)", "Armor", "StuG III Ausf.G w/ Full Interior", "1/35", "high", 88),
        ("Dragon", "Armor", "Ferdinand Sd.Kfz.184", "1/35", "high", 75),

        # 1/35 Armor — Modern Middle East & Asia
        ("Meng Model", "Armor", "Israeli Namer Heavy APC", "1/35", "high", 82),
        ("Trumpeter", "Armor", "Indian T-90S Bhishma", "1/35", "mid", 55),
        ("HobbyBoss", "Armor", "ZBD-04A Chinese IFV", "1/35", "mid", 52),
        ("Academy", "Armor", "Turkish Altay MBT", "1/35", "mid", 48),

        # 1/350 Ships — More WWII Capital Ships
        ("Trumpeter", "Ship", "USS Saratoga CV-3", "1/350", "grail", 185),
        ("Fujimi", "Ship", "IJN Taiho Aircraft Carrier", "1/350", "high", 145),
        ("Tamiya", "Ship", "HMS Rodney British Battleship", "1/350", "high", 115),

        # 1/700 Ships — More IJN & USN
        ("Tamiya", "Ship", "IJN Chitose Seaplane Carrier", "1/700", "standard", 28),
        ("Fujimi", "Ship", "IJN Maya Heavy Cruiser 1944", "1/700", "standard", 30),
        ("Pitroad", "Ship", "JMSDF Murasame DD-101", "1/700", "standard", 28),
        ("Aoshima", "Ship", "JMSDF Aegis Destroyer Ashigara DDG-178", "1/700", "standard", 32),

        # 1/24 Cars — More Rally Legends
        ("Hasegawa", "Car", "Toyota Celica GT-Four ST165 1990 Safari Rally", "1/24", "mid", 55),
        ("NuNu", "Car", "Volvo S40 BTCC 1997 Champion", "1/24", "mid", 48),
        ("Beemax", "Car", "Toyota Celica TA64 1985 Safari Rally", "1/24", "mid", 55),
        ("Hasegawa", "Car", "Ford Escort RS1600 Mk.I RAC Rally", "1/24", "mid", 52),
        ("Aoshima", "Car", "Subaru BRZ (ZC6) Street Custom", "1/24", "standard", 30),

        # 1/24 Cars — European Exotics
        ("Tamiya", "Car", "Alfa Romeo Giulia Sprint GTA", "1/24", "mid", 48),
        ("Tamiya", "Car", "Mercedes-Benz 300 SL Gullwing", "1/24", "mid", 55),
        ("Revell", "Car", "Jaguar E-Type Roadster", "1/24", "standard", 35),
        ("Italeri", "Car", "Lancia Delta HF Integrale 16V", "1/24", "mid", 42),
        ("Italeri", "Car", "Fiat 500 F (1968)", "1/24", "standard", 28),

        # 1/25 Cars — More American Muscle
        ("AMT", "Car", "1971 Plymouth Hemi Cuda", "1/25", "mid", 42),
        ("MPC", "Car", "1972 Pontiac GTO The Judge", "1/25", "mid", 40),
        ("Revell", "Car", "'70 Dodge Challenger 2 in 1", "1/25", "standard", 30),

        # 1/12 Motorcycles — More Tamiya
        ("Tamiya", "Car", "Honda RC211V 2006", "1/12", "high", 85),
        ("Tamiya", "Car", "Ducati 1199 Panigale S", "1/12", "high", 82),
        ("Tamiya", "Car", "Kawasaki Ninja ZX-14 Special Color Edition", "1/12", "high", 78),
        ("Tamiya", "Car", "Repsol Honda RC213V 2014 Marc Marquez", "1/12", "high", 88),

        # Sci-fi — Gundam & Anime Kits
        ("Bandai", "Sci-fi", "Star Wars V-Wing Starfighter", "1/72", "standard", 28),
        ("Bandai", "Sci-fi", "Star Wars Sith Infiltrator", "1/72", "mid", 42),
        ("AMT", "Sci-fi", "Star Trek USS Defiant NX-74205", "1/420", "mid", 38),
        ("Polar Lights", "Sci-fi", "Star Trek USS Enterprise NCC-1701-D", "1/1400", "mid", 45),
        ("Moebius", "Sci-fi", "2001 A Space Odyssey Discovery XD-1", "1/350", "high", 120),
        ("Pegasus", "Sci-fi", "Area 51 UFO (Roswell)", "1/72", "mid", 48),

        # Figures — More Variety
        ("Tamiya", "Figure", "German Afrika Korps Infantry Set", "1/35", "standard", 18),
        ("Tamiya", "Figure", "Russian Army Assault Infantry", "1/35", "standard", 18),
        ("ICM", "Figure", "WWII French Infantry (1940)", "1/35", "standard", 20),
        ("MasterBox", "Figure", "Italian Paratroopers WWII", "1/35", "standard", 22),
        ("Alpine Miniatures", "Figure", "US 101st Airborne Resin 1944", "1/35", "mid", 48),

        # Diorama & Accessories
        ("MiniArt", "Diorama", "Berlin 1945 Street Scene", "1/35", "mid", 42),
        ("MiniArt", "Diorama", "Industrial Building Ruins", "1/35", "mid", 38),
        ("Tamiya", "Diorama", "German Military Motorcycle w/ Sidecar", "1/35", "standard", 22),

        # 1/24 Trucks — European Haulers
        ("Italeri", "Car", "Volvo FH16 Globetrotter XL", "1/24", "high", 88),
        ("Italeri", "Car", "MAN TGX XXL Wolf Transporte", "1/24", "high", 85),
        ("Revell", "Car", "Mercedes-Benz Actros MP3", "1/24", "high", 82),

        # Vintage / OOP — Collector Items
        ("Aurora", "Sci-fi", "The Mummy (Classic Monster)", "1/8", "grail", 240),
        ("Monogram", "Aircraft", "P-61 Black Widow", "1/48", "high", 100),
        ("Matchbox", "Aircraft", "Handley Page 0/400", "1/72", "high", 75),
        ("Frog", "Aircraft", "Bristol Beaufighter TF.X", "1/72", "high", 80),
        ("Airfix", "Aircraft", "Avro Lancaster B.I (Vintage Classic)", "1/72", "mid", 45),

        # ── Tamiya 1/35 Military — Additional Armor ─────────────────────
        ("Tamiya", "Armor", "Tiger I Early Production (Afrika Korps)", "1/35", "mid", 55),
        ("Tamiya", "Armor", "Panther Ausf.D (Battle of Kursk)", "1/35", "mid", 52),
        ("Tamiya", "Armor", "M1A2 Abrams (Operation Iraqi Freedom)", "1/35", "mid", 68),
        ("Tamiya", "Armor", "T-72M1 (Modern Russian MBT)", "1/35", "mid", 48),
        ("Tamiya", "Armor", "M26 Pershing (T26E3)", "1/35", "mid", 48),

        # ── Trumpeter 1/350 Ships ────────────────────────────────────────
        ("Trumpeter", "Ship", "Bismarck (German Battleship)", "1/350", "high", 120),
        ("Trumpeter", "Ship", "Yamato (IJN Battleship)", "1/350", "high", 140),
        ("Trumpeter", "Ship", "USS Iowa BB-61", "1/350", "high", 130),
        ("Trumpeter", "Ship", "HMS Hood (British Battlecruiser)", "1/350", "high", 110),
        ("Trumpeter", "Ship", "USS Enterprise CV-6", "1/350", "grail", 180),
        ("Trumpeter", "Ship", "Tirpitz (German Battleship)", "1/350", "high", 125),
        ("Trumpeter", "Ship", "Admiral Kuznetsov (Russian Carrier)", "1/350", "high", 135),
        ("Trumpeter", "Ship", "USS Missouri BB-63", "1/350", "high", 130),

        # ── Airfix 1/72 Aircraft ─────────────────────────────────────────
        ("Airfix", "Aircraft", "Supermarine Spitfire Mk.Vb", "1/72", "standard", 18),
        ("Airfix", "Aircraft", "Avro Lancaster B.III (Dambusters)", "1/72", "mid", 48),
        ("Airfix", "Aircraft", "de Havilland Mosquito B.XVI", "1/72", "mid", 40),
        ("Airfix", "Aircraft", "Hawker Hurricane Mk.I", "1/72", "standard", 15),
        ("Airfix", "Aircraft", "BAe Harrier GR.9", "1/72", "mid", 35),
        ("Airfix", "Aircraft", "Bristol Blenheim Mk.IV", "1/72", "standard", 28),

        # ── Revell 1/72 Aircraft ─────────────────────────────────────────
        ("Revell", "Aircraft", "F-14A Tomcat (Top Gun)", "1/72", "mid", 35),
        ("Revell", "Aircraft", "SR-71A Blackbird", "1/72", "mid", 42),
        ("Revell", "Aircraft", "F/A-18E Super Hornet", "1/72", "standard", 22),
        ("Revell", "Aircraft", "Heinkel He 111 H-6", "1/72", "mid", 38),

        # ── Meng Models ──────────────────────────────────────────────────
        ("Meng Model", "Armor", "Sd.Kfz.171 Panther Ausf.A (Late)", "1/35", "high", 82),
        ("Meng Model", "Armor", "M2A3 Bradley IFV w/ BUSK III", "1/35", "mid", 70),
        ("Meng Model", "Armor", "Leopard 2A7+ (German MBT)", "1/35", "high", 85),
        ("Meng Model", "SD Cute", "World War Toons Sherman (SD)", "SD", "standard", 18),
        ("Meng Model", "SD Cute", "World War Toons Tiger I (SD)", "SD", "standard", 18),
        ("Meng Model", "SD Cute", "World War Toons P-51 Mustang (SD)", "SD", "standard", 16),

        # ── Takom 1/35 WWI/WWII ──────────────────────────────────────────
        ("Takom", "Armor", "Mk.IV Male WWI Tank", "1/35", "mid", 55),
        ("Takom", "Armor", "St. Chamond French Heavy Tank (WWI)", "1/35", "mid", 52),
        ("Takom", "Armor", "Panzer III Ausf.M w/ Schürzen", "1/35", "mid", 48),
        ("Takom", "Armor", "Jagdpanther G1 Early Production", "1/35", "mid", 58),
        ("Takom", "Armor", "Chieftain Mk.10 (British MBT)", "1/35", "mid", 60),

        # ── Rye Field Model 1/35 ─────────────────────────────────────────
        ("RFM (Rye Field Model)", "Armor", "Tiger I Late Production w/ Zimmerit & Full Interior", "1/35", "high", 95),
        ("RFM (Rye Field Model)", "Armor", "M4A3E8 Sherman w/ Workable Track Links", "1/35", "mid", 55),
        ("RFM (Rye Field Model)", "Armor", "Leopard 2A6 Main Battle Tank w/ Full Interior", "1/35", "high", 90),
        ("RFM (Rye Field Model)", "Armor", "T-34/85 Model 1944 No.174 Factory", "1/35", "mid", 48),
        ("RFM (Rye Field Model)", "Armor", "Sturmtiger w/ Full Interior", "1/35", "high", 85),

        # ── Tamiya 1/35 Military (Additional) ───────────────────────────────
        ("Tamiya", "Armor", "M41 Walker Bulldog", "1/35", "mid", 40),
        ("Tamiya", "Armor", "Jagdpanzer IV/70(V) Lang", "1/35", "mid", 48),
        ("Tamiya", "Armor", "Cromwell Mk.IV Cruiser Tank", "1/35", "mid", 42),
        ("Tamiya", "Armor", "StuG III Ausf.G (Finnish Army)", "1/35", "mid", 45),
        ("Tamiya", "Armor", "Type 10 Tank (JGSDF)", "1/35", "mid", 55),
        ("Tamiya", "Armor", "Sd.Kfz.234/2 Puma", "1/35", "mid", 44),
        ("Tamiya", "Armor", "Nashorn German Heavy SP Gun", "1/35", "mid", 46),
        ("Tamiya", "Armor", "M48A3 Patton", "1/35", "mid", 48),

        # ── Hasegawa 1/48 Aircraft (Additional) ─────────────────────────────
        ("Hasegawa", "Aircraft", "F-104G Starfighter (Luftwaffe)", "1/48", "mid", 42),
        ("Hasegawa", "Aircraft", "Ki-84 Frank (Type 4 Fighter Hayate)", "1/48", "mid", 38),
        ("Hasegawa", "Aircraft", "F-86F Sabre (USAF)", "1/48", "mid", 40),
        ("Hasegawa", "Aircraft", "P-40N Warhawk", "1/48", "mid", 36),
        ("Hasegawa", "Aircraft", "Bf109K-4 (Late War)", "1/48", "mid", 42),
        ("Hasegawa", "Aircraft", "A6M5c Zero Type 52 Hei", "1/48", "mid", 44),
        ("Hasegawa", "Aircraft", "Tornado IDS (Luftwaffe)", "1/48", "mid", 48),
        ("Hasegawa", "Aircraft", "F-8E Crusader (VF-162)", "1/48", "mid", 45),

        # ── Revell Car Kits ──────────────────────────────────────────────────
        ("Revell", "Car", "Shelby GT350H 1966", "1/24", "mid", 35),
        ("Revell", "Car", "Plymouth GTX 1970", "1/24", "standard", 28),
        ("Revell", "Car", "Kenworth W-900 Truck", "1/25", "mid", 55),
        ("Revell", "Car", "Chevy Impala SS 1964 (Lowrider)", "1/25", "mid", 38),
        ("Revell", "Car", "VW T1 Samba Bus (Flower Power)", "1/24", "mid", 42),
        ("Revell", "Car", "Porsche Panamera Turbo S", "1/24", "standard", 30),
        ("Revell", "Car", "Citroen 2CV Charleston", "1/24", "mid", 35),
        ("Revell", "Car", "Mercedes-Benz 300 SL Gullwing", "1/24", "mid", 40),

        # ── Trumpeter Ships ──────────────────────────────────────────────────
        ("Trumpeter", "Ship", "HMS Hood (Battlecruiser)", "1/350", "high", 115),
        ("Trumpeter", "Ship", "Yamato (Japanese Battleship)", "1/350", "grail", 160),
        ("Trumpeter", "Ship", "USS Fletcher DD-445", "1/350", "mid", 65),
        ("Trumpeter", "Ship", "Type VIIC U-Boat", "1/144", "mid", 55),
        ("Trumpeter", "Ship", "HMS Warspite (Battleship)", "1/350", "high", 120),

        # ── Meng AFV Kits ────────────────────────────────────────────────────
        ("Meng", "Armor", "PzH 2000 Self-Propelled Howitzer", "1/35", "mid", 68),
        ("Meng", "Armor", "Merkava Mk.4M w/ Trophy APS", "1/35", "mid", 72),
        ("Meng", "Armor", "FT-17 French Light Tank (Cast Turret)", "1/35", "mid", 40),
        ("Meng", "Armor", "King Tiger Porsche Turret w/ Interior", "1/35", "high", 95),
        ("Meng", "Armor", "T-90A Russian MBT", "1/35", "mid", 60),
        ("Meng", "Armor", "M2A3 Bradley BUSK III IFV", "1/35", "mid", 65),
        ("Meng", "Armor", "PLZ 05 Chinese 155mm SP Howitzer", "1/35", "mid", 58),

        # ── Eduard Limited Editions ──────────────────────────────────────────
        ("Eduard", "Aircraft", "Spitfire Mk.IX Royal Class (Dual Combo)", "1/48", "grail", 165),
        ("Eduard", "Aircraft", "Bf109G-6 Royal Class (Dual Combo)", "1/48", "grail", 155),
        ("Eduard", "Aircraft", "Fw 190A-8 ProfiPACK", "1/48", "high", 85),
        ("Eduard", "Aircraft", "MiG-21MF ProfiPACK", "1/48", "high", 80),
        ("Eduard", "Aircraft", "P-51D-5 Mustang ProfiPACK", "1/48", "high", 78),
        ("Eduard", "Aircraft", "Tempest Mk.V Series 2 ProfiPACK", "1/48", "high", 82),

        # ── Wingnut Wings WWI (Discontinued/Collectible) ─────────────────────
        ("Wingnut Wings", "Aircraft", "Fokker E.III Eindecker", "1/32", "grail", 220),
        ("Wingnut Wings", "Aircraft", "Pfalz D.IIIa", "1/32", "grail", 210),
        ("Wingnut Wings", "Aircraft", "Halberstadt CL.II", "1/32", "grail", 260),

        # ── Academy 1/72 Jets ────────────────────────────────────────────────
        ("Academy", "Aircraft", "F-22A Raptor (USAF)", "1/72", "standard", 28),
        ("Academy", "Aircraft", "F/A-18E Super Hornet", "1/72", "standard", 25),
        ("Academy", "Aircraft", "KF-21 Boramae (Korean Fighter)", "1/72", "mid", 35),
        ("Academy", "Aircraft", "F-15K Slam Eagle (ROKAF)", "1/72", "standard", 28),
        ("Academy", "Aircraft", "MiG-29A Fulcrum", "1/72", "standard", 22),
        ("Academy", "Aircraft", "F-16CG/CJ Block 40 (Fighting Falcon)", "1/72", "standard", 24),

        # ── ICM Figures ──────────────────────────────────────────────────────
        ("ICM", "Figure", "US Paratroopers (D-Day 1944)", "1/35", "standard", 18),
        ("ICM", "Figure", "German Infantry in Gas Masks (WWI)", "1/35", "standard", 16),
        ("ICM", "Figure", "Soviet Female Snipers (WWII)", "1/35", "standard", 17),
        ("ICM", "Figure", "SEAL Team Six (Modern)", "1/35", "standard", 20),
        ("ICM", "Figure", "British Infantry Somme Battle (WWI)", "1/35", "standard", 18),
        ("ICM", "Figure", "German Tankmen (Kursk 1943)", "1/35", "standard", 16),

        # ── Zvezda WWII Kits ─────────────────────────────────────────────────
        ("Zvezda", "Armor", "T-34/76 Model 1942", "1/35", "standard", 25),
        ("Zvezda", "Armor", "IS-2 (Stalin Tank)", "1/35", "standard", 30),
        ("Zvezda", "Armor", "KV-1 Heavy Tank", "1/35", "standard", 28),
        ("Zvezda", "Armor", "BT-5 Fast Tank", "1/35", "standard", 22),
        ("Zvezda", "Armor", "GAZ Tiger Russian Armored Vehicle", "1/35", "standard", 26),
        ("Zvezda", "Aircraft", "Yak-3 Soviet Fighter", "1/48", "standard", 20),
        ("Zvezda", "Aircraft", "IL-2 Shturmovik", "1/48", "standard", 28),
        ("Zvezda", "Ship", "Knyaz Suvorov Russian Battleship", "1/350", "mid", 55),

        # ── Additional Scale Models (+8) ────────────────────────────────────
        ("Wingnut Wings", "Aircraft", "Sopwith Camel F.1", "1/32", "high", 95),
        ("Bronco Models", "Armor", "CV-33 Tankette Series II", "1/35", "standard", 28),
        ("Meng Model", "Armor", "Merkava Mk.4M w/Trophy APS", "1/35", "mid", 65),
        ("Meng Model", "Aircraft", "F-35A Lightning II", "1/48", "mid", 58),
        ("Trumpeter", "Ship", "USS Missouri BB-63", "1/200", "grail", 280),
        ("Academy", "Aircraft", "F-14A Tomcat (US Navy)", "1/48", "mid", 42),
        ("Academy", "Armor", "M1A2 SEP Abrams TUSK II", "1/35", "mid", 48),
    ]

    kits = kits + _variant_expansion()

    catalog = []
    for manufacturer, model_type, name, scale, tier, price in kits:
        catalog.append({
            "manufacturer": manufacturer,
            "model_type": model_type,
            "name": name,
            "scale": scale,
            "rarity_tier": tier,
            "price_eur": price,
        })
    # Deduplicate by ('manufacturer', 'name', 'scale') (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = (item["manufacturer"], item["name"], item["scale"])
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


def item_to_catalog_item(item: dict) -> CatalogItem:
    manufacturer = item["manufacturer"]
    name = item["name"]
    model_type = item["model_type"]
    scale = item["scale"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{manufacturer}-{name}-{scale}"),
        title=f"{name} ({scale})",
        set_code=slugify(model_type),
        brand=manufacturer,
        rarity=item["rarity_tier"].title(),
        notes=f"{manufacturer} | {model_type} | {scale}",
        attributes_json={
            "manufacturer": manufacturer,
            "model_type": model_type,
            "scale": scale,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    model_type = item["model_type"]
    type_scores = {
        "Aircraft": 0.5,
        "Armor": 0.5,
        "Ship": 0.7,
        "Car": 0.4,
        "Sci-fi": 0.6,
    }

    manufacturer = item["manufacturer"]
    mfr_scores = {
        "Tamiya": 0.7,
        "Hasegawa": 0.5,
        "Eduard": 0.6,
        "Bandai": 0.6,
        "Meng Model": 0.6,
        "RFM (Rye Field Model)": 0.65,
        "Takom": 0.5,
        "GWH (Great Wall Hobby)": 0.55,
        "Fujimi": 0.5,
        "Trumpeter": 0.5,
        "Moebius": 0.6,
    }

    edition_score = (type_scores.get(model_type, 0.5) + mfr_scores.get(manufacturer, 0.5)) / 2

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": round(edition_score, 2),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import Scale Models catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Scale Models Import ===")

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

    logger.info(f"\n=== Scale Models Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
