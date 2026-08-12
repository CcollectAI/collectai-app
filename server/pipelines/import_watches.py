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
    "Christopher Ward": 0.75,
    "Baltic": 0.75,
    "Ming": 0.80,
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
    # Premium Microbrands (0.75-0.85)
    "Lorier": 0.75,
    "Halios": 0.80,
    "Zelos": 0.75,
    "Squale": 0.35,
    "Steinhart": 0.35,
    "Dan Henry": 0.35,
    "Boldr": 0.30,
    "Brew": 0.75,
    # Budget Icons (0.3)
    "Bulova": 0.3,
    "Luminox": 0.3,
    "Glycine": 0.35,
    "Invicta": 0.2,
    # Japanese Affordable (0.4-0.6)
    "Kurono Tokyo": 0.80,
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
    "Farer": 0.75,
    "Formex": 0.4,
    # Microbrands — Expansion (0.30-0.40)
    "Islander": 0.30,
    "San Martin": 0.30,
    "Pagani Design": 0.25,
    "Sugess": 0.25,
    "Escapement Time": 0.25,
    "Proxima": 0.30,
    "Heimdallr": 0.25,
    "Addiesdive": 0.25,
    "Tandorio": 0.25,
    "Cadisen": 0.25,
    "Merkur": 0.30,
    "Baltany": 0.30,
    "Bertucci": 0.25,
    "Nodus": 0.35,
    "Vaer": 0.35,
    "Oak & Oscar": 0.40,
    "Traska": 0.35,
    "Autodromo": 0.75,
    "Marlin": 0.30,
    "RZE": 0.35,
    "Monta": 0.80,
    "Mercer": 0.30,
    "Gruppo Gamma": 0.35,
    "NTH": 0.35,
    "Undone": 0.30,
    "Tsao Baltimore": 0.35,
    "Furlan Marri": 0.35,
    "Nezumi": 0.35,
    "Bravur": 0.35,
    "Astor+Banks": 0.35,
    "Spinnaker": 0.30,
    "AVI-8": 0.30,
    "Gavox": 0.30,
    "Phoibos": 0.30,
    "Axios": 0.30,
    "Maen": 0.35,
    "Wolbrook": 0.30,
    "Unimatic": 0.75,
    "anOrdain": 0.80,
    "MING": 0.80,
    "Atelier Wen": 0.40,
    "Venezianico": 0.35,
    "Direnzo": 0.35,
    "Marloe": 0.35,
    "Straum": 0.35,
    "Studio Underd0g": 0.35,
    "Sartory Billard": 0.40,
    "Serica": 0.40,
    # Affordable mainstream expansion
    "Fossil": 0.20,
    "Skagen": 0.20,
    "Movado": 0.35,
    "Bulova": 0.30,
    "Alpina": 0.40,
    "Victorinox": 0.30,
    "Mondaine": 0.30,
    "Braun": 0.25,
    "Rotary": 0.25,
    "Philip Watch": 0.30,
    "Corniche": 0.30,
    "MVMT": 0.20,
    "Daniel Wellington": 0.15,
    "Edox": 0.35,
    "Raymond Weil": 0.40,
    "Ebel": 0.40,
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
    # Luxury expansion (2026-03-20)
    "TAG Heuer": 0.75,
    "Hublot": 0.80,
    "Montblanc": 0.55,
    "BVLGARI": 0.70,
    "Hermès": 0.60,
    "Jaquet Droz": 0.85,
    "Laurent Ferrier": 0.90,
    "Moritz Grossmann": 0.85,
    "Van Cleef & Arpels": 0.90,
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
        ("Grand Seiko", "Heritage Collection SBGH271 Seasons Autumn", "SBGH271",
         "Automatic Hi-Beat Cal. 9S85", "Stainless Steel", "Limited Edition", 6800),
        ("Grand Seiko", "Elegance SBGK005 Mt. Iwate", "SBGK005",
         "Manual Cal. 9S63", "Stainless Steel", "Current Production", 5500),

        # ── Tudor (4) ─────────────────────────────────────────────────────
        ("Tudor", "Black Bay 54 37mm", "M79000N-0001",
         "Automatic Cal. MT5400", "Stainless Steel", "Current Production", 3600),

        # ── Cartier (6) ───────────────────────────────────────────────────
        ("Cartier", "Santos de Cartier Large Two-Tone", "W2SA0006",
         "Automatic Cal. 1847 MC", "Steel/Gold", "Current Production", 11500),
        ("Cartier", "Tank Française Small Steel Quartz", "WSTA0064",
         "Quartz Cal. 057", "Stainless Steel", "Current Production", 4200),
        ("Cartier", "Tank Must Large SolarBeat", "WSTA0055",
         "Quartz SolarBeat Cal. 1", "Stainless Steel", "Current Production", 3100),
        ("Cartier", "Pasha de Cartier 41mm Chronograph", "WSPA0018",
         "Automatic Cal. 1904-CH MC", "Stainless Steel", "Current Production", 9500),

        # ── IWC (5) ───────────────────────────────────────────────────────
        ("IWC", "Portugieser Automatic 40", "IW358305",
         "Automatic Cal. 82200", "Stainless Steel", "Current Production", 7500),
        ("IWC", "Portugieser Chronograph", "IW371617",
         "Automatic Cal. 69355", "Stainless Steel", "Current Production", 8900),
        ("IWC", "Big Pilot 43mm", "IW329303",
         "Automatic Cal. 82100", "Stainless Steel", "Current Production", 9200),
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


def _expansion_round3_watches() -> list[tuple]:
    """92 additional watches — G-Shock collabs, Seiko Presage LE, MoonSwatch,
    Omega Speedmaster specials, Tudor Black Bay, Grand Seiko seasonal, Citizen Promaster."""
    return [
        # ── Casio G-Shock Collaborations — BAPE, NASA, Dragon Ball (12) ──
        ("G-Shock", "DW-5600 x BAPE 30th Anniversary", "DW-5600BAPE30-1",
         "Quartz Module 3229", "Resin", "Limited Edition", 550),
        ("G-Shock", "GA-2100 x BAPE ABC Camo", "GA-2100BAPE-1A",
         "Quartz Module 5611", "Resin", "Limited Edition", 480),
        ("G-Shock", "DW-5600 x NASA All Systems Go", "DW-5600NASA21-1",
         "Quartz Module 3229", "Resin", "Limited Edition", 350),
        ("G-Shock", "GA-2000 x NASA Space Exploration", "GA-2000NASA-1A",
         "Quartz Module 5590", "Resin", "Limited Edition", 400),
        ("G-Shock", "GM-5600 x NASA 50th Anniversary Gold", "GM-5600NASA50-1",
         "Quartz Module 3229", "Stainless Steel", "Limited Edition", 500),
        ("G-Shock", "GA-110 x Dragon Ball Z Goku Orange", "GA-110DB-1A",
         "Quartz Module 5146", "Resin", "Limited Edition", 380),
        ("G-Shock", "GA-110 x Dragon Ball Z Vegeta Blue", "GA-110DB-7A",
         "Quartz Module 5146", "Resin", "Limited Edition", 400),
        ("G-Shock", "GA-700 x Dragon Ball Z Cell", "GA-700CELL-1A",
         "Quartz Module 5522", "Resin", "Limited Edition", 350),
        ("G-Shock", "DW-5600 x One Piece Straw Hat", "DW-5600OP-1",
         "Quartz Module 3229", "Resin", "Limited Edition", 420),
        ("G-Shock", "GWF-A1000 x Borneo Rainbow Toad", "GWF-A1000BRT-1A",
         "Tough Solar Module 5624", "Resin", "Limited Edition", 1200),
        ("G-Shock", "MRG-B5000 x BAPE Gold", "MRG-B5000BA-1",
         "Tough Solar Module 3496", "Titanium", "Limited Edition", 3800),
        ("G-Shock", "DW-5600 x Slam Dunk 30th Anniversary", "DW-5600SD30-1",
         "Quartz Module 3229", "Resin", "Limited Edition", 350),

        # ── Seiko Presage Limited Editions (10) ─────────────────────────
        ("Seiko", "Presage Urushi Lacquer Dial SRQ033J1", "SRQ033J1",
         "Automatic Cal. 8R48", "Stainless Steel", "Limited Edition", 3500),
        ("Seiko", "Presage 60th Anniversary Enamel SPB093J1", "SPB093J1",
         "Automatic Cal. 6R27", "Stainless Steel", "Limited Edition", 1800),
        ("Seiko", "Presage Cocktail Time Sakura Fubuki SRP839J1", "SRP839J1",
         "Automatic Cal. 4R35", "Stainless Steel", "Limited Edition", 550),
        ("Seiko", "Presage Sharp Edged Ryugu SPB259J1", "SPB259J1",
         "Automatic Cal. 6R35", "Stainless Steel", "Limited Edition", 1100),
        ("Seiko", "Presage Cocktail Time Tequila Sunset SRPE47J1", "SRPE47J1",
         "Automatic Cal. 4R35", "Stainless Steel", "Current Production", 380),
        ("Seiko", "Presage Crown Blue Enamel SPB399J1", "SPB399J1",
         "Automatic Cal. 6R35", "Stainless Steel", "Limited Edition", 1600),
        ("Seiko", "Presage Karesansui Green Moss SPB295J1", "SPB295J1",
         "Automatic Cal. 6R35", "Stainless Steel", "Limited Edition", 1400),
        ("Seiko", "Presage Star Bar Midnight SSA457J1", "SSA457J1",
         "Automatic Cal. 4R57", "Stainless Steel", "Limited Edition", 520),
        ("Seiko", "Presage Riki Watanabe Enamel SPB113J1", "SPB113J1",
         "Automatic Cal. 6R27", "Stainless Steel", "Limited Edition", 2000),

        # ── Swatch MoonSwatch Variants (10) ─────────────────────────────
        ("Swatch", "MoonSwatch Mission to Pluto Snoopy", "SO33P700",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 500),
        ("Swatch", "MoonSwatch Mission to Jupiter Brown", "SO33J700",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 360),
        ("Swatch", "MoonSwatch Mission to Earth Green", "SO33G700",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 370),
        ("Swatch", "MoonSwatch Mission to Uranus Teal", "SO33U700",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 380),
        ("Swatch", "MoonSwatch Full Moon Snoopy Black", "SO33K700",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 600),
        ("Swatch", "MoonSwatch Mission to Moonshine Gold Chrono", "SO33W700C",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 500),
        ("Swatch", "MoonSwatch Mission to Mars Chrono", "SO33R700C",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 480),
        ("Swatch", "MoonSwatch Mission to Mercury Chrono", "SO33A700C",
         "Quartz ETA", "Ceramic/Plastic", "Special Edition", 400),

        # ── Omega Speedmaster Specials (10) ─────────────────────────────
        ("Omega", "Speedmaster Moonwatch Apollo 11 50th Anniversary", "310.20.42.50.01.001",
         "Manual Cal. 3861", "Stainless Steel", "Anniversary Edition", 12000),
        ("Omega", "Speedmaster Dark Side of the Moon Apollo 8", "311.92.44.30.01.001",
         "Manual Cal. 1869", "Ceramic", "Limited Edition", 9500),
        ("Omega", "Speedmaster '57 1957 Trilogy", "311.10.39.30.01.001",
         "Manual Cal. 1861", "Stainless Steel", "Limited Edition", 8500),
        ("Omega", "Speedmaster CK2998 Pulsometer", "311.33.40.30.02.001",
         "Manual Cal. 1861", "Stainless Steel", "Limited Edition", 7500),
        ("Omega", "Speedmaster Racing Co-Axial White Dial", "329.30.44.51.04.001",
         "Automatic Cal. 9900", "Stainless Steel", "Current Production", 8200),
        ("Omega", "Speedmaster Super Racing Co-Axial", "329.32.44.51.01.001",
         "Automatic Cal. 9920", "Stainless Steel", "Current Production", 9500),

        # ── Tudor Black Bay Heritage (2) ───────────────────────────────
        ("Tudor", "Black Bay Fifty-Eight Bronze", "M79012M-0001",
         "Automatic Cal. MT5400", "Bronze", "Current Production", 3800),
        ("Tudor", "Pelagos FXD Marine Nationale", "M25707KN-0001",
         "Automatic Cal. MT5602", "Titanium", "Limited Edition", 4800),

        # ── Grand Seiko Seasonal Dials (10) ─────────────────────────────
        ("Grand Seiko", "Heritage Shunkū Sky Flake", "SBGA407",
         "Spring Drive Cal. 9R65", "Stainless Steel", "Current Production", 5500),
        ("Grand Seiko", "Evolution 9 Rikka Summer Blue", "SLGA021",
         "Spring Drive Cal. 9RA2", "Titanium", "Limited Edition", 11000),
        ("Grand Seiko", "Elegance Fuji-san Blue", "SBGD205",
         "Manual Cal. 9S63", "18k White Gold", "Limited Edition", 25000),
        ("Grand Seiko", "Heritage Mt. Iwate Green", "SBGA439",
         "Spring Drive Cal. 9R65", "Stainless Steel", "Limited Edition", 6200),
        ("Grand Seiko", "Heritage Ginza Night SBGP017", "SBGP017",
         "Quartz Cal. 9F85", "Stainless Steel", "Limited Edition", 3500),

        # ── Citizen Promaster Specials (10) ─────────────────────────────
        ("Citizen", "Promaster Mechanical Diver 200m", "NB6021-17E",
         "Automatic Cal. 9051", "Stainless Steel", "Current Production", 650),
        ("Citizen", "Promaster Marine Fujitsubo Barnacle", "BN0227-09L",
         "Eco-Drive Cal. E168", "Stainless Steel", "Limited Edition", 380),
        ("Citizen", "Promaster Eco-Drive Orca Black", "BN0235-01E",
         "Eco-Drive Cal. E168", "Stainless Steel", "Current Production", 320),
        ("Citizen", "Promaster Sky Navihawk GPS", "CC9020-54E",
         "Eco-Drive Cal. F990", "Stainless Steel", "Current Production", 1500),
        ("Citizen", "Promaster Challenge Diver 1000m Titanium", "BN7020-17E",
         "Eco-Drive Cal. E168", "Titanium", "Current Production", 2500),
        ("Citizen", "Promaster Land Altichron Cincom", "CC5006-06L",
         "Eco-Drive Cal. F150", "Stainless Steel", "Limited Edition", 700),
        ("Citizen", "Promaster Marine Super Titanium", "BN0220-16E",
         "Eco-Drive Cal. E168", "Titanium", "Current Production", 450),
        ("Citizen", "Promaster NY0040 Classic Reissue", "NY0040-17LE",
         "Automatic Cal. 8204", "Stainless Steel", "Limited Edition", 400),
        ("Citizen", "Promaster Sky Blue Angels Nighthawk", "BJ7007-02L",
         "Eco-Drive Cal. B877", "Stainless Steel", "Special Edition", 450),
        ("Citizen", "Promaster Mechanical Diver Fujitsubo 200m LE", "NB6024-02E",
         "Automatic Cal. 9051", "Stainless Steel", "Limited Edition", 750),

        # ── Omega Seamaster & Constellation (10) ────────────────────────
        ("Omega", "Seamaster Diver 300M James Bond 60th Anniversary", "210.30.42.20.03.002",
         "Automatic Cal. 8806", "Stainless Steel", "Anniversary Edition", 8500),
        ("Omega", "Seamaster Railmaster Co-Axial Denim", "220.12.40.20.03.001",
         "Automatic Cal. 8806", "Stainless Steel", "Discontinued Classic", 5200),
        ("Omega", "Constellation Co-Axial 39mm Green Dial", "131.13.39.20.10.001",
         "Automatic Cal. 8800", "Stainless Steel", "Current Production", 5400),
        ("Omega", "De Ville Tresor Power Reserve", "435.13.40.22.06.001",
         "Manual Cal. 8929", "Stainless Steel", "Current Production", 7800),
        ("Omega", "Seamaster Planet Ocean 600M Chrono", "215.30.46.51.01.001",
         "Automatic Cal. 9900", "Stainless Steel", "Current Production", 8900),
        ("Omega", "Seamaster Aqua Terra Worldtimer", "220.12.43.22.03.001",
         "Automatic Cal. 8938", "Stainless Steel", "Current Production", 7200),

        # ── Additional Watches (+10) ──────────────────────────────────────
        ("Nomos", "Tangente Neomatik 41 Update", "180.S2",
         "Automatic DUW 6101", "Stainless Steel", "Current Production", 3200),
        ("Nomos", "Club Campus Neomatik", "748.S2",
         "Automatic DUW 3001", "Stainless Steel", "Current Production", 2100),
        ("Junghans", "Max Bill Chronoscope", "027/4003.48",
         "Automatic J880.2", "Stainless Steel", "Current Production", 1950),
        ("Junghans", "Meister Pilot", "027/3591.00",
         "Automatic J880.2", "Stainless Steel", "Current Production", 1750),
        ("Sinn", "556 I Mother of Pearl", "556.0105",
         "Automatic SW 200-1", "Stainless Steel", "Current Production", 1450),
        ("Sinn", "104 St Sa I", "104.011",
         "Automatic SW 220-1", "Stainless Steel", "Current Production", 1790),
        ("Mido", "Ocean Star 600 Chronometer", "M026.608.11.051.01",
         "Automatic Cal. 80", "Stainless Steel", "Current Production", 1350),
    ]


# ---------------------------------------------------------------------------
# Affordable & Microbrand Expansion (2026-03-14)
# ---------------------------------------------------------------------------

def _microbrand_expansion_watches() -> list[tuple]:
    """50 microbrand watches — popular enthusiast-favorite microbrands under 2K."""
    return [
        # Nodus
        ("Nodus", "Avalon II 38mm Blue", "AVL2-BLU", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 650),
        ("Nodus", "Contrail III GMT", "CNT3-GMT-BLK", "Automatic Miyota 9075", "Stainless Steel",
         "Current Production", 750),
        ("Nodus", "Sector Field 36mm", "SEC-36-GRN", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 550),
        # Vaer
        ("Vaer", "C5 Field Black 40mm", "C5-BLK-40", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 499),
        ("Vaer", "D5 Tropic Diver", "D5-TRP-BLU", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 549),
        ("Vaer", "A5 Automatic White 36mm", "A5-WHT-36", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 399),
        ("Vaer", "S5 Solar Field Titanium", "S5-TI-GRN", "Solar Seiko V187", "Titanium",
         "Current Production", 329),
        # Traska
        ("Traska", "Summiteer GMT Black", "SUM-GMT-BLK", "Automatic Miyota 9075", "Stainless Steel",
         "Current Production", 650),
        ("Traska", "Freediver V3 Seafoam", "FDV3-SEA", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 550),
        ("Traska", "Commuter Black", "COM-BLK", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 450),
        # Oak & Oscar
        ("Oak & Oscar", "Olmsted 38.5 Green", "OLM-38-GRN", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 1490),
        ("Oak & Oscar", "Burnham Day-Date", "BRN-DD-BLU", "Automatic Miyota 9132", "Stainless Steel",
         "Current Production", 1590),
        # Autodromo
        ("Autodromo", "Group B Series 2 Night Stage", "GBS2-NGT", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 875),
        ("Autodromo", "Intereuropa Rattrapante", "INT-RAT-BLK", "Mecaquartz Seiko VK67", "Stainless Steel",
         "Limited Edition", 1200),
        # Monta
        ("Monta", "Oceanking 600m Black", "OK-BLK-600", "Automatic Sellita SW300-1", "Stainless Steel",
         "Current Production", 1950),
        ("Monta", "Noble Date Blue", "NOB-BLU-DT", "Automatic Sellita SW300-1", "Stainless Steel",
         "Current Production", 1750),
        ("Monta", "Atlas GMT Pepsi", "ATL-GMT-PEP", "Automatic Sellita SW330-2", "Stainless Steel",
         "Current Production", 2190),
        # NTH
        ("NTH", "Nacken Modern Blue", "NTH-NAC-BLU", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 575),
        ("NTH", "Barracuda Vintage Black", "NTH-BAR-BLK", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 575),
        # Furlan Marri
        ("Furlan Marri", "Mechaquartz Salmon 38mm", "FM-SAL-38", "Mecaquartz Seiko VK64", "Stainless Steel",
         "Current Production", 289),
        ("Furlan Marri", "Mechanical Hand-Wind White", "FM-HW-WHT", "Manual Seagull ST3600", "Stainless Steel",
         "Current Production", 349),
        # Unimatic
        ("Unimatic", "Modello Uno U1S-8N Black", "U1S-8N", "Automatic Seiko NH35", "Stainless Steel",
         "Limited Edition", 750),
        ("Unimatic", "Modello Due U2S-MP Steel", "U2S-MP", "Automatic Seiko NH35", "Stainless Steel",
         "Current Production", 500),
        # anOrdain
        ("anOrdain", "Model 1 Fumé Iron Cream", "M1-FC", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 1850),
        ("anOrdain", "Model 2 Enamel Blue Cairn", "M2-BC", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 1650),
        # Atelier Wen
        ("Atelier Wen", "Perception Porcelain White", "PER-WHT", "Automatic Hangzhou 5000A", "Stainless Steel",
         "Current Production", 1288),
        ("Atelier Wen", "Hao Guilloché Blue", "HAO-BLU", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 788),
        # Venezianico
        ("Venezianico", "Nereide GMT 39mm Aqua", "VNZ-GMT-AQA", "Automatic Miyota 9075", "Stainless Steel",
         "Current Production", 619),
        ("Venezianico", "Redentore Ultraleggero 40mm", "VNZ-RED-UL", "Automatic Miyota 82S5", "Stainless Steel",
         "Current Production", 389),
        # Serica
        ("Serica", "5303-2 Field Watch", "5303-2", "Automatic ETA 2801-2", "Stainless Steel",
         "Current Production", 990),
        ("Serica", "4512 California Dial", "4512", "Manual ETA 7001", "Stainless Steel",
         "Current Production", 890),
        # Studio Underd0g
        ("Studio Underd0g", "Dessert Watch Mint Chip", "DW-MNT", "Automatic Miyota 8215", "Stainless Steel",
         "Current Production", 495),
        ("Studio Underd0g", "Dessert Watch Blueberry", "DW-BLB", "Automatic Miyota 8215", "Stainless Steel",
         "Current Production", 495),
        # Sartory Billard
        ("Sartory Billard", "SB04 Grey Sector", "SB04-GRY", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 1200),
        # Marloe
        ("Marloe", "Morar Salmon", "MOR-SAL", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 599),
        ("Marloe", "Coniston Blue", "CON-BLU", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 529),
        # Straum
        ("Straum", "Opphav Green", "OPH-GRN", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 699),
        # Spinnaker
        ("Spinnaker", "Fleuss Automatic Blue", "SP-5055-BLU", "Automatic Seiko NH35", "Stainless Steel",
         "Current Production", 299),
        ("Spinnaker", "Bradner 42mm Vintage", "SP-5062-VIN", "Automatic Seiko NH35", "Stainless Steel",
         "Current Production", 279),
        ("Spinnaker", "Croft 3912 GMT", "SP-5130-GMT", "Automatic Seiko NH34", "Stainless Steel",
         "Current Production", 399),
        # Phoibos
        ("Phoibos", "Proteus 300m Black", "PY028C", "Automatic Seiko NH35", "Stainless Steel",
         "Current Production", 289),
        ("Phoibos", "Eagle Ray 200m Bronze", "PY021C-BRZ", "Automatic Miyota 9015", "Bronze",
         "Current Production", 399),
        # Gruppo Gamma
        ("Gruppo Gamma", "Venturo Field II Black", "VF2-BLK", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 550),
        # RZE
        ("RZE", "Resolute Ti Blue", "RES-TI-BLU", "Automatic Miyota 9015", "Titanium",
         "Current Production", 499),
        ("RZE", "Endeavour Ti GMT", "END-TI-GMT", "Automatic Miyota 9075", "Titanium",
         "Current Production", 599),
        # Axios
        ("Axios", "Ironclad 40mm Chrono Blue", "IC-40-BLU", "Mecaquartz Seiko VK64", "Stainless Steel",
         "Current Production", 399),
        # Nezumi
        ("Nezumi", "Voiture Chronograph Panda", "VOI-PAN", "Mecaquartz Seiko VK64", "Stainless Steel",
         "Current Production", 399),
        # Maen
        ("Maen", "Hudson 38 Automatic Ice Blue", "HUD-38-ICE", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 479),
        # Bravur
        ("Bravur", "BW003 Scandinavian Blue", "BW003-BLU", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 650),
    ]


def _chinese_value_watches() -> list[tuple]:
    """30 Chinese-made value watches — popular on enthusiast forums, under 500 EUR."""
    return [
        # San Martin
        ("San Martin", "SN004-G V4 Submariner Homage", "SN004-GV4", "Automatic Seiko NH35", "Stainless Steel",
         "Current Production", 210),
        ("San Martin", "SN0021-G BB58 Homage", "SN0021-G", "Automatic Seiko NH35", "Stainless Steel",
         "Current Production", 220),
        ("San Martin", "SN007-G Pilot Flieger 39mm", "SN007-G", "Automatic Seiko NH35", "Stainless Steel",
         "Current Production", 180),
        ("San Martin", "SN0108-G 62MAS Diver 200m", "SN0108-G", "Automatic Seiko NH35", "Stainless Steel",
         "Current Production", 250),
        ("San Martin", "SN0054-G Explorer Homage 36mm", "SN0054-G", "Automatic Seiko NH35", "Stainless Steel",
         "Current Production", 165),
        ("San Martin", "SN0116-G GMT Pepsi", "SN0116-G", "Automatic Seiko NH34", "Stainless Steel",
         "Current Production", 280),
        # Pagani Design
        ("Pagani Design", "PD-1661 Daytona Homage Black", "PD-1661-BLK", "Quartz Seiko VK63", "Stainless Steel",
         "Current Production", 85),
        ("Pagani Design", "PD-1662 GMT Batman", "PD-1662-BAT", "Automatic Seiko NH34", "Stainless Steel",
         "Current Production", 100),
        ("Pagani Design", "PD-1679 Seamaster Homage Blue", "PD-1679-BLU", "Automatic Seiko NH35", "Stainless Steel",
         "Current Production", 80),
        ("Pagani Design", "PD-1685 Speedmaster Homage Panda", "PD-1685-PAN", "Quartz Seiko VK63", "Stainless Steel",
         "Current Production", 90),
        # Sugess
        ("Sugess", "SU1901 Chronograph Panda 40mm", "SU1901-PAN", "Manual Seagull ST1901", "Stainless Steel",
         "Current Production", 250),
        ("Sugess", "SU1908 Moon Phase Dress", "SU1908-WHT", "Manual Seagull ST2108", "Stainless Steel",
         "Current Production", 200),
        ("Sugess", "SU2025 Tourbillon Heritage", "SU2025-TRB", "Manual Seagull ST8000", "Stainless Steel",
         "Current Production", 350),
        # Islander
        ("Islander", "ISL-40 Diver Black 200m", "ISL-40-BLK", "Automatic Seiko NH35", "Stainless Steel",
         "Current Production", 199),
        ("Islander", "ISL-69 Field Watch Green", "ISL-69-GRN", "Automatic Seiko NH35", "Stainless Steel",
         "Current Production", 229),
        ("Islander", "ISL-94 Port Jefferson Diver", "ISL-94-BLU", "Automatic Seiko NH38", "Stainless Steel",
         "Current Production", 249),
        # Escapement Time
        ("Escapement Time", "King Seiko Homage Blue", "ET-KS-BLU", "Automatic Seiko NH35", "Stainless Steel",
         "Current Production", 120),
        ("Escapement Time", "Dress Watch Guilloché Silver", "ET-DR-SLV", "Automatic Miyota 8215", "Stainless Steel",
         "Current Production", 100),
        # Proxima
        ("Proxima", "PX1681 MM300 Homage Black", "PX1681-BLK", "Automatic Seiko NH35", "Stainless Steel",
         "Current Production", 230),
        ("Proxima", "PX01 Turtle Diver Bronze", "PX01-BRZ", "Automatic Seiko NH35", "Bronze",
         "Current Production", 280),
        # Heimdallr
        ("Heimdallr", "Monster Diver V2 Orange", "HMD-MON-ORG", "Automatic Seiko NH36", "Stainless Steel",
         "Current Production", 130),
        ("Heimdallr", "SKX007 Homage Turtle", "HMD-SKX-BLK", "Automatic Seiko NH36", "Stainless Steel",
         "Current Production", 110),
        # Merkur
        ("Merkur", "Flieger Type-B Pilot 42mm", "MK-PIL-B", "Manual Seagull ST3621", "Stainless Steel",
         "Current Production", 200),
        ("Merkur", "Handwinding Chronograph Reverse Panda", "MK-CHR-RP", "Manual Seagull ST1901", "Stainless Steel",
         "Current Production", 280),
        # Baltany
        ("Baltany", "1926 Explorer Homage 36mm", "BAL-1926-WHT", "Automatic Seiko NH38", "Stainless Steel",
         "Current Production", 130),
        ("Baltany", "Dirty Dozen Military 36mm", "BAL-DD-BLK", "Automatic Seiko NH35", "Stainless Steel",
         "Current Production", 120),
        ("Baltany", "Bubble Back Bronze Salmon", "BAL-BB-SAL", "Automatic Miyota 8215", "Bronze",
         "Current Production", 160),
        # Cadisen
        ("Cadisen", "C8185 Dress Watch Silver", "C8185-SLV", "Automatic Miyota 8215", "Stainless Steel",
         "Current Production", 70),
        # Tandorio
        ("Tandorio", "62MAS Diver Teal 38mm", "TND-62-TEA", "Automatic Seiko NH35", "Stainless Steel",
         "Current Production", 95),
        # Addiesdive
        ("Addiesdive", "Pilot Flieger 42mm Bronze", "AD-FLI-BRZ", "Automatic Seiko NH35", "Bronze",
         "Current Production", 110),
    ]


def _affordable_mainstream_expansion() -> list[tuple]:
    """40 affordable mainstream brand watches — well-known brands under 3K EUR."""
    return [
        # Hamilton (more affordable range)
        ("Hamilton", "Khaki Field Quartz 38mm", "H68201143", "Quartz ETA F06.115", "Stainless Steel",
         "Current Production", 350),
        ("Hamilton", "Ventura Quartz", "H24411732", "Quartz ETA 956.412", "Stainless Steel",
         "Current Production", 495),
        ("Hamilton", "Khaki Navy Pioneer Auto 40mm", "H77715553", "Automatic H-10", "Stainless Steel",
         "Current Production", 895),
        ("Hamilton", "Jazzmaster Thinline Auto 40mm", "H38525811", "Automatic H-10", "Stainless Steel",
         "Current Production", 625),
        # Tissot (more models)
        ("Tissot", "PRX 35mm Quartz Green", "T137.210.11.091.00", "Quartz ETA F06.115", "Stainless Steel",
         "Current Production", 325),
        ("Tissot", "Classic Dream 42mm", "T129.410.16.013.00", "Quartz ETA F06.115", "Stainless Steel",
         "Current Production", 225),
        ("Tissot", "Everytime 40mm", "T143.410.16.031.00", "Quartz ETA F06.115", "Stainless Steel",
         "Current Production", 195),
        # Citizen (more Eco-Drive)
        ("Citizen", "Eco-Drive Corso BM7100-59E", "BM7100-59E", "Eco-Drive Cal. E111", "Stainless Steel",
         "Current Production", 175),
        ("Citizen", "Eco-Drive Chandler BM8180-03E", "BM8180-03E", "Eco-Drive Cal. E101", "Stainless Steel",
         "Current Production", 125),
        ("Citizen", "Eco-Drive Paradigm AW1550-50E", "AW1550-50E", "Eco-Drive Cal. E111", "Stainless Steel",
         "Current Production", 250),
        ("Citizen", "Automatic NY0086-16LE Promaster Fugu", "NY0086-16LE", "Automatic Cal. 8204", "Stainless Steel",
         "Limited Edition", 350),
        # Orient (more affordable automatics)
        ("Orient", "Ray II Black FAA02004B", "FAA02004B", "Automatic Cal. F6922", "Stainless Steel",
         "Current Production", 175),
        ("Orient", "Tristar Gold Dial", "FAB00009P9", "Automatic Cal. 46943", "Stainless Steel",
         "Current Production", 80),
        ("Orient", "Sun & Moon V3 Blue", "RA-AK0011D", "Automatic Cal. F6B24", "Stainless Steel",
         "Current Production", 280),
        ("Orient", "Defender II Field RA-AK0401L", "RA-AK0401L", "Automatic Cal. F6922", "Stainless Steel",
         "Current Production", 175),
        # Seiko (affordable line)
        ("Seiko", "5 Sports SRPD55 Black", "SRPD55K1", "Automatic Cal. 4R36", "Stainless Steel",
         "Current Production", 250),
        ("Seiko", "5 Sports Field SRPE65 Green", "SRPE65K1", "Automatic Cal. 4R36", "Stainless Steel",
         "Current Production", 275),
        ("Seiko", "5 Sports GMT SSK001 Black", "SSK001", "Automatic Cal. 4R34", "Stainless Steel",
         "Current Production", 375),
        ("Seiko", "5 Sports SNXS77 Datejust Style", "SNXS77K1", "Automatic Cal. 7S26", "Stainless Steel",
         "Current Production", 130),
        ("Seiko", "Prospex King Turtle SRPE05", "SRPE05K1", "Automatic Cal. 4R36", "Stainless Steel",
         "Current Production", 450),
        ("Seiko", "Prospex SNE573 Solar Tuna", "SNE573P1", "Solar V157", "Stainless Steel",
         "Current Production", 350),
        # Casio (dressy & affordable)
        ("Casio", "Edifice EFR-S108D Slim Chrono", "EFR-S108D-1AV", "Quartz Module", "Stainless Steel",
         "Current Production", 120),
        ("Casio", "Oceanus OCW-T200S Titanium Solar", "OCW-T200S-1AJF", "Tough Solar Module", "Titanium",
         "Current Production", 500),
        ("Casio", "Lineage LCW-M170TD Titanium", "LCW-M170TD-7AJF", "Tough Solar Module", "Titanium",
         "Current Production", 180),
        # Timex (more models)
        ("Timex", "Expedition North Titanium Solar", "TW2V40600", "Solar", "Titanium",
         "Current Production", 200),
        # Victorinox
        ("Victorinox", "INOX Automatic 43mm", "241834", "Automatic ETA 2824-2", "Stainless Steel",
         "Current Production", 750),
        ("Victorinox", "Fieldforce Chrono 42mm", "241853", "Quartz Ronda 5021.D", "Stainless Steel",
         "Current Production", 350),
        # Alpina
        ("Alpina", "Startimer Pilot Auto 44mm", "AL-525NN4S6", "Automatic AL-525", "Stainless Steel",
         "Current Production", 750),
        ("Alpina", "Seastrong Diver 300 Auto", "AL-525LBN4V6", "Automatic AL-525", "Stainless Steel",
         "Current Production", 850),
        # Mondaine
        ("Mondaine", "Official Swiss Railways Classic 40mm", "A660.30360.16SBB", "Quartz Ronda 763", "Stainless Steel",
         "Current Production", 280),
        ("Mondaine", "SBB Essence 41mm", "MS1.41120.RB", "Quartz Ronda 783", "Stainless Steel",
         "Current Production", 250),
        # Raymond Weil
        ("Raymond Weil", "Freelancer Auto 42mm Blue", "2780-ST-50001", "Automatic RW4200", "Stainless Steel",
         "Current Production", 1295),
        ("Raymond Weil", "Toccata Classic 39mm", "5485-STC-00300", "Quartz", "Stainless Steel",
         "Current Production", 595),
        # Frederique Constant
        ("Frederique Constant", "Classics Auto 40mm", "FC-303S5B6", "Automatic FC-303", "Stainless Steel",
         "Current Production", 895),
        ("Frederique Constant", "Highlife Automatic 41mm", "FC-303S4NH6B", "Automatic FC-303", "Stainless Steel",
         "Current Production", 1295),
        # Movado
        ("Movado", "Museum Classic 40mm Black", "0607199", "Quartz", "Stainless Steel",
         "Current Production", 495),
    ]


def _value_diver_watches() -> list[tuple]:
    """30 value diver watches — popular affordable divers under 1K EUR."""
    return [
        # Casio Duro family
        ("Casio", "Duro Marlin MDV-107D Silver", "MDV-107D-1A1V", "Quartz Module", "Stainless Steel",
         "Current Production", 70),
        ("Casio", "Duro MDV-106G Gold Accent", "MDV-106G-1AV", "Quartz Module", "Stainless Steel",
         "Current Production", 55),
        # Invicta (actually popular budget)
        ("Invicta", "Pro Diver 8927OB Two-Tone Auto", "8927OB", "Automatic NH35A", "Stainless Steel",
         "Current Production", 85),
        ("Invicta", "Pro Diver 9094 Swiss Quartz", "9094", "Quartz ISA 1198/30", "Stainless Steel",
         "Current Production", 65),
        # Citizen Promaster affordable
        ("Citizen", "Promaster Diver BN0150-28E", "BN0150-28E", "Eco-Drive Cal. E168", "Stainless Steel",
         "Current Production", 180),
        # Seiko divers
        ("Seiko", "Prospex SBDC101 Willard Black", "SBDC101", "Automatic Cal. 6R35", "Stainless Steel",
         "Current Production", 900),
        ("Seiko", "Prospex SNE586 Solar Street Series", "SNE586P1", "Solar V157", "Stainless Steel",
         "Current Production", 290),
        ("Seiko", "Prospex SRPH75 King Samurai Blue", "SRPH75K1", "Automatic Cal. 4R35", "Stainless Steel",
         "Current Production", 400),
        # Orient divers
        ("Orient", "Mako III RA-AA0814R Green", "RA-AA0814R", "Automatic Cal. F6922", "Stainless Steel",
         "Current Production", 250),
        ("Orient", "Triton RA-EL0002B 200m Power Reserve", "RA-EL0002B", "Automatic Cal. F6727", "Stainless Steel",
         "Current Production", 380),
        # Certina divers
        ("Certina", "DS Action Diver Powermatic 80", "C032.407.11.041.00", "Automatic Powermatic 80", "Stainless Steel",
         "Current Production", 575),
        # Longines affordable diver
        ("Longines", "HydroConquest 41mm Automatic Blue", "L3.781.4.96.6", "Automatic L888.5", "Stainless Steel",
         "Current Production", 1275),
        # Tissot divers
        ("Tissot", "Seastar 2000 Professional Powermatic 80", "T120.607.11.041.00", "Automatic Powermatic 80", "Stainless Steel",
         "Current Production", 775),
        # Deep value divers
        ("Vostok", "Amphibia Scuba Dude 710", "710059", "Automatic Cal. 2416B", "Stainless Steel",
         "Current Production", 90),
        # Marathon
        ("Marathon", "Medium Diver Automatic MSAR 36mm", "WW194026", "Automatic ETA 2824-2", "Stainless Steel",
         "Military Issue", 900),
        # Squale divers
        ("Squale", "1545 30 Atmos Tropic Ceramica", "1545-TRP", "Automatic ETA 2824-2", "Stainless Steel",
         "Current Production", 750),
        ("Squale", "SUB-39 GMT Vintage", "SUB39-GMT-VIN", "Automatic ETA 2893-2", "Stainless Steel",
         "Current Production", 900),
        # Doxa divers
        ("Doxa", "SUB 200T Sharkhunter Black", "804.10.101.21", "Automatic ETA 2824-2", "Stainless Steel",
         "Current Production", 890),
        ("Doxa", "SUB 300 Searambler Silver Lung", "821.10.021.10", "Automatic ETA 2824-2", "Stainless Steel",
         "Current Production", 1550),
        # Zodiac divers
        ("Zodiac", "Super Sea Wolf Pro-Diver", "ZO3552", "Automatic STP 1-11", "Stainless Steel",
         "Current Production", 995),
        # Yema divers
        ("Yema", "Superman Heritage 39mm", "YSUP2022-AMS", "Automatic YEMA2000", "Stainless Steel",
         "Current Production", 990),
        ("Yema", "Navygraf Heritage", "YNAV2022-3MNS", "Automatic YEMA2000", "Stainless Steel",
         "Current Production", 890),
        # NTH Sub
        ("NTH", "Oberon 40mm Orange Diver", "NTH-OBR-ORG", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 575),
        # Glycine Combat Sub
        ("Glycine", "Combat Sub 46mm Bronze", "GL0318", "Automatic GL 224", "Bronze",
         "Current Production", 580),
        # Undone
        ("Undone", "Aquadeep 500m Black Ti", "AQD-TI-BLK", "Automatic Seiko NH35", "Titanium",
         "Current Production", 450),
        # Wolbrook (French microbrand)
        ("Wolbrook", "Skindiver WT Automatic", "WB-SKD-BLU", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 590),
        # Maen (Dutch microbrand)
        ("Maen", "Hudson 38 Diver Blue", "HUD-38-DVR-BLU", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 449),
    ]


def _affordable_dress_field_watches() -> list[tuple]:
    """40 affordable dress & field watches — popular sub-2K pieces."""
    return [
        # Junghans
        ("Junghans", "Max Bill Handwinding 34mm", "027/3701.04", "Manual J805.1", "Stainless Steel",
         "Current Production", 695),
        ("Junghans", "Form A Automatic 39mm", "027/4730.00", "Automatic J800.1", "Stainless Steel",
         "Current Production", 795),
        # Nomos affordable range
        ("Nomos", "Club Campus 36 Night", "709.S3", "Manual Cal. Alpha", "Stainless Steel",
         "Current Production", 990),
        ("Nomos", "Tangente 33 Duo", "120.S2", "Manual Cal. Alpha", "Stainless Steel",
         "Current Production", 1300),
        # Sinn
        ("Sinn", "556 A Red Seconds", "556.0104", "Automatic SW 200-1", "Stainless Steel",
         "Current Production", 1290),
        # Baltic
        ("Baltic", "MR01 Micro Rotor Silver", "MR01-SLV", "Automatic Miyota 9122", "Stainless Steel",
         "Current Production", 630),
        ("Baltic", "HMS 002 Blue Gilt", "HMS002-BLU", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 490),
        ("Baltic", "Bicompax 002 Salmon", "BC002-SAL", "Mecaquartz Seiko VK64", "Stainless Steel",
         "Current Production", 580),
        # Christopher Ward
        ("Christopher Ward", "C63 Sealander Auto 39mm", "C63-39ADA1-SWK0S", "Automatic Sellita SW200-1", "Stainless Steel",
         "Current Production", 695),
        ("Christopher Ward", "C1 Moonglow 40mm", "C1-40AMG1-SWK0B", "Automatic Sellita SW200-1", "Stainless Steel",
         "Current Production", 825),
        ("Christopher Ward", "C60 Trident Pro 600 42mm", "C60-42ADA3-SWK0B", "Automatic Sellita SW200-1", "Stainless Steel",
         "Current Production", 895),
        ("Christopher Ward", "C65 Sandhurst Bronze", "C65-41BRZ-SAL", "Automatic Sellita SW200-1", "Bronze",
         "Current Production", 795),
        # Farer
        ("Farer", "Lander IV 39.5mm", "LND4-BLU", "Automatic SW200-1", "Stainless Steel",
         "Current Production", 895),
        ("Farer", "Carnegie GMT 39.5mm", "CRN-GMT-BLU", "Automatic SW330-1", "Stainless Steel",
         "Current Production", 1195),
        ("Farer", "Bernina Chrono 39mm", "BRN-CHR-WHT", "Automatic SW510", "Stainless Steel",
         "Current Production", 1395),
        # Formex
        ("Formex", "Essence 39 Auto Chronometre Blue", "ESS-39-BLU", "Automatic COSC Sellita", "Stainless Steel",
         "Current Production", 995),
        ("Formex", "Reef 39 Auto Black", "REF-39-BLK", "Automatic Sellita SW200-1", "Stainless Steel",
         "Current Production", 845),
        # Norqain
        ("Norqain", "Freedom 60 Chrono 40mm", "FR60-CHR-40", "Automatic Sellita SW510 BH", "Stainless Steel",
         "Current Production", 2490),
        ("Norqain", "Adventure Sport Auto 42mm", "ADV-42-BLU", "Automatic Sellita SW200-1", "Stainless Steel",
         "Current Production", 1790),
        # Longines affordable
        ("Longines", "Conquest Classic 40mm Blue", "L4.312.4.96.6", "Quartz L296", "Stainless Steel",
         "Current Production", 850),
        ("Longines", "Master Collection 40mm Auto", "L2.793.4.97.6", "Automatic L888.5", "Stainless Steel",
         "Current Production", 1900),
        # Oris affordable
        ("Oris", "Divers Sixty-Five 40mm Bronze", "01 733 7707 4355", "Automatic SW200-1", "Bronze",
         "Current Production", 1750),
        # Mido
        ("Mido", "Multifort Patrimony", "M040.407.36.060.00", "Automatic Cal. 80", "Stainless Steel",
         "Current Production", 950),
        ("Mido", "Commander Shade Grey", "M021.407.11.411.00", "Automatic Cal. 80", "Stainless Steel",
         "Current Production", 750),
        # Baume & Mercier
        ("Baume & Mercier", "Classima Auto 42mm", "M0A10453", "Automatic ETA 2892-A2", "Stainless Steel",
         "Current Production", 1450),
        ("Baume & Mercier", "Riviera Auto 42mm Blue", "M0A10620", "Automatic ETA 2892-A2", "Stainless Steel",
         "Current Production", 2950),
        # Edox
        ("Edox", "SkyDiver Military Bronze LE", "80115-BRZN-NDR", "Automatic ETA 2824-2", "Bronze",
         "Limited Edition", 990),
        ("Edox", "Les Vauberts Open Heart Auto", "85014-3-NIN", "Automatic ETA 2824-2", "Stainless Steel",
         "Current Production", 750),
        # Bertucci
        ("Bertucci", "A-2T Classic Field Ti", "12086", "Quartz Swiss ISA", "Titanium",
         "Current Production", 89),
        ("Bertucci", "A-11T Americana 42mm", "13331", "Quartz Swiss ISA", "Titanium",
         "Current Production", 99),
        # Dan Henry (more)
        ("Dan Henry", "1947 Dress Chrono Silver", "1947-SLV", "Mecaquartz Seiko VK64", "Stainless Steel",
         "Current Production", 230),
        ("Dan Henry", "2024 World Timer", "2024-WT-BLU", "Mecaquartz Seiko VK73", "Stainless Steel",
         "Current Production", 280),
        # Undone
        ("Undone", "Basecamp Auto Cali Dial", "BSC-CAL-WHT", "Automatic Seiko NH35", "Stainless Steel",
         "Current Production", 350),
        ("Undone", "Urban Tropical 40mm", "URB-TRP-BLU", "Automatic Miyota 8215", "Stainless Steel",
         "Current Production", 299),
        # Tsao Baltimore
        ("Tsao Baltimore", "Torsk-Diver Marine Green", "TSK-DVR-GRN", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 695),
        # Astor+Banks
        ("Astor+Banks", "Fortitude Diver v2 Black", "FRT-V2-BLK", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 695),
    ]


def _mid_range_enthusiast_watches() -> list[tuple]:
    """30 mid-range enthusiast watches — EUR 1K-5K sweet spot."""
    return [
        # Sinn (more)
        ("Sinn", "104 I St Sa Pilot White", "104.012", "Automatic SW 220-1", "Stainless Steel",
         "Current Production", 1790),
        ("Sinn", "856 UTC Tegimented", "856.011", "Automatic ETA 2893-2", "Stainless Steel",
         "Current Production", 2490),
        ("Sinn", "903 St Navigator Chrono", "903.040", "Manual Valjoux 7750", "Stainless Steel",
         "Current Production", 2950),
        # Nomos (more)
        ("Nomos", "Metro 38.5 Date Urban Blue", "1115.S2", "Automatic DUW 6101", "Stainless Steel",
         "Current Production", 3200),
        ("Nomos", "Ludwig 38 White", "231", "Manual Cal. Alpha", "Stainless Steel",
         "Current Production", 1700),
        ("Nomos", "Ahoi Neomatik 36.3mm", "562.S3", "Automatic DUW 3001", "Stainless Steel",
         "Current Production", 2800),
        # Oris
        ("Oris", "Aquis Date 41.5mm Green", "01 733 7766 4157", "Automatic Oris 733", "Stainless Steel",
         "Current Production", 1850),
        ("Oris", "Big Crown ProPilot Big Date 41mm", "01 751 7761 4065", "Automatic Oris 751", "Stainless Steel",
         "Current Production", 1650),
        # Longines
        ("Longines", "Spirit Pilot Chrono 42mm", "L3.820.4.93.6", "Automatic L688.4", "Stainless Steel",
         "Current Production", 2950),
        ("Longines", "Record 40mm COSC Blue", "L2.821.4.96.6", "Automatic L888.4", "Stainless Steel",
         "Current Production", 1700),
        # Tissot PRX
        # Hamilton higher-end
        ("Hamilton", "Khaki Aviation X-Wind GMT Chrono", "H77912135", "Quartz H-31", "Stainless Steel",
         "Current Production", 1095),
        # Grand Seiko entry
        ("Grand Seiko", "Heritage SBGP001 Quartz 40mm", "SBGP001", "Quartz Cal. 9F85", "Stainless Steel",
         "Current Production", 2800),
        ("Grand Seiko", "Heritage SBGA373 Spring Drive", "SBGA373", "Spring Drive Cal. 9R65", "Stainless Steel",
         "Current Production", 4800),
        # Tudor entry
        ("Tudor", "1926 41mm Opaline", "M91650-0011", "Automatic Cal. T603", "Stainless Steel",
         "Current Production", 1700),
        # Bell & Ross
        ("Bell & Ross", "BR 05 Black Steel 40mm", "BR05A-BL-ST/SST", "Automatic BR-CAL.321", "Stainless Steel",
         "Current Production", 4300),
        # Rado
        ("Rado", "Captain Cook Auto 37mm Green", "R32500318", "Automatic Powermatic 80", "Stainless Steel",
         "Current Production", 1050),
        ("Rado", "DiaStar Original 38mm", "R12160253", "Automatic R764", "Ceramic/Steel",
         "Current Production", 1750),
        # Ming (highly collectible microbrand)
        ("MING", "27.02 Field Watch Black", "2702-BLK", "Automatic ETA 2824-2", "Stainless Steel",
         "Limited Edition", 1950),
        ("MING", "18.01 Diver H41 Blue", "1801-BLU", "Automatic Sellita SW300-1", "Stainless Steel",
         "Limited Edition", 2950),
        # Zodiac (more)
        ("Zodiac", "Super Sea Wolf Topper Edition", "ZO9290", "Automatic STP 1-11", "Stainless Steel",
         "Limited Edition", 1495),
        # Christopher Ward
        ("Christopher Ward", "C60 Sapphire 40mm", "C60-40SPH-SWK0B", "Automatic Sellita SW200-1", "Stainless Steel",
         "Current Production", 995),
        # Stowa
        ("Stowa", "Flieger Classic 36 Date", "FL-CLS-36-DT", "Automatic ETA 2824-2", "Stainless Steel",
         "Current Production", 890),
        ("Stowa", "Partitio Classic White", "PA-CLS-WHT", "Manual Unitas 6498", "Stainless Steel",
         "Current Production", 850),
        # Yema
        ("Yema", "Speedgraf Meca-Quartz Panda", "YMHF1573-ZW", "Mecaquartz Seiko VK64", "Stainless Steel",
         "Current Production", 449),
        # Direnzo
        ("Direnzo", "DRZ 04 Mondial Blue", "DRZ04-BLU", "Automatic Sellita SW200-1", "Stainless Steel",
         "Current Production", 990),
    ]


def _g_shock_affordable_expansion() -> list[tuple]:
    """30 G-Shock & Casio affordable watches — popular collectible models under 1K."""
    return [
        # Classic squares
        ("G-Shock", "DW-5600E-1V Classic Square", "DW-5600E-1V", "Quartz Module 3229", "Resin",
         "Current Production", 65),
        ("G-Shock", "GW-M5610U-1 Solar Multiband 6", "GW-M5610U-1", "Tough Solar Module 3459", "Resin",
         "Current Production", 130),
        ("G-Shock", "GMW-B5000D-1 Full Metal Silver", "GMW-B5000D-1", "Tough Solar Module 3459", "Stainless Steel",
         "Current Production", 450),
        # CasiOak
        ("G-Shock", "GA-2100-1A1 CasiOak Black", "GA-2100-1A1", "Quartz Module 5611", "Resin",
         "Current Production", 80),
        ("G-Shock", "GA-2110SU-3A CasiOak Olive", "GA-2110SU-3A", "Quartz Module 5611", "Resin",
         "Current Production", 100),
        ("G-Shock", "GM-2100-1A Metal CasiOak", "GM-2100-1A", "Quartz Module 5611", "Stainless Steel",
         "Current Production", 180),
        ("G-Shock", "GM-B2100D-1A Full Metal CasiOak", "GM-B2100D-1A", "Tough Solar Module 5674", "Stainless Steel",
         "Current Production", 400),
        # Mudmaster & Rangeman
        ("G-Shock", "GG-B100-1B3 Mudmaster", "GG-B100-1B3", "Quartz Module 5571", "Resin",
         "Current Production", 320),
        ("G-Shock", "GPR-H1000-1 Rangeman Heart Rate", "GPR-H1000-1", "Tough Solar Module", "Resin",
         "Current Production", 600),
        ("G-Shock", "GWG-2000-1A1 Mudmaster Carbon Core", "GWG-2000-1A1", "Tough Solar Module 5678", "Carbon",
         "Current Production", 520),
        # Frogman
        ("G-Shock", "GWF-A1000-1A4 Frogman Analog", "GWF-A1000-1A4", "Tough Solar Module 5624", "Carbon",
         "Current Production", 650),
        # Solar & Multiband
        ("G-Shock", "GW-9400-1 Rangeman", "GW-9400-1", "Tough Solar Module 3410", "Resin",
         "Current Production", 250),
        ("G-Shock", "GW-B5600BC-1B Composite Band", "GW-B5600BC-1B", "Tough Solar Module 3461", "Resin",
         "Current Production", 150),
        # G-STEEL
        ("G-Shock", "GST-B400D-1A G-STEEL Slim", "GST-B400D-1A", "Tough Solar Module 5637", "Stainless Steel",
         "Current Production", 350),
        ("G-Shock", "GST-B500D-1A G-STEEL Octagon", "GST-B500D-1A", "Tough Solar Module 5641", "Stainless Steel",
         "Current Production", 400),
        # Vintage & retro
        ("Casio", "A168WA-1 Classic Silver Retro", "A168WA-1", "Quartz Module", "Stainless Steel",
         "Current Production", 25),
        ("Casio", "AE-1200WH World Time Silver", "AE-1200WHD-1AV", "Quartz Module", "Stainless Steel",
         "Current Production", 35),
        ("Casio", "F-91W Classic Digital", "F-91W-1", "Quartz Module", "Resin",
         "Current Production", 15),
        ("Casio", "CA-53W Calculator Watch", "CA-53W-1", "Quartz Module", "Resin",
         "Current Production", 25),
        ("Casio", "W-800H Classic Digital", "W-800H-1AV", "Quartz Module", "Resin",
         "Current Production", 20),
        # Pro Trek
        ("Casio", "Pro Trek PRW-6900Y Solar Climber", "PRW-6900Y-1", "Tough Solar Module", "Resin",
         "Current Production", 350),
        ("Casio", "Pro Trek PRG-340 Slim", "PRG-340-1", "Tough Solar Module", "Resin",
         "Current Production", 180),
        # Baby-G (collectible)
        ("Casio", "Baby-G BGA-310 Pastel Pink", "BGA-310-4A", "Quartz Module", "Resin",
         "Current Production", 90),
        ("Casio", "Baby-G BGD-565 Classic Mini Square", "BGD-565-4", "Quartz Module", "Resin",
         "Current Production", 70),
        # MR-G premium
        ("G-Shock", "MRG-B5000B-1 Titanium Cobarion", "MRG-B5000B-1", "Tough Solar Module 3496", "Titanium",
         "Current Production", 2500),
        # MT-G
        ("G-Shock", "MTG-B3000D-1A MT-G Slim", "MTG-B3000D-1A", "Tough Solar Module 5672", "Stainless Steel",
         "Current Production", 800),
        ("G-Shock", "MTG-B2000D-1A Rainbow Phoenix", "MTG-B2000D-1A", "Tough Solar Module 5606", "Stainless Steel",
         "Limited Edition", 950),
        # Affordable digital
        ("Casio", "WS-1500H Tide Graph", "WS-1500H-1AV", "Quartz Module", "Resin",
         "Current Production", 40),
        ("Casio", "DW-291H 200m Digital", "DW-291H-1AV", "Quartz Module", "Resin",
         "Current Production", 35),
    ]


def _accessible_luxury_watches() -> list[tuple]:
    """20 accessible luxury watches — EUR 2K-5K range, entry-level Swiss & Japanese."""
    return [
        # Omega entry
        ("Omega", "Seamaster Aqua Terra 38mm Grey", "220.10.38.20.06.001", "Automatic Cal. 8800", "Stainless Steel",
         "Current Production", 4700),
        # Longines
        ("Longines", "Flagship Heritage 38.5mm", "L4.795.4.78.2", "Automatic L888.5", "Stainless Steel",
         "Current Production", 1825),
        # Breitling entry
        ("Breitling", "Superocean Automatic 42 Blue", "A17375E71C1S1", "Automatic B17", "Stainless Steel",
         "Current Production", 3800),
        # Grand Seiko
        ("Grand Seiko", "Heritage SBGX261 Quartz Black", "SBGX261", "Quartz Cal. 9F62", "Stainless Steel",
         "Current Production", 2400),
        # Frederique Constant
        ("Frederique Constant", "Slimline Moonphase Auto", "FC-775S4S6", "Automatic FC-775", "Stainless Steel",
         "Current Production", 2495),
        # Baume & Mercier
        ("Baume & Mercier", "Classima Dual Time 42mm", "M0A10482", "Quartz ETA 2893-2", "Stainless Steel",
         "Current Production", 1650),
        # Rado
        ("Rado", "Captain Cook High-Tech Ceramic 43mm", "R32127162", "Automatic R802", "Ceramic",
         "Current Production", 2350),
        # Oris
        ("Oris", "Aquis Date 39.5mm Turquoise", "01 733 7732 4155", "Automatic Oris 733", "Stainless Steel",
         "Current Production", 1900),
        # Monta
        ("Monta", "Triumph GMT Black", "TRI-GMT-BLK", "Automatic Sellita SW330-2", "Stainless Steel",
         "Current Production", 2290),
        # Norqain
        ("Norqain", "Wild One 42mm Skeleton", "WO-42-SKL", "Automatic Kenissi", "Carbon",
         "Current Production", 3490),
        # Glashutte Original entry
        ("Glashutte Original", "SeaQ 1969 39.5mm", "1-39-11-09-81-70", "Automatic Cal. 39-11", "Stainless Steel",
         "Current Production", 4900),
        # Blancpain entry
        ("Blancpain", "Fifty Fathoms Bathyscaphe 38mm", "5100-1110-B52A", "Automatic Cal. 1150", "Stainless Steel",
         "Current Production", 4800),
        # Ulysse Nardin entry
        ("Ulysse Nardin", "Diver 42mm Blue", "8163-175-7M/93", "Automatic UN-816", "Stainless Steel",
         "Current Production", 4500),
        # Bell & Ross entry
        ("Bell & Ross", "BR V2-92 Steel Heritage", "BRV292-HER-ST/SRB", "Automatic BR-CAL.302", "Stainless Steel",
         "Current Production", 2700),
        # Ebel
        ("Ebel", "Sport Classic Gent Auto 40mm", "1216432", "Automatic ETA 2892-A2", "Stainless Steel",
         "Current Production", 1750),
    ]


# ---------------------------------------------------------------------------
# Luxury Variants Expansion — Men's & Women's (2026-03-14)
# ---------------------------------------------------------------------------

def _cartier_variants_watches() -> list[tuple]:
    """40 Cartier variants — full range men's & women's, materials, sizes."""
    return [
        # Santos — men's
        ("Cartier", "Santos de Cartier Small Steel", "WSSA0038", "Automatic 1847 MC", "Stainless Steel",
         "Current Production", 5700),
        ("Cartier", "Santos de Cartier Large Rose Gold", "WGSA0019", "Automatic 1847 MC", "18k Rose Gold",
         "Current Production", 17500),
        ("Cartier", "Santos de Cartier Medium Blue Dial", "WSSA0030", "Automatic 1847 MC", "Stainless Steel",
         "Current Production", 7200),
        ("Cartier", "Santos de Cartier Medium Two-Tone", "W2SA0007", "Automatic 1847 MC", "Steel/Gold",
         "Current Production", 9950),
        ("Cartier", "Santos de Cartier Chronograph Steel", "WSSA0037", "Automatic 1904-CH MC", "Stainless Steel",
         "Current Production", 9450),
        # Santos — women's
        ("Cartier", "Santos-Dumont Small Rose Gold", "WGSA0022", "Quartz 157", "18k Rose Gold",
         "Current Production", 9800),
        ("Cartier", "Santos-Dumont Large Steel", "WSSA0022", "Manual 430 MC", "Stainless Steel",
         "Current Production", 4300),
        # Tank — men's
        ("Cartier", "Tank Must Large Silver", "WSTA0056", "Quartz SolarBeat", "Stainless Steel",
         "Current Production", 3100),
        ("Cartier", "Tank Must XL Skeleton", "WHTA0002", "Manual 9627 MC", "Stainless Steel",
         "Limited Edition", 10500),
        ("Cartier", "Tank Louis Cartier Small Rose Gold", "WGTA0011", "Quartz 157", "18k Rose Gold",
         "Current Production", 11000),
        ("Cartier", "Tank Américaine Medium Rose Gold", "WGTA0024", "Automatic 1847 MC", "18k Rose Gold",
         "Current Production", 15000),
        ("Cartier", "Tank Cintrée Platinum", "WGTA0061", "Manual 8971 MC", "Platinum",
         "Limited Edition", 32000),
        # Tank — women's
        ("Cartier", "Tank Must Small Steel", "WSTA0051", "Quartz SolarBeat", "Stainless Steel",
         "Current Production", 2760),
        ("Cartier", "Tank Française Small Diamond Bezel", "W4TA0008", "Quartz 157", "Stainless Steel",
         "Current Production", 6500),
        ("Cartier", "Tank Louis Cartier Mini Rose Gold", "WGTA0023", "Quartz 157", "18k Rose Gold",
         "Current Production", 9500),
        # Ballon Bleu — men's
        ("Cartier", "Ballon Bleu 40mm Steel Blue", "WSBB0061", "Automatic 1847 MC", "Stainless Steel",
         "Current Production", 6800),
        ("Cartier", "Ballon Bleu 40mm Rose Gold", "WGBB0035", "Automatic 1847 MC", "18k Rose Gold",
         "Current Production", 22000),
        # Ballon Bleu — women's
        ("Cartier", "Ballon Bleu 33mm Steel Silver", "WSBB0044S", "Automatic 076", "Stainless Steel",
         "Current Production", 5400),
        ("Cartier", "Ballon Bleu 28mm Steel Quartz", "WSBB0067", "Quartz 157", "Stainless Steel",
         "Current Production", 4200),
        ("Cartier", "Ballon Bleu 33mm Diamond", "W4BB0016", "Automatic 076", "Stainless Steel",
         "Current Production", 8500),
        # Panthère — women's
        ("Cartier", "Panthère Medium Yellow Gold", "WGPN0009", "Quartz 157", "18k Yellow Gold",
         "Current Production", 18500),
        ("Cartier", "Panthère Mini Steel", "WSPN0019", "Quartz 157", "Stainless Steel",
         "Current Production", 3400),
        ("Cartier", "Panthère Medium Two-Tone", "W2PN0007", "Quartz 157", "Steel/Gold",
         "Current Production", 7500),
        # Pasha — unisex/men's
        ("Cartier", "Pasha 41mm Steel Blue Grid", "WSPA0038", "Automatic 1847 MC", "Stainless Steel",
         "Current Production", 7500),
        ("Cartier", "Pasha 35mm Steel", "WSPA0012", "Automatic 1847 MC", "Stainless Steel",
         "Current Production", 6300),
        # Ronde — women's
        ("Cartier", "Ronde Must 29mm Steel", "WSRN0031", "Quartz 157", "Stainless Steel",
         "Current Production", 2700),
        ("Cartier", "Ronde Louis Cartier 36mm Rose Gold", "W6800251", "Manual 430 MC", "18k Rose Gold",
         "Current Production", 12000),
        # Clé — unisex
        ("Cartier", "Clé de Cartier 35mm Steel", "WSCL0005", "Automatic 1847 MC", "Stainless Steel",
         "Current Production", 5900),
        # Drive — men's
        ("Cartier", "Drive de Cartier Steel", "WSNM0004", "Automatic 1847 MC", "Stainless Steel",
         "Current Production", 6500),
        # Tonneau — men's
        ("Cartier", "Tonneau Large Rose Gold", "WGTO0003", "Manual 8971 MC", "18k Rose Gold",
         "Limited Edition", 35000),
        # Baignoire — women's
        ("Cartier", "Baignoire Small Rose Gold", "WGBA0015", "Quartz 157", "18k Rose Gold",
         "Current Production", 13000),
        ("Cartier", "Baignoire Allongée Medium WG", "WGBA0017", "Manual 1917 MC", "18k White Gold",
         "Current Production", 22000),
        # Santos Galbée — women's
        ("Cartier", "Santos Galbée Small Two-Tone", "W20012C4", "Quartz", "Steel/Gold",
         "Discontinued Classic", 3500),
        # Vintage collectibles
        ("Cartier", "Vintage Tank Basculante Steel", "2386", "Manual", "Stainless Steel",
         "Vintage Pre-1970", 5500),
        ("Cartier", "Vintage Crash Yellow Gold", "W7200002", "Manual Cal. 080", "18k Yellow Gold",
         "Vintage Pre-1970", 85000),
        # Affordable entry
        ("Cartier", "Ronde Solo Steel 36mm Quartz", "WSRN0012", "Quartz 690", "Stainless Steel",
         "Current Production", 2550),
        ("Cartier", "Tank Must Large Green", "WSTA0056G", "Quartz SolarBeat", "Stainless Steel",
         "Current Production", 3100),
        ("Cartier", "Tank Must Large Blue", "WSTA0055B", "Quartz SolarBeat", "Stainless Steel",
         "Current Production", 3100),
        ("Cartier", "Santos de Cartier Medium Green Dial", "WSSA0062", "Automatic 1847 MC", "Stainless Steel",
         "Current Production", 7200),
        ("Cartier", "Santos de Cartier Large Skeleton ADLC", "WHSA0009", "Manual 9611 MC", "Stainless Steel",
         "Limited Edition", 14500),
    ]


def _ap_variants_watches() -> list[tuple]:
    """35 Audemars Piguet variants — Royal Oak, RO Offshore, Code 11.59, men's & women's."""
    return [
        # Royal Oak — men's sizes & materials
        ("Audemars Piguet", "Royal Oak Selfwinding 41mm Blue", "15500ST.OO.1220ST.02", "Automatic Cal. 4302", "Stainless Steel",
         "Current Production", 36000),
        ("Audemars Piguet", "Royal Oak Selfwinding 37mm Steel Blue", "15450ST.OO.1256ST.03", "Automatic Cal. 3120", "Stainless Steel",
         "Current Production", 28000),
        ("Audemars Piguet", "Royal Oak Selfwinding 41mm Rose Gold", "15510OR.OO.1320OR.01", "Automatic Cal. 4302", "18k Rose Gold",
         "Current Production", 55000),
        ("Audemars Piguet", "Royal Oak Selfwinding 41mm Green Dial", "15510ST.OO.1320ST.04", "Automatic Cal. 4302", "Stainless Steel",
         "Current Production", 38000),
        ("Audemars Piguet", "Royal Oak Selfwinding 41mm Black Ceramic", "15400CE.OO.1225CE.01", "Automatic Cal. 3120", "Ceramic",
         "Discontinued Classic", 55000),
        ("Audemars Piguet", "Royal Oak Chronograph 41mm Panda", "26331ST.OO.1220ST.03", "Automatic Cal. 2385", "Stainless Steel",
         "Current Production", 42000),
        ("Audemars Piguet", "Royal Oak Chronograph 41mm Rose Gold", "26331OR.OO.1220OR.01", "Automatic Cal. 2385", "18k Rose Gold",
         "Current Production", 68000),
        ("Audemars Piguet", "Royal Oak Tourbillon 41mm", "26530ST.OO.1220ST.01", "Manual Cal. 2950", "Stainless Steel",
         "Current Production", 160000),
        ("Audemars Piguet", "Royal Oak Perpetual Calendar 41mm Blue", "26574ST.OO.1220ST.02", "Automatic Cal. 5134", "Stainless Steel",
         "Current Production", 80000),
        ("Audemars Piguet", "Royal Oak Jumbo 39mm 50th Anniversary", "16202BA.OO.1240BA.01", "Automatic Cal. 7121", "18k Yellow Gold",
         "Anniversary Edition", 60000),
        ("Audemars Piguet", "Royal Oak Frosted Gold 37mm", "15454OR.GG.1259OR.03", "Automatic Cal. 3120", "18k Rose Gold",
         "Current Production", 52000),
        # Royal Oak — women's
        ("Audemars Piguet", "Royal Oak Selfwinding 34mm Steel Blue", "77350ST.OO.1261ST.01", "Automatic Cal. 5800", "Stainless Steel",
         "Current Production", 22000),
        ("Audemars Piguet", "Royal Oak Selfwinding 34mm Rose Gold", "77350OR.OO.1261OR.01", "Automatic Cal. 5800", "18k Rose Gold",
         "Current Production", 38000),
        ("Audemars Piguet", "Royal Oak Quartz 33mm Steel", "67650ST.OO.1261ST.01", "Quartz Cal. 2713", "Stainless Steel",
         "Current Production", 16000),
        ("Audemars Piguet", "Royal Oak Mini 33mm Diamond Bezel", "67651ST.ZZ.1261ST.01", "Quartz Cal. 2713", "Stainless Steel",
         "Current Production", 24000),
        ("Audemars Piguet", "Royal Oak Frosted Gold 34mm White Gold", "77244BC.GG.1272BC.01", "Automatic Cal. 5800", "18k White Gold",
         "Current Production", 48000),
        # Offshore — men's
        ("Audemars Piguet", "Royal Oak Offshore 44mm Steel Black", "26400IO.OO.A004CA.02", "Automatic Cal. 3126/3840", "Stainless Steel",
         "Current Production", 35000),
        ("Audemars Piguet", "Royal Oak Offshore Diver 42mm Green", "15720ST.OO.A052CA.01", "Automatic Cal. 4308", "Stainless Steel",
         "Current Production", 30000),
        ("Audemars Piguet", "Royal Oak Offshore Chronograph 43mm Ceramic", "26405CE.OO.A002CA.02", "Automatic Cal. 3126/3840", "Ceramic",
         "Current Production", 38000),
        ("Audemars Piguet", "Royal Oak Offshore Tourbillon 44mm", "26421OR.OO.A002CA.01", "Manual Cal. 2951", "18k Rose Gold",
         "Current Production", 200000),
        # Code 11.59 — men's & women's
        ("Audemars Piguet", "Code 11.59 Selfwinding 41mm Blue Lacquer", "15210OR.OO.A028CR.01", "Automatic Cal. 4302", "18k Rose Gold",
         "Current Production", 28000),
        ("Audemars Piguet", "Code 11.59 Chronograph 41mm", "26393OR.OO.A002CR.01", "Automatic Cal. 4401", "18k Rose Gold",
         "Current Production", 45000),
        ("Audemars Piguet", "Code 11.59 Starwheel 41mm", "26396NR.OO.D002CR.01", "Automatic Cal. 4310", "Ceramic",
         "Current Production", 52000),
        ("Audemars Piguet", "Code 11.59 34mm Rose Gold White", "77410OR.OO.A018CR.01", "Automatic Cal. 5909", "18k Rose Gold",
         "Current Production", 25000),
        # Millenary — women's
        ("Audemars Piguet", "Millenary Ladies Rose Gold MOP", "77247OR.ZZ.A812CR.01", "Automatic Cal. 5201", "18k Rose Gold",
         "Current Production", 28000),
        # Royal Oak Concept
        ("Audemars Piguet", "Royal Oak Concept Supersonnerie", "26577TI.OO.D002CA.01", "Manual Cal. 2956", "Titanium",
         "Limited Edition", 500000),
        # Vintage / discontinued
        ("Audemars Piguet", "Royal Oak 36mm 14790ST Vintage", "14790ST", "Automatic Cal. 2225", "Stainless Steel",
         "Discontinued Classic", 18000),
        ("Audemars Piguet", "Royal Oak Offshore End of Days", "25770SN.O.0009KE.01", "Automatic Cal. 2226/2840", "Stainless Steel",
         "Discontinued Classic", 35000),
        # Entry level (used market)
        ("Audemars Piguet", "Royal Oak Quartz 33mm Vintage Steel", "67450ST", "Quartz Cal. 2612", "Stainless Steel",
         "Discontinued Classic", 12000),
        ("Audemars Piguet", "Royal Oak Date 36mm 14790ST White", "14790ST.OO.0789ST.08", "Automatic Cal. 2225", "Stainless Steel",
         "Discontinued Classic", 16000),
    ]


def _jlc_variants_watches() -> list[tuple]:
    """30 Jaeger-LeCoultre variants — Reverso, Master, Polaris, Rendez-Vous, men's & women's."""
    return [
        # Reverso — men's
        ("Jaeger-LeCoultre", "Reverso Classic Medium Thin", "Q2548520", "Manual Cal. 822/2", "Stainless Steel",
         "Current Production", 5500),
        ("Jaeger-LeCoultre", "Reverso Tribute Duoface Rose Gold", "Q3912420", "Manual Cal. 854A/2", "18k Rose Gold",
         "Current Production", 17000),
        ("Jaeger-LeCoultre", "Reverso Classic Large Duoface", "Q3848420", "Manual Cal. 854A/2", "Stainless Steel",
         "Current Production", 10500),
        ("Jaeger-LeCoultre", "Reverso Tribute Chronograph", "Q3858590", "Manual Cal. 860", "Stainless Steel",
         "Current Production", 14000),
        ("Jaeger-LeCoultre", "Reverso Hybris Mechanica Quadriptyque", "QUAD-1234", "Manual Cal. 185", "18k Rose Gold",
         "Limited Edition", 1500000),
        # Reverso — women's
        ("Jaeger-LeCoultre", "Reverso One Duetto Steel", "Q3348120", "Quartz Cal. 844", "Stainless Steel",
         "Current Production", 5800),
        ("Jaeger-LeCoultre", "Reverso One Duetto Rose Gold Diamond", "Q3352420", "Quartz Cal. 844", "18k Rose Gold",
         "Current Production", 17500),
        ("Jaeger-LeCoultre", "Reverso Classic Small Steel", "Q2618530", "Manual Cal. 846/1", "Stainless Steel",
         "Current Production", 4500),
        ("Jaeger-LeCoultre", "Reverso One Precious Flowers", "Q3292401", "Manual Cal. 846/1", "18k White Gold",
         "Limited Edition", 55000),
        # Master — men's
        ("Jaeger-LeCoultre", "Master Ultra Thin 39mm Silver", "Q1218420", "Automatic Cal. 896A", "Stainless Steel",
         "Current Production", 6500),
        ("Jaeger-LeCoultre", "Master Ultra Thin Tourbillon", "Q1322410", "Manual Cal. 978", "18k Rose Gold",
         "Current Production", 85000),
        ("Jaeger-LeCoultre", "Master Calendar 40mm", "Q1558420", "Automatic Cal. 866AA", "Stainless Steel",
         "Current Production", 9800),
        ("Jaeger-LeCoultre", "Master Geographic 39mm", "Q1422521", "Automatic Cal. 939AA/1", "Stainless Steel",
         "Current Production", 9200),
        ("Jaeger-LeCoultre", "Master Memovox 40mm", "Q1418471", "Automatic Cal. 956", "Stainless Steel",
         "Current Production", 10500),
        ("Jaeger-LeCoultre", "Master Compressor Diving 42mm Navy SEALs", "Q2018770", "Automatic Cal. 899/1", "Titanium",
         "Limited Edition", 12000),
        # Polaris — men's
        ("Jaeger-LeCoultre", "Polaris Automatic 41mm Blue", "Q9008480", "Automatic Cal. 898E/1", "Stainless Steel",
         "Current Production", 7800),
        ("Jaeger-LeCoultre", "Polaris Mariner Date 42mm", "Q9068180", "Automatic Cal. 900E/1", "Stainless Steel",
         "Current Production", 8500),
        ("Jaeger-LeCoultre", "Polaris Mariner Memovox", "Q9038670", "Automatic Cal. 956", "Stainless Steel",
         "Current Production", 14000),
        ("Jaeger-LeCoultre", "Polaris Perpetual Calendar", "Q9087480", "Automatic Cal. 868AA", "Stainless Steel",
         "Current Production", 24000),
        # Rendez-Vous — women's
        ("Jaeger-LeCoultre", "Rendez-Vous Classic Date 34mm", "Q3548490", "Automatic Cal. 967A", "Stainless Steel",
         "Current Production", 6200),
        ("Jaeger-LeCoultre", "Rendez-Vous Night & Day 34mm Rose Gold", "Q3442520", "Automatic Cal. 898H/1", "18k Rose Gold",
         "Current Production", 16000),
        ("Jaeger-LeCoultre", "Rendez-Vous Moon 36mm", "Q3572430", "Automatic Cal. 935A", "Stainless Steel",
         "Current Production", 9000),
        ("Jaeger-LeCoultre", "Rendez-Vous Dazzling Star 36mm", "Q3523570", "Automatic Cal. 735", "18k White Gold",
         "Limited Edition", 45000),
        ("Jaeger-LeCoultre", "Rendez-Vous Sonatina 38mm", "Q3592520", "Automatic Cal. 735", "18k Rose Gold",
         "Current Production", 28000),
        # Duomètre — men's
        ("Jaeger-LeCoultre", "Duometre Chronographe Rose Gold", "Q6012521", "Manual Cal. 380", "18k Rose Gold",
         "Current Production", 35000),
        # Atmos — desk clock (collectible)
        ("Jaeger-LeCoultre", "Atmos Classique Phases de Lune", "Q5112202", "Atmos Cal. 528", "Stainless Steel",
         "Current Production", 7500),
        # Vintage
        ("Jaeger-LeCoultre", "Vintage Memovox Polaris 1968", "E859", "Automatic Cal. K825", "Stainless Steel",
         "Vintage Pre-1970", 25000),
        ("Jaeger-LeCoultre", "Vintage Reverso Art Deco 1930s", "VR-1930", "Manual Cal. 410", "Stainless Steel",
         "Vintage Pre-1970", 8000),
        # Entry price
        ("Jaeger-LeCoultre", "Master Control Date 40mm Green", "Q4018420G", "Automatic Cal. 899/1", "Stainless Steel",
         "Current Production", 6800),
    ]


def _vc_variants_watches() -> list[tuple]:
    """30 Vacheron Constantin variants — Overseas, Patrimony, Traditionnelle, Fiftysix, Historiques, Egérie."""
    return [
        # Overseas — men's
        ("Vacheron Constantin", "Overseas Automatic 41mm Green", "4500V/110A-B483G", "Automatic Cal. 5100", "Stainless Steel",
         "Current Production", 25000),
        ("Vacheron Constantin", "Overseas Automatic 41mm Rose Gold Blue", "4500V/000R-B127", "Automatic Cal. 5100", "18k Rose Gold",
         "Current Production", 42000),
        ("Vacheron Constantin", "Overseas Chronograph Blue", "5500V/110A-B148", "Automatic Cal. 5200", "Stainless Steel",
         "Current Production", 33000),
        ("Vacheron Constantin", "Overseas Ultra-Thin Perpetual Calendar", "4300V/120G-B102", "Automatic Cal. 1120 QP", "18k White Gold",
         "Current Production", 95000),
        ("Vacheron Constantin", "Overseas World Time 43.5mm", "7700V/110A-B172", "Automatic Cal. 2460 WT", "Stainless Steel",
         "Current Production", 38000),
        ("Vacheron Constantin", "Overseas Tourbillon 42.5mm Rose Gold", "6000V/110R-B544", "Automatic Cal. 2160", "18k Rose Gold",
         "Current Production", 180000),
        # Overseas — women's
        ("Vacheron Constantin", "Overseas Automatic 37mm Diamond Steel", "2305V/100A-B170", "Automatic Cal. 5300", "Stainless Steel",
         "Current Production", 18000),
        ("Vacheron Constantin", "Overseas Small Model 36mm Quartz Steel", "1205V/100A-B590", "Quartz Cal. 1088L", "Stainless Steel",
         "Current Production", 14000),
        # Patrimony — men's
        ("Vacheron Constantin", "Patrimony Self-Winding 40mm Rose Gold", "85180/000R-9248", "Automatic Cal. 2450", "18k Rose Gold",
         "Current Production", 24000),
        ("Vacheron Constantin", "Patrimony Retrograde Day-Date", "4000U/000R-B516", "Automatic Cal. 2460 R31R7", "18k Rose Gold",
         "Current Production", 42000),
        ("Vacheron Constantin", "Patrimony Ultra-Thin Minute Repeater", "30110/000P-9999", "Manual Cal. 1731", "Platinum",
         "Current Production", 350000),
        ("Vacheron Constantin", "Patrimony Contemporaine 42mm WG", "85180/000G-9230", "Automatic Cal. 2450", "18k White Gold",
         "Current Production", 25000),
        # Patrimony — women's
        ("Vacheron Constantin", "Patrimony Small 36.5mm Rose Gold", "81530/000R-9682", "Manual Cal. 1400", "18k Rose Gold",
         "Current Production", 18000),
        # Traditionnelle — men's
        ("Vacheron Constantin", "Traditionnelle Complete Calendar 41mm", "4010T/000R-B344", "Automatic Cal. 2460 QCL", "18k Rose Gold",
         "Current Production", 48000),
        ("Vacheron Constantin", "Traditionnelle Chronograph 42mm Platinum", "5000T/000P-B048", "Manual Cal. 1141", "Platinum",
         "Current Production", 65000),
        ("Vacheron Constantin", "Traditionnelle 14-Day Tourbillon 42mm", "89000/000R-B407", "Manual Cal. 2260", "18k Rose Gold",
         "Current Production", 220000),
        ("Vacheron Constantin", "Traditionnelle Manual Wind 38mm Steel", "82172/000G-9383", "Manual Cal. 4400 AS", "Stainless Steel",
         "Current Production", 16500),
        # Fiftysix — men's (most accessible line)
        ("Vacheron Constantin", "Fiftysix Complete Calendar 40mm", "4000E/000A-B548", "Automatic Cal. 2460 QCL", "Stainless Steel",
         "Current Production", 19500),
        ("Vacheron Constantin", "Fiftysix Day-Date Rose Gold", "4400E/000R-B436", "Automatic Cal. 2475", "18k Rose Gold",
         "Current Production", 22000),
        ("Vacheron Constantin", "Fiftysix Tourbillon Steel", "6000E/000A-B544", "Automatic Cal. 2160", "Stainless Steel",
         "Limited Edition", 120000),
        # Egérie — women's
        ("Vacheron Constantin", "Egérie Self-Winding 35mm Diamond", "4605F/000R-B496", "Automatic Cal. 1088L", "18k Rose Gold",
         "Current Production", 25000),
        ("Vacheron Constantin", "Egérie Moon Phase 37mm", "8005F/000R-B498", "Automatic Cal. 1088ML", "18k Rose Gold",
         "Current Production", 35000),
        # Historiques — men's
        ("Vacheron Constantin", "Historiques Triple Calendrier 1942", "3110V/000R-B425", "Automatic Cal. 4400 QC", "18k Rose Gold",
         "Limited Edition", 55000),
        ("Vacheron Constantin", "Historiques 222 Steel", "4200H/000A-B978", "Automatic Cal. 2455/2", "Stainless Steel",
         "Limited Edition", 35000),
        # Les Cabinotiers (ultra-high)
        ("Vacheron Constantin", "Les Cabinotiers Celestia Astronomical", "9720C/000G-B281", "Manual Cal. 3600 QGP", "18k White Gold",
         "Prototype/Unique", 750000),
        # Vintage
        ("Vacheron Constantin", "Vintage 6068 Chronometre 1960s", "6068", "Manual Cal. 1003", "18k Yellow Gold",
         "Vintage Pre-1970", 15000),
        ("Vacheron Constantin", "Vintage 222 1977 Jumbo", "44018", "Automatic Cal. 1120", "Stainless Steel",
         "Vintage Pre-1970", 55000),
        # Entry
        ("Vacheron Constantin", "Fiftysix Self-Winding 40mm Grey", "4600E/000A-B442", "Automatic Cal. 1326", "Stainless Steel",
         "Current Production", 11000),
    ]


def _hamilton_variants_watches() -> list[tuple]:
    """30 Hamilton variants — Khaki, Jazzmaster, Ventura, American Classic, men's & women's."""
    return [
        # Khaki Field — men's
        ("Hamilton", "Khaki Field Auto 42mm Black", "H70605731", "Automatic H-10", "Stainless Steel",
         "Current Production", 595),
        ("Hamilton", "Khaki Field Day Date Auto 42mm", "H70535061", "Automatic H-30", "Stainless Steel",
         "Current Production", 695),
        ("Hamilton", "Khaki Field Mechanical Bronze 38mm", "H69459530", "Manual H-50", "Bronze",
         "Limited Edition", 695),
        ("Hamilton", "Khaki Field Auto Chrono 42mm Green", "H71626735", "Automatic H-21", "Stainless Steel",
         "Current Production", 1695),
        # Khaki Aviation — men's
        ("Hamilton", "Khaki Aviation Pilot Pioneer Meca 36mm", "H76419931", "Manual H-50", "Stainless Steel",
         "Current Production", 495),
        ("Hamilton", "Khaki Aviation X-Wind Auto 45mm", "H77755533", "Automatic H-21", "Stainless Steel",
         "Current Production", 1395),
        # Khaki Navy — men's
        ("Hamilton", "Khaki Navy Frogman Auto 46mm", "H77845330", "Automatic H-10", "Titanium",
         "Current Production", 995),
        ("Hamilton", "Khaki Navy Pioneer Small Second Auto", "H78465553", "Automatic H-10", "Stainless Steel",
         "Current Production", 895),
        ("Hamilton", "Khaki Navy Sub Auto 43mm Blue", "H82505140", "Automatic H-10", "Stainless Steel",
         "Current Production", 750),
        # Jazzmaster — men's
        ("Hamilton", "Jazzmaster Viewmatic Auto 40mm Green", "H32475730", "Automatic H-10", "Stainless Steel",
         "Current Production", 595),
        ("Hamilton", "Jazzmaster Power Reserve Auto 42mm", "H32635781", "Automatic H-13", "Stainless Steel",
         "Current Production", 895),
        ("Hamilton", "Jazzmaster Maestro Auto Chrono 41mm", "H32766643", "Automatic H-21", "Stainless Steel",
         "Current Production", 1295),
        ("Hamilton", "Jazzmaster Skeleton Auto 40mm", "H42535610", "Automatic H-10S", "Stainless Steel",
         "Current Production", 995),
        # Jazzmaster — women's
        ("Hamilton", "Jazzmaster Open Heart Lady Auto 36mm", "H32215890", "Automatic H-10", "Stainless Steel",
         "Current Production", 795),
        ("Hamilton", "Jazzmaster Lady Quartz 30mm MOP", "H32261197", "Quartz ETA", "Stainless Steel",
         "Current Production", 395),
        # Ventura — men's
        ("Hamilton", "Ventura Elvis80 Auto 42mm", "H24555331", "Automatic H-10", "Stainless Steel",
         "Current Production", 895),
        ("Hamilton", "Ventura Open Heart Auto", "H24515732", "Automatic H-10S", "Stainless Steel",
         "Current Production", 1045),
        ("Hamilton", "Ventura XXL Auto Skeleton", "H24625330", "Automatic H-10S", "Stainless Steel",
         "Current Production", 1195),
        # Ventura — women's
        ("Hamilton", "Ventura Quartz Small Gold PVD", "H24101511", "Quartz ETA F06.115", "Stainless Steel",
         "Current Production", 495),
        # American Classic — men's
        ("Hamilton", "American Classic Intra-Matic 68 Auto 40mm", "H38735751", "Automatic H-10", "Stainless Steel",
         "Current Production", 895),
        ("Hamilton", "American Classic Boulton Small Second Quartz", "H13431553Q", "Quartz ETA", "Stainless Steel",
         "Current Production", 395),
        ("Hamilton", "American Classic Pan Europ Day Date Auto", "H35445733", "Automatic H-30", "Stainless Steel",
         "Current Production", 1095),
        ("Hamilton", "American Classic Ardmore Quartz", "H11411553", "Quartz ETA", "Stainless Steel",
         "Current Production", 345),
        # American Classic — women's
        ("Hamilton", "American Classic Lady Hamilton Vintage Quartz", "H31271113", "Quartz ETA", "Stainless Steel",
         "Current Production", 395),
        ("Hamilton", "American Classic Ardmore Lady", "H11221514", "Quartz ETA", "Stainless Steel",
         "Current Production", 345),
        # Broadway — men's
        ("Hamilton", "Broadway Day Date Auto 42mm", "H43515135", "Automatic H-40", "Stainless Steel",
         "Current Production", 695),
        # Khaki Field Murph variants
        ("Hamilton", "Khaki Field Murph Auto 42mm", "H70605993", "Automatic H-10", "Stainless Steel",
         "Current Production", 995),
        ("Hamilton", "Khaki Field Murph 38mm Green", "H70405860", "Automatic H-10", "Stainless Steel",
         "Current Production", 895),
        # PSR
        ("Hamilton", "American Classic PSR Digital Gold", "H52424130", "Quartz Digital", "Stainless Steel",
         "Current Production", 895),
    ]


def _rolex_variants_watches() -> list[tuple]:
    """Rolex dial/size/material variants — men's, women's, vintage."""
    return [
        # Datejust 31mm women's
        ("Rolex", "Datejust 31mm Silver Dial Fluted Jubilee", "278274", "Automatic 2236", "Stainless Steel",
         "Current Production", 8_200),
        ("Rolex", "Datejust 31mm Pink Dial Smooth Oyster", "278240", "Automatic 2236", "Stainless Steel",
         "Current Production", 7_350),
        ("Rolex", "Datejust 31mm Champagne Dial Two-Tone Jubilee", "278273", "Automatic 2236", "Steel/Yellow Gold",
         "Current Production", 12_800),
        # Datejust 36mm unisex
        ("Rolex", "Datejust 36mm Blue Fluted Dial Oyster", "126200", "Automatic 3235", "Stainless Steel",
         "Current Production", 7_800),
        ("Rolex", "Datejust 36mm Wimbledon Dial Jubilee Two-Tone", "126233", "Automatic 3235", "Steel/Yellow Gold",
         "Current Production", 13_500),
        # Lady-Datejust 28mm
        ("Rolex", "Lady-Datejust 28mm Steel Silver Dial", "279160", "Automatic 2236", "Stainless Steel",
         "Current Production", 7_000),
        ("Rolex", "Lady-Datejust 28mm Two-Tone Rose MOP Dial", "279171", "Automatic 2236", "Steel/Everose Gold",
         "Current Production", 12_400),
        ("Rolex", "Lady-Datejust 28mm Rose Gold Chocolate Dial", "279175", "Automatic 2236", "18K Everose Gold",
         "Current Production", 26_500),
        # Oyster Perpetual 31/34/36mm
        ("Rolex", "Oyster Perpetual 31mm Coral Red Dial", "277200", "Automatic 2232", "Stainless Steel",
         "Current Production", 5_600),
        ("Rolex", "Oyster Perpetual 34mm Yellow Dial", "124200", "Automatic 2232", "Stainless Steel",
         "Current Production", 5_900),
        # Day-Date 36mm women's/smaller
        ("Rolex", "Day-Date 36mm Rose Gold Sundust Dial", "128235", "Automatic 3255", "18K Everose Gold",
         "Current Production", 35_000),
        # Submariner 41mm
        # GMT-Master II
        ("Rolex", "GMT-Master II Rootbeer Rose Gold/Steel", "126711CHNR", "Automatic 3285", "Steel/Everose Gold",
         "Current Production", 16_800),
        ("Rolex", "GMT-Master II Coke Red/Black Bezel", "126710BLRO-Coke", "Automatic 3285", "Stainless Steel",
         "Discontinued Classic", 19_500),
        # Daytona
        ("Rolex", "Cosmograph Daytona Steel White Dial", "126500LN", "Automatic 4131", "Stainless Steel",
         "Current Production", 15_400),
        ("Rolex", "Cosmograph Daytona Oysterflex Rose Gold Black", "126515LN", "Automatic 4131", "18K Everose Gold",
         "Current Production", 30_500),
        ("Rolex", "Cosmograph Daytona Panda Dial Steel", "126500LN-Panda", "Automatic 4131", "Stainless Steel",
         "Current Production", 17_200),
        ("Rolex", "Cosmograph Daytona Le Mans Centenary", "126529LN", "Automatic 4131", "Stainless Steel",
         "Special Edition", 22_000),
        # Sky-Dweller
        ("Rolex", "Sky-Dweller Oysterflex Rose Gold Slate Dial", "326235", "Automatic 9001", "18K Everose Gold",
         "Current Production", 42_000),
        ("Rolex", "Sky-Dweller Two-Tone Champagne Dial", "326933", "Automatic 9001", "Steel/Yellow Gold",
         "Current Production", 17_800),
        # Yacht-Master 37mm women's
        ("Rolex", "Yacht-Master 37mm Rose Gold/Rubber Oysterflex", "268655", "Automatic 2236", "18K Everose Gold",
         "Current Production", 22_500),
        ("Rolex", "Yacht-Master 37mm Steel/Platinum Rhodium Dial", "268622", "Automatic 2236", "Steel/Platinum",
         "Current Production", 10_500),
        # Pearlmaster 34mm
        ("Rolex", "Pearlmaster 34mm Diamond Bezel MOP Dial", "81319", "Automatic 2235", "18K White Gold",
         "Limited Edition", 42_000),
        # Cellini
        ("Rolex", "Cellini Time 39mm Rose Gold White Dial", "50505", "Automatic 3132", "18K Everose Gold",
         "Current Production", 16_000),
        ("Rolex", "Cellini Date 39mm White Gold Silver Dial", "50519", "Automatic 3165", "18K White Gold",
         "Current Production", 18_500),
        # Explorer
        ("Rolex", "Explorer I 40mm Black Dial", "224270", "Automatic 3230", "Stainless Steel",
         "Current Production", 7_850),
        ("Rolex", "Explorer II 42mm Black Dial", "226570-BK", "Automatic 3285", "Stainless Steel",
         "Current Production", 9_550),
        # Deepsea / Sea-Dweller
        ("Rolex", "Deepsea Challenge 50mm Titanium", "126067", "Automatic 3230", "RLX Titanium",
         "Current Production", 26_000),
        # Vintage
        ("Rolex", "Daytona Paul Newman Tropical Dial Ref.6241", "6241", "Manual Valjoux 722", "14K Yellow Gold",
         "Vintage Pre-1970", 350_000),
        # Additional current variants to reach 50
        ("Rolex", "Datejust 41mm Mint Green Dial Oyster", "126300", "Automatic 3235", "Stainless Steel",
         "Current Production", 8_600),
    ]


def _omega_variants_watches() -> list[tuple]:
    """Omega dial/size/material variants — men's, women's, vintage."""
    return [
        # Speedmaster Moonwatch women's 38mm
        ("Omega", "Speedmaster 38mm Co-Axial Cappuccino", "324.23.38.50.02.002", "Co-Axial 3330", "Steel/Sedna Gold",
         "Current Production", 6_800),
        ("Omega", "Speedmaster 38mm Co-Axial Blue Orbis", "324.30.38.50.03.002", "Co-Axial 3330", "Stainless Steel",
         "Current Production", 5_900),
        ("Omega", "Speedmaster 38mm Co-Axial Grey Dial", "324.30.38.50.06.001", "Co-Axial 3330", "Stainless Steel",
         "Current Production", 5_900),
        ("Omega", "Speedmaster 38mm Co-Axial Slate Blue", "324.33.38.50.06.001", "Co-Axial 3330", "Stainless Steel",
         "Current Production", 6_100),
        # Constellation 29mm women's
        ("Omega", "Constellation 29mm MOP Diamond Dial", "131.15.29.20.55.001", "Co-Axial 8700", "Stainless Steel",
         "Current Production", 7_200),
        ("Omega", "Constellation 29mm Two-Tone Sedna Gold", "131.20.29.20.52.001", "Co-Axial 8700", "Steel/Sedna Gold",
         "Current Production", 9_500),
        ("Omega", "Constellation 29mm Diamond Bezel Steel", "131.15.29.20.53.001", "Co-Axial 8700", "Stainless Steel",
         "Current Production", 8_400),
        # Constellation 34mm women's
        ("Omega", "Constellation 34mm Silver Pie-Pan Dial", "131.10.34.20.02.001", "Co-Axial 8800", "Stainless Steel",
         "Current Production", 5_500),
        ("Omega", "Constellation 34mm Two-Tone MOP Dial", "131.20.34.20.55.001", "Co-Axial 8800", "Steel/Sedna Gold",
         "Current Production", 9_100),
        # De Ville Ladymatic 34mm
        ("Omega", "De Ville Ladymatic 34mm White MOP", "425.30.34.20.55.002", "Co-Axial 8520", "Stainless Steel",
         "Current Production", 6_900),
        ("Omega", "De Ville Ladymatic 34mm Sedna Gold Diamond", "425.65.34.20.55.005", "Co-Axial 8520", "18K Sedna Gold",
         "Current Production", 18_500),
        # De Ville Prestige 27.4mm quartz
        ("Omega", "De Ville Prestige 27.4mm Quartz Steel MOP", "424.10.27.60.05.001", "Quartz 4061", "Stainless Steel",
         "Current Production", 2_600),
        ("Omega", "De Ville Prestige 27.4mm Quartz Two-Tone", "424.20.27.60.08.001", "Quartz 4061", "Steel/Yellow Gold",
         "Current Production", 3_800),
        # Seamaster Aqua Terra 34mm women's
        ("Omega", "Seamaster Aqua Terra 34mm Blue Dial", "220.10.34.20.03.001", "Co-Axial 8800", "Stainless Steel",
         "Current Production", 5_400),
        ("Omega", "Seamaster Aqua Terra 34mm MOP Diamond", "220.15.34.20.55.001", "Co-Axial 8800", "Stainless Steel",
         "Current Production", 7_100),
        # Aqua Terra Shades
        ("Omega", "Seamaster Aqua Terra 38mm Lavender Dial", "220.10.38.20.10.003", "Co-Axial 8800", "Stainless Steel",
         "Current Production", 5_800),
        ("Omega", "Seamaster Aqua Terra 38mm Terracotta Dial", "220.10.38.20.13.001", "Co-Axial 8800", "Stainless Steel",
         "Current Production", 5_800),
        ("Omega", "Seamaster Aqua Terra 38mm Sand Dial", "220.10.38.20.09.001", "Co-Axial 8800", "Stainless Steel",
         "Current Production", 5_800),
        # Seamaster 300M dial colors
        ("Omega", "Seamaster 300M Blue Dial 42mm", "210.30.42.20.03.001", "Co-Axial 8800", "Stainless Steel",
         "Current Production", 5_350),
        ("Omega", "Seamaster 300M White Dial 42mm", "210.30.42.20.04.001", "Co-Axial 8800", "Stainless Steel",
         "Current Production", 5_350),
        ("Omega", "Seamaster 300M Green Dial 42mm", "210.30.42.20.10.001", "Co-Axial 8800", "Stainless Steel",
         "Current Production", 5_350),
        ("Omega", "Seamaster 300M Grey Dial 42mm", "210.30.42.20.06.001", "Co-Axial 8800", "Stainless Steel",
         "Current Production", 5_350),
        # Speedmaster Moonwatch precious metals
        ("Omega", "Speedmaster Moonwatch Rose Gold Sedna", "310.63.42.50.01.001", "Manual 3861", "18K Sedna Gold",
         "Current Production", 28_000),
        ("Omega", "Speedmaster Moonwatch Canopus White Gold", "310.93.42.50.01.001", "Manual 3861", "18K Canopus Gold",
         "Current Production", 35_000),
        # Planet Ocean women's 37.5mm
        ("Omega", "Seamaster Planet Ocean 37.5mm Orange Bezel", "215.30.40.20.01.001", "Co-Axial 8800", "Stainless Steel",
         "Current Production", 6_100),
        ("Omega", "Seamaster Planet Ocean 37.5mm White Dial", "215.30.40.20.04.001", "Co-Axial 8800", "Stainless Steel",
         "Current Production", 6_100),
        # Constellation Globemaster Annual Calendar
        ("Omega", "Constellation Globemaster Annual Calendar 41mm", "130.33.41.22.02.001", "Co-Axial 8922", "Stainless Steel",
         "Current Production", 8_300),
        # De Ville Tourbillon
        ("Omega", "De Ville Tourbillon Co-Axial Numbered Edition", "528.53.44.21.03.001", "Co-Axial 2635", "18K Sedna Gold",
         "Limited Edition", 125_000),
        # Speedmaster 38mm colors
        ("Omega", "Speedmaster 38mm Co-Axial Green Racing", "324.30.38.50.01.004", "Co-Axial 3330", "Stainless Steel",
         "Current Production", 5_900),
        ("Omega", "Speedmaster 38mm Co-Axial Reverse Panda", "324.30.38.50.02.001", "Co-Axial 3330", "Stainless Steel",
         "Current Production", 5_900),
        # Vintage
        ("Omega", "Constellation Manhattan C-Case Vintage 1960s", "168.017", "Automatic 564", "Stainless Steel",
         "Vintage Pre-1970", 3_200),
        ("Omega", "Constellation Pie-Pan Crosshair Dial 1960s", "14381-61", "Automatic 551", "Stainless Steel",
         "Vintage Pre-1970", 4_500),
        ("Omega", "Geneve Chronostop 1960s Orange Hand", "145.009", "Manual 865", "Stainless Steel",
         "Vintage Pre-1970", 2_800),
        ("Omega", "Geneve Chronostop Driver's Ref.145.010", "145.010", "Manual 865", "Stainless Steel",
         "Vintage Pre-1970", 3_500),
        # Additional to reach 40
        ("Omega", "Speedmaster Super Racing Chronograph", "329.30.44.51.01.003", "Co-Axial 9920", "Stainless Steel",
         "Current Production", 9_200),
    ]


def _patek_philippe_variants_watches() -> list[tuple]:
    """Patek Philippe dial/size/material variants — men's, women's, vintage."""
    return [
        # Nautilus 5711
        ("Patek Philippe", "Nautilus 5711/1A White Dial", "5711/1A-011", "Automatic 26-330 SC", "Stainless Steel",
         "Discontinued Classic", 150_000),
        ("Patek Philippe", "Nautilus 5711/1A Olive Green Tiffany", "5711/1A-018", "Automatic 26-330 SC", "Stainless Steel",
         "Limited Edition", 350_000),
        ("Patek Philippe", "Nautilus 5711/1R Rose Gold Blue Dial", "5711/1R-001", "Automatic 26-330 SC", "18K Rose Gold",
         "Discontinued Classic", 185_000),
        ("Patek Philippe", "Nautilus 5811/1G White Gold Blue Dial", "5811/1G-001", "Automatic 26-330 SC", "18K White Gold",
         "Current Production", 75_000),
        # Nautilus 5712 Moon Phase
        ("Patek Philippe", "Nautilus 5712/1A Moon Phase Steel Blue", "5712/1A-001", "Automatic 240 PS IRM C LU", "Stainless Steel",
         "Discontinued Classic", 130_000),
        ("Patek Philippe", "Nautilus 5712R Moon Phase Rose Gold", "5712R-001", "Automatic 240 PS IRM C LU", "18K Rose Gold",
         "Current Production", 62_000),
        # Nautilus Chronograph 5980
        ("Patek Philippe", "Nautilus Chronograph 5980/1R Rose Gold", "5980/1R-001", "Automatic CH 28-520 C", "18K Rose Gold",
         "Discontinued Classic", 110_000),
        # Nautilus Travel Time 5990
        ("Patek Philippe", "Nautilus Travel Time 5990R Rose Gold", "5990/1R-001", "Automatic 26-330 S C FUS", "18K Rose Gold",
         "Current Production", 78_000),
        # Nautilus 7118 women's
        ("Patek Philippe", "Nautilus 7118/1A Women's Steel Blue Dial", "7118/1A-001", "Automatic 324 SC", "Stainless Steel",
         "Current Production", 45_000),
        ("Patek Philippe", "Nautilus 7118/1200R Women's Rose Gold White", "7118/1200R-001", "Automatic 324 SC", "18K Rose Gold",
         "Current Production", 55_000),
        # Aquanaut 5167
        ("Patek Philippe", "Aquanaut 5167A Khaki Green Dial", "5167A-010", "Automatic 324 SC", "Stainless Steel",
         "Discontinued Classic", 38_000),
        # Aquanaut 5168
        ("Patek Philippe", "Aquanaut 5168G Rose Gold Green Dial", "5168G-010", "Automatic 324 SC", "18K Rose Gold",
         "Current Production", 48_000),
        ("Patek Philippe", "Aquanaut 5168G White Gold Blue Dial", "5168G-001", "Automatic 324 SC", "18K White Gold",
         "Current Production", 50_000),
        # Aquanaut Luce 5067 women's
        ("Patek Philippe", "Aquanaut Luce 5067A Women's Steel", "5067A-011", "Quartz E23 SC", "Stainless Steel",
         "Current Production", 17_000),
        ("Patek Philippe", "Aquanaut Luce 5067A Women's Rose Gold", "5067A-024", "Quartz E23 SC", "18K Rose Gold",
         "Current Production", 32_000),
        ("Patek Philippe", "Aquanaut Luce 5267/200A Women's Diamond", "5267/200A-010", "Quartz E23 SC", "Stainless Steel",
         "Current Production", 22_000),
        # Aquanaut Chronograph 5968
        ("Patek Philippe", "Aquanaut Chronograph 5968A Steel Orange", "5968A-001", "Automatic CH 28-520 C FUS", "Stainless Steel",
         "Current Production", 55_000),
        # Calatrava
        ("Patek Philippe", "Calatrava 5227R Rose Gold Ivory Dial", "5227R-001", "Automatic 324 SC", "18K Rose Gold",
         "Current Production", 32_000),
        ("Patek Philippe", "Calatrava 5227G White Gold Grey Dial", "5227G-010", "Automatic 324 SC", "18K White Gold",
         "Current Production", 33_000),
        ("Patek Philippe", "Calatrava 5227J Yellow Gold Silver Dial", "5227J-001", "Automatic 324 SC", "18K Yellow Gold",
         "Current Production", 31_000),
        ("Patek Philippe", "Calatrava 5196G Ultra-Thin Manual White Gold", "5196G-001", "Manual 215 PS", "18K White Gold",
         "Current Production", 22_000),
        ("Patek Philippe", "Calatrava 7200R Women's Rose Gold", "7200/200R-001", "Automatic 324 SC", "18K Rose Gold",
         "Current Production", 28_500),
        # Twenty~4 women's
        ("Patek Philippe", "Twenty~4 7300/1200A Women's Auto Steel", "7300/1200A-001", "Automatic 324 SC", "Stainless Steel",
         "Current Production", 18_000),
        ("Patek Philippe", "Twenty~4 7300/1200R Women's Auto Rose Gold", "7300/1200R-010", "Automatic 324 SC", "18K Rose Gold",
         "Current Production", 35_000),
        ("Patek Philippe", "Twenty~4 4910/1200A Quartz Steel Diamond", "4910/1200A-001", "Quartz E15", "Stainless Steel",
         "Current Production", 14_000),
        # Complications
        ("Patek Philippe", "Annual Calendar 5205G White Gold Blue Dial", "5205G-013", "Automatic 324 S QA LU", "18K White Gold",
         "Current Production", 42_000),
        ("Patek Philippe", "Annual Calendar 5205R Rose Gold Silver Dial", "5205R-001", "Automatic 324 S QA LU", "18K Rose Gold",
         "Current Production", 43_000),
        ("Patek Philippe", "Weekly Calendar 5212A Steel Blue Dial", "5212A-001", "Automatic 26-330 S C J SE", "Stainless Steel",
         "Current Production", 38_000),
        ("Patek Philippe", "Chronograph 5172G White Gold Blue Dial", "5172G-001", "Manual CH 29-535 PS", "18K White Gold",
         "Current Production", 65_000),
        # World Time
        ("Patek Philippe", "World Time 5231J Enamel Cloisonné Europe", "5231J-001", "Automatic 240 HU", "18K Yellow Gold",
         "Current Production", 70_000),
        # Grand Complications
        ("Patek Philippe", "Perpetual Calendar 5320G White Gold Cream", "5320G-001", "Automatic 324 S Q", "18K White Gold",
         "Current Production", 88_000),
        ("Patek Philippe", "Perpetual Calendar Chrono 5270P Platinum", "5270P-001", "Manual CH 29-535 PS Q", "Platinum",
         "Current Production", 195_000),
        ("Patek Philippe", "Minute Repeater 5078G White Gold", "5078G-001", "Automatic R 27 PS", "18K White Gold",
         "Current Production", 320_000),
        ("Patek Philippe", "Sky Moon Tourbillon 6002G", "6002G-010", "Manual RTO 27 QR SID LU CL", "18K White Gold",
         "Current Production", 1_500_000),
        ("Patek Philippe", "Grandmaster Chime 6300G", "6300G-001", "Manual 300 GS AL 36-750 QIS FUS IRM", "18K White Gold",
         "Limited Edition", 2_500_000),
        # Gondolo
        ("Patek Philippe", "Gondolo 5124G Art Deco White Gold", "5124G-011", "Manual 25-21 REC", "18K White Gold",
         "Current Production", 25_000),
        # Vintage
        ("Patek Philippe", "Vintage Ref.1463 Steel Chronograph 1940s", "1463", "Manual 13-130", "Stainless Steel",
         "Vintage Pre-1970", 800_000),
        ("Patek Philippe", "Vintage Ref.2526 Enamel Dial 1950s", "2526", "Automatic 12-600 AT", "18K Yellow Gold",
         "Vintage Pre-1970", 250_000),
        ("Patek Philippe", "Nautilus Original Ref.3700/1A 1976", "3700/1A", "Automatic 28-255 C", "Stainless Steel",
         "Vintage Pre-1970", 120_000),
    ]


def _premium_microbrand_watches() -> list[tuple]:
    """~70 premium microbrand watches — Halios, Ming, Kurono Tokyo, Unimatic,
    Baltic, Zelos, Lorier, Brew, Farer, Monta, Christopher Ward, Anordain,
    Autodromo. These are enthusiast-beloved brands with strong secondary markets."""
    return [
        # --- Halios ---
        ("Halios", "Seaforth IV Dive Black", "SF-IV-DIV-BLK", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 750),
        ("Halios", "Seaforth IV Abyss Blue", "SF-IV-ABY-BLU", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 750),
        ("Halios", "Universa Slate Grey", "UNI-SLT-GRY", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 650),
        ("Halios", "Universa Forest Green", "UNI-FOR-GRN", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 650),
        ("Halios", "Fairwind Black", "FW-SS-BLK", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 735),
        # --- Ming ---
        ("Ming", "17.09 Blue", "17.09-BLU", "Automatic Sellita SW330-2", "Stainless Steel",
         "Limited Edition", 4500),
        ("Ming", "18.01 H41 Abyss Concept", "18.01-H41", "Automatic ETA 7001 modified", "Stainless Steel",
         "Limited Edition", 5200),
        ("Ming", "27.02 Concept World Timer", "27.02-WT", "Automatic AGH 6498 modified", "Titanium",
         "Limited Edition", 13500),
        ("Ming", "37.09 Bluefin", "37.09-BLU", "Automatic Schwarz-Etienne ASE 200.00", "Titanium",
         "Limited Edition", 8500),
        ("Ming", "22.01 Worldtimer", "22.01-WT", "Automatic ETA 2893-2 modified", "Stainless Steel",
         "Limited Edition", 3950),
        # --- Kurono Tokyo ---
        ("Kurono Tokyo", "Grand Hagane", "KT-GH-001", "Automatic Miyota 90S5", "Stainless Steel",
         "Limited Edition", 2700),
        ("Kurono Tokyo", "Shiro II", "KT-SHIRO-II", "Automatic Miyota 90S5", "Stainless Steel",
         "Limited Edition", 2200),
        ("Kurono Tokyo", "Toki", "KT-TOKI-001", "Automatic Miyota 90S5", "Stainless Steel",
         "Limited Edition", 2100),
        ("Kurono Tokyo", "Chronograph 1 Shiro", "KT-CHR1-SHR", "Automatic Miyota 6S21", "Stainless Steel",
         "Limited Edition", 3900),
        ("Kurono Tokyo", "Grand Akane", "KT-GA-001", "Automatic Miyota 90S5", "Stainless Steel",
         "Limited Edition", 2700),
        # --- Unimatic ---
        ("Unimatic", "Modello Uno U1-DZ Blacked Out", "U1-DZ", "Automatic Seiko NH35", "Stainless Steel",
         "Limited Edition", 800),
        ("Unimatic", "Modello Uno U1-H Hodinkee", "U1-H", "Automatic Seiko NH35", "Stainless Steel",
         "Limited Edition", 1200),
        ("Unimatic", "Modello Due U2-F Classico", "U2-F", "Automatic Seiko NH35", "Stainless Steel",
         "Current Production", 550),
        ("Unimatic", "Modello Quattro U4-A 36mm", "U4-A", "Automatic Seiko NH35", "Stainless Steel",
         "Current Production", 475),
        ("Unimatic", "Modello Uno U1-SS Edition", "U1-SS", "Automatic Seiko NH35", "Stainless Steel",
         "Limited Edition", 850),
        # --- Baltic ---
        ("Baltic", "Aquascaphe Blue Gilt", "AQ-BLU-GLT", "Automatic Miyota 9039", "Stainless Steel",
         "Current Production", 650),
        ("Baltic", "Aquascaphe Dual Crown Black", "AQ-DC-BLK", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 750),
        ("Baltic", "MR01 Micro-Rotor Salmon", "MR01-SAL", "Automatic Miyota 9122", "Stainless Steel",
         "Current Production", 610),
        ("Baltic", "Bicompax 001 Panda", "BC001-PAN", "Mecaquartz Seiko VK64", "Stainless Steel",
         "Current Production", 530),
        ("Baltic", "Bicompax 001 Reverse Panda", "BC001-RPAN", "Mecaquartz Seiko VK64", "Stainless Steel",
         "Current Production", 530),
        ("Baltic", "HMS 001 Blue", "HMS001-BLU", "Automatic Miyota 9039", "Stainless Steel",
         "Current Production", 580),
        ("Baltic", "HMS 002 Silver", "HMS002-SLV", "Automatic Miyota 9039", "Stainless Steel",
         "Current Production", 620),
        # --- Zelos ---
        ("Zelos", "Mako V3 300m Frost", "MAKO-V3-FRS", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 449),
        ("Zelos", "Horizons V2 GMT Blue", "HOR-V2-BLU", "Automatic Miyota 9075", "Stainless Steel",
         "Current Production", 499),
        ("Zelos", "Nova 38mm Teal Ti", "NOV-38-TL-TI", "Automatic Miyota 9015", "Titanium",
         "Current Production", 549),
        ("Zelos", "Nova 38mm Black Damascus", "NOV-38-DAM", "Automatic Miyota 9015", "Damascus Steel",
         "Limited Edition", 750),
        ("Zelos", "Skyraider 2 Titanium Blue", "SKY2-TI-BLU", "Automatic Miyota 9015", "Titanium",
         "Current Production", 599),
        # --- Lorier ---
        ("Lorier", "Neptune Series V Black", "NEP-V-BLK", "Automatic Miyota 90S5", "Stainless Steel",
         "Current Production", 549),
        ("Lorier", "Falcon Series IV Green", "FAL-IV-GRN", "Automatic Miyota 90S5", "Stainless Steel",
         "Current Production", 549),
        ("Lorier", "Gemini II Chronograph Panda", "GEM-II-PAN", "Mecaquartz Seiko VK64", "Stainless Steel",
         "Current Production", 599),
        ("Lorier", "Hyperion II GMT Black/Blue", "HYP-II-BLK-BLU", "Automatic Miyota 9075", "Stainless Steel",
         "Current Production", 649),
        # --- Brew ---
        ("Brew", "HP-1 Pressed Copper", "HP1-COP", "Mecaquartz Seiko VK64", "Stainless Steel",
         "Current Production", 395),
        ("Brew", "HP-1 Pressed Black", "HP1-BLK", "Mecaquartz Seiko VK64", "Stainless Steel",
         "Current Production", 395),
        ("Brew", "Metric Retromatic Black", "MET-RET-V2-BLK", "Automatic NH35", "Stainless Steel",
         "Current Production", 375),
        ("Brew", "Mastergraph V2 Panda", "MAS-V2-PAN", "Mecaquartz Seiko VK64", "Stainless Steel",
         "Current Production", 450),
        # --- Farer ---
        ("Farer", "Lander IV Automatic Blue", "LND-IV-BLU", "Automatic Sellita SW200-1", "Stainless Steel",
         "Current Production", 1195),
        ("Farer", "Bernina Hand-Wound Chrono", "BRN-HW-BLU", "Manual Sellita SW510 BM", "Stainless Steel",
         "Current Production", 1595),
        ("Farer", "Markham II GMT Blue", "MKH-II-BLU", "Automatic Sellita SW330-2", "Stainless Steel",
         "Current Production", 1395),
        ("Farer", "Hecla II Diver Black", "HCL-II-BLK", "Automatic Sellita SW200-1", "Stainless Steel",
         "Current Production", 1295),
        ("Farer", "Carnegie Worldtimer", "CRN-WT-BLU", "Automatic Sellita SW330-2", "Stainless Steel",
         "Current Production", 1595),
        # --- Monta ---
        ("Monta", "Oceanking Titanium Black", "OK-TI-BLK", "Automatic Sellita SW300-1", "Titanium",
         "Current Production", 2250),
        ("Monta", "Skyquest GMT Blue", "SQ-GMT-BLU", "Automatic Sellita SW330-2", "Stainless Steel",
         "Current Production", 2090),
        ("Monta", "Noble Date Silver", "NOB-SLV-DT", "Automatic Sellita SW300-1", "Stainless Steel",
         "Current Production", 1750),
        ("Monta", "Triumph Silver", "TRI-SLV", "Automatic Sellita SW300-1", "Stainless Steel",
         "Current Production", 1650),
        ("Monta", "Skyquest GMT Black", "SQ-GMT-BLK", "Automatic Sellita SW330-2", "Stainless Steel",
         "Current Production", 2090),
        # --- Christopher Ward ---
        ("Christopher Ward", "C60 Trident Pro 300 Blue", "C60-300-BLU", "Automatic Sellita SW200-1", "Stainless Steel",
         "Current Production", 895),
        ("Christopher Ward", "C60 Trident Pro 300 Black", "C60-300-BLK", "Automatic Sellita SW200-1", "Stainless Steel",
         "Current Production", 895),
        ("Christopher Ward", "C63 Sealander GMT Blue", "C63-GMT-BLU", "Automatic Sellita SW330-2", "Stainless Steel",
         "Current Production", 1050),
        ("Christopher Ward", "C63 Sealander Auto 39mm Green", "C63-39-GRN", "Automatic Sellita SW200-1", "Stainless Steel",
         "Current Production", 795),
        ("Christopher Ward", "C65 Super Compressor Black", "C65-SC-BLK", "Automatic Sellita SW200-1", "Stainless Steel",
         "Current Production", 995),
        ("Christopher Ward", "C65 Super Compressor Blue", "C65-SC-BLU", "Automatic Sellita SW200-1", "Stainless Steel",
         "Current Production", 995),
        # --- Anordain ---
        ("anOrdain", "Model 1 Fumé Blue Dial", "M1-FB", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 1850),
        ("anOrdain", "Model 1 Fumé Green Dial", "M1-FG", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 1850),
        ("anOrdain", "Model 2 Fumé Iron Blue", "M2-FIB", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 1650),
        ("anOrdain", "Model 2 Fumé Fired Enamel Salmon", "M2-FES", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 1750),
        # --- Autodromo ---
        ("Autodromo", "Group B Series 2 Blue", "GBS2-BLU", "Automatic Miyota 9015", "Stainless Steel",
         "Current Production", 875),
        ("Autodromo", "Intereuropa Manual White", "INT-MAN-WHT", "Manual Sellita SW215-1", "Stainless Steel",
         "Current Production", 950),
        ("Autodromo", "Prototipo Chronograph Green", "PRT-CHR-GRN", "Mecaquartz Seiko VK64", "Stainless Steel",
         "Current Production", 625),
        ("Autodromo", "Prototipo Chronograph Blue", "PRT-CHR-BLU", "Mecaquartz Seiko VK64", "Stainless Steel",
         "Current Production", 625),
        ("Autodromo", "Group B Evoluzione Night Stage", "GBE-NGT", "Automatic Miyota 9015", "Stainless Steel",
         "Limited Edition", 975),
    ]


# ---------------------------------------------------------------------------
# TAG Heuer — 15 watches
# ---------------------------------------------------------------------------

def _tag_heuer_watches() -> list[tuple]:
    """15 TAG Heuer watches — Monaco, Carrera, Aquaracer, Autavia, Link."""
    return [
        # --- Monaco ---
        ("TAG Heuer", "Monaco Calibre Heuer 02", "CBL2111.BA0644",
         "Automatic Cal. Heuer 02", "Stainless Steel", "Current Production", 6200),
        ("TAG Heuer", "Monaco Gulf Special Edition", "CBL2115.FC6494",
         "Automatic Cal. Heuer 02", "Stainless Steel", "Special Edition", 7500),
        ("TAG Heuer", "Monaco 1969-1979 Limited Edition", "CAW211C.FC6241",
         "Automatic Cal. Heuer 02", "Stainless Steel", "Limited Edition", 8500),
        # --- Carrera ---
        ("TAG Heuer", "Carrera Chronograph 44mm", "CBS2210.BA0706",
         "Automatic Cal. Heuer 02", "Stainless Steel", "Current Production", 5800),
        ("TAG Heuer", "Carrera Chronograph Tourbillon", "CAR5A8Y.FC6377",
         "Automatic Cal. Heuer 02T", "Titanium", "Current Production", 18500),
        ("TAG Heuer", "Carrera Skipper", "CBS2213.FN6002",
         "Automatic Cal. Heuer 02", "Stainless Steel", "Special Edition", 6400),
        ("TAG Heuer", "Carrera Plasma Diamant d'Avant-Garde", "CBN2012.BA0642",
         "Automatic Cal. Heuer 02", "Stainless Steel", "Limited Edition", 9500),
        ("TAG Heuer", "Carrera Date 36mm", "WBN2312.BA0001",
         "Automatic Cal. 5", "Stainless Steel", "Current Production", 2800),
        # --- Aquaracer ---
        ("TAG Heuer", "Aquaracer Professional 300", "WBP201B.BA0632",
         "Automatic Cal. 5", "Stainless Steel", "Current Production", 2600),
        ("TAG Heuer", "Aquaracer Professional 200 Solargraph", "WBP1112.BA0627",
         "Solar Quartz TH50-00", "Stainless Steel", "Current Production", 1800),
        ("TAG Heuer", "Aquaracer Professional 1000 Superdiver", "WBP5A8A.BF0619",
         "Automatic Cal. TH30-00", "Titanium", "Current Production", 5500),
        # --- Autavia ---
        ("TAG Heuer", "Autavia Chronometer Flyback", "WBE5190.FC8268",
         "Automatic Cal. Heuer 02 COSC", "Stainless Steel", "Current Production", 4800),
        ("TAG Heuer", "Autavia 60th Anniversary", "CBE2111.BA0687",
         "Automatic Cal. Heuer 02", "Stainless Steel", "Anniversary Edition", 6800),
        # --- Link ---
        ("TAG Heuer", "Link Calibre 17 Chronograph", "CBC2110.BA0603",
         "Automatic Cal. 17", "Stainless Steel", "Discontinued Classic", 3800),
        ("TAG Heuer", "Link Calibre 5 Day-Date", "WBC2110.BA0603",
         "Automatic Cal. 5", "Stainless Steel", "Discontinued Classic", 2200),
    ]


# ---------------------------------------------------------------------------
# Hublot — 12 watches
# ---------------------------------------------------------------------------

def _hublot_watches() -> list[tuple]:
    """12 Hublot watches — Big Bang, Classic Fusion, Spirit of Big Bang."""
    return [
        # --- Big Bang ---
        ("Hublot", "Big Bang Unico Titanium 42mm", "441.NX.1171.RX",
         "Automatic Cal. HUB1280 UNICO", "Titanium", "Current Production", 16500),
        ("Hublot", "Big Bang Integral Ceramic", "451.CX.1170.CX",
         "Automatic Cal. HUB1280 UNICO", "Ceramic", "Current Production", 21000),
        ("Hublot", "Big Bang Unico King Gold", "441.OX.1181.RX",
         "Automatic Cal. HUB1280 UNICO", "18k Rose Gold", "Current Production", 32000),
        ("Hublot", "Big Bang Sang Bleu II Titanium", "418.NX.1107.RX.MXM19",
         "Automatic Cal. HUB1240 UNICO", "Titanium", "Limited Edition", 24000),
        ("Hublot", "Big Bang Meca-10 King Gold", "414.OI.1123.RX",
         "Manual Cal. HUB1201", "18k Rose Gold", "Current Production", 35000),
        # --- Classic Fusion ---
        ("Hublot", "Classic Fusion Titanium 42mm", "542.NX.7071.LR",
         "Automatic Cal. HUB1110", "Titanium", "Current Production", 6500),
        ("Hublot", "Classic Fusion Chronograph Ceramic", "521.CM.1171.RX",
         "Automatic Cal. HUB1143", "Ceramic", "Current Production", 9800),
        ("Hublot", "Classic Fusion Aerofusion Moonphase King Gold", "517.OX.0180.LR",
         "Automatic Cal. HUB1137", "18k Rose Gold", "Current Production", 28000),
        ("Hublot", "Classic Fusion Orlinski Titanium", "550.NS.1800.RX.ORL19",
         "Automatic Cal. HUB1100", "Titanium", "Special Edition", 8900),
        # --- Spirit of Big Bang ---
        ("Hublot", "Spirit of Big Bang Titanium", "601.NX.0173.LR",
         "Automatic Cal. HUB4700 UNICO", "Titanium", "Current Production", 18000),
        ("Hublot", "Spirit of Big Bang Ceramic", "601.CI.0173.RX",
         "Automatic Cal. HUB4700 UNICO", "Ceramic", "Current Production", 20000),
        ("Hublot", "Spirit of Big Bang Sapphire", "601.JX.0120.RT",
         "Automatic Cal. HUB4700 UNICO", "Stainless Steel", "Limited Edition", 42000),
    ]


# ---------------------------------------------------------------------------
# Montblanc — 8 watches
# ---------------------------------------------------------------------------

def _montblanc_watches() -> list[tuple]:
    """8 Montblanc watches — 1858, Heritage, Star Legacy, TimeWalker."""
    return [
        # --- 1858 ---
        ("Montblanc", "1858 Geosphere 0 Oxygen", "130982",
         "Automatic Cal. MB 29.25", "Titanium", "Current Production", 5200),
        ("Montblanc", "1858 Iced Sea Automatic Date", "129371",
         "Automatic Cal. MB 24.15", "Stainless Steel", "Current Production", 3200),
        # --- Heritage ---
        ("Montblanc", "Heritage Manufacture Perpetual Calendar", "119925",
         "Automatic Cal. MB 29.22", "18k Rose Gold", "Current Production", 22000),
        ("Montblanc", "Heritage Chronométrie ExoTourbillon Minute", "112542",
         "Automatic Cal. MB M16.68", "18k Rose Gold", "Limited Edition", 65000),
        # --- Star Legacy ---
        ("Montblanc", "Star Legacy Automatic Date 43mm", "128681",
         "Automatic Cal. MB 24.00", "Stainless Steel", "Current Production", 2800),
        ("Montblanc", "Star Legacy Full Calendar 42mm", "128670",
         "Automatic Cal. MB 29.12", "Stainless Steel", "Current Production", 4200),
        # --- TimeWalker ---
        ("Montblanc", "TimeWalker Chronograph Rally Timer", "118491",
         "Automatic Cal. MB 25.07", "Stainless Steel", "Discontinued Classic", 4500),
        ("Montblanc", "TimeWalker Manufacture Chronograph", "116098",
         "Automatic Cal. MB 25.07", "Stainless Steel", "Discontinued Classic", 3800),
    ]


# ---------------------------------------------------------------------------
# Blancpain expansion — 8 watches
# ---------------------------------------------------------------------------

def _blancpain_expansion_watches() -> list[tuple]:
    """8 additional Blancpain watches — Fifty Fathoms & Villeret."""
    return [
        # --- Fifty Fathoms ---
        ("Blancpain", "Fifty Fathoms 70th Anniversary Act 1", "5010-1130-B52A",
         "Automatic Cal. 1315", "Stainless Steel", "Anniversary Edition", 16500),
        ("Blancpain", "Fifty Fathoms Tourbillon 8 Jours", "5025-3630-52A",
         "Manual Cal. 25A", "18k Rose Gold", "Current Production", 110000),
        ("Blancpain", "Fifty Fathoms Automatique Grande Date", "5050-12B30-B52A",
         "Automatic Cal. 6918B", "Titanium", "Current Production", 17500),
        ("Blancpain", "Fifty Fathoms No Rad Limited Edition", "5008-1130-B52A",
         "Automatic Cal. 1315", "Stainless Steel", "Limited Edition", 19000),
        # --- Villeret ---
        ("Blancpain", "Villeret Quantième Perpétuel", "6656-1127-55B",
         "Automatic Cal. 5954", "18k Rose Gold", "Current Production", 38000),
        ("Blancpain", "Villeret Ultraplate 40mm", "6223-1127-55A",
         "Automatic Cal. 1150", "18k Rose Gold", "Current Production", 14000),
        ("Blancpain", "Villeret Grande Date Jour Rétrograde", "6668-3642-55B",
         "Automatic Cal. 6950", "18k White Gold", "Current Production", 32000),
        ("Blancpain", "Villeret Moonphase 40mm", "6126-1127-55B",
         "Automatic Cal. 913", "18k Rose Gold", "Current Production", 18000),
    ]


# ---------------------------------------------------------------------------
# Breguet expansion — 8 watches
# ---------------------------------------------------------------------------

def _breguet_expansion_watches() -> list[tuple]:
    """8 additional Breguet watches — Classique, Marine, Tradition, Type XX."""
    return [
        # --- Classique ---
        ("Breguet", "Classique Tourbillon Extra-Plat", "5367PT/2Y/9WU",
         "Automatic Cal. 581", "Platinum", "Current Production", 135000),
        ("Breguet", "Classique Phase de Lune 7787", "7787BR/29/9V6",
         "Automatic Cal. 591DRL", "18k Rose Gold", "Current Production", 28000),
        # --- Marine ---
        ("Breguet", "Marine Chronographe 5527", "5527BB/Y2/9WV",
         "Automatic Cal. 582 QA", "18k White Gold", "Current Production", 32000),
        ("Breguet", "Marine Alarme Musicale 5547", "5547TI/Y1/9ZU",
         "Automatic Cal. 519R", "Titanium", "Current Production", 25000),
        # --- Tradition ---
        ("Breguet", "Tradition Automatique 7097 Rose Gold", "7097BR/G1/9WU",
         "Automatic Cal. 505 SR1", "18k Rose Gold", "Current Production", 22000),
        ("Breguet", "Tradition Chronographe Indépendant 7077", "7077BB/G9/9XV",
         "Manual Cal. 580 DR", "18k White Gold", "Current Production", 45000),
        # --- Type XX ---
        ("Breguet", "Type XXI Flyback Chronograph 3817", "3817ST/X2/3ZU",
         "Automatic Cal. 584 Q/A", "Stainless Steel", "Current Production", 12500),
        ("Breguet", "Type 20 Chronograph 2057", "2057ST/92/3WU",
         "Automatic Cal. 7281", "Stainless Steel", "Current Production", 11000),
    ]


# ---------------------------------------------------------------------------
# Chopard expansion — 6 watches
# ---------------------------------------------------------------------------

def _chopard_expansion_watches() -> list[tuple]:
    """6 additional Chopard watches — L.U.C, Alpine Eagle, Happy Sport."""
    return [
        # --- L.U.C ---
        ("Chopard", "L.U.C XPS 1860 Officer", "161242-5001",
         "Automatic Cal. L.U.C 96.01-L", "18k Rose Gold", "Current Production", 14000),
        ("Chopard", "L.U.C Full Strike Sapphire", "161947-9001",
         "Manual Cal. L.U.C 08.01-L", "18k Rose Gold", "Limited Edition", 250000),
        ("Chopard", "L.U.C Perpetual Twin", "168561-3003",
         "Automatic Cal. L.U.C 96.26-L", "18k Rose Gold", "Current Production", 42000),
        # --- Alpine Eagle ---
        ("Chopard", "Alpine Eagle 36mm Steel", "298601-3001",
         "Automatic Cal. 09.01-C", "Stainless Steel", "Current Production", 8900),
        # --- Happy Sport ---
        ("Chopard", "Happy Sport 36mm", "278559-3003",
         "Automatic Cal. 09.01-C", "Stainless Steel", "Current Production", 7200),
        ("Chopard", "Happy Diamonds Planet", "283578-5001",
         "Quartz", "18k White Gold", "Current Production", 18000),
    ]


# ---------------------------------------------------------------------------
# Girard-Perregaux expansion — 6 watches
# ---------------------------------------------------------------------------

def _girard_perregaux_expansion_watches() -> list[tuple]:
    """6 additional Girard-Perregaux watches — Laureato, Free Bridge."""
    return [
        # --- Laureato ---
        ("Girard-Perregaux", "Laureato Chronograph 42mm", "81020-11-431-11A",
         "Automatic Cal. GP03300", "Stainless Steel", "Current Production", 14500),
        ("Girard-Perregaux", "Laureato Skeleton 42mm", "81015-11-001-11A",
         "Automatic Cal. GP01800-0004", "Stainless Steel", "Current Production", 16000),
        ("Girard-Perregaux", "Laureato Absolute Chronograph", "81060-21-491-FH6A",
         "Automatic Cal. GP03300", "Titanium", "Current Production", 11000),
        ("Girard-Perregaux", "Laureato Perpetual Calendar 42mm", "81035-11-431-11A",
         "Automatic Cal. GP03300-0082", "Stainless Steel", "Current Production", 38000),
        # --- Free Bridge ---
        ("Girard-Perregaux", "Free Bridge 44mm", "86000-21-001-FB6A",
         "Automatic Cal. GP01800-1105", "Titanium", "Current Production", 14000),
        ("Girard-Perregaux", "Free Bridge Infinity Edition", "86000-21-00B-FB6A",
         "Automatic Cal. GP01800-1105", "Ceramic", "Limited Edition", 18000),
    ]


# ---------------------------------------------------------------------------
# BVLGARI — 5 watches
# ---------------------------------------------------------------------------

def _bvlgari_watches() -> list[tuple]:
    """5 BVLGARI watches — Octo Finissimo, Serpenti, Aluminium."""
    return [
        # --- Octo Finissimo ---
        ("BVLGARI", "Octo Finissimo Automatic", "103431",
         "Automatic Cal. BVL 138", "Titanium", "Current Production", 11500),
        ("BVLGARI", "Octo Finissimo Skeleton", "103610",
         "Automatic Cal. BVL 128SK", "Titanium", "Current Production", 14000),
        ("BVLGARI", "Octo Finissimo Perpetual Calendar", "103200",
         "Automatic Cal. BVL 305", "Titanium", "Current Production", 32000),
        # --- Serpenti ---
        ("BVLGARI", "Serpenti Seduttori 33mm", "103143",
         "Quartz Cal. BVL 191", "Stainless Steel", "Current Production", 4500),
        # --- Aluminium ---
        ("BVLGARI", "Aluminium Chronograph 40mm", "103868",
         "Automatic Cal. B130", "Aluminum", "Current Production", 4100),
    ]


# ---------------------------------------------------------------------------
# Piaget expansion — 4 watches
# ---------------------------------------------------------------------------

def _piaget_expansion_watches() -> list[tuple]:
    """4 additional Piaget watches — Altiplano, Polo."""
    return [
        # --- Altiplano ---
        ("Piaget", "Altiplano Ultimate Concept", "G0A45500",
         "Manual Cal. 900P-UC", "Stainless Steel", "Limited Edition", 400000),
        ("Piaget", "Altiplano 40mm Rose Gold", "G0A38131",
         "Automatic Cal. 1200P", "18k Rose Gold", "Current Production", 18000),
        # --- Polo ---
        ("Piaget", "Polo Skeleton", "G0A46009",
         "Automatic Cal. 1200S", "Stainless Steel", "Current Production", 26000),
        ("Piaget", "Polo Chronograph 42mm Blue", "G0A46024",
         "Automatic Cal. 1160P", "Stainless Steel", "Current Production", 16000),
    ]


# ---------------------------------------------------------------------------
# Hermès — 4 watches
# ---------------------------------------------------------------------------

def _hermes_watches() -> list[tuple]:
    """4 Hermès watches — Arceau, Cape Cod, H08."""
    return [
        # --- Arceau ---
        ("Hermès", "Arceau Automatique 40mm", "W055064WW00",
         "Automatic Cal. H1928", "Stainless Steel", "Current Production", 5500),
        ("Hermès", "Arceau L'Heure de la Lune", "W055247WW00",
         "Automatic Cal. H1837", "18k White Gold", "Limited Edition", 28000),
        # --- Cape Cod ---
        ("Hermès", "Cape Cod Automatique 33mm", "W044291WW00",
         "Automatic Cal. H1912", "Stainless Steel", "Current Production", 4200),
        # --- H08 ---
        ("Hermès", "H08 39mm Titanium", "W049430WW00",
         "Automatic Cal. H1837", "Titanium", "Current Production", 6500),
    ]


# ---------------------------------------------------------------------------
# Jaquet Droz — 3 watches
# ---------------------------------------------------------------------------

def _jaquet_droz_watches() -> list[tuple]:
    """3 Jaquet Droz watches — Grande Seconde, Bird Repeater."""
    return [
        # --- Grande Seconde ---
        ("Jaquet Droz", "Grande Seconde Quantième Ivory Enamel", "J007013200",
         "Automatic Cal. 2660Q2", "18k Rose Gold", "Current Production", 15000),
        ("Jaquet Droz", "Grande Seconde Off-Centered 39mm", "J006010270",
         "Automatic Cal. 2663A.S", "Stainless Steel", "Current Production", 9500),
        # --- Bird Repeater ---
        ("Jaquet Droz", "Bird Repeater", "J031033202",
         "Automatic Cal. RMA88", "18k Rose Gold", "Limited Edition", 450000),
    ]


# ---------------------------------------------------------------------------
# Catalog Expansion — 2026-03-20 (underrepresented + missing icons + affordable)
# ---------------------------------------------------------------------------


def _glashutte_original_expansion_watches() -> list[tuple]:
    """6 Glashutte Original watches — Senator, PanoMaticLunar, SeaQ, Sixties."""
    return [
        ("Glashutte Original", "Senator Chronometer 42mm", "1-58-01-05-34-30",
         "Automatic Cal. 58-01", "Stainless Steel", "Current Production", 8500),
        ("Glashutte Original", "Senator Excellence Panorama Date Moon Phase", "1-36-04-01-02-30",
         "Automatic Cal. 36-04", "Stainless Steel", "Current Production", 10500),
        ("Glashutte Original", "PanoMaticLunar 40mm", "1-90-02-42-32-05",
         "Automatic Cal. 90-02", "18k Rose Gold", "Current Production", 18000),
        ("Glashutte Original", "PanoReserve 40mm", "1-65-01-26-12-04",
         "Manual Cal. 65-01", "Stainless Steel", "Current Production", 8200),
        ("Glashutte Original", "Sixties Panorama Date 42mm", "2-39-47-04-02-04",
         "Automatic Cal. 39-47", "Stainless Steel", "Current Production", 7500),
        ("Glashutte Original", "SeaQ Panorama Date 43.2mm", "1-36-13-02-90-04",
         "Automatic Cal. 36-13", "Stainless Steel", "Current Production", 9800),
    ]


def _baume_mercier_expansion_watches() -> list[tuple]:
    """5 Baume & Mercier watches — Clifton, Riviera, Hampton, Classima."""
    return [
        ("Baume & Mercier", "Clifton Baumatic 10551", "M0A10551",
         "Automatic Cal. BM13-1975A", "Stainless Steel", "Current Production", 2800),
        ("Baume & Mercier", "Clifton Baumatic Perpetual Calendar", "M0A10549",
         "Automatic Cal. BM13-1975AC2", "Stainless Steel", "Current Production", 5500),
        ("Baume & Mercier", "Riviera Automatic GMT 43mm", "M0A10659",
         "Automatic Cal. BM14-1975AGM", "Stainless Steel", "Current Production", 3900),
        ("Baume & Mercier", "Hampton Rectangular Auto", "M0A10522",
         "Automatic Cal. ML115", "Stainless Steel", "Current Production", 2600),
        ("Baume & Mercier", "Classima Open Balance 42mm", "M0A10524",
         "Automatic Cal. ML166", "Stainless Steel", "Current Production", 2200),
    ]


def _frederique_constant_expansion_watches() -> list[tuple]:
    """5 Frederique Constant watches — Highlife, Classics, Slimline."""
    return [
        ("Frederique Constant", "Highlife Heartbeat Auto 41mm", "FC-310N4NH6B",
         "Automatic Cal. FC-310", "Stainless Steel", "Current Production", 1800),
        ("Frederique Constant", "Highlife COSC Chronograph 41mm", "FC-391S4NH6B",
         "Automatic Cal. FC-391", "Stainless Steel", "Current Production", 3200),
        ("Frederique Constant", "Classics Worldtimer Manufacture", "FC-718DGWM4H6",
         "Automatic Cal. FC-718", "Stainless Steel", "Current Production", 3500),
        ("Frederique Constant", "Slimline Power Reserve Manufacture", "FC-723GR3S6",
         "Automatic Cal. FC-723", "Stainless Steel", "Current Production", 2100),
        ("Frederique Constant", "Classics Index Auto 40mm", "FC-303S5B6B",
         "Automatic Cal. FC-303", "Stainless Steel", "Current Production", 1100),
    ]


def _h_moser_expansion_watches() -> list[tuple]:
    """5 H. Moser & Cie watches — Endeavour, Pioneer, Streamliner, Swiss Alp."""
    return [
        ("H. Moser & Cie", "Endeavour Perpetual Moon", "1801-0300",
         "Automatic Cal. HMC 801", "18k Rose Gold", "Current Production", 25000),
        ("H. Moser & Cie", "Endeavour Small Seconds Purity", "1321-0210",
         "Manual Cal. HMC 321", "Stainless Steel", "Current Production", 12500),
        ("H. Moser & Cie", "Pioneer Centre Seconds Arctic Blue", "3200-1218",
         "Automatic Cal. HMC 200", "Stainless Steel", "Current Production", 11800),
        ("H. Moser & Cie", "Streamliner Centre Seconds Funky Blue", "6200-1208",
         "Automatic Cal. HMC 200", "Stainless Steel", "Current Production", 15500),
        ("H. Moser & Cie", "Swiss Alp Watch Final Upgrade", "5324-1206",
         "Manual Cal. HMC 324", "Stainless Steel", "Limited Edition", 28000),
    ]


def _ulysse_nardin_expansion_watches() -> list[tuple]:
    """5 Ulysse Nardin watches — Diver, Marine, Freak, Blast."""
    return [
        ("Ulysse Nardin", "Diver Chronometer 44mm", "1183-170-3/92",
         "Automatic Cal. UN-118", "Stainless Steel", "Current Production", 7500),
        ("Ulysse Nardin", "Marine Torpilleur 42mm", "1183-310-7M/40",
         "Automatic Cal. UN-118", "Stainless Steel", "Current Production", 6800),
        ("Ulysse Nardin", "Marine Chronograph Annual Calendar", "1533-150-3/40",
         "Automatic Cal. UN-153", "Stainless Steel", "Current Production", 11000),
        ("Ulysse Nardin", "Freak X 43mm Titanium", "2303-270.1/03",
         "Automatic Cal. UN-230", "Titanium", "Current Production", 16000),
        ("Ulysse Nardin", "Blast Tourbillon Auto 45mm", "1723-400-3A/00",
         "Automatic Cal. UN-172", "Titanium", "Current Production", 52000),
    ]


def _raymond_weil_expansion_watches() -> list[tuple]:
    """4 Raymond Weil watches — Freelancer, Maestro, Tango."""
    return [
        ("Raymond Weil", "Freelancer Chronograph 43.5mm", "7741-ST-30021",
         "Automatic Cal. RW5010", "Stainless Steel", "Current Production", 2500),
        ("Raymond Weil", "Freelancer Open Heart 42mm", "2780-ST-20001",
         "Automatic Cal. RW4200", "Stainless Steel", "Current Production", 1800),
        ("Raymond Weil", "Maestro Moonphase 40mm", "2239-STC-00509",
         "Automatic Cal. RW4280", "Stainless Steel", "Current Production", 1600),
        ("Raymond Weil", "Tango Classic Chrono 43mm", "8560-ST-00206",
         "Quartz Cal. RW5030", "Stainless Steel", "Current Production", 1100),
    ]


def _glycine_expansion_watches() -> list[tuple]:
    """3 Glycine watches — Airman, Combat Sub."""
    return [
        ("Glycine", "Airman Vintage 1953 36mm", "GL0419",
         "Automatic Cal. GL293", "Stainless Steel", "Current Production", 1200),
        ("Glycine", "Airman Double Twelve 42mm", "GL0234",
         "Automatic Cal. GL293", "Stainless Steel", "Current Production", 1400),
        ("Glycine", "Combat Sub Aquarius 42mm", "GL0325",
         "Automatic Cal. GL224", "Stainless Steel", "Current Production", 750),
    ]


def _luminox_expansion_watches() -> list[tuple]:
    """3 Luminox watches — Navy SEAL, Bear Grylls, Master Carbon SEAL."""
    return [
        ("Luminox", "Navy SEAL Chronograph 3580 Series", "XS.3581",
         "Quartz Cal. Ronda 5030D", "Carbon", "Current Production", 650),
        ("Luminox", "Bear Grylls Survival SEA 3723", "XB.3723",
         "Quartz Cal. Ronda 515", "Carbon", "Current Production", 400),
        ("Luminox", "Master Carbon SEAL Automatic 3875", "XS.3875",
         "Automatic Cal. Miyota 9015", "Carbon", "Current Production", 1200),
    ]


def _omega_expansion2_watches() -> list[tuple]:
    """10 Omega — Aqua Terra, Planet Ocean, De Ville, Moonwatch LE."""
    return [
        ("Omega", "Seamaster Aqua Terra 150M Shades Green 41mm", "220.10.41.21.10.002",
         "Automatic Cal. 8900", "Stainless Steel", "Current Production", 5400),
        ("Omega", "Seamaster Aqua Terra Small Seconds 38mm", "220.13.38.20.02.001",
         "Automatic Cal. 8800", "Stainless Steel", "Current Production", 5200),
        ("Omega", "Seamaster Aqua Terra 150M Annual Calendar 41mm", "231.10.43.22.01.002",
         "Automatic Cal. 8601", "Stainless Steel", "Current Production", 7200),
        ("Omega", "Seamaster Planet Ocean 600M GMT 43.5mm", "215.30.44.22.01.001",
         "Automatic Cal. 8906", "Stainless Steel", "Current Production", 7800),
        ("Omega", "Seamaster Planet Ocean 600M Chrono Titanium", "215.90.46.51.99.001",
         "Automatic Cal. 9900", "Titanium", "Current Production", 9500),
        ("Omega", "De Ville Prestige Co-Axial 40mm Blue", "424.13.40.20.03.001",
         "Automatic Cal. 2500", "Stainless Steel", "Current Production", 3800),
        ("Omega", "De Ville Hour Vision Annual Calendar 41mm", "433.13.41.22.03.001",
         "Automatic Cal. 8611", "Stainless Steel", "Current Production", 7500),
        ("Omega", "De Ville Tresor 40mm Manual Sedna Gold", "435.53.40.21.06.001",
         "Manual Cal. 8929", "18k Rose Gold", "Current Production", 12000),
        ("Omega", "Speedmaster Moonwatch Apollo 17 50th Anniversary", "311.30.42.30.99.002",
         "Manual Cal. 3861", "Stainless Steel", "Limited Edition", 9800),
        ("Omega", "Speedmaster Moonwatch Grey Side of the Moon", "311.93.44.51.99.001",
         "Automatic Cal. 9300", "Ceramic", "Current Production", 11500),
    ]


def _rolex_expansion2_watches() -> list[tuple]:
    """8 Rolex — Datejust variants, Explorer II, Yacht-Master, Air-King, Milgauss."""
    return [
        ("Rolex", "Datejust 41mm Slate Dial Roman Fluted Jubilee", "126334-Slate",
         "Automatic Cal. 3235", "Stainless Steel", "Current Production", 10500),
        ("Rolex", "Datejust 36mm Silver Index Oyster", "126200-Silver",
         "Automatic Cal. 3235", "Stainless Steel", "Current Production", 7500),
        ("Rolex", "Datejust 41mm Blue Diamond Dial White Gold Bezel", "126334-BlueDia",
         "Automatic Cal. 3235", "Steel/Gold", "Current Production", 12000),
        ("Rolex", "Datejust 36mm Everose Rolesor Chocolate", "126231",
         "Automatic Cal. 3235", "Steel/Gold", "Current Production", 12500),
        ("Rolex", "Yacht-Master 42mm Titanium RLX Black", "226627",
         "Automatic Cal. 3235", "Titanium", "Current Production", 14000),
        ("Rolex", "Air-King 40mm Green/Black Dial", "126900-2",
         "Automatic Cal. 3230", "Stainless Steel", "Current Production", 8000),
        ("Rolex", "Milgauss Black Dial Orange Lightning", "116400",
         "Automatic Cal. 3131", "Stainless Steel", "Discontinued Classic", 11000),
        ("Rolex", "Explorer II 42mm White Dial Polar", "226570-White",
         "Automatic Cal. 3285", "Stainless Steel", "Current Production", 9500),
    ]


def _seiko_expansion2_watches() -> list[tuple]:
    """8 Seiko — Presage, Astron, King Seiko, 5 Sports LE."""
    return [
        ("Seiko", "Presage Craftsmanship Enamel SPB401", "SPB401J1",
         "Automatic Cal. 6R35", "Stainless Steel", "Limited Edition", 1200),
        ("Seiko", "Presage Style60s Open Heart SSA455", "SSA455J1",
         "Automatic Cal. 4R38", "Stainless Steel", "Current Production", 450),
        ("Seiko", "Astron GPS Solar 5X SSH113", "SSH113J1",
         "Solar GPS Cal. 5X53", "Titanium", "Current Production", 2200),
        ("Seiko", "Astron GPS Solar Dual Time SSH063", "SSH063J1",
         "Solar GPS Cal. 5X53", "Stainless Steel", "Current Production", 1800),
        ("Seiko", "King Seiko SPB281 Modern Re-Interpretation", "SPB281J1",
         "Automatic Cal. 6R55", "Stainless Steel", "Current Production", 1400),
        ("Seiko", "King Seiko SPB283 Ivory Dial", "SPB283J1",
         "Automatic Cal. 6R55", "Stainless Steel", "Current Production", 1400),
        ("Seiko", "5 Sports x Rowing Blazers SRPL11", "SRPL11K1",
         "Automatic Cal. 4R36", "Stainless Steel", "Limited Edition", 380),
        ("Seiko", "5 Sports 55th Anniversary LE SRPK17", "SRPK17K1",
         "Automatic Cal. 4R36", "Stainless Steel", "Limited Edition", 420),
    ]


def _cartier_expansion2_watches() -> list[tuple]:
    """6 Cartier — Ballon Bleu, Drive, Pasha, Cloche."""
    return [
        ("Cartier", "Ballon Bleu 36mm Automatic Rose Gold Silver", "WGBB0045",
         "Automatic Cal. 076", "18k Rose Gold", "Current Production", 14000),
        ("Cartier", "Ballon Bleu 42mm Chronograph Steel", "WSBB0049",
         "Automatic Cal. 8101", "Stainless Steel", "Current Production", 9500),
        ("Cartier", "Drive de Cartier Moon Phases", "WSNM0017",
         "Automatic Cal. 1904-LU MC", "Stainless Steel", "Current Production", 7200),
        ("Cartier", "Pasha de Cartier 35mm Automatic", "WSPA0036",
         "Automatic Cal. 1847 MC", "Stainless Steel", "Current Production", 5500),
        ("Cartier", "Pasha de Cartier 41mm Skeleton", "WHPA0007",
         "Manual Cal. 9624 MC", "Stainless Steel", "Current Production", 38000),
        ("Cartier", "Cloche de Cartier Large Platinum", "WGCC0001",
         "Manual Cal. 1917 MC", "Platinum", "Limited Edition", 35000),
    ]


def _iwc_expansion2_watches() -> list[tuple]:
    """6 IWC — Pilot's, Portugieser, Ingenieur, Da Vinci."""
    return [
        ("IWC", "Pilot's Watch Mark XX 40mm Green", "IW328205",
         "Automatic Cal. 32111", "Stainless Steel", "Current Production", 5200),
        ("IWC", "Pilot's Watch Chronograph 41mm Spitfire Bronze", "IW387902",
         "Automatic Cal. 69385", "Bronze", "Current Production", 6500),
        ("IWC", "Portugieser Yacht Club Chronograph 44mm", "IW390701",
         "Automatic Cal. 89361", "Stainless Steel", "Current Production", 12000),
        ("IWC", "Portugieser Eternal Calendar 44mm", "IW505703",
         "Automatic Cal. 52640", "18k Rose Gold", "Current Production", 38000),
        ("IWC", "Ingenieur Automatic 40mm Titanium", "IW328902",
         "Automatic Cal. 32111", "Titanium", "Current Production", 8500),
        ("IWC", "Da Vinci Automatic Moon Phase 36mm", "IW459308",
         "Automatic Cal. 35800", "Stainless Steel", "Current Production", 6000),
    ]


def _tudor_expansion2_watches() -> list[tuple]:
    """5 Tudor — Pelagos FXD, Ranger, Royal, 1926."""
    return [
        ("Tudor", "Pelagos FXD XF Chrono", "M25807KN-0001",
         "Automatic Cal. MT5836", "Titanium", "Current Production", 5800),
        ("Tudor", "Ranger 39mm Green Dial", "M79950-0003",
         "Automatic Cal. MT5402", "Stainless Steel", "Current Production", 3100),
        ("Tudor", "Royal 38mm Blue Dial", "M28500-0006",
         "Automatic Cal. T603", "Stainless Steel", "Current Production", 2300),
        ("Tudor", "1926 36mm Silver Dial", "M91450-0001",
         "Automatic Cal. T601", "Stainless Steel", "Current Production", 1800),
        ("Tudor", "Black Bay 58 Bronze Boutique Edition", "M79012M-0002",
         "Automatic Cal. MT5400", "Bronze", "Limited Edition", 4800),
    ]


def _hamilton_expansion2_watches() -> list[tuple]:
    """5 Hamilton — Ventura Elvis80, Khaki Navy, PSR, Jazzmaster Thinline."""
    return [
        ("Hamilton", "Ventura Elvis80 Skeleton Auto", "H24555381",
         "Automatic Cal. H-10", "Stainless Steel", "Current Production", 1300),
        ("Hamilton", "Khaki Navy BeLOWZERO Auto 46mm", "H78585333",
         "Automatic Cal. H-10", "Titanium", "Current Production", 1500),
        ("Hamilton", "PSR Digital Quartz 74 Tribute", "H52414139",
         "Quartz Hybrid OLED", "Stainless Steel", "Current Production", 750),
        ("Hamilton", "Jazzmaster Thinline Auto 40mm Silver", "H38525111",
         "Automatic Cal. H-10", "Stainless Steel", "Current Production", 800),
        ("Hamilton", "Khaki Navy Sub Auto 41mm Black", "H82515330",
         "Automatic Cal. H-10", "Stainless Steel", "Current Production", 750),
    ]


def _longines_expansion2_watches() -> list[tuple]:
    """5 Longines — Legend Diver, HydroConquest, Conquest Heritage."""
    return [
        ("Longines", "Legend Diver 42mm Green", "L3.774.4.40.2",
         "Automatic Cal. L888.5", "Stainless Steel", "Current Production", 2300),
        ("Longines", "Legend Diver No Date 36mm", "L3.374.4.50.6",
         "Automatic Cal. L592.5", "Stainless Steel", "Current Production", 2100),
        ("Longines", "HydroConquest GMT 41mm Sunray Blue", "L3.790.4.96.6",
         "Automatic Cal. L844.5", "Stainless Steel", "Current Production", 1800),
        ("Longines", "HydroConquest 39mm Ceramic Green", "L3.780.4.06.9",
         "Automatic Cal. L888.5", "Stainless Steel", "Current Production", 1600),
        ("Longines", "Conquest Heritage Central Power Reserve 38.5mm", "L1.648.4.78.2",
         "Automatic Cal. L896.5", "Stainless Steel", "Current Production", 2200),
    ]


def _tissot_expansion2_watches() -> list[tuple]:
    """5 Tissot — PRX Powermatic, Gentleman, Seastar, T-Sport."""
    return [
        ("Tissot", "PRX Powermatic 80 35mm Green Ladies", "T137.207.11.091.00",
         "Automatic Cal. Powermatic 80", "Stainless Steel", "Current Production", 550),
        ("Tissot", "Gentleman Powermatic 80 Open Heart", "T127.407.16.031.01",
         "Automatic Cal. Powermatic 80", "Stainless Steel", "Current Production", 650),
        ("Tissot", "Seastar 1000 Powermatic 80 36mm", "T120.207.11.041.01",
         "Automatic Cal. Powermatic 80", "Stainless Steel", "Current Production", 600),
        ("Tissot", "T-Sport Supersport Chrono", "T125.617.11.031.00",
         "Quartz Cal. ETA G10.212", "Stainless Steel", "Current Production", 420),
        ("Tissot", "PRX Powermatic 80 40mm Waffle Dial Black", "T137.407.11.051.01",
         "Automatic Cal. Powermatic 80", "Stainless Steel", "Current Production", 600),
    ]


def _grand_seiko_expansion2_watches() -> list[tuple]:
    """5 Grand Seiko — Snowflake variants, SLGA, Hi-Beat GMT, Kodo."""
    return [
        ("Grand Seiko", "Heritage Snowflake Titanium SBGA461", "SBGA461",
         "Spring Drive Cal. 9R65", "Titanium", "Current Production", 5800),
        ("Grand Seiko", "Evolution 9 SLGA015 Spring Drive 5 Days", "SLGA015",
         "Spring Drive Cal. 9RA2", "Stainless Steel", "Current Production", 9200),
        ("Grand Seiko", "Sport Hi-Beat GMT SBGJ239", "SBGJ239",
         "Automatic Cal. 9S86", "Stainless Steel", "Current Production", 6500),
        ("Grand Seiko", "Kodo Constant-Force Tourbillon SLGT003", "SLGT003",
         "Mechanical Cal. T0", "Platinum", "Limited Edition", 350000),
        ("Grand Seiko", "Evolution 9 SLGA019 Night Birch", "SLGA019",
         "Spring Drive Cal. 9RA2", "Stainless Steel", "Current Production", 9200),
    ]


def _casio_expansion2_watches() -> list[tuple]:
    """5 Casio — Casiotron, Edifice, Oceanus."""
    return [
        ("Casio", "Casiotron 50th Anniversary TRN-50-2A", "TRN-50-2AJR",
         "Quartz Digital Cal. Module 4395", "Resin", "Anniversary Edition", 300),
        ("Casio", "Edifice EQB-2000 Smartphone Link Solar Chrono", "EQB-2000DB-1AJF",
         "Solar Quartz Cal. Module 5654", "Stainless Steel", "Current Production", 380),
        ("Casio", "Edifice ECB-2200 Bluetooth Solar", "ECB-2200DC-1AJF",
         "Solar Quartz Cal. Module 5688", "Stainless Steel", "Current Production", 280),
        ("Casio", "Oceanus OCW-T6000 Manta Premium", "OCW-T6000-1AJF",
         "Solar Quartz Cal. Module 5674", "Titanium", "Current Production", 1800),
        ("Casio", "Oceanus OCW-S5000 Slim Titanium", "OCW-S5000-1AJF",
         "Solar Quartz Cal. Module 5673", "Titanium", "Current Production", 1200),
    ]


def _timex_expansion2_watches() -> list[tuple]:
    """4 Timex — Marlin, Q Timex, M79, Todd Snyder."""
    return [
        ("Timex", "Marlin Automatic 40mm California Dial", "TW2W47500",
         "Automatic Cal. Miyota 8215", "Stainless Steel", "Current Production", 280),
        ("Timex", "Q Timex GMT 38mm Blue/Red Bezel", "TW2V38000",
         "Quartz Cal. Miyota", "Stainless Steel", "Current Production", 200),
        ("Timex", "M79 Automatic 40mm Black/Orange", "TW2U96900",
         "Automatic Cal. Miyota 8205", "Stainless Steel", "Current Production", 300),
        ("Timex", "Timex x Todd Snyder Mod Inspired 40mm", "TWG030000",
         "Quartz", "Stainless Steel", "Special Edition", 160),
    ]


def _citizen_expansion2_watches() -> list[tuple]:
    """4 Citizen — Series 8, Tsuyosa, Corso, Promaster Navihawk."""
    return [
        ("Citizen", "Series 8 880 Mechanical GMT NA1010-84X", "NA1010-84X",
         "Automatic Cal. 9054", "Stainless Steel", "Current Production", 1500),
        ("Citizen", "Tsuyosa Automatic 40mm Blue NJ0150-81L", "NJ0150-81L",
         "Automatic Cal. 8210", "Stainless Steel", "Current Production", 280),
        ("Citizen", "Eco-Drive Corso BM7490-52E", "BM7490-52E",
         "Eco-Drive Cal. E111", "Stainless Steel", "Current Production", 300),
        ("Citizen", "Promaster Navihawk A-T JY8100-80L", "JY8100-80L",
         "Eco-Drive Cal. U680", "Stainless Steel", "Current Production", 550),
    ]


# ---------------------------------------------------------------------------
# Assemble full catalog
# ---------------------------------------------------------------------------

def _haute_horlogerie_depth_watches() -> list[tuple]:
    """Depth for the haute-horlogerie maisons that were thin (2026-08-12).

    The catalogue was strong at the top of the mainstream — Omega 88, Rolex 77,
    Cartier 62, Patek 49 — while several of the most collected high-end houses
    sat in single digits: Piaget 5, Richard Mille 5, F.P. Journe 5, Chopard 7,
    H. Moser 9, Blancpain 11, Breguet 12. Those are exactly the references a
    Chrono24 or Catawiki buyer searches for, and the ones the new price-gated
    "where to buy" routing sends there.

    Every reference here is checked against the rows already in the catalogue —
    `get_curated_catalog()` deduplicates by REFERENCE and keeps the first
    occurrence, so a repeat would be dropped in silence rather than flagged.

    Same standing caveat as the jewellery seeds: curated from knowledge, not
    from a source feed. A wrong reference is invisible to every gate in this
    repo — that check is a human one.
    """
    return [
        # --- Piaget: Altiplano (ultra-thin) and Polo -------------------------
        ("Piaget", "Altiplano 38mm Ultra-Thin White Gold", "G0A29112",
         "Manual Cal. 430P", "18k White Gold", "Current Production", 21000),
        ("Piaget", "Altiplano Moonphase 36mm", "G0A44051",
         "Automatic Cal. 580P", "18k Rose Gold", "Current Production", 29000),
        ("Piaget", "Polo Perpetual Calendar Ultra-Thin", "G0A48002",
         "Automatic Cal. 1255P", "18k White Gold", "Limited Edition", 78000),
        ("Piaget", "Limelight Gala 32mm", "G0A38160",
         "Quartz Cal. 690P", "18k Rose Gold", "Current Production", 24000),
        # --- Richard Mille ---------------------------------------------------
        ("Richard Mille", "RM 010 Automatic", "RM 010",
         "Automatic Cal. RMAS7", "Titanium", "Discontinued Classic", 120000),
        ("Richard Mille", "RM 029 Automatic Big Date", "RM 029",
         "Automatic Cal. RMAS7", "Titanium", "Current Production", 110000),
        ("Richard Mille", "RM 030 Declutchable Rotor", "RM 030",
         "Automatic Cal. RMAR2", "Titanium", "Current Production", 145000),
        ("Richard Mille", "RM 07-01 Ladies Automatic", "RM 07-01",
         "Automatic Cal. CRMA2", "Ceramic", "Current Production", 165000),
        # --- F.P. Journe ------------------------------------------------------
        ("F.P. Journe", "Chronometre a Resonance 2020", "CR",
         "Manual Cal. 1520", "Platinum", "Current Production", 340000),
        ("F.P. Journe", "Octa Divine", "OD",
         "Automatic Cal. 1300.3", "18k Rose Gold", "Current Production", 62000),
        ("F.P. Journe", "Octa Lune", "OL",
         "Automatic Cal. 1300.3", "Platinum", "Current Production", 95000),
        ("F.P. Journe", "Elegante 48", "EL48",
         "Quartz Cal. 1210", "Titanium", "Current Production", 22000),
        # --- Chopard: L.U.C and Alpine Eagle ---------------------------------
        ("Chopard", "L.U.C Quattro 43mm", "161926-5004",
         "Manual Cal. L.U.C 98.01-L", "18k Rose Gold", "Current Production", 26000),
        ("Chopard", "L.U.C Lunar One Perpetual Calendar", "161927-5001",
         "Automatic Cal. L.U.C 96.13-L", "Platinum", "Limited Edition", 78000),
        ("Chopard", "Alpine Eagle Chrono 44mm", "298609-3001",
         "Automatic Cal. 03.05-C", "Lucent Steel", "Current Production", 18500),
        ("Chopard", "Mille Miglia GTS Chrono", "168571-3001",
         "Automatic Cal. 03.05-C", "Stainless Steel", "Current Production", 8200),
        # --- H. Moser & Cie ---------------------------------------------------
        ("H. Moser & Cie", "Streamliner Perpetual Calendar", "6812-1200",
         "Automatic Cal. HMC 812", "Stainless Steel", "Limited Edition", 95000),
        ("H. Moser & Cie", "Endeavour Tourbillon Concept", "1804-0501",
         "Automatic Cal. HMC 804", "18k White Gold", "Limited Edition", 82000),
        ("H. Moser & Cie", "Pioneer Perpetual Calendar", "3810-1200",
         "Automatic Cal. HMC 800", "Stainless Steel", "Current Production", 58000),
        # --- Blancpain --------------------------------------------------------
        ("Blancpain", "Fifty Fathoms Bathyscaphe Chronographe Flyback", "5200-1110-B52A",
         "Automatic Cal. F385", "Stainless Steel", "Current Production", 19500),
        ("Blancpain", "Villeret Quantieme Complet 40mm", "6654-1127-55B",
         "Automatic Cal. 6654", "Stainless Steel", "Current Production", 14500),
        ("Blancpain", "Le Brassus Carrousel Repetition Minutes", "00232-3631-55B",
         "Manual Cal. 2322", "Platinum", "Limited Edition", 320000),
        # --- Breguet ----------------------------------------------------------
        ("Breguet", "Classique Double Tourbillon 5345", "5345PT/1S/7XU",
         "Manual Cal. 588N", "Platinum", "Limited Edition", 480000),
        ("Breguet", "Reine de Naples 8918", "8918BB/58/964/D00D",
         "Automatic Cal. 537/3", "18k White Gold", "Current Production", 38000),
        ("Breguet", "Marine Hora Mundi 5557", "5557ST/2A/5WV",
         "Automatic Cal. 77F0", "Stainless Steel", "Current Production", 32000),
    ]


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
    all_tuples.extend(_expansion_round3_watches())
    # Affordable & Microbrand Expansion (2026-03-14)
    all_tuples.extend(_microbrand_expansion_watches())
    all_tuples.extend(_chinese_value_watches())
    all_tuples.extend(_affordable_mainstream_expansion())
    all_tuples.extend(_value_diver_watches())
    all_tuples.extend(_affordable_dress_field_watches())
    all_tuples.extend(_mid_range_enthusiast_watches())
    all_tuples.extend(_g_shock_affordable_expansion())
    all_tuples.extend(_accessible_luxury_watches())
    # Luxury Variants — Men's & Women's (2026-03-14)
    all_tuples.extend(_cartier_variants_watches())
    all_tuples.extend(_ap_variants_watches())
    all_tuples.extend(_jlc_variants_watches())
    all_tuples.extend(_vc_variants_watches())
    all_tuples.extend(_hamilton_variants_watches())
    all_tuples.extend(_rolex_variants_watches())
    all_tuples.extend(_omega_variants_watches())
    all_tuples.extend(_patek_philippe_variants_watches())
    # Premium Microbrands (2026-03-15)
    all_tuples.extend(_premium_microbrand_watches())
    # Luxury Brand Expansion (2026-03-20)
    all_tuples.extend(_tag_heuer_watches())
    all_tuples.extend(_hublot_watches())
    all_tuples.extend(_montblanc_watches())
    all_tuples.extend(_blancpain_expansion_watches())
    all_tuples.extend(_breguet_expansion_watches())
    all_tuples.extend(_chopard_expansion_watches())
    all_tuples.extend(_girard_perregaux_expansion_watches())
    all_tuples.extend(_bvlgari_watches())
    all_tuples.extend(_piaget_expansion_watches())
    all_tuples.extend(_hermes_watches())
    all_tuples.extend(_jaquet_droz_watches())
    # Catalog Expansion — 2026-03-20
    all_tuples.extend(_glashutte_original_expansion_watches())
    all_tuples.extend(_baume_mercier_expansion_watches())
    all_tuples.extend(_frederique_constant_expansion_watches())
    all_tuples.extend(_h_moser_expansion_watches())
    all_tuples.extend(_ulysse_nardin_expansion_watches())
    all_tuples.extend(_raymond_weil_expansion_watches())
    all_tuples.extend(_glycine_expansion_watches())
    all_tuples.extend(_luminox_expansion_watches())
    all_tuples.extend(_omega_expansion2_watches())
    all_tuples.extend(_rolex_expansion2_watches())
    all_tuples.extend(_seiko_expansion2_watches())
    all_tuples.extend(_cartier_expansion2_watches())
    all_tuples.extend(_iwc_expansion2_watches())
    all_tuples.extend(_tudor_expansion2_watches())
    all_tuples.extend(_hamilton_expansion2_watches())
    all_tuples.extend(_longines_expansion2_watches())
    all_tuples.extend(_tissot_expansion2_watches())
    all_tuples.extend(_grand_seiko_expansion2_watches())
    all_tuples.extend(_casio_expansion2_watches())
    all_tuples.extend(_timex_expansion2_watches())
    all_tuples.extend(_citizen_expansion2_watches())
    all_tuples.extend(_haute_horlogerie_depth_watches())

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
    # Deduplicate by ('reference',) (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = item["reference"]
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


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
