"""
run_metric.py — Corre la metrica de infravaloracion sobre el dataset en SQLite
y muestra: pools, shortlist sub-23, y el desglose de 1-2 jugadores.

Uso:
    python analysis/run_metric.py --min-minutes 500 --top 10 --sub-age 23
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pandas as pd

import normalize as nz
import undervaluation as uv

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "scout.db"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-minutes", type=int, default=nz.DEFAULT_MIN_MINUTES)
    ap.add_argument("--min-pool", type=int, default=nz.DEFAULT_MIN_POOL)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--sub-age", type=int, default=23)
    args = ap.parse_args()

    with sqlite3.connect(DB_PATH) as con:
        df = pd.read_sql("SELECT * FROM players", con)
    print(f"Dataset: {len(df)} jugadores desde {DB_PATH.name}")

    # Paso 1: percentiles por pool, con umbral de minutos + guard de pool minimo
    df = nz.add_percentiles(df, min_minutes=args.min_minutes, min_pool=args.min_pool)
    excl = df[~df["in_pool"]]
    print(f"\nUmbral de minutos: {args.min_minutes}'  ->  "
          f"{df['in_pool'].sum()} califican, {len(excl)} excluidos")
    if len(excl):
        print("  Excluidos por pocos minutos (caso Ferreyra resuelto):")
        for _, r in excl.iterrows():
            print(f"    - {r['name']} ({int(r['minutes'])}')")
    print("\nTamano de pools (jugadores calificados por posicion):")
    for pool, n in nz.pool_sizes(df).items():
        print(f"    {pool}: {n}")

    # Guard de pool minimo: datos insuficientes para rankear (NO se inventa 1.0)
    insuf = nz.insufficient_players(df)
    if len(insuf):
        print(f"\n[GUARD] pool < {args.min_pool} -> 'datos insuficientes para rankear' "
              f"({len(insuf)}, fuera de la shortlist principal):")
        for _, r in insuf.iterrows():
            print(f"    - {r['name']} ({r['position']} / pool {r['pos_pool']}="
                  f"{r['pool_size']})  [percentil = NA, no fabricado]")

    # Paso 2: scores
    w = uv.Weights()
    df = uv.score(df, w)

    print(f"\nPesos de infravaloracion: w_perf={w.w_perf} w_cheap={w.w_cheap} "
          f"w_youth={w.w_youth} | bonus_proy<= {w.proj_max} (pico {w.proj_peak})")

    # Tabla completa de calificados (para ver la logica, no solo los sub-23)
    print("\n=== Pool calificado, ordenado por infravaloracion ===")
    scored = df[df["undervaluation"].notna()].sort_values("undervaluation", ascending=False)
    show = ["name", "age", "pos_pool", "minutes", "market_value_eur",
            "performance", "cheapness", "youth", "proj_bonus", "undervaluation"]
    with pd.option_context("display.width", 200, "display.max_columns", None):
        print(scored[show].to_string(index=False))

    # Shortlist sub-23
    sl = uv.shortlist(df, sub_age=args.sub_age, top_n=args.top)
    print(f"\n=== SHORTLIST: top-{args.top} sub-{args.sub_age} infravalorados ===")
    cols = ["name", "age", "position", "minutes", "market_value_eur",
            "performance", "undervaluation"]
    with pd.option_context("display.width", 200, "display.max_columns", None):
        print(sl[cols].to_string(index=False) if len(sl) else "  (vacio)")

    # Desglose de 1-2 jugadores para validar la logica a mano
    print("\n=== Desglose del calculo (validacion manual) ===")
    targets = list(scored["name"].head(2))
    for nm in targets:
        print(uv.explain_player(df, nm, w))
        print()


if __name__ == "__main__":
    main()
