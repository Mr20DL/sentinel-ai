# Tarea 4 - Evidencia de uso de IA generativa y revision de calidad

**Proyecto:** SentinelAI - plataforma de observabilidad autonoma para microservicios.

**Grupo:** 2

**Curso:** Tendencias de Arquitectura de Software (202W1005), Ciclo 2026-II, UNMSM.

**Integrantes:** Carlos Montenegro, Bruno Chochoca, Ever Avendano, Jose Chaco.

**Fecha:** 2026-10-26.

---

## 1. Resumen ejecutivo

Se audito el **motor agentico de dominio** de SentinelAI, implementado con asistencia de
OpenCode segun ADR-0008. La revision se hizo contra seis escenarios de calidad y con
analisis estatico (`ruff`, `mypy`, `bandit`) y pruebas funcionales (`pytest`).

Resultado: **5 hallazgos documentados**. Se corrigieron las 2 correcciones exigidas
(H1 y H2) y, como mejora adicional de la misma revision, H3 y H4; H5 quedo saneado. La
suite paso de 8 a **35 pruebas**, la cobertura total subio de **93% a 99%**, `ruff` paso
de 10 errores a **0**, `mypy` se mantuvo en **0** y `bandit` paso de 1 hallazgo medio a
**0**. La cifra incluye la integracion de Fase 2 (diagnostico LLM con structured output).

| Metrica | Antes | Despues |
|---|---|---|
| Pruebas | 8 PASSED | 35 PASSED |
| Cobertura total | 93% | 99% |
| Cobertura `src/domain` | 87-100% | 100% |
| `ruff check src tests` | 10 errores | 0 errores |
| `mypy src` | 0 errores | 0 errores |
| `bandit -r src -q` | 1 medio (B104) | 0 hallazgos |

## 2. Modulo auditado y evidencia de que fue escrito con IA

El modulo elegido es el motor de dominio:

- `src/domain/state.py`: contratos Pydantic v2 y estado del grafo.
- `src/domain/nodes.py`: nodos de ingesta, analisis, contexto y respuesta.
- `src/domain/graph.py`: maquina de estados LangGraph, checkpointer y routing.

La decision de usar OpenCode como asistente de codigo esta registrada en
[`docs/adr/0008-opencode-asistente-ia.md`](../adr/0008-opencode-asistente-ia.md), que
declara que el codigo del dominio, puertos, adaptadores y pruebas se desarrolla con ese
asistente. El historial Git del repositorio conserva los commits de esas iteraciones
(`git log --oneline`).

El registro de los usos de IA de esta revision esta en
[`docs/tarea4/registro_uso_ia.md`](registro_uso_ia.md): 15 filas, con 14 usos
ejecutados y 1 propuesta descartada por alcance.

## 3. Escenarios de calidad

Los seis escenarios estan en [`docs/quality_scenarios.md`](../quality_scenarios.md), con
formato de seis partes (fuente, estimulo, artefacto, entorno, respuesta y medida):

| ID | Escenario | Verificacion |
|---|---|---|
| QS1 | Clasificar correctamente un incidente critico | `tests/test_graph.py` |
| QS2 | Rechazar un evento no confiable antes del diagnostico | `test_zero_trust_rejects_empty_payload` |
| QS3 | Tolerar metricas ausentes o no numericas | `test_analysis_handles_malformed_metrics` |
| QS4 | Emitir salidas que cumplan el esquema Pydantic | `test_anomaly_path_produces_structured_diagnosis` |
| QS5 | Registrar cada nodo con un `trace_id` estable | `test_anomaly_path_runs_all_four_nodes` |
| QS6 | Pasar el analisis estatico sin errores nuevos | `ruff`, `mypy`, `bandit` |

## 4. Metodologia

### 4.1 Herramientas y versiones

```text
Python 3.12.10
pytest 9.1.1
pytest-cov 7.1.0
ruff 0.17.3
mypy 2.4.0
bandit 1.9.4
```

Las herramientas se agregaron a las dependencias `dev` de `pyproject.toml` para que la
evidencia sea reproducible con `uv`.

### 4.2 Comandos ejecutados

```powershell
$env:UV_LINK_MODE="copy"
$env:PYTHONUTF8="1"

uv sync --extra dev

# Antes de las correcciones
uv run pytest -v -p no:cacheprovider
uv run pytest --cov=src --cov-report=term-missing -p no:cacheprovider
uv run ruff check src tests
uv run mypy src
uv run bandit -r src -q

# Despues de las correcciones
uv run pytest -v -p no:cacheprovider
uv run pytest --cov=src --cov-report=term-missing -p no:cacheprovider
uv run ruff check src tests
uv run mypy src
uv run bandit -r src -q
```

Las salidas completas estan en `docs/evidencia/tarea4/`.

## 5. Hallazgos

El detalle completo, con referencias `archivo:linea`, evidencia y estado, esta en
[`docs/tarea4/hallazgos.md`](hallazgos.md).

| ID | Severidad | Hallazgo | Estado |
|---|---|---|---|
| H1 | Critica | El evento rechazado por zero trust seguia hasta diagnostico y notificacion. | Corregido |
| H2 | Alta | Metricas no numericas lanzaban `ValueError` y tumbaban el grafo/API. | Corregido |
| H3 | Media | La sanitizacion eliminaba acentos y emojis (`caída` -> `cada`). | Corregido |
| H4 | Alta | `thread_id=event-{id}` reutilizaba checkpoints y devolvia diagnostico obsoleto. | Corregido |
| H5 | Baja | Deuda de lint/seguridad: imports muertos, lineas largas y `host=0.0.0.0`. | Saneado |

### 5.1 H1 - Zero trust no detenia el flujo

**Antes:** `ingestion_node` calculaba `sanitization_ok`, pero la arista
`ingestion_node -> analysis_node` era incondicional. El evento vacio seguia hasta
`response_node` y generaba diagnostico y notificacion.

```text
H1 sanitization_ok: False
H1 analysis_ran: True
H1 diagnosis_present: True
H1 RESULT: FAIL
```

**Despues:** se agrego la funcion `should_process` y una arista condicional:

```python
def should_process(state: AgentState) -> str:
    if state.get("sanitization_ok", False):
        return "analysis_node"
    return END
```

```python
workflow.add_conditional_edges(
    "ingestion_node",
    should_process,
    {"analysis_node": "analysis_node", END: END},
)
```

**Resultado:**

```text
H1 sanitization_ok: False
H1 analysis_ran: False
H1 diagnosis_present: False
H1 RESULT: PASS
```

Evidencia: `docs/evidencia/tarea4/regresion-antes.txt` y `regresion-despues.txt`.

### 5.2 H2 - Metricas no numericas rompian el grafo

**Antes:**

```python
cpu = float(event.metrics.get("cpu", 0.0))
error_rate = float(event.metrics.get("error_rate", 0.0))
```

Con `{"cpu": "high"}` la ejecucion terminaba en
`ValueError: could not convert string to float: 'high'`.

**Despues:** se agrego `_safe_metric`, que acepta solo valores finitos y no negativos:

```python
def _safe_metric(value: float | int | str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number) or number < 0.0:
        return default
    return number
```

**Resultado:** los 4 casos malformados (`string-and-none`, `none-and-text`,
`nan-and-inf`, `missing-cpu`) pasan sin excepciones y con `anomaly_score` en `[0, 1]`.

Evidencia: `docs/evidencia/tarea4/regresion-antes.txt` y `regresion-despues.txt`.

### 5.3 H3 - Sanitizacion pierde Unicode legitimo

**Antes:** `re.sub(r"[^\x20-\x7E]", "", ...)` eliminaba acentos y emojis. La evidencia
mostraba `'Informe de caída del servicio 🚨'` convertido en
`'Informe de cada del servicio '`, y el mensaje limpio no se aplicaba al estado.

**Despues:** `sanitize_event` usa `str.isprintable()` y devuelve el evento saneado:

```python
cleaned = "".join(char for char in event.message if char.isprintable())
sanitized_event = event.model_copy(update={"message": cleaned})
if not cleaned.strip():
    return False, "Payload de telemetría vacío tras sanitización...", sanitized_event
```

`ingestion_node` guarda `sanitized_event` en `raw_event` y lo usa para la traza. Con eso
se conserva `'Informe de caída del servicio 🚨'`, se eliminan caracteres de control y se
rechaza un mensaje que queda vacio tras la limpieza.

Evidencia: `docs/evidencia/tarea4/h3-unicode-antes.txt` y `h3-unicode-despues.txt`.

### 5.4 H4 - `thread_id` colisionaba entre ejecuciones

**Antes:** `thread_id=f"event-{event.id}"` hacia que dos peticiones con el mismo `id`
compartieran checkpoint. La evidencia mostraba que un evento normal de `checkout-service`
devolvia el diagnostico critico de `payment-service` y 8 entradas de auditoria.

**Despues:** cada ejecucion agrega un UUID v4:

```python
def _build_thread_id(event: TelemetryEvent) -> str:
    return f"event-{event.id}-{uuid.uuid4().hex}"
```

La misma secuencia ahora devuelve `diagnosis: None`, `trace_id:
trace-999001-checkout-service` y 3 entradas de auditoria para el evento normal.

Evidencia: `docs/evidencia/tarea4/h4-thread-id-antes.txt` y `h4-thread-id-despues.txt`.

## 6. Pruebas funcionales y cobertura

Antes de los cambios: **8 pruebas**.

Despues: **35 pruebas** (27 nuevas):

- Rechazo zero trust antes de `analysis_node`.
- Routing condicional (`should_process` y `should_continue`).
- Metricas no numericas, nulas, `NaN`/`Infinity` y ausentes.
- Sanitizacion de caracteres de control y preservacion de Unicode (acentos y emojis).
- Rechazo de un mensaje que queda vacio tras la sanitizacion.
- Ingesta sin tracker.
- Ruta normal del nodo de respuesta.
- Checkpointer personalizado.
- `thread_id` unico: el mismo `id` no reutiliza checkpoint ni diagnostico.
- Un tracker que falla no aborta la ejecucion del incidente (ADR-0007).
- `timestamp` tipado como `datetime` con zona horaria y `metrics` como modelo Pydantic.
- Diagnostico LLM mediante `DiagnosisPort`, adaptador LangChain y structured output.
- Seleccion de proveedor por entorno (`heuristic`, `openai`, `ollama`) y fallback.

Salida final (`docs/evidencia/tarea4/despues-pytest.txt`):

```text
35 passed in 20.19s
```

Cobertura final (`docs/evidencia/tarea4/despues-cobertura.txt`):

```text
src/domain/graph.py     45 stmts    0 miss    100%
src/domain/nodes.py     91 stmts    0 miss    100%
src/domain/state.py     46 stmts    0 miss    100%
src/domain/diagnosis.py 11 stmts    0 miss    100%
TOTAL                  297 stmts    3 miss     99%
```

## 7. Analisis estatico

### 7.1 Antes

- `ruff`: 10 errores (`F401` imports sin uso, `I001` imports desordenados, `E501` lineas
  largas).
- `mypy`: 0 errores una vez configurado `explicit_package_bases = true`. Sin esa
  opcion mypy abortaba con un falso duplicado de modulo:
  `Source file found twice under different module names`.
- `bandit`: 1 hallazgo medio, `B104` por `host="0.0.0.0"`.

Evidencia: `antes-ruff.txt`, `antes-mypy.txt`, `mypy-config-inicial.txt`,
`antes-bandit.txt`.

### 7.2 Despues

```text
ruff:   All checks passed!
mypy:   Success: no issues found in 12 source files
bandit: sin hallazgos
```

Evidencia: `despues-ruff.txt`, `despues-mypy.txt`, `despues-bandit.txt`.

## 8. AGENTS.md

El archivo [`AGENTS.md`](../../AGENTS.md) define el contrato de trabajo con el asistente:

- Limites de la arquitectura hexagonal: el dominio no importa adaptadores, FastAPI ni
  SDKs de infraestructura.
- Puertos como `Protocol`; adaptadores como unicas implementaciones.
- `src/composition.py` como unico composition root.
- Contratos Pydantic v2 en `src/domain/state.py`.
- Zero trust: si `sanitization_ok` es `False`, el grafo termina antes de
  `analysis_node`.
- Reglas de LangGraph: nodos que devuelven solo su porcion de estado, efectos
  secundarios por puertos y `thread_id` unico por ejecucion.
- Comandos obligatorios de calidad y criterios de Definition of Done.
- Registro de descartes del asistente en `docs/tarea4/registro_uso_ia.md`.

## 9. Limitaciones y trabajo futuro

1. **Langfuse real:** reemplazar `NoopTracker` por el SDK de Langfuse en Fase 4.
2. **Validacion LLM:** el puerto `DiagnosisPort`, el adaptador LangChain y el fallback
   heuristico ya estan implementados; falta una prueba de integracion con credenciales
   reales u Ollama local.

## 10. Archivos del entregable

```text
AGENTS.md
docs/quality_scenarios.md
docs/tarea4/informe.md
docs/tarea4/registro_uso_ia.md
docs/tarea4/hallazgos.md
docs/evidencia/tarea4/antes-pytest.txt
docs/evidencia/tarea4/antes-cobertura.txt
docs/evidencia/tarea4/antes-ruff.txt
docs/evidencia/tarea4/antes-mypy.txt
docs/evidencia/tarea4/mypy-config-inicial.txt
docs/evidencia/tarea4/antes-bandit.txt
docs/evidencia/tarea4/despues-pytest.txt
docs/evidencia/tarea4/despues-cobertura.txt
docs/evidencia/tarea4/despues-ruff.txt
docs/evidencia/tarea4/despues-mypy.txt
docs/evidencia/tarea4/despues-bandit.txt
docs/evidencia/tarea4/regresion-antes.txt
docs/evidencia/tarea4/regresion-despues.txt
docs/evidencia/tarea4/h3-unicode-antes.txt
docs/evidencia/tarea4/h3-unicode-despues.txt
docs/evidencia/tarea4/h4-thread-id-antes.txt
docs/evidencia/tarea4/h4-thread-id-despues.txt
```

## 11. Capturas sugeridas para la presentacion

El entorno de esta revision es de terminal; las salidas de texto ya estan guardadas.
Para la exposicion se sugiere capturar:

- `docs/evidencia/tarea4/t4-agents-md.png`: `AGENTS.md` abierto en el editor.
- `docs/evidencia/tarea4/t4-pytest.png`: salida de `uv run pytest -v`.
- `docs/evidencia/tarea4/t4-ruff.png`: salida de `uv run ruff check src tests`.
- `docs/evidencia/tarea4/t4-cobertura.png`: tabla de cobertura.
- `docs/evidencia/tarea4/t4-hallazgos.png`: tabla de hallazgos del informe.

## 12. Reproducibilidad

```powershell
$env:UV_LINK_MODE="copy"
$env:PYTHONUTF8="1"

uv sync --extra dev
uv run pytest -v -p no:cacheprovider
uv run pytest --cov=src --cov-report=term-missing -p no:cacheprovider
uv run ruff check src tests
uv run mypy src
uv run bandit -r src -q
```

Todas las cifras de este informe provienen de esas ejecuciones y de los archivos de
`docs/evidencia/tarea4/`.
