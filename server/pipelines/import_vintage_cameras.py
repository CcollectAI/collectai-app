"""
Curated Vintage Camera Import Pipeline — Film & Analog Camera Collectibles.

Imports a curated catalog of 80+ real vintage/film cameras across 11 subcategories:
  Leica, Hasselblad, Nikon, Canon, Olympus, Minolta, Contax, Pentax,
  Medium Format, Polaroid/Instant, Large Format

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
# Curated catalog — 80+ vintage/film cameras
# Each tuple: (name, brand, type, year_range, price_eur, condition, has_lens, rarity, notes)
# ---------------------------------------------------------------------------


def _leica_cameras() -> list[tuple]:
    """12 Leica cameras — iconic rangefinders and SLRs."""
    return [
        ("M3 Double Stroke", "Leica", "rangefinder", "1954-1966", 2800, "Excellent", True, "Limited Edition", "First Leica M, double-stroke advance"),
        ("M3 Single Stroke", "Leica", "rangefinder", "1954-1966", 2400, "Good", True, "Limited Edition", "Single-stroke film advance variant"),
        ("M6 Classic Black", "Leica", "rangefinder", "1984-1998", 3200, "Excellent", False, "Limited Edition", "Built-in light meter, most popular M"),
        ("M6 TTL Silver", "Leica", "rangefinder", "1998-2002", 3600, "Excellent", False, "Limited Edition", "Through-the-lens metering variant"),
        ("M2 Chrome", "Leica", "rangefinder", "1957-1967", 2200, "Good", False, "Limited Edition", "Simplified M3, 35mm framelines"),
        ("IIIf Red Dial", "Leica", "rangefinder", "1950-1956", 1200, "Good", True, "Rare", "Late screw-mount Leica, red dial variant"),
        ("IIIg", "Leica", "rangefinder", "1957-1960", 1500, "Excellent", True, "Rare", "Last screw-mount Leica"),
        ("CL", "Leica", "rangefinder", "1973-1976", 800, "Good", True, "Standard", "Compact M-mount rangefinder, Minolta-built"),
        ("M4-P", "Leica", "rangefinder", "1981-1987", 1800, "Excellent", False, "Limited Edition", "Red dot Leica, 28/75mm framelines"),
        ("R6.2", "Leica", "SLR", "1992-2002", 900, "Excellent", False, "Standard", "Mechanical Leica R-mount SLR"),
        ("R4", "Leica", "SLR", "1980-1987", 500, "Good", False, "Standard", "Electronic Leica R-mount SLR"),
        ("M-A (Typ 127) Silver", "Leica", "rangefinder", "2014-present", 5200, "Mint", False, "Limited Edition", "Modern all-mechanical M, no meter"),
    ]


def _hasselblad_cameras() -> list[tuple]:
    """8 Hasselblad cameras — medium format icons."""
    return [
        ("500C/M", "Hasselblad", "medium format", "1970-1994", 1800, "Excellent", True, "Limited Edition", "Most popular V-system body"),
        ("500C", "Hasselblad", "medium format", "1957-1970", 1400, "Good", True, "Rare", "Original V-system, moon camera lineage"),
        ("503CW", "Hasselblad", "medium format", "1996-2006", 2500, "Excellent", True, "Limited Edition", "Winder-compatible V-system"),
        ("SWC/M", "Hasselblad", "medium format", "1980-1988", 3800, "Excellent", True, "Rare", "Super Wide with fixed 38mm Biogon"),
        ("X-Pan", "Hasselblad", "rangefinder", "1998-2003", 4500, "Excellent", True, "Rare", "Panoramic 35mm, dual format"),
        ("X-Pan II", "Hasselblad", "rangefinder", "2003-2006", 5200, "Excellent", True, "Rare", "Updated panoramic, improved viewfinder"),
        ("2000FC/M", "Hasselblad", "medium format", "1981-1984", 1200, "Good", False, "Standard", "Focal plane shutter V-system"),
        ("553ELX", "Hasselblad", "medium format", "1988-1999", 1600, "Good", True, "Standard", "Motorized V-system body"),
    ]


def _nikon_cameras() -> list[tuple]:
    """10 Nikon cameras — legendary SLRs and rangefinders."""
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
    ]


def _canon_cameras() -> list[tuple]:
    """10 Canon cameras — classic SLRs and rangefinders."""
    return [
        ("AE-1 Black", "Canon", "SLR", "1976-1984", 200, "Excellent", True, "Standard", "First microprocessor SLR, massive seller"),
        ("AE-1 Chrome", "Canon", "SLR", "1976-1984", 150, "Good", True, "Standard", "Chrome variant, iconic beginner SLR"),
        ("AE-1 Program", "Canon", "SLR", "1981-1987", 220, "Excellent", True, "Standard", "Program mode upgrade of AE-1"),
        ("A-1", "Canon", "SLR", "1978-1985", 300, "Excellent", False, "Standard", "Multi-mode electronic SLR, pro-level"),
        ("F-1 Original", "Canon", "SLR", "1971-1976", 500, "Excellent", False, "Limited Edition", "Canon first pro SLR, fully mechanical"),
        ("F-1 New", "Canon", "SLR", "1981-1992", 550, "Excellent", False, "Limited Edition", "Redesigned pro body, modular system"),
        ("Canon 7", "Canon", "rangefinder", "1961-1964", 600, "Good", False, "Rare", "Top-tier Canon rangefinder, LTM"),
        ("Canon P", "Canon", "rangefinder", "1959-1961", 450, "Good", False, "Rare", "Popular Canon rangefinder, simplified 7"),
        ("Canonet QL17 GIII Black", "Canon", "rangefinder", "1972-1982", 350, "Excellent", True, "Standard", "Compact rangefinder, sharp 40mm f/1.7"),
        ("Canonet QL17 GIII Chrome", "Canon", "rangefinder", "1972-1982", 280, "Good", True, "Standard", "Chrome version, fixed lens classic"),
    ]


def _olympus_cameras() -> list[tuple]:
    """8 Olympus cameras — compact legends and OM system."""
    return [
        ("OM-1 MD Chrome", "Olympus", "SLR", "1972-1979", 350, "Excellent", False, "Standard", "Compact mechanical SLR, Maitani design"),
        ("OM-1n Black", "Olympus", "SLR", "1979-1987", 400, "Excellent", False, "Standard", "Improved OM-1 with flash sync"),
        ("OM-2n", "Olympus", "SLR", "1979-1984", 350, "Good", False, "Standard", "OTF auto exposure, electronic shutter"),
        ("XA", "Olympus", "rangefinder", "1979-1985", 300, "Excellent", True, "Standard", "Clamshell pocketable rangefinder, f/2.8"),
        ("XA2", "Olympus", "compact", "1980-1985", 120, "Good", True, "Standard", "Zone-focus compact, 35mm f/3.5"),
        ("Pen F Chrome", "Olympus", "SLR", "1963-1966", 600, "Excellent", True, "Rare", "Half-frame SLR, rotary shutter"),
        ("Mju II (Stylus Epic)", "Olympus", "point-and-shoot", "1997-2002", 400, "Excellent", True, "Limited Edition", "Cult 35mm f/2.8 point-and-shoot"),
        ("Trip 35", "Olympus", "compact", "1967-1984", 120, "Good", True, "Standard", "Solar-cell metered zone-focus compact"),
    ]


def _minolta_cameras() -> list[tuple]:
    """6 Minolta cameras — underrated SLRs and rangefinders."""
    return [
        ("X-700", "Minolta", "SLR", "1981-1999", 200, "Excellent", True, "Standard", "Program auto SLR, sharp Rokkor lenses"),
        ("X-700 Black (body only)", "Minolta", "SLR", "1981-1999", 150, "Good", False, "Standard", "Body only, MD mount"),
        ("SRT 101", "Minolta", "SLR", "1966-1975", 180, "Good", True, "Standard", "CLC metering pioneer, fully mechanical"),
        ("CLE", "Minolta", "rangefinder", "1981-1985", 900, "Excellent", True, "Rare", "Compact M-mount rangefinder, AE"),
        ("TC-1", "Minolta", "compact", "1996-2003", 1200, "Excellent", True, "Rare", "Titanium luxury compact, 28mm f/3.5 G-Rokkor"),
        ("XD-7 (XD-11)", "Minolta", "SLR", "1977-1982", 250, "Good", False, "Standard", "First multi-mode SLR, Leica collaboration"),
    ]


def _contax_cameras() -> list[tuple]:
    """6 Contax cameras — premium Japanese rangefinders and SLRs."""
    return [
        ("T2 Titanium", "Contax", "compact", "1990-2002", 1800, "Excellent", True, "Rare", "Premium titanium compact, Sonnar T* 38mm f/2.8"),
        ("T3 Titanium", "Contax", "compact", "2001-2005", 3500, "Excellent", True, "Rare", "Last Contax T, Sonnar T* 35mm f/2.8"),
        ("G2 Black", "Contax", "rangefinder", "1996-2005", 1200, "Excellent", False, "Limited Edition", "AF rangefinder, Zeiss lenses"),
        ("G1 Green Label", "Contax", "rangefinder", "1994-2005", 500, "Good", False, "Standard", "First Contax G, updated firmware"),
        ("RTS III", "Contax", "SLR", "1990-2000", 700, "Good", False, "Standard", "Real-time vacuum film plane, pro SLR"),
        ("167MT", "Contax", "SLR", "1987-1997", 300, "Good", False, "Standard", "Multi-program SLR, Yashica/Contax mount"),
    ]


def _pentax_cameras() -> list[tuple]:
    """6 Pentax cameras — rugged SLRs and medium format."""
    return [
        ("K1000", "Pentax", "SLR", "1976-1997", 150, "Good", True, "Standard", "Ultimate student SLR, fully mechanical"),
        ("K1000 SE", "Pentax", "SLR", "1976-1997", 180, "Excellent", True, "Standard", "Special edition with split-image focus"),
        ("MX", "Pentax", "SLR", "1976-1985", 350, "Excellent", False, "Standard", "Compact mechanical pro SLR"),
        ("LX", "Pentax", "SLR", "1980-2001", 600, "Excellent", False, "Limited Edition", "Pentax pro flagship, weather sealed"),
        ("67 (6x7)", "Pentax", "medium format", "1969-1999", 700, "Good", True, "Standard", "Medium format SLR, 6x7 negatives"),
        ("645N", "Pentax", "medium format", "1997-2001", 500, "Good", True, "Standard", "AF medium format SLR, 645 format"),
    ]


def _medium_format_cameras() -> list[tuple]:
    """8 medium format cameras — Mamiya, Bronica, Yashica, Rolleiflex."""
    return [
        ("RZ67 Pro II", "Mamiya", "medium format", "1995-2004", 1200, "Excellent", True, "Limited Edition", "Professional 6x7, revolving back"),
        ("RB67 Pro-S", "Mamiya", "medium format", "1974-1990", 700, "Good", True, "Standard", "Studio workhorse, rotating back"),
        ("RB67 Pro-SD", "Mamiya", "medium format", "1990-2000", 900, "Excellent", True, "Standard", "Final RB67, improved film backs"),
        ("7 II", "Mamiya", "rangefinder", "1999-2005", 2800, "Excellent", True, "Rare", "6x7 rangefinder, interchangeable lenses"),
        ("SQ-A", "Bronica", "medium format", "1982-1995", 400, "Good", True, "Standard", "Modular 6x6, leaf shutter lenses"),
        ("ETRSi", "Bronica", "medium format", "1989-2000", 350, "Good", True, "Standard", "Compact 645 format system"),
        ("Mat 124G", "Yashica", "TLR", "1970-1986", 450, "Excellent", True, "Standard", "Last Yashica TLR, Yashinon 80mm f/3.5"),
        ("2.8F Planar", "Rolleiflex", "TLR", "1960-1981", 2200, "Excellent", True, "Rare", "Definitive TLR, Zeiss Planar 80mm f/2.8"),
    ]


def _polaroid_instant_cameras() -> list[tuple]:
    """5 Polaroid/instant cameras — icons of instant photography."""
    return [
        ("SX-70 Original Chrome", "Polaroid", "instant", "1972-1981", 350, "Good", True, "Limited Edition", "Folding SLR instant, design icon"),
        ("SX-70 Sonar OneStep", "Polaroid", "instant", "1978-1981", 250, "Good", True, "Standard", "Autofocus SX-70 variant"),
        ("SLR 680", "Polaroid", "instant", "1982-1988", 400, "Excellent", True, "Limited Edition", "Upgraded SX-70, sonar AF + flash"),
        ("Spectra System", "Polaroid", "instant", "1986-2008", 80, "Good", True, "Standard", "Wide-format instant, Quintic lens"),
        ("600 One Step Close-Up", "Polaroid", "instant", "1990-2000", 50, "Good", True, "Standard", "Fixed-focus consumer instant"),
    ]


def _large_format_cameras() -> list[tuple]:
    """3 large format cameras — press and field cameras."""
    return [
        ("Speed Graphic 4x5", "Graflex", "large format", "1947-1973", 500, "Good", True, "Standard", "Press camera icon, focal plane shutter"),
        ("Technika Master 45", "Linhof", "large format", "1972-2005", 2000, "Excellent", False, "Rare", "Precision field camera, full movements"),
        ("Crown Graphic 4x5", "Graflex", "large format", "1947-1973", 350, "Fair", True, "Standard", "Lightweight press camera variant"),
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
