"""
Import Manga catalog (focus on out-of-print, collectible volumes/sets).

Layer 1 (Catalog):  Popular & OOP manga series → category_items
Layer 2 (Prices):   Market estimates for OOP volumes → train.jsonl

Sources:
- MyAnimeList API (series metadata)
- Curated OOP manga price data (700+ hand-picked collectible series)
- Can be augmented with MangaDex, AniList later

Curated catalog covers:
- OOP grails (Tokyopop/VIZ/Dark Horse out-of-print singles)
- Horror/seinen OOP (MPD Psycho, Parasyte singles, Junji Ito, etc.)
- Josei/shoujo OOP (Basara, Banana Fish singles, Mars, etc.)
- Modern collector/deluxe editions (Berserk Deluxe, Blade Deluxe, etc.)
- Box sets in print (Demon Slayer, MHA, AoT, etc.)
- Japanese tankobon collector items (first prints, Jump specials)
- Light novels (Overlord, Mushoku Tensei, Re:Zero, etc.)

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
    """Curated out-of-print and collectible manga with price data.

    700+ hand-picked series across categories:
    - OOP grails (Tokyopop/VIZ/Dark Horse out-of-print singles)
    - Additional OOP grails (Tokyopop/ADV/CMX era titles)
    - Horror/seinen OOP
    - Seinen/mature OOP (Nihei, Tezuka, Vertical classics)
    - Josei/shoujo OOP
    - Shoujo/josei OOP classics (Yuu Watase, magical girl, VIZ shoujo)
    - Modern collector/deluxe editions
    - Rare/limited editions (art books, anniversary sets, hardcovers)
    - Box sets in print (complete box sets for major series)
    - Japanese tankobon collector items (first prints, Jump specials)
    - Light novels
    - Modern fan-favorite series (Dandadan, Sakamoto Days, Blue Lock, etc.)
    - Junji Ito horror collection
    - Kodansha rare prints & Vertical manga
    - Additional complete box sets (Bleach, Naruto, One Piece multi-box)
    - First English printings (Dragon Ball, Naruto, Bleach, Death Note, Chainsaw Man)
    - Fullmetal Alchemist Fullmetal Editions (hardcovers)
    - VIZ Signature & mature reader OOP titles
    - Rare artbooks & illustration collections
    - Modern rising series (Kagurabachi, Dandadan, Akane-banashi)
    - Japanese 1st print tankoubon rarities
    - Classic shounen OOP (Gintama, Kinnikuman, Bastard!!)
    - Horror classics OOP (Museum of Terror, Uzumaki singles)
    """

    # (title, publisher, volumes, status, avg_vol_price, complete_set_price, rarity)
    oop_manga = [
        # ── Highly sought after OOP manga (original 42) ─────────────────
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

        # ── More OOP Grails ────────────────────────────────────────────
        ("Rave Master", "Tokyopop", 35, "OOP", 18, 630, "High"),
        ("Fist of the North Star (Singles)", "VIZ", 27, "OOP", 35, 950, "High"),
        ("Initial D", "Tokyopop", 33, "OOP", 20, 660, "High"),
        ("Maison Ikkoku (VIZ Old)", "VIZ", 15, "OOP", 18, 270, "Mid"),
        ("Ranma 1/2 (VIZ Old Singles)", "VIZ", 36, "OOP", 12, 430, "Mid"),
        ("Flame of Recca", "VIZ", 33, "OOP", 10, 330, "Mid"),
        ("GetBackers", "Tokyopop", 39, "OOP", 12, 470, "Mid"),
        ("Shaman King (Singles)", "VIZ", 32, "OOP", 14, 450, "Mid"),
        ("Black Cat", "VIZ", 20, "OOP", 10, 200, "Mid"),
        ("Mar", "VIZ", 15, "OOP", 10, 150, "Mid"),
        ("Air Gear", "Kodansha/Del Rey", 37, "OOP", 15, 555, "Mid"),
        ("Skip Beat (Singles)", "VIZ", 49, "Partial OOP", 8, 390, "Mid"),
        ("Rurouni Kenshin (VizBig)", "VIZ", 9, "Partial OOP", 18, 162, "Mid"),
        ("Yu Yu Hakusho", "VIZ", 19, "OOP", 12, 228, "Mid"),
        ("Inu-Yasha (VIZ Singles)", "VIZ", 56, "OOP", 8, 450, "Mid"),
        ("Hikaru no Go", "VIZ", 23, "OOP", 10, 230, "Mid"),
        ("Prince of Tennis", "VIZ", 42, "OOP", 8, 336, "Mid"),
        ("Zatch Bell", "VIZ", 25, "OOP", 15, 375, "High"),
        ("Cross Game", "VIZ", 8, "OOP", 14, 112, "Mid"),

        # ── Horror / Seinen OOP ────────────────────────────────────────
        ("MPD Psycho", "Dark Horse", 11, "OOP", 30, 330, "High"),
        ("Parasyte (Del Rey Singles)", "Del Rey", 8, "OOP", 35, 280, "High"),
        ("Gyo (Deluxe)", "VIZ", 1, "In Print", 23, 23, "Standard"),
        ("Hideout", "Dark Horse", 1, "OOP", 30, 30, "Mid"),
        ("Junji Ito's Cat Diary", "Kodansha", 1, "In Print", 13, 13, "Standard"),
        ("Drifting Classroom (Perfect)", "VIZ", 3, "In Print", 28, 84, "Standard"),
        ("Drifting Classroom (Singles)", "VIZ", 11, "OOP", 25, 275, "High"),
        ("Franken Fran", "Seven Seas", 8, "OOP", 20, 160, "Mid"),
        ("Kurosagi Corpse Delivery Service", "Dark Horse", 14, "OOP", 18, 252, "Mid"),
        ("Ichi the Killer", "n/a (fan translated)", 10, "OOP", 60, 600, "High"),
        ("Old Boy", "Dark Horse", 8, "OOP", 25, 200, "Mid"),

        # ── Josei / Shoujo OOP ─────────────────────────────────────────
        ("Basara", "VIZ", 27, "OOP", 15, 405, "High"),
        ("Banana Fish (Singles)", "VIZ", 19, "OOP", 18, 340, "High"),
        ("Mars", "Tokyopop", 15, "OOP", 20, 300, "High"),
        ("Hana-Kimi", "VIZ", 23, "OOP", 10, 230, "Mid"),
        ("Boys Over Flowers", "VIZ", 37, "OOP", 8, 296, "Mid"),
        ("Kimi ni Todoke", "VIZ", 30, "Partial OOP", 8, 240, "Mid"),
        ("Fruits Basket (Singles)", "Tokyopop", 23, "OOP", 12, 276, "Mid"),
        ("Please Save My Earth", "VIZ", 21, "OOP", 15, 315, "High"),

        # ── Modern Collector / Deluxe Editions ─────────────────────────
        ("Berserk Deluxe Edition vol 1", "Dark Horse", 1, "In Print", 50, 50, "Standard"),
        ("Berserk Deluxe Edition vol 2", "Dark Horse", 1, "In Print", 50, 50, "Standard"),
        ("Berserk Deluxe Edition vol 3", "Dark Horse", 1, "In Print", 50, 50, "Standard"),
        ("Blade of the Immortal Deluxe", "Dark Horse", 10, "In Print", 50, 500, "Standard"),
        ("Vinland Saga Deluxe", "Kodansha", 7, "In Print", 50, 350, "Standard"),
        ("Uzumaki (3-in-1 Deluxe)", "VIZ", 1, "In Print", 28, 28, "Standard"),
        ("Sensor", "VIZ", 1, "In Print", 16, 16, "Standard"),
        ("Remina", "VIZ", 1, "In Print", 16, 16, "Standard"),
        ("Hellsing Deluxe", "Dark Horse", 3, "In Print", 50, 150, "Standard"),
        ("Trigun Deluxe", "Dark Horse", 2, "In Print", 45, 90, "Standard"),

        # ── Box Sets In Print ──────────────────────────────────────────
        ("Demon Slayer Box Set", "VIZ", 23, "In Print", 9, 200, "Standard"),
        ("My Hero Academia Box Set 1", "VIZ", 20, "In Print", 8, 160, "Standard"),
        ("Attack on Titan Box Set", "Kodansha", 34, "In Print", 8, 270, "Standard"),
        ("Tokyo Ghoul Box Set", "VIZ", 14, "In Print", 10, 140, "Standard"),
        ("Promised Neverland Box Set", "VIZ", 20, "In Print", 8, 160, "Standard"),

        # ── Japanese Tankobon Collector Items ──────────────────────────
        ("Dragon Ball vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 120, 120, "High"),
        ("One Piece vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 200, 200, "High"),
        ("Naruto vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 80, 80, "High"),
        ("Slam Dunk vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 90, 90, "High"),
        ("Weekly Shonen Jump #1-2 1968 (reprint)", "Shueisha", 1, "OOP", 150, 150, "High"),
        ("Akira vol 1 (1st Print JP)", "Kodansha", 1, "OOP", 100, 100, "High"),
        ("JoJo's Bizarre Adventure vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 70, 70, "High"),
        ("Dragon Ball 30th Anniversary Super History Book", "Shueisha", 1, "OOP", 60, 60, "Mid"),

        # ── Light Novels ───────────────────────────────────────────────
        ("Overlord (Light Novel)", "Yen Press", 16, "In Print", 14, 224, "Standard"),
        ("Mushoku Tensei (Light Novel)", "Seven Seas", 26, "In Print", 14, 364, "Standard"),
        ("Re:Zero (Light Novel)", "Yen Press", 35, "In Print", 14, 490, "Standard"),
        ("That Time I Got Reincarnated as a Slime (LN)", "Yen Press", 22, "In Print", 14, 308, "Standard"),
        ("Sword Art Online Progressive (Light Novel)", "Yen Press", 8, "In Print", 14, 112, "Standard"),

        # ── Additional OOP Grails (Tokyopop / ADV / CMX) ─────────────
        ("Love Hina", "Tokyopop", 14, "OOP", 10, 140, "Mid"),
        ("Samurai Deeper Kyo", "Tokyopop", 38, "OOP", 15, 570, "High"),
        ("Tsubasa: Reservoir Chronicle", "Del Rey/Kodansha", 28, "OOP", 10, 280, "Mid"),
        ("xxxHolic", "Del Rey/Kodansha", 19, "OOP", 12, 228, "Mid"),
        ("Negima! Magister Negi Magi", "Del Rey/Kodansha", 38, "OOP", 10, 380, "Mid"),
        ("Chrono Crusade", "ADV Manga", 8, "OOP", 20, 160, "Mid"),
        ("Peach Girl", "Tokyopop", 18, "OOP", 10, 180, "Mid"),
        ("Chobits", "Tokyopop", 8, "OOP", 12, 96, "Mid"),
        ("Angelic Layer", "Tokyopop", 5, "OOP", 15, 75, "Mid"),
        ("Magic Knight Rayearth", "Tokyopop", 6, "OOP", 15, 90, "Mid"),
        ("Cardcaptor Sakura (Tokyopop)", "Tokyopop", 12, "OOP", 12, 144, "Mid"),
        ("Sgt. Frog", "Tokyopop", 28, "OOP", 10, 280, "Mid"),
        ("Yotsuba&!", "ADV/Yen Press", 15, "Partial OOP", 10, 150, "Mid"),
        ("Cromartie High School", "ADV Manga", 17, "OOP", 15, 255, "Mid"),
        ("Excel Saga", "VIZ", 27, "OOP", 12, 324, "Mid"),
        ("Azumanga Daioh", "ADV Manga", 4, "OOP", 15, 60, "Mid"),
        ("Pita-Ten", "Tokyopop", 8, "OOP", 12, 96, "Mid"),
        ("King of Hell", "Tokyopop", 22, "OOP", 10, 220, "Mid"),
        ("Saiyuki", "Tokyopop", 9, "OOP", 14, 126, "Mid"),
        ("Saiyuki Reload", "Tokyopop", 9, "OOP", 14, 126, "Mid"),
        ("Kodocha: Sana's Stage", "Tokyopop", 10, "OOP", 18, 180, "High"),
        ("Gravitation", "Tokyopop", 12, "OOP", 12, 144, "Mid"),
        ("Sensual Phrase", "VIZ", 18, "OOP", 10, 180, "Mid"),
        ("Hot Gimmick", "VIZ", 12, "OOP", 10, 120, "Mid"),
        ("Suikoden III", "Tokyopop", 11, "OOP", 18, 198, "Mid"),
        ("Zombie Powder", "VIZ", 4, "OOP", 14, 56, "Mid"),
        ("Buso Renkin", "VIZ", 10, "OOP", 10, 100, "Mid"),
        ("Whistle!", "VIZ", 24, "OOP", 10, 240, "Mid"),
        ("Yakitate!! Japan", "VIZ", 26, "OOP", 12, 312, "Mid"),
        ("MeruPuri", "VIZ", 4, "OOP", 10, 40, "Mid"),
        ("Reborn!", "VIZ", 16, "OOP", 12, 192, "Mid"),

        # ── Seinen / Mature OOP ───────────────────────────────────────
        ("Blame!", "Tokyopop", 10, "OOP", 30, 300, "High"),
        ("Blame! Master Edition", "Vertical", 6, "In Print", 35, 210, "Standard"),
        ("Knights of Sidonia", "Vertical", 15, "Partial OOP", 13, 195, "Mid"),
        ("Abara", "VIZ", 2, "OOP", 18, 36, "Mid"),
        ("NOiSE", "Tokyopop", 1, "OOP", 40, 40, "High"),
        ("Battle Angel Alita (Singles)", "VIZ", 9, "OOP", 15, 135, "Mid"),
        ("Battle Angel Alita: Last Order", "VIZ", 19, "OOP", 12, 228, "Mid"),
        ("Battle Angel Alita Deluxe", "Kodansha", 5, "In Print", 30, 150, "Standard"),
        ("Sanctuary", "VIZ", 9, "OOP", 25, 225, "High"),
        ("Crying Freeman", "Dark Horse", 5, "OOP", 20, 100, "Mid"),
        ("Path of the Assassin", "Dark Horse", 15, "OOP", 15, 225, "Mid"),
        ("Lady Snowblood", "Dark Horse", 4, "OOP", 18, 72, "Mid"),
        ("Uziga Waita: Mai-chan's Daily Life", "n/a", 1, "OOP", 80, 80, "High"),
        ("Homunculus", "Seven Seas", 15, "In Print", 13, 195, "Standard"),
        ("I Am a Hero", "Dark Horse", 11, "OOP", 20, 220, "Mid"),
        ("Suicide Island", "n/a (fan translated)", 17, "OOP", 40, 680, "High"),
        ("Ikigami: The Ultimate Limit", "VIZ", 10, "OOP", 12, 120, "Mid"),
        ("Arm of Kannon", "Tokyopop", 9, "OOP", 25, 225, "High"),
        ("Phoenix (Hi no Tori)", "VIZ", 12, "OOP", 18, 216, "High"),
        ("Ode to Kirihito", "Vertical", 1, "OOP", 25, 25, "Mid"),
        ("MW", "Vertical", 1, "OOP", 20, 20, "Mid"),
        ("Black Jack", "Vertical", 17, "OOP", 15, 255, "Mid"),
        ("Message to Adolf", "Vertical", 2, "OOP", 20, 40, "Mid"),
        ("Buddha", "Vertical", 8, "OOP", 15, 120, "Mid"),
        ("Dororo", "Vertical", 3, "OOP", 15, 45, "Mid"),

        # ── Shoujo / Josei OOP Classics ───────────────────────────────
        ("Fushigi Yugi (Singles)", "VIZ", 18, "OOP", 10, 180, "Mid"),
        ("Fushigi Yugi VizBig", "VIZ", 6, "Partial OOP", 18, 108, "Mid"),
        ("Ceres: Celestial Legend", "VIZ", 14, "OOP", 10, 140, "Mid"),
        ("Alice 19th", "VIZ", 7, "OOP", 10, 70, "Mid"),
        ("Imadoki!", "VIZ", 5, "OOP", 10, 50, "Mid"),
        ("Absolute Boyfriend", "VIZ", 6, "OOP", 10, 60, "Mid"),
        ("Full Moon O Sagashite", "VIZ", 7, "OOP", 12, 84, "Mid"),
        ("Gentleman's Alliance Cross", "VIZ", 11, "OOP", 10, 110, "Mid"),
        ("Sand Chronicles", "VIZ", 10, "OOP", 10, 100, "Mid"),
        ("Honey and Clover", "VIZ", 10, "OOP", 12, 120, "Mid"),
        ("Loveless", "Tokyopop", 12, "OOP", 12, 144, "Mid"),
        ("Natsume's Book of Friends", "VIZ", 28, "In Print", 10, 280, "Standard"),
        ("Requiem of the Rose King", "VIZ", 17, "In Print", 10, 170, "Standard"),
        ("Revolutionary Girl Utena", "VIZ", 5, "OOP", 20, 100, "High"),
        ("Rose of Versailles", "Udon", 5, "In Print", 40, 200, "Standard"),
        ("Sailor Moon (Tokyopop Singles)", "Tokyopop", 18, "OOP", 15, 270, "High"),
        ("Sailor Moon (Kodansha)", "Kodansha", 12, "OOP", 12, 144, "Mid"),
        ("Sailor Moon Eternal Edition", "Kodansha", 10, "In Print", 20, 200, "Standard"),
        ("Tokyo Mew Mew", "Tokyopop", 7, "OOP", 14, 98, "Mid"),
        ("Kitchen Princess", "Del Rey/Kodansha", 10, "OOP", 12, 120, "Mid"),
        ("Ouran High School Host Club", "VIZ", 18, "In Print", 10, 180, "Standard"),
        ("Vampire Knight", "VIZ", 19, "In Print", 10, 190, "Standard"),
        ("Maid-Sama!", "Tokyopop", 18, "OOP", 12, 216, "Mid"),
        ("Special A", "VIZ", 17, "OOP", 10, 170, "Mid"),

        # ── Rare / Limited Editions ───────────────────────────────────
        ("Akira 35th Anniversary Box Set", "Kodansha", 6, "In Print", 50, 250, "Standard"),
        ("Dragon Ball Super Gallery (Art Book)", "Shueisha", 1, "OOP", 60, 60, "Mid"),
        ("Nausicaa of the Valley of the Wind (Box Set)", "VIZ", 7, "In Print", 15, 100, "Standard"),
        ("Nausicaa Deluxe (Hardcover)", "VIZ", 2, "OOP", 40, 80, "Mid"),
        ("Ghost in the Shell Deluxe", "Kodansha", 1, "In Print", 30, 30, "Standard"),
        ("Ghost in the Shell 1.5", "Kodansha", 1, "OOP", 18, 18, "Mid"),
        ("Appleseed (Deluxe)", "Dark Horse", 4, "OOP", 30, 120, "Mid"),
        ("Berserk Official Guidebook", "Dark Horse", 1, "OOP", 25, 25, "Mid"),
        ("One Piece Color Walk Compendium", "VIZ", 3, "Partial OOP", 35, 105, "Mid"),
        ("JoJo's Bizarre Adventure Part 1 (HC)", "VIZ", 3, "In Print", 20, 60, "Standard"),
        ("JoJo's Bizarre Adventure Part 2 (HC)", "VIZ", 4, "In Print", 20, 80, "Standard"),
        ("JoJo's Bizarre Adventure Part 3 (HC)", "VIZ", 10, "In Print", 20, 200, "Standard"),
        ("JoJo's Bizarre Adventure Part 4 (HC)", "VIZ", 9, "In Print", 20, 180, "Standard"),
        ("All You Need Is Kill", "VIZ", 2, "In Print", 10, 20, "Standard"),
        ("Solanin", "VIZ", 2, "In Print", 13, 26, "Standard"),
        ("A Girl on the Shore", "Vertical", 1, "In Print", 16, 16, "Standard"),
        ("Dead Dead Demon's Dededede Destruction", "VIZ", 12, "In Print", 15, 180, "Standard"),
        ("Downfall", "VIZ", 1, "In Print", 13, 13, "Standard"),

        # ── Additional Japanese Collector Items ───────────────────────
        ("Bleach vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 70, 70, "High"),
        ("Death Note vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 60, 60, "Mid"),
        ("Hunter x Hunter vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 80, 80, "High"),
        ("Jujutsu Kaisen vol 0 (1st Print JP)", "Shueisha", 1, "OOP", 50, 50, "Mid"),
        ("Chainsaw Man vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 45, 45, "Mid"),
        ("Demon Slayer vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 60, 60, "Mid"),
        ("My Hero Academia vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 40, 40, "Mid"),
        ("Spy x Family vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 35, 35, "Mid"),
        ("Attack on Titan vol 1 (1st Print JP)", "Kodansha", 1, "OOP", 70, 70, "High"),
        ("Berserk vol 1 (1st Print JP)", "Hakusensha", 1, "OOP", 150, 150, "High"),
        ("Vagabond vol 1 (1st Print JP)", "Kodansha", 1, "OOP", 100, 100, "High"),

        # ── Additional Light Novels ───────────────────────────────────
        ("Spice and Wolf (Light Novel)", "Yen Press", 22, "In Print", 14, 308, "Standard"),
        ("The Rising of the Shield Hero (LN)", "One Peace Books", 22, "In Print", 14, 308, "Standard"),
        ("Konosuba (Light Novel)", "Yen Press", 17, "In Print", 14, 238, "Standard"),
        ("No Game No Life (Light Novel)", "Yen Press", 11, "Partial OOP", 14, 154, "Mid"),
        ("Monogatari Series (Light Novel)", "Vertical", 22, "In Print", 14, 308, "Standard"),
        ("Haruhi Suzumiya (Light Novel)", "Yen Press", 11, "Partial OOP", 14, 154, "Mid"),
        ("Durarara!! (Light Novel)", "Yen Press", 13, "In Print", 14, 182, "Standard"),
        ("Baccano! (Light Novel)", "Yen Press", 22, "Partial OOP", 14, 308, "Mid"),
        ("Boogiepop (Light Novel)", "Seven Seas", 6, "OOP", 16, 96, "Mid"),
        ("Legend of the Galactic Heroes (Novel)", "VIZ/Haikasoru", 10, "In Print", 16, 160, "Standard"),
        ("86--Eighty-Six (Light Novel)", "Yen Press", 12, "In Print", 14, 168, "Standard"),
        ("Classroom of the Elite (Light Novel)", "Seven Seas", 12, "In Print", 14, 168, "Standard"),
        ("Toradora! (Light Novel)", "Seven Seas", 10, "In Print", 14, 140, "Standard"),
        ("Wandering Witch (Light Novel)", "Yen Press", 9, "In Print", 14, 126, "Standard"),

        # ── Complete Box Sets ────────────────────────────────────────────
        ("Bleach Box Set 1", "VIZ", 21, "In Print", 8, 170, "Standard"),
        ("Bleach Box Set 2", "VIZ", 21, "In Print", 8, 170, "Standard"),
        ("Bleach Box Set 3", "VIZ", 32, "In Print", 8, 260, "Standard"),
        ("Naruto Box Set 1 (Vols 1-27)", "VIZ", 27, "In Print", 7, 190, "Standard"),
        ("Naruto Box Set 2 (Vols 28-48)", "VIZ", 21, "In Print", 7, 150, "Standard"),
        ("Naruto Box Set 3 (Vols 49-72)", "VIZ", 24, "In Print", 7, 170, "Standard"),
        ("Dragon Ball Z Box Set", "VIZ", 26, "In Print", 8, 210, "Standard"),
        ("One Piece Box Set 2 (Vols 24-46)", "VIZ", 23, "In Print", 8, 184, "Standard"),
        ("One Piece Box Set 3 (Vols 47-70)", "VIZ", 24, "In Print", 8, 192, "Standard"),
        ("One Piece Box Set 4 (Vols 71-90)", "VIZ", 20, "In Print", 8, 160, "Standard"),
        ("Hunter x Hunter Box Set", "VIZ", 36, "Partial OOP", 7, 250, "Mid"),
        ("Dragon Ball Super Box Set", "VIZ", 18, "In Print", 10, 180, "Standard"),

        # ── Junji Ito Collection ─────────────────────────────────────────
        ("Tomie (Singles)", "ComicsOne", 3, "OOP", 45, 135, "High"),
        ("Junji Ito's Dissolving Classroom", "Vertical", 1, "In Print", 13, 13, "Standard"),
        ("Fragments of Horror", "VIZ", 1, "In Print", 15, 15, "Standard"),
        ("Venus in the Blind Spot", "VIZ", 1, "In Print", 15, 15, "Standard"),
        ("Smashed", "VIZ", 1, "In Print", 15, 15, "Standard"),
        ("Shiver", "VIZ", 1, "In Print", 15, 15, "Standard"),
        ("No Longer Human (Junji Ito)", "VIZ", 1, "In Print", 23, 23, "Standard"),
        ("Deserter (Junji Ito)", "VIZ", 1, "In Print", 23, 23, "Standard"),
        ("Frankenstein (Junji Ito)", "VIZ", 1, "In Print", 23, 23, "Standard"),

        # ── Modern Fan Favorites ─────────────────────────────────────────
        ("Dandadan", "VIZ", 15, "In Print", 10, 150, "Standard"),
        ("Sakamoto Days", "VIZ", 17, "In Print", 10, 170, "Standard"),
        ("Kaiju No. 8", "VIZ", 12, "In Print", 10, 120, "Standard"),
        ("Hell's Paradise: Jigokuraku", "VIZ", 13, "In Print", 10, 130, "Standard"),
        ("Undead Unluck", "VIZ", 20, "In Print", 10, 200, "Standard"),
        ("Mashle: Magic and Muscles", "VIZ", 18, "In Print", 10, 180, "Standard"),
        ("Blue Lock", "Kodansha", 26, "In Print", 11, 286, "Standard"),
        ("Frieren: Beyond Journey's End", "VIZ", 12, "In Print", 10, 120, "Standard"),
        ("Witch Hat Atelier", "Kodansha", 12, "In Print", 13, 156, "Standard"),
        ("Rooster Fighter", "VIZ", 7, "In Print", 10, 70, "Standard"),
        ("Gachiakuta", "Kodansha", 8, "In Print", 11, 88, "Standard"),
        ("Mission: Yozakura Family", "VIZ", 18, "In Print", 10, 180, "Standard"),

        # ── Collector / Deluxe Editions (Additional) ─────────────────────
        ("Berserk Deluxe Edition vol 4", "Dark Horse", 1, "In Print", 50, 50, "Standard"),
        ("Berserk Deluxe Edition vol 5", "Dark Horse", 1, "In Print", 50, 50, "Standard"),
        ("Berserk Deluxe Edition vol 6", "Dark Horse", 1, "In Print", 50, 50, "Standard"),
        ("Berserk Deluxe Edition vol 7", "Dark Horse", 1, "In Print", 50, 50, "Standard"),
        ("Vagabond VizBig vol 1", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("20th Century Boys Perfect Edition vol 1", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("Akira (Kodansha 35th Ann.) vol 1", "Kodansha", 1, "In Print", 50, 50, "Standard"),
        ("Fist of the North Star (Hardcover)", "VIZ", 4, "In Print", 20, 80, "Standard"),
        ("Gantz (Omnibus)", "Dark Horse", 12, "In Print", 25, 300, "Standard"),
        ("Parasyte (Full Color Collection)", "Kodansha", 8, "In Print", 30, 240, "Standard"),
        ("Claymore Box Set", "VIZ", 27, "In Print", 10, 270, "Standard"),
        ("Slam Dunk (Star Edition JP)", "Shueisha", 20, "In Print", 12, 240, "Standard"),

        # ── Kodansha Rare Prints & Vertical Manga ───────────────────────
        ("Chi's Sweet Home", "Vertical", 12, "OOP", 12, 144, "Mid"),
        ("The Flowers of Evil (Collector's Ed)", "Vertical", 4, "OOP", 25, 100, "Mid"),
        ("Punpun (Asano Inio)", "VIZ", 7, "In Print", 20, 140, "Standard"),
        ("Solanin (Asano Inio)", "VIZ", 2, "In Print", 13, 26, "Standard"),
        ("What a Wonderful World! (Asano Inio)", "VIZ", 2, "OOP", 15, 30, "Mid"),
        ("Inuyashiki", "Kodansha", 10, "Partial OOP", 13, 130, "Mid"),
        ("Ajin: Demi-Human", "Vertical", 17, "In Print", 13, 221, "Standard"),
        ("Land of the Lustrous", "Kodansha", 12, "In Print", 13, 156, "Standard"),
        ("The Ghost in the Shell 2: Man-Machine Interface", "Kodansha", 1, "OOP", 25, 25, "Mid"),
        ("Kodansha's Blue Period", "Kodansha", 14, "In Print", 13, 182, "Standard"),
        ("Kodansha's Fire Force Box Set", "Kodansha", 34, "In Print", 8, 272, "Standard"),
        ("A Silent Voice Box Set", "Kodansha", 7, "In Print", 10, 70, "Standard"),

        # ── More OOP Grails (Tokyopop/VIZ/Dark Horse) ───────────────────
        ("Culdcept", "Tokyopop", 6, "OOP", 30, 180, "High"),
        ("DNA2", "VIZ", 5, "OOP", 20, 100, "Mid"),
        ("Video Girl Ai", "VIZ", 15, "OOP", 12, 180, "Mid"),
        ("Shadow Star Narutaru", "Dark Horse", 12, "OOP", 30, 360, "High"),
        ("MPD Psycho vol 11 (final)", "Dark Horse", 1, "OOP", 80, 80, "High"),
        ("Genshiken (Singles)", "Del Rey/Kodansha", 9, "OOP", 12, 108, "Mid"),
        ("Genshiken Second Season", "Kodansha", 12, "Partial OOP", 12, 144, "Mid"),
        ("Midori Days", "VIZ", 8, "OOP", 12, 96, "Mid"),
        ("School Rumble", "Del Rey/Kodansha", 22, "OOP", 12, 264, "Mid"),
        ("Yotsuba&! vol 1-5 (ADV editions)", "ADV Manga", 5, "OOP", 25, 125, "Mid"),
        ("Planetes (Singles)", "Tokyopop", 5, "OOP", 20, 100, "Mid"),
        ("Remote", "Tokyopop", 10, "OOP", 14, 140, "Mid"),
        ("Beck: Mongolian Chop Squad", "Tokyopop", 34, "OOP", 20, 680, "High"),

        # ── Additional Japanese 1st Print Collector Items ────────────────
        ("One Piece vol 1000 (Shueisha Special)", "Shueisha", 1, "OOP", 40, 40, "Mid"),
        ("Tokyo Ghoul vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 50, 50, "Mid"),
        ("Slam Dunk vol 31 (Final, 1st Print JP)", "Shueisha", 1, "OOP", 80, 80, "High"),
        ("Haikyuu!! vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 35, 35, "Mid"),
        ("One Punch Man vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 35, 35, "Mid"),

        # ── Additional Light Novels ──────────────────────────────────────
        ("Solo Leveling (Light Novel)", "Yen Press", 8, "In Print", 15, 120, "Standard"),
        ("Goblin Slayer (Light Novel)", "Yen Press", 16, "In Print", 14, 224, "Standard"),
        ("The Devil Is a Part-Timer! (LN)", "Yen Press", 21, "In Print", 14, 294, "Standard"),
        ("That Time I Got Reincarnated as a Slime (Trinity)", "Kodansha", 9, "In Print", 11, 99, "Standard"),
        ("Ascendance of a Bookworm (LN)", "J-Novel Club", 33, "In Print", 14, 462, "Standard"),
        ("Mushoku Tensei Roxy Gets Serious", "Seven Seas", 11, "In Print", 13, 143, "Standard"),
        ("Sword Art Online (Light Novel)", "Yen Press", 26, "In Print", 14, 364, "Standard"),
        ("Danmachi (Light Novel)", "Yen Press", 19, "In Print", 14, 266, "Standard"),
        ("Re:Zero EX (Light Novel)", "Yen Press", 5, "In Print", 14, 70, "Standard"),

        # ── Rare / Out-of-Print Shoujo & Josei ──────────────────────────
        ("Red River (Anatolia Story)", "VIZ", 28, "OOP", 15, 420, "High"),
        ("From Far Away", "VIZ", 14, "OOP", 12, 168, "Mid"),
        ("La Corda d'Oro", "VIZ", 17, "OOP", 10, 170, "Mid"),
        ("Otomen", "VIZ", 18, "OOP", 8, 144, "Mid"),
        ("Library Wars: Love & War", "VIZ", 15, "OOP", 10, 150, "Mid"),
        ("Tail of the Moon", "VIZ", 15, "OOP", 10, 150, "Mid"),
        ("High School Debut", "VIZ", 13, "OOP", 10, 130, "Mid"),

        # ── Junji Ito — Complete Collection ────────────────────────────
        ("Junji Ito's Liminal Zone", "VIZ", 1, "In Print", 15, 15, "Standard"),
        ("Lovesickness (Junji Ito)", "VIZ", 1, "In Print", 23, 23, "Standard"),
        ("Junji Ito's Maniac (Art Book)", "VIZ", 1, "In Print", 30, 30, "Standard"),
        ("Black Paradox (Junji Ito)", "VIZ", 1, "In Print", 15, 15, "Standard"),
        ("The Hanging Balloons (Junji Ito)", "VIZ", 1, "In Print", 15, 15, "Standard"),

        # ── Deluxe / Hardcover Editions — Complete ─────────────────────
        ("Berserk Deluxe Edition vol 8", "Dark Horse", 1, "In Print", 50, 50, "Standard"),
        ("Berserk Deluxe Edition vol 9", "Dark Horse", 1, "In Print", 50, 50, "Standard"),
        ("Berserk Deluxe Edition vol 10", "Dark Horse", 1, "In Print", 50, 50, "Standard"),
        ("Berserk Deluxe Edition vol 11", "Dark Horse", 1, "In Print", 50, 50, "Standard"),
        ("Berserk Deluxe Edition vol 12", "Dark Horse", 1, "In Print", 50, 50, "Standard"),
        ("Berserk Deluxe Edition vol 13", "Dark Horse", 1, "In Print", 50, 50, "Standard"),
        ("Berserk Deluxe Edition vol 14", "Dark Horse", 1, "In Print", 50, 50, "Standard"),
        ("Blade of the Immortal Deluxe vol 1", "Dark Horse", 1, "In Print", 50, 50, "Standard"),
        ("Blade of the Immortal Deluxe vol 2", "Dark Horse", 1, "In Print", 50, 50, "Standard"),
        ("Blade of the Immortal Deluxe vol 3", "Dark Horse", 1, "In Print", 50, 50, "Standard"),
        ("Vinland Saga Deluxe vol 1", "Kodansha", 1, "In Print", 50, 50, "Standard"),
        ("Vinland Saga Deluxe vol 2", "Kodansha", 1, "In Print", 50, 50, "Standard"),
        ("Vinland Saga Deluxe vol 3", "Kodansha", 1, "In Print", 50, 50, "Standard"),
        ("Vinland Saga Deluxe vol 4", "Kodansha", 1, "In Print", 50, 50, "Standard"),
        ("Vinland Saga Deluxe vol 5", "Kodansha", 1, "In Print", 50, 50, "Standard"),
        ("Vinland Saga Deluxe vol 6", "Kodansha", 1, "In Print", 50, 50, "Standard"),
        ("Vinland Saga Deluxe vol 7", "Kodansha", 1, "In Print", 50, 50, "Standard"),

        # ── Dragon Ball Complete Box Sets ──────────────────────────────
        ("Dragon Ball Complete Box Set (Vols 1-16)", "VIZ", 16, "In Print", 10, 160, "Standard"),
        ("Dragon Ball Z Complete Box Set (Vols 1-26)", "VIZ", 26, "In Print", 8, 200, "Standard"),
        ("Dragon Ball Super (Complete)", "VIZ", 22, "In Print", 10, 220, "Standard"),

        # ── Attack on Titan Complete ───────────────────────────────────
        ("Attack on Titan Season 1 Box Set", "Kodansha", 4, "In Print", 10, 40, "Standard"),
        ("Attack on Titan Season 2 Box Set", "Kodansha", 4, "In Print", 10, 40, "Standard"),
        ("Attack on Titan Season 3 Part 1 Box Set", "Kodansha", 5, "In Print", 10, 50, "Standard"),
        ("Attack on Titan Season 3 Part 2 Box Set", "Kodansha", 5, "In Print", 10, 50, "Standard"),
        ("Attack on Titan: The Final Season Box Set", "Kodansha", 16, "In Print", 10, 160, "Standard"),
        ("Attack on Titan Colossal Edition vol 1", "Kodansha", 1, "In Print", 35, 35, "Standard"),
        ("Attack on Titan Colossal Edition vol 2", "Kodansha", 1, "In Print", 35, 35, "Standard"),
        ("Attack on Titan Colossal Edition vol 3", "Kodansha", 1, "In Print", 35, 35, "Standard"),
        ("Attack on Titan Colossal Edition vol 4", "Kodansha", 1, "In Print", 35, 35, "Standard"),
        ("Attack on Titan Colossal Edition vol 5", "Kodansha", 1, "In Print", 35, 35, "Standard"),
        ("Attack on Titan Colossal Edition vol 6", "Kodansha", 1, "In Print", 35, 35, "Standard"),

        # ── One Piece Complete Box Sets ────────────────────────────────
        ("One Piece Box Set 1 (East Blue) Vols 1-23", "VIZ", 23, "In Print", 8, 180, "Standard"),

        # ── Naruto Complete ────────────────────────────────────────────
        ("Naruto 3-in-1 Omnibus vol 1", "VIZ", 1, "In Print", 15, 15, "Standard"),
        ("Boruto: Naruto Next Generations", "VIZ", 20, "In Print", 10, 200, "Standard"),

        # ── More OOP Tokyopop/ADV/CMX Era ──────────────────────────────
        ("Ragnarok", "Tokyopop", 10, "OOP", 12, 120, "Mid"),
        ("Priest", "Tokyopop", 16, "OOP", 15, 240, "Mid"),
        ("King of Bandits Jing", "Tokyopop", 7, "OOP", 18, 126, "Mid"),
        ("The Candidate for Goddess", "Tokyopop", 5, "OOP", 15, 75, "Mid"),
        ("Di Gi Charat", "VIZ", 5, "OOP", 12, 60, "Mid"),
        ("Galaxy Angel", "ADV Manga", 5, "OOP", 15, 75, "Mid"),
        ("DNAngel", "Tokyopop", 15, "OOP", 10, 150, "Mid"),
        ("Pretear", "ADV Manga", 4, "OOP", 18, 72, "Mid"),
        ("Confidential Confessions", "Tokyopop", 6, "OOP", 14, 84, "Mid"),
        ("Planet Ladder", "Tokyopop", 7, "OOP", 16, 112, "Mid"),
        ("Corrector Yui", "Tokyopop", 5, "OOP", 15, 75, "Mid"),
        ("Brigadoon", "Tokyopop", 5, "OOP", 18, 90, "Mid"),
        ("Immortal Rain", "Tokyopop", 11, "OOP", 15, 165, "Mid"),
        ("Psychic Academy", "Tokyopop", 11, "OOP", 10, 110, "Mid"),
        ("Kare Kano (His and Her Circumstances)", "Tokyopop", 21, "OOP", 10, 210, "Mid"),
        ("Rising Stars of Manga", "Tokyopop", 10, "OOP", 12, 120, "Mid"),
        ("Cowboy Bebop", "Tokyopop", 3, "OOP", 25, 75, "High"),
        ("Cowboy Bebop: Shooting Star", "Tokyopop", 2, "OOP", 30, 60, "High"),
        ("Tenchi Muyo!", "VIZ", 12, "OOP", 10, 120, "Mid"),
        ("Oh My Goddess!", "Dark Horse", 48, "OOP", 8, 384, "Mid"),
        ("Mahoromatic", "Tokyopop", 8, "OOP", 12, 96, "Mid"),
        ("Steel Angel Kurumi", "ADV Manga", 11, "OOP", 12, 132, "Mid"),
        ("Patlabor", "VIZ", 22, "OOP", 10, 220, "Mid"),
        ("Silent Mobius", "VIZ", 12, "OOP", 12, 144, "Mid"),
        ("3x3 Eyes", "Dark Horse", 8, "OOP", 20, 160, "Mid"),
        ("Shadow Lady", "Dark Horse", 3, "OOP", 25, 75, "Mid"),
        ("Club 9", "Dark Horse", 5, "OOP", 20, 100, "Mid"),
        ("Blade of the Immortal (Fanfare/Ponent Mon)", "Dark Horse", 3, "OOP", 40, 120, "High"),
        ("Lone Wolf & Cub (First Editions)", "First Comics", 6, "OOP", 50, 300, "High"),

        # ── Seinen / Mature Modern Classics ────────────────────────────
        ("Vagabond vol 37 (Final, OOP)", "VIZ", 1, "OOP", 80, 80, "High"),
        ("Monster Perfect Edition vol 1", "VIZ", 1, "In Print", 18, 18, "Standard"),
        ("Btooom!", "Yen Press", 26, "Partial OOP", 13, 338, "Mid"),
        ("Gantz:G", "Dark Horse", 3, "In Print", 13, 39, "Standard"),
        ("Blood on the Tracks", "Vertical", 17, "In Print", 13, 221, "Standard"),
        ("Inside Mari", "Denpa", 9, "In Print", 13, 117, "Standard"),
        ("Happiness", "Kodansha", 10, "In Print", 13, 130, "Standard"),
        ("Trail of Blood", "Vertical", 14, "In Print", 13, 182, "Standard"),
        ("Goodnight Punpun (Asano Inio)", "VIZ", 7, "In Print", 20, 140, "Standard"),

        # ── Light Novels — Complete Collection ─────────────────────────
        ("The Saga of Tanya the Evil (LN)", "Yen Press", 13, "In Print", 14, 182, "Standard"),
        ("The Empty Box and Zeroth Maria (LN)", "Yen Press", 7, "In Print", 14, 98, "Standard"),
        ("Arifureta: From Commonplace to World's Strongest (LN)", "J-Novel Club", 13, "In Print", 14, 182, "Standard"),
        ("Combatants Will Be Dispatched! (LN)", "Yen Press", 7, "In Print", 14, 98, "Standard"),
        ("Death March to the Parallel World Rhapsody (LN)", "Yen Press", 18, "In Print", 14, 252, "Standard"),
        ("The World's Finest Assassin (LN)", "Yen Press", 7, "In Print", 14, 98, "Standard"),
        ("Banished from the Hero's Party (LN)", "Yen Press", 9, "In Print", 14, 126, "Standard"),
        ("Infinite Dendrogram (LN)", "J-Novel Club", 20, "In Print", 14, 280, "Standard"),
        ("Grimgar of Fantasy and Ash (LN)", "J-Novel Club", 18, "In Print", 14, 252, "Standard"),
        ("How a Realist Hero Rebuilt the Kingdom (LN)", "J-Novel Club", 18, "In Print", 14, 252, "Standard"),

        # ── Artbooks & Special Editions ────────────────────────────────
        ("Bleach Art Book: All Colour But The Black", "VIZ", 1, "OOP", 40, 40, "Mid"),
        ("Naruto Art Book: Uzumaki", "VIZ", 1, "OOP", 35, 35, "Mid"),
        ("One Piece Color Walk 1", "VIZ", 1, "Partial OOP", 30, 30, "Mid"),
        ("One Piece Color Walk 2", "VIZ", 1, "Partial OOP", 30, 30, "Mid"),
        ("Attack on Titan Art Book: FLY", "Kodansha", 1, "In Print", 30, 30, "Standard"),
        ("Dragon Ball Z: A Visual History", "VIZ", 1, "In Print", 40, 40, "Standard"),
        ("Vagabond Illustration Collection: Water", "VIZ", 1, "OOP", 50, 50, "High"),
        ("Vagabond Illustration Collection: Sumi", "VIZ", 1, "OOP", 60, 60, "High"),
        ("Berserk Official Guidebook (Reprint)", "Dark Horse", 1, "In Print", 25, 25, "Standard"),
        ("Slam Dunk Illustrations", "Shueisha", 1, "OOP", 60, 60, "High"),
        ("Takehiko Inoue Illustrations", "VIZ", 1, "OOP", 50, 50, "Mid"),
        ("Death Note: How to Read", "VIZ", 1, "In Print", 10, 10, "Standard"),

        # ── Modern Shounen Completions ─────────────────────────────────
        ("Dr. Stone", "VIZ", 26, "In Print", 10, 260, "Standard"),
        ("Black Clover", "VIZ", 35, "In Print", 10, 350, "Standard"),
        ("Fire Force", "Kodansha", 34, "In Print", 11, 374, "Standard"),
        ("Haikyuu!!", "VIZ", 45, "In Print", 10, 450, "Standard"),
        ("Assassination Classroom", "VIZ", 21, "In Print", 10, 210, "Standard"),
        ("Food Wars! Shokugeki no Soma", "VIZ", 36, "In Print", 10, 360, "Standard"),
        ("Magi: The Labyrinth of Magic", "VIZ", 37, "Partial OOP", 10, 370, "Mid"),
        ("World Trigger", "VIZ", 26, "In Print", 10, 260, "Standard"),
        ("The Promised Neverland", "VIZ", 20, "In Print", 10, 200, "Standard"),
        ("Demon Slayer: Kimetsu no Yaiba", "VIZ", 23, "In Print", 10, 230, "Standard"),
        ("Kaguya-sama: Love Is War", "VIZ", 28, "In Print", 10, 280, "Standard"),
        ("Oshi no Ko", "VIZ", 14, "In Print", 10, 140, "Standard"),
        ("Solo Leveling (Manga)", "Yen Press", 8, "In Print", 14, 112, "Standard"),

        # ── Classic Manga — VIZ Signature / Ikki / SigIkki ────────────
        ("Nausicaa of the Valley of the Wind (Deluxe Set)", "VIZ", 2, "In Print", 30, 60, "Standard"),
        ("Tekkonkinkreet: Black & White", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("No. 5", "VIZ", 8, "In Print", 15, 120, "Standard"),
        ("Children of the Sea", "VIZ", 5, "In Print", 15, 75, "Standard"),
        ("Cats of the Louvre", "VIZ", 1, "In Print", 18, 18, "Standard"),
        ("Saturn Apartments", "VIZ", 7, "OOP", 15, 105, "Mid"),
        ("Bokurano: Ours", "VIZ", 11, "OOP", 13, 143, "Mid"),
        ("Gente", "VIZ", 3, "OOP", 13, 39, "Mid"),
        ("Drops of God", "Vertical", 4, "OOP", 15, 60, "Mid"),

        # ── JoJo's Complete Hardcover Line ─────────────────────────────
        ("JoJo's Bizarre Adventure Part 5 (HC)", "VIZ", 9, "In Print", 20, 180, "Standard"),
        ("JoJo's Bizarre Adventure Part 6 (HC)", "VIZ", 6, "In Print", 20, 120, "Standard"),

        # ── More Japanese 1st Print & Import Rarities ──────────────────
        ("Fullmetal Alchemist vol 1 (1st Print JP)", "Square Enix", 1, "OOP", 50, 50, "Mid"),
        ("Doraemon vol 1 (1st Print JP)", "Shogakukan", 1, "OOP", 60, 60, "High"),
        ("Astro Boy vol 1 (1st Print JP)", "Shogakukan", 1, "OOP", 200, 200, "High"),
        ("Nausicaa vol 1 (1st Print JP)", "Tokuma Shoten", 1, "OOP", 80, 80, "High"),
        ("Golgo 13 vol 1 (1st Print JP)", "Shogakukan", 1, "OOP", 70, 70, "High"),
        ("Kochikame vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 100, 100, "High"),

        # ── Shoujo/Josei — More Complete Collections ───────────────────
        ("Cardcaptor Sakura Collector's Edition", "Kodansha", 9, "In Print", 25, 225, "Standard"),
        ("Cardcaptor Sakura: Clear Card", "Kodansha", 14, "In Print", 11, 154, "Standard"),
        ("Fruits Basket Collector's Edition", "Yen Press", 12, "In Print", 22, 264, "Standard"),
        ("Fruits Basket Another", "Yen Press", 3, "In Print", 14, 42, "Standard"),
        ("Yona of the Dawn", "VIZ", 42, "In Print", 10, 420, "Standard"),
        ("The Apothecary Diaries (Manga)", "Square Enix", 12, "In Print", 11, 132, "Standard"),
        ("My Love Story!!", "VIZ", 13, "In Print", 10, 130, "Standard"),
        ("Dawn of the Arcana", "VIZ", 13, "OOP", 10, 130, "Mid"),
        ("Kamisama Kiss", "VIZ", 25, "In Print", 10, 250, "Standard"),
        ("Snow White with the Red Hair", "VIZ", 25, "In Print", 10, 250, "Standard"),
        ("The Saint's Magic Power Is Omnipotent (Manga)", "Seven Seas", 9, "In Print", 13, 117, "Standard"),
        ("Skip and Loafer", "Seven Seas", 9, "In Print", 13, 117, "Standard"),
        ("A Sign of Affection", "Kodansha", 10, "In Print", 11, 110, "Standard"),
        ("Sweat and Soap", "Kodansha", 16, "In Print", 13, 208, "Standard"),
        ("Wotakoi: Love Is Hard for Otaku", "Kodansha", 6, "In Print", 18, 108, "Standard"),

        # ── More OOP Dark Horse / VIZ Grails ───────────────────────────
        ("Blade of Heaven", "Tokyopop", 10, "OOP", 15, 150, "Mid"),
        ("Rebirth", "Tokyopop", 25, "OOP", 10, 250, "Mid"),
        ("Demon Diary", "Tokyopop", 7, "OOP", 14, 98, "Mid"),
        ("Model", "Tokyopop", 7, "OOP", 16, 112, "Mid"),
        ("Witch Class", "Tokyopop", 6, "OOP", 14, 84, "Mid"),
        ("Paradise Kiss Complete Collection", "Vertical", 1, "OOP", 40, 40, "Mid"),
        ("Maoh: Juvenile Remix", "VIZ", 10, "OOP", 12, 120, "Mid"),
        ("Dorohedoro (Singles before Omnibus)", "VIZ", 23, "OOP", 15, 345, "Mid"),
        ("Tokyo Babylon", "Tokyopop", 7, "OOP", 20, 140, "High"),
        ("X/1999", "VIZ", 18, "OOP", 12, 216, "Mid"),
        ("RG Veda", "Tokyopop", 10, "OOP", 14, 140, "Mid"),
        ("Clover", "Tokyopop", 4, "OOP", 18, 72, "Mid"),
        ("Tsubasa Chronicle (Singles)", "Del Rey", 28, "OOP", 10, 280, "Mid"),
        ("Gate 7", "Dark Horse", 4, "OOP", 12, 48, "Mid"),
        ("Legal Drug", "Tokyopop", 3, "OOP", 15, 45, "Mid"),
        ("Nabari no Ou", "Yen Press", 14, "OOP", 12, 168, "Mid"),
        ("07-Ghost", "VIZ", 17, "OOP", 10, 170, "Mid"),
        ("Tegami Bachi: Letter Bee", "VIZ", 20, "OOP", 10, 200, "Mid"),
        ("Muhyo & Roji's Bureau of Supernatural Investigation", "VIZ", 18, "OOP", 10, 180, "Mid"),
        ("Rosario + Vampire", "VIZ", 10, "OOP", 10, 100, "Mid"),
        ("Rosario + Vampire Season II", "VIZ", 14, "OOP", 10, 140, "Mid"),
        ("Ultimo", "VIZ", 12, "OOP", 10, 120, "Mid"),
        ("Psyren", "VIZ", 16, "OOP", 12, 192, "Mid"),
        ("Toriko", "VIZ", 43, "Partial OOP", 8, 344, "Mid"),
        ("Nisekoi: False Love", "VIZ", 25, "In Print", 10, 250, "Standard"),
        ("We Never Learn", "VIZ", 21, "In Print", 10, 210, "Standard"),
        ("The Elusive Samurai", "VIZ", 16, "In Print", 10, 160, "Standard"),
        ("Spy x Family Family Portrait (Novel)", "VIZ", 1, "In Print", 10, 10, "Standard"),

        # ── Additional Complete Box Sets & Omnibus ─────────────────────
        ("Assassination Classroom Box Set", "VIZ", 21, "In Print", 10, 210, "Standard"),
        ("Death Note All-in-One Edition", "VIZ", 1, "In Print", 35, 35, "Standard"),
        ("Haikyuu!! Box Set 1 (Vols 1-10)", "VIZ", 10, "In Print", 10, 100, "Standard"),
        ("My Hero Academia Box Set 2", "VIZ", 20, "In Print", 8, 160, "Standard"),
        ("Tokyo Ghoul:re Box Set", "VIZ", 16, "In Print", 10, 160, "Standard"),
        ("Yu-Gi-Oh! 3-in-1 Omnibus", "VIZ", 13, "In Print", 15, 195, "Standard"),
        ("Bleach 3-in-1 Omnibus vol 1", "VIZ", 1, "In Print", 15, 15, "Standard"),
        ("One Punch Man", "VIZ", 29, "In Print", 10, 290, "Standard"),
        ("Mob Psycho 100", "Dark Horse", 16, "In Print", 12, 192, "Standard"),
        ("Spy x Family (Complete to date)", "VIZ", 14, "In Print", 10, 140, "Standard"),
        ("Vagabond VizBig vol 2", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("Vagabond VizBig vol 3", "VIZ", 1, "In Print", 20, 20, "Standard"),

        # ── Dragon Ball First Printings & Rare Editions ──────────────────
        ("Dragon Ball vol 1 (1st English Print)", "VIZ", 1, "OOP", 80, 80, "High"),
        ("Dragon Ball vol 2 (1st English Print)", "VIZ", 1, "OOP", 45, 45, "Mid"),
        ("Dragon Ball vol 3 (1st English Print)", "VIZ", 1, "OOP", 40, 40, "Mid"),
        ("Dragon Ball Z vol 1 (1st English Print)", "VIZ", 1, "OOP", 60, 60, "High"),
        ("Dragon Ball Z VizBig vol 1", "VIZ", 1, "In Print", 18, 18, "Standard"),
        ("Dragon Ball Full Color: Saiyan Arc", "VIZ", 3, "In Print", 20, 60, "Standard"),
        ("Dragon Ball Full Color: Freeza Arc", "VIZ", 5, "In Print", 20, 100, "Standard"),
        ("Dragon Ball Full Color: Cell Arc", "VIZ", 6, "In Print", 20, 120, "Standard"),
        ("Dragon Ball Full Color: Buu Arc", "VIZ", 6, "In Print", 20, 120, "Standard"),
        ("Dragon Ball Daizenshuu (Complete JP)", "Shueisha", 10, "OOP", 45, 450, "High"),

        # ── Naruto First Printings & Rare Editions ───────────────────────
        ("Naruto vol 1 (1st English Print)", "VIZ", 1, "OOP", 50, 50, "High"),
        ("Naruto vol 72 (Final Volume, 1st Print)", "VIZ", 1, "OOP", 25, 25, "Mid"),
        ("Naruto 3-in-1 Omnibus vol 2", "VIZ", 1, "In Print", 15, 15, "Standard"),
        ("Naruto 3-in-1 Omnibus vol 3", "VIZ", 1, "In Print", 15, 15, "Standard"),
        ("Naruto Illustration Collection: Naruto", "VIZ", 1, "OOP", 40, 40, "Mid"),
        ("Naruto: The Art of Naruto Uzumaki", "VIZ", 1, "OOP", 45, 45, "Mid"),
        ("The Art of Naruto: Road to Ninja", "Shueisha", 1, "OOP", 50, 50, "Mid"),

        # ── Bleach First Printings & Rare Editions ───────────────────────
        ("Bleach vol 1 (1st English Print)", "VIZ", 1, "OOP", 40, 40, "Mid"),
        ("Bleach vol 74 (Final Volume, 1st Print)", "VIZ", 1, "OOP", 20, 20, "Mid"),
        ("Bleach 3-in-1 Omnibus vol 2", "VIZ", 1, "In Print", 15, 15, "Standard"),
        ("Bleach 3-in-1 Omnibus vol 3", "VIZ", 1, "In Print", 15, 15, "Standard"),
        ("Bleach Brave Souls Art Book", "Shueisha", 1, "OOP", 35, 35, "Mid"),
        ("Bleach: Official Character Book SOULs", "VIZ", 1, "OOP", 25, 25, "Mid"),
        ("Bleach: Official Bootleg KaraBuri+", "VIZ", 1, "OOP", 20, 20, "Mid"),
        ("Bleach: Can't Fear Your Own World (LN)", "VIZ", 3, "In Print", 14, 42, "Standard"),

        # ── Death Note Collectible Editions ──────────────────────────────
        ("Death Note vol 1 (1st English Print)", "VIZ", 1, "OOP", 30, 30, "Mid"),
        ("Death Note Black Edition vol 1", "VIZ", 1, "In Print", 15, 15, "Standard"),
        ("Death Note Black Edition vol 2", "VIZ", 1, "In Print", 15, 15, "Standard"),
        ("Death Note Black Edition vol 3", "VIZ", 1, "In Print", 15, 15, "Standard"),
        ("Death Note Black Edition vol 4", "VIZ", 1, "In Print", 15, 15, "Standard"),
        ("Death Note Black Edition vol 5", "VIZ", 1, "In Print", 15, 15, "Standard"),
        ("Death Note Black Edition vol 6", "VIZ", 1, "In Print", 15, 15, "Standard"),
        ("Death Note: Another Note (Novel)", "VIZ", 1, "OOP", 18, 18, "Mid"),
        ("Death Note: L Change the World (Novel)", "VIZ", 1, "OOP", 15, 15, "Mid"),

        # ── Attack on Titan Rare & Collectible ───────────────────────────
        ("Attack on Titan vol 1 (1st English Print)", "Kodansha", 1, "OOP", 35, 35, "Mid"),
        ("Attack on Titan vol 34 (Final, 1st Print)", "Kodansha", 1, "OOP", 20, 20, "Mid"),
        ("Attack on Titan: No Regrets", "Kodansha", 2, "In Print", 11, 22, "Standard"),
        ("Attack on Titan: Before the Fall", "Kodansha", 17, "Partial OOP", 11, 187, "Mid"),
        ("Attack on Titan: Lost Girls", "Kodansha", 2, "In Print", 11, 22, "Standard"),
        ("Attack on Titan Character Encyclopedia", "Kodansha", 1, "In Print", 20, 20, "Standard"),
        ("Attack on Titan Guidebook: Inside & Outside", "Kodansha", 1, "OOP", 18, 18, "Mid"),
        ("Attack on Titan Anthology", "Kodansha", 1, "OOP", 20, 20, "Mid"),

        # ── Chainsaw Man Complete & Collectible ──────────────────────────
        ("Chainsaw Man vol 1 (1st English Print)", "VIZ", 1, "OOP", 30, 30, "Mid"),
        ("Chainsaw Man Box Set 1 (Vols 1-11)", "VIZ", 11, "In Print", 10, 110, "Standard"),
        ("Chainsaw Man: Buddy Stories (Novel)", "VIZ", 1, "In Print", 10, 10, "Standard"),
        ("Tatsuki Fujimoto Before Chainsaw Man", "VIZ", 1, "In Print", 15, 15, "Standard"),
        ("Look Back (Tatsuki Fujimoto)", "VIZ", 1, "In Print", 10, 10, "Standard"),
        ("Goodbye, Eri (Tatsuki Fujimoto)", "VIZ", 1, "In Print", 12, 12, "Standard"),

        # ── Jujutsu Kaisen Complete & Collectible ────────────────────────
        ("Jujutsu Kaisen vol 1 (1st English Print)", "VIZ", 1, "OOP", 25, 25, "Mid"),
        ("Jujutsu Kaisen 0 (Movie Edition)", "VIZ", 1, "In Print", 10, 10, "Standard"),
        ("Jujutsu Kaisen: Thorny Road at Dawn (Novel)", "VIZ", 1, "In Print", 10, 10, "Standard"),
        ("Jujutsu Kaisen Official Fanbook", "VIZ", 1, "In Print", 10, 10, "Standard"),
        ("Jujutsu Kaisen: The Official Guide", "VIZ", 1, "In Print", 15, 15, "Standard"),

        # ── Spy x Family Collectible ─────────────────────────────────────
        ("Spy x Family vol 1 (1st English Print)", "VIZ", 1, "OOP", 22, 22, "Mid"),
        ("Spy x Family: Family Portrait (Art Book)", "Shueisha", 1, "OOP", 35, 35, "Mid"),

        # ── Dandadan & New Wave Shounen ───────────────────────────────────
        ("Dandadan vol 1 (1st English Print)", "VIZ", 1, "OOP", 18, 18, "Mid"),
        ("Sakamoto Days vol 1 (1st English Print)", "VIZ", 1, "OOP", 18, 18, "Mid"),
        ("Nue's Exorcist", "VIZ", 5, "In Print", 10, 50, "Standard"),
        ("Me & Roboco", "VIZ", 10, "In Print", 10, 100, "Standard"),
        ("Cipher Academy", "VIZ", 6, "In Print", 10, 60, "Standard"),
        ("Akane-banashi", "VIZ", 10, "In Print", 10, 100, "Standard"),
        ("Show-ha Shoten!", "VIZ", 5, "In Print", 10, 50, "Standard"),
        ("Kill Blue", "VIZ", 5, "In Print", 10, 50, "Standard"),
        ("Kagurabachi", "VIZ", 5, "In Print", 10, 50, "Standard"),
        ("Ruri Dragon", "VIZ", 3, "In Print", 10, 30, "Standard"),

        # ── Berserk Deluxe & Collector Expansions ────────────────────────
        ("Berserk vol 1 (1st English Print)", "Dark Horse", 1, "OOP", 100, 100, "High"),
        ("Berserk Illustration File (Art Book)", "Dark Horse", 1, "OOP", 60, 60, "High"),
        ("The Art of Berserk Exhibition Catalog", "Hakusensha", 1, "OOP", 120, 120, "High"),
        ("Berserk vol 41 (Final, Miura)", "Dark Horse", 1, "In Print", 15, 15, "Standard"),

        # ── Deluxe / Hardcover Editions — Additional ─────────────────────
        ("Tokyo Ghoul Illustrations: zakki", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("Tokyo Ghoul:re Illustrations: zakki:re", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("Fullmetal Alchemist Fullmetal Edition vol 1", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("Fullmetal Alchemist Fullmetal Edition vol 2", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("Fullmetal Alchemist Fullmetal Edition vol 3", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("Fullmetal Alchemist Fullmetal Edition vol 4", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("Fullmetal Alchemist Fullmetal Edition vol 5", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("Fullmetal Alchemist Fullmetal Edition vol 6", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("Fullmetal Alchemist Fullmetal Edition vol 7", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("Fullmetal Alchemist Fullmetal Edition vol 8", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("Fullmetal Alchemist Fullmetal Edition vol 9", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("Fullmetal Alchemist Fullmetal Edition vol 10", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("Fullmetal Alchemist Fullmetal Edition vol 11", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("Fullmetal Alchemist Fullmetal Edition vol 12", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("Fullmetal Alchemist Fullmetal Edition vol 13", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("Fullmetal Alchemist Fullmetal Edition vol 14", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("Fullmetal Alchemist Fullmetal Edition vol 15", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("Fullmetal Alchemist Fullmetal Edition vol 16", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("Fullmetal Alchemist Fullmetal Edition vol 17", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("Fullmetal Alchemist Fullmetal Edition vol 18", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("Hellsing Deluxe vol 1", "Dark Horse", 1, "In Print", 50, 50, "Standard"),
        ("Hellsing Deluxe vol 2", "Dark Horse", 1, "In Print", 50, 50, "Standard"),
        ("Hellsing Deluxe vol 3", "Dark Horse", 1, "In Print", 50, 50, "Standard"),

        # ── Out-of-Print VIZ Signature Line ──────────────────────────────
        ("IKIGAMI: The Ultimate Limit vol 1-10", "VIZ", 10, "OOP", 12, 120, "Mid"),
        ("Oishinbo A la Carte", "VIZ", 7, "OOP", 15, 105, "Mid"),
        ("Town of Evening Calm, Country of Cherry Blossoms", "Last Gasp", 1, "OOP", 20, 20, "Mid"),
        ("Summit of the Gods", "Fanfare/Ponent Mon", 5, "OOP", 30, 150, "High"),
        ("Taniguchi: A Distant Neighborhood", "Fanfare/Ponent Mon", 2, "OOP", 25, 50, "Mid"),
        ("The Walking Man (Taniguchi)", "Fanfare/Ponent Mon", 1, "OOP", 30, 30, "Mid"),
        ("A Drifting Life (Yoshihiro Tatsumi)", "Drawn & Quarterly", 1, "OOP", 25, 25, "Mid"),
        ("Abandon the Old in Tokyo (Tatsumi)", "Drawn & Quarterly", 1, "OOP", 20, 20, "Mid"),
        ("The Push Man (Yoshihiro Tatsumi)", "Drawn & Quarterly", 1, "OOP", 20, 20, "Mid"),
        ("Good-Bye (Yoshihiro Tatsumi)", "Drawn & Quarterly", 1, "OOP", 20, 20, "Mid"),

        # ── Rare Artbooks & Illustration Collections ─────────────────────
        ("Takeshi Obata: Blanc et Noir", "VIZ", 1, "OOP", 40, 40, "Mid"),
        ("Hiromu Arakawa Art Book (Fullmetal)", "Square Enix", 1, "OOP", 50, 50, "High"),
        ("Yoshitaka Amano: The Illustrated Biography", "Dark Horse", 1, "OOP", 60, 60, "Mid"),
        ("Tsutomu Nihei: Blame! Art Book", "Kodansha", 1, "OOP", 70, 70, "High"),
        ("Kentaro Miura: Berserk Exhibition Artworks", "Hakusensha", 1, "OOP", 90, 90, "High"),
        ("Jojo6251: The World of Hirohiko Araki", "Shueisha", 1, "OOP", 80, 80, "High"),
        ("Hirohiko Araki: Manga in Theory and Practice", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("CLAMP Art Book: South Side", "Tokyopop", 1, "OOP", 35, 35, "Mid"),
        ("CLAMP Art Book: North Side", "Tokyopop", 1, "OOP", 35, 35, "Mid"),
        ("Rumiko Takahashi Art Book: Rin-ne", "VIZ", 1, "OOP", 30, 30, "Mid"),
        ("Eiichiro Oda: One Piece Art Book Color Walk 3", "VIZ", 1, "OOP", 35, 35, "Mid"),
        ("Junji Ito Artbook: Twisted Visions", "VIZ", 1, "In Print", 30, 30, "Standard"),

        # ── Complete Deluxe Box Sets ─────────────────────────────────────
        ("Akira 35th Anniversary HC Box Set (JP)", "Kodansha", 6, "OOP", 80, 480, "High"),
        ("Slam Dunk Complete Collection Box Set (JP)", "Shueisha", 31, "OOP", 12, 370, "High"),
        ("Hunter x Hunter vol 36 (1st Print JP)", "Shueisha", 1, "OOP", 30, 30, "Mid"),
        ("One Piece Treasure Cruise Art Book", "Shueisha", 1, "OOP", 40, 40, "Mid"),
        ("Weekly Shonen Jump 50th Anniversary Golden Issue", "Shueisha", 1, "OOP", 35, 35, "Mid"),
        ("Shonen Jump Alpha #1 (US Digital-to-Print)", "VIZ", 1, "OOP", 25, 25, "Mid"),

        # ── Modern Series — Popular & Rising ─────────────────────────────
        ("Kaiju No. 8 vol 1 (1st Print)", "VIZ", 1, "OOP", 18, 18, "Mid"),
        ("Blue Lock vol 1 (1st English Print)", "Kodansha", 1, "OOP", 20, 20, "Mid"),
        ("Frieren: Beyond Journey's End vol 1 (1st Print)", "VIZ", 1, "OOP", 18, 18, "Mid"),
        ("Hell's Paradise vol 1 (1st Print)", "VIZ", 1, "OOP", 20, 20, "Mid"),
        ("Witch Hat Atelier vol 1 (1st Print)", "Kodansha", 1, "OOP", 18, 18, "Mid"),
        ("Blue Period", "Kodansha", 14, "In Print", 13, 182, "Standard"),
        ("Toilet-Bound Hanako-kun", "Yen Press", 20, "In Print", 13, 260, "Standard"),
        ("Toilet-Bound Hanako-kun vol 0", "Yen Press", 1, "In Print", 13, 13, "Standard"),
        ("The Quintessential Quintuplets", "Kodansha", 14, "In Print", 11, 154, "Standard"),
        ("The Quintessential Quintuplets Box Set 1", "Kodansha", 7, "In Print", 11, 77, "Standard"),
        ("The Quintessential Quintuplets Box Set 2", "Kodansha", 7, "In Print", 11, 77, "Standard"),
        ("Rent-A-Girlfriend", "Kodansha", 32, "In Print", 11, 352, "Standard"),
        ("Call of the Night", "VIZ", 19, "In Print", 10, 190, "Standard"),
        ("Zom 100: Bucket List of the Dead", "VIZ", 17, "In Print", 10, 170, "Standard"),
        ("To Your Eternity", "Kodansha", 20, "In Print", 11, 220, "Standard"),
        ("The Summer Hikaru Died", "Yen Press", 4, "In Print", 13, 52, "Standard"),
        ("Roaming the Apocalypse with My Shiba Inu", "Yen Press", 3, "In Print", 15, 45, "Standard"),

        # ── Rare Tankoubon — JP First Prints & Specials ──────────────────
        ("Yu Yu Hakusho vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 60, 60, "High"),
        ("Rurouni Kenshin vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 55, 55, "High"),
        ("Dr. Slump vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 80, 80, "High"),
        ("Fist of the North Star vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 90, 90, "High"),
        ("City Hunter vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 70, 70, "High"),
        ("Saint Seiya vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 65, 65, "High"),
        ("Captain Tsubasa vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 60, 60, "High"),
        ("Shaman King vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 45, 45, "Mid"),
        ("Gintama vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 35, 35, "Mid"),
        ("Toriko vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 30, 30, "Mid"),
        ("Dandadan vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 30, 30, "Mid"),
        ("Sakamoto Days vol 1 (1st Print JP)", "Shueisha", 1, "OOP", 25, 25, "Mid"),

        # ── Out-of-Print Seinen Gems ─────────────────────────────────────
        ("Ikki Comix: Baku-On!! (Singles)", "Viz/Ikki", 4, "OOP", 25, 100, "Mid"),
        ("Tanpenshu (Hiroki Endo)", "Dark Horse", 2, "OOP", 25, 50, "Mid"),
        ("Eden: It's an Endless World! vol 14", "Dark Horse", 1, "OOP", 80, 80, "High"),
        ("Panorama of Hell (Hideshi Hino)", "Blast Books", 1, "OOP", 40, 40, "High"),
        ("Hell Baby (Hideshi Hino)", "Blast Books", 1, "OOP", 35, 35, "Mid"),
        ("Lychee Light Club", "Vertical", 1, "OOP", 20, 20, "Mid"),
        ("Dementia 21 (Shintaro Kago)", "Fantagraphics", 1, "OOP", 25, 25, "Mid"),
        ("Assassination Classroom vol 1 (1st Print)", "VIZ", 1, "OOP", 15, 15, "Mid"),

        # ── VIZ Signature / Mature Reader Line ───────────────────────────
        ("Pluto (Naoki Urasawa) vol 1 (1st Print)", "VIZ", 1, "OOP", 20, 20, "Mid"),
        ("Asadora!", "VIZ", 10, "In Print", 15, 150, "Standard"),
        ("Mujirushi: The Sign of Dreams", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("Master Keaton", "VIZ", 12, "In Print", 18, 216, "Standard"),
        ("Master Keaton vol 1 (1st Print)", "VIZ", 1, "OOP", 22, 22, "Mid"),
        ("Billy Bat", "Kodansha", 20, "OOP", 13, 260, "Mid"),
        ("Happy! (Naoki Urasawa)", "VIZ", 8, "OOP", 14, 112, "Mid"),

        # ── Light Novels — High Demand & OOP ─────────────────────────────
        ("Vampire Hunter D (Novel)", "Dark Horse", 29, "Partial OOP", 12, 348, "Mid"),
        ("Vampire Hunter D vol 1 (1st Print)", "Dark Horse", 1, "OOP", 30, 30, "Mid"),
        ("Full Metal Panic! (Light Novel)", "J-Novel Club", 12, "In Print", 14, 168, "Standard"),
        ("Log Horizon (Light Novel)", "Yen Press", 12, "In Print", 14, 168, "Standard"),
        ("Fate/Zero (Light Novel)", "Dark Horse", 4, "In Print", 16, 64, "Standard"),
        ("The Irregular at Magic High School (LN)", "Yen Press", 32, "In Print", 14, 448, "Standard"),
        ("So I'm a Spider, So What? (LN)", "Yen Press", 16, "In Print", 14, 224, "Standard"),
        ("My Youth Romantic Comedy Is Wrong (LN)", "Yen Press", 14, "Partial OOP", 14, 196, "Mid"),
        ("A Certain Magical Index (Light Novel)", "Yen Press", 22, "In Print", 14, 308, "Standard"),
        ("The Apothecary Diaries (Light Novel)", "J-Novel Club", 10, "In Print", 14, 140, "Standard"),
        ("Rascal Does Not Dream of Bunny Girl Senpai (LN)", "Yen Press", 11, "In Print", 14, 154, "Standard"),
        ("Steins;Gate (Novel)", "Yen Press", 3, "OOP", 15, 45, "Mid"),
        ("Welcome to the NHK (Novel)", "Tokyopop", 1, "OOP", 30, 30, "High"),
        ("Battle Royale (Novel)", "VIZ/Haikasoru", 1, "OOP", 18, 18, "Mid"),

        # ── Classic Shounen OOP ──────────────────────────────────────────
        ("Kinnikuman", "VIZ", 6, "OOP", 25, 150, "High"),
        ("Bastard!! (Singles)", "VIZ", 19, "OOP", 15, 285, "Mid"),
        ("Beet the Vandel Buster", "VIZ", 12, "OOP", 10, 120, "Mid"),
        ("Legendz", "VIZ", 4, "OOP", 12, 48, "Mid"),
        ("Bo-bobo-bo Bo-bobo", "VIZ", 21, "OOP", 12, 252, "Mid"),
        ("Gintama (English)", "VIZ", 23, "OOP", 12, 276, "Mid"),
        ("Beelzebub", "VIZ", 28, "Partial OOP", 10, 280, "Mid"),
        ("Nura: Rise of the Yokai Clan", "VIZ", 25, "OOP", 10, 250, "Mid"),
        ("Blue Exorcist", "VIZ", 28, "In Print", 10, 280, "Standard"),
        ("Jojo's Bizarre Adventure Part 1 (Shonen Jump Singles)", "VIZ", 5, "OOP", 20, 100, "Mid"),
        ("Hoshin Engi", "VIZ", 23, "OOP", 10, 230, "Mid"),
        ("Kekkaishi", "VIZ", 35, "OOP", 10, 350, "Mid"),

        # ── Horror Manga — Out-of-Print Classics ────────────────────────
        ("Uzumaki (Singles)", "VIZ", 3, "OOP", 25, 75, "Mid"),
        ("Museum of Terror (Junji Ito)", "Dark Horse", 3, "OOP", 50, 150, "High"),
        ("Tomie (Comics One Singles)", "ComicsOne", 1, "OOP", 60, 60, "High"),
        ("Gyo (Singles)", "VIZ", 2, "OOP", 20, 40, "Mid"),
        ("Scary Book (Kazuo Umezu)", "Dark Horse", 3, "OOP", 18, 54, "Mid"),
        ("The Drifting Classroom (Singles) vol 11 (Final)", "VIZ", 1, "OOP", 60, 60, "High"),
        ("Orochi: The Perfect Edition (Kazuo Umezu)", "VIZ", 2, "In Print", 23, 46, "Standard"),
        ("Cat Eyed Boy (Kazuo Umezu)", "VIZ", 2, "In Print", 23, 46, "Standard"),

        # ── Additional Modern Box Sets ───────────────────────────────────
        ("Dr. Stone Box Set", "VIZ", 26, "In Print", 10, 260, "Standard"),
        ("Food Wars! Box Set", "VIZ", 36, "In Print", 10, 360, "Standard"),
        ("Black Clover Box Set 1 (Vols 1-17)", "VIZ", 17, "In Print", 10, 170, "Standard"),
        ("Haikyuu!! Box Set 2 (Vols 11-20)", "VIZ", 10, "In Print", 10, 100, "Standard"),
        ("Haikyuu!! Box Set 3 (Vols 21-30)", "VIZ", 10, "In Print", 10, 100, "Standard"),
        ("Haikyuu!! Box Set 4 (Vols 31-45)", "VIZ", 15, "In Print", 10, 150, "Standard"),
        ("Kaguya-sama: Love Is War Box Set", "VIZ", 28, "In Print", 10, 280, "Standard"),
        ("Jujutsu Kaisen Box Set 1 (Vols 1-8)", "VIZ", 8, "In Print", 10, 80, "Standard"),

        # ── Expansion Round 2 — ~100 new items ─────────────────────────────

        # ── Slam Dunk OOP & Variants ────────────────────────────────────────
        ("Slam Dunk (Singles) Complete 1-31", "VIZ", 31, "OOP", 22, 680, "High"),
        ("Slam Dunk (Deluxe Kanzenban JP)", "Shueisha", 24, "In Print", 35, 840, "Mid"),
        ("Slam Dunk New Edition (JP Shinsoban)", "Shueisha", 20, "In Print", 15, 300, "Standard"),

        # ── Monster OOP Singles ─────────────────────────────────────────────
        ("Monster (Singles 1st Ed.)", "VIZ", 18, "OOP", 15, 270, "Mid"),

        # ── Vagabond Extended ───────────────────────────────────────────────
        ("Vagabond (Singles) Vol 37 Final Issue", "VIZ", 1, "OOP", 85, 85, "High"),

        # ── Box Sets — Unique Entries ───────────────────────────────────────
        ("My Hero Academia Box Set 2 (Vols 21-40)", "VIZ", 20, "In Print", 10, 200, "Standard"),
        ("Haikyuu!! Complete Box Set (Vols 1-45)", "VIZ", 45, "In Print", 10, 450, "Standard"),
        ("One Punch Man Box Set (Vols 1-23)", "VIZ", 23, "In Print", 10, 230, "Standard"),
        ("World Trigger Box Set (Vols 1-23)", "VIZ", 23, "In Print", 10, 230, "Standard"),
        ("The Quintessential Quintuplets Box Set", "Kodansha", 14, "In Print", 11, 154, "Standard"),
        ("Black Clover Box Set 2 (Vols 18-35)", "VIZ", 18, "In Print", 10, 180, "Standard"),
        ("Promised Neverland Complete Box Set", "VIZ", 20, "In Print", 8, 160, "Standard"),

        # ── First Editions / First English Printings ────────────────────────
        ("Akira vol 1 (1st English Edition, Epic/Marvel)", "Epic/Marvel", 1, "OOP", 80, 80, "High"),
        ("Dragon Ball vol 1 (1st English Print 2003)", "VIZ", 1, "OOP", 45, 45, "Mid"),
        ("Naruto vol 1 (1st English Print 2003)", "VIZ", 1, "OOP", 40, 40, "Mid"),
        ("One Piece vol 1 (1st English Print 2003)", "VIZ", 1, "OOP", 50, 50, "High"),
        ("Demon Slayer vol 1 (1st English Print)", "VIZ", 1, "OOP", 35, 35, "Mid"),

        # ── Variant Covers & Limited Editions ───────────────────────────────
        ("Chainsaw Man vol 1 (Viz Exclusive Foil Cover)", "VIZ", 1, "In Print", 40, 40, "Mid"),
        ("Jujutsu Kaisen vol 0 (Movie Tie-In Cover)", "VIZ", 1, "In Print", 15, 15, "Standard"),
        ("One Piece Color Walk Compendium: East Blue to Skypiea", "VIZ", 1, "In Print", 35, 35, "Standard"),
        ("One Piece Color Walk Compendium: Water Seven to Paramount War", "VIZ", 1, "In Print", 35, 35, "Standard"),

        # ── Japanese Tankobon Rarities (Unique Entries) ─────────────────────
        ("Dragon Ball vol 1 (1st Print JP Tankobon, 1985)", "Shueisha", 1, "OOP", 200, 200, "High"),
        ("Naruto vol 1 (1st Print JP Tankobon, 1999)", "Shueisha", 1, "OOP", 100, 100, "High"),
        ("One Piece vol 1 (1st Print JP Tankobon, 1997)", "Shueisha", 1, "OOP", 300, 300, "High"),
        ("JoJo's Bizarre Adventure Part 1 vol 1 (1st Print JP, 1987)", "Shueisha", 1, "OOP", 120, 120, "High"),
        ("Yu Yu Hakusho vol 1 (1st Print JP Tankobon)", "Shueisha", 1, "OOP", 80, 80, "Mid"),
        ("Rurouni Kenshin vol 1 (1st Print JP Tankobon)", "Shueisha", 1, "OOP", 70, 70, "Mid"),
        ("Slam Dunk vol 31 Final (1st Print JP Tankobon)", "Shueisha", 1, "OOP", 100, 100, "High"),
        ("Captain Tsubasa vol 1 (1st Print JP Tankobon)", "Shueisha", 1, "OOP", 90, 90, "High"),
        ("Fist of the North Star vol 1 (1st Print JP Tankobon)", "Shueisha", 1, "OOP", 120, 120, "High"),
        ("Dr. Slump vol 1 (1st Print JP Tankobon)", "Shueisha", 1, "OOP", 150, 150, "High"),

        # ── Light Novel Collector's Editions ────────────────────────────────
        ("Sword Art Online (Light Novel) vol 1 1st Print", "Yen Press", 1, "OOP", 20, 20, "Mid"),
        ("Spice and Wolf Anniversary Collector's Edition", "Yen Press", 1, "OOP", 50, 50, "High"),
        ("Monogatari Season 1 Box Set (Light Novel)", "Vertical", 6, "In Print", 14, 84, "Standard"),
        ("Monogatari Season 2 Box Set (Light Novel)", "Vertical", 7, "In Print", 14, 98, "Standard"),
        ("Monogatari Season 3 Box Set (Light Novel)", "Vertical", 6, "In Print", 14, 84, "Standard"),
        ("Classroom of the Elite Year 1 Complete Set (LN)", "Seven Seas", 12, "In Print", 14, 168, "Standard"),
        ("Classroom of the Elite Year 2 Set (LN)", "Seven Seas", 8, "In Print", 14, 112, "Standard"),

        # ── Fullmetal Alchemist Fullmetal Editions (Hardcovers) ─────────────
        ("FMA Fullmetal Edition Complete Set (vols 1-18)", "VIZ", 18, "In Print", 20, 360, "Standard"),
        ("FMA Fullmetal Edition vol 10", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("FMA Fullmetal Edition vol 11", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("FMA Fullmetal Edition vol 12", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("FMA Fullmetal Edition vol 13", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("FMA Fullmetal Edition vol 14", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("FMA Fullmetal Edition vol 15", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("FMA Fullmetal Edition vol 16", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("FMA Fullmetal Edition vol 17", "VIZ", 1, "In Print", 20, 20, "Standard"),
        ("FMA Fullmetal Edition vol 18", "VIZ", 1, "In Print", 20, 20, "Standard"),

        # ── OOP Classics — Unique Entries ───────────────────────────────────
        ("Yu-Gi-Oh! (3-in-1 Edition)", "VIZ", 13, "In Print", 15, 195, "Standard"),
        ("Yu-Gi-Oh! (Singles)", "VIZ", 38, "OOP", 8, 304, "Mid"),
        ("Inuyasha (VizBig Edition)", "VIZ", 18, "In Print", 18, 324, "Standard"),
        ("Inuyasha (Singles Set)", "VIZ", 56, "OOP", 8, 448, "Mid"),

        # ── Rare Artbooks & Illustration Collections ────────────────────────
        ("One Piece Color Walk 1 (JP Import Edition)", "Shueisha", 1, "OOP", 40, 40, "Mid"),
        ("Naruto Illustrations: NARUTO Artbook", "VIZ", 1, "In Print", 35, 35, "Standard"),
        ("Dragon Ball Super History Book (JP Import Edition)", "Shueisha", 1, "In Print", 30, 30, "Standard"),
        ("Berserk Official Guidebook (2nd Print)", "Dark Horse", 1, "In Print", 25, 25, "Standard"),
        ("Slam Dunk Illustrations 2 (JP)", "Shueisha", 1, "OOP", 50, 50, "High"),
        ("Inoue Takehiko: WATER (Artbook JP)", "Kodansha", 1, "OOP", 70, 70, "High"),
        ("Tsutomu Nihei: BLAME! and So On", "Kodansha", 1, "OOP", 45, 45, "Mid"),
        ("Kentaro Miura: Berserk Exhibition Artbook", "Hakusensha", 1, "OOP", 80, 80, "High"),
        ("Naoki Urasawa: Drawing the Borderline", "VIZ", 1, "In Print", 30, 30, "Standard"),
        ("Takeshi Obata: Blanc et Noir (Artbook)", "VIZ", 1, "In Print", 30, 30, "Standard"),

        # ── Additional Modern Manga ─────────────────────────────────────────
        ("Fujimoto Short Stories: Look Back + Goodbye Eri", "VIZ", 2, "In Print", 10, 20, "Standard"),
        ("Just Listen to the Song of the Wind (Fujimoto)", "VIZ", 1, "In Print", 16, 16, "Standard"),
        ("Dandadan (Deluxe Edition)", "VIZ", 5, "In Print", 20, 100, "Standard"),
        ("Zom 100 Complete Set (Vols 1-17)", "VIZ", 17, "In Print", 10, 170, "Standard"),
        ("Ranger Reject", "Kodansha", 12, "In Print", 11, 132, "Standard"),
        ("Choujin X", "VIZ", 8, "In Print", 10, 80, "Standard"),
        ("Rooster Fighter (Complete Set)", "VIZ", 8, "In Print", 10, 80, "Standard"),
        ("Spy x Family Official Fanbook: Eyes Only", "VIZ", 1, "In Print", 10, 10, "Standard"),
        ("One Piece Film Red Novel", "VIZ", 1, "In Print", 10, 10, "Standard"),
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
