"""
Interfaz gráfica del módulo de enriquecimiento automático de entidades.
Permite al usuario ejecutar análisis OSINT sobre una persona, correo o dominio
y visualizar los resultados de forma agrupada, con opciones de gestión.
"""

import streamlit as st
from core import enrichment
from core.database import get_session
from core.entities import User, SearchLog
from modules.relations.utils import add_relation
from utils.logger import logger
from sqlmodel import select
from datetime import datetime
from collections import defaultdict
import json
from modules.ai.semantic_enricher import analyze_text_with_ai


def run(entity_type: str, entity_value: str, extra_data: dict = None):
    """
    Ejecuta el flujo de enriquecimiento desde la interfaz Streamlit.
    """
    user = st.session_state.get("user")
    if not user:
        st.warning("⚠️ Debes iniciar sesión para acceder a esta función.")
        st.stop()
    # `user` se almacena como un diccionario en session_state (ver core.auth.login_user)
    # Extraemos los campos primitivos en lugar de acceder como atributos
    try:
        username = user["username"]
        user_id = user["id"]
    except Exception:
        # Si el formato es distinto, hacemos un intento de asignación
        username = user.get("username") if isinstance(user, dict) else None
        user_id = user.get("id") if isinstance(user, dict) else None

    st.markdown("## 🧠 Enriquecimiento automático")
    st.write(f"Usuario activo: **{username}**")
    st.info(f"Iniciando enriquecimiento de **{entity_type}**: `{entity_value}`")
    st.markdown("---")

    # Botón de ejecución
    if st.button("🚀 Ejecutar enriquecimiento", key=f"start_enrich_{entity_value}"):
        progress = st.progress(0)
        status_text = st.empty()

        try:
            # === 1️⃣ Ejecutar enriquecimiento según tipo ===
            status_text.text("🔍 Analizando fuente principal...")
            if entity_type == "person":
                results = enrichment.enrich_person(username, extra_data or {"name": entity_value})
            elif entity_type == "email":
                results = enrichment.enrich_email(username, entity_value)
            elif entity_type == "domain":
                results = enrichment.enrich_domain(username, entity_value)
            else:
                st.error(f"Tipo de entidad desconocido: {entity_type}")
                return

            if not results:
                st.warning("⚠️ No se encontraron resultados relevantes.")
                return

            progress.progress(70)
            status_text.text("🧩 Procesando resultados...")
            st.success(f"✅ Enriquecimiento completado ({len(results)} fuentes).")

            # === 2️⃣ Agrupar resultados ===
            grouped = defaultdict(list)
            for r in results:
                cat = getattr(r, "category", "otros") or "otros"
                grouped[cat].append(r)

            st.subheader("📋 Resultados agrupados por categoría")
            progress.progress(90)

            # === 3️⃣ Mostrar tarjetas ===
            for category, items in grouped.items():
                emoji = _emoji_for_category(category)
                with st.expander(f"{emoji} {category.upper()} — {len(items)} resultados", expanded=False):
                    for idx, r in enumerate(items, start=1):
                        _render_result_card(user_id, entity_type, entity_value, r, idx)

            # === 4️⃣ Eliminar todos ===
            st.markdown("---")
            if st.button("❌ Eliminar todos los resultados de este enriquecimiento"):
                _delete_all_results(user_id, entity_value)
                st.warning("Todos los resultados del enriquecimiento fueron eliminados.")
                st.rerun()

        except Exception as e:
            logger.exception(f"[auto_enrich_ui] Error durante el enriquecimiento: {e}")
            st.error(f"❌ Error durante el enriquecimiento: {e}")

        finally:
            progress.progress(100)
            status_text.empty()

    else:
        st.info("Haz clic en **🚀 Ejecutar enriquecimiento** para comenzar el análisis.")


# ======================================================
# 🔧 FUNCIONES AUXILIARES
# ======================================================

def _render_result_card(user_id: int, entity_type: str, entity_value: str, r, idx: int):
    """Renderiza una tarjeta de resultado enriquecido."""
    data = getattr(r, "data", None)
    if isinstance(r, dict):
        data = r
    elif not isinstance(data, dict):
        data = {}

    source = getattr(r, "source", "desconocido")
    category = getattr(r, "category", "sin categoría")
    ts = getattr(r, "timestamp", datetime.utcnow())

    st.markdown(f"#### 🧩 {source}")
    st.caption(f"{ts.strftime('%Y-%m-%d %H:%M:%S')} — {category}")

    snippet = json.dumps(data, ensure_ascii=False, indent=2)[:300]
    st.code(snippet + "...", language="json")

    c1, c2, c3 = st.columns([1, 1, 1])
    if c1.button("📁 Ver completo", key=f"show_{idx}_{source}"):
        st.json(data)
    if c2.button("📊 Añadir al grafo", key=f"add_{idx}_{source}"):
        # Para añadir relaciones al grafo utilizamos el nombre de usuario
        # en lugar del identificador numérico, ya que add_relation acepta username
        user = st.session_state.get("user", {})
        username = user.get("username") if isinstance(user, dict) else None
        _auto_add_relations(username, entity_type, entity_value, data, source)
        st.success("Relaciones añadidas al grafo.")
    if c3.button("🗑️ Eliminar", key=f"del_{idx}_{source}"):
        _delete_result(user_id, entity_value, source)
        st.info(f"Resultado de {source} eliminado.")
        st.rerun()

    _persist_result(user_id, entity_type, entity_value, r)
    st.markdown("---")


def _persist_result(user_id: int, entity_type: str, entity_value: str, result):
    """Guarda el resultado del enriquecimiento en SearchLog."""
    try:
        with get_session() as session:
            payload = (
                result.to_dict() if hasattr(result, "to_dict")
                else result if isinstance(result, dict)
                else {}
            )
            log = SearchLog(
                query=f"enrich:{entity_type}:{entity_value}:{payload.get('source', '')}",
                result=json.dumps(payload, ensure_ascii=False),
                user_id=user_id,
                type="enrich",
                created_at=datetime.utcnow()
            )
            session.add(log)
            session.commit()
    except Exception as e:
        logger.exception(f"Error guardando resultado de enrich: {e}")


def _delete_result(user_id: int, entity_value: str, source: str):
    """Elimina un resultado individual del SearchLog."""
    try:
        with get_session() as session:
            logs = session.exec(
                select(SearchLog)
                .where(SearchLog.user_id == user_id)
                .where(SearchLog.query.contains(f"{entity_value}:{source}"))
            ).all()
            for log in logs:
                session.delete(log)
            session.commit()
    except Exception as e:
        logger.exception(f"Error eliminando resultado individual de enrich: {e}")


def _delete_all_results(user_id: int, entity_value: str):
    """Elimina todos los resultados de enriquecimiento asociados a una entidad."""
    try:
        with get_session() as session:
            logs = session.exec(
                select(SearchLog)
                .where(SearchLog.user_id == user_id)
                .where(SearchLog.query.contains("enrich:"))
                .where(SearchLog.query.contains(entity_value))
            ).all()
            for log in logs:
                session.delete(log)
            session.commit()
    except Exception as e:
        logger.exception(f"Error eliminando todos los resultados de enrich: {e}")


def _auto_add_relations(username: str, entity_type: str, entity_value: str, data: dict, source: str):
    """Detecta datos relevantes en los resultados y los añade al grafo."""
    try:
        if not username:
            return
        origin_id = f"{entity_type}:{entity_value}"

        # URLs
        for key in ("url", "link", "website"):
            val = data.get(key)
            if isinstance(val, str) and val.startswith("http"):
                add_relation(username, origin_id, f"url:{val}", f"found_by:{source}")

        # Dominios
        domain_name = data.get("domainName")
        if domain_name:
            add_relation(username, origin_id, f"domain:{domain_name}", "related_domain")

        # Breaches
        breaches = data.get("breaches")
        if isinstance(breaches, list):
            for b in breaches:
                add_relation(username, origin_id, f"breach:{b}", "pwned_in")

    except Exception as e:
        logger.exception(f"Error añadiendo relaciones automáticas: {e}")


def _emoji_for_category(category: str) -> str:
    """Asigna un emoji representativo según la categoría."""
    mapping = {
        "search": "🔎",
        "mentions": "💬",
        "data_breaches": "🔐",
        "domain": "🌐",
        "whois": "🌍",
        "documents": "📄",
        "files": "🗂️",
        "social": "👤",
        "tech": "⚙️",
        "otros": "🧩",
    }
    for k, emoji in mapping.items():
        if k in category.lower():
            return emoji
    return "🧩"
