# modules/search/document_search.py
from modules.search.ai_ranking import rank_results
from modules.search.buscadores import search_buscador

def search_documents(query, username=None, max_results=10):
    """
    Busca documentos (PDF, DOC, DOCX, etc.) relacionados con la entidad.
    """
    dork = f'("{query}" filetype:pdf OR filetype:doc OR filetype:docx OR filetype:pptx)'
    results = search_buscador(dork, username=username, engine="auto", max_results=max_results)
    return rank_results(query, results)
