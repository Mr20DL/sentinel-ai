from src.domain.graph import sentinel_app
from src.domain.state import TelemetryEvent

# 1. Creamos un evento simulado de un ERROR CRÍTICO
critical_event = TelemetryEvent(
    id=1,
    service_name="payment-service",
    environment="production",
    timestamp="2026-10-06T16:00:00Z",
    log_level="CRITICAL",
    message="Connection failure to payment gateway API.",
    metrics={"cpu": 95.5, "error_rate": 0.45}
)

# 2. Ejecutamos el grafo con la velocidad de uv
print("=== EJECUTANDO SENTINEL-AI ===")
result = sentinel_app.invoke({"raw_event": critical_event, "audit_logs": []})

# 3. Inspeccionamos la auditoría acumulada en el Estado
print("\n📋 HISTORIAL DE AUDITORÍA (Reducers en acción):")
for log in result.get("audit_logs", []):
    print(f" -> {log}")

print("\n🚨 DIAGNÓSTICO DEL SISTEMA:")
print(f" Causa Raíz: {result.get('root_cause_analysis')}")
print(f" Acción Recomendada: {result.get('recommended_action')}")