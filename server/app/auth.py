from __future__ import annotations

import logging
from fastapi import Depends, Header, HTTPException, Request
from app.request_id import set_user_id
from app.config import DEV_MODE, DEV_USER_ID, JWT_SECRET, JWT_ISSUER, OPS_API_KEY, API_SHARED_SECRET

logger = logging.getLogger(__name__)

# Supabase is migrating projects from a single HS256 shared secret to
# asymmetric JWT signing keys (ES256/RS256). A migrated project issues tokens
# the HS256-only path cannot verify → 401 on every authenticated write
# (follow / add-to-watchlist / event RSVP). We therefore dispatch on the
# token's own `alg` header and verify asymmetric tokens against the project
# JWKS, while keeping the legacy HS256 path unchanged.
_ASYMMETRIC_ALGS = {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "EdDSA"}
_jwks_client = None  # lazily built, caches the JWK set internally (5 min)


def _get_jwks_client():
    """Return a cached PyJWKClient for the Supabase project's JWKS endpoint.

    Returns None when SUPABASE_URL is unset — asymmetric verification is then
    unavailable and HS256 remains the only supported path.
    """
    global _jwks_client
    if _jwks_client is not None:
        return _jwks_client
    from app.config import SUPABASE_URL

    if not SUPABASE_URL:
        return None
    import jwt as _jwt

    _jwks_client = _jwt.PyJWKClient(
        f"{SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
    )
    return _jwks_client


def _decode_supabase_jwt(token: str) -> dict:
    """Verify a Supabase access token via HS256 (legacy shared secret) OR the
    project's asymmetric signing keys (ES256/RS256), chosen by the token header.

    Raises on any validation failure (bad signature, expired, wrong audience/
    issuer, unknown key) so the caller maps it to 401 exactly as before.
    """
    import jwt as _jwt

    alg = _jwt.get_unverified_header(token).get("alg", "")

    common: dict = {
        "audience": "authenticated",
        "options": {"require": ["exp", "sub"]},
    }
    if JWT_ISSUER:
        common["issuer"] = JWT_ISSUER

    if alg in _ASYMMETRIC_ALGS:
        client = _get_jwks_client()
        if client is None:
            raise RuntimeError(
                "SUPABASE_URL not set — cannot verify asymmetric JWT"
            )
        signing_key = client.get_signing_key_from_jwt(token)
        return _jwt.decode(token, signing_key.key, algorithms=[alg], **common)

    # Legacy / default: HS256 shared secret.
    return _jwt.decode(token, JWT_SECRET, algorithms=["HS256"], **common)


def _log_jwt_failure(token: str, exc: Exception) -> None:
    """Explain WHY a token was rejected, without leaking secrets.

    Logs the token's own (unverified) alg / iss / aud / expiry next to what
    THIS server expects, so the recurring write-401 root cause is visible on
    the very first failed request:

      * ``InvalidSignatureError`` + ``secret_configured=True``  → server's
        SUPABASE_JWT_SECRET does not match the project's JWT secret.
      * ``secret_configured=False``                            → secret unset.
      * ``token_iss`` != ``expected_issuer``                   → SUPABASE_JWT_ISSUER wrong.
      * ``token_aud`` != ``authenticated``                     → audience mismatch.
      * ``token_expired=True``                                 → stale/expired session (client-side).

    The JWT secret value is NEVER logged — only whether it is set and its length.
    """
    import time as _time

    detail: dict = {
        "reason": type(exc).__name__,
        "secret_configured": bool(JWT_SECRET),
        "secret_len": len(JWT_SECRET or ""),
        "expected_issuer": JWT_ISSUER or "(unchecked)",
        "expected_audience": "authenticated",
    }
    try:
        import jwt as _jwt

        hdr = _jwt.get_unverified_header(token)
        claims = _jwt.decode(token, options={"verify_signature": False})
        exp = claims.get("exp")
        detail.update(
            {
                "token_alg": hdr.get("alg"),
                "token_iss": claims.get("iss"),
                "token_aud": claims.get("aud"),
                "token_expired": bool(exp and exp < _time.time()),
            }
        )
    except Exception:  # malformed token — the claims themselves are unreadable
        detail["unverified_decode"] = "failed"

    logger.warning("JWT validation failed: %s", detail)


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
            payload = _decode_supabase_jwt(token)
            user_id = payload.get("sub", "")
            if user_id:
                set_user_id(user_id)
                return user_id
            logger.warning("JWT decoded but 'sub' claim is empty")
        except ImportError:
            logger.error("PyJWT not installed — cannot validate tokens")
            raise HTTPException(status_code=500, detail="Auth module misconfigured")
        except Exception as exc:
            # Log the PRECISE reason (token's own iss/aud/exp vs. what this server
            # expects) so a secret/issuer/audience/expiry mismatch is obvious on
            # the first failed request — the recurring write-401 root cause.
            _log_jwt_failure(token, exc)
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
