from __future__ import annotations

# load .env early (but after the future import)
try:
    from services.collectors_merge.core.env import ensure_env as _ensure_env

    _ensure_env()
except Exception:
    pass

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest

# Import the API routes
from services.collectors_merge.api.routes import router as app_router

app = FastAPI(title="Collectors Merge API")
app.include_router(app_router)


@app.get("/health")
def health():
    # fast smoke; avoid DB here
    return {"ok": True, "flags": {"market_ebay": True, "photo_fastpass": True}}


@app.get("/ready")
def ready():
    return {"ok": True}


@app.get("/metrics")
def metrics():
    data = generate_latest(REGISTRY)
    return PlainTextResponse(data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)
