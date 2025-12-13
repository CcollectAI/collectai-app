import requests

def test_telemetry_endpoint(client):
    # The /ops/telemetry endpoint serves Prometheus exposition format (text/plain)
    resp = client.get("/ops/telemetry")
    assert resp.status_code == 200

    # Pull the same endpoint over the real HTTP port used by the embedded server in tests
    # (We only need to validate the text body contains at least one of our metrics.)
    r = requests.get("http://127.0.0.1:9000/metrics", timeout=2)
    assert r.status_code == 200
    body = r.text

    # Accept any of the known collectors we expose
    assert any(
        token in body
        for token in [
            "collectors_uptime_seconds_total",
            "collectors_task_failures_total",
            "collectors_task_retries_total",
            "collectors_task_latency_seconds",
        ]
    ), "Expected collectors metrics not found in Prometheus exposition"
