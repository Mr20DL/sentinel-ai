from datetime import datetime

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END
from pydantic import ValidationError

from src.composition import build_default_components
from src.domain.graph import (
    create_sentinel_graph,
    sentinel_app,
    should_continue,
    should_process,
)
from src.domain.nodes import create_ingestion_node, create_response_node
from src.domain.state import (
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


class _FailingTracker:
    def start_trace(self, trace_id: str, event: dict) -> None:
        raise RuntimeError("tracker unavailable")

    def record_step(self, trace_id: str, node: str, payload: dict) -> None:
        raise RuntimeError("tracker unavailable")


class _StubDiagnoser:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def generate(self, event, analysis, historical_context):
        self.calls.append((event, analysis, historical_context))
        return RootCauseReport(
            root_cause="LLM root cause",
            severity="critical",
            recommended_action="Scale the service.",
            runbook_steps=["1. Scale the service."],
        )


class _FailingDiagnoser:
    def generate(self, event, analysis, historical_context):
        raise RuntimeError("diagnosis provider unavailable")


@pytest.fixture
def graph():
    return create_sentinel_graph()


@pytest.fixture
def default_app():
    return sentinel_app


def test_anomaly_path_runs_all_four_nodes(graph):
    critical_event = _event(log_level="CRITICAL")
    cfg = {"configurable": {"thread_id": "test-anom"}}

    result = graph.invoke({"raw_event": critical_event, "audit_logs": []}, config=cfg)

    assert result["is_anomaly"] is True
    assert result["sanitization_ok"] is True
    logs = "\n".join(result["audit_logs"])
    assert "IngestionNode" in logs
    assert "AnalysisNode" in logs
    assert "ContextNode" in logs
    assert "ResponseNode" in logs


def test_anomaly_path_produces_structured_diagnosis(graph):
    critical_event = _event(log_level="CRITICAL")
    cfg = {"configurable": {"thread_id": "test-anom2"}}

    result = graph.invoke({"raw_event": critical_event, "audit_logs": []}, config=cfg)

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
    cfg = {"configurable": {"thread_id": "test-norm"}}

    result = graph.invoke({"raw_event": info_event, "audit_logs": []}, config=cfg)

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
    cfg = {"configurable": {"thread_id": "test-metrics"}}

    result = graph.invoke({"raw_event": high_cpu_event, "audit_logs": []}, config=cfg)

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
    cfg = {"configurable": {"thread_id": "test-zt"}}

    result = graph.invoke({"raw_event": empty_event, "audit_logs": []}, config=cfg)

    assert result["sanitization_ok"] is False
    logs = "\n".join(result["audit_logs"])
    assert "IngestionNode" in logs
    assert "AnalysisNode" not in logs
    assert result.get("diagnosis") is None
    assert result.get("notification_sent") is not True


@pytest.mark.parametrize(
    "metrics",
    [
        {"cpu": "high", "error_rate": None},
        {"cpu": None, "error_rate": "N/A"},
        {"cpu": float("nan"), "error_rate": float("inf")},
        {"error_rate": 0.01},
    ],
    ids=["string-and-none", "none-and-text", "nan-and-inf", "missing-cpu"],
)
def test_analysis_handles_malformed_metrics(graph, metrics, request):
    event = _event(log_level="INFO", metrics=metrics)
    cfg = {
        "configurable": {
            "thread_id": f"test-malformed-{request.node.callspec.id}",
        }
    }

    result = graph.invoke({"raw_event": event, "audit_logs": []}, config=cfg)

    assert result["sanitization_ok"] is True
    assert result["is_anomaly"] is False
    assert 0.0 <= result["anomaly_score"] <= 1.0
    assert isinstance(result["anomaly_output"], AnomalyAnalysisOutput)


def test_sanitizes_control_characters(graph):
    event = _event(log_level="INFO", message="valid\x00message")
    cfg = {"configurable": {"thread_id": "test-control-chars"}}

    result = graph.invoke({"raw_event": event, "audit_logs": []}, config=cfg)

    assert result["sanitization_ok"] is True
    assert result["raw_event"].message == "validmessage"
    logs = "\n".join(result["audit_logs"])
    assert "Caracteres de control eliminados" in logs


def test_sanitize_preserves_unicode(graph):
    message = "Informe de caída del servicio 🚨"
    event = _event(log_level="INFO", message=message)
    cfg = {"configurable": {"thread_id": "test-unicode"}}

    result = graph.invoke({"raw_event": event, "audit_logs": []}, config=cfg)

    assert result["sanitization_ok"] is True
    assert result["raw_event"].message == message
    logs = "\n".join(result["audit_logs"])
    assert "validado y limpio" in logs


def test_rejects_message_empty_after_sanitization(graph):
    event = _event(log_level="CRITICAL", message="\x00\x01")
    cfg = {"configurable": {"thread_id": "test-empty-after-sanitize"}}

    result = graph.invoke({"raw_event": event, "audit_logs": []}, config=cfg)

    assert result["sanitization_ok"] is False
    logs = "\n".join(result["audit_logs"])
    assert "AnalysisNode" not in logs
    assert result.get("diagnosis") is None


def test_ingestion_without_tracker():
    node = create_ingestion_node(None)

    result = node({"raw_event": _event(log_level="INFO"), "audit_logs": []})

    assert result["sanitization_ok"] is True
    assert result["trace_id"].startswith("trace-")


def test_graph_uses_injected_diagnoser():
    diagnoser = _StubDiagnoser()
    components = build_default_components()
    components["diagnoser"] = diagnoser
    graph = create_sentinel_graph(components=components)
    event = _event(log_level="CRITICAL")
    cfg = {"configurable": {"thread_id": "test-diagnoser"}}

    result = graph.invoke({"raw_event": event, "audit_logs": []}, config=cfg)

    assert result["diagnosis"].root_cause == "LLM root cause"
    assert result["recommended_action"] == "Scale the service."
    assert len(diagnoser.calls) == 1


def test_response_node_uses_diagnoser():
    diagnoser = _StubDiagnoser()
    node = create_response_node(diagnoser=diagnoser)
    event = _event(log_level="CRITICAL")
    analysis = AnomalyAnalysisOutput(
        is_anomaly=True,
        anomaly_score=0.9,
        severity="critical",
        reasoning="Log level 'CRITICAL' is critical/high severity.",
    )

    result = node(
        {
            "raw_event": event,
            "is_anomaly": True,
            "anomaly_output": analysis,
            "historical_context": ["past incident"],
        }
    )

    assert result["diagnosis"].root_cause == "LLM root cause"
    assert result["notification_sent"] is False
    assert diagnoser.calls == [(event, analysis, ["past incident"])]


def test_response_node_uses_heuristic_without_diagnoser():
    node = create_response_node()
    event = _event(log_level="CRITICAL")
    analysis = AnomalyAnalysisOutput(
        is_anomaly=True,
        anomaly_score=0.9,
        severity="critical",
        reasoning="Log level 'CRITICAL' is critical/high severity.",
    )

    result = node(
        {
            "raw_event": event,
            "is_anomaly": True,
            "anomaly_output": analysis,
            "historical_context": [],
        }
    )

    assert result["diagnosis"].root_cause == "Critical log level detected in payment-service"
    assert "fallback" not in result["audit_logs"][0]


def test_response_node_falls_back_when_diagnoser_fails():
    node = create_response_node(diagnoser=_FailingDiagnoser())
    event = _event(log_level="CRITICAL")
    analysis = AnomalyAnalysisOutput(
        is_anomaly=True,
        anomaly_score=0.9,
        severity="critical",
        reasoning="Log level 'CRITICAL' is critical/high severity.",
    )

    result = node(
        {
            "raw_event": event,
            "is_anomaly": True,
            "anomaly_output": analysis,
            "historical_context": [],
        }
    )

    assert result["diagnosis"].root_cause == "Critical log level detected in payment-service"
    assert "fallback" in result["audit_logs"][0]


def test_graph_survives_tracker_failure():
    components = build_default_components()
    components["tracker"] = _FailingTracker()
    graph = create_sentinel_graph(components=components)
    event = _event(log_level="CRITICAL")
    cfg = {"configurable": {"thread_id": "test-tracker-failure"}}

    result = graph.invoke({"raw_event": event, "audit_logs": []}, config=cfg)

    assert result["sanitization_ok"] is True
    assert result["diagnosis"] is not None
    assert result["notification_sent"] is True


def test_telemetry_contract_types_timestamp_and_metrics():
    event = _event(log_level="INFO", metrics={"cpu": "high", "memory_mb": 512})

    assert isinstance(event.timestamp, datetime)
    assert event.metrics.cpu == "high"
    assert event.metrics.error_rate is None
    assert event.metrics.model_extra == {"memory_mb": 512}


def test_telemetry_rejects_naive_timestamp():
    with pytest.raises(ValidationError):
        TelemetryEvent(
            id=99,
            service_name="payment-service",
            timestamp="2026-10-06T16:00:00",
            log_level="INFO",
            message="sample message",
        )


def test_error_rate_triggers_anomaly(graph):
    event = _event(
        log_level="WARNING",
        metrics={"cpu": 10.0, "error_rate": 0.5},
    )
    cfg = {"configurable": {"thread_id": "test-error-rate"}}

    result = graph.invoke({"raw_event": event, "audit_logs": []}, config=cfg)

    assert result["is_anomaly"] is True
    assert result["anomaly_score"] == 0.8
    assert result["anomaly_output"].severity == "major"


def test_response_node_normal_path():
    node = create_response_node()
    event = _event(log_level="INFO", metrics={"cpu": 10.0, "error_rate": 0.01})

    result = node({"raw_event": event, "is_anomaly": False})

    assert result["diagnosis"].severity == "ok"
    assert result["diagnosis"].runbook_steps == []
    assert result["notification_sent"] is False


def test_conditional_routing_gates_on_sanitization():
    assert should_process({"sanitization_ok": False}) == END
    assert should_process({"sanitization_ok": True}) == "analysis_node"
    assert should_continue({"sanitization_ok": False, "is_anomaly": True}) == END
    assert should_continue({"sanitization_ok": True, "is_anomaly": True}) == "context_node"
    assert should_continue({"sanitization_ok": True, "is_anomaly": False}) == END


def test_graph_accepts_custom_checkpointer():
    graph = create_sentinel_graph(checkpointer=MemorySaver())
    event = _event(log_level="INFO", metrics={"cpu": 10.0, "error_rate": 0.01})
    cfg = {"configurable": {"thread_id": "test-custom-checkpointer"}}

    result = graph.invoke({"raw_event": event, "audit_logs": []}, config=cfg)

    assert result["is_anomaly"] is False
