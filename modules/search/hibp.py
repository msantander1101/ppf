import requests
from core.config import get_user_setting
from utils.logger import logger

HIBP_API_BASE = "https://haveibeenpwned.com/api/v3"


def _headers_for(username: str):
    key = get_user_setting(username, "hibp")
    if not key:
        logger.warning(f"[HIBP] No se encontró clave API para el usuario {username}.")
        return None
    return {"hibp-api-key": key, "user-agent": "ppf-osint-suite/1.0"}


def search_hibp(email: str, username: str):
    """
    Consulta HIBP para un email y devuelve lista de breaches normalizada.
    """
    if not email or not username:
        return []

    headers = _headers_for(username)
    if not headers:
        return []

    url = f"{HIBP_API_BASE}/breachedaccount/{email}"
    params = {"truncateResponse": False}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        if r.status_code == 200:
            data = r.json()
            normalized = []
            for b in data:
                normalized.append({
                    "Name": b.get("Name"),
                    "Domain": b.get("Domain", ""),
                    "BreachDate": b.get("BreachDate", ""),
                    "PwnCount": b.get("PwnCount", ""),
                    "Description": b.get("Description", "")
                })
            return normalized
        elif r.status_code == 404:
            return []
        elif r.status_code == 429:
            logger.warning(f"[HIBP] Rate limited (429) para {email}")
            return []
        else:
            logger.warning(f"[HIBP] Código inesperado {r.status_code}: {r.text}")
            return []
    except Exception as e:
        logger.exception(f"[HIBP] Error buscando {email}: {e}")
        return []
