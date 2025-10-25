# core/database.py
"""
Gestión central de la base de datos para OSINT Suite.
Incluye inicialización, contexto de sesión y soporte SQLite / PostgreSQL.
"""

import os
from sqlmodel import SQLModel, create_engine, Session
from contextlib import contextmanager
from utils.logger import logger

# ==========================================================
# 🔹 CONFIGURACIÓN DEL MOTOR
# ==========================================================
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///data/osint.db")

# Si usas SQLite local, activa check_same_thread=False
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)


# ==========================================================
# 🧱 INICIALIZACIÓN
# ==========================================================
def init_db():
    """Crea las tablas definidas si no existen."""
    try:
        from core import entities  # aseguramos que los modelos estén importados
        SQLModel.metadata.create_all(engine)
        logger.info("Base de datos inicializada correctamente.")
    except Exception as e:
        logger.exception(f"[init_db] Error al inicializar la base de datos: {e}")


# ==========================================================
# 💾 SESIÓN DE BASE DE DATOS (CONTEXT MANAGER)
# ==========================================================
@contextmanager
def get_session():
    """Crea y gestiona una sesión SQLModel segura."""
    session = Session(engine)
    try:
        yield session
    except Exception as e:
        session.rollback()
        logger.exception(f"[get_session] Error en sesión: {e}")
        raise
    finally:
        session.close()
