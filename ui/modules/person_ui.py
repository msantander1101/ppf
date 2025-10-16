import streamlit as st
from sqlmodel import select

from core.database import get_session
from core.entities import Person, Email, Profile
from utils.logger import logger
from modules.graph.builder import build_graph_html_for_person
import streamlit.components.v1 as components

def run(username: str):
    st.header("Personas / Huella digital")
    st.info("Crea una entidad persona y lanza pipelines de enriquecimiento.")

    with st.form("create_person"):
        name = st.text_input("Nombre completo")
        notes = st.text_area("Notas (opcional)")
        submit = st.form_submit_button("Crear persona")
        if submit:
            if not name.strip():
                st.warning("Introduce un nombre.")
            else:
                with get_session() as session:
                    p = Person(name=name.strip(), notes=notes.strip() or None)
                    session.add(p)
                    session.commit()
                    st.success(f"Persona creada: {p.name} (id={p.id})")
                    st.experimental_rerun()

    st.markdown("### Personas existentes")
    with get_session() as session:
        persons = session.exec(select(Person)).all()
        for p in persons:
            cols = st.columns([4,1,1])
            cols[0].write(f"**{p.name}** (id={p.id})")
            if cols[1].button("Ver", key=f"view_{p.id}"):
                st.session_state.selected_person = p.id
                st.rerun()
            if cols[2].button("Grafo", key=f"graph_{p.id}"):
                path = build_graph_html_for_person(p.id)
                components.html(open(path,'r',encoding='utf-8').read(), height=800)

    if st.session_state.get("selected_person"):
        pid = st.session_state.selected_person
        with get_session() as session:
            p = session.get(Person, pid)
            st.subheader(f"Detalles: {p.name}")
            st.write("Notas:", p.notes)
            st.write("Emails:")
            for e in p.emails:
                st.write("-", e.address)
            st.write("Profiles:")
            for pr in p.profiles:
                st.write("-", f"{pr.platform} - {pr.handle} ({pr.url})")
            if st.button("Construir grafo"):
                path = build_graph_html_for_person(pid)
                components.html(open(path,'r',encoding='utf-8').read(), height=800)
