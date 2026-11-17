# SentinelAI 🛡️🤖

Plataforma inteligente de observabilidad y resolución de incidentes agéntica basada en LangGraph, Pydantic y Arquitectura Hexagonal.

## 🏗️ Arquitectura del Sistema (Modelo C4)

### Nivel 1: Diagrama de Contexto
![C4 Context](docs/c4/Context%20Diagram%20-%20SentinelAI%20(Current).svg)

### Nivel 2: Contenedores
![C4 Containers](docs/c4/SentinelAI%20Containers%20Diagram%20(Current).svg)

### Nivel 3: Componentes (Motor Agéntico Core)
![C4 Components](docs/c4/Motor%20Ag%C3%A9ntico%20Core%20(Worker%20_%20Microservice)_%20Component%20Diagram%20(Current).svg)

## 🚀 Roadmap de Desarrollo

- [x] **Fase 1:** Core agéntico, persistencia en memoria y pruebas
- [x] **Fase 2:** Diagnóstico con LLM y structured output
- [x] **Fase 3:** RAG y enriquecimiento de contexto con Neon/pgvector y Gemini
- [x] **Fase 4:** Observabilidad y despliegue productivo
  - [x] Ingesta de logs OTel Demo con filtro, dedup y límite de eventos
  - [x] Trazabilidad real con Langfuse (`SENTINEL_OBSERVABILITY_PROVIDER=langfuse`)
  - [x] Cola QStash para desacoplar la ingesta OTLP (`SENTINEL_QUEUE_PROVIDER=qstash`)
  - [x] Dashboard operativo en `/dashboard` con refresco cada 2 segundos
  - [x] Rate limiting configurable en los endpoints públicos de ingesta
  - [x] Estado distribuido opcional con Upstash Redis para rate limit, dedup y feed
  - [x] Notificador webhook con reintentos y degradación controlada
  - [x] Autenticación opcional del dashboard con HTTP Basic
  - [x] CI con tests, cobertura, lint, tipos, seguridad estática y auditoría de dependencias

## ☁️ Despliegue gratuito

Guía paso a paso para usar Groq, Gemini Embeddings y Neon/pgvector sin costo, y publicar
la API en Render Free:

[`docs/guia_llm_gratis_y_despliegue.md`](docs/guia_llm_gratis_y_despliegue.md)