# Potrero Scout ⚽

**Detector de talento sub-23 infravalorado en la Primera Nacional argentina** (segunda división), con arquitectura replicable a otras ligas.

## La tesis (el porqué)

Las plataformas grandes de scouting (Wyscout, Hudl) cuestan £20k+/año e **ignoran el ascenso y las juveniles sudamericanas**. Para la Primera Nacional **no existe ninguna fuente gratuita** con datos de eventos ni métricas avanzadas.

Esa escasez de información es la asimetría que explota el proyecto: **encontrar jugadores que rinden por encima de lo que el mercado todavía ve** — valor de mercado bajo + edad joven + buen rendimiento por-90.

## Cómo funciona

```
Ingesta (conectores)  →  Dataset limpio (SQLite)  →  Métrica de infravaloración  →  Shortlist  →  Informe IA  →  Dashboard
```

1. **Ingesta** — un "conector" por fuente, todos normalizan al mismo esquema. Agregar una liga = agregar un conector, sin tocar el análisis.
2. **Dataset** — unificado y limpio en SQLite. Contrato mínimo: `player_id, name, age, position, minutes, market_value_eur, goals_90, assists_90`.
3. **Métrica** — stats por-90 → percentiles **dentro de la misma posición y liga** → score de rendimiento → cruce con valor de mercado y edad. Todo transparente, nada de caja negra.
4. **Shortlist** — top-N sub-23 infravalorados, rankeados.
5. **Informe IA** — la API de Claude **redacta** sobre números ya calculados (no inventa datos; structured outputs + anti-alucinación).
6. **Dashboard** — Streamlit: shortlist → perfil del jugador → informe.

## Fuentes de datos

| Fuente | Qué aporta | Cómo |
|---|---|---|
| **Transfermarkt** (`ARG2`) | valor de mercado €, edad, posición, minutos | scraping con rate-limiting + caché, uso educativo |
| **API-Football** (tier gratis) | stats básicas | **validar cobertura real ANTES de construir** |
| **Sofascore** (vía ScraperFC) | fallback si API-Football viene pobre | — |

## Stack

Python 3 · pandas · SQLite · Streamlit · SDK de Anthropic.
Las API keys van en `.env` (nunca commiteado). Copiá `.env.example` a `.env` y completá.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # y completá las claves
streamlit run app/streamlit_app.py
```

## Estado

🚧 **V1 en construcción.** Validando cobertura de datos del ascenso antes de armar el pipeline.

## Alcance V1

**Entra:** 1 liga (Primera Nacional, temporada actual), dataset limpio, métrica de infravaloración, shortlist, informe por jugador con IA, dashboard.
**Queda para V2+:** xG propio, player similarity con embeddings, aging curves entrenadas, múltiples ligas en simultáneo.

---

*Proyecto de aprendizaje. Prioriza claridad y simplicidad sobre cleverness. Uso educativo / no comercial.*
