# core/config.py
"""
Gestión centralizada de configuración y ajustes de usuario (API keys, preferencias, etc.)
Compatible con settings_ui y el resto de módulos.
"""

from sqlmodel import select
from core.database import get_session
from core.entities import User, UserSetting
from utils.logger import logger


# ==========================================================
# 🔹 Obtener ajustes
# ==========================================================
def get_user_setting(username: str, key: str) -> str | None:
    """
    Obtiene un ajuste (API key, preferencia, etc.) para un usuario concreto.
    Devuelve None si el usuario o la clave no existen.
    """
    try:
        with get_session() as session:
            user = session.exec(select(User).where(User.username == username)).first()
            if not user:
                logger.warning(f"[config] Usuario no encontrado: {username}")
                return None

            setting = session.exec(
                select(UserSetting).where(
                    UserSetting.user_id == user.id,
                    UserSetting.key == key
                )
            ).first()
            return setting.value if setting else None
    except Exception as e:
        logger.error(f"[config] Error obteniendo setting '{key}' para {username}: {e}")
        return None


# ==========================================================
# 🔹 Guardar o actualizar ajustes
# ==========================================================
def set_user_setting(username: str, key: str, value: str):
    """
    Crea o actualiza un ajuste para un usuario.
    Si la clave ya existe, la sobrescribe.
    """
    try:
        with get_session() as session:
            user = session.exec(select(User).where(User.username == username)).first()
            if not user:
                logger.error(f"[config] Usuario {username} no encontrado al guardar setting {key}")
                return

            setting = session.exec(
                select(UserSetting).where(
                    UserSetting.user_id == user.id,
                    UserSetting.key == key
                )
            ).first()

            if setting:
                setting.value = value
            else:
                setting = UserSetting(user_id=user.id, key=key, value=value)
                session.add(setting)

            session.commit()
            logger.info(f"[config] Configuración '{key}' actualizada para usuario {username}")
    except Exception as e:
        logger.error(f"[config] Error guardando setting '{key}' para {username}: {e}")


# ==========================================================
# 🔹 Eliminar ajustes
# ==========================================================
def delete_user_setting(username: str, key: str):
    """
    Elimina un ajuste (API key, preferencia, etc.) de un usuario concreto.
    """
    try:
        with get_session() as session:
            user = session.exec(select(User).where(User.username == username)).first()
            if not user:
                logger.warning(f"[config] Usuario {username} no encontrado al eliminar setting {key}")
                return

            setting = session.exec(
                select(UserSetting).where(
                    UserSetting.user_id == user.id,
                    UserSetting.key == key
                )
            ).first()

            if setting:
                session.delete(setting)
                session.commit()
                logger.info(f"[config] Setting '{key}' eliminado para usuario {username}")
            else:
                logger.warning(f"[config] No se encontró el setting '{key}' para eliminarlo")
    except Exception as e:
        logger.error(f"[config] Error eliminando setting '{key}' para {username}: {e}")


# ==========================================================
# 🔹 Utilidad extra (listar todas las claves de un usuario)
# ==========================================================
def list_user_settings(username: str) -> dict:
    """
    Devuelve todas las configuraciones registradas para un usuario.
    Útil para depuración o exportación de settings.
    """
    try:
        with get_session() as session:
            user = session.exec(select(User).where(User.username == username)).first()
            if not user:
                logger.warning(f"[config] Usuario {username} no encontrado al listar settings")
                return {}

            settings = session.exec(select(UserSetting).where(UserSetting.user_id == user.id)).all()
            return {s.key: s.value for s in settings}
    except Exception as e:
        logger.error(f"[config] Error listando settings para {username}: {e}")
        return {}
