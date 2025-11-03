"""
Módulo de búsqueda OSINT — Buscadores y agregador central.
Soporta SerpAPI, Google Custom Search API, Bing y DuckDuckGo.
Incluye detección automática de tipo de consulta y fallback.
"""

import requests
import re
from core.config import get_user_setting
from utils.logger import logger

# -----------------------------------------------------------
# 🔎 Detección del tipo de búsqueda (para ajustar dorks)
# -----------------------------------------------------------
def detect_query_type(query: str) -> str:
    if re.match(r"[^@]+@[^@]+\.[^@]+", query):
        return "email"
    elif re.match(r"^\+?\d{7,15}$", query):
        return "phone"
    elif re.match(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", query):
        return "domain"
    else:
        return "person"


# -----------------------------------------------------------
# 🌐 Búsqueda con SerpAPI
# -----------------------------------------------------------
def search_serpapi(query: str, username: str, max_results: int = 10):
    api_key = get_user_setting(username, "serpapi")
    if not api_key:
        logger.warning("[search_serpapi] Falta API key de SerpAPI.")
        return []

    params = {
        "engine": "google",
        "q": query,
        "num": max_results,
        "api_key": api_key
    }

    try:
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=20)
        if r.status_code != 200:
            logger.warning(f"[SerpAPI] Código HTTP {r.status_code}")
            return []
        data = r.json()
        results = []
        for item in data.get("organic_results", []):
            results.append({
                "title": item.get("title"),
                "link": item.get("link"),
                "snippet": item.get("snippet"),
                "source": "SerpAPI"
            })
        return results
    except Exception as e:
        logger.error(f"[SerpAPI] Error: {e}")
        return []


# -----------------------------------------------------------
# 🔍 Búsqueda con Google Custom Search API (CSE)
# -----------------------------------------------------------
def search_google_cse(query: str, username: str, max_results: int = 10):
    api_key = get_user_setting(username, "google_api_key")
    cx = get_user_setting(username, "google_cse_cx")
    if not api_key or not cx:
        logger.warning("[search_google_cse] Faltan google_api_key o google_cse_cx.")
        return []

    url = "https://www.googleapis.com/customsearch/v1"
    params = {"key": api_key, "cx": cx, "q": query, "num": max_results}
    try:
        r = requests.get(url, params=params, timeout=20)
        if r.status_code != 200:
            logger.warning(f"[Google CSE] Código HTTP {r.status_code}")
            return []
        data = r.json()
        results = []
        for item in data.get("items", []):
            results.append({
                "title": item.get("title"),
                "link": item.get("link"),
                "snippet": item.get("snippet"),
                "source": "Google CSE"
            })
        return results
    except Exception as e:
        logger.error(f"[Google CSE] Error: {e}")
        return []


# -----------------------------------------------------------
# 🦆 DuckDuckGo (sin clave)
# -----------------------------------------------------------
def search_duckduckgo(query: str, max_results: int = 10):
    try:
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_redirect": "1", "no_html": "1"}
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            return []
        data = r.json()
        results = []
        for rel in data.get("RelatedTopics", []):
            if "Text" in rel and "FirstURL" in rel:
                results.append({
                    "title": rel["Text"],
                    "link": rel["FirstURL"],
                    "snippet": rel["Text"],
                    "source": "DuckDuckGo"
                })
        return results[:max_results]
    except Exception as e:
        logger.error(f"[DuckDuckGo] Error: {e}")
        return []


# -----------------------------------------------------------
# 💼 Bing Search API (requiere clave)
# -----------------------------------------------------------
def search_bing(query: str, username: str, max_results: int = 10):
    api_key = get_user_setting(username, "bing_api_key")
    if not api_key:
        return []

    url = "https://api.bing.microsoft.com/v7.0/search"
    headers = {"Ocp-Apim-Subscription-Key": api_key}
    params = {"q": query, "count": max_results}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        if r.status_code != 200:
            return []
        data = r.json()
        results = []
        for item in data.get("webPages", {}).get("value", []):
            results.append({
                "title": item.get("name"),
                "link": item.get("url"),
                "snippet": item.get("snippet"),
                "source": "Bing"
            })
        return results
    except Exception as e:
        logger.error(f"[Bing] Error: {e}")
        return []


# -----------------------------------------------------------
# 🧠 Agregador central (auto)
# -----------------------------------------------------------
def search_general(query: str, username: str, max_results: int = 15):
    """
    Busca utilizando SerpAPI, Google CSE, Bing o DuckDuckGo según disponibilidad.
    Aplica dorks contextualizados por tipo de entidad.
    """
    qtype = detect_query_type(query)
    logger.info(f"[search_general] Tipo detectado: {qtype}")

    # Dorks base
    dorks = {
        "email": f'"{query}" site:pastebin.com OR site:ghostbin.com OR site:github.com',
        "person": f'"{query}" site:linkedin.com OR site:facebook.com OR site:twitter.com',
        "domain": f'site:{query} OR "{query}" inurl:login OR contact',
        "phone": f'"{query}" site:telegram.org OR site:facebook.com'
    }

    search_query = dorks.get(qtype, query)

    # Orden de preferencia
    engines = [search_serpapi, search_google_cse, search_bing, search_duckduckgo]
    all_results = []
    for engine in engines:
        try:
            name = engine.__name__.replace("search_", "")
            logger.debug(f"[search_general] Usando motor: {name}")
            if "username" in engine.__code__.co_varnames:
                results = engine(search_query, username=username, max_results=max_results)
            else:
                results = engine(search_query, max_results=max_results)

            if results:
                all_results.extend(results)
                break  # si un motor devuelve algo, no seguimos
        except Exception as e:
            logger.warning(f"[search_general] Motor {engine.__name__} falló: {e}")

    # Eliminar duplicados por URL
    seen = set()
    unique_results = []
    for r in all_results:
        link = r.get("link")
        if link and link not in seen:
            unique_results.append(r)
            seen.add(link)

    logger.info(f"[search_general] {len(unique_results)} resultados obtenidos para '{query}' ({qtype})")
    return unique_results
