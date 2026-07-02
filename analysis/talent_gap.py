"""
talent_gap.py — Talent Gap Score (TGS, 0-100) con subscores explicables.

Envuelve la logica YA validada (percentiles por pool de posicion, pesos
posicionales, guard de pool minimo, umbral de minutos) sin reescribirla: toma la
salida de normalize.add_percentiles + undervaluation.score y la reorganiza en
cuatro subscores 0-100 mas un total entero.

Subscores:
  - Produccion (30%): percentil de produccion ofensiva por 90' dentro del pool,
    con los pesos por posicion existentes (= performance * 100).
  - Brecha de mercado (35%): diferencia normalizada entre el percentil de
    produccion y el percentil de valor de mercado EN EL POOL. El corazon del gap.
  - Uso (20%): percentil de minutos jugados en el pool.
  - Recorrido de edad (15%): mapeo lineal de la edad (mas joven = mas recorrido),
    reutilizando el factor de edad existente de undervaluation.

Decision de diseño (ADR 0010): la confianza A/B/C NO entra en la formula. Se lee
de la capa manual (data/radar_manual.csv) y se muestra SIEMPRE como dimension
separada; sin asignar -> "sin verificar", nunca un default.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

import normalize as nz
import undervaluation as uv

ROOT = Path(__file__).resolve().parent.parent
MANUAL_CSV = ROOT / "data" / "radar_manual.csv"

# Pesos del TGS. Deben sumar 1 (hay un test que lo garantiza).
TGS_WEIGHTS = {"brecha": 0.35, "produccion": 0.30, "uso": 0.20, "edad": 0.15}

# Nombre legible de cada pool para los drivers ("entre laterales del pool").
POOL_LABEL = {"FW": "delanteros", "ATT": "extremos/enganches", "CM": "volantes",
              "FB": "laterales", "CB": "centrales", "GK": "arqueros",
              "OTHER": "jugadores"}

CONFIDENCE_UNSET = "sin verificar"


# ---------------------------------------------------------------------------
# Calculo del TGS
# ---------------------------------------------------------------------------
def compute_tgs(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega subscores 0-100, tgs (entero) y exclusion_reason.

    `df` es la salida de nz.add_percentiles + uv.score. Solo los jugadores
    `rankable` reciben TGS; el resto queda excluido con la razon explicita
    (misma filosofia del guard: no fabricar numeros donde no significan nada).
    """
    out = df.copy()
    w = uv.Weights()
    rank_rows = out[out["rankable"]]

    # Percentiles de valor y minutos DENTRO del pool, solo entre rankeables.
    val_pct = rank_rows.groupby("pos_pool")["market_value_eur"].rank(pct=True)
    min_pct = rank_rows.groupby("pos_pool")["minutes"].rank(pct=True)
    out.loc[val_pct.index, "value_pct_pool"] = val_pct
    out.loc[min_pct.index, "minutes_pct_pool"] = min_pct

    out["sub_produccion"] = (pd.to_numeric(out["performance"], errors="coerce") * 100).round(1)
    # Brecha cruda en [-1, 1] -> normalizada a [0, 100]
    brecha_raw = pd.to_numeric(out["performance"], errors="coerce") - out["value_pct_pool"]
    out["sub_brecha"] = ((brecha_raw + 1) / 2 * 100).round(1)
    out["sub_uso"] = (out["minutes_pct_pool"] * 100).round(1)
    out["sub_edad"] = out["age"].map(lambda a: round(uv._youth(a, w) * 100, 1))

    tgs = (TGS_WEIGHTS["brecha"] * out["sub_brecha"]
           + TGS_WEIGHTS["produccion"] * out["sub_produccion"]
           + TGS_WEIGHTS["uso"] * out["sub_uso"]
           + TGS_WEIGHTS["edad"] * out["sub_edad"])
    out["tgs"] = tgs.round().astype("Int64")
    out.loc[~out["rankable"], "tgs"] = pd.NA

    def _reason(r):
        if r["rankable"]:
            return None
        if not r["in_pool"]:
            return (f"bajo el umbral de minutos ({int(r['minutes'] or 0)}′ "
                    f"< {nz.DEFAULT_MIN_MINUTES}′)")
        return (f"pool de posición demasiado chico "
                f"({int(r['pool_size'])} < {nz.DEFAULT_MIN_POOL} jugadores)")
    out["exclusion_reason"] = out.apply(_reason, axis=1)
    return out


def subscores(r) -> dict[str, float]:
    """Los 4 subscores de una fila, con sus pesos, listos para mostrar."""
    return {
        "Brecha de mercado (35%)": float(r["sub_brecha"]),
        "Producción (30%)": float(r["sub_produccion"]),
        "Uso (20%)": float(r["sub_uso"]),
        "Recorrido de edad (15%)": float(r["sub_edad"]),
    }


# ---------------------------------------------------------------------------
# Drivers y señales por reglas — cada frase trazable a un numero
# ---------------------------------------------------------------------------
def positive_signals(r, max_n: int = 3) -> list[str]:
    """Señales positivas EN LOS DATOS (sin juicio de scout)."""
    out: list[str] = []
    pool = POOL_LABEL.get(r.get("pos_pool"), "jugadores")
    g, a = r.get("goals_90_pct"), r.get("assists_90_pct")
    if pd.notna(a) and float(a) >= 0.60:
        out.append(f"percentil {round(float(a) * 100)} en asistencias/90 "
                   f"entre {pool} del pool ({float(r['assists_90']):.3f}/90)")
    if pd.notna(g) and float(g) >= 0.60:
        out.append(f"percentil {round(float(g) * 100)} en goles/90 "
                   f"entre {pool} del pool ({float(r['goals_90']):.3f}/90)")
    vp = r.get("value_pct_pool")
    if pd.notna(vp) and float(vp) <= 0.40 and pd.notna(r.get("market_value_eur")):
        out.append(f"valor de mercado en el percentil {round(float(vp) * 100)} "
                   f"de su pool (€{int(r['market_value_eur']):,})")
    if pd.notna(r.get("sub_brecha")) and float(r["sub_brecha"]) >= 75:
        out.append(f"brecha de mercado {r['sub_brecha']:.0f}/100: produce por "
                   "encima de lo que cuesta dentro de su pool")
    return out[:max_n]


def risk_signals(r, max_n: int = 3) -> list[str]:
    """Señales de riesgo EN LOS DATOS. La limitacion de muestra va SIEMPRE
    que aplique."""
    out: list[str] = []
    minutes = r.get("minutes")
    if pd.notna(minutes) and float(minutes) < 900:
        out.append(f"muestra chica: {int(minutes)}′ jugados — los por-90 y "
                   "percentiles son inestables")
    g = r.get("goals_90_pct")
    if pd.notna(g) and float(g) < 0.40:
        out.append(f"percentil {round(float(g) * 100)} en goles/90: aporte "
                   "goleador bajo dentro de su pool")
    if r.get("pos_pool") in ("CB", "FB", "GK"):
        out.append("sin datos defensivos públicos para esta liga: el núcleo "
                   "del rol no está medido")
    if pd.notna(r.get("sub_uso")) and float(r["sub_uso"]) < 30:
        out.append(f"uso bajo: percentil {r['sub_uso']:.0f} en minutos dentro "
                   "de su pool")
    return out[:max_n]


def drivers(r, max_n: int = 3) -> list[str]:
    """2-3 lineas de 'por que esta aca' para tablas y Home."""
    pos = positive_signals(r, max_n=2)
    rsk = risk_signals(r, max_n=1)
    return (pos + rsk)[:max_n]


# ---------------------------------------------------------------------------
# Capa manual: confianza como dimension separada (ADR 0010)
# ---------------------------------------------------------------------------
def load_manual_layer(path: Path | None = None) -> pd.DataFrame:
    """Lee data/radar_manual.csv. DataFrame vacio si falta o no parsea:
    la app funciona sin la capa manual, mostrando 'sin verificar'."""
    p = path or MANUAL_CSV
    try:
        return pd.read_csv(p)
    except Exception:
        return pd.DataFrame()


def confidence_for(player_id, manual: pd.DataFrame) -> str:
    """A/B/C si esta asignada en la capa manual; si no, 'sin verificar'.
    NUNCA un default que parezca dato."""
    if manual is None or manual.empty or "data_confidence" not in manual.columns:
        return CONFIDENCE_UNSET
    hit = manual[manual["player_id"] == player_id]
    if hit.empty:
        return CONFIDENCE_UNSET
    v = str(hit.iloc[0]["data_confidence"]).strip().upper()
    return v if v in ("A", "B", "C") else CONFIDENCE_UNSET


def manual_row_for(player_id, manual: pd.DataFrame):
    """Fila de la capa manual para un jugador, o None si no esta."""
    if manual is None or manual.empty:
        return None
    hit = manual[manual["player_id"] == player_id]
    return hit.iloc[0] if len(hit) else None
