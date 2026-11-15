from datetime import UTC, datetime

from src.adapters.in_memory_event_feed import InMemoryEventFeed
from src.domain.state import AnomalyAnalysisOutput, RootCauseReport, TelemetryEvent


def _event(event_id: int = 1, service_name: str = "payment-service") -> TelemetryEvent:
    return TelemetryEvent(
        id=event_id,
        service_name=service_name,
        environment="production",
        timestamp=datetime(2026, 11, 13, 12, 0, tzinfo=UTC),
        log_level="CRITICAL",
        message="Payment gateway unavailable",
    )


def _anomaly_result(event: TelemetryEvent) -> dict:
    return {
        "raw_event": event,
        "trace_id": "trace-1",
        "sanitization_ok": True,
        "is_anomaly": True,
        "anomaly_score": 0.91,
        "anomaly_output": AnomalyAnalysisOutput(
            is_anomaly=True,
            anomaly_score=0.91,
            severity="critical",
            reasoning="High error rate",
        ),
        "diagnosis": RootCauseReport(
            root_cause="Payment gateway timeout",
            severity="critical",
            recommended_action="Rollback the last deployment",
            runbook_steps=["Check gateway health", "Rollback deployment"],
        ),
    }


def test_feed_records_anomaly_snapshot():
    feed = InMemoryEventFeed()
    event = _event()

    feed.record(event, _anomaly_result(event))

    snapshot = feed.recent()[0]
    assert snapshot.event_id == 1
    assert snapshot.service_name == "payment-service"
    assert snapshot.is_anomaly is True
    assert snapshot.anomaly_score == 0.91
    assert snapshot.severity == "critical"
    assert snapshot.root_cause == "Payment gateway timeout"
    assert snapshot.recommended_action == "Rollback the last deployment"
    assert snapshot.runbook_steps == ["Check gateway health", "Rollback deployment"]
    assert snapshot.trace_id == "trace-1"


def test_feed_records_normal_snapshot_without_diagnosis():
    feed = InMemoryEventFeed()
    event = _event(event_id=2, service_name="checkout-service")

    feed.record(
        event,
        {
            "raw_event": event,
            "trace_id": "trace-2",
            "sanitization_ok": True,
            "is_anomaly": False,
            "anomaly_score": 0.0,
        },
    )

    snapshot = feed.recent()[0]
    assert snapshot.event_id == 2
    assert snapshot.is_anomaly is False
    assert snapshot.severity == "ok"
    assert snapshot.root_cause is None
    assert snapshot.runbook_steps == []


def test_feed_keeps_rejected_events():
    feed = InMemoryEventFeed()
    event = _event(event_id=3)

    feed.record(
        event,
        {
            "raw_event": event,
            "sanitization_ok": False,
            "is_anomaly": False,
            "trace_id": "trace-3",
        },
    )

    snapshot = feed.recent()[0]
    assert snapshot.sanitization_ok is False
    assert snapshot.severity == "ok"
    assert snapshot.anomaly_score == 0.0


def test_feed_uses_sanitized_event_from_result():
    feed = InMemoryEventFeed()
    original = _event(event_id=4)
    sanitized = original.model_copy(update={"message": "redacted"})

    feed.record(original, {"raw_event": sanitized, "sanitization_ok": True})

    assert feed.recent()[0].message == "redacted"


def test_feed_returns_newest_first_and_respects_limit():
    feed = InMemoryEventFeed()
    for event_id in range(1, 4):
        event = _event(event_id=event_id)
        feed.record(event, _anomaly_result(event))

    assert [item.event_id for item in feed.recent(2)] == [3, 2]
    assert [item.event_id for item in feed.recent(10)] == [3, 2, 1]
    assert feed.recent(0) == []


def test_feed_evicts_oldest_events():
    feed = InMemoryEventFeed(max_events=2)
    for event_id in range(1, 4):
        event = _event(event_id=event_id)
        feed.record(event, _anomaly_result(event))

    assert [item.event_id for item in feed.recent(10)] == [3, 2]
