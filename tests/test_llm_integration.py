import os

import pytest

from src.composition import build_diagnosis_adapter
from src.domain.state import AnomalyAnalysisOutput, RootCauseReport, TelemetryEvent

pytestmark = pytest.mark.skipif(
    os.getenv("SENTINEL_LLM_INTEGRATION") != "1",
    reason="Set SENTINEL_LLM_INTEGRATION=1 to run live provider tests.",
)

_PROVIDER_KEYS = {
    "groq": "GROQ_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "openai": "OPENAI_API_KEY",
    "ollama": "OLLAMA_API_KEY",
}


def test_live_provider_returns_valid_report(monkeypatch):
    provider = os.getenv("SENTINEL_LLM_INTEGRATION_PROVIDER", "groq").strip().lower()
    key_env = _PROVIDER_KEYS.get(provider)
    if key_env and not os.getenv(key_env) and not os.getenv("SENTINEL_LLM_API_KEY"):
        pytest.skip(f"{key_env} is not configured")
    if provider == "openrouter" and not os.getenv("SENTINEL_LLM_MODEL"):
        pytest.skip("SENTINEL_LLM_MODEL is required for OpenRouter")
    if provider == "openai-compatible":
        if not os.getenv("SENTINEL_LLM_BASE_URL"):
            pytest.skip("SENTINEL_LLM_BASE_URL is required for openai-compatible")
        if not os.getenv("SENTINEL_LLM_MODEL"):
            pytest.skip("SENTINEL_LLM_MODEL is required for openai-compatible")

    monkeypatch.setenv("SENTINEL_LLM_PROVIDER", provider)
    adapter = build_diagnosis_adapter()
    event = TelemetryEvent(
        id=9001,
        service_name="payment-service",
        environment="production",
        timestamp="2026-10-28T16:00:00Z",
        log_level="CRITICAL",
        message="Connection pool exhausted while calling the payment gateway.",
        metrics={"cpu": 95.5, "error_rate": 0.45},
    )
    analysis = AnomalyAnalysisOutput(
        is_anomaly=True,
        anomaly_score=0.9,
        severity="critical",
        reasoning="Log level 'CRITICAL' is critical/high severity.",
    )

    report = adapter.generate(event, analysis, ["Past gateway timeout incident."])

    assert isinstance(report, RootCauseReport)
    assert report.root_cause
    assert report.severity in {"critical", "major", "minor", "ok"}
    assert report.recommended_action
    assert report.runbook_steps
