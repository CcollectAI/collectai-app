"""
Curated Watch Import Pipeline — Luxury, Vintage & Affordable Timepieces.

Imports a curated catalog of 310+ watches across 30 subcategories:
  Rolex, Omega, Seiko, Grand Seiko, Tudor, Casio/G-Shock, Patek Philippe,
  Audemars Piguet, Affordable Collectibles, Independent/Micro Brands,
  Vintage Icons, Vacheron Constantin, Cartier, A. Lange & Sohne,
  IWC, Breitling, Jaeger-LeCoultre, Timex, Zenith, Panerai,
  Richard Mille, F.P. Journe, MB&F, H. Moser & Cie, Swatch MoonSwatch,
  G-Shock Limited Collabs, Breguet

Each entry has a real reference number, movement type, case material,
watch type classification, and realistic EUR secondary market price.

Pattern follows import_books_isbn.py (get_curated_catalog, _watch_to_catalog_item,
_watch_to_price_observation).

Usage:
    python -m pipelines.import_watches [--dry-run] [--jsonl-only] [--cache-images]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines.import_common import (
    CatalogItem,
    PriceObservation,
    SupabaseIngest,
    write_training_jsonl,
    write_catalog_sql,
    cache_catalog_images,
    log_progress,
    slugify,
    logger,
    close_http_client,
)

CATEGORY = "watches"

# ---------------------------------------------------------------------------
# Watch-type collectibility scores
# ---------------------------------------------------------------------------
WATCH_TYPE_SCORES: dict[str, float] = {
    "Vintage Pre-1970": 0.95,
    "Discontinued Classic": 0.85,
    "Limited Edition": 0.90,
    "Current Production": 0.40,
    "Special Edition": 0.75,
    "Anniversary Edition": 0.80,
    "Prototype/Unique": 0.99,
    "Military Issue": 0.85,
    "Full Set (Box + Papers)": 0.10,  # bonus, added on top
}

# ---------------------------------------------------------------------------
# Condition scores (watch-specific grading)
# ---------------------------------------------------------------------------
CONDITION_SCORES: dict[str, float] = {
    "BNIB (Brand New In Box)": 1.0,
    "Unworn": 0.95,
    "Excellent": 0.85,
    "Very Good": 0.70,
    "Good": 0.55,
    "Fair": 0.35,
    "Poor": 0.15,
    "Serviced": 0.80,
}

# ---------------------------------------------------------------------------
# Brand tier scoring for ML features
# ---------------------------------------------------------------------------
BRAND_TIER: dict[str, float] = {
    # Luxury (0.9)
    "Rolex": 0.9,
    "Patek Philippe": 0.9,
    "Audemars Piguet": 0.9,
    "A. Lange & Sohne": 0.9,
    "Vacheron Constantin": 0.9,
    "Cartier": 0.9,
    # Premium (0.7)
    "Omega": 0.7,
    "Tudor": 0.7,
    "Grand Seiko": 0.7,
    "IWC": 0.7,
    "Jaeger-LeCoultre": 0.7,
    "Zenith": 0.7,
    "Breitling": 0.7,
    "H. Moser & Cie": 0.7,
    "Panerai": 0.7,
    # Mid (0.5)
    "Nomos": 0.5,
    "Sinn": 0.5,
    "Junghans": 0.5,
    "Longines": 0.5,
    "Oris": 0.5,
    "Christopher Ward": 0.5,
    "Baltic": 0.5,
    "Ming": 0.5,
    "Seiko": 0.5,
    "Marathon": 0.5,
    "Universal Geneve": 0.5,
    "Heuer": 0.5,
    # Affordable (0.3)
    "Casio": 0.3,
    "G-Shock": 0.3,
    "Tissot": 0.3,
    "Hamilton": 0.3,
    "Orient": 0.3,
    "Swatch": 0.3,
    "Timex": 0.3,
    "Citizen": 0.3,
    "Seagull": 0.3,
    "Vostok": 0.3,
    # Ultra-luxury (0.95)
    "Richard Mille": 0.95,
    "F.P. Journe": 0.95,
    "MB&F": 0.95,
    "Breguet": 0.9,
    # Microbrands (0.35)
    "Lorier": 0.35,
    "Halios": 0.35,
    "Zelos": 0.35,
    "Squale": 0.35,
    "Steinhart": 0.35,
    "Dan Henry": 0.35,
    "Boldr": 0.30,
    "Brew": 0.30,
    # Budget Icons (0.3)
    "Bulova": 0.3,
    "Luminox": 0.3,
    "Glycine": 0.35,
    "Invicta": 0.2,
    # Japanese Affordable (0.4-0.6)
    "Kurono Tokyo": 0.6,
    "Orient Star": 0.4,
    "Minase": 0.55,
    # German Value (0.4-0.5)
    "Stowa": 0.45,
    "Laco": 0.4,
    "Junkers": 0.35,
    "MeisterSinger": 0.45,
    "Archimede": 0.4,
    # Heritage Revivals (0.4-0.5)
    "Doxa": 0.45,
    "Zodiac": 0.4,
    "Certina": 0.35,
    "Rado": 0.45,
    "Mido": 0.35,
    # Niche Independents (0.4-0.5)
    "Yema": 0.4,
    "Norqain": 0.45,
    "Farer": 0.4,
    "Formex": 0.4,
    # Additional haute horlogerie / luxury
    "Girard-Perregaux": 0.85,
    "Glashutte Original": 0.8,
    "Blancpain": 0.85,
    "Chopard": 0.8,
    "Piaget": 0.9,
    "Ulysse Nardin": 0.75,
    "Bell & Ross": 0.55,
    "Frederique Constant": 0.45,
    "Baume & Mercier": 0.45,
    "Doxa": 0.45,
}

# ---------------------------------------------------------------------------
# Material scores
# ---------------------------------------------------------------------------
MATERIAL_SCORES: dict[str, float] = {
    "Platinum": 0.95,
    "18k Gold": 0.90,
    "18k Rose Gold": 0.90,
    "18k White Gold": 0.90,
    "18k Yellow Gold": 0.90,
    "Titanium": 0.65,
    "Bronze": 0.55,
    "Ceramic": 0.60,
    "Stainless Steel": 0.50,
    "Steel/Ceramic": 0.55,
    "Steel/Gold": 0.70,
    "Carbon": 0.65,
    "Resin": 0.20,
    "Plastic": 0.15,
    "Aluminum": 0.25,
    "Tantalum": 0.80,
    "Ceramic/Plastic": 0.20,
    "Silver": 0.45,
    "Submarine Steel": 0.55,
    "Steel/Platinum": 0.75,
}


def _material_score(material: str) -> float:
    """Map case material to a 0-1 score."""
    return MATERIAL_SCORES.get(material, 0.50)


def _brand_tier(brand: str) -> float:
    """Map brand to a tier score."""
    return BRAND_TIER.get(brand, 0.40)


def _watch_type_score(watch_type: str) -> float:
    """Map watch type to a collectibility score."""
    return WATCH_TYPE_SCORES.get(watch_type, 0.40)


# ---------------------------------------------------------------------------
# Curated catalog — 125+ watches
# Each tuple: (brand, model, reference, movement, material, watch_type, price_eur)
# ---------------------------------------------------------------------------


def _rolex_watches() -> list[tuple]:
    """20 Rolex watches — current production, discontinued, and vintage icons."""
    return [
        ("Rolex", "Submariner Date", "126610LN", "Automatic Cal. 3235", "Stainless Steel",
         "Current Production", 13500),
        ("Rolex", "Submariner No-Date", "124060", "Automatic Cal. 3230", "Stainless Steel",
         "Current Production", 12000),
        ("Rolex", "GMT-Master II Pepsi", "126710BLRO", "Automatic Cal. 3285", "Stainless Steel",
         "Current Production", 19500),
        ("Rolex", "GMT-Master II Batman", "126710BLNR", "Automatic Cal. 3285", "Stainless Steel",
         "Current Production", 17500),
        ("Rolex", "Daytona White Dial", "116500LN", "Automatic Cal. 4130", "Stainless Steel",
         "Current Production", 32000),
        ("Rolex", "Daytona Black Dial", "116500LN-BK", "Automatic Cal. 4130", "Stainless Steel",
         "Current Production", 28000),
        ("Rolex", "Datejust 41 Blue Fluted", "126334", "Automatic Cal. 3235", "Stainless Steel",
         "Current Production", 12500),
        ("Rolex", "Explorer I", "124270", "Automatic Cal. 3230", "Stainless Steel",
         "Current Production", 8500),
        ("Rolex", "Explorer II Polar", "226570", "Automatic Cal. 3285", "Stainless Steel",
         "Current Production", 10500),
        ("Rolex", "Air-King", "126900", "Automatic Cal. 3230", "Stainless Steel",
         "Current Production", 8000),
        ("Rolex", "Oyster Perpetual 36 Green", "126000", "Automatic Cal. 3230", "Stainless Steel",
         "Current Production", 7500),
        ("Rolex", "Day-Date 40 Champagne", "228238", "Automatic Cal. 3255", "18k Yellow Gold",
         "Current Production", 36000),
        ("Rolex", "Sea-Dweller", "126600", "Automatic Cal. 3235", "Stainless Steel",
         "Current Production", 14000),
        ("Rolex", "Sky-Dweller Blue", "326934", "Automatic Cal. 9001", "Stainless Steel",
         "Current Production", 22000),
        ("Rolex", "Milgauss Z-Blue", "116400GV", "Automatic Cal. 3131", "Stainless Steel",
         "Discontinued Classic", 15000),
        ("Rolex", "Yacht-Master 40 Rhodium", "126622", "Automatic Cal. 3235", "Steel/Platinum",
         "Current Production", 14500),
        ("Rolex", "Vintage Submariner 5513", "5513", "Automatic Cal. 1520", "Stainless Steel",
         "Vintage Pre-1970", 18000),
        ("Rolex", "Vintage Daytona 6263 Paul Newman", "6263", "Manual Cal. 727", "Stainless Steel",
         "Vintage Pre-1970", 250000),
        ("Rolex", "Vintage GMT-Master Gilt Dial", "1675", "Automatic Cal. 1570", "Stainless Steel",
         "Vintage Pre-1970", 25000),
        ("Rolex", "Vintage Explorer 1016", "1016", "Automatic Cal. 1570", "Stainless Steel",
         "Vintage Pre-1970", 22000),
    ]


def _omega_watches() -> list[tuple]:
    """15 Omega watches — Speedmaster, Seamaster, and vintage references."""
    return [
        ("Omega", "Speedmaster Moonwatch Professional", "310.30.42.50.01.001",
         "Manual Cal. 3861", "Stainless Steel", "Current Production", 6500),
        ("Omega", "Speedmaster First Omega in Space", "311.32.40.30.01.001",
         "Manual Cal. 1861", "Stainless Steel", "Special Edition", 5800),
        ("Omega", "Seamaster Diver 300M Black", "210.30.42.20.01.001",
         "Automatic Cal. 8800", "Stainless Steel", "Current Production", 5200),
        ("Omega", "Seamaster Planet Ocean 600M", "215.30.44.21.01.001",
         "Automatic Cal. 8900", "Stainless Steel", "Current Production", 6200),
        ("Omega", "Aqua Terra 150M Green", "220.10.41.21.10.001",
         "Automatic Cal. 8900", "Stainless Steel", "Current Production", 5500),
        ("Omega", "Speedmaster 57 Co-Axial", "332.10.41.51.01.001",
         "Automatic Cal. 9906", "Stainless Steel", "Current Production", 8500),
        ("Omega", "Speedmaster Silver Snoopy Award 50th", "310.32.42.50.02.001",
         "Manual Cal. 3861", "Stainless Steel", "Anniversary Edition", 28000),
        ("Omega", "De Ville Prestige Co-Axial", "424.10.40.20.02.003",
         "Automatic Cal. 2500", "Stainless Steel", "Current Production", 3200),
        ("Omega", "Constellation Co-Axial 39mm", "131.10.39.20.02.001",
         "Automatic Cal. 8800", "Stainless Steel", "Current Production", 5800),
        ("Omega", "Seamaster Diver 300M No Time To Die", "210.90.42.20.01.001",
         "Automatic Cal. 8806", "Titanium", "Limited Edition", 9500),
        ("Omega", "Vintage Speedmaster 145.012 Pre-Moon", "145.012-67",
         "Manual Cal. 321", "Stainless Steel", "Vintage Pre-1970", 35000),
        ("Omega", "Speedmaster Mark II Co-Axial", "327.10.43.50.01.001",
         "Automatic Cal. 3330", "Stainless Steel", "Current Production", 4800),
        ("Omega", "Seamaster 300 Master Co-Axial", "234.30.41.21.01.001",
         "Automatic Cal. 8912", "Stainless Steel", "Current Production", 6800),
        ("Omega", "Speedmaster Moonwatch 321 Ed White", "311.30.40.30.01.001",
         "Manual Cal. 321", "Stainless Steel", "Limited Edition", 12000),
        ("Omega", "Vintage Seamaster 300 165.024", "165.024",
         "Automatic Cal. 552", "Stainless Steel", "Vintage Pre-1970", 8500),
    ]


def _seiko_watches() -> list[tuple]:
    """15 Seiko watches — classic models, Prospex, Grand Seiko, and vintage."""
    return [
        ("Seiko", "SKX007", "SKX007K2", "Automatic Cal. 7S26", "Stainless Steel",
         "Discontinued Classic", 450),
        ("Seiko", "SKX009 Pepsi", "SKX009K2", "Automatic Cal. 7S26", "Stainless Steel",
         "Discontinued Classic", 400),
        ("Seiko", "SARB033", "SARB033", "Automatic Cal. 6R15", "Stainless Steel",
         "Discontinued Classic", 650),
        ("Seiko", "SARB035 Cream", "SARB035", "Automatic Cal. 6R15", "Stainless Steel",
         "Discontinued Classic", 600),
        ("Seiko", "Presage Cocktail Time", "SRPB41J1", "Automatic Cal. 4R35", "Stainless Steel",
         "Current Production", 350),
        ("Seiko", "Prospex Turtle Save the Ocean", "SRPE93K1", "Automatic Cal. 4R36", "Stainless Steel",
         "Special Edition", 380),
        ("Seiko", "King Seiko SPB279", "SPB279J1", "Automatic Cal. 6R55", "Stainless Steel",
         "Current Production", 800),
        ("Grand Seiko", "Snowflake Spring Drive", "SBGA211", "Spring Drive Cal. 9R65", "Titanium",
         "Current Production", 5500),
        ("Grand Seiko", "Peacock SBGH267", "SBGH267", "Automatic Hi-Beat Cal. 9S85", "Stainless Steel",
         "Limited Edition", 8000),
        ("Seiko", "5 Sports Field Specialist", "SRPD76K1", "Automatic Cal. 4R36", "Stainless Steel",
         "Current Production", 220),
        ("Seiko", "Marinemaster 300 SLA021", "SLA021J1", "Automatic Cal. 8L35", "Stainless Steel",
         "Limited Edition", 3200),
        ("Seiko", "Vintage 6309-7040 Turtle", "6309-7040", "Automatic Cal. 6309", "Stainless Steel",
         "Vintage Pre-1970", 500),
        ("Seiko", "Alpinist SPB117", "SPB117J1", "Automatic Cal. 6R35", "Stainless Steel",
         "Current Production", 650),
        ("Seiko", "Tuna 300M", "SBBN049", "Quartz Cal. 7C46", "Stainless Steel",
         "Current Production", 700),
        ("Seiko", "Prospex LX Spring Drive", "SNR029J1", "Spring Drive Cal. 5R65", "Titanium",
         "Current Production", 3500),
    ]


def _tudor_watches() -> list[tuple]:
    """10 Tudor watches — Black Bay, Pelagos, and dress pieces."""
    return [
        ("Tudor", "Black Bay 58", "M79030N-0001", "Automatic Cal. MT5402", "Stainless Steel",
         "Current Production", 3800),
        ("Tudor", "Black Bay GMT", "M79830RB-0001", "Automatic Cal. MT5652", "Stainless Steel",
         "Current Production", 3900),
        ("Tudor", "Pelagos 39", "M25407N-0001", "Automatic Cal. MT5400", "Titanium",
         "Current Production", 4200),
        ("Tudor", "Black Bay Chrono", "M79360N-0002", "Automatic Cal. MT5813", "Stainless Steel",
         "Current Production", 4800),
        ("Tudor", "Ranger", "M79950-0001", "Automatic Cal. MT5402", "Stainless Steel",
         "Current Production", 2800),
        ("Tudor", "Black Bay 36", "M79500-0007", "Automatic Cal. MT5400", "Stainless Steel",
         "Current Production", 2600),
        ("Tudor", "Black Bay Bronze", "M79250BA-0001", "Automatic Cal. MT5601", "Bronze",
         "Current Production", 3600),
        ("Tudor", "1926 39mm", "M91550-0001", "Automatic Cal. T603", "Stainless Steel",
         "Current Production", 1800),
        ("Tudor", "Black Bay 58 925 Silver", "M79010SG-0001", "Automatic Cal. MT5400", "Silver",
         "Limited Edition", 4500),
        ("Tudor", "Black Bay Pro", "M79470-0001", "Automatic Cal. MT5652", "Stainless Steel",
         "Current Production", 3500),
    ]


def _casio_gshock_watches() -> list[tuple]:
    """10 Casio / G-Shock watches — iconic digitals, CasiOak, and premium."""
    return [
        ("Casio", "G-Shock DW-5600E-1V", "DW-5600E-1VER", "Quartz Module 3229", "Resin",
         "Current Production", 65),
        ("Casio", "G-Shock GA-2100-1A1 CasiOak", "GA-2100-1A1ER", "Quartz Module 5611", "Resin",
         "Current Production", 90),
        ("Casio", "G-Shock GW-M5610U-1 Multiband 6", "GW-M5610U-1ER", "Tough Solar Module 3495", "Resin",
         "Current Production", 120),
        ("Casio", "G-Shock MR-G Hana-Basara", "MRGB2000SH-5A", "Tough Solar Module 5645", "Titanium",
         "Limited Edition", 4500),
        ("Casio", "G-Shock Frogman GWF-A1000", "GWF-A1000-1A2ER", "Tough Solar Module 5623", "Carbon",
         "Current Production", 500),
        ("Casio", "A168WA-1 Vintage", "A168WA-1YES", "Quartz Module 1572", "Stainless Steel",
         "Current Production", 25),
        ("Casio", "G-Shock x John Mayer DW-6900", "DW-6900JM", "Quartz Module 3230", "Resin",
         "Limited Edition", 350),
        ("Casio", "G-Shock GM-B2100D-1A Full Metal CasiOak", "GM-B2100D-1AER",
         "Tough Solar Module 5690", "Stainless Steel", "Current Production", 450),
        ("Casio", "G-Shock GPW-2000 Gravitymaster", "GPW-2000-1AER",
         "Tough Solar Module 5524", "Carbon", "Current Production", 550),
        ("Casio", "G-Shock DW-5000C-1A Reissue", "DW-5000REC-1ER", "Quartz Module 3229", "Resin",
         "Anniversary Edition", 280),
    ]


def _patek_philippe_watches() -> list[tuple]:
    """10 Patek Philippe watches — Nautilus, Aquanaut, Calatrava, and complications."""
    return [
        ("Patek Philippe", "Nautilus Blue Dial", "5711/1A-010",
         "Automatic Cal. 26-330 SC", "Stainless Steel", "Discontinued Classic", 130000),
        ("Patek Philippe", "Aquanaut", "5167A-001",
         "Automatic Cal. 324 SC", "Stainless Steel", "Current Production", 32000),
        ("Patek Philippe", "Calatrava", "5196R-001",
         "Manual Cal. 215 PS", "18k Rose Gold", "Current Production", 22000),
        ("Patek Philippe", "Annual Calendar", "5205R-010",
         "Automatic Cal. 324 S QA LU 24H", "18k Rose Gold", "Current Production", 42000),
        ("Patek Philippe", "World Time", "5131J-001",
         "Automatic Cal. 240 HU", "18k Yellow Gold", "Current Production", 55000),
        ("Patek Philippe", "Perpetual Calendar", "5327G-001",
         "Automatic Cal. 240 Q", "18k White Gold", "Current Production", 85000),
        ("Patek Philippe", "Nautilus Chronograph", "5980/1A-001",
         "Automatic Cal. CH 28-520 C", "Stainless Steel", "Discontinued Classic", 95000),
        ("Patek Philippe", "Nautilus Travel Time", "5990/1A-001",
         "Automatic Cal. CH 28-520 C FUS", "Stainless Steel", "Current Production", 72000),
        ("Patek Philippe", "Nautilus Green", "5711/1A-014",
         "Automatic Cal. 26-330 SC", "Stainless Steel", "Limited Edition", 180000),
        ("Patek Philippe", "Twenty~4 Automatic", "7300/1200A-010",
         "Automatic Cal. 324 SC", "Stainless Steel", "Current Production", 28000),
    ]


def _audemars_piguet_watches() -> list[tuple]:
    """10 Audemars Piguet watches — Royal Oak variants and Code 11.59."""
    return [
        ("Audemars Piguet", "Royal Oak Selfwinding", "15500ST.OO.1220ST.01",
         "Automatic Cal. 4302", "Stainless Steel", "Current Production", 35000),
        ("Audemars Piguet", "Royal Oak Offshore Diver", "15710ST.OO.A002CA.01",
         "Automatic Cal. 3120", "Stainless Steel", "Current Production", 28000),
        ("Audemars Piguet", "Royal Oak Jumbo Extra-Thin", "15202ST.OO.1240ST.01",
         "Automatic Cal. 2121", "Stainless Steel", "Discontinued Classic", 75000),
        ("Audemars Piguet", "Code 11.59 Selfwinding", "15210OR.OO.A002CR.01",
         "Automatic Cal. 4302", "18k Rose Gold", "Current Production", 25000),
        ("Audemars Piguet", "Royal Oak Concept Flying Tourbillon", "26228OR.ZZ.D101CR.01",
         "Manual Cal. 2964", "18k Rose Gold", "Limited Edition", 180000),
        ("Audemars Piguet", "Royal Oak Chronograph", "26331ST.OO.1220ST.01",
         "Automatic Cal. 2385", "Stainless Steel", "Current Production", 38000),
        ("Audemars Piguet", "Royal Oak Offshore Chronograph", "26470ST.OO.A101CR.01",
         "Automatic Cal. 3126/3840", "Stainless Steel", "Current Production", 30000),
        ("Audemars Piguet", "Royal Oak Double Balance Wheel", "15407ST.OO.1220ST.01",
         "Automatic Cal. 3132", "Stainless Steel", "Current Production", 50000),
        ("Audemars Piguet", "Royal Oak Perpetual Calendar", "26574ST.OO.1220ST.01",
         "Automatic Cal. 5134", "Stainless Steel", "Current Production", 75000),
        ("Audemars Piguet", "Royal Oak Offshore Survivor", "26165IO.OO.A002CA.01",
         "Automatic Cal. 3126/3840", "Ceramic", "Limited Edition", 45000),
    ]


def _affordable_watches() -> list[tuple]:
    """15 affordable collectible watches — entry-level icons and value picks."""
    return [
        ("Tissot", "PRX Powermatic 80", "T137.407.11.041.00",
         "Automatic Powermatic 80", "Stainless Steel", "Current Production", 600),
        ("Hamilton", "Khaki Field Mechanical", "H69439931",
         "Manual Cal. H-50", "Stainless Steel", "Current Production", 450),
        ("Hamilton", "Khaki Aviation Pilot Day Date", "H64615135",
         "Automatic Cal. H-40", "Stainless Steel", "Current Production", 650),
        ("Orient", "Bambino Version 2", "FAC00005W0",
         "Automatic Cal. F6724", "Stainless Steel", "Current Production", 180),
        ("Swatch", "MoonSwatch Mission to the Moon", "SO33M100",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 350),
        ("Swatch", "MoonSwatch Mission to Mars", "SO33R100",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 400),
        ("Timex", "Marlin Automatic", "TW2T22700",
         "Automatic Miyota 8215", "Stainless Steel", "Current Production", 200),
        ("Citizen", "Promaster Diver Eco-Drive", "BN0151-17L",
         "Eco-Drive Cal. E168", "Stainless Steel", "Current Production", 200),
        ("Seagull", "1963 Reissue Chronograph", "1963",
         "Manual Cal. ST1901", "Stainless Steel", "Special Edition", 300),
        ("Vostok", "Amphibia 420 Classic", "420059",
         "Automatic Cal. 2416B", "Stainless Steel", "Current Production", 80),
        ("Casio", "Duro MDV106", "MDV106-1AV",
         "Quartz Module", "Stainless Steel", "Current Production", 50),
        ("Marathon", "GSAR 41mm", "WW194006",
         "Automatic ETA 2824-2", "Stainless Steel", "Military Issue", 1100),
        ("Marathon", "TSAR 36mm Quartz", "WW194027",
         "Quartz ETA F06.111", "Stainless Steel", "Military Issue", 500),
        ("Orient", "Kamasu", "RA-AA0003R19B",
         "Automatic Cal. F6922", "Stainless Steel", "Current Production", 250),
        ("Citizen", "NB1050-59A Tsuyosa", "NB1050-59A",
         "Automatic Cal. 8210", "Stainless Steel", "Current Production", 350),
    ]


def _independent_watches() -> list[tuple]:
    """10 independent / micro brand watches — Nomos, Sinn, Junghans, etc."""
    return [
        ("Nomos", "Tangente 38", "164",
         "Manual Cal. Alpha", "Stainless Steel", "Current Production", 1500),
        ("Nomos", "Club Campus 38.5", "736",
         "Manual Cal. Alpha", "Stainless Steel", "Current Production", 1100),
        ("Sinn", "556 I", "556.010",
         "Automatic SW 200-1", "Stainless Steel", "Current Production", 1250),
        ("Sinn", "U50", "1050.010",
         "Automatic SW 300-1", "Submarine Steel", "Current Production", 2300),
        ("Junghans", "Max Bill Automatic", "027/3501.04",
         "Automatic J800.1", "Stainless Steel", "Current Production", 900),
        ("Baltic", "Aquascaphe", "AQ.BLC",
         "Automatic Miyota 9039", "Stainless Steel", "Current Production", 550),
        ("Christopher Ward", "C60 Sealander GMT", "C60-40AGM3-S0KK0-B0",
         "Automatic Sellita SW330-2", "Stainless Steel", "Current Production", 900),
        ("Ming", "17.09", "17.09",
         "Automatic Sellita SW330-2", "Stainless Steel", "Limited Edition", 3500),
        ("H. Moser & Cie", "Streamliner Flyback Chronograph", "6902-1200",
         "Automatic Cal. HMC 902", "Stainless Steel", "Current Production", 28000),
        ("Oris", "Aquis Date 41.5mm", "01 733 7766 4135",
         "Automatic Cal. 400", "Stainless Steel", "Current Production", 2100),
    ]


def _vintage_icon_watches() -> list[tuple]:
    """10 vintage icon watches — legendary references from various maisons."""
    return [
        ("Omega", "Vintage Constellation Pie Pan", "168.005",
         "Automatic Cal. 564", "Stainless Steel", "Vintage Pre-1970", 3500),
        ("Heuer", "Vintage Monaco Steve McQueen", "1133B",
         "Automatic Cal. 11", "Stainless Steel", "Vintage Pre-1970", 45000),
        ("Universal Geneve", "Vintage Polerouter", "20217-1",
         "Automatic Cal. 215-1", "Stainless Steel", "Vintage Pre-1970", 2500),
        ("Zenith", "Vintage El Primero A386", "A386",
         "Automatic Cal. 3019 PHC", "Stainless Steel", "Vintage Pre-1970", 25000),
        ("Jaeger-LeCoultre", "Vintage Reverso Classic", "250.8.86",
         "Manual Cal. 846/1", "Stainless Steel", "Vintage Pre-1970", 5000),
        ("Longines", "Vintage Flagship", "3418",
         "Automatic Cal. L633.1", "Stainless Steel", "Vintage Pre-1970", 1200),
        ("Breitling", "Vintage Navitimer 806", "806",
         "Manual Cal. Venus 178", "Stainless Steel", "Vintage Pre-1970", 12000),
        ("IWC", "Vintage Mark XI RAF", "IW6B/346",
         "Manual Cal. 89", "Stainless Steel", "Military Issue", 8000),
        ("Heuer", "Vintage Carrera Ref. 2447", "2447SN",
         "Manual Cal. Valjoux 72", "Stainless Steel", "Vintage Pre-1970", 18000),
        ("Omega", "Vintage Seamaster 300 CK2913", "CK2913",
         "Automatic Cal. 501", "Stainless Steel", "Vintage Pre-1970", 30000),
    ]


def _vacheron_constantin_watches() -> list[tuple]:
    """10 Vacheron Constantin watches — Overseas, Patrimony, Historiques, Traditionnelle, FiftySix."""
    return [
        ("Vacheron Constantin", "Overseas Blue Dial", "4500V/110A-B128",
         "Automatic Cal. 5100", "Stainless Steel", "Current Production", 24000),
        ("Vacheron Constantin", "Overseas Black Dial", "4500V/110A-B483",
         "Automatic Cal. 5100", "Stainless Steel", "Current Production", 22000),
        ("Vacheron Constantin", "Overseas Chronograph", "5500V/110A-B481",
         "Automatic Cal. 5200", "Stainless Steel", "Current Production", 32000),
        ("Vacheron Constantin", "Patrimony Manual Wind", "81180/000R-9159",
         "Manual Cal. 1400", "18k Rose Gold", "Current Production", 18000),
        ("Vacheron Constantin", "Patrimony Self-Winding", "85180/000R-9166",
         "Automatic Cal. 2450 Q6", "18k Rose Gold", "Current Production", 22000),
        ("Vacheron Constantin", "Patrimony Moon Phase", "4010U/000R-B329",
         "Automatic Cal. 5235/2", "18k Rose Gold", "Current Production", 35000),
        ("Vacheron Constantin", "Historiques American 1921", "1100S/000R-B430",
         "Manual Cal. 4400 AS", "18k Rose Gold", "Current Production", 32000),
        ("Vacheron Constantin", "Historiques Cornes de Vache 1955", "5000H/000R-B013",
         "Manual Cal. 1142", "18k Rose Gold", "Limited Edition", 55000),
        ("Vacheron Constantin", "Traditionnelle Manual Wind", "82172/000R-9382",
         "Manual Cal. 4400 AS", "18k Rose Gold", "Current Production", 20000),
        ("Vacheron Constantin", "FiftySix Self-Winding", "4600E/000A-B487",
         "Automatic Cal. 1326", "Stainless Steel", "Current Production", 11000),
    ]


def _cartier_watches() -> list[tuple]:
    """10 Cartier watches — Santos, Tank, Ballon Bleu, Panthere, Drive."""
    return [
        ("Cartier", "Santos de Cartier Medium", "WSSA0029",
         "Automatic Cal. 1847 MC", "Stainless Steel", "Current Production", 6200),
        ("Cartier", "Santos de Cartier Large", "WSSA0018",
         "Automatic Cal. 1847 MC", "Stainless Steel", "Current Production", 7200),
        ("Cartier", "Santos de Cartier Skeleton", "WHSA0015",
         "Manual Cal. 9611 MC", "Stainless Steel", "Current Production", 12000),
        ("Cartier", "Tank Must", "WSTA0065",
         "Quartz Cal. 076", "Stainless Steel", "Current Production", 3100),
        ("Cartier", "Tank Francaise Medium", "WSTA0065",
         "Quartz Cal. 057", "Stainless Steel", "Current Production", 3800),
        ("Cartier", "Tank Louis Cartier", "W1529756",
         "Manual Cal. 8971 MC", "18k Yellow Gold", "Current Production", 12500),
        ("Cartier", "Ballon Bleu 36mm", "WSBB0044",
         "Automatic Cal. 076", "Stainless Steel", "Current Production", 6000),
        ("Cartier", "Ballon Bleu 42mm", "WSBB0026",
         "Automatic Cal. 1847 MC", "Stainless Steel", "Current Production", 7500),
        ("Cartier", "Panthere de Cartier Medium", "WSPN0007",
         "Quartz Cal. 057", "Stainless Steel", "Current Production", 4500),
        ("Cartier", "Panthere de Cartier Small", "WSPN0006",
         "Quartz Cal. 157", "Stainless Steel", "Current Production", 3800),
    ]


def _lange_sohne_watches() -> list[tuple]:
    """8 A. Lange & Sohne watches — Lange 1, Saxonia, 1815, Zeitwerk, Datograph."""
    return [
        ("A. Lange & Sohne", "Lange 1", "191.032",
         "Manual Cal. L121.1", "18k Rose Gold", "Current Production", 35000),
        ("A. Lange & Sohne", "Grand Lange 1", "117.032",
         "Manual Cal. L095.1", "18k Rose Gold", "Current Production", 42000),
        ("A. Lange & Sohne", "Lange 1 Moon Phase", "192.032",
         "Manual Cal. L121.3", "18k Rose Gold", "Current Production", 45000),
        ("A. Lange & Sohne", "Saxonia Thin", "201.033",
         "Manual Cal. L093.1", "18k White Gold", "Current Production", 18000),
        ("A. Lange & Sohne", "Saxonia Annual Calendar", "330.032",
         "Automatic Cal. L085.1 SAX-0-MAT", "18k Rose Gold", "Current Production", 38000),
        ("A. Lange & Sohne", "1815 Manual Wind", "235.032",
         "Manual Cal. L051.1", "18k Rose Gold", "Current Production", 22000),
        ("A. Lange & Sohne", "1815 Chronograph", "414.031",
         "Manual Cal. L951.5", "18k White Gold", "Current Production", 52000),
        ("A. Lange & Sohne", "1815 Up/Down", "234.032",
         "Manual Cal. L051.2", "18k Rose Gold", "Current Production", 28000),
    ]


def _iwc_watches() -> list[tuple]:
    """8 IWC watches — Portugieser, Pilot's Watch, Aquatimer, Da Vinci."""
    return [
        ("IWC", "Portugieser Chronograph", "IW371605",
         "Automatic Cal. 69355", "Stainless Steel", "Current Production", 8200),
        ("IWC", "Portugieser Annual Calendar", "IW503501",
         "Automatic Cal. 52850", "Stainless Steel", "Current Production", 12500),
        ("IWC", "Portugieser Perpetual Calendar", "IW503301",
         "Automatic Cal. 52610", "18k Rose Gold", "Current Production", 32000),
        ("IWC", "Pilot's Watch Mark XX", "IW328203",
         "Automatic Cal. 32111", "Stainless Steel", "Current Production", 4800),
        ("IWC", "Big Pilot's Watch 43", "IW329301",
         "Automatic Cal. 82100", "Stainless Steel", "Current Production", 8500),
        ("IWC", "Pilot's Watch Chronograph Spitfire", "IW387901",
         "Automatic Cal. 69385", "Stainless Steel", "Current Production", 5600),
        ("IWC", "Aquatimer Automatic 2000", "IW358001",
         "Automatic Cal. 32110", "Titanium", "Current Production", 10000),
        ("IWC", "Da Vinci Perpetual Calendar", "IW392103",
         "Automatic Cal. 82590", "18k Rose Gold", "Current Production", 28000),
    ]


def _breitling_watches() -> list[tuple]:
    """8 Breitling watches — Navitimer, Superocean Heritage, Chronomat, Avenger."""
    return [
        ("Breitling", "Navitimer B01 Chronograph 43", "AB0121211B1A1",
         "Automatic Cal. B01", "Stainless Steel", "Current Production", 7800),
        ("Breitling", "Navitimer B01 Chronograph 46", "AB0127211B1P1",
         "Automatic Cal. B01", "Stainless Steel", "Current Production", 8500),
        ("Breitling", "Superocean Heritage 57", "A10370121B1A1",
         "Automatic Cal. B10", "Stainless Steel", "Current Production", 4500),
        ("Breitling", "Superocean Heritage II 42", "AB2010121B1A1",
         "Automatic Cal. B20", "Stainless Steel", "Current Production", 3800),
        ("Breitling", "Chronomat B01 42", "AB0134101B1A1",
         "Automatic Cal. B01", "Stainless Steel", "Current Production", 7200),
        ("Breitling", "Chronomat Automatic 36", "A10380101A2A1",
         "Automatic Cal. B10", "Stainless Steel", "Current Production", 4600),
        ("Breitling", "Avenger Chronograph 45", "A13317101B1A1",
         "Automatic Cal. B13", "Stainless Steel", "Current Production", 5200),
        ("Breitling", "Avenger Automatic GMT 44", "A32320101B1X1",
         "Automatic Cal. B32", "Stainless Steel", "Current Production", 4200),
    ]


def _jlc_watches() -> list[tuple]:
    """8 Jaeger-LeCoultre watches — Reverso, Master Ultra Thin, Master Control, Polaris."""
    return [
        ("Jaeger-LeCoultre", "Reverso Classic Large", "Q3858520",
         "Manual Cal. 822/2", "Stainless Steel", "Current Production", 6500),
        ("Jaeger-LeCoultre", "Reverso Tribute", "Q3978480",
         "Manual Cal. 822/2", "Stainless Steel", "Current Production", 8000),
        ("Jaeger-LeCoultre", "Reverso Classic Duoface", "Q3838420",
         "Manual Cal. 854A/2", "Stainless Steel", "Current Production", 10000),
        ("Jaeger-LeCoultre", "Master Ultra Thin Moon", "Q1368420",
         "Automatic Cal. 925/1", "Stainless Steel", "Current Production", 10500),
        ("Jaeger-LeCoultre", "Master Ultra Thin Date", "Q1288420",
         "Automatic Cal. 899/1", "Stainless Steel", "Current Production", 7500),
        ("Jaeger-LeCoultre", "Master Control Date", "Q4018420",
         "Automatic Cal. 899AC", "Stainless Steel", "Current Production", 6800),
        ("Jaeger-LeCoultre", "Master Control Chronograph", "Q4138420",
         "Automatic Cal. 759", "Stainless Steel", "Current Production", 9000),
        ("Jaeger-LeCoultre", "Polaris Chronograph", "Q9028170",
         "Automatic Cal. 751H", "Stainless Steel", "Current Production", 9500),
    ]


def _timex_watches() -> list[tuple]:
    """8 Timex watches — collectible Marlin, Q Timex reissues, collaborations."""
    return [
        ("Timex", "Marlin Automatic", "TW2T22700",
         "Automatic Miyota 8215", "Stainless Steel", "Current Production", 200),
        ("Timex", "Marlin Hand-Wound", "TW2T18200",
         "Manual Cal. 2115", "Stainless Steel", "Current Production", 160),
        ("Timex", "Marlin Automatic Snoopy", "TW2U71200",
         "Automatic Miyota 8215", "Stainless Steel", "Special Edition", 250),
        ("Timex", "Q Timex Reissue 1979", "TW2U61300",
         "Quartz", "Stainless Steel", "Special Edition", 180),
        ("Timex", "Q Timex Pepsi Reissue", "TW2U61100",
         "Quartz", "Stainless Steel", "Special Edition", 170),
        ("Timex", "Q Timex x Coca-Cola", "TW2V25900",
         "Quartz", "Stainless Steel", "Limited Edition", 200),
        ("Timex", "Waterbury Traditional Chronograph", "TW2R72200",
         "Quartz", "Stainless Steel", "Current Production", 120),
        ("Timex", "M79 Automatic", "TW2U83400",
         "Automatic Miyota 8205", "Stainless Steel", "Current Production", 280),
    ]


def _zenith_watches() -> list[tuple]:
    """8 Zenith watches — El Primero, Chronomaster, Defy, Pilot."""
    return [
        ("Zenith", "Chronomaster Sport", "03.3100.3600/69.M3100",
         "Automatic Cal. El Primero 3600", "Stainless Steel", "Current Production", 8500),
        ("Zenith", "Chronomaster Original", "03.3200.3600/21.M3200",
         "Automatic Cal. El Primero 3600", "Stainless Steel", "Current Production", 7800),
        ("Zenith", "Defy Skyline", "03.9300.3620/01.I001",
         "Automatic Cal. Elite 670 SK", "Stainless Steel", "Current Production", 7200),
        ("Zenith", "Defy Classic", "95.9000.670/78.R782",
         "Automatic Cal. Elite 670", "Titanium", "Current Production", 6500),
        ("Zenith", "Pilot Type 20 Extra Special", "03.2430.3000/21.C738",
         "Automatic Cal. Elite 679", "Stainless Steel", "Current Production", 5500),
        ("Zenith", "Chronomaster Revival El Primero A384", "03.A384.400/21.M384",
         "Automatic Cal. El Primero 400", "Stainless Steel", "Limited Edition", 9000),
        ("Zenith", "Defy El Primero 21", "95.9005.9004/01.R582",
         "Automatic Cal. El Primero 9004", "Titanium", "Current Production", 12000),
        ("Zenith", "Chronomaster Open", "03.2040.4061/69.C496",
         "Automatic Cal. El Primero 4061", "Stainless Steel", "Current Production", 7500),
    ]


def _panerai_watches() -> list[tuple]:
    """8 Panerai watches — Luminor, Submersible, Radiomir."""
    return [
        ("Panerai", "Luminor Marina", "PAM01312",
         "Automatic Cal. P.9010", "Stainless Steel", "Current Production", 7200),
        ("Panerai", "Luminor Due 42mm", "PAM01046",
         "Automatic Cal. P.900", "Stainless Steel", "Current Production", 6800),
        ("Panerai", "Submersible 42mm", "PAM00959",
         "Automatic Cal. P.900", "Stainless Steel", "Current Production", 8200),
        ("Panerai", "Radiomir Base", "PAM00753",
         "Manual Cal. P.6000", "Stainless Steel", "Current Production", 5500),
        ("Panerai", "Luminor Chrono", "PAM01218",
         "Automatic Cal. P.9200", "Stainless Steel", "Current Production", 9500),
        ("Panerai", "Submersible Azzurro 42mm", "PAM01209",
         "Automatic Cal. P.900", "Stainless Steel", "Limited Edition", 9000),
        ("Panerai", "Luminor 1950 3 Days GMT", "PAM01321",
         "Automatic Cal. P.9001", "Stainless Steel", "Current Production", 9800),
        ("Panerai", "Radiomir California 47mm", "PAM00424",
         "Manual Cal. P.3000", "Stainless Steel", "Special Edition", 7500),
    ]


def _luxury_expansion_watches() -> list[tuple]:
    """5 additional luxury watches — Richard Mille, FP Journe, MB&F, Moser."""
    return [
        ("H. Moser & Cie", "Endeavour Centre Seconds", "1200-0215",
         "Automatic Cal. HMC 200", "Stainless Steel", "Current Production", 12000),
        ("Oris", "Big Crown Pointer Date", "01 754 7741 4065",
         "Automatic Cal. 754", "Stainless Steel", "Current Production", 1800),
        ("Longines", "Spirit Zulu Time", "L3.812.4.53.6",
         "Automatic Cal. L844.4", "Stainless Steel", "Current Production", 2600),
        ("Tissot", "PRX 40 205", "T137.407.11.091.00",
         "Automatic Powermatic 80", "Stainless Steel", "Current Production", 650),
        ("Hamilton", "Ventura Automatic", "H24515591",
         "Automatic Cal. H-10", "Stainless Steel", "Current Production", 900),
    ]


def _rolex_expansion_watches() -> list[tuple]:
    """20 additional Rolex — GMT Sprite, Yacht-Master, Day-Date, Daytona variants, vintage."""
    return [
        ("Rolex", "GMT-Master II Sprite", "126720VTNR", "Automatic Cal. 3285", "Stainless Steel",
         "Current Production", 20000),
        ("Rolex", "Daytona Rose Gold Chocolate", "116515LN", "Automatic Cal. 4130", "18k Rose Gold",
         "Current Production", 35000),
        ("Rolex", "Daytona Platinum Ice Blue", "116506", "Automatic Cal. 4130", "Platinum",
         "Current Production", 85000),
        ("Rolex", "Day-Date 40 Olive Green", "228235", "Automatic Cal. 3255", "18k Rose Gold",
         "Current Production", 42000),
        ("Rolex", "Day-Date 36 Fluted", "128238", "Automatic Cal. 3255", "18k Yellow Gold",
         "Current Production", 33000),
        ("Rolex", "Yacht-Master 42 White Gold", "226659", "Automatic Cal. 3235", "18k White Gold",
         "Current Production", 26000),
        ("Rolex", "Yacht-Master 40 Everose", "126621", "Automatic Cal. 3235", "Steel/Gold",
         "Current Production", 16000),
        ("Rolex", "Submariner Date Two-Tone", "126613LB", "Automatic Cal. 3235", "Steel/Gold",
         "Current Production", 18000),
        ("Rolex", "Submariner Date Green (Starbucks)", "126610LV", "Automatic Cal. 3235", "Stainless Steel",
         "Current Production", 17000),
        ("Rolex", "Datejust 41 Wimbledon", "126333", "Automatic Cal. 3235", "Steel/Gold",
         "Current Production", 14500),
        ("Rolex", "Datejust 36 Palm Motif", "126234", "Automatic Cal. 3235", "Stainless Steel",
         "Current Production", 11000),
        ("Rolex", "Oyster Perpetual 41 Turquoise", "124300", "Automatic Cal. 3230", "Stainless Steel",
         "Current Production", 14000),
        ("Rolex", "Cellini Moonphase", "50535", "Automatic Cal. 3195", "18k Rose Gold",
         "Current Production", 25000),
        ("Rolex", "Vintage Day-Date 1803", "1803", "Automatic Cal. 1556", "18k Yellow Gold",
         "Vintage Pre-1970", 15000),
        ("Rolex", "Vintage Daytona 6239", "6239", "Manual Cal. 722-1", "Stainless Steel",
         "Vintage Pre-1970", 150000),
        ("Rolex", "Vintage Submariner Red 1680", "1680", "Automatic Cal. 1570", "Stainless Steel",
         "Vintage Pre-1970", 28000),
        ("Rolex", "Vintage Datejust Buckley 1601", "1601", "Automatic Cal. 1570", "Stainless Steel",
         "Vintage Pre-1970", 6000),
        ("Rolex", "Explorer II Steve McQueen 1655", "1655", "Automatic Cal. 1575", "Stainless Steel",
         "Vintage Pre-1970", 30000),
        ("Rolex", "Deepsea D-Blue James Cameron", "136660", "Automatic Cal. 3235", "Stainless Steel",
         "Current Production", 16000),
        ("Rolex", "GMT-Master II Meteorite", "126719BLRO", "Automatic Cal. 3285", "18k White Gold",
         "Current Production", 55000),
    ]


def _omega_expansion_watches() -> list[tuple]:
    """10 additional Omega — Speedmaster Dark Side, Seamaster variants, vintage."""
    return [
        ("Omega", "Speedmaster Dark Side of the Moon", "311.92.44.51.01.003",
         "Automatic Cal. 9300", "Ceramic", "Current Production", 10500),
        ("Omega", "Speedmaster Racing Co-Axial", "329.30.44.51.01.002",
         "Automatic Cal. 9900", "Stainless Steel", "Current Production", 6800),
        ("Omega", "Seamaster Diver 300M Nekton", "210.32.42.20.01.002",
         "Automatic Cal. 8806", "Stainless Steel", "Limited Edition", 7500),
        ("Omega", "Seamaster Aqua Terra Worldtimer", "220.10.43.22.03.001",
         "Automatic Cal. 8938", "Stainless Steel", "Current Production", 7800),
        ("Omega", "Speedmaster CK2998 Pulsometer", "311.32.40.30.02.001",
         "Manual Cal. 1861", "Stainless Steel", "Limited Edition", 7200),
        ("Omega", "Speedmaster Ultraman", "311.12.42.30.01.001",
         "Manual Cal. 1861", "Stainless Steel", "Limited Edition", 9000),
        ("Omega", "Seamaster 300 Bronze Gold", "234.92.41.21.10.001",
         "Automatic Cal. 8912", "Bronze", "Current Production", 12500),
        ("Omega", "De Ville Tresor Power Reserve", "435.13.40.22.02.001",
         "Manual Cal. 8929", "Stainless Steel", "Current Production", 5500),
        ("Omega", "Vintage Speedmaster Professional 145.022-69", "145.022-69",
         "Manual Cal. 861", "Stainless Steel", "Vintage Pre-1970", 15000),
        ("Omega", "Seamaster Planet Ocean Ultra Deep", "215.30.46.21.01.001",
         "Automatic Cal. 8912", "Titanium", "Current Production", 12000),
    ]


def _grand_seiko_expansion_watches() -> list[tuple]:
    """10 Grand Seiko watches — Spring Drive, Hi-Beat, and limited editions."""
    return [
        ("Grand Seiko", "Heritage SBGA413 Shunbun", "SBGA413",
         "Spring Drive Cal. 9R65", "Stainless Steel", "Limited Edition", 6200),
        ("Grand Seiko", "Heritage SBGH311 Mt. Iwate", "SBGH311",
         "Automatic Hi-Beat Cal. 9S85", "Stainless Steel", "Current Production", 6500),
        ("Grand Seiko", "Evolution 9 SLGA007 White Birch", "SLGA007",
         "Spring Drive Cal. 9RA2", "Stainless Steel", "Current Production", 9800),
        ("Grand Seiko", "Elegance SBGY007 Omiwatari", "SBGY007",
         "Spring Drive Cal. 9R31", "Platinum", "Limited Edition", 32000),
        ("Grand Seiko", "Sport SBGE257 Spring Drive GMT", "SBGE257",
         "Spring Drive Cal. 9R66", "Stainless Steel", "Current Production", 5800),
        ("Grand Seiko", "Heritage SBGW231 Manual Wind", "SBGW231",
         "Manual Cal. 9S64", "Stainless Steel", "Current Production", 3800),
        ("Grand Seiko", "Sport SBGC240 Spring Drive Chronograph", "SBGC240",
         "Spring Drive Cal. 9R96", "Titanium", "Current Production", 12000),
        ("Grand Seiko", "Heritage SBGJ201", "SBGJ201",
         "Automatic Hi-Beat Cal. 9S86", "Stainless Steel", "Current Production", 6200),
        ("Grand Seiko", "Evolution 9 SLGH005 White Birch", "SLGH005",
         "Automatic Hi-Beat Cal. 9SA5", "Stainless Steel", "Current Production", 9200),
        ("Grand Seiko", "Heritage SBGA211G Snowflake LE", "SBGA211G",
         "Spring Drive Cal. 9R65", "Titanium", "Limited Edition", 7500),
    ]


def _richard_mille_watches() -> list[tuple]:
    """5 Richard Mille watches — iconic ultra-luxury sport pieces."""
    return [
        ("Richard Mille", "RM 011 Automatic Flyback Chronograph", "RM 011",
         "Automatic Cal. RMAC3", "Titanium", "Current Production", 180000),
        ("Richard Mille", "RM 035 Rafael Nadal", "RM 035",
         "Manual Cal. RMUL3", "Carbon", "Limited Edition", 250000),
        ("Richard Mille", "RM 055 Bubba Watson", "RM 055",
         "Manual Cal. RMUL2", "Ceramic", "Limited Edition", 200000),
        ("Richard Mille", "RM 027 Tourbillon Rafael Nadal", "RM 027",
         "Manual Cal. RM027", "Titanium", "Limited Edition", 750000),
        ("Richard Mille", "RM 067-01 Automatic Extra Flat", "RM 067-01",
         "Automatic Cal. CRMA6", "Titanium", "Current Production", 85000),
    ]


def _fp_journe_watches() -> list[tuple]:
    """5 F.P. Journe watches — independent haute horlogerie icons."""
    return [
        ("F.P. Journe", "Chronometre Bleu", "CB",
         "Manual Cal. 1304", "Tantalum", "Current Production", 45000),
        ("F.P. Journe", "Chronometre Souverain", "CS",
         "Manual Cal. 1304", "Platinum", "Current Production", 55000),
        ("F.P. Journe", "Octa Automatique", "OA",
         "Automatic Cal. 1300.3", "18k Rose Gold", "Current Production", 48000),
        ("F.P. Journe", "Tourbillon Souverain", "TS",
         "Manual Cal. 1403", "Platinum", "Current Production", 280000),
        ("F.P. Journe", "Resonance", "RES",
         "Manual Cal. 1499.3", "Platinum", "Current Production", 320000),
    ]


def _mbf_watches() -> list[tuple]:
    """5 MB&F watches — avant-garde horological machines."""
    return [
        ("MB&F", "Legacy Machine 101", "LM101",
         "Manual Cal. Kari Voutilainen", "18k Rose Gold", "Current Production", 65000),
        ("MB&F", "Legacy Machine Perpetual", "LM Perpetual",
         "Automatic Cal. Stephen McDonnell", "Platinum", "Limited Edition", 160000),
        ("MB&F", "HM7 Aquapod", "HM7",
         "Automatic Cal. HM7", "Titanium", "Limited Edition", 95000),
        ("MB&F", "HM10 Bulldog", "HM10",
         "Manual Cal. HM10", "Titanium", "Current Production", 85000),
        ("MB&F", "Legacy Machine 2", "LM2",
         "Manual Cal. Jean-Francois Mojon", "18k White Gold", "Current Production", 75000),
    ]


def _swatch_moonswatch_watches() -> list[tuple]:
    """10 Swatch x Omega MoonSwatch variants — the 2022 phenomenon."""
    return [
        ("Swatch", "MoonSwatch Mission to Neptune", "SO33N100",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 300),
        ("Swatch", "MoonSwatch Mission to Jupiter", "SO33I100",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 280),
        ("Swatch", "MoonSwatch Mission to Saturn", "SO33T100",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 280),
        ("Swatch", "MoonSwatch Mission to the Sun", "SO33J100",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 300),
        ("Swatch", "MoonSwatch Mission to Mercury", "SO33A100",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 280),
        ("Swatch", "MoonSwatch Mission to Venus", "SO33P100",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 280),
        ("Swatch", "MoonSwatch Mission to Earth", "SO33G100",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 320),
        ("Swatch", "MoonSwatch Mission to Pluto", "SO33M101",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 350),
        ("Swatch", "MoonSwatch Mission to Uranus", "SO33L100",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 280),
        ("Swatch", "MoonSwatch Snoopy", "SO33W100",
         "Quartz ETA", "Ceramic/Plastic", "Limited Edition", 500),
    ]


def _gshock_collab_watches() -> list[tuple]:
    """10 G-Shock limited collabs — BAPE, Kith, Supreme, NASA, and more."""
    return [
        ("G-Shock", "DW-6900 x BAPE White", "DW-6900BAPE20-7",
         "Quartz Module 3230", "Resin", "Limited Edition", 400),
        ("G-Shock", "GA-2100 x CasiOak Rainbow", "GA-2100SKE-7A",
         "Quartz Module 5611", "Resin", "Limited Edition", 250),
        ("G-Shock", "DW-5600 x NASA", "DW5600NASA21-1",
         "Quartz Module 3229", "Resin", "Limited Edition", 300),
        ("G-Shock", "DW-5600 x Supreme", "DW-5600SUP-1",
         "Quartz Module 3229", "Resin", "Limited Edition", 600),
        ("G-Shock", "GA-110 x Kith", "GA-110KITH-1A",
         "Quartz Module 5146", "Resin", "Limited Edition", 350),
        ("G-Shock", "GWF-1000 x ICERC Love The Sea", "GWF-1000K-7JR",
         "Tough Solar Module 5053", "Resin", "Limited Edition", 800),
        ("G-Shock", "DW-5600 x Bamford", "DW-5600BWD-1",
         "Quartz Module 3229", "Resin", "Limited Edition", 280),
        ("G-Shock", "GA-2100 x Neon Genesis Evangelion", "GA-2100EVA-8A",
         "Quartz Module 5611", "Resin", "Limited Edition", 350),
        ("G-Shock", "GMW-B5000 Full Metal Gold", "GMW-B5000GD-9",
         "Tough Solar Module 3459", "Stainless Steel", "Current Production", 550),
        ("G-Shock", "MR-G Gassan", "MRGB2000GA-1A",
         "Tough Solar Module 5645", "Titanium", "Limited Edition", 5500),
    ]


def _additional_independents_watches() -> list[tuple]:
    """15 additional independent / niche brand watches."""
    return [
        ("Ming", "27.02 Concept", "27.02",
         "Automatic Schwarz-Etienne", "Titanium", "Limited Edition", 15000),
        ("Ming", "37.09 Bluefin", "37.09",
         "Automatic Sellita SW330-2", "Stainless Steel", "Limited Edition", 5500),
        ("Sinn", "EZM 1.1 Mission Timer", "EZM1.1",
         "Automatic Valjoux 7750", "Stainless Steel", "Military Issue", 3200),
        ("Sinn", "356 Flieger Chronograph", "356.020",
         "Automatic Valjoux 7750", "Stainless Steel", "Current Production", 2200),
        ("Nomos", "Zurich Worldtimer", "807",
         "Automatic Cal. DUW 5201", "Stainless Steel", "Current Production", 4200),
        ("Nomos", "Lambda 39", "954",
         "Manual Cal. DUW 1001", "18k Rose Gold", "Current Production", 7500),
        ("Baltic", "Bicompax 001", "BC001",
         "Manual Sellita SW510 BM", "Stainless Steel", "Current Production", 750),
        ("Baltic", "MR01 Micro-Rotor", "MR01",
         "Automatic Miyota 9039", "Stainless Steel", "Current Production", 600),
        ("Oris", "Divers Sixty-Five", "01 733 7707 4064",
         "Automatic Sellita SW 200-1", "Bronze", "Current Production", 2200),
        ("Christopher Ward", "C63 Sealander Automatic", "C63-39ADA3-S0KK0-B0",
         "Automatic Sellita SW200-1", "Stainless Steel", "Current Production", 700),
        ("Longines", "Legend Diver", "L3.774.4.50.0",
         "Automatic Cal. L888.5", "Stainless Steel", "Current Production", 2300),
        ("Longines", "Master Collection Moon Phase", "L2.773.4.78.3",
         "Automatic Cal. L899", "Stainless Steel", "Current Production", 2800),
        ("Hamilton", "Intra-Matic Auto Chrono", "H38416711",
         "Automatic Cal. H-31", "Stainless Steel", "Current Production", 2200),
        ("Junghans", "Meister Chronoscope", "027/4120.02",
         "Automatic J880.2", "Stainless Steel", "Current Production", 1800),
        ("Tissot", "Gentleman Powermatic 80 Silicium", "T127.407.11.041.00",
         "Automatic Powermatic 80", "Stainless Steel", "Current Production", 550),
    ]


def _additional_haute_horlogerie_watches() -> list[tuple]:
    """10 additional haute horlogerie — Zeitwerk, RM, FPJ, Moser, De Bethune, etc."""
    return [
        ("A. Lange & Sohne", "Zeitwerk", "140.032",
         "Manual Cal. L043.1", "18k Rose Gold", "Current Production", 75000),
        ("A. Lange & Sohne", "Datograph Up/Down", "405.031",
         "Manual Cal. L951.6", "Platinum", "Current Production", 85000),
        ("H. Moser & Cie", "Swiss Alp Watch Concept Black", "5324-1200",
         "Manual Cal. HMC 324", "Stainless Steel", "Limited Edition", 25000),
        ("H. Moser & Cie", "Pioneer Centre Seconds Mega Cool", "3200-1214",
         "Automatic Cal. HMC 200", "Stainless Steel", "Current Production", 10500),
        ("Vacheron Constantin", "Overseas Dual Time", "7900V/110A-B334",
         "Automatic Cal. 5110 DT", "Stainless Steel", "Current Production", 28000),
        ("Vacheron Constantin", "Traditionnelle Tourbillon", "6000T/000R-B346",
         "Manual Cal. 2160", "18k Rose Gold", "Current Production", 150000),
        ("Cartier", "Crash", "WGCH0080",
         "Manual Cal. 8970 MC", "18k Rose Gold", "Limited Edition", 60000),
        ("Cartier", "Drive de Cartier Extra-Flat", "WSNM0015",
         "Automatic Cal. 430 MC", "18k Rose Gold", "Current Production", 15000),
        ("Breguet", "Classique 5177", "5177BB/2Y/9V6",
         "Automatic Cal. 777Q", "18k White Gold", "Current Production", 20000),
        ("Breguet", "Tradition 7097", "7097BB/G1/9WU",
         "Automatic Cal. 505 Q1", "18k White Gold", "Current Production", 28000),
    ]


def _seiko_expansion_watches() -> list[tuple]:
    """12 additional Seiko watches — Prospex, Presage, 5 Sports, vintage."""
    return [
        ("Seiko", "Prospex 1965 Diver Re-Issue", "SPB143J1", "Automatic 6R35", "Stainless Steel",
         "Current Production", 950),
        ("Seiko", "Prospex 1968 Diver Re-Issue", "SPB187J1", "Automatic 6R35", "Stainless Steel",
         "Current Production", 1100),
        ("Seiko", "Prospex Willard", "SPB151J1", "Automatic 6R35", "Stainless Steel",
         "Current Production", 1050),
        ("Seiko", "Presage Sharp Edged", "SPB167J1", "Automatic 6R35", "Stainless Steel",
         "Current Production", 850),
        ("Seiko", "Presage Urushi Byakudan-nuri", "SPB085J1", "Automatic 6R27", "Stainless Steel",
         "Limited Edition", 2200),
        ("Seiko", "5 Sports SKX Sports Style", "SRPD51K1", "Automatic 4R36", "Stainless Steel",
         "Current Production", 220),
        ("Seiko", "5 Sports x Naruto Boruto", "SRPF71K1", "Automatic 4R36", "Stainless Steel",
         "Limited Edition", 550),
        ("Seiko", "Prospex Black Series Monster", "SRPH13K1", "Automatic 4R36", "Stainless Steel",
         "Special Edition", 380),
        ("Seiko", "Vintage 6105-8110 Captain Willard", "6105-8110", "Automatic 6105B", "Stainless Steel",
         "Vintage Pre-1970", 3500),
        ("Seiko", "Vintage Grand Quartz 9943", "9943-8000", "Quartz 9943A", "Stainless Steel",
         "Vintage Pre-1970", 600),
        ("Seiko", "Presage Arita Porcelain", "SPB171J1", "Automatic 6R35", "Stainless Steel",
         "Limited Edition", 1800),
        ("Seiko", "Prospex Speedtimer Solar Chrono", "SSC813P1", "Solar V192", "Stainless Steel",
         "Current Production", 450),
    ]


def _tudor_expansion_watches() -> list[tuple]:
    """10 additional Tudor watches — full Black Bay range and vintage."""
    return [
        ("Tudor", "Black Bay Fifty-Eight Navy Blue", "M79030B-0001", "Automatic MT5402", "Stainless Steel",
         "Current Production", 3400),
        ("Tudor", "Black Bay Ceramic", "M79210CNU-0001", "Automatic MT5602-1U", "Ceramic",
         "Current Production", 4800),
        ("Tudor", "Black Bay S&G", "M79733N-0008", "Automatic MT5612", "Steel/Gold",
         "Current Production", 4200),
        ("Tudor", "Pelagos FXD", "M25707B/23-0001", "Automatic MT5602", "Titanium",
         "Current Production", 4100),
        ("Tudor", "Royal 41mm", "M28600-0005", "Automatic T601", "Stainless Steel",
         "Current Production", 2300),
        ("Tudor", "Black Bay Chrono S&G", "M79363N-0001", "Automatic MT5813", "Steel/Gold",
         "Current Production", 5600),
        ("Tudor", "Vintage Submariner Snowflake", "94010", "Automatic 2484", "Stainless Steel",
         "Vintage Pre-1970", 12000),
        ("Tudor", "Black Bay 41", "M79540-0006", "Automatic MT5601", "Stainless Steel",
         "Current Production", 2800),
        ("Tudor", "Glamour Date", "M55003-0076", "Automatic T600", "Stainless Steel",
         "Current Production", 1800),
        ("Tudor", "Vintage Prince Date-Day", "76214", "Automatic 2836-2", "Stainless Steel",
         "Discontinued Classic", 2200),
    ]


def _tissot_expansion_watches() -> list[tuple]:
    """12 additional Tissot watches — PRX, Seastar, Gentleman, Heritage."""
    return [
        ("Tissot", "PRX Chronograph", "T137.427.11.011.00", "Automatic Valjoux A05.H31", "Stainless Steel",
         "Current Production", 1500),
        ("Tissot", "PRX 35mm Quartz", "T137.210.11.041.00", "Quartz ETA F06.115", "Stainless Steel",
         "Current Production", 350),
        ("Tissot", "PRX Powermatic 80 Green", "T137.407.11.091.01", "Automatic Powermatic 80", "Stainless Steel",
         "Current Production", 650),
        ("Tissot", "Seastar 1000 Powermatic 80", "T120.407.11.041.03", "Automatic Powermatic 80", "Stainless Steel",
         "Current Production", 625),
        ("Tissot", "Seastar 2000 Professional", "T120.607.11.041.01", "Automatic Powermatic 80.111", "Stainless Steel",
         "Current Production", 875),
        ("Tissot", "Le Locle Powermatic 80", "T006.407.11.033.00", "Automatic Powermatic 80", "Stainless Steel",
         "Current Production", 550),
        ("Tissot", "Heritage Visodate", "T118.430.11.271.00", "Automatic Powermatic 80", "Stainless Steel",
         "Current Production", 525),
        ("Tissot", "Gentleman Quartz", "T127.410.11.031.00", "Quartz ETA F06.115", "Stainless Steel",
         "Current Production", 300),
        ("Tissot", "T-Race Chronograph", "T115.417.27.057.00", "Quartz ETA G10.212", "Stainless Steel",
         "Current Production", 475),
        ("Tissot", "Chemin des Tourelles Powermatic 80", "T099.407.11.038.00", "Automatic Powermatic 80", "Stainless Steel",
         "Current Production", 650),
        ("Tissot", "T-Touch Expert Solar II", "T110.420.44.051.00", "Solar-Quartz ETA E49.301", "Titanium",
         "Current Production", 950),
        ("Tissot", "Heritage Navigator 160th Anniversary", "T078.641.16.057.00", "Automatic ETA 2836-2", "Stainless Steel",
         "Limited Edition", 1200),
    ]


def _panerai_expansion_watches() -> list[tuple]:
    """10 additional Panerai watches — Luminor, Submersible, historic."""
    return [
        ("Panerai", "Luminor Base Logo 44mm", "PAM00000", "Manual P.6000", "Stainless Steel",
         "Current Production", 4800),
        ("Panerai", "Luminor Marina Quaranta 40mm", "PAM01270", "Automatic P.900", "Stainless Steel",
         "Current Production", 6500),
        ("Panerai", "Submersible Carbotech 47mm", "PAM01616", "Automatic P.9010", "Carbon",
         "Current Production", 12500),
        ("Panerai", "Luminor GMT Power Reserve", "PAM01033", "Automatic P.9012", "Stainless Steel",
         "Current Production", 8200),
        ("Panerai", "Radiomir Otto Giorni 45mm", "PAM00992", "Manual P.5000", "Stainless Steel",
         "Current Production", 6800),
        ("Panerai", "Submersible Mike Horn Edition", "PAM00984", "Automatic P.9010", "Titanium",
         "Special Edition", 11500),
        ("Panerai", "Luminor Equation of Time", "PAM00670", "Automatic P.2005/E", "Titanium",
         "Limited Edition", 28000),
        ("Panerai", "Mare Nostrum Chrono 42mm", "PAM00716", "Manual OP XXV", "Stainless Steel",
         "Limited Edition", 9500),
        ("Panerai", "Luminor Sealand Year of the Dragon", "PAM00859", "Manual P.5000", "Stainless Steel",
         "Limited Edition", 14000),
        ("Panerai", "Vintage Pre-Vendome 5218-203A", "5218-203A", "Manual Rolex 618", "Stainless Steel",
         "Vintage Pre-1970", 45000),
    ]


def _oris_expansion_watches() -> list[tuple]:
    """10 additional Oris watches — Aquis, Big Crown, ProPilot, Artelier."""
    return [
        ("Oris", "Aquis Date Calibre 400", "01 400 7769 4135", "Automatic Oris 400", "Stainless Steel",
         "Current Production", 2600),
        ("Oris", "Aquis Pro 4000m", "01 400 7767 7754", "Automatic Oris 400", "Titanium",
         "Current Production", 4200),
        ("Oris", "Aquis Whale Shark LE", "01 798 7754 4175", "Automatic SW 200-1", "Stainless Steel",
         "Limited Edition", 2200),
        ("Oris", "Big Crown ProPilot X Calibre 400", "01 400 7778 7153", "Automatic Oris 400", "Titanium",
         "Current Production", 3200),
        ("Oris", "Big Crown ProPilot Altimeter", "01 733 7705 4134", "Automatic SW 200-1", "Stainless Steel",
         "Current Production", 2800),
        ("Oris", "Artelier Calibre 400", "01 400 7763 4051", "Automatic Oris 400", "Stainless Steel",
         "Current Production", 2200),
        ("Oris", "Divers Sixty-Five Cotton Candy", "01 733 7771 4057", "Automatic SW 200-1", "Stainless Steel",
         "Special Edition", 1950),
        ("Oris", "Roberto Clemente LE", "01 733 7766 4185", "Automatic SW 200-1", "Stainless Steel",
         "Limited Edition", 2100),
        ("Oris", "Aquis Date 39.5mm Green", "01 733 7732 4157", "Automatic SW 200-1", "Stainless Steel",
         "Current Production", 1800),
        ("Oris", "ProPilot X Kermit Edition", "01 400 7778 7157", "Automatic Oris 400", "Titanium",
         "Limited Edition", 3500),
    ]


def _hamilton_expansion_watches() -> list[tuple]:
    """10 additional Hamilton watches — Field, Jazzmaster, American Classic."""
    return [
        ("Hamilton", "Khaki Field Auto 38mm", "H70455133", "Automatic H-10", "Stainless Steel",
         "Current Production", 475),
        ("Hamilton", "Khaki Field Titanium Auto", "H70545560", "Automatic H-10", "Titanium",
         "Current Production", 750),
        ("Hamilton", "Khaki Navy Scuba Auto", "H82515130", "Automatic H-10", "Stainless Steel",
         "Current Production", 595),
        ("Hamilton", "Jazzmaster Open Heart Auto", "H32675170", "Automatic H-10", "Stainless Steel",
         "Current Production", 850),
        ("Hamilton", "Jazzmaster Performer Auto Chrono", "H36616130", "Automatic H-31", "Stainless Steel",
         "Current Production", 1595),
        ("Hamilton", "American Classic PSR Digital", "H52414130", "Quartz Digital", "Stainless Steel",
         "Current Production", 745),
        ("Hamilton", "American Classic Boulton Quartz", "H13431553", "Quartz", "Stainless Steel",
         "Current Production", 395),
        ("Hamilton", "Khaki Aviation X-Wind Auto Chrono", "H77616533", "Automatic H-21", "Stainless Steel",
         "Current Production", 1495),
        ("Hamilton", "Ventura XXL Auto", "H24655331", "Automatic H-10", "Stainless Steel",
         "Current Production", 1095),
        ("Hamilton", "Khaki Field Murph 38mm", "H70405730", "Automatic H-10", "Stainless Steel",
         "Special Edition", 895),
    ]


def _citizen_expansion_watches() -> list[tuple]:
    """10 additional Citizen watches — Promaster, Eco-Drive, Series 8."""
    return [
        ("Citizen", "Promaster Aqualand Eco-Drive", "BN2038-01L", "Eco-Drive E168", "Stainless Steel",
         "Current Production", 450),
        ("Citizen", "Promaster Diver 200m Auto", "NY0040-17L", "Automatic 8203", "Stainless Steel",
         "Current Production", 220),
        ("Citizen", "Promaster Nighthawk", "BJ7000-52E", "Eco-Drive E812", "Stainless Steel",
         "Current Production", 280),
        ("Citizen", "Promaster Sky Eco-Drive", "JY8078-52L", "Eco-Drive U680", "Stainless Steel",
         "Current Production", 500),
        ("Citizen", "Series 8 870 Mechanical", "NA1004-87E", "Automatic 0951", "Stainless Steel",
         "Current Production", 900),
        ("Citizen", "Series 8 831 Mechanical", "NA1000-88A", "Automatic 0950", "Stainless Steel",
         "Current Production", 650),
        ("Citizen", "Attesa Eco-Drive GPS", "CC4004-58E", "Eco-Drive F950", "Titanium",
         "Current Production", 1800),
        ("Citizen", "The Citizen Chronomaster AQ4060", "AQ4060-50E", "Eco-Drive A060", "Stainless Steel",
         "Current Production", 2500),
        ("Citizen", "Promaster Tough Eco-Drive", "BN0211-50E", "Eco-Drive E168", "Stainless Steel",
         "Current Production", 350),
        ("Citizen", "Vintage Promaster Aqualand C023", "C023-088069", "Quartz C023", "Stainless Steel",
         "Vintage Pre-1970", 450),
    ]


def _orient_expansion_watches() -> list[tuple]:
    """10 additional Orient watches — Kamasu, Bambino, Star, Sun & Moon."""
    return [
        ("Orient", "Bambino Version 4", "FAC08004D0", "Automatic F6724", "Stainless Steel",
         "Current Production", 160),
        ("Orient", "Bambino Version 1", "FAC00009N0", "Automatic F6724", "Stainless Steel",
         "Current Production", 140),
        ("Orient", "Mako III", "RA-AA0814R19B", "Automatic F6922", "Stainless Steel",
         "Current Production", 220),
        ("Orient", "Ray II", "FAA02005D9", "Automatic F6922", "Stainless Steel",
         "Current Production", 180),
        ("Orient", "Triton Diver", "RA-EL0002B00B", "Automatic F6922", "Stainless Steel",
         "Current Production", 350),
        ("Orient", "Sun & Moon Version 5", "RA-AK0010B10B", "Automatic F6R24", "Stainless Steel",
         "Current Production", 280),
        ("Orient", "Defender II Field", "RA-AK0401L10B", "Automatic F6922", "Stainless Steel",
         "Current Production", 200),
        ("Orient", "Neo 70s Panda Chrono", "WV0041TX", "Solar/Quartz KD00", "Stainless Steel",
         "Discontinued Classic", 350),
        ("Orient", "King Diver 70s Reissue", "RA-AA0D01B1HB", "Automatic F6922", "Stainless Steel",
         "Special Edition", 300),
        ("Orient", "Vintage SK Diver", "EM6Q00", "Automatic 46943", "Stainless Steel",
         "Vintage Pre-1970", 250),
    ]


def _microbrand_watches() -> list[tuple]:
    """25 microbrand watches — Lorier, Halios, Zelos, Squale, Steinhart, Dan Henry, Boldr, Brew."""
    return [
        # Lorier
        ("Lorier", "Neptune Series IV Blue", "NEP-IV-BLU", "Automatic Miyota 90S5", "Stainless Steel",
         "Current Production", 499),
        ("Lorier", "Falcon Series III", "FAL-III-BLK", "Automatic Miyota 90S5", "Stainless Steel",
         "Current Production", 499),
        ("Lorier", "Gemini Chronograph", "GEM-BLU-WHT", "Mecaquartz Seiko VK64", "Stainless Steel",
         "Current Production", 550),
        ("Lorier", "Hyperion GMT", "HYP-GMT-BLK", "Automatic Miyota 9075", "Stainless Steel",
         "Current Production", 599),
        # Halios
        ("Halios", "Seaforth IV Fixed Bezel", "SF-IV-FXD", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 735),
        ("Halios", "Universa Pastel Blue", "UNI-PAS-BLU", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 650),
        ("Halios", "Fairwind Titanium", "FW-TI-BLK", "Automatic Miyota 9015", "Titanium",
         "Current Production", 795),
        # Zelos
        ("Zelos", "Mako V3 300m Bronze", "MAKO-V3-BRZ", "Automatic Miyota 9015", "Bronze",
         "Current Production", 449),
        ("Zelos", "Hammerhead 1000m Ti", "HAM-TI-BLK", "Automatic Miyota 9015", "Titanium",
         "Current Production", 549),
        ("Zelos", "Horizons V2 GMT", "HOR-V2-GMT", "Automatic Miyota 9075", "Stainless Steel",
         "Current Production", 499),
        # Squale
        ("Squale", "1521 Ocean Blue 500m", "1521-026/A", "Automatic ETA 2824-2", "Stainless Steel",
         "Current Production", 890),
        ("Squale", "50 Atmos 1521 Militaire", "1521-026/MIL", "Automatic ETA 2824-2", "Stainless Steel",
         "Special Edition", 950),
        ("Squale", "Matic 600m Grey", "MATIC-GRY", "Automatic ETA 2824-2", "Stainless Steel",
         "Current Production", 1100),
        # Steinhart
        ("Steinhart", "Ocean One 39 Black Ceramic", "103-0735", "Automatic SW 200-1", "Stainless Steel",
         "Current Production", 490),
        ("Steinhart", "Nav B-Uhr 44 Premium", "108-0311", "Automatic SW 200-1", "Stainless Steel",
         "Current Production", 550),
        ("Steinhart", "Ocean One GMT Pepsi", "103-0877", "Automatic SW 330-1", "Stainless Steel",
         "Current Production", 590),
        # Dan Henry
        ("Dan Henry", "1962 Racing Chronograph", "1962-BLK", "Mecaquartz Seiko VK64", "Stainless Steel",
         "Current Production", 250),
        ("Dan Henry", "1964 Gran Turismo Chrono", "1964-WHT", "Mecaquartz Seiko VK64", "Stainless Steel",
         "Current Production", 250),
        ("Dan Henry", "1970 Automatic Diver 40mm", "1970-BLU", "Automatic Miyota 8215", "Stainless Steel",
         "Current Production", 250),
        ("Dan Henry", "1972 Compressor Diver", "1972-BLK", "Automatic Miyota 8215", "Stainless Steel",
         "Current Production", 260),
        # Boldr
        ("Boldr", "Venture Field Titanium", "VNT-TI-GRN", "Automatic Miyota 9015", "Titanium",
         "Current Production", 399),
        ("Boldr", "Expedition Rushmore", "EXP-RSH-BLK", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 349),
        # Brew
        ("Brew", "Retrograph Copper", "RET-COP", "Mecaquartz Seiko VK64", "Stainless Steel",
         "Current Production", 375),
        ("Brew", "Metric Retromatic", "MET-RET-BLK", "Automatic NH35", "Stainless Steel",
         "Current Production", 350),
        ("Brew", "Mastergraph Chronograph", "MAS-BLK", "Mecaquartz Seiko VK64", "Stainless Steel",
         "Current Production", 425),
    ]


def _budget_icon_watches() -> list[tuple]:
    """12 budget icon watches — Bulova, Luminox, Glycine, Invicta."""
    return [
        # Bulova
        ("Bulova", "Lunar Pilot Chronograph", "96B258", "Quartz UHF 262kHz", "Stainless Steel",
         "Current Production", 450),
        ("Bulova", "Precisionist Champlain", "98B153", "Quartz Precisionist", "Stainless Steel",
         "Current Production", 350),
        ("Bulova", "Accutron Spaceview 2020 Re-Issue", "2ES6A001", "Electrostatic N/A", "Stainless Steel",
         "Limited Edition", 1300),
        ("Bulova", "Archive Series Computron", "97C110", "Quartz LED", "Stainless Steel",
         "Current Production", 350),
        # Luminox
        ("Luminox", "Navy SEAL Original 3001", "XS.3001", "Quartz Ronda 715li", "Carbon",
         "Current Production", 280),
        ("Luminox", "Navy SEAL 3051 Blackout", "XS.3051.BO.1", "Quartz Ronda 515", "Carbon",
         "Current Production", 330),
        ("Luminox", "Bear Grylls Survival 3729", "XB.3729", "Quartz Ronda 515", "Carbon",
         "Current Production", 350),
        ("Luminox", "Master Carbon SEAL 3803", "XS.3803C", "Automatic SW 200-1", "Carbon",
         "Current Production", 1200),
        # Glycine
        ("Glycine", "Airman GMT 42", "GL0066", "Automatic GL 293", "Stainless Steel",
         "Current Production", 650),
        ("Glycine", "Combat Sub 42", "GL0076", "Automatic GL 224", "Stainless Steel",
         "Current Production", 450),
        ("Glycine", "Airman No.1 Purist 40mm", "GL0163", "Automatic GL 293", "Stainless Steel",
         "Current Production", 780),
        # Invicta
        ("Invicta", "Pro Diver 8926OB", "8926OB", "Automatic NH35A", "Stainless Steel",
         "Current Production", 75),
    ]


def _japanese_affordable_watches() -> list[tuple]:
    """10 Japanese affordable/mid-range — Kurono Tokyo, Orient Star, Minase."""
    return [
        # Kurono Tokyo
        ("Kurono Tokyo", "Grand Urushi", "KT-GU-01", "Automatic Miyota 90S5", "Stainless Steel",
         "Limited Edition", 2200),
        ("Kurono Tokyo", "Chronograph 2", "KT-CH2-BLK", "Mecaquartz VK63", "Stainless Steel",
         "Limited Edition", 1800),
        ("Kurono Tokyo", "Toki", "KT-TOKI-01", "Automatic Miyota 90S5", "Stainless Steel",
         "Limited Edition", 1600),
        ("Kurono Tokyo", "Shiro", "KT-SHR-01", "Automatic Miyota 90S5", "Stainless Steel",
         "Limited Edition", 1500),
        # Orient Star
        ("Orient Star", "Classic Semi-Skeleton", "RE-AV0B03B", "Automatic F6R44", "Stainless Steel",
         "Current Production", 550),
        ("Orient Star", "Diver 1964 2nd Edition", "RE-AU0307E", "Automatic F6R47", "Stainless Steel",
         "Current Production", 780),
        ("Orient Star", "Heritage Gothic", "RE-AW0005L", "Automatic F6B42", "Stainless Steel",
         "Current Production", 600),
        # Minase
        ("Minase", "Divido HiZ", "VM04-R02SD", "Automatic Citizen 9015", "Stainless Steel",
         "Current Production", 3200),
        ("Minase", "Horizon Year", "VM11-M01WD", "Automatic Citizen 9015", "Stainless Steel",
         "Current Production", 3800),
        ("Minase", "5 Windows MidSize", "VY03-K07SD", "Automatic Citizen 9015", "Stainless Steel",
         "Current Production", 2800),
    ]


def _german_value_watches() -> list[tuple]:
    """14 German value watches — Stowa, Laco, Junkers, MeisterSinger, Archimede."""
    return [
        # Stowa
        ("Stowa", "Flieger Classic 40 No Logo", "FL-CLS-40", "Automatic ETA 2824-2", "Stainless Steel",
         "Current Production", 950),
        ("Stowa", "Marine Original", "MA-ORI-WHT", "Manual Durowe/Unitas 6498", "Stainless Steel",
         "Current Production", 1100),
        ("Stowa", "Antea KS 39", "AN-KS-39", "Automatic ETA 2892-A2", "Stainless Steel",
         "Current Production", 1050),
        # Laco
        ("Laco", "Flieger Original Munster", "861748", "Manual Laco 97", "Stainless Steel",
         "Current Production", 390),
        ("Laco", "Marineuhr Cuxhaven", "862104", "Automatic Miyota 8215", "Stainless Steel",
         "Current Production", 350),
        ("Laco", "Augsburg 39 Type A", "861988", "Automatic Miyota 8215", "Stainless Steel",
         "Current Production", 300),
        # Junkers
        ("Junkers", "Bauhaus 6060-5", "6060-5", "Quartz Miyota 6S21", "Stainless Steel",
         "Current Production", 250),
        ("Junkers", "Hugo Junkers GMT", "6644-2", "Quartz Miyota GL20", "Stainless Steel",
         "Current Production", 280),
        ("Junkers", "Tante Ju Chrono", "6818-1", "Quartz Miyota 6S20", "Stainless Steel",
         "Current Production", 260),
        # MeisterSinger
        ("MeisterSinger", "Perigraph 43mm", "AM1003", "Automatic SW 200-1", "Stainless Steel",
         "Current Production", 1550),
        ("MeisterSinger", "Pangaea Day Date", "PDD903", "Automatic SW 220-1", "Stainless Steel",
         "Current Production", 1850),
        ("MeisterSinger", "No.03 38mm", "AM903", "Automatic ETA 2824-2", "Stainless Steel",
         "Current Production", 1200),
        # Archimede
        ("Archimede", "Pilot 39 H", "UA7929-A3.2H", "Automatic SW 200-1", "Stainless Steel",
         "Current Production", 590),
        ("Archimede", "Outdoor 41 Protect", "UA8239B-A4.1", "Automatic SW 200-1", "Stainless Steel",
         "Current Production", 690),
    ]


def _heritage_revival_watches() -> list[tuple]:
    """12 heritage revival watches — Doxa, Zodiac, Certina, Rado, Mido."""
    return [
        # Doxa
        ("Doxa", "SUB 200 Professional", "799.10.241.10", "Automatic ETA 2824-2", "Stainless Steel",
         "Current Production", 990),
        ("Doxa", "SUB 300 Carbon Divingstar", "822.70.361.20", "Automatic ETA 2824-2", "Carbon",
         "Current Production", 1890),
        ("Doxa", "Army 42mm Bronze", "785.30.031G.23", "Automatic ETA 2824-2", "Bronze",
         "Current Production", 1250),
        # Zodiac
        ("Zodiac", "Super Sea Wolf Compression", "ZO9307", "Automatic STP 1-11", "Stainless Steel",
         "Current Production", 1295),
        ("Zodiac", "Super Sea Wolf GMT", "ZO9403", "Automatic STP 4-13", "Stainless Steel",
         "Current Production", 1395),
        ("Zodiac", "Grandrally Quartz Chrono", "ZO9601", "Quartz", "Stainless Steel",
         "Current Production", 795),
        # Certina
        ("Certina", "DS Action Diver 43mm", "C032.407.11.051.00", "Automatic Powermatic 80", "Stainless Steel",
         "Current Production", 575),
        ("Certina", "DS PH200M", "C036.407.16.040.00", "Automatic Powermatic 80", "Stainless Steel",
         "Current Production", 690),
        # Rado
        ("Rado", "Captain Cook Automatic 42mm", "R32505203", "Automatic Powermatic 80", "Stainless Steel",
         "Current Production", 1150),
        ("Rado", "True Thinline", "R27957152", "Quartz", "Ceramic",
         "Current Production", 1100),
        # Mido
        ("Mido", "Ocean Star 200 Anniversary", "M026.430.44.061.00", "Automatic Caliber 80", "Titanium",
         "Special Edition", 1050),
        ("Mido", "Baroncelli Heritage", "M027.407.16.010.00", "Automatic Caliber 80", "Stainless Steel",
         "Current Production", 850),
    ]


def _collector_expansion_watches() -> list[tuple]:
    """30 additional collector watches — vintage icons, limited editions, and niche pieces."""
    return [
        # Vintage Omega
        ("Omega", "Vintage Seamaster 600 135.011", "135.011",
         "Manual Cal. 601", "Stainless Steel", "Vintage Pre-1970", 1200),
        ("Omega", "Vintage Geneve Dynamic", "166.039",
         "Automatic Cal. 565", "Stainless Steel", "Vintage Pre-1970", 900),
        ("Omega", "Speedmaster Mark 40 Triple Calendar", "3520.53.00",
         "Automatic Cal. 1151", "Stainless Steel", "Discontinued Classic", 3200),
        # Vintage Seiko
        ("Seiko", "Vintage Bellmatic 4006-6011", "4006-6011",
         "Automatic Cal. 4006A", "Stainless Steel", "Vintage Pre-1970", 400),
        ("Seiko", "Vintage Lord Marvel 36000", "5740-8000",
         "Automatic Hi-Beat Cal. 5740C", "Stainless Steel", "Vintage Pre-1970", 350),
        # Breitling vintage
        ("Breitling", "Vintage Top Time Ref. 2002", "2002",
         "Manual Cal. Venus 178", "Stainless Steel", "Vintage Pre-1970", 6000),
        ("Breitling", "Vintage Chrono-Matic Ref. 2110", "2110",
         "Automatic Cal. 11", "Stainless Steel", "Vintage Pre-1970", 8000),
        # IWC vintage
        ("IWC", "Vintage Ingenieur Ref. 666", "666AD",
         "Automatic Cal. 8541B", "Stainless Steel", "Vintage Pre-1970", 5500),
        # Cartier limited
        ("Cartier", "Santos-Dumont La Demoiselle LE", "WSSA0032",
         "Manual Cal. 430 MC", "Stainless Steel", "Limited Edition", 9500),
        # Tudor vintage
        ("Tudor", "Vintage Submariner Blue Snowflake 94110", "94110",
         "Automatic Cal. 2784", "Stainless Steel", "Vintage Pre-1970", 15000),
        # Longines heritage
        ("Longines", "Heritage Classic Sector Dial", "L2.828.4.53.2",
         "Automatic Cal. L893.5", "Stainless Steel", "Current Production", 2100),
        ("Longines", "Heritage Military 1938", "L2.826.4.53.2",
         "Automatic Cal. L888.5", "Stainless Steel", "Limited Edition", 2400),
        # Zenith vintage
        ("Zenith", "Vintage A384 Original 1969", "A384-69",
         "Automatic Cal. 3019 PHC", "Stainless Steel", "Vintage Pre-1970", 20000),
        # JLC vintage
        ("Jaeger-LeCoultre", "Vintage Memovox Deep Sea", "E857",
         "Automatic Cal. K825", "Stainless Steel", "Vintage Pre-1970", 12000),
        # Bulova vintage
        ("Bulova", "Vintage Accutron Spaceview 1963", "214-M6",
         "Tuning Fork Cal. 214", "Stainless Steel", "Vintage Pre-1970", 1800),
        # Sinn special
        ("Sinn", "140 Space Chronograph", "140.020",
         "Automatic Lemania 5100", "Stainless Steel", "Discontinued Classic", 5500),
        # Vostok special
        ("Vostok", "Komandirskie Classic 431", "431307",
         "Manual Cal. 2414A", "Stainless Steel", "Current Production", 45),
        # Doxa vintage
        ("Doxa", "Vintage SUB 300T Aqua Lung", "SUB300T-AL",
         "Automatic ETA 2452", "Stainless Steel", "Vintage Pre-1970", 4500),
        # Breguet expansion
        ("Breguet", "Marine 5517", "5517TI/Y1/9ZU",
         "Automatic Cal. 777Q", "Titanium", "Current Production", 16000),
        ("Breguet", "Type XX Chronograph 2024", "2067ST/92/3WU",
         "Automatic Cal. 584 Q/2", "Stainless Steel", "Current Production", 15000),
        # Girard-Perregaux
        ("Girard-Perregaux", "Laureato 42mm Blue", "81010-11-431-11A",
         "Automatic Cal. GP01800", "Stainless Steel", "Current Production", 12000),
        # Glashutte Original
        ("Glashutte Original", "Senator Excellence", "1-36-01-01-02-70",
         "Automatic Cal. 36-01", "Stainless Steel", "Current Production", 8500),
        # Blancpain
        ("Blancpain", "Fifty Fathoms Automatique", "5015-1130-52A",
         "Automatic Cal. 1315", "Stainless Steel", "Current Production", 14000),
        ("Blancpain", "Fifty Fathoms Bathyscaphe", "5000-1110-B52A",
         "Automatic Cal. 1315", "Stainless Steel", "Current Production", 11000),
        # Chopard
        ("Chopard", "Alpine Eagle 41mm", "298600-3001",
         "Automatic Cal. 01.01-C", "Stainless Steel", "Current Production", 11500),
        # Piaget
        ("Piaget", "Polo Date 42mm", "G0A46018",
         "Automatic Cal. 1110P", "Stainless Steel", "Current Production", 14000),
        # Ulysse Nardin
        ("Ulysse Nardin", "Diver 42mm", "8163-175-7M/92",
         "Automatic Cal. UN-816", "Stainless Steel", "Current Production", 6500),
        # Bell & Ross
        ("Bell & Ross", "BR 05 Blue Steel", "BR05A-BLU-ST/SST",
         "Automatic Cal. BR-CAL.321", "Stainless Steel", "Current Production", 4700),
        # Frederique Constant
        ("Frederique Constant", "Highlife Perpetual Calendar", "FC-775N4NH6B",
         "Automatic Cal. FC-775", "Stainless Steel", "Current Production", 3500),
        # Baume & Mercier
        ("Baume & Mercier", "Riviera Automatic 42mm", "M0A10616",
         "Automatic Cal. Baumatic BM13-1975A", "Stainless Steel", "Current Production", 3200),
    ]


def _niche_independent_watches() -> list[tuple]:
    """10 niche independent watches — Yema, Norqain, Farer, Formex."""
    return [
        # Yema
        ("Yema", "Superman 500 GMT", "YSUP22GM-AMS", "Automatic Yema2000 GMT", "Stainless Steel",
         "Current Production", 1250),
        ("Yema", "Navygraf Marine Nationale", "YNAV2021-AMS", "Automatic Yema2000", "Stainless Steel",
         "Current Production", 750),
        ("Yema", "Spacegraf ZERO-G Chrono", "YMHF2021-AMS", "Mecaquartz Seiko VK63", "Stainless Steel",
         "Current Production", 650),
        # Norqain
        ("Norqain", "Freedom 60 GMT", "N2200S22C/IA221/20BPR.18S", "Automatic Kenissi NN20/2", "Stainless Steel",
         "Current Production", 2950),
        ("Norqain", "Adventure Sport DLC", "N1000C01A/B101/10BRO.18S", "Automatic NN20/1", "Stainless Steel",
         "Current Production", 2400),
        # Farer
        ("Farer", "Lander IV GMT", "LAN-IV-BLU", "Automatic SW 330-2", "Stainless Steel",
         "Current Production", 1195),
        ("Farer", "Carnegie Chronograph", "CRN-CHR-WHT", "Automatic SW 510 BH", "Stainless Steel",
         "Current Production", 1395),
        # Formex
        ("Formex", "Reef 42 Chronometer COSC", "2200.1.6341.100", "Automatic SW 200-1 COSC", "Stainless Steel",
         "Current Production", 1090),
        ("Formex", "Essence 43 Leggera Chrono", "0330.1.6321.100", "Mecaquartz ETA 251.272", "Carbon",
         "Current Production", 990),
        ("Formex", "Reef GMT Automatic", "2202.1.5341.100", "Automatic SW 330-2", "Stainless Steel",
         "Current Production", 1290),
    ]


def _expanded_batch_premium_brands() -> list[tuple]:
    """50 additional watches — Grand Seiko, Tudor, Cartier, IWC, Breitling, Nomos, Bell & Ross, Longines."""
    return [
        # ── Grand Seiko (8) ────────────────────────────────────────────────
        ("Grand Seiko", "Spring Drive Snowflake SBGA211", "SBGA211",
         "Spring Drive Cal. 9R65", "Titanium", "Current Production", 5800),
        ("Grand Seiko", "Hi-Beat GMT SBGJ201", "SBGJ201",
         "Automatic Hi-Beat Cal. 9S86", "Stainless Steel", "Current Production", 6200),
        ("Grand Seiko", "Heritage Collection SBGH271 Seasons Autumn", "SBGH271",
         "Automatic Hi-Beat Cal. 9S85", "Stainless Steel", "Limited Edition", 6800),
        ("Grand Seiko", "Heritage Collection SBGY007 Omiwatari", "SBGY007",
         "Spring Drive Cal. 9R02", "Platinum", "Limited Edition", 28000),
        ("Grand Seiko", "Elegance SBGK005 Mt. Iwate", "SBGK005",
         "Manual Cal. 9S63", "Stainless Steel", "Current Production", 5500),
        ("Grand Seiko", "Sport Collection SBGE257 Spring Drive GMT", "SBGE257",
         "Spring Drive Cal. 9R66", "Stainless Steel", "Current Production", 6000),
        ("Grand Seiko", "Heritage Collection SBGA413 Shunbun", "SBGA413",
         "Spring Drive Cal. 9R65", "Stainless Steel", "Limited Edition", 6500),
        ("Grand Seiko", "Evolution 9 SLGA007 White Birch", "SLGA007",
         "Spring Drive Cal. 9RA2", "Stainless Steel", "Current Production", 9200),

        # ── Tudor (8) ─────────────────────────────────────────────────────
        ("Tudor", "Black Bay 58 925 Silver", "M79010SG-0001",
         "Automatic Cal. MT5400", "Silver", "Current Production", 4200),
        ("Tudor", "Black Bay 58 Navy Blue", "M79030B-0001",
         "Automatic Cal. MT5402", "Stainless Steel", "Current Production", 3800),
        ("Tudor", "Pelagos FXD Marine Nationale", "M25707B/23-0001",
         "Automatic Cal. MT5602", "Titanium", "Special Edition", 4500),
        ("Tudor", "Pelagos 39 Black", "M25407N-0001",
         "Automatic Cal. MT5400", "Titanium", "Current Production", 4100),
        ("Tudor", "Ranger 39mm", "M79950-0001",
         "Automatic Cal. MT5402", "Stainless Steel", "Current Production", 3100),
        ("Tudor", "Black Bay Pro GMT", "M79470-0001",
         "Automatic Cal. MT5652", "Stainless Steel", "Current Production", 3900),
        ("Tudor", "Black Bay Chrono S&G", "M79363N-0001",
         "Automatic Cal. MT5813", "Steel/Gold", "Current Production", 5800),
        ("Tudor", "Black Bay 54 37mm", "M79000N-0001",
         "Automatic Cal. MT5400", "Stainless Steel", "Current Production", 3600),

        # ── Cartier (6) ───────────────────────────────────────────────────
        ("Cartier", "Santos de Cartier Medium Steel", "WSSA0029",
         "Automatic Cal. 1847 MC", "Stainless Steel", "Current Production", 7200),
        ("Cartier", "Santos de Cartier Large Two-Tone", "W2SA0006",
         "Automatic Cal. 1847 MC", "Steel/Gold", "Current Production", 11500),
        ("Cartier", "Tank Française Medium Steel", "WSTA0065",
         "Automatic Cal. 1853 MC", "Stainless Steel", "Current Production", 5800),
        ("Cartier", "Tank Française Small Steel Quartz", "WSTA0064",
         "Quartz Cal. 057", "Stainless Steel", "Current Production", 4200),
        ("Cartier", "Tank Must Large SolarBeat", "WSTA0055",
         "Quartz SolarBeat Cal. 1", "Stainless Steel", "Current Production", 3100),
        ("Cartier", "Pasha de Cartier 41mm Chronograph", "WSPA0018",
         "Automatic Cal. 1904-CH MC", "Stainless Steel", "Current Production", 9500),

        # ── IWC (6) ───────────────────────────────────────────────────────
        ("IWC", "Portugieser Automatic 40", "IW358305",
         "Automatic Cal. 82200", "Stainless Steel", "Current Production", 7500),
        ("IWC", "Portugieser Chronograph", "IW371617",
         "Automatic Cal. 69355", "Stainless Steel", "Current Production", 8900),
        ("IWC", "Big Pilot 43mm", "IW329303",
         "Automatic Cal. 82100", "Stainless Steel", "Current Production", 9200),
        ("IWC", "Pilot's Watch Mark XX", "IW328203",
         "Automatic Cal. 32111", "Stainless Steel", "Current Production", 5400),
        ("IWC", "Spitfire Pilot Chronograph 41mm", "IW387903",
         "Automatic Cal. 69385", "Stainless Steel", "Current Production", 6800),
        ("IWC", "Pilot's Watch Chronograph Top Gun Ceratanium", "IW389101",
         "Automatic Cal. 69380", "Ceramic", "Current Production", 10500),

        # ── Breitling (6) ─────────────────────────────────────────────────
        ("Breitling", "Navitimer B01 Chronograph 43", "AB0138211B1P1",
         "Automatic Cal. B01", "Stainless Steel", "Current Production", 8900),
        ("Breitling", "Navitimer Automatic 41", "A17326211C1P4",
         "Automatic Cal. B17", "Stainless Steel", "Current Production", 5200),
        ("Breitling", "Superocean Heritage 57 Capsule", "A10370161C1X1",
         "Automatic Cal. B10", "Stainless Steel", "Limited Edition", 5800),
        ("Breitling", "Superocean Heritage 42 Blue", "AB2010161C1S1",
         "Automatic Cal. B20", "Stainless Steel", "Current Production", 5400),
        ("Breitling", "Chronomat B01 42 Green Dial", "AB0134101L1A1",
         "Automatic Cal. B01", "Stainless Steel", "Current Production", 8200),
        ("Breitling", "Premier B01 Chronograph 42 Norton", "AB0118A21G1X2",
         "Automatic Cal. B01", "Stainless Steel", "Special Edition", 6800),

        # ── Nomos (6) ─────────────────────────────────────────────────────
        ("Nomos", "Tangente 35mm", "139",
         "Manual Cal. Alpha", "Stainless Steel", "Current Production", 1580),
        ("Nomos", "Tangente Neomatik 41 Update", "180",
         "Automatic Cal. DUW 6101", "Stainless Steel", "Current Production", 3200),
        ("Nomos", "Club Campus 36 Night", "712",
         "Manual Cal. Alpha", "Stainless Steel", "Current Production", 1320),
        ("Nomos", "Club Campus 38.5 Electric Blue", "730",
         "Manual Cal. Alpha", "Stainless Steel", "Current Production", 1440),
        ("Nomos", "Metro Neomatik 41 Update", "1106",
         "Automatic Cal. DUW 6101", "Stainless Steel", "Current Production", 3600),
        ("Nomos", "Zurich Weltzeit Nachtblau", "807",
         "Automatic Cal. DUW 5201", "Stainless Steel", "Current Production", 4800),

        # ── Bell & Ross (5) ───────────────────────────────────────────────
        ("Bell & Ross", "BR 03-92 Diver Blue Bronze", "BR0392-D-LU-BR/SCA",
         "Automatic Cal. BR-CAL.302", "Bronze", "Limited Edition", 4200),
        ("Bell & Ross", "BR 03-92 Nightlum", "BR0392-IDC-CE/SRB",
         "Automatic Cal. BR-CAL.302", "Ceramic", "Current Production", 3800),
        ("Bell & Ross", "BR 05 Skeleton Blue", "BR05A-BLU-SKST/SST",
         "Automatic Cal. BR-CAL.322", "Stainless Steel", "Current Production", 6200),
        ("Bell & Ross", "BR V2-93 GMT Blue", "BRV293-BLU-ST/SST",
         "Automatic Cal. BR-CAL.303", "Stainless Steel", "Current Production", 3200),
        ("Bell & Ross", "BR 03-92 MA-1 Bomber Jacket", "BR0392-KHA-ST/SCA",
         "Automatic Cal. BR-CAL.302", "Stainless Steel", "Special Edition", 3600),

        # ── Longines (5) ──────────────────────────────────────────────────
        ("Longines", "Spirit Zulu Time 42mm Blue", "L3.812.4.93.6",
         "Automatic Cal. L844.2 (COSC)", "Stainless Steel", "Current Production", 2950),
        ("Longines", "Spirit 40mm Green Dial", "L3.810.4.03.6",
         "Automatic Cal. L888.4 (COSC)", "Stainless Steel", "Current Production", 2350),
        ("Longines", "Legend Diver 42mm Bronze", "L3.774.1.50.2",
         "Automatic Cal. L888.5", "Bronze", "Current Production", 2750),
        ("Longines", "Legend Diver 36mm Blue", "L3.374.4.90.2",
         "Automatic Cal. L592.4", "Stainless Steel", "Current Production", 2200),
        ("Longines", "Ultra-Chron 43mm Diver Reissue", "L2.836.4.52.9",
         "Automatic Cal. L836.6 Hi-Beat", "Stainless Steel", "Current Production", 3050),
    ]


def _expansion_round2_watches() -> list[tuple]:
    """55+ additional watches — G-Shock collabs, MoonSwatch, Seiko Presage, Orient Star,
    Tissot PRX, Hamilton Khaki, Citizen Promaster, Timex collabs."""
    return [
        # ── Casio G-Shock Collaborations (10) ────────────────────────────
        ("G-Shock", "DW-5600 x Porter Yoshida", "DW-5600VT",
         "Quartz Module 3229", "Resin", "Limited Edition", 380),
        ("G-Shock", "GA-2100 x Aim Leon Dore", "GA-2100ALD-7A",
         "Quartz Module 5611", "Resin", "Limited Edition", 450),
        ("G-Shock", "DW-6900 x Stussy 30th Anniversary", "DW-6900STUSSY-1",
         "Quartz Module 3230", "Resin", "Limited Edition", 420),
        ("G-Shock", "GM-2100 x John Mayer Ref. 6557", "GM-2100JM",
         "Quartz Module 5611", "Stainless Steel", "Limited Edition", 500),
        ("G-Shock", "DW-5600 x Medicom Toy Bearbrick", "DW-5600BE-1",
         "Quartz Module 3229", "Resin", "Limited Edition", 320),
        ("G-Shock", "GA-110 x Dragon Ball Z Frieza", "GA-110FRZ-4A",
         "Quartz Module 5146", "Resin", "Limited Edition", 380),
        ("G-Shock", "DW-5600 x Huf SF", "DW-5600HUF-1",
         "Quartz Module 3229", "Resin", "Limited Edition", 350),
        ("G-Shock", "MR-G x Bruce Lee", "MRGB5000BA-1",
         "Tough Solar Module 3496", "Titanium", "Limited Edition", 4200),
        ("G-Shock", "GA-2100 x CLOT Kevin Poon", "GA-2100CLOT",
         "Quartz Module 5611", "Resin", "Limited Edition", 380),
        ("G-Shock", "GMW-B5000 x Eric Haze", "GMW-B5000EH-1",
         "Tough Solar Module 3459", "Stainless Steel", "Limited Edition", 700),

        # ── Swatch MoonSwatch Collection (8) ─────────────────────────────
        ("Swatch", "MoonSwatch Mission to Moonshine Gold Moon", "SO33W700",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 400),
        ("Swatch", "MoonSwatch Mission to Mars Snoopy", "SO33R700",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 550),
        ("Swatch", "MoonSwatch Full Moon", "SO33K100",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 360),
        ("Swatch", "MoonSwatch New Moon", "SO33B100",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 340),
        ("Swatch", "MoonSwatch Mission to the Moon Bioceramic", "SO33M700",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 450),
        ("Swatch", "MoonSwatch Mission to Neptune Blue", "SO33N700",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 380),
        ("Swatch", "MoonSwatch Mission to Saturn Gold", "SO33T700",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 370),
        ("Swatch", "MoonSwatch Mission to Mercury Brown", "SO33A700",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 350),

        # ── Seiko Presage (8) ────────────────────────────────────────────
        ("Seiko", "Presage Cocktail Time Blue Moon", "SRPB43J1",
         "Automatic Cal. 4R35", "Stainless Steel", "Current Production", 370),
        ("Seiko", "Presage Cocktail Time Starlight", "SSA361J1",
         "Automatic Cal. 4R57", "Stainless Steel", "Current Production", 420),
        ("Seiko", "Presage Cocktail Time Manhattan", "SSA346J1",
         "Automatic Cal. 4R57", "Stainless Steel", "Current Production", 400),
        ("Seiko", "Presage Style60s Ruby", "SSA431J1",
         "Automatic Cal. 4R35", "Stainless Steel", "Current Production", 380),
        ("Seiko", "Presage Craftsmanship Shippo Enamel", "SPB293J1",
         "Automatic Cal. 6R35", "Stainless Steel", "Limited Edition", 1500),
        ("Seiko", "Presage Sharp Edged Midnight", "SPB205J1",
         "Automatic Cal. 6R35", "Stainless Steel", "Current Production", 900),
        ("Seiko", "Presage Zen Garden", "SRPF39J1",
         "Automatic Cal. 4R35", "Stainless Steel", "Current Production", 350),
        ("Seiko", "Presage Star Bar Honeycomb", "SARY171",
         "Automatic Cal. 4R35", "Stainless Steel", "Limited Edition", 480),

        # ── Orient Star (7) ──────────────────────────────────────────────
        ("Orient Star", "Skeleton Mechanical", "RE-AZ0001S",
         "Automatic F6R44", "Stainless Steel", "Current Production", 650),
        ("Orient Star", "Avant-Garde Skeleton", "RE-AV0A01B",
         "Automatic F6R44", "Stainless Steel", "Current Production", 750),
        ("Orient Star", "M45 F7 Mechanical Moon Phase", "RE-AY0107N",
         "Automatic F7M64", "Stainless Steel", "Current Production", 1200),
        ("Orient Star", "Sports Diver 200m ISO", "RE-AU0302L",
         "Automatic F6N47", "Stainless Steel", "Current Production", 600),
        ("Orient Star", "Retrograde Day Indicator", "RE-DE0001L",
         "Automatic F6R24", "Stainless Steel", "Current Production", 550),
        ("Orient Star", "Classic Power Reserve", "RE-AW0004S",
         "Automatic F6R44", "Stainless Steel", "Current Production", 500),
        ("Orient Star", "Layered Skeleton", "RE-AV0B08Y",
         "Automatic F6R44", "Stainless Steel", "Limited Edition", 850),

        # ── Tissot PRX Variations (7) ────────────────────────────────────
        ("Tissot", "PRX Powermatic 80 Ice Blue", "T137.407.11.351.00",
         "Automatic Powermatic 80", "Stainless Steel", "Current Production", 650),
        ("Tissot", "PRX Powermatic 80 Damian Lillard", "T137.407.11.041.01",
         "Automatic Powermatic 80", "Stainless Steel", "Special Edition", 700),
        ("Tissot", "PRX Digital 35mm", "T137.263.11.050.00",
         "Quartz Digital", "Stainless Steel", "Current Production", 375),
        ("Tissot", "PRX Powermatic 80 Rose Gold Tone", "T137.407.33.031.00",
         "Automatic Powermatic 80", "Steel/Gold", "Current Production", 700),
        ("Tissot", "PRX 40 205 Black", "T137.407.11.051.00",
         "Automatic Powermatic 80", "Stainless Steel", "Current Production", 650),
        ("Tissot", "PRX Chronograph Quartz Blue", "T137.417.11.041.00",
         "Quartz ETA G10.212", "Stainless Steel", "Current Production", 475),
        ("Tissot", "PRX 35mm Powermatic 80 Ladies", "T137.207.11.041.00",
         "Automatic Powermatic 80", "Stainless Steel", "Current Production", 600),

        # ── Hamilton Khaki Models (5) ────────────────────────────────────
        ("Hamilton", "Khaki Field Mechanical 38mm White", "H69439511",
         "Manual Cal. H-50", "Stainless Steel", "Current Production", 475),
        ("Hamilton", "Khaki Field Auto Chrono", "H71616535",
         "Automatic Cal. H-21", "Stainless Steel", "Current Production", 1695),
        ("Hamilton", "Khaki Navy Pioneer Small Second", "H78415733",
         "Automatic Cal. H-10", "Stainless Steel", "Current Production", 895),
        ("Hamilton", "Khaki Field Expedition Auto 41mm", "H70315510",
         "Automatic Cal. H-10", "Stainless Steel", "Current Production", 695),
        ("Hamilton", "Khaki Aviation Converter Auto", "H76635730",
         "Automatic Cal. H-10", "Stainless Steel", "Current Production", 995),

        # ── Citizen Promaster (5) ────────────────────────────────────────
        ("Citizen", "Promaster Marine Eco-Drive 200m", "BN0191-55L",
         "Eco-Drive Cal. E168", "Stainless Steel", "Current Production", 250),
        ("Citizen", "Promaster Altichron Eco-Drive", "BN4021-02E",
         "Eco-Drive Cal. J280", "Stainless Steel", "Current Production", 600),
        ("Citizen", "Promaster Sky Blue Angels", "JY8128-56L",
         "Eco-Drive Cal. U680", "Stainless Steel", "Special Edition", 550),
        ("Citizen", "Promaster Fugu Limited Edition", "NY0098-84E",
         "Automatic Cal. 8204", "Stainless Steel", "Limited Edition", 350),
        ("Citizen", "Promaster Tough Land Eco-Drive", "BN0217-02E",
         "Eco-Drive Cal. E168", "Stainless Steel", "Current Production", 300),

        # ── Timex Collaborations (5) ─────────────────────────────────────
        ("Timex", "Q Timex x Seconde/Seconde/ Degrade", "TW2W24500",
         "Quartz", "Stainless Steel", "Limited Edition", 220),
        ("Timex", "Timex x Todd Snyder Marlin Jet Black", "TW2U11800",
         "Automatic Miyota 8215", "Stainless Steel", "Limited Edition", 280),
        ("Timex", "Timex x Peanuts Marlin Automatic Snoopy Tennis", "TW2U71300",
         "Automatic Miyota 8215", "Stainless Steel", "Special Edition", 270),
        ("Timex", "Timex x Giorgio Galli S2T Automatic", "TW2V62100",
         "Automatic Miyota 82S5", "Stainless Steel", "Current Production", 395),
        ("Timex", "Q Timex x Space Invaders", "TW2V39800",
         "Quartz", "Stainless Steel", "Limited Edition", 200),
    ]


# ---------------------------------------------------------------------------
# Assemble full catalog
# ---------------------------------------------------------------------------

def get_curated_catalog() -> list[dict]:
    """Return the full curated watch catalog as a list of dicts.

    Each dict has keys: brand, model, reference, movement, material,
    watch_type, price_eur.
    """
    all_tuples: list[tuple] = []
    all_tuples.extend(_rolex_watches())
    all_tuples.extend(_omega_watches())
    all_tuples.extend(_seiko_watches())
    all_tuples.extend(_tudor_watches())
    all_tuples.extend(_casio_gshock_watches())
    all_tuples.extend(_patek_philippe_watches())
    all_tuples.extend(_audemars_piguet_watches())
    all_tuples.extend(_affordable_watches())
    all_tuples.extend(_independent_watches())
    all_tuples.extend(_vintage_icon_watches())
    all_tuples.extend(_vacheron_constantin_watches())
    all_tuples.extend(_cartier_watches())
    all_tuples.extend(_lange_sohne_watches())
    all_tuples.extend(_iwc_watches())
    all_tuples.extend(_breitling_watches())
    all_tuples.extend(_jlc_watches())
    all_tuples.extend(_timex_watches())
    all_tuples.extend(_zenith_watches())
    all_tuples.extend(_panerai_watches())
    all_tuples.extend(_luxury_expansion_watches())
    all_tuples.extend(_rolex_expansion_watches())
    all_tuples.extend(_omega_expansion_watches())
    all_tuples.extend(_grand_seiko_expansion_watches())
    all_tuples.extend(_richard_mille_watches())
    all_tuples.extend(_fp_journe_watches())
    all_tuples.extend(_mbf_watches())
    all_tuples.extend(_swatch_moonswatch_watches())
    all_tuples.extend(_gshock_collab_watches())
    all_tuples.extend(_additional_independents_watches())
    all_tuples.extend(_additional_haute_horlogerie_watches())
    all_tuples.extend(_seiko_expansion_watches())
    all_tuples.extend(_tudor_expansion_watches())
    all_tuples.extend(_tissot_expansion_watches())
    all_tuples.extend(_panerai_expansion_watches())
    all_tuples.extend(_oris_expansion_watches())
    all_tuples.extend(_hamilton_expansion_watches())
    all_tuples.extend(_citizen_expansion_watches())
    all_tuples.extend(_orient_expansion_watches())
    all_tuples.extend(_microbrand_watches())
    all_tuples.extend(_budget_icon_watches())
    all_tuples.extend(_japanese_affordable_watches())
    all_tuples.extend(_german_value_watches())
    all_tuples.extend(_heritage_revival_watches())
    all_tuples.extend(_collector_expansion_watches())
    all_tuples.extend(_niche_independent_watches())
    all_tuples.extend(_expanded_batch_premium_brands())
    all_tuples.extend(_expansion_round2_watches())

    catalog: list[dict] = []
    for brand, model, reference, movement, material, watch_type, price_eur in all_tuples:
        catalog.append({
            "brand": brand,
            "model": model,
            "reference": reference,
            "movement": movement,
            "material": material,
            "watch_type": watch_type,
            "price_eur": price_eur,
        })
    return catalog


# ---------------------------------------------------------------------------
# Transform helpers
# ---------------------------------------------------------------------------

def _watch_to_catalog_item(item: dict) -> CatalogItem:
    """Convert a watch dict to a CatalogItem.

    Sets category='watches', item_key from slugify(brand-model-reference),
    brand from the watch brand, set_code from the model name.
    """
    brand = item["brand"]
    model = item["model"]
    reference = item["reference"]
    movement = item["movement"]
    material = item["material"]
    watch_type = item["watch_type"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{brand}-{model}-{reference}"),
        title=f"{brand} {model} ({reference})",
        set_code=model,
        brand=brand,
        rarity=watch_type,
        notes=f"{brand} | {model} | Ref. {reference} | {movement} | {material}",
        attributes_json={
            "reference": reference,
            "movement": movement,
            "material": material,
            "watch_type": watch_type,
        },
    )


def _watch_to_price_observation(item: dict) -> PriceObservation:
    """Convert a watch dict to a PriceObservation.

    Features:
    - condition_score: 0.90 (assumes excellent for catalog baseline)
    - type_score: from WATCH_TYPE_SCORES
    - brand_tier: luxury 0.9, premium 0.7, mid 0.5, affordable 0.3
    - material_score: from MATERIAL_SCORES
    - has_box_papers: 1.0 for luxury/premium brands, 0.0 otherwise
    """
    brand = item["brand"]
    watch_type = item["watch_type"]
    material = item["material"]
    price = item["price_eur"]

    tier = _brand_tier(brand)
    type_sc = _watch_type_score(watch_type)
    mat_sc = _material_score(material)

    # Assume luxury/premium watches come with box + papers for baseline
    has_box = 1.0 if tier >= 0.7 else 0.0

    return PriceObservation(
        features={
            "condition_score": 0.90,
            "type_score": type_sc,
            "brand_tier": tier,
            "material_score": mat_sc,
            "has_box_papers": has_box,
        },
        price=price,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Import curated watch catalog + prices"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Write local files only, skip Supabase upsert")
    parser.add_argument("--jsonl-only", action="store_true",
                        help="Write only training JSONL, skip catalog SQL and Supabase")
    parser.add_argument("--cache-images", action="store_true",
                        help="Cache external image URLs to S3 after import")
    args = parser.parse_args()

    logger.info("=== Watch Import Pipeline ===")

    ingest = SupabaseIngest()
    if args.dry_run or args.jsonl_only:
        ingest.enabled = False

    catalog = get_curated_catalog()
    logger.info(f"  Curated catalog: {len(catalog)} watches")

    all_items = [_watch_to_catalog_item(w) for w in catalog]
    all_observations = [_watch_to_price_observation(w) for w in catalog]

    # Write training JSONL (always)
    write_training_jsonl(CATEGORY, all_observations)
    log_progress(CATEGORY, "training JSONL written", len(all_observations))

    if not args.jsonl_only:
        # Write catalog SQL
        write_catalog_sql(CATEGORY, all_items)
        log_progress(CATEGORY, "catalog SQL written", len(all_items))

        # Cache images to S3 if requested
        if args.cache_images:
            all_items = cache_catalog_images(
                all_items, dry_run=args.dry_run
            )
            log_progress(CATEGORY, "images cached", len(all_items))

        # Upsert to Supabase if enabled
        if ingest.enabled:
            inserted = ingest.upsert_catalog(all_items)
            log_progress(CATEGORY, "catalog upserted", inserted)

    ingest.close()
    close_http_client()

    logger.info(f"\n=== Watch Import Complete ===")
    logger.info(f"  Total catalog items:  {len(all_items)}")
    logger.info(f"  Price observations:   {len(all_observations)}")
    if args.dry_run:
        logger.info("  Mode: DRY RUN (local files only)")
    if args.jsonl_only:
        logger.info("  Mode: JSONL ONLY (training data only)")


if __name__ == "__main__":
    main()
