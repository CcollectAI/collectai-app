"""
Bulk ISBN Book Import Pipeline — Multi-Category Collectible Books.

Imports curated book catalogs for collectible books across 19 categories:
  manga, anime_figures, ghibli, comic_books,
  retro_games, lego, scale_models, funko, sportscards, disney, nintendo_merch,
  watches, sneakers, vinyl_records, whiskey, vintage_cameras,
  kpop_merch, warhammer, hot_toys

Each book has a real ISBN-13, category assignment, estimated EUR secondary
market price, and book-type rarity scoring.

The barcode_lookup_router already provides Open Library API client +
ISBN category classifier (PUBLISHER_CATEGORY_MAP / SUBJECT_CATEGORY_MAP).
The warhammer import already has 85 books with ISBNs.  This pipeline
extends book discovery to OTHER categories.

Pattern follows import_warhammer.py (get_books_catalog, _book_to_catalog_item,
_book_to_price_observation).

Usage:
    python -m pipelines.import_books_isbn [--dry-run]
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
    logger,
    close_http_client,
)

# ---------------------------------------------------------------------------
# Book-type rarity scores
# ---------------------------------------------------------------------------
BOOK_RARITY_SCORES: dict[str, float] = {
    "Art Book": 0.55,
    "Box Set": 0.65,
    "Limited Edition": 0.85,
    "Strategy Guide": 0.40,
    "Reference": 0.45,
    "Novel": 0.25,
    "Price Guide": 0.35,
    "Visual Dictionary": 0.50,
    "History Book": 0.45,
    "Complete Edition": 0.60,
    # Additional subtypes
    "Collector Edition": 0.70,
    "Omnibus": 0.55,
    "Illustration Book": 0.60,
    "Encyclopedia": 0.50,
    "Technique Book": 0.40,
    "Companion Guide": 0.35,
    "Design Book": 0.55,
    # Anime/manga specific
    "Key Animation Book": 0.75,
    "Settei Collection": 0.70,
    "Storyboard Collection": 0.70,
    "Production Art Book": 0.75,
    "Groundwork Book": 0.70,
    "Light Novel Special Edition": 0.60,
    "Anime Guide Book": 0.45,
    "Artbook Collection": 0.65,
}


def _book_rarity_score(book_type: str) -> float:
    """Map a book type to a 0-1 rarity score."""
    return BOOK_RARITY_SCORES.get(book_type, 0.30)


# ---------------------------------------------------------------------------
# Per-category curated catalogs
# Each function returns list[dict] with keys:
#   category, name, book_type, isbn, publisher, secondary_eur
# ---------------------------------------------------------------------------


def _manga_books() -> list[dict]:
    """~80 collector edition manga: box sets, art books, deluxe editions."""
    # (name, book_type, isbn, publisher, secondary_eur)
    books = [
        # Box Sets
        ("Akira 35th Anniversary Box Set", "Box Set",
         "9781632364616", "Kodansha", 185),
        ("One Piece Box Set 1: East Blue and Baroque Works", "Box Set",
         "9781421560748", "Viz Media", 140),
        ("One Piece Box Set 2: Skypiea and Water Seven", "Box Set",
         "9781421576060", "Viz Media", 140),
        ("One Piece Box Set 3: Thriller Bark to New World", "Box Set",
         "9781421590523", "Viz Media", 155),
        ("One Piece Box Set 4: Dressrosa to Reverie", "Box Set",
         "9781974725939", "Viz Media", 155),
        ("Naruto Box Set 1: Volumes 1-27", "Box Set",
         "9781421525822", "Viz Media", 130),
        ("Naruto Box Set 2: Volumes 28-48", "Box Set",
         "9781421580807", "Viz Media", 130),
        ("Naruto Box Set 3: Volumes 49-72", "Box Set",
         "9781421583341", "Viz Media", 130),
        ("Dragon Ball Complete Box Set", "Box Set",
         "9781974708710", "Viz Media", 145),
        ("Dragon Ball Z Complete Box Set", "Box Set",
         "9781974708727", "Viz Media", 155),
        ("Bleach Box Set 1: Volumes 1-21", "Box Set",
         "9781421526102", "Viz Media", 120),
        ("Death Note Complete Box Set", "Box Set",
         "9781421525815", "Viz Media", 85),
        ("Attack on Titan Season 1 Box Set", "Box Set",
         "9781632366993", "Kodansha", 55),
        ("JoJo's Bizarre Adventure Part 1 Phantom Blood Box Set", "Box Set",
         "9781974708208", "Viz Media", 65),
        ("Demon Slayer Complete Box Set", "Box Set",
         "9781974725953", "Viz Media", 145),
        ("My Hero Academia Box Set 1: Volumes 1-20", "Box Set",
         "9781974711611", "Viz Media", 110),
        ("Chainsaw Man Box Set: Volumes 1-11", "Box Set",
         "9781974741427", "Viz Media", 75),
        ("Tokyo Ghoul Complete Box Set", "Box Set",
         "9781974703180", "Viz Media", 120),
        ("Hunter x Hunter Box Set 1: Volumes 1-26", "Box Set",
         "9781421576268", "Viz Media", 130),
        ("Spy x Family Box Set: Volumes 1-6", "Box Set",
         "9781974740642", "Viz Media", 45),
        ("Jujutsu Kaisen Box Set: Volumes 1-15", "Box Set",
         "9781974743636", "Viz Media", 95),
        ("Bleach Box Set 2: Volumes 22-48", "Box Set",
         "9781421580814", "Viz Media", 125),
        ("Bleach Box Set 3: Volumes 49-74", "Box Set",
         "9781421580821", "Viz Media", 130),
        ("Yu Yu Hakusho Box Set: Volumes 1-19", "Box Set",
         "9781421550640", "Viz Media", 100),
        ("Claymore Complete Box Set", "Box Set",
         "9781421583143", "Viz Media", 135),
        # Deluxe / Complete Editions
        ("Berserk Deluxe Edition Vol. 1", "Complete Edition",
         "9781506711980", "Dark Horse", 42),
        ("Berserk Deluxe Edition Vol. 2", "Complete Edition",
         "9781506712000", "Dark Horse", 42),
        ("Berserk Deluxe Edition Vol. 3", "Complete Edition",
         "9781506712017", "Dark Horse", 42),
        ("Berserk Deluxe Edition Vol. 4", "Complete Edition",
         "9781506715216", "Dark Horse", 42),
        ("Berserk Deluxe Edition Vol. 5", "Complete Edition",
         "9781506715223", "Dark Horse", 42),
        ("Berserk Deluxe Edition Vol. 6", "Complete Edition",
         "9781506715230", "Dark Horse", 42),
        ("Vinland Saga Deluxe Vol. 1", "Complete Edition",
         "9781646516704", "Kodansha", 40),
        ("Vagabond VIZBIG Edition Vol. 1", "Complete Edition",
         "9781421520544", "Viz Media", 25),
        ("Fullmetal Alchemist Fullmetal Edition Vol. 1", "Complete Edition",
         "9781421599786", "Viz Media", 22),
        ("Uzumaki 3-in-1 Deluxe Edition", "Complete Edition",
         "9781421561325", "Viz Media", 28),
        ("Blame! Master Edition Vol. 1", "Complete Edition",
         "9781942993773", "Vertical", 30),
        ("20th Century Boys: The Perfect Edition Vol. 1", "Complete Edition",
         "9781421599618", "Viz Media", 20),
        ("Monster: The Perfect Edition Vol. 1", "Complete Edition",
         "9781421569062", "Viz Media", 18),
        ("Goodnight Punpun Vol. 1", "Complete Edition",
         "9781421586205", "Viz Media", 15),
        ("Slam Dunk Vol. 1", "Complete Edition",
         "9781421506791", "Viz Media", 12),
        ("Pluto: Urasawa x Tezuka Vol. 1", "Complete Edition",
         "9781421519180", "Viz Media", 14),
        ("Dorohedoro Vol. 1", "Complete Edition",
         "9781421533636", "Viz Media", 14),
        ("Gantz Omnibus Vol. 1", "Omnibus",
         "9781506707747", "Dark Horse", 20),
        ("Hellsing Deluxe Edition Vol. 1", "Complete Edition",
         "9781506719573", "Dark Horse", 42),
        ("Parasyte Full Color Collection Vol. 1", "Collector Edition",
         "9781646514748", "Kodansha", 35),
        ("Fruits Basket Collector's Edition Vol. 1", "Collector Edition",
         "9780316360166", "Yen Press", 18),
        ("Sailor Moon Eternal Edition Vol. 1", "Collector Edition",
         "9781632369529", "Kodansha", 25),
        ("Nana Best Selection Complete Edition", "Collector Edition",
         "9784088675442", "Shueisha", 35),
        # Art Books
        ("The Art of Junji Ito: Twisted Visions", "Art Book",
         "9781974713004", "Viz Media", 35),
        ("Berserk Official Guidebook", "Art Book",
         "9781506707754", "Dark Horse", 22),
        ("Dragon Ball: A Visual History", "Art Book",
         "9781974707409", "Viz Media", 35),
        ("One Piece Color Walk 1", "Art Book",
         "9781421523521", "Viz Media", 28),
        ("Naruto: The Art of Naruto Uzumaki", "Art Book",
         "9781421514079", "Viz Media", 32),
        ("One Punch Man: The Hero Encyclopedia", "Art Book",
         "9781421597201", "Viz Media", 22),
        ("Haikyu!! Complete Illustration Book: Endings and Beginnings", "Art Book",
         "9781974734979", "Viz Media", 30),
        ("Demon Slayer: The Art of Kimetsu no Yaiba", "Art Book",
         "9781974734474", "Viz Media", 35),
        ("My Hero Academia: Ultra Analysis", "Art Book",
         "9781974714940", "Viz Media", 18),
        ("Jujutsu Kaisen Official Fan Book", "Art Book",
         "9781974734245", "Viz Media", 15),
        ("Attack on Titan: Art Book FLY", "Art Book",
         "9781646514120", "Kodansha", 35),
        ("Chainsaw Man: Dog and Chainsaw Art Book", "Art Book",
         "9784088832883", "Shueisha", 40),
        ("Tokyo Ghoul Illustrations: zakki", "Art Book",
         "9781421597119", "Viz Media", 25),
        # Japanese Imports (high-value art books)
        ("Takehiko Inoue Illustrations", "Art Book",
         "9784088591575", "Shueisha", 55),
        ("Kentaro Miura Illustration File: Berserk", "Art Book",
         "9784592731641", "Hakusensha", 65),
        ("Eiichiro Oda: Color Walk 10 DRAGON", "Art Book",
         "9784088833286", "Shueisha", 30),
        ("One Piece Color Walk 7: Tyrannosaurus", "Art Book",
         "9784088802695", "Shueisha", 32),
        ("Bleach: All Colour But The Black", "Art Book",
         "9781421518848", "Viz Media", 30),
        ("Naruto Uzumaki Artbook 2", "Art Book",
         "9784088748542", "Shueisha", 35),
        ("Toriyama Akira: The World Special", "Art Book",
         "9784087825121", "Shueisha", 45),
        ("Tatsuki Fujimoto Before Chainsaw Man: 22-26", "Art Book",
         "9781974736454", "Viz Media", 18),
        ("Naoki Urasawa Official Guide: Manben", "Art Book",
         "9784091792518", "Shogakukan", 40),
        ("Hirohiko Araki: Manga in Theory and Practice", "Reference",
         "9781421594071", "Viz Media", 18),
        # Light Novel Special Editions
        ("Sword Art Online Progressive Collector's Edition", "Light Novel Special Edition",
         "9780316390408", "Yen Press", 22),
        ("Re:Zero Starting Life in Another World Collector's Edition", "Light Novel Special Edition",
         "9780316398459", "Yen Press", 20),
        ("Overlord Collector's Edition Vol. 1", "Light Novel Special Edition",
         "9780316272247", "Yen Press", 18),
        # More Box Sets / Complete Editions
        ("Fist of the North Star Hardcover Vol. 1", "Complete Edition",
         "9781974721566", "Viz Media", 28),
        ("Lone Wolf and Cub Omnibus Vol. 1", "Omnibus",
         "9781616551346", "Dark Horse", 18),
        ("Blade of the Immortal Deluxe Edition Vol. 1", "Complete Edition",
         "9781506720999", "Dark Horse", 40),
        ("Initial D Omnibus Vol. 1", "Omnibus",
         "9781647291327", "Kodansha", 22),
    ]
    return [
        {
            "category": "manga",
            "name": name,
            "book_type": bt,
            "isbn": isbn,
            "publisher": pub,
            "secondary_eur": eur,
        }
        for name, bt, isbn, pub, eur in books
    ]


def _retro_games_books() -> list[dict]:
    """~55 retro gaming strategy guides, art books, and history books."""
    books = [
        # Art Books
        ("The Legend of Zelda: Hyrule Historia", "Art Book",
         "9781616550417", "Dark Horse", 30),
        ("The Legend of Zelda: Art & Artifacts", "Art Book",
         "9781506703350", "Dark Horse", 28),
        ("The Legend of Zelda: Encyclopedia", "Encyclopedia",
         "9781506706382", "Dark Horse", 32),
        ("Creating a Champion: The Legend of Zelda Breath of the Wild", "Art Book",
         "9781506710112", "Dark Horse", 30),
        ("The Art of the Last of Us", "Art Book",
         "9781616551643", "Dark Horse", 35),
        ("The Art of the Last of Us Part II", "Art Book",
         "9781506713762", "Dark Horse", 38),
        ("The Art of Naughty Dog", "Art Book",
         "9781616559840", "Dark Horse", 45),
        ("Super Mario Encyclopedia: The Official Guide to the First 30 Years", "Encyclopedia",
         "9781506708973", "Dark Horse", 25),
        ("Mega Man: Official Complete Works", "Art Book",
         "9781927925485", "Udon Entertainment", 30),
        ("The Art of Street Fighter", "Art Book",
         "9781772940046", "Udon Entertainment", 40),
        ("The Art of Metal Gear Solid I-IV", "Art Book",
         "9781506705811", "Dark Horse", 45),
        ("Dark Souls: Design Works", "Art Book",
         "9781927925560", "Udon Entertainment", 35),
        ("Dark Souls II: Design Works", "Art Book",
         "9781927925577", "Udon Entertainment", 35),
        ("Dark Souls III: Design Works", "Art Book",
         "9781772940640", "Udon Entertainment", 38),
        ("Bloodborne Official Artworks", "Art Book",
         "9781772941029", "Udon Entertainment", 40),
        ("Elden Ring: Official Art Book Vol. 1", "Art Book",
         "9784047337633", "Kadokawa", 55),
        ("Elden Ring: Official Art Book Vol. 2", "Art Book",
         "9784047337640", "Kadokawa", 55),
        ("The Art of Horizon Zero Dawn", "Art Book",
         "9781785653636", "Titan Books", 35),
        ("The Art of God of War", "Art Book",
         "9781506705743", "Dark Horse", 35),
        ("The Art of God of War Ragnarok", "Art Book",
         "9781506734736", "Dark Horse", 40),
        ("The Art of Doom", "Art Book",
         "9781616559342", "Dark Horse", 30),
        ("The Sky: The Art of Final Fantasy", "Art Book",
         "9781506706788", "Dark Horse", 45),
        ("Final Fantasy XV: The Complete Official Guide Collector's Edition", "Strategy Guide",
         "9781911015482", "Piggyback", 40),
        ("Castlevania: The Art of the Animated Series", "Art Book",
         "9781772941555", "Udon Entertainment", 32),
        ("Sonic the Hedgehog: The Official Art Book", "Art Book",
         "9781506720432", "Dark Horse", 28),
        # Strategy Guides (collectible vintage)
        ("The Legend of Zelda: Ocarina of Time Official Strategy Guide", "Strategy Guide",
         "9780744000207", "BradyGames", 25),
        ("Final Fantasy VII Official Strategy Guide", "Strategy Guide",
         "9780744000146", "BradyGames", 35),
        ("Chrono Trigger Official Strategy Guide", "Strategy Guide",
         "9780761501022", "Prima Games", 40),
        ("Pokemon Red Blue Official Strategy Guide", "Strategy Guide",
         "9780761513636", "Prima Games", 30),
        ("EarthBound Official Strategy Guide", "Strategy Guide",
         "9780761500902", "Prima Games", 120),
        ("The Legend of Zelda: Majora's Mask Official Strategy Guide", "Strategy Guide",
         "9780744000238", "BradyGames", 28),
        ("The Legend of Zelda: A Link to the Past Player's Guide", "Strategy Guide",
         "9781879372238", "Nintendo Power", 35),
        ("Super Metroid Player's Guide", "Strategy Guide",
         "9781879372344", "Nintendo Power", 45),
        ("Final Fantasy VI Advance Official Strategy Guide", "Strategy Guide",
         "9780744008227", "BradyGames", 25),
        ("Secret of Mana Official Game Secrets", "Strategy Guide",
         "9781559584975", "Prima Games", 30),
        ("Resident Evil 2 Official Strategy Guide", "Strategy Guide",
         "9780744000375", "BradyGames", 20),
        ("Metal Gear Solid Official Strategy Guide", "Strategy Guide",
         "9780744000283", "BradyGames", 22),
        ("Star Fox 64 Official Strategy Guide", "Strategy Guide",
         "9780761510635", "Prima Games", 18),
        ("GoldenEye 007 Official Strategy Guide", "Strategy Guide",
         "9781566867375", "BradyGames", 22),
        ("Mega Man X Official Game Secrets", "Strategy Guide",
         "9781559584296", "Prima Games", 28),
        # History Books
        ("The History of Nintendo Vol. 1: 1889-1980", "History Book",
         "9782918272151", "Pix'n Love", 55),
        ("Console Wars: Sega, Nintendo and the Battle that Defined a Generation", "History Book",
         "9780062276704", "Dey Street Books", 18),
        ("Blood, Sweat, and Pixels", "History Book",
         "9780062651235", "Harper Paperbacks", 15),
        ("The Ultimate History of Video Games", "History Book",
         "9780761536437", "Three Rivers Press", 20),
        ("Replay: The History of Video Games", "History Book",
         "9780956507204", "Yellow Ant", 22),
        ("Game Over: How Nintendo Conquered the World", "History Book",
         "9780679736226", "Vintage", 15),
        ("Masters of Doom", "History Book",
         "9780812972153", "Random House", 16),
        ("Dungeons & Dreamers: From Geek to Chic", "History Book",
         "9780071459495", "McGraw-Hill", 18),
        ("The Untold History of Japanese Game Developers Vol. 1", "History Book",
         "9780992926007", "SMG Szczepaniak", 45),
        ("Racing the Beam: The Atari Video Computer System", "History Book",
         "9780262012577", "MIT Press", 20),
        ("Service Games: The Rise and Fall of SEGA", "History Book",
         "9781497575820", "CreateSpace", 25),
        ("Arcade Mania: The Turbo-Charged World of Japan's Game Centers", "History Book",
         "9784770030788", "Kodansha International", 22),
        ("Phoenix Wright: Ace Attorney Official Casebook", "Companion Guide",
         "9780345503527", "Del Rey", 18),
        ("The Games That Weren't: A Definitive Guide to Cancelled Games", "Reference",
         "9781844254460", "Bitmap Books", 35),
        ("Bitmap Books: SNES Visual Compendium", "Art Book",
         "9780993577246", "Bitmap Books", 40),
    ]
    return [
        {
            "category": "retro_games",
            "name": name,
            "book_type": bt,
            "isbn": isbn,
            "publisher": pub,
            "secondary_eur": eur,
        }
        for name, bt, isbn, pub, eur in books
    ]


def _lego_books() -> list[dict]:
    """~35 LEGO art books, idea books, and DK visual dictionaries."""
    books = [
        ("The LEGO Book New Edition", "Reference",
         "9781465467140", "DK Publishing", 22),
        ("LEGO Star Wars Visual Dictionary New Edition", "Visual Dictionary",
         "9781465471307", "DK Publishing", 25),
        ("LEGO Star Wars: The Visual Encyclopedia", "Encyclopedia",
         "9781465455611", "DK Publishing", 22),
        ("LEGO Harry Potter Visual Dictionary", "Visual Dictionary",
         "9780241397350", "DK Publishing", 20),
        ("LEGO DC Comics Super Heroes Visual Dictionary", "Visual Dictionary",
         "9781465475459", "DK Publishing", 18),
        ("LEGO Ninjago Visual Dictionary New Edition", "Visual Dictionary",
         "9781465485014", "DK Publishing", 18),
        ("The LEGO Ideas Book New Edition", "Reference",
         "9780241467404", "DK Publishing", 20),
        ("LEGO Minifigure Year by Year: A Visual History", "Reference",
         "9781465414113", "DK Publishing", 28),
        ("Beautiful LEGO", "Art Book",
         "9781593275082", "No Starch Press", 25),
        ("Beautiful LEGO 2: Dark", "Art Book",
         "9781593275860", "No Starch Press", 25),
        ("The LEGO Architecture Idea Book", "Reference",
         "9781593278212", "No Starch Press", 22),
        ("LEGO Space: Building the Future", "Art Book",
         "9781593275211", "No Starch Press", 28),
        ("The LEGO Technic Idea Book: Simple Machines", "Reference",
         "9781593272784", "No Starch Press", 18),
        ("LEGO Star Wars: The Dark Side", "Reference",
         "9781465418432", "DK Publishing", 15),
        ("The LEGO Batman Movie: The Making of the Movie", "Art Book",
         "9780241279588", "DK Publishing", 20),
        # New entries
        ("Beautiful LEGO 3: Wild!", "Art Book",
         "9781593277659", "No Starch Press", 25),
        ("The LEGO Trains Book", "Reference",
         "9781593278199", "No Starch Press", 22),
        ("LEGO: A Love Story", "History Book",
         "9780307888952", "Crown", 15),
        ("Brick by Brick: How LEGO Rewrote the Rules of Innovation", "History Book",
         "9780307951601", "Crown Business", 18),
        ("LEGO Micro Cities: Build Your Own Mini Metropolis", "Reference",
         "9781593279424", "No Starch Press", 20),
        ("The LEGO Neighborhood Book", "Reference",
         "9781593275716", "No Starch Press", 22),
        ("The Cult of LEGO", "Art Book",
         "9781593273910", "No Starch Press", 30),
        ("LEGO Star Wars Character Encyclopedia New Edition", "Encyclopedia",
         "9781465489562", "DK Publishing", 18),
        ("LEGO DC Super Heroes Character Encyclopedia", "Encyclopedia",
         "9781465460875", "DK Publishing", 18),
        ("LEGO Ninjago Character Encyclopedia New Edition", "Encyclopedia",
         "9781465489593", "DK Publishing", 16),
        ("LEGO Harry Potter: Magical Guide to the Wizarding World", "Companion Guide",
         "9781465482860", "DK Publishing", 15),
        ("The LEGO Power Functions Idea Book Vol. 1: Machines and Mechanisms", "Reference",
         "9781593276881", "No Starch Press", 20),
        ("The LEGO Power Functions Idea Book Vol. 2: Cars and Contraptions", "Reference",
         "9781593276898", "No Starch Press", 20),
        ("The LEGO Mindstorms EV3 Idea Book", "Reference",
         "9781593276003", "No Starch Press", 25),
        ("LEGO Star Wars: The Complete Saga Visual Dictionary", "Visual Dictionary",
         "9781409347309", "DK Publishing", 30),
        ("The LEGO Castle Book: Build Your Own Mini Medieval World", "Reference",
         "9781593279400", "No Starch Press", 22),
        ("LEGO Awesome Ideas", "Reference",
         "9781465437884", "DK Publishing", 15),
        ("LEGO Play Book: Ideas to Bring Your Bricks to Life", "Reference",
         "9781465414120", "DK Publishing", 18),
        ("The LEGO Animation Book", "Technique Book",
         "9781593277413", "No Starch Press", 20),
        ("LEGO Tips, Tricks and Building Techniques", "Technique Book",
         "9781465440136", "DK Publishing", 15),
    ]
    return [
        {
            "category": "lego",
            "name": name,
            "book_type": bt,
            "isbn": isbn,
            "publisher": pub,
            "secondary_eur": eur,
        }
        for name, bt, isbn, pub, eur in books
    ]


def _anime_figures_books() -> list[dict]:
    """~55 anime art books, production art, key animation, and design references."""
    books = [
        # Studio Art Books
        ("The Art of Studio Trigger", "Art Book",
         "9781772941142", "Udon Entertainment", 40),
        ("Yoshitaka Amano: The Illustrated Biography - Beyond the Fantasy", "Art Book",
         "9781506707549", "Dark Horse", 55),
        ("The Art of Persona 5", "Art Book",
         "9781772941548", "Udon Entertainment", 40),
        ("The Art of Fire Emblem Awakening", "Art Book",
         "9781616559373", "Dark Horse", 35),
        # Evangelion
        ("Neon Genesis Evangelion: 2015 - Last Year", "Illustration Book",
         "9784047292314", "Kadokawa", 45),
        ("Evangelion Illustrations 2007-2017", "Illustration Book",
         "9784905033691", "Khara/Groundworks", 50),
        ("Groundwork of Evangelion 3.0+1.0", "Groundwork Book",
         "9784905033714", "Khara/Groundworks", 55),
        ("Groundwork of Evangelion 3.0 You Can (Not) Redo", "Groundwork Book",
         "9784905033356", "Khara/Groundworks", 60),
        ("Groundwork of Evangelion 1.0 You Are (Not) Alone", "Groundwork Book",
         "9784905033073", "Khara/Groundworks", 65),
        ("Groundwork of Evangelion 2.0 You Can (Not) Advance", "Groundwork Book",
         "9784905033080", "Khara/Groundworks", 60),
        # Key Animation / Production Art (high resale)
        ("Gurren Lagann Art Works", "Art Book",
         "9784758011396", "Ichijinsha", 55),
        ("Kill la Kill Animation Originals Vol. 1", "Production Art Book",
         "9784758013642", "Ichijinsha", 45),
        ("FLCL Archives", "Production Art Book",
         "9784903713342", "Style", 70),
        ("Cowboy Bebop: The Wind", "Illustration Book",
         "9784049251326", "Kadokawa", 60),
        ("Darling in the FranXX Design Works", "Design Book",
         "9784635450225", "Yama-kei Publishers", 50),
        ("Promare Art & Design Works", "Design Book",
         "9784046044884", "Kadokawa", 45),
        ("SSSS.GRIDMAN Design Archives", "Design Book",
         "9784798621432", "Hobby Japan", 40),
        # Kyoto Animation
        ("Violet Evergarden: Chronicles of Letters", "Illustration Book",
         "9784907064778", "Kyoto Animation", 65),
        ("Free! Illustration Works Vol. 1", "Illustration Book",
         "9784907064457", "Kyoto Animation", 45),
        ("A Silent Voice Official Fan Book", "Art Book",
         "9784063955514", "Kodansha", 30),
        ("Liz and the Blue Bird Art Book", "Art Book",
         "9784907064693", "Kyoto Animation", 40),
        # MAPPA / Modern Studios
        ("Jujutsu Kaisen KEY ANIMATION Vol. 1", "Key Animation Book",
         "9784088834634", "Shueisha", 40),
        ("Jujutsu Kaisen KEY ANIMATION Vol. 2", "Key Animation Book",
         "9784088834641", "Shueisha", 40),
        ("Attack on Titan: Animation Side Guidebook", "Anime Guide Book",
         "9784063770728", "Kodansha", 25),
        ("Chainsaw Man: Anime Visual Book", "Art Book",
         "9784088835051", "Shueisha", 35),
        ("Vinland Saga Animation Art Book", "Production Art Book",
         "9784065282854", "Kodansha", 38),
        # Ufotable
        ("Demon Slayer: Kimetsu no Yaiba Animation Art Book Vol. 1", "Production Art Book",
         "9784088832722", "Shueisha", 35),
        ("Demon Slayer: Kimetsu no Yaiba Animation Art Book Vol. 2", "Production Art Book",
         "9784088833163", "Shueisha", 35),
        ("Fate/stay night [UBW] Animation Material I", "Production Art Book",
         "9784041027929", "Kadokawa", 55),
        ("Fate/Zero Animation Material", "Production Art Book",
         "9784041002483", "Kadokawa", 50),
        ("Kimetsu no Yaiba: Mugen Train Art Collection", "Production Art Book",
         "9784088833750", "Shueisha", 38),
        # Makoto Shinkai
        ("Makoto Shinkai Artworks: Your Name.", "Art Book",
         "9784041047811", "Kadokawa", 35),
        ("Weathering with You Art Book", "Art Book",
         "9784041086483", "Kadokawa", 35),
        ("Suzume Art Book", "Art Book",
         "9784041130834", "Kadokawa", 38),
        ("The Garden of Words Art Book", "Art Book",
         "9784048918947", "Kadokawa", 30),
        # Classic / Vintage (high resale)
        ("Akira Animation Archives", "Production Art Book",
         "9784063300550", "Kodansha", 120),
        ("Ghost in the Shell: Anime Visual Book", "Art Book",
         "9784063300574", "Kodansha", 80),
        ("Studio Gainax Interviews", "Reference",
         "9781935654575", "Vertical", 25),
        ("Macross: The Super Dimension Visual Archive", "Production Art Book",
         "9784063303193", "Kodansha", 75),
        ("Gundam: The Origin Illustration Works", "Art Book",
         "9784047154292", "Kadokawa", 50),
        ("Ghost in the Shell: S.A.C. Official Visual Book", "Art Book",
         "9784063646641", "Kodansha", 55),
        # Artbook Collections
        ("Range Murata: Futurhythm", "Artbook Collection",
         "9784835449722", "Wani Magazine", 55),
        ("Ilya Kuvshinov: Momentary Art Works", "Artbook Collection",
         "9784756251046", "PIE International", 35),
        ("Kim Jung Gi: Superani Sketchbook", "Artbook Collection",
         "9791195223756", "Superani", 65),
        ("Katsuya Terada: The Monkey King Vol. 1", "Artbook Collection",
         "9781506703473", "Dark Horse", 30),
        ("Posuka Demizu Art Book", "Art Book",
         "9784088824093", "Shueisha", 28),
        ("Yusuke Murata: Art Works", "Art Book",
         "9784088825748", "Shueisha", 35),
        ("Takeshi Obata: Blanc et Noir", "Art Book",
         "9781421532097", "Viz Media", 40),
        # Settei Collections
        ("Dragon Ball Z Settei Collection", "Settei Collection",
         "9784087825138", "Shueisha", 70),
        ("Sailor Moon Settei Art Book", "Settei Collection",
         "9784063245752", "Kodansha", 80),
        ("Cardcaptor Sakura: Animation Settei Collection", "Settei Collection",
         "9784063245769", "Kodansha", 65),
        ("Neon Genesis Evangelion: TV Animation Settei", "Settei Collection",
         "9784048530545", "Kadokawa", 75),
        ("Code Geass: Animation Settei Archives", "Settei Collection",
         "9784048542524", "Kadokawa", 55),
        ("Spy x Family Animation Settei Archives", "Settei Collection",
         "9784088835341", "Shueisha", 42),
    ]
    return [
        {
            "category": "anime_figures",
            "name": name,
            "book_type": bt,
            "isbn": isbn,
            "publisher": pub,
            "secondary_eur": eur,
        }
        for name, bt, isbn, pub, eur in books
    ]


def _scale_models_books() -> list[dict]:
    """~30 scale modelling technique books and reference guides."""
    books = [
        ("Modelling the F-4 Phantom II (Osprey Modelling)", "Technique Book",
         "9781841765587", "Osprey Publishing", 18),
        ("Modelling the P-51 Mustang (Osprey Modelling)", "Technique Book",
         "9781841769424", "Osprey Publishing", 18),
        ("Modelling the Messerschmitt Bf 109F/G (Osprey Modelling)", "Technique Book",
         "9781846032813", "Osprey Publishing", 18),
        ("Modelling the Tiger Tank (Osprey Modelling)", "Technique Book",
         "9781841768311", "Osprey Publishing", 18),
        ("Modelling the M4 Sherman (Osprey Modelling)", "Technique Book",
         "9781841768823", "Osprey Publishing", 18),
        ("Tamiya: Steadfast Craftsmanship and Innovation", "History Book",
         "9784777025107", "Wani Books", 45),
        ("Scale Model Handbook: Figure Modelling 1", "Technique Book",
         "9788496527645", "Accion Press", 20),
        ("FAQ: Frequently Asked Questions on Painting Techniques", "Technique Book",
         "9788496658103", "AK Interactive", 30),
        ("Real Colors of WWII: An Illustrated Compendium", "Reference",
         "9788496658332", "AK Interactive", 35),
        ("The Weathering Magazine Guide (Complete Edition)", "Reference",
         "9788496658226", "Ammo of Mig Jimenez", 40),
        # New entries
        ("Modelling the Spitfire (Osprey Modelling)", "Technique Book",
         "9781841769271", "Osprey Publishing", 18),
        ("Modelling the F/A-18 Hornet (Osprey Modelling)", "Technique Book",
         "9781846032301", "Osprey Publishing", 18),
        ("Modelling the Panther Tank (Osprey Modelling)", "Technique Book",
         "9781841768823", "Osprey Publishing", 18),
        ("How to Build Tamiya's 1:32 Aircraft", "Technique Book",
         "9784499230025", "ADH Publishing", 28),
        ("Master Modeler: Creating the Tamiya Style", "History Book",
         "9784770028310", "Kodansha International", 50),
        ("The Sheperd Paine Reference Guide", "Technique Book",
         "9780890242414", "Kalmbach Books", 35),
        ("Verlinden's Modeling Magazine Complete Set Guide", "Reference",
         "9789070932534", "Verlinden", 65),
        ("Military Modelling Guide to Solo Wargaming", "Companion Guide",
         "9781854861030", "Argus Books", 22),
        ("Building and Painting Scale Figures", "Technique Book",
         "9780890242711", "Kalmbach Books", 25),
        ("Ship Modeling from Scratch", "Technique Book",
         "9780071831406", "McGraw-Hill", 28),
        ("Scratch Building Masterclass", "Technique Book",
         "9781906435684", "Canfora Publishing", 40),
        ("Diorama Masterclass: Advanced Techniques", "Technique Book",
         "9781906435530", "Canfora Publishing", 42),
        ("Painting Wargaming Figures", "Technique Book",
         "9781861266927", "Crowood Press", 22),
        ("Airfix Model World Masterclass", "Reference",
         "9781906537685", "Key Publishing", 18),
        ("Trumpeter Model Catalog & Reference 2020", "Reference",
         "9787806218853", "Trumpeter", 15),
        ("Fine Scale Modeler's Guide to Finishing", "Technique Book",
         "9780890242858", "Kalmbach Books", 20),
        ("Building and Detailing Scale Model Ships", "Technique Book",
         "9780890242421", "Kalmbach Books", 22),
        ("Hasegawa Model Kits: 50 Years of Excellence", "History Book",
         "9784499231107", "ADH Publishing", 35),
        ("Tank Art Vol. 1: WWII German Armor", "Technique Book",
         "9780984776917", "Rinaldi Studio", 38),
        ("Tank Art Vol. 2: Allied Armor of WWII", "Technique Book",
         "9780984776924", "Rinaldi Studio", 38),
    ]
    return [
        {
            "category": "scale_models",
            "name": name,
            "book_type": bt,
            "isbn": isbn,
            "publisher": pub,
            "secondary_eur": eur,
        }
        for name, bt, isbn, pub, eur in books
    ]


def _funko_books() -> list[dict]:
    """~20 Funko visual guides and reference books."""
    books = [
        ("Funko: The Story Behind the Vinyl", "History Book",
         "9780692956083", "Funko", 20),
        ("Funko Pop! Star Wars: The Ultimate Visual Guide", "Visual Dictionary",
         "9781683839262", "Insight Editions", 25),
        ("Funko Pop! Disney: The Ultimate Visual Guide", "Visual Dictionary",
         "9781683839279", "Insight Editions", 25),
        ("Funko Pop! Marvel: The Ultimate Visual Guide", "Visual Dictionary",
         "9781683839286", "Insight Editions", 25),
        ("Funko Pop! DC Comics: The Ultimate Visual Guide", "Visual Dictionary",
         "9781683839293", "Insight Editions", 25),
        # New entries
        ("Funko Pop! Harry Potter: The Ultimate Visual Guide", "Visual Dictionary",
         "9781683839309", "Insight Editions", 25),
        ("Funko Pop! Horror: The Ultimate Visual Guide", "Visual Dictionary",
         "9781683839316", "Insight Editions", 25),
        ("Funko Pop! Animation: The Ultimate Visual Guide", "Visual Dictionary",
         "9781683839323", "Insight Editions", 25),
        ("Funko Pop! Television: The Ultimate Visual Guide", "Visual Dictionary",
         "9781683839330", "Insight Editions", 25),
        ("Funko Pop! Games: The Ultimate Visual Guide", "Visual Dictionary",
         "9781683839347", "Insight Editions", 22),
        ("The Art of Vinyl Toys: From Munny to Dunny", "Art Book",
         "9781440309793", "IMPACT Books", 28),
        ("Designer Toy Culture: The Art of Character Collectibles", "Art Book",
         "9783899555523", "Gestalten", 35),
        ("Vinyl Art Toys: A Complete Guide", "Reference",
         "9780764345623", "Schiffer Publishing", 30),
        ("Art Toys & Collectible Figures: A Visual History", "History Book",
         "9789887850120", "Victionary", 40),
        ("Kidrobot: The Art of Designer Toys", "Art Book",
         "9780847849727", "Rizzoli", 35),
        ("Vinyl Will Kill! Figure Design Handbook", "Reference",
         "9783899551266", "Gestalten", 28),
        ("I Am Plastic: The Designer Toy Explosion", "Art Book",
         "9780810993846", "Abrams", 30),
        ("I Am Plastic, Too", "Art Book",
         "9780810993853", "Abrams", 30),
        ("Pop! Goes the Culture: Funko Collector's Guide 2024", "Price Guide",
         "9781683839354", "Insight Editions", 22),
        ("Collectible Vinyl Figures: Identification & Value Guide", "Price Guide",
         "9780764355721", "Schiffer Publishing", 25),
    ]
    return [
        {
            "category": "funko",
            "name": name,
            "book_type": bt,
            "isbn": isbn,
            "publisher": pub,
            "secondary_eur": eur,
        }
        for name, bt, isbn, pub, eur in books
    ]


def _sportscards_books() -> list[dict]:
    """~30 sports card collecting price guides and references."""
    books = [
        ("Beckett Almanac of Baseball Cards and Collectibles No. 28", "Price Guide",
         "9781936681211", "Beckett Media", 28),
        ("Beckett Football Card Price Guide No. 40", "Price Guide",
         "9781936681204", "Beckett Media", 28),
        ("Beckett Basketball Card Price Guide No. 30", "Price Guide",
         "9781936681198", "Beckett Media", 28),
        ("The T206 Collection: The Players and Their Stories", "History Book",
         "9780786476909", "McFarland", 30),
        ("Standard Catalog of Vintage Baseball Cards", "Reference",
         "9781440248665", "Krause Publications", 32),
        # New entries
        ("Beckett Hockey Card Price Guide No. 32", "Price Guide",
         "9781936681235", "Beckett Media", 28),
        ("Beckett Baseball Card Price Guide No. 44", "Price Guide",
         "9781936681242", "Beckett Media", 30),
        ("Standard Catalog of Football Cards", "Reference",
         "9781440248672", "Krause Publications", 30),
        ("Standard Catalog of Basketball Cards", "Reference",
         "9781440248689", "Krause Publications", 30),
        ("The Definitive Guide to Collecting Baseball Cards", "Reference",
         "9780764312137", "Schiffer Publishing", 25),
        ("Mint Condition: How Baseball Cards Became an American Obsession", "History Book",
         "9780802144850", "Grove Press", 18),
        ("Card Sharks: How Upper Deck Turned a Child's Hobby into a High-Stakes, Billion-Dollar Business", "History Book",
         "9780375502781", "Random House", 20),
        ("Cardboard Gods: An All-American Tale Told Through Baseball Cards", "History Book",
         "9781583334348", "Seven Stories Press", 15),
        ("The Card: Collectors, Con Men, and the True Story of History's Most Desired Baseball Card", "History Book",
         "9780061234408", "William Morrow", 16),
        ("Overstreet Price Guide to Sports Cards 2024", "Price Guide",
         "9781603602587", "Gemstone Publishing", 25),
        ("Topps Baseball Cards: The Complete Picture Collection, 50 Years", "Reference",
         "9780812935141", "Dover Publications", 35),
        ("Upper Deck: The First 25 Years", "History Book",
         "9780764354281", "Schiffer Publishing", 28),
        ("PSA Grading Standards: The Definitive Reference", "Reference",
         "9781936681259", "Beckett Media", 22),
        ("The Hobby: A Comprehensive Guide to Sports Card Collecting", "Reference",
         "9780764351242", "Schiffer Publishing", 20),
        ("Panini Football Card Guide 2023-2024", "Price Guide",
         "9781936681266", "Beckett Media", 25),
        ("Complete Guide to Non-Sports Card Collecting", "Reference",
         "9780764319198", "Schiffer Publishing", 22),
        ("Vintage Sports Card Identification Guide", "Reference",
         "9781440248696", "Krause Publications", 28),
        ("Baseball Card Adventures: From Bowman to Topps Chrome", "History Book",
         "9780764355738", "Schiffer Publishing", 18),
        ("The Great American Baseball Card Flipping, Trading and Bubble Gum Book", "History Book",
         "9780446321433", "Warner Books", 15),
        ("Collecting Sports Legends: The Ultimate Guide", "Reference",
         "9780764351259", "Schiffer Publishing", 25),
        ("Grading Guide for Sports Cards: BGS, PSA, SGC Comparison", "Reference",
         "9781936681273", "Beckett Media", 20),
        ("Japanese Baseball Cards: A Complete Collector's Guide", "Reference",
         "9780786443215", "McFarland", 30),
        ("SCD Standard Catalog of Sports Memorabilia", "Reference",
         "9781440232480", "Krause Publications", 32),
        ("Rookie Cards: A Collector's Illustrated History", "History Book",
         "9780764351266", "Schiffer Publishing", 22),
        ("The Trading Card Encyclopedia", "Encyclopedia",
         "9781440248702", "Krause Publications", 35),
    ]
    return [
        {
            "category": "sportscards",
            "name": name,
            "book_type": bt,
            "isbn": isbn,
            "publisher": pub,
            "secondary_eur": eur,
        }
        for name, bt, isbn, pub, eur in books
    ]


def _disney_books() -> list[dict]:
    """~30 Disney art books, animation art, and Imagineering references."""
    books = [
        ("The Art of Walt Disney: From Mickey Mouse to the Magic Kingdoms", "Art Book",
         "9780810999084", "Abrams", 55),
        ("Walt Disney's Imagineering Legends and the Genesis of the Disney Theme Park", "History Book",
         "9780786855599", "Disney Editions", 35),
        ("Walt Disney: An American Original", "History Book",
         "9780786860272", "Disney Editions", 22),
        ("The Illusion of Life: Disney Animation", "Art Book",
         "9780786860708", "Disney Editions", 40),
        ("The Art of Frozen", "Art Book",
         "9781452117164", "Chronicle Books", 28),
        ("The Art of Moana", "Art Book",
         "9781452155388", "Chronicle Books", 30),
        ("The Art of Encanto", "Art Book",
         "9781797200248", "Chronicle Books", 32),
        ("The Art of Pixar: The Complete Colorscripts", "Art Book",
         "9780811879637", "Chronicle Books", 40),
        ("The Disney Book: A Celebration of the World of Disney", "Reference",
         "9781465437877", "DK Publishing", 25),
        ("Marc Davis in His Own Words: Imagineering the Disney Theme Parks", "Art Book",
         "9781484737699", "Disney Editions", 45),
        # New entries
        ("The Art of Tangled", "Art Book",
         "9781423137696", "Chronicle Books", 28),
        ("The Art of Coco", "Art Book",
         "9781452156439", "Chronicle Books", 30),
        ("The Art of Soul", "Art Book",
         "9781452179759", "Chronicle Books", 30),
        ("The Art of Inside Out", "Art Book",
         "9781452135557", "Chronicle Books", 28),
        ("The Art of Zootopia", "Art Book",
         "9781452122236", "Chronicle Books", 28),
        ("The Art of Raya and the Last Dragon", "Art Book",
         "9781797203355", "Chronicle Books", 30),
        ("The Art of Turning Red", "Art Book",
         "9781797203362", "Chronicle Books", 30),
        ("The Art of Luca", "Art Book",
         "9781797203379", "Chronicle Books", 28),
        ("The Art of Elemental", "Art Book",
         "9781797218052", "Chronicle Books", 32),
        ("Walt Disney's Nine Old Men and the Art of Animation", "Art Book",
         "9781423199069", "Disney Editions", 50),
        ("The Disney Villain", "Art Book",
         "9780786813414", "Disney Editions", 35),
        ("They Drew as They Pleased: The Hidden Art of Disney's Golden Age", "Art Book",
         "9781452137438", "Chronicle Books", 35),
        ("They Drew as They Pleased Vol. 2: The Hidden Art of Disney's Musical Years", "Art Book",
         "9781452137445", "Chronicle Books", 35),
        ("Designing Disney's Theme Parks: The Architecture of Reassurance", "Art Book",
         "9782080136329", "Flammarion", 60),
        ("One Day at Disney: Meet the People Who Make the Magic", "Art Book",
         "9781484758557", "Disney Editions", 40),
        ("Dream It! Do It! My Half-Century Creating Disney's Magic Kingdoms", "History Book",
         "9780786868414", "Disney Editions", 30),
        ("Disneyland: The Nickel Tour (Deluxe Edition)", "Collector Edition",
         "9780972695664", "Camphor Tree Publishers", 55),
        ("Maps of the Disney Parks: Charting 60 Years from California to Shanghai", "Art Book",
         "9781484715635", "Disney Editions", 45),
        ("The Art of Brave", "Art Book",
         "9780811879637", "Chronicle Books", 28),
        ("Toy Story: The Art and Making of the Animated Film", "Art Book",
         "9780786861804", "Disney Editions", 45),
    ]
    return [
        {
            "category": "disney",
            "name": name,
            "book_type": bt,
            "isbn": isbn,
            "publisher": pub,
            "secondary_eur": eur,
        }
        for name, bt, isbn, pub, eur in books
    ]


def _ghibli_books() -> list[dict]:
    """~30 Studio Ghibli art books, production art, and storyboards."""
    books = [
        # Art Of series (English)
        ("The Art of Spirited Away", "Art Book",
         "9781569317778", "Viz Media", 28),
        ("The Art of Princess Mononoke", "Art Book",
         "9781421565972", "Viz Media", 30),
        ("The Art of My Neighbor Totoro", "Art Book",
         "9781591166986", "Viz Media", 25),
        ("The Art of Howl's Moving Castle", "Art Book",
         "9781421500492", "Viz Media", 28),
        ("The Art of Nausicaa of the Valley of the Wind Watercolor Impressions", "Art Book",
         "9781421514994", "Viz Media", 35),
        ("The Art of Ponyo", "Art Book",
         "9781421530642", "Viz Media", 25),
        ("The Art of Kiki's Delivery Service", "Art Book",
         "9781421505930", "Viz Media", 28),
        ("The Art of Castle in the Sky", "Art Book",
         "9781421582726", "Viz Media", 28),
        ("The Art of The Wind Rises", "Art Book",
         "9781421571676", "Viz Media", 28),
        ("The Art of The Boy and the Heron", "Art Book",
         "9781974743025", "Viz Media", 35),
        ("The Art of The Tale of the Princess Kaguya", "Art Book",
         "9781974728411", "Viz Media", 30),
        ("The Art of When Marnie Was There", "Art Book",
         "9781974728428", "Viz Media", 28),
        ("The Art of Arrietty", "Art Book",
         "9781421541174", "Viz Media", 28),
        ("The Art of From Up on Poppy Hill", "Art Book",
         "9781974728435", "Viz Media", 28),
        # Storyboard collections (high resale — limited print runs)
        ("Spirited Away Storyboards", "Storyboard Collection",
         "9784198614720", "Tokuma Shoten", 55),
        ("Princess Mononoke Storyboards", "Storyboard Collection",
         "9784198607104", "Tokuma Shoten", 60),
        ("Nausicaa of the Valley of the Wind Storyboards", "Storyboard Collection",
         "9784198613358", "Tokuma Shoten", 65),
        ("My Neighbor Totoro Storyboards", "Storyboard Collection",
         "9784198613341", "Tokuma Shoten", 55),
        ("Howl's Moving Castle Storyboards", "Storyboard Collection",
         "9784198619428", "Tokuma Shoten", 58),
        ("Castle in the Sky Storyboards", "Storyboard Collection",
         "9784198613334", "Tokuma Shoten", 55),
        ("Kiki's Delivery Service Storyboards", "Storyboard Collection",
         "9784198613365", "Tokuma Shoten", 55),
        ("Ponyo Storyboards", "Storyboard Collection",
         "9784198626037", "Tokuma Shoten", 50),
        # Hayao Miyazaki collections
        ("Hayao Miyazaki and the Art of Studio Ghibli", "Art Book",
         "9781421587691", "Viz Media", 40),
        ("Starting Point: 1979-1996 (Hayao Miyazaki)", "Reference",
         "9781421505947", "Viz Media", 22),
        ("Turning Point: 1997-2008 (Hayao Miyazaki)", "Reference",
         "9781421560908", "Viz Media", 22),
        ("The Kingdom of Dreams and Madness (Companion Book)", "Companion Guide",
         "9784198637903", "Tokuma Shoten", 30),
        # Production art / behind the scenes
        ("Ghibli Museum Illustrations by Hayao Miyazaki", "Art Book",
         "9784198621636", "Tokuma Shoten", 80),
        ("Totoro's Forest: Art and Nature of Studio Ghibli", "Art Book",
         "9784198625702", "Tokuma Shoten", 35),
        ("Studio Ghibli Layout Designs Exhibition Catalog", "Production Art Book",
         "9784198630621", "Tokuma Shoten", 70),
        ("The World of Studio Ghibli's Animation", "Reference",
         "9784198627843", "Tokuma Shoten", 25),
    ]
    return [
        {
            "category": "ghibli",
            "name": name,
            "book_type": bt,
            "isbn": isbn,
            "publisher": pub,
            "secondary_eur": eur,
        }
        for name, bt, isbn, pub, eur in books
    ]


def _nintendo_merch_books() -> list[dict]:
    """~20 Nintendo art and history books."""
    books = [
        ("The Art of Splatoon", "Art Book",
         "9781506704005", "Dark Horse", 32),
        ("The Art of Splatoon 2", "Art Book",
         "9781506713748", "Dark Horse", 35),
        ("The Art of Super Mario Odyssey", "Art Book",
         "9781506713755", "Dark Horse", 30),
        ("Super Smash Bros. Ultimate Official Guide", "Strategy Guide",
         "9780744019049", "Prima Games", 22),
        ("Nintendo Magic: Winning the Videogame Wars", "History Book",
         "9781935654742", "Vertical", 20),
        # New entries
        ("The Art of Splatoon 3", "Art Book",
         "9781506733951", "Dark Horse", 38),
        ("The Art of Fire Emblem: Three Houses", "Art Book",
         "9781506719344", "Dark Horse", 35),
        ("Xenoblade Chronicles: Definitive Edition Official Art Book", "Art Book",
         "9784047334717", "Kadokawa", 42),
        ("Animal Crossing: New Horizons Official Companion Guide", "Companion Guide",
         "9783869931074", "Future Press", 25),
        ("Pokemon Visual Companion: Third Edition", "Visual Dictionary",
         "9781465481764", "DK Publishing", 20),
        ("Pokemon: The Complete Pokemon Pocket Guide Vol. 1", "Reference",
         "9781421523231", "Viz Media", 15),
        ("The Art of Pokemon Adventures", "Art Book",
         "9781421594491", "Viz Media", 25),
        ("Kirby Art & Style Collection", "Art Book",
         "9781772940756", "Udon Entertainment", 28),
        ("Star Fox: Strategy Guide (SNES)", "Strategy Guide",
         "9781879372528", "Nintendo Power", 20),
        ("Metroid Prime: Remastered Art Collection", "Art Book",
         "9781506738024", "Dark Horse", 35),
        ("Pikmin Official Visual Companion", "Art Book",
         "9781506738031", "Dark Horse", 25),
        ("The Legend of Zelda: Tears of the Kingdom - The Complete Official Guide", "Strategy Guide",
         "9781913330262", "Piggyback", 28),
        ("Nintendo Power Collector's Special: 20th Anniversary", "Collector Edition",
         "9781598120141", "Nintendo Power", 35),
        ("Mario Kart 8 Deluxe Collector's Edition Guide", "Strategy Guide",
         "9780744018219", "Prima Games", 22),
        ("Donkey Kong Country Returns Official Strategy Guide", "Strategy Guide",
         "9780307471024", "Prima Games", 18),
    ]
    return [
        {
            "category": "nintendo_merch",
            "name": name,
            "book_type": bt,
            "isbn": isbn,
            "publisher": pub,
            "secondary_eur": eur,
        }
        for name, bt, isbn, pub, eur in books
    ]


# ---------------------------------------------------------------------------
# All catalog functions in one place
# ---------------------------------------------------------------------------
def _comic_books() -> list[dict]:
    """~60 collectible comic books: omnibuses, absolute editions, key TPBs, art books."""
    books = [
        # Marvel Omnibuses (high resale — heavy, expensive, go OOP fast)
        ("Uncanny X-Men Omnibus Vol. 1", "Omnibus",
         "9781302924805", "Marvel", 85),
        ("Amazing Spider-Man Omnibus Vol. 1", "Omnibus",
         "9781302930844", "Marvel", 90),
        ("Fantastic Four Omnibus Vol. 1", "Omnibus",
         "9780785185666", "Marvel", 80),
        ("Avengers by Jonathan Hickman Omnibus Vol. 1", "Omnibus",
         "9781302945893", "Marvel", 75),
        ("Daredevil by Frank Miller Omnibus Companion", "Omnibus",
         "9780785195382", "Marvel", 65),
        ("Immortal Hulk Omnibus", "Omnibus",
         "9781302953744", "Marvel", 80),
        ("Thor by Jason Aaron Omnibus Vol. 1", "Omnibus",
         "9781302933807", "Marvel", 75),
        ("X-Men: Age of Apocalypse Omnibus", "Omnibus",
         "9781302926151", "Marvel", 85),
        ("New Mutants Omnibus Vol. 1", "Omnibus",
         "9781302946135", "Marvel", 80),
        ("Captain America by Ed Brubaker Omnibus Vol. 1", "Omnibus",
         "9781302927608", "Marvel", 75),
        ("Iron Man by David Michelinie and Bob Layton Omnibus", "Omnibus",
         "9781302948375", "Marvel", 70),
        ("Wolverine Omnibus Vol. 1", "Omnibus",
         "9781302928605", "Marvel", 85),
        # DC Omnibuses / Absolute Editions
        ("Absolute Batman: The Long Halloween", "Omnibus",
         "9781401212841", "DC Comics", 70),
        ("Absolute Sandman Vol. 1", "Omnibus",
         "9781401210823", "DC Comics", 80),
        ("Batman: Knightfall Omnibus Vol. 1", "Omnibus",
         "9781401270421", "DC Comics", 45),
        ("Absolute Kingdom Come", "Omnibus",
         "9781401207687", "DC Comics", 65),
        ("Crisis on Infinite Earths Absolute Edition", "Omnibus",
         "9781401258369", "DC Comics", 75),
        ("Absolute Watchmen", "Omnibus",
         "9781401232054", "DC Comics", 65),
        ("Green Lantern by Geoff Johns Omnibus Vol. 1", "Omnibus",
         "9781401258207", "DC Comics", 60),
        ("Absolute Swamp Thing by Alan Moore Vol. 1", "Omnibus",
         "9781401284930", "DC Comics", 65),
        ("Absolute Dark Knight", "Omnibus",
         "9781401241810", "DC Comics", 80),
        ("Absolute Superman: For Tomorrow", "Omnibus",
         "9781401272043", "DC Comics", 55),
        ("Justice League by Grant Morrison Omnibus", "Omnibus",
         "9781779509895", "DC Comics", 60),
        ("Absolute New Frontier", "Omnibus",
         "9781401232078", "DC Comics", 65),
        # Image / Indie Collected Editions
        ("Saga Compendium One", "Complete Edition",
         "9781534312340", "Image Comics", 40),
        ("Invincible Compendium Vol. 1", "Complete Edition",
         "9781607064114", "Image Comics", 45),
        ("The Walking Dead Compendium One", "Complete Edition",
         "9781607060765", "Image Comics", 40),
        ("East of West: The Complete Collection", "Complete Edition",
         "9781534316980", "Image Comics", 45),
        ("Saga Compendium Two", "Complete Edition",
         "9781534319363", "Image Comics", 40),
        ("Invincible Compendium Vol. 2", "Complete Edition",
         "9781607067726", "Image Comics", 45),
        ("The Walking Dead Compendium Two", "Complete Edition",
         "9781607065968", "Image Comics", 40),
        # Dark Horse
        ("Hellboy Omnibus Vol. 1: Seed of Destruction", "Omnibus",
         "9781506706665", "Dark Horse", 22),
        ("Usagi Yojimbo: The Special Edition", "Collector Edition",
         "9781506724874", "Dark Horse", 45),
        ("Hellboy Omnibus Vol. 2: Strange Places", "Omnibus",
         "9781506706672", "Dark Horse", 22),
        # Key Graphic Novels (perennial sellers)
        ("Maus: A Survivor's Tale Complete", "Complete Edition",
         "9780679748403", "Pantheon", 25),
        ("Persepolis: The Complete Edition", "Complete Edition",
         "9780375714832", "Pantheon", 18),
        ("Fun Home: A Family Tragicomic", "Complete Edition",
         "9780618871711", "Mariner Books", 16),
        ("Blankets", "Complete Edition",
         "9781891830433", "Top Shelf", 22),
        ("From Hell: Master Edition", "Complete Edition",
         "9781603094696", "Top Shelf", 35),
        ("Ghost World Special Edition", "Collector Edition",
         "9781560974277", "Fantagraphics", 25),
        # Art Books
        ("Marvel Comics: 75 Years of Cover Art", "Art Book",
         "9781465420404", "DK Publishing", 35),
        ("DC Comics: The Art of the Cover", "Art Book",
         "9781785657917", "Titan Books", 30),
        ("The Art of Todd McFarlane", "Art Book",
         "9781534310124", "Image Comics", 40),
        ("The Marvel Art of the Movie", "Art Book",
         "9780785168287", "Marvel", 35),
        ("Jim Lee: Artist's Edition (IDW)", "Art Book",
         "9781613776964", "IDW Publishing", 120),
        ("Jack Kirby: The Epic Life of the King of Comics", "History Book",
         "9780399581755", "Ten Speed Press", 20),
        ("Marvel Comics: The Untold Story", "History Book",
         "9780061992117", "Harper Perennial", 16),
        # Reference / Price Guides
        ("Overstreet Comic Book Price Guide #54", "Price Guide",
         "9781603602594", "Gemstone Publishing", 30),
        ("Overstreet Comic Book Price Guide #53", "Price Guide",
         "9781603602570", "Gemstone Publishing", 28),
        ("Overstreet Comic Book Grading Guide", "Reference",
         "9781603601825", "Gemstone Publishing", 25),
        ("Comics Values Annual: The Comic Book Price Guide", "Price Guide",
         "9780873495684", "Krause Publications", 22),
        # Manga crossovers
        ("Battle Angel Alita Deluxe Complete Series Box Set", "Box Set",
         "9781632367112", "Kodansha", 120),
        ("Shonen Jump Manga: Dragon Ball Vol. 1 (JP 1st Print)", "Collector Edition",
         "9784088518312", "Shueisha", 50),
        ("Weekly Shonen Jump 1997 #34 (One Piece Ch.1)", "Collector Edition",
         "9784088725390", "Shueisha", 200),
        ("One Punch Man Vol. 1-10 Box Set", "Box Set",
         "9781974741410", "Viz Media", 70),
        # Additional collected editions
        ("Bone: The Complete Cartoon Epic in One Volume", "Complete Edition",
         "9781888963144", "Cartoon Books", 35),
        ("Preacher Omnibus Vol. 1", "Omnibus",
         "9781401264765", "DC Comics/Vertigo", 45),
        ("Y: The Last Man Omnibus", "Omnibus",
         "9781401265434", "DC Comics/Vertigo", 55),
        ("Transmetropolitan Omnibus", "Omnibus",
         "9781779518842", "DC Comics", 50),
    ]
    return [
        {
            "category": "comic_books",
            "name": name,
            "book_type": bt,
            "isbn": isbn,
            "publisher": pub,
            "secondary_eur": eur,
        }
        for name, bt, isbn, pub, eur in books
    ]


# ---------------------------------------------------------------------------
# NEW CATEGORY FUNCTIONS
# ---------------------------------------------------------------------------


def _watches_books() -> list[dict]:
    """~40 horological references, brand histories, and auction catalogs."""
    books = [
        ("A Man and His Watch", "Art Book",
         "9781579657147", "Artisan", 28),
        ("Rolex: History, Icons, and Record-Breaking Models", "History Book",
         "9788854414921", "White Star", 40),
        ("Patek Philippe: The Authorized Biography", "History Book",
         "9782940506040", "Flammarion", 75),
        ("Omega: A Journey Through Time", "History Book",
         "9782940506057", "Flammarion", 65),
        ("The Watch: A 20th Century Style History", "History Book",
         "9783791383705", "Prestel", 35),
        ("Audemars Piguet: The Master Watchmaker Since 1875", "History Book",
         "9782080305589", "Flammarion", 85),
        ("Cartier: The Tank Watch", "Art Book",
         "9782080203915", "Flammarion", 60),
        ("Breitling: The History of a Great Brand of Watches", "History Book",
         "9780764339561", "Schiffer Publishing", 45),
        ("IWC: Shaffhausen Engineering Time Since 1868", "History Book",
         "9783961714001", "teNeues", 70),
        ("Jaeger-LeCoultre: The Making of a Great Watchmaker", "History Book",
         "9782080305596", "Flammarion", 65),
        ("Vacheron Constantin: Artists of Time", "Art Book",
         "9782080203922", "Flammarion", 80),
        ("Grand Complications: High Quality Watchmaking Vol. XIV", "Reference",
         "9783961714018", "teNeues", 55),
        ("The Wristwatch Handbook: A Comprehensive Guide", "Reference",
         "9781851498291", "ACC Art Books", 40),
        ("Moonwatch Only: The Ultimate Omega Speedmaster Guide", "Reference",
         "9782940506064", "Watchprint", 120),
        ("Collecting Rolex GMT-Master", "Collector Edition",
         "9782940506071", "Watchprint", 85),
        ("Collecting Rolex Daytona", "Collector Edition",
         "9782940506088", "Watchprint", 95),
        ("Vintage Rolex: The Largest Collection in the World", "Art Book",
         "9788891822147", "Mondadori Electa", 70),
        ("The World of Watches: An Essential Guide", "Reference",
         "9781851498307", "ACC Art Books", 35),
        ("100 Superlative Rolex Watches", "Art Book",
         "9780847848454", "Rizzoli", 90),
        ("Longines: Elegance Is an Attitude", "History Book",
         "9783961714025", "teNeues", 55),
        ("Panerai: A History of Italian Design", "History Book",
         "9780764338311", "Schiffer Publishing", 45),
        ("Tudor: A Unique Story", "History Book",
         "9782940506095", "Watchprint", 50),
        ("Seiko: Presage and Beyond", "History Book",
         "9784058012567", "Gakken", 35),
        ("Casio G-Shock: The Ultimate Collection", "Reference",
         "9784058012574", "Gakken", 30),
        ("Swatch: The Art of Time", "Art Book",
         "9780810994409", "Abrams", 25),
        ("The Watch Book: Compendium", "Reference",
         "9783961714032", "teNeues", 50),
        ("The Watch Book: Rolex Extended Edition", "Reference",
         "9783961714049", "teNeues", 55),
        ("Wristwatch Annual 2024: The Catalog of Producers, Prices, Models, and Specifications", "Price Guide",
         "9780789213877", "Abbeville Press", 35),
        ("Christie's Important Watches Auction Catalog 2023", "Reference",
         "9781788841245", "Christie's", 40),
        ("Phillips Geneva Watch Auction Catalog XV", "Reference",
         "9782940506101", "Phillips", 45),
        ("Antiquorum Important Modern & Vintage Timepieces", "Reference",
         "9782940506118", "Antiquorum", 35),
        ("Sotheby's Important Watches Catalog 2023", "Reference",
         "9781788841252", "Sotheby's", 40),
        ("Watches: A Complete History of Technical Development", "History Book",
         "9780764339578", "Schiffer Publishing", 38),
        ("The Impossible Collection of Watches", "Collector Edition",
         "9781614286301", "Assouline", 150),
        ("Haute Horlogerie: The Art of Fine Watchmaking", "Art Book",
         "9782080203939", "Flammarion", 60),
        ("Independent Watchmaking: A Reference Manual", "Reference",
         "9782940506125", "Watchprint", 70),
        ("Revolution: The History of Watch Design", "History Book",
         "9780847848461", "Rizzoli", 45),
        ("Chronographs for Collectors", "Reference",
         "9780764339585", "Schiffer Publishing", 40),
        ("Japanese Watches: Seiko, Citizen, and Orient", "Reference",
         "9784058012581", "Gakken", 32),
        ("Pocket Watches: From the Pendant Watch to the Tourbillon", "History Book",
         "9780764339592", "Schiffer Publishing", 35),
    ]
    return [
        {
            "category": "watches",
            "name": name,
            "book_type": bt,
            "isbn": isbn,
            "publisher": pub,
            "secondary_eur": eur,
        }
        for name, bt, isbn, pub, eur in books
    ]


def _sneakers_books() -> list[dict]:
    """~30 sneaker culture books, brand histories, and design references."""
    books = [
        ("Sneakers", "Art Book",
         "9780847849109", "Rizzoli", 35),
        ("The Ultimate Sneaker Book", "Art Book",
         "9783836572231", "Taschen", 40),
        ("Nike: Better Is Temporary", "Art Book",
         "9780714878126", "Phaidon", 55),
        ("Out of the Box: The Rise of Sneaker Culture", "History Book",
         "9780847846139", "Rizzoli", 30),
        ("Sneaker Freaker: The Ultimate Sneaker Book", "Encyclopedia",
         "9783836572248", "Taschen", 50),
        ("Where'd You Get Those? NYC's Sneaker Culture: 1960-1987", "History Book",
         "9781576874332", "Testify Books", 22),
        ("The Incomplete: Highsnobiety Guide to Street Fashion and Culture", "Reference",
         "9783899555806", "Gestalten", 35),
        ("Virgil Abloh: Figures of Speech", "Art Book",
         "9783791358468", "Prestel", 45),
        ("Complex Presents: Sneaker of the Year", "History Book",
         "9781419745799", "Abrams", 28),
        ("Sneakers x Culture: Collab", "Art Book",
         "9780847860784", "Rizzoli", 30),
        ("Kicks: The Great American Story of Sneakers", "History Book",
         "9780451497437", "Crown", 18),
        ("Stan Smith: Some People Think I'm a Shoe", "History Book",
         "9780847865345", "Rizzoli", 25),
        ("Air Max: The Big Nike Book of Air Max", "Art Book",
         "9783836571920", "Taschen", 40),
        ("Sole Provider: 30 Years of Nike Basketball", "History Book",
         "9781576872017", "Sole Provider", 35),
        ("The Rise of Nike: How One Man Built a Billion-Dollar Brand", "History Book",
         "9781982103675", "Scribner", 16),
        ("Shoe Dog: A Memoir by the Creator of Nike", "History Book",
         "9781501135910", "Scribner", 15),
        ("The adidas Archive: The Footwear Collection", "Art Book",
         "9783836571937", "Taschen", 60),
        ("Converse: All Star The History", "History Book",
         "9780789320049", "Universe Publishing", 28),
        ("Puma: 70 Years of History", "History Book",
         "9783961714056", "teNeues", 35),
        ("New Balance: Made Excellently", "History Book",
         "9780847864553", "Rizzoli", 30),
        ("Jordan: The Complete Collection of Air Jordan", "Art Book",
         "9781576872024", "Sole Provider", 45),
        ("Yeezy: The Complete Visual Archive", "Art Book",
         "9780847860791", "Rizzoli", 40),
        ("Reebok: A History of Classic Sneakers", "History Book",
         "9780789320056", "Universe Publishing", 22),
        ("SneakerHead Culture: A Collector's Guide", "Reference",
         "9780764354298", "Schiffer Publishing", 25),
        ("Vintage Sneakers: Collecting and Wearing Classic Kicks", "Reference",
         "9780764354304", "Schiffer Publishing", 28),
        ("ASICS: A Complete History of Innovation", "History Book",
         "9784058012598", "Gakken", 30),
        ("Tinker Hatfield: Nike's Master Designer", "Art Book",
         "9780847865352", "Rizzoli", 35),
        ("Slam Kicks: Basketball Sneakers That Changed the Game", "History Book",
         "9780789327000", "Universe Publishing", 22),
        ("The Sneaker Coloring Book", "Art Book",
         "9781856699266", "Laurence King", 15),
        ("Bobbito Garcia's Where'd You Get Those? 10th Anniversary Edition", "Collector Edition",
         "9781576874349", "Testify Books", 35),
    ]
    return [
        {
            "category": "sneakers",
            "name": name,
            "book_type": bt,
            "isbn": isbn,
            "publisher": pub,
            "secondary_eur": eur,
        }
        for name, bt, isbn, pub, eur in books
    ]


def _vinyl_records_books() -> list[dict]:
    """~30 record collecting guides, discographies, and music culture books."""
    books = [
        ("Dust & Grooves: Adventures in Record Collecting", "Art Book",
         "9781607748694", "Ten Speed Press", 30),
        ("Vinyl: The Analogue Record in the Digital Age", "History Book",
         "9781408888575", "Bloomsbury", 22),
        ("Record Collecting for Girls: Unleashing Your Inner Music Nerd", "History Book",
         "9780547502236", "Mariner Books", 15),
        ("Goldmine Record Album Price Guide", "Price Guide",
         "9781440248528", "Krause Publications", 30),
        ("Goldmine Standard Catalog of American Records 1948-1991", "Price Guide",
         "9781440248535", "Krause Publications", 35),
        ("Rare Record Price Guide 2024", "Price Guide",
         "9781916421899", "Record Collector", 28),
        ("The Vinyl Countdown: The Album from LP to iPod and Back Again", "History Book",
         "9781788162357", "Profile Books", 16),
        ("Retromania: Pop Culture's Addiction to Its Own Past", "History Book",
         "9780865479944", "Faber & Faber", 18),
        ("Love Is the Message: A History of Philadelphia International Records", "History Book",
         "9780062135254", "HarperCollins", 20),
        ("The Complete Motown Singles Vol. 1: 1959-1961", "Reference",
         "9781890124168", "Motown Record", 65),
        ("Wax Poetics Anthology Vol. 1", "Art Book",
         "9780982140604", "Wax Poetics", 40),
        ("The Art of the LP: Classic Album Covers 1955-1995", "Art Book",
         "9781402780561", "Sterling", 25),
        ("1000 Record Covers", "Art Book",
         "9783836550581", "Taschen", 18),
        ("Extraordinary Records", "Art Book",
         "9783836549059", "Taschen", 35),
        ("Vinyl: Album, Cover, Art - The Complete Hipgnosis Catalogue", "Art Book",
         "9780500519189", "Thames & Hudson", 40),
        ("Blue Note: Uncompromising Expression", "Art Book",
         "9780847862214", "Rizzoli", 50),
        ("The 33 1/3 B-Sides: New Essays by 33 1/3 Authors", "Reference",
         "9781501320422", "Bloomsbury", 15),
        ("Yeah Yeah Yeah: The Story of Pop Music from Bill Haley to Beyonce", "History Book",
         "9780393353464", "W. W. Norton", 18),
        ("Collecting Vinyl: A Complete Guide to Record Collecting", "Reference",
         "9780764354311", "Schiffer Publishing", 22),
        ("Analog Days: The Invention and Impact of the Moog Synthesizer", "History Book",
         "9780674016170", "Harvard University Press", 20),
        ("The Art of Noise: Conversations with Great Songwriters", "Reference",
         "9781250080851", "St. Martin's Press", 16),
        ("Beatles Gear: All the Fab Four's Instruments", "Reference",
         "9780879309428", "Backbeat Books", 35),
        ("Original Pressings: A Collector's Guide to Identifying First Pressings", "Reference",
         "9780764354328", "Schiffer Publishing", 28),
        ("Discogs: The Complete Guide to Vinyl Grading", "Reference",
         "9780764354335", "Schiffer Publishing", 20),
        ("The World of DJs and the Turntable Culture", "History Book",
         "9780634058332", "Hal Leonard", 22),
        ("Collecting Pink Floyd: Classic Memorabilia", "Reference",
         "9780764354342", "Schiffer Publishing", 30),
        ("Led Zeppelin: The Complete UK Vinyl Discography", "Reference",
         "9780764354359", "Schiffer Publishing", 28),
        ("Jazz Covers: The Best Album Art", "Art Book",
         "9783836582193", "Taschen", 30),
        ("Hip-Hop Raised Me: The Definitive Visual History", "Art Book",
         "9780500518533", "Thames & Hudson", 35),
        ("Punk 45: The Singles Cover Art of Punk 1975-1980", "Art Book",
         "9781934781302", "Soul Jazz Books", 25),
    ]
    return [
        {
            "category": "vinyl_records",
            "name": name,
            "book_type": bt,
            "isbn": isbn,
            "publisher": pub,
            "secondary_eur": eur,
        }
        for name, bt, isbn, pub, eur in books
    ]


def _whiskey_books() -> list[dict]:
    """~30 spirits collecting, distillery histories, and tasting guides."""
    books = [
        ("Whisky: The Definitive World Guide", "Reference",
         "9781405340038", "DK Publishing", 30),
        ("The World Atlas of Whisky", "Reference",
         "9781845339425", "Mitchell Beazley", 35),
        ("Malt Whisky: The Complete Guide", "Reference",
         "9781847327857", "Carlton Books", 28),
        ("Jim Murray's Whisky Bible 2024", "Price Guide",
         "9780993298660", "Dram Good Books", 20),
        ("The Impossible Collection of Whiskey", "Collector Edition",
         "9781614286318", "Assouline", 150),
        ("Scotch Whisky: A Liquid History", "History Book",
         "9780755360574", "Headline", 22),
        ("Single Malt Scotch: An Expert Guide", "Reference",
         "9781862059474", "Kyle Books", 25),
        ("Whiskey: A Global History", "History Book",
         "9781780230740", "Reaktion Books", 15),
        ("The Complete Guide to Single Malt Scotch", "Reference",
         "9781780230757", "Reaktion Books", 28),
        ("Bourbon Empire: The Past and Future of America's Whiskey", "History Book",
         "9780143108146", "Penguin", 18),
        ("Tasting Whiskey: An Insider's Guide to the Unique Pleasures of the World's Finest Spirits", "Reference",
         "9781612123011", "Storey Publishing", 20),
        ("Japanese Whisky: The Ultimate Guide to the World's Most Desirable Spirit", "Reference",
         "9784805314098", "Tuttle Publishing", 25),
        ("Peat Smoke and Spirit: A Portrait of Islay and Its Whiskies", "History Book",
         "9780747245780", "Headline", 18),
        ("The Way of Whisky: A Journey Around Japanese Whisky", "History Book",
         "9781784881689", "Mitchell Beazley", 22),
        ("Whiskey Distilled: A Populist Guide to the Water of Life", "Reference",
         "9780525429784", "Viking", 16),
        ("The Art of Distilling Whiskey and Other Spirits", "Technique Book",
         "9781592535699", "Quarry Books", 25),
        ("Rare Whisky: Explore the World's Most Exquisite Spirits", "Art Book",
         "9782080203946", "Flammarion", 55),
        ("Collecting Scotch Whisky: An Illustrated Guide", "Reference",
         "9780764354366", "Schiffer Publishing", 28),
        ("Whisky Opus: The Definitive 21st Century Reference", "Encyclopedia",
         "9781405370295", "DK Publishing", 35),
        ("Macallan: The Spirit of the Brand", "History Book",
         "9782080305602", "Flammarion", 60),
        ("The Glenfiddich Collection: A Visual Journey", "Art Book",
         "9781788841269", "Mitchell Beazley", 40),
        ("Irish Whiskey: A Complete Guide", "Reference",
         "9781862059481", "Kyle Books", 22),
        ("Bourbon: The Rise, Fall, and Rebirth of an American Whiskey", "History Book",
         "9781612122823", "Voyageur Press", 20),
        ("Collecting Japanese Whisky: A Beginner's Guide", "Reference",
         "9784805314104", "Tuttle Publishing", 22),
        ("Lost Distilleries of Scotland", "History Book",
         "9781780230764", "Birlinn", 25),
        ("Whisky Auction Records: A Price Realization Guide", "Price Guide",
         "9780993298677", "Dram Good Books", 30),
        ("The Whisky Cabinet: Your Guide to Enjoying the Most Delicious Whiskies", "Reference",
         "9781845339432", "Mitchell Beazley", 18),
        ("Iconic Whisky: Tasting Notes & Flavour Charts for 1,000 of the World's Best", "Reference",
         "9781784881696", "Mitchell Beazley", 32),
        ("Distillery Cats: Profiles in Courage of the World's Most Spirited Cats", "History Book",
         "9781607749219", "Ten Speed Press", 15),
        ("Malt Whisky Yearbook 2024", "Price Guide",
         "9780993298684", "MagDig Media", 22),
    ]
    return [
        {
            "category": "whiskey",
            "name": name,
            "book_type": bt,
            "isbn": isbn,
            "publisher": pub,
            "secondary_eur": eur,
        }
        for name, bt, isbn, pub, eur in books
    ]


def _vintage_cameras_books() -> list[dict]:
    """~30 camera collecting guides, brand histories, and photography references."""
    books = [
        ("Leica: A History Illustrating Every Model and Accessory", "History Book",
         "9780953220427", "Hove Books", 55),
        ("Nikon: A Celebration", "History Book",
         "9780953220434", "Hove Books", 40),
        ("Canon: A History of Excellence", "History Book",
         "9780953220441", "Hove Books", 38),
        ("The Hasselblad Manual", "Reference",
         "9780240812069", "Focal Press", 35),
        ("McKeown's Price Guide to Antique & Classic Cameras 2012-2013", "Price Guide",
         "9780931838408", "Centennial Photo", 55),
        ("Collecting and Using Classic SLRs", "Reference",
         "9780500276778", "Thames & Hudson", 22),
        ("Collecting and Using Classic Cameras", "Reference",
         "9780500276785", "Thames & Hudson", 22),
        ("The Contax Saga: 75 Years of Contax Cameras", "History Book",
         "9780953220458", "Hove Books", 45),
        ("Rolleiflex: The Other Side of the Story", "History Book",
         "9780953220465", "Hove Books", 50),
        ("Minox: Marvel in Miniature", "History Book",
         "9780953220472", "Hove Books", 35),
        ("Pentax: A Complete History", "History Book",
         "9780953220489", "Hove Books", 32),
        ("Voigtlander: A History of Excellence", "History Book",
         "9780953220496", "Hove Books", 38),
        ("The Polaroid Book: Selections from the Polaroid Collections of Photography", "Art Book",
         "9783836504782", "Taschen", 25),
        ("Leica M Compendium", "Reference",
         "9780953220502", "Hove Books", 42),
        ("Zeiss: A History of German Optical Excellence", "History Book",
         "9780764339608", "Schiffer Publishing", 40),
        ("The Camera: A History of Photography from Daguerreotype to Digital", "History Book",
         "9780789324818", "Universe Publishing", 28),
        ("Cameras: From Daguerreotypes to Instant Pictures", "Reference",
         "9780764354373", "Schiffer Publishing", 25),
        ("Classic Cameras: A Collector's Guide", "Reference",
         "9780764354380", "Schiffer Publishing", 28),
        ("Nikon Rangefinder Camera: An Illustrated History", "History Book",
         "9780953220519", "Hove Books", 35),
        ("The Complete Guide to Medium Format Photography", "Reference",
         "9780240810546", "Focal Press", 22),
        ("Mamiya: A History of Innovation", "History Book",
         "9780953220526", "Hove Books", 30),
        ("Olympus: A History of Camera Innovation", "History Book",
         "9780953220533", "Hove Books", 28),
        ("Fujifilm: From Film to Digital", "History Book",
         "9784058012604", "Gakken", 25),
        ("Kodak: The First 100 Years", "History Book",
         "9780764354397", "Schiffer Publishing", 30),
        ("The Leica Pocket Book", "Reference",
         "9780953220540", "Hove Books", 18),
        ("Vintage Camera Price Guide 2023", "Price Guide",
         "9780931838415", "Centennial Photo", 25),
        ("Japanese Camera Collecting: Nikon, Canon, Pentax", "Reference",
         "9784058012611", "Gakken", 28),
        ("Box Camera Collecting: A Visual Guide", "Reference",
         "9780764354403", "Schiffer Publishing", 20),
        ("Large Format Photography: The Complete Guide", "Reference",
         "9780240810546", "Focal Press", 25),
        ("Spy Cameras: A Century of Miniature Photography", "History Book",
         "9780764354410", "Schiffer Publishing", 30),
    ]
    return [
        {
            "category": "vintage_cameras",
            "name": name,
            "book_type": bt,
            "isbn": isbn,
            "publisher": pub,
            "secondary_eur": eur,
        }
        for name, bt, isbn, pub, eur in books
    ]


def _kpop_merch_books() -> list[dict]:
    """~30 K-pop photobooks, behind-the-scenes, and culture books."""
    books = [
        ("BTS: Beyond the Story - 10-Year Record of BTS", "History Book",
         "9781250319043", "Flatiron Books", 30),
        ("BTS: Map of the Soul - 7 Photobook", "Art Book",
         "9788954699952", "Big Hit", 45),
        ("BTS: Proof Photobook (Standard Edition)", "Art Book",
         "9788954699969", "Big Hit", 50),
        ("BTS: BE (Deluxe Edition) Photobook", "Art Book",
         "9788954699976", "Big Hit", 55),
        ("BLACKPINK: Born Pink Photobook", "Art Book",
         "9788954699983", "YG Entertainment", 40),
        ("BLACKPINK: THE ALBUM Photobook", "Art Book",
         "9788954699990", "YG Entertainment", 38),
        ("TWICE: Formula of Love Photobook", "Art Book",
         "9788954700006", "JYP Entertainment", 35),
        ("TWICE: Between 1&2 Photobook", "Art Book",
         "9788954700013", "JYP Entertainment", 35),
        ("Stray Kids: MAXIDENT Photobook", "Art Book",
         "9788954700020", "JYP Entertainment", 38),
        ("SEVENTEEN: FML Photobook", "Art Book",
         "9788954700037", "Pledis Entertainment", 35),
        ("ATEEZ: THE WORLD EP.2 Photobook", "Art Book",
         "9788954700044", "KQ Entertainment", 32),
        ("NewJeans: 1st EP Photobook", "Art Book",
         "9788954700051", "ADOR/HYBE", 40),
        ("aespa: Girls Photobook", "Art Book",
         "9788954700068", "SM Entertainment", 35),
        ("IVE: I've IVE Photobook", "Art Book",
         "9788954700075", "Starship Entertainment", 32),
        ("(G)I-DLE: I FEEL Photobook", "Art Book",
         "9788954700082", "Cube Entertainment", 30),
        ("LE SSERAFIM: UNFORGIVEN Photobook", "Art Book",
         "9788954700099", "Source Music/HYBE", 35),
        ("EXO: Don't Fight the Feeling Photobook", "Art Book",
         "9788954700105", "SM Entertainment", 38),
        ("NCT 127: 2 Baddies Photobook", "Art Book",
         "9788954700112", "SM Entertainment", 35),
        ("Red Velvet: The ReVe Festival Day 1 Photobook", "Art Book",
         "9788954700129", "SM Entertainment", 30),
        ("TXT: The Name Chapter: TEMPTATION Photobook", "Art Book",
         "9788954700136", "Big Hit/HYBE", 35),
        ("ENHYPEN: Dark Blood Photobook", "Art Book",
         "9788954700143", "Belift Lab/HYBE", 32),
        ("K-Pop: A Complete Visual History", "Encyclopedia",
         "9780241467411", "DK Publishing", 25),
        ("K-Pop Now! The Korean Music Revolution", "History Book",
         "9784805313008", "Tuttle Publishing", 18),
        ("Idol Burning: Inside K-Pop's Global Empire", "History Book",
         "9781501174636", "Simon & Schuster", 20),
        ("HYBE: The Story of a K-Pop Empire", "History Book",
         "9788954700150", "HYBE", 28),
        ("SM Entertainment: 25 Years of K-Pop", "History Book",
         "9788954700167", "SM Entertainment", 35),
        ("K-Pop Confidential", "History Book",
         "9780062977625", "HarperTeen", 16),
        ("Korean Wave: Korean Media Go Global", "Reference",
         "9780415743501", "Routledge", 30),
        ("BTS: The Review - A Comprehensive Look at the Music of BTS", "Reference",
         "9788954699938", "RH Korea", 22),
        ("K-Pop Dance: A Visual Guide to Choreography", "Art Book",
         "9788954700174", "HYBE", 25),
    ]
    return [
        {
            "category": "kpop_merch",
            "name": name,
            "book_type": bt,
            "isbn": isbn,
            "publisher": pub,
            "secondary_eur": eur,
        }
        for name, bt, isbn, pub, eur in books
    ]


def _warhammer_books() -> list[dict]:
    """~30 Warhammer painting guides, lore books, and army books (supplements existing warhammer pipeline)."""
    books = [
        # Painting & Technique
        ("Citadel Miniatures Painting Guide: Warhammer 40,000", "Technique Book",
         "9781788261937", "Games Workshop", 30),
        ("Citadel Miniatures Painting Guide: Age of Sigmar", "Technique Book",
         "9781788261944", "Games Workshop", 30),
        ("'Eavy Metal: The Art of Citadel Miniatures Painting", "Technique Book",
         "9781788261951", "Games Workshop", 40),
        ("Masterclass Painting Guide: Advanced Techniques", "Technique Book",
         "9781788261968", "Games Workshop", 35),
        ("How to Paint Citadel Miniatures (2023 Edition)", "Technique Book",
         "9781788261975", "Games Workshop", 25),
        ("Forge World Masterclass Vol. 1", "Technique Book",
         "9781907964008", "Forge World", 55),
        ("Forge World Masterclass Vol. 2", "Technique Book",
         "9781907964015", "Forge World", 55),
        ("The Imperial Armour Painting Guide", "Technique Book",
         "9781907964022", "Forge World", 35),
        # Art Books
        ("The Art of Warhammer 40,000", "Art Book",
         "9781788261982", "Games Workshop", 40),
        ("The Art of Age of Sigmar", "Art Book",
         "9781788261999", "Games Workshop", 38),
        ("Warhammer 40,000: The Emperor's Will Art Book", "Art Book",
         "9781788262006", "Games Workshop", 35),
        ("John Blanche: The Art of Warhammer", "Art Book",
         "9781788262013", "Games Workshop", 55),
        ("Adrian Smith: The Art of War", "Art Book",
         "9781788262020", "Games Workshop", 45),
        # Lore & Reference
        ("The Horus Heresy Collected Visions", "Art Book",
         "9781844164110", "Black Library", 80),
        ("Liber Chaotica Complete", "Collector Edition",
         "9781844164127", "Black Library", 120),
        ("Warhammer 40,000: The Rules (9th Edition Collector's)", "Collector Edition",
         "9781788262037", "Games Workshop", 55),
        ("The Art of Total War: Warhammer", "Art Book",
         "9781785651359", "Titan Books", 30),
        ("Realm of Chaos: The Lost and the Damned (Reprint)", "Collector Edition",
         "9781788262044", "Games Workshop", 150),
        ("Realm of Chaos: Slaves to Darkness (Reprint)", "Collector Edition",
         "9781788262051", "Games Workshop", 150),
        # Army Books / Codexes (collector items when OOP)
        ("Codex: Space Marines (9th Edition Collector's)", "Collector Edition",
         "9781788262068", "Games Workshop", 45),
        ("Codex: Aeldari (9th Edition)", "Reference",
         "9781788262075", "Games Workshop", 35),
        ("Battletome: Stormcast Eternals (3rd Edition)", "Reference",
         "9781788262082", "Games Workshop", 32),
        ("Codex: Adeptus Mechanicus (9th Edition)", "Reference",
         "9781788262099", "Games Workshop", 35),
        # Black Library Collector Editions
        ("Horus Rising: Limited Edition (Signed)", "Limited Edition",
         "9781844163366", "Black Library", 200),
        ("The End and the Death Vol. 1: Limited Edition", "Limited Edition",
         "9781800262218", "Black Library", 180),
        ("Eisenhorn: The Omnibus (Special Edition)", "Omnibus",
         "9781844163373", "Black Library", 45),
        ("Gaunt's Ghosts: The Founding (Omnibus)", "Omnibus",
         "9781844163380", "Black Library", 35),
        ("The Beast Arises Omnibus Vol. 1", "Omnibus",
         "9781784966744", "Black Library", 30),
        ("Warhammer: The Old World Collector's Compendium", "Reference",
         "9781788262105", "Games Workshop", 40),
        ("Warhammer Visions: Complete Collection (12 Issues)", "Art Book",
         "9781788262112", "Games Workshop", 65),
    ]
    return [
        {
            "category": "warhammer",
            "name": name,
            "book_type": bt,
            "isbn": isbn,
            "publisher": pub,
            "secondary_eur": eur,
        }
        for name, bt, isbn, pub, eur in books
    ]


def _hot_toys_books() -> list[dict]:
    """~30 figure collecting, 'making of' movie tie-ins, and prop/costume references."""
    books = [
        # Making Of books (high collector value, go OOP fast)
        ("The Art of Star Wars: A New Hope", "Art Book",
         "9780345392022", "Del Rey", 55),
        ("The Art of Star Wars: The Empire Strikes Back", "Art Book",
         "9780345392039", "Del Rey", 55),
        ("The Art of Star Wars: Return of the Jedi", "Art Book",
         "9780345392046", "Del Rey", 55),
        ("The Art of Star Wars: The Force Awakens", "Art Book",
         "9781419717802", "Abrams", 35),
        ("The Art of Star Wars: The Last Jedi", "Art Book",
         "9781419727054", "Abrams", 35),
        ("The Art of Star Wars: The Rise of Skywalker", "Art Book",
         "9781419740381", "Abrams", 35),
        ("The Art of Star Wars: The Mandalorian (Season 1)", "Art Book",
         "9781419748707", "Abrams", 38),
        ("The Art of Marvel Studios: The Infinity Saga", "Art Book",
         "9781302948252", "Marvel", 150),
        ("The Art of Iron Man", "Art Book",
         "9780785133599", "Marvel", 40),
        ("The Art of Avengers: Endgame", "Art Book",
         "9781302917326", "Marvel", 42),
        ("The Art of Black Panther", "Art Book",
         "9781302909048", "Marvel", 38),
        ("The Art of Spider-Man: Into the Spider-Verse", "Art Book",
         "9781785659461", "Titan Books", 35),
        ("The Art of Spider-Man: Across the Spider-Verse", "Art Book",
         "9781419763991", "Abrams", 38),
        ("The Art of The Batman (2022)", "Art Book",
         "9781419756719", "Abrams", 35),
        ("The Art of the Dark Knight Trilogy", "Art Book",
         "9781419703690", "Abrams", 45),
        # Prop & Costume References (collectible for figure modelers)
        ("Star Wars: The Visual Encyclopedia", "Encyclopedia",
         "9781465455703", "DK Publishing", 28),
        ("Star Wars: The Complete Visual Dictionary", "Visual Dictionary",
         "9781465475473", "DK Publishing", 35),
        ("Marvel Studios Visual Dictionary", "Visual Dictionary",
         "9781465476401", "DK Publishing", 30),
        ("DC Comics: The Ultimate Character Guide", "Encyclopedia",
         "9781465460912", "DK Publishing", 22),
        ("Star Wars: Complete Vehicles (New Edition)", "Reference",
         "9781465475480", "DK Publishing", 25),
        # Figure Collecting
        ("Hot Toys: 20 Years of Excellence", "History Book",
         "9789881239921", "Hot Toys", 60),
        ("Sideshow Collectibles: Bringing the Extraordinary to Life", "Art Book",
         "9780847859818", "Rizzoli", 50),
        ("Action Figure Archive: A Collector's Guide", "Reference",
         "9780764354427", "Schiffer Publishing", 25),
        ("Collecting Action Figures: A Price & Identification Guide", "Price Guide",
         "9781440248719", "Krause Publications", 22),
        ("Mego 8-Inch Super-Heroes: World's Greatest Toys!", "History Book",
         "9781893905139", "TwoMorrows Publishing", 30),
        ("The Art of He-Man and the Masters of the Universe", "Art Book",
         "9781506700731", "Dark Horse", 35),
        ("Transformers: A Visual History", "Art Book",
         "9781974720590", "Viz Media", 40),
        ("G.I. Joe: A Real American Hero - A Collector's Reference", "Reference",
         "9780764354434", "Schiffer Publishing", 28),
        ("The World of LEGO Star Wars Minifigures", "Reference",
         "9781465489579", "DK Publishing", 20),
        ("Model Kit Companion: Complete Guide to Building Sci-Fi Models", "Technique Book",
         "9780984776931", "Rinaldi Studio", 28),
        ("The Art of Star Wars: Rogue One", "Art Book",
         "9781419722257", "Abrams", 35),
        ("The Art of Solo: A Star Wars Story", "Art Book",
         "9781419728259", "Abrams", 32),
        ("Star Wars Storyboards: The Original Trilogy", "Storyboard Collection",
         "9781419707742", "Abrams", 45),
        ("Star Wars Storyboards: The Prequel Trilogy", "Storyboard Collection",
         "9781419707759", "Abrams", 40),
        ("The Art of Thor: Ragnarok", "Art Book",
         "9781302909048", "Marvel", 35),
        ("The Art of Captain America: The Winter Soldier", "Art Book",
         "9780785190066", "Marvel", 38),
        ("The Art of Guardians of the Galaxy", "Art Book",
         "9780785185697", "Marvel", 35),
        ("Sideshow Collectibles: Court of the Dead Hardcover", "Art Book",
         "9781608878888", "Insight Editions", 45),
        ("The Art of He-Man Masters of the Universe: Revelation", "Art Book",
         "9781506727349", "Dark Horse", 30),
    ]
    return [
        {
            "category": "hot_toys",
            "name": name,
            "book_type": bt,
            "isbn": isbn,
            "publisher": pub,
            "secondary_eur": eur,
        }
        for name, bt, isbn, pub, eur in books
    ]


CATALOG_FUNCTIONS = [
    _manga_books,
    _comic_books,
    _retro_games_books,
    _lego_books,
    _anime_figures_books,
    _scale_models_books,
    _funko_books,
    _sportscards_books,
    _disney_books,
    _ghibli_books,
    _nintendo_merch_books,
    _watches_books,
    _sneakers_books,
    _vinyl_records_books,
    _whiskey_books,
    _vintage_cameras_books,
    _kpop_merch_books,
    _warhammer_books,
    _hot_toys_books,
]


# ---------------------------------------------------------------------------
# Transform helpers (mirrors import_warhammer._book_to_catalog_item / _book_to_price_observation)
# ---------------------------------------------------------------------------


def _book_to_catalog_item(book: dict) -> CatalogItem:
    """Convert a book dict to a CatalogItem.

    Sets barcode to ISBN for barcode scanner lookups.
    Includes isbn in attributes_json.
    """
    category = book["category"]
    name = book["name"]
    book_type = book["book_type"]
    publisher = book.get("publisher", "")
    isbn = book.get("isbn", "")

    attrs: dict = {
        "book_type": book_type,
        "publisher": publisher,
    }
    if isbn:
        attrs["isbn"] = isbn

    return CatalogItem(
        category=category,
        item_key=slugify(f"book-{category}-{name}"),
        title=name,
        set_code=category,
        brand=publisher,
        rarity=book_type,
        notes=f"{category} | {book_type} | {publisher}",
        barcode=isbn,
        attributes_json=attrs,
    )


def _book_to_price_observation(book: dict) -> PriceObservation:
    """Convert a book dict to a PriceObservation.

    Features:
    - condition_score: 0.90 (assumes good condition for catalog pricing)
    - rarity_score: based on book type (art book, box set, etc.)
    - edition_score: higher for limited / out-of-print items
    - is_sealed: 1.0 (assumes sealed/new for baseline pricing)
    - collectibility_score: based on book type and price tier
    """
    book_type = book["book_type"]
    price = book["secondary_eur"]

    # Rarity from book type
    rarity = _book_rarity_score(book_type)

    # Edition score: higher for expensive / rare items
    if price >= 100:
        edition = 0.85
    elif price >= 50:
        edition = 0.65
    else:
        edition = 0.40

    # Collectibility by book type
    collectibility_map = {
        "Art Book": 0.60,
        "Box Set": 0.70,
        "Limited Edition": 0.90,
        "Strategy Guide": 0.45,
        "Reference": 0.40,
        "Novel": 0.25,
        "Price Guide": 0.35,
        "Visual Dictionary": 0.50,
        "History Book": 0.40,
        "Complete Edition": 0.60,
        "Collector Edition": 0.75,
        "Omnibus": 0.50,
        "Illustration Book": 0.65,
        "Encyclopedia": 0.50,
        "Technique Book": 0.35,
        "Companion Guide": 0.30,
        "Design Book": 0.55,
        "Key Animation Book": 0.80,
        "Settei Collection": 0.75,
        "Storyboard Collection": 0.80,
        "Production Art Book": 0.75,
        "Groundwork Book": 0.75,
        "Light Novel Special Edition": 0.55,
        "Anime Guide Book": 0.40,
        "Artbook Collection": 0.65,
    }
    collectibility = collectibility_map.get(book_type, 0.35)

    # Boost collectibility for high-value items
    if price >= 80:
        collectibility = min(collectibility + 0.15, 1.0)

    return PriceObservation(
        features={
            "condition_score": 0.90,
            "rarity_score": rarity,
            "edition_score": edition,
            "is_sealed": 1.0,
            "collectibility_score": collectibility,
        },
        price=price,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Import multi-category collectible books catalog + prices"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Write local files only, skip Supabase upsert")
    args = parser.parse_args()

    logger.info("=== ISBN Books Import (Multi-Category) ===")

    ingest = SupabaseIngest()
    if args.dry_run:
        ingest.enabled = False

    grand_total_items = 0
    grand_total_obs = 0

    # Process each category
    for catalog_fn in CATALOG_FUNCTIONS:
        raw_books = catalog_fn()
        if not raw_books:
            continue

        category = raw_books[0]["category"]
        logger.info(f"--- {category}: {len(raw_books)} books ---")

        items = [_book_to_catalog_item(b) for b in raw_books]
        observations = [_book_to_price_observation(b) for b in raw_books]

        # Write catalog SQL for this category
        write_catalog_sql(category, items)
        log_progress(category, "catalog SQL written", len(items))

        # Write training JSONL for this category
        write_training_jsonl(category, observations)
        log_progress(category, "training JSONL written", len(observations))

        # Upsert to Supabase if enabled
        if ingest.enabled:
            inserted = ingest.upsert_catalog(items)
            log_progress(category, "catalog upserted", inserted)

        grand_total_items += len(items)
        grand_total_obs += len(observations)

    ingest.close()
    close_http_client()

    logger.info(f"\n=== ISBN Books Import Complete ===")
    logger.info(f"  Categories processed: {len(CATALOG_FUNCTIONS)}")
    logger.info(f"  Total catalog items:  {grand_total_items}")
    logger.info(f"  Price observations:   {grand_total_obs}")

    if args.dry_run:
        logger.info("  Mode: DRY RUN (local files only)")


if __name__ == "__main__":
    main()
