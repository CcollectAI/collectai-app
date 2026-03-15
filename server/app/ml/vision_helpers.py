"""
Shared types, constants, and utility functions for the vision classification pipeline.

Contains:
- ALL_CATEGORIES: canonical category ID list
- CATEGORY_DESCRIPTIONS: text descriptions for CLIP zero-shot matching
- CATEGORY_PROMPTS: category-specific extraction prompts for OpenAI Vision
- CONDITION_KEYWORDS: keyword sets for condition detection
- _HEURISTIC_PATTERNS: filename keyword patterns per category
- ClassificationResult: dataclass for classification output
- Math helpers: cosine_similarity, softmax
- _detect_condition_from_text: keyword-based condition detection
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# 36+ Categories — canonical IDs matching taxonomy_mapper.py
# ---------------------------------------------------------------------------

ALL_CATEGORIES: list[str] = [
    # TCGs
    "pokemon", "mtg", "yugioh", "lorcana",
    # Toys / Figures
    "funko", "designer_toys", "anime_figures", "hot_toys",
    "action_figures", "vintage_toys", "marvel_legends",
    # Building / Models
    "lego", "gunpla", "scale_models", "warhammer",
    # Gaming
    "retro_games",
    # Media
    "manga", "comic_books", "bluray_steelbook", "anime_bluray", "anime_soundtrack", "anime_ost_vinyl",
    # Music / Fandom
    "kpop_merch", "taylor_swift", "pop_fandom", "kpop_lightsticks",
    # Disney / Theme Parks
    "disney", "theme_park", "ghibli",
    # Japan Exclusives
    "bandai_premium", "jp_magazine", "jp_event",
    # Nintendo / Pokemon Merch
    "nintendo_merch", "retro_pokemon",
    # IP-Specific
    "one_piece", "vtuber",
    # Niche
    "keycaps", "loungefly",
    # Lifestyle
    "vinyl_records", "sneakers", "watches",
    # Collectibles
    "blind_box", "plush_collectibles",
    # Spirits / Luxury
    "whiskey", "vintage_cameras", "pens",
    # TCGs (stub)
    "digimon", "one_piece_tcg",
    # Legacy
    "diecast", "sportscards", "retro_handhelds",
    # New Categories
    "oop_board_games", "city_pop_vinyl", "niche_perfumery",
]

# Short text descriptions for each category (used by CLIP zero-shot matching).
CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "pokemon": "Pokemon trading card game card, Pokemon TCG, Pikachu, Charizard collectible card",
    "mtg": "Magic: The Gathering card, MTG collectible card game, Black Lotus, planeswalker",
    "yugioh": "Yu-Gi-Oh! trading card, YGO card game, Blue-Eyes White Dragon, Dark Magician",
    "lorcana": "Disney Lorcana trading card game, Lorcana TCG card",
    "funko": "Funko Pop vinyl figure, bobblehead collectible figure in box",
    "designer_toys": "Designer art toy, KAWS figure, Bearbrick, Medicom vinyl toy",
    "anime_figures": "Anime figure, Nendoroid, Figma, Japanese scale figure, PVC statue",
    "hot_toys": "Hot Toys sixth scale figure, premium action figure, Sideshow collectible",
    "action_figures": "Action figure toy, 6 inch figure, Hasbro Star Wars Black Series, GI Joe, Power Rangers Lightning",
    "vintage_toys": "Vintage toy, Kenner Star Wars figure, 1980s toy, retro action figure, AFA graded",
    "marvel_legends": "Marvel Legends action figure, Hasbro Marvel 6 inch, Build-A-Figure BAF wave",
    "lego": "LEGO set, LEGO bricks, LEGO minifigure, building block set",
    "gunpla": "Gunpla model kit, Gundam plastic model, Bandai mecha model kit",
    "scale_models": "Scale model kit, plastic model airplane, Tamiya model, military miniature",
    "warhammer": "Warhammer miniature, Warhammer 40K Space Marine, Games Workshop figure",
    "retro_games": "Retro video game cartridge, NES SNES N64 game, vintage console game, Backyard Baseball PC big box, Backyard Sports Humongous Entertainment",
    "manga": "Manga volume, Japanese comic book, tankoubon, manga graphic novel",
    "bluray_steelbook": "Blu-ray steelbook, 4K UHD limited edition movie disc, Criterion collection",
    "anime_bluray": "Anime Blu-ray box set, Japanese anime disc collection, Aniplex limited",
    "anime_soundtrack": "Anime soundtrack CD, anime OST compact disc, original sound track",
    "anime_ost_vinyl": "Anime vinyl record, anime soundtrack LP, OST vinyl pressing",
    "kpop_merch": "K-pop album, K-pop photocard, BTS BLACKPINK merchandise, idol goods",
    "taylor_swift": "Taylor Swift merchandise, Eras Tour merch, Taylor Swift vinyl record",
    "pop_fandom": "Pop music fandom merchandise, concert tour merch, music artist collectible",
    "kpop_lightsticks": "K-pop lightstick, concert light stick, ARMY bomb, official fan light",
    "disney": "Disney collectible, Disney pin, Disney limited edition figure, Disneyana",
    "theme_park": "Theme park exclusive merchandise, Disneyland souvenir, park-exclusive item",
    "ghibli": "Studio Ghibli collectible, Totoro figure, Spirited Away merchandise, Miyazaki",
    "bandai_premium": "Bandai Premium exclusive, P-Bandai figure, Tamashii Nations, S.H.Figuarts",
    "jp_magazine": "Japanese magazine insert, Dengeki appendix, Famitsu furoku, anime magazine",
    "jp_event": "Japanese event exclusive, Comiket goods, Wonder Festival item, anime convention",
    "nintendo_merch": "Nintendo merchandise, Pokemon Center plush, amiibo figure, Nintendo store",
    "retro_pokemon": "Retro Pokemon toy, vintage Pokemon accessory, Tomy Pokemon figure",
    "one_piece": "One Piece figure, One Piece collectible, Luffy statue, Portrait of Pirates",
    "vtuber": "VTuber merchandise, Hololive goods, Nijisanji merch, virtual YouTuber",
    "keycaps": "Artisan keycap, mechanical keyboard keycap, GMK keycap set, custom cap",
    "loungefly": "Loungefly backpack, Loungefly bag, Loungefly wallet, Disney Loungefly",
    "comic_books": "Comic book, graphic novel, Marvel DC Image, first appearance, key issue, CGC graded comic",
    "vinyl_records": "Vinyl record, LP album, 12-inch vinyl, colored vinyl, limited pressing, turntable record",
    "diecast": "Diecast model car, Hot Wheels, Matchbox, die-cast vehicle, miniature car",
    "sportscards": "Sports trading card, baseball card, basketball card, Topps Panini rookie card",
    "retro_handhelds": "Retro handheld console, Game Boy, Tamagotchi, DS, PSP, retro portable gaming device",
    "sneakers": "Collectible sneakers, limited edition shoes, Nike Jordan, Yeezy, rare kicks",
    "watches": "Luxury watch, Rolex, Omega, Seiko, timepiece, wristwatch, chronograph",
    "blind_box": "Blind box figure, Pop Mart, Labubu, Sonny Angels, Dimoo, mystery box toy",
    "plush_collectibles": "Collectible plush, Squishmallow, Jellycat, Sanrio plush, stuffed animal",
    "whiskey": "Whiskey bottle, bourbon, scotch, Japanese whisky, collectible spirits",
    "vintage_cameras": "Vintage film camera, analog camera, Leica, Hasselblad, Nikon FM, Canon AE-1",
    "pens": "Fountain pen, luxury pen, Montblanc, Pelikan, Sailor, Pilot Namiki, writing instrument",
    "digimon": "Digimon trading card, Digimon Card Game, Omnimon, Agumon, collectible card",
    "one_piece_tcg": "One Piece trading card game, One Piece TCG card, Luffy card, manga art card",
    "oop_board_games": "Out-of-print board game, Kickstarter exclusive board game, sealed euro game, Gloomhaven, Kingdom Death",
    "city_pop_vinyl": "Japanese City Pop vinyl record, Tatsuro Yamashita LP, Mariya Takeuchi vinyl, future funk record",
    "niche_perfumery": "Niche perfume bottle, fragrance collection, Creed Aventus, Tom Ford Private Blend, MFK Baccarat Rouge",
}

# ---------------------------------------------------------------------------
# Category-specific extraction prompts (injected into OpenAI Vision prompt)
# ---------------------------------------------------------------------------

CATEGORY_PROMPTS: dict[str, str] = {
    # Trading cards
    "pokemon": (
        "Extract: card_name, set_name, card_number (e.g. #4/102), rarity_symbol "
        "(circle/diamond/star/rainbow), printing (1st Edition/Unlimited/Shadowless), "
        "is_holo (boolean), language, condition_notes (scratches, whitening, centering)."
    ),
    "mtg": (
        "Extract: card_name, set_name, set_code, card_number, rarity "
        "(common/uncommon/rare/mythic), foil (boolean), language, "
        "edition (Alpha/Beta/Unlimited/Revised/etc), condition_notes."
    ),
    "yugioh": (
        "Extract: card_name, set_code, card_number, rarity "
        "(Common/Rare/Super/Ultra/Secret/Ghost/Starlight), "
        "printing (1st Edition/Unlimited), language, condition_notes."
    ),
    "lorcana": (
        "Extract: card_name, set_name, card_number, rarity "
        "(Common/Uncommon/Rare/Super Rare/Legendary), foil (boolean), "
        "ink_color, condition_notes."
    ),
    "sportscards": (
        "Extract: player_name, year, brand (Topps/Panini/Upper Deck), "
        "set_name, card_number, parallel (base/refractor/prizm/auto), "
        "graded (boolean), grade_service, grade_value, condition_notes."
    ),
    # Figures
    "funko": (
        "Extract: character_name, franchise, figure_number, product_line "
        "(Pop/Soda/Mystery Mini), exclusive_sticker (Chase/Convention/Store), "
        "is_sealed (boolean), condition_notes (box damage, window)."
    ),
    "anime_figures": (
        "Extract: character_name, franchise, manufacturer (Good Smile/Alter/Kotobukiya), "
        "figure_type (Nendoroid/Figma/Scale), scale (1/4, 1/7, 1/8), "
        "is_sealed (boolean), condition_notes."
    ),
    "hot_toys": (
        "Extract: character_name, franchise, figure_type (MMS/DX/Cosbaby), "
        "scale, exclusive, is_sealed (boolean), condition_notes."
    ),
    "designer_toys": (
        "Extract: character_name, artist_designer, brand (KAWS/Bearbrick/Medicom), "
        "size (100%/400%/1000%), variant_colorway, is_sealed (boolean), condition_notes."
    ),
    # Building / Models
    "lego": (
        "Extract: set_name, set_number, theme (Star Wars/City/Technic/Creator), "
        "piece_count, year, built_or_sealed (built/sealed/open complete), "
        "minifigures_included, condition_notes."
    ),
    "gunpla": (
        "Extract: model_name, grade (HG/RG/MG/PG/SD), scale, "
        "series (Gundam/Zaku/etc), kit_number, built_or_unbuilt, "
        "painted (boolean), condition_notes."
    ),
    "warhammer": (
        "Extract: unit_name, faction (Space Marines/Orks/Necrons/etc), "
        "game_system (40K/AoS/Kill Team), built_or_sprue (built/on sprue/NOS), "
        "painted (boolean), edition, condition_notes."
    ),
    "scale_models": (
        "Extract: subject_name, manufacturer (Tamiya/Hasegawa/Revell), "
        "scale (1/35, 1/48, 1/72), category (aircraft/armor/ship/car), "
        "built_or_unbuilt, condition_notes."
    ),
    # Media
    "manga": (
        "Extract: title, volume_number, author, publisher "
        "(Viz/Kodansha/Yen Press/Shueisha), isbn, language, "
        "printing (1st print/reprint), condition_notes."
    ),
    "bluray_steelbook": (
        "Extract: title, format (Blu-ray/4K UHD/DVD), steelbook (boolean), "
        "edition (Standard/Limited/Criterion/Arrow), region_code, "
        "slipcover (boolean), is_sealed (boolean), condition_notes."
    ),
    "anime_bluray": (
        "Extract: title, format (Blu-ray/DVD), publisher (Aniplex/Funimation), "
        "edition (Standard/Limited/Collector), region_code, episodes_included, "
        "is_sealed (boolean), condition_notes."
    ),
    "anime_ost_vinyl": (
        "Extract: title, artist_composer, anime_franchise, label, "
        "format (LP/2xLP/7inch), color_variant, pressing (1st/repress), "
        "is_sealed (boolean), condition_notes."
    ),
    "anime_soundtrack": (
        "Extract: title, artist_composer, anime_franchise, label, "
        "format (CD/SACD), is_limited (boolean), is_sealed (boolean), condition_notes."
    ),
    # Music / Fandom
    "kpop_merch": (
        "Extract: group_name, album_name, version_variant, "
        "inclusions (photocard/poster/bookmark), member_pulled, "
        "is_sealed (boolean), condition_notes."
    ),
    "taylor_swift": (
        "Extract: item_type (vinyl/CD/merch/poster), album_era, variant, "
        "tour (Eras/1989/etc), is_signed (boolean), is_sealed (boolean), condition_notes."
    ),
    "kpop_lightsticks": (
        "Extract: group_name, version (v1/v2/SE), model_name, "
        "is_official (boolean), is_sealed (boolean), condition_notes."
    ),
    # Gaming
    "retro_games": (
        "Extract: game_title, platform (NES/SNES/N64/Game Boy/Genesis), "
        "region (NTSC/PAL/NTSC-J), cib_status (CIB/cart only/box only), "
        "manual_included (boolean), condition_notes."
    ),
    # Nintendo / Pokemon Merch
    "nintendo_merch": (
        "Extract: item_name, character, product_type (plush/amiibo/figure/apparel), "
        "store_exclusive (Pokemon Center/Nintendo Store), year, "
        "is_sealed (boolean), condition_notes."
    ),
    "retro_pokemon": (
        "Extract: item_name, character, manufacturer (Tomy/Hasbro/Bandai), "
        "product_type (figure/plush/toy), year, is_sealed (boolean), condition_notes."
    ),
    # Disney / Theme Parks
    "disney": (
        "Extract: item_name, character, product_type (pin/figure/plush/ornament/doll), "
        "franchise (Frozen/Marvel/Star Wars/Pixar), year, edition (Limited/Open), "
        "pin_number, is_sealed (boolean), condition_notes."
    ),
    "theme_park": (
        "Extract: item_name, park_name (Disneyland/Walt Disney World/Universal Studios), "
        "event_name, year, product_type (pin/figure/mug/magnet/clothing), "
        "is_exclusive (boolean), is_sealed (boolean), condition_notes."
    ),
    "ghibli": (
        "Extract: item_name, film_title (Spirited Away/Totoro/Princess Mononoke), "
        "character, product_type (figure/plush/music box/print), manufacturer, "
        "is_sealed (boolean), condition_notes."
    ),
    # Japan Exclusives
    "bandai_premium": (
        "Extract: item_name, franchise, product_line (S.H.Figuarts/Metal Build/"
        "Figure-rise/Tamashii Nations), scale, is_p_bandai_exclusive (boolean), "
        "is_sealed (boolean), condition_notes."
    ),
    "jp_magazine": (
        "Extract: magazine_name (Dengeki/Famitsu/Newtype/Animage), issue_date, "
        "insert_type (furoku/poster/figure/card), franchise, "
        "is_insert_included (boolean), condition_notes."
    ),
    "jp_event": (
        "Extract: event_name (Comiket/Wonder Festival/AnimeJapan/Jump Festa), "
        "year, circle_booth, item_type (tapestry/acrylic stand/keychain/doujin), "
        "franchise, is_limited (boolean), condition_notes."
    ),
    # IP-Specific
    "one_piece": (
        "Extract: character_name, figure_line (Portrait of Pirates/Figuarts Zero/"
        "Grandista/Ichiban Kuji), manufacturer (Megahouse/Banpresto/Bandai), "
        "scale, prize_rank, is_sealed (boolean), condition_notes."
    ),
    "vtuber": (
        "Extract: vtuber_name, agency (Hololive/Nijisanji/VShojo/indie), "
        "item_type (acrylic stand/tapestry/voice pack/badge/plush), "
        "event_name, is_official (boolean), is_sealed (boolean), condition_notes."
    ),
    # Niche
    "keycaps": (
        "Extract: keycap_name, maker_artist, sculpt_name, colorway, "
        "profile (SA/Cherry/OEM/DSA), material (resin/PBT/ABS), "
        "mount (MX/Topre), is_sealed (boolean), condition_notes."
    ),
    "loungefly": (
        "Extract: item_name, franchise (Disney/Marvel/Star Wars/Sanrio/Pokemon), "
        "product_type (mini backpack/wallet/crossbody/pin set), "
        "exclusive_retailer, year, is_sealed (boolean), condition_notes."
    ),
    # Legacy
    "diecast": (
        "Extract: vehicle_name, brand (Hot Wheels/Matchbox/Tomica/Greenlight), "
        "scale (1/64, 1/43, 1/24, 1/18), series_line, year, "
        "variant (chase/treasure hunt/super), is_sealed (boolean), condition_notes."
    ),
    "pop_fandom": (
        "Extract: artist_name, item_type (vinyl/CD/poster/signed item/tour merch), "
        "tour_or_era, year, variant, is_signed (boolean), "
        "is_sealed (boolean), condition_notes."
    ),
    "retro_handhelds": (
        "Extract: device_name, brand (Nintendo/Sega/Atari/Bandai/Tiger), "
        "model (Game Boy/Game Gear/Neo Geo Pocket/Tamagotchi), "
        "variant_color, year, working_status (working/for parts), "
        "cib_status (CIB/loose/box only), condition_notes."
    ),
    # Lifestyle / Luxury
    "watches": (
        "Extract: brand (Rolex/Omega/Seiko/Tudor/Casio), model_name, "
        "reference_number, case_material (steel/gold/titanium), "
        "dial_color, movement (automatic/quartz/manual), "
        "has_box_papers (boolean), condition_notes."
    ),
    "sneakers": (
        "Extract: brand (Nike/Adidas/New Balance/Jordan), model_name, "
        "colorway, size, sku_style_code, collaboration, "
        "is_deadstock (boolean), condition_notes."
    ),
    # Collectibles
    "blind_box": (
        "Extract: brand (Pop Mart/Medicom/Tokidoki), series_name, "
        "character_name (Labubu/Molly/Dimoo/SkullPanda/Sonny Angel), "
        "variant (regular/secret/chase/mega secret), "
        "is_sealed (boolean), condition_notes."
    ),
    "plush_collectibles": (
        "Extract: brand (Squishmallow/Jellycat/Sanrio/Build-A-Bear), "
        "character_name, size (inches), collection_line, "
        "exclusive_retailer, is_with_tags (boolean), condition_notes."
    ),
    # Spirits
    "whiskey": (
        "Extract: brand (Macallan/Pappy Van Winkle/Yamazaki/Buffalo Trace), "
        "expression_name, age_statement, proof_abv, bottle_size, "
        "vintage_year, is_sealed (boolean), condition_notes."
    ),
    # Photography
    "vintage_cameras": (
        "Extract: brand (Leica/Nikon/Canon/Hasselblad/Pentax/Mamiya), "
        "model_name, camera_type (SLR/rangefinder/TLR/medium format/point-and-shoot), "
        "lens_included, film_format (35mm/120/large format), "
        "serial_number, working_status (working/for parts/CLA done), condition_notes."
    ),
    # Writing instruments
    "pens": (
        "Extract: brand (Montblanc/Pelikan/Sailor/Pilot/Visconti/Parker), "
        "model_name, pen_type (fountain/rollerball/ballpoint), "
        "nib_size (EF/F/M/B), nib_material (steel/14K/18K/21K), "
        "filling_system (piston/cartridge/converter/vacuum), "
        "is_limited_edition (boolean), condition_notes."
    ),
    # TCGs (additional)
    "digimon": (
        "Extract: card_name, set_name, card_number, rarity "
        "(Common/Uncommon/Rare/Super Rare/Secret Rare/Alt Art), "
        "color (Red/Blue/Yellow/Green/Black/Purple/White), "
        "foil (boolean), language, condition_notes."
    ),
    "one_piece_tcg": (
        "Extract: card_name, set_code (OP01/OP02/etc), card_number, "
        "rarity (C/UC/R/SR/SEC/L/SP/Manga Art), "
        "leader_or_character, color, foil_parallel (boolean), "
        "language, condition_notes."
    ),
    "comic_books": (
        "Extract: title, issue_number, publisher (Marvel/DC/Image/etc), "
        "year, key_issue_note (first appearance, death, variant cover), "
        "graded (boolean), grade_service (CGC/CBCS), grade_number, "
        "variant_cover_artist, condition_notes."
    ),
    "vinyl_records": (
        "Extract: artist, album_title, label, catalog_number, "
        "pressing_year, variant (colored/picture disc/limited/OBI strip), "
        "speed (33/45 RPM), format (LP/EP/single/box set), "
        "is_sealed (boolean), condition_notes."
    ),
    # New Categories
    "oop_board_games": (
        "Extract: game_name, publisher (Fantasy Flight/CMON/Stonemaier/Chip Theory), "
        "designer, player_count, edition (1st Edition/Kickstarter Deluxe/Retail/Collector's), "
        "is_sealed (boolean), completeness (complete/missing pieces), condition_notes."
    ),
    "city_pop_vinyl": (
        "Extract: artist (Tatsuro Yamashita/Mariya Takeuchi/Anri/etc), album_title, "
        "label (Nippon Columbia/Air Records/Moon Records), catalog_number, "
        "pressing (OG/reissue/remaster), has_obi_strip (boolean), "
        "vinyl_color, format (LP/2xLP/7\"/12\"), condition_notes."
    ),
    "niche_perfumery": (
        "Extract: house (MFK/Tom Ford/Creed/Xerjoff/etc), fragrance_name, "
        "concentration (EDT/EDP/Extrait/Parfum), bottle_size_ml, "
        "fill_level (full/partial), batch_code, "
        "is_box_included (boolean), condition_notes."
    ),
}

# Default extraction prompt for categories without a specific template
DEFAULT_CATEGORY_PROMPT = (
    "Extract: item_name, brand, series_line, variant_colorway, "
    "year_released, is_sealed (boolean), condition_notes."
)

# Condition keywords for heuristic detection
CONDITION_KEYWORDS: dict[str, list[str]] = {
    "mint": ["mint", "gem mint", "pristine", "perfect"],
    "near_mint": ["near mint", "nm", "excellent", "like new"],
    "very_good": ["very good", "vg", "fine"],
    "good": ["good", "gd", "decent"],
    "fair": ["fair", "fr", "played", "used"],
    "poor": ["poor", "pr", "damaged", "heavily played"],
}

# Heuristic keyword patterns per category (subset for filename matching)
HEURISTIC_PATTERNS: dict[str, list[str]] = {
    "pokemon": ["pokemon", "pikachu", "charizard", "pokémon", "psa.*pokemon"],
    "mtg": ["magic.*gathering", "mtg", "black.*lotus"],
    "yugioh": ["yugioh", "yu-gi-oh", "ygo"],
    "lorcana": ["lorcana"],
    "funko": ["funko", "pop.*vinyl"],
    "designer_toys": ["kaws", "bearbrick", "medicom", "pop.*mart"],
    "anime_figures": ["nendoroid", "figma", "scale.*figure", "anime.*figure"],
    "hot_toys": ["hot.*toys", "sideshow", "sixth.*scale"],
    "lego": ["lego"],
    "gunpla": ["gunpla", "gundam", "bandai.*model"],
    "scale_models": ["tamiya", "hasegawa", "revell", "airfix", "scale.*model"],
    "warhammer": ["warhammer", "40k", "space.*marine", "games.*workshop"],
    "retro_games": ["nes", "snes", "n64", "game.*boy", "retro.*game", "backyard.*sports", "backyard.*baseball", "humongous.*entertainment"],
    "manga": ["manga"],
    "bluray_steelbook": ["steelbook", "4k.*uhd", "criterion"],
    "anime_bluray": ["anime.*blu", "aniplex"],
    "anime_soundtrack": ["anime.*ost", "anime.*soundtrack"],
    "anime_ost_vinyl": ["anime.*vinyl", "ost.*vinyl"],
    "kpop_merch": ["bts", "blackpink", "kpop", "k-pop", "stray.*kids"],
    "taylor_swift": ["taylor.*swift", "swiftie", "eras.*tour"],
    "pop_fandom": ["ariana.*grande", "olivia.*rodrigo", "tour.*merch"],
    "kpop_lightsticks": ["lightstick", "light.*stick", "army.*bomb"],
    "disney": ["disney.*pin", "disney.*collect", "disneyana"],
    "theme_park": ["theme.*park", "disneyland", "universal.*studios"],
    "ghibli": ["ghibli", "totoro", "miyazaki", "spirited.*away"],
    "bandai_premium": ["p-bandai", "bandai.*premium", "figuarts"],
    "jp_magazine": ["dengeki", "famitsu", "furoku"],
    "jp_event": ["comiket", "wonder.*festival", "wonfes"],
    "nintendo_merch": ["pokemon.*center", "amiibo", "nintendo.*store"],
    "retro_pokemon": ["retro.*pokemon", "tomy.*pokemon"],
    "one_piece": ["one.*piece", "luffy", "portrait.*pirates"],
    "vtuber": ["vtuber", "hololive", "nijisanji"],
    "keycaps": ["keycap", "artisan.*keycap", "gmk"],
    "loungefly": ["loungefly"],
    "diecast": ["hot.*wheels", "hotwheels", "diecast", "matchbox"],
    "sportscards": ["topps", "panini", "rookie.*card", "prizm"],
    "retro_handhelds": ["game.*boy", "tamagotchi", "psp", "nintendo.*ds", "retro.*handheld"],
}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ClassificationResult:
    category_id: str
    category_confidence: float
    condition: Optional[str] = None
    condition_confidence: float = 0.0
    suggested_name: Optional[str] = None
    attributes: dict[str, Any] = field(default_factory=dict)
    embedding_vector: Optional[list[float]] = None
    classification_method: str = "heuristic"
    # R15-11: Track which model(s) were used for reproducibility
    model_version: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "category_id": self.category_id,
            "category_confidence": round(self.category_confidence, 4),
            "condition": self.condition,
            "condition_confidence": round(self.condition_confidence, 4),
            "suggested_name": self.suggested_name,
            "attributes": self.attributes,
            "embedding_vector": self.embedding_vector,
            "classification_method": self.classification_method,
            "model_version": self.model_version,
        }


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or len(a) == 0:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def softmax(scores: list[float]) -> list[float]:
    """Numerically stable softmax over a list of scores."""
    if not scores:
        return []
    max_s = max(scores)
    exps = [math.exp(s - max_s) for s in scores]
    total = sum(exps)
    if total == 0.0:
        return [1.0 / len(scores)] * len(scores)
    return [e / total for e in exps]


# ---------------------------------------------------------------------------
# Condition detection
# ---------------------------------------------------------------------------

def detect_condition_from_text(text: str) -> tuple[str | None, float]:
    """Detect condition from text using keyword matching (longest match first)."""
    text_lower = text.lower()

    # Sort conditions by keyword length descending to prevent partial matches
    # e.g., "near mint" should match before "mint"
    all_conditions: list[tuple[str, str]] = []
    for cond_id, keywords in CONDITION_KEYWORDS.items():
        for kw in keywords:
            all_conditions.append((kw, cond_id))
    all_conditions.sort(key=lambda x: len(x[0]), reverse=True)

    for keyword, cond_id in all_conditions:
        if keyword in text_lower:
            return cond_id, 0.6
    return None, 0.0
