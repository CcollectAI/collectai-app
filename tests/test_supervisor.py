import pytest
from app.tasks.supervisor import _retry_task

@pytest.mark.asyncio
async def test_retry_task_runs_successfully():
    called = {"n": 0}
    async def sometimes_fails():
        called["n"] += 1
        # fail twice, then succeed
        if called["n"] < 3:
            raise RuntimeError("boom")
        return "ok"
    out = await _retry_task(sometimes_fails, "sometimes_fails", max_retries=5, base_delay=0.01, max_delay=0.05)
    assert out == "ok"
    assert called["n"] == 3
