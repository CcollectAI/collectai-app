"""
QuickScan proxy router.

Delegates to the advanced QuickScan endpoints, providing a simplified
interface for the mobile app's QuickScan flow.
"""

from __future__ import annotations

import os
import re as _re
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter(tags=["quickscan"])


# ---- Friendly category map ----
_FRIENDLY_CATEGORY_MAP = {
    "pokemon": "Pokémon", "mtg": "Magic: The Gathering", "yugioh": "Yu-Gi-Oh!",
    "lorcana": "Disney Lorcana", "funko": "Funko Pop", "lego": "LEGO",
    "warhammer": "Warhammer", "retro_games": "Retro Games", "manga": "Manga",
    "sportscards": "Sports Cards", "designer_toys": "Designer & Art Toys",
    "anime_figures": "Anime Figures", "hot_toys": "Hot Toys",
    "gunpla": "Gunpla & Model Kits", "scale_models": "Scale Models",
    "keycaps": "Artisan Keycaps", "bluray_steelbook": "Blu-ray Steelbooks",
    "anime_bluray": "Anime Blu-ray", "nintendo_merch": "Nintendo Merch",
    "one_piece": "One Piece", "retro_pokemon": "Retro Pokémon",
    "diecast": "Diecast & Hot Wheels", "kpop_merch": "K-pop Merch",
    "taylor_swift": "Taylor Swift", "pop_fandom": "Pop Fandom",
    "kpop_lightsticks": "K-pop Lightsticks", "anime_soundtrack": "Anime Soundtrack",
    "anime_ost_vinyl": "Anime OST Vinyl", "disney": "Disney",
    "theme_park": "Theme Park", "ghibli": "Studio Ghibli",
    "bandai_premium": "Bandai Premium", "jp_magazine": "JP Magazines",
    "jp_event": "JP Event Exclusives", "vtuber": "VTuber",
    "loungefly": "Loungefly",
}


# ---- Request / Response models ----

class QuickScanRequest(BaseModel):
    mode: Optional[str] = None
    category_hint: Optional[str] = None
    image_id: Optional[str] = None
    image_ids: Optional[List[str]] = None


class QuickScanUploadResponse(BaseModel):
    image_id: str


# ---- Endpoints ----

@router.post("/quickscan")
async def quickscan_proxy(payload: QuickScanRequest):
    """
    Proxy QuickScan endpoint that delegates to quickscan-advanced.
    If an image_id / image_ids are provided, we use the batch demo endpoint.
    Otherwise we fall back to the single demo.
    """
    from app.features.quickscan_advanced_router import (
        quickscan_single_demo,
        quickscan_batch_demo,
        BatchQuickScanRequest,
        QuickScanResult,
        BatchQuickScanResponse,
    )

    # Decide which advanced endpoint to call
    advanced_result: QuickScanResult
    image_ids: list[str] = []

    if payload.image_id:
        image_ids.append(payload.image_id)
    if payload.image_ids:
        image_ids.extend(payload.image_ids)

    # Deduplicate and drop empties
    deduped_ids: list[str] = []
    seen = set()
    for iid in image_ids:
        if not iid:
            continue
        if iid in seen:
            continue
        seen.add(iid)
        deduped_ids.append(iid)

    if deduped_ids:
        batch_req = BatchQuickScanRequest(image_ids=deduped_ids)
        batch_resp: BatchQuickScanResponse = await quickscan_batch_demo(batch_req)
        if batch_resp.results:
            advanced_result = batch_resp.results[0]
        else:
            advanced_result = await quickscan_single_demo()
    else:
        advanced_result = await quickscan_single_demo()

    attrs = advanced_result.attributes
    pred = advanced_result.prediction

    # Map category codes (mtg/funko/etc.) to friendly labels
    raw_cat = (attrs.category or "").lower()
    friendly_category = _FRIENDLY_CATEGORY_MAP.get(raw_cat, attrs.category)

    # Build rich notes string for the Add screen
    notes_parts = []
    if attrs.condition_guess:
        notes_parts.append(f"Condition guess: {attrs.condition_guess}")
    if attrs.edition_guess:
        notes_parts.append(f"Edition guess: {attrs.edition_guess}")
    if attrs.rarity_score is not None:
        notes_parts.append(f"Rarity score: {attrs.rarity_score:.2f}")
    notes_parts.append(f"Model confidence: {pred.confidence:.2f}")
    base_notes = " · ".join(notes_parts)
    final_notes = f"QuickScan: {base_notes}"

    return {
        "name": pred.name,
        "collection_name": attrs.edition_guess or "Unknown edition",
        "estimated_value": pred.estimated_mid,
        "notes": final_notes,
        "category": friendly_category or attrs.category,
    }


@router.post("/quickscan/upload-image", response_model=QuickScanUploadResponse)
async def quickscan_upload_image(file: UploadFile = File(...)):
    """
    Accept a user image for QuickScan, store it, and return an image_id
    that can be passed into /quickscan. Later, the advanced model can
    look up the image by this ID.
    """
    image_id = f"quickscan-{uuid4().hex}"
    tmp_dir = Path(os.getenv("QUICKSCAN_TMP_DIR", "/tmp"))
    tmp_dir.mkdir(parents=True, exist_ok=True)

    raw_name = os.path.basename(file.filename or "upload.jpg")
    safe_name = _re.sub(r"[^\w.\-]", "_", raw_name)[:100]
    out_path = tmp_dir / f"{image_id}_{safe_name}"

    contents = await file.read()
    if len(contents) > 20 * 1024 * 1024:  # 20 MB max for images
        raise HTTPException(status_code=413, detail="Image too large (max 20 MB)")
    out_path.write_bytes(contents)

    return {"image_id": image_id}
