from typing import Protocol

from src.domain.state import AnomalyAnalysisOutput, RootCauseReport, TelemetryEvent


class DiagnosisPort(Protocol):
    """Contrato para generar un diagnóstico estructurado a partir del incidente."""

    def generate(
        self,
        event: TelemetryEvent,
        analysis: AnomalyAnalysisOutput,
        historical_context: list[str],
    ) -> RootCauseReport:
        """Devuelve causa raíz, severidad, acción y runbook para el incidente."""
        ...
