from urllib.parse import urlparse

import httpx


class UpstashRedisError(RuntimeError):
    """Raised when an Upstash Redis REST command cannot be completed."""


class UpstashRedisClient:
    """Small Upstash Redis REST client that sends commands as JSON arrays."""

    def __init__(
        self,
        url: str,
        token: str,
        timeout: float = 5.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Upstash Redis URL must be a valid http(s) URL")
        if not token.strip():
            raise ValueError("Upstash Redis token is required")
        if timeout <= 0:
            raise ValueError("Upstash Redis timeout must be greater than zero")
        self._url = url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._http_client = http_client

    def execute(self, *command: object) -> object:
        """Execute a Redis command through the REST API."""
        response = self._post(list(command))
        try:
            payload = response.json()
        except ValueError as exc:
            raise UpstashRedisError("Upstash Redis returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise UpstashRedisError("Upstash Redis returned an invalid response")
        if payload.get("error"):
            raise UpstashRedisError(str(payload["error"]))
        return payload.get("result")

    def _post(self, command: list[object]) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        try:
            if self._http_client is not None:
                response = self._http_client.post(
                    self._url,
                    json=command,
                    headers=headers,
                    timeout=self._timeout,
                )
            else:
                response = httpx.post(
                    self._url,
                    json=command,
                    headers=headers,
                    timeout=self._timeout,
                )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise UpstashRedisError("Upstash Redis request failed") from exc
        return response
