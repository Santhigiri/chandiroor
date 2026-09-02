from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.db.models.nakshatra_transition import NakshatraTransition
    from app.db.models.panchangam import Panchangam


class Nakshatra(SQLModel, table=True):
    """One of the 27 lunar mansions."""

    __tablename__ = "nakshatra" # pyright: ignore[reportAssignmentType]


    id:   int = Field(primary_key=True)  # 1–27
    name: str = Field(unique=True)       # Python enum member name e.g. 'ASWATHI'
    # Localized display text — see the note on Thithi.ml/en. Not seeded from the
    # enum; filled by db/sql/02_seed.sql on real DBs, NULL in db/seed.py DBs.
    ml:   Optional[str] = None
    en:   Optional[str] = None

    panchangams: List["Panchangam"]           = Relationship(back_populates="nakshatra")
    transitions: List["NakshatraTransition"]  = Relationship(back_populates="nakshatra")
