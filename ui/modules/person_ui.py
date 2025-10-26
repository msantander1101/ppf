# ui/modules/person_ui.py
"""
Módulo UI — Investigación y gestión OSINT de personas.
Versión mejorada con progreso visual, autoenriquecimiento activo y persistencia de búsqueda.
"""

import streamlit as st
from sqlmodel import select
from sqlalchemy.orm import joinedload
from core.database import get_session
from core.entities import Person, Email, Profile, Relation, SearchLog
from modules.search.buscadores import search_general
from modules.search.hibp import search_hibp
from modules.ai.intel_assistant import analyze_results_with_ai
from modules.relations.utils import add_relation
from utils.logger import logger
from datetime import datetime
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
        if "selected_person_id" not in st.session_state:
            st.session_state["selected_person_id"] = None

        # Mostrar tabla o detalle según el estado
        if st.session_state["selected_person_id"] is None:
            _show_person_table(username)
        else:
            _view_person_detail(username, st.session_state["selected_person_id"])

    with tab2:
        _add_new_person(username)

    with tab3:
        _search_osint_interface(username)


# ==========================================================
# 📋 LISTADO DE PERSONAS
# ==========================================================
def _show_person_table(username: str):
    """Lista de personas registradas y gestión de detalle sin recarga completa."""
    with get_session() as session:
        persons = session.exec(
            select(Person)
            .options(joinedload(Person.emails), joinedload(Person.profiles))
        ).unique().all()

    if not persons:
        st.info("No hay personas registradas todavía.")
        return

    # ----------------------------------------------------------
    # Tabla principal
    # ----------------------------------------------------------
    data = [
        {
            "ID": p.id,
            "Nombre": p.name,
            "Emails": ", ".join([e.address for e in (p.emails or [])]),
            "Perfiles": ", ".join([f"{pr.platform}:{pr.handle}" for pr in (p.profiles or [])]),
            "Notas": p.notes or "",
            "Creado": p.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
        for p in persons
    ]

    df = pd.DataFrame(data)
    st.dataframe(df, width="stretch", hide_index=True)

    # ----------------------------------------------------------
    # Panel de acciones
    # ----------------------------------------------------------
    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    with col1:
        person_id = st.text_input("ID de persona a gestionar", key="input_manage_id")
        if st.button("👁️ Ver Detalles", key="btn_view_person"):
            if person_id.strip():
                try:
                    st.session_state["active_person_id"] = int(person_id.strip())
                    st.session_state["show_detail"] = True
                    st.toast(f"Mostrando detalles de persona ID {person_id}")
                except ValueError:
                    st.warning("El ID debe ser un número válido.")
            else:
                st.warning("Introduce un ID válido.")

    with col2:
        if st.button("🔄 Refrescar lista"):
            st.rerun()

    with col3:
        csv = df.to_csv(index=False)
        st.download_button(
            "📥 Descargar CSV",
            data=csv.encode("utf-8"),
            file_name="personas_osint.csv",
            mime="text/csv",
        )

    # ----------------------------------------------------------
    # Mostrar detalles sin recargar toda la app
    # ----------------------------------------------------------
    if st.session_state.get("show_detail") and st.session_state.get("active_person_id"):
        selected_id = st.session_state["active_person_id"]
        _view_person_detail(username, selected_id)

# ==========================================================
# ➕ NUEVA PERSONA
# ==========================================================
def _add_new_person(username: str):
    with st.form("new_person_form"):
        st.markdown("### ➕ Registrar nueva persona")
        name = st.text_input("👤 Nombre completo")
        notes = st.text_area("🗒️ Notas o contexto adicional")
        emails = st.text_area("📧 Correos asociados (uno por línea)")
        profiles = st.text_area("🌐 Perfiles o identificadores (plataforma:handle)")
        submitted = st.form_submit_button("✅ Guardar Persona")

        if not submitted:
            return

        if not name.strip():
            st.warning("El nombre es obligatorio.")
            return

        try:
            with get_session() as session:
                new_person = Person(name=name.strip(), notes=notes.strip() if notes else "")
                session.add(new_person)
                session.flush()

                for e in emails.splitlines():
                    e = e.strip()
                    if e:
                        session.add(Email(address=e, person_id=new_person.id))

                for line in profiles.splitlines():
                    if ":" in line:
                        platform, handle = line.split(":", 1)
                        session.add(Profile(platform=platform.strip(), handle=handle.strip(), person_id=new_person.id))

                session.commit()

            logger.info(f"[person_ui] Persona '{name}' añadida correctamente por {username}")
            st.success(f"✅ Persona '{name}' guardada con éxito.")
            st.balloons()
            st.session_state["person_added"] = True
            st.rerun()

        except Exception as e:
            logger.exception(f"[person_ui] Error al añadir persona: {e}")
            st.error(f"❌ Error al guardar la persona: {e}")


# ==========================================================
# 👁️ DETALLE DE PERSONA Y BÚSQUEDA
# ==========================================================
def _view_person_detail(username: str, person_id: str):
    with get_session() as session:
        person = session.exec(
            select(Person)
            .options(joinedload(Person.emails), joinedload(Person.profiles))
            .where(Person.id == int(person_id))
        ).unique().first()

    if not person:
        st.error("Persona no encontrada.")
        return

    st.markdown(f"### 👤 {person.name}")
    st.caption(f"🕒 Creado el {person.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
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
        st.warning("Sin perfiles registrados.")

    st.markdown("---")
    st.subheader("🧠 Análisis y Huella Digital")

    cols = st.columns(6)
    botones = ["docs", "pastes", "social", "code", "historical", "general"]
    emojis = ["📄", "🧾", "👥", "💻", "🕰️", "🔍"]

    for i, mode in enumerate(botones):
        if cols[i].button(f"{emojis[i]} {mode.capitalize()}", key=f"btn_{mode}_{person_id}"):
            st.session_state["active_person_id"] = person_id
            st.session_state["active_mode"] = mode

    # 🚀 Ejecutar búsqueda si hay modo activo y coincide la persona
    if (
        st.session_state.get("active_person_id") == person_id
        and st.session_state.get("active_mode")
    ):
        mode = st.session_state["active_mode"]
        _execute_search(username, person, mode)
        st.session_state.pop("active_mode", None)
        st.session_state.pop("active_person_id", None)

    st.markdown("---")
    _show_relations(person_id)
    if st.button("⬅️ Volver a la lista"):
        st.session_state["selected_person_id"] = None
        st.rerun()


# ==========================================================
# 🧩 FUNCIONES DE BÚSQUEDA CON PROGRESO VISUAL
# ==========================================================
import time
import json
from datetime import datetime
from utils.logger import logger
from core.database import get_session
from core.entities import SearchLog

def _execute_search(username: str, person, mode: str):
    st.info(f"Buscando información tipo **{mode}** para {person.name}...")

    # ==========================================================
    # 🔹 Definición de consultas según el modo
    # ==========================================================
    queries = {
        "docs": f'"{person.name}" (filetype:pdf OR filetype:docx)',
        "pastes": f'"{person.name}" site:pastebin.com OR site:ghostbin.com OR site:hastebin.com',
        "social": f'"{person.name}" site:twitter.com OR site:linkedin.com OR site:facebook.com',
        "code": f'"{person.name}" site:github.com OR site:gitlab.com',
        "historical": f'"{person.name}" site:web.archive.org OR site:archive.is',
        "general": f'"{person.name}" OR "{person.name}" + contacto OR perfil'
    }

    query = queries.get(mode, person.name)
    results = []
    hibp_results = []

    # ==========================================================
    # 🔍 Búsqueda OSINT general (Google / SerpAPI)
    # ==========================================================
    try:
        results = search_general(query, username=username, max_results=15)
        logger.info(f"[OSINT] {len(results)} resultados obtenidos para '{person.name}' ({mode})")
    except Exception as e:
        logger.error(f"[OSINT] Error ejecutando búsqueda {mode}: {e}")
        st.error(f"Error en búsqueda OSINT ({mode}): {e}")

    # ==========================================================
    # 📧 Búsqueda HIBP (respetando rate limits)
    # ==========================================================
    if getattr(person, "emails", None):
        for email_obj in person.emails:
            try:
                hibp_data = search_hibp(email_obj.address, username)
                if hibp_data:
                    hibp_results.append({
                        "source": "HIBP",
                        "email": email_obj.address,
                        "data": hibp_data
                    })
                # Espera 2 segundos entre peticiones para evitar 429
                time.sleep(2)
            except Exception as e:
                logger.warning(f"[HIBP] Error procesando {email_obj.address}: {e}")

    # ==========================================================
    # 🧩 Mostrar resultados combinados
    # ==========================================================
    combined_results = results + hibp_results
    _render_osint_results(username, person, combined_results, mode)

    # ==========================================================
    # 🗂️ Guardar log de búsqueda (en base de datos)
    # ==========================================================
    try:
        with get_session() as session:
            log = SearchLog(
                query=f"osint:{mode}:{person.name}",
                result=json.dumps(combined_results, ensure_ascii=False),
                user_id=username,
                type="osint_search",
                created_at=datetime.utcnow()
            )
            session.add(log)
            session.commit()
            logger.info(f"[person_ui] Log guardado correctamente para {person.name}")
    except Exception as e:
        logger.warning(f"[person_ui] No se pudo guardar el log de búsqueda: {e}")

# ==========================================================
# 📊 MOSTRAR RESULTADOS
# ==========================================================
def _render_osint_results(username: str, person, results: list, mode: str):
    """
    Renderiza los resultados OSINT combinados (SerpAPI + HIBP)
    y permite enriquecer o vincularlos sin recargar la interfaz.
    """
    if not results:
        st.warning("Sin resultados.")
        return

    # ==============================================
    # 🔹 Mantener los resultados en sesión
    # ==============================================
    if "osint_results" not in st.session_state:
        st.session_state["osint_results"] = results
    else:
        # Si ya hay resultados, solo actualiza si son distintos
        if results != st.session_state["osint_results"]:
            st.session_state["osint_results"] = results

    results = st.session_state["osint_results"]
    st.subheader(f"📋 Resultados — {len(results)} hallazgos encontrados")

    # ==============================================
    # 🔸 Mostrar cada resultado con acciones
    # ==============================================
    for idx, r in enumerate(results):
        title = r.get("title") or r.get("source") or "Sin título"
        link = r.get("link", "")
        snippet = r.get("snippet") or r.get("data", "")
        source = r.get("source", "Desconocida")

        with st.expander(f"{idx + 1}. {title[:100]}"):
            st.caption(f"🗂️ Fuente: {source}")

            if link:
                st.markdown(f"🔗 [Abrir enlace]({link})", unsafe_allow_html=True)

            if isinstance(snippet, dict):
                st.json(snippet)
            else:
                st.caption(snippet)

            col1, col2, col3 = st.columns(3)
            # =====================================================
            # ➕ Añadir al grafo
            # =====================================================
            if col1.button("➕ Añadir al grafo", key=f"add_graph_{idx}"):
                add_relation(username, f"person:{person.id}", f"url:{link or title}", f"found_in_{mode}")
                st.session_state[f"added_{idx}"] = True
                st.success("Relación añadida al grafo.")

            # =====================================================
            # 🧠 Enriquecer (sin borrar resultados)
            # =====================================================
            if col2.button("🧠 Enriquecer", key=f"enrich_{idx}"):
                _auto_enrich(username, person, link or title)
                st.session_state[f"enriched_{idx}"] = True
                st.info("Enriquecimiento lanzado.")

            # =====================================================
            # 🗑️ Borrar resultado (sin recargar)
            # =====================================================
            if col3.button("🗑️ Ocultar", key=f"hide_{idx}"):
                if "hidden_results" not in st.session_state:
                    st.session_state["hidden_results"] = set()
                st.session_state["hidden_results"].add(idx)
                st.warning(f"Resultado {idx + 1} ocultado.")

    # Filtrar resultados ocultos
    if "hidden_results" in st.session_state:
        hidden = st.session_state["hidden_results"]
        visible_results = [r for i, r in enumerate(results) if i not in hidden]
        if len(visible_results) != len(results):
            st.session_state["osint_results"] = visible_results
            st.rerun()

    # ==============================================
    # 🧠 Análisis con IA (opcional)
    # ==============================================
    st.markdown("---")
    if st.button("🧩 Analizar con IA los resultados"):
        with st.spinner("Analizando con IA..."):
            ai_summary = analyze_results_with_ai(results)
            st.markdown("### 🧠 Resumen Inteligente (IA)")
            st.write(ai_summary)

    st.info("💾 Los resultados permanecen visibles incluso tras interacciones.")

# ==========================================================
# 🔗 RELACIONES
# ==========================================================
def _show_relations(person_id: str):
    """
    Muestra todas las relaciones asociadas a una persona,
    con actualización en tiempo real y presentación visual mejorada.
    """

    # ==========================================================
    # 🔄 Refrescar automáticamente si hay nuevos vínculos
    # ==========================================================
    if st.session_state.get("update_relations"):
        st.session_state["update_relations"] = False
        st.rerun()

    # ==========================================================
    # 📦 Cargar relaciones
    # ==========================================================
    with get_session() as session:
        rels = session.exec(
            select(Relation).where(Relation.source_id == f"person:{person_id}")
        ).all()

    st.markdown("#### 🔗 Relaciones detectadas")

    if not rels:
        st.info("No hay relaciones asociadas a esta persona todavía.")
        return

    # ==========================================================
    # 📊 Mostrar en formato tabla expandible
    # ==========================================================
    data = []
    for r in rels:
        data.append({
            "Relación": r.relation,
            "Destino": r.target_id,
            "Fecha": r.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })

    df = pd.DataFrame(data)

    with st.expander("📋 Ver tabla completa de relaciones", expanded=True):
        st.dataframe(df, width="stretch", hide_index=True)

    # ==========================================================
    # 🌳 Visualización jerárquica simplificada
    # ==========================================================
    st.markdown("#### 🌐 Vista jerárquica (simplificada)")

    grouped = {}
    for r in rels:
        rel_type = r.relation
        grouped.setdefault(rel_type, []).append(r.target_id)

    for rel_type, targets in grouped.items():
        with st.expander(f"🔸 {rel_type} ({len(targets)})", expanded=False):
            for t in targets:
                st.markdown(f"- {t}")

    # ==========================================================
    # 🗑️ Botón para limpiar relaciones
    # ==========================================================
    st.markdown("---")
    if st.button("❌ Eliminar todas las relaciones"):
        with get_session() as session:
            for r in rels:
                session.delete(r)
            session.commit()

        st.warning("Relaciones eliminadas permanentemente.")
        st.session_state["update_relations"] = True
        st.rerun()

    # ==========================================================
    # 🧩 Mostrar último enriquecimiento
    # ==========================================================
    if "last_enrichment" in st.session_state and st.session_state["last_enrichment"]:
        st.markdown("##### 🧠 Último enriquecimiento realizado")
        last = st.session_state["last_enrichment"][-1]
        st.info(
            f"Tipo: **{last['type']}** — Valor: `{last['value']}` — "
            f"⏱️ {last['timestamp'].split('T')[1][:8]}"
        )

# ==========================================================
# 🧠 ENRIQUECIMIENTO AUTOMÁTICO
# ==========================================================
def _auto_enrich(username: str, person: Person, value: str):
    """
    Enriquecimiento automático inteligente.
    Detecta el tipo de dato y crea relaciones sin duplicar ni recargar la interfaz.
    """

    # ================================================================
    # 🔍 Detección del tipo de dato
    # ================================================================
    if "@" in value:
        enrich_type = "email"
    elif any(k in value for k in ["github.com", "linkedin.com", "twitter.com", "facebook.com"]):
        enrich_type = "profile"
    elif value.startswith("http://") or value.startswith("https://"):
        enrich_type = "url"
    elif "." in value:
        enrich_type = "domain"
    else:
        enrich_type = "string"

    # ================================================================
    # 🧱 Prevención de duplicados (relaciones repetidas)
    # ================================================================
    existing_relations = set()
    with get_session() as session:
        rels = session.exec(
            select(Relation).where(Relation.source_id == f"person:{person.id}")
        ).all()
        for r in rels:
            existing_relations.add((r.target_id, r.relation))

    relation_key = (f"{enrich_type}:{value}", f"auto_enrich_{enrich_type}")
    if relation_key in existing_relations:
        st.info(f"🟡 Ya existe una relación de tipo **{enrich_type}** con este valor.")
        return

    # ================================================================
    # 🔗 Crear relación automáticamente
    # ================================================================
    try:
        add_relation(
            username,
            f"person:{person.id}",
            f"{enrich_type}:{value}",
            f"auto_enrich_{enrich_type}"
        )

        # Guardar en sesión
        if "last_enrichment" not in st.session_state:
            st.session_state["last_enrichment"] = []
        st.session_state["last_enrichment"].append({
            "type": enrich_type,
            "value": value,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Confirmación visual
        st.success(f"🧠 Enriquecimiento añadido correctamente → {enrich_type}: {value}")
        st.toast(f"Nuevo vínculo detectado: {enrich_type}", icon="🪄")

        # Actualizar relaciones visibles en tiempo real
        st.session_state["update_relations"] = True

    except Exception as e:
        logger.error(f"[person_ui] Error durante auto_enrich: {e}")
        st.error(f"❌ Error en el enriquecimiento: {e}")

# ==========================================================
# 🔍 BÚSQUEDA LIBRE OSINT (con persistencia)
# ==========================================================
def _search_osint_interface(username: str):
    st.markdown("### 🔎 Búsqueda libre OSINT")

    if "last_osint_query" not in st.session_state:
        st.session_state["last_osint_query"] = ""

    query = st.text_input(
        "Introduce un nombre, correo, dominio o alias social",
        value=st.session_state["last_osint_query"],
        key="free_osint_input"
    )
    engine = st.selectbox("Buscador", ["auto", "google", "bing", "duckduckgo"], index=0)
    limit = st.slider("Número máximo de resultados", 5, 50, 15)

    if st.button("🚀 Buscar"):
        if not query.strip():
            st.warning("Introduce una consulta válida.")
            return
        st.session_state["last_osint_query"] = query  # ✅ Guardar persistencia
        with st.spinner("Buscando en múltiples fuentes..."):
            results = _osint_query(username, query, engine, limit)
            if results:
                _render_osint_results(username, None, results, "manual")
            else:
                st.info("Sin resultados relevantes.")


def _osint_query(username: str, query: str, engine: str = "auto", limit: int = 15):
    st.info("Iniciando búsqueda OSINT libre...")
    progress = st.progress(0)
    status = st.empty()

    try:
        status.text("🧩 Analizando tipo de consulta...")
        if re.match(r"[^@]+@[^@]+\.[^@]+", query):
            qtype = "email"
        elif re.match(r"^\+?\d{7,15}$", query):
            qtype = "phone"
        elif re.match(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", query):
            qtype = "domain"
        else:
            qtype = "person"
        progress.progress(20)

        status.text(f"🧠 Generando dorks para tipo '{qtype}'...")
        dorks = {
            "person": f'"{query}" site:linkedin.com OR site:twitter.com OR site:facebook.com',
            "email": f'"{query}" site:pastebin.com OR site:github.com',
            "phone": f'"{query}" site:telegram.org OR site:facebook.com',
            "domain": f'site:{query} OR "{query}" inurl:login OR contact'
        }
        progress.progress(40)

        status.text("🌐 Consultando resultados con SerpApi...")
        results = search_general(dorks.get(qtype, query), username=username, max_results=limit)
        progress.progress(80)

        status.text("✅ Búsqueda completada con éxito.")
        progress.progress(100)
        return results

    except Exception as e:
        st.error(f"Error ejecutando búsqueda: {e}")
        logger.error(f"[OSINT manual] {e}")
        progress.empty()
        status.empty()
        return []
