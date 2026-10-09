from fastapi.testclient import TestClient

from src.adapters.fastapi_app import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


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