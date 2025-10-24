# modules/search/social_search.py
import requests
from utils.logger import logger

SOCIAL_PLATFORMS = {
    "twitter": "https://twitter.com/search?q={query}",
    "reddit": "https://www.reddit.com/search/?q={query}",
    "instagram": "https://www.instagram.com/{query}/",
    "facebook": "https://www.facebook.com/search/top/?q={query}",
}


def search_social(query: str, username: str = None, engine: str = "auto", max_results: int = 10):
    results = []
    for name, url_tpl in SOCIAL_PLATFORMS.items():
        results.append({"title": f"{name.capitalize()} search", "link": url_tpl.format(query=query), "snippet": ""})
    return results
