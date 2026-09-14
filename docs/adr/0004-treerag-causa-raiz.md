# 4. Implementación de TreeRAG para Diagnóstico Causa-Raíz

- **Status:** accepted
- **Date:** 2026-09-14

## Context

Consultar la base de datos completa de logs pasados en cada evento anómalo incrementa la latencia y los costos por token.

## Decision

Implementar TreeRAG (Hierarchical RAG) y Revelación Progresiva de Contexto sobre Neon PostgreSQL.

## Consequences

- **Positivas:** Reducción estimada del 70% en el consumo de tokens y análisis de causa-raíz localizado.
- **Negativas:** Complejidad en la indexación jerárquica de los logs históricos.
