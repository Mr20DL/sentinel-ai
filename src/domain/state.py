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
    
class AgentState(TypedDict, total=False):
    raw_event: TelemetryEvent
    is_anomaly: bool
    anomaly_score: float
    historical_context: list[str]
    root_cause_analysis: str
    recommended_action: str
    audit_logs: Annotated[list[str], operator.add]


