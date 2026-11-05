from typing import Protocol


class IncidentRepositoryPort(Protocol):
    """Contrato para recuperar antecedentes históricos de incidentes."""

    def search_incidents(
        self, service_name: str, query: str, limit: int = 5
    ) -> list[str]:
        """Devuelve incidentes pasados similares al evento y servicio dados."""
        ...