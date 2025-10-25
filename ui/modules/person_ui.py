# ui/modules/person_ui.py
"""
Módulo UI — Gestión y búsqueda OSINT de personas.
Integra buscadores automáticos y generación de dorks por IA para búsquedas enfocadas
en la huella digital de personas (docs, pastes, social, code, historic, general).
"""

import re
import json
from datetime import datetime

import streamlit as st
import pandas as pd
from sqlmodel import select
from sqlalchemy.orm import selectinload

from utils.logger import logger

# Importar funciones/entidades del core
from core.database import get_session
from core.entities import Person, Email, Profile, Relation, SearchLog, User

# Integración buscadores y IA
from modules.search.buscadores import search_buscador
# Si implementaste el generador IA propuesto, se importará:
try:
    from modules.ai.dork_generator import generate_dorks
except Exception:
    generate_dorks = None  # en caso de que no exista, se usan consultas simples


# ==========================================================
# 🔹 INTERFAZ PRINCIPAL
# ==========================================================
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


# ==========================================================
# 📋 LISTADO DE PERSONAS
# ==========================================================
def _show_person_table(username: str):
    # Cargamos personas con relaciones necesarias para evitar DetachedInstanceError
    with get_session() as session:
        stmt = select(Person).options(selectinload(Person.emails), selectinload(Person.profiles))
        persons = session.exec(stmt).all()

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
            "Creado": p.created_at.strftime("%Y-%m-%d %H:%M:%S") if p.created_at else "—"
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
        if st.button("💾 Exportar CSV"):
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Descargar CSV",
                data=csv.encode("utf-8"),
                file_name="personas_osint.csv",
                mime="text/csv",
            )


# ==========================================================
# ➕ NUEVA PERSONA
# ==========================================================
def _add_new_person(username: str):
    with st.form("new_person_form"):
        name = st.text_input("👤 Nombre completo")
        notes = st.text_area("🗒️ Notas o contexto")
        email_list = st.text_area("📧 Correos asociados (uno por línea)")
        profiles_data = st.text_area("🌐 Perfiles o identificadores (plataforma:handle)")
        submitted = st.form_submit_button("✅ Guardar Persona")

        if submitted:
            if not name or not name.strip():
                st.warning("El campo nombre es obligatorio.")
                return

            with get_session() as session:
                new_person = Person(name=name.strip(), notes=notes.strip() if notes else "")
                session.add(new_person)
                session.commit()
                # refrescar para obtener id
                session.refresh(new_person)

                # Añadir emails
                for e in email_list.splitlines():
                    e = e.strip()
                    if e:
                        session.add(Email(address=e, person_id=new_person.id))

                # Añadir perfiles
                for line in profiles_data.splitlines():
                    if ":" in line:
                        platform, handle = line.split(":", 1)
                        session.add(Profile(platform=platform.strip(), handle=handle.strip(), person_id=new_person.id))

                session.commit()
                logger.info(f"Nueva persona registrada: {name}")
                st.success(f"✅ Persona '{name}' añadida correctamente.")
                st.rerun()


# ==========================================================
# 👁️ DETALLE DE PERSONA
# ==========================================================
def _view_person_detail(username: str, person_id: str):
    with get_session() as session:
        # cargar persona con relaciones
        stmt = select(Person).where(Person.id == int(person_id)).options(selectinload(Person.emails), selectinload(Person.profiles))
        person = session.exec(stmt).first()

    if not person:
        st.error("Persona no encontrada.")
        return

    st.markdown(f"### 👤 {person.name}")
    st.caption(f"🕒 Creado el {person.created_at.strftime('%Y-%m-%d %H:%M:%S') if person.created_at else '—'}")
    if person.notes:
        st.info(person.notes)

    st.markdown("#### 📧 Emails")
    if person.emails:
        for e in person.emails:
            st.write(f"- {e.address}")
    else:
        st.warning("Sin correos asociados.")

    st.markdown("#### 🌐 Perfiles")
    if person.profiles:
        for p in person.profiles:
            url = p.url or f"https://{p.platform}.com/{p.handle}"
            st.markdown(f"- [{p.platform}]({url}) → {p.handle}")
    else:
        st.warning("Sin perfiles sociales registrados.")

    st.markdown("---")

    # === BÚSQUEDA RÁPIDA OSINT ===
    st.subheader("🔍 Ejecutar búsqueda OSINT")
    if st.button("🚀 Buscar Huella Digital"):
        with st.spinner("Ejecutando búsqueda OSINT..."):
            results = _osint_query(username, person)
            if results:
                _render_osint_results(username, person, results)
            else:
                st.warning("No se encontraron resultados relevantes.")

    st.markdown("---")
    _show_relations(person_id)


# ==========================================================
# 🔍 INTERFAZ DE BÚSQUEDA OSINT MANUAL
# ==========================================================
def _search_osint_interface(username: str):
    st.markdown("### 🔎 Búsqueda libre OSINT")
    query = st.text_input("Introduce un nombre, correo, dominio o alias social")
    if st.button("Buscar"):
        with st.spinner("Buscando en múltiples fuentes..."):
            results = _osint_query(username, query)
            if results:
                _render_osint_results(username, None, results)
            else:
                st.warning("Sin resultados.")


# ==========================================================
# 🧠 FUNCIÓN CENTRAL DE BÚSQUEDA
# ==========================================================
def _osint_query(username, person_or_query):
    """
    Determina el tipo de búsqueda y ejecuta buscadores OSINT.
    Usa dorks generados por IA si el módulo está disponible.
    """
    # Determinar query base
    if isinstance(person_or_query, Person):
        query = person_or_query.name
    else:
        query = str(person_or_query)

    # Detección del tipo de dato
    if re.match(r"[^@]+@[^@]+\.[^@]+", query):
        query_type = "email"
    elif re.match(r"^\+?\d{7,15}$", query):
        query_type = "phone"
    elif re.match(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", query):
        query_type = "domain"
    else:
        query_type = "person"

    # Generar dorks con IA (si está disponible)
    dorks = None
    if generate_dorks:
        try:
            dorks = generate_dorks(query_type, query)
        except Exception as e:
            logger.warning(f"[person_ui] Error generando dorks IA: {e}")
            dorks = None

    # Fallback a dorks simples si IA no disponible o falla
    if not dorks:
        # estructura esperada: { "google": [...], "bing": [...], "duckduckgo": [...] }
        fallback = f'"{query}"'
        dorks = {
            "google": [fallback + " site:linkedin.com OR site:twitter.com", fallback + " filetype:pdf OR filetype:docx"],
            "bing": [fallback + " site:pastebin.com OR site:github.com"],
            "duckduckgo": [fallback + " leak OR breach OR paste"]
        }

    results = []
    max_results = 12

    # Ejecutar búsquedas en los distintos motores (siempre que haya implementaciones en buscadores)
    for engine, queries in dorks.items():
        for q in queries:
            # Mensaje en UI para trazabilidad
            st.write(f"🔎 Ejecutando búsqueda en **{engine.title()}** con dork: `{q}`")
            try:
                partial = search_buscador(q, username=username, engine=engine, max_results=max_results)
                if partial:
                    results.extend(partial)
            except Exception as e:
                logger.exception(f"[person_ui] Error ejecutando buscador {engine} con dork `{q}`: {e}")

    # eliminar duplicados por link
    seen = set()
    unique_results = []
    for r in results:
        link = r.get("link") or r.get("url") or r.get("href") or json.dumps(r, ensure_ascii=False)
        if link not in seen:
            seen.add(link)
            unique_results.append(r)

    return unique_results


# ==========================================================
# 📊 MOSTRAR RESULTADOS OSINT
# ==========================================================
def _render_osint_results(username, person, results):
    st.info(f"🔍 {len(results)} resultados agregados de múltiples motores.")
    for idx, r in enumerate(results, start=1):
        title = r.get("title") or r.get("name") or r.get("link") or f"Resultado {idx}"
        link = r.get("link") or r.get("url") or ""
        snippet = r.get("snippet") or r.get("excerpt") or ""
        source = r.get("source") or ""

        with st.expander(f"🌐 {title}"):
            if link:
                st.markdown(f"[Abrir enlace]({link})")
            if snippet:
                st.caption(snippet)

            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                if st.button("➕ Añadir al grafo", key=f"add_graph_{idx}_{hash(link)}"):
                    # Añadir relación básica entre persona y resultado
                    origin = f"person:{person.id}" if person else f"search:{datetime.utcnow().timestamp()}"
                    target = f"url:{link}" if link else f"result:{idx}"
                    _add_relation_simple(origin, target, "found_in", username)
                    st.success("Añadido al grafo.")
            with c2:
                if st.button("🧠 Enriquecer", key=f"enrich_{idx}_{hash(link)}"):
                    # Lanzar enriquecimiento automático según contenido detectado (email, perfil, dominio...)
                    _launch_enrich_from_result(username, person, r)
                    st.info("Enriquecimiento lanzado (ver logs).")
            with c3:
                if st.button("🔗 Copiar enlace", key=f"copy_{idx}_{hash(link)}"):
                    try:
                        st.write(link)
                        st.success("Enlace mostrado (usa tu gestor de portapapeles).")
                    except Exception:
                        st.error("No se pudo copiar el enlace.")

    # Guardar en logs de búsqueda
    try:
        with get_session() as session:
            user = None
            if username:
                user = session.exec(select(User).where(User.username == username)).first()

            log = SearchLog(
                query=f"osint:{person.name if person else 'manual'}",
                result=json.dumps(results, ensure_ascii=False),
                user_id=user.id if user else None,
                type="osint_search",
                created_at=datetime.utcnow()
            )
            session.add(log)
            session.commit()
            logger.info(f"[person_ui] Guardados {len(results)} resultados OSINT en SearchLog.")
    except Exception as e:
        logger.exception(f"[person_ui] Error guardando SearchLog: {e}")


# ==========================================================
# 🔗 RELACIONES Y ENRIQUECIMIENTO RÁPIDO
# ==========================================================
def _show_relations(person_id: str):
    with get_session() as session:
        rels = session.exec(select(Relation).where(Relation.source_id == f"person:{person_id}")).all()

    if not rels:
        st.info("No hay relaciones asociadas a esta persona.")
        return

    st.markdown("#### 🔗 Relaciones detectadas")
    for r in rels:
        st.write(f"- **{r.relation}** → {r.target_id} ({r.created_at.strftime('%Y-%m-%d') if r.created_at else '—'})")

    if st.button("❌ Eliminar todas las relaciones de esta persona"):
        with get_session() as session:
            for r in rels:
                session.delete(r)
            session.commit()
        st.warning("Relaciones eliminadas.")
        st.rerun()


def _add_relation_simple(source_id: str, target_id: str, relation_type: str, username: str = None):
    """
    Inserta una relación sencilla en la tabla Relation.
    """
    try:
        with get_session() as session:
            rel = Relation(
                source_id=source_id,
                target_id=target_id,
                relation=relation_type,
                created_at=datetime.utcnow()
            )
            session.add(rel)
            session.commit()
    except Exception as e:
        logger.exception(f"[person_ui] Error creando relación {source_id} -> {target_id}: {e}")


def _launch_enrich_from_result(username, person, result):
    """
    Detecta el tipo de dato en el resultado y lanza funciones de enriquecimiento
    (esto debe mapearse a tu módulo enrichment existente).
    """
    try:
        # Detección simple
        link = result.get("link") or result.get("url") or ""
        title = result.get("title", "")
        snippet = result.get("snippet", "")

        # Email en el resultado
        m = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", f"{title} {snippet} {link}")
        if m:
            email = m.group(1)
            # Llamar a tu enriquecimiento de email si existe
            try:
                from core import enrichment
                enrichment.enrich_email(username, email)
                logger.info(f"[person_ui] Enriquecimiento lanzado para email {email}")
            except Exception as e:
                logger.warning(f"[person_ui] enrichment.enrich_email no disponible: {e}")
            return

        # Perfil en dominio conocido (github, linkedin, twitter)
        if "github.com" in link or "gitlab.com" in link:
            try:
                from core import enrichment
                enrichment.enrich_github_profile(username, link)
                logger.info(f"[person_ui] Enriquecimiento lanzado para perfil técnico {link}")
            except Exception:
                logger.warning("enrich_github_profile no disponible.")
            return

        if "linkedin.com" in link or "twitter.com" in link:
            try:
                from core import enrichment
                enrichment.enrich_social_profile(username, link)
                logger.info(f"[person_ui] Enriquecimiento lanzado para perfil social {link}")
            except Exception:
                logger.warning("enrich_social_profile no disponible.")
            return

        # Dominio genérico -> enriquecer dominio
        if link and (re.match(r"^https?://", link) or "." in link):
            domain = link.split("/")[2] if link.startswith("http") else link
            try:
                from core import enrichment
                enrichment.enrich_domain(username, domain)
                logger.info(f"[person_ui] Enriquecimiento lanzado para dominio {domain}")
            except Exception:
                logger.warning("enrich_domain no disponible.")
            return

        # Si no se detecta nada específico, registro informativo
        logger.info("[person_ui] Resultado sin tipo detectable para auto-enrich.")
    except Exception as e:
        logger.exception(f"[person_ui] Error en _launch_enrich_from_result: {e}")
