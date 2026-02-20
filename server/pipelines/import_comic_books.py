"""
Import Comic Books & Graphic Novels catalog.

Layer 1 (Catalog):  Key issues, collected editions, graded comics → category_items
Layer 2 (Prices):   Secondary market estimates → train.jsonl

Covers:
- Marvel key issues (Amazing Fantasy #15, ASM #129, #300, X-Men #1, etc.)
- DC key issues (Action Comics #1, Detective Comics #27, Batman #1, etc.)
- Image/Indie (Saga, Walking Dead, Spawn, etc.)
- Variant covers (1:25, 1:50, virgin, foil variants)
- Graded comics (CGC 9.8, 9.6, etc.)
- Modern keys (first appearances, death issues)

Usage:
    python -m pipelines.import_comic_books [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines.import_common import (
    CatalogItem, PriceObservation, SupabaseIngest,
    write_training_jsonl, write_catalog_sql,
    log_progress, slugify,
    rarity_score as shared_rarity_score,
    logger,
    close_http_client,
)

CATEGORY = "comic_books"

# ---------------------------------------------------------------------------
# Issue-type rarity scores (comic-specific)
# ---------------------------------------------------------------------------

ISSUE_TYPE_SCORES: dict[str, float] = {
    "Golden Age Key": 0.98,
    "Silver Age Key": 0.95,
    "Bronze Age Key": 0.85,
    "Modern Key": 0.75,
    "Variant Cover": 0.70,
    "CGC 9.8": 0.90,
    "CGC 9.6": 0.85,
    "First Print": 0.60,
    "TPB": 0.30,
    "Omnibus": 0.55,
    "Absolute Edition": 0.65,
    "Signed": 0.80,
    "Convention Exclusive": 0.75,
}


def _rarity_tier(price_eur: float) -> str:
    """Determine rarity tier from price.

    - grail:    >= 500 EUR
    - high:     100-499 EUR
    - mid:      20-99 EUR
    - standard: < 20 EUR
    """
    if price_eur >= 500:
        return "grail"
    if price_eur >= 100:
        return "high"
    if price_eur >= 20:
        return "mid"
    return "standard"


def _issue_type_score(issue_type: str) -> float:
    """Look up issue-type rarity score, fallback 0.50."""
    return ISSUE_TYPE_SCORES.get(issue_type, 0.50)


def get_curated_catalog() -> list[dict]:
    """Curated comic books catalog -- ~120 items across 10 subcategories.

    Tuple format per entry:
        (publisher, series, name, issue_type, rarity_tier, price_eur)

    Prices are approximate secondary-market EUR values (2026) for
    mid-grade raw copies unless otherwise noted (CGC entries are slabbed).
    """

    # (publisher, series, name, issue_type, rarity_tier, price_eur)
    comics: list[tuple[str, str, str, str, str, float]] = [
        # ── 1. Marvel Golden/Silver Age Keys (10) ─────────────────────────
        ("Marvel", "Amazing Fantasy", "Amazing Fantasy #15 (1st Spider-Man)", "Golden Age Key", "grail", 300000.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #1 (1963)", "Silver Age Key", "grail", 80000.0),
        ("Marvel", "X-Men", "X-Men #1 (1963, 1st X-Men)", "Silver Age Key", "grail", 35000.0),
        ("Marvel", "Incredible Hulk", "Incredible Hulk #1 (1962)", "Silver Age Key", "grail", 120000.0),
        ("Marvel", "Fantastic Four", "Fantastic Four #1 (1961)", "Silver Age Key", "grail", 150000.0),
        ("Marvel", "Avengers", "Avengers #1 (1963)", "Silver Age Key", "grail", 40000.0),
        ("Marvel", "Iron Man", "Iron Man #55 (1st Thanos)", "Silver Age Key", "grail", 3500.0),
        ("Marvel", "Giant-Size X-Men", "Giant-Size X-Men #1 (1975, New X-Men)", "Bronze Age Key", "grail", 6000.0),
        ("Marvel", "Tales of Suspense", "Tales of Suspense #39 (1st Iron Man)", "Silver Age Key", "grail", 50000.0),
        ("Marvel", "Journey into Mystery", "Journey into Mystery #83 (1st Thor)", "Silver Age Key", "grail", 30000.0),

        # ── 2. DC Golden/Silver Age Keys (10) ─────────────────────────────
        ("DC", "Action Comics", "Action Comics #1 (1st Superman)", "Golden Age Key", "grail", 999000.0),
        ("DC", "Detective Comics", "Detective Comics #27 (1st Batman)", "Golden Age Key", "grail", 800000.0),
        ("DC", "Batman", "Batman #1 (1940, 1st Joker & Catwoman)", "Golden Age Key", "grail", 500000.0),
        ("DC", "Flash", "Flash #123 (Flash of Two Worlds)", "Silver Age Key", "grail", 8000.0),
        ("DC", "Showcase", "Showcase #4 (1st Silver Age Flash)", "Silver Age Key", "grail", 50000.0),
        ("DC", "Green Lantern", "Green Lantern #76 (Green Lantern/Green Arrow)", "Silver Age Key", "grail", 3500.0),
        ("DC", "Superman", "Superman #1 (1939)", "Golden Age Key", "grail", 450000.0),
        ("DC", "Wonder Woman", "Wonder Woman #1 (1942)", "Golden Age Key", "grail", 100000.0),
        ("DC", "Brave and the Bold", "Brave and the Bold #28 (1st Justice League)", "Silver Age Key", "grail", 25000.0),
        ("DC", "All Star Comics", "All Star Comics #8 (1st Wonder Woman)", "Golden Age Key", "grail", 120000.0),

        # ── 3. Marvel Modern Keys (15) ────────────────────────────────────
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #129 (1st Punisher)", "Bronze Age Key", "grail", 4500.0),
        ("Marvel", "New Mutants", "New Mutants #98 (1st Deadpool)", "Modern Key", "grail", 1200.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #300 (1st Venom)", "Modern Key", "grail", 2500.0),
        ("Marvel", "Incredible Hulk", "Incredible Hulk #181 (1st Wolverine full)", "Bronze Age Key", "grail", 8000.0),
        ("Marvel", "Marvel Spotlight", "Marvel Spotlight #5 (1st Ghost Rider)", "Bronze Age Key", "grail", 3000.0),
        ("Marvel", "Ms. Marvel", "Ms. Marvel #1 (2014, 1st Kamala Khan)", "Modern Key", "high", 250.0),
        ("Marvel", "Ultimate Comics", "Ultimate Fallout #4 (1st Miles Morales)", "Modern Key", "high", 400.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #252 (1st Black Suit)", "Modern Key", "high", 350.0),
        ("Marvel", "Incredible Hulk", "Incredible Hulk #180 (1st Wolverine cameo)", "Bronze Age Key", "grail", 2000.0),
        ("Marvel", "Marvel Super Heroes", "Marvel Super Heroes Secret Wars #8 (Symbiote origin)", "Modern Key", "high", 300.0),
        ("Marvel", "Edge of Spider-Verse", "Edge of Spider-Verse #2 (1st Spider-Gwen)", "Modern Key", "high", 350.0),
        ("Marvel", "Star Wars", "Star Wars #1 (1977, Marvel adaptation)", "Bronze Age Key", "high", 400.0),
        ("Marvel", "Eternals", "Eternals #1 (1976, 1st Eternals)", "Bronze Age Key", "high", 200.0),
        ("Marvel", "Werewolf by Night", "Werewolf by Night #32 (1st Moon Knight)", "Bronze Age Key", "grail", 3500.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #361 (1st Carnage)", "Modern Key", "high", 300.0),

        # ── 4. DC Modern Keys (10) ────────────────────────────────────────
        ("DC", "Batman", "Batman #423 (Todd McFarlane cover)", "Modern Key", "high", 250.0),
        ("DC", "Batman", "Batman #608 (Hush, Jim Lee)", "Modern Key", "high", 150.0),
        ("DC", "Batman", "New 52 Batman #1 (2011, Snyder/Capullo)", "Modern Key", "high", 200.0),
        ("DC", "Harley Quinn", "Batman Adventures #12 (1st Harley Quinn)", "Modern Key", "grail", 2000.0),
        ("DC", "Batman", "Batman #232 (1st Ra's al Ghul)", "Bronze Age Key", "grail", 2500.0),
        ("DC", "Batman", "Batman #251 (Classic Joker, Neal Adams)", "Bronze Age Key", "grail", 1500.0),
        ("DC", "Batman", "Batman: The Killing Joke (1st print, 1988)", "Modern Key", "high", 350.0),
        ("DC", "Saga of the Swamp Thing", "Saga of the Swamp Thing #37 (1st John Constantine)", "Modern Key", "high", 400.0),
        ("DC", "Crisis on Infinite Earths", "Crisis on Infinite Earths #7 (Death of Supergirl)", "Modern Key", "high", 120.0),
        ("DC", "Batman", "Batman #181 (1st Poison Ivy)", "Silver Age Key", "grail", 5000.0),

        # ── 5. Image/Indie Keys (10) ──────────────────────────────────────
        ("Image", "Spawn", "Spawn #1 (1992, Todd McFarlane)", "Modern Key", "high", 150.0),
        ("Image", "Walking Dead", "Walking Dead #1 (2003, Kirkman)", "Modern Key", "grail", 3000.0),
        ("Image", "Saga", "Saga #1 (2012, BKV/Staples)", "Modern Key", "high", 250.0),
        ("Image", "Invincible", "Invincible #1 (2003, Kirkman)", "Modern Key", "grail", 2500.0),
        ("Cartoon Books", "Bone", "Bone #1 (1991, Jeff Smith)", "Modern Key", "high", 400.0),
        ("Mirage", "TMNT", "Teenage Mutant Ninja Turtles #1 (1984, Eastman/Laird)", "Modern Key", "grail", 15000.0),
        ("Dark Horse", "Hellboy", "Hellboy: Seed of Destruction #1 (1994)", "Modern Key", "high", 200.0),
        ("Image", "The Maxx", "The Maxx #1 (1993, Sam Kieth)", "Modern Key", "mid", 50.0),
        ("Valiant", "Harbinger", "Harbinger #1 (1992, with coupon)", "Modern Key", "high", 150.0),
        ("Image", "Invincible", "Invincible #7 (1st Atom Eve)", "Modern Key", "high", 300.0),

        # ── 6. Variant Covers (15) ────────────────────────────────────────
        ("Marvel", "Amazing Spider-Man", "ASM #1 (2022) 1:50 Hughes Virgin Variant", "Variant Cover", "high", 250.0),
        ("DC", "Batman", "Batman #89 (1st Punchline, 2nd print)", "Variant Cover", "high", 100.0),
        ("Marvel", "Venom", "Venom #3 (2018) 1:25 Stegman Variant (1st Knull)", "Variant Cover", "high", 200.0),
        ("Marvel", "X-Men", "X-Men #1 (2019) 1:100 Virgin Variant", "Variant Cover", "high", 350.0),
        ("DC", "Joker", "Joker 80th Anniversary #1 Artgerm Foil Variant", "Variant Cover", "mid", 80.0),
        ("Marvel", "Immortal Hulk", "Immortal Hulk #1 (2018) 1:25 Alex Ross Variant", "Variant Cover", "high", 150.0),
        ("Image", "Something is Killing the Children", "SIKTC #1 (2019) 1:25 Frison Variant", "Variant Cover", "high", 400.0),
        ("Marvel", "Thor", "Thor #6 (2020) 1:50 Black Winter Virgin", "Variant Cover", "high", 180.0),
        ("DC", "Batman", "Batman #100 (2020) 1:25 Jorge Jimenez Variant", "Variant Cover", "mid", 60.0),
        ("Marvel", "Miles Morales", "Miles Morales Spider-Man #1 (2023) 1:100 Virgin", "Variant Cover", "high", 300.0),
        ("DC", "Wonder Woman", "Wonder Woman #1 (2023) 1:50 Stanley Artgerm Lau Virgin", "Variant Cover", "high", 200.0),
        ("Marvel", "Wolverine", "Wolverine #1 (2020) 1:25 Hidden Gem Variant", "Variant Cover", "mid", 75.0),
        ("Image", "Spawn", "Spawn #350 (2024) Gold Foil Variant", "Variant Cover", "mid", 90.0),
        ("Marvel", "Fantastic Four", "Fantastic Four #1 (2018) 1:50 Ross Virgin Variant", "Variant Cover", "high", 180.0),
        ("DC", "Superman", "Superman #1 (2023) 1:25 Jim Lee Foil Variant", "Variant Cover", "mid", 65.0),

        # ── 7. CGC Graded Examples (15) ───────────────────────────────────
        ("Marvel", "Amazing Spider-Man", "ASM #300 (1st Venom) CGC 9.8", "CGC 9.8", "grail", 5500.0),
        ("DC", "Batman", "Batman #423 (McFarlane) CGC 9.8", "CGC 9.8", "grail", 1200.0),
        ("Image", "Spawn", "Spawn #1 CGC 9.8", "CGC 9.8", "high", 350.0),
        ("Marvel", "New Mutants", "New Mutants #98 (1st Deadpool) CGC 9.8", "CGC 9.8", "grail", 3500.0),
        ("Marvel", "Incredible Hulk", "Incredible Hulk #181 (1st Wolverine) CGC 9.6", "CGC 9.6", "grail", 15000.0),
        ("DC", "Batman", "Batman Adventures #12 (1st Harley) CGC 9.8", "CGC 9.8", "grail", 5000.0),
        ("Marvel", "Amazing Spider-Man", "ASM #129 (1st Punisher) CGC 9.6", "CGC 9.6", "grail", 8000.0),
        ("Image", "Walking Dead", "Walking Dead #1 (2003) CGC 9.8", "CGC 9.8", "grail", 8000.0),
        ("Image", "Invincible", "Invincible #1 CGC 9.8", "CGC 9.8", "grail", 6000.0),
        ("Marvel", "Edge of Spider-Verse", "Edge of Spider-Verse #2 (Spider-Gwen) CGC 9.8", "CGC 9.8", "grail", 1500.0),
        ("Marvel", "Ultimate Fallout", "Ultimate Fallout #4 (1st Miles) CGC 9.8", "CGC 9.8", "grail", 2000.0),
        ("DC", "Batman", "New 52 Batman #1 CGC 9.8", "CGC 9.8", "grail", 600.0),
        ("Marvel", "Amazing Spider-Man", "ASM #361 (1st Carnage) CGC 9.8", "CGC 9.8", "grail", 800.0),
        ("Marvel", "X-Men", "Giant-Size X-Men #1 CGC 9.6", "CGC 9.6", "grail", 12000.0),
        ("DC", "Batman", "Batman: Killing Joke 1st Print CGC 9.8", "CGC 9.8", "grail", 1000.0),

        # ── 8. Convention Exclusives (10) ─────────────────────────────────
        ("Marvel", "Amazing Spider-Man", "ASM #1 SDCC 2022 Exclusive J. Scott Campbell", "Convention Exclusive", "high", 120.0),
        ("DC", "Batman", "Batman #125 SDCC 2022 Exclusive Foil", "Convention Exclusive", "high", 100.0),
        ("Image", "Spawn", "Spawn #301 SDCC Exclusive Gold Foil", "Convention Exclusive", "high", 150.0),
        ("Marvel", "Avengers", "Avengers #1 NYCC 2023 Exclusive Peach Momoko", "Convention Exclusive", "mid", 80.0),
        ("DC", "Harley Quinn", "Harley Quinn #1 C2E2 2022 Artgerm Exclusive", "Convention Exclusive", "mid", 70.0),
        ("Marvel", "Venom", "Venom #1 SDCC 2018 Crain Exclusive", "Convention Exclusive", "high", 120.0),
        ("Image", "Saga", "Saga #1 SDCC 10th Anniversary Exclusive", "Convention Exclusive", "high", 200.0),
        ("DC", "Superman", "Superman #1 NYCC 2023 Jim Lee Exclusive", "Convention Exclusive", "mid", 60.0),
        ("Marvel", "X-Men", "X-Men #1 SDCC 2024 Exclusive Virgin Cover", "Convention Exclusive", "high", 130.0),
        ("DC", "Wonder Woman", "Wonder Woman #800 C2E2 2023 Exclusive", "Convention Exclusive", "mid", 50.0),

        # ── 9. Collected Editions (15) ────────────────────────────────────
        ("Marvel", "Uncanny X-Men", "Uncanny X-Men Omnibus Vol. 1 (Claremont)", "Omnibus", "high", 100.0),
        ("DC", "Sandman", "Absolute Sandman Vol. 1 (Gaiman)", "Absolute Edition", "high", 120.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man Omnibus Vol. 1 (Lee/Ditko)", "Omnibus", "high", 110.0),
        ("DC", "Batman", "Absolute Batman: The Long Halloween", "Absolute Edition", "mid", 80.0),
        ("Marvel", "Fantastic Four", "Fantastic Four Omnibus Vol. 1 (Lee/Kirby)", "Omnibus", "high", 100.0),
        ("Image", "Saga", "Saga Compendium One (TPB)", "TPB", "mid", 35.0),
        ("DC", "Watchmen", "Absolute Watchmen (Moore/Gibbons)", "Absolute Edition", "mid", 80.0),
        ("Image", "Invincible", "Invincible Compendium One (TPB)", "TPB", "mid", 40.0),
        ("Marvel", "Avengers", "Avengers by Jonathan Hickman Omnibus Vol. 1", "Omnibus", "mid", 85.0),
        ("DC", "Swamp Thing", "Absolute Swamp Thing by Alan Moore Vol. 1", "Absolute Edition", "mid", 75.0),
        ("Marvel", "Daredevil", "Daredevil by Frank Miller Omnibus Companion", "Omnibus", "high", 100.0),
        ("DC", "Batman", "Batman: Hush Absolute Edition", "Absolute Edition", "mid", 90.0),
        ("Marvel", "X-Men", "X-Men: Age of Apocalypse Omnibus", "Omnibus", "mid", 85.0),
        ("Marvel", "Thor", "Thor by Jason Aaron Omnibus Vol. 1", "Omnibus", "mid", 75.0),
        ("Image", "Walking Dead", "Walking Dead Compendium One (TPB)", "TPB", "mid", 30.0),

        # ── 10. Manga Crossover (Key Magazine Issues) (10) ────────────────
        ("Shueisha", "Weekly Shonen Jump", "Weekly Shonen Jump #1968-1 (1st issue)", "Golden Age Key", "grail", 5000.0),
        ("Kodansha", "Akira", "Akira #1 (1982, original Japanese tankoubon)", "Modern Key", "high", 300.0),
        ("Shueisha", "Weekly Shonen Jump", "WSJ 1997 #34 (One Piece Chapter 1)", "Modern Key", "high", 400.0),
        ("Shueisha", "Weekly Shonen Jump", "WSJ 1999 #43 (Naruto Chapter 1)", "Modern Key", "high", 250.0),
        ("Shueisha", "Weekly Shonen Jump", "WSJ 1984 #51 (Dragon Ball Chapter 1)", "Modern Key", "grail", 800.0),
        ("Kodansha", "Akira", "Akira Epic Comics #1 (1988, English 1st print)", "Modern Key", "high", 200.0),
        ("Shogakukan", "Nausicaa", "Nausicaa of the Valley of the Wind Vol. 1 (1st print JP)", "Modern Key", "high", 150.0),
        ("Dark Horse", "Lone Wolf and Cub", "Lone Wolf and Cub #1 (1987, English 1st print)", "First Print", "mid", 80.0),
        ("Viz", "Dragon Ball", "Dragon Ball Vol. 1 (English 1st print, 2000)", "First Print", "mid", 60.0),
        ("Viz", "Naruto", "Naruto Vol. 1 (English 1st print, 2003)", "First Print", "mid", 50.0),
    ]

    catalog = []
    for publisher, series, name, issue_type, rarity_tier, price_eur in comics:
        catalog.append({
            "publisher": publisher,
            "series": series,
            "name": name,
            "issue_type": issue_type,
            "rarity_tier": rarity_tier,
            "price_eur": price_eur,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    """Convert a curated dict to a CatalogItem row."""
    publisher = item["publisher"]
    series = item["series"]
    name = item["name"]
    issue_type = item["issue_type"]
    rarity_tier = item["rarity_tier"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{publisher}-{name}"),
        title=name,
        set_code=slugify(series),
        brand=publisher,
        rarity=rarity_tier,
        notes=f"{publisher} | {series} | {issue_type}",
        attributes_json={
            "publisher": publisher,
            "series": series,
            "issue_type": issue_type,
            "rarity_tier": rarity_tier,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    """Convert a curated dict to a PriceObservation for training."""
    issue_type = item["issue_type"]
    rarity_tier = item["rarity_tier"]
    price_eur = item["price_eur"]

    rarity_val = _issue_type_score(issue_type)

    # Condition score heuristic: CGC graded → high, raw key → mid, TPB/omni → near mint
    if "CGC 9.8" in issue_type:
        cond = 0.98
    elif "CGC 9.6" in issue_type:
        cond = 0.96
    elif issue_type in ("TPB", "Omnibus", "Absolute Edition"):
        cond = 0.90
    elif "Golden Age" in issue_type:
        cond = 0.50  # mid-grade raw golden age
    elif "Silver Age" in issue_type:
        cond = 0.60  # mid-grade raw silver age
    else:
        cond = 0.75  # decent raw modern/bronze

    # Edition score: first print / key > reprint / collected
    if issue_type in ("Golden Age Key", "Silver Age Key", "Bronze Age Key"):
        edition = 0.95
    elif issue_type in ("Modern Key", "Convention Exclusive", "Signed"):
        edition = 0.80
    elif issue_type in ("Variant Cover", "First Print"):
        edition = 0.70
    elif issue_type in ("Absolute Edition", "Omnibus"):
        edition = 0.55
    else:
        edition = 0.40

    # Clamp to MAX_PRICE_EUR (1,000,000)
    price_eur = min(price_eur, 999000.0)

    return PriceObservation(
        features={
            "condition_score": cond,
            "rarity_score": rarity_val,
            "edition_score": edition,
            "issue_type": issue_type,
            "rarity_tier": rarity_tier,
        },
        price=price_eur,
    )


def main():
    parser = argparse.ArgumentParser(description="Import comic books catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== Comic Books Import ===")

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    catalog = get_curated_catalog()

    all_items = [item_to_catalog_item(i) for i in catalog]
    all_observations = [item_to_price_observation(i) for i in catalog]

    write_catalog_sql(CATEGORY, all_items)
    log_progress(CATEGORY, "catalog SQL written", len(all_items))

    write_training_jsonl(CATEGORY, all_observations)
    log_progress(CATEGORY, "training JSONL written", len(all_observations))

    if ingest.enabled:
        inserted = ingest.upsert_catalog(all_items)
        log_progress(CATEGORY, "catalog upserted", inserted)

    ingest.close()
    close_http_client()

    logger.info(f"\n=== Comic Books Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
