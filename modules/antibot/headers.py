import random

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",  # (ejemplos de User-Agent reales)
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64)...",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)..."
]

def get_random_headers():
    """Devuelve un diccionario de cabeceras HTTP con un User-Agent aleatorio."""
    return {"User-Agent": random.choice(USER_AGENTS)}
