# 2. Selección de LangGraph para la Orquestación Agéntica

- **Status:** accepted
- **Date:** 2026-09-14

## Context

Se requiere orquestar el flujo entre 4 agentes especializados con capacidad de mantener estado, ejecutar ciclos de decisión y aplicar retroalimentación.

## Decision

Utilizar LangGraph (#108 en Thoughtworks Radar - Trial) para definir el grafo de estados de los agentes en Python.

## Consequences

- **Positivas:** Máquinas de estado finitas deterministas y soporte nativo para ciclos de retroalimentación (Closed-Loop).
- **Negativas:** Curva de aprendizaje para la gestión de la persistencia del estado global.
