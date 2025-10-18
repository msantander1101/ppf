# ui/modules/person_ui.py

import streamlit as st
from sqlmodel import select
from core.database import get_session
from core.entities import Person, Email, Profile
from utils.logger import logger
import streamlit.components.v1 as components
from pyvis.network import Network
import os
from core.config import get_user_setting
from modules.search.dorks_engine import fill_template, search_dork, wayback_urls
from modules.relations.utils import add_relation
from core.database import SearchLog, User
import json
from datetime import datetime
from ui.modules import auto_enrich_ui
from core import enrichment as core_enrichment


# ==============================================================
# 🔧 CONFIGURACIÓN DE DORKS
# ==============================================================
DORK_TEMPLATES = {
    "documents": [
        ("Documentos en web (pdf/docx)", 'site:{entity} filetype:pdf OR filetype:docx'),
        ("Documentos en Google Drive", 'site:drive.google.com "{entity}"'),
    ],
    "files": [
        ("Archivos comprimidos", 'site:{entity} filetype:zip OR filetype:rar'),
        ("Excel/Sheets", 'site:{entity} filetype:xls OR filetype:xlsx OR filetype:csv'),
    ],
    "content": [
        ("Coincidencia exacta", '"{entity}"'),
        ("Contenido en foros", 'site:reddit.com "{entity}" OR site:stackoverflow.com "{entity}"'),
    ],
    "wayback": [
        ("Histórico (Wayback)", "{entity}"),
    ]
}


# ==============================================================
# 🔹 FUNCIONES AUXILIARES
# ==============================================================

def _persist_dork_result(username: str, person: Person, result: dict, tpl: str):
    """Guarda en SearchLog un resultado de búsqueda Dork."""
    try:
        with get_session() as session:
            user = session.exec(select(User).where(User.username == username)).first()
            if user:
                log = SearchLog(
                    query=tpl.replace("{entity}", person.name),
                    result=json.dumps(result, ensure_ascii=False),
                    user_id=user.id,
                    type="dork",
                    created_at=datetime.utcnow(),
                )
                session.add(log)
                session.commit()
    except Exception as e:
        logger.exception(f"Error guardando SearchLog (dork): {e}")


def _delete_dork_results(username: str, person: Person):
    """Elimina todos los resultados de búsqueda Dork para una persona."""
    try:
        with get_session() as session:
            logs = session.exec(
                select(SearchLog).where(SearchLog.query.contains(person.name))
            ).all()
            for log in logs:
                session.delete(log)
            session.commit()
    except Exception as e:
        logger.exception(f"Error eliminando resultados de Dorks: {e}")


def _delete_person(username: str, person: Person):
    """Elimina completamente una persona y sus datos relacionados."""
    try:
        with get_session() as session:
            p = session.get(Person, person.id)
            if not p:
                logger.warning(f"Tried to delete non-existing person id={person.id}")
                return

            # Eliminar SearchLogs
            logs = session.exec(select(SearchLog).where(SearchLog.query.contains(p.name))).all()
            for log in logs:
                session.delete(log)

            # Eliminar relaciones si existe el modelo Relation
            try:
                from core.database import Relation
                rels = session.exec(
                    select(Relation).where(
                        (Relation.source_id == f"person:{p.id}") |
                        (Relation.target_id.contains(f"person:{p.id}"))
                    )
                ).all()
                for r in rels:
                    session.delete(r)
            except Exception:
                logger.debug("Relation model not present or error querying relations while deleting person.")

            # Eliminar emails y perfiles asociados
            emails = session.exec(select(Email).where(Email.person_id == p.id)).all()
            for e in emails:
                session.delete(e)

            profiles = session.exec(select(Profile).where(Profile.person_id == p.id)).all()
            for pr in profiles:
                session.delete(pr)

            # Finalmente eliminar la persona
            session.delete(p)
            session.commit()
            logger.info(f"Persona y datos relacionados eliminados: {p.name} (id={p.id})")
    except Exception as e:
        logger.exception(f"Error eliminando persona {person.id}: {e}")


# ==============================================================
# 🔹 DORKS
# ==============================================================

def _run_dork_batch(p: Person, username: str, category: str = "documents"):
    """Ejecuta un conjunto de dorks predefinidos según categoría."""
    api_key = get_user_setting(username, "serpapi")
    templates = DORK_TEMPLATES.get(category, [])
    all_results = []

    with st.spinner(f"Ejecutando dorks ({category}) para {p.name}..."):
        for label, tpl in templates:
            query = fill_template(tpl, p.name)

            if category == "wayback":
                items = wayback_urls(p.name, limit=20)
                for it in items:
                    res = {"title": "Wayback", "link": it["url"], "snippet": f"timestamp:{it['timestamp']}", "tpl": tpl}
                    all_results.append(res)
                    _persist_dork_result(username, p, res, tpl)
            else:
                try:
                    items = search_dork(query, engine="auto", max_results=10, api_key=api_key)
                except Exception as e:
                    st.error(f"Error ejecutando dork {label}: {e}")
                    continue
                for it in items:
                    res = {
                        "title": it.get("title") or it.get("link") or "(sin título)",
                        "link": it.get("link") or it.get("url") or "",
                        "snippet": (it.get("snippet") or "")[:150],
                        "tpl": tpl
                    }
                    all_results.append(res)
                    _persist_dork_result(username, p, res, tpl)

    st.markdown("---")
    if all_results:
        st.success(f"Se han encontrado {len(all_results)} resultados para {p.name}.")
        if st.button("🗑️ Eliminar todos los resultados", key=f"del_all_{p.id}"):
            _delete_dork_results(username, p)
            st.warning("Resultados eliminados.")
            st.rerun()

        for i, r in enumerate(all_results, start=1):
            with st.container():
                st.markdown(f"**{i}. [{r['title']}]({r['link']})**")
                st.caption(r.get("snippet", ""))
                c1, c2, c3 = st.columns([1, 1, 1])
                if c1.button("🌐 Abrir", key=f"open_{p.id}_{i}"):
                    st.write(f"[Abrir enlace]({r['link']})")
                if c2.button("📊 Añadir al grafo", key=f"add_{p.id}_{i}"):
                    add_relation(username, f"person:{p.id}", f"url:{r['link']}", "referencia")
                    st.success("Añadido al grafo.")
                if c3.button("🗑️ Eliminar", key=f"del_{p.id}_{i}"):
                    with get_session() as session:
                        logs = session.exec(select(SearchLog).where(SearchLog.result.contains(r['link']))).all()
                        for log in logs:
                            session.delete(log)
                        session.commit()
                    st.warning("Resultado eliminado.")
                    st.rerun()
                st.markdown("---")
    else:
        st.info("No se encontraron resultados para esos dorks.")


# ==============================================================
# 🔹 ENRIQUECIMIENTO
# ==============================================================

def _persist_enrich_result(username: str, person: Person, result):
    """Guarda resultado de enriquecimiento en SearchLog."""
    try:
        with get_session() as session:
            user = session.exec(select(User).where(User.username == username)).first()
            if user:
                payload = result.to_dict() if hasattr(result, "to_dict") else result
                log = SearchLog(
                    query=f"enrich:{person.name}:{payload.get('source','')}",
                    result=json.dumps(payload, ensure_ascii=False),
                    user_id=user.id,
                    type="enrich",
                    created_at=datetime.utcnow()
                )
                session.add(log)
                session.commit()
    except Exception as e:
        logger.exception(f"Error guardando SearchLog (enrich): {e}")


def _quick_enrich_person(person: Person, username: str):
    """Enriquecimiento rápido usando core.enrichment"""
    st.info(f"Iniciando enriquecimiento rápido para {person.name}...")
    try:
        extra = {
            "name": person.name,
            "email": person.emails[0].address if person.emails else "",
            "username": person.profiles[0].handle if person.profiles else "",
        }

        results = core_enrichment.enrich_person(username, extra)
        if not results:
            st.warning("No se obtuvieron resultados.")
            return

        for r in results:
            _persist_enrich_result(username, person, r)
        st.success(f"Enriquecimiento completado: {len(results)} fuentes procesadas.")
    except Exception as e:
        st.error(f"Error durante el enriquecimiento: {e}")
        logger.exception(e)


# ==============================================================
# 🔹 GRAFO DE PERSONA
# ==============================================================

def build_graph_for_person(person_id: int) -> str:
    """Genera grafo visual de una persona y sus relaciones."""
    net = Network(height="700px", width="100%", bgcolor="#111", font_color="white")

    with get_session() as session:
        person = session.get(Person, person_id)
        if not person:
            raise ValueError("Persona no encontrada")

        net.add_node(f"person:{person.id}", label=person.name, color="#00aaff", shape="ellipse", size=35)

        for e in person.emails:
            net.add_node(f"email:{e.id}", label=e.address, color="#ffcc00", shape="dot")
            net.add_edge(f"person:{person.id}", f"email:{e.id}", title="tiene email")

        for pr in person.profiles:
            net.add_node(f"profile:{pr.id}", label=f"{pr.platform}:{pr.handle}", title=pr.url, color="#66cc66", shape="box")
            net.add_edge(f"person:{person.id}", f"profile:{pr.id}", title="perfil")

        try:
            from core.database import Relation
            relations = session.exec(select(Relation).where(Relation.user_id == person.id)).all()
            for r in relations:
                target = r.target_id
                nid = f"node:{target}"
                net.add_node(nid, label=target, title=r.relation, color="#ffa500", shape="diamond")
                net.add_edge(f"person:{person.id}", nid, title=r.relation)
        except Exception:
            pass

    os.makedirs("data", exist_ok=True)
    out_path = f"data/person_graph_{person_id}.html"
    net.show(out_path)
    return out_path


# ==============================================================
# 🔹 INTERFAZ PRINCIPAL
# ==============================================================

def run(username: str):
    st.header("🧑‍💻 Personas — Huella Digital")
    st.info("Crea y gestiona entidades 'Persona', añade correos, perfiles y ejecuta búsquedas OSINT.")

    # Crear persona
    with st.form("new_person_form"):
        name = st.text_input("Nombre completo")
        notes = st.text_area("Notas (opcional)")
        if st.form_submit_button("Crear persona"):
            if not name.strip():
                st.warning("El nombre no puede estar vacío.")
            else:
                with get_session() as session:
                    person = Person(name=name.strip(), notes=notes or None)
                    session.add(person)
                    session.commit()
                    st.success(f"✅ Persona creada: {person.name}")
                    st.rerun()

    # Listado de personas
    st.subheader("Personas registradas")
    with get_session() as session:
        persons = session.exec(select(Person)).all()
        if not persons:
            st.info("No hay personas registradas todavía.")
            return

        # ✅ Cargar datos antes de cerrar la sesión
        persons_data = []
        for p in persons:
            emails = [e.address for e in p.emails]
            profiles = [f"{pr.platform}:{pr.handle}" for pr in p.profiles]
            persons_data.append({
                "id": p.id,
                "name": p.name,
                "notes": p.notes,
                "emails": emails,
                "profiles": profiles
            })

    # 🔽 Interfaz fuera de la sesión
    for pdata in persons_data:
        with st.expander(f"👤 {pdata['name']} (ID: {pdata['id']})"):
            st.write("🗒️ **Notas:**", pdata['notes'] or "—")
            st.write("📧 **Emails:**", ", ".join(pdata['emails']) or "—")
            st.write("🌐 **Perfiles:**", ", ".join(pdata['profiles']) or "—")

            with get_session() as s:
                p = s.get(Person, pdata['id'])
                if not p:
                    st.warning("Persona no encontrada.")
                    continue

                # Botones de búsqueda
                col_doc, col_files, col_content, col_way = st.columns(4)
                if col_doc.button("📄 Documentos", key=f"doc_{p.id}"):
                    _run_dork_batch(p, username, category="documents")
                if col_files.button("🗂️ Archivos", key=f"files_{p.id}"):
                    _run_dork_batch(p, username, category="files")
                if col_content.button("📝 Contenido", key=f"content_{p.id}"):
                    _run_dork_batch(p, username, category="content")
                if col_way.button("⏳ Wayback", key=f"way_{p.id}"):
                    _run_dork_batch(p, username, category="wayback")

                # Enriquecimiento
                en_col1, en_col2 = st.columns([1, 1])
                if en_col1.button("🧠 Enriquecer (rápido)", key=f"quick_enrich_{p.id}"):
                    _quick_enrich_person(p, username)
                if en_col2.button("🧩 Enriquecer (UI)", key=f"ui_enrich_{p.id}"):
                    auto_enrich_ui.run(username, "person", p.name)

                # Añadir email
                with st.form(f"add_email_{p.id}", clear_on_submit=True):
                    new_email = st.text_input("Añadir email", key=f"email_input_{p.id}")
                    if st.form_submit_button("➕ Agregar email") and new_email.strip():
                        e = Email(address=new_email.strip(), person_id=p.id)
                        s.add(e)
                        s.commit()
                        st.success(f"📧 Email agregado: {new_email}")
                        st.rerun()

                # Añadir perfil
                with st.form(f"add_profile_{p.id}", clear_on_submit=True):
                    col1, col2, col3 = st.columns(3)
                    platform = col1.selectbox("Plataforma", ["Twitter", "Instagram", "LinkedIn", "Facebook", "GitHub", "Otro"])
                    handle = col2.text_input("Usuario / Handle")
                    url = col3.text_input("URL del perfil")
                    if st.form_submit_button("➕ Agregar perfil") and handle.strip():
                        pr = Profile(platform=platform, handle=handle.strip(), url=url.strip(), person_id=p.id)
                        s.add(pr)
                        s.commit()
                        st.success(f"🌐 Perfil agregado: {platform} / {handle}")
                        st.rerun()

                # Grafo
                if st.button(f"Ver grafo de {p.name}", key=f"graph_{p.id}"):
                    try:
                        graph_path = build_graph_for_person(p.id)
                        with open(graph_path, "r", encoding="utf-8") as f:
                            components.html(f.read(), height=700, scrolling=True)
                    except Exception as e:
                        st.error(f"Error generando grafo: {e}")

                # Eliminar persona
                if st.button("❌ Eliminar persona", key=f"del_person_{p.id}"):
                    st.session_state[f"confirm_delete_{p.id}"] = True

                if st.session_state.get(f"confirm_delete_{p.id}", False):
                    with st.expander("⚠️ Confirma eliminación permanente", expanded=True):
                        st.warning("Esta acción eliminará la persona y TODOS sus datos relacionados.")
                        confirm_input = st.text_input("Escribe el nombre completo para confirmar", key=f"confirm_input_{p.id}")
                        col_ok, col_cancel = st.columns([1, 1])
                        if col_ok.button("Confirmar eliminación", key=f"confirm_del_btn_{p.id}"):
                            if confirm_input.strip() == p.name:
                                _delete_person(username, p)
                                st.success("✅ Persona eliminada correctamente.")
                                st.session_state.pop(f"confirm_delete_{p.id}", None)
                                st.rerun()
                            else:
                                st.error("El texto no coincide con el nombre de la persona.")
                        if col_cancel.button("Cancelar", key=f"cancel_del_btn_{p.id}"):
                            st.session_state.pop(f"confirm_delete_{p.id}", None)
                            st.info("Eliminación cancelada.")
