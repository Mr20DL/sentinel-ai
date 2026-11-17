import logging
import os
import secrets
import uuid
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import ValidationError

from src.adapters.dashboard_page import DASHBOARD_HTML
from src.adapters.otel_ingestion import OtelLogNormalizer
from src.composition import (
    build_dedup_store,
    build_event_feed,
    build_rate_limiter,
    build_telemetry_queue,
)
from src.domain.graph import create_sentinel_graph
from src.domain.state import TelemetryEvent

logger = logging.getLogger(__name__)

app = FastAPI(
    title="SentinelAI",
    version="0.1.0",
    description="Plataforma de observabilidad autónoma (motor agéntico LangGraph).",
)

engine = create_sentinel_graph()
event_feed = build_event_feed()
dashboard_security = HTTPBasic(auto_error=False)


def _build_thread_id(event: TelemetryEvent) -> str:
    return f"event-{event.id}-{uuid.uuid4().hex}"


def _process_event(event: TelemetryEvent) -> dict:
    result = engine.invoke(
        {"raw_event": event, "audit_logs": []},
        config={"configurable": {"thread_id": _build_thread_id(event)}},
    )
    try:
        event_feed.record(event, result)
    except Exception:
        logger.exception("Failed to record event in the dashboard feed")
    return result


telemetry_queue = build_telemetry_queue(_process_event)
rate_limiter = build_rate_limiter()


def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, "").strip())
    except ValueError:
        return default
    return value if value > 0 else default


def _non_negative_float_env(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, "").strip())
    except ValueError:
        return default
    return value if value >= 0 else default


otel_normalizer = OtelLogNormalizer(
    dedup_ttl=_non_negative_float_env("SENTINEL_OTEL_DEDUP_TTL", 60.0),
    dedup_store=build_dedup_store(),
)


def _verify_ingest_key(
    x_ingest_key: str | None = Header(default=None, alias="X-Ingest-Key"),
) -> None:
    expected = os.getenv("SENTINEL_INGEST_API_KEY", "").strip()
    if expected and not secrets.compare_digest(x_ingest_key or "", expected):
        raise HTTPException(status_code=401, detail="Invalid ingest key")


def _verify_dashboard_auth(
    credentials: Annotated[
        HTTPBasicCredentials | None, Depends(dashboard_security)
    ] = None,
) -> None:
    username = os.getenv("SENTINEL_DASHBOARD_USER", "").strip()
    password = os.getenv("SENTINEL_DASHBOARD_PASSWORD", "").strip()
    if not username and not password:
        return
    if not username or not password:
        raise HTTPException(status_code=503, detail="Dashboard auth is misconfigured")

    valid = (
        credentials is not None
        and secrets.compare_digest(
            credentials.username.encode("utf-8"), username.encode("utf-8")
        )
        and secrets.compare_digest(
            credentials.password.encode("utf-8"), password.encode("utf-8")
        )
    )
    if not valid:
        raise HTTPException(
            status_code=401,
            detail="Invalid dashboard credentials",
            headers={"WWW-Authenticate": 'Basic realm="SentinelAI"'},
        )


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _enforce_rate_limit(request: Request) -> None:
    if rate_limiter is None:
        return
    try:
        allowed = rate_limiter.allow(_client_key(request))
    except Exception:
        logger.exception("Rate limiter unavailable; allowing request")
        return
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"},
        )


@app.get("/")
def root() -> dict:
    return {
        "service": "sentinel-ai",
        "version": "0.1.0",
        "health": "/health",
        "events": "/events",
        "otel_logs": "/ingest/otel/v1/logs",
        "otel_worker": "/internal/otel/process",
        "dashboard": "/dashboard",
        "dashboard_events": "/dashboard/events",
        "docs": "/docs",
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "sentinel-ai"}


@app.get(
    "/dashboard",
    response_class=HTMLResponse,
    dependencies=[Depends(_verify_dashboard_auth)],
)
def dashboard() -> HTMLResponse:
    return HTMLResponse(DASHBOARD_HTML)


@app.get("/dashboard/events", dependencies=[Depends(_verify_dashboard_auth)])
def dashboard_events(limit: int = 50) -> JSONResponse:
    safe_limit = max(1, min(limit, 200))
    snapshots = event_feed.recent(safe_limit)
    return JSONResponse({"events": [snapshot.model_dump(mode="json") for snapshot in snapshots]})


@app.post(
    "/events",
    dependencies=[Depends(_verify_ingest_key), Depends(_enforce_rate_limit)],
)
def ingest_event(event: TelemetryEvent) -> JSONResponse:
    result = _process_event(event)
    anomaly_output = result.get("anomaly_output")
    diagnosis = result.get("diagnosis")
    return JSONResponse(
        {
            "trace_id": result.get("trace_id"),
            "sanitization_ok": result.get("sanitization_ok"),
            "is_anomaly": result.get("is_anomaly"),
            "anomaly_score": result.get("anomaly_score"),
            "anomaly_output": anomaly_output.model_dump() if anomaly_output else None,
            "historical_context": result.get("historical_context", []),
            "diagnosis": diagnosis.model_dump() if diagnosis else None,
            "notification_sent": result.get("notification_sent"),
            "audit_logs": result.get("audit_logs", []),
        }
    )


@app.post(
    "/ingest/otel/v1/logs",
    dependencies=[Depends(_verify_ingest_key), Depends(_enforce_rate_limit)],
)
def ingest_otel_logs(payload: dict) -> JSONResponse:
    max_events = _positive_int_env("SENTINEL_OTEL_MAX_EVENTS", 3)
    events = otel_normalizer.normalize(payload, max_events=max_events)
    queued = 0
    failed = 0
    for event in events:
        try:
            telemetry_queue.publish(event)
            queued += 1
        except Exception:
            failed += 1
    return JSONResponse({"accepted": len(events), "queued": queued, "failed": failed})


@app.post("/internal/otel/process")
async def process_otel_event(
    request: Request,
    upstash_signature: str | None = Header(default=None, alias="Upstash-Signature"),
) -> JSONResponse:
    if not telemetry_queue.is_remote:
        raise HTTPException(status_code=404, detail="Worker endpoint is disabled")
    body = await request.body()
    if not upstash_signature or not telemetry_queue.verify_signature(body, upstash_signature):
        raise HTTPException(status_code=401, detail="Invalid QStash signature")
    try:
        event = TelemetryEvent.model_validate_json(body)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail="Invalid telemetry event") from exc
    try:
        result = await run_in_threadpool(_process_event, event)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Event processing failed") from exc
    return JSONResponse({"processed": 1, "is_anomaly": bool(result.get("is_anomaly"))})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.adapters.fastapi_app:app", host="127.0.0.1", port=8000, reload=True)
