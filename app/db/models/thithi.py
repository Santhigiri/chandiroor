from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.db.models.paksha import Paksha
    from app.db.models.panchangam import Panchangam
    from app.db.models.thithi_transition import ThithiTransition


class Thithi(SQLModel, table=True):
    """One of the 30 lunar days (15 per paksha)."""

    __tablename__ = "thithi" # pyright: ignore[reportAssignmentType]

    id:        int = Field(primary_key=True)        # 1–30
    name:      str = Field(unique=True)             # Python enum member name e.g. 'PRATHAMA_SHUKLA'
    paksha_id: int = Field(foreign_key="paksha.id")
    day:       int                                  # day within paksha (1–15)
    ml:        str
    en:        str

    paksha:      Optional["Paksha"]        = Relationship(back_populates="thithis")
    panchangams: List["Panchangam"]        = Relationship(back_populates="thithi")
    transitions: List["ThithiTransition"]  = Relationship(back_populates="thithi")
