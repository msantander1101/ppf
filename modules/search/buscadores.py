# modules/search/buscadores.py
import requests
from core.config import get_user_setting
from utils.logger import logger


def search_general(query: str, username: str = None, max_results: int = 10):
    """Busca en Google, Bing y DuckDuckGo (fallback automático)."""
    results = []

    serpapi_key = get_user_setting(username, "serpapi")
    cse_key = get_user_setting(username, "google_api_key")
    cse_cx = get_user_setting(username, "google_cse_cx")

    # Preferencia: SerpAPI > Google CSE > Bing > DuckDuckGo
    if serpapi_key:
        try:
            r = requests.get("https://serpapi.com/search.json", params={
                "engine": "google", "q": query, "num": max_results, "api_key": serpapi_key
            }, timeout=15)
            for item in r.json().get("organic_results", []):
                results.append({
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "snippet": item.get("snippet", ""),
                    "source": "Google"
                })
            return results
        except Exception as e:
            logger.warning(f"[search_general] Error SerpAPI: {e}")

    if cse_key and cse_cx:
        try:
            url = f"https://www.googleapis.com/customsearch/v1?key={cse_key}&cx={cse_cx}&q={query}"
            data = requests.get(url, timeout=10).json()
            for item in data.get("items", []):
                results.append({
                    "title": item["title"],
                    "link": item["link"],
                    "snippet": item.get("snippet", ""),
                    "source": "Google CSE"
                })
            return results
        except Exception as e:
            logger.warning(f"[search_general] Error Google CSE: {e}")

    # Bing fallback
    try:
        html = requests.get(f"https://www.bing.com/search?q={query}", timeout=10).text
        parts = html.split('<li class="b_algo"')
        for p in parts[1:max_results]:
            title_start = p.find("<h2>")
            title_end = p.find("</h2>")
            href_start = p.find('href="') + 6
            href_end = p.find('"', href_start)
            title = p[title_start + 4:title_end]
            link = p[href_start:href_end]
            results.append({"title": title, "link": link, "snippet": "", "source": "Bing"})
    except Exception as e:
        logger.warning(f"[search_general] Fallback DuckDuckGo: {e}")
        try:
            html = requests.get(f"https://duckduckgo.com/html/?q={query}", timeout=10).text
            items = html.split('<a class="result__a"')
            for h in items[1:max_results]:
                href_start = h.find('href="') + 6
                href_end = h.find('"', href_start)
                title_start = h.find(">") + 1
                title_end = h.find("</a>")
                results.append({
                    "title": h[title_start:title_end],
                    "link": h[href_start:href_end],
                    "snippet": "",
                    "source": "DuckDuckGo"
                })
        except Exception as ex:
            logger.error(f"[search_general] Error final: {ex}")
    return results[:max_results]
