"""
validate_sources.py — Paso 2: VALIDAR que se puede sacar data real de la
Primera Nacional argentina ANTES de construir el pipeline.

No construye nada del pipeline. Solo intenta, con honestidad:
  - Transfermarkt (codigo de competicion ARG2): jugadores con valor de
    mercado, edad y posicion.
  - Sofascore: stats basicas (goles, asistencias, minutos) de la misma liga.

Reglas que respeta:
  - Rate-limiting: pausa de PAUSA_SEG segundos entre requests REALES.
  - Cache en disco (data/raw/cache/): no repite una descarga ya hecha.
  - No crea cuentas ni evade autenticacion.

Uso:
    python ingest/validate_sources.py
"""
from __future__ import annotations

import hashlib
import re
import sys
import time
import traceback
from pathlib import Path

import cloudscraper
from bs4 import BeautifulSoup

# --- Config ---
PAUSA_SEG = 5  # segundos entre requests reales (no cacheados)
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
TM_ROOT = "https://www.transfermarkt.us"
TM_COMP_ARG2 = f"{TM_ROOT}/primera-nacional/startseite/wettbewerb/ARG2"

# Un solo scraper reutilizado (mantiene la sesion / cookies de Cloudflare)
_scraper = cloudscraper.CloudScraper()


def _cache_path(url: str) -> Path:
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return CACHE_DIR / f"{h}.html"


def fetch(url: str) -> bytes:
    """GET con cache en disco + rate-limiting. Cache hit = sin red, sin pausa."""
    cp = _cache_path(url)
    if cp.exists():
        print(f"      [cache] {url}")
        return cp.read_bytes()
    print(f"      [red]   {url}  (pausa {PAUSA_SEG}s)")
    time.sleep(PAUSA_SEG)
    r = _scraper.get(url, timeout=45, allow_redirects=True)
    r.raise_for_status()
    cp.write_bytes(r.content)
    return r.content


# ----------------------------------------------------------------------------
# TRANSFERMARKT
# ----------------------------------------------------------------------------
def validar_transfermarkt() -> None:
    print("\n" + "=" * 78)
    print("FUENTE 1 — TRANSFERMARKT (Primera Nacional, ARG2)")
    print("=" * 78)

    soup = BeautifulSoup(fetch(TM_COMP_ARG2), "html.parser")

    # 1) Temporadas disponibles (confirma que la liga existe en TM)
    sel = soup.find("select", {"name": "saison_id"})
    if not sel:
        print("  [X] No se encontro el selector de temporadas. La liga no carga bien.")
        return
    seasons = [o.get("value") for o in sel.find_all("option")]
    print(f"  Temporadas disponibles (saison_id): {seasons[:6]} ... ({len(seasons)} total)")
    season_actual = seasons[0]
    print(f"  -> Uso temporada actual: saison_id={season_actual}")

    # 2) Clubes de la liga en la temporada actual
    page = BeautifulSoup(fetch(f"{TM_COMP_ARG2}/plus/?saison_id={season_actual}"), "html.parser")
    items = page.find("table", {"class": "items"})
    if items is None:
        print("  [X] No hay tabla de clubes para esta temporada.")
        return
    club_links = []
    for a in items.find_all("a", href=True):
        if "/startseite/verein/" in a["href"] and a.text.strip():
            full = TM_ROOT + a["href"]
            if full not in club_links:
                club_links.append(full)
    print(f"  Clubes encontrados: {len(club_links)}")
    for c in club_links[:5]:
        print(f"      - {c}")

    if not club_links:
        print("  [X] Sin clubes -> no se puede seguir.")
        return

    # 3) Plantilla detallada de UN club (muestra de campos por jugador)
    #    No bajamos los 20+ clubes en una validacion: con uno alcanza para
    #    probar que los campos (valor, edad, posicion) estan.
    club0 = club_links[0]
    squad_url = club0.replace("/startseite/verein/", "/kader/verein/") + "/plus/1"
    squad = BeautifulSoup(fetch(squad_url), "html.parser")
    stable = squad.find("table", {"class": "items"})
    if stable is None:
        print("  [X] No se encontro la plantilla del club de muestra.")
        return

    jugadores = _parse_squad(stable)
    print(f"\n  Plantilla de muestra ({club0.split('/')[3]}): {len(jugadores)} jugadores")
    print(f"  Campos por jugador: {list(jugadores[0].keys()) if jugadores else 'NINGUNO'}")
    print("  Primeros 8 jugadores (datos REALES):")
    for j in jugadores[:8]:
        print(f"      {j['nombre']:<26} | edad {j['edad']:<4} | {j['posicion']:<22} | {j['valor']}")

    n_con_valor = sum(1 for j in jugadores if j["valor"] not in ("", "-", None))
    print(f"\n  Cobertura de valor de mercado en la muestra: {n_con_valor}/{len(jugadores)}")
    print(f"  Estimacion liga completa: ~{len(club_links)} clubes x ~{len(jugadores)} = "
          f"~{len(club_links) * len(jugadores)} jugadores (full scrape, no en esta validacion)")
    print("  VEREDICTO TM: datos de valor/edad/posicion DISPONIBLES para el ascenso.")


def _parse_squad(table) -> list[dict]:
    """Parsea la tabla 'kader/plus/1' de un club. Defensivo: si un campo no
    esta, queda vacio en vez de romper."""
    out = []
    body = table.find("tbody")
    rows = body.find_all("tr", recursive=False) if body else table.find_all("tr")
    for tr in rows:
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 5:
            continue
        # nombre + posicion estan en la celda con la inline-table
        nombre, posicion = "", ""
        inline = tr.find("table", {"class": "inline-table"})
        if inline:
            link = inline.find("td", {"class": "hauptlink"})
            nombre = link.get_text(strip=True) if link else ""
            tr_rows = inline.find_all("tr")
            if len(tr_rows) >= 2:
                posicion = tr_rows[1].get_text(strip=True)
        # edad: celda con formato "Mar 1, 2003 (22)"
        edad = ""
        for td in tds:
            m = re.search(r"\((\d{2})\)", td.get_text())
            if m:
                edad = m.group(1)
                break
        # valor de mercado: celda derecha (rechts hauptlink) o ultima con simbolo
        valor = ""
        vcell = tr.find("td", {"class": re.compile(r"rechts.*hauptlink")})
        if vcell is None:
            vcell = tds[-1]
        valor = vcell.get_text(strip=True)
        if nombre:
            out.append({"nombre": nombre, "edad": edad, "posicion": posicion, "valor": valor})
    return out


# ----------------------------------------------------------------------------
# SOFASCORE  (camino fragil: API tras Cloudflare -> navegador botasaurus)
# ----------------------------------------------------------------------------
def validar_sofascore() -> None:
    print("\n" + "=" * 78)
    print("FUENTE 2 — SOFASCORE (stats: goles/asistencias/minutos)")
    print("=" * 78)
    try:
        import ScraperFC.sofascore as sfmod
        from ScraperFC import Sofascore
    except Exception as e:
        print(f"  [X] No se pudo importar ScraperFC.sofascore: {e!r}")
        return

    # 1) Descubrir el unique-tournament id de 'Primera Nacional' via el buscador
    #    (necesita el navegador de botasaurus; la API da 403 con HTTP plano).
    print("  Buscando el ID de torneo de Primera Nacional en Sofascore...")
    tid = None
    try:
        search_url = (f"{sfmod.API_PREFIX}/search/all?q=primera%20nacional")
        data = sfmod.botasaurus_browser_get_json(search_url)
        for res in data.get("results", []):
            ent = res.get("entity", {})
            cat = (ent.get("category") or {}).get("name", "")
            if res.get("type") == "uniqueTournament" and "Argentina" in str(cat):
                tid = ent.get("id")
                print(f"      -> encontrado: id={tid} | {ent.get('name')} | {cat}")
                break
        if tid is None:
            print("      [!] El buscador no devolvio una Primera Nacional argentina clara.")
            for res in data.get("results", [])[:8]:
                ent = res.get("entity", {})
                print(f"          cand: {res.get('type')} id={ent.get('id')} "
                      f"name={ent.get('name')} cat={(ent.get('category') or {}).get('name')}")
    except Exception as e:
        print(f"  [X] Fallo el navegador/Cloudflare de Sofascore: {e!r}")
        traceback.print_exc()
        print("  VEREDICTO SOFASCORE: no se pudo acceder desde esta maquina (ver error arriba).")
        return

    if tid is None:
        print("  VEREDICTO SOFASCORE: no se ubico el torneo. Sin stats por ahora.")
        return

    # 2) Inyectar la liga y pedir stats de jugadores
    league_name = "Argentina Primera Nacional"
    sfmod.comps[league_name] = {"SOFASCORE": tid}
    sc = Sofascore()
    try:
        seasons = sc.get_valid_seasons(league_name)
        year = list(seasons.keys())[0]
        print(f"  Temporadas Sofascore: {list(seasons.keys())[:5]} -> uso {year}")
        df = sc.scrape_player_league_stats(year, league_name, accumulation="total")
        print(f"  Jugadores devueltos: {len(df)}")
        cols = list(df.columns)
        print(f"  Columnas ({len(cols)}): {cols[:25]}")
        for want in ["goals", "assists", "minutesPlayed", "minutes"]:
            hit = [c for c in cols if want.lower() in c.lower()]
            print(f"      stat '{want}': {hit if hit else 'NO ESTA'}")
        print("  VEREDICTO SOFASCORE: stats DISPONIBLES." if len(df) else
              "  VEREDICTO SOFASCORE: respuesta VACIA para el ascenso.")
    except Exception as e:
        print(f"  [X] Fallo al traer stats: {e!r}")
        traceback.print_exc()


if __name__ == "__main__":
    print("VALIDACION DE FUENTES — Primera Nacional argentina")
    print(f"Cache: {CACHE_DIR}  |  Pausa entre requests reales: {PAUSA_SEG}s")
    try:
        validar_transfermarkt()
    except Exception as e:
        print(f"\n[ERROR no manejado en Transfermarkt] {e!r}")
        traceback.print_exc()
    try:
        validar_sofascore()
    except Exception as e:
        print(f"\n[ERROR no manejado en Sofascore] {e!r}")
        traceback.print_exc()
    print("\n" + "=" * 78)
    print("FIN DE LA VALIDACION")
    print("=" * 78)
