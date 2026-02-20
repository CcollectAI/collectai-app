"""
Curated Watch Import Pipeline — Luxury, Vintage & Affordable Timepieces.

Imports a curated catalog of 125+ watches across 10 subcategories:
  Rolex, Omega, Seiko, Tudor, Casio/G-Shock, Patek Philippe,
  Audemars Piguet, Affordable Collectibles, Independent/Micro Brands,
  Vintage Icons

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
    # Premium (0.7)
    "Omega": 0.7,
    "Tudor": 0.7,
    "Grand Seiko": 0.7,
    "IWC": 0.7,
    "Jaeger-LeCoultre": 0.7,
    "Zenith": 0.7,
    "Breitling": 0.7,
    "H. Moser & Cie": 0.7,
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
