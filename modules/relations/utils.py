from core.database import get_session
from core.entities import Relation, User
from utils.logger import logger


def add_relation(username: str, source_id: str, target_id: str, relation_type: str):
    """Agrega una relación en la base de datos de manera segura."""
    try:
        with get_session() as session:
            user = session.query(User).filter(User.username == username).first()
            if not user:
                logger.warning(f"No se encontró el usuario '{username}' para agregar relación.")
                return False

            rel = Relation(
                source_id=source_id,
                target_id=target_id,
                relation=relation_type,
                user_id=user.id
            )
            session.add(rel)
            session.commit()
            logger.debug(f"Relación añadida automáticamente: {source_id} -> {target_id} ({relation_type})")
            return True
    except Exception as e:
        logger.exception(f"Error al agregar relación automática: {e}")
        return False
