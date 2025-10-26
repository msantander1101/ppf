# modules/ai/intel_assistant.py
"""
Módulo de Inteligencia Artificial (IA)
Analiza los resultados OSINT con modelos LLM para ofrecer resúmenes,
correlaciones, posibles amenazas y patrones de comportamiento.
"""

from core.config import get_user_setting
from utils.logger import logger
import openai


def analyze_results_with_ai(results: list) -> str:
    """
    Analiza una lista de resultados OSINT con IA para ofrecer
    un resumen contextual y correlaciones relevantes.
    """
    try:
        if not results:
            return "No hay resultados disponibles para analizar."

        # Intentar cargar la API key del usuario (OpenAI o equivalente)
        api_key = get_user_setting("system", "openai_api_key") or get_user_setting("admin", "openai_api_key")
        if not api_key:
            return "⚠️ No se ha configurado una clave de API para OpenAI en 'Configuración'."

        openai.api_key = api_key

        # Construir el texto base para análisis
        text_to_analyze = ""
        for r in results[:10]:  # limitar a 10 resultados por eficiencia
            title = r.get("title") or r.get("source", "")
            snippet = r.get("snippet") or str(r.get("data", ""))
            link = r.get("link", "")
            text_to_analyze += f"\n- Título: {title}\nDescripción: {snippet}\nEnlace: {link}\n"

        # Prompt de análisis inteligente
        prompt = f"""
        Eres un analista OSINT experto en inteligencia digital.
        Se te proporciona una lista de hallazgos sobre una persona.
        Tu tarea es:
        1. Identificar patrones (nombres, correos, redes, filtraciones, repositorios, etc.).
        2. Resumir las conclusiones de forma clara y profesional.
        3. Indicar si hay riesgos de seguridad o privacidad.

        Datos a analizar:
        {text_to_analyze}

        Devuelve el análisis en formato de puntos y subtítulos.
        """

        # Llamada a la API (modelo eficiente y coherente)
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un analista OSINT profesional especializado en inteligencia humana y ciberseguridad."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=700
        )

        return response["choices"][0]["message"]["content"].strip()

    except Exception as e:
        logger.error(f"[intel_assistant] Error analizando resultados con IA: {e}")
        return f"❌ Error analizando con IA: {e}"
