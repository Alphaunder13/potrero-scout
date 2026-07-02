"""
common.py — Utilidades compartidas de la app multipage (V2 Talent Gap Radar).

Centraliza: rutas, carga del dataset con la metrica aplicada, la metadata de
procedencia del snapshot (ADR 0009), y helpers de presentacion.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
for _p in (ROOT / "analysis", ROOT / "reports"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import normalize as nz       # noqa: E402
import undervaluation as uv  # noqa: E402
import talent_gap as tg      # noqa: E402

DB_PATH = ROOT / "db" / "scout.db"
META_PATH = ROOT / "data" / "snapshot_meta.json"

# Local vs nube: el .env existe en local (gitignored) y NUNCA en Streamlit Cloud.
load_dotenv(ROOT / ".env")
IS_LOCAL = (ROOT / ".env").exists()
HAS_KEY = bool(os.getenv("ANTHROPIC_API_KEY"))

_MES = {1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
        7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic"}


# ---------------------------------------------------------------------------
# Procedencia del snapshot (ADR 0009)
# ---------------------------------------------------------------------------
def load_snapshot_meta() -> dict | None:
    """Lee data/snapshot_meta.json. None si no existe o no parsea."""
    try:
        return json.loads(META_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def _rango(a_iso: str, b_iso: str) -> str:
    a, b = date.fromisoformat(a_iso), date.fromisoformat(b_iso)
    if a == b:
        return f"{a.day} {_MES[a.month]} {a.year}"
    if (a.year, a.month) == (b.year, b.month):
        return f"{a.day}–{b.day} {_MES[a.month]} {a.year}"
    if a.year == b.year:
        return f"{a.day} {_MES[a.month]} – {b.day} {_MES[b.month]} {a.year}"
    return f"{a.day} {_MES[a.month]} {a.year} – {b.day} {_MES[b.month]} {b.year}"


def snapshot_caption(meta: dict | None) -> str:
    """Linea de procedencia para la UI. NUNCA infiere ni hardcodea fechas:
    si la metadata falta, lo dice."""
    if not meta:
        return "Fecha de datos no disponible."
    partes = []
    if meta.get("season"):
        partes.append(f"temporada {meta['season']}")
    ini, fin = meta.get("scrape_started"), meta.get("scrape_completed")
    if ini and fin:
        partes.append(f"capturados {_rango(ini, fin)}")
    elif meta.get("built_at"):
        b = date.fromisoformat(meta["built_at"])
        partes.append(f"actualizados {b.day} {_MES[b.month]} {b.year}")
    else:
        partes.append("fecha de captura no disponible")
    return "Datos: " + " · ".join(partes)


# ---------------------------------------------------------------------------
# Datos + metrica
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_scored(min_minutes: int = nz.DEFAULT_MIN_MINUTES,
                min_pool: int = nz.DEFAULT_MIN_POOL) -> pd.DataFrame:
    """Dataset completo con percentiles y scores aplicados."""
    with sqlite3.connect(DB_PATH) as con:
        df = pd.read_sql("SELECT * FROM players", con)
    df = nz.add_percentiles(df, min_minutes=min_minutes, min_pool=min_pool)
    return uv.score(df)


@st.cache_data(show_spinner=False)
def load_tgs(min_minutes: int = nz.DEFAULT_MIN_MINUTES,
             min_pool: int = nz.DEFAULT_MIN_POOL) -> pd.DataFrame:
    """Dataset completo con la metrica + Talent Gap Score (subscores 0-100)."""
    return tg.compute_tgs(load_scored(min_minutes, min_pool))


def drivers(r) -> list[str]:
    """2-3 lineas de 'por que esta aca', trazables a numeros (reglas en
    analysis/talent_gap.py)."""
    return tg.drivers(r)


# ---------------------------------------------------------------------------
# Presentacion
# ---------------------------------------------------------------------------
def euros(v) -> str:
    return f"€{int(v):,}" if pd.notna(v) else "—"


def nav_link(page: str, label: str) -> None:
    """st.page_link con fallback (fuera del contexto de st.navigation,
    ej. AppTest de una pagina suelta, page_link no resuelve)."""
    try:
        st.page_link(page, label=label)
    except Exception:
        st.caption(label)
