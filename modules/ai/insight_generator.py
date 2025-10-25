# modules/ai/insight_generator.py
"""
Generador de informes analíticos con IA para una persona OSINT.
- Recolecta contexto (emails, perfiles, relaciones, logs, leaks)
- Llama a un LLM (OpenAI) y devuelve un texto resumido y accionable.
"""

import os
import json
from datetime import datetime, timedelta

from openai import OpenAI

from sqlmodel import select
from core.database import get_session
from core.entities import Person, Email, Profile, Relation, SearchLog
from utils.logger import logger

# === Config ===
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _get_openai_client(username: str | None = None):
    """
    Recupera la API key desde:
      1) Variable de entorno OPENAI_API_KEY
      2) (opcional) futura integración con settings por usuario.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Falta OPENAI_API_KEY. Define la variable de entorno con tu clave de OpenAI."
        )
    return OpenAI(api_key=api_key)


def _collect_person_context(person_id: int) -> dict:
    """
    Reúne el contexto de una persona: emails, perfiles, relaciones y últimos logs.
    Limita los logs a los últimos 60 días para no sobrecargar el prompt.
    """
    ctx = {
        "person": None,
        "emails": [],
        "profiles": [],
        "relations": [],
        "recent_logs": [],
        "possible_leaks": []
    }

    with get_session() as session:
        person = session.get(Person, person_id)
        if not person:
            raise ValueError(f"Persona con id={person_id} no encontrada")

        ctx["person"] = {
            "id": person.id,
            "name": person.name,
            "notes": person.notes or "",
            "created_at": person.created_at.strftime("%Y-%m-%d %H:%M:%S") if person.created_at else None,
        }

        # Emails y Perfiles
        emails = session.exec(select(Email).where(Email.person_id == person_id)).all()
        profiles = session.exec(select(Profile).where(Profile.person_id == person_id)).all()

        ctx["emails"] = [{"id": e.id, "address": e.address} for e in emails]
        ctx["profiles"] = [
            {"id": p.id, "platform": p.platform, "handle": p.handle, "url": p.url} for p in profiles
        ]

        # Relaciones
        rels = session.exec(select(Relation).where(Relation.source_id == f"person:{person_id}")).all()
        ctx["relations"] = [
            {
                "id": r.id,
                "relation": r.relation,
                "target_id": r.target_id,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else None,
            }
            for r in rels
        ]

        # Logs recientes (últimos 60 días)
        cutoff = datetime.utcnow() - timedelta(days=60)
        logs = session.exec(
            select(SearchLog)
            .where(SearchLog.created_at >= cutoff)
            .order_by(SearchLog.created_at.desc())
            .limit(100)
        ).all()

        for lg in logs:
            try:
                payload = json.loads(lg.result) if isinstance(lg.result, str) else lg.result
            except Exception:
                payload = lg.result

            ctx["recent_logs"].append(
                {
                    "id": lg.id,
                    "type": lg.type,
                    "query": lg.query,
                    "created_at": lg.created_at.strftime("%Y-%m-%d %H:%M:%S") if lg.created_at else None,
                    "result_excerpt": str(payload)[:400],
                }
            )

            # Posibles leaks (heurística simple por tipo/consulta)
            if any(k in (lg.type or "") for k in ("leak", "hibp", "breach", "pastes")) or \
               ("pastebin" in (lg.query or "").lower()) or ("breach" in (lg.query or "").lower()):
                ctx["possible_leaks"].append(
                    {
                        "id": lg.id,
                        "query": lg.query,
                        "created_at": lg.created_at.strftime("%Y-%m-%d %H:%M:%S") if lg.created_at else None,
                    }
                )

    return ctx


def _build_prompt(context: dict) -> str:
    """
    Ensambla un prompt claro y conciso para el modelo.
    Deja instrucciones para devolver un informe operativo.
    """
    person = context.get("person", {})
    emails = context.get("emails", [])
    profiles = context.get("profiles", [])
    relations = context.get("relations", [])
    leaks = context.get("possible_leaks", [])
    recent_logs = context.get("recent_logs", [])

    # Reducimos ruido: solo metemos extractos resumidos
    safe_logs = [
        {"type": l["type"], "query": l["query"], "created_at": l["created_at"], "result_excerpt": l["result_excerpt"]}
        for l in recent_logs[:15]
    ]

    prompt = f"""
Eres un analista OSINT senior. Debes generar un informe breve, claro y accionable del perfil de esta persona.

## Persona
{json.dumps(person, ensure_ascii=False, indent=2)}

## Emails
{json.dumps(emails, ensure_ascii=False, indent=2)}

## Perfiles
{json.dumps(profiles, ensure_ascii=False, indent=2)}

## Relaciones
{json.dumps(relations, ensure_ascii=False, indent=2)}

## Posibles Leaks (heurística)
{json.dumps(leaks, ensure_ascii=False, indent=2)}

## Extractos de Actividad (últimos 60 días)
{json.dumps(safe_logs, ensure_ascii=False, indent=2)}

### Instrucciones
- Sé conciso (máx. ~250-300 palabras).
- Estructura en secciones: 
  1) Resumen Ejecutivo 
  2) Evidencias Clave 
  3) Riesgos y Exposición 
  4) Recomendaciones de Próximos Pasos (con bullets).
- No inventes datos: si falta evidencia, dilo.
- Usa un tono profesional y operativo (estilo informe).
"""
    return prompt


def generate_person_insight(person_id: int, username: str | None = None, model: str | None = None) -> str:
    """
    Punto de entrada principal:
      - Construye el contexto
      - Llama al LLM
      - Devuelve un informe en texto (markdown)
    """
    try:
        ctx = _collect_person_context(person_id)
        prompt = _build_prompt(ctx)

        client = _get_openai_client(username)
        model_name = model or DEFAULT_MODEL

        resp = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "Eres un analista OSINT experto, preciso y conciso."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        text = resp.choices[0].message.content.strip()
        return text

    except Exception as e:
        logger.exception(f"[insight_generator] Error generando informe IA: {e}")
        raise
