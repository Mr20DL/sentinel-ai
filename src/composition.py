from src.adapters.console_notifier import ConsoleNotifier
from src.adapters.in_memory_repository import InMemoryRepository
from src.adapters.langfuse_tracker import NoopTracker


def build_default_components() -> dict:
    """Composition root: adaptadores por defecto para desarrollo (hexagonal)."""
    return {
        "repository": InMemoryRepository(),
        "notifier": ConsoleNotifier(),
        "tracker": NoopTracker(),
    }