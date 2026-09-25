# 6. Aplicación de Zero Trust Architecture y Aislamiento

- **Status:** accepted
- **Date:** 2026-09-14

## Context
Los agentes autónomos que procesan entradas no estructuradas (como logs de servidores o llamadas API externas) son vulnerables a ataques de **Inyección Indirecta de Prompts (Indirect Prompt Injection)**, donde un atacante oculta instrucciones dentro de los datos de telemetría para manipular el razonamiento de la IA o acceder a credenciales internas.

Asimismo, las diferencias en los entornos de desarrollo locales de los integrantes del equipo generan fallos por desalineación de versiones de software.

## Decision
Adoptar los principios de **Zero Trust Architecture (Arquitectura de Cero Confianza)** y Aislamiento:

1. **Sanitización de Ingesta:** El Agente de Ingesta actúa como frontera de seguridad (*Trust Boundary*), validando y limpiando cualquier payload de entrada antes de ser procesado por los agentes analíticos.
2. **Principio de Menor Privilegio:** Cada servicio y adaptador cuenta con claves de API independientes con permisos mínimos necesarios (ej. la API de ingesta solo tiene permisos de escritura en Kafka, no de lectura en PostgreSQL).
3. **Aislamiento en Dev Containers:** Utilizar VS Code Dev Containers (#73 en Radar) para encapsular las dependencias, herramientas y versiones exactas de runtime en contenedores Docker estandarizados para todo el equipo.

## Consequences
- **Positivas:**
  - Alta protección frente a inyecciones de código o prompts maliciosos en la telemetría.
  - Reproducibilidad garantizada del entorno de desarrollo entre los miembros del equipo.
- **Negativas:**
  - Complejidad en la gestión de credenciales y secretos de entorno en desarrollo local.