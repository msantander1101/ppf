"""
Módulo: docs.py
-------------------------------------
Busca documentos públicos (PDF, DOCX, PPT, XLS, TXT, etc.) relacionados con una entidad o persona.
Compatible con buscadores.py, usando SerpAPI, Google CSE o DuckDuckGo como fallback.
"""

import requests
from core.config import get_user_setting
from utils.logger import logger


# ==========================================================
# 🔹 Función principal
# ==========================================================
def search_docs(query: str, username: str, max_results: int = 15) -> list:
    """
    Busca documentos públicos (PDF, DOCX, XLS, PPT, TXT) relacionados con la consulta.
    """
    try:
        serp_key = get_user_setting(username, "serpapi")
        google_key = get_user_setting(username, "google_api_key")
        google_cx = get_user_setting(username, "google_cse_cx")

        # Selección de fuente
        if serp_key:
            results = _search_docs_serpapi(query, serp_key, max_results)
        elif google_key and google_cx:
            results = _search_docs_google(query, google_key, google_cx, max_results)
        else:
            results = _search_docs_duckduckgo(query, max_results)

        logger.info(f"[docs] {len(results)} resultados de documentos para '{query}'")
        return results

    except Exception as e:
        logger.exception(f"[docs] Error general: {e}")
        return []


# ==========================================================
# 🔹 SERPAPI
# ==========================================================
def _search_docs_serpapi(query: str, serp_key: str, max_results: int = 15) -> list:
    """
    Busca documentos usando SerpAPI.
    """
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google",
        "q": f'"{query}" (filetype:pdf OR filetype:docx OR filetype:pptx OR filetype:xlsx OR filetype:txt)',
        "num": max_results,
        "api_key": serp_key
    }

    try:
        r = requests.get(url, params=params, timeout=20)
        if r.status_code != 200:
            logger.warning(f"[docs-serpapi] Código {r.status_code}: {r.text[:100]}")
            return []

        organic = r.json().get("organic_results", [])
        results = []
        for i in organic:
            results.append({
                "title": i.get("title"),
                "link": i.get("link"),
                "snippet": i.get("snippet"),
                "source": "docs-serpapi"
            })
        return results

    except Exception as e:
        logger.exception(f"[docs-serpapi] Error ejecutando búsqueda: {e}")
        return []


# ==========================================================
# 🔹 Google Custom Search API
# ==========================================================
def _search_docs_google(query: str, google_key: str, google_cx: str, max_results: int = 15) -> list:
    """
    Busca documentos usando la API de Google Custom Search.
    """
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "q": f'"{query}" (filetype:pdf OR filetype:docx OR filetype:pptx OR filetype:xlsx OR filetype:txt)',
        "key": google_key,
        "cx": google_cx,
        "num": min(max_results, 10)
    }

    try:
        r = requests.get(url, params=params, timeout=20)
        if r.status_code != 200:
            logger.warning(f"[docs-google] Código {r.status_code}: {r.text[:100]}")
            return []

        items = r.json().get("items", [])
        results = []
        for i in items:
            results.append({
                "title": i.get("title"),
                "link": i.get("link"),
                "snippet": i.get("snippet"),
                "source": "docs-google"
            })
        return results

    except Exception as e:
        logger.exception(f"[docs-google] Error: {e}")
        return []


# ==========================================================
# 🔹 DuckDuckGo (sin clave)
# ==========================================================
def _search_docs_duckduckgo(query: str, max_results: int = 10) -> list:
    """
    Fallback con DuckDuckGo (sin API key).
    """
    url = "https://api.duckduckgo.com/"
    params = {
        "q": f'"{query}" (filetype:pdf OR filetype:docx OR filetype:pptx OR filetype:xlsx OR filetype:txt)',
        "format": "json",
        "no_redirect": 1,
        "no_html": 1
    }

    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            logger.warning(f"[docs-duckduckgo] Código {r.status_code}")
            return []

        data = r.json()
        results = []
        for topic in data.get("RelatedTopics", []):
            if "Text" in topic and "FirstURL" in topic:
                results.append({
                    "title": topic["Text"],
                    "link": topic["FirstURL"],
                    "snippet": topic.get("Result", ""),
                    "source": "docs-duckduckgo"
                })

        return results[:max_results]

    except Exception as e:
        logger.warning(f"[docs-duckduckgo] Error: {e}")
        return []
