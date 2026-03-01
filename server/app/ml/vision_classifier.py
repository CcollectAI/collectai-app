"""
Vision classifier for CollectAI.

Classifies collectible items from images using a 3-tier approach:
  Tier 1 (CLIP via fal.ai): Real image embeddings + zero-shot category matching
  Tier 2 (OpenAI Vision): GPT-4o-mini vision API for classification
  Tier 3 (Heuristic): Filename keywords, EXIF metadata, barcode detection

Returns a ClassificationResult with category, confidence, condition, and optional embeddings.
"""

from __future__ import annotations

import base64
import json
import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from app.config import FAL_KEY, FAL_CLIP_URL, OPENAI_API_KEY, OPENAI_VISION_MODEL

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 36 Categories — canonical IDs matching taxonomy_mapper.py
# ---------------------------------------------------------------------------

ALL_CATEGORIES: list[str] = [
    # TCGs
    "pokemon", "mtg", "yugioh", "lorcana",
    # Toys / Figures
    "funko", "designer_toys", "anime_figures", "hot_toys",
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
    "lego": "LEGO set, LEGO bricks, LEGO minifigure, building block set",
    "gunpla": "Gunpla model kit, Gundam plastic model, Bandai mecha model kit",
    "scale_models": "Scale model kit, plastic model airplane, Tamiya model, military miniature",
    "warhammer": "Warhammer miniature, Warhammer 40K Space Marine, Games Workshop figure",
    "retro_games": "Retro video game cartridge, NES SNES N64 game, vintage console game",
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
}

# Condition keywords for heuristic detection
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
}

# Default extraction prompt for categories without a specific template
_DEFAULT_CATEGORY_PROMPT = (
    "Extract: item_name, brand, series_line, variant_colorway, "
    "year_released, is_sealed (boolean), condition_notes."
)

CONDITION_KEYWORDS: dict[str, list[str]] = {
    "mint": ["mint", "gem mint", "pristine", "perfect"],
    "near_mint": ["near mint", "nm", "excellent", "like new"],
    "very_good": ["very good", "vg", "fine"],
    "good": ["good", "gd", "decent"],
    "fair": ["fair", "fr", "played", "used"],
    "poor": ["poor", "pr", "damaged", "heavily played"],
}

# Heuristic keyword patterns per category (subset for filename matching)
_HEURISTIC_PATTERNS: dict[str, list[str]] = {
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
    "retro_games": ["nes", "snes", "n64", "game.*boy", "retro.*game"],
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

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or len(a) == 0:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _softmax(scores: list[float]) -> list[float]:
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
# Tier 1 — CLIP via fal.ai
# ---------------------------------------------------------------------------

# Cached text embeddings for category descriptions.  Populated once on first
# CLIP classification call, then reused for all subsequent calls.  This avoids
# 37+ fal.ai API calls per scan — only 1 (image) is needed after warm-up.
_clip_text_embeddings: dict[str, list[float]] = {}
_clip_text_embeddings_loaded: bool = False


async def _ensure_clip_text_embeddings(client: httpx.AsyncClient) -> dict[str, list[float]]:
    """Fetch and cache text embeddings for all category descriptions (once)."""
    global _clip_text_embeddings_loaded

    if _clip_text_embeddings_loaded and _clip_text_embeddings:
        return _clip_text_embeddings

    logger.info("CLIP: warming up text embeddings for %d categories", len(ALL_CATEGORIES))
    for cat_id in ALL_CATEGORIES:
        if cat_id in _clip_text_embeddings:
            continue
        desc = CATEGORY_DESCRIPTIONS.get(cat_id, cat_id)
        try:
            text_resp = await client.post(
                FAL_CLIP_URL,
                headers={
                    "Authorization": f"Key {FAL_KEY}",
                    "Content-Type": "application/json",
                },
                json={"text": desc},
            )
            text_resp.raise_for_status()
            text_data = text_resp.json()
            emb: list[float] = text_data.get("embedding", [])
            if emb:
                _clip_text_embeddings[cat_id] = emb
        except Exception as e:
            logger.warning("CLIP: failed to get text embedding for %s: %s", cat_id, e)

    _clip_text_embeddings_loaded = True
    logger.info("CLIP: cached %d/%d text embeddings", len(_clip_text_embeddings), len(ALL_CATEGORIES))
    return _clip_text_embeddings


async def _classify_clip(image_bytes: bytes, filename: str) -> ClassificationResult | None:
    """
    Use fal.ai CLIP endpoint to generate image embeddings, then compute
    cosine similarity against cached text embeddings of all category descriptions.
    """
    if not FAL_KEY:
        return None

    logger.info("vision_classifier: attempting CLIP classification via fal.ai")

    try:
        # Encode image as base64 data URI
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        # Detect MIME type from magic bytes
        mime = "image/jpeg"
        if image_bytes[:4] == b"\x89PNG":
            mime = "image/png"
        elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
            mime = "image/webp"
        data_uri = f"data:{mime};base64,{b64_image}"

        # 1) Get image embedding
        async with httpx.AsyncClient(timeout=30.0) as client:
            img_resp = await client.post(
                FAL_CLIP_URL,
                headers={
                    "Authorization": f"Key {FAL_KEY}",
                    "Content-Type": "application/json",
                },
                json={"image_url": data_uri},
            )
            img_resp.raise_for_status()
            img_data = img_resp.json()
            image_embedding: list[float] = img_data.get("embedding", [])

            if not image_embedding:
                logger.warning("CLIP returned empty image embedding")
                return None

            # 2) Compare against cached text embeddings
            text_embs = await _ensure_clip_text_embeddings(client)
            similarities: list[tuple[str, float]] = []
            for cat_id, text_embedding in text_embs.items():
                sim = _cosine_similarity(image_embedding, text_embedding)
                similarities.append((cat_id, sim))

            if not similarities:
                logger.warning("CLIP: no text embeddings generated")
                return None

            # Sort by similarity descending
            similarities.sort(key=lambda x: x[1], reverse=True)
            best_cat, best_sim = similarities[0]

            # Convert raw cosine similarity to a confidence via softmax
            raw_scores = [s for _, s in similarities]
            probs = _softmax([s * 10.0 for s in raw_scores])  # scale for sharper softmax
            confidence = probs[0]

            logger.info(
                "CLIP classification: category=%s sim=%.4f confidence=%.4f",
                best_cat, best_sim, confidence,
            )

            return ClassificationResult(
                category_id=best_cat,
                category_confidence=min(confidence, 1.0),
                suggested_name=None,
                attributes={"top_3": [
                    {"category": similarities[i][0], "score": round(similarities[i][1], 4)}
                    for i in range(min(3, len(similarities)))
                ]},
                embedding_vector=image_embedding,
                classification_method="clip",
                model_version=f"clip:fal-ai/clip@{FAL_CLIP_URL}",
            )

    except httpx.HTTPStatusError as e:
        logger.warning("CLIP API HTTP error: %s (status %d)", e, e.response.status_code)
        return None
    except Exception as e:
        logger.warning("CLIP classification failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Tier 2 — OpenAI Vision API
# ---------------------------------------------------------------------------

_OPENAI_SYSTEM_PROMPT = """Collectibles ID expert. Observe image details (text, logos, numbers, packaging, damage), classify category, identify specific item (set/number/edition/variant), extract attributes, assess condition (mint/near_mint/very_good/good/fair/poor).

Categories: pokemon,mtg,yugioh,lorcana,funko,designer_toys,anime_figures,hot_toys,lego,gunpla,scale_models,warhammer,retro_games,manga,bluray_steelbook,anime_bluray,anime_soundtrack,anime_ost_vinyl,kpop_merch,taylor_swift,pop_fandom,kpop_lightsticks,disney,theme_park,ghibli,bandai_premium,jp_magazine,jp_event,nintendo_merch,retro_pokemon,one_piece,vtuber,keycaps,loungefly,diecast,sportscards,retro_handhelds

{category_detail}"""

# Structured output JSON schema for response_format
_IDENTIFICATION_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "collectible_identification",
        "strict": False,
        "schema": {
            "type": "object",
            "properties": {
                "reasoning": {
                    "type": "string",
                    "description": "Chain-of-thought trace: what you see, how you identify it",
                },
                "category_id": {
                    "type": "string",
                    "description": "Category ID from the allowed list",
                },
                "category_confidence": {
                    "type": "number",
                    "description": "Confidence in category (0.0-1.0)",
                },
                "suggested_name": {
                    "type": "string",
                    "description": "Specific item name with set/number/edition/variant",
                },
                "name_confidence": {
                    "type": "number",
                    "description": "Confidence in the item name (0.0-1.0)",
                },
                "condition": {
                    "anyOf": [{"type": "string"}, {"type": "null"}],
                    "description": "Condition: mint, near_mint, very_good, good, fair, poor, or null",
                },
                "condition_confidence": {
                    "type": "number",
                    "description": "Confidence in condition assessment (0.0-1.0)",
                },
                "attributes": {
                    "type": "object",
                    "description": "Category-specific extracted attributes",
                    "additionalProperties": True,
                },
                "search_keywords": {
                    "type": "array",
                    "description": "3-5 keywords for catalog search",
                    "items": {"type": "string"},
                },
            },
            "required": [
                "reasoning", "category_id", "category_confidence",
                "suggested_name", "name_confidence",
                "condition", "condition_confidence",
                "attributes", "search_keywords",
            ],
            "additionalProperties": False,
        },
    },
}


def _build_system_prompt(category_hint: str | None = None) -> str:
    """Build the system prompt, optionally injecting category-specific extraction instructions."""
    if category_hint:
        detail = CATEGORY_PROMPTS.get(category_hint, _DEFAULT_CATEGORY_PROMPT)
        detail_block = f"Category hint: {category_hint}\n{detail}"
    else:
        detail_block = (
            "No category hint available. Identify the category first, "
            "then extract relevant attributes."
        )
    return _OPENAI_SYSTEM_PROMPT.format(category_detail=detail_block)


async def _classify_openai_vision(
    image_bytes: bytes,
    filename: str,
    category_hint: str | None = None,
) -> ClassificationResult | None:
    """
    Use OpenAI Vision API with chain-of-thought prompting and structured output
    to identify a specific collectible item from an image.
    """
    if not OPENAI_API_KEY:
        return None

    logger.info(
        "vision_classifier: attempting OpenAI Vision classification (hint=%s)",
        category_hint,
    )

    try:
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        mime = "image/jpeg"
        if image_bytes[:4] == b"\x89PNG":
            mime = "image/png"
        elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
            mime = "image/webp"

        system_prompt = _build_system_prompt(category_hint)

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": OPENAI_VISION_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime};base64,{b64_image}",
                                        "detail": "auto",
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": f"Identify this collectible item. Filename: {filename}",
                                },
                            ],
                        },
                    ],
                    "response_format": _IDENTIFICATION_SCHEMA,
                    "max_tokens": 800,
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        # Parse the structured response
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            logger.warning("OpenAI Vision returned empty content")
            return None

        # With response_format, content is guaranteed valid JSON (no markdown stripping needed)
        # But keep a safety fallback for edge cases
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            lines = [ln for ln in lines if not ln.strip().startswith("```")]
            content = "\n".join(lines).strip()

        parsed = json.loads(content)

        category_id = parsed.get("category_id", "")
        if category_id not in ALL_CATEGORIES:
            logger.warning("OpenAI Vision returned unknown category: %s", category_id)
            cat_lower = category_id.lower().replace(" ", "_").replace("-", "_")
            if cat_lower in ALL_CATEGORIES:
                category_id = cat_lower
            else:
                return None

        confidence = max(0.0, min(1.0, float(parsed.get("category_confidence", 0.7))))
        name_confidence = max(0.0, min(1.0, float(parsed.get("name_confidence", 0.5))))

        condition = parsed.get("condition")
        if condition and condition not in CONDITION_KEYWORDS:
            condition = condition.lower().replace(" ", "_").replace("-", "_")
            if condition not in CONDITION_KEYWORDS:
                condition = None

        cond_conf = max(0.0, min(1.0, float(parsed.get("condition_confidence", 0.0))))

        # Merge extracted attributes with per-field confidences and search keywords
        attributes = parsed.get("attributes", {})
        attributes["search_keywords"] = parsed.get("search_keywords", [])
        attributes["chain_of_thought"] = parsed.get("reasoning", "")
        attributes["name_confidence"] = name_confidence

        logger.info(
            "OpenAI Vision identification: category=%s conf=%.2f name='%s' name_conf=%.2f",
            category_id, confidence,
            parsed.get("suggested_name", "")[:60], name_confidence,
        )

        return ClassificationResult(
            category_id=category_id,
            category_confidence=confidence,
            condition=condition,
            condition_confidence=cond_conf,
            suggested_name=parsed.get("suggested_name"),
            attributes=attributes,
            embedding_vector=None,
            classification_method="openai_vision",
            model_version=f"openai:{OPENAI_VISION_MODEL}",
        )

    except json.JSONDecodeError as e:
        logger.warning("OpenAI Vision response was not valid JSON: %s", e)
        return None
    except httpx.HTTPStatusError as e:
        logger.warning("OpenAI Vision API HTTP error: %s (status %d)", e, e.response.status_code)
        return None
    except Exception as e:
        logger.warning("OpenAI Vision classification failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Tier 3 — Heuristic fallback
# ---------------------------------------------------------------------------

def _detect_condition_from_text(text: str) -> tuple[str | None, float]:
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


def _classify_heuristic(image_bytes: bytes, filename: str) -> ClassificationResult:
    """
    Heuristic fallback classification using filename keywords and image metadata.
    Always returns a result (never None).
    """
    logger.info("vision_classifier: using heuristic fallback")

    text_to_match = filename.lower() if filename else ""

    # Try EXIF data for additional text clues
    exif_text = ""
    try:
        # Check for EXIF in JPEG
        if image_bytes[:2] == b"\xff\xd8":
            # Simple EXIF extraction: look for ASCII text after Exif marker
            exif_marker = image_bytes.find(b"Exif")
            if exif_marker > 0:
                # Extract a chunk of bytes and decode what we can
                chunk = image_bytes[exif_marker:exif_marker + 2048]
                # Filter to printable ASCII
                exif_text = "".join(
                    chr(b) if 32 <= b < 127 else " " for b in chunk
                )
    except Exception:
        pass

    combined_text = f"{text_to_match} {exif_text}".strip()

    # Match against heuristic patterns
    best_cat: str | None = None
    best_score = 0.0

    for cat_id, patterns in _HEURISTIC_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                # Score based on pattern specificity (longer patterns = more specific)
                score = 0.5 + min(len(pattern) / 50.0, 0.3)
                if score > best_score:
                    best_score = score
                    best_cat = cat_id

    # Check for barcode-like patterns in filename
    barcode_match = re.search(r"\b(\d{10,13})\b", text_to_match)
    barcode_info: dict[str, Any] = {}
    if barcode_match:
        barcode_info["barcode"] = barcode_match.group(1)
        # ISBN-13 prefix 978/979 suggests a book/manga
        if barcode_match.group(1).startswith(("978", "979")):
            if best_cat is None:
                best_cat = "manga"
                best_score = 0.55
            barcode_info["barcode_type"] = "isbn13"
        else:
            barcode_info["barcode_type"] = "ean13"

    # Detect condition
    condition, cond_conf = _detect_condition_from_text(combined_text)

    # If nothing matched at all, signal failure with explicit low confidence
    if best_cat is None:
        best_cat = "unknown"
        best_score = 0.0

    attributes: dict[str, Any] = {}
    if barcode_info:
        attributes["barcode"] = barcode_info
    if exif_text.strip():
        attributes["has_exif"] = True

    logger.info(
        "Heuristic classification: category=%s confidence=%.4f source=%s",
        best_cat, best_score, "filename" if not exif_text else "filename+exif",
    )

    return ClassificationResult(
        category_id=best_cat,
        category_confidence=best_score,
        condition=condition,
        condition_confidence=cond_conf,
        suggested_name=None,
        attributes=attributes,
        embedding_vector=None,
        classification_method="heuristic",
        model_version="heuristic:v1",
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def classify_image(
    image_bytes: bytes,
    filename: str = "",
) -> ClassificationResult:
    """
    Classify and identify a collectible item image using a refined 3-tier approach.

    Tier 1: CLIP via fal.ai — fast pre-filter to get a category_hint
    Tier 2: OpenAI Vision with category_hint — specific item identification
    Tier 3: Heuristic fallback (always available)

    CLIP now feeds INTO OpenAI Vision rather than being an alternative.
    This gives us fast category narrowing + precise item identification.

    Args:
        image_bytes: Raw image bytes (JPEG, PNG, or WebP)
        filename: Original filename (used for heuristic hints)

    Returns:
        ClassificationResult with category, confidence, and optional embeddings
    """
    if not image_bytes:
        logger.warning("classify_image called with empty image bytes")
        return ClassificationResult(
            category_id="funko",
            category_confidence=0.0,
            classification_method="heuristic",
            model_version="heuristic:v1",
            attributes={"error": "empty_image"},
        )

    # Tier 1: CLIP — fast pre-filter for category hint
    category_hint: str | None = None
    clip_embedding: list[float] | None = None
    clip_result = await _classify_clip(image_bytes, filename)
    if clip_result is not None and clip_result.category_confidence > 0.5:
        category_hint = clip_result.category_id
        clip_embedding = clip_result.embedding_vector
        logger.info(
            "CLIP pre-filter: hint=%s (confidence=%.2f)",
            category_hint, clip_result.category_confidence,
        )

    # Tier 2: OpenAI Vision with category hint for specific identification
    result = await _classify_openai_vision(image_bytes, filename, category_hint)
    if result is not None:
        # Preserve CLIP embedding on the final result for future vector search
        if clip_embedding:
            result.embedding_vector = clip_embedding
            if category_hint:
                result.attributes["clip_hint"] = category_hint
        return result

    # If CLIP returned a result on its own (even without OpenAI), use it
    if clip_result is not None:
        return clip_result

    # Tier 3: Heuristic (always returns a result)
    return _classify_heuristic(image_bytes, filename)
