# modules/search/paste_search.py
from modules.search.ai_ranking import rank_results
from modules.search.buscadores import search_buscador

def search_pastes(query, username=None, max_results=10):
    """
    Busca filtraciones o pastes (Pastebin, Ghostbin, etc.) relacionados con la entidad.
    """
    dork = f'site:pastebin.com "{query}" OR site:ghostbin.com "{query}" OR site:paste.ee "{query}"'
    results = search_buscador(dork, username=username, engine="auto", max_results=max_results)
    return rank_results(query, results)
