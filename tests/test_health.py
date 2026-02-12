import os

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DB_DSN", "")
os.environ.setdefault("DEV_MODE", "true")

from fastapi.testclient import TestClient
from main import app  # noqa: E402

client = TestClient(app)


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["ok"] is True
