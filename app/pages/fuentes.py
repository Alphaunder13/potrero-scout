"""Fuentes — politica de fuentes y procedencia de los datos (spec V2 §5)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import common  # noqa: E402

import streamlit as st  # noqa: E402

st.title("Fuentes")
meta = common.load_snapshot_meta()
st.caption(common.snapshot_caption(meta))

st.markdown("""
## Política de fuentes

1. **Cada dato clave lleva URL de fuente y fecha de consulta.**
2. **Sin fuente, el dato no se publica.** Un hueco honesto vale más que un dato
   sin respaldo.
3. **Fuentes permitidas:** Transfermarkt, Soccerway, WorldFootball, BeSoccer,
   Ceroacero, sitios oficiales de liga y clubes, comunicados y prensa
   establecida. Video público solo como apoyo cualitativo referenciado.
4. **Nada de scraping agresivo:** la capa verificada se carga a mano, dato por
   dato. La automatización solo sobre lo que los términos de servicio permitan.
5. **La fecha de actualización es visible** en cada ficha y en la portada.
""")

st.divider()
st.markdown("## Procedencia del dato actual")

if meta:
    filas = [
        ("Fuente", meta.get("source", "—")),
        ("Liga", meta.get("league", "—")),
        ("Temporada", meta.get("season", "—")),
        ("Jugadores en la liga", meta.get("total_league_players", "—")),
        ("Jugadores con estadísticas", meta.get("players_with_stats", "—")),
    ]
    for k, v in filas:
        st.markdown(f"- **{k}:** {v}")
    st.markdown(
        "La capa cuantitativa completa proviene de **Transfermarkt** (scraping "
        "respetuoso: dos fases, *rate-limiting*, caché local; ver el detalle en "
        "las decisiones de arquitectura del repositorio). Los valores de mercado "
        "de Transfermarkt son estimaciones de su comunidad: acá se usan como "
        "**señal de contexto**, no como tasación."
    )
else:
    st.warning("Fecha de datos no disponible: falta la metadata del snapshot.")

st.divider()
st.caption(
    "La capa verificada a mano —con URL de fuente y fecha de consulta por cada "
    "dato de cada jugador del top-15— está en construcción."
)
