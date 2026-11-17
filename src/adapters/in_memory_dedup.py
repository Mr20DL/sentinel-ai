import time
from collections import OrderedDict
from collections.abc import Callable
from threading import Lock


class InMemoryDedup:
    """Thread-safe, bounded and expiring deduplication window for one process."""

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        max_entries: int = 1000,
    ) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be greater than zero")
        self._clock = clock
        self._max_entries = max_entries
        self._seen: OrderedDict[str, float] = OrderedDict()
        self._lock = Lock()

    def allow(self, key: str, ttl_seconds: float) -> bool:
        if ttl_seconds < 0:
            raise ValueError("ttl_seconds must be non-negative")
        now = self._clock()
        with self._lock:
            while self._seen:
                _, seen_at = next(iter(self._seen.items()))
                if now - seen_at <= ttl_seconds:
                    break
                self._seen.popitem(last=False)
            if key in self._seen:
                return False
            self._seen[key] = now
            while len(self._seen) > self._max_entries:
                self._seen.popitem(last=False)
            return True

    def clear(self) -> None:
        with self._lock:
            self._seen.clear()
