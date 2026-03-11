"""
MFA (Multi-Factor Authentication) router — TOTP enrollment status.

Endpoints:
    GET  /auth/mfa/status   — Check if user has MFA enrolled
    POST /auth/mfa/unenroll — Unenroll a TOTP factor (requires factor_id)

Note: MFA enrollment and verification is handled client-side via Supabase Auth SDK.
The backend only needs to check MFA status for gating and provide unenroll capability.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.auth import get_current_user_id
from app.config import SUPABASE_URL, SUPABASE_SERVICE_KEY
from app.errors import error_response
from app.rate_limit import per_user_rate_limit

_log = logging.getLogger("collectai.mfa")

router = APIRouter(prefix="/auth/mfa", tags=["Auth"])


def _get_supabase_admin():
    """Get a Supabase admin client for MFA factor management."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return None
    try:
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    except Exception:
        return None


@router.get("/status", summary="Get MFA enrollment status")
async def mfa_status(
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(per_user_rate_limit(20, scope="mfa")),
):
    """Check if the user has MFA enrolled."""
    admin = _get_supabase_admin()
    if not admin:
        # Without Supabase admin access, we can't check — return safe default
        return JSONResponse({
            "enrolled": False,
            "factors": [],
        })

    try:
        # Use admin API to list MFA factors for the user
        resp = admin.auth.admin.mfa_list_factors({"user_id": user_id})
        totp_factors = [
            {"id": f.id, "friendly_name": getattr(f, "friendly_name", None), "status": f.status}
            for f in (resp.totp or [])
        ]
        enrolled = any(f["status"] == "verified" for f in totp_factors)

        return JSONResponse({
            "enrolled": enrolled,
            "factors": totp_factors,
        })
    except Exception as exc:
        _log.warning("MFA status check failed: %s", exc)
        return JSONResponse({
            "enrolled": False,
            "factors": [],
            "error": "Could not check MFA status",
        })


@router.post("/unenroll", summary="Unenroll MFA factor")
async def mfa_unenroll(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(per_user_rate_limit(5, scope="mfa_unenroll")),
):
    """Unenroll a TOTP factor. Requires the factor_id in the request body."""
    admin = _get_supabase_admin()
    if not admin:
        raise error_response(503, "MFA management not available")

    body = await request.json()
    factor_id = body.get("factor_id")
    if not factor_id:
        raise error_response(400, "factor_id is required")

    try:
        admin.auth.admin.mfa_delete_factor({"user_id": user_id, "factor_id": factor_id})
        return JSONResponse({"success": True, "message": "MFA factor removed"})
    except Exception as exc:
        _log.warning("MFA unenroll failed for user %s: %s", user_id, exc)
        raise error_response(500, f"Failed to remove MFA factor: {exc}")
