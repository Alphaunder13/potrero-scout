"""
build_dataset.py — Orquestador de ingesta (Etapa de ingesta del SPEC).

Corre las dos fases del conector de Transfermarkt y unifica todo en SQLite con
el esquema-contrato del SPEC:
    player_id, name, age, position, minutes, market_value_eur, goals_90, assists_90

Fases:
  1) BARATA  : ~todos los jugadores de la liga con valor/edad/posicion (HTTP).
               Se guarda crudo en data/raw/.
  2) CARA    : filtra el pool a < MAX_AGE y saca stats (navegador) SOLO de ese
               subconjunto. --max-stats limita cuantos render para una demo.

Uso:
    python ingest/build_dataset.py --season 2025 --max-age 25 --max-stats 20
    python ingest/build_dataset.py --season 2025 --max-age 25 --max-stats 0   # 0 = sin limite (run completo, horas)
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd

import transfermarkt as tm

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
DB_PATH = ROOT / "db" / "scout.db"
for d in (RAW, CLEAN, DB_PATH.parent):
    d.mkdir(parents=True, exist_ok=True)

SCHEMA = ["player_id", "name", "age", "position", "minutes",
          "market_value_eur", "goals_90", "assists_90"]


def per90(value, minutes) -> float | None:
    if not minutes or minutes <= 0 or value is None:
        return None
    return round(value / minutes * 90, 3)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="2025")
    ap.add_argument("--max-age", type=int, default=25)
    ap.add_argument("--max-stats", type=int, default=20,
                    help="limite de jugadores para la fase cara (0 = sin limite)")
    args = ap.parse_args()

    print("=" * 78)
    print(f"INGESTA — Primera Nacional {args.season} | max_age<{args.max_age} | "
          f"max_stats={args.max_stats or 'SIN LIMITE'}")
    print("=" * 78)

    # ---- FASE 1 (barata) -----------------------------------------------------
    print("\n[FASE 1 — BARATA] plantillas (valor/edad/posicion) via HTTP...")
    squads = tm.scrape_squads(args.season)
    df_sq = pd.DataFrame(squads)
    raw_path = RAW / f"tm_squads_{args.season}.csv"
    df_sq.to_csv(raw_path, index=False, encoding="utf-8")
    print(f"  -> {len(df_sq)} jugadores en la liga. Crudo guardado: {raw_path.name}")
    print(f"     con valor de mercado: {df_sq['market_value_eur'].notna().sum()} | "
          f"con edad: {df_sq['age'].notna().sum()}")

    # ---- Filtro de pool para la fase cara ------------------------------------
    pool = df_sq[df_sq["age"].notna() & (df_sq["age"] < args.max_age)].copy()
    pool = pool.sort_values("market_value_eur", ascending=False, na_position="last")
    print(f"\n[FILTRO] pool sub-{args.max_age}: {len(pool)} jugadores "
          f"(de {len(df_sq)} totales)")
    target = pool if args.max_stats == 0 else pool.head(args.max_stats)
    print(f"[FASE 2] se van a renderizar stats de {len(target)} jugadores "
          f"(~{len(target) * 13}s estimado)")

    # ---- FASE 2 (cara) -------------------------------------------------------
    print("\n[FASE 2 — CARA] stats (goles/asist/minutos), aislando Primera Nacional...")
    import http_cache as hc
    stats = []
    for n, (_, p) in enumerate(target.iterrows(), 1):
        cached = hc.is_cached_render(tm.stats_url(p["slug"], int(p["player_id"]), args.season))
        print(f"  [{n}/{len(target)}] {p['name']}{'  [cache]' if cached else ''}")
        s = tm.scrape_player_stats(p["slug"], int(p["player_id"]), args.season)
        if s:
            stats.append(s)
    df_st = pd.DataFrame(stats)
    stats_path = RAW / f"tm_stats_{args.season}.csv"
    df_st.to_csv(stats_path, index=False, encoding="utf-8")
    print(f"  -> con fila de Primera Nacional: {len(df_st)}/{len(target)}. "
          f"Crudo: {stats_path.name}")

    # ---- UNIFICAR al esquema-contrato ---------------------------------------
    print("\n[UNIFICAR] join + per-90 -> esquema del SPEC...")
    df = pool.merge(df_st, on="player_id", how="inner") if len(df_st) else pool.assign(
        minutes=pd.NA, goals=pd.NA, assists=pd.NA)
    df["goals_90"] = df.apply(lambda r: per90(r.get("goals"), r.get("minutes")), axis=1)
    df["assists_90"] = df.apply(lambda r: per90(r.get("assists"), r.get("minutes")), axis=1)
    df_final = df.reindex(columns=SCHEMA)

    clean_path = CLEAN / f"dataset_{args.season}.csv"
    df_final.to_csv(clean_path, index=False, encoding="utf-8")

    # ---- SQLite -------------------------------------------------------------
    with sqlite3.connect(DB_PATH) as con:
        df_final.to_sql("players", con, if_exists="replace", index=False)
    print(f"  -> SQLite: {DB_PATH.relative_to(ROOT)} (tabla 'players', {len(df_final)} filas)")
    print(f"  -> limpio: {clean_path.relative_to(ROOT)}")

    # ---- Reporte ------------------------------------------------------------
    print("\n" + "=" * 78)
    print("RESUMEN")
    print("=" * 78)
    print(f"  Fase 1 (liga completa):      {len(df_sq)} jugadores")
    print(f"  Pool sub-{args.max_age}:                {len(pool)} jugadores")
    print(f"  Fase 2 (stats renderizados): {len(target)} (demo) -> {len(df_st)} con datos de liga")
    print(f"  Dataset final (SQLite):      {len(df_final)} filas")
    print("\n  MUESTRA del dataset final (esquema-contrato del SPEC):")
    with pd.option_context("display.max_columns", None, "display.width", 200):
        print(df_final.head(12).to_string(index=False))

    # ---- Metadata de procedencia del snapshot (ADR 0009) ---------------------
    # Aditivo puro: no toca la logica de scraping ni de procesamiento. Escribe
    # la fuente unica de verdad que la app usa para mostrar la fecha de datos.
    # Nota: se escribe built_at (fecha de la corrida), NO un rango de captura:
    # con la cache, parte de los datos puede ser anterior a la corrida, y
    # afirmar un rango seria procedencia inventada.
    meta = {
        "season": args.season,
        "built_at": date.today().isoformat(),
        "players_with_stats": int(len(df_final)),
        "total_league_players": int(len(df_sq)),
        "source": "Transfermarkt",
        "league": "Primera Nacional (Argentina)",
        "competition_code": "ARG2",
    }
    meta_path = ROOT / "data" / "snapshot_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    print(f"  -> metadata de procedencia: {meta_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
