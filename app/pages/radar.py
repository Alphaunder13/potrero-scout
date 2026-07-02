"""Radar — capa cuantitativa completa (en construccion en este paso)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import common  # noqa: E402

import streamlit as st  # noqa: E402

st.title("Radar")
st.caption(common.snapshot_caption(common.load_snapshot_meta()))
st.info("Sección en construcción.")
