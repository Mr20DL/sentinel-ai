import os

from src.adapters.console_notifier import ConsoleNotifier
from src.adapters.heuristic_diagnoser import HeuristicDiagnoser
from src.adapters.in_memory_repository import InMemoryRepository
from src.adapters.langfuse_tracker import NoopTracker
from src.ports.diagnosis import DiagnosisPort


def build_diagnosis_adapter() -> DiagnosisPort:
    """Select the diagnosis provider from the environment (composition root)."""
    provider = os.getenv("SENTINEL_LLM_PROVIDER", "heuristic").strip().lower()
    if provider in {"", "heuristic", "mock"}:
        return HeuristicDiagnoser()
    if provider not in {"openai", "ollama"}:
        raise ValueError(f"Unsupported SENTINEL_LLM_PROVIDER: {provider}")

    default_model = "llama3.1" if provider == "ollama" else "gpt-4o-mini"
    model = os.getenv("SENTINEL_LLM_MODEL") or default_model
    api_key: str
    base_url: str | None
    if provider == "ollama":
        api_key = os.getenv("OLLAMA_API_KEY") or "ollama-local"
        base_url = os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434/v1"
    else:
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            raise RuntimeError(
                "OPENAI_API_KEY is required when SENTINEL_LLM_PROVIDER=openai"
            )
        api_key = openai_key
        base_url = os.getenv("OPENAI_BASE_URL") or None

    from src.adapters.langchain_diagnoser import build_openai_diagnoser

    return build_openai_diagnoser(model=model, api_key=api_key, base_url=base_url)


def build_default_components() -> dict:
    """Composition root: adaptadores por defecto para desarrollo (hexagonal)."""
    return {
        "repository": InMemoryRepository(),
        "notifier": ConsoleNotifier(),
        "tracker": NoopTracker(),
        "diagnoser": build_diagnosis_adapter(),
    }
