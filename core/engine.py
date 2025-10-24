# core/database.py
from sqlmodel import SQLModel, create_engine, Session
from utils.logger import logger
import os

# ==========================
# 🔹 Configuración general
# ==========================
DB_PATH = os.path.join("data", "osint_suite.db")
os.makedirs("data", exist_ok=True)
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False)


# ==========================
# 🔹 Inicialización de la base de datos
# ==========================
def init_db():
    """
    Inicializa la base de datos y crea todas las tablas si no existen.
    """
    try:
        from core.entities import User, Person, Email, Profile, SearchLog, Relation

        logger.info("Inicializando base de datos...")
        SQLModel.metadata.create_all(engine)
        logger.info("Base de datos inicializada correctamente.")
    except Exception as e:
        logger.error(f"Error inicializando la base de datos: {e}", exc_info=True)


# ==========================
# 🔹 Sesiones
# ==========================
def get_session():
    """
    Crea un contexto de sesión con la base de datos.
    """
    with Session(engine) as session:
        yield session


# ==========================
# 🔹 Sesión directa (uso interno opcional)
# ==========================
def session_scope():
    """
    Proporciona una sesión reutilizable para operaciones directas.
    """
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
