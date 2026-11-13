# 13. Cola QStash para desacoplar la ingesta OTLP

- **Status:** accepted
- **Date:** 2026-11-13
- **Deciders:** Equipo SentinelAI

## Context

La ingesta OTLP de OpenTelemetry Demo normaliza y procesa cada evento dentro del mismo
request HTTP (`ADR-0012`). Ese diseno funciona para la demo local, pero mantiene acoplada
la recepcion de telemetria con la ejecucion del grafo agentico y con las llamadas al LLM.
Una tormenta de errores puede agotar la cuota del proveedor o bloquear la respuesta al
Collector.

El `ADR-0003` preveia Upstash Kafka como bus de eventos. Sin embargo, Upstash
descontinuo Kafka y sus conectores el 11 de marzo de 2025; ya no es una opcion vigente
para el despliegue. Render Free tampoco es un buen host para un consumidor Kafka
persistente, porque duerme el servicio tras periodos de inactividad.

## Decision

1. **Puerto de cola:** `src/ports/queue.py` define `TelemetryQueuePort` con `publish`,
   `verify_signature` e `is_remote`. El dominio sigue sin conocer QStash ni HTTP.
2. **Modo inline por defecto:** `InlineTelemetryQueue` procesa el evento en el mismo request
   para desarrollo local y tests, preservando el comportamiento previo sin red.
3. **QStash en produccion:** `QStashTelemetryQueue` usa el SDK oficial `qstash` para
   publicar cada `TelemetryEvent` en un endpoint publico de SentinelAI.
4. **Worker HTTP:** QStash entrega en `POST /internal/otel/process`. El endpoint valida
   la firma `Upstash-Signature` con las claves de firma actual y siguiente, y usa la URL
   configurada como destino para verificar el claim `sub`.
5. **Ingesta asincrona:** `POST /ingest/otel/v1/logs` normaliza, deduplica y publica los
   eventos. La respuesta informa `accepted`, `queued` y `failed`; ya no espera el
   diagnostico del grafo.
6. **Configuracion:** `SENTINEL_QUEUE_PROVIDER=inline|qstash`. El modo `qstash` exige
   `QSTASH_TOKEN`, `SENTINEL_OTEL_WORKER_URL`, `QSTASH_CURRENT_SIGNING_KEY` y
   `QSTASH_NEXT_SIGNING_KEY`. `QSTASH_URL` permite fijar la region.
7. **Semantica de entrega:** QStash reintenta hasta 3 veces y aplica deduplicacion por
   `event.id` durante su ventana de deduplicacion. La entrega es at-least-once; el
   procesamiento debe tolerar duplicados.

## Considered Options

- **QStash (elegido):** cola HTTP push con reintentos y DLQ. No requiere worker
  persistente y encaja con Render Free. No implementa semantica Kafka.
- **Upstash Kafka:** descartado porque el servicio fue discontinuado en 2025.
- **Aiven Kafka Free:** mantiene Kafka real, pero exige un consumidor persistente y
  agrega operacion que Render Free no ofrece de forma natural.
- **Solo cola en memoria:** suficiente para tests, pero no desacopla procesos ni
  sobrevive a reinicios.

## Consequences

- **Positivas:**
  - La API responde al Collector sin ejecutar el grafo ni consumir cuota de LLM.
  - QStash reintenta entregas fallidas y conserva mensajes en su DLQ.
  - El diseno sigue siendo serverless y compatible con scale-to-zero.
  - La firma del webhook evita que terceros invoquen el worker interno.
- **Negativas:**
  - QStash no ofrece semantica Kafka; el nombre "Kafka" del roadmap queda obsoleto.
  - El plan gratuito limita a 1.000 entregas por dia (los reintentos cuentan) y 1 MB por
    mensaje.
  - El worker requiere una URL publica accesible por QStash.
  - La entrega es at-least-once y el orden no esta garantizado entre eventos.
  - Sin configuracion de QStash, el modo `inline` sigue procesando en el request.

## Links

- [ADR-0001: Arquitectura hexagonal](0001-arquitectura-hexagonal.md)
- [ADR-0003: Infraestructura serverless](0003-infraestructura-serverless.md)
- [ADR-0012: Ingesta OTLP](0012-ingesta-opentelemetry-demo.md)
- [Documentacion de QStash](https://upstash.com/docs/qstash)
- [Verificacion de firmas QStash](https://upstash.com/docs/qstash/howto/signature)
