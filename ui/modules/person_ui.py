import streamlit as st
from sqlmodel import select
from core.database import get_session
from core.entities import Person, Email, Profile
from utils.logger import logger
import streamlit.components.v1 as components
from pyvis.network import Network
import os
from modules.enrichment.hibp_enricher import enrich_person_emails
from modules.enrichment.domain_enricher import enrich_person_domains
from modules.enrichment.social_enricher import enrich_person_profiles


def build_graph_for_person(person_id: int) -> str:
    """Crea un grafo interactivo para la persona seleccionada."""
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

                # Mostrar correos y perfiles
                st.write("📧 **Emails:**", ", ".join([e.address for e in p.emails]) or "—")
                st.write("🌐 **Perfiles:**", ", ".join([f"{pr.platform}:{pr.handle}" for pr in p.profiles]) or "—")

                # --- Formulario para añadir email ---
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

                # --- Formulario para añadir perfil ---
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
                # --- Botón de enriquecimiento completo ---
                if st.button(f"🔍 Enriquecer datos ({p.name})", key=f"enrich_{p.id}"):
                    with get_session() as s:
                        ok1, msg1 = enrich_person_emails(p.id, username, s)
                        ok2, msg2 = enrich_person_domains(p.id, username, s)
                        ok3, msg3 = enrich_person_profiles(p.id, s)

                        st.info("Resultados de enriquecimiento:")
                        st.write(f"- 📧 {msg1}")
                        st.write(f"- 🌐 {msg2}")
                        st.write(f"- 👤 {msg3}")
                        st.success("Enriquecimiento completado.")
                        st.rerun()
                # --- Mostrar grafo ---
                if st.button(f"Ver grafo de {p.name}", key=f"graph_{p.id}"):
                    try:
                        graph_path = build_graph_for_person(p.id)
                        with open(graph_path, "r", encoding="utf-8") as f:
                            components.html(f.read(), height=700, scrolling=True)
                    except Exception as e:
                        st.error(f"Error generando grafo: {e}")
