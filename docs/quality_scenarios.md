# Escenarios de calidad - SentinelAI

**Modulo auditado:** motor agentico de dominio (`src/domain/nodes.py`,
`src/domain/graph.py`, `src/domain/state.py`).

**Metodo:** escenarios en seis partes (Bass, Clements & Kazman, *Software Architecture
in Practice*), alineados con los atributos de ISO/IEC 25010. Cada escenario tiene una
medida verificable con pruebas funcionales o analisis estatico.

## Resumen

| ID | Atributo (ISO 25010) | Escenario | Verificacion |
|---|---|---|---|
| QS1 | Adecuacion funcional | Clasificar correctamente un incidente critico | `tests/test_graph.py` |
| QS2 | Seguridad | Rechazar un evento no confiable antes del diagnostico | `tests/test_graph.py` |
| QS3 | Fiabilidad / robustez | Tolerar metricas ausentes o no numericas | `tests/test_graph.py` |
| QS4 | Adecuacion funcional / contrato | Emitir salidas que cumplan el esquema Pydantic | `tests/test_graph.py` |
| QS5 | Trazabilidad / auditabilidad | Registrar cada nodo con un `trace_id` estable | `tests/test_graph.py` |
| QS6 | Mantenibilidad | Pasar el analisis estatico sin errores nuevos | `ruff`, `mypy`, `bandit` |

---

## QS1 - Correctitud de la clasificacion

- **Fuente:** operador SRE que consume la alerta.
- **Estimulo:** evento con `log_level="CRITICAL"`, `cpu=95.5` y `error_rate=0.45`.
- **Artefacto:** grafo compilado (`create_sentinel_graph`).
- **Entorno:** ejecucion normal, sin fallos de infraestructura.
- **Respuesta:** el grafo marca `is_anomaly=True`, asigna `severity="critical"` y
  genera un `RootCauseReport` con al menos un paso de runbook.
- **Medida de respuesta:** 100% de los casos criticos de la suite producen diagnostico
  y `notification_sent=True`; 0 falsos negativos en los casos de prueba.

## QS2 - Zero trust en la frontera de ingesta

- **Fuente:** integracion no confiable o payload manipulado.
- **Estimulo:** evento con `service_name` vacio, `message` vacio o caracteres de control.
- **Artefacto:** `ingestion_node` y las transiciones del grafo.
- **Entorno:** ejecucion normal.
- **Respuesta:** `sanitization_ok=False`; el grafo termina **antes** de `analysis_node`;
  no se ejecuta diagnostico, no se recupera contexto y no se notifica.
- **Medida de respuesta:** 0 ejecuciones de `analysis_node`, `context_node` y
  `response_node` para eventos rechazados; 100% de los payloads invalidos rechazados.

## QS3 - Robustez ante metricas malformadas

- **Fuente:** integracion de telemetria defectuosa.
- **Estimulo:** `metrics` con `cpu="high"`, `cpu=None`, `error_rate="N/A"` o ausente.
- **Artefacto:** `analysis_node`.
- **Entorno:** ejecucion normal.
- **Respuesta:** el nodo no lanza excepciones; usa un valor seguro por defecto (0.0),
  mantiene `anomaly_score` en `[0.0, 1.0]` y devuelve una salida estructurada valida.
- **Medida de respuesta:** 0 excepciones no controladas y 100% de los casos malformados
  procesados con una salida valida.

## QS4 - Contrato de salida estructurada

- **Fuente:** consumidor de la API o del estado del grafo.
- **Estimulo:** evento de anomalia procesado por el grafo.
- **Artefacto:** `AnomalyAnalysisOutput`, `RootCauseReport` y respuesta HTTP.
- **Entorno:** ejecucion normal.
- **Respuesta:** las salidas validan con Pydantic v2; `severity` pertenece al conjunto
  permitido y `anomaly_score` esta en `[0.0, 1.0]`.
- **Medida de respuesta:** 100% de las salidas validan sin `ValidationError`; 0 valores
  fuera de rango.

## QS5 - Trazabilidad y auditoria

- **Fuente:** auditor o ingeniero que investiga un incidente.
- **Estimulo:** evento de anomalia procesado por el grafo.
- **Artefacto:** `AgentState.audit_logs` y `trace_id`.
- **Entorno:** ejecucion normal.
- **Respuesta:** cada nodo ejecutado agrega su entrada de auditoria y todas comparten el
  mismo `trace_id`. Si el adaptador de observabilidad falla, la respuesta al incidente
  continua (ADR-0007).
- **Medida de respuesta:** 4 entradas (ingesta, analisis, contexto, respuesta) para la
  ruta de anomalia; 1 `trace_id` estable; 0 nodos sin registro; 0 respuestas abortadas
  por fallos del tracker.

## QS6 - Mantenibilidad y analisis estatico

- **Fuente:** equipo de desarrollo / pipeline de calidad.
- **Estimulo:** ejecucion de `ruff`, `mypy` y `bandit` sobre `src/` y `tests/`.
- **Artefacto:** codigo fuente del dominio, puertos y adaptadores.
- **Entorno:** entorno local reproducible con `uv`.
- **Respuesta:** no hay errores nuevos de lint/tipado ni hallazgos de seguridad de
  severidad alta; no quedan imports ni parametros muertos.
- **Medida de respuesta:** 0 errores de `ruff` y `mypy`; 0 hallazgos de `bandit`;
  cobertura igual o superior a la linea base.

---

## Trazabilidad escenario -> hallazgo

| Hallazgo | Escenario afectado | Estado |
|---|---|---|
| H1: zero trust no corta el flujo | QS2 | Corregido |
| H2: metricas no numericas rompen el analisis | QS3 | Corregido |
| H3: sanitizacion elimina Unicode legitimo | QS1 / QS4 | Corregido |
| H4: `thread_id` colisiona entre ejecuciones | QS5 | Corregido |
| H5: imports/parametros muertos, lineas largas y host inseguro | QS6 | Saneado |

La evidencia de ejecucion vive en `docs/tarea4/informe.md` y en
`docs/evidencia/tarea4/`. Las mejoras posteriores de robustez (tracker y contratos)
estan documentadas en `docs/tarea4/hallazgos.md`.
