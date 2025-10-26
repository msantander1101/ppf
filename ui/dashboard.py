
import streamlit as st
from core.auth import get_current_user, logout_user
from ui.modules import person_ui, auto_enrich_ui, history_ui, graph_ui, settings_ui
from utils.logger import logger


def run():
    # ==========================================================
    # 🧍 CONTROL DE SESIÓN
    # ==========================================================
    user = get_current_user()
    if not user:
        st.warning("⚠️ No has iniciado sesión. Por favor, accede con tus credenciales.")
        st.switch_page("login.py")
        st.stop()

    username = user["username"]
    # ==========================================================
    # 🧭 ENCABEZADO
    # ==========================================================
    st.set_page_config(page_title="OSINT Suite — Dashboard", page_icon="🧩", layout="wide")
    st.title("🧩 OSINT Suite — Panel principal")
    st.caption(f"Bienvenido, **{username}**")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.info("Selecciona una sección para comenzar el análisis OSINT.")
    with col2:
        if st.button("🚪 Cerrar sesión"):
            logout_user()
            st.success("Sesión cerrada correctamente.")
            st.switch_page("login.py")
            st.stop()

    st.markdown("---")

    # ==========================================================
    # 📁 SECCIONES PRINCIPALES
    # ==========================================================
    tabs = st.tabs([
        "🧍 Personas",
        "🧠 Auto-Enriquecimiento",
        "📜 Historial",
        "🌐 Grafo Global",
        "⚙️ Configuración"
    ])

    with tabs[0]:
        person_ui.run(username)

    with tabs[1]:
        st.subheader("🧠 Enriquecimiento automático de entidades")
        entity_type = st.selectbox("Tipo de entidad", ["person", "email", "domain"])
        entity_value = st.text_input("Valor de la entidad", placeholder="Ej. msantander@example.com o dominio.com")

        if st.button("🧩 Ejecutar enriquecimiento"):
            if entity_value.strip():
                auto_enrich_ui.run(username, entity_type, entity_value)
            else:
                st.warning("Introduce un valor válido para la entidad.")

    with tabs[2]:
        history_ui.run(username)

    with tabs[3]:
        graph_ui.run(username)

    with tabs[4]:
        settings_ui.run(username)
