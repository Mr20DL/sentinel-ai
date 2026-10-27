# Evidencia de las Tendencias Implementadas — SentinelAI

**Grupo 2 — Tendencias de Arquitectura de Software**

- **Curso:** Tendencias de Arquitectura de Software (202W1005) — Ciclo 2026-II, UNMSM
- **Docente:** Cordero Sánchez, Hugo R.
- **Integrantes:** Carlos Montenegro, Bruno Chochoca, Ever Avendaño, Jose Chaco
- **Fecha:** 2026-10-12
- **Documento base:** [`trends_selection.md`](trends_selection.md)

---

## 0. Cómo leer este documento

Cada una de las **seis tendencias** del *Technology Radar* Vol. 34 (abril 2026) tiene su propia
sección con el mismo formato:

1. **Tendencia / blip / cuadrante / anillo.**
2. **Ubicación en el repositorio** (referencias `archivo:línea` verificables).
3. **ADR** que documenta la decisión.
4. **Comando reproducible** para generar la evidencia.
5. **Evidencia**: salida real capturada + captura(s) de pantalla a adjuntar.

> **Capturas de pantalla.** Las imágenes se guardan en la carpeta [`docs/evidencia/`](evidencia/)
> y se referencian con rutas relativas (`evidencia/nombre.png`). El equipo debe tomar cada
> captura siguiendo la sección [7. Cómo generar las capturas](#7-cómo-generar-las-capturas).
> Mientras un PNG no esté adjunto, el bloque `[captura pendiente]` indica el archivo faltante.

### Resumen

| # | Tendencia | Cuadrante | Blip | Anillo | Ubicación principal | Estado |
|---|---|---|---|---|---|---|
| T1 | Structured output from LLMs | Techniques | 5 | Adopt | `src/domain/state.py` | Implementado y probado |
| T2 | Zero trust architecture | Techniques | 6 | Adopt | `src/domain/nodes.py` | Implementado y probado |
| T3 | Dev Containers | Tools | 73 | Trial | `.devcontainer/devcontainer.json` | Configurado |
| T4 | OpenCode | Tools | 87 | Assess | ADR-0008 + historial Git | En uso |
| T5 | Langfuse | Platforms | 46 | Trial | `src/ports/observability.py`, `src/adapters/langfuse_tracker.py` | Puerto + adaptador NO-OP (SDK real en Fase 4) |
| T6 | LangGraph | Languages & Frameworks | 108 | Trial | `src/domain/graph.py` | Implementado y probado |

### Comandos base (entorno del proyecto)

```powershell
$env:UV_LINK_MODE="copy"      # evita warning de hardlink en Windows
$env:PYTHONUTF8="1"           # evita UnicodeEncodeError por emojis en consola Windows
uv sync --extra dev           # instala dependencias + pytest
uv run pytest -v              # suite completa (8 pruebas)
uv run python test_run.py     # demo del grafo (historial + diagnóstico)
```

---

## T1 — Structured output from LLMs

- **Blip:** #5 — **Cuadrante:** Techniques — **Anillo:** Adopt
- **ADR:** [`docs/adr/0005-structured-output.md`](adr/0005-structured-output.md)

### Ubicación en el repositorio

| Elemento | Referencia |
|---|---|
| Contratos del dominio (Pydantic v2) | `src/domain/state.py:7` (`TelemetryEvent`), `:17` (`AnomalyAnalysisOutput`), `:26` (`RootCauseReport`) |
| Restricciones de esquema | `src/domain/state.py:21` (`anomaly_score` con `ge=0.0, le=1.0`), `:22` (`severity` con `pattern`) |
| Validación en los puertos (FastAPI) | `src/adapters/fastapi_app.py:21` — el `POST /events` recibe un `TelemetryEvent` validado |
| Rechazo de payload inválido | `src/adapters/fastapi_app.py:22` — Pydantic devuelve `HTTP 422` |
| Prueba del contrato | `tests/test_graph.py:52` (`test_anomaly_path_produces_structured_diagnosis`) |

### Comando reproducible

```powershell
uv run pytest tests/test_graph.py::test_anomaly_path_produces_structured_diagnosis tests/test_api.py -v
```

### Evidencia

Salida real (Validación Pydantic → `HTTP 422` al enviar un payload fuera de contrato):

```text
tests/test_api.py::test_ingest_rejects_invalid_payload PASSED
tests/test_graph.py::test_anomaly_path_produces_structured_diagnosis PASSED
...
HTTP 422
{
  "detail": [
    {
      "type": "int_parsing",
      "loc": ["body", "id"],
      "msg": "Input should be a valid integer, unable to parse string as an integer",
      "input": "no-amount"
    },
    {
      "type": "missing",
      "loc": ["body", "service_name"],
      "msg": "Field required"
    }
  ]
}
```

Salida estructurada válida (`anomaly_output` y `diagnosis` cumplen el esquema al 100%):

```json
{
  "is_anomaly": true,
  "anomaly_score": 0.9,
  "severity": "critical",
  "reasoning": "Log level 'CRITICAL' is critical/high severity."
}
```

Captura de pantalla requerida:

```markdown
![T1 - Esquemas Pydantic](evidencia/t1-schemas.png)
![T1 - Prueba en verde](evidencia/t1-test.png)
```

> **Pie de figura (paper/PPT):** *Figura T1.* Contratos de datos definidos con Pydantic v2
> (`AnomalyAnalysisOutput`, `RootCauseReport`) y validación estricta en la frontera del
> dominio: un payload inválido es rechazado con `HTTP 422`.

`[capturas pendientes: evidencia/t1-schemas.png, evidencia/t1-test.png]`

---

## T2 — Zero trust architecture

- **Blip:** #6 — **Cuadrante:** Techniques — **Anillo:** Adopt
- **ADR:** [`docs/adr/0006-zero-trust-architecture.md`](adr/0006-zero-trust-architecture.md)

### Ubicación en el repositorio

| Elemento | Referencia |
|---|---|
| Frontera de confianza (`ingestion_node`) | `src/domain/nodes.py:26` (`create_ingestion_node`) |
| Sanitización y validación del payload | `src/domain/nodes.py:16` (`sanitize_event`) |
| Eliminación de caracteres de control | `src/domain/nodes.py:20` (`re.sub(r"[^\x20-\x7E]", "", event.message)`) |
| Rechazo de payload vacío | `src/domain/nodes.py:18` |
| Prueba de la frontera | `tests/test_graph.py:96` (`test_zero_trust_rejects_empty_payload`) |

### Comando reproducible

```powershell
uv run pytest tests/test_graph.py::test_zero_trust_rejects_empty_payload -v
```

### Evidencia

Salida real (el evento con payload vacío se **rechaza** en la frontera):

```text
tests/test_graph.py::test_zero_trust_rejects_empty_payload PASSED

# En ejecución, el nodo registra en la auditoría:
[IngestionNode] Payload de telemetría vacío: evento rechazado en la frontera.
# y expone sanitization_ok = False
```

Captura de pantalla requerida:

```markdown
![T2 - Frontera de confianza](evidencia/t2-sanitize.png)
![T2 - Prueba en verde](evidencia/t2-test.png)
```

> **Pie de figura (paper/PPT):** *Figura T2.* El `ingestion_node` actúa como *Trust Boundary*
> (ADR-0006): valida y sanitiza la telemetría no confiable antes de entregarla a los agentes
> analíticos ("nunca confiar, siempre verificar").

`[capturas pendientes: evidencia/t2-sanitize.png, evidencia/t2-test.png]`

---

## T3 — Dev Containers

- **Blip:** #73 — **Cuadrante:** Tools — **Anillo:** Trial
- **ADR:** [`docs/adr/0006-zero-trust-architecture.md`](adr/0006-zero-trust-architecture.md) (aislamiento)

### Ubicación en el repositorio

| Elemento | Referencia |
|---|---|
| Definición del entorno reproducible | `.devcontainer/devcontainer.json` |
| Imagen base / versión de Python | `.devcontainer/devcontainer.json:3` (`python:3.12`) |
| Instalación reproducible de dependencias | `.devcontainer/devcontainer.json:9` (`postCreateCommand: uv sync --extra dev`) |
| Extensiones estandarizadas (ruff, black, Pylance) | `.devcontainer/devcontainer.json:12` |
| Lockfile reproducible | `uv.lock` |

### Comando reproducible

```powershell
# Dentro del contenedor (VS Code > "Reopen in Container")
python --version          # -> Python 3.12.x
uv sync --extra dev       # instala el entorno exacto definido en uv.lock
uv run pytest -v
```

### Evidencia

Captura de pantalla requerida:

```markdown
![T3 - devcontainer.json](evidencia/t3-devcontainer-json.png)
![T3 - Status bar VS Code](evidencia/t3-vscode-statusbar.png)
![T3 - Entorno 3.12 y uv sync](evidencia/t3-env.png)
```

> **Pie de figura (paper/PPT):** *Figura T3.* Entorno de desarrollo aislado y 100% reproducible
> mediante `devcontainer.json`: mismo runtime (Python 3.12), mismas dependencias (`uv.lock`) y
> mismas extensiones para los cuatro integrantes.

`[capturas pendientes: evidencia/t3-devcontainer-json.png, evidencia/t3-vscode-statusbar.png, evidencia/t3-env.png]`

---

## T4 — OpenCode

- **Blip:** #87 — **Cuadrante:** Tools — **Anillo:** Assess
- **ADR:** [`docs/adr/0008-opencode-asistente-ia.md`](adr/0008-opencode-asistente-ia.md)

### Ubicación en el repositorio

| Elemento | Referencia |
|---|---|
| Decisión y justificación | `docs/adr/0008-opencode-asistente-ia.md` |
| Evidencia de uso (trazabilidad) | `git log --oneline` — commits generados durante el desarrollo asistido |
| Requisito PRA cubierto | Punto **4d** ("codificar utilizando un asistente de código con IA") |

### Comando reproducible

```powershell
git log --oneline -6
```

### Evidencia

Salida real (historial de desarrollo asistido por el agente):

```text
5a47173 feat: ports/adapters/structured-output/fastapi + tests + devcontainer + docs + ADR-0008
b409660 Documentación de tendencias, articulo, caso de negocio y primer test.
bdf2797 .
be02bed feat: definir estructura inicial del proyecto, diagramas C4 y esqueleto hexagonal
e947440 feat: estructura inicial de SentinelAI, C4 DSL y 7 ADRs
4956c68 feat: estructura inicial de SentinelAI y 7 ADRs
```

Captura de pantalla requerida:

```markdown
![T4 - Historial Git](evidencia/t4-git-log.png)
![T4 - ADR-0008](evidencia/t4-adr.png)
![T4 - Sesión OpenCode](evidencia/t4-opencode-tui.png)
```

> **Pie de figura (paper/PPT):** *Figura T4.* OpenCode como asistente de código con IA
> (cuadrante Tools, #87): el requisito metodológico 4d del PRA queda evidenciado en el
> historial de commits del repositorio y en el ADR-0008.

`[capturas pendientes: evidencia/t4-git-log.png, evidencia/t4-adr.png, evidencia/t4-opencode-tui.png]`

---

## T5 — Langfuse

- **Blip:** #46 — **Cuadrante:** Platforms — **Anillo:** Trial
- **ADR:** [`docs/adr/0007-langfuse-observabilidad.md`](adr/0007-langfuse-observabilidad.md)

### Ubicación en el repositorio

| Elemento | Referencia |
|---|---|
| Puerto de observabilidad (contrato hexagonal) | `src/ports/observability.py:4` (`ObservabilityPort`) |
| Adaptador NO-OP para desarrollo | `src/adapters/langfuse_tracker.py:4` (`NoopTracker`) |
| Adaptador real (SDK) — pendiente | `src/adapters/langfuse_tracker.py:19` (`LangfuseTracker`, Fase 4) |
| Inicio de traza por evento | `src/domain/nodes.py:30` (`tracker.start_trace(trace_id, ...)`) |
| Registro por nodo (paso a paso) | `src/domain/graph.py:26` (wrapper `tracked`) y `:30` (`record_step`) |
| Configuración de claves | `.env.example:10` (`LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST`) |

> **Alcance declarado.** La integración actual es el **puerto** (`ObservabilityPort`) más el
> **adaptador NO-OP** que registra el `trace_id` y el paso por cada nodo. La conexión con el
> SDK real de Langfuse queda planificada para la **Fase 4** (`docs/fases.md`). Se documenta de
> forma honesta como evidencia de diseño, no como integración productiva.

### Comando reproducible

```powershell
uv run python test_run.py
```

### Evidencia

Salida real (cada nodo del grafo emite su paso asociado a un `trace_id` único):

```text
=== EJECUTANDO SENTINEL-AI ===
[Langfuse:noop] start_trace=trace-1-payment-service
[Langfuse:noop] trace=trace-1-payment-service node=analysis_node
[Langfuse:noop] trace=trace-1-payment-service node=context_node
[Langfuse:noop] trace=trace-1-payment-service node=response_node
```

Captura de pantalla requerida:

```markdown
![T5 - Puerto de observabilidad](evidencia/t5-port.png)
![T5 - Adaptador NoopTracker](evidencia/t5-noop.png)
![T5 - trace_id por nodo](evidencia/t5-trace-id.png)
```

> **Pie de figura (paper/PPT):** *Figura T5.* Observabilidad como puerto hexagonal: un
> `trace_id` único acompaña cada ejecución a través de los nodos de LangGraph (ADR-0007). El
> adaptador real de Langfuse se integra en la Fase 4.

`[capturas pendientes: evidencia/t5-port.png, evidencia/t5-noop.png, evidencia/t5-trace-id.png]`

---

## T6 — LangGraph

- **Blip:** #108 — **Cuadrante:** Languages & Frameworks — **Anillo:** Trial
- **ADR:** [`docs/adr/0002-langgraph-orquestacion.md`](adr/0002-langgraph-orquestacion.md)

### Ubicación en el repositorio

| Elemento | Referencia |
|---|---|
| Grafo de estados (`StateGraph`) | `src/domain/graph.py:35` |
| Definición de nodos | `src/domain/graph.py:37` (`ingestion`, `analysis`, `context`, `response`) |
| Transición condicional (según anomalía) | `src/domain/graph.py:14` (`should_continue`) y `:44` (`add_conditional_edges`) |
| Estado compartido tipado | `src/domain/state.py:35` (`AgentState`) |
| Reducer de auditoría acumulativa | `src/domain/state.py:47` (`Annotated[list[str], operator.add]`) |
| Pruebas de las dos rutas | `tests/test_graph.py:38` (ruta anómala) y `:65` (ruta normal) |

### Comando reproducible

```powershell
uv run pytest -v
uv run python test_run.py
```

### Evidencia

Suite completa en verde (8 pruebas):

```text
tests/test_api.py::test_health_endpoint PASSED                           [ 12%]
tests/test_api.py::test_ingest_anomaly_event PASSED                      [ 25%]
tests/test_api.py::test_ingest_rejects_invalid_payload PASSED            [ 37%]
tests/test_graph.py::test_anomaly_path_runs_all_four_nodes PASSED        [ 50%]
tests/test_graph.py::test_anomaly_path_produces_structured_diagnosis PASSED [ 62%]
tests/test_graph.py::test_normal_path_ends_early_at_analysis PASSED      [ 75%]
tests/test_graph.py::test_analysis_evaluates_metrics_thresholds PASSED   [ 87%]
tests/test_graph.py::test_zero_trust_rejects_empty_payload PASSED        [100%]

============================== 8 passed in 5.45s ==============================
```

Historial de auditoría acumulado por los 4 nodos (reducer `operator.add`):

```text
📋 HISTORIAL DE AUDITORÍA (Reducers en acción):
 -> [IngestionNode] Received event from service 'payment-service'.
 -> [IngestionNode] Payload de telemetría validado y limpio.
 -> [AnalysisNode] Evaluated anomaly status: True (score: 0.90).
 -> [ContextNode] Retrieved 3 historical records for 'payment-service'.
 -> [ResponseNode] Diagnosis and recommendation generated.
```

Captura de pantalla requerida:

```markdown
![T6 - Grafo LangGraph](evidencia/t6-graph.png)
![T6 - Reducers y diagnóstico](evidencia/t6-reducers.png)
![T6 - Suite de pruebas](evidencia/t6-tests.png)
```

> **Pie de figura (paper/PPT):** *Figura T6.* Motor agéntico sobre LangGraph: `StateGraph` con
> cuatro nodos, transición condicional por *Anomaly Score* y auditoría acumulativa mediante
> reducers (ADR-0002).

`[capturas pendientes: evidencia/t6-graph.png, evidencia/t6-reducers.png, evidencia/t6-tests.png]`

---

## 7. Cómo generar las capturas

Protocolo para que las capturas sean **consistentes y verificables**:

1. Abrir el proyecto en el Dev Container (VS Code → *Reopen in Container*).
2. Ejecutar `uv sync --extra dev`.
3. Tomar las capturas de código con el número de línea visible.
4. Tomar las capturas de terminal con el comando y su salida completa visibles.
5. Guardar cada PNG en `docs/evidencia/` con **exactamente** el nombre indicado en cada
   sección (ver tabla resumen en [0](#0-cómo-leer-este-documento)).
6. Verificar que las imágenes se rendericen al abrir este documento en GitHub/VS Code.

| Captura | Comando previo | Qué debe mostrar |
|---|---|---|
| `t1-schemas.png` | — | `src/domain/state.py` líneas 17–32 (modelos Pydantic) |
| `t1-test.png` | `uv run pytest tests/test_graph.py::test_anomaly_path_produces_structured_diagnosis -v` | Prueba `PASSED` |
| `t2-sanitize.png` | — | `src/domain/nodes.py` líneas 16–42 |
| `t2-test.png` | `uv run pytest tests/test_graph.py::test_zero_trust_rejects_empty_payload -v` | Prueba `PASSED` |
| `t3-devcontainer-json.png` | — | `.devcontainer/devcontainer.json` completo |
| `t3-vscode-statusbar.png` | — | VS Code con "Dev Container: sentinel-ai" |
| `t3-env.png` | `python --version` + `uv sync --extra dev` | Python 3.12.x y sincronización OK |
| `t4-git-log.png` | `git log --oneline -6` | Historial de commits |
| `t4-adr.png` | — | `docs/adr/0008-opencode-asistente-ia.md` |
| `t4-opencode-tui.png` | — | Sesión de OpenCode en el repositorio |
| `t5-port.png` | — | `src/ports/observability.py` |
| `t5-noop.png` | — | `src/adapters/langfuse_tracker.py` |
| `t5-trace-id.png` | `uv run python test_run.py` | Líneas `[Langfuse:noop] ...` |
| `t6-graph.png` | — | `src/domain/graph.py` |
| `t6-reducers.png` | `uv run python test_run.py` | Historial de auditoría de los 4 nodos |
| `t6-tests.png` | `uv run pytest -v` | `8 passed` |

> **Nota Windows.** Si `test_run.py` falla con `UnicodeEncodeError` por los emojis, ejecutar
> antes `$env:PYTHONUTF8="1"` (ver comando base) o capturar directamente dentro del Dev
> Container Linux.

---

## 8. Referencias

1. Thoughtworks. (2026). *Technology Radar* (Vol. 34). https://www.thoughtworks.com/content/dam/thoughtworks/documents/radar/2026/04/tr_technology_radar_vol_34_en.pdf
2. Selección de tendencias del proyecto: [`docs/trends_selection.md`](trends_selection.md)
3. Registros de decisión de arquitectura: [`docs/adr/`](adr/)
4. Plan de fases: [`docs/fases.md`](fases.md)
