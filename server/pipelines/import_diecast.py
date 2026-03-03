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
    return catalog


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
