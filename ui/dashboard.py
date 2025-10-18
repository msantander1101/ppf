import streamlit as st
from core.database import get_session
from core.entities import Person
from core.database import SearchLog
from sqlmodel import select
from utils.logger import logger

# Importamos los módulos UI disponibles
from ui.modules import person_ui, history_ui, settings_ui, graph_ui

def main():
    """
    Panel principal de OSINT Suite.
    Gestiona la navegación entre módulos y muestra métricas globales.
    """

    st.set_page_config(page_title="OSINT Suite Dashboard", page_icon="🕵️‍♂️", layout="wide")
    st.sidebar.title("📂 OSINT Suite")

    # Menú lateral de navegación
    menu = st.sidebar.radio(
        "Navegación",
        ["Inicio", "Personas", "Historial", "Grafo", "Configuración"]
    )

    username = st.session_state.get("username", "Invitado")

    if menu == "Inicio":
        st.title("🕵️‍♂️ OSINT Suite — Panel Principal")
        st.markdown(f"👋 Bienvenido, **{username}**.")
        st.info("Selecciona un módulo en el menú lateral para comenzar tu investigación OSINT.")

        try:
            from sqlalchemy import func
            with get_session() as session:
                total_personas = session.exec(select(func.count()).select_from(Person)).one()
                total_logs = session.exec(select(func.count()).select_from(SearchLog)).one()

            col1, col2 = st.columns(2)
            col1.metric("👤 Personas registradas", total_personas)
            col2.metric("🔍 Búsquedas ejecutadas", total_logs)

            # Mostrar últimos logs de actividad
            st.markdown("### 🕓 Actividad reciente")
            with get_session() as session:
                logs = session.exec(
                    select(SearchLog).order_by(SearchLog.created_at.desc()).limit(5)
                ).all()

                if not logs:
                    st.info("No hay actividad reciente registrada.")
                else:
                    for log in logs:
                        st.markdown(
                            f"- **{log.query}**  \n"
                            f"🧩 Tipo: `{log.type}`  \n"
                            f"🕒 {log.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
                        )
        except Exception as e:
            st.error(f"Error cargando métricas: {e}")
            logger.exception("Error en dashboard metrics")

    elif menu == "Personas":
        person_ui.run(username)

    elif menu == "Historial":
        history_ui.run(username)

    elif menu == "Grafo":
        graph_ui.run(username)

    elif menu == "Configuración":
        settings_ui.run(username)

    else:
        st.warning("Selecciona una opción válida en el menú lateral.")


if __name__ == "__main__":
    main()
