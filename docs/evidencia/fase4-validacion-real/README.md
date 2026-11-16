# Evidencia de validacion real en Render - Fase 4

- **Fecha de captura inicial:** 2026-11-15
- **Fecha de validacion remota:** 2026-11-16
- **Commit validado:** `d783488` (`docs: record local QStash and Langfuse validation`)
- **Commit funcional de dashboard y rate limiting:** `d438b6c`
- **URL publica:** <https://sentinel-ai-46hj.onrender.com>
- **Entorno:** Render Free, Docker, region Oregon
- **LLM:** Groq, modelo `openai/gpt-oss-120b`
- **Embeddings:** Gemini, modelo `gemini-embedding-2`, 384 dimensiones
- **Persistencia:** Neon PostgreSQL con pgvector
- **Cola validada en Render:** `qstash` (`us-east-1`)
- **Observabilidad validada en Render:** `langfuse`
- **ADRs relacionados:**
  [`0014-dashboard-tiempo-real.md`](../../adr/0014-dashboard-tiempo-real.md),
  [`0015-rate-limiting-ingesta.md`](../../adr/0015-rate-limiting-ingesta.md)

## Resumen

| Caso | Evidencia | Resultado |
|---|---|---|
| Health check | `GET /health` | `200`, servicio disponible |
| Ruta raiz | `GET /` | Expone dashboard y rutas de ingesta |
| Seed de Neon | `scripts.seed_incidents` | `Seeded 5 incidents. Total rows: 5` |
| Incidente critico | `POST /events` | Diagnostico real con Groq y 3 registros historicos de Neon |
| Dashboard | `GET /dashboard/events` | Evento visible con `severity: critical` |
| Zero Trust | `POST /events` con mensaje vacio | Rechazado en `ingestion_node`; sin diagnostico |
| Rate limiting | 3 POST a `/events` con limite `2` y `X-Forwarded-For` fijo | Tercera peticion `429` con `Retry-After: 60` |
| OTLP en Render | `POST /ingest/otel/v1/logs` | `accepted: 1`, `queued: 1`, `failed: 0`; evento visible en dashboard |
| QStash | Worker `401`, OTLP asincrono y log de entrega | Validado en Render: `DELIVERED` con `200` y evento visible en dashboard |
| Langfuse | Incidente critico real desde Render | Validado en Render: 5 observaciones en la traza |

## Configuracion validada

La configuracion base del servicio se mantiene:

```text
SENTINEL_LLM_PROVIDER=groq
SENTINEL_LLM_MODEL=openai/gpt-oss-120b
SENTINEL_LLM_STRUCTURED_METHOD=function_calling
SENTINEL_EMBEDDING_PROVIDER=gemini
SENTINEL_EMBEDDING_MODEL=gemini-embedding-2
SENTINEL_EMBEDDING_DIMENSIONS=384
SENTINEL_DASHBOARD_MAX_EVENTS=100
SENTINEL_OTEL_MAX_EVENTS=3
SENTINEL_OTEL_DEDUP_TTL=60
SENTINEL_RATE_LIMIT_PER_MINUTE=120
```

La validacion remota del 2026-11-16 dejo activos en Render estos valores no secretos:

```text
SENTINEL_QUEUE_PROVIDER=qstash
QSTASH_URL=https://qstash-us-east-1.upstash.io
SENTINEL_OTEL_WORKER_URL=https://sentinel-ai-46hj.onrender.com/internal/otel/process
SENTINEL_OBSERVABILITY_PROVIDER=langfuse
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_TRACING_ENVIRONMENT=production
```

Las claves de QStash y Langfuse se cargaron como secretos en Render y no se incluyen en
este documento. `SENTINEL_RATE_LIMIT_PER_MINUTE=2` se uso solo durante la prueba de rate
limiting; el valor operativo quedo en `120`.

## Health check y ruta raiz

Comandos ejecutados:

```powershell
$base = "https://sentinel-ai-46hj.onrender.com"

Invoke-RestMethod "$base/health"
Invoke-RestMethod "$base/"
```

Salida relevante:

```text
status service
------ -------
ok     sentinel-ai
```

La ruta raiz respondio con:

```text
service          : sentinel-ai
version          : 0.1.0
health           : /health
events           : /events
otel_logs        : /ingest/otel/v1/logs
otel_worker      : /internal/otel/process
dashboard        : /dashboard
dashboard_events : /dashboard/events
docs             : /docs
```

## Seed de Neon

Comando ejecutado en local con `.env` apuntando a Neon y Gemini:

```powershell
uv run --env-file .env python -m scripts.seed_incidents
```

Salida:

```text
Seeded 5 incidents. Total rows: 5
```

## Incidente critico con LLM y RAG reales

Comando resumido:

```powershell
$body = @{
  id = 990001
  service_name = "payment-service"
  environment = "production"
  timestamp = "2026-11-15T12:00:00Z"
  log_level = "CRITICAL"
  message = "Connection failure to payment gateway API."
  metrics = @{ cpu = 95.5; error_rate = 0.45 }
} | ConvertTo-Json -Depth 5

$response = Invoke-RestMethod -Method Post `
  -Uri "$base/events" `
  -ContentType "application/json" `
  -Body $body
```

Salida relevante:

```json
{
  "trace_id": "trace-990001-payment-service",
  "sanitization_ok": true,
  "is_anomaly": true,
  "anomaly_score": 0.9,
  "historical_context": [
    "2026-09-01: Connection failure to payment gateway API resolved by restarting pool.",
    "2026-06-15: High latency in payment-service caused by DB connection exhaustion.",
    "2025-11-02: Partial outage after deploy; rolled back and enlarged connection pool."
  ],
  "diagnosis": {
    "root_cause": "Connection pool exhaustion in payment-service caused by high CPU load and traffic surge, leading to failure to reach the payment gateway API.",
    "severity": "critical",
    "recommended_action": "Restart the payment-service connection pool and, if needed, scale the service or increase pool size to handle load.",
    "runbook_steps": [
      "1. Verify the payment gateway API health via its status endpoint.",
      "2. Inspect the payment-service connection pool metrics (active, idle, max).",
      "3. Restart the connection pool or the entire payment-service process.",
      "4. If the issue recurs, increase the connection pool size or add additional service instances.",
      "5. Monitor CPU usage and error_rate until they return to normal thresholds."
    ]
  },
  "notification_sent": true,
  "audit_logs": [
    "[IngestionNode] Received event from service 'payment-service'.",
    "[IngestionNode] Payload de telemetría validado y limpio.",
    "[AnalysisNode] Evaluated anomaly status: True (score: 0.90).",
    "[ContextNode] Retrieved 3 historical records for 'payment-service'.",
    "[ResponseNode] Diagnosis and recommendation generated."
  ]
}
```

Este resultado confirma:

- Groq genero un diagnostico real, no el fallback heuristico.
- Neon devolvio 3 incidentes historicos.
- El nodo de respuesta notifico mediante el notificador configurado.

## Dashboard

Comando ejecutado:

```powershell
Invoke-RestMethod "$base/dashboard/events?limit=10" | ConvertTo-Json -Depth 10
```

La captura se hizo despues de las pruebas de rate limiting. El evento `990001` ya no
aparece porque los redeploys reiniciaron el feed en memoria; se usa `992002` como
evidencia equivalente del dashboard.

Fragmento de la salida real:

```json
[
  {
    "event_id": 992002,
    "service_name": "payment-service",
    "environment": "production",
    "timestamp": "2026-11-15T12:05:00Z",
    "log_level": "CRITICAL",
    "sanitization_ok": true,
    "is_anomaly": true,
    "anomaly_score": 0.9,
    "severity": "critical",
    "trace_id": "trace-992002-payment-service"
  },
  {
    "event_id": 990002,
    "service_name": "payment-service",
    "environment": "production",
    "timestamp": "2026-11-15T12:01:00Z",
    "log_level": "CRITICAL",
    "message": "",
    "sanitization_ok": false,
    "is_anomaly": false,
    "anomaly_score": 0.0,
    "severity": "ok",
    "root_cause": null,
    "recommended_action": null,
    "runbook_steps": [],
    "trace_id": "trace-990002-payment-service"
  }
]
```

El dashboard muestra correctamente un evento anomalo y un evento rechazado. La pagina
`GET /dashboard` consulta `GET /dashboard/events` cada 2 segundos.

## Zero Trust

Comando ejecutado:

```powershell
$bad = @{
  id = 990002
  service_name = "payment-service"
  environment = "production"
  timestamp = "2026-11-15T12:01:00Z"
  log_level = "CRITICAL"
  message = ""
  metrics = @{ cpu = 95.5; error_rate = 0.45 }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post `
  -Uri "$base/events" `
  -ContentType "application/json" `
  -Body $bad
```

Salida real normalizada a UTF-8:

```json
{
  "trace_id": "trace-990002-payment-service",
  "sanitization_ok": false,
  "is_anomaly": null,
  "anomaly_score": null,
  "anomaly_output": null,
  "historical_context": [],
  "diagnosis": null,
  "notification_sent": null,
  "audit_logs": [
    "[IngestionNode] Received event from service 'payment-service'.",
    "[IngestionNode] Payload de telemetría vacío: evento rechazado en la frontera."
  ]
}
```

`notification_sent: null` es el comportamiento esperado para este caso: el grafo termina
en `ingestion_node` y `response_node` nunca se ejecuta, por lo que la clave no existe en
el estado y FastAPI la serializa como `null`. La prueba
`tests/test_graph.py::test_zero_trust_rejects_empty_payload` valida que no sea `True`, y
la evidencia anterior `docs/evidencia/despliegue/04-zero-trust.txt` muestra el mismo
resultado.

El evento rechazado no ejecuto `analysis_node`, no genero diagnostico y no envio
notificacion. En el dashboard se normaliza como `is_anomaly: false` y `severity: ok`,
manteniendo `sanitization_ok: false` para que el rechazo sea visible.

## Rate limiting

Se configuro temporalmente:

```dotenv
SENTINEL_RATE_LIMIT_PER_MINUTE=2
```

El primer intento, sin fijar `X-Forwarded-For`, no fue concluyente: las tres peticiones
respondieron `200`. El segundo intento fijo la clave de prueba:

```powershell
$rateHeaders = @{ "X-Forwarded-For" = "203.0.113.77" }

1..3 | ForEach-Object {
  $payload = @{
    id = 992000 + $_
    service_name = "payment-service"
    environment = "production"
    timestamp = "2026-11-15T12:05:00Z"
    log_level = "CRITICAL"
    message = "Rate limit isolated test $_"
    metrics = @{ cpu = 95.5; error_rate = 0.45 }
  } | ConvertTo-Json -Depth 5

  try {
    $r = Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$base/events" `
      -Headers $rateHeaders -ContentType "application/json" -Body $payload
    "request $_ -> $($r.StatusCode)"
  } catch {
    "request $_ -> $([int]$_.Exception.Response.StatusCode) Retry-After=$($_.Exception.Response.Headers['Retry-After'])"
  }
}
```

Salida real:

```text
request 1 -> 200
request 2 -> 200
request 3 -> 429, Retry-After: 60
```

PowerShell muestra el `429` como `Error en el servidor remoto: (429) Too Many Requests`;
el codigo y la cabecera `Retry-After` son correctos.

## Ingesta OTLP real en Render

Con `SENTINEL_QUEUE_PROVIDER=inline` y el rate limit restaurado a `120`, se envio un log
OTLP con severidad `ERROR`:

```powershell
$now = [DateTimeOffset]::UtcNow
$nanos = [string]($now.ToUnixTimeMilliseconds() * 1000000)
$stamp = $now.ToUnixTimeSeconds()
$message = "Payment charge failed in Render OTLP validation $stamp"

$otel = @{
  resourceLogs = @(
    @{
      resource = @{
        attributes = @(
          @{ key = "service.name"; value = @{ stringValue = "payment" } },
          @{ key = "deployment.environment.name"; value = @{ stringValue = "production" } }
        )
      }
      scopeLogs = @(
        @{
          logRecords = @(
            @{
              timeUnixNano = $nanos
              severityText = "ERROR"
              body = @{ stringValue = $message }
              attributes = @(
                @{ key = "error_rate"; value = @{ doubleValue = 0.45 } },
                @{ key = "cpu"; value = @{ doubleValue = 91.5 } }
              )
              traceId = "trace-otlp-render-$stamp"
              spanId = "span-otlp-1"
            }
          )
        }
      )
    }
  )
} | ConvertTo-Json -Depth 12

Invoke-RestMethod -Method Post `
  -Uri "$base/ingest/otel/v1/logs" `
  -ContentType "application/json" `
  -Body $otel
```

Respuesta real:

```json
{"accepted":1,"queued":1,"failed":0}
```

El evento se proceso en la misma peticion porque la cola estaba en `inline`. La consulta
`GET /dashboard/events?limit=20` devolvio:

```json
{
  "event_id": 523198458151254729,
  "service_name": "payment",
  "environment": "production",
  "timestamp": "2026-11-15T08:41:43.099000Z",
  "log_level": "ERROR",
  "message": "Payment charge failed in Render OTLP validation 1794732103",
  "sanitization_ok": true,
  "is_anomaly": true,
  "anomaly_score": 0.9,
  "severity": "critical",
  "trace_id": "trace-523198458151254729-payment"
}
```

Esto confirma la cadena OTLP -> normalizacion -> grafo -> dashboard en Render. El evento
tambien genero diagnostico y runbook mediante el LLM configurado.

## QStash local y Render

La primera prueba uso el endpoint global por defecto del SDK y fallo porque el token
pertenece a otra region:

```text
QStashError: Request failed with status: 404
"not found in this region (eu-central-1). Check that you are using the correct endpoint."
```

Se fijo la region `us-east-1` y se probo el adaptador real `QStashTelemetryQueue` contra un
webhook temporal:

```powershell
$env:SENTINEL_QUEUE_PROVIDER = "qstash"
$env:QSTASH_URL = "https://qstash-us-east-1.upstash.io"
$env:SENTINEL_OTEL_WORKER_URL = "https://webhook.site/<token-temporal>"
uv run --env-file .env python <script-de-validacion>
```

Salida real:

```text
queue: QStashTelemetryQueue
is_remote: True
published_event_id: 1794733028
webhook_message_id: msg_7YoJxFpwkEy56tfz53hC1i6njnEZ9ZZ6zAoEXuTGvCGu4x7atGXqw
signature_valid: True
body_event_id: 1794733028
```

El webhook recibio `User-Agent: Upstash-QStash` y `upstash-region: us-east-1`. La firma se
verifico con `QSTASH_CURRENT_SIGNING_KEY` y `QSTASH_NEXT_SIGNING_KEY` mediante
`QStashTelemetryQueue.verify_signature`. El `.env` local no define `QSTASH_URL`; en la
prueba se paso por variable de entorno.

### QStash en Render

Con `SENTINEL_QUEUE_PROVIDER=qstash`, el worker remoto rechaza peticiones sin firma con
`401`, que es el comportamiento esperado. Luego se envio un OTLP real a
`/ingest/otel/v1/logs`:

```text
response={"accepted":1,"queued":1,"failed":0}
```

El log de QStash confirmo la entrega al worker:

```text
messageId: msg_7YoJxFpwkEy6sUx4uarLkWKj1uxYxawNHd4QrETyphu3jjji13XVv
state: DELIVERED
url: https://sentinel-ai-46hj.onrender.com/internal/otel/process
responseStatus: 200
```

El dashboard mostro el evento normalizado:

```text
event_id: 743264080429855354
service_name: payment
environment: production
log_level: ERROR
sanitization_ok: true
is_anomaly: true
anomaly_score: 0.9
severity: critical
trace_id: trace-743264080429855354-payment
```

## Langfuse local y Render

Con `SENTINEL_OBSERVABILITY_PROVIDER=langfuse` y las claves del `.env`, el SDK respondio:

```text
tracker: LangfuseTracker
auth_check: True
degraded: False
trace_id: f43b2b8f76a72ea037a0aa25a2ae2c7a
observations_found: 5
observation: sentinel.incident
observation: sentinel.node.ingestion_node
observation: sentinel.node.analysis_node
observation: sentinel.node.context_node
observation: sentinel.node.response_node
```

La prueba ejecuto el grafo real con `HeuristicDiagnoser` e `InMemoryRepository` para aislar
Langfuse. El evento critico termino con `is_anomaly: true`, `notification_sent: true` y
`trace_id` logico `trace-1794733001-payment-service`. Las observaciones se consultaron con
`client.api.observations.get_many(trace_id=...)` del SDK.

### Langfuse en Render

La traza remota del incidente reportado desde Render corresponde al evento `1794857615` y
al `trace_id` logico `trace-1794857615-payment-service`. La UI mostro `is_anomaly: true`,
`anomaly_score: 0.9`, `severity: critical`, `notification_sent: true` y 3 registros de
contexto historico.

La consulta al SDK confirmo la traza completa:

```text
seed: trace-1794857615-payment-service
trace_id: 364ebdcdfa8b67db06e0248c38dab3d7
observations_found: 5
observation: sentinel.node.response_node
observation: sentinel.node.context_node
observation: sentinel.node.analysis_node
observation: sentinel.node.ingestion_node
observation: sentinel.incident
```

## Configuracion aplicada en Render

Render quedo con ambas integraciones activas y sin secretos en el repositorio:

```text
SENTINEL_QUEUE_PROVIDER=qstash
QSTASH_URL=https://qstash-us-east-1.upstash.io
SENTINEL_OTEL_WORKER_URL=https://sentinel-ai-46hj.onrender.com/internal/otel/process
SENTINEL_OBSERVABILITY_PROVIDER=langfuse
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_TRACING_ENVIRONMENT=production
```

Los secretos `QSTASH_TOKEN`, `QSTASH_CURRENT_SIGNING_KEY`, `QSTASH_NEXT_SIGNING_KEY`,
`LANGFUSE_PUBLIC_KEY` y `LANGFUSE_SECRET_KEY` viven solo en Render Environment.
`render.yaml` declara los mismos providers y deja las claves como `sync: false`.

Si se recrea el servicio, cargar primero los secretos y despues desplegar. La composicion
falla al iniciar si `qstash` no tiene token, worker URL o signing keys, o si `langfuse` no
tiene sus claves.

## Calidad

La suite completa del commit funcional se ejecuto antes de publicar y esta registrada en
`docs/evidencia/fase4-dashboard/README.md`:

- `152 passed, 2 skipped`.
- Cobertura total: `97%`.
- `ruff check`: sin hallazgos.
- `mypy src`: sin errores.
- `bandit -r src -q`: sin hallazgos.

En esta captura se reejecutaron las pruebas de rate limiting y API:

```powershell
uv run pytest tests/test_rate_limiter.py tests/test_api.py -q
```

Resultado: `22 passed`.

Para la validacion de QStash y Langfuse se ejecutaron las pruebas de composicion, cola y
tracker:

```powershell
uv run pytest tests/test_composition.py tests/test_telemetry_queue.py tests/test_langfuse_tracker.py -q
```

Resultado: `54 passed`.

## Pendiente

- Confirmar que `SENTINEL_RATE_LIMIT_PER_MINUTE` volvio a `120` y que el deploy quedo
  `Live`.
- Si el servicio es Blueprint, verificar que `render.yaml` con `qstash`/`langfuse` sea la
  fuente de verdad y que un redeploy no revierta los providers.
- Vigilar la DLQ de QStash y los costos/limites de Langfuse Cloud.

## Limitaciones

- El feed del dashboard y el rate limiter viven en memoria por proceso. Un reinicio los
  reinicia y no se comparten entre instancias.
- El dashboard es publico y de solo lectura; no tiene autenticacion de usuarios.
- El rate limiting usa el primer valor de `X-Forwarded-For`. Es valido detras del proxy
  de Render, pero conviene verificar si Render conserva valores enviados por el cliente.
  Como endurecimiento futuro se puede preferir `CF-Connecting-IP` o una lista de proxies
  confiables.
- Render Free duerme tras un periodo sin trafico; la primera peticion puede tardar.
- La evidencia no incluye tokens, claves, contrasenas ni `DATABASE_URL`.
- La consola de Windows PowerShell puede mostrar caracteres no ASCII de forma corrupta;
  las salidas de este documento se normalizaron a UTF-8.

## Reproduccion

```powershell
$base = "https://sentinel-ai-46hj.onrender.com"

Invoke-RestMethod "$base/health"
Invoke-RestMethod "$base/"
Invoke-RestMethod "$base/dashboard/events?limit=10" | ConvertTo-Json -Depth 10
```

Para el seed local:

```powershell
uv run --env-file .env python -m scripts.seed_incidents
```

No se debe versionar el archivo `.env` ni incluir secretos en la evidencia.
