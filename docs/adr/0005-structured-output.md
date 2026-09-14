# 5. Contratos de Datos mediante Structured Output (Pydantic / JSON Schema)

- **Status:** accepted
- **Date:** 2026-09-14

## Context

Los modelos de lenguaje producen texto no estructurado que puede romper la comunicación entre microservicios o nodos del grafo.

## Decision

Exigir respuestas con Structured Output (#5 en Thoughtworks Radar - Adopt) tipadas mediante Pydantic y JSON Schema.

## Consequences

- **Positivas:** Inmunidad a errores de parseo en producción y validación estricta de entradas/salidas.
- **Negativas:** Necesidad de gestionar reintentos automáticos si el LLM no cumple la estructura.
