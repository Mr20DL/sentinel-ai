# Guia: modelos LLM gratuitos y despliegue en la nube sin pagar

Esta guia explica como reemplazar el diagnostico heuristico de SentinelAI por un modelo
real sin gastar dinero y como publicar la API FastAPI en la nube con costo operativo de
$0.00.

> Fecha de referencia: 2026-10-28. Los free tiers cambian con frecuencia. Verifica los
> limites y modelos vigentes en los enlaces oficiales antes de una demo o entrega.

## 1. Punto de partida

La Fase 2 ya tiene implementado:

- `DiagnosisPort` en `src/ports/diagnosis.py`.
- `LangChainDiagnoser` con salida estructurada `RootCauseReport`.
- `HeuristicDiagnoser` como fallback offline.
- Seleccion de proveedor desde variables de entorno en `src/composition.py`.

Si no configuras nada, `SENTINEL_LLM_PROVIDER=heuristic` y el sistema usa el diagnostico
deterministico. Eso es util para tests, pero no es un modelo de lenguaje real.

Lo que sigue sin implementarse de fases posteriores:

- Persistencia real en Neon/PostgreSQL (`PostgresIncidentRepository` es un stub).
- RAG con pgvector o ChromaDB.
- Observabilidad real con Langfuse (`NoopTracker` no envia trazas).
- Consumo de Upstash Kafka.
- Autenticacion y rate limiting del endpoint publico.

Por eso, al desplegar hoy tendras una API funcional con LLM real, pero con repositorio en
memoria y trazas no-op. Al reiniciar el servicio se pierde el estado en memoria.

## 2. Stack gratuito recomendado

| Componente | Servicio | Free tier | Limitacion principal |
|---|---|---|---|
| LLM principal | Groq | 30 RPM, 1.000 req/dia, 8K TPM, 200K tokens/dia por modelo | Requiere verificacion de telefono |
| LLM de respaldo | Google Gemini API | Tokens gratuitos por modelo, sin tarjeta | Puede usar contenido para mejorar sus productos |
| LLM alternativo | OpenRouter `:free` | 20 RPM y 50 req/dia (1.000/dia con $10 de credito historico) | Limite diario bajo y modelos rotativos |
| Hosting API | Render Free | 750 horas/mes, sin tarjeta | Duerme a los 15 min y tarda ~1 min en despertar |
| Base de datos futura | Neon PostgreSQL | Plan gratuito con auto-suspend | Fase 3; el codigo actual usa memoria |
| Kafka futuro | Upstash Kafka | Plan gratuito por request | Fase 4; aun no integrado |
| Observabilidad futura | Langfuse Cloud | Plan gratuito | Fase 4; aun no integrado |

Referencias:

- Groq rate limits: <https://console.groq.com/docs/rate-limits>
- Groq models: <https://console.groq.com/docs/models>
- Gemini OpenAI compatibility: <https://ai.google.dev/gemini-api/docs/openai>
- Gemini rate limits: <https://ai.google.dev/gemini-api/docs/rate-limits>
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
- El endpoint `/events` no tiene autenticacion todavia. No lo expongas a Internet con
  datos sensibles.
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
uv run ruff check src tests
uv run mypy src
uv run bandit -r src -q
```

## 11. Evidencia del despliegue

La evidencia de la primera publicacion en Render esta en:

[`docs/evidencia/despliegue/README.md`](evidencia/despliegue/README.md)

Incluye salidas de health check, incidente critico, evento normal, rechazo zero trust,
payload invalido y la ruta raiz local.

## 12. Checklist para la demo

- [ ] `GET /health` responde `{"status": "ok"}` en Render.
- [ ] `POST /events` con un incidente critico devuelve `is_anomaly: true`.
- [ ] `diagnosis.root_cause` no es el texto heuristico por defecto.
- [ ] `diagnosis.runbook_steps` tiene al menos un paso.
- [ ] `audit_logs` confirma que se genero el diagnostico.
- [ ] La key no aparece en el repositorio ni en capturas.
- [ ] Sabes que hacer si aparece `429` o si Render esta dormido.
- [ ] Puedes explicar que Neon, Kafka y Langfuse aun son trabajo de fases posteriores.
