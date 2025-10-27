"""
Módulo: code.py
-------------------------------------
Búsqueda OSINT en plataformas de código:
GitHub, GitLab, Bitbucket, Gist, etc.
Detecta huellas de desarrolladores, fugas de credenciales o metadatos.
"""

import re
import requests
from core.config import get_user_setting
from utils.logger import logger


CODE_PLATFORMS = [
    "github.com",
    "gitlab.com",
    "bitbucket.org",
    "gist.github.com",
    "sourceforge.net",
    "pastebin.com"
]


# ==========================================================
# 🔹 Búsqueda principal
# ==========================================================
def search_code(query: str, username: str, max_results: int = 15) -> list:
    """
    Busca en plataformas de código fuente cualquier rastro del nombre, alias o email.
    """
    serp_key = get_user_setting(username, "serpapi")
    google_key = get_user_setting(username, "google_api_key")
    google_cx = get_user_setting(username, "google_cse_cx")

    dork = _build_code_dork(query)

    try:
        if serp_key:
            results = _search_serpapi_code(dork, serp_key, max_results)
        elif google_key and google_cx:
            results = _search_google_code(dork, google_key, google_cx, max_results)
        else:
            results = _search_scrape_code(dork, max_results)
    except Exception as e:
        logger.exception(f"[code] Error general: {e}")
        results = []

    logger.info(f"[code] {len(results)} resultados para '{query}'")
    return results


# ==========================================================
# 🔹 Dork builder
# ==========================================================
def _build_code_dork(query: str) -> str:
    """
    Genera un dork adaptado a plataformas de código.
    """
    q = query.strip().replace('"', '')
    dork = f'"{q}" (site:github.com OR site:gitlab.com OR site:bitbucket.org OR site:gist.github.com)'
    return dork


# ==========================================================
# 🔹 SerpAPI
# ==========================================================
def _search_serpapi_code(query: str, api_key: str, max_results: int = 15) -> list:
    url = "https://serpapi.com/search.json"
    params = {"engine": "google", "q": query, "num": max_results, "api_key": api_key}

    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            logger.warning(f"[code:serpapi] Código {r.status_code}: {r.text[:80]}")
            return []

        data = r.json()
        organic = data.get("organic_results", [])
        results = []
        for item in organic:
            snippet = item.get("snippet", "")
            link = item.get("link", "")
            info = _detect_code_signals(snippet)
            results.append({
                "title": item.get("title", "Repositorio encontrado"),
                "link": link,
                "snippet": f"{snippet} | {info}".strip(),
                "source": "code-serpapi"
            })
        return results
    except Exception as e:
        logger.exception(f"[code:serpapi] Error: {e}")
        return []


# ==========================================================
# 🔹 Google API
# ==========================================================
def _search_google_code(query: str, key: str, cx: str, max_results: int = 10) -> list:
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"q": query, "key": key, "cx": cx, "num": min(max_results, 10)}

    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            logger.warning(f"[code:google] Código {r.status_code}")
            return []
        data = r.json()
        items = data.get("items", [])
        results = []
        for i in items:
            snippet = i.get("snippet", "")
            link = i.get("link", "")
            info = _detect_code_signals(snippet)
            results.append({
                "title": i.get("title", "Código encontrado"),
                "link": link,
                "snippet": f"{snippet} | {info}".strip(),
                "source": "code-google"
            })
        return results
    except Exception as e:
        logger.exception(f"[code:google] Error: {e}")
        return []


# ==========================================================
# 🔹 Fallback scraper
# ==========================================================
def _search_scrape_code(query: str, max_results: int = 10) -> list:
    """
    Búsqueda en DuckDuckGo HTML sin API.
    """
    url = "https://html.duckduckgo.com/html/"
    params = {"q": query}
    headers = {"User-Agent": "Mozilla/5.0 (compatible; OSINTSuite/1.0)"}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        if r.status_code != 200:
            return []

        links = re.findall(r'href="(https?://[^"]+)"', r.text)
        code_links = [l for l in links if any(p in l for p in CODE_PLATFORMS)]

        results = []
        for i, link in enumerate(code_links[:max_results]):
            snippet = _fetch_snippet(link)
            info = _detect_code_signals(snippet)
            results.append({
                "title": f"Resultado {i+1}",
                "link": link,
                "snippet": f"{snippet[:150]} | {info}".strip(),
                "source": "code-scraper"
            })
        return results
    except Exception as e:
        logger.exception(f"[code:scrape] Error: {e}")
        return []


# ==========================================================
# 🔹 Detección de patrones sensibles en código
# ==========================================================
def _detect_code_signals(text: str) -> str:
    """
    Busca patrones comunes de datos sensibles o correos en código.
    """
    if not text:
        return ""
    matches = []
    if re.search(r"api[_-]?key", text, re.I):
        matches.append("API key detectada")
    if re.search(r"token", text, re.I):
        matches.append("Token potencial")
    if re.search(r"password|passwd", text, re.I):
        matches.append("Posible contraseña")
    if re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text):
        matches.append("Email detectado")
    return " | ".join(matches) if matches else ""


# ==========================================================
# 🔹 Fetch snippet
# ==========================================================
def _fetch_snippet(url: str) -> str:
    """
    Intenta obtener una porción del contenido del enlace.
    """
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return ""
        text = r.text
        code_sample = "\n".join(text.splitlines()[:10])
        return code_sample.strip()
    except Exception:
        return ""
