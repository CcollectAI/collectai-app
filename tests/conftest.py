import os
import asyncio
import pytest
from starlette.testclient import TestClient

# Force mock DB mode, dev auth bypass, and disable rate limiting in tests
os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["PER_USER_RATE_LIMIT_ENABLED"] = "false"

from main import app  # noqa: E402

# Ensure rate limiter is disabled even if it was imported before env var was set
try:
    import app.rate_limit as _rl
    _rl.RATE_LIMIT_ENABLED = False
    _rl.PER_USER_RATE_LIMIT_ENABLED = False
except ImportError:
    pass

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
