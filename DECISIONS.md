# Decisiones de arquitectura — Potrero Scout

Registro de decisiones de diseño en formato **ADR** (Architecture Decision Records).
Cada entrada documenta una decisión, su contexto, las alternativas que se
descartaron y sus consecuencias.

> _Borrador. El texto de cada entrada está sujeto a revisión del autor._

---

## ADR 0001 — Registrar las decisiones de arquitectura con ADRs

**Estado:** Aceptada · **Fecha:** 2026-06-29

### Contexto
Un proyecto de portfolio se juzga tanto por el código como por el **criterio**
detrás de él. Las decisiones importantes (qué fuente de datos, cómo medir, cómo
manejar un secreto filtrado) se toman una vez y después se olvidan los porqués.
Sin un registro, ese razonamiento se pierde y cualquiera que lea el repo —o yo
mismo en seis meses— tiene que reconstruirlo.

### Decisión
Documentamos cada decisión de arquitectura como un ADR, siguiendo el formato que
propuso **Michael Nygard** ("Documenting Architecture Decisions", 2011): entradas
cortas, numeradas, inmutables, con estado, contexto, decisión, alternativas y
consecuencias. Los ADRs viven en este archivo, en el repo, versionados junto al
código.

### Alternativas consideradas
- **No documentar nada:** más rápido, pero el porqué se evapora.
- **Un wiki o Notion externo:** se desincroniza del código y se pierde el control de versiones.
- **Comentarios en el código:** sirven para el *cómo*, no para el *por qué* a nivel sistema.

### Consecuencias
- **Positivas:** el razonamiento queda explícito y auditable; facilita explicar el proyecto.
- **Negativas / riesgos:** mantener los ADRs al día requiere disciplina.
- **Reconsiderar si:** el proyecto crece y conviene migrar a un ADR por archivo (`docs/adr/`).

---

## ADR 0002 — Usar Transfermarkt como fuente de datos del ascenso

**Estado:** Aceptada · **Fecha:** 2026-06-27

### Contexto
La tesis del proyecto exige datos de la Primera Nacional argentina (valor de
mercado, edad, posición, goles, asistencias, minutos). El riesgo número uno era
quedarnos sin una fuente que cubriera el ascenso. Validamos antes de construir.

### Decisión
Adoptamos **Transfermarkt** (competición `ARG2`) como única fuente. Es la única
que cubre el ascenso de punta a punta y es accesible por HTTP.

### Alternativas consideradas
- **Sofascore:** bloqueado por Cloudflare (`403 challenge`) incluso vía navegador. No se evadió la protección — se respetó y se descartó.
- **FBref / StatsBomb:** no cubre la Primera Nacional (solo la Liga Profesional / 1.ª división).
- **API-Football (plan gratis):** cobertura pobre del ascenso y límite de requests.

### Consecuencias
- **Positivas:** una sola fuente cubre todo el dataset; sin claves ni costos.
- **Negativas / riesgos:** dependemos de un único proveedor y de la estabilidad de su HTML. **Importante y honesto:** los valores de mercado de Transfermarkt son *crowd-sourced* (estimaciones de la comunidad), no precios reales de transferencia. Se usan como **señal de contexto**, no como verdad.
- **Reconsiderar si:** Transfermarkt cambia su estructura, o aparece una fuente con datos de eventos para el ascenso.

---

## ADR 0003 — Ingesta en dos fases (barata → cara)

**Estado:** Aceptada · **Fecha:** 2026-06-27

### Contexto
El valor/edad/posición se obtiene por HTTP simple, pero goles/asistencias/minutos
viven en una tabla que carga por JavaScript y requiere renderizar con un navegador
headless (~13s por jugador). Renderizar a los ~1.000 jugadores de la liga sería
lento y poco respetuoso con el servidor.

### Decisión
Separamos la ingesta en dos fases: **(1) fase barata** (HTTP, instantánea) que
trae a toda la liga, y **(2) fase cara** (navegador headless) que corre **solo
sobre el subconjunto joven** ya filtrado. Todo con *rate-limiting* y caché en
disco; nada se re-descarga ni se re-renderiza.

### Alternativas consideradas
- **Renderizar todo con navegador:** simple pero lento, caro y agresivo con el servidor.
- **Solo HTTP:** imposible, los stats no están en el HTML crudo.

### Consecuencias
- **Positivas:** minimiza el costo y la carga al servidor; el proceso es reanudable (sobrevivió a un corte de luz a mitad de scrape).
- **Negativas / riesgos:** el filtro de la fase 1 define qué jugadores tienen stats; cambiar el criterio implica re-renderizar.
- **Reconsiderar si:** aparece un endpoint que devuelva los stats sin navegador.

---

## ADR 0004 — Guard de tamaño mínimo de pool para los percentiles

**Estado:** Aceptada · **Fecha:** 2026-06-28

### Contexto
La métrica compara a cada jugador contra sus pares de posición vía percentiles.
Si un pool de posición tiene muy pocos jugadores, el percentil deja de significar
algo: un pool de 1 daría "percentil 1.0" automático (el jugador sería "el mejor
del mundo" de su puesto por default).

### Decisión
Exigimos un **mínimo de jugadores por pool** (por defecto 5) para calcular
percentiles. A quienes no lo alcanzan los marcamos como *"datos insuficientes
para rankear"* y los sacamos de la shortlist principal — **no les fabricamos un
percentil.**

### Alternativas consideradas
- **Rellenar con un valor neutro (0.5):** mezcla un número inventado con los reales.
- **Ignorar el problema:** produce rankings sin sentido en posiciones raras.

Es la misma lógica de umbral que usa **FBref**, que exige un mínimo de jugadores/minutos para que un percentil entre a su pool de comparación.

### Consecuencias
- **Positivas:** ningún número fabricado contamina el ranking; misma filosofía anti-relleno que la capa de IA.
- **Negativas / riesgos:** posiciones con pocos jugadores quedan sin evaluar.
- **Reconsiderar si:** el dataset crece y el umbral puede subir, o si se suman ligas que engrosen los pools.

---

## ADR 0005 — Umbral mínimo de minutos para entrar al pool

**Estado:** Aceptada · **Fecha:** 2026-06-28

### Contexto
Los stats por-90 sobre muestras chicas son ruido. Caso real del dataset: un
jugador con **0.486 goles/90 en apenas 185 minutos** aparecía como "goleador de
elite" — un artefacto de la muestra, no una señal.

### Decisión
Exigimos un **mínimo de minutos** (configurable, por defecto 500') para que un
jugador entre al pool de comparación y sea rankeable.

### Alternativas consideradas
- **Sin umbral:** deja entrar ruido puro (el caso de los 185').
- **Umbral muy alto (ej. 1500'):** más confiable, pero **excluye justamente a los jóvenes con poco rodaje que el proyecto busca** — el tradeoff central de esta decisión.

### Consecuencias
- **Positivas:** separa señal de ruido; el umbral es un parámetro, no un valor hardcodeado.
- **Negativas / riesgos:** todo umbral es arbitrario y deja afuera a algún prospecto real con pocos minutos. Es un balance, no una verdad.
- **Reconsiderar si:** se incorpora un modelo de confianza por tamaño de muestra (ej. *shrinkage* bayesiano) que haga innecesario el corte duro.

---

## ADR 0006 — Pesos de rendimiento por posición

**Estado:** Aceptada · **Fecha:** 2026-06-29

### Contexto
El score de rendimiento pondera goles vs asistencias. Un peso fijo para todas las
posiciones es futbolísticamente incorrecto: a un delantero le pesa el gol; a un
central, el aporte de asistencia importa relativamente más.

### Decisión
Definimos **pesos de rendimiento por familia de posición** (FW 0.7/0.3, extremo/
volante ofensivo 0.5/0.5, mediocampo 0.4/0.6, lateral 0.4/0.6, central 0.3/0.7),
en un diccionario configurable y documentado.

### Alternativas consideradas
- **Peso único para todos:** simple pero sesgado (penaliza a centrales por no hacer goles).
- **Pesos aprendidos de datos:** requeriría una variable objetivo (ej. revalorización futura) y datos que hoy no tenemos.

### Consecuencias
- **Positivas:** la métrica refleja lo que se le pide a cada rol; el sesgo más feo (centrales) quedó corregido.
- **Negativas / riesgos:** **son heurísticas de criterio experto, no aprendidas de datos** — un juicio razonable pero discutible. Marcado explícitamente como mejora futura.
- **Reconsiderar si:** se consigue una señal objetivo para entrenar los pesos en vez de fijarlos a mano.

---

## ADR 0007 — Diseño anti-alucinación de la capa de IA

**Estado:** Aceptada · **Fecha:** 2026-06-28

### Contexto
La capa de IA redacta informes de scouting. El riesgo es que invente cifras,
comparaciones o mecanismos que el dato no respalda — fatal en una herramienta que
debe ser confiable para un director deportivo.

### Decisión
La IA **solo redacta sobre números ya calculados por el pipeline; no calcula ni
infiere datos.** El *grounding* se logra con tres mecanismos:
1. **Structured outputs (`json_schema`):** campos fijos, formato garantizado.
2. **System prompt restrictivo:** prohíbe inventar cifras, exige declarar lo que falta, marca los comparables como tentativos y **prohíbe atribuir mecanismos** ("desde la pelota parada", "por la banda") que no estén en los datos.
3. **Verificación contra ground truth:** cada cifra del informe se cruza contra lo que calculó el pipeline.

### Alternativas consideradas
- **Pedirle al modelo que "calcule" desde stats crudas:** invita a la alucinación numérica.
- **Bajar la temperatura del modelo:** no es la palanca acá — `claude-opus-4-8` no expone el parámetro de temperatura. El control anti-alucinación no viene de ahí, sino del *grounding* en datos ya calculados, los structured outputs y la verificación contra el ground truth.

### Consecuencias
- **Positivas:** verificado en producción — los informes citan percentiles reales, reportan riesgos con datos en contra y declaran lo que no pueden saber.
- **Negativas / riesgos:** structured outputs garantiza el formato, no la veracidad; depende de la disciplina del prompt y de la verificación.
- **Reconsiderar si:** se suma una validación automática que rechace informes con cifras fuera del ground truth.

---

## ADR 0008 — Postmortem: manejo del incidente de la API key

**Estado:** Aceptada · **Fecha:** 2026-06-29

### Contexto
Durante el desarrollo, la `ANTHROPIC_API_KEY` se pegó por error en `.env.example`
—un archivo **versionado** (es la plantilla pública)— en vez de en `.env`. Una
key en un archivo trackeado que llega a un commit queda expuesta.

### Decisión
Respuesta en este orden:
1. **Rotar/revocar la key primero.** Es lo único que neutraliza de verdad un secreto expuesto; todo lo demás es secundario.
2. **Limpiar el archivo no alcanza si ya se commiteó:** git guarda el historial, así que borrar la línea en un commit nuevo deja la key en los commits viejos (haría falta reescribir historia con `filter-branch`/BFG). En nuestro caso auditamos el historial y confirmamos que **nunca se llegó a commitear** (se revirtió antes del `git add`), así que no hubo que reescribir nada.
3. **Prevención por diseño:** `.env` en `.gitignore`, `.env.example` como plantilla vacía, y **la versión pública de la app no llama a la API** — así la key nunca necesita salir de la máquina local (ni a GitHub ni a Streamlit).

### Alternativas consideradas
- **Solo borrar el archivo y seguir:** falso sentido de seguridad; si estuvo en un commit, sigue en el historial.
- **Reescribir el historial sin rotar:** deja la key viva si ya fue vista (estaba en el chat).

### Consecuencias
- **Positivas:** incidente cerrado sin exposición real; controles preventivos en su lugar.
- **Negativas / riesgos:** la verificación de "ningún secreto en el repo" hay que correrla en cada cambio, no asumirla.
- **Reconsiderar si:** se agrega CI con un *secret scanner* (ej. gitleaks) que automatice esa verificación.

---

## ADR 0009 — Procedencia del snapshot: metadata explícita, no inferida del filesystem

**Estado:** Aceptada · **Fecha:** 2026-07-02

### Contexto
La V2 muestra la fecha de los datos ("edición") en la Home y en cada ficha. Esa
fecha necesita una fuente de verdad. La opción perezosa —inferirla del `mtime`
de `db/scout.db`— falla justo donde más importa: en Streamlit Cloud, el checkout
del deploy pisa los `mtime`, así que la app mostraría **la fecha del deploy como
si fuera la fecha de los datos**. Una procedencia falsa en un producto cuya
propuesta es, precisamente, la procedencia.

### Decisión
La fecha de los datos vive en `data/snapshot_meta.json`, un archivo de metadata
explícito y versionado. Para el snapshot actual se creó a mano (backfill) con los
valores reales conocidos; las corridas futuras de `ingest/build_dataset.py` lo
escriben automáticamente al final (única modificación admitida a `ingest/`:
aditiva pura, cero cambios a la lógica de scraping o procesamiento). Detalle de
honestidad: las corridas futuras escriben `built_at` (fecha de la corrida), no un
rango de captura — con la caché, parte de los datos puede ser anterior a la
corrida, y afirmar un rango sería inventar procedencia. La app muestra la fecha
solo si el archivo existe; si falta, muestra "fecha de datos no disponible" —
nunca una fecha inferida ni hardcodeada.

### Alternativas consideradas
- **`mtime` del archivo de datos:** descartado — los checkouts de deploy lo pisan y produce procedencia falsa.
- **Hardcodear la fecha en la UI:** envejece mal y se desincroniza del dato en silencio.
- **Derivarla del historial de git:** acopla el dato al repo; la metadata debe viajar con el snapshot.

### Consecuencias
- **Positivas:** una sola fuente de verdad para la fecha de edición; la procedencia mostrada es siempre real o declaradamente ausente.
- **Negativas / riesgos:** el backfill manual depende de que los valores registrados sean correctos; un archivo más que mantener (mitigado: lo escribe la corrida).
- **Reconsiderar si:** el dataset pasa a actualizarse por partes o por fuente — ahí la procedencia debería ser por-dato (la capa manual de la V2 ya la trae: `last_updated` por registro).
