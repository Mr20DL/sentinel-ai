import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast
from urllib.parse import urlparse

from src.adapters.console_notifier import ConsoleNotifier
from src.adapters.gemini_embeddings import GeminiEmbeddingAdapter
from src.adapters.heuristic_diagnoser import HeuristicDiagnoser
from src.adapters.in_memory_event_feed import InMemoryEventFeed
from src.adapters.in_memory_repository import InMemoryRepository
from src.adapters.langfuse_tracker import LangfuseTracker, NoopTracker
from src.adapters.neon_db import PostgresIncidentRepository
from src.adapters.rate_limiter import SlidingWindowRateLimiter
from src.adapters.telemetry_queue import InlineTelemetryQueue, QStashTelemetryQueue
from src.adapters.webhook_notifier import WebhookNotifier
from src.domain.state import TelemetryEvent
from src.ports.diagnosis import DiagnosisPort
from src.ports.embeddings import EmbeddingPort
from src.ports.event_feed import EventFeedPort
from src.ports.notifier import NotifierPort
from src.ports.observability import ObservabilityPort
from src.ports.queue import TelemetryQueuePort
from src.ports.repository import IncidentRepositoryPort

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


@dataclass(frozen=True)
class EmbeddingSettings:
    provider: str
    model: str
    api_key: str
    dimensions: int
    timeout: float


@dataclass(frozen=True)
class QueueSettings:
    provider: str
    token: str
    destination_url: str
    current_signing_key: str
    next_signing_key: str
    base_url: str | None


@dataclass(frozen=True)
class NotifierSettings:
    provider: str
    webhook_url: str
    timeout: float
    max_retries: int
    backoff_seconds: float


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
        raise ValueError(f"SENTINEL_LLM_MODEL is required for provider '{provider}'")

    api_key = os.getenv("SENTINEL_LLM_API_KEY", "").strip()
    key_env = _PROVIDER_KEY_ENV.get(provider)
    if not api_key and key_env:
        api_key = os.getenv(key_env, "").strip()
    if provider == "ollama" and not api_key:
        api_key = "ollama-local"
    if not api_key:
        raise RuntimeError(
            f"{key_env or 'SENTINEL_LLM_API_KEY'} is required when SENTINEL_LLM_PROVIDER={provider}"
        )

    base_url = os.getenv("SENTINEL_LLM_BASE_URL", "").strip() or default_base_url
    if provider == "openai" and not os.getenv("SENTINEL_LLM_BASE_URL"):
        base_url = os.getenv("OPENAI_BASE_URL", "").strip() or default_base_url
    if provider == "ollama" and not os.getenv("SENTINEL_LLM_BASE_URL"):
        base_url = os.getenv("OLLAMA_BASE_URL", "").strip() or default_base_url
    if provider == "openai-compatible" and not base_url:
        raise ValueError(
            "SENTINEL_LLM_BASE_URL is required when SENTINEL_LLM_PROVIDER=openai-compatible"
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


def _load_embedding_settings() -> EmbeddingSettings:
    provider = os.getenv("SENTINEL_EMBEDDING_PROVIDER", "disabled").strip().lower()
    dimensions = _env_int("SENTINEL_EMBEDDING_DIMENSIONS", 384)
    timeout = _env_float("SENTINEL_EMBEDDING_TIMEOUT", 20.0)
    if dimensions <= 0:
        raise ValueError("SENTINEL_EMBEDDING_DIMENSIONS must be greater than zero")
    if timeout <= 0:
        raise ValueError("SENTINEL_EMBEDDING_TIMEOUT must be greater than zero")

    if provider in {"", "disabled", "heuristic", "none"}:
        return EmbeddingSettings(
            provider="disabled",
            model="",
            api_key="",
            dimensions=dimensions,
            timeout=timeout,
        )
    if provider != "gemini":
        raise ValueError(f"Unsupported SENTINEL_EMBEDDING_PROVIDER: {provider}")

    model = (
        os.getenv("SENTINEL_EMBEDDING_MODEL", "gemini-embedding-2").strip() or "gemini-embedding-2"
    )
    api_key = os.getenv("SENTINEL_EMBEDDING_API_KEY", "").strip()
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required when SENTINEL_EMBEDDING_PROVIDER=gemini")

    return EmbeddingSettings(
        provider=provider,
        model=model,
        api_key=api_key,
        dimensions=dimensions,
        timeout=timeout,
    )


def build_embedding_adapter() -> EmbeddingPort | None:
    """Build the embedding adapter, or None when RAG is disabled."""
    settings = _load_embedding_settings()
    if settings.provider == "disabled":
        return None
    return GeminiEmbeddingAdapter(
        api_key=settings.api_key,
        model=settings.model,
        dimensions=settings.dimensions,
        timeout=settings.timeout,
    )


def load_database_url() -> str:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required for PostgreSQL persistence")
    return database_url


def build_repository() -> IncidentRepositoryPort:
    """Select in-memory or Neon/pgvector persistence from the environment."""
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        return InMemoryRepository()

    embedder = build_embedding_adapter()
    if embedder is None:
        raise RuntimeError(
            "SENTINEL_EMBEDDING_PROVIDER must be gemini when DATABASE_URL is configured"
        )
    return PostgresIncidentRepository(database_url, embedder)


def _load_queue_settings() -> QueueSettings:
    provider = os.getenv("SENTINEL_QUEUE_PROVIDER", "inline").strip().lower()
    if provider in {"", "inline", "memory", "local"}:
        return QueueSettings(
            provider="inline",
            token=os.getenv("QSTASH_TOKEN", ""),
            destination_url="",
            current_signing_key="",
            next_signing_key="",
            base_url=None,
        )
    if provider != "qstash":
        raise ValueError(f"Unsupported SENTINEL_QUEUE_PROVIDER: {provider}")

    token = os.getenv("QSTASH_TOKEN", "").strip()
    destination_url = os.getenv("SENTINEL_OTEL_WORKER_URL", "").strip()
    current_signing_key = os.getenv("QSTASH_CURRENT_SIGNING_KEY", "").strip()
    next_signing_key = os.getenv("QSTASH_NEXT_SIGNING_KEY", "").strip()
    missing = [
        name
        for name, value in (
            ("QSTASH_TOKEN", token),
            ("SENTINEL_OTEL_WORKER_URL", destination_url),
            ("QSTASH_CURRENT_SIGNING_KEY", current_signing_key),
            ("QSTASH_NEXT_SIGNING_KEY", next_signing_key),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"{', '.join(missing)} required when SENTINEL_QUEUE_PROVIDER=qstash")

    parsed = urlparse(destination_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("SENTINEL_OTEL_WORKER_URL must be a valid http(s) URL")

    return QueueSettings(
        provider="qstash",
        token=token,
        destination_url=destination_url,
        current_signing_key=current_signing_key,
        next_signing_key=next_signing_key,
        base_url=os.getenv("QSTASH_URL", "").strip() or None,
    )


def build_telemetry_queue(processor: Callable[[TelemetryEvent], object]) -> TelemetryQueuePort:
    """Select inline processing or Upstash QStash from the environment."""
    settings = _load_queue_settings()
    if settings.provider == "inline":
        return InlineTelemetryQueue(processor)
    return QStashTelemetryQueue(
        token=settings.token,
        destination_url=settings.destination_url,
        current_signing_key=settings.current_signing_key,
        next_signing_key=settings.next_signing_key,
        base_url=settings.base_url,
    )


def _load_notifier_settings() -> NotifierSettings:
    provider = os.getenv("SENTINEL_NOTIFIER_PROVIDER", "console").strip().lower()
    timeout = _env_float("SENTINEL_NOTIFIER_TIMEOUT", 5.0)
    max_retries = _env_int("SENTINEL_NOTIFIER_MAX_RETRIES", 2)
    backoff_seconds = _env_float("SENTINEL_NOTIFIER_BACKOFF_SECONDS", 0.5)
    if timeout <= 0:
        raise ValueError("SENTINEL_NOTIFIER_TIMEOUT must be greater than zero")
    if max_retries < 0:
        raise ValueError("SENTINEL_NOTIFIER_MAX_RETRIES cannot be negative")
    if backoff_seconds < 0:
        raise ValueError("SENTINEL_NOTIFIER_BACKOFF_SECONDS cannot be negative")

    if provider in {"", "console", "log", "none"}:
        return NotifierSettings(
            provider="console",
            webhook_url="",
            timeout=timeout,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
        )
    if provider not in {"webhook", "slack"}:
        raise ValueError(f"Unsupported SENTINEL_NOTIFIER_PROVIDER: {provider}")

    webhook_url = os.getenv("SENTINEL_NOTIFIER_WEBHOOK_URL", "").strip()
    if not webhook_url:
        raise RuntimeError(
            "SENTINEL_NOTIFIER_WEBHOOK_URL is required when "
            "SENTINEL_NOTIFIER_PROVIDER=webhook"
        )
    parsed = urlparse(webhook_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("SENTINEL_NOTIFIER_WEBHOOK_URL must be a valid http(s) URL")

    return NotifierSettings(
        provider="webhook",
        webhook_url=webhook_url,
        timeout=timeout,
        max_retries=max_retries,
        backoff_seconds=backoff_seconds,
    )


def build_notifier() -> NotifierPort:
    """Select console output or a retrying webhook notifier from the environment."""
    settings = _load_notifier_settings()
    if settings.provider == "console":
        return ConsoleNotifier()
    return WebhookNotifier(
        settings.webhook_url,
        timeout=settings.timeout,
        max_retries=settings.max_retries,
        backoff_seconds=settings.backoff_seconds,
    )


def build_event_feed() -> EventFeedPort:
    """Build the bounded in-memory feed used by the live dashboard."""
    max_events = _env_int("SENTINEL_DASHBOARD_MAX_EVENTS", 100)
    if max_events <= 0:
        raise ValueError("SENTINEL_DASHBOARD_MAX_EVENTS must be greater than zero")
    return InMemoryEventFeed(max_events=max_events)


def build_rate_limiter() -> SlidingWindowRateLimiter | None:
    """Build the ingest rate limiter, or None when it is disabled."""
    limit = _env_int("SENTINEL_RATE_LIMIT_PER_MINUTE", 120)
    if limit < 0:
        raise ValueError("SENTINEL_RATE_LIMIT_PER_MINUTE cannot be negative")
    if limit == 0:
        return None
    return SlidingWindowRateLimiter(limit=limit)


def build_observability_adapter() -> ObservabilityPort:
    """Select no-op or Langfuse tracing from the environment."""
    provider = os.getenv("SENTINEL_OBSERVABILITY_PROVIDER", "noop").strip().lower()
    if provider in {"", "noop", "disabled", "none"}:
        return NoopTracker()
    if provider != "langfuse":
        raise ValueError(f"Unsupported SENTINEL_OBSERVABILITY_PROVIDER: {provider}")

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    if not public_key or not secret_key:
        raise RuntimeError(
            "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are required when "
            "SENTINEL_OBSERVABILITY_PROVIDER=langfuse"
        )
    host = (
        os.getenv("LANGFUSE_BASE_URL", "").strip()
        or os.getenv("LANGFUSE_HOST", "").strip()
        or "https://cloud.langfuse.com"
    )
    return LangfuseTracker(public_key, secret_key, host)


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
        "repository": build_repository(),
        "notifier": build_notifier(),
        "tracker": build_observability_adapter(),
        "diagnoser": build_diagnosis_adapter(),
    }
