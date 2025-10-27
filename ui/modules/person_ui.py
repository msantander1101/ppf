"""
Módulo: person_ui.py
-------------------------------------
Interfaz de búsqueda, enriquecimiento y análisis de personas para OSINT Suite.
Integración total con módulos de búsqueda (pastes, social, code, docs) y AI.
"""

import streamlit as st
from core.config import get_user_setting
from modules.search.buscadores import search_general
from modules.ai.intel_assistant import analyze_results_with_ai
from utils.logger import logger


# ==========================================================
# 🔹 Interfaz principal
# ==========================================================
def run(username: str):
    st.title("🕵️‍♂️ Análisis de Persona / Entidad")
    st.caption("Busca información en fuentes abiertas, documentos, redes sociales, repositorios y filtraciones.")

    # Mantener estado persistente entre ejecuciones
    if "search_results" not in st.session_state:
        st.session_state.search_results = []
    if "current_target" not in st.session_state:
        st.session_state.current_target = ""

    # ==========================================================
    # 🔍 Formulario de búsqueda
    # ==========================================================
    st.subheader("🔎 Búsqueda OSINT")

    persona = st.text_input("Nombre o entidad objetivo", st.session_state.current_target or "")
    max_results = st.slider("Número máximo de resultados", 5, 30, 15)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        buscar = st.button("🔍 Buscar")
    with col2:
        enrich = st.button("♻️ Auto-enriquecer")
    with col3:
        ai_analyze = st.button("🧠 Analizar con IA")
    with col4:
        clear = st.button("🧹 Limpiar resultados")

    # ==========================================================
    # 🎯 Ejecución de búsqueda
    # ==========================================================
    if buscar and persona.strip():
        try:
            st.session_state.current_target = persona.strip()
            with st.spinner("Buscando información OSINT..."):
                results = search_general(persona, username, "auto", max_results)
                st.session_state.search_results = results

            st.success(f"✅ Se encontraron {len(results)} resultados para **{persona}**")

        except Exception as e:
            st.error(f"❌ Error en la búsqueda: {e}")
            logger.exception(f"[person_ui] Error buscando: {e}")

    # ==========================================================
    # ♻️ Auto-enriquecimiento (búsquedas temáticas)
    # ==========================================================
    if enrich and persona.strip():
        try:
            st.session_state.current_target = persona.strip()
            st.info("🧩 Ejecutando enriquecimiento automático...")

            enrich_queries = [
                f'"{persona}" (filetype:pdf OR filetype:docx)',
                f'"{persona}" site:pastebin.com OR site:ghostbin.com',
                f'"{persona}" site:twitter.com OR site:linkedin.com OR site:facebook.com',
                f'"{persona}" site:github.com OR site:gitlab.com'
            ]

            all_results = []
            with st.spinner("Recopilando resultados de distintas fuentes..."):
                for q in enrich_queries:
                    all_results.extend(search_general(q, username, "auto", max_results // 2))

            st.session_state.search_results = all_results
            st.success(f"✅ Enriquecimiento completado ({len(all_results)} resultados combinados)")

        except Exception as e:
            st.error(f"❌ Error en el enriquecimiento: {e}")
            logger.exception(f"[person_ui] Error en auto-enrich: {e}")

    # ==========================================================
    # 🧠 Análisis con IA
    # ==========================================================
    if ai_analyze and st.session_state.search_results:
        try:
            with st.spinner("Analizando resultados con inteligencia artificial..."):
                analysis = analyze_results_with_ai(st.session_state.current_target, st.session_state.search_results, username)
            st.markdown("### 🧠 Informe generado por IA")
            st.write(analysis)

        except Exception as e:
            st.error(f"❌ Error durante el análisis con IA: {e}")
            logger.exception(f"[person_ui] Error IA: {e}")

    # ==========================================================
    # 🧹 Limpiar resultados
    # ==========================================================
    if clear:
        st.session_state.search_results = []
        st.session_state.current_target = ""
        st.info("🧹 Resultados limpiados.")

    # ==========================================================
    # 📊 Mostrar resultados (persistentes)
    # ==========================================================
    if st.session_state.search_results:
        st.markdown("---")
        st.subheader(f"📂 Resultados para: {st.session_state.current_target}")

        for i, item in enumerate(st.session_state.search_results, start=1):
            with st.expander(f"🔗 {i}. {item.get('title', 'Sin título')}"):
                st.markdown(f"**Fuente:** `{item.get('source', 'desconocida')}`")
                st.markdown(f"**URL:** [{item.get('link', 'Sin enlace')}]({item.get('link', '#')})")
                if item.get("snippet"):
                    st.markdown(f"📝 *{item.get('snippet')}*")

    else:
        st.info("🕵️‍♂️ Introduce un nombre y haz clic en **Buscar** para comenzar.")

    st.markdown("---")
    st.caption("🧩 OSINT Suite — Módulo de análisis de personas")
