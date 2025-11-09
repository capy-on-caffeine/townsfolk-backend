
# schema.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
from datetime import datetime


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


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

    @staticmethod
    def from_mongo(doc: Dict[str, Any]) -> "Persona":
        return Persona(
            id=str(doc.get("_id") or doc.get("id") or ""),
            name=doc.get("name", ""),
            age=doc.get("age"),
            gender=doc.get("gender"),
            occupation=doc.get("occupation"),
            bio=doc.get("bio"),
            created_at=doc.get("created_at"),
            updated_at=doc.get("updated_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Feedback:
    id: Optional[str]
    job: str
    persona: str
    feedback: str
    rating: Optional[float] = None
    rubric_breakdown: Optional[Dict[str, Any]] = None
    raw_actions: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @staticmethod
    def new(job: str, persona: str, feedback: str, rating: Optional[float] = None,
            rubric_breakdown: Optional[Dict[str, Any]] = None,
            raw_actions: Optional[Dict[str, Any]] = None) -> "Feedback":
        now = now_iso()
        return Feedback(
            id=None,
            job=job,
            persona=persona,
            feedback=feedback,
            rating=rating,
            rubric_breakdown=rubric_breakdown,
            raw_actions=raw_actions,
            created_at=now,
            updated_at=now,
        )

    def to_mongo(self) -> Dict[str, Any]:
        # Do not include None fields for cleanliness
        data = {k: v for k, v in self.__dict__.items() if v is not None}
        return data
