"""
Módulo: intel_assistant.py
-------------------------------------
Análisis avanzado con IA de resultados OSINT.
Compatibilidad con:
 - OpenAI GPT (vía API key)
 - Servidor local personalizado (FastAPI / Flask / etc.)
 - Modelos locales Ollama o LM Studio

Elige automáticamente la mejor opción según configuración del usuario.
"""

import requests
import json
from core.config import get_user_setting
from utils.logger import logger


# ==========================================================
# 🔹 Función principal
# ==========================================================
def analyze_results_with_ai(target: str, results: list, username: str) -> str:
    """
    Analiza los resultados OSINT usando IA (OpenAI, servidor local o Ollama).
    Retorna un texto con el informe OSINT generado.
    """
    if not results:
        return "⚠️ No hay resultados para analizar."

    # Recuperar configuración del usuario
    openai_key = get_user_setting(username, "openai_api_key")
    local_ai_url = get_user_setting(username, "local_ai_url") or "http://localhost:8000/api/ai/analyze"
    ollama_model = get_user_setting(username, "ollama_model") or "llama3"

    # Crear prompt
    sources = "\n".join([
        f"- {r.get('title', 'Sin título')} ({r.get('source', 'desconocido')}) → {r.get('link', '')}"
        for r in results
    ])[:8000]

    prompt = f"""
Eres un analista de inteligencia OSINT. Analiza toda la información recopilada sobre **{target}** y genera un informe estructurado:

1️⃣ **Resumen general de hallazgos**
2️⃣ **Correlaciones relevantes entre fuentes**
3️⃣ **Posibles exposiciones o fugas de datos**
4️⃣ **Indicadores de riesgo o reputación**
5️⃣ **Conclusiones y recomendaciones**

Fuentes analizadas:
{sources}
"""

    # ==========================================================
    # 🔹 Opción 1: OpenAI (si hay clave)
    # ==========================================================
    if openai_key:
        try:
            import openai
            openai.api_key = openai_key
            completion = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Eres un analista experto en inteligencia OSINT."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=900
            )
            return completion["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"[intel_assistant] Error con OpenAI: {e}")

    # ==========================================================
    # 🔹 Opción 2: Servidor local (FastAPI / Flask)
    # ==========================================================
    try:
        r = requests.post(local_ai_url, json={"prompt": prompt, "target": target}, timeout=60)
        if r.status_code == 200:
            data = r.json()
            if "response" in data:
                return data["response"].strip()
            elif isinstance(data, str):
                return data.strip()
        else:
            logger.warning(f"[intel_assistant] Servidor local devolvió {r.status_code}: {r.text[:200]}")

    except requests.exceptions.ConnectionError:
        logger.warning("[intel_assistant] No se pudo conectar al servidor local de IA.")
    except Exception as e:
        logger.warning(f"[intel_assistant] Error servidor local: {e}")

    # ==========================================================
    # 🔹 Opción 3: Ollama / LM Studio (API local HTTP)
    # ==========================================================
    try:
        r = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": ollama_model, "prompt": prompt},
            timeout=90
        )
        if r.status_code == 200:
            # Ollama responde con streaming; concatenamos el texto
            text = ""
            for line in r.text.splitlines():
                try:
                    data = json.loads(line)
                    if "response" in data:
                        text += data["response"]
                except json.JSONDecodeError:
                    continue
            if text.strip():
                return text.strip()
        else:
            logger.warning(f"[intel_assistant] Ollama devolvió {r.status_code}")
    except requests.exceptions.ConnectionError:
        logger.warning("[intel_assistant] Ollama no está en ejecución en localhost:11434.")
    except Exception as e:
        logger.warning(f"[intel_assistant] Error con Ollama: {e}")

    # ==========================================================
    # 🔹 Fallback
    # ==========================================================
    return (
        "⚠️ No se pudo ejecutar el análisis con IA.\n\n"
        "Verifica tu configuración en **Configuración → Claves API y Servicios Externos**:\n"
        "- Clave de OpenAI (`openai_api_key`)\n"
        "- Servidor local (`local_ai_url`)\n"
        "- Modelo Ollama (`ollama_model`)\n"
    )
