# AGENTS.md - Reglas de arquitectura para asistentes de IA

Este archivo define el contrato de trabajo entre el equipo de SentinelAI y cualquier
asistente de codigo con IA (OpenCode, Claude Code, Cursor, Copilot, etc.). El asistente
debe leerlo antes de proponer o aplicar cambios.

## 1. Contexto del proyecto

SentinelAI es una plataforma de observabilidad autonoma para microservicios. Ingiere
telemetria, detecta anomalias, recupera incidentes historicos y genera un diagnostico
con runbook. El motor agentico se implementa con LangGraph y sigue arquitectura
hexagonal. Las decisiones de arquitectura viven en `docs/adr/`.

## 2. Stack y restricciones tecnicas

- Python 3.12+, gestionado con `uv`.
- LangGraph para la maquina de estados; Pydantic v2 para contratos.
- FastAPI para la frontera HTTP.
- SQLite/Neon PostgreSQL para persistencia futura; Langfuse para observabilidad.
- No agregar dependencias nuevas sin justificarlo y, si cambia una decision de
  arquitectura, registrar un ADR en `docs/adr/`.

## 3. Estructura y responsabilidades

```text
src/
  domain/        # Modelo, nodos y grafo. Reglas de negocio puras.
  ports/         # Protocolos (interfaces) que el dominio necesita.
  adapters/      # Implementaciones concretas de los puertos.
  composition.py # Composition root: unico lugar que ensambla adaptadores.
tests/           # Pruebas unitarias y funcionales con pytest.
docs/            # Documentacion, ADRs, escenarios de calidad y evidencia.
```

## 4. Reglas de dependencia (hexagonal)

- `src/domain/` **no** puede importar `src/adapters/`, `fastapi`, `langfuse`,
  `psycopg`, `os.getenv` ni ningun SDK de infraestructura.
- `src/ports/` solo contiene `Protocol` y docstrings; no contiene implementaciones.
- `src/adapters/` implementa los puertos. Puede usar SDKs, red o disco, pero no debe
  contener reglas de negocio.
- `src/composition.py` es el unico modulo que instancia adaptadores y los inyecta.
- `src/adapters/fastapi_app.py` solo traduce HTTP a casos de uso; no implementa logica
  de diagnostico.
- Si un cambio exige romper una flecha de dependencia, detente y propone un ADR.

## 5. Contratos y validacion

- Todo dato que cruza una frontera (HTTP, base de datos, cola) se valida con un modelo
  Pydantic v2 en `src/domain/state.py`.
- No pasar `dict` crudos entre nodos si existe un modelo; usar `model_dump()` solo en
  la frontera de salida.
- `severity` solo admite `critical`, `major`, `minor` u `ok`.
- `anomaly_score` debe estar en el rango `[0.0, 1.0]`.
- Las metricas (`cpu`, `error_rate`) se leen con conversion segura: un valor ausente,
  nulo o no numerico no debe lanzar una excepcion ni tumbar el grafo.

## 6. Zero trust y seguridad

- `ingestion_node` es la frontera de confianza (ADR-0006): valida y sanitiza el evento.
- Si `sanitization_ok` es `False`, el grafo debe terminar antes de `analysis_node`.
  Un evento rechazado nunca debe llegar a diagnostico ni a notificacion.
- No registrar secretos, tokens ni payloads completos en logs o auditoria.
- Las credenciales se leen de variables de entorno y jamas se escriben en el repo;
  usar `.env.example` como plantilla.

## 7. Reglas para LangGraph

- Cada nodo devuelve solo la porcion de estado que modifica (no el estado completo).
- Los nodos no mutan estado global ni comparten objetos mutables entre ejecuciones.
- Los efectos secundarios (notificar, persistir, trazar) pasan por puertos inyectados.
- Las transiciones condicionales se declaran de forma explicita y con nombres claros.
- `thread_id` debe ser unico por ejecucion (incluir servicio/entorno/timestamp o UUID);
  no reutilizar `event-{id}` entre servicios o reintentos.
- Los tests deben usar un `thread_id` distinto por prueba para evitar checkpoints
  compartidos.

## 8. Observabilidad y auditoria

- Cada nodo agrega entradas a `audit_logs` mediante el reducer `operator.add`.
- `trace_id` debe mantenerse estable durante toda la ejecucion.
- Un fallo del tracker de observabilidad no debe abortar la respuesta al incidente;
  el adaptador debe degradar de forma controlada.

## 9. Pruebas y calidad

- Framework: `pytest`. No introducir otro framework sin ADR.
- Toda correccion de un hallazgo debe incluir una prueba de regresion que falle antes
  y pase despues.
- Cubrir rutas de anomalia, ruta normal, rechazo zero trust y entradas malformadas.
- No depender del orden de ejecucion ni de estado compartido entre pruebas.
- Comandos obligatorios antes de cerrar un cambio:

```powershell
uv sync --extra dev
uv run pytest -v
uv run pytest --cov=src --cov-report=term-missing
uv run ruff check src tests
uv run mypy src
uv run bandit -r src -q
```

En Windows, si aparecen errores de encoding o hardlinks:

```powershell
$env:UV_LINK_MODE = "copy"
$env:PYTHONUTF8 = "1"
```

## 10. Convenciones de codigo y documentacion

- Codigo, nombres de funciones y comentarios tecnicos: ingles.
- Documentacion de usuario, ADRs, escenarios y evidencia: espanol.
- Formato: `ruff format`/`ruff check`; lineas de hasta 100 caracteres.
- No editar `.venv/`, `uv.lock` a mano ni archivos generados.
- No dejar imports, parametros o funciones muertas.
- Mantener los diagramas C4 y los ADRs sincronizados con el codigo.

## 11. Reglas especificas para el asistente de IA

1. Leer `AGENTS.md`, `docs/adr/index.md` y los archivos del modulo afectado antes de
   proponer cambios.
2. Declarar el plan y los archivos que se van a tocar antes de editar.
3. Respetar los limites de la seccion 4; no importar infraestructura desde el dominio.
4. No inventar APIs, credenciales ni resultados de pruebas. Toda evidencia debe salir
   de un comando ejecutado en el repositorio.
5. Ejecutar la suite y el analisis estatico despues de cada cambio funcional.
6. Si una sugerencia del asistente se descarta o modifica, registrar el motivo en
   `docs/tarea4/registro_uso_ia.md`.
7. No hacer commit, push ni crear PR sin autorizacion explicita del equipo.
8. Reportar hallazgos con referencia `archivo:linea` y severidad.

## 12. Definition of Done

Un cambio se considera terminado cuando:

- [ ] La suite `pytest` pasa completa.
- [ ] `ruff` y `mypy` no reportan errores nuevos (o quedan documentados).
- [ ] La cobertura no disminuye respecto de la linea base.
- [ ] Existe prueba de regresion para cada correccion funcional.
- [ ] La documentacion/ADR correspondiente esta actualizada.
- [ ] No hay secretos ni datos sensibles en el diff.
