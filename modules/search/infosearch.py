# modules/search/infosearch.py
from utils.logger import logger

def search_info(query: str, username: str = None, engine: str = "shodan", max_results: int = 10):
    # Placeholder: aquí irían Shodan, Censys, VirusTotal, etc.
    logger.info(f"[infosearch] Buscando info infra para: {query}")
    return [{"title": "Shodan lookup (placeholder)", "link": f"https://www.shodan.io/search?query={query}", "snippet": ""}]
