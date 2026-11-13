from typing import Protocol

from src.domain.state import TelemetryEvent


class TelemetryQueuePort(Protocol):
    """Contrato para desacoplar la ingesta OTLP del procesamiento de incidentes."""

    @property
    def is_remote(self) -> bool:
        """Indica si la cola entrega eventos mediante un webhook remoto."""
        ...

    def publish(self, event: TelemetryEvent) -> None:
        """Encola un evento normalizado para su procesamiento."""
        ...

    def verify_signature(self, body: bytes, signature: str) -> bool:
        """Valida la firma de una entrega remota."""
        ...
