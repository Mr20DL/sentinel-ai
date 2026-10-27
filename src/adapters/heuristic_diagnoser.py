from src.domain.diagnosis import build_heuristic_report
from src.domain.state import AnomalyAnalysisOutput, RootCauseReport, TelemetryEvent


class HeuristicDiagnoser:
    """Offline diagnosis provider used in development and as a safe fallback."""

    def generate(
        self,
        event: TelemetryEvent,
        analysis: AnomalyAnalysisOutput,
        _historical_context: list[str],
    ) -> RootCauseReport:
        return build_heuristic_report(event, analysis)
