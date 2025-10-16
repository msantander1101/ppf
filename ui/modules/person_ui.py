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

# Dork templates por defecto (puedes permitir editar/guardar en DB más adelante)
DORK_TEMPLATES = {
    "documents": [
        ("Documentos en web (pdf/docx)", 'site:{entity} filetype:pdf OR filetype:docx'),
        ("Documentos en google drive", 'site:drive.google.com "{entity}"'),
    ],
    "files": [
        ("Archivos (zip, rar)", 'site:{entity} filetype:zip OR filetype:rar'),
        ("Excel/Sheets", 'site:{entity} filetype:xls OR filetype:xlsx OR filetype:csv'),
    ],
    "content": [
        ("Coincidencia exacta", '"{entity}"'),
        ("Contenido en foros", 'site:reddit.com "{entity}" OR site:stackoverflow.com "{entity}"'),
    ],
    "wayback": [
        ("Wayback (histórico)", "{entity}"),
    ]
}


def build_graph_for_person(person_id: int) -> str:
    net = Network(height="700px", width="100%", bgcolor="#111", font_color="white")
    with get_session() as session:
        person = session.get(Person, person_id)
        if not person:
            raise ValueError("Persona no encontrada")

        net.add_node(f"person:{person.id}", label=person.name, color="#00aaff", shape="ellipse", size=35)

        # Emails
        for e in person.emails:
            net.add_node(f"email:{e.id}", label=e.address, color="#ffcc00", shape="dot")
            net.add_edge(f"person:{person.id}", f"email:{e.id}", title="tiene email")

        # Profiles
        for pr in person.profiles:
            net.add_node(f"profile:{pr.id}", label=f"{pr.platform}:{pr.handle}", title=pr.url, color="#66cc66", shape="box")
            net.add_edge(f"person:{person.id}", f"profile:{pr.id}", title="perfil")

        # Relaciones almacenadas (por ejemplo URLs / doc nodes creados via add_relation)
        rels = session.exec(select(SearchLog)).all()  # No queremos solo SearchLog, sino Relations, pero esto es ejemplo
        # Si tú tienes tabla Relation, úsala aquí para agregar nodos URL
        try:
            from core.database import Relation
            relations = session.exec(select(Relation).where(Relation.user_id == person.id)).all()
            for r in relations:
                # si target_id empieza por url: o dork: o similar
                target = r.target_id
                if target.startswith("url:") or target.startswith("dork:") or target.startswith("http"):
                    nid = f"node:{target}"
                    net.add_node(nid, label=target, title=r.relation, color="#ffa500", shape="diamond")
                    net.add_edge(f"person:{person.id}", nid, title=r.relation)
        except Exception:
            # si no hay Relation model no hacemos nada
            pass

    os.makedirs("data", exist_ok=True)
    out_path = f"data/person_graph_{person_id}.html"
    net.show(out_path)
    return out_path


def run(username: str):
    st.header("🧑‍💻 Personas — Huella Digital")
    st.info("Crea y gestiona entidades 'Persona', añade correos y perfiles sociales.")

    # Crear nueva persona
    with st.form("new_person_form"):
        name = st.text_input("Nombre completo")
        notes = st.text_area("Notas (opcional)")
        submitted = st.form_submit_button("Crear persona")

        if submitted:
            if not name.strip():
                st.warning("El nombre no puede estar vacío.")
            else:
                with get_session() as session:
                    person = Person(name=name.strip(), notes=notes or None)
                    session.add(person)
                    session.commit()
                    st.success(f"✅ Persona creada: {person.name}")
                    st.rerun()

    # Listar personas existentes
    st.subheader("Personas registradas")
    with get_session() as session:
        persons = session.exec(select(Person)).all()
        if not persons:
            st.info("No hay personas registradas todavía.")
            return

        for p in persons:
            with st.expander(f"👤 {p.name} (ID: {p.id})"):
                st.write("🗒️ **Notas:**", p.notes or "—")
                st.write("📧 **Emails:**", ", ".join([e.address for e in p.emails]) or "—")
                st.write("🌐 **Perfiles:**", ", ".join([f"{pr.platform}:{pr.handle}" for pr in p.profiles]) or "—")

                # BOTONES DE DORKS: Documentos / Archivos / Contenido / Wayback
                col_doc, col_files, col_content, col_way = st.columns(4)
                if col_doc.button("📄 Documentos", key=f"doc_{p.id}"):
                    _run_dork_batch(p, username, category="documents")
                if col_files.button("🗂️ Archivos", key=f"files_{p.id}"):
                    _run_dork_batch(p, username, category="files")
                if col_content.button("📝 Contenido", key=f"content_{p.id}"):
                    _run_dork_batch(p, username, category="content")
                if col_way.button("⏳ Wayback", key=f"way_{p.id}"):
                    _run_dork_batch(p, username, category="wayback")

                # Form to add email
                with st.form(f"add_email_{p.id}", clear_on_submit=True):
                    new_email = st.text_input("Añadir email", key=f"email_input_{p.id}")
                    add_email_btn = st.form_submit_button("➕ Agregar email")
                    if add_email_btn:
                        if not new_email.strip():
                            st.warning("Introduce un email válido.")
                        else:
                            with get_session() as s:
                                e = Email(address=new_email.strip(), person_id=p.id)
                                s.add(e)
                                s.commit()
                            st.success(f"📧 Email agregado: {new_email}")
                            st.rerun()

                # Form to add profile
                with st.form(f"add_profile_{p.id}", clear_on_submit=True):
                    col1, col2, col3 = st.columns(3)
                    platform = col1.selectbox("Plataforma", ["Twitter", "Instagram", "LinkedIn", "Facebook", "GitHub", "Otro"], key=f"platform_{p.id}")
                    handle = col2.text_input("Usuario / Handle", key=f"handle_{p.id}")
                    url = col3.text_input("URL del perfil", key=f"url_{p.id}")
                    add_profile_btn = st.form_submit_button("➕ Agregar perfil")

                    if add_profile_btn:
                        if not handle.strip():
                            st.warning("Introduce un nombre de usuario o handle.")
                        else:
                            with get_session() as s:
                                pr = Profile(platform=platform, handle=handle.strip(), url=url.strip(), person_id=p.id)
                                s.add(pr)
                                s.commit()
                            st.success(f"🌐 Perfil agregado: {platform} / {handle}")
                            st.rerun()

                # Botón ver grafo
                if st.button(f"Ver grafo de {p.name}", key=f"graph_{p.id}"):
                    try:
                        graph_path = build_graph_for_person(p.id)
                        with open(graph_path, "r", encoding="utf-8") as f:
                            components.html(f.read(), height=700, scrolling=True)
                    except Exception as e:
                        st.error(f"Error generando grafo: {e}")


# Helper: ejecutar plantillas de una categoría para la entidad p
def _run_dork_batch(p: Person, username: str, category: str = "documents"):
    api_key = get_user_setting(username, "serpapi")
    templates = DORK_TEMPLATES.get(category, [])
    all_results = []

    with st.spinner(f"Ejecutando dorks ({category}) para {p.name}..."):
        for label, tpl in templates:
            q = fill_template(tpl, p.name)
            # para Wayback hacemos llamada diferente
            if category == "wayback":
                items = wayback_urls(p.name, limit=20)
                for it in items:
                    res = {"title": "Wayback", "link": it["url"], "snippet": f"timestamp:{it['timestamp']}", "tpl": tpl}
                    all_results.append(res)
                    _persist_dork_result(username, p, res, tpl)
            else:
                try:
                    items = search_dork(q, engine="auto", max_results=10, api_key=api_key)
                except Exception as e:
                    st.error(f"Error ejecutando dork {label}: {e}")
                    continue
                for it in items:
                    title = it.get("title") or it.get("link") or ""
                    link = it.get("link") or it.get("url") or ""
                    snippet = it.get("snippet") or ""
                    res = {"title": title, "link": link, "snippet": snippet, "tpl": tpl}
                    all_results.append(res)
                    _persist_dork_result(username, p, res, tpl)

    # Mostrar resultados en modal/expander debajo de la persona
    if all_results:
        st.success(f"Se han encontrado {len(all_results)} resultados.")
        st.markdown("#### Resultados de dorks")
        for i, r in enumerate(all_results, start=1):
            st.markdown(f"**{i}. [{r['title']}]({r['link']})**")
            if r.get("snippet"):
                st.write(r["snippet"])
            c1, c2 = st.columns([1, 1])
            if c1.button("Abrir", key=f"open_{p.id}_{i}"):
                st.write(f"[Abrir]({r['link']})")
            if c2.button("Añadir al grafo", key=f"add_{p.id}_{i}"):
                # Crear relación: person -> url
                add_relation(username, f"person:{p.id}", f"url:{r['link']}", "referencia")
                st.success("Añadido al grafo (relación creada).")
    else:
        st.info("No se encontraron resultados para esos dorks.")


def _persist_dork_result(username: str, person: Person, result: dict, tpl: str):
    # Guarda SearchLog y relación básica para que quede registro
    try:
        with get_session() as session:
            user = session.exec(select(User).where(User.username == username)).first()
            if user:
                log = SearchLog(query=tpl.replace("{entity}", person.name),
                                result=json.dumps(result, ensure_ascii=False),
                                user_id=user.id,
                                type="dork",
                                created_at=datetime.utcnow())
                session.add(log)
                session.commit()
    except Exception as e:
        logger.exception(f"Error guardando SearchLog: {e}")
