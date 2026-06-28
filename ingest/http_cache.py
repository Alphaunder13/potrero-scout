"""
http_cache.py — Fetchers compartidos para los conectores de ingesta.

Dos caminos, segun el costo:
  - get_html()    : cloudscraper, HTTP puro, instantaneo. Para paginas que el
                    servidor renderiza solo (plantillas, valores de mercado).
  - render_html() : navegador Chrome headless (via botasaurus de ScraperFC).
                    Para paginas cuyo contenido carga por JavaScript/XHR
                    (la grilla de stats de Transfermarkt). ~13s por pagina.

Ambos cachean en disco: una URL ya descargada NO se vuelve a pedir nunca.
Rate-limiting: pausa solo en los pedidos REALES (un cache hit no espera).
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

import cloudscraper
from bs4 import BeautifulSoup
from ScraperFC.utils import botasaurus_browser_get_soup

# data/raw/ es la zona "cruda e inmutable" del SPEC
_RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
CACHE_HTTP = _RAW / "cache"          # paginas cloudscraper
CACHE_RENDER = _RAW / "cache_render"  # paginas renderizadas con navegador
for d in (CACHE_HTTP, CACHE_RENDER):
    d.mkdir(parents=True, exist_ok=True)

PAUSA_HTTP = 3    # seg entre pedidos HTTP reales
PAUSA_RENDER = 6  # seg entre renders reales (ademas del propio tiempo de render)

_scraper = cloudscraper.CloudScraper()  # sesion unica (mantiene cookies CF)


def _cache_file(folder: Path, url: str) -> Path:
    return folder / (hashlib.sha1(url.encode("utf-8")).hexdigest()[:16] + ".html")


def get_html(url: str) -> BeautifulSoup:
    """GET por HTTP (cloudscraper) con cache + rate-limiting."""
    cf = _cache_file(CACHE_HTTP, url)
    if cf.exists():
        return BeautifulSoup(cf.read_bytes(), "html.parser")
    time.sleep(PAUSA_HTTP)
    r = _scraper.get(url, timeout=45, allow_redirects=True)
    r.raise_for_status()
    cf.write_bytes(r.content)
    return BeautifulSoup(r.content, "html.parser")


def render_html(url: str) -> BeautifulSoup:
    """Render con navegador headless (espera el XHR) + cache + rate-limiting.

    NUNCA re-renderiza lo cacheado: ese es el ahorro grande, porque cada render
    cuesta ~13s. Si ya esta en disco, lo lee y listo.
    """
    cf = _cache_file(CACHE_RENDER, url)
    if cf.exists():
        return BeautifulSoup(cf.read_text(encoding="utf-8"), "html.parser")
    time.sleep(PAUSA_RENDER)
    # block_images_and_css=False + delay: imprescindible para que la grilla Svelte
    # de stats termine de cargarse antes de leer el HTML.
    soup = botasaurus_browser_get_soup(
        url, block_images_and_css=False, wait_for_complete_page_load=True, delay=7
    )
    cf.write_text(str(soup), encoding="utf-8")
    return soup


def is_cached_render(url: str) -> bool:
    return _cache_file(CACHE_RENDER, url).exists()
