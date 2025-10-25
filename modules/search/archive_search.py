# modules/search/archive_search.py
from modules.search.ai_ranking import rank_results
from modules.search.buscadores import search_buscador

def search_archive(query, username=None, max_results=10):
    """
    Busca en la Wayback Machine y otros archivos históricos (copias antiguas).
    """
    dork = f'site:web.archive.org "{query}"'
    results = search_buscador(dork, username=username, engine="auto", max_results=max_results)
    return rank_results(query, results)
