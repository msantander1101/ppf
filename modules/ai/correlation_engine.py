# modules/ai/correlation_engine.py
"""
Motor de correlación automática entre personas usando IA y heurísticas.
- Detecta coincidencias entre entidades (emails, dominios, leaks, perfiles).
- Llama a LLM para validar si el vínculo parece real o accidental.
- Inserta relaciones automáticas en el grafo (Relation).
"""

import os
import re
from typing import List, Dict
from datetime import datetime
from sqlmodel import select
from openai import OpenAI

from core.database import get_session
from core.entities import Person, Email, Profile, Relation, SearchLog
from utils.logger import logger

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ========================
# 🧩 Capa Heurística Base
# ========================
def _extract_domain(email: str) -> str:
    m = re.search(r"@([A-Za-z0-9.-]+)", email or "")
    return m.group(1).lower() if m else ""


def _heuristic_match(p1, p2) -> List[Dict]:
    """
    Detecta coincidencias directas entre dos personas.
    Devuelve lista de posibles relaciones detectadas.
    """
    rels = []

    # Emails compartidos
    emails1 = {e.address.lower() for e in p1.emails or []}
    emails2 = {e.address.lower() for e in p2.emails or []}
    shared_emails = emails1 & emails2
    for e in shared_emails:
        rels.append({"relation": "same_email", "evidence": e})

    # Dominio común
    domains1 = {_extract_domain(e) for e in emails1 if "@" in e}
    domains2 = {_extract_domain(e) for e in emails2 if "@" in e}
    shared_domains = domains1 & domains2
    for d in shared_domains:
        rels.append({"relation": "same_email_domain", "evidence": d})

    # Perfiles similares
    profs1 = {f"{p.platform}:{p.handle}".lower() for p in p1.profiles or []}
    profs2 = {f"{p.platform}:{p.handle}".lower() for p in p2.profiles or []}
    shared_profiles = profs1 & profs2
    for p in shared_profiles:
        rels.append({"relation": "same_profile", "evidence": p})

    return rels


# ========================
# 🧠 Capa IA (validación semántica)
# ========================
def _get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Falta la variable OPENAI_API_KEY.")
    return OpenAI(api_key=api_key)


def _validate_with_ai(person_a, person_b, raw_relations: List[Dict]) -> Dict:
    """
    Llama a la IA para evaluar si el vínculo es real o coincidencia.
    """
    if not raw_relations:
        return {"confidence": 0.0, "ai_relation": None}

    prompt = f"""
Analiza si las siguientes coincidencias sugieren que las dos personas podrían estar relacionadas (misma identidad, colaborador, vínculo profesional, etc).

Persona A:
{person_a.name}
Emails: {[e.address for e in person_a.emails or []]}
Perfiles: {[f"{p.platform}:{p.handle}" for p in person_a.profiles or []]}

Persona B:
{person_b.name}
Emails: {[e.address for e in person_b.emails or []]}
Perfiles: {[f"{p.platform}:{p.handle}" for p in person_b.profiles or []]}

Coincidencias detectadas:
{raw_relations}

Devuelve un JSON válido con:
{{
  "confidence": 0-1,
  "relation_type": "same_identity" | "possible_linked_to" | "coincidence"
}}
"""
    try:
        client = _get_openai_client()
        resp = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": "Eres un analista OSINT experto en correlaciones de identidad."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        import json
        out = resp.choices[0].message.content.strip()
        data = json.loads(out)
        return data
    except Exception as e:
        logger.warning(f"[correlation_engine] Error IA: {e}")
        return {"confidence": 0.3, "relation_type": "possible_linked_to"}


# ========================
# 🔗 Motor principal
# ========================
def run_correlation(username: str | None = None, min_confidence: float = 0.5):
    """
    Compara todas las personas registradas y crea relaciones sugeridas
    si la IA o heurística las confirma.
    """
    with get_session() as session:
        persons = session.exec(select(Person)).all()

        logger.info(f"[correlation_engine] Analizando correlaciones entre {len(persons)} personas...")
        results = []

        for i, p1 in enumerate(persons):
            for p2 in persons[i + 1:]:
                raw_rels = _heuristic_match(p1, p2)
                if not raw_rels:
                    continue

                ai_eval = _validate_with_ai(p1, p2, raw_rels)
                conf = ai_eval.get("confidence", 0)
                rtype = ai_eval.get("relation_type", "possible_linked_to")

                if conf >= min_confidence:
                    rel = Relation(
                        source_id=f"person:{p1.id}",
                        target_id=f"person:{p2.id}",
                        relation=rtype,
                        confidence=conf,
                        created_at=datetime.utcnow()
                    )
                    session.add(rel)
                    results.append({
                        "source": p1.name,
                        "target": p2.name,
                        "relation": rtype,
                        "confidence": conf,
                        "evidence": raw_rels
                    })
                    logger.info(f"[correlation_engine] Relación detectada: {p1.name} ↔ {p2.name} ({rtype}, {conf:.2f})")

        session.commit()

    return results
