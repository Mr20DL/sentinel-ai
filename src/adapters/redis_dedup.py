import hashlib
import logging
import math

from src.adapters.upstash_redis import UpstashRedisClient, UpstashRedisError

logger = logging.getLogger(__name__)


class UpstashRedisDedup:
    """Distributed deduplication using Redis SET NX with a millisecond TTL."""

    def __init__(
        self,
        redis: UpstashRedisClient,
        key_prefix: str = "sentinel:dedup",
    ) -> None:
        if not key_prefix:
            raise ValueError("key_prefix cannot be empty")
        self._redis = redis
        self._key_prefix = key_prefix

    def allow(self, key: str, ttl_seconds: float) -> bool:
        if ttl_seconds < 0:
            raise ValueError("ttl_seconds must be non-negative")
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        redis_key = f"{self._key_prefix}:{digest}"
        ttl_milliseconds = max(1, math.ceil(ttl_seconds * 1000))
        try:
            result = self._redis.execute(
                "SET",
                redis_key,
                "1",
                "NX",
                "PX",
                str(ttl_milliseconds),
            )
        except UpstashRedisError:
            logger.warning("Redis deduplication unavailable; accepting event")
            return True
        return result == "OK"
