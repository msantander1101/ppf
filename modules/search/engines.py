# modules/search/engines.py
from utils.logger import logger
from modules.search.buscadores import search_buscador
from modules.search.pastes_search import search_paste
from modules.search.social_search import search_social
from modules.search.code_search import search_code
from modules.search.infosearch import search_info
from modules.search.archive_search import search_archive


def search(query: str, username: str = None, category: str = "buscadores", engine: str = "auto", max_results: int = 10):
    """
    Router principal de búsquedas. Redirige según categoría.
    """
    try:
        if category == "buscadores":
            return search_buscador(query, username, engine, max_results)
        elif category == "pastes":
            return search_paste(query, username, engine, max_results)
        elif category == "social":
            return search_social(query, username, engine, max_results)
        elif category == "code":
            return search_code(query, username, engine, max_results)
        elif category == "infra":
            return search_info(query, username, engine, max_results)
        elif category == "archive":
            return search_archive(query, username, engine, max_results)
        else:
            logger.warning(f"[engines] Categoría desconocida: {category}")
            return []
    except Exception as e:
        logger.exception(f"[engines] Error ejecutando búsqueda en categoría {category}: {e}")
        return []
