# modules/search/hibp.py
import requests
from core.config import get_user_setting
from utils.logger import logger

API_URL = "https://haveibeenpwned.com/api/v3/breachedaccount/"


def search_hibp(email: str, username: str = None):
    """Busca filtraciones asociadas a un correo electrónico."""
    api_key = get_user_setting(username, "hibp")
    headers = {"hibp-api-key": api_key, "user-agent": "OSINT-Suite"}

    try:
        r = requests.get(f"{API_URL}{email}", headers=headers, timeout=15)
        if r.status_code == 404:
            return []
        if r.status_code != 200:
            logger.warning(f"HIBP error {r.status_code}: {r.text}")
            return []

        breaches = r.json()
        return [
            {
                "title": b.get("Name"),
                "link": f"https://haveibeenpwned.com/account/{email}",
                "snippet": f"{b.get('Title')} - {b.get('Domain')} ({b.get('BreachDate')})",
                "source": "HIBP"
            } for b in breaches
        ]
    except Exception as e:
        logger.error(f"[HIBP] Error consultando {email}: {e}")
        return []
