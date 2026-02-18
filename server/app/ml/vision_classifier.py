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
    "manga", "bluray_steelbook", "anime_bluray", "anime_soundtrack", "anime_ost_vinyl",
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
    "diecast": "Diecast model car, Hot Wheels, Matchbox, die-cast vehicle, miniature car",
    "sportscards": "Sports trading card, baseball card, basketball card, Topps Panini rookie card",
    "retro_handhelds": "Retro handheld console, Game Boy, Tamagotchi, DS, PSP, retro portable gaming device",
}

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

async def _classify_clip(image_bytes: bytes, filename: str) -> ClassificationResult | None:
    """
    Use fal.ai CLIP endpoint to generate image embeddings, then compute
    cosine similarity against text embeddings of all 36 category descriptions.
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

            # 2) Get text embeddings for all category descriptions and compute similarities
            similarities: list[tuple[str, float]] = []
            for cat_id in ALL_CATEGORIES:
                desc = CATEGORY_DESCRIPTIONS.get(cat_id, cat_id)
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
                text_embedding: list[float] = text_data.get("embedding", [])
                if text_embedding:
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

_OPENAI_SYSTEM_PROMPT = """You are a collectibles classification expert for the CollectAI app.
Given an image of a collectible item, classify it into exactly ONE of these 36 categories:

pokemon, mtg, yugioh, lorcana, funko, designer_toys, anime_figures, hot_toys,
lego, gunpla, scale_models, warhammer, retro_games, manga, bluray_steelbook,
anime_bluray, anime_soundtrack, anime_ost_vinyl, kpop_merch, taylor_swift,
pop_fandom, kpop_lightsticks, disney, theme_park, ghibli, bandai_premium,
jp_magazine, jp_event, nintendo_merch, retro_pokemon, one_piece, vtuber,
keycaps, loungefly, diecast, sportscards

Also estimate the condition if visible (mint, near_mint, very_good, good, fair, poor).
Suggest a name/title for the item.

Respond ONLY with valid JSON in this exact format (no markdown, no extra text):
{
  "category_id": "pokemon",
  "category_confidence": 0.92,
  "condition": "near_mint",
  "condition_confidence": 0.75,
  "suggested_name": "Charizard Base Set Holo #4",
  "attributes": {}
}"""


async def _classify_openai_vision(image_bytes: bytes, filename: str) -> ClassificationResult | None:
    """
    Use OpenAI Vision API (GPT-4o-mini or similar) to classify the image.
    """
    if not OPENAI_API_KEY:
        return None

    logger.info("vision_classifier: attempting OpenAI Vision classification")

    try:
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        mime = "image/jpeg"
        if image_bytes[:4] == b"\x89PNG":
            mime = "image/png"
        elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
            mime = "image/webp"

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
                        {"role": "system", "content": _OPENAI_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime};base64,{b64_image}",
                                        "detail": "low",
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": f"Classify this collectible item. Filename: {filename}",
                                },
                            ],
                        },
                    ],
                    "max_tokens": 300,
                    "temperature": 0.1,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        # Parse the response
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            logger.warning("OpenAI Vision returned empty content")
            return None

        # Strip markdown code fences if present
        content = content.strip()
        if content.startswith("```"):
            # Remove ```json ... ``` wrapper
            lines = content.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            content = "\n".join(lines).strip()

        parsed = json.loads(content)

        category_id = parsed.get("category_id", "")
        if category_id not in ALL_CATEGORIES:
            logger.warning("OpenAI Vision returned unknown category: %s", category_id)
            # Try to find closest match
            cat_lower = category_id.lower().replace(" ", "_").replace("-", "_")
            if cat_lower in ALL_CATEGORIES:
                category_id = cat_lower
            else:
                return None

        confidence = float(parsed.get("category_confidence", 0.7))
        confidence = max(0.0, min(1.0, confidence))

        condition = parsed.get("condition")
        if condition and condition not in CONDITION_KEYWORDS:
            # Normalize
            condition = condition.lower().replace(" ", "_").replace("-", "_")
            if condition not in CONDITION_KEYWORDS:
                condition = None

        cond_conf = float(parsed.get("condition_confidence", 0.0))
        cond_conf = max(0.0, min(1.0, cond_conf))

        logger.info(
            "OpenAI Vision classification: category=%s confidence=%.4f condition=%s",
            category_id, confidence, condition,
        )

        return ClassificationResult(
            category_id=category_id,
            category_confidence=confidence,
            condition=condition,
            condition_confidence=cond_conf,
            suggested_name=parsed.get("suggested_name"),
            attributes=parsed.get("attributes", {}),
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
    Classify a collectible item image using the 3-tier approach.

    Tier 1: CLIP via fal.ai (if FAL_KEY is set)
    Tier 2: OpenAI Vision API (if OPENAI_API_KEY is set)
    Tier 3: Heuristic fallback (always available)

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

    # Tier 1: CLIP
    result = await _classify_clip(image_bytes, filename)
    if result is not None:
        return result

    # Tier 2: OpenAI Vision
    result = await _classify_openai_vision(image_bytes, filename)
    if result is not None:
        return result

    # Tier 3: Heuristic (always returns a result)
    return _classify_heuristic(image_bytes, filename)
