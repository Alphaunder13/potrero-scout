"""
normalize.py — Paso 1 de la metrica: stats crudas -> percentiles por posicion.

Transparente a proposito:
  1) Agrupamos posiciones similares en POOLS, para que cada pool tenga
     suficientes jugadores para comparar (con 36 equipos hay de sobra; con la
     muestra chica los pools quedan flacos, pero la logica es la misma).
  2) Exigimos un minimo de minutos para entrar al pool de comparacion
     (resuelve el ruido de muestra chica: 185' marcando "mucho" no cuenta).
  3) Cada stat se convierte a PERCENTIL dentro de su pool (0-1, mas alto = mejor
     respecto a sus pares de esa posicion).
"""
from __future__ import annotations

import pandas as pd

# --- Agrupacion de posiciones (la etiqueta cruda de Transfermarkt -> pool) ---
# Juntamos posiciones con rol ofensivo parecido para que el percentil compare
# peras con peras.
POSITION_POOLS: dict[str, str] = {
    "Goalkeeper": "GK",
    "Centre-Back": "CB",
    "Left-Back": "FB", "Right-Back": "FB",
    "Defensive Midfield": "CM", "Central Midfield": "CM",
    "Attacking Midfield": "ATT", "Left Winger": "ATT", "Right Winger": "ATT",
    "Left Midfield": "ATT", "Right Midfield": "ATT", "Second Striker": "ATT",
    "Centre-Forward": "FW",
}

# Stats que percentilamos (las que tenemos del conector de TM).
STATS = ["goals_90", "assists_90"]

DEFAULT_MIN_MINUTES = 500  # umbral para entrar al pool de comparacion
DEFAULT_MIN_POOL = 5       # tamano minimo de pool para que el percentil signifique algo


def position_pool(position: str | None) -> str:
    """Mapea la posicion cruda de TM a su pool. Desconocidas -> 'OTHER'."""
    if not position:
        return "OTHER"
    return POSITION_POOLS.get(position.strip(), "OTHER")


def add_percentiles(
    df: pd.DataFrame,
    min_minutes: int = DEFAULT_MIN_MINUTES,
    min_pool: int = DEFAULT_MIN_POOL,
) -> pd.DataFrame:
    """Agrega: pos_pool, in_pool, pool_size, rankable, y <stat>_pct por pool.

    Dos guardas, ambas anti-relleno (no fabricamos numeros):
      - in_pool:  exige minutos minimos (umbral de muestra).
      - rankable: ademas exige que el pool tenga >= min_pool jugadores. Un pool
        de 1-2 daria percentil 1.0 "de regalo" (un central solo seria el mejor
        del mundo). A esos los marcamos rankable=False y su percentil queda en
        NaN: datos insuficientes para rankear, NO un valor inventado.
    """
    out = df.copy()
    out["pos_pool"] = out["position"].map(position_pool)
    out["in_pool"] = out["minutes"].fillna(0) >= min_minutes

    # tamano de cada pool contando solo a los que cumplen minutos
    counts = out.loc[out["in_pool"], "pos_pool"].value_counts()
    out["pool_size"] = out["pos_pool"].map(counts).fillna(0).astype(int)
    out["rankable"] = out["in_pool"] & (out["pool_size"] >= min_pool)

    for stat in STATS:
        out[f"{stat}_pct"] = pd.NA

    # percentil SOLO entre rankeables (pools suficientemente grandes)
    rank_rows = out[out["rankable"]]
    for stat in STATS:
        pct = rank_rows.groupby("pos_pool")[stat].rank(pct=True)
        out.loc[pct.index, f"{stat}_pct"] = pct
    return out


def pool_sizes(df: pd.DataFrame) -> pd.Series:
    """Cuantos jugadores califican por pool (para chequear que no esten vacios)."""
    return df[df["in_pool"]].groupby("pos_pool").size().sort_values(ascending=False)


def insufficient_players(df: pd.DataFrame) -> pd.DataFrame:
    """Jugadores que cumplen minutos pero cuyo pool es muy chico para rankear."""
    return df[df["in_pool"] & ~df["rankable"]]
