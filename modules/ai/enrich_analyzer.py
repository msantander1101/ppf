# modules/ai/enrich_analyzer.py
import openai
from core.config import get_user_setting
from utils.logger import logger


def enrich_text_with_ai(username: str, text: str) -> str:
    """Usa la IA para generar un resumen o análisis contextual."""
    api_key = get_user_setting(username, "openai_api_key")
    if not api_key:
        return "⚠️ No hay clave API configurada para IA."

    openai.api_key = api_key
    prompt = f"Analiza este texto desde una perspectiva OSINT, resumiendo hallazgos clave y posibles riesgos:\n\n{text}"

    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        return resp["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"[AI] Error al enriquecer texto: {e}")
        return "❌ Error al procesar IA"
