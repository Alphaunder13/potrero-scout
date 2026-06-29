"""
streamlit_app.py — Dashboard de Potrero Scout (ultima pieza de la V1).

Flujo: shortlist rankeada -> elegir jugador -> perfil + DESGLOSE auditable del
score + espacio para el informe de IA.

El desglose existe para validar la metrica con ojo de scout: muestra QUE
percentiles, QUE pesos y COMO se llego al numero de infravaloracion, no solo el
resultado.

Correr:  streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "analysis"))
sys.path.insert(0, str(ROOT / "reports"))
import normalize as nz       # noqa: E402
import undervaluation as uv  # noqa: E402
import claude_report as cr   # noqa: E402

DB_PATH = ROOT / "db" / "scout.db"
load_dotenv(ROOT / ".env")
# En Streamlit Cloud la key NO viene de un .env (no existe en la nube), sino de
# st.secrets. La exponemos como variable de entorno para que el SDK de Anthropic
# la tome. El secret se carga en la config de Streamlit, NUNCA en el repo.
if not os.getenv("ANTHROPIC_API_KEY"):
    try:
        if st.secrets.get("ANTHROPIC_API_KEY"):
            os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        pass
HAS_KEY = bool(os.getenv("ANTHROPIC_API_KEY"))

# Local vs nube: el .env existe en local (gitignored) y NUNCA en Streamlit Cloud.
# En la demo publica NO exponemos el boton de generacion en vivo (la app es
# publica: cada clic gastaria la API key). Ahi mostramos un informe ya generado.
IS_LOCAL = (ROOT / ".env").exists()
SAMPLE_REPORT = ROOT / "reports" / "sample_report_cardozo.json"


def render_report(rep: dict) -> None:
    """Renderiza un informe (en vivo o de ejemplo) con el mismo formato."""
    st.markdown(f"**Perfil**\n\n{rep['perfil']}")
    st.markdown("**Fortalezas**")
    for f in rep["fortalezas"]:
        st.markdown(f"- {f}")
    st.markdown(f"**Comparable de estilo** (tentativo)\n\n{rep['comparable_estilo']}")
    st.markdown(f"**Tesis — por qué ahora**\n\n{rep['tesis_por_que_ahora']}")
    st.markdown("**Riesgos**")
    for rg in rep["riesgos"]:
        st.markdown(f"- {rg}")


@st.cache_data(show_spinner=False)
def load_scored(min_minutes: int, min_pool: int) -> pd.DataFrame:
    """Lee el SQLite y corre la metrica (percentiles + scores)."""
    with sqlite3.connect(DB_PATH) as con:
        df = pd.read_sql("SELECT * FROM players", con)
    df = nz.add_percentiles(df, min_minutes=min_minutes, min_pool=min_pool)
    return uv.score(df)


def euros(v) -> str:
    return f"€{int(v):,}" if v and v == v else "—"


# ---------------------------------------------------------------------------
st.set_page_config(page_title="Potrero Scout", page_icon="⚽", layout="wide")
st.title("⚽ Potrero Scout")
st.caption("Filtro de productividad ofensiva ajustado por valor y edad — "
           "punto de partida para análisis en video, no veredicto final.")

# --- Controles (sidebar) ---
with st.sidebar:
    st.header("Filtros")
    min_minutes = st.slider("Mínimo de minutos", 0, 2000, nz.DEFAULT_MIN_MINUTES, 50)
    min_pool = st.slider("Tamaño mínimo de pool", 2, 15, nz.DEFAULT_MIN_POOL, 1)
    sub_age = st.slider("Edad máxima (sub-N)", 18, 25, 23, 1)
    top_n = st.slider("Top N", 5, 40, 15, 5)
    w = uv.Weights()
    st.markdown(
        f"**Pesos del score**\n\n"
        f"- rendimiento: `{w.w_perf}`\n- valor bajo: `{w.w_cheap}`\n"
        f"- juventud: `{w.w_youth}`\n- bonus proyección: `≤{w.proj_max}`"
    )

df = load_scored(min_minutes, min_pool)
sl = uv.shortlist(df, sub_age=sub_age, top_n=top_n)

col_list, col_detail = st.columns([1, 1.4], gap="large")

# --- Shortlist ---
with col_list:
    st.subheader(f"Shortlist — top {top_n} sub-{sub_age}")
    if sl.empty:
        st.warning("No hay jugadores rankeables con estos filtros "
                   "(probá bajar el mínimo de minutos o el tamaño de pool).")
        st.stop()
    tabla = sl[["name", "age", "position", "minutes",
                "market_value_eur", "undervaluation"]].copy()
    tabla.columns = ["Jugador", "Edad", "Posición", "Min", "Valor €", "Score"]
    tabla.index = range(1, len(tabla) + 1)
    st.dataframe(tabla, width="stretch", height=560)

# --- Detalle del jugador ---
with col_detail:
    elegido = st.selectbox("Jugador a inspeccionar", list(sl["name"]))
    r = df[df["name"] == elegido].iloc[0]

    st.subheader(elegido)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Edad", int(r["age"]))
    c2.metric("Minutos", int(r["minutes"]))
    c3.metric("Valor", euros(r["market_value_eur"]))
    c4.metric("Score infraval.", f"{r['undervaluation']:.3f}")
    st.caption(f"{r['position']}  ·  pool de comparación: **{r['pos_pool']}**")

    # ---- DESGLOSE AUDITABLE ----
    st.markdown("### 🔍 Cómo se calculó el score")
    pw = w.perf_weights.get(r["pos_pool"], w.perf_weights["OTHER"])

    st.markdown(
        f"**Pesos de rendimiento aplicados** para su familia de posición "
        f"`{r['pos_pool']}` ({r['position']}): "
        f"goles `{pw['goals_90']}` · asistencias `{pw['assists_90']}` "
        f"— *cambian según la posición; a un 9 le pesa el gol, a un central la asistencia.*"
    )
    st.markdown("**1. Percentiles dentro de su posición** (0–1, vs sus pares del pool)")
    perc = pd.DataFrame([
        {"Métrica": "goles_90", "Valor /90": r["goals_90"],
         "Percentil": r["goals_90_pct"], "Peso": pw["goals_90"]},
        {"Métrica": "assists_90", "Valor /90": r["assists_90"],
         "Percentil": r["assists_90_pct"], "Peso": pw["assists_90"]},
    ])
    st.dataframe(perc, width="stretch", hide_index=True)

    st.markdown(
        f"**2. Rendimiento** = "
        f"`{pw['goals_90']}·{r['goals_90_pct']:.3f} + "
        f"{pw['assists_90']}·{r['assists_90_pct']:.3f}` = **{r['performance']:.3f}**"
    )

    comp = pd.DataFrame([
        {"Componente": "Rendimiento", "Valor": r["performance"], "Peso": str(w.w_perf),
         "Aporte": w.w_perf * r["performance"]},
        {"Componente": "Baratura (valor bajo)", "Valor": r["cheapness"], "Peso": str(w.w_cheap),
         "Aporte": w.w_cheap * r["cheapness"]},
        {"Componente": "Juventud", "Valor": r["youth"], "Peso": str(w.w_youth),
         "Aporte": w.w_youth * r["youth"]},
        {"Componente": "Bonus proyección", "Valor": r["proj_bonus"], "Peso": "(aditivo)",
         "Aporte": r["proj_bonus"]},
    ])
    st.markdown("**3. Score de infravaloración** = suma de aportes")
    st.dataframe(comp, width="stretch", hide_index=True)
    st.success(f"Infravaloración = **{r['undervaluation']:.4f}**")

    # ---- Informe de IA ----
    st.markdown("### 🧠 Informe de scouting (IA)")
    if IS_LOCAL and HAS_KEY:
        # Local con key: generacion en vivo del jugador seleccionado.
        payload = cr.build_player_payload(r)
        if st.button("Generar informe real (usa la API de Anthropic — paga por uso)"):
            with st.spinner("Generando con Claude…"):
                report = cr.generate_report(payload, dry_run=False)
            render_report(report)
    elif IS_LOCAL:
        # Local sin key: dry-run, muestra que se enviaria sin gastar.
        payload = cr.build_player_payload(r)
        st.info("Sin `ANTHROPIC_API_KEY` en el `.env` → modo dry-run (no se llama a la API). "
                "Poné la key y recargá para habilitar el botón de generar.")
        with st.expander("Ver lo que se le enviaría al modelo (datos ya calculados)"):
            st.code(payload, language="text")
    else:
        # Demo publica (Streamlit Cloud): sin generacion en vivo. Informe de ejemplo.
        st.info("🔒 La generación en vivo está deshabilitada en esta demo pública: "
                "no exponemos la API key, que se gastaría con cada clic. Abajo, un "
                "informe **real** ya generado por el sistema, como muestra de lo que produce.")
        sample = json.loads(SAMPLE_REPORT.read_text(encoding="utf-8"))
        st.markdown(f"#### 📋 Informe de ejemplo — {sample['player']} "
                    "*(generado en local con la API y validado contra el pipeline)*")
        render_report(sample)
