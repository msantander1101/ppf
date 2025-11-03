# modules/search/darkweb.py
"""
Módulo de búsqueda Dark Web OSINT
Fuentes: Danex, Torry, Dargle, Tor.link, Vormweb, OnionLand.io, Onion Search Engine, OnionLinkHub.
- Proxy Tor automático (lee settings del usuario: proxy/use_tor)
- Rotación de mirrors .onion cuando estén disponibles
- Caché por (fuente, query) para reducir bloqueos
- Logging en BD (SearchLog)
"""

from __future__ import annotations
from typing import List, Dict, Optional
import time
import hashlib

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import diskcache as dc

from utils.logger import logger
from core.database import get_session
from core.entities import SearchLog
from core.config import get_user_setting

# =========================
# Config general
# =========================
DEFAULT_TOR_PROXY = "socks5h://127.0.0.1:9050"
TIMEOUT = 25
SLEEP_BETWEEN_SOURCES = 2.0
CACHE_DIR = "./cache/darkweb"
CACHE_TTL = 60 * 60 * 6  # 6 horas
cache = dc.Cache(CACHE_DIR)

# =========================
# Fuentes + mirrors .onion
# (clearnet primero, luego posibles .onion)
# =========================
DARKWEB_SOURCES: List[Dict] = [
    {
        "name": "Danex",
        "endpoints": [
            {"url": "https://danex.io/search?q={query}", "parser": "html", "selector": ".result a, .result h3"},
            # (No mirror onion público estable conocido)
        ],
    },
    {
        "name": "Torry",
        "endpoints": [
            {"url": "https://torry.io/search?q={query}", "parser": "html", "selector": "div.search-result a"},
        ],
    },
    {
        "name": "Dargle",
        "endpoints": [
            {"url": "https://dargle.io/search?q={query}", "parser": "html", "selector": "article a, article h2"},
        ],
    },
    {
        "name": "Tor.link",
        "endpoints": [
            {"url": "https://tor.link/search?q={query}", "parser": "html", "selector": "div.result a"},
        ],
    },
    {
        "name": "Vormweb",
        "endpoints": [
            {"url": "https://vormweb.com/search?q={query}", "parser": "html", "selector": "div.result-item a"},
        ],
    },
    {
        "name": "OnionLand.io",
        "endpoints": [
            {"url": "https://onionland.io/search?q={query}&format=json", "parser": "json"},
            # Ejemplo ficticio de mirror onion:
            {"url": "http://onionlandxxxxxxxxxxxxxxxxxxxxxxx.onion/search?q={query}&format=json", "parser": "json", "requires_tor": True},
        ],
    },
    {
        "name": "Onion Search Engine",
        "endpoints": [
            {"url": "https://onionsearchengine.com/search?q={query}", "parser": "html", "selector": "div.result a"},
            # Mirror onion hipotético:
            {"url": "http://osexxxxxxxxxxxxxxxxxxxxxxxxxxxx.onion/search?q={query}", "parser": "html", "selector": "div.result a", "requires_tor": True},
        ],
    },
    {
        "name": "OnionLinkHub",
        "endpoints": [
            {"url": "https://onionhub.link/search?q={query}", "parser": "html", "selector": "div.result-card a"},
        ],
    },
]


# =========================
# Helpers
# =========================
def _cache_key(query: str, source: str, endpoint_url: str) -> str:
    return hashlib.sha256(f"{source}:{endpoint_url}:{query}".encode()).hexdigest()


def _headers() -> dict:
    ua = UserAgent()
    return {
        "User-Agent": ua.random,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
        "Connection": "close",
    }


def _resolve_proxy(username: Optional[str]) -> Dict[str, str] | None:
    """
    Determina qué proxy usar:
    - Si el usuario tiene 'proxy' -> usarlo (http/https)
    - Si 'use_tor' == 'true' -> usar Tor socks5h por defecto
    - Si la URL es .onion y no hay Tor/proxy socks -> no se puede acceder
    """
    user_proxy = get_user_setting(username, "proxy") if username else None
    use_tor = (get_user_setting(username, "use_tor") or "").lower() == "true" if username else False

    # Si el usuario ha configurado un proxy explícito, úsalo
    if user_proxy:
        # Para .onion necesitarás un proxy SOCKS (ej: socks5h://localhost:9050)
        return {"http": user_proxy, "https": user_proxy}

    # Si no hay proxy explícito pero use_tor está activo -> Tor por defecto
    if use_tor:
        return {"http": DEFAULT_TOR_PROXY, "https": DEFAULT_TOR_PROXY}

    # Sin proxy
    return None


def _can_use_endpoint(endpoint_url: str, proxies: Optional[Dict[str, str]], endpoint_requires_tor: bool) -> bool:
    """
    Si el endpoint requiere Tor (.onion o marcado), solo usamos si proxies apuntan a socks5h
    """
    is_onion = endpoint_url.startswith("http://") and endpoint_url.endswith(".onion") or ".onion/" in endpoint_url
    if endpoint_requires_tor or is_onion:
        if not proxies:
            return False
        # Consideramos Tor si contiene socks5h
        return str(proxies.get("http", "")) .startswith("socks5h") or str(proxies.get("https", "")).startswith("socks5h")
    return True


def _fetch_html(url: str, proxies: Optional[Dict[str, str]]) -> Optional[BeautifulSoup]:
    try:
        r = requests.get(url, headers=_headers(), proxies=proxies, timeout=TIMEOUT)
        if r.status_code == 200 and "text/html" in r.headers.get("Content-Type", ""):
            return BeautifulSoup(r.text, "html.parser")
        logger.warning(f"[darkweb] [{r.status_code}] no HTML en {url}")
    except Exception as e:
        logger.warning(f"[darkweb] fallo fetch HTML {url}: {e}")
    return None


def _fetch_json(url: str, proxies: Optional[Dict[str, str]]) -> Optional[List[Dict]]:
    try:
        r = requests.get(url, headers=_headers(), proxies=proxies, timeout=TIMEOUT)
        if r.status_code == 200 and "application/json" in r.headers.get("Content-Type", ""):
            return r.json()
        logger.warning(f"[darkweb] [{r.status_code}] no JSON en {url}")
    except Exception as e:
        logger.warning(f"[darkweb] fallo fetch JSON {url}: {e}")
    return None


def _normalize_result(title: str, link: str, snippet: str, source: str) -> Dict:
    return {
        "title": title.strip() if title else "Sin título",
        "link": link.strip() if link else "",
        "snippet": snippet.strip() if snippet else "",
        "source": source,
        "_type": "darkweb",
    }


# =========================
# API principal
# =========================
def search_darkweb(query: str, username: Optional[str] = None, max_results: int = 30, use_cache: bool = True) -> List[Dict]:
    """
    Busca 'query' en todas las fuentes declaradas.
    - Respeta mirrors .onion si hay proxy Tor
    - Devuelve lista homogénea de dicts
    - Guarda log en BD
    """
    proxies = _resolve_proxy(username)
    all_results: List[Dict] = []

    for src in DARKWEB_SOURCES:
        source_name = src["name"]
        source_results: List[Dict] = []

        for ep in src["endpoints"]:
            url = ep["url"].format(query=query)
            requires_tor = ep.get("requires_tor", False)

            # Si endpoint requiere Tor / onion y no hay Tor activo, saltamos
            if not _can_use_endpoint(url, proxies, requires_tor):
                logger.info(f"[darkweb] saltando endpoint (requiere Tor): {url}")
                continue

            key = _cache_key(query, source_name, url)
            if use_cache:
                cached = cache.get(key)
                if cached:
                    logger.info(f"[darkweb] cache hit: {source_name} -> {url}")
                    source_results.extend(cached)
                    break  # este endpoint ya nos dio resultados

            logger.info(f"[darkweb] 🔍 {source_name} → {url}")
            fetched: List[Dict] = []

            if ep["parser"] == "json":
                data = _fetch_json(url, proxies)
                if data:
                    for d in data[:max_results]:
                        fetched.append(
                            _normalize_result(
                                d.get("title") or d.get("name", "Sin título"),
                                d.get("link") or d.get("url", ""),
                                d.get("snippet") or d.get("description", ""),
                                source_name,
                            )
                        )

            elif ep["parser"] == "html":
                soup = _fetch_html(url, proxies)
                if soup:
                    # Buscamos anchors y descripciones cercanas
                    for a in soup.select(ep["selector"])[:max_results]:
                        title = a.get_text(" ", strip=True)
                        link = a.get("href") or ""
                        # Heurística de snippet
                        parent = a.parent if a else None
                        snippet_el = None
                        if parent:
                            snippet_el = parent.find("p") or parent.find(class_="desc") or parent.find(class_="snippet")
                        snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
                        fetched.append(_normalize_result(title, link, snippet, source_name))

            if fetched:
                # guarda en cache y añade a resultados
                if use_cache:
                    cache.set(key, fetched, expire=CACHE_TTL)
                source_results.extend(fetched)
                # pasamos al siguiente source (un endpoint bueno basta)
                break

            # Si este endpoint no devolvió nada, probamos siguiente mirror
            time.sleep(1.0)

        all_results.extend(source_results)
        time.sleep(SLEEP_BETWEEN_SOURCES)

    logger.info(f"[darkweb] total resultados: {len(all_results)}")

    # ==== Log en BD ====
    try:
        with get_session() as session:
            log = SearchLog(
                query=f"darkweb:{query}",
                result=str(all_results),
                user_id=username,
                type="darkweb_search",
            )
            session.add(log)
            session.commit()
        logger.info("[darkweb] Log guardado en BD")
    except Exception as e:
        logger.warning(f"[darkweb] no se pudo guardar log en BD: {e}")

    return all_results
