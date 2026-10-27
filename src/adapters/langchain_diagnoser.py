import json

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import SecretStr

from src.domain.state import AnomalyAnalysisOutput, RootCauseReport, TelemetryEvent
from src.ports.diagnosis import DiagnosisPort

_SYSTEM_PROMPT = (
    "You are SentinelAI, an autonomous incident diagnostician. "
    "Use only the telemetry payload and historical context provided. "
    "Return a root cause, a severity from the allowed schema, a recommended action, "
    "and a concise ordered runbook. Do not invent credentials or external facts."
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

    def __init__(self, model: BaseChatModel):
        self._structured_model = model.with_structured_output(RootCauseReport)

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
) -> DiagnosisPort:
    from langchain_openai import ChatOpenAI

    chat_model = ChatOpenAI(
        model=model,
        api_key=SecretStr(api_key),
        base_url=base_url,
        temperature=0.0,
    )
    return LangChainDiagnoser(chat_model)
