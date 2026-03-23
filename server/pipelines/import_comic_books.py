"""
Import Comic Books & Graphic Novels catalog.

Layer 1 (Catalog):  Key issues, collected editions, graded comics → category_items
Layer 2 (Prices):   Secondary market estimates → train.jsonl

Covers:
- Marvel key issues (Amazing Fantasy #15, ASM #129, #300, X-Men #1, etc.)
- DC key issues (Action Comics #1, Detective Comics #27, Batman #1, etc.)
- Image/Indie (Saga, Walking Dead, Spawn, etc.)
- Variant covers (1:25, 1:50, 1:100, 1:200, 1:500, virgin, foil variants)
- Graded comics (CGC 9.8, 9.6, CGC Signature Series)
- Modern keys (first appearances, death issues)
- Golden Age (DC, Timely/Atlas), Silver Age (Marvel & DC first appearances)
- Bronze Age (key deaths, first appearances), Copper Age (DKR, Watchmen, Crisis)
- Indie publishers (Dark Horse, IDW, BOOM!, Valiant, Vertigo)
- Magazine-size comics (Creepy, Eerie, Vampirella, Heavy Metal)
- Omnibus & Absolute editions

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
    "CGC 9.4": 0.82,
    "CGC 9.2": 0.80,
    "CGC 9.0": 0.78,
    "CGC 8.0": 0.72,
    "CGC 6.0": 0.60,
    "CGC 4.0": 0.50,
    "CGC 2.0": 0.40,
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
    """Curated comic books catalog -- 500+ items across 52 subcategories.

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

        # ── 11. Golden Age Grails (5) ───────────────────────────────────
        ("Timely", "Captain America Comics", "Captain America Comics #1 (1941, 1st Cap)", "Golden Age Key", "grail", 350000.0),
        ("Timely", "Marvel Comics", "Marvel Comics #1 (1939, 1st Human Torch)", "Golden Age Key", "grail", 600000.0),
        ("DC", "More Fun Comics", "More Fun Comics #73 (1st Aquaman & Green Arrow)", "Golden Age Key", "grail", 80000.0),
        ("Fawcett", "Whiz Comics", "Whiz Comics #2 (1st Captain Marvel/Shazam, 1940)", "Golden Age Key", "grail", 200000.0),
        ("DC", "All-American Comics", "All-American Comics #16 (1st Green Lantern, 1940)", "Golden Age Key", "grail", 400000.0),

        # ── 12. More Marvel Keys (6) ────────────────────────────────────
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #194 (1st Black Cat)", "Bronze Age Key", "grail", 1500.0),
        ("Marvel", "Avengers", "Avengers #57 (1st Vision)", "Silver Age Key", "grail", 2500.0),
        ("Marvel", "Captain America", "Captain America #117 (1st Falcon)", "Silver Age Key", "grail", 2000.0),
        ("Marvel", "Daredevil", "Daredevil #1 (1964, 1st Daredevil)", "Silver Age Key", "grail", 15000.0),
        ("Marvel", "Strange Tales", "Strange Tales #110 (1st Doctor Strange)", "Silver Age Key", "grail", 20000.0),
        ("Marvel", "Tales to Astonish", "Tales to Astonish #27 (1st Ant-Man)", "Silver Age Key", "grail", 25000.0),

        # ── 13. More DC Keys (5) ────────────────────────────────────────
        ("DC", "Batman", "Batman #497 (Bane breaks Batman's back)", "Modern Key", "high", 120.0),
        ("DC", "Green Lantern", "Green Lantern #7 (1st Sinestro)", "Silver Age Key", "grail", 4000.0),
        ("DC", "Flash", "Showcase #22 (1st Hal Jordan Green Lantern)", "Silver Age Key", "grail", 20000.0),
        ("DC", "New Teen Titans", "New Teen Titans #2 (1st Deathstroke)", "Modern Key", "grail", 800.0),
        ("DC", "Batman", "Batman #357 (1st Killer Croc)", "Modern Key", "high", 200.0),

        # ── 14. Image / Indie Expansion (5) ─────────────────────────────
        ("Image", "Savage Dragon", "Savage Dragon #1 (1992, Erik Larsen)", "Modern Key", "mid", 40.0),
        ("Dark Horse", "Sin City", "Sin City: The Hard Goodbye #1 (Frank Miller)", "Modern Key", "high", 150.0),
        ("Image", "Chew", "Chew #1 (2009, John Layman)", "Modern Key", "high", 250.0),
        ("Fantagraphics", "Love and Rockets", "Love and Rockets #1 (1982, Hernandez Bros)", "Modern Key", "high", 300.0),
        ("Mirage", "TMNT", "TMNT #2 (1984, 1st Mousers)", "Modern Key", "grail", 1500.0),

        # ── 15. CGC vs CBCS Market (4) ──────────────────────────────────
        ("Marvel", "Amazing Spider-Man", "ASM #300 (1st Venom) CBCS 9.8", "CGC 9.8", "grail", 4500.0),
        ("DC", "Batman", "Batman Adventures #12 (1st Harley) CBCS 9.8", "CGC 9.8", "grail", 4000.0),
        ("Marvel", "Incredible Hulk", "Incredible Hulk #181 (1st Wolverine) CGC 9.8", "CGC 9.8", "grail", 50000.0),
        ("Image", "Saga", "Saga #1 CGC 9.8 Signed by BKV", "Signed", "grail", 800.0),

        # ── 16. Modern First Appearances CGC 9.8 (5) ────────────────────
        ("Marvel", "Venom", "Venom: Lethal Protector #1 (1993) CGC 9.8", "CGC 9.8", "high", 250.0),
        ("Image", "Something is Killing the Children", "SIKTC #1 (2019) CGC 9.8", "CGC 9.8", "grail", 1500.0),
        ("BOOM!", "Something is Killing the Children", "SIKTC #1 Cover A (2019) CGC 9.8", "CGC 9.8", "grail", 1200.0),
        ("Marvel", "Moon Knight", "Moon Knight #1 (2021 Gleason) CGC 9.8", "CGC 9.8", "high", 120.0),
        ("DC", "Joker", "Joker #1 (2021, 1st Daughter of Bane) CGC 9.8", "CGC 9.8", "high", 100.0),

        # ── 17. Variant Covers Expansion (5) ────────────────────────────
        ("Marvel", "Amazing Spider-Man", "ASM #55 (2021) 1:25 Gleason Webhead Virgin", "Variant Cover", "high", 200.0),
        ("DC", "Batman", "Batman #50 (2018) Jim Lee 1:100 Virgin Variant", "Variant Cover", "high", 350.0),
        ("Marvel", "Venom", "Venom #1 (2018) 1:100 Mark Bagley Virgin Variant", "Variant Cover", "high", 450.0),
        ("Marvel", "Wolverine", "Wolverine #1 (2020) 1:200 Kael Ngu Virgin Variant", "Variant Cover", "grail", 600.0),
        ("Image", "Spawn", "Spawn #300 (2019) J. Scott Campbell 1:50 Virgin", "Variant Cover", "high", 300.0),

        # ── 18. Horror / Sci-Fi Keys (15) ──────────────────────────────────
        ("EC", "Tales from the Crypt", "Tales from the Crypt #33 (1952, Classic Cover)", "Golden Age Key", "grail", 5000.0),
        ("DC", "House of Secrets", "House of Secrets #92 (1st Swamp Thing)", "Bronze Age Key", "grail", 6000.0),
        ("Marvel", "Tomb of Dracula", "Tomb of Dracula #10 (1st Blade)", "Bronze Age Key", "grail", 4000.0),
        ("DC", "Watchmen", "Watchmen #1 (1986, Alan Moore/Dave Gibbons)", "Modern Key", "high", 200.0),
        ("Image", "The Walking Dead", "Walking Dead #100 (1st Negan)", "Modern Key", "high", 150.0),
        ("Image", "Something is Killing the Children", "SIKTC #1 (2019, Cover A)", "Modern Key", "high", 350.0),
        ("IDW", "Locke & Key", "Locke & Key #1 (2008, Joe Hill)", "Modern Key", "high", 200.0),
        ("Dark Horse", "Aliens", "Aliens #1 (1988, Dark Horse)", "Modern Key", "mid", 80.0),
        ("Marvel", "Ghost Rider", "Ghost Rider #1 (1973, Son of Satan cameo)", "Bronze Age Key", "high", 300.0),
        ("EC", "Vault of Horror", "Vault of Horror #12 (#1) (1950)", "Golden Age Key", "grail", 8000.0),
        ("Marvel", "Blade", "Blade the Vampire Hunter #1 (1994)", "Modern Key", "mid", 40.0),
        ("DC", "Preacher", "Preacher #1 (1995, Garth Ennis)", "Modern Key", "high", 250.0),
        ("DC", "Sandman", "Sandman #1 (1989, Neil Gaiman)", "Modern Key", "grail", 800.0),
        ("DC", "Sandman", "Sandman #8 (1st Death of the Endless)", "Modern Key", "high", 400.0),
        ("Image", "Negan Lives", "Negan Lives #1 (2020, Red Foil)", "Variant Cover", "mid", 50.0),

        # ── 19. Undervalued / Cult Classic Keys (15) ───────────────────────
        ("Marvel", "Incredible Hulk", "Incredible Hulk #271 (1st Rocket Raccoon)", "Bronze Age Key", "high", 400.0),
        ("Marvel", "Avengers", "Avengers #196 (1st Taskmaster)", "Bronze Age Key", "high", 200.0),
        ("DC", "Supergirl", "Action Comics #252 (1st Supergirl)", "Silver Age Key", "grail", 8000.0),
        ("Marvel", "Captain Marvel", "Marvel Super-Heroes #12 (1st Captain Marvel)", "Silver Age Key", "grail", 2000.0),
        ("DC", "Teen Titans", "Brave and the Bold #54 (1st Teen Titans)", "Silver Age Key", "grail", 3000.0),
        ("Marvel", "X-Men", "X-Men #94 (New X-Men begin, Thunderbird dies)", "Bronze Age Key", "grail", 2500.0),
        ("Marvel", "Spider-Man", "Amazing Spider-Man #50 (Spider-Man No More!)", "Silver Age Key", "grail", 5000.0),
        ("Marvel", "Silver Surfer", "Silver Surfer #1 (1968, Origin issue)", "Silver Age Key", "grail", 3000.0),
        ("Marvel", "X-Factor", "X-Factor #6 (1st Apocalypse full)", "Modern Key", "high", 250.0),
        ("DC", "Superman", "Superman #75 (Death of Superman, 1992, polybagged)", "Modern Key", "mid", 30.0),
        ("Marvel", "Spider-Man", "Web of Spider-Man #1 (1985)", "Modern Key", "mid", 40.0),
        ("Marvel", "Spider-Man", "Peter Parker: Spider-Man #75 (Death of Ben Reilly)", "Modern Key", "mid", 25.0),
        ("Marvel", "Black Panther", "Fantastic Four #52 (1st Black Panther)", "Silver Age Key", "grail", 12000.0),
        ("DC", "Batgirl", "Detective Comics #359 (1st Batgirl)", "Silver Age Key", "grail", 4000.0),
        ("Marvel", "Shang-Chi", "Special Marvel Edition #15 (1st Shang-Chi)", "Bronze Age Key", "high", 400.0),

        # ── 20. Modern Spec / 2020s Keys (20) ─────────────────────────────
        ("DC", "Batman", "Batman #89 (1st Punchline cameo)", "Modern Key", "high", 100.0),
        ("DC", "Batman", "Batman #92 (1st Punchline full)", "Modern Key", "mid", 60.0),
        ("Marvel", "Venom", "Venom #3 (2018, 1st Knull)", "Modern Key", "high", 200.0),
        ("Marvel", "Thor", "Thor #2 (2020, 1st Black Winter)", "Modern Key", "mid", 50.0),
        ("Marvel", "Immortal Hulk", "Immortal Hulk #1 (2018, Al Ewing)", "Modern Key", "mid", 80.0),
        ("BOOM!", "Something is Killing the Children", "SIKTC #12 (1st Bite-Sized)", "Modern Key", "mid", 40.0),
        ("Marvel", "King in Black", "King in Black #1 (2020, Donny Cates)", "Modern Key", "mid", 30.0),
        ("Image", "Ice Cream Man", "Ice Cream Man #1 (2018, W. Maxwell Prince)", "Modern Key", "high", 200.0),
        ("Image", "Department of Truth", "Department of Truth #1 (2020, James Tynion IV)", "Modern Key", "high", 100.0),
        ("Image", "Radiant Black", "Radiant Black #1 (2021, Kyle Higgins)", "Modern Key", "mid", 40.0),
        ("Marvel", "Spider-Man", "Amazing Spider-Man #798 (1st Red Goblin)", "Modern Key", "mid", 50.0),
        ("Marvel", "Moon Knight", "Moon Knight #1 (2021, Jed MacKay)", "Modern Key", "mid", 30.0),
        ("DC", "Joker", "Joker #1 (2021, James Tynion IV, 1st Daughter of Bane)", "Modern Key", "mid", 35.0),
        ("Marvel", "X-Men", "House of X #1 (2019, Jonathan Hickman)", "Modern Key", "mid", 40.0),
        ("Marvel", "X-Men", "Powers of X #1 (2019, Jonathan Hickman)", "Modern Key", "mid", 30.0),
        ("Image", "Fire & Ice", "Fire & Ice #1 (2023, Bill Willingham cover)", "Modern Key", "mid", 20.0),
        ("Marvel", "Carnage", "Carnage #1 (2022, Ram V)", "Modern Key", "mid", 25.0),
        ("DC", "Nightwing", "Nightwing #78 (2021, Tom Taylor run begins)", "Modern Key", "mid", 40.0),
        ("Marvel", "Spider-Gwen", "Spider-Gwen #1 (2015, Jason Latour)", "Modern Key", "high", 100.0),
        ("Image", "Geiger", "Geiger #1 (2021, Geoff Johns)", "Modern Key", "mid", 30.0),

        # ── 21. Marvel Silver Age Deep Cuts (10) ─────────────────────────
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #14 (1st Green Goblin)", "Silver Age Key", "grail", 25000.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #28 (1st Molten Man)", "Silver Age Key", "grail", 2000.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #3 (1st Doctor Octopus)", "Silver Age Key", "grail", 20000.0),
        ("Marvel", "Avengers", "Avengers #4 (1st Silver Age Captain America)", "Silver Age Key", "grail", 30000.0),
        ("Marvel", "X-Men", "X-Men #4 (1st Scarlet Witch & Quicksilver)", "Silver Age Key", "grail", 5000.0),
        ("Marvel", "X-Men", "X-Men #12 (1st Juggernaut)", "Silver Age Key", "grail", 3000.0),
        ("Marvel", "Fantastic Four", "Fantastic Four #5 (1st Doctor Doom)", "Silver Age Key", "grail", 60000.0),
        ("Marvel", "Fantastic Four", "Fantastic Four #48 (1st Silver Surfer & Galactus)", "Silver Age Key", "grail", 20000.0),
        ("Marvel", "Fantastic Four", "Fantastic Four #49 (2nd Silver Surfer & Galactus)", "Silver Age Key", "grail", 5000.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #2 (1st Vulture)", "Silver Age Key", "grail", 15000.0),

        # ── 22. Marvel Bronze Age Essentials (10) ────────────────────────
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #121 (Death of Gwen Stacy)", "Bronze Age Key", "grail", 5000.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #122 (Death of Green Goblin)", "Bronze Age Key", "grail", 2500.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #101 (1st Morbius)", "Bronze Age Key", "grail", 3000.0),
        ("Marvel", "Incredible Hulk", "Incredible Hulk #182 (Wolverine app)", "Bronze Age Key", "high", 400.0),
        ("Marvel", "Marvel Premiere", "Marvel Premiere #15 (1st Iron Fist)", "Bronze Age Key", "grail", 1500.0),
        ("Marvel", "Hero for Hire", "Hero for Hire #1 (1st Luke Cage)", "Bronze Age Key", "grail", 2000.0),
        ("Marvel", "X-Men", "X-Men #101 (1st Phoenix)", "Bronze Age Key", "grail", 2500.0),
        ("Marvel", "X-Men", "X-Men #129 (1st Kitty Pryde & Emma Frost)", "Bronze Age Key", "grail", 1000.0),
        ("Marvel", "X-Men", "X-Men #130 (1st Dazzler)", "Bronze Age Key", "high", 400.0),
        ("Marvel", "X-Men", "X-Men #137 (Death of Phoenix)", "Bronze Age Key", "grail", 600.0),

        # ── 23. DC Silver/Bronze Age Deep Cuts (10) ──────────────────────
        ("DC", "Flash", "Flash #105 (1st Silver Age Flash ongoing)", "Silver Age Key", "grail", 15000.0),
        ("DC", "Flash", "Flash #139 (1st Reverse Flash)", "Silver Age Key", "grail", 5000.0),
        ("DC", "Green Lantern", "Green Lantern #1 (1st Silver Age GL ongoing, 1960)", "Silver Age Key", "grail", 15000.0),
        ("DC", "Justice League", "Justice League of America #1 (1960)", "Silver Age Key", "grail", 12000.0),
        ("DC", "Adventure Comics", "Adventure Comics #247 (1st Legion of Super-Heroes)", "Silver Age Key", "grail", 10000.0),
        ("DC", "Batman", "Batman #121 (1st Mr. Freeze)", "Silver Age Key", "grail", 8000.0),
        ("DC", "Batman", "Batman #155 (1st Silver Age Penguin)", "Silver Age Key", "grail", 3000.0),
        ("DC", "Superman", "Superman #233 (Classic Neal Adams cover, Kryptonite No More)", "Bronze Age Key", "grail", 1000.0),
        ("DC", "New Gods", "New Gods #1 (1st Orion, Jack Kirby)", "Bronze Age Key", "grail", 800.0),
        ("DC", "Forever People", "Forever People #1 (1st Darkseid full, Jack Kirby)", "Bronze Age Key", "grail", 1000.0),

        # ── 24. DC Modern/Copper Age Keys (10) ──────────────────────────
        ("DC", "Batman", "Batman #404 (Year One Part 1, Frank Miller)", "Modern Key", "high", 200.0),
        ("DC", "Batman", "Batman #386 (1st Black Mask)", "Modern Key", "high", 150.0),
        ("DC", "Batman", "Batman #635 (1st Jason Todd as Red Hood)", "Modern Key", "high", 250.0),
        ("DC", "Batman", "Batman #655 (1st Damian Wayne)", "Modern Key", "high", 300.0),
        ("DC", "Swamp Thing", "Swamp Thing #21 (Alan Moore run begins)", "Modern Key", "high", 200.0),
        ("DC", "Crisis on Infinite Earths", "Crisis on Infinite Earths #8 (Death of Flash)", "Modern Key", "high", 100.0),
        ("DC", "Dark Knight Returns", "Batman: The Dark Knight Returns #1 (1986, Frank Miller)", "Modern Key", "grail", 600.0),
        ("DC", "Superman", "Superman #423 / Action Comics #583 (Whatever Happened to the Man of Tomorrow?)", "Modern Key", "high", 150.0),
        ("DC", "Suicide Squad", "Legends #3 (1987, New Suicide Squad)", "Modern Key", "mid", 80.0),
        ("DC", "Batman", "Batman #427 (A Death in the Family Part 2, Jason Todd dies)", "Modern Key", "high", 200.0),

        # ── 25. Image / Indie Keys Expansion (10) ────────────────────────
        ("Image", "Spawn", "Spawn #9 (1st Angela, Neil Gaiman)", "Modern Key", "high", 100.0),
        ("Image", "Spawn", "Spawn #174 (1st Gunslinger Spawn)", "Modern Key", "mid", 80.0),
        ("Image", "Invincible", "Invincible #25 (1st Angstrom Levy)", "Modern Key", "high", 150.0),
        ("Image", "Invincible", "Invincible #33 (Conquest preview)", "Modern Key", "high", 100.0),
        ("Image", "Walking Dead", "Walking Dead #19 (1st Michonne)", "Modern Key", "grail", 800.0),
        ("Image", "Walking Dead", "Walking Dead #27 (1st Governor)", "Modern Key", "high", 250.0),
        ("Image", "Walking Dead", "Walking Dead #53 (1st Abraham)", "Modern Key", "high", 150.0),
        ("Image", "Deadly Class", "Deadly Class #1 (2014, Rick Remender)", "Modern Key", "mid", 60.0),
        ("Image", "East of West", "East of West #1 (2013, Jonathan Hickman)", "Modern Key", "mid", 50.0),
        ("Image", "Paper Girls", "Paper Girls #1 (2015, BKV)", "Modern Key", "high", 150.0),

        # ── 26. Golden Age Rarities & Timely (8) ─────────────────────────
        ("Timely", "Human Torch", "Human Torch #5 (#4) (1st Sub-Mariner vs Human Torch)", "Golden Age Key", "grail", 100000.0),
        ("Timely", "Sub-Mariner", "Sub-Mariner Comics #1 (1941)", "Golden Age Key", "grail", 120000.0),
        ("Quality", "Police Comics", "Police Comics #1 (1st Plastic Man, 1941)", "Golden Age Key", "grail", 60000.0),
        ("DC", "Sensation Comics", "Sensation Comics #1 (1942, Wonder Woman)", "Golden Age Key", "grail", 80000.0),
        ("DC", "Flash Comics", "Flash Comics #1 (1st Flash Jay Garrick, 1940)", "Golden Age Key", "grail", 150000.0),
        ("Fox", "Blue Beetle", "Blue Beetle #1 (1940, Fox Features)", "Golden Age Key", "grail", 15000.0),
        ("Timely", "All Winners", "All Winners Comics #1 (1941)", "Golden Age Key", "grail", 50000.0),
        ("DC", "World's Finest", "World's Finest Comics #2 (1941, Superman & Batman)", "Golden Age Key", "grail", 30000.0),

        # ── 27. Horror/Sci-Fi Classics (8) ───────────────────────────────
        ("EC", "Haunt of Fear", "Haunt of Fear #15 (#1) (1950)", "Golden Age Key", "grail", 6000.0),
        ("EC", "Weird Science", "Weird Science #12 (#1) (1950, Wally Wood)", "Golden Age Key", "grail", 5000.0),
        ("EC", "Weird Fantasy", "Weird Fantasy #13 (#1) (1950)", "Golden Age Key", "grail", 4000.0),
        ("EC", "Crime SuspenStories", "Crime SuspenStories #22 (1954, most controversial EC)", "Golden Age Key", "grail", 8000.0),
        ("DC", "House of Mystery", "House of Mystery #174 (1st modern horror host)", "Bronze Age Key", "high", 300.0),
        ("Warren", "Creepy", "Creepy #1 (1964, Warren Magazine, 1st issue)", "Silver Age Key", "grail", 2000.0),
        ("Warren", "Eerie", "Eerie #1 (1966, Warren Magazine)", "Silver Age Key", "grail", 1500.0),
        ("Atlas/Marvel", "Journey into Mystery", "Journey into Mystery #1 (1952, pre-hero Atlas)", "Golden Age Key", "grail", 5000.0),

        # ── 28. CGC Graded Expansion (10) ────────────────────────────────
        ("Marvel", "Amazing Spider-Man", "ASM #14 (1st Green Goblin) CGC 9.6", "CGC 9.6", "grail", 80000.0),
        ("Marvel", "Fantastic Four", "Fantastic Four #5 (1st Dr. Doom) CGC 9.6", "CGC 9.6", "grail", 120000.0),
        ("DC", "Action Comics", "Action Comics #1 (1st Superman) CGC 1.0", "CGC 9.6", "grail", 500000.0),
        ("Marvel", "Amazing Spider-Man", "ASM #194 (1st Black Cat) CGC 9.8", "CGC 9.8", "grail", 5000.0),
        ("Marvel", "Werewolf by Night", "Werewolf by Night #32 (1st Moon Knight) CGC 9.8", "CGC 9.8", "grail", 25000.0),
        ("DC", "Batman", "Batman #232 (1st Ra's al Ghul) CGC 9.8", "CGC 9.8", "grail", 30000.0),
        ("Marvel", "Avengers", "Avengers #4 (1st SA Cap) CGC 9.6", "CGC 9.6", "grail", 60000.0),
        ("DC", "Brave and the Bold", "Brave and the Bold #28 (1st JLA) CGC 9.6", "CGC 9.6", "grail", 80000.0),
        ("Marvel", "Iron Man", "Tales of Suspense #39 (1st Iron Man) CGC 9.6", "CGC 9.6", "grail", 150000.0),
        ("Image", "Walking Dead", "Walking Dead #19 (1st Michonne) CGC 9.8", "CGC 9.8", "grail", 3000.0),

        # ── 29. Signed / Remarked Editions (5) ──────────────────────────
        ("Marvel", "Amazing Spider-Man", "ASM #300 Signed by Todd McFarlane CGC SS 9.8", "Signed", "grail", 8000.0),
        ("DC", "Batman", "Batman: Dark Knight Returns #1 Signed by Frank Miller CGC SS 9.8", "Signed", "grail", 3000.0),
        ("Image", "Spawn", "Spawn #1 Signed by Todd McFarlane CGC SS 9.8", "Signed", "grail", 1000.0),
        ("Marvel", "X-Men", "Giant-Size X-Men #1 Signed by Stan Lee CGC SS 9.4", "Signed", "grail", 20000.0),
        ("DC", "Sandman", "Sandman #1 Signed by Neil Gaiman CGC SS 9.8", "Signed", "grail", 2500.0),

        # ── 30. Convention & Store Exclusives Expansion (5) ──────────────
        ("Marvel", "Spider-Man", "ASM #1 (2018) SDCC Exclusive Mark Bagley Virgin", "Convention Exclusive", "high", 150.0),
        ("DC", "Batman", "Batman #1 (2016) NYCC Exclusive Jim Lee Foil", "Convention Exclusive", "high", 120.0),
        ("Image", "Invincible", "Invincible #1 LCSD Exclusive (Local Comic Shop Day)", "Convention Exclusive", "high", 300.0),
        ("Marvel", "Wolverine", "Wolverine #1 (2020) WonderCon Exclusive Artgerm", "Convention Exclusive", "high", 100.0),
        ("BOOM!", "Power Rangers", "Mighty Morphin Power Rangers #1 SDCC Exclusive", "Convention Exclusive", "mid", 50.0),

        # ── 31. Collected Editions / Omnibus Expansion (10) ──────────────
        ("Marvel", "Incredible Hulk", "Incredible Hulk Omnibus Vol. 1 (Peter David)", "Omnibus", "high", 100.0),
        ("DC", "Batman", "Absolute Batman: Court of Owls", "Absolute Edition", "mid", 85.0),
        ("Marvel", "New Mutants", "New Mutants Omnibus Vol. 1 (Claremont)", "Omnibus", "mid", 90.0),
        ("DC", "Superman", "All-Star Superman Absolute Edition (Morrison/Quitely)", "Absolute Edition", "high", 120.0),
        ("Marvel", "X-Men", "Uncanny X-Men Omnibus Vol. 2 (Claremont/Byrne)", "Omnibus", "high", 130.0),
        ("DC", "Green Lantern", "Absolute Green Lantern: Rebirth (Geoff Johns)", "Absolute Edition", "mid", 75.0),
        ("Image", "Invincible", "Invincible Compendium Two (TPB)", "TPB", "mid", 40.0),
        ("Image", "Invincible", "Invincible Compendium Three (TPB)", "TPB", "mid", 40.0),
        ("Marvel", "Punisher", "Punisher MAX by Garth Ennis Omnibus Vol. 1", "Omnibus", "mid", 90.0),
        ("DC", "Justice League", "JLA by Grant Morrison Omnibus", "Omnibus", "mid", 80.0),

        # ── 32. Modern 2024-2025 Spec Keys (10) ─────────────────────────
        ("Marvel", "Ultimate Spider-Man", "Ultimate Spider-Man #1 (2024, Hickman/Checchetto)", "Modern Key", "high", 100.0),
        ("Marvel", "Ultimate X-Men", "Ultimate X-Men #1 (2024, Peach Momoko)", "Modern Key", "mid", 40.0),
        ("DC", "Absolute Batman", "Absolute Batman #1 (2024, Scott Snyder)", "Modern Key", "high", 120.0),
        ("DC", "Absolute Superman", "Absolute Superman #1 (2024, Jason Aaron)", "Modern Key", "mid", 50.0),
        ("Marvel", "Venom", "Venom #1 (2024, Al Ewing, War of the Symbiotes)", "Modern Key", "mid", 25.0),
        ("Marvel", "X-Men", "X-Men #1 (2024, Jed MacKay, From the Ashes)", "Modern Key", "mid", 30.0),
        ("DC", "Absolute Wonder Woman", "Absolute Wonder Woman #1 (2024, Kelly Thompson)", "Modern Key", "mid", 40.0),
        ("Image", "Transformers", "Transformers #1 (2023, Image/Skybound, Daniel Warren Johnson)", "Modern Key", "high", 100.0),
        ("Image", "Void Rivals", "Void Rivals #1 (2023, 1st Energon Universe, Kirkman)", "Modern Key", "high", 150.0),
        ("Marvel", "Ultimate Black Panther", "Ultimate Black Panther #1 (2024, Bryan Hill)", "Modern Key", "mid", 30.0),

        # ── 33. Golden Age — DC Expansion (10) ─────────────────────────────
        ("DC", "Adventure Comics", "Adventure Comics #40 (1st Sandman, Wesley Dodds, 1939)", "Golden Age Key", "grail", 80000.0),
        ("DC", "More Fun Comics", "More Fun Comics #52 (1st Spectre, 1940)", "Golden Age Key", "grail", 60000.0),
        ("DC", "Star Spangled Comics", "Star Spangled Comics #1 (1941)", "Golden Age Key", "grail", 15000.0),
        ("DC", "Adventure Comics", "Adventure Comics #48 (1st Hourman, 1940)", "Golden Age Key", "grail", 30000.0),
        ("DC", "Action Comics", "Action Comics #7 (2nd Superman cover, 1938)", "Golden Age Key", "grail", 100000.0),
        ("DC", "Detective Comics", "Detective Comics #31 (Classic Batman cover, 1939)", "Golden Age Key", "grail", 150000.0),
        ("DC", "Batman", "Batman #5 (1941, 1st Batmobile cover)", "Golden Age Key", "grail", 40000.0),
        ("DC", "Action Comics", "Action Comics #23 (1st Lex Luthor, 1940)", "Golden Age Key", "grail", 80000.0),
        ("DC", "Detective Comics", "Detective Comics #38 (1st Robin, 1940)", "Golden Age Key", "grail", 200000.0),
        ("DC", "Batman", "Batman #16 (1st Alfred, 1943)", "Golden Age Key", "grail", 25000.0),

        # ── 34. Golden Age — Timely/Atlas Expansion (8) ────────────────────
        ("Timely", "Young Allies", "Young Allies Comics #1 (1941, Bucky & Toro)", "Golden Age Key", "grail", 25000.0),
        ("Timely", "All Select", "All Select Comics #1 (1943)", "Golden Age Key", "grail", 20000.0),
        ("Timely", "USA Comics", "USA Comics #1 (1941, 1st Major Liberty)", "Golden Age Key", "grail", 30000.0),
        ("Timely", "Mystic Comics", "Mystic Comics #1 (1940)", "Golden Age Key", "grail", 15000.0),
        ("Timely", "Daring Mystery", "Daring Mystery Comics #1 (1940)", "Golden Age Key", "grail", 20000.0),
        ("Timely", "Captain America Comics", "Captain America Comics #3 (1941, Red Skull cover)", "Golden Age Key", "grail", 30000.0),
        ("Atlas", "Venus", "Venus #1 (1948, Good Girl art)", "Golden Age Key", "grail", 8000.0),
        ("Atlas", "Marvel Boy", "Marvel Boy #1 (1950)", "Golden Age Key", "grail", 5000.0),

        # ── 35. Silver Age — Marvel First Appearances (12) ─────────────────
        ("Marvel", "Tales of Suspense", "Tales of Suspense #52 (1st Black Widow)", "Silver Age Key", "grail", 8000.0),
        ("Marvel", "Tales of Suspense", "Tales of Suspense #57 (1st Hawkeye)", "Silver Age Key", "grail", 5000.0),
        ("Marvel", "Strange Tales", "Strange Tales #135 (1st Nick Fury Agent of SHIELD)", "Silver Age Key", "grail", 3000.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #20 (1st Scorpion)", "Silver Age Key", "grail", 4000.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #9 (1st Electro)", "Silver Age Key", "grail", 8000.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #13 (1st Mysterio)", "Silver Age Key", "grail", 6000.0),
        ("Marvel", "Avengers", "Avengers #8 (1st Kang the Conqueror)", "Silver Age Key", "grail", 6000.0),
        ("Marvel", "X-Men", "X-Men #14 (1st Sentinels)", "Silver Age Key", "grail", 3000.0),
        ("Marvel", "Avengers", "Avengers #16 (New Avengers lineup, Cap's Kooky Quartet)", "Silver Age Key", "grail", 2000.0),
        ("Marvel", "Fantastic Four", "Fantastic Four #45 (1st Inhumans)", "Silver Age Key", "grail", 4000.0),
        ("Marvel", "Avengers", "Avengers #55 (1st Ultron)", "Silver Age Key", "grail", 3000.0),

        # ── 36. Silver Age — DC First Appearances (8) ──────────────────────
        ("DC", "Batman", "Batman #139 (1st Batgirl Bette Kane, 1961)", "Silver Age Key", "grail", 3000.0),
        ("DC", "Showcase", "Showcase #34 (1st Silver Age Atom, 1961)", "Silver Age Key", "grail", 5000.0),
        ("DC", "Showcase", "Showcase #17 (1st Adam Strange, 1958)", "Silver Age Key", "grail", 4000.0),
        ("DC", "Adventure Comics", "Adventure Comics #260 (1st Silver Age Aquaman, 1959)", "Silver Age Key", "grail", 3000.0),
        ("DC", "Showcase", "Showcase #30 (1st Silver Age Aquaman solo, 1961)", "Silver Age Key", "grail", 3000.0),
        ("DC", "Teen Titans", "Teen Titans #1 (1966, own series)", "Silver Age Key", "grail", 2000.0),
        ("DC", "Hawkman", "Brave and the Bold #34 (1st Silver Age Hawkman, 1961)", "Silver Age Key", "grail", 4000.0),
        ("DC", "Metal Men", "Showcase #37 (1st Metal Men, 1962)", "Silver Age Key", "grail", 3000.0),

        # ── 37. Bronze Age — All Key Deaths & First Appearances (12) ───────
        ("Marvel", "Incredible Hulk", "Incredible Hulk #271 (1st Rocket Raccoon) CGC 9.8", "CGC 9.8", "grail", 2000.0),
        ("Marvel", "Power Man", "Power Man #48 (Power Man & Iron Fist begin)", "Bronze Age Key", "high", 200.0),
        ("Marvel", "Tomb of Dracula", "Tomb of Dracula #1 (1972)", "Bronze Age Key", "grail", 1500.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #129 CGC 9.8", "CGC 9.8", "grail", 40000.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #238 (1st Hobgoblin)", "Bronze Age Key", "grail", 600.0),
        ("Marvel", "Marvel Premiere", "Marvel Premiere #47 (1st Scott Lang Ant-Man)", "Bronze Age Key", "high", 400.0),
        ("DC", "Batman", "Batman #227 (Classic Neal Adams cover, homage to Det. #31)", "Bronze Age Key", "grail", 1000.0),
        ("DC", "Green Lantern", "Green Lantern #87 (1st John Stewart)", "Bronze Age Key", "grail", 2000.0),
        ("Marvel", "Iron Fist", "Iron Fist #14 (1st Sabretooth)", "Bronze Age Key", "grail", 1500.0),
        ("Marvel", "Avengers", "Avengers #181 (1st Scott Lang appearance)", "Bronze Age Key", "high", 300.0),
        ("DC", "Superman", "Superman #276 (Captain Thunder, proto-Shazam at DC)", "Bronze Age Key", "high", 150.0),
        ("Marvel", "What If?", "What If? #10 (1st Jane Foster as Thor)", "Bronze Age Key", "high", 250.0),

        # ── 38. Copper Age Keys (10) ───────────────────────────────────────
        ("DC", "Dark Knight Returns", "Batman: The Dark Knight Returns #2 (1986)", "Modern Key", "high", 200.0),
        ("DC", "Dark Knight Returns", "Batman: The Dark Knight Returns #3 (1986)", "Modern Key", "high", 150.0),
        ("DC", "Dark Knight Returns", "Batman: The Dark Knight Returns #4 (1986)", "Modern Key", "high", 200.0),
        ("DC", "Watchmen", "Watchmen #12 (1987, Final Issue)", "Modern Key", "high", 100.0),
        ("DC", "Crisis on Infinite Earths", "Crisis on Infinite Earths #1 (1985)", "Modern Key", "high", 150.0),
        ("Marvel", "Secret Wars", "Marvel Super Heroes Secret Wars #1 (1984)", "Modern Key", "high", 200.0),
        ("Marvel", "Secret Wars", "Marvel Super Heroes Secret Wars #12 (1985)", "Modern Key", "high", 100.0),
        ("DC", "Legends", "Legends #1 (1986, 1st Modern Amanda Waller)", "Modern Key", "mid", 60.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #298 (1st Todd McFarlane ASM)", "Modern Key", "high", 200.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #299 (Venom cameo)", "Modern Key", "high", 150.0),

        # ── 39. Image Founders Era (10) ────────────────────────────────────
        ("Image", "Savage Dragon", "Savage Dragon #2 (1992)", "Modern Key", "mid", 20.0),
        ("Image", "Savage Dragon", "Savage Dragon #3 (1992)", "Modern Key", "mid", 15.0),
        ("Image", "WildC.A.T.s", "WildC.A.T.s #1 (1992, Jim Lee)", "Modern Key", "mid", 30.0),
        ("Image", "WildC.A.T.s", "WildC.A.T.s #2 (1992)", "Modern Key", "mid", 15.0),
        ("Image", "Youngblood", "Youngblood #1 (1992, Rob Liefeld)", "Modern Key", "mid", 25.0),
        ("Image", "Youngblood", "Youngblood #1 (1992, Gold Edition)", "Variant Cover", "mid", 80.0),
        ("Image", "Cyberforce", "Cyberforce #1 (1992, Marc Silvestri)", "Modern Key", "mid", 20.0),
        ("Image", "Shadowhawk", "Shadowhawk #1 (1992, Jim Valentino)", "Modern Key", "mid", 15.0),
        ("Image", "Wetworks", "Wetworks #1 (1994, Whilce Portacio)", "Modern Key", "mid", 15.0),
        ("Image", "Pitt", "Pitt #1 (1993, Dale Keown)", "Modern Key", "mid", 20.0),

        # ── 40. Vertigo Keys (10) ──────────────────────────────────────────
        ("DC/Vertigo", "Sandman", "Sandman #75 (1996, Final Issue)", "Modern Key", "high", 100.0),
        ("DC/Vertigo", "Hellblazer", "Hellblazer #1 (1988, 1st John Constantine ongoing)", "Modern Key", "high", 300.0),
        ("DC/Vertigo", "Swamp Thing", "Swamp Thing #37 (1st John Constantine, Alan Moore)", "Modern Key", "high", 500.0),
        ("DC/Vertigo", "Y: The Last Man", "Y: The Last Man #1 (2002, Brian K. Vaughan)", "Modern Key", "high", 300.0),
        ("DC/Vertigo", "Fables", "Fables #1 (2002, Bill Willingham)", "Modern Key", "high", 150.0),
        ("DC/Vertigo", "100 Bullets", "100 Bullets #1 (1999, Brian Azzarello)", "Modern Key", "mid", 80.0),
        ("DC/Vertigo", "Transmetropolitan", "Transmetropolitan #1 (1997, Warren Ellis)", "Modern Key", "high", 100.0),
        ("DC/Vertigo", "Lucifer", "Lucifer #1 (2000, Mike Carey)", "Modern Key", "mid", 60.0),
        ("DC/Vertigo", "DMZ", "DMZ #1 (2006, Brian Wood)", "Modern Key", "mid", 40.0),
        ("DC/Vertigo", "Animal Man", "Animal Man #1 (1988, Grant Morrison)", "Modern Key", "high", 100.0),

        # ── 41. Dark Horse Keys (8) ────────────────────────────────────────
        ("Dark Horse", "Hellboy", "Hellboy: Wake the Devil #1 (1996, Mignola)", "Modern Key", "mid", 60.0),
        ("Dark Horse", "The Mask", "The Mask #1 (1991, Dark Horse)", "Modern Key", "high", 200.0),
        ("Dark Horse", "Aliens", "Aliens vs. Predator #0 (1989, Ashcan)", "Modern Key", "mid", 80.0),
        ("Dark Horse", "Star Wars", "Star Wars: Dark Empire #1 (1991)", "Modern Key", "mid", 60.0),
        ("Dark Horse", "Usagi Yojimbo", "Usagi Yojimbo #1 (1987, Stan Sakai)", "Modern Key", "high", 200.0),
        ("Dark Horse", "Concrete", "Concrete #1 (1987, Paul Chadwick)", "Modern Key", "mid", 40.0),
        ("Dark Horse", "300", "300 #1 (1998, Frank Miller)", "Modern Key", "high", 100.0),
        ("Dark Horse", "Umbrella Academy", "Umbrella Academy: Apocalypse Suite #1 (2007, Gerard Way)", "Modern Key", "high", 200.0),

        # ── 42. IDW Keys (6) ──────────────────────────────────────────────
        ("IDW", "TMNT", "Teenage Mutant Ninja Turtles #1 (2011, IDW)", "Modern Key", "mid", 60.0),
        ("IDW", "Transformers", "Transformers: More Than Meets the Eye #1 (2012)", "Modern Key", "mid", 30.0),
        ("IDW", "30 Days of Night", "30 Days of Night #1 (2002, Steve Niles)", "Modern Key", "high", 150.0),
        ("IDW", "Locke & Key", "Locke & Key: Welcome to Lovecraft #1 (2008)", "Modern Key", "high", 250.0),
        ("IDW", "Star Trek", "Star Trek: Countdown #1 (2009, movie prequel)", "Modern Key", "mid", 30.0),
        ("IDW", "GI Joe", "GI Joe #1 (2008, IDW relaunch)", "Modern Key", "mid", 25.0),

        # ── 43. BOOM! Studios Keys (6) ─────────────────────────────────────
        ("BOOM!", "Lumberjanes", "Lumberjanes #1 (2014)", "Modern Key", "high", 150.0),
        ("BOOM!", "Once & Future", "Once & Future #1 (2019, Kieron Gillen)", "Modern Key", "mid", 60.0),
        ("BOOM!", "Irredeemable", "Irredeemable #1 (2009, Mark Waid)", "Modern Key", "mid", 50.0),
        ("BOOM!", "Power Rangers", "Mighty Morphin Power Rangers #0 (2016)", "Modern Key", "mid", 40.0),
        ("BOOM!", "Something is Killing the Children", "SIKTC #1 Cover B (2019, Jenny Frison)", "Modern Key", "grail", 1000.0),
        ("BOOM!", "Keanu Reeves' BRZRKR", "BRZRKR #1 (2021, Keanu Reeves)", "Modern Key", "mid", 40.0),

        # ── 44. Valiant Keys (6) ──────────────────────────────────────────
        ("Valiant", "X-O Manowar", "X-O Manowar #1 (1992, with coupon)", "Modern Key", "high", 100.0),
        ("Valiant", "Bloodshot", "Bloodshot #1 (1993)", "Modern Key", "mid", 50.0),
        ("Valiant", "Rai", "Rai #0 (1992, 1st Bloodshot chromium)", "Modern Key", "high", 100.0),
        ("Valiant", "Ninjak", "Ninjak #1 (1994, chromium cover)", "Modern Key", "mid", 40.0),
        ("Valiant", "Divinity", "Divinity #1 (2015, Matt Kindt)", "Modern Key", "mid", 30.0),
        ("Valiant", "X-O Manowar", "X-O Manowar #0 (1993, Gold edition)", "Variant Cover", "high", 150.0),

        # ── 45. CGC Signature Series (10) ──────────────────────────────────
        ("Marvel", "Amazing Spider-Man", "ASM #1 (1963) Signed by Stan Lee CGC SS 6.0", "Signed", "grail", 50000.0),
        ("Marvel", "Incredible Hulk", "Incredible Hulk #181 Signed by Len Wein CGC SS 9.2", "Signed", "grail", 25000.0),
        ("DC", "Batman", "Batman #1 (2016) Signed by Tom King CGC SS 9.8", "Signed", "high", 200.0),
        ("Marvel", "Amazing Spider-Man", "ASM #129 Signed by Gerry Conway CGC SS 9.4", "Signed", "grail", 12000.0),
        ("Image", "Walking Dead", "Walking Dead #1 Signed by Robert Kirkman CGC SS 9.8", "Signed", "grail", 10000.0),
        ("Image", "Invincible", "Invincible #1 Signed by Robert Kirkman CGC SS 9.8", "Signed", "grail", 8000.0),
        ("DC", "Watchmen", "Watchmen #1 Signed by Dave Gibbons CGC SS 9.8", "Signed", "grail", 2000.0),
        ("Marvel", "X-Men", "X-Men #1 (1963) Signed by Stan Lee CGC SS 5.0", "Signed", "grail", 30000.0),
        ("Marvel", "New Mutants", "New Mutants #98 Signed by Rob Liefeld CGC SS 9.8", "Signed", "grail", 5000.0),
        ("DC", "Batman", "Batman Adventures #12 Signed by Bruce Timm CGC SS 9.8", "Signed", "grail", 8000.0),

        # ── 46. Variant Covers — High Ratio (10) ──────────────────────────
        ("Marvel", "Amazing Spider-Man", "ASM #1 (2022) 1:100 John Romita Sr. Virgin", "Variant Cover", "grail", 500.0),
        ("Marvel", "Thor", "Thor #1 (2020) 1:200 Peach Momoko Virgin", "Variant Cover", "grail", 800.0),
        ("DC", "Batman", "Batman #125 (2022) 1:100 Alex Ross Virgin", "Variant Cover", "grail", 500.0),
        ("Marvel", "X-Men", "X-Men #1 (2024) 1:500 Peach Momoko Virgin", "Variant Cover", "grail", 1200.0),
        ("DC", "Superman", "Superman #1 (2023) 1:100 Jim Lee Virgin", "Variant Cover", "high", 350.0),
        ("Marvel", "Ultimate Spider-Man", "Ultimate Spider-Man #1 (2024) 1:100 Marco Checchetto Virgin", "Variant Cover", "grail", 600.0),
        ("Marvel", "Venom", "Venom #1 (2024) 1:50 Ryan Stegman Virgin", "Variant Cover", "high", 200.0),
        ("DC", "Absolute Batman", "Absolute Batman #1 (2024) 1:50 Jock Virgin", "Variant Cover", "high", 300.0),
        ("Image", "Transformers", "Transformers #1 (2023) 1:100 DWJ Virgin Variant", "Variant Cover", "grail", 500.0),
        ("Marvel", "Spider-Man", "Amazing Spider-Man #900 (2022) 1:500 Alex Ross Virgin", "Variant Cover", "grail", 1000.0),

        # ── 47. Omnibus & Absolute Editions Expansion (10) ─────────────────
        ("Marvel", "Spider-Man", "Amazing Spider-Man Omnibus Vol. 2 (Lee/Romita)", "Omnibus", "high", 110.0),
        ("Marvel", "Spider-Man", "Amazing Spider-Man Omnibus Vol. 3 (Lee/Kane)", "Omnibus", "high", 100.0),
        ("DC", "Batman", "Absolute Batman: Dark Victory", "Absolute Edition", "mid", 90.0),
        ("DC", "Superman", "Absolute Superman: For All Seasons", "Absolute Edition", "mid", 75.0),
        ("Marvel", "X-Men", "Uncanny X-Men Omnibus Vol. 3 (Claremont/Romita Jr.)", "Omnibus", "high", 120.0),
        ("Marvel", "Captain America", "Captain America Omnibus Vol. 1 (Brubaker)", "Omnibus", "mid", 90.0),
        ("DC", "Batman", "Absolute Batman: Year One", "Absolute Edition", "high", 120.0),
        ("Marvel", "Venom", "Venom by Donny Cates Omnibus", "Omnibus", "mid", 85.0),
        ("DC", "Wonder Woman", "Absolute Wonder Woman by George Perez Vol. 1", "Absolute Edition", "high", 100.0),
        ("Image", "Saga", "Saga Compendium Two (TPB)", "TPB", "mid", 35.0),

        # ── 48. Magazine-Size Comics (10) ──────────────────────────────────
        ("Warren", "Creepy", "Creepy #2 (1965, Frank Frazetta cover)", "Silver Age Key", "grail", 1000.0),
        ("Warren", "Creepy", "Creepy #9 (1966, Frank Frazetta cover)", "Silver Age Key", "high", 500.0),
        ("Warren", "Eerie", "Eerie #8 (1967, Steve Ditko art)", "Silver Age Key", "high", 400.0),
        ("Warren", "Vampirella", "Vampirella #1 (1969, Warren Magazine, 1st Vampirella)", "Silver Age Key", "grail", 5000.0),
        ("Warren", "Vampirella", "Vampirella #11 (1971, Spanish Vampirella art begins)", "Bronze Age Key", "high", 300.0),
        ("Marvel", "Savage Sword of Conan", "Savage Sword of Conan #1 (1974, Magazine)", "Bronze Age Key", "high", 300.0),
        ("Heavy Metal", "Heavy Metal", "Heavy Metal #1 (1977, 1st issue)", "Bronze Age Key", "grail", 500.0),
        ("Heavy Metal", "Heavy Metal", "Heavy Metal V1 #3 (1977, Moebius Arzach)", "Bronze Age Key", "high", 200.0),
        ("Marvel", "Bizarre Adventures", "Bizarre Adventures #34 (1983, last Marvel magazine)", "Modern Key", "mid", 40.0),
        ("Warren", "Creepy", "Creepy #146 (1983, Final Issue)", "Modern Key", "mid", 80.0),

        # ── 49. Modern Indie — 2010s-2020s (12) ───────────────────────────
        ("Image", "Nailbiter", "Nailbiter #1 (2014, Joshua Williamson)", "Modern Key", "mid", 40.0),
        ("Image", "Descender", "Descender #1 (2015, Jeff Lemire)", "Modern Key", "mid", 50.0),
        ("Image", "Die", "Die #1 (2018, Kieron Gillen)", "Modern Key", "mid", 30.0),
        ("Image", "Undiscovered Country", "Undiscovered Country #1 (2019, Snyder/Soule)", "Modern Key", "mid", 30.0),
        ("Image", "King Spawn", "King Spawn #1 (2021, Sean Lewis)", "Modern Key", "mid", 25.0),
        ("Image", "Local Man", "Local Man #1 (2023, Tim Seeley)", "Modern Key", "mid", 20.0),
        ("Aftershock", "Animosity", "Animosity #1 (2016, Marguerite Bennett)", "Modern Key", "mid", 40.0),
        ("Oni Press", "Scott Pilgrim", "Scott Pilgrim Vol. 1 (2004, Bryan Lee O'Malley)", "First Print", "high", 200.0),
        ("Drawn & Quarterly", "Fun Home", "Fun Home (2006, Alison Bechdel, 1st print HC)", "First Print", "high", 150.0),
        ("Fantagraphics", "Acme Novelty Library", "Acme Novelty Library #1 (1993, Chris Ware)", "First Print", "high", 100.0),
        ("Top Shelf", "Blankets", "Blankets (2003, Craig Thompson, 1st print HC)", "First Print", "mid", 80.0),
        ("Image", "Crossover", "Crossover #1 (2020, Donny Cates)", "Modern Key", "mid", 30.0),

        # ── 50. Marvel 2024-2025 Hot Keys (10) ─────────────────────────────
        ("Marvel", "Ultimate Spider-Man", "Ultimate Spider-Man #5 (2024, 1st Ultimate Green Goblin)", "Modern Key", "mid", 40.0),
        ("Marvel", "X-Men", "X-Men #35 (2024, From the Ashes finale)", "Modern Key", "mid", 25.0),
        ("Marvel", "Absolute Carnage", "Absolute Carnage #1 (2019, Donny Cates)", "Modern Key", "mid", 50.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #26 (2023, Death of Ms. Marvel)", "Modern Key", "mid", 40.0),
        ("Marvel", "Wolverine", "Wolverine #50 (2024, sabretooth anniversary)", "Modern Key", "mid", 30.0),
        ("Marvel", "Fantastic Four", "Fantastic Four #1 (2025, Ryan North)", "Modern Key", "mid", 25.0),
        ("Marvel", "Thunderbolts", "Thunderbolts #1 (2025, Marvel movie tie-in)", "Modern Key", "mid", 30.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #252 (Symbiote origin) CGC 9.8", "CGC 9.8", "grail", 2000.0),
        ("Marvel", "Avengers", "Avengers #57 (1st Vision) CGC 9.6", "CGC 9.6", "grail", 8000.0),
        ("Marvel", "Daredevil", "Daredevil #1 (1964) CGC 9.6", "CGC 9.6", "grail", 40000.0),

        # ── 51. DC 2024-2025 Keys (8) ──────────────────────────────────────
        ("DC", "Absolute Batman", "Absolute Batman #2 (2024, Scott Snyder)", "Modern Key", "mid", 30.0),
        ("DC", "Absolute Batman", "Absolute Batman #3 (2024)", "Modern Key", "mid", 25.0),
        ("DC", "Absolute Superman", "Absolute Superman #2 (2024, Jason Aaron)", "Modern Key", "mid", 25.0),
        ("DC", "Green Lantern", "Green Lantern #1 (2023, Jeremy Adams)", "Modern Key", "mid", 30.0),
        ("DC", "Batman", "Batman #137 (2024, Chip Zdarsky, Failsafe saga)", "Modern Key", "mid", 30.0),
        ("DC", "Flash", "The Flash #1 (2023, Si Spurrier)", "Modern Key", "mid", 25.0),
        ("DC", "Absolute Wonder Woman", "Absolute Wonder Woman #2 (2024)", "Modern Key", "mid", 20.0),
        ("DC", "Nightwing", "Nightwing #100 (2023, Tom Taylor)", "Modern Key", "mid", 40.0),

        # ── 52. CGC Graded — Additional High-Value (10) ────────────────────
        ("Marvel", "Fantastic Four", "Fantastic Four #1 (1961) CGC 9.6", "CGC 9.6", "grail", 400000.0),
        ("Marvel", "X-Men", "X-Men #1 (1963) CGC 9.6", "CGC 9.6", "grail", 100000.0),
        ("DC", "Batman", "Batman #1 (1940) CGC 6.0", "CGC 9.6", "grail", 300000.0),
        ("DC", "Superman", "Superman #1 (1939) CGC 5.0", "CGC 9.6", "grail", 250000.0),
        ("Marvel", "Captain America", "Captain America Comics #1 (1941) CGC 9.0", "CGC 9.6", "grail", 500000.0),
        ("Marvel", "Avengers", "Avengers #1 (1963) CGC 9.6", "CGC 9.6", "grail", 100000.0),
        ("DC", "Showcase", "Showcase #4 (1st SA Flash) CGC 9.4", "CGC 9.6", "grail", 150000.0),
        ("Marvel", "Amazing Spider-Man", "ASM #50 (Spider-Man No More) CGC 9.8", "CGC 9.8", "grail", 50000.0),
        ("Marvel", "Amazing Spider-Man", "ASM #121 (Death of Gwen Stacy) CGC 9.8", "CGC 9.8", "grail", 30000.0),
        ("DC", "Batman", "Batman #181 (1st Poison Ivy) CGC 9.6", "CGC 9.6", "grail", 25000.0),

        # ── 53. Additional Modern Keys & Indies (8) ────────────────────────
        ("Image", "Hack/Slash", "Hack/Slash #1 (2004, Tim Seeley)", "Modern Key", "mid", 50.0),
        ("Oni Press", "Rick and Morty", "Rick and Morty #1 (2015, Oni Press)", "Modern Key", "mid", 80.0),
        ("Archie", "Afterlife with Archie", "Afterlife with Archie #1 (2013, Francesco Francavilla)", "Modern Key", "mid", 60.0),
        ("Image", "Chew", "Chew #1 CGC 9.8", "CGC 9.8", "grail", 800.0),
        ("Avatar", "Crossed", "Crossed #1 (2008, Garth Ennis)", "Modern Key", "mid", 50.0),
        ("Dynamite", "The Boys", "The Boys #1 (2006, Garth Ennis)", "Modern Key", "high", 300.0),
        ("Dynamite", "Red Sonja", "Red Sonja #1 (2005, Michael Turner cover)", "Variant Cover", "mid", 60.0),
        ("Antarctic Press", "Gold Digger", "Gold Digger #1 (1992, Fred Perry)", "Modern Key", "mid", 40.0),
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

    # Round 7 expansion — 50 items
    catalog.extend(_expanded_round7_comic_books())

    # Round 8 expansion — 55 items (Image, Dark Horse, Indie, DC Silver Age,
    # Marvel Bronze Age, Modern spec, CGC graded slabs)
    catalog.extend(_expanded_round8_comic_books())

    # Round 10 expansion — ~120 items: variant covers, CGC graded tiers,
    # signature series, modern keys, independent/Image keys
    catalog.extend(_expanded_variant_covers_graded_modern())

    # Deduplicate by ('publisher', 'name') (keep first occurrence)
    _seen: set = set()
    _deduped: list = []
    for item in catalog:
        _key = (item["publisher"], item["name"])
        if _key not in _seen:
            _seen.add(_key)
            _deduped.append(item)
    return _deduped


def _expanded_round7_comic_books() -> list[dict]:
    """50 new comic book items: Image keys, Dark Horse keys, indie keys, modern hot keys, CGC 9.8 variants."""
    comics = [
        # --- Image Comics Keys ---
        ("Image", "Walking Dead", "Walking Dead #1 (2003, Robert Kirkman, 1st print)", "Modern Key", "grail", 3000.0),
        ("Image", "Invincible", "Invincible #1 (2003, Robert Kirkman, 1st print)", "Modern Key", "grail", 2500.0),
        ("Image", "Saga", "Saga #1 (2012, Brian K. Vaughan, 1st print)", "Modern Key", "high", 250.0),
        ("Image", "Spawn", "Spawn #1 (1992, Todd McFarlane, 1st print)", "Modern Key", "high", 150.0),
        ("Image", "Spawn", "Spawn #174 (2008, 1st She-Spawn)", "Modern Key", "mid", 80.0),
        ("Image", "The Walking Dead", "Walking Dead #19 (2005, 1st Michonne)", "Modern Key", "high", 400.0),
        ("Image", "The Walking Dead", "Walking Dead #27 (2006, 1st Governor)", "Modern Key", "high", 200.0),
        ("Image", "The Walking Dead", "Walking Dead #100 (2012, Death of Glenn)", "Modern Key", "high", 150.0),
        ("Image", "Invincible", "Invincible #7 (2003, 1st Atom Eve)", "Modern Key", "high", 300.0),
        ("Image", "Invincible", "Invincible #25 (2005, 1st Rex Splode death fake-out)", "Modern Key", "mid", 80.0),

        # --- Dark Horse Comics Keys ---
        ("Dark Horse", "Hellboy", "Hellboy: Seed of Destruction #1 (1994, Mike Mignola)", "Modern Key", "high", 200.0),
        ("Dark Horse", "Sin City", "Sin City: The Hard Goodbye TPB (1991, Frank Miller, 1st print)", "First Print", "high", 150.0),
        ("Dark Horse", "The Mask", "The Mask #1 (1991, 1st Dark Horse series)", "Modern Key", "mid", 80.0),
        ("Dark Horse", "Star Wars Dark Empire", "Star Wars: Dark Empire #1 (1991, Tom Veitch)", "Modern Key", "mid", 60.0),
        ("Dark Horse", "Aliens", "Aliens #1 (1988, 1st Dark Horse Aliens)", "Modern Key", "high", 200.0),
        ("Dark Horse", "Predator", "Predator #1 (1989, 1st comic appearance)", "Modern Key", "high", 120.0),

        # --- Indie Publisher Keys ---
        ("Cartoon Books", "Bone", "Bone #1 (1991, Jeff Smith, 1st print)", "Modern Key", "high", 400.0),
        ("Aardvark-Vanaheim", "Cerebus", "Cerebus the Aardvark #1 (1977, Dave Sim)", "Bronze Age Key", "grail", 2000.0),
        ("Mirage", "TMNT", "Teenage Mutant Ninja Turtles #1 (1984, Eastman/Laird, 1st print)", "Modern Key", "grail", 8000.0),
        ("Mirage", "TMNT", "Teenage Mutant Ninja Turtles #1 (1984, 2nd print)", "First Print", "high", 400.0),
        ("Caliber", "The Crow", "The Crow #1 (1989, James O'Barr, 1st print)", "Modern Key", "grail", 1500.0),
        ("Eclipse", "Miracleman", "Miracleman #1 (1985, Alan Moore, Eclipse)", "Modern Key", "high", 200.0),
        ("Pacific Comics", "Rocketeer", "Rocketeer Special Edition #1 (1984, Dave Stevens)", "Modern Key", "high", 150.0),

        # --- Modern Hot Keys (2020-2025) ---
        ("BOOM!", "Something is Killing the Children", "Something is Killing the Children #1 (2019, James Tynion IV, 1st print)", "Modern Key", "grail", 800.0),
        ("BOOM!", "Something is Killing the Children", "SIKTC #7 (2020, 1st Cecilia)", "Modern Key", "mid", 50.0),
        ("BOOM!", "House of Slaughter", "House of Slaughter #1 (2021, Tynion/Dell'Edera)", "Modern Key", "mid", 40.0),
        ("Image", "Ice Cream Man", "Ice Cream Man #1 (2018, W. Maxwell Prince, 1st print)", "Modern Key", "high", 200.0),
        ("Image", "Department of Truth", "Department of Truth #1 (2020, James Tynion IV, 2nd print)", "Modern Key", "mid", 60.0),
        ("Image", "Void Rivals", "Void Rivals #1 (2023, Robert Kirkman, 1st Energon Universe)", "Modern Key", "high", 100.0),
        ("Image", "Void Rivals", "Void Rivals #1 (2023, 2nd print, 1st Transformers cameo)", "Modern Key", "mid", 40.0),
        ("Image", "Universal Monsters: Dracula", "Universal Monsters: Dracula #1 (2023, James Tynion IV)", "Modern Key", "mid", 30.0),
        ("Skybound", "Energon Universe: Transformers", "Transformers #1 (2023, Daniel Warren Johnson)", "Modern Key", "high", 120.0),
        ("Skybound", "Energon Universe: G.I. Joe", "G.I. Joe #1 (2023, Joshua Williamson)", "Modern Key", "mid", 40.0),

        # --- CGC 9.8 Graded Keys & Variants ---
        ("Image", "Spawn", "Spawn #1 CGC 9.8 (1992, Todd McFarlane)", "CGC 9.8", "grail", 800.0),
        ("Image", "Saga", "Saga #1 CGC 9.8 (2012, BKV/Staples)", "CGC 9.8", "grail", 1200.0),
        ("Image", "Ice Cream Man", "Ice Cream Man #1 CGC 9.8 (2018)", "CGC 9.8", "grail", 800.0),
        ("BOOM!", "Something is Killing the Children", "SIKTC #1 CGC 9.8 (2019)", "CGC 9.8", "grail", 3000.0),
        ("Image", "Invincible", "Invincible #1 CGC 9.8 (2003, Kirkman/Walker)", "CGC 9.8", "grail", 8000.0),
        ("Image", "Walking Dead", "Walking Dead #1 CGC 9.8 (2003, Black Label)", "CGC 9.8", "grail", 12000.0),
        ("Dark Horse", "Hellboy", "Hellboy: Seed of Destruction #1 CGC 9.8 (1994)", "CGC 9.8", "grail", 1500.0),
        ("Mirage", "TMNT", "TMNT #1 CGC 9.6 (1984, 1st print, Eastman/Laird)", "CGC 9.6", "grail", 30000.0),
        ("Image", "The Department of Truth", "Department of Truth #1 CGC 9.8 (1:25 Simmonds variant)", "CGC 9.8", "grail", 500.0),
        ("Marvel", "Venom", "Venom: Lethal Protector #1 CGC 9.8 (1993, Black Cover)", "CGC 9.8", "grail", 600.0),

        # --- Additional Modern Indies ---
        ("BOOM!", "Lumberjanes", "Lumberjanes #1 (2014, Stevenson/Watters, 1st print)", "Modern Key", "mid", 50.0),
        ("BOOM!", "Once & Future", "Once & Future #1 (2019, Kieron Gillen, 1st print)", "Modern Key", "mid", 30.0),
        ("Image", "Stray Dogs", "Stray Dogs #1 (2021, Tony Fleecs, 1st print)", "Modern Key", "mid", 25.0),
        ("Image", "W0rldtr33", "W0rldtr33 #1 (2023, James Tynion IV, 1st print)", "Modern Key", "mid", 20.0),
        ("Image", "Geiger", "Geiger #1 (2021, Geoff Johns, 1st print)", "Modern Key", "mid", 25.0),
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


def _expanded_round8_comic_books() -> list[dict]:
    """55 new comic book items: Image keys, Dark Horse keys, indie keys,
    DC Silver Age, Marvel Bronze Age, modern spec keys, CGC graded slabs."""
    comics = [
        # --- Image Comics Keys (+10) ---
        ("Image", "Savage Dragon", "Savage Dragon #1 (1992, Erik Larsen, 1st print)", "Modern Key", "mid", 60.0),
        ("Image", "Witchblade", "Witchblade #1 (1995, Michael Turner, 1st print)", "Modern Key", "mid", 80.0),
        ("Image", "The Darkness", "The Darkness #1 (1996, Marc Silvestri/Garth Ennis)", "Modern Key", "mid", 50.0),
        ("Image", "Youngblood", "Youngblood #1 (1992, Rob Liefeld, 1st print)", "Modern Key", "mid", 30.0),
        ("Image", "Cyberforce", "Cyberforce #1 (1992, Marc Silvestri, 1st print)", "Modern Key", "mid", 25.0),
        ("Image", "Pitt", "Pitt #1 (1993, Dale Keown, 1st print)", "Modern Key", "mid", 20.0),
        ("Image", "Deadly Class", "Deadly Class #1 (2014, Rick Remender/Wes Craig)", "Modern Key", "mid", 60.0),
        ("Image", "Paper Girls", "Paper Girls #1 (2015, Brian K. Vaughan/Cliff Chiang)", "Modern Key", "high", 120.0),
        ("Image", "East of West", "East of West #1 (2013, Jonathan Hickman/Nick Dragotta)", "Modern Key", "mid", 50.0),
        ("Image", "Nailbiter", "Nailbiter #1 (2014, Joshua Williamson, 1st print)", "Modern Key", "mid", 30.0),

        # --- Dark Horse Keys (+8) ---
        ("Dark Horse", "300", "300 #1 (1998, Frank Miller, 1st print)", "Modern Key", "high", 200.0),
        ("Dark Horse", "Usagi Yojimbo", "Usagi Yojimbo #1 (1987, Stan Sakai, Dark Horse run)", "Modern Key", "high", 150.0),
        ("Dark Horse", "Barb Wire", "Barb Wire #1 (1994, Chris Warner)", "Modern Key", "mid", 20.0),
        ("Dark Horse", "Ghost", "Ghost #1 (1995, Eric Luke/Adam Hughes)", "Modern Key", "mid", 30.0),
        ("Dark Horse", "X", "X #1 (1994, Steven Grant)", "Modern Key", "mid", 15.0),
        ("Dark Horse", "Grendel", "Grendel: War Child #1 (1992, Matt Wagner)", "Modern Key", "mid", 25.0),
        ("Dark Horse", "Emily the Strange", "Emily the Strange #1 (2005, Dark Horse)", "Modern Key", "mid", 40.0),
        ("Dark Horse", "Umbrella Academy", "Umbrella Academy: Apocalypse Suite #1 (2007, Gerard Way/Gabriel Ba)", "Modern Key", "high", 180.0),

        # --- Indie Publisher Keys (+8) ---
        ("Fantagraphics", "Love and Rockets", "Love and Rockets #1 (1982, Hernandez Brothers, 1st print)", "Modern Key", "high", 300.0),
        ("Drawn & Quarterly", "Berlin", "Berlin #1 (1996, Jason Lutes)", "Modern Key", "mid", 40.0),
        ("Oni Press", "Scott Pilgrim", "Scott Pilgrim Vol 1 (2004, Bryan Lee O'Malley, 1st print)", "First Print", "high", 200.0),
        ("Dark Horse", "Usagi Yojimbo", "Usagi Yojimbo #1 (1996, Stan Sakai, Mirage original 1st print)", "Modern Key", "grail", 800.0),
        ("Archie", "Archie", "Archie #1 (2015, Mark Waid/Fiona Staples, New Riverdale)", "Modern Key", "mid", 30.0),
        ("Valiant", "Harbinger", "Harbinger #1 (1992, Jim Shooter, with coupon)", "Modern Key", "high", 150.0),
        ("First Comics", "Nexus", "Nexus #1 (1983, Mike Baron/Steve Rude, Capital edition)", "Modern Key", "high", 100.0),
        ("Eclipse", "DNAgents", "DNAgents #1 (1983, Mark Evanier/Will Meugniot)", "Modern Key", "mid", 20.0),

        # --- DC Silver Age (+8) ---
        ("DC", "The Flash", "The Flash #105 (1959, 1st Silver Age Flash solo title)", "Silver Age Key", "grail", 8000.0),
        ("DC", "Green Lantern", "Green Lantern #1 (1960, 1st Silver Age GL solo title)", "Silver Age Key", "grail", 12000.0),
        ("DC", "Justice League of America", "Justice League of America #1 (1960, 1st JLA solo title)", "Silver Age Key", "grail", 10000.0),
        ("DC", "The Atom", "Showcase #34 (1961, 1st Silver Age Atom)", "Silver Age Key", "grail", 5000.0),
        ("DC", "Hawkman", "The Brave and the Bold #34 (1961, 1st Silver Age Hawkman)", "Silver Age Key", "grail", 4000.0),
        ("DC", "Teen Titans", "The Brave and the Bold #54 (1964, 1st Teen Titans)", "Silver Age Key", "grail", 6000.0),
        ("DC", "Aquaman", "Aquaman #1 (1962, 1st Silver Age Aquaman solo)", "Silver Age Key", "grail", 7000.0),
        ("DC", "Metal Men", "Showcase #37 (1962, 1st Metal Men)", "Silver Age Key", "grail", 3000.0),

        # --- Marvel Bronze Age Keys (+8) ---
        ("Marvel", "Werewolf by Night", "Werewolf by Night #32 (1975, 1st Moon Knight)", "Bronze Age Key", "grail", 15000.0),
        ("Marvel", "Marvel Spotlight", "Marvel Spotlight #5 (1972, 1st Ghost Rider Johnny Blaze)", "Bronze Age Key", "grail", 8000.0),
        ("Marvel", "Hero for Hire", "Hero for Hire #1 (1972, 1st Luke Cage)", "Bronze Age Key", "grail", 5000.0),
        ("Marvel", "Marvel Premiere", "Marvel Premiere #15 (1974, 1st Iron Fist)", "Bronze Age Key", "grail", 4000.0),
        ("Marvel", "The Eternals", "Eternals #1 (1976, Jack Kirby, 1st Eternals)", "Bronze Age Key", "grail", 2000.0),
        ("Marvel", "Ms. Marvel", "Ms. Marvel #1 (1977, 1st Carol Danvers as Ms. Marvel)", "Bronze Age Key", "grail", 3000.0),
        ("Marvel", "Nova", "Nova #1 (1976, 1st Richard Rider Nova)", "Bronze Age Key", "grail", 1500.0),
        ("Marvel", "What If?", "What If? #10 (1978, 1st Jane Foster as Thor)", "Bronze Age Key", "high", 400.0),

        # --- Modern Spec Keys (+8) ---
        ("DC", "Batman", "Batman #89 (2020, 1st Punchline cameo)", "Modern Key", "high", 150.0),
        ("DC", "Batman", "Batman #92 (2020, 1st Punchline full appearance)", "Modern Key", "high", 100.0),
        ("Marvel", "Ultimate Fallout", "Ultimate Fallout #4 (2011, 1st Miles Morales)", "Modern Key", "grail", 3000.0),
        ("Marvel", "Spider-Man", "Miles Morales: Spider-Man #1 (2018, 1st solo ongoing)", "Modern Key", "mid", 50.0),
        ("Marvel", "Edge of Spider-Verse", "Edge of Spider-Verse #2 (2014, 1st Spider-Gwen)", "Modern Key", "grail", 600.0),
        ("DC", "Harley Quinn", "Batman Adventures #12 (1993, 1st Harley Quinn in comics)", "Modern Key", "grail", 5000.0),
        ("Marvel", "Moon Girl", "Moon Girl and Devil Dinosaur #1 (2015, 1st Lunella Lafayette)", "Modern Key", "mid", 80.0),
        ("Marvel", "Ironheart", "Invincible Iron Man #7 (2017, 1st Riri Williams as Ironheart)", "Modern Key", "mid", 60.0),

        # --- CGC Graded Slabs (+5) ---
        ("DC", "Batman", "Batman #89 CGC 9.8 (2020, 1st Punchline cameo)", "CGC 9.8", "grail", 600.0),
        ("Marvel", "Ultimate Fallout", "Ultimate Fallout #4 CGC 9.8 (2011, 1st Miles Morales, Djurdjevic variant)", "CGC 9.8", "grail", 12000.0),
        ("Marvel", "Edge of Spider-Verse", "Edge of Spider-Verse #2 CGC 9.8 (2014, 1st Spider-Gwen)", "CGC 9.8", "grail", 2500.0),
        ("DC", "Harley Quinn", "Batman Adventures #12 CGC 9.8 (1993, 1st Harley Quinn)", "CGC 9.8", "grail", 20000.0),
        ("Image", "Paper Girls", "Paper Girls #1 CGC 9.8 (2015, BKV/Cliff Chiang)", "CGC 9.8", "grail", 500.0),

        # === ROUND 9 — 90 new items to reach 700+ ===

        # --- Marvel Key Issues — Amazing Spider-Man (+10) ---
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #14 (1964, 1st Green Goblin)", "Silver Age Key", "grail", 20000.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #194 (1979, 1st Black Cat)", "Bronze Age Key", "grail", 2000.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #238 (1983, 1st Hobgoblin)", "Modern Key", "grail", 1500.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #361 (1992, 1st Carnage full)", "Modern Key", "high", 400.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #344 (1991, 1st Cletus Kasady)", "Modern Key", "high", 200.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #529 (2006, 1st Iron Spider suit)", "Modern Key", "mid", 80.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #569 (2008, 1st Anti-Venom)", "Modern Key", "mid", 60.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #798 (2018, 1st Red Goblin)", "Modern Key", "mid", 40.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #4 (2014, 1st Silk/Cindy Moon)", "Modern Key", "high", 150.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man #9 (2014, 1st Spider-UK)", "Modern Key", "mid", 30.0),

        # --- Marvel Key Issues — X-Men First Appearances (+10) ---
        ("Marvel", "X-Men", "X-Men #4 (1964, 1st Brotherhood of Evil Mutants, 1st Scarlet Witch, 1st Quicksilver)", "Silver Age Key", "grail", 15000.0),
        ("Marvel", "X-Men", "X-Men #12 (1965, 1st Juggernaut)", "Silver Age Key", "grail", 8000.0),
        ("Marvel", "X-Men", "X-Men #14 (1965, 1st Sentinels)", "Silver Age Key", "grail", 5000.0),
        ("Marvel", "X-Men", "Giant-Size X-Men #1 (1975, New X-Men team, Storm, Colossus, Nightcrawler)", "Bronze Age Key", "grail", 20000.0),
        ("Marvel", "X-Men", "X-Men #101 (1976, 1st Phoenix)", "Bronze Age Key", "grail", 5000.0),
        ("Marvel", "X-Men", "X-Men #120 (1979, 1st Alpha Flight)", "Bronze Age Key", "high", 400.0),
        ("Marvel", "X-Men", "X-Men #130 (1980, 1st Dazzler)", "Bronze Age Key", "high", 300.0),
        ("Marvel", "X-Men", "X-Men #141 (1981, Days of Future Past Part 1)", "Bronze Age Key", "grail", 2000.0),
        ("Marvel", "X-Men", "New Mutants #87 (1990, 1st Cable)", "Modern Key", "high", 400.0),
        ("Marvel", "X-Men", "New Mutants #98 (1991, 1st Deadpool)", "Modern Key", "grail", 3000.0),

        # --- DC Key Issues — Batman (+8) ---
        ("DC", "Batman", "Batman #232 (1971, 1st Ra's al Ghul)", "Bronze Age Key", "grail", 8000.0),
        ("DC", "Batman", "Batman #251 (1973, Joker's Five-Way Revenge, Neal Adams)", "Bronze Age Key", "grail", 3000.0),
        ("DC", "Batman", "Batman #357 (1983, 1st Jason Todd/Killer Croc)", "Modern Key", "high", 300.0),
        ("DC", "Batman", "Batman #386 (1985, 1st Black Mask)", "Modern Key", "high", 200.0),
        ("DC", "Batman", "Batman #497 (1993, Bane breaks Batman's back)", "Modern Key", "high", 150.0),
        ("DC", "Batman", "Batman #608 (2002, Hush Part 1, Jim Lee cover)", "Modern Key", "mid", 80.0),
        ("DC", "Batman", "Batman #655 (2006, 1st Damian Wayne)", "Modern Key", "high", 300.0),
        ("DC", "Batman", "Batman #1 (New 52, 2011, Scott Snyder/Greg Capullo)", "Modern Key", "mid", 80.0),

        # --- DC Key Issues — Detective Comics (+6) ---
        ("DC", "Detective Comics", "Detective Comics #359 (1967, 1st Batgirl/Barbara Gordon)", "Silver Age Key", "grail", 10000.0),
        ("DC", "Detective Comics", "Detective Comics #400 (1970, 1st Man-Bat)", "Bronze Age Key", "grail", 2000.0),
        ("DC", "Detective Comics", "Detective Comics #411 (1971, 1st Talia al Ghul)", "Bronze Age Key", "grail", 3000.0),
        ("DC", "Detective Comics", "Detective Comics #474 (1977, 1st modern Deadshot)", "Bronze Age Key", "high", 500.0),
        ("DC", "Detective Comics", "Detective Comics #880 (2011, Jock iconic cover)", "Modern Key", "high", 200.0),
        ("DC", "Detective Comics", "Detective Comics #1000 (2019, milestone issue, multiple covers)", "Modern Key", "mid", 30.0),

        # --- Image Comics Firsts — Saga & Invincible (+8) ---
        ("Image", "Saga", "Saga #2 (2012, Brian K. Vaughan, 1st print)", "Modern Key", "mid", 60.0),
        ("Image", "Saga", "Saga #12 (2013, Prince Robot IV cover)", "Modern Key", "mid", 30.0),
        ("Image", "Saga", "Saga #54 (2023, Final Issue)", "Modern Key", "mid", 40.0),
        ("Image", "Invincible", "Invincible #48 (2008, 1st Conquest)", "Modern Key", "high", 150.0),
        ("Image", "Invincible", "Invincible #110 (2014, controversial issue)", "Modern Key", "mid", 50.0),
        ("Image", "Invincible", "Invincible #144 (2018, Final Issue)", "Modern Key", "mid", 60.0),
        ("Image", "Invincible", "Invincible Returns #1 (2010, Kirkman/Ottley)", "Modern Key", "mid", 30.0),
        ("Image", "Fire Power", "Fire Power #1 (2020, Robert Kirkman)", "Modern Key", "mid", 20.0),

        # --- Indie Keys — Bone, Usagi Yojimbo, Others (+8) ---
        ("Cartoon Books", "Bone", "Bone #2 (1991, Jeff Smith, 1st print)", "Modern Key", "high", 200.0),
        ("Cartoon Books", "Bone", "Bone #1 (1991, Jeff Smith, 2nd print)", "First Print", "mid", 80.0),
        ("Fantagraphics", "Usagi Yojimbo", "Usagi Yojimbo #1 (1987, Stan Sakai, Fantagraphics)", "Modern Key", "high", 250.0),
        ("Dark Horse", "Usagi Yojimbo", "Usagi Yojimbo #1 (1996, Dark Horse vol 3, Stan Sakai)", "Modern Key", "mid", 60.0),
        ("IDW", "Usagi Yojimbo", "Usagi Yojimbo #1 (2019, IDW vol 4, Stan Sakai)", "Modern Key", "mid", 25.0),
        ("Valiant", "X-O Manowar", "X-O Manowar #1 (1992, Jim Shooter/Barry Windsor-Smith)", "Modern Key", "mid", 50.0),
        ("Valiant", "Bloodshot", "Bloodshot #1 (1993, Don Perlin, with coupon)", "Modern Key", "mid", 40.0),
        ("Antarctic Press", "Ninja High School", "Ninja High School #1 (1986, Ben Dunn, B&W)", "Modern Key", "mid", 30.0),

        # --- Variant Covers by Major Artists (+10) ---
        ("Marvel", "Amazing Spider-Man", "ASM #1 (2022, Peach Momoko 1:100 Virgin Variant)", "Variant Cover", "grail", 500.0),
        ("DC", "Batman", "Batman #50 (2018, Jim Lee 1:100 Virgin Variant)", "Variant Cover", "high", 200.0),
        ("Marvel", "Venom", "Venom #1 (2018, Mark Bagley 1:200 Virgin Variant)", "Variant Cover", "grail", 400.0),
        ("Marvel", "Thor", "Thor #6 (2020, Artgerm 1:100 Virgin Variant, Black Winter)", "Variant Cover", "high", 300.0),
        ("Marvel", "X-Men", "X-Men #1 (2019, Artgerm 1:500 Virgin Variant)", "Variant Cover", "grail", 600.0),
        ("DC", "Wonder Woman", "Wonder Woman #750 (2020, Artgerm 1:100 Virgin Variant)", "Variant Cover", "high", 150.0),
        ("Marvel", "Miles Morales: Spider-Man", "Miles Morales #1 (2022, Peach Momoko 1:50 Variant)", "Variant Cover", "high", 120.0),
        ("Marvel", "Fantastic Four", "Fantastic Four #1 (2018, Alex Ross 1:100 Virgin Variant)", "Variant Cover", "high", 200.0),
        ("DC", "Superman", "Action Comics #1000 (2018, Jim Lee 1:100 Tour Virgin Variant)", "Variant Cover", "grail", 500.0),
        ("Marvel", "Spider-Man", "Amazing Spider-Man #55 (2021, Patrick Gleason Webhead 2nd print)", "Variant Cover", "mid", 40.0),

        # --- CGC-Notable Books (+8) ---
        ("Marvel", "Hulk", "Incredible Hulk #181 (1974, 1st Wolverine full) CGC 9.8", "CGC 9.8", "grail", 150000.0),
        ("Marvel", "Iron Man", "Tales of Suspense #39 (1963, 1st Iron Man) CGC 9.4", "CGC 9.6", "grail", 200000.0),
        ("DC", "Superman", "Action Comics #252 (1959, 1st Supergirl) CGC 9.2", "CGC 9.6", "grail", 80000.0),
        ("Marvel", "Daredevil", "Daredevil #168 (1981, 1st Elektra) CGC 9.8", "CGC 9.8", "grail", 5000.0),
        ("Marvel", "Wolverine", "Wolverine Limited Series #1 (1982, Frank Miller) CGC 9.8", "CGC 9.8", "grail", 3000.0),
        ("DC", "Swamp Thing", "Saga of the Swamp Thing #37 (1985, 1st John Constantine) CGC 9.8", "CGC 9.8", "grail", 8000.0),
        ("Marvel", "New Mutants", "New Mutants #98 (1991, 1st Deadpool) CGC 9.8", "CGC 9.8", "grail", 10000.0),
        ("Image", "Spawn", "Spawn #300 (2019, J. Scott Campbell cover) CGC 9.8", "CGC 9.8", "grail", 200.0),

        # --- 2024-2025 First Appearances (+10) ---
        ("Marvel", "Ultimate Spider-Man", "Ultimate Spider-Man #1 (2024, Jonathan Hickman, 1st print)", "Modern Key", "mid", 50.0),
        ("DC", "Absolute Batman", "Absolute Batman #1 (2024, Scott Snyder, 1st print)", "Modern Key", "high", 100.0),
        ("DC", "Absolute Superman", "Absolute Superman #1 (2024, Jason Aaron, 1st print)", "Modern Key", "mid", 60.0),
        ("DC", "Absolute Wonder Woman", "Absolute Wonder Woman #1 (2024, Kelly Thompson, 1st print)", "Modern Key", "mid", 40.0),
        ("Marvel", "Ultimate X-Men", "Ultimate X-Men #1 (2024, Peach Momoko, 1st print)", "Modern Key", "mid", 50.0),
        ("Marvel", "Ultimate Black Panther", "Ultimate Black Panther #1 (2024, Bryan Hill, 1st print)", "Modern Key", "mid", 30.0),
        ("Skybound", "Transformers", "Transformers #7 (2024, 1st Energon Universe Megatron)", "Modern Key", "mid", 40.0),
        ("Image", "Rook: Exodus", "Rook: Exodus #1 (2024, Geoff Johns/Gary Frank)", "Modern Key", "mid", 25.0),
        ("Marvel", "One World Under Doom", "One World Under Doom #1 (2025, Ryan North)", "Modern Key", "mid", 20.0),
        ("DC", "All In Special", "DC All In Special #1 (2024, Darkseid event)", "Modern Key", "mid", 20.0),

        # --- Omnibus & Absolute Editions (+12) ---
        ("Marvel", "Uncanny X-Men", "Uncanny X-Men Omnibus Vol 1 (Claremont/Cockrum/Byrne, DM variant)", "Omnibus", "high", 150.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man Omnibus Vol 1 (Lee/Ditko, DM variant)", "Omnibus", "high", 125.0),
        ("Marvel", "Fantastic Four", "Fantastic Four Omnibus Vol 1 (Lee/Kirby, DM variant)", "Omnibus", "high", 130.0),
        ("DC", "Sandman", "Absolute Sandman Vol 1 (Neil Gaiman)", "Absolute Edition", "high", 100.0),
        ("DC", "Batman", "Absolute Dark Knight (Frank Miller, HC)", "Absolute Edition", "high", 80.0),
        ("DC", "Watchmen", "Absolute Watchmen (Alan Moore/Dave Gibbons)", "Absolute Edition", "high", 100.0),
        ("DC", "Superman", "All-Star Superman Absolute Edition", "Absolute Edition", "high", 70.0),
        ("Marvel", "Avengers", "Avengers by Jonathan Hickman Omnibus Vol 1 (DM variant)", "Omnibus", "high", 150.0),
        ("Marvel", "Daredevil", "Daredevil by Frank Miller Omnibus Companion (DM variant)", "Omnibus", "high", 125.0),
        ("DC", "Batman", "Batman by Grant Morrison Omnibus Vol 1", "Omnibus", "high", 100.0),
        ("Image", "Invincible", "Invincible Compendium Vol 1 (2011, Robert Kirkman)", "First Print", "mid", 60.0),
        ("Image", "Saga", "Saga Compendium Vol 1 (2019, Brian K. Vaughan)", "First Print", "mid", 50.0),
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


def _expanded_variant_covers_graded_modern() -> list[dict]:
    """~120 new items: variant covers of key issues, CGC/CBCS graded tiers,
    signature series, modern keys (2015-2025), and independent/Image keys."""
    comics: list[tuple[str, str, str, str, str, float]] = [
        # ── 54. ASM #300 Variant Covers & Grades ────────────────────────────
        ("Marvel", "Amazing Spider-Man", "ASM #300 (1st Venom, 1988) Newsstand Edition", "Variant Cover", "grail", 3500.0),
        ("Marvel", "Amazing Spider-Man", "ASM #300 (1st Venom, 1988) Direct Edition", "Modern Key", "grail", 2200.0),
        ("Marvel", "Amazing Spider-Man", "ASM #300 (1st Venom) CGC 9.6", "CGC 9.6", "grail", 4000.0),
        ("Marvel", "Amazing Spider-Man", "ASM #300 (1st Venom) CGC 9.4", "CGC 9.4", "grail", 3200.0),
        ("Marvel", "Amazing Spider-Man", "ASM #300 (1st Venom) CGC 9.2", "CGC 9.2", "grail", 2800.0),
        ("Marvel", "Amazing Spider-Man", "ASM #300 (1st Venom) CGC 9.0", "CGC 9.0", "grail", 2400.0),
        ("Marvel", "Amazing Spider-Man", "ASM #300 (1st Venom) CGC 8.0", "CGC 8.0", "grail", 1800.0),
        ("Marvel", "Amazing Spider-Man", "ASM #300 (1st Venom) CGC 6.0", "CGC 6.0", "grail", 1000.0),

        # ── 55. Batman #1 (New 52) Variant Covers ───────────────────────────
        ("DC", "Batman", "Batman #1 (New 52, 2011) Jim Lee 1:200 Variant", "Variant Cover", "grail", 800.0),
        ("DC", "Batman", "Batman #1 (New 52, 2011) Blank Sketch Variant", "Variant Cover", "high", 250.0),
        ("DC", "Batman", "Batman #1 (New 52, 2011) CGC 9.8", "CGC 9.8", "grail", 600.0),

        # ── 56. X-Men #1 (1991 Jim Lee) All 5 Covers + Gatefold ────────────
        ("Marvel", "X-Men", "X-Men #1 (1991, Jim Lee) Cover A (Wolverine/Cyclops)", "Modern Key", "high", 120.0),
        ("Marvel", "X-Men", "X-Men #1 (1991, Jim Lee) Cover B (Beast/Storm)", "Modern Key", "high", 100.0),
        ("Marvel", "X-Men", "X-Men #1 (1991, Jim Lee) Cover C (Rogue/Psylocke)", "Modern Key", "high", 100.0),
        ("Marvel", "X-Men", "X-Men #1 (1991, Jim Lee) Cover D (Magneto)", "Modern Key", "high", 100.0),
        ("Marvel", "X-Men", "X-Men #1 (1991, Jim Lee) Cover E (Professor X/Magneto)", "Modern Key", "mid", 80.0),
        ("Marvel", "X-Men", "X-Men #1 (1991, Jim Lee) Gatefold Variant (all 4 covers combined)", "Variant Cover", "high", 250.0),
        ("Marvel", "X-Men", "X-Men #1 (1991, Jim Lee) CGC 9.8 (Cover A)", "CGC 9.8", "high", 400.0),

        # ── 57. Spawn #1 Variants & Grades ──────────────────────────────────
        ("Image", "Spawn", "Spawn #1 (1992) Newsstand Edition", "Variant Cover", "high", 250.0),
        ("Image", "Spawn", "Spawn #1 (1992) CGC 9.8 (Newsstand)", "CGC 9.8", "grail", 1200.0),

        # ── 58. Ultimate Fallout #4 Variants ─────────────────────────────────
        ("Marvel", "Ultimate Fallout", "Ultimate Fallout #4 (1st Miles Morales) Djurdjevic Variant", "Variant Cover", "grail", 1500.0),
        ("Marvel", "Ultimate Fallout", "Ultimate Fallout #4 (1st Miles Morales) 2nd Print", "Modern Key", "high", 300.0),

        # ── 59. Edge of Spider-Verse #2 Variants ────────────────────────────
        ("Marvel", "Edge of Spider-Verse", "Edge of Spider-Verse #2 (1st Spider-Gwen) Greg Land Variant", "Variant Cover", "grail", 600.0),
        ("Marvel", "Edge of Spider-Verse", "Edge of Spider-Verse #2 (1st Spider-Gwen) CGC 9.6", "CGC 9.6", "grail", 1000.0),

        # ── 60. Venom: Lethal Protector #1 Variants ─────────────────────────
        ("Marvel", "Venom", "Venom: Lethal Protector #1 (1993) Gold Edition", "Variant Cover", "grail", 500.0),
        ("Marvel", "Venom", "Venom: Lethal Protector #1 (1993) Black Error Variant", "Variant Cover", "grail", 800.0),
        ("Marvel", "Venom", "Venom: Lethal Protector #1 (1993) Newsstand Edition", "Variant Cover", "high", 350.0),
        ("Marvel", "Venom", "Venom: Lethal Protector #1 (1993) CGC 9.6", "CGC 9.6", "high", 180.0),

        # ── 61. Walking Dead #1 CGC Tiers ────────────────────────────────────
        ("Image", "Walking Dead", "Walking Dead #1 (2003) CGC 9.6", "CGC 9.6", "grail", 5000.0),
        ("Image", "Walking Dead", "Walking Dead #1 (2003) CGC 9.4", "CGC 9.4", "grail", 3500.0),

        # ── 62. Amazing Fantasy #15 CGC Grade Tiers ─────────────────────────
        ("Marvel", "Amazing Fantasy", "Amazing Fantasy #15 (1st Spider-Man) CGC 6.0", "CGC 6.0", "grail", 50000.0),
        ("Marvel", "Amazing Fantasy", "Amazing Fantasy #15 (1st Spider-Man) CGC 4.0", "CGC 4.0", "grail", 25000.0),
        ("Marvel", "Amazing Fantasy", "Amazing Fantasy #15 (1st Spider-Man) CGC 2.0", "CGC 2.0", "grail", 12000.0),

        # ── 63. Incredible Hulk #181 CGC Grade Tiers ─────────────────────────
        ("Marvel", "Incredible Hulk", "Incredible Hulk #181 (1st Wolverine) CGC 9.4", "CGC 9.4", "grail", 30000.0),
        ("Marvel", "Incredible Hulk", "Incredible Hulk #181 (1st Wolverine) CGC 8.0", "CGC 8.0", "grail", 12000.0),
        ("Marvel", "Incredible Hulk", "Incredible Hulk #181 (1st Wolverine) CGC 6.0", "CGC 6.0", "grail", 6000.0),

        # ── 64. Giant-Size X-Men #1 CGC Grade Tiers ─────────────────────────
        ("Marvel", "Giant-Size X-Men", "Giant-Size X-Men #1 (1975) CGC 9.8", "CGC 9.8", "grail", 100000.0),
        ("Marvel", "Giant-Size X-Men", "Giant-Size X-Men #1 (1975) CGC 9.4", "CGC 9.4", "grail", 25000.0),
        ("Marvel", "Giant-Size X-Men", "Giant-Size X-Men #1 (1975) CGC 8.0", "CGC 8.0", "grail", 8000.0),

        # ── 65. ASM #129 CGC Grade Tiers ─────────────────────────────────────
        ("Marvel", "Amazing Spider-Man", "ASM #129 (1st Punisher) CGC 9.8", "CGC 9.8", "grail", 50000.0),
        ("Marvel", "Amazing Spider-Man", "ASM #129 (1st Punisher) CGC 9.4", "CGC 9.4", "grail", 15000.0),
        ("Marvel", "Amazing Spider-Man", "ASM #129 (1st Punisher) CGC 8.0", "CGC 8.0", "grail", 4000.0),
        ("Marvel", "Amazing Spider-Man", "ASM #129 (1st Punisher) CGC 6.0", "CGC 6.0", "grail", 2000.0),

        # ── 66. New Mutants #98 CGC Grade Tiers ──────────────────────────────
        ("Marvel", "New Mutants", "New Mutants #98 (1st Deadpool) CGC 9.6", "CGC 9.6", "grail", 5000.0),
        ("Marvel", "New Mutants", "New Mutants #98 (1st Deadpool) CGC 9.4", "CGC 9.4", "grail", 3000.0),
        ("Marvel", "New Mutants", "New Mutants #98 (1st Deadpool) CGC 9.0", "CGC 9.0", "grail", 2000.0),

        # ── 67. Signature Series — Stan Lee ──────────────────────────────────
        ("Marvel", "Amazing Spider-Man", "ASM #300 Signed by Stan Lee CGC SS 9.6", "Signed", "grail", 12000.0),
        ("Marvel", "Incredible Hulk", "Incredible Hulk #181 Signed by Stan Lee CGC SS 8.0", "Signed", "grail", 40000.0),
        ("Marvel", "Amazing Spider-Man", "ASM #129 Signed by Stan Lee CGC SS 9.0", "Signed", "grail", 25000.0),
        ("Marvel", "X-Men", "X-Men #1 (1991, Jim Lee) Signed by Stan Lee CGC SS 9.8", "Signed", "grail", 2000.0),
        ("Marvel", "Fantastic Four", "Fantastic Four #1 (1961) Signed by Stan Lee CGC SS 3.0", "Signed", "grail", 80000.0),

        # ── 68. Signature Series — Todd McFarlane ────────────────────────────
        ("Image", "Spawn", "Spawn #1 Signed by Todd McFarlane (raw, witnessed)", "Signed", "grail", 500.0),
        ("Marvel", "Amazing Spider-Man", "ASM #298 Signed by Todd McFarlane CGC SS 9.8", "Signed", "grail", 1500.0),
        ("Marvel", "Amazing Spider-Man", "ASM #299 Signed by Todd McFarlane CGC SS 9.8", "Signed", "grail", 1200.0),

        # ── 69. Signature Series — Jim Lee ───────────────────────────────────
        ("Marvel", "X-Men", "X-Men #1 (1991) Signed by Jim Lee CGC SS 9.8", "Signed", "grail", 1500.0),
        ("DC", "Batman", "Batman #608 (Hush) Signed by Jim Lee CGC SS 9.8", "Signed", "grail", 800.0),
        ("Image", "WildC.A.T.s", "WildC.A.T.s #1 Signed by Jim Lee CGC SS 9.8", "Signed", "high", 300.0),

        # ── 70. Something is Killing the Children #1 Variants ────────────────
        ("BOOM!", "Something is Killing the Children", "SIKTC #1 (2019) Jenny Frison 1:25 Variant", "Variant Cover", "grail", 2000.0),
        ("BOOM!", "Something is Killing the Children", "SIKTC #1 (2019) LCBK (Local Comic Book Day) Variant", "Variant Cover", "grail", 1500.0),
        ("BOOM!", "Something is Killing the Children", "SIKTC #1 (2019) 2nd Print", "Modern Key", "high", 200.0),
        ("BOOM!", "Something is Killing the Children", "SIKTC #1 (2019) CGC 9.6", "CGC 9.6", "grail", 800.0),

        # ── 71. Department of Truth #1 ───────────────────────────────────────
        ("Image", "Department of Truth", "Department of Truth #1 (2020) CGC 9.8", "CGC 9.8", "high", 350.0),

        # ── 72. Ice Cream Man #1 ─────────────────────────────────────────────
        ("Image", "Ice Cream Man", "Ice Cream Man #1 (2018, Cover A, 1st print)", "Modern Key", "high", 180.0),
        ("Image", "Ice Cream Man", "Ice Cream Man #1 (2018) 1:10 Morazzo B&W Variant", "Variant Cover", "high", 400.0),

        # ── 73. Saga #1 Variants & Grades ────────────────────────────────────
        ("Image", "Saga", "Saga #1 (2012) CGC 9.6", "CGC 9.6", "grail", 600.0),

        # ── 74. Paper Girls #1 ───────────────────────────────────────────────
        ("Image", "Paper Girls", "Paper Girls #1 (2015, BKV/Cliff Chiang, Cover A)", "Modern Key", "high", 130.0),
        ("Image", "Paper Girls", "Paper Girls #1 (2015) 1:25 Variant", "Variant Cover", "high", 350.0),

        # ── 75. Immortal Hulk #1 ─────────────────────────────────────────────
        ("Marvel", "Immortal Hulk", "Immortal Hulk #1 (2018, Al Ewing, Cover A)", "Modern Key", "mid", 70.0),
        ("Marvel", "Immortal Hulk", "Immortal Hulk #1 (2018) CGC 9.8", "CGC 9.8", "high", 250.0),

        # ── 76. House of X / Powers of X ─────────────────────────────────────
        ("Marvel", "House of X", "House of X #1 (2019, Hickman, Cover A)", "Modern Key", "mid", 35.0),
        ("Marvel", "House of X", "House of X #2 (2019, Moira reveal)", "Modern Key", "mid", 25.0),
        ("Marvel", "Powers of X", "Powers of X #1 (2019, Hickman, Cover A)", "Modern Key", "mid", 25.0),
        ("Marvel", "House of X", "House of X #1 (2019) CGC 9.8", "CGC 9.8", "high", 120.0),

        # ── 77. Batman #89 & #92 (1st Punchline) ────────────────────────────
        ("DC", "Batman", "Batman #89 (1st Punchline) CGC 9.8", "CGC 9.8", "grail", 500.0),
        ("DC", "Batman", "Batman #92 (1st Punchline full) CGC 9.8", "CGC 9.8", "high", 250.0),
        ("DC", "Batman", "Batman #89 (2020) 2nd Print Variant", "Variant Cover", "mid", 50.0),
        ("DC", "Batman", "Batman #92 (2020) Artgerm Variant", "Variant Cover", "mid", 60.0),

        # ── 78. Strange Academy #1 ──────────────────────────────────────────
        ("Marvel", "Strange Academy", "Strange Academy #1 (2020, Skottie Young, 1st print)", "Modern Key", "mid", 80.0),
        ("Marvel", "Strange Academy", "Strange Academy #1 (2020) 1:25 Opena Variant", "Variant Cover", "high", 200.0),
        ("Marvel", "Strange Academy", "Strange Academy #1 (2020) CGC 9.8", "CGC 9.8", "high", 250.0),

        # ── 79. Miles Morales: Spider-Man #1 (2023) ──────────────────────────
        ("Marvel", "Miles Morales: Spider-Man", "Miles Morales: Spider-Man #1 (2023, Ziglar/Vicentini)", "Modern Key", "mid", 25.0),
        ("Marvel", "Miles Morales: Spider-Man", "Miles Morales: Spider-Man #1 (2023) 1:25 Variant", "Variant Cover", "mid", 80.0),
        ("Marvel", "Miles Morales: Spider-Man", "Miles Morales: Spider-Man #1 (2023) CGC 9.8", "CGC 9.8", "mid", 100.0),

        # ── 80. TMNT #1 (Mirage, 1984) ──────────────────────────────────────
        ("Mirage", "TMNT", "TMNT #1 (1984, Eastman/Laird, 1st print, B&W) CGC 9.4", "CGC 9.4", "grail", 50000.0),
        ("Mirage", "TMNT", "TMNT #1 (1984, Eastman/Laird, 1st print, B&W) CGC 8.0", "CGC 8.0", "grail", 15000.0),
        ("Mirage", "TMNT", "TMNT #1 (1984, Eastman/Laird, 1st print, B&W) CGC 6.0", "CGC 6.0", "grail", 8000.0),
        ("Mirage", "TMNT", "TMNT #1 (1984, 3rd print, color cover)", "First Print", "high", 200.0),

        # ── 81. Invincible #1 Variants & Grades ─────────────────────────────
        ("Image", "Invincible", "Invincible #1 (2003) CGC 9.6", "CGC 9.6", "grail", 4000.0),
        ("Image", "Invincible", "Invincible #1 (2003) CGC 9.4", "CGC 9.4", "grail", 3000.0),

        # ── 82. The Boys #1 ─────────────────────────────────────────────────
        ("Dynamite", "The Boys", "The Boys #1 (2006, Garth Ennis/Darick Robertson, 1st print)", "Modern Key", "high", 350.0),
        ("Dynamite", "The Boys", "The Boys #1 (2006) CGC 9.8", "CGC 9.8", "grail", 1200.0),
        ("Dynamite", "The Boys", "The Boys #2 (2006, 1st Female of the Species)", "Modern Key", "high", 150.0),

        # ── 83. Preacher #1 ─────────────────────────────────────────────────
        ("DC/Vertigo", "Preacher", "Preacher #1 (1995, Garth Ennis/Steve Dillon, 1st print)", "Modern Key", "high", 300.0),
        ("DC/Vertigo", "Preacher", "Preacher #1 (1995) CGC 9.8", "CGC 9.8", "grail", 1000.0),

        # ── 84. Y: The Last Man #1 ──────────────────────────────────────────
        ("DC/Vertigo", "Y: The Last Man", "Y: The Last Man #1 (2002, BKV/Pia Guerra, 1st print)", "Modern Key", "high", 350.0),
        ("DC/Vertigo", "Y: The Last Man", "Y: The Last Man #1 (2002) CGC 9.8", "CGC 9.8", "grail", 1200.0),

        # ── 85. Batman Adventures #12 CGC Grade Tiers ────────────────────────
        ("DC", "Batman Adventures", "Batman Adventures #12 (1st Harley Quinn) CGC 9.6", "CGC 9.6", "grail", 3500.0),
        ("DC", "Batman Adventures", "Batman Adventures #12 (1st Harley Quinn) CGC 9.4", "CGC 9.4", "grail", 2500.0),
        ("DC", "Batman Adventures", "Batman Adventures #12 (1st Harley Quinn) CGC 9.0", "CGC 9.0", "grail", 1800.0),

        # ── 86. ASM #361 (1st Carnage) CGC Tiers ────────────────────────────
        ("Marvel", "Amazing Spider-Man", "ASM #361 (1st Carnage) CGC 9.6", "CGC 9.6", "grail", 600.0),
        ("Marvel", "Amazing Spider-Man", "ASM #361 (1st Carnage) CGC 9.4", "CGC 9.4", "high", 400.0),
        ("Marvel", "Amazing Spider-Man", "ASM #361 (1st Carnage) Newsstand Edition", "Variant Cover", "high", 450.0),

        # ── 87. Hulk #181 Signature Series ───────────────────────────────────
        ("Marvel", "Incredible Hulk", "Incredible Hulk #181 Signed by Herb Trimpe CGC SS 7.0", "Signed", "grail", 20000.0),

        # ── 88. Additional Modern Keys — Affordable Entry ────────────────────
        ("DC", "Batman", "Batman #100 (2020, Joker War finale, Ghost-Maker)", "Modern Key", "mid", 30.0),
        ("Marvel", "Venom", "Venom #3 (2018, 1st full Knull) CGC 9.8", "CGC 9.8", "grail", 600.0),
        ("Marvel", "Thor", "Thor #6 (2020, Black Winter, Donny Cates) CGC 9.8", "CGC 9.8", "high", 200.0),
        ("Marvel", "Carnage", "Carnage #1 (2022, Ram V) CGC 9.8", "CGC 9.8", "mid", 80.0),
        ("Marvel", "Spider-Gwen", "Spider-Gwen #1 (2015, Jason Latour) CGC 9.8", "CGC 9.8", "high", 350.0),
        ("Image", "Geiger", "Geiger #1 (2021, Geoff Johns) CGC 9.8", "CGC 9.8", "mid", 80.0),
        ("Image", "Radiant Black", "Radiant Black #1 (2021, Kyle Higgins) CGC 9.8", "CGC 9.8", "high", 120.0),
        ("Marvel", "Moon Knight", "Moon Knight #1 (2021, Jed MacKay) CGC 9.8", "CGC 9.8", "high", 100.0),

        # ── 89. Edge of Spider-Verse #2 CGC Tiers ───────────────────────────
        ("Marvel", "Edge of Spider-Verse", "Edge of Spider-Verse #2 (1st Spider-Gwen) CGC 9.4", "CGC 9.4", "grail", 700.0),

        # ── 90. Signature Series — Rob Liefeld ──────────────────────────────
        ("Marvel", "New Mutants", "New Mutants #87 Signed by Rob Liefeld CGC SS 9.8", "Signed", "grail", 1500.0),

        # ── 91. Spawn Signature Graded Tiers ─────────────────────────────────
        ("Image", "Spawn", "Spawn #1 Signed by Todd McFarlane CGC SS 9.6", "Signed", "grail", 800.0),
        ("Image", "Spawn", "Spawn #1 CGC 9.6", "CGC 9.6", "high", 250.0),

        # ── 92. Walking Dead #1 Signature ────────────────────────────────────
        ("Image", "Walking Dead", "Walking Dead #1 Signed by Tony Moore CGC SS 9.8", "Signed", "grail", 12000.0),

        # ── 93. SIKTC CGC Grade Tiers ────────────────────────────────────────
        ("BOOM!", "Something is Killing the Children", "SIKTC #1 (2019) CGC 9.4", "CGC 9.4", "grail", 600.0),

        # ── 94. ASM #252 Variants ────────────────────────────────────────────
        ("Marvel", "Amazing Spider-Man", "ASM #252 (1st Black Suit) Newsstand Edition", "Variant Cover", "high", 500.0),
        ("Marvel", "Amazing Spider-Man", "ASM #252 (1st Black Suit) CGC 9.6", "CGC 9.6", "grail", 1500.0),

        # ── 95. Invincible #1 Signed ─────────────────────────────────────────
        ("Image", "Invincible", "Invincible #1 Signed by Ryan Ottley CGC SS 9.8", "Signed", "grail", 9000.0),

        # ── 96. ASM Key Issues — Additional ────────────────────────────────
        ("Marvel", "Amazing Spider-Man", "ASM #129 (1st Punisher) CGC 9.4", "CGC 9.4", "grail", 10000.0),
        ("Marvel", "Amazing Spider-Man", "ASM #129 (1st Punisher) CGC 9.0", "CGC 9.0", "grail", 6000.0),
        ("Marvel", "Amazing Spider-Man", "ASM #129 (1st Punisher) CGC 8.0", "CGC 8.0", "grail", 3500.0),
        ("Marvel", "Amazing Spider-Man", "ASM #129 (1st Punisher) Raw VG", "Bronze Age Key", "grail", 1500.0),
        ("Marvel", "Amazing Spider-Man", "ASM #252 (1st Black Suit) CGC 9.8", "CGC 9.8", "grail", 3500.0),
        ("Marvel", "Amazing Spider-Man", "ASM #252 (1st Black Suit) CGC 9.4", "CGC 9.4", "grail", 800.0),
        ("Marvel", "Amazing Spider-Man", "ASM #300 (1st Venom) CGC 9.6", "CGC 9.6", "grail", 4500.0),
        ("Marvel", "Amazing Spider-Man", "ASM #300 (1st Venom) CGC 9.4", "CGC 9.4", "grail", 3000.0),
        ("Marvel", "Amazing Spider-Man", "ASM #300 (1st Venom) CGC 9.0", "CGC 9.0", "grail", 2000.0),
        ("Marvel", "Amazing Spider-Man", "ASM #300 (1st Venom) Newsstand CGC 9.6", "CGC 9.6", "grail", 6000.0),
        ("Marvel", "Amazing Spider-Man", "ASM #238 (1st Hobgoblin) CGC 9.6", "CGC 9.6", "grail", 1500.0),
        ("Marvel", "Amazing Spider-Man", "ASM #194 (1st Black Cat)", "Bronze Age Key", "grail", 800.0),
        ("Marvel", "Amazing Spider-Man", "ASM #50 (Spider-Man No More)", "Silver Age Key", "grail", 5000.0),
        ("Marvel", "Amazing Spider-Man", "ASM #14 (1st Green Goblin)", "Silver Age Key", "grail", 15000.0),

        # ── 97. Golden Age Keys — Additional ───────────────────────────────
        ("DC", "Detective Comics", "Detective Comics #27 (1st Batman) CGC 2.0", "Golden Age Key", "grail", 400000.0),
        ("DC", "Detective Comics", "Detective Comics #27 (1st Batman) CGC 4.0", "Golden Age Key", "grail", 600000.0),
        ("DC", "Action Comics", "Action Comics #1 (1st Superman) CGC 1.0", "Golden Age Key", "grail", 500000.0),
        ("Timely", "Marvel Comics", "Marvel Comics #1 (1939, 1st Human Torch & Namor)", "Golden Age Key", "grail", 400000.0),
        ("Timely", "Captain America Comics", "Captain America Comics #1 (1941, 1st Cap)", "Golden Age Key", "grail", 300000.0),
        ("Fawcett", "Whiz Comics", "Whiz Comics #2 (1940, 1st Captain Marvel/Shazam)", "Golden Age Key", "grail", 150000.0),

        # ── 98. Modern Keys — Additional ───────────────────────────────────
        ("Image", "Walking Dead", "Walking Dead #1 (2003, 1st Rick Grimes) CGC 9.8", "CGC 9.8", "grail", 8000.0),
        ("Image", "Walking Dead", "Walking Dead #1 (2003, raw) High Grade", "Modern Key", "grail", 2500.0),
        ("Image", "Walking Dead", "Walking Dead #100 (Negan's Lucille) CGC 9.8", "CGC 9.8", "high", 200.0),
        ("Image", "Walking Dead", "Walking Dead #2 (1st Lori & Carl) CGC 9.8", "CGC 9.8", "grail", 1500.0),
        ("Image", "Saga", "Saga #1 (2012, BKV/Fiona Staples, 1st print) CGC 9.8", "CGC 9.8", "grail", 1500.0),
        ("Image", "Saga", "Saga #1 (2012) Raw NM", "Modern Key", "high", 400.0),
        ("Image", "Invincible", "Invincible #1 (2003, Kirkman/Walker) CGC 9.8", "CGC 9.8", "grail", 10000.0),
        ("Image", "Invincible", "Invincible #2 (2003, 1st Atom Eve cameo)", "Modern Key", "high", 200.0),
        ("Image", "Invincible", "Invincible #7 (2003, 1st Atom Eve full)", "Modern Key", "high", 350.0),

        # ── 99. Variant Covers — Todd McFarlane ────────────────────────────
        ("Marvel", "Amazing Spider-Man", "ASM #316 (1st Venom cover, McFarlane) CGC 9.8", "CGC 9.8", "grail", 2000.0),
        ("Marvel", "Amazing Spider-Man", "ASM #316 (1st Venom cover) Raw NM", "Modern Key", "high", 400.0),
        ("Marvel", "Amazing Spider-Man", "ASM #298 (1st McFarlane ASM) CGC 9.8", "CGC 9.8", "high", 400.0),
        ("Marvel", "Amazing Spider-Man", "ASM #299 (Venom cameo, McFarlane) CGC 9.8", "CGC 9.8", "high", 350.0),
        ("Marvel", "Spider-Man", "Spider-Man #1 (1990, McFarlane, Gold Edition)", "Variant Cover", "high", 200.0),
        ("Marvel", "Spider-Man", "Spider-Man #1 (1990, McFarlane, Platinum Edition)", "Variant Cover", "grail", 3000.0),
        ("Marvel", "Spider-Man", "Spider-Man #1 (1990, McFarlane, Silver Edition)", "Variant Cover", "high", 150.0),

        # ── 100. Variant Covers — Jim Lee ──────────────────────────────────
        ("Marvel", "X-Men", "X-Men #1 (1991, Jim Lee, Cover A Wolverine/Cyclops)", "Variant Cover", "mid", 80.0),
        ("Marvel", "X-Men", "X-Men #1 (1991, Jim Lee, Gatefold Cover E)", "Variant Cover", "high", 150.0),
        ("DC", "Batman", "Batman #608 (Hush, Jim Lee) 2nd Print Variant", "Variant Cover", "mid", 50.0),
        ("DC", "Justice League", "Justice League #1 (2011, Jim Lee, Combo Pack)", "Variant Cover", "mid", 40.0),

        # ── 101. Variant Covers — Artgerm ──────────────────────────────────
        ("DC", "Action Comics", "Action Comics #1000 (2018, Artgerm Variant)", "Variant Cover", "high", 120.0),
        ("DC", "Supergirl", "Supergirl #15 (Stanley 'Artgerm' Lau Variant)", "Variant Cover", "mid", 60.0),
        ("DC", "Catwoman", "Catwoman #1 (2018, Artgerm Variant)", "Variant Cover", "mid", 50.0),
        ("DC", "Batgirl", "Batgirl #23 (Artgerm Variant)", "Variant Cover", "mid", 40.0),
        ("Marvel", "Captain Marvel", "Captain Marvel #1 (2019, Artgerm Variant)", "Variant Cover", "mid", 45.0),

        # ── 102. Indie Classics — Bone ─────────────────────────────────────
        ("Cartoon Books", "Bone", "Bone #1 (1991, Jeff Smith, 1st print) CGC 9.8", "CGC 9.8", "grail", 5000.0),
        ("Cartoon Books", "Bone", "Bone #1 (1991, Jeff Smith, 1st print) CGC 9.4", "CGC 9.4", "grail", 3000.0),
        ("Cartoon Books", "Bone", "Bone #1 (1991, Jeff Smith, 1st print) Raw NM", "Modern Key", "grail", 1500.0),
        ("Scholastic", "Bone", "Bone One Volume Complete Edition", "TPB", "mid", 30.0),

        # ── 103. Indie Classics — Hellboy ──────────────────────────────────
        ("Dark Horse", "Hellboy", "Hellboy: Seed of Destruction #1 (1994, 1st Hellboy) CGC 9.8", "CGC 9.8", "grail", 2000.0),
        ("Dark Horse", "Hellboy", "Hellboy: Seed of Destruction #1 (1994, raw NM)", "Modern Key", "grail", 500.0),
        ("Dark Horse", "Hellboy", "Hellboy Library Edition vol 1 (HC)", "Omnibus", "high", 100.0),
        ("Dark Horse", "Hellboy", "Hellboy Omnibus vol 1 (Seed of Destruction)", "Omnibus", "mid", 25.0),

        # ── 104. Indie Classics — TMNT (Additional Grades) ─────────────────
        ("Mirage", "TMNT", "TMNT #1 (1984, 2nd print, white cover)", "First Print", "high", 500.0),
        ("Mirage", "TMNT", "TMNT #4 (1985, 2nd print, Fugitoid)", "First Print", "high", 150.0),
        ("Mirage", "TMNT", "TMNT #1 (1984) CGC 9.8 White Pages", "CGC 9.8", "grail", 100000.0),
        ("Mirage", "TMNT", "TMNT #1 (1984) CGC 9.2", "CGC 9.2", "grail", 25000.0),

        # ── 105. Manga in English — First Prints ──────────────────────────
        ("VIZ", "Akira", "Akira #1 (1988, English color edition, Epic Comics) CGC 9.8", "CGC 9.8", "grail", 1500.0),
        ("VIZ", "Akira", "Akira #1 (1988, Epic Comics) Raw NM", "Modern Key", "high", 300.0),
        ("VIZ", "Dragon Ball Z", "Dragon Ball Z #1 (1998, English, 1st print) CGC 9.8", "CGC 9.8", "high", 400.0),
        ("VIZ", "Naruto", "Naruto vol 1 (English, 1st print, VIZ) Raw NM", "First Print", "high", 100.0),
        ("Tokyopop", "Sailor Moon", "Sailor Moon #1 (1998, English, 1st print) CGC 9.8", "CGC 9.8", "grail", 800.0),

        # ── 106. CGC Slabs — Grade Tier Spreads ───────────────────────────
        ("DC", "Batman", "Batman #1 (1940) CGC 2.0", "CGC 2.0", "grail", 100000.0),
        ("DC", "Batman", "Batman #1 (1940) CGC 4.0", "CGC 4.0", "grail", 250000.0),
        ("DC", "Batman", "Batman #1 (1940) CGC 6.0", "CGC 6.0", "grail", 400000.0),
        ("Marvel", "Amazing Fantasy", "Amazing Fantasy #15 CGC 4.0", "CGC 4.0", "grail", 50000.0),
        ("Marvel", "Amazing Fantasy", "Amazing Fantasy #15 CGC 6.0", "CGC 6.0", "grail", 100000.0),
        ("Marvel", "Amazing Fantasy", "Amazing Fantasy #15 CGC 8.0", "CGC 8.0", "grail", 250000.0),
        ("Marvel", "Incredible Hulk", "Incredible Hulk #181 CGC 9.8", "CGC 9.8", "grail", 50000.0),
        ("Marvel", "Incredible Hulk", "Incredible Hulk #181 CGC 9.4", "CGC 9.4", "grail", 15000.0),
        ("Marvel", "Incredible Hulk", "Incredible Hulk #181 CGC 9.0", "CGC 9.0", "grail", 10000.0),
        ("Marvel", "Incredible Hulk", "Incredible Hulk #181 CGC 6.0", "CGC 6.0", "grail", 4000.0),

        # ── 107. Omnibus & Absolute Editions — Additional ──────────────────
        ("DC", "Batman", "Batman by Grant Morrison Omnibus vol 1", "Omnibus", "high", 100.0),
        ("DC", "Batman", "Absolute Dark Knight Returns (30th Anniversary)", "Absolute Edition", "grail", 500.0),
        ("DC", "Superman", "All-Star Superman Absolute Edition", "Absolute Edition", "high", 150.0),
        ("DC", "Sandman", "Absolute Sandman vol 1 (Gaiman, HC)", "Absolute Edition", "high", 200.0),
        ("DC", "Sandman", "Absolute Sandman vol 2", "Absolute Edition", "high", 200.0),
        ("Marvel", "Uncanny X-Men", "Uncanny X-Men Omnibus vol 1 (Claremont/Byrne)", "Omnibus", "high", 125.0),
        ("Marvel", "Uncanny X-Men", "Uncanny X-Men Omnibus vol 2 (Claremont/Byrne)", "Omnibus", "high", 125.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man Omnibus vol 1 (Lee/Ditko)", "Omnibus", "high", 150.0),
        ("Marvel", "Amazing Spider-Man", "Amazing Spider-Man Omnibus vol 3 (Death of Gwen Stacy)", "Omnibus", "high", 125.0),
        ("Marvel", "Fantastic Four", "Fantastic Four Omnibus vol 1 (Lee/Kirby)", "Omnibus", "high", 125.0),
        ("Image", "Invincible", "Invincible Compendium 1 (issues 1-47)", "Omnibus", "mid", 50.0),
        ("Image", "Invincible", "Invincible Compendium 2 (issues 48-96)", "Omnibus", "mid", 50.0),
        ("Image", "Invincible", "Invincible Compendium 3 (issues 97-144)", "Omnibus", "mid", 50.0),

        # ── 108. Bronze Age Keys — Additional ─────────────────────────────
        ("Marvel", "Avengers", "Avengers #57 (1st Vision)", "Silver Age Key", "grail", 3000.0),
        ("DC", "Batman", "Batman #227 (Neal Adams, classic cover)", "Bronze Age Key", "grail", 2000.0),
        ("Marvel", "Hero for Hire", "Hero for Hire #1 (1st Luke Cage)", "Bronze Age Key", "grail", 2500.0),
        ("Marvel", "X-Men", "Uncanny X-Men #94 (New X-Men begin, 1975)", "Bronze Age Key", "grail", 3000.0),
        ("Marvel", "X-Men", "Uncanny X-Men #101 (1st Phoenix)", "Bronze Age Key", "grail", 2000.0),
        ("Marvel", "X-Men", "Uncanny X-Men #129 (1st Kitty Pryde & Emma Frost)", "Bronze Age Key", "grail", 1500.0),
        ("Marvel", "X-Men", "Uncanny X-Men #141 (Days of Future Past pt 1)", "Bronze Age Key", "grail", 1200.0),
        ("Marvel", "X-Men", "Uncanny X-Men #266 (1st Gambit)", "Modern Key", "grail", 800.0),
        ("Marvel", "Daredevil", "Daredevil #168 (1st Elektra, Frank Miller)", "Bronze Age Key", "grail", 1500.0),

        # ── 109. Convention Exclusives ─────────────────────────────────────
        ("Marvel", "Amazing Spider-Man", "ASM #1 (2022, SDCC Exclusive J. Scott Campbell)", "Convention Exclusive", "high", 250.0),
        ("DC", "Batman", "Batman #1 (2024, SDCC Exclusive Foil Variant)", "Convention Exclusive", "high", 200.0),
        ("Image", "Spawn", "Spawn #1 (2024, SDCC Gold Foil Edition)", "Convention Exclusive", "high", 200.0),
        ("Marvel", "X-Men", "X-Men #1 (2024, NYCC Exclusive Virgin Variant)", "Convention Exclusive", "high", 180.0),

        # ── 110. Independent Publishers — Additional ───────────────────────
        ("Dark Horse", "Sin City", "Sin City: The Hard Goodbye (1991, 1st print) CGC 9.8", "CGC 9.8", "grail", 1000.0),
        ("Valiant", "Harbinger", "Harbinger #1 (1992, w/ coupon) CGC 9.8", "CGC 9.8", "high", 400.0),
        ("Valiant", "X-O Manowar", "X-O Manowar #1 (2012, Venditti, 1st print)", "Modern Key", "mid", 30.0),
        ("BOOM!", "Lumberjanes", "Lumberjanes #1 (2014, 1st print) CGC 9.8", "CGC 9.8", "high", 300.0),
        ("IDW", "TMNT", "TMNT #1 (2011, IDW, Cover A)", "Modern Key", "mid", 50.0),
        ("Dark Horse", "Usagi Yojimbo", "Usagi Yojimbo #1 (1987, Fantagraphics) CGC 9.6", "CGC 9.6", "grail", 800.0),
        ("Vertigo", "Y: The Last Man", "Y: The Last Man Absolute Edition vol 1", "Absolute Edition", "high", 200.0),
        ("Vertigo", "Preacher", "Preacher Absolute Edition vol 1", "Absolute Edition", "high", 200.0),

        # ── 111. Newsstand vs Direct Edition ───────────────────────────────
        ("Marvel", "New Mutants", "New Mutants #98 (1st Deadpool) Newsstand Edition", "Variant Cover", "grail", 2000.0),
        ("Marvel", "Incredible Hulk", "Incredible Hulk #181 Newsstand / Mark Jewelers", "Variant Cover", "grail", 15000.0),

        # ── 112. Copper Age Keys ───────────────────────────────────────────
        ("DC", "Batman", "Batman: The Dark Knight Returns #1 (1986, Frank Miller) CGC 9.8", "CGC 9.8", "grail", 2000.0),
        ("DC", "Batman", "Batman: The Dark Knight Returns #1 (1986) Raw NM", "Modern Key", "high", 400.0),
        ("DC", "Watchmen", "Watchmen #1 (1986, Alan Moore/Dave Gibbons) CGC 9.8", "CGC 9.8", "grail", 1500.0),
        ("DC", "Watchmen", "Watchmen #1 (1986) Raw NM", "Modern Key", "high", 200.0),
        ("DC", "Crisis", "Crisis on Infinite Earths #1 (1985, Marv Wolfman/George Perez)", "Modern Key", "high", 150.0),
        ("Marvel", "Secret Wars", "Marvel Super Heroes Secret Wars #1 (1984) CGC 9.8", "CGC 9.8", "high", 400.0),
        ("Marvel", "Wolverine", "Wolverine #1 (1982, Frank Miller Limited Series) CGC 9.8", "CGC 9.8", "grail", 2500.0),

        # ── 113. Modern Marvel Keys — Additional ──────────────────────────
        ("Marvel", "Amazing Spider-Man", "ASM #569 (1st Anti-Venom) CGC 9.8", "CGC 9.8", "high", 200.0),
        ("Marvel", "Amazing Spider-Man", "ASM #648 (Big Time, new suit) CGC 9.8", "CGC 9.8", "mid", 80.0),
        ("Marvel", "Amazing Spider-Man", "ASM #700 (Death of Spider-Man) CGC 9.8", "CGC 9.8", "high", 200.0),
        ("Marvel", "Venom", "Venom #1 (2018, Donny Cates, Cover A)", "Modern Key", "mid", 50.0),
        ("Marvel", "Venom", "Venom: Lethal Protector #1 (1993) CGC 9.8", "CGC 9.8", "high", 350.0),
        ("Marvel", "Venom", "Venom: Lethal Protector #1 (1993, Gold Edition)", "Variant Cover", "high", 200.0),
        ("Marvel", "Carnage", "Amazing Spider-Man #362 (1st Carnage cover) CGC 9.8", "CGC 9.8", "grail", 600.0),
        ("Marvel", "X-Men", "Uncanny X-Men #244 (1st Jubilee)", "Modern Key", "high", 150.0),
        ("Marvel", "X-Men", "Uncanny X-Men #268 (Jim Lee Captain America cover)", "Modern Key", "high", 200.0),
        ("Marvel", "Daredevil", "Daredevil #1 (2011, Mark Waid) CGC 9.8", "CGC 9.8", "high", 120.0),

        # ── 114. DC Modern Keys — Additional ──────────────────────────────
        ("DC", "Batman", "Batman #497 (Bane Breaks Batman, Knightfall)", "Modern Key", "high", 150.0),
        ("DC", "Batman", "Batman #655 (1st Damian Wayne)", "Modern Key", "high", 200.0),
        ("DC", "Harley Quinn", "Harley Quinn #1 (2000, ongoing series) CGC 9.8", "CGC 9.8", "high", 400.0),
        ("DC", "Flash", "Flash #139 (1st Reverse-Flash, Eobard Thawne)", "Silver Age Key", "grail", 5000.0),
        ("DC", "Batman", "Batman: No Man's Land #1 (1999, earthquake storyline)", "Modern Key", "mid", 30.0),
        ("DC", "Superman", "Death of Superman TPB (sealed, 1992)", "TPB", "mid", 50.0),
        ("DC", "Superman", "Superman #75 (Death of Superman, poly-bagged) CGC 9.8", "CGC 9.8", "high", 150.0),

        # ── 115. Image/Indie — Additional Modern Keys ─────────────────────
        ("Image", "The Wicked + The Divine", "The Wicked + The Divine #1 (2014) CGC 9.8", "CGC 9.8", "high", 200.0),
        ("Image", "Chew", "Chew #1 (2009, John Layman/Rob Guillory) CGC 9.8", "CGC 9.8", "grail", 1500.0),
        ("Image", "East of West", "East of West #1 (2013, Hickman) CGC 9.8", "CGC 9.8", "high", 200.0),
        ("Dark Horse", "Hellboy", "Hellboy in Hell #1 (2012, Mike Mignola) CGC 9.8", "CGC 9.8", "high", 150.0),
        ("IDW", "TMNT", "TMNT: The Last Ronin #1 (2020, 1st print) CGC 9.8", "CGC 9.8", "grail", 500.0),
        ("IDW", "TMNT", "TMNT: The Last Ronin #1 (2020, raw NM)", "Modern Key", "high", 150.0),
        ("BOOM!", "Power Rangers", "Mighty Morphin Power Rangers #0 (2016) CGC 9.8", "CGC 9.8", "high", 200.0),

        # ── 116. Variant Cover Ratios — Modern Speculation ─────────────────
        ("Marvel", "Amazing Spider-Man", "ASM #1 (2022, 1:200 Virgin Variant)", "Variant Cover", "grail", 1000.0),
        ("Marvel", "X-Men", "X-Men #1 (2024, 1:100 Virgin Variant)", "Variant Cover", "grail", 500.0),
        ("DC", "Batman", "Batman #125 (2022, 1:100 Chip Kidd Virgin)", "Variant Cover", "grail", 800.0),
        ("Marvel", "Wolverine", "Wolverine #1 (2020, 1:500 Virgin Variant)", "Variant Cover", "grail", 1500.0),
        ("Marvel", "Thor", "Thor #1 (2020, 1:200 Virgin Variant)", "Variant Cover", "grail", 600.0),

        # ── 117. Additional Affordable Modern Keys ─────────────────────────
        ("Marvel", "Miles Morales", "Miles Morales: Spider-Man #1 (2018, Ahmed/Garron)", "Modern Key", "mid", 40.0),
        ("Marvel", "Black Panther", "Black Panther #1 (2016, Ta-Nehisi Coates) CGC 9.8", "CGC 9.8", "high", 150.0),
        ("Marvel", "X-Men", "X-Men #4 (2020, 1st Horsemen of Apocalypse)", "Modern Key", "mid", 25.0),
        ("Image", "Nocterra", "Nocterra #1 (2021, Scott Snyder) CGC 9.8", "CGC 9.8", "mid", 80.0),
        ("Image", "Undiscovered Country", "Undiscovered Country #1 (2019, Snyder/Soule) CGC 9.8", "CGC 9.8", "high", 100.0),
        ("AfterShock", "Animosity", "Animosity #1 (2016, 1st print) CGC 9.8", "CGC 9.8", "high", 200.0),
        ("BOOM!", "Once & Future", "Once & Future #1 (2019, Gillen) CGC 9.8", "CGC 9.8", "high", 150.0),
        ("DC", "Nightwing", "Nightwing #1 (2016, Tim Seeley/Javier Fernandez)", "Modern Key", "mid", 30.0),

        # ── 118. European Comics — Franco-Belgian (Bande Dessinée) ────────────
        ("Casterman", "Tintin", "Tintin au Pays des Soviets (1st Edition, 1930)", "Golden Age Key", "grail", 50000.0),
        ("Casterman", "Tintin", "Tintin in the Congo (Original 1931, B&W)", "Golden Age Key", "grail", 25000.0),
        ("Casterman", "Tintin", "The Blue Lotus (1st Color Edition, 1946)", "Golden Age Key", "grail", 8000.0),
        ("Casterman", "Tintin", "Tintin and the Picaros (1st Edition, 1976)", "First Print", "high", 200.0),
        ("Casterman", "Tintin", "Tintin in Tibet (1st Edition, 1960)", "First Print", "grail", 3000.0),
        ("Casterman", "Tintin", "The Shooting Star (1st Edition, 1942)", "Golden Age Key", "grail", 5000.0),
        ("Casterman", "Tintin", "Destination Moon / Explorers on the Moon (1st, 1953/54)", "First Print", "grail", 4000.0),
        ("Casterman", "Tintin", "Tintin in America (1st Color, 1945)", "First Print", "grail", 3500.0),
        ("Dargaud", "Asterix", "Asterix the Gaul (1st Edition, 1961)", "Golden Age Key", "grail", 15000.0),
        ("Dargaud", "Asterix", "Asterix and Cleopatra (1st Edition, 1965)", "First Print", "grail", 5000.0),
        ("Dargaud", "Asterix", "Asterix in Britain (1st Edition, 1966)", "First Print", "grail", 2000.0),
        ("Dargaud", "Asterix", "Asterix and the Banquet (1st Edition, 1965)", "First Print", "high", 1500.0),
        ("Dargaud", "Asterix", "Asterix the Gladiator (1st Edition, 1964)", "First Print", "high", 1800.0),
        ("Dupuis", "Spirou", "Spirou #1 (Journal, 1938)", "Golden Age Key", "grail", 20000.0),
        ("Dupuis", "Spirou", "Spirou et Fantasio - QRN sur Bretzelburg (1st, 1966)", "First Print", "grail", 1500.0),
        ("Dupuis", "Lucky Luke", "Lucky Luke - Ma Dalton (1st Edition)", "First Print", "high", 300.0),
        ("Dupuis", "Gaston Lagaffe", "Gaston #1 (1st Edition, 1960)", "Golden Age Key", "grail", 3000.0),
        ("Dargaud", "Blueberry", "Fort Navajo (1st Edition, 1965)", "First Print", "grail", 2500.0),
        ("Dargaud", "Blueberry", "Ballade pour un Cercueil (1st Edition, 1974)", "First Print", "high", 800.0),
        ("Lombard", "Blake and Mortimer", "The Yellow M (1st Edition, 1956)", "Golden Age Key", "grail", 5000.0),
        ("Lombard", "Blake and Mortimer", "The Mystery of the Great Pyramid (1st, 1954)", "Golden Age Key", "grail", 4000.0),
        ("Casterman", "Corto Maltese", "The Ballad of the Salt Sea (1st Edition, 1975)", "First Print", "grail", 2000.0),
        ("Casterman", "Corto Maltese", "Corto Maltese in Siberia (1st Edition, 1979)", "First Print", "high", 800.0),
        ("Dargaud", "Valerian", "Valerian - Bad Dreams (1st Edition)", "First Print", "high", 400.0),
        ("Dargaud", "Valerian", "Valerian - The City of Shifting Waters (1st, 1970)", "First Print", "grail", 1500.0),

        # ── 119. European Comics — British ───────────────────────────────────
        ("IPC/Fleetway", "2000 AD", "2000 AD #2 (1st Judge Dredd, 1977)", "Golden Age Key", "grail", 3000.0),
        ("IPC/Fleetway", "2000 AD", "2000 AD #1 (1977, with free gift)", "Golden Age Key", "grail", 2000.0),
        ("DC/Vertigo", "V for Vendetta", "Warrior #1 (1st V for Vendetta, UK, 1982)", "First Print", "grail", 1500.0),
        ("Quality Comics", "2000 AD", "Judge Dredd: The Complete Case Files Vol 1 (1st Print)", "First Print", "high", 150.0),
        ("Rebellion", "2000 AD", "ABC Warriors: The Mek-Nificent Seven (1st HC)", "First Print", "high", 200.0),
        ("Titan Comics", "Tank Girl", "Tank Girl #1 (1st Print, Deadline Magazine)", "First Print", "grail", 800.0),
        ("Knockabout", "The Adventures of Luther Arkwright", "Luther Arkwright (1st Edition, Bryan Talbot)", "First Print", "high", 300.0),

        # ── 120. European Comics — Italian/Spanish ───────────────────────────
        ("Sergio Bonelli", "Dylan Dog", "Dylan Dog #1 (L'alba dei morti viventi, 1986)", "First Print", "grail", 2500.0),
        ("Sergio Bonelli", "Tex Willer", "Tex #1 (Il Totem Misterioso, 1948)", "Golden Age Key", "grail", 15000.0),
        ("Sergio Bonelli", "Martin Mystere", "Martin Mystere #1 (1982)", "First Print", "high", 500.0),
        ("Sergio Bonelli", "Nathan Never", "Nathan Never #1 (1991)", "First Print", "high", 300.0),
        ("Bruguera", "Mortadelo y Filemon", "Mortadelo y Filemon #1 (1st Edition, 1958)", "Golden Age Key", "grail", 5000.0),
        ("Norma Editorial", "Blacksad", "Blacksad #1 Somewhere Within the Shadows (1st Spanish, 2000)", "First Print", "grail", 1000.0),

        # ── 121. European Comics — Graphic Novels / Modern BD ────────────────
        ("Casterman", "The Incal", "The Incal (1st French Edition, Moebius, 1981)", "First Print", "grail", 3000.0),
        ("Humanoids", "The Incal", "The Incal (1st English Deluxe HC)", "First Print", "high", 200.0),
        ("Les Humanoïdes Associés", "Metabarons", "The Metabarons (1st French, Jodorowsky/Gimenez)", "First Print", "grail", 1500.0),
        ("Delcourt", "Persepolis", "Persepolis (1st French Edition, 2000)", "First Print", "high", 500.0),
        ("Dargaud", "XIII", "XIII #1 - The Day of the Black Sun (1st Edition, 1984)", "First Print", "high", 800.0),
        ("Glenat", "Akira", "Akira (1st French Color Edition, Glenat, 1990)", "First Print", "high", 300.0),
        ("Kana", "Dragon Ball", "Dragon Ball (1st French Edition, Vol 1, 1993)", "First Print", "high", 250.0),
        ("Lombard", "Thorgal", "Thorgal #1 - La Magicienne Trahie (1st, 1980)", "First Print", "grail", 1000.0),
        ("Dargaud", "Largo Winch", "Largo Winch #1 - L'Héritier (1st, 1990)", "First Print", "high", 400.0),
        ("Aire Libre", "Le Chat du Rabbin", "Le Chat du Rabbin #1 (1st, 2002)", "First Print", "high", 200.0),
        ("Dupuis", "Marsupilami", "Marsupilami #1 (1st solo album, 1987)", "First Print", "high", 300.0),
        ("Les Humanoïdes Associés", "The Nikopol Trilogy", "La Foire aux Immortels (1st, Bilal, 1980)", "First Print", "grail", 1500.0),

        # ── Star Trek Comics (10) ───────────────────────────────────────────
        ("Gold Key", "Star Trek", "Star Trek #1 (1967, Gold Key, 1st Star Trek comic)", "Silver Age Key", "grail", 3000.0),
        ("Gold Key", "Star Trek", "Star Trek #2 (1968, Gold Key, early issue)", "Silver Age Key", "high", 400.0),
        ("Marvel", "Star Trek", "Star Trek #1 (1980, Marvel, movie adaptation)", "Bronze Age Key", "high", 150.0),
        ("DC", "Star Trek TNG", "Star Trek: The Next Generation #1 (1989, DC)", "Modern Key", "high", 80.0),
        ("DC", "Star Trek", "Star Trek #1 (1984, DC ongoing series)", "Modern Key", "mid", 50.0),
        ("IDW", "Star Trek", "Star Trek #1 (2011, IDW ongoing, Mike Johnson)", "Modern Key", "mid", 30.0),
        ("IDW", "Star Trek / Legion", "Star Trek / Legion of Super-Heroes #1 (2011, crossover)", "Modern Key", "mid", 25.0),
        ("Malibu", "Star Trek DS9", "Star Trek: Deep Space Nine #1 (1993, Malibu)", "Modern Key", "mid", 40.0),
        ("IDW", "Star Trek", "Star Trek: Countdown #1 (2009, prequel to 2009 film)", "Modern Key", "mid", 35.0),
        ("Wildstorm", "Star Trek TNG", "Star Trek TNG: The Space Between #1 (2007)", "Modern Key", "mid", 20.0),

        # ── 122. Modern Keys — Miles Morales, Kamala Khan, etc. ────────────
        ("Marvel", "Ultimate Comics Spider-Man", "Ultimate Comics Spider-Man #1 (2011, 1st Miles Morales solo)", "Modern Key", "high", 300.0),
        ("Marvel", "Champions", "Champions #1 (2016, 1st Champions team, Ms. Marvel leads)", "Modern Key", "mid", 40.0),
        ("Marvel", "America", "America #1 (2017, 1st America Chavez solo)", "Modern Key", "mid", 30.0),
        ("Marvel", "Young Avengers", "Young Avengers #1 (2005, 1st Kate Bishop, 1st Young Avengers)", "Modern Key", "high", 300.0),
        ("Marvel", "Young Avengers", "Young Avengers #6 (2005, 1st Stature, 1st Patriot full)", "Modern Key", "high", 100.0),
        ("Marvel", "Hawkeye", "Hawkeye #1 (2012, Fraction/Aja run, Kate Bishop co-star)", "Modern Key", "high", 100.0),
        ("Marvel", "Miles Morales: Spider-Man", "Miles Morales: Spider-Man #1 (2018, Saladin Ahmed)", "Modern Key", "mid", 40.0),
        ("Marvel", "Venom", "Venom #3 (2018, 1st Knull, Donny Cates)", "Modern Key", "high", 150.0),
        ("Marvel", "Venom", "Venom #7 (2018, 1st Dylan Brock)", "Modern Key", "high", 80.0),
        ("Marvel", "Amazing Spider-Man", "ASM #798 (2018, 1st Red Goblin)", "Modern Key", "mid", 50.0),
        ("Marvel", "Immortal Hulk", "Immortal Hulk #1 (2018, Al Ewing)", "Modern Key", "high", 100.0),
        ("Marvel", "Amazing Spider-Man", "ASM #194 (1979, 1st Black Cat)", "Bronze Age Key", "grail", 1500.0),
        ("Marvel", "Shang-Chi", "Special Marvel Edition #15 (1973, 1st Shang-Chi)", "Bronze Age Key", "grail", 2000.0),
        ("DC", "Batman", "Batman #567 (1999, 1st Batgirl Cassandra Cain)", "Modern Key", "high", 150.0),
        ("DC", "Nightwing", "Nightwing #1 (1996, 1st solo series, Chuck Dixon)", "Modern Key", "high", 100.0),

        # ── 123. Indie Keys — Saga, Paper Girls, Monstress, Die ────────────
        ("Image", "Paper Girls", "Paper Girls #1 (2015, BKV/Chiang)", "Modern Key", "high", 150.0),
        ("Image", "Monstress", "Monstress #1 (2015, Liu/Takeda)", "Modern Key", "high", 100.0),
        ("Image", "Deadly Class", "Deadly Class #1 (2014, Rick Remender)", "Modern Key", "mid", 50.0),
        ("Image", "Descender", "Descender #1 (2015, Lemire/Nguyen)", "Modern Key", "mid", 40.0),
        ("Image", "East of West", "East of West #1 (2013, Hickman)", "Modern Key", "mid", 50.0),
        ("Image", "Chew", "Chew #1 (2009, John Layman)", "Modern Key", "high", 200.0),
        ("Image", "Saga", "Saga #2 (2012, BKV/Staples)", "Modern Key", "mid", 50.0),
        ("Image", "Saga", "Saga #12 (2013, 1st Prince Robot IV)", "Modern Key", "mid", 40.0),
        ("Image", "Ice Cream Man", "Ice Cream Man #1 (2018, W. Maxwell Prince)", "Modern Key", "high", 100.0),
        ("Image", "Something is Killing the Children", "Something is Killing the Children #1 (2019, Tynion IV)", "Modern Key", "high", 250.0),
        ("BOOM!", "Once & Future", "Once & Future #1 (2019, Gillen)", "Modern Key", "mid", 50.0),
        ("BOOM!", "Lumberjanes", "Lumberjanes #1 (2014, Stevenson)", "Modern Key", "mid", 60.0),
        ("Dark Horse", "Black Hammer", "Black Hammer #1 (2016, Jeff Lemire)", "Modern Key", "mid", 40.0),
        ("Oni Press", "Scott Pilgrim", "Scott Pilgrim Vol 1 (2004, 1st print Bryan Lee O'Malley)", "Modern Key", "high", 200.0),
        ("Image", "Department of Truth", "Department of Truth #1 (2020, Tynion IV)", "Modern Key", "high", 100.0),

        # ── 124. Horror Keys — Creepshow, Tales from the Crypt ─────────────
        ("EC", "Tales from the Crypt", "Tales from the Crypt #20 (1950, 1st horror format issue)", "Golden Age Key", "grail", 8000.0),
        ("EC", "Tales from the Crypt", "Tales from the Crypt #22 (1951, classic Feldstein cover)", "Golden Age Key", "grail", 5000.0),
        ("EC", "Vault of Horror", "Vault of Horror #12 (1950, 1st issue)", "Golden Age Key", "grail", 6000.0),
        ("EC", "Haunt of Fear", "Haunt of Fear #15 (1950, 1st issue)", "Golden Age Key", "grail", 5000.0),
        ("EC", "Weird Science", "Weird Science #12 (1950, classic Feldstein sci-fi)", "Golden Age Key", "grail", 4000.0),
        ("EC", "Creepy", "Creepy #1 (1964, Warren Publishing, 1st issue)", "Silver Age Key", "grail", 3000.0),
        ("Warren", "Eerie", "Eerie #1 (1966, Warren Publishing, 1st issue)", "Silver Age Key", "grail", 1500.0),
        ("Warren", "Vampirella", "Vampirella #1 (1969, Warren, 1st Vampirella)", "Silver Age Key", "grail", 8000.0),
        ("Warren", "Vampirella", "Vampirella #1 CGC 9.8", "CGC 9.8", "grail", 30000.0),
        ("DC", "House of Mystery", "House of Mystery #174 (1968, 1st horror format)", "Silver Age Key", "high", 400.0),
        ("DC", "Swamp Thing", "Swamp Thing #1 (1972, Wrightson, 1st solo series)", "Bronze Age Key", "grail", 2500.0),
        ("Marvel", "Tomb of Dracula", "Tomb of Dracula #10 (1973, 1st Blade)", "Bronze Age Key", "grail", 3000.0),
        ("Marvel", "Marvel Spotlight", "Marvel Spotlight #2 (1972, 1st Werewolf by Night)", "Bronze Age Key", "grail", 1500.0),

        # ── 125. CGC 9.8 Price Points for Key Issues ───────────────────────
        ("Marvel", "Amazing Spider-Man", "ASM #300 CGC 9.8 (1st Venom)", "CGC 9.8", "grail", 5000.0),
        ("Marvel", "New Mutants", "New Mutants #98 CGC 9.8 (1st Deadpool)", "CGC 9.8", "grail", 3500.0),
        ("Marvel", "Amazing Spider-Man", "ASM #129 CGC 9.8 (1st Punisher)", "CGC 9.8", "grail", 25000.0),
        ("Marvel", "Incredible Hulk", "Incredible Hulk #181 CGC 9.8 (1st Wolverine)", "CGC 9.8", "grail", 50000.0),
        ("DC", "Batman Adventures", "Batman Adventures #12 CGC 9.8 (1st Harley)", "CGC 9.8", "grail", 8000.0),
        ("Image", "Walking Dead", "Walking Dead #1 CGC 9.8 (2003)", "CGC 9.8", "grail", 12000.0),
        ("Image", "Spawn", "Spawn #1 CGC 9.8 (1992)", "CGC 9.8", "grail", 800.0),
        ("Marvel", "Amazing Spider-Man", "ASM #361 CGC 9.8 (1st Carnage)", "CGC 9.8", "grail", 800.0),
        ("Marvel", "Edge of Spider-Verse", "Edge of Spider-Verse #2 CGC 9.8 (1st Spider-Gwen)", "CGC 9.8", "grail", 1500.0),
        ("Marvel", "Venom", "Venom: Lethal Protector #1 CGC 9.8 (Black cover, 1993)", "CGC 9.8", "grail", 500.0),
        ("DC", "Batman", "Batman: The Killing Joke CGC 9.8 (1st print)", "CGC 9.8", "grail", 1200.0),
        ("Marvel", "Marvel Super Heroes", "Secret Wars #8 CGC 9.8 (Symbiote)", "CGC 9.8", "grail", 1500.0),
        ("DC", "Batman", "Batman #423 CGC 9.8 (McFarlane cover)", "CGC 9.8", "grail", 1000.0),
        ("Image", "Invincible", "Invincible #1 CGC 9.8", "CGC 9.8", "grail", 10000.0),

        # ── 126. Ratio Variant Covers (1:100, 1:200, 1:500) ───────────────
        ("Marvel", "Amazing Spider-Man", "ASM #1 (2022) 1:100 Momoko Virgin Variant", "Variant Cover", "grail", 500.0),
        ("Marvel", "Amazing Spider-Man", "ASM #1 (2022) 1:200 Peach Momoko Variant", "Variant Cover", "grail", 800.0),
        ("DC", "Batman", "Batman #1 (Rebirth, 2016) 1:500 Jim Lee Foil Variant", "Variant Cover", "grail", 600.0),
        ("DC", "Action Comics", "Action Comics #1000 (2018) 1:100 Jim Lee Virgin", "Variant Cover", "grail", 500.0),
        ("Marvel", "X-Men", "X-Men #1 (2019) 1:100 Hidden Gem Variant", "Variant Cover", "high", 300.0),
        ("Marvel", "Venom", "Venom #1 (2021) 1:200 Virgin Stegman Variant", "Variant Cover", "grail", 600.0),
        ("DC", "Batman", "Batman #100 (2020) 1:100 Jimenez Virgin Variant", "Variant Cover", "high", 250.0),
        ("Marvel", "Thor", "Thor #1 (2020) 1:200 Cates/Klein Virgin Variant", "Variant Cover", "grail", 500.0),
        ("Image", "Spawn", "Spawn #300 (2019) 1:100 Capullo B&W Sketch Variant", "Variant Cover", "grail", 500.0),
        ("DC", "Wonder Woman", "Wonder Woman #1 (2023) 1:100 Jenny Frison Virgin", "Variant Cover", "high", 250.0),
        ("Marvel", "Ultimate Spider-Man", "Ultimate Spider-Man #1 (2024) 1:100 Inhyuk Lee Virgin", "Variant Cover", "high", 300.0),
        ("Marvel", "Deadpool", "Deadpool #1 (2024) 1:200 Skottie Young Virgin", "Variant Cover", "grail", 500.0),

        # ── 127. Manga in English — Berserk, Vagabond, etc. ───────────────
        ("Dark Horse", "Berserk", "Berserk Deluxe Edition Vol 1 (HC, Kentaro Miura)", "Omnibus", "high", 50.0),
        ("Dark Horse", "Berserk", "Berserk Deluxe Edition Vol 2 (HC)", "Omnibus", "mid", 45.0),
        ("Dark Horse", "Berserk", "Berserk Deluxe Edition Vol 3 (HC)", "Omnibus", "mid", 45.0),
        ("Dark Horse", "Berserk", "Berserk Deluxe Edition Vol 4 (HC)", "Omnibus", "mid", 45.0),
        ("Dark Horse", "Berserk", "Berserk Deluxe Edition Vol 13 (HC, final Miura volume)", "Omnibus", "high", 55.0),
        ("VIZ", "Vagabond", "Vagabond VIZBIG Vol 1 (Takehiko Inoue, 3-in-1)", "Omnibus", "high", 30.0),
        ("VIZ", "Vagabond", "Vagabond VIZBIG Vol 12 (final omnibus)", "Omnibus", "high", 40.0),
        ("Kodansha", "Vinland Saga", "Vinland Saga Deluxe HC Vol 1 (Makoto Yukimura)", "Omnibus", "high", 35.0),
        ("Kodansha", "Vinland Saga", "Vinland Saga Deluxe HC Vol 2", "Omnibus", "mid", 30.0),
        ("Kodansha", "Vinland Saga", "Vinland Saga Deluxe HC Vol 3", "Omnibus", "mid", 30.0),
        ("Kodansha", "Attack on Titan", "Attack on Titan Colossal Edition Vol 1 (Hajime Isayama)", "Omnibus", "mid", 35.0),
        ("VIZ", "Akira", "Akira 35th Anniversary Box Set (Katsuhiro Otomo, HC)", "Omnibus", "grail", 200.0),
        ("VIZ", "Akira", "Akira Vol 1 (1st English Graphic Novel Edition, 1988)", "First Print", "grail", 500.0),
        ("VIZ", "Uzumaki", "Uzumaki Deluxe HC (Junji Ito, 2-in-1)", "Omnibus", "high", 30.0),
        ("VIZ", "Monster", "Monster Perfect Edition Vol 1 (Naoki Urasawa)", "Omnibus", "mid", 20.0),
        ("VIZ", "20th Century Boys", "20th Century Boys Perfect Edition Vol 1 (Urasawa)", "Omnibus", "mid", 20.0),
        ("VIZ", "Slam Dunk", "Slam Dunk Vol 1 (English, Takehiko Inoue)", "First Print", "mid", 15.0),
        ("VIZ", "Dragon Ball", "Dragon Ball Complete Box Set (Vols 1-16, Akira Toriyama)", "Omnibus", "high", 120.0),
        ("VIZ", "Naruto", "Naruto Complete Box Set 1 (Vols 1-27)", "Omnibus", "high", 150.0),
        ("VIZ", "One Piece", "One Piece Box Set 1 East Blue (Vols 1-23)", "Omnibus", "high", 120.0),
        ("VIZ", "Chainsaw Man", "Chainsaw Man Box Set (Vols 1-11, Tatsuki Fujimoto)", "Omnibus", "mid", 70.0),
        ("VIZ", "Jujutsu Kaisen", "Jujutsu Kaisen Vol 1 (1st print, English, Gege Akutami)", "First Print", "mid", 20.0),
        ("VIZ", "Spy x Family", "Spy x Family Vol 1 (1st print, English, Tatsuya Endo)", "First Print", "mid", 12.0),
        ("VIZ", "Demon Slayer", "Demon Slayer Complete Box Set (Vols 1-23)", "Omnibus", "high", 140.0),

        # ── 128. CGC Signature Series ──────────────────────────────────────
        ("Marvel", "Amazing Spider-Man", "ASM #300 CGC SS 9.8 (Signed Todd McFarlane)", "CGC 9.8", "grail", 8000.0),
        ("Marvel", "New Mutants", "New Mutants #87 CGC SS 9.8 (Signed Liefeld, 1st Cable)", "CGC 9.8", "grail", 2000.0),
        ("Image", "Spawn", "Spawn #1 CGC SS 9.8 (Signed McFarlane)", "CGC 9.8", "grail", 1500.0),
        ("DC", "Batman", "Batman #1 (New 52) CGC SS 9.8 (Signed Snyder/Capullo)", "CGC 9.8", "grail", 1000.0),
        ("Image", "Walking Dead", "Walking Dead #1 CGC SS 9.8 (Signed Kirkman)", "CGC 9.8", "grail", 15000.0),
        ("Marvel", "Incredible Hulk", "Hulk #181 CGC SS 7.0 (Signed Stan Lee)", "CGC 8.0", "grail", 15000.0),

        # ── 129. Omnibus & Absolute Editions — Most Collected ──────────────
        ("DC", "Batman", "Absolute Batman: The Long Halloween (Loeb/Sale)", "Absolute Edition", "high", 100.0),
        ("DC", "Batman", "Absolute Dark Knight Returns (Frank Miller)", "Absolute Edition", "high", 120.0),
        ("DC", "Batman", "Batman by Grant Morrison Omnibus Vol 1", "Omnibus", "high", 80.0),
        ("Marvel", "Uncanny X-Men", "Uncanny X-Men Omnibus Vol 1 (Claremont/Byrne)", "Omnibus", "high", 100.0),
        ("Marvel", "Uncanny X-Men", "Uncanny X-Men Omnibus Vol 2 (Claremont/Cockrum)", "Omnibus", "high", 90.0),
        ("Marvel", "Amazing Spider-Man", "ASM Omnibus Vol 1 (Lee/Ditko)", "Omnibus", "high", 100.0),
        ("Marvel", "Fantastic Four", "Fantastic Four Omnibus Vol 1 (Lee/Kirby)", "Omnibus", "high", 100.0),
        ("DC", "Crisis on Infinite Earths", "Crisis on Infinite Earths Absolute Edition (Wolfman/Perez)", "Absolute Edition", "high", 150.0),
        ("Marvel", "Immortal Hulk", "Immortal Hulk Omnibus (Al Ewing)", "Omnibus", "high", 100.0),
        ("DC", "Swamp Thing", "Absolute Swamp Thing by Alan Moore Vol 1", "Absolute Edition", "high", 100.0),
        ("DC", "Batman", "Absolute Hush (Batman, Jim Lee)", "Absolute Edition", "high", 80.0),
        ("Marvel", "Daredevil", "Daredevil by Frank Miller Omnibus", "Omnibus", "high", 100.0),
        ("Image", "Invincible", "Invincible Compendium Vol 1 (Kirkman)", "Omnibus", "mid", 50.0),
        ("Image", "Saga", "Saga Compendium Vol 1 (BKV/Staples)", "Omnibus", "mid", 50.0),
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
    elif "CGC 9.4" in issue_type:
        cond = 0.94
    elif "CGC 9.2" in issue_type:
        cond = 0.92
    elif "CGC 9.0" in issue_type:
        cond = 0.90
    elif "CGC 8.0" in issue_type:
        cond = 0.80
    elif "CGC 6.0" in issue_type:
        cond = 0.60
    elif "CGC 4.0" in issue_type:
        cond = 0.40
    elif "CGC 2.0" in issue_type:
        cond = 0.20
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
    elif issue_type.startswith("CGC"):
        edition = 0.90  # CGC slabbed = authenticated first print
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
