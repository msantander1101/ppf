# modules/search/phoneint.py
"""
PHONEINT — Phone number intelligence & enumeration
=================================================

Fuentes incluidas (plantillas / endpoints):
    - WhoCallD.com
    - NumLookup
    - TrueCaller (via web UI / fallback)
    - QuiénLlama (quienllama.com)  <- España
    - PáginasAmarillas (paginasamarillas.es)  <- España
    - Infobel (infobel.com)  <- internacional con datos locales
    - 11870 (11870.com)  <- España
    - HolaTel (holatel.com)  <- España (plantilla)
    - OpenCNAM / freecarrierlookup (cuando haya API)
    - Otros (placeholder para añadir scrapers locales/regionales)

Características:
    - Cache SQLite (data/cache/osint_cache.db)
    - Proxy / Tor configurable (lee core.config.get_user_setting(username, "proxy"))
    - Concurrency configurable (user setting "concurrency")
    - Resultados normalizados: phone, normalized_phone, country, carrier, source, link, snippet, structured
    - Preparado para integrarse con grafo / IA / UI
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

from core.config import get_user_setting
from utils.logger import logger

# ---------------------------------------------------------------------
# Config / caché (misma base que otros módulos para coherencia)
# ---------------------------------------------------------------------
CACHE_DIR = os.path.join("data", "cache")
DB_PATH = os.path.join(CACHE_DIR, "osint_cache.db")
os.makedirs(CACHE_DIR, exist_ok=True)

_DEFAULT_TTL = 60 * 60 * 24  # 24h por defecto
_DEFAULT_WORKERS = 4
_DEFAULT_TIMEOUT = (8, 25)

_db_lock = threading.Lock()


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


def _cache_get(group: str, q: str, username: str, ttl: int = _DEFAULT_TTL):
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


# ---------------------------------------------------------------------
# HTTP session (proxy / tor)
# ---------------------------------------------------------------------
def _build_session(username: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; OSINT-Suite/PhoneINT/1.0; +https://example.org)",
        "Accept": "application/json,text/html;q=0.9,*/*;q=0.8"
    })

    try:
        proxy = get_user_setting(username, "proxy")
    except Exception:
        proxy = None

    # Si el usuario ha configurado proxy, usarlo; si no, intentar Tor por defecto (socks5h)
    if proxy:
        s.proxies.update({"http": proxy, "https": proxy})
    else:
        # intenta usar Tor (si el usuario lo tiene levantado)
        s.proxies.update({"http": "socks5h://127.0.0.1:9050", "https": "socks5h://127.0.0.1:9050"})

    s.timeout = _DEFAULT_TIMEOUT
    return s


# ---------------------------------------------------------------------
# Fuentes (plantillas de consulta / URL)
# ---------------------------------------------------------------------
def _phoneint_sources(phone: str) -> List[Dict[str, str]]:
    p_enc = requests.utils.requote_uri(phone)
    # Plantillas: al implementar cada scraper deberás mapear la ruta real / parámetros
    return [
        {"name": "WhoCallD", "url": f"https://whocalld.com/search?q={p_enc}"},
        {"name": "NumLookup", "url": f"https://www.numlookupapi.com/lookup?number={p_enc}"},
        {"name": "TrueCaller", "url": f"https://www.truecaller.com/search?query={p_enc}"},
        # Fuentes España
        {"name": "QuienLlama", "url": f"https://www.quienllama.com/buscar/{p_enc}"},
        {"name": "PaginasAmarillas", "url": f"https://www.paginasamarillas.es/buscar/{p_enc}"},
        {"name": "Infobel", "url": f"https://www.infobel.com/en/world/search/{p_enc}"},
        {"name": "11870", "url": f"https://www.11870.com/telefono/{p_enc}"},
        {"name": "HolaTel", "url": f"https://holatel.example/search?phone={p_enc}"},
        # verificación / carrier / CNAM
        {"name": "OpenCNAM", "url": f"https://api.opencnam.com/v3/phone/{p_enc}"},
        {"name": "FreeCarrierLookup", "url": f"https://freecarrierlookup.example/lookup?number={p_enc}"},
    ]


# ---------------------------------------------------------------------
# Normalización simple
# ---------------------------------------------------------------------
def _normalize(source: str, phone: str, url: str, category: str = "phoneint") -> Dict[str, Any]:
    return {
        "source": source,
        "title": f"{source} — resultados PhoneINT para {phone}",
        "link": url,
        "snippet": "Abrir para ver detalles (nombre, operador, localización si existiera).",
        "phone": phone,
        "normalized_phone": _normalize_phone(phone),
        "country": _guess_country_from_phone(phone),
        "carrier": None,
        "structured": {},
        "category": category,
        "fetched_at": datetime.utcnow().isoformat(),
        "_cached": False,
    }


def _normalize_phone(phone: str) -> str:
    # limpieza básica: dejar solo dígitos y prefijo +
    s = "".join(ch for ch in phone if ch.isdigit() or ch == "+")
    if s.startswith("00"):
        s = "+" + s[2:]
    if not s.startswith("+") and len(s) >= 9:
        # sin prefijo, no podemos adivinar con exactitud; devolver sin cambiar
        return s
    return s


def _guess_country_from_phone(phone: str) -> Optional[str]:
    # heurística básica por prefijo
    p = "".join(ch for ch in phone if ch.isdigit() or ch == "+")
    if p.startswith("+34") or p.startswith("0034"):
        return "ES"
    if p.startswith("+44") or p.startswith("0044"):
        return "UK"
    if p.startswith("+1") or p.startswith("001"):
        return "US"
    return None


# ---------------------------------------------------------------------
# Collector (sin scraping pesado; devuelve entradas normalizadas con URL)
# ---------------------------------------------------------------------
def _collect(username: str, group: str, sources: List[Dict[str, str]], q: str, use_cache: bool = True) -> List[Dict[str, Any]]:
    if use_cache:
        cached = _cache_get(group, q, username)
        if cached:
            return cached

    session = _build_session(username)
    results: List[Dict[str, Any]] = []

    for s in sources:
        try:
            rec = _normalize(s["name"], q, s["url"], category=group)
            # Intentamos una petición ligera HEAD/GET para comprobar estado (no parseamos aquí)
            try:
                r = session.head(s["url"], allow_redirects=True)
                rec["status_code"] = r.status_code
            except Exception:
                rec["status_code"] = None
            results.append(rec)
        except Exception as e:
            logger.warning(f"[phoneint] Error al normalizar fuente {s}: {e}")

    # Guardar en caché
    try:
        _cache_set(group, q, username, results)
    except Exception as e:
        logger.warning(f"[phoneint] No se pudo guardar cache: {e}")

    return results


# ---------------------------------------------------------------------
# API público
# ---------------------------------------------------------------------
def search_phoneint(query: str, username: str, max_results: int = 25, use_cache: bool = True) -> List[Dict[str, Any]]:
    """
    Ejecuta enumeración / intelligence sobre un número de teléfono.
    - query: número en cualquier formato (string)
    - username: usuario que solicita (para usar proxy / claves / caché separada)
    """
    group = "phoneint"
    sources = _phoneint_sources(query)

    # workers configurable por user setting "concurrency"
    workers = _DEFAULT_WORKERS
    try:
        cfg = get_user_setting(username, "concurrency")
        if cfg:
            workers = int(cfg)
    except Exception:
        pass

    results: List[Dict[str, Any]] = []
    # Para phoneint el trabajo es ligero: pedir metadata / urls -> suficiente para UI
    # Si quieres scrapers profundos, cada source debe implementarse como extractor específico.
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futures = [ex.submit(_collect, username, group, sources, query, use_cache)]
        for f in as_completed(futures):
            try:
                results.extend(f.result())
            except Exception as e:
                logger.warning(f"[phoneint] Error en worker: {e}")

    # Unificar por link
    seen = set()
    uniq = []
    for r in results:
        key = r.get("link") or r.get("title")
        if key not in seen:
            seen.add(key)
            uniq.append(r)

    return uniq[:max_results]


# ---------------------------------------------------------------------
# Si se ejecuta en local (prueba rápida)
# ---------------------------------------------------------------------
if __name__ == "__main__":
    out = search_phoneint("+34123456789", "demo", max_results=10, use_cache=False)
    print(json.dumps(out, indent=2, ensure_ascii=False))
