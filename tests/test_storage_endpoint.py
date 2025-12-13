def test_storage_sign_missing_provider(client):
    r = client.get("/storage/sign", params={"bucket": "b", "key": "k"})
    assert r.status_code == 200
    j = r.json()
    # ok may be False if libs not installed; but key should exist
    assert "url" in j
