"""
Bulk ISBN Book Import Pipeline — Multi-Category Collectible Books.

Imports curated book catalogs for collectible books across 11 categories:
  manga, anime_figures, ghibli, comic_books (NEW),
  retro_games, lego, scale_models, funko, sportscards, disney, nintendo_merch

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
    """~30 collector edition manga: box sets, art books, deluxe editions."""
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
        # Deluxe / Complete Editions
        ("Berserk Deluxe Edition Vol. 1", "Complete Edition",
         "9781506711980", "Dark Horse", 42),
        ("Berserk Deluxe Edition Vol. 2", "Complete Edition",
         "9781506712000", "Dark Horse", 42),
        ("Berserk Deluxe Edition Vol. 3", "Complete Edition",
         "9781506712017", "Dark Horse", 42),
        ("Vinland Saga Deluxe Vol. 1", "Complete Edition",
         "9781646516704", "Kodansha", 40),
        ("Vagabond VIZBIG Edition Vol. 1", "Complete Edition",
         "9781421520544", "Viz Media", 25),
        ("Fullmetal Alchemist Fullmetal Edition Vol. 1", "Complete Edition",
         "9781421599786", "Viz Media", 22),
        ("Uzumaki 3-in-1 Deluxe Edition", "Complete Edition",
         "9781421561325", "Viz Media", 28),
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
        ("Blame! Master Edition Vol. 1", "Complete Edition",
         "9781942993773", "Vertical", 30),
        ("20th Century Boys: The Perfect Edition Vol. 1", "Complete Edition",
         "9781421599618", "Viz Media", 20),
        ("Monster: The Perfect Edition Vol. 1", "Complete Edition",
         "9781421569062", "Viz Media", 18),
        # More Box Sets
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
        ("Fruits Basket Collector's Edition Vol. 1", "Collector Edition",
         "9780316360166", "Yen Press", 18),
        ("Sailor Moon Eternal Edition Vol. 1", "Collector Edition",
         "9781632369529", "Kodansha", 25),
        # OOP / High-Value Singles
        ("Goodnight Punpun Vol. 1", "Complete Edition",
         "9781421586205", "Viz Media", 15),
        ("Slam Dunk Vol. 1", "Complete Edition",
         "9781421506791", "Viz Media", 12),
        ("Pluto: Urasawa x Tezuka Vol. 1", "Complete Edition",
         "9781421519180", "Viz Media", 14),
        ("Dorohedoro Vol. 1", "Complete Edition",
         "9781421533636", "Viz Media", 14),
        # More Art Books
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
    """~20 retro gaming strategy guides, art books, and history books."""
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
    """~15 LEGO art books, idea books, and DK visual dictionaries."""
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
    """~35 anime art books, production art, key animation, and design references."""
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
        # Kyoto Animation
        ("Violet Evergarden: Chronicles of Letters", "Illustration Book",
         "9784907064778", "Kyoto Animation", 65),
        ("Free! Illustration Works Vol. 1", "Illustration Book",
         "9784907064457", "Kyoto Animation", 45),
        ("A Silent Voice Official Fan Book", "Art Book",
         "9784063955514", "Kodansha", 30),
        # MAPPA / Modern Studios
        ("Jujutsu Kaisen KEY ANIMATION Vol. 1", "Key Animation Book",
         "9784088834634", "Shueisha", 40),
        ("Jujutsu Kaisen KEY ANIMATION Vol. 2", "Key Animation Book",
         "9784088834641", "Shueisha", 40),
        ("Attack on Titan: Animation Side Guidebook", "Anime Guide Book",
         "9784063770728", "Kodansha", 25),
        ("Chainsaw Man: Anime Visual Book", "Art Book",
         "9784088835051", "Shueisha", 35),
        # Ufotable
        ("Demon Slayer: Kimetsu no Yaiba Animation Art Book Vol. 1", "Production Art Book",
         "9784088832722", "Shueisha", 35),
        ("Demon Slayer: Kimetsu no Yaiba Animation Art Book Vol. 2", "Production Art Book",
         "9784088833163", "Shueisha", 35),
        ("Fate/stay night [UBW] Animation Material I", "Production Art Book",
         "9784041027929", "Kadokawa", 55),
        ("Fate/Zero Animation Material", "Production Art Book",
         "9784041002483", "Kadokawa", 50),
        # Makoto Shinkai
        ("Makoto Shinkai Artworks: Your Name.", "Art Book",
         "9784041047811", "Kadokawa", 35),
        ("Weathering with You Art Book", "Art Book",
         "9784041086483", "Kadokawa", 35),
        ("Suzume Art Book", "Art Book",
         "9784041130834", "Kadokawa", 38),
        # Classic / Vintage (high resale)
        ("Akira Animation Archives", "Production Art Book",
         "9784063300550", "Kodansha", 120),
        ("Ghost in the Shell: Anime Visual Book", "Art Book",
         "9784063300574", "Kodansha", 80),
        ("Studio Gainax Interviews", "Reference",
         "9781935654575", "Vertical", 25),
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
    """~10 scale modelling technique books and reference guides."""
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
    """~5 Funko visual guides and reference books."""
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
    """~5 sports card collecting price guides and references."""
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
    """~10 Disney art books, animation art, and Imagineering references."""
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
    """~15 Studio Ghibli art books, production art, and storyboards."""
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
        # Storyboard collections (high resale — limited print runs)
        ("Spirited Away Storyboards", "Storyboard Collection",
         "9784198614720", "Tokuma Shoten", 55),
        ("Princess Mononoke Storyboards", "Storyboard Collection",
         "9784198607104", "Tokuma Shoten", 60),
        ("Nausicaa of the Valley of the Wind Storyboards", "Storyboard Collection",
         "9784198613358", "Tokuma Shoten", 65),
        # Hayao Miyazaki collections
        ("Hayao Miyazaki and the Art of Studio Ghibli", "Art Book",
         "9781421587691", "Viz Media", 40),
        ("Starting Point: 1979-1996 (Hayao Miyazaki)", "Reference",
         "9781421505947", "Viz Media", 22),
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
    """~5 Nintendo art and history books."""
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
    """~40 collectible comic books: omnibuses, absolute editions, key TPBs, art books."""
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
        # Image / Indie Collected Editions
        ("Saga Compendium One", "Complete Edition",
         "9781534312340", "Image Comics", 40),
        ("Invincible Compendium Vol. 1", "Complete Edition",
         "9781607064114", "Image Comics", 45),
        ("The Walking Dead Compendium One", "Complete Edition",
         "9781607060765", "Image Comics", 40),
        ("East of West: The Complete Collection", "Complete Edition",
         "9781534316980", "Image Comics", 45),
        # Dark Horse
        ("Hellboy Omnibus Vol. 1: Seed of Destruction", "Omnibus",
         "9781506706665", "Dark Horse", 22),
        ("Usagi Yojimbo: The Special Edition", "Collector Edition",
         "9781506724874", "Dark Horse", 45),
        # Key Graphic Novels (perennial sellers)
        ("Maus: A Survivor's Tale Complete", "Complete Edition",
         "9780679748403", "Pantheon", 25),
        ("Persepolis: The Complete Edition", "Complete Edition",
         "9780375714832", "Pantheon", 18),
        ("Fun Home: A Family Tragicomic", "Complete Edition",
         "9780618871711", "Mariner Books", 16),
        ("Blankets", "Complete Edition",
         "9781891830433", "Top Shelf", 22),
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
        # Manga crossovers (unique to comic_books — no ISBN overlap with manga category)
        ("Battle Angel Alita Deluxe Complete Series Box Set", "Box Set",
         "9781632367112", "Kodansha", 120),
        # Japanese manga in original Weekly Shonen Jump format
        ("Shonen Jump Manga: Dragon Ball Vol. 1 (JP 1st Print)", "Collector Edition",
         "9784088518312", "Shueisha", 50),
        ("Weekly Shonen Jump 1997 #34 (One Piece Ch.1)", "Collector Edition",
         "9784088725390", "Shueisha", 200),
        # Key collected editions (unique ISBNs)
        ("One Punch Man Vol. 1-10 Box Set", "Box Set",
         "9781974741410", "Viz Media", 70),
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
