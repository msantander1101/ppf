from sqlmodel import SQLModel, Field, create_engine, Session, select, Relationship
from sqlalchemy import inspect, text
from datetime import datetime
from typing import Optional, List
import os
from utils.logger import logger


DB_URL = "sqlite:///data/osint_suite.db"
engine = create_engine(DB_URL, echo=False)


# =========================
#  Modelo User
# =========================
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    __table_args__ = {"extend_existing": True}

    # Relaciones
    logs: List["SearchLog"] = Relationship(back_populates="user")
    relations: List["Relation"] = Relationship(back_populates="user")
    settings: List["UserSetting"] = Relationship(back_populates="user")


# =========================
#  Modelo SearchLog
# =========================
class SearchLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    query: str
    result: str
    # Tipo de búsqueda o módulo que genera el log (ej. 'dork', 'hibp', etc.).
    # Se añade este campo para permitir filtrar el historial por origen.
    type: str = Field(default="dork")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user_id: int = Field(foreign_key="user.id")

    # 🔧 Relación inversa explícita
    user: Optional["User"] = Relationship(back_populates="logs")


# =========================
#  Modelo Relation
# =========================
class Relation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: str
    target_id: str
    relation: str
    user_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # 🔧 Relación inversa explícita
    user: Optional["User"] = Relationship(back_populates="relations")


# =========================
#  Modelo UserSetting (API keys por usuario, valor cifrado)
# =========================
class UserSetting(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    key: str  # ej. "serpapi", "shodan", "hibp", "whoisxmlapi"
    value_encrypted: str  # valor cifrado (Fernet) o en claro si no hay clave
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relación inversa
    user: Optional["User"] = Relationship(back_populates="settings")

# =========================
#  Inicialización
# =========================
from core.entities import Person, Email, Profile
def init_db():
    os.makedirs("data", exist_ok=True)
    try:
        SQLModel.metadata.create_all(engine)
        # Después de crear las tablas, comprobamos si falta alguna columna
        # para mantener la compatibilidad con versiones anteriores.
        try:
            with engine.connect() as conn:
                inspector = inspect(engine)
                # Añadimos la columna 'type' a SearchLog si no existe
                if "searchlog" in inspector.get_table_names():
                    columns = [c["name"] for c in inspector.get_columns("searchlog")]
                    if "type" not in columns:
                        conn.execute(text("ALTER TABLE searchlog ADD COLUMN type TEXT DEFAULT 'dork'"))
                        conn.commit()
                        logger.info("Se añadió la columna 'type' a la tabla searchlog para compatibilidad.")
        except Exception as migration_err:
            logger.exception(f"Error al migrar la base de datos: {migration_err}")

        logger.info("Base de datos inicializada correctamente.")
    except Exception as e:
        logger.exception(f"Error inicializando la base de datos: {e}")


def get_session():
    return Session(engine)
