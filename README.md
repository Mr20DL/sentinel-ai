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
- [ ] **Fase 3:** RAG y enriquecimiento de contexto
- [ ] **Fase 4:** Observabilidad y despliegue productivo

## ☁️ Despliegue gratuito

Guía paso a paso para usar Groq sin costo y publicar la API en Render Free:

[`docs/guia_llm_gratis_y_despliegue.md`](docs/guia_llm_gratis_y_despliegue.md)