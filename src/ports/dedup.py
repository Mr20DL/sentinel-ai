from typing import Protocol


class DedupPort(Protocol):
    """Contract for short-lived duplicate suppression."""

    def allow(self, key: str, ttl_seconds: float) -> bool:
        """Return True only the first time a key is seen within the TTL."""
        ...
