"""
claude_report.py — Capa de IA (Etapa de informes del SPEC).

Principio rector del SPEC: el pipeline YA calculo todo lo cuantitativo. La IA
NO calcula numeros ni los inventa: solo REDACTA un informe de scouting sobre los
datos ya calculados, en formato estructurado (json_schema) y con un system prompt
anti-alucinacion.

Campos del informe (structured outputs):
  perfil, fortalezas (citando percentiles concretos), comparable_estilo,
  tesis_por_que_ahora, riesgos.

Costo honesto: usa la API de Anthropic (console.anthropic.com), que es PAGA por
uso y aparte de la suscripcion Max. Por eso, si no hay ANTHROPIC_API_KEY en el
.env, este script corre en modo DRY-RUN: arma y muestra el prompt exacto que se
enviaria, SIN llamar a la API (no gasta nada). Con la key puesta, genera de verdad.

Uso:
    python reports/claude_report.py --player "Ignacio Lago"        # dry-run si no hay key
    python reports/claude_report.py --player "Ignacio Lago" --dry-run   # forzar dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

# importar la metrica para alimentar el informe con datos YA calculados
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "analysis"))
import normalize as nz       # noqa: E402
import undervaluation as uv  # noqa: E402

MODEL = "claude-opus-4-8"
DB_PATH = ROOT / "db" / "scout.db"

# --- Schema del informe (json_schema, structured outputs) -------------------
REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "perfil": {"type": "string"},
        "fortalezas": {"type": "array", "items": {"type": "string"}},
        "comparable_estilo": {"type": "string"},
        "tesis_por_que_ahora": {"type": "string"},
        "riesgos": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["perfil", "fortalezas", "comparable_estilo",
                 "tesis_por_que_ahora", "riesgos"],
    "additionalProperties": False,
}

# --- System prompt: anti-alucinacion ----------------------------------------
SYSTEM = """Sos un analista de scouting de futbol. Escribis en español rioplatense, claro y conciso.

REGLAS INVIOLABLES (anti-alucinacion):
1. El pipeline YA calculo todos los numeros. Vos NO calculas ni estimas numeros, y NUNCA inventas datos.
2. Solo podes mencionar cifras que aparezcan EXPLICITAMENTE en los DATOS provistos. Si citas un percentil o una metrica, tiene que ser uno que este en los datos.
3. Si un dato NO esta en los datos (por ejemplo, no hay percentil porque el pool era chico, o no hay metricas avanzadas para esta liga), decilo de forma explicita: "no hay datos suficientes para X". No lo tapes con una afirmacion inventada.
4. "comparable_estilo" es una comparacion de ESTILO, tentativa y cualitativa, no un dato. Marcala como tentativa y no la presentes como un hecho. Si no podes fundamentarla con lo que hay, deci que es solo orientativa.
5. En "fortalezas", cuando exista el percentil, citalo textual (ej: "percentil 0.82 en goles_90 dentro de su posicion"). Si no hay percentil, hablar de la cifra cruda por-90 y aclarar que el percentil no esta disponible.
6. No inventes clubes, transferencias, lesiones, ni rendimientos que no esten en los datos.

El objetivo es un informe honesto y util para un director deportivo: que no prometa lo que el dato no respalda."""


def _fmt(v) -> str:
    import pandas as pd
    if v is None or pd.isna(v):  # None, NaN o pd.NA
        return "NO DISPONIBLE"
    if isinstance(v, float):
        return f"{round(v, 3):g}"
    return str(v)


def build_player_payload(row) -> str:
    """Arma el bloque de DATOS YA CALCULADOS que se le pasa al modelo."""
    val = row.get("market_value_eur")
    val_txt = f"€{int(val):,}" if val and val == val else "NO DISPONIBLE"
    lines = [
        "DATOS YA CALCULADOS (no inventar nada fuera de esto):",
        f"- Nombre: {row['name']}",
        f"- Edad: {_fmt(row.get('age'))}",
        f"- Posicion: {_fmt(row.get('position'))} (pool de comparacion: {_fmt(row.get('pos_pool'))})",
        f"- Minutos jugados (Primera Nacional): {_fmt(row.get('minutes'))}",
        f"- Valor de mercado: {val_txt}",
        f"- Goles por 90: {_fmt(row.get('goals_90'))}",
        f"- Asistencias por 90: {_fmt(row.get('assists_90'))}",
        "",
        "PERCENTILES DENTRO DE SU POSICION (0-1; NO DISPONIBLE = pool insuficiente, no inventar):",
        f"- Percentil goles_90: {_fmt(row.get('goals_90_pct'))}",
        f"- Percentil assists_90: {_fmt(row.get('assists_90_pct'))}",
        f"- Score de rendimiento: {_fmt(row.get('performance'))}",
        f"- Baratura (valor bajo): {_fmt(row.get('cheapness'))}",
        f"- Score de infravaloracion: {_fmt(row.get('undervaluation'))}",
        "",
        "LIMITES DE DATOS DE ESTA LIGA: no hay metricas avanzadas (xG, datos de eventos, "
        "acciones defensivas) para la Primera Nacional. Si haria falta una de esas para "
        "afirmar algo, decilo en vez de inventarla.",
    ]
    return "\n".join(lines)


def load_scored_player(name: str):
    """Lee el dataset, corre la metrica, y devuelve la fila del jugador pedido."""
    with sqlite3.connect(DB_PATH) as con:
        df = nz.add_percentiles(
            __import__("pandas").read_sql("SELECT * FROM players", con)
        )
    df = uv.score(df)
    hit = df[df["name"].str.lower() == name.lower()]
    if hit.empty:
        raise SystemExit(f"No encontre a '{name}' en el dataset. "
                         f"Jugadores: {list(df['name'])}")
    return hit.iloc[0]


def generate_report(payload: str, dry_run: bool) -> dict | None:
    """Llama (o simula) a la API de Claude con structured outputs."""
    if dry_run:
        print("\n" + "#" * 78)
        print("DRY-RUN — esto es lo que se ENVIARIA a la API (no se llama, no se gasta):")
        print("#" * 78)
        print(f"\nMODELO: {MODEL}")
        print("\n--- SYSTEM PROMPT ---\n" + SYSTEM)
        print("\n--- MENSAJE DEL USUARIO ---\n" + payload)
        print("\n--- SCHEMA DE SALIDA (json_schema) ---\n"
              + json.dumps(REPORT_SCHEMA, indent=2, ensure_ascii=False))
        print("\n(Costo aprox.: un informe son ~1-2k tokens de entrada + ~0.7k de salida; "
              "a $5/$25 por millon en opus-4-8, del orden de centavos.)")
        return None

    import anthropic
    client = anthropic.Anthropic()  # toma ANTHROPIC_API_KEY del entorno
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM,
        messages=[{"role": "user", "content": payload}],
        output_config={"format": {"type": "json_schema", "schema": REPORT_SCHEMA}},
    )
    text = next(b.text for b in resp.content if b.type == "text")
    print(f"\n[tokens] in={resp.usage.input_tokens} out={resp.usage.output_tokens} "
          f"| request {resp._request_id}")
    return json.loads(text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--player", required=True)
    ap.add_argument("--dry-run", action="store_true",
                    help="forzar dry-run aunque haya key")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    has_key = bool(os.getenv("ANTHROPIC_API_KEY"))
    dry = args.dry_run or not has_key
    if not has_key and not args.dry_run:
        print("[aviso] No hay ANTHROPIC_API_KEY en el .env -> corro en DRY-RUN "
              "(no llamo a la API, no gasto). Pone la key para generar de verdad.")

    row = load_scored_player(args.player)
    payload = build_player_payload(row)
    report = generate_report(payload, dry_run=dry)

    if report is not None:
        print("\n" + "=" * 78)
        print(f"INFORME DE SCOUTING — {row['name']}")
        print("=" * 78)
        print(f"\nPERFIL\n{report['perfil']}")
        print("\nFORTALEZAS")
        for f in report["fortalezas"]:
            print(f"  - {f}")
        print(f"\nCOMPARABLE DE ESTILO (tentativo)\n{report['comparable_estilo']}")
        print(f"\nTESIS — POR QUE AHORA\n{report['tesis_por_que_ahora']}")
        print("\nRIESGOS")
        for r in report["riesgos"]:
            print(f"  - {r}")


if __name__ == "__main__":
    main()
