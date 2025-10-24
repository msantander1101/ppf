# modules/search/archive_search.py
import requests
from utils.logger import logger


def search_archive(query: str, username: str = None, engine: str = "wayback", max_results: int = 10):
    results = []
    try:
        url = f"http://web.archive.org/cdx/search/cdx?url={query}/*&output=json&fl=original,timestamp&limit={max_results}"
        r = requests.get(url, timeout=10)
        data = r.json()[1:]
        for d in data:
            results.append({
                "title": "Wayback capture",
                "link": d[0],
                "snippet": f"timestamp: {d[1]}"
            })
    except Exception as e:
        logger.warning(f"[archive] Error en Wayback: {e}")
    return results
