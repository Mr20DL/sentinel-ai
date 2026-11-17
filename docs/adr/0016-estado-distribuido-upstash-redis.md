# 16. Estado distribuido opcional con Upstash Redis REST

- **Status:** accepted
- **Date:** 2026-11-16
- **Deciders:** Equipo SentinelAI

## Context

El rate limiting, la deduplicacion de logs OTLP y el feed del dashboard viven en memoria
por proceso (ADR-0015). Eso es suficiente para una sola instancia de Render Free, pero al
escalar horizontalmente cada instancia tendria su propio limite, aceptaria duplicados y
mostraria un feed distinto. El proyecto ya usa Upstash QStash y no quiere agregar un
cliente Redis con conexiones TCP persistentes ni una dependencia nueva.

## Decision

1. **Cliente REST propio:** `UpstashRedisClient` en
   `src/adapters/upstash_redis.py` envia comandos Redis como un array JSON a
   `UPSTASH_REDIS_REST_URL` con `Authorization: Bearer`.
2. **Rate limiting distribuido:** `UpstashRedisRateLimiter` ejecuta un script Lua atomico
   sobre un sorted set por cliente. La ventana sigue siendo deslizante y usa
   `SENTINEL_RATE_LIMIT_PER_MINUTE`.
3. **Deduplicacion distribuida:** `UpstashRedisDedup` usa `SET key 1 NX PX ttl` con una
   clave SHA-256 derivada del evento. No se almacenan mensajes ni payloads completos.
4. **Feed distribuido:** `UpstashRedisEventFeed` guarda snapshots JSON en una lista con
   `LPUSH`, `LTRIM` y TTL de 24 horas. El tamano se limita con
   `SENTINEL_DASHBOARD_MAX_EVENTS`.
5. **Activacion opt-in:** si `UPSTASH_REDIS_REST_URL` y
   `UPSTASH_REDIS_REST_TOKEN` existen, el composition root inyecta los adaptadores Redis.
   Si faltan ambas, se conserva el comportamiento en memoria. Si solo existe una, el
   arranque falla con un error de configuracion.
6. **Degradacion controlada:** si Redis no responde, el rate limiting y la deduplicacion
   fallan abiertos para no bloquear la ingesta. Un fallo del feed se registra y el
   incidente se sigue procesando. La disponibilidad del diagnostico prevalece sobre la
   proteccion distribuida.

## Considered Options

- **Upstash Redis REST (elegido):** reutiliza `httpx`, no agrega dependencias, no necesita
  conexiones persistentes y comparte estado entre instancias.
- **`redis-py` contra Redis propio:** requiere hospedar Redis, abrir puertos y gestionar
  conexiones; mas costo operativo para el alcance actual.
- **Gateway o WAF con rate limiting:** no esta disponible en el plan gratuito y no cubre
  deduplicacion ni feed.
- **Mantener todo en memoria:** simple, pero no escala horizontalmente ni sobrevive a
  reinicios para el feed y el rate limit.

## Consequences

- **Positivas:**
  - Rate limit, deduplicacion y feed consistentes entre instancias.
  - Sin dependencia nueva; el cliente REST es pequeno y testeable con `httpx`.
  - La configuracion local y los tests siguen funcionando sin Redis.
  - Las claves de deduplicacion no exponen mensajes.
- **Negativas:**
  - Cada operacion agrega una llamada HTTP a Upstash; la latencia depende de la red.
  - El modo fail-open reduce la proteccion durante una caida de Redis.
  - El feed distribuido requiere TTL y limpieza por lista; no es un historial permanente.
  - Los checkpoints de LangGraph siguen en `MemorySaver`; se resolveran con
    `PostgresSaver` en una decision posterior.

## Links

- [ADR-0013: Cola QStash](0013-cola-qstash-ingesta-otel.md)
- [ADR-0014: Dashboard operativo](0014-dashboard-tiempo-real.md)
- [ADR-0015: Rate limiting en memoria](0015-rate-limiting-ingesta.md)
