from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from src.domain.state import TelemetryEvent, TelemetryMetrics

_CRITICAL_LEVELS = {"ERROR", "CRITICAL", "FATAL"}
_SEVERITY_ALIASES = {
    "ERR": "ERROR",
    "CRIT": "CRITICAL",
    "WARNING": "WARN",
}
_SEVERITY_NAMES = ("TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL")


class OtelLogNormalizer:
    """Convert OTLP log records into the canonical TelemetryEvent contract."""

    def __init__(
        self,
        dedup_ttl: float = 60.0,
        max_message_length: int = 4000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if dedup_ttl < 0:
            raise ValueError("dedup_ttl must be non-negative")
        if max_message_length <= 0:
            raise ValueError("max_message_length must be greater than zero")
        self._dedup_ttl = dedup_ttl
        self._max_message_length = max_message_length
        self._clock = clock
        self._seen: OrderedDict[str, float] = OrderedDict()

    def clear(self) -> None:
        """Clear the in-memory deduplication window."""
        self._seen.clear()

    def normalize(self, payload: object, max_events: int = 3) -> list[TelemetryEvent]:
        """Return a bounded list of critical events from an OTLP logs payload."""
        if max_events <= 0:
            return []

        candidates = [
            event
            for resource, record in self._iter_records(payload)
            if (event := self._to_event(resource, record)) is not None
        ]
        candidates.sort(
            key=lambda event: (_severity_rank(event.log_level), event.timestamp),
            reverse=True,
        )

        selected: list[TelemetryEvent] = []
        for event in candidates:
            if not self._allow(event):
                continue
            selected.append(event)
            if len(selected) >= max_events:
                break
        return selected

    def _iter_records(
        self, payload: object
    ) -> Iterable[tuple[Mapping[str, Any], Mapping[str, Any]]]:
        if not isinstance(payload, dict):
            return
        resource_logs = payload.get("resourceLogs")
        if not isinstance(resource_logs, list):
            return

        for resource_log in resource_logs:
            if not isinstance(resource_log, dict):
                continue
            resource = resource_log.get("resource")
            resource_attributes = self._attributes(
                resource.get("attributes") if isinstance(resource, dict) else None
            )
            scope_logs = resource_log.get("scopeLogs")
            if not isinstance(scope_logs, list):
                continue
            for scope_log in scope_logs:
                if not isinstance(scope_log, dict):
                    continue
                records = scope_log.get("logRecords")
                if not isinstance(records, list):
                    continue
                for record in records:
                    if isinstance(record, dict):
                        yield resource_attributes, record

    def _to_event(
        self, resource: Mapping[str, Any], record: Mapping[str, Any]
    ) -> TelemetryEvent | None:
        service_name = self._text(resource.get("service.name"))
        if not service_name:
            return None

        log_level = self._severity(record)
        if log_level not in _CRITICAL_LEVELS:
            return None

        attributes = self._attributes(record.get("attributes"))
        message = self._message(record, attributes)
        if not message:
            return None
        message = message[: self._max_message_length]

        timestamp = self._timestamp(record)
        environment = (
            self._text(resource.get("deployment.environment.name"))
            or self._text(resource.get("deployment.environment"))
            or "production"
        )
        return TelemetryEvent(
            id=self._event_id(record, service_name, timestamp, message),
            service_name=service_name,
            environment=environment,
            timestamp=timestamp,
            log_level=log_level,
            message=message,
            metrics=self._metrics(attributes),
        )

    def _allow(self, event: TelemetryEvent) -> bool:
        now = self._clock()
        while self._seen:
            _, seen_at = next(iter(self._seen.items()))
            if now - seen_at <= self._dedup_ttl:
                break
            self._seen.popitem(last=False)

        key = (
            f"{event.environment}|{event.service_name}|{event.log_level}|"
            f"{event.timestamp.strftime('%Y%m%d%H%M')}|{event.message[:200]}"
        )
        if key in self._seen:
            return False
        self._seen[key] = now
        while len(self._seen) > 1000:
            self._seen.popitem(last=False)
        return True

    def _severity(self, record: Mapping[str, Any]) -> str:
        text = self._text(record.get("severityText")).upper()
        if text:
            return _SEVERITY_ALIASES.get(text, text)
        number = self._integer(record.get("severityNumber"))
        if number is None or number <= 0:
            return "INFO"
        index = min((number - 1) // 4, len(_SEVERITY_NAMES) - 1)
        return _SEVERITY_NAMES[index]

    def _timestamp(self, record: Mapping[str, Any]) -> datetime:
        for field in ("timeUnixNano", "observedTimeUnixNano"):
            nanoseconds = self._integer(record.get(field))
            if nanoseconds and nanoseconds > 0:
                seconds, remainder = divmod(nanoseconds, 1_000_000_000)
                return datetime.fromtimestamp(seconds, tz=UTC) + timedelta(
                    microseconds=remainder // 1000
                )
        return datetime.now(UTC)

    def _message(self, record: Mapping[str, Any], attributes: Mapping[str, Any]) -> str:
        body = self._body(record.get("body"))
        if body:
            return body
        return self._text(attributes.get("log.message"))

    def _body(self, body: object) -> str:
        if isinstance(body, str):
            return body.strip()
        if not isinstance(body, dict):
            return ""
        if "stringValue" in body:
            return self._text(body["stringValue"])
        if "kvlistValue" in body:
            return json.dumps(body["kvlistValue"], separators=(",", ":"), default=str)
        if "arrayValue" in body:
            return json.dumps(body["arrayValue"], separators=(",", ":"), default=str)
        return json.dumps(body, separators=(",", ":"), default=str)

    def _metrics(self, attributes: Mapping[str, Any]) -> TelemetryMetrics:
        cpu = attributes.get("cpu")
        if cpu is None:
            cpu = attributes.get("cpu.utilization")
        error_rate = attributes.get("error_rate")
        if error_rate is None:
            error_rate = attributes.get("error.rate")
        return TelemetryMetrics(cpu=cpu, error_rate=error_rate)

    def _event_id(
        self,
        record: Mapping[str, Any],
        service_name: str,
        timestamp: datetime,
        message: str,
    ) -> int:
        seed = "|".join(
            (
                self._text(record.get("traceId")),
                self._text(record.get("spanId")),
                service_name,
                timestamp.isoformat(),
                message,
            )
        )
        return int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:15], 16)

    def _attributes(self, attributes: object) -> dict[str, Any]:
        if not isinstance(attributes, list):
            return {}
        result: dict[str, Any] = {}
        for attribute in attributes:
            if not isinstance(attribute, dict):
                continue
            key = attribute.get("key")
            if isinstance(key, str):
                result[key] = self._attribute_value(attribute.get("value"))
        return result

    def _attribute_value(self, value: object) -> Any:
        if not isinstance(value, dict):
            return None
        if "stringValue" in value:
            return value["stringValue"]
        if "intValue" in value:
            return self._integer(value["intValue"])
        if "doubleValue" in value:
            try:
                return float(value["doubleValue"])
            except (TypeError, ValueError):
                return None
        if "boolValue" in value:
            return value["boolValue"]
        if "arrayValue" in value:
            return value["arrayValue"]
        if "kvlistValue" in value:
            return value["kvlistValue"]
        return None

    def _integer(self, value: object) -> int | None:
        try:
            return int(value)  # type: ignore[call-overload]
        except (TypeError, ValueError):
            return None

    def _text(self, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()


def _severity_rank(log_level: str) -> int:
    return {"FATAL": 3, "CRITICAL": 2, "ERROR": 1}.get(log_level.upper(), 0)
