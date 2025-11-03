# modules/search/webosint.py
"""
WEBOSINT — Módulo OSINT para inteligencia web y análisis técnico de dominios.

Fuentes soportadas (Misc):
    • YUPGR Subdomain Finder
    • MetaBeta
    • Nikto Online Scanner
    • Cerast Intelligence
    • NerdyData
    • BuiltWith
    • WHOIS History by WhoisXML
    • I Know What You Download
    • AnswerThePublic
    • AtSame IP
    • Sitechecker Similar Websites
    • Pentest-Tools.com
    • DotDB.com
    • DorkGenius
    • Favihunter
    • PageCached.com
    • Wayback-Google-Analytics
    • wayBackLister
    • web-check.xyz
    • Investigator

Características:
    - Cache SQLite compartida (data/cache/osint_cache.db)
    - Soporte proxy / Tor configurable
    - Estructura lista para incorporar conectores reales
    - Resultados estructurados compatibles con grafo e IA
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
DEFAULT_WORKERS = 4
DEFAULT_TIMEOUT = (10, 25)

_db_lock = threading.Lock()


# ============================================================
# 💾 Sistema de caché
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
            "REPLACE INTO cache (key, source_group, q, username, payload, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (_make_key(group, q, username), group, q, username, data, now),
        )
        conn.commit()
        conn.close()


# ============================================================
# 🌐 Sesión HTTP con soporte Tor/Proxy
# ============================================================

def _build_session(username: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; OSINT-Suite/1.0; +https://example.org)",
        "Accept": "application/json, text/html;q=0.9,*/*;q=0.8"
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
# 🔍 Fuentes de inteligencia web
# ============================================================

def _webosint_sources(query: str) -> List[Dict[str, str]]:
    q_enc = requests.utils.requote_uri(query)
    return [
        {"name": "YUPGR Subdomain Finder", "url": f"https://yupgr.com/subdomain-finder?q={q_enc}"},
        {"name": "MetaBeta", "url": f"https://metabeta.io/search?q={q_enc}"},
        {"name": "Nikto Online Scanner", "url": f"https://pentest-tools.com/network-vulnerability-scanner/nmap-online-scanner?target={q_enc}"},
        {"name": "Cerast Intelligence", "url": f"https://cerast.io/intel?q={q_enc}"},
        {"name": "NerdyData", "url": f"https://nerdydata.com/search?query={q_enc}"},
        {"name": "BuiltWith", "url": f"https://builtwith.com/{q_enc}"},
        {"name": "WHOIS History by WhoisXML", "url": f"https://whoisxmlapi.com/whoisserver/WhoisService?domainName={q_enc}"},
        {"name": "I Know What You Download", "url": f"https://iknowwhatyoudownload.com/en/peer/?q={q_enc}"},
        {"name": "AnswerThePublic", "url": f"https://answerthepublic.com/results/{q_enc}"},
        {"name": "AtSame IP", "url": f"https://atsameip.intercode.ca/?host={q_enc}"},
        {"name": "Sitechecker Similar Websites", "url": f"https://sitechecker.pro/similar-websites/{q_enc}"},
        {"name": "Pentest-Tools.com", "url": f"https://pentest-tools.com/?q={q_enc}"},
        {"name": "DotDB.com", "url": f"https://dotdb.com/search?q={q_enc}"},
        {"name": "DorkGenius", "url": f"https://dorkgenius.com/?query={q_enc}"},
        {"name": "Favihunter", "url": f"https://favihunter.io/search?query={q_enc}"},
        {"name": "PageCached.com", "url": f"https://pagecached.com/?url={q_enc}"},
        {"name": "Wayback-Google-Analytics", "url": f"https://wayback-google-analytics.io/analyze?url={q_enc}"},
        {"name": "wayBackLister", "url": f"https://waybacklister.io/search?q={q_enc}"},
        {"name": "web-check.xyz", "url": f"https://web-check.xyz/?url={q_enc}"},
        {"name": "Investigator", "url": f"https://investigator.io/search?q={q_enc}"},
    ]


# ============================================================
# 🧠 Normalización
# ============================================================

def _normalize(source: str, q: str, url: str, category: str = "webosint") -> Dict[str, Any]:
    return {
        "source": source,
        "title": f"{source} — resultados para {q}",
        "link": url,
        "snippet": "Abrir para revisar información técnica, subdominios o tecnología del sitio.",
        "query": q,
        "category": category,
        "structured": {},
        "_cached": False,
        "fetched_at": datetime.utcnow().isoformat(),
    }


# ============================================================
# 🕸️ Recolector
# ============================================================

def _collect(username: str, group: str, sources: List[Dict[str, str]], q: str, use_cache=True) -> List[Dict[str, Any]]:
    if use_cache:
        cached = _cache_get(group, q, username)
        if cached:
            return cached

    _build_session(username)
    results: List[Dict[str, Any]] = []

    for s in sources:
        try:
            rec = _normalize(s["name"], q, s["url"], category=group)
            results.append(rec)
        except Exception as e:
            logger.warning(f"[webosint] Error con fuente {s}: {e}")

    _cache_set(group, q, username, results)
    return results


# ============================================================
# 🚀 Búsqueda principal
# ============================================================

def search_webosint(query: str, username: str, max_results: int = 25, use_cache: bool = True) -> List[Dict[str, Any]]:
    """
    Ejecuta inteligencia web OSINT sobre dominios o URLs.
    """
    group = "webosint"
    sources = _webosint_sources(query)

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
        for fut in as_completed(futures):
            try:
                results.extend(fut.result())
            except Exception as e:
                logger.warning(f"[webosint] Error en worker: {e}")

    seen = set()
    unique = []
    for r in results:
        key = r.get("link")
        if key and key not in seen:
            seen.add(key)
            unique.append(r)

    return unique[:max_results]


# ============================================================
# 🧪 Test rápido
# ============================================================

if __name__ == "__main__":
    test = search_webosint("openai.com", "demo", max_results=10, use_cache=False)
    print(json.dumps(test, indent=2, ensure_ascii=False))
