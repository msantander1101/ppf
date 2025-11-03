# modules/search/engines.py
"""
Router principal de motores OSINT
Permite enrutar automáticamente la búsqueda según el tipo de dato o módulo solicitado.
Cada módulo devuelve resultados en formato unificado para renderizado en UI y grafo.
"""

from typing import List, Dict, Any, Optional

from utils.logger import logger

# === Importación de módulos de búsqueda ===
from modules.search.general_search import search_general
from modules.search.darkweb import search_darkweb
from modules.search.socmint import search_socmint
from modules.search.people_search import search_people
from modules.search.emailint import search_emailint
from modules.search.phoneint import search_phoneint
from modules.search.domainint import search_domainint
from modules.search.breachdata import search_breachdata
from modules.search.geoint import search_geoint
from modules.search.imageint import search_imageint
from modules.search.publicdata import search_publicdata
from modules.search.webintelligence import search_webosint

# === Enrutador principal ===
def run_search(
    username: str,
    query: str,
    qtype: Optional[str] = None,
    mode: Optional[str] = None,
    max_results: int = 20
) -> List[Dict[str, Any]]:
    """
    Ejecuta la búsqueda OSINT correspondiente al tipo o módulo.
    Retorna una lista normalizada de resultados.
    """

    logger.info(f"[ENGINES] Ejecutando búsqueda: query='{query}', type='{qtype}', mode='{mode}'")

    try:
        if mode == "darkweb":
            return search_darkweb(query, username=username, max_results=max_results)
        elif mode == "socmint":
            return search_socmint(query, username=username, max_results=max_results)
        elif mode == "people":
            return search_people(query, username=username, max_results=max_results)
        elif mode == "emailint" or qtype == "email":
            return search_emailint(query, username=username, max_results=max_results)
        elif mode == "phoneint" or qtype == "phone":
            return search_phoneint(query, username=username, max_results=max_results)
        elif mode == "domainint" or qtype == "domain":
            return search_domainint(query, username=username, max_results=max_results)
        elif mode == "breachdata":
            return search_breachdata(query, username=username, max_results=max_results)
        elif mode == "geoint":
            return search_geoint(query, username=username, max_results=max_results)
        elif mode == "imageint":
            return search_imageint(query, username=username, max_results=max_results)
        elif mode == "publicdata":
            return search_publicdata(query, username=username, max_results=max_results)
        elif mode == "webosint":
            return search_webosint(query, username=username, max_results=max_results)
        else:
            # Búsqueda general por defecto
            return search_general(query, username=username, max_results=max_results)
    except Exception as e:
        logger.error(f"[ENGINES] Error ejecutando búsqueda ({mode or qtype}): {e}")
        return []
