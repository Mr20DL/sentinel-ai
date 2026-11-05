# Guia: modelos LLM gratuitos y despliegue en la nube sin pagar

Esta guia explica como reemplazar el diagnostico heuristico de SentinelAI por un modelo
real sin gastar dinero y como publicar la API FastAPI en la nube con costo operativo de
$0.00.

> Fecha de referencia: 2026-11-02. Los free tiers cambian con frecuencia. Verifica los
> limites y modelos vigentes en los enlaces oficiales antes de una demo o entrega.

## 1. Punto de partida

La Fase 2 ya tiene implementado:

- `DiagnosisPort` en `src/ports/diagnosis.py`.
- `LangChainDiagnoser` con salida estructurada `RootCauseReport`.
- `HeuristicDiagnoser` como fallback offline.
- Seleccion de proveedor desde variables de entorno en `src/composition.py`.

Si no configuras nada, `SENTINEL_LLM_PROVIDER=heuristic` y el sistema usa el diagnostico
deterministico. Eso es util para tests, pero no es un modelo de lenguaje real.

La Fase 3 agrega:

- `EmbeddingPort` en `src/ports/embeddings.py`.
- `GeminiEmbeddingAdapter` con `gemini-embedding-2` y 384 dimensiones.
- `PostgresIncidentRepository` con Neon PostgreSQL y `pgvector`.
- Seed idempotente en `scripts/seed_incidents.py`.
- Busqueda semantica en `context_node` usando el mensaje del evento.

Lo que sigue sin implementarse de fases posteriores:

- Observabilidad real con Langfuse (`NoopTracker` no envia trazas).
- Consumo de Upstash Kafka.
- Autenticacion y rate limiting del endpoint publico.

Si `DATABASE_URL` no esta configurado, la API sigue usando `InMemoryRepository` y el
estado se pierde al reiniciar. Para persistencia real, configura Neon y ejecuta el seed.

## 2. Stack gratuito recomendado

| Componente | Servicio | Free tier | Limitacion principal |
|---|---|---|---|
| LLM principal | Groq | 30 RPM, 1.000 req/dia, 8K TPM, 200K tokens/dia por modelo | Requiere verificacion de telefono |
| LLM de respaldo | Google Gemini API | Tokens gratuitos por modelo, sin tarjeta | Puede usar contenido para mejorar sus productos |
| LLM alternativo | OpenRouter `:free` | 20 RPM y 50 req/dia (1.000/dia con $10 de credito historico) | Limite diario bajo y modelos rotativos |
| Hosting API | Render Free | 750 horas/mes, sin tarjeta | Duerme a los 15 min y tarda ~1 min en despertar |
| Base de datos RAG | Neon PostgreSQL + pgvector | Plan gratuito con auto-suspend | Fase 3; requiere `DATABASE_URL` |
| Embeddings | Gemini Embeddings | Free tier sin costo | Fase 3; requiere `GEMINI_API_KEY` |
| Kafka futuro | Upstash Kafka | Plan gratuito por request | Fase 4; aun no integrado |
| Observabilidad futura | Langfuse Cloud | Plan gratuito | Fase 4; aun no integrado |

Referencias:

- Groq rate limits: <https://console.groq.com/docs/rate-limits>
- Groq models: <https://console.groq.com/docs/models>
- Gemini OpenAI compatibility: <https://ai.google.dev/gemini-api/docs/openai>
- Gemini rate limits: <https://ai.google.dev/gemini-api/docs/rate-limits>
- Gemini embeddings: <https://ai.google.dev/gemini-api/docs/embeddings>
- Gemini pricing: <https://ai.google.dev/gemini-api/docs/pricing>
- OpenRouter limits: <https://openrouter.ai/docs/api-reference/limits>
- Render free tier: <https://render.com/docs/free>

## 3. Crear la API key de Groq

1. Entra a <https://console.groq.com/>.
2. Crea una cuenta y completa la verificacion de telefono si la solicita.
3. Abre `API Keys` y crea una key nueva.
4. Copia la key una sola vez. No la subas al repositorio ni la pegues en capturas.
5. Verifica en `Limits` el limite vigente para el modelo que vas a usar.

Modelo recomendado para empezar:

```text
openai/gpt-oss-120b
```

Si tienes errores `429`, prueba `openai/gpt-oss-20b` o `qwen/qwen3.8-27b`, siempre
revisando que sigan disponibles en el catalogo de Groq.

## 4. Configuracion local

Copia la plantilla y edita `.env`:

```powershell
Copy-Item .env.example .env
notepad .env
```

Contenido minimo para Groq:

```dotenv
SENTINEL_LLM_PROVIDER=groq
SENTINEL_LLM_MODEL=openai/gpt-oss-120b
GROQ_API_KEY=tu_key_de_groq
SENTINEL_LLM_STRUCTURED_METHOD=function_calling
SENTINEL_LLM_TIMEOUT=30
SENTINEL_LLM_MAX_RETRIES=2
```

`.env` esta ignorado por Git. No lo abras en un editor que lo sincronice a la nube.

Instala dependencias y ejecuta la API:

```powershell
$env:UV_LINK_MODE="copy"
$env:PYTHONUTF8="1"

uv sync --extra dev
uv run --env-file .env uvicorn src.adapters.fastapi_app:app --host 127.0.0.1 --port 8000
```

`uv run --env-file .env` carga las variables sin necesidad de instalar `python-dotenv`.

Verifica el health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

La ruta raíz devuelve metadatos y enlaces utiles:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/
```

Prueba un incidente real:

```powershell
$body = @{
  id = 1001
  service_name = "payment-service"
  environment = "production"
  timestamp = "2026-10-28T16:00:00Z"
  log_level = "CRITICAL"
  message = "Connection failure to payment gateway API."
  metrics = @{ cpu = 95.5; error_rate = 0.45 }
} | ConvertTo-Json -Depth 5

$response = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/events `
  -ContentType "application/json" `
  -Body $body

$response | ConvertTo-Json -Depth 10
```

En la respuesta revisa:

- `is_anomaly` debe ser `true` para el ejemplo.
- `diagnosis.root_cause` debe describir el incidente.
- `diagnosis.runbook_steps` debe contener pasos.
- `audit_logs` debe indicar que se genero el diagnostico.

Si aparece el mensaje de fallback heuristico en `audit_logs`, el proveedor fallo y el
sistema respondio de forma controlada. Revisa la seccion de troubleshooting.

## 5. Variables por proveedor

| Proveedor | `SENTINEL_LLM_PROVIDER` | Variable de key | Base URL por defecto | Modelo por defecto |
|---|---|---|---|---|
| Heuristico | `heuristic` o `mock` | ninguna | ninguna | ninguno |
| Groq | `groq` | `GROQ_API_KEY` | `https://api.groq.com/openai/v1` | `openai/gpt-oss-120b` |
| Gemini | `gemini` | `GEMINI_API_KEY` | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.5-flash` |
| OpenRouter | `openrouter` | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` | obligatorio definir |
| OpenAI | `openai` | `OPENAI_API_KEY` | oficial | `gpt-4o-mini` |
| Ollama local | `ollama` | `OLLAMA_API_KEY` | `http://localhost:11434/v1` | `llama3.1` |
| Otro compatible | `openai-compatible` | `SENTINEL_LLM_API_KEY` | obligatorio definir | obligatorio definir |

Overrides generales:

- `SENTINEL_LLM_API_KEY` tiene prioridad sobre la key especifica del proveedor.
- `SENTINEL_LLM_BASE_URL` tiene prioridad sobre la base URL por defecto.
- `SENTINEL_LLM_MODEL` tiene prioridad sobre el modelo por defecto.
- `SENTINEL_LLM_STRUCTURED_METHOD` acepta `function_calling`, `json_mode` o
  `json_schema`.
- `SENTINEL_LLM_TIMEOUT` y `SENTINEL_LLM_MAX_RETRIES` controlan timeouts y reintentos.

Ejemplo con Gemini:

```dotenv
SENTINEL_LLM_PROVIDER=gemini
GEMINI_API_KEY=tu_key
SENTINEL_LLM_MODEL=gemini-2.5-flash
```

Ejemplo con OpenRouter, usando un modelo gratuito vigente:

```dotenv
SENTINEL_LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=tu_key
SENTINEL_LLM_MODEL=meta-llama/llama-3.3-70b-instruct:free
```

OpenRouter tiene un limite diario muy bajo en la cuenta gratuita. Usalo como respaldo o
para pruebas puntuales, no como proveedor principal de una demo con muchos eventos.

## 6. Desplegar en Render Free

### 6.1 Preparar el repositorio

1. Verifica que `.env` no este versionado:

```powershell
git status --short
```

2. Confirma que `.env.example`, `Dockerfile`, `.dockerignore` y `render.yaml` si esten
   versionados.
3. Haz commit y push de los cambios cuando el equipo lo autorice.

### 6.2 Crear el Blueprint

1. Entra a <https://render.com/> y crea una cuenta.
2. Conecta tu cuenta de GitHub.
3. En el dashboard elige `New` > `Blueprint`.
4. Selecciona el repositorio de SentinelAI.
5. Render detectara `render.yaml` y propondra el servicio `sentinel-ai`.
6. Cuando pida el valor de `GROQ_API_KEY`, pega la key. Render la guarda como secreto.
7. Confirma el plan `free` y despliega.

El blueprint ya configura:

```text
SENTINEL_LLM_PROVIDER=groq
SENTINEL_LLM_MODEL=openai/gpt-oss-120b
SENTINEL_LLM_STRUCTURED_METHOD=function_calling
SENTINEL_LLM_TIMEOUT=30
SENTINEL_LLM_MAX_RETRIES=3
```

### 6.3 Verificar el despliegue

Cuando Render termine, tendras una URL similar a:

```text
https://sentinel-ai-xxxx.onrender.com
```

Prueba el health check y la ruta raiz:

```powershell
Invoke-RestMethod https://sentinel-ai-xxxx.onrender.com/health
Invoke-RestMethod https://sentinel-ai-xxxx.onrender.com/
```

La primera peticion puede tardar cerca de un minuto si el servicio estaba dormido.

Prueba el endpoint de eventos:

```powershell
$body = @{
  id = 2001
  service_name = "payment-service"
  environment = "production"
  timestamp = "2026-10-28T16:10:00Z"
  log_level = "CRITICAL"
  message = "Payment gateway latency exceeded 5 seconds."
  metrics = @{ cpu = 92.0; error_rate = 0.42 }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
  -Method Post `
  -Uri https://sentinel-ai-xxxx.onrender.com/events `
  -ContentType "application/json" `
  -Body $body
```

### 6.4 Limites de Render Free

- 750 horas de instancia por mes y workspace.
- El servicio se duerme tras 15 minutos sin trafico.
- El arranque en frio tarda aproximadamente un minuto.
- El filesystem es efimero: no guardes SQLite ni archivos locales.
- No esta pensado para produccion real; sirve para demo, pruebas y evidencia academica.
- Render puede reiniciar el servicio en cualquier momento.

## 7. Seguridad y datos

- Nunca subas `.env`, keys, tokens ni payloads reales al repositorio.
- En Render, usa variables de entorno secretas; no las escribas en `render.yaml`.
- Rota la key inmediatamente si se filtra.
- `/events` y `/ingest/otel/v1/logs` aceptan `X-Ingest-Key` solo si defines
  `SENTINEL_INGEST_API_KEY`. Sin esa variable no hay autenticacion; no los expongas a
  Internet con datos sensibles. En Render, define la variable para la demo.
- No envies secretos, credenciales ni datos personales en `message`, `metrics` ni
  `historical_context`.
- Groq indica que no usa tus entradas/salidas para entrenamiento salvo que lo permitas,
  pero revisa sus terminos vigentes.
- Gemini free tier puede usar el contenido para mejorar sus productos fuera de algunas
  regiones. Para datos sensibles, prefiere Ollama local o un proveedor con garantias
  contractuales.

## 8. Troubleshooting

### `401 Unauthorized`

La key no esta configurada o es invalida. Verifica `GROQ_API_KEY` o
`SENTINEL_LLM_API_KEY`. Si cambiaste la key en Render, vuelve a desplegar.

### `404 model_not_found`

El modelo ya no existe o el ID esta mal escrito. Consulta el catalogo actual de Groq,
Gemini u OpenRouter y actualiza `SENTINEL_LLM_MODEL`.

### `429 Too Many Requests`

Se agoto el limite gratuito. Espera, reduce la frecuencia de eventos o cambia de modelo.
El adaptador reintenta automaticamente segun `SENTINEL_LLM_MAX_RETRIES`.

### Error de structured output

Si el proveedor no soporta function calling, prueba:

```dotenv
SENTINEL_LLM_STRUCTURED_METHOD=json_mode
```

Si el proveedor soporta JSON Schema estricto, prueba `json_schema`. Un fallo de parsing
no tumba la API: `response_node` usa el diagnostico heuristico y lo registra en
`audit_logs`.

### Cold start o timeout

Render Free duerme el servicio. La primera peticion puede tardar ~1 minuto. Si el modelo
tarda demasiado, aumenta `SENTINEL_LLM_TIMEOUT` o usa un modelo mas pequeno.

### La API funciona local pero no en Docker

- Confirma que `uv.lock` esta actualizado.
- Revisa que el contenedor escuche en el puerto que Render define en `PORT`.
- Ejecuta el contenedor localmente para aislar el problema:

```powershell
docker build -t sentinel-ai .
docker run --rm -p 8000:8080 -e SENTINEL_LLM_PROVIDER=heuristic sentinel-ai
Invoke-RestMethod http://127.0.0.1:8000/health
```

## 9. Prueba de integracion real opt-in

La suite normal usa el fallback heuristico y no hace llamadas de red. Para probar un
proveedor real:

```powershell
$env:SENTINEL_LLM_INTEGRATION="1"
$env:SENTINEL_LLM_INTEGRATION_PROVIDER="groq"
$env:GROQ_API_KEY="tu_key"

uv run pytest tests/test_llm_integration.py -v
```

Esta prueba consume cuota del free tier. No la ejecutes en CI sin controlar el costo y
la disponibilidad de la key.

## 10. Comandos de validacion

Antes de cerrar un cambio:

```powershell
$env:UV_LINK_MODE="copy"
$env:PYTHONUTF8="1"

uv sync --extra dev
uv run pytest -v
uv run pytest --cov=src --cov-report=term-missing
uv run ruff check src tests scripts
uv run mypy src
uv run bandit -r src -q
```

## 11. Evidencia del despliegue

La evidencia de la primera publicacion en Render esta en:

[`docs/evidencia/despliegue/README.md`](evidencia/despliegue/README.md)

Incluye salidas de health check, incidente critico, evento normal, rechazo zero trust,
payload invalido y la ruta raiz local.

## 12. Fase 3: RAG con Neon y Gemini

### 12.1 Crear la base de datos

1. Crea un proyecto en <https://neon.tech/>.
2. Copia la cadena de conexion PostgreSQL. Debe incluir `sslmode=require`.
3. Guardala como `DATABASE_URL` en `.env` y en Render. No la subas al repositorio.

Neon ya soporta la extension `pgvector`; el seed ejecuta `CREATE EXTENSION IF NOT EXISTS
vector`. La tabla se crea con `embedding vector(384)` y un indice HNSW para similitud
coseno.

### 12.2 Crear la API key de Gemini

1. Entra a <https://aistudio.google.com/app/apikey>.
2. Crea una API key y guardala como `GEMINI_API_KEY`.
3. No reutilices la key de Groq: son proveedores distintos.

### 12.3 Configuracion local

Agrega a `.env`:

```dotenv
DATABASE_URL=postgresql://usuario:password@host/neondb?sslmode=require
SENTINEL_EMBEDDING_PROVIDER=gemini
SENTINEL_EMBEDDING_MODEL=gemini-embedding-2
SENTINEL_EMBEDDING_DIMENSIONS=384
SENTINEL_EMBEDDING_TIMEOUT=20
GEMINI_API_KEY=tu_key_de_gemini
```

Con `DATABASE_URL` y el proveedor `gemini`, `composition.py` construye
`PostgresIncidentRepository`. Si falta cualquiera de los dos, la API falla al arrancar
para no ocultar una mala configuracion. Sin `DATABASE_URL`, usa `InMemoryRepository`:
tener solo `GEMINI_API_KEY` no activa el RAG ni persiste incidentes.

### 12.4 Crear el esquema y sembrar incidentes

```powershell
uv run --env-file .env python -m scripts.seed_incidents
```

El script es idempotente: crea la extension y la tabla, y actualiza los embeddings con
`ON CONFLICT`. Verifica el total de filas:

```powershell
uv run --env-file .env python -c "from src.composition import build_embedding_adapter, load_database_url; from src.adapters.neon_db import PostgresIncidentRepository; print(PostgresIncidentRepository(load_database_url(), build_embedding_adapter()).count_incidents())"
```

### 12.5 Probar la integracion real

La suite normal usa un repositorio falso. Para probar Neon y Gemini de verdad:

```powershell
$env:SENTINEL_RAG_INTEGRATION="1"
uv run --env-file .env pytest tests/test_rag_integration.py -v
```

La prueba inserta un incidente temporal, busca por similitud y lo elimina al terminar.
Ejecutala sola, no junto con la suite normal, para que `SENTINEL_RAG_INTEGRATION=1` y
las credenciales reales no afecten a los demas tests.

### 12.6 Configurar Render

En el dashboard de Render agrega estas variables al servicio:

```dotenv
DATABASE_URL=postgresql://...
SENTINEL_EMBEDDING_PROVIDER=gemini
SENTINEL_EMBEDDING_MODEL=gemini-embedding-2
SENTINEL_EMBEDDING_DIMENSIONS=384
GEMINI_API_KEY=...
```

Despues del despliegue, dispara un incidente critico. Si Neon esta sembrado,
`historical_context` se llena y el diagnostico de Groq recibe esos antecedentes. Si la
busqueda falla, el grafo continua sin RAG y deja constancia en `audit_logs`.

Validado en Render el 2026-11-05: un incidente de prueba recupero el marcador sembrado
en Neon y `audit_logs` reporto `[ContextNode] Retrieved 1 historical records`. La fila
temporal se elimino despues de la prueba.

## 13. Fase 4: ingesta desde OpenTelemetry Demo

Esta integracion usa logs reales de OpenTelemetry Demo. El Collector reenvia los logs
por OTLP HTTP JSON a SentinelAI; el dominio sigue recibiendo solo `TelemetryEvent`.

```text
OpenTelemetry Demo -> OTel Collector -> /ingest/otel/v1/logs -> ingestion_node -> grafo
```

### 13.1 Requisitos

- Docker Desktop activo.
- OpenTelemetry Demo clonado y funcionando.
- SentinelAI ejecutandose en el host, no dentro de Render Free.

### 13.2 Configurar SentinelAI

Agrega a `.env` o exporta en la terminal:

```dotenv
SENTINEL_INGEST_API_KEY=demo-secret
SENTINEL_OTEL_MAX_EVENTS=3
SENTINEL_OTEL_DEDUP_TTL=60
```

`SENTINEL_OTEL_MAX_EVENTS` limita cuantos eventos procesa cada request.
`SENTINEL_OTEL_DEDUP_TTL` evita repetir el mismo error del mismo servicio durante esa
ventana de segundos. `SENTINEL_INGEST_API_KEY` es opcional; si esta definida, los
endpoints de ingesta exigen el header `X-Ingest-Key`.

Si defines la key, pasa la misma variable al contenedor del Collector en un
`compose.override.yaml` dentro del demo; de lo contrario el header viaja vacio y
recibes `401`:

```yaml
services:
  otel-collector:
    environment:
      SENTINEL_INGEST_API_KEY: ${SENTINEL_INGEST_API_KEY}
```

Inicia la API escuchando en todas las interfaces:

```powershell
uv run --env-file .env uvicorn src.adapters.fastapi_app:app --host 0.0.0.0 --port 8000
```

### 13.3 Conectar el Collector

Copia `integrations/otel-demo/otelcol-config-extras.yml` sobre el archivo equivalente
del demo:

```powershell
Copy-Item integrations/otel-demo/otelcol-config-extras.yml `
  C:\ruta\opentelemetry-demo\src\otel-collector\otelcol-config-extras.yml
```

El archivo usa `http://host.docker.internal:8000/ingest/otel`, que en Docker Desktop
apunta al host. Si usas Linux, reemplaza el host por la IP del host o configura
`extra_hosts`. Mantiene `encoding: json` y `compression: none` porque el endpoint no
descomprime gzip. Tambien agrega `filter/sentinelai_noise` para no reenviar los errores
internos del propio Collector (`service.name=otelcol-contrib`) y conserva los
procesadores base de logs (`resource_detection`, `memory_limiter` y
`transform/sanitize_logs`).

Inicia el demo (la primera ejecucion puede tardar varios minutos):

```powershell
Set-Location C:\ruta\opentelemetry-demo
docker compose -f compose.yaml -f compose.override.yaml up -d --quiet-pull
```

### 13.4 Generar un incidente

Activa el fallo de pago del demo cambiando `paymentFailure.defaultVariant` a `"100%"` en
`src/flagd/demo.flagd.json`, o usa la UI de Flagd en `http://localhost:4000`.

El fallo del servicio `payment` se registra como `WARN`, por lo que el normalizador lo
filtra. La senal que si llega a SentinelAI es el log critico que emite
`load-generator` cuando el checkout falla. No esperes un evento con
`service_name=payment` por este flag.

Verifica que el Collector reenvia logs y que SentinelAI responde `200`:

```powershell
docker logs otel-collector --tail 50
docker logs sentinel-ai-otel --tail 50
```

En una prueba directa al endpoint veras un resumen como
`{"accepted": 1, "processed": 1, "failed": 0}`; el Collector solo muestra el `200`.

### 13.5 Limites y siguientes pasos

- Solo se procesan logs `ERROR`, `CRITICAL` o `FATAL`. Un `WARN` como el de
  `paymentFailure` no se ingiere; el impacto se observa en el `ERROR`/`CRITICAL` de
  `load-generator`.
- Los logs internos del Collector (`otelcol-contrib`) se descartan con
  `filter/sentinelai_noise` para evitar incidentes del propio Collector.
- Las metricas y trazas OTLP quedan para una siguiente iteracion.
- La deduplicacion es en memoria por proceso; con varios workers se necesita un
  almacenamiento compartido.
- El demo no corre en Render Free. Para la evidencia, ejecutalo localmente y captura la
  respuesta del endpoint y los logs del Collector.
- Si el Collector no conecta, confirma que SentinelAI escucha en `0.0.0.0`, que el
  puerto `8000` esta libre y que `host.docker.internal` resuelve desde el contenedor.

## 14. Checklist para la demo

- [ ] `GET /health` responde `{"status": "ok"}` en Render.
- [ ] `POST /events` con un incidente critico devuelve `is_anomaly: true`.
- [ ] `diagnosis.root_cause` no es el texto heuristico por defecto.
- [ ] `diagnosis.runbook_steps` tiene al menos un paso.
- [ ] `audit_logs` confirma que se genero el diagnostico.
- [ ] `historical_context` proviene de Neon/pgvector, no de `DEFAULT_INCIDENTS`.
- [ ] `python -m scripts.seed_incidents` ya se ejecuto y el conteo de filas es mayor que cero.
- [ ] La key no aparece en el repositorio ni en capturas.
- [ ] Sabes que hacer si aparece `429` o si Render esta dormido.
- [ ] Si usas OTel Demo, el Collector reenvia logs a `/ingest/otel/v1/logs`
      (`200 OK`) y SentinelAI procesa al menos un evento critico.
- [ ] Puedes explicar que Neon/pgvector y Gemini Embeddings ya estan activos; la ingesta
      OTel Demo es logs-only y Kafka/Langfuse siguen pendientes.
