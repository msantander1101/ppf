# core/database.py
import logging
from sqlmodel import SQLModel, create_engine, Session
from contextlib import contextmanager
from pathlib import Path

# Importa todos los modelos (import tardío para evitar ciclos)
from core.entities import (
    User,
    UserSetting,
    Person,
    Email,
    Profile,
    SearchLog,
    Relation,
)

logger = logging.getLogger("osint_suite")

# ======================================================
# CONFIGURACIÓN DE LA BASE DE DATOS
# ======================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "osint_suite.db"
DB_PATH.parent.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(DATABASE_URL, echo=False)


# ======================================================
# FUNCIÓN: Inicializar Base de Datos
# ======================================================
def init_db() -> None:
    """
    Inicializa las tablas de la base de datos si no existen.
    """
    try:
        logger.info("Inicializando base de datos...")
        SQLModel.metadata.create_all(engine)
        logger.info("Base de datos inicializada correctamente.")
    except Exception as e:
        logger.error(f"Error inicializando la base de datos: {e}", exc_info=True)


# ======================================================
# CONTEXT MANAGER para obtener sesiones limpias
# ======================================================
@contextmanager
def get_session():
    """
    Devuelve una sesión de base de datos usando context manager.

    Ejemplo:
        with get_session() as session:
            session.add(obj)
            session.commit()
    """
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Error en sesión de base de datos: {e}", exc_info=True)
        raise
    finally:
        session.close()
