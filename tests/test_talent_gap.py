"""
Tests del Talent Gap Score (Bloque 3).

Cubre: suma de pesos = 1, determinismo, subscores presentes y acotados, TGS
entero, exclusion con razon del jugador bajo umbral, sanidad de la brecha de
mercado, y confianza como dimension separada (ADR 0010).
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))

import normalize as nz       # noqa: E402
import undervaluation as uv  # noqa: E402
import talent_gap as tg      # noqa: E402

SUBS = ["sub_produccion", "sub_brecha", "sub_uso", "sub_edad"]


def _toy_df() -> pd.DataFrame:
    """Pool de delanteros suficiente + un jugador bajo umbral de minutos."""
    base = dict(position="Centre-Forward")
    return pd.DataFrame([
        dict(player_id=1, name="Barato", age=19, minutes=1500,
             market_value_eur=100_000, goals_90=0.60, assists_90=0.30, **base),
        dict(player_id=2, name="Caro", age=19, minutes=1500,
             market_value_eur=2_000_000, goals_90=0.60, assists_90=0.30, **base),
        dict(player_id=3, name="F1", age=24, minutes=1200,
             market_value_eur=800_000, goals_90=0.40, assists_90=0.20, **base),
        dict(player_id=4, name="F2", age=25, minutes=1000,
             market_value_eur=600_000, goals_90=0.30, assists_90=0.10, **base),
        dict(player_id=5, name="F3", age=22, minutes=900,
             market_value_eur=400_000, goals_90=0.20, assists_90=0.15, **base),
        dict(player_id=6, name="PocoMinuto", age=18, minutes=120,
             market_value_eur=50_000, goals_90=1.50, assists_90=0.75, **base),
    ])


def _pipeline(df):
    return tg.compute_tgs(uv.score(nz.add_percentiles(df)))


def test_pesos_suman_uno():
    assert abs(sum(tg.TGS_WEIGHTS.values()) - 1.0) < 1e-9


def test_determinismo():
    """Mismos datos -> mismo score, siempre."""
    a = _pipeline(_toy_df())
    b = _pipeline(_toy_df())
    pd.testing.assert_series_equal(a["tgs"], b["tgs"])
    for s in SUBS:
        pd.testing.assert_series_equal(a[s], b[s])


def test_subscores_presentes_y_acotados():
    df = _pipeline(_toy_df())
    rankeables = df[df["rankable"]]
    for s in SUBS:
        assert s in df.columns
        assert rankeables[s].between(0, 100).all(), f"{s} fuera de [0,100]"


def test_tgs_es_entero_en_rango():
    df = _pipeline(_toy_df())
    vals = df.loc[df["rankable"], "tgs"]
    assert vals.notna().all()
    assert (vals == vals.round()).all()
    assert vals.between(0, 100).all()


def test_bajo_umbral_excluido_con_razon():
    df = _pipeline(_toy_df())
    r = df[df["name"] == "PocoMinuto"].iloc[0]
    assert pd.isna(r["tgs"])
    assert "umbral de minutos" in r["exclusion_reason"]
    # y los rankeables no tienen razon de exclusion
    assert df.loc[df["rankable"], "exclusion_reason"].isna().all()


def test_brecha_favorece_al_barato():
    """Mismo rendimiento, mitad de precio -> mayor brecha y mayor TGS."""
    df = _pipeline(_toy_df()).set_index("name")
    assert df.loc["Barato", "sub_brecha"] > df.loc["Caro", "sub_brecha"]
    assert df.loc["Barato", "tgs"] > df.loc["Caro", "tgs"]


def test_drivers_trazables():
    df = _pipeline(_toy_df())
    r = df[df["name"] == "Barato"].iloc[0]
    ds = tg.drivers(r)
    assert 1 <= len(ds) <= 3
    # cada driver debe contener al menos un numero (trazable a un dato)
    assert all(any(ch.isdigit() for ch in d) for d in ds)


def test_confianza_fuera_del_score():
    """ADR 0010: sin capa manual -> 'sin verificar'; con A -> 'A'; basura -> 'sin verificar'."""
    vacia = pd.DataFrame()
    assert tg.confidence_for(1, vacia) == tg.CONFIDENCE_UNSET

    manual = pd.DataFrame([
        {"player_id": 1, "data_confidence": "A"},
        {"player_id": 2, "data_confidence": ""},
        {"player_id": 3, "data_confidence": "X"},
    ])
    assert tg.confidence_for(1, manual) == "A"
    assert tg.confidence_for(2, manual) == tg.CONFIDENCE_UNSET
    assert tg.confidence_for(3, manual) == tg.CONFIDENCE_UNSET
    assert tg.confidence_for(99, manual) == tg.CONFIDENCE_UNSET  # no esta en el CSV

    # y la confianza NO altera el TGS: el calculo no consume la capa manual
    df1 = _pipeline(_toy_df())
    assert "data_confidence" not in df1.columns


def test_manual_layer_faltante_no_rompe(tmp_path):
    assert tg.load_manual_layer(tmp_path / "no_existe.csv").empty


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
