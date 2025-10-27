"""
Módulo: social.py
-------------------------------------
Búsqueda de huellas en redes sociales, foros y comunidades online.
Usa SerpAPI o scraping ligero con dorks adaptados.
Compatible con buscadores.py y person_ui (modo "social").
"""

import re
import requests
from core.config import get_user_setting
from utils.logger import logger


# ==========================================================
# Plataformas soportadas
# ==========================================================
SOCIAL_PLATFORMS = {
    "twitter": "site:twitter.com",
    "linkedin": "site:linkedin.com/in OR site:linkedin.com/pub",
    "facebook": "site:facebook.com",
    "instagram": "site:instagram.com",
    "github": "site:github.com",
    "tiktok": "site:tiktok.com",
    "reddit": "site:reddit.com/user",
    "telegram": "site:t.me OR site:telegram.me",
    "medium": "site:medium.com",
}


# ==========================================================
# 🔹 Búsqueda principal
# ==========================================================
def search_social(query: str, username: str, max_results: int = 15) -> list:
    """
    Busca presencia en redes sociales de una persona, alias o correo.
    Combina SerpAPI, Google API o fallback scraping.
    """
    serp_key = get_user_setting(username, "serpapi")
    google_key = get_user_setting(username, "google_api_key")
    google_cx = get_user_setting(username, "google_cse_cx")

    dork = _build_social_dork(query)

    try:
        if serp_key:
            return _search_serpapi_social(dork, serp_key, max_results)
        elif google_key and google_cx:
            return _search_google_social(dork, google_key, google_cx, max_results)
        else:
            return _search_scrape_social(dork, max_results)
    except Exception as e:
        logger.exception(f"[social] Error general: {e}")
        return []


# ==========================================================
# 🔹 Dork builder
# ==========================================================
def _build_social_dork(query: str) -> str:
    """
    Construye un dork OSINT para redes sociales según el patrón de búsqueda.
    """
    terms = []
    q = query.strip().replace('"', '')

    if "@" in q:
        # correo: buscar menciones y perfiles vinculados
        terms.append(f'"{q}" (twitter OR linkedin OR facebook OR instagram)')
    elif re.match(r"^[A-Za-z0-9_.-]{3,}$", q):
        # alias probable
        terms.append(f'"{q}" site:twitter.com OR site:instagram.com OR site:github.com')
    else:
        # nombre completo
        terms.append(f'"{q}" site:linkedin.com OR site:facebook.com OR site:twitter.com')

    dork = " OR ".join(terms)
    return dork


# ==========================================================
# 🔹 SerpAPI
# ==========================================================
def _search_serpapi_social(query: str, api_key: str, max_results: int = 15) -> list:
    url = "https://serpapi.com/search.json"
    params = {"engine": "google", "q": query, "num": max_results, "api_key": api_key}

    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            logger.warning(f"[social:serpapi] Código {r.status_code}: {r.text[:100]}")
            return []
        data = r.json()
        organic = data.get("organic_results", [])
        results = []
        for item in organic:
            title = item.get("title", "")
            link = item.get("link", "")
            source = _detect_social_source(link)
            results.append({
                "title": title,
                "link": link,
                "snippet": item.get("snippet", ""),
                "source": source or "serpapi"
            })
        return results
    except Exception as e:
        logger.exception(f"[social:serpapi] Error: {e}")
        return []


# ==========================================================
# 🔹 Google API (Custom Search)
# ==========================================================
def _search_google_social(query: str, key: str, cx: str, max_results: int = 10) -> list:
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"q": query, "key": key, "cx": cx, "num": min(max_results, 10)}

    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            logger.warning(f"[social:google] Código {r.status_code}: {r.text[:100]}")
            return []

        data = r.json()
        items = data.get("items", [])
        results = []
        for i in items:
            link = i.get("link", "")
            source = _detect_social_source(link)
            results.append({
                "title": i.get("title"),
                "link": link,
                "snippet": i.get("snippet", ""),
                "source": source or "google"
            })
        return results
    except Exception as e:
        logger.exception(f"[social:google] Error: {e}")
        return []


# ==========================================================
# 🔹 Fallback scraping
# ==========================================================
def _search_scrape_social(query: str, max_results: int = 10) -> list:
    """
    Búsqueda simple vía DuckDuckGo HTML sin API.
    """
    url = "https://html.duckduckgo.com/html/"
    params = {"q": query}
    headers = {"User-Agent": "Mozilla/5.0 (compatible; OSINTSuite/1.0)"}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        if r.status_code != 200:
            return []

        links = re.findall(r'href="(https?://[^"]+)"', r.text)
        social_links = [l for l in links if _detect_social_source(l)]

        results = []
        for i, link in enumerate(social_links[:max_results]):
            source = _detect_social_source(link)
            results.append({
                "title": f"Perfil {i+1}",
                "link": link,
                "snippet": "",
                "source": source or "scraper"
            })
        return results
    except Exception as e:
        logger.exception(f"[social:scrape] Error: {e}")
        return []


# ==========================================================
# 🔹 Detección de plataforma según enlace
# ==========================================================
def _detect_social_source(link: str) -> str:
    for name, pattern in SOCIAL_PLATFORMS.items():
        if any(p in link for p in pattern.split(" OR ")):
            return name
    return "social"


# ==========================================================
# 🔹 Normalización avanzada
# ==========================================================
def normalize_social_results(results: list) -> list:
    """
    Agrupa y limpia resultados duplicados, mejorando la legibilidad.
    """
    seen = set()
    normalized = []
    for r in results:
        link = r.get("link")
        if not link or link in seen:
            continue
        seen.add(link)
        normalized.append({
            "title": r.get("title", "Perfil encontrado"),
            "link": link,
            "snippet": r.get("snippet", ""),
            "source": r.get("source", "social")
        })
    return normalized
