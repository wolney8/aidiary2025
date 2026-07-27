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
    profile = next(endpoint for endpoint in report["endpoints"] if endpoint["name"] == "profile")
    assert profile["samples"][0]["response_shape"] == {
        "kind": "object",
        "keys": ["ok"],
    }


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


def test_capture_baseline_counts_auth_failures():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/profile":
            return httpx.Response(401, json={"msg": "Token has expired"})
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    with httpx.Client(
        base_url="https://example.test",
        transport=transport,
    ) as client:
        report = capture_baseline(
            base_url="https://example.test",
            token="expired-token",
            samples=1,
            client=client,
        )

    assert report["summary"]["error_count"] == 1
    profile = next(endpoint for endpoint in report["endpoints"] if endpoint["name"] == "profile")
    assert profile["error_count"] == 1
    assert profile["samples"][0]["status_code"] == 401


def test_capture_baseline_records_collection_response_counts_without_body_payloads():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/daily":
            return httpx.Response(
                200,
                json=[
                    {"id": 1, "title": "Private one"},
                    {"id": 2, "title": "Private two"},
                ],
            )
        if request.url.path == "/api/on-this-day":
            return httpx.Response(
                200,
                json={
                    "enabled": True,
                    "date": "2026-07-27",
                    "entries": [{"id": 1}],
                },
            )
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

    daily = next(endpoint for endpoint in report["endpoints"] if endpoint["name"] == "daily_entries")
    assert daily["samples"][0]["response_shape"] == {
        "kind": "list",
        "item_count": 2,
    }
    assert "Private one" not in str(daily["samples"][0]["response_shape"])

    on_this_day = next(endpoint for endpoint in report["endpoints"] if endpoint["name"] == "on_this_day")
    assert on_this_day["samples"][0]["response_shape"] == {
        "kind": "object",
        "entries_count": 1,
        "keys": ["date", "enabled", "entries"],
    }
