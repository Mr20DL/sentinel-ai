import pytest

from src.adapters.heuristic_diagnoser import HeuristicDiagnoser
from src.adapters.langchain_diagnoser import LangChainDiagnoser
from src.composition import _load_llm_settings, build_diagnosis_adapter

_ENV_VARS = (
    "SENTINEL_LLM_PROVIDER",
    "SENTINEL_LLM_MODEL",
    "SENTINEL_LLM_API_KEY",
    "SENTINEL_LLM_BASE_URL",
    "SENTINEL_LLM_STRUCTURED_METHOD",
    "SENTINEL_LLM_TIMEOUT",
    "SENTINEL_LLM_MAX_RETRIES",
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OLLAMA_API_KEY",
    "OLLAMA_BASE_URL",
)


def _clear_llm_env(monkeypatch):
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_default_provider_is_heuristic(monkeypatch):
    _clear_llm_env(monkeypatch)

    assert isinstance(build_diagnosis_adapter(), HeuristicDiagnoser)
    assert _load_llm_settings().provider == "heuristic"


def test_unknown_provider_is_rejected(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("SENTINEL_LLM_PROVIDER", "unknown")

    with pytest.raises(ValueError, match="Unsupported SENTINEL_LLM_PROVIDER"):
        build_diagnosis_adapter()


def test_openai_provider_requires_api_key(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("SENTINEL_LLM_PROVIDER", "openai")

    with pytest.raises(RuntimeError):
        build_diagnosis_adapter()


def test_openai_provider_builds_adapter(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("SENTINEL_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openai.example/v1")

    settings = _load_llm_settings()

    assert settings.model == "gpt-4o-mini"
    assert settings.base_url == "https://openai.example/v1"
    assert isinstance(build_diagnosis_adapter(), LangChainDiagnoser)


def test_ollama_provider_builds_openai_compatible_adapter(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("SENTINEL_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)

    settings = _load_llm_settings()

    assert settings.model == "llama3.1"
    assert settings.base_url == "http://localhost:11434/v1"
    assert settings.api_key == "ollama-local"
    assert isinstance(build_diagnosis_adapter(), LangChainDiagnoser)


def test_groq_provider_requires_api_key(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("SENTINEL_LLM_PROVIDER", "groq")

    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        build_diagnosis_adapter()


def test_groq_provider_builds_adapter_with_free_defaults(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("SENTINEL_LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    settings = _load_llm_settings()

    assert settings.model == "openai/gpt-oss-120b"
    assert settings.base_url == "https://api.groq.com/openai/v1"
    assert isinstance(build_diagnosis_adapter(), LangChainDiagnoser)


def test_generic_settings_override_provider_defaults(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("SENTINEL_LLM_PROVIDER", "groq")
    monkeypatch.setenv("SENTINEL_LLM_API_KEY", "generic-key")
    monkeypatch.setenv("SENTINEL_LLM_MODEL", "custom-model")
    monkeypatch.setenv("SENTINEL_LLM_BASE_URL", "https://custom.example/v1")

    settings = _load_llm_settings()

    assert settings.model == "custom-model"
    assert settings.api_key == "generic-key"
    assert settings.base_url == "https://custom.example/v1"


def test_gemini_provider_builds_adapter(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("SENTINEL_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    settings = _load_llm_settings()

    assert settings.model == "gemini-2.5-flash"
    assert settings.base_url == (
        "https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    assert isinstance(build_diagnosis_adapter(), LangChainDiagnoser)


def test_openrouter_requires_explicit_model(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("SENTINEL_LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    with pytest.raises(ValueError, match="SENTINEL_LLM_MODEL"):
        build_diagnosis_adapter()


def test_openrouter_provider_builds_adapter(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("SENTINEL_LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("SENTINEL_LLM_MODEL", "meta-llama/llama-3.3-70b-instruct:free")

    settings = _load_llm_settings()

    assert settings.model == "meta-llama/llama-3.3-70b-instruct:free"
    assert settings.base_url == "https://openrouter.ai/api/v1"
    assert isinstance(build_diagnosis_adapter(), LangChainDiagnoser)


def test_openai_compatible_requires_base_url(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("SENTINEL_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("SENTINEL_LLM_API_KEY", "test-key")
    monkeypatch.setenv("SENTINEL_LLM_MODEL", "test-model")

    with pytest.raises(ValueError, match="SENTINEL_LLM_BASE_URL"):
        build_diagnosis_adapter()


def test_openai_compatible_provider_builds_adapter(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("SENTINEL_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("SENTINEL_LLM_API_KEY", "test-key")
    monkeypatch.setenv("SENTINEL_LLM_MODEL", "test-model")
    monkeypatch.setenv("SENTINEL_LLM_BASE_URL", "https://compatible.example/v1")

    settings = _load_llm_settings()

    assert settings.model == "test-model"
    assert settings.base_url == "https://compatible.example/v1"
    assert isinstance(build_diagnosis_adapter(), LangChainDiagnoser)


def test_invalid_structured_method_is_rejected(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("SENTINEL_LLM_STRUCTURED_METHOD", "xml")

    with pytest.raises(ValueError, match="SENTINEL_LLM_STRUCTURED_METHOD"):
        _load_llm_settings()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SENTINEL_LLM_TIMEOUT", "not-a-number"),
        ("SENTINEL_LLM_MAX_RETRIES", "not-an-integer"),
        ("SENTINEL_LLM_TIMEOUT", "0"),
        ("SENTINEL_LLM_MAX_RETRIES", "-1"),
    ],
    ids=["timeout-not-number", "retries-not-integer", "timeout-zero", "retries-negative"],
)
def test_invalid_numeric_settings_are_rejected(monkeypatch, name, value):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=name):
        _load_llm_settings()
