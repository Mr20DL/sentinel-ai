1. Contexto Funcional de SentinelAI
   SentinelAI es una plataforma de observabilidad autónoma diseñada para detectar, diagnosticar y responder ante anomalías operativas en arquitecturas de microservicios distribuidos de alto volumen.

Problema que resuelve
En entornos de alto tráfico, los sistemas tradicionales de monitoreo generan cientos de alertas simultáneas (tormentas de alertas) cuando ocurre un fallo en cadena. Los ingenieros de SRE (Site Reliability Engineering) pierden minutos críticos filtrando logs ruidosos manualmente para encontrar la causa raíz.

Propuesta de Valor
SentinelAI actúa como un primer respondedor de Nivel 1 (L1 SRE) autónomo:

Ingesta Inteligente: Filtra e interpreta eventos de telemetría (logs, métricas de CPU/memoria, latencias de API).

Evaluación de Anormalidades: Clasifica en tiempo real si el evento constituye una anomalía real o un comportamiento esperado.

Recuperación de Antecedentes (RAG): Busca automáticamente en la base de conocimientos post-mortems e incidentes pasados similares.

Diagnóstico & Recomendación: Genera un análisis de causa raíz respaldado por evidencia y propone un plan de acción (runbook) inmediato.

Trazabilidad & Auditoría: Registra cada paso del proceso de decisión en un estado inmutable para auditoría y retroalimentación humana.
