# Registro de uso de IA generativa - Tarea 4

**Proyecto:** SentinelAI (Grupo 2)

**Herramienta:** OpenCode (asistente agentico en terminal)

**Modelo:** `opencode/big-pickle`

**Sesion registrada:** 2026-10-26/27, revision y correccion del motor de dominio.

**Filas:** 15, con 14 usos ejecutados y 1 propuesta descartada por alcance.

> Todos los usos de esta tabla corresponden a la sesion de trabajo de la Tarea 4 y
> fueron verificados con comandos ejecutados en el repositorio. El "prompt resumido"
> registra la instruccion que el equipo dio al asistente; en los usos 4-10 y 12-15 la
> instruccion se deriva del plan aprobado y de las acciones ejecutadas en esta sesion.
> No se reconstruyen prompts de sesiones anteriores para no inventar evidencia.

## Tabla de usos

| # | Tarea | Herramienta | Modelo | Prompt resumido | Resultado | Verificacion |
|---|---|---|---|---|---|---|
| 1 | Diagnosticar el estado del proyecto y decidir el alcance | OpenCode | `opencode/big-pickle` | "Revisa el repositorio y recomienda si conviene terminar el proyecto o hacer la Tarea 4." | Aceptado | `git status`, `git log --oneline`, lectura de `src/`, `tests/` y `docs/`; linea base de 8 tests en verde. |
| 2 | Planificar la Tarea 4 y elegir el modulo a auditar | OpenCode | `opencode/big-pickle` | "Propón un plan de 5-6 h para la Tarea 4 y selecciona un modulo auditables." | Modificado | Se acoto el alcance a solo Tarea 4 y al motor de dominio; el usuario ajusto alcance, modulo y modelo antes de aprobar. |
| 3 | Redactar escenarios de calidad | OpenCode | `opencode/big-pickle` | "Redacta 6 escenarios de calidad en formato Bass/ISO 25010 para el motor de dominio." | Modificado | `docs/quality_scenarios.md`; se descarto el escenario de rendimiento por riesgo de flakiness y se reemplazo por mantenibilidad. |
| 4 | Crear las reglas de arquitectura para el asistente | OpenCode | `opencode/big-pickle` | "Crea `AGENTS.md` con reglas hexagonales, contratos Pydantic, zero trust, LangGraph y comandos." | Aceptado | `AGENTS.md` creado; reglas alineadas con ADR-0001, ADR-0006 y ADR-0008. |
| 5 | Configurar el analisis estatico | OpenCode | `opencode/big-pickle` | "Agrega `ruff`, `mypy`, `bandit` y `pytest-cov` con configuracion reproducible." | Aceptado | `uv sync --extra dev`; dependencias y configuracion en `pyproject.toml`; `uv.lock` actualizado. |
| 6 | Ejecutar y clasificar el analisis estatico | OpenCode | `opencode/big-pickle` | "Ejecuta `ruff`, `mypy` y `bandit`; clasifica los hallazgos por severidad." | Aceptado | `docs/evidencia/tarea4/antes-ruff.txt` (10 errores), `antes-bandit.txt` (B104), `antes-mypy.txt` (sin errores). |
| 7 | Corregir H1: zero trust no detenia el flujo | OpenCode | `opencode/big-pickle` | "Implementa un gate de `sanitization_ok` antes de `analysis_node` y agrega una prueba de regresion." | Aceptado | `src/domain/graph.py:15-26,63-70`; `regresion-antes.txt` muestra FAIL y `regresion-despues.txt` muestra PASS. |
| 8 | Corregir H2: metricas no numericas rompian el grafo | OpenCode | `opencode/big-pickle` | "Implementa conversion segura de metricas y prueba con valores no numericos." | Aceptado | `src/domain/nodes.py:17-27,62-63`; antes `ValueError`, despues PASS; 4 casos parametrizados en `tests/test_graph.py`. |
| 9 | Ampliar pruebas de regresion y cobertura | OpenCode | `opencode/big-pickle` | "Agrega pruebas para routing, metricas, caracteres de control, response normal y checkpointer." | Modificado | Se descarto un test de rendimiento por flakiness; se agregaron 10 casos; 18 tests en verde en ese paso (24 al cierre) y 98% de cobertura total. |
| 10 | Redactar el informe y la evidencia | OpenCode | `opencode/big-pickle` | "Redacta el informe, los hallazgos y la tabla de usos; enlaza las salidas reales." | Aceptado | `docs/tarea4/informe.md`, `docs/tarea4/hallazgos.md` y este registro; enlaces a `docs/evidencia/tarea4/`. |
| 11 | Actualizar `README.md` y `docs/fases.md` con el estado de la Tarea 4 | OpenCode | `opencode/big-pickle` | "Actualiza el README y el plan de fases para reflejar la Tarea 4." | Descartado | El alcance aprobado fue solo Tarea 4; no se modifico `README.md` ni `docs/fases.md`. |
| 12 | Corregir H4: `thread_id` unico por ejecucion | OpenCode | `opencode/big-pickle` | "Haz unico el `thread_id` por ejecucion y agrega una prueba con el mismo `id` para dos servicios." | Aceptado | `src/adapters/fastapi_app.py:18-19,31`; `test_same_event_id_does_not_reuse_checkpoint`; `h4-thread-id-despues.txt` muestra `diagnosis: None` y 3 logs. |
| 13 | Corregir H3: preservar Unicode y aplicar el mensaje saneado | OpenCode | `opencode/big-pickle` | "Corrige la sanitizacion para preservar acentos y emojis, y rechaza el evento si el mensaje queda vacio." | Aceptado | `src/domain/nodes.py:29-65`; `test_sanitize_preserves_unicode`, `test_rejects_message_empty_after_sanitization`; `h3-unicode-despues.txt`. |
| 14 | Aislar fallos del tracker de observabilidad | OpenCode | `opencode/big-pickle` | "Haz que un fallo de `start_trace` o `record_step` no aborte la respuesta del incidente (ADR-0007)." | Aceptado | `src/domain/nodes.py:55-57`, `src/domain/graph.py:42-44`; `test_graph_survives_tracker_failure`; 24 tests en verde. |
| 15 | Tipar `timestamp` y `metrics` | OpenCode | `opencode/big-pickle` | "Tipa `timestamp` como `datetime` con zona horaria y `metrics` con un modelo Pydantic tolerante." | Aceptado | `src/domain/state.py:8-31`; `test_telemetry_contract_types_timestamp_and_metrics`, `test_telemetry_rejects_naive_timestamp`. |

## Descartes y ajustes registrados

- **Escenario de rendimiento (uso 3):** se descarto porque una prueba de latencia local
  puede ser inestable en Windows y no aportaba evidencia confiable al alcance de la
  tarea. Se reemplazo por un escenario de mantenibilidad verificable con `ruff`/`mypy`.
- **Prueba de rendimiento (uso 9):** mismo motivo; se priorizaron pruebas funcionales
  deterministas de routing, metricas y contrato.
- **Actualizacion de `README.md` y `docs/fases.md`:** se difirio porque el alcance
  aprobado fue solo Tarea 4; no se modifico documentacion fuera del entregable.
- **Correccion de H3 y H4:** se difirio inicialmente para no mezclar correcciones de
  alcance amplio (Unicode y `thread_id`) con las dos correcciones exigidas; al cerrar
  H1/H2 se implementaron y verificaron en los usos 12 y 13.

## Verificacion global

```powershell
uv run pytest -v -p no:cacheprovider
uv run pytest --cov=src --cov-report=term-missing -p no:cacheprovider
uv run ruff check src tests
uv run mypy src
uv run bandit -r src -q
```

Resultado final: **24 tests PASSED**, cobertura **98%**, `ruff` sin errores, `mypy`
sin errores y `bandit` sin hallazgos.
