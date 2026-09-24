"""A source that overruns the search budget must not throw away the others.

2026-09-24: every Smart Deal Agent scan failed with "a coroutine was expected,
got <_GatheringFuture pending>" — aggregate_search reaped over-budget
stragglers with spawn_bg(asyncio.gather(...)), and spawn_bg's create_task
refuses a future. The TypeError escaped, so eBay's results (which had arrived)
were discarded along with the slow Cardmarket scrape. 81 times in one week of
bake.log.
"""
import asyncio
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DB_ENABLED", "false")

from app.agents import marketplace_agent as ma  # noqa: E402
from app.lib.bg_tasks import spawn_bg  # noqa: E402


@pytest.mark.asyncio
async def test_spawn_bg_accepts_a_future():
    fut = asyncio.gather(asyncio.sleep(0), return_exceptions=True)
    task = spawn_bg(fut, "test_future")
    assert task is not None
    await task


@pytest.mark.asyncio
async def test_slow_source_is_dropped_and_fast_hits_kept(monkeypatch):
    agent = ma.MarketplaceAgent()

    async def fast():
        return [{"title": "Charizard ex", "price": 25.0, "url": "https://x/1", "source": "ebay",
                 "currency": "EUR", "price_eur": 25.0}]

    async def slow():
        await asyncio.sleep(5)
        return []

    monkeypatch.setattr(agent, "_build_search_tasks", lambda *a, **k: ([("ebay", fast()), ("cardmarket", slow())], 2))
    monkeypatch.setattr(ma.MarketplaceAgent, "_SEARCH_BUDGET_SECONDS", 0.2, raising=False)
    monkeypatch.setattr(ma, "_SEARCH_BUDGET_SECONDS", 0.2, raising=False)

    def _noop(*a, **k):
        return None

    result = await agent._do_aggregate_search(
        "Charizard ex", "pokemon", None, 20, False, None, None, False, "k", 60, _noop,
    )
    assert result.successful_sources == 1
    assert len(result.hits) >= 1
