def test_listing_draft_valid(client):
    payload = {
        "items": [{
            "sku": "lego-10240",
            "title": "LEGO 10240 Red Five X-Wing",
            "quantity": 1,
            "price": 199.99,
            "currency": "USD",
            "category": "lego"
        }],
        "seller_id": "seller_123"
    }
    r = client.post("/listing/draft", json=payload)
    assert r.status_code == 201
    j = r.json()
    assert j["ok"] is True
    assert j["items_count"] == 1
    assert j["draft_id"].startswith("draft_")
