def test_storage_presign_upload_requires_body(client):
    """POST /storage/presign-upload without a body should return 422."""
    r = client.post("/storage/presign-upload")
    assert r.status_code == 422
