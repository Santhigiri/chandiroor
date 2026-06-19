from __future__ import annotations

from typing import TYPE_CHECKING, List

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from db.models.nakshatra_transition import NakshatraTransition


class Nakshatra(SQLModel, table=True):
    """One of the 27 lunar mansions."""

    __tablename__ = "nakshatra"

    id:   int = Field(primary_key=True)  # 1–27
    name: str = Field(unique=True)       # Python enum member name e.g. 'ASWATHI'
    ml:   str
    en:   str

    transitions: List[NakshatraTransition] = Relationship(back_populates="nakshatra")
