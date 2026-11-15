# Arquitectura del sistema

SentinelAI combina Arquitectura Hexagonal (puertos y adaptadores) con una máquina de
estados agéntica implementada en LangGraph. El dominio contiene las reglas de negocio y
no conoce FastAPI, QStash, Neon, Langfuse ni ningún SDK de infraestructura.

## 1. Vista de capas

```text
+----------------------------------------------------------------------------------+
|                            ADAPTADORES DE ENTRADA                                |
|  FastAPI (/events, /ingest/otel, /internal/otel, /dashboard)                     |
|  OtelLogNormalizer | SlidingWindowRateLimiter | dashboard.html                    |
+----------------------------------------+-----------------------------------------+
                                         |
                                         v
+----------------------------------------------------------------------------------+
|                              DOMINIO (src/domain)                                |
|                                                                                  |
|  state.py: TelemetryEvent, AnomalyAnalysisOutput, RootCauseReport, EventSnapshot  |
|  graph.py: StateGraph + MemorySaver + enrutamiento condicional                    |
|  nodes.py: ingestion -> analysis -> context -> response                           |
|  diagnosis.py: reportes heuristicos de respaldo                                   |
+----------------------------------------+-----------------------------------------+
                                         |
                                         v
+----------------------------------------------------------------------------------+
|                            PUERTOS (src/ports)                                   |
|  DiagnosisPort | EmbeddingPort | EventFeedPort | IncidentRepositoryPort           |
|  NotifierPort | ObservabilityPort | TelemetryQueuePort                            |
+----------------------------------------+-----------------------------------------+
                                         |
                                         v
+----------------------------------------------------------------------------------+
|                          ADAPTADORES DE SALIDA                                   |
|  HeuristicDiagnoser / LangChainDiagnoser                                          |
|  GeminiEmbeddingAdapter                                                           |
|  InMemoryRepository / PostgresIncidentRepository                                  |
|  ConsoleNotifier                                                                  |
|  NoopTracker / LangfuseTracker                                                    |
|  InlineTelemetryQueue / QStashTelemetryQueue                                      |
|  InMemoryEventFeed                                                                |
+----------------------------------------------------------------------------------+
```

`src/composition.py` es el composition root: selecciona adaptadores según variables de
entorno y los inyecta en el grafo. `src/adapters/fastapi_app.py` solo traduce HTTP a casos
de uso.

## 2. Grafo agéntico

```text
[ingestion_node] --(sanitization_ok?)--> [analysis_node] --(is_anomaly?)--> [context_node]
       |                                      |                                  |
      (no)                                   (no)                               v
       v                                      v                           [response_node]
      END                                    END                                  |
                                                                                 v
                                                                                END
```

- `ingestion_node` es la frontera Zero Trust (`ADR-0006`): valida y sanitiza el evento.
  Si `sanitization_ok` es `False`, el grafo termina sin diagnóstico ni notificación.
- `analysis_node` calcula la anomalía con nivel de log y umbrales de CPU/error rate.
- `context_node` recupera incidentes históricos mediante `IncidentRepositoryPort`; si el
  repositorio falla, continúa sin RAG y lo registra en `audit_logs`.
- `response_node` genera el diagnóstico con `DiagnosisPort`, aplica fallback heurístico y
  notifica por `NotifierPort`.
- Cada nodo devuelve solo la porción de estado que modifica. `audit_logs` usa el reducer
  `operator.add`; `trace_id` se mantiene estable durante la ejecución.
- `thread_id` es único por ejecución (`event-{id}-{uuid}`) para evitar checkpoints
  compartidos.

## 3. Puertos y adaptadores

| Puerto | Contrato | Adaptadores |
|---|---|---|
| `DiagnosisPort` | Genera `RootCauseReport` | `HeuristicDiagnoser`, `LangChainDiagnoser` |
| `EmbeddingPort` | Embeddings de documentos y consultas | `GeminiEmbeddingAdapter` |
| `IncidentRepositoryPort` | Recupera incidentes históricos | `InMemoryRepository`, `PostgresIncidentRepository` |
| `NotifierPort` | Envía notificaciones operativas | `ConsoleNotifier` |
| `ObservabilityPort` | Traza inicio, pasos y fin de ejecución | `NoopTracker`, `LangfuseTracker` |
| `TelemetryQueuePort` | Publica eventos OTLP y valida firmas | `InlineTelemetryQueue`, `QStashTelemetryQueue` |
| `EventFeedPort` | Conserva y consulta los últimos eventos | `InMemoryEventFeed` |

## 4. Rutas HTTP

| Ruta | Método | Responsabilidad |
|---|---|---|
| `/` | GET | Metadatos del servicio y enlaces a rutas |
| `/health` | GET | Health check para Render |
| `/events` | POST | Procesa un `TelemetryEvent` en el grafo |
| `/ingest/otel/v1/logs` | POST | Normaliza logs OTLP y los publica en la cola |
| `/internal/otel/process` | POST | Worker de QStash con validación de firma |
| `/dashboard` | GET | Página HTML del dashboard operativo |
| `/dashboard/events` | GET | Últimos `EventSnapshot` en JSON |
| `/docs` | GET | OpenAPI generado por FastAPI |

Controles de seguridad:

- `/events` y `/ingest/otel/v1/logs` aceptan `SENTINEL_INGEST_API_KEY` y exigen
  `X-Ingest-Key` cuando la variable está definida.
- Ambos endpoints aplican rate limiting deslizante por cliente cuando
  `SENTINEL_RATE_LIMIT_PER_MINUTE` es mayor que cero (`ADR-0015`).
- `/internal/otel/process` valida `Upstash-Signature` con las signing keys de QStash y la
  URL pública configurada; solo existe cuando la cola remota está activa.

## 5. Flujos principales

### Ingesta directa

```text
Cliente -> POST /events -> _process_event -> grafo -> EventFeed -> respuesta JSON
```

### Ingesta OTLP en modo inline

```text
OTel Collector -> POST /ingest/otel/v1/logs -> OtelLogNormalizer
  -> InlineTelemetryQueue -> _process_event -> grafo -> EventFeed
```

### Ingesta OTLP con QStash

```text
OTel Collector -> POST /ingest/otel/v1/logs -> OtelLogNormalizer
  -> QStashTelemetryQueue -> Upstash QStash
  -> POST /internal/otel/process -> verificación de firma
  -> _process_event -> grafo -> EventFeed
```

La entrega de QStash es at-least-once y sin orden garantizado; el procesamiento debe
tolerar duplicados. El modo `inline` es el default local.

### Dashboard

```text
Navegador -> GET /dashboard -> dashboard.html
  -> GET /dashboard/events?limit=50 cada 2 segundos -> EventFeed
```

El feed conserva 100 eventos por defecto (`SENTINEL_DASHBOARD_MAX_EVENTS`) y se pierde al
reiniciar el proceso (`ADR-0014`).

## 6. Persistencia y estado

| Dato | Implementación por defecto | Opción de infraestructura |
|---|---|---|
| Checkpoints del grafo | `MemorySaver` | Persistencia distribuida pendiente |
| Incidentes históricos | `InMemoryRepository` | Neon PostgreSQL + pgvector |
| Embeddings | Deshabilitados | Gemini Embeddings |
| Feed del dashboard | `InMemoryEventFeed` | Almacenamiento compartido pendiente |
| Rate limiting | En memoria por proceso | Redis o gateway dedicado |
| Cola OTLP | `InlineTelemetryQueue` | Upstash QStash |
| Trazas | `NoopTracker` | Langfuse Cloud |
| Diagnóstico | `HeuristicDiagnoser` | Groq, Gemini, OpenRouter, OpenAI, Ollama |

Si `DATABASE_URL` está configurado, `build_repository()` exige
`SENTINEL_EMBEDDING_PROVIDER=gemini` y construye `PostgresIncidentRepository`.

## 7. Despliegue

- La API se empaqueta con Docker y se despliega en Render Free; el health check es
  `/health` y el puerto se toma de `PORT` (8080 por defecto).
- Render puede dormir por inactividad y arrancar en frío.
- Los proveedores de LLM, embeddings, base de datos, observabilidad y cola se seleccionan
  por variables de entorno; las credenciales nunca se escriben en el repositorio.
- `render.yaml` deja `SENTINEL_QUEUE_PROVIDER=inline` y los proveedores opcionales
  desactivados hasta configurar secretos.

## 8. Reglas de dependencia

- `src/domain/` no importa `src/adapters/`, FastAPI, `langfuse`, `psycopg`, `os.getenv`
  ni SDKs de infraestructura.
- `src/ports/` solo contiene `Protocol` y docstrings; no tiene implementaciones.
- `src/adapters/` implementa puertos y puede usar red, disco o SDKs, pero no contiene
  reglas de negocio.
- `src/composition.py` es el único módulo que instancia adaptadores y los inyecta.
- Los efectos secundarios (notificar, persistir, trazar, encolar) pasan por puertos.

## 9. Límites actuales y evolución

- La ingesta OTLP del MVP procesa solo logs; métricas y trazas quedan para una iteración
  posterior.
- El dashboard, el rate limiter y el feed son por proceso: no se comparten entre
  instancias y se reinician con el despliegue.
- El dashboard es de solo lectura y no tiene autenticación de usuarios.
- El rate limiting confía en `X-Forwarded-For` detrás del proxy de Render; si la API se
  expone directamente, se necesita un gateway o Redis.
- Para tiempo real estricto o multi-instancia se evaluará SSE/WebSocket y almacenamiento
  compartido.

## 10. Decisiones relacionadas

- [ADR-0001: Arquitectura hexagonal](adr/0001-arquitectura-hexagonal.md)
- [ADR-0003: Infraestructura serverless](adr/0003-infraestructura-serverless.md)
- [ADR-0006: Zero trust en la ingesta](adr/0006-zero-trust-architecture.md)
- [ADR-0009: Diagnóstico con LLM](adr/0009-llm-diagnosis-port.md)
- [ADR-0012: Ingesta OTLP](adr/0012-ingesta-opentelemetry-demo.md)
- [ADR-0013: Cola QStash](adr/0013-cola-qstash-ingesta-otel.md)
- [ADR-0014: Dashboard operativo](adr/0014-dashboard-tiempo-real.md)
- [ADR-0015: Rate limiting de ingesta](adr/0015-rate-limiting-ingesta.md)
