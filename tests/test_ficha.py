"""
Tests de la ficha exportable (Bloque 5): gate de publicacion y estructura.

El estado 'verificado' se prueba con una fila manual SINTETICA de test
(example.org) — nunca se cargan fuentes inventadas en el CSV real.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "analysis"))
sys.path.insert(0, str(ROOT / "reports"))

import normalize as nz       # noqa: E402
import undervaluation as uv  # noqa: E402
import talent_gap as tg      # noqa: E402
import ficha_md              # noqa: E402


def _qrow():
    """Fila cuantitativa real de pipeline (toy de 6 delanteros)."""
    base = dict(position="Centre-Forward")
    df = pd.DataFrame([
        dict(player_id=1, name="Joven Promesa", age=20, minutes=840,
             market_value_eur=50_000, goals_90=0.60, assists_90=0.30, **base),
        dict(player_id=2, name="F1", age=24, minutes=1500,
             market_value_eur=900_000, goals_90=0.50, assists_90=0.25, **base),
        dict(player_id=3, name="F2", age=25, minutes=1400,
             market_value_eur=700_000, goals_90=0.40, assists_90=0.20, **base),
        dict(player_id=4, name="F3", age=23, minutes=1300,
             market_value_eur=500_000, goals_90=0.30, assists_90=0.15, **base),
        dict(player_id=5, name="F4", age=22, minutes=1100,
             market_value_eur=300_000, goals_90=0.20, assists_90=0.10, **base),
    ])
    df = tg.compute_tgs(uv.score(nz.add_percentiles(df)))
    return df[df["name"] == "Joven Promesa"].iloc[0]


VERIFIED_ROW = {
    "player_id": 1, "player_name": "Joven Promesa", "club": "Club Test",
    "data_confidence": "B", "last_updated": "2026-07-01",
    "source_market_value": "https://example.org/valor",
    "source_minutes": "https://example.org/minutos",
    "source_profile": "https://example.org/perfil",
    "appearances": 12, "goals": 5, "assists": 3,
    "contract_until": "2027-12-31",
    "source_contract": "https://example.org/contrato",
    "context_notes": "Titular en un equipo de mitad de tabla (nota de test).",
    "source_news": "https://example.org/nota",
    "recommended_market": "Segunda division europea (hipotesis de test).",
    "positive_signals": "", "risk_signals": "", "qualitative_notes": "",
    "why_undervalued": "Produce por encima de su percentil de valor (test).",
}

UNVERIFIED_ROW = {
    "player_id": 1, "player_name": "Joven Promesa", "club": "",
    "data_confidence": "", "last_updated": "",
    "source_market_value": "", "source_minutes": "", "source_profile": "",
    "appearances": 12, "goals": 5, "assists": 3,
}


def test_gate_is_verified():
    assert ficha_md.is_verified(VERIFIED_ROW)
    assert not ficha_md.is_verified(UNVERIFIED_ROW)
    assert not ficha_md.is_verified(None)
    # confianza sin fuentes NO alcanza
    r = dict(UNVERIFIED_ROW, data_confidence="A")
    assert not ficha_md.is_verified(r)
    # fuentes sin confianza NO alcanzan
    r = dict(VERIFIED_ROW, data_confidence="")
    assert not ficha_md.is_verified(r)


def test_ficha_completa_todas_las_secciones(tmp_path):
    md = ficha_md.build_ficha_md(_qrow(), VERIFIED_ROW, provenance="Datos: test.")
    for seccion in ["# Joven Promesa", "Talent Gap Score", "Confianza: B",
                    "## Por qué está en el radar", "## Datos",
                    "## Señales positivas (en los datos)",
                    "## Señales de riesgo (en los datos)",
                    "## Contexto competitivo", "## Interpretación — Hipótesis",
                    "## Fuentes", ficha_md.DISCLAIMER, "2026-07-01",
                    "Club Test", "Contrato hasta"]:
        assert seccion in md, f"falta: {seccion}"
    # fuentes linkeadas en la tabla de datos
    assert "[fuente](https://example.org/valor)" in md
    # el archivo exportado es valido
    out = tmp_path / ficha_md.ficha_filename("Joven Promesa")
    out.write_text(md, encoding="utf-8")
    assert out.exists() and out.stat().st_size > 500


def test_ficha_reducida_sin_verificar(tmp_path):
    md = ficha_md.build_ficha_md(_qrow(), UNVERIFIED_ROW, provenance="Datos: test.")
    assert "Verificación en curso" in md
    assert "Confianza: sin verificar" in md
    # NO hay secciones manuales ni fuentes por dato
    assert "## Contexto competitivo" not in md
    assert "Hipótesis" not in md
    assert "example.org" not in md
    assert "pendiente de verificación" in md
    # el disclaimer va SIEMPRE, tambien en la reducida
    assert ficha_md.DISCLAIMER in md
    out = tmp_path / "reducida.md"
    out.write_text(md, encoding="utf-8")
    assert out.exists() and out.stat().st_size > 300


def test_limitacion_de_muestra_siempre_presente():
    """Jugador con <900' -> la señal de muestra chica aparece aunque las
    señales manuales digan otra cosa."""
    row = dict(VERIFIED_ROW, risk_signals="señal manual cualquiera")
    md = ficha_md.build_ficha_md(_qrow(), row, provenance="Datos: test.")
    assert "muestra chica: 840′" in md


def test_celdas_vacias_nunca_estimadas():
    """Sin club -> 'pendiente de verificación', jamas un valor inventado."""
    md = ficha_md.build_ficha_md(_qrow(), UNVERIFIED_ROW, provenance="Datos: test.")
    linea_encabezado = md.splitlines()[2]
    assert "pendiente de verificación" in linea_encabezado


def test_radar_url_desde_metadata(monkeypatch, tmp_path):
    """La URL del pie viene de snapshot_meta.json (fuente unica, sin valores
    magicos); si la metadata falta, el pie degrada sin inventar una URL."""
    # con la metadata real del repo: la URL aparece
    md = ficha_md.build_ficha_md(_qrow(), UNVERIFIED_ROW, provenance="Datos: test.")
    assert "streamlit.app" in md
    # sin metadata: degrada a texto, sin URL inventada
    monkeypatch.setattr(ficha_md, "META_PATH", tmp_path / "no_existe.json")
    md2 = ficha_md.build_ficha_md(_qrow(), UNVERIFIED_ROW, provenance="Datos: test.")
    assert "streamlit.app" not in md2
    assert "sección Metodología" in md2
    assert ficha_md.DISCLAIMER in md2


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
