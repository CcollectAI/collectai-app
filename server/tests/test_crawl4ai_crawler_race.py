"""_get_crawler returns the crawler it started even if close() ran meanwhile."""
import asyncio
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.lib import crawl4ai_client as cc  # noqa: E402


@pytest.mark.asyncio
async def test_close_during_start_does_not_hand_back_none(monkeypatch):
    class _Crawler:
        def __init__(self, config=None):
            pass

        async def start(self):
            await cc.close()  # the concurrent shutdown, landing mid-start

        async def close(self):
            pass

    fake = types.SimpleNamespace(AsyncWebCrawler=_Crawler, BrowserConfig=lambda **k: None)
    monkeypatch.setitem(sys.modules, "crawl4ai", fake)
    monkeypatch.setattr(cc, "_crawler", None)
    got = await cc._get_crawler()
    assert isinstance(got, _Crawler)
