from uuid import uuid4
from app.features import insights_router
from app.features import screenshot_intel_router
from app.features import quickscan_advanced_router
from app.features import watchlist_router
from app.features import marketplace_trust_router
from app.features import provenance_router
from app.features import trends_and_deepdive_router
from app.features import alerts_feature_router
import os
import httpx
from pathlib import Path
from typing import Optional, List
from app.routers.vision_commit import router as vision_commit_router
from app.routers.vision_predict_log import router as vision_predict_log_router
from fastapi import FastAPI, Depends, Header, HTTPException, UploadFile, File
from pydantic import BaseModel
from app.middleware_stack import install_middlewares
from app.db import connect_pool, close_pool, db_configured
from app.metrics import metrics_middleware, ensure_metrics_once
from app.logging_mw import logging_middleware
from app.limit_body import limit_body_middleware
from app.rate_limit import rate_limit_middleware
from app.routes.agent import router as agent_router
from app.routes.spool import router as ops_router
from app.routes.spool_ui import router as spool_ui_router
from app.routes.webhook import router as webhook_router
from app.routes.vision_debug import router as vision_debug_router
from app.routes.vision_predict import router as vision_predict_router
from app.routes.vision_ops import router as vision_ops_router
from app.routes.vision_ingest import router as vision_ingest_router
from app.routes.vision_search import router as vision_search_router
from app.routes.spool_ops import router as spool_ops_router
from app.routes.manifests import router as manifests_router
from app.routes.ops import router as ops_router
from app.routes.marketplace import router as marketplace_router

app = FastAPI(title="Collectors Merge Service", version=os.getenv("SERVICE_VERSION","0.1.0"))
API_SHARED_SECRET = os.environ.get("API_SHARED_SECRET")
SIGNALS_BASE_URL = "http://127.0.0.1:8082"


async def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    if not API_SHARED_SECRET:
        raise HTTPException(status_code=500, detail="API key not configured")
    if x_api_key != API_SHARED_SECRET:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


@app.get("/debug-ping")
async def debug_ping():
    return {"ok": True}


@app.get("/portfolio/overview")
async def portfolio_overview(_: bool = Depends(require_api_key)):
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{SIGNALS_BASE_URL}/portfolio/overview",
            headers={"X-API-Key": API_SHARED_SECRET},
            timeout=10.0,
        )
    r.raise_for_status()
    return r.json()


@app.get("/portfolio/items")
async def portfolio_items(_: bool = Depends(require_api_key)):
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{SIGNALS_BASE_URL}/portfolio/items",
            headers={"X-API-Key": API_SHARED_SECRET},
            timeout=10.0,
        )
    r.raise_for_status()
    return r.json()


@app.get("/portfolio/timeseries")
async def portfolio_timeseries(_: bool = Depends(require_api_key)):
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{SIGNALS_BASE_URL}/portfolio/timeseries",
            headers={"X-API-Key": API_SHARED_SECRET},
            timeout=10.0,
        )
    r.raise_for_status()
    return r.json()

app.include_router(vision_commit_router)
app.include_router(vision_predict_log_router)
app.include_router(marketplace_router)

# Core middlewares
install_middlewares(app)
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(metrics_middleware)
app.middleware("http")(logging_middleware)

# Routers
app.include_router(agent_router)
app.include_router(ops_router)
app.include_router(spool_ui_router)
app.include_router(webhook_router)
app.include_router(vision_debug_router)
app.include_router(vision_predict_router)
app.include_router(vision_ops_router)
app.include_router(vision_ingest_router)
app.include_router(vision_search_router)
app.include_router(spool_ops_router)
app.include_router(manifests_router)
app.include_router(ops_router)
app.include_router(spool_ui_router)

@app.get("/healthz")
async def healthz():
    return {
        "ok": True,
        "db_configured": db_configured(),
        "db_enabled": os.getenv("DB_ENABLED","true"),
        "db_optional": os.getenv("DB_OPTIONAL","0"),
    }

@app.get("/version")
async def version():
    return {"version": os.getenv("SERVICE_VERSION","0.1.0")}

@app.on_event("startup")
async def _startup():
    import os, logging
    # Offline mode: skip DB connect entirely
    if os.getenv("DB_ENABLED", "false").lower() in ("0","false","no"):
        logging.getLogger("uvicorn").info("[startup] DB disabled; skipping pool connect.")
        return
    try:
        from app.db import connect_pool
        await connect_pool()
    except Exception as e:
        # Optional mode: continue even if DB connect fails/missing DSN
        if os.getenv("DB_OPTIONAL", "0").lower() in ("1","true","yes"):
            logging.getLogger("uvicorn").warning(f"[startup] DB optional; continuing without pool. Reason: {e}")
            return
        raise
@app.on_event("shutdown")
async def _shutdown():
    await close_pool()

@app.get("/debug-ping")
async def debug_ping():
    return {"ok": True}

# Auto-wired alerts router
app.include_router(alerts_feature_router.router)

# Auto-wired trends/deep-dive router
app.include_router(trends_and_deepdive_router.router)

# Auto-wired provenance router
app.include_router(provenance_router.router)

# Auto-wired marketplace trust router
app.include_router(marketplace_trust_router.router)


# Watchlist, QuickScan advanced, Insights routers
app.include_router(watchlist_router.router)
app.include_router(quickscan_advanced_router.router)
app.include_router(insights_router.router)

# Screenshot intel router
app.include_router(screenshot_intel_router.router)

from app.features import items_export_router

app.include_router(items_export_router.router)

class QuickScanRequest(BaseModel):
    mode: Optional[str] = None
    category_hint: Optional[str] = None
    image_id: Optional[str] = None
    image_ids: Optional[List[str]] = None
    image_id: Optional[str] = None
    image_ids: Optional[List[str]] = None

@app.post("/quickscan")

@app.post("/quickscan")

@app.post("/quickscan")
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
    friendly_category_map = {
        "mtg": "Magic: The Gathering",
        "lorcana": "Disney Lorcana",
        "fab": "Flesh and Blood",
        "funko": "Funko Pop",
        "diecast": "Diecast",
    }
    friendly_category = friendly_category_map.get(raw_cat, attrs.category)

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

class QuickScanUploadResponse(BaseModel):
    image_id: str


@app.post("/quickscan/upload-image", response_model=QuickScanUploadResponse)
async def quickscan_upload_image(file: UploadFile = File(...)):
    """
    Accept a user image for QuickScan, store it, and return an image_id
    that can be passed into /quickscan. Later, the advanced model can
    look up the image by this ID.
    """
    # Generate a stable-ish ID and write to a temp directory
    image_id = f"quickscan-{uuid4().hex}"
    tmp_dir = Path(os.getenv("QUICKSCAN_TMP_DIR", "/tmp"))
    tmp_dir.mkdir(parents=True, exist_ok=True)

    safe_name = file.filename or "upload.jpg"
    out_path = tmp_dir / f"{image_id}_{safe_name}"

    contents = await file.read()
    out_path.write_bytes(contents)

    return {"image_id": image_id}

class ItemCreateRequest(BaseModel):
    name: str
    category: Optional[str] = None
    collection_name: Optional[str] = None
    estimated_value: Optional[float] = None
    notes: Optional[str] = None


class ItemResponse(ItemCreateRequest):
    id: str


_DEMO_ITEMS: list[ItemResponse] = []


@app.post("/items", response_model=ItemResponse)
async def create_item(payload: ItemCreateRequest):
    """
    Demo create-item endpoint.
    Stores items in memory so the Items tab can show QuickScan results.
    Later we can swap this to Supabase without changing the frontend.
    """
    new_id = f"demo-{len(_DEMO_ITEMS) + 1}"
    item = ItemResponse(
        id=new_id,
        name=payload.name,
        category=payload.category,
        collection_name=payload.collection_name,
        estimated_value=payload.estimated_value,
        notes=payload.notes,
    )
    _DEMO_ITEMS.append(item)
    return item


@app.get("/items", response_model=list[ItemResponse])
async def list_items():
    """
    List all demo items stored in memory.
    """
    return _DEMO_ITEMS

@app.get("/portfolio/summary")
async def portfolio_summary():
    """
    Backend sync v1: lightweight portfolio summary based on the same
    store that /items uses (_DEMO_ITEMS for now). Later this can be
    swapped to Supabase/Signals without changing the mobile app.
    """
    items_payload = []

    try:
        # Reuse the in-memory store if it exists
        global _DEMO_ITEMS  # type: ignore[name-defined]
        for it in _DEMO_ITEMS:
            try:
                value = float(it.estimated_value or 0.0)
            except Exception:
                value = 0.0
            items_payload.append(
                {
                    "id": it.id,
                    "name": it.name,
                    "category": it.category or "Uncategorized",
                    "value": value,
                    "change_pct": 0.0,
                }
            )
    except Exception as e:
        logging.getLogger("uvicorn").warning(
            f"[portfolio_summary] _DEMO_ITEMS unavailable: {e}"
        )

    total_value = sum(i["value"] for i in items_payload) if items_payload else 0.0
    avg_change_pct = 0.0

    return {
        "total_value": total_value,
        "avg_change_pct": avg_change_pct,
        "items": items_payload,
        "watchlist": [],
    }



@app.get("/ops/status")
async def ops_status():
    """Lightweight ops status for frontend + probes.

    Kept deliberately simple: if this returns 200, the app + DB wiring are considered 'up enough'
    for the mobile/web client to function.
    """
    return {
        "status": "ok",
        "service": "collectors-merge",
        "version": "ops-status-v1"
    }

# -----------------------------------------
# Twitch routes
# -----------------------------------------
from routers.twitch import router as twitch_router
app.include_router(twitch_router)



from fastapi import UploadFile, File, HTTPException
import csv
import io
from typing import Any, Dict, List


@app.post("/api/imports/collection")
async def import_collection(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Accept a CSV or Excel file and return a summary of rows.
    This first version does NOT write to the database – it only parses.
    Later we will attach user_id & insert into items table.
    """
    filename = file.filename or "upload"
    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    # Decide how to parse based on extension
    lower_name = filename.lower()
    rows: List[Dict[str, Any]] = []

    try:
        if lower_name.endswith(".csv"):
            text = content.decode("utf-8", errors="replace")
            reader = csv.DictReader(io.StringIO(text))
            rows = list(reader)
        elif lower_name.endswith(".xlsx") or lower_name.endswith(".xls"):
            try:
                import pandas as pd  # type: ignore
            except ImportError:
                raise HTTPException(
                    status_code=500,
                    detail="Excel support is not installed. Please install pandas and openpyxl.",
                )
            df = pd.read_excel(io.BytesIO(content))
            rows = df.to_dict(orient="records")
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Please upload a CSV or Excel file.",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {e}")

    # Normalize keys (lowercase, strip spaces)
    norm_rows: List[Dict[str, Any]] = []
    for row in rows:
        norm: Dict[str, Any] = {}
        for k, v in row.items():
            if k is None:
                continue
            norm_key = str(k).strip().lower().replace(" ", "_")
            norm[norm_key] = v
        norm_rows.append(norm)

    total = len(norm_rows)
    inserted = 0
    skipped = 0
    errors: List[Dict[str, Any]] = []

    for idx, r in enumerate(norm_rows, start=1):
        name = r.get("name")
        if not name or str(name).strip() == "":
            skipped += 1
            errors.append({"row": idx, "message": "Missing required 'name' column"})
            continue

        # Later: validate more fields, insert into DB items table
        inserted += 1

    return {
        "total_rows": total,
        "inserted_count": inserted,
        "skipped_count": skipped,
        "errors": errors,
        "columns_detected": sorted(list(norm_rows[0].keys())) if norm_rows else [],
    }
