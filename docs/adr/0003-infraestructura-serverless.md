# 3. Infraestructura Serverless Cloud con Modelo Scale-to-Zero ($0.00)

- **Status:** accepted
- **Date:** 2026-09-14

## Context

Se exige desplegar la plataforma en la nube sin incurrir en costos fijos de servidor mientras el sistema no reciba tráfico de telemetría.

## Decision

Adopción de un stack 100% Serverless Event-Driven: Render (contenedores), Upstash Kafka (bus por peticiones) y Neon.tech (PostgreSQL con auto-pausa).

## Consequences

- **Positivas:** Costo operativo de $0.00 en inactividad y autoescalado dinámico según la demanda.
- **Negativas:** Latencia adicional (cold start) en la primera petición tras periodos prolongados de inactividad.
