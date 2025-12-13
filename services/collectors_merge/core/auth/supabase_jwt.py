from __future__ import annotations

import os
import time

import httpx
from jose import jwt

JWKS_CACHE = {"exp": 0, "keys": None}


def _jwks_url() -> str:
    # Supabase JWKS endpoint
    url = os.getenv("SUPABASE_JWKS_URL")
    if not url:
        # Example: https://<project>.supabase.co/auth/v1/jwks
        raise RuntimeError("SUPABASE_JWKS_URL not set")
    return url


def _load_jwks():
    now = int(time.time())
    if JWKS_CACHE["exp"] > now and JWKS_CACHE["keys"] is not None:
        return JWKS_CACHE["keys"]
    with httpx.Client(timeout=10) as c:
        r = c.get(_jwks_url())
        r.raise_for_status()
        data = r.json()
    JWKS_CACHE["keys"] = data
    JWKS_CACHE["exp"] = now + 300
    return data


def verify(token: str) -> dict:
    jwks = _load_jwks()
    headers = jwt.get_unverified_header(token)
    kid = headers.get("kid")
    key = None
    for k in jwks["keys"]:
        if k["kid"] == kid:
            key = k
            break
    if key is None:
        raise RuntimeError("Key not found for kid")
    return jwt.decode(
        token,
        key,
        options={
            "verify_aud": False,
            "verify_at_hash": False,
            "verify_sub": True,
            "require_sub": True,
        },
    )
