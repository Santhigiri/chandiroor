from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.db.models.chandra_masa_date import ChandraMasaDate


class ChandraMasa(SQLModel, table=True):
    """One of the 12 lunar (Amanta) months (masa)."""

    __tablename__ = "chandra_masa" # pyright: ignore[reportAssignmentType]

    id:   int = Field(primary_key=True)  # 1–12
    name: str = Field(unique=True)       # Python enum member name e.g. 'CHAITRA'
    # Localized display text — see the note on Thithi.ml/en. Not seeded from the
    # enum; filled by db/sql/02_seed.sql on real DBs, NULL in db/seed.py DBs.
    ml:   Optional[str] = None
    en:   Optional[str] = None

    chandra_masa_dates: List["ChandraMasaDate"] = Relationship(back_populates="masa")
