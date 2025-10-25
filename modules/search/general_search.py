from modules.search.ai_ranking import rank_results
from modules.search.buscadores import search_buscador

def search_general(query, username=None, max_results=10):
    """
    Busca en Google/Bing/DuckDuckGo de manera genérica.
    """
    results = search_buscador(query, username=username, engine="auto", max_results=max_results)
    return rank_results(query, results)
