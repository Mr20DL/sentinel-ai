from pydantic import ValidationError

from src.adapters.upstash_redis import UpstashRedisClient
from src.domain.state import EventSnapshot, TelemetryEvent

_RECORD_SCRIPT = """
local key = KEYS[1]
redis.call('LPUSH', key, ARGV[1])
redis.call('LTRIM', key, 0, tonumber(ARGV[2]) - 1)
redis.call('EXPIRE', key, tonumber(ARGV[3]))
return 1
"""


class UpstashRedisEventFeed:
    """Bounded, shared dashboard feed backed by a Redis list."""

    def __init__(
        self,
        redis: UpstashRedisClient,
        max_events: int = 100,
        key: str = "sentinel:dashboard:events",
        ttl_seconds: int = 86400,
    ) -> None:
        if max_events <= 0:
            raise ValueError("max_events must be greater than zero")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")
        if not key:
            raise ValueError("key cannot be empty")
        self._redis = redis
        self._max_events = max_events
        self._key = key
        self._ttl_seconds = ttl_seconds

    def record(self, event: TelemetryEvent, result: dict) -> None:
        snapshot = EventSnapshot.from_result(event, result)
        self._redis.execute(
            "EVAL",
            _RECORD_SCRIPT,
            1,
            self._key,
            snapshot.model_dump_json(),
            str(self._max_events),
            str(self._ttl_seconds),
        )

    def recent(self, limit: int = 50) -> list[EventSnapshot]:
        if limit <= 0:
            return []
        safe_limit = min(limit, self._max_events)
        raw_events = self._redis.execute("LRANGE", self._key, 0, safe_limit - 1)
        if not isinstance(raw_events, list):
            return []

        snapshots: list[EventSnapshot] = []
        for raw_event in raw_events:
            if not isinstance(raw_event, str):
                continue
            try:
                snapshots.append(EventSnapshot.model_validate_json(raw_event))
            except ValidationError:
                continue
        return snapshots
