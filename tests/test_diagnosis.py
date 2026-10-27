from src.adapters.langchain_diagnoser import LangChainDiagnoser
from src.domain.state import AnomalyAnalysisOutput, RootCauseReport, TelemetryEvent


class _FakeStructuredModel:
    def __init__(self, result: RootCauseReport | dict) -> None:
        self.result = result
        self.prompt = ""

    def invoke(self, prompt: str) -> RootCauseReport | dict:
        self.prompt = prompt
        return self.result


class _FakeChatModel:
    def __init__(self, result: RootCauseReport | dict) -> None:
        self.structured = _FakeStructuredModel(result)
        self.schema = None

    def with_structured_output(self, schema):
        self.schema = schema
        return self.structured


def _event() -> TelemetryEvent:
    return TelemetryEvent(
        id=501,
        service_name="payment-service",
        environment="production",
        timestamp="2026-10-06T16:00:00Z",
        log_level="CRITICAL",
        message="Connection failure to payment gateway API.",
        metrics={"cpu": 95.5, "error_rate": 0.45},
    )


def _analysis() -> AnomalyAnalysisOutput:
    return AnomalyAnalysisOutput(
        is_anomaly=True,
        anomaly_score=0.9,
        severity="critical",
        reasoning="Log level 'CRITICAL' is critical/high severity.",
    )


def test_langchain_diagnoser_returns_pydantic_report():
    expected = RootCauseReport(
        root_cause="Payment gateway connection pool exhausted",
        severity="critical",
        recommended_action="Restart the connection pool.",
        runbook_steps=["1. Restart the connection pool."],
    )
    fake_model = _FakeChatModel(expected)
    diagnoser = LangChainDiagnoser(fake_model)

    result = diagnoser.generate(_event(), _analysis(), ["past incident"])

    assert result is expected
    assert fake_model.schema is RootCauseReport
    assert "payment-service" in fake_model.structured.prompt
    assert "past incident" in fake_model.structured.prompt


def test_langchain_diagnoser_validates_dict_output():
    expected = RootCauseReport(
        root_cause="Payment gateway connection pool exhausted",
        severity="critical",
        recommended_action="Restart the connection pool.",
        runbook_steps=["1. Restart the connection pool."],
    )
    fake_model = _FakeChatModel(expected.model_dump())
    diagnoser = LangChainDiagnoser(fake_model)

    result = diagnoser.generate(_event(), _analysis(), [])

    assert result == expected
