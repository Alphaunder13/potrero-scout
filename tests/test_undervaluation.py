"""
Tests basicos de la metrica de infravaloracion.

Regla central a validar: un jugador con percentil de rendimiento ALTO, valor de
mercado BAJO y edad JOVEN debe rankear arriba de la shortlist.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

# permitir importar los modulos de analysis/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))

import normalize as nz       # noqa: E402
import undervaluation as uv  # noqa: E402


def _toy_df() -> pd.DataFrame:
    """Pool de delanteros + dos sub-23 (una 'gema' y un 'mediocre')."""
    return pd.DataFrame([
        # gema: joven, barata, goleadora
        dict(player_id=1, name="Gema",     age=19, position="Centre-Forward",
             minutes=1500, market_value_eur=200_000,  goals_90=0.90, assists_90=0.50),
        dict(player_id=2, name="CaroBueno", age=25, position="Centre-Forward",
             minutes=1500, market_value_eur=2_000_000, goals_90=0.80, assists_90=0.40),
        dict(player_id=3, name="Veterano",  age=28, position="Centre-Forward",
             minutes=1500, market_value_eur=1_500_000, goals_90=0.50, assists_90=0.30),
        dict(player_id=4, name="Medio",     age=24, position="Centre-Forward",
             minutes=1500, market_value_eur=800_000,   goals_90=0.30, assists_90=0.20),
        dict(player_id=5, name="Flojo",     age=30, position="Centre-Forward",
             minutes=1500, market_value_eur=3_000_000, goals_90=0.10, assists_90=0.10),
        # sub-23 pero malo y caro: debe quedar por debajo de la gema
        dict(player_id=6, name="JovenMalo", age=22, position="Centre-Forward",
             minutes=1500, market_value_eur=1_200_000, goals_90=0.20, assists_90=0.10),
        # poco minutaje: debe quedar excluido del pool
        dict(player_id=7, name="PocoMinuto", age=20, position="Centre-Forward",
             minutes=120, market_value_eur=150_000,  goals_90=2.00, assists_90=1.00),
    ])


def _pipeline(df, min_minutes=500):
    df = nz.add_percentiles(df, min_minutes=min_minutes)
    return uv.score(df)


def test_gema_rankea_primera():
    """Alto rendimiento + valor bajo + joven => tope de la shortlist."""
    df = _pipeline(_toy_df())
    sl = uv.shortlist(df, sub_age=23, top_n=10)
    assert sl.iloc[0]["name"] == "Gema"
    # y debe estar por encima del joven malo
    nombres = list(sl["name"])
    assert nombres.index("Gema") < nombres.index("JovenMalo")


def test_umbral_minutos_excluye():
    """Un jugador por debajo del umbral no entra al pool ni a la shortlist."""
    df = _pipeline(_toy_df(), min_minutes=500)
    fila = df[df["name"] == "PocoMinuto"].iloc[0]
    assert fila["in_pool"] == False  # noqa: E712
    assert pd.isna(fila["undervaluation"])
    sl = uv.shortlist(df, sub_age=23)
    assert "PocoMinuto" not in set(sl["name"])


def test_a_menor_valor_mayor_score():
    """A igualdad de lo demas, mas barato => mayor infravaloracion.
    (Pool de 5 para pasar el guard: comparamos barato vs caro dentro de el.)"""
    base = dict(position="Centre-Forward", minutes=1500, age=21,
                goals_90=0.50, assists_90=0.30)
    df = pd.DataFrame([
        dict(player_id=1, name="Barato", market_value_eur=300_000, **base),
        dict(player_id=2, name="Caro",   market_value_eur=3_000_000, **base),
        dict(player_id=3, name="Fill1",  market_value_eur=1_000_000, **base),
        dict(player_id=4, name="Fill2",  market_value_eur=1_500_000, **base),
        dict(player_id=5, name="Fill3",  market_value_eur=2_000_000, **base),
    ])
    df = _pipeline(df)
    s_barato = df[df["name"] == "Barato"]["undervaluation"].iloc[0]
    s_caro = df[df["name"] == "Caro"]["undervaluation"].iloc[0]
    assert s_barato > s_caro


def test_mas_joven_mayor_juventud():
    """El componente de juventud decrece con la edad."""
    w = uv.Weights()
    assert uv._youth(18, w) > uv._youth(21, w) > uv._youth(23, w) == 0.0


def test_guard_pool_chico_no_inventa_percentil():
    """Un pool con < min_pool jugadores: rankable=False, percentil NA (no 1.0
    fabricado) y fuera de la shortlist principal."""
    base_fw = _toy_df().iloc[:6]  # 6 delanteros: pool suficiente
    cbs = pd.DataFrame([
        dict(player_id=10, name="CB_top", age=20, position="Centre-Back",
             minutes=1500, market_value_eur=300_000, goals_90=0.40, assists_90=0.20),
        dict(player_id=11, name="CB_mid", age=21, position="Centre-Back",
             minutes=1500, market_value_eur=500_000, goals_90=0.10, assists_90=0.10),
        dict(player_id=12, name="CB_low", age=22, position="Centre-Back",
             minutes=1500, market_value_eur=400_000, goals_90=0.00, assists_90=0.05),
    ])  # solo 3 centrales -> pool < 5
    df = _pipeline(pd.concat([base_fw, cbs], ignore_index=True))  # min_pool=5 default

    cb_top = df[df["name"] == "CB_top"].iloc[0]
    assert cb_top["pool_size"] == 3
    assert cb_top["rankable"] == False                 # noqa: E712
    assert pd.isna(cb_top["goals_90_pct"])             # NO le inventamos 1.0
    assert pd.isna(cb_top["undervaluation"])
    # ningun central entra a la shortlist principal
    sl = uv.shortlist(df, sub_age=23, top_n=20)
    assert not set(sl["name"]) & {"CB_top", "CB_mid", "CB_low"}
    # pero los delanteros (pool de 6) si son rankeables
    assert df[df["name"] == "Gema"].iloc[0]["rankable"] == True  # noqa: E712


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
