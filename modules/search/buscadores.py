"""
Módulo: buscadores.py
-------------------------------------
Motor de búsqueda unificado para OSINT Suite.
Integra Google API, SerpAPI, Bing, DuckDuckGo, y fallback antibot.
Redirige automáticamente hacia módulos especializados:
 - social.py → redes sociales
 - code.py → repositorios de código
 - pastes.py → filtraciones
 - docs.py → documentos públicos

Devuelve resultados normalizados con estructura:
{
    "title": "...",
    "link": "...",
    "snippet": "...",
    "source": "..."
}
"""

import requests
import random
import time
from core.config import get_user_setting
from utils.logger import logger

# Import diferido de módulos especializados (evita bucles circulares)
from modules.search.pastes import search_pastes
from modules.search.social import search_social
from modules.search.code import search_code
from modules.search.docs import search_docs


# ==========================================================
# 🔹 Función principal
# ==========================================================
def search_general(query: str, username: str, engine: str = "auto", max_results: int = 15) -> list:
    """
    Busca en múltiples motores (Google, Bing, DDG, SerpAPI, fallback antibot).
    Llama automáticamente a los módulos especializados si detecta patrones conocidos.
    """
    results = []

    # --- Redirecciones automáticas ---
    qlower = query.lower()
    if any(x in qlower for x in ["pastebin", "ghostbin", "hastebin", "pastes", "leak", "breach"]):
        return search_pastes(query, username, max_results)

    if any(x in qlower for x in ["twitter", "linkedin", "facebook", "instagram", "tiktok", "social", "threads"]):
        return search_social(query, username, max_results)

    if any(x in qlower for x in ["github", "gitlab", "bitbucket", "sourcecode", "repo", "dev", "programming"]):
        return search_code(query, username, max_results)

    if any(x in qlower for x in ["filetype", "pdf", "docx", "xlsx", "ppt", "pptx", "txt", ".pdf", ".doc"]):
        return search_docs(query, username, max_results)

    # --- Selección del motor general ---
    try:
        if engine == "auto":
            serp_key = get_user_setting(username, "serpapi")
            google_key = get_user_setting(username, "google_api_key")
            google_cx = get_user_setting(username, "google_cse_cx")

            if serp_key:
                engine = "serpapi"
            elif google_key and google_cx:
                engine = "google"
            else:
                engine = "duckduckgo"

        if engine == "serpapi":
            results = _search_serpapi(query, username, max_results)
        elif engine == "google":
            results = _search_google(query, username, max_results)
        elif engine == "bing":
            results = _search_bing(query, username, max_results)
        elif engine == "duckduckgo":
            results = _search_duckduckgo(query, max_results)
        else:
            results = _search_antibot(query, max_results)

    except Exception as e:
        logger.exception(f"[search_general] Error buscando '{query}': {e}")

    # --- Fallback automático ---
    if not results:
        logger.warning(f"[search_general] No se obtuvieron resultados, usando fallback antibot...")
        results = _search_antibot(query, max_results)

    logger.info(f"[OSINT] {len(results)} resultados obtenidos para '{query}' ({engine})")
    return results


# ==========================================================
# 🔹 SERPAPI (Google)
# ==========================================================
def _search_serpapi(query: str, username: str, max_results: int = 10) -> list:
    key = get_user_setting(username, "serpapi")
    if not key:
        logger.warning(f"[serpapi] No hay clave API configurada.")
        return []

    url = "https://serpapi.com/search.json"
    params = {"engine": "google", "q": query, "num": max_results, "api_key": key}

    try:
        r = requests.get(url, params=params, timeout=20)
        if r.status_code != 200:
            logger.warning(f"[serpapi] Respuesta {r.status_code}: {r.text[:120]}")
            return []

        data = r.json()
        organic = data.get("organic_results", [])
        results = [
            {"title": i.get("title"), "link": i.get("link"), "snippet": i.get("snippet"), "source": "serpapi"}
            for i in organic
        ]
        return results

    except Exception as e:
        logger.exception(f"[serpapi] Error ejecutando búsqueda: {e}")
        return []


# ==========================================================
# 🔹 Google Custom Search API
# ==========================================================
def _search_google(query: str, username: str, max_results: int = 10) -> list:
    key = get_user_setting(username, "google_api_key")
    cx = get_user_setting(username, "google_cse_cx")

    if not key or not cx:
        logger.warning("[google_api] Clave o CX no configurado.")
        return []

    url = "https://www.googleapis.com/customsearch/v1"
    params = {"q": query, "key": key, "cx": cx, "num": min(max_results, 10)}

    try:
        r = requests.get(url, params=params, timeout=20)
        if r.status_code != 200:
            logger.warning(f"[google_api] Código {r.status_code}: {r.text[:100]}")
            return []

        data = r.json()
        items = data.get("items", [])
        results = [
            {"title": i.get("title"), "link": i.get("link"), "snippet": i.get("snippet"), "source": "google"}
            for i in items
        ]
        return results

    except Exception as e:
        logger.exception(f"[google_api] Error: {e}")
        return []


# ==========================================================
# 🔹 Bing Web Search (requiere clave)
# ==========================================================
def _search_bing(query: str, username: str, max_results: int = 10) -> list:
    key = get_user_setting(username, "bing_api_key")
    if not key:
        logger.warning("[bing] No hay clave configurada.")
        return []

    url = "https://api.bing.microsoft.com/v7.0/search"
    headers = {"Ocp-Apim-Subscription-Key": key}
    params = {"q": query, "count": max_results}

    try:
        r = requests.get(url, headers=headers, params=params, timeout=20)
        if r.status_code != 200:
            logger.warning(f"[bing] Código {r.status_code}: {r.text[:100]}")
            return []

        data = r.json()
        items = data.get("webPages", {}).get("value", [])
        results = [
            {"title": i.get("name"), "link": i.get("url"), "snippet": i.get("snippet"), "source": "bing"}
            for i in items
        ]
        return results

    except Exception as e:
        logger.exception(f"[bing] Error: {e}")
        return []


# ==========================================================
# 🔹 DuckDuckGo (sin clave)
# ==========================================================
def _search_duckduckgo(query: str, max_results: int = 10) -> list:
    url = "https://api.duckduckgo.com/"
    params = {"q": query, "format": "json", "no_redirect": 1, "no_html": 1}

    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            return []

        data = r.json()
        results = []
        for topic in data.get("RelatedTopics", []):
            if "Text" in topic and "FirstURL" in topic:
                results.append({
                    "title": topic["Text"],
                    "link": topic["FirstURL"],
                    "snippet": topic.get("Result", ""),
                    "source": "duckduckgo"
                })

        return results[:max_results]

    except Exception as e:
        logger.warning(f"[duckduckgo] Error: {e}")
        return []


# ==========================================================
# 🔹 Fallback Antibot (scraping ligero)
# ==========================================================
def _search_antibot(query: str, max_results: int = 10) -> list:
    """
    Scraper de fallback simple con rotación de User-Agents y delays.
    Usa DuckDuckGo HTML público (sin API).
    """
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64)"
    ]

    headers = {"User-Agent": random.choice(user_agents)}
    url = f"https://html.duckduckgo.com/html/?q={query}"

    try:
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code != 200:
            logger.warning(f"[antibot] Código {r.status_code}")
            return []

        links = []
        for line in r.text.split("\n"):
            if 'href="' in line and "duckduckgo.com" not in line:
                start = line.find('href="') + 6
                end = line.find('"', start)
                link = line[start:end]
                if link.startswith("http") and link not in links:
                    links.append(link)
            if len(links) >= max_results:
                break

        results = [{"title": f"Resultado {i+1}", "link": l, "snippet": "", "source": "antibot"} for i, l in enumerate(links)]
        time.sleep(random.uniform(0.5, 1.5))
        return results

    except Exception as e:
        logger.exception(f"[antibot] Error scraping: {e}")
        return []
