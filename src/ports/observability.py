from typing import Protocol


class ObservabilityPort(Protocol):
    """Contrato de trazabilidad distribuida del motor agéntico (Langfuse/OTel)."""

    def start_trace(self, trace_id: str, event: dict) -> None:
        """Inicia el seguimiento de una ejecución con identificador único."""
        ...

    def record_step(self, trace_id: str, node: str, payload: dict) -> None:
        """Registra el paso de un nodo del grafo dentro de la traza."""
        ...