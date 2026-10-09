from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.domain.graph import create_sentinel_graph
from src.domain.state import TelemetryEvent

app = FastAPI(
    title="SentinelAI",
    version="0.1.0",
    description="Plataforma de observabilidad autónoma (motor agéntico LangGraph).",
)

engine = create_sentinel_graph()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "sentinel-ai"}


@app.post("/events")
def ingest_event(event: TelemetryEvent) -> JSONResponse:
    result = engine.invoke({"raw_event": event, "audit_logs": []})
    diagnosis = result.get("diagnosis")
    return JSONResponse(
        {
            "trace_id": result.get("trace_id"),
            "sanitization_ok": result.get("sanitization_ok"),
            "is_anomaly": result.get("is_anomaly"),
            "anomaly_score": result.get("anomaly_score"),
            "anomaly_output": (
                result.get("anomaly_output").model_dump()
                if result.get("anomaly_output")
                else None
            ),
            "historical_context": result.get("historical_context", []),
            "diagnosis": diagnosis.model_dump() if diagnosis else None,
            "notification_sent": result.get("notification_sent"),
            "audit_logs": result.get("audit_logs", []),
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.adapters.fastapi_app:app", host="0.0.0.0", port=8000, reload=True)