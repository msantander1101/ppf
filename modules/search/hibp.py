import time
import requests
from utils.logger import logger
from core.config import get_user_setting  # ✅ correcta función para leer configuraciones del usuario

def search_hibp(email: str, username: str):
    """
    Busca si un email ha sido filtrado en Have I Been Pwned (HIBP).
    Usa la API key almacenada en configuración (get_user_setting) y gestiona el rate limit automáticamente.
    """
    api_key = get_user_setting(username, "hibp")
    if not api_key:
        logger.warning(f"[HIBP] No se encontró clave API para el usuario {username}.")
        return None

    headers = {
        "hibp-api-key": api_key,
        "user-agent": f"OSINTSuite/{username}"
    }

    url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
    max_retries = 5
    delay = 2  # segundos entre intentos

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, timeout=15)

            # ✅ 200 → resultados encontrados
            if resp.status_code == 200:
                return resp.json()

            # ⚪ 404 → no hay filtraciones
            elif resp.status_code == 404:
                logger.info(f"[HIBP] {email} no encontrado en filtraciones.")
                return None

            # 🟡 429 → rate limit → espera y reintenta
            elif resp.status_code == 429:
                wait_time = 5 + attempt * 2
                logger.warning(f"[HIBP] Rate limit alcanzado (429). Esperando {wait_time}s...")
                time.sleep(wait_time)
                continue

            # 🔴 otros errores HTTP
            else:
                logger.warning(f"[HIBP] Error {resp.status_code}: {resp.text}")
                return None

        except requests.RequestException as e:
            logger.error(f"[HIBP] Error de conexión al consultar {email}: {e}")
            time.sleep(delay)

    logger.warning(f"[HIBP] Demasiados intentos fallidos para {email}.")
    return None
