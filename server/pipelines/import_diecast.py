"""
Import diecast vehicle collectibles data.

Layer 1 (Catalog):  Curated Hot Wheels, Matchbox, AUTOart, Kyosho, etc. → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Sources:
- Curated catalog of Hot Wheels RLC, Super Treasure Hunts, Matchbox vintage,
  AUTOart 1:18, Kyosho 1:43, Minichamps F1, Greenlight chase
- Can be augmented with hobbyDB or eBay sold listings later

Usage:
    python -m pipelines.import_diecast [--dry-run]
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

CATEGORY = "diecast"


def get_curated_catalog() -> list[dict]:
    """Curated diecast vehicle collector catalog (500+ items)."""

    # Format: (brand, name, scale, variant, rarity_tier, price_eur)
    # rarity_tier: grail (>200), high (100-200), mid (40-100), standard (<40)

    vehicles = [
        # Hot Wheels Red Line Club (RLC) Exclusives
        ("Hot Wheels RLC", "'55 Chevy Bel Air Gasser", "1:64", "RLC Exclusive 2023", "high", 120),
        ("Hot Wheels RLC", "'71 Datsun 510", "1:64", "RLC Exclusive", "high", 150),
        ("Hot Wheels RLC", "Porsche 993 GT2", "1:64", "RLC Exclusive", "grail", 200),
        ("Hot Wheels RLC", "'69 Dodge Charger R/T", "1:64", "RLC Exclusive", "high", 130),
        ("Hot Wheels RLC", "Nissan Skyline GT-R (R34)", "1:64", "RLC Exclusive", "grail", 180),
        ("Hot Wheels RLC", "Custom Mustang (Spectraflame)", "1:64", "RLC Exclusive", "high", 100),
        ("Hot Wheels RLC", "'64 Impala", "1:64", "RLC Exclusive", "high", 110),
        ("Hot Wheels RLC", "Lamborghini Countach LP500S", "1:64", "RLC Exclusive", "high", 140),

        # Hot Wheels Super Treasure Hunts ($TH)
        ("Hot Wheels $TH", "Toyota AE86 Sprinter Trueno", "1:64", "Super Treasure Hunt", "high", 80),
        ("Hot Wheels $TH", "Porsche 911 GT3 RS", "1:64", "Super Treasure Hunt", "mid", 60),
        ("Hot Wheels $TH", "Nissan Skyline GT-R (BNR32)", "1:64", "Super Treasure Hunt", "mid", 70),
        ("Hot Wheels $TH", "'92 BMW M3", "1:64", "Super Treasure Hunt", "mid", 55),
        ("Hot Wheels $TH", "Tesla Model S", "1:64", "Super Treasure Hunt", "mid", 50),
        ("Hot Wheels $TH", "'70 Chevelle SS", "1:64", "Super Treasure Hunt 2022", "mid", 45),
        ("Hot Wheels $TH", "McLaren Senna", "1:64", "Super Treasure Hunt", "high", 100),
        ("Hot Wheels $TH", "Mazda RX-7 (FD)", "1:64", "Super Treasure Hunt", "mid", 65),

        # Matchbox Vintage
        ("Matchbox", "No. 75 Ferrari Berlinetta", "1:64", "Lesney Vintage 1965", "high", 80),
        ("Matchbox", "No. 41 Ford GT40", "1:64", "Lesney Vintage 1966", "mid", 60),
        ("Matchbox", "No. 5 Lotus Europa", "1:64", "Lesney Vintage 1969", "mid", 50),
        ("Matchbox", "No. 1 Mercedes Benz Lorry", "1:64", "Lesney Vintage 1968", "mid", 45),
        ("Matchbox", "No. 67 Volkswagen 1600 TL", "1:64", "Lesney Vintage 1967", "mid", 55),
        ("Matchbox", "Superfast No. 20 Lamborghini Marzal", "1:64", "Superfast 1969", "mid", 50),
        ("Matchbox", "Models of Yesteryear Y-1 Allchin", "1:64", "Yesteryear Vintage", "standard", 25),
        ("Matchbox", "Models of Yesteryear Y-16 Spyker", "1:64", "Yesteryear Vintage", "standard", 20),

        # AUTOart 1:18 Scale
        ("AUTOart", "Porsche 911 (993) Carrera", "1:18", "Composite", "high", 200),
        ("AUTOart", "Lamborghini Aventador SVJ", "1:18", "Composite", "grail", 350),
        ("AUTOart", "Nissan GT-R (R35) Nismo", "1:18", "Composite", "grail", 300),
        ("AUTOart", "McLaren 720S", "1:18", "Composite", "high", 250),
        ("AUTOart", "Toyota 2000GT", "1:18", "Composite", "grail", 380),
        ("AUTOart", "Ford GT (2017)", "1:18", "Composite", "high", 200),
        ("AUTOart", "Koenigsegg One:1", "1:18", "Composite", "grail", 400),
        ("AUTOart", "Bugatti Chiron", "1:18", "Composite", "grail", 350),

        # Kyosho 1:43 Scale
        ("Kyosho", "Ferrari F40", "1:43", "High-End", "mid", 60),
        ("Kyosho", "Lamborghini Miura SV", "1:43", "High-End", "mid", 70),
        ("Kyosho", "Nissan Skyline 2000 GT-R (KPGC10)", "1:43", "High-End", "mid", 55),
        ("Kyosho", "Toyota Supra (A80)", "1:43", "High-End", "mid", 50),
        ("Kyosho", "Shelby Cobra 427 S/C", "1:43", "High-End", "high", 80),
        ("Kyosho", "Ferrari 250 GTO", "1:43", "High-End", "high", 120),

        # Minichamps F1 Cars
        ("Minichamps", "Red Bull RB19 Verstappen 2023", "1:43", "F1 Collection", "high", 100),
        ("Minichamps", "Mercedes W11 Hamilton 2020", "1:43", "F1 Collection", "high", 120),
        ("Minichamps", "Ferrari SF90 Leclerc 2019", "1:43", "F1 Collection", "mid", 80),
        ("Minichamps", "McLaren MP4/4 Senna 1988", "1:43", "F1 Collection", "grail", 200),
        ("Minichamps", "Williams FW14B Mansell 1992", "1:43", "F1 Collection", "high", 150),
        ("Minichamps", "Ferrari F2004 Schumacher 2004", "1:43", "F1 Collection", "high", 130),
        ("Minichamps", "Red Bull RB16B Verstappen 2021", "1:18", "F1 1:18 Collection", "grail", 300),
        ("Minichamps", "Mercedes W12 Hamilton Abu Dhabi 2021", "1:18", "F1 1:18 Collection", "grail", 280),

        # Greenlight Chase Variants
        ("Greenlight", "1967 Ford Mustang GT Fastback", "1:64", "Chase Green Machine", "mid", 40),
        ("Greenlight", "1970 Dodge Challenger R/T", "1:64", "Chase Green Machine", "mid", 45),
        ("Greenlight", "1969 Chevrolet Camaro Z/28", "1:64", "Chase Green Machine", "standard", 30),
        ("Greenlight", "Jeep Wrangler Rubicon", "1:64", "Chase Green Machine", "standard", 25),
        ("Greenlight", "1979 Pontiac Firebird Trans Am", "1:64", "Chase Green Machine", "mid", 50),
        ("Greenlight", "1971 Plymouth Hemi Cuda", "1:64", "Chase Green Machine", "mid", 55),
        ("Greenlight", "Ford Bronco (2021)", "1:64", "Chase Green Machine", "standard", 35),

        # AUTOart 1:18 Scale (additional)
        ("AUTOart", "BMW M3 (E30) Sport Evolution", "1:18", "Composite", "grail", 320),
        ("AUTOart", "Lamborghini Countach LP400", "1:18", "Composite", "grail", 360),
        ("AUTOart", "McLaren F1", "1:18", "Composite", "grail", 450),
        ("AUTOart", "Ferrari F40", "1:18", "Composite", "grail", 380),
        ("AUTOart", "Porsche 918 Spyder", "1:18", "Composite", "grail", 290),
        ("AUTOart", "Pagani Huayra", "1:18", "Composite", "grail", 340),

        # Kyosho 1:43 Scale (additional)
        ("Kyosho", "Honda NSX (NA1)", "1:43", "High-End", "mid", 55),
        ("Kyosho", "Lamborghini Miura P400 SV", "1:43", "High-End", "mid", 65),
        ("Kyosho", "Ferrari 250 GTO (1962)", "1:43", "High-End", "high", 130),
        ("Kyosho", "Shelby Cobra 427", "1:43", "High-End", "mid", 75),
        ("Kyosho", "Porsche 911 Carrera RS 2.7", "1:43", "High-End", "mid", 70),

        # Minichamps F1 Cars (additional)
        ("Minichamps", "McLaren MP4/4 Senna 1988 World Champion", "1:18", "F1 1:18 Collection", "grail", 350),
        ("Minichamps", "Ferrari F2004 Schumacher Belgian GP 2004", "1:18", "F1 1:18 Collection", "grail", 280),
        ("Minichamps", "Mercedes W11 Hamilton Turkish GP 2020", "1:18", "F1 1:18 Collection", "grail", 260),
        ("Minichamps", "Red Bull RB16B Verstappen Abu Dhabi 2021", "1:43", "F1 Collection", "high", 140),
        ("Minichamps", "McLaren MP4/2C Prost 1986", "1:43", "F1 Collection", "high", 160),

        # Tomica Limited Vintage
        ("Tomica LV", "Nissan Skyline GT-R (R32) V-Spec", "1:64", "Limited Vintage Neo", "high", 90),
        ("Tomica LV", "Toyota Sprinter Trueno (AE86)", "1:64", "Limited Vintage Neo", "high", 85),
        ("Tomica LV", "Mazda RX-7 (FD3S) Spirit R", "1:64", "Limited Vintage Neo", "mid", 75),
        ("Tomica LV", "Honda Civic Type R (EK9)", "1:64", "Limited Vintage Neo", "mid", 70),
        ("Tomica LV", "Mitsubishi Lancer Evolution VI TME", "1:64", "Limited Vintage Neo", "mid", 65),

        # M2 Machines
        ("M2 Machines", "1970 Nissan Fairlady Z (S30)", "1:64", "Auto-Japan Chase", "mid", 55),
        ("M2 Machines", "1969 Pontiac GTO Judge", "1:64", "Detroit Muscle Chase", "mid", 50),
        ("M2 Machines", "1957 Chevrolet Bel Air", "1:64", "Clearly Auto-Thentics", "mid", 45),
        ("M2 Machines", "1971 Plymouth Hemi Cuda", "1:64", "Auto-Drivers Chase", "mid", 60),

        # Johnny Lightning
        ("Johnny Lightning", "1970 Chevrolet Chevelle SS 454", "1:64", "White Lightning Chase", "mid", 65),
        ("Johnny Lightning", "1969 Ford Mustang Boss 429", "1:64", "White Lightning Chase", "mid", 60),
        ("Johnny Lightning", "1967 Chevrolet Corvette Stingray", "1:64", "Classic Gold", "standard", 25),

        # Spark 1:43 Scale
        ("Spark", "Porsche 917K Le Mans Winner 1971", "1:43", "Le Mans Collection", "high", 110),
        ("Spark", "Ford GT40 Mk II Le Mans Winner 1966", "1:43", "Le Mans Collection", "high", 120),
        ("Spark", "Toyota TS050 Le Mans Winner 2020", "1:43", "Le Mans Collection", "mid", 85),
        ("Spark", "Mercedes W196 Fangio 1954", "1:43", "F1 Collection", "grail", 220),

        # Tarmac Works 1:64 Scale
        ("Tarmac Works", "Nissan Skyline GT-R (R34) V-Spec II", "1:64", "Global64", "mid", 40),
        ("Tarmac Works", "Honda NSX GT3 Evo", "1:64", "Hobby64", "standard", 30),
        ("Tarmac Works", "Toyota GR Supra Racing Concept", "1:64", "Global64", "standard", 28),

        # === NEW ITEMS (35 additions below) ===

        # Spark 1:43 F1 Race Winners
        ("Spark", "Red Bull RB19 Verstappen Winner Bahrain GP 2023", "1:43", "F1 Collection", "high", 100),
        ("Spark", "Red Bull RB19 Verstappen Winner Miami GP 2023", "1:43", "F1 Collection", "high", 95),
        ("Spark", "Red Bull RB20 Verstappen Winner Bahrain GP 2024", "1:43", "F1 Collection", "high", 105),
        ("Spark", "McLaren MCL60 Norris Winner Miami GP 2023", "1:43", "F1 Collection", "high", 110),
        ("Spark", "Ferrari SF-23 Leclerc Winner Monaco GP 2024", "1:43", "F1 Collection", "high", 115),

        # BBR 1:18 Ferrari Limited Editions
        ("BBR", "Ferrari LaFerrari Rosso Corsa", "1:18", "BBR Limited Edition", "grail", 450),
        ("BBR", "Ferrari 296 GTB Assetto Fiorano", "1:18", "BBR Limited Edition", "grail", 380),
        ("BBR", "Ferrari SF90 Stradale Giallo Modena", "1:18", "BBR Limited Edition", "grail", 400),

        # Almost Real 1:18
        ("Almost Real", "Land Rover Defender 110 Heritage Edition", "1:18", "Premium", "high", 180),
        ("Almost Real", "Mercedes-AMG GT Black Series", "1:18", "Premium", "high", 200),

        # TSM TrueScale 1:43
        ("TSM", "McLaren 720S Spider Belize Blue", "1:43", "TrueScale", "mid", 75),
        ("TSM", "Porsche 911 (992) GT3 Shark Blue", "1:43", "TrueScale", "mid", 70),
        ("TSM", "McLaren Artura Flux Green", "1:43", "TrueScale", "mid", 65),

        # Ignition Model 1:18 Japanese Cars
        ("Ignition Model", "Nissan Skyline GT-R (R32) V-Spec II Bayside Blue", "1:18", "IG Limited", "grail", 350),
        ("Ignition Model", "Nissan Skyline GT-R (R34) V-Spec II Nur Millennium Jade", "1:18", "IG Limited", "grail", 400),
        ("Ignition Model", "Mazda RX-7 (FD3S) Spirit R Type A", "1:18", "IG Limited", "grail", 320),
        ("Ignition Model", "Toyota Supra (A80) RZ Twin Turbo", "1:18", "IG Limited", "grail", 340),

        # INNO64 1:64
        ("INNO64", "Honda Civic Type R (EK9) Championship White", "1:64", "IN64 Collection", "mid", 35),
        ("INNO64", "Nissan Skyline GT-R (R34) V-Spec II Bayside Blue", "1:64", "IN64 Collection", "mid", 40),
        ("INNO64", "Honda Civic Si (EF9) No Good Racing", "1:64", "IN64 Collection", "standard", 30),

        # Mini GT 1:64
        ("Mini GT", "Bugatti Chiron Sport Blue Royal", "1:64", "MGT Collection", "standard", 18),
        ("Mini GT", "Lamborghini Sian FKP 37 Green", "1:64", "MGT Collection", "standard", 20),
        ("Mini GT", "Porsche 911 (992) GT3 Shark Blue", "1:64", "MGT Collection", "standard", 16),
        ("Mini GT", "Mercedes-AMG GT Black Series Red", "1:64", "MGT Collection", "standard", 18),

        # Vintage Dinky Toys 1950s-60s
        ("Dinky Toys", "Foden 14-Ton Tanker (No. 504)", "1:43", "Vintage 1950s", "grail", 300),
        ("Dinky Toys", "Leyland Octopus Flat Truck (No. 934)", "1:43", "Vintage 1950s", "high", 180),
        ("Dinky Toys", "Guy Warrior 4-Ton Lorry (No. 431)", "1:43", "Vintage 1960s", "high", 150),

        # Vintage Corgi
        ("Corgi", "James Bond Aston Martin DB5 (No. 261)", "1:43", "Vintage 1965", "grail", 350),
        ("Corgi", "Batmobile 1st Issue (No. 267)", "1:43", "Vintage 1966", "grail", 400),
        ("Corgi", "Chitty Chitty Bang Bang (No. 266)", "1:43", "Vintage 1968", "grail", 280),

        # More Tarmac Works 1:64 Racing Liveries
        ("Tarmac Works", "Mercedes-AMG GT3 Macau GT Cup 2023", "1:64", "Hobby64", "mid", 38),
        ("Tarmac Works", "Porsche 911 GT3 R Spa 24h 2023", "1:64", "Hobby64", "mid", 42),
        ("Tarmac Works", "BMW M4 GT3 Nurburgring 24h 2023", "1:64", "Hobby64", "mid", 36),
        ("Tarmac Works", "Toyota GR86 D1 Grand Prix Drift", "1:64", "Global64", "standard", 30),

        # === ROUND 3 — 20 new items ===

        # Schuco 1:43 European Classics
        ("Schuco", "Porsche 356A Speedster Silver", "1:43", "Pro.R43", "mid", 75),
        ("Schuco", "VW Beetle Ovali 1955 Green", "1:43", "Pro.R43", "mid", 65),
        ("Schuco", "Mercedes-Benz 300 SL Gullwing", "1:43", "Pro.R43", "high", 85),

        # GT Spirit 1:18 Resin
        ("GT Spirit", "Nissan Skyline GT-R (R34) Z-Tune Midnight Purple", "1:18", "GT Spirit Asia Exclusive", "grail", 280),
        ("GT Spirit", "Porsche 911 (964) RWB Rauh-Welt", "1:18", "GT Spirit Limited", "high", 180),
        ("GT Spirit", "BMW M3 (E46) CSL Silver Grey", "1:18", "GT Spirit Limited", "high", 160),

        # Bburago Signature 1:18
        ("Bburago", "Ferrari Monza SP1 Rosso Corsa", "1:18", "Signature Series", "mid", 55),
        ("Bburago", "Lamborghini Centenario Giallo Orion", "1:18", "Signature Series", "mid", 50),

        # Hot Wheels RLC (more exclusives)
        ("Hot Wheels RLC", "Custom Corvette Stingray (Spectraflame)", "1:64", "RLC Exclusive 2024", "high", 135),
        ("Hot Wheels RLC", "'70 Dodge Hemi Challenger", "1:64", "RLC Exclusive", "grail", 190),

        # Tomica LV (additional)
        ("Tomica LV", "Nissan Silvia (S13) K's", "1:64", "Limited Vintage Neo", "mid", 60),
        ("Tomica LV", "Toyota Crown Comfort Taxi", "1:64", "Limited Vintage Neo", "standard", 35),

        # Vintage Solido (French diecast)
        ("Solido", "Alpine A110 1600S Rally", "1:43", "Vintage 1970s", "high", 95),
        ("Solido", "Citroen DS 21 Pallas", "1:43", "Vintage 1960s", "mid", 70),

        # JADA Toys Import Racer
        ("JADA", "Nissan Skyline GT-R (R34) Fast & Furious", "1:24", "Hollywood Rides", "mid", 40),
        ("JADA", "Mazda RX-7 (FD) Fast & Furious", "1:24", "Hollywood Rides", "mid", 38),

        # Maisto Premium 1:18
        ("Maisto", "Ford GT Heritage Edition Gulf Livery", "1:18", "Special Edition", "mid", 45),
        ("Maisto", "Bugatti Divo Matte Grey", "1:18", "Special Edition", "mid", 42),

        # Norev 1:18 Official Dealer
        ("Norev", "Mercedes-Benz 300 SL (W198) Silver", "1:18", "Dealer Edition", "high", 110),
        ("Norev", "Porsche 911 (992) Turbo S Python Green", "1:18", "Dealer Edition", "high", 100),

        # === ROUND 4 — 63 new items to reach 205+ ===

        # Hot Wheels RLC — More Recent Exclusives
        ("Hot Wheels RLC", "'73 BMW 3.0 CSL Race Car", "1:64", "RLC Exclusive 2024", "high", 125),
        ("Hot Wheels RLC", "'82 Toyota Supra (A60)", "1:64", "RLC Exclusive", "high", 115),
        ("Hot Wheels RLC", "Porsche 959", "1:64", "RLC Exclusive 2024", "grail", 210),
        ("Hot Wheels RLC", "'67 Camaro SS", "1:64", "RLC Exclusive", "high", 105),

        # Hot Wheels Super Treasure Hunts — More Recent
        ("Hot Wheels $TH", "Ford Mustang Shelby GT500", "1:64", "Super Treasure Hunt 2024", "mid", 55),
        ("Hot Wheels $TH", "Lamborghini Huracan STO", "1:64", "Super Treasure Hunt 2024", "mid", 60),
        ("Hot Wheels $TH", "'95 Mazda RX-7 (FD)", "1:64", "Super Treasure Hunt 2024", "mid", 70),
        ("Hot Wheels $TH", "Nissan Z (Z34)", "1:64", "Super Treasure Hunt 2023", "mid", 50),

        # AUTOart 1:18 — Modern Supercars
        ("AUTOart", "Porsche 911 (992) GT3 RS", "1:18", "Composite", "grail", 380),
        ("AUTOart", "Lexus LFA Whitest White", "1:18", "Composite", "grail", 420),
        ("AUTOart", "Lamborghini Huracan Performante", "1:18", "Composite", "grail", 310),
        ("AUTOart", "Honda NSX (NC1)", "1:18", "Composite", "high", 250),
        ("AUTOart", "Aston Martin Vantage", "1:18", "Composite", "high", 220),

        # Kyosho 1:43 — Additional JDM & Exotics
        ("Kyosho", "Mazda RX-7 (FD3S) Spirit R", "1:43", "High-End", "mid", 60),
        ("Kyosho", "Nissan Fairlady Z (S30) 432", "1:43", "High-End", "mid", 55),
        ("Kyosho", "Toyota Celica GT-Four (ST205)", "1:43", "High-End", "mid", 50),
        ("Kyosho", "Honda S2000 (AP1)", "1:43", "High-End", "mid", 48),
        ("Kyosho", "Lamborghini Countach LP500S", "1:43", "High-End", "mid", 70),

        # Minichamps F1 — More Historic Cars
        ("Minichamps", "Lotus 79 Andretti 1978", "1:43", "F1 Collection", "high", 140),
        ("Minichamps", "Tyrrell P34 Scheckter 1976", "1:43", "F1 Collection", "high", 160),
        ("Minichamps", "Brabham BT52 Piquet 1983", "1:43", "F1 Collection", "high", 150),
        ("Minichamps", "McLaren MCL60 Norris Australian GP 2023", "1:43", "F1 Collection", "mid", 90),
        ("Minichamps", "Aston Martin AMR23 Alonso Bahrain GP 2023", "1:43", "F1 Collection", "mid", 85),

        # Spark F1/Le Mans — Additional
        ("Spark", "McLaren MCL38 Norris Winner Miami GP 2024", "1:43", "F1 Collection", "high", 115),
        ("Spark", "Ferrari 499P Le Mans Winner 2023", "1:43", "Le Mans Collection", "high", 130),
        ("Spark", "Toyota GR010 Le Mans Winner 2021", "1:43", "Le Mans Collection", "high", 100),
        ("Spark", "Audi R18 Le Mans Winner 2014", "1:43", "Le Mans Collection", "mid", 90),
        ("Spark", "Porsche 963 Le Mans 2023", "1:43", "Le Mans Collection", "mid", 85),

        # Tomica LV — More JDM Legends
        ("Tomica LV", "Nissan Fairlady Z (S30) 432", "1:64", "Limited Vintage Neo", "mid", 70),
        ("Tomica LV", "Toyota AE86 Sprinter Trueno GT-APEX", "1:64", "Limited Vintage Neo", "high", 90),
        ("Tomica LV", "Honda NSX Type R (NA2)", "1:64", "Limited Vintage Neo", "high", 85),
        ("Tomica LV", "Mazda Cosmo Sport L10B", "1:64", "Limited Vintage Neo", "mid", 75),
        ("Tomica LV", "Subaru Impreza WRX STI (GC8)", "1:64", "Limited Vintage Neo", "mid", 65),

        # Tarmac Works 1:64 — Rally & Drift
        ("Tarmac Works", "Subaru Impreza WRC 1997 Monte Carlo Rally", "1:64", "Global64", "mid", 38),
        ("Tarmac Works", "Mitsubishi Lancer Evo VI TME Tommi Makinen Edition", "1:64", "Global64", "mid", 42),
        ("Tarmac Works", "Toyota GR Yaris Rallye Monte-Carlo 2024", "1:64", "Hobby64", "mid", 36),

        # INNO64 — More JDM Tuners
        ("INNO64", "Toyota Sprinter Trueno (AE86) Initial D", "1:64", "IN64 Collection", "mid", 45),
        ("INNO64", "Mitsubishi Lancer Evo III GSR", "1:64", "IN64 Collection", "mid", 38),
        ("INNO64", "Honda Integra Type R (DC2)", "1:64", "IN64 Collection", "standard", 30),

        # Mini GT 1:64 — More Variety
        ("Mini GT", "Nissan Skyline GT-R (R34) V-Spec II Bayside Blue", "1:64", "MGT Collection", "standard", 22),
        ("Mini GT", "Toyota GR Supra Heritage Edition", "1:64", "MGT Collection", "standard", 18),
        ("Mini GT", "Ford GT MK II Shadow Black", "1:64", "MGT Collection", "standard", 18),
        ("Mini GT", "Pagani Zonda F Geneva Edition", "1:64", "MGT Collection", "standard", 20),

        # Vintage Matchbox — More Lesney Era
        ("Matchbox", "No. 14 Daimler Ambulance", "1:64", "Lesney Vintage 1956", "mid", 55),
        ("Matchbox", "No. 32 Jaguar XK140", "1:64", "Lesney Vintage 1957", "mid", 60),
        ("Matchbox", "No. 73 Ferrari Racing Car", "1:64", "Lesney Vintage 1962", "high", 80),

        # CMC 1:18 — Ultra-Premium
        ("CMC", "Mercedes-Benz 300 SLR Mille Miglia 1955", "1:18", "CMC Limited", "grail", 550),
        ("CMC", "Ferrari 250 GTO 1962", "1:18", "CMC Limited", "grail", 600),
        ("CMC", "Maserati 300S Dirty Hero 1956", "1:18", "CMC Limited", "grail", 480),

        # Looksmart 1:43 Ferrari Limited
        ("Looksmart", "Ferrari SF-24 Leclerc Monza 2024", "1:43", "Looksmart Limited", "high", 110),
        ("Looksmart", "Ferrari 296 GT3 Le Mans 2024", "1:43", "Looksmart Limited", "high", 100),

        # Greenlight — Hollywood/TV Tie-ins
        ("Greenlight", "1969 Dodge Charger R/T The Dukes of Hazzard", "1:64", "Hollywood Series", "mid", 45),
        ("Greenlight", "1977 Pontiac Trans Am Smokey and the Bandit", "1:64", "Hollywood Series", "mid", 40),
        ("Greenlight", "2013 Ford Mustang Boss 302 Need for Speed", "1:64", "Hollywood Series", "standard", 28),

        # M2 Machines — Haulers & Sets
        ("M2 Machines", "1966 Ford C-950 Hauler + 1966 Mustang GT", "1:64", "Auto-Haulers Chase", "mid", 65),
        ("M2 Machines", "1970 Dodge Challenger T/A", "1:64", "Detroit Muscle Chase", "mid", 55),

        # Johnny Lightning — More White Lightning Chase
        ("Johnny Lightning", "1971 AMC Javelin AMX", "1:64", "White Lightning Chase", "mid", 55),
        ("Johnny Lightning", "1968 Dodge Charger R/T", "1:64", "White Lightning Chase", "mid", 60),
        ("Johnny Lightning", "1970 Plymouth Superbird", "1:64", "Classic Gold", "standard", 28),

        # Welly / Bburago Budget Collectibles
        ("Bburago", "Ferrari SF90 Spider", "1:18", "Signature Series", "mid", 48),
        ("Bburago", "Porsche 911 GT3 (992)", "1:18", "Race Series", "mid", 45),

        # Schuco — More European
        ("Schuco", "BMW Isetta Export", "1:43", "Pro.R43", "mid", 55),
        ("Schuco", "Porsche 911 (964) Turbo Black", "1:43", "Pro.R43", "mid", 70),

        # === ROUND 5 — 300+ new items to reach 500+ total ===

        # Hot Wheels RLC — More Exclusives
        ("Hot Wheels RLC", "'71 Plymouth GTX", "1:64", "RLC Exclusive 2024", "high", 120),
        ("Hot Wheels RLC", "'68 Mercury Cougar", "1:64", "RLC Exclusive", "high", 115),
        ("Hot Wheels RLC", "BMW 507", "1:64", "RLC Exclusive 2023", "high", 130),
        ("Hot Wheels RLC", "Datsun 240Z", "1:64", "RLC Exclusive", "high", 125),
        ("Hot Wheels RLC", "'66 Chevy Super Nova", "1:64", "RLC Exclusive 2024", "grail", 195),
        ("Hot Wheels RLC", "Porsche 964 Carrera 2", "1:64", "RLC Exclusive", "high", 140),
        ("Hot Wheels RLC", "'69 Mustang Boss 302", "1:64", "RLC Exclusive", "high", 135),
        ("Hot Wheels RLC", "Toyota Land Cruiser FJ40", "1:64", "RLC Exclusive 2023", "high", 110),

        # Hot Wheels Super Treasure Hunts — More Years
        ("Hot Wheels $TH", "Honda Civic Type R (FK8)", "1:64", "Super Treasure Hunt 2023", "mid", 55),
        ("Hot Wheels $TH", "Dodge Viper SRT10 ACR", "1:64", "Super Treasure Hunt", "mid", 50),
        ("Hot Wheels $TH", "Corvette C8.R", "1:64", "Super Treasure Hunt 2023", "mid", 60),
        ("Hot Wheels $TH", "'71 AMC Javelin", "1:64", "Super Treasure Hunt", "mid", 45),
        ("Hot Wheels $TH", "Porsche 918 Spyder", "1:64", "Super Treasure Hunt 2022", "mid", 55),
        ("Hot Wheels $TH", "BMW M4 GTS", "1:64", "Super Treasure Hunt 2024", "mid", 65),
        ("Hot Wheels $TH", "Aston Martin Vulcan", "1:64", "Super Treasure Hunt", "mid", 50),
        ("Hot Wheels $TH", "'55 Chevy Bel Air Gasser", "1:64", "Super Treasure Hunt 2023", "mid", 60),
        ("Hot Wheels $TH", "Subaru WRX STI", "1:64", "Super Treasure Hunt 2024", "mid", 55),
        ("Hot Wheels $TH", "Toyota GR Supra", "1:64", "Super Treasure Hunt 2024", "mid", 48),

        # Hot Wheels Premium — Team Transport & Car Culture
        ("Hot Wheels Premium", "Nissan Skyline GT-R (BNR34) Team Transport", "1:64", "Team Transport", "mid", 35),
        ("Hot Wheels Premium", "Porsche 962 Gulf Livery", "1:64", "Car Culture", "mid", 30),
        ("Hot Wheels Premium", "'73 BMW 3.0 CSL Race Car", "1:64", "Car Culture", "standard", 25),
        ("Hot Wheels Premium", "Toyota AE86 Sprinter Trueno Tofu Delivery", "1:64", "Car Culture", "mid", 32),
        ("Hot Wheels Premium", "Lancia 037 Rally Martini", "1:64", "Car Culture", "standard", 28),
        ("Hot Wheels Premium", "Audi Sport Quattro S1 E2", "1:64", "Car Culture", "standard", 25),

        # Matchbox — More Vintage Lesney & Superfast
        ("Matchbox", "No. 19 Aston Martin Racing Car", "1:64", "Lesney Vintage 1961", "high", 90),
        ("Matchbox", "No. 52 Maserati 4CLT Racer", "1:64", "Lesney Vintage 1958", "high", 85),
        ("Matchbox", "No. 66 Harley-Davidson Sidecar", "1:64", "Lesney Vintage 1962", "mid", 70),
        ("Matchbox", "Superfast No. 4 Gruesome Twosome", "1:64", "Superfast 1971", "mid", 55),
        ("Matchbox", "Superfast No. 8 Ford Mustang (Wildcat Dragster)", "1:64", "Superfast 1970", "mid", 60),
        ("Matchbox", "Superfast No. 34 Vantastic", "1:64", "Superfast 1975", "mid", 45),
        ("Matchbox", "No. 9 Merryweather Marquis Fire Engine", "1:64", "Lesney Vintage 1959", "high", 80),

        # AUTOart 1:18 — JDM Legends
        ("AUTOart", "Toyota Sprinter Trueno (AE86) Initial D", "1:18", "Composite", "grail", 340),
        ("AUTOart", "Nissan Skyline GT-R (R32) V-Spec II", "1:18", "Composite", "grail", 320),
        ("AUTOart", "Mazda RX-7 (FD3S) Spirit R", "1:18", "Composite", "grail", 300),
        ("AUTOart", "Honda S2000 (AP1)", "1:18", "Composite", "high", 250),
        ("AUTOart", "Subaru Impreza WRX STI 22B", "1:18", "Composite", "grail", 380),
        ("AUTOart", "Nissan Fairlady Z (S30) Wangan Midnight Devil Z", "1:18", "Composite", "grail", 350),

        # AUTOart 1:18 — European Sports
        ("AUTOart", "Lamborghini Diablo SE30", "1:18", "Composite", "grail", 320),
        ("AUTOart", "Porsche 911 (964) Carrera RS 3.6", "1:18", "Composite", "grail", 340),
        ("AUTOart", "Mercedes-Benz 190E 2.5-16 Evo II", "1:18", "Composite", "grail", 360),
        ("AUTOart", "Jaguar E-Type Lightweight", "1:18", "Composite", "grail", 380),
        ("AUTOart", "Aston Martin DB5 James Bond", "1:18", "Composite", "grail", 320),

        # Kyosho 1:43 — More Models
        ("Kyosho", "Toyota Celica GT-Four (ST185) Safari Rally", "1:43", "High-End", "mid", 60),
        ("Kyosho", "Nissan R390 GT1 Le Mans 1998", "1:43", "High-End", "mid", 65),
        ("Kyosho", "Lamborghini Aventador LP700-4", "1:43", "High-End", "mid", 55),
        ("Kyosho", "Ferrari Dino 246 GT", "1:43", "High-End", "mid", 60),
        ("Kyosho", "BMW 2002 Turbo", "1:43", "High-End", "mid", 50),
        ("Kyosho", "Mazda Cosmo Sport L10B", "1:43", "High-End", "mid", 55),
        ("Kyosho", "Toyota 86 (ZN6)", "1:43", "High-End", "mid", 45),

        # Minichamps F1 — 1:43 Historic & Modern
        ("Minichamps", "Ferrari 312T Lauda 1975", "1:43", "F1 Collection", "high", 140),
        ("Minichamps", "McLaren M23 Hunt 1976", "1:43", "F1 Collection", "high", 150),
        ("Minichamps", "Williams FW11B Piquet 1987", "1:43", "F1 Collection", "high", 130),
        ("Minichamps", "Benetton B195 Schumacher 1995", "1:43", "F1 Collection", "high", 120),
        ("Minichamps", "Renault R25 Alonso 2005", "1:43", "F1 Collection", "high", 110),
        ("Minichamps", "Brawn BGP 001 Button 2009", "1:43", "F1 Collection", "high", 130),
        ("Minichamps", "Ferrari SF-24 Hamilton 2025 Test", "1:43", "F1 Collection", "high", 140),

        # Minichamps F1 — 1:18 Scale
        ("Minichamps", "McLaren MP4/5B Senna 1990", "1:18", "F1 1:18 Collection", "grail", 350),
        ("Minichamps", "Ferrari F310 Schumacher 1996", "1:18", "F1 1:18 Collection", "grail", 280),
        ("Minichamps", "Lotus 97T Senna 1985", "1:18", "F1 1:18 Collection", "grail", 400),
        ("Minichamps", "Williams FW14B Mansell 1992", "1:18", "F1 1:18 Collection", "grail", 320),

        # Spark — F1 Expanded
        ("Spark", "Williams FW43B Russell Spa 2021 P2", "1:43", "F1 Collection", "mid", 85),
        ("Spark", "Alpine A521 Ocon Hungary Winner 2021", "1:43", "F1 Collection", "high", 100),
        ("Spark", "AlphaTauri AT02 Gasly Monza Winner 2020", "1:43", "F1 Collection", "high", 110),
        ("Spark", "Mercedes W14 Hamilton British GP 2023", "1:43", "F1 Collection", "mid", 90),
        ("Spark", "Red Bull RB20 Verstappen Japanese GP 2024", "1:43", "F1 Collection", "high", 105),

        # Spark — Le Mans Expanded
        ("Spark", "Porsche 917 KH Salzburg 1970 Winner", "1:43", "Le Mans Collection", "grail", 200),
        ("Spark", "Jaguar XJR-9 Le Mans Winner 1988", "1:43", "Le Mans Collection", "high", 120),
        ("Spark", "Mazda 787B Le Mans Winner 1991", "1:43", "Le Mans Collection", "high", 150),
        ("Spark", "Bentley Speed 8 Le Mans Winner 2003", "1:43", "Le Mans Collection", "mid", 95),
        ("Spark", "Audi R8 Le Mans Winner 2005", "1:43", "Le Mans Collection", "mid", 90),
        ("Spark", "Ferrari 499P Le Mans Winner 2024", "1:43", "Le Mans Collection", "high", 140),
        ("Spark", "BMW V12 LMR Le Mans Winner 1999", "1:43", "Le Mans Collection", "high", 110),

        # Spark — Touring Cars & Rally
        ("Spark", "BMW M3 (E30) DTM 1992 Champion", "1:43", "DTM Collection", "mid", 85),
        ("Spark", "Alfa Romeo 155 V6 TI DTM 1993", "1:43", "DTM Collection", "mid", 80),
        ("Spark", "Lancia Delta Integrale Rally Monte Carlo 1992", "1:43", "Rally Collection", "mid", 85),
        ("Spark", "Subaru Impreza WRC Rally Monte Carlo 1997", "1:43", "Rally Collection", "mid", 80),

        # BBR — More Ferrari Limited Editions
        ("BBR", "Ferrari 250 GTO Rosso Corsa 1962", "1:18", "BBR Limited Edition", "grail", 600),
        ("BBR", "Ferrari F40 Rosso Corsa", "1:18", "BBR Limited Edition", "grail", 500),
        ("BBR", "Ferrari 488 Pista Spider Giallo Modena", "1:18", "BBR Limited Edition", "grail", 420),
        ("BBR", "Ferrari Monza SP2 Rosso Corsa", "1:18", "BBR Limited Edition", "grail", 450),
        ("BBR", "Ferrari Daytona SP3 Rosso Corsa", "1:18", "BBR Limited Edition", "grail", 480),

        # CMC — More Ultra-Premium
        ("CMC", "Mercedes-Benz SSK 1930", "1:18", "CMC Limited", "grail", 520),
        ("CMC", "Jaguar C-Type 1952 Le Mans", "1:18", "CMC Limited", "grail", 500),
        ("CMC", "Auto Union Type C 1936", "1:18", "CMC Limited", "grail", 550),
        ("CMC", "Bugatti Type 35 Grand Prix 1924", "1:18", "CMC Limited", "grail", 480),
        ("CMC", "Alfa Romeo 8C 2900B Speciale 1938", "1:18", "CMC Limited", "grail", 580),

        # Exoto — Ultra-Premium Racing
        ("Exoto", "Ford GT40 Mk II 1966 Le Mans 1st Place", "1:18", "Grand Prix Classics", "grail", 500),
        ("Exoto", "Porsche 917 Salzburg 1970 Le Mans", "1:18", "Grand Prix Classics", "grail", 480),
        ("Exoto", "Ferrari 312T Lauda 1975", "1:18", "Grand Prix Classics", "grail", 450),
        ("Exoto", "Lotus 72D Fittipaldi 1972", "1:18", "Grand Prix Classics", "grail", 420),

        # GMP / ACME — American Muscle 1:18
        ("GMP", "1970 Chevelle SS 454 LS6 Cranberry Red", "1:18", "Street Fighter", "grail", 300),
        ("GMP", "1969 Ford Mustang Boss 429 Candy Apple Red", "1:18", "Street Fighter", "grail", 320),
        ("GMP", "1967 Chevrolet Camaro SS/RS Bolero Red", "1:18", "Street Fighter", "high", 250),
        ("ACME", "1970 Dodge Challenger R/T Hemi Plum Crazy", "1:18", "ACME Exclusive", "grail", 280),
        ("ACME", "1969 Chevrolet Camaro ZL1 Daytona Yellow", "1:18", "ACME Exclusive", "grail", 300),
        ("ACME", "1971 Plymouth Hemi Cuda Tor-Red", "1:18", "ACME Exclusive", "grail", 320),
        ("ACME", "1970 Ford Torino Cobra Jet Calypso Coral", "1:18", "ACME Exclusive", "high", 250),

        # Tomica Limited Vintage Neo — More JDM
        ("Tomica LV", "Toyota Century (GZG50)", "1:64", "Limited Vintage Neo", "mid", 60),
        ("Tomica LV", "Nissan Cedric Gran Turismo Ultima", "1:64", "Limited Vintage Neo", "mid", 55),
        ("Tomica LV", "Honda Prelude Si VTEC (BB4)", "1:64", "Limited Vintage Neo", "mid", 50),
        ("Tomica LV", "Mitsubishi GTO Twin Turbo MR", "1:64", "Limited Vintage Neo", "mid", 60),
        ("Tomica LV", "Toyota Chaser Tourer V (JZX100)", "1:64", "Limited Vintage Neo", "mid", 65),
        ("Tomica LV", "Nissan Leopard Ultima (F31)", "1:64", "Limited Vintage Neo", "mid", 55),
        ("Tomica LV", "Mazda Savanna RX-7 (FC3S)", "1:64", "Limited Vintage Neo", "mid", 60),
        ("Tomica LV", "Honda City Turbo II", "1:64", "Limited Vintage Neo", "mid", 70),

        # Tomica Premium — Modern
        ("Tomica", "GT-R (R35) 2024 Nismo", "1:64", "Premium", "standard", 15),
        ("Tomica", "Toyota GR86", "1:64", "Premium", "standard", 12),
        ("Tomica", "Honda Civic Type R (FL5)", "1:64", "Premium", "standard", 14),
        ("Tomica", "Ferrari SF90 Stradale", "1:64", "Premium", "standard", 15),
        ("Tomica", "Lamborghini Sian FKP 37", "1:64", "Premium", "standard", 14),

        # Tarmac Works — More Racing
        ("Tarmac Works", "Audi R8 LMS GT3 Bathurst 12h", "1:64", "Hobby64", "mid", 38),
        ("Tarmac Works", "Ford Mustang GT3 IMSA 2024", "1:64", "Hobby64", "mid", 40),
        ("Tarmac Works", "Nissan GT-R Nismo GT3 Super GT", "1:64", "Hobby64", "mid", 36),
        ("Tarmac Works", "Honda Civic Type R FK8 TCR", "1:64", "Hobby64", "mid", 34),
        ("Tarmac Works", "Lancia 037 Rally Martini", "1:64", "Global64", "mid", 42),
        ("Tarmac Works", "Toyota GR Corolla Rally1 WRC", "1:64", "Global64", "mid", 38),

        # INNO64 — More Releases
        ("INNO64", "Nissan Silvia (S13) V1 Pandem Rocket Bunny", "1:64", "IN64 Collection", "mid", 38),
        ("INNO64", "Toyota Corolla AE86 Levin", "1:64", "IN64 Collection", "mid", 35),
        ("INNO64", "Mazda MX-5 Miata (NA) Classic Red", "1:64", "IN64 Collection", "standard", 28),
        ("INNO64", "Honda City Turbo II with Motocompo", "1:64", "IN64 Collection", "mid", 42),
        ("INNO64", "Mitsubishi Lancer Evo VI TME Red", "1:64", "IN64 Collection", "mid", 40),

        # Mini GT — Expanded Range
        ("Mini GT", "Porsche 911 (992) GT3 RS Weissach", "1:64", "MGT Collection", "standard", 22),
        ("Mini GT", "Toyota Land Cruiser GR Sport", "1:64", "MGT Collection", "standard", 18),
        ("Mini GT", "Lamborghini Countach LPI 800-4", "1:64", "MGT Collection", "standard", 20),
        ("Mini GT", "McLaren 720S GT3 Evo", "1:64", "MGT Collection", "standard", 18),
        ("Mini GT", "BMW M3 (E30) Alpine White", "1:64", "MGT Collection", "standard", 18),
        ("Mini GT", "Bentley Continental GT Speed", "1:64", "MGT Collection", "standard", 16),
        ("Mini GT", "Range Rover 1970 Tuscan Blue", "1:64", "MGT Collection", "standard", 18),

        # Ignition Model 1:18 — More JDM
        ("Ignition Model", "Honda NSX (NA1) Type R", "1:18", "IG Limited", "grail", 360),
        ("Ignition Model", "Mitsubishi Lancer Evolution VI TME", "1:18", "IG Limited", "grail", 340),
        ("Ignition Model", "Nissan Silvia (S15) Spec-R Aero", "1:18", "IG Limited", "grail", 300),
        ("Ignition Model", "Subaru Impreza 22B STI", "1:18", "IG Limited", "grail", 380),
        ("Ignition Model", "Toyota Supra (A70) 3.0 GT Turbo A", "1:18", "IG Limited", "grail", 320),

        # GT Spirit 1:18 — More Resin
        ("GT Spirit", "Ford Mustang Shelby GT500 2020 Oxford White", "1:18", "GT Spirit Limited", "high", 160),
        ("GT Spirit", "Dodge Challenger SRT Demon Plum Crazy", "1:18", "GT Spirit Limited", "high", 170),
        ("GT Spirit", "Toyota Supra (A80) TRD 3000GT", "1:18", "GT Spirit Asia Exclusive", "grail", 260),
        ("GT Spirit", "Lamborghini Diablo GTR Orange", "1:18", "GT Spirit Limited", "high", 180),
        ("GT Spirit", "Mercedes-AMG G63 4x4 Squared", "1:18", "GT Spirit Limited", "high", 170),

        # Almost Real 1:18 — More
        ("Almost Real", "Porsche 911 (964) Singer DLS Oak Green", "1:18", "Premium", "grail", 250),
        ("Almost Real", "RUF CTR Yellowbird 1987", "1:18", "Premium", "high", 200),
        ("Almost Real", "Land Rover Range Rover Classic 1970", "1:18", "Premium", "high", 180),
        ("Almost Real", "Mercedes-Benz G-Class (W463) 2018", "1:18", "Premium", "high", 170),

        # TSM TrueScale 1:43 — More
        ("TSM", "Ford GT40 Mk I Gulf Blue 1969", "1:43", "TrueScale", "mid", 80),
        ("TSM", "Porsche 935/78 Moby Dick 1978", "1:43", "TrueScale", "mid", 75),
        ("TSM", "Honda RA272 Mexico GP 1965 Winner", "1:43", "TrueScale", "mid", 70),
        ("TSM", "Aston Martin Valkyrie AMR Pro", "1:43", "TrueScale", "mid", 75),

        # Vintage Solido — More
        ("Solido", "Porsche 911 (930) Turbo Ivory", "1:43", "Vintage 1970s", "mid", 80),
        ("Solido", "Renault 5 Turbo Rally Blue", "1:43", "Vintage 1980s", "mid", 70),
        ("Solido", "Peugeot 205 T16 Rally White", "1:43", "Vintage 1980s", "mid", 75),

        # Vintage Corgi — More
        ("Corgi", "Lotus Esprit S1 James Bond (No. 269)", "1:43", "Vintage 1977", "grail", 300),
        ("Corgi", "Ford Mustang Mach 1 (No. 391)", "1:43", "Vintage 1972", "high", 180),
        ("Corgi", "Citroen 2CV James Bond (No. 272)", "1:43", "Vintage 1981", "high", 200),

        # Vintage Dinky Toys — More
        ("Dinky Toys", "Rolls-Royce Silver Cloud III (No. 127)", "1:43", "Vintage 1960s", "high", 160),
        ("Dinky Toys", "Jaguar E-Type 2+2 (No. 131)", "1:43", "Vintage 1960s", "high", 170),
        ("Dinky Toys", "Ferrari Dino 246 (No. 216)", "1:43", "Vintage 1960s", "high", 150),
        ("Dinky Toys", "Citroen DS 19 (No. 530)", "1:43", "Vintage 1960s", "high", 140),

        # Schuco — More European
        ("Schuco", "Alfa Romeo GTA 1300 Junior", "1:43", "Pro.R43", "mid", 60),
        ("Schuco", "Opel GT 1900", "1:43", "Pro.R43", "mid", 55),
        ("Schuco", "Porsche 917K Gulf 1970", "1:43", "Pro.R43", "high", 85),
        ("Schuco", "VW T1 Samba Bus", "1:43", "Pro.R43", "mid", 70),

        # Norev 1:18 — More Dealer Editions
        ("Norev", "BMW M3 (E30) Alpine White", "1:18", "Dealer Edition", "high", 100),
        ("Norev", "Renault 5 Turbo 1 Blue", "1:18", "Dealer Edition", "high", 110),
        ("Norev", "Citroen DS 21 Pallas 1967 Chapron", "1:18", "Dealer Edition", "high", 120),
        ("Norev", "Peugeot 205 GTI 1.9 Red", "1:18", "Dealer Edition", "mid", 90),
        ("Norev", "Volkswagen Golf GTI (Mk1) 1976", "1:18", "Dealer Edition", "mid", 85),

        # Bburago — More Budget Models
        ("Bburago", "Lamborghini Aventador SVJ Yellow", "1:18", "Race Series", "mid", 45),
        ("Bburago", "Ferrari 488 GTB Rosso Corsa", "1:18", "Race Series", "mid", 42),
        ("Bburago", "Porsche 911 GT3 RS (991) Orange", "1:18", "Race Series", "mid", 40),
        ("Bburago", "Bugatti Bolide Blue", "1:18", "Race Series", "mid", 48),

        # JADA Toys — More Hollywood Rides
        ("JADA", "Toyota Supra (A80) Fast & Furious Orange", "1:24", "Hollywood Rides", "mid", 42),
        ("JADA", "1970 Dodge Charger R/T Fast & Furious", "1:24", "Hollywood Rides", "mid", 40),
        ("JADA", "Batmobile 1989 Tim Burton", "1:24", "Hollywood Rides", "mid", 45),
        ("JADA", "DeLorean Time Machine Back to the Future", "1:24", "Hollywood Rides", "mid", 42),
        ("JADA", "1967 Shelby GT500 Eleanor Gone in 60 Seconds", "1:24", "Hollywood Rides", "mid", 45),

        # Maisto 1:18 — More
        ("Maisto", "Porsche 911 Carrera S (992) Black", "1:18", "Special Edition", "mid", 40),
        ("Maisto", "Lamborghini Centenario Anthracite", "1:18", "Special Edition", "mid", 42),
        ("Maisto", "Mercedes-AMG GT Black Series", "1:18", "Special Edition", "mid", 45),
        ("Maisto", "Chevrolet Corvette C8 Stingray 2020 Yellow", "1:18", "Special Edition", "mid", 38),

        # Welly 1:18 & 1:24
        ("Welly", "Porsche 356A Speedster Silver", "1:18", "NEX Models", "mid", 40),
        ("Welly", "DeLorean DMC-12 Back to the Future", "1:24", "NEX Models", "standard", 25),
        ("Welly", "Volkswagen T2 Bus Peace and Love", "1:24", "NEX Models", "standard", 22),

        # Looksmart — More Ferrari
        ("Looksmart", "Ferrari F40 Giallo Modena", "1:43", "Looksmart Limited", "high", 120),
        ("Looksmart", "Ferrari 250 GT SWB Berlinetta", "1:43", "Looksmart Limited", "high", 130),
        ("Looksmart", "Ferrari 812 Competizione Rosso Corsa", "1:43", "Looksmart Limited", "high", 105),

        # M2 Machines — More
        ("M2 Machines", "1967 Chevrolet Nova SS", "1:64", "Detroit Muscle Chase", "mid", 50),
        ("M2 Machines", "1965 Ford Econoline Delivery Van", "1:64", "Auto-Trucks Chase", "mid", 45),
        ("M2 Machines", "1970 Datsun 510", "1:64", "Auto-Japan Chase", "mid", 55),
        ("M2 Machines", "1973 Chevrolet K5 Blazer", "1:64", "Auto-Trucks Chase", "mid", 48),

        # Johnny Lightning — More
        ("Johnny Lightning", "1966 Chevrolet Nova SS", "1:64", "White Lightning Chase", "mid", 55),
        ("Johnny Lightning", "1977 Chevrolet Camaro Z/28", "1:64", "Classic Gold", "standard", 25),
        ("Johnny Lightning", "1972 Ford Pinto Runabout", "1:64", "Classic Gold", "standard", 22),
        ("Johnny Lightning", "1965 Pontiac GTO", "1:64", "White Lightning Chase", "mid", 60),

        # Siku — German Diecast
        ("Siku", "Liebherr Hydraulic Excavator R9800", "1:87", "Super Series", "standard", 18),
        ("Siku", "Scania R620 Topline Truck with Trailer", "1:87", "Super Series", "standard", 22),
        ("Siku", "Porsche 911 Turbo S", "1:55", "Super Series", "standard", 12),

        # Motorart — Construction Equipment
        ("Motorart", "Volvo EC220E Excavator", "1:50", "Construction", "mid", 65),
        ("Motorart", "Volvo A40G Articulated Hauler", "1:50", "Construction", "mid", 70),
        ("Diecast Masters", "CAT D11 Track-Type Tractor", "1:50", "Construction", "high", 120),
        ("Diecast Masters", "CAT 390F L Hydraulic Excavator", "1:50", "Construction", "high", 110),
        ("Diecast Masters", "CAT 745 Articulated Truck", "1:50", "Construction", "mid", 85),

        # Greenlight — More Chase & Hollywood
        ("Greenlight", "1972 Chevrolet C-10 Pickup", "1:64", "Chase Green Machine", "standard", 30),
        ("Greenlight", "2018 Dodge Durango SRT Pursuit", "1:64", "Chase Green Machine", "standard", 28),
        ("Greenlight", "1986 Chevrolet Monte Carlo SS Breaking Bad", "1:64", "Hollywood Series", "mid", 40),
        ("Greenlight", "2011 Dodge Charger R/T Drive", "1:64", "Hollywood Series", "standard", 30),
        ("Greenlight", "1974 Dodge Monaco Bluesmobile Blues Brothers", "1:64", "Hollywood Series", "mid", 42),

        # === ROUND 6 — 95+ new items to reach 500+ total ===

        # Hot Wheels RLC — Convention & sELECTIONs
        ("Hot Wheels RLC", "'55 Gasser Candy Striper", "1:64", "RLC sELECTIONs", "grail", 250),
        ("Hot Wheels RLC", "Nissan Laurel 2000SGX", "1:64", "RLC Exclusive 2024", "high", 130),
        ("Hot Wheels RLC", "'70 Chevy Blazer", "1:64", "RLC Exclusive", "high", 115),
        ("Hot Wheels RLC", "Datsun Bluebird 510 Wagon", "1:64", "RLC Exclusive", "high", 125),

        # Hot Wheels Convention Exclusives
        ("Hot Wheels", "'66 Super Nova (LA Convention 2024)", "1:64", "Convention Exclusive", "grail", 300),
        ("Hot Wheels", "'55 Chevy Panel (Japan Convention 2023)", "1:64", "Convention Exclusive", "grail", 280),
        ("Hot Wheels", "Volkswagen Drag Truck (Mexico Convention)", "1:64", "Convention Exclusive", "grail", 250),
        ("Hot Wheels", "Custom '72 Datsun 240Z (Nationals 2024)", "1:64", "Convention Exclusive", "grail", 320),

        # Hot Wheels $TH — Additional Years
        ("Hot Wheels $TH", "Ferrari 250 GTO", "1:64", "Super Treasure Hunt 2024", "high", 80),
        ("Hot Wheels $TH", "'71 De Tomaso Mangusta", "1:64", "Super Treasure Hunt 2023", "mid", 55),
        ("Hot Wheels $TH", "Pagani Huayra", "1:64", "Super Treasure Hunt", "mid", 50),
        ("Hot Wheels $TH", "'69 COPO Camaro", "1:64", "Super Treasure Hunt 2024", "mid", 65),

        # Hot Wheels Premium — Boulevard & Jay Leno's Garage
        ("Hot Wheels Premium", "McLaren F1 GTR Gulf", "1:64", "Boulevard", "mid", 35),
        ("Hot Wheels Premium", "Lamborghini Miura P400 SV", "1:64", "Boulevard", "standard", 28),
        ("Hot Wheels Premium", "Porsche 356 Outlaw", "1:64", "Jay Leno's Garage", "standard", 25),
        ("Hot Wheels Premium", "Mercedes-Benz 300 SL Gullwing", "1:64", "Boulevard", "standard", 28),

        # AUTOart 1:18 — Hypercars & Classic Supercars
        ("AUTOart", "McLaren Senna GTR", "1:18", "Composite", "grail", 380),
        ("AUTOart", "Ford GT40 Mk I Gulf", "1:18", "Composite", "grail", 400),
        ("AUTOart", "Lamborghini Veneno", "1:18", "Composite", "grail", 350),
        ("AUTOart", "Bugatti EB110 SS", "1:18", "Composite", "grail", 320),
        ("AUTOart", "Nissan Silvia (S15) Spec-R", "1:18", "Composite", "high", 260),

        # Kyosho 1:43 — Rally & Racing
        ("Kyosho", "Lancia Stratos HF Rally", "1:43", "High-End", "mid", 65),
        ("Kyosho", "Alpine A110 1600S", "1:43", "High-End", "mid", 60),
        ("Kyosho", "Nissan Skyline 2000 GT-R (KPGC110)", "1:43", "High-End", "mid", 55),
        ("Kyosho", "Toyota Sports 800 (UP15)", "1:43", "High-End", "mid", 50),

        # Minichamps F1 — More Iconic Cars
        ("Minichamps", "Red Bull RB20 Verstappen Dutch GP 2024", "1:43", "F1 Collection", "high", 110),
        ("Minichamps", "McLaren MCL38 Piastri Monza Winner 2024", "1:43", "F1 Collection", "high", 120),
        ("Minichamps", "Ferrari SF-24 Leclerc Dutch GP 2024", "1:43", "F1 Collection", "mid", 95),
        ("Minichamps", "Mercedes W15 Russell Belgian GP Winner 2024", "1:43", "F1 Collection", "high", 105),
        ("Minichamps", "Jordan 191 Schumacher Spa 1991", "1:43", "F1 Collection", "high", 140),
        ("Minichamps", "Toleman TG184 Senna Monaco 1984", "1:43", "F1 Collection", "high", 160),

        # Spark — WEC & GT Racing
        ("Spark", "Porsche 919 Hybrid Le Mans Winner 2017", "1:43", "Le Mans Collection", "high", 110),
        ("Spark", "Toyota GR010 Le Mans Winner 2022", "1:43", "Le Mans Collection", "high", 100),
        ("Spark", "McLaren F1 GTR Winner Le Mans 1995", "1:43", "Le Mans Collection", "grail", 200),
        ("Spark", "Ferrari 250 LM Le Mans Winner 1965", "1:43", "Le Mans Collection", "grail", 220),
        ("Spark", "Porsche 911 RSR Le Mans GTE Winner 2019", "1:43", "Le Mans Collection", "mid", 85),

        # Spark — IndyCar
        ("Spark", "Dallara DW12 Castroneves Indy 500 Winner 2021", "1:43", "IndyCar Collection", "high", 100),
        ("Spark", "Dallara IR18 Newgarden Indy 500 Winner 2023", "1:43", "IndyCar Collection", "high", 110),

        # Tomica Limited Vintage Neo — More JDM
        ("Tomica LV", "Nissan Gloria Gran Turismo Ultima", "1:64", "Limited Vintage Neo", "mid", 55),
        ("Tomica LV", "Toyota Soarer (Z30)", "1:64", "Limited Vintage Neo", "mid", 60),
        ("Tomica LV", "Nissan Silvia (S14) K's", "1:64", "Limited Vintage Neo", "mid", 55),
        ("Tomica LV", "Honda Beat (PP1)", "1:64", "Limited Vintage Neo", "mid", 65),
        ("Tomica LV", "Suzuki Cappuccino (EA11R)", "1:64", "Limited Vintage Neo", "mid", 60),
        ("Tomica LV", "Mazda Eunos Roadster (NA) V-Special", "1:64", "Limited Vintage Neo", "mid", 55),

        # Tarmac Works — More Releases
        ("Tarmac Works", "Porsche 911 (964) RWB Rauh-Welt", "1:64", "Global64", "mid", 42),
        ("Tarmac Works", "Mercedes-AMG GT3 Macau FIA GT Cup 2024", "1:64", "Hobby64", "mid", 38),
        ("Tarmac Works", "Lamborghini Huracan GT3 Evo2 Daytona 24h", "1:64", "Hobby64", "mid", 36),

        # INNO64 — More Releases
        ("INNO64", "Nissan Skyline GT-R (R33) V-Spec LM Limited", "1:64", "IN64 Collection", "mid", 42),
        ("INNO64", "Honda Civic Type R (FD2)", "1:64", "IN64 Collection", "mid", 35),
        ("INNO64", "Toyota AE86 Levin N2 Racing", "1:64", "IN64 Collection", "mid", 38),

        # Mini GT — More Releases
        ("Mini GT", "Ferrari F40 Rosso Corsa", "1:64", "MGT Collection", "standard", 22),
        ("Mini GT", "Nissan GT-R (R35) Nismo 2020", "1:64", "MGT Collection", "standard", 20),
        ("Mini GT", "Porsche 911 Targa 4S Heritage Edition", "1:64", "MGT Collection", "standard", 18),
        ("Mini GT", "Ford Bronco Wildtrak 2021", "1:64", "MGT Collection", "standard", 16),

        # Ignition Model — More Premium JDM
        ("Ignition Model", "Nissan Fairlady Z (S30) Wangan Midnight Devil Z", "1:18", "IG Limited", "grail", 380),
        ("Ignition Model", "Toyota Celica GT-Four (ST205) WRC", "1:18", "IG Limited", "grail", 340),
        ("Ignition Model", "Mazda Savanna RX-7 (FC3S) Infini", "1:18", "IG Limited", "grail", 300),

        # CMC — More Ultra-Premium
        ("CMC", "Ferrari 250 Testa Rossa 1958", "1:18", "CMC Limited", "grail", 550),
        ("CMC", "Mercedes-Benz W196 Fangio 1954", "1:18", "CMC Limited", "grail", 520),
        ("CMC", "Lancia D50 Ascari 1955", "1:18", "CMC Limited", "grail", 500),

        # Construction & Trucks — 1:50
        ("Diecast Masters", "CAT 336 Next Gen Excavator", "1:50", "Construction", "mid", 95),
        ("Diecast Masters", "CAT 966M Wheel Loader", "1:50", "Construction", "mid", 80),
        ("Diecast Masters", "CAT 797F Mining Truck", "1:50", "Construction", "high", 130),
        ("Motorart", "Volvo L350H Wheel Loader", "1:50", "Construction", "mid", 75),
        ("NZG", "Liebherr LTM 1300-6.2 Mobile Crane", "1:50", "Construction", "grail", 350),
        ("NZG", "Komatsu PC490LC-11 Excavator", "1:50", "Construction", "mid", 90),

        # Vintage Corgi — More 1960s/70s
        ("Corgi", "The Saint's Volvo P1800 (No. 258)", "1:43", "Vintage 1965", "grail", 280),
        ("Corgi", "Man from U.N.C.L.E. Thrushbuster (No. 497)", "1:43", "Vintage 1966", "grail", 300),
        ("Corgi", "Monkeemobile (No. 277)", "1:43", "Vintage 1968", "high", 200),
        ("Corgi", "Aston Martin DB4 (No. 218)", "1:43", "Vintage 1960", "high", 160),

        # Vintage Dinky Toys — More
        ("Dinky Toys", "Aston Martin DB5 (No. 110)", "1:43", "Vintage 1960s", "high", 180),
        ("Dinky Toys", "Meccano Dinky Petrol Tanker (No. 25d)", "1:43", "Vintage 1940s", "grail", 250),
        ("Dinky Toys", "Guy Van Slumberland (No. 514)", "1:43", "Vintage 1950s", "grail", 280),

        # Looksmart — More Limited
        ("Looksmart", "Ferrari 499P WEC Hypercar Champion 2023", "1:43", "Looksmart Limited", "high", 130),
        ("Looksmart", "Ferrari Purosangue Rosso Corsa", "1:43", "Looksmart Limited", "high", 110),

        # GT Spirit — More 1:18
        ("GT Spirit", "Nissan Skyline GT-R (R33) 400R Nismo", "1:18", "GT Spirit Asia Exclusive", "grail", 260),
        ("GT Spirit", "BMW M3 (E36) Lightweight", "1:18", "GT Spirit Limited", "high", 160),
        ("GT Spirit", "Audi RS6 Avant (C8) Nardo Grey", "1:18", "GT Spirit Limited", "high", 170),

        # Exoto — More Premium Racing
        ("Exoto", "Chaparral 2F 1967 Nurburgring", "1:18", "Grand Prix Classics", "grail", 400),
        ("Exoto", "McLaren M8A Can-Am 1968 Denny Hulme", "1:18", "Grand Prix Classics", "grail", 420),

        # GMP / ACME — More American Muscle
        ("ACME", "1968 Dodge Hemi Dart LO23 Super Stock", "1:18", "ACME Exclusive", "grail", 300),
        ("GMP", "1970 Plymouth Road Runner Vitamin C Orange", "1:18", "Street Fighter", "grail", 280),
        ("ACME", "1969 Chevrolet Nova SS 396 Hugger Orange", "1:18", "ACME Exclusive", "high", 250),

        # === ROUND 7 — 15+ new items to exceed 507 ===

        # Hot Wheels RLC — 2024/2025 Releases
        ("Hot Wheels RLC", "BMW 507", "1:64", "RLC Exclusive 2024", "high", 135),
        ("Hot Wheels RLC", "'73 BMW 3.0 CSL", "1:64", "RLC Exclusive 2025", "high", 140),

        # Hot Wheels $TH — 2025 Releases
        ("Hot Wheels $TH", "Lancia Delta Integrale", "1:64", "Super Treasure Hunt 2025", "mid", 65),
        ("Hot Wheels $TH", "'73 BMW 3.0 CSL Race Car", "1:64", "Super Treasure Hunt 2025", "mid", 60),

        # Matchbox — More Vintage Lesney
        ("Matchbox", "No. 32 Jaguar XK140", "1:64", "Lesney Vintage 1957", "high", 90),
        ("Matchbox", "No. 19 MG Midget TD", "1:64", "Lesney Vintage 1956", "high", 85),

        # AUTOart 1:18 — Latest Releases
        ("AUTOart", "Porsche 911 (992) GT3 RS Weissach", "1:18", "Composite", "grail", 380),
        ("AUTOart", "Lamborghini Revuelto", "1:18", "Composite", "grail", 400),

        # Tomica Limited Vintage Neo — Kei Cars
        ("Tomica LV", "Daihatsu Midget II Cargo", "1:64", "Limited Vintage Neo", "mid", 55),
        ("Tomica LV", "Subaru Sambar Classic Van", "1:64", "Limited Vintage Neo", "mid", 50),

        # Mini GT — 2024/2025 Releases
        ("Mini GT", "Pagani Utopia", "1:64", "MGT Collection", "standard", 20),
        ("Mini GT", "Koenigsegg Jesko Attack", "1:64", "MGT Collection", "standard", 22),
        ("Mini GT", "Bugatti Chiron Pur Sport", "1:64", "MGT Collection", "standard", 20),

        # Spark — More Le Mans
        ("Spark", "Cadillac V-Series.R Le Mans Winner 2023", "1:43", "Le Mans Collection", "high", 110),
        ("Spark", "Porsche 963 Penske Le Mans 2023", "1:43", "Le Mans Collection", "high", 105),

        # === ROUND 8 — 140 new items ===

        # Hot Wheels — Super Treasure Hunts 2024-2025 (+20)
        ("Hot Wheels $TH", "Toyota GR Supra (A90)", "1:64", "Super Treasure Hunt 2024", "mid", 70),
        ("Hot Wheels $TH", "Nissan 300ZX (Z32)", "1:64", "Super Treasure Hunt 2024", "mid", 65),
        ("Hot Wheels $TH", "Ford Mustang Shelby GT500", "1:64", "Super Treasure Hunt 2024", "mid", 60),
        ("Hot Wheels $TH", "Lamborghini Huracan STO", "1:64", "Super Treasure Hunt 2025", "mid", 70),
        ("Hot Wheels $TH", "Chevrolet Corvette C8 Z06", "1:64", "Super Treasure Hunt 2025", "high", 85),
        ("Hot Wheels $TH", "Honda Civic Type R (FK8)", "1:64", "Super Treasure Hunt 2024", "mid", 55),
        ("Hot Wheels $TH", "2007 Olds 442 (Classic STH)", "1:64", "Super Treasure Hunt 2007", "grail", 200),
        ("Hot Wheels $TH", "2008 Custom Mustang (Classic STH)", "1:64", "Super Treasure Hunt 2008", "grail", 180),
        ("Hot Wheels $TH", "2012 Camaro SS (Classic STH)", "1:64", "Super Treasure Hunt 2012", "high", 120),
        ("Hot Wheels $TH", "Datsun Bluebird 510 Wagon", "1:64", "Super Treasure Hunt 2024", "mid", 60),
        ("Hot Wheels RLC", "'69 Camaro SS Convention STH", "1:64", "Convention Super Treasure Hunt", "grail", 300),
        ("Hot Wheels", "Nissan Skyline 2000 GT-R (KPGC10)", "1:64", "Japan Historics Exclusive", "high", 140),
        ("Hot Wheels", "Toyota Celica Liftback 1975", "1:64", "Japan Historics Exclusive", "high", 130),
        ("Hot Wheels", "Datsun 240Z", "1:64", "Japan Historics 3 Exclusive", "high", 145),
        ("Hot Wheels RLC", "'70 Dodge Charger R/T (Spectraflame Red)", "1:64", "RLC Exclusive 2024", "high", 150),
        ("Hot Wheels RLC", "Nissan Fairlady Z (S30)", "1:64", "RLC Exclusive 2025", "high", 145),
        ("Hot Wheels RLC", "Shelby Cobra 427 S/C", "1:64", "RLC Exclusive 2024", "high", 155),
        ("Hot Wheels RLC", "Mercedes-Benz 300 SL Gullwing", "1:64", "RLC Exclusive 2025", "grail", 200),
        ("Hot Wheels $TH", "Alfa Romeo Giulia Sprint GTA", "1:64", "Super Treasure Hunt 2025", "mid", 60),
        ("Hot Wheels $TH", "Subaru Impreza WRX STI", "1:64", "Super Treasure Hunt 2025", "mid", 55),

        # Hot Wheels — Premium Lines (+15)
        ("Hot Wheels", "Nissan Skyline GT-R (BNR34)", "1:64", "Car Culture Mountain Drifters", "mid", 35),
        ("Hot Wheels", "BMW 2002", "1:64", "Car Culture Modern Classics", "mid", 30),
        ("Hot Wheels", "Volvo 850 Estate", "1:64", "Car Culture Fast Wagons", "standard", 28),
        ("Hot Wheels", "Audi RS6 Avant", "1:64", "Car Culture Fast Wagons", "standard", 28),
        ("Hot Wheels", "Honda NSX (NA1)", "1:64", "Car Culture Japan Historics 3", "mid", 40),
        ("Hot Wheels", "Mazda 787B", "1:64", "Team Transport JDM", "mid", 45),
        ("Hot Wheels", "BMW M3 (E30) DTM", "1:64", "Team Transport Euro", "mid", 40),
        ("Hot Wheels", "Ford Mustang Boss 302 Trans Am", "1:64", "Team Transport Muscle", "mid", 42),
        ("Hot Wheels", "Porsche 356 Speedster", "1:64", "Boulevard Premium", "standard", 22),
        ("Hot Wheels", "Lancia Stratos HF", "1:64", "Boulevard Premium", "standard", 25),
        ("Hot Wheels", "Toyota AE86 & Nissan Silvia S13", "1:64", "Premium 2-Pack Drift", "mid", 35),
        ("Hot Wheels", "Porsche 911 RSR & Ford GT40", "1:64", "Premium 2-Pack Le Mans", "mid", 38),
        ("Hot Wheels", "Chevrolet C10 Stepside", "1:64", "Car Culture Cruise Boulevard", "standard", 25),
        ("Hot Wheels", "Datsun 510 Pro Street", "1:64", "Car Culture Street Tuners", "mid", 32),
        ("Hot Wheels", "Mercedes-Benz 190E 2.5-16 Evo II", "1:64", "Car Culture Deutschland Design", "mid", 38),

        # Matchbox — Collectors (+10)
        ("Matchbox", "2023 Porsche 911 Turbo S", "1:64", "Matchbox Collectors Edition", "mid", 35),
        ("Matchbox", "1970 Ford Bronco Wildtrak", "1:64", "Matchbox Collectors Edition", "mid", 30),
        ("Matchbox", "2022 BMW iX", "1:64", "Matchbox Collectors Edition", "standard", 25),
        ("Matchbox", "1965 Land Rover Gen II", "1:64", "70th Anniversary Gold Edition", "high", 55),
        ("Matchbox", "1964 Austin Mini Cooper S", "1:64", "70th Anniversary Gold Edition", "high", 50),
        ("Matchbox", "1962 Volkswagen Beetle", "1:64", "70th Anniversary Gold Edition", "mid", 45),
        ("Matchbox", "Aston Martin DB5", "1:64", "Best of British Collection", "mid", 35),
        ("Matchbox", "Jaguar E-Type Roadster", "1:64", "Best of British Collection", "mid", 35),
        ("Matchbox", "Land Rover Defender 110", "1:64", "Best of British Collection", "standard", 28),
        ("Matchbox", "Lamborghini LM002", "1:64", "Matchbox x Top Gear", "mid", 40),

        # Tomica / Tomica Premium (+15)
        ("Tomica Premium", "Nissan Skyline GT-R (BNR32)", "1:64", "Tomica Premium 2024", "mid", 25),
        ("Tomica Premium", "Toyota Supra (A80)", "1:64", "Tomica Premium 2024", "mid", 25),
        ("Tomica Premium", "Honda NSX (NA1)", "1:64", "Tomica Premium", "mid", 22),
        ("Tomica Premium", "Mazda RX-7 (FD3S)", "1:64", "Tomica Premium", "mid", 22),
        ("Tomica Premium", "Honda S2000 (AP1)", "1:64", "Tomica Premium", "standard", 20),
        ("Tomica Premium", "Toyota AE86 Sprinter Trueno", "1:64", "Tomica Premium", "mid", 22),
        ("Tomica LV", "Nissan Skyline 2000 GT-R (KPGC110)", "1:64", "Limited Vintage Neo", "high", 80),
        ("Tomica LV", "Toyota Celica 1600GT (TA22)", "1:64", "Limited Vintage Neo", "mid", 65),
        ("Tomica LV", "Mazda Cosmo Sport (L10B)", "1:64", "Limited Vintage Neo", "high", 85),
        ("Tomica LV", "Nissan Fairlady Z-L (S30)", "1:64", "Limited Vintage Neo", "mid", 70),
        ("Tomica LV", "Honda Civic RS (SB1)", "1:64", "Limited Vintage Neo", "mid", 60),
        ("Tomica Premium", "Nissan GT-R (R35) Nismo 2024", "1:64", "Tomica Shop Exclusive", "mid", 35),
        ("Tomica Premium", "Toyota GR86 Initial D", "1:64", "Tomica Shop Exclusive", "mid", 40),
        ("Tomica Premium", "Mitsubishi Lancer Evo VI TME Initial D", "1:64", "Initial D Series", "mid", 45),
        ("Tomica Premium", "Nissan Skyline GT-R (R32) Initial D", "1:64", "Initial D Series", "mid", 45),

        # AUTOart 1:18 (+15)
        ("AUTOart", "Koenigsegg One:1 Grey", "1:18", "Composite", "grail", 450),
        ("AUTOart", "McLaren P1 Volcano Yellow", "1:18", "Composite", "grail", 380),
        ("AUTOart", "Bugatti Chiron French Racing Blue", "1:18", "Composite", "grail", 400),
        ("AUTOart", "Porsche 911 (992) GT3 RS Weissach Python Green", "1:18", "Composite", "grail", 390),
        ("AUTOart", "Liberty Walk Nissan GT-R (R35) White", "1:18", "Composite", "grail", 350),
        ("AUTOart", "Pagani Huayra Blu Francia", "1:18", "Composite", "grail", 420),
        ("AUTOart", "Ford GT Le Mans 2016 #68", "1:18", "Composite Race", "grail", 360),
        ("AUTOart", "Honda NSX-R (NA2) Championship White", "1:18", "Composite", "grail", 320),
        ("AUTOart", "Nissan Silvia S15 Spec-R Brilliant Blue", "1:18", "Composite", "high", 250),
        ("AUTOart", "Toyota Sprinter Trueno (AE86) Initial D Final Stage", "1:18", "Composite", "grail", 400),
        ("AUTOart", "Lexus LFA Whitest White", "1:18", "Composite", "grail", 380),
        ("AUTOart", "Mazda RX-7 (FD) Spirit R Type A Titanium Grey", "1:18", "Composite", "high", 290),
        ("AUTOart", "Subaru Impreza 22B STi", "1:18", "Composite", "grail", 360),
        ("AUTOart", "Chevrolet Corvette C7 ZR1 Sebring Orange", "1:18", "Composite", "high", 280),
        ("AUTOart", "Dodge Challenger SRT Demon Plum Crazy", "1:18", "Composite", "high", 260),

        # Spark 1:43 & 1:18 (+10)
        ("Spark", "Red Bull RB20 Max Verstappen 2024 Champion", "1:43", "F1 Collection", "high", 120),
        ("Spark", "Mercedes W15 Lewis Hamilton 2024", "1:43", "F1 Collection", "high", 110),
        ("Spark", "Ferrari SF-24 Charles Leclerc 2024", "1:43", "F1 Collection", "high", 115),
        ("Spark", "McLaren MCL38 Lando Norris 2024", "1:43", "F1 Collection", "high", 110),
        ("Spark", "Red Bull RB20 Max Verstappen 2024 Champion", "1:18", "F1 Collection 1:18", "grail", 280),
        ("Spark", "Porsche 963 #6 Le Mans Winner 2024", "1:43", "Le Mans Collection", "high", 115),
        ("Spark", "Toyota GR010 #7 Le Mans 2024", "1:43", "Le Mans Collection", "high", 105),
        ("Spark", "Toyota Yaris WRC Rovanpera Rally", "1:43", "Rally Collection", "mid", 85),
        ("Spark", "Hyundai i20 WRC Neuville Rally", "1:43", "Rally Collection", "mid", 80),
        ("Spark", "Alpine A524 Pierre Gasly 2024", "1:43", "F1 Collection", "mid", 95),

        # Maisto / Bburago (+10)
        ("Maisto", "Ducati Panigale V4 S", "1:12", "Maisto Motorcycles", "standard", 25),
        ("Maisto", "Honda CBR1000RR-R Fireblade", "1:12", "Maisto Motorcycles", "standard", 22),
        ("Maisto", "Kawasaki Ninja H2R", "1:12", "Maisto Motorcycles", "standard", 25),
        ("Maisto", "BMW S1000RR", "1:12", "Maisto Motorcycles", "standard", 22),
        ("Maisto", "Yamaha YZF-R1", "1:12", "Maisto Motorcycles", "standard", 20),
        ("Bburago", "Ferrari 296 GTB Signature Series", "1:18", "Bburago Signature", "mid", 55),
        ("Bburago", "Ferrari Monza SP1 Signature Series", "1:18", "Bburago Signature", "mid", 60),
        ("Bburago", "Lamborghini Revuelto Signature Series", "1:18", "Bburago Signature", "mid", 55),
        ("Bburago", "Ferrari F40 Red", "1:18", "Bburago Ferrari Collection", "standard", 35),
        ("Bburago", "Ferrari LaFerrari Red", "1:18", "Bburago Ferrari Collection", "mid", 45),

        # Johnny Lightning / Greenlight (+10)
        ("Johnny Lightning", "1970 Chevrolet Chevelle SS 454", "1:64", "Muscle Cars USA", "mid", 30),
        ("Johnny Lightning", "1969 Pontiac GTO Judge", "1:64", "Muscle Cars USA", "mid", 28),
        ("Johnny Lightning", "1968 Ford Mustang GT Fastback", "1:64", "Muscle Cars USA", "mid", 28),
        ("Johnny Lightning", "1971 Plymouth Road Runner 383", "1:64", "Muscle Cars USA", "standard", 25),
        ("Greenlight", "1967 Ford Mustang Eleanor", "1:64", "Hollywood Series", "mid", 35),
        ("Greenlight", "1977 Pontiac Trans Am Smokey & Bandit", "1:64", "Hollywood Series", "mid", 38),
        ("Greenlight", "2023 Ford Bronco Raptor", "1:64", "Hobby Exclusive", "mid", 32),
        ("Greenlight", "1970 Dodge Challenger R/T", "1:64", "Hobby Exclusive", "mid", 30),
        ("Greenlight", "1973 Ford F-100 Pickup & Trailer", "1:64", "Diorama Set", "mid", 45),
        ("Greenlight", "Gas Station Diorama with Vintage Pumps", "1:64", "Diorama Set", "mid", 40),

        # Tarmac Works / INNO64 (+15)
        ("Tarmac Works", "Nissan Skyline GT-R (R34) Z-Tune Bayside Blue", "1:64", "Tarmac Works LE", "high", 65),
        ("Tarmac Works", "Mitsubishi Lancer Evo VI TME Ralliart", "1:64", "Tarmac Works LE", "mid", 50),
        ("Tarmac Works", "Subaru Impreza WRX STI 555 Rally", "1:64", "Tarmac Works LE", "mid", 48),
        ("Tarmac Works", "Toyota GR Yaris Rally1 WRC", "1:64", "Tarmac Works LE", "mid", 45),
        ("Tarmac Works", "Porsche 911 (993) RWB Rauh-Welt", "1:64", "Tarmac Works LE", "mid", 55),
        ("Tarmac Works", "Nissan GT-R (R35) Nismo GT3", "1:64", "Tarmac Works Event Exclusive", "high", 80),
        ("Tarmac Works", "Honda Civic Type R (EK9) BTCC", "1:64", "Tarmac Works Collab Edition", "high", 70),
        ("Inno64", "Honda Civic (EF9) SiR", "1:64", "Inno64 LE", "mid", 35),
        ("Inno64", "Nissan Silvia S14 Adrenaline", "1:64", "Inno64 LE", "mid", 35),
        ("Inno64", "Toyota AE86 Sprinter Trueno Drift", "1:64", "Inno64 LE", "mid", 38),
        ("Inno64", "Mitsubishi Pajero Evolution", "1:64", "Inno64 LE", "mid", 32),
        ("Inno64", "Nissan Skyline GT-R (R33) 400R", "1:64", "Inno64 Event Exclusive", "high", 65),
        ("Tarmac Works", "Mercedes-AMG GT3 Macau GP", "1:64", "Tarmac Works Event Exclusive", "high", 75),
        ("Inno64", "Honda Integra Type R (DC2) Spoon", "1:64", "Inno64 Collab Edition", "mid", 42),
        ("Tarmac Works", "BMW M3 (E30) DTM Champion", "1:64", "Tarmac Works LE", "mid", 50),

        # Mini GT (+15)
        ("Mini GT", "Bugatti Chiron Super Sport 300+ Black", "1:64", "MGT Collection", "standard", 22),
        ("Mini GT", "Porsche 911 (992) Targa 4S Heritage", "1:64", "MGT Collection", "standard", 22),
        ("Mini GT", "BMW M4 CSL (G82) Frozen Brooklyn Grey", "1:64", "MGT Collection", "standard", 18),
        ("Mini GT", "Mercedes-AMG G63 Brabus 800", "1:64", "MGT Collection", "standard", 20),
        ("Mini GT", "McLaren Elva Silver", "1:64", "MGT Collection", "standard", 18),
        ("Mini GT", "Nissan Skyline GT-R (R34) V-Spec II Bayside Blue", "1:64", "MGT Chase Raw", "high", 80),
        ("Mini GT", "Lamborghini Countach LPI 800-4 Raw Chase", "1:64", "MGT Chase Green", "high", 85),
        ("Mini GT", "Porsche 911 GT3 RS (992) Raw Chase", "1:64", "MGT Chase Raw", "high", 90),
        ("Mini GT", "Lamborghini Huracan STO LB Works", "1:64", "LB Works Series", "mid", 25),
        ("Mini GT", "Nissan GT-R (R35) LB Works Type 2", "1:64", "LB Works Series", "mid", 28),
        ("Mini GT", "BMW M4 LB Works", "1:64", "LB Works Series", "mid", 25),
        ("Mini GT", "Toyota GR Supra (A90) LB Works", "1:64", "LB Works Series", "mid", 25),
        ("Mini GT", "Pagani Zonda F Convention Exclusive", "1:64", "MGT Convention Exclusive", "high", 70),
        ("Mini GT", "Ford GT MK IV Heritage Edition Convention", "1:64", "MGT Convention Exclusive", "high", 65),

        # Kyosho (+10)
        ("Kyosho", "Ferrari 250 GTO 1962 Rosso Corsa", "1:18", "Kyosho Original", "grail", 420),
        ("Kyosho", "Lamborghini Miura SV Orange", "1:18", "Kyosho Original", "grail", 380),
        ("Kyosho", "Nissan Skyline GT-R (BNR34) V-Spec II Nur Millennium Jade", "1:18", "Kyosho Original", "grail", 400),
        ("Kyosho", "Toyota 2000GT White", "1:18", "Kyosho Original", "grail", 360),
        ("Kyosho", "Honda NSX Type R (NA2) Championship White", "1:18", "Kyosho Original", "high", 280),
        ("Kyosho", "Ferrari LaFerrari Rosso Corsa", "1:64", "Kyosho 1:64 Ferrari", "standard", 18),
        ("Kyosho", "Ferrari F40 Rosso Corsa", "1:64", "Kyosho 1:64 Ferrari", "standard", 15),
        ("Kyosho", "Nissan Skyline GT-R (R32)", "1:64", "Kyosho JDM Series", "standard", 15),
        ("Kyosho", "Toyota AE86 Sprinter Trueno", "1:64", "Kyosho JDM Series", "standard", 15),
        ("Kyosho", "Kyosho Mini-Z AWD MA-030EVO Nissan GT-R", "1:27", "Kyosho Egg RC", "high", 150),
    ]

    catalog = []
    for brand, name, scale, variant, tier, price in vehicles:
        catalog.append({
            "brand": brand,
            "name": name,
            "scale": scale,
            "variant": variant,
            "rarity_tier": tier,
            "price_eur": price,
        })

    catalog.extend(_batch_premium_diecast_2025())
    catalog.extend(_variant_expansion())
    # Deduplicate by ('brand', 'name', 'scale', 'variant') (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = (item["brand"], item["name"], item["scale"], item["variant"])
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


def _batch_premium_diecast_2025() -> list[dict]:
    """Batch 8 — Kyosho 1:18, Minichamps F1, Spark F1/Le Mans, BBR, MR Collection,
    Tarmac Works, Inno64 premium JDM. ~50 items."""

    items = [
        # Kyosho 1:18 — Ferrari
        ("Kyosho", "Ferrari F40 Rosso Corsa", "1:18", "Kyosho Original", "grail", 320),
        ("Kyosho", "Ferrari 250 GTO 1962 Red", "1:18", "Kyosho Original", "grail", 380),
        ("Kyosho", "Ferrari Enzo Ferrari Red", "1:18", "Kyosho Original", "high", 280),
        ("Kyosho", "Ferrari Testarossa Red", "1:18", "Kyosho Original", "high", 260),

        # Kyosho 1:18 — Lamborghini
        ("Kyosho", "Lamborghini Countach LP400 White", "1:18", "Kyosho Original", "grail", 340),
        ("Kyosho", "Lamborghini Miura P400SV Orange", "1:18", "Kyosho Original", "grail", 360),
        ("Kyosho", "Lamborghini Diablo GT Metallic Grey", "1:18", "Kyosho Original", "high", 250),

        # Kyosho 1:18 — Porsche
        ("Kyosho", "Porsche 911 (964) Carrera RS Guards Red", "1:18", "Kyosho Original", "high", 240),
        ("Kyosho", "Porsche 911 (993) GT2 Speed Yellow", "1:18", "Kyosho Original", "high", 260),
        ("Kyosho", "Porsche 356A Speedster Silver", "1:18", "Kyosho Original", "high", 230),

        # Minichamps F1 — Red Bull
        ("Minichamps", "Red Bull RB19 Max Verstappen 2023 World Champion", "1:18", "F1 Collection", "grail", 350),
        ("Minichamps", "Red Bull RB19 Sergio Perez 2023", "1:18", "F1 Collection", "high", 250),
        ("Minichamps", "Red Bull RB18 Max Verstappen 2022 World Champion", "1:18", "F1 Collection", "grail", 380),

        # Minichamps F1 — Mercedes
        ("Minichamps", "Mercedes W14 Lewis Hamilton 2023", "1:18", "F1 Collection", "high", 260),
        ("Minichamps", "Mercedes W11 Lewis Hamilton 2020 Record Season", "1:18", "F1 Collection", "grail", 400),
        ("Minichamps", "Mercedes W10 Lewis Hamilton 2019 Monaco GP Winner", "1:18", "F1 Collection", "high", 280),

        # Minichamps F1 — Ferrari / McLaren
        ("Minichamps", "Ferrari SF-23 Charles Leclerc 2023", "1:18", "F1 Collection", "high", 250),
        ("Minichamps", "McLaren MCL60 Lando Norris 2023 Silverstone", "1:18", "F1 Collection", "high", 240),
        ("Minichamps", "McLaren MCL38 Lando Norris 2024 Miami GP Winner", "1:18", "F1 Collection", "high", 280),

        # Spark 1:43 F1 — Le Mans Winners
        ("Spark", "Toyota GR010 Hybrid Le Mans Winner 2024", "1:43", "Le Mans Collection", "high", 115),
        ("Spark", "Porsche 919 Hybrid Le Mans Winner 2017", "1:43", "Le Mans Collection", "high", 120),
        ("Spark", "Audi R18 e-tron quattro Le Mans Winner 2014", "1:43", "Le Mans Collection", "high", 110),
        ("Spark", "Ferrari 499P Le Mans Winner 2023 #51", "1:43", "Le Mans Collection", "high", 130),

        # Spark 1:43 F1 — Monaco GP
        ("Spark", "Red Bull RB19 Verstappen Monaco GP Winner 2023", "1:43", "F1 Monaco GP", "high", 100),
        ("Spark", "Ferrari SF-24 Leclerc Monaco GP Winner 2024", "1:43", "F1 Monaco GP", "high", 110),
        ("Spark", "McLaren MCL35M Ricciardo Monza GP Winner 2021", "1:43", "F1 Collection", "high", 95),

        # BBR Models Ferrari
        ("BBR Models", "Ferrari LaFerrari Rosso Corsa", "1:18", "BBR Limited", "grail", 450),
        ("BBR Models", "Ferrari 296 GTB Assetto Fiorano Yellow", "1:18", "BBR Limited", "grail", 420),
        ("BBR Models", "Ferrari SF90 Stradale Red", "1:18", "BBR Limited", "grail", 400),
        ("BBR Models", "Ferrari Roma Spider Argento Nurburgring", "1:18", "BBR Limited", "high", 350),
        ("BBR Models", "Ferrari 812 Competizione A Blu Capri", "1:43", "BBR Limited", "high", 180),

        # MR Collection — Hypercars
        ("MR Collection", "Bugatti Chiron Sport Nocturne Black", "1:18", "MR Limited", "grail", 500),
        ("MR Collection", "Pagani Huayra BC Roadster Blu Tricolore", "1:18", "MR Limited", "grail", 480),
        ("MR Collection", "Lamborghini Revuelto Verde Alceo", "1:18", "MR Limited", "grail", 460),
        ("MR Collection", "Bugatti Mistral W16 Yellow", "1:18", "MR Limited", "grail", 520),
        ("MR Collection", "Pagani Utopia Platinum", "1:18", "MR Limited", "grail", 490),

        # Tarmac Works — RWB Porsche
        ("Tarmac Works", "Porsche 911 (930) RWB Rauh-Welt Natalia Kills", "1:64", "Hobby64", "mid", 45),
        ("Tarmac Works", "Porsche 911 (993) RWB Backdate Holy Grail", "1:64", "Hobby64", "mid", 48),
        ("Tarmac Works", "Porsche 911 (964) RWB Idlers Car", "1:64", "Hobby64", "mid", 42),

        # Tarmac Works — Honda Civic & JDM
        ("Tarmac Works", "Honda Civic EG6 Gr.A Racing JTCC 1992", "1:64", "Hobby64", "mid", 40),
        ("Tarmac Works", "Honda Civic EG6 No Good Racing", "1:64", "Hobby64", "mid", 38),
        ("Tarmac Works", "Honda NSX GT3 Evo Macau Grand Prix", "1:64", "Hobby64", "mid", 36),
        ("Tarmac Works", "Mitsubishi Lancer Evo VI Tommi Makinen WRC", "1:64", "Hobby64", "mid", 42),

        # Inno64 — Nissan Skyline GT-R
        ("INNO64", "Nissan Skyline GT-R (R32) Pandem Rocket Bunny", "1:64", "IN64 Collection", "mid", 45),
        ("INNO64", "Nissan Skyline GT-R (R34) V-Spec II Nur Millennium Jade", "1:64", "IN64 Collection", "mid", 48),
        ("INNO64", "Nissan Skyline GT-R (R34) Nismo Z-tune Silver", "1:64", "IN64 Collection", "mid", 50),
        ("INNO64", "Nissan Skyline GT-R (R32) Group A Calsonic 1990", "1:64", "IN64 Collection", "mid", 46),

        # Inno64 — More JDM Legends
        ("INNO64", "Toyota Sprinter Trueno AE86 Black Limited", "1:64", "IN64 Collection", "mid", 42),
        ("INNO64", "Mazda RX-7 (FD3S) Mazdaspeed A-Spec", "1:64", "IN64 Collection", "mid", 40),
        ("INNO64", "Mitsubishi Lancer Evo III GSR Rally Art", "1:64", "IN64 Collection", "mid", 38),
        ("INNO64", "Honda Civic Type R (EK9) Championship White", "1:64", "IN64 Collection", "mid", 36),

        # === BATCH 9 — 50 new items to reach 605+ ===

        # Hot Wheels Super Treasure Hunts — 2024/2025 Wave
        ("Hot Wheels $TH", "Porsche 918 Spyder", "1:64", "Super Treasure Hunt 2024", "high", 90),
        ("Hot Wheels $TH", "Lamborghini Countach LPI 800-4", "1:64", "Super Treasure Hunt 2024", "mid", 70),
        ("Hot Wheels $TH", "Ferrari F40", "1:64", "Super Treasure Hunt 2024", "high", 95),
        ("Hot Wheels $TH", "'69 Ford Mustang Boss 302", "1:64", "Super Treasure Hunt 2024", "mid", 65),
        ("Hot Wheels $TH", "Toyota GR Supra", "1:64", "Super Treasure Hunt 2025", "mid", 60),
        ("Hot Wheels $TH", "Nissan Z (RZ34)", "1:64", "Super Treasure Hunt 2025", "mid", 55),
        ("Hot Wheels $TH", "Pagani Huayra Roadster", "1:64", "Super Treasure Hunt 2025", "high", 85),
        ("Hot Wheels $TH", "'71 Plymouth GTX", "1:64", "Super Treasure Hunt 2025", "mid", 60),
        ("Hot Wheels $TH", "Aston Martin Valhalla", "1:64", "Super Treasure Hunt 2025", "mid", 65),
        ("Hot Wheels $TH", "Alfa Romeo Giulia Sprint GTA", "1:64", "Super Treasure Hunt 2024", "mid", 70),

        # Matchbox Premium — Collectors Series
        ("Matchbox", "1964 Ford Fairlane Thunderbolt", "1:64", "Premium Collectors 2024", "mid", 45),
        ("Matchbox", "Nissan Skyline 2000GT-R (KPGC10)", "1:64", "Premium Collectors 2024", "mid", 50),
        ("Matchbox", "Porsche 914/6", "1:64", "Premium Collectors 2024", "mid", 42),
        ("Matchbox", "1970 Plymouth Barracuda", "1:64", "Premium Collectors 2024", "mid", 48),
        ("Matchbox", "Toyota FJ40 Land Cruiser", "1:64", "Premium Collectors 2025", "mid", 40),
        ("Matchbox", "BMW 2002 Turbo", "1:64", "Premium Collectors 2025", "mid", 45),
        ("Matchbox", "Volkswagen Karmann Ghia Coupe", "1:64", "Premium Collectors 2025", "mid", 42),
        ("Matchbox", "Mercedes-Benz 300 SL Gullwing", "1:64", "Premium Collectors 2025", "mid", 55),

        # Tomica Limited Vintage Neo — More JDM Classics
        ("Tomica LV", "Toyota Supra (JZA70) 2.5GT Twin Turbo", "1:64", "Limited Vintage Neo", "mid", 65),
        ("Tomica LV", "Nissan 180SX (RPS13) Type II", "1:64", "Limited Vintage Neo", "mid", 55),
        ("Tomica LV", "Honda Prelude Si (BA4)", "1:64", "Limited Vintage Neo", "mid", 50),
        ("Tomica LV", "Mitsubishi Lancer Evolution III GSR", "1:64", "Limited Vintage Neo", "mid", 60),
        ("Tomica LV", "Toyota Crown Comfort Taxi", "1:64", "Limited Vintage Neo", "mid", 45),
        ("Tomica LV", "Nissan Cedric (Y31) Gran Turismo SV", "1:64", "Limited Vintage Neo", "mid", 55),

        # AUTOart 1:18 — Latest Premium Releases
        ("AUTOart", "Porsche 911 (992) GT3 Shark Blue", "1:18", "Composite", "grail", 360),
        ("AUTOart", "Koenigsegg Agera RS (Naraya)", "1:18", "Composite", "grail", 420),
        ("AUTOart", "McLaren Speedtail Supernova Silver", "1:18", "Composite", "grail", 380),
        ("AUTOart", "Lexus LFA Nurburgring Package Pearl Yellow", "1:18", "Composite", "grail", 350),
        ("AUTOart", "Pagani Huayra BC Blu Francia", "1:18", "Composite", "grail", 400),
        ("AUTOart", "Honda NSX (NC1) Type S Gotham Grey", "1:18", "Composite", "high", 280),
        ("AUTOart", "Bugatti Chiron Sport French Racing Blue", "1:18", "Composite", "grail", 450),

        # Maisto Premium — Special Edition Plus
        ("Maisto", "Ford GT (2019) Heritage Edition Gulf Blue", "1:18", "Premium Edition", "mid", 55),
        ("Maisto", "Bugatti Divo Matte Grey", "1:18", "Premium Edition", "mid", 58),
        ("Maisto", "Lamborghini Sian FKP 37 Green", "1:18", "Premium Edition", "mid", 52),
        ("Maisto", "Ferrari Monza SP1 Rosso Corsa", "1:18", "Premium Edition", "mid", 50),
        ("Maisto", "McLaren Elva Gulf Livery", "1:18", "Premium Edition", "mid", 55),

        # Greenlight — More Chase & Series
        ("Greenlight", "1979 Pontiac Firebird Trans Am Rocky II", "1:64", "Hollywood Series", "mid", 42),
        ("Greenlight", "2020 Ford Explorer Police Interceptor", "1:64", "Chase Green Machine", "standard", 28),
        ("Greenlight", "1977 Pontiac LeMans Safari Terminator", "1:64", "Hollywood Series", "mid", 40),
        ("Greenlight", "1969 Chevrolet Camaro Z/28 The Crow", "1:64", "Hollywood Series", "mid", 45),
        ("Greenlight", "2023 Ford Bronco Wildtrak Yellowstone", "1:64", "Hollywood Series", "standard", 30),
        ("Greenlight", "1973 Ford Falcon XB Last of the V8 Interceptors", "1:64", "Hollywood Series", "mid", 50),

        # JADA Toys Imports — JDM Tuners & Hollywood Rides
        ("JADA", "Nissan Skyline GT-R (R34) Fast & Furious Silver", "1:24", "Hollywood Rides", "mid", 45),
        ("JADA", "Mazda RX-7 (FD) Fast & Furious Red", "1:24", "Hollywood Rides", "mid", 42),
        ("JADA", "Honda S2000 Fast & Furious Pink", "1:24", "Hollywood Rides", "mid", 40),
        ("JADA", "Mitsubishi Eclipse GSX Fast & Furious Green", "1:24", "Hollywood Rides", "mid", 38),
        ("JADA", "Nissan 350Z Fast & Furious Orange", "1:24", "Hollywood Rides", "mid", 40),
        ("JADA", "Toyota FT-1 Concept JDM Tuners Bronze", "1:24", "JDM Tuners", "mid", 38),

        # === BATCH 10 — 91 new items to reach 700+ ===

        # Hot Wheels RLC — 2025 Releases
        ("Hot Wheels RLC", "Mercedes-Benz 300 SLR Uhlenhaut", "1:64", "RLC Exclusive 2025", "grail", 220),
        ("Hot Wheels RLC", "'70 Plymouth Superbird", "1:64", "RLC Exclusive 2025", "high", 145),
        ("Hot Wheels RLC", "Porsche 911 (964) Singer", "1:64", "RLC Exclusive 2025", "high", 155),
        ("Hot Wheels RLC", "'69 Camaro SS 396", "1:64", "RLC Exclusive 2025", "high", 130),
        ("Hot Wheels RLC", "Datsun Sunny Truck (B120)", "1:64", "RLC Exclusive 2025", "high", 120),

        # Hot Wheels Convention — 2025 Circuit
        ("Hot Wheels", "'67 Camaro (Brazil Convention 2025)", "1:64", "Convention Exclusive", "grail", 290),
        ("Hot Wheels", "Volkswagen T1 Panel Bus (UK Convention 2025)", "1:64", "Convention Exclusive", "grail", 270),
        ("Hot Wheels", "Nissan Skyline H/T 2000GT-R (Japan Convention 2025)", "1:64", "Convention Exclusive", "grail", 310),
        ("Hot Wheels", "'71 Datsun Bluebird 510 (Nationals 2025)", "1:64", "Convention Exclusive", "grail", 340),

        # Matchbox 70th Anniversary
        ("Matchbox", "Land Rover Defender 90 70th Anniversary", "1:64", "70th Anniversary Gold", "mid", 55),
        ("Matchbox", "Volkswagen Type 2 Bus 70th Anniversary", "1:64", "70th Anniversary Gold", "mid", 50),
        ("Matchbox", "MG 1100 70th Anniversary", "1:64", "70th Anniversary Gold", "mid", 48),
        ("Matchbox", "Mercedes-Benz L319 Delivery 70th Anniversary", "1:64", "70th Anniversary Gold", "mid", 52),
        ("Matchbox", "Ford Model A 70th Anniversary", "1:64", "70th Anniversary Gold", "mid", 55),
        ("Matchbox", "Citroen DS 70th Anniversary", "1:64", "70th Anniversary Gold", "mid", 48),

        # AUTOart 1:18 — New Premium 2025
        ("AUTOart", "Toyota GR Yaris Rallye Platinum White", "1:18", "Composite", "high", 280),
        ("AUTOart", "Nissan Skyline GT-R (R34) Z-Tune Silver", "1:18", "Composite", "grail", 450),
        ("AUTOart", "McLaren 720S GT3 Gulf Livery", "1:18", "Composite", "grail", 380),
        ("AUTOart", "Ford GT (2017) Heritage Edition", "1:18", "Composite", "grail", 360),
        ("AUTOart", "Porsche 918 Spyder Weissach Package", "1:18", "Composite", "grail", 400),

        # Minichamps F1 — 2025 Season
        ("Minichamps", "Red Bull RB21 Verstappen 2025", "1:43", "F1 Collection", "high", 115),
        ("Minichamps", "McLaren MCL39 Norris 2025", "1:43", "F1 Collection", "high", 110),
        ("Minichamps", "Ferrari SF-25 Hamilton 2025 Debut", "1:43", "F1 Collection", "grail", 150),
        ("Minichamps", "Ferrari SF-25 Leclerc 2025", "1:43", "F1 Collection", "high", 120),
        ("Minichamps", "Mercedes W16 Russell 2025", "1:43", "F1 Collection", "mid", 95),
        ("Minichamps", "Aston Martin AMR25 Alonso 2025", "1:43", "F1 Collection", "mid", 90),
        ("Minichamps", "Williams FW47 Sainz 2025", "1:43", "F1 Collection", "mid", 85),
        ("Minichamps", "Alpine A525 Gasly 2025", "1:43", "F1 Collection", "mid", 80),

        # Spark 1:43 — Le Mans 2024/2025
        ("Spark", "Porsche 963 Penske Le Mans Winner 2024", "1:43", "Le Mans Collection", "high", 120),
        ("Spark", "Ferrari 499P Le Mans 2024 #50", "1:43", "Le Mans Collection", "high", 115),
        ("Spark", "Toyota GR010 Hybrid Le Mans 2024 #8", "1:43", "Le Mans Collection", "high", 110),
        ("Spark", "Lamborghini SC63 Le Mans 2024 Debut", "1:43", "Le Mans Collection", "high", 125),
        ("Spark", "BMW M Hybrid V8 Le Mans 2024", "1:43", "Le Mans Collection", "mid", 95),
        ("Spark", "Alpine A424 Le Mans 2024", "1:43", "Le Mans Collection", "mid", 90),

        # Tarmac Works — New 2025
        ("Tarmac Works", "Toyota GR86 D1GP Drift Car", "1:64", "Hobby64", "mid", 38),
        ("Tarmac Works", "Nissan GT-R (R35) Nismo GT3 Bathurst 12h", "1:64", "Hobby64", "mid", 40),
        ("Tarmac Works", "Honda Civic Type R (FL5) Time Attack", "1:64", "Global64", "mid", 35),
        ("Tarmac Works", "Porsche 911 (992) GT3 RS Weissach", "1:64", "Global64", "mid", 42),
        ("Tarmac Works", "BMW M4 GT3 DTM 2024", "1:64", "Hobby64", "mid", 36),
        ("Tarmac Works", "Subaru BRZ Super GT 2024", "1:64", "Hobby64", "mid", 38),

        # INNO64 — 2025 Releases
        ("INNO64", "Honda NSX (NA1) Type R Championship White", "1:64", "IN64 Collection", "mid", 44),
        ("INNO64", "Nissan Skyline GT-R (R32) Group A HKS", "1:64", "IN64 Collection", "mid", 46),
        ("INNO64", "Toyota Supra (JZA80) Toms Castrol", "1:64", "IN64 Collection", "mid", 48),
        ("INNO64", "Mitsubishi Lancer Evo VI Tommi Makinen WRC White", "1:64", "IN64 Collection", "mid", 42),
        ("INNO64", "Mazda RX-7 (FC3S) RE Amemiya", "1:64", "IN64 Collection", "mid", 40),
        ("INNO64", "Subaru Impreza WRX STI (GC8) 555 WRC", "1:64", "IN64 Collection", "mid", 44),

        # BM Creations — 1:64 JDM
        ("BM Creations", "Suzuki Jimny Sierra (JB74) Kinetic Yellow", "1:64", "Junior Collection", "standard", 22),
        ("BM Creations", "Mitsubishi Pajero Evolution Silver", "1:64", "Junior Collection", "standard", 24),
        ("BM Creations", "Subaru Sambar Dias Classic", "1:64", "Junior Collection", "standard", 20),
        ("BM Creations", "Toyota Land Cruiser 80 (FJ80) White", "1:64", "Junior Collection", "standard", 22),
        ("BM Creations", "Honda City Turbo II Red with Motocompo", "1:64", "Junior Collection", "standard", 25),
        ("BM Creations", "Daihatsu Copen Red", "1:64", "Junior Collection", "standard", 20),

        # Tomica Limited Vintage Neo — New 2025
        ("Tomica LV", "Nissan Skyline GT-R (R32) NISMO", "1:64", "Limited Vintage Neo", "mid", 70),
        ("Tomica LV", "Toyota Celica XX (MA61) 2800GT", "1:64", "Limited Vintage Neo", "mid", 55),
        ("Tomica LV", "Nissan Leopard (F31) Ultima", "1:64", "Limited Vintage Neo", "mid", 60),
        ("Tomica LV", "Honda Ballade Sports CR-X Si", "1:64", "Limited Vintage Neo", "mid", 55),
        ("Tomica LV", "Mitsubishi Galant GTO MR", "1:64", "Limited Vintage Neo", "high", 80),

        # Mini GT — Premium 2025
        ("Mini GT", "Porsche 911 (992) GT3 RS Guards Red", "1:64", "MGT Collection", "standard", 22),
        ("Mini GT", "Lamborghini Revuelto Verde Alceo", "1:64", "MGT Collection", "standard", 20),
        ("Mini GT", "Bugatti Mistral Black", "1:64", "MGT Collection", "standard", 22),
        ("Mini GT", "Ferrari 296 GTB Assetto Fiorano Red", "1:64", "MGT Collection", "standard", 20),
        ("Mini GT", "McLaren 750S Spider Blue", "1:64", "MGT Collection", "standard", 18),

        # BBR Models — Latest Ferrari
        ("BBR Models", "Ferrari F80 Rosso Corsa (2025)", "1:18", "BBR Limited", "grail", 500),
        ("BBR Models", "Ferrari SF90 XX Stradale Black", "1:18", "BBR Limited", "grail", 480),
        ("BBR Models", "Ferrari Purosangue Blu Pozzi", "1:43", "BBR Limited", "high", 180),

        # MR Collection — Latest Hypercars
        ("MR Collection", "Lamborghini Temerario Blu Caelum", "1:18", "MR Limited", "grail", 480),
        ("MR Collection", "Bugatti Tourbillon Blue Royal", "1:18", "MR Limited", "grail", 540),
        ("MR Collection", "Pagani Utopia Roadster Exposed Carbon", "1:18", "MR Limited", "grail", 510),

        # Ignition Model — Premium JDM
        ("Ignition Model", "Toyota Sprinter Trueno (AE86) TRD N2 3Door", "1:18", "IG Limited", "grail", 350),
        ("Ignition Model", "Honda S2000 (AP1) Type V Indy Yellow", "1:18", "IG Limited", "grail", 320),

        # CMC — 2025 Premium Classic
        ("CMC", "Maserati 300S Sports Car 1956", "1:18", "CMC Limited", "grail", 540),
        ("CMC", "Porsche 901 Sport Coupe 1964", "1:18", "CMC Limited", "grail", 480),

        # Hot Wheels $TH — 2025 Q2 Wave
        ("Hot Wheels $TH", "Porsche 911 (930) Turbo", "1:64", "Super Treasure Hunt 2025", "mid", 65),
        ("Hot Wheels $TH", "BMW M3 (E30) Sport Evolution", "1:64", "Super Treasure Hunt 2025", "mid", 70),
        ("Hot Wheels $TH", "Mazda RX-7 (FC) Savanna", "1:64", "Super Treasure Hunt 2025", "mid", 60),
        ("Hot Wheels $TH", "Mercedes-AMG GT Black Series", "1:64", "Super Treasure Hunt 2025", "high", 80),

        # Additional Diecast Items (+14)
        ("AUTOart", "Lamborghini Huracan Performante Verde Mantis", "1:18", "AUTOart Composite", "grail", 280),
        ("AUTOart", "Porsche 911 (991.2) GT2 RS Weissach White", "1:18", "AUTOart Composite", "grail", 300),
        ("AUTOart", "McLaren 720S Glacier White", "1:18", "AUTOart Composite", "high", 220),
        ("Minichamps", "Porsche 911 (992) GT3 RS Acid Green", "1:18", "Minichamps 2024", "high", 180),
        ("Minichamps", "BMW M3 (G80) Isle of Man Green", "1:18", "Minichamps 2024", "high", 160),
        ("Spark", "Toyota GR010 Le Mans Winner 2024 #8", "1:43", "Le Mans Collection", "high", 115),
        ("Spark", "Ferrari 499P Le Mans 2024 #50", "1:43", "Le Mans Collection", "high", 110),
        ("Tarmac Works", "Honda Civic EG6 Spoon Sports", "1:64", "Tarmac Works LE", "mid", 45),
        ("Tarmac Works", "Mitsubishi Lancer Evolution VI TME", "1:64", "Tarmac Works LE", "mid", 42),
        ("Inno64", "Honda NSX-R (NA2) Championship White", "1:64", "Inno64 LE", "mid", 38),
        ("Inno64", "Nissan Silvia S15 Rocket Bunny", "1:64", "Inno64 LE", "mid", 40),
        ("Mini GT", "Ford GT MK II #006 Shadow Black", "1:64", "MGT Collection", "standard", 22),
        ("Mini GT", "Mercedes-AMG ONE Silver", "1:64", "MGT Collection", "standard", 24),
        ("Hot Wheels RLC", "Toyota 2000GT", "1:64", "RLC Exclusive 2025", "high", 135),
    ]

    catalog = []
    for brand, name, scale, variant, tier, price in items:
        catalog.append({
            "brand": brand,
            "name": name,
            "scale": scale,
            "variant": variant,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def _variant_expansion() -> list[dict]:
    """Scale/color/chase/convention variants for existing diecast models. ~70 items."""
    variants = [
        # Super Treasure Hunt chase variants
        ("Hot Wheels $TH", "Toyota AE86 Sprinter Trueno", "1:64", "Super Treasure Hunt ZAMAC", "high", 95),
        ("Hot Wheels $TH", "Porsche 911 GT3 RS", "1:64", "Super Treasure Hunt Chrome", "high", 85),
        ("Hot Wheels $TH", "Nissan Skyline GT-R (BNR32)", "1:64", "Super Treasure Hunt ZAMAC", "high", 90),
        ("Hot Wheels $TH", "'92 BMW M3", "1:64", "Super Treasure Hunt Raw", "high", 80),
        ("Hot Wheels $TH", "McLaren Senna", "1:64", "Super Treasure Hunt ZAMAC", "grail", 130),
        ("Hot Wheels $TH", "Mazda RX-7 (FD)", "1:64", "Super Treasure Hunt Chrome", "high", 85),
        # Greenlight Green Machine chase
        ("Greenlight", "1967 Ford Mustang GT Fastback", "1:64", "Green Machine Chase", "high", 80),
        ("Greenlight", "1969 Chevrolet Camaro Z/28", "1:64", "Green Machine Chase", "high", 75),
        ("Greenlight", "1970 Dodge Challenger R/T", "1:64", "Green Machine Chase", "high", 70),
        ("Greenlight", "1977 Pontiac Firebird Trans Am", "1:64", "Green Machine Chase", "high", 85),
        ("Greenlight", "1971 Plymouth Hemi 'Cuda", "1:64", "Green Machine Chase", "high", 90),
        ("Greenlight", "2021 Ford Bronco Wildtrak", "1:64", "Green Machine Chase", "mid", 55),
        # Raw / Error Card variants
        ("Hot Wheels", "Custom '67 Pontiac Firebird", "1:64", "Error Card (Wrong Base)", "high", 100),
        ("Hot Wheels", "Bone Shaker", "1:64", "Error Card (Misprint)", "high", 120),
        ("Hot Wheels", "'55 Chevy Bel Air Gasser", "1:64", "Raw Unpainted Prototype", "grail", 250),
        ("Hot Wheels", "Nissan Skyline GT-R (R34)", "1:64", "ZAMAC Edition", "mid", 45),
        ("Hot Wheels", "Mazda RX-7 (FD)", "1:64", "ZAMAC Edition", "mid", 40),
        # Convention exclusives
        ("Hot Wheels RLC", "'55 Chevy Bel Air Gasser", "1:64", "2024 Nationals Convention", "grail", 280),
        ("Hot Wheels RLC", "Custom Mustang (Spectraflame)", "1:64", "2023 Collectors Convention", "grail", 220),
        ("Hot Wheels RLC", "'69 Dodge Charger R/T", "1:64", "Japan Convention Exclusive", "grail", 250),
        ("Hot Wheels", "Volkswagen T1 Drag Bus", "1:64", "Mexico Convention 2024", "high", 150),
        ("Hot Wheels", "Datsun Bluebird 510", "1:64", "Brazil Convention 2024", "high", 140),
        # Scale variants — 1:64 → 1:43 upgrades
        ("AUTOart", "Toyota AE86 Sprinter Trueno", "1:18", "Initial D Version", "grail", 350),
        ("AUTOart", "Mazda RX-7 (FD) Spirit R", "1:18", "Composite", "high", 280),
        ("AUTOart", "Nissan Skyline GT-R (BNR32)", "1:18", "V-Spec II Composite", "grail", 320),
        ("Kyosho", "Porsche 911 GT3 RS", "1:43", "High-End Resin", "high", 120),
        ("Kyosho", "McLaren Senna", "1:43", "High-End Resin", "high", 130),
        ("Kyosho", "BMW M3 (E30)", "1:43", "High-End Resin", "mid", 90),
        ("Minichamps", "Porsche 911 GT3 RS", "1:43", "Minichamps Street", "high", 100),
        ("Minichamps", "McLaren Senna", "1:43", "Minichamps Street", "high", 110),
        # 1:24 scale variants
        ("Jada Toys", "Nissan Skyline GT-R (R34)", "1:24", "JDM Tuners Series", "standard", 30),
        ("Jada Toys", "Toyota Supra MK4", "1:24", "JDM Tuners Series", "standard", 28),
        ("Jada Toys", "Mazda RX-7 (FD)", "1:24", "JDM Tuners Series", "standard", 28),
        ("Jada Toys", "Honda S2000 AP1", "1:24", "JDM Tuners Series", "standard", 25),
        ("Maisto", "Lamborghini Aventador SVJ", "1:24", "Special Edition", "standard", 22),
        ("Maisto", "Ford GT (2017)", "1:24", "Special Edition", "standard", 20),
        ("Maisto", "Porsche 911 (992) GT3", "1:24", "Special Edition", "standard", 22),
        # Color variants
        ("AUTOart", "Lamborghini Aventador SVJ", "1:18", "Composite Matte Black", "grail", 380),
        ("AUTOart", "Nissan GT-R (R35) Nismo", "1:18", "Composite Brilliant White Pearl", "grail", 310),
        ("AUTOart", "McLaren 720S", "1:18", "Composite Azores Orange", "high", 260),
        ("AUTOart", "Porsche 911 (993) Carrera", "1:18", "Composite Arena Red", "high", 210),
        ("AUTOart", "Ford GT (2017)", "1:18", "Composite Triple Yellow", "high", 210),
        # Tarmac Works / Inno64 premium chase
        ("Tarmac Works", "Nissan Skyline GT-R (R34) V-Spec II", "1:64", "Global64 Chase Green", "high", 95),
        ("Tarmac Works", "Toyota GR Supra (A90)", "1:64", "Global64 Chase Red", "high", 85),
        ("Tarmac Works", "Mitsubishi Lancer Evo VI TME", "1:64", "Global64 Chase Silver", "high", 90),
        ("Inno64", "Honda Civic Type R (EK9)", "1:64", "Chrome Chase", "high", 80),
        ("Inno64", "Nissan Silvia S13 Pandem Rocket Bunny", "1:64", "Chrome Chase", "high", 85),
        ("Inno64", "Toyota Sprinter Trueno AE86", "1:64", "Chrome Chase", "high", 75),
        # M2 Machines chase variants
        ("M2 Machines", "1970 Ford Mustang Boss 302", "1:64", "Raw Chase 1/750", "high", 100),
        ("M2 Machines", "1969 Pontiac GTO Judge", "1:64", "Raw Chase 1/750", "high", 95),
        ("M2 Machines", "1957 Chevrolet Bel Air", "1:64", "Raw Chase 1/750", "high", 90),
        ("M2 Machines", "1971 Plymouth Hemi 'Cuda", "1:64", "Raw Chase 1/750", "high", 105),
        # Johnny Lightning White Lightning chase
        ("Johnny Lightning", "1969 Chevrolet Camaro SS", "1:64", "White Lightning Chase", "high", 70),
        ("Johnny Lightning", "1970 Plymouth Superbird", "1:64", "White Lightning Chase", "high", 80),
        ("Johnny Lightning", "1965 Ford Mustang 2+2", "1:64", "White Lightning Chase", "mid", 55),
        ("Johnny Lightning", "1967 Chevrolet Chevelle SS", "1:64", "White Lightning Chase", "mid", 60),
        # ZAMAC / Chrome finishes
        ("Hot Wheels", "'70 Chevelle SS", "1:64", "ZAMAC Edition 2023", "mid", 35),
        ("Hot Wheels", "Tesla Model S", "1:64", "ZAMAC Edition", "mid", 35),
        ("Hot Wheels", "'69 Dodge Charger R/T", "1:64", "Chrome Finish", "mid", 50),
        ("Hot Wheels", "Porsche 911 GT3 RS", "1:64", "Chrome Finish", "mid", 45),
        # Matchbox scale variants
        ("Matchbox", "No. 75 Ferrari Berlinetta", "1:64", "Superfast Reissue 2024", "mid", 40),
        ("Matchbox", "No. 41 Ford GT40", "1:64", "70th Anniversary Reissue", "mid", 45),
        ("Matchbox", "No. 5 Lotus Europa", "1:64", "Superfast Reissue 2024", "standard", 30),
        # BBR / MR Collection exclusive colors
        ("BBR", "Ferrari SF90 Stradale", "1:18", "Giallo Modena LE 99", "grail", 480),
        ("BBR", "Ferrari 296 GTB", "1:18", "Verde British Racing LE 50", "grail", 520),
        ("MR Collection", "Lamborghini Revuelto", "1:18", "Blu Nethuns LE 49", "grail", 550),
        ("MR Collection", "Bugatti Chiron Sport", "1:18", "Atlantic Blue LE 99", "grail", 480),

        # ── CMC 1:18 Scale ─────────────────────────────────────────────────
        ("CMC", "Mercedes-Benz 300 SLR Uhlenhaut Coupe", "1:18", "CMC Exclusive Silver", "grail", 650),
        ("CMC", "Mercedes-Benz W196 Streamliner", "1:18", "CMC Silver Arrows", "grail", 580),
        ("CMC", "Ferrari 250 GTO 1962 #22 Le Mans", "1:18", "CMC LE 2000", "grail", 520),
        ("CMC", "Maserati 300S 1956 Dirty Hero", "1:18", "CMC Weathered Edition", "grail", 480),
        ("CMC", "Bugatti Type 57 SC Atlantic Coupe", "1:18", "CMC Black", "grail", 600),
        ("CMC", "Auto Union Type C 1937 Rosemeyer", "1:18", "CMC Silver", "grail", 450),
        ("CMC", "Aston Martin DB5 1964 Green", "1:18", "CMC LE 1500", "grail", 520),
        ("CMC", "Alfa Romeo 8C 2900B Speciale 1938", "1:18", "CMC LE 3000", "grail", 480),
        # ── Amalgam 1:18 Scale ─────────────────────────────────────────────
        ("Amalgam", "Ferrari SF90 Stradale", "1:18", "Amalgam Rosso Corsa", "grail", 900),
        ("Amalgam", "McLaren Speedtail", "1:18", "Amalgam Supernova Silver", "grail", 850),
        ("Amalgam", "Bugatti Chiron Pur Sport", "1:18", "Amalgam Agile Blue", "grail", 880),
        ("Amalgam", "Aston Martin Valkyrie", "1:18", "Amalgam Stirling Green", "grail", 820),
        # ── Rally Cars (Ixo / Spark) ───────────────────────────────────────
        ("Ixo", "Lancia Delta HF Integrale 1992 Rally", "1:18", "Ixo Martini Livery", "high", 120),
        ("Ixo", "Subaru Impreza WRC 1997 Safari Rally", "1:18", "Ixo #3 McRae", "high", 110),
        ("Ixo", "Toyota Celica GT-Four ST205 1995", "1:18", "Ixo Castrol Livery", "high", 115),
        ("Ixo", "Ford Escort RS Cosworth 1994 Monte Carlo", "1:18", "Ixo Mobil 1 Livery", "high", 105),
        ("Ixo", "Peugeot 205 T16 1985 Rally Portugal", "1:18", "Ixo Shell Livery", "high", 130),
        ("Ixo", "Audi Quattro S1 1985 San Remo", "1:18", "Ixo HB Livery", "high", 140),
        ("Spark", "Citroen DS3 WRC 2012 Monte Carlo", "1:43", "Spark Red Bull Livery", "mid", 55),
        ("Spark", "Hyundai i20 WRC 2020 Tanak", "1:43", "Spark Shell Livery", "mid", 50),
        ("Spark", "Toyota Yaris WRC 2021 Ogier", "1:43", "Spark Gazoo Racing", "mid", 55),
        ("Spark", "Ford Puma Rally1 2022 Loeb", "1:43", "Spark Red Bull Livery", "mid", 50),
        # ── Truck / Construction (Tonkin, WSI, NZG) ────────────────────────
        ("Tonkin", "Kenworth W900L Day Cab", "1:53", "Tonkin Red Metallic", "high", 120),
        ("Tonkin", "Peterbilt 389 Sleeper Cab", "1:53", "Tonkin Chrome Edition", "high", 130),
        ("Tonkin", "Freightliner Cascadia Evolution", "1:53", "Tonkin White", "mid", 90),
        ("WSI", "Scania S Highline 6x2 + Reefer", "1:50", "WSI Transport Livery", "high", 180),
        ("WSI", "Volvo FH5 Globetrotter XL", "1:50", "WSI Premium Line", "high", 165),
        ("WSI", "DAF XG+ 4x2 + Curtainside", "1:50", "WSI Blue Edition", "high", 155),
        ("WSI", "MAN TGX GX 4x2 Tractor", "1:50", "WSI Red", "mid", 95),
        ("NZG", "Liebherr LTM 1300-6.2 Mobile Crane", "1:50", "NZG Yellow", "grail", 450),
        ("NZG", "Liebherr R 9800 Mining Excavator", "1:50", "NZG White/Red", "grail", 380),
        ("NZG", "CAT 390F L Hydraulic Excavator", "1:50", "NZG CAT Yellow", "high", 180),
        ("NZG", "CAT D11T Track-Type Tractor", "1:50", "NZG CAT Yellow", "high", 200),
        ("NZG", "Liebherr LR 1600/2 Crawler Crane", "1:50", "NZG Yellow", "grail", 500),
        # ── Motorcycle Diecast (Minichamps MotoGP) ─────────────────────────
        ("Minichamps", "Yamaha YZR-M1 Rossi 2004 Laguna Seca", "1:12", "Minichamps MotoGP", "high", 150),
        ("Minichamps", "Ducati Desmosedici GP20 Dovizioso", "1:12", "Minichamps MotoGP", "high", 130),
        ("Minichamps", "Honda RC213V Marquez 2019", "1:12", "Minichamps MotoGP", "high", 140),
        ("Minichamps", "Yamaha YZR-M1 Rossi 2009 Barcelona", "1:12", "Minichamps LE", "grail", 220),
        ("Minichamps", "Ducati 916 Carl Fogarty WSB 1994", "1:12", "Minichamps SBK", "high", 160),
        ("Minichamps", "Aprilia RSV4 2021 Espargaro", "1:12", "Minichamps MotoGP", "high", 120),
        ("Minichamps", "KTM RC16 Brad Binder 2021", "1:12", "Minichamps MotoGP", "mid", 95),
        ("Minichamps", "Suzuki GSX-RR Joan Mir 2020 Champion", "1:12", "Minichamps MotoGP LE", "high", 180),
        # ── Vintage Matchbox / Corgi ───────────────────────────────────────
        ("Matchbox", "No. 1 Road Roller", "1:64", "Lesney Regular Wheels (1953)", "high", 120),
        ("Matchbox", "No. 9 Fire Engine", "1:64", "Lesney Regular Wheels (1955)", "high", 100),
        ("Matchbox", "No. 20 ERF Stake Truck", "1:64", "Lesney Regular Wheels (1956)", "high", 85),
        ("Matchbox", "No. 32 Jaguar XK140", "1:64", "Lesney Regular Wheels (1957)", "high", 110),
        ("Matchbox", "No. 36 Austin A50", "1:64", "Lesney Regular Wheels (1957)", "high", 95),
        ("Matchbox", "No. 52 Maserati 4CLT", "1:64", "Lesney Regular Wheels (1958)", "high", 130),
        ("Matchbox", "No. 65 Jaguar 3.4 Litre", "1:64", "Lesney Regular Wheels (1959)", "high", 105),
        ("Matchbox", "No. 74 Mobile Refreshment Bar", "1:64", "Lesney Regular Wheels (1959)", "high", 90),
        ("Corgi", "No. 261 James Bond Aston Martin DB5", "1:43", "Corgi Original (1965)", "grail", 250),
        ("Corgi", "No. 267 Batmobile", "1:43", "Corgi Original (1966)", "grail", 300),
        ("Corgi", "No. 497 Man From U.N.C.L.E. Oldsmobile", "1:43", "Corgi Original (1966)", "grail", 220),
        ("Corgi", "No. 270 James Bond Aston Martin DB5 (Gold)", "1:43", "Corgi Reissue (1968)", "high", 180),
        ("Corgi", "No. 336 James Bond Toyota 2000GT", "1:43", "Corgi Original (1967)", "grail", 280),
        ("Corgi", "No. 320 The Saint Volvo P1800", "1:43", "Corgi Original (1965)", "high", 160),
        ("Corgi", "No. 441 Volkswagen Toblerone Van", "1:43", "Corgi Original (1963)", "high", 140),
        ("Corgi", "Gift Set 36 Tarzan Set", "1:43", "Corgi Original (1976)", "grail", 350),

        # ── Additional Rally / Race (Spark, Ixo) ──────────────────────────
        ("Spark", "Porsche 911 RSR Le Mans 2023 #91", "1:43", "Spark Le Mans Winner", "mid", 60),
        ("Spark", "Toyota GR010 Hybrid Le Mans 2023 #8", "1:43", "Spark Le Mans Winner", "mid", 65),
        ("Spark", "Alpine A480 Le Mans 2022 #36", "1:43", "Spark LMP1 Hypercar", "mid", 55),
        ("Spark", "Ferrari 499P Le Mans 2023 #50", "1:43", "Spark Le Mans Winner", "high", 75),
        ("Spark", "Cadillac V-Series.R Le Mans 2023 #2", "1:43", "Spark LMDh", "mid", 60),
        ("Ixo", "Mitsubishi Lancer Evo VI Rally 1999", "1:43", "Ixo WRC Champion Makinen", "mid", 45),
        ("Ixo", "Citroen Xsara WRC 2004 Loeb", "1:43", "Ixo WRC Champion", "mid", 42),
        ("Ixo", "Skoda Fabia R5 Rally 2019", "1:43", "Ixo WRC2", "standard", 35),

        # ── Bburago Premium/Signature ──────────────────────────────────────
        ("Bburago", "Ferrari Monza SP1", "1:18", "Bburago Signature", "mid", 65),
        ("Bburago", "Lamborghini Sian FKP 37", "1:18", "Bburago Signature", "mid", 60),
        ("Bburago", "Bugatti Bolide", "1:18", "Bburago Signature", "mid", 65),
        ("Bburago", "Porsche 911 GT3 RS (992)", "1:18", "Bburago Signature White", "mid", 55),
        ("Bburago", "Alfa Romeo Giulia GTA", "1:18", "Bburago Signature", "mid", 50),
        ("Bburago", "Ferrari SF90 Spider", "1:18", "Bburago Race & Play", "standard", 35),

        # ── Maisto Premium / Design ────────────────────────────────────────
        ("Maisto", "Ford GT (2017)", "1:18", "Maisto Exclusive Style", "mid", 45),
        ("Maisto", "Lamborghini Centenario LP770-4", "1:18", "Maisto Exclusive", "mid", 48),
        ("Maisto", "Mercedes-AMG GT R", "1:18", "Maisto Exclusive", "mid", 42),
        ("Maisto", "Ducati Panigale V4 S Corse", "1:18", "Maisto Design", "standard", 30),
        ("Maisto", "BMW S1000RR", "1:12", "Maisto Assembly Line", "standard", 25),

        # ── More 1:64 Hot Wheels Premium ───────────────────────────────────
        ("Hot Wheels", "Nissan Skyline GT-R (BNR34)", "1:64", "Hot Wheels Premium Boulevard", "mid", 15),
        ("Hot Wheels", "Toyota AE86 Sprinter Trueno", "1:64", "Hot Wheels Premium Japan Historics", "mid", 18),
        ("Hot Wheels", "Mazda RX-7 FD3S", "1:64", "Hot Wheels Premium Japan Historics", "mid", 16),
        ("Hot Wheels", "Porsche 964 RWB RAUH-Welt", "1:64", "Hot Wheels Premium Car Culture", "mid", 15),
        ("Hot Wheels", "Datsun 510 Bluebird", "1:64", "Hot Wheels Premium Japan Historics", "mid", 20),
        ("Hot Wheels", "Land Rover Defender 110", "1:64", "Hot Wheels Premium Boulevard", "standard", 12),
        ("Hot Wheels", "Mercedes-Benz 300 SL Gullwing", "1:64", "Hot Wheels Premium Boulevard", "mid", 15),
        ("Hot Wheels", "Lancia 037 Rally", "1:64", "Hot Wheels Premium Rally Legends", "mid", 18),
        ("Hot Wheels", "RLC Exclusive Pink Party Car 2024", "1:64", "HW RLC Convention Exclusive", "grail", 120),
        ("Hot Wheels", "RLC Exclusive Chrome Camaro SS 2024", "1:64", "HW RLC Members Exclusive", "high", 80),

        # ── Mini GT ───────────────────────────────────────────────────────
        ("Mini GT", "Porsche 911 (992) GT3 RS White", "1:64", "Mini GT #596", "standard", 15),
        ("Mini GT", "Lamborghini Revuelto Verde Selvans", "1:64", "Mini GT #642", "standard", 16),
        ("Mini GT", "BMW M3 Competition G80 Isle of Man Green", "1:64", "Mini GT #549", "standard", 14),
        ("Mini GT", "Nissan Skyline GT-R R34 V-Spec II Nur", "1:64", "Mini GT #602 Millennium Jade", "mid", 22),
        ("Mini GT", "Toyota GR Supra A90 HKS", "1:64", "Mini GT #522", "standard", 14),
        ("Mini GT", "McLaren Senna GTR Orange/White", "1:64", "Mini GT #480", "standard", 15),
        ("Mini GT", "Pagani Huayra R Blu Tricolore", "1:64", "Mini GT #638", "standard", 16),

        # ── Tarmac Works 1:64 ──────────────────────────────────────────────
        ("Tarmac Works", "Mercedes-AMG GT3 Evo CRAFT-BAMBOO", "1:64", "Tarmac Works LE", "mid", 22),
        ("Tarmac Works", "Honda Civic Type R FK8 SUPER GT", "1:64", "Tarmac Works SUPER GT", "mid", 20),
        ("Tarmac Works", "Porsche 911 GT3 R Nurburgring 2022", "1:64", "Tarmac Works LE", "mid", 22),
        ("Tarmac Works", "Toyota GR Supra GT4 Gazoo Racing", "1:64", "Tarmac Works Hobby64", "standard", 15),
        ("Tarmac Works", "Audi R8 LMS GT3 Evo II Macau", "1:64", "Tarmac Works Macau GP", "mid", 20),
        # ── Inno64 Premium ─────────────────────────────────────────────────
        ("Inno64", "Nissan Skyline GT-R R32 Pandem Rocket Bunny", "1:64", "Inno64 LE", "mid", 18),
        ("Inno64", "Toyota Sprinter Trueno AE86 TRD", "1:64", "Inno64 LE", "mid", 16),
        ("Inno64", "Honda Civic EF9 OSAKA JDM", "1:64", "Inno64 Japan Edition", "mid", 18),
        ("Inno64", "Mitsubishi Lancer Evo III Ralliart", "1:64", "Inno64 LE", "mid", 16),
        ("Inno64", "Nissan Silvia S13 Pandem V3", "1:64", "Inno64 LE", "mid", 18),
        # ── Kyosho 1:64 ───────────────────────────────────────────────────
        ("Kyosho", "Lamborghini Aventador SVJ Green", "1:64", "Kyosho MiniCar Collection", "standard", 15),
        ("Kyosho", "Ferrari F8 Tributo Rosso Corsa", "1:64", "Kyosho MiniCar Collection", "standard", 14),
        ("Kyosho", "Porsche 911 Turbo S (992) Ice Grey", "1:64", "Kyosho MiniCar Collection", "standard", 15),
        ("Kyosho", "Honda NSX (NA2) Type R White", "1:64", "Kyosho JDM Series 2", "standard", 15),
        ("Kyosho", "Mazda RX-7 Spirit R FD3S Red", "1:64", "Kyosho JDM Series 2", "standard", 15),
        # ── Schuco / SIKU (German) ─────────────────────────────────────────
        ("Schuco", "Porsche 356A Coupe 1955 Blue", "1:18", "Schuco ProR18", "high", 150),
        ("Schuco", "VW Beetle Brezelkafer 1951 Green", "1:18", "Schuco ProR18", "high", 140),
        ("Schuco", "BMW Isetta 250 Red/White", "1:18", "Schuco ProR18", "high", 120),
        ("SIKU", "Liebherr R 9800 Mining Excavator", "1:87", "SIKU Super Series", "mid", 45),
        ("SIKU", "Scania R620 Topline with Low Loader", "1:50", "SIKU Super Series", "mid", 55),

        # ── Star Trek Die-Cast Ships (10) ────────────────────────────────────
        ("Eaglemoss", "Star Trek USS Enterprise NCC-1701 (TOS)", "1:1400", "Eaglemoss XL Edition", "high", 120),
        ("Eaglemoss", "Star Trek USS Enterprise NCC-1701-D (TNG)", "1:1400", "Eaglemoss XL Edition", "high", 120),
        ("Eaglemoss", "Star Trek Klingon Bird of Prey", "1:1400", "Eaglemoss XL Edition", "high", 100),
        ("Eaglemoss", "Star Trek Romulan Warbird", "1:1400", "Eaglemoss XL Edition", "high", 100),
        ("Eaglemoss", "Star Trek Borg Cube", "1:1400", "Eaglemoss XL Edition", "high", 130),
        ("Eaglemoss", "Star Trek USS Defiant NX-74205", "1:1400", "Eaglemoss XL Edition", "mid", 90),
        ("Eaglemoss", "Star Trek USS Voyager NCC-74656", "1:1400", "Eaglemoss XL Edition", "mid", 90),
        ("Hot Wheels", "Star Trek USS Enterprise NCC-1701 (2009 Film)", "1:64", "SDCC 2009 Exclusive", "high", 150),
        ("Corgi", "Star Trek USS Enterprise NCC-1701 (Vintage)", "1:600", "Corgi Classics", "high", 180),
        ("Johnny Lightning", "Star Trek Enterprise NCC-1701 (White Lightning Chase)", "1:64", "Johnny Lightning Legends", "high", 100),

        # ── Hot Wheels RLC (additional) ───────────────────────────────────
        ("Hot Wheels RLC", "Custom '69 Volkswagen Squareback", "1:64", "RLC Exclusive 2024", "high", 130),
        ("Hot Wheels RLC", "'70 Dodge Hemi Challenger", "1:64", "RLC Exclusive 2024", "high", 140),
        ("Hot Wheels RLC", "Datsun 240Z (Street Tuner)", "1:64", "RLC Exclusive 2024", "high", 160),
        ("Hot Wheels RLC", "Nissan Laurel SGX (C130)", "1:64", "RLC Exclusive 2023", "high", 145),
        ("Hot Wheels RLC", "'73 BMW 3.0 CSL Race Car", "1:64", "RLC Exclusive 2023", "grail", 180),
        ("Hot Wheels RLC", "Porsche 964 Singer", "1:64", "RLC Exclusive 2024", "grail", 200),
        ("Hot Wheels RLC", "Toyota Land Cruiser FJ40", "1:64", "RLC Exclusive 2024", "high", 120),
        ("Hot Wheels RLC", "Mazda REPU Pickup", "1:64", "RLC Exclusive 2023", "high", 130),
        ("Hot Wheels RLC", "'82 Lamborghini Countach LP500 S", "1:64", "RLC Exclusive 2024", "grail", 200),
        ("Hot Wheels RLC", "'55 Chevy Bel Air Gasser (Chrome)", "1:64", "RLC Exclusive 2024", "grail", 180),

        # ── Tomica Limited Vintage Neo (JDM) ─────────────────────────────
        ("Tomica", "Nissan Skyline GT-R (KPGC10) Green", "1:64", "TLV Neo LV-N214a", "mid", 35),
        ("Tomica", "Nissan Skyline GT-R (BNR32) White", "1:64", "TLV Neo LV-N213b", "mid", 32),
        ("Tomica", "Nissan Skyline GT-R (BCNR33) Purple", "1:64", "TLV Neo LV-N217c", "mid", 30),
        ("Tomica", "Nissan Skyline GT-R (BNR34) V-Spec II Bayside Blue", "1:64", "TLV Neo LV-N217a", "mid", 45),
        ("Tomica", "Toyota Supra RZ (A80) White", "1:64", "TLV Neo LV-N232a", "mid", 38),
        ("Tomica", "Toyota Supra RZ (A80) Black", "1:64", "TLV Neo LV-N232b", "mid", 38),
        ("Tomica", "Mazda RX-7 (FD3S) Type RS Red", "1:64", "TLV Neo LV-N267a", "mid", 35),
        ("Tomica", "Mazda RX-7 (FC3S) Savanna Silver", "1:64", "TLV Neo LV-N192a", "mid", 30),
        ("Tomica", "Toyota Sprinter Trueno AE86 (Initial D)", "1:64", "TLV Neo LV-N235", "mid", 50),
        ("Tomica", "Nissan Silvia (S13) K's White", "1:64", "TLV Neo LV-N235c", "mid", 30),
        ("Tomica", "Nissan 180SX Type II (RPS13)", "1:64", "TLV Neo LV-N235d", "mid", 28),
        ("Tomica", "Honda NSX (NA1) Type R Red", "1:64", "TLV Neo LV-N228a", "mid", 42),
        ("Tomica", "Honda Civic Type R (EK9) White", "1:64", "TLV Neo LV-N256a", "mid", 35),
        ("Tomica", "Mitsubishi Lancer Evo VI GSR (Tommi Makinen)", "1:64", "TLV Neo LV-N190a", "mid", 40),
        ("Tomica", "Subaru Impreza WRX STi (GC8) Blue", "1:64", "TLV Neo LV-N218b", "mid", 38),
        ("Tomica", "Nissan Fairlady Z (S30) Orange", "1:64", "TLV Neo LV-N41d", "mid", 32),

        # ── 1:18 Premium (additional) ────────────────────────────────────
        ("AUTOart", "Lexus LFA (Nurburgring Package)", "1:18", "Composite", "grail", 400),
        ("AUTOart", "Nissan Skyline GT-R (KPGC10) Hakosuka", "1:18", "Composite", "grail", 350),
        ("AUTOart", "Porsche 911 (991.2) GT2 RS Weissach", "1:18", "Composite", "grail", 380),
        ("AUTOart", "Honda NSX (NA1) Type R Red", "1:18", "Composite", "high", 250),
        ("AUTOart", "DeLorean DMC-12 (Back to the Future)", "1:18", "Composite", "high", 200),
        ("CMC", "Ferrari 250 GTO (1962) Red", "1:18", "CMC Premium", "grail", 600),
        ("CMC", "Mercedes-Benz W196 Streamliner", "1:18", "CMC Premium", "grail", 550),
        ("CMC", "Bugatti Type 57 SC Atlantic", "1:18", "CMC Premium", "grail", 700),
        ("CMC", "Maserati Tipo 61 Birdcage #66", "1:18", "CMC Premium", "grail", 500),
        ("Amalgam", "Ferrari F40 (1:18 Resin)", "1:18", "Amalgam Resin", "grail", 900),
        ("Amalgam", "McLaren F1 (1:18 Resin)", "1:18", "Amalgam Resin", "grail", 1000),
        ("BBR", "Ferrari 296 GTB Rosso Corsa", "1:18", "BBR Premium", "grail", 400),
        ("BBR", "Ferrari SF90 Stradale Rosso Corsa", "1:18", "BBR Premium", "grail", 380),

        # ── Matchbox 70th Anniversary & Special ──────────────────────────
        ("Matchbox", "1962 Volkswagen Beetle (70th Anniversary)", "1:64", "70th Anniversary LE", "mid", 25),
        ("Matchbox", "1971 MGB GT Coupe (70th Anniversary)", "1:64", "70th Anniversary LE", "mid", 22),
        ("Matchbox", "1964 Austin Mini Cooper S (70th Anniversary)", "1:64", "70th Anniversary LE", "mid", 22),
        ("Matchbox", "Land Rover Defender 110 (70th Anniversary)", "1:64", "70th Anniversary LE", "mid", 25),
        ("Matchbox", "Tesla Roadster 2020 (Moving Parts)", "1:64", "Matchbox Moving Parts", "standard", 8),
        ("Matchbox", "Ford Bronco (2021, Moving Parts)", "1:64", "Matchbox Moving Parts", "standard", 8),

        # ── Hot Wheels Convention Exclusives ──────────────────────────────
        ("Hot Wheels", "Japan Convention '67 Camaro (2024)", "1:64", "HW Japan Convention Exclusive", "grail", 200),
        ("Hot Wheels", "Mexico Convention Datsun 620 (2024)", "1:64", "HW Mexico Convention Exclusive", "grail", 180),
        ("Hot Wheels", "Indonesia Convention VW Drag Bus (2024)", "1:64", "HW Indonesia Convention Exclusive", "grail", 250),
        ("Hot Wheels", "Nationals Convention '69 Mustang Boss 302 (2024)", "1:64", "HW Nationals Exclusive", "grail", 300),
        ("Hot Wheels", "Collectors Convention Volkswagen T1 Panel (2024)", "1:64", "HW Convention Exclusive", "grail", 220),
        ("Hot Wheels", "Brazil Convention VW Kombi (2024)", "1:64", "HW Brazil Convention Exclusive", "grail", 200),

        # ── Tarmac Works & INNO64 (JDM Racing, additional) ───────────────
        ("Tarmac Works", "Toyota AE86 Corolla Levin Initial D", "1:64", "Tarmac Works Hobby64", "mid", 25),
        ("Tarmac Works", "Nissan Skyline GT-R R34 Nismo S-tune", "1:64", "Tarmac Works LE", "mid", 25),
        ("Tarmac Works", "Mitsubishi Lancer Evo VI TME Rally", "1:64", "Tarmac Works Rally", "mid", 22),
        ("Tarmac Works", "Toyota Supra A80 JZA80 TRD (Tarmac)", "1:64", "Tarmac Works Hobby64", "mid", 22),
        ("Tarmac Works", "Honda Civic Type R FK8 Time Attack", "1:64", "Tarmac Works LE", "mid", 20),
        ("Inno64", "Honda S2000 AP1 Mugen GP", "1:64", "Inno64 LE", "mid", 20),
        ("Inno64", "Nissan Silvia S15 Rocket Bunny", "1:64", "Inno64 LE", "mid", 20),
        ("Inno64", "Mazda MX-5 (NA) Eunos Roadster", "1:64", "Inno64 LE", "mid", 18),
        ("Inno64", "Toyota AE86 Sprinter Trueno (Drift King)", "1:64", "Inno64 LE", "mid", 18),

        # ── Kyosho 1:64 (additional) ─────────────────────────────────────
        ("Kyosho", "Toyota AE86 Sprinter Trueno White/Black", "1:64", "Kyosho JDM Series 3", "standard", 15),
        ("Kyosho", "Nissan Skyline GT-R R32 Gunmetal Grey", "1:64", "Kyosho JDM Series 3", "standard", 15),
        ("Kyosho", "Nissan Fairlady Z (RZ34) Seiran Blue", "1:64", "Kyosho JDM Series 3", "standard", 15),
        ("Kyosho", "Subaru Impreza 22B STi Blue", "1:64", "Kyosho JDM Series 3", "mid", 20),
        ("Kyosho", "Porsche 911 GT3 (992) Racing Yellow", "1:64", "Kyosho MiniCar Collection", "standard", 15),
        ("Kyosho", "Ferrari 488 GTB Rosso Corsa", "1:64", "Kyosho MiniCar Collection", "standard", 14),

        # ── More Hot Wheels Super Treasure Hunts ($TH) ────────────────────
        ("Hot Wheels $TH", "Ford GT (2024 $TH)", "1:64", "Super Treasure Hunt 2024", "high", 80),
        ("Hot Wheels $TH", "Pagani Huayra (2024 $TH)", "1:64", "Super Treasure Hunt 2024", "mid", 65),
        ("Hot Wheels $TH", "Nissan 300ZX (Z32) (2024 $TH)", "1:64", "Super Treasure Hunt 2024", "mid", 60),
        ("Hot Wheels $TH", "Toyota Supra A80 (2025 $TH)", "1:64", "Super Treasure Hunt 2025", "high", 90),
        ("Hot Wheels $TH", "Lamborghini Countach LPI 800-4 (2025 $TH)", "1:64", "Super Treasure Hunt 2025", "high", 85),
        ("Hot Wheels $TH", "Corvette C8 Z06 (2025 $TH)", "1:64", "Super Treasure Hunt 2025", "mid", 60),
        ("Hot Wheels $TH", "BMW M4 CSL (2025 $TH)", "1:64", "Super Treasure Hunt 2025", "mid", 55),

        # ── Hot Wheels RLC (Red Line Club — additional) ─────────────────
        ("Hot Wheels RLC", "'70 Dodge Challenger (Spectraflame Green)", "1:64", "RLC Exclusive 2024 Spectraflame", "grail", 220),
        ("Hot Wheels RLC", "BMW 507 (Spectraflame Light Blue)", "1:64", "RLC Exclusive 2024 Spectraflame", "high", 150),
        ("Hot Wheels RLC", "'67 Camaro (Spectraflame Red)", "1:64", "RLC Exclusive Membership Car 2024", "high", 130),
        ("Hot Wheels RLC", "McLaren F1 GTR (Spectraflame Orange)", "1:64", "RLC Exclusive 2024", "grail", 250),
        ("Hot Wheels RLC", "Nissan Skyline GT-R (R33) (Spectraflame Purple)", "1:64", "RLC Exclusive 2024", "grail", 200),
        ("Hot Wheels RLC", "'55 Bel Air Gasser (Convention Exclusive 2024)", "1:64", "Convention Exclusive", "grail", 300),
        ("Hot Wheels RLC", "Porsche 911 GT3 RS (RLC Membership 2025)", "1:64", "RLC Membership Car 2025", "high", 120),
        ("Hot Wheels RLC", "Ford GT40 (Spectraflame Gold)", "1:64", "RLC Exclusive 2025", "grail", 230),
        ("Hot Wheels RLC", "'71 Plymouth GTX (Convention Exclusive 2025)", "1:64", "Convention Exclusive", "grail", 280),

        # ── Tomica Limited Vintage Neo (additional) ─────────────────────
        ("Tomica LV-N", "Nissan Skyline GT-R R32 V-Spec (White)", "1:64", "Tomica LV-N234a", "mid", 45),
        ("Tomica LV-N", "Nissan Skyline GT-R R32 V-Spec II (Gun Grey)", "1:64", "Tomica LV-N234b", "mid", 50),
        ("Tomica LV-N", "Nissan Skyline GT-R R33 V-Spec (Midnight Purple)", "1:64", "Tomica LV-N235a", "high", 65),
        ("Tomica LV-N", "Nissan Skyline GT-R R33 V-Spec (Sonic Silver)", "1:64", "Tomica LV-N235b", "mid", 50),
        ("Tomica LV-N", "Nissan Skyline GT-R R34 V-Spec II Nür (Millenium Jade)", "1:64", "Tomica LV-N236a", "high", 80),
        ("Tomica LV-N", "Toyota Supra RZ (A70) White", "1:64", "Tomica LV-N237a", "mid", 45),
        ("Tomica LV-N", "Toyota Supra RZ (A80) Silver", "1:64", "Tomica LV-N237b", "high", 60),
        ("Tomica LV-N", "Toyota GR Supra (A90) Prominence Red", "1:64", "Tomica LV-N237c", "mid", 40),
        ("Tomica LV-N", "Mazda RX-7 FC3S Infini (Crystal White)", "1:64", "Tomica LV-N238a", "mid", 50),
        ("Tomica LV-N", "Mazda RX-7 FD3S Type RS (Brilliant Black)", "1:64", "Tomica LV-N238b", "high", 65),
        ("Tomica LV-N", "Mazda RX-7 FD3S Spirit R Type A (Titanium Grey)", "1:64", "Tomica LV-N238c", "high", 75),
        ("Tomica LV-N", "Honda NSX (NA1) Type R (Championship White)", "1:64", "Tomica LV-N239a", "high", 70),
        ("Tomica LV-N", "Honda NSX (NA2) Type S (New Formula Red)", "1:64", "Tomica LV-N239b", "high", 65),

        # ── AUTOart 1:18 (latest releases) ─────────────────────────────
        ("AUTOart", "Nissan Skyline GT-R R34 V-Spec II Nür (Millenium Jade)", "1:18", "AUTOart 77408", "grail", 350),
        ("AUTOart", "Toyota 2000GT (White)", "1:18", "AUTOart 78754", "high", 280),
        ("AUTOart", "Lamborghini Countach LPI 800-4 (Bianco Siderale)", "1:18", "AUTOart 79244", "high", 250),
        ("AUTOart", "Porsche 911 (992) GT3 RS (Weissach Package)", "1:18", "AUTOart 78165", "high", 280),
        ("AUTOart", "McLaren 720S (Glacier White)", "1:18", "AUTOart 76074", "high", 240),
        ("AUTOart", "Ford GT (2017) (Liquid Blue)", "1:18", "AUTOart 72944", "high", 260),
        ("AUTOart", "Koenigsegg Agera RS (Naraya)", "1:18", "AUTOart 79024", "grail", 400),

        # ── Mini GT Chase / Raw Cars ────────────────────────────────────
        ("Mini GT", "Nissan Skyline GT-R R34 V-Spec (Chase)", "1:64", "Mini GT #589 Chase", "mid", 45),
        ("Mini GT", "Porsche 911 (992) GT3 (Chase)", "1:64", "Mini GT #630 Chase", "mid", 40),
        ("Mini GT", "Lamborghini Huracán STO (Chase)", "1:64", "Mini GT #523 Chase", "mid", 35),
        ("Mini GT", "Toyota Supra GR A90 (Raw)", "1:64", "Mini GT Raw Zamac", "mid", 50),
        ("Mini GT", "Bugatti Chiron Pur Sport (Chase)", "1:64", "Mini GT #428 Chase", "mid", 45),
        ("Mini GT", "McLaren Senna (Raw)", "1:64", "Mini GT Raw Zamac", "mid", 55),
        ("Mini GT", "Ford GT MkII (Chase)", "1:64", "Mini GT #297 Chase", "mid", 40),

        # ── Tarmac Works Racing Liveries ────────────────────────────────
        ("Tarmac Works", "Mercedes-AMG GT3 Evo Craft-Bamboo #77", "1:64", "Tarmac Works GT Cup", "mid", 30),
        ("Tarmac Works", "Porsche 911 GT3 R (992) Martini Racing", "1:64", "Tarmac Works Hobby64", "mid", 35),
        ("Tarmac Works", "Nissan GT-R Nismo GT3 KONDO Racing", "1:64", "Tarmac Works Super GT", "mid", 30),
        ("Tarmac Works", "BMW M4 GT3 Turner Motorsport", "1:64", "Tarmac Works Hobby64", "mid", 28),
        ("Tarmac Works", "Toyota GR Supra GT4 Rookie Racing", "1:64", "Tarmac Works Super GT", "standard", 25),
        ("Tarmac Works", "Audi R8 LMS GT3 Evo II Audi Sport", "1:64", "Tarmac Works GT Cup", "mid", 30),
        ("Tarmac Works", "Honda Civic Type R FK8 BTCC Champion", "1:64", "Tarmac Works Hobby64", "mid", 28),
    ]
    catalog = []
    for brand, name, scale, variant, tier, price in variants:
        catalog.append({
            "brand": brand,
            "name": name,
            "scale": scale,
            "variant": variant,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    brand = item["brand"]
    name = item["name"]
    scale = item["scale"]
    variant = item["variant"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{brand}-{name}-{variant}"),
        title=f"{name} ({scale})",
        set_code=brand.lower().replace(" ", "-").replace("$", "sth"),
        brand=brand.split(" $")[0] if "$" in brand else brand,
        rarity=item["rarity_tier"].title(),
        notes=f"{brand} | {scale} | {variant}",
        attributes_json={
            "brand": brand,
            "scale": scale,
            "variant": variant,
            "is_chase": "chase" in variant.lower() or "$th" in brand.lower(),
            "is_vintage": "vintage" in variant.lower() or "lesney" in variant.lower(),
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]
    is_limited = any(kw in item["variant"].lower() for kw in ["exclusive", "chase", "treasure hunt", "limited"])

    return PriceObservation(
        features={
            "condition_score": 0.9,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": 0.85 if is_limited else 0.4,
            "is_chase": 1.0 if "chase" in item["variant"].lower() or "$th" in item["brand"].lower() else 0.0,
            "is_vintage": 1.0 if "vintage" in item["variant"].lower() or "lesney" in item["variant"].lower() else 0.0,
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import diecast vehicles catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Diecast Import ===")

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

    logger.info(f"\n=== Diecast Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
