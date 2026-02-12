from __future__ import annotations

import logging
from fastapi import Depends, Header, HTTPException, Request
from app.request_id import set_user_id
from app.config import DEV_MODE, DEV_USER_ID, JWT_SECRET, OPS_API_KEY

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

            payload = _jwt.decode(
                token,
                JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
            )
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
