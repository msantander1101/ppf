# modules/search/code_search.py
from modules.search.ai_ranking import rank_results
from modules.search.buscadores import search_buscador

def search_code(query, username=None, max_results=10):
    """
    Busca presencia técnica en GitHub, GitLab, StackOverflow.
    """
    dork = f'site:github.com OR site:gitlab.com OR site:stackoverflow.com "{query}"'
    results = search_buscador(dork, username=username, engine="auto", max_results=max_results)
    return rank_results(query, results)
