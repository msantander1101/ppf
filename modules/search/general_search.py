# modules/search/general_search.py
from modules.search.buscadores import search_buscador

TEMPLATES = [
    ("Menciones exactas", '"{q}"'),
    ("Nombre + alias", '"{q}" OR "{alias}"'),
    ("Nombre + cargo", '"{q}" ("CEO" OR "Manager" OR "Director")'),
]

def search_general(q: str, alias: str = "", username: str = None, max_results: int = 12):
    results = []
    for label, tpl in TEMPLATES:
        query = tpl.format(q=q, alias=alias or "")
        hits = search_buscador(query, username=username, engine="auto", max_results=max_results)
        for h in hits:
            h["category"] = "general"
            h["label"] = label
            results.append(h)
    return results
