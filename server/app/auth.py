from __future__ import annotations

import logging
from fastapi import Depends, Header, HTTPException, Request
from app.request_id import set_user_id
from app.config import DEV_MODE, DEV_USER_ID, JWT_SECRET, JWT_ISSUER, OPS_API_KEY, API_SHARED_SECRET

logger = logging.getLogger(__name__)


async def get_current_user_id(request: Request) -> str:
    """
    FastAPI dependency that extracts and validates a JWT from the
    Authorization header.

    Returns the ``sub`` claim (Supabase user-id) on success.

    Behaviour when no valid JWT is present:
    * **DEV_MODE=true** and no Authorization header  ->  returns a
      configurable dev user id (``DEV_USER_ID`` env var, default
      ``"dev-user-local"``).
    * Otherwise  ->  raises ``HTTPException(401)``.
    """
    auth_header = request.headers.get("authorization", "")

    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            import jwt as _jwt

            decode_opts: dict = {
                "algorithms": ["HS256"],
                "audience": "authenticated",
                "options": {"require": ["exp", "sub"]},
            }
            if JWT_ISSUER:
                decode_opts["issuer"] = JWT_ISSUER
            payload = _jwt.decode(token, JWT_SECRET, **decode_opts)
            user_id = payload.get("sub", "")
            if user_id:
                set_user_id(user_id)
                return user_id
            logger.warning("JWT decoded but 'sub' claim is empty")
        except ImportError:
            logger.error("PyJWT not installed — cannot validate tokens")
            raise HTTPException(status_code=500, detail="Auth module misconfigured")
        except Exception as exc:
            logger.warning("JWT validation failed: %s", type(exc).__name__)
            if not DEV_MODE:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required",
                )
            # In DEV_MODE, fall through to the dev-user path below

    # No Authorization header (or it was invalid in DEV_MODE)
    if DEV_MODE and not auth_header.startswith("Bearer "):
        dev_id = DEV_USER_ID or "dev-user-local"
        logger.debug("DEV_MODE active, returning dev user: %s", dev_id)
        set_user_id(dev_id)
        return dev_id

    raise HTTPException(status_code=401, detail="Authentication required")


# Backward-compatible alias so existing ``from app.auth import get_current_user``
# imports continue to work without changes in non-feature files.
get_current_user = get_current_user_id


async def get_optional_user_id(request: Request) -> str | None:
    """
    Like get_current_user_id but returns None instead of raising 401.

    Use this on read-only endpoints where anonymous access is allowed
    but authenticated users get personalised results (e.g. events feed).
    """
    try:
        return await get_current_user_id(request)
    except HTTPException:
        return None


async def require_seller_age_verified(
    user_id: str = Depends(get_current_user_id),
) -> str:
    """
    Reject the request if the user has not attested to being of legal selling
    age (profiles.seller_age_verified_at IS NULL).

    Use on every mutating /marketplace/listings/* endpoint (connect account,
    create listing, publish). Replaces the onboarding-time age checkbox with
    a point-of-sale gate — see docs/HYBRID_WEB_SUBSCRIPTION_PLAN.md style
    rationale and the 2026-05-18 onboarding rework.

    Returns the user_id (passing it through) so callers can chain:
        Depends(require_seller_age_verified)
    in place of Depends(get_current_user_id) when both auth and gate are needed.
    """
    from app.lib.db_helpers import get_db_pool
    from app.errors import error_response

    pool = get_db_pool()
    if pool is None:
        raise error_response(503, "Database unavailable")
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT seller_age_verified_at FROM profiles WHERE id = $1",
            user_id,
        )
    if row is None or row["seller_age_verified_at"] is None:
        # 412 Precondition Failed — the FE knows to surface the age confirm modal
        # for this status code on any seller-side request.
        raise HTTPException(
            status_code=412,
            detail={
                "error": "seller_age_verification_required",
                "message": "You must confirm you are of legal age to sell in your region before using marketplace features.",
            },
        )
    return user_id


async def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> bool:
    """
    Inter-service shared-secret guard.

    Checks the ``X-API-Key`` header against ``API_SHARED_SECRET``.
    """
    if not API_SHARED_SECRET:
        raise HTTPException(status_code=500, detail="API key not configured")
    if x_api_key != API_SHARED_SECRET:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


async def require_ops_key(
    x_ops_key: str | None = Header(None, alias="X-Ops-Key"),
) -> bool:
    """
    Lightweight auth guard for /ops/* endpoints.

    Checks the ``X-Ops-Key`` header against the ``OPS_API_KEY`` env var.
    In DEV_MODE the check is skipped so local development works without
    extra configuration.
    """
    if DEV_MODE:
        return True

    if not OPS_API_KEY:
        logger.error("OPS_API_KEY is not configured — ops endpoints are locked out")
        raise HTTPException(
            status_code=503,
            detail="Ops endpoints are not configured",
        )

    if not x_ops_key or x_ops_key != OPS_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing ops key")

    return True
