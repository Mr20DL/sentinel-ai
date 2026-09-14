# 6. Aplicación de Zero Trust Architecture y Aislamiento

- **Status:** accepted
- **Date:** 2026-09-14

## Context

Los agentes autónomos ejecutan herramientas y consultas que podrían ser vulneradas mediante inyecciones de datos o payloads maliciosos.

## Decision

Restringir permisos por token de API (#6 en Radar - Adopt), sanitizar entradas en el Agente de Ingesta y aislar el entorno en Dev Containers (#73 en Radar - Trial).

## Consequences

- **Positivas:** Mitigación de elevación de privilegios y entorno reproducible para todo el equipo.
- **Negativas:** Gestión individual de secretos y credenciales por cada servicio.
