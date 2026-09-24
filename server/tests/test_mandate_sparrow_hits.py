"""Mandates see Sparrow's own marketplace, not only outside ones.

2026-09-24: a member listing the exact card a mandate wanted could fire Target
Hit but never a mandate deal — scan_mandate searched external marketplaces only.
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DB_ENABLED", "false")

from app.agents import deal_discovery_agent as dda  # noqa: E402

BUYER = "00000000-0000-0000-0000-0000000000a1"


class _Conn:
    def __init__(self):
        self.args = None

    async def fetch(self, q, *a):
        self.args = a
        return [{"id": "L1", "listing_title": "Charizard ex SVP 161", "price": 20.0, "currency": "USD",
                 "condition_label": "Near Mint", "shipping_cost": None, "ships_from": "NL",
                 "created_at": datetime.now(timezone.utc)}]


@pytest.mark.asyncio
async def test_member_listing_becomes_a_hit_in_eur(monkeypatch):
    import app.lib.blocks as blocks
    import app.lib.fx_service as fx

    async def _no_blocks(conn, uid):
        return []

    async def _usd(amount, cur):
        return amount * 0.9 if cur == "USD" else amount

    monkeypatch.setattr(blocks, "blocked_user_ids", _no_blocks)
    monkeypatch.setattr(fx, "convert_to_eur", _usd)
    agent = dda.DealDiscoveryAgent.__new__(dda.DealDiscoveryAgent)
    conn = _Conn()
    hits = await agent._sparrow_hits(conn, {"user_id": BUYER, "canonical_ref": "pokemon:svp-svp-161",
                                            "category": "pokemon", "search_query": "Charizard ex"})
    assert len(hits) == 1
    h = hits[0].hit
    assert h["source"] == "sparrow" and h["url"] == "https://sparrowcollect.com/l/L1"
    assert h["price"] == 18.0 and h["currency"] == "EUR"
    # the query is told whose listings to leave out, and which key to match
    assert conn.args[0] == BUYER and conn.args[1] == "pokemon:svp-svp-161"
