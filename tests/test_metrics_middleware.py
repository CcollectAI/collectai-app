import requests
def test_metrics_middleware_increments(client):
    # trigger a simple request to count
    r = client.get("/healthz")
    assert r.status_code == 200
    # scrape metrics
    m = requests.get("http://127.0.0.1:9000/metrics", timeout=2)
    assert m.status_code == 200
    body = m.text
    assert "collectors_requests_total" in body
    assert "collectors_request_latency_seconds" in body
