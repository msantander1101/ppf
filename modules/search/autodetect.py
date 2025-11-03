# modules/search/autodetect.py
import re

def detect_type(query: str) -> str:
    """
    Detecta automáticamente el tipo de dato introducido por el usuario.
    Retorna uno de: email, domain, ip, username, person, general.
    """
    query = query.strip().lower()

    if re.match(r"[^@]+@[^@]+\.[^@]+", query):
        return "email"
    elif re.match(r"^(https?:\/\/)?([a-z0-9-]+\.)+[a-z]{2,}$", query):
        return "domain"
    elif re.match(r"^\d{1,3}(\.\d{1,3}){3}$", query):
        return "ip"
    elif len(query.split()) > 1:
        return "person"
    elif re.match(r"^[a-z0-9_.-]{3,}$", query):
        return "username"
    else:
        return "general"
