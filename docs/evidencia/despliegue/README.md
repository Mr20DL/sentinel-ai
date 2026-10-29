# Evidencia de despliegue en Render Free

- **Fecha de captura:** 2026-10-29
- **URL pública:** <https://sentinel-ai-46hj.onrender.com>
- **Commit inicial de la captura:** `10b5a01`
- **Commit que agrega la ruta raíz:** `cda83b6`
- **Modelo:** `openai/gpt-oss-120b` (Groq free tier)
- **Proveedor LLM:** Groq
- **Hosting:** Render Free con Docker
- **Repositorio:** <https://github.com/Mr20DL/sentinel-ai>

## Resumen de pruebas

| Caso | Archivo | Resultado |
|---|---|---|
| Health check | `01-health.txt` | `200 OK`, servicio disponible |
| Incidente crítico | `02-evento-critico.txt` | Diagnóstico real de Groq con causa raíz y runbook |
| Evento normal | `03-evento-normal.txt` | Sin anomalía y sin diagnóstico, como se espera |
| Zero trust | `04-zero-trust.txt` | Evento rechazado antes del análisis |
| Payload inválido | `05-payload-invalido.txt` | `422 Unprocessable Entity` |
| Ruta raíz local | `06-root-local.txt` | `200 OK`, metadatos del servicio |
| Ruta raíz en Render | `07-root-render.txt` | `200 OK` tras desplegar `cda83b6` |

## Interpretación

El incidente crítico generó un diagnóstico detallado con causa raíz, severidad,
acción recomendada y seis pasos de runbook. El `audit_logs` termina con
`[ResponseNode] Diagnosis and recommendation generated.`, lo que confirma que no se usó
el fallback heurístico.

El evento normal terminó en `analysis_node` sin ejecutar `context_node` ni
`response_node`; por eso `diagnosis` es `null` y no se envió notificación.

El evento con mensaje vacío fue rechazado en `ingestion_node` con
`sanitization_ok: false`. No llegó a `analysis_node`, no generó diagnóstico y no envió
notificación, conforme a la frontera zero trust de ADR-0006.

El payload incompleto fue rechazado por FastAPI/Pydantic con `422`.

## Ruta raíz

La ruta `GET /` se validó localmente en `06-root-local.txt` y quedó desplegada en Render
con el commit `cda83b6`; su salida pública está en `07-root-render.txt`. Devuelve:

```json
{
  "service": "sentinel-ai",
  "version": "0.1.0",
  "health": "/health",
  "events": "/events",
  "docs": "/docs"
}
```

## Limitaciones actuales

- `historical_context` usa los incidentes de ejemplo de `InMemoryRepository`; no hay
  persistencia real en Neon todavía.
- El estado se pierde cuando Render reinicia o duerme el servicio.
- El endpoint `/events` no tiene autenticación ni rate limiting.
- Render Free duerme tras 15 minutos sin tráfico; la primera petición puede tardar
  cerca de un minuto.
- Groq free tier: 30 RPM, 1.000 req/día, 8K TPM y 200K tokens/día por modelo.
- Langfuse sigue usando `NoopTracker`; las trazas solo se imprimen en consola.
- Upstash Kafka aún no está integrado.

## Reproducción

```powershell
$body = @{
  id = 3002
  service_name = 'payment-service'
  environment = 'production'
  timestamp = '2026-10-28T17:10:00Z'
  log_level = 'CRITICAL'
  message = 'Connection failure to payment gateway API.'
  metrics = @{ cpu = 95.5; error_rate = 0.45 }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post `
  -Uri https://sentinel-ai-46hj.onrender.com/events `
  -ContentType 'application/json' `
  -Body $body
```

Las salidas de texto se normalizaron a UTF-8 para conservar tildes y caracteres
españoles. La API devuelve JSON con `telemetría` correctamente; algunas consolas de
Windows muestran ese texto como `telemetrÃa` por configuración de codificación.
