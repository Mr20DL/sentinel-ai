# Hallazgos de la revision - Motor de dominio

**Modulo auditado:** `src/domain/nodes.py`, `src/domain/graph.py`,
`src/domain/state.py` (con impacto verificado en `src/adapters/fastapi_app.py`).

**Escenarios de referencia:** [`docs/quality_scenarios.md`](../quality_scenarios.md).

## Resumen

| ID | Severidad | Hallazgo | Escenario | Estado |
|---|---|---|---|---|
| H1 | Critica | Zero trust no detenia el flujo: un evento rechazado llegaba a diagnostico y notificacion. | QS2 | **Corregido** |
| H2 | Alta | Metricas no numericas lanzaban `ValueError` y tumbaban el grafo/API. | QS3 | **Corregido** |
| H3 | Media | La sanitizacion eliminaba Unicode legitimo (acentos, emojis) y aun asi reportaba exito. | QS1 / QS4 | **Corregido** |
| H4 | Alta | `thread_id=event-{id}` reutilizaba checkpoints y devolvia un diagnostico obsoleto. | QS5 | **Corregido** |
| H5 | Baja | Deuda de analisis estatico: imports/parametros muertos, lineas largas y `host=0.0.0.0`. | QS6 | Saneado |

---

## H1 - Zero trust no detenia el flujo (Critica)

**Evidencia antes de la correccion:** `docs/evidencia/tarea4/regresion-antes.txt`

```text
H1 sanitization_ok: False
H1 analysis_ran: True
H1 diagnosis_present: True
H1 RESULT: FAIL
```

**Causa:** `ingestion_node` calculaba `sanitization_ok`, pero el grafo tenia una arista
directa `ingestion_node -> analysis_node`. El resultado de la validacion solo se
registraba en el estado; no se usaba para decidir la transicion.

**Referencia original:** `src/domain/graph.py:54-55` (arista directa, version anterior).

**Impacto:** un payload vacio o no confiable podia generar diagnostico y enviar una
notificacion, incumpliendo ADR-0006 y el escenario QS2.

**Correccion aplicada:** se agrego `should_process` y una arista condicional despues de
la ingesta. Si `sanitization_ok` es `False`, el grafo termina en `END`.

**Referencia corregida:** `src/domain/graph.py:15-26,63-70`.

**Pruebas de regresion:**
`tests/test_graph.py::test_zero_trust_rejects_empty_payload` y
`test_conditional_routing_gates_on_sanitization`.

**Evidencia despues:** `docs/evidencia/tarea4/regresion-despues.txt`

```text
H1 sanitization_ok: False
H1 analysis_ran: False
H1 diagnosis_present: False
H1 RESULT: PASS
```

---

## H2 - Metricas no numericas rompian el analisis (Alta)

**Evidencia antes de la correccion:** `docs/evidencia/tarea4/regresion-antes.txt`

```text
H2 RESULT: FAIL (ValueError: could not convert string to float: 'high')
```

**Causa:** `analysis_node` convertia las metricas con `float(...)` sin validar el tipo:

```python
cpu = float(event.metrics.get("cpu", 0.0))
error_rate = float(event.metrics.get("error_rate", 0.0))
```

**Referencia original:** `src/domain/nodes.py:64-65` (version anterior).

**Impacto:** una integracion defectuosa podia enviar `cpu="high"`, `None`, `NaN` o
`Infinity`; la excepcion no controlada tumbaba la ejecucion y producia un `HTTP 500`.

**Correccion aplicada:** helper `_safe_metric` que convierte solo valores finitos y no
negativos, y usa `0.0` como valor seguro.

**Referencia corregida:** `src/domain/nodes.py:17-27,62-63`.

**Pruebas de regresion:** `tests/test_graph.py::test_analysis_handles_malformed_metrics`
con 4 casos parametrizados (`string-and-none`, `none-and-text`, `nan-and-inf`,
`missing-cpu`).

**Evidencia despues:** `docs/evidencia/tarea4/regresion-despues.txt`

```text
H2 RESULT: PASS
```

---

## H3 - Sanitizacion pierde Unicode legitimo (Media) - Corregido

**Evidencia antes:** `docs/evidencia/tarea4/h3-unicode-antes.txt`

```text
ok: True
note: Caracteres de control eliminados del payload de telemetría.
original: 'Informe de caída del servicio 🚨'
cleaned : 'Informe de cada del servicio '
longitud original: 31
longitud limpia : 29
```

**Causa:** `src/domain/nodes.py:30-37` (version anterior) usaba
`re.sub(r"[^\x20-\x7E]", "", ...)`, que elimina todo caracter fuera de ASCII
imprimible, no solo caracteres de control.

**Impacto:** se alteraba el contenido del incidente (`caída` -> `cada`) y se podian
perder nombres de servicios, rutas o evidencia relevante. Ademas, el evento se marcaba
como valido aunque el mensaje quedara vacio tras la limpieza y el mensaje limpio no se
aplicaba al estado.

**Correccion aplicada:** `sanitize_event` ahora usa `str.isprintable()` (conserva
acentos y emojis), devuelve el evento saneado y rechaza el payload si el mensaje limpio
queda vacio. `ingestion_node` guarda ese evento saneado en `raw_event` y lo usa para la
traza.

**Referencia corregida:** `src/domain/nodes.py:29-47,50-65`.

**Pruebas de regresion:** `tests/test_graph.py::test_sanitize_preserves_unicode`,
`test_sanitizes_control_characters` y `test_rejects_message_empty_after_sanitization`.

**Evidencia despues:** `docs/evidencia/tarea4/h3-unicode-despues.txt`

```text
unicode ok: True
original: 'Informe de caída del servicio 🚨'
sanitized: 'Informe de caída del servicio 🚨'
preserved: True
control sanitized: 'validmessage'
empty-after ok: False
```

---

## H4 - `thread_id` colisiona y devuelve diagnostico obsoleto (Alta) - Corregido

**Evidencia antes:** `docs/evidencia/tarea4/h4-thread-id-antes.txt`

```text
r1 is_anomaly: True diagnosis: True
r2 is_anomaly: False diagnosis: {'root_cause': 'Critical log level detected in payment-service', 'severity': 'critical', ...}
r2 audit_logs: 8
```

**Causa:** `src/adapters/fastapi_app.py:25` (version anterior) usaba
`thread_id=f"event-{event.id}"`. Dos eventos distintos con el mismo `id` (por ejemplo,
otro servicio o un reintento) compartian checkpoint. El segundo evento normal reutilizaba
el `raw_event`, el diagnostico y la auditoria del primero.

**Impacto:** un incidente normal podia devolver un diagnostico critico de otro servicio;
la auditoria se mezclaba y dejaba de ser confiable. Incumplia la regla de `thread_id`
unico de ADR-0002 y `AGENTS.md`.

**Correccion aplicada:** `_build_thread_id` agrega un UUID v4 a cada ejecucion
(`event-{id}-{uuid4}`), por lo que dos peticiones nunca comparten checkpoint.

**Referencia corregida:** `src/adapters/fastapi_app.py:18-19,31`.

**Prueba de regresion:** `tests/test_api.py::test_same_event_id_does_not_reuse_checkpoint`.
Reenvia el mismo `id` para `payment-service` (critico) y `checkout-service` (normal), y
verifica que la segunda respuesta no herede el diagnostico ni la auditoria.

**Evidencia despues:** `docs/evidencia/tarea4/h4-thread-id-despues.txt`

```text
r1 is_anomaly: True diagnosis: True
r2 is_anomaly: False diagnosis: None
r2 trace_id: trace-999001-checkout-service
r2 audit_logs: 3
```

---

## H5 - Deuda de analisis estatico (Baja)

**Evidencia antes:** `docs/evidencia/tarea4/antes-ruff.txt` y
`docs/evidencia/tarea4/antes-bandit.txt`.

- `ruff`: 10 errores (6 imports sin uso, 2 bloques de imports desordenados, 3 lineas
  de mas de 100 caracteres, 1 import sin uso en tests).
- `bandit`: 1 hallazgo medio, `B104` por `host="0.0.0.0"` en
  `src/adapters/fastapi_app.py:50`.
- `mypy`: sin errores con la configuracion inicial; se ajusto
  `explicit_package_bases` para evitar el falso error de modulo duplicado.

**Saneamiento aplicado:** se eliminaron imports y parametros muertos, se ordenaron los
imports, se dividieron las lineas largas, se cambio el host de desarrollo a
`127.0.0.1` y se agrego cobertura para el nodo de ingesta sin tracker.

**Evidencia despues:** `docs/evidencia/tarea4/despues-ruff.txt` (`All checks passed!`),
`despues-mypy.txt` (`Success: no issues found`) y `despues-bandit.txt` (sin hallazgos).

---

## Mejoras de robustez aplicadas

- **Degradacion controlada del tracker (ADR-0007):** `ingestion_node` y el wrapper
  `tracked` aíslan los fallos de `start_trace` y `record_step` con
  `contextlib.suppress(Exception)` (`src/domain/nodes.py:55-57`,
  `src/domain/graph.py:42-44`). Un tracker caido ya no aborta el diagnostico ni la
  notificacion. Prueba: `tests/test_graph.py::test_graph_survives_tracker_failure`.
- **Contratos tipados:** `TelemetryEvent.timestamp` es `datetime` con zona horaria
  obligatoria y `metrics` es `TelemetryMetrics`, con `cpu`/`error_rate` tolerantes y
  campos extra permitidos (`src/domain/state.py:8-31`). Pruebas:
  `test_telemetry_contract_types_timestamp_and_metrics` y
  `test_telemetry_rejects_naive_timestamp`.
