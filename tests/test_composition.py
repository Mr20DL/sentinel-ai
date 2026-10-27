import pytest

from src.adapters.heuristic_diagnoser import HeuristicDiagnoser
from src.adapters.langchain_diagnoser import LangChainDiagnoser
from src.composition import build_diagnosis_adapter


def test_default_provider_is_heuristic(monkeypatch):
    monkeypatch.delenv("SENTINEL_LLM_PROVIDER", raising=False)

    assert isinstance(build_diagnosis_adapter(), HeuristicDiagnoser)


def test_unknown_provider_is_rejected(monkeypatch):
    monkeypatch.setenv("SENTINEL_LLM_PROVIDER", "unknown")

    with pytest.raises(ValueError):
        build_diagnosis_adapter()


def test_openai_provider_requires_api_key(monkeypatch):
    monkeypatch.setenv("SENTINEL_LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError):
        build_diagnosis_adapter()


def test_openai_provider_builds_adapter(monkeypatch):
    monkeypatch.setenv("SENTINEL_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    assert isinstance(build_diagnosis_adapter(), LangChainDiagnoser)


def test_ollama_provider_builds_openai_compatible_adapter(monkeypatch):
    monkeypatch.setenv("SENTINEL_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)

    assert isinstance(build_diagnosis_adapter(), LangChainDiagnoser)
