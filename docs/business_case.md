# Caso de Negocio — SentinelAI

**Grupo 2 — Tendencias de Arquitectura de Software**

- **Curso:** Tendencias de Arquitectura de Software (202W1005)
- **Escuela:** Ingeniería de Software — UNMSM (Ciclo 2026-II)
- **Docente:** Cordero Sánchez, Hugo R.
- **Integrantes:**
  - Carlos Montenegro
  - Bruno Chochoca
  - Ever Avendaño
  - Jose Chaco
- **Versión:** 0.1 (2026-10-09)
- **Estado de validación con el profesor:** pendiente

---

## 1. Resumen ejecutivo

SentinelAI es una plataforma de observabilidad autónoma que actúa como **primer respondedor de nivel 1 (L1 SRE)** en sistemas transaccionales de alto tráfico. Está orientada al sector **fintech / procesamiento de pagos**, donde el costo de una caída se mide en **pérdida directa de ingresos por minuto**.

El caso de negocio se plantea como un **escenario de referencia académica** (no se simula ni se declara un cliente real), sustentado en **estudios de industria documentados** sobre costo de caídas, fatiga de alertas y MTTR. Esto cumple el requisito del PRA de atender una *problemática real* sin inventar contactos ni datos falsos: el problema (tormentas de alertas, MTTR alto, alertas no accionables) está ampliamente documentado, y los datos de telemetría provienen de software de referencia de código abierto (OpenTelemetry Demo).

## 2. Contexto del sector

Los procesadores de pago operan con arquitecturas de microservicios de alto volumen: auth, checkout, ledger, anti-fraude, notificaciones, etc. Un fallo en cadena (`cascade failure`) dispara cientos de alertas simultáneas — una **tormenta de alertas** — que sepultan la señal real sobre el ruido [1][2].

En este contexto, una caída de los servicios de pago **no se manifiesta solo como indisponibilidad**: cada minuto de caída implica transacciones fallidas, carritos abandonados, multas regulatorias y daño reputacional [3][4].

## 3. Problemática real

### 3.1 Problema operativo

- **Tormentas de alertas:** cuando un servicio aguas abajo falla, cientos de microservicios reportan errores simultáneamente [1]. Los estudios de 2026 indican que **57% de las organizaciones reciben más de 70% de alertas no accionables**, y **63% de los equipos SRE reportan que menos de la mitad de sus alertas son accionables** [5][6].
- **Fatiga de alertas → incidentes reales:** la fatiga alerta es hoy el **mayor reto operativo** para los equipos SRE [6]. El **44% de las organizaciones** sufrió en el último año una caída vinculada a una alerta ignorada o suprimida [5].
- **MTTR alto:** el **58%** de las organizaciones reporta un MTTR de 30 minutos a 2 horas, y **26%** supera las 2 horas [5]. En industrias de infraestructura (donde fallan varios sistemas en cascada), la mediana llega a **3.1–3.8 horas** [7].
- **Detección tardía:** cerca del **40% de los incidentes son descubiertos por los clientes antes que por el monitoreo** [5].
- **Costo de talento:** los equipos dedican **40% o más de su tiempo** a gestión de incidentes en lugar de innovación, y 36% invierte 5–10 horas semanales en post-mortems [5].

### 3.2 Impacto financiero (referencias de industria)

| Fuente | Hallazgo |
|---|---|
| Gartner (2014), citado por Atlassian | ~**USD 5 600 por minuto** de caída como promedio de industria [8] |
| Ponemon Institute / Vertiv (2016) | Promedio real: **~USD 9 000 por minuto**; incidencia promedio cercana a **USD 740 000** [9] |
| EMA / BigPanda (2024) | Promedio de **USD 14 056 por minuto** de caída no planificada [10] |
| SafeCharge / WBR Digital | **72%** de comercios perdió entre **€10 000 y €100 000 por caída** [11] |
| NeuBird (2026) | **61%** de las organizaciones estima una hora de caída en **USD 50 000+** [5] |
| Forbes Tech Council (2024) | Caídas en sistemas de pago **>USD 400 mil millones de ingresos anuales** a nivel global [4] |

> Nota: las cifras son de estudios de terceros y varían por vertical y tamaño. Se usan como **referencia para parametrizar los KPIs** del escenario, no como datos propios de una empresa determinada.

## 4. Caso de negocio (escenario de referencia)

Se define un **procesador de pagos de referencia** (del tipo pasarela de pagos latinoamericana) con la siguiente arquitectura indicativa:

- **Microservicios:** `auth-service`, `checkout-service`, `payment-service`, `ledger-service`, `anti-fraud-service`, `notification-service`.
- **Volumen:** 100 transacciones por segundo en hora pico (ticket promedio USD 85; comisión 2.0% por transacción).
- **Acuerdo de nivel de servicio:** 99.99% de disponibilidad objetivo (≈ 4 minutos de caída al mes).

### 4.1 Supuestos explícitos del modelo

Los supuestos son **declarados** (no se presentan como datos reales de una empresa):

1. Volumen promedio de 100 TPS durante la ventana del incidente (análogo al ejemplo publicado por IR [3]).
2. Incidente típico de pago: **210 minutos** de indisponibilidad completa del `payment-service`.
3. Ticket promedio USD 85 y comisión promedio 2.0% [3][4].

### 4.2 Estimación del impacto directo (ilustrativa)

- **Transacciones no procesadas:** 100 TPS × 12 600 s = **1 260 000 transacciones**.
- **Ingresos perdidos por comisiones:** 1 260 000 × USD 85 × 2.0% ≈ **USD 2,14 millones por incidente** (antes de multas, costos de ingeniería y daño reputacional).

Con un costo de industria de **USD 5 600–9 000 por minuto** [8][9], un incidente de 210 minutos representa **USD 1,18M–1,89M** solo en costo de caída, coherente con el cálculo por volumen. Un incidente evitado o **acortado a la mitad** (reducción de MTTR) **evitaría ~USD 600 000–1 000 000** por evento.

Estas cifras se usan únicamente para dimensionar el ROI del prototipo y deben validarse con parámetros del caso real que asigne el profesor.

## 5. Propuesta de valor de SentinelAI

SentinelAI reduce el MTTR y la fatiga de alertas actuando como L1 SRE autónomo:

1. **Ingesta inteligente:** filtra e interpreta logs, métricas (CPU/memoria/error rate) y latencias de la API.
2. **Evaluación de anormalidades:** clasifica en tiempo real si un evento es anomalía real o comportamiento esperado (reduce >70% de alertas no accionables antes de paginar a un humano).
3. **Recuperación de antecedentes (RAG):** busca post-mortems e incidentes pasados similares (contexto). En esta iteración, los antecedentes provienen del historial del propio sistema.
4. **Diagnóstico y recomendación:** genera análisis de causa raíz respaldado por evidencia y un runbook sugerido.
5. **Trazabilidad y auditoría:** registra cada paso de decisión en un estado inmutable (cada contribución se obtiene mediante Structured Output con esquemas Pydantic).

**Beneficios esperados:** menor MTTR, menor costo por incidente, menor carga onerosa de on-call y evidencia de auditoría completa.

## 6. Stakeholders y usuarios

| Stakeholder | Rol | Necesidad |
|---|---|---|
| Líder de SRE (head of reliability) | Sponsor | Reducir MTTR, costo por minuto de caída y rotación del equipo on-call |
| Ingeniero SRE L1 | Usuario final | Filtrar ruido y recibir causa raíz + runbook accionable |
| Gerente de operaciones/pagos | Beneficiario | Mantener el uptime del procesador y cumplir SLO/SLA |
| Equipo de auditoría / cumplimiento | Beneficiario | Trazabilidad completa de decisiones de incidentes |

## 7. KPIs del caso de negocio

| KPI | Línea base (industria 2026) | Objetivo SentinelAI (prototipo) |
|---|---|---|
| Alertas no accionables | 57–70% del total [5][6] | Reducir **≥70%** el número de alertas paginadas a humanos |
| MTTR de incidentes críticos | 30 min–2 h (58%); >2 h (26%) [5] | **≤ 45 minutos** (reducción 40–60%) |
| Tiempo de diagnóstico de causa raíz | 15–30 min de triage manual | **< 5 minutos** (análisis + contexto RAG) |
| Tiempo de detección | ~40% descubiertos por clientes [5] | Detección en **< 1 min** de la anomalía |
| Costo evitado por incidente | USD 5 600–9 000/min [8][9] | **>USD 500 000** por incidente crítico evitado/acortado |

## 8. Estrategia de datos y demo

Para la **validación y la demo en vivo** se usa el **OpenTelemetry Demo** (aplicación de referencia de e-commerce con microservicios instrumentados: checkout, payments, product catalog, etc.) [12]:

- **Telemetría real y controlable:** logs, métricas y trazas en streaming.
- **Inyección de caos:** se pueden forzar fallos en vivo (latencia alta, errores, service down) para demostrar la ruta de anomalía del grafo (ingesta → análisis → contexto → respuesta).
- **Respaldo documental:** opcionalmente se complementa con un dataset público de logs de microservicios para mostrar el pipeline de ingesta a mayor escala.

El consumo se modela como eventos `TelemetryEvent` (id, servicio, entorno, timestamp, nivel de log, mensaje, métricas), compatibles con el estado del motor agéntico.

## 9. Alcance del prototipo

**Incluido (entregables demostrables):**

- Motor agéntico LangGraph con 4 nodos y rama condicional (anomalía → diagnóstico completo; normal → fin temprano).
- Evaluación de anomalía basada en nivel del log + umbral de métricas (CPU / error rate).
- Diagnóstico de causa raíz y acción recomendada con **esquemas estructurados (Pydantic v2 / Structured Output)**.
- Auditoría acumulada (`audit_logs`) con reducers de LangGraph.
- Trazabilidad de decisiones (adaptador Langfuse previsto), sanitización de ingesta (Zero Trust) y entorno reproducible (Dev Containers).
- Suite de pruebas unitarias sobre las rutas anómala y normal del grafo.

**No incluido (fases posteriores):** integración real con proveedores de pago, autenticación multiinquilino, dashboard web y despliegue productivo en la nube (queda el diseño serverless documentado).

## 10. Criterios de validación con el profesor

Este documento se presenta para validar el caso antes de consolidar el desarrollo. Puntos de discusión:

1. El escenario de **referencia (fintech/pagos con datos de OTel Demo)** es aceptable en lugar de un cliente real. *(Conforme al requisito del PRA: "el caso debe ser validado con el profesor antes de iniciar el desarrollo".)*
2. Los **KPIs y el modelo de costo** son aceptables tal como están parametrizados.
3. El **cuadrante "Techniques"** del Technology Radar equivale al "Technologies" que menciona el PRA.

---

## 11. Referencias (APA 7)

1. Chen, Z., Kang, Y., Li, L., Zhang, X., Zhang, H., et al. (2020). Understanding and handling alert storm for online service systems. En *Proceedings of the ACM/IEEE 42nd International Conference on Software Engineering: Companion Proceedings* (pp. 162–163). ACM. https://doi.org/10.1145/3377812.3390809
2. Thoughtworks. (2026). *Technology Radar* (Vol. 34). https://www.thoughtworks.com/content/dam/thoughtworks/documents/radar/2026/04/tr_technology_radar_vol_34_en.pdf
3. Guiver, D. (2024, 28 de julio). *The true cost of payment system outages*. IR. https://www.ir.com/blog/payments/true-cost-of-payment-system-outages
4. Beck, S. (2024, 7 de noviembre). *The true cost of payment system downtime: Can your business afford it?* Forbes Technology Council. https://www.forbes.com/councils/forbestechcouncil/2024/11/07/the-true-cost-of-payment-system-downtime-can-your-business-afford-it/
5. NeuBird AI. (2026). *2026 State of production reliability and AI adoption report*. https://assets.ctfassets.net/jdtwqhzvc2n1/1L65zWJm1D3elsD2Yaeo6T/fc9a23041a967a94848f9afa88047e06/State-of-Production-Reliability-and-AI-Adoption.pdf
6. OpsWerks. (2026). *State of SRE operations 2026*. https://go.opswerks.com/hubfs/OpsWerks-sre-report-2026-general-v5.pdf
7. StackGen. (2026). *2026 State of reliability*. https://stackgen.com/hubfs/2026-State-of-Reliability/SOR2026_Report.pdf
8. Atlassian. (s. f.). *Calculating the cost of downtime*. https://www.atlassian.com/incident-management/kpis/cost-of-downtime
9. Ponemon, L. (2016). *2016 Cost of data center outages*. Ponemon Institute / Vertiv. https://www.vertiv.com/4a8191/globalassets/documents/reports/2016-cost-of-data-center-outages-11-11_51190_1.pdf
10. Enterprise Management Associates (EMA) & BigPanda. (2024). *IT outages: The $1,400,000,000,000 elephant in the boardroom*. https://www.bigpanda.io/wp-content/uploads/2024/04/EMA-BigPanda-final-Outage-eBook.pdf
11. SafeCharge / WBR Digital. (s. f.). *76% of merchants experienced at least one complete payments outage within the last year*. Financial IT. https://financialit.net/news/payments/76-merchants-experienced-least-one-complete-payments-outage-within-last-year
12. OpenTelemetry. (s. f.). *OpenTelemetry Demo documentation*. https://opentelemetry.io/docs/demo/