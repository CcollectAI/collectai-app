import requests

def test_health_and_metrics(client):
    # Core endpoints
    h = client.get("/healthz")
    r = client.get("/readyz")
    s = client.get("/ops/status")
    assert h.status_code == 200
    assert r.status_code == 200
    assert s.status_code == 200
    data = s.json()
    assert "status" in data
    assert "cache_ok" in data

    # Metrics server check
    res = requests.get("http://127.0.0.1:9000/metrics")
    assert res.status_code == 200
    text = res.text
    # accept any of the main collectors
    assert any(
        key in text
        for key in [
            "collectors_inference_requests_total",
            "collectors_task_failures_total",
            "collectors_uptime_seconds_total",
        ]
    ), "Expected collectors metrics not found in /metrics"
