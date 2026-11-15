from collections import deque
from threading import Lock

from src.domain.state import EventSnapshot, TelemetryEvent


class InMemoryEventFeed:
    """Thread-safe bounded feed of recent events for the live dashboard."""

    def __init__(self, max_events: int = 100) -> None:
        if max_events <= 0:
            raise ValueError("max_events must be greater than zero")
        self._events: deque[EventSnapshot] = deque(maxlen=max_events)
        self._lock = Lock()

    def record(self, event: TelemetryEvent, result: dict) -> None:
        snapshot = EventSnapshot.from_result(event, result)
        with self._lock:
            self._events.append(snapshot)

    def recent(self, limit: int = 50) -> list[EventSnapshot]:
        if limit <= 0:
            return []
        with self._lock:
            events = list(self._events)
        return list(reversed(events))[:limit]
