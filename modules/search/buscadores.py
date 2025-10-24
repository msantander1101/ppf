# modules/search/buscadores.py
import requests
from core.config import get_user_setting
from utils.logger import logger


def search_buscador(query: str, username: str = None, engine: str = "auto", max_results: int = 10):
    """
    Ejecuta búsqueda en Google / Bing / DuckDuckGo según disponibilidad.
    """
    results = []

    serpapi_key = get_user_setting(username, "serpapi")
    cse_key = get_user_setting(username, "google_api_key")
    cse_cx = get_user_setting(username, "google_cse_cx")

    if engine == "google" or (engine == "auto" and serpapi_key):
        try:
            url = "https://serpapi.com/search.json"
            params = {"engine": "google", "q": query, "num": max_results, "api_key": serpapi_key}
            r = requests.get(url, params=params, timeout=15)
            data = r.json()
            for item in data.get("organic_results", []):
                results.append({
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "snippet": item.get("snippet", "")
                })
            return results
        except Exception as e:
            logger.warning(f"[buscadores] Fallback a Bing por error en SerpAPI: {e}")

    if engine in ("bing", "auto"):
        try:
            r = requests.get(f"https://www.bing.com/search?q={query}&count={max_results}", timeout=10)
            items = r.text.split('<li class="b_algo"')
            for it in items[1:]:
                title_start = it.find("<h2>")
                title_end = it.find("</h2>")
                link_start = it.find('href="') + 6
                link_end = it.find('"', link_start)
                title = it[title_start + 4:title_end]
                link = it[link_start:link_end]
                results.append({"title": title, "link": link, "snippet": ""})
            return results[:max_results]
        except Exception as e:
            logger.warning(f"[buscadores] Fallback a DuckDuckGo: {e}")

    try:
        r = requests.get(f"https://duckduckgo.com/html/?q={query}", timeout=10)
        html = r.text.split('<a class="result__a"')
        for h in html[1:max_results]:
            href_start = h.find('href="') + 6
            href_end = h.find('"', href_start)
            link = h[href_start:href_end]
            title_start = h.find(">") + 1
            title_end = h.find("</a>")
            title = h[title_start:title_end]
            results.append({"title": title, "link": link, "snippet": ""})
    except Exception as e:
        logger.error(f"[buscadores] Error general: {e}")

    return results[:max_results]
