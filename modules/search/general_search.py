# modules/search/general_search.py
import requests
from core.config import get_user_setting
from utils.logger import logger

def search_general(query: str, username: str, engine: str = "auto", max_results: int = 15):
    """
    Realiza búsquedas generales usando SerpAPI o Google Custom Search API.
    """
    results = []
    serpapi_key = get_user_setting(username, "serpapi")
    google_key = get_user_setting(username, "google_api_key")
    google_cx = get_user_setting(username, "google_cse_cx")

    try:
        # 🔹 SerpAPI
        if engine in ("auto", "serpapi") and serpapi_key:
            params = {"engine": "google", "q": query, "num": max_results, "api_key": serpapi_key}
            r = requests.get("https://serpapi.com/search.json", params=params, timeout=10)
            data = r.json()
            for item in data.get("organic_results", []):
                results.append({
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "snippet": item.get("snippet", ""),
                    "source": "SerpAPI",
                    "raw": item
                })
            return results

        # 🔹 Google Custom Search API (CSE)
        if engine in ("auto", "google") and google_key and google_cx:
            url = f"https://www.googleapis.com/customsearch/v1"
            params = {"key": google_key, "cx": google_cx, "q": query, "num": max_results}
            r = requests.get(url, params=params, timeout=10)
            data = r.json()
            for item in data.get("items", []):
                results.append({
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "snippet": item.get("snippet", ""),
                    "source": "Google CSE",
                    "raw": item
                })
            return results

        logger.warning("[general_search] No se encontró ninguna API key activa para búsquedas.")
        return []

    except Exception as e:
        logger.error(f"[general_search] Error general: {e}")
        return []
