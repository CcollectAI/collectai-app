import asyncio
from app.tasks.prefetcher import prefetch_trending
from app.cache.files_async import get_cached_async

def test_prefetch_trending(event_loop):
    result = event_loop.run_until_complete(prefetch_trending())
    assert "items" in result
    cached = event_loop.run_until_complete(get_cached_async("prefetch:trending"))
    assert cached is not None
