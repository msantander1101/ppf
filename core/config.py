import os
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken
from core.database import get_session, UserSetting, User
from utils.logger import logger

FERNET_KEY = os.environ.get("APP_ENCRYPTION_KEY")

if not FERNET_KEY:
    logger.warning("APP_ENCRYPTION_KEY no configurada. Los valores se almacenarán en claro (no recomendado).")

def _get_fernet() -> Optional[Fernet]:
    if not FERNET_KEY:
        return None
    try:
        return Fernet(FERNET_KEY.encode())
    except Exception as e:
        logger.exception(f"Clave Fernet inválida: {e}")
        return None

def store_user_setting(username: str, key: str, value: str) -> bool:
    try:
        with get_session() as session:
            user = session.query(User).filter(User.username == username).first()
            if not user:
                logger.error(f"store_user_setting: usuario {username} no encontrado")
                return False

            f = _get_fernet()
            if f:
                encrypted = f.encrypt(value.encode()).decode()
            else:
                logger.warning("APP_ENCRYPTION_KEY no configurada: almacenando en claro")
                encrypted = value

            existing = session.query(UserSetting).filter(
                UserSetting.user_id == user.id, UserSetting.key == key
            ).first()
            if existing:
                existing.value_encrypted = encrypted
            else:
                s = UserSetting(user_id=user.id, key=key, value_encrypted=encrypted)
                session.add(s)
            session.commit()
            logger.info(f"Setting '{key}' guardado para usuario {username}")
            return True
    except Exception as e:
        logger.exception(f"Error en store_user_setting: {e}")
        return False

def get_user_setting(username: str, key: str) -> Optional[str]:
    try:
        with get_session() as session:
            user = session.query(User).filter(User.username == username).first()
            if not user:
                return None
            existing = session.query(UserSetting).filter(
                UserSetting.user_id == user.id, UserSetting.key == key
            ).first()
            if not existing:
                return None
            f = _get_fernet()
            if f:
                try:
                    return f.decrypt(existing.value_encrypted.encode()).decode()
                except InvalidToken:
                    logger.exception("La APP_ENCRYPTION_KEY es inválida. No puedo descifrar settings.")
                    return None
            else:
                return existing.value_encrypted
    except Exception as e:
        logger.exception(f"Error en get_user_setting: {e}")
        return None

def delete_user_setting(username: str, key: str) -> bool:
    try:
        with get_session() as session:
            user = session.query(User).filter(User.username == username).first()
            if not user:
                return False
            existing = session.query(UserSetting).filter(
                UserSetting.user_id == user.id, UserSetting.key == key
            ).first()
            if existing:
                session.delete(existing)
                session.commit()
                logger.info(f"Setting '{key}' eliminado para usuario {username}")
            return True
    except Exception as e:
        logger.exception(f"Error en delete_user_setting: {e}")
        return False
