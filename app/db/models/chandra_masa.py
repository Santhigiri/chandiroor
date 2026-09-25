from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

if TYPE_CHECKING:
    from app.db.models.chandra_masa_date import ChandraMasaDate


class ChandraMasa(SQLModel, table=True):
    """One of the 12 lunar (Amanta) months (masa)."""

    __tablename__ = "chandra_masa" # pyright: ignore[reportAssignmentType]

    id:   int = Field(primary_key=True)  # 1–12
    name: str = Field(unique=True)       # Python enum member name e.g. 'CHAITRA'
    # Localized display text — see the note on Thithi.ml/en. Not seeded from the
    # enum; filled by db/sql/02_seed.sql on real DBs, NULL in db/seed.py DBs.
    # Kept in place so the v1 endpoint keeps reading it unchanged —
    # ChandraMasaTranslation below is the v2 source.
    ml:   Optional[str] = None
    en:   Optional[str] = None

    chandra_masa_dates: List["ChandraMasaDate"] = Relationship(back_populates="masa")
    translations: List["ChandraMasaTranslation"] = Relationship(back_populates="masa")


class ChandraMasaTranslation(SQLModel, table=True):
    """One chandra masa's display text in one language — the v2 reference source."""

    __tablename__ = "chandra_masa_translation" # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint(
            "chandra_masa_id", "language_code", name="uq_chandra_masa_translation_masa_language"
        ),
    )

    id:              Optional[int] = Field(default=None, primary_key=True)
    chandra_masa_id: int = Field(index=True, foreign_key="chandra_masa.id")
    language_code:   str = Field(index=True)
    text:            str

    masa: Optional["ChandraMasa"] = Relationship(back_populates="translations")
