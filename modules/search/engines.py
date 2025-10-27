# modules/search/engines.py
from utils.logger import logger
from modules.search.buscadores import search_buscador
from modules.search.pastes import search_pastes
from modules.search.social import search_social
from modules.search.code import search_code
from modules.search.infosearch import search_info
from modules.search.archive_search import search_archive

# modules/search/engines.py
def search(query, username=None, category='general', max_results=10):
    from modules.search import (
        general_search, docs, pastes,
        social, code, archive_search
    )
    category_map = {
        'general': general_search.search_general,
        'documents': documents_search.search_documents,
        'pastes': pastes_search.search_pastes,
        'social': social_search.search_social,
        'code': code.search_code,
        'archive': archive_search.search_archive,
    }
    search_func = category_map.get(category, general_search.search_general)
    return search_func(query, username=username, max_results=max_results)
