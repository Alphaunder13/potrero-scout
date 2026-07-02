"""Home — el hallazgo primero, el metodo a un clic (spec V2 §3)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import common  # noqa: E402

import pandas as pd     # noqa: E402
import streamlit as st  # noqa: E402
import talent_gap as tg  # noqa: E402

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

df = common.load_tgs()
manual = tg.load_manual_layer()
top5 = (df[(df["age"] < 23) & df["tgs"].notna()]
        .sort_values("tgs", ascending=False).head(5))

if top5.empty:
    st.warning("No hay jugadores rankeables en esta edición.")
else:
    for i, (_, r) in enumerate(top5.iterrows(), start=1):
        conf = tg.confidence_for(r["player_id"], manual)
        mrow = tg.manual_row_for(r["player_id"], manual)
        club = ""
        if mrow is not None and str(mrow.get("club") or "").strip():
            club = f" ({mrow['club']})"
        st.markdown(
            f"**{i}. {r['name']}**{club} — {r['position']}, {int(r['age'])} años · "
            f"**TGS {int(r['tgs'])}** · confianza: {conf}"
        )
        ds = common.drivers(r)
        if ds:
            st.caption("Por qué está acá: " + " · ".join(ds[:2]))

st.divider()
common.nav_link("views/radar.py", "Ver el radar completo (las dos capas)")
common.nav_link("views/metodologia.py", "Cómo se calcula el score — y qué NO mide")
