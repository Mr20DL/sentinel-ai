from src.domain.state import AnomalyAnalysisOutput, RootCauseReport, TelemetryEvent


def build_normal_report() -> RootCauseReport:
    """Return the structured report used when the event is not an anomaly."""
    return RootCauseReport(
        root_cause="Normal activity",
        severity="ok",
        recommended_action="No action required.",
        runbook_steps=[],
    )


def build_heuristic_report(
    event: TelemetryEvent,
    analysis: AnomalyAnalysisOutput | None,
) -> RootCauseReport:
    """Build a deterministic fallback diagnosis when no LLM is available."""
    reasoning = analysis.reasoning if analysis else ""
    if "CPU" in reasoning:
        root_cause = f"CPU saturation detected in {event.service_name}"
    elif "Error rate" in reasoning:
        root_cause = f"Elevated error rate detected in {event.service_name}"
    else:
        root_cause = f"Critical log level detected in {event.service_name}"

    return RootCauseReport(
        root_cause=root_cause,
        severity=analysis.severity if analysis else "critical",
        recommended_action="Restart application connection pool and monitor latency.",
        runbook_steps=[
            "1. Confirm incident in downstream dependency (payment gateway).",
            f"2. Restart the connection pool of '{event.service_name}'.",
            "3. Monitor latency and error_rate for 15 minutes.",
            "4. Escalate to on-call SRE if anomalies persist.",
        ],
    )
