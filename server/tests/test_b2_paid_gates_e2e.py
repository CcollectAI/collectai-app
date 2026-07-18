"""B2 paywall E2E verification.

Drives the live FastAPI app in-process and asserts every paid feature
returns 403 for free users and passes the gate for paid users.

Run from server/:
    DEV_MODE=true DB_ENABLED=false ../.venv/bin/python -m pytest \
        tests/test_b2_paid_gates_e2e.py -v
"""
from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("JWT_SECRET", "test-secret-for-b2-e2e")
os.environ.setdefault("DEV_USER_ID", "00000000-0000-0000-0000-00000000beef")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from main import app  # noqa: E402
from app.auth import get_current_user_id  # noqa: E402

TEST_USER = "00000000-0000-0000-0000-00000000beef"


@pytest.fixture
async def client():
    async def _u():
        return TEST_USER

    app.dependency_overrides[get_current_user_id] = _u
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_current_user_id, None)


# (method, path, min_plan, body)
GATED_ROUTES = [
    ("GET",  "/purchase/deals",                  "pro",     None),
    ("GET",  "/purchase/deals/00000000-0000-0000-0000-000000000abc", "pro", None),
    ("GET",  "/dossier/00000000-0000-0000-0000-000000000abc/export",     "pro",     None),
    ("GET",  "/sell-timing/items/pokemon%3Acharizard-base-set-4-102",     "premium", None),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,min_plan,body", GATED_ROUTES)
async def test_free_user_gets_403(client, method, path, min_plan, body):
    with patch("app.subscription.get_user_plan", new=AsyncMock(return_value="free")):
        r = await client.request(method, path, json=body or {})
    assert r.status_code == 403, (
        f"{method} {path}: expected 403 for free user, got {r.status_code}: {r.text[:200]}"
    )
    text = (r.text or "").lower()
    assert "plan_required" in text or "plan" in text, (
        f"{path}: response did not signal plan requirement: {r.text[:200]}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,min_plan,body", GATED_ROUTES)
async def test_paid_user_passes_gate(client, method, path, min_plan, body):
    """Paid user must NOT be rejected by the plan gate. The route may
    still 4xx/5xx for unrelated reasons (DB disabled, missing item, etc.)
    but must not be 403/PLAN_REQUIRED."""
    with patch("app.subscription.get_user_plan", new=AsyncMock(return_value=min_plan)):
        r = await client.request(method, path, json=body or {})
    text = (r.text or "").lower()
    plan_blocked = (r.status_code == 403) and ("plan_required" in text or "requires " in text)
    assert not plan_blocked, (
        f"{method} {path}: paid user ({min_plan}) was rejected by plan gate: {r.status_code} {r.text[:200]}"
    )


@pytest.mark.asyncio
async def test_intake_condition_grading_helper():
    from app.agents.intake.orchestrator import _user_has_paid_plan

    with patch("app.subscription.get_user_plan", new=AsyncMock(return_value="free")):
        assert await _user_has_paid_plan(TEST_USER) is False

    with patch("app.subscription.get_user_plan", new=AsyncMock(return_value="pro")):
        assert await _user_has_paid_plan(TEST_USER) is True

    with patch("app.subscription.get_user_plan", new=AsyncMock(return_value="premium")):
        assert await _user_has_paid_plan(TEST_USER) is True

    assert await _user_has_paid_plan(None) is False


@pytest.mark.asyncio
async def test_intake_set_completion_gated():
    from app.agents.intake_duplicate_check import check_user_duplicates

    class _Conn:
        async def fetchval(self, sql, *_a, **_kw):
            return 5

        async def fetch(self, *_a, **_kw):
            return []

    class _AcquireCM:
        async def __aenter__(self):
            return _Conn()

        async def __aexit__(self, *_):
            return False

    class _Pool:
        def acquire(self):
            return _AcquireCM()

    with patch("app.subscription.get_user_plan", new=AsyncMock(return_value="free")):
        result = await check_user_duplicates(
            user_id=TEST_USER,
            category_id="pokemon",
            normalized_key="charizard",
            catalog_match_key="pokemon:charizard-1st-edition",
            pool=_Pool(),
        )
    assert result["set_completion"] is None, "free user must NOT receive set_completion"

    with patch("app.subscription.get_user_plan", new=AsyncMock(return_value="pro")):
        result = await check_user_duplicates(
            user_id=TEST_USER,
            category_id="pokemon",
            normalized_key="charizard",
            catalog_match_key="pokemon:charizard-1st-edition",
            pool=_Pool(),
        )
    assert result["set_completion"] is not None, "pro user must receive set_completion"
    assert result["set_completion"]["owned"] == 5
    assert result["set_completion"]["total"] == 5
