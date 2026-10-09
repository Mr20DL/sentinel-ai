# 8. Selección de OpenCode como Asistente de Código con IA

- **Status:** accepted
- **Date:** 2026-10-09

## Context
El proyecto del curso (PRA) exige, en el punto 4d, **"codificar utilizando un asistente de código con IA"**. Además, el Technology Radar Vol. 34 (abril 2026) incluye a **OpenCode (#87)** dentro del cuadrante **Tools** (anillo **Assess**) por su capacidad de planear y ejecutar flujos de trabajo complejos multi-paso desde la terminal, junto a otros agentes de código como Claude Code (#67, Adopt) o Cursor (#68, Adopt).

El equipo requiere: (1) una herramienta de asistencia con IA integrada al flujo de trabajo real del repositorio, (2) evidencia verificable de su uso (historial de commits, decisiones de arquitectura documentadas), y (3) satisfacer el requisito de "Developments con asistente de código IA" sin añadir costos de licencia.

## Decision
Adoptar **OpenCode** como asistente de código con IA para el desarrollo de SentinelAI, y declararlo explícitamente como una de las **seis tendencias** del proyecto (cuadrante Tools, #87, anillo Assess):

1. **Desarrollo asistido por IA:** todo el código del dominio, puertos, adaptadores y pruebas se desarrollan con OpenCode (asistente agéntico en terminal).
2. **Evidencia verificable:** el uso queda registrado en el historial de Git del repositorio (commits, ADRs, documentación), de modo que el profesor pueda auditar el flujo de trabajo.
3. **Contraste con alternativas:** se evalúa frente a Claude Code y Cursor; se elige OpenCode por ser gratuito, agéntico, y suficiente para las tareas del curso. El radar lo sitúa en *Assess* (consolidado pero en evolución), un nivel aceptable para un proyecto académico.

## Consequences
- **Positivas:**
  - Cumple el requisito 4d del PRA ("codificar utilizando un asistente de código con IA") y añade la sexta tendencia al proyecto.
  - Acelera la implementación de las otras cinco tendencias manteniendo trazabilidad en Git.
  - Sin costo de licencia y reproducible en Dev Containers (tendencia #73).
- **Negativas:**
  - Al ser una herramienta en anillo *Assess*, su ecosistema está en evolución y algunas funcionalidades pueden variar durante el ciclo.
  - Requiere supervisión humana de sus cambios (revisión de código, pruebas) para control de calidad.