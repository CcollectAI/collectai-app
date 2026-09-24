"""The deals list shows deals, not every candidate the agent looked at.

2026-09-24: /purchase/deals listed all 22 stored candidates for a €30 mandate,
including €96 price-guide rows from a source the member had switched off — each
with a "New" badge. Only `policy_passed` rows are deals.
"""
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DB_ENABLED", "false")

from app.agents import purchase_router as pr  # noqa: E402

USER = "00000000-0000-0000-0000-0000000000a1"


class _Conn:
    def __init__(self):
        self.sql = []

    async def fetchval(self, q, *a):
        self.sql.append(q)
        return 0

    async def fetch(self, q, *a):
        self.sql.append(q)
        return []


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [None, "discovered"])
async def test_list_reads_only_passed_deals(monkeypatch, status):
    conn = _Conn()

    @asynccontextmanager
    async def fake_conn():
        yield conn

    monkeypatch.setattr(pr, "get_conn", fake_conn)
    monkeypatch.setattr(pr, "_require_db", lambda: None)
    await pr.list_deals(user_id=USER, pagination=(20, 0), status=status, _plan="pro")
    assert conn.sql and all("policy_passed IS TRUE" in q for q in conn.sql)


@pytest.mark.asyncio
async def test_detail_reads_only_passed_deals(monkeypatch):
    """A direct link to a REJECTED candidate is a 404, not a deal with a Buy button."""
    seen = []

    class _One:
        async def fetchrow(self, q, *a):
            seen.append(q)
            return None

    @asynccontextmanager
    async def fake_conn():
        yield _One()

    monkeypatch.setattr(pr, "get_conn", fake_conn)
    monkeypatch.setattr(pr, "_require_db", lambda: None)
    with pytest.raises(Exception):
        await pr.get_deal("00000000-0000-0000-0000-0000000000d1", user_id=USER, _plan="pro")
    assert seen and "policy_passed IS TRUE" in seen[0]
