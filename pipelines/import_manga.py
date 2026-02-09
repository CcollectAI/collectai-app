"""
Import Manga catalog (focus on out-of-print, collectible volumes/sets).

Layer 1 (Catalog):  Popular & OOP manga series → category_items
Layer 2 (Prices):   Market estimates for OOP volumes → train.jsonl

Sources:
- MyAnimeList API (series metadata)
- Curated OOP manga price data
- Can be augmented with MangaDex, AniList later

Usage:
    python -m pipelines.import_manga [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines.import_common import (
    CatalogItem, PriceObservation, SupabaseIngest,
    write_training_jsonl, write_catalog_sql, fetch_json,
    log_progress, slugify,
    rarity_score as shared_rarity_score,
    RARITY_SCORE_MAP,
    logger,
    close_http_client,
)

CATEGORY = "manga"
JIKAN_API = "https://api.jikan.moe/v4"  # Unofficial MAL API, no key needed


def fetch_top_manga(limit: int = 200) -> list[dict]:
    """Fetch top manga from Jikan (MAL) API."""
    all_manga = []
    page = 1
    per_page = 25  # Jikan max

    while len(all_manga) < limit:
        try:
            data = fetch_json(f"{JIKAN_API}/top/manga", params={
                "page": page,
                "limit": per_page,
                "filter": "bypopularity",
            })
            results = data.get("data", [])
            if not results:
                break
            all_manga.extend(results)
            page += 1
            time.sleep(1.0)  # Jikan rate limit: 1 req/sec
        except Exception as e:
            logger.info(f"  Jikan API error on page {page}: {e}")
            break

    log_progress(CATEGORY, "MAL manga fetched", len(all_manga))
    return all_manga[:limit]


def get_curated_oop_manga() -> list[dict]:
    """Curated out-of-print and collectible manga with price data."""

    # (title, publisher, volumes, status, avg_vol_price, complete_set_price, rarity)
    oop_manga = [
        # Highly sought after OOP manga
        ("Blade of the Immortal (Singles)", "Dark Horse", 31, "OOP", 25, 800, "High"),
        ("Berserk (Deluxe)", "Dark Horse", 14, "In Print", 50, 700, "Standard"),
        ("Berserk (Singles)", "Dark Horse", 42, "OOP", 15, 600, "Mid"),
        ("Vagabond (Singles)", "VIZ", 37, "Partial OOP", 12, 450, "Mid"),
        ("Vagabond VizBig", "VIZ", 12, "In Print", 20, 240, "Standard"),
        ("Slam Dunk", "VIZ", 31, "OOP", 20, 600, "High"),
        ("Gantz", "Dark Horse", 37, "OOP", 30, 1100, "High"),
        ("Pluto", "VIZ", 8, "In Print", 15, 120, "Standard"),
        ("20th Century Boys (Perfect)", "VIZ", 12, "In Print", 20, 240, "Standard"),
        ("Monster (Perfect)", "VIZ", 9, "In Print", 18, 160, "Standard"),
        ("Battle Royale", "Tokyopop", 15, "OOP", 40, 600, "High"),
        ("GTO (Great Teacher Onizuka)", "Tokyopop", 25, "OOP", 15, 375, "Mid"),
        ("Eyeshield 21", "VIZ", 37, "OOP", 12, 450, "Mid"),
        ("D.Gray-man", "VIZ", 27, "Partial OOP", 10, 270, "Mid"),
        ("Uzumaki (Deluxe)", "VIZ", 1, "In Print", 28, 28, "Standard"),
        ("Tomie (Deluxe)", "VIZ", 1, "In Print", 23, 23, "Standard"),
        ("Nana", "VIZ", 21, "OOP", 20, 420, "High"),
        ("Paradise Kiss", "Tokyopop/Vertical", 5, "OOP", 25, 125, "Mid"),
        ("Claymore", "VIZ", 27, "In Print", 10, 270, "Standard"),
        ("Trigun Maximum", "Dark Horse", 14, "OOP", 20, 280, "Mid"),
        ("Lone Wolf and Cub", "Dark Horse", 28, "In Print", 15, 420, "Standard"),
        ("Akira (Box Set)", "Kodansha", 6, "In Print", 30, 180, "Standard"),
        ("Dragon Ball (Box Set)", "VIZ", 16, "In Print", 10, 160, "Standard"),
        ("Naruto (Box Set 1-3)", "VIZ", 72, "In Print", 7, 500, "Standard"),
        ("One Piece (Box Set)", "VIZ", 23, "In Print", 8, 184, "Standard"),
        ("Fullmetal Alchemist (Box Set)", "VIZ", 27, "In Print", 8, 216, "Standard"),
        ("Death Note (Box Set)", "VIZ", 13, "In Print", 10, 130, "Standard"),
        ("Oyasumi Punpun", "VIZ", 7, "In Print", 20, 140, "Standard"),
        ("Dorohedoro", "VIZ", 23, "In Print", 13, 300, "Standard"),
        ("Chainsaw Man", "VIZ", 17, "In Print", 10, 170, "Standard"),
        ("Jujutsu Kaisen", "VIZ", 25, "In Print", 10, 250, "Standard"),
        ("Spy x Family", "VIZ", 13, "In Print", 10, 130, "Standard"),
        ("Vinland Saga (Hardcover)", "Kodansha", 13, "In Print", 23, 300, "Standard"),
        ("Real", "VIZ", 15, "Partial OOP", 15, 225, "Mid"),
        ("Mushishi", "Del Rey/Kodansha", 10, "OOP", 30, 300, "High"),
        ("Eden: It's an Endless World!", "Dark Horse", 14, "OOP", 35, 490, "High"),
        ("Biomega", "VIZ", 6, "OOP", 20, 120, "Mid"),
        ("Flowers of Evil", "Vertical", 11, "OOP", 18, 200, "Mid"),
        ("Sundome", "Yen Press", 8, "OOP", 25, 200, "Mid"),
        ("I''s", "VIZ", 15, "OOP", 15, 225, "Mid"),
    ]

    items = []
    for title, publisher, vols, status, vol_price, set_price, rarity in oop_manga:
        items.append({
            "title": title,
            "publisher": publisher,
            "volumes": vols,
            "status": status,
            "avg_vol_price": vol_price,
            "complete_set_price": set_price,
            "rarity": rarity,
        })
    return items


def mal_to_catalog_item(manga: dict) -> CatalogItem:
    title = manga.get("title", "")
    title_en = manga.get("title_english", "") or title
    mal_id = manga.get("mal_id", 0)
    volumes = manga.get("volumes") or 0
    status = manga.get("status", "")
    score = manga.get("score") or 0
    image = manga.get("images", {}).get("jpg", {}).get("small_image_url", "")

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"mal-{mal_id}-{title_en}"),
        title=title_en,
        set_code=f"mal-{mal_id}",
        brand=", ".join(s.get("name", "") for s in manga.get("serializations", [])) or "Unknown",
        rarity="Popular" if score > 8 else "Standard",
        notes=f"{volumes} vols | {status} | MAL {score}",
        image_url=image,
        attributes_json={
            "mal_id": mal_id,
            "volumes": volumes,
            "status": status,
            "score": score,
            "genres": [g.get("name", "") for g in manga.get("genres", [])],
        },
    )


def oop_to_catalog_item(item: dict) -> CatalogItem:
    title = item["title"]
    publisher = item["publisher"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{publisher}-{title}"),
        title=title,
        set_code=publisher.lower().replace(" ", "-"),
        brand=publisher,
        rarity=item["rarity"],
        notes=f"{publisher} | {item['volumes']} vols | {item['status']}",
        attributes_json={
            "publisher": publisher,
            "volumes": item["volumes"],
            "status": item["status"],
        },
    )


def oop_to_price_observations(item: dict) -> list[PriceObservation]:
    rarity_score = shared_rarity_score(item["rarity"])
    is_oop = item["status"] in ("OOP", "Partial OOP")

    observations = []
    # Per-volume price
    observations.append(PriceObservation(
        features={
            "condition_score": 0.8,
            "rarity_score": rarity_score,
            "edition_score": 0.7 if is_oop else 0.4,
            "completeness": 0.3,  # single volume
        },
        price=float(item["avg_vol_price"]),
    ))
    # Complete set price
    observations.append(PriceObservation(
        features={
            "condition_score": 0.8,
            "rarity_score": rarity_score + 0.1,  # complete sets are rarer
            "edition_score": 0.7 if is_oop else 0.4,
            "completeness": 1.0,  # full set
        },
        price=float(item["complete_set_price"]),
    ))
    return observations


def main():
    parser = argparse.ArgumentParser(description="Import manga catalog + prices")
    parser.add_argument("--skip-mal", action="store_true",
                        help="Skip MAL API, use curated data only")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Manga Import ===")

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    all_items: list[CatalogItem] = []
    all_observations: list[PriceObservation] = []

    # 1. Fetch top manga from MAL for catalog breadth
    if not args.skip_mal:
        try:
            mal_manga = fetch_top_manga(limit=200)
            all_items.extend([mal_to_catalog_item(m) for m in mal_manga])
        except Exception as e:
            logger.info(f"  MAL fetch failed: {e}, using curated only")

    # 2. Add curated OOP manga with price data
    oop_manga = get_curated_oop_manga()
    all_items.extend([oop_to_catalog_item(m) for m in oop_manga])
    for m in oop_manga:
        all_observations.extend(oop_to_price_observations(m))

    # Deduplicate by item_key
    seen = set()
    deduped = []
    for item in all_items:
        if item.item_key not in seen:
            seen.add(item.item_key)
            deduped.append(item)
    all_items = deduped

    write_catalog_sql(CATEGORY, all_items)
    log_progress(CATEGORY, "catalog SQL written", len(all_items))

    if all_observations:
        write_training_jsonl(CATEGORY, all_observations)
        log_progress(CATEGORY, "training JSONL written", len(all_observations))

    if ingest.enabled:
        inserted = ingest.upsert_catalog(all_items)
        log_progress(CATEGORY, "catalog upserted", inserted)

    ingest.close()

    logger.info(f"\n=== Manga Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
