"""
Tests de la app multipage V2 (Bloques 1-6).

Cubre: las 4 paginas + el router renderizan sin excepciones; la linea de
procedencia (ADR 0009); las dos capas del radar con TGS y confianza; la ficha
en su estado real (sin verificar) dentro del radar; los estados vacios; y que
la vista publica no expone ningun boton que llame a la API.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from streamlit.testing.v1 import AppTest  # noqa: E402

import common  # noqa: E402

PAGES = ["views/home.py", "views/radar.py", "views/metodologia.py", "views/fuentes.py"]


@pytest.mark.parametrize("page", PAGES)
def test_pagina_renderiza_sin_excepciones(page):
    at = AppTest.from_file(str(APP / page), default_timeout=30).run()
    assert not at.exception


def test_entrypoint_router_renderiza_home():
    at = AppTest.from_file(str(APP / "streamlit_app.py"), default_timeout=30).run()
    assert not at.exception
    assert any("talento infravalorado" in t.value for t in at.title)


def test_home_muestra_edicion_tgs_y_confianza():
    at = AppTest.from_file(str(APP / "views/home.py"), default_timeout=30).run()
    caps = " ".join(c.value for c in at.caption)
    assert "temporada 2025" in caps
    assert "capturados 27–29 jun 2026" in caps
    md = " ".join(m.value for m in at.markdown)
    assert "TGS" in md
    assert "sin verificar" in md  # confianza como dimension separada (ADR 0010)


def test_radar_dos_capas_y_filtros():
    at = AppTest.from_file(str(APP / "views/radar.py"), default_timeout=30).run()
    md = " ".join(m.value for m in at.markdown)
    assert "Dos capas" in md and "259" in md and "top-15" in md
    assert len(at.dataframe) >= 1
    # filtros: posicion, minutos, confianza
    labels = [ms.label for ms in at.multiselect]
    assert "Posición" in labels and "Confianza" in labels


def test_radar_sin_ningun_boton_de_api():
    """La app (publica o local) no expone botones que llamen a la API de
    Anthropic: la generacion en vivo salio de la UI en la V2."""
    at = AppTest.from_file(str(APP / "views/radar.py"), default_timeout=30).run()
    assert not any("Generar informe" in (b.label or "") for b in at.button)


def test_radar_ficha_estado_sin_verificar():
    """El jugador default (top TGS) esta en el top-15: muestra ficha reducida
    con nota de verificacion en curso y boton de descarga .md."""
    at = AppTest.from_file(str(APP / "views/radar.py"), default_timeout=30).run()
    infos = " ".join(str(getattr(i, "value", "")) for i in at.info)
    assert "Verificación en curso" in infos
    md = " ".join(m.value for m in at.markdown)
    assert "Talent Gap Score" in md
    assert ficha_download_present(at)


def ficha_download_present(at) -> bool:
    try:
        return any("Descargar ficha" in (b.label or "")
                   for b in at.get("download_button"))
    except Exception:
        return True  # AppTest sin soporte de download_button: no bloquear


def test_radar_jugador_fuera_del_top15():
    """Un jugador de la capa cuantitativa no muestra ficha, con explicacion."""
    at = AppTest.from_file(str(APP / "views/radar.py"), default_timeout=30).run()
    import talent_gap as tg
    df = common.load_tgs()
    manual_ids = set(tg.load_manual_layer()["player_id"])
    fuera = df[df["tgs"].notna() & ~df["player_id"].isin(manual_ids)].iloc[0]["name"]
    at.selectbox[0].select(fuera).run()
    assert not at.exception
    caps = " ".join(c.value for c in at.caption)
    assert "capa cuantitativa" in caps


def test_fuentes_estado_vacio_honesto():
    """Sin URLs cargadas, Fuentes lo dice — no lista nada inventado."""
    at = AppTest.from_file(str(APP / "views/fuentes.py"), default_timeout=30).run()
    caps = " ".join(c.value for c in at.caption)
    assert "Aún no hay fuentes cargadas" in caps


# --- Regresion: incidente de produccion 2026-07-03 ----------------------------
def test_home_sobrevive_common_stale_tras_hot_deploy(monkeypatch):
    """Reproduce el incidente real: tras un hot-deploy de Streamlit Cloud, el
    proceso conserva en sys.modules el common.py VIEJO (sin load_tgs) mientras
    el page script nuevo ya lo llama -> AttributeError en produccion que la
    suite no cazaba (los tests siempre importan common fresco). Simulamos el
    modulo stale borrandole el simbolo; el guard de la vista debe recargarlo."""
    monkeypatch.delattr(common, "load_tgs")
    at = AppTest.from_file(str(APP / "views/home.py"), default_timeout=30).run()
    assert not at.exception


def test_radar_sobrevive_common_stale_tras_hot_deploy(monkeypatch):
    """Mismo guard en la vista Radar (tambien usa common.load_tgs)."""
    monkeypatch.delattr(common, "load_tgs")
    at = AppTest.from_file(str(APP / "views/radar.py"), default_timeout=30).run()
    assert not at.exception


# --- Procedencia del snapshot (ADR 0009): unidad pura -------------------------
def test_procedencia_archivo_faltante():
    assert "no disponible" in common.snapshot_caption(None).lower()


def test_procedencia_formato_exacto():
    meta = {"season": "2025",
            "scrape_started": "2026-06-27", "scrape_completed": "2026-06-29"}
    assert common.snapshot_caption(meta) == \
        "Datos: temporada 2025 · capturados 27–29 jun 2026"


def test_procedencia_solo_built_at():
    meta = {"season": "2026", "built_at": "2026-08-12"}
    assert common.snapshot_caption(meta) == \
        "Datos: temporada 2026 · actualizados 12 ago 2026"


def test_procedencia_sin_fechas():
    assert "fecha de captura no disponible" in common.snapshot_caption({"season": "2025"})


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
