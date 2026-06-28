"""
validate_tm_stats.py — Sub-paso de validacion: ¿se pueden sacar stats de
rendimiento (goles/asistencias/minutos) de Transfermarkt?

La tabla de rendimiento de TM se renderiza por JavaScript (no esta en el HTML
crudo), asi que usamos el navegador headless de botasaurus (via ScraperFC) para
renderizar la pagina y recien ahi parsear la tabla.

MUESTRA CHICA: solo 3 jugadores conocidos. NO es el scrape completo. El objetivo
es decidir si vale la pena construir el scraper de stats sobre Transfermarkt.

Reglas: rate-limiting entre renders + cache en disco del HTML renderizado.
"""
from __future__ import annotations

import hashlib
import time
import traceback
from pathlib import Path

from bs4 import BeautifulSoup
from ScraperFC.utils import botasaurus_browser_get_soup

PAUSA_SEG = 6
TM_ROOT = "https://www.transfermarkt.us"
SEASON = "2025"  # temporada 2025/26 (mismo saison_id que usamos para los clubes)
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "cache_render"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# 3 jugadores de campo de Godoy Cruz (Primera Nacional), IDs ya verificados.
JUGADORES = [
    ("Mateo Mendoza", "mateo-mendoza", "1103933"),
    ("Nahuel Brunet", "nahuel-brunet", "1011921"),
    ("Tomas Rossi",   "tomas-rossi",   "856020"),
]


def render_cached(url: str) -> BeautifulSoup:
    """Renderiza con navegador (JS activado + espera), cacheando el HTML.

    OJO: la tabla de stats de TM es un componente Svelte que se llena por XHR
    DESPUES del load. Hay que NO bloquear css/js y dar un delay para que el XHR
    complete; si no, la grilla viene vacia.
    """
    cp = CACHE_DIR / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".html")
    if cp.exists():
        print(f"    [cache] {url}")
        return BeautifulSoup(cp.read_bytes(), "html.parser")
    print(f"    [render] {url}  (pausa {PAUSA_SEG}s)")
    time.sleep(PAUSA_SEG)
    soup = botasaurus_browser_get_soup(
        url, block_images_and_css=False, wait_for_complete_page_load=True, delay=7
    )
    cp.write_text(str(soup), encoding="utf-8")
    return soup


# Orden de columnas de la grilla Svelte de TM (vista detallada), las 12 distintas.
COLS = ["Appearances", "Goals", "Assists", "Own goals", "Subs on", "Subs off",
        "Yellow", "2nd yellow", "Red", "Penalty goals", "Min/goal", "Minutes"]


def parse_perf_table(soup: BeautifulSoup) -> dict:
    """Extrae la fila 'Total:' de la grilla renderizada y la mapea a columnas.

    Heuristico (suficiente para validar): toma los tokens entre 'Total:' y el
    siguiente bloque. minutos = token con apostrofe. Para el scraper real esto
    se endurece, pero alcanza para ver si el dato viene utilizable.
    """
    import re
    txt = re.sub(r"\s+", " ", soup.find("body").get_text(" ", strip=True))
    m = re.search(r"Total:\s*([0-9,.\-'’ ]+?)\s+(?:Primera Nacional|Compact|Matchday)", txt)
    if not m:
        return {"ok": False, "reason": "no se encontro la fila 'Total:' (grilla vacia?)"}
    tokens = m.group(1).split()
    if len(tokens) < 3:
        return {"ok": False, "reason": f"fila Total con pocos tokens: {tokens}"}

    def num(t):
        t = t.replace(",", "").replace("'", "").replace("’", "")
        return 0 if t in ("-", "") else (int(t) if t.isdigit() else t)

    minutos = next((num(t) for t in tokens if "'" in t or "’" in t), None)
    return {
        "ok": True,
        "tokens": tokens,
        "appearances": num(tokens[0]),
        "goals": num(tokens[1]),
        "assists": num(tokens[2]),
        "minutes": minutos,
    }


def main() -> None:
    print("VALIDACION TM-STATS — 3 jugadores, temporada", SEASON)
    print(f"Cache render: {CACHE_DIR}  |  pausa: {PAUSA_SEG}s\n")
    for nombre, slug, pid in JUGADORES:
        print("=" * 78)
        print(f"{nombre}  (id {pid})")
        url = f"{TM_ROOT}/{slug}/leistungsdaten/spieler/{pid}/saison/{SEASON}/plus/1"
        try:
            soup = render_cached(url)
            res = parse_perf_table(soup)
            if not res["ok"]:
                print(f"  [X] {res['reason']}")
                continue
            print(f"  fila Total cruda: {res['tokens']}")
            print(f"  -> Partidos:    {res['appearances']}")
            print(f"  -> Goles:       {res['goals']}")
            print(f"  -> Asistencias: {res['assists']}")
            print(f"  -> Minutos:     {res['minutes']}")
        except Exception as e:
            print(f"  [X] ERROR CRUDO: {e!r}")
            traceback.print_exc()
    print("=" * 78)
    print("FIN — muestra de 3. Decidir si el campo goles/asist/minutos viene utilizable.")


if __name__ == "__main__":
    main()
