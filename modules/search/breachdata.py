# modules/search/breachdata.py
"""
BREACHDATA — Módulo OSINT para recopilación de información sobre filtraciones de datos y credenciales.

Fuentes integradas:
    • Credential Leaks: WhatBreach, CyberNews Leak Check, Leaked.Domains,
      Pentester.com, LeakBase, hashmob, ProxyNova COMB Search, Leakpeek,
      exposed.lol, Leaked Password
    • Misc: Venacus, Find.OSINT-Tool.com, Infostealers.info, ScatteredSecrets.com,
      Amibreached.com, Psbdmp-ws-api, LeakRadar, Pastebin Finder, OSINTLeak, Leak-Lookup

Características:
    - Caché SQLite centralizada (data/cache/osint_cache.db)
    - Soporte Tor / proxy (usa core.config.get_user_setting)
    - Compatible con búsquedas por email, username o dominio
    - Resultados normalizados y listos para UI y grafo
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
# ⚙️ Configuración
# ============================================================

CACHE_PATH = os.path.join("data", "cache")
DB_PATH = os.path.join(CACHE_PATH, "osint_cache.db")
os.makedirs(CACHE_PATH, exist_ok=True)

DEFAULT_TTL = 24 * 60 * 60
DEFAULT_WORKERS = 5
DEFAULT_TIMEOUT = (8, 25)

_db_lock = threading.Lock()


# ============================================================
# 🧱 Caché global
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
# 🌐 Sesión HTTP (Tor / proxy)
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

def _credential_leak_sources(q: str) -> List[Dict[str, str]]:
    return [
        {"name": "WhatBreach", "url": f"https://whatbreach.com/?query={q}"},
        {"name": "CyberNews Leak Check", "url": f"https://cybernews.com/personal-data-leak-check/?q={q}"},
        {"name": "Leaked.Domains", "url": f"https://leaked.domains/search?q={q}"},
        {"name": "Pentester.com", "url": f"https://pentester.com/leaks/{q}"},
        {"name": "LeakBase", "url": f"https://leakbase.io/search/{q}"},
        {"name": "hashmob", "url": f"https://hashmob.net/?search={q}"},
        {"name": "ProxyNova COMB Search", "url": f"https://www.proxynova.com/tools/comb/?q={q}"},
        {"name": "Leakpeek", "url": f"https://leakpeek.com/?q={q}"},
        {"name": "exposed.lol", "url": f"https://exposed.lol/search?q={q}"},
        {"name": "Leaked Password", "url": f"https://leakedpassword.com/?search={q}"},
    ]


def _misc_sources(q: str) -> List[Dict[str, str]]:
    return [
        {"name": "Venacus", "url": f"https://venacus.io/search?q={q}"},
        {"name": "Find.OSINT-Tool.com", "url": f"https://find.osint-tool.com/?q={q}"},
        {"name": "Infostealers.info", "url": f"https://infostealers.info/search?q={q}"},
        {"name": "ScatteredSecrets.com", "url": f"https://scatteredsecrets.com/?search={q}"},
        {"name": "Amibreached.com", "url": f"https://amibreached.com/?query={q}"},
        {"name": "Psbdmp-ws-api", "url": f"https://psbdmp.ws/api/search/{q}"},
        {"name": "LeakRadar", "url": f"https://leakr.net/search?q={q}"},
        {"name": "Pastebin Finder", "url": f"https://pastebinfinder.com/?q={q}"},
        {"name": "OSINTLeak", "url": f"https://osintleak.io/?search={q}"},
        {"name": "Leak-Lookup", "url": f"https://leak-lookup.com/?search={q}"},
    ]


# ============================================================
# 🧠 Helpers
# ============================================================

_EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")

def _is_email(q: str) -> bool:
    return bool(_EMAIL_REGEX.match(q))


def _normalize_record(source: str, q: str, url: str, group: str) -> Dict[str, Any]:
    return {
        "source": source,
        "title": f"{source} — resultados para {q}",
        "link": url,
        "snippet": "Abrir para revisar posibles filtraciones o leaks asociados.",
        "query": q,
        "category": group,
        "structured": {},
        "_cached": False,
        "fetched_at": datetime.utcnow().isoformat(),
    }


# ============================================================
# ⚙️ Recolector genérico
# ============================================================

def _collect_from_sources(username: str, group: str, sources: List[Dict[str, str]], q: str, use_cache=True) -> List[Dict[str, Any]]:
    if use_cache:
        cached = _cache_get(group, q, username)
        if cached:
            return cached

    s = _build_session(username)
    results = []

    for src in sources:
        try:
            rec = _normalize_record(src["name"], q, src["url"], group)
            results.append(rec)
        except Exception as e:
            logger.warning(f"[breachdata] Error con fuente {src}: {e}")

    _cache_set(group, q, username, results)
    return results


# ============================================================
# 🚀 Módulo principal
# ============================================================

def search_breachdata(query: str, username: str, max_results: int = 30, use_cache: bool = True) -> List[Dict[str, Any]]:
    """
    Ejecuta búsqueda OSINT sobre fugas de datos relacionadas con:
        - emails
        - usernames
        - dominios
    """
    results: List[Dict[str, Any]] = []
    groups = []

    # detección del tipo de query
    if _is_email(query):
        groups = ["credential_leaks", "misc"]
    elif re.match(r"^[\w.-]+\.[a-zA-Z]{2,}$", query):
        groups = ["misc", "credential_leaks"]
    else:
        groups = ["credential_leaks"]

    mapping = {
        "credential_leaks": _credential_leak_sources,
        "misc": _misc_sources,
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
                logger.warning(f"[breachdata] Error en tarea: {e}")

    # de-duplicar por URL
    seen = set()
    unique = []
    for r in results:
        key = (r.get("link") or r.get("title"))
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique[:max_results]


# ============================================================
# 🧪 Test rápido
# ============================================================

if __name__ == "__main__":
    test = search_breachdata("demo@example.com", "demo", max_results=10, use_cache=False)
    print(json.dumps(test, indent=2, ensure_ascii=False))
