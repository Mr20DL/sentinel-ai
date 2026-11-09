import logging

from langfuse import Langfuse, LangfuseSpan

_logger = logging.getLogger(__name__)


class NoopTracker:
    """Adaptador de observabilidad NO-OP para desarrollo (ADR-0007)."""

    def start_trace(self, trace_id: str, event: dict) -> None:
        print(f"[Langfuse:noop] start_trace={trace_id}")

    def record_step(self, trace_id: str, node: str, payload: dict) -> None:
        print(f"[Langfuse:noop] trace={trace_id} node={node}")

    def finish_trace(self, trace_id: str) -> None:
        print(f"[Langfuse:noop] finish_trace={trace_id}")


class LangfuseTracker:
    """Adaptador Langfuse v5 con degradacion controlada ante fallos del SDK."""

    def __init__(
        self,
        public_key: str,
        secret_key: str,
        host: str,
        *,
        client: Langfuse | None = None,
    ) -> None:
        self._client = client or Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            base_url=host or None,
        )
        self._roots: dict[str, LangfuseSpan] = {}
        self._degraded = False

    def start_trace(self, trace_id: str, event: dict) -> None:
        if self._degraded:
            return
        try:
            root = self._client.start_observation(
                trace_context={"trace_id": self._client.create_trace_id(seed=trace_id)},
                name="sentinel.incident",
                as_type="span",
                input=event,
                metadata={
                    "trace_id": trace_id,
                    "service_name": event.get("service_name"),
                    "environment": event.get("environment"),
                },
            )
            self._roots[trace_id] = root
        except Exception as exc:
            self._degrade(exc)

    def record_step(self, trace_id: str, node: str, payload: dict) -> None:
        if self._degraded:
            return
        root = self._roots.get(trace_id)
        if root is None:
            return
        try:
            step = root.start_observation(
                name=f"sentinel.node.{node}",
                as_type="span",
                output=payload.get("audit", payload),
                metadata={"trace_id": trace_id, "node": node},
            )
            step.end()
        except Exception as exc:
            self._degrade(exc)

    def finish_trace(self, trace_id: str) -> None:
        if self._degraded:
            return
        root = self._roots.pop(trace_id, None)
        if root is None:
            return
        try:
            root.end()
        except Exception as exc:
            self._degrade(exc)

    def _degrade(self, exc: Exception) -> None:
        self._degraded = True
        _logger.warning(
            "Langfuse tracking disabled after %s; incident processing continues.",
            type(exc).__name__,
        )
        for root in self._roots.values():
            try:
                root.end()
            except Exception:
                _logger.debug("Failed to close a Langfuse root span.", exc_info=True)
        self._roots.clear()
