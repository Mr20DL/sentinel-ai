# 14. Dashboard operativo con feed en memoria y polling

- **Status:** accepted
- **Date:** 2026-11-15
- **Deciders:** Equipo SentinelAI

## Context

La Fase 4 incluye un dashboard para observar la telemetria procesada sin abrir la
documentacion de la API ni revisar los logs de Render. El MVP necesita una vista simple
que muestre el ultimo evento, su severidad, el score de anomalia y el diagnostico
generado.

El proyecto no tiene frontend, autenticacion de usuarios ni una base de datos de
telemetria historica. Agregar SSE, WebSocket o un framework de UI aumentaria la
superficie del MVP y las dependencias sin mejorar la demostracion.

## Decision

1. **Contrato de lectura:** `EventSnapshot` en `src/domain/state.py` resume un evento
   procesado (estado de sanitizacion, anomalia, severidad, diagnostico, runbook y
   `trace_id`). Se construye desde el resultado del grafo, sin duplicar reglas de
   negocio en el adaptador.
2. **Puerto de feed:** `src/ports/event_feed.py` define `EventFeedPort` con `record` y
   `recent`. El dominio no conoce la implementacion.
3. **Feed en memoria:** `InMemoryEventFeed` conserva los ultimos 100 eventos por defecto
   (`SENTINEL_DASHBOARD_MAX_EVENTS`), con `deque` y lock para lecturas concurrentes.
4. **Entrega HTTP:** `GET /dashboard` sirve una pagina HTML estatica incluida en
   `src/adapters/dashboard.html`. `GET /dashboard/events?limit=50` devuelve los snapshots
   como JSON. La pagina consulta el endpoint cada 2 segundos con `fetch`.
5. **Registro transparente:** `_process_event()` registra cada resultado en el feed. Esto
   cubre tanto `/events` como el worker de QStash y el modo inline.
6. **Sin autenticacion en el dashboard:** la vista es de solo lectura y no expone
   payloads completos. Las credenciales de ingesta siguen aplicando a `/events` y
   `/ingest/otel/v1/logs`.

## Considered Options

- **Polling cada 2 s (elegido):** simple, sin dependencias, compatible con Render Free y
  suficiente para una demo operativa.
- **SSE:** menor latencia, pero requiere manejar reconexiones, keep-alive y el ciclo de
  vida del cliente; no aporta valor al MVP.
- **WebSocket:** bidireccional y mas complejo; el dashboard solo necesita lectura.
- **Persistir snapshots en Neon:** agrega escrituras y migraciones; el dashboard es una
  vista operativa, no un historico de auditoria.

## Consequences

- **Positivas:**
  - El dashboard no agrega dependencias ni procesos nuevos.
  - El feed es thread-safe y se alimenta automaticamente del flujo real del grafo.
  - La pagina tolera fallos de red y muestra el estado de conexion.
- **Negativas:**
  - Los eventos se pierden al reiniciar el proceso y no se comparten entre instancias.
  - El historico esta acotado por `SENTINEL_DASHBOARD_MAX_EVENTS`.
  - El polling genera una peticion cada 2 segundos por cliente abierto.
  - Si se necesita tiempo real estricto o multi-instancia, habra que migrar a SSE y a un
    almacenamiento compartido.

## Links

- [ADR-0001: Arquitectura hexagonal](0001-arquitectura-hexagonal.md)
- [ADR-0006: Zero trust en la ingesta](0006-zero-trust-ingesta.md)
- [ADR-0012: Ingesta OTLP](0012-ingesta-opentelemetry-demo.md)
- [ADR-0013: Cola QStash](0013-cola-qstash-ingesta-otel.md)
