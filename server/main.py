"""
CollectAI — Collectors Merge Service entry point.

This module creates the FastAPI app, installs middleware, registers all
routers, and defines the lifespan (startup / shutdown) hooks.
Endpoint logic lives in ``app/routes/``, ``app/features/``, and
``app/agents/``.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Depends, Request
from fastapi.responses import JSONResponse

from app.auth import require_ops_key
from app.config import (
    SERVICE_VERSION,
    SENTRY_DSN,
    SENTRY_TRACES_RATE,
    SENTRY_ENV,
    DB_ENABLED,
    MONITOR_ENABLED,
    DEAL_DISCOVERY_ENABLED,
    CATALOG_LEARNING_ENABLED,
    TASK_WORKER_ENABLED,
    DEBUG,
)
from app.middleware_stack import install_middlewares
from app.db import connect_pool, close_pool, db_configured
from app.metrics import metrics_middleware, ensure_metrics_once
from app.logging_mw import logging_middleware
from app.limit_body import limit_body_middleware
from app.rate_limit import rate_limit_middleware
from app.request_id import request_id_middleware

# ---------------------------------------------------------------------------
# Sentry (optional)
# ---------------------------------------------------------------------------
try:
    import sentry_sdk
except ImportError:
    sentry_sdk = None  # type: ignore[assignment]

if SENTRY_DSN and sentry_sdk is not None:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=SENTRY_TRACES_RATE,
        environment=SENTRY_ENV,
        release=SERVICE_VERSION,
    )

# ---------------------------------------------------------------------------
# Lifespan (replaces deprecated @app.on_event("startup") / "shutdown")
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Async context manager for app startup and shutdown."""
    # ---- Startup ----
    from app.config import validate_config
    validate_config()

    if not DB_ENABLED:
        logging.getLogger("uvicorn").info("[startup] DB disabled; skipping pool connect.")
    else:
        try:
            await connect_pool()
        except Exception as e:
            if os.getenv("DB_OPTIONAL", "0").lower() in ("1", "true", "yes"):
                logging.getLogger("uvicorn").warning(
                    "[startup] DB optional; continuing without pool. Reason: %s", e
                )
            else:
                raise

    if MONITOR_ENABLED:
        try:
            from workers.price_monitor_scheduler import scheduler_loop
            asyncio.create_task(scheduler_loop())
            logging.getLogger("uvicorn").info("[startup] Price monitor scheduler started")
        except Exception as e:
            logging.getLogger("uvicorn").warning("[startup] Failed to start price monitor: %s", e)

    if DEAL_DISCOVERY_ENABLED:
        try:
            from workers.deal_discovery_scheduler import scheduler_loop as deal_scheduler_loop
            asyncio.create_task(deal_scheduler_loop())
            logging.getLogger("uvicorn").info("[startup] Deal discovery scheduler started")
        except Exception as e:
            logging.getLogger("uvicorn").warning("[startup] Failed to start deal discovery: %s", e)

    if CATALOG_LEARNING_ENABLED:
        try:
            from workers.catalog_learning_scheduler import scheduler_loop as catalog_learning_loop
            asyncio.create_task(catalog_learning_loop())
            logging.getLogger("uvicorn").info("[startup] Catalog learning scheduler started")
        except Exception as e:
            logging.getLogger("uvicorn").warning("[startup] Failed to start catalog learning: %s", e)

    if os.getenv("MATVIEW_REFRESH_ENABLED", "true").lower() in ("true", "1"):
        try:
            from workers.matview_refresh_worker import scheduler_loop as matview_scheduler_loop
            asyncio.create_task(matview_scheduler_loop())
            logging.getLogger("uvicorn").info("[startup] Matview refresh scheduler started")
        except Exception as e:
            logging.getLogger("uvicorn").warning("[startup] Failed to start matview refresh: %s", e)

    if TASK_WORKER_ENABLED:
        try:
            from app.lib.task_worker import run_worker as task_worker_loop
            from app.config import TASK_WORKER_POLL_INTERVAL
            asyncio.create_task(task_worker_loop(poll_interval=TASK_WORKER_POLL_INTERVAL))
            logging.getLogger("uvicorn").info("[startup] Task queue worker started")
        except Exception as e:
            logging.getLogger("uvicorn").warning("[startup] Failed to start task queue worker: %s", e)

    yield

    # ---- Shutdown ----
    from app.routes.portfolio_router import close_http_client
    await close_http_client()
    await close_pool()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Collectors Merge Service", version=SERVICE_VERSION, lifespan=lifespan)

_logger = logging.getLogger("collectai.main")


@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return a safe 500 without leaking internals."""
    _logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ---------------------------------------------------------------------------
# Middleware (outermost first — request_id wraps everything)
# ---------------------------------------------------------------------------
install_middlewares(app)
app.middleware("http")(limit_body_middleware)
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(metrics_middleware)
app.middleware("http")(logging_middleware)
app.middleware("http")(request_id_middleware)
ensure_metrics_once(app)

# ---------------------------------------------------------------------------
# Router imports
# ---------------------------------------------------------------------------
from app.features.quickscan_proxy_router import router as quickscan_proxy_router
from app.routes.items_router import router as items_router
from app.routes.portfolio_router import router as portfolio_router
from app.features.import_router import router as import_router

from app.routes.vision_predict import router as vision_predict_router
from app.routes.user_settings_router import router as user_settings_router
from app.routes.account_router import router as account_router
from app.routes.fx_router import router as fx_router
from app.routes.pipeline_status_router import router as pipeline_status_router

from app.features import data_moat
from app.features import insights_router
from app.features import screenshot_intel_router
from app.features import quickscan_advanced_router
from app.features import watchlist_router
from app.features import provenance_router
from app.features import trends_and_deepdive_router
from app.features import alerts_feature_router
from app.features import feedback_router
from app.features import items_export_router
from app.features import photo_upload_router
from app.features import events_router
from app.features import barcode_lookup_router
from app.features import storage_router
from app.features import taxonomy_router
from app.features import notification_router
from app.features import collections_router
from app.features.predict_router import router as predict_router

from app.agents.marketplace_router import router as marketplace_agg_router
from app.agents.dossier_router import router as dossier_router
from app.agents.intake_router import router as intake_router
from app.agents.intake_feedback_router import router as intake_feedback_router
from app.agents.purchase_router import router as purchase_router
from app.routes.billing_router import router as billing_router
from app.routes.admin_dashboard import router as admin_dashboard_router
from app.routes.mfa_router import router as mfa_router
from app.routes.beta_signup_router import router as beta_signup_router
from app.routes.seed_router import router as seed_router
from app.routes.affiliate_links_router import router as affiliate_links_router
from app.features.sponsor_router import router as sponsor_router
from app.features.catalog_learning_router import router as catalog_learning_router
from app.features.social_router import router as social_router
from app.routes.geo_router import router as geo_router
from app.features.sponsor_company_router import router as sponsor_company_router
from app.features.build_paint_router import router as build_paint_router
from app.features.set_router import router as set_router
from app.features.task_queue_router import router as task_queue_router
from app.features.activity_router import router as activity_router
from app.features.search_router import router as search_router
from app.agents.deal_desk_router import router as deal_desk_router
from app.features.item_images_router import router as item_images_router
from app.features.gamification_router import router as gamification_router
from app.features.catalog_browser_router import router as catalog_browser_router
from app.features.grading_router import router as grading_router
from app.features.export_router import router as export_router
from app.features.marketplace_listing_router import router as marketplace_listing_router
from app.features.chat_router import router as chat_router
from app.features.admin_health_router import router as admin_health_router

# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------

# Extracted routers (Phase 1)
app.include_router(quickscan_proxy_router)
app.include_router(items_router)
app.include_router(portfolio_router)
app.include_router(import_router)

# Core routers
app.include_router(vision_predict_router)

# Feature routers
app.include_router(data_moat.router)
app.include_router(alerts_feature_router.router)
app.include_router(trends_and_deepdive_router.router)
app.include_router(provenance_router.router)
app.include_router(watchlist_router.router)
app.include_router(quickscan_advanced_router.router)
app.include_router(insights_router.router)
app.include_router(screenshot_intel_router.router)
app.include_router(feedback_router.router)
app.include_router(items_export_router.router)
app.include_router(storage_router.router)
app.include_router(photo_upload_router.router)
app.include_router(events_router.router)
app.include_router(barcode_lookup_router.router)
app.include_router(taxonomy_router.router)
app.include_router(notification_router.router)
app.include_router(collections_router.router)

# Agent routers
app.include_router(marketplace_agg_router)
app.include_router(dossier_router)
app.include_router(intake_router)
app.include_router(intake_feedback_router)
app.include_router(purchase_router)
app.include_router(predict_router)
app.include_router(fx_router)
app.include_router(user_settings_router)
app.include_router(account_router)
app.include_router(pipeline_status_router)
app.include_router(billing_router)
app.include_router(admin_dashboard_router)
app.include_router(mfa_router)
app.include_router(beta_signup_router)
app.include_router(seed_router)
app.include_router(affiliate_links_router)
app.include_router(sponsor_router)
app.include_router(catalog_learning_router)
app.include_router(social_router)
app.include_router(geo_router)
app.include_router(sponsor_company_router)
app.include_router(build_paint_router)
app.include_router(set_router)
app.include_router(task_queue_router)
app.include_router(activity_router)
app.include_router(search_router)
app.include_router(deal_desk_router)
app.include_router(item_images_router)
app.include_router(gamification_router)
app.include_router(catalog_browser_router)
app.include_router(grading_router)
app.include_router(export_router)
app.include_router(marketplace_listing_router)
app.include_router(chat_router)
app.include_router(admin_health_router)

# Twitch (optional)
try:
    from app.routers.twitch import router as twitch_router
    app.include_router(twitch_router)
except ImportError:
    pass

# ---------------------------------------------------------------------------
# /v1 aliases — all feature routers also available under /v1 prefix
# ---------------------------------------------------------------------------
_v1 = APIRouter(prefix="/v1")
_v1.include_router(data_moat.router)
_v1.include_router(alerts_feature_router.router)
_v1.include_router(trends_and_deepdive_router.router)
_v1.include_router(provenance_router.router)
_v1.include_router(watchlist_router.router)
_v1.include_router(quickscan_advanced_router.router)
_v1.include_router(insights_router.router)
_v1.include_router(screenshot_intel_router.router)
_v1.include_router(feedback_router.router)
_v1.include_router(items_export_router.router)
_v1.include_router(storage_router.router)
_v1.include_router(photo_upload_router.router)
_v1.include_router(events_router.router)
_v1.include_router(barcode_lookup_router.router)
_v1.include_router(taxonomy_router.router)
_v1.include_router(notification_router.router)
_v1.include_router(collections_router.router)
_v1.include_router(marketplace_agg_router)
_v1.include_router(dossier_router)
_v1.include_router(intake_router)
_v1.include_router(intake_feedback_router)
_v1.include_router(purchase_router)
_v1.include_router(predict_router)
_v1.include_router(fx_router)
_v1.include_router(user_settings_router)
_v1.include_router(account_router)
_v1.include_router(pipeline_status_router)
_v1.include_router(billing_router)
_v1.include_router(mfa_router)
_v1.include_router(affiliate_links_router)
_v1.include_router(sponsor_router)
_v1.include_router(catalog_learning_router)
_v1.include_router(geo_router)
_v1.include_router(task_queue_router)
_v1.include_router(set_router)
_v1.include_router(item_images_router)
_v1.include_router(gamification_router)
_v1.include_router(catalog_browser_router)
_v1.include_router(grading_router)
_v1.include_router(export_router)
_v1.include_router(marketplace_listing_router)
_v1.include_router(chat_router)
app.include_router(_v1)

# ---------------------------------------------------------------------------
# Lightweight inline endpoints
# ---------------------------------------------------------------------------


@app.get("/healthz")
async def healthz():
    result = {
        "ok": True,
        "db_configured": db_configured(),
    }
    if db_configured():
        import time as _time
        try:
            from app.db import get_pool
            pool = get_pool()
            if pool is not None:
                t0 = _time.monotonic()
                async with pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                result["db_ms"] = round((_time.monotonic() - t0) * 1000, 1)
                result["db"] = "up"
            else:
                result["db"] = "pool_not_initialized"
                result["ok"] = False
        except Exception as exc:
            _logger.warning("healthz DB check failed: %s", exc)
            result["db"] = "down"
            result["ok"] = False
    if not result["ok"]:
        return JSONResponse(status_code=503, content=result)
    return result


@app.get("/version")
async def version():
    return {"version": SERVICE_VERSION}


# ---------------------------------------------------------------------------
# Ops endpoints (kept inline — small and ops-key guarded)
# ---------------------------------------------------------------------------


@app.get("/ops/status")
async def ops_status(_: bool = Depends(require_ops_key)):
    return {"status": "ok", "service": "collectors-merge", "version": "ops-status-v1"}


@app.get("/ops/worker-status")
async def ops_worker_status(_: bool = Depends(require_ops_key)):
    from app.worker_registry import get_status
    return get_status()


@app.get("/ops/worker-overdue")
async def ops_worker_overdue(_: bool = Depends(require_ops_key)):
    """Return list of workers that haven't run within 1.5x their expected interval."""
    from app.worker_registry import get_overdue_workers
    overdue = get_overdue_workers()
    return {"overdue": overdue, "count": len(overdue)}


@app.get("/ops/cache")
async def ops_cache(_: bool = Depends(require_ops_key)):
    from app.cache import cache_stats
    return cache_stats()


@app.get("/ops/circuits")
async def ops_circuits(_: bool = Depends(require_ops_key)):
    from workers.circuit_breaker import all_circuit_status
    return all_circuit_status()


@app.get("/ops/canary-status")
async def ops_canary_status(_: bool = Depends(require_ops_key)):
    from app.ml.model_loader import get_canary_status
    return await get_canary_status()


@app.get("/ops/worker-history")
async def ops_worker_history(
    worker_name: str = "",
    limit: int = 50,
    _: bool = Depends(require_ops_key),
):
    """Recent worker run history from DB (persisted across restarts)."""
    from app.lib.db_helpers import get_db_pool
    pool = get_db_pool()
    if not pool:
        return {"runs": [], "note": "no_db_pool"}
    try:
        async with pool.acquire() as conn:
            if worker_name:
                rows = await conn.fetch(
                    """
                    SELECT worker_name, status, finished_at
                    FROM worker_runs
                    WHERE worker_name = $1
                    ORDER BY finished_at DESC
                    LIMIT $2
                    """,
                    worker_name,
                    min(limit, 200),
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT worker_name, status, finished_at
                    FROM worker_runs
                    ORDER BY finished_at DESC
                    LIMIT $1
                    """,
                    min(limit, 200),
                )
            return {"runs": [dict(r) for r in rows]}
    except Exception as e:
        return {"runs": [], "error": str(e)}


if DEBUG:
    @app.get("/debug-ping")
    async def debug_ping():
        return {"ok": True}

