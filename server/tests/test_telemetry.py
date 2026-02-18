def test_telemetry_endpoint(client):
    # The /ops/telemetry endpoint serves Prometheus exposition format
    resp = client.get("/ops/telemetry")
    assert resp.status_code == 200

    body = resp.text
    # Verify collector-level metrics are present
    assert any(
        token in body
        for token in [
            "collectors_uptime_seconds_total",
            "collectors_task_failures_total",
            "collectors_task_retries_total",
            "collectors_requests_total",
        ]
    ), "Expected collectors metrics not found in /ops/telemetry"
