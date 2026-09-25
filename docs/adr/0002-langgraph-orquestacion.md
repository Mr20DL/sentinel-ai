# 2. Selección de LangGraph para la Orquestación Agéntica

- **Status:** accepted
- **Date:** 2026-09-14

## Context
Los sistemas agénticos simples utilizan flujos secuenciales y lineales conocidos como DAGs (*Directed Acyclic Graphs*). Sin embargo, SentinelAI exige coordinar 4 agentes con roles diferenciados que requieren loops de retroalimentación (*Closed-Loop*), evaluación de estados condicionales y persistencia de contexto compartido durante el diagnóstico de una anomalía.

Las cadenas lineales tradicionales no permiten volver a ejecutar un agente analítico si la evaluación de causa-raíz arroja un falso positivo o requiere una re-evaluación de los datos.

## Decision
Utilizar **LangGraph** (marco de trabajo para orquestación de agentes con estado) para construir el núcleo agéntico:

1. **Grafo de Estados (`StateGraph`):** Se define un estado compartido fuertemente tipado mediante Pydantic/TypedDict que fluye a través del grafo.
2. **Nodos Ciclicos:** Cada agente representa un nodo del grafo. LangGraph permite transiciones condicionales (ej. si el *Anomaly Score* es menor a 0.75, el flujo se detiene; si es mayor, escala automáticamente al Agente de Contexto).
3. **Persistencia y Checkpoints:** Permite pausar, inspeccionar o revertir estados durante la ejecución del análisis en tiempo real.

## Consequences
- **Positivas:**
  - Control determinista sobre el comportamiento no determinista de los LLMs.
  - Capacidad nativa de implementar ciclos de re-intento y corrección autónoma (*Closed-Loop*).
- **Negativas:**
  - Curva de aprendizaje técnica más elevada para la gestión adecuada de la memoria compartida (*State*) y mitigación de bucles infinitos en el grafo.