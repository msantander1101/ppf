# modules/search/darkweb.py
from modules.search.general_search import search_general
from utils.logger import logger

def search_darkweb(query: str, username: str, engine: str = "auto", max_results: int = 15):
    """
    Busca información relacionada en motores onion indexados públicamente.
    """
    try:
        dork = f'"{query}" site:onionsearchengine.com OR site:onionland.io OR site:danex.io OR site:tor.link'
        results = search_general(dork, username=username, engine=engine, max_results=max_results)
        for r in results:
            r["source"] = "Dark Web Search"
        logger.info(f"[darkweb_search] {len(results)} resultados para '{query}'")
        return results
    except Exception as e:
        logger.error(f"[darkweb_search] Error: {e}")
        return []
