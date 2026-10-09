from typing import Protocol


class IncidentRepositoryPort(Protocol):
    """Contrato para recuperar antecedentes históricos de incidentes."""

    def search_incidents(self, service_name: str, limit: int = 5) -> list[str]:
        """Devuelve post-mortems/incidentes pasados similares para el servicio dado."""
        ...