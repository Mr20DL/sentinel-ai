import re

from src.domain.state import (
    AgentState,
    AnomalyAnalysisOutput,
    RootCauseReport,
    TelemetryEvent,
)
from src.ports.notifier import NotifierPort
from src.ports.observability import ObservabilityPort
from src.ports.repository import IncidentRepositoryPort

_CRITICAL_LEVELS = {"ERROR", "CRITICAL", "FATAL"}


def sanitize_event(event: TelemetryEvent) -> tuple[bool, str]:
    """Zero Trust: el ingestion_node es la frontera de confianza (ADR-0006)."""
    if not event.service_name or not event.message:
        return False, "Payload de telemetría vacío: evento rechazado en la frontera."
    cleaned = re.sub(r"[^\x20-\x7E]", "", event.message)
    if len(cleaned) != len(event.message):
        return True, "Caracteres de control eliminados del payload de telemetría."
    return True, "Payload de telemetría validado y limpio."


def create_ingestion_node(tracker: ObservabilityPort | None = None):
    def ingestion_node(state: AgentState) -> dict:
        event = state["raw_event"]
        ok, note = sanitize_event(event)
        trace_id = state.get("trace_id") or f"trace-{event.id}-{event.service_name}"
        if tracker:
            tracker.start_trace(trace_id, event.model_dump())
        return {
            "trace_id": trace_id,
            "sanitization_ok": ok,
            "audit_logs": [
                f"[IngestionNode] Received event from service '{event.service_name}'.",
                f"[IngestionNode] {note}",
            ],
        }

    return ingestion_node


def create_analysis_node(tracker: ObservabilityPort | None = None):
    def analysis_node(state: AgentState) -> dict:
        event = state["raw_event"]
        cpu = float(event.metrics.get("cpu", 0.0))
        error_rate = float(event.metrics.get("error_rate", 0.0))
        level = event.log_level.upper()

        is_anomaly = (
            level in _CRITICAL_LEVELS or cpu >= 90.0 or error_rate >= 0.40
        )
        if level in _CRITICAL_LEVELS:
            score = 0.9
            reasoning = f"Log level '{event.log_level}' is critical/high severity."
        elif cpu >= 90.0:
            score = 0.85
            reasoning = f"CPU at {cpu:.1f}% exceeds the 90% alerting threshold."
        elif error_rate >= 0.40:
            score = 0.8
            reasoning = f"Error rate at {error_rate:.2f} exceeds the 0.40 threshold."
        else:
            score = 0.1
            reasoning = "Event matches expected operational behavior."

        severity = (
            "critical"
            if score >= 0.85
            else "major"
            if score >= 0.6
            else "minor"
            if is_anomaly
            else "ok"
        )
        output = AnomalyAnalysisOutput(
            is_anomaly=is_anomaly,
            anomaly_score=round(score, 2),
            severity=severity,
            reasoning=reasoning,
        )

        return {
            "is_anomaly": is_anomaly,
            "anomaly_score": round(score, 2),
            "anomaly_output": output,
            "audit_logs": [
                f"[AnalysisNode] Evaluated anomaly status: {is_anomaly} (score: {score:.2f})."
            ],
        }

    return analysis_node


def create_context_node(
    repository: IncidentRepositoryPort,
    tracker: ObservabilityPort | None = None,
):
    def context_node(state: AgentState) -> dict:
        event = state["raw_event"]
        history = repository.search_incidents(event.service_name, limit=3)
        return {
            "historical_context": history,
            "audit_logs": [
                f"[ContextNode] Retrieved {len(history)} historical records for '{event.service_name}'."
            ],
        }

    return context_node


def create_response_node(
    notifier: NotifierPort | None = None,
    tracker: ObservabilityPort | None = None,
):
    def response_node(state: AgentState) -> dict:
        event = state["raw_event"]
        is_anomaly = state.get("is_anomaly", False)
        output: AnomalyAnalysisOutput | None = state.get("anomaly_output")

        if is_anomaly:
            root_cause = f"Critical log level detected in {event.service_name}"
            recommendation = "Restart application connection pool and monitor latency."
            runbook = [
                "1. Confirm incident in downstream dependency (payment gateway).",
                f"2. Restart the connection pool of '{event.service_name}'.",
                "3. Monitor latency and error_rate for 15 minutes.",
                "4. Escalate to on-call SRE if anomalies persist.",
            ]
        else:
            root_cause = "Normal activity"
            recommendation = "No action required."
            runbook = []

        report = RootCauseReport(
            root_cause=root_cause,
            severity=output.severity if output else ("ok" if not is_anomaly else "critical"),
            recommended_action=recommendation,
            runbook_steps=runbook,
        )

        notification_sent = False
        if is_anomaly and notifier:
            message = f"[{event.service_name}] {root_cause} -> {recommendation}"
            notifier.send("ops-oncall", message)
            notification_sent = True

        return {
            "diagnosis": report,
            "root_cause_analysis": root_cause,
            "recommended_action": recommendation,
            "notification_sent": notification_sent,
            "audit_logs": ["[ResponseNode] Diagnosis and recommendation generated."],
        }

    return response_node