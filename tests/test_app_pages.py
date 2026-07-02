"""
Tests de la app multipage V2 (Bloque 1).

Cubre: las 4 paginas renderizan sin excepciones, la linea de procedencia
(ADR 0009: fecha explicita o "no disponible", nunca inferida), el etiquetado de
la capa cuantitativa, y que la vista publica (sin .env) no expone el boton de IA.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from streamlit.testing.v1 import AppTest  # noqa: E402

import common  # noqa: E402

PAGES = ["pages/home.py", "pages/radar.py", "pages/metodologia.py", "pages/fuentes.py"]


@pytest.mark.parametrize("page", PAGES)
def test_pagina_renderiza_sin_excepciones(page):
    at = AppTest.from_file(str(APP / page), default_timeout=30).run()
    assert not at.exception


def test_entrypoint_router_renderiza_home():
    at = AppTest.from_file(str(APP / "streamlit_app.py"), default_timeout=30).run()
    assert not at.exception
    assert any("talento infravalorado" in t.value for t in at.title)


def test_home_muestra_edicion_y_top5():
    at = AppTest.from_file(str(APP / "pages/home.py"), default_timeout=30).run()
    caps = " ".join(c.value for c in at.caption)
    assert "temporada 2025" in caps
    assert "capturados 27–29 jun 2026" in caps
    assert any("Top 5" in s.value for s in at.subheader)


def test_radar_etiqueta_capa_cuantitativa():
    at = AppTest.from_file(str(APP / "pages/radar.py"), default_timeout=30).run()
    md = " ".join(m.value for m in at.markdown)
    assert "Capa cuantitativa — 259" in md
    assert len(at.dataframe) >= 1


def test_vista_publica_sin_boton_ia(monkeypatch):
    """En la nube (sin .env) el boton de generacion en vivo NO se expone."""
    monkeypatch.setattr(common, "IS_LOCAL", False)
    at = AppTest.from_file(str(APP / "pages/radar.py"), default_timeout=30).run()
    assert not at.exception
    assert not any("Generar informe" in (b.label or "") for b in at.button)
    caps = " ".join(c.value for c in at.caption)
    assert "en construcción" in caps


# --- Procedencia del snapshot (ADR 0009): unidad pura -------------------------
def test_procedencia_archivo_faltante():
    """Sin metadata -> 'no disponible'. Nunca una fecha inferida o hardcodeada."""
    assert "no disponible" in common.snapshot_caption(None).lower()


def test_procedencia_formato_exacto():
    meta = {"season": "2025",
            "scrape_started": "2026-06-27", "scrape_completed": "2026-06-29"}
    assert common.snapshot_caption(meta) == \
        "Datos: temporada 2025 · capturados 27–29 jun 2026"


def test_procedencia_solo_built_at():
    """Corridas futuras: sin rango de captura, cae a 'actualizados' (honesto)."""
    meta = {"season": "2026", "built_at": "2026-08-12"}
    assert common.snapshot_caption(meta) == \
        "Datos: temporada 2026 · actualizados 12 ago 2026"


def test_procedencia_sin_fechas():
    meta = {"season": "2025"}
    out = common.snapshot_caption(meta)
    assert "fecha de captura no disponible" in out


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
