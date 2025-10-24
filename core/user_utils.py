from sqlmodel import select
from core.database import get_session
from core.entities import User
from utils.logger import logger

def get_user_id(username: str) -> int | None:
    """Obtiene el ID de usuario activo por nombre."""
    try:
        with get_session() as session:
            user = session.exec(select(User).where(User.username == username)).first()
            if user:
                return user.id
            else:
                logger.warning(f"No se encontró ID para usuario '{username}'.")
                return None
    except Exception as e:
        logger.exception(f"Error obteniendo ID de usuario '{username}': {e}")
        return None
