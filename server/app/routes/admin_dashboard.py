"""
Ops Admin Dashboard — server-rendered HTML dashboard for system monitoring.

Endpoints:
    GET /ops/dashboard          — Main dashboard HTML page
    GET /ops/dashboard/users    — User management JSON endpoint
    GET /ops/dashboard/stats    — System stats JSON endpoint
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse

from app.auth import require_ops_key
from app.config import DB_ENABLED, SERVICE_VERSION, DEV_MODE
from app.db import get_pool

_log = logging.getLogger("collectai.admin")

router = APIRouter(prefix="/ops/dashboard", tags=["Ops"])

# ---------------------------------------------------------------------------
# Stats endpoint
# ---------------------------------------------------------------------------


@router.get("/stats", summary="Get dashboard stats")
async def dashboard_stats(_: bool = Depends(require_ops_key)):
    """Return system statistics for the admin dashboard."""
    stats: dict[str, Any] = {
        "version": SERVICE_VERSION,
        "dev_mode": DEV_MODE,
        "db_enabled": DB_ENABLED,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    pool = get_pool()
    if pool is None:
        stats["db_status"] = "disconnected"
        return JSONResponse(stats)

    stats["db_status"] = "connected"

    try:
        # User count
        stats["total_users"] = await pool.fetchval(
            "SELECT count(*) FROM auth.users"
        ) or 0

        # Subscription breakdown
        rows = await pool.fetch(
            "SELECT plan, count(*) as cnt FROM subscriptions GROUP BY plan"
        )
        stats["subscriptions"] = {r["plan"]: r["cnt"] for r in rows} if rows else {}

        # Active mandates
        stats["active_mandates"] = await pool.fetchval(
            "SELECT count(*) FROM purchase_mandates WHERE status = 'active'"
        ) or 0

        # Items
        stats["total_items"] = await pool.fetchval(
            "SELECT count(*) FROM category_items"
        ) or 0

        # Events
        stats["total_events"] = await pool.fetchval(
            "SELECT count(*) FROM events"
        ) or 0

        # Beta signups
        try:
            stats["beta_signups"] = await pool.fetchval(
                "SELECT count(*) FROM beta_signups"
            ) or 0
        except asyncpg.PostgresError:
            _log.warning("beta_signups table query failed (table may not exist)")
            stats["beta_signups"] = 0

        # Recent signups (last 7 days)
        stats["recent_signups"] = await pool.fetchval(
            "SELECT count(*) FROM auth.users WHERE created_at > now() - interval '7 days'"
        ) or 0

        # Catalog learning stats
        try:
            stats["catalog_suggestions_pending"] = await pool.fetchval(
                "SELECT count(*) FROM catalog_suggestions WHERE status = 'pending'"
            ) or 0
            stats["catalog_suggestions_mapped_week"] = await pool.fetchval(
                "SELECT count(*) FROM catalog_suggestions WHERE status = 'mapped' AND updated_at > now() - interval '7 days'"
            ) or 0
            stats["category_candidates_watching"] = await pool.fetchval(
                "SELECT count(*) FROM category_candidates WHERE status = 'watching'"
            ) or 0
            stats["category_candidates_candidate"] = await pool.fetchval(
                "SELECT count(*) FROM category_candidates WHERE status = 'candidate'"
            ) or 0
        except asyncpg.PostgresError:
            # Tables may not exist yet
            _log.warning("Catalog learning tables query failed (tables may not exist yet)")
            stats["catalog_suggestions_pending"] = 0
            stats["catalog_suggestions_mapped_week"] = 0
            stats["category_candidates_watching"] = 0
            stats["category_candidates_candidate"] = 0

    except Exception as exc:
        _log.warning("Dashboard stats query failed: %s", exc)
        stats["db_error"] = str(exc)

    return JSONResponse(stats)


# ---------------------------------------------------------------------------
# Users endpoint
# ---------------------------------------------------------------------------


@router.get("/users", summary="List users")
async def dashboard_users(
    _: bool = Depends(require_ops_key),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    """Return paginated user list with subscription status."""
    pool = get_pool()
    if pool is None:
        return JSONResponse({"users": [], "total": 0, "page": page})

    offset = (page - 1) * per_page

    try:
        total = await pool.fetchval("SELECT count(*) FROM auth.users") or 0

        rows = await pool.fetch(
            """
            SELECT
                u.id, u.email, u.created_at,
                COALESCE(s.plan, 'free') as plan,
                COALESCE(s.status, 'active') as sub_status,
                COALESCE(mc.cnt, 0) as mandate_count,
                COALESCE(ic.cnt, 0) as item_count
            FROM auth.users u
            LEFT JOIN subscriptions s ON s.user_id = u.id
            LEFT JOIN LATERAL (
                SELECT count(*) AS cnt FROM purchase_mandates m WHERE m.user_id = u.id
            ) mc ON true
            LEFT JOIN LATERAL (
                SELECT count(*) AS cnt FROM category_items ci WHERE ci.user_id = u.id::text
            ) ic ON true
            ORDER BY u.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            per_page,
            offset,
        )

        users = [
            {
                "id": str(r["id"]),
                "email": r["email"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "plan": r["plan"],
                "sub_status": r["sub_status"],
                "mandate_count": r["mandate_count"],
                "item_count": r["item_count"],
            }
            for r in rows
        ]

        return JSONResponse({"users": users, "total": total, "page": page, "per_page": per_page})
    except Exception as exc:
        _log.warning("Dashboard users query failed: %s", exc)
        return JSONResponse({"users": [], "total": 0, "error": str(exc)})


# ---------------------------------------------------------------------------
# Sponsor analytics endpoint
# ---------------------------------------------------------------------------


@router.get("/sponsor-analytics", tags=["Ops"], summary="Get sponsor analytics")
async def sponsor_analytics(_: bool = Depends(require_ops_key)):
    """List all sponsored events with analytics data."""
    pool = get_pool()
    if pool is None:
        return JSONResponse({"sponsored_events": [], "error": "DB not available"})

    try:
        rows = await pool.fetch(
            """
            SELECT e.id, e.title, e.sponsor_name, e.sponsor_tier,
                   e.sponsor_paid_at, e.sponsor_expires_at, e.category_id,
                   COALESCE(sa.impressions, 0) AS impressions,
                   COALESCE(sa.clicks, 0) AS clicks,
                   COALESCE(sa.rsvps, 0) AS rsvps
            FROM events e
            LEFT JOIN event_sponsor_analytics sa ON sa.event_id = e.id
            WHERE e.is_sponsored = true
            ORDER BY e.sponsor_paid_at DESC NULLS LAST
            """
        )
        events = []
        for r in rows:
            events.append({
                "id": str(r["id"]),
                "title": r["title"],
                "sponsor_name": r["sponsor_name"],
                "sponsor_tier": r["sponsor_tier"],
                "category_id": r["category_id"],
                "sponsor_paid_at": str(r["sponsor_paid_at"]) if r["sponsor_paid_at"] else None,
                "sponsor_expires_at": str(r["sponsor_expires_at"]) if r["sponsor_expires_at"] else None,
                "impressions": r["impressions"],
                "clicks": r["clicks"],
                "rsvps": r["rsvps"],
            })
        return JSONResponse({"sponsored_events": events, "total": len(events)})
    except Exception as exc:
        _log.error("Failed to fetch sponsor analytics: %s", exc)
        return JSONResponse({"sponsored_events": [], "error": str(exc)})


# ---------------------------------------------------------------------------
# Worker health endpoint
# ---------------------------------------------------------------------------


@router.get("/workers/health", tags=["Ops"], summary="Get worker health status")
async def workers_health(_: bool = Depends(require_ops_key)):
    """Return health status for all registered workers.

    Each worker shows: name, last_run, expected_interval_minutes,
    status (ok/overdue/never_run/on_demand), minutes_overdue.
    Workers are sorted with overdue first for quick triage.
    """
    from app.worker_registry import get_worker_health
    return JSONResponse(get_worker_health())


# ---------------------------------------------------------------------------
# Main dashboard HTML
# ---------------------------------------------------------------------------


@router.get("", response_class=HTMLResponse, summary="Render admin dashboard")
async def dashboard_page(_: bool = Depends(require_ops_key)):
    """Render the admin dashboard as a self-contained HTML page."""
    return HTMLResponse(_DASHBOARD_HTML)


_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>CollectAI Admin Dashboard</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f8fafc; color: #0f172a; }
        .header { background: #81D8D0; padding: 20px 32px; display: flex; align-items: center; gap: 12px; }
        .header h1 { font-size: 22px; font-weight: 800; color: #fff; }
        .header .version { font-size: 13px; color: rgba(255,255,255,0.8); margin-left: auto; }
        .container { max-width: 1200px; margin: 24px auto; padding: 0 24px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 32px; }
        .card { background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
        .card .label { font-size: 13px; color: #64748b; margin-bottom: 4px; }
        .card .value { font-size: 28px; font-weight: 700; }
        .card .sub { font-size: 12px; color: #94a3b8; margin-top: 2px; }
        .section { margin-bottom: 32px; }
        .section h2 { font-size: 18px; font-weight: 700; margin-bottom: 12px; }
        table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
        th { text-align: left; padding: 12px 16px; background: #f1f5f9; font-size: 12px; text-transform: uppercase; color: #64748b; font-weight: 600; }
        td { padding: 10px 16px; border-top: 1px solid #f1f5f9; font-size: 14px; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; }
        .badge-free { background: #f1f5f9; color: #64748b; }
        .badge-pro { background: #dbeafe; color: #1d4ed8; }
        .badge-premium { background: #fef3c7; color: #b45309; }
        .badge-active { background: #d1fae5; color: #065f46; }
        .badge-canceled { background: #fee2e2; color: #991b1b; }
        .badge-past_due { background: #fef3c7; color: #92400e; }
        .loading { text-align: center; color: #94a3b8; padding: 40px; }
        .error { color: #ef4444; padding: 12px; background: #fef2f2; border-radius: 8px; }
        .refresh { background: #81D8D0; color: #fff; border: none; padding: 8px 16px; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 13px; }
        .refresh:hover { background: #5FBFB6; }
    </style>
</head>
<body>
    <div class="header">
        <h1>CollectAI Admin</h1>
        <span class="version" id="version">Loading...</span>
    </div>
    <div class="container">
        <div style="display:flex;justify-content:flex-end;margin-bottom:16px;">
            <button class="refresh" onclick="loadAll()">Refresh</button>
        </div>

        <div class="grid" id="stats-grid">
            <div class="card"><div class="label">Loading...</div></div>
        </div>

        <div class="section">
            <h2>Recent Users</h2>
            <div id="users-table"><div class="loading">Loading users...</div></div>
        </div>
    </div>

    <script>
        function esc(s) {
            if (s == null) return '';
            const d = document.createElement('div');
            d.appendChild(document.createTextNode(String(s)));
            return d.innerHTML;
        }
        const KEY = new URLSearchParams(window.location.search).get('key') || '';
        const headers = KEY ? { 'X-Ops-Key': KEY } : {};

        async function loadStats() {
            try {
                const res = await fetch('/ops/dashboard/stats', { headers });
                const d = await res.json();
                document.getElementById('version').textContent = 'v' + (d.version || '?') + (d.dev_mode ? ' (DEV)' : '');
                const subs = d.subscriptions || {};
                document.getElementById('stats-grid').innerHTML = `
                    <div class="card"><div class="label">Total Users</div><div class="value">${esc(d.total_users ?? '?')}</div><div class="sub">Last 7d: +${esc(d.recent_signups ?? 0)}</div></div>
                    <div class="card"><div class="label">Free</div><div class="value">${esc(subs.free ?? 0)}</div></div>
                    <div class="card"><div class="label">Pro</div><div class="value">${esc(subs.pro ?? 0)}</div></div>
                    <div class="card"><div class="label">Premium</div><div class="value">${esc(subs.premium ?? 0)}</div></div>
                    <div class="card"><div class="label">Items</div><div class="value">${esc(d.total_items ?? 0)}</div></div>
                    <div class="card"><div class="label">Active Mandates</div><div class="value">${esc(d.active_mandates ?? 0)}</div></div>
                    <div class="card"><div class="label">Events</div><div class="value">${esc(d.total_events ?? 0)}</div></div>
                    <div class="card"><div class="label">DB Status</div><div class="value" style="font-size:16px">${esc(d.db_status ?? 'unknown')}</div></div>
                    <div class="card"><div class="label">Beta Signups</div><div class="value">${esc(d.beta_signups ?? 0)}</div><div class="sub">Pre-launch waitlist</div></div>
                    <div class="card"><div class="label">Catalog Queue</div><div class="value">${esc(d.catalog_suggestions_pending ?? 0)}</div><div class="sub">Mapped this week: ${esc(d.catalog_suggestions_mapped_week ?? 0)}</div></div>
                    <div class="card"><div class="label">Category Candidates</div><div class="value">${esc((d.category_candidates_watching ?? 0) + (d.category_candidates_candidate ?? 0))}</div><div class="sub">Watching: ${esc(d.category_candidates_watching ?? 0)} | Candidate: ${esc(d.category_candidates_candidate ?? 0)}</div></div>
                `;
            } catch(e) {
                document.getElementById('stats-grid').innerHTML = '<div class="error">Failed to load stats: ' + esc(e.message) + '</div>';
            }
        }

        async function loadUsers() {
            try {
                const res = await fetch('/ops/dashboard/users?per_page=25', { headers });
                const d = await res.json();
                if (!d.users || d.users.length === 0) {
                    document.getElementById('users-table').innerHTML = '<div class="loading">No users found</div>';
                    return;
                }
                let html = '<table><thead><tr><th>Email</th><th>Plan</th><th>Status</th><th>Items</th><th>Mandates</th><th>Joined</th></tr></thead><tbody>';
                for (const u of d.users) {
                    const date = u.created_at ? new Date(u.created_at).toLocaleDateString() : '?';
                    const planCls = ['free','pro','premium'].includes(u.plan) ? u.plan : 'free';
                    const statusCls = ['active','canceled','past_due'].includes(u.sub_status) ? u.sub_status : 'active';
                    html += `<tr>
                        <td>${esc(u.email || u.id.slice(0,8))}</td>
                        <td><span class="badge badge-${planCls}">${esc(u.plan)}</span></td>
                        <td><span class="badge badge-${statusCls}">${esc(u.sub_status)}</span></td>
                        <td>${esc(u.item_count)}</td>
                        <td>${esc(u.mandate_count)}</td>
                        <td>${esc(date)}</td>
                    </tr>`;
                }
                html += '</tbody></table>';
                document.getElementById('users-table').innerHTML = html;
            } catch(e) {
                document.getElementById('users-table').innerHTML = '<div class="error">Failed to load users: ' + esc(e.message) + '</div>';
            }
        }

        function loadAll() { loadStats(); loadUsers(); }
        loadAll();
    </script>
</body>
</html>"""
