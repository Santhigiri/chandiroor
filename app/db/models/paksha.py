from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.db.models.thithi import Thithi


class Paksha(SQLModel, table=True):
    """Moon phase grouping — Shukla (waxing) or Krishna (waning)."""

    __tablename__ = "paksha" # pyright: ignore[reportAssignmentType]

    id:   int = Field(primary_key=True)  # 1=SHUKLA, 2=KRISHNA
    name: str = Field(unique=True)       # Python enum member name
    # Localized display text — see the note on Thithi.ml/en. Not seeded from the
    # enum; filled by db/sql/02_seed.sql on real DBs, NULL in db/seed.py DBs.
    ml:   Optional[str] = None           # Malayalam label
    en:   Optional[str] = None           # English label

    thithis: List["Thithi"] = Relationship(back_populates="paksha")
