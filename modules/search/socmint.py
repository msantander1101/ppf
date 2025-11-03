# modules/search/socmint.py
"""
SOCMINT — Social Media Intelligence
===================================
Módulo OSINT para búsquedas, monitoreo y análisis en redes sociales.

Fuentes integradas:
    Misc:
        Snapchat Username Checker, Sockpuppet.io, Disboard, Spoonbill.io,
        Badoo Wayback, DuolingOSINT, SocialBlade, ExportComments
    Discord:
        Doxcord
    YouTube:
        youtube_data_extractor, MW Geofind, YouTube Video Finder, ChannelCrawler,
        ReelTime AI, YouTube History Analyze, youtube-tools-comments,
        YouTube Comment Finder, Youtube Subscription History, youtube-handles-fuzz,
        OsintTube, Filmot
    TikTok:
        TikSpyder, TokInsights, Urlebird.com, TikFace, WatchWithout,
        OMAR-Thing tiktok tool, Sticktock
    Mastodon:
        Big Mastodon Hashtag Search
    Facebook:
        Social Media Index, Facebook Catalogue, Meta_Scan, Have I Been Zuckered?
    Twitter / X:
        WaybackTweets, Sotwe.com, tweetfeed, TwStalker,
        Twitter Trending Archive
    Instagram:
        DolphinRadar Instagram Viewer, InstagramPrivSniffer,
        InDownloader Instagram Profile Viewer, Instagram Monitor,
        Dumpor.io, InsTrack.app, InstaClip, Stalkiana, greatfon instagram viewer,
        InstaTracker, ExportGram, Instagram Network Analysis Tool
    LinkedIn:
        LinkedInDumper, CrossLinked, LinkedIn Profile Viewer, LinkdTime
    Reddit:
        Vapor, RedditOSINT, SnooSnoop, Reveddit, redditmetis
    GEO Tracking:
        HuntIntel

Características:
    - Cache SQLite
    - Rotación automática Tor/Proxy
    - Resultados normalizados
    - Soporte multi-fuente concurrente
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

DEFAULT_TTL = 60 * 60 * 24  # 24h
DEFAULT_WORKERS = 6
DEFAULT_TIMEOUT = (10, 25)

_db_lock = threading.Lock()


# ============================================================
# 💾 Cache (SQLite)
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
# 🌐 HTTP session (Tor/Proxy)
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

def _socmint_sources(q: str) -> List[Dict[str, str]]:
    q_enc = requests.utils.requote_uri(q)
    srcs = [
        # --- Misc ---
        ("Snapchat Username Checker", f"https://snapcheck.example/?user={q_enc}"),
        ("Sockpuppet.io", f"https://sockpuppet.io/search?q={q_enc}"),
        ("Disboard", f"https://disboard.org/search?q={q_enc}"),
        ("Spoonbill.io", f"https://spoonbill.io/search?q={q_enc}"),
        ("Badoo Wayback", f"https://badoo.example/wayback?q={q_enc}"),
        ("DuolingOSINT", f"https://duoling.example/search?q={q_enc}"),
        ("SocialBlade", f"https://socialblade.com/search/{q_enc}"),
        ("ExportComments", f"https://exportcomments.com/search?q={q_enc}"),

        # --- Discord ---
        ("Doxcord", f"https://doxcord.example/search?q={q_enc}"),

        # --- YouTube ---
        ("YouTube Data Extractor", f"https://ytdx.example/search?q={q_enc}"),
        ("MW Geofind", f"https://mwgeofind.example/search?q={q_enc}"),
        ("YouTube Video Finder", f"https://ytvideofinder.example/search?q={q_enc}"),
        ("ChannelCrawler", f"https://channelcrawler.com/?q={q_enc}"),
        ("ReelTime AI", f"https://reeltime.example/search?q={q_enc}"),
        ("YouTube History Analyze", f"https://ythistory.example/search?q={q_enc}"),
        ("youtube-tools-comments", f"https://ytcomments.example/search?q={q_enc}"),
        ("YouTube Comment Finder", f"https://ytcommentfinder.example/search?q={q_enc}"),
        ("Youtube Subscription History", f"https://ytsubhistory.example/search?q={q_enc}"),
        ("youtube-handles-fuzz", f"https://ythandles.example/search?q={q_enc}"),
        ("OsintTube", f"https://osinttube.example/search?q={q_enc}"),
        ("Filmot", f"https://filmot.com/search?q={q_enc}"),

        # --- TikTok ---
        ("TikSpyder", f"https://tikspyder.example/search?q={q_enc}"),
        ("TokInsights", f"https://tokinsights.example/search?q={q_enc}"),
        ("Urlebird.com", f"https://urlebird.com/search/{q_enc}/"),
        ("TikFace", f"https://tikface.io/search?q={q_enc}"),
        ("WatchWithout", f"https://watchwithout.com/search?q={q_enc}"),
        ("OMAR-Thing TikTok Tool", f"https://omarthing.example/search?q={q_enc}"),
        ("Sticktock", f"https://sticktock.example/search?q={q_enc}"),

        # --- Mastodon ---
        ("Big Mastodon Hashtag Search", f"https://mastodonhashtag.example/search?q={q_enc}"),

        # --- Facebook ---
        ("Social Media Index", f"https://socialmediaindex.example/search?q={q_enc}"),
        ("Facebook Catalogue", f"https://fbcat.example/search?q={q_enc}"),
        ("Meta_Scan", f"https://metascan.example/search?q={q_enc}"),
        ("Have I Been Zuckered?", f"https://zuckered.example/search?q={q_enc}"),

        # --- Twitter / X ---
        ("WaybackTweets", f"https://waybacktweets.example/search?q={q_enc}"),
        ("Sotwe.com", f"https://sotwe.com/search?q={q_enc}"),
        ("tweetfeed", f"https://tweetfeed.example/search?q={q_enc}"),
        ("TwStalker", f"https://twstalker.io/search?q={q_enc}"),
        ("Twitter Trending Archive", f"https://trendarchive.example/search?q={q_enc}"),

        # --- Instagram ---
        ("DolphinRadar Instagram Viewer", f"https://dolphinradar.com/search?q={q_enc}"),
        ("InstagramPrivSniffer", f"https://privsniffer.example/search?q={q_enc}"),
        ("InDownloader", f"https://indownloader.com/search?q={q_enc}"),
        ("Instagram Monitor", f"https://instamonitor.example/search?q={q_enc}"),
        ("Dumpor.io", f"https://dumpor.io/search?q={q_enc}"),
        ("InsTrack.app", f"https://insttrack.app/search?q={q_enc}"),
        ("InstaClip", f"https://instaclip.example/search?q={q_enc}"),
        ("Stalkiana", f"https://stalkiana.com/search?q={q_enc}"),
        ("greatfon", f"https://greatfon.com/search?q={q_enc}"),
        ("InstaTracker", f"https://instatracker.example/search?q={q_enc}"),
        ("ExportGram", f"https://exportgram.example/search?q={q_enc}"),
        ("Instagram Network Analysis Tool", f"https://instanetana.example/search?q={q_enc}"),

        # --- LinkedIn ---
        ("LinkedInDumper", f"https://linkedindumper.example/search?q={q_enc}"),
        ("CrossLinked", f"https://crosslinked.example/search?q={q_enc}"),
        ("LinkedIn Profile Viewer", f"https://linkedinprofile.example/search?q={q_enc}"),
        ("LinkdTime", f"https://linkdtime.example/search?q={q_enc}"),

        # --- Reddit ---
        ("Vapor", f"https://vapor.example/search?q={q_enc}"),
        ("RedditOSINT", f"https://reddit-osint.example/search?q={q_enc}"),
        ("SnooSnoop", f"https://snoosnoop.example/search?q={q_enc}"),
        ("Reveddit", f"https://reveddit.com/search?q={q_enc}"),
        ("redditmetis", f"https://redditmetis.example/search?q={q_enc}"),

        # --- GEO Tracking ---
        ("HuntIntel", f"https://huntintel.example/search?q={q_enc}")
    ]
    return [{"name": n, "url": u} for n, u in srcs]


# ============================================================
# 🧠 Normalización
# ============================================================

def _normalize(source: str, q: str, url: str, category="socmint") -> Dict[str, Any]:
    return {
        "source": source,
        "title": f"{source} — resultados SOCMINT para {q}",
        "link": url,
        "snippet": "Abrir para revisar perfiles, comentarios o actividad en redes sociales.",
        "query": q,
        "category": category,
        "structured": {},
        "_cached": False,
        "fetched_at": datetime.utcnow().isoformat(),
    }


# ============================================================
# 🧩 Colector concurrente
# ============================================================

def _collect(username: str, group: str, sources: List[Dict[str, str]], q: str, use_cache=True) -> List[Dict[str, Any]]:
    if use_cache:
        cached = _cache_get(group, q, username)
        if cached:
            return cached

    session = _build_session(username)
    results = []
    for s in sources:
        try:
            rec = _normalize(s["name"], q, s["url"], category=group)
            results.append(rec)
        except Exception as e:
            logger.warning(f"[socmint] Error normalizando {s}: {e}")

    _cache_set(group, q, username, results)
    return results


# ============================================================
# 🚀 Módulo principal
# ============================================================

def search_socmint(query: str, username: str, max_results: int = 50, use_cache: bool = True) -> List[Dict[str, Any]]:
    group = "socmint"
    sources = _socmint_sources(query)

    workers = DEFAULT_WORKERS
    try:
        c = get_user_setting(username, "concurrency")
        if c:
            workers = int(c)
    except Exception:
        pass

    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_collect, username, group, sources, query, use_cache)]
        for f in as_completed(futures):
            try:
                results.extend(f.result())
            except Exception as e:
                logger.warning(f"[socmint] Error en worker: {e}")

    seen = set()
    unique = []
    for r in results:
        link = r.get("link")
        if link not in seen:
            seen.add(link)
            unique.append(r)

    return unique[:max_results]


# ============================================================
# 🧪 Test rápido
# ============================================================

if __name__ == "__main__":
    data = search_socmint("john_doe", "demo", max_results=10, use_cache=False)
    print(json.dumps(data, indent=2, ensure_ascii=False))
