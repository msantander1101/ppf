"""
AntiBot & Request Manager — Versión avanzada.
Rotación de proxies, fallback automático a Tor, delays aleatorios y detección de bloqueos.
Integrado con core/config (proxy, proxy_list, tor_enabled).
"""

import requests
import random
import time
from itertools import cycle
from core.config import get_user_setting
from utils.logger import logger

# ==============================================
# 🧩 LISTAS DE USER-AGENTS
# ==============================================
USER_AGENTS = [
    # Navegadores reales
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/126.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Bots disfrazados
    "Googlebot/2.1 (+http://www.google.com/bot.html)",
    "Bingbot/2.0 (+http://www.bing.com/bingbot.htm)",
    "DuckDuckBot/1.1; (+http://duckduckgo.com/duckduckbot.html)"
]

# ==============================================
# 🔍 PATRONES DE BLOQUEO / CAPTCHA
# ==============================================
BLOCK_PATTERNS = [
    "captcha", "verify you are human", "access denied", "forbidden",
    "temporarily unavailable", "rate limit", "unusual traffic",
    "cloudflare", "akamai", "perimeterx"
]

# ==============================================
# 🔁 SISTEMA DE PROXY ROTATION
# ==============================================

_proxy_cycle = None  # ciclo global de proxies


def _init_proxy_rotation(username: str):
    """
    Inicializa el ciclo de proxies del usuario desde la configuración.
    Admite 'proxy' (simple) o 'proxy_list' (varios separados por coma/espacio/nueva línea).
    """
    global _proxy_cycle

    proxy_list = get_user_setting(username, "proxy_list")
    if proxy_list:
        proxies = [p.strip() for p in proxy_list.replace(",", "\n").splitlines() if p.strip()]
    else:
        single = get_user_setting(username, "proxy")
        proxies = [single] if single else []

    if proxies:
        _proxy_cycle = cycle(proxies)
        logger.info(f"[AntiBot] Rotación de {len(proxies)} proxies inicializada.")
    else:
        _proxy_cycle = None
        logger.info("[AntiBot] Sin proxies configurados, se usará conexión directa.")


def get_next_proxy(username: str) -> dict | None:
    """
    Devuelve el siguiente proxy de la rotación o el configurado.
    Si tor_enabled=True, usa Tor por SOCKS5.
    """
    global _proxy_cycle

    if _proxy_cycle is None:
        _init_proxy_rotation(username)

    tor_enabled = get_user_setting(username, "tor_enabled")
    if tor_enabled and tor_enabled.lower() == "true":
        tor_proxy = "socks5h://127.0.0.1:9050"
        return {"http": tor_proxy, "https": tor_proxy}

    try:
        if _proxy_cycle:
            proxy_url = next(_proxy_cycle)
            if proxy_url:
                return {"http": proxy_url, "https": proxy_url}
    except StopIteration:
        _init_proxy_rotation(username)

    return None


# ==============================================
# 🧩 CABECERAS Y UTILIDADES
# ==============================================
def random_headers():
    """Genera cabeceras HTTP realistas y aleatorias."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": random.choice(["es-ES,es;q=0.9", "en-US,en;q=0.8"]),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Connection": "keep-alive"
    }


def is_blocked_response(resp: requests.Response) -> bool:
    """Detecta si una respuesta indica bloqueo o rate-limit."""
    if not resp:
        return True
    if resp.status_code in [403, 429, 503]:
        return True
    text = resp.text.lower()[:2000]
    return any(p in text for p in BLOCK_PATTERNS)


# ==============================================
# 🔐 SAFE REQUEST (core)
# ==============================================
def safe_request(
    url: str,
    username: str = None,
    params=None,
    headers=None,
    timeout: int = 15,
    max_retries: int = 4,
    allow_tor_fallback: bool = True
) -> requests.Response | None:
    """
    Realiza una petición HTTP segura con rotación de UA, proxies y detección de bloqueos.
    Usa automáticamente Tor si se activa 'tor_enabled' o se agotan los proxies.
    """
    headers = headers or random_headers()
    proxies = get_next_proxy(username) if username else None

    for attempt in range(1, max_retries + 1):
        try:
            sleep_time = random.uniform(0.6, 2.8)
            time.sleep(sleep_time)
            logger.debug(f"[AntiBot] Intento {attempt}/{max_retries} → {url}")

            resp = requests.get(url, headers=headers, params=params, proxies=proxies, timeout=timeout)

            if is_blocked_response(resp):
                logger.warning(f"[AntiBot] Bloqueo detectado ({resp.status_code}) - cambiando proxy...")
                proxies = get_next_proxy(username)
                continue

            if resp.status_code == 200:
                return resp

        except Exception as e:
            logger.warning(f"[AntiBot] Error en intento {attempt}: {e}")
            proxies = get_next_proxy(username)
            time.sleep(random.uniform(1.5, 3.5))

    # fallback a Tor
    if allow_tor_fallback:
        tor_enabled = get_user_setting(username, "tor_enabled")
        if tor_enabled and tor_enabled.lower() == "true":
            logger.warning("[AntiBot] Reintentando vía Tor...")
            try:
                tor_proxy = {"http": "socks5h://127.0.0.1:9050", "https": "socks5h://127.0.0.1:9050"}
                headers = random_headers()
                resp = requests.get(url, headers=headers, params=params, proxies=tor_proxy, timeout=timeout)
                if resp.status_code == 200:
                    logger.info("[AntiBot] Fallback Tor exitoso.")
                    return resp
            except Exception as e:
                logger.error(f"[AntiBot] Fallback Tor fallido: {e}")

    logger.error(f"[AntiBot] Fallo total tras {max_retries} intentos en {url}")
    return None
