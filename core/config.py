# core/config.py
import logging
from typing import Optional

from core.database import get_session
from core.entities import UserSetting, User
from typing import Union

logger = logging.getLogger("osint_suite")


# =========================================
# Obtener la configuración de un usuario
# =========================================
def get_user_setting(user: Union[int, str], key: str) -> Optional[str]:
    """
    Devuelve el valor de una configuración concreta para un usuario.

    Este helper acepta tanto un identificador numérico (`user_id`) como un
    nombre de usuario (`username`). Si se pasa un `username`, se realizará
    una búsqueda en la base de datos para obtener su `id`. Si el usuario no
    existe o la configuración no está almacenada, se devuelve `None`.
    """
    try:
        with get_session() as session:
            # Determinar el user_id a partir del parámetro
            if isinstance(user, int):
                user_id = user
            else:
                # Buscar por nombre de usuario
                u = session.query(User).filter_by(username=user).first()
                if not u:
                    logger.debug(f"Usuario no encontrado: {user}")
                    return None
                user_id = u.id

            setting = session.query(UserSetting).filter_by(user_id=user_id, key=key).first()
            if setting:
                logger.debug(f"Configuración encontrada [{key}] = {setting.value}")
                return setting.value
            else:
                logger.debug(f"Configuración [{key}] no encontrada para usuario {user_id}")
                return None
    except Exception as e:
        logger.error(f"Error obteniendo configuración '{key}' para usuario {user}: {e}")
        return None


# =========================================
# Guardar o actualizar una configuración
# =========================================
def set_user_setting(user: Union[int, str], key: str, value: str) -> None:
    """
    Crea o actualiza un valor de configuración para un usuario.

    Se acepta como primer parámetro tanto el `user_id` (int) como el
    `username` (str). Si el usuario no existe en la base de datos, no se
    realizará ninguna operación.
    """
    try:
        with get_session() as session:
            # Determinar el user_id
            if isinstance(user, int):
                user_id = user
            else:
                u = session.query(User).filter_by(username=user).first()
                if not u:
                    logger.debug(f"No existe el usuario '{user}' para guardar configuración.")
                    return
                user_id = u.id

            setting = session.query(UserSetting).filter_by(user_id=user_id, key=key).first()
            if setting:
                setting.value = value
                logger.debug(f"Configuración actualizada [{key}] = {value}")
            else:
                setting = UserSetting(user_id=user_id, key=key, value=value)
                session.add(setting)
                logger.debug(f"Nueva configuración creada [{key}] = {value}")

            session.commit()
    except Exception as e:
        logger.error(f"Error guardando configuración '{key}' para usuario {user}: {e}")


# =========================================
# Cargar todas las configuraciones de un usuario
# =========================================
def get_all_user_settings(user: Union[int, str]) -> dict:
    """
    Devuelve todas las configuraciones del usuario en forma de diccionario.

    Acepta tanto `user_id` como `username`. Si el usuario no existe o no tiene
    configuraciones, se devuelve un diccionario vacío.
    """
    try:
        with get_session() as session:
            # Determinar el user_id
            if isinstance(user, int):
                user_id = user
            else:
                u = session.query(User).filter_by(username=user).first()
                if not u:
                    logger.debug(f"Usuario no encontrado: {user}")
                    return {}
                user_id = u.id

            settings = session.query(UserSetting).filter_by(user_id=user_id).all()
            config_dict = {s.key: s.value for s in settings}
            logger.debug(f"Configuraciones cargadas para usuario {user_id}: {config_dict}")
            return config_dict
    except Exception as e:
        logger.error(f"Error obteniendo todas las configuraciones para usuario {user}: {e}")
        return {}
