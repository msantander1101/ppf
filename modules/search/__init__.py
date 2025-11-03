# modules/search/__init__.py
"""
Inicialización del paquete de búsqueda OSINT Suite.
Agrupa todos los módulos de búsqueda (engines, autodetect, emailint, etc.)
para importación simplificada y compatibilidad con versiones anteriores.
"""

from utils.logger import logger

# Importar submódulos principales
try:
    from modules.search.engines import smart_search
    from modules.search.buscadores import search_general, search_buscador
    from modules.search.autodetect import detect_type

    # Módulos especializados
    from modules.search.emailint import search_email_intelligence
    from modules.search.people_search import search_person_data
    from modules.search.domainint import search_domain_intel
    from modules.search.paste_search import search_pastes
    from modules.search.darkweb import search_darkweb
    from modules.search.general_search import search_general as general_search

    logger.info("[modules.search] Módulos de búsqueda inicializados correctamente.")

except ImportError as e:
    logger.error(f"[modules.search] Error al importar submódulos: {e}")
    raise


# Exportar funciones clave para acceso directo
__all__ = [
    "smart_search",
    "search_general",
    "search_buscador",
    "detect_type",
    "search_email_intelligence",
    "search_person_data",
    "search_domain_intel",
    "search_pastes",
    "search_darkweb",
    "general_search",
]
