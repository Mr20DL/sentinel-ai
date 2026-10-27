# 9. Diagnóstico con LLM mediante puerto y structured output

- **Status:** accepted
- **Date:** 2026-10-26

## Context

La Fase 2 requiere reemplazar el diagnóstico mockeado de `response_node` por un LLM real.
El dominio no puede importar SDKs de proveedores ni credenciales, y la salida debe cumplir
el contrato `RootCauseReport` de Pydantic v2 (ADR-0005). La suite debe seguir ejecutándose
sin red ni API keys.

## Decision

1. **Puerto de diagnóstico:** `DiagnosisPort` en `src/ports/diagnosis.py` define
   `generate(event, analysis, historical_context) -> RootCauseReport`.
2. **Adaptador LangChain:** `LangChainDiagnoser` usa
   `ChatOpenAI.with_structured_output(RootCauseReport)` para obtener una salida validada.
   El cliente es compatible con OpenAI y con el endpoint OpenAI de Ollama.
3. **Fallback determinista:** `HeuristicDiagnoser` implementa el puerto sin red y se usa
   por defecto en desarrollo/tests. Si el proveedor falla durante un incidente,
   `response_node` degrada a un diagnóstico heurístico y registra el fallback.
4. **Selección por entorno:** `src/composition.py` lee `SENTINEL_LLM_PROVIDER`
   (`heuristic`, `openai`, `ollama`), `SENTINEL_LLM_MODEL`, `OPENAI_API_KEY`,
   `OPENAI_BASE_URL` y `OLLAMA_*`. El dominio solo recibe el puerto ya construido.
5. **Dependencia:** se agrega `langchain-openai` como adaptador de infraestructura.

## Consequences

- **Positivas:**
  - El dominio permanece aislado de LangChain/OpenAI y de `os.getenv`.
  - La salida del LLM se valida con Pydantic antes de entrar al estado.
  - Tests y demo funcionan offline con el fallback heurístico.
  - Ollama se puede usar apuntando `OLLAMA_BASE_URL` al endpoint compatible.
- **Negativas:**
  - El adaptador real agrega dependencias de LangChain/OpenAI.
  - La calidad del diagnóstico depende del modelo configurado.
  - La prueba de integración real requiere credenciales o un Ollama local; la suite
    cubre el contrato con modelos falsos.

## Links

- [ADR-0001: Arquitectura hexagonal](0001-arquitectura-hexagonal.md)
- [ADR-0005: Structured output](0005-structured-output.md)
- [ADR-0007: Observabilidad](0007-langfuse-observabilidad.md)
