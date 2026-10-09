Plan de Desarrollo por Fases: SentinelAI
┌─────────────────────────────────────────────────────────────────────────┐
│  Fase 1: Core Agentic Engine & Persistence                             │
│  • Memory Checkpointers (MemorySaver / PostgresSaver)                   │
│  • Tests unitarios e integración (Pytest + LangGraph test kit)          │
│  • Validación robusta de esquemas (Pydantic V2)                        │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Fase 2: LLM Integration & Structured Output                            │
│  • Integración de modelos con LangChain (OpenAI / Ollama / Anthropic)   │
│  • Generación de diagnósticos estructurados (PydanticOutputParser)      │
│  • Prompt engineering para análisis de causa raíz                       │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Fase 3: RAG & Context Enrichment                                       │
│  • Recuperación de logs históricos y métricas (ChromaDB / Vector Store) │
│  • Búsqueda de incidentes similares para enriquecer `context_node`      │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Fase 4: Observability & Production Readiness                           │
│  • Instrumentación con OpenTelemetry (métricas y trazas por nodo)       │
│  • Exposición de API REST / WebSockets mediante FastAPI                 │
│  • Empaquetado y ejecución con Docker / `uv`                            │
└─────────────────────────────────────────────────────────────────────────┘
Detalles de cada Fase
Fase 1: Persistencia, Memoria y Pruebas (Base Estable)
  Objetivo: Asegurar la confiabilidad de la máquina de estados y permitir pausar/reanudar ejecuciones (human-in-the-loop si fuera necesario).

   Entregables:

   Incorporar MemorySaver / checkpointers de LangGraph para guardar el estado por thread_id.

   Suite de pruebas unitarias (tests/test_graph.py) con pytest que valide:

   Ruta con anomalía (ejecución completa de los 4 nodos).

   Ruta normal (corte temprano en analysis_node hacia END).

Fase 2: Razonamiento LLM y Respuestas Estructuradas
  Objetivo: Reemplazar las respuestas mockeadas de response_node por inferencias reales basadas en modelos de lenguaje.

   Entregables:

   Integración de ChatOpenAI / ChatOllama / ChatAnthropic.

   Estructuración rígida de la salida (JSON schema para causa raíz, nivel de severidad y runbook sugerido).

Fase 3: Enriquecimiento de Contexto (RAG / Vector Store)
  Objetivo: Hacer que context_node sea verdaderamente inteligente buscando post-mortems e incidentes pasados.

   Entregables:

   Almacenamiento vectorial (ej. ChromaDB) cargado con documentación técnica y logs históricos.

   Búsqueda por similitud semántica según el mensaje del evento.

Fase 4: Observabilidad y Despliegue
  Objetivo: Preparar el agente para entornos distribuidos y monitoreo en tiempo real.

   Entregables:

   Traza distribuida de cada nodo con OpenTelemetry / LangSmith.

   Endpoint en FastAPI para ingerir telemetría vía Webhook / HTTP POST.