# ui/modules/person_ui.py  (tu base + añadidos de categorías)
import streamlit as st
from sqlmodel import select
from core.database import get_session
from core.entities import Person, Email, Profile, Relation, SearchLog
from utils.logger import logger
from datetime import datetime
import pandas as pd
import json
import re
from modules.search.general_search import search_general
from modules.search.documents_search import search_documents
from modules.search.pastes_search import search_pastes
from modules.search.social_search import search_social
from modules.search.code_search import search_code
from modules.search.archive_search import search_archive
from modules.relations.utils import add_relation
from ui.modules.enrich_utils import smart_enrich

def run(username: str):
    st.subheader("🧍 Investigación y Gestión de Personas")
    st.caption("Registra, busca y analiza la huella digital de una persona en distintas fuentes OSINT.")

    tab1, tab2, tab3 = st.tabs(["📋 Lista", "➕ Nueva persona", "🔍 Búsqueda OSINT"])

    with tab1:
        _show_person_table(username)

    with tab2:
        _add_new_person(username)

    with tab3:
        _search_osint_interface(username)

# ----------------------- LISTA -----------------------
def _show_person_table(username: str):
    # Mantener la sesión abierta para evitar DetachedInstanceError
    with get_session() as session:
        persons = session.exec(select(Person)).all()

        if not persons:
            st.info("No hay personas registradas todavía.")
            return

        data = []
        for p in persons:
            emails = ", ".join([e.address for e in (p.emails or [])])
            profiles = ", ".join([f"{pr.platform}:{pr.handle}" for pr in (p.profiles or [])])
            data.append({
                "ID": p.id,
                "Nombre": p.name,
                "Emails": emails,
                "Perfiles": profiles,
                "Notas": p.notes or "",
                "Creado": p.created_at.strftime("%Y-%m-%d %H:%M:%S")
            })

    df = pd.DataFrame(data)
    st.dataframe(df, width='stretch', hide_index=True)

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        person_id = st.text_input("ID de persona a gestionar", key="input_manage_id")
        if st.button("👁️ Ver Detalles", key="btn_view_person"):
            if person_id.strip():
                _view_person_detail(username, person_id.strip())
            else:
                st.warning("Introduce un ID válido.")
    with col2:
        if st.button("🔄 Refrescar lista"):
            st.rerun()
    with col3:
        if st.button("💾 Exportar CSV"):
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Descargar CSV",
                data=csv.encode("utf-8"),
                file_name="personas_osint.csv",
                mime="text/csv",
            )

# ------------------- NUEVA PERSONA -------------------
def _add_new_person(username: str):
    with st.form("new_person_form"):
        name = st.text_input("👤 Nombre completo")
        notes = st.text_area("🗒️ Notas o contexto")
        email_list = st.text_area("📧 Correos asociados (uno por línea)")
        profiles_data = st.text_area("🌐 Perfiles o identificadores (plataforma:handle)")
        submitted = st.form_submit_button("✅ Guardar Persona")

        if submitted:
            if not name.strip():
                st.warning("El campo nombre es obligatorio.")
                return

            with get_session() as session:
                new_person = Person(name=name.strip(), notes=notes.strip() if notes else "")
                session.add(new_person)
                session.commit()

                for e in email_list.splitlines():
                    e = e.strip()
                    if e:
                        session.add(Email(address=e, person_id=new_person.id))

                for line in profiles_data.splitlines():
                    if ":" in line:
                        platform, handle = line.split(":", 1)
                        session.add(Profile(platform=platform.strip(), handle=handle.strip(), person_id=new_person.id))

                session.commit()
                logger.info(f"Nueva persona registrada: {name}")
                st.success(f"✅ Persona '{name}' añadida correctamente.")
                st.rerun()

# ------------------ DETALLE PERSONA ------------------
def _view_person_detail(username: str, person_id: str):
    # Mantener la sesión abierta mientras se usa el objeto
    with get_session() as session:
        person = session.get(Person, int(person_id))

        if not person:
            st.error("Persona no encontrada.")
            return

        # Convertir a datos simples dentro del contexto
        person_data = {
            "name": person.name,
            "notes": person.notes,
            "created_at": person.created_at,
            "emails": [e.address for e in (person.emails or [])],
            "profiles": [(p.platform, p.handle, p.url) for p in (person.profiles or [])],
        }

    # Aquí ya no se usa el objeto Person, solo dict
    st.markdown(f"### 👤 {person_data['name']}")
    st.caption(f"🕒 Creado el {person_data['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
    if person_data["notes"]:
        st.info(person_data["notes"])

    st.markdown("#### 📧 Emails")
    if person_data["emails"]:
        for e in person_data["emails"]:
            st.write(f"- {e}")
    else:
        st.warning("Sin correos asociados.")

    st.markdown("#### 🌐 Perfiles")
    if person_data["profiles"]:
        for platform, handle, url in person_data["profiles"]:
            url = url or f"https://{platform}.com/{handle}"
            st.markdown(f"- [{platform}]({url}) → {handle}")
    else:
        st.warning("Sin perfiles sociales registrados.")

    st.markdown("---")
    st.subheader("🧭 Buscar por categoría")

    col1, col2, col3 = st.columns(3)
    col4, col5, col6 = st.columns(3)

    if col1.button("🔍 General"):
        _run_and_render(username, person, search_general(person.name))
    if col2.button("📄 Docs"):
        _run_and_render(username, person, search_documents(person.name))
    if col3.button("🧾 Pastes"):
        first_email = person.emails[0].address if person.emails else ""
        _run_and_render(username, person, search_pastes(person.name, email=first_email))
    if col4.button("👥 Social"):
        _run_and_render(username, person, search_social(person.name))
    if col5.button("💻 Code"):
        first_email = person.emails[0].address if person.emails else ""
        _run_and_render(username, person, search_code(person.name, email=first_email))
    if col6.button("🕰️ Histórico"):
        _run_and_render(username, person, search_archive(person.name))

    st.markdown("---")
    _show_relations(person_id)

# -------------- BUSQUEDA LIBRE MANUAL ----------------
def _search_osint_interface(username: str):
    st.markdown("### 🔎 Búsqueda libre OSINT")
    query = st.text_input("Introduce un nombre, correo, dominio o alias social")
    if st.button("Buscar"):
        with st.spinner("Buscando en múltiples fuentes..."):
            # por simplicidad, usa General
            results = search_general(query, username=username)
            if results:
                _render_osint_results(username, None, results)
            else:
                st.warning("Sin resultados.")

# ---------------- RENDER & PERSISTENCIA ---------------
def _run_and_render(username, person, results):
    if not results:
        st.info("No se encontraron resultados.")
        return
    _render_osint_results(username, person, results)

def _render_osint_results(username, person, results):
    count = 0
    for r in results:
        count += 1
        title = r.get("title") or r.get("link") or "sin título"
        link = r.get("link") or ""
        snippet = r.get("snippet") or ""
        label = r.get("label", "")
        category = r.get("category", "")

        with st.expander(f"🌐 {title}"):
            st.caption(f"{category} · {label}")
            if link:
                st.markdown(f"[Abrir enlace]({link})")
            if snippet:
                st.caption(snippet[:300] + ("..." if len(snippet) > 300 else ""))

            c1, c2, c3 = st.columns(3)
            if c1.button("🔗 Abrir", key=f"open_{count}_{title[:16]}"):
                st.markdown(f"[Abrir enlace]({link})")
            if c2.button("➕ Añadir al grafo", key=f"add_{count}_{title[:16]}"):
                if person and link:
                    add_relation(username, f"person:{person.id}", f"url:{link}", "referencia")
                    st.success("Añadido al grafo.")
            if c3.button("🧠 Enriquecer", key=f"enrich_{count}_{title[:16]}"):
                try:
                    out = smart_enrich(username, link or title)
                    st.success("Enriquecimiento lanzado.")
                except Exception as e:
                    st.error(f"Error enriqueciendo: {e}")

    # Guardar log (sin forzar user_id)
    try:
        with get_session() as session:
            log = SearchLog(
                query=f"osint:{person.name if person else 'manual'}",
                result=json.dumps(results, ensure_ascii=False),
                user_id=None,
                type="osint_search",
                created_at=datetime.utcnow()
            )
            session.add(log)
            session.commit()
        logger.info(f"[person_ui] Guardados {len(results)} resultados OSINT.")
    except Exception as e:
        logger.warning(f"No se pudo guardar SearchLog: {e}")

# -------------------- RELACIONES ----------------------
def _show_relations(person_id: str):
    with get_session() as session:
        rels = session.exec(select(Relation).where(Relation.source_id == f"person:{person_id}")).all()

    if not rels:
        st.info("No hay relaciones asociadas a esta persona.")
        return

    st.markdown("#### 🔗 Relaciones detectadas")
    for r in rels:
        st.write(f"- **{r.relation}** → {r.target_id} ({r.created_at.strftime('%Y-%m-%d')})")

    if st.button("❌ Eliminar todas las relaciones de esta persona"):
        with get_session() as session:
            for r in rels:
                session.delete(r)
            session.commit()
        st.warning("Relaciones eliminadas.")
        st.rerun()
