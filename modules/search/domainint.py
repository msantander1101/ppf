# modules/search/domainint.py
"""
DOMAININT — Módulo OSINT para inteligencia de dominios.
Fuentes integradas:
    • Misc: HaveIBeenSquatted, BigDomainData, DomainIQ Tools
    • Subdomain Enumeration: SubDoSec, SubDomainRadar.io, Subdomain Finder C99, PugRecon
    • DNS Lookup: Dnslytics
    • Uncategorized: Rintel

Características:
    - Caché SQLite centralizada (data/cache/osint_cache.db)
    - Soporte Tor / proxy (lee configuración desde core.config.get_user_setting)
    - Búsqueda estructurada y adaptable (dominio o subdominio)
    - Formato uniforme compatible con grafo y UI
"""

import os
import re
import json
import time
import hashlib
import sqlite3
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import requests
from core.config import get_user_setting
from utils.logger import logger

# ============================================================
# ⚙️ Configuración global
# ============================================================

CACHE_PATH = os.path.join("data", "cache")
DB_PATH = os.path.join(CACHE_PATH, "osint_cache.db")
os.makedirs(CACHE_PATH, exist_ok=True)

DEFAULT_TTL = 24 * 60 * 60  # 24h de validez
DEFAULT_WORKERS = 4
DEFAULT_TIMEOUT = (10, 25)

_db_lock = threading.Lock()


# ============================================================
# 🧱 CACHÉ (global compartida)
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
# 🌐 Sesión HTTP (Tor o proxy)
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
# 🔎 Fuentes de búsqueda (adapters)
# ============================================================

def _misc_sources(q: str) -> List[Dict[str, str]]:
    return [
        {"name": "HaveIBeenSquatted", "url": f"https://haveibeensquatted.com/domain/{q}"},
        {"name": "BigDomainData", "url": f"https://bigdomaindata.com/report/{q}"},
        {"name": "DomainIQ Tools", "url": f"https://www.domainiq.com/domain/{q}"},
    ]


def _subdomain_sources(q: str) -> List[Dict[str, str]]:
    return [
        {"name": "SubDoSec", "url": f"https://subdosec.com/scan/{q}"},
        {"name": "SubDomainRadar.io", "url": f"https://subdomainradar.io/domain/{q}"},
        {"name": "Subdomain Finder C99", "url": f"https://subdomainfinder.c99.nl/scans/{q}"},
        {"name": "PugRecon", "url": f"https://pugrecon.io/domain/{q}"},
    ]


def _dns_sources(q: str) -> List[Dict[str, str]]:
    return [
        {"name": "Dnslytics", "url": f"https://dnslytics.com/domain/{q}"},
    ]


def _uncategorized_sources(q: str) -> List[Dict[str, str]]:
    return [
        {"name": "Rintel", "url": f"https://rintel.io/search?domain={q}"},
    ]


# ============================================================
# 🧠 Normalizador
# ============================================================

def _normalize_record(source: str, q: str, url: str, group: str) -> Dict[str, Any]:
    return {
        "source": source,
        "title": f"{source} — resultados para {q}",
        "link": url,
        "snippet": f"Abrir para revisar información de dominio.",
        "domain": q,
        "category": group,
        "structured": {},
        "_cached": False,
        "fetched_at": datetime.utcnow().isoformat(),
    }


# ============================================================
# 🔧 Recolector genérico
# ============================================================

def _collect_from_sources(username: str, group: str, sources: List[Dict[str, str]], q: str, use_cache=True) -> List[Dict[str, Any]]:
    if use_cache:
        cached = _cache_get(group, q, username)
        if cached:
            return cached

    s = _build_session(username)
    results: List[Dict[str, Any]] = []

    for src in sources:
        try:
            name = src.get("name")
            url = src.get("url")
            rec = _normalize_record(name, q, url, group)
            results.append(rec)
        except Exception as e:
            logger.warning(f"[domainint] Error con fuente {src}: {e}")

    _cache_set(group, q, username, results)
    return results


# ============================================================
# 🚀 Módulo principal
# ============================================================

def search_domainint(query: str, username: str, max_results: int = 30, use_cache: bool = True) -> List[Dict[str, Any]]:
    """
    Ejecuta búsqueda de inteligencia sobre dominios y subdominios.
    Detecta automáticamente si el valor es dominio, subdominio o IP.
    """
    results: List[Dict[str, Any]] = []
    groups = []

    # Detección básica
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", query):
        groups = ["dns"]
    elif query.count(".") >= 2:
        groups = ["subdomain", "dns", "misc"]
    else:
        groups = ["misc", "dns", "uncategorized"]

    mapping = {
        "misc": _misc_sources,
        "subdomain": _subdomain_sources,
        "dns": _dns_sources,
        "uncategorized": _uncategorized_sources,
    }

    workers = DEFAULT_WORKERS
    try:
        cfg = get_user_setting(username, "concurrency")
        if cfg:
            workers = int(cfg)
    except Exception:
        pass

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = []
        for g in groups:
            fn = mapping[g]
            sources = fn(query)
            futures.append(ex.submit(_collect_from_sources, username, g, sources, query, use_cache))

        for fut in as_completed(futures):
            try:
                chunk = fut.result()
                results.extend(chunk)
            except Exception as e:
                logger.warning(f"[domainint] Error en {fut}: {e}")

    # deduplicar por link
    seen = set()
    unique = []
    for r in results:
        key = (r.get("link") or r.get("title"))
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique[:max_results]


# ============================================================
# 🧪 Test rápido local
# ============================================================

if __name__ == "__main__":
    test = search_domainint("example.com", "demo", max_results=10, use_cache=False)
    print(json.dumps(test, indent=2, ensure_ascii=False))
