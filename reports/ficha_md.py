"""
ficha_md.py — Ficha individual (mini-dossier) en Markdown, plantilla spec V2 §8.

La misma funcion sirve a la vista de la app y al boton de descarga: una sola
estructura, un solo gate.

Gate de publicacion: la ficha COMPLETA solo se genera para jugadores con
data_confidence asignada (A/B/C) y las tres fuentes obligatorias cargadas
(source_market_value, source_minutes, source_profile). El resto recibe la
version REDUCIDA: solo capa cuantitativa, con nota "verificacion en curso".

Regla transversal: celda vacia se muestra como "pendiente de verificacion" —
JAMAS se rellena con un valor estimado o inventado.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "analysis") not in sys.path:
    sys.path.insert(0, str(ROOT / "analysis"))

import talent_gap as tg  # noqa: E402

DISCLAIMER = ("Este dossier presenta señales públicas de posible infravaloración. "
              "No constituye una evaluación de scouting ni una recomendación de fichaje.")
RADAR_URL = "https://potrero-scout-sdyte4krc3hjvktx8szswg.streamlit.app"
REQUIRED_SOURCES = ["source_market_value", "source_minutes", "source_profile"]
PENDIENTE = "pendiente de verificación"


# ---------------------------------------------------------------------------
# Gate y helpers
# ---------------------------------------------------------------------------
def _cell(row, col) -> str:
    """Valor de una celda de la capa manual como string limpio; '' si vacia."""
    if row is None:
        return ""
    v = row.get(col) if isinstance(row, dict) else (row[col] if col in row.index else None)
    if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
        return ""
    return str(v).strip()


def is_verified(manual_row) -> bool:
    """True solo con confianza asignada Y las tres fuentes obligatorias."""
    if manual_row is None:
        return False
    conf_ok = _cell(manual_row, "data_confidence").upper() in ("A", "B", "C")
    sources_ok = all(_cell(manual_row, c) for c in REQUIRED_SOURCES)
    return conf_ok and sources_ok


def ficha_filename(name: str) -> str:
    slug = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", slug).strip("_").lower()
    return f"ficha_{slug}.md"


def _split_signals(raw: str) -> list[str]:
    return [s.strip() for s in raw.split(";") if s.strip()]


def _tabla_datos(qrow, manual_row, verified: bool, fecha: str) -> list[str]:
    """Tabla DATOS. Con gate pasado: fuente linkeada + fecha por fila."""
    def src(col):
        url = _cell(manual_row, col)
        return f"[fuente]({url}) · {fecha}" if (verified and url) else PENDIENTE

    pj = _cell(manual_row, "appearances") or "—"
    goles = _cell(manual_row, "goals") or "—"
    asist = _cell(manual_row, "assists") or "—"
    filas = [
        "| Dato | Valor | Fuente y fecha |",
        "|---|---|---|",
        f"| Minutos | {int(qrow['minutes'])} | {src('source_minutes')} |",
        f"| Partidos jugados | {pj} | {src('source_minutes')} |",
        f"| Goles | {goles} | {src('source_profile')} |",
        f"| Asistencias | {asist} | {src('source_profile')} |",
        f"| Valor estimado | €{int(qrow['market_value_eur']):,} | {src('source_market_value')} |",
    ]
    contrato = _cell(manual_row, "contract_until")
    if contrato:
        url_c = _cell(manual_row, "source_contract")
        fuente_c = f"[fuente]({url_c}) · {fecha}" if url_c else PENDIENTE
        filas.append(f"| Contrato hasta | {contrato} | {fuente_c} |")
    return filas


def build_ficha_md(qrow, manual_row=None,
                   provenance: str = "Fecha de datos no disponible.") -> str:
    """Genera la ficha en Markdown. Version completa o reducida segun el gate."""
    verified = is_verified(manual_row)
    conf = (_cell(manual_row, "data_confidence").upper()
            if verified else tg.CONFIDENCE_UNSET)
    fecha = _cell(manual_row, "last_updated") or PENDIENTE

    club = _cell(manual_row, "club") or PENDIENTE
    liga = _cell(manual_row, "league") or "Primera Nacional (Argentina)"
    pos_sec = _cell(manual_row, "secondary_position")
    pos = f"{qrow['position']} ({pos_sec})" if pos_sec else str(qrow["position"])

    L: list[str] = []
    # 1. Encabezado
    L += [f"# {qrow['name']}",
          "",
          f"{int(qrow['age'])} años · {club} · {pos} · {liga}",
          ""]
    # 2. TGS + confianza + subscores
    tgs_txt = str(int(qrow["tgs"])) if pd.notna(qrow["tgs"]) else "—"
    L += [f"## Talent Gap Score: {tgs_txt}/100 · Confianza: {conf}", ""]
    if pd.notna(qrow["tgs"]):
        for etiqueta, valor in tg.subscores(qrow).items():
            L.append(f"- **{etiqueta}:** {valor:.0f}/100")
    else:
        L.append(f"- Sin TGS: {qrow.get('exclusion_reason')}")
    L.append("")

    if not verified:
        L += ["> **Verificación en curso.** Esta ficha muestra solo la capa "
              "cuantitativa. Las fuentes por dato, el contexto competitivo y el "
              "nivel de confianza llegan con la verificación manual.",
              ""]

    # 3. Por que esta en el radar (solo hechos derivados de datos)
    L += ["## Por qué está en el radar", ""]
    why = _cell(manual_row, "why_undervalued") if verified else ""
    if why:
        L.append(why)
    else:
        for d in tg.drivers(qrow):
            L.append(f"- {d}")
    L.append("")

    # 4. Datos (con fuente por fila si el gate paso)
    L += ["## Datos", ""]
    L += _tabla_datos(qrow, manual_row, verified, fecha)
    if not verified:
        L += ["", f"_Capa cuantitativa — {provenance} Fuente global: Transfermarkt; "
              "la fuente individual por dato está en verificación._"]
    L.append("")

    # 5-6. Señales (max 3, trazables a numeros)
    pos_manual = _split_signals(_cell(manual_row, "positive_signals")) if verified else []
    rsk_manual = _split_signals(_cell(manual_row, "risk_signals")) if verified else []
    positivas = (pos_manual or tg.positive_signals(qrow))[:3]
    riesgos = (rsk_manual or tg.risk_signals(qrow))[:3]
    # La limitacion de muestra va SIEMPRE que aplique, tambien sobre señales manuales
    if pd.notna(qrow["minutes"]) and float(qrow["minutes"]) < 900:
        if not any("muestra" in s.lower() or "minut" in s.lower() for s in riesgos):
            riesgos = ([f"muestra chica: {int(qrow['minutes'])}′ jugados — los "
                        "por-90 y percentiles son inestables"] + riesgos)[:3]

    L += ["## Señales positivas (en los datos)", ""]
    L += [f"- {s}" for s in positivas] or ["- (sin señales que superen los umbrales)"]
    L += ["", "## Señales de riesgo (en los datos)", ""]
    L += [f"- {s}" for s in riesgos] or ["- (sin señales de riesgo detectadas)"]
    L.append("")

    if verified:
        # 7. Contexto competitivo (manual, con fuente)
        L += ["## Contexto competitivo", ""]
        ctx = _cell(manual_row, "context_notes")
        if ctx:
            L.append(ctx)
            url_n = _cell(manual_row, "source_news")
            if url_n:
                L.append(f"([fuente]({url_n}) · {fecha})")
        else:
            L.append(f"_{PENDIENTE}._")
        L.append("")

        # 8. Interpretacion — el UNICO lugar con lectura, rotulado como hipotesis
        L += ["## Interpretación — Hipótesis", ""]
        hip = []
        rec = _cell(manual_row, "recommended_market")
        if rec:
            hip.append(f"**Hipótesis de encaje de mercado:** {rec}")
        qn = _cell(manual_row, "qualitative_notes")
        if qn:
            hip.append(qn)
        if hip:
            L.append("> " + " ".join(hip))
            L.append("> ")
            L.append("> _Este bloque es interpretación, no dato._")
        else:
            L.append(f"_{PENDIENTE}._")
        L.append("")

        # 9. Fuentes completas
        L += ["## Fuentes", ""]
        for col in REQUIRED_SOURCES + ["source_contract", "source_news", "source_video"]:
            url = _cell(manual_row, col)
            if url:
                L.append(f"- {col.replace('source_', '').replace('_', ' ')}: "
                         f"{url} (consultado: {fecha})")
        L.append("")

    # 10. Cierre
    L += ["---",
          "",
          f"Última actualización: {fecha if verified else provenance}",
          "",
          f"> {DISCLAIMER} Metodología completa: {RADAR_URL}",
          ""]
    return "\n".join(L)
