import os
import secrets
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from src.adapters.otel_ingestion import OtelLogNormalizer
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
    processed = 0
    failed = 0
    for event in events:
        try:
            result = engine.invoke(
                {"raw_event": event, "audit_logs": []},
                config={"configurable": {"thread_id": _build_thread_id(event)}},
            )
            if result.get("is_anomaly"):
                processed += 1
        except Exception:
            failed += 1
    return JSONResponse({"accepted": len(events), "processed": processed, "failed": failed})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.adapters.fastapi_app:app", host="127.0.0.1", port=8000, reload=True)
