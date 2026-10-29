import json
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import SecretStr

from src.domain.state import AnomalyAnalysisOutput, RootCauseReport, TelemetryEvent
from src.ports.diagnosis import DiagnosisPort

StructuredMethod = Literal["function_calling", "json_mode", "json_schema"]

_SYSTEM_PROMPT = (
    "You are SentinelAI, an autonomous incident diagnostician. "
    "Use only the telemetry payload and historical context provided. "
    "Return only the structured response requested by the schema, without markdown fences "
    "or extra text. The JSON object must include root_cause, severity, recommended_action "
    "and runbook_steps. The severity must be one of critical, major, minor or ok. "
    "Provide a root cause, a recommended action and a concise ordered runbook. "
    "Do not invent credentials or external facts."
)


def _build_prompt(
    event: TelemetryEvent,
    analysis: AnomalyAnalysisOutput,
    historical_context: list[str],
) -> str:
    payload = {
        "event": {
            "id": event.id,
            "service_name": event.service_name,
            "environment": event.environment,
            "timestamp": event.timestamp.isoformat(),
            "log_level": event.log_level,
            "message": event.message,
            "metrics": event.metrics.model_dump(exclude_none=True),
        },
        "analysis": analysis.model_dump(),
        "historical_context": historical_context,
    }
    return f"{_SYSTEM_PROMPT}\nPayload:\n{json.dumps(payload, ensure_ascii=False)}"


class LangChainDiagnoser:
    """Generate a validated RootCauseReport with a LangChain chat model."""

    def __init__(
        self,
        model: BaseChatModel,
        structured_method: StructuredMethod = "function_calling",
    ):
        self._structured_model = model.with_structured_output(
            RootCauseReport, method=structured_method
        )

    def generate(
        self,
        event: TelemetryEvent,
        analysis: AnomalyAnalysisOutput,
        historical_context: list[str],
    ) -> RootCauseReport:
        prompt = _build_prompt(event, analysis, historical_context)
        result = self._structured_model.invoke(prompt)
        if isinstance(result, RootCauseReport):
            return result
        return RootCauseReport.model_validate(result)


def build_openai_diagnoser(
    *,
    model: str,
    api_key: str,
    base_url: str | None = None,
    structured_method: StructuredMethod = "function_calling",
    timeout: float = 30.0,
    max_retries: int = 2,
) -> DiagnosisPort:
    from langchain_openai import ChatOpenAI

    chat_model = ChatOpenAI(
        model=model,
        api_key=SecretStr(api_key),
        base_url=base_url,
        temperature=0.0,
        timeout=timeout,
        max_retries=max_retries,
    )
    return LangChainDiagnoser(chat_model, structured_method=structured_method)
