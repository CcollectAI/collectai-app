"""
Master runner for all category import pipelines.

Runs all Tier 1-3 import scripts in sequence (or parallel).
Use --tier to run only a specific tier, or --category for a single category.

Usage:
    python -m pipelines.import_all                          # all tiers
    python -m pipelines.import_all --tier 1                 # tier 1 only
    python -m pipelines.import_all --category pokemon       # single category
    python -m pipelines.import_all --tier 1 --dry-run       # dry run
    python -m pipelines.import_all --cache-images           # cache images to S3
    python -m pipelines.import_all --list                   # show all categories
    python -m pipelines.import_all --parallel 4             # run 4 at a time
    python -m pipelines.import_all --resume                 # resume interrupted run
"""

from __future__ import annotations

import argparse
import importlib
import json
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from pipelines.import_common import (
    close_http_client,
    logger,
    setup_logging,
    IngestStats,
)

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
    ("oop_board_games", "import_oop_board_games", "OOP Board Games (curated)"),
    ("city_pop_vinyl",  "import_city_pop_vinyl",  "City Pop Vinyl (curated)"),
    ("fragrances", "import_niche_perfumery", "Fragrances (curated)"),
]

TIER_4 = [
    ("action_figures",    "import_action_figures",    "Action Figures (curated)"),
    ("blind_box",         "import_blind_box",         "Blind Box / Mystery (curated)"),
    ("comic_books",       "import_comic_books",       "Comic Books (curated)"),
    ("digimon",           "import_digimon",           "Digimon TCG (curated)"),
    ("marvel_legends",    "import_marvel_legends",    "Marvel Legends (curated)"),
    ("one_piece_tcg",     "import_one_piece_tcg",     "One Piece TCG (curated)"),
    ("pens",              "import_pens",              "Fountain Pens (curated)"),
    ("plush_collectibles","import_plush_collectibles","Plush Collectibles (curated)"),
    ("retro_handhelds",   "import_retro_handhelds",   "Retro Handhelds (curated)"),
    ("sneakers",          "import_sneakers",          "Sneakers (curated)"),
    ("vintage_cameras",   "import_vintage_cameras",   "Vintage Cameras (curated)"),
    ("vintage_toys",      "import_vintage_toys",      "Vintage Toys (curated)"),
    ("vinyl_records",     "import_vinyl",             "Vinyl Records (curated)"),
    ("watches",           "import_watches",           "Watches (curated)"),
    ("whiskey",           "import_whiskey",           "Whiskey (curated)"),
]

ALL_TIERS = {1: TIER_1, 2: TIER_2, 3: TIER_3, 4: TIER_4}


# ---------------------------------------------------------------------------
# Progress Persistence (SQLite checkpoint) (#10)
# ---------------------------------------------------------------------------

CHECKPOINT_DB = Path(__file__).resolve().parent.parent / "data" / ".import_checkpoint.db"

# Thread-safety lock for SQLite checkpoint writes when --parallel > 1
_checkpoint_lock = threading.Lock()


def _init_checkpoint_db() -> sqlite3.Connection:
    CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CHECKPOINT_DB), check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS checkpoints (
            run_id TEXT NOT NULL,
            category TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            started_at TEXT,
            finished_at TEXT,
            error_msg TEXT,
            PRIMARY KEY (run_id, category)
        )
    """)
    conn.commit()
    return conn


def _mark_checkpoint(conn: sqlite3.Connection, run_id: str, category: str,
                     status: str, error_msg: str = "") -> None:
    now = datetime.now().isoformat()
    with _checkpoint_lock:
        if status == "running":
            conn.execute(
                "INSERT OR REPLACE INTO checkpoints (run_id, category, status, started_at) VALUES (?, ?, ?, ?)",
                (run_id, category, status, now),
            )
        else:
            conn.execute(
                "UPDATE checkpoints SET status = ?, finished_at = ?, error_msg = ? WHERE run_id = ? AND category = ?",
                (status, now, error_msg, run_id, category),
            )
        conn.commit()


def _get_completed_categories(conn: sqlite3.Connection, run_id: str) -> set[str]:
    with _checkpoint_lock:
        rows = conn.execute(
            "SELECT category FROM checkpoints WHERE run_id = ? AND status = 'success'",
            (run_id,),
        ).fetchall()
        return {r[0] for r in rows}


def _get_latest_run_id(conn: sqlite3.Connection) -> str | None:
    with _checkpoint_lock:
        row = conn.execute(
            "SELECT DISTINCT run_id FROM checkpoints ORDER BY run_id DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None


# ---------------------------------------------------------------------------
# Import runner
# ---------------------------------------------------------------------------

def run_import(module_name: str, category: str, description: str,
               dry_run: bool, cache_images: bool = False) -> tuple[bool, str]:
    """Run a single import module. Returns (success, error_message)."""
    logger.info(f"{'='*60}")
    logger.info(f"  {category.upper()} - {description}")
    logger.info(f"{'='*60}")

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
        return True, ""

    except ModuleNotFoundError:
        msg = f"pipelines/{module_name}.py not yet implemented"
        logger.warning(f"SKIP: {msg}")
        return False, msg
    except Exception as e:
        msg = str(e)
        logger.error(f"FAILED {category}: {msg}")
        return False, msg


def main():
    parser = argparse.ArgumentParser(description="Run all category import pipelines")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3, 4], default=None,
                        help="Run only a specific tier")
    parser.add_argument("--category", type=str, default=None,
                        help="Run only a specific category slug")
    parser.add_argument("--dry-run", action="store_true",
                        help="Write local files only, skip Supabase")
    parser.add_argument("--cache-images", action="store_true",
                        help="Download external images and cache to S3")
    parser.add_argument("--list", action="store_true",
                        help="List all categories and exit")
    parser.add_argument("--parallel", type=int, default=1, metavar="N",
                        help="Run N categories in parallel (default: 1 = sequential)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume the most recent interrupted run")
    args = parser.parse_args()

    if args.list:
        for tier_num, tier in ALL_TIERS.items():
            logger.info(f"\n=== Tier {tier_num} ===")
            for slug, module, desc in tier:
                logger.info(f"  {slug:20s} | {desc}")
        return

    # Initialize checkpoint DB
    checkpoint_conn = _init_checkpoint_db()
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    completed_categories: set[str] = set()

    if args.resume:
        prev_run_id = _get_latest_run_id(checkpoint_conn)
        if prev_run_id:
            run_id = prev_run_id
            completed_categories = _get_completed_categories(checkpoint_conn, run_id)
            logger.info(f"Resuming run {run_id} — {len(completed_categories)} categories already done")
        else:
            logger.info("No previous run found, starting fresh")

    start_time = datetime.now()
    results = {"success": [], "skipped": [], "failed": []}
    global_stats = IngestStats()

    def _run_one(slug: str, module: str, desc: str) -> tuple[str, bool, str]:
        """Wrapper for parallel execution."""
        if slug in completed_categories:
            logger.info(f"SKIP (already completed): {slug}")
            return slug, True, ""
        _mark_checkpoint(checkpoint_conn, run_id, slug, "running")
        ok, err = run_import(module, slug, desc, args.dry_run, args.cache_images)
        status = "success" if ok else ("skipped" if "not yet implemented" in err else "failed")
        _mark_checkpoint(checkpoint_conn, run_id, slug, status, err)
        return slug, ok, err

    # Determine which categories to run
    if args.category:
        found = False
        for tier in ALL_TIERS.values():
            for slug, module, desc in tier:
                if slug == args.category:
                    slug, ok, err = _run_one(slug, module, desc)
                    if ok:
                        results["success"].append(slug)
                    else:
                        results["failed"].append(slug)
                    found = True
                    break
        if not found:
            logger.error(f"Unknown category '{args.category}'")
            sys.exit(1)
    else:
        tiers_to_run = [args.tier] if args.tier else [1, 2, 3, 4]

        for tier_num in tiers_to_run:
            tier = ALL_TIERS[tier_num]
            logger.info(f"\n{'#'*60}")
            logger.info(f"  TIER {tier_num} ({len(tier)} categories)")
            logger.info(f"{'#'*60}")

            if args.parallel > 1:
                # Parallel execution within tier (#11)
                with ThreadPoolExecutor(max_workers=args.parallel) as pool:
                    futures = {
                        pool.submit(_run_one, slug, module, desc): slug
                        for slug, module, desc in tier
                    }
                    for future in as_completed(futures):
                        slug, ok, err = future.result()
                        if ok:
                            results["success"].append(slug)
                        elif "not yet implemented" in err:
                            results["skipped"].append(slug)
                        else:
                            results["failed"].append(slug)
            else:
                # Sequential (default)
                for slug, module, desc in tier:
                    slug, ok, err = _run_one(slug, module, desc)
                    if ok:
                        results["success"].append(slug)
                    elif "not yet implemented" in err:
                        results["skipped"].append(slug)
                    else:
                        results["failed"].append(slug)
                    time.sleep(0.5)

    elapsed = (datetime.now() - start_time).total_seconds()

    # Close shared HTTP client
    close_http_client()

    # Auto-rebuild vocab + brand registry + schema if any imports succeeded
    if results.get("success"):
        try:
            logger.info("Rebuilding attribute vocabulary...")
            from pipelines.build_attribute_vocab import main as build_vocab
            build_vocab()
        except Exception as e:
            logger.warning(f"Failed to rebuild vocab: {e}")

        try:
            logger.info("Rebuilding brand registry...")
            from pipelines.build_brand_registry import main as build_brands
            build_brands()
        except Exception as e:
            logger.warning(f"Failed to rebuild brand registry: {e}")

        try:
            logger.info("Rebuilding attribute schema...")
            from pipelines.train_attribute_completeness import main as build_schema
            build_schema()
        except Exception as e:
            logger.warning(f"Failed to rebuild schema: {e}")

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"  IMPORT SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"  Run ID:    {run_id}")
    logger.info(f"  Completed: {len(results['success'])} categories")
    logger.info(f"  Skipped:   {len(results['skipped'])} categories (not yet implemented)")
    logger.info(f"  Failed:    {len(results['failed'])} categories")
    logger.info(f"  Time:      {elapsed:.0f}s")

    if results["success"]:
        logger.info(f"  Completed: {', '.join(results['success'])}")
    if results["skipped"]:
        logger.info(f"  Skipped:   {', '.join(results['skipped'])}")
    if results["failed"]:
        logger.info(f"  Failed:    {', '.join(results['failed'])}")

    # Non-zero exit code on failures (#4)
    if results["failed"]:
        logger.error(f"{len(results['failed'])} categories failed — exiting with code 1")
        sys.exit(1)

    checkpoint_conn.close()


if __name__ == "__main__":
    main()
