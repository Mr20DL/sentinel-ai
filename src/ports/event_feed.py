from typing import Protocol

from src.domain.state import EventSnapshot, TelemetryEvent


class EventFeedPort(Protocol):
    """Contract for keeping the latest processed events for the dashboard."""

    def record(self, event: TelemetryEvent, result: dict) -> None:
        """Add a processed event to the feed."""
        ...

    def recent(self, limit: int = 50) -> list[EventSnapshot]:
        """Return the most recent events, newest first."""
        ...
