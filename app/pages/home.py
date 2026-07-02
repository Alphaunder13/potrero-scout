"""Home — el hallazgo primero, el metodo a un clic (spec V2 §3)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import common  # noqa: E402

import streamlit as st       # noqa: E402
import undervaluation as uv  # noqa: E402

st.title("Señales públicas de talento infravalorado en el ascenso argentino")
st.markdown(
    "**Radar sub-23 de la Primera Nacional.** "
    "Metodología abierta · Fuentes verificables · Score explicable."
)
st.caption(common.snapshot_caption(common.load_snapshot_meta()))

st.markdown(
    "Radar público de talento sudamericano infravalorado. Detecta, con datos "
    "públicos y criterios explicables, dónde vale la pena que un ojo experto "
    "mire — no evalúa jugadores ni recomienda fichajes."
)

# --- Top 5 de esta edicion ---------------------------------------------------
st.subheader("Top 5 de esta edición")

df = common.load_scored()
top5 = uv.shortlist(df, sub_age=23, top_n=5)

if top5.empty:
    st.warning("No hay jugadores rankeables en esta edición.")
else:
    for i, (_, s) in enumerate(top5.iterrows(), start=1):
        r = df[df["player_id"] == s["player_id"]].iloc[0]
        st.markdown(
            f"**{i}. {r['name']}** — {r['position']}, {int(r['age'])} años · "
            f"Score {r['undervaluation']:.3f}"
        )
        ds = common.drivers(r)
        if ds:
            st.caption("Por qué está acá: " + " · ".join(ds[:2]))

st.divider()
common.nav_link("pages/radar.py", "Ver el radar completo (capa cuantitativa)")
common.nav_link("pages/metodologia.py", "Cómo se calcula el score — y qué NO mide")
