import requests
from utils.logger import logger
from core.config import get_user_setting

def hibp_check(email: str, api_key: str) -> str:
    """Consulta Have I Been Pwned API para un email."""
    headers = {
        "hibp-api-key": api_key,
        "user-agent": "OSINTSuite/1.0"
    }
    url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}?truncateResponse=false"

    resp = requests.get(url, headers=headers)

    if resp.status_code == 404:
        return "No encontrado en brechas."
    elif resp.status_code == 200:
        breaches = [b["Name"] for b in resp.json()]
        return f"Filtrado en: {', '.join(breaches)}"
    else:
        logger.warning(f"HIBP error {resp.status_code} para {email}: {resp.text}")
        return f"Error {resp.status_code}: {resp.text}"

def enrich_person_emails(person_id: int, username: str, session):
    """Enriquece los emails de una persona consultando HIBP."""
    from core.entities import Email, Person

    api_key = get_user_setting(username, "hibp")
    if not api_key:
        return False, "No se ha configurado la API key de HIBP."

    person = session.get(Person, person_id)
    if not person:
        return False, "Persona no encontrada."

    updated = 0
    for email in person.emails:
        result = hibp_check(email.address, api_key)
        email.leaks_summary = result
        updated += 1

    session.commit()
    return True, f"{updated} correos enriquecidos con HIBP."
