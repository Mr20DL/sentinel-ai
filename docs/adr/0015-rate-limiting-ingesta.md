# 15. Rate limiting en memoria para los endpoints de ingesta

- **Status:** accepted
- **Date:** 2026-11-15
- **Deciders:** Equipo SentinelAI

## Context

`/events` y `/ingest/otel/v1/logs` son las fronteras publicas de SentinelAI. La API key
de ingesta es opcional y, cuando no esta configurada, cualquier cliente puede enviar
telemetria. Un pico de peticiones puede consumir cuota del LLM, llenar el feed del
dashboard o agotar la cuota de QStash.

El despliegue actual usa una sola instancia de Render Free. No hay Redis, gateway
propio ni balanceador con limites configurables.

## Decision

1. **Limite deslizante:** `SlidingWindowRateLimiter` en
   `src/adapters/rate_limiter.py` mantiene una cola de timestamps por clave, con lock y
   reloj inyectable para tests.
2. **Configuracion:** `SENTINEL_RATE_LIMIT_PER_MINUTE` define el limite por cliente y
   ventana de 60 segundos. El default es `120`; `0` desactiva el limite. Valores
   negativos se rechazan.
3. **Clave del cliente:** se usa el primer valor de `X-Forwarded-For`, que Render agrega
   al pasar por su proxy; si no existe, se usa `request.client.host`.
4. **Aplicacion:** el limite se aplica como dependencia de FastAPI en `/events` y
   `/ingest/otel/v1/logs`, despues de validar la API key. El worker interno de QStash no
   se limita porque QStash ya controla la entrega y los reintentos.
5. **Respuesta:** al exceder el limite se devuelve `429 Rate limit exceeded` con
   `Retry-After: 60`.

## Considered Options

- **Limite en memoria por instancia (elegido):** sin dependencias, suficiente para el
  despliegue de una sola instancia y para la demo.
- **Upstash Redis:** permitiria un limite distribuido, pero agrega un servicio, latencia
  de red y configuracion adicional.
- **Rate limiting en Render/WAF:** no esta disponible en el plan gratuito y no cubre
  ejecuciones locales.
- **No limitar:** deja la puerta abierta a abuso y a consumo accidental de cuota.

## Consequences

- **Positivas:**
  - Protege el costo del LLM y la cuota de QStash con una implementacion pequena.
  - Es configurable y se puede desactivar para pruebas locales.
  - La respuesta `429` es explicita y facilita reintentos ordenados.
- **Negativas:**
  - El limite es por proceso: al reiniciar se resetea y no se comparte entre instancias.
  - `X-Forwarded-For` solo es confiable detras de un proxy controlado; si la API se
    expone directamente, un cliente podria falsificarlo.
  - La ventana deslizante usa memoria proporcional al numero de clientes activos.
  - Para varias instancias o multiinquilino se necesitara Redis o un gateway dedicado.

## Links

- [ADR-0006: Zero trust en la ingesta](0006-zero-trust-ingesta.md)
- [ADR-0012: Ingesta OTLP](0012-ingesta-opentelemetry-demo.md)
- [ADR-0013: Cola QStash](0013-cola-qstash-ingesta-otel.md)
- [ADR-0014: Dashboard operativo](0014-dashboard-tiempo-real.md)
