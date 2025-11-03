# modules/search/geoint.py
"""
GEOINT — Módulo OSINT para inteligencia geoespacial (geolocalización e información visual).
Fuentes integradas:
    • Map to Censys
    • Maps.Video
    • geoguessr gpt
    • Google Maps Scraper
    • Instant Street View
    • IP2Location
    • FindPicLocation

Características:
    - Caché SQLite centralizada (data/cache/osint_cache.db)
    - Soporte Tor / proxy (lee desde core.config.get_user_setting)
    - Búsqueda por IP, coordenadas o texto libre (dirección, localización)
    - Salida estructurada compatible con grafo y UI
"""

import os
import re
import json
import time
import hashlib
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from core.config import get_user_setting
from utils.logger import logger


# ============================================================
# ⚙️ Configuración global
# ============================================================

CACHE_PATH = os.path.join("data", "cache")
DB_PATH = os.path.join(CACHE_PATH, "osint_cache.db")
os.makedirs(CACHE_PATH, exist_ok=True)

DEFAULT_TTL = 24 * 60 * 60
DEFAULT_WORKERS = 4
DEFAULT_TIMEOUT = (8, 25)

_db_lock = threading.Lock()


# ============================================================
# 🧱 Caché
# ============================================================

def _ensure_schema():
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    source_group TEXT,
                    q TEXT,
                    username TEXT,
                    payload TEXT,
                    created_at INTEGER
                )
            """)
            conn.commit()
        finally:
            conn.close()


def _make_key(group: str, q: str, username: str) -> str:
    raw = f"{group}::{q}::{username}"
    return hashlib.sha256(raw.encode()).hexdigest()


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
            "REPLACE INTO cache (key, source_group, q, username, payload, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (_make_key(group, q, username), group, q, username, data, now),
        )
        conn.commit()
        conn.close()


# ============================================================
# 🌐 Sesión HTTP
# ============================================================

def _build_session(username: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36",
    })
    try:
        proxy = get_user_setting(username, "proxy")
    except Exception:
        proxy = None

    if proxy:
        s.proxies.update({"http": proxy, "https": proxy})
    else:
        s.proxies.update({"http": "socks5h://127.0.0.1:9050", "https": "socks5h://127.0.0.1:9050"})
    s.timeout = DEFAULT_TIMEOUT
    return s


# ============================================================
# 🔍 Fuentes
# ============================================================

def _geoint_sources(q: str) -> List[Dict[str, str]]:
    return [
        {"name": "Map to Censys", "url": f"https://censys.io/ipv4?q={q}"},
        {"name": "Maps.Video", "url": f"https://maps.video/search?q={q}"},
        {"name": "geoguessr gpt", "url": f"https://chat.openai.com/?model=gpt-geo&query={q}"},
        {"name": "Google Maps Scraper", "url": f"https://www.google.com/maps/search/{q.replace(' ', '+')}"},
        {"name": "Instant Street View", "url": f"https://www.instantstreetview.com/@{q}"},
        {"name": "IP2Location", "url": f"https://www.ip2location.com/demo/{q}"},
        {"name": "FindPicLocation", "url": f"https://findpiclocation.com/search?q={q}"},
    ]


# ============================================================
# 🧠 Helpers
# ============================================================

_COORD_REGEX = re.compile(r"^-?\d{1,3}\.\d+,\s*-?\d{1,3}\.\d+$")
_IP_REGEX = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")

def _is_ip(q: str) -> bool:
    return bool(_IP_REGEX.match(q))

def _is_coords(q: str) -> bool:
    return bool(_COORD_REGEX.match(q))


def _normalize_record(source: str, q: str, url: str) -> Dict[str, Any]:
    return {
        "source": source,
        "title": f"{source} — resultados geoespaciales para {q}",
        "link": url,
        "snippet": "Abrir para analizar la ubicación o contexto visual.",
        "query": q,
        "structured": {},
        "_cached": False,
        "fetched_at": datetime.utcnow().isoformat(),
    }


# ============================================================
# 🕸️ Recolector
# ============================================================

def _collect_geoint(username: str, group: str, sources: List[Dict[str, str]], q: str, use_cache=True) -> List[Dict[str, Any]]:
    if use_cache:
        cached = _cache_get(group, q, username)
        if cached:
            return cached

    _build_session(username)  # session disponible si se amplía
    results = []
    for src in sources:
        try:
            rec = _normalize_record(src["name"], q, src["url"])
            results.append(rec)
        except Exception as e:
            logger.warning(f"[geoint] Error en fuente {src}: {e}")

    _cache_set(group, q, username, results)
    return results


# ============================================================
# 🚀 Módulo principal
# ============================================================

def search_geoint(query: str, username: str, max_results: int = 25, use_cache: bool = True) -> List[Dict[str, Any]]:
    """
    Realiza inteligencia geoespacial (GEOINT) sobre IPs, coordenadas, direcciones o ubicaciones.
    """
    results: List[Dict[str, Any]] = []

    group = "geoint"
    sources = _geoint_sources(query)

    workers = DEFAULT_WORKERS
    try:
        cfg = get_user_setting(username, "concurrency")
        if cfg:
            workers = int(cfg)
    except Exception:
        pass

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_collect_geoint, username, group, sources, query, use_cache)]
        for fut in as_completed(futures):
            try:
                results.extend(fut.result())
            except Exception as e:
                logger.warning(f"[geoint] Error en tarea: {e}")

    # deduplicado simple
    seen, unique = set(), []
    for r in results:
        if r["link"] not in seen:
            seen.add(r["link"])
            unique.append(r)

    return unique[:max_results]


# ============================================================
# 🧪 Test rápido
# ============================================================

if __name__ == "__main__":
    test = search_geoint("40.4168,-3.7038", "demo", max_results=10, use_cache=False)
    print(json.dumps(test, indent=2, ensure_ascii=False))
