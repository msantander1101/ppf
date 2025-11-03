# modules/search/people_search.py
"""
PEOPLE SEARCH — Módulo OSINT para búsqueda de personas, usernames y reconocimiento facial.
Fuentes integradas:
    • Misc: SocialFinder, RoboFinder, SearchPeopleFree
    • Username Search: UserSearch.org, InstantUsername, DetectDee, Rhino Profile User Checker,
      DigitalFootprintCheck, Maigret OSINT Bot, cupidcr4wl, User-Searcher, AnalyzeID, HandleHawk
    • Face Recognition: VK.watch, FaceOnLive, Faceagle, ProfileImageIntel
    • Namint: Namint

Características:
    - Caché SQLite centralizada (data/cache/osint_cache.db)
    - Soporte Tor / proxy
    - Búsqueda por nombre, username o imagen
    - Extracción estructurada de datos cuando sea posible
    - Normalización de resultados compatible con grafo e IA
"""

import os
import re
import json
import time
import hashlib
import sqlite3
import threading
import mimetypes
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import requests
from PIL import Image
import imagehash

from core.config import get_user_setting
from utils.logger import logger


# ============================================================
# ⚙️ Configuración base
# ============================================================

CACHE_PATH = os.path.join("data", "cache")
DB_PATH = os.path.join(CACHE_PATH, "osint_cache.db")
os.makedirs(CACHE_PATH, exist_ok=True)

DEFAULT_TTL = 12 * 60 * 60  # 12 horas
DEFAULT_WORKERS = 5
DEFAULT_TIMEOUT = (10, 25)

_db_lock = threading.Lock()


# ============================================================
# 🧱 Utilidades de caché global
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
        return json.loads(payload)


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
# 🌐 HTTP Session (Tor/proxy)
# ============================================================

def _build_session(username: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0 Safari/537.36",
    })
    proxy = get_user_setting(username, "proxy")
    if proxy:
        s.proxies.update({"http": proxy, "https": proxy})
    else:
        s.proxies.update({"http": "socks5h://127.0.0.1:9050", "https": "socks5h://127.0.0.1:9050"})
    return s


# ============================================================
# 🔍 Fuentes
# ============================================================

def _misc_sources(q: str) -> List[tuple]:
    return [
        ("SocialFinder", f"https://socialfinder.io/?q={q}"),
        ("RoboFinder", f"https://robofinder.io/search?q={q}"),
        ("SearchPeopleFree", f"https://www.searchpeoplefree.com/find/{q.replace(' ', '-')}")
    ]


def _username_sources(q: str) -> List[tuple]:
    username = q.replace("@", "")
    return [
        ("UserSearch.org", f"https://usersearch.org/results/?q={username}"),
        ("InstantUsername", f"https://instantusername.com/#/{username}"),
        ("DetectDee", f"https://detectdee.com/search/{username}"),
        ("Rhino Profile Checker", f"https://rhinosearch.io/{username}"),
        ("DigitalFootprintCheck", f"https://digitalfootprintcheck.com/?user={username}"),
        ("Maigret OSINT Bot", f"https://github.com/soxoj/maigret?q={username}"),
        ("Cupidcr4wl", f"https://cupidcr4wl.io/search?q={username}"),
        ("User-Searcher", f"https://usersearcher.io/?q={username}"),
        ("AnalyzeID", f"https://analyzeid.com/search/{username}"),
        ("HandleHawk", f"https://handlehawk.com/?handle={username}")
    ]


def _face_sources(q: str) -> List[tuple]:
    # Si q es ruta local o URL de imagen
    return [
        ("VK.watch", "https://vk.watch/"),
        ("FaceOnLive", "https://faceonlive.com/search"),
        ("Faceagle", "https://faceagle.ai/"),
        ("ProfileImageIntel", "https://profileimageintel.com/"),
    ]


def _namint_sources(q: str) -> List[tuple]:
    return [
        ("Namint", f"https://namint.com/search?name={q.replace(' ', '+')}"),
    ]


# ============================================================
# 🧠 Hash de imagen y helpers
# ============================================================

def _phash_image(img_path: str) -> Optional[str]:
    try:
        img = Image.open(img_path)
        return str(imagehash.phash(img))
    except Exception:
        return None


def _is_image(q: str) -> bool:
    return os.path.isfile(q) and mimetypes.guess_type(q)[0] and "image" in mimetypes.guess_type(q)[0]


# ============================================================
# ⚙️ Worker de recolección
# ============================================================

def _collect_from_sources(username: str, group: str, sources: List[tuple], q: str, use_cache=True) -> List[Dict[str, Any]]:
    if use_cache:
        cached = _cache_get(group, q, username)
        if cached:
            for r in cached:
                r["_cached"] = True
            return cached

    s = _build_session(username)
    results = []
    for name, url in sources:
        results.append({
            "platform": group.capitalize(),
            "source": name,
            "title": f"Búsqueda en {name} para {q}",
            "link": url,
            "snippet": "Abrir para revisar coincidencias.",
            "structured": {},
            "_cached": False
        })
    _cache_set(group, q, username, results)
    return results


# ============================================================
# 🧩 Router principal
# ============================================================

def search_people(query: str, username: str, max_results: int = 20, use_cache=True) -> List[Dict[str, Any]]:
    """
    Detección automática de tipo:
        - @username → username_sources
        - Nombre y apellido → misc + namint
        - Imagen (ruta/URL) → face_sources
    """
    results = []
    group_tasks = []

    # Detectar tipo
    if _is_image(query) or re.match(r"^https?://.*\.(jpg|png|jpeg|gif)$", query):
        groups = ["face"]
    elif re.match(r"^@?\w{3,}$", query):
        groups = ["username"]
    else:
        groups = ["misc", "namint"]

    mapping = {
        "misc": _misc_sources,
        "username": _username_sources,
        "face": _face_sources,
        "namint": _namint_sources,
    }

    workers = DEFAULT_WORKERS
    try:
        cfg_workers = get_user_setting(username, "concurrency")
        if cfg_workers:
            workers = int(cfg_workers)
    except Exception:
        pass

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for g in groups:
            fn = mapping[g]
            sources = fn(query)
            group_tasks.append(ex.submit(_collect_from_sources, username, g, sources, query, use_cache))

        for fut in as_completed(group_tasks):
            try:
                chunk = fut.result()
                results.extend(chunk)
            except Exception as e:
                logger.warning(f"[people_search] Error: {e}")

    # Limitar
    return results[:max_results]
