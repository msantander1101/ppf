"""
Interfaz para consultas de fuga de datos en HaveIBeenPwned (HIBP).

Este módulo permite al usuario introducir un correo electrónico y consultar
si ha sido comprometido mediante la API de HIBP. Registra las búsquedas en el
historial del usuario para su posterior consulta.
"""

from typing import Optional
import streamlit as st

from core.user_utils import get_user_id
from core.database import get_session
from core.entities import SearchLog
from utils.logger import logger
from utils import config
from core.config import get_user_setting
from modules.search import hibp


def run(username: Optional[str] = None):
    """
    Ejecuta el módulo de búsqueda HIBP para un correo electrónico.

    :param username: Nombre de usuario activo. Si se proporciona, se usará para
                     registrar la búsqueda en el historial.
    """
    st.header("📬 Análisis de Emails (HaveIBeenPwned)")

    # Campo de entrada para el correo
    email = st.text_input("Introduce un correo electrónico")

    if st.button("Consultar"):
        if not email or not email.strip():
            st.warning("Introduce un email válido.")
            return

        try:
            # Ejecutar consulta HIBP con la API key del usuario (o la global de configuración)
            api_key = None
            if username:
                api_key = get_user_setting(username, "hibp")
            if not api_key:
                api_key = config.HIBP_KEY
            result = hibp.run(email, api_key=api_key)
            if result.get("error"):
                st.error(result["error"])
                return

            # Mostrar resultado al usuario
            st.success("Consulta realizada.")
            st.json(result)

            # Registrar búsqueda en historial si hay usuario activo
            if username:
                user_id = get_user_id(username)
                if user_id:
                    try:
                        with get_session() as session:
                            log_entry = SearchLog(
                                user_id=user_id,
                                query=email,
                                type="hibp",
                                result=str(result),
                            )
                            session.add(log_entry)
                            session.commit()
                        logger.info(f"[{username}] Consulta HIBP registrada en historial.")
                    except Exception as db_err:
                        logger.exception(f"Error guardando log HIBP para {username}: {db_err}")
                else:
                    logger.warning("No se pudo registrar búsqueda: usuario no encontrado.")

        except Exception as e:
            st.error("Error durante la consulta HIBP.")
            logger.exception(f"Error en search_ui con email '{email}': {e}")
