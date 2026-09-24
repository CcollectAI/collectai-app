"""Fire-and-forget background-task helper.

Every `asyncio.create_task(...)` for best-effort work (analytics signals, cache
warms, counter bumps) must (1) hold a strong reference — the event loop keeps
only a *weak* ref, so an un-referenced task can be garbage-collected mid-await —
and (2) surface failures at WARNING. A bare `create_task` + `logger.debug` in
the coroutine hides errors forever. This was learned the hard way in
spend_tracker / worker_registry; this helper centralises the pattern so no call
site reinvents (or forgets) it.

Usage:
    from app.lib.bg_tasks import spawn_bg
    spawn_bg(_record_demand(...), "watchlist_demand")
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Optional, Set

logger = logging.getLogger(__name__)

# Module-level strong refs so tasks can't be GC'd before they finish.
_pending: Set["asyncio.Task[Any]"] = set()


def spawn_bg(coro: "Awaitable[Any]", label: str) -> "Optional[asyncio.Task[Any]]":
    """Schedule ``coro`` fire-and-forget with a retained ref + WARNING-logged failures.

    Returns the created Task, or ``None`` when there is no running event loop
    (the caller is in a sync context). In that case the coroutine is closed to
    avoid a "coroutine was never awaited" warning.
    """
    # A FUTURE is not a coroutine, and `create_task` refuses it with
    # "a coroutine was expected, got <_GatheringFuture pending>". That exact
    # TypeError escaped MarketplaceAgent.aggregate_search whenever a source ran
    # over budget (it reaped stragglers with spawn_bg(asyncio.gather(...))), so
    # the search threw away the results it DID get — 81 times in one week of
    # bake.log, and every Smart Deal Agent scan on 2026-09-24. Accept any
    # awaitable by wrapping it.
    if not asyncio.iscoroutine(coro):
        awaitable = coro

        async def _await_it() -> Any:
            return await awaitable

        coro = _await_it()

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        coro.close()
        return None

    task = loop.create_task(coro)
    _pending.add(task)

    def _on_done(t: "asyncio.Task[Any]", _label: str = label) -> None:
        _pending.discard(t)
        exc = t.exception() if not t.cancelled() else None
        if exc is not None:
            logger.warning("background task %s failed: %r", _label, exc)

    task.add_done_callback(_on_done)
    return task
