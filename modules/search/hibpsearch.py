# modules/search/hibpsearch.py
"""
Consulta Have I Been Pwned (HIBP) para detectar si un email
ha sido comprometido en filtraciones conocidas.
"""

import requests
from core.config import get_user_setting
from utils.logger import logger


def hibp_lookup(username: str, email: str):
    """
    Busca filtraciones asociadas a un correo electrónico en HIBP.
    Devuelve lista de breaches detectados.
    """
    api_key = get_user_setting(username, "hibp_api_key")
    if not api_key:
        logger.warning("[hibpsearch] No se ha configurado HIBP API key.")
        return []

    headers = {"hibp-api-key": api_key, "User-Agent": "OSINT-Suite/1.0"}
    url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}?truncateResponse=false"

    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 404:
            return []  # No breaches
        r.raise_for_status()
        data = r.json()
        breaches = []
        for b in data:
            breaches.append({
                "name": b.get("Name"),
                "domain": b.get("Domain"),
                "breach_date": b.get("BreachDate"),
                "description": b.get("Description", "")[:250]
            })
        return breaches
    except Exception as e:
        logger.error(f"[hibpsearch] Error consultando HIBP: {e}")
        return []
