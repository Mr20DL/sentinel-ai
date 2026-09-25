# 1. Adopción de Arquitectura Hexagonal (Ports & Adapters)

- **Status:** accepted
- **Date:** 2026-09-14

## Context
Las aplicaciones orientadas a Inteligencia Artificial y agentes autónomos suelen sufrir de acoplamiento rígido con los SDKs de proveedores de LLMs (OpenAI, LangChain) y servicios de infraestructura (bases de datos, brokers de mensajería). En proyectos tradicionales, la lógica del negocio queda dispersa dentro de controladores HTTP o scripts de procesamiento, dificultando la ejecución de pruebas unitarias aisladas y creando una alta dependencia del proveedor (*vendor lock-in*).

Se requiere una estructura donde la lógica agéntica (la orquestación de los 4 agentes en SentinelAI) esté aislada de los detalles tecnológicos externos como bases de datos, APIs de mensajería o herramientas de observabilidad.

## Decision
Implementar **Arquitectura Hexagonal (Puertos y Adaptadores)** en la estructura del código Python:

1. **Dominio Interno (`src/domain`):** Contiene la lógica pura de los agentes autónomos (Ingesta, Analítico, Contexto y Respuesta) y el modelo del grafo. No importa ningún paquete de infraestructura externa.
2. **Puertos (`src/ports`):** Interfaces abstractas en Python (`ABC` / `Protocols`) que definen los contratos de comunicación que el dominio necesita (ej. `DatabaseRepositoryPort`, `NotificationPort`).
3. **Adaptadores (`src/adapters`):** Implementaciones concretas de la infraestructura (ej. FastAPI para HTTP, Upstash para Kafka, Neon para PostgreSQL, y Langfuse para trazabilidad).

## Consequences
- **Positivas:** 
  - **Mantenibilidad y Flexibilidad:** Permite cambiar componentes de infraestructura (ej. migrar de Neon PostgreSQL a Pinecone o Qdrant) sin modificar una sola línea de la lógica de los agentes.
  - **Testabilidad:** Se pueden realizar pruebas unitarias simulando (*mocking*) los adaptadores externos mediante los puertos definidos.
- **Negativas:**
  - Incremento en la cantidad inicial de código (*boilerplate*) para definir interfaces y mapeadores de modelos de dominio a modelos de infraestructura.