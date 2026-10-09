# Selección de Tendencias — Technology Radar Vol. 34 (abril 2026)

**Grupo 2 — Tendencias de Arquitectura de Software**

- **Curso:** Tendencias de Arquitectura de Software (202W1005) — Ciclo 2026-II, UNMSM
- **Docente:** Cordero Sánchez, Hugo R.
- **Integrantes:** Carlos Montenegro, Bruno Chochoca, Ever Avendaño, Jose Chaco
- **Fecha:** 2026-10-09

---

## 1. Contexto

El PRA del curso exige desarrollar una aplicación funcional que implemente **seis tendencias del Technology Radar** de Thoughtworks (Vol. 34, abril 2026) [1], con la siguiente distribución:

- 2 del grupo **Technologies** (en el radar el cuadrante oficial es **Techniques**)
- 2 del grupo **Tools**
- 1 del grupo **Platform**
- 1 del grupo **Language and frameworks**

> **Nota de nomenclatura:** el PRA usa "Technologies"; el cuadrante oficial del radar es **"Techniques"**. Asumimos que se refiere al mismo, y queda pendiente de confirmación con el profesor (ver `business_case.md`, sección 10).

El radar ordena las tendencias en **cuatro cuadrantes** (Techniques, Platforms, Tools, Languages & Frameworks) y **cuatro anillos** (Adopt, Trial, Assess, Caution) [1].

## 2. Selección oficial de las seis tendencias

| # | Tendencia | Cuadrante | Blip | Anillo | Evidencia en el proyecto |
|---|---|---|---|---|---|
| T1 | **Structured output from LLMs** | Techniques | 5 | **Adopt** | ADR-0005; esquemas Pydantic v2 en el estado y nodos |
| T2 | **Zero trust architecture** | Techniques | 6 | **Adopt** | ADR-0006; sanitización en `ingestion_node` como frontera de confianza |
| T3 | **Dev Containers** | Tools | 73 | Trial | ADR-0006; `devcontainer.json` (entorno reproducible) |
| T4 | **OpenCode** | Tools | 87 | Assess | ADR-0008; asistente de código con IA (requisito 4d del PRA) |
| T5 | **Langfuse** | Platforms | 46 | Trial | ADR-0007; adaptador de observabilidad y trazabilidad de LLM |
| T6 | **LangGraph** | Languages & Frameworks | 108 | Trial | ADR-0002; motor agéntico (`src/domain/graph.py`) |

### 2.1 Justificación por tendencia

**T1 — Structured output from LLMs (#5, Adopt)** [1]
La salida de los modelos de lenguaje es texto libre; en un sistema agéntico donde cada nodo alimenta al siguiente, una respuesta no estructurada rompe la tubería [2]. Por eso todo contrato del sistema (estado `AgentState`, eventos `TelemetryEvent`, diagnóstico) se define con **Pydantic v2 / JSON Schema** y la validación ocurre en la frontera del dominio (ADR-0005). Es el anillo **Adopt** del radar.

**T2 — Zero trust architecture (#6, Adopt)** [1]
Los agentes autónomos que ingieren telemetría (entrada no confiable) son vulnerables a *prompt injection* indirecta [3]. SentinelAI aplica "nunca confiar, siempre verificar": el **`ingestion_node` actúa como frontera de seguridad**, validando/limpiando el payload antes de que llegue a los agentes analíticos, y se aplica el **principio de menor privilegio** a cada adaptador (ADR-0006). Es el anillo **Adopt**.

**T3 — Dev Containers (#73, Trial)** [1]
Dev Containers definen entornos de desarrollo reproducibles y aislados vía `devcontainer.json` [4]. Además de reproducibilidad entre los 4 integrantes, el radar los destaca como ejecución aislada para agentes de IA (alineado con *Sandboxed execution for coding agents*, técnica #13). SentinelAI los usa como base del entorno (ADR-0006).

**T4 — OpenCode (#87, Assess)** [1]
OpenCode es un agente de código en terminal (categoría *Tools*, anillo *Assess*). El PRA exige **"codificar utilizando un asistente de código con IA"** (requisito 4d). Documentar **OpenCode como una de las seis tendencias** da visibilidad al requisito y deja evidencia verificable en el historial de commits del repositorio (ADR-0008).

**T5 — Langfuse (#46, Trial)** [1]
Observabilidad distribuida del motor agéntico: cada ejecución genera un `trace_id` que rastrea el paso por los nodos de LangGraph, registra prompts, respuestas intermedias, consumo de tokens y costos [2]. Se integra como adaptador de salida en hexagonal (ADR-0007). *Nota: el listado oficial lo ubica en **Trial**; su texto interno menciona "remains in Assess" — se declara Trial conforme al listado e índice del radar, y se confirma con el profesor.*

**T6 — LangGraph (#108, Trial)** [1]
Orquestador de agentes con estado: `StateGraph`, nodos, edges condicionales, reducers y checkpointers [5]. Es la base del motor (ADR-0002). El radar lo mantiene en **Trial** (dejó de ser "default" frente a enfoques más simples como Pydantic AI), pero sigue siendo la opción idónea para flujos con estado y ejecución duradera como el de SentinelAI.

## 3. Matriz tendencias ↔ requerimientos

Requerimientos derivados de `functional_context.md` y los ADRs:

- **FR1** — Ingesta inteligente: filtrar e interpretar telemetría (logs, métricas, latencias).
- **FR2** — Evaluación en tiempo real: clasificar anomalía vs. comportamiento esperado.
- **FR3** — Recuperación de antecedentes: contexto RAG de incidentes/post-mortems.
- **FR4** — Diagnóstico y recomendación: causa raíz + runbook accionable.
- **FR5** — Trazabilidad y auditoría: estado inmutable de cada decisión.
- **NFR1** — Escalabilidad elástica (cloud-native, serverless).
- **NFR2** — Costo operativo bajo (scale-to-zero).
- **NFR3** — Seguridad (menor privilegio, sanitización de entrada).
- **NFR4** — Testabilidad / mantenibilidad (arquitectura hexagonal).
- **NFR5** — Reproducibilidad del entorno de desarrollo.
- **NFR6** — Verificabilidad: salidas deterministas y validables (JSON Schema).

| | FR1 Ingesta | FR2 Anomalía | FR3 Contexto | FR4 Diagnóstico | FR5 Auditoría | NFR1 Escalar | NFR2 Costo | NFR3 Seguridad | NFR4 Testable | NFR5 Reproducible | NFR6 Verificable |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **T1 Structured output** | ● | ● | | ● | ● | | | | ● | | ● |
| **T2 Zero trust** | ● | | | | ● | | | ● | | | |
| **T3 Dev Containers** | | | | | | | | ● | ● | ● | |
| **T4 OpenCode** | | | | | | | | | | | ● |
| **T5 Langfuse** | | | | ● | ● | | | | | | ● |
| **T6 LangGraph** | | ● | ● | ● | ● | | | | | | |
| Soporte: Serverless (Upstash/Neon/Render) | | | | | | ● | ● | | | | |

Leyenda: ● = habilitador directo de la capacidad. El stack serverless de infraestructura (ADR-0003) se lista como **soporte del requisito "diseño nativo para nube" (4a del PRA)**, no como tendencia del radar.

### 3.1 Lectura de la matriz

- **T1 (Structured output)** es la tendencia transversal: asegura que FR2/FR4/FR5 produzcan contratos válidos y valide NFR6 (verificabilidad).
- **T6 (LangGraph)** habilita la orquestación FR2→FR3→FR4 y la auditoría acumulativa (FR5) mediante reducers.
- **T2 (Zero trust) y T3 (Dev Containers)** cubren los aspectos de seguridad y reproducibilidad (NFR3/NFR5) y complementan la sanitización de FR1.
- **T4 (OpenCode)** es la evidencia del requisito metodológico 4d y se alinea con la tendencia del radar.
- **T5 (Langfuse)** aporta la observabilidad de LLM (FR5) y el monitoreo de costos (NFR2 indirecto).

## 4. Alineación con la rúbrica (RA por resultado de aprendizaje)

| Resultado de aprendizaje | Cómo lo cubre esta selección |
|---|---|
| RA1 — Diseño con arquitectura + tendencias | Arquitectura Hexagonal (ADR-0001) + las 6 tendencias |
| RA2 — Cloud native (serverless / microservicios / eventos) | Stack serverless (ADR-0003) + arquitectura orientada a eventos (Kafka/Upstash) |
| RA3 — Pruebas de concepto y demos de ≥2 tendencias | Demo con OTel Demo: Structured output + LangGraph + Langfuse (trazas) |
| RA4 — Solución real con 2+ tecnologías en tendencia | LangGraph (motor funcional) + Pydantic/Structured output (contratos) implementados y probados |

---

## 5. Referencias (APA 7)

1. Thoughtworks. (2026). *Technology Radar* (Vol. 34). https://www.thoughtworks.com/content/dam/thoughtworks/documents/radar/2026/04/tr_technology_radar_vol_34_en.pdf
2. Langfuse. (s. f.). *Langfuse documentation*. https://langfuse.com/docs
3. Rose, S., Borchert, O., Mitchell, S., & Connelly, S. (2020). *Zero trust architecture* (NIST SP 800-207). National Institute of Standards and Technology. https://doi.org/10.6028/NIST.SP.800-207
4. Containers.dev. (2026). *Development Containers specification*. https://containers.dev/
5. LangChain AI. (s. f.). *LangGraph: Low-level orchestration framework for agentic AI*. https://langchain-ai.github.io/langgraph/
6. Pydantic. (s. f.). *Pydantic v2 documentation*. https://docs.pydantic.dev/