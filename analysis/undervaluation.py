"""
undervaluation.py — Paso 2 de la metrica: score de rendimiento + infravaloracion.

Todo es una suma ponderada de numeros 0-1, documentada y configurable. Nada de
caja negra: cada jugador se puede desglosar a mano (ver explain_player()).

Cadena de calculo:
  rendimiento  = promedio ponderado de percentiles relevantes SEGUN el pool
                 (a un '9' le pesa el gol; a un lateral, la asistencia).
  baratura     = 1 - percentil de valor de mercado dentro del pool calificado
                 (mas barato respecto a sus pares = mas alto).
  juventud     = cuan por debajo de YOUTH_REF esta su edad (lineal, 0-1).
  bonus_proy   = bonus ADITIVO extra para los muy jovenes (proyeccion; pico ~26).

  infravaloracion = W_PERF*rendimiento + W_CHEAP*baratura + W_YOUTH*juventud
                    + bonus_proy
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from normalize import STATS


# --- Pesos del rendimiento por pool (cuanto pesa cada stat) ------------------
# goals_90 vs assists_90. Documentado: refleja que se le pide a cada rol.
PERF_WEIGHTS: dict[str, dict[str, float]] = {
    "FW":  {"goals_90": 0.70, "assists_90": 0.30},  # 9: gol manda
    "ATT": {"goals_90": 0.55, "assists_90": 0.45},  # extremo/enganche: mixto
    "CM":  {"goals_90": 0.40, "assists_90": 0.60},  # volante: mas asistencia
    "FB":  {"goals_90": 0.30, "assists_90": 0.70},  # lateral: aporte por asistencia
    "CB":  {"goals_90": 0.50, "assists_90": 0.50},  # central: pobre con estos stats (*)
    "GK":  {"goals_90": 0.50, "assists_90": 0.50},  # GK: no captado por estos stats (*)
    "OTHER": {"goals_90": 0.50, "assists_90": 0.50},
}
# (*) Con solo goles/asistencias, CB y GK quedan mal medidos. Es una limitacion
#     conocida de la V1 (sin datos de eventos). Queda documentada, no escondida.


@dataclass
class Weights:
    """Pesos del score de infravaloracion. Todos configurables."""
    w_perf: float = 0.50          # rendimiento
    w_cheap: float = 0.30         # valor de mercado bajo
    w_youth: float = 0.20         # juventud (lineal)
    youth_ref: int = 23          # edad de referencia: en/sobre esto, juventud=0
    youth_floor: int = 16        # edad minima realista (para escalar 0-1)
    proj_max: float = 0.10        # tope del bonus de proyeccion (aditivo)
    proj_peak: int = 26          # edad pico (heuristica de literatura ~25-27)
    perf_weights: dict = field(default_factory=lambda: PERF_WEIGHTS)


def performance_score(row, w: Weights) -> float | None:
    """Promedio ponderado de los percentiles del jugador, segun su pool."""
    pcts = {s: row.get(f"{s}_pct") for s in STATS}
    if any(pd.isna(v) for v in pcts.values()):
        return None
    weights = w.perf_weights.get(row["pos_pool"], w.perf_weights["OTHER"])
    return round(sum(weights[s] * float(pcts[s]) for s in STATS), 4)


def _youth(age, w: Weights) -> float:
    if pd.isna(age):
        return 0.0
    span = w.youth_ref - w.youth_floor
    return round(max(0.0, min(1.0, (w.youth_ref - age) / span)), 4)


def _projection_bonus(age, w: Weights) -> float:
    """Bonus aditivo: maximo en youth_floor, cero en/sobre proj_peak."""
    if pd.isna(age):
        return 0.0
    span = w.proj_peak - w.youth_floor
    frac = max(0.0, min(1.0, (w.proj_peak - age) / span))
    return round(w.proj_max * frac, 4)


def score(df: pd.DataFrame, w: Weights | None = None) -> pd.DataFrame:
    """Calcula rendimiento, baratura, juventud, bonus e infravaloracion.

    Solo sobre los jugadores in_pool (los demas no tienen percentiles validos).
    """
    w = w or Weights()
    out = df.copy()

    out["performance"] = out.apply(lambda r: performance_score(r, w), axis=1)

    # baratura: 1 - percentil de valor DENTRO de los calificados con rendimiento.
    scored = out[out["performance"].notna()].copy()
    value_pct = scored["market_value_eur"].rank(pct=True)
    out.loc[value_pct.index, "cheapness"] = (1 - value_pct).round(4)

    out["youth"] = out["age"].map(lambda a: _youth(a, w))
    out["proj_bonus"] = out["age"].map(lambda a: _projection_bonus(a, w))

    out["undervaluation"] = (
        w.w_perf * out["performance"]
        + w.w_cheap * out["cheapness"]
        + w.w_youth * out["youth"]
        + out["proj_bonus"]
    ).round(4)
    return out


def shortlist(df: pd.DataFrame, sub_age: int = 23, top_n: int = 20) -> pd.DataFrame:
    """Top-N sub-`sub_age` por score de infravaloracion (con score valido)."""
    cols = ["player_id", "name", "age", "position", "pos_pool", "minutes",
            "market_value_eur", "goals_90", "assists_90",
            "performance", "cheapness", "youth", "proj_bonus", "undervaluation"]
    elig = df[df["undervaluation"].notna() & (df["age"] < sub_age)].copy()
    return elig.sort_values("undervaluation", ascending=False).head(top_n)[cols]


def explain_player(df: pd.DataFrame, name: str, w: Weights | None = None) -> str:
    """Desglose legible de COMO se calculo el score de un jugador."""
    w = w or Weights()
    r = df[df["name"] == name].iloc[0]
    pw = w.perf_weights.get(r["pos_pool"], w.perf_weights["OTHER"])
    lines = [
        f"--- Desglose: {r['name']} ({r['position']} -> pool {r['pos_pool']}, "
        f"edad {r['age']}, {int(r['minutes'])}', valor €{int(r['market_value_eur']):,}) ---",
        "  Percentiles dentro de su pool:",
        f"    goals_90={r['goals_90']}  -> pct {r['goals_90_pct']:.3f}  (peso {pw['goals_90']})",
        f"    assists_90={r['assists_90']} -> pct {r['assists_90_pct']:.3f}  (peso {pw['assists_90']})",
        f"  => rendimiento = {pw['goals_90']}*{r['goals_90_pct']:.3f} + "
        f"{pw['assists_90']}*{r['assists_90_pct']:.3f} = {r['performance']:.4f}",
        f"  baratura (1 - pct de valor en el pool) = {r['cheapness']:.4f}",
        f"  juventud (lineal, ref {w.youth_ref}) = {r['youth']:.4f}",
        f"  bonus proyeccion (pico {w.proj_peak}) = {r['proj_bonus']:.4f}",
        f"  => infravaloracion = {w.w_perf}*{r['performance']:.3f} + "
        f"{w.w_cheap}*{r['cheapness']:.3f} + {w.w_youth}*{r['youth']:.3f} + "
        f"{r['proj_bonus']:.3f} = {r['undervaluation']:.4f}",
    ]
    return "\n".join(lines)
