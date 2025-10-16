# modules/search/google_dork.py
"""
Módulo de búsqueda DORK:
- Usa SerpApi si se pasa api_key o si existe en env
- Fallback a Bing scraping (requests + BeautifulSoup)
- Exporta la función `search_dork(query, max_results=10, engine='auto', api_key=None, use_proxies=None)`
"""

import os
import time
import re
from typing import List, Dict, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from utils.logger import logger

# Regex para correos
EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


def _headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }


def _extract_domain(url: str) -> str:
    try:
        p = urlparse(url)
        return p.netloc.lower()
    except Exception:
        return url or ""


def _extract_emails(text: str) -> List[str]:
    if not text:
        return []
    return list(set(EMAIL_RE.findall(text)))


# ---------- SerpApi ----------
def _search_serpapi(query: str, num: int = 10, api_key: Optional[str] = None) -> List[Dict]:
    key = api_key or os.environ.get("SERPAPI_API_KEY")
    if not key:
        raise RuntimeError("SERPAPI API key no disponible")
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google",
        "q": query,
        "num": num,
        "api_key": key,
    }
    logger.debug(f"[google_dork] SerpApi query: {query}")
    r = requests.get(url, params=params, headers=_headers(), timeout=20)
    r.raise_for_status()
    data = r.json()
    results = []
    for item in data.get("organic_results", [])[:num]:
        title = item.get("title")
        link = item.get("link") or item.get("position")
        snippet = item.get("snippet") or ""
        emails = _extract_emails(" ".join([title or "", snippet or "", str(item)]))
        results.append({
            "title": title,
            "link": link,
            "snippet": snippet,
            "domain": _extract_domain(link or ""),
            "emails": emails,
            "source": "serpapi"
        })
    return results


# ---------- Bing fallback (scraping) ----------
def _search_bing(query: str, num: int = 10, pause: float = 1.0, session: Optional[requests.Session] = None) -> List[Dict]:
    logger.debug(f"[google_dork] Bing fallback query: {query}")
    results: List[Dict] = []
    url = "https://www.bing.com/search"
    params = {"q": query, "count": num}
    s = session or requests.Session()
    s.headers.update(_headers())
    r = s.get(url, params=params, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("li.b_algo")[:num]
    for it in items:
        try:
            h2 = it.find("h2")
            a = h2.find("a") if h2 else None
            title = a.get_text(strip=True) if a else (h2.get_text(strip=True) if h2 else "")
            link = a["href"] if a and a.has_attr("href") else ""
            snippet_tag = it.find("p")
            snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
            emails = _extract_emails(" ".join([title or "", snippet or ""]))
            results.append({
                "title": title,
                "link": link,
                "snippet": snippet,
                "domain": _extract_domain(link or ""),
                "emails": emails,
                "source": "bing"
            })
        except Exception:
            logger.debug("[google_dork] Error parsing a Bing result item", exc_info=True)
    time.sleep(pause)
    return results


# ---------- Public function ----------
def search_dork(query: str, max_results: int = 10, engine: str = "auto",
                api_key: Optional[str] = None, use_proxies: Optional[dict] = None) -> List[Dict]:
    """
    Ejecuta una búsqueda dork y devuelve lista de resultados:
    [{title, link, snippet, domain, emails, source}, ...]
    - engine: 'auto' (serpapi if key else bing), 'serpapi' or 'bing'
    - api_key: si se pasa, se usa para SerpApi
    - use_proxies: dict para requests ({"http": "...", "https": "..."})
    """
    if not query or not query.strip():
        return []

    # determinar motor
    if engine == "auto":
        engine = "serpapi" if (api_key or os.environ.get("SERPAPI_API_KEY")) else "bing"

    session = requests.Session()
    session.headers.update(_headers())
    if use_proxies:
        session.proxies.update(use_proxies)

    try:
        if engine == "serpapi":
            return _search_serpapi(query, num=max_results, api_key=api_key)
        elif engine == "bing":
            return _search_bing(query, num=max_results, session=session)
        else:
            raise ValueError("Engine desconocido, use 'serpapi' o 'bing'")
    except Exception as e:
        logger.exception(f"[google_dork] Error ejecutando search_dork (engine={engine}): {e}")
        # fallback: si intentamos serpapi y falla, intentar bing
        if engine == "serpapi":
            try:
                logger.info("[google_dork] SerpApi falló, intentando fallback a Bing")
                return _search_bing(query, num=max_results, session=session)
            except Exception as e2:
                logger.exception("[google_dork] Fallback a Bing también falló", exc_info=True)
                return []
        return []
