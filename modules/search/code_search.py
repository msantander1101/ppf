# modules/search/code_search.py
import requests
from core.config import get_user_setting
from utils.logger import logger


def search_code(query: str, username: str = None, engine: str = "github", max_results: int = 10):
    token = get_user_setting(username, "github_token")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    results = []
    try:
        url = f"https://api.github.com/search/code?q={query}&per_page={max_results}"
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        for item in data.get("items", []):
            results.append({"title": item["name"], "link": item["html_url"], "snippet": item["repository"]["full_name"]})
    except Exception as e:
        logger.warning(f"[codesearch] Error GitHub: {e}")
    return results
