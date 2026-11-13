from datetime import UTC, datetime

import pytest

from src.adapters.telemetry_queue import InlineTelemetryQueue, QStashTelemetryQueue
from src.domain.state import TelemetryEvent


def _event() -> TelemetryEvent:
    return TelemetryEvent(
        id=42,
        service_name="payment-service",
        environment="production",
        timestamp=datetime(2026, 11, 9, 12, 0, tzinfo=UTC),
        log_level="ERROR",
        message="Payment gateway unavailable",
    )


def test_inline_queue_processes_event_synchronously():
    seen = []
    queue = InlineTelemetryQueue(seen.append)

    queue.publish(_event())

    assert seen == [_event()]
    assert queue.is_remote is False
    assert queue.verify_signature(b"{}", "signature") is False


def test_inline_queue_propagates_processor_errors():
    def fail(event: TelemetryEvent) -> None:
        raise RuntimeError("processor down")

    queue = InlineTelemetryQueue(fail)

    with pytest.raises(RuntimeError, match="processor down"):
        queue.publish(_event())


class _FakeMessage:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def publish_json(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


class _FakeClient:
    def __init__(self) -> None:
        self.message = _FakeMessage()


class _FakeReceiver:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict] = []

    def verify(self, **kwargs: object) -> None:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error


def test_qstash_publishes_event_with_deduplication():
    client = _FakeClient()
    queue = QStashTelemetryQueue(
        "token",
        "https://example.com/internal/otel/process",
        "current-key",
        "next-key",
        client=client,
        receiver=_FakeReceiver(),
    )

    queue.publish(_event())

    assert queue.is_remote is True
    assert client.message.calls == [
        {
            "url": "https://example.com/internal/otel/process",
            "body": {
                "id": 42,
                "service_name": "payment-service",
                "environment": "production",
                "timestamp": "2026-11-09T12:00:00Z",
                "log_level": "ERROR",
                "message": "Payment gateway unavailable",
                "metrics": {"cpu": None, "error_rate": None},
            },
            "retries": 3,
            "deduplication_id": "sentinel-otel-42",
        }
    ]


def test_qstash_verifies_signature_with_destination_url():
    receiver = _FakeReceiver()
    queue = QStashTelemetryQueue(
        "token",
        "https://example.com/internal/otel/process",
        "current-key",
        "next-key",
        client=_FakeClient(),
        receiver=receiver,
    )

    assert queue.verify_signature(b'{"id":42}', "signature") is True
    assert receiver.calls == [
        {
            "signature": "signature",
            "body": '{"id":42}',
            "url": "https://example.com/internal/otel/process",
            "clock_tolerance": 5,
        }
    ]


def test_qstash_rejects_invalid_signature():
    queue = QStashTelemetryQueue(
        "token",
        "https://example.com/internal/otel/process",
        "current-key",
        "next-key",
        client=_FakeClient(),
        receiver=_FakeReceiver(RuntimeError("bad signature")),
    )

    assert queue.verify_signature(b"{}", "invalid") is False
