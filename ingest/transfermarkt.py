"""
transfermarkt.py — Conector de ingesta de Transfermarkt para la Primera
Nacional argentina (codigo de competicion ARG2).

Interfaz (estilo SPEC): expone funciones que devuelven datos normalizados.
Dos fases:
  FASE BARATA  scrape_squads()       -> jugadores con valor/edad/posicion (HTTP)
  FASE CARA    scrape_player_stats() -> goles/asistencias/minutos (navegador),
                                        AISLANDO la fila de Primera Nacional.
"""
from __future__ import annotations

import re
from typing import Optional

import http_cache as hc

TM_ROOT = "https://www.transfermarkt.us"
COMP_URL = f"{TM_ROOT}/primera-nacional/startseite/wettbewerb/ARG2"
COMP_NAME = "Primera Nacional"  # etiqueta exacta de la fila de liga en la grilla

# Orden de las 12 columnas de stats de la grilla Svelte (vista detallada).
# Indice 0 = Appearances ... el ultimo = Minutes played.
# Lo que nos importa: Goals=idx1, Assists=idx2, Minutes=idx ultimo.


# ---------------------------------------------------------------------------
# FASE BARATA — plantillas (valor de mercado, edad, posicion)
# ---------------------------------------------------------------------------
def get_club_links(season: str) -> list[str]:
    """Links de los clubes de la liga en la temporada dada (1 pedido HTTP)."""
    page = hc.get_html(f"{COMP_URL}/plus/?saison_id={season}")
    items = page.find("table", {"class": "items"})
    if items is None:
        return []
    links, seen = [], set()
    for a in items.find_all("a", href=True):
        if "/startseite/verein/" in a["href"] and a.text.strip():
            full = TM_ROOT + a["href"]
            if full not in seen:
                seen.add(full)
                links.append(full)
    return links


def scrape_squads(season: str) -> list[dict]:
    """Todos los jugadores de la liga con valor/edad/posicion (fase barata).

    Un pedido HTTP por club. Devuelve una lista de dicts normalizados.
    """
    rows = []
    clubs = get_club_links(season)
    for i, club in enumerate(clubs, 1):
        squad_url = club.replace("/startseite/verein/", "/kader/verein/") + "/plus/1"
        club_slug = club.split("/")[3]
        print(f"  [club {i}/{len(clubs)}] {club_slug}")
        table = hc.get_html(squad_url).find("table", {"class": "items"})
        if table is None:
            continue
        rows.extend(_parse_squad(table, club_slug))
    return rows


def _parse_squad(table, club_slug: str) -> list[dict]:
    """Parsea la tabla 'kader/plus/1' de un club -> jugadores con sus campos."""
    out = []
    body = table.find("tbody")
    trs = body.find_all("tr", recursive=False) if body else table.find_all("tr")
    for tr in trs:
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 5:
            continue
        inline = tr.find("table", {"class": "inline-table"})
        if not inline:
            continue
        link = inline.find("td", {"class": "hauptlink"})
        a = link.find("a", href=True) if link else None
        if not a:
            continue
        m = re.search(r"/([^/]+)/profil/spieler/(\d+)", a["href"])
        if not m:
            continue
        slug, pid = m.group(1), m.group(2)
        name = a.get_text(strip=True)
        # posicion: 2da fila de la inline-table
        pos = ""
        irows = inline.find_all("tr")
        if len(irows) >= 2:
            pos = irows[1].get_text(strip=True)
        # edad: celda con formato "... (NN)"
        age = None
        for td in tds:
            mm = re.search(r"\((\d{2})\)", td.get_text())
            if mm:
                age = int(mm.group(1))
                break
        # valor de mercado: celda derecha
        vcell = tr.find("td", {"class": re.compile(r"rechts.*hauptlink")}) or tds[-1]
        mv = parse_market_value(vcell.get_text(strip=True))
        out.append({
            "player_id": int(pid),
            "name": name,
            "slug": slug,
            "age": age,
            "position": pos,
            "market_value_eur": mv,
            "club": club_slug,
        })
    return out


def parse_market_value(text: str) -> Optional[int]:
    """'€2.50m' -> 2500000 ; '€200k' -> 200000 ; '-' -> None."""
    if not text or "€" not in text:
        return None
    t = text.replace("€", "").replace(",", "").strip().lower()
    mult = 1
    if t.endswith("m"):
        mult, t = 1_000_000, t[:-1]
    elif t.endswith("k"):
        mult, t = 1_000, t[:-1]
    elif t.endswith("bn"):
        mult, t = 1_000_000_000, t[:-2]
    try:
        return int(float(t) * mult)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# FASE CARA — stats de rendimiento (goles/asistencias/minutos)
# ---------------------------------------------------------------------------
def stats_url(slug: str, player_id: int, season: str) -> str:
    return f"{TM_ROOT}/{slug}/leistungsdaten/spieler/{player_id}/saison/{season}/plus/1"


def scrape_player_stats(slug: str, player_id: int, season: str) -> Optional[dict]:
    """Goles/asistencias/minutos de la temporada, SOLO de la Primera Nacional.

    Aisla la fila de competicion 'Primera Nacional' de la grilla (NO la 'Total',
    que sumaria Copa Argentina u otras). Devuelve None si el jugador no tiene
    fila de Primera Nacional (no jugo en la liga esa temporada).
    """
    soup = hc.render_html(stats_url(slug, player_id, season))
    for row in soup.select("div.grid-row"):
        cells = [c.get_text(strip=True) for c in row.find_all(recursive=False)]
        # La fila-resumen de liga: primer campo = nombre de la competicion,
        # segundo campo = nro de partidos (entero). Las filas por-partido tienen
        # una fecha en el segundo campo, asi las descartamos.
        if len(cells) >= 13 and cells[0] == COMP_NAME and re.fullmatch(r"\d+", cells[1]):
            return {
                "player_id": player_id,
                "appearances": _num(cells[1]),
                "goals": _num(cells[2]),
                "assists": _num(cells[3]),
                "minutes": _minutes(cells[-1]),
            }
    return None


def _num(t: str) -> int:
    t = t.replace(".", "").replace(",", "").strip()
    return int(t) if t.isdigit() else 0


def _minutes(t: str) -> int:
    """\"1,161'\" -> 1161 ; '-' -> 0."""
    t = t.replace(".", "").replace(",", "").replace("'", "").replace("’", "").strip()
    return int(t) if t.isdigit() else 0
