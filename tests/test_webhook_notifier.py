import json
from collections.abc import Callable

import httpx
import pytest

from src.adapters.webhook_notifier import NotificationError, WebhookNotifier


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_webhook_notifier_sends_slack_compatible_payload():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200)

    client = _client(handler)
    notifier = WebhookNotifier("https://hooks.example/sentinel", client=client)

    notifier.send("ops-oncall", "CPU saturation detected")
    client.close()

    assert len(requests) == 1
    payload = json.loads(requests[0].content)
    assert payload == {"text": "[ops-oncall] CPU saturation detected"}


def test_webhook_notifier_retries_retryable_status_codes():
    responses = [httpx.Response(503), httpx.Response(429), httpx.Response(200)]
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return responses.pop(0)

    client = _client(handler)
    notifier = WebhookNotifier(
        "https://hooks.example/sentinel",
        max_retries=2,
        backoff_seconds=0.25,
        client=client,
        sleep=sleeps.append,
    )

    notifier.send("ops-oncall", "Database latency")
    client.close()

    assert sleeps == [0.25, 0.5]


def test_webhook_notifier_does_not_retry_client_errors():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400)

    client = _client(handler)
    notifier = WebhookNotifier(
        "https://hooks.example/sentinel",
        max_retries=3,
        client=client,
        sleep=lambda _: None,
    )

    with pytest.raises(NotificationError, match="HTTP 400"):
        notifier.send("ops-oncall", "Bad payload")
    client.close()

    assert calls == 1


def test_webhook_notifier_raises_after_retry_exhaustion():
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    client = _client(handler)
    notifier = WebhookNotifier(
        "https://hooks.example/sentinel",
        max_retries=2,
        backoff_seconds=0.1,
        client=client,
        sleep=sleeps.append,
    )

    with pytest.raises(NotificationError, match="failed"):
        notifier.send("ops-oncall", "Unavailable")
    client.close()

    assert calls == 3
    assert sleeps == [0.1, 0.2]


def test_webhook_notifier_retries_network_errors():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("connection refused", request=request)

    client = _client(handler)
    notifier = WebhookNotifier(
        "https://hooks.example/sentinel",
        max_retries=1,
        client=client,
        sleep=lambda _: None,
    )

    with pytest.raises(NotificationError, match="ConnectError"):
        notifier.send("ops-oncall", "Unavailable")
    client.close()

    assert calls == 2
