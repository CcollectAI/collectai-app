"""
Taxonomy Mapper for ingest pipeline.

Maps raw category strings to canonical category_id/subtype_id.
Stores taxonomy_version on every mapping for safe remapping later.

Supports loading patterns from the taxonomy_registry table via
load_from_registry(), with fallback to hardcoded patterns.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from .types import RawObservation, TAXONOMY_VERSION

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registry cache — populated by load_from_registry(), used by map_category()
# ---------------------------------------------------------------------------
_registry_cache: dict[str, Any] | None = None
_registry_version: str | None = None

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
    # Dungeons & Dragons, added 2026-08-14 with the category itself. Without a
    # pattern here the ingest pipeline can never assign `dnd`, so the category
    # page would sit permanently empty — a category reachable from nowhere.
    #
    # Deliberately NOT bare `dice`, `d20` or `polyhedral`: those appear in
    # Warhammer, board-game and generic-accessory listings, and a pattern that
    # steals another category's items is worse than one that misses a few
    # (learning_keyword_filters_need_per_category_false_positive_audit). Every
    # alternative below names D&D or a D&D-specific product line.
    'dnd': [
        r'dungeons\s*(&|and)\s*dragons|\bd&d\b|\bdnd\b',
        r'players\s*handbook|dungeon\s*master.?s?\s*guide|monster\s*manual',
        r'\btsr\b.*(d&d|dungeons)|(d&d|dungeons).*\btsr\b',
        r'nolzur.?s|icons\s*of\s*the\s*realms',
    ],
    'warhammer': [
        r'warhammer|40k|40,?000|age\s*of\s*sigmar|aos',
        r'space\s*marine|primarch|forge\s*world|games\s*workshop',
        r'kill\s*team|necromunda|blood\s*bowl',
        r'black\s*library|horus\s*heresy|codex\s*\w+|battletome',
        r'gaunt.?s\s*ghosts|eisenhorn|ciaphas\s*cain|ravenor',
        r'imperial\s*armou?r|liber\s*chaotica',
    ],

    # --- Gaming ---
    'retro_games': [
        r'nes\b|snes\b|n64\b|gamecube|game\s*boy|gba\b',
        r'sega\s*(genesis|saturn|dreamcast)|neo\s*geo',
        r'retro\s*game|retro\s*console|cartridge',
        r'ps1\b|playstation\s*1|psp\b',
    ],
    'retro_handhelds': [
        r'game\s*boy\s*(color|advance|sp|micro|pocket)',
        r'\bds\s*lite\b|nintendo\s*ds|3ds\b|new\s*3ds',
        r'\bpsp\b|ps\s*vita|playstation\s*portable',
        r'game\s*&?\s*watch|tamagotchi|neo\s*geo\s*pocket',
        r'atari\s*lynx|sega\s*game\s*gear|wonderswan',
        r'retro\s*handheld|portable\s*console|modded.*handheld',
    ],

    # --- Media ---
    'manga': [
        r'\bmanga\b|manga\s*vol|out\s*of\s*print.*manga',
        r'viz\s*media|kodansha|dark\s*horse.*manga|tokyopop',
        r'tankoubon|tankobon',
    ],
    'comic_books': [
        r'\bcomic\s*book\b|graphic\s*novel|comic\s*issue',
        r'\bcgc\b.*\d|cbcs\s*\d|graded\s*comic',
        r'marvel\s*comics|dc\s*comics|image\s*comics|dark\s*horse\s*comics',
        r'omnibus.*comic|absolute\s*edition|variant\s*cover',
        r'key\s*issue|first\s*appearance|first\s*print.*comic',
        r'\bspawn\b.*#|\bsaga\b.*#|walking\s*dead.*#',
        r'spider-?man.*#|batman.*#|superman.*#|x-?men.*#',
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
        r'seventeen\b|nct\b|aespa|le\s*sserafim|ive\b|itzy\b',
        r'red\s*velvet|got7|txt\b|tomorrow\s*x\s*together',
        r'g\W?i-?dle|nmixx|dreamcatcher|mamamoo|shinee|bigbang',
        r'super\s*junior|2ne1|exo\b|newjeans|gi-?dle',
        r'k-?pop.*photocard|k-?pop.*album|fansign|weverse',
        r'hybe|sm\s*entertainment|jyp|yg\s*entertainment|starship',
        r'ktown4u|yes24.*kpop|aladin.*kpop|cokodive',
    ],
    'taylor_swift': [
        r'taylor\s*swift|swiftie|eras\s*tour',
        r'midnights.*vinyl|folklore.*vinyl|evermore.*vinyl',
    ],
    'pop_fandom': [
        r'ariana\s*grande|olivia\s*rodrigo|billie\s*eilish',
        r'harry\s*styles|dua\s*lipa|doja\s*cat',
        r'stray\s*kids|skz\b|straykids|felix\s*lee|hyunjin\s*hwang',
        r'tour\s*merch|concert\s*exclusive|fan\s*meeting',
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

    # --- Lifestyle ---
    'vinyl_records': [
        r'\bvinyl\b|vinyl\s*record|\blp\b.*record|vinyl\s*press',
        r'discogs|vinyl\s*me\s*please|vmp\b|mondo\s*vinyl',
        r'colored\s*vinyl|splatter\s*vinyl|picture\s*disc|limited\s*press',
        r'first\s*press|1st\s*press|original\s*press|audiophile',
        r'gatefold|180\s*g|half.?speed\s*master',
    ],
    'sneakers': [
        r'\bjordan\s*\d|air\s*jordan|retro\s*jordan',
        r'\bnike\s*dunk|nike\s*sb|air\s*max|air\s*force\s*1',
        r'\byeezy\b|adidas\s*yeezy|yeezy\s*(boost|slide|foam)',
        r'new\s*balance\s*\d{3,4}|nb\s*\d{3,4}',
        r'deadstock|vnds\b|\bds\b.*sneaker|stockx|goat\.com',
        r'travis\s*scott.*shoe|off.?white.*nike|fragment.*jordan',
        r'sneaker\s*collect|sneakerhead|grail.*shoe|hyped\s*sneaker',
    ],
    # Added 2026-08-11 alongside the `jewellery` category in
    # src/data/categories.ts. Brand-led, like `watches` — a piece is almost
    # always named by house and line ("Cartier Love", "Alhambra"), rarely by a
    # reference number, which is why jewellery rows are name-only.
    #
    # Ordered BEFORE 'watches' deliberately: Cartier and Bulgari make both, and
    # a bare brand name would otherwise classify a Love bracelet as a watch.
    # The watch patterns are model-anchored (Santos, Tank, Serpenti Tubogas), so
    # a real watch still matches its own rule.
    'jewellery': [
        # BRAND-AND-LINE ANCHORED ONLY. Measured against 4,000 real catalogue
        # titles on 2026-08-11: a first draft that also matched the bare nouns
        # (necklace|pendant|bracelet|bangle|earrings|brooch), bare `swarovski`
        # and `18k...gold` stole **213 rows** from eight other categories —
        # Yu-Gi-Oh's "Pendulum Pendant" and MTG's "Null Brooch" (both CARDS),
        # Digimon's "Vital Bracelet DIM Card" (a device), "Swarovski Disney
        # Moana Crystal Figurine" (a figurine), plus Ghibli and Taylor Swift
        # merch bracelets.
        #
        # Same lesson as the accessory filter in docs/TAXONOMY.md §146: naming a
        # product TYPE is not sufficient, because other categories sell objects
        # named after it. A house plus its line is the only signal that is
        # actually about jewellery. RE-MEASURE before widening this.
        # `tiffany` and `etoile` are BOTH anchored, not bare. Bare `tiffany`
        # matched the Funko and action figure "Tiffany (Bride of Chucky)" — the
        # doll character — and bare `etoile` matched the Yu-Gi-Oh card
        # "Flowering Etoile the Melodious Magnificat". Both are the
        # bare-term-hits-a-real-card class from docs/TAXONOMY.md §180.
        r'tiffany\s*&\s*co|\btiffany\b[\w\s]{0,24}?(ring|necklace|bracelet|bangle|pendant|earrings|charm|band|setting|knot)\b',
        r'(tiffany|\bt&co\b)\s*[\w\s]{0,12}?\betoile\b|\betoile\b\s*(band|ring|bracelet|necklace)\b',
        r'\bt\s*smile\b|hardwear|elsa\s*peretti|paloma\s*picasso',
        r'cartier\s*(love|juste\s*un\s*clou|trinity|clash|panth[eè]re\s*ring)',
        r'van\s*cleef|alhambra|frivole|perl[eé]e',
        r'bulgari\s*(b\.?zero1|serpenti\s*viper|divas|monete)|bvlgari\s*(b\.?zero1|serpenti\s*viper)',
        # DESIGNER / HIGH-ASP MAISONS ONLY (2026-08-11, Merle's call). Pandora and
        # Swarovski were removed: they are mass-market, and bare `swarovski` was
        # also stealing "Swarovski Disney Moana Crystal Figurine" from disney.
        # Niche and independent houses come later, deliberately.
        r'\bde\s*beers\b|forevermark',
        r'\bmessika\b|move\s*(romane|uno|classique|noa)',
        # Pure-jewellery houses: bare brand is safe.
        r'\b(boucheron|chaumet|mikimoto|buccellati|pomellato|repossi|fred\s*paris|dinh\s*van|david\s*yurman)\b',
        # DUAL MAKERS — anchored to jewellery lines, never bare. Piaget, Chopard,
        # Graff and Harry Winston all make watches too, and bare `piaget` stole
        # "Piaget Altiplano 40mm Rose Gold (G0A38131)" from watches (measured
        # 2026-08-11). Cartier and Bulgari above are line-anchored for the same
        # reason.
        r'piaget\s*(possession|rose\s*(ring|pendant|bracelet)|limelight\s*(necklace|earrings))',
        r'chopard\s*(happy\s*(diamonds|hearts|spirit)|ice\s*cube|my\s*happy\s*hearts)',
        r'(harry\s*winston|graff)[\w\s-]{0,24}?(ring|necklace|pendant|bracelet|earrings|studs|brooch)\b',
        r'\b(engagement\s*ring|eternity\s*band|signet\s*ring|cocktail\s*ring)\b',
        # FASHION HOUSES — line-anchored, NEVER bare. Chanel, Dior, Hermès,
        # Louis Vuitton and Gucci sell bags, clothing and watches; a bare brand
        # name would strip those categories wholesale. Same rule that keeps
        # Cartier, Bulgari, Piaget and Chopard from stealing watches.
        r'chanel\s*(coco\s*crush|cam[eé]lia|ultra|comète|comete|1932)',
        r'dior\s*(rose\s*des\s*vents|bois\s*de\s*rose|mimirose|rose\s*c[eé]leste|gem\s*dior)',
        r'herm[eè]s\s*(cha[iî]ne\s*d.?ancre|clic\s*h|kelly\s*(pendant|bracelet|ring)|collier\s*de\s*chien|finesse)',
        r'louis\s*vuitton\s*(empreinte|idylle\s*blossom|color\s*blossom|b\.?blossom|lv\s*volt)',
        r'gucci\s*(link\s*to\s*love|ouroboros|gg\s*running|icon\s*(ring|bracelet)|flora\s*(ring|necklace))',
        # Pure-jewellery houses added 2026-08-11: bare brand is safe.
        r'\b(tasaki|georg\s*jensen|damiani|vhernier|marina\s*b|verdura|seaman\s*schepps|belperron)\b',
        r'\b(marco\s*bicego|roberto\s*coin|foundrae|spinelli\s*kilcollin|anita\s*ko|suzanne\s*kalan|sydney\s*evan)\b',
        r'\b(boodles|garrard|asprey|ole\s*lynggaard|asprey\s*london)\b',
        r'\bfaberg[eé]\b',
    ],
    'watches': [
        r'\brolex\b|submariner|daytona|datejust|gmt.?master',
        r'\bomega\b|speedmaster|seamaster|moonwatch',
        r'\bseiko\b|skx\d{3}|presage|grand\s*seiko',
        r'\btudor\b|black\s*bay|pelagos',
        r'\bpatek\b|patek\s*philippe|nautilus|calatrava',
        r'audemars\s*piguet|royal\s*oak',
        r'\bcasio\b|g.?shock|ga-?\d{3,4}|dw-?\d{4}',
        r'chrono24|hodinkee|watch\s*collect|horology',
        r'automatic\s*watch|chronograph|diver.?s?\s*watch',
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
