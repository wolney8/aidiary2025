import httpx

from scripts.capture_post_cutover_baseline import capture_baseline


def test_capture_baseline_samples_public_and_auth_endpoints():
    seen_paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        if request.url.path == "/api/profile":
            assert request.headers["Authorization"] == "Bearer token-1"
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    with httpx.Client(
        base_url="https://example.test",
        transport=transport,
    ) as client:
        report = capture_baseline(
            base_url="https://example.test",
            token="token-1",
            samples=2,
            client=client,
        )

    assert report["authenticated"] is True
    assert report["summary"]["skipped_endpoints"] == 0
    assert report["summary"]["error_count"] == 0
    assert report["summary"]["sample_count"] == len(report["endpoints"]) * 2
    assert "/health" in seen_paths
    assert "/api/profile" in seen_paths


def test_capture_baseline_skips_auth_endpoints_without_token():
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json={"ok": True})
    )
    with httpx.Client(
        base_url="https://example.test",
        transport=transport,
    ) as client:
        report = capture_baseline(
            base_url="https://example.test/",
            samples=1,
            client=client,
        )

    skipped = [
        endpoint for endpoint in report["endpoints"] if endpoint.get("skipped")
    ]
    assert report["authenticated"] is False
    assert report["summary"]["measured_endpoints"] == 2
    assert len(skipped) > 0
    assert {endpoint["skip_reason"] for endpoint in skipped} == {
        "auth token not supplied"
    }


def test_capture_baseline_counts_server_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(503, json={"ok": False})
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    with httpx.Client(
        base_url="https://example.test",
        transport=transport,
    ) as client:
        report = capture_baseline(
            base_url="https://example.test",
            token="token-1",
            samples=1,
            client=client,
        )

    assert report["summary"]["error_count"] == 1
    health = next(endpoint for endpoint in report["endpoints"] if endpoint["name"] == "health")
    assert health["error_count"] == 1
