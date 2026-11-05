# 12. Ingesta de telemetria real desde OpenTelemetry Demo

- **Status:** accepted
- **Date:** 2026-11-05
- **Deciders:** Equipo SentinelAI

## Context

El caso de negocio define OpenTelemetry Demo como fuente de telemetria para la demo
(`docs/business_case.md`, seccion 8). Hoy SentinelAI solo acepta `TelemetryEvent`
construidos a mano mediante `POST /events`; no existe un adaptador para telemetria real
emitida por microservicios.

OpenTelemetry Demo emite logs, metricas y trazas por OTLP al Collector en los puertos
`4317` (gRPC) y `4318` (HTTP). El motor agentico no debe acoplarse al formato OTLP ni
depender de OpenTelemetry en el dominio. Ademas, una tormenta de errores reales puede
generar cientos de eventos y consumir cuotas de Groq/Gemini si se procesan sin filtros.

## Decision

1. **Frontera de ingesta:** el Collector de OpenTelemetry Demo exporta logs por OTLP
   HTTP JSON a `POST /ingest/otel/v1/logs`.
2. **Normalizador en adaptadores:** `src/adapters/otel_ingestion.py` convierte cada log
   OTLP en el `TelemetryEvent` canonico existente. El dominio no importa OpenTelemetry.
3. **MVP solo logs:** se procesan unicamente severidades `ERROR`, `CRITICAL` y `FATAL`.
   Metricas y trazas OTLP quedan para una iteracion posterior.
4. **Control de costo:** el normalizador deduplica por servicio, mensaje y minuto, y
   procesa como maximo `SENTINEL_OTEL_MAX_EVENTS` eventos por request. La ventana de
   deduplicacion se configura con `SENTINEL_OTEL_DEDUP_TTL`.
5. **Autenticacion opcional:** si existe `SENTINEL_INGEST_API_KEY`, los endpoints de
   ingesta exigen el header `X-Ingest-Key`. Sin la variable, el comportamiento actual
   queda abierto para desarrollo local.
6. **Sin Kafka en esta fase:** el Collector entrega por HTTP directo. Kafka/Upstash se
   evalua cuando la ingesta sincrona y el control de volumen ya sean estables.
7. **Ejecucion local:** OpenTelemetry Demo y su Collector corren con Docker fuera de
   Render Free; SentinelAI puede ejecutarse en el host o en otro contenedor.

## Considered Options

- **Collector OTLP HTTP + normalizador (elegido):** mantiene el dominio limpio, usa el
  estandar de OpenTelemetry y permite filtrar antes de invocar el grafo.
- **Recibir OTLP directamente en el dominio:** menos componentes, pero acopla el motor a
  un formato de infraestructura y complica la validacion zero trust.
- **Tail de logs de contenedores:** rapido para una demo, pero depende del runtime y no
  aprovecha metricas ni trazas estructuradas.

## Consequences

- **Positivas:**
  - La demo usa telemetria de microservicios reales y fallos inyectables del OTel Demo.
  - El contrato `TelemetryEvent` sigue siendo la unica entrada del dominio.
  - El filtro y la deduplicacion reducen el consumo de APIs de LLM.
  - El Collector descarta sus propios logs (`otelcol-contrib`) para evitar incidentes de
    infraestructura del propio Collector.
- **Negativas:**
  - El MVP no usa todavia metricas ni trazas OTLP.
  - La deduplicacion es en memoria por proceso; con multiples workers se necesita un
    almacenamiento compartido.
  - El fallo `paymentFailure` del demo emite `WARN`, que el MVP filtra; la senal util
    llega como `ERROR`/`CRITICAL` del `load-generator`.
  - La demo requiere levantar Docker con OpenTelemetry Demo y su Collector.

## Links

- [ADR-0001: Arquitectura hexagonal](0001-arquitectura-hexagonal.md)
- [ADR-0006: Zero trust](0006-zero-trust-architecture.md)
- [ADR-0011: RAG con Neon y Gemini](0011-rag-neon-pgvector-gemini.md)
- [Caso de negocio](../business_case.md)
- [OpenTelemetry Demo](https://opentelemetry.io/docs/demo/)
