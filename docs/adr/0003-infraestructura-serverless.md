# 3. Infraestructura Serverless Cloud con Modelo Scale-to-Zero ($0.00)

- **Status:** accepted
- **Date:** 2026-09-14
- **Nota (2026-10-09):** Este ADR documenta el **soporte del requisito "diseño nativo para nube" (punto 4a del PRA)**. El stack descrito (Render, Upstash Kafka, Neon PostgreSQL) **no corresponde a un ítem con nombre del Technology Radar Vol. 34**, por lo que **no cuenta como una de las seis tendencias** del proyecto. Las seis tendencias se listan en `docs/trends_selection.md`.

## Context
Para el despliegue de SentinelAI en un entorno académico y de desarrollo inicial, no se cuenta con presupuesto para mantener servidores dedicados o clústeres de Kubernetes (EKS/GKE) activos las 24 horas del día. Sin embargo, el sistema debe ser capaz de procesar eventos en tiempo real mediante arquitectura orientada a eventos (*Event-Driven*).

Se requiere una arquitectura de infraestructura cloud que escale a cero cuando no haya flujo de telemetría entrante, eliminando los costos fijos mensuales.

## Decision
Adoptar un stack de infraestructura **100% Serverless Cloud con costo operativo inicial de $0.00**:

1. **API Gateway & Workers (Render):** Micro-contenedores despliegan la API FastAPI y los workers de Python, escalando a 0 instancias tras periodos de inactividad.
2. **Bus de Eventos (Upstash Kafka):** Plataforma de mensajería Kafka Serverless que cobra únicamente por petición procesada (HTTP/REST Kafka API), sin costo por clúster encendido.
3. **Base de Datos (Neon.tech PostgreSQL):** PostgreSQL serverless que soporta pausa automática (*auto-suspend*) de cómputo cuando no recibe consultas.

## Consequences
- **Positivas:**
  - Costo fijo mensual garantizado de $0.00 en periodos de inactividad.
  - Escalabilidad elástica automática cuando se incrementa el volumen de eventos de telemetría.
- **Negativas:**
  - Latencia adicional (*Cold Start*) en la primera petición enviada tras un periodo prolongado de inactividad del sistema.