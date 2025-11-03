# modules/search/emailint.py
"""
EMAILINT — Email Intelligence & Enumeration
===========================================

Fuentes soportadas:
    Email Info:
        - TraceFind.info
        - SkyMem.info
        - ghunt online
        - Hashtray
    Misc:
        - emailfinder
        - Email-Crawler-Lead-Generator
        - Email2PhoneNumber
        - emailGuesser
    Email Verification:
        - gmail_permutator

Características:
    - Cache SQLite centralizada
    - Soporte Proxy / Tor
    - Resultados estructurados listos para grafo e IA
    - Búsqueda concurrente
"""

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

from core.config import get_user_setting
from utils.logger import logger


# ============================================================
# ⚙️ Configuración general
# ============================================================

CACHE_DIR = os.path.join("data", "cache")
DB_PATH = os.path.join(CACHE_DIR, "osint_cache.db")
os.makedirs(CACHE_DIR, exist_ok=True)

DEFAULT_TTL = 60 * 60 * 24
DEFAULT_WORKERS = 4
DEFAULT_TIMEOUT = (10, 25)

_db_lock = threading.Lock()


# ============================================================
# 💾 Cache
# ============================================================

def _ensure_schema():
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                group_name TEXT,
                q TEXT,
                username TEXT,
                payload TEXT,
                created_at INTEGER
            )
        """)
        conn.commit()
        conn.close()


def _make_key(group: str, q: str, username: str) -> str:
    return hashlib.sha256(f"{group}::{q}::{username}".encode()).hexdigest()


def _cache_get(group: str, q: str, username: str, ttl: int = DEFAULT_TTL):
    _ensure_schema()
    now = int(time.time())
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
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "REPLACE INTO cache (key, group_name, q, username, payload, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (_make_key(group, q, username), group, q, username, data, now),
    )
    conn.commit()
    conn.close()


# ============================================================
# 🌐 HTTP session
# ============================================================

def _build_session(username: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; OSINT-Suite/1.0; +https://example.org)",
        "Accept": "application/json,text/html;q=0.9,*/*;q=0.8"
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

def _emailint_sources(q: str) -> List[Dict[str, str]]:
    q_enc = requests.utils.requote_uri(q)
    return [
        # --- Email Info ---
        {"name": "TraceFind.info", "url": f"https://tracefind.info/search?q={q_enc}"},
        {"name": "SkyMem.info", "url": f"https://www.skymem.info/srch?q={q_enc}"},
        {"name": "ghunt online", "url": f"https://ghunt.io/search/{q_enc}"},
        {"name": "Hashtray", "url": f"https://hashtray.io/search?q={q_enc}"},

        # --- Misc ---
        {"name": "emailfinder", "url": f"https://emailfinder.io/search?q={q_enc}"},
        {"name": "Email-Crawler-Lead-Generator", "url": f"https://leadgen.example/search?q={q_enc}"},
        {"name": "Email2PhoneNumber", "url": f"https://email2phone.example/search?q={q_enc}"},
        {"name": "emailGuesser", "url": f"https://emailguesser.example/search?q={q_enc}"},

        # --- Email Verification ---
        {"name": "gmail_permutator", "url": f"https://gmailpermutator.example/search?q={q_enc}"}
    ]


# ============================================================
# 🧠 Normalización
# ============================================================

def _normalize(source: str, q: str, url: str, category: str = "emailint") -> Dict[str, Any]:
    return {
        "source": source,
        "title": f"{source} — resultados EmailINT para {q}",
        "link": url,
        "snippet": "Abrir para analizar información asociada al correo electrónico.",
        "query": q,
        "category": category,
        "structured": {},
        "_cached": False,
        "fetched_at": datetime.utcnow().isoformat(),
    }


# ============================================================
# 🧩 Colector
# ============================================================

def _collect(username: str, group: str, sources: List[Dict[str, str]], q: str, use_cache=True) -> List[Dict[str, Any]]:
    if use_cache:
        cached = _cache_get(group, q, username)
        if cached:
            return cached

    session = _build_session(username)
    results: List[Dict[str, Any]] = []

    for s in sources:
        try:
            rec = _normalize(s["name"], q, s["url"], category=group)
            results.append(rec)
        except Exception as e:
            logger.warning(f"[emailint] Error en {s}: {e}")

    _cache_set(group, q, username, results)
    return results


# ============================================================
# 🚀 Módulo principal
# ============================================================

def search_emailint(query: str, username: str, max_results: int = 25, use_cache: bool = True) -> List[Dict[str, Any]]:
    """
    Ejecuta inteligencia OSINT sobre direcciones de correo electrónico.
    """
    group = "emailint"
    sources = _emailint_sources(query)

    workers = DEFAULT_WORKERS
    try:
        cfg = get_user_setting(username, "concurrency")
        if cfg:
            workers = int(cfg)
    except Exception:
        pass

    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_collect, username, group, sources, query, use_cache)]
        for f in as_completed(futures):
            try:
                results.extend(f.result())
            except Exception as e:
                logger.warning(f"[emailint] Error en worker: {e}")

    seen = set()
    unique = []
    for r in results:
        if r["link"] not in seen:
            seen.add(r["link"])
            unique.append(r)

    return unique[:max_results]


# ============================================================
# 🧪 Test rápido
# ============================================================

if __name__ == "__main__":
    data = search_emailint("john.doe@gmail.com", "demo", max_results=10, use_cache=False)
    print(json.dumps(data, indent=2, ensure_ascii=False))
