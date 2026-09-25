from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

if TYPE_CHECKING:
    from app.db.models.kollavarsham_date import KollavarshamDate


class MalayalamMasa(SQLModel, table=True):
    """One of the 12 Malayalam solar months (masa)."""

    __tablename__ = "malayalam_masa" # pyright: ignore[reportAssignmentType]

    id:   int = Field(primary_key=True)  # 1–12
    name: str = Field(unique=True)       # Python enum member name e.g. 'MEDAM'
    # Localized display text — see the note on Thithi.ml/en. Not seeded from the
    # enum; filled by db/sql/02_seed.sql on real DBs, NULL in db/seed.py DBs.
    # Kept in place so the v1 endpoint keeps reading it unchanged —
    # MalayalamMasaTranslation below is the v2 source.
    ml:   Optional[str] = None
    en:   Optional[str] = None

    kollavarsham_dates: List["KollavarshamDate"] = Relationship(back_populates="masa")
    translations: List["MalayalamMasaTranslation"] = Relationship(back_populates="masa")


class MalayalamMasaTranslation(SQLModel, table=True):
    """One malayalam masa's display text in one language — the v2 reference source."""

    __tablename__ = "malayalam_masa_translation" # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint(
            "malayalam_masa_id", "language_code", name="uq_malayalam_masa_translation_masa_language"
        ),
    )

    id:                Optional[int] = Field(default=None, primary_key=True)
    malayalam_masa_id: int = Field(index=True, foreign_key="malayalam_masa.id")
    language_code:     str = Field(index=True)
    text:              str

    masa: Optional["MalayalamMasa"] = Relationship(back_populates="translations")
