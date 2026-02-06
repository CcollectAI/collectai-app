"""
Taxonomy Mapper for ingest pipeline.

Maps raw category strings to canonical category_id/subtype_id.
Stores taxonomy_version on every mapping for safe remapping later.
"""

import re
from typing import Tuple, Optional
from .types import RawObservation, TAXONOMY_VERSION

# Category mapping rules (v1.0)
# Add new categories here; when taxonomy changes, increment TAXONOMY_VERSION in types.py
CATEGORY_PATTERNS = {
    # --- TCGs ---
    'pokemon': [
        r'pokemon|pikachu|charizard|pokémon|psa\s*\d+.*pokemon|cgc.*pokemon',
        r'tcg.*pokemon|pokemon.*tcg|pokémon.*card',
        r'base\s*set|jungle|fossil|team\s*rocket|neo\s*genesis',
        r'vmax|vstar|ex\s*card|gx\s*card|full\s*art',
    ],
    'mtg': [
        r'magic.*gathering|mtg|black\s*lotus|mox\s*\w+',
        r'reserved\s*list|dual\s*land|commander|edh',
        r'alpha|beta|unlimited.*magic|revised.*magic',
    ],
    'yugioh': [
        r'yu-?gi-?oh|yugioh|ygo|konami.*card',
        r'blue.?eyes|dark\s*magician|exodia|starlight\s*rare',
    ],
    'lorcana': [
        r'lorcana|disney.*lorcana',
    ],

    # --- Toys / Figures ---
    'funko': [
        r'funko|pop!?\s*vinyl|funko\s*pop',
        r'chase\s*funko|sdcc.*funko|exclusive.*pop',
    ],
    'designer_toys': [
        r'kaws|bearbrick|be@rbrick|medicom',
        r'superplastic|janky|designer\s*toy|art\s*toy|pop\s*mart',
    ],
    'anime_figures': [
        r'nendoroid|figma|scale\s*figure|garage\s*kit',
        r'good\s*smile|kotobukiya|alter|max\s*factory',
        r'anime\s*figure|anime\s*statue|prize\s*figure',
    ],
    'hot_toys': [
        r'hot\s*toys|mms\d+|sideshow|premium\s*format',
        r'sixth\s*scale|1/6\s*scale.*figure',
    ],

    # --- Building / Models ---
    'lego': [
        r'\blego\b|lego\s*set|lego\s*\d{4,5}',
        r'minifig|lepin',  # lepin = bootleg but signals LEGO interest
    ],
    'gunpla': [
        r'gunpla|gundam|bandai.*model|mg\s*gundam|pg\s*gundam|rg\s*gundam',
        r'mobile\s*suit|zaku|rx-78',
    ],
    'scale_models': [
        r'tamiya|hasegawa|revell|airfix|trumpeter|academy',
        r'scale\s*model|model\s*kit|plastic\s*model',
        r'1/72|1/48|1/35|1/350',
    ],
    'warhammer': [
        r'warhammer|40k|40,?000|age\s*of\s*sigmar|aos',
        r'space\s*marine|primarch|forge\s*world|games\s*workshop',
        r'kill\s*team|necromunda|blood\s*bowl',
    ],

    # --- Gaming ---
    'retro_games': [
        r'nes\b|snes\b|n64\b|gamecube|game\s*boy|gba\b',
        r'sega\s*(genesis|saturn|dreamcast)|neo\s*geo',
        r'retro\s*game|retro\s*console|cartridge',
        r'ps1\b|playstation\s*1|psp\b',
    ],

    # --- Media ---
    'manga': [
        r'\bmanga\b|manga\s*vol|out\s*of\s*print.*manga',
        r'viz\s*media|kodansha|dark\s*horse.*manga|tokyopop',
        r'tankoubon|tankobon',
    ],
    'bluray_steelbook': [
        r'steelbook|4k\s*uhd|criterion|arrow\s*video',
        r'boutique\s*blu-?ray|shout\s*factory|vinegar\s*syndrome',
        r'limited\s*edition.*blu-?ray|collector.*blu-?ray',
    ],
    'anime_bluray': [
        r'anime.*blu-?ray|anime.*box\s*set|aniplex.*blu',
        r'jp\s*blu-?ray.*anime|limited.*anime.*bd',
    ],
    'anime_soundtrack': [
        r'anime\s*ost|anime\s*soundtrack|anime\s*cd',
        r'original\s*sound\s*track.*anime',
    ],
    'anime_ost_vinyl': [
        r'anime.*vinyl|ost.*vinyl|soundtrack.*vinyl',
        r'tiger\s*lab|anime\s*lp|anime.*pressing',
    ],

    # --- Music / Fandom ---
    'kpop_merch': [
        r'bts\b|blackpink|stray\s*kids|twice|ateez|enhypen',
        r'k-?pop.*photocard|k-?pop.*album|fansign|weverse',
        r'hybe|sm\s*entertainment|jyp|yg\s*entertainment',
    ],
    'taylor_swift': [
        r'taylor\s*swift|swiftie|eras\s*tour',
        r'midnights.*vinyl|folklore.*vinyl|evermore.*vinyl',
    ],
    'pop_fandom': [
        r'ariana\s*grande|olivia\s*rodrigo|billie\s*eilish',
        r'harry\s*styles|dua\s*lipa|doja\s*cat',
        r'tour\s*merch|concert\s*exclusive',
    ],
    'kpop_lightsticks': [
        r'lightstick|light\s*stick|k-?pop.*stick',
        r'army\s*bomb|bong.*official',
    ],

    # --- Disney / Theme Parks ---
    'disney': [
        r'disney\s*pin|disney\s*collect|disney\s*limited',
        r'disney\s*ears|disney\s*ornament|disney\s*figure',
        r'walt\s*disney|disneyana',
    ],
    'theme_park': [
        r'theme\s*park.*exclusive|park\s*exclusive',
        r'tokyo\s*disney|disneyland|universal\s*studios',
        r'popcorn\s*bucket|park\s*merch',
    ],
    'ghibli': [
        r'ghibli|studio\s*ghibli|totoro|spirited\s*away',
        r'miyazaki|kiki.*delivery|mononoke',
        r'donguri\s*sora|benelic',
    ],

    # --- Japan Exclusives ---
    'bandai_premium': [
        r'p-?bandai|bandai\s*premium|tamashii\s*exclusive',
        r's\.?h\.?\s*figuarts|robot\s*spirits|chogokin',
    ],
    'jp_magazine': [
        r'dengeki|newtype|animedia|famitsu',
        r'magazine\s*insert|magazine\s*exclusive|furoku',
    ],
    'jp_event': [
        r'comiket|wonder\s*festival|wonfes|anime\s*japan',
        r'event\s*exclusive.*japan|comic\s*market',
    ],

    # --- Nintendo / Pokemon Merch ---
    'nintendo_merch': [
        r'pokemon\s*center|nintendo\s*store|amiibo',
        r'pokemon\s*plush|nintendo\s*merch',
        r'pokemon\s*figure|pikachu\s*plush',
    ],
    'retro_pokemon': [
        r'pokedex\s*toy|pokemon.*game\s*boy|pokemon.*accessory',
        r'tomy.*pokemon|hasbro.*pokemon|tiger.*pokemon',
    ],

    # --- IP-Specific ---
    'one_piece': [
        r'one\s*piece.*figure|one\s*piece.*card|portrait.*pirates',
        r'luffy|zoro|one\s*piece.*collect|megahouse.*one\s*piece',
        r'ichiban\s*kuji.*one\s*piece|figuarts.*one\s*piece',
    ],
    'vtuber': [
        r'vtuber|hololive|nijisanji|gawr\s*gura|pekora',
        r'virtual\s*youtuber|vtuber\s*merch|streamer\s*merch',
    ],

    # --- Niche ---
    'keycaps': [
        r'artisan\s*keycap|keycap|mechanical\s*keyboard.*cap',
        r'gmk|epbt|cherry\s*profile|sa\s*profile',
    ],
    'loungefly': [
        r'loungefly|loungefly.*backpack|loungefly.*wallet',
    ],

    # --- Legacy ---
    'diecast': [
        r'hot\s*wheels|hotwheels|rlc.*hot\s*wheels|treasure\s*hunt',
        r'redline.*hot\s*wheels|matchbox|diecast.*car',
        r'autoart|kyosho|minichamps',
    ],
    'sportscards': [
        r'topps|panini|nba.*card|nfl.*card|mlb.*card',
        r'rookie\s*card|psa\s*\d+.*\b(baseball|basketball|football)\b',
        r'prizm|optic|mosaic|select.*card',
    ],
}

# Subtype patterns (within categories)
SUBTYPE_PATTERNS = {
    'pokemon': {
        'graded': r'psa|cgc|bgs|grade[d]?\s*\d+',
        'sealed': r'sealed|booster\s*box|etb|elite\s*trainer',
        'raw': r'raw|ungraded|nm|near\s*mint|lp|played',
    },
    'mtg': {
        'graded': r'psa|cgc|bgs|grade[d]?\s*\d+',
        'sealed': r'sealed|booster\s*box|draft\s*box',
        'raw': r'raw|nm|near\s*mint|lp|played',
    },
}


def map_category(text: str) -> Tuple[Optional[str], float, str]:
    """
    Map raw text to category_id.

    Args:
        text: Raw category/title text to match

    Returns:
        Tuple of (category_id, confidence, rationale)
    """
    if not text:
        return None, 0.0, "empty input"

    text_lower = text.lower()

    for category_id, patterns in CATEGORY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                confidence = 0.85  # Base confidence for pattern match
                rationale = f"matched pattern '{pattern}' for {category_id}"
                return category_id, confidence, rationale

    return None, 0.0, "no pattern matched"


def map_subtype(text: str, category_id: str) -> Tuple[Optional[str], float]:
    """
    Map raw text to subtype_id within a category.

    Args:
        text: Raw text to match
        category_id: The category to look up subtypes for

    Returns:
        Tuple of (subtype_id, confidence)
    """
    if not text or not category_id:
        return None, 0.0

    text_lower = text.lower()
    subtype_patterns = SUBTYPE_PATTERNS.get(category_id, {})

    for subtype_id, pattern in subtype_patterns.items():
        if re.search(pattern, text_lower, re.IGNORECASE):
            return subtype_id, 0.8

    return None, 0.0


def apply_taxonomy_mapping(observation: RawObservation) -> RawObservation:
    """
    Apply taxonomy mapping to a RawObservation.
    Modifies in place and returns the observation.

    Args:
        observation: The observation to map

    Returns:
        The same observation with taxonomy fields filled
    """
    # Combine title and category_raw for matching
    match_text = f"{observation.title} {observation.category_raw}"

    # Map category
    category_id, cat_confidence, rationale = map_category(match_text)
    observation.category_id = category_id
    observation.mapping_confidence = cat_confidence
    observation.mapping_rationale = rationale
    observation.taxonomy_version = TAXONOMY_VERSION

    # Map subtype if category was found
    if category_id:
        subtype_id, sub_confidence = map_subtype(match_text, category_id)
        observation.subtype_id = subtype_id
        # Adjust confidence if subtype was found
        if subtype_id:
            observation.mapping_confidence = (cat_confidence + sub_confidence) / 2

    return observation


def batch_apply_taxonomy(observations: list[RawObservation]) -> list[RawObservation]:
    """
    Apply taxonomy mapping to a batch of observations.

    Args:
        observations: List of observations to map

    Returns:
        List of mapped observations (same objects, modified in place)
    """
    for obs in observations:
        apply_taxonomy_mapping(obs)
    return observations
