"""
Curated Fountain Pen Import Pipeline — Collectible Writing Instruments.

Imports a curated catalog of 1020+ collectible fountain pens across 18+ subcategories:
  Montblanc, Pelikan, Sailor, Pilot, Lamy, Visconti, Aurora, Nakaya,
  Vintage Classics, Japanese Artisan/Maki-e, Cartier, S.T. Dupont,
  Caran d'Ache, Graf von Faber-Castell, Platinum, Parker Modern,
  Conid/BENU/Opus 88 Independents, Esterbrook

Each entry has real model names, nib material, nib size, filling system,
limited edition status, and realistic EUR secondary market price.

Pattern follows import_keycaps.py / import_watches.py (get_curated_catalog,
item_to_catalog_item, item_to_price_observation).

Usage:
    python -m pipelines.import_pens [--dry-run]
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
    log_progress,
    slugify,
    rarity_score as shared_rarity_score,
    logger,
    close_http_client,
)

CATEGORY = "pens"

# ---------------------------------------------------------------------------
# Brand tier scoring for ML features
# ---------------------------------------------------------------------------
BRAND_TIER: dict[str, float] = {
    "Montblanc": 1.0,
    "Nakaya": 1.0,
    "Cartier": 0.9,
    "Pelikan": 0.9,
    "Sailor": 0.9,
    "Pilot": 0.8,
    "Namiki": 0.8,
    "Aurora": 0.8,
    "Visconti": 0.8,
    "Platinum": 0.8,
    "S.T. Dupont": 0.8,
    "Caran d'Ache": 0.8,
    "Graf von Faber-Castell": 0.8,
    "Lamy": 0.6,
    "Parker": 0.7,
    "Sheaffer": 0.7,
    "Waterman": 0.7,
    "Conklin": 0.6,
    "Conid": 0.8,
    "TWSBI": 0.5,
    "Opus 88": 0.5,
    "BENU": 0.5,
    "Scribo": 0.8,
    "Esterbrook": 0.6,
    "Kaweco": 0.5,
    "Faber-Castell": 0.6,
    "Cross": 0.7,
    "Noodler's": 0.4,
    "Eversharp": 0.7,
    "Swan": 0.6,
    "Conway Stewart": 0.7,
}

# ---------------------------------------------------------------------------
# Nib material scoring for ML features
# ---------------------------------------------------------------------------
NIB_MATERIAL_SCORES: dict[str, float] = {
    "18k Gold": 1.0,
    "14k Gold": 1.0,
    "21k Gold": 1.0,
    "Palladium": 1.0,
    "Ruthenium": 0.5,
    "Steel": 0.7,
    "14k Gold (Flex)": 1.0,
    "14k Gold (Soft)": 1.0,
}


def _brand_tier(brand: str) -> float:
    """Map brand to a tier score."""
    return BRAND_TIER.get(brand, 0.6)


def _nib_material_score(material: str) -> float:
    """Map nib material to a 0-1 score."""
    return NIB_MATERIAL_SCORES.get(material, 0.7)


# ---------------------------------------------------------------------------
# Curated catalog — 500+ fountain pens
# Each tuple: (name, brand, model_line, nib_material, nib_size,
#               filling_system, price_eur, is_limited, rarity, notes)
# ---------------------------------------------------------------------------


def _montblanc_pens() -> list[tuple]:
    """18 Montblanc fountain pens — Meisterstueck, Writers Edition, Heritage, LE."""
    return [
        ("Meisterstueck 149", "Montblanc", "Meisterstueck", "18k Gold", "M",
         "piston", 950, False, "Standard", "Flagship model, celluloid barrel"),
        ("Meisterstueck 146 Le Grand", "Montblanc", "Meisterstueck", "14k Gold", "F",
         "piston", 750, False, "Standard", "Mid-size classic, 14k nib"),
        ("Meisterstueck 145 Classique", "Montblanc", "Meisterstueck", "14k Gold", "M",
         "converter", 580, False, "Standard", "Slim profile, converter fill"),
        ("Writers Edition William Shakespeare", "Montblanc", "Writers Edition", "18k Gold", "M",
         "piston", 1200, True, "Limited Edition", "2016 LE, vermeil clip"),
        ("Writers Edition Antoine de Saint-Exupery", "Montblanc", "Writers Edition", "18k Gold", "F",
         "piston", 1400, True, "Limited Edition", "2017 LE, sand-colored lacquer"),
        ("Writers Edition Homage to Homer", "Montblanc", "Writers Edition", "18k Gold", "M",
         "piston", 1100, True, "Limited Edition", "2018 LE, dark blue lacquer"),
        ("Writers Edition Sir Arthur Conan Doyle", "Montblanc", "Writers Edition", "18k Gold", "B",
         "piston", 1300, True, "Limited Edition", "2021 LE, magnifying glass clip"),
        ("Writers Edition Brothers Grimm", "Montblanc", "Writers Edition", "18k Gold", "M",
         "piston", 1250, True, "Limited Edition", "2022 LE, forest green lacquer"),
        ("StarWalker Ultimate Carbon", "Montblanc", "StarWalker", "14k Gold", "M",
         "converter", 850, False, "Standard", "Carbon fiber barrel, modern design"),
        ("StarWalker Precious Resin", "Montblanc", "StarWalker", "14k Gold", "F",
         "converter", 650, False, "Standard", "Black resin, floating MB emblem"),
        ("Heritage Rouge et Noir", "Montblanc", "Heritage", "14k Gold", "M",
         "piston", 900, False, "Standard", "Art Deco-inspired, coral accent"),
        ("Heritage 1912 Capless", "Montblanc", "Heritage", "18k Gold", "M",
         "piston", 1050, True, "Limited Edition", "Retractable safety pen tribute"),
        ("Meisterstueck 149 Calligraphy", "Montblanc", "Meisterstueck", "18k Gold", "Stub",
         "piston", 1100, True, "Limited Edition", "Flex calligraphy nib"),
        ("Patron of Art Homage to Hadrian 4810", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 2800, True, "Limited Edition", "4810-piece LE, Roman motifs"),
        ("Great Characters Miles Davis", "Montblanc", "Great Characters", "18k Gold", "M",
         "piston", 1500, True, "Limited Edition", "Special edition, trumpet-inspired clip"),
        ("Meisterstueck 149 90th Anniversary", "Montblanc", "Meisterstueck", "18k Gold", "M",
         "piston", 1800, True, "Limited Edition", "Rose gold trim, burgundy lacquer"),
        ("Writers Edition Leo Tolstoy", "Montblanc", "Writers Edition", "18k Gold", "M",
         "piston", 1350, True, "Limited Edition", "2015 LE, faceted barrel, octagonal cap"),
        ("Meisterstueck Ultra Black", "Montblanc", "Meisterstueck", "14k Gold", "M",
         "piston", 780, False, "Standard", "Matte black PVD fittings, stealth design"),
    ]


def _pelikan_pens() -> list[tuple]:
    """13 Pelikan fountain pens — Souveraen, Toledo, special editions."""
    return [
        ("Souveraen M800 Black", "Pelikan", "Souveraen", "18k Gold", "M",
         "piston", 550, False, "Standard", "Flagship, striped celluloid"),
        ("Souveraen M800 Blue-Black", "Pelikan", "Souveraen", "18k Gold", "B",
         "piston", 550, False, "Standard", "Classic blue stripes"),
        ("Souveraen M1000", "Pelikan", "Souveraen", "18k Gold", "B",
         "piston", 750, False, "Standard", "Largest Souveraen, oversize nib"),
        ("Souveraen M600 Vibrant Green", "Pelikan", "Souveraen", "14k Gold", "F",
         "piston", 400, False, "Standard", "Special edition colorway"),
        ("Souveraen M400 White Tortoiseshell", "Pelikan", "Souveraen", "14k Gold", "EF",
         "piston", 350, False, "Standard", "Classic compact size"),
        ("Toledo M700 Silver", "Pelikan", "Toledo", "18k Gold", "M",
         "piston", 1200, False, "Standard", "Hand-engraved sterling silver"),
        ("Toledo M900", "Pelikan", "Toledo", "18k Gold", "B",
         "piston", 2500, True, "Limited Edition", "Large Toledo, elaborate engraving"),
        ("M800 Stone Garden", "Pelikan", "Souveraen", "18k Gold", "M",
         "piston", 700, True, "Limited Edition", "Special edition, marbled pattern"),
        ("M800 Renaissance Brown", "Pelikan", "Souveraen", "18k Gold", "M",
         "piston", 800, True, "Limited Edition", "Brown tortoiseshell resin"),
        ("M805 Ocean Swirl", "Pelikan", "Souveraen", "18k Gold", "F",
         "piston", 650, True, "Limited Edition", "Blue swirl demonstration barrel"),
        ("M200 Smoky Quartz", "Pelikan", "Classic", "Steel", "M",
         "piston", 130, True, "Limited Edition", "Ink of the Year edition"),
        ("Souveraen M600 Turquoise-White", "Pelikan", "Souveraen", "14k Gold", "M",
         "piston", 420, True, "Limited Edition", "Special edition turquoise stripes"),
        ("Souveraen M800 Grand Place", "Pelikan", "Souveraen", "18k Gold", "B",
         "piston", 850, True, "Limited Edition", "Brussels-inspired special edition"),
    ]


def _sailor_pens() -> list[tuple]:
    """13 Sailor fountain pens — King of Pen, Pro Gear, 1911, Realo, Bespoke."""
    return [
        ("King of Pen Black", "Sailor", "King of Pen", "21k Gold", "M",
         "converter", 850, False, "Standard", "Oversized flagship, 21k nib"),
        ("King of Pen Ebonite", "Sailor", "King of Pen", "21k Gold", "B",
         "converter", 1200, True, "Limited Edition", "Ebonite barrel, urushi lacquer"),
        ("Pro Gear Classic Black", "Sailor", "Pro Gear", "21k Gold", "M",
         "converter", 350, False, "Standard", "Flat-top design, RESIN body"),
        ("Pro Gear Slim Shikiori Yonaga", "Sailor", "Pro Gear Slim", "14k Gold", "MF",
         "converter", 280, True, "Limited Edition", "Four Seasons series, autumn night"),
        ("1911 Large Black Gold", "Sailor", "1911", "21k Gold", "M",
         "converter", 400, False, "Standard", "Classic cigar shape"),
        ("1911 Standard Transparent", "Sailor", "1911", "14k Gold", "F",
         "converter", 250, False, "Standard", "Demonstrator model"),
        ("Realo Pro Gear Black", "Sailor", "Realo", "21k Gold", "M",
         "piston", 550, False, "Standard", "Piston-fill Pro Gear"),
        ("Pro Gear Cocktail Series Kure Azur", "Sailor", "Pro Gear", "21k Gold", "M",
         "converter", 450, True, "Limited Edition", "Cocktail-inspired colorway"),
        ("King of Pen Bespoke Tangerine", "Sailor", "Bespoke", "21k Gold", "B",
         "converter", 1500, True, "Limited Edition", "Wancher exclusive, urushi"),
        ("Pro Gear Realo Demonstrator", "Sailor", "Realo", "21k Gold", "MF",
         "piston", 600, True, "Limited Edition", "Transparent piston filler"),
        ("1911 Profit Naginata Togi", "Sailor", "1911", "21k Gold", "Stub",
         "converter", 700, False, "Standard", "Cross-point specialty nib"),
        ("Pro Gear Slim Lucky Charm Clover", "Sailor", "Pro Gear Slim", "14k Gold", "MF",
         "converter", 300, True, "Limited Edition", "Green clover pattern, mini size"),
        ("King of Pen Urushi Vermillion", "Sailor", "King of Pen", "21k Gold", "M",
         "converter", 1800, True, "Limited Edition", "Hand-applied urushi over ebonite"),
    ]


def _pilot_pens() -> list[tuple]:
    """13 Pilot fountain pens — Namiki, Custom, VP, Myu."""
    return [
        ("Namiki Falcon", "Pilot", "Namiki", "14k Gold (Soft)", "F",
         "converter", 200, False, "Standard", "Soft semi-flex nib, metal barrel"),
        ("Custom 823 Amber", "Pilot", "Custom", "14k Gold", "M",
         "vacuum", 320, False, "Standard", "Vacuum-fill, large ink capacity"),
        ("Custom 823 Smoke", "Pilot", "Custom", "14k Gold", "F",
         "vacuum", 320, False, "Standard", "Smoke demonstrator variant"),
        ("Custom Urushi Vermillion", "Pilot", "Custom Urushi", "18k Gold", "M",
         "converter", 800, False, "Standard", "Hand-applied urushi lacquer"),
        ("Custom Urushi Black", "Pilot", "Custom Urushi", "18k Gold", "B",
         "converter", 800, False, "Standard", "24-layer urushi finish"),
        ("Vanishing Point Matte Black", "Pilot", "Vanishing Point", "18k Gold", "M",
         "converter", 200, False, "Standard", "Click retractable nib"),
        ("Vanishing Point Decimo Champagne", "Pilot", "Vanishing Point", "18k Gold", "F",
         "converter", 220, False, "Standard", "Slimmer VP variant"),
        ("Myu 701", "Pilot", "Myu", "Steel", "F",
         "converter", 600, False, "Exclusive", "Vintage integrated nib, stainless steel"),
        ("Custom 743 Deep Red", "Pilot", "Custom", "14k Gold", "B",
         "converter", 280, False, "Standard", "Size 15 nib, large barrel"),
        ("Custom Heritage 92 Demonstrator", "Pilot", "Custom Heritage", "14k Gold", "M",
         "piston", 180, False, "Standard", "Clear piston-fill demonstrator"),
        ("Namiki Yukari Nightline Milky Way", "Pilot", "Namiki Yukari", "18k Gold", "M",
         "converter", 2500, True, "Limited Edition", "Maki-e raden art, mother of pearl"),
        ("Custom 74 Dark Blue", "Pilot", "Custom", "14k Gold", "F",
         "converter", 160, False, "Standard", "Classic cigar shape, popular entry pen"),
        ("Vanishing Point Raden Galaxy", "Pilot", "Vanishing Point", "18k Gold", "M",
         "converter", 500, True, "Limited Edition", "Raden abalone shell inlay, retractable"),
    ]


def _lamy_pens() -> list[tuple]:
    """11 Lamy fountain pens — 2000, Dialog, Safari LE, Imporium."""
    return [
        ("2000 Black Makrolon", "Lamy", "2000", "14k Gold", "EF",
         "piston", 350, False, "Standard", "Bauhaus design icon, hooded nib"),
        ("2000 Stainless Steel", "Lamy", "2000", "14k Gold", "M",
         "piston", 550, False, "Standard", "Brushed steel variant"),
        ("Dialog 3 Piano Black", "Lamy", "Dialog", "14k Gold", "M",
         "converter", 380, False, "Standard", "Twist-retractable nib"),
        ("Safari Dark Lilac", "Lamy", "Safari", "Steel", "F",
         "converter", 80, True, "Limited Edition", "2016 special edition"),
        ("Safari Mango", "Lamy", "Safari", "Steel", "M",
         "converter", 65, True, "Limited Edition", "Annual limited color"),
        ("Safari Petrol", "Lamy", "Safari", "Steel", "F",
         "converter", 90, True, "Limited Edition", "2017 special edition, sought after"),
        ("Studio LX All Black", "Lamy", "Studio", "Steel", "M",
         "converter", 120, False, "Standard", "Matte black propeller clip"),
        ("Al-Star Bronze", "Lamy", "Al-Star", "Steel", "M",
         "converter", 45, True, "Limited Edition", "2019 limited colorway"),
        ("Aion Black", "Lamy", "Aion", "Steel", "M",
         "converter", 75, False, "Standard", "Seamless aluminum barrel"),
        ("2000 Black Amber", "Lamy", "2000", "14k Gold", "M",
         "piston", 400, True, "Limited Edition", "2024 special edition, amber resin window"),
        ("Imporium Blue-Gold", "Lamy", "Imporium", "14k Gold", "M",
         "converter", 450, False, "Standard", "Premium line, blue PVD coating"),
    ]


def _visconti_pens() -> list[tuple]:
    """9 Visconti fountain pens — Homo Sapiens, Opera Master, Wall Street, Van Gogh."""
    return [
        ("Homo Sapiens Bronze Age", "Visconti", "Homo Sapiens", "Palladium", "M",
         "vacuum", 750, False, "Standard", "Basaltic lava barrel, power-fill"),
        ("Homo Sapiens Dark Age", "Visconti", "Homo Sapiens", "Palladium", "B",
         "vacuum", 800, False, "Standard", "Matte black lava, dreamtouch nib"),
        ("Homo Sapiens Crystal Dream", "Visconti", "Homo Sapiens", "Palladium", "M",
         "vacuum", 900, True, "Limited Edition", "Clear demonstrator edition"),
        ("Opera Master Typhoon", "Visconti", "Opera Master", "18k Gold", "M",
         "vacuum", 1200, True, "Limited Edition", "Swirling celluloid"),
        ("Opera Master Rainforest", "Visconti", "Opera Master", "18k Gold", "M",
         "vacuum", 1100, True, "Limited Edition", "Green celluloid"),
        ("Wall Street Celluloid", "Visconti", "Wall Street", "Palladium", "F",
         "vacuum", 550, False, "Standard", "Pinstriped celluloid barrel"),
        ("Rembrandt Black", "Visconti", "Rembrandt", "Steel", "M",
         "converter", 200, False, "Standard", "Entry-level Visconti"),
        ("Homo Sapiens Lava Color Red", "Visconti", "Homo Sapiens", "Palladium", "M",
         "vacuum", 850, True, "Limited Edition", "Red lava resin, double reservoir"),
        ("Van Gogh Starry Night", "Visconti", "Van Gogh", "Steel", "M",
         "converter", 280, False, "Standard", "Hand-marbled resin, impressionist tribute"),
    ]


def _aurora_pens() -> list[tuple]:
    """7 Aurora fountain pens — 88, Optima, limited editions."""
    return [
        ("88 Black Mamba", "Aurora", "88", "18k Gold", "M",
         "piston", 600, False, "Standard", "Classic Italian design"),
        ("88 Saturno", "Aurora", "88", "18k Gold", "M",
         "piston", 700, True, "Limited Edition", "Limited blue marbled resin"),
        ("Optima Blue", "Aurora", "Optima", "18k Gold", "F",
         "piston", 550, False, "Standard", "Auroloide resin, flexible nib"),
        ("Optima 365 Coral", "Aurora", "Optima", "18k Gold", "M",
         "piston", 650, True, "Limited Edition", "365-piece annual edition"),
        ("Internazionale Black", "Aurora", "Internazionale", "18k Gold", "M",
         "piston", 500, False, "Standard", "Oversize piston filler"),
        ("Talentum Finesse Black", "Aurora", "Talentum", "14k Gold", "M",
         "converter", 280, False, "Standard", "Mid-range Italian pen"),
        ("88 Unica Black-Blue", "Aurora", "88", "18k Gold", "F",
         "piston", 650, True, "Limited Edition", "Annual limited, blue celluloid cap"),
    ]


def _nakaya_pens() -> list[tuple]:
    """7 Nakaya fountain pens — Dorsal Fin, Piccolo, Cigar, Naka-ai, urushi."""
    return [
        ("Dorsal Fin Version 2 Aka-Tamenuri", "Nakaya", "Dorsal Fin", "14k Gold", "M",
         "converter", 1200, False, "Standard", "Hand-turned ebonite, urushi finish"),
        ("Dorsal Fin Version 2 Kuro-Tamenuri", "Nakaya", "Dorsal Fin", "14k Gold", "F",
         "converter", 1200, False, "Standard", "Black tamenuri urushi"),
        ("Piccolo Long Cigar Shu", "Nakaya", "Piccolo", "14k Gold", "M",
         "converter", 800, False, "Standard", "Vermillion urushi, compact size"),
        ("Cigar Long Midori-Tamenuri", "Nakaya", "Cigar", "14k Gold", "B",
         "converter", 1000, False, "Standard", "Green tamenuri finish"),
        ("Decapod Twist Aka-Tamenuri", "Nakaya", "Decapod", "14k Gold", "M",
         "converter", 1500, False, "Standard", "Twisted faceted barrel"),
        ("Portable Writer Kuro-Roiro", "Nakaya", "Portable", "14k Gold", "F",
         "converter", 900, False, "Standard", "Deep black roiro urushi"),
        ("Naka-ai Writer Midori-Tamenuri", "Nakaya", "Naka-ai", "14k Gold", "M",
         "converter", 1100, False, "Standard", "Green tamenuri, capped writer size"),
    ]


def _vintage_pens() -> list[tuple]:
    """11 vintage fountain pens — Parker, Sheaffer, Waterman, Conklin."""
    return [
        ("Parker 51 Aerometric Navy", "Parker", "51", "14k Gold", "F",
         "aerometric", 250, False, "Exclusive", "1950s icon, hooded nib"),
        ("Parker 51 Vacumatic Burgundy", "Parker", "51", "14k Gold", "M",
         "vacuum", 400, False, "Exclusive", "Early vacumatic fill, celluloid"),
        ("Parker Duofold Centennial Black", "Parker", "Duofold", "18k Gold", "M",
         "converter", 500, False, "Standard", "Modern reissue of classic"),
        ("Sheaffer Snorkel Valiant Green", "Sheaffer", "Snorkel", "14k Gold", "F",
         "snorkel", 350, False, "Exclusive", "1950s pneumatic snorkel fill"),
        ("Sheaffer PFM III Black", "Sheaffer", "PFM", "14k Gold (Flex)", "M",
         "snorkel", 500, False, "Exclusive", "Pen for Men, inlaid nib"),
        ("Waterman 52 Red Ripple", "Waterman", "52", "14k Gold (Flex)", "F",
         "eyedropper", 800, False, "Exclusive", "1920s hard rubber, flex nib"),
        ("Waterman 52V Red Ripple", "Waterman", "52V", "14k Gold (Flex)", "F",
         "eyedropper", 650, False, "Exclusive", "Vest-pocket size, flex nib"),
        ("Conklin Crescent Filler Mark Twain", "Conklin", "Crescent", "Steel", "M",
         "crescent", 150, False, "Standard", "Modern reissue of crescent fill"),
        ("Parker Vacumatic Major Blue Diamond", "Parker", "Vacumatic", "14k Gold", "M",
         "vacuum", 350, False, "Exclusive", "1940s laminated celluloid"),
        ("Sheaffer Imperial Triumph Gold", "Sheaffer", "Imperial", "14k Gold", "M",
         "converter", 280, False, "Exclusive", "1960s gold-filled barrel, inlaid nib"),
        ("Waterman Edson Sapphire Blue", "Waterman", "Edson", "18k Gold", "M",
         "converter", 650, False, "Standard", "Flagship modern Waterman, oversize"),
    ]


def _japanese_artisan_pens() -> list[tuple]:
    """8 Japanese artisan / maki-e art pens."""
    return [
        ("Namiki Emperor Chinkin Autumn Leaf", "Namiki", "Emperor", "18k Gold", "M",
         "converter", 10000, True, "Limited Edition", "Large maki-e, chinkin technique"),
        ("Namiki Emperor Dragon", "Namiki", "Emperor", "18k Gold", "B",
         "converter", 8500, True, "Limited Edition", "Taka maki-e dragon motif"),
        ("Platinum Izumo Tamenuri", "Platinum", "Izumo", "18k Gold", "M",
         "converter", 1500, False, "Standard", "Yakumo-nuri lacquer, large pen"),
        ("Platinum Izumo Maki-e Pine", "Platinum", "Izumo", "18k Gold", "M",
         "converter", 3500, True, "Limited Edition", "Togidashi maki-e artwork"),
        ("Namiki Yukari Royale Peacock", "Namiki", "Yukari Royale", "18k Gold", "M",
         "converter", 4500, True, "Limited Edition", "Hira maki-e peacock, raden inlay"),
        ("Pilot Custom Urushi Maki-e Crane", "Pilot", "Custom Urushi", "18k Gold", "M",
         "converter", 5000, True, "Limited Edition", "Tsugaru lacquer, crane motif"),
        ("Namiki Yukari Royale Dragon", "Namiki", "Yukari Royale", "18k Gold", "B",
         "converter", 5500, True, "Limited Edition", "Taka maki-e dragon, gold accents"),
        ("Platinum President Maki-e Crane & Turtle", "Platinum", "President", "18k Gold", "M",
         "converter", 4000, True, "Limited Edition", "Togidashi maki-e, longevity motif"),
    ]


def _cartier_pens() -> list[tuple]:
    """6 Cartier fountain pens — luxury jewellery-quality writing instruments."""
    return [
        ("Santos de Cartier", "Cartier", "Santos", "18k Gold", "M",
         "converter", 850, False, "Standard",
         "Black composite barrel, palladium finish, Cartier signature C decor"),
        ("Diabolo de Cartier", "Cartier", "Diabolo", "18k Gold", "M",
         "converter", 1200, False, "Standard",
         "Black resin, platinum finish, cabochon cap jewel"),
        ("Roadster de Cartier", "Cartier", "Roadster", "18k Gold", "F",
         "converter", 950, False, "Standard",
         "Automotive-inspired tonneau shape, honeycomb guilloche"),
        ("Pasha de Cartier", "Cartier", "Pasha", "18k Gold", "M",
         "converter", 1500, False, "Standard",
         "Round profile, blue cabochon cap, lacquer barrel"),
        ("Louis Cartier Godron", "Cartier", "Louis Cartier", "18k Gold", "F",
         "converter", 1100, False, "Standard",
         "Godron ribbed pattern, palladium trim, Art Deco heritage"),
        ("R de Cartier", "Cartier", "R de Cartier", "18k Gold", "M",
         "converter", 400, False, "Standard",
         "Ribbed metal barrel, entry-level Cartier, compass rose cap"),
    ]


def _st_dupont_pens() -> list[tuple]:
    """9 S.T. Dupont fountain pens — French luxury maison, Chinese lacquer tradition."""
    return [
        ("Ligne 2 Gold Dust", "S.T. Dupont", "Ligne 2", "18k Gold", "M",
         "converter", 1200, False, "Standard",
         "Chinese lacquer, gold dust finish, 40 lacquer coats"),
        ("Ligne 2 Palladium", "S.T. Dupont", "Ligne 2", "18k Gold", "F",
         "converter", 900, False, "Standard",
         "Palladium finish, Chinese lacquer body, diamond-head pattern"),
        ("Ligne 2 Chinese Lacquer Black", "S.T. Dupont", "Ligne 2", "14k Gold", "M",
         "converter", 800, False, "Standard",
         "Natural Chinese lacquer, deep black, 8 lacquer layers"),
        ("Ligne 2 Fire Head Guilloche", "S.T. Dupont", "Ligne 2", "18k Gold", "M",
         "converter", 1100, True, "Limited Edition",
         "Guilloche pattern, amber lacquer, fire-head motif"),
        ("Ligne 2 Atelier Blue", "S.T. Dupont", "Ligne 2", "18k Gold", "F",
         "converter", 1050, True, "Limited Edition",
         "Atelier collection, midnight blue lacquer, gold dust finish"),
        ("Liberté Black Lacquer", "S.T. Dupont", "Liberté", "14k Gold", "M",
         "converter", 550, False, "Standard",
         "Streamlined silhouette, black natural lacquer, palladium accents"),
        ("Liberté Palladium", "S.T. Dupont", "Liberté", "14k Gold", "F",
         "converter", 500, False, "Standard",
         "All-palladium finish, guilloche engraving, slim profile"),
        ("Defi Millennium Carbon", "S.T. Dupont", "Defi", "14k Gold", "M",
         "converter", 300, False, "Standard",
         "Carbon fiber body, matt black PVD trim, modern design"),
        ("Olympio Large Black Lacquer", "S.T. Dupont", "Olympio", "18k Gold", "B",
         "converter", 900, False, "Standard",
         "Oversize profile, Chinese lacquer, two-tone 18k nib"),
    ]


def _caran_dache_pens() -> list[tuple]:
    """7 Caran d'Ache fountain pens — Swiss luxury, precision engineering."""
    return [
        ("Léman Slim Ebony Black", "Caran d'Ache", "Léman", "18k Gold", "M",
         "converter", 650, False, "Standard",
         "Chinese lacquer over brass, rhodium-coated 18k nib, slim profile"),
        ("Léman Grand Bleu", "Caran d'Ache", "Léman", "18k Gold", "F",
         "converter", 750, False, "Standard",
         "Deep blue lacquer, rhodium-coated 18k nib, silver-plated trim"),
        ("Ecridor Chevron", "Caran d'Ache", "Ecridor", "Steel", "M",
         "converter", 300, False, "Standard",
         "Palladium-coated brass, chevron guilloche, spring-loaded clip"),
        ("Ecridor Retro", "Caran d'Ache", "Ecridor", "Steel", "F",
         "converter", 350, False, "Standard",
         "Palladium-coated brass, retro diamond pattern, hexagonal barrel"),
        ("Varius Ivanhoe Silver", "Caran d'Ache", "Varius", "18k Gold", "M",
         "converter", 900, False, "Standard",
         "Sterling silver chainmail barrel, rhodium-coated 18k bicolor nib"),
        ("Varius Carbon", "Caran d'Ache", "Varius", "18k Gold", "M",
         "converter", 600, False, "Standard",
         "Carbon fiber barrel, rhodium-coated 18k nib, lightweight design"),
        ("Leman Caviar", "Caran d'Ache", "Léman", "18k Gold", "M",
         "converter", 850, False, "Standard",
         "Textured caviar-grain lacquer, rhodium-coated 18k nib"),
    ]


def _graf_von_faber_castell_pens() -> list[tuple]:
    """8 Graf von Faber-Castell fountain pens — Faber-Castell's premium luxury line."""
    return [
        ("Pen of the Year 2023 Ancient Egypt", "Graf von Faber-Castell", "Pen of the Year",
         "18k Gold", "M", "converter", 3000, True, "Limited Edition",
         "Annual LE, gold-plated barrel, hieroglyph engraving, 18k bicolor nib"),
        ("Pen of the Year 2022 Aztecs", "Graf von Faber-Castell", "Pen of the Year",
         "18k Gold", "B", "converter", 2800, True, "Limited Edition",
         "Annual LE, obsidian-inspired dark barrel, Aztec calendar motif"),
        ("Classic Anello Gold", "Graf von Faber-Castell", "Classic Anello",
         "18k Gold", "M", "converter", 450, False, "Standard",
         "Ribbed barrel with gold-plated rings, ebony wood cap, 18k bicolor nib"),
        ("Guilloche Burnt Orange", "Graf von Faber-Castell", "Guilloche",
         "18k Gold", "F", "converter", 350, False, "Standard",
         "Guilloche-engraved resin, rhodium-plated 18k nib, spring-loaded clip"),
        ("Guilloche Gulf Blue", "Graf von Faber-Castell", "Guilloche",
         "18k Gold", "M", "converter", 350, False, "Standard",
         "Guilloche-patterned resin barrel, platinum-plated fittings"),
        ("Tamitio Black", "Graf von Faber-Castell", "Tamitio",
         "Steel", "M", "converter", 200, False, "Standard",
         "Lacquered metal barrel, stainless steel nib, entry-level luxury"),
        ("Pen of the Year 2021 Knights", "Graf von Faber-Castell", "Pen of the Year",
         "18k Gold", "M", "converter", 3200, True, "Limited Edition",
         "Annual LE, Damascus steel barrel, medieval knight armor motif"),
        ("Classic Macassar", "Graf von Faber-Castell", "Classic",
         "18k Gold", "F", "converter", 500, False, "Standard",
         "Macassar ebony wood barrel, platinum-plated fittings, 18k bicolor nib"),
    ]


def _platinum_pens() -> list[tuple]:
    """8 Platinum fountain pens — Century, President, Procyon, Balance."""
    return [
        ("Century #3776 Black Diamond", "Platinum", "#3776 Century", "14k Gold", "M",
         "converter", 180, False, "Standard", "Flagship, slip & seal cap system"),
        ("Century #3776 Chartres Blue", "Platinum", "#3776 Century", "14k Gold", "F",
         "converter", 180, False, "Standard", "Translucent blue resin, popular color"),
        ("Century #3776 Nice Lavande", "Platinum", "#3776 Century", "14k Gold", "M",
         "converter", 200, True, "Limited Edition", "Lavender translucent resin"),
        ("Century #3776 Kumpoo", "Platinum", "#3776 Century", "14k Gold", "M",
         "converter", 350, True, "Limited Edition", "Fragrant olive maki-e, special edition"),
        ("President Black", "Platinum", "President", "18k Gold", "M",
         "converter", 600, False, "Standard", "Top-of-line, 18k nib, double-action cartridge"),
        ("Procyon Porcelain Blue", "Platinum", "Procyon", "Steel", "M",
         "converter", 80, False, "Standard", "Aluminum barrel, entry fountain pen"),
        ("Platinum Balance Crystal Blue", "Platinum", "Balance", "Steel", "M",
         "converter", 30, False, "Standard", "Entry-level translucent barrel"),
        ("Century #3776 Shape of a Heart", "Platinum", "#3776 Century", "14k Gold", "F",
         "converter", 250, True, "Limited Edition", "Heart-shaped barrel motif, LE release"),
    ]


def _parker_modern_pens() -> list[tuple]:
    """8 Parker modern fountain pens — Sonnet, IM, Premier, Duofold International."""
    return [
        ("Sonnet Gold Trim", "Parker", "Sonnet", "18k Gold", "M",
         "converter", 280, False, "Standard", "Lacquered brass barrel, gold trim"),
        ("Sonnet Pearl Lacquer", "Parker", "Sonnet", "18k Gold", "F",
         "converter", 300, False, "Standard", "White pearl lacquer, premium finish"),
        ("IM Premium Blue Grey", "Parker", "IM", "Steel", "M",
         "converter", 50, False, "Standard", "Anodized aluminum, modern entry pen"),
        ("Premier Custom Tartan", "Parker", "Premier", "18k Gold", "M",
         "converter", 450, False, "Standard", "Tartan lacquer pattern, luxury line"),
        ("Duofold International Classic Black", "Parker", "Duofold", "18k Gold", "M",
         "converter", 550, False, "Standard", "International size reissue, acrylic barrel"),
        ("Duofold International Red", "Parker", "Duofold", "18k Gold", "M",
         "converter", 580, False, "Standard", "Signature Big Red colour, acrylic barrel"),
        ("Parker 51 Reissue Burgundy", "Parker", "51 (Modern)", "18k Gold", "F",
         "converter", 350, False, "Standard", "2021 reissue of the iconic 51"),
        ("Parker 51 Reissue Midnight Blue", "Parker", "51 (Modern)", "18k Gold", "M",
         "converter", 350, False, "Standard", "2021 reissue, hooded 18k nib"),
    ]


def _independent_pens() -> list[tuple]:
    """10 independent / artisan brand fountain pens — Conid, BENU, Opus 88, TWSBI, Scribo."""
    return [
        ("Conid Bulkfiller Regular", "Conid", "Bulkfiller", "14k Gold", "M",
         "bulkfiller", 800, False, "Standard", "Belgian-made, patented bulk fill system"),
        ("Conid Minimalistica", "Conid", "Minimalistica", "14k Gold", "F",
         "bulkfiller", 650, False, "Standard", "Slim Conid, titanium internals"),
        ("BENU Briolette Luminous Amber", "BENU", "Briolette", "Steel", "M",
         "converter", 120, False, "Standard", "Sparkle resin barrel, glow-in-the-dark"),
        ("BENU Euphoria Tropical", "BENU", "Euphoria", "Steel", "M",
         "converter", 130, False, "Standard", "Swirled resin, vibrant colorway"),
        ("Opus 88 Koloro Demonstrator", "Opus 88", "Koloro", "Steel", "M",
         "eyedropper", 130, False, "Standard", "Japanese eyedropper, large ink capacity"),
        ("Opus 88 Jazz Translucent Blue", "Opus 88", "Jazz", "Steel", "F",
         "eyedropper", 85, False, "Standard", "Mini pen, eyedropper fill, pocket size"),
        ("TWSBI Eco Clear", "TWSBI", "Eco", "Steel", "EF",
         "piston", 35, False, "Standard", "Clear demonstrator, popular entry pen"),
        ("TWSBI Diamond 580ALR Navy Blue", "TWSBI", "Diamond 580", "Steel", "M",
         "piston", 70, False, "Standard", "Aluminum ring pattern, piston fill"),
        ("Scribo Feel Tramonto", "Scribo", "Feel", "18k Gold", "M",
         "piston", 550, False, "Standard", "Italian artisan, ebonite body, sunset color"),
        ("Scribo La Dotta Zucca", "Scribo", "La Dotta", "18k Gold", "B",
         "piston", 700, True, "Limited Edition", "Bologna tribute, pumpkin orange ebonite"),
    ]


def _esterbrook_pens() -> list[tuple]:
    """7 Esterbrook fountain pens — revived American heritage brand."""
    return [
        ("Estie Honeycomb", "Esterbrook", "Estie", "Steel", "M",
         "converter", 180, False, "Standard", "Honeycomb acrylic pattern, revived brand"),
        ("Estie Oversized Sea Glass", "Esterbrook", "Estie", "Steel", "B",
         "converter", 230, True, "Limited Edition", "Oversized, sea glass blue-green acrylic"),
        ("JR Pocket Pen Tuxedo Black", "Esterbrook", "JR Pocket", "Steel", "F",
         "converter", 85, False, "Standard", "Compact pocket pen, nod to vintage J series"),
        ("Camden Northern Lights", "Esterbrook", "Camden", "Steel", "M",
         "converter", 120, False, "Standard", "Aurora borealis resin pattern"),
        ("Estie Oversize Maraschino", "Esterbrook", "Estie", "Steel", "M",
         "converter", 220, True, "Limited Edition", "Cherry red oversize edition"),
        ("Influen$er Berry Sparkle", "Esterbrook", "Influen$er", "Steel", "M",
         "converter", 40, False, "Standard", "Budget-friendly, sparkle finish"),
        ("Estie Tortoise Gold Trim", "Esterbrook", "Estie", "Steel", "M",
         "converter", 190, False, "Standard", "Classic tortoiseshell pattern, gold fittings"),
    ]


def _montblanc_expanded() -> list[tuple]:
    """7 additional Montblanc fountain pens — Great Characters, Donation, Muses."""
    return [
        ("Great Characters Walt Disney SE", "Montblanc", "Great Characters", "18k Gold", "M",
         "piston", 1600, True, "Limited Edition", "Walt Disney tribute, magic cap"),
        ("Great Characters John F. Kennedy Navy", "Montblanc", "Great Characters", "18k Gold", "M",
         "converter", 800, False, "Standard", "Navy blue lacquer, JFK tribute"),
        ("Muses Marilyn Monroe Pearl", "Montblanc", "Muses", "18k Gold", "M",
         "converter", 900, True, "Limited Edition", "Pearl white lacquer, jewel-like cap"),
        ("Muses Elizabeth Taylor Boheme", "Montblanc", "Muses", "18k Gold", "F",
         "converter", 950, True, "Limited Edition", "Violet lacquer, diamond-shaped clip"),
        ("Donation Pen Frédéric Chopin", "Montblanc", "Donation Pen", "18k Gold", "M",
         "converter", 800, True, "Limited Edition", "Piano key motif, platinum trim"),
        ("Meisterstueck Solitaire Blue Hour", "Montblanc", "Meisterstueck", "18k Gold", "M",
         "piston", 1500, True, "Limited Edition", "Lacquer gradient blue, skeleton cap"),
        ("Heritage Egyptomania Black", "Montblanc", "Heritage", "18k Gold", "M",
         "converter", 1200, True, "Limited Edition", "Egyptian motif, lapis lazuli inlay"),
    ]


def _pelikan_expanded() -> list[tuple]:
    """7 additional Pelikan fountain pens — Birds of the World, Classic."""
    return [
        ("Souveraen M1000 Raden Sunrise", "Pelikan", "Souveraen", "18k Gold", "B",
         "piston", 2500, True, "Limited Edition", "Mother of pearl raden inlay, sunrise motif"),
        ("Souveraen M600 Red-White", "Pelikan", "Souveraen", "14k Gold", "M",
         "piston", 400, True, "Limited Edition", "Red & white stripes, special edition"),
        ("M800 Wall Street", "Pelikan", "Souveraen", "18k Gold", "F",
         "piston", 750, True, "Limited Edition", "Pinstripe pattern, business edition"),
        ("Classic M205 Olivine", "Pelikan", "Classic", "Steel", "M",
         "piston", 140, True, "Limited Edition", "Ink of the Year 2018 companion"),
        ("Classic M205 Star Ruby", "Pelikan", "Classic", "Steel", "F",
         "piston", 140, True, "Limited Edition", "Ink of the Year 2019 companion"),
        ("Souveraen M405 Stresemann", "Pelikan", "Souveraen", "14k Gold", "EF",
         "piston", 280, False, "Standard", "Anthracite stripes, named after politician"),
        ("M1005 Stresemann Black-Green", "Pelikan", "Souveraen", "18k Gold", "B",
         "piston", 850, False, "Standard", "Large size Stresemann, green-black stripes"),
    ]


def _sailor_expanded() -> list[tuple]:
    """7 additional Sailor fountain pens — limited colors, specialty nibs."""
    return [
        ("Pro Gear Slim Manyo Haha", "Sailor", "Pro Gear Slim", "14k Gold", "MF",
         "converter", 320, True, "Limited Edition", "Manyo botanical series, mother plant"),
        ("Pro Gear Slim Manyo Nekoyanagi", "Sailor", "Pro Gear Slim", "14k Gold", "F",
         "converter", 320, True, "Limited Edition", "Manyo botanical, willow catkin"),
        ("King of Pen ST (Standard Nib)", "Sailor", "King of Pen", "21k Gold", "MF",
         "converter", 900, False, "Standard", "Standard-tip version of KoP"),
        ("Pro Gear Classic Ivory", "Sailor", "Pro Gear", "21k Gold", "M",
         "converter", 380, False, "Standard", "Ivory resin body, gold trim"),
        ("1911 Large Fresca Blue", "Sailor", "1911", "21k Gold", "M",
         "converter", 420, True, "Limited Edition", "Cool blue transparent resin"),
        ("Pro Gear Zoom Nib", "Sailor", "Pro Gear", "21k Gold", "Zoom",
         "converter", 450, False, "Standard", "Specialty Zoom nib, line variation with speed"),
        ("Pro Gear Slim Mini Gold Forest Green", "Sailor", "Pro Gear Slim Mini", "14k Gold", "MF",
         "converter", 200, False, "Standard", "Compact pocket pen, forest green resin"),
    ]


def _additional_visconti() -> list[tuple]:
    """6 additional Visconti fountain pens."""
    return [
        ("Homo Sapiens Midnight in Florence", "Visconti", "Homo Sapiens", "Palladium", "M",
         "vacuum", 850, True, "Limited Edition", "Dark blue lava, Florence tribute"),
        ("Opera Gold Typhoon", "Visconti", "Opera", "18k Gold", "B",
         "vacuum", 1400, True, "Limited Edition", "Swirling celluloid, gold trim"),
        ("Van Gogh Self Portrait Blue", "Visconti", "Van Gogh", "Steel", "F",
         "converter", 290, False, "Standard", "Blue marbled resin, self-portrait tribute"),
        ("Medici Dynasty Red", "Visconti", "Medici", "18k Gold", "M",
         "vacuum", 950, True, "Limited Edition", "Florentine dynasty tribute, red acrylic"),
        ("Homo Sapiens Florentine Hills", "Visconti", "Homo Sapiens", "Palladium", "F",
         "vacuum", 800, True, "Limited Edition", "Green basaltic lava barrel"),
        ("Torpedo Crystal Swirl", "Visconti", "Torpedo", "Steel", "M",
         "converter", 350, False, "Standard", "Crystal swirl demonstrator, torpedo shape"),
    ]


# ---------------------------------------------------------------------------
# EXPANSION ROUND — 310+ additional fountain pens
# ---------------------------------------------------------------------------


def _montblanc_round3() -> list[tuple]:
    """20 additional Montblanc fountain pens — StarWalker, Great Characters, Patron of Art."""
    return [
        ("StarWalker Doue", "Montblanc", "StarWalker", "14k Gold", "F",
         "converter", 700, False, "Standard", "Two-tone resin and metal barrel"),
        ("StarWalker SpaceBlue Doue", "Montblanc", "StarWalker", "14k Gold", "M",
         "converter", 780, False, "Standard", "Blue lacquer and metal, floating emblem"),
        ("Great Characters Enzo Ferrari", "Montblanc", "Great Characters", "18k Gold", "M",
         "piston", 1400, True, "Limited Edition", "2023 LE, racing red lacquer, horse clip"),
        ("Great Characters The Beatles", "Montblanc", "Great Characters", "18k Gold", "F",
         "piston", 1350, True, "Limited Edition", "2024 LE, Abbey Road tribute design"),
        ("Great Characters Muhammad Ali", "Montblanc", "Great Characters", "18k Gold", "B",
         "piston", 1500, True, "Limited Edition", "Boxing glove cap, gold ring clip"),
        ("Great Characters Jimi Hendrix", "Montblanc", "Great Characters", "18k Gold", "M",
         "piston", 1450, True, "Limited Edition", "Purple haze lacquer, guitar fret clip"),
        ("Great Characters Leonardo da Vinci", "Montblanc", "Great Characters", "18k Gold", "M",
         "piston", 1600, True, "Limited Edition", "Renaissance brown lacquer, codex engravings"),
        ("Patron of Art Homage to Ludwig II 4810", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 3000, True, "Limited Edition", "Bavarian castle motifs, 4810-piece LE"),
        ("Patron of Art Homage to Albert 4810", "Montblanc", "Patron of Art", "18k Gold", "F",
         "piston", 2900, True, "Limited Edition", "British crown motifs, 4810-piece LE"),
        ("Writers Edition Victor Hugo", "Montblanc", "Writers Edition", "18k Gold", "M",
         "piston", 1300, True, "Limited Edition", "2020 LE, Gothic cathedral cap design"),
        ("Writers Edition Jane Austen", "Montblanc", "Writers Edition", "18k Gold", "F",
         "piston", 1250, True, "Limited Edition", "2022 LE, ivory lacquer, cameo clip"),
        ("Writers Edition Daniel Defoe", "Montblanc", "Writers Edition", "18k Gold", "M",
         "piston", 1150, True, "Limited Edition", "2014 LE, blue resin, nautical motifs"),
        ("Writers Edition Mark Twain", "Montblanc", "Writers Edition", "18k Gold", "B",
         "piston", 1200, True, "Limited Edition", "2010 LE, Mississippi paddlewheel clip"),
        ("Meisterstueck Glacier", "Montblanc", "Meisterstueck", "14k Gold", "M",
         "piston", 800, True, "Limited Edition", "Ice blue translucent resin, glacier motif"),
        ("Meisterstueck Around the World in 80 Days", "Montblanc", "Meisterstueck", "18k Gold", "M",
         "piston", 1100, True, "Limited Edition", "Blue lacquer, globe engraving"),
        ("Meisterstueck Le Petit Prince Aviator", "Montblanc", "Meisterstueck", "18k Gold", "F",
         "converter", 850, True, "Limited Edition", "Night blue lacquer, fox emblem"),
        ("Heritage Rouge et Noir Tropic Brown", "Montblanc", "Heritage", "14k Gold", "M",
         "piston", 950, False, "Standard", "Tropical brown resin, Art Deco design"),
        ("Meisterstueck 149 Unicef", "Montblanc", "Meisterstueck", "18k Gold", "M",
         "piston", 1050, True, "Limited Edition", "Turquoise lacquer, UNICEF charity edition"),
        ("Meisterstueck 146 Doue Stainless Steel", "Montblanc", "Meisterstueck", "14k Gold", "F",
         "piston", 900, False, "Standard", "Stainless steel cap, resin barrel"),
        ("Meisterstueck 145 Gold-Coated", "Montblanc", "Meisterstueck", "14k Gold", "M",
         "converter", 700, False, "Standard", "Gold-plated cap and barrel overlay"),
    ]


def _pelikan_round3() -> list[tuple]:
    """18 additional Pelikan fountain pens — M200-M1000 range, Edelstein, Hubs."""
    return [
        ("Souveraen M200 Black", "Pelikan", "Classic", "Steel", "F",
         "piston", 110, False, "Standard", "Entry-level piston filler, gold-plated trim"),
        ("Souveraen M200 Cafe Creme", "Pelikan", "Classic", "Steel", "M",
         "piston", 120, True, "Limited Edition", "Ink of the Year 2023 companion"),
        ("Souveraen M300 Black-Green", "Pelikan", "Souveraen", "14k Gold", "F",
         "piston", 220, False, "Standard", "Compact pocket-size Souveraen"),
        ("Souveraen M400 Black", "Pelikan", "Souveraen", "14k Gold", "M",
         "piston", 330, False, "Standard", "Classic mid-size, green-black stripes"),
        ("Souveraen M600 Black", "Pelikan", "Souveraen", "14k Gold", "B",
         "piston", 380, False, "Standard", "Full-size entry to 14k Souveraen line"),
        ("Souveraen M600 Violet-White", "Pelikan", "Souveraen", "14k Gold", "F",
         "piston", 430, True, "Limited Edition", "2023 special edition, violet stripes"),
        ("Souveraen M800 Brown-Black", "Pelikan", "Souveraen", "18k Gold", "M",
         "piston", 600, True, "Limited Edition", "Tortoiseshell brown stripes, classic elegance"),
        ("Souveraen M800 Burnt Orange", "Pelikan", "Souveraen", "18k Gold", "B",
         "piston", 650, True, "Limited Edition", "2015 special edition, vivid orange stripes"),
        ("Souveraen M1000 Green-Black", "Pelikan", "Souveraen", "18k Gold", "M",
         "piston", 780, False, "Standard", "Largest standard Souveraen, classic colorway"),
        ("M805 Vibrant Blue", "Pelikan", "Souveraen", "18k Gold", "F",
         "piston", 600, True, "Limited Edition", "2016 special edition, vivid blue stripes"),
        ("M800 Blue o'Blue", "Pelikan", "Souveraen", "18k Gold", "M",
         "piston", 680, True, "Limited Edition", "2021 special edition, deep blue celluloid"),
        ("Classic M200 Pastel Green", "Pelikan", "Classic", "Steel", "F",
         "piston", 135, True, "Limited Edition", "Ink of the Year 2024 companion"),
        ("Classic M205 Aquamarine", "Pelikan", "Classic", "Steel", "M",
         "piston", 140, True, "Limited Edition", "Demonstrator with Edelstein ink match"),
        ("Classic M120 Iconic Blue", "Pelikan", "Classic", "Steel", "M",
         "piston", 95, False, "Standard", "Entry-level Pelikan, piston filler"),
        ("M800 Grand Place Special Edition", "Pelikan", "Souveraen", "18k Gold", "F",
         "piston", 850, True, "Limited Edition", "Brussels-inspired transparent barrel"),
        ("Toledo M710", "Pelikan", "Toledo", "18k Gold", "F",
         "piston", 1300, False, "Standard", "Sterling silver hand-engraved barrel, mid-size"),
        ("M1005 Demonstrator", "Pelikan", "Souveraen", "18k Gold", "B",
         "piston", 900, True, "Limited Edition", "Fully transparent M1000 special edition"),
        ("M815 Metal Striped", "Pelikan", "Souveraen", "18k Gold", "M",
         "piston", 620, True, "Limited Edition", "Alternating metal and resin stripes"),
    ]


def _sailor_round3() -> list[tuple]:
    """22 additional Sailor fountain pens — Pro Gear, KoP, 1911, Manyo, limited editions."""
    return [
        ("Pro Gear Realo Demonstrator Blue", "Sailor", "Realo", "21k Gold", "M",
         "piston", 620, True, "Limited Edition", "Blue-tinted transparent piston filler"),
        ("Pro Gear Slim Shikiori Shimoyo", "Sailor", "Pro Gear Slim", "14k Gold", "F",
         "converter", 280, True, "Limited Edition", "Four Seasons frost night, pale blue"),
        ("Pro Gear Slim Shikiori Ayanami", "Sailor", "Pro Gear Slim", "14k Gold", "MF",
         "converter", 280, True, "Limited Edition", "Four Seasons gentle waves, blue-green"),
        ("Pro Gear Slim Manyo Sakura", "Sailor", "Pro Gear Slim", "14k Gold", "MF",
         "converter", 320, True, "Limited Edition", "Manyo botanical series, cherry blossom"),
        ("Pro Gear Slim Manyo Kakitsubata", "Sailor", "Pro Gear Slim", "14k Gold", "F",
         "converter", 320, True, "Limited Edition", "Manyo botanical, iris flower, deep purple"),
        ("Pro Gear Slim Manyo Ume", "Sailor", "Pro Gear Slim", "14k Gold", "MF",
         "converter", 320, True, "Limited Edition", "Manyo botanical series, plum blossom pink"),
        ("King of Pen Profit", "Sailor", "King of Pen", "21k Gold", "B",
         "converter", 950, False, "Standard", "Rounded profile KoP, classic cigar shape"),
        ("1911 Large Demonstrator", "Sailor", "1911", "21k Gold", "M",
         "converter", 450, True, "Limited Edition", "Fully transparent 1911 body"),
        ("1911 Standard Wicked Witch of the West", "Sailor", "1911", "14k Gold", "MF",
         "converter", 280, True, "Limited Edition", "Pen of the Year exclusive, green marble"),
        ("Pro Gear Classic Fire", "Sailor", "Pro Gear", "21k Gold", "M",
         "converter", 400, True, "Limited Edition", "Burnt orange resin, gold trim"),
        ("Pro Gear Cocktail Series Old Fashioned", "Sailor", "Pro Gear", "21k Gold", "B",
         "converter", 450, True, "Limited Edition", "Cocktail-inspired, amber celluloid"),
        ("Pro Gear Cocktail Series Tequila Sunrise", "Sailor", "Pro Gear", "21k Gold", "M",
         "converter", 450, True, "Limited Edition", "Orange-red gradient resin"),
        ("1911 Profit Standard Demonstrator", "Sailor", "1911", "14k Gold", "F",
         "converter", 230, False, "Standard", "Clear transparent 1911 standard size"),
        ("1911 Large Stormy Sea", "Sailor", "1911", "21k Gold", "M",
         "converter", 480, True, "Limited Edition", "Dark blue swirled resin"),
        ("Pro Gear King Cobra", "Sailor", "Pro Gear", "21k Gold", "Zoom",
         "converter", 500, True, "Limited Edition", "King Cobra cross-point specialty nib"),
        ("Pro Gear Slim Lucky Charm Daruma", "Sailor", "Pro Gear Slim", "14k Gold", "MF",
         "converter", 300, True, "Limited Edition", "Red daruma motif, compact size"),
        ("King of Pen Bespoke Morita Blue", "Sailor", "Bespoke", "21k Gold", "B",
         "converter", 1600, True, "Limited Edition", "Morita exclusive, deep blue urushi"),
        ("King of Pen Bespoke Lilac", "Sailor", "Bespoke", "21k Gold", "M",
         "converter", 1500, True, "Limited Edition", "Wancher exclusive, lilac urushi"),
        ("Pro Gear Realo Midnight Blue-Gold", "Sailor", "Realo", "21k Gold", "MF",
         "piston", 580, False, "Standard", "Midnight blue resin, gold trim, piston fill"),
        ("1911 Profit Junior Clear", "Sailor", "1911", "14k Gold", "F",
         "converter", 180, False, "Standard", "Entry-level gold nib, clear demonstrator"),
        ("Pro Gear Slim Sapporo Mini Pearl", "Sailor", "Pro Gear Slim Mini", "14k Gold", "F",
         "converter", 200, True, "Limited Edition", "Pearl white compact pocket pen"),
        ("1911 Large Silver Cosmos", "Sailor", "1911", "21k Gold", "M",
         "converter", 500, True, "Limited Edition", "Cosmos-themed silver lacquer"),
    ]


def _pilot_round3() -> list[tuple]:
    """20 additional Pilot/Namiki fountain pens — Custom, VP, Maki-e, Urushi."""
    return [
        ("Custom 912 FA (Falcon Nib)", "Pilot", "Custom", "14k Gold (Soft)", "F",
         "converter", 250, False, "Standard", "Flex/soft nib on 912 body, wet writer"),
        ("Custom 912 PO (Posting Nib)", "Pilot", "Custom", "14k Gold", "EF",
         "converter", 240, False, "Standard", "Ultra-fine posting nib, accounting pen"),
        ("Custom 912 WA (Waverly Nib)", "Pilot", "Custom", "14k Gold", "M",
         "converter", 240, False, "Standard", "Upturned Waverly nib, smooth start"),
        ("Custom 845 Vermillion Urushi", "Pilot", "Custom Urushi", "18k Gold", "M",
         "converter", 600, False, "Standard", "Ebonite body, hand-applied urushi layers"),
        ("Custom 743 Black", "Pilot", "Custom", "14k Gold", "M",
         "converter", 280, False, "Standard", "Size 15 nib, large ink capacity"),
        ("Vanishing Point Carbonesque", "Pilot", "Vanishing Point", "18k Gold", "F",
         "converter", 250, False, "Standard", "Carbon fiber pattern, retractable nib"),
        ("Vanishing Point Tropical Turquoise", "Pilot", "Vanishing Point", "18k Gold", "M",
         "converter", 240, True, "Limited Edition", "2023 limited colorway, bright turquoise"),
        ("Vanishing Point Stripes", "Pilot", "Vanishing Point", "18k Gold", "F",
         "converter", 280, True, "Limited Edition", "Guilloche stripe pattern, brass body"),
        ("Justus 95 Adjustable Nib", "Pilot", "Justus", "14k Gold", "M",
         "converter", 350, False, "Standard", "Adjustable soft-hard nib tension ring"),
        ("Namiki Chinkin Cherry Blossom", "Namiki", "Chinkin", "18k Gold", "M",
         "converter", 3500, True, "Limited Edition", "Chinkin needle-engraved sakura design"),
        ("Namiki Chinkin Carp", "Namiki", "Chinkin", "18k Gold", "B",
         "converter", 3800, True, "Limited Edition", "Chinkin technique, koi carp motif"),
        ("Namiki Yukari Royale Pine", "Namiki", "Yukari Royale", "18k Gold", "M",
         "converter", 4200, True, "Limited Edition", "Taka maki-e pine tree, gold accents"),
        ("Custom Heritage 912 Smoke", "Pilot", "Custom Heritage", "14k Gold", "F",
         "converter", 230, False, "Standard", "Translucent smoke barrel, CON-70"),
        ("Custom Heritage 91 Blue", "Pilot", "Custom Heritage", "14k Gold", "M",
         "converter", 150, False, "Standard", "Entry-level 14k gold nib pen"),
        ("Custom 74 Demonstrator", "Pilot", "Custom", "14k Gold", "F",
         "converter", 180, False, "Standard", "Clear transparent Custom 74 barrel"),
        ("Myu 701 Stripe", "Pilot", "Myu", "Steel", "M",
         "converter", 700, False, "Exclusive", "Vintage integrated nib, striped barrel variant"),
        ("Murex MR", "Pilot", "Murex", "Steel", "M",
         "converter", 550, False, "Exclusive", "Vintage all-metal pen, sister to Myu"),
        ("E95s Red", "Pilot", "E95s", "14k Gold", "F",
         "converter", 180, False, "Standard", "Pocket pen, retro design, red lacquer"),
        ("Namiki Yukari Autumn Grass", "Namiki", "Yukari", "18k Gold", "M",
         "converter", 2200, True, "Limited Edition", "Hira maki-e susuki grass, raden inlay"),
        ("Custom Urushi Tamenuri Green", "Pilot", "Custom Urushi", "18k Gold", "B",
         "converter", 850, False, "Standard", "Green tamenuri urushi finish, ebonite"),
    ]


def _platinum_round3() -> list[tuple]:
    """15 additional Platinum fountain pens — #3776, President, Izumo, specialty."""
    return [
        ("Century #3776 Bourgogne", "Platinum", "#3776 Century", "14k Gold", "B",
         "converter", 180, False, "Standard", "Deep red translucent resin"),
        ("Century #3776 Carnelian", "Platinum", "#3776 Century", "14k Gold", "M",
         "converter", 200, True, "Limited Edition", "Orange-red translucent limited edition"),
        ("Century #3776 Shiun", "Platinum", "#3776 Century", "14k Gold", "F",
         "converter", 350, True, "Limited Edition", "Purple cloud maki-e, dealer exclusive"),
        ("Century #3776 Rokka", "Platinum", "#3776 Century", "14k Gold", "M",
         "converter", 350, True, "Limited Edition", "Snowflake maki-e, winter series"),
        ("Century #3776 Star Wars R2-D2", "Platinum", "#3776 Century", "14k Gold", "M",
         "converter", 300, True, "Limited Edition", "Officially licensed Star Wars edition"),
        ("President Wine Red", "Platinum", "President", "18k Gold", "B",
         "converter", 620, False, "Standard", "Wine red lacquer, double-action converter"),
        ("Izumo Tagi Shu Akebono", "Platinum", "Izumo", "18k Gold", "M",
         "converter", 1800, True, "Limited Edition", "Dawn-inspired Yakumo-nuri lacquer"),
        ("Izumo Soratame", "Platinum", "Izumo", "18k Gold", "F",
         "converter", 1600, False, "Standard", "Cloudy sky Yakumo-nuri, ebonite barrel"),
        ("Procyon Luster Turquoise Blue", "Platinum", "Procyon", "Steel", "F",
         "converter", 90, False, "Standard", "Luster finish aluminum barrel"),
        ("Curidas Gran Red", "Platinum", "Curidas", "14k Gold", "M",
         "retractable", 250, False, "Standard", "Retractable nib, red resin body"),
        ("Curidas Graphite Smoke", "Platinum", "Curidas", "14k Gold", "F",
         "retractable", 250, False, "Standard", "Retractable nib, translucent smoke"),
        ("Century #3776 Music Nib", "Platinum", "#3776 Century", "14k Gold", "Music",
         "converter", 220, False, "Standard", "Triple-tine music nib, wet line variation"),
        ("Century #3776 UEF", "Platinum", "#3776 Century", "14k Gold", "UEF",
         "converter", 180, False, "Standard", "Ultra extra fine, finest production nib"),
        ("Maki-e Kanazawa Leaf Phoenix", "Platinum", "Maki-e", "18k Gold", "M",
         "converter", 2500, True, "Limited Edition", "Kanazawa gold leaf phoenix motif"),
        ("Century #3776 Fuji Konpeki", "Platinum", "#3776 Century", "14k Gold", "M",
         "converter", 200, True, "Limited Edition", "Mount Fuji inspired azure blue"),
    ]


def _parker_waterman_round3() -> list[tuple]:
    """18 additional Parker and Waterman fountain pens."""
    return [
        # Parker
        ("Parker 75 Sterling Silver Cisele", "Parker", "75", "14k Gold", "F",
         "converter", 300, False, "Exclusive", "1960s classic, sterling silver crosshatch"),
        ("Parker 75 Gold Filled", "Parker", "75", "14k Gold", "M",
         "converter", 250, False, "Exclusive", "Gold-filled barrel, click cap"),
        ("Parker Duofold Centennial Red", "Parker", "Duofold", "18k Gold", "B",
         "converter", 550, False, "Standard", "Big Red modern reissue"),
        ("Parker Duofold Centennial Pearl & Black", "Parker", "Duofold", "18k Gold", "M",
         "converter", 580, False, "Standard", "Pearl and black acrylic barrel"),
        ("Parker Duofold Senior Streamline Green", "Parker", "Duofold Vintage", "14k Gold", "M",
         "button", 800, False, "Exclusive", "1930s vintage, jade green celluloid"),
        ("Parker Sonnet Secret Red Shell", "Parker", "Sonnet", "18k Gold", "F",
         "converter", 320, False, "Standard", "Red lacquer with subtle shell pattern"),
        ("Parker Sonnet Chiselled Carbon", "Parker", "Sonnet", "18k Gold", "M",
         "converter", 350, False, "Standard", "Carbon fiber pattern, palladium trim"),
        ("Parker 51 Reissue Black", "Parker", "51 (Modern)", "18k Gold", "M",
         "converter", 350, False, "Standard", "2021 reissue, classic black, hooded nib"),
        ("Parker Vacumatic Emerald Pearl", "Parker", "Vacumatic", "14k Gold", "M",
         "vacuum", 400, False, "Exclusive", "1940s green pearl laminated celluloid"),
        # Waterman
        ("Waterman Carene Black Sea", "Waterman", "Carene", "18k Gold", "M",
         "converter", 350, False, "Standard", "Lacquered metallic body, boat-shaped silhouette"),
        ("Waterman Carene Amber", "Waterman", "Carene", "18k Gold", "F",
         "converter", 380, False, "Standard", "Shimmer amber lacquer, streamlined shape"),
        ("Waterman Expert Metallic Gold", "Waterman", "Expert", "Steel", "M",
         "converter", 120, False, "Standard", "Gold lacquer over brass, premium entry"),
        ("Waterman Hemisphere Matte Black", "Waterman", "Hemisphere", "Steel", "F",
         "converter", 80, False, "Standard", "Slim matte black barrel, affordable French pen"),
        ("Waterman Exception Slim Blue", "Waterman", "Exception", "18k Gold", "M",
         "converter", 500, False, "Standard", "Slim luxury line, blue lacquer"),
        ("Waterman Ideal Original Brown", "Waterman", "Ideal", "14k Gold (Flex)", "M",
         "eyedropper", 900, False, "Exclusive", "1920s brown ripple hard rubber, flex nib"),
        ("Waterman 42 Safety Red Ripple", "Waterman", "42 Safety", "14k Gold (Flex)", "F",
         "eyedropper", 700, False, "Exclusive", "Safety retractable nib, hard rubber"),
        ("Waterman 452 Sterling Silver Overlay", "Waterman", "452", "14k Gold (Flex)", "M",
         "eyedropper", 1200, False, "Exclusive", "1920s overlay, vine pattern, flex nib"),
        ("Waterman Patrician Onyx", "Waterman", "Patrician", "14k Gold", "B",
         "lever", 600, False, "Exclusive", "1930s oversize, black celluloid"),
    ]


def _aurora_round3() -> list[tuple]:
    """12 additional Aurora fountain pens."""
    return [
        ("88 Nebulosa", "Aurora", "88", "18k Gold", "M",
         "piston", 750, True, "Limited Edition", "Nebula-inspired swirl celluloid"),
        ("88 Minerali Ambra", "Aurora", "88", "18k Gold", "F",
         "piston", 700, True, "Limited Edition", "Amber mineral celluloid"),
        ("Optima 365 Tortoise", "Aurora", "Optima", "18k Gold", "M",
         "piston", 650, True, "Limited Edition", "365-piece annual, tortoiseshell celluloid"),
        ("Optima Blue Chrome", "Aurora", "Optima", "18k Gold", "B",
         "piston", 580, False, "Standard", "Chrome blue auroloide, flexible nib"),
        ("Optima Demonstrator", "Aurora", "Optima", "18k Gold", "F",
         "piston", 600, True, "Limited Edition", "Transparent demonstrator Optima"),
        ("Internazionale Red", "Aurora", "Internazionale", "18k Gold", "M",
         "piston", 520, False, "Standard", "Red auroloide oversize piston filler"),
        ("Talentum Black Chrome", "Aurora", "Talentum", "14k Gold", "F",
         "converter", 300, False, "Standard", "Black chrome finish, Italian mid-range"),
        ("88 Ottantotto Green Mamba", "Aurora", "88", "18k Gold", "M",
         "piston", 650, True, "Limited Edition", "Green swirl celluloid cap"),
        ("Ipsilon Deluxe Blue", "Aurora", "Ipsilon", "Steel", "M",
         "converter", 150, False, "Standard", "Entry-level Aurora, blue resin"),
        ("Mare Blu Limited", "Aurora", "Mare", "18k Gold", "M",
         "piston", 1200, True, "Limited Edition", "Mediterranean blue, 888-piece LE"),
        ("Afrika Red", "Aurora", "Afrika", "18k Gold", "B",
         "piston", 900, True, "Limited Edition", "Africa-themed, red resin, safari clip"),
        ("Hastil Gold Plated", "Aurora", "Hastil", "14k Gold", "M",
         "converter", 350, False, "Standard", "Slim all-metal tubular design"),
    ]


def _lamy_twsbi_round3() -> list[tuple]:
    """15 additional Lamy and TWSBI fountain pens."""
    return [
        # Lamy
        ("2000 Taxus", "Lamy", "2000", "14k Gold", "M",
         "piston", 550, True, "Limited Edition", "Yew wood barrel, Bauhaus design"),
        ("2000 Brown", "Lamy", "2000", "14k Gold", "F",
         "piston", 380, True, "Limited Edition", "2019 limited edition brown Makrolon"),
        ("2000 Blue Bauhaus", "Lamy", "2000", "14k Gold", "EF",
         "piston", 400, True, "Limited Edition", "2019 Bauhaus 100th anniversary blue"),
        ("Dialog CC", "Lamy", "Dialog", "14k Gold", "M",
         "converter", 300, False, "Standard", "Modern retractable, rubber grip section"),
        ("Safari All Black", "Lamy", "Safari", "Steel", "F",
         "converter", 35, False, "Standard", "Stealth matte all-black Safari"),
        ("Safari Savannah Green", "Lamy", "Safari", "Steel", "M",
         "converter", 70, True, "Limited Edition", "2021 annual limited color"),
        ("Safari Aquamarine", "Lamy", "Safari", "Steel", "F",
         "converter", 70, True, "Limited Edition", "2020 annual limited color, teal"),
        ("Al-Star Ocean Blue", "Lamy", "Al-Star", "Steel", "M",
         "converter", 40, False, "Standard", "Anodized aluminum barrel, ocean blue"),
        ("Scala Black", "Lamy", "Scala", "Steel", "M",
         "converter", 150, False, "Standard", "Piano lacquer black, slim design"),
        # TWSBI
        ("TWSBI Eco Rose Gold", "TWSBI", "Eco", "Steel", "M",
         "piston", 40, True, "Limited Edition", "Rose gold trim on clear demonstrator"),
        ("TWSBI Eco White", "TWSBI", "Eco", "Steel", "F",
         "piston", 35, False, "Standard", "White barrel piston fill demonstrator"),
        ("TWSBI Vac700R Iris", "TWSBI", "Vac700R", "Steel", "M",
         "vacuum", 75, True, "Limited Edition", "Rainbow plated trim, vacuum fill"),
        ("TWSBI Vac700R Clear", "TWSBI", "Vac700R", "Steel", "B",
         "vacuum", 65, False, "Standard", "Vacuum fill demonstrator, large capacity"),
        ("TWSBI Diamond 580 Clear", "TWSBI", "Diamond 580", "Steel", "EF",
         "piston", 60, False, "Standard", "Full-size demonstrator piston filler"),
        ("TWSBI Precision Gunmetal", "TWSBI", "Precision", "Steel", "M",
         "converter", 55, False, "Standard", "All-metal machined barrel, gunmetal finish"),
    ]


def _vintage_expanded() -> list[tuple]:
    """25 additional vintage fountain pens — Sheaffer, Esterbrook, Wahl Eversharp, Moore, Conway Stewart."""
    return [
        # Sheaffer
        ("Sheaffer Lifetime Balance Emerald", "Sheaffer", "Lifetime", "14k Gold (Flex)", "M",
         "lever", 500, False, "Exclusive", "1930s oversized, emerald pearl celluloid, flex nib"),
        ("Sheaffer Targa 1001 Gold Fluted", "Sheaffer", "Targa", "14k Gold", "M",
         "converter", 200, False, "Exclusive", "1970s slim gold electroplate, fluted barrel"),
        ("Sheaffer Snorkel Sentinel Blue", "Sheaffer", "Snorkel", "14k Gold", "F",
         "snorkel", 250, False, "Exclusive", "1950s blue barrel, touchdown snorkel fill"),
        ("Sheaffer Crest Reissue Black", "Sheaffer", "Crest", "18k Gold", "M",
         "converter", 350, False, "Standard", "Modern reissue of Crest line"),
        ("Sheaffer Legacy Heritage Black", "Sheaffer", "Legacy", "18k Gold", "M",
         "converter", 400, False, "Standard", "TD-style filling, inlaid nib, black lacquer"),
        ("Sheaffer Snorkel Admiral Burgundy", "Sheaffer", "Snorkel", "14k Gold", "M",
         "snorkel", 300, False, "Exclusive", "1953 two-tone burgundy-chrome, snorkel fill"),
        # Esterbrook (vintage)
        ("Esterbrook J Black", "Esterbrook", "J Series", "Steel", "M",
         "lever", 80, False, "Standard", "1940s workhorse, interchangeable Renew-Point nibs"),
        ("Esterbrook SJ Blue", "Esterbrook", "SJ Series", "Steel", "F",
         "lever", 70, False, "Standard", "Short J series, slim pocket pen"),
        ("Esterbrook Dollar Pen Red", "Esterbrook", "Dollar", "Steel", "M",
         "lever", 50, False, "Standard", "1930s economy pen, red marbled hard rubber"),
        # Wahl Eversharp
        ("Wahl Eversharp Skyline Green", "Sheaffer", "Skyline", "14k Gold (Flex)", "M",
         "lever", 350, False, "Exclusive", "1940s Deco design, Henry Dreyfuss, green stripe"),
        ("Wahl Eversharp Skyline Blue", "Sheaffer", "Skyline", "14k Gold", "F",
         "lever", 300, False, "Exclusive", "1940s streamlined design, blue stripe barrel"),
        ("Wahl Eversharp Doric Kashmir Green", "Sheaffer", "Doric", "14k Gold (Flex)", "M",
         "lever", 800, False, "Exclusive", "1930s Art Deco, twelve-sided, adjustable nib"),
        ("Wahl Eversharp Gold Seal Rosewood", "Sheaffer", "Gold Seal", "14k Gold (Flex)", "M",
         "lever", 450, False, "Exclusive", "1920s full-size, rosewood hard rubber, flex nib"),
        ("Wahl Eversharp Equipoised Black", "Sheaffer", "Equipoised", "14k Gold", "F",
         "lever", 250, False, "Exclusive", "1930s ringtop-style, balanced design"),
        # Conway Stewart
        ("Conway Stewart 100 Classic Blue", "Parker", "Conway Stewart", "18k Gold", "M",
         "converter", 550, False, "Standard", "British heritage brand, blue casein"),
        ("Conway Stewart Churchill Blue", "Parker", "Conway Stewart", "18k Gold", "B",
         "converter", 800, True, "Limited Edition", "Oversized cigar shape, blue marble resin"),
        # Moore
        ("Moore L-92 Black", "Parker", "Moore", "14k Gold (Flex)", "M",
         "lever", 350, False, "Exclusive", "1930s oversized lever-filler, flex nib"),
        # Conklin vintage
        ("Conklin Endura Rosewood", "Conklin", "Endura", "14k Gold (Flex)", "M",
         "lever", 300, False, "Exclusive", "1920s streamlined, rosewood hard rubber"),
        ("Conklin Nozac Toledo Blue", "Conklin", "Nozac", "14k Gold", "M",
         "piston", 400, False, "Exclusive", "1930s first American piston filler"),
        # Pelikan vintage
        ("Pelikan 100N Black-Green Vintage", "Pelikan", "100N", "14k Gold (Flex)", "M",
         "piston", 600, False, "Exclusive", "1937-1950s, green marbled celluloid, flex nib"),
        ("Pelikan 400NN Tortoiseshell", "Pelikan", "400NN", "14k Gold", "M",
         "piston", 350, False, "Exclusive", "1950s, tortoiseshell striped celluloid barrel"),
        # Parker vintage
        ("Parker 45 Gold Filled", "Parker", "45", "14k Gold", "F",
         "converter", 120, False, "Standard", "1960s modular pen, gold-filled cap"),
        ("Parker 61 Stratus Blue", "Parker", "61", "14k Gold", "M",
         "capillary", 250, False, "Exclusive", "1950s capillary fill system, no moving parts"),
        ("Parker Challenger Blue Pearl", "Parker", "Challenger", "14k Gold", "M",
         "button", 200, False, "Exclusive", "1930s streamline, blue pearl celluloid"),
        ("Parker Lady Duofold Red", "Parker", "Lady Duofold", "14k Gold", "F",
         "button", 350, False, "Exclusive", "1920s petite version, Chinese red hard rubber"),
    ]


def _nakaya_round3() -> list[tuple]:
    """10 additional Nakaya fountain pens."""
    return [
        ("Decapod Twist Kuro-Roiro", "Nakaya", "Decapod", "14k Gold", "M",
         "converter", 1600, False, "Standard", "Twisted faceted, deep black roiro urushi"),
        ("Dorsal Fin Version 1 Shu", "Nakaya", "Dorsal Fin", "14k Gold", "F",
         "converter", 1100, False, "Standard", "Vermillion urushi, original dorsal fin shape"),
        ("Neo Standard Aka-Tamenuri", "Nakaya", "Neo Standard", "14k Gold", "M",
         "converter", 900, False, "Standard", "Cigar shape, red tamenuri urushi"),
        ("Piccolo Midori-Tamenuri", "Nakaya", "Piccolo", "14k Gold", "F",
         "converter", 750, False, "Standard", "Compact green tamenuri finish"),
        ("Writer Araishu", "Nakaya", "Writer", "14k Gold", "M",
         "converter", 950, False, "Standard", "Rough vermillion texture urushi"),
        ("Naka-ai Writer Kuro-Tamenuri", "Nakaya", "Naka-ai", "14k Gold", "B",
         "converter", 1050, False, "Standard", "Mid-size, black tamenuri finish"),
        ("Ascending Dragon Maki-e", "Nakaya", "Ascending Dragon", "14k Gold", "M",
         "converter", 3500, True, "Limited Edition", "Maki-e dragon ascending clouds"),
        ("Dorsal Fin V2 Heki-Tamenuri", "Nakaya", "Dorsal Fin", "14k Gold", "F",
         "converter", 1250, False, "Standard", "Green-jade tamenuri urushi"),
        ("Long Cigar Kuro-Roiro", "Nakaya", "Cigar", "14k Gold", "M",
         "converter", 1000, False, "Standard", "Full-size cigar, deepest black roiro"),
        ("Portable Writer Aka-Tamenuri", "Nakaya", "Portable", "14k Gold", "F",
         "converter", 850, False, "Standard", "Compact travel pen, red tamenuri"),
    ]


def _conid_opus88_scribo_round3() -> list[tuple]:
    """14 additional independent/artisan brand pens — Conid, Opus 88, Scribo, BENU, Leonardo."""
    return [
        ("Conid Kingsize Regular", "Conid", "Kingsize", "14k Gold", "B",
         "bulkfiller", 950, False, "Standard", "Oversized Belgian bulkfiller"),
        ("Conid Giraffe", "Conid", "Giraffe", "14k Gold", "M",
         "bulkfiller", 750, False, "Standard", "Tall slim profile, titanium internals"),
        ("Opus 88 Flora", "Opus 88", "Flora", "Steel", "F",
         "eyedropper", 120, False, "Standard", "Floral pattern resin, JoWo nib"),
        ("Opus 88 Omar", "Opus 88", "Omar", "Steel", "M",
         "eyedropper", 110, False, "Standard", "Demonstrator eyedropper, large capacity"),
        ("Opus 88 Fantasia", "Opus 88", "Fantasia", "Steel", "B",
         "eyedropper", 100, False, "Standard", "Colorful marbled resin eyedropper"),
        ("Scribo Feel Borealis", "Scribo", "Feel", "18k Gold", "M",
         "piston", 550, False, "Standard", "Italian artisan, ebonite, aurora green"),
        ("Scribo La Dotta Sanguigna", "Scribo", "La Dotta", "18k Gold", "F",
         "piston", 700, True, "Limited Edition", "Bologna tribute, blood-red ebonite"),
        ("Scribo Piuma Aureo", "Scribo", "Piuma", "18k Gold", "M",
         "piston", 600, False, "Standard", "Lightweight ebonite, golden amber"),
        ("BENU Briolette Ocean Breeze", "BENU", "Briolette", "Steel", "F",
         "converter", 125, False, "Standard", "Blue shimmer resin, glow-in-the-dark"),
        ("BENU Talisman Autumn Leaves", "BENU", "Talisman", "Steel", "M",
         "converter", 140, True, "Limited Edition", "Autumn leaf resin with sparkle"),
        ("Leonardo Momento Zero Grande Pietra Marina", "Conklin", "Momento Zero", "Steel", "M",
         "converter", 200, False, "Standard", "Italian sea-stone blue resin, JoWo nib"),
        ("Leonardo Furore Blue Hawaii", "Conklin", "Furore", "Steel", "F",
         "converter", 85, False, "Standard", "Italian entry-level, vibrant blue resin"),
        ("Penlux Masterpiece Grande Blue Swirl", "BENU", "Masterpiece", "Steel", "M",
         "piston", 180, False, "Standard", "Taiwanese piston filler, blue swirl celluloid"),
        ("Nahvalur Original Plus Azurite", "BENU", "Original", "Steel", "M",
         "piston", 70, False, "Standard", "Blue shimmer resin, piston fill, great value"),
    ]


def _caran_dupont_gvfc_round3() -> list[tuple]:
    """18 additional Caran d'Ache, S.T. Dupont, and Graf von Faber-Castell pens."""
    return [
        # Caran d'Ache
        ("Léman Bicolor Saffron", "Caran d'Ache", "Léman", "18k Gold", "M",
         "converter", 700, False, "Standard", "Saffron lacquer, bicolor 18k nib"),
        ("Ecridor XS Retro", "Caran d'Ache", "Ecridor", "Steel", "F",
         "converter", 250, False, "Standard", "Compact pocket size, retro pattern"),
        ("Varius Rubracer", "Caran d'Ache", "Varius", "18k Gold", "M",
         "converter", 750, False, "Standard", "Rubber and silver barrel, 18k nib"),
        ("1010 Limited Edition Rose Gold", "Caran d'Ache", "1010", "18k Gold", "M",
         "converter", 1200, True, "Limited Edition", "Anniversary edition, rose gold trim"),
        # S.T. Dupont
        ("Ligne 2 Micro-Diamond", "S.T. Dupont", "Ligne 2", "18k Gold", "M",
         "converter", 1800, True, "Limited Edition", "Micro-diamond head pattern, gold dust"),
        ("Ligne 2 Guilloche Rose Gold", "S.T. Dupont", "Ligne 2", "18k Gold", "F",
         "converter", 1300, False, "Standard", "Rose gold finish, guilloche engraving"),
        ("Ligne 2 Windsor Duo", "S.T. Dupont", "Ligne 2", "14k Gold", "M",
         "converter", 750, False, "Standard", "Two-tone gold and palladium finish"),
        ("Elysée Black Lacquer", "S.T. Dupont", "Elysée", "14k Gold", "M",
         "converter", 600, False, "Standard", "Mid-range, black natural lacquer, classic shape"),
        ("Line D Eternity Medium", "S.T. Dupont", "Line D", "14k Gold", "M",
         "converter", 450, False, "Standard", "Natural lacquer, plated brass, medium size"),
        ("Maxijet Matte Black", "S.T. Dupont", "Maxijet", "Steel", "M",
         "converter", 200, False, "Standard", "Modern design, matte black lacquer"),
        # Graf von Faber-Castell
        ("Pen of the Year 2020 Sparta", "Graf von Faber-Castell", "Pen of the Year",
         "18k Gold", "M", "converter", 3500, True, "Limited Edition",
         "Annual LE, olive wood barrel, Spartan helmet motif"),
        ("Pen of the Year 2019 Samurai", "Graf von Faber-Castell", "Pen of the Year",
         "18k Gold", "F", "converter", 3800, True, "Limited Edition",
         "Annual LE, damascene steel, Japanese samurai armor"),
        ("Pen of the Year 2018 Imperium Romanum", "Graf von Faber-Castell", "Pen of the Year",
         "18k Gold", "M", "converter", 3200, True, "Limited Edition",
         "Annual LE, smoked oak barrel, Roman coin cap"),
        ("Classic Pernambuco", "Graf von Faber-Castell", "Classic",
         "18k Gold", "M", "converter", 500, False, "Standard",
         "Brazilian Pernambuco wood barrel, platinum fittings"),
        ("Classic Grenadilla", "Graf von Faber-Castell", "Classic",
         "18k Gold", "F", "converter", 480, False, "Standard",
         "African Grenadilla wood, platinum-plated trim"),
        ("Intuition Platino Ebony", "Graf von Faber-Castell", "Intuition",
         "18k Gold", "M", "converter", 650, False, "Standard",
         "Fluted ebony wood barrel, platinum-plated fittings"),
        ("Guilloche Olive Green", "Graf von Faber-Castell", "Guilloche",
         "18k Gold", "M", "converter", 350, False, "Standard",
         "Olive green resin, guilloche pattern"),
        ("Tamitio Rose", "Graf von Faber-Castell", "Tamitio",
         "Steel", "F", "converter", 210, False, "Standard",
         "Rose lacquer on metal barrel, entry luxury"),
    ]


def _cartier_round3() -> list[tuple]:
    """8 additional Cartier fountain pens."""
    return [
        ("Trinity de Cartier", "Cartier", "Trinity", "18k Gold", "M",
         "converter", 1300, False, "Standard", "Three-ring motif, palladium lacquer barrel"),
        ("Santos de Cartier Large Godron", "Cartier", "Santos", "18k Gold", "B",
         "converter", 1100, False, "Standard", "Godron-ribbed oversized barrel"),
        ("Diabolo de Cartier Black & Palladium", "Cartier", "Diabolo", "18k Gold", "F",
         "converter", 1250, False, "Standard", "Black composite, palladium fittings"),
        ("Louis Cartier Vertical Lines", "Cartier", "Louis Cartier", "18k Gold", "M",
         "converter", 1000, False, "Standard", "Vertical fluted pattern, platinum finish"),
        ("Pasha de Cartier Blue", "Cartier", "Pasha", "18k Gold", "M",
         "converter", 1600, True, "Limited Edition", "Blue lacquer, cabochon cap, limited"),
        ("Must de Cartier Gold Plated", "Cartier", "Must", "18k Gold", "F",
         "converter", 700, False, "Standard", "Gold-plated barrel, entry Cartier line"),
        ("Roadster Palladium", "Cartier", "Roadster", "18k Gold", "M",
         "converter", 1000, False, "Standard", "Automotive tonneau, palladium finish"),
        ("Happy Birthday Gold", "Cartier", "Happy Birthday", "18k Gold", "F",
         "converter", 500, False, "Standard", "Engraved gold-plated barrel, festive design"),
    ]


def _japanese_artisan_round3() -> list[tuple]:
    """12 additional Japanese artisan / maki-e art pens."""
    return [
        ("Namiki Emperor Kylin", "Namiki", "Emperor", "18k Gold", "M",
         "converter", 9000, True, "Limited Edition", "Taka maki-e kylin motif, large format"),
        ("Namiki Emperor Phoenix", "Namiki", "Emperor", "18k Gold", "B",
         "converter", 9500, True, "Limited Edition", "Taka maki-e phoenix, gold powder"),
        ("Namiki Yukari Bamboo", "Namiki", "Yukari", "18k Gold", "M",
         "converter", 2000, True, "Limited Edition", "Hira maki-e bamboo grove, raden"),
        ("Namiki Yukari Royale Kingfisher", "Namiki", "Yukari Royale", "18k Gold", "F",
         "converter", 4800, True, "Limited Edition", "Taka maki-e kingfisher bird, raden inlay"),
        ("Platinum Izumo Maki-e Dragon", "Platinum", "Izumo", "18k Gold", "M",
         "converter", 4000, True, "Limited Edition", "Togidashi maki-e dragon, ebonite body"),
        ("Platinum President Maki-e Pine", "Platinum", "President", "18k Gold", "B",
         "converter", 3500, True, "Limited Edition", "Pine tree togidashi maki-e"),
        ("Pilot Custom Urushi Maki-e Wave", "Pilot", "Custom Urushi", "18k Gold", "M",
         "converter", 4500, True, "Limited Edition", "Great wave Hokusai tribute, gold dust"),
        ("Namiki Chinkin Phoenix", "Namiki", "Chinkin", "18k Gold", "M",
         "converter", 4000, True, "Limited Edition", "Chinkin needle-point phoenix art"),
        ("Sailor King of Pen Maki-e Mount Fuji", "Sailor", "King of Pen", "21k Gold", "M",
         "converter", 5000, True, "Limited Edition", "Mount Fuji togidashi maki-e, sunrise"),
        ("Danitrio Takumi Sakura", "Namiki", "Takumi", "18k Gold", "F",
         "converter", 2500, True, "Limited Edition", "Cherry blossom maki-e, ebonite barrel"),
        ("Platinum Century Maki-e Wave", "Platinum", "#3776 Century", "14k Gold", "M",
         "converter", 1500, True, "Limited Edition", "Kanagawa wave maki-e, limited series"),
        ("Pilot Namiki Nippon Art Rabbit", "Pilot", "Nippon Art", "18k Gold", "M",
         "converter", 350, False, "Standard", "Affordable maki-e, rabbit and moon motif"),
    ]


def _esterbrook_round3() -> list[tuple]:
    """8 additional Esterbrook modern fountain pens."""
    return [
        ("Estie Oversize Sunflower", "Esterbrook", "Estie", "Steel", "M",
         "converter", 230, True, "Limited Edition", "Bright yellow oversize edition"),
        ("Estie Fantasy Nouveau Blush", "Esterbrook", "Estie", "Steel", "F",
         "converter", 200, True, "Limited Edition", "Art Nouveau blush pink pattern"),
        ("Camden Composition Gray", "Esterbrook", "Camden", "Steel", "M",
         "converter", 120, False, "Standard", "Gray marble composition resin"),
        ("JR Pocket Pen Capri Blue", "Esterbrook", "JR Pocket", "Steel", "F",
         "converter", 85, False, "Standard", "Compact pocket pen, Capri blue"),
        ("Estie Open Sesame", "Esterbrook", "Estie", "Steel", "M",
         "converter", 180, True, "Limited Edition", "Arabian Nights teal resin, gold trim"),
        ("Estie Oversize Rocky Top", "Esterbrook", "Estie", "Steel", "B",
         "converter", 240, True, "Limited Edition", "Smoky mountain-inspired grey marble"),
        ("Estie Pumpkin Spice", "Esterbrook", "Estie", "Steel", "M",
         "converter", 190, True, "Limited Edition", "Autumn orange swirl acrylic"),
        ("Estie Evergreen", "Esterbrook", "Estie", "Steel", "F",
         "converter", 180, False, "Standard", "Forest green classic pattern"),
    ]


def _additional_brands_round3() -> list[tuple]:
    """70 additional pens — filling gaps across all brands for 500+ total."""
    return [
        # Montblanc additional
        ("Meisterstueck 149 Diamond", "Montblanc", "Meisterstueck", "18k Gold", "M",
         "piston", 2200, True, "Limited Edition", "Diamond-set cap ring, platinum trim"),
        ("Meisterstueck Geometry Solitaire", "Montblanc", "Meisterstueck", "18k Gold", "F",
         "piston", 1700, True, "Limited Edition", "Geometric lacquer pattern, champagne gold"),
        ("Writers Edition Agatha Christie", "Montblanc", "Writers Edition", "18k Gold", "M",
         "piston", 1300, True, "Limited Edition", "2007 LE, green marbled resin, serpent clip"),
        ("Writers Edition Marcel Proust", "Montblanc", "Writers Edition", "18k Gold", "F",
         "piston", 1400, True, "Limited Edition", "1999 LE, sterling silver filigree"),
        ("Writers Edition F. Scott Fitzgerald", "Montblanc", "Writers Edition", "18k Gold", "M",
         "piston", 1350, True, "Limited Edition", "2020 LE, Art Deco champagne gold"),
        ("Writers Edition Rudyard Kipling", "Montblanc", "Writers Edition", "18k Gold", "B",
         "piston", 1150, True, "Limited Edition", "2019 LE, jungle green, bamboo clip"),
        ("StarWalker Blue Planet Doue", "Montblanc", "StarWalker", "14k Gold", "M",
         "converter", 820, False, "Standard", "Blue planet dome, metal and resin"),
        # Pelikan additional
        ("M800 Calculation of Infinity", "Pelikan", "Souveraen", "18k Gold", "M",
         "piston", 900, True, "Limited Edition", "Pi motif, transparent barrel section"),
        ("M600 Vibrant Orange", "Pelikan", "Souveraen", "14k Gold", "F",
         "piston", 420, True, "Limited Edition", "Vivid orange special edition stripes"),
        ("M800 Stone Garden Special Edition", "Pelikan", "Souveraen", "18k Gold", "B",
         "piston", 750, True, "Limited Edition", "Grey marbled stone pattern resin"),
        # Sailor additional
        ("Pro Gear Slim Fairy Tale Alice", "Sailor", "Pro Gear Slim", "14k Gold", "MF",
         "converter", 320, True, "Limited Edition", "Alice in Wonderland collaboration"),
        ("Pro Gear Slim Yukitsubaki", "Sailor", "Pro Gear Slim", "14k Gold", "F",
         "converter", 310, True, "Limited Edition", "Snow camellia white and pink resin"),
        ("1911 Standard Fresca", "Sailor", "1911", "14k Gold", "M",
         "converter", 260, True, "Limited Edition", "Fresh blue transparent resin"),
        ("Pro Gear Imperial Black", "Sailor", "Pro Gear", "21k Gold", "M",
         "converter", 380, False, "Standard", "All-black resin and black ion plating"),
        ("King of Pen Naginata Togi Cross-Point", "Sailor", "King of Pen", "21k Gold", "Stub",
         "converter", 1100, False, "Standard", "Specialty cross-point nib on KoP body"),
        # Pilot additional
        ("Custom 823 Clear", "Pilot", "Custom", "14k Gold", "B",
         "vacuum", 340, False, "Standard", "Fully clear demonstrator vacuum fill"),
        ("Vanishing Point Decimo Dark Blue", "Pilot", "Vanishing Point", "18k Gold", "M",
         "converter", 230, False, "Standard", "Slim retractable, dark blue metallic"),
        ("Custom 74 Demonstrator Clear", "Pilot", "Custom", "14k Gold", "M",
         "converter", 180, False, "Standard", "Clear demonstrator with Con-70"),
        ("Namiki Yukari No. 20 Emperor Tiger", "Namiki", "Emperor", "18k Gold", "M",
         "converter", 12000, True, "Limited Edition", "Large maki-e tiger, taka maki-e art"),
        # Platinum additional
        ("Century #3776 Laurel Green", "Platinum", "#3776 Century", "14k Gold", "M",
         "converter", 200, True, "Limited Edition", "Dark green translucent resin"),
        ("Century #3776 Coarse Nib", "Platinum", "#3776 Century", "14k Gold", "B",
         "converter", 180, False, "Standard", "Broad/coarse nib for kanji writing"),
        ("Procyon Dark Citrus", "Platinum", "Procyon", "Steel", "F",
         "converter", 85, False, "Standard", "Orange aluminum barrel, snap cap"),
        # Parker/Waterman additional
        ("Parker Sonnet Metal & Pearl", "Parker", "Sonnet", "18k Gold", "M",
         "converter", 350, False, "Standard", "Mother of pearl inlay, palladium trim"),
        ("Parker Duofold Centennial Amber", "Parker", "Duofold", "18k Gold", "M",
         "converter", 600, True, "Limited Edition", "Amber Check acrylic barrel"),
        ("Waterman Expert Obsession Blue", "Waterman", "Expert", "Steel", "M",
         "converter", 130, False, "Standard", "Deep blue lacquer, chrome trim"),
        # Aurora additional
        ("88 Sole Limited", "Aurora", "88", "18k Gold", "M",
         "piston", 800, True, "Limited Edition", "Sun-themed celluloid, 888-piece annual"),
        ("Optima 365 Burgundy", "Aurora", "Optima", "18k Gold", "F",
         "piston", 650, True, "Limited Edition", "365-piece annual, deep burgundy celluloid"),
        # Lamy additional
        ("2000 Titanium", "Lamy", "2000", "14k Gold", "M",
         "piston", 900, True, "Limited Edition", "Titanium barrel variant of the 2000"),
        ("Safari Cream", "Lamy", "Safari", "Steel", "F",
         "converter", 70, True, "Limited Edition", "2023 annual limited cream color"),
        ("Al-Star Pacific Blue", "Lamy", "Al-Star", "Steel", "M",
         "converter", 40, False, "Standard", "Anodized aluminum, Pacific blue"),
        # TWSBI additional
        ("TWSBI Diamond Mini Classic", "TWSBI", "Diamond Mini", "Steel", "F",
         "piston", 55, False, "Standard", "Compact piston filler, mini demonstrator"),
        ("TWSBI GO Smoke", "TWSBI", "GO", "Steel", "M",
         "piston", 20, False, "Standard", "Budget spring-loaded piston, smoke barrel"),
        # Visconti additional
        ("Homo Sapiens Magma", "Visconti", "Homo Sapiens", "Palladium", "M",
         "vacuum", 900, True, "Limited Edition", "Red-orange lava, volcanic motif"),
        ("Homo Sapiens Skylight", "Visconti", "Homo Sapiens", "Palladium", "F",
         "vacuum", 820, True, "Limited Edition", "Light blue lava resin barrel"),
        ("Opera Master Crimson Tide", "Visconti", "Opera Master", "18k Gold", "B",
         "vacuum", 1300, True, "Limited Edition", "Crimson swirl celluloid"),
        ("Mirage Amber", "Visconti", "Mirage", "Steel", "M",
         "converter", 150, False, "Standard", "Entry-level Visconti, amber resin"),
        # Nakaya additional
        ("Writer Shu", "Nakaya", "Writer", "14k Gold", "M",
         "converter", 1000, False, "Standard", "Full-size cigar shape, vermillion urushi"),
        ("Dorsal Fin V2 Midori-Tamenuri Green", "Nakaya", "Dorsal Fin", "14k Gold", "B",
         "converter", 1300, False, "Standard", "Green tamenuri dorsal fin shape"),
        # Conid/Independent additional
        ("Conid Bulkfiller Kingsize Demonstrator", "Conid", "Kingsize", "14k Gold", "M",
         "bulkfiller", 1000, True, "Limited Edition", "Clear oversized Belgian demonstrator"),
        ("Opus 88 Picnic Blue", "Opus 88", "Picnic", "Steel", "F",
         "eyedropper", 70, False, "Standard", "Compact pocket eyedropper, blue resin"),
        # Caran d'Ache additional
        ("Léman Cashmere Brown", "Caran d'Ache", "Léman", "18k Gold", "M",
         "converter", 700, False, "Standard", "Warm brown lacquer, gold-plated trim"),
        ("Varius Ceramic Black", "Caran d'Ache", "Varius", "18k Gold", "F",
         "converter", 800, False, "Standard", "High-tech ceramic barrel, 18k bicolor nib"),
        # S.T. Dupont additional
        ("Ligne 2 Fire Head Red", "S.T. Dupont", "Ligne 2", "18k Gold", "M",
         "converter", 1100, True, "Limited Edition", "Red Chinese lacquer, fire head motif"),
        ("Liberté Brushed Copper", "S.T. Dupont", "Liberté", "14k Gold", "M",
         "converter", 580, False, "Standard", "Brushed copper finish, modern design"),
        # Graf von Faber-Castell additional
        ("Pen of the Year 2024 Venetian Carnival", "Graf von Faber-Castell", "Pen of the Year",
         "18k Gold", "M", "converter", 3600, True, "Limited Edition",
         "Annual LE, Murano glass cap, Venetian mask motif"),
        ("Guilloche Cognac", "Graf von Faber-Castell", "Guilloche",
         "18k Gold", "F", "converter", 350, False, "Standard",
         "Warm cognac brown resin, guilloche pattern"),
        # Cartier additional
        ("Santos de Cartier Gold Finish", "Cartier", "Santos", "18k Gold", "M",
         "converter", 1200, False, "Standard", "Gold-finish barrel, C de Cartier motif"),
        ("Diabolo Onyx", "Cartier", "Diabolo", "18k Gold", "F",
         "converter", 1400, True, "Limited Edition", "Onyx stone cap, platinum finish"),
        # Vintage additional
        ("Parker Lucky Curve Black Giant", "Parker", "Lucky Curve", "14k Gold (Flex)", "M",
         "button", 500, False, "Exclusive", "1920s oversized, black hard rubber, flex nib"),
        ("Sheaffer Balance Aspen", "Sheaffer", "Balance", "14k Gold", "M",
         "lever", 250, False, "Exclusive", "1930s streamline, pearl and black celluloid"),
        ("Sheaffer Valiant Touchdown Green", "Sheaffer", "Touchdown", "14k Gold", "F",
         "touchdown", 200, False, "Exclusive", "1950s touchdown filling, green barrel"),
        ("Pelikan 140 Green-Black Vintage", "Pelikan", "140", "14k Gold", "F",
         "piston", 200, False, "Exclusive", "1950s small piston filler, classic stripes"),
        # Japanese artisan additional
        ("Namiki Chinkin Dragonfly", "Namiki", "Chinkin", "18k Gold", "F",
         "converter", 3200, True, "Limited Edition", "Chinkin dragonfly, gold accents"),
        ("Platinum Izumo Maki-e Samurai", "Platinum", "Izumo", "18k Gold", "M",
         "converter", 4500, True, "Limited Edition", "Togidashi maki-e samurai armor"),
        ("Pilot Nippon Art Mt. Fuji", "Pilot", "Nippon Art", "18k Gold", "M",
         "converter", 380, False, "Standard", "Affordable maki-e, Mount Fuji scene"),
        # Esterbrook additional
        ("Estie Rocky Mountain Highline", "Esterbrook", "Estie", "Steel", "M",
         "converter", 200, True, "Limited Edition", "Mountain-inspired grey marble acrylic"),
        ("Estie Blackberry", "Esterbrook", "Estie", "Steel", "F",
         "converter", 180, False, "Standard", "Dark purple classic resin pattern"),
        # More luxury
        ("Cross Townsend Lustrous Chrome", "Parker", "Townsend", "18k Gold", "M",
         "converter", 350, False, "Standard", "American luxury, chrome barrel, smooth nib"),
        ("Cross Peerless 125 Obsidian Black", "Parker", "Peerless", "18k Gold", "M",
         "converter", 600, True, "Limited Edition", "Cross anniversary, lacquer barrel"),
        ("Faber-Castell e-motion Pearwood Brown", "Lamy", "e-motion", "Steel", "M",
         "converter", 100, False, "Standard", "Pearwood barrel, chrome trim, budget luxury"),
        ("Diplomat Aero Black", "Conklin", "Aero", "Steel", "M",
         "converter", 200, False, "Standard", "German-made, aircraft-inspired barrel shape"),
        ("Diplomat Excellence A2 Evergreen Gold", "Conklin", "Excellence", "Steel", "F",
         "converter", 150, False, "Standard", "Guilloche evergreen lacquer, gold trim"),
        ("Kaweco Sport Classic Green", "TWSBI", "Sport", "Steel", "M",
         "converter", 25, False, "Standard", "Pocket pen icon, octagonal cap, snap closure"),
        ("Kaweco AL Sport Anthracite", "TWSBI", "AL Sport", "Steel", "F",
         "converter", 65, False, "Standard", "Aluminum body pocket pen, dark grey"),
        ("Kaweco Dia2 Chrome", "TWSBI", "Dia2", "Steel", "M",
         "converter", 110, False, "Standard", "Full-size Kaweco, chrome accents"),
        ("Hongdian N1 Black Forest", "BENU", "N1", "Steel", "EF",
         "converter", 20, False, "Standard", "Chinese budget pen, metal body, Iridium Point"),
        ("Pineider La Grande Bellezza Gemstones Lapis", "Conklin", "La Grande Bellezza", "14k Gold", "M",
         "converter", 400, True, "Limited Edition", "Italian luxury, lapis blue resin"),
    ]


# ---------------------------------------------------------------------------
# VARIANT COVERAGE EXPANSION — ~100 pens focused on nib/color variants
# ---------------------------------------------------------------------------


def _montblanc_nib_variants() -> list[tuple]:
    """14 Montblanc nib-size and model variants — Meisterstueck 149/146/145, StarWalker, Heritage, Writers Edition."""
    return [
        # Meisterstueck 149 nib variants
        ("Meisterstueck 149 EF Nib", "Montblanc", "Meisterstueck", "18k Gold", "EF",
         "piston", 950, False, "Standard", "Flagship with extra-fine nib, precise line"),
        ("Meisterstueck 149 F Nib", "Montblanc", "Meisterstueck", "18k Gold", "F",
         "piston", 950, False, "Standard", "Flagship with fine nib, everyday writer"),
        ("Meisterstueck 149 B Nib", "Montblanc", "Meisterstueck", "18k Gold", "B",
         "piston", 950, False, "Standard", "Flagship with broad nib, expressive line"),
        ("Meisterstueck 149 BB Nib", "Montblanc", "Meisterstueck", "18k Gold", "BB",
         "piston", 1000, False, "Standard", "Flagship with double-broad nib, rare width"),
        ("Meisterstueck 149 OB Nib", "Montblanc", "Meisterstueck", "18k Gold", "OB",
         "piston", 1050, False, "Standard", "Oblique broad nib, angled for right-handers"),
        ("Meisterstueck 149 OBB Nib", "Montblanc", "Meisterstueck", "18k Gold", "OBB",
         "piston", 1100, False, "Standard", "Oblique double-broad, rarest standard nib option"),
        # Meisterstueck 146 nib variants
        ("Meisterstueck 146 Le Grand EF Nib", "Montblanc", "Meisterstueck", "14k Gold", "EF",
         "piston", 750, False, "Standard", "Mid-size classic, extra-fine nib"),
        ("Meisterstueck 146 Le Grand B Nib", "Montblanc", "Meisterstueck", "14k Gold", "B",
         "piston", 750, False, "Standard", "Mid-size classic, broad nib"),
        # Meisterstueck 145 nib variants
        ("Meisterstueck 145 Classique F Nib", "Montblanc", "Meisterstueck", "14k Gold", "F",
         "converter", 580, False, "Standard", "Slim profile, fine nib for detail work"),
        ("Meisterstueck 145 Classique B Nib", "Montblanc", "Meisterstueck", "14k Gold", "B",
         "converter", 580, False, "Standard", "Slim profile, broad nib for signatures"),
        # StarWalker / Heritage / Writers Edition variants
        ("StarWalker Midnight Black", "Montblanc", "StarWalker", "14k Gold", "B",
         "converter", 680, False, "Standard", "Midnight black resin, floating MB dome"),
        ("Heritage Rouge et Noir Spider Metamorphosis", "Montblanc", "Heritage", "14k Gold", "F",
         "piston", 950, True, "Limited Edition", "Spider web pattern, black/red lacquer"),
        ("Writers Edition Ernest Hemingway", "Montblanc", "Writers Edition", "18k Gold", "M",
         "piston", 3500, True, "Limited Edition", "1992 inaugural LE, orange/brown, most sought after"),
        ("Writers Edition Homage to Shakespeare", "Montblanc", "Writers Edition", "18k Gold", "F",
         "piston", 1200, True, "Limited Edition", "2016 LE, feather-cut cap, vermeil accents"),
    ]


def _pelikan_stripe_nib_variants() -> list[tuple]:
    """14 Pelikan stripe color and nib-size variants — M800/M1000/M400/M600."""
    return [
        # M800 stripe colors with different nibs
        ("Souveraen M800 Green-Black EF Nib", "Pelikan", "Souveraen", "18k Gold", "EF",
         "piston", 550, False, "Standard", "Classic green stripes, extra-fine nib"),
        ("Souveraen M800 Green-Black F Nib", "Pelikan", "Souveraen", "18k Gold", "F",
         "piston", 550, False, "Standard", "Classic green stripes, fine nib"),
        ("Souveraen M800 Green-Black B Nib", "Pelikan", "Souveraen", "18k Gold", "B",
         "piston", 550, False, "Standard", "Classic green stripes, broad nib"),
        ("Souveraen M800 Red-Black F Nib", "Pelikan", "Souveraen", "18k Gold", "F",
         "piston", 580, False, "Standard", "Red tortoiseshell stripes, fine nib"),
        ("Souveraen M800 Burnt Orange M Nib", "Pelikan", "Souveraen", "18k Gold", "M",
         "piston", 680, True, "Limited Edition", "2015 SE, vivid burnt orange stripes, medium nib"),
        # M1000 nib variants
        ("Souveraen M1000 EF Nib", "Pelikan", "Souveraen", "18k Gold", "EF",
         "piston", 750, False, "Standard", "Largest Souveraen with extra-fine nib, rare combo"),
        ("Souveraen M1000 F Nib", "Pelikan", "Souveraen", "18k Gold", "F",
         "piston", 750, False, "Standard", "Oversize nib in fine, great line variation"),
        ("Souveraen M1000 M Nib", "Pelikan", "Souveraen", "18k Gold", "M",
         "piston", 750, False, "Standard", "Oversize medium nib, buttery smooth writer"),
        # M400/M600 smaller sizes for smaller hands
        ("Souveraen M400 Green-Black M Nib", "Pelikan", "Souveraen", "14k Gold", "M",
         "piston", 350, False, "Standard", "Compact size ideal for smaller hands, green stripes"),
        ("Souveraen M400 Blue-Black EF Nib", "Pelikan", "Souveraen", "14k Gold", "EF",
         "piston", 350, False, "Standard", "Blue stripes, compact size, extra-fine nib"),
        ("Souveraen M600 Black M Nib", "Pelikan", "Souveraen", "14k Gold", "M",
         "piston", 380, False, "Standard", "Full-size all-black, gold trim, medium nib"),
        ("Souveraen M600 Green-Black EF Nib", "Pelikan", "Souveraen", "14k Gold", "EF",
         "piston", 380, False, "Standard", "Classic green stripes, extra-fine nib"),
        ("Souveraen M600 Red-White F Nib", "Pelikan", "Souveraen", "14k Gold", "F",
         "piston", 430, True, "Limited Edition", "Red and white SE stripes, fine nib"),
        ("Souveraen M400 Tortoiseshell Red F Nib", "Pelikan", "Souveraen", "14k Gold", "F",
         "piston", 360, False, "Standard", "Red tortoiseshell compact, fine nib"),
    ]


def _sailor_nib_specialty_variants() -> list[tuple]:
    """16 Sailor nib type variants — Pro Gear, KoP, 1911 with specialty and standard nibs."""
    return [
        # Pro Gear nib variants
        ("Pro Gear Black MF Nib", "Sailor", "Pro Gear", "21k Gold", "MF",
         "converter", 350, False, "Standard", "Flat-top, medium-fine for detailed writing"),
        ("Pro Gear Black B Nib", "Sailor", "Pro Gear", "21k Gold", "B",
         "converter", 350, False, "Standard", "Flat-top, broad nib for bold strokes"),
        ("Pro Gear Music Nib", "Sailor", "Pro Gear", "21k Gold", "Music",
         "converter", 480, False, "Standard", "Triple-tine music nib, wet line variation"),
        ("Pro Gear Zoom Nib Black", "Sailor", "Pro Gear", "21k Gold", "Zoom",
         "converter", 480, False, "Standard", "Zoom nib, line varies with writing speed"),
        # King of Pen nib variants
        ("King of Pen Black B Nib", "Sailor", "King of Pen", "21k Gold", "B",
         "converter", 850, False, "Standard", "Oversized flagship with broad nib"),
        ("King of Pen Black MF Nib", "Sailor", "King of Pen", "21k Gold", "MF",
         "converter", 850, False, "Standard", "Oversized with medium-fine nib"),
        # 1911 nib variants
        ("1911 Large Black F Nib", "Sailor", "1911", "21k Gold", "F",
         "converter", 400, False, "Standard", "Classic cigar shape, fine 21k nib"),
        ("1911 Large Black B Nib", "Sailor", "1911", "21k Gold", "B",
         "converter", 400, False, "Standard", "Classic cigar shape, broad 21k nib"),
        # Specialty nib grinds
        ("1911 Large Cross Point Nib", "Sailor", "1911", "21k Gold", "Cross Point",
         "converter", 800, False, "Standard", "Dual-direction cross-point nib, writes two line widths"),
        ("1911 Large Naginata Togi MF", "Sailor", "1911", "21k Gold", "Naginata Togi",
         "converter", 900, False, "Standard", "Traditional naginata grind, line variation with angle"),
        ("Pro Gear Naginata Concord", "Sailor", "Pro Gear", "21k Gold", "Naginata Concord",
         "converter", 1050, False, "Standard", "Specialty Concord nib, dual tipping points"),
        ("1911 Large Long-Medium Nib", "Sailor", "1911", "21k Gold", "Long-Medium",
         "converter", 500, False, "Standard", "Extended tipping for smoother, wetter medium line"),
        ("1911 Large Long-Fine Nib", "Sailor", "1911", "21k Gold", "Long-Fine",
         "converter", 500, False, "Standard", "Extended tipping for smoother fine writing"),
        ("Pro Gear Naginata Emperor", "Sailor", "Pro Gear", "21k Gold", "Naginata Emperor",
         "converter", 1200, False, "Standard", "Premium naginata grind, maximum line variation"),
        ("Pro Gear King Cobra Cross-Point", "Sailor", "Pro Gear", "21k Gold", "Cross Point",
         "converter", 550, False, "Standard", "Cross-point specialty, two writing angles"),
        ("1911 Large Fude Nib", "Sailor", "1911", "21k Gold", "Fude",
         "converter", 420, False, "Standard", "Bent fude nib for calligraphy and sketching"),
    ]


def _pilot_nib_color_variants() -> list[tuple]:
    """14 Pilot nib and color variants — Custom 823, Heritage 912, Vanishing Point."""
    return [
        # Custom 823 nib variants
        ("Custom 823 Amber FA Nib", "Pilot", "Custom", "14k Gold (Soft)", "FA",
         "vacuum", 350, False, "Standard", "Vacuum-fill with falcon soft nib, line variation"),
        ("Custom 823 Amber B Nib", "Pilot", "Custom", "14k Gold", "B",
         "vacuum", 320, False, "Standard", "Vacuum-fill with broad nib, smooth writer"),
        ("Custom 823 Clear EF Nib", "Pilot", "Custom", "14k Gold", "EF",
         "vacuum", 340, False, "Standard", "Clear demonstrator with extra-fine nib"),
        # Custom Heritage 912 specialty nibs
        ("Custom Heritage 912 FA Nib", "Pilot", "Custom Heritage", "14k Gold (Soft)", "FA",
         "converter", 260, False, "Standard", "Falcon soft nib on 912 body, flexible writing"),
        ("Custom Heritage 912 PO Nib", "Pilot", "Custom Heritage", "14k Gold", "PO",
         "converter", 250, False, "Standard", "Posting nib, ultra-fine for accounting"),
        ("Custom Heritage 912 WA Nib", "Pilot", "Custom Heritage", "14k Gold", "WA",
         "converter", 250, False, "Standard", "Waverly upturned nib, skip-free starts"),
        ("Custom Heritage 912 SU Nib", "Pilot", "Custom Heritage", "14k Gold", "SU",
         "converter", 250, False, "Standard", "Stub nib, italic line variation for calligraphy"),
        # Vanishing Point color variants
        ("Vanishing Point Blue Carbonesque", "Pilot", "Vanishing Point", "18k Gold", "F",
         "converter", 260, False, "Standard", "Blue carbon fiber weave, retractable 18k nib"),
        ("Vanishing Point Decimo Champagne M", "Pilot", "Vanishing Point", "18k Gold", "M",
         "converter", 220, False, "Standard", "Slim Decimo in champagne, medium 18k nib"),
        ("Vanishing Point Decimo Light Blue", "Pilot", "Vanishing Point", "18k Gold", "F",
         "converter", 220, False, "Standard", "Slim Decimo in light blue, feminine design"),
        ("Vanishing Point Raden Water Surface", "Pilot", "Vanishing Point", "18k Gold", "M",
         "converter", 550, True, "Limited Edition", "Raden abalone inlay, water surface pattern"),
        ("Vanishing Point Raden Stripes", "Pilot", "Vanishing Point", "18k Gold", "F",
         "converter", 520, True, "Limited Edition", "Raden abalone striped inlay pattern"),
        ("Vanishing Point Metallic Blue", "Pilot", "Vanishing Point", "18k Gold", "M",
         "converter", 210, False, "Standard", "Metallic blue lacquer, classic VP design"),
        ("Vanishing Point Burgundy", "Pilot", "Vanishing Point", "18k Gold", "F",
         "converter", 200, False, "Standard", "Deep burgundy lacquer, gold accents"),
    ]


def _lamy_safari_alstar_variants() -> list[tuple]:
    """10 Lamy Safari/Al-Star/2000 annual and color variants."""
    return [
        # Safari annual special editions
        ("Safari Candy Violet", "Lamy", "Safari", "Steel", "M",
         "converter", 75, True, "Limited Edition", "2020 Candy series, violet translucent"),
        ("Safari Candy Mango", "Lamy", "Safari", "Steel", "F",
         "converter", 75, True, "Limited Edition", "2020 Candy series, mango translucent"),
        ("Safari Terra Red", "Lamy", "Safari", "Steel", "M",
         "converter", 70, True, "Limited Edition", "2024 annual limited color, earth red"),
        ("Safari Strawberry", "Lamy", "Safari", "Steel", "F",
         "converter", 70, True, "Limited Edition", "2022 annual limited color, strawberry pink"),
        ("Safari Charcoal", "Lamy", "Safari", "Steel", "M",
         "converter", 30, False, "Standard", "Classic charcoal grey, popular starter pen"),
        # Al-Star variants
        ("Al-Star Tourmaline", "Lamy", "Al-Star", "Steel", "F",
         "converter", 45, True, "Limited Edition", "2020 annual limited, tourmaline green"),
        ("Al-Star Cosmic", "Lamy", "Al-Star", "Steel", "M",
         "converter", 50, True, "Limited Edition", "2023 annual limited, cosmic blue-purple"),
        # 2000 additional nibs
        ("2000 Makrolon F Nib", "Lamy", "2000", "14k Gold", "F",
         "piston", 350, False, "Standard", "Bauhaus icon with fine hooded nib"),
        ("2000 Makrolon B Nib", "Lamy", "2000", "14k Gold", "B",
         "piston", 350, False, "Standard", "Bauhaus icon with broad hooded nib"),
        ("2000 Makrolon OB Nib", "Lamy", "2000", "14k Gold", "OB",
         "piston", 380, False, "Standard", "Oblique broad variant, smoother for angled writing"),
    ]


def _twsbi_kaweco_affordable_variants() -> list[tuple]:
    """14 TWSBI and Kaweco color variants — hugely popular with new collectors."""
    return [
        # TWSBI Eco color variants
        ("TWSBI Eco Cement Grey", "TWSBI", "Eco", "Steel", "M",
         "piston", 35, False, "Standard", "Cement grey demonstrator, subtle colorway"),
        ("TWSBI Eco Coral", "TWSBI", "Eco", "Steel", "F",
         "piston", 40, True, "Limited Edition", "Coral pink limited demonstrator"),
        ("TWSBI Eco Turquoise", "TWSBI", "Eco", "Steel", "EF",
         "piston", 35, False, "Standard", "Turquoise barrel, popular entry pen"),
        ("TWSBI Eco Pastel Blue", "TWSBI", "Eco", "Steel", "M",
         "piston", 35, False, "Standard", "Soft pastel blue demonstrator"),
        # TWSBI Diamond 580 colors
        ("TWSBI Diamond 580ALR Purple", "TWSBI", "Diamond 580", "Steel", "F",
         "piston", 70, True, "Limited Edition", "Purple aluminum ring demonstrator"),
        ("TWSBI Diamond 580 Prussian Blue", "TWSBI", "Diamond 580", "Steel", "M",
         "piston", 65, True, "Limited Edition", "Deep Prussian blue limited edition"),
        # TWSBI Vac700R colors
        ("TWSBI Vac700R Smoke", "TWSBI", "Vac700R", "Steel", "F",
         "vacuum", 65, False, "Standard", "Smoke-tinted barrel, vacuum fill, large capacity"),
        ("TWSBI Vac700R Iris", "TWSBI", "Vac700R", "Steel", "EF",
         "vacuum", 75, True, "Limited Edition", "Rainbow plated trim with extra-fine nib"),
        # Kaweco Sport color variants
        ("Kaweco Sport Classic White", "Kaweco", "Sport", "Steel", "F",
         "converter", 25, False, "Standard", "Clean white octagonal pocket pen"),
        ("Kaweco Sport Classic Red", "Kaweco", "Sport", "Steel", "M",
         "converter", 25, False, "Standard", "Bright red classic pocket pen"),
        ("Kaweco Sport Frosted Pitaya", "Kaweco", "Sport", "Steel", "F",
         "converter", 30, False, "Standard", "Frosted pink translucent resin"),
        ("Kaweco Sport Frosted Calligraphy Natural Coconut", "Kaweco", "Sport", "Steel", "Stub",
         "converter", 30, False, "Standard", "Coconut white frosted with 1.1mm stub nib"),
        ("Kaweco Classic Sport Green", "Kaweco", "Classic Sport", "Steel", "M",
         "converter", 30, False, "Standard", "Classic octagonal design, racing green"),
        ("Kaweco Supra Brass", "Kaweco", "Supra", "Steel", "M",
         "converter", 120, False, "Standard", "Extendable brass pocket pen, develops patina"),
    ]


def _platinum_color_variants() -> list[tuple]:
    """8 Platinum #3776 Century color variants."""
    return [
        ("Century #3776 Bourgogne B Nib", "Platinum", "#3776 Century", "14k Gold", "B",
         "converter", 180, False, "Standard", "Deep red resin, broad nib for signatures"),
        ("Century #3776 Laurel Green F Nib", "Platinum", "#3776 Century", "14k Gold", "F",
         "converter", 200, True, "Limited Edition", "Dark green translucent, fine nib"),
        ("Century #3776 Nice Lavande F Nib", "Platinum", "#3776 Century", "14k Gold", "F",
         "converter", 200, True, "Limited Edition", "Lavender translucent, fine nib"),
        ("Century #3776 Black Diamond EF Nib", "Platinum", "#3776 Century", "14k Gold", "EF",
         "converter", 180, False, "Standard", "Flagship black with extra-fine nib"),
        ("Century #3776 Chartres Blue B Nib", "Platinum", "#3776 Century", "14k Gold", "B",
         "converter", 180, False, "Standard", "Translucent blue with broad nib"),
        ("Century #3776 Chartres Blue M Nib", "Platinum", "#3776 Century", "14k Gold", "M",
         "converter", 180, False, "Standard", "Translucent blue, most popular nib size"),
        ("Century #3776 Nice Pur Purple", "Platinum", "#3776 Century", "14k Gold", "M",
         "converter", 200, True, "Limited Edition", "Purple translucent resin, limited release"),
        ("Century #3776 Shiun Purple Cloud", "Platinum", "#3776 Century", "14k Gold", "MF",
         "converter", 380, True, "Limited Edition", "Purple cloud maki-e, dealer exclusive, MF nib"),
    ]


def _visconti_van_gogh_homo_sapiens_variants() -> list[tuple]:
    """8 Visconti Homo Sapiens and Van Gogh series variants."""
    return [
        ("Homo Sapiens Bronze Age F Nib", "Visconti", "Homo Sapiens", "Palladium", "F",
         "vacuum", 750, False, "Standard", "Basaltic lava, fine dreamtouch palladium nib"),
        ("Homo Sapiens Bronze Age EF Nib", "Visconti", "Homo Sapiens", "Palladium", "EF",
         "vacuum", 750, False, "Standard", "Basaltic lava, extra-fine dreamtouch nib"),
        ("Homo Sapiens Dark Age M Nib", "Visconti", "Homo Sapiens", "Palladium", "M",
         "vacuum", 800, False, "Standard", "Matte black lava, medium dreamtouch nib"),
        ("Van Gogh Almond Blossoms", "Visconti", "Van Gogh", "Steel", "F",
         "converter", 290, False, "Standard", "Light blue/white resin, almond branch motif"),
        ("Van Gogh The Bedroom", "Visconti", "Van Gogh", "Steel", "M",
         "converter", 290, False, "Standard", "Warm amber/blue resin, bedroom at Arles"),
        ("Van Gogh Portrait in Blue", "Visconti", "Van Gogh", "Steel", "F",
         "converter", 290, False, "Standard", "Blue/green resin, self-portrait palette"),
        ("Van Gogh Red Vineyard", "Visconti", "Van Gogh", "Steel", "M",
         "converter", 290, False, "Standard", "Red/amber resin, vineyard painting tribute"),
        ("Homo Sapiens Skylight F Nib", "Visconti", "Homo Sapiens", "Palladium", "F",
         "vacuum", 820, True, "Limited Edition", "Light blue lava, fine nib variant"),
    ]


def _aurora_parker_waterman_variants() -> list[tuple]:
    """10 Aurora, Parker, and Waterman variants."""
    return [
        # Aurora Optima / 88 variants
        ("Optima Auroloide Burgundy F Nib", "Aurora", "Optima", "18k Gold", "F",
         "piston", 550, False, "Standard", "Classic burgundy auroloide, fine nib"),
        ("Optima Auroloide Green B Nib", "Aurora", "Optima", "18k Gold", "B",
         "piston", 560, False, "Standard", "Classic green auroloide, broad nib"),
        ("88 Black Mamba F Nib", "Aurora", "88", "18k Gold", "F",
         "piston", 600, False, "Standard", "Classic 88 with fine nib, Italian craftmanship"),
        ("88 Black Mamba B Nib", "Aurora", "88", "18k Gold", "B",
         "piston", 600, False, "Standard", "Classic 88 with broad nib, wet writer"),
        # Parker Duofold / Sonnet variants
        ("Duofold Centennial Blue-Black", "Parker", "Duofold", "18k Gold", "F",
         "converter", 560, False, "Standard", "Blue and black acrylic, fine 18k nib"),
        ("Duofold Centennial Ivory-Black", "Parker", "Duofold", "18k Gold", "M",
         "converter", 570, False, "Standard", "Ivory and black acrylic, classic elegance"),
        ("Sonnet Matte Black Gold Trim", "Parker", "Sonnet", "18k Gold", "M",
         "converter", 300, False, "Standard", "Matte black lacquer, premium line"),
        # Waterman Expert / Carene variants
        ("Waterman Expert Black Gold Trim", "Waterman", "Expert", "Steel", "F",
         "converter", 110, False, "Standard", "Black lacquer, gold trim, reliable daily writer"),
        ("Waterman Carene Vivid Blue", "Waterman", "Carene", "18k Gold", "M",
         "converter", 370, False, "Standard", "Vivid blue lacquer, boat-hull silhouette"),
        ("Waterman Carene Gunmetal", "Waterman", "Carene", "18k Gold", "F",
         "converter", 350, False, "Standard", "Gunmetal grey lacquer, modern elegance"),
    ]


# ---------------------------------------------------------------------------
# Assemble full catalog
# ---------------------------------------------------------------------------


def get_curated_catalog() -> list[dict]:
    """Return the full curated fountain pen catalog as a list of dicts.

    Each dict has keys: name, brand, model_line, nib_material, nib_size,
    filling_system, price_eur, is_limited, rarity, notes.
    """
    all_tuples: list[tuple] = []
    all_tuples.extend(_montblanc_pens())
    all_tuples.extend(_pelikan_pens())
    all_tuples.extend(_sailor_pens())
    all_tuples.extend(_pilot_pens())
    all_tuples.extend(_lamy_pens())
    all_tuples.extend(_visconti_pens())
    all_tuples.extend(_aurora_pens())
    all_tuples.extend(_nakaya_pens())
    all_tuples.extend(_vintage_pens())
    all_tuples.extend(_japanese_artisan_pens())
    all_tuples.extend(_cartier_pens())
    all_tuples.extend(_st_dupont_pens())
    all_tuples.extend(_caran_dache_pens())
    all_tuples.extend(_graf_von_faber_castell_pens())
    all_tuples.extend(_platinum_pens())
    all_tuples.extend(_parker_modern_pens())
    all_tuples.extend(_independent_pens())
    all_tuples.extend(_esterbrook_pens())
    all_tuples.extend(_montblanc_expanded())
    all_tuples.extend(_pelikan_expanded())
    all_tuples.extend(_sailor_expanded())
    all_tuples.extend(_additional_visconti())
    # Expansion round
    all_tuples.extend(_montblanc_round3())
    all_tuples.extend(_pelikan_round3())
    all_tuples.extend(_sailor_round3())
    all_tuples.extend(_pilot_round3())
    all_tuples.extend(_platinum_round3())
    all_tuples.extend(_parker_waterman_round3())
    all_tuples.extend(_aurora_round3())
    all_tuples.extend(_lamy_twsbi_round3())
    all_tuples.extend(_vintage_expanded())
    all_tuples.extend(_nakaya_round3())
    all_tuples.extend(_conid_opus88_scribo_round3())
    all_tuples.extend(_caran_dupont_gvfc_round3())
    all_tuples.extend(_cartier_round3())
    all_tuples.extend(_japanese_artisan_round3())
    all_tuples.extend(_esterbrook_round3())
    all_tuples.extend(_additional_brands_round3())

    # Expansion Batch 4 — Pelikan Art, Sailor KoP/Realo, Namiki, Visconti, Aurora
    all_tuples.extend(_expanded_batch_4())
    # Expansion Batch 5 — Visconti, Pelikan, Sailor, Kaweco, Aurora, TWSBI, Platinum, Faber-Castell
    all_tuples.extend(_expanded_batch_5())
    # Expansion Batch 6 — 95 more pens to reach 700+
    all_tuples.extend(_expanded_batch_6())
    # Variant Coverage Expansion — ~108 pens focused on nib/color variants
    all_tuples.extend(_montblanc_nib_variants())
    all_tuples.extend(_pelikan_stripe_nib_variants())
    all_tuples.extend(_sailor_nib_specialty_variants())
    all_tuples.extend(_pilot_nib_color_variants())
    all_tuples.extend(_lamy_safari_alstar_variants())
    all_tuples.extend(_twsbi_kaweco_affordable_variants())
    all_tuples.extend(_platinum_color_variants())
    all_tuples.extend(_visconti_van_gogh_homo_sapiens_variants())
    all_tuples.extend(_aurora_parker_waterman_variants())

    # Expansion Round 7 — Montblanc LEs + additional brands (~230 pens)
    all_tuples.extend(_montblanc_patron_of_art())
    all_tuples.extend(_montblanc_writers_edition_le())
    all_tuples.extend(_montblanc_great_characters_le())
    all_tuples.extend(_montblanc_high_artistry())
    all_tuples.extend(_montblanc_meisterstueck_special())
    all_tuples.extend(_expanded_pelikan_round7())
    all_tuples.extend(_expanded_sailor_round7())
    all_tuples.extend(_expanded_pilot_round7())
    all_tuples.extend(_expanded_nakaya_round7())
    all_tuples.extend(_expanded_visconti_round7())
    all_tuples.extend(_expanded_aurora_round7())
    all_tuples.extend(_expanded_lamy_round7())
    all_tuples.extend(_expanded_platinum_round7())
    all_tuples.extend(_expanded_twsbi_round7())
    all_tuples.extend(_expanded_kaweco_round7())
    all_tuples.extend(_expanded_parker_waterman_cross_round7())
    all_tuples.extend(_expanded_vintage_round7())
    all_tuples.extend(_additional_round7_overflow())

    catalog: list[dict] = []
    for (name, brand, model_line, nib_material, nib_size,
         filling_system, price_eur, is_limited, rarity, notes) in all_tuples:
        catalog.append({
            "name": name,
            "brand": brand,
            "model_line": model_line,
            "nib_material": nib_material,
            "nib_size": nib_size,
            "filling_system": filling_system,
            "price_eur": price_eur,
            "is_limited": is_limited,
            "rarity": rarity,
            "notes": notes,
        })
    # Deduplicate by ('brand', 'name', 'nib_size') (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = (item["brand"], item["name"], item["nib_size"])
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


def _expanded_batch_4() -> list[tuple]:
    """50 additional fountain pens — Pelikan Art Collection, Sailor KoP/Realo/Naginata, Namiki, Visconti, Aurora."""
    return [
        # ── Pelikan — M800 Art Collection & Souveran SE ──
        ("M800 Art Collection Macaw", "Pelikan", "Art Collection", "18k Gold", "M",
         "piston", 900, True, "Limited Edition", "2023 LE, blue/yellow macaw resin"),
        ("M800 Art Collection Golden Beryl", "Pelikan", "Art Collection", "18k Gold", "B",
         "piston", 850, True, "Limited Edition", "2022 LE, golden amber resin"),
        ("M800 Art Collection Smoky High-Rise", "Pelikan", "Art Collection", "18k Gold", "F",
         "piston", 880, True, "Limited Edition", "2024 LE, smoky grey resin"),
        ("M1000 Raden Sunrise", "Pelikan", "Souveraen", "18k Gold", "B",
         "piston", 1800, True, "Limited Edition", "Raden (mother-of-pearl inlay) sunrise"),
        ("Souveraen M600 Pink", "Pelikan", "Souveraen", "14k Gold", "F",
         "piston", 420, True, "Limited Edition", "Special edition pink stripes"),
        ("M800 Art Collection Spirit of 1838", "Pelikan", "Art Collection", "18k Gold", "M",
         "piston", 950, True, "Limited Edition", "Anniversary LE, jade green barrel"),
        ("M800 Art Collection Ocean Swirl", "Pelikan", "Art Collection", "18k Gold", "F",
         "piston", 870, True, "Limited Edition", "2021 LE, deep blue swirl resin"),

        # ── Sailor — King of Pen, Pro Gear Realo, 1911 Naginata ──
        ("King of Pen Urushi Crimson", "Sailor", "King of Pen", "21k Gold", "M",
         "converter", 1600, True, "Limited Edition", "Hand-applied crimson urushi lacquer"),
        ("Pro Gear Realo Blue Demonstrator", "Sailor", "Realo", "21k Gold", "M",
         "piston", 580, True, "Limited Edition", "Transparent blue piston-fill"),
        ("Pro Gear Realo Maroon", "Sailor", "Realo", "21k Gold", "F",
         "piston", 560, False, "Standard", "Piston-fill Pro Gear, maroon resin"),
        ("1911 Large Naginata Concord", "Sailor", "1911", "21k Gold", "Naginata Concord",
         "converter", 1100, False, "Standard", "Dual-point specialty nib"),
        ("Pro Gear Slim Lucky Charm Series Manyo Haha", "Sailor", "Pro Gear Slim", "14k Gold", "MF",
         "converter", 300, True, "Limited Edition", "Botanical color ink-matching pen"),
        ("King of Pen Bespoke Lapis Blue", "Sailor", "Bespoke", "21k Gold", "B",
         "converter", 1800, True, "Limited Edition", "Wancher exclusive, deep lapis urushi"),
        ("1911 Standard Night Blue", "Sailor", "1911", "14k Gold", "F",
         "converter", 260, False, "Standard", "Deep navy resin, silver trim"),

        # ── Namiki — Yukari Royale, Emperor ──
        ("Yukari Royale Mount Fuji", "Namiki", "Yukari Royale", "18k Gold", "M",
         "converter", 3500, True, "Limited Edition", "Maki-e Mt. Fuji, gold/silver dust"),
        ("Yukari Royale Dragon and Cumulus", "Namiki", "Yukari Royale", "18k Gold", "B",
         "converter", 4200, True, "Limited Edition", "Togidashi maki-e dragon motif"),
        ("Emperor Chinkin Carp", "Namiki", "Emperor", "18k Gold", "M",
         "converter", 6500, True, "Limited Edition", "Chinkin engraving, koi carp motif"),
        ("Emperor Dragon", "Namiki", "Emperor", "18k Gold", "B",
         "converter", 7500, True, "Limited Edition", "Taka maki-e raised gold dragon"),
        ("Yukari Pine Tree", "Namiki", "Yukari", "18k Gold", "M",
         "converter", 1200, True, "Limited Edition", "Hira maki-e pine needles, green/gold"),
        ("Yukari Cherry Blossom", "Namiki", "Yukari", "18k Gold", "F",
         "converter", 1100, True, "Limited Edition", "Pink/gold sakura maki-e design"),
        ("Nippon Art Golden Pheasant", "Namiki", "Nippon Art", "14k Gold", "M",
         "converter", 480, False, "Standard", "Screen-printed maki-e, accessible Namiki"),
        ("Nippon Art Mount Fuji and Shrimp", "Namiki", "Nippon Art", "14k Gold", "F",
         "converter", 480, False, "Standard", "Ukiyo-e inspired Hokusai design"),

        # ── Visconti — Homo Sapiens, Van Gogh, Opera Master ──
        ("Homo Sapiens Dark Age", "Visconti", "Homo Sapiens", "Palladium", "F",
         "vacuum", 800, False, "Standard", "Black lava, ruthenium trim"),
        ("Van Gogh Orchard in Blossom", "Visconti", "Van Gogh", "Steel", "F",
         "converter", 320, False, "Standard", "Green/white resin, spring palette"),
        ("Van Gogh Sunflowers", "Visconti", "Van Gogh", "Steel", "M",
         "converter", 320, False, "Standard", "Yellow/amber resin, vibrant design"),
        ("Medici Matte Black", "Visconti", "Medici", "18k Gold", "M",
         "converter", 650, False, "Standard", "Matte black resin, 18k gold nib"),
        ("Homo Sapiens Lava Color Blue", "Visconti", "Homo Sapiens", "Palladium", "M",
         "vacuum", 850, True, "Limited Edition", "Blue lava resin, limited colorway"),

        # ── Aurora — 88, Optima, Internazionale ──
        ("88 Big Black Mamba", "Aurora", "88", "18k Gold", "M",
         "piston", 680, False, "Standard", "Oversized 88, black resin, gold trim"),
        ("Optima Auroloide Blue", "Aurora", "Optima", "18k Gold", "F",
         "piston", 550, False, "Standard", "Blue auroloide resin, gold bands"),
        ("Optima Flex Nib", "Aurora", "Optima", "18k Gold", "Flex",
         "piston", 650, True, "Limited Edition", "Rare flex nib variant"),
        ("Internazionale Blue", "Aurora", "Internazionale", "18k Gold", "M",
         "piston", 450, False, "Standard", "Classic blue resin, compact size"),
        ("Internazionale Orange Limited", "Aurora", "Internazionale", "18k Gold", "M",
         "piston", 520, True, "Limited Edition", "LE orange resin, numbered"),
        ("88 Minerali Cinnabar", "Aurora", "88 Minerali", "18k Gold", "B",
         "piston", 750, True, "Limited Edition", "Mineral-inspired resin, red/gold"),
        ("88 Minerali Malachite", "Aurora", "88 Minerali", "18k Gold", "M",
         "piston", 750, True, "Limited Edition", "Green mineral resin, gold trim"),
        ("88 Unica Nera", "Aurora", "88", "18k Gold", "M",
         "piston", 580, False, "Standard", "All-black edition, PVD trim"),
        ("Talentum Classic Black", "Aurora", "Talentum", "14k Gold", "M",
         "converter", 280, False, "Standard", "Entry-level Aurora, 14k nib"),
    ]


def _expanded_batch_5() -> list[tuple]:
    """55 additional fountain pens — Visconti, Pelikan, Sailor, Kaweco, Aurora,
    TWSBI, Platinum, Faber-Castell expansion."""
    return [
        # ── Visconti — Homo Sapiens, Van Gogh, Opera Master (+10) ──
        ("Homo Sapiens Elegance Oversize", "Visconti", "Homo Sapiens", "Palladium", "B",
         "vacuum", 900, False, "Standard", "Oversized basaltic lava, palladium dreamtouch nib"),
        ("Homo Sapiens Steel Age", "Visconti", "Homo Sapiens", "Palladium", "F",
         "vacuum", 780, False, "Standard", "Stainless steel trim, charcoal lava barrel"),
        ("Homo Sapiens London Fog", "Visconti", "Homo Sapiens", "Palladium", "M",
         "vacuum", 850, True, "Limited Edition", "Grey fog lava resin, limited colorway"),
        ("Van Gogh Café Terrace at Night", "Visconti", "Van Gogh", "Steel", "F",
         "converter", 320, False, "Standard", "Amber/blue resin, night café tribute"),
        ("Van Gogh Irises", "Visconti", "Van Gogh", "Steel", "M",
         "converter", 320, False, "Standard", "Purple/green resin, garden palette"),
        ("Van Gogh Wheatfield with Crows", "Visconti", "Van Gogh", "Steel", "B",
         "converter", 320, False, "Standard", "Blue/gold resin, dramatic landscape tribute"),
        ("Opera Master Desert Springs", "Visconti", "Opera Master", "Palladium", "M",
         "vacuum", 1200, True, "Limited Edition", "Amber/sand swirl acrylic, oasis motif"),
        ("Opera Master Corsica", "Visconti", "Opera Master", "Palladium", "F",
         "vacuum", 1250, True, "Limited Edition", "Mediterranean blue/white acrylic swirl"),
        ("Homo Sapiens Dual Touch", "Visconti", "Homo Sapiens", "Palladium", "M",
         "vacuum", 880, False, "Standard", "Dual-tone lava barrel, bronze and black"),
        ("Rembrandt-S Night Blue", "Visconti", "Rembrandt", "Steel", "F",
         "converter", 180, False, "Standard", "Night blue resin, steel nib, entry Visconti"),

        # ── Pelikan Souverän — M800, M1000, special editions (+8) ──
        ("Souveraen M1000 Blue-Black", "Pelikan", "Souveraen", "18k Gold", "B",
         "piston", 780, False, "Standard", "Blue striped oversized flagship"),
        ("M800 Art Collection Burnt Orange", "Pelikan", "Art Collection", "18k Gold", "M",
         "piston", 900, True, "Limited Edition", "2020 LE, warm burnt orange resin"),
        ("M800 Art Collection Pistachio", "Pelikan", "Art Collection", "18k Gold", "F",
         "piston", 880, True, "Limited Edition", "Pistachio green swirl resin, gold trim"),
        ("Souveraen M600 Red-White", "Pelikan", "Souveraen", "14k Gold", "B",
         "piston", 430, True, "Limited Edition", "Red and white striped special edition, broad nib variant"),
        ("Souveraen M400 Brown Tortoiseshell", "Pelikan", "Souveraen", "14k Gold", "F",
         "piston", 360, False, "Standard", "Compact brown tortoiseshell resin"),
        ("M200 Classic Gold Marbled", "Pelikan", "Classic", "Steel", "M",
         "piston", 120, False, "Standard", "Gold marbled resin, entry Pelikan piston filler"),

        # ── Sailor Pro Gear — Realo, Slim, limited editions (+8) ──
        ("Pro Gear Realo Black Gold", "Sailor", "Realo", "21k Gold", "B",
         "piston", 570, False, "Standard", "Piston-fill Pro Gear, black with gold trim"),
        ("Pro Gear Slim Shikiori Amaoto Harusame", "Sailor", "Pro Gear Slim", "14k Gold", "MF",
         "converter", 290, True, "Limited Edition", "Spring rain series, soft blue resin"),
        ("Pro Gear Slim Dragon Palace", "Sailor", "Pro Gear Slim", "14k Gold", "F",
         "converter", 350, True, "Limited Edition", "Ryugu-jo inspired teal and gold"),
        ("Pro Gear Slim Manyo Nadeshiko", "Sailor", "Pro Gear Slim", "14k Gold", "MF",
         "converter", 300, True, "Limited Edition", "Botanical series, pink carnation color"),
        ("Pro Gear Cocktail Series Old-Fashioned", "Sailor", "Pro Gear", "21k Gold", "B",
         "converter", 460, True, "Limited Edition", "Cocktail-inspired amber/brown resin"),
        ("1911 Large Transparent Demonstrator", "Sailor", "1911", "21k Gold", "M",
         "converter", 450, True, "Limited Edition", "Fully transparent cigar shape, 21k nib"),
        ("Pro Gear Slim Mini Gold Ivory", "Sailor", "Pro Gear Slim", "14k Gold", "MF",
         "converter", 240, False, "Standard", "Compact ivory resin, gold trim, mini format"),

        # ── Kaweco Sport — Classic, AL Sport, Stone, special editions (+6) ──
        ("Kaweco Sport Classic Navy", "Kaweco", "Sport", "Steel", "M",
         "converter", 25, False, "Standard", "Pocket pen icon, navy blue octagonal barrel"),
        ("Kaweco Sport Classic Bordeaux", "Kaweco", "Sport", "Steel", "F",
         "converter", 25, False, "Standard", "Deep bordeaux red, snap cap, pocket size"),
        ("Kaweco AL Sport Raw High Gloss", "Kaweco", "AL Sport", "Steel", "M",
         "converter", 80, False, "Standard", "Polished raw aluminum body, premium pocket pen"),
        ("Kaweco AL Sport Vibrant Violet", "Kaweco", "AL Sport", "Steel", "EF",
         "converter", 75, True, "Limited Edition", "Annual limited purple anodized aluminum"),
        ("Kaweco Sport Collectors Edition Iridescent Pearl", "Kaweco", "Sport", "Steel", "M",
         "converter", 40, True, "Limited Edition", "Iridescent pearl resin, collector SE"),
        ("Kaweco Brass Sport", "Kaweco", "Brass Sport", "Steel", "M",
         "converter", 95, False, "Standard", "Solid brass body, develops patina over time"),

        # ── Aurora — Optima, 88, Ipsilon (+6) ──
        ("Optima Auroloide Green", "Aurora", "Optima", "18k Gold", "M",
         "piston", 560, False, "Standard", "Classic green auroloide celluloid, gold bands"),
        ("88 Minerali Lapis Lazuli", "Aurora", "88 Minerali", "18k Gold", "F",
         "piston", 750, True, "Limited Edition", "Blue lapis mineral celluloid, gold trim"),
        ("88 Minerali Nero Perla", "Aurora", "88 Minerali", "18k Gold", "M",
         "piston", 720, True, "Limited Edition", "Black pearl mineral celluloid"),
        ("Ipsilon Satin Orange", "Aurora", "Ipsilon", "Steel", "F",
         "converter", 120, False, "Standard", "Satin finish orange resin barrel"),
        ("Ipsilon Deluxe Bordeaux", "Aurora", "Ipsilon", "Steel", "M",
         "converter", 160, False, "Standard", "Premium lacquered bordeaux resin, chrome trim"),
        ("88 Anniversary Green-Gold", "Aurora", "88", "18k Gold", "B",
         "piston", 700, True, "Limited Edition", "88th anniversary, jade green celluloid"),

        # ── TWSBI — Eco, 580, Diamond series (+6) ──
        ("TWSBI Eco Jade Green", "TWSBI", "Eco", "Steel", "M",
         "piston", 35, False, "Standard", "Jade green demonstrator, piston fill"),
        ("TWSBI Eco Smoke Rose Gold", "TWSBI", "Eco", "Steel", "F",
         "piston", 40, True, "Limited Edition", "Smoke barrel with rose gold trim"),
        ("TWSBI Diamond 580ALR Nickel Gray", "TWSBI", "Diamond 580", "Steel", "EF",
         "piston", 70, False, "Standard", "Nickel gray aluminum ring demonstrator"),
        ("TWSBI Diamond 580 Smoke", "TWSBI", "Diamond 580", "Steel", "M",
         "piston", 60, False, "Standard", "Smoke tinted barrel, full-size demonstrator"),
        ("TWSBI Diamond Mini AL Silver", "TWSBI", "Diamond Mini", "Steel", "F",
         "piston", 60, False, "Standard", "Aluminum-accented compact piston filler"),
        ("TWSBI Vac Mini Smoke", "TWSBI", "Vac Mini", "Steel", "M",
         "vacuum", 60, False, "Standard", "Compact vacuum filler, smoke-tinted barrel"),

        # ── Platinum — #3776 Century, Procyon, Preppy (+6) ──
        ("Century #3776 Chenonceau White", "Platinum", "#3776 Century", "14k Gold", "F",
         "converter", 200, True, "Limited Edition", "Pure white translucent resin, Loire tribute"),
        ("Century #3776 Shape of a Star", "Platinum", "#3776 Century", "14k Gold", "M",
         "converter", 250, True, "Limited Edition", "Star faceted barrel motif, limited release"),
        ("Century #3776 Soft Fine", "Platinum", "#3776 Century", "14k Gold", "SF",
         "converter", 200, False, "Standard", "Soft fine nib, slight flex, fine line variation"),
        ("Procyon Luster Citrus Yellow", "Platinum", "Procyon", "Steel", "M",
         "converter", 90, False, "Standard", "Bright citrus yellow aluminum barrel"),
        ("Procyon Persimmon Orange", "Platinum", "Procyon", "Steel", "F",
         "converter", 80, False, "Standard", "Warm persimmon aluminum barrel, snap cap"),
        ("Preppy Wa Limited Sakura", "Platinum", "Preppy", "Steel", "F",
         "converter", 8, True, "Limited Edition", "Cherry blossom print, budget collector piece"),

        # ── Faber-Castell — Ondoro, Ambition, e-motion (+5) ──
        ("Ondoro Smoked Oak", "Faber-Castell", "Ondoro", "Steel", "M",
         "converter", 130, False, "Standard", "Hexagonal smoked oak barrel, chrome trim"),
        ("Ondoro Graphite Black", "Faber-Castell", "Ondoro", "Steel", "F",
         "converter", 110, False, "Standard", "Matte black lacquer hexagonal barrel"),
        ("Ambition Walnut Wood", "Faber-Castell", "Ambition", "Steel", "M",
         "converter", 90, False, "Standard", "Walnut wood barrel, chrome accents"),
        ("Ambition Coconut", "Faber-Castell", "Ambition", "Steel", "F",
         "converter", 85, False, "Standard", "Coconut brown lacquer resin, slim profile"),
        ("e-motion Pure Black", "Faber-Castell", "e-motion", "Steel", "M",
         "converter", 110, False, "Standard", "Matt black lacquer, chrome guilloche pattern"),
    ]


def _expanded_batch_6() -> list[tuple]:
    """95 additional fountain pens — Montblanc Writers Edition, Pelikan Souveran SE,
    Sailor Pro Gear LE, Visconti art pens, Aurora Optima specials, Lamy 2000 variants,
    vintage Parker Duofold, Cross Townsend specials."""
    return [
        # ── Montblanc Writers Edition (+12) ────────────────────────────
        ("Writers Edition Leo Tolstoy", "Montblanc", "Writers Edition", "18k Gold", "F",
         "piston", 1350, True, "Limited Edition", "2015 LE, burgundy celluloid, Cyrillic clip, fine nib variant"),
        ("Writers Edition Rudyard Kipling", "Montblanc", "Writers Edition", "18k Gold", "F",
         "piston", 1250, True, "Limited Edition", "2019 LE, brown lacquer, Indian motifs"),
        ("Writers Edition Victor Hugo", "Montblanc", "Writers Edition", "18k Gold", "B",
         "piston", 1400, True, "Limited Edition", "2020 LE, cathedral-inspired cap design"),
        ("Writers Edition Jane Austen", "Montblanc", "Writers Edition", "18k Gold", "M",
         "piston", 1300, True, "Limited Edition", "2023 LE, ivory lacquer, quill-inspired clip, medium nib variant"),
        ("Writers Edition Miguel de Cervantes", "Montblanc", "Writers Edition", "18k Gold", "M",
         "piston", 1150, True, "Limited Edition", "2022 LE, Don Quixote windmill engraving"),
        ("Patron of Art Gaius Maecenas 4810", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 2500, True, "Limited Edition", "2003 LE 4810 pcs, Roman mosaic inlay"),
        ("Patron of Art Alexander von Humboldt", "Montblanc", "Patron of Art", "18k Gold", "F",
         "piston", 2200, True, "Limited Edition", "2019 LE 4810 pcs, ocean blue lacquer"),
        ("Meisterstueck 149 Unicef 2017", "Montblanc", "Meisterstueck", "18k Gold", "M",
         "piston", 1100, True, "Limited Edition", "Unicef blue lacquer, special edition"),
        ("Great Characters Elvis Presley", "Montblanc", "Great Characters", "18k Gold", "M",
         "converter", 1400, True, "Limited Edition", "Pink gold-coated, rock & roll motifs"),
        ("Great Characters Walt Disney", "Montblanc", "Great Characters", "18k Gold", "F",
         "converter", 1500, True, "Limited Edition", "2019 LE, Fantasia-inspired blue lacquer"),
        ("Meisterstueck 146 Solitaire Blue Hour", "Montblanc", "Meisterstueck", "18k Gold", "F",
         "piston", 1250, True, "Limited Edition", "Midnight blue lacquer, diamond pattern"),
        ("Heritage Egyptomania", "Montblanc", "Heritage", "18k Gold", "M",
         "piston", 1600, True, "Limited Edition", "Egyptian hieroglyph engraving, gold accents"),

        # ── Pelikan Souveran Special Editions (+10) ────────────────────
        ("Souveraen M800 Renaissance Brown", "Pelikan", "Souveraen", "18k Gold", "B",
         "piston", 650, True, "Limited Edition", "Renaissance brown striped resin, gold trim"),
        ("Souveraen M800 Grand Place", "Pelikan", "Souveraen", "18k Gold", "M",
         "piston", 750, True, "Limited Edition", "Brussels Grand Place edition, burgundy/gold"),
        ("Souveraen M600 Vibrant Blue", "Pelikan", "Souveraen", "14k Gold", "F",
         "piston", 420, True, "Limited Edition", "Vibrant blue transparent barrel SE"),
        ("Souveraen M600 Vibrant Orange", "Pelikan", "Souveraen", "14k Gold", "M",
         "piston", 420, True, "Limited Edition", "Vibrant orange transparent barrel SE"),
        ("Souveraen M600 Vibrant Green", "Pelikan", "Souveraen", "14k Gold", "EF",
         "piston", 420, True, "Limited Edition", "Vibrant green transparent barrel SE"),
        ("Souveraen M1000 Raden Royal Gold", "Pelikan", "Souveraen", "18k Gold", "B",
         "piston", 2200, True, "Limited Edition", "Raden mother-of-pearl, gold leaf inlay"),
        ("Souveraen M805 Stresemann Anthracite", "Pelikan", "Souveraen", "18k Gold", "F",
         "piston", 520, False, "Standard", "Anthracite grey striped, palladium trim"),
        ("M800 Art Collection Ocean Fantasy", "Pelikan", "Art Collection", "18k Gold", "M",
         "piston", 920, True, "Limited Edition", "2021 LE, deep ocean blue swirl resin"),
        ("M800 Art Collection Dawn", "Pelikan", "Art Collection", "18k Gold", "F",
         "piston", 880, True, "Limited Edition", "2019 LE, sunrise pink/orange resin"),
        ("M205 Olivine Demonstrator", "Pelikan", "Classic", "Steel", "F",
         "piston", 135, True, "Limited Edition", "Olive green demonstrator, special ink edition"),

        # ── Sailor Pro Gear Limited Editions (+10) ─────────────────────
        ("Pro Gear Slim Lucky Charm Dharma", "Sailor", "Pro Gear Slim", "14k Gold", "MF",
         "converter", 380, True, "Limited Edition", "Red Dharma doll motif, Japanese luck charm"),
        ("Pro Gear King of Pen Ebonite Tangerine", "Sailor", "King of Pen", "21k Gold", "B",
         "converter", 1200, True, "Limited Edition", "Ebonite tangerine barrel, oversized 21k nib"),
        ("Pro Gear Cocktail Series Mojito", "Sailor", "Pro Gear", "21k Gold", "M",
         "converter", 450, True, "Limited Edition", "Mint green resin, cocktail series"),
        ("Pro Gear Cocktail Series Kure Azur", "Sailor", "Pro Gear", "21k Gold", "MF",
         "converter", 460, True, "Limited Edition", "Azure blue resin, Kure city exclusive"),
        ("Pro Gear Slim Shikiori Yonaga", "Sailor", "Pro Gear Slim", "14k Gold", "F",
         "converter", 310, True, "Limited Edition", "Long night series, deep navy resin"),
        ("1911 Large Wicked Witch of the West", "Sailor", "1911", "21k Gold", "M",
         "converter", 520, True, "Limited Edition", "Bungubox collab, emerald green"),
        ("Pro Gear Slim Shikiori Shimoyo", "Sailor", "Pro Gear Slim", "14k Gold", "MF",
         "converter", 300, True, "Limited Edition", "Frost night series, ice blue resin"),
        ("Pro Gear Storm over the Sea", "Sailor", "Pro Gear", "21k Gold", "B",
         "converter", 500, True, "Limited Edition", "PenSachi exclusive, dark storm blue"),
        ("Pro Gear Slim Manyo Sakura", "Sailor", "Pro Gear Slim", "14k Gold", "F",
         "converter", 310, True, "Limited Edition", "Cherry blossom pink botanical series"),

        # ── Visconti Art Pens (+8) ─────────────────────────────────────
        ("Homo Sapiens Magma", "Visconti", "Homo Sapiens", "Palladium", "B",
         "vacuum", 920, True, "Limited Edition", "Red/black lava swirl, magma colorway, broad nib variant"),
        ("Opera Master Crimson Tide", "Visconti", "Opera Master", "Palladium", "F",
         "vacuum", 1300, True, "Limited Edition", "Deep crimson acrylic swirl"),
        ("Homo Sapiens Bronze Age", "Visconti", "Homo Sapiens", "Palladium", "B",
         "vacuum", 850, False, "Standard", "Bronze trim, basaltic lava barrel"),
        ("Il Magnifico Marble Green", "Visconti", "Il Magnifico", "18k Gold", "B",
         "piston", 2000, True, "Limited Edition", "Oversized marble green celluloid"),
        ("Rembrandt-S Bordeaux", "Visconti", "Rembrandt", "Steel", "F",
         "converter", 190, False, "Standard", "Bordeaux resin, entry Visconti"),
        ("Van Gogh Orchard in Blossom", "Visconti", "Van Gogh", "Steel", "M",
         "converter", 330, False, "Standard", "Pink/white resin, spring blossom motif"),
        ("Homo Sapiens Crystal Dream", "Visconti", "Homo Sapiens", "Palladium", "EF",
         "vacuum", 1100, True, "Limited Edition", "Clear crystal lava, visible ink chamber"),

        # ── Aurora Optima Specials (+8) ─────────────────────────────────
        ("Optima Auroloide Blue", "Aurora", "Optima", "18k Gold", "M",
         "piston", 580, False, "Standard", "Blue auroloide celluloid, gold bands"),
        ("Optima Mare Shimmering Blue", "Aurora", "Optima", "18k Gold", "M",
         "piston", 650, True, "Limited Edition", "Shimmering sea blue limited"),
        ("Optima Caleidoscopio Luce", "Aurora", "Optima", "18k Gold", "F",
         "piston", 720, True, "Limited Edition", "Kaleidoscope light edition, multicolor"),
        ("Internazionale Blue", "Aurora", "Internazionale", "18k Gold", "B",
         "piston", 900, True, "Limited Edition", "Annual limited, deep navy blue"),
        ("88 Sole Sun Yellow", "Aurora", "88", "18k Gold", "M",
         "piston", 680, True, "Limited Edition", "Sunny yellow celluloid, gold trim"),
        ("Talentum Finesse Burgundy", "Aurora", "Talentum", "14k Gold", "F",
         "converter", 350, False, "Standard", "Slim burgundy lacquer, 14k gold nib"),
        ("Optima Demo Auroloide Clear", "Aurora", "Optima", "18k Gold", "M",
         "piston", 620, True, "Limited Edition", "Clear auroloide demonstrator, gold trim"),

        # ── Lamy 2000 Variants (+8) ────────────────────────────────────
        ("Lamy 2000 Makrolon", "Lamy", "2000", "14k Gold", "EF",
         "piston", 350, False, "Standard", "Classic Makrolon, brushed metal clip"),
        ("Lamy 2000 Stainless Steel", "Lamy", "2000", "14k Gold", "M",
         "piston", 450, False, "Standard", "Brushed stainless steel body"),
        ("Lamy 2000 Black Amber", "Lamy", "2000", "14k Gold", "F",
         "piston", 420, True, "Limited Edition", "2019 LE, amber-tinted Makrolon barrel"),
        ("Lamy 2000 Brown", "Lamy", "2000", "14k Gold", "M",
         "piston", 480, True, "Limited Edition", "2021 LE, brown Makrolon barrel"),
        ("Lamy 2000 Bauhaus Blue", "Lamy", "2000", "14k Gold", "F",
         "piston", 520, True, "Limited Edition", "2019 Bauhaus centenary, midnight blue"),
        ("Lamy Dialog CC Dark Blue", "Lamy", "Dialog", "14k Gold", "M",
         "converter", 420, True, "Limited Edition", "Dark blue lacquer, retractable nib"),
        ("Lamy Studio Glacier Blue", "Lamy", "Studio", "Steel", "F",
         "converter", 75, True, "Limited Edition", "Glacier blue special edition"),
        ("Lamy Aion Olive Silver", "Lamy", "Aion", "Steel", "M",
         "converter", 90, True, "Limited Edition", "Olive silver anodized aluminum"),

        # ── Vintage Parker Duofold (+10) ────────────────────────────────
        ("Duofold Senior Big Red (1920s)", "Parker", "Duofold Vintage", "14k Gold (Flex)", "M",
         "button", 1200, False, "Vintage", "1920s oversized, red hard rubber, flex nib"),
        ("Duofold Junior Jade Green (1930s)", "Parker", "Duofold Vintage", "14k Gold", "F",
         "button", 800, False, "Vintage", "1930s jade green Permanite barrel"),
        ("Vacumatic Major Blue Diamond (1940s)", "Parker", "Vacumatic", "14k Gold", "M",
         "vacumatic", 600, False, "Vintage", "1940s golden pearl striated barrel"),
        ("Vacumatic Maxima Silver Pearl (1940s)", "Parker", "Vacumatic", "14k Gold", "B",
         "vacumatic", 700, False, "Vintage", "1940s oversized silver pearl stripes"),
        ("Parker 51 Aerometric Black (1950s)", "Parker", "51", "14k Gold", "F",
         "aerometric", 350, False, "Vintage", "1950s classic, black Lucite barrel, lustraloy cap"),
        ("Parker 51 Signet Gold Cap (1950s)", "Parker", "51", "14k Gold", "M",
         "aerometric", 550, False, "Vintage", "1950s, 14k gold-filled cap, forest green barrel"),
        ("Parker 75 Sterling Silver Cisele", "Parker", "75", "14k Gold", "M",
         "converter", 400, False, "Vintage", "1960s, sterling silver crosshatch barrel, medium nib variant"),
        ("Parker 61 Capillary Black (1960s)", "Parker", "61", "14k Gold", "M",
         "capillary", 300, False, "Vintage", "Capillary fill system, black Lucite barrel"),
        ("Duofold Centennial Black (Modern)", "Parker", "Duofold Centennial", "18k Gold", "M",
         "converter", 550, False, "Standard", "Modern reissue, black acrylic, 18k nib"),
        ("Duofold Centennial Orange (Modern)", "Parker", "Duofold Centennial", "18k Gold", "B",
         "converter", 580, False, "Standard", "Big Red tribute, orange acrylic barrel"),

        # ── Cross Townsend Specials (+7) ────────────────────────────────
        ("Townsend Black Lacquer", "Cross", "Townsend", "18k Gold", "M",
         "converter", 450, False, "Standard", "Black Chinese lacquer, gold accents"),
        ("Townsend Star Wars Millennium Falcon", "Cross", "Townsend", "18k Gold", "M",
         "converter", 700, True, "Limited Edition", "Star Wars LE, etched Millennium Falcon"),
        ("Townsend Lustrous Chrome", "Cross", "Townsend", "18k Gold", "F",
         "converter", 350, False, "Standard", "Mirror-polished chrome, rhodium-plated nib"),
        ("Townsend Medalist Platinum", "Cross", "Townsend", "18k Gold", "M",
         "converter", 500, False, "Standard", "Platinum-plated barrel, 18k nib"),
        ("Peerless 125 Obsidian Black", "Cross", "Peerless 125", "18k Gold", "B",
         "converter", 600, True, "Limited Edition", "125th anniversary, obsidian resin"),
        ("Century II Black Lacquer", "Cross", "Century II", "Steel", "M",
         "converter", 150, False, "Standard", "Classic black lacquer, slim design"),
        ("Wanderlust Malta", "Cross", "Wanderlust", "Steel", "F",
         "converter", 100, True, "Limited Edition", "Malta blue/orange, travel series"),

        # ── Sheaffer Legacy Heritage (+5) ──────────────────────────────
        ("Legacy Heritage Black Lacquer", "Sheaffer", "Legacy Heritage", "18k Gold", "M",
         "converter", 450, False, "Standard", "Black lacquer, palladium trim, inlaid nib"),
        ("Legacy Heritage Green Lacquer", "Sheaffer", "Legacy Heritage", "18k Gold", "F",
         "converter", 480, True, "Limited Edition", "British racing green lacquer"),
        ("Snorkel Valiant Burgundy (1950s)", "Sheaffer", "Snorkel", "14k Gold", "M",
         "snorkel", 350, False, "Vintage", "1950s pneumatic snorkel fill, burgundy"),
        ("PFM Autograph Black (1960s)", "Sheaffer", "PFM", "14k Gold", "B",
         "snorkel", 500, False, "Vintage", "Pen For Men, inlaid nib, touchdown fill"),
        ("Prelude Matte Black", "Sheaffer", "Prelude", "Steel", "M",
         "converter", 80, False, "Standard", "Matte black lacquer, chrome accents"),

        # ── Waterman Edson & Exception (+5) ────────────────────────────
        ("Edson Sapphire Blue", "Waterman", "Edson", "18k Gold", "M",
         "piston", 650, False, "Standard", "Sapphire blue lacquer, oversized barrel"),
        ("Edson Ruby Red", "Waterman", "Edson", "18k Gold", "F",
         "piston", 680, False, "Standard", "Ruby red lacquer, premium piston fill"),
        ("Exception Night & Day Silver", "Waterman", "Exception", "18k Gold", "M",
         "converter", 550, False, "Standard", "Sterling silver barrel, art deco pattern"),
        ("Exception Slim Black", "Waterman", "Exception", "18k Gold", "F",
         "converter", 380, False, "Standard", "Slim black lacquer, gold-plated trim"),
        ("Carene Black Sea", "Waterman", "Carene", "18k Gold", "M",
         "converter", 280, False, "Standard", "Black lacquer, boat-hull barrel shape"),

        # ── Conklin Heritage / Noodler's (+5) ──────────────────────────
        ("Duragraph Amber", "Conklin", "Duragraph", "Steel", "M",
         "converter", 65, False, "Standard", "Amber crescent fill resin, vintage style"),
        ("All American Sunstone", "Conklin", "All American", "Steel", "F",
         "converter", 120, True, "Limited Edition", "Sunstone orange resin, gold trim"),
        ("Herringbone Rosewood", "Conklin", "Herringbone", "Steel", "M",
         "converter", 50, False, "Standard", "Rosewood herringbone resin pattern"),
        ("Noodler's Ahab Flex Cardinal Darkness", "Noodler's", "Ahab", "Steel", "Flex",
         "piston", 30, False, "Standard", "Ebonite feed, flex steel nib, piston fill"),
        ("Noodler's Konrad Flex Acrylic Teal", "Noodler's", "Konrad", "Steel", "Flex",
         "piston", 25, False, "Standard", "Demonstrator teal acrylic, flex nib"),

        # ── S.T. Dupont Expanded (+5) ──────────────────────────────────
        ("Line D Atelier Bronze", "S.T. Dupont", "Line D", "14k Gold", "M",
         "converter", 750, False, "Standard", "Natural lacquer, bronze highlights"),
        ("Line D Firehead Guilloche Gold", "S.T. Dupont", "Line D", "14k Gold", "F",
         "converter", 820, True, "Limited Edition", "Gold guilloche diamond head cap"),
        ("Liberté Black", "S.T. Dupont", "Liberté", "14k Gold", "M",
         "converter", 450, False, "Standard", "Black composite, palladium finish"),
        ("D-Initial Blue-Bronze", "S.T. Dupont", "D-Initial", "Steel", "M",
         "converter", 150, False, "Standard", "Blue lacquer, bronze clip, entry model"),
        ("Line D Medium Star Wars", "S.T. Dupont", "Line D", "14k Gold", "M",
         "converter", 1200, True, "Limited Edition", "Star Wars collaboration, Darth Vader"),

        # ── Caran d'Ache Expanded (+5) ─────────────────────────────────
        ("Léman Grand Bleu", "Caran d'Ache", "Léman", "18k Gold", "M",
         "piston", 800, False, "Standard", "Grand blue lacquer, rhodium-coated nib"),
        ("Léman Slim Scarlet Red", "Caran d'Ache", "Léman", "18k Gold", "F",
         "converter", 650, False, "Standard", "Slim scarlet red Chinese lacquer"),
        ("Ecridor Chevron Gilded", "Caran d'Ache", "Ecridor", "Steel", "M",
         "converter", 250, False, "Standard", "Gold-plated chevron guilloche pattern"),
        ("849 Brut Rosé", "Caran d'Ache", "849", "Steel", "M",
         "converter", 35, True, "Limited Edition", "Rosé gold aluminum, annual LE"),
        ("Varius Rubracer", "Caran d'Ache", "Varius", "18k Gold", "F",
         "converter", 750, False, "Standard", "Red rubber barrel, silver trim, fine nib variant"),
    ]


# ---------------------------------------------------------------------------
# Expansion Round 7 — Montblanc Limited Editions + Additional Brands (~230 pens)
# ---------------------------------------------------------------------------


def _montblanc_patron_of_art() -> list[tuple]:
    """~30 Montblanc Patron of Art fountain pens — annual series since 1992, 4810-piece and 888-piece editions."""
    return [
        # ── Pre-2000 grails ──
        ("Patron of Art Homage to Gaius Maecenas 4810", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 800, True, "Grail", "1992, first Patron of Art, 4810 pcs"),
        ("Patron of Art Homage to Gaius Maecenas 888", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 12000, True, "Grail", "1992, 888-piece LE, inaugural edition"),
        ("Patron of Art Lorenzo de Medici 4810", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 3000, True, "Grail", "1992, 4810 pcs, most sought-after PoA"),
        ("Patron of Art Lorenzo de Medici 888", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 15000, True, "Grail", "1992, 888-piece LE, highest-valued PoA"),
        ("Patron of Art Octavian 4810", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 2500, True, "Grail", "1993, 4810 pcs, Roman emperor motif"),
        ("Patron of Art Octavian 888", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 10000, True, "Grail", "1993, 888-piece LE, elaborate engraving"),
        ("Patron of Art Louis XIV 4810", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 2200, True, "Grail", "1994, 4810 pcs, Sun King tribute"),
        ("Patron of Art Louis XIV 888", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 9000, True, "Grail", "1994, 888-piece LE, gold vermeil"),
        ("Patron of Art Alexander the Great 4810", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 1800, True, "Grail", "1998, 4810 pcs, Macedonian motifs"),
        ("Patron of Art Alexander the Great 888", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 8000, True, "Grail", "1998, 888-piece LE, gold overlay"),
        # ── 2000-2010 high ──
        ("Patron of Art Karl der Grosse 4810", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 700, True, "Grail", "2000, 4810 pcs, Charlemagne tribute"),
        ("Patron of Art Karl der Grosse 888", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 5000, True, "Grail", "2000, 888-piece LE, elaborate crown motif"),
        ("Patron of Art Andrew Carnegie 4810", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 600, True, "Limited Edition", "2002, 4810 pcs, steel baron tribute"),
        ("Patron of Art Andrew Carnegie 888", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 3500, True, "Limited Edition", "2002, 888-piece LE, gold and steel"),
        ("Patron of Art Pope Julius II 4810", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 550, True, "Limited Edition", "2005, 4810 pcs, Renaissance patron"),
        ("Patron of Art Pope Julius II 888", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 3200, True, "Limited Edition", "2005, 888-piece LE, papal crest"),
        ("Patron of Art Marquise de Pompadour 4810", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 500, True, "Limited Edition", "2006, 4810 pcs, Rococo style"),
        ("Patron of Art Marquise de Pompadour 888", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 3000, True, "Limited Edition", "2006, 888-piece LE, mother of pearl"),
        ("Patron of Art Max von Oppenheim 4810", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 450, True, "Limited Edition", "2009, 4810 pcs, archaeological motifs"),
        ("Patron of Art Max von Oppenheim 888", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 2800, True, "Limited Edition", "2009, 888-piece LE, gold filigree"),
        ("Patron of Art Henry E. Steinway 4810", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 450, True, "Limited Edition", "2010, 4810 pcs, piano-inspired design"),
        ("Patron of Art Henry E. Steinway 888", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 2500, True, "Limited Edition", "2010, 888-piece LE, ebony and ivory"),
        # ── 2011-2023 ──
        ("Patron of Art Zetkin 4810", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 450, True, "Limited Edition", "2011, 4810 pcs, Art Nouveau motifs"),
        ("Patron of Art Joseph II 4810", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 500, True, "Limited Edition", "2013, 4810 pcs, Habsburg tribute"),
        ("Patron of Art Joseph II 888", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 2500, True, "Limited Edition", "2013, 888-piece LE, ornate engraving"),
        ("Patron of Art Peggy Guggenheim 4810", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 500, True, "Limited Edition", "2016, 4810 pcs, Venetian art deco"),
        ("Patron of Art Peggy Guggenheim 888", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 2200, True, "Limited Edition", "2016, 888-piece LE, gold and lapis"),
        ("Patron of Art Victoria 4810", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 500, True, "Limited Edition", "2017, 4810 pcs, Victorian era tribute"),
        ("Patron of Art Victoria 888", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 2200, True, "Limited Edition", "2017, 888-piece LE, amethyst inlay"),
        ("Patron of Art Napoleon Bonaparte 4810", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 550, True, "Limited Edition", "2021, 4810 pcs, imperial eagle motif"),
        ("Patron of Art Napoleon Bonaparte 888", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 2500, True, "Limited Edition", "2021, 888-piece LE, gold overlay"),
        ("Patron of Art Scipione Borghese 4810", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 550, True, "Limited Edition", "2022, 4810 pcs, Roman Baroque motifs"),
        ("Patron of Art Scipione Borghese 888", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 2300, True, "Limited Edition", "2022, 888-piece LE, marble inlay"),
        ("Patron of Art Homage to Albert 888", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 2200, True, "Limited Edition", "2023, 888-piece LE, Victorian flair"),
    ]


def _montblanc_writers_edition_le() -> list[tuple]:
    """~20 Montblanc Writers Edition LE fountain pens — ones not already in catalog."""
    return [
        ("Writers Edition Voltaire", "Montblanc", "Writers Edition", "18k Gold", "M",
         "piston", 2000, True, "Grail", "1995 LE, French Enlightenment tribute"),
        ("Writers Edition Alexandre Dumas", "Montblanc", "Writers Edition", "18k Gold", "M",
         "piston", 1800, True, "Grail", "1996 LE, Three Musketeers motif"),
        ("Writers Edition Fyodor Dostoevsky", "Montblanc", "Writers Edition", "18k Gold", "M",
         "piston", 1200, True, "Limited Edition", "1997 LE, Russian literary tribute"),
        ("Writers Edition Edgar Allan Poe", "Montblanc", "Writers Edition", "18k Gold", "M",
         "piston", 2500, True, "Grail", "1998 LE, raven clip, dark lacquer"),
        ("Writers Edition Jules Verne", "Montblanc", "Writers Edition", "18k Gold", "M",
         "piston", 1000, True, "Limited Edition", "2003 LE, submarine porthole cap"),
        ("Writers Edition Franz Kafka", "Montblanc", "Writers Edition", "18k Gold", "M",
         "piston", 900, True, "Limited Edition", "2004 LE, metamorphosis-inspired design"),
        ("Writers Edition Miguel de Cervantes", "Montblanc", "Writers Edition", "18k Gold", "F",
         "piston", 800, True, "Limited Edition", "2005 LE, Don Quixote motif"),
        ("Writers Edition Virginia Woolf", "Montblanc", "Writers Edition", "18k Gold", "F",
         "piston", 800, True, "Limited Edition", "2006 LE, bloomsbury-inspired design"),
        ("Writers Edition Oscar Wilde", "Montblanc", "Writers Edition", "18k Gold", "M",
         "piston", 550, True, "Limited Edition", "2016 LE, green carnation clip"),
        ("Writers Edition Honoré de Balzac", "Montblanc", "Writers Edition", "18k Gold", "M",
         "piston", 500, True, "Limited Edition", "2013 LE, Comédie Humaine tribute"),
        ("Writers Edition Carlo Collodi", "Montblanc", "Writers Edition", "18k Gold", "M",
         "piston", 500, True, "Limited Edition", "2011 LE, Pinocchio-inspired design"),
        ("Writers Edition Jonathan Swift", "Montblanc", "Writers Edition", "18k Gold", "M",
         "piston", 480, True, "Limited Edition", "2012 LE, Gulliver motif"),
        ("Writers Edition F. Scott Fitzgerald", "Montblanc", "Writers Edition", "18k Gold", "B",
         "piston", 450, True, "Limited Edition", "2023 LE, Jazz Age art deco"),
    ]


def _montblanc_great_characters_le() -> list[tuple]:
    """~12 Montblanc Great Characters LE fountain pens — additions not already in catalog."""
    return [
        ("Great Characters Albert Einstein", "Montblanc", "Great Characters", "18k Gold", "M",
         "piston", 900, True, "Limited Edition", "2012 LE, E=mc² engraving, grey lacquer"),
        ("Great Characters James Dean", "Montblanc", "Great Characters", "18k Gold", "M",
         "piston", 650, True, "Limited Edition", "2018 LE, rebel red lacquer"),
        ("Great Characters Mahatma Gandhi", "Montblanc", "Great Characters", "18k Gold", "M",
         "piston", 800, True, "Limited Edition", "2009 LE, cotton-white, mandarin orange"),
        ("Great Characters John Lennon", "Montblanc", "Great Characters", "18k Gold", "M",
         "piston", 900, True, "Limited Edition", "2010 LE, peace symbol, white lacquer"),
        ("Great Characters Che Guevara", "Montblanc", "Great Characters", "18k Gold", "M",
         "piston", 600, True, "Limited Edition", "Revolutionary red lacquer, star clip"),
        ("Great Characters Alfred Hitchcock", "Montblanc", "Great Characters", "18k Gold", "M",
         "piston", 700, True, "Limited Edition", "2014 LE, Birds silhouette, suspense design"),
        ("Great Characters Marilyn Monroe", "Montblanc", "Great Characters", "18k Gold", "F",
         "piston", 500, True, "Limited Edition", "2023 LE, pearl white lacquer, pink accents"),
        ("Great Characters Napoleon LE", "Montblanc", "Great Characters", "18k Gold", "M",
         "piston", 750, True, "Limited Edition", "2021 LE, tricorne-inspired cap"),
        ("Great Characters Marco Polo", "Montblanc", "Great Characters", "18k Gold", "M",
         "piston", 650, True, "Limited Edition", "Silk Road motif, jade lacquer"),
    ]


def _montblanc_high_artistry() -> list[tuple]:
    """10 Montblanc High Artistry fountain pens — ultra-premium collector pieces."""
    return [
        ("High Artistry Homage to Hannibal Barca", "Montblanc", "High Artistry", "18k Gold", "M",
         "piston", 25000, True, "Grail", "Skeleton pen, LE 86, Carthaginian warrior motif"),
        ("High Artistry Tribute to the Taj Mahal", "Montblanc", "High Artistry", "18k Gold", "M",
         "piston", 30000, True, "Grail", "LE 65, white gold, diamond-set, Mughal art"),
        ("High Artistry Celebration of the Silk Road", "Montblanc", "High Artistry", "18k Gold", "M",
         "piston", 20000, True, "Grail", "LE 88, lapis lazuli, jade, gold overlay"),
        ("High Artistry Homage to Vincent van Gogh", "Montblanc", "High Artistry", "18k Gold", "M",
         "piston", 15000, True, "Grail", "LE 90, Starry Night maki-e, gold filigree"),
        ("High Artistry Meisterstueck Solitaire Skeleton 149", "Montblanc", "High Artistry", "18k Gold", "M",
         "piston", 5000, True, "Grail", "Skeletonized 149, visible mechanism"),
        ("High Artistry Around the World in 80 Days", "Montblanc", "High Artistry", "18k Gold", "M",
         "piston", 18000, True, "Grail", "LE 80, Jules Verne tribute, globe motif"),
        ("High Artistry Dragon LE 888", "Montblanc", "High Artistry", "18k Gold", "M",
         "piston", 8000, True, "Grail", "888-piece LE, dragon engraving, jade accent"),
        ("High Artistry Inca LE 125", "Montblanc", "High Artistry", "18k Gold", "M",
         "piston", 12000, True, "Grail", "LE 125, Peruvian gold motifs, turquoise"),
        ("High Artistry Zodiac LE 88", "Montblanc", "High Artistry", "18k Gold", "M",
         "piston", 10000, True, "Grail", "LE 88, celestial engraving, mother of pearl"),
        ("High Artistry Venetian Art LE 81", "Montblanc", "High Artistry", "18k Gold", "M",
         "piston", 9000, True, "Grail", "LE 81, Murano glass-inspired, gold leaf"),
    ]


def _montblanc_meisterstueck_special() -> list[tuple]:
    """10 Montblanc Meisterstück Special Edition fountain pens."""
    return [
        ("Meisterstueck 149 Diamond LE", "Montblanc", "Meisterstueck", "18k Gold", "M",
         "piston", 4000, True, "Grail", "Diamond-set cap band, limited production"),
        ("Meisterstueck 149 Solitaire Gold & Black", "Montblanc", "Meisterstueck", "18k Gold", "M",
         "piston", 1200, False, "Limited Edition", "Gold-plated barrel, black resin cap"),
        ("Meisterstueck 149 Solitaire Doué", "Montblanc", "Meisterstueck", "18k Gold", "M",
         "piston", 800, False, "Limited Edition", "Sterling silver lower barrel, black cap"),
        ("Meisterstueck 149 Solitaire Blue Hour", "Montblanc", "Meisterstueck", "18k Gold", "M",
         "piston", 900, True, "Limited Edition", "Blue lacquer with diamond pattern"),
        ("Meisterstueck 149 Platinum Line", "Montblanc", "Meisterstueck", "18k Gold", "M",
         "piston", 600, False, "Standard", "Platinum-coated fittings, classic black"),
        ("Meisterstueck 149 Red Gold", "Montblanc", "Meisterstueck", "18k Gold", "M",
         "piston", 1000, False, "Limited Edition", "Rose gold fittings, warm tone"),
        ("Meisterstueck LeGrand Solitaire Carbon Steel", "Montblanc", "Meisterstueck", "18k Gold", "M",
         "piston", 700, False, "Limited Edition", "Carbon fiber barrel, steel fittings"),
        ("Meisterstueck Around the World in 80 Days LeGrand", "Montblanc", "Meisterstueck", "18k Gold", "M",
         "piston", 550, True, "Limited Edition", "Jules Verne tribute, brown lacquer"),
        ("Meisterstueck Great Masters Calligraphy Solitaire", "Montblanc", "Meisterstueck", "18k Gold", "M",
         "piston", 800, True, "Limited Edition", "Calligraphy-engraved barrel"),
        ("Meisterstueck 100th Anniversary 2006 LE", "Montblanc", "Meisterstueck", "18k Gold", "M",
         "piston", 3000, True, "Grail", "2006 centennial edition, diamond-set, 18k trim"),
    ]


def _expanded_pelikan_round7() -> list[tuple]:
    """20 Pelikan fountain pens — Souveran, Toledo, Raden, special editions."""
    return [
        ("Souveraen M800 Green-Black", "Pelikan", "Souveraen", "18k Gold", "F",
         "piston", 550, False, "Standard", "Classic green stripes, fine nib variant"),
        ("Souveraen M800 Brown-Black", "Pelikan", "Souveraen", "18k Gold", "B",
         "piston", 600, True, "Limited Edition", "Special edition brown tortoiseshell"),
        ("Souveraen M800 Burnt Orange", "Pelikan", "Souveraen", "18k Gold", "M",
         "piston", 750, True, "Limited Edition", "Special edition, autumn colorway"),
        ("Souveraen M1000 Green-Black", "Pelikan", "Souveraen", "18k Gold", "M",
         "piston", 750, False, "Standard", "Oversized, green stripes"),
        ("Toledo M710", "Pelikan", "Toledo", "18k Gold", "M",
         "piston", 800, False, "Standard", "Hand-engraved gold-plated barrel"),
        ("M800 Raden Royal Gold", "Pelikan", "Souveraen", "18k Gold", "M",
         "piston", 1500, True, "Limited Edition", "Raden mother-of-pearl, gold stripes"),
        ("M800 Raden Royal Platinum", "Pelikan", "Souveraen", "18k Gold", "F",
         "piston", 1500, True, "Limited Edition", "Raden mother-of-pearl, silver stripes"),
        ("M600 Souveraen Red-Black", "Pelikan", "Souveraen", "14k Gold", "M",
         "piston", 400, False, "Standard", "Red stripes, classic mid-size"),
        ("M600 Souveraen Tortoiseshell Red", "Pelikan", "Souveraen", "14k Gold", "F",
         "piston", 450, True, "Limited Edition", "Vivid red tortoiseshell pattern"),
        ("M400 Souveraen Blue-Black", "Pelikan", "Souveraen", "14k Gold", "EF",
         "piston", 320, False, "Standard", "Compact size, blue stripes"),
        ("M800 Art Collection Rock", "Pelikan", "Art Collection", "18k Gold", "B",
         "piston", 900, True, "Limited Edition", "2020 LE, volcanic red-black resin"),
        ("M800 Art Collection Ocean", "Pelikan", "Art Collection", "18k Gold", "M",
         "piston", 880, True, "Limited Edition", "2019 LE, deep ocean blue-green resin"),
        ("M805 Stresemann Anthracite", "Pelikan", "Souveraen", "18k Gold", "M",
         "piston", 600, True, "Limited Edition", "Pinstripe anthracite, silver trim"),
        ("M205 Star Ruby", "Pelikan", "Classic", "Steel", "F",
         "piston", 140, True, "Limited Edition", "Red transparent demonstrator"),
        ("M205 Aquamarine", "Pelikan", "Classic", "Steel", "M",
         "piston", 140, True, "Limited Edition", "Light blue transparent"),
        ("Souveraen M800 Golf Edition Green", "Pelikan", "Souveraen", "18k Gold", "M",
         "piston", 700, True, "Limited Edition", "Golf-green resin, club clip"),
        ("M600 Souveraen Turquoise", "Pelikan", "Souveraen", "14k Gold", "M",
         "piston", 420, True, "Limited Edition", "Vibrant turquoise stripes"),
        ("M1000 Black-Green", "Pelikan", "Souveraen", "18k Gold", "B",
         "piston", 780, False, "Standard", "Full-size, green stripes, broad nib"),
        ("Toledo M915 Grand", "Pelikan", "Toledo", "18k Gold", "M",
         "piston", 3500, True, "Limited Edition", "Grand Toledo, full-body engraving"),
        ("Souveraen M600 Vibrant Blue", "Pelikan", "Souveraen", "14k Gold", "M",
         "piston", 420, True, "Limited Edition", "Special edition bright blue stripes"),
    ]


def _expanded_sailor_round7() -> list[tuple]:
    """20 Sailor fountain pens — KoP, Pro Gear, 1911, Wancher collabs, Shikiori."""
    return [
        ("King of Pen ST Demonstrator", "Sailor", "King of Pen", "21k Gold", "M",
         "converter", 900, True, "Limited Edition", "Transparent KoP, oversized"),
        ("Pro Gear Black Luster", "Sailor", "Pro Gear", "21k Gold", "M",
         "converter", 450, True, "Limited Edition", "Matte black ion-plated trim"),
        ("Pro Gear Imperial Black", "Sailor", "Pro Gear", "21k Gold", "B",
         "converter", 500, True, "Limited Edition", "All-black rhodium trim"),
        ("Pro Gear Slim Shikiori Ayanami", "Sailor", "Pro Gear Slim", "14k Gold", "MF",
         "converter", 280, True, "Limited Edition", "Four Seasons ocean wave"),
        ("Pro Gear Slim Shikiori Haruzora", "Sailor", "Pro Gear Slim", "14k Gold", "M",
         "converter", 280, True, "Limited Edition", "Four Seasons spring sky"),
        ("Pro Gear Slim Shikiori Shimoyo", "Sailor", "Pro Gear Slim", "14k Gold", "F",
         "converter", 280, True, "Limited Edition", "Four Seasons frost night"),
        ("1911 Large Stormy Sea", "Sailor", "1911", "21k Gold", "M",
         "converter", 500, True, "Limited Edition", "Deep teal resin, gold trim"),
        ("Pro Gear x Wancher Stardust Galaxy", "Sailor", "Pro Gear", "21k Gold", "MF",
         "converter", 600, True, "Limited Edition", "Wancher exclusive, galaxy sparkle"),
        ("Pro Gear x Wancher Turquoise Blue", "Sailor", "Pro Gear", "21k Gold", "M",
         "converter", 550, True, "Limited Edition", "Wancher exclusive, vivid turquoise"),
        ("1911 Standard Fresca Blue", "Sailor", "1911", "14k Gold", "MF",
         "converter", 260, True, "Limited Edition", "Ink-studio matching pen"),
        ("Pro Gear Slim Mini Gold Transparent", "Sailor", "Pro Gear Slim", "14k Gold", "F",
         "converter", 220, True, "Limited Edition", "Compact transparent, gold trim"),
        ("1911 Large Realo Ocean", "Sailor", "1911", "21k Gold", "M",
         "piston", 650, True, "Limited Edition", "Piston-fill 1911, ocean blue"),
        ("King of Pen Bespoke Ama-Iro", "Sailor", "Bespoke", "21k Gold", "M",
         "converter", 1400, True, "Limited Edition", "Wancher exclusive, sky blue urushi"),
        ("Pro Gear Cocktail Series Mojito", "Sailor", "Pro Gear", "21k Gold", "MF",
         "converter", 450, True, "Limited Edition", "Cocktail series, lime green"),
        ("Pro Gear Cocktail Series Old Fashioned", "Sailor", "Pro Gear", "21k Gold", "M",
         "converter", 450, True, "Limited Edition", "Cocktail series, amber gold"),
        ("1911 Profit Standard Demonstrator", "Sailor", "1911", "14k Gold", "F",
         "converter", 250, False, "Standard", "Clear body demonstrator"),
        ("Pro Gear Fire Special Edition", "Sailor", "Pro Gear", "21k Gold", "M",
         "converter", 500, True, "Limited Edition", "Flame red resin, rhodium trim"),
        ("King of Pen Bespoke Ebonite Aka", "Sailor", "Bespoke", "21k Gold", "B",
         "converter", 1600, True, "Limited Edition", "Red ebonite, urushi accent"),
        ("Pro Gear Slim White Russian", "Sailor", "Pro Gear Slim", "14k Gold", "MF",
         "converter", 300, True, "Limited Edition", "Cocktail series, cream/coffee"),
        ("1911 Large Naginata Emperor", "Sailor", "1911", "21k Gold", "Naginata Emperor",
         "converter", 1200, False, "Standard", "Triple-point specialty nib, rare"),
    ]


def _expanded_pilot_round7() -> list[tuple]:
    """15 Pilot fountain pens — Namiki Emperor, Yukari Royale, Custom, VP LE."""
    return [
        ("Namiki Emperor Vermillion", "Pilot", "Namiki Emperor", "18k Gold", "M",
         "converter", 8000, True, "Limited Edition", "Large maki-e, vermillion urushi"),
        ("Namiki Yukari Royale Pine", "Pilot", "Namiki Yukari Royale", "18k Gold", "M",
         "converter", 4000, True, "Limited Edition", "Togidashi maki-e pine motif"),
        ("Custom 823 Clear", "Pilot", "Custom", "14k Gold", "B",
         "vacuum", 320, False, "Standard", "Clear demonstrator, vacuum fill"),
        ("Custom 743 Black", "Pilot", "Custom", "14k Gold", "M",
         "converter", 280, False, "Standard", "Size 15 nib, black resin"),
        ("Custom Heritage 912 FA", "Pilot", "Custom Heritage", "14k Gold", "FA",
         "converter", 250, False, "Standard", "Falcon soft nib, popular flex"),
        ("Custom Heritage 912 PO", "Pilot", "Custom Heritage", "14k Gold", "PO",
         "converter", 250, False, "Standard", "Posting nib, ultra-fine writing"),
        ("Vanishing Point LE Tropical Turquoise", "Pilot", "Vanishing Point", "18k Gold", "M",
         "converter", 250, True, "Limited Edition", "Annual LE color, turquoise body"),
        ("Vanishing Point LE Crimson Sunrise", "Pilot", "Vanishing Point", "18k Gold", "F",
         "converter", 250, True, "Limited Edition", "Annual LE, red-gold gradient"),
        ("Vanishing Point Carbonesque", "Pilot", "Vanishing Point", "18k Gold", "M",
         "converter", 280, True, "Limited Edition", "Carbon fiber weave pattern"),
        ("Justus 95 Black", "Pilot", "Justus", "14k Gold", "M",
         "converter", 350, False, "Standard", "Adjustable nib flexibility"),
        ("Namiki Emperor Chrysanthemum", "Pilot", "Namiki Emperor", "18k Gold", "B",
         "converter", 9500, True, "Limited Edition", "Taka maki-e chrysanthemum"),
        ("Custom Urushi Blue", "Pilot", "Custom Urushi", "18k Gold", "M",
         "converter", 850, False, "Standard", "Blue urushi lacquer, 30-layer"),
        ("Custom 845 Black", "Pilot", "Custom", "18k Gold", "M",
         "converter", 450, False, "Standard", "Ebonite feed, large size"),
        ("Namiki Falcon Resin Black", "Pilot", "Namiki", "14k Gold (Soft)", "M",
         "converter", 180, False, "Standard", "Resin barrel, semi-flex nib"),
        ("Vanishing Point Matte Blue", "Pilot", "Vanishing Point", "18k Gold", "F",
         "converter", 220, False, "Standard", "Matte blue finish, retractable"),
    ]


def _expanded_nakaya_round7() -> list[tuple]:
    """10 Nakaya fountain pens — various models and urushi finishes."""
    return [
        ("Dorsal Fin Version 2 Heki-Tamenuri", "Nakaya", "Dorsal Fin", "14k Gold", "M",
         "converter", 1300, False, "Standard", "Green-tinged tamenuri urushi"),
        ("Naka-ai Writer Aka-Tamenuri", "Nakaya", "Naka-ai", "14k Gold", "F",
         "converter", 1100, False, "Standard", "Red tamenuri, capped writer"),
        ("Portable Writer Aka-Tamenuri", "Nakaya", "Portable", "14k Gold", "M",
         "converter", 950, False, "Standard", "Vermillion tamenuri, pocket size"),
        ("Cigar Long Kuro-Roiro", "Nakaya", "Cigar", "14k Gold", "M",
         "converter", 1000, False, "Standard", "Deep mirror-black roiro urushi"),
        ("Piccolo Long Cigar Kuro-Tamenuri", "Nakaya", "Piccolo", "14k Gold", "F",
         "converter", 800, False, "Standard", "Black tamenuri, compact body"),
        ("Decapod Twist Midori-Tamenuri", "Nakaya", "Decapod", "14k Gold", "M",
         "converter", 1500, False, "Standard", "Green tamenuri, faceted twist"),
        ("Dorsal Fin Version 1 Chinkin Pine", "Nakaya", "Dorsal Fin", "14k Gold", "M",
         "converter", 2500, True, "Limited Edition", "Chinkin hand-engraved pine motif"),
        ("Naka-ai Writer Maki-e Crane", "Nakaya", "Naka-ai", "14k Gold", "M",
         "converter", 3000, True, "Limited Edition", "Custom maki-e crane artwork"),
        ("Portable Writer Chinkin Wave", "Nakaya", "Portable", "14k Gold", "F",
         "converter", 2200, True, "Limited Edition", "Chinkin wave pattern, pocket size"),
        ("Long Cigar Shu-Kuro", "Nakaya", "Cigar", "14k Gold", "B",
         "converter", 1050, False, "Standard", "Deep red-black layered urushi"),
    ]


def _expanded_visconti_round7() -> list[tuple]:
    """10 Visconti fountain pens — Homo Sapiens, Medici, Opera Master, Rembrandt."""
    return [
        ("Homo Sapiens Lava Magma", "Visconti", "Homo Sapiens", "Palladium", "M",
         "vacuum", 800, True, "Limited Edition", "Red lava, magma resin accents"),
        ("Homo Sapiens Crystal Swirl", "Visconti", "Homo Sapiens", "Palladium", "F",
         "vacuum", 950, True, "Limited Edition", "Crystal demonstrator, swirl pattern"),
        ("Homo Sapiens Bronze Maori", "Visconti", "Homo Sapiens", "Palladium", "B",
         "vacuum", 850, True, "Limited Edition", "Maori tribal engraving on bronze"),
        ("Medici Fountain Pen", "Visconti", "Medici", "18k Gold", "M",
         "vacuum", 1500, True, "Limited Edition", "Florentine design, gold accents"),
        ("Opera Master Corsica", "Visconti", "Opera Master", "18k Gold", "M",
         "vacuum", 1300, True, "Limited Edition", "Corsican celluloid, vivid patterns"),
        ("Rembrandt Van Gogh Irises", "Visconti", "Van Gogh", "Steel", "M",
         "converter", 300, False, "Standard", "Blue iris-inspired resin"),
        ("Rembrandt Van Gogh Sunflowers", "Visconti", "Van Gogh", "Steel", "F",
         "converter", 300, False, "Standard", "Yellow sunflower resin"),
        ("Wall Street Grey", "Visconti", "Wall Street", "Palladium", "M",
         "vacuum", 580, False, "Standard", "Grey pinstripe celluloid"),
        ("Opera Master Le Stagioni", "Visconti", "Opera Master", "18k Gold", "M",
         "vacuum", 1200, True, "Limited Edition", "Four Seasons celluloid"),
        ("Homo Sapiens Elegance Oversize", "Visconti", "Homo Sapiens", "Palladium", "B",
         "vacuum", 900, False, "Standard", "Oversize barrel, black lava"),
    ]


def _expanded_aurora_round7() -> list[tuple]:
    """10 Aurora fountain pens — 88, Optima, Minerali, Talentum, Ipsilon."""
    return [
        ("Optima Flex Blue", "Aurora", "Optima", "18k Gold", "F",
         "piston", 600, False, "Standard", "Flexible nib, blue Auroloide"),
        ("88 Sigaro Arancio", "Aurora", "88", "18k Gold", "M",
         "piston", 650, True, "Limited Edition", "Orange cigar shape, annual LE"),
        ("Minerali Amber", "Aurora", "Minerali", "Steel", "M",
         "piston", 250, False, "Standard", "Mineral-inspired resin, entry Italian pen"),
        ("Minerali Emerald", "Aurora", "Minerali", "Steel", "F",
         "piston", 250, False, "Standard", "Emerald green mineral resin"),
        ("Talentum Black-Rose Gold", "Aurora", "Talentum", "14k Gold", "M",
         "converter", 300, False, "Standard", "Rose gold trim, modern style"),
        ("Ipsilon Quadra Green", "Aurora", "Ipsilon", "Steel", "M",
         "converter", 100, False, "Standard", "Square barrel design, entry model"),
        ("Optima 365 Tortoiseshell", "Aurora", "Optima", "18k Gold", "M",
         "piston", 700, True, "Limited Edition", "365-piece LE, brown tortoiseshell"),
        ("88 Nebulosa Blue", "Aurora", "88", "18k Gold", "B",
         "piston", 700, True, "Limited Edition", "Nebula-blue resin, annual edition"),
        ("Internazionale Limited Art Deco", "Aurora", "Internazionale", "18k Gold", "M",
         "piston", 800, True, "Limited Edition", "Art Deco-inspired, geometric pattern"),
        ("Optima Mare Blue", "Aurora", "Optima", "18k Gold", "F",
         "piston", 580, True, "Limited Edition", "Sea-blue Auroloide, limited run"),
    ]


def _expanded_lamy_round7() -> list[tuple]:
    """10 Lamy fountain pens — 2000, Dialog 3, Safari LE, Al-Star LE, Studio, Imporium."""
    return [
        ("2000 Taxus Brown", "Lamy", "2000", "14k Gold", "M",
         "piston", 450, True, "Limited Edition", "2024 LE, warm brown Makrolon"),
        ("Dialog 3 Piano White", "Lamy", "Dialog", "14k Gold", "F",
         "converter", 400, False, "Standard", "White lacquer, retractable nib"),
        ("Safari Violet Blackberry", "Lamy", "Safari", "Steel", "F",
         "converter", 75, True, "Limited Edition", "2024 annual color"),
        ("Safari Candy Aquamarine", "Lamy", "Safari", "Steel", "M",
         "converter", 70, True, "Limited Edition", "2020 annual color, pastel aqua"),
        ("Al-Star Pacific Blue", "Lamy", "Al-Star", "Steel", "M",
         "converter", 45, True, "Limited Edition", "2017 annual aluminum color"),
        ("Studio Olive Silver", "Lamy", "Studio", "Steel", "F",
         "converter", 100, False, "Standard", "Olive green lacquer, propeller clip"),
        ("Imporium Black-Gold", "Lamy", "Imporium", "14k Gold", "M",
         "converter", 500, False, "Standard", "Premium line, matt black PVD, gold accents"),
        ("Safari All-Black Ncode", "Lamy", "Safari", "Steel", "M",
         "converter", 90, True, "Limited Edition", "2019 stealth matte edition"),
        ("2000 Blue Bauhaus", "Lamy", "2000", "14k Gold", "F",
         "piston", 500, True, "Limited Edition", "100th Bauhaus anniversary, blue Makrolon"),
        ("Al-Star Cosmic Black", "Lamy", "Al-Star", "Steel", "M",
         "converter", 45, True, "Limited Edition", "2022 annual color, sparkle black"),
    ]


def _expanded_platinum_round7() -> list[tuple]:
    """8 Platinum fountain pens — 3776 Century variants, President, Izumo."""
    return [
        ("3776 Century Nice Lavande", "Platinum", "#3776 Century", "14k Gold", "M",
         "converter", 200, True, "Limited Edition", "Nice series, lavender resin"),
        ("3776 Century Chartres Blue", "Platinum", "#3776 Century", "14k Gold", "M",
         "converter", 180, False, "Standard", "Cathedral stained-glass blue"),
        ("3776 Century Bourgogne", "Platinum", "#3776 Century", "14k Gold", "F",
         "converter", 180, False, "Standard", "Burgundy red, gold trim"),
        ("3776 Century Black Diamond", "Platinum", "#3776 Century", "14k Gold", "M",
         "converter", 180, False, "Standard", "Translucent black, rhodium trim"),
        ("3776 Century Shape of Heart Burgundy", "Platinum", "#3776 Century", "14k Gold", "B",
         "converter", 200, True, "Limited Edition", "Heart-shaped barrel profile"),
        ("President Black-Gold", "Platinum", "President", "18k Gold", "M",
         "converter", 500, False, "Standard", "Oversize, 18k nib, gold accents"),
        ("Izumo Tamenuri Akame", "Platinum", "Izumo", "18k Gold", "M",
         "converter", 1600, False, "Standard", "Red-eye tamenuri, Izumo region lacquer"),
        ("3776 Century Fuji Shizuku", "Platinum", "#3776 Century", "14k Gold", "F",
         "converter", 200, True, "Limited Edition", "Mt Fuji-inspired translucent blue"),
    ]


def _expanded_twsbi_round7() -> list[tuple]:
    """8 TWSBI fountain pens — ECO, Diamond 580, Precision, VAC700R, Mini AL."""
    return [
        ("ECO Clear", "TWSBI", "ECO", "Steel", "M",
         "piston", 35, False, "Standard", "Transparent piston filler, high capacity"),
        ("ECO Jade Green", "TWSBI", "ECO", "Steel", "F",
         "piston", 35, True, "Limited Edition", "Limited jade green demonstrator"),
        ("ECO Smoke Rose Gold", "TWSBI", "ECO", "Steel", "M",
         "piston", 40, True, "Limited Edition", "Smoke grey, rose gold trim"),
        ("Diamond 580 ALR Nickel Grey", "TWSBI", "Diamond 580", "Steel", "M",
         "piston", 65, False, "Standard", "Aluminum grip, nickel grey"),
        ("Diamond 580 AL Lapis Blue", "TWSBI", "Diamond 580", "Steel", "F",
         "piston", 70, True, "Limited Edition", "Aluminum blue, demonstrator"),
        ("Precision Gunmetal", "TWSBI", "Precision", "Steel", "M",
         "piston", 75, False, "Standard", "Fixed-nib, CNC-machined body"),
        ("VAC700R Clear", "TWSBI", "VAC700R", "Steel", "B",
         "vacuum", 70, False, "Standard", "Vacuum-fill, huge ink capacity"),
        ("Mini AL Silver", "TWSBI", "Mini AL", "Steel", "F",
         "piston", 60, False, "Standard", "Compact aluminum, piston-fill"),
    ]


def _expanded_kaweco_round7() -> list[tuple]:
    """7 Kaweco fountain pens — Sport, Special, Student, Dia2."""
    return [
        ("Sport Classic Navy", "Kaweco", "Sport", "Steel", "M",
         "converter", 30, False, "Standard", "Pocket pen icon, snap cap"),
        ("AL Sport Anthracite", "Kaweco", "Sport", "Steel", "F",
         "converter", 80, False, "Standard", "Aluminum body, pocket size"),
        ("Brass Sport Raw", "Kaweco", "Sport", "Steel", "M",
         "converter", 90, False, "Standard", "Raw brass, patina over time"),
        ("Steel Sport", "Kaweco", "Sport", "Steel", "M",
         "converter", 120, False, "Standard", "Stainless steel, weighty pocket pen"),
        ("Special Black Long", "Kaweco", "Special", "Steel", "F",
         "converter", 50, False, "Standard", "Aluminum, minimalist octagonal"),
        ("Student Transparent", "Kaweco", "Student", "Steel", "M",
         "converter", 35, False, "Standard", "Full-size demonstrator"),
        ("Dia2 Black Chrome", "Kaweco", "Dia2", "Steel", "M",
         "converter", 150, False, "Standard", "Classic design, chrome accents"),
    ]


def _expanded_parker_waterman_cross_round7() -> list[tuple]:
    """7 Parker, Waterman, and Cross fountain pens."""
    return [
        ("Duofold Centennial Big Red", "Parker", "Duofold", "18k Gold", "M",
         "converter", 550, False, "Standard", "Classic orange-red, oversized"),
        ("Parker 51 Premium Black GT", "Parker", "51", "18k Gold", "F",
         "converter", 350, False, "Standard", "2020 reissue, gold-trimmed hooded nib"),
        ("Waterman Edson Ruby Red", "Waterman", "Edson", "18k Gold", "M",
         "converter", 700, False, "Standard", "Flagship, ruby red lacquer"),
        ("Waterman Exception Slim Black GT", "Waterman", "Exception", "18k Gold", "F",
         "converter", 400, False, "Standard", "Slim elegance, gold trim"),
        ("Cross Peerless 125 Medalist", "Cross", "Peerless", "18k Gold", "M",
         "converter", 600, False, "Standard", "Flagship Cross, 23k gold plate"),
        ("Parker Sonnet Black Lacquer GT", "Parker", "Sonnet", "18k Gold", "M",
         "converter", 250, False, "Standard", "Mid-range classic, gold nib"),
        ("Waterman Carène Black Sea GT", "Waterman", "Carène", "18k Gold", "F",
         "converter", 350, False, "Standard", "Boat-shaped section, inlaid nib"),
    ]


def _expanded_vintage_round7() -> list[tuple]:
    """15 vintage fountain pens — Parker, Sheaffer, Esterbrook, Eversharp, Swan, Mabie Todd, Conway Stewart."""
    return [
        ("Parker Vacumatic Major Golden Pearl", "Parker", "Vacumatic", "14k Gold", "F",
         "vacuum", 400, False, "Exclusive", "1940s laminated golden celluloid"),
        ("Parker Vacumatic Debutante Azure", "Parker", "Vacumatic", "14k Gold", "F",
         "vacuum", 300, False, "Exclusive", "1930s small size, azure blue pearl"),
        ("Parker 51 Aerometric Teal", "Parker", "51", "14k Gold", "F",
         "aerometric", 280, False, "Exclusive", "1950s, teal barrel, lustraloy cap"),
        ("Sheaffer Snorkel Sentinel Burgundy", "Sheaffer", "Snorkel", "14k Gold", "F",
         "snorkel", 300, False, "Exclusive", "1950s, burgundy barrel, pneumatic fill"),
        ("Sheaffer PFM V Black", "Sheaffer", "PFM", "14k Gold", "M",
         "snorkel", 600, False, "Exclusive", "Pen for Men V, gold-filled cap"),
        ("Esterbrook J Model Copper", "Esterbrook", "J Series", "Steel", "M",
         "lever", 80, False, "Exclusive", "1940s-50s, interchangeable nib unit"),
        ("Esterbrook SJ Green", "Esterbrook", "SJ Series", "Steel", "F",
         "lever", 70, False, "Exclusive", "Short model, green celluloid"),
        ("Eversharp Skyline Blue", "Eversharp", "Skyline", "14k Gold", "M",
         "lever", 250, False, "Exclusive", "1940s Loewy design, blue stripes"),
        ("Eversharp Skyline Executive Green", "Eversharp", "Skyline", "14k Gold", "F",
         "lever", 300, False, "Exclusive", "1940s, dark green, gold derby cap"),
        ("Swan Eternal 46 Black", "Swan", "Eternal", "14k Gold", "F",
         "lever", 200, False, "Exclusive", "1930s, Mabie Todd Swan brand"),
        ("Mabie Todd Swan SM200 Red", "Swan", "SM200", "14k Gold", "M",
         "lever", 250, False, "Exclusive", "1930s, red hard rubber, flexible nib"),
        ("Conklin Crescent Filler Black Chased", "Conklin", "Crescent", "14k Gold (Flex)", "F",
         "crescent", 400, False, "Exclusive", "1910s-20s, chased hard rubber, flex nib"),
        ("Conway Stewart 100 Blue Herringbone", "Conway Stewart", "100", "14k Gold", "M",
         "lever", 350, False, "Exclusive", "1950s English, blue herringbone celluloid"),
        ("Conway Stewart 58 Green Hatched", "Conway Stewart", "58", "14k Gold", "F",
         "lever", 300, False, "Exclusive", "1950s, green cross-hatched pattern"),
        ("Waterman 52 BCHR", "Waterman", "52", "14k Gold (Flex)", "F",
         "eyedropper", 600, False, "Exclusive", "1920s black chased hard rubber, flex"),
    ]


def _additional_round7_overflow() -> list[tuple]:
    """25 additional pens to reach 1020+ — mixed brands, filling gaps."""
    return [
        # ── Montblanc Patron of Art missing 888s ──
        ("Patron of Art Zetkin 888", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 2200, True, "Limited Edition", "2011, 888-piece LE, Art Nouveau gold"),
        ("Patron of Art Peggy Guggenheim LE 80", "Montblanc", "Patron of Art", "18k Gold", "M",
         "piston", 4500, True, "Grail", "2016, LE 80, ultra-premium gold/lapis"),
        # ── Montblanc Writers Edition extras ──
        ("Writers Edition Agatha Christie LE 1200", "Montblanc", "Writers Edition", "18k Gold", "F",
         "piston", 3500, True, "Grail", "1993, LE 1200, snake clip, vermeil cap"),
        # ── Sailor specialty nibs ──
        ("1911 Large Naginata Togi Cross Point", "Sailor", "1911", "21k Gold", "Cross Point",
         "converter", 800, False, "Standard", "Specialty cross-point nib"),
        ("Pro Gear Zoom Nib", "Sailor", "Pro Gear", "21k Gold", "Zoom",
         "converter", 400, False, "Standard", "Specialty zoom nib, ultra-wet"),
        # ── Pelikan extras ──
        ("M800 Art Collection Piazza Navona", "Pelikan", "Art Collection", "18k Gold", "M",
         "piston", 920, True, "Limited Edition", "2018 LE, Italian marble resin"),
        ("M600 Souveraen Violet-White", "Pelikan", "Souveraen", "14k Gold", "F",
         "piston", 430, True, "Limited Edition", "Special edition violet stripes"),
        # ── Pilot extras ──
        ("Vanishing Point LE Purple Haze", "Pilot", "Vanishing Point", "18k Gold", "M",
         "converter", 260, True, "Limited Edition", "Annual LE color, metallic purple"),
        ("Custom Heritage 912 SU", "Pilot", "Custom Heritage", "14k Gold", "SU",
         "converter", 250, False, "Standard", "Stub nib variant, italic writing"),
        ("Namiki Yukari Goldfish", "Pilot", "Namiki Yukari", "18k Gold", "M",
         "converter", 2200, True, "Limited Edition", "Hira maki-e goldfish motif"),
        # ── Visconti extras ──
        ("Homo Sapiens Dual Touch Black", "Visconti", "Homo Sapiens", "Palladium", "M",
         "vacuum", 850, False, "Standard", "Dual-touch nib system"),
        ("Opera Master Demo Cocktail", "Visconti", "Opera Master", "18k Gold", "F",
         "vacuum", 1100, True, "Limited Edition", "Demonstrator celluloid barrel"),
        # ── TWSBI extras ──
        ("Diamond 580 Iris", "TWSBI", "Diamond 580", "Steel", "M",
         "piston", 75, True, "Limited Edition", "Rainbow PVD, iridescent finish"),
        ("ECO-T Mint Blue", "TWSBI", "ECO", "Steel", "F",
         "piston", 35, True, "Limited Edition", "Triangular grip, mint blue"),
        # ── Kaweco extras ──
        ("Liliput Brass", "Kaweco", "Liliput", "Steel", "F",
         "converter", 80, False, "Standard", "Ultra-compact brass pocket pen"),
        ("Sport Classic White", "Kaweco", "Sport", "Steel", "M",
         "converter", 30, False, "Standard", "Classic white pocket pen"),
        # ── Faber-Castell ──
        ("Faber-Castell E-Motion Pure Black", "Faber-Castell", "E-Motion", "Steel", "M",
         "converter", 150, False, "Standard", "Pearwood barrel, chrome accents"),
        ("Faber-Castell Ondoro Graphite", "Faber-Castell", "Ondoro", "Steel", "M",
         "converter", 120, False, "Standard", "Hexagonal graphite barrel"),
        # ── Scribo ──
        ("Scribo Feel Oceano", "Scribo", "Feel", "18k Gold", "M",
         "piston", 500, False, "Standard", "Italian artisan, ocean blue resin"),
        ("Scribo La Dotta Menta", "Scribo", "La Dotta", "18k Gold", "M",
         "piston", 700, True, "Limited Edition", "Bologna tribute, mint celluloid"),
        # ── Conid ──
        ("Conid Bulkfiller Regular Clear Demo", "Conid", "Bulkfiller", "Steel", "M",
         "bulkfiller", 500, False, "Standard", "Belgian engineering, clear demonstrator"),
        # ── Aurora extras ──
        ("Optima 365 Giallo", "Aurora", "Optima", "18k Gold", "M",
         "piston", 680, True, "Limited Edition", "365-piece LE, bright yellow Auroloide"),
        # ── Cross ──
        ("Cross Townsend Black Lacquer", "Cross", "Townsend", "18k Gold", "M",
         "converter", 350, False, "Standard", "Classic oversize, gold appointments"),
        # ── Caran d'Ache ──
        ("Caran d'Ache Léman Caviar", "Caran d'Ache", "Léman", "18k Gold", "F",
         "piston", 750, False, "Standard", "Black guilloche, caviar pattern"),
        # ── Graf von Faber-Castell ──
        ("Pen of the Year 2023 Ancient Egypt", "Graf von Faber-Castell", "Pen of the Year", "18k Gold", "M",
         "converter", 3500, True, "Limited Edition", "Annual LE, Egyptian motifs, gold accents"),
    ]


# ---------------------------------------------------------------------------
# Transform helpers
# ---------------------------------------------------------------------------


def item_to_catalog_item(item: dict) -> CatalogItem:
    """Convert a pen dict to a CatalogItem.

    Sets category='pens', item_key from slugify(brand-model_line-name),
    brand from the pen brand.
    """
    brand = item["brand"]
    name = item["name"]
    model_line = item["model_line"]
    nib_material = item["nib_material"]
    nib_size = item["nib_size"]
    filling_system = item["filling_system"]
    is_limited = item["is_limited"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{brand}-{model_line}-{name}"),
        title=f"{brand} {name}",
        set_code=model_line,
        brand=brand,
        rarity=item["rarity"],
        notes=f"{brand} | {model_line} | {nib_material} {nib_size} | {filling_system} | {item['notes']}",
        attributes_json={
            "brand": brand,
            "model_line": model_line,
            "nib_material": nib_material,
            "nib_size": nib_size,
            "filling_system": filling_system,
            "is_limited": is_limited,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    """Convert a pen dict to a PriceObservation.

    Features:
    - condition_score: 0.85 (assumes excellent for catalog baseline)
    - rarity_score: from shared_rarity_score()
    - brand_tier: 1.0 Montblanc/Nakaya, 0.9 Pelikan/Sailor, 0.8 Pilot/Aurora/Visconti, 0.6 Lamy
    - nib_material: 1.0 gold/palladium, 0.7 steel, 0.5 ruthenium
    - is_limited: 1.0 or 0.0
    """
    brand = item["brand"]
    rarity = item["rarity"]
    nib_material = item["nib_material"]
    is_limited = item["is_limited"]

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(rarity),
            "brand_tier": _brand_tier(brand),
            "nib_material": _nib_material_score(nib_material),
            "is_limited": 1.0 if is_limited else 0.0,
        },
        price=item["price_eur"],
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Import curated fountain pen catalog + prices"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Write local files only, skip Supabase upsert")
    args = parser.parse_args()

    logger.info("=== Fountain Pen Import Pipeline ===")

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    catalog = get_curated_catalog()
    logger.info(f"  Curated catalog: {len(catalog)} fountain pens")

    all_items = [item_to_catalog_item(p) for p in catalog]
    all_observations = [item_to_price_observation(p) for p in catalog]

    # Write catalog SQL
    write_catalog_sql(CATEGORY, all_items)
    log_progress(CATEGORY, "catalog SQL written", len(all_items))

    # Write training JSONL
    write_training_jsonl(CATEGORY, all_observations)
    log_progress(CATEGORY, "training JSONL written", len(all_observations))

    # Upsert to Supabase if enabled
    if ingest.enabled:
        inserted = ingest.upsert_catalog(all_items)
        log_progress(CATEGORY, "catalog upserted", inserted)

    ingest.close()
    close_http_client()

    logger.info(f"\n=== Fountain Pen Import Complete ===")
    logger.info(f"  Total catalog items:  {len(all_items)}")
    logger.info(f"  Price observations:   {len(all_observations)}")
    if args.dry_run:
        logger.info("  Mode: DRY RUN (local files only)")


if __name__ == "__main__":
    main()
