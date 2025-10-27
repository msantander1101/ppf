"""
Módulo: pastes.py
-------------------------------------
Busca filtraciones, leaks o textos en servicios tipo Pastebin, Ghostbin, Hastebin, etc.
Integra fuentes públicas mediante SerpAPI o Google CSE si hay claves configuradas.
Evita bucles circulares con buscadores.py usando import diferido.
"""

import requests
from core.config import get_user_setting
from utils.logger import logger


# ==========================================================
# 🔹 Búsqueda principal
# ==========================================================
def search_pastes(query: str, username: str, max_results: int = 15) -> list:
    """
    Busca coincidencias del término en sitios de pasteo público (Pastebin, Ghostbin, Hastebin).
    Prioriza SerpAPI o Google API; si no hay claves, hace fallback a DuckDuckGo.
    """
    try:
        # 🔑 Intentar con SerpAPI primero
        serp_key = get_user_setting(username, "serpapi")
        if serp_key:
            logger.debug(f"[pastes] Usando SerpAPI para '{query}'")
            return _search_pastes_serpapi(query, serp_key, max_results)

        # 🔑 Si no hay SerpAPI, intentar Google Custom Search
        google_key = get_user_setting(username, "google_api_key")
        google_cx = get_user_setting(username, "google_cse_cx")
        if google_key and google_cx:
            logger.debug(f"[pastes] Usando Google CSE para '{query}'")
            return _search_pastes_google(query, google_key, google_cx, max_results)

        # 🦆 Fallback DuckDuckGo (sin API)
        logger.debug(f"[pastes] Usando fallback DuckDuckGo para '{query}'")
        return _search_pastes_duckduckgo(query, max_results)

    except Exception as e:
        logger.exception(f"[pastes] Error general: {e}")
        return []


# ==========================================================
# 🔹 SERPAPI
# ==========================================================
def _search_pastes_serpapi(query: str, serp_key: str, max_results: int) -> list:
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google",
        "q": f'"{query}" site:pastebin.com OR site:ghostbin.com OR site:hastebin.com',
        "num": max_results,
        "api_key": serp_key
    }
    try:
        r = requests.get(url, params=params, timeout=20)
        if r.status_code != 200:
            logger.warning(f"[pastes-serpapi] Código {r.status_code}: {r.text[:100]}")
            return []

        organic = r.json().get("organic_results", [])
        return [
            {
                "title": i.get("title"),
                "link": i.get("link"),
                "snippet": i.get("snippet"),
                "source": "pastes-serpapi"
            } for i in organic
        ]

    except Exception as e:
        logger.exception(f"[pastes-serpapi] Error ejecutando búsqueda: {e}")
        return []


# ==========================================================
# 🔹 Google Custom Search
# ==========================================================
def _search_pastes_google(query: str, google_key: str, google_cx: str, max_results: int) -> list:
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "q": f'"{query}" site:pastebin.com OR site:ghostbin.com OR site:hastebin.com',
        "key": google_key,
        "cx": google_cx,
        "num": min(max_results, 10)
    }
    try:
        r = requests.get(url, params=params, timeout=20)
        if r.status_code != 200:
            logger.warning(f"[pastes-google] Código {r.status_code}: {r.text[:100]}")
            return []

        items = r.json().get("items", [])
        return [
            {
                "title": i.get("title"),
                "link": i.get("link"),
                "snippet": i.get("snippet"),
                "source": "pastes-google"
            } for i in items
        ]

    except Exception as e:
        logger.exception(f"[pastes-google] Error: {e}")
        return []


# ==========================================================
# 🔹 DuckDuckGo fallback (sin API)
# ==========================================================
def _search_pastes_duckduckgo(query: str, max_results: int = 10) -> list:
    url = "https://api.duckduckgo.com/"
    params = {
        "q": f'"{query}" site:pastebin.com OR site:ghostbin.com OR site:hastebin.com',
        "format": "json",
        "no_redirect": 1,
        "no_html": 1
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            logger.warning(f"[pastes-duckduckgo] Código {r.status_code}")
            return []

        data = r.json()
        results = []
        for topic in data.get("RelatedTopics", []):
            if "Text" in topic and "FirstURL" in topic:
                results.append({
                    "title": topic["Text"],
                    "link": topic["FirstURL"],
                    "snippet": topic.get("Result", ""),
                    "source": "pastes-duckduckgo"
                })
        return results[:max_results]

    except Exception as e:
        logger.warning(f"[pastes-duckduckgo] Error: {e}")
        return []
