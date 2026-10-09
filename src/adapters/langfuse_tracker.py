from src.ports.observability import ObservabilityPort


class NoopTracker:
    """Adaptador de observabilidad NO-OP para desarrollo (ADR-0007).

    En producción se instala Langfuse y se usa LangfuseTracker:
        from langfuse.decorators import observe
    Ver https://langfuse.com/docs para configurar LANGFUSE_* (ver .env.example).
    """

    def start_trace(self, trace_id: str, event: dict) -> None:
        print(f"[Langfuse:noop] start_trace={trace_id}")

    def record_step(self, trace_id: str, node: str, payload: dict) -> None:
        print(f"[Langfuse:noop] trace={trace_id} node={node}")


class LangfuseTracker:
    """Pendiente: implementación real con el SDK de Langfuse (Fase 4)."""

    def __init__(self, public_key: str, secret_key: str, host: str) -> None:
        raise NotImplementedError(
            "Langfuse SDK integration pending. Use NoopTracker in development."
        )