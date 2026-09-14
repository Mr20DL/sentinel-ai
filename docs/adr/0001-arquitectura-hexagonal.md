# 1. Adopción de Arquitectura Hexagonal (Ports & Adapters)

- **Status:** accepted
- **Date:** 2026-09-14

## Context

Las plataformas de IA tienden a acoplar la lógica de los agentes con los SDKs de los proveedores de LLMs e infraestructura, dificultando el mantenimiento y las pruebas unitarias.

## Decision

Implementar Arquitectura Hexagonal aislando el Core de Dominio (los 4 agentes en LangGraph) de los proveedores externos mediante Puertos e Interfaces.

## Consequences

- **Positivas:** Alta mantenibilidad, testabilidad desacoplada y capacidad de cambiar de proveedor de base de datos o broker sin tocar la lógica agéntica.
- **Negativas:** Ligero incremento en la cantidad de código inicial (boilerplate).
