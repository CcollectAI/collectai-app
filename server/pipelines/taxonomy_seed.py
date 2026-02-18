"""
Seed the taxonomy_registry table with the v1.0 taxonomy.

Reads the 36 categories and their regex patterns from
src/ingest/taxonomy_mapper.py, builds the categories and mapping_rules
JSONB payloads, and inserts a v1.0 row into taxonomy_registry.

Usage:
    python -m pipelines.taxonomy_seed
    python -m pipelines.taxonomy_seed --dry-run
    python -m pipelines.taxonomy_seed --version v1.0 --notes "Initial seed"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure repo root is on sys.path so `from src.ingest...` works
_repo_root = str(Path(__file__).resolve().parent.parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import asyncpg

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

logger = logging.getLogger("collectai.taxonomy_seed")


def _setup_logging(level: str = "INFO") -> None:
    if logger.handlers:
        return
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
    logger.addHandler(handler)


# ---------------------------------------------------------------------------
# Category metadata — display names, subtypes, and collections
# Mirrors types/category.ts and src/data/categories.ts
# ---------------------------------------------------------------------------

CATEGORY_DISPLAY_NAMES: dict[str, str] = {
    "pokemon": "Pokemon TCG",
    "mtg": "Magic: The Gathering",
    "yugioh": "Yu-Gi-Oh!",
    "lorcana": "Disney Lorcana",
    "funko": "Funko Pop",
    "designer_toys": "Designer Toys",
    "anime_figures": "Anime Figures & Statues",
    "hot_toys": "Hot Toys & Movie Statues",
    "lego": "LEGO",
    "gunpla": "Gunpla (Gundam Kits)",
    "scale_models": "Scale Model Kits",
    "warhammer": "Warhammer & Tabletop",
    "retro_games": "Retro Video Games",
    "manga": "Manga",
    "bluray_steelbook": "Blu-ray & Steelbooks",
    "anime_bluray": "Anime Blu-ray Box Sets",
    "anime_soundtrack": "Anime Soundtracks",
    "anime_ost_vinyl": "Anime OST Vinyl & CD",
    "kpop_merch": "K-pop Merch",
    "taylor_swift": "Taylor Swift",
    "pop_fandom": "Pop Fandom Merch",
    "kpop_lightsticks": "K-pop Lightsticks",
    "disney": "Disney Collectibles",
    "theme_park": "Theme Park Exclusives",
    "ghibli": "Studio Ghibli",
    "bandai_premium": "Bandai Premium",
    "jp_magazine": "JP Magazine Exclusives",
    "jp_event": "JP Event Exclusives",
    "nintendo_merch": "Nintendo & Pokemon Merch",
    "retro_pokemon": "Retro Pokemon Accessories",
    "one_piece": "One Piece",
    "vtuber": "VTuber Merch",
    "keycaps": "Artisan Keycaps",
    "loungefly": "Loungefly",
    "diecast": "Diecast",
    "sportscards": "Sports Cards",
}

# Subtypes known from the taxonomy_mapper SUBTYPE_PATTERNS
CATEGORY_SUBTYPES: dict[str, list[dict[str, str]]] = {
    "pokemon": [
        {"id": "graded", "name": "Graded Cards"},
        {"id": "sealed", "name": "Sealed Product"},
        {"id": "raw", "name": "Raw Cards"},
    ],
    "mtg": [
        {"id": "graded", "name": "Graded Cards"},
        {"id": "sealed", "name": "Sealed Product"},
        {"id": "raw", "name": "Raw Cards"},
    ],
    "yugioh": [
        {"id": "graded", "name": "Graded Cards"},
        {"id": "sealed", "name": "Sealed Product"},
        {"id": "raw", "name": "Raw Cards"},
    ],
    "lorcana": [
        {"id": "graded", "name": "Graded Cards"},
        {"id": "sealed", "name": "Sealed Product"},
        {"id": "raw", "name": "Raw Cards"},
    ],
    "funko": [
        {"id": "pop_vinyl", "name": "Pop! Vinyl"},
        {"id": "soda", "name": "Soda"},
        {"id": "chase", "name": "Chase Variant"},
    ],
    "anime_figures": [
        {"id": "scale_figure", "name": "Scale Figure"},
        {"id": "nendoroid", "name": "Nendoroid"},
        {"id": "figma", "name": "Figma"},
        {"id": "prize", "name": "Prize Figure"},
        {"id": "garage_kit", "name": "Garage Kit"},
    ],
    "lego": [
        {"id": "sealed_set", "name": "Sealed Set"},
        {"id": "minifig", "name": "Minifigure"},
        {"id": "used_set", "name": "Used Set"},
    ],
    "gunpla": [
        {"id": "hg", "name": "High Grade (HG)"},
        {"id": "rg", "name": "Real Grade (RG)"},
        {"id": "mg", "name": "Master Grade (MG)"},
        {"id": "pg", "name": "Perfect Grade (PG)"},
        {"id": "sd", "name": "Super Deformed (SD)"},
    ],
    "warhammer": [
        {"id": "40k", "name": "Warhammer 40K"},
        {"id": "aos", "name": "Age of Sigmar"},
        {"id": "horus_heresy", "name": "Horus Heresy"},
        {"id": "kill_team", "name": "Kill Team"},
    ],
    "retro_games": [
        {"id": "loose", "name": "Loose Cartridge"},
        {"id": "cib", "name": "Complete in Box"},
        {"id": "sealed", "name": "Sealed"},
        {"id": "graded", "name": "Graded"},
    ],
    "manga": [
        {"id": "single_vol", "name": "Single Volume"},
        {"id": "box_set", "name": "Box Set"},
        {"id": "oop", "name": "Out of Print"},
    ],
    "sportscards": [
        {"id": "graded", "name": "Graded Cards"},
        {"id": "raw", "name": "Raw Cards"},
        {"id": "sealed", "name": "Sealed Product"},
    ],
    "diecast": [
        {"id": "1_64", "name": "1:64 Scale"},
        {"id": "1_24", "name": "1:24 Scale"},
        {"id": "1_18", "name": "1:18 Scale"},
        {"id": "premium", "name": "Premium/Autoart"},
    ],
    "kpop_merch": [
        {"id": "photocard", "name": "Photocard"},
        {"id": "album", "name": "Album"},
        {"id": "lightstick", "name": "Lightstick"},
        {"id": "fansign", "name": "Fansign"},
    ],
}

# Collections are thematic groupings users can tag items with
CATEGORY_COLLECTIONS: dict[str, list[str]] = {
    "pokemon": ["Modern Grails", "Vintage Holos", "Japanese Promos", "Sealed Collection"],
    "mtg": ["Reserved List", "Commander Staples", "Dual Lands", "Power Nine"],
    "yugioh": ["Starlight Rares", "First Editions", "Ghost Rares"],
    "lorcana": ["Enchanted Cards", "Foils", "Sealed Collection"],
    "funko": ["Vaulted Classics", "Con Exclusives", "Chase Collection"],
    "lego": ["Ultimate Collector Series", "Retired Sets", "Minifig Collection"],
    "diecast": ["Premium Lines", "Treasure Hunts", "RLC Collection"],
    "sportscards": ["Rookie Cards", "Graded 10s", "Vintage"],
    "anime_figures": ["Nendoroid Shelf", "Scale Collection", "Prize Figures"],
    "warhammer": ["Painted Army", "New on Sprue", "Forge World"],
    "retro_games": ["Nintendo Collection", "Sega Collection", "Sealed CIB"],
    "manga": ["Complete Series", "OOP Volumes", "First Prints"],
    "kpop_merch": ["Photocards", "Albums", "Tour Merch"],
    "disney": ["Pin Collection", "Park Exclusives", "Vintage Disney"],
}


# ---------------------------------------------------------------------------
# Build taxonomy payload from taxonomy_mapper.py patterns
# ---------------------------------------------------------------------------

def _load_category_patterns() -> dict[str, list[str]]:
    """Import CATEGORY_PATTERNS from taxonomy_mapper.py."""
    # Add project root to path so we can import from src
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

    try:
        from src.ingest.taxonomy_mapper import CATEGORY_PATTERNS
        return dict(CATEGORY_PATTERNS)
    except ImportError as exc:
        logger.warning("Could not import CATEGORY_PATTERNS: %s", exc)
        logger.info("Returning empty patterns — manual review needed.")
        return {}


def _load_subtype_patterns() -> dict[str, dict[str, str]]:
    """Import SUBTYPE_PATTERNS from taxonomy_mapper.py."""
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

    try:
        from src.ingest.taxonomy_mapper import SUBTYPE_PATTERNS
        return dict(SUBTYPE_PATTERNS)
    except ImportError as exc:
        logger.warning("Could not import SUBTYPE_PATTERNS: %s", exc)
        return {}


def build_categories_json(patterns: dict[str, list[str]]) -> list[dict]:
    """Build the categories JSONB array for the registry."""
    categories = []
    for category_id in patterns:
        display_name = CATEGORY_DISPLAY_NAMES.get(category_id, category_id.replace("_", " ").title())
        subtypes = CATEGORY_SUBTYPES.get(category_id, [])
        collections = CATEGORY_COLLECTIONS.get(category_id, [])

        categories.append({
            "category_id": category_id,
            "display_name": display_name,
            "subtypes": subtypes,
            "collections": collections,
        })

    # Sort by display name for consistent ordering
    categories.sort(key=lambda c: c["display_name"])
    return categories


def build_mapping_rules_json(patterns: dict[str, list[str]]) -> list[dict]:
    """Build the mapping_rules JSONB array from regex patterns."""
    rules = []
    for category_id, pattern_list in patterns.items():
        for pattern in pattern_list:
            rules.append({
                "pattern": pattern,
                "category_id": category_id,
                "confidence": 0.85,
                "rationale": f"Regex pattern match for {category_id}",
            })
    return rules


# ---------------------------------------------------------------------------
# Seed logic
# ---------------------------------------------------------------------------

async def seed_taxonomy(
    version: str = "v1.0",
    dry_run: bool = False,
    notes: str | None = None,
    created_by: str = "system",
) -> dict:
    """Seed the taxonomy_registry with the initial version.

    Args:
        version: Version string to use.
        dry_run: If True, only print what would be inserted.
        notes: Optional notes for the registry row.
        created_by: Who created this version.

    Returns:
        Summary dict with category count, rule count, etc.
    """
    patterns = _load_category_patterns()
    if not patterns:
        logger.error("No category patterns loaded. Cannot seed taxonomy.")
        return {"error": "no_patterns"}

    categories_json = build_categories_json(patterns)
    mapping_rules_json = build_mapping_rules_json(patterns)

    summary = {
        "version": version,
        "category_count": len(categories_json),
        "mapping_rule_count": len(mapping_rules_json),
        "dry_run": dry_run,
    }

    logger.info(
        "Taxonomy v%s: %d categories, %d mapping rules",
        version,
        len(categories_json),
        len(mapping_rules_json),
    )

    if dry_run:
        logger.info("[DRY RUN] Would insert taxonomy version %s", version)
        logger.info("Categories: %s", json.dumps(categories_json, indent=2))
        logger.info("Sample rules (first 5): %s", json.dumps(mapping_rules_json[:5], indent=2))
        return summary

    # Connect to database and insert
    dsn = os.getenv("DB_DSN", "")
    if not dsn:
        logger.error("DB_DSN not set. Cannot seed taxonomy.")
        return {"error": "no_dsn"}

    conn = None
    try:
        conn = await asyncpg.connect(dsn)

        # Check if version already exists
        existing = await conn.fetchval(
            "SELECT version FROM taxonomy_registry WHERE version = $1",
            version,
        )
        if existing:
            logger.warning("Taxonomy version %s already exists. Skipping insert.", version)
            summary["skipped"] = True
            return summary

        await conn.execute(
            """
            INSERT INTO taxonomy_registry (version, categories, mapping_rules, effective_from, created_by, notes)
            VALUES ($1, $2::jsonb, $3::jsonb, $4, $5, $6)
            """,
            version,
            json.dumps(categories_json),
            json.dumps(mapping_rules_json),
            datetime.now(timezone.utc),
            created_by,
            notes or f"Initial taxonomy seed with {len(categories_json)} categories",
        )

        logger.info("Successfully seeded taxonomy version %s", version)
        summary["inserted"] = True
    except Exception:
        logger.exception("Failed to seed taxonomy version %s", version)
        summary["error"] = "db_insert_failed"
    finally:
        if conn is not None:
            await conn.close()

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed the taxonomy_registry table with the initial v1.0 taxonomy.",
    )
    parser.add_argument(
        "--version",
        default="v1.0",
        help="Taxonomy version string (default: v1.0)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be inserted without touching the database",
    )
    parser.add_argument(
        "--notes",
        default=None,
        help="Optional notes for the registry row",
    )
    parser.add_argument(
        "--created-by",
        default="system",
        help="Creator identifier (default: system)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()
    _setup_logging(args.log_level)

    result = asyncio.run(
        seed_taxonomy(
            version=args.version,
            dry_run=args.dry_run,
            notes=args.notes,
            created_by=args.created_by,
        )
    )

    if result.get("error"):
        logger.error("Seed failed: %s", result["error"])
        sys.exit(1)

    logger.info("Seed complete: %s", json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
