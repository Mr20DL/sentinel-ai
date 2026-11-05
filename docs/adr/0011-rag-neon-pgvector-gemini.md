# 11. RAG con Neon PostgreSQL, pgvector y embeddings de Gemini

- **Status:** accepted
- **Date:** 2026-11-02
- **Deciders:** Equipo SentinelAI

## Context

La Fase 3 requiere reemplazar `InMemoryRepository`, que devuelve incidentes de ejemplo
fijos, por una recuperacion semantica real sobre incidentes historicos. El dominio ya
depende del puerto `IncidentRepositoryPort`, pero la implementacion actual no persiste
datos ni usa el mensaje del evento para buscar antecedentes.

La solucion debe funcionar en Render Free, con 512 MB de RAM y sin costo. El diagnostico
sigue usando Groq, pero Groq no ofrece embeddings. Se necesita un proveedor de embeddings
o un modelo local dentro del contenedor.

## Decision

1. **Puerto de embeddings:** `EmbeddingPort` en `src/ports/embeddings.py` define
   `dimensions`, `embed_documents(texts)` y `embed_query(text)`.
2. **Adaptador Gemini:** `GeminiEmbeddingAdapter` usa la REST API de Gemini con
   `gemini-embedding-2` y `outputDimensionality=384`. Como este modelo no admite
   `task_type`, se antepone `task: search result | query: ...` para consultas y
   `title: none | text: ...` para documentos. La API key se envia en `x-goog-api-key`,
   nunca en la URL.
3. **Persistencia:** `PostgresIncidentRepository` implementa el puerto con Neon
   PostgreSQL y la extension `pgvector`. La tabla `incidents` guarda
   `service_name`, `summary` y `embedding vector(384)`, con un indice HNSW para
   similitud coseno y un indice por servicio.
4. **Busqueda:** `context_node` envia `event.service_name` y `event.message` al puerto.
   El adaptador vectoriza la consulta y devuelve los `limit` incidentes mas similares
   del mismo servicio.
5. **Seed:** `scripts/seed_incidents.py` crea el esquema y carga los incidentes de
   `InMemoryRepository.DEFAULT_INCIDENTS` con `ON CONFLICT` para poder ejecutarlo varias
   veces.
6. **Seleccion por entorno:** `composition.py` usa PostgreSQL solo cuando existen
   `DATABASE_URL` y `SENTINEL_EMBEDDING_PROVIDER=gemini`. Sin esas variables conserva
   `InMemoryRepository` para desarrollo y tests.
7. **Degradacion controlada:** si la busqueda falla, `context_node` continua sin
   contexto historico y registra el fallo en `audit_logs`; el diagnostico no se aborta.

## Considered Options

- **Gemini Embeddings API:** embeddings de alta calidad, bajo consumo de memoria en
  Render y free tier sin costo. Requiere API key, red y aceptar las condiciones del
  free tier.
- **FastEmbed local:** sin API key ni cuotas, pero agrega un modelo ONNX y consumo de
  RAM al contenedor de 512 MB. Se deja como posible adaptador futuro del mismo puerto.
- **Solo busqueda por palabra clave:** no requiere embeddings, pero no cumple RAG
  semantico real.

## Consequences

- **Positivas:**
  - Los incidentes historicos persisten en Neon y sobreviven a reinicios de Render.
  - `context_node` recupera incidentes por similitud semantica, no solo por servicio.
  - El dominio permanece aislado de Gemini y PostgreSQL mediante puertos.
  - El consumo de memoria en Render se mantiene bajo.
- **Negativas:**
  - El free tier de Gemini tiene cuotas y puede usar los datos para mejorar productos.
  - La busqueda depende de red y de una API key.
  - Cambiar de modelo o de dimensiones exige reindexar los incidentes.
  - El seed es un paso operativo explicito y no se ejecuta en cada arranque.
  - FastEmbed local queda pendiente como fallback offline.

## Links

- [ADR-0003: Infraestructura serverless](0003-infraestructura-serverless.md)
- [ADR-0006: Zero trust](0006-zero-trust-architecture.md)
- [ADR-0009: Puerto de diagnostico LLM](0009-llm-diagnosis-port.md)
- [ADR-0010: Proveedores LLM gratuitos y Render](0010-proveedores-llm-gratuitos-y-render.md)
- [Guia de despliegue](../guia_llm_gratis_y_despliegue.md)
