# Potrero Scout ⚽

**Un detector de talento sub-23 infravalorado en la Primera Nacional argentina (segunda división), construido sobre datos públicos y una capa de IA que redacta informes de scouting sin inventar nada.**

Arquitectura replicable a otras ligas del ascenso sudamericano sin reescribir el análisis.

---

## La tesis: una asimetría de información

El scouting profesional corre sobre plataformas como Wyscout o Hudl, que cuestan **£20.000+ al año** y concentran su cobertura en las primeras divisiones de Europa. El **ascenso sudamericano** —la Primera Nacional argentina, donde se forma y se revende buena parte del talento joven— es un punto ciego: **no existe ninguna fuente gratuita con datos de eventos ni métricas avanzadas para esta categoría.**

Esa escasez de información *es* la oportunidad. Si nadie mide sistemáticamente al ascenso, hay jugadores que rinden por encima de lo que el mercado todavía ve. Potrero Scout cruza tres señales públicas —**valor de mercado bajo + edad joven + rendimiento por-90 alto dentro de su posición**— para producir una shortlist rankeada de candidatos a estar infravalorados, y un informe por jugador que explica el porqué.

No es magia ni promete fichajes seguros. Es un filtro transparente que convierte datos dispersos en una hipótesis accionable, con todas sus limitaciones a la vista.

---

## El hueco de datos (lo que encontramos validando antes de construir)

El principio que guió el proyecto fue **validar la fuente de datos antes de construir el pipeline**, porque el riesgo número uno era quedarnos sin con qué llenarlo. La validación dio un resultado incómodo pero clarificador:

| Fuente | Resultado real |
|---|---|
| **API-Football** (plan gratis) | Cobertura pobre del ascenso. Descartada. |
| **Sofascore** | **Bloqueada por Cloudflare** (`403 challenge`) incluso vía navegador. No se evadió la protección — se respetó y se descartó. |
| **FBref / StatsBomb** | No cubre la Primera Nacional (solo la Liga Profesional / 1.ª división). |
| **Transfermarkt** (`ARG2`) | ✅ **Viable.** Valor de mercado, edad, posición, y —con más trabajo— goles/asistencias/minutos. |

Transfermarkt terminó siendo la única fuente que cubre el ascenso de punta a punta. Pero ni siquiera fue directo: los datos de rendimiento viven en un componente que carga por JavaScript (XHR), así que hubo que **renderizar la página con un navegador headless** y parsear la grilla, aislando la fila de la *Primera Nacional* específicamente (no el "Total", que suma copas). Cada decisión quedó documentada en vez de escondida.

**Resultado:** dataset limpio de **1.053 jugadores** de la liga (36 clubes, temporada 2025), de los cuales **395 son sub-25** y **259 tienen estadísticas de rendimiento** utilizables.

---

## Cómo funciona

```
Ingesta (2 fases)  →  SQLite limpio  →  Métrica de infravaloración  →  Shortlist  →  Informe IA  →  Dashboard
```

1. **Ingesta en dos fases**, para controlar el costo del navegador headless:
   - *Fase barata* (HTTP, instantánea): valor de mercado, edad y posición de toda la liga.
   - *Fase cara* (Chrome headless, ~13s/jugador): goles, asistencias y minutos, **solo sobre el subconjunto joven** ya filtrado. Caché agresiva en disco: nada se vuelve a descargar ni a renderizar (el proceso es reanudable si se corta).
2. **Dataset unificado** en SQLite, con un esquema-contrato mínimo: `player_id, name, age, position, minutes, market_value_eur, goals_90, assists_90`.
3. **Métrica de infravaloración** (abajo en detalle).
4. **Shortlist**: top-N sub-23 rankeados por score.
5. **Informe por jugador** generado con la API de Claude, que redacta sobre números ya calculados (no calcula ni inventa).
6. **Dashboard** en Streamlit: shortlist → perfil → desglose auditable → informe.

La arquitectura separa **ingesta** de **análisis**: cada fuente es un conector con la misma interfaz. Sumar una liga nueva es agregar/parametrizar un conector, sin tocar la métrica.

---

## La metodología de la métrica (en lenguaje claro)

Todo el score es una suma de números entre 0 y 1, documentada y auditable a mano. Cero caja negra.

1. **Stats crudas → por-90 minutos.** Goles y asistencias se normalizan por 90' para comparar jugadores con distinto tiempo en cancha.
2. **Por-90 → percentil dentro de la misma posición.** A un jugador se lo compara con sus pares de su *pool* de posición (extremos con extremos, centrales con centrales), no contra toda la liga. Un percentil 0.90 en goles significa "mejor que el 90% de los de su puesto".
3. **Dos guardas anti-ruido, ambas honestas:**
   - **Umbral de minutos** (configurable, por defecto 500'): quien no llegó no entra al pool de comparación. Esto evita que un jugador con 150' y un gol parezca un goleador de elite.
   - **Tamaño mínimo de pool** (por defecto 5): si una posición tiene muy pocos jugadores, **no se le inventa un percentil** (un pool de 1 daría un "percentil 1.0" de regalo). Esos jugadores se marcan como *"datos insuficientes para rankear"* y quedan fuera de la shortlist principal. Misma filosofía anti-alucinación que la capa de IA: no rellenar huecos con números fabricados.
4. **Score de rendimiento** = promedio ponderado de los percentiles relevantes, **con pesos por posición**: a un delantero le pesa más el gol; a un lateral, la asistencia.
5. **Score de infravaloración** = `0.5 · rendimiento  +  0.3 · baratura  +  0.2 · juventud  +  bonus_proyección`, donde *baratura* = qué tan bajo es el valor de mercado respecto a sus pares, *juventud* = qué tan por debajo de los 23 está, y *bonus_proyección* premia a los más jóvenes (heurística de curva de carrera, pico ~26). **Todos los pesos son configurables y están documentados.**

Cada número del ranking se puede desarmar a mano. El dashboard muestra ese desglose por jugador, justamente para validarlo con ojo de scout.

---

## Un informe real de ejemplo

Generado por la capa de IA sobre **Martín Lazarte** (lateral izquierdo, 20 años, €50.000), #1 de la shortlist. La IA recibe *solo* los números ya calculados por el pipeline y tiene prohibido inventar:

> **PERFIL**
> Martín Lazarte es un lateral izquierdo de 20 años que milita en la Primera Nacional, con apenas 840 minutos jugados, por lo que el tamaño de muestra es chico y hay que tomar los números con cautela. Pese a eso, dentro de su pool de comparación (FB) muestra una proyección ofensiva muy llamativa, con un score de rendimiento de 0.971 y un valor de mercado bajo (€50.000) que lo posiciona como un perfil potencialmente infravalorado (score de infravaloración 0.894). Importante: para esta liga no hay métricas avanzadas (xG, datos de eventos, acciones defensivas), así que su aporte defensivo y la calidad de las chances no se pueden evaluar con datos.
>
> **FORTALEZAS**
> - Aporte de asistencias de elite dentro de su posición: percentil 1 en assists_90, con 0.321 asistencias por 90.
> - Llegada al gol inusual para un lateral: percentil 0.904 en goles_90, con 0.107 goles por 90.
> - Score de rendimiento muy alto dentro del pool FB: 0.971.
> - Perfil económico: percentil 0.876 en baratura (valor de mercado bajo, €50.000).
>
> **COMPARABLE DE ESTILO** (tentativo)
> Comparación tentativa y solo orientativa: por su volumen ofensivo desde el lateral izquierdo recuerda al arquetipo de lateral con vocación de generar asistencias y sumarse al ataque. No es un dato y no hay métricas avanzadas que lo respalden.
>
> **TESIS — POR QUÉ AHORA**
> La combinación de juventud (20 años), producción ofensiva top dentro de su posición (percentil 1 en asistencias, 0.904 en goles) y un valor de mercado muy bajo (€50.000) lo vuelve una apuesta de bajo costo y alto potencial de revalorización. Entrar ahora permite captar el upside antes de una eventual suba de precio.
>
> **RIESGOS**
> - Muestra muy chica: solo 840 minutos, lo que reduce la confiabilidad de los por-90 y percentiles.
> - No hay métricas avanzadas en la Primera Nacional: no se puede evaluar su solidez defensiva ni la calidad real de sus chances.
> - Los números ofensivos podrían no sostenerse al aumentar los minutos o subir de categoría.
> - El comparable de estilo es tentativo y no está respaldado por datos de eventos.

Notar cómo el informe **cita percentiles concretos** y, donde el dato no existe, lo dice explícitamente en vez de rellenarlo. Eso es por diseño: el system prompt prohíbe inventar cifras, clubes, transferencias o comparaciones como hechos. Las salidas son **estructuradas** (`json_schema`), lo que garantiza el formato; la veracidad la cuida el prompt.

---

## Limitaciones honestas

Un proyecto serio dice lo que **no** puede hacer:

- **No hay métricas avanzadas para el ascenso.** Sin datos de eventos, no hay xG, ni acciones defensivas, ni progresión de balón. La métrica se construye sobre goles, asistencias, minutos, edad y valor — señales útiles pero gruesas. El aporte defensivo de un central o un lateral queda esencialmente sin medir.
- **El valor de mercado es un proxy imperfecto.** Es una estimación de la comunidad de Transfermarkt, no un precio de transferencia real.
- **Muestras chicas.** Muchos jóvenes del ascenso juegan pocos minutos; el umbral de 500' ayuda, pero la confiabilidad de los por-90 sigue siendo limitada para varios casos.
- **Zona gris del scraping.** Los datos se obtienen por scraping de Transfermarkt con *rate-limiting* agresivo y caché local, para **uso educativo y no comercial**. No se crearon cuentas ni se evadieron protecciones: cuando Sofascore respondió con un desafío de Cloudflare, se respetó y se descartó la fuente.
- **Validación cualitativa pendiente.** El sentido futbolístico de la shortlist necesita el ojo de alguien que conozca el ascenso. La métrica propone; no decide.

---

## Stack

`Python 3` · `pandas` · `SQLite` · `cloudscraper` + navegador headless (vía ScraperFC) para la ingesta · `Streamlit` para el dashboard · **SDK de Anthropic (`claude-opus-4-8`)** con *structured outputs* para los informes.

```
potrero-scout/
├── ingest/        # conector Transfermarkt (2 fases) + caché HTTP/render
├── analysis/      # normalize.py (percentiles) · undervaluation.py (score)
├── reports/       # claude_report.py (capa de IA, anti-alucinación)
├── app/           # streamlit_app.py (dashboard)
├── tests/         # tests de la métrica
├── data/          # crudo + dataset limpio (gitignored)
└── db/scout.db    # SQLite (gitignored)
```

## Setup

```bash
python -m venv .venv && .venv/Scripts/activate      # Windows
pip install -r requirements.txt
cp .env.example .env                                 # y completá ANTHROPIC_API_KEY (opcional, para informes)

python ingest/build_dataset.py --season 2025         # construir el dataset
streamlit run app/streamlit_app.py                   # abrir el dashboard
```

La capa de IA es opcional y de pago por uso: sin `ANTHROPIC_API_KEY`, el sistema corre en modo *dry-run* (muestra qué se le enviaría al modelo, sin llamarlo ni gastar).

---

## Estado

**V1 funcional, de punta a punta:** ingesta → métrica → shortlist → informe IA → dashboard. Dataset de 259 jugadores con estadísticas cargado.

**Próximo (V2+):** xG propio sobre eventos, *player similarity* con embeddings, curvas de envejecimiento entrenadas, y múltiples ligas en simultáneo.

---

*Proyecto de aprendizaje. Prioriza claridad y honestidad sobre cleverness. Uso educativo / no comercial.*
