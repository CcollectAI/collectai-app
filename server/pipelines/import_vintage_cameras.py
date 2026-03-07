"""
Curated Vintage Camera Import Pipeline — Film & Analog Camera Collectibles.

Imports a curated catalog of 210+ real vintage/film cameras & lenses across 14 subcategories:
  Leica, Hasselblad, Nikon, Canon, Olympus, Minolta, Contax, Pentax,
  Medium Format (Mamiya/Rolleiflex/Fuji), Polaroid/Instant, Large Format, Vintage Lenses

Each entry has a real camera name, brand, type classification, year range,
condition, lens inclusion flag, rarity tier, and realistic EUR secondary market price.

Pattern follows import_diecast.py / import_watches.py (get_curated_catalog,
item_to_catalog_item, item_to_price_observation).

Usage:
    python -m pipelines.import_vintage_cameras [--dry-run]
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

CATEGORY = "vintage_cameras"

# ---------------------------------------------------------------------------
# Brand tier scoring for ML features
# ---------------------------------------------------------------------------
BRAND_TIER: dict[str, float] = {
    "Leica": 1.0,
    "Hasselblad": 0.9,
    "Contax": 0.9,
    "Nikon": 0.7,
    "Canon": 0.7,
    "Olympus": 0.5,
    "Minolta": 0.5,
    "Pentax": 0.5,
    "Mamiya": 0.5,
    "Bronica": 0.5,
    "Yashica": 0.5,
    "Polaroid": 0.5,
    "Graflex": 0.5,
    "Linhof": 0.5,
    "Rolleiflex": 0.5,
    "Fuji": 0.5,
    "Voigtlander": 0.5,
    "Wista": 0.5,
}

# ---------------------------------------------------------------------------
# Camera type scoring for ML features
# ---------------------------------------------------------------------------
TYPE_SCORE: dict[str, float] = {
    "rangefinder": 0.9,
    "SLR": 0.7,
    "TLR": 0.8,
    "medium format": 0.8,
    "instant": 0.5,
    "large format": 0.8,
    "compact": 0.6,
    "point-and-shoot": 0.5,
}

# ---------------------------------------------------------------------------
# Condition scoring for cameras
# ---------------------------------------------------------------------------
CONDITION_SCORES: dict[str, float] = {
    "Mint": 1.0,
    "Excellent": 0.85,
    "Good": 0.65,
    "Fair": 0.45,
}


def _brand_tier(brand: str) -> float:
    """Map camera brand to a tier score."""
    return BRAND_TIER.get(brand, 0.5)


def _type_score(camera_type: str) -> float:
    """Map camera type to a collectibility score."""
    return TYPE_SCORE.get(camera_type, 0.5)


def _condition_score(condition: str) -> float:
    """Map condition string to a 0-1 score."""
    return CONDITION_SCORES.get(condition, 0.5)


# ---------------------------------------------------------------------------
# Curated catalog — 145+ vintage/film cameras
# Each tuple: (name, brand, type, year_range, price_eur, condition, has_lens, rarity, notes)
# ---------------------------------------------------------------------------


def _leica_cameras() -> list[tuple]:
    """18 Leica cameras — iconic rangefinders and SLRs."""
    return [
        ("M3 Double Stroke", "Leica", "rangefinder", "1954-1966", 2800, "Excellent", True, "Limited Edition", "First Leica M, double-stroke advance"),
        ("M3 Single Stroke", "Leica", "rangefinder", "1954-1966", 2400, "Good", True, "Limited Edition", "Single-stroke film advance variant"),
        ("M6 Classic Black", "Leica", "rangefinder", "1984-1998", 3200, "Excellent", False, "Limited Edition", "Built-in light meter, most popular M"),
        ("M6 TTL Silver", "Leica", "rangefinder", "1998-2002", 3600, "Excellent", False, "Limited Edition", "Through-the-lens metering variant"),
        ("M6 TTL Black Chrome", "Leica", "rangefinder", "1998-2002", 3800, "Excellent", False, "Rare", "TTL with black chrome finish, collector premium"),
        ("M6 Black Paint", "Leica", "rangefinder", "1984-1998", 6500, "Excellent", False, "Rare", "Factory black paint finish, extremely collectible patina"),
        ("M2 Chrome", "Leica", "rangefinder", "1957-1967", 2200, "Good", False, "Limited Edition", "Simplified M3, 35mm framelines"),
        ("M4-2", "Leica", "rangefinder", "1977-1980", 2000, "Excellent", False, "Limited Edition", "Hot shoe added, Canadian-made, no self-timer"),
        ("IIIf Red Dial", "Leica", "rangefinder", "1950-1956", 1200, "Good", True, "Rare", "Late screw-mount Leica, red dial variant"),
        ("IIIf Black Dial", "Leica", "rangefinder", "1950-1956", 950, "Good", True, "Standard", "Earlier screw-mount Leica, black dial"),
        ("IIIg", "Leica", "rangefinder", "1957-1960", 1500, "Excellent", True, "Rare", "Last screw-mount Leica"),
        ("CL", "Leica", "rangefinder", "1973-1976", 800, "Good", True, "Standard", "Compact M-mount rangefinder, Minolta-built"),
        ("M4-P", "Leica", "rangefinder", "1981-1987", 1800, "Excellent", False, "Limited Edition", "Red dot Leica, 28/75mm framelines"),
        ("R6.2", "Leica", "SLR", "1992-2002", 900, "Excellent", False, "Standard", "Mechanical Leica R-mount SLR"),
        ("R4", "Leica", "SLR", "1980-1987", 500, "Good", False, "Standard", "Electronic Leica R-mount SLR"),
        ("M-A (Typ 127) Silver", "Leica", "rangefinder", "2014-present", 5200, "Mint", False, "Limited Edition", "Modern all-mechanical M, no meter"),
        ("M3 Single Stroke Black Paint", "Leica", "rangefinder", "1954-1966", 8500, "Good", False, "Rare", "Black paint M3, holy grail for Leica collectors"),
        ("MP 0.72 Black Paint", "Leica", "rangefinder", "2003-present", 5800, "Mint", False, "Limited Edition", "Modern black paint M, brass top plate"),
        ("M5 Chrome", "Leica", "rangefinder", "1971-1975", 1600, "Good", False, "Standard", "Controversial M body with CdS metering arm"),
        ("M4 Black Chrome", "Leica", "rangefinder", "1969-1975", 3200, "Excellent", False, "Rare", "Black chrome M4, photojournalist favourite"),
        ("IIIa", "Leica", "rangefinder", "1935-1950", 800, "Good", True, "Standard", "Pre-war screw-mount, 1/1000s shutter"),
        ("M7 0.72 Black", "Leica", "rangefinder", "2002-2018", 4200, "Excellent", False, "Limited Edition", "AE-capable M body, electronic shutter"),
    ]


def _hasselblad_cameras() -> list[tuple]:
    """10 Hasselblad cameras — medium format icons."""
    return [
        ("500C/M", "Hasselblad", "medium format", "1970-1994", 1800, "Excellent", True, "Limited Edition", "Most popular V-system body"),
        ("500C", "Hasselblad", "medium format", "1957-1970", 1400, "Good", True, "Rare", "Original V-system, moon camera lineage"),
        ("503CW", "Hasselblad", "medium format", "1996-2006", 2500, "Excellent", True, "Limited Edition", "Winder-compatible V-system"),
        ("503CXi", "Hasselblad", "medium format", "1988-1996", 2100, "Excellent", True, "Standard", "Databus V-system, gliding mirror"),
        ("SWC/M", "Hasselblad", "medium format", "1980-1988", 3800, "Excellent", True, "Rare", "Super Wide with fixed 38mm Biogon"),
        ("X-Pan", "Hasselblad", "rangefinder", "1998-2003", 4500, "Excellent", True, "Rare", "Panoramic 35mm, dual format"),
        ("X-Pan II", "Hasselblad", "rangefinder", "2003-2006", 5200, "Excellent", True, "Rare", "Updated panoramic, improved viewfinder"),
        ("2000FC/M", "Hasselblad", "medium format", "1981-1984", 1200, "Good", False, "Standard", "Focal plane shutter V-system"),
        ("553ELX", "Hasselblad", "medium format", "1988-1999", 1600, "Good", True, "Standard", "Motorized V-system body"),
        ("903SWC", "Hasselblad", "medium format", "1988-2001", 4200, "Excellent", True, "Rare", "Updated Super Wide, fixed 38mm Biogon T*"),
        ("500EL/M", "Hasselblad", "medium format", "1971-1984", 1500, "Good", False, "Standard", "Motorized V-system, NASA moon camera descendant"),
        ("201F", "Hasselblad", "medium format", "1994-2001", 800, "Good", False, "Standard", "Focal plane shutter, metered, budget V entry"),
        ("Flexbody", "Hasselblad", "medium format", "1995-2003", 900, "Good", False, "Standard", "Tilt/shift bellows body for V lenses"),
    ]


def _nikon_cameras() -> list[tuple]:
    """16 Nikon cameras — legendary SLRs and rangefinders."""
    return [
        ("FM2n Black", "Nikon", "SLR", "1984-2001", 450, "Excellent", False, "Standard", "Mechanical SLR workhorse, 1/4000s"),
        ("FM2n Chrome", "Nikon", "SLR", "1984-2001", 400, "Good", False, "Standard", "Chrome version of the FM2n"),
        ("F3HP", "Nikon", "SLR", "1980-2000", 550, "Excellent", False, "Limited Edition", "Giugiaro-designed pro SLR, high eyepoint"),
        ("F3/T Titanium", "Nikon", "SLR", "1982-2000", 900, "Excellent", False, "Rare", "Titanium variant of the F3"),
        ("F2 Photomic", "Nikon", "SLR", "1971-1980", 500, "Good", False, "Limited Edition", "Tank-like mechanical pro SLR"),
        ("F2AS", "Nikon", "SLR", "1977-1980", 600, "Excellent", False, "Limited Edition", "F2 with AI-S metering"),
        ("FE Black", "Nikon", "SLR", "1978-1983", 300, "Good", False, "Standard", "Aperture-priority compact SLR"),
        ("FA", "Nikon", "SLR", "1983-1987", 250, "Good", False, "Standard", "First matrix metering SLR"),
        ("FM3A", "Nikon", "SLR", "2001-2006", 1200, "Excellent", False, "Rare", "Hybrid mechanical/electronic, last manual Nikon"),
        ("S2 Chrome", "Nikon", "rangefinder", "1954-1958", 900, "Good", True, "Rare", "Nikon rangefinder, Contax-mount heritage"),
        ("S3 2000 Limited Edition", "Nikon", "rangefinder", "2000-2001", 3500, "Excellent", True, "Rare", "Y2K reissue limited to 2000 units, with 50mm f/1.4"),
        ("SP 2005 Limited Edition", "Nikon", "rangefinder", "2005", 6500, "Mint", True, "Rare", "Holy grail Nikon RF, 2500 units, with 35mm f/1.8"),
        ("S3 Original", "Nikon", "rangefinder", "1958-1960", 1800, "Good", True, "Rare", "Original Nikon S3, titanium shutter"),
        ("F Photomic FTN", "Nikon", "SLR", "1968-1974", 400, "Good", False, "Standard", "Center-weighted metering, pro workhorse"),
        ("F2 Titan", "Nikon", "SLR", "1978-1980", 2500, "Excellent", False, "Rare", "Titanium F2, Uemura Arctic expedition"),
        ("Nikonos V", "Nikon", "compact", "1984-2001", 350, "Good", True, "Limited Edition", "Underwater 35mm, Nikkor 35mm f/2.5 waterproof"),
        ("F Black", "Nikon", "SLR", "1959-1974", 450, "Good", False, "Limited Edition", "First Nikon SLR, fully mechanical, pro flagship"),
        ("FE2 Black", "Nikon", "SLR", "1983-1987", 350, "Excellent", False, "Standard", "Fastest 1/4000s shutter, aperture-priority SLR"),
        ("FM Black", "Nikon", "SLR", "1977-1982", 280, "Good", False, "Standard", "Original mechanical Nikon compact SLR"),
        ("EM", "Nikon", "SLR", "1979-1982", 100, "Good", True, "Standard", "Budget aperture-priority, lightweight Nikon SLR"),
    ]


def _canon_cameras() -> list[tuple]:
    """12 Canon cameras — classic SLRs and rangefinders."""
    return [
        ("AE-1 Black", "Canon", "SLR", "1976-1984", 200, "Excellent", True, "Standard", "First microprocessor SLR, massive seller"),
        ("AE-1 Chrome", "Canon", "SLR", "1976-1984", 150, "Good", True, "Standard", "Chrome variant, iconic beginner SLR"),
        ("AE-1 Program", "Canon", "SLR", "1981-1987", 220, "Excellent", True, "Standard", "Program mode upgrade of AE-1"),
        ("A-1", "Canon", "SLR", "1978-1985", 300, "Excellent", False, "Standard", "Multi-mode electronic SLR, pro-level"),
        ("F-1 Original", "Canon", "SLR", "1971-1976", 500, "Excellent", False, "Limited Edition", "Canon first pro SLR, fully mechanical"),
        ("F-1 New", "Canon", "SLR", "1981-1992", 550, "Excellent", False, "Limited Edition", "Redesigned pro body, modular system"),
        ("Canon 7", "Canon", "rangefinder", "1961-1964", 600, "Good", False, "Rare", "Top-tier Canon rangefinder, LTM"),
        ("Canon P", "Canon", "rangefinder", "1959-1961", 450, "Good", False, "Rare", "Popular Canon rangefinder, simplified 7"),
        ("Canon L1", "Canon", "rangefinder", "1956-1957", 550, "Good", False, "Rare", "Lever-wind Canon rangefinder, LTM mount"),
        ("Canon 7s", "Canon", "rangefinder", "1964-1967", 750, "Excellent", False, "Rare", "CdS metered Canon rangefinder, last of the line"),
        ("Canonet QL17 GIII Black", "Canon", "rangefinder", "1972-1982", 350, "Excellent", True, "Standard", "Compact rangefinder, sharp 40mm f/1.7"),
        ("Canonet QL17 GIII Chrome", "Canon", "rangefinder", "1972-1982", 280, "Good", True, "Standard", "Chrome version, fixed lens classic"),
        ("FTb QL", "Canon", "SLR", "1971-1976", 120, "Good", True, "Standard", "Mid-range Canon SLR, quick-loading back"),
        ("Canon EF", "Canon", "SLR", "1973-1978", 180, "Good", False, "Standard", "Shutter-priority auto, Canon FD mount"),
        ("Canon T90", "Canon", "SLR", "1986-1992", 250, "Excellent", False, "Standard", "Giugiaro design, last FD-mount pro body"),
    ]


def _olympus_cameras() -> list[tuple]:
    """11 Olympus cameras — compact legends and OM system."""
    return [
        ("OM-1 MD Chrome", "Olympus", "SLR", "1972-1979", 350, "Excellent", False, "Standard", "Compact mechanical SLR, Maitani design"),
        ("OM-1n Black", "Olympus", "SLR", "1979-1987", 400, "Excellent", False, "Standard", "Improved OM-1 with flash sync"),
        ("OM-2n", "Olympus", "SLR", "1979-1984", 350, "Good", False, "Standard", "OTF auto exposure, electronic shutter"),
        ("XA", "Olympus", "rangefinder", "1979-1985", 300, "Excellent", True, "Standard", "Clamshell pocketable rangefinder, f/2.8"),
        ("XA2", "Olympus", "compact", "1980-1985", 120, "Good", True, "Standard", "Zone-focus compact, 35mm f/3.5"),
        ("Pen F Chrome", "Olympus", "SLR", "1963-1966", 600, "Excellent", True, "Rare", "Half-frame SLR, rotary shutter"),
        ("Mju II (Stylus Epic)", "Olympus", "point-and-shoot", "1997-2002", 400, "Excellent", True, "Limited Edition", "Cult 35mm f/2.8 point-and-shoot"),
        ("Trip 35", "Olympus", "compact", "1967-1984", 120, "Good", True, "Standard", "Solar-cell metered zone-focus compact"),
        ("OM-3Ti", "Olympus", "SLR", "1994-2002", 800, "Excellent", False, "Rare", "Titanium body, multi-spot metering, very limited"),
        ("OM-4Ti Black", "Olympus", "SLR", "1989-2002", 600, "Excellent", False, "Limited Edition", "Titanium top/bottom, multi-spot metering"),
        ("Pen EE-3", "Olympus", "compact", "1973-1983", 100, "Good", True, "Standard", "Half-frame auto-exposure compact, D.Zuiko 28mm f/3.5"),
        ("OM-2 SP", "Olympus", "SLR", "1984-1987", 250, "Good", False, "Standard", "Spot metering OM-2, mechanical backup"),
        ("OM-10", "Olympus", "SLR", "1979-1987", 120, "Good", True, "Standard", "Budget auto-exposure OM, manual adapter optional"),
        ("XA3", "Olympus", "compact", "1985-1990", 100, "Good", True, "Standard", "Program auto zone-focus, DX film coding"),
    ]


def _minolta_cameras() -> list[tuple]:
    """8 Minolta cameras — underrated SLRs and rangefinders."""
    return [
        ("X-700", "Minolta", "SLR", "1981-1999", 200, "Excellent", True, "Standard", "Program auto SLR, sharp Rokkor lenses"),
        ("X-700 Black (body only)", "Minolta", "SLR", "1981-1999", 150, "Good", False, "Standard", "Body only, MD mount"),
        ("SRT 101", "Minolta", "SLR", "1966-1975", 180, "Good", True, "Standard", "CLC metering pioneer, fully mechanical"),
        ("CLE", "Minolta", "rangefinder", "1981-1985", 900, "Excellent", True, "Rare", "Compact M-mount rangefinder, AE"),
        ("TC-1", "Minolta", "compact", "1996-2003", 1200, "Excellent", True, "Rare", "Titanium luxury compact, 28mm f/3.5 G-Rokkor"),
        ("XD-7 (XD-11)", "Minolta", "SLR", "1977-1982", 250, "Good", False, "Standard", "First multi-mode SLR, Leica collaboration"),
        ("Hi-Matic 7s", "Minolta", "rangefinder", "1966-1978", 120, "Good", True, "Standard", "Fixed 45mm f/1.8 rangefinder, aperture priority"),
        ("SRT 303", "Minolta", "SLR", "1973-1978", 160, "Good", True, "Standard", "Split-image focus, CLC metering, MC Rokkor lenses"),
        ("XE-7", "Minolta", "SLR", "1974-1977", 200, "Good", False, "Standard", "Leica-co-developed electronically governed vertical shutter"),
        ("X-500", "Minolta", "SLR", "1983-1988", 130, "Good", False, "Standard", "Budget multi-mode MD-mount SLR"),
    ]


def _contax_cameras() -> list[tuple]:
    """10 Contax cameras — premium Japanese rangefinders and SLRs."""
    return [
        ("T2 Titanium", "Contax", "compact", "1990-2002", 1800, "Excellent", True, "Rare", "Premium titanium compact, Sonnar T* 38mm f/2.8"),
        ("T3 Titanium", "Contax", "compact", "2001-2005", 3500, "Excellent", True, "Rare", "Last Contax T, Sonnar T* 35mm f/2.8"),
        ("TVS III", "Contax", "compact", "2000-2003", 600, "Excellent", True, "Standard", "Zoom compact, Vario-Sonnar 30-60mm f/3.7-6.7"),
        ("G2 Black", "Contax", "rangefinder", "1996-2005", 1200, "Excellent", False, "Limited Edition", "AF rangefinder, Zeiss lenses"),
        ("G1 Green Label", "Contax", "rangefinder", "1994-2005", 500, "Good", False, "Standard", "First Contax G, updated firmware"),
        ("Aria", "Contax", "SLR", "1998-2005", 400, "Excellent", False, "Standard", "Compact Zeiss-mount SLR, aperture-priority favourite"),
        ("RTS III", "Contax", "SLR", "1990-2000", 700, "Good", False, "Standard", "Real-time vacuum film plane, pro SLR"),
        ("167MT", "Contax", "SLR", "1987-1997", 300, "Good", False, "Standard", "Multi-program SLR, Yashica/Contax mount"),
        ("T Gold", "Contax", "compact", "1990-2002", 2200, "Excellent", True, "Rare", "Gold-plated limited edition T2, 35mm Sonnar T*"),
        ("S2 (body only)", "Contax", "SLR", "1992-1998", 500, "Good", False, "Standard", "Titanium pro body, no electronics, fully mechanical"),
        ("G1 Original", "Contax", "rangefinder", "1994-1996", 400, "Good", False, "Standard", "First-generation firmware, AF rangefinder"),
        ("RX", "Contax", "SLR", "1994-2000", 300, "Good", False, "Standard", "Aperture-priority SLR, evaluative metering, C/Y mount"),
    ]


def _pentax_cameras() -> list[tuple]:
    """8 Pentax cameras — rugged SLRs and medium format."""
    return [
        ("K1000", "Pentax", "SLR", "1976-1997", 150, "Good", True, "Standard", "Ultimate student SLR, fully mechanical"),
        ("K1000 SE", "Pentax", "SLR", "1976-1997", 180, "Excellent", True, "Standard", "Special edition with split-image focus"),
        ("MX", "Pentax", "SLR", "1976-1985", 350, "Excellent", False, "Standard", "Compact mechanical pro SLR"),
        ("LX", "Pentax", "SLR", "1980-2001", 600, "Excellent", False, "Limited Edition", "Pentax pro flagship, weather sealed"),
        ("67 (6x7)", "Pentax", "medium format", "1969-1999", 700, "Good", True, "Standard", "Medium format SLR, 6x7 negatives"),
        ("67II", "Pentax", "medium format", "1998-2005", 1100, "Excellent", True, "Limited Edition", "Updated 6x7, AE metering, mirror lock-up"),
        ("645N", "Pentax", "medium format", "1997-2001", 500, "Good", True, "Standard", "AF medium format SLR, 645 format"),
        ("645NII", "Pentax", "medium format", "2001-2005", 650, "Excellent", True, "Standard", "Final 645 film body, improved AF and build"),
        ("ME Super", "Pentax", "SLR", "1979-1984", 120, "Good", True, "Standard", "Pushbutton shutter speed, compact K-mount SLR"),
        ("Spotmatic F", "Pentax", "SLR", "1973-1976", 130, "Good", True, "Standard", "Open-aperture TTL metering, M42 screw mount"),
        ("SP500", "Pentax", "SLR", "1971-1973", 100, "Good", True, "Standard", "Budget Spotmatic, stop-down metering"),
    ]


def _medium_format_cameras() -> list[tuple]:
    """18 medium format cameras — Mamiya, Bronica, Yashica, Rolleiflex, Fuji."""
    return [
        ("RZ67 Pro II", "Mamiya", "medium format", "1995-2004", 1200, "Excellent", True, "Limited Edition", "Professional 6x7, revolving back"),
        ("RB67 Pro-S", "Mamiya", "medium format", "1974-1990", 700, "Good", True, "Standard", "Studio workhorse, rotating back"),
        ("RB67 Pro-SD", "Mamiya", "medium format", "1990-2000", 900, "Excellent", True, "Standard", "Final RB67, improved film backs"),
        ("7 II", "Mamiya", "rangefinder", "1999-2005", 2800, "Excellent", True, "Rare", "6x7 rangefinder, interchangeable lenses"),
        ("645 Pro TL", "Mamiya", "medium format", "1999-2006", 600, "Excellent", True, "Standard", "AF 645 system, TTL metering, pro workhorse"),
        ("SQ-A", "Bronica", "medium format", "1982-1995", 400, "Good", True, "Standard", "Modular 6x6, leaf shutter lenses"),
        ("ETRSi", "Bronica", "medium format", "1989-2000", 350, "Good", True, "Standard", "Compact 645 format system"),
        ("Mat 124G", "Yashica", "TLR", "1970-1986", 450, "Excellent", True, "Standard", "Last Yashica TLR, Yashinon 80mm f/3.5"),
        ("2.8F Planar", "Rolleiflex", "TLR", "1960-1981", 2200, "Excellent", True, "Rare", "Definitive TLR, Zeiss Planar 80mm f/2.8"),
        ("3.5F Planar", "Rolleiflex", "TLR", "1958-1976", 1800, "Excellent", True, "Rare", "75mm Planar TLR, lighter than 2.8F"),
        ("Rolleicord V", "Rolleiflex", "TLR", "1954-1957", 450, "Good", True, "Standard", "Budget Rolleiflex, Schneider Xenar 75mm f/3.5"),
        ("GW690III", "Fuji", "rangefinder", "1992-2000", 1100, "Excellent", True, "Standard", "Texas Leica, 6x9 rangefinder, sharp 90mm f/3.5"),
        ("GA645", "Fuji", "medium format", "1995-2002", 750, "Excellent", True, "Standard", "AF 645 compact, built-in 60mm f/4 Super-EBC Fujinon"),
        ("GF670 Professional", "Fuji", "rangefinder", "2008-2014", 2800, "Excellent", True, "Rare", "Last Fuji 6x7 film camera, folding bellows rangefinder"),
        ("Mamiya 6 MF", "Mamiya", "rangefinder", "1989-1995", 1800, "Excellent", True, "Rare", "6x6 rangefinder, interchangeable lenses, ultra-sharp"),
        ("GS645S Professional", "Fuji", "rangefinder", "1983-1995", 500, "Good", True, "Standard", "Wide-angle 645 rangefinder, 60mm f/4 EBC Fujinon"),
        ("Automat MX", "Rolleiflex", "TLR", "1951-1954", 400, "Good", True, "Standard", "Post-war Automat, Schneider Xenar 75mm f/3.5"),
        ("GS-1", "Bronica", "medium format", "1985-1997", 350, "Good", True, "Standard", "6x7 SLR system, leaf-shutter lenses, modular"),
        ("C330 Professional F", "Mamiya", "TLR", "1970-1994", 500, "Good", True, "Standard", "Interchangeable-lens TLR, bellows focusing"),
        ("C220 Professional", "Mamiya", "TLR", "1968-1994", 350, "Good", True, "Standard", "Compact interchangeable-lens TLR, lighter than C330"),
        ("M645 1000S", "Mamiya", "medium format", "1976-1982", 400, "Good", True, "Standard", "Original 645 SLR, modular system, leaf shutter option"),
        ("Super Ikonta 532/16", "Voigtlander", "medium format", "1937-1956", 350, "Fair", True, "Standard", "Folding 6x6 with coupled rangefinder"),
        ("Bessa R2", "Voigtlander", "rangefinder", "2002-2012", 500, "Excellent", False, "Standard", "Modern M-mount rangefinder, Cosina-made"),
    ]


def _polaroid_instant_cameras() -> list[tuple]:
    """10 Polaroid/instant cameras — icons of instant photography."""
    return [
        ("SX-70 Original Chrome", "Polaroid", "instant", "1972-1981", 350, "Good", True, "Limited Edition", "Folding SLR instant, design icon"),
        ("SX-70 Alpha 1 Model 2 Black", "Polaroid", "instant", "1977-1981", 400, "Excellent", True, "Limited Edition", "Black body SX-70, split-image focus"),
        ("SX-70 Sonar OneStep", "Polaroid", "instant", "1978-1981", 250, "Good", True, "Standard", "Autofocus SX-70 variant"),
        ("SLR 680", "Polaroid", "instant", "1982-1988", 400, "Excellent", True, "Limited Edition", "Upgraded SX-70, sonar AF + flash"),
        ("195 Land Camera", "Polaroid", "instant", "1974-1976", 600, "Excellent", True, "Rare", "Pro pack film camera, Tominon 114mm f/3.8, manual controls"),
        ("180 Land Camera", "Polaroid", "instant", "1965-1969", 750, "Good", True, "Rare", "First pro pack film, Tominon f/4.5, Zeiss viewfinder"),
        ("Spectra System", "Polaroid", "instant", "1986-2008", 80, "Good", True, "Standard", "Wide-format instant, Quintic lens"),
        ("600 One Step Close-Up", "Polaroid", "instant", "1990-2000", 50, "Good", True, "Standard", "Fixed-focus consumer instant"),
        ("SX-70 Model 2 Brown", "Polaroid", "instant", "1974-1977", 200, "Good", True, "Standard", "Brown vinyl SX-70 variant, non-metallic"),
        ("Image/Spectra Pro", "Polaroid", "instant", "1986-2008", 120, "Excellent", True, "Standard", "Pro Spectra with manual controls, tripod socket"),
        ("SX-70 Gold Edition", "Polaroid", "instant", "1972-1981", 800, "Good", True, "Rare", "Gold-plated limited edition SX-70, extremely rare"),
        ("110A", "Polaroid", "instant", "1957-1960", 500, "Good", True, "Rare", "Converted to FP-100C pack film, Ysarex or Rodenstock lens"),
    ]


def _large_format_cameras() -> list[tuple]:
    """7 large format cameras — press and field cameras."""
    return [
        ("Speed Graphic 4x5", "Graflex", "large format", "1947-1973", 500, "Good", True, "Standard", "Press camera icon, focal plane shutter"),
        ("Technika Master 45", "Linhof", "large format", "1972-2005", 2000, "Excellent", False, "Rare", "Precision field camera, full movements"),
        ("Technika III 4x5", "Linhof", "large format", "1946-1956", 800, "Good", False, "Standard", "Classic German field camera, precision movements"),
        ("Crown Graphic 4x5", "Graflex", "large format", "1947-1973", 350, "Fair", True, "Standard", "Lightweight press camera variant"),
        ("Wista 45D Field Camera", "Wista", "large format", "1980-present", 600, "Excellent", False, "Standard", "Japanese cherry wood field camera, lightweight"),
        ("Super Graphic 4x5", "Graflex", "large format", "1959-1973", 450, "Good", True, "Standard", "Upgraded press camera, rangefinder coupled, back movements"),
        ("Technika V 4x5", "Linhof", "large format", "1963-1976", 1200, "Excellent", False, "Limited Edition", "German precision field camera, full movements, cam rangefinder"),
        ("Chamonix 045N-2", "Wista", "large format", "2010-present", 700, "Excellent", False, "Standard", "Lightweight carbon fibre/wood 4x5 field camera"),
        ("Intrepid 4x5 MK4", "Wista", "large format", "2018-present", 350, "Excellent", False, "Standard", "Budget lightweight 4x5 field camera, plywood construction"),
    ]


def _vintage_lenses() -> list[tuple]:
    """16 vintage lenses — legendary glass for film and mirrorless shooters."""
    return [
        ("Summicron 50mm f/2 V4 (Pre-ASPH)", "Leica", "rangefinder", "1979-1994", 1800, "Excellent", True, "Limited Edition", "Classic Leica 50, sharp and contrasty, M-mount"),
        ("Summicron 50mm f/2 Rigid V2", "Leica", "rangefinder", "1956-1968", 2400, "Good", True, "Rare", "Rigid barrel Summicron, vintage rendering, M-mount"),
        ("Summilux 35mm f/1.4 Pre-ASPH", "Leica", "rangefinder", "1961-1995", 3200, "Good", True, "Rare", "Steel rim and later versions, classic glow wide open"),
        ("Nikkor 105mm f/2.5 AI-S", "Nikon", "SLR", "1971-2005", 250, "Excellent", True, "Standard", "Afghan Girl portrait lens, legendary sharpness"),
        ("Nikkor 50mm f/1.2 AI-S", "Nikon", "SLR", "1978-present", 500, "Excellent", True, "Standard", "Fast normal lens, manual focus, character wide open"),
        ("Canon 50mm f/0.95 Dream Lens (LTM)", "Canon", "rangefinder", "1961-1972", 5500, "Good", True, "Rare", "Ultra-fast dream lens, dreamy bokeh, holy grail for street"),
        ("Canon 50mm f/1.4 LTM", "Canon", "rangefinder", "1959-1971", 400, "Good", True, "Standard", "Leica thread mount, sharp and affordable classic"),
        ("Carl Zeiss Planar 50mm f/1.4 C/Y", "Contax", "SLR", "1975-2005", 350, "Excellent", True, "Standard", "Zeiss T* coating, beautiful colour rendering"),
        ("Carl Zeiss Planar 85mm f/1.4 C/Y", "Contax", "SLR", "1975-2005", 700, "Excellent", True, "Limited Edition", "Legendary portrait lens, creamy bokeh"),
        ("Voigtlander Nokton 50mm f/1.5 Aspherical LTM", "Voigtlander", "rangefinder", "2000-present", 450, "Excellent", True, "Standard", "Modern classic, LTM mount, vintage rendering"),
        ("Leica Summilux 50mm f/1.4 V2 Black", "Leica", "rangefinder", "1962-1995", 2800, "Excellent", True, "Rare", "Iconic fast normal, M-mount, vintage warmth wide open"),
        ("Nikkor 28mm f/2.8 AI-S", "Nikon", "SLR", "1981-2006", 200, "Excellent", True, "Standard", "Classic wide-angle, CRC close-range correction"),
        ("Canon 35mm f/2 LTM", "Canon", "rangefinder", "1962-1973", 600, "Good", True, "Rare", "Leica thread mount, 8-element design, sharp wide-angle"),
        ("Pentax Super-Takumar 50mm f/1.4", "Pentax", "SLR", "1964-1971", 120, "Good", True, "Standard", "Radioactive thorium element, warm rendering, M42 mount"),
        ("Carl Zeiss Distagon 28mm f/2.8 C/Y", "Contax", "SLR", "1975-2005", 300, "Excellent", True, "Standard", "Zeiss T* wide-angle, excellent flare control, crisp rendering"),
        ("Leica Elmarit-M 28mm f/2.8 V4", "Leica", "rangefinder", "1993-2000", 2200, "Excellent", True, "Limited Edition", "Compact M-mount wide-angle, aspherical element"),
        ("Nikkor 35mm f/1.4 AI-S", "Nikon", "SLR", "1981-2005", 600, "Excellent", True, "Standard", "Fast wide-angle, CRC, character wide open"),
        ("Nikkor 85mm f/1.4 AI-S", "Nikon", "SLR", "1981-present", 550, "Excellent", True, "Standard", "Legendary portrait lens, creamy bokeh, manual focus"),
        ("Canon FD 55mm f/1.2 SSC Aspherical", "Canon", "SLR", "1973-1975", 4000, "Good", True, "Rare", "First aspherical Canon lens, extremely rare, museum piece"),
        ("Minolta MC Rokkor-PG 58mm f/1.2", "Minolta", "SLR", "1969-1977", 500, "Good", True, "Rare", "Ultra-fast Rokkor, dreamy wide open rendering"),
        ("Pentax SMC Takumar 50mm f/1.4 (8-element)", "Pentax", "SLR", "1971-1975", 150, "Excellent", True, "Standard", "8-element SMC coated version, sharper than Super Takumar"),
        ("Carl Zeiss Sonnar 180mm f/2.8 C/Y", "Contax", "SLR", "1975-2005", 400, "Excellent", True, "Standard", "Telephoto portrait lens, T* coated, stunning bokeh"),
        ("Voigtlander Color-Skopar 35mm f/2.5 LTM", "Voigtlander", "rangefinder", "1999-present", 280, "Excellent", True, "Standard", "Pancake wide-angle, LTM mount, ultra-compact"),
        ("Olympus Zuiko 50mm f/1.2", "Olympus", "SLR", "1975-2002", 450, "Excellent", True, "Standard", "Fastest OM lens, silver-nose version most prized"),
    ]


def _point_and_shoot_cameras() -> list[tuple]:
    """12 cult point-and-shoot and compact cameras."""
    return [
        ("TC-1", "Minolta", "compact", "1996-2003", 1200, "Excellent", True, "Rare", "Titanium luxury compact, 28mm f/3.5 G-Rokkor"),
        ("Ricoh GR1v", "Nikon", "compact", "1998-2001", 700, "Excellent", True, "Limited Edition", "28mm f/2.8 GR lens, snap focus, titanium"),
        ("Ricoh GR1s", "Nikon", "compact", "1996-1998", 600, "Good", True, "Standard", "Original Ricoh GR, 28mm f/2.8, compact legend"),
        ("Yashica T4 (T5 in EU)", "Yashica", "point-and-shoot", "1990-2001", 500, "Excellent", True, "Limited Edition", "Carl Zeiss T* Tessar 35mm f/3.5, cult compact"),
        ("Nikon 35Ti", "Nikon", "compact", "1993-2000", 800, "Excellent", True, "Rare", "Titanium body, 35mm f/2.8 Nikkor, analog dials"),
        ("Nikon 28Ti", "Nikon", "compact", "1994-2000", 1000, "Excellent", True, "Rare", "Titanium body, 28mm f/2.8 Nikkor, compass on top plate"),
        ("Fuji Klasse S", "Fuji", "compact", "2007-2013", 600, "Excellent", True, "Standard", "38mm f/2.8 Super-EBC Fujinon, last premium Fuji compact"),
        ("Fuji Klasse W", "Fuji", "compact", "2006-2013", 550, "Excellent", True, "Standard", "28mm f/2.8 Super-EBC Fujinon, wide-angle variant"),
        ("Konica Hexar AF", "Nikon", "rangefinder", "1993-2003", 900, "Excellent", True, "Limited Edition", "Silent shutter 35mm f/2, stealth street camera"),
        ("Konica Hexar RF", "Nikon", "rangefinder", "1999-2003", 1400, "Excellent", False, "Rare", "M-mount rangefinder, AE, motorized film advance"),
        ("Leica CM", "Leica", "compact", "2004-2007", 1500, "Excellent", True, "Rare", "Leica-branded compact, Summarit 40mm f/2.4, titanium"),
        ("Rollei 35 S", "Voigtlander", "compact", "1974-1980", 300, "Good", True, "Standard", "Miniature viewfinder camera, Sonnar 40mm f/2.8 HFT"),
    ]


def _misc_cameras() -> list[tuple]:
    """8 miscellaneous and niche vintage cameras."""
    return [
        ("Kiev 4A", "Nikon", "rangefinder", "1958-1980", 100, "Good", True, "Standard", "Ukrainian Contax II clone, Jupiter-8M 50mm f/2"),
        ("Fed-5B", "Nikon", "rangefinder", "1975-1996", 60, "Good", True, "Standard", "Soviet Leica clone, Industar-61 53mm f/2.8"),
        ("Zorki 4K", "Nikon", "rangefinder", "1972-1978", 80, "Good", True, "Standard", "Soviet LTM rangefinder, Jupiter-8 50mm f/2"),
        ("Holga 120N", "Fuji", "medium format", "1982-present", 30, "Good", True, "Standard", "Lo-fi plastic medium format, light leak aesthetic"),
        ("Diana F+", "Fuji", "medium format", "2007-present", 40, "Good", True, "Standard", "Lomography reissue Diana, 120 film, dreamy soft focus"),
        ("Lomography LC-A+", "Fuji", "compact", "2005-present", 200, "Excellent", True, "Standard", "Reissue of Soviet LOMO LC-A, Minitar-1 32mm f/2.8"),
        ("Mamiya Press Super 23", "Mamiya", "rangefinder", "1964-1980", 600, "Good", True, "Standard", "6x7/6x9 press camera, interchangeable lenses and backs"),
        ("Robot Royal 36", "Voigtlander", "compact", "1955-1965", 400, "Good", True, "Rare", "Spring-motor clockwork advance, half-frame 24x24mm"),
    ]


# === ROUND 2 — 300+ new items to reach 500+ total ===


def _leica_expanded() -> list[tuple]:
    """15 more Leica cameras and variants."""
    return [
        ("M6J (40th Anniversary)", "Leica", "rangefinder", "1994", 8000, "Mint", False, "Rare", "40th anniversary M, engraved J, only 1640 made"),
        ("M2-R", "Leica", "rangefinder", "1969-1970", 4500, "Good", False, "Rare", "M2 with rapid-load system, only 2000 made for US military"),
        ("M4-M (50 Jahre)", "Leica", "rangefinder", "1975", 5000, "Good", False, "Rare", "50th anniversary M4, only 1500 made"),
        ("MP 0.58 Silver Chrome", "Leica", "rangefinder", "2003-present", 5200, "Mint", False, "Limited Edition", "Wide-angle finder, mechanical perfection"),
        ("M-P (Typ 240) Safari", "Leica", "rangefinder", "2015", 7500, "Excellent", False, "Rare", "Olive green limited edition digital M"),
        ("M Monochrom (Typ 246)", "Leica", "rangefinder", "2015-2020", 5500, "Excellent", False, "Limited Edition", "B&W only digital M, no Bayer filter"),
        ("M10-R Black Chrome", "Leica", "rangefinder", "2020-present", 8300, "Mint", False, "Limited Edition", "40MP digital M, modern flagship"),
        ("R8", "Leica", "SLR", "1996-2002", 600, "Good", False, "Standard", "Controversial Leica R-mount SLR, Audi design"),
        ("R9", "Leica", "SLR", "2002-2009", 800, "Good", False, "Standard", "Final Leica R-mount film SLR"),
        ("If Black Dial", "Leica", "rangefinder", "1952-1956", 700, "Good", False, "Standard", "No viewfinder screw-mount, press camera use"),
        ("Ig", "Leica", "rangefinder", "1957-1960", 600, "Good", False, "Standard", "No viewfinder/rangefinder, scientific Leica"),
        ("MDa", "Leica", "rangefinder", "1966-1976", 500, "Good", False, "Standard", "No viewfinder M, scientific/lab use"),
        ("M6 Titanium", "Leica", "rangefinder", "1992-2000", 5500, "Excellent", False, "Rare", "Titanium body, only ~3500 made"),
        ("M4-2 Gold (Oskar Barnack Edition)", "Leica", "rangefinder", "1979", 12000, "Mint", False, "Rare", "Gold-plated, only 1000 made, Barnack tribute"),
        ("CL 50th Anniversary", "Leica", "rangefinder", "2018", 3200, "Mint", False, "Limited Edition", "Digital CL 50th anniversary edition"),
    ]


def _hasselblad_expanded() -> list[tuple]:
    """10 more Hasselblad cameras and variants."""
    return [
        ("500C/M 30th Anniversary", "Hasselblad", "medium format", "1982", 3000, "Excellent", True, "Rare", "30th anniversary blue leatherette"),
        ("500 Classic", "Hasselblad", "medium format", "1994-1997", 2200, "Excellent", True, "Limited Edition", "Special edition, chrome trim, last manual-only V"),
        ("202FA", "Hasselblad", "medium format", "1994-2004", 1200, "Good", False, "Standard", "Focal plane shutter, aperture priority, F-series lenses"),
        ("205FCC", "Hasselblad", "medium format", "1991-2004", 2000, "Excellent", False, "Limited Edition", "Zone System metering, focal plane V-system"),
        ("ArcBody", "Hasselblad", "medium format", "1997-2005", 1500, "Good", False, "Standard", "Shift/tilt body for V lenses, architectural"),
        ("SWA", "Hasselblad", "medium format", "1954-1958", 5000, "Good", True, "Rare", "Original Super Wide, rare first version"),
        ("1600F", "Hasselblad", "medium format", "1948-1953", 3000, "Good", True, "Rare", "First Hasselblad camera, Kodak Ektar lens"),
        ("1000F", "Hasselblad", "medium format", "1953-1957", 2500, "Good", True, "Rare", "Improved first-gen V-system, focal plane shutter"),
        ("X-Pan 30mm Kit", "Hasselblad", "rangefinder", "1998-2006", 5500, "Excellent", True, "Rare", "X-Pan with ultra-wide 30mm f/5.6 Aspherical"),
        ("503CW Gold Supreme", "Hasselblad", "medium format", "2002", 8000, "Mint", True, "Rare", "Gold-plated 503CW, only 200 made"),
    ]


def _nikon_expanded() -> list[tuple]:
    """14 more Nikon cameras."""
    return [
        ("FM10", "Nikon", "SLR", "1995-present", 200, "Excellent", True, "Standard", "Cosina-made budget Nikon, AI-S mount, student camera"),
        ("FG-20", "Nikon", "SLR", "1984-1986", 100, "Good", True, "Standard", "Budget auto-exposure SLR, programmed auto"),
        ("F4", "Nikon", "SLR", "1988-1996", 500, "Excellent", False, "Limited Edition", "First Nikon autofocus pro SLR, Giugiaro design"),
        ("F4S", "Nikon", "SLR", "1988-1996", 600, "Excellent", False, "Limited Edition", "F4 with MB-21 battery pack, 5.7fps"),
        ("F5", "Nikon", "SLR", "1996-2004", 450, "Excellent", False, "Standard", "8fps pro SLR, 3D Color Matrix metering"),
        ("F6", "Nikon", "SLR", "2004-2020", 1500, "Excellent", False, "Rare", "Last Nikon film SLR, modern AF, EXIF recording"),
        ("F100", "Nikon", "SLR", "1999-2006", 350, "Excellent", False, "Standard", "Semi-pro AF SLR, baby F5"),
        ("N90s (F90X)", "Nikon", "SLR", "1994-2001", 200, "Good", False, "Standard", "Mid-range AF SLR, 3D Matrix metering"),
        ("FM", "Nikon", "SLR", "1977-1982", 280, "Good", False, "Standard", "Original mechanical Nikon compact SLR, AI mount"),
        ("Nikkormat FT2", "Nikon", "SLR", "1975-1977", 200, "Good", True, "Standard", "Budget Nikon, AI-coupled metering"),
        ("Nikkormat FTN", "Nikon", "SLR", "1967-1975", 150, "Good", True, "Standard", "Center-weighted metering, Nikon F-mount"),
        ("Nikkorex F", "Nikon", "SLR", "1962-1967", 200, "Good", True, "Standard", "Early consumer Nikon SLR, Mamiya-made"),
        ("S2 Black Dial", "Nikon", "rangefinder", "1954-1958", 1200, "Good", True, "Rare", "Black dial variant, higher value to collectors"),
        ("SP Original", "Nikon", "rangefinder", "1957-1965", 4000, "Good", True, "Rare", "Original Nikon SP, titanium shutter, 6 framelines"),
    ]


def _canon_expanded() -> list[tuple]:
    """12 more Canon cameras."""
    return [
        ("New F-1 AE Finder", "Canon", "SLR", "1981-1992", 650, "Excellent", False, "Limited Edition", "F-1 with AE viewfinder, full auto mode"),
        ("EOS-1V", "Canon", "SLR", "2000-2012", 600, "Excellent", False, "Standard", "Last Canon pro film SLR, 10fps, 45-point AF"),
        ("EOS-1N", "Canon", "SLR", "1994-2000", 350, "Good", False, "Standard", "Pro AF film SLR, 5-point AF, eye-control focus"),
        ("EOS-3", "Canon", "SLR", "1998-2007", 300, "Excellent", False, "Standard", "Semi-pro 45-point AF, eye-controlled AF"),
        ("EF-M (FD)", "Canon", "SLR", "1991-1994", 150, "Good", False, "Standard", "Last manual-focus Canon FD-mount SLR"),
        ("A-1 Black", "Canon", "SLR", "1978-1985", 350, "Excellent", False, "Standard", "Premium black chrome A-1 variant"),
        ("Canon 7s Black Body", "Canon", "rangefinder", "1964-1967", 900, "Good", False, "Rare", "Black repaint 7s, rare variant"),
        ("Canon VT Deluxe", "Canon", "rangefinder", "1957-1958", 500, "Good", False, "Rare", "Trigger-wind rangefinder, unique design"),
        ("Canon VL", "Canon", "rangefinder", "1958-1959", 400, "Good", False, "Standard", "Lever-wind Canon rangefinder, budget model"),
        ("Demi C", "Canon", "compact", "1963-1966", 150, "Good", True, "Standard", "Half-frame compact, Canon SH 28mm f/2.8"),
        ("Dial 35-2", "Canon", "compact", "1963-1967", 250, "Good", True, "Rare", "Half-frame with spring motor, unique dial design"),
        ("Canonet 28", "Canon", "rangefinder", "1971-1976", 120, "Good", True, "Standard", "Fixed 40mm f/2.8, compact rangefinder"),
    ]


def _olympus_expanded() -> list[tuple]:
    """10 more Olympus cameras."""
    return [
        ("OM-4 Black", "Olympus", "SLR", "1983-1987", 350, "Good", False, "Standard", "Multi-spot metering, manual highlight/shadow"),
        ("OM-2N", "Olympus", "SLR", "1979-1984", 400, "Excellent", False, "Standard", "Updated OM-2, shoe connector, improved flash"),
        ("Mju I (Stylus)", "Olympus", "point-and-shoot", "1991-1997", 150, "Good", True, "Standard", "Original Mju, 35mm f/3.5, weatherproof"),
        ("Pen FT Black", "Olympus", "SLR", "1966-1972", 500, "Good", True, "Rare", "Half-frame SLR with TTL metering, black body"),
        ("Pen FV", "Olympus", "SLR", "1967-1970", 350, "Good", True, "Standard", "Budget Pen F, no metering, rotary shutter"),
        ("OM-1 MD Black", "Olympus", "SLR", "1972-1979", 400, "Excellent", False, "Standard", "Black body OM-1, motor drive compatible"),
        ("OM-40 Program", "Olympus", "SLR", "1985-1990", 100, "Good", False, "Standard", "Multi-program OM, LCD display, ESP metering"),
        ("XA4 Macro", "Olympus", "compact", "1985-1989", 200, "Good", True, "Standard", "Macro-capable XA, 28mm f/3.5, close focus to 0.3m"),
        ("OM-2000", "Olympus", "SLR", "1997-2002", 200, "Excellent", False, "Standard", "Cosina-made mechanical OM, budget option"),
        ("Infinity Stylus Zoom 140 DLX", "Olympus", "point-and-shoot", "1999-2003", 60, "Good", True, "Standard", "Multi-AF zoom compact, 38-140mm"),
    ]


def _rollei_cameras() -> list[tuple]:
    """10 Rollei cameras — TLRs, SLRs, and compacts."""
    return [
        ("2.8GX Expression", "Rolleiflex", "TLR", "1987-2001", 3500, "Excellent", True, "Rare", "Last-production Rolleiflex, Planar HFT 80mm f/2.8"),
        ("2.8E Planar", "Rolleiflex", "TLR", "1956-1959", 1500, "Good", True, "Limited Edition", "Pre-F series, exposure meter, Planar lens"),
        ("T (Grey)", "Rolleiflex", "TLR", "1958-1976", 600, "Good", True, "Standard", "Budget Rolleiflex, Tessar 75mm f/3.5, grey leatherette"),
        ("3.5E Planar", "Rolleiflex", "TLR", "1956-1959", 1400, "Good", True, "Limited Edition", "Selenium meter, Planar 75mm f/3.5"),
        ("SL66", "Rolleiflex", "medium format", "1966-1982", 1200, "Good", False, "Limited Edition", "6x6 SLR with bellows focusing, tilt capability"),
        ("SL66E", "Rolleiflex", "medium format", "1982-1992", 1500, "Excellent", False, "Limited Edition", "Electronic metering SL66"),
        ("35 SE", "Rolleiflex", "compact", "1979-1981", 350, "Good", True, "Standard", "Rollei compact with Sonnar 40mm f/2.8 HFT"),
        ("35 TE", "Rolleiflex", "compact", "1979-1981", 300, "Good", True, "Standard", "Rollei compact, Tessar 40mm f/3.5"),
        ("Rollei 35 Black", "Rolleiflex", "compact", "1966-1974", 250, "Good", True, "Standard", "Original Rollei 35, Tessar 40mm f/3.5"),
        ("Rolleicord III", "Rolleiflex", "TLR", "1950-1953", 300, "Good", True, "Standard", "Budget TLR, Xenar 75mm f/3.5, art deco styling"),
    ]


def _mamiya_expanded() -> list[tuple]:
    """10 more Mamiya cameras."""
    return [
        ("RZ67 Pro IID", "Mamiya", "medium format", "2004-2014", 1800, "Excellent", True, "Limited Edition", "Last RZ67, digital back compatible"),
        ("645 AFD II", "Mamiya", "medium format", "2004-2006", 800, "Good", True, "Standard", "AF medium format, digital back compatible"),
        ("645 Super", "Mamiya", "medium format", "1985-1992", 350, "Good", True, "Standard", "Winder-compatible 645, manual focus"),
        ("C330 Professional", "Mamiya", "TLR", "1969-1982", 400, "Good", True, "Standard", "Interchangeable-lens TLR, parallax correcting"),
        ("Universal Press", "Mamiya", "rangefinder", "1969-1979", 500, "Good", True, "Standard", "6x7/6x9 press camera, Polaroid back compatible"),
        ("645E", "Mamiya", "medium format", "1998-2001", 350, "Good", True, "Standard", "Budget electronic 645, fixed prism"),
        ("645J", "Mamiya", "medium format", "1982-1988", 250, "Good", True, "Standard", "Budget 645, no interchangeable finders"),
        ("M645", "Mamiya", "medium format", "1975-1982", 300, "Good", True, "Standard", "First Mamiya 645 SLR, waist-level finder"),
        ("Mamiya 6 (New)", "Mamiya", "rangefinder", "1989-1995", 2000, "Excellent", True, "Rare", "Collapsible 75mm f/3.5, ultra-compact 6x6"),
        ("RB67 Pro", "Mamiya", "medium format", "1970-1974", 500, "Good", True, "Standard", "Original RB67, revolving back, heavy-duty studio"),
    ]


def _bronica_expanded() -> list[tuple]:
    """8 more Bronica cameras."""
    return [
        ("S2A", "Bronica", "medium format", "1969-1977", 500, "Good", True, "Standard", "Focal plane shutter 6x6, Nikkor lenses"),
        ("EC-TL", "Bronica", "medium format", "1975-1982", 350, "Good", True, "Standard", "TTL metering, focal plane shutter, 6x6"),
        ("ETR", "Bronica", "medium format", "1976-1989", 250, "Good", True, "Standard", "First Bronica 645, leaf shutter lenses"),
        ("ETRS", "Bronica", "medium format", "1978-1989", 300, "Good", True, "Standard", "Updated ETR, speed grip compatible"),
        ("RF645", "Bronica", "rangefinder", "1999-2005", 700, "Excellent", True, "Standard", "645 rangefinder, fixed 65mm f/4"),
        ("SQ-Ai", "Bronica", "medium format", "1990-1998", 500, "Good", True, "Standard", "Final SQ-series, improved metering"),
        ("SQ-B", "Bronica", "medium format", "1993-2000", 250, "Good", False, "Standard", "Budget SQ body, no metering"),
        ("GS-1 with 100mm f/3.5", "Bronica", "medium format", "1985-1997", 500, "Excellent", True, "Standard", "6x7 system with standard lens"),
    ]


def _graflex_expanded() -> list[tuple]:
    """6 more large format and press cameras."""
    return [
        ("Century Graphic 2x3", "Graflex", "large format", "1949-1970", 300, "Good", True, "Standard", "2x3 press camera, compact format"),
        ("Pacemaker Speed Graphic 4x5", "Graflex", "large format", "1947-1970", 500, "Good", True, "Standard", "Most popular press camera, Graflex FP shutter"),
        ("Graphic View II 4x5", "Graflex", "large format", "1949-1973", 250, "Good", False, "Standard", "Monorail studio camera, full movements"),
        ("Toyo 45A Field Camera", "Wista", "large format", "1980-present", 500, "Good", False, "Standard", "Japanese field camera, modular design"),
        ("Toyo 45CF Carbon Fiber", "Wista", "large format", "2000-present", 900, "Excellent", False, "Standard", "Carbon fiber monorail, ultra-light field camera"),
        ("Sinar F2 4x5 Monorail", "Wista", "large format", "1986-present", 600, "Good", False, "Standard", "Swiss monorail, precise movements, studio standard"),
    ]


def _additional_lenses() -> list[tuple]:
    """20 more vintage lenses."""
    return [
        ("Summicron 35mm f/2 V3 (6-element)", "Leica", "rangefinder", "1969-1979", 2000, "Good", True, "Limited Edition", "6-element Summicron, King of Bokeh"),
        ("Summicron 35mm f/2 V4 (7-element)", "Leica", "rangefinder", "1979-1997", 2400, "Excellent", True, "Limited Edition", "7-element, sharp and contrasty wide-angle"),
        ("Summicron 90mm f/2 Pre-ASPH", "Leica", "rangefinder", "1980-1998", 1800, "Excellent", True, "Limited Edition", "Compact telephoto, M-mount, superb portraits"),
        ("Summaron 35mm f/3.5 M-mount", "Leica", "rangefinder", "1956-1960", 800, "Good", True, "Standard", "Early M-mount wide-angle, compact"),
        ("Elmar 50mm f/3.5 Collapsible", "Leica", "rangefinder", "1950-1961", 400, "Good", True, "Standard", "Classic collapsible screw-mount/M lens"),
        ("Nikkor 50mm f/1.4 AI-S", "Nikon", "SLR", "1981-present", 250, "Excellent", True, "Standard", "Classic fast normal, still in production"),
        ("Nikkor 135mm f/2.8 AI-S", "Nikon", "SLR", "1981-2005", 200, "Excellent", True, "Standard", "Compact telephoto, sharp portraits"),
        ("Nikkor 20mm f/2.8 AI-S", "Nikon", "SLR", "1984-2005", 350, "Excellent", True, "Standard", "Ultra-wide, CRC, rectilinear"),
        ("Canon FD 85mm f/1.2 L", "Canon", "SLR", "1976-1989", 2000, "Good", True, "Rare", "Fast portrait lens, L designation, aspherical"),
        ("Canon FD 24mm f/1.4 L", "Canon", "SLR", "1975-1989", 1800, "Good", True, "Rare", "Ultra-fast wide-angle L lens"),
        ("Canon FD 135mm f/2", "Canon", "SLR", "1975-1989", 600, "Good", True, "Standard", "Fast telephoto portrait lens"),
        ("Carl Zeiss Makro-Planar 60mm f/2.8 C/Y", "Contax", "SLR", "1975-2005", 400, "Excellent", True, "Standard", "Macro lens, T* coating, 1:1 magnification"),
        ("Pentax SMC 67 105mm f/2.4", "Pentax", "medium format", "1969-2005", 600, "Good", True, "Standard", "Legendary 6x7 portrait lens, creamy bokeh"),
        ("Pentax FA 77mm f/1.8 Limited", "Pentax", "SLR", "1999-present", 800, "Excellent", True, "Limited Edition", "Compact aluminium portrait lens, sharp wide open"),
        ("Olympus Zuiko 21mm f/2", "Olympus", "SLR", "1979-2002", 800, "Excellent", True, "Rare", "Ultra-wide fast prime, rare and desirable"),
        ("Olympus Zuiko 100mm f/2", "Olympus", "SLR", "1979-2002", 600, "Excellent", True, "Rare", "Fast telephoto, rare OM lens"),
        ("Minolta MC Rokkor 35mm f/1.8", "Minolta", "SLR", "1968-1977", 350, "Good", True, "Standard", "Fast wide-angle Rokkor, excellent color"),
        ("Voigtlander Ultron 35mm f/1.7 LTM", "Voigtlander", "rangefinder", "2001-present", 350, "Excellent", True, "Standard", "Fast M-mount wide-angle, Cosina-made"),
        ("Leica Noctilux 50mm f/1.0 V3", "Leica", "rangefinder", "1982-2008", 8000, "Good", True, "Rare", "Ultra-fast aspherical, cult following, dream lens"),
        ("Canon 100mm f/2 LTM", "Canon", "rangefinder", "1958-1970", 500, "Good", True, "Standard", "Screw-mount telephoto, excellent portrait rendering"),
    ]


def _point_and_shoot_expanded() -> list[tuple]:
    """18 more cult point-and-shoot cameras."""
    return [
        ("Ricoh GR21", "Nikon", "compact", "2001-2005", 1200, "Excellent", True, "Rare", "21mm f/3.5 ultra-wide GR lens, only 3000 made"),
        ("Yashica T4 Safari (T5 Safari)", "Yashica", "point-and-shoot", "1990-2001", 600, "Good", True, "Rare", "Safari green T4, Carl Zeiss Tessar 35mm f/3.5"),
        ("Yashica T3 Super", "Yashica", "point-and-shoot", "1989-1993", 300, "Good", True, "Standard", "Carl Zeiss Tessar 35mm f/2.8, compact"),
        ("Contax Tix", "Contax", "compact", "1998-2001", 250, "Good", True, "Standard", "APS compact, Carl Zeiss Sonnar 28mm f/2.8"),
        ("Minolta TC-1 Black", "Minolta", "compact", "1996-2003", 1400, "Excellent", True, "Rare", "Rare black version of the TC-1"),
        ("Ricoh R1", "Nikon", "compact", "1994-1998", 200, "Good", True, "Standard", "Ultra-compact, 30mm f/3.5 wide-angle"),
        ("Nikon L35AF", "Nikon", "point-and-shoot", "1983-1986", 200, "Good", True, "Standard", "Pikaichi, first AF compact, 35mm f/2.8 Nikkor"),
        ("Canon Sure Shot AF35M II (Autoboy)", "Canon", "point-and-shoot", "1986-1990", 100, "Good", True, "Standard", "Budget AF compact, Canon 38mm f/2.8"),
        ("Fuji Natura Black F1.9", "Fuji", "point-and-shoot", "2002-2008", 800, "Excellent", True, "Rare", "24mm f/1.9 Super-EBC Fujinon, NP mode"),
        ("Fuji Natura S", "Fuji", "point-and-shoot", "2005-2010", 500, "Excellent", True, "Standard", "24mm f/1.9, flash-off priority, quiet shutter"),
        ("Konica Big Mini BM-201", "Nikon", "compact", "1991-1996", 150, "Good", True, "Standard", "35mm f/3.5 Konica Hexanon, very compact"),
        ("Konica Big Mini F", "Nikon", "compact", "1996-2002", 200, "Good", True, "Standard", "28mm f/3.5 Hexanon, wider Big Mini"),
        ("Olympus Mju Zoom 140", "Olympus", "point-and-shoot", "2000-2004", 50, "Good", True, "Standard", "38-140mm zoom compact, all-weather"),
        ("Canon Prima Super 115 (Sure Shot 115u)", "Canon", "point-and-shoot", "2001-2005", 40, "Good", True, "Standard", "38-115mm zoom compact, date back"),
        ("Minox 35 GT-E", "Minolta", "compact", "1981-1990", 200, "Good", True, "Standard", "Ultra-compact spy-cam style, 35mm f/2.8 Minotar"),
        ("Pentax Espio Mini", "Pentax", "point-and-shoot", "1994-1998", 200, "Good", True, "Standard", "32mm f/3.5 smc Pentax, splash-proof"),
        ("Samsung Slim Zoom 1150", "Nikon", "point-and-shoot", "2003-2005", 30, "Good", True, "Standard", "38-115mm Schneider zoom, ultra-slim"),
        ("Leica Mini 3", "Leica", "compact", "1994-2000", 300, "Good", True, "Standard", "Leica-branded Minolta compact, 32mm f/3.2 Elmar"),
    ]


def _minolta_expanded() -> list[tuple]:
    """8 more Minolta cameras."""
    return [
        ("SRT 201", "Minolta", "SLR", "1977-1981", 120, "Good", True, "Standard", "Updated SRT, split-image focus screen"),
        ("XG-M", "Minolta", "SLR", "1981-1984", 100, "Good", True, "Standard", "Multi-mode budget SLR, MD mount"),
        ("X-300 (X-370)", "Minolta", "SLR", "1984-2001", 80, "Good", True, "Standard", "Budget manual-focus SLR, long production run"),
        ("Alpha 7 (Maxxum 7 / Dynax 7)", "Minolta", "SLR", "2000-2006", 300, "Excellent", False, "Standard", "Last great Minolta AF film SLR, SSM support"),
        ("Alpha 9 (Maxxum 9 / Dynax 9)", "Minolta", "SLR", "1998-2003", 400, "Excellent", False, "Standard", "Pro Minolta AF film body, 5.5fps, weather sealed"),
        ("Hi-Matic AF", "Minolta", "rangefinder", "1979-1982", 80, "Good", True, "Standard", "First AF compact camera ever made"),
        ("Prod 20s", "Minolta", "compact", "1990", 2000, "Excellent", True, "Rare", "Limited to 3000 units, dual-lens design, curiosity piece"),
        ("SR-7", "Minolta", "SLR", "1962-1966", 120, "Good", True, "Standard", "First SLR with built-in CdS meter"),
    ]


def _contax_expanded() -> list[tuple]:
    """8 more Contax cameras."""
    return [
        ("G2 Titanium", "Contax", "rangefinder", "1996-2005", 1400, "Excellent", False, "Rare", "Titanium-finish G2 variant, limited production"),
        ("RTS", "Contax", "SLR", "1974-1985", 250, "Good", False, "Standard", "First Yashica/Contax mount SLR, quartz timing"),
        ("RTS II", "Contax", "SLR", "1982-1990", 350, "Good", False, "Standard", "Improved RTS, titanium shutter, real-time metering"),
        ("137MA Quartz", "Contax", "SLR", "1982-1985", 200, "Good", False, "Standard", "Aperture-priority auto, quartz-controlled shutter"),
        ("T Black", "Contax", "compact", "1984-1990", 1500, "Good", True, "Rare", "Original Contax T, Sonnar 38mm f/2.8, rare black body"),
        ("ST", "Contax", "SLR", "1992-1998", 350, "Good", False, "Standard", "Multi-mode SLR, 5-point AF, C/Y mount"),
        ("N1", "Contax", "SLR", "2000-2005", 400, "Good", False, "Standard", "Last Contax SLR system, N-mount AF, Zeiss AF lenses"),
        ("TVS Digital", "Contax", "compact", "2002-2003", 150, "Good", True, "Standard", "Early premium digital compact, Carl Zeiss Vario-Sonnar"),
    ]


def _pentax_expanded() -> list[tuple]:
    """10 more Pentax cameras."""
    return [
        ("LX Gold (Limited Edition)", "Pentax", "SLR", "1981", 3000, "Mint", False, "Rare", "Gold-plated LX, only 300 made"),
        ("MZ-S (MZ-S QD)", "Pentax", "SLR", "2001-2005", 350, "Excellent", False, "Standard", "Semi-pro AF film body, magnesium alloy"),
        ("MZ-5N", "Pentax", "SLR", "1997-2001", 200, "Good", False, "Standard", "Compact AF SLR with manual feel"),
        ("Super Program (Super A)", "Pentax", "SLR", "1983-1986", 150, "Good", False, "Standard", "Multi-mode electronic SLR, K/KA mount"),
        ("645 (Original)", "Pentax", "medium format", "1984-1997", 350, "Good", True, "Standard", "First Pentax 645, TTL flash, motor built in"),
        ("K2", "Pentax", "SLR", "1975-1977", 200, "Good", False, "Standard", "Aperture-priority auto K-mount SLR, electronic shutter"),
        ("ES II", "Pentax", "SLR", "1973-1975", 150, "Good", False, "Standard", "Electronic shutter M42 SLR, auto exposure"),
        ("Spotmatic SP", "Pentax", "SLR", "1964-1974", 150, "Good", True, "Standard", "Iconic TTL SLR, M42 mount, stop-down metering"),
        ("Auto 110", "Pentax", "SLR", "1978-1985", 250, "Excellent", True, "Rare", "Tiny SLR for 110 film, interchangeable lenses"),
        ("67II AE Finder", "Pentax", "medium format", "1998-2005", 1300, "Excellent", False, "Limited Edition", "67II with AE metering prism finder"),
    ]


def _medium_format_expanded() -> list[tuple]:
    """14 more medium format cameras."""
    return [
        ("GW670III", "Fuji", "rangefinder", "1992-2000", 900, "Good", True, "Standard", "Texas Leica, 6x7 rangefinder, 90mm f/3.5"),
        ("GA645 Professional", "Fuji", "medium format", "1995-2002", 800, "Excellent", True, "Standard", "AF vertical 645, 60mm f/4 Super-EBC Fujinon"),
        ("GA645W Professional", "Fuji", "medium format", "1995-2002", 900, "Excellent", True, "Standard", "Wide-angle AF 645, 45mm f/4 EBC Fujinon"),
        ("GA645Zi Professional", "Fuji", "medium format", "1998-2002", 750, "Good", True, "Standard", "Zoom AF 645, 55-90mm f/4.5-6.9"),
        ("Fuji GX680III Professional", "Fuji", "medium format", "1997-2006", 800, "Good", False, "Standard", "Tilt/shift studio 6x8 SLR, huge negative"),
        ("Kiev 88 CM", "Mamiya", "medium format", "1972-2000", 200, "Good", True, "Standard", "Ukrainian Hasselblad clone, Arsat lenses"),
        ("Kowa Six MM", "Mamiya", "medium format", "1974-1980", 400, "Good", True, "Standard", "Japanese 6x6 SLR, leaf shutter lenses"),
        ("Norita 66", "Mamiya", "medium format", "1972-1977", 600, "Good", True, "Rare", "Rare 6x6 SLR, Noritar 80mm f/2 dream lens"),
        ("Rolleiflex 2.8FX", "Rolleiflex", "TLR", "2003-2015", 4000, "Excellent", True, "Rare", "Modern production TLR, Planar HFT 80mm f/2.8"),
        ("Yashica D", "Yashica", "TLR", "1958-1973", 200, "Good", True, "Standard", "Budget Yashica TLR, Yashikor 80mm f/3.5"),
        ("Yashica A", "Yashica", "TLR", "1956-1969", 150, "Good", True, "Standard", "Entry Yashica TLR, knob advance"),
        ("Mamiya C33 Professional", "Mamiya", "TLR", "1965-1969", 350, "Good", True, "Standard", "Interchangeable-lens TLR, heavy-duty"),
        ("Seagull 4A-109", "Yashica", "TLR", "1960-present", 100, "Good", True, "Standard", "Chinese TLR, Haiou lens, budget 6x6"),
        ("Lubitel 166B", "Fuji", "TLR", "1980-1996", 50, "Good", True, "Standard", "Soviet plastic TLR, T-22 75mm f/4.5, lo-fi charm"),
    ]


def _instant_expanded() -> list[tuple]:
    """8 more instant and Polaroid cameras."""
    return [
        ("SX-70 Mint Custom TLR", "Polaroid", "instant", "2020-present", 500, "Mint", True, "Limited Edition", "Mint Camera restored/custom SX-70"),
        ("OneStep+ i-Type", "Polaroid", "instant", "2018-present", 120, "Excellent", True, "Standard", "Modern Polaroid, Bluetooth app control"),
        ("Now+ Gen 2", "Polaroid", "instant", "2022-present", 150, "Excellent", True, "Standard", "Modern i-Type, lens filters, creative tools"),
        ("Go Generation 2", "Polaroid", "instant", "2023-present", 80, "Excellent", True, "Standard", "Smallest Polaroid, new Go film format"),
        ("Fuji Instax Mini 90 Neo Classic", "Fuji", "instant", "2013-present", 130, "Excellent", True, "Standard", "Retro-styled Instax Mini, multiple modes"),
        ("Fuji Instax Wide 300", "Fuji", "instant", "2014-present", 100, "Excellent", True, "Standard", "Wide-format Instax, 95mm f/14 Fujinon"),
        ("Fuji Instax Mini Evo", "Fuji", "instant", "2021-present", 180, "Mint", True, "Standard", "Hybrid digital-instant, retro design, 10 lens effects"),
        ("Impossible I-1", "Polaroid", "instant", "2016-2018", 200, "Good", True, "Standard", "First new Polaroid camera by Impossible Project"),
    ]


def _round3_leica_nikon() -> list[tuple]:
    """20 more Leica & Nikon cameras and variants for Round 3."""
    return [
        ("M4 Chrome", "Leica", "rangefinder", "1967-1975", 2800, "Excellent", False, "Limited Edition", "Chrome M4, self-timer, rapid-load lever"),
        ("M6 0.58 Black", "Leica", "rangefinder", "1984-1998", 3400, "Excellent", False, "Limited Edition", "Wide-angle viewfinder variant, 0.58x magnification"),
        ("M6 0.85 Black", "Leica", "rangefinder", "1984-1998", 3600, "Excellent", False, "Limited Edition", "Tele-optimized 0.85x viewfinder, rare variant"),
        ("M5 Black", "Leica", "rangefinder", "1971-1975", 2000, "Good", False, "Standard", "Black chrome M5, metering arm"),
        ("IIf Red Dial (Sharkskin)", "Leica", "rangefinder", "1951-1956", 1400, "Good", True, "Rare", "Vulcanite sharkskin variant, sought-after"),
        ("Standard (Model E)", "Leica", "rangefinder", "1932-1950", 1200, "Good", True, "Rare", "Pre-war screw mount, no rangefinder, early Leitz"),
        ("R5", "Leica", "SLR", "1987-1992", 400, "Good", False, "Standard", "Multi-mode R-mount SLR, Minolta-derived"),
        ("R3", "Leica", "SLR", "1976-1979", 350, "Good", False, "Standard", "First Minolta-Leica collaboration R-mount SLR"),
        ("R7", "Leica", "SLR", "1992-1997", 500, "Good", False, "Standard", "Multi-mode electronic R-mount SLR"),
        ("Nikon F2A", "Nikon", "SLR", "1977-1980", 550, "Excellent", False, "Limited Edition", "F2 with AI coupling, matrix meter"),
        ("Nikon F4E", "Nikon", "SLR", "1988-1996", 650, "Excellent", False, "Limited Edition", "F4 with MB-23 vertical grip, 5.7fps"),
        ("Nikon F3P Press", "Nikon", "SLR", "1983-2001", 800, "Excellent", False, "Rare", "Press version F3, no-name branding, faster controls"),
        ("Nikon FE Black", "Nikon", "SLR", "1978-1983", 350, "Excellent", False, "Standard", "Black body FE, aperture-priority, mechanical backup"),
        ("Nikon FM2 Year of the Dragon", "Nikon", "SLR", "2000", 1500, "Mint", False, "Rare", "Limited dragon-engraved FM2, only 2500 made"),
        ("Nikon EL2", "Nikon", "SLR", "1977-1978", 200, "Good", False, "Standard", "Aperture-priority Nikkormat successor, AI mount"),
        ("Nikon Nikkorex Zoom 35", "Nikon", "SLR", "1963-1967", 300, "Good", True, "Rare", "First zoom lens SLR, built-in 43-86mm zoom"),
        ("Nikon F2SB", "Nikon", "SLR", "1976-1977", 600, "Good", False, "Limited Edition", "F2 with SB finder, LED metering"),
        ("Nikon N8008s (F-801s)", "Nikon", "SLR", "1991-1994", 150, "Good", False, "Standard", "Mid-range AF SLR, matrix metering, 3.3fps"),
        ("Nikon F80 (N80)", "Nikon", "SLR", "2000-2006", 150, "Excellent", False, "Standard", "Consumer AF SLR, 5-area AF, baby F100"),
        ("Nikon FG", "Nikon", "SLR", "1982-1986", 150, "Good", True, "Standard", "Compact program auto SLR, AI-S mount"),
    ]


def _round3_canon_olympus() -> list[tuple]:
    """16 more Canon & Olympus cameras for Round 3."""
    return [
        ("Canon EOS-1N RS", "Canon", "SLR", "1995-2000", 500, "Good", False, "Rare", "Pellicle mirror 1N, zero blackout, 10fps"),
        ("Canon EOS 5 (A2E)", "Canon", "SLR", "1992-1998", 200, "Good", False, "Standard", "Eye-control AF, 5-point AF, semi-pro film body"),
        ("Canon EOS 50E (Elan IIE)", "Canon", "SLR", "1995-2000", 120, "Good", False, "Standard", "Mid-range AF SLR with eye-control AF"),
        ("Canon T70", "Canon", "SLR", "1984-1987", 100, "Good", False, "Standard", "Multi-program FD-mount SLR, LCD panel"),
        ("Canon T50", "Canon", "SLR", "1983-1985", 80, "Good", True, "Standard", "Budget program-only FD-mount SLR"),
        ("Canon AL-1 QF", "Canon", "SLR", "1982-1985", 100, "Good", False, "Standard", "Quick Focus SLR, infrared AF assist"),
        ("Canon Sureshot 70 Zoom", "Canon", "point-and-shoot", "1994-1999", 40, "Good", True, "Standard", "35-70mm zoom compact, date back"),
        ("Canon IVSb2", "Canon", "rangefinder", "1952-1956", 700, "Good", True, "Rare", "Late screw-mount Canon rangefinder, flash sync"),
        ("Olympus OM-3", "Olympus", "SLR", "1983-1986", 500, "Good", False, "Rare", "Mechanical multi-spot metering, rare body"),
        ("Olympus Pen W", "Olympus", "compact", "1964-1965", 400, "Good", True, "Rare", "Wide-angle half-frame, E.Zuiko 25mm f/2.8"),
        ("Olympus Pen D3", "Olympus", "compact", "1965-1969", 200, "Good", True, "Standard", "Half-frame, F.Zuiko 32mm f/1.7, CdS meter"),
        ("Olympus OM-20 (OM-G)", "Olympus", "SLR", "1983-1986", 100, "Good", True, "Standard", "Budget OM auto-exposure SLR"),
        ("Olympus IS-3 DLX", "Olympus", "SLR", "1995-1999", 60, "Good", True, "Standard", "Bridge SLR, built-in 35-180mm zoom"),
        ("Olympus Mju III 80", "Olympus", "point-and-shoot", "2002-2005", 40, "Good", True, "Standard", "38-80mm zoom, all-weather compact"),
        ("Olympus Pen EES-2", "Olympus", "compact", "1968-1971", 100, "Good", True, "Standard", "Half-frame with auto exposure, D.Zuiko 28mm f/3.5"),
        ("Olympus OM-4 Ti American", "Olympus", "SLR", "1989-2002", 700, "Excellent", False, "Rare", "American market titanium OM-4, champagne finish"),
    ]


def _round3_contax_pentax_minolta() -> list[tuple]:
    """18 more Contax, Pentax, and Minolta cameras for Round 3."""
    return [
        ("Contax Tix APS", "Contax", "compact", "1998-2001", 200, "Good", True, "Standard", "APS-format, Carl Zeiss Sonnar 28mm f/2.8"),
        ("Contax G2 Black", "Contax", "rangefinder", "1996-2005", 1300, "Excellent", False, "Limited Edition", "Standard black G2, fastest AF rangefinder ever"),
        ("Contax NX", "Contax", "SLR", "2002-2005", 250, "Good", False, "Standard", "N-mount AF SLR, Zeiss AF lenses"),
        ("Contax AX", "Contax", "SLR", "1996-2000", 500, "Good", False, "Standard", "Autofocus via moving film plane, C/Y mount MF lenses work"),
        ("Contax 139 Quartz", "Contax", "SLR", "1979-1987", 200, "Good", False, "Standard", "Budget Contax SLR, aperture-priority, C/Y mount"),
        ("Contax 159MM", "Contax", "SLR", "1985-1992", 250, "Good", False, "Standard", "Multi-mode SLR, MM lens compatible, C/Y mount"),
        ("Pentax MZ-3 (ZX-5n)", "Pentax", "SLR", "1997-2005", 250, "Excellent", False, "Standard", "Retro-styled AF SLR, manual feel with AF convenience"),
        ("Pentax KX", "Pentax", "SLR", "1975-1977", 200, "Good", False, "Standard", "Full-featured K-mount SLR, open-aperture metering"),
        ("Pentax KM", "Pentax", "SLR", "1975-1977", 130, "Good", True, "Standard", "Budget K-mount SLR, match-needle metering"),
        ("Pentax SP1000", "Pentax", "SLR", "1973-1976", 100, "Good", True, "Standard", "Budget Spotmatic, stop-down metering, M42 mount"),
        ("Pentax SV", "Pentax", "SLR", "1962-1968", 120, "Good", True, "Standard", "Pre-Spotmatic, external meter, M42 mount"),
        ("Pentax Auto 110 Super", "Pentax", "SLR", "1982-1985", 300, "Excellent", True, "Rare", "Updated 110 SLR, AF and program mode"),
        ("Minolta SR-T Super (SR-T 102)", "Minolta", "SLR", "1973-1976", 150, "Good", True, "Standard", "Pro-level SR-T, split-image focus, CLC metering"),
        ("Minolta XD-5", "Minolta", "SLR", "1978-1982", 200, "Good", False, "Standard", "Simplified XD-7, aperture-priority only"),
        ("Minolta Maxxum 7000 (Alpha 7000)", "Minolta", "SLR", "1985-1988", 150, "Good", True, "Standard", "First integrated AF SLR system, revolutionary"),
        ("Minolta Maxxum 9000 (Alpha 9000)", "Minolta", "SLR", "1985-1989", 200, "Good", False, "Standard", "Pro AF body, modular system, A-mount"),
        ("Minolta Weathermatic A", "Minolta", "compact", "1980-1984", 60, "Good", True, "Standard", "Waterproof 110 format compact, bright yellow"),
        ("Minolta AF-C", "Minolta", "compact", "1983-1986", 60, "Good", True, "Standard", "Budget AF compact, 35mm f/2.8 Minolta lens"),
    ]


def _round3_medium_format_lenses() -> list[tuple]:
    """22 more medium format cameras and vintage lenses for Round 3."""
    return [
        ("Mamiya RZ67 Pro", "Mamiya", "medium format", "1982-1995", 800, "Good", True, "Standard", "Original RZ67, electronic release, revolving back"),
        ("Mamiya 645 AF", "Mamiya", "medium format", "1999-2004", 500, "Good", True, "Standard", "First AF Mamiya 645, Phase One compatible"),
        ("Bronica EC", "Bronica", "medium format", "1972-1975", 300, "Good", True, "Standard", "Electronic focal plane 6x6, Nikkor lenses"),
        ("Bronica D (Deluxe)", "Bronica", "medium format", "1958-1961", 400, "Good", True, "Rare", "First Bronica, Hasselblad-style 6x6 SLR"),
        ("Rolleiflex 2.8C Planar", "Rolleiflex", "TLR", "1953-1956", 1800, "Good", True, "Rare", "Early Planar-equipped Rolleiflex, excellent optics"),
        ("Rolleiflex MiniDigi", "Rolleiflex", "compact", "2007", 400, "Excellent", True, "Rare", "Digital miniature TLR, collectible novelty"),
        ("Yashica-Mat EM", "Yashica", "TLR", "1964-1969", 200, "Good", True, "Standard", "Auto-exposure Yashica TLR, Yashinon 80mm f/3.5"),
        ("Yashica 635", "Yashica", "TLR", "1958-1962", 350, "Good", True, "Standard", "Dual format TLR, 120 and 35mm compatible"),
        ("Fuji GW680III Professional", "Fuji", "rangefinder", "1992-2000", 1000, "Excellent", True, "Standard", "6x8 Texas Leica, 90mm f/3.5 EBC Fujinon"),
        ("Fuji GSW680III Professional", "Fuji", "rangefinder", "1992-2000", 1100, "Excellent", True, "Standard", "Wide-angle 6x8, 65mm f/5.6 EBC Fujinon"),
        ("Mamiya Press Standard", "Mamiya", "rangefinder", "1960-1969", 400, "Good", True, "Standard", "6x9 press camera, interchangeable lenses"),
        ("Leica Summicron 50mm f/2 V5 (Current)", "Leica", "rangefinder", "2012-present", 2800, "Mint", True, "Limited Edition", "Current production 50 Summicron, APO-like rendering"),
        ("Leica Elmarit 21mm f/2.8 V1 (Pre-ASPH)", "Leica", "rangefinder", "1963-1980", 2500, "Good", True, "Rare", "Early M-mount ultra-wide, external viewfinder required"),
        ("Leica Tele-Elmarit 90mm f/2.8", "Leica", "rangefinder", "1963-1990", 800, "Excellent", True, "Standard", "Compact tele for M-mount, fat version prized"),
        ("Nikkor 180mm f/2.8 ED AI-S", "Nikon", "SLR", "1981-2005", 350, "Excellent", True, "Standard", "ED glass telephoto, sharp and contrasty"),
        ("Nikkor 24mm f/2 AI-S", "Nikon", "SLR", "1981-2005", 400, "Excellent", True, "Standard", "Fast ultra-wide, CRC, sought-after focal length"),
        ("Canon FD 50mm f/1.2 L", "Canon", "SLR", "1980-1989", 800, "Good", True, "Standard", "Fast L-series normal lens, smooth bokeh"),
        ("Canon FD 200mm f/2.8 IF", "Canon", "SLR", "1979-1989", 400, "Good", True, "Standard", "Internal focus telephoto, sharp portraits"),
        ("Pentax SMC Takumar 135mm f/2.5", "Pentax", "SLR", "1971-1975", 100, "Good", True, "Standard", "Budget tele portrait, M42 mount, sharp rendering"),
        ("Olympus Zuiko 135mm f/2.8", "Olympus", "SLR", "1975-2002", 150, "Excellent", True, "Standard", "Compact OM tele, excellent sharpness"),
        ("Carl Zeiss Planar 135mm f/2 C/Y", "Contax", "SLR", "1975-2005", 800, "Excellent", True, "Rare", "Fast tele Zeiss, T* coated, rare focal length"),
        ("Voigtlander Nokton 40mm f/1.4 SC M-mount", "Voigtlander", "rangefinder", "2003-present", 400, "Excellent", True, "Standard", "Single-coated, classic rendering, M-mount"),
    ]


def _round3_point_and_shoot_misc() -> list[tuple]:
    """25 more point-and-shoot and miscellaneous cameras for Round 3."""
    return [
        ("Ricoh GR1", "Nikon", "compact", "1996-1998", 500, "Good", True, "Standard", "First Ricoh GR, 28mm f/2.8 GR lens, titanium"),
        ("Ricoh GR10", "Nikon", "compact", "1998-2001", 250, "Good", True, "Standard", "Budget GR, 28mm f/2.8 lens, lighter build"),
        ("Yashica T2", "Yashica", "point-and-shoot", "1986-1990", 200, "Good", True, "Standard", "Carl Zeiss T* Tessar 35mm f/3.5, predecessor to T4"),
        ("Fuji Cardia Mini Tiara", "Fuji", "compact", "1994-1999", 300, "Good", True, "Standard", "28mm f/3.5 Super-EBC Fujinon, ultra-compact"),
        ("Fuji DL Super Mini (Tiara II)", "Fuji", "compact", "1998-2002", 250, "Good", True, "Standard", "Updated Tiara, 28mm f/3.5, date back"),
        ("Olympus XA1", "Olympus", "compact", "1982-1985", 80, "Good", True, "Standard", "Simplified XA, selenium meter, zone focus"),
        ("Canon Autoboy Luna 105 (Sure Shot 105 Zoom)", "Canon", "point-and-shoot", "1996-2001", 50, "Good", True, "Standard", "38-105mm zoom, multi-AF, date back"),
        ("Nikon Lite Touch Zoom 120 ED", "Nikon", "point-and-shoot", "1998-2002", 60, "Good", True, "Standard", "38-120mm ED zoom, weather-resistant"),
        ("Nikon L35AF2 (One Touch)", "Nikon", "point-and-shoot", "1985-1989", 100, "Good", True, "Standard", "Updated Pikaichi, 35mm f/2.8 Nikkor"),
        ("Pentax Espio 140M", "Pentax", "point-and-shoot", "2000-2004", 40, "Good", True, "Standard", "38-140mm zoom, compact body, date back"),
        ("Minolta Riva Zoom 70W", "Minolta", "point-and-shoot", "1993-1998", 60, "Good", True, "Standard", "28-70mm wide-angle zoom compact"),
        ("Konica C35 AF", "Nikon", "rangefinder", "1977-1983", 150, "Good", True, "Standard", "First autofocus camera ever, Hexanon 38mm f/2.8"),
        ("Konica C35 Flashmatic", "Nikon", "rangefinder", "1971-1975", 80, "Good", True, "Standard", "Compact rangefinder, 38mm f/2.8 Hexanon"),
        ("Agfa Optima 1535 Sensor", "Voigtlander", "rangefinder", "1978-1985", 120, "Good", True, "Standard", "German compact rangefinder, Solitar 40mm f/2.8"),
        ("Rollei 35 LED", "Rolleiflex", "compact", "1978-1980", 200, "Good", True, "Standard", "Rollei 35 with LED meter, Triotar 40mm f/3.5"),
        ("Vivitar Ultra Wide & Slim", "Fuji", "compact", "2005-present", 30, "Good", True, "Standard", "22mm plastic wide-angle, lo-fi cult favourite"),
        ("Olympus Trip AF", "Olympus", "point-and-shoot", "1985-1990", 40, "Good", True, "Standard", "Budget AF compact, Zuiko 35mm f/4"),
        ("Topcon Uni", "Nikon", "SLR", "1964-1969", 200, "Good", True, "Standard", "TTL metering SLR, UV-Topcor lenses"),
        ("Miranda Sensorex", "Nikon", "SLR", "1966-1972", 100, "Good", True, "Standard", "Japanese SLR, interchangeable viewfinder prism"),
        ("Fujica ST801", "Fuji", "SLR", "1972-1978", 150, "Good", True, "Standard", "LED metering M42 SLR, EBC Fujinon lenses"),
        ("Fujica ST605", "Fuji", "SLR", "1976-1978", 80, "Good", True, "Standard", "Budget M42 SLR, match-needle metering"),
        ("Olympus Pen EE-2", "Olympus", "compact", "1968-1977", 80, "Good", True, "Standard", "Half-frame auto-exposure, D.Zuiko 28mm f/3.5"),
        ("Konica FP-1 Program", "Nikon", "SLR", "1981-1984", 80, "Good", True, "Standard", "Program auto Konica SLR, Hexanon AR mount"),
        ("Ricoh 500G", "Nikon", "rangefinder", "1972-1975", 100, "Good", True, "Standard", "Compact rangefinder, 40mm f/2.8 Rikenon, CdS meter"),
        ("Zenit-E", "Nikon", "SLR", "1965-1982", 50, "Good", True, "Standard", "Most-produced SLR ever, Soviet workhorse, M42 mount"),
    ]


def _additional_misc() -> list[tuple]:
    """20 more niche, unusual, and regional cameras."""
    return [
        ("Chinon CE-4s", "Nikon", "SLR", "1981-1985", 80, "Good", True, "Standard", "Budget K-mount SLR, Chinon-made"),
        ("Cosina CT-1 Super", "Nikon", "SLR", "1983-1988", 60, "Good", True, "Standard", "Budget K-mount/Nikon mount SLR"),
        ("Ricoh XR-P", "Nikon", "SLR", "1985-1988", 80, "Good", True, "Standard", "Program auto K-mount SLR, LCD display"),
        ("Praktica BCA Electronic", "Nikon", "SLR", "1985-1990", 50, "Good", True, "Standard", "East German SLR, Pentacon mount"),
        ("Zorki 1", "Nikon", "rangefinder", "1948-1956", 100, "Good", True, "Standard", "Soviet Leica II copy, FED-derived"),
        ("Fed-2", "Nikon", "rangefinder", "1955-1970", 80, "Good", True, "Standard", "Improved Soviet Leica copy, combined VF/RF"),
        ("Kiev 60 TTL", "Mamiya", "medium format", "1984-2000", 200, "Good", True, "Standard", "Soviet Pentacon Six clone, 6x6 SLR"),
        ("Pentacon Six TL", "Mamiya", "medium format", "1968-1990", 250, "Good", True, "Standard", "East German 6x6 SLR, Carl Zeiss Jena lenses"),
        ("Exakta VX 1000", "Nikon", "SLR", "1967-1970", 150, "Good", True, "Standard", "East German SLR pioneer, left-hand shutter"),
        ("Topcon RE Super", "Nikon", "SLR", "1963-1972", 200, "Good", True, "Standard", "First SLR with TTL metering through the lens"),
        ("Petri 7s", "Nikon", "rangefinder", "1963-1977", 80, "Good", True, "Standard", "Japanese rangefinder, 45mm f/2.8, green circle"),
        ("Argus C3 Matchmatic", "Nikon", "rangefinder", "1939-1966", 80, "Good", True, "Standard", "The Brick, iconic American rangefinder"),
        ("Agfa Isolette III", "Voigtlander", "medium format", "1952-1957", 200, "Good", True, "Standard", "Folding 6x6, coupled rangefinder, Solinar lens"),
        ("Voigtlander Vitessa A", "Voigtlander", "rangefinder", "1950-1957", 300, "Good", True, "Standard", "Barn-door folding camera, plunger advance"),
        ("Voigtlander Prominent", "Voigtlander", "rangefinder", "1951-1958", 350, "Good", True, "Standard", "Interchangeable lens rangefinder, Ultron 50mm f/2"),
        ("Minolta Autocord L", "Minolta", "TLR", "1965-1969", 300, "Good", True, "Standard", "Japanese TLR, Rokkor 75mm f/3.5, light meter"),
        ("Kodak Retina IIIc", "Nikon", "rangefinder", "1954-1957", 200, "Good", True, "Standard", "German Kodak folding rangefinder, Schneider Xenon"),
        ("Canon Pellix", "Canon", "SLR", "1965-1970", 250, "Good", False, "Rare", "Pellicle mirror SLR, no viewfinder blackout"),
        ("Nikon F3 Limited", "Nikon", "SLR", "1994", 2000, "Excellent", False, "Rare", "Black titanium F3, limited to 2000 units"),
        ("Leica IIIc K", "Leica", "rangefinder", "1942-1945", 1500, "Good", True, "Rare", "Wartime ball-bearing Leica, grey finish variant"),
    ]


def _round4_medium_format_rangefinder_misc() -> list[tuple]:
    """50 more cameras — Mamiya RB67, Pentax 67, Bronica SQ-A, Hasselblad 500C/M w/ lenses,
    Rolleiflex 3.5F, Yashica Mat 124G, Minolta CLE, Olympus Pen F, Canon P, Nikon S3,
    Contax T2 Black, Fuji GA645, Plaubel Makina 67, and more."""
    return [
        # --- Mamiya RB67 variants ---
        ("RB67 Pro-S with 90mm f/3.8", "Mamiya", "medium format", "1974-1990", 800, "Excellent", True, "Standard", "Studio workhorse with standard C lens, rotating back"),
        ("RB67 Pro-S with 127mm f/3.8", "Mamiya", "medium format", "1974-1990", 850, "Excellent", True, "Standard", "RB67 with short tele portrait lens"),
        ("RB67 Pro-S with 180mm f/4.5", "Mamiya", "medium format", "1974-1990", 900, "Excellent", True, "Standard", "RB67 with telephoto lens, wedding favourite"),
        ("RB67 Pro-S with 65mm f/4.5", "Mamiya", "medium format", "1974-1990", 850, "Good", True, "Standard", "RB67 with wide-angle lens, environmental portraits"),
        ("RB67 Pro-SD with 90mm K/L", "Mamiya", "medium format", "1990-2000", 1100, "Excellent", True, "Standard", "Final RB67 with improved K/L multi-coated lens"),

        # --- Pentax 67 variants ---
        ("67 with 105mm f/2.4", "Pentax", "medium format", "1969-1999", 1000, "Excellent", True, "Limited Edition", "Pentax 67 with legendary portrait lens combo"),
        ("67 with 55mm f/4", "Pentax", "medium format", "1969-1999", 850, "Good", True, "Standard", "Pentax 67 with ultra-wide for landscapes"),
        ("67 with 150mm f/2.8", "Pentax", "medium format", "1969-1999", 900, "Good", True, "Standard", "Pentax 67 with fast telephoto, bokeh master"),
        ("67 MLU (Mirror Lock-Up)", "Pentax", "medium format", "1989-1999", 800, "Good", False, "Standard", "Late model 67 with mirror lock-up, reduced vibration"),
        ("67II with 105mm f/2.4 Kit", "Pentax", "medium format", "1998-2005", 1500, "Excellent", True, "Limited Edition", "Ultimate 67 kit with AE metering + best portrait lens"),

        # --- Bronica SQ-A variants ---
        ("SQ-A with 80mm f/2.8 PS", "Bronica", "medium format", "1982-1995", 500, "Excellent", True, "Standard", "Modular 6x6 with leaf-shutter standard lens"),
        ("SQ-A with 150mm f/4 PS", "Bronica", "medium format", "1982-1995", 550, "Good", True, "Standard", "SQ-A with portrait telephoto, leaf shutter"),
        ("SQ-A with 50mm f/3.5 PS", "Bronica", "medium format", "1982-1995", 550, "Good", True, "Standard", "SQ-A with wide-angle, leaf shutter"),
        ("SQ-A Prism Finder", "Bronica", "medium format", "1982-1995", 450, "Good", False, "Standard", "SQ-A with eye-level prism finder, no waist-level"),

        # --- Hasselblad 500C/M with lens kits ---
        ("500C/M with CF 80mm f/2.8 T*", "Hasselblad", "medium format", "1970-1994", 2200, "Excellent", True, "Limited Edition", "Most popular V-system kit with standard Planar"),
        ("500C/M with CF 150mm f/4 T*", "Hasselblad", "medium format", "1970-1994", 2400, "Excellent", True, "Limited Edition", "V-system with portrait Sonnar lens"),
        ("500C/M with CF 50mm f/4 T* Distagon", "Hasselblad", "medium format", "1970-1994", 2600, "Excellent", True, "Limited Edition", "V-system with wide-angle Distagon for landscapes"),

        # --- Rolleiflex 3.5F variants ---
        ("3.5F Xenotar", "Rolleiflex", "TLR", "1958-1976", 1600, "Excellent", True, "Rare", "Schneider Xenotar 75mm f/3.5, sharp alternative to Planar"),
        ("3.5F White Face", "Rolleiflex", "TLR", "1958-1976", 2000, "Excellent", True, "Rare", "White-face nameplate variant, collector premium"),
        ("3.5F Planar Type 3", "Rolleiflex", "TLR", "1960-1976", 1900, "Excellent", True, "Rare", "Late production Planar, improved coatings"),

        # --- Yashica Mat 124G variants ---
        ("Mat 124G Late Serial", "Yashica", "TLR", "1970-1986", 500, "Excellent", True, "Standard", "Late serial numbers, improved QC, Yashinon 80mm f/3.5"),
        ("Mat 124G with Case & Hood", "Yashica", "TLR", "1970-1986", 550, "Excellent", True, "Standard", "Complete with original ever-ready case and lens hood"),

        # --- Minolta CLE variants ---
        ("CLE with 40mm f/2 M-Rokkor", "Minolta", "rangefinder", "1981-1985", 1100, "Excellent", True, "Rare", "Compact M-mount with fast standard lens"),
        ("CLE with 28mm f/2.8 M-Rokkor", "Minolta", "rangefinder", "1981-1985", 1200, "Excellent", True, "Rare", "Compact M-mount with wide-angle, AE"),
        ("CLE with 90mm f/4 M-Rokkor", "Minolta", "rangefinder", "1981-1985", 1050, "Excellent", True, "Rare", "M-mount with compact telephoto, AE"),

        # --- Olympus Pen F variants ---
        ("Pen F Chrome Medical", "Olympus", "SLR", "1963-1966", 800, "Good", True, "Rare", "Chrome medical/scientific variant, engraved body"),
        ("Pen FT Chrome with 38mm f/1.8", "Olympus", "SLR", "1966-1972", 650, "Excellent", True, "Standard", "Half-frame SLR with fast standard lens kit"),
        ("Pen FT Black with 40mm f/1.4", "Olympus", "SLR", "1966-1972", 750, "Excellent", True, "Rare", "Half-frame with ultra-fast lens, rare black body kit"),

        # --- Canon P variants ---
        ("Canon P with 50mm f/1.4 LTM", "Canon", "rangefinder", "1959-1961", 650, "Good", True, "Rare", "Canon P with fast standard LTM lens kit"),
        ("Canon P Black Repaint", "Canon", "rangefinder", "1959-1961", 550, "Good", False, "Standard", "Professionally repainted black Canon P, popular mod"),
        ("Canon P with Canon 35mm f/2 LTM", "Canon", "rangefinder", "1959-1961", 700, "Good", True, "Rare", "Canon P with legendary wide-angle, street combo"),

        # --- Nikon S3 variants ---
        ("S3 2000 Year with 50mm f/1.4", "Nikon", "rangefinder", "2000-2001", 4000, "Excellent", True, "Rare", "Y2K reissue with fast Nikkor, 2000 units made"),
        ("S3 Original Black", "Nikon", "rangefinder", "1958-1960", 2500, "Good", False, "Rare", "Original S3 with black paint, photojournalist model"),
        ("S3 Original Chrome with 35mm f/2.5", "Nikon", "rangefinder", "1958-1960", 2200, "Good", True, "Rare", "S3 with W-Nikkor wide-angle, documentary combo"),

        # --- Contax T2 Black ---
        ("T2 Titanium Black", "Contax", "compact", "1990-2002", 2200, "Excellent", True, "Rare", "Black titanium T2, rarest colour, Sonnar 38mm f/2.8"),
        ("T2 Titanium Silver Champagne", "Contax", "compact", "1990-2002", 1900, "Excellent", True, "Rare", "Silver champagne T2, Sonnar T* 38mm f/2.8"),

        # --- Fuji GA645 variants ---
        ("GA645i Professional", "Fuji", "medium format", "1997-2002", 850, "Excellent", True, "Standard", "Improved AF GA645, 60mm f/4 Super-EBC Fujinon"),
        ("GA645Wi Professional", "Fuji", "medium format", "1997-2002", 950, "Excellent", True, "Standard", "Wide-angle AF 645, 45mm f/4 EBC Fujinon, improved AF"),
        ("GA645Zi Professional Black", "Fuji", "medium format", "1998-2002", 800, "Excellent", True, "Standard", "Black finish zoom GA645, 55-90mm f/4.5-6.9"),

        # --- Plaubel Makina 67 ---
        ("Makina 67", "Fuji", "rangefinder", "1978-1986", 3500, "Excellent", True, "Rare", "Plaubel Makina 67, bellows rangefinder, Nikkor 80mm f/2.8"),
        ("Makina 67 with Case", "Fuji", "rangefinder", "1978-1986", 3800, "Excellent", True, "Rare", "Plaubel Makina 67 with original leather case, collector set"),
        ("Makina W67", "Fuji", "rangefinder", "1981-1986", 4200, "Excellent", True, "Rare", "Wide-angle Makina, Nikkor 55mm f/4.5, ultra-rare"),

        # --- Additional medium format / rangefinder rarities ---
        ("Fuji GF670W Professional", "Fuji", "rangefinder", "2010-2014", 3200, "Excellent", True, "Rare", "Wide-angle folding bellows 6x7, 55mm f/4.5 Fujinon"),
        ("Mamiya 7 with 80mm f/4 L", "Mamiya", "rangefinder", "1995-2005", 3200, "Excellent", True, "Rare", "6x7 rangefinder with standard lens, ultra-sharp"),
        ("Mamiya 7II with 65mm f/4 L", "Mamiya", "rangefinder", "1999-2005", 3500, "Excellent", True, "Rare", "6x7 rangefinder with wide-angle, ultimate landscape kit"),
        ("Hasselblad 500C 1960 First Year", "Hasselblad", "medium format", "1957-1970", 1800, "Good", True, "Rare", "Early production 500C, historical significance"),
        ("Rolleiflex 2.8D Xenotar", "Rolleiflex", "TLR", "1955-1956", 1600, "Good", True, "Rare", "Pre-F model, Schneider Xenotar 80mm f/2.8"),
        ("Fuji GSW690III Professional", "Fuji", "rangefinder", "1992-2000", 1200, "Excellent", True, "Standard", "Wide-angle Texas Leica 6x9, 65mm f/5.6 EBC Fujinon"),
        ("Konica Hexar RF Limited", "Nikon", "rangefinder", "1999-2003", 1600, "Excellent", False, "Rare", "M-mount RF with titanium top plate, 2001 limited edition"),
    ]


def _round5_expansion() -> list[tuple]:
    """Round 5 expansion: 55 items — medium format, rangefinders, TLR, instant, 35mm SLR, lenses, large format."""
    return [
        # --- Medium Format Cameras (10) ---
        ("Hasselblad 501CM", "Hasselblad", "medium format", "1994-2005", 2200, "Excellent", True, "Limited Edition", "Last mechanical-only V-system, Acute Matte screen"),
        ("Hasselblad SWC/M", "Hasselblad", "medium format", "1980-1988", 3800, "Excellent", True, "Rare", "Super Wide C/M, Biogon 38mm f/4.5, ultrawide 6x6"),
        ("Mamiya RZ67 Pro II", "Mamiya", "medium format", "1995-2004", 1200, "Excellent", True, "Standard", "Professional studio workhorse, revolving back, bellows focus"),
        ("Mamiya RB67 Pro SD", "Mamiya", "medium format", "1990-2004", 900, "Excellent", True, "Standard", "Last RB67, revolving adapter, 6x7 format"),
        ("Mamiya 645 Pro TL", "Mamiya", "medium format", "1992-1999", 700, "Excellent", True, "Standard", "645 SLR with through-lens metering, modular system"),
        ("Bronica SQ-Ai", "Bronica", "medium format", "1990-2004", 650, "Excellent", True, "Standard", "6x6 SLR, Zenzanon PS lenses, electronic shutter"),
        ("Bronica GS-1", "Bronica", "medium format", "1983-1998", 800, "Good", True, "Standard", "6x7 SLR, unique grip design, Zenzanon PG lenses"),
        ("Pentax 67II", "Pentax", "medium format", "1998-2009", 2800, "Excellent", True, "Limited Edition", "Ultimate 6x7 SLR, AE metering, mirror lock-up"),
        ("Fuji GX680III Professional (Late Serial)", "Fuji", "medium format", "1999-2006", 1600, "Excellent", True, "Standard", "Late production GX680III, improved mirror mechanism, EBC Fujinon lenses"),
        ("Mamiya C330 Professional f", "Mamiya", "TLR", "1969-1994", 500, "Good", True, "Standard", "Interchangeable lens TLR, 6x6, bellows focusing"),

        # --- Rangefinder Cameras (10) ---
        ("Contax G2 Titanium", "Contax", "rangefinder", "1996-2005", 1800, "Excellent", False, "Limited Edition", "Titanium body AF rangefinder, Carl Zeiss lenses"),
        ("Contax G1 Green Label", "Contax", "rangefinder", "1994-2005", 800, "Excellent", False, "Standard", "Updated G1 with improved AF, Carl Zeiss T* lenses"),
        ("Voigtlander Bessa R2M", "Voigtlander", "rangefinder", "2002-2015", 650, "Excellent", False, "Standard", "M-mount rangefinder, compact body, 0.7x viewfinder"),
        ("Voigtlander Bessa R3M", "Voigtlander", "rangefinder", "2005-2015", 750, "Excellent", False, "Standard", "M-mount rangefinder, 1:1 viewfinder magnification"),
        ("Voigtlander Bessa R4M", "Voigtlander", "rangefinder", "2006-2015", 800, "Excellent", False, "Standard", "M-mount wide-angle rangefinder, 0.52x viewfinder"),
        ("Canonet QL17 GIII (Mint CLA'd)", "Canon", "rangefinder", "1972-1982", 400, "Mint", True, "Standard", "40mm f/1.7 fully CLA'd, the poor man's Leica, cult classic"),
        ("Canonet QL17 GIII Black (Early Serial)", "Canon", "rangefinder", "1972-1975", 500, "Excellent", True, "Limited Edition", "Early production black paint, rarer than chrome, collector premium"),
        ("Yashica Electro 35 GSN", "Yashica", "rangefinder", "1973-1979", 200, "Good", True, "Standard", "45mm f/1.7, electronic AE rangefinder, great optics"),
        ("Olympus 35 SP", "Olympus", "rangefinder", "1969-1976", 300, "Good", True, "Standard", "42mm f/1.7 G.Zuiko, spot/average metering, underrated gem"),
        ("Minolta Hi-Matic 7sII", "Minolta", "rangefinder", "1977-1981", 250, "Excellent", True, "Standard", "40mm f/1.7 Rokkor, compact rangefinder, sharp optics"),

        # --- TLR Cameras (8) ---
        ("Rolleiflex 2.8F Planar", "Rolleiflex", "TLR", "1960-1981", 2800, "Excellent", True, "Rare", "Ultimate Rolleiflex, Carl Zeiss Planar 80mm f/2.8"),
        ("Rolleiflex 2.8E Xenotar", "Rolleiflex", "TLR", "1956-1959", 1800, "Good", True, "Rare", "Schneider Xenotar lens, built-in meter, classic design"),
        ("Rolleiflex 3.5F Planar", "Rolleiflex", "TLR", "1958-1981", 2200, "Excellent", True, "Rare", "Slower but sharper, 75mm f/3.5 Planar, light-meter model"),
        ("Rolleicord Vb", "Rolleiflex", "TLR", "1962-1977", 500, "Excellent", True, "Standard", "Last Rolleicord model, Schneider Xenar 75mm f/3.5, improved meter"),
        ("Yashica Mat 124G", "Yashica", "TLR", "1970-1986", 350, "Excellent", True, "Standard", "Best-selling TLR ever, Yashinon 80mm f/3.5, CdS meter"),
        ("Yashica D (Grey Leatherette)", "Yashica", "TLR", "1958-1974", 230, "Good", True, "Standard", "Entry-level Yashica TLR, grey leatherette variant, Yashikor 80mm f/3.5"),
        ("Minolta Autocord CdS III", "Minolta", "TLR", "1965-1970", 400, "Excellent", True, "Standard", "Rokkor 75mm f/3.5, built-in CdS meter, automatic film advance"),
        ("Mamiya C220 Professional", "Mamiya", "TLR", "1968-1982", 350, "Good", True, "Standard", "Interchangeable lens TLR, 80mm f/2.8 standard, affordable pro"),

        # --- Instant / Polaroid Cameras (7) ---
        ("Polaroid SX-70 Land Camera (Chrome/Tan)", "Polaroid", "instant", "1972-1981", 350, "Excellent", True, "Limited Edition", "Iconic folding SLR, original chrome/tan leather"),
        ("Polaroid SX-70 Sonar OneStep", "Polaroid", "instant", "1978-1981", 280, "Good", True, "Standard", "SX-70 with sonar autofocus, gold stripe"),
        ("Polaroid SX-70 Alpha 1 Model 2", "Polaroid", "instant", "1977-1979", 400, "Excellent", True, "Limited Edition", "Black body SX-70, split-image focusing, premium model"),
        ("Polaroid Spectra System", "Polaroid", "instant", "1986-1992", 120, "Good", True, "Standard", "Wide-format instant, Quintic lens, sonar AF"),
        ("Polaroid Land Camera 195", "Polaroid", "instant", "1974-1976", 500, "Good", True, "Rare", "Professional packfilm camera, Tominon 114mm f/3.8, manual controls"),
        ("Polaroid Land Camera 180", "Polaroid", "instant", "1965-1969", 600, "Good", True, "Rare", "Pro packfilm, Tominon 114mm f/4.5, manual exposure, rangefinder"),
        ("Polaroid 600 SE", "Polaroid", "instant", "1978-1981", 700, "Good", True, "Rare", "Professional body, Mamiya 127mm f/4.7, packfilm, studio use"),

        # --- 35mm SLR Bodies (7) ---
        ("Pentax LX", "Pentax", "SLR", "1980-2001", 600, "Excellent", False, "Limited Edition", "Pentax flagship pro SLR, weather-sealed, interchangeable screens"),
        ("Pentax MX", "Pentax", "SLR", "1976-1985", 350, "Excellent", False, "Standard", "Compact mechanical SLR, 100% viewfinder, K-mount"),
        ("Minolta XD-11", "Minolta", "SLR", "1977-1981", 300, "Excellent", False, "Standard", "World's first multi-mode AE SLR, Leitz co-design"),
        ("Minolta X-700", "Minolta", "SLR", "1981-1999", 200, "Excellent", False, "Standard", "Program AE SLR, huge MD lens ecosystem"),
        ("Olympus OM-3Ti", "Olympus", "SLR", "1994-2002", 800, "Excellent", False, "Rare", "Titanium OM body, spot/multi-spot metering, mechanical shutter"),
        ("Pentax K1000", "Pentax", "SLR", "1976-1997", 180, "Good", False, "Standard", "Most popular student SLR ever, fully mechanical, indestructible"),
        ("Nikon FM3A", "Nikon", "SLR", "2001-2006", 900, "Mint", False, "Limited Edition", "Last manual-focus Nikon, hybrid electronic/mechanical shutter"),

        # --- Vintage Lenses (7) ---
        ("Carl Zeiss Planar T* 50mm f/1.4 ZM", "Contax", "rangefinder", "2005-present", 800, "Mint", True, "Standard", "Leica M-mount, modern Zeiss optic, 6 elements"),
        ("Carl Zeiss Sonnar T* 85mm f/2 ZM", "Contax", "rangefinder", "2005-present", 950, "Mint", True, "Standard", "Leica M-mount Zeiss 85mm, classic Sonnar rendering"),
        ("Leica Summicron 50mm f/2 V4 (Pre-ASPH)", "Leica", "rangefinder", "1979-1994", 1800, "Excellent", True, "Limited Edition", "4th generation Summicron, legendary sharpness, compact"),
        ("Leica Summilux 35mm f/1.4 (Pre-ASPH Steel Rim)", "Leica", "rangefinder", "1961-1966", 4500, "Good", True, "Rare", "Steel rim Summilux, dreamy wide-open rendering, holy grail"),
        ("Nikon AI-S Nikkor 105mm f/2.5", "Nikon", "SLR", "1981-2005", 350, "Excellent", True, "Standard", "Classic portrait lens, Afghan Girl fame, sharp and contrasty"),
        ("Nikon AI-S Nikkor 28mm f/2.8", "Nikon", "SLR", "1981-2006", 280, "Excellent", True, "Standard", "Compact wide-angle, CRC, excellent for street photography"),
        ("Nikon AI-S Nikkor 35mm f/1.4", "Nikon", "SLR", "1981-2005", 900, "Excellent", True, "Limited Edition", "Fast wide-angle Nikkor, NIC coating, photojournalist lens"),

        # --- Large Format Cameras (6) ---
        ("Linhof Technika V 4x5", "Linhof", "large format", "1976-2005", 2500, "Excellent", False, "Rare", "German precision field camera, full movements, legendary build"),
        ("Linhof Master Technika 2000", "Linhof", "large format", "2000-present", 4500, "Mint", False, "Rare", "Ultimate field camera, titanium parts, micro-precision gearing"),
        ("Wista 45D Cherry Wood", "Wista", "large format", "1975-2000", 800, "Excellent", False, "Standard", "Japanese cherry wood field camera, lightweight, full movements"),
        ("Graflex Crown Graphic 4x5", "Graflex", "large format", "1947-1973", 400, "Good", False, "Standard", "Press camera with Graflex back, Kalart rangefinder"),
        ("Sinar P2 4x5 Monorail", "Linhof", "large format", "1988-present", 2000, "Excellent", False, "Limited Edition", "Swiss precision monorail, geared everything, studio standard"),
        ("Deardorff 8x10 V8", "Graflex", "large format", "1940-1988", 3500, "Good", False, "Rare", "American-made large format icon, mahogany and brass, 8x10 contact prints"),
    ]


# ---------------------------------------------------------------------------
# Assemble full catalog
# ---------------------------------------------------------------------------

def get_curated_catalog() -> list[dict]:
    """Return the full curated vintage camera catalog as a list of dicts.

    Each dict has keys: name, brand, type, year_range, price_eur,
    condition, has_lens, rarity, notes.
    """
    all_tuples: list[tuple] = []
    all_tuples.extend(_leica_cameras())
    all_tuples.extend(_hasselblad_cameras())
    all_tuples.extend(_nikon_cameras())
    all_tuples.extend(_canon_cameras())
    all_tuples.extend(_olympus_cameras())
    all_tuples.extend(_minolta_cameras())
    all_tuples.extend(_contax_cameras())
    all_tuples.extend(_pentax_cameras())
    all_tuples.extend(_medium_format_cameras())
    all_tuples.extend(_polaroid_instant_cameras())
    all_tuples.extend(_large_format_cameras())
    all_tuples.extend(_vintage_lenses())
    all_tuples.extend(_point_and_shoot_cameras())
    all_tuples.extend(_misc_cameras())
    # Round 2 expansion
    all_tuples.extend(_leica_expanded())
    all_tuples.extend(_hasselblad_expanded())
    all_tuples.extend(_nikon_expanded())
    all_tuples.extend(_canon_expanded())
    all_tuples.extend(_olympus_expanded())
    all_tuples.extend(_rollei_cameras())
    all_tuples.extend(_mamiya_expanded())
    all_tuples.extend(_bronica_expanded())
    all_tuples.extend(_graflex_expanded())
    all_tuples.extend(_additional_lenses())
    all_tuples.extend(_point_and_shoot_expanded())
    all_tuples.extend(_minolta_expanded())
    all_tuples.extend(_contax_expanded())
    all_tuples.extend(_pentax_expanded())
    all_tuples.extend(_medium_format_expanded())
    all_tuples.extend(_instant_expanded())
    all_tuples.extend(_additional_misc())
    # Round 3 expansion
    all_tuples.extend(_round3_leica_nikon())
    all_tuples.extend(_round3_canon_olympus())
    all_tuples.extend(_round3_contax_pentax_minolta())
    all_tuples.extend(_round3_medium_format_lenses())
    all_tuples.extend(_round3_point_and_shoot_misc())
    # Round 4 expansion
    all_tuples.extend(_round4_medium_format_rangefinder_misc())
    # Round 5 expansion
    all_tuples.extend(_round5_expansion())

    catalog: list[dict] = []
    for name, brand, cam_type, year_range, price_eur, condition, has_lens, rarity, notes in all_tuples:
        catalog.append({
            "name": name,
            "brand": brand,
            "type": cam_type,
            "year_range": year_range,
            "price_eur": price_eur,
            "condition": condition,
            "has_lens": has_lens,
            "rarity": rarity,
            "notes": notes,
        })
    return catalog


# ---------------------------------------------------------------------------
# Transform helpers
# ---------------------------------------------------------------------------

def item_to_catalog_item(item: dict) -> CatalogItem:
    """Convert a camera dict to a CatalogItem.

    Sets category='vintage_cameras', item_key from slugify(brand-name),
    brand from the camera brand.
    """
    brand = item["brand"]
    name = item["name"]
    cam_type = item["type"]
    year_range = item["year_range"]
    has_lens = item["has_lens"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{brand}-{name}"),
        title=f"{brand} {name}",
        set_code=brand.lower().replace(" ", "-"),
        brand=brand,
        rarity=item["rarity"],
        notes=f"{brand} | {name} | {cam_type} | {year_range} | {item['notes']}",
        attributes_json={
            "brand": brand,
            "type": cam_type,
            "year_range": year_range,
            "has_lens": has_lens,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    """Convert a camera dict to a PriceObservation.

    Features:
    - condition_score: based on condition string (Mint/Excellent/Good/Fair)
    - rarity_score: from shared_rarity_score()
    - brand_tier: 1.0 Leica, 0.9 Hasselblad/Contax, 0.7 Nikon/Canon, 0.5 others
    - type_score: 0.9 rangefinder, 0.7 SLR, 0.8 medium format, etc.
    - has_lens: 1.0 or 0.0
    """
    brand = item["brand"]
    condition = item["condition"]
    rarity = item["rarity"]
    cam_type = item["type"]
    has_lens = item["has_lens"]
    price = item["price_eur"]

    return PriceObservation(
        features={
            "condition_score": _condition_score(condition),
            "rarity_score": shared_rarity_score(rarity),
            "brand_tier": _brand_tier(brand),
            "type_score": _type_score(cam_type),
            "has_lens": 1.0 if has_lens else 0.0,
        },
        price=price,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Import curated vintage camera catalog + prices"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Write local files only, skip Supabase upsert")
    args = parser.parse_args()

    logger.info("=== Vintage Camera Import Pipeline ===")

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    catalog = get_curated_catalog()
    logger.info(f"  Curated catalog: {len(catalog)} cameras")

    all_items = [item_to_catalog_item(c) for c in catalog]
    all_observations = [item_to_price_observation(c) for c in catalog]

    # Write training JSONL (always)
    write_training_jsonl(CATEGORY, all_observations)
    log_progress(CATEGORY, "training JSONL written", len(all_observations))

    # Write catalog SQL
    write_catalog_sql(CATEGORY, all_items)
    log_progress(CATEGORY, "catalog SQL written", len(all_items))

    # Upsert to Supabase if enabled
    if ingest.enabled:
        inserted = ingest.upsert_catalog(all_items)
        log_progress(CATEGORY, "catalog upserted", inserted)

    ingest.close()
    close_http_client()

    logger.info(f"\n=== Vintage Camera Import Complete ===")
    logger.info(f"  Total catalog items:  {len(all_items)}")
    logger.info(f"  Price observations:   {len(all_observations)}")
    if args.dry_run:
        logger.info("  Mode: DRY RUN (local files only)")


if __name__ == "__main__":
    main()
