from dataclasses import dataclass
from typing import Optional


@dataclass
class Persona:
    id: Optional[str]
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    occupation: Optional[str] = None
    bio: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Job:
    id: Optional[str]
    status: str = "pending"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

