# Guía del Artículo de Investigación (Tipo Paper Técnico)

**Grupo 2 — Tendencias de Arquitectura de Software (202W1005), Ciclo 2026-II, UNMSM**

Requisitos del PRA (punto 7):
> "Presentar el artículo de investigación en la semana 16 como máximo, con el desarrollo de una de las tendencias implementadas en su proyecto. El artículo es individual. El formato es tipo paper técnico. Debe incluir las correcciones y ajustes indicados en las exposiciones, si hubiese."

---

## 1. Asignación de tendencia por integrante

| Integrante | Tendencia (blip Vol. 34) | Cuadrante / Anillo |
|---|---|---|
| Carlos Montenegro | **LangGraph (#108)** — orquestación agéntica | Languages & Frameworks / Trial |
| Bruno Chochoca | **Structured output from LLMs (#5)** | Techniques / Adopt |
| Ever Avendaño | **Langfuse (#46)** — observabilidad de LLM | Platforms / Trial |
| Jose Chaco | **Zero trust architecture (#6)** | Techniques / Adopt |

> Cada artículo desarrolla **una** tendencia implementada en SentinelAI. Cita el código real (`src/domain/`, `src/adapters/`, `src/ports/`), los ADRs y, si corresponde, los resultados de las pruebas.

## 2. Estructura del paper técnico (plantilla sugerida)

1. **Título** (informativo y específico) y autores.
2. **Resumen (≤200 palabras):** problema, objetivo, método, resultados, conclusión. Sin citas.
3. **Palabras clave** (3–5).
4. **Introducción:** contexto del sector (fintech/pagos), el problema (tormentas de alertas/MTTR), motivación, y por qué la tendencia elegida lo ataca. Enunciar contribución.
5. **Trabajo relacionado / marco conceptual:** estado del arte de la tendencia (qué dice el Technology Radar, para qué sirve, alternativas, limitaciones).
6. **Metodología:** cómo se implementó en SentinelAI (arquitectura hexagonal, dónde vive el código, decisiones de diseño/ADR). Incluir fragmento o diagrama.
7. **Implementación / resultados:** lo que se logró, con evidencia reproducible (salida de `test_run.py`, trazas, esquemas). Tabla de resultados si aplica.
8. **Discusión:** pros/contras, limitaciones, oportunidades (en base al caso de negocio y KPIs).
9. **Conclusiones y trabajo futuro.**
10. **Referencias (APA 7).**

## 3. Reglas básicas de citación APA 7

- Cita en el texto: `(Thoughtworks, 2026)` o `Thoughtworks (2026)`. Con 2 autores: `(Rose & Borchert, 2020)`; con 3+: `(Rose et al., 2020)`.
- Lista de referencias: orden alfabético, sangría francesa, solo iniciales de nombre.
- Libro: Apellido, N. (Año). *Título*. Editorial. DOI/URL
- Informe/PDF: Autor. (Año). *Título* [reporte]. Organización. URL
- Artículo web: Autor. (Año, Mes día). *Título del artículo*. Sitio. URL
- Fuentes sin fecha: `(s. f.)`.

## 4. Referencias base por integrante

**Carlos Montenegro — LangGraph:**
- ADR-0002; `src/domain/graph.py`, `src/domain/nodes.py`, `src/domain/state.py`
- LangChain AI. (s. f.). *LangGraph* [documentación]. https://langchain-ai.github.io/langgraph/
- Thoughtworks. (2026). *Technology Radar* (Vol. 34), blip #108.
- Chen, Z., Kang, Y., et al. (2020). *Understanding and handling alert storm for online service systems*, ICSE-Companion. https://doi.org/10.1145/3377812.3390809
- Bass, L., Clements, P., & Kazman, R. (2013). *Software architecture in practice* (3.ª ed.). Addison-Wesley.

**Bruno Chochoca — Structured output:**
- ADR-0005; `src/domain/state.py` (TelemetryEvent, AgentState)
- Pydantic. (s. f.). *Pydantic v2* [documentación]. https://docs.pydantic.dev/
- Thoughtworks. (2026). *Technology Radar*, blip #5 (Adopt).
- Richards, M., & Ford, N. (2020). *Fundamentals of software architecture*. O'Reilly.

**Ever Avendaño — Langfuse:**
- ADR-0007; `src/adapters/langfuse_tracker.py`
- Langfuse. (s. f.). *Langfuse documentation*. https://langfuse.com/docs
- Thoughtworks. (2026). *Technology Radar*, blip #46.
- Informe NeuBird (2026) para métricas de observabilidad/MTTR. https://assets.ctfassets.net/jdtwqhzvc2n1/1L65zWJm1D3elsD2Yaeo6T/fc9a23041a967a94848f9afa88047e06/State-of-Production-Reliability-and-AI-Adoption.pdf

**Jose Chaco — Zero trust:**
- ADR-0006; `src/domain/nodes.py` (ingestion_node como frontera de confianza)
- Rose, S., Borchert, O., Mitchell, S., & Connelly, S. (2020). *Zero trust architecture* (NIST SP 800-207). https://doi.org/10.6028/NIST.SP.800-207
- Thoughtworks. (2026). *Technology Radar*, blip #6.
- Containers.dev. (2026). *Development Containers specification*. https://containers.dev/

> Referencias adicionales del sílabo (bibliografía del curso): Nick Tune & Jean-Georges Perrin (2024); Sam Newman (2021); Neal Ford et al. (2021); JJ Geewax (2021).

## 5. Recordatorios del PRA

1. **Semana 16 como máximo** para entregar el artículo (individual).
2. Debe **incluir las correcciones y ajustes** indicados en las exposiciones parcial/final.
3. El artículo profundiza **una** tendencia implementada; si un integrante cambia de tema, debe documentarlo (evita duplicados).
4. Formato **paper técnico**: objetivo, método, resultados y conclusiones, no un ensayo descriptivo.

## 6. Cronograma sugerido

| Semana | Entregable |
|---|---|
| Parte (semana 8) | Definir título, resumen y referencias base |
| Avance (semana 10–12) | Introducción + trabajo relacionado (2–3 págs.) |
| Avance (semana 14) | Metodología + implementación + resultados |
| Semana 15 | Versión completa + revisión compañeros |
| Semana 16 | Entrega final (incluye correcciones de exposiciones) |