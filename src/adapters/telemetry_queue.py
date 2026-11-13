from collections.abc import Callable

from qstash import QStash, Receiver

from src.domain.state import TelemetryEvent

Processor = Callable[[TelemetryEvent], object]


class InlineTelemetryQueue:
    """Process telemetry events in the same request, useful for local development."""

    def __init__(self, processor: Processor) -> None:
        self._processor = processor

    @property
    def is_remote(self) -> bool:
        return False

    def publish(self, event: TelemetryEvent) -> None:
        self._processor(event)

    def verify_signature(self, body: bytes, signature: str) -> bool:
        return False


class QStashTelemetryQueue:
    """Publish telemetry events to Upstash QStash and verify its webhook signatures."""

    def __init__(
        self,
        token: str,
        destination_url: str,
        current_signing_key: str,
        next_signing_key: str,
        base_url: str | None = None,
        client: QStash | None = None,
        receiver: Receiver | None = None,
    ) -> None:
        self._destination_url = destination_url
        self._client = client or QStash(token, base_url=base_url)
        self._receiver = receiver or Receiver(
            current_signing_key=current_signing_key,
            next_signing_key=next_signing_key,
        )

    @property
    def is_remote(self) -> bool:
        return True

    def publish(self, event: TelemetryEvent) -> None:
        self._client.message.publish_json(
            url=self._destination_url,
            body=event.model_dump(mode="json"),
            retries=3,
            deduplication_id=f"sentinel-otel-{event.id}",
        )

    def verify_signature(self, body: bytes, signature: str) -> bool:
        try:
            self._receiver.verify(
                signature=signature,
                body=body.decode("utf-8"),
                url=self._destination_url,
                clock_tolerance=5,
            )
        except Exception:
            return False
        return True
