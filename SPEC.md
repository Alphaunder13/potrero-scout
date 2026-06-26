# SPEC.md — Potrero Scout V1

## Objetivo
Detector de talento **sub-23 infravalorado** en la **Primera Nacional argentina** (segunda división). Cruza valor de mercado bajo + edad joven + rendimiento por-90, produce una shortlist rankeada, y genera un informe de scouting con IA por jugador. La arquitectura debe ser **replicable** a otras ligas sin reescribir el análisis.

## Tesis (el porqué)
Las plataformas grandes (Wyscout, Hudl, £20k+/año) ignoran el ascenso y las juveniles sudamericanas. Para la Primera Nacional NO existe ninguna fuente gratuita con datos de eventos ni métricas avanzadas. Esa escasez de información es la asimetría que explota el proyecto: encontrar jugadores que rinden por encima de lo que el mercado todavía ve.

## Alcance V1 — lo que SÍ entra
1. **Ingesta** de ≥1 fuente para 1 liga (Primera Nacional, temporada actual).
2. **Dataset limpio** unificado en SQLite.
3. **Métrica de infravaloración** transparente (percentiles por posición + valor de mercado + edad).
4. **Shortlist** rankeada: top-N sub-23 infravalorados.
5. **Informe por jugador** generado con la API de Claude (structured outputs, anti-alucinación).
6. **Dashboard** en Streamlit: shortlist → perfil → informe.

## Fuera de alcance — V2+
xG propio sobre eventos, player similarity con embeddings, aging curves entrenadas, múltiples ligas en simultáneo, producto comercial / scraping con licencia.

## Arquitectura
Principio rector: **separar ingesta de análisis**. Cada fuente es un "conector" que implementa la misma interfaz y normaliza al mismo esquema de columnas. Agregar una liga nueva = agregar/parametrizar un conector, sin tocar el análisis.

```
potrero-scout/
├── ingest/        # un conector por fuente (misma interfaz: fetch() -> DataFrame)
├── data/raw/      # crudo por fuente (inmutable)
├── data/clean/    # dataset unificado
├── analysis/      # normalize.py, undervaluation.py, similarity.py
├── reports/       # claude_report.py (structured outputs)
├── app/           # streamlit_app.py
├── db/scout.db    # SQLite
├── tests/
├── README.md
└── requirements.txt
```

Esquema-contrato del dataset unificado (mínimo):
`player_id, name, age, position, minutes, market_value_eur, goals_90, assists_90`

## Fuentes de datos
- **Transfermarkt** (competición `ARG2`): valor de mercado €, edad, posición, minutos. Vía scraping con rate-limiting agresivo + caché local. Uso educativo / no comercial.
- **API-Football** (tier gratis, 100 req/día): stats básicas. **VALIDAR la cobertura real de Primera Nacional ANTES de construir el pipeline** (puede devolver respuestas vacías sin dar error).
- **Fallback**: Sofascore vía ScraperFC si API-Football viene incompleto.

## Métrica de infravaloración
1. Stats crudas → por-90 minutos.
2. Por-90 → **percentiles dentro de la misma posición y liga** (exigir un mínimo de minutos para entrar al pool de comparación).
3. Score de rendimiento compuesto por posición (promedio ponderado de los percentiles relevantes).
4. Infravaloración = rendimiento alto + valor de mercado bajo + edad < 23.
5. Ajuste por edad: bonus de proyección a los más jóvenes (heurística de literatura, pico ~25-27). Todo transparente, nada de caja negra.

## Capa de IA
- El **pipeline calcula todo lo cuantitativo**. La IA **no calcula números**, solo redacta sobre datos ya calculados.
- **Structured outputs** (json_schema) con campos: `perfil`, `fortalezas` (citando percentiles concretos), `comparable_estilo`, `tesis_por_que_ahora`, `riesgos`.
- **Anti-alucinación**: el system prompt prohíbe inventar datos; si un dato no está, debe decirlo ("no hay métricas avanzadas para esta liga"). Structured outputs garantiza el formato, no la veracidad: de eso se encarga el prompt.

## Stack
Python · pandas · SQLite · Streamlit · SDK de Anthropic. `requirements.txt` pin-eado. `.env` para las API keys (NUNCA commiteado; va en `.gitignore`).

## Verificación — cómo sabemos que la V1 está lista
- [ ] Dataset limpio de >100 jugadores sub-23 de Primera Nacional con valor + stats.
- [ ] Shortlist que "tiene sentido futbolístico" al mirarla (validación cualitativa contra tu conocimiento del ascenso).
- [ ] Informe que cita percentiles reales y no inventa nada fuera de los datos.
- [ ] Dashboard navegable: shortlist → click en jugador → perfil + informe.
- [ ] Deploy en Streamlit Community Cloud + README con la tesis, la metodología y un informe de ejemplo.
