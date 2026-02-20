import os
import sys
import asyncio
import pytest
from pathlib import Path
from starlette.testclient import TestClient

# Ensure `server/` is on sys.path so `import main` and `from app.xxx` work
_server_dir = str(Path(__file__).resolve().parent.parent)
if _server_dir not in sys.path:
    sys.path.insert(0, _server_dir)

# Also add project root so top-level modules like inference.py are importable
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Force mock DB mode, dev auth bypass, and disable rate limiting in tests
os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("FORCE_DEV_MODE", "true")  # bypass hostname check in validate_config
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
