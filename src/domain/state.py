import operator
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing_extensions import TypedDict


class TelemetryMetrics(BaseModel):
    """Common telemetry metrics with tolerant raw values for zero-trust ingestion."""

    model_config = ConfigDict(extra="allow")

    cpu: float | int | str | None = None
    error_rate: float | int | str | None = None


class TelemetryEvent(BaseModel):
    id: int
    service_name: str
    environment: str = Field(default="production")
    timestamp: datetime
    log_level: str
    message: str
    metrics: TelemetryMetrics = Field(default_factory=TelemetryMetrics)

    @field_validator("timestamp")
    @classmethod
    def _timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include timezone information")
        return value


class AnomalyAnalysisOutput(BaseModel):
    """Contrato estructurado de salida del nodo de análisis (Structured Output, #5)."""

    is_anomaly: bool
    anomaly_score: float = Field(ge=0.0, le=1.0)
    severity: str = Field(pattern="^(critical|major|minor|ok)$")
    reasoning: str


class RootCauseReport(BaseModel):
    """Structured diagnosis and runbook contract."""

    root_cause: str
    severity: str = Field(pattern="^(critical|major|minor|ok)$")
    recommended_action: str
    runbook_steps: list[str]


class EventSnapshot(BaseModel):
    """Summary of a processed event for the live dashboard."""

    event_id: int
    service_name: str
    environment: str
    timestamp: datetime
    log_level: str
    message: str
    sanitization_ok: bool
    is_anomaly: bool
    anomaly_score: float = Field(ge=0.0, le=1.0)
    severity: str = Field(pattern="^(critical|major|minor|ok)$")
    root_cause: str | None = None
    recommended_action: str | None = None
    runbook_steps: list[str] = Field(default_factory=list)
    trace_id: str | None = None

    @classmethod
    def from_result(cls, event: TelemetryEvent, result: dict) -> "EventSnapshot":
        sanitized = result.get("raw_event")
        if not isinstance(sanitized, TelemetryEvent):
            sanitized = event

        output = result.get("anomaly_output")
        analysis = output if isinstance(output, AnomalyAnalysisOutput) else None
        diagnosis = result.get("diagnosis")
        report = diagnosis if isinstance(diagnosis, RootCauseReport) else None
        raw_score = result.get("anomaly_score")
        try:
            score = float(raw_score) if raw_score is not None else 0.0
        except (TypeError, ValueError):
            score = 0.0
        if not 0.0 <= score <= 1.0:
            score = 0.0
        trace_id = result.get("trace_id")

        return cls(
            event_id=sanitized.id,
            service_name=sanitized.service_name,
            environment=sanitized.environment,
            timestamp=sanitized.timestamp,
            log_level=sanitized.log_level,
            message=sanitized.message,
            sanitization_ok=bool(result.get("sanitization_ok", True)),
            is_anomaly=bool(result.get("is_anomaly", False)),
            anomaly_score=score,
            severity=analysis.severity if analysis else "ok",
            root_cause=report.root_cause if report else None,
            recommended_action=report.recommended_action if report else None,
            runbook_steps=list(report.runbook_steps) if report else [],
            trace_id=trace_id if isinstance(trace_id, str) else None,
        )


class AgentState(TypedDict, total=False):
    raw_event: TelemetryEvent
    trace_id: str
    sanitization_ok: bool
    is_anomaly: bool
    anomaly_score: float
    anomaly_output: AnomalyAnalysisOutput
    historical_context: list[str]
    diagnosis: RootCauseReport
    root_cause_analysis: str
    recommended_action: str
    notification_sent: bool
    audit_logs: Annotated[list[str], operator.add]
