# core/entities.py
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime


# ==========================================================
# 👤 USUARIO
# ==========================================================
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    preferences: List["UserPreference"] = Relationship(back_populates="user")
    persons: List["Person"] = Relationship(back_populates="owner")


# ==========================================================
# ⚙️ CONFIGURACIONES DE USUARIO
# ==========================================================
class UserPreference(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    key: str
    value: str

    user: Optional[User] = Relationship(back_populates="preferences")


# ==========================================================
# 🧍 PERSONA
# ==========================================================
class Person(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    owner_id: Optional[int] = Field(default=None, foreign_key="user.id")

    emails: List["Email"] = Relationship(back_populates="person")
    profiles: List["Profile"] = Relationship(back_populates="person")
    owner: Optional[User] = Relationship(back_populates="persons")


# ==========================================================
# 📧 EMAILS
# ==========================================================
class Email(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    address: str
    person_id: Optional[int] = Field(default=None, foreign_key="person.id")

    person: Optional[Person] = Relationship(back_populates="emails")


# ==========================================================
# 🌐 PERFILES SOCIALES
# ==========================================================
class Profile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    platform: str
    handle: str
    url: Optional[str] = None
    person_id: Optional[int] = Field(default=None, foreign_key="person.id")

    person: Optional[Person] = Relationship(back_populates="profiles")


# ==========================================================
# 🔗 RELACIONES ENTRE ENTIDADES
# ==========================================================
class Relation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: str
    target_id: str
    relation: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ==========================================================
# 📜 LOG DE BÚSQUEDAS
# ==========================================================
class SearchLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    query: str
    result: str
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    type: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
