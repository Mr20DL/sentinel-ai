# 7. Adopción de Langfuse para Observabilidad y Trazabilidad Distribuida

- **Status:** accepted
- **Date:** 2026-09-14

## Context

Se requiere auditar el comportamiento interno de los agentes, medir latencias por nodo y controlar los costos por token ejecutado.

## Decision

Integrar Langfuse (#46 en Thoughtworks Radar - Assess) mediante un adaptador de salida para registrar trazas completas de las decisiones de IA.

## Consequences

- **Positivas:** Transparencia total del razonamiento agéntico y control preciso del consumo de tokens.
- **Negativas:** Dependencia de un servicio de telemetría externo.
