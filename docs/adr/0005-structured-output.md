# 5. Contratos de Datos mediante Structured Output (Pydantic / JSON Schema)

- **Status:** accepted
- **Date:** 2026-09-14

## Context
Los modelos de lenguaje de gran tamaño (LLMs) generan texto libre en lenguaje natural por defecto. En un sistema agéntico donde el resultado de un agente sirve como entrada para el siguiente nodo del grafo (o para la activación de un webhook de alerta), las respuestas no estructuradas causan fallos de parseo (*parsing exceptions*) y quiebran la tubería de ejecución en producción.

## Decision
Establecer el uso obligatorio de **Structured Output (Salida Estructurada)** alineado a la tendencia #5 (*Adopt*) del Thoughtworks Technology Radar:

1. **Esquemas Estrictos en Pydantic:** Se definen clases de validación en Python para las salidas de cada agente (ej. `AnomalyAnalysisOutput`, `RootCauseReport`).
2. **Garantía por JSON Schema:** Se utiliza la capacidad nativa de *Function Calling / Guided Decoding* del proveedor de LLM para forzar que las respuestas cumplan al 100% el esquema JSON esperado.
3. **Validación en los Puertos:** Cualquier payload que no cumpla la estructura es rechazado en la frontera del dominio.

## Consequences
- **Positivas:**
  - Eliminación total de errores por parseo de texto o formato inválido en los componentes del sistema.
  - Tipado estático e intellisense completo durante el desarrollo de la aplicación en Python.
- **Negativas:**
  - Requiere lógica adicional de reintentos (*fallback retries*) si el LLM falla en generar el JSON adecuado bajo restricciones severas.