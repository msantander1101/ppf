# modules/search/pastes_search.py
from modules.search.buscadores import search_buscador

TEMPLATES = [
    ("Pastebin por nombre", 'site:pastebin.com "{q}"'),
    ("Pastebin por email", 'site:pastebin.com "{email}"'),
    ("Otros pastes", '"{q}" site:ghostbin.com OR site:paste.ee OR site:hastebin.com'),
]

def search_pastes(q: str, email: str = "", username: str = None, max_results: int = 12):
    results = []
    for label, tpl in TEMPLATES:
        query = tpl.format(q=q, email=email or q)
        hits = search_buscadores(query, username=username, max_results=max_results)
        for h in hits:
            h["category"] = "pastes"
            h["label"] = label
            results.append(h)
    return results

# pequeño alias para usar el mismo backend (evita import circular si renombramos después)
def search_buscadores(query, username=None, max_results=12):
    return search_buscador(query, username=username, engine="auto", max_results=max_results)
