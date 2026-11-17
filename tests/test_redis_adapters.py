import hashlib
import json
from datetime import UTC, datetime

import httpx
import pytest
from fastapi import Request

from src.adapters import fastapi_app
from src.adapters.in_memory_dedup import InMemoryDedup
from src.adapters.redis_dedup import UpstashRedisDedup
from src.adapters.redis_event_feed import UpstashRedisEventFeed
from src.adapters.redis_rate_limiter import UpstashRedisRateLimiter
from src.adapters.upstash_redis import UpstashRedisClient, UpstashRedisError
from src.domain.state import AnomalyAnalysisOutput, RootCauseReport, TelemetryEvent


class _FakeRedis:
    def __init__(self, results: list[object] | None = None, error: Exception | None = None) -> None:
        self.commands: list[tuple[object, ...]] = []
        self._results = results or []
        self._error = error

    def execute(self, *command: object) -> object:
        self.commands.append(command)
        if self._error is not None:
            raise self._error
        return self._results.pop(0) if self._results else None


class _FakeClock:
    def __init__(self, now: float = 100.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def _event(event_id: int = 1) -> TelemetryEvent:
    return TelemetryEvent(
        id=event_id,
        service_name="payment-service",
        environment="production",
        timestamp=datetime(2026, 11, 16, 12, 0, tzinfo=UTC),
        log_level="CRITICAL",
        message="Payment gateway unavailable",
    )


def _anomaly_result(event: TelemetryEvent) -> dict:
    return {
        "raw_event": event,
        "trace_id": "trace-redis",
        "sanitization_ok": True,
        "is_anomaly": True,
        "anomaly_score": 0.91,
        "anomaly_output": AnomalyAnalysisOutput(
            is_anomaly=True,
            anomaly_score=0.91,
            severity="critical",
            reasoning="High error rate",
        ),
        "diagnosis": RootCauseReport(
            root_cause="Payment gateway timeout",
            severity="critical",
            recommended_action="Rollback the last deployment",
            runbook_steps=["Check gateway health"],
        ),
    }


def _client(handler) -> UpstashRedisClient:
    return UpstashRedisClient(
        "https://redis.example",
        "test-token",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_redis_client_sends_authenticated_json_command():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"result": "PONG"})

    client = _client(handler)

    assert client.execute("PING") == "PONG"
    assert captured[0].headers["authorization"] == "Bearer test-token"
    assert json.loads(captured[0].content) == ["PING"]


def test_redis_client_rejects_invalid_configuration():
    with pytest.raises(ValueError, match="valid http"):
        UpstashRedisClient("not-a-url", "token")
    with pytest.raises(ValueError, match="token"):
        UpstashRedisClient("https://redis.example", " ")
    with pytest.raises(ValueError, match="timeout"):
        UpstashRedisClient("https://redis.example", "token", timeout=0)


def test_redis_client_raises_on_error_payload():
    client = _client(lambda request: httpx.Response(200, json={"error": "ERR broken"}))
    invalid_response = _client(lambda request: httpx.Response(200, json=["unexpected"]))

    with pytest.raises(UpstashRedisError, match="ERR broken"):
        client.execute("PING")
    with pytest.raises(UpstashRedisError, match="invalid response"):
        invalid_response.execute("PING")


def test_redis_client_uses_httpx_post_without_injected_client(monkeypatch):
    captured: dict[str, object] = {}

    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        captured["url"] = url
        captured.update(kwargs)
        return httpx.Response(
            200,
            json={"result": "PONG"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("src.adapters.upstash_redis.httpx.post", fake_post)
    client = UpstashRedisClient("https://redis.example", "token")

    assert client.execute("PING") == "PONG"
    assert captured["url"] == "https://redis.example"
    assert captured["json"] == ["PING"]


def test_redis_client_raises_on_invalid_json_and_http_error():
    invalid_json = _client(lambda request: httpx.Response(200, text="not-json"))
    http_error = _client(lambda request: httpx.Response(500, text="boom"))

    with pytest.raises(UpstashRedisError, match="invalid JSON"):
        invalid_json.execute("PING")
    with pytest.raises(UpstashRedisError, match="request failed"):
        http_error.execute("PING")


def test_redis_rate_limiter_uses_atomic_sliding_window():
    redis = _FakeRedis(results=[1, 0])
    limiter = UpstashRedisRateLimiter(
        redis,
        limit=2,
        window_seconds=60,
        clock=_FakeClock(100.0),
    )

    assert limiter.limit == 2
    assert limiter.allow("client-a") is True
    assert limiter.allow("client-a") is False

    command = redis.commands[0]
    assert command[0] == "EVAL"
    assert command[2] == 1
    assert command[3] == "sentinel:rate:client-a"
    assert command[4] == "100.000000"
    assert command[5] == "60"
    assert command[6] == "2"
    assert str(command[7]).startswith("100.000000:")


@pytest.mark.parametrize(
    ("limit", "window_seconds", "key_prefix"),
    [(0, 60, "prefix"), (-1, 60, "prefix"), (1, 0, "prefix"), (1, -1, "prefix"), (1, 60, "")],
)
def test_redis_rate_limiter_rejects_invalid_settings(
    limit: int, window_seconds: float, key_prefix: str
):
    with pytest.raises(ValueError):
        UpstashRedisRateLimiter(
            _FakeRedis(),
            limit=limit,
            window_seconds=window_seconds,
            key_prefix=key_prefix,
        )


def test_redis_event_feed_records_and_reads_snapshots():
    event = _event()
    result = _anomaly_result(event)
    record_redis = _FakeRedis(results=[1])
    feed = UpstashRedisEventFeed(record_redis, max_events=5, ttl_seconds=60)

    feed.record(event, result)

    record_command = record_redis.commands[0]
    assert record_command[0] == "EVAL"
    assert record_command[2] == 1
    assert record_command[3] == "sentinel:dashboard:events"
    assert record_command[5] == "5"
    assert record_command[6] == "60"

    stored = json.loads(str(record_command[4]))
    assert stored["event_id"] == 1
    assert stored["root_cause"] == "Payment gateway timeout"

    read_redis = _FakeRedis(results=[[json.dumps(stored), "not-json", 3]])
    read_feed = UpstashRedisEventFeed(read_redis, max_events=5)
    snapshots = read_feed.recent(2)

    assert len(snapshots) == 1
    assert snapshots[0].event_id == 1
    assert read_redis.commands[0][0] == "LRANGE"


def test_redis_event_feed_handles_empty_and_invalid_limits():
    feed = UpstashRedisEventFeed(_FakeRedis(results=[None]))

    assert feed.recent(0) == []
    assert feed.recent(10) == []

    with pytest.raises(ValueError, match="max_events"):
        UpstashRedisEventFeed(_FakeRedis(), max_events=0)
    with pytest.raises(ValueError, match="ttl_seconds"):
        UpstashRedisEventFeed(_FakeRedis(), ttl_seconds=0)
    with pytest.raises(ValueError, match="key"):
        UpstashRedisEventFeed(_FakeRedis(), key="")


def test_redis_dedup_uses_hashed_set_nx():
    redis = _FakeRedis(results=["OK", None])
    dedup = UpstashRedisDedup(redis)
    key = "production|payment|CRITICAL|message"

    assert dedup.allow(key, 60) is True
    assert dedup.allow(key, 60) is False

    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    assert redis.commands[0] == (
        "SET",
        f"sentinel:dedup:{digest}",
        "1",
        "NX",
        "PX",
        "60000",
    )


def test_redis_dedup_fails_open_and_validates_ttl():
    dedup = UpstashRedisDedup(_FakeRedis(error=UpstashRedisError("down")))

    assert dedup.allow("event", 60) is True
    with pytest.raises(ValueError, match="ttl_seconds"):
        dedup.allow("event", -1)
    with pytest.raises(ValueError, match="key_prefix"):
        UpstashRedisDedup(_FakeRedis(), key_prefix="")


def test_in_memory_dedup_expires_and_clears():
    clock = _FakeClock()
    dedup = InMemoryDedup(clock=clock, max_entries=2)

    assert dedup.allow("a", 10) is True
    assert dedup.allow("a", 10) is False

    clock.now = 111.0
    assert dedup.allow("a", 10) is True

    assert dedup.allow("b", 10) is True
    assert dedup.allow("c", 10) is True
    assert dedup.allow("b", 10) is False
    assert dedup.allow("a", 10) is True

    dedup.clear()
    assert dedup.allow("a", 10) is True

    with pytest.raises(ValueError, match="max_entries"):
        InMemoryDedup(max_entries=0)
    with pytest.raises(ValueError, match="ttl_seconds"):
        dedup.allow("d", -1)


def test_rate_limiter_outage_fails_open(monkeypatch, caplog):
    class _BrokenLimiter:
        limit = 1

        def allow(self, key: str) -> bool:
            raise UpstashRedisError("down")

    monkeypatch.setattr(fastapi_app, "rate_limiter", _BrokenLimiter())
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/events",
            "headers": [],
            "client": ("127.0.0.1", 1234),
        }
    )

    fastapi_app._enforce_rate_limit(request)

    assert "Rate limiter unavailable" in caplog.text


def test_feed_outage_does_not_abort_processing(monkeypatch, caplog):
    event = _event()

    class _BrokenFeed:
        def record(self, event: TelemetryEvent, result: dict) -> None:
            raise UpstashRedisError("down")

    class _Engine:
        def invoke(self, *args: object, **kwargs: object) -> dict:
            return {"is_anomaly": False}

    monkeypatch.setattr(fastapi_app, "engine", _Engine())
    monkeypatch.setattr(fastapi_app, "event_feed", _BrokenFeed())

    result = fastapi_app._process_event(event)

    assert result["is_anomaly"] is False
    assert "Failed to record event" in caplog.text
