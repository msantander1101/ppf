# modules/search/imageint.py
"""
IMAGEINT — Módulo OSINT para análisis e inteligencia de imágenes.

Fuentes integradas:
    • Misc: AI Image Detector, FotoForensics, ExifTool-Web
    • Reverse Search: FaceSearch Arrests.org, Reversely.ai, faceseek online
    • Image Enhancement: Depix, Upscale Media

Características:
    - Caché SQLite centralizada (data/cache/osint_cache.db)
    - Soporte para Tor / proxy (core.config.get_user_setting)
    - Detección automática (imagen local, URL o texto)
    - Resultados estructurados para grafo e IA
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

def _misc_sources(q: str) -> List[Dict[str, str]]:
    return [
        {"name": "AI Image Detector", "url": f"https://huggingface.co/spaces/AIImageDetector?query={q}"},
        {"name": "FotoForensics", "url": f"https://fotoforensics.com/analysis.php?url={q}"},
        {"name": "ExifTool-Web", "url": f"https://exiftool.org/exiftool.html?image={q}"},
    ]


def _reverse_sources(q: str) -> List[Dict[str, str]]:
    return [
        {"name": "FaceSearch Arrests.org", "url": f"https://arrests.org/facesearch/?q={q}"},
        {"name": "Reversely.ai", "url": f"https://reversely.ai/search?query={q}"},
        {"name": "faceseek online", "url": f"https://faceseek.online/search?q={q}"},
    ]


def _enhancement_sources(q: str) -> List[Dict[str, str]]:
    return [
        {"name": "Depix", "url": f"https://depix.io/upload?image={q}"},
        {"name": "Upscale Media", "url": f"https://www.upscale.media/?image_url={q}"},
    ]


# ============================================================
# 🧠 Detección y normalización
# ============================================================

_URL_REGEX = re.compile(r"^https?://", re.IGNORECASE)
_IMG_EXT = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")

def _detect_query_type(q: str) -> str:
    if _URL_REGEX.match(q):
        return "url"
    if q.lower().endswith(_IMG_EXT):
        return "file"
    if re.match(r"^[a-f0-9]{32,64}$", q):
        return "hash"
    return "text"


def _normalize_record(source: str, q: str, url: str, group: str) -> Dict[str, Any]:
    return {
        "source": source,
        "title": f"{source} — análisis de imagen para {q}",
        "link": url,
        "snippet": "Abrir para revisar detalles, coincidencias o metadatos.",
        "query": q,
        "category": group,
        "structured": {},
        "_cached": False,
        "fetched_at": datetime.utcnow().isoformat(),
    }


# ============================================================
# 🕸️ Recolector
# ============================================================

def _collect_from_sources(username: str, group: str, sources: List[Dict[str, str]], q: str, use_cache=True) -> List[Dict[str, Any]]:
    if use_cache:
        cached = _cache_get(group, q, username)
        if cached:
            return cached

    _build_session(username)
    results = []
    for src in sources:
        try:
            rec = _normalize_record(src["name"], q, src["url"], group)
            results.append(rec)
        except Exception as e:
            logger.warning(f"[imageint] Error con fuente {src}: {e}")

    _cache_set(group, q, username, results)
    return results


# ============================================================
# 🚀 Módulo principal
# ============================================================

def search_imageint(query: str, username: str, max_results: int = 20, use_cache: bool = True) -> List[Dict[str, Any]]:
    """
    Ejecuta búsqueda OSINT sobre una imagen (URL, archivo, hash o descripción).
    """
    results: List[Dict[str, Any]] = []
    qtype = _detect_query_type(query)

    groups = []
    if qtype in ["url", "file"]:
        groups = ["misc", "reverse", "enhancement"]
    elif qtype == "hash":
        groups = ["reverse"]
    else:
        groups = ["misc", "reverse"]

    mapping = {
        "misc": _misc_sources,
        "reverse": _reverse_sources,
        "enhancement": _enhancement_sources,
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
                results.extend(fut.result())
            except Exception as e:
                logger.warning(f"[imageint] Error en tarea: {e}")

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
# 🧪 Test rápido
# ============================================================

if __name__ == "__main__":
    test = search_imageint("https://example.com/photo.jpg", "demo", max_results=10, use_cache=False)
    print(json.dumps(test, indent=2, ensure_ascii=False))
