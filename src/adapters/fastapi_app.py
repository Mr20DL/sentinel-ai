import os
import secrets
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.adapters.otel_ingestion import OtelLogNormalizer
from src.composition import build_telemetry_queue
from src.domain.graph import create_sentinel_graph
from src.domain.state import TelemetryEvent

app = FastAPI(
    title="SentinelAI",
    version="0.1.0",
    description="Plataforma de observabilidad autónoma (motor agéntico LangGraph).",
)

engine = create_sentinel_graph()


def _build_thread_id(event: TelemetryEvent) -> str:
    return f"event-{event.id}-{uuid.uuid4().hex}"


def _process_event(event: TelemetryEvent) -> dict:
    return engine.invoke(
        {"raw_event": event, "audit_logs": []},
        config={"configurable": {"thread_id": _build_thread_id(event)}},
    )


telemetry_queue = build_telemetry_queue(_process_event)


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
    dedup_ttl=_non_negative_float_env("SENTINEL_OTEL_DEDUP_TTL", 60.0)
)


def _verify_ingest_key(
    x_ingest_key: str | None = Header(default=None, alias="X-Ingest-Key"),
) -> None:
    expected = os.getenv("SENTINEL_INGEST_API_KEY", "").strip()
    if expected and not secrets.compare_digest(x_ingest_key or "", expected):
        raise HTTPException(status_code=401, detail="Invalid ingest key")


@app.get("/")
def root() -> dict:
    return {
        "service": "sentinel-ai",
        "version": "0.1.0",
        "health": "/health",
        "events": "/events",
        "otel_logs": "/ingest/otel/v1/logs",
        "otel_worker": "/internal/otel/process",
        "docs": "/docs",
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "sentinel-ai"}


@app.post("/events", dependencies=[Depends(_verify_ingest_key)])
def ingest_event(event: TelemetryEvent) -> JSONResponse:
    result = engine.invoke(
        {"raw_event": event, "audit_logs": []},
        config={"configurable": {"thread_id": _build_thread_id(event)}},
    )
    diagnosis = result.get("diagnosis")
    return JSONResponse(
        {
            "trace_id": result.get("trace_id"),
            "sanitization_ok": result.get("sanitization_ok"),
            "is_anomaly": result.get("is_anomaly"),
            "anomaly_score": result.get("anomaly_score"),
            "anomaly_output": (
                result.get("anomaly_output").model_dump() if result.get("anomaly_output") else None
            ),
            "historical_context": result.get("historical_context", []),
            "diagnosis": diagnosis.model_dump() if diagnosis else None,
            "notification_sent": result.get("notification_sent"),
            "audit_logs": result.get("audit_logs", []),
        }
    )


@app.post("/ingest/otel/v1/logs", dependencies=[Depends(_verify_ingest_key)])
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
