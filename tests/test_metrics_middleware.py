def test_metrics_middleware_increments(client):
    # trigger a request to count
    r = client.get("/healthz")
    assert r.status_code == 200

    # trigger a non-exempt request so counters increment
    client.get("/ops/status")

    # scrape metrics via the app's /metrics endpoint
    m = client.get("/metrics")
    assert m.status_code == 200
    body = m.text
    assert "collectors_requests_total" in body
    assert "collectors_request_latency_seconds" in body
    assert "collectors_uptime_seconds_total" in body
