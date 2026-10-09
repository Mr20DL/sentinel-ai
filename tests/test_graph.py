import pytest

from src.domain.graph import create_sentinel_graph, sentinel_app
from src.domain.state import (
    AgentState,
    AnomalyAnalysisOutput,
    RootCauseReport,
    TelemetryEvent,
)


def _event(
    log_level: str,
    message: str = "sample message",
    metrics: dict | None = None,
) -> TelemetryEvent:
    return TelemetryEvent(
        id=1,
        service_name="payment-service",
        environment="production",
        timestamp="2026-10-06T16:00:00Z",
        log_level=log_level,
        message=message,
        metrics=metrics or {"cpu": 95.5, "error_rate": 0.45},
    )


@pytest.fixture
def graph():
    return create_sentinel_graph()


@pytest.fixture
def default_app():
    return sentinel_app


def test_anomaly_path_runs_all_four_nodes(graph):
    critical_event = _event(log_level="CRITICAL")

    result = graph.invoke({"raw_event": critical_event, "audit_logs": []})

    assert result["is_anomaly"] is True
    assert result["sanitization_ok"] is True
    logs = "\n".join(result["audit_logs"])
    assert "IngestionNode" in logs
    assert "AnalysisNode" in logs
    assert "ContextNode" in logs
    assert "ResponseNode" in logs


def test_anomaly_path_produces_structured_diagnosis(graph):
    critical_event = _event(log_level="CRITICAL")

    result = graph.invoke({"raw_event": critical_event, "audit_logs": []})

    assert isinstance(result["anomaly_output"], AnomalyAnalysisOutput)
    assert result["anomaly_output"].severity == "critical"
    assert isinstance(result["diagnosis"], RootCauseReport)
    assert result["diagnosis"].root_cause
    assert result["diagnosis"].runbook_steps
    assert result["notification_sent"] is True


def test_normal_path_ends_early_at_analysis(graph):
    info_event = TelemetryEvent(
        id=2,
        service_name="payment-service",
        timestamp="2026-10-06T16:00:00Z",
        log_level="INFO",
        message="Payment processed successfully",
        metrics={"cpu": 35.0, "error_rate": 0.01},
    )

    result = graph.invoke({"raw_event": info_event, "audit_logs": []})

    assert result["is_anomaly"] is False
    assert result["anomaly_output"].severity == "ok"
    logs = "\n".join(result["audit_logs"])
    assert "IngestionNode" in logs
    assert "AnalysisNode" in logs
    assert "ContextNode" not in logs
    assert "ResponseNode" not in logs
    assert result.get("diagnosis") is None


def test_analysis_evaluates_metrics_thresholds(graph):
    high_cpu_event = _event(log_level="WARNING", metrics={"cpu": 96.0, "error_rate": 0.05})

    result = graph.invoke({"raw_event": high_cpu_event, "audit_logs": []})

    assert result["is_anomaly"] is True
    assert result["anomaly_score"] >= 0.85


def test_zero_trust_rejects_empty_payload(graph):
    empty_event = TelemetryEvent(
        id=3,
        service_name="",
        timestamp="2026-10-06T16:00:00Z",
        log_level="CRITICAL",
        message="",
    )

    result = graph.invoke({"raw_event": empty_event, "audit_logs": []})

    assert result["sanitization_ok"] is False