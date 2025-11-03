# core/entities.py
"""
Modelos principales de la base de datos OSINT Suite.
Incluye entidades: User, UserSetting, Person, Email, Profile, Relation, SearchLog.
"""

from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship


# ==========================================================
# 👤 USUARIO Y CONFIGURACIÓN
# ==========================================================
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, sa_column_kwargs={"unique": True})
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    settings: List["UserSetting"] = Relationship(back_populates="user")


class UserSetting(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    key: str
    value: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)

    user: Optional[User] = Relationship(back_populates="settings")


# ==========================================================
# 🧍 PERSONAS Y ELEMENTOS RELACIONADOS
# ==========================================================
class Person(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    emails: List["Email"] = Relationship(back_populates="person")
    profiles: List["Profile"] = Relationship(back_populates="person")


class Email(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    address: str = Field(index=True)
    person_id: Optional[int] = Field(foreign_key="person.id")

    person: Optional[Person] = Relationship(back_populates="emails")


class Profile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    platform: str
    handle: str
    url: Optional[str] = None
    person_id: Optional[int] = Field(foreign_key="person.id")

    person: Optional[Person] = Relationship(back_populates="profiles")


# ==========================================================
# 🔗 RELACIONES / GRAFO
# ==========================================================
class Relation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: str
    target_id: str
    relation: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ==========================================================
# 🧠 REGISTRO DE BÚSQUEDAS
# ==========================================================
class SearchLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    query: str
    result: str
    type: str = "osint_search"
    created_at: datetime = Field(default_factory=datetime.utcnow)

# core/entities.py

from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime

class OsintResult(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    person_id: int | None = Field(default=None, foreign_key="person.id")
    query: str
    mode: str
    title: str
    link: str
    snippet: str
    source: str
    date: datetime = Field(default_factory=datetime.utcnow)
