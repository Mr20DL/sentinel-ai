from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from src.adapters.fastapi_app import _non_negative_float_env, app, otel_normalizer
from src.adapters.otel_ingestion import OtelLogNormalizer

client = TestClient(app)
_TIMESTAMP = datetime(2026, 11, 5, 18, 30, tzinfo=UTC)
_NANOS = str(int(_TIMESTAMP.timestamp() * 1_000_000_000))
_RESOURCE_ATTRIBUTES = [
    {"key": "service.name", "value": {"stringValue": "payment"}},
    {"key": "deployment.environment.name", "value": {"stringValue": "production"}},
]


def _payload(
    message: str = "Payment charge failed",
    severity_text: str = "ERROR",
    severity_number: int | None = None,
    attributes: list[dict] | None = None,
) -> dict:
    record = {
        "timeUnixNano": _NANOS,
        "severityText": severity_text,
        "body": {"stringValue": message},
        "attributes": attributes or [],
        "traceId": "trace-payment-1",
        "spanId": "span-1",
    }
    if severity_number is not None:
        record["severityNumber"] = severity_number
    return _payload_from([record])


def _record(message: str = "Payment charge failed", **overrides: object) -> dict:
    record = {
        "timeUnixNano": _NANOS,
        "severityText": "ERROR",
        "body": {"stringValue": message},
        "attributes": [],
        "traceId": "trace-payment-1",
        "spanId": "span-1",
    }
    record.update(overrides)
    return record


def _payload_from(records: list[dict], resource_attributes: list[dict] | None = None) -> dict:
    return {
        "resourceLogs": [
            {
                "resource": {
                    "attributes": (
                        _RESOURCE_ATTRIBUTES if resource_attributes is None else resource_attributes
                    )
                },
                "scopeLogs": [{"logRecords": records}],
            }
        ]
    }


def test_normalizes_otlp_log_into_telemetry_event():
    normalizer = OtelLogNormalizer()
    payload = _payload(
        attributes=[
            {"key": "error_rate", "value": {"doubleValue": 0.45}},
            {"key": "cpu", "value": {"doubleValue": 91.5}},
        ]
    )

    events = normalizer.normalize(payload)

    assert len(events) == 1
    event = events[0]
    assert event.service_name == "payment"
    assert event.environment == "production"
    assert event.log_level == "ERROR"
    assert event.message == "Payment charge failed"
    assert event.timestamp == _TIMESTAMP
    assert float(event.metrics.error_rate) == 0.45
    assert float(event.metrics.cpu) == 91.5


def test_maps_severity_number_and_ignores_non_critical_logs():
    normalizer = OtelLogNormalizer()
    fatal = normalizer.normalize(
        _payload(message="Fatal payment failure", severity_text="", severity_number=21)
    )
    info = normalizer.normalize(
        _payload(message="Payment completed", severity_text="INFO", severity_number=9)
    )

    assert [event.log_level for event in fatal] == ["FATAL"]
    assert info == []


def test_deduplicates_same_service_message_and_minute():
    now = [100.0]
    normalizer = OtelLogNormalizer(dedup_ttl=60.0, clock=lambda: now[0])
    payload = _payload()

    assert len(normalizer.normalize(payload)) == 1
    assert normalizer.normalize(payload) == []

    now[0] = 161.0
    assert len(normalizer.normalize(payload)) == 1


def test_limits_events_per_request():
    normalizer = OtelLogNormalizer()
    payload = _payload(message="Payment charge failed")
    payload["resourceLogs"][0]["scopeLogs"][0]["logRecords"] = [
        {
            "timeUnixNano": _NANOS,
            "severityText": "ERROR",
            "body": {"stringValue": f"failure-{index}"},
        }
        for index in range(5)
    ]

    assert len(normalizer.normalize(payload, max_events=2)) == 2


def test_rejects_malformed_payloads():
    normalizer = OtelLogNormalizer()

    assert normalizer.normalize(None) == []
    assert normalizer.normalize({"resourceLogs": "not-a-list"}) == []
    assert normalizer.normalize({"resourceLogs": [{"scopeLogs": "bad"}]}) == []


def test_otel_endpoint_processes_critical_log():
    otel_normalizer.clear()

    response = client.post("/ingest/otel/v1/logs", json=_payload())

    assert response.status_code == 200
    assert response.json() == {"accepted": 1, "processed": 1, "failed": 0}


def test_otel_endpoint_requires_key_when_configured(monkeypatch):
    monkeypatch.setenv("SENTINEL_INGEST_API_KEY", "test-secret")
    otel_normalizer.clear()

    unauthorized = client.post("/ingest/otel/v1/logs", json=_payload())
    authorized = client.post(
        "/ingest/otel/v1/logs",
        json=_payload(message="Second payment failure"),
        headers={"X-Ingest-Key": "test-secret"},
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200


def test_rejects_invalid_normalizer_configuration():
    with pytest.raises(ValueError):
        OtelLogNormalizer(dedup_ttl=-0.1)
    with pytest.raises(ValueError):
        OtelLogNormalizer(max_message_length=0)
    assert OtelLogNormalizer().normalize(_payload(), max_events=0) == []


def test_ignores_malformed_resource_scope_and_record_entries():
    payload = {
        "resourceLogs": [
            None,
            {"resource": "not-a-resource", "scopeLogs": "not-a-list"},
            {
                "resource": {"attributes": _RESOURCE_ATTRIBUTES},
                "scopeLogs": [
                    None,
                    {"logRecords": "not-a-list"},
                    {"logRecords": [None, _record("valid failure")]},
                ],
            },
        ]
    }

    events = OtelLogNormalizer().normalize(payload)

    assert [event.message for event in events] == ["valid failure"]


def test_skips_events_without_service_or_message():
    no_service = _payload_from([_record("no service")], resource_attributes=[])
    no_message = _payload_from([_record("", body=None)])

    assert OtelLogNormalizer().normalize(no_service) == []
    assert OtelLogNormalizer().normalize(no_message) == []


def test_uses_observed_timestamp_message_attribute_and_time_fallback():
    observed = _record(
        "",
        body=None,
        attributes=[{"key": "log.message", "value": {"stringValue": "attribute message"}}],
    )
    observed.pop("timeUnixNano")
    observed["observedTimeUnixNano"] = _NANOS
    fallback = _record("fallback timestamp")
    fallback.pop("timeUnixNano")

    events = OtelLogNormalizer().normalize(_payload_from([observed, fallback]), max_events=5)

    by_message = {event.message: event for event in events}
    assert by_message["attribute message"].timestamp == _TIMESTAMP
    assert by_message["attribute message"].environment == "production"
    assert by_message["fallback timestamp"].timestamp.tzinfo is UTC


def test_handles_all_body_shapes():
    payload = _payload_from(
        [
            _record("raw", body="  raw body  "),
            _record("kv", body={"kvlistValue": {"values": [{"key": "a"}]}}),
            _record("array", body={"arrayValue": {"values": [{"stringValue": "x"}]}}),
            _record("other", body={"foo": "bar"}),
            _record("bad", body=42),
        ]
    )

    events = OtelLogNormalizer().normalize(payload, max_events=10)

    messages = [event.message for event in events]
    assert len(events) == 4
    assert "raw body" in messages
    assert any('"key":"a"' in message for message in messages)
    assert any('"stringValue":"x"' in message for message in messages)
    assert any('"foo":"bar"' in message for message in messages)


def test_handles_all_attribute_value_shapes():
    record = _record(
        "",
        body={"stringValue": ""},
        attributes=[
            "not-a-dict",
            {"key": 1, "value": {"stringValue": "ignored"}},
            {"key": "none", "value": "raw"},
            {"key": "int", "value": {"intValue": "12"}},
            {"key": "bad_double", "value": {"doubleValue": "not-a-number"}},
            {"key": "flag", "value": {"boolValue": True}},
            {"key": "array", "value": {"arrayValue": {"values": []}}},
            {"key": "kv", "value": {"kvlistValue": {"values": []}}},
            {"key": "bad_int", "value": {"intValue": "not-an-int"}},
            {"key": "unknown", "value": {"unknownValue": True}},
            {"key": "log.message", "value": {"intValue": 123}},
        ],
    )

    events = OtelLogNormalizer().normalize(_payload_from([record]))

    assert [event.message for event in events] == ["123"]


def test_reads_alternative_metric_attribute_names():
    record = _record(
        "metrics failure",
        attributes=[
            {"key": "cpu.utilization", "value": {"doubleValue": 81.5}},
            {"key": "error.rate", "value": {"doubleValue": 0.61}},
        ],
    )

    event = OtelLogNormalizer().normalize(_payload_from([record]))[0]

    assert float(event.metrics.cpu) == 81.5
    assert float(event.metrics.error_rate) == 0.61


def test_handles_severity_aliases_zero_and_missing_values():
    normalizer = OtelLogNormalizer()

    assert normalizer.normalize(_payload(severity_text="ERR"))[0].log_level == "ERROR"
    assert normalizer.normalize(_payload(message="warning", severity_text="WARNING")) == []
    assert normalizer.normalize(_payload(message="zero", severity_text="", severity_number=0)) == []
    assert normalizer.normalize(_payload(message="missing", severity_text="")) == []


def test_evicts_deduplication_entries_above_limit():
    records = [_record(f"failure-{index}") for index in range(1001)]

    assert len(OtelLogNormalizer().normalize(_payload_from(records), max_events=1001)) == 1001


def test_otel_endpoint_reports_engine_failures(monkeypatch):
    class BrokenEngine:
        def invoke(self, *args: object, **kwargs: object) -> dict:
            raise RuntimeError("engine down")

    monkeypatch.setattr("src.adapters.fastapi_app.engine", BrokenEngine())
    otel_normalizer.clear()

    response = client.post("/ingest/otel/v1/logs", json=_payload())

    assert response.status_code == 200
    assert response.json() == {"accepted": 1, "processed": 0, "failed": 1}


def test_otel_endpoint_handles_non_anomaly_result(monkeypatch):
    class NormalEngine:
        def invoke(self, *args: object, **kwargs: object) -> dict:
            return {"is_anomaly": False}

    monkeypatch.setattr("src.adapters.fastapi_app.engine", NormalEngine())
    otel_normalizer.clear()

    response = client.post("/ingest/otel/v1/logs", json=_payload())

    assert response.status_code == 200
    assert response.json() == {"accepted": 1, "processed": 0, "failed": 0}


def test_otel_endpoint_ignores_invalid_max_events(monkeypatch):
    monkeypatch.setenv("SENTINEL_OTEL_MAX_EVENTS", "not-a-number")
    otel_normalizer.clear()

    response = client.post("/ingest/otel/v1/logs", json=_payload())

    assert response.status_code == 200
    assert response.json()["accepted"] == 1


def test_otel_endpoint_reads_max_events_from_environment(monkeypatch):
    monkeypatch.setenv("SENTINEL_OTEL_MAX_EVENTS", "1")
    otel_normalizer.clear()

    response = client.post("/ingest/otel/v1/logs", json=_payload())

    assert response.status_code == 200
    assert response.json()["accepted"] == 1


def test_reads_dedup_ttl_from_environment(monkeypatch):
    monkeypatch.setenv("SENTINEL_OTEL_DEDUP_TTL", "5")
    assert _non_negative_float_env("SENTINEL_OTEL_DEDUP_TTL", 60.0) == 5.0

    monkeypatch.setenv("SENTINEL_OTEL_DEDUP_TTL", "-1")
    assert _non_negative_float_env("SENTINEL_OTEL_DEDUP_TTL", 60.0) == 60.0

    monkeypatch.setenv("SENTINEL_OTEL_DEDUP_TTL", "not-a-number")
    assert _non_negative_float_env("SENTINEL_OTEL_DEDUP_TTL", 60.0) == 60.0
