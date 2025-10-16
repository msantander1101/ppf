import requests
from utils.logger import logger

SOCIAL_PLATFORMS = {
    "Twitter": "https://twitter.com/{handle}",
    "Instagram": "https://instagram.com/{handle}",
    "Facebook": "https://facebook.com/{handle}",
    "GitHub": "https://github.com/{handle}",
    "LinkedIn": "https://www.linkedin.com/in/{handle}",
}


def check_profile_exists(url: str) -> bool:
    """Verifica si una URL de perfil existe (HTTP 200)."""
    try:
        resp = requests.get(url, timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def enrich_person_profiles(person_id: int, session):
    """Comprueba si los perfiles sociales existen realmente."""
    from core.entities import Person, Profile

    person = session.get(Person, person_id)
    if not person:
        return False, "Persona no encontrada."

    checked = 0
    for pr in person.profiles:
        base_url = SOCIAL_PLATFORMS.get(pr.platform, pr.url)
        url = base_url.format(handle=pr.handle) if "{handle}" in base_url else pr.url
        exists = check_profile_exists(url)
        pr.url = url
        pr.info_json = f"✅ Activo" if exists else "⚠️ No encontrado"
        checked += 1

    session.commit()
    return True, f"{checked} perfiles sociales comprobados."
