import streamlit as st
from sqlmodel import select
from core.database import get_session, SearchLog, User
from utils.logger import logger


def run(username: str):
    """
    Muestra el historial de búsquedas del usuario activo
    y permite re-ejecutar búsquedas anteriores.
    """
    st.header("📜 Historial de Búsquedas")

    if not username:
        st.warning("⚠️ No se ha detectado un usuario activo.")
        return

    try:
        with get_session() as session:
            user = session.exec(select(User).where(User.username == username)).first()
            if not user:
                st.error("Usuario no encontrado en la base de datos.")
                logger.warning(f"Intento de acceso a historial sin usuario válido ({username})")
                return

            logs = session.exec(
                select(SearchLog)
                .where(SearchLog.user_id == user.id)
                .order_by(SearchLog.created_at.desc())
            ).all()

            if not logs:
                st.info("🕳️ Aún no hay búsquedas registradas para este usuario.")
                return

            st.success(f"Mostrando {len(logs)} registros para **{username}**")

            for log in logs:
                with st.expander(f"🕓 {log.created_at.strftime('%Y-%m-%d %H:%M:%S')} — {log.type.upper()}"):
                    st.write(f"**Consulta:** `{log.query}`")

                    # Mostrar resultado de texto o JSON
                    if log.result:
                        with st.expander("🧩 Resultado almacenado"):
                            st.text_area("Resultado", log.result, height=150)

                    # Botón para repetir búsqueda (solo en tipo dork por ahora)
                    if log.type == "dork":
                        if st.button(f"🔁 Repetir búsqueda: {log.query}", key=f"repeat_{log.id}"):
                            st.session_state["previous_query"] = log.query
                            st.session_state["previous_type"] = log.type
                            st.switch_page("pages/1_Dashboard.py")  # volver al dashboard

    except Exception as e:
        st.error("Error al cargar el historial.")
        logger.exception(f"Error al cargar historial de {username}: {e}")
