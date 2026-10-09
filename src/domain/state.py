from pydantic import BaseModel, Field
import operator
from typing import Annotated
from typing_extensions import TypedDict


class TelemetryEvent(BaseModel):
    id: int
    service_name: str
    environment: str = Field(default="production")
    timestamp: str
    log_level: str
    message: str
    metrics: dict = Field(default_factory=dict)


class AnomalyAnalysisOutput(BaseModel):
    """Contrato estructurado de salida del nodo de análisis (Structured Output, #5)."""

    is_anomaly: bool
    anomaly_score: float = Field(ge=0.0, le=1.0)
    severity: str = Field(pattern="^(critical|major|minor|ok)$")
    reasoning: str


class RootCauseReport(BaseModel):
    """Contrato estructurado de diagnóstico y runbook sugerido."""

    root_cause: str
    severity: str = Field(pattern="^(critical|major|minor|ok)$")
    recommended_action: str
    runbook_steps: list[str]


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