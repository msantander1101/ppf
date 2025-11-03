# modules/search/paste_search.py
from modules.search.general_search import search_general
from utils.logger import logger

def search_pastes(username: str, q: str, engine: str = "auto", max_results: int = 15):
    """
    Busca coincidencias en sitios de leaks/pastes.
    """
    try:
        dork = f'"{q}" site:pastebin.com OR site:ghostbin.com OR site:hastebin.com OR site:psbdmp.ws OR site:leakpeek.com'
        results = search_general(dork, username=username, engine=engine, max_results=max_results)
        for r in results:
            r["source"] = "Paste OSINT"
        logger.info(f"[paste_search] {len(results)} resultados para '{q}'")
        return results
    except Exception as e:
        logger.error(f"[paste_search] Error: {e}")
        return []
