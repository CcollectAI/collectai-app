def test_health_and_status(client):
    """Verify core health and status endpoints."""
    h = client.get("/healthz")
    assert h.status_code == 200
    assert h.json()["ok"] is True

    s = client.get("/ops/status")
    assert s.status_code == 200
    data = s.json()
    assert "status" in data
    assert data["status"] == "ok"
