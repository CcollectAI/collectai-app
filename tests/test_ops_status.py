def test_ops_status_endpoint(client):
    resp = client.get("/ops/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "healthy" in data
    assert "db_ok" in data
    assert "cache_ok" in data
