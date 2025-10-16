from typing import Literal, TypedDict

EntityType = Literal["user", "email", "social", "domain", "leak", "custom"]

class Entity(TypedDict):
    id: str
    label: str
    type: EntityType
