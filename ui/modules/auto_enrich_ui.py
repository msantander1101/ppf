# ui/modules/auto_enrich_ui.py
"""
Interfaz gráfica del módulo de enriquecimiento automático de entidades.
Permite al usuario ejecutar análisis OSINT sobre una persona, correo o dominio
y visualizar los resultados obtenidos de forma agrupada y gestionable.
"""

import streamlit as st
from core import enrichment
from utils.logger import logger
from sqlmodel import select
from core.database import get_session, SearchLog, User
from modules.relations.utils import add_relation
from datetime import datetime
import json
from collections import defaultdict


def run(username: str, entity_type: str, entity_value: str, extra_data: dict = None):
    """
    Ejecuta el flujo de enriquecimiento desde la interfaz Streamlit.
    """
    st.markdown("## 🧠 Enriquecimiento automático")
    st.write(f"Usuario activo: **{username}**")
    st.markdown("---")

    st.info(f"Iniciando enriquecimiento de **{entity_type}**: `{entity_value}`")

    # Botón de ejecución
    if st.button("🚀 Ejecutar enriquecimiento", key="start_enrich"):
        progress = st.progress(0)
        status_text = st.empty()
        results = []

        try:
            # === 1️⃣ Ejecutar enriquecimiento según tipo ===
            if entity_type == "person":
                progress.progress(10)
                status_text.text("🔍 Analizando identidad...")
                results = enrichment.enrich_person(username, extra_data or {"name": entity_value})
            elif entity_type == "email":
                progress.progress(10)
                status_text.text("📧 Analizando correo electrónico...")
                results = enrichment.enrich_email(username, entity_value)
            elif entity_type == "domain":
                progress.progress(10)
                status_text.text("🌐 Analizando dominio...")
                results = enrichment.enrich_domain(username, entity_value)
            else:
                st.error(f"Tipo de entidad desconocido: {entity_type}")
                return

            progress.progress(70)
            status_text.text("🧩 Procesando resultados...")

            if not results:
                st.warning("⚠️ No se encontraron resultados relevantes.")
                progress.progress(100)
                return

            st.success(f"✅ Enriquecimiento completado ({len(results)} fuentes).")
            progress.progress(100)
            st.markdown("---")

            # === 2️⃣ Agrupar por categoría ===
            grouped_results = defaultdict(list)
            for r in results:
                cat = getattr(r, "category", "otros") or "otros"
                grouped_results[cat].append(r)

            st.subheader("📋 Resultados agrupados por categoría")

            # === 3️⃣ Mostrar bloques por categoría ===
            for category, group in grouped_results.items():
                emoji = _emoji_for_category(category)
                with st.expander(f"{emoji} {category.upper()} — {len(group)} resultados", expanded=False):
                    for idx, r in enumerate(group, start=1):
                        _render_enrich_card(username, entity_type, entity_value, r, idx)

            # === 4️⃣ Botón eliminar todos ===
            st.markdown("---")
            if st.button("❌ Eliminar todos los resultados de este enriquecimiento"):
                _delete_all_enrich_results(username, entity_value)
                st.warning("Todos los resultados del enriquecimiento fueron eliminados.")
                st.rerun()

            logger.info(f"[auto_enrich_ui] {len(results)} resultados generados para {entity_value}")

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

def _render_enrich_card(username, entity_type, entity_value, r, idx):
    """Renderiza una tarjeta compacta de un resultado de enriquecimiento."""
    data = r.data if hasattr(r, "data") else {}
    source = getattr(r, "source", "desconocido")
    category = getattr(r, "category", "sin categoría")
    ts = getattr(r, "timestamp", datetime.utcnow())

    title = f"🧩 {source}"
    st.markdown(f"### {title}")
    st.caption(f"{ts.strftime('%Y-%m-%d %H:%M:%S')} — {category}")

    snippet = json.dumps(data, ensure_ascii=False)[:250] + "..."
    st.code(snippet, language="json")

    c1, c2, c3 = st.columns([1, 1, 1])
    if c1.button("📁 Ver completo", key=f"show_enrich_{idx}_{source}"):
        st.json(data)
    if c2.button("📊 Añadir al grafo", key=f"add_enrich_{idx}_{source}"):
        _auto_add_relations(username, entity_type, entity_value, data, source)
        st.success("Relaciones añadidas al grafo.")
    if c3.button("🗑️ Eliminar", key=f"del_enrich_{idx}_{source}"):
        _delete_enrich_result(username, entity_value, source)
        st.warning(f"Resultado de {source} eliminado.")
        st.rerun()

    st.markdown("---")
    _persist_enrich_result(username, entity_type, entity_value, r)


def _persist_enrich_result(username: str, entity_type: str, entity_value: str, result):
    """Guarda en SearchLog el resultado del enrich (result puede ser objeto o dict)."""
    try:
        with get_session() as session:
            user = session.exec(select(User).where(User.username == username)).first()
            if user:
                payload = result.to_dict() if hasattr(result, "to_dict") else (result if isinstance(result, dict) else {})
                log = SearchLog(
                    query=f"enrich:{entity_type}:{entity_value}:{payload.get('source','')}",
                    result=json.dumps(payload, ensure_ascii=False),
                    user_id=user.id,
                    type="enrich",
                    created_at=datetime.utcnow()
                )
                session.add(log)
                session.commit()
    except Exception as e:
        logger.exception(f"Error guardando resultado de enrich: {e}")


def _delete_enrich_result(username: str, entity_value: str, source: str):
    """Elimina un resultado individual del SearchLog según la fuente."""
    try:
        with get_session() as session:
            logs = session.exec(
                select(SearchLog).where(SearchLog.query.contains(f"{entity_value}:{source}"))
            ).all()
            for log in logs:
                session.delete(log)
            session.commit()
    except Exception as e:
        logger.exception(f"Error eliminando resultado individual de enrich: {e}")


def _delete_all_enrich_results(username: str, entity_value: str):
    """Elimina todos los resultados de enriquecimiento asociados a una entidad."""
    try:
        with get_session() as session:
            logs = session.exec(
                select(SearchLog)
                .where(SearchLog.query.contains("enrich:"))
                .where(SearchLog.query.contains(entity_value))
            ).all()
            for log in logs:
                session.delete(log)
            session.commit()
    except Exception as e:
        logger.exception(f"Error eliminando todos los resultados de enrich: {e}")


def _auto_add_relations(username: str, entity_type: str, entity_value: str, data: dict, source: str):
    """Detecta datos relevantes en los resultados y los añade al grafo automáticamente."""
    try:
        if not isinstance(data, dict):
            return

        origin_id = f"{entity_type}:{entity_value}"

        # URLs
        for key in ("url", "link", "website"):
            if key in data and isinstance(data[key], str) and data[key].startswith("http"):
                add_relation(username, origin_id, f"url:{data[key]}", f"found_by:{source}")

        # Dominio
        if "domainName" in data:
            add_relation(username, origin_id, f"domain:{data['domainName']}", "related_domain")

        # Breaches
        if "breaches" in data and isinstance(data["breaches"], list):
            for b in data["breaches"]:
                add_relation(username, origin_id, f"breach:{b}", "pwned_in")

    except Exception as e:
        logger.exception(f"Error añadiendo relaciones automáticas: {e}")


def _emoji_for_category(category: str) -> str:
    """Asigna un emoji representativo según la categoría."""
    mapping = {
        "search": "🔎",
        "mentions": "💬",
        "data_breaches": "🔐",
        "domain_info": "🌐",
        "whois": "🌍",
        "documents": "📄",
        "files": "🗂️",
        "social": "👤",
        "tech": "⚙️",
        "otros": "🧩"
    }
    for k, emoji in mapping.items():
        if k in category.lower():
            return emoji
    return "🧩"
