# modules/search/emailint.py
import requests
from core.config import get_user_setting
from modules.search.general_search import search_general
from utils.logger import logger

def hibp_breaches_for_email(username: str, email: str):
    """
    Devuelve lista de brechas de HaveIBeenPwned para el email.
    Requiere que el usuario tenga clave HIBP configurada.
    """
    api_key = get_user_setting(username, "hibp")
    if not api_key:
        logger.warning(f"[HIBP] No se encontró clave API para el usuario {username}.")
        return []

    headers = {"hibp-api-key": api_key, "user-agent": "OSINTSuite"}
    url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}?truncateResponse=false"

    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 404:
            return []
        else:
            logger.warning(f"[HIBP] Error {r.status_code}: {r.text}")
            return []
    except Exception as e:
        logger.error(f"[HIBP] Error al consultar HIBP: {e}")
        return []

def search_emailint(username: str, email: str, engine: str = "auto", max_results: int = 15):
    """
    Analiza un correo con HIBP y buscadores OSINT.
    """
    results = []

    # 🔹 HIBP Breaches
    breaches = hibp_breaches_for_email(username, email)
    for b in breaches:
        results.append({
            "title": f"{b.get('Name', 'Unknown')} breach",
            "link": f"https://haveibeenpwned.com/account/{email}",
            "snippet": f"Dominio: {b.get('Domain', '')} | Fecha: {b.get('BreachDate', '')} | Filtrado: {b.get('DataClasses', [])}",
            "source": "HaveIBeenPwned",
            "raw": b
        })

    # 🔹 Búsqueda OSINT adicional (pastes, leaks, etc.)
    dork = f'"{email}" site:pastebin.com OR site:ghostbin.com OR site:hastebin.com OR site:psbdmp.ws'
    more = search_general(dork, username=username, engine=engine, max_results=max_results)
    for m in more:
        m["source"] = "Email Leak Search"
        results.append(m)

    logger.info(f"[emailint_search] {len(results)} resultados combinados para {email}")
    return results
