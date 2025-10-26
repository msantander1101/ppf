# ui/modules/person_ui.py
"""
Módulo UI — Investigación y gestión OSINT de personas.
Integra IA, buscadores, filtraciones, redes sociales y enriquecimiento automático.
"""

import streamlit as st
from sqlmodel import select
from core.database import get_session
from core.entities import Person, Email, Profile, Relation, SearchLog
from modules.search.buscadores import search_general
from utils.logger import logger
from datetime import datetime
from modules.ai.intel_assistant import analyze_results_with_ai  # 🧠 IA
from modules.search.hibp import search_hibp  # 💀 Have I Been Pwned
from modules.relations.utils import add_relation
import pandas as pd
import json
import re


# ==========================================================
# 🔹 INTERFAZ PRINCIPAL
# ==========================================================
def run(username: str):
    st.subheader("🧍 Investigación de Personas — Huella Digital")
    st.caption("Registra, busca y analiza la huella digital completa de una persona en fuentes abiertas OSINT.")

    tab1, tab2, tab3 = st.tabs(["📋 Lista", "➕ Nueva persona", "🔍 Búsqueda libre OSINT"])

    with tab1:
        _show_person_table(username)

    with tab2:
        _add_new_person(username)

    with tab3:
        _search_osint_interface(username)


# ==========================================================
# 📋 LISTADO DE PERSONAS
# ==========================================================
from sqlalchemy.orm import joinedload
def _show_person_table(username: str):
    from sqlalchemy.orm import joinedload

    with get_session() as session:
        persons = session.exec(
            select(Person)
            .options(
                joinedload(Person.emails),
                joinedload(Person.profiles)
            )
        ).all()

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
    st.dataframe(df, use_container_width=True, hide_index=True)

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
        csv = df.to_csv(index=False)
        st.download_button("📥 Descargar CSV", data=csv.encode("utf-8"), file_name="personas_osint.csv", mime="text/csv")
# ==========================================================
# ➕ NUEVA PERSONA
# ==========================================================
def _add_new_person(username: str):
    """Formulario para añadir una nueva persona a la base de datos."""
    with st.form("new_person_form"):
        st.markdown("### ➕ Registrar nueva persona")
        name = st.text_input("👤 Nombre completo")
        notes = st.text_area("🗒️ Notas o contexto adicional")
        emails = st.text_area("📧 Correos asociados (uno por línea)")
        profiles = st.text_area("🌐 Perfiles o identificadores (plataforma:handle)")

        submitted = st.form_submit_button("✅ Guardar Persona")

        if not submitted:
            return

        # === Validación ===
        if not name.strip():
            st.warning("El nombre es obligatorio.")
            return

        # === Inserción en base de datos ===
        try:
            with get_session() as session:
                # Crear persona
                new_person = Person(
                    name=name.strip(),
                    notes=notes.strip() if notes else ""
                )
                session.add(new_person)
                session.flush()  # 🔹 Esto asigna ID sin cerrar la transacción

                # Agregar emails
                for e in emails.splitlines():
                    e = e.strip()
                    if e:
                        session.add(Email(address=e, person_id=new_person.id))

                # Agregar perfiles sociales
                for line in profiles.splitlines():
                    if ":" in line:
                        platform, handle = line.split(":", 1)
                        platform, handle = platform.strip(), handle.strip()
                        session.add(Profile(platform=platform, handle=handle, person_id=new_person.id))

                # Confirmar todo
                session.commit()

            logger.info(f"[person_ui] Persona '{name}' añadida correctamente por {username}")
            st.success(f"✅ Persona '{name}' guardada con éxito.")
            st.balloons()
            st.rerun()

        except Exception as e:
            logger.exception(f"[person_ui] Error al añadir persona: {e}")
            st.error(f"❌ Error al guardar la persona: {e}")


# ==========================================================
# 👁️ DETALLE DE PERSONA Y BÚSQUEDA
# ==========================================================
def _view_person_detail(username: str, person_id: str):
    from sqlalchemy.orm import joinedload

    # 🚀 Cargar persona + emails + perfiles en una sola consulta (sin lazy loading)
    with get_session() as session:
        person = session.exec(
            select(Person)
            .options(
                joinedload(Person.emails),
                joinedload(Person.profiles)
            )
            .where(Person.id == int(person_id))
        ).first()

    if not person:
        st.error("Persona no encontrada.")
        return

    # === Datos principales ===
    st.markdown(f"### 👤 {person.name}")
    st.caption(f"🕒 Creado el {person.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    if person.notes:
        st.info(person.notes)

    # === Emails ===
    st.markdown("#### 📧 Emails")
    if person.emails:
        for e in person.emails:
            st.write(f"- {e.address}")
    else:
        st.warning("Sin correos asociados.")

    # === Perfiles ===
    st.markdown("#### 🌐 Perfiles")
    if person.profiles:
        for p in person.profiles:
            url = p.url or f"https://{p.platform}.com/{p.handle}"
            st.markdown(f"- [{p.platform}]({url}) → {p.handle}")
    else:
        st.warning("Sin perfiles registrados.")

    # === Bloque de búsquedas OSINT ===
    st.markdown("---")
    st.subheader("🧠 Análisis y Huella Digital")

    cols = st.columns(6)
    if cols[0].button("📄 Docs"):
        _execute_search(username, person, "docs")
    if cols[1].button("🧾 Pastes"):
        _execute_search(username, person, "pastes")
    if cols[2].button("👥 Social"):
        _execute_search(username, person, "social")
    if cols[3].button("💻 Code"):
        _execute_search(username, person, "code")
    if cols[4].button("🕰️ Histórico"):
        _execute_search(username, person, "historical")
    if cols[5].button("🔍 General"):
        _execute_search(username, person, "general")

    st.markdown("---")
    _show_relations(person_id)



# ==========================================================
# 🧩 FUNCIONES DE BÚSQUEDA DETALLADA
# ==========================================================
def _execute_search(username: str, person: Person, mode: str):
    st.info(f"Buscando información tipo **{mode}** para {person.name}...")

    queries = {
        "docs": f'"{person.name}" (filetype:pdf OR filetype:docx)',
        "pastes": f'"{person.name}" site:pastebin.com OR site:ghostbin.com OR site:hastebin.com',
        "social": f'"{person.name}" site:twitter.com OR site:linkedin.com OR site:facebook.com',
        "code": f'"{person.name}" site:github.com OR site:gitlab.com',
        "historical": f'"{person.name}" site:web.archive.org OR site:archive.is',
        "general": f'"{person.name}" OR "{person.name}" + contacto OR perfil'
    }

    query = queries.get(mode, person.name)
    results = search_general(query, username=username, max_results=15)

    hibp_results = []
    for e in person.emails:
        hibp_data = search_hibp(e.address, username)
        if hibp_data:
            hibp_results.append({"source": "HIBP", "data": hibp_data})

    _render_osint_results(username, person, results + hibp_results, mode)


# ==========================================================
# 📊 MOSTRAR RESULTADOS Y ACCIONES
# ==========================================================
def _render_osint_results(username: str, person: Person, results: list, mode: str):
    if not results:
        st.warning("Sin resultados.")
        return

    st.subheader(f"📋 Resultados — {len(results)} hallazgos")

    for idx, r in enumerate(results):
        title = r.get("title", r.get("source", "Sin título"))
        link = r.get("link", "")
        snippet = r.get("snippet", r.get("data", ""))

        with st.expander(f"{idx+1}. {title[:100]}"):
            if link:
                st.markdown(f"🔗 [Abrir enlace]({link})")
            if isinstance(snippet, dict):
                st.json(snippet)
            else:
                st.caption(snippet)

            cols = st.columns(3)
            if cols[0].button("➕ Añadir al grafo", key=f"add_{idx}"):
                add_relation(username, f"person:{person.id}", f"url:{link or title}", f"found_in_{mode}")
                st.success("Relación añadida.")
            if cols[1].button("🧠 Enriquecer", key=f"enrich_{idx}"):
                _auto_enrich(username, person, link or title)
            if cols[2].button("🗑️ Borrar", key=f"delete_{idx}"):
                st.info("Resultado descartado.")

    with get_session() as session:
        log = SearchLog(
            query=f"osint:{mode}:{person.name}",
            result=json.dumps(results, ensure_ascii=False),
            user_id=None,
            type="osint_search",
            created_at=datetime.utcnow()
        )
        session.add(log)
        session.commit()

    st.markdown("---")
    if st.button("🧠 Analizar con IA los resultados"):
        ai_summary = analyze_results_with_ai(results)
        st.markdown("### 🧩 Resumen Inteligente (IA)")
        st.write(ai_summary)


# ==========================================================
# 🔗 RELACIONES
# ==========================================================
def _show_relations(person_id: str):
    with get_session() as session:
        rels = session.exec(select(Relation).where(Relation.source_id == f"person:{person_id}")).all()

    if not rels:
        st.info("No hay relaciones asociadas a esta persona.")
        return

    st.markdown("#### 🔗 Relaciones detectadas")
    for r in rels:
        st.write(f"- **{r.relation}** → {r.target_id} ({r.created_at.strftime('%Y-%m-%d')})")

    if st.button("❌ Eliminar todas las relaciones"):
        with get_session() as session:
            for r in rels:
                session.delete(r)
            session.commit()
        st.warning("Relaciones eliminadas.")
        st.rerun()


# ==========================================================
# 🧠 ENRIQUECIMIENTO AUTOMÁTICO
# ==========================================================
def _auto_enrich(username: str, person: Person, value: str):
    if "@" in value:
        enrich_type = "email"
    elif any(k in value for k in ["github.com", "linkedin.com", "twitter.com"]):
        enrich_type = "profile"
    else:
        enrich_type = "domain"

    add_relation(username, f"person:{person.id}", f"{enrich_type}:{value}", f"auto_enrich_{enrich_type}")
    st.success(f"🧠 Enriquecimiento automático lanzado para {enrich_type}.")


# ==========================================================
# 🔍 INTERFAZ DE BÚSQUEDA LIBRE OSINT
# ==========================================================
def _search_osint_interface(username: str):
    """Interfaz libre para consultar fuentes OSINT sin necesidad de persona registrada."""
    st.markdown("### 🔎 Búsqueda libre OSINT")
    query = st.text_input("Introduce un nombre, correo, dominio o alias social", key="free_osint_input")
    engine = st.selectbox("Buscador", ["auto", "google", "bing", "duckduckgo"], index=0)
    limit = st.slider("Número máximo de resultados", 5, 50, 15)

    if st.button("🚀 Buscar"):
        if not query.strip():
            st.warning("Introduce una consulta válida.")
            return
        with st.spinner("Buscando en múltiples fuentes..."):
            results = _osint_query(username, query, engine, limit)
            if results:
                _render_osint_results(username, None, results, "manual")
            else:
                st.info("Sin resultados relevantes.")


def _osint_query(username: str, query: str, engine: str = "auto", limit: int = 15):
    """Detecta tipo de dato y genera dorks automáticos."""
    if re.match(r"[^@]+@[^@]+\.[^@]+", query):
        qtype = "email"
    elif re.match(r"^\+?\d{7,15}$", query):
        qtype = "phone"
    elif re.match(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", query):
        qtype = "domain"
    else:
        qtype = "person"

    dorks = {
        "person": f'"{query}" site:linkedin.com OR site:twitter.com OR site:facebook.com',
        "email": f'"{query}" site:pastebin.com OR site:github.com',
        "phone": f'"{query}" site:telegram.org OR site:facebook.com',
        "domain": f'site:{query} OR "{query}" inurl:login OR contact'
    }

    try:
        results = search_general(dorks.get(qtype, query), username=username, max_results=limit)
    except Exception as e:
        st.error(f"Error ejecutando búsqueda: {e}")
        results = []

    return results
