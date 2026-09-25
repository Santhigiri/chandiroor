from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

if TYPE_CHECKING:
    from app.db.models.thithi import Thithi


class Paksha(SQLModel, table=True):
    """Moon phase grouping — Shukla (waxing) or Krishna (waning)."""

    __tablename__ = "paksha" # pyright: ignore[reportAssignmentType]

    id:   int = Field(primary_key=True)  # 1=SHUKLA, 2=KRISHNA
    name: str = Field(unique=True)       # Python enum member name
    # Localized display text — see the note on Thithi.ml/en. Not seeded from the
    # enum; filled by db/sql/02_seed.sql on real DBs, NULL in db/seed.py DBs.
    # Kept in place so the v1 endpoint keeps reading it unchanged —
    # PakshaTranslation below is the v2 source.
    ml:   Optional[str] = None           # Malayalam label
    en:   Optional[str] = None           # English label

    thithis: List["Thithi"] = Relationship(back_populates="paksha")
    translations: List["PakshaTranslation"] = Relationship(back_populates="paksha")


class PakshaTranslation(SQLModel, table=True):
    """One paksha's display text in one language — the v2 reference source."""

    __tablename__ = "paksha_translation" # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint("paksha_id", "language_code", name="uq_paksha_translation_paksha_language"),
    )

    id:            Optional[int] = Field(default=None, primary_key=True)
    paksha_id:     int = Field(index=True, foreign_key="paksha.id")
    language_code: str = Field(index=True)
    text:          str

    paksha: Optional["Paksha"] = Relationship(back_populates="translations")
