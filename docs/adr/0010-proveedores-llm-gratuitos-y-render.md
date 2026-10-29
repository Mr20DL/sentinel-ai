# 10. Proveedores LLM gratuitos compatibles con OpenAI y despliegue en Render Free

- **Status:** accepted
- **Date:** 2026-10-28

## Context

La Fase 2 ya cuenta con `DiagnosisPort`, `LangChainDiagnoser` y structured output
(ADR-0009), pero la seleccion por entorno solo permitia `heuristic`, `openai` y
`ollama`. El proyecto necesita usar un modelo real para la demo y la evidencia sin
presupuesto, y la API debe poder publicarse en la nube con costo operativo de $0.00
(ADR-0003).

Los proveedores gratuitos relevantes exponen APIs compatibles con OpenAI. Mantener un
solo adaptador basado en `langchain-openai` evita agregar SDKs por proveedor y conserva
el dominio aislado de la infraestructura.

## Decision

1. **Groq como proveedor principal:** `SENTINEL_LLM_PROVIDER=groq`, base URL
   `https://api.groq.com/openai/v1`, modelo por defecto `openai/gpt-oss-120b` y key en
   `GROQ_API_KEY`.
2. **Proveedores alternativos:** se agregan `gemini`, `openrouter` y
   `openai-compatible` con base URL y modelos configurables. `openrouter` y
   `openai-compatible` exigen `SENTINEL_LLM_MODEL` explicito.
3. **Overrides generales:** `SENTINEL_LLM_MODEL`, `SENTINEL_LLM_API_KEY`,
   `SENTINEL_LLM_BASE_URL`, `SENTINEL_LLM_STRUCTURED_METHOD`,
   `SENTINEL_LLM_TIMEOUT` y `SENTINEL_LLM_MAX_RETRIES` se resuelven en
   `src/composition.py`.
4. **Structured output configurable:** se expone el metodo
   `function_calling`/`json_mode`/`json_schema` para adaptarse a las capacidades de cada
   endpoint compatible.
5. **Fallback conservado:** si el proveedor falla, `response_node` sigue degradando al
   diagnostico heuristico y registra el evento en `audit_logs`.
6. **Tests offline por defecto:** `tests/conftest.py` fuerza `heuristic`; la prueba real
   es opt-in con `SENTINEL_LLM_INTEGRATION=1`.
7. **Despliegue:** se agrega `Dockerfile`, `.dockerignore` y `render.yaml` para Render
   Free. La key se configura como secreto en Render, nunca en el repositorio.
8. **Sin nuevas dependencias:** se reutiliza `langchain-openai` como cliente compatible
   con OpenAI.

## Consequences

- **Positivas:**
  - El sistema puede generar diagnosticos reales sin costo fijo.
  - Cambiar de proveedor gratuito requiere solo variables de entorno.
  - La suite sigue siendo reproducible sin red ni credenciales.
  - El fallback heuristico mantiene disponible la respuesta ante errores o rate limits.
  - El despliegue gratuito queda versionado y reproducible.
- **Negativas:**
  - Los free tiers tienen limites bajos y pueden cambiar sin aviso.
  - Render Free duerme el servicio y tiene arranque en frio.
  - La calidad y el soporte de structured output dependen del modelo elegido.
  - El endpoint sigue sin autenticacion; es apto para demo, no para produccion real.
  - La persistencia, el RAG y la observabilidad real siguen pendientes de Fase 3/4.

## Links

- [ADR-0003: Infraestructura serverless](0003-infraestructura-serverless.md)
- [ADR-0005: Structured output](0005-structured-output.md)
- [ADR-0009: Diagnostico con LLM](0009-llm-diagnosis-port.md)
- [Guia de LLM gratis y despliegue](../guia_llm_gratis_y_despliegue.md)
