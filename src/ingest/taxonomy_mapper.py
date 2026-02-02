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
    'funko': [
        r'funko|pop!?\s*vinyl|funko\s*pop',
        r'chase\s*funko|sdcc.*funko|exclusive.*pop',
    ],
    'warhammer': [
        r'warhammer|40k|40,?000|age\s*of\s*sigmar|aos',
        r'space\s*marine|primarch|forge\s*world|games\s*workshop',
    ],
    'lorcana': [
        r'lorcana|disney.*lorcana',
    ],
    'flesh_and_blood': [
        r'flesh\s*and\s*blood|fab.*tcg|flesh.*blood',
    ],
    'gunpla': [
        r'gunpla|gundam|bandai.*model|mg\s*gundam|pg\s*gundam|rg\s*gundam',
        r'mobile\s*suit|zaku|rx-78',
    ],
    'hot_wheels': [
        r'hot\s*wheels|hotwheels|rlc.*hot\s*wheels|treasure\s*hunt',
        r'redline.*hot\s*wheels|matchbox',
    ],
    'designer_toys': [
        r'kaws|bearbrick|be@rbrick|medicom',
        r'superplastic|janky|designer\s*toy|art\s*toy',
    ],
    'sports_cards': [
        r'topps|panini|nba.*card|nfl.*card|mlb.*card',
        r'rookie\s*card|psa\s*\d+.*\b(baseball|basketball|football)\b',
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
