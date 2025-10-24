# modules/search/documents_search.py
from modules.search.buscadores import search_buscador

TEMPLATES = [
    ("PDF/DOCX/DOC", '"{q}" (filetype:pdf OR filetype:doc OR filetype:docx)'),
    ("Currículums", '"{q}" (intitle:cv OR intitle:curriculum) (filetype:pdf OR filetype:docx)'),
    ("Presentaciones", '"{q}" filetype:ppt OR filetype:pptx'),
]

def search_documents(q: str, username: str = None, max_results: int = 12):
    results = []
    for label, tpl in TEMPLATES:
        hits = search_buscador(tpl.format(q=q), username=username, engine="auto", max_results=max_results)
        for h in hits:
            h["category"] = "documents"
            h["label"] = label
            results.append(h)
    return results
