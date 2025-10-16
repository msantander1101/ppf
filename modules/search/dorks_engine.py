import os
import requests
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from utils.logger import logger

SERPAPI_KEY_ENV = "SERPAPI_API_KEY"


def fill_template(template: str, entity: str) -> str:
    return template.replace("{entity}", entity)


def _serpapi_search(q: str, num: int = 10, api_key: str = None):
    api_key = api_key or os.environ.get(SERPAPI_KEY_ENV)
    if not api_key:
        raise RuntimeError("SerpAPI API key no disponible")
    url = "https://serpapi.com/search.json"
    params = {"engine": "google", "q": q, "num": num, "api_key": api_key}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("organic_results", [])


def _bing_search(q: str, num: int = 10):
    url = f"https://www.bing.com/search?q={quote_plus(q)}&count={num}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    for li in soup.select("li.b_algo")[:num]:
        a = li.find("a")
        title = a.get_text(strip=True) if a else None
        href = a.get("href") if a else None
        snippet = li.select_one(".b_caption p")
        snippet = snippet.get_text(strip=True) if snippet else ""
        results.append({"title": title or href, "link": href, "snippet": snippet})
    return results


def search_dork(query: str, engine: str = "auto", max_results: int = 10, api_key: str = None, use_fallback=True):
    try:
        if engine == "serpapi" or (engine == "auto" and (api_key or os.environ.get(SERPAPI_KEY_ENV))):
            return _serpapi_search(query, num=max_results, api_key=api_key)
        else:
            return _bing_search(query, num=max_results)
    except Exception as e:
        logger.warning(f"Dork search error ({engine}): {e}")
        if use_fallback and engine != "bing":
            return _bing_search(query, num=max_results)
        raise


def wayback_urls(domain_or_query: str, limit: int = 50):
    params = {"url": domain_or_query, "output": "json", "limit": limit}
    r = requests.get("https://web.archive.org/cdx/search/cdx", params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    entries = []
    if len(data) <= 1:
        return entries
    headers = data[0]
    for row in data[1:]:
        rec = dict(zip(headers, row))
        url = rec.get("original")
        ts = rec.get("timestamp")
        entries.append({"url": url, "timestamp": ts, "raw": rec})
    return entries
