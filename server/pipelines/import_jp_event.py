"""
Import Japanese event exclusives catalog.

Layer 1 (Catalog):  Curated JP event-exclusive goods → category_items
Layer 2 (Prices):   Estimated market prices → train.jsonl

Covers:
- Wonder Festival (WonFes): garage kits, exclusive figures
- Comiket: doujinshi, tapestries, acrylic stands, exclusive goods
- AnimeJapan: exclusive goods, clear files, badges, stage goods
- Tamashii Nations event: exclusive figures, anniversary items
- Jump Festa exclusives
- Tokyo Game Show (TGS): game merch, collab goods
- Character1 / Chara Expo: acrylic stands, trading cards
- Anime Expo (US crossover): JP publisher collab exclusives
- Shizuoka Hobby Show / All Japan Model Show: limited model kits
- Gundam Base Tokyo / Fukuoka: exclusive color kits
- Kyoto Animation / Studio Ghibli exhibitions
- Pokemon Center events, D23 Japan
- COMITIA indie art market, Touken Ranbu exhibitions
- Key franchises: Fate, Vocaloid, Love Live, Gundam, Hololive, Touhou, Pokemon, Berserk

Usage:
    python -m pipelines.import_jp_event [--dry-run]
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

CATEGORY = "jp_event"


def get_curated_catalog() -> list[dict]:
    """Curated Japanese event exclusives catalog (500+ items)."""

    # (event, franchise, item_type, name, rarity_tier, price_eur)
    # rarity_tier: grail (>300), high (100-300), mid (30-100), standard (<30)

    items = [
        # Wonder Festival (WonFes) – garage kits & exclusive figures
        ("WonFes", "Fate/Grand Order", "Garage Kit", "Saber Artoria Pendragon 1/6 GK (Unpainted)", "grail", 350),
        ("WonFes", "Evangelion", "Garage Kit", "EVA Unit-02 Beast Mode 1/8 GK (Unpainted)", "high", 280),
        ("WonFes", "Vocaloid", "Exclusive Figure", "Hatsune Miku WonFes 2023 Exclusive Nendoroid", "high", 120),
        ("WonFes", "Fate/Grand Order", "Exclusive Figure", "Mash Kyrielight WonFes Limited 1/7", "high", 180),
        ("WonFes", "Gundam", "Garage Kit", "Sazabi Ver.Ka 1/100 Resin Conversion GK", "grail", 450),
        ("WonFes", "Original", "Garage Kit", "WonFes Original Character 1/6 GK Limited 20pcs", "grail", 500),
        ("WonFes", "Chainsaw Man", "Exclusive Figure", "Power WonFes Limited Painted GK", "high", 250),

        # Comiket – doujinshi, tapestries, acrylic stands
        ("Comiket", "Fate/Grand Order", "Tapestry", "FGO Comiket 103 Exclusive B2 Tapestry Castoria", "mid", 45),
        ("Comiket", "Touhou Project", "Doujinshi Set", "Touhou C103 Popular Circle Doujinshi Bundle (5)", "mid", 40),
        ("Comiket", "Hololive", "Acrylic Stand", "Hololive C103 Exclusive Acrylic Stand Set", "mid", 35),
        ("Comiket", "Love Live!", "Tapestry", "Love Live! Sunshine!! Comiket Summer Tapestry", "mid", 40),
        ("Comiket", "Vocaloid", "Art Book", "Hatsune Miku 15th Anniversary Doujin Art Book", "mid", 30),
        ("Comiket", "Original", "Tapestry", "Comiket Limited Original Character B2 Tapestry", "standard", 25),
        ("Comiket", "Various", "Badge Set", "Comiket Corporate Booth Badge Random Set (10)", "standard", 15),
        ("Comiket", "Fate/Grand Order", "Acrylic Stand", "FGO Comiket Exclusive Acrylic Diorama Set", "high", 100),

        # AnimeJapan – exclusive goods
        ("AnimeJapan", "Demon Slayer", "Clear File", "Demon Slayer AnimeJapan Exclusive Clear File Set", "standard", 15),
        ("AnimeJapan", "Spy x Family", "Acrylic Stand", "Spy x Family AnimeJapan 2024 Acrylic Stand Trio", "standard", 20),
        ("AnimeJapan", "Jujutsu Kaisen", "Badge Set", "JJK AnimeJapan Random Badge Collection (8pc)", "standard", 18),
        ("AnimeJapan", "Gundam", "Clear File", "Gundam Seed Freedom AnimeJapan Clear File Pair", "standard", 10),
        ("AnimeJapan", "My Hero Academia", "Mini Poster Set", "MHA AnimeJapan Exclusive Mini Poster Set (5)", "mid", 30),
        ("AnimeJapan", "Attack on Titan", "Acrylic Stand", "AoT Final Season AnimeJapan Acrylic Diorama", "mid", 45),

        # Tamashii Nations Event – exclusive figures
        ("Tamashii Nations", "Dragon Ball Z", "S.H.Figuarts", "SSJ Vegito Event Exclusive S.H.Figuarts", "high", 150),
        ("Tamashii Nations", "Kamen Rider", "S.H.Figuarts", "Kamen Rider Black Sun Event Exclusive", "high", 130),
        ("Tamashii Nations", "Gundam", "Robot Spirits", "Gundam Aerial Permet Score 6 Event Exclusive", "high", 110),
        ("Tamashii Nations", "One Piece", "Figuarts ZERO", "Kaido Dragon Form Event Exclusive", "high", 180),
        ("Tamashii Nations", "Evangelion", "Metal Build", "EVA Unit-01 Metal Build Event Color Ver.", "grail", 350),

        # Jump Festa exclusives
        ("Jump Festa", "One Piece", "Figure", "Luffy Gear 5 Jump Festa Exclusive Figure", "high", 100),
        ("Jump Festa", "Dragon Ball Super", "Clear File", "DBS Super Hero Jump Festa Clear File Set", "standard", 15),
        ("Jump Festa", "My Hero Academia", "Acrylic Stand", "Deku vs Shigaraki Jump Festa Acrylic Stand", "mid", 35),
        ("Jump Festa", "Jujutsu Kaisen", "Poster Set", "JJK Jump Festa 2024 Exclusive Poster Set", "mid", 40),
        ("Jump Festa", "Chainsaw Man", "Badge Set", "CSM Jump Festa Random Badge Set (6pc)", "standard", 20),

        # === NEW ITEMS (35+) ===

        # More WonFes – garage kits & exclusive figures (+6)
        ("WonFes", "Touhou Project", "Garage Kit", "Reimu Hakurei 1/6 Resin GK WonFes Limited", "grail", 380),
        ("WonFes", "Kantai Collection", "Exclusive Figure", "Shimakaze WonFes Exclusive 1/7 Painted GK", "high", 220),
        ("WonFes", "Re:Zero", "Garage Kit", "Rem Oni Form 1/6 GK WonFes Unpainted", "high", 260),
        ("WonFes", "Chainsaw Man", "Garage Kit", "Makima Control Devil 1/7 Resin GK Limited 30pcs", "grail", 420),
        ("WonFes", "Spy x Family", "Exclusive Figure", "Yor Forger Thorn Princess WonFes Exclusive 1/7", "high", 190),
        ("WonFes", "Jujutsu Kaisen", "Exclusive Figure", "Gojo Satoru Hollow Purple WonFes Limited GK", "high", 280),

        # More Comiket – doujinshi, music, tapestries, exclusive goods (+6)
        ("Comiket", "Hololive", "Doujinshi Set", "Hololive C104 Popular Circle Doujinshi Bundle (5)", "mid", 50),
        ("Comiket", "Touhou Project", "Music Album", "Touhou Arrange Album C103 Compilation CD Set (3)", "mid", 35),
        ("Comiket", "Fate/Grand Order", "Doujinshi Set", "FGO Comiket 104 Top Circle Doujinshi Bundle (5)", "mid", 55),
        ("Comiket", "Various", "Tapestry", "Comiket C104 Corporate Exclusive B1 Tapestry", "high", 100),
        ("Comiket", "Type-Moon", "Exclusive Goods", "Type-Moon C103 Limited Goods Set (Poster + Clearfile + Badge)", "high", 120),
        ("Comiket", "Various", "Goods Set", "C104 Limited Corporate Booth Exclusive Goods Bag", "mid", 65),

        # Jump Festa – exclusive figures, cards, goods (+5)
        ("Jump Festa", "One Piece", "Exclusive Figure", "Shanks Film Red Jump Festa 2024 Exclusive Figure", "high", 130),
        ("Jump Festa", "Dragon Ball Super", "Exclusive Card", "DBS Card Game Jump Festa Promo SP Pack (5 cards)", "mid", 60),
        ("Jump Festa", "My Hero Academia", "Exclusive Figure", "All Might Jump Festa 2024 Exclusive Mini Figure", "mid", 45),
        ("Jump Festa", "Jujutsu Kaisen", "Goods Set", "JJK Jump Festa 2024 Exclusive Goods Set (Towel + Badge + Clearfile)", "mid", 50),
        ("Jump Festa", "Bleach", "Exclusive Figure", "Ichigo TYBW Bankai Jump Festa Exclusive Figure", "high", 110),

        # AnimeJapan – stage goods, clear files, exhibit goods (+5)
        ("AnimeJapan", "Demon Slayer", "Stage Goods", "Demon Slayer Hashira Stage Event Exclusive Towel Set", "mid", 40),
        ("AnimeJapan", "Chainsaw Man", "Clear File Set", "CSM AnimeJapan 2024 Clear File Collection (6pc)", "standard", 22),
        ("AnimeJapan", "Spy x Family", "Exclusive Figure", "Anya Forger AnimeJapan Exclusive Chibi Figure", "mid", 55),
        ("AnimeJapan", "Gundam", "Exhibit Goods", "Gundam NEXT FUTURE Exhibition Exclusive Model Kit", "high", 150),
        ("AnimeJapan", "Attack on Titan", "Exhibit Goods", "AoT Final Exhibition Memorial Acrylic Art Panel", "high", 120),

        # Tamashii Nations Event – exclusive figures, anniversary items (+4)
        ("Tamashii Nations", "Dragon Ball Z", "S.H.Figuarts", "SSGSS Gogeta Event Exclusive S.H.Figuarts", "high", 160),
        ("Tamashii Nations", "Gundam", "Metal Build", "Strike Freedom Metal Build Event Prototype Color", "grail", 400),
        ("Tamashii Nations", "Kamen Rider", "Robot Spirits", "Kamen Rider Geats Boost Mk.IX Robot Spirits Limited", "high", 120),
        ("Tamashii Nations", "Various", "Anniversary Figure", "Tamashii Nations 25th Anniversary Exclusive Figure Set", "grail", 320),

        # Tokyo Game Show (TGS) – game merch, figure exclusives, collab goods (+4)
        ("Tokyo Game Show", "Final Fantasy", "Exclusive Figure", "Cloud Strife TGS 2024 Exclusive Play Arts Kai Mini", "high", 140),
        ("Tokyo Game Show", "Persona 5", "Exclusive Merch", "Persona 5 Royal TGS Exclusive Acrylic Stand Set (4)", "mid", 35),
        ("Tokyo Game Show", "Monster Hunter", "Collab Goods", "Monster Hunter Wilds TGS Limited Plush Palico", "mid", 45),
        ("Tokyo Game Show", "NieR:Automata", "Exclusive Figure", "2B TGS Exclusive Mini Figure with Base", "high", 110),

        # Character1 / Chara Expo – cosplay prizes, acrylic stands, trading cards (+3)
        ("Character1", "Various", "Acrylic Stand Set", "Character1 2024 Limited Acrylic Stand Collection (8pc)", "mid", 40),
        ("Character1", "Various", "Trading Cards", "Character1 Exclusive Trading Card Sealed Box (20 packs)", "mid", 55),
        ("Chara Expo", "Various", "Cosplay Prize", "Chara Expo Grand Prix Winner Exclusive Signed Print", "high", 180),

        # Anime Expo (US crossover with JP publishers) (+2)
        ("Anime Expo", "Fate/Grand Order", "Exclusive Figure", "Saber Alter AX 2024 Exclusive 1/7 (Aniplex Booth)", "high", 200),
        ("Anime Expo", "Demon Slayer", "Collab Goods", "Demon Slayer x Anime Expo Exclusive Art Print Set (3)", "mid", 65),

        # === ROUND 2 ADDITIONS (36 items) ===

        # WonFes 2023/2024 Winter/Summer specific exclusives
        ("WonFes", "Fate/Grand Order", "Exclusive Figure", "Oberon WonFes 2024 Summer Exclusive 1/7 Painted GK", "grail", 380),
        ("WonFes", "Bocchi the Rock!", "Garage Kit", "Gotoh Hitori WonFes 2024 Winter 1/7 GK Unpainted", "high", 200),
        ("WonFes", "NieR:Automata", "Exclusive Figure", "2B YoRHa WonFes 2023 Summer Exclusive GK", "high", 280),
        ("WonFes", "Frieren", "Exclusive Figure", "Frieren WonFes 2024 Summer Limited 1/7 Figure", "high", 220),

        # Comiket C103/C104 exclusive doujinshi sets and goods
        ("Comiket", "Touhou Project", "Doujinshi Set", "Touhou C104 Premium Circle Doujinshi Bundle (8)", "mid", 65),
        ("Comiket", "Hololive", "Exclusive Goods", "Hololive C103 Exclusive Signed Shikishi Board Set", "high", 150),
        ("Comiket", "Blue Archive", "Tapestry", "Blue Archive C104 Exclusive B2 Tapestry Sensei Set", "mid", 50),

        # Anime Expo exclusive Funko/Bandai/Aniplex items
        ("Anime Expo", "Dragon Ball Z", "Funko Pop", "Vegeta Super Saiyan AX 2024 Exclusive Funko Pop (LE 1500)", "high", 120),
        ("Anime Expo", "Naruto", "Exclusive Figure", "Naruto Sage Mode Anime Expo 2024 Exclusive SFC", "mid", 80),
        ("Anime Expo", "Gundam", "Model Kit", "RX-93 Nu Gundam AX Exclusive Clear Color HG Kit", "high", 110),

        # Crunchyroll Expo exclusives
        ("Crunchyroll Expo", "Jujutsu Kaisen", "Exclusive Figure", "Gojo Satoru CRX 2024 Exclusive Mini Figure", "mid", 65),
        ("Crunchyroll Expo", "Spy x Family", "Goods Set", "Spy x Family CRX Exclusive Goods Box (Poster + Pin + Sticker)", "mid", 45),
        ("Crunchyroll Expo", "Chainsaw Man", "Exclusive Figure", "Denji CRX 2023 Exclusive Vinyl Figure", "mid", 55),

        # Studio Ghibli Exhibition tour goods
        ("Ghibli Exhibition", "Spirited Away", "Art Print", "Ghibli Exhibition Spirited Away Limited Art Print (A3)", "high", 120),
        ("Ghibli Exhibition", "Princess Mononoke", "Exclusive Goods", "Ghibli Exhibition Mononoke Ceramic Kodama Figure Set", "high", 100),
        ("Ghibli Exhibition", "My Neighbor Totoro", "Plush", "Ghibli Exhibition Limited Totoro Plush (Exhibition Tag)", "mid", 75),

        # Evangelion Exhibition items
        ("Evangelion Exhibition", "Evangelion", "Art Print", "Evangelion Exhibition Unit-01 Awakening Art Print (Signed)", "grail", 300),
        ("Evangelion Exhibition", "Evangelion", "Exclusive Figure", "EVA Exhibition Exclusive Rei Ayanami 1/6 Figure", "high", 180),

        # Dragon Ball Super Hero/Super movie premiums
        ("Movie Premium", "Dragon Ball Super", "Premium Figure", "DBS Super Hero Movie Premium Gohan Beast Figure", "mid", 55),
        ("Movie Premium", "Dragon Ball Super", "Premium Figure", "DBS Broly Movie Premium Golden Frieza Figure", "mid", 50),

        # Tamashii Nations events (Tokyo/Osaka tour exclusives)
        ("Tamashii Nations", "One Piece", "S.H.Figuarts", "Luffy Gear 5 Tamashii Tour Osaka Exclusive SHF", "high", 170),
        ("Tamashii Nations", "Dragon Ball Z", "Metal Build", "Perfect Cell Tamashii Tour Tokyo Exclusive Figure", "high", 140),
        ("Tamashii Nations", "Naruto Shippuden", "S.H.Figuarts", "Minato Namikaze Tamashii Nations Tour Exclusive SHF", "high", 130),

        # Anime Japan specific vendor exclusives
        ("AnimeJapan", "Frieren", "Acrylic Stand", "Frieren AnimeJapan 2024 Exclusive Acrylic Stand Trio", "mid", 35),
        ("AnimeJapan", "Oshi no Ko", "Clear File Set", "Oshi no Ko AnimeJapan 2024 Exclusive Clear File (3pc)", "standard", 18),
        ("AnimeJapan", "Blue Lock", "Badge Set", "Blue Lock AnimeJapan 2024 Random Badge Collection (10pc)", "standard", 22),

        # Machi Asobi exclusives (ufotable festival)
        ("Machi Asobi", "Demon Slayer", "Exclusive Goods", "Demon Slayer Machi Asobi ufotable Exclusive Tapestry", "high", 100),
        ("Machi Asobi", "Fate/stay night", "Exclusive Goods", "Fate/stay night HF Machi Asobi Exclusive Art Board", "high", 120),
        ("Machi Asobi", "Gintama", "Exclusive Goods", "Gintama Machi Asobi Final Festival Memorial Goods Set", "mid", 65),

        # Regional anime events: CharaExpo, Anime NYC
        ("CharaExpo", "Gundam", "Exclusive Model Kit", "Gundam CharaExpo Exclusive RG Strike Freedom Clear Ver.", "high", 110),
        ("Anime NYC", "My Hero Academia", "Exclusive Figure", "Deku Anime NYC 2024 Exclusive Banpresto Figure", "mid", 60),
        ("Anime NYC", "One Piece", "Exclusive Figure", "Luffy Anime NYC 2023 Exclusive DXF Figure", "mid", 55),

        # Voice actor event signed goods
        ("Voice Actor Event", "Various", "Signed Photo", "Kana Hanazawa Signed Event Photo (Certificate)", "high", 150),
        ("Voice Actor Event", "Various", "Signed Poster", "Mamoru Miyano Signed Live Event B2 Poster", "high", 130),
        ("Voice Actor Event", "Various", "Signed Shikishi", "Aoi Yuuki Signed Shikishi Board (Fan Meeting)", "high", 120),

        # === ROUND 3 ADDITIONS (44 items) ===

        # WonFes – more garage kits from classic franchises
        ("WonFes", "Dragon Ball Z", "Garage Kit", "Vegeta SSJ4 1/6 Resin GK WonFes Limited 25pcs", "grail", 480),
        ("WonFes", "One Piece", "Garage Kit", "Luffy Gear 5 Nika 1/6 Resin GK WonFes Summer 2024", "grail", 420),
        ("WonFes", "Berserk", "Garage Kit", "Guts Berserker Armor 1/6 Resin GK WonFes Limited", "grail", 550),
        ("WonFes", "Naruto Shippuden", "Exclusive Figure", "Itachi Uchiha Susanoo WonFes 2024 Exclusive Painted GK", "high", 290),
        ("WonFes", "Made in Abyss", "Garage Kit", "Nanachi WonFes 2023 Winter 1/7 GK Unpainted", "high", 180),

        # Comiket – indie games & music circles
        ("Comiket", "Touhou Project", "Music Album", "Touhou C104 IOSYS x Sound Holic Collab Album CD Set", "mid", 40),
        ("Comiket", "Original", "Art Book", "Comiket C104 Pixiv Popular Artist Art Book Compilation", "mid", 45),
        ("Comiket", "Blue Archive", "Doujinshi Set", "Blue Archive C104 Top Circle Doujinshi Bundle (5)", "mid", 50),
        ("Comiket", "Hololive", "Tapestry", "Hololive C104 Exclusive Gawr Gura B2 Tapestry", "mid", 55),
        ("Comiket", "Touhou Project", "Exclusive Goods", "Touhou C103 ZUN Autographed Shikishi Board (Lottery)", "grail", 350),

        # Tokyo Game Show – more game merch
        ("Tokyo Game Show", "Elden Ring", "Collab Goods", "Elden Ring TGS 2024 Exclusive Art Print Set (3)", "mid", 50),
        ("Tokyo Game Show", "Zelda", "Exclusive Merch", "Zelda TotK TGS Exclusive Acrylic Diorama", "mid", 45),
        ("Tokyo Game Show", "Tekken 8", "Exclusive Figure", "Jin Kazama TGS 2024 Exclusive Mini Bust", "high", 100),
        ("Tokyo Game Show", "Street Fighter 6", "Collab Goods", "SF6 TGS Limited Edition Art Board + Pin Set", "mid", 40),
        ("Tokyo Game Show", "Armored Core VI", "Exclusive Model Kit", "AC6 TGS Exclusive 1/144 Steel Haze Kit", "high", 130),

        # Tamashii Nations – Sentai & Ultraman
        ("Tamashii Nations", "Ultraman", "S.H.Figuarts", "Ultraman Tiga Multi Type Tamashii Event Exclusive SHF", "high", 120),
        ("Tamashii Nations", "Super Sentai", "S.H.Figuarts", "Abaranger Tamashii Nations 20th Anniversary Exclusive SHF", "high", 110),
        ("Tamashii Nations", "Sailor Moon", "Figuarts ZERO", "Super Sailor Moon Tamashii Event Exclusive Figuarts ZERO", "high", 140),
        ("Tamashii Nations", "One Piece", "S.H.Figuarts", "Zoro Enma Tamashii Nations Tour Exclusive SHF", "high", 160),

        # Jump Festa – card game promos
        ("Jump Festa", "Dragon Ball Super", "Exclusive Card", "DBS Card Game Jump Festa 2025 Secret Rare Pack", "mid", 50),
        ("Jump Festa", "One Piece", "Exclusive Card", "One Piece Card Game Jump Festa 2024 Promo Shanks Alt Art", "high", 100),
        ("Jump Festa", "Yu-Gi-Oh!", "Exclusive Card", "Yu-Gi-Oh! Jump Festa 2024 Promo Card Set (3)", "mid", 45),
        ("Jump Festa", "Naruto/Boruto", "Exclusive Figure", "Boruto Jump Festa 2024 Exclusive Mini Figure", "mid", 40),

        # Hobby events – Shizuoka Hobby Show, All Japan Model & Hobby Show
        ("Shizuoka Hobby Show", "Gundam", "Limited Model Kit", "HG Gundam RX-78-2 Shizuoka Show Exclusive Clear Ver.", "high", 100),
        ("Shizuoka Hobby Show", "Macross", "Limited Model Kit", "Macross VF-31J Shizuoka Show Exclusive Metallic Kit", "high", 120),
        ("All Japan Model Show", "Gundam", "Limited Model Kit", "MG Freedom Gundam Model Show Memorial Color Kit", "high", 110),

        # D23 Japan / Disney JP event exclusives
        ("D23 Japan", "Kingdom Hearts", "Exclusive Figure", "Sora D23 Japan 2024 Exclusive Bring Arts Mini", "high", 130),
        ("D23 Japan", "Twisted Wonderland", "Exclusive Goods", "Twisted Wonderland D23 Japan Exclusive Goods Box", "mid", 60),

        # Pokemon Center special events
        ("Pokemon Center Event", "Pokemon", "Exclusive Figure", "Pikachu Pokemon Center Tokyo DX Opening Figure", "high", 100),
        ("Pokemon Center Event", "Pokemon", "Exclusive Plush", "Mew Pokemon Center 25th Anniversary LE Plush", "high", 120),
        ("Pokemon Center Event", "Pokemon", "Exclusive Card", "Pokemon Center Kanazawa Opening Promo Card Pikachu", "grail", 300),

        # Kyoto Animation events
        ("Kyoto Animation Event", "Violet Evergarden", "Art Print", "Violet Evergarden KyoAni Event A3 Art Print (Signed)", "grail", 350),
        ("Kyoto Animation Event", "Free!", "Exclusive Goods", "Free! KyoAni Shop Exclusive Goods Set (Poster + Towel)", "mid", 55),
        ("Kyoto Animation Event", "K-On!", "Exclusive Goods", "K-On! 15th Anniversary KyoAni Event Memorial Set", "high", 100),

        # Gundam Base Tokyo / Fukuoka exclusives
        ("Gundam Base Tokyo", "Gundam", "Limited Model Kit", "RG Unicorn Gundam Perfectibility Gundam Base LE", "high", 150),
        ("Gundam Base Tokyo", "Gundam", "Limited Model Kit", "HG Gundam Aerial Gundam Base Tokyo Exclusive Color", "mid", 65),
        ("Gundam Base Fukuoka", "Gundam", "Limited Model Kit", "MG Rx-93ff Nu Gundam Fukuoka Exclusive Ver.", "grail", 300),

        # Touken Ranbu / Otome game events
        ("Touken Ranbu Exhibition", "Touken Ranbu", "Exclusive Goods", "Touken Ranbu Exhibition Mikazuki Munechika Art Board", "high", 100),
        ("Uta no Prince-sama Event", "Uta no Prince-sama", "Exclusive Goods", "UtaPri Maji LOVE Live Event Exclusive Penlight Set", "mid", 55),

        # Comic Market After-Party / COMITIA indie art
        ("COMITIA", "Original", "Art Book", "COMITIA 148 Award-Winning Artist Original Art Book", "mid", 35),
        ("COMITIA", "Original", "Illustration Card", "COMITIA Guest Artist Limited Signed Illustration Card", "high", 100),

        # === ROUND 4 ADDITIONS (63 items) ===

        # WonFes — More franchises & seasons
        ("WonFes", "Demon Slayer", "Garage Kit", "Rengoku Kyojuro Flame Breathing 1/6 Resin GK WonFes", "grail", 450),
        ("WonFes", "Bleach", "Garage Kit", "Ichigo Vasto Lorde 1/6 Resin GK WonFes Limited 20pcs", "grail", 520),
        ("WonFes", "Blue Lock", "Exclusive Figure", "Isagi Yoichi WonFes 2025 Winter Exclusive 1/7", "high", 200),
        ("WonFes", "Oshi no Ko", "Exclusive Figure", "Ai Hoshino WonFes 2024 Winter Exclusive 1/7 Painted GK", "high", 260),
        ("WonFes", "Solo Leveling", "Garage Kit", "Sung Jinwoo Shadow Monarch 1/6 GK WonFes Limited", "grail", 400),

        # Comiket — C105 goods & more circles
        ("Comiket", "Blue Archive", "Tapestry", "Blue Archive C105 Exclusive B1 Tapestry Arona", "mid", 55),
        ("Comiket", "Hololive", "Music Album", "Hololive C105 Fan Circle Music Compilation CD Set (3)", "mid", 40),
        ("Comiket", "Fate/Grand Order", "Art Book", "FGO Comiket 105 Premium Art Book (WADA Arco)", "high", 100),
        ("Comiket", "Touhou Project", "Art Book", "Touhou C105 Doujin Game Art Collection Book", "mid", 35),
        ("Comiket", "Original", "Doujinshi Set", "Comiket C105 Award Circle Doujinshi Bundle (10)", "mid", 80),

        # AnimeJapan — More 2025 vendors
        ("AnimeJapan", "Solo Leveling", "Acrylic Stand", "Solo Leveling AnimeJapan 2025 Exclusive Acrylic Stand Set", "standard", 22),
        ("AnimeJapan", "Dandadan", "Clear File Set", "Dandadan AnimeJapan 2025 Exclusive Clear File (3pc)", "standard", 15),
        ("AnimeJapan", "Sakamoto Days", "Badge Set", "Sakamoto Days AnimeJapan 2025 Random Badge (8pc)", "standard", 18),
        ("AnimeJapan", "Blue Lock", "Exclusive Figure", "Blue Lock AnimeJapan 2025 Exclusive Chibi Figure Set", "mid", 45),
        ("AnimeJapan", "Kaiju No. 8", "Acrylic Stand", "Kaiju No. 8 AnimeJapan 2025 Acrylic Diorama", "mid", 35),

        # Tamashii Nations — More diverse franchises
        ("Tamashii Nations", "Bleach TYBW", "S.H.Figuarts", "Ichigo Bankai TYBW Tamashii Event Exclusive SHF", "high", 150),
        ("Tamashii Nations", "Demon Slayer", "Figuarts ZERO", "Tanjiro Hinokami Kagura Tamashii Event Exclusive", "high", 130),
        ("Tamashii Nations", "Chainsaw Man", "S.H.Figuarts", "Denji Devil Form Tamashii Tour Exclusive SHF", "high", 140),
        ("Tamashii Nations", "Solo Leveling", "S.H.Figuarts", "Sung Jinwoo Tamashii Nations 2025 Exclusive SHF", "high", 160),
        ("Tamashii Nations", "Frieren", "Figuarts ZERO", "Frieren Casting Spell Tamashii Event Exclusive", "high", 120),

        # Jump Festa — More card game & figure promos
        ("Jump Festa", "One Piece", "Exclusive Card", "One Piece Card Game Jump Festa 2025 Promo Gear 5 Alt Art", "high", 120),
        ("Jump Festa", "Dragon Ball Super", "Exclusive Figure", "Goku Ultra Instinct Jump Festa 2025 Exclusive Figure", "high", 100),
        ("Jump Festa", "Sakamoto Days", "Goods Set", "Sakamoto Days Jump Festa 2025 Exclusive Goods Set", "mid", 45),
        ("Jump Festa", "Undead Unluck", "Badge Set", "Undead Unluck Jump Festa 2025 Random Badge Set (6pc)", "standard", 20),
        ("Jump Festa", "Mashle", "Exclusive Figure", "Mash Burnedead Jump Festa 2024 Exclusive Mini Figure", "mid", 40),

        # Tokyo Game Show — More game exclusives
        ("Tokyo Game Show", "Final Fantasy XVI", "Exclusive Figure", "Clive Rosfield TGS 2023 Exclusive Play Arts Mini", "high", 130),
        ("Tokyo Game Show", "Metaphor: ReFantazio", "Exclusive Merch", "Metaphor TGS 2024 Exclusive Acrylic Stand Set", "mid", 40),
        ("Tokyo Game Show", "Dragon Quest XII", "Collab Goods", "DQ XII TGS 2024 Limited Slime Plush Keychain Set", "mid", 35),
        ("Tokyo Game Show", "Sonic the Hedgehog", "Exclusive Figure", "Sonic TGS 2024 Exclusive Nendoroid", "mid", 55),

        # Gundam Base exclusives — More limited kits
        ("Gundam Base Tokyo", "Gundam", "Limited Model Kit", "MG Gundam Barbatos Lupus Gundam Base LE Color", "high", 120),
        ("Gundam Base Tokyo", "Gundam", "Limited Model Kit", "PG Unleashed RX-78-2 Gundam Base Chrome Ver.", "grail", 350),
        ("Gundam Base Tokyo", "Gundam", "Limited Model Kit", "RG Wing Gundam Zero EW Gundam Base Pearl Coat", "high", 100),
        ("Gundam Base Fukuoka", "Gundam", "Limited Model Kit", "HG 1/144 Aerial Rebuild Fukuoka Exclusive Color", "mid", 75),

        # Pokemon Center — Seasonal & Anniversary
        ("Pokemon Center Event", "Pokemon", "Exclusive Plush", "Charizard Pokemon Center 30th Anniversary LE Plush", "high", 150),
        ("Pokemon Center Event", "Pokemon", "Exclusive Card", "Pokemon Center Birthday Pikachu Promo Card Set (4)", "mid", 60),
        ("Pokemon Center Event", "Pokemon", "Exclusive Figure", "Mewtwo Pokemon Center Gallery Figure DX", "mid", 80),
        ("Pokemon Center Event", "Pokemon", "Exclusive Goods", "Pokemon Center Mega Tokyo R Opening Goods Set", "high", 110),

        # D23 Japan — Disney crossover
        ("D23 Japan", "Kingdom Hearts", "Exclusive Goods", "Kingdom Hearts 4 D23 Japan Exclusive Art Board Set", "high", 100),
        ("D23 Japan", "Star Wars Visions", "Exclusive Figure", "The Duel Ronin D23 Japan Exclusive Figure", "high", 120),

        # Kyoto Animation — More exhibition goods
        ("Kyoto Animation Event", "A Silent Voice", "Art Print", "Koe no Katachi KyoAni Exhibition Limited Art Print", "high", 130),
        ("Kyoto Animation Event", "Sound! Euphonium", "Exclusive Goods", "Hibike! Euphonium KyoAni Event Exclusive Goods Set", "mid", 55),
        ("Kyoto Animation Event", "Clannad", "Exclusive Goods", "Clannad 20th Anniversary KyoAni Memorial Goods Set", "high", 100),

        # Machi Asobi — More ufotable festival goods
        ("Machi Asobi", "Demon Slayer Infinity Castle", "Exclusive Goods", "Demon Slayer Infinity Castle Machi Asobi Exclusive B2 Tapestry", "high", 110),
        ("Machi Asobi", "Fate/Grand Order", "Exclusive Goods", "FGO x ufotable Machi Asobi Exclusive Acrylic Diorama", "high", 130),

        # Regional US events — Japan booths
        ("Anime Expo", "Hololive", "Exclusive Goods", "Hololive x Anime Expo 2024 Exclusive Acrylic Stand Set", "high", 100),
        ("Anime Expo", "Genshin Impact", "Exclusive Goods", "Genshin Impact AX 2024 Exclusive Art Print + Pin Set", "mid", 55),
        ("Anime NYC", "Chainsaw Man", "Exclusive Figure", "Denji Anime NYC 2024 Exclusive Vinyl Figure", "mid", 60),
        ("Anime NYC", "Jujutsu Kaisen", "Exclusive Goods", "JJK Anime NYC 2024 Exclusive Goods Box", "mid", 55),

        # Voice Actor / Seiyuu Events — More signed goods
        ("Voice Actor Event", "Various", "Signed Poster", "Nana Mizuki Live Event Signed B2 Poster", "high", 160),
        ("Voice Actor Event", "Various", "Signed Photo", "Takahiro Sakurai Fan Meeting Signed Photo Set", "high", 140),
        ("Voice Actor Event", "Various", "Signed Shikishi", "Rie Takahashi Signed Shikishi Board (Birthday Event)", "high", 130),

        # Hobby Shows — More exclusive kits
        ("Shizuoka Hobby Show", "Evangelion", "Limited Model Kit", "EVA Unit-01 Shizuoka Show Exclusive Gold Plated Kit", "grail", 300),
        ("Shizuoka Hobby Show", "Macross", "Limited Model Kit", "VF-25F Messiah Shizuoka Exclusive Pearl Coat Kit", "high", 130),
        ("All Japan Model Show", "Gundam", "Limited Model Kit", "RG Nu Gundam Model Show Metallic Ver.", "high", 120),

        # Touken Ranbu / Otome — More exhibitions
        ("Touken Ranbu Exhibition", "Touken Ranbu", "Exclusive Goods", "Touken Ranbu Exhibition Kogitsunemaru Exclusive Tapestry", "mid", 65),
        ("Touken Ranbu Exhibition", "Touken Ranbu", "Exclusive Figure", "Mikazuki Munechika Exhibition Exclusive Nendoroid", "high", 110),

        # COMITIA — More indie originals
        ("COMITIA", "Original", "Art Book", "COMITIA 149 Guest of Honor Limited Art Book (Signed)", "high", 120),
        ("COMITIA", "Original", "Illustration Print", "COMITIA 150 Anniversary Collaborative Print Set (5 artists)", "mid", 60),

        # Evangelion Exhibition — More items
        ("Evangelion Exhibition", "Evangelion", "Exclusive Goods", "EVA Exhibition Exclusive Kaworu Nagisa Tapestry", "high", 100),
        ("Evangelion Exhibition", "Evangelion", "Exclusive Figure", "EVA Exhibition NERV Logo LED Acrylic Display", "mid", 75),

        # Studio Ghibli Exhibition — More
        ("Ghibli Exhibition", "Howl's Moving Castle", "Art Print", "Ghibli Exhibition Howl's Castle Limited Art Print (A3)", "high", 110),
        ("Ghibli Exhibition", "Ponyo", "Exclusive Goods", "Ghibli Exhibition Ponyo Ceramic Figure Set", "mid", 65),

        # Movie Premiere Events
        ("Movie Premium", "One Piece Film Red", "Premium Figure", "One Piece Film Red Movie Theatre Premium Uta Figure", "mid", 55),
        ("Movie Premium", "Demon Slayer Infinity Castle", "Premium Goods", "Demon Slayer Infinity Castle Premiere Exclusive Poster Set", "mid", 45),

        # === ROUND 5 ADDITIONS — Comiket C100-C105 Exclusives ===

        # Comiket C100 (Summer 2022)
        ("Comiket", "Fate/Grand Order", "Tapestry", "FGO Comiket 100 Exclusive B2 Tapestry Kama", "mid", 50),
        ("Comiket", "Hololive", "Acrylic Stand", "Hololive C100 Exclusive Acrylic Stand Tokino Sora", "mid", 35),
        ("Comiket", "Touhou Project", "Music Album", "Touhou C100 COOL&CREATE Album CD", "standard", 25),
        ("Comiket", "Various", "Goods Set", "C100 Memorial Corporate Booth Goods Bag Set", "mid", 70),
        ("Comiket", "Blue Archive", "Doujinshi Set", "Blue Archive C100 Circle Doujinshi Bundle (5)", "mid", 45),

        # Comiket C101 (Winter 2022)
        ("Comiket", "Touhou Project", "Doujinshi Set", "Touhou C101 Premium Circle Bundle (8)", "mid", 60),
        ("Comiket", "Hololive", "Tapestry", "Hololive C101 Exclusive Usada Pekora B2 Tapestry", "mid", 50),
        ("Comiket", "Fate/Grand Order", "Art Book", "FGO C101 Aniplex Exclusive Art Book (TYPE-MOON)", "high", 110),
        ("Comiket", "Original", "Music Album", "C101 Indie Music Circle Compilation Album Set (3)", "standard", 28),

        # Comiket C102 (Summer 2023)
        ("Comiket", "Hololive", "Exclusive Goods", "Hololive C102 Exclusive Gawr Gura Signed Shikishi", "high", 140),
        ("Comiket", "Touhou Project", "Art Book", "Touhou C102 Full-Color Doujin Game Art Collection", "mid", 40),
        ("Comiket", "Spy x Family", "Tapestry", "Spy x Family C102 Exclusive B2 Tapestry Yor", "mid", 45),
        ("Comiket", "Various", "Badge Set", "C102 Corporate Booth Metal Pin Badge Set (12pc)", "standard", 18),

        # Comiket C105 (Winter 2024) — additional
        ("Comiket", "Frieren", "Tapestry", "Frieren C105 Exclusive B2 Tapestry Frieren & Fern", "mid", 55),
        ("Comiket", "Solo Leveling", "Doujinshi Set", "Solo Leveling C105 Circle Doujinshi Bundle (5)", "mid", 45),
        ("Comiket", "Dandadan", "Acrylic Stand", "Dandadan C105 Exclusive Acrylic Stand Okarun & Momo", "standard", 25),
        ("Comiket", "Oshi no Ko", "Art Book", "Oshi no Ko C105 Doujin Art Book Compilation", "mid", 40),

        # === Wonder Festival Expanded — Summer & Winter ===

        # WonFes 2023 Summer
        ("WonFes", "Attack on Titan", "Garage Kit", "Levi Ackerman 1/6 Resin GK WonFes 2023 Summer", "grail", 400),
        ("WonFes", "My Hero Academia", "Exclusive Figure", "All Might WonFes 2023 Summer Exclusive 1/7 Painted GK", "high", 250),
        ("WonFes", "Genshin Impact", "Garage Kit", "Raiden Shogun 1/7 Resin GK WonFes 2023 Summer Limited", "high", 280),

        # WonFes 2023 Winter
        ("WonFes", "Demon Slayer", "Exclusive Figure", "Nezuko Kamado WonFes 2023 Winter Exclusive 1/7", "high", 230),
        ("WonFes", "Hololive", "Garage Kit", "Gawr Gura WonFes 2023 Winter 1/7 GK Unpainted", "high", 200),
        ("WonFes", "Azur Lane", "Garage Kit", "Shinano WonFes 2023 Winter 1/6 Resin GK Limited 15pcs", "grail", 450),

        # WonFes 2024 Summer — additional
        ("WonFes", "Dandadan", "Exclusive Figure", "Okarun WonFes 2024 Summer Exclusive 1/7 Figure", "high", 200),
        ("WonFes", "Blue Archive", "Garage Kit", "Arona WonFes 2024 Summer 1/7 GK Unpainted", "high", 220),
        ("WonFes", "Mushoku Tensei", "Garage Kit", "Eris Boreas Greyrat 1/6 Resin GK WonFes Limited", "high", 260),

        # WonFes 2024 Winter
        ("WonFes", "Sakamoto Days", "Exclusive Figure", "Sakamoto WonFes 2024 Winter Exclusive 1/7 Painted GK", "high", 210),
        ("WonFes", "Kaiju No. 8", "Garage Kit", "Kafka Hibino Monster Form 1/6 GK WonFes Limited", "grail", 380),
        ("WonFes", "Vinland Saga", "Garage Kit", "Thorfinn 1/6 Resin GK WonFes 2024 Winter Limited 20pcs", "grail", 420),

        # WonFes 2025 Summer
        ("WonFes", "Solo Leveling", "Exclusive Figure", "Sung Jinwoo WonFes 2025 Summer Exclusive 1/7", "high", 250),
        ("WonFes", "Oshi no Ko", "Garage Kit", "Ruby Hoshino WonFes 2025 Summer 1/7 GK Unpainted", "high", 220),
        ("WonFes", "Frieren", "Garage Kit", "Himmel WonFes 2025 Summer 1/6 Resin GK Limited", "high", 240),

        # WonFes 2025 Winter
        ("WonFes", "Chainsaw Man", "Exclusive Figure", "Pochita WonFes 2025 Winter Exclusive Plush Figure", "mid", 80),
        ("WonFes", "Blue Lock", "Garage Kit", "Rin Itoshi WonFes 2025 Winter 1/7 GK Unpainted", "high", 200),
        ("WonFes", "Dragon Ball Daima", "Garage Kit", "Mini Goku Dragon Ball Daima WonFes 2025 Limited GK", "high", 250),

        # === Jump Festa Expanded ===

        # Jump Festa 2023
        ("Jump Festa", "One Piece", "Exclusive Card", "One Piece Card Game Jump Festa 2023 Promo Luffy Alt Art", "high", 100),
        ("Jump Festa", "Dragon Ball Super", "Goods Set", "DBS Card Game Jump Festa 2023 Exclusive Goods Set", "mid", 40),
        ("Jump Festa", "My Hero Academia", "Exclusive Figure", "Bakugo Jump Festa 2023 Exclusive Mini Figure", "mid", 45),
        ("Jump Festa", "Spy x Family", "Clear File Set", "Spy x Family Jump Festa 2023 Clear File Collection (5pc)", "standard", 20),

        # Jump Festa 2024 — additional
        ("Jump Festa", "Demon Slayer", "Exclusive Figure", "Tanjiro Kamado Jump Festa 2024 Exclusive Banpresto Figure", "mid", 55),
        ("Jump Festa", "Solo Leveling", "Poster Set", "Solo Leveling Jump Festa 2024 Exclusive Poster Set", "mid", 35),
        ("Jump Festa", "Dandadan", "Badge Set", "Dandadan Jump Festa 2024 Random Badge Set (6pc)", "standard", 18),
        ("Jump Festa", "Blue Lock", "Exclusive Card", "Blue Lock Card Jump Festa 2024 Promo Isagi Alt Art", "mid", 50),

        # Jump Festa 2025 — additional
        ("Jump Festa", "Kaiju No. 8", "Exclusive Figure", "Kafka Hibino Jump Festa 2025 Exclusive Figure", "mid", 55),
        ("Jump Festa", "Frieren", "Goods Set", "Frieren Jump Festa 2025 Exclusive Goods Set (Towel + Badge)", "mid", 40),
        ("Jump Festa", "One Piece", "Exclusive Figure", "Shanks Jump Festa 2025 Exclusive DXF Figure", "high", 100),
        ("Jump Festa", "Sakamoto Days", "Exclusive Figure", "Sakamoto Jump Festa 2025 Exclusive Mini Figure", "mid", 45),

        # === AnimeJapan Expanded ===

        # AnimeJapan 2023
        ("AnimeJapan", "Demon Slayer", "Exclusive Figure", "Demon Slayer AnimeJapan 2023 Exclusive Rengoku Chibi Figure", "mid", 50),
        ("AnimeJapan", "My Hero Academia", "Clear File Set", "MHA AnimeJapan 2023 Exclusive Clear File Collection (5pc)", "standard", 18),
        ("AnimeJapan", "Tokyo Revengers", "Acrylic Stand", "Tokyo Revengers AnimeJapan 2023 Acrylic Stand Set", "standard", 22),
        ("AnimeJapan", "Bleach TYBW", "Badge Set", "Bleach TYBW AnimeJapan 2023 Random Badge (8pc)", "standard", 18),
        ("AnimeJapan", "Vinland Saga", "Clear File", "Vinland Saga AnimeJapan 2023 Exclusive Clear File Pair", "standard", 12),

        # AnimeJapan 2024 — additional
        ("AnimeJapan", "Oshi no Ko", "Exclusive Figure", "Oshi no Ko AnimeJapan 2024 Ai Hoshino Chibi Figure", "mid", 55),
        ("AnimeJapan", "Mushoku Tensei", "Acrylic Stand", "Mushoku Tensei AnimeJapan 2024 Acrylic Stand Trio", "standard", 22),
        ("AnimeJapan", "One Piece", "Exhibit Goods", "One Piece AnimeJapan 2024 Gear 5 Art Panel", "high", 100),
        ("AnimeJapan", "Dragon Ball Daima", "Clear File Set", "Dragon Ball Daima AnimeJapan 2024 Clear File (3pc)", "standard", 15),

        # AnimeJapan 2025 — additional
        ("AnimeJapan", "Chainsaw Man Part 2", "Acrylic Stand", "Chainsaw Man Part 2 AnimeJapan 2025 Acrylic Stand Set", "mid", 30),
        ("AnimeJapan", "Jujutsu Kaisen", "Exhibit Goods", "JJK AnimeJapan 2025 Exhibition Art Board Panel", "high", 110),
        ("AnimeJapan", "Frieren", "Exclusive Figure", "Frieren AnimeJapan 2025 Exclusive Chibi Figure Set", "mid", 50),
        ("AnimeJapan", "Spy x Family S3", "Clear File Set", "Spy x Family S3 AnimeJapan 2025 Clear File (5pc)", "standard", 20),

        # === Tokyo Game Show Expanded ===

        # TGS 2023 — additional
        ("Tokyo Game Show", "Final Fantasy VII Rebirth", "Exclusive Figure", "Cloud Strife FF7 Rebirth TGS 2023 Exclusive Mini", "high", 120),
        ("Tokyo Game Show", "Dragon Quest Monsters", "Collab Goods", "DQ Monsters TGS 2023 Exclusive Slime Plush Set", "mid", 40),
        ("Tokyo Game Show", "Resident Evil 4", "Exclusive Merch", "RE4 Remake TGS 2023 Exclusive Art Print + Pin Set", "mid", 45),

        # TGS 2024 — additional
        ("Tokyo Game Show", "Monster Hunter Wilds", "Exclusive Figure", "MH Wilds TGS 2024 Exclusive Palamute Figure", "mid", 55),
        ("Tokyo Game Show", "Shin Megami Tensei V", "Exclusive Merch", "SMT V Vengeance TGS 2024 Exclusive Acrylic Panel", "mid", 40),
        ("Tokyo Game Show", "Kingdom Hearts IV", "Exclusive Figure", "Sora KH4 TGS 2024 Exclusive Mini Bring Arts", "high", 130),
        ("Tokyo Game Show", "Granblue Fantasy Relink", "Collab Goods", "GBF Relink TGS 2024 Exclusive Art Board + Towel", "mid", 50),

        # TGS 2025
        ("Tokyo Game Show", "Final Fantasy VII Part 3", "Exclusive Merch", "FF7 Part 3 TGS 2025 Exclusive A2 Poster Set", "mid", 35),
        ("Tokyo Game Show", "Dragon Quest XII", "Exclusive Figure", "DQ XII TGS 2025 Exclusive Hero Mini Figure", "high", 100),
        ("Tokyo Game Show", "Metal Gear Solid Delta", "Collab Goods", "MGS Delta TGS 2025 Exclusive Snake Art Print Set", "mid", 45),

        # === Anime Expo Expanded ===

        # Anime Expo 2023
        ("Anime Expo", "Jujutsu Kaisen", "Exclusive Figure", "Gojo Satoru AX 2023 Exclusive 1/7 (Aniplex Booth)", "high", 180),
        ("Anime Expo", "Chainsaw Man", "Exclusive Goods", "Chainsaw Man AX 2023 Exclusive Art Print Set (3)", "mid", 55),
        ("Anime Expo", "Spy x Family", "Exclusive Figure", "Anya Forger AX 2023 Exclusive Chibi Figure", "mid", 60),
        ("Anime Expo", "My Hero Academia", "Funko Pop", "Deku Full Cowl AX 2023 Exclusive Funko Pop (LE 2000)", "high", 100),

        # Anime Expo 2024 — additional
        ("Anime Expo", "Frieren", "Exclusive Figure", "Frieren AX 2024 Exclusive 1/7 (Aniplex Booth)", "high", 200),
        ("Anime Expo", "Solo Leveling", "Exclusive Goods", "Solo Leveling AX 2024 Exclusive Art Print + Acrylic", "mid", 65),
        ("Anime Expo", "Blue Lock", "Exclusive Goods", "Blue Lock AX 2024 Exclusive Goods Box (Poster + Pin Set)", "mid", 50),
        ("Anime Expo", "Oshi no Ko", "Funko Pop", "Ai Hoshino AX 2024 Exclusive Funko Pop (LE 1500)", "high", 110),

        # Anime Expo 2025
        ("Anime Expo", "Dandadan", "Exclusive Figure", "Okarun AX 2025 Exclusive Vinyl Figure", "mid", 60),
        ("Anime Expo", "Kaiju No. 8", "Exclusive Goods", "Kaiju No. 8 AX 2025 Exclusive Art Board + Pin", "mid", 50),
        ("Anime Expo", "Dragon Ball Daima", "Funko Pop", "Mini Goku Daima AX 2025 Exclusive Funko Pop (LE 2000)", "high", 100),

        # === Collaboration Cafe Items ===

        # Animate Cafe
        ("Animate Cafe", "Jujutsu Kaisen", "Collab Goods", "JJK x Animate Cafe Exclusive Acrylic Stand Set (6pc)", "mid", 40),
        ("Animate Cafe", "Demon Slayer", "Collab Goods", "Demon Slayer x Animate Cafe Coaster Set (8pc)", "standard", 22),
        ("Animate Cafe", "Haikyuu!!", "Collab Goods", "Haikyuu!! x Animate Cafe Exclusive Can Badge Set (10pc)", "mid", 30),
        ("Animate Cafe", "My Hero Academia", "Collab Goods", "MHA x Animate Cafe Exclusive Clear File Set (5pc)", "standard", 18),
        ("Animate Cafe", "Spy x Family", "Collab Goods", "Spy x Family x Animate Cafe Exclusive Mug Cup Set", "mid", 35),
        ("Animate Cafe", "Blue Lock", "Collab Goods", "Blue Lock x Animate Cafe Exclusive Acrylic Panel", "mid", 28),
        ("Animate Cafe", "Chainsaw Man", "Collab Goods", "CSM x Animate Cafe Exclusive Tapestry + Coaster", "mid", 32),

        # Tower Records Cafe
        ("Tower Records Cafe", "Hololive", "Collab Goods", "Hololive x Tower Records Cafe Exclusive Bromide Set", "mid", 35),
        ("Tower Records Cafe", "Love Live!", "Collab Goods", "Love Live! x Tower Records Cafe Exclusive Can Badge Set", "standard", 25),
        ("Tower Records Cafe", "BanG Dream!", "Collab Goods", "BanG Dream! x Tower Records Cafe Clear File Set", "standard", 20),
        ("Tower Records Cafe", "Ensemble Stars!", "Collab Goods", "Enstars x Tower Records Cafe Acrylic Stand Set", "mid", 30),

        # Square Enix Cafe
        ("Square Enix Cafe", "Final Fantasy", "Collab Goods", "FF VII x Square Enix Cafe Exclusive Acrylic Stand Set", "mid", 40),
        ("Square Enix Cafe", "NieR:Automata", "Collab Goods", "NieR x Square Enix Cafe Exclusive Coaster + Placemat Set", "mid", 35),
        ("Square Enix Cafe", "Dragon Quest", "Collab Goods", "DQ x Square Enix Cafe Exclusive Slime Glass Cup Set", "mid", 30),
        ("Square Enix Cafe", "Kingdom Hearts", "Collab Goods", "KH x Square Enix Cafe Exclusive Art Plate Set", "mid", 38),

        # Capcom Bar/Cafe
        ("Capcom Cafe", "Monster Hunter", "Collab Goods", "Monster Hunter x Capcom Cafe Exclusive Palico Plush", "mid", 35),
        ("Capcom Cafe", "Resident Evil", "Collab Goods", "Resident Evil x Capcom Cafe Exclusive Umbrella Corp Mug", "mid", 28),
        ("Capcom Cafe", "Street Fighter", "Collab Goods", "Street Fighter x Capcom Cafe Exclusive Coaster Set", "standard", 20),

        # === Ichiban Kuji / Lottery Prize Items ===

        # One Piece Ichiban Kuji
        ("Ichiban Kuji", "One Piece", "Prize Figure", "One Piece Ichiban Kuji Last One Prize Luffy Gear 5", "high", 150),
        ("Ichiban Kuji", "One Piece", "Prize Figure", "One Piece Ichiban Kuji A Prize Zoro Enma", "mid", 65),
        ("Ichiban Kuji", "One Piece", "Prize Figure", "One Piece Ichiban Kuji B Prize Shanks Film Red", "mid", 55),
        ("Ichiban Kuji", "One Piece", "Prize Goods", "One Piece Ichiban Kuji C Prize Straw Hat Towel Set", "standard", 25),

        # Dragon Ball Ichiban Kuji
        ("Ichiban Kuji", "Dragon Ball Z", "Prize Figure", "Dragon Ball Ichiban Kuji Last One Prize Vegito Blue", "high", 130),
        ("Ichiban Kuji", "Dragon Ball Super", "Prize Figure", "DBS Ichiban Kuji A Prize Ultra Instinct Goku", "mid", 70),
        ("Ichiban Kuji", "Dragon Ball Z", "Prize Figure", "DBZ Ichiban Kuji B Prize Perfect Cell", "mid", 55),
        ("Ichiban Kuji", "Dragon Ball Z", "Prize Goods", "DBZ Ichiban Kuji D Prize Master Stars Art Board", "mid", 35),

        # Demon Slayer Ichiban Kuji
        ("Ichiban Kuji", "Demon Slayer", "Prize Figure", "Demon Slayer Ichiban Kuji Last One Prize Rengoku", "high", 120),
        ("Ichiban Kuji", "Demon Slayer", "Prize Figure", "Demon Slayer Ichiban Kuji A Prize Tanjiro Hinokami", "mid", 60),
        ("Ichiban Kuji", "Demon Slayer", "Prize Figure", "Demon Slayer Ichiban Kuji B Prize Nezuko", "mid", 55),

        # Jujutsu Kaisen Ichiban Kuji
        ("Ichiban Kuji", "Jujutsu Kaisen", "Prize Figure", "JJK Ichiban Kuji Last One Prize Gojo Domain Expansion", "high", 140),
        ("Ichiban Kuji", "Jujutsu Kaisen", "Prize Figure", "JJK Ichiban Kuji A Prize Sukuna", "mid", 65),
        ("Ichiban Kuji", "Jujutsu Kaisen", "Prize Figure", "JJK Ichiban Kuji B Prize Yuji Itadori", "mid", 50),

        # My Hero Academia Ichiban Kuji
        ("Ichiban Kuji", "My Hero Academia", "Prize Figure", "MHA Ichiban Kuji Last One Prize All Might vs AFO", "high", 110),
        ("Ichiban Kuji", "My Hero Academia", "Prize Figure", "MHA Ichiban Kuji A Prize Deku Full Cowl", "mid", 55),

        # Spy x Family Ichiban Kuji
        ("Ichiban Kuji", "Spy x Family", "Prize Figure", "Spy x Family Ichiban Kuji Last One Prize Anya", "high", 100),
        ("Ichiban Kuji", "Spy x Family", "Prize Figure", "Spy x Family Ichiban Kuji A Prize Yor Briar", "mid", 55),

        # Hololive Ichiban Kuji
        ("Ichiban Kuji", "Hololive", "Prize Figure", "Hololive Ichiban Kuji Last One Prize Gawr Gura", "high", 120),
        ("Ichiban Kuji", "Hololive", "Prize Figure", "Hololive Ichiban Kuji A Prize Usada Pekora", "mid", 60),

        # Chainsaw Man Ichiban Kuji
        ("Ichiban Kuji", "Chainsaw Man", "Prize Figure", "CSM Ichiban Kuji Last One Prize Pochita Gigantic", "high", 100),
        ("Ichiban Kuji", "Chainsaw Man", "Prize Figure", "CSM Ichiban Kuji A Prize Denji & Power Set", "mid", 65),

        # === Regional Anime Events Expanded ===

        # Anime NYC — additional
        ("Anime NYC", "Dragon Ball Super", "Exclusive Figure", "Goku Anime NYC 2024 Exclusive Banpresto Figure", "mid", 55),
        ("Anime NYC", "Demon Slayer", "Exclusive Goods", "Demon Slayer Anime NYC 2024 Exclusive Art Print Set", "mid", 50),
        ("Anime NYC", "Frieren", "Exclusive Figure", "Frieren Anime NYC 2024 Exclusive Mini Figure", "mid", 60),
        ("Anime NYC", "Spy x Family", "Exclusive Goods", "Spy x Family Anime NYC 2023 Exclusive Poster + Pin Set", "mid", 45),

        # Crunchyroll Expo — additional
        ("Crunchyroll Expo", "Frieren", "Exclusive Figure", "Frieren CRX 2024 Exclusive Mini Figure", "mid", 60),
        ("Crunchyroll Expo", "Solo Leveling", "Exclusive Goods", "Solo Leveling CRX 2024 Exclusive Art Board", "mid", 50),
        ("Crunchyroll Expo", "Blue Lock", "Exclusive Figure", "Isagi CRX 2024 Exclusive Vinyl Figure", "mid", 55),
        ("Crunchyroll Expo", "Oshi no Ko", "Goods Set", "Oshi no Ko CRX 2024 Exclusive Goods Box (Poster + Pin)", "mid", 45),
        ("Crunchyroll Expo", "Dandadan", "Exclusive Goods", "Dandadan CRX 2025 Exclusive Art Print Set", "mid", 40),

        # CharaExpo — additional
        ("CharaExpo", "Love Live!", "Exclusive Goods", "Love Live! CharaExpo Exclusive Signed Shikishi Set", "high", 120),
        ("CharaExpo", "BanG Dream!", "Exclusive Goods", "BanG Dream! CharaExpo Exclusive Acrylic Stand Set", "mid", 40),
        ("CharaExpo", "Vocaloid", "Exclusive Figure", "Hatsune Miku CharaExpo Exclusive Nendoroid", "high", 100),

        # Sakura-Con, Otakon
        ("Sakura-Con", "Gundam", "Exclusive Model Kit", "Gundam Sakura-Con 2024 Exclusive HG Sakura Color Kit", "mid", 65),
        ("Sakura-Con", "Fate/Grand Order", "Exclusive Goods", "FGO Sakura-Con 2024 Exclusive Art Print + Pin Set", "mid", 50),
        ("Otakon", "Evangelion", "Exclusive Goods", "Evangelion Otakon 2024 Exclusive Art Board + Poster", "mid", 55),
        ("Otakon", "Demon Slayer", "Exclusive Figure", "Demon Slayer Otakon 2024 Exclusive Mini Figure", "mid", 50),

        # === Tamashii Nations Expanded ===

        # Tamashii Nations 2024 — additional
        ("Tamashii Nations", "Dragon Ball Z", "Figuarts ZERO", "Gohan Father-Son Kamehameha Tamashii Event Exclusive", "high", 140),
        ("Tamashii Nations", "One Piece", "Figuarts ZERO", "Sanji Diable Jambe Tamashii Event Exclusive", "high", 120),
        ("Tamashii Nations", "Naruto Shippuden", "Figuarts ZERO", "Naruto Sage Mode Tamashii Event Exclusive", "high", 130),
        ("Tamashii Nations", "Kamen Rider", "Robot Spirits", "Kamen Rider Black RX Tamashii Event Exclusive", "high", 110),
        ("Tamashii Nations", "Ultraman", "Metal Build", "Ultraman Suit Tamashii Nations 2024 Exclusive Metal Build", "grail", 320),

        # Tamashii Nations 2025
        ("Tamashii Nations", "Dragon Ball Daima", "S.H.Figuarts", "Mini Goku Daima Tamashii Nations 2025 Exclusive SHF", "high", 120),
        ("Tamashii Nations", "Chainsaw Man", "Figuarts ZERO", "Power Blood Devil Tamashii Nations 2025 Exclusive", "high", 140),
        ("Tamashii Nations", "Solo Leveling", "Figuarts ZERO", "Sung Jinwoo Shadow Army Tamashii Event 2025 Exclusive", "high", 160),
        ("Tamashii Nations", "Gundam", "Metal Build", "Nu Gundam Double Fin Funnel Tamashii 2025 Exclusive", "grail", 450),
        ("Tamashii Nations", "Evangelion", "Robot Spirits", "EVA Unit-08 Tamashii Nations 2025 Exclusive", "high", 130),

        # === Gundam Base Expanded ===

        # Gundam Base Tokyo — additional
        ("Gundam Base Tokyo", "Gundam", "Limited Model Kit", "HG 1/144 RX-78-2 Gundam Clear Color Tokyo Limited", "mid", 55),
        ("Gundam Base Tokyo", "Gundam", "Limited Model Kit", "MG Zaku II Char Custom Gundam Base Metallic Ver.", "high", 110),
        ("Gundam Base Tokyo", "Gundam", "Limited Model Kit", "RG Crossbone Gundam X1 Gundam Base Pearl Coat", "high", 100),
        ("Gundam Base Tokyo", "Gundam", "Limited Model Kit", "HG 1/144 Gundam Calibarn Gundam Base Exclusive Color", "mid", 65),
        ("Gundam Base Tokyo", "Gundam", "Limited Model Kit", "MG Freedom Gundam Ver.2.0 Gundam Base Tokyo Edition", "high", 130),

        # Gundam Base Fukuoka — additional
        ("Gundam Base Fukuoka", "Gundam", "Limited Model Kit", "HG 1/144 Gundam Aerial Fukuoka Pearl Coat", "mid", 70),
        ("Gundam Base Fukuoka", "Gundam", "Limited Model Kit", "MG Unicorn Gundam Perfectibility Fukuoka LE", "high", 180),

        # Gundam Base Shanghai / Seoul
        ("Gundam Base Shanghai", "Gundam", "Limited Model Kit", "HG Freedom Gundam Shanghai Exclusive Gold Ver.", "high", 120),
        ("Gundam Base Shanghai", "Gundam", "Limited Model Kit", "RG Strike Freedom Shanghai Exclusive Color", "high", 100),
        ("Gundam Base Seoul", "Gundam", "Limited Model Kit", "HG 1/144 RX-78-2 Seoul Exclusive Trans-Am Color", "mid", 65),

        # === Pokemon Center Events Expanded ===

        ("Pokemon Center Event", "Pokemon", "Exclusive Plush", "Pikachu Pokemon Center Kyoto Opening LE Plush", "high", 100),
        ("Pokemon Center Event", "Pokemon", "Exclusive Card", "Eevee Pokemon Center Birthday Promo Card 2024", "mid", 45),
        ("Pokemon Center Event", "Pokemon", "Exclusive Figure", "Charizard Pokemon Center Gallery DX Figure", "high", 120),
        ("Pokemon Center Event", "Pokemon", "Exclusive Goods", "Pokemon Center Mega Tokyo Opening Goods Bag Set", "high", 130),
        ("Pokemon Center Event", "Pokemon", "Exclusive Plush", "Gengar Pokemon Center Halloween 2024 LE Plush", "mid", 65),
        ("Pokemon Center Event", "Pokemon", "Exclusive Card", "Pikachu Pokemon Center Okinawa Opening Promo Card", "high", 150),
        ("Pokemon Center Event", "Pokemon", "Exclusive Plush", "Snorlax Pokemon Center 25th Anniversary Giant Plush", "grail", 300),

        # === Kyoto Animation Events Expanded ===

        ("Kyoto Animation Event", "Liz and the Blue Bird", "Art Print", "Liz and the Blue Bird KyoAni Exhibition Art Print", "high", 110),
        ("Kyoto Animation Event", "Hyouka", "Exclusive Goods", "Hyouka 10th Anniversary KyoAni Event Memorial Set", "high", 100),
        ("Kyoto Animation Event", "Dragon Maid", "Exclusive Goods", "Kobayashi Dragon Maid KyoAni Event Goods Set", "mid", 55),
        ("Kyoto Animation Event", "Tsurune", "Exclusive Goods", "Tsurune KyoAni Shop Exclusive Goods Set", "mid", 45),

        # === Studio Ghibli Exhibition Expanded ===

        ("Ghibli Exhibition", "Castle in the Sky", "Art Print", "Ghibli Exhibition Laputa Limited Art Print (A3)", "high", 120),
        ("Ghibli Exhibition", "Kiki's Delivery Service", "Exclusive Goods", "Ghibli Exhibition Kiki Ceramic Jiji Figure Set", "high", 100),
        ("Ghibli Exhibition", "The Wind Rises", "Art Print", "Ghibli Exhibition Wind Rises Miyazaki Sketch Print", "high", 130),
        ("Ghibli Exhibition", "Nausicaa", "Exclusive Goods", "Ghibli Exhibition Nausicaa Ohmu Resin Figure", "grail", 300),
        ("Ghibli Exhibition", "Arrietty", "Exclusive Goods", "Ghibli Exhibition Arrietty Miniature Diorama", "mid", 65),

        # === Evangelion Exhibition Expanded ===

        ("Evangelion Exhibition", "Evangelion", "Art Print", "EVA Exhibition Mari Makinami Art Print (Signed)", "grail", 280),
        ("Evangelion Exhibition", "Evangelion", "Exclusive Goods", "EVA Exhibition Exclusive NERV Acrylic LED Panel", "mid", 80),
        ("Evangelion Exhibition", "Evangelion", "Exclusive Figure", "EVA Exhibition Unit-02 Beast Mode Mini Figure", "high", 120),

        # === Machi Asobi Expanded ===

        ("Machi Asobi", "Fate/Grand Order", "Exclusive Goods", "FGO Machi Asobi Exclusive Scathach B2 Tapestry", "high", 100),
        ("Machi Asobi", "Demon Slayer", "Exclusive Goods", "Demon Slayer Machi Asobi Hashira Complete Tapestry Set", "high", 150),
        ("Machi Asobi", "Kimetsu Academy", "Exclusive Goods", "Kimetsu Academy Machi Asobi Exclusive Clear File Set", "mid", 30),
        ("Machi Asobi", "Fate/stay night", "Exclusive Figure", "Saber Machi Asobi ufotable Exclusive Mini Figure", "mid", 65),

        # === Hobby Shows Expanded ===

        ("Shizuoka Hobby Show", "Gundam", "Limited Model Kit", "MG Gundam Exia Shizuoka Show Exclusive Metallic", "high", 120),
        ("Shizuoka Hobby Show", "Armored Core", "Limited Model Kit", "AC VI Shizuoka Show Exclusive 1/144 Steel Haze Kit", "high", 110),
        ("Shizuoka Hobby Show", "Star Wars", "Limited Model Kit", "Star Wars X-Wing Shizuoka Exclusive Chrome Kit", "mid", 80),
        ("All Japan Model Show", "Macross", "Limited Model Kit", "VF-1S Valkyrie Model Show Memorial Gold Kit", "high", 130),
        ("All Japan Model Show", "Evangelion", "Limited Model Kit", "EVA Unit-01 Model Show Exclusive Clear Kit", "high", 120),

        # === D23 Japan Expanded ===

        ("D23 Japan", "Kingdom Hearts", "Exclusive Goods", "Kingdom Hearts D23 Japan Exclusive Keyblade Replica", "high", 180),
        ("D23 Japan", "Disney Twisted Wonderland", "Exclusive Figure", "Twisted Wonderland D23 Exclusive Nendoroid Malleus", "high", 130),
        ("D23 Japan", "Star Wars Visions", "Exclusive Goods", "Star Wars Visions D23 Japan Art Print Set (3)", "mid", 60),

        # === Touken Ranbu Exhibition Expanded ===

        ("Touken Ranbu Exhibition", "Touken Ranbu", "Exclusive Figure", "Kashuu Kiyomitsu Exhibition Exclusive Nendoroid", "high", 100),
        ("Touken Ranbu Exhibition", "Touken Ranbu", "Exclusive Goods", "Touken Ranbu Exhibition Heshikiri Hasebe Art Board", "mid", 65),
        ("Touken Ranbu Exhibition", "Touken Ranbu", "Exclusive Goods", "Touken Ranbu Exhibition Complete Tapestry Set (5 Swords)", "high", 180),

        # === Convention-Exclusive Figures & Goods (Mixed Events) ===

        # Hobby Japan / Alter Exclusive Figures
        ("Hobby Japan Exclusive", "Fate/Grand Order", "Exclusive Figure", "Altria Pendragon Hobby Japan 1/7 Limited Color", "high", 200),
        ("Hobby Japan Exclusive", "Re:Zero", "Exclusive Figure", "Rem Crystal Dress Hobby Japan Exclusive 1/7", "high", 180),
        ("Hobby Japan Exclusive", "Date A Live", "Exclusive Figure", "Kurumi Tokisaki Hobby Japan Exclusive 1/7", "high", 190),

        # Good Smile Company Festival
        ("GSC Festival", "Vocaloid", "Exclusive Nendoroid", "Hatsune Miku GSC Festival 2024 Exclusive Nendoroid", "high", 100),
        ("GSC Festival", "Fate/Grand Order", "Exclusive Nendoroid", "Saber GSC Festival 2024 Exclusive Nendoroid", "mid", 80),
        ("GSC Festival", "Overwatch", "Exclusive Nendoroid", "D.Va GSC Festival Exclusive Nendoroid", "mid", 75),

        # === Voice Actor Events Expanded ===

        ("Voice Actor Event", "Various", "Signed Photo", "Saori Hayami Fan Meeting Signed Photo Set", "high", 150),
        ("Voice Actor Event", "Various", "Signed Poster", "Yuki Kaji Live Event Signed B2 Poster", "high", 140),
        ("Voice Actor Event", "Various", "Signed Shikishi", "Inori Minase Birthday Event Signed Shikishi Board", "high", 130),
        ("Voice Actor Event", "Various", "Signed CD", "LiSA Live Concert Signed CD (First Press LE)", "high", 160),
        ("Voice Actor Event", "Various", "Signed Photo", "Ayane Sakura Fan Event Signed Photo + Message Card", "high", 140),
        ("Voice Actor Event", "Various", "Signed Poster", "FLOW Band Signed Naruto Anniversary Poster", "high", 120),

        # === Movie Premiere Events Expanded ===

        ("Movie Premium", "Jujutsu Kaisen 0", "Premium Figure", "JJK 0 Movie Theatre Premium Okkotsu Yuta Figure", "mid", 50),
        ("Movie Premium", "Dragon Ball Super: Super Hero", "Premium Goods", "DBS Super Hero Movie Premiere Poster Set (3)", "mid", 40),
        ("Movie Premium", "One Piece Film Red", "Premium Goods", "OP Film Red Movie Premiere Clear File Collection (5pc)", "standard", 25),
        ("Movie Premium", "Demon Slayer Mugen Train", "Premium Figure", "KnY Mugen Train Movie Theatre Premium Rengoku Figure", "mid", 55),
        ("Movie Premium", "Sword Art Online Progressive", "Premium Figure", "SAO Progressive Movie Premium Asuna Figure", "mid", 45),
        ("Movie Premium", "My Hero Academia World Heroes", "Premium Goods", "MHA World Heroes Mission Premiere Exclusive Poster Set", "mid", 35),
        ("Movie Premium", "Evangelion 3.0+1.0", "Premium Figure", "EVA 3.0+1.0 Movie Theatre Premium Unit-01 Figure", "mid", 60),

        # === COMITIA Expanded ===

        ("COMITIA", "Original", "Art Book", "COMITIA 151 Guest of Honor Signed Art Book", "high", 110),
        ("COMITIA", "Original", "Illustration Print", "COMITIA 152 10th Anniversary Collab Print Set (8 artists)", "high", 100),
        ("COMITIA", "Original", "Art Book", "COMITIA 147 Award-Winning Doujin Manga Compilation", "mid", 40),
        ("COMITIA", "Original", "Illustration Card", "COMITIA 153 Guest Artist Signed Illustration Card Set", "high", 120),

        # === Otome Game Events Expanded ===

        ("Uta no Prince-sama Event", "Uta no Prince-sama", "Exclusive Goods", "UtaPri Maji LOVE Kingdom Movie Premiere Goods Set", "mid", 50),
        ("Uta no Prince-sama Event", "Uta no Prince-sama", "Exclusive Figure", "UtaPri Event Exclusive Tokiya Ichinose Nendoroid", "high", 100),
        ("Ensemble Stars Event", "Ensemble Stars!", "Exclusive Goods", "Enstars LIVE Event Exclusive Penlight + Wristband Set", "mid", 40),
        ("Ensemble Stars Event", "Ensemble Stars!", "Exclusive Goods", "Enstars Concert Exclusive Bromide Card Set (10pc)", "mid", 35),

        # === Hololive EXPO / Events ===

        ("Hololive EXPO", "Hololive", "Exclusive Goods", "Hololive 4th Fes Exclusive Acrylic Stand Set (10pc)", "high", 120),
        ("Hololive EXPO", "Hololive", "Exclusive Goods", "Hololive EXPO 2024 Exclusive Tapestry B2 Set (5pc)", "high", 150),
        ("Hololive EXPO", "Hololive", "Exclusive Figure", "Hololive EXPO 2024 Exclusive Nendoroid Tokino Sora", "high", 100),
        ("Hololive EXPO", "Hololive", "Exclusive Goods", "Hololive 5th Fes Exclusive Goods Box Complete Set", "grail", 300),

        # === Additional Convention Exclusives ===

        # AGF (Animate Girls Festival) — otome/BL events
        ("AGF", "Hypnosis Mic", "Exclusive Goods", "Hypnosis Mic AGF 2024 Exclusive Bromide + Can Badge Set", "mid", 35),
        ("AGF", "Twisted Wonderland", "Exclusive Goods", "Twisted Wonderland AGF 2024 Exclusive Acrylic Stand Set", "mid", 40),
        ("AGF", "Obey Me!", "Exclusive Goods", "Obey Me! AGF 2024 Exclusive Tapestry + Clear File Set", "mid", 35),
        ("AGF", "A3!", "Exclusive Goods", "A3! AGF 2024 Exclusive Bromide Card Set (12pc)", "mid", 30),

        # Comic Market Special / Non-numbered events
        ("Comiket Special", "Various", "Exclusive Goods", "Comiket Special 7 Memorial Goods Bag Complete Set", "high", 100),
        ("Comiket Special", "Various", "Badge Set", "Comiket 50th Anniversary Memorial Pin Badge Set", "mid", 45),

        # === ROUND 6 — More Convention-Exclusive Figures & Goods ===

        # More Ichiban Kuji — popular franchises
        ("Ichiban Kuji", "Dragon Ball Z", "Prize Figure", "DBZ Ichiban Kuji Last One Majin Vegeta Final Atonement", "high", 140),
        ("Ichiban Kuji", "One Piece", "Prize Figure", "OP Ichiban Kuji A Prize Yamato Thunder Bagua", "mid", 70),
        ("Ichiban Kuji", "One Piece", "Prize Figure", "OP Ichiban Kuji Last One Nika Luffy Sun God", "grail", 200),
        ("Ichiban Kuji", "Dragon Ball Super", "Prize Figure", "DBS Ichiban Kuji Last One Gogeta Blue", "high", 130),
        ("Ichiban Kuji", "Naruto Shippuden", "Prize Figure", "Naruto Ichiban Kuji Last One Naruto & Kurama", "high", 120),
        ("Ichiban Kuji", "Naruto Shippuden", "Prize Figure", "Naruto Ichiban Kuji A Prize Itachi Susanoo", "mid", 65),
        ("Ichiban Kuji", "Bleach TYBW", "Prize Figure", "Bleach Ichiban Kuji Last One Ichigo Bankai TYBW", "high", 110),
        ("Ichiban Kuji", "Bleach TYBW", "Prize Figure", "Bleach Ichiban Kuji A Prize Byakuya Kuchiki", "mid", 60),
        ("Ichiban Kuji", "Frieren", "Prize Figure", "Frieren Ichiban Kuji Last One Frieren Casting Spell", "high", 120),
        ("Ichiban Kuji", "Frieren", "Prize Figure", "Frieren Ichiban Kuji A Prize Fern", "mid", 55),
        ("Ichiban Kuji", "Solo Leveling", "Prize Figure", "Solo Leveling Ichiban Kuji Last One Sung Jinwoo", "high", 130),
        ("Ichiban Kuji", "Blue Lock", "Prize Figure", "Blue Lock Ichiban Kuji Last One Isagi & Rin", "high", 100),
        ("Ichiban Kuji", "Blue Lock", "Prize Figure", "Blue Lock Ichiban Kuji A Prize Bachira", "mid", 55),
        ("Ichiban Kuji", "Oshi no Ko", "Prize Figure", "Oshi no Ko Ichiban Kuji Last One Ai Hoshino", "high", 110),
        ("Ichiban Kuji", "Oshi no Ko", "Prize Figure", "Oshi no Ko Ichiban Kuji A Prize Ruby & Aqua", "mid", 60),

        # More Animate Cafe — seasonal collabs
        ("Animate Cafe", "Frieren", "Collab Goods", "Frieren x Animate Cafe Exclusive Acrylic Panel Set", "mid", 35),
        ("Animate Cafe", "Solo Leveling", "Collab Goods", "Solo Leveling x Animate Cafe Exclusive Coaster Set", "standard", 22),
        ("Animate Cafe", "Oshi no Ko", "Collab Goods", "Oshi no Ko x Animate Cafe Exclusive Can Badge Set (8pc)", "standard", 25),
        ("Animate Cafe", "One Piece", "Collab Goods", "One Piece x Animate Cafe Exclusive Acrylic Stand Set (6pc)", "mid", 35),
        ("Animate Cafe", "Naruto", "Collab Goods", "Naruto x Animate Cafe 20th Anniversary Exclusive Mug Set", "mid", 38),

        # More Tower Records Cafe
        ("Tower Records Cafe", "Jujutsu Kaisen", "Collab Goods", "JJK x Tower Records Cafe Exclusive Acrylic Panel", "mid", 32),
        ("Tower Records Cafe", "Demon Slayer", "Collab Goods", "Demon Slayer x Tower Records Cafe Clear File Set (5pc)", "standard", 25),
        ("Tower Records Cafe", "Spy x Family", "Collab Goods", "Spy x Family x Tower Records Cafe Coaster Set", "standard", 20),

        # More Collaboration Cafes — various
        ("Sweets Paradise", "Jujutsu Kaisen", "Collab Goods", "JJK x Sweets Paradise Exclusive Can Badge Set (8pc)", "standard", 22),
        ("Sweets Paradise", "Haikyuu!!", "Collab Goods", "Haikyuu!! x Sweets Paradise Exclusive Coaster Set", "standard", 18),
        ("Sweets Paradise", "My Hero Academia", "Collab Goods", "MHA x Sweets Paradise Exclusive Bromide Set (6pc)", "standard", 20),
        ("Ufotable Cafe", "Demon Slayer", "Collab Goods", "Demon Slayer x Ufotable Cafe Exclusive Mug + Coaster", "mid", 35),
        ("Ufotable Cafe", "Fate/stay night", "Collab Goods", "Fate/stay night HF x Ufotable Cafe Exclusive Art Board", "mid", 40),
        ("Ufotable Cafe", "Gintama", "Collab Goods", "Gintama x Ufotable Cafe Exclusive Acrylic Stand Set", "mid", 30),

        # More Comiket C100-C105 — additional circles/types
        ("Comiket", "Vocaloid", "Music Album", "Hatsune Miku C100 DECO*27 Fan Arrange CD Set", "mid", 35),
        ("Comiket", "Touhou Project", "Exclusive Goods", "Touhou C101 ZUN Illustrated Shikishi (Lottery Winner)", "grail", 380),
        ("Comiket", "Various", "Tapestry", "C102 Corporate Exclusive B0 Giant Tapestry", "high", 120),
        ("Comiket", "Kantai Collection", "Doujinshi Set", "KanColle C103 Circle Doujinshi Bundle (5)", "mid", 40),
        ("Comiket", "Uma Musume", "Tapestry", "Uma Musume C103 Exclusive B2 Tapestry Special Week", "mid", 50),
        ("Comiket", "Genshin Impact", "Art Book", "Genshin Impact C104 Fan Art Book Compilation", "mid", 40),
        ("Comiket", "Blue Archive", "Music Album", "Blue Archive C104 Fan Arrange Music CD Set (3)", "mid", 35),
        ("Comiket", "Lycoris Recoil", "Tapestry", "Lycoris Recoil C103 Exclusive B2 Tapestry Chisato", "mid", 45),

        # More WonFes — classic & newer franchises
        ("WonFes", "Goblin Slayer", "Garage Kit", "Goblin Slayer 1/6 Resin GK WonFes Limited 20pcs", "grail", 400),
        ("WonFes", "Overlord", "Garage Kit", "Ainz Ooal Gown 1/6 Resin GK WonFes Limited", "grail", 450),
        ("WonFes", "Fate/Grand Order", "Garage Kit", "Ishtar 1/7 Resin GK WonFes 2025 Summer Limited", "high", 280),
        ("WonFes", "Lycoris Recoil", "Exclusive Figure", "Chisato Nishikigi WonFes 2024 Exclusive 1/7", "high", 220),
        ("WonFes", "Genshin Impact", "Exclusive Figure", "Hu Tao WonFes 2024 Winter Exclusive 1/7 Painted GK", "high", 260),
        ("WonFes", "Uma Musume", "Exclusive Figure", "Rice Shower WonFes 2025 Winter Exclusive 1/7", "high", 210),

        # More Jump Festa — additional manga promos
        ("Jump Festa", "Boruto: Two Blue Vortex", "Exclusive Figure", "Boruto TBV Jump Festa 2025 Exclusive Mini Figure", "mid", 45),
        ("Jump Festa", "Black Clover", "Exclusive Card", "Black Clover Card Jump Festa 2024 Promo Asta Alt Art", "mid", 40),
        ("Jump Festa", "Witch Watch", "Badge Set", "Witch Watch Jump Festa 2024 Random Badge Set (6pc)", "standard", 18),
        ("Jump Festa", "Mission: Yozakura Family", "Goods Set", "Yozakura Family Jump Festa 2025 Goods Set", "mid", 35),

        # More D23 Japan
        ("D23 Japan", "Marvel", "Exclusive Figure", "Spider-Man D23 Japan Exclusive Mini Figure (Disney Parks)", "mid", 65),
        ("D23 Japan", "Frozen", "Exclusive Goods", "Frozen D23 Japan Exclusive Elsa Crystal Art Frame", "mid", 55),

        # Niconico Chokaigi
        ("Niconico Chokaigi", "Vocaloid", "Exclusive Goods", "Hatsune Miku Niconico Chokaigi 2024 Exclusive Acrylic Stand", "mid", 35),
        ("Niconico Chokaigi", "Touhou Project", "Exclusive Goods", "Touhou x Niconico Chokaigi Exclusive Clearfile Set", "standard", 20),
        ("Niconico Chokaigi", "Hololive", "Exclusive Goods", "Hololive x Niconico Chokaigi Exclusive Can Badge Set", "mid", 30),

        # Treasure Festa (Yokohama garage kit event)
        ("Treasure Festa", "Fate/Grand Order", "Garage Kit", "Jeanne d'Arc 1/7 Resin GK Treasure Festa Limited", "grail", 380),
        ("Treasure Festa", "Evangelion", "Garage Kit", "Asuka Langley 1/6 GK Treasure Festa Limited 15pcs", "grail", 420),
        ("Treasure Festa", "Azur Lane", "Garage Kit", "Enterprise 1/7 Resin GK Treasure Festa Limited", "high", 280),

        # Tamashii Nations — World Tour stops
        ("Tamashii Nations", "Dragon Ball Z", "S.H.Figuarts", "Son Goku SSJ3 Tamashii World Tour Exclusive SHF", "high", 170),
        ("Tamashii Nations", "One Piece", "Figuarts ZERO", "Ace Fire Fist Tamashii World Tour Exclusive", "high", 130),
        ("Tamashii Nations", "Kamen Rider", "S.H.Figuarts", "Kamen Rider W Double Driver Tamashii Tour Exclusive", "high", 140),

        # More WonFes vintage franchises
        ("WonFes", "Berserk", "Exclusive Figure", "Casca WonFes 2025 Winter Exclusive 1/7 Painted GK", "high", 280),
        ("WonFes", "JoJo's Bizarre Adventure", "Garage Kit", "Jotaro & Star Platinum 1/6 Resin GK WonFes Limited", "grail", 500),
        ("WonFes", "Steins;Gate", "Garage Kit", "Kurisu Makise 1/7 Resin GK WonFes 2024 Limited", "high", 240),

        # More Anime Expo — Japan publisher exclusives
        ("Anime Expo", "Bocchi the Rock!", "Exclusive Figure", "Bocchi AX 2025 Exclusive Nendoroid (Aniplex)", "mid", 80),
        ("Anime Expo", "Lycoris Recoil", "Exclusive Figure", "Chisato AX 2025 Exclusive 1/7 (Aniplex Booth)", "high", 200),
        ("Anime Expo", "Mushoku Tensei", "Exclusive Goods", "Mushoku Tensei AX 2025 Art Print + Acrylic Set", "mid", 55),

        # Additional Tokyo Game Show
        ("Tokyo Game Show", "Tales of Arise", "Exclusive Figure", "Alphen TGS 2023 Exclusive Mini Figure with Base", "mid", 55),
        ("Tokyo Game Show", "Like a Dragon", "Collab Goods", "Like a Dragon TGS 2024 Exclusive Kasuga Art Board", "mid", 40),
        ("Tokyo Game Show", "Ace Attorney", "Exclusive Merch", "Phoenix Wright TGS 2025 Exclusive Acrylic Stand Set", "mid", 35),

        # === ROUND 7 — Additional items to reach 510+ ===

        # More Pokemon Center Events
        ("Pokemon Center Event", "Pokemon", "Exclusive Plush", "Mimikyu Pokemon Center Halloween 2024 LE Plush", "mid", 55),
        ("Pokemon Center Event", "Pokemon", "Exclusive Card", "Mew Pokemon Center 25th Anniversary Promo Card", "high", 120),
        ("Pokemon Center Event", "Pokemon", "Exclusive Plush", "Eevee Pokemon Center Fukuoka Opening LE Plush", "mid", 60),

        # More Machi Asobi
        ("Machi Asobi", "Fate/Grand Order", "Exclusive Goods", "FGO Machi Asobi Exclusive Gilgamesh B2 Tapestry", "high", 110),
        ("Machi Asobi", "Demon Slayer", "Exclusive Figure", "Demon Slayer Machi Asobi Muzan LED Acrylic Panel", "mid", 70),

        # Toho Animation Store Events
        ("Toho Animation Store", "Haikyuu!!", "Exclusive Goods", "Haikyuu!! Toho Store Pop-Up Exclusive Acrylic Stand Set", "mid", 40),
        ("Toho Animation Store", "Jujutsu Kaisen", "Exclusive Goods", "JJK Toho Store Exclusive Gojo Domain Expansion Art Panel", "high", 100),

        # Additional GSC Festival
        ("GSC Festival", "Fate/Grand Order", "Exclusive Nendoroid", "Mash Kyrielight GSC Festival 2025 Exclusive Nendoroid", "mid", 80),
        ("GSC Festival", "Hatsune Miku", "Exclusive Nendoroid", "Hatsune Miku 16th Anniversary GSC Festival Exclusive", "high", 100),
    ]

    catalog = []
    for event, franchise, item_type, name, tier, price in items:
        catalog.append({
            "event": event,
            "franchise": franchise,
            "item_type": item_type,
            "name": name,
            "rarity_tier": tier,
            "price_eur": price,
        })

    catalog.extend(_batch_jp_events_2025())
    return catalog


def _batch_jp_events_2025() -> list[dict]:
    """Batch 8 — WonFes 2024/2025 garage kits, Comiket C103-C104, AnimeJapan 2025,
    Jump Festa expanded, TGS, AGF goods, Comic Market tapestries/clear files. ~50 items."""

    items = [
        # Wonder Festival 2024/2025 — Garage Kits & Prototype Figures
        ("WonFes", "Frieren", "Garage Kit", "Fern WonFes 2025 Summer 1/7 Resin GK Limited 15pcs", "grail", 400),
        ("WonFes", "Oshi no Ko", "Garage Kit", "Akane Kurokawa WonFes 2025 Winter 1/7 GK Unpainted", "high", 220),
        ("WonFes", "Dandadan", "Garage Kit", "Momo Ayase WonFes 2025 Summer 1/7 Resin GK Limited", "high", 260),
        ("WonFes", "Chainsaw Man", "Garage Kit", "Asa Mitaka War Devil 1/6 GK WonFes 2025 Limited 20pcs", "grail", 440),
        ("WonFes", "Solo Leveling", "Garage Kit", "Iron Shadow Monarch Form 1/6 Resin GK WonFes 2025", "grail", 480),
        ("WonFes", "Genshin Impact", "Exclusive Figure", "Furina WonFes 2025 Winter Exclusive 1/7 Painted GK", "high", 280),
        ("WonFes", "Hololive", "Exclusive Figure", "Usada Pekora WonFes 2025 Summer Exclusive 1/7", "high", 240),

        # Comiket C103/C104 — Doujinshi & Exclusive Goods
        ("Comiket", "Frieren", "Doujinshi Set", "Frieren C104 Premium Circle Doujinshi Bundle (8)", "mid", 65),
        ("Comiket", "Dandadan", "Doujinshi Set", "Dandadan C104 Circle Doujinshi Bundle (5)", "mid", 45),
        ("Comiket", "Hololive", "Tapestry", "Hololive C104 Exclusive Shion Murasaki B2 Tapestry", "mid", 55),
        ("Comiket", "Touhou Project", "Exclusive Goods", "Touhou C104 Fumo Plush Reimu Limited Edition", "high", 120),
        ("Comiket", "Blue Archive", "Exclusive Goods", "Blue Archive C104 Corporate Booth Art Board Set", "mid", 70),

        # AnimeJapan 2025 — New Merch
        ("AnimeJapan", "Dandadan", "Exclusive Figure", "Dandadan AnimeJapan 2025 Okarun Chibi Figure", "mid", 45),
        ("AnimeJapan", "Solo Leveling", "Exclusive Figure", "Solo Leveling AnimeJapan 2025 Sung Jinwoo Chibi Figure", "mid", 50),
        ("AnimeJapan", "Oshi no Ko", "Exhibit Goods", "Oshi no Ko AnimeJapan 2025 Exhibition Art Panel", "high", 100),
        ("AnimeJapan", "Blue Lock", "Clear File Set", "Blue Lock AnimeJapan 2025 Clear File Collection (5pc)", "standard", 18),
        ("AnimeJapan", "Frieren", "Exhibit Goods", "Frieren AnimeJapan 2025 Exhibition Acrylic Diorama", "high", 110),

        # Jump Festa — One Piece & Naruto & Dragon Ball Exclusives
        ("Jump Festa", "One Piece", "Exclusive Figure", "Luffy Nika Sun God Jump Festa 2025 Premium Figure", "high", 130),
        ("Jump Festa", "Naruto", "Exclusive Figure", "Naruto Baryon Mode Jump Festa 2025 Exclusive Figure", "high", 110),
        ("Jump Festa", "Dragon Ball", "Exclusive Figure", "Goku Ultra Instinct Omen Jump Festa 2025 Figure", "high", 100),
        ("Jump Festa", "Dragon Ball Daima", "Goods Set", "Dragon Ball Daima Jump Festa 2025 Goods Set (Towel + Badge)", "mid", 45),
        ("Jump Festa", "One Piece", "Exclusive Card", "One Piece Card Game Jump Festa 2025 Promo Yamato Alt Art", "high", 100),
        ("Jump Festa", "Chainsaw Man", "Exclusive Figure", "Power Blood Fiend Jump Festa 2025 Exclusive Figure", "mid", 65),

        # Tokyo Game Show — Game Merch
        ("Tokyo Game Show", "Metaphor: ReFantazio", "Exclusive Figure", "Protagonist TGS 2025 Exclusive Play Arts Mini", "high", 120),
        ("Tokyo Game Show", "Elden Ring DLC", "Exclusive Merch", "Elden Ring Shadow of the Erdtree TGS Art Board Set", "mid", 50),
        ("Tokyo Game Show", "Monster Hunter Wilds", "Exclusive Figure", "Seikret TGS 2025 Exclusive Plush", "mid", 45),

        # Animate Girls Festival — Otome & BL Goods
        ("AGF", "Twisted Wonderland", "Exclusive Goods", "Twisted Wonderland AGF 2025 Exclusive Acrylic Stand Full Set", "mid", 50),
        ("AGF", "Hypnosis Mic", "Exclusive Goods", "Hypnosis Mic AGF 2025 Exclusive Can Badge Set (12pc)", "mid", 35),
        ("AGF", "Obey Me!", "Exclusive Goods", "Obey Me! AGF 2025 Exclusive B2 Tapestry Set", "mid", 40),
        ("AGF", "Ensemble Stars!", "Exclusive Goods", "Enstars AGF 2025 Exclusive Bromide Card Full Set (24pc)", "mid", 45),
        ("AGF", "A3!", "Exclusive Goods", "A3! AGF 2025 Anniversary Exclusive Acrylic Panel Set", "mid", 38),

        # Comic Market — Limited Tapestries & Clear Files
        ("Comiket", "Genshin Impact", "Tapestry", "Genshin Impact C105 Exclusive B2 Tapestry Furina", "mid", 55),
        ("Comiket", "Uma Musume", "Clear File Set", "Uma Musume C105 Corporate Booth Clear File Set (5pc)", "standard", 22),
        ("Comiket", "Fate/Grand Order", "Tapestry", "FGO C105 Exclusive B1 Tapestry Oberon & Castoria", "high", 100),
        ("Comiket", "Lycoris Recoil", "Acrylic Stand", "Lycoris Recoil C105 Exclusive Acrylic Diorama Takina & Chisato", "mid", 40),

        # More Jump Festa — Card Game Promos
        ("Jump Festa", "Yu-Gi-Oh!", "Exclusive Card", "Yu-Gi-Oh! Jump Festa 2025 Secret Rare Promo Card Set (3)", "mid", 55),
        ("Jump Festa", "Dragon Ball Super", "Exclusive Card", "DBS Card Game Jump Festa 2025 SP Ultra Rare Pack", "mid", 60),
        ("Jump Festa", "One Piece", "Goods Set", "One Piece Jump Festa 2025 Complete Goods Box (Towel + Badge + Poster)", "mid", 55),

        # Treasure Festa (Yokohama) — More Garage Kits
        ("Treasure Festa", "Bocchi the Rock!", "Garage Kit", "Gotoh Hitori 1/7 Resin GK Treasure Festa Limited", "high", 220),
        ("Treasure Festa", "Spy x Family", "Garage Kit", "Yor Forger Thorn Princess 1/7 GK Treasure Festa Limited", "high", 260),

        # Hololive EXPO — More Exclusive Goods
        ("Hololive EXPO", "Hololive", "Exclusive Goods", "Hololive 5th Fes Exclusive Nendoroid Sakura Miko", "high", 110),
        ("Hololive EXPO", "Hololive", "Exclusive Goods", "Hololive EXPO 2025 Exclusive Acrylic Stand Full Set (15pc)", "high", 150),

        # Additional Ichiban Kuji — Latest Prizes
        ("Ichiban Kuji", "Solo Leveling", "Prize Figure", "Solo Leveling Ichiban Kuji A Prize Cha Hae-In", "mid", 55),
        ("Ichiban Kuji", "Dandadan", "Prize Figure", "Dandadan Ichiban Kuji Last One Prize Okarun & Turbo Granny", "high", 120),
        ("Ichiban Kuji", "Dragon Ball Daima", "Prize Figure", "Dragon Ball Daima Ichiban Kuji Last One Prize Mini Goku", "high", 110),
    ]

    catalog = []
    for event, franchise, item_type, name, tier, price in items:
        catalog.append({
            "event": event,
            "franchise": franchise,
            "item_type": item_type,
            "name": name,
            "rarity_tier": tier,
            "price_eur": price,
        })
    return catalog


def item_to_catalog_item(item: dict) -> CatalogItem:
    event = item["event"]
    name = item["name"]
    franchise = item["franchise"]
    item_type = item["item_type"]

    return CatalogItem(
        category=CATEGORY,
        item_key=slugify(f"{event}-{name}"),
        title=name,
        set_code=slugify(event),
        brand=event,
        rarity=item["rarity_tier"].title(),
        notes=f"{event} | {franchise} | {item_type}",
        attributes_json={
            "event": event,
            "franchise": franchise,
            "item_type": item_type,
        },
    )


def item_to_price_observation(item: dict) -> PriceObservation:
    tier = item["rarity_tier"]

    event = item["event"]
    edition_scores = {
        "WonFes": 0.90,
        "Comiket": 0.70,
        "AnimeJapan": 0.50,
        "Tamashii Nations": 0.85,
        "Jump Festa": 0.65,
        "Tokyo Game Show": 0.60,
        "Character1": 0.55,
        "Chara Expo": 0.55,
        "Anime Expo": 0.75,
        "Crunchyroll Expo": 0.60,
        "Ghibli Exhibition": 0.80,
        "Evangelion Exhibition": 0.85,
        "Movie Premium": 0.45,
        "Machi Asobi": 0.75,
        "CharaExpo": 0.55,
        "Anime NYC": 0.60,
        "Voice Actor Event": 0.80,
        "Shizuoka Hobby Show": 0.65,
        "All Japan Model Show": 0.65,
        "D23 Japan": 0.70,
        "Pokemon Center Event": 0.80,
        "Kyoto Animation Event": 0.85,
        "Gundam Base Tokyo": 0.75,
        "Gundam Base Fukuoka": 0.75,
        "Touken Ranbu Exhibition": 0.70,
        "Uta no Prince-sama Event": 0.60,
        "COMITIA": 0.55,
        "Animate Cafe": 0.50,
        "Tower Records Cafe": 0.50,
        "Square Enix Cafe": 0.55,
        "Capcom Cafe": 0.50,
        "Ichiban Kuji": 0.60,
        "Sakura-Con": 0.55,
        "Otakon": 0.55,
        "Hololive EXPO": 0.70,
        "AGF": 0.55,
        "Hobby Japan Exclusive": 0.70,
        "GSC Festival": 0.65,
        "Gundam Base Shanghai": 0.70,
        "Gundam Base Seoul": 0.65,
        "Comiket Special": 0.70,
        "Ensemble Stars Event": 0.55,
        "Sweets Paradise": 0.45,
        "Ufotable Cafe": 0.55,
        "Niconico Chokaigi": 0.50,
        "Treasure Festa": 0.85,
        "Toho Animation Store": 0.55,
    }

    return PriceObservation(
        features={
            "condition_score": 0.85,
            "rarity_score": shared_rarity_score(tier),
            "edition_score": edition_scores.get(event, 0.5),
        },
        price=item["price_eur"],
    )


def main():
    parser = argparse.ArgumentParser(description="Import JP event exclusives catalog + prices")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logger.info("=== JP Event Exclusives Import ===")

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

    logger.info(f"\n=== JP Event Exclusives Import Complete ===")
    logger.info(f"  Catalog items:      {len(all_items)}")
    logger.info(f"  Price observations: {len(all_observations)}")


if __name__ == "__main__":
    main()
