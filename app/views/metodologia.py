"""Metodologia — que mide el radar, que NO mide, y como leerlo (spec V2 §6)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import common  # noqa: E402

import streamlit as st  # noqa: E402

st.title("Metodología")
st.caption(common.snapshot_caption(common.load_snapshot_meta()))

st.info(
    "**Estado de implementación.** El **Talent Gap Score (0–100) con sus cuatro "
    "subscores** está vivo y es auditable en la sección Radar. El mecanismo de "
    "**niveles de confianza (A/B/C)** también está vivo, pero la asignación es "
    "parte de la verificación manual del top-15, que está **en curso**: hasta "
    "completarla, los jugadores muestran «sin verificar» — nunca un valor por "
    "defecto que parezca dato."
)

st.markdown("""
## Qué mide este radar

Señales públicas y cuantificables de posible infravaloración en jugadores sub-23
de la Primera Nacional: producción ofensiva ajustada por posición (goles y
asistencias por 90'), volumen de uso (minutos), edad, y la brecha entre
rendimiento relativo y valor de mercado estimado dentro del mismo pool.

## Qué NO mide

Calidad técnica observable solo en video, inteligencia táctica, juego sin
pelota, aporte defensivo (no hay datos públicos de eventos defensivos para esta
liga), personalidad, entorno, historial médico, ni contexto de vestuario.
**Este radar no evalúa jugadores: detecta dónde vale la pena que un ojo experto
mire.**

## Qué significa "infravalorado" acá

Que el percentil de producción de un jugador dentro de su pool posicional es
materialmente superior a su percentil de valor de mercado en ese mismo pool.
Es una anomalía estadística pública, no un veredicto de calidad.

## Qué significa "señal pública"

Un indicio derivado exclusivamente de datos públicos verificables, con fuente y
fecha citadas. Ni información privada, ni rumores, ni juicio propio.

## Niveles de confianza *(asignación en curso — hasta entonces: «sin verificar»)*

- **A** — datos completos, fuentes frescas (≤60 días), muestra sobre el umbral
  de minutos, valor de mercado con actualización reciente.
- **B** — falta un dato secundario, o el valor de mercado tiene más de 6 meses.
- **C** — muestra cercana al umbral mínimo o valor de mercado dudoso. Se publica
  solo con advertencia visible.

## Sesgos conocidos y declarados

1. **Sesgo ofensivo:** sin datos defensivos, centrales y volantes de marca están
   estructuralmente subrepresentados.
2. **Piso del pool:** destacar en el ascenso argentino no garantiza rendir una
   categoría arriba.
3. **Valores de mercado de Transfermarkt:** estimaciones *crowd-sourced*; se
   usan como señal de contexto, no como tasación.
4. **Minutos como proxy de confianza del club:** en equipos flojos, muchos
   minutos pueden significar "es lo que hay".

## Por qué no reemplaza al scout

Porque el radar ve *outputs*, no procesos. El gol dice cuánto; no dice cómo, ni
contra quién, ni en qué contexto. Esa lectura es humana. El radar reduce el
universo de búsqueda; la decisión es del ojo experto.

## Cómo interpretar el score

Un score alto significa "vale la pena mirar el video de este jugador esta
semana". No significa "ficharlo". Un score bajo no significa "malo": puede
significar datos insuficientes o un perfil que estas métricas no capturan.

---

**Reglas duras del cálculo (vivas hoy, auditables en la sección Radar):**
percentiles calculados solo dentro del pool de la misma posición · pesos de
goles/asistencias distintos por familia de posición · umbral mínimo de minutos
para entrar al pool (500') · pool mínimo de 5 jugadores para que un percentil
exista — donde la comparación no significa nada, no se fabrica un número.
""")
