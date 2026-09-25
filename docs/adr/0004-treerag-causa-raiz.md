# 4. Implementación de TreeRAG para Diagnóstico Causa-Raíz

- **Status:** accepted
- **Date:** 2026-09-14

## Context
En sistemas transaccionales con alto volumen de datos, realizar una búsqueda vectorial plana (Flat RAG) sobre millones de registros de logs pasados consume una cantidad masiva de tokens, eleva la latencia de respuesta y satura la ventana de contexto de los modelos de lenguaje con información irrelevante.

Para diagnosticar la causa-raíz de una anomalía detectada, el sistema debe consultar el historial sin leer gigabytes de logs crudos en cada ejecución.

## Decision
Implementar la técnica **TreeRAG (Hierarchical RAG)** basada en la estrategia de *Revelación Progresiva de Contexto*:

1. **Estructura Jerárquica:** Los registros e incidentes pasados se indexan en PostgreSQL (`pgvector`) estructurados en un árbol de decisión (Resúmenes Ejecutivos -> Cúmulos de Errores -> Logs Crudos).
2. **Navegación Progresiva:** El Agente de Contexto solo desciende en la jerarquía del árbol si la información del nivel superior no es suficiente para confirmar la hipótesis del fallo.
3. **Búsqueda Vectorial Eficiente:** Se ejecutan consultas por similitud de coseno únicamente sobre los nodos relevantes del árbol.

## Consequences
- **Positivas:**
  - Reducción estimada de hasta un 70% en el consumo de tokens comparado con un RAG tradicional.
  - Reducción sustancial de la latencia en el diagnóstico de causa-raíz.
- **Negativas:**
  - Proceso de ingesta e indexación inicial más complejo, requiriendo pipelines de estructuración previa de logs.