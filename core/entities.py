from sqlalchemy import Index, Column, String
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

# ==========================
# Entidad principal: Usuario
# ==========================
class User(SQLModel, table=True):
    # Índice único estable para username (evita 'ix_user_username')
    __table_args__ = (
        Index("ux_user_username", "username", unique=True),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    # NOTA: no usamos index=True aquí para evitar otro índice; el único será ux_user_username
    username: str = Field(sa_column=Column("username", String, nullable=False))
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    persons: List["Person"] = Relationship(back_populates="user")
    logs: List["SearchLog"] = Relationship(back_populates="user")

    # Configuraciones de usuario (API keys, preferencias, etc.)
    settings: List["UserSetting"] = Relationship(back_populates="user")


# ==========================
# Entidad: Persona (ampliada)
# ==========================
class Person(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    alias: Optional[str] = Field(default=None, index=True)
    dni: Optional[str] = Field(default=None, index=True)
    phone: Optional[str] = Field(default=None, index=True)
    address: Optional[str] = Field(default=None)
    company: Optional[str] = Field(default=None, index=True)
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    user: Optional[User] = Relationship(back_populates="persons")

    emails: List["Email"] = Relationship(back_populates="person")
    profiles: List["Profile"] = Relationship(back_populates="person")

    # Dominios asociados a la persona (opcional)
    domains: List["Domain"] = Relationship(back_populates="person")


# ==========================
# Entidad: Dominio
# ==========================
class Domain(SQLModel, table=True):
    """
    Representa un dominio de Internet vinculado opcionalmente a una persona.

    Permite almacenar dominios investigados junto con notas y la fecha de
    creación. Un dominio puede pertenecer a una persona (mediante `person_id`)
    para indicar asociación en el contexto de una investigación OSINT.
    """
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relación con persona propietaria (opcional)
    person_id: Optional[int] = Field(default=None, foreign_key="person.id")
    person: Optional[Person] = Relationship(back_populates="domains")


# ==========================
# Email asociado a persona
# ==========================
class Email(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    address: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Resumen de filtraciones para este correo (por ejemplo, reporte de HIBP)
    leaks_summary: Optional[str] = None

    person_id: Optional[int] = Field(default=None, foreign_key="person.id")
    person: Optional[Person] = Relationship(back_populates="emails")


# ==========================
# Perfil social / técnico
# ==========================
class Profile(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    platform: str = Field(index=True)
    handle: str = Field(index=True)
    url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    person_id: Optional[int] = Field(default=None, foreign_key="person.id")
    person: Optional[Person] = Relationship(back_populates="profiles")


# ==========================
# Registro de búsquedas / resultados
# ==========================
class SearchLog(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    query: str
    result: Optional[str] = None  # JSON string
    type: str = Field(default="dork")  # dork / enrich / paste / social
    created_at: datetime = Field(default_factory=datetime.utcnow)

    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    user: Optional[User] = Relationship(back_populates="logs")


# ==========================
# Relaciones (para grafo)
# ==========================
class Relation(SQLModel, table=True):
    """
    Representa una relación entre dos entidades genéricas dentro del grafo OSINT.

    Cada relación está asociada a un usuario a través de `user_id` de modo que
    diferentes usuarios puedan almacenar sus propios grafos sin interferencia.

    - `source_id` y `target_id` utilizan un esquema de prefijos para referenciar
      entidades heterogéneas (por ejemplo, "person:1" o "email:3").
    - `relation` es una descripción opcional del tipo de vínculo.
    - `created_at` almacena la fecha y hora de creación de la relación.
    """
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    source_id: str = Field(index=True)
    target_id: str = Field(index=True)
    relation: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserSetting(SQLModel, table=True):
    """
    Almacena pares clave/valor de configuración específicos de cada usuario.

    Las claves permiten registrar API keys u otras preferencias del usuario. El
    modelo está vinculado a `User` a través de `user_id` y dispone de un
    `created_at` para trazar cuándo se creó la configuración. No se almacenan
    datos de grafo aquí; los campos `source_id`/`target_id` y `relation` que
    aparecían anteriormente se movieron a la entidad `Relation`.
    """
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    key: str = Field(index=True)
    value: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # back-reference to User
    user: Optional[User] = Relationship(back_populates="settings")