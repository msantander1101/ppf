import whois
from utils.logger import logger
from core.config import get_user_setting
from datetime import datetime


def enrich_domain(domain: str) -> str:
    """Obtiene información WHOIS básica de un dominio."""
    try:
        data = whois.whois(domain)
        if not data.domain_name:
            return "Dominio no encontrado o WHOIS vacío."

        created = data.creation_date
        updated = data.updated_date
        expires = data.expiration_date
        registrar = data.registrar
        return (
            f"Registrador: {registrar}, "
            f"Creado: {created}, "
            f"Expira: {expires}"
        )
    except Exception as e:
        logger.warning(f"Error WHOIS para {domain}: {e}")
        return f"Error WHOIS: {e}"


def enrich_person_domains(person_id: int, username: str, session):
    """Busca dominios en los emails de una persona y ejecuta WHOIS."""
    from core.entities import Email, Profile, Person
    from core.entities import Profile  # seguridad

    person = session.get(Person, person_id)
    if not person:
        return False, "Persona no encontrada."

    found_domains = set()
    for e in person.emails:
        if "@" in e.address:
            domain = e.address.split("@")[-1]
            found_domains.add(domain)

    updated = 0
    for domain in found_domains:
        result = enrich_domain(domain)
        # Guardamos en notas del perfil de la persona para simplificar
        person.notes = (person.notes or "") + f"\n🌐 {domain}: {result}"
        updated += 1

    session.commit()
    return True, f"{updated} dominios enriquecidos."
