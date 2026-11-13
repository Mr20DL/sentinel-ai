from fastapi.testclient import TestClient

from src.adapters.fastapi_app import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_endpoint_describes_service():
    response = client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "sentinel-ai"
    assert body["health"] == "/health"
    assert body["events"] == "/events"
    assert body["otel_logs"] == "/ingest/otel/v1/logs"
    assert body["otel_worker"] == "/internal/otel/process"


def test_ingest_anomaly_event():
    payload = {
        "id": 10,
        "service_name": "payment-service",
        "environment": "production",
        "timestamp": "2026-10-06T16:00:00Z",
        "log_level": "CRITICAL",
        "message": "Connection failure to payment gateway API.",
        "metrics": {"cpu": 95.5, "error_rate": 0.45},
    }

    response = client.post("/events", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["is_anomaly"] is True
    assert body["trace_id"].startswith("trace-")
    assert body["diagnosis"]["recommended_action"]
    assert body["diagnosis"]["runbook_steps"]
    assert len(body["audit_logs"]) >= 5


def test_ingest_rejects_invalid_payload():
    response = client.post("/events", json={"id": "no-amount"})
    assert response.status_code == 422


def test_events_requires_key_when_configured(monkeypatch):
    monkeypatch.setenv("SENTINEL_INGEST_API_KEY", "test-secret")
    payload = {
        "id": 800001,
        "service_name": "payment-service",
        "environment": "production",
        "timestamp": "2026-10-06T16:00:00Z",
        "log_level": "CRITICAL",
        "message": "Connection failure to payment gateway API.",
        "metrics": {"cpu": 95.5, "error_rate": 0.45},
    }

    unauthorized = client.post("/events", json=payload)
    authorized = client.post("/events", json=payload, headers={"X-Ingest-Key": "test-secret"})

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200


def _worker_event(event_id: int = 910001) -> dict:
    return {
        "id": event_id,
        "service_name": "payment-service",
        "environment": "production",
        "timestamp": "2026-11-09T12:00:00Z",
        "log_level": "CRITICAL",
        "message": "Connection failure to payment gateway API.",
        "metrics": {"cpu": 95.5, "error_rate": 0.45},
    }


class _RemoteQueue:
    is_remote = True

    def __init__(self, valid_signature: bool = True) -> None:
        self.valid_signature = valid_signature
        self.published = []

    def publish(self, event: object) -> None:
        self.published.append(event)

    def verify_signature(self, body: bytes, signature: str) -> bool:
        return self.valid_signature


def test_worker_endpoint_is_disabled_for_inline_queue():
    response = client.post("/internal/otel/process", json=_worker_event())

    assert response.status_code == 404


def test_worker_endpoint_rejects_missing_signature(monkeypatch):
    monkeypatch.setattr("src.adapters.fastapi_app.telemetry_queue", _RemoteQueue())

    response = client.post("/internal/otel/process", json=_worker_event())

    assert response.status_code == 401


def test_worker_endpoint_rejects_invalid_signature(monkeypatch):
    monkeypatch.setattr(
        "src.adapters.fastapi_app.telemetry_queue",
        _RemoteQueue(valid_signature=False),
    )

    response = client.post(
        "/internal/otel/process",
        json=_worker_event(),
        headers={"Upstash-Signature": "invalid"},
    )

    assert response.status_code == 401


def test_worker_endpoint_processes_signed_event(monkeypatch):
    monkeypatch.setattr("src.adapters.fastapi_app.telemetry_queue", _RemoteQueue())

    response = client.post(
        "/internal/otel/process",
        json=_worker_event(),
        headers={"Upstash-Signature": "valid"},
    )

    assert response.status_code == 200
    assert response.json() == {"processed": 1, "is_anomaly": True}


def test_worker_endpoint_rejects_invalid_event(monkeypatch):
    monkeypatch.setattr("src.adapters.fastapi_app.telemetry_queue", _RemoteQueue())

    response = client.post(
        "/internal/otel/process",
        json={"id": "not-an-integer"},
        headers={"Upstash-Signature": "valid"},
    )

    assert response.status_code == 400


def test_worker_endpoint_reports_engine_failures(monkeypatch):
    class BrokenEngine:
        def invoke(self, *args: object, **kwargs: object) -> dict:
            raise RuntimeError("engine down")

    monkeypatch.setattr("src.adapters.fastapi_app.telemetry_queue", _RemoteQueue())
    monkeypatch.setattr("src.adapters.fastapi_app.engine", BrokenEngine())

    response = client.post(
        "/internal/otel/process",
        json=_worker_event(),
        headers={"Upstash-Signature": "valid"},
    )

    assert response.status_code == 500


def test_same_event_id_does_not_reuse_checkpoint():
    critical = {
        "id": 700001,
        "service_name": "payment-service",
        "environment": "production",
        "timestamp": "2026-10-06T16:00:00Z",
        "log_level": "CRITICAL",
        "message": "Connection failure to payment gateway API.",
        "metrics": {"cpu": 95.5, "error_rate": 0.45},
    }
    normal = {
        "id": 700001,
        "service_name": "checkout-service",
        "environment": "production",
        "timestamp": "2026-10-06T16:05:00Z",
        "log_level": "INFO",
        "message": "Checkout completed successfully.",
        "metrics": {"cpu": 10.0, "error_rate": 0.01},
    }

    first = client.post("/events", json=critical)
    second = client.post("/events", json=normal)

    assert first.status_code == 200
    assert first.json()["is_anomaly"] is True
    assert first.json()["diagnosis"] is not None

    body = second.json()
    assert second.status_code == 200
    assert body["is_anomaly"] is False
    assert body["diagnosis"] is None
    assert body["trace_id"] == "trace-700001-checkout-service"
    assert len(body["audit_logs"]) == 3
