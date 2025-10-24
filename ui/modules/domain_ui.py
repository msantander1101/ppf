# ui/modules/domain_ui.py
import streamlit as st
from sqlmodel import select
from core.database import get_session
from core.entities import Domain, Person
from utils.logger import logger
import streamlit.components.v1 as components
from pyvis.network import Network
from core.config import get_user_setting
from core.entities import User, SearchLog
from modules.search.dorks_engine import fill_template, search_dork
from modules.relations.utils import add_relation
from core import enrichment as core_enrichment
from datetime import datetime
import json
import os
import re

# ======================
# CONFIGURACIÓN DE DORKS
# ======================
DOMAIN_DORKS = [
    ("Subdominios", "site:*.{entity}"),
    ("Archivos públicos", "site:{entity} filetype:xls OR filetype:csv OR filetype:pdf OR filetype:docx"),
    ("Configuraciones expuestas", "site:{entity} ext:env OR ext:ini OR ext:conf"),
    ("Fugas de datos", '"{entity}" password OR contraseña OR leaked'),
    ("Repositorios Git", "site:github.com {entity}"),
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


def _build_graph_for_domain(domain_id: int) -> str:
    """Construye grafo visual del dominio y sus relaciones."""
    net = Network(height="700px", width="100%", bgcolor="#111", font_color="white")

    with get_session() as session:
        domain = session.get(Domain, domain_id)
        if not domain:
            raise ValueError("Dominio no encontrado")

        net.add_node(f"domain:{domain.id}", label=domain.name, color="#00cc99", shape="ellipse", size=35)

        if domain.person_id:
            person = session.get(Person, domain.person_id)
            if person:
                net.add_node(f"person:{person.id}", label=person.name, color="#00aaff", shape="dot")
                net.add_edge(f"person:{person.id}", f"domain:{domain.id}", title="posee")

        try:
            # Importamos Relation desde core.entities para evitar problemas de importación
            from core.entities import Relation
            relations = session.exec(select(Relation).where(Relation.source_id == f"domain:{domain.id}")).all()
            for r in relations:
                target = r.target_id
                net.add_node(f"node:{target}", label=target, title=r.relation, color="#ffa500", shape="diamond")
                net.add_edge(f"domain:{domain.id}", f"node:{target}", title=r.relation)
        except Exception:
            # Silenciamos excepciones cuando la tabla no existe
            pass

    os.makedirs("data", exist_ok=True)
    out_path = f"data/domain_graph_{domain_id}.html"
    net.show(out_path)
    return out_path


def _run_dork_search(domain: str, username: str):
    """Ejecuta búsquedas OSINT (dorks) para un dominio."""
    api_key = get_user_setting(username, "serpapi")
    all_results = []

    with st.spinner(f"🔍 Ejecutando dorks OSINT para {domain}..."):
        for label, tpl in DOMAIN_DORKS:
            q = fill_template(tpl, domain)
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


def _auto_enrich_entity(username: str, result: dict, parent_domain: Domain = None):
    """Detecta entidades relevantes y ejecuta enriquecimiento automático."""
    snippet = result.get("snippet", "")
    link = result.get("link", "")
    entity = None
    entity_type = None

    # Detectar emails o dominios adicionales
    email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", snippet)
    if email_match:
        entity = email_match.group(0)
        entity_type = "email"
    elif link:
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

        if parent_domain:
            add_relation(username, f"domain:{parent_domain.id}", f"{entity_type}:{entity}", "auto_enriched")

        st.success(f"✅ Enriquecimiento completado ({len(results)} resultados).")
    except Exception as e:
        logger.exception(f"Error en auto_enrich_entity (domain): {e}")
        st.error(f"Error durante enriquecimiento: {e}")


# ======================
# INTERFAZ PRINCIPAL
# ======================
def run(username: str):
    st.header("🌐 Dominios — Análisis OSINT")
    st.info("Gestiona dominios, ejecuta búsquedas OSINT y enriquecimiento de información.")

    # Crear nuevo dominio
    with st.form("new_domain_form"):
        name = st.text_input("Nombre del dominio (ej. ejemplo.com)")
        notes = st.text_area("Notas (opcional)")
        submitted = st.form_submit_button("Agregar dominio")
        if submitted:
            if not name.strip():
                st.warning("El nombre del dominio no puede estar vacío.")
            else:
                with get_session() as session:
                    domain = Domain(name=name.strip(), notes=notes or None)
                    session.add(domain)
                    session.commit()
                    st.success(f"✅ Dominio agregado: {domain.name}")
                    st.rerun()

    # Listar dominios existentes
    with get_session() as session:
        domains = session.exec(select(Domain)).all()

    if not domains:
        st.warning("No hay dominios registrados todavía.")
        return

    for d in domains:
        with st.expander(f"🌐 {d.name} (ID: {d.id})"):
            st.write("🗒️ **Notas:**", d.notes or "—")
            st.write(f"👤 **Persona vinculada:** {d.person.name if d.person_id else '—'}")

            col1, col2, col3 = st.columns(3)
            if col1.button("🔍 Buscar Dorks", key=f"dork_{d.id}"):
                _display_dork_results(d, username)
            if col2.button("🧠 Enriquecer Dominio", key=f"enrich_{d.id}"):
                _enrich_domain(d, username)
            if col3.button("📊 Ver grafo", key=f"graph_{d.id}"):
                graph_path = _build_graph_for_domain(d.id)
                with open(graph_path, "r", encoding="utf-8") as f:
                    components.html(f.read(), height=700, scrolling=True)

            if st.button("🗑️ Eliminar dominio", key=f"delete_{d.id}"):
                with get_session() as s:
                    s.delete(s.get(Domain, d.id))
                    s.commit()
                st.warning(f"Dominio '{d.name}' eliminado.")
                st.rerun()


def _display_dork_results(domain_obj: Domain, username: str):
    """Muestra resultados de dorks con acciones."""
    results = _run_dork_search(domain_obj.name, username)
    if not results:
        st.info("No se encontraron resultados.")
        return

    st.success(f"Se encontraron {len(results)} resultados para {domain_obj.name}.")
    for i, r in enumerate(results, 1):
        st.markdown(f"**{i}. [{r['title']}]({r['link']})**")
        snippet = r.get("snippet", "")
        if snippet:
            st.caption(snippet[:250] + ("..." if len(snippet) > 250 else ""))

        c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
        if c1.button("🌐 Abrir", key=f"open_{domain_obj.id}_{i}"):
            st.write(f"[Abrir]({r['link']})")
        if c2.button("📊 Añadir al grafo", key=f"add_{domain_obj.id}_{i}"):
            add_relation(username, f"domain:{domain_obj.id}", f"url:{r['link']}", "referencia")
            st.success("Añadido al grafo.")
        if c3.button("🗑️ Eliminar", key=f"del_{domain_obj.id}_{i}"):
            st.info("Resultado eliminado temporalmente.")
        if c4.button("🧠 Enriquecer esta entidad", key=f"auto_enrich_{domain_obj.id}_{i}"):
            _auto_enrich_entity(username, r, parent_domain=domain_obj)

        st.markdown("---")


def _enrich_domain(domain_obj: Domain, username: str):
    """Ejecuta enriquecimiento completo (Dorks + core.enrichment)."""
    st.info(f"🧠 Enriqueciendo completamente {domain_obj.name}...")

    try:
        dork_results = _run_dork_search(domain_obj.name, username)
        enrich_results = core_enrichment.enrich_domain(username, domain_obj.name)

        total = len(dork_results) + len(enrich_results)
        for r in enrich_results:
            _persist_result(username, domain_obj.name, r, tipo="enrich")

        st.success(f"✅ Enriquecimiento completado ({total} resultados combinados).")

    except Exception as e:
        logger.exception(f"Error en _enrich_domain: {e}")
        st.error(f"Error durante enriquecimiento: {e}")
