"""
Beta Signup Router — pre-launch email collection and admin listing.

Endpoints:
    POST /api/beta-signup       — Public endpoint for email signups
    GET  /ops/beta-signups      — Ops-key protected paginated signup list
"""

from __future__ import annotations

import logging
import re
import time
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from app.auth import require_ops_key
from app.db import get_pool
from app.errors import error_response

_log = logging.getLogger("collectai.beta_signup")

router = APIRouter(tags=["Beta"])

# ---------------------------------------------------------------------------
# Email validation regex (same approach as rest of codebase — no new deps)
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

# ---------------------------------------------------------------------------
# In-memory IP rate limiting: 5 signups per IP per hour
# ---------------------------------------------------------------------------
_RATE_LIMIT: dict[str, list[float]] = {}
_RATE_WINDOW = 3600  # seconds
_RATE_MAX = 5


def _check_rate_limit(ip: str) -> bool:
    """Return True if the IP is within rate limits, False if exceeded."""
    now = time.monotonic()
    timestamps = _RATE_LIMIT.get(ip, [])
    # Prune old entries
    timestamps = [t for t in timestamps if now - t < _RATE_WINDOW]
    if len(timestamps) >= _RATE_MAX:
        _RATE_LIMIT[ip] = timestamps
        return False
    timestamps.append(now)
    _RATE_LIMIT[ip] = timestamps
    return True


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------


class BetaSignupRequest(BaseModel):
    email: str
    referral_source: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Email is required")
        if not _EMAIL_RE.match(v):
            raise ValueError("Invalid email address")
        return v.lower()


# ---------------------------------------------------------------------------
# POST /api/beta-signup — public, no auth
# ---------------------------------------------------------------------------


@router.post("/api/beta-signup", summary="Submit beta signup")
async def beta_signup(body: BetaSignupRequest, request: Request):
    """Collect a beta signup email. Public endpoint — no auth required."""
    pool = get_pool()
    if pool is None:
        raise error_response(503, "Service temporarily unavailable", code="DB_UNAVAILABLE")

    # IP-based rate limiting
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    ip = forwarded or (request.client.host if request.client else "unknown")
    if not _check_rate_limit(ip):
        raise error_response(429, "Too many attempts. Please wait.", code="RATE_LIMITED")

    try:
        await pool.execute(
            """
            INSERT INTO beta_signups (email, referral_source, ip_address)
            VALUES ($1, $2, $3)
            """,
            body.email,
            body.referral_source,
            ip,
        )
    except Exception as exc:
        # asyncpg UniqueViolationError
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
            raise error_response(409, "You're already on the list!", code="ALREADY_SIGNED_UP")
        _log.error("Beta signup insert failed: %s", exc)
        raise error_response(500, "Signup failed", code="INSERT_ERROR")

    _log.info("Beta signup: %s (ref=%s)", body.email, body.referral_source)
    return JSONResponse({"message": "You're on the list!", "email": body.email})


# ---------------------------------------------------------------------------
# GET /ops/beta-signups — ops-key protected
# ---------------------------------------------------------------------------


@router.get("/ops/beta-signups", summary="List beta signups")
async def list_beta_signups(
    _: bool = Depends(require_ops_key),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    """Return paginated beta signup list. Ops-key required."""
    pool = get_pool()
    if pool is None:
        return JSONResponse({"signups": [], "total": 0, "page": page})

    offset = (page - 1) * per_page

    try:
        total = await pool.fetchval("SELECT count(*) FROM beta_signups") or 0

        rows = await pool.fetch(
            """
            SELECT id, email, referral_source, ip_address, signed_up_at
            FROM beta_signups
            ORDER BY signed_up_at DESC
            LIMIT $1 OFFSET $2
            """,
            per_page,
            offset,
        )

        signups = [
            {
                "id": str(r["id"]),
                "email": r["email"],
                "referral_source": r["referral_source"],
                "ip_address": r["ip_address"],
                "signed_up_at": r["signed_up_at"].isoformat() if r["signed_up_at"] else None,
            }
            for r in rows
        ]

        return JSONResponse({
            "signups": signups,
            "total": total,
            "page": page,
            "per_page": per_page,
        })
    except Exception as exc:
        _log.warning("Beta signups list query failed: %s", exc)
        return JSONResponse({"signups": [], "total": 0, "error": str(exc)})
