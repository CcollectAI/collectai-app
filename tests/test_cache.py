import asyncio

from app.cache.files_async import get_cached_async, set_cached_async


def test_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    key = "demo:test"
    data = {"v": 1}
    asyncio.run(set_cached_async(key, data))
    out = asyncio.run(get_cached_async(key))
    assert out == data
