# modules/ai/dork_generator.py
"""
Generador de dorks dinámicos usando IA para búsquedas OSINT.
El modelo crea consultas optimizadas según el tipo de entidad.
"""

import os
from openai import OpenAI
from utils.logger import logger

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def _get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Falta la variable OPENAI_API_KEY.")
    return OpenAI(api_key=api_key)


def generate_dorks(entity_type: str, query: str, context: str | None = None) -> dict:
    """
    Genera dorks de Google, Bing y DuckDuckGo adaptados al tipo de entidad.
    """
    prompt = f"""
Eres un analista OSINT experto. Tu tarea es crear dorks específicos para buscar información
sobre el siguiente tipo de entidad:

Entidad: {query}
Tipo: {entity_type}
Contexto adicional: {context or "N/A"}

Genera 3 dorks por buscador (Google, Bing y DuckDuckGo). 
El objetivo es encontrar huella digital, filtraciones, redes sociales y documentos relacionados.

Devuelve un JSON válido con la siguiente estructura:
{{
  "google": ["dork1", "dork2", "dork3"],
  "bing": ["dork1", "dork2", "dork3"],
  "duckduckgo": ["dork1", "dork2", "dork3"]
}}
"""
    try:
        client = _get_openai_client()
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": "Eres un experto en OSINT, preciso y técnico."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
        )

        import json
        content = response.choices[0].message.content.strip()
        return json.loads(content)

    except Exception as e:
        logger.warning(f"[dork_generator] Error generando dorks: {e}")
        return {
            "google": [f'"{query}" site:linkedin.com OR site:twitter.com'],
            "bing": [f'"{query}" filetype:pdf OR filetype:xlsx'],
            "duckduckgo": [f'"{query}" site:pastebin.com OR site:github.com'],
        }
