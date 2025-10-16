import requests
from typing import List, Dict
from urllib.parse import urlparse
from utils.logger import logger
import time

GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"

def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return url or ""

def search_google_cse(query: str, api_key: str, cx: str, num: int = 10, pause: float = 0.1) -> List[Dict]:
    """
    Wrapper ligero para Google Custom Search (CSE).
    Devuelve lista de dicts: {title, link, snippet, domain, source}
    """
    if not api_key or not cx:
        raise ValueError("api_key y cx son requeridos")

    results = []
    retrieved = 0
    start = 1
    while retrieved < num:
        per_call = min(10, num - retrieved)
        params = {
            "q": query,
            "key": api_key,
            "cx": cx,
            "start": start,
            "num": per_call,
        }
        logger.debug(f"[google_cse] q={query} start={start} num={per_call}")
        r = requests.get(GOOGLE_CSE_URL, params=params, timeout=15)
        if r.status_code == 200:
            data = r.json()
            items = data.get("items", [])
            for it in items:
                title = it.get("title")
                link = it.get("link")
                snippet = it.get("snippet") or ""
                results.append({
                    "title": title,
                    "link": link,
                    "snippet": snippet,
                    "domain": _extract_domain(link or ""),
                    "source": "google_cse"
                })
            retrieved += len(items)
            if len(items) < per_call:
                break
            start += len(items)
            time.sleep(pause)
        else:
            try:
                err = r.json()
            except Exception:
                err = r.text
            logger.error(f"[google_cse] Error {r.status_code}: {err}")
            raise RuntimeError(f"Google CSE error {r.status_code}: {err}")
    return results
