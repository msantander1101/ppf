"""
Módulo central de enriquecimiento de entidades (personas, correos, dominios, etc.)
para OSINT Suite. Utiliza las API keys guardadas por el usuario en core.config.
"""

import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
from core.config import get_user_setting
from utils.logger import logger


class EnrichmentResult:
    """
    Representa el resultado de un proceso de enriquecimiento.
    Se utiliza para mostrar resultados en la UI y registrar en base de datos.
    """
    def __init__(self, source: str, category: str, data: Dict[str, Any]):
        self.source = source
        self.category = category
        self.data = data
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "category": self.category,
            "data": self.data,
            "timestamp": self.timestamp.isoformat()
        }


# ============================================================
# Funciones principales de enriquecimiento
# ============================================================

def enrich_person(username: str, person: Dict[str, Any]) -> List[EnrichmentResult]:
    """
    Enriquecimiento de una persona a partir de su información básica.
    - Busca presencia online (Google, Bing, redes)
    - Valida emails o usernames asociados
    - Busca fugas y menciones
    """
    results = []
    logger.debug(f"[enrichment] Iniciando enriquecimiento de persona: {person}")

    name = person.get("name") or ""
    email = person.get("email") or ""
    username_field = person.get("username") or ""

    # --- SERPAPI (búsqueda general en Google)
    serp_key = get_user_setting(username, "serpapi")
    if serp_key:
        try:
            serp_results = _search_serpapi(name or email or username_field, serp_key)
            results.append(EnrichmentResult("SerpAPI", "search", {"results": serp_results}))
        except Exception as e:
            logger.warning(f"[enrichment] Error usando SerpAPI: {e}")

    # --- HUNTER.IO (validación de correo)
    if email:
        hunter_key = get_user_setting(username, "hunter")
        if hunter_key:
            try:
                hunter_data = _check_hunter(email, hunter_key)
                results.append(EnrichmentResult("Hunter.io", "email_verification", hunter_data))
            except Exception as e:
                logger.warning(f"[enrichment] Error usando Hunter.io: {e}")

    # --- HaveIBeenPwned (fugas de email)
    if email:
        hibp_key = get_user_setting(username, "hibp")
        if hibp_key:
            try:
                breaches = _check_hibp(email, hibp_key)
                if breaches:
                    results.append(EnrichmentResult("HaveIBeenPwned", "data_breaches", {"breaches": breaches}))
            except Exception as e:
                logger.warning(f"[enrichment] Error usando HIBP: {e}")

    return results


def enrich_email(username: str, email: str) -> List[EnrichmentResult]:
    """
    Enriquecimiento de un correo electrónico.
    """
    person = {"email": email}
    return enrich_person(username, person)


def enrich_domain(username: str, domain: str) -> List[EnrichmentResult]:
    """
    Enriquecimiento de un dominio.
    Usa WhoisXML, Shodan y SerpAPI si hay claves disponibles.
    """
    results = []
    logger.debug(f"[enrichment] Enriqueciendo dominio: {domain}")

    # --- WHOISXML
    whois_key = get_user_setting(username, "whoisxml")
    if whois_key:
        try:
            whois_data = _check_whoisxml(domain, whois_key)
            results.append(EnrichmentResult("WhoisXML", "domain_info", whois_data))
        except Exception as e:
            logger.warning(f"[enrichment] Error en WhoisXML: {e}")

    # --- SHODAN
    shodan_key = get_user_setting(username, "shodan")
    if shodan_key:
        try:
            shodan_data = _check_shodan(domain, shodan_key)
            results.append(EnrichmentResult("Shodan", "infrastructure", shodan_data))
        except Exception as e:
            logger.warning(f"[enrichment] Error en Shodan: {e}")

    # --- SERPAPI (búsqueda de referencias)
    serp_key = get_user_setting(username, "serpapi")
    if serp_key:
        try:
            serp_results = _search_serpapi(domain, serp_key)
            results.append(EnrichmentResult("SerpAPI", "mentions", {"results": serp_results}))
        except Exception as e:
            logger.warning(f"[enrichment] Error en SerpAPI: {e}")

    return results


# ============================================================
# Funciones auxiliares de APIs externas
# ============================================================

def _search_serpapi(query: str, api_key: str) -> List[Dict[str, str]]:
    """
    Realiza una búsqueda en Google a través de SerpAPI.
    """
    logger.debug(f"[SerpAPI] Buscando: {query}")
    url = f"https://serpapi.com/search.json?q={query}&num=10&api_key={api_key}"
    resp = requests.get(url, timeout=15)
    data = resp.json()
    results = []
    for item in data.get("organic_results", []):
        results.append({
            "title": item.get("title"),
            "link": item.get("link"),
            "snippet": item.get("snippet")
        })
    return results


def _check_hunter(email: str, api_key: str) -> Dict[str, Any]:
    """
    Valida un correo electrónico con Hunter.io.
    """
    logger.debug(f"[Hunter.io] Validando email: {email}")
    url = f"https://api.hunter.io/v2/email-verifier?email={email}&api_key={api_key}"
    resp = requests.get(url, timeout=15)
    return resp.json().get("data", {})


def _check_hibp(email: str, api_key: str) -> List[str]:
    """
    Consulta fugas conocidas en HaveIBeenPwned.
    """
    logger.debug(f"[HIBP] Consultando fugas para {email}")
    headers = {"hibp-api-key": api_key, "User-Agent": "ppf-osint-suite"}
    resp = requests.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}", headers=headers, timeout=15)
    if resp.status_code == 404:
        return []
    return [b["Name"] for b in resp.json()]


def _check_whoisxml(domain: str, api_key: str) -> Dict[str, Any]:
    """
    Obtiene información WHOIS de un dominio con WhoisXML API.
    """
    logger.debug(f"[WhoisXML] Consultando dominio: {domain}")
    url = f"https://www.whoisxmlapi.com/whoisserver/WhoisService?apiKey={api_key}&domainName={domain}&outputFormat=JSON"
    resp = requests.get(url, timeout=15)
    return resp.json().get("WhoisRecord", {})


def _check_shodan(domain: str, api_key: str) -> Dict[str, Any]:
    """
    Consulta información de infraestructura con Shodan.
    """
    logger.debug(f"[Shodan] Consultando dominio: {domain}")
    url = f"https://api.shodan.io/dns/resolve?hostnames={domain}&key={api_key}"
    resp = requests.get(url, timeout=15)
    data = resp.json()
    ip = data.get(domain)
    if not ip:
        return {"ip": None}
    info = requests.get(f"https://api.shodan.io/shodan/host/{ip}?key={api_key}", timeout=15)
    return info.json()