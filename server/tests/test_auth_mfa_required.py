"""The API refuses a password-only (aal1) token for a member with 2FA (2026-09-26).

The app sent an aal1 session to the code screen, but the API accepted the
token, so the password alone reached every endpoint.
"""
import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import jwt  # noqa: E402
from fastapi import HTTPException  # noqa: E402

import app.auth as auth  # noqa: E402

SECRET = "test-secret-for-mfa"
UID = "8b313570-cb44-4c0a-b9b5-3f4fb741648c"


def _token(aal: str) -> str:
    return jwt.encode(
        {"sub": UID, "aud": "authenticated", "exp": int(time.time()) + 600, "aal": aal},
        SECRET, algorithm="HS256",
    )


class _Req:
    def __init__(self, token):
        self.headers = {"authorization": f"Bearer {token}"}


def _call(aal: str, has_factor):
    async def fake(_uid):
        return has_factor
    with patch.object(auth, "JWT_SECRET", SECRET), patch.object(auth, "JWT_ISSUER", None), \
         patch.object(auth, "_has_verified_factor", fake):
        return asyncio.run(auth.get_current_user_id(_Req(_token(aal))))


def test_aal1_with_a_verified_factor_is_refused_with_403_not_401():
    with pytest.raises(HTTPException) as e:
        _call("aal1", True)
    assert e.value.status_code == 403
    assert e.value.detail["code"] == "MFA_REQUIRED"


def test_aal2_passes():
    assert _call("aal2", True) == UID


def test_member_without_2fa_is_untouched():
    assert _call("aal1", False) == UID


def test_unreadable_factor_table_lets_the_request_through():
    assert _call("aal1", None) == UID
