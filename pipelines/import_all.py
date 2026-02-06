"""
Master runner for all category import pipelines.

Runs all Tier 1-3 import scripts in sequence.
Use --tier to run only a specific tier, or --category for a single category.

Usage:
    python -m pipelines.import_all                          # all tiers
    python -m pipelines.import_all --tier 1                 # tier 1 only
    python -m pipelines.import_all --category pokemon       # single category
    python -m pipelines.import_all --tier 1 --dry-run       # dry run
    python -m pipelines.import_all --cache-images           # cache images to S3
    python -m pipelines.import_all --list                   # show all categories
"""

from __future__ import annotations

import argparse
import importlib
import sys
import time
from datetime import datetime

# All categories organized by tier
TIER_1 = [
    ("pokemon",      "import_pokemon",      "Pokemon TCG (pokemontcg.io API)"),
    ("mtg",          "import_mtg",          "Magic: The Gathering (Scryfall API)"),
    ("yugioh",       "import_yugioh",       "Yu-Gi-Oh (YGOProDeck API)"),
    ("lorcana",      "import_lorcana",      "Disney Lorcana (community API)"),
    ("lego",         "import_lego",         "LEGO (Rebrickable API)"),
    ("funko",        "import_funko",        "Funko Pop (curated grails)"),
    ("warhammer",    "import_warhammer",    "Warhammer (curated catalog)"),
    ("retro_games",  "import_retro_games",  "Retro Games (curated catalog)"),
    ("manga",        "import_manga",        "Manga (MAL API + curated OOP)"),
    ("sportscards",  "import_sportscards",  "Sports Cards (curated catalog)"),
]

TIER_2 = [
    ("designer_toys",  "import_designer_toys",  "Designer Toys (StockX + curated)"),
    ("anime_figures",  "import_anime_figures",  "Anime Figures (MFC + curated)"),
    ("hot_toys",       "import_hot_toys",       "Hot Toys (Sideshow + curated)"),
    ("gunpla",         "import_gunpla",         "Gunpla (HobbySearch + curated)"),
    ("scale_models",   "import_scale_models",   "Scale Models (Scalemates + curated)"),
    ("keycaps",        "import_keycaps",        "Keycaps (community + curated)"),
    ("bluray_steelbook", "import_bluray",       "Blu-ray Steelbooks (TMDB + curated)"),
    ("anime_bluray",   "import_anime_bluray",   "Anime Blu-ray (curated)"),
    ("nintendo_merch", "import_nintendo_merch", "Nintendo Merch (curated)"),
    ("one_piece",      "import_one_piece",      "One Piece (MFC + curated)"),
    ("retro_pokemon",  "import_retro_pokemon",  "Retro Pokemon Accessories (curated)"),
    ("diecast",        "import_diecast",        "Diecast Vehicles (curated)"),
]

TIER_3 = [
    ("kpop_merch",      "import_kpop",           "K-pop Merch (curated)"),
    ("taylor_swift",    "import_taylor_swift",    "Taylor Swift (curated)"),
    ("pop_fandom",      "import_pop_fandom",      "Pop Fandom (curated)"),
    ("kpop_lightsticks", "import_kpop_lightsticks", "K-pop Lightsticks (curated)"),
    ("anime_soundtrack", "import_anime_soundtrack", "Anime Soundtracks (VGMdb)"),
    ("disney",          "import_disney",          "Disney Collectibles (curated)"),
    ("theme_park",      "import_theme_park",      "Theme Park Exclusives (curated)"),
    ("ghibli",          "import_ghibli",          "Studio Ghibli (curated)"),
    ("bandai_premium",  "import_bandai_premium",  "Bandai Premium (curated)"),
    ("vtuber",          "import_vtuber",          "VTuber Merch (curated)"),
    ("jp_magazine",     "import_jp_magazine",     "JP Magazine Exclusives (curated)"),
    ("jp_event",        "import_jp_event",        "JP Event Exclusives (curated)"),
    ("anime_ost_vinyl", "import_anime_ost_vinyl", "Anime OST Vinyl (VGMdb)"),
    ("loungefly",       "import_loungefly",       "Loungefly (curated)"),
]

ALL_TIERS = {1: TIER_1, 2: TIER_2, 3: TIER_3}


def run_import(module_name: str, category: str, description: str,
               dry_run: bool, cache_images: bool = False) -> bool:
    """Run a single import module."""
    print(f"\n{'='*60}")
    print(f"  {category.upper()} - {description}")
    print(f"{'='*60}")

    try:
        # Save original argv and override
        orig_argv = sys.argv
        argv_extra = []
        if dry_run:
            argv_extra.append("--dry-run")
        if cache_images:
            argv_extra.append("--cache-images")
        sys.argv = ["import_all", *argv_extra]

        mod = importlib.import_module(f"pipelines.{module_name}")
        mod.main()

        sys.argv = orig_argv
        return True

    except ModuleNotFoundError:
        print(f"  SKIP: pipelines/{module_name}.py not yet implemented")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Run all category import pipelines")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3], default=None,
                        help="Run only a specific tier")
    parser.add_argument("--category", type=str, default=None,
                        help="Run only a specific category slug")
    parser.add_argument("--dry-run", action="store_true",
                        help="Write local files only, skip Supabase")
    parser.add_argument("--cache-images", action="store_true",
                        help="Download external images and cache to S3")
    parser.add_argument("--list", action="store_true",
                        help="List all categories and exit")
    args = parser.parse_args()

    if args.list:
        for tier_num, tier in ALL_TIERS.items():
            print(f"\n=== Tier {tier_num} ===")
            for slug, module, desc in tier:
                print(f"  {slug:20s} | {desc}")
        return

    start_time = datetime.now()
    results = {"success": [], "skipped": [], "failed": []}

    # Determine which categories to run
    if args.category:
        # Find the category in any tier
        found = False
        for tier in ALL_TIERS.values():
            for slug, module, desc in tier:
                if slug == args.category:
                    ok = run_import(module, slug, desc, args.dry_run, args.cache_images)
                    (results["success"] if ok else results["failed"]).append(slug)
                    found = True
                    break
        if not found:
            print(f"ERROR: Unknown category '{args.category}'")
            sys.exit(1)
    else:
        tiers_to_run = [args.tier] if args.tier else [1, 2, 3]
        for tier_num in tiers_to_run:
            tier = ALL_TIERS[tier_num]
            print(f"\n{'#'*60}")
            print(f"  TIER {tier_num} ({len(tier)} categories)")
            print(f"{'#'*60}")

            for slug, module, desc in tier:
                ok = run_import(module, slug, desc, args.dry_run, args.cache_images)
                if ok:
                    results["success"].append(slug)
                else:
                    results["skipped"].append(slug)
                time.sleep(0.5)

    elapsed = (datetime.now() - start_time).total_seconds()

    print(f"\n{'='*60}")
    print(f"  IMPORT SUMMARY")
    print(f"{'='*60}")
    print(f"  Completed: {len(results['success'])} categories")
    print(f"  Skipped:   {len(results['skipped'])} categories (not yet implemented)")
    print(f"  Failed:    {len(results['failed'])} categories")
    print(f"  Time:      {elapsed:.0f}s")

    if results["success"]:
        print(f"\n  Completed: {', '.join(results['success'])}")
    if results["skipped"]:
        print(f"  Skipped:   {', '.join(results['skipped'])}")
    if results["failed"]:
        print(f"  Failed:    {', '.join(results['failed'])}")


if __name__ == "__main__":
    main()
