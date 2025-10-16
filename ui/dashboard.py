from ui.modules import dorks_ui
import streamlit as st
from utils.logger import logger
from core.engine import engine
from ui.modules import person_ui

def main():
    st.set_page_config(page_title="Dashboard - OSINT Suite", page_icon="🕵️", layout="wide")

    if not st.session_state.get("logged_in"):
        st.warning("Debes iniciar sesión para acceder al dashboard.")
        st.stop()

    st.sidebar.title("🧭 Navegación")

    # Nota: Usamos "Configuración" con tilde de acuerdo al condicional más adelante. Asegúrate de que las etiquetas coincidan.
    page = st.sidebar.radio(
        "Selecciona módulo",
        [
            "Inicio",
            "Personas",
            "Dorks",
            "Búsqueda",
            "Enriquecimiento",
            "Historial",
            "Grafo",
            "Relaciones",
            "Configuración",
            "Salir",
        ],
        index=0,
    )
    # --- Detección de búsqueda repetida desde historial ---
    if "previous_query" in st.session_state and "previous_type" in st.session_state:
        if st.session_state.previous_type == "dork":
            from ui.modules import dorks_ui
            previous_query = st.session_state.previous_query
            st.session_state.pop("previous_query")
            st.session_state.pop("previous_type")
            dorks_ui.run(st.session_state.username, previous_query=previous_query)
            st.stop()

    st.title(f"🕵️ OSINT Suite - Dashboard")
    st.markdown(f"**Usuario activo:** `{st.session_state.username}`")

    if page == "Inicio":
        st.markdown("### Bienvenido al panel OSINT.")
        st.info("Selecciona un módulo en la barra lateral para comenzar una investigación.")
        logger.debug("Mostrando página de inicio en dashboard.")

    elif page == "Personas":
        from ui.modules import person_ui
        person_ui.run(st.session_state.username)

    elif page == "Dorks":
        from ui.modules import dorks_ui
        dorks_ui.run(st.session_state.username)

    elif page == "Búsqueda":
        from ui.modules import search_ui
        search_ui.run(st.session_state.username)

    elif page == "Enriquecimiento":
        from ui.modules import enrichment_ui
        enrichment_ui.run(st.session_state.username)

    elif page == "Historial":
        from ui.modules import history_ui
        history_ui.run(st.session_state.username)

    elif page == "Grafo":
        from ui.modules import graph_ui
        graph_ui.run(st.session_state.username)

    elif page == "Relaciones":
        from ui.modules import relations_ui
        relations_ui.run(st.session_state.username)

    elif page == "Configuración":
        from ui.modules import settings_ui
        settings_ui.run(st.session_state.username)

    elif page == "Salir":
        st.session_state.logged_in = False
        st.session_state.username = None
        st.switch_page("ui/login.py")
