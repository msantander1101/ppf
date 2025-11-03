# modules/search/publicdata.py
"""
PUBLICDATA — Módulo OSINT: búsqueda en fuentes de datos públicos y repositorios.
Fuentes (curadas por el usuario):
    NFOMINER, xeuledoc, SurveillanceWatch.io, Postman Public API, OONI Explorer,
    ODCrawler, Rostral.io, impersonal.me, Yorba, Github Monitor, Google Trends,
    EyeDex.org, Data.Occrp.org, GHIntel.secrets.ninja, postleaks, information laundromat,
    ransom-privtools, firebaseExploiter, Criminal IP, JSNinja, Favicorn, Carbon14,
    FaviHash, Keyword Discovery, Chronos, Oh365UserFinder, WikiStalk, MarketScreener,
    Octosuite, Cyber URL Scanner, ...
Características:
    - Cache SQLite para resultados
    - Soporte proxy / Tor (lee proxy del usuario con core.config.get_user_setting)
    - Concurrency configurable
    - Resultados normalizados: {source, title, link, snippet, category, structured, fetched_at}
    - Lista de "sources" predefinida que devuelve enlaces e info mínima hasta que se implemente el scraper/connector.
"""

from __future__ import annotations

import os
import json
import time
import hashlib
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from utils.logger import logger
from core.config import get_user_setting

# ---------------------------
# Config / paths
# ---------------------------
CACHE_DIR = os.path.join("data", "cache")
DB_PATH = os.path.join(CACHE_DIR, "osint_cache.db")
os.makedirs(CACHE_DIR, exist_ok=True)

DEFAULT_TTL = 60 * 60 * 24  # 24h
DEFAULT_WORKERS = 4
DEFAULT_TIMEOUT = (10, 25)

_db_lock = threading.Lock()


# ---------------------------
# Caché simple (SQLite)
# ---------------------------
def _ensure_schema():
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    group_name TEXT,
                    q TEXT,
                    username TEXT,
                    payload TEXT,
                    created_at INTEGER
                )
                """
            )
            conn.commit()
        finally:
            conn.close()


def _make_key(group: str, q: str, username: str) -> str:
    return hashlib.sha256(f"{group}::{q}::{username}".encode()).hexdigest()


def _cache_get(group: str, q: str, username: str, ttl: int = DEFAULT_TTL) -> Optional[List[Dict[str, Any]]]:
    _ensure_schema()
    now = int(time.time())
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute("SELECT payload, created_at FROM cache WHERE key=?", (_make_key(group, q, username),))
        row = cur.fetchone()
        conn.close()
    if not row:
        return None
    payload, created = row
    if now - created > ttl:
        return None
    try:
        data = json.loads(payload)
        for r in data:
            r["_cached"] = True
        return data
    except Exception:
        return None


def _cache_set(group: str, q: str, username: str, payload: List[Dict[str, Any]]):
    _ensure_schema()
    now = int(time.time())
    data = json.dumps(payload, ensure_ascii=False)
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "REPLACE INTO cache (key, group_name, q, username, payload, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (_make_key(group, q, username), group, q, username, data, now),
        )
        conn.commit()
        conn.close()


# ---------------------------
# HTTP Session (proxy / tor)
# ---------------------------
def _build_session(username: str) -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (compatible; OSINT-Suite/1.0; +https://example.org)",
            "Accept": "application/json, text/html, */*",
        }
    )
    try:
        proxy = get_user_setting(username, "proxy")
    except Exception:
        proxy = None

    if proxy:
        s.proxies.update({"http": proxy, "https": proxy})
    else:
        # por defecto intentamos usar Tor socks5 si no hay proxy explícito
        s.proxies.update({"http": "socks5h://127.0.0.1:9050", "https": "socks5h://127.0.0.1:9050"})
    s.timeout = DEFAULT_TIMEOUT
    return s


# ---------------------------
# Fuentes: devolverán un listado de {name, url} para cada fuente
# (implementa scraper/connector real más adelante)
# ---------------------------
def _publicdata_sources(query: str) -> List[Dict[str, str]]:
    # Para cada fuente devolvemos el enlace de búsqueda (plantilla).
    # Cuando implementes el connector real, sustituye por la llamada API/scrape.
    q_enc = requests.utils.requote_uri(query)
    return [
        {"name": "NFOMINER", "url": f"https://nfominer.com/search?q={q_enc}"},
        {"name": "xeuledoc", "url": f"https://xeuledoc.example/search?q={q_enc}"},
        {"name": "SurveillanceWatch", "url": f"https://surveillancewatch.io/search?q={q_enc}"},
        {"name": "Postman Public API", "url": f"https://api.postman.com/public-apis?search={q_enc}"},
        {"name": "OONI Explorer", "url": f"https://explorer.ooni.org/search?pattern={q_enc}"},
        {"name": "ODCrawler", "url": f"https://odcrawler.example/search?q={q_enc}"},
        {"name": "Rostral.io", "url": f"https://rostral.io/search?q={q_enc}"},
        {"name": "impersonal.me", "url": f"https://impersonal.me/search?q={q_enc}"},
        {"name": "Yorba", "url": f"https://yorba.example/search?q={q_enc}"},
        {"name": "Github Monitor", "url": f"https://github.com/search?q={q_enc}"},
        {"name": "Google Trends", "url": f"https://trends.google.com/trends/search?q={q_enc}"},
        {"name": "EyeDex", "url": f"https://eyedex.org/search?q={q_enc}"},
        {"name": "Data.Occrp", "url": f"https://data.occrp.org/search?q={q_enc}"},
        {"name": "GHIntel.secrets.ninja", "url": f"https://ghintel.secrets.ninja/search?q={q_enc}"},
        {"name": "postleaks", "url": f"https://postleaks.example/search?q={q_enc}"},
        {"name": "information laundromat", "url": f"https://informationlaundromat.example/search?q={q_enc}"},
        {"name": "ransom-privtools", "url": f"https://ransom-privtools.example/search?q={q_enc}"},
        {"name": "firebaseExploiter", "url": f"https://firebaseexploiter.example/search?q={q_enc}"},
        {"name": "Criminal IP", "url": f"https://criminalip.io/search?q={q_enc}"},
        {"name": "JSNinja", "url": f"https://jsninja.example/search?q={q_enc}"},
        {"name": "Favicorn", "url": f"https://favicorn.example/search?q={q_enc}"},
        {"name": "Carbon14", "url": f"https://carbon14.example/search?q={q_enc}"},
        {"name": "FaviHash", "url": f"https://favihash.example/search?q={q_enc}"},
        {"name": "Keyword Discovery", "url": f"https://keyworddiscovery.example/search?q={q_enc}"},
        {"name": "Chronos", "url": f"https://chronos.example/search?q={q_enc}"},
        {"name": "Oh365UserFinder", "url": f"https://oh365userfinder.example/search?q={q_enc}"},
        {"name": "WikiStalk", "url": f"https://wikistalk.example/search?q={q_enc}"},
        {"name": "MarketScreener", "url": f"https://marketscreener.com/search?q={q_enc}"},
        {"name": "Octosuite", "url": f"https://octosuite.example/search?q={q_enc}"},
        {"name": "Cyber URL Scanner", "url": f"https://cyberurlscanner.example/search?q={q_enc}"},
    ]


# ---------------------------
# Normalización de resultados
# ---------------------------
def _normalize(source_name: str, query: str, url: str, category: str = "publicdata") -> Dict[str, Any]:
    return {
        "source": source_name,
        "title": f"{source_name} — resultados para {query}",
        "link": url,
        "snippet": f"Enlace a búsqueda/search en {source_name}",
        "query": query,
        "category": category,
        "structured": {},
        "_cached": False,
        "fetched_at": datetime.utcnow().isoformat(),
    }


# ---------------------------
# Colección paralela desde las fuentes (actualmente: enlaces normalizados)
# ---------------------------
def _collect(username: str, group: str, sources: List[Dict[str, str]], query: str, use_cache: bool = True) -> List[Dict[str, Any]]:
    if use_cache:
        cached = _cache_get(group, query, username)
        if cached:
            return cached

    # crea sesión para posibles requests reales
    session = _build_session(username)
    results: List[Dict[str, Any]] = []
    for s in sources:
        try:
            # placeholder: por ahora no hacemos scraping, sólo normalizamos la URL
            rec = _normalize(s["name"], query, s["url"], category=group)
            results.append(rec)
        except Exception as e:
            logger.warning(f"[publicdata] Error normalizando fuente {s}: {e}")

    # guardar en caché
    try:
        _cache_set(group, query, results)
    except Exception as e:
        logger.warning(f"[publicdata] No se pudo guardar cache: {e}")

    return results


# ---------------------------
# API público: search_public_data
# ---------------------------
def search_public_data(query: str, username: str, max_results: int = 30, use_cache: bool = True) -> List[Dict[str, Any]]:
    """
    Ejecuta búsquedas en fuentes públicas (publicdata).
    Devuelve una lista de registros normalizados.
    """
    group = "publicdata"
    # try to read concurrency from user config
    workers = DEFAULT_WORKERS
    try:
        cfg = get_user_setting(username, "concurrency")
        if cfg:
            workers = int(cfg)
    except Exception:
        pass

    sources = _publicdata_sources(query)

    # ejecución paralela (aunque _collect actualmente no hace requests - diseñada para cuando implementes connectors)
    results: List[Dict[str, Any]] = []
    if workers <= 1:
        results = _collect(username, group, sources, query, use_cache=use_cache)
    else:
        # chunk sources to tasks
        chunk_size = max(1, len(sources) // workers)
        chunks = [sources[i : i + chunk_size] for i in range(0, len(sources), chunk_size)]
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_collect, username, group, c, query, use_cache) for c in chunks]
            for fut in as_completed(futures):
                try:
                    res = fut.result()
                    if res:
                        results.extend(res)
                except Exception as e:
                    logger.warning(f"[publicdata] Error en worker: {e}")

    # deduplicate by link
    seen = set()
    unique: List[Dict[str, Any]] = []
    for r in results:
        key = r.get("link") or r.get("title")
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique[:max_results]


# ---------------------------
# Si se ejecuta directamente (test)
# ---------------------------
if __name__ == "__main__":
    test = search_public_data("Miguel Santander Romera", "demo", max_results=10, use_cache=False)
    print(json.dumps(test, indent=2, ensure_ascii=False))

