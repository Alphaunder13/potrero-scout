"""
streamlit_app.py — Entrypoint de Potrero Scout V2 (Talent Gap Radar).

Router multipage (st.navigation + st.Page, Streamlit >= 1.36). El contenido
vive en app/views/*; los helpers compartidos en app/common.py.

Correr:  streamlit run app/streamlit_app.py
"""
import streamlit as st

st.set_page_config(
    page_title="Potrero Scout — Radar de talento del ascenso",
    layout="wide",
)

pages = [
    st.Page("views/home.py", title="Home", default=True),
    st.Page("views/radar.py", title="Radar"),
    st.Page("views/metodologia.py", title="Metodología"),
    st.Page("views/fuentes.py", title="Fuentes"),
]

st.navigation(pages).run()
