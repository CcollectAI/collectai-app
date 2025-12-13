def test_agent_ingest_ok(client):
    payload = {"source": "web", "kind": "click", "user_id": "u1", "session_id": "s1", "payload": {"x": 1}}
    r = client.post("/agent/ingest", json=payload)
    assert r.status_code == 202
    j = r.json()
    assert j["ok"] is True
    assert "stored" in j  # True or False depending on env
