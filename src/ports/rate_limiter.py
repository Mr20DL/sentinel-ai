from typing import Protocol


class RateLimiterPort(Protocol):
    """Contract for limiting requests per client key."""

    @property
    def limit(self) -> int:
        """Maximum number of requests allowed in the window."""
        ...

    def allow(self, key: str) -> bool:
        """Return True when the request for the key is allowed."""
        ...
