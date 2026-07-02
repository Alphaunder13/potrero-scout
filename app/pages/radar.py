"""Radar — capa cuantitativa completa: tabla filtrable + desglose auditable.

La capa verificada a mano (top-15 con fuentes por dato) llega en el proximo
bloque; por ahora esta seccion sirve la capa cuantitativa entera, etiquetada
como tal.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import common  # noqa: E402

import pandas as pd          # noqa: E402
import streamlit as st       # noqa: E402
import undervaluation as uv  # noqa: E402

st.title("Radar")
st.caption(common.snapshot_caption(common.load_snapshot_meta()))

df = common.load_scored()

st.markdown(
    f"**Capa cuantitativa — {len(df)} jugadores.** Todos los sub-25 de la "
    "Primera Nacional con estadísticas en el pipeline. Es el filtro estadístico: "
    "señala dónde mirar, no evalúa jugadores. La capa verificada a mano "
    "(top-15 con fuente y fecha por dato) está en construcción."
)

# --- Filtros -----------------------------------------------------------------
c1, c2 = st.columns(2)
posiciones = sorted(df["position"].dropna().unique())
sel_pos = c1.multiselect("Posición", posiciones, default=[],
                         placeholder="Todas las posiciones")
min_min = c2.slider("Minutos mínimos", 0, int(df["minutes"].max()), 0, 50)

view = df.copy()
if sel_pos:
    view = view[view["position"].isin(sel_pos)]
view = view[view["minutes"].fillna(0) >= min_min]
view = view.sort_values("undervaluation", ascending=False, na_position="last")

tabla = view[["name", "age", "position", "minutes", "market_value_eur",
              "goals_90", "assists_90", "undervaluation"]].copy()
tabla.columns = ["Jugador", "Edad", "Posición", "Min", "Valor €",
                 "Goles/90", "Asist/90", "Score"]
tabla.index = range(1, len(tabla) + 1)
st.dataframe(tabla, width="stretch", height=420)
st.caption(
    "Sin score = datos insuficientes para rankear (no llega al umbral de "
    "minutos, o su pool de posición es demasiado chico para que el percentil "
    "signifique algo). El criterio está explicado en Metodología."
)

# --- Detalle del jugador: el desglose auditable --------------------------------
st.divider()
st.subheader("Desglose por jugador")
st.caption("Cada score se puede desarmar a mano: qué percentiles, qué pesos, "
           "cómo se llega al número.")

if view.empty:
    st.warning("Ningún jugador pasa los filtros actuales.")
    st.stop()

elegido = st.selectbox("Jugador a inspeccionar", list(view["name"]))
r = view[view["name"] == elegido].iloc[0]

m1, m2, m3, m4 = st.columns(4)
m1.metric("Edad", int(r["age"]))
m2.metric("Minutos", int(r["minutes"]))
m3.metric("Valor", common.euros(r["market_value_eur"]))
m4.metric("Score", f"{r['undervaluation']:.3f}" if pd.notna(r["undervaluation"]) else "—")
st.caption(f"{r['position']} · pool de comparación: **{r['pos_pool']}**")

if pd.isna(r["undervaluation"]):
    st.info(
        "Sin score: datos insuficientes para rankear. "
        f"Minutos: {int(r['minutes'])} (umbral: 500) · "
        f"tamaño de su pool: {int(r['pool_size'])} (mínimo: 5). "
        "No se fabrica un percentil donde la comparación no significa nada."
    )
else:
    w = uv.Weights()
    pw = w.perf_weights.get(r["pos_pool"], w.perf_weights["OTHER"])

    st.markdown(
        f"**Pesos de rendimiento aplicados** para su familia de posición "
        f"`{r['pos_pool']}` ({r['position']}): goles `{pw['goals_90']}` · "
        f"asistencias `{pw['assists_90']}` — cambian según la posición."
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
        f"**2. Rendimiento** = `{pw['goals_90']}·{r['goals_90_pct']:.3f} + "
        f"{pw['assists_90']}·{r['assists_90_pct']:.3f}` = **{r['performance']:.3f}**"
    )

    comp = pd.DataFrame([
        {"Componente": "Rendimiento", "Valor": r["performance"],
         "Peso": str(w.w_perf), "Aporte": w.w_perf * r["performance"]},
        {"Componente": "Baratura (valor bajo)", "Valor": r["cheapness"],
         "Peso": str(w.w_cheap), "Aporte": w.w_cheap * r["cheapness"]},
        {"Componente": "Juventud", "Valor": r["youth"],
         "Peso": str(w.w_youth), "Aporte": w.w_youth * r["youth"]},
        {"Componente": "Bonus proyección", "Valor": r["proj_bonus"],
         "Peso": "(aditivo)", "Aporte": r["proj_bonus"]},
    ])
    st.markdown("**3. Score de infravaloración** = suma de aportes")
    st.dataframe(comp, width="stretch", hide_index=True)
    st.success(f"Infravaloración = **{r['undervaluation']:.4f}**")

# --- Fichas ---------------------------------------------------------------
st.divider()
if common.IS_LOCAL and common.HAS_KEY:
    # Solo en local: generacion en vivo (la clave nunca sale de esta maquina).
    import claude_report as cr
    payload = cr.build_player_payload(r)
    if st.button("Generar informe (local — usa la API de Anthropic, paga por uso)"):
        with st.spinner("Generando…"):
            report = cr.generate_report(payload, dry_run=False)
        st.markdown(f"**Perfil**\n\n{report['perfil']}")
        st.markdown("**Fortalezas**")
        for f_ in report["fortalezas"]:
            st.markdown(f"- {f_}")
        st.markdown(f"**Comparable de estilo** (tentativo)\n\n{report['comparable_estilo']}")
        st.markdown(f"**Tesis — por qué ahora**\n\n{report['tesis_por_que_ahora']}")
        st.markdown("**Riesgos**")
        for rg in report["riesgos"]:
            st.markdown(f"- {rg}")
else:
    st.caption("Fichas individuales verificadas: en construcción.")
