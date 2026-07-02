"""Radar — dos capas señalizadas: cuantitativa (completa) y top-15 en
verificacion (capa manual). TGS con desglose auditable y export CSV."""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import common  # noqa: E402

if not hasattr(common, "load_tgs"):
    # Guard anti hot-deploy stale (ver nota identica en views/home.py).
    common = importlib.reload(common)

import pandas as pd          # noqa: E402
import streamlit as st       # noqa: E402
import talent_gap as tg      # noqa: E402
import undervaluation as uv  # noqa: E402

st.title("Radar")
st.caption(common.snapshot_caption(common.load_snapshot_meta()))

df = common.load_tgs()
manual = tg.load_manual_layer()
manual_ids = set(manual["player_id"]) if not manual.empty else set()

n_manual = len(manual_ids)
st.markdown(
    f"**Dos capas.** Capa cuantitativa: **{len(df)} jugadores** del pipeline "
    f"(el filtro estadístico). Capa en verificación manual: **top-{n_manual}** "
    "con fuente y fecha por dato (en curso). El score señala dónde mirar; "
    "no evalúa jugadores."
)

# Dimension de capa y confianza (ADR 0010: la confianza NO altera el TGS)
df = df.copy()
df["capa"] = df["player_id"].map(
    lambda pid: f"top-{n_manual} en verificación" if pid in manual_ids
    else "cuantitativa")
df["confianza"] = df["player_id"].map(
    lambda pid: tg.confidence_for(pid, manual) if pid in manual_ids else "—")

# --- Filtros: posicion, minutos, confianza ------------------------------------
c1, c2, c3 = st.columns(3)
posiciones = sorted(df["position"].dropna().unique())
sel_pos = c1.multiselect("Posición", posiciones, default=[],
                         placeholder="Todas las posiciones")
min_min = c2.slider("Minutos mínimos", 0, int(df["minutes"].max()), 0, 50)
sel_conf = c3.multiselect("Confianza", ["A", "B", "C", tg.CONFIDENCE_UNSET],
                          default=[], placeholder="Todas")

view = df.copy()
if sel_pos:
    view = view[view["position"].isin(sel_pos)]
view = view[view["minutes"].fillna(0) >= min_min]
if sel_conf:
    view = view[view["confianza"].isin(sel_conf)]
view = view.sort_values("tgs", ascending=False, na_position="last")

tabla = view[["name", "age", "position", "minutes", "market_value_eur",
              "tgs", "confianza", "capa"]].copy()
tabla.columns = ["Jugador", "Edad", "Posición", "Min", "Valor €",
                 "TGS", "Confianza", "Capa"]
tabla.index = range(1, len(tabla) + 1)
st.dataframe(tabla, width="stretch", height=420)
st.caption(
    "Sin TGS = datos insuficientes para rankear (umbral de minutos o pool de "
    "posición chico; el porqué exacto aparece en el detalle del jugador). "
    "Confianza «—» = fuera de la capa en verificación. Criterio en Metodología."
)

# Export del radar filtrado
st.download_button(
    "Descargar radar filtrado (CSV)",
    data=tabla.to_csv(index=False).encode("utf-8"),
    file_name="potrero_radar.csv",
    mime="text/csv",
)

# --- Detalle por jugador -------------------------------------------------------
st.divider()
st.subheader("Detalle por jugador")

if view.empty:
    st.warning("Ningún jugador pasa los filtros actuales.")
    st.stop()

elegido = st.selectbox("Jugador a inspeccionar", list(view["name"]))
r = view[view["name"] == elegido].iloc[0]
conf = r["confianza"] if r["confianza"] != "—" else None

m1, m2, m3, m4 = st.columns(4)
m1.metric("Edad", int(r["age"]))
m2.metric("Minutos", int(r["minutes"]))
m3.metric("Valor", common.euros(r["market_value_eur"]))
m4.metric("TGS", int(r["tgs"]) if pd.notna(r["tgs"]) else "—")
st.caption(
    f"{r['position']} · pool: **{r['pos_pool']}** · "
    + (f"confianza: **{conf}**" if conf else "capa cuantitativa (fuera del top en verificación)")
)

if pd.isna(r["tgs"]):
    st.info(f"Sin TGS: {r['exclusion_reason']}. "
            "No se fabrica un score donde la comparación no significa nada.")
else:
    # Subscores 0-100
    for etiqueta, valor in tg.subscores(r).items():
        st.progress(min(max(valor / 100, 0.0), 1.0), text=f"{etiqueta}: {valor:.0f}")

    ds = tg.drivers(r)
    if ds:
        st.markdown("**Drivers (por reglas, trazables al dato):**")
        for d in ds:
            st.markdown(f"- {d}")

    with st.expander("Cálculo detallado (auditable)"):
        w = uv.Weights()
        pw = w.perf_weights.get(r["pos_pool"], w.perf_weights["OTHER"])
        st.markdown(
            f"**Pesos de rendimiento** del pool `{r['pos_pool']}`: goles "
            f"`{pw['goals_90']}` · asistencias `{pw['assists_90']}`."
        )
        st.markdown("**Percentiles dentro de su posición** (0–1)")
        st.dataframe(pd.DataFrame([
            {"Métrica": "goles_90", "Valor /90": r["goals_90"],
             "Percentil": r["goals_90_pct"], "Peso": pw["goals_90"]},
            {"Métrica": "assists_90", "Valor /90": r["assists_90"],
             "Percentil": r["assists_90_pct"], "Peso": pw["assists_90"]},
        ]), width="stretch", hide_index=True)
        st.markdown(
            f"**Producción** = `({pw['goals_90']}·{r['goals_90_pct']:.3f} + "
            f"{pw['assists_90']}·{r['assists_90_pct']:.3f})·100` = "
            f"**{r['sub_produccion']:.1f}**"
        )
        st.markdown(
            f"**Brecha de mercado** = producción vs percentil de valor en el pool "
            f"(`{r['value_pct_pool']:.3f}`), normalizada = **{r['sub_brecha']:.1f}**"
        )
        st.markdown(
            f"**Uso** = percentil de minutos en el pool = **{r['sub_uso']:.1f}** · "
            f"**Recorrido de edad** = **{r['sub_edad']:.1f}**"
        )
        st.markdown(
            f"**TGS** = `0.35·{r['sub_brecha']:.1f} + 0.30·{r['sub_produccion']:.1f} "
            f"+ 0.20·{r['sub_uso']:.1f} + 0.15·{r['sub_edad']:.1f}` = "
            f"**{int(r['tgs'])}**"
        )

# --- Ficha (capa verificada) ---------------------------------------------------
st.divider()
if int(r["player_id"]) in manual_ids:
    import ficha_md
    st.subheader("Ficha")
    mrow = tg.manual_row_for(int(r["player_id"]), manual)
    md = ficha_md.build_ficha_md(
        r, mrow, provenance=common.snapshot_caption(common.load_snapshot_meta()))
    if not ficha_md.is_verified(mrow):
        st.info("Verificación en curso: esta ficha muestra solo la capa "
                "cuantitativa. La versión completa (fuentes por dato, contexto, "
                "confianza) se publica cuando la verificación manual termina.")
    st.markdown(md)
    st.download_button(
        "Descargar ficha (.md)",
        data=md.encode("utf-8"),
        file_name=ficha_md.ficha_filename(r["name"]),
        mime="text/markdown",
    )
else:
    st.caption("Este jugador está en la capa cuantitativa; las fichas "
               "individuales corresponden al top en verificación.")
