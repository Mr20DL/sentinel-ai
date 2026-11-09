# 7. Adopción de Langfuse para Observabilidad y Trazabilidad Distribuida

- **Status:** accepted
- **Date:** 2026-09-14

## Context
A diferencia del software tradicional determinista, depurar un motor agéntico de IA es complejo debido a que las decisiones son estocásticas. Sin herramientas especializadas de observabilidad, es imposible auditar el camino de razonamiento que tomó un agente, identificar en qué nodo específico ocurrió una latencia anormal o medir el costo financiero por uso de tokens.

## Decision
Integrar **Langfuse** (Plataforma de Observabilidad de Código Abierto para LLMs) como adaptador de salida en la capa de infraestructura:

1. **Trazabilidad Distribuida:** Cada evento de telemetría genera un `trace_id` único que rastrea la ejecución de punta a punta a través de los nodos de LangGraph.
2. **Auditoría de Razonamiento:** Se registran los prompts exactos, las respuestas intermedias, el consumo de tokens y el tiempo de ejecución por agente.
3. **Monitoreo de Costos:** Permite visualizar métricas acumuladas de latencias, errores y gastos por llamadas a modelos de IA en un panel centralizado.

## Implementation Notes
- El adaptador usa Langfuse Python SDK v5, basado en OpenTelemetry.
- `SENTINEL_OBSERVABILITY_PROVIDER=noop` es el default; `langfuse` exige
  `LANGFUSE_PUBLIC_KEY` y `LANGFUSE_SECRET_KEY`.
- `LANGFUSE_BASE_URL` tiene prioridad sobre `LANGFUSE_HOST`; si ninguno se define, se usa
  Langfuse Cloud.
- El `trace_id` del dominio se usa como semilla de `create_trace_id` para conservar la
  correlación entre la API y Langfuse.
- Cada nodo se registra como observación hija y la traza raíz se cierra al terminar la
  ejecución. Un fallo del SDK degrada el adaptador sin abortar el incidente.

## Consequences
- **Positivas:**
  - Visibilidad completa e inspección del ciclo de vida de cada decisión agéntica.
  - Capacidad para auditar costos y optimizar la latencia de cada agente individualmente.
- **Negativas:**
  - Dependencia de la disponibilidad de la plataforma externa de telemetría para la recolección de trazas.