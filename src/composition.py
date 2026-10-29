import os
from dataclasses import dataclass
from typing import cast

from src.adapters.console_notifier import ConsoleNotifier
from src.adapters.heuristic_diagnoser import HeuristicDiagnoser
from src.adapters.in_memory_repository import InMemoryRepository
from src.adapters.langfuse_tracker import NoopTracker
from src.ports.diagnosis import DiagnosisPort

_PROVIDER_DEFAULTS: dict[str, tuple[str, str | None]] = {
    "groq": ("openai/gpt-oss-120b", "https://api.groq.com/openai/v1"),
    "gemini": (
        "gemini-2.5-flash",
        "https://generativelanguage.googleapis.com/v1beta/openai/",
    ),
    "openrouter": ("", "https://openrouter.ai/api/v1"),
    "ollama": ("llama3.1", "http://localhost:11434/v1"),
    "openai": ("gpt-4o-mini", None),
}
_PROVIDER_KEY_ENV = {
    "groq": "GROQ_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "openai": "OPENAI_API_KEY",
    "ollama": "OLLAMA_API_KEY",
}
_ALLOWED_STRUCTURED_METHODS = {"function_calling", "json_mode", "json_schema"}


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    model: str
    api_key: str
    base_url: str | None
    structured_method: str
    timeout: float
    max_retries: int


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid number") from exc


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid integer") from exc


def _load_llm_settings() -> LLMSettings:
    provider = os.getenv("SENTINEL_LLM_PROVIDER", "heuristic").strip().lower()
    structured_method = (
        os.getenv("SENTINEL_LLM_STRUCTURED_METHOD", "function_calling").strip().lower()
    )
    if structured_method not in _ALLOWED_STRUCTURED_METHODS:
        raise ValueError(
            "SENTINEL_LLM_STRUCTURED_METHOD must be one of "
            "function_calling, json_mode or json_schema"
        )
    timeout = _env_float("SENTINEL_LLM_TIMEOUT", 30.0)
    max_retries = _env_int("SENTINEL_LLM_MAX_RETRIES", 2)
    if timeout <= 0:
        raise ValueError("SENTINEL_LLM_TIMEOUT must be greater than zero")
    if max_retries < 0:
        raise ValueError("SENTINEL_LLM_MAX_RETRIES cannot be negative")

    if provider in {"", "heuristic", "mock"}:
        return LLMSettings(
            provider="heuristic",
            model="",
            api_key="",
            base_url=None,
            structured_method=structured_method,
            timeout=timeout,
            max_retries=max_retries,
        )
    if provider != "openai-compatible" and provider not in _PROVIDER_DEFAULTS:
        raise ValueError(f"Unsupported SENTINEL_LLM_PROVIDER: {provider}")

    default_model, default_base_url = _PROVIDER_DEFAULTS.get(provider, ("", None))
    model = (os.getenv("SENTINEL_LLM_MODEL") or default_model).strip()
    if not model:
        raise ValueError(
            "SENTINEL_LLM_MODEL is required for provider "
            f"'{provider}'"
        )

    api_key = os.getenv("SENTINEL_LLM_API_KEY", "").strip()
    key_env = _PROVIDER_KEY_ENV.get(provider)
    if not api_key and key_env:
        api_key = os.getenv(key_env, "").strip()
    if provider == "ollama" and not api_key:
        api_key = "ollama-local"
    if not api_key:
        raise RuntimeError(
            f"{key_env or 'SENTINEL_LLM_API_KEY'} is required when "
            f"SENTINEL_LLM_PROVIDER={provider}"
        )

    base_url = os.getenv("SENTINEL_LLM_BASE_URL", "").strip() or default_base_url
    if provider == "openai" and not os.getenv("SENTINEL_LLM_BASE_URL"):
        base_url = os.getenv("OPENAI_BASE_URL", "").strip() or default_base_url
    if provider == "ollama" and not os.getenv("SENTINEL_LLM_BASE_URL"):
        base_url = os.getenv("OLLAMA_BASE_URL", "").strip() or default_base_url
    if provider == "openai-compatible" and not base_url:
        raise ValueError(
            "SENTINEL_LLM_BASE_URL is required when "
            "SENTINEL_LLM_PROVIDER=openai-compatible"
        )

    return LLMSettings(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        structured_method=structured_method,
        timeout=timeout,
        max_retries=max_retries,
    )


def build_diagnosis_adapter() -> DiagnosisPort:
    """Select the diagnosis provider from the environment (composition root)."""
    settings = _load_llm_settings()
    if settings.provider == "heuristic":
        return HeuristicDiagnoser()

    from src.adapters.langchain_diagnoser import StructuredMethod, build_openai_diagnoser

    return build_openai_diagnoser(
        model=settings.model,
        api_key=settings.api_key,
        base_url=settings.base_url,
        structured_method=cast(StructuredMethod, settings.structured_method),
        timeout=settings.timeout,
        max_retries=settings.max_retries,
    )


def build_default_components() -> dict:
    """Composition root: adaptadores por defecto para desarrollo (hexagonal)."""
    return {
        "repository": InMemoryRepository(),
        "notifier": ConsoleNotifier(),
        "tracker": NoopTracker(),
        "diagnoser": build_diagnosis_adapter(),
    }
