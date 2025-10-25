# modules/search/social_search.py
from modules.search.ai_ranking import rank_results
from modules.search.buscadores import search_buscador

def search_social(query, username=None, max_results=10):
    """
    Busca perfiles y menciones en redes sociales (Twitter, Facebook, Instagram, LinkedIn).
    """
    dork = f'site:twitter.com OR site:facebook.com OR site:instagram.com OR site:linkedin.com "{query}"'
    results = search_buscador(dork, username=username, engine="auto", max_results=max_results)
    return rank_results(query, results)
