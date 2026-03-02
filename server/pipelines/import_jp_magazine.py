"""
Import Japanese magazine exclusives catalog.

Layer 1 (Catalog):  Curated JP magazine inserts & exclusives → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Dengeki G's Magazine (Love Live, idol game inserts)
- Newtype magazine (anime posters, production art)
- Famitsu (game codes, mini figures)
- Animedia / Animage (classic anime inserts)
- Limited clear files, shikishi boards, acrylic stands
- Vintage 80s/90s anime magazine inserts
- Weekly Shonen Jump / Sunday / Magazine milestone issues
- V Jump (Yu-Gi-Oh! / Dragon Ball promo cards)
- CoroCoro Comic (Pokemon reveal issues)
- Hobby Japan, Model Graphix (mecha & model features)
- Megami Magazine, Nyantype (tapestry & clear file inserts)
- Ultra Jump (JoJo), Monthly Gangan (FMA), Comp Ace (Fate/Overlord)
- Figure King, Dengeki Hobby Magazine (defunct vintage)

Usage:
    python -m pipelines.import_jp_magazine [--dry-run]
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
    RARITY_SCORE_MAP,
    logger,
    close_http_client,
)

CATEGORY = "jp_magazine"


def get_curated_catalog() -> list[dict]:
    """Curated Japanese magazine exclusives catalog (500+ items)."""

    # (magazine, franchise, item_type, name, era, rarity_tier, price_eur)
    # rarity_tier: grail (>100), high (50-100), mid (15-50), standard (<15)

    items = [
        # Dengeki G's Magazine – Love Live / idol inserts
        ("Dengeki G's Magazine", "Love Live!", "Insert Poster", "Love Live! Muse Final Live A2 Poster Insert", "2010s", "mid", 25),
        ("Dengeki G's Magazine", "Love Live! Sunshine!!", "Insert Poster", "Aqours 2nd Live A2 Poster Insert", "2010s", "mid", 20),
        ("Dengeki G's Magazine", "Love Live!", "Clear File", "Muse Valentine Clear File Set", "2010s", "mid", 18),
        ("Dengeki G's Magazine", "Love Live! Superstar!!", "Acrylic Stand", "Liella! 1st Anniversary Acrylic Stand", "2020s", "mid", 22),
        ("Dengeki G's Magazine", "The Idolmaster", "Insert Card", "iM@S Shiny Colors Insert Bromide Set", "2020s", "standard", 12),
        ("Dengeki G's Magazine", "Love Live!", "Shikishi Board", "Muse 9th Anniversary Shikishi Board", "2010s", "mid", 30),

        # Newtype magazine – anime posters & production art
        ("Newtype", "Evangelion", "B2 Poster", "Evangelion 3.0+1.0 Key Visual B2 Poster", "2020s", "mid", 28),
        ("Newtype", "Fate/stay night", "B2 Poster", "Fate/stay night HF III Key Art Poster", "2020s", "mid", 22),
        ("Newtype", "Gundam: Witch from Mercury", "Clear File", "Suletta Mercury Clear File Insert", "2020s", "standard", 8),
        ("Newtype", "Code Geass", "Insert Poster", "Code Geass 15th Anniversary A3 Insert", "2020s", "mid", 18),
        ("Newtype", "Mobile Suit Gundam", "Production Art", "Original Gundam Production Settei Reprint", "2010s", "mid", 35),

        # Famitsu – game codes & mini figures
        ("Famitsu", "Final Fantasy VII Remake", "DLC Code", "FF7R Exclusive Weapon DLC Code Card", "2020s", "standard", 10),
        ("Famitsu", "Persona 5", "Clear File", "Persona 5 Royal Clear File Insert", "2010s", "standard", 12),
        ("Famitsu", "Monster Hunter", "Mini Figure", "Monster Hunter Rise Palamute Mini Figure", "2020s", "mid", 18),
        ("Famitsu", "Dragon Quest", "Insert Poster", "Dragon Quest XII Reveal A3 Poster", "2020s", "standard", 8),
        ("Famitsu", "Xenoblade Chronicles 3", "Acrylic Stand", "Xenoblade 3 Mio Acrylic Stand Insert", "2020s", "mid", 15),

        # Animedia / Animage – classic anime inserts
        ("Animage", "Nausicaa", "B3 Poster", "Nausicaa Theatrical Release Poster Reprint", "1980s", "high", 80),
        ("Animage", "Castle in the Sky", "Insert Poster", "Laputa Original Insert Poster 1986", "1980s", "grail", 150),
        ("Animedia", "Dragon Ball Z", "Pin-up Poster", "DBZ Cell Saga A3 Pin-up Set (3 sheets)", "1990s", "mid", 35),
        ("Animedia", "Sailor Moon", "Insert Poster", "Sailor Moon S Character Poster Insert", "1990s", "mid", 40),
        ("Animage", "Mobile Suit Gundam", "Settei Sheet", "Gundam 0083 Settei Sheet Insert", "1990s", "mid", 30),

        # Limited clear files, shikishi boards, acrylic stands
        ("Various", "Demon Slayer", "Clear File", "Demon Slayer Magazine Exclusive Clear File 5-Set", "2020s", "mid", 20),
        ("Various", "Spy x Family", "Shikishi Board", "Spy x Family Anime Festa Shikishi Board", "2020s", "standard", 12),
        ("Various", "Chainsaw Man", "Clear File", "Chainsaw Man Newtype x Animedia Clear File Pair", "2020s", "standard", 10),
        ("Various", "My Hero Academia", "Acrylic Stand", "MHA Magazine Insert Acrylic Stand Deku", "2020s", "standard", 12),

        # Vintage 80s/90s anime magazine inserts
        ("Animage", "Macross", "B2 Poster", "Macross DYRL Minmay B2 Poster Insert 1984", "1980s", "grail", 180),
        ("Newtype", "Akira", "Insert Poster", "Akira Theatrical A2 Poster Insert 1988", "1980s", "grail", 200),
        ("Animage", "Saint Seiya", "Pin-up Set", "Saint Seiya Gold Saints Pin-up Set 1988", "1980s", "high", 65),
        ("Newtype", "Ghost in the Shell", "Insert Poster", "Ghost in the Shell Movie A3 Poster 1995", "1990s", "high", 75),
        ("Animedia", "Neon Genesis Evangelion", "Pin-up Poster", "EVA Rei & Asuka Double-Sided A3 Poster", "1990s", "high", 55),

        # --- New items below (36 additions) ---

        # More Newtype (+6)
        ("Newtype", "Evangelion", "Insert Poster Set", "Evangelion Rebuild 4-Poster Set (Unit 01/02/08/13)", "2020s", "high", 55),
        ("Newtype", "Evangelion", "B2 Poster", "Evangelion Death & Rebirth Theatrical B2 Poster Insert", "1990s", "high", 70),
        ("Newtype", "Gundam SEED", "Insert Poster", "Gundam SEED Destiny Freedom vs Justice A2 Poster", "2000s", "mid", 28),
        ("Newtype", "Gundam 00", "Insert Poster", "Gundam 00 Movie Key Visual A3 Poster Insert", "2010s", "mid", 22),
        ("Newtype", "Fate/stay night", "Clear File", "Fate/stay night UBW Saber & Rin Clear File Set", "2010s", "mid", 16),
        ("Newtype", "Code Geass", "B2 Poster", "Code Geass R2 Lelouch & C.C. B2 Poster Insert", "2000s", "mid", 32),

        # More Dengeki (+5)
        ("Dengeki G's Magazine", "Sword Art Online", "Insert Poster", "SAO Alicization War of Underworld A2 Poster", "2010s", "mid", 20),
        ("Dengeki G's Magazine", "Date A Live", "Clear File", "Date A Live IV Tohka & Kurumi Clear File", "2020s", "standard", 14),
        ("Dengeki G's Magazine", "Oreimo", "Insert Poster", "Ore no Imouto Kirino & Kuroneko A3 Poster", "2010s", "mid", 18),
        ("Dengeki G's Magazine", "Oregairu", "Clear File", "Oregairu Kan Yukino & Yui Clear File Set", "2020s", "standard", 12),
        ("Dengeki G's Magazine", "Toaru Kagaku no Railgun", "Insert Poster", "Railgun T Misaka Mikoto A2 Poster Insert", "2020s", "mid", 16),

        # Famitsu (+5)
        ("Famitsu", "Final Fantasy XVI", "DLC Code", "FF16 Exclusive Weapon DLC Code Card Insert", "2020s", "standard", 8),
        ("Famitsu", "Dragon Quest XI", "Mini Strategy Guide", "DQ XI S Mini Strategy Guide Booklet Insert", "2010s", "standard", 10),
        ("Famitsu", "Tales of Arise", "Mini Figure", "Tales of Arise Shionne Mini Figure Appendix", "2020s", "mid", 22),
        ("Famitsu", "Final Fantasy XIV", "Insert Poster", "FF XIV Endwalker Key Art A3 Poster Insert", "2020s", "standard", 12),
        ("Famitsu", "Dragon Quest", "Illustration Card", "Dragon Quest 35th Anniversary Toriyama Art Card Set", "2020s", "mid", 25),

        # Animedia / Animage (+5)
        ("Animage", "Mobile Suit Gundam", "B2 Poster", "Original Gundam TV Series Cast B2 Poster 1980", "1980s", "grail", 120),
        ("Animedia", "Sailor Moon", "Pin-up Set", "Sailor Moon SuperS Inner Senshi Pin-up Set", "1990s", "mid", 38),
        ("Animage", "Saint Seiya", "Insert Poster", "Saint Seiya Hades Chapter A3 Poster Insert 1990", "1990s", "high", 50),
        ("Animedia", "Macross", "Insert Poster", "Macross 7 Basara & Mylene A3 Poster Insert", "1990s", "mid", 30),
        ("Animedia", "Dragon Ball", "Pin-up Poster", "Dragon Ball Piccolo Daimao Arc A3 Pin-up 1988", "1980s", "high", 60),

        # Megami Magazine (+4)
        ("Megami Magazine", "Fate/Grand Order", "Tapestry", "FGO Mash Kyrielight B2 Tapestry Appendix", "2020s", "mid", 35),
        ("Megami Magazine", "Love Live! Sunshine!!", "Clear File", "Aqours Summer Uniform Clear File Set", "2010s", "mid", 18),
        ("Megami Magazine", "Vocaloid", "Tapestry", "Hatsune Miku 10th Anniversary B2 Tapestry", "2010s", "mid", 40),
        ("Megami Magazine", "Fate/stay night", "Clear File", "Fate/stay night Saber Alter Clear File Insert", "2010s", "mid", 15),

        # Comptiq (+3)
        ("Comptiq", "Clannad", "Illustration Card", "Clannad After Story Nagisa Illustration Card Set", "2000s", "mid", 22),
        ("Comptiq", "Kanon", "Illustration Card", "Kanon 2006 Ayu & Nayuki Illustration Card Insert", "2000s", "mid", 20),
        ("Comptiq", "Fate/stay night", "Insert Poster", "Fate/hollow ataraxia A3 Poster Insert", "2000s", "mid", 18),

        # PASH! (+3)
        ("PASH!", "The Idolmaster SideM", "Insert Poster", "iDOLM@STER SideM Jupiter A3 Poster Insert", "2010s", "standard", 14),
        ("PASH!", "Ensemble Stars!", "Clear File", "Ensemble Stars! Trickstar Clear File Appendix", "2020s", "standard", 12),
        ("PASH!", "Given", "Insert Poster", "Given Mafuyu & Ritsuka A3 Poster Insert", "2020s", "mid", 16),

        # Vintage 80s/90s (+5)
        ("Animage", "Urusei Yatsura", "B2 Poster", "Urusei Yatsura Lum B2 Poster Insert 1983", "1980s", "grail", 140),
        ("Animage", "Macross", "Pin-up Set", "SDF Macross Lynn Minmay Pin-up Set 1983", "1980s", "grail", 160),
        ("Newtype", "Akira", "Production Art", "Akira Kaneda Motorcycle Settei Reprint Insert", "1980s", "grail", 190),
        ("Newtype", "Ghost in the Shell", "B2 Poster", "Ghost in the Shell Motoko Kusanagi B2 Poster 1995", "1990s", "high", 85),
        ("Newtype", "Evangelion", "Insert Poster", "Neon Genesis Evangelion TV Series A2 Poster 1996", "1990s", "high", 90),

        # --- Round 2 additions (35 items) ---

        # Weekly Shonen Jump milestone issues
        ("Weekly Shonen Jump", "Various", "Magazine Issue", "Weekly Shonen Jump #1 (1968 Inaugural Issue Reprint)", "1960s", "grail", 300),
        ("Weekly Shonen Jump", "Dragon Ball", "Magazine Issue", "Weekly Shonen Jump 1984 #51 Dragon Ball Ch.1 Debut", "1980s", "grail", 250),
        ("Weekly Shonen Jump", "One Piece", "Magazine Issue", "Weekly Shonen Jump 1997 #34 One Piece Ch.1 Debut", "1990s", "grail", 200),
        ("Weekly Shonen Jump", "Naruto", "Magazine Issue", "Weekly Shonen Jump 2014 #50 Naruto Final Chapter Issue", "2010s", "high", 80),
        ("Weekly Shonen Jump", "Dragon Ball", "Magazine Issue", "Weekly Shonen Jump 1995 #25 Dragon Ball Final Chapter", "1990s", "grail", 180),
        ("Weekly Shonen Jump", "Demon Slayer", "Magazine Issue", "Weekly Shonen Jump 2020 #24 Demon Slayer Final Chapter", "2020s", "high", 55),

        # V Jump with Yu-Gi-Oh! promo cards
        ("V Jump", "Yu-Gi-Oh!", "Promo Card Insert", "V Jump Blue-Eyes White Dragon Promo Card (VJMP)", "2000s", "grail", 150),
        ("V Jump", "Yu-Gi-Oh!", "Promo Card Insert", "V Jump Dark Magician Promo Card Insert", "2000s", "high", 90),
        ("V Jump", "Yu-Gi-Oh!", "Promo Card Insert", "V Jump Stardust Dragon Promo Card Insert", "2010s", "high", 70),
        ("V Jump", "Dragon Ball Heroes", "Promo Card Insert", "V Jump Dragon Ball Heroes Secret Rarity Promo Card", "2020s", "mid", 35),

        # CoroCoro Comic – Pokemon reveal issues
        ("CoroCoro Comic", "Pokemon", "Magazine Issue", "CoroCoro Comic 1996 Feb Pokemon Red/Green First Reveal", "1990s", "grail", 220),
        ("CoroCoro Comic", "Pokemon", "Magazine Issue", "CoroCoro Comic 1999 April Pokemon Gold/Silver Reveal", "1990s", "high", 80),
        ("CoroCoro Comic", "Pokemon", "Insert Card", "CoroCoro Comic Mew Promo Card Insert 1997", "1990s", "grail", 180),
        ("CoroCoro Comic", "Doraemon", "Magazine Issue", "CoroCoro Comic 1986 Doraemon Special Anniversary Issue", "1980s", "high", 65),

        # Hobby Japan – Gunpla features
        ("Hobby Japan", "Gundam", "Magazine Issue", "Hobby Japan 1980 #1 Original Gunpla Feature Issue", "1980s", "grail", 120),
        ("Hobby Japan", "Gundam", "Limited Model Kit", "Hobby Japan Exclusive HG RX-78-2 Clear Version Kit", "2010s", "high", 75),
        ("Hobby Japan", "Gundam", "Limited Model Kit", "Hobby Japan Exclusive MG Char's Zaku II Metallic Ver.", "2020s", "high", 85),
        ("Hobby Japan", "Macross", "Magazine Issue", "Hobby Japan Macross VF-1S Special Feature Issue 1984", "1980s", "high", 60),

        # Figure King & Dengeki Hobby Magazine (defunct, vintage)
        ("Figure King", "Various", "Magazine Issue", "Figure King #1 Inaugural Issue 1998", "1990s", "high", 55),
        ("Figure King", "Evangelion", "Magazine Issue", "Figure King EVA Special Feature with Mini Figure Appendix", "2000s", "mid", 35),
        ("Dengeki Hobby Magazine", "Gundam", "Magazine Issue", "Dengeki Hobby Final Issue #84 (Discontinued 2015)", "2010s", "mid", 40),
        ("Dengeki Hobby Magazine", "Gundam", "Limited Model Kit", "Dengeki Hobby Exclusive 1/144 Gundam GP04 Gerbera Kit", "2000s", "high", 70),

        # Type-Moon Ace – Fate coverage
        ("Type-Moon Ace", "Fate/stay night", "Magazine Issue", "Type-Moon Ace Vol.1 Inaugural Issue (Fate Special)", "2000s", "high", 65),
        ("Type-Moon Ace", "Fate/Grand Order", "Insert Poster", "Type-Moon Ace FGO 5th Anniversary Special A2 Poster", "2020s", "mid", 30),

        # Monthly Comic Alive & Dengeki Daioh – light novel tie-ins
        ("Monthly Comic Alive", "Re:Zero", "Clear File", "Comic Alive Re:Zero Rem & Ram Clear File Insert", "2020s", "mid", 18),
        ("Monthly Comic Alive", "Konosuba", "Insert Poster", "Comic Alive Konosuba Megumin A3 Poster Insert", "2010s", "mid", 16),
        ("Dengeki Daioh", "Sword Art Online", "Clear File", "Dengeki Daioh SAO Asuna & Kirito Clear File Set", "2010s", "mid", 15),
        ("Dengeki Daioh", "Toaru Majutsu no Index", "Insert Poster", "Dengeki Daioh Index & Misaka A3 Poster Insert", "2010s", "standard", 12),

        # Issues with rare promo inserts (cards, posters, booklets)
        ("Animage", "Macross", "Promo Booklet", "Animage Macross Flashback 2012 Special Booklet Insert", "1980s", "high", 70),
        ("Newtype", "Gundam", "Promo Poster Set", "Newtype Gundam 40th Anniversary 4-Poster Set Insert", "2020s", "mid", 35),

        # Otomedia – male idol anime features
        ("Otomedia", "Haikyuu!!", "Insert Poster", "Otomedia Haikyuu!! Hinata & Kageyama A2 Poster", "2010s", "mid", 22),
        ("Otomedia", "Free!", "Clear File", "Otomedia Free! Eternal Summer Clear File Set", "2010s", "mid", 18),
        ("Otomedia", "Gintama", "Insert Poster", "Otomedia Gintama Final Arc Special A3 Poster", "2010s", "mid", 20),

        # PASH! & Animage vintage (Gundam, Macross covers from 80s)
        ("PASH!", "Yuri!!! on Ice", "Insert Poster", "PASH! Yuri on Ice Victor & Yuuri A2 Poster Insert", "2010s", "mid", 25),
        ("Animage", "Gundam", "B2 Poster", "Animage Mobile Suit Gundam Char Aznable B2 Poster 1981", "1980s", "grail", 130),

        # --- Round 3 additions (44 items) ---

        # Shonen Sunday / Shonen Magazine milestone issues
        ("Weekly Shonen Sunday", "Inuyasha", "Magazine Issue", "Weekly Shonen Sunday 1996 #50 Inuyasha Ch.1 Debut", "1990s", "high", 90),
        ("Weekly Shonen Sunday", "Urusei Yatsura", "Magazine Issue", "Weekly Shonen Sunday 1978 #39 Urusei Yatsura Debut", "1970s", "grail", 280),
        ("Weekly Shonen Sunday", "Detective Conan", "Magazine Issue", "Weekly Shonen Sunday 1994 #5 Detective Conan Ch.1 Debut", "1990s", "grail", 150),
        ("Weekly Shonen Magazine", "Hajime no Ippo", "Magazine Issue", "Weekly Shonen Magazine 1989 #43 Hajime no Ippo Debut", "1980s", "high", 70),
        ("Weekly Shonen Magazine", "Attack on Titan", "Magazine Issue", "Bessatsu Shonen Magazine 2009 #10 AoT Ch.1 Debut", "2000s", "grail", 160),
        ("Weekly Shonen Magazine", "Fairy Tail", "Magazine Issue", "Weekly Shonen Magazine 2006 #35 Fairy Tail Debut", "2000s", "high", 55),

        # Nyantype / NyanACE – moe insert magazines
        ("Nyantype", "Fate/Grand Order", "Tapestry Insert", "Nyantype FGO Mash & Artoria B2 Tapestry Appendix", "2020s", "mid", 28),
        ("Nyantype", "Love Live! Superstar!!", "Clear File", "Nyantype Liella! Swimsuit Clear File Set", "2020s", "standard", 14),
        ("Nyantype", "Azur Lane", "Tapestry Insert", "Nyantype Azur Lane Enterprise B2 Tapestry", "2010s", "mid", 25),
        ("Nyantype", "Girls und Panzer", "Insert Poster", "Nyantype Girls und Panzer Final Chapter A2 Poster", "2020s", "mid", 20),

        # Kadokawa magazines – Comp Ace, Monthly Ace
        ("Comp Ace", "Fate/Grand Order", "Clear File", "Comp Ace FGO Kama Clear File Insert", "2020s", "standard", 12),
        ("Comp Ace", "Overlord", "Insert Poster", "Comp Ace Overlord IV Ainz Ooal Gown A3 Poster", "2020s", "mid", 18),
        ("Comp Ace", "The Rising of the Shield Hero", "Illustration Card", "Comp Ace Shield Hero Raphtalia Illustration Card", "2020s", "standard", 10),
        ("Monthly Ace", "Re:Zero", "Clear File", "Monthly Ace Re:Zero Rem & Emilia Clear File Pair", "2020s", "mid", 16),

        # Model Graphix – mecha special features
        ("Model Graphix", "Gundam", "Magazine Issue", "Model Graphix Gundam Sentinel Special Feature 1988", "1980s", "high", 75),
        ("Model Graphix", "Macross", "Magazine Issue", "Model Graphix Macross Plus VF-19 Feature Issue", "1990s", "high", 50),
        ("Model Graphix", "Five Star Stories", "Magazine Issue", "Model Graphix FSS Mamoru Nagano Interview Issue", "1990s", "high", 60),

        # Afternoon / Monthly manga magazines
        ("Monthly Afternoon", "Vinland Saga", "Magazine Issue", "Monthly Afternoon Vinland Saga Final Arc Cover", "2020s", "mid", 25),
        ("Monthly Afternoon", "Blue Giant", "Magazine Issue", "Monthly Afternoon Blue Giant Supreme Final Chapter", "2020s", "mid", 20),
        ("Morning", "Vagabond", "Magazine Issue", "Morning Vagabond Takehiko Inoue Cover Issue", "2000s", "high", 55),

        # Vintage 70s items
        ("Animage", "Space Battleship Yamato", "B2 Poster", "Animage Yamato 2199 Classic Reprint B2 Poster", "1970s", "grail", 170),
        ("Animage", "Galaxy Express 999", "Insert Poster", "Animage Galaxy Express 999 Maetel A2 Poster 1979", "1970s", "grail", 140),

        # More CoroCoro & V Jump
        ("CoroCoro Comic", "Pokemon", "Magazine Issue", "CoroCoro Comic 2006 Sep Pokemon Diamond/Pearl Reveal", "2000s", "high", 50),
        ("CoroCoro Comic", "Yokai Watch", "Insert Card", "CoroCoro Comic Yokai Watch Medal Promo Insert", "2010s", "mid", 22),
        ("V Jump", "Dragon Ball Super", "Promo Card Insert", "V Jump DBS Card Game Ultra Instinct Goku Promo", "2020s", "mid", 40),
        ("V Jump", "One Piece Card Game", "Promo Card Insert", "V Jump One Piece Card Game Luffy Gear 5 Promo", "2020s", "high", 65),

        # Hobby magazines – scale model & cosplay
        ("Hobby Japan", "Evangelion", "Magazine Issue", "Hobby Japan EVA Rebuild Kit Feature with 1/144 Sample", "2020s", "mid", 35),
        ("Hobby Japan", "Armored Core", "Magazine Issue", "Hobby Japan Armored Core VI Special Feature Issue", "2020s", "mid", 28),
        ("COSMODE", "Various", "Magazine Issue", "COSMODE Final Issue #066 Collector's Edition", "2010s", "mid", 30),

        # Monthly Comic Gene / Sylph (josei/shoujo)
        ("Monthly Comic Gene", "Bungou Stray Dogs", "Clear File", "Comic Gene Bungou Stray Dogs Dazai Clear File", "2020s", "standard", 14),
        ("Monthly Comic Gene", "Moriarty the Patriot", "Insert Poster", "Comic Gene Moriarty the Patriot A3 Poster Insert", "2020s", "standard", 12),

        # Ultra Jump – JoJo & seinen
        ("Ultra Jump", "JoJo's Bizarre Adventure", "Magazine Issue", "Ultra Jump JoJo Part 9 The JoJolands Chapter 1 Issue", "2020s", "high", 50),
        ("Ultra Jump", "JoJo's Bizarre Adventure", "Insert Poster", "Ultra Jump JoJo Stone Ocean A2 Poster Insert", "2020s", "mid", 28),
        ("Ultra Jump", "Steel Ball Run", "Magazine Issue", "Ultra Jump Steel Ball Run Final Chapter Issue", "2010s", "high", 65),

        # Gangan / Square Enix mags
        ("Monthly Gangan", "Fullmetal Alchemist", "Magazine Issue", "Monthly Gangan FMA Final Chapter Issue 2010", "2010s", "high", 75),
        ("Monthly Gangan", "Soul Eater", "Insert Poster", "Monthly Gangan Soul Eater Maka A3 Poster Insert", "2000s", "mid", 22),
        ("Gangan Joker", "Kakegurui", "Clear File", "Gangan Joker Kakegurui Yumeko Clear File Insert", "2010s", "standard", 12),

        # Seasonal anime magazines (defunct / rare)
        ("Charamel", "Various", "Magazine Issue", "Charamel Final Issue Collector's Edition 2016", "2010s", "mid", 25),
        ("Lyrical DS", "Symphogear", "Insert Poster", "Lyrical DS Symphogear XV Cast A2 Poster Insert", "2010s", "mid", 18),

        # More Megami Magazine
        ("Megami Magazine", "Date A Live", "Tapestry", "Megami Magazine Date A Live V Tohka B2 Tapestry", "2020s", "mid", 32),
        ("Megami Magazine", "Mushoku Tensei", "Clear File", "Megami Magazine Mushoku Tensei Roxy Clear File", "2020s", "standard", 14),
        ("Megami Magazine", "Azur Lane", "Tapestry", "Megami Magazine Azur Lane Shinano B2 Tapestry", "2020s", "mid", 35),
        ("Megami Magazine", "Blue Archive", "Clear File", "Megami Magazine Blue Archive Arona Clear File Insert", "2020s", "standard", 12),

        # --- Round 4 additions (56+ items) ---

        # Weekly Shonen Jump — additional milestone issues
        ("Weekly Shonen Jump", "Bleach", "Magazine Issue", "Weekly Shonen Jump 2001 #36-37 Bleach Ch.1 Debut", "2000s", "high", 85),
        ("Weekly Shonen Jump", "Hunter x Hunter", "Magazine Issue", "Weekly Shonen Jump 1998 #14 Hunter x Hunter Ch.1 Debut", "1990s", "grail", 130),
        ("Weekly Shonen Jump", "My Hero Academia", "Magazine Issue", "Weekly Shonen Jump 2014 #32 My Hero Academia Ch.1 Debut", "2010s", "high", 55),
        ("Weekly Shonen Jump", "Jujutsu Kaisen", "Magazine Issue", "Weekly Shonen Jump 2018 #14 Jujutsu Kaisen Ch.1 Debut", "2010s", "high", 60),
        ("Weekly Shonen Jump", "Chainsaw Man", "Magazine Issue", "Weekly Shonen Jump 2019 #1 Chainsaw Man Ch.1 Debut", "2010s", "high", 50),
        ("Weekly Shonen Jump", "One Piece", "Magazine Issue", "Weekly Shonen Jump 2024 Gear 5 Color Spread Issue", "2020s", "mid", 35),
        ("Weekly Shonen Jump", "Dr. Stone", "Magazine Issue", "Weekly Shonen Jump 2022 #14 Dr. Stone Final Chapter", "2020s", "mid", 30),

        # CoroCoro — additional issues
        ("CoroCoro Comic", "Pokemon", "Magazine Issue", "CoroCoro Comic 2010 Sep Pokemon Black/White Reveal", "2010s", "high", 45),
        ("CoroCoro Comic", "Pokemon", "Insert Card", "CoroCoro Comic Shiny Mew Promo Insert Card 2005", "2000s", "grail", 120),
        ("CoroCoro Comic", "Inazuma Eleven", "Magazine Issue", "CoroCoro Comic 2008 Inazuma Eleven Special Issue", "2000s", "mid", 28),

        # V Jump — additional promo cards
        ("V Jump", "Yu-Gi-Oh!", "Promo Card Insert", "V Jump Number 39: Utopia Promo Card Insert", "2010s", "high", 55),
        ("V Jump", "Yu-Gi-Oh!", "Promo Card Insert", "V Jump Red-Eyes Black Dragon Alt Art Promo", "2000s", "high", 80),
        ("V Jump", "Dragon Ball Super", "Magazine Issue", "V Jump DBS Broly Movie Special Feature Issue", "2010s", "mid", 22),

        # Hobby Japan — additional
        ("Hobby Japan", "Gundam", "Limited Model Kit", "Hobby Japan Exclusive RG Strike Freedom Gold Frame Kit", "2020s", "high", 90),
        ("Hobby Japan", "Five Star Stories", "Magazine Issue", "Hobby Japan FSS Mortar Headd Feature Issue", "1990s", "high", 55),
        ("Hobby Japan", "Armored Core", "Magazine Issue", "Hobby Japan Armored Core Kotobukiya Kit Special", "2010s", "mid", 30),

        # Model Graphix — additional
        ("Model Graphix", "Gundam", "Magazine Issue", "Model Graphix Gundam The Origin Hajime Katoki Feature", "2010s", "mid", 35),
        ("Model Graphix", "Star Wars", "Magazine Issue", "Model Graphix Star Wars Model Kit Special Feature", "2000s", "mid", 28),

        # Newtype — additional vintage & modern
        ("Newtype", "Macross", "B2 Poster", "Newtype Macross Frontier Sheryl & Ranka B2 Poster Insert", "2000s", "mid", 25),
        ("Newtype", "Sword Art Online", "Clear File", "Newtype SAO Progressive Asuna Clear File Insert", "2020s", "standard", 10),
        ("Newtype", "Mobile Suit Gundam", "Production Art", "Newtype Gundam Unicorn NT-D Settei Reprint Insert", "2010s", "mid", 28),
        ("Newtype", "Violet Evergarden", "B2 Poster", "Newtype Violet Evergarden The Movie B2 Poster", "2020s", "mid", 22),
        ("Newtype", "Your Name", "Insert Poster", "Newtype Kimi no Na wa Shinkai A2 Poster Insert", "2010s", "mid", 30),
        ("Newtype", "Spirited Away", "Insert Poster", "Newtype Spirited Away 20th Anniversary A3 Poster", "2020s", "mid", 25),

        # Animage — additional vintage
        ("Animage", "Captain Harlock", "B2 Poster", "Animage Captain Harlock B2 Poster Insert 1978", "1970s", "grail", 160),
        ("Animage", "Nausicaa", "Insert Poster", "Animage Nausicaa Manga Chapter A3 Poster Insert", "1980s", "high", 90),
        ("Animage", "Lupin III", "Pin-up Set", "Animage Lupin III Part II Pin-up Set 1980", "1980s", "high", 70),

        # Animedia — additional
        ("Animedia", "Yu Yu Hakusho", "Pin-up Poster", "Animedia Yu Yu Hakusho Team Urameshi A3 Pin-up", "1990s", "mid", 38),
        ("Animedia", "Slam Dunk", "Insert Poster", "Animedia Slam Dunk Sakuragi & Rukawa A3 Poster", "1990s", "mid", 42),
        ("Animedia", "Rurouni Kenshin", "Insert Poster", "Animedia Rurouni Kenshin Kenshin & Kaoru A3 Poster", "1990s", "mid", 35),

        # Megami Magazine — additional
        ("Megami Magazine", "Lycoris Recoil", "Tapestry", "Megami Magazine Lycoris Recoil Chisato B2 Tapestry", "2020s", "mid", 30),
        ("Megami Magazine", "Bocchi the Rock!", "Clear File", "Megami Magazine Bocchi the Rock! Clear File Set", "2020s", "mid", 18),
        ("Megami Magazine", "Oshi no Ko", "Tapestry", "Megami Magazine Oshi no Ko Ai B2 Tapestry", "2020s", "mid", 28),
        ("Megami Magazine", "Frieren", "Clear File", "Megami Magazine Frieren Frieren & Fern Clear File", "2020s", "mid", 16),

        # Nyantype — additional
        ("Nyantype", "Evangelion", "Tapestry Insert", "Nyantype Evangelion Asuka & Rei B2 Tapestry", "2020s", "mid", 32),
        ("Nyantype", "Fate/Grand Order", "Clear File", "Nyantype FGO Tamamo no Mae Clear File Insert", "2020s", "standard", 14),
        ("Nyantype", "Sword Art Online", "Tapestry Insert", "Nyantype SAO Asuna Swimsuit B2 Tapestry", "2010s", "mid", 25),

        # Dengeki G's — additional
        ("Dengeki G's Magazine", "Love Live! Nijigasaki", "Acrylic Stand", "Dengeki G's Nijigasaki Setsuna Acrylic Stand", "2020s", "standard", 14),
        ("Dengeki G's Magazine", "Lycoris Recoil", "Clear File", "Dengeki G's Lycoris Recoil Takina Clear File", "2020s", "standard", 12),
        ("Dengeki G's Magazine", "Bang Dream!", "Insert Poster", "Dengeki G's BanG Dream! Poppin'Party A3 Poster", "2020s", "standard", 10),

        # Famitsu — additional
        ("Famitsu", "Elden Ring", "Insert Poster", "Famitsu Elden Ring Key Visual A3 Poster Insert", "2020s", "mid", 15),
        ("Famitsu", "Zelda: Tears of the Kingdom", "Illustration Card", "Famitsu Zelda TotK Illustration Card Set Insert", "2020s", "mid", 20),
        ("Famitsu", "Persona 3 Reload", "Clear File", "Famitsu Persona 3 Reload Clear File Insert", "2020s", "standard", 12),

        # PASH! — additional
        ("PASH!", "Tokyo Revengers", "Insert Poster", "PASH! Tokyo Revengers Mikey & Draken A2 Poster", "2020s", "mid", 18),
        ("PASH!", "Blue Lock", "Clear File", "PASH! Blue Lock Isagi & Bachira Clear File Set", "2020s", "standard", 14),
        ("PASH!", "Spy x Family", "Insert Poster", "PASH! Spy x Family Loid & Yor A3 Poster Insert", "2020s", "mid", 16),

        # Ultra Jump — additional
        ("Ultra Jump", "JoJo's Bizarre Adventure", "Insert Poster", "Ultra Jump JoJolands Jodio A3 Poster Insert", "2020s", "mid", 30),
        ("Ultra Jump", "Bastard!! Heavy Metal Dark Fantasy", "Magazine Issue", "Ultra Jump Bastard!! Revival Cover Issue", "2010s", "mid", 22),

        # Type-Moon Ace — additional
        ("Type-Moon Ace", "Fate/Grand Order", "Magazine Issue", "Type-Moon Ace FGO Lostbelt 7 Feature Issue", "2020s", "mid", 25),
        ("Type-Moon Ace", "Tsukihime", "Insert Poster", "Type-Moon Ace Tsukihime Remake Arcueid A2 Poster", "2020s", "mid", 28),

        # Figure King — additional
        ("Figure King", "Various", "Magazine Issue", "Figure King Hot Toys Special Feature Issue 2018", "2010s", "mid", 30),
        ("Figure King", "Gundam", "Magazine Issue", "Figure King Gunpla 40th Anniversary Special", "2020s", "mid", 25),

        # Monthly Afternoon / Morning — additional
        ("Monthly Afternoon", "Witch Hat Atelier", "Magazine Issue", "Monthly Afternoon Witch Hat Atelier Cover Issue", "2020s", "mid", 18),
        ("Morning", "Space Brothers", "Magazine Issue", "Morning Space Brothers Milestone Chapter Cover", "2020s", "mid", 16),

        # Dengeki Hobby — additional defunct vintage
        ("Dengeki Hobby Magazine", "Macross", "Limited Model Kit", "Dengeki Hobby Exclusive 1/100 VF-1S Strike Valkyrie Kit", "2000s", "high", 65),
        ("Dengeki Hobby Magazine", "Evangelion", "Limited Model Kit", "Dengeki Hobby Exclusive EVA Unit 01 Chrome Kit", "2010s", "high", 80),

        # Monthly Comic Gene — additional
        ("Monthly Comic Gene", "Vanitas no Carte", "Clear File", "Comic Gene Vanitas no Carte Vanitas & Noe Clear File", "2020s", "standard", 12),
        ("Monthly Comic Gene", "Banana Fish", "Insert Poster", "Comic Gene Banana Fish Ash & Eiji A3 Poster Insert", "2010s", "mid", 25),

        # ── Additional Comp Ace ──────────────────────────────────────────
        ("Comp Ace", "Fate/Grand Order", "Tapestry", "Comp Ace FGO Castoria B2 Tapestry Appendix", "2020s", "mid", 30),
        ("Comp Ace", "Overlord", "Clear File", "Comp Ace Overlord Albedo & Shalltear Clear File Set", "2020s", "standard", 14),

        # ── Additional Monthly Gangan ────────────────────────────────────
        ("Monthly Gangan", "Fullmetal Alchemist", "Insert Poster", "Monthly Gangan FMA Brotherhood A2 Poster Insert", "2000s", "mid", 28),

        # ── Additional CoroCoro ──────────────────────────────────────────
        ("CoroCoro Comic", "Pokemon", "Magazine Issue", "CoroCoro Comic 2013 Oct Pokemon X/Y Reveal Issue", "2010s", "high", 40),

        # ── Additional Vintage Animage ───────────────────────────────────
        ("Animage", "Dirty Pair", "B2 Poster", "Animage Dirty Pair Kei & Yuri B2 Poster Insert 1985", "1980s", "high", 75),
        ("Animage", "Ideon", "Insert Poster", "Animage Space Runaway Ideon A2 Poster Insert 1982", "1980s", "high", 65),

        # --- Round 5 additions (295 items) ---

        # Weekly Shonen Jump — more debut/final issues
        ("Weekly Shonen Jump", "Slam Dunk", "Magazine Issue", "Weekly Shonen Jump 1990 #42 Slam Dunk Ch.1 Debut", "1990s", "grail", 140),
        ("Weekly Shonen Jump", "Rurouni Kenshin", "Magazine Issue", "Weekly Shonen Jump 1994 #19 Rurouni Kenshin Ch.1 Debut", "1990s", "high", 70),
        ("Weekly Shonen Jump", "Yu-Gi-Oh!", "Magazine Issue", "Weekly Shonen Jump 1996 #42 Yu-Gi-Oh! Ch.1 Debut", "1990s", "grail", 110),
        ("Weekly Shonen Jump", "Death Note", "Magazine Issue", "Weekly Shonen Jump 2003 #53 Death Note Ch.1 Debut", "2000s", "high", 75),
        ("Weekly Shonen Jump", "Gintama", "Magazine Issue", "Weekly Shonen Jump 2004 #2 Gintama Ch.1 Debut Issue", "2000s", "high", 60),
        ("Weekly Shonen Jump", "Yu Yu Hakusho", "Magazine Issue", "Weekly Shonen Jump 1990 #51 Yu Yu Hakusho Ch.1 Debut", "1990s", "high", 80),
        ("Weekly Shonen Jump", "Dragon Ball", "Magazine Issue", "Weekly Shonen Jump 1992 #12 Cell Games Cover Issue", "1990s", "high", 65),
        ("Weekly Shonen Jump", "Saint Seiya", "Magazine Issue", "Weekly Shonen Jump 1986 #1-2 Saint Seiya Ch.1 Debut", "1980s", "grail", 120),
        ("Weekly Shonen Jump", "Bleach", "Magazine Issue", "Weekly Shonen Jump 2016 #38 Bleach Final Chapter Issue", "2010s", "high", 50),
        ("Weekly Shonen Jump", "Assassination Classroom", "Magazine Issue", "Weekly Shonen Jump 2016 #12 AssClass Final Chapter", "2010s", "mid", 40),
        ("Weekly Shonen Jump", "Naruto", "Magazine Issue", "Weekly Shonen Jump 1999 #43 Naruto Ch.1 Debut Issue", "1990s", "grail", 150),
        ("Weekly Shonen Jump", "Black Clover", "Magazine Issue", "Weekly Shonen Jump 2015 #12 Black Clover Ch.1 Debut", "2010s", "mid", 35),
        ("Weekly Shonen Jump", "World Trigger", "Magazine Issue", "Weekly Shonen Jump 2013 #11 World Trigger Ch.1 Debut", "2010s", "mid", 30),
        ("Weekly Shonen Jump", "Mashle", "Magazine Issue", "Weekly Shonen Jump 2020 #9 Mashle Ch.1 Debut Issue", "2020s", "mid", 25),
        ("Weekly Shonen Jump", "Undead Unluck", "Magazine Issue", "Weekly Shonen Jump 2020 #8 Undead Unluck Ch.1 Debut", "2020s", "mid", 25),
        ("Weekly Shonen Jump", "Sakamoto Days", "Magazine Issue", "Weekly Shonen Jump 2020 #51 Sakamoto Days Ch.1 Debut", "2020s", "mid", 30),

        # Weekly Shonen Sunday — additional
        ("Weekly Shonen Sunday", "Ranma 1/2", "Magazine Issue", "Weekly Shonen Sunday 1987 #36 Ranma 1/2 Ch.1 Debut", "1980s", "grail", 130),
        ("Weekly Shonen Sunday", "Major", "Magazine Issue", "Weekly Shonen Sunday 1994 #33 Major Ch.1 Debut Issue", "1990s", "high", 50),
        ("Weekly Shonen Sunday", "Hayate the Combat Butler", "Magazine Issue", "Weekly Shonen Sunday 2004 #45 Hayate Debut Issue", "2000s", "mid", 30),
        ("Weekly Shonen Sunday", "Magi", "Magazine Issue", "Weekly Shonen Sunday 2009 #27 Magi Ch.1 Debut Issue", "2000s", "mid", 35),
        ("Weekly Shonen Sunday", "Frieren", "Magazine Issue", "Weekly Shonen Sunday 2020 #22-23 Frieren Ch.1 Debut", "2020s", "high", 55),
        ("Weekly Shonen Sunday", "Komi Can't Communicate", "Magazine Issue", "Weekly Shonen Sunday 2016 #25 Komi Ch.1 Debut", "2010s", "mid", 35),

        # Weekly Shonen Magazine — additional
        ("Weekly Shonen Magazine", "Slam Dunk", "Magazine Issue", "Weekly Shonen Magazine 1990 Slam Dunk Feature Spread", "1990s", "mid", 30),
        ("Weekly Shonen Magazine", "Diamond no Ace", "Magazine Issue", "Weekly Shonen Magazine 2006 #24 Diamond no Ace Debut", "2000s", "mid", 30),
        ("Weekly Shonen Magazine", "The Seven Deadly Sins", "Magazine Issue", "Weekly Shonen Magazine 2012 #45 Seven Deadly Sins Debut", "2010s", "mid", 35),
        ("Weekly Shonen Magazine", "Tokyo Revengers", "Magazine Issue", "Weekly Shonen Magazine 2017 #13 Tokyo Revengers Debut", "2010s", "mid", 40),
        ("Weekly Shonen Magazine", "Blue Lock", "Magazine Issue", "Weekly Shonen Magazine 2018 #35 Blue Lock Ch.1 Debut", "2010s", "high", 50),
        ("Weekly Shonen Magazine", "Rave Master", "Magazine Issue", "Weekly Shonen Magazine 1999 #35 Rave Master Debut", "1990s", "mid", 35),

        # CoroCoro Comic — additional
        ("CoroCoro Comic", "Pokemon", "Magazine Issue", "CoroCoro Comic 2016 Feb Pokemon Sun/Moon First Reveal", "2010s", "high", 40),
        ("CoroCoro Comic", "Pokemon", "Insert Card", "CoroCoro Comic Arceus Promo Card Insert 2009", "2000s", "high", 70),
        ("CoroCoro Comic", "Pokemon", "Magazine Issue", "CoroCoro Comic 2019 Feb Pokemon Sword/Shield Reveal", "2010s", "mid", 35),
        ("CoroCoro Comic", "Pokemon", "Insert Card", "CoroCoro Comic Ancient Mew Promo Card 1999", "1990s", "grail", 200),
        ("CoroCoro Comic", "Beyblade", "Magazine Issue", "CoroCoro Comic 2001 Beyblade Special Feature Issue", "2000s", "mid", 25),
        ("CoroCoro Comic", "Doraemon", "Insert Card", "CoroCoro Comic Doraemon Stamp Rally Card Set", "1990s", "mid", 30),

        # V Jump — additional promo cards & issues
        ("V Jump", "Yu-Gi-Oh!", "Promo Card Insert", "V Jump Cyber Dragon Alt Art Promo Card", "2000s", "high", 60),
        ("V Jump", "Yu-Gi-Oh!", "Promo Card Insert", "V Jump Firewall Dragon Promo Card Insert", "2010s", "mid", 40),
        ("V Jump", "Yu-Gi-Oh!", "Promo Card Insert", "V Jump Elemental HERO Neos Promo Card", "2000s", "high", 55),
        ("V Jump", "Dragon Ball", "Promo Card Insert", "V Jump Dragon Ball Z Dokkan Battle Promo Card", "2020s", "mid", 25),
        ("V Jump", "One Piece Card Game", "Promo Card Insert", "V Jump One Piece Card Game Shanks Alt Art Promo", "2020s", "high", 50),
        ("V Jump", "Yu-Gi-Oh!", "Promo Card Insert", "V Jump Exodia the Forbidden One Promo Card", "2000s", "grail", 120),

        # Dengeki G's Magazine — additional idol/game inserts
        ("Dengeki G's Magazine", "Love Live! Sunshine!!", "Tapestry", "Dengeki G's Aqours 5th Anniversary B2 Tapestry", "2020s", "mid", 28),
        ("Dengeki G's Magazine", "Hololive", "Clear File", "Dengeki G's Hololive Collaboration Clear File Set", "2020s", "mid", 20),
        ("Dengeki G's Magazine", "Blue Archive", "Acrylic Stand", "Dengeki G's Blue Archive Shiroko Acrylic Stand", "2020s", "standard", 14),
        ("Dengeki G's Magazine", "Genshin Impact", "Clear File", "Dengeki G's Genshin Impact Clear File Set Insert", "2020s", "standard", 12),
        ("Dengeki G's Magazine", "Fate/Grand Order", "Insert Poster", "Dengeki G's FGO Castoria A2 Poster Insert", "2020s", "mid", 18),
        ("Dengeki G's Magazine", "Uma Musume", "Clear File", "Dengeki G's Uma Musume Pretty Derby Clear File", "2020s", "standard", 14),
        ("Dengeki G's Magazine", "Project Sekai", "Acrylic Stand", "Dengeki G's Project Sekai Miku Acrylic Stand", "2020s", "standard", 12),

        # Newtype — additional modern & vintage
        ("Newtype", "Demon Slayer", "B2 Poster", "Newtype Demon Slayer Mugen Train B2 Poster Insert", "2020s", "mid", 25),
        ("Newtype", "Jujutsu Kaisen", "Insert Poster", "Newtype Jujutsu Kaisen Gojo Satoru A2 Poster", "2020s", "mid", 25),
        ("Newtype", "Spy x Family", "Clear File", "Newtype Spy x Family Anya & Bond Clear File Set", "2020s", "standard", 10),
        ("Newtype", "Mobile Suit Gundam", "B2 Poster", "Newtype Gundam 0080 War in the Pocket B2 Poster 1989", "1980s", "high", 70),
        ("Newtype", "Patlabor", "Insert Poster", "Newtype Patlabor Movie A2 Poster Insert 1989", "1980s", "high", 65),
        ("Newtype", "Tenchi Muyo!", "Insert Poster", "Newtype Tenchi Muyo! Ryo-Ohki A3 Poster Insert 1995", "1990s", "mid", 28),
        ("Newtype", "Cowboy Bebop", "Insert Poster", "Newtype Cowboy Bebop Spike A2 Poster Insert 1998", "1990s", "high", 60),
        ("Newtype", "Trigun", "Insert Poster", "Newtype Trigun Vash A3 Poster Insert 1998", "1990s", "mid", 40),
        ("Newtype", "Serial Experiments Lain", "Insert Poster", "Newtype Serial Experiments Lain A3 Poster 1998", "1990s", "high", 55),
        ("Newtype", "Cardcaptor Sakura", "Clear File", "Newtype Cardcaptor Sakura Clear Card A3 Poster", "2010s", "mid", 22),
        ("Newtype", "Oshi no Ko", "B2 Poster", "Newtype Oshi no Ko Ai & Aqua B2 Poster Insert", "2020s", "mid", 22),
        ("Newtype", "Frieren", "Insert Poster", "Newtype Frieren Beyond Journey's End A2 Poster", "2020s", "mid", 20),
        ("Newtype", "Mobile Suit Gundam", "B2 Poster", "Newtype Char's Counterattack B2 Poster Insert 1988", "1980s", "grail", 100),

        # Animage — additional vintage & modern
        ("Animage", "Urusei Yatsura", "Pin-up Set", "Animage Urusei Yatsura Lum Pin-up Set 1982", "1980s", "high", 80),
        ("Animage", "Future Boy Conan", "Insert Poster", "Animage Future Boy Conan A3 Poster Insert 1978", "1970s", "grail", 150),
        ("Animage", "Gundam Zeta", "B2 Poster", "Animage Zeta Gundam Cast B2 Poster Insert 1985", "1980s", "high", 85),
        ("Animage", "Totoro", "Insert Poster", "Animage My Neighbor Totoro A3 Poster Insert 1988", "1980s", "grail", 120),
        ("Animage", "Kiki's Delivery Service", "Insert Poster", "Animage Kiki's Delivery Service A3 Poster 1989", "1980s", "high", 90),
        ("Animage", "Gundam ZZ", "Insert Poster", "Animage Gundam ZZ Judau & Ple A3 Poster Insert 1986", "1980s", "high", 55),
        ("Animage", "Voltron", "B2 Poster", "Animage GoLion/Voltron B2 Poster Insert 1981", "1980s", "high", 70),
        ("Animage", "City Hunter", "Insert Poster", "Animage City Hunter Ryo Saeba A3 Poster 1987", "1980s", "high", 55),
        ("Animage", "Doraemon", "Insert Poster", "Animage Doraemon Movie A3 Poster Insert 1980", "1980s", "high", 60),
        ("Animage", "Dr. Slump", "Pin-up Set", "Animage Dr. Slump Arale Pin-up Set 1981", "1980s", "high", 65),

        # Animedia — additional
        ("Animedia", "Inuyasha", "Insert Poster", "Animedia Inuyasha Inuyasha & Kagome A3 Poster", "2000s", "mid", 28),
        ("Animedia", "Bleach", "Pin-up Poster", "Animedia Bleach Gotei 13 Captains A3 Pin-up Set", "2000s", "mid", 32),
        ("Animedia", "Fullmetal Alchemist", "Insert Poster", "Animedia FMA Brotherhood Ed & Al A3 Poster", "2000s", "mid", 30),
        ("Animedia", "Naruto", "Pin-up Poster", "Animedia Naruto Shippuden Team 7 A3 Pin-up", "2000s", "mid", 28),
        ("Animedia", "One Piece", "Insert Poster", "Animedia One Piece Straw Hat Crew A3 Poster", "2000s", "mid", 25),
        ("Animedia", "Gintama", "Pin-up Poster", "Animedia Gintama Yorozuya Trio A3 Pin-up Set", "2010s", "mid", 22),
        ("Animedia", "Gundam Wing", "Insert Poster", "Animedia Gundam Wing Five Pilots A3 Poster 1995", "1990s", "mid", 38),
        ("Animedia", "Cardcaptor Sakura", "Pin-up Set", "Animedia Cardcaptor Sakura Sakura & Tomoyo Pin-up", "1990s", "mid", 35),
        ("Animedia", "Escaflowne", "Insert Poster", "Animedia Escaflowne Hitomi & Van A3 Poster 1996", "1990s", "mid", 32),
        ("Animedia", "Magic Knight Rayearth", "Pin-up Set", "Animedia Magic Knight Rayearth CLAMP Pin-up Set", "1990s", "mid", 35),

        # Famitsu — additional game inserts
        ("Famitsu", "Fire Emblem Engage", "Clear File", "Famitsu Fire Emblem Engage Alear Clear File", "2020s", "standard", 10),
        ("Famitsu", "Pikmin 4", "Insert Poster", "Famitsu Pikmin 4 Key Art A3 Poster Insert", "2020s", "standard", 8),
        ("Famitsu", "Armored Core VI", "Insert Poster", "Famitsu Armored Core VI Key Visual A3 Poster", "2020s", "mid", 15),
        ("Famitsu", "Octopath Traveler II", "Illustration Card", "Famitsu Octopath Traveler II Art Card Set", "2020s", "standard", 12),
        ("Famitsu", "Resident Evil 4 Remake", "Clear File", "Famitsu RE4 Remake Leon Clear File Insert", "2020s", "standard", 10),
        ("Famitsu", "Star Ocean 6", "Insert Poster", "Famitsu Star Ocean The Divine Force A3 Poster", "2020s", "standard", 10),
        ("Famitsu", "Final Fantasy", "Magazine Issue", "Famitsu 1988 #1 Inaugural Issue (FF II Feature)", "1980s", "grail", 200),
        ("Famitsu", "Street Fighter 6", "Clear File", "Famitsu Street Fighter 6 Character Clear File Set", "2020s", "standard", 12),
        ("Famitsu", "Dragon Quest III Remake", "Insert Poster", "Famitsu Dragon Quest III HD-2D A3 Poster", "2020s", "mid", 18),
        ("Famitsu", "Pokemon Scarlet/Violet", "Illustration Card", "Famitsu Pokemon SV DLC Art Card Set Insert", "2020s", "mid", 15),

        # Megami Magazine — additional tapestries & clear files
        ("Megami Magazine", "Chainsaw Man", "Tapestry", "Megami Magazine Chainsaw Man Makima B2 Tapestry", "2020s", "mid", 30),
        ("Megami Magazine", "Spy x Family", "Clear File", "Megami Magazine Spy x Family Yor Clear File", "2020s", "standard", 14),
        ("Megami Magazine", "My Dress-Up Darling", "Tapestry", "Megami Magazine My Dress-Up Darling Marin B2 Tapestry", "2020s", "mid", 32),
        ("Megami Magazine", "Quintessential Quintuplets", "Clear File", "Megami Magazine Quintuplets 5-Girl Clear File Set", "2020s", "mid", 22),
        ("Megami Magazine", "Re:Zero", "Tapestry", "Megami Magazine Re:Zero Rem Swimsuit B2 Tapestry", "2020s", "mid", 28),
        ("Megami Magazine", "Is It Wrong to Pick Up Girls", "Tapestry", "Megami Magazine DanMachi Hestia B2 Tapestry", "2010s", "mid", 25),
        ("Megami Magazine", "Rent-A-Girlfriend", "Clear File", "Megami Magazine Rent-A-Girlfriend Chizuru Clear File", "2020s", "standard", 12),
        ("Megami Magazine", "High School DxD", "Tapestry", "Megami Magazine High School DxD Rias B2 Tapestry", "2010s", "mid", 28),
        ("Megami Magazine", "Evangelion", "Tapestry", "Megami Magazine Evangelion Asuka B2 Tapestry", "2020s", "mid", 35),
        ("Megami Magazine", "Konosuba", "Clear File", "Megami Magazine Konosuba Megumin & Aqua Clear File", "2020s", "mid", 16),

        # Nyantype — additional
        ("Nyantype", "Chainsaw Man", "Tapestry Insert", "Nyantype Chainsaw Man Power B2 Tapestry", "2020s", "mid", 28),
        ("Nyantype", "My Dress-Up Darling", "Clear File", "Nyantype My Dress-Up Darling Marin Clear File Set", "2020s", "standard", 14),
        ("Nyantype", "Quintessential Quintuplets", "Tapestry Insert", "Nyantype Quintuplets Nakano Sisters B2 Tapestry", "2020s", "mid", 30),
        ("Nyantype", "Re:Zero", "Tapestry Insert", "Nyantype Re:Zero Emilia B2 Tapestry Appendix", "2020s", "mid", 26),
        ("Nyantype", "Mushoku Tensei", "Clear File", "Nyantype Mushoku Tensei Eris & Roxy Clear File", "2020s", "standard", 14),
        ("Nyantype", "Spy x Family", "Tapestry Insert", "Nyantype Spy x Family Yor Briar B2 Tapestry", "2020s", "mid", 25),

        # Comptiq — additional
        ("Comptiq", "Fate/Grand Order", "Clear File", "Comptiq FGO Ishtar Clear File Insert", "2020s", "standard", 12),
        ("Comptiq", "Azur Lane", "Insert Poster", "Comptiq Azur Lane Atago A3 Poster Insert", "2020s", "standard", 14),
        ("Comptiq", "Uma Musume", "Clear File", "Comptiq Uma Musume Special Week Clear File Set", "2020s", "standard", 12),
        ("Comptiq", "Touhou Project", "Illustration Card", "Comptiq Touhou Project Reimu Illustration Card", "2010s", "mid", 18),
        ("Comptiq", "Strike Witches", "Insert Poster", "Comptiq Strike Witches Yoshika A3 Poster Insert", "2010s", "mid", 16),

        # PASH! — additional
        ("PASH!", "Demon Slayer", "Insert Poster", "PASH! Demon Slayer Hashira A2 Poster Insert", "2020s", "mid", 20),
        ("PASH!", "Haikyuu!!", "Clear File", "PASH! Haikyuu!! Karasuno Clear File Set", "2010s", "mid", 18),
        ("PASH!", "Jujutsu Kaisen", "Insert Poster", "PASH! Jujutsu Kaisen Gojo & Geto A2 Poster", "2020s", "mid", 22),
        ("PASH!", "Banana Fish", "Clear File", "PASH! Banana Fish Ash & Eiji Clear File Set", "2010s", "mid", 20),
        ("PASH!", "SK8 the Infinity", "Insert Poster", "PASH! SK8 the Infinity Reki & Langa A3 Poster", "2020s", "standard", 14),
        ("PASH!", "Uta no Prince-sama", "Clear File", "PASH! Uta no Prince-sama STARISH Clear File Set", "2010s", "mid", 16),
        ("PASH!", "Obey Me!", "Insert Poster", "PASH! Obey Me! Seven Brothers A2 Poster Insert", "2020s", "standard", 14),

        # Otomedia — additional
        ("Otomedia", "Demon Slayer", "Insert Poster", "Otomedia Demon Slayer Tanjiro & Nezuko A2 Poster", "2020s", "mid", 20),
        ("Otomedia", "Bungou Stray Dogs", "Clear File", "Otomedia Bungou Stray Dogs Armed Detective Agency Clear File", "2020s", "standard", 14),
        ("Otomedia", "Hypnosis Mic", "Insert Poster", "Otomedia Hypnosis Mic Division All Stars A2 Poster", "2020s", "mid", 18),
        ("Otomedia", "Blue Period", "Insert Poster", "Otomedia Blue Period Yatora A3 Poster Insert", "2020s", "standard", 12),
        ("Otomedia", "Fruits Basket", "Clear File", "Otomedia Fruits Basket Tohru & Yuki Clear File", "2010s", "mid", 16),

        # Ultra Jump — additional
        ("Ultra Jump", "JoJo's Bizarre Adventure", "Magazine Issue", "Ultra Jump JoJo Part 7 Steel Ball Run Ch.1 Debut", "2000s", "grail", 100),
        ("Ultra Jump", "JoJo's Bizarre Adventure", "B2 Poster", "Ultra Jump JoJo Part 8 JoJolion B2 Poster Insert", "2010s", "mid", 35),
        ("Ultra Jump", "Deadman Wonderland", "Magazine Issue", "Ultra Jump Deadman Wonderland Cover Issue", "2000s", "mid", 22),
        ("Ultra Jump", "Claymore", "Magazine Issue", "Ultra Jump Claymore Final Chapter Issue", "2010s", "mid", 28),

        # Monthly Gangan / Square Enix — additional
        ("Monthly Gangan", "Fullmetal Alchemist", "Magazine Issue", "Monthly Gangan FMA Ch.1 Debut Issue 2001", "2000s", "grail", 100),
        ("Monthly Gangan", "D.Gray-man", "Insert Poster", "Monthly Gangan D.Gray-man Allen A3 Poster Insert", "2000s", "mid", 22),
        ("Monthly Gangan", "Pandora Hearts", "Clear File", "Monthly Gangan Pandora Hearts Oz Clear File Insert", "2000s", "mid", 18),
        ("Gangan Joker", "The Duke of Death", "Clear File", "Gangan Joker Duke of Death Clear File Insert", "2020s", "standard", 10),
        ("Young Gangan", "Yen Press", "Magazine Issue", "Young Gangan Bungo Stray Dogs Chapter 1 Issue", "2010s", "mid", 28),

        # Monthly Afternoon / Morning / Seinen — additional
        ("Monthly Afternoon", "Land of the Lustrous", "Magazine Issue", "Monthly Afternoon Land of Lustrous Cover Issue", "2010s", "mid", 22),
        ("Monthly Afternoon", "Blade of the Immortal", "Magazine Issue", "Monthly Afternoon Blade of Immortal Final Chapter", "2010s", "mid", 30),
        ("Monthly Afternoon", "History's Strongest Disciple Kenichi", "Magazine Issue", "Monthly Afternoon Kenichi Final Chapter Issue", "2010s", "mid", 22),
        ("Morning", "20th Century Boys", "Magazine Issue", "Morning (Big Comic Spirits) 20th Century Boys Feature", "2000s", "high", 50),
        ("Morning", "Giant Killing", "Magazine Issue", "Morning Giant Killing Soccer Feature Cover Issue", "2010s", "mid", 18),
        ("Big Comic Spirits", "Ping Pong", "Magazine Issue", "Big Comic Spirits Ping Pong Taiyo Matsumoto Cover", "1990s", "high", 55),
        ("Big Comic Spirits", "Ichi the Killer", "Magazine Issue", "Big Comic Spirits Ichi the Killer Feature Issue", "2000s", "mid", 35),
        ("Young Magazine", "Akira", "Magazine Issue", "Young Magazine Akira Serialization Start Issue 1982", "1980s", "grail", 250),
        ("Young Magazine", "Initial D", "Magazine Issue", "Young Magazine Initial D Final Chapter Issue 2013", "2010s", "high", 50),
        ("Young Magazine", "Parasyte", "Magazine Issue", "Monthly Afternoon Parasyte Shinichi Cover Issue 1990", "1990s", "high", 55),

        # Hobby Japan — additional mecha & model coverage
        ("Hobby Japan", "Gundam", "Limited Model Kit", "Hobby Japan Exclusive PG Unicorn LED Unit Special", "2020s", "high", 95),
        ("Hobby Japan", "Gundam", "Magazine Issue", "Hobby Japan HGUC Gundam 100th Kit Celebration Issue", "2010s", "mid", 30),
        ("Hobby Japan", "Evangelion", "Limited Model Kit", "Hobby Japan Exclusive EVA Unit 02 Metallic Ver. Kit", "2010s", "high", 80),
        ("Hobby Japan", "Frame Arms Girl", "Magazine Issue", "Hobby Japan Frame Arms Girl Gourai Feature Issue", "2010s", "mid", 25),
        ("Hobby Japan", "30 Minutes Missions", "Magazine Issue", "Hobby Japan 30MM Custom Build Feature Issue", "2020s", "mid", 20),
        ("Hobby Japan", "Zoids", "Magazine Issue", "Hobby Japan Zoids Wild Special Feature Issue", "2010s", "mid", 25),
        ("Hobby Japan", "Super Robot Wars", "Magazine Issue", "Hobby Japan SRW OG Mech Feature Issue", "2000s", "mid", 28),

        # Model Graphix — additional
        ("Model Graphix", "Gundam", "Magazine Issue", "Model Graphix MS-06 Zaku II Complete Feature", "2000s", "mid", 30),
        ("Model Graphix", "Macross", "Magazine Issue", "Model Graphix Macross Delta VF-31 Feature Issue", "2010s", "mid", 25),
        ("Model Graphix", "Yamato", "Magazine Issue", "Model Graphix Yamato 2199 Kit Building Feature", "2010s", "mid", 28),
        ("Model Graphix", "Star Wars", "Magazine Issue", "Model Graphix Bandai Star Wars Kit Complete Guide", "2010s", "mid", 25),
        ("Model Graphix", "Evangelion", "Magazine Issue", "Model Graphix Evangelion Entry Plug Kit Feature", "2020s", "mid", 22),

        # Type-Moon Ace — additional
        ("Type-Moon Ace", "Fate/Grand Order", "Magazine Issue", "Type-Moon Ace FGO 7th Anniversary Feature Issue", "2020s", "mid", 28),
        ("Type-Moon Ace", "Fate/stay night", "Insert Poster", "Type-Moon Ace Fate/stay night HF Sakura A2 Poster", "2020s", "mid", 25),
        ("Type-Moon Ace", "Tsukihime", "Magazine Issue", "Type-Moon Ace Tsukihime Remake Feature Issue", "2020s", "mid", 30),
        ("Type-Moon Ace", "Mahou Tsukai no Yoru", "Clear File", "Type-Moon Ace Witch on Holy Night Clear File", "2020s", "standard", 14),

        # Monthly Comic Alive / Dengeki Daioh — additional
        ("Monthly Comic Alive", "Mushoku Tensei", "Clear File", "Comic Alive Mushoku Tensei Eris Clear File Insert", "2020s", "standard", 12),
        ("Monthly Comic Alive", "The Eminence in Shadow", "Insert Poster", "Comic Alive Eminence in Shadow Cid A3 Poster", "2020s", "mid", 16),
        ("Monthly Comic Alive", "Saga of Tanya the Evil", "Clear File", "Comic Alive Tanya the Evil Tanya Clear File Insert", "2020s", "standard", 12),
        ("Dengeki Daioh", "Azur Lane", "Insert Poster", "Dengeki Daioh Azur Lane Belfast A3 Poster Insert", "2020s", "standard", 14),
        ("Dengeki Daioh", "A Certain Scientific Railgun", "Clear File", "Dengeki Daioh Railgun T Misaka Sisters Clear File", "2020s", "standard", 12),
        ("Dengeki Daioh", "Yuru Yuri", "Insert Poster", "Dengeki Daioh Yuru Yuri Cast A3 Poster Insert", "2010s", "standard", 10),

        # Monthly Comic Gene / Monthly Sylph — additional
        ("Monthly Comic Gene", "Given", "Clear File", "Comic Gene Given Mafuyu Clear File Insert", "2020s", "standard", 12),
        ("Monthly Comic Gene", "Yona of the Dawn", "Insert Poster", "Comic Gene Yona of the Dawn Hak & Yona A3 Poster", "2020s", "mid", 16),
        ("Monthly Comic Gene", "Toilet-bound Hanako-kun", "Clear File", "Comic Gene Hanako-kun Clear File Set Insert", "2020s", "standard", 14),

        # Comp Ace — additional
        ("Comp Ace", "Fate/Grand Order", "Insert Poster", "Comp Ace FGO Oberon A2 Poster Insert", "2020s", "mid", 22),
        ("Comp Ace", "Overlord", "Tapestry", "Comp Ace Overlord Ainz B2 Tapestry Appendix", "2020s", "mid", 28),
        ("Comp Ace", "Kadokawa Fate", "Magazine Issue", "Comp Ace Fate/Extra Record Feature Issue", "2020s", "mid", 18),

        # Dengeki Hobby Magazine — additional defunct vintage
        ("Dengeki Hobby Magazine", "Gundam", "Limited Model Kit", "Dengeki Hobby Exclusive HGUC Gouf Custom Kit", "2000s", "high", 60),
        ("Dengeki Hobby Magazine", "Macross", "Magazine Issue", "Dengeki Hobby Macross Frontier Kit Feature Issue", "2000s", "mid", 30),
        ("Dengeki Hobby Magazine", "Armored Core", "Magazine Issue", "Dengeki Hobby Armored Core Kotobukiya Feature", "2000s", "mid", 25),

        # Figure King — additional
        ("Figure King", "Kamen Rider", "Magazine Issue", "Figure King Kamen Rider S.H.Figuarts Special Feature", "2010s", "mid", 25),
        ("Figure King", "Ultraman", "Magazine Issue", "Figure King Ultraman Ultra-Act Complete Feature", "2010s", "mid", 22),
        ("Figure King", "Star Wars", "Magazine Issue", "Figure King Star Wars Hot Toys 1/6 Scale Feature", "2010s", "mid", 28),
        ("Figure King", "Transformers", "Magazine Issue", "Figure King Transformers Masterpiece MP Feature", "2000s", "mid", 25),

        # COSMODE / Cosplay magazines
        ("COSMODE", "Various", "Magazine Issue", "COSMODE Summer Comiket Special Issue 2015", "2010s", "mid", 22),
        ("COSMODE", "Various", "Magazine Issue", "COSMODE Cosplay World Championship Feature 2014", "2010s", "mid", 20),

        # Kadokawa magazines — additional
        ("Monthly Ace", "Evangelion", "Insert Poster", "Monthly Ace Evangelion ANIMA A3 Poster Insert", "2010s", "mid", 20),
        ("Monthly Ace", "Overlord", "Clear File", "Monthly Ace Overlord Shalltear Clear File Insert", "2020s", "standard", 12),

        # Monthly Afternoon — additional
        ("Monthly Afternoon", "Parasyte", "Magazine Issue", "Monthly Afternoon Parasyte Color Spread Issue", "1990s", "high", 50),
        ("Monthly Afternoon", "Ah! My Goddess", "Magazine Issue", "Monthly Afternoon Oh My Goddess Final Chapter", "2010s", "mid", 35),

        # Vintage 70s/80s additions
        ("Animage", "Lupin III", "B2 Poster", "Animage Lupin III Castle of Cagliostro B2 Poster 1979", "1970s", "grail", 180),
        ("Animage", "Gundam", "Pin-up Set", "Animage Mobile Suit Gundam Amuro Pin-up Set 1979", "1970s", "grail", 140),
        ("Animage", "Daitarn 3", "Insert Poster", "Animage Daitarn 3 A3 Poster Insert 1978", "1970s", "high", 60),
        ("Animage", "Zambot 3", "Insert Poster", "Animage Zambot 3 A3 Poster Insert 1977", "1970s", "high", 55),
        ("Newtype", "Royal Space Force", "B2 Poster", "Newtype Wings of Honneamise B2 Poster Insert 1987", "1980s", "high", 75),
        ("Newtype", "Bubblegum Crisis", "Insert Poster", "Newtype Bubblegum Crisis Knight Sabers A3 Poster 1987", "1980s", "high", 60),
        ("Newtype", "Megazone 23", "Insert Poster", "Newtype Megazone 23 Shogo & Eve A3 Poster 1985", "1980s", "high", 65),
        ("Newtype", "Legend of Galactic Heroes", "B2 Poster", "Newtype Legend of Galactic Heroes B2 Poster 1988", "1980s", "high", 80),
        ("Animage", "Votoms", "Insert Poster", "Animage Armored Trooper Votoms A3 Poster Insert 1983", "1980s", "high", 55),
        ("Animage", "Creamy Mami", "Pin-up Set", "Animage Creamy Mami Magical Girl Pin-up Set 1983", "1980s", "high", 60),

        # Vintage 90s additions
        ("Newtype", "Escaflowne", "B2 Poster", "Newtype Escaflowne Hitomi B2 Poster Insert 1996", "1990s", "high", 50),
        ("Newtype", "Macross Plus", "Insert Poster", "Newtype Macross Plus Isamu A2 Poster Insert 1995", "1990s", "high", 55),
        ("Newtype", "Gundam Wing", "B2 Poster", "Newtype Gundam Wing Heero Yuy B2 Poster Insert 1995", "1990s", "mid", 38),
        ("Animage", "Slayers", "Insert Poster", "Animage Slayers Lina Inverse A3 Poster Insert 1995", "1990s", "mid", 30),
        ("Animage", "Record of Lodoss War", "B2 Poster", "Animage Record of Lodoss War Deedlit B2 Poster 1990", "1990s", "high", 65),
        ("Animedia", "Tenchi Muyo!", "Pin-up Set", "Animedia Tenchi Muyo! Girls Pin-up Set 1994", "1990s", "mid", 30),
        ("Animedia", "Trigun", "Insert Poster", "Animedia Trigun Vash the Stampede A3 Poster 1998", "1990s", "mid", 28),
        ("Animedia", "GTO", "Insert Poster", "Animedia Great Teacher Onizuka A3 Poster Insert", "1990s", "mid", 25),
        ("Animedia", "Outlaw Star", "Insert Poster", "Animedia Outlaw Star Gene Starwind A3 Poster 1998", "1990s", "mid", 25),
        ("Animedia", "Serial Experiments Lain", "Insert Poster", "Animedia Serial Experiments Lain Lain A3 Poster", "1990s", "mid", 40),

        # Dengeki PlayStation / Game magazines
        ("Dengeki PlayStation", "Final Fantasy VII", "Magazine Issue", "Dengeki PlayStation FF VII Launch Feature 1997", "1990s", "high", 60),
        ("Dengeki PlayStation", "Kingdom Hearts", "Magazine Issue", "Dengeki PlayStation Kingdom Hearts Launch Feature", "2000s", "mid", 30),
        ("Dengeki PlayStation", "Metal Gear Solid", "Magazine Issue", "Dengeki PlayStation MGS Feature Issue 1998", "1990s", "high", 50),
        ("Dengeki PlayStation", "Persona 5", "Magazine Issue", "Dengeki PlayStation Persona 5 Exclusive Feature 2016", "2010s", "mid", 25),

        # Nintendo Dream
        ("Nintendo Dream", "Pokemon", "Magazine Issue", "Nintendo Dream Pokemon Ruby/Sapphire Feature 2002", "2000s", "mid", 30),
        ("Nintendo Dream", "Animal Crossing", "Magazine Issue", "Nintendo Dream Animal Crossing NH Feature 2020", "2020s", "standard", 14),
        ("Nintendo Dream", "Fire Emblem", "Insert Poster", "Nintendo Dream Fire Emblem Three Houses A3 Poster", "2010s", "standard", 12),
        ("Nintendo Dream", "Splatoon", "Clear File", "Nintendo Dream Splatoon 3 Clear File Insert", "2020s", "standard", 10),

        # Shonen Ace — Kadokawa
        ("Shonen Ace", "Evangelion", "Magazine Issue", "Shonen Ace Evangelion Manga Sadamoto Cover Issue", "2000s", "high", 55),
        ("Shonen Ace", "Evangelion", "Insert Poster", "Shonen Ace Evangelion 3.0+1.0 A2 Poster Insert", "2020s", "mid", 25),
        ("Shonen Ace", "The Melancholy of Haruhi", "Magazine Issue", "Shonen Ace Haruhi Suzumiya Manga Feature Issue", "2000s", "mid", 30),
        ("Shonen Ace", "Gundam: The Origin", "Magazine Issue", "Shonen Ace Gundam The Origin Yasuhiko Cover", "2000s", "mid", 28),
        ("Shonen Ace", "Future Diary", "Insert Poster", "Shonen Ace Future Diary Yuno A3 Poster Insert", "2000s", "mid", 20),

        # Champion / Akita Shoten
        ("Weekly Shonen Champion", "Baki", "Magazine Issue", "Weekly Shonen Champion Baki Hanma Feature Issue", "2000s", "mid", 25),
        ("Weekly Shonen Champion", "Yowamushi Pedal", "Magazine Issue", "Weekly Shonen Champion Yowamushi Pedal Cover", "2010s", "mid", 18),
        ("Weekly Shonen Champion", "Dragon Ball Super", "Magazine Issue", "Saikyo Jump Dragon Ball Super Exclusive Feature", "2020s", "mid", 18),

        # Additional unique/rare items
        ("Various", "Dragon Ball", "Shikishi Board", "Dragon Ball Toriyama Signed Shikishi Board Reprint", "2010s", "high", 80),
        ("Various", "One Piece", "Shikishi Board", "One Piece Oda Eiichiro Color Shikishi Board Insert", "2020s", "high", 65),
        ("Various", "Naruto", "Illustration Card", "Naruto Kishimoto Final Art Card Insert Set", "2010s", "mid", 35),
        ("Various", "Bleach", "Illustration Card", "Bleach Kubo Tite TYBW Art Card Insert Set", "2020s", "mid", 30),
        ("Various", "Demon Slayer", "Shikishi Board", "Demon Slayer Ufotable Shikishi Board Set", "2020s", "mid", 25),
        ("Various", "Jujutsu Kaisen", "Illustration Card", "Jujutsu Kaisen Akutami Gege Art Card Set Insert", "2020s", "mid", 28),
        ("Various", "Attack on Titan", "Shikishi Board", "Attack on Titan Isayama Hajime Final Shikishi Board", "2020s", "mid", 35),
        ("Various", "My Hero Academia", "Clear File", "My Hero Academia Jump Festa Exclusive Clear File Set", "2020s", "mid", 22),

        # Monthly Shonen Sirius / Kodansha
        ("Monthly Shonen Sirius", "That Time I Got Reincarnated as a Slime", "Magazine Issue", "Sirius Tensura Rimuru Cover Feature Issue", "2020s", "mid", 18),
        ("Monthly Shonen Sirius", "Kemono Jihen", "Clear File", "Sirius Kemono Jihen Kabane Clear File Insert", "2020s", "standard", 10),

        # Manga Time Kirara — 4-koma moe
        ("Manga Time Kirara", "K-On!", "Magazine Issue", "Manga Time Kirara K-On! Final Chapter Issue", "2010s", "high", 55),
        ("Manga Time Kirara", "Bocchi the Rock!", "Magazine Issue", "Manga Time Kirara Max Bocchi the Rock Cover Issue", "2020s", "mid", 30),
        ("Manga Time Kirara", "Is the Order a Rabbit?", "Magazine Issue", "Manga Time Kirara Max GochiUsa Cover Issue", "2020s", "mid", 22),
        ("Manga Time Kirara", "Hidamari Sketch", "Magazine Issue", "Manga Time Kirara Carat Hidamari Sketch Feature", "2010s", "mid", 20),

        # More Dengeki G's Magazine
        ("Dengeki G's Magazine", "Nijigasaki High School", "Tapestry", "Dengeki G's Nijigasaki Ayumu B2 Tapestry", "2020s", "mid", 22),
        ("Dengeki G's Magazine", "Love Live! Superstar!!", "Shikishi Board", "Dengeki G's Liella! 2nd Live Shikishi Board", "2020s", "mid", 25),
        ("Dengeki G's Magazine", "The Idolmaster Shiny Colors", "Clear File", "Dengeki G's Shiny Colors Illumination Stars Clear File", "2020s", "standard", 12),

        # More V Jump / Card game promos
        ("V Jump", "Yu-Gi-Oh!", "Promo Card Insert", "V Jump Ash Blossom & Joyous Spring Alt Art Promo", "2010s", "high", 65),
        ("V Jump", "Yu-Gi-Oh!", "Promo Card Insert", "V Jump Blue-Eyes Alternative Dragon Promo Card", "2010s", "high", 55),
        ("V Jump", "Dragon Ball Super", "Promo Card Insert", "V Jump DBS Card Game Vegito Blue Promo Card", "2020s", "mid", 35),

        # Hobby Japan Extra / Extras
        ("Hobby Japan", "Girls' Frontline", "Magazine Issue", "Hobby Japan Girls' Frontline Model Kit Feature", "2020s", "mid", 22),
        ("Hobby Japan", "Fate/Grand Order", "Magazine Issue", "Hobby Japan FGO Figure Special Feature Issue", "2020s", "mid", 25),

        # Additional weekly magazine one-shots
        ("Weekly Shonen Jump", "Spy x Family", "Magazine Issue", "Shonen Jump+ Spy x Family 10M Circulation Feature", "2020s", "mid", 30),
        ("Weekly Shonen Jump", "Dandadan", "Magazine Issue", "Shonen Jump+ Dandadan Anime Announcement Issue", "2020s", "mid", 25),
        ("Weekly Shonen Jump", "Kaiju No. 8", "Magazine Issue", "Shonen Jump+ Kaiju No. 8 Cover Feature Issue", "2020s", "mid", 28),

        # --- Round 6 additions (55 items) ---

        # More vintage Animage/Newtype 80s
        ("Animage", "Fang of the Sun Dougram", "Insert Poster", "Animage Dougram A3 Poster Insert 1982", "1980s", "high", 55),
        ("Animage", "Xabungle", "Insert Poster", "Animage Xabungle Jiron A3 Poster Insert 1982", "1980s", "high", 50),
        ("Animage", "Orguss", "B2 Poster", "Animage Super Dimension Century Orguss B2 Poster 1983", "1980s", "high", 55),
        ("Animage", "Dunbine", "Insert Poster", "Animage Aura Battler Dunbine A3 Poster Insert 1983", "1980s", "high", 50),
        ("Newtype", "Venus Wars", "B2 Poster", "Newtype Venus Wars Theatrical B2 Poster Insert 1989", "1980s", "high", 55),
        ("Newtype", "Gunbuster", "Insert Poster", "Newtype Gunbuster Noriko A2 Poster Insert 1988", "1980s", "high", 65),
        ("Newtype", "Dirty Pair Flash", "Insert Poster", "Newtype Dirty Pair Flash A3 Poster Insert 1994", "1990s", "mid", 25),
        ("Newtype", "Blue Seed", "Insert Poster", "Newtype Blue Seed Momiji A3 Poster Insert 1994", "1990s", "mid", 22),
        ("Newtype", "Nadesico", "B2 Poster", "Newtype Martian Successor Nadesico B2 Poster 1996", "1990s", "mid", 35),
        ("Newtype", "Outlaw Star", "Insert Poster", "Newtype Outlaw Star Melfina A3 Poster Insert 1998", "1990s", "mid", 28),

        # More CoroCoro & children's magazine
        ("CoroCoro Comic", "Beyblade Burst", "Insert Card", "CoroCoro Comic Beyblade Burst Special Insert Card", "2010s", "mid", 18),
        ("CoroCoro Comic", "Mini 4WD", "Magazine Issue", "CoroCoro Comic Mini 4WD Tamiya Feature 1988", "1980s", "high", 55),
        ("CoroCoro Comic", "Pokemon", "Magazine Issue", "CoroCoro Comic 2022 Nov Pokemon Scarlet/Violet Reveal", "2020s", "mid", 30),

        # More game magazines
        ("Famitsu", "Chrono Trigger", "Magazine Issue", "Famitsu Chrono Trigger Perfect Score 40/40 Issue 1995", "1990s", "grail", 120),
        ("Famitsu", "Legend of Zelda", "Magazine Issue", "Famitsu Zelda Ocarina of Time 40/40 Score Issue 1998", "1990s", "high", 80),
        ("Famitsu", "Vagrant Story", "Magazine Issue", "Famitsu Vagrant Story 40/40 Score Issue 2000", "2000s", "high", 60),
        ("Famitsu", "Metal Gear Solid 4", "Magazine Issue", "Famitsu MGS4 Perfect Score Feature Issue 2008", "2000s", "mid", 35),
        ("Dengeki PlayStation", "NieR Automata", "Magazine Issue", "Dengeki PlayStation NieR Automata Feature Issue", "2010s", "mid", 25),
        ("Dengeki PlayStation", "Bloodborne", "Magazine Issue", "Dengeki PlayStation Bloodborne Feature Issue 2015", "2010s", "mid", 22),

        # More Weekly Shonen Jump — classic covers
        ("Weekly Shonen Jump", "Haikyuu!!", "Magazine Issue", "Weekly Shonen Jump 2012 #12 Haikyuu!! Ch.1 Debut", "2010s", "high", 50),
        ("Weekly Shonen Jump", "The Promised Neverland", "Magazine Issue", "Weekly Shonen Jump 2016 #35 Promised Neverland Debut", "2010s", "mid", 40),
        ("Weekly Shonen Jump", "Act-Age", "Magazine Issue", "Weekly Shonen Jump 2018 #8 Act-Age Ch.1 Debut Issue", "2010s", "mid", 35),
        ("Weekly Shonen Jump", "Kimetsu no Yaiba", "Magazine Issue", "Weekly Shonen Jump 2016 #11 Demon Slayer Ch.1 Debut", "2010s", "grail", 120),
        ("Weekly Shonen Jump", "Hunter x Hunter", "Magazine Issue", "Weekly Shonen Jump 2018 #52 Hunter x Hunter Return Issue", "2010s", "mid", 35),

        # More Hobby Japan vintage
        ("Hobby Japan", "Macross", "Limited Model Kit", "Hobby Japan Exclusive VF-1J Hikaru Custom Kit", "2000s", "high", 70),
        ("Hobby Japan", "Gundam", "Magazine Issue", "Hobby Japan MG Gundam Nu Ver.Ka Complete Build Feature", "2000s", "mid", 28),
        ("Hobby Japan", "Dunbine", "Magazine Issue", "Hobby Japan Aura Battler Dunbine Kit Feature 1984", "1980s", "high", 55),

        # More Figure King
        ("Figure King", "Marvel", "Magazine Issue", "Figure King Marvel SHF Complete Feature Issue", "2010s", "mid", 22),
        ("Figure King", "DC Comics", "Magazine Issue", "Figure King DC Comics Statue Feature Issue", "2010s", "mid", 20),

        # More Monthly Gangan
        ("Monthly Gangan", "Fire Force", "Insert Poster", "Monthly Gangan Fire Force Shinra A3 Poster Insert", "2010s", "mid", 18),
        ("Monthly Gangan", "Yuri on Ice Comic", "Clear File", "Monthly Gangan Yuri on Ice Welcome to Madness Clear File", "2010s", "standard", 14),

        # More Megami Magazine
        ("Megami Magazine", "Sword Art Online", "Tapestry", "Megami Magazine SAO Asuna B2 Tapestry Appendix", "2020s", "mid", 28),
        ("Megami Magazine", "Violet Evergarden", "Clear File", "Megami Magazine Violet Evergarden Clear File Set", "2020s", "mid", 18),
        ("Megami Magazine", "Kaguya-sama", "Tapestry", "Megami Magazine Kaguya-sama Kaguya B2 Tapestry", "2020s", "mid", 22),
        ("Megami Magazine", "Bunny Girl Senpai", "Tapestry", "Megami Magazine Bunny Girl Senpai Mai B2 Tapestry", "2020s", "mid", 30),

        # More Nyantype
        ("Nyantype", "Konosuba", "Tapestry Insert", "Nyantype Konosuba Darkness B2 Tapestry Appendix", "2020s", "mid", 22),
        ("Nyantype", "Goblin Slayer", "Clear File", "Nyantype Goblin Slayer Priestess Clear File Insert", "2020s", "standard", 12),

        # Additional seinen magazine issues
        ("Young Jump", "Tokyo Ghoul", "Magazine Issue", "Young Jump Tokyo Ghoul Kaneki Cover Feature Issue", "2010s", "mid", 35),
        ("Young Jump", "Kingdom", "Magazine Issue", "Young Jump Kingdom 500th Chapter Anniversary Issue", "2020s", "mid", 30),
        ("Young Jump", "Oshi no Ko", "Magazine Issue", "Young Jump Oshi no Ko Ch.1 Debut Aka Akasaka Issue", "2020s", "high", 55),
        ("Young Jump", "Kaguya-sama", "Magazine Issue", "Young Jump Kaguya-sama Final Chapter Issue", "2020s", "mid", 35),
        ("Big Comic Spirits", "My Dress-Up Darling", "Magazine Issue", "Young Gangan My Dress-Up Darling Color Spread Issue", "2020s", "mid", 28),

        # Rare promotional booklets
        ("Various", "Studio Ghibli", "Promo Booklet", "Cinema Comic Studio Ghibli Theater Exclusive Booklet Set", "2000s", "high", 75),
        ("Various", "Evangelion", "Promo Booklet", "Evangelion Rebuild Theater Exclusive Mini Booklet Set", "2020s", "mid", 35),
        ("Various", "Makoto Shinkai", "Promo Booklet", "Suzume Theater Exclusive B5 Art Booklet", "2020s", "mid", 25),
        ("Various", "Dragon Ball", "Promo Booklet", "Dragon Ball Super: Super Hero Theater Exclusive Booklet", "2020s", "mid", 20),
        ("Various", "One Piece Film Red", "Promo Booklet", "One Piece Film Red Theater Exclusive Vol.1-4 Booklet Set", "2020s", "mid", 30),

        # Model Graphix additions
        ("Model Graphix", "Patlabor", "Magazine Issue", "Model Graphix Patlabor Ingram Kit Building Feature 1990", "1990s", "high", 45),
        ("Model Graphix", "Virtual-On", "Magazine Issue", "Model Graphix Virtual-On Temjin Kit Feature Issue", "2000s", "mid", 25),

        # Additional Shonen Ace
        ("Shonen Ace", "Deadman Wonderland", "Insert Poster", "Shonen Ace Deadman Wonderland Ganta A3 Poster", "2000s", "mid", 18),
        ("Shonen Ace", "Eureka Seven", "Magazine Issue", "Shonen Ace Eureka Seven Manga Feature Issue", "2000s", "mid", 22),

        # --- Round 7 additions (60 items) ---

        # Weekly Shonen Jump — additional classic & modern milestones
        ("Weekly Shonen Jump", "Bobobo-bo Bo-bobo", "Magazine Issue", "Weekly Shonen Jump 2001 #12 Bobobo-bo Bo-bobo Debut", "2000s", "mid", 25),
        ("Weekly Shonen Jump", "Toriko", "Magazine Issue", "Weekly Shonen Jump 2008 #25 Toriko Ch.1 Debut Issue", "2000s", "mid", 30),
        ("Weekly Shonen Jump", "Medaka Box", "Magazine Issue", "Weekly Shonen Jump 2009 #10 Medaka Box Ch.1 Debut", "2000s", "mid", 25),
        ("Weekly Shonen Jump", "Nisekoi", "Magazine Issue", "Weekly Shonen Jump 2011 #48 Nisekoi Ch.1 Debut Issue", "2010s", "mid", 28),
        ("Weekly Shonen Jump", "Food Wars! Shokugeki no Soma", "Magazine Issue", "Weekly Shonen Jump 2012 #52 Food Wars Ch.1 Debut", "2010s", "mid", 30),
        ("Weekly Shonen Jump", "We Never Learn", "Magazine Issue", "Weekly Shonen Jump 2017 #10 We Never Learn Debut", "2010s", "mid", 22),

        # CoroCoro Comic — additional rare issues
        ("CoroCoro Comic", "Pokemon", "Insert Card", "CoroCoro Comic Celebi Promo Card Insert 2001", "2000s", "high", 65),
        ("CoroCoro Comic", "Pokemon", "Magazine Issue", "CoroCoro Comic 2021 Nov Pokemon Legends Arceus Reveal", "2020s", "mid", 28),
        ("CoroCoro Comic", "Duel Masters", "Insert Card", "CoroCoro Comic Duel Masters Promo Bolmeteus Card", "2000s", "mid", 30),
        ("CoroCoro Comic", "Tamagotchi", "Magazine Issue", "CoroCoro Comic 1997 Tamagotchi Special Feature Issue", "1990s", "mid", 35),

        # V Jump — additional Yu-Gi-Oh! & Dragon Ball promos
        ("V Jump", "Yu-Gi-Oh!", "Promo Card Insert", "V Jump Galaxy-Eyes Photon Dragon Promo Card", "2010s", "high", 50),
        ("V Jump", "Yu-Gi-Oh!", "Promo Card Insert", "V Jump Decode Talker Promo Card Insert", "2010s", "mid", 35),
        ("V Jump", "Dragon Ball Super", "Promo Card Insert", "V Jump DBS Card Game Broly Promo Card Insert", "2020s", "mid", 30),

        # Famitsu — additional rare & vintage issues
        ("Famitsu", "Dragon Quest III", "Magazine Issue", "Famitsu Dragon Quest III Social Phenomenon Feature 1988", "1980s", "high", 90),
        ("Famitsu", "Super Smash Bros. Ultimate", "Insert Poster", "Famitsu Smash Bros Ultimate Full Roster A2 Poster", "2010s", "mid", 18),
        ("Famitsu", "Splatoon 3", "Clear File", "Famitsu Splatoon 3 Squid Sisters Clear File Insert", "2020s", "standard", 10),
        ("Famitsu", "Monster Hunter World", "Magazine Issue", "Famitsu Monster Hunter World 10M Copies Feature", "2010s", "mid", 20),

        # Newtype — additional 2000s era inserts
        ("Newtype", "Eureka Seven", "B2 Poster", "Newtype Eureka Seven Renton & Eureka B2 Poster 2005", "2000s", "mid", 30),
        ("Newtype", "Haruhi Suzumiya", "Insert Poster", "Newtype Haruhi Suzumiya SOS Brigade A2 Poster 2006", "2000s", "mid", 35),
        ("Newtype", "Gurren Lagann", "B2 Poster", "Newtype Gurren Lagann Simon & Kamina B2 Poster 2007", "2000s", "mid", 32),
        ("Newtype", "Lucky Star", "Clear File", "Newtype Lucky Star Konata Clear File Insert 2007", "2000s", "standard", 14),
        ("Newtype", "Clannad", "Insert Poster", "Newtype Clannad After Story Nagisa A3 Poster 2008", "2000s", "mid", 22),
        ("Newtype", "K-On!", "B2 Poster", "Newtype K-On! Ho-kago Tea Time B2 Poster Insert 2009", "2000s", "mid", 28),

        # Animage — additional 1990s rare posters
        ("Animage", "Ranma 1/2", "Pin-up Set", "Animage Ranma 1/2 Female Ranma Pin-up Set 1990", "1990s", "high", 55),
        ("Animage", "Nadia: Secret of Blue Water", "B2 Poster", "Animage Nadia B2 Poster Insert 1990", "1990s", "high", 65),
        ("Animage", "Princess Mononoke", "Insert Poster", "Animage Princess Mononoke Theatrical A2 Poster 1997", "1990s", "grail", 110),

        # Animedia — additional 2000s/2010s inserts
        ("Animedia", "Code Geass", "Pin-up Poster", "Animedia Code Geass Lelouch & Suzaku A3 Pin-up", "2000s", "mid", 30),
        ("Animedia", "Eureka Seven", "Insert Poster", "Animedia Eureka Seven Eureka & Renton A3 Poster", "2000s", "mid", 25),
        ("Animedia", "Toradora!", "Pin-up Set", "Animedia Toradora! Taiga & Ryuuji Pin-up Set", "2000s", "mid", 22),
        ("Animedia", "Durarara!!", "Insert Poster", "Animedia Durarara!! Shizuo & Izaya A3 Poster", "2010s", "mid", 22),

        # Weekly Shonen Sunday — additional debuts
        ("Weekly Shonen Sunday", "Zatch Bell!", "Magazine Issue", "Weekly Shonen Sunday 2001 #6-7 Zatch Bell Ch.1 Debut", "2000s", "mid", 35),
        ("Weekly Shonen Sunday", "Detective Conan", "Magazine Issue", "Weekly Shonen Sunday Conan 1100th Chapter Feature", "2020s", "high", 55),
        ("Weekly Shonen Sunday", "Maison Ikkoku", "Magazine Issue", "Big Comic Spirits 1980 #6 Maison Ikkoku Ch.1 Debut", "1980s", "grail", 160),

        # Weekly Shonen Magazine — additional milestones
        ("Weekly Shonen Magazine", "Kodansha", "Magazine Issue", "Weekly Shonen Magazine 1959 #1 Inaugural Issue Reprint", "1960s", "grail", 280),
        ("Weekly Shonen Magazine", "Devilman", "Magazine Issue", "Weekly Shonen Magazine 1972 #25 Devilman Nagai Cover", "1970s", "grail", 200),
        ("Weekly Shonen Magazine", "Ashita no Joe", "Magazine Issue", "Weekly Shonen Magazine 1968 #1 Ashita no Joe Debut", "1960s", "grail", 250),

        # Dengeki PlayStation — additional
        ("Dengeki PlayStation", "Dragon Quest VIII", "Magazine Issue", "Dengeki PlayStation DQVIII Feature Issue 2004", "2000s", "mid", 25),
        ("Dengeki PlayStation", "Tales of Vesperia", "Clear File", "Dengeki PlayStation Tales of Vesperia Clear File 2008", "2000s", "standard", 14),

        # Nintendo Dream — additional
        ("Nintendo Dream", "Pokemon", "Magazine Issue", "Nintendo Dream Pokemon Diamond/Pearl Feature 2006", "2000s", "mid", 25),
        ("Nintendo Dream", "Zelda", "Insert Poster", "Nintendo Dream Zelda Breath of the Wild A3 Poster", "2010s", "mid", 18),
        ("Nintendo Dream", "Kirby", "Clear File", "Nintendo Dream Kirby and the Forgotten Land Clear File", "2020s", "standard", 10),

        # Young Jump — additional seinen milestones
        ("Young Jump", "Gantz", "Magazine Issue", "Young Jump Gantz Hiroya Oku Cover Feature Issue", "2000s", "mid", 30),
        ("Young Jump", "Terra Formars", "Magazine Issue", "Young Jump Terra Formars Cover Feature Issue", "2010s", "mid", 22),
        ("Young Jump", "Golden Kamuy", "Magazine Issue", "Young Jump Golden Kamuy Final Chapter Issue", "2020s", "mid", 35),

        # Dengeki G's Magazine — additional game/idol inserts
        ("Dengeki G's Magazine", "Idoly Pride", "Clear File", "Dengeki G's Idoly Pride Kotono Clear File Insert", "2020s", "standard", 10),
        ("Dengeki G's Magazine", "D4DJ", "Acrylic Stand", "Dengeki G's D4DJ Happy Around! Acrylic Stand Set", "2020s", "standard", 12),

        # Megami Magazine — additional rare tapestries
        ("Megami Magazine", "Dandadan", "Tapestry", "Megami Magazine Dandadan Momo B2 Tapestry", "2020s", "mid", 25),
        ("Megami Magazine", "Solo Leveling", "Clear File", "Megami Magazine Solo Leveling Cha Hae-In Clear File", "2020s", "standard", 14),
        ("Megami Magazine", "Apothecary Diaries", "Tapestry", "Megami Magazine Apothecary Diaries Maomao B2 Tapestry", "2020s", "mid", 28),

        # Hobby Japan — additional modern features
        ("Hobby Japan", "Gundam", "Magazine Issue", "Hobby Japan RG God Gundam Complete Build Feature 2024", "2020s", "mid", 25),
        ("Hobby Japan", "Macross", "Magazine Issue", "Hobby Japan DX Chogokin VF-25 Renewal Feature Issue", "2020s", "mid", 22),
        ("Hobby Japan", "Gundam", "Magazine Issue", "Hobby Japan MG Freedom Gundam Ver.2.0 Build Feature", "2010s", "mid", 22),

        # Shonen Ace — additional Kadokawa
        ("Shonen Ace", "Evangelion", "Magazine Issue", "Shonen Ace Evangelion Manga Final Volume Feature Issue", "2010s", "high", 50),
        ("Shonen Ace", "Fate/Apocrypha", "Insert Poster", "Shonen Ace Fate/Apocrypha Mordred A3 Poster Insert", "2010s", "mid", 18),

        # Comp Ace — additional
        ("Comp Ace", "Fate/Grand Order", "Magazine Issue", "Comp Ace FGO Manga Section Anthology Feature Issue", "2020s", "mid", 20),
        ("Comp Ace", "Overlord", "Insert Poster", "Comp Ace Overlord Ainz & Albedo A2 Poster Insert", "2020s", "mid", 22),
    ]

    catalog = []
    for magazine, franchise, item_type, name, era, tier, price in items:
        catalog.append({
            "magazine": magazine,
            "franchise": franchise,
            "item_type": item_type,
            "name": name,
            "era": era,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    magazine = item["magazine"]
    name = item["name"]
    franchise = item["franchise"]
    item_type = item["item_type"]
    era = item["era"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{magazine}-{name}"),
        title=name,
        set_code=slugify(magazine),
        brand=magazine,
        rarity=item["rarity_tier"].title(),
        notes=f"{magazine} | {franchise} | {item_type} | {era}",
        attributes_json={
            "magazine": magazine,
            "franchise": franchise,
            "item_type": item_type,
            "era": era,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    era = item["era"]
    edition_scores = {
        "1960s": 0.95,
        "1970s": 0.92,
        "1980s": 0.90,
        "1990s": 0.75,
        "2000s": 0.55,
        "2010s": 0.45,
        "2020s": 0.30,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_scores.get(era, 0.5),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import JP magazine exclusives catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== JP Magazine Exclusives Import ===")

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

    logger.info(f"\n=== JP Magazine Exclusives Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
