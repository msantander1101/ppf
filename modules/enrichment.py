# modules/enrichment.py
from core.database import get_session
from core.entities import Person, OsintResult
from modules.search.autodetect import detect_type
from modules.search.emailint import search_email_intelligence
from modules.search.people_search import search_person_data
from modules.search.domainint import search_domain_intel
from modules.search.paste_search import search_pastes
from modules.search.darkweb import search_darkweb
from modules.search.general_search import search_general
from utils.logger import logger


def run_osint_enrichment(username: str, person_id: int, field_name: str, field_value: str):
    """
    Ejecuta enriquecimiento OSINT del campo indicado y guarda los resultados.
    """
    field_value = (field_value or "").strip()
    if not field_value:
        return []

    mode = detect_type(field_value)
    logger.info(f"[enrichment] Enriqueciendo '{field_value}' (tipo: {mode})")

    results = []

    try:
        if mode == "email":
            results = search_email_intelligence(username, field_value)
        elif mode == "person":
            results = search_person_data(username, field_value)
        elif mode == "domain":
            results = search_domain_intel(username, field_value)
        elif mode == "ip":
            results = search_general(field_value, username=username)
        else:
            # fallback general
            results = search_general(field_value, username=username)
    except Exception as e:
        logger.error(f"[enrichment] Error ejecutando búsqueda: {e}")
        return []

    if not results:
        logger.info(f"[enrichment] Sin resultados para {field_value}")
        return []

    # Guardar en BD
    try:
        with get_session() as session:
            for r in results:
                session.add(
                    OsintResult(
                        person_id=person_id,
                        query=field_value,
                        mode=mode,
                        title=r.get("title", ""),
                        link=r.get("link", ""),
                        snippet=r.get("snippet", ""),
                        source=r.get("source", ""),
                    )
                )
            session.commit()
        logger.info(f"[enrichment] {len(results)} resultados guardados para persona {person_id}")
    except Exception as e:
        logger.error(f"[enrichment] Error guardando resultados: {e}")

    return results
