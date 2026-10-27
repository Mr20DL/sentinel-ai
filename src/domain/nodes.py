import math
from contextlib import suppress

from src.domain.diagnosis import build_heuristic_report, build_normal_report
from src.domain.state import (
    AgentState,
    AnomalyAnalysisOutput,
    TelemetryEvent,
)
from src.ports.diagnosis import DiagnosisPort
from src.ports.notifier import NotifierPort
from src.ports.observability import ObservabilityPort
from src.ports.repository import IncidentRepositoryPort

_CRITICAL_LEVELS = {"ERROR", "CRITICAL", "FATAL"}


def _safe_metric(value: float | int | str | None, default: float = 0.0) -> float:
    """Convert a telemetry metric to a finite non-negative float."""
    if value is None:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number) or number < 0.0:
        return default
    return number


def sanitize_event(event: TelemetryEvent) -> tuple[bool, str, TelemetryEvent]:
    """Zero Trust: el ingestion_node es la frontera de confianza (ADR-0006)."""
    if not event.service_name or not event.message:
        return False, "Payload de telemetría vacío: evento rechazado en la frontera.", event
    cleaned = "".join(char for char in event.message if char.isprintable())
    sanitized_event = event.model_copy(update={"message": cleaned})
    if not cleaned.strip():
        return (
            False,
            "Payload de telemetría vacío tras sanitización: evento rechazado en la frontera.",
            sanitized_event,
        )
    if cleaned != event.message:
        return (
            True,
            "Caracteres de control eliminados del payload de telemetría.",
            sanitized_event,
        )
    return True, "Payload de telemetría validado y limpio.", sanitized_event


def create_ingestion_node(tracker: ObservabilityPort | None = None):
    def ingestion_node(state: AgentState) -> dict:
        event = state["raw_event"]
        ok, note, sanitized_event = sanitize_event(event)
        trace_id = state.get("trace_id") or f"trace-{event.id}-{event.service_name}"
        if tracker:
            with suppress(Exception):
                tracker.start_trace(trace_id, sanitized_event.model_dump())
        return {
            "raw_event": sanitized_event,
            "trace_id": trace_id,
            "sanitization_ok": ok,
            "audit_logs": [
                f"[IngestionNode] Received event from service '{event.service_name}'.",
                f"[IngestionNode] {note}",
            ],
        }

    return ingestion_node


def create_analysis_node():
    def analysis_node(state: AgentState) -> dict:
        event = state["raw_event"]
        cpu = _safe_metric(event.metrics.cpu)
        error_rate = _safe_metric(event.metrics.error_rate)
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


def create_context_node(repository: IncidentRepositoryPort):
    def context_node(state: AgentState) -> dict:
        event = state["raw_event"]
        history = repository.search_incidents(event.service_name, limit=3)
        return {
            "historical_context": history,
            "audit_logs": [
                f"[ContextNode] Retrieved {len(history)} historical records "
                f"for '{event.service_name}'."
            ],
        }

    return context_node


def create_response_node(
    notifier: NotifierPort | None = None,
    diagnoser: DiagnosisPort | None = None,
):
    def response_node(state: AgentState) -> dict:
        event = state["raw_event"]
        is_anomaly = state.get("is_anomaly", False)
        output: AnomalyAnalysisOutput | None = state.get("anomaly_output")

        fallback_used = False
        if not is_anomaly:
            report = build_normal_report()
        elif diagnoser and output:
            try:
                report = diagnoser.generate(
                    event, output, state.get("historical_context", [])
                )
            except Exception:
                report = build_heuristic_report(event, output)
                fallback_used = True
        else:
            report = build_heuristic_report(event, output)
            fallback_used = diagnoser is not None

        notification_sent = False
        if is_anomaly and notifier:
            message = (
                f"[{event.service_name}] {report.root_cause} -> "
                f"{report.recommended_action}"
            )
            notifier.send("ops-oncall", message)
            notification_sent = True

        audit_entry = (
            "[ResponseNode] Diagnosis provider unavailable; heuristic fallback used."
            if fallback_used
            else "[ResponseNode] Diagnosis and recommendation generated."
        )
        return {
            "diagnosis": report,
            "root_cause_analysis": report.root_cause,
            "recommended_action": report.recommended_action,
            "notification_sent": notification_sent,
            "audit_logs": [audit_entry],
        }

    return response_node