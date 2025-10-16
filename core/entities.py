from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime


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
    validated: bool = Field(default=False)
    leaks_summary: Optional[str] = None
    person_id: Optional[int] = Field(default=None, foreign_key="person.id")

    person: Optional[Person] = Relationship(back_populates="emails")


class Profile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    platform: str  # 'twitter','instagram','linkedin'
    handle: str
    url: str
    info_json: Optional[str] = None  # 🔁 antes era `metadata`
    person_id: Optional[int] = Field(default=None, foreign_key="person.id")

    person: Optional[Person] = Relationship(back_populates="profiles")
