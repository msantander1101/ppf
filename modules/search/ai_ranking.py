from difflib import SequenceMatcher

def simple_similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def rank_results(query, results, top_n=None):
    """
    Ordena resultados en función de la similitud con el título y snippet.
    Asigna un score promedio entre título y snippet.
    """
    ranked = []
    for r in results:
        title = r.get('title') or ''
        snippet = r.get('snippet') or ''
        score_title = simple_similarity(query, title)
        score_snippet = simple_similarity(query, snippet)
        r['score'] = (score_title + score_snippet) / 2
        ranked.append(r)
    ranked.sort(key=lambda x: x['score'], reverse=True)
    return ranked[:top_n] if top_n else ranked
