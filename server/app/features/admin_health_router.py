"""
Admin Worker Health, Demand Summary & Spend Monitor endpoints.

Provides:
  ``GET /admin/worker-health``   — runtime health of every registered worker
  ``GET /admin/demand-summary``  — catalog demand signals for the owner
  ``GET /admin/spend-summary``   — current month API spend vs budget
  ``POST /admin/spend-budget``   — update monthly budget cap
  ``POST /admin/spend-pause``    — pause/resume a provider
  ``POST /admin/spend-reset``    — reset spend counters

Protected by the ``OPS_API_KEY`` environment variable — callers must send
the key in the ``X-Ops-Key`` header.  Returns 403 when the key is missing
or incorrect.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.db import get_pool
from app.lib.bg_tasks import spawn_bg
from app.worker_registry import check_and_alert_overdue, get_worker_health

_log = logging.getLogger("collectai.admin_health")

router = APIRouter(tags=["Admin"])


def _check_ops_key(request: Request) -> JSONResponse | None:
    """Validate OPS_API_KEY from request header. Returns error JSONResponse or None."""
    ops_key = os.getenv("OPS_API_KEY", "")
    provided = request.headers.get("X-Ops-Key", "")

    if not ops_key:
        _log.error("OPS_API_KEY is not configured — admin endpoint locked out")
        return JSONResponse(
            status_code=403,
            content={"detail": "OPS_API_KEY not configured on server"},
        )

    if not provided or provided != ops_key:
        return JSONResponse(
            status_code=403,
            content={"detail": "Invalid or missing X-Ops-Key header"},
        )

    return None


@router.get("/admin/worker-health", summary="Worker health status")
async def worker_health(request: Request) -> JSONResponse:
    """Return health status for all registered workers.

    Each worker entry includes: name, last_run_at, last_status (ok/error),
    run_count, average_duration_s, status (ok/overdue/never_run/on_demand),
    and minutes_overdue.

    Requires ``X-Ops-Key`` header matching the ``OPS_API_KEY`` env var.
    """
    err = _check_ops_key(request)
    if err is not None:
        return err

    health = get_worker_health()

    # Fire-and-forget: send Telegram alert if any workers are overdue (1h cooldown)
    try:
        await check_and_alert_overdue()
    except Exception:
        _log.debug("[worker-health] overdue alert check failed", exc_info=True)

    return JSONResponse(health)


@router.get("/admin/demand-summary", summary="Catalog demand signals summary")
async def demand_summary(request: Request) -> JSONResponse:
    """Return a summary of catalog demand signals for the app owner.

    Includes:
    - pending_suggestions: count of unprocessed suggestions
    - new_categories_watching: count of category candidates in 'watching' status
    - top_requested_items: items requested by most unique users, not yet in catalog
    - top_requested_categories: category candidates sorted by unique users
    - daily_request_counts: suggestion submissions per day for last 7 days

    Requires ``X-Ops-Key`` header matching the ``OPS_API_KEY`` env var.
    """
    err = _check_ops_key(request)
    if err is not None:
        return err

    pool = get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={"detail": "Database not available"},
        )

    try:
        # Pending suggestions count
        pending_count: int = await pool.fetchval(
            "SELECT count(*) FROM catalog_suggestions WHERE status = 'pending'"
        ) or 0

        # Watching category candidates count
        watching_count: int = await pool.fetchval(
            "SELECT count(*) FROM category_candidates WHERE status = 'watching'"
        ) or 0

        # Top requested items (by unique user count, still pending)
        top_items_rows = await pool.fetch(
            """
            SELECT lower(suggested_name) AS name,
                   suggested_category,
                   count(*) AS total_requests,
                   count(DISTINCT user_id) AS unique_users,
                   max(created_at) AS last_requested
            FROM catalog_suggestions
            WHERE status = 'pending'
            GROUP BY lower(suggested_name), suggested_category
            ORDER BY unique_users DESC, total_requests DESC
            LIMIT 20
            """
        )
        top_items: list[dict[str, Any]] = [
            {
                "name": r["name"],
                "suggested_category": r["suggested_category"],
                "total_requests": r["total_requests"],
                "unique_users": r["unique_users"],
                "last_requested": r["last_requested"].isoformat() if r["last_requested"] else None,
            }
            for r in top_items_rows
        ]

        # Top requested categories (from category_candidates)
        top_cats_rows = await pool.fetch(
            """
            SELECT proposed_name, proposed_slug, signal_count,
                   unique_users, status, first_seen, last_seen
            FROM category_candidates
            ORDER BY unique_users DESC, signal_count DESC
            LIMIT 20
            """
        )
        top_categories: list[dict[str, Any]] = [
            {
                "name": r["proposed_name"],
                "slug": r["proposed_slug"],
                "signal_count": r["signal_count"],
                "unique_users": r["unique_users"],
                "status": r["status"],
                "first_seen": r["first_seen"].isoformat() if r["first_seen"] else None,
                "last_seen": r["last_seen"].isoformat() if r["last_seen"] else None,
            }
            for r in top_cats_rows
        ]

        # Daily request counts for last 7 days
        daily_rows = await pool.fetch(
            """
            SELECT date_trunc('day', created_at)::date AS day,
                   count(*) AS requests,
                   count(DISTINCT user_id) AS unique_users
            FROM catalog_suggestions
            WHERE created_at >= now() - interval '7 days'
            GROUP BY date_trunc('day', created_at)::date
            ORDER BY day DESC
            """
        )
        daily_counts: list[dict[str, Any]] = [
            {
                "day": r["day"].isoformat() if r["day"] else None,
                "requests": r["requests"],
                "unique_users": r["unique_users"],
            }
            for r in daily_rows
        ]

        return JSONResponse({
            "pending_suggestions": pending_count,
            "new_categories_watching": watching_count,
            "top_requested_items": top_items,
            "top_requested_categories": top_categories,
            "daily_request_counts": daily_counts,
        })

    except Exception as exc:
        _log.error("[admin-demand-summary] Failed: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to fetch demand summary"},
        )


# ---------------------------------------------------------------------------
# Spend Monitor endpoints
# ---------------------------------------------------------------------------

from app.lib.spend_tracker import spend_tracker  # noqa: E402


@router.get("/admin/spend-summary", summary="Monthly API spend summary")
async def spend_summary(request: Request) -> JSONResponse:
    """Return current month spend vs budget, per-provider breakdown."""
    err = _check_ops_key(request)
    if err is not None:
        return err
    return JSONResponse(spend_tracker.summary())


@router.post("/admin/spend-budget", summary="Update monthly budget")
async def spend_budget(request: Request) -> JSONResponse:
    """Set the monthly budget cap (EUR). Body: {"budget_eur": 150.0}"""
    err = _check_ops_key(request)
    if err is not None:
        return err
    try:
        body = await request.json()
        budget = float(body.get("budget_eur", 150.0))
        spend_tracker.set_budget(budget)
        return JSONResponse({"ok": True, "budget_eur": budget})
    except Exception as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})


@router.post("/admin/spend-pause", summary="Pause or resume a provider")
async def spend_pause(request: Request) -> JSONResponse:
    """Pause/resume a provider. Body: {"provider": "openai", "paused": true}"""
    err = _check_ops_key(request)
    if err is not None:
        return err
    try:
        body = await request.json()
        provider = body["provider"]
        paused = body.get("paused", True)
        if paused:
            spend_tracker.pause_provider(provider)
        else:
            spend_tracker.resume_provider(provider)
        return JSONResponse({"ok": True, "provider": provider, "paused": paused})
    except Exception as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})


@router.post("/admin/spend-reset", summary="Reset spend counters")
async def spend_reset(request: Request) -> JSONResponse:
    """Reset all spend counters for current month."""
    err = _check_ops_key(request)
    if err is not None:
        return err
    spend_tracker.reset()
    return JSONResponse({"ok": True, "message": "Spend counters reset"})


@router.get("/admin/bake-summary", summary="Data-bake aggregate health snapshot")
async def bake_summary(request: Request) -> JSONResponse:
    """Single-call health snapshot for the data-bake operator.

    Aggregates everything an operator wants to know during the pre-launch
    bake into one JSON payload — used by ``scripts/bake_status.sh`` and the
    daily Telegram digest.
    """
    err = _check_ops_key(request)
    if err is not None:
        return err

    out: dict[str, Any] = {
        "ok": True,
        "workers": {},
        "rows": {},
        "spend": {},
        "data_sources": {},
        "warnings": [],
    }

    # 1. Worker health (reuse the same internal function /admin/worker-health calls)
    try:
        health = get_worker_health()
        out["workers"] = health
        # Count overdue / errored workers as warnings
        overdue = [w["name"] for w in health.get("workers", []) if w.get("overdue")]
        errored = [w["name"] for w in health.get("workers", []) if w.get("last_status") == "error"]
        if overdue:
            out["warnings"].append(f"overdue workers: {', '.join(overdue)}")
        if errored:
            out["warnings"].append(f"errored workers: {', '.join(errored)}")
    except Exception as exc:
        out["warnings"].append(f"worker health unavailable: {exc}")

    # 2. Row counts that prove the bake is actually accumulating
    pool = get_pool()
    if pool is not None:
        try:
            row_queries = {
                "category_items_total": "SELECT count(*) FROM public.category_items",
                "market_hits_total": "SELECT count(*) FROM public.market_hits",
                # market_hits has `seen_at` (legacy) instead of created_at on this prod DB
                "market_hits_24h": "SELECT count(*) FROM public.market_hits WHERE seen_at > now() - interval '24 hours'",
                "price_predictions_total": "SELECT count(*) FROM public.price_predictions",
                # generated_at is the partition key; using created_at
                # works (column exists) but skips partition prune so the
                # planner walks every monthly partition on every admin
                # health-check tick. generated_at + the time filter
                # gives Subplans Removed > 0 in EXPLAIN.
                "price_predictions_24h": "SELECT count(*) FROM public.price_predictions WHERE generated_at > now() - interval '24 hours'",
                "mandate_deals_total": "SELECT count(*) FROM public.mandate_deals",
                "alert_history_24h": "SELECT count(*) FROM public.alert_trigger_history WHERE created_at > now() - interval '24 hours'",
            }
            for key, sql in row_queries.items():
                try:
                    out["rows"][key] = await pool.fetchval(sql) or 0
                except Exception as exc:
                    out["rows"][key] = None
                    _log.debug("[bake-summary] %s failed: %s", key, exc)
        except Exception as exc:
            out["warnings"].append(f"row counts unavailable: {exc}")
    else:
        out["warnings"].append("DB pool unavailable")

    # 3. Spend snapshot (already exposed via spend_tracker.summary())
    try:
        out["spend"] = spend_tracker.summary()
    except Exception as exc:
        out["warnings"].append(f"spend summary unavailable: {exc}")

    # 4. Which data sources are actually configured (no secret values, just bools)
    out["data_sources"] = {
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "firecrawl": bool(os.getenv("FIRECRAWL_API_KEY")),
        "scrapedo": bool(os.getenv("SCRAPEDO_API_KEY")),
        "serpapi": bool(os.getenv("SERPAPI_API_KEY")),
        "ebay": bool(os.getenv("EBAY_APP_ID") or os.getenv("EBAY_CLIENT_ID")),
        "tcgplayer": bool(os.getenv("TCGPLAYER_PUBLIC_KEY") or os.getenv("TCGPLAYER_BEARER_TOKEN")),
        "discogs": bool(os.getenv("DISCOGS_PERSONAL_TOKEN")),
        "etsy": bool(os.getenv("ETSY_API_KEY")),
        "rebrickable": bool(os.getenv("REBRICKABLE_API_KEY")),
        "pokemontcg": bool(os.getenv("POKEMONTCG_API_KEY")),
        "cardmarket": bool(os.getenv("CARDMARKET_APP_TOKEN")),
        "stockx": bool(os.getenv("STOCKX_API_KEY")),
        "pricecharting": bool(os.getenv("PRICECHARTING_API_KEY")),
        "bricklink": bool(os.getenv("BRICKLINK_CONSUMER_KEY")),
        "fal": bool(os.getenv("FAL_KEY")),
        "telegram": bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID")),
    }
    active_sources = [k for k, v in out["data_sources"].items() if v]
    out["data_sources"]["_active_count"] = len(active_sources)

    # Operator-friendly warnings
    if out["rows"].get("category_items_total", 0) == 0:
        out["warnings"].append("category_items is empty — run pipelines/import_all")
    if out["rows"].get("market_hits_24h", 0) == 0 and out["rows"].get("market_hits_total", 0) == 0:
        out["warnings"].append("no market_hits ever — workers may not be running")
    pct = out["spend"].get("pct_used", 0) or 0
    if pct >= 75:
        out["warnings"].append(f"spend at {pct:.0f}% of budget")

    out["ok"] = len(out["warnings"]) == 0
    return JSONResponse(out)


# ---------------------------------------------------------------------------
# GET /admin/models  —  ML model registry
# ---------------------------------------------------------------------------
# The admin dashboard's ML Models tab called this and /admin/metrics; neither
# existed, so every request 404'd and the tab silently rendered a hardcoded
# DEMO_MODELS list. Both are now served from model_registry / model_metrics.


@router.get("/admin/models", summary="Registered ML models per category")
async def admin_models(request: Request):
    """Per-category model versions, newest first."""
    if (err := _check_ops_key(request)) is not None:
        return err

    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"detail": "Database unavailable"})

    try:
        # model_metrics is the only per-category source: model_registry rows are
        # per training run (name='price'), not per collectible category.
        # DISTINCT ON picks each category's most recently evaluated version.
        rows = await pool.fetch(
            """
            SELECT DISTINCT ON (category)
                   category,
                   model_version AS version,
                   computed_at
            FROM model_metrics
            WHERE category IS NOT NULL AND category <> 'unknown'
            ORDER BY category, computed_at DESC
            """
        )
        registry = await pool.fetch(
            "SELECT name, version, uri, is_canary, created_at "
            "FROM model_registry ORDER BY created_at DESC LIMIT 50"
        )
    except Exception as exc:
        _log.exception("admin/models query failed")
        return JSONResponse(status_code=500, content={"detail": f"Query failed: {exc}"})

    latest = registry[0]["version"] if registry else None
    models = [
        {
            "category": r["category"],
            "version": r["version"],
            # "active" means this category's newest evaluated version matches the
            # newest registry version; anything older is stale, not active.
            "status": "active" if latest and r["version"] == latest else "stale",
            "artifact_uri": None,
            "evaluated_at": r["computed_at"].isoformat() if r["computed_at"] else None,
        }
        for r in rows
    ]

    return JSONResponse(
        content={
            "models": models,
            "registry": [
                {
                    "name": r["name"],
                    "version": r["version"],
                    "uri": r["uri"],
                    "is_canary": r["is_canary"],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                }
                for r in registry
            ],
        }
    )


# ---------------------------------------------------------------------------
# GET /admin/metrics  —  model accuracy + recent prediction volume
# ---------------------------------------------------------------------------


_METRICS_CACHE: dict[str, Any] = {"at": 0.0, "payload": None}
_METRICS_TTL_S = 600  # 10 min: the rollup is refreshed once a day by cron
_METRICS_REFRESHING = False


def _seven_day_window_label() -> str:
    from datetime import date, timedelta
    return f"{(date.today() - timedelta(days=7)).isoformat()}..{date.today().isoformat()}"


@router.get("/admin/metrics", summary="Model MAE and 7-day prediction counts")
async def admin_metrics(request: Request):
    """MAE per category plus 7-day prediction volume.

    Cached for 10 minutes. The underlying scan is ~1-2s over 180k rollup rows,
    and the admin client aborts at 5s and silently substitutes demo data — so
    an uncached endpoint would render fabricated numbers most of the time.
    """
    if (err := _check_ops_key(request)) is not None:
        return err

    import time as _time

    fresh = _METRICS_CACHE["payload"] is not None and (
        _time.monotonic() - _METRICS_CACHE["at"] < _METRICS_TTL_S
    )
    if fresh:
        return JSONResponse(content=_METRICS_CACHE["payload"])

    # Stale-while-revalidate. The scan costs 20s+ through the pooler (which
    # caps at 30s and returned a 500 on a cold call), while the admin client
    # aborts at 5s and silently substitutes demo data. So a request must never
    # wait on it: serve what we have and refresh out of band.
    if not _METRICS_REFRESHING:
        spawn_bg(_refresh_metrics_cache(), "admin_metrics_refresh")

    if _METRICS_CACHE["payload"] is not None:
        stale = dict(_METRICS_CACHE["payload"])
        stale["stale"] = True
        return JSONResponse(content=stale)

    # Cold start: empty and explicitly labelled. Empty-and-honest beats
    # fabricated-and-plausible, which is what the client shows on a timeout.
    return JSONResponse(
        content={"mae": [], "counts_7d": [], "warming": True,
                 "detail": "metrics are being computed — reload in a few seconds"}
    )

async def _refresh_metrics_cache() -> None:
    """Recompute the metrics payload out of band. Never raises to the caller.

    The guard flag is reset in a finally that wraps EVERY exit path, including
    the no-pool early return — leaving it set would permanently block all
    future refreshes and freeze the cache at whatever it last held.
    """
    global _METRICS_REFRESHING
    from time import monotonic

    _METRICS_REFRESHING = True
    try:
        pool = await get_pool()
        if pool is None:
            _log.warning("admin/metrics refresh skipped — no DB pool")
            return

        mae = await pool.fetch(
            """
            SELECT DISTINCT ON (category, model_version)
                   category, model_version, mae, mape, n
            FROM model_metrics
            WHERE category IS NOT NULL AND category <> 'unknown'
            ORDER BY category, model_version, computed_at DESC
            """
        )
        # Grouped by category only: AdminMLModels sums every row for a category
        # (countForCategory) and never reads the per-day split, so grouping by
        # day returned 7x the rows for no rendered benefit.
        #
        # Reads the price_prediction_daily rollup rather than the raw
        # partitioned table, and needs idx_ppd_day — without that index this
        # seq-scans 1.2GB and takes 6.3s.
        counts = await pool.fetch(
            """
            SELECT category, SUM(n_predictions)::int AS n
            FROM price_prediction_daily
            WHERE day >= (CURRENT_DATE - 7)
            GROUP BY category
            ORDER BY n DESC
            LIMIT 200
            """
        )

        _METRICS_CACHE["payload"] = {
            "mae": [
                {
                    "category": r["category"],
                    "model_version": r["model_version"],
                    "mae": float(r["mae"]) if r["mae"] is not None else None,
                    "mape": float(r["mape"]) if r["mape"] is not None else None,
                    "n": r["n"] or 0,
                }
                for r in mae
            ],
            "counts_7d": [
                {
                    "category": r["category"] or "unknown",
                    "model_version": "",
                    # Kept for the CountsRow shape the client expects; the value
                    # is the 7-day window, not a single day.
                    "day": _seven_day_window_label(),
                    "n": r["n"],
                }
                for r in counts
            ],
        }
        _METRICS_CACHE["at"] = monotonic()
        _log.info(
            "admin/metrics cache refreshed: %d mae rows, %d category counts",
            len(mae), len(counts),
        )
    except Exception:
        # Cache left untouched so a failed refresh serves the last good value
        # rather than reverting to empty.
        _log.exception("admin/metrics refresh failed")
    finally:
        _METRICS_REFRESHING = False


# ---------------------------------------------------------------------------
# GET /admin/kpi-summary  —  real acquisition funnel
# ---------------------------------------------------------------------------
# The KPI Funnel tab called this and got 404, so the tab named for the funnel
# had no backend at all. Built from the app's own tables: profiles for signups
# and subscription_events for paid conversions. There is deliberately no
# in-app engagement step here — that needs PostHog, which is not yet wired
# (EXPO_PUBLIC_POSTHOG_KEY unset), and inventing one would be fiction.


@router.get("/admin/kpi-summary", summary="Acquisition funnel summary")
async def admin_kpi_summary(request: Request, days: int = 30):
    """Signups, attributed signups, and paid conversions over `days`."""
    if (err := _check_ops_key(request)) is not None:
        return err

    pool = await get_pool()
    if pool is None:
        return JSONResponse(status_code=503, content={"detail": "Database unavailable"})

    days = max(1, min(int(days or 30), 365))

    try:
        signups = await pool.fetchrow(
            """
            SELECT COUNT(*)::int AS total,
                   COUNT(referred_by_code)::int AS attributed
            FROM profiles
            WHERE created_at >= now() - make_interval(days => $1)
            """,
            days,
        )
        conv = await pool.fetchrow(
            """
            SELECT COUNT(*)::int AS paid_events,
                   COUNT(DISTINCT user_id)::int AS paying_users,
                   COALESCE(SUM(revenue_cents), 0)::bigint AS revenue_cents,
                   COUNT(*) FILTER (WHERE affiliate_code IS NOT NULL)::int AS attributed_events
            FROM subscription_events
            WHERE occurred_at >= now() - make_interval(days => $1)
              AND revenue_cents > 0
            """,
            days,
        )
        active = await pool.fetchval(
            "SELECT COUNT(*)::int FROM subscriptions WHERE status = 'active' AND plan <> 'free'"
        )
    except Exception as exc:
        _log.exception("admin/kpi-summary query failed")
        return JSONResponse(status_code=500, content={"detail": f"Query failed: {exc}"})

    total = signups["total"] or 0
    paying = conv["paying_users"] or 0

    return JSONResponse(
        content={
            "period_days": days,
            "signups": total,
            "attributed_signups": signups["attributed"] or 0,
            "paid_events": conv["paid_events"] or 0,
            "paying_users": paying,
            "attributed_paid_events": conv["attributed_events"] or 0,
            "revenue_eur": round((conv["revenue_cents"] or 0) / 100, 2),
            "active_subscriptions": active or 0,
            "signup_to_paid_pct": round((paying / total) * 100, 1) if total else 0.0,
            # Named so the UI can say WHY a stage is absent instead of showing 0
            # as though it were measured.
            "unavailable": ["engagement (needs PostHog: EXPO_PUBLIC_POSTHOG_KEY unset)"],
        }
    )
