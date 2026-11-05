# Evidencia de cierre - Fase 4: ingesta OTLP desde OpenTelemetry Demo

- **Fecha de captura:** 2026-11-05
- **Commit validado:** `2f17b13` (`feat: add OpenTelemetry Demo log ingestion`)
- **Entorno:** Docker Desktop local en Windows
- **SentinelAI:** contenedor `sentinel-ai-otel`, host `8000` -> contenedor `8080`
- **OpenTelemetry Demo:** `compose.yaml` + `compose.override.yaml` en `E:\opentelemetry-demo`
- **Collector:** `otelcol-contrib` 0.160.0
- **Endpoint:** `http://host.docker.internal:8000/ingest/otel/v1/logs`
- **ADR:** [`docs/adr/0012-ingesta-opentelemetry-demo.md`](../../adr/0012-ingesta-opentelemetry-demo.md)

## Configuracion validada

El contenedor de SentinelAI se ejecuto con:

```text
SENTINEL_LLM_PROVIDER=heuristic
SENTINEL_EMBEDDING_PROVIDER=disabled
SENTINEL_INGEST_API_KEY=demo-secret
SENTINEL_OTEL_MAX_EVENTS=3
SENTINEL_OTEL_DEDUP_TTL=60
```

El Collector exporta logs por OTLP HTTP JSON, sin compresion, y aplica
`filter/sentinelai_noise` para descartar sus propios logs
(`resource.attributes["service.name"] == "otelcol-contrib"`).

## Resumen de pruebas

| Caso | Archivo | Resultado |
|---|---|---|
| Health check de SentinelAI | `01-health.txt` | `200 OK`, servicio disponible |
| Ingesta OTLP desde el demo | `02-ingesta-200.txt` | 4.165 POST a `/ingest/otel/v1/logs` con `200 OK` |
| Filtro de ruido del Collector | `03-filtro-ruido.txt` | `0` notificaciones de `otelcol-contrib` tras el reinicio |
| Evento critico end-to-end | `04-evento-critico.txt` | `load-generator` ejecuto `analysis/context/response` y notifico |
| Inyeccion de fallo | `05-inyeccion-fallo.txt` | `paymentFailure=100%`; 95 fallos `WARN` de `payment` |
| Apagado del demo | `06-demo-down.txt` | Stack detenido y sin contenedores del demo |

## Interpretacion

1. El Collector reenvio telemetria real del OpenTelemetry Demo a SentinelAI sin errores
   de autenticacion ni de contrato: 4.165 peticiones `200 OK` desde el reinicio.
2. El fallo inyectado `paymentFailure=100%` produjo 95 errores
   `Payment request failed. Invalid token.` en `payment`. Esos logs son `WARN`, por lo
   que el MVP logs-only los filtra correctamente.
3. La senal critica util provino de `load-generator`: SentinelAI ejecuto los nodos
   `analysis_node`, `context_node` y `response_node`, y envio la notificacion
   `[load-generator] Critical log level detected...`.
4. Antes del filtro, el Collector generaba incidentes falsos con
   `service.name=otelcol-contrib`. Despues de aplicar `filter/sentinelai_noise` y
   reiniciar el Collector, la ingesta siguio activa pero esas notificaciones bajaron a
   `0`.
5. El demo se detuvo al cerrar la evidencia; SentinelAI no se despliega a Render en esta
   fase y la ingesta OTLP queda validada solo en local.

## Validacion de calidad

La suite y el analisis estatico se ejecutaron sobre el commit validado:

```text
uv sync --extra dev
uv run pytest -v
uv run pytest --cov=src --cov-report=term-missing
uv run ruff check src tests
uv run mypy src
uv run bandit -r src -q
```

Resultado: `98 passed, 2 skipped`, cobertura total `97%`, `ruff` sin errores,
`mypy` sin errores y `bandit` sin hallazgos.

## Reproduccion

```powershell
# SentinelAI
docker run --rm --name sentinel-ai-otel -p 8000:8080 `
  -e SENTINEL_LLM_PROVIDER=heuristic `
  -e SENTINEL_EMBEDDING_PROVIDER=disabled `
  -e SENTINEL_INGEST_API_KEY=demo-secret `
  -e SENTINEL_OTEL_MAX_EVENTS=3 `
  -e SENTINEL_OTEL_DEDUP_TTL=60 `
  sentinel-ai:otel

# OpenTelemetry Demo
cd E:\opentelemetry-demo
docker compose -f compose.yaml -f compose.override.yaml up -d --quiet-pull

# Evidencia
docker logs --timestamps --since <collector_started> sentinel-ai-otel

# Apagado
docker compose -f compose.yaml -f compose.override.yaml down
```

## Limitaciones

- Solo se ingestan logs; metricas y trazas OTLP quedan pendientes.
- La deduplicacion es en memoria por proceso.
- `payment` emite el fallo como `WARN`; para la demo, el critico observable es
  `load-generator`.
- La ingesta OTLP no esta desplegada en Render.
