def test_ops_status_endpoint(client):
    resp = client.get("/ops/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert data["status"] == "ok"
