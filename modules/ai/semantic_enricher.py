# modules/ai/semantic_enricher.py
"""
Enriquecimiento semántico por IA para resultados OSINT.
- Extrae entidades (person, email, domain, org, profile, leak)
- Sugiere relaciones (source, target, relation_type)
- Resume y puntúa relevancia

Usa OpenAI si hay OPENAI_API_KEY; si no, hace fallback con regex.
"""

from typing import Dict, List
import os
import re
import json
from utils.logger import logger

# Cliente IA opcional (OpenAI). Si no hay clave, se hace fallback.
CLIENT = None
try:
    from openai import OpenAI
    if os.getenv("OPENAI_API_KEY"):
        CLIENT = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception:
    CLIENT = None


def analyze_text_with_ai(text: str) -> Dict:
    """
    Entrada: texto (título/snippet/contenido de resultado)
    Salida (dict):
      {
        "entities": [{"type": "...", "value": "..."}],
        "relations": [{"source": "...", "target": "...", "relation_type": "..."}],
        "relevance": "alta|media|baja",
        "summary": "..."
      }
    """
    text = (text or "").strip()
    if not text:
        return {
            "entities": [],
            "relations": [],
            "relevance": "baja",
            "summary": "Sin contenido para analizar."
        }

    if CLIENT is None:
        # Fallback por regex
        return _fallback_entity_detection(text)

    prompt = f"""
Eres un analista OSINT experto. Analiza el siguiente texto y devuelve SOLO un JSON válido con:
- entities: lista de objetos con 'type' en {{person, email, domain, org, profile, leak}} y 'value'
- relations: lista de objetos con 'source', 'target', 'relation_type' (ej: mentions, works_at, related_to, breach_of)
- relevance: "alta", "media" o "baja"
- summary: breve resumen (1-2 frases)

Texto:
{text}
"""

    try:
        resp = CLIENT.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "Eres un analista OSINT muy preciso y conciso."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        raw = resp.choices[0].message.content
        # El modelo debe devolver JSON. Si falla, fallback.
        data = json.loads(raw)
        # Normalización mínima
        data.setdefault("entities", [])
        data.setdefault("relations", [])
        data.setdefault("relevance", "media")
        data.setdefault("summary", "")
        return data
    except Exception as e:
        logger.warning(f"[semantic_enricher] Error IA: {e}. Usando fallback.")
        return _fallback_entity_detection(text)


def _fallback_entity_detection(text: str) -> Dict:
    entities: List[Dict] = []
    relations: List[Dict] = []

    # Emails
    for e in set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)):
        entities.append({"type": "email", "value": e})

    # Dominios (de URLs)
    for d in set(re.findall(r"https?://([\w\.-]+)", text)):
        entities.append({"type": "domain", "value": d})

    # Perfiles simples por menciones comunes
    if "github.com/" in text:
        for gh in set(re.findall(r"github\.com/([\w\-_\.]+)", text)):
            entities.append({"type": "profile", "value": f"github:{gh}"})
    if "linkedin.com/in/" in text:
        for li in set(re.findall(r"linkedin\.com/in/([\w\-_/%]+)", text)):
            entities.append({"type": "profile", "value": f"linkedin:{li}"})
    if "twitter.com/" in text or "x.com/" in text:
        for tw in set(re.findall(r"(?:twitter|x)\.com/([\w\-_\.]+)", text)):
            entities.append({"type": "profile", "value": f"twitter:{tw}"})

    # Nombres propios básicos (heurística débil)
    for n in set(re.findall(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+ [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\b", text)):
        entities.append({"type": "person", "value": n})

    # Detección de leak / breach
    if any(k in text.lower() for k in ("leak", "breach", "pwned", "passwords", "exposed data", "data breach", "pastebin")):
        entities.append({"type": "leak", "value": "possible_leak_context"})

    return {
        "entities": entities,
        "relations": relations,
        "relevance": "media" if entities else "baja",
        "summary": "Detección básica por patrones (fallback)."
    }
