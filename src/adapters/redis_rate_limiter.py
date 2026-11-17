import time
import uuid
from collections.abc import Callable

from src.adapters.upstash_redis import UpstashRedisClient

_RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
local count = redis.call('ZCARD', key)
if count >= limit then
    return 0
end
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, math.ceil(window))
return 1
"""


class UpstashRedisRateLimiter:
    """Distributed sliding-window limiter backed by an atomic Redis script."""

    def __init__(
        self,
        redis: UpstashRedisClient,
        limit: int,
        window_seconds: float = 60.0,
        key_prefix: str = "sentinel:rate",
        clock: Callable[[], float] = time.time,
    ) -> None:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than zero")
        if not key_prefix:
            raise ValueError("key_prefix cannot be empty")
        self._redis = redis
        self._limit = limit
        self._window_seconds = window_seconds
        self._key_prefix = key_prefix
        self._clock = clock

    @property
    def limit(self) -> int:
        return self._limit

    def allow(self, key: str) -> bool:
        now = self._clock()
        member = f"{now:.6f}:{uuid.uuid4().hex}"
        result = self._redis.execute(
            "EVAL",
            _RATE_LIMIT_SCRIPT,
            1,
            f"{self._key_prefix}:{key}",
            f"{now:.6f}",
            str(self._window_seconds),
            str(self._limit),
            member,
        )
        return bool(result)
