from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.db.models.kollavarsham_date import KollavarshamDate


class MalayalamMasa(SQLModel, table=True):
    """One of the 12 Malayalam solar months (masa)."""

    __tablename__ = "malayalam_masa" # pyright: ignore[reportAssignmentType]

    id:   int = Field(primary_key=True)  # 1–12
    name: str = Field(unique=True)       # Python enum member name e.g. 'MEDAM'
    # Localized display text — see the note on Thithi.ml/en. Not seeded from the
    # enum; filled by db/sql/02_seed.sql on real DBs, NULL in db/seed.py DBs.
    ml:   Optional[str] = None
    en:   Optional[str] = None

    kollavarsham_dates: List["KollavarshamDate"] = Relationship(back_populates="masa")
