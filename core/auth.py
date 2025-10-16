import bcrypt
from sqlmodel import select
from core.database import User, get_session
from utils.logger import logger

def register_user(username: str, password: str) -> bool:
    logger.debug(f"Intentando registrar usuario: {username}")
    try:
        with get_session() as session:
            existing = session.exec(select(User).where(User.username == username)).first()
            if existing:
                logger.warning(f"Intento de registro duplicado para usuario '{username}'")
                return False
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            user = User(username=username, password_hash=hashed)
            session.add(user)
            session.commit()
            logger.info(f"Usuario registrado correctamente: {username}")
            return True
    except Exception as e:
        logger.exception(f"Error registrando usuario '{username}': {e}")
        return False

def login_user(username: str, password: str) -> bool:
    logger.debug(f"Intentando login para usuario: {username}")
    try:
        with get_session() as session:
            user = session.exec(select(User).where(User.username == username)).first()
            if not user:
                logger.warning(f"Usuario '{username}' no encontrado.")
                return False
            if bcrypt.checkpw(password.encode(), user.password_hash.encode()):
                logger.info(f"Login exitoso: {username}")
                return True
            else:
                logger.warning(f"Contraseña incorrecta para usuario '{username}'")
                return False
    except Exception as e:
        logger.exception(f"Error en login para usuario '{username}': {e}")
        return False
