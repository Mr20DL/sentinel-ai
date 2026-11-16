import time
from collections.abc import Callable

import httpx

from src.ports.notifier import NotifierPort

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class NotificationError(RuntimeError):
    """Raised when a webhook notification cannot be delivered."""


class WebhookNotifier(NotifierPort):
    """Send incident notifications to a Slack-compatible webhook with retries."""

    def __init__(
        self,
        url: str,
        *,
        timeout: float = 5.0,
        max_retries: int = 2,
        backoff_seconds: float = 0.5,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._url = url
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._client = client
        self._sleep = sleep

    def send(self, channel: str, message: str) -> None:
        payload = {"text": f"[{channel}] {message}"}
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                response = self._post(payload)
                if 200 <= response.status_code < 300:
                    return
                error = NotificationError(
                    f"Webhook returned HTTP {response.status_code}"
                )
                if response.status_code not in _RETRYABLE_STATUS_CODES:
                    raise error
                last_error = error
            except httpx.HTTPError as exc:
                last_error = exc

            if attempt < self._max_retries:
                self._sleep(self._backoff_seconds * (2**attempt))

        raise NotificationError(
            f"Webhook notification failed: {type(last_error).__name__}: {last_error}"
        )

    def _post(self, payload: dict[str, str]) -> httpx.Response:
        if self._client is not None:
            return self._client.post(self._url, json=payload, timeout=self._timeout)
        return httpx.post(self._url, json=payload, timeout=self._timeout)
