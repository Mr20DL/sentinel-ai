# Evidencia del dashboard y rate limiting

- **Fecha:** 2026-11-15
- **Alcance:** Fase 4, dashboard operativo y proteccion de los endpoints de ingesta.
- **Commit funcional:** pendiente de publicacion al momento de esta captura.

## Dashboard

La pagina `GET /dashboard` se sirve desde FastAPI y consulta
`GET /dashboard/events?limit=50` cada 2 segundos. El feed conserva 100 eventos por
defecto mediante `SENTINEL_DASHBOARD_MAX_EVENTS`.

Comando ejecutado:

```powershell
uv run python -c "from fastapi.testclient import TestClient; from src.adapters.fastapi_app import app; c=TestClient(app); page=c.get('/dashboard'); print('dashboard', page.status_code, 'SentinelAI' in page.text); payload={'id':990001,'service_name':'payment-service','environment':'production','timestamp':'2026-11-15T12:00:00Z','log_level':'CRITICAL','message':'Connection failure to payment gateway API.','metrics':{'cpu':95.5,'error_rate':0.45}}; print('post', c.post('/events', json=payload).status_code); events=c.get('/dashboard/events?limit=1').json()['events']; print('events', len(events)); print('snapshot', {k: events[0][k] for k in ('event_id','is_anomaly','severity','root_cause')})"
```

Salida relevante:

```text
dashboard 200 True
post 200
events 1
snapshot {'event_id': 990001, 'is_anomaly': True, 'severity': 'critical', 'root_cause': 'Critical log level detected in payment-service'}
```

## Rate limiting

`SENTINEL_RATE_LIMIT_PER_MINUTE` define el limite deslizante de 60 segundos por cliente.
El default es `120`; `0` lo desactiva. Al excederlo, `/events` y
`/ingest/otel/v1/logs` responden `429` con `Retry-After: 60`.

La prueba de regresion `tests/test_api.py::test_rate_limit_rejects_excess_requests`
configura un limite de una peticion y verifica el `429` en la segunda solicitud.

## Calidad

Comandos ejecutados:

```powershell
uv sync --extra dev
uv run pytest -v
uv run pytest --cov=src --cov-report=term-missing -q
uv run ruff check src tests
uv run mypy src
uv run bandit -r src -q
```

Resultados:

- `152 passed, 2 skipped`.
- Cobertura total: `97%`.
- `ruff check`: sin hallazgos.
- `mypy src`: sin errores.
- `bandit -r src -q`: sin hallazgos.

## Limitaciones

- El feed y el rate limiter viven en memoria: se reinician con el proceso y no se
  comparten entre instancias.
- El dashboard es de solo lectura y no tiene autenticacion de usuarios.
- El rate limiting usa `X-Forwarded-For`, confiable solo detras del proxy de Render.
- La validacion end-to-end con credenciales reales de QStash sigue pendiente.
