import streamlit as st
from sqlmodel import select
from core.database import get_session
from core.entities import Email, Person, User, SearchLog
from utils.logger import logger
import streamlit.components.v1 as components
from pyvis.network import Network
from core.config import get_user_setting
from modules.search.dorks_engine import fill_template, search_dork
from modules.relations.utils import add_relation
from core import enrichment as core_enrichment
from datetime import datetime
import json
import re
import os

# ======================
# CONFIGURACIÓN DE DORKS
# ======================
EMAIL_DORKS = [
    ("Coincidencias en foros", '"{entity}" site:reddit.com OR site:pastebin.com OR site:breached.vc'),
    ("Archivos públicos", '"{entity}" filetype:xls OR filetype:csv OR filetype:txt'),
    ("Fugas de datos", '"{entity}" "password" OR "contraseña"'),
    ("Documentos PDF", '"{entity}" filetype:pdf'),
    ("GitHub", 'site:github.com "{entity}"'),
]


# ======================
# FUNCIONES AUXILIARES
# ======================
def _persist_result(username, query, result, tipo="dork"):
    """Guardar resultados en SearchLog."""
    try:
        with get_session() as session:
            user = session.exec(select(User).where(User.username == username)).first()
            if user:
                log = SearchLog(
                    query=query,
                    result=json.dumps(result, ensure_ascii=False),
                    user_id=user.id,
                    type=tipo,
                    created_at=datetime.utcnow(),
                )
                session.add(log)
                session.commit()
    except Exception as e:
        logger.exception(f"Error guardando resultado ({tipo}): {e}")


def _build_graph_for_email(email_id: int) -> str:
    """Construye grafo visual de conexiones de un email."""
    net = Network(height="700px", width="100%", bgcolor="#111", font_color="white")

    with get_session() as session:
        email = session.get(Email, email_id)
        if not email:
            raise ValueError("Email no encontrado")

        net.add_node(f"email:{email.id}", label=email.address, color="#ffcc00", shape="dot", size=35)

        if email.person_id:
            person = session.get(Person, email.person_id)
            if person:
                net.add_node(f"person:{person.id}", label=person.name, color="#00aaff", shape="ellipse", size=40)
                net.add_edge(f"person:{person.id}", f"email:{email.id}", title="posee")

        try:
            # Importamos la entidad Relation desde core.entities en lugar de core.database
            from core.entities import Relation
            relations = session.exec(select(Relation).where(Relation.source_id == f"email:{email.id}")).all()
            for r in relations:
                target = r.target_id
                net.add_node(f"node:{target}", label=target, title=r.relation, color="#ffa500", shape="diamond")
                net.add_edge(f"email:{email.id}", f"node:{target}", title=r.relation)
        except Exception:
            # Si la tabla de relaciones no está disponible, ignoramos
            pass

    os.makedirs("data", exist_ok=True)
    out_path = f"data/email_graph_{email_id}.html"
    net.show(out_path)
    return out_path


def _run_dork_search(email_addr: str, username: str):
    """Ejecuta búsquedas OSINT (dorks) para un correo."""
    api_key = get_user_setting(username, "serpapi")
    all_results = []

    with st.spinner(f"🔍 Ejecutando dorks OSINT para {email_addr}..."):
        for label, tpl in EMAIL_DORKS:
            q = fill_template(tpl, email_addr)
            try:
                items = search_dork(q, engine="auto", max_results=10, api_key=api_key)
                for it in items:
                    res = {
                        "title": it.get("title") or it.get("link") or "Sin título",
                        "link": it.get("link") or "",
                        "snippet": it.get("snippet") or "",
                        "tpl": tpl,
                        "category": label,
                    }
                    all_results.append(res)
                    _persist_result(username, q, res, tipo="dork")
            except Exception as e:
                st.error(f"Error ejecutando {label}: {e}")

    return all_results


def _auto_enrich_entity(username: str, result: dict, parent_email: Email = None):
    """Detecta entidades relevantes (email, dominio, perfil) y las enriquece automáticamente."""
    snippet = result.get("snippet", "")
    link = result.get("link", "")
    entity = None
    entity_type = None

    # Detectar email adicional
    email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", snippet)
    if email_match:
        entity = email_match.group(0)
        entity_type = "email"

    # Detectar dominios
    if not entity and link:
        domain_match = re.search(r"https?://([A-Za-z0-9.-]+\.[A-Za-z]{2,})", link)
        if domain_match:
            entity = domain_match.group(1)
            entity_type = "domain"

    if not entity:
        st.warning("No se detectó entidad relevante para enriquecer.")
        return

    st.info(f"🧠 Enriqueciendo {entity_type}: {entity}")
    try:
        if entity_type == "email":
            results = core_enrichment.enrich_email(username, entity)
        elif entity_type == "domain":
            results = core_enrichment.enrich_domain(username, entity)
        else:
            results = []

        for r in results:
            _persist_result(username, entity, r, tipo="enrich")

        if parent_email:
            add_relation(username, f"email:{parent_email.id}", f"{entity_type}:{entity}", "auto_enriched")

        st.success(f"✅ Enriquecimiento completado ({len(results)} resultados).")
    except Exception as e:
        logger.exception(f"Error en auto_enrich_entity (email): {e}")
        st.error(f"Error durante enriquecimiento: {e}")


# ======================
# INTERFAZ PRINCIPAL
# ======================
def run(username: str):
    st.header("📧 Emails — Análisis OSINT")
    st.info("Gestiona correos electrónicos asociados y ejecuta búsquedas y enriquecimiento OSINT.")

    with get_session() as session:
        emails = session.exec(select(Email)).all()

    if not emails:
        st.warning("No hay correos registrados todavía.")
        return

    for e in emails:
        with st.expander(f"📧 {e.address} (ID: {e.id})"):
            st.write(f"🔗 Vinculado a persona: {e.person.name if e.person_id else '—'}")

            col1, col2, col3 = st.columns(3)
            if col1.button("🔍 Buscar Dorks", key=f"dork_{e.id}"):
                _display_dork_results(e, username)
            if col2.button("🧠 Enriquecer Email", key=f"enrich_{e.id}"):
                _enrich_email(e, username)
            if col3.button("📊 Ver grafo", key=f"graph_{e.id}"):
                graph_path = _build_graph_for_email(e.id)
                with open(graph_path, "r", encoding="utf-8") as f:
                    components.html(f.read(), height=700, scrolling=True)

            if st.button("🗑️ Eliminar email", key=f"delete_{e.id}"):
                with get_session() as s:
                    s.delete(s.get(Email, e.id))
                    s.commit()
                st.warning(f"Email '{e.address}' eliminado.")
                st.rerun()


def _display_dork_results(email_obj: Email, username: str):
    """Muestra los resultados de los dorks con botones de acción."""
    results = _run_dork_search(email_obj.address, username)
    if not results:
        st.info("No se encontraron resultados.")
        return

    st.success(f"Se encontraron {len(results)} resultados para {email_obj.address}.")
    for i, r in enumerate(results, 1):
        st.markdown(f"**{i}. [{r['title']}]({r['link']})**")
        snippet = r.get("snippet", "")
        if snippet:
            st.caption(snippet[:250] + ("..." if len(snippet) > 250 else ""))

        c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
        if c1.button("🌐 Abrir", key=f"open_{email_obj.id}_{i}"):
            st.write(f"[Abrir]({r['link']})")
        if c2.button("📊 Añadir al grafo", key=f"add_{email_obj.id}_{i}"):
            add_relation(username, f"email:{email_obj.id}", f"url:{r['link']}", "referencia")
            st.success("Añadido al grafo.")
        if c3.button("🗑️ Eliminar", key=f"del_{email_obj.id}_{i}"):
            st.info("Resultado eliminado temporalmente.")
        if c4.button("🧠 Enriquecer esta entidad", key=f"auto_enrich_{email_obj.id}_{i}"):
            _auto_enrich_entity(username, r, parent_email=email_obj)

        st.markdown("---")


def _enrich_email(email_obj: Email, username: str):
    """Ejecuta enriquecimiento completo (Dorks + Módulo core.enrichment)."""
    st.info(f"🧠 Enriqueciendo completamente {email_obj.address}...")

    try:
        dork_results = _run_dork_search(email_obj.address, username)
        enrich_results = core_enrichment.enrich_email(username, email_obj.address)

        total = len(dork_results) + len(enrich_results)
        for r in enrich_results:
            _persist_result(username, email_obj.address, r, tipo="enrich")

        st.success(f"✅ Enriquecimiento completado ({total} resultados combinados).")

    except Exception as e:
        logger.exception(f"Error en _enrich_email: {e}")
        st.error(f"Error durante enriquecimiento: {e}")
