"""
Intake Agent Router.

Exposes the IntakeAgent as HTTP endpoints for the unified Snap-to-Logged flow.

Endpoints:
  POST /intake/process       -- full intake (image + barcode + hints)
  POST /intake/barcode-only  -- barcode-only intake (no image)
  POST /intake/image-only    -- image-only intake (no barcode)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field

from app.agents.intake_agent import IntakeResult, process_intake, process_url_import
from app.auth import get_current_user_id
from app.errors import error_response
from app.config import INTAKE_MAX_IMAGE_BYTES as MAX_IMAGE_BYTES
from app.rate_limit import per_user_rate_limit
from app.ssrf import validate_url

logger = logging.getLogger(__name__)

# Per-user: 30 requests per minute across all intake endpoints
_intake_user_limit = per_user_rate_limit(30, scope="intake")

router = APIRouter(
    prefix="/intake",
    tags=["Intake"],
    dependencies=[Depends(get_current_user_id), Depends(_intake_user_limit)],
)

# Allowed MIME types for vision classification
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------

class PriceBandResponse(BaseModel):
    q10: float
    q50: float
    q90: float
    confidence: float
    currency: str = "EUR"


class SuggestedCorrectionResponse(BaseModel):
    from_category: str
    to_category: str
    frequency: int
    user_count: int


class FieldConfidence(BaseModel):
    """Per-field confidence scores from the vision + catalog pipeline."""
    category: float = 0.0
    name: float = 0.0
    condition: float = 0.0


class CatalogMatchResponse(BaseModel):
    """A catalog item that matched the scanned item."""
    catalog_item_id: Optional[str] = None
    item_key: Optional[str] = None
    title: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    rarity: Optional[str] = None
    set_code: Optional[str] = None
    image_url: Optional[str] = None
    match_score: float = 0.0
    match_reason: Optional[str] = None


class SocialProofRecentSold(BaseModel):
    title: Optional[str] = None
    price: Optional[float] = None
    currency: str = "EUR"
    sold_at: Optional[str] = None
    source: Optional[str] = None


class ScarcityInfo(BaseModel):
    listing_count: int = 0
    supply_trend: str = "stable"
    scarcity_score: float = 0.0


class SocialProofResponse(BaseModel):
    collector_count: int = 0
    is_trending: bool = False
    trend_rank: Optional[int] = None
    recent_sold: list[SocialProofRecentSold] = Field(default_factory=list)
    scarcity: Optional[ScarcityInfo] = None


class DuplicateInfoResponse(BaseModel):
    owned_count: int = 0
    owned_item_ids: list[str] = Field(default_factory=list)
    is_variant: bool = False
    variant_of: Optional[str] = None
    set_completion: Optional[dict[str, Any]] = None


class DefectAnnotationResponse(BaseModel):
    type: Optional[str] = None
    severity: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None


class SuggestedGradeResponse(BaseModel):
    scale: Optional[str] = None
    grade_value: Optional[str] = None
    reasoning: Optional[str] = None


class IntakeResultResponse(BaseModel):
    """JSON-serialisable response for an intake result."""

    name: Optional[str] = None
    category_id: Optional[str] = None
    category_confidence: float = 0.0
    subtype_id: Optional[str] = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    identification_method: str = "manual"
    barcode: Optional[str] = None
    barcode_type: Optional[str] = None
    taxonomy_version: str = "v1.0"
    taxonomy_confidence: float = 0.0
    suggested_corrections: list[SuggestedCorrectionResponse] = Field(default_factory=list)
    estimated_price: Optional[float] = None
    price_source: Optional[str] = None
    price_band: Optional[PriceBandResponse] = None
    image_url: Optional[str] = None
    catalog_miss: bool = False
    catalog_match_id: Optional[str] = None
    catalog_match_key: Optional[str] = None
    alternatives: list[CatalogMatchResponse] = Field(default_factory=list)
    field_confidence: Optional[FieldConfidence] = None
    chain_of_thought: Optional[str] = None
    rationale: list[str] = Field(default_factory=list)
    scan_session_id: Optional[str] = None
    social_proof: Optional[SocialProofResponse] = None
    duplicate_info: Optional[DuplicateInfoResponse] = None
    defect_annotations: list[DefectAnnotationResponse] = Field(default_factory=list)
    suggested_grade: Optional[SuggestedGradeResponse] = None


class BoundingBoxResponse(BaseModel):
    x: float = 0.0
    y: float = 0.0
    w: float = 1.0
    h: float = 1.0


class DetectedItemResponse(BaseModel):
    item_index: int = 0
    bounding_box: BoundingBoxResponse = Field(default_factory=BoundingBoxResponse)
    category_hint: Optional[str] = None
    suggested_name: Optional[str] = None
    confidence: float = 0.0


class MultiDetectResponse(BaseModel):
    items: list[DetectedItemResponse] = Field(default_factory=list)
    total_detected: int = 0


class BarcodeOnlyRequest(BaseModel):
    barcode: str = Field(..., min_length=1, max_length=50)
    barcode_type: Optional[str] = Field(None, max_length=20)
    category: Optional[str] = Field(None, max_length=64)
    name: Optional[str] = Field(None, max_length=500)
    condition: Optional[str] = Field(None, max_length=30)


class UrlImportRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)
    category: Optional[str] = Field(None, max_length=64)
    name: Optional[str] = Field(None, max_length=500)
    condition: Optional[str] = Field(None, max_length=30)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _intake_to_response(result: IntakeResult) -> IntakeResultResponse:
    """Convert internal IntakeResult to API response model."""
    price_band = None
    if result.price_band:
        try:
            price_band = PriceBandResponse(
                q10=result.price_band.get("q10", 0),
                q50=result.price_band.get("q50", 0),
                q90=result.price_band.get("q90", 0),
                confidence=result.price_band.get("confidence", 0),
                currency=result.price_band.get("currency", "EUR"),
            )
        except Exception:
            logger.debug("Failed to parse price band from intake result")

    corrections = []
    for c in result.suggested_corrections:
        try:
            corrections.append(SuggestedCorrectionResponse(
                from_category=c.get("from_category", ""),
                to_category=c.get("to_category", ""),
                frequency=c.get("frequency", 0),
                user_count=c.get("user_count", 0),
            ))
        except Exception:
            pass

    # Build alternatives list
    alternatives: list[CatalogMatchResponse] = []
    for alt in (result.alternatives or []):
        try:
            alternatives.append(CatalogMatchResponse(
                catalog_item_id=alt.get("catalog_item_id"),
                item_key=alt.get("item_key"),
                title=alt.get("title"),
                category=alt.get("category"),
                brand=alt.get("brand"),
                rarity=alt.get("rarity"),
                set_code=alt.get("set_code"),
                image_url=alt.get("image_url"),
                match_score=alt.get("match_score", 0),
                match_reason=alt.get("match_reason"),
            ))
        except Exception:
            pass

    # Build field confidence
    field_confidence = None
    if result.field_confidence:
        try:
            field_confidence = FieldConfidence(
                category=result.field_confidence.get("category", 0),
                name=result.field_confidence.get("name", 0),
                condition=result.field_confidence.get("condition", 0),
            )
        except Exception:
            pass

    # Build social proof response
    social_proof = None
    if result.social_proof:
        try:
            recent_sold = []
            for s in result.social_proof.get("recent_sold", []):
                recent_sold.append(SocialProofRecentSold(
                    title=s.get("title"),
                    price=s.get("price"),
                    currency=s.get("currency", "EUR"),
                    sold_at=s.get("sold_at"),
                    source=s.get("source"),
                ))
            scarcity_data = result.social_proof.get("scarcity")
            scarcity = None
            if scarcity_data:
                scarcity = ScarcityInfo(
                    listing_count=scarcity_data.get("listing_count", 0),
                    supply_trend=scarcity_data.get("supply_trend", "stable"),
                    scarcity_score=scarcity_data.get("scarcity_score", 0.0),
                )
            social_proof = SocialProofResponse(
                collector_count=result.social_proof.get("collector_count", 0),
                is_trending=result.social_proof.get("is_trending", False),
                trend_rank=result.social_proof.get("trend_rank"),
                recent_sold=recent_sold,
                scarcity=scarcity,
            )
        except Exception:
            logger.debug("Failed to build social proof response")

    # Build duplicate info response
    duplicate_info = None
    if result.duplicate_info:
        try:
            duplicate_info = DuplicateInfoResponse(
                owned_count=result.duplicate_info.get("owned_count", 0),
                owned_item_ids=result.duplicate_info.get("owned_item_ids", []),
                is_variant=result.duplicate_info.get("is_variant", False),
                variant_of=result.duplicate_info.get("variant_of"),
                set_completion=result.duplicate_info.get("set_completion"),
            )
        except Exception:
            logger.debug("Failed to build duplicate info response")

    # Build defect annotations
    defect_annotations = []
    for d in (result.defect_annotations or []):
        try:
            defect_annotations.append(DefectAnnotationResponse(
                type=d.get("type"),
                severity=d.get("severity"),
                location=d.get("location"),
                description=d.get("description"),
            ))
        except Exception:
            pass

    # Build suggested grade
    suggested_grade = None
    if result.suggested_grade:
        try:
            suggested_grade = SuggestedGradeResponse(
                scale=result.suggested_grade.get("scale"),
                grade_value=result.suggested_grade.get("grade_value"),
                reasoning=result.suggested_grade.get("reasoning"),
            )
        except Exception:
            pass

    return IntakeResultResponse(
        name=result.name,
        category_id=result.category_id,
        category_confidence=round(result.category_confidence, 4),
        subtype_id=result.subtype_id,
        attributes=result.attributes,
        identification_method=result.identification_method,
        barcode=result.barcode,
        barcode_type=result.barcode_type,
        taxonomy_version=result.taxonomy_version,
        taxonomy_confidence=round(result.taxonomy_confidence, 4),
        suggested_corrections=corrections,
        estimated_price=result.estimated_price,
        price_source=result.price_source,
        price_band=price_band,
        image_url=result.image_url,
        catalog_miss=result.catalog_miss,
        catalog_match_id=result.catalog_match_id,
        catalog_match_key=result.catalog_match_key,
        alternatives=alternatives,
        field_confidence=field_confidence,
        chain_of_thought=result.chain_of_thought,
        rationale=result.rationale,
        scan_session_id=result.scan_session_id,
        social_proof=social_proof,
        duplicate_info=duplicate_info,
        defect_annotations=defect_annotations,
        suggested_grade=suggested_grade,
    )


def _is_valid_image(data: bytes) -> bool:
    """Check magic bytes to verify the data is a valid image."""
    if len(data) < 4:
        return False
    if data[:2] == b"\xff\xd8":
        return True
    if data[:4] == b"\x89PNG":
        return True
    if data[:4] == b"RIFF" and len(data) >= 12 and data[8:12] == b"WEBP":
        return True
    if data[:4] in (b"GIF8",):
        return True
    return False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/process", response_model=IntakeResultResponse, summary="Full intake processing", description="Accepts multipart form with optional image, barcode, and user hints. Barcode is tried first when both are provided, with vision as fallback.")
async def intake_process(
    file: Optional[UploadFile] = File(None, description="Image of the collectible item"),
    barcode: Optional[str] = Form(None, max_length=50),
    barcode_type: Optional[str] = Form(None, max_length=20),
    category: Optional[str] = Form(None, max_length=64),
    name: Optional[str] = Form(None, max_length=500),
    condition: Optional[str] = Form(None, max_length=30),
    user_id: str = Depends(get_current_user_id),
):
    """
    Full intake endpoint: accepts multipart form with optional image,
    barcode, and user hints.

    If both image and barcode are provided, barcode is tried first,
    with vision as a supplement/fallback.
    """
    image_bytes: Optional[bytes] = None

    # Read and validate image if provided
    if file is not None:
        content_type = (file.content_type or "").lower()
        if content_type and content_type not in ALLOWED_CONTENT_TYPES:
            raise error_response(400, f"Unsupported image type. Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}")

        try:
            image_bytes = await file.read()
        except Exception:
            logger.warning("Failed to read uploaded file for intake")
            raise error_response(400, "Failed to read uploaded file")

        if image_bytes and len(image_bytes) > MAX_IMAGE_BYTES:
            raise error_response(413, f"Image too large. Maximum size: {MAX_IMAGE_BYTES // (1024 * 1024)} MB")

        if image_bytes and not _is_valid_image(image_bytes):
            raise error_response(400, "File does not appear to be a valid image")

    # Must have at least barcode or image
    if not barcode and not image_bytes:
        raise error_response(400, "At least one of barcode or image is required")

    # Build user hints
    user_hints: dict[str, Any] = {}
    if category:
        user_hints["category"] = category
    if name:
        user_hints["name"] = name
    if condition:
        user_hints["condition"] = condition

    result = await process_intake(
        image_bytes=image_bytes,
        barcode=barcode,
        barcode_type=barcode_type,
        user_hints=user_hints if user_hints else None,
        user_id=user_id,
    )

    # Record demand signal with geo enrichment (best-effort)
    try:
        from app.features.data_moat import record_demand_signal, get_user_geo
        region, country = await get_user_geo(user_id)
        await record_demand_signal(
            signal_type="item_scanned",
            category=category,
            item_key=name or barcode,
            user_id=user_id,
            region=region,
            country_code=country,
        )
    except Exception:
        pass

    return _intake_to_response(result)


@router.post("/barcode-only", response_model=IntakeResultResponse, summary="Barcode-only intake")
async def intake_barcode_only(
    req: BarcodeOnlyRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Barcode-only intake endpoint.

    Lightweight version: barcode lookup -> taxonomy resolve -> price hint.
    No image processing involved.
    """
    barcode = req.barcode.strip()
    if not barcode:
        raise error_response(400, "Barcode is required")

    from app.lib.validators import is_valid_barcode
    if not is_valid_barcode(barcode):
        raise error_response(400, "Invalid barcode format")

    user_hints: dict[str, Any] = {}
    if req.category:
        user_hints["category"] = req.category
    if req.name:
        user_hints["name"] = req.name
    if req.condition:
        user_hints["condition"] = req.condition

    result = await process_intake(
        image_bytes=None,
        barcode=barcode,
        barcode_type=req.barcode_type,
        user_hints=user_hints if user_hints else None,
        user_id=user_id,
    )

    try:
        from app.features.data_moat import record_demand_signal, get_user_geo
        region, country = await get_user_geo(user_id)
        await record_demand_signal(
            signal_type="item_scanned",
            category=req.category,
            item_key=req.name or barcode,
            user_id=user_id,
            region=region,
            country_code=country,
        )
    except Exception:
        pass

    return _intake_to_response(result)


@router.post("/image-only", response_model=IntakeResultResponse, summary="Image-only intake")
async def intake_image_only(
    file: UploadFile = File(..., description="Image of the collectible item"),
    category: Optional[str] = Form(None, max_length=64),
    name: Optional[str] = Form(None, max_length=500),
    condition: Optional[str] = Form(None, max_length=30),
    user_id: str = Depends(get_current_user_id),
):
    """
    Image-only intake endpoint.

    Vision classification -> taxonomy resolve -> price hint.
    No barcode processing involved.
    """
    content_type = (file.content_type or "").lower()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise error_response(400, f"Unsupported image type. Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}")

    try:
        image_bytes = await file.read()
    except Exception:
        logger.warning("Failed to read uploaded file for intake")
        raise error_response(400, "Failed to read uploaded file")

    if not image_bytes:
        raise error_response(400, "Empty file uploaded")

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise error_response(413, f"Image too large. Maximum size: {MAX_IMAGE_BYTES // (1024 * 1024)} MB")

    if not _is_valid_image(image_bytes):
        raise error_response(400, "File does not appear to be a valid image")

    user_hints: dict[str, Any] = {}
    if category:
        user_hints["category"] = category
    if name:
        user_hints["name"] = name
    if condition:
        user_hints["condition"] = condition

    result = await process_intake(
        image_bytes=image_bytes,
        barcode=None,
        barcode_type=None,
        user_hints=user_hints if user_hints else None,
        user_id=user_id,
    )

    try:
        from app.features.data_moat import record_demand_signal, get_user_geo
        region, country = await get_user_geo(user_id)
        await record_demand_signal(
            signal_type="item_scanned",
            category=category,
            item_key=name,
            user_id=user_id,
            region=region,
            country_code=country,
        )
    except Exception:
        pass

    return _intake_to_response(result)


@router.post("/url", response_model=IntakeResultResponse, summary="Import from URL", description="Paste a marketplace listing URL to get structured item data. Supports eBay, Mercari, StockX, TCGPlayer, BrickLink, and more.")
async def intake_url(
    req: UrlImportRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    URL import endpoint.

    Paste a marketplace listing URL and get structured item data back.
    Supported: eBay, Mercari, StockX, TCGPlayer, BrickLink, MFC, Ktown4u, Weverse.
    """
    url = req.url.strip()
    if not url:
        raise error_response(400, "URL is required")

    if not url.startswith(("http://", "https://")):
        raise error_response(400, "URL must start with http:// or https://")

    # SSRF protection: block private/internal IPs
    try:
        validate_url(url)
    except ValueError as e:
        raise error_response(400, str(e))

    user_hints: dict[str, Any] = {}
    if req.category:
        user_hints["category"] = req.category
    if req.name:
        user_hints["name"] = req.name
    if req.condition:
        user_hints["condition"] = req.condition

    result = await process_url_import(
        url=url,
        user_hints=user_hints if user_hints else None,
        user_id=user_id,
    )

    return _intake_to_response(result)


# ---------------------------------------------------------------------------
# Save intake result as a new collection item
# ---------------------------------------------------------------------------

class IntakeSaveRequest(BaseModel):
    """Persist an intake result to the items table."""
    title: str = Field(..., min_length=1, max_length=500)
    category: Optional[str] = Field(None, max_length=64)
    condition: Optional[str] = Field(None, max_length=30)
    subtype_id: Optional[str] = Field(None, max_length=64)
    taxonomy_version: Optional[str] = Field(None, max_length=20)
    attributes: dict[str, Any] = Field(default_factory=dict)
    images: list[str] = Field(default_factory=list)
    barcode: Optional[str] = Field(None, max_length=50)
    estimated_price: Optional[float] = None


class IntakeSaveResponse(BaseModel):
    id: str
    title: str
    category: Optional[str] = None
    created: bool = True


def _normalize_key(title: str) -> str:
    """Generate a normalized_key from a title for dedup / matching."""
    import re
    key = title.lower().strip()
    key = re.sub(r"[^a-z0-9\s]", "", key)
    key = re.sub(r"\s+", " ", key).strip()
    return key[:200]


@router.post("/save", response_model=IntakeSaveResponse, summary="Save intake result to collection", description="Persist an intake result as a new item in the user's collection. Called after scan identification when the user taps 'Add to Collection'.")
async def intake_save(
    payload: IntakeSaveRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Persist an intake result as a new item in the user's collection.

    Called after barcode scan / image intake returns an identification,
    when the user taps "Add to Collection".
    """
    from uuid import uuid4
    import json as _json

    item_id = str(uuid4())

    from app.db import db_configured, get_conn

    if not db_configured():
        # DB-disabled mode: return a mock saved item
        return IntakeSaveResponse(id=item_id, title=payload.title, category=payload.category)

    normalized_key = _normalize_key(payload.title)

    async with get_conn() as conn:
        await conn.execute(
            """
            INSERT INTO public.items (
                id, user_id, title, category, condition,
                subtype_id, taxonomy_version,
                attributes_json, images, normalized_key
            ) VALUES (
                $1::uuid, $2::uuid, $3, $4, $5,
                $6, $7,
                $8, $9, $10
            )
            """,
            item_id,
            user_id,
            payload.title,
            payload.category,
            payload.condition,
            payload.subtype_id,
            payload.taxonomy_version,
            _json.dumps(payload.attributes) if payload.attributes else None,
            _json.dumps(payload.images) if payload.images else None,
            normalized_key,
        )

    logger.info(
        "[intake/save] Created item %s for user %s (category=%s)",
        item_id, user_id, payload.category,
    )

    # Award XP for scan+save (best-effort, slightly more than manual add)
    try:
        from app.features.gamification_router import record_activity_xp
        async with get_conn() as conn2:
            scan_count = await conn2.fetchval(
                "SELECT COUNT(*) FROM items WHERE user_id = $1::uuid",
                user_id,
            )
            achievement_checks = []
            scan_milestones = [
                (1, "scanner_1"), (5, "scanner_5"),
                (10, "scanner_10"), (25, "scanner_25"),
            ]
            for threshold, ach_id in scan_milestones:
                if scan_count >= threshold:
                    achievement_checks.append((ach_id, scan_count))
            collector_milestones = [
                (5, "collector_5"), (10, "collector_10"),
                (25, "collector_25"), (50, "collector_50"),
                (100, "collector_100"),
            ]
            for threshold, ach_id in collector_milestones:
                if scan_count >= threshold:
                    achievement_checks.append((ach_id, scan_count))
            await record_activity_xp(conn2, user_id, 15, achievement_checks or None)
    except Exception:
        logger.debug("[intake/save] Gamification XP award failed (non-critical)")

    # Record demand signal with geo — strongest signal: user committed to adding this item
    try:
        from app.features.data_moat import record_demand_signal, get_user_geo
        region, country = await get_user_geo(user_id)
        await record_demand_signal(
            signal_type="item_added",
            category=payload.category,
            item_key=normalized_key,
            user_id=user_id,
            region=region,
            country_code=country,
        )
    except Exception:
        pass

    return IntakeSaveResponse(id=item_id, title=payload.title, category=payload.category)


# ---------------------------------------------------------------------------
# Multi-item detection
# ---------------------------------------------------------------------------

# Per-user: 10 multi-detect requests per minute
_multi_detect_limit = per_user_rate_limit(10, scope="intake_multi_detect")


@router.post("/multi-detect", response_model=MultiDetectResponse, dependencies=[Depends(_multi_detect_limit)], summary="Detect multiple items in image", description="Returns bounding boxes and category hints for each detected item in a single photograph.")
async def intake_multi_detect(
    file: UploadFile = File(..., description="Image with multiple collectible items"),
    user_id: str = Depends(get_current_user_id),
):
    """
    Detect multiple collectible items in a single photograph.

    Returns bounding boxes and category hints for each detected item.
    Use the regular /intake/process endpoint to identify each individual item.
    """
    content_type = (file.content_type or "").lower()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise error_response(400, f"Unsupported image type. Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}")

    try:
        image_bytes = await file.read()
    except Exception:
        raise error_response(400, "Failed to read uploaded file")

    if not image_bytes:
        raise error_response(400, "Empty file uploaded")

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise error_response(413, f"Image too large. Maximum size: {MAX_IMAGE_BYTES // (1024 * 1024)} MB")

    if not _is_valid_image(image_bytes):
        raise error_response(400, "File does not appear to be a valid image")

    from app.ml.multi_item_detector import detect_multiple_items

    detected = await detect_multiple_items(image_bytes)

    items = [
        DetectedItemResponse(
            item_index=d.item_index,
            bounding_box=BoundingBoxResponse(
                x=d.bounding_box.x,
                y=d.bounding_box.y,
                w=d.bounding_box.w,
                h=d.bounding_box.h,
            ),
            category_hint=d.category_hint,
            suggested_name=d.suggested_name,
            confidence=d.confidence,
        )
        for d in detected
    ]

    return MultiDetectResponse(items=items, total_detected=len(items))
