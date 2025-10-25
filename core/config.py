# core/config.py
"""
Gestión de configuración general y ajustes de usuario.
Incluye cifrado AES-256 para claves y variables sensibles.
"""

import os
from sqlmodel import select
from core.database import get_session
from core.entities import User
from utils.logger import logger
from utils.crypto import encrypt_value, decrypt_value

# ==========================================================
# 🔹 VARIABLES GLOBALES DE CONFIGURACIÓN
# ==========================================================
APP_ENCRYPTION_KEY = os.getenv("APP_ENCRYPTION_KEY", None)
DB_PATH = os.getenv("DB_PATH", "data/osint_suite.db")

# ==========================================================
# 🧩 FUNCIONES DE AJUSTES DE USUARIO
# ==========================================================
def get_user_setting(username: str, key: str) -> str:
    """Recupera un valor de configuración del usuario (descifrado)."""
    from core.entities import UserSetting

    with get_session() as session:
        user = session.exec(select(User).where(User.username == username)).first()
        if not user:
            logger.warning(f"[config] Usuario {username} no encontrado.")
            return None

        pref = session.exec(
            select(UserSetting).where(
                UserSetting.user_id == user.id, UserSetting.key == key
            )
        ).first()
        return decrypt_value(pref.value) if pref else None


def set_user_setting(username: str, key: str, value: str):
    """Guarda o actualiza un valor cifrado en la configuración del usuario."""
    from core.entities import UserSetting

    with get_session() as session:
        user = session.exec(select(User).where(User.username == username)).first()
        if not user:
            logger.warning(f"[config] Usuario {username} no encontrado.")
            return

        pref = session.exec(
            select(UserSetting).where(
                UserSetting.user_id == user.id, UserSetting.key == key
            )
        ).first()

        encrypted_value = encrypt_value(value)

        if pref:
            pref.value = encrypted_value
        else:
            pref = UserSetting(user_id=user.id, key=key, value=encrypted_value)
            session.add(pref)

        session.commit()
        logger.info(f"[config] Guardado setting {key} para usuario {username}.")


def delete_user_setting(username: str, key: str):
    """Elimina una clave o ajuste específico del usuario."""
    from core.entities import UserSetting

    with get_session() as session:
        user = session.exec(select(User).where(User.username == username)).first()
        if not user:
            return

        pref = session.exec(
            select(UserSetting).where(
                UserSetting.user_id == user.id, UserSetting.key == key
            )
        ).first()
        if pref:
            session.delete(pref)
            session.commit()
            logger.info(f"[config] Eliminado setting {key} de usuario {username}.")
