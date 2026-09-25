from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

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
    # Kept in place so the v1 endpoint keeps reading it unchanged —
    # NakshatraTranslation below is the v2 source.
    ml:   Optional[str] = None
    en:   Optional[str] = None

    panchangams: List["Panchangam"]           = Relationship(back_populates="nakshatra")
    transitions: List["NakshatraTransition"]  = Relationship(back_populates="nakshatra")
    translations: List["NakshatraTranslation"] = Relationship(back_populates="nakshatra")


class NakshatraTranslation(SQLModel, table=True):
    """One nakshatra's display text in one language — the v2 reference source."""

    __tablename__ = "nakshatra_translation" # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint("nakshatra_id", "language_code", name="uq_nakshatra_translation_nakshatra_language"),
    )

    id:            Optional[int] = Field(default=None, primary_key=True)
    nakshatra_id:  int = Field(index=True, foreign_key="nakshatra.id")
    language_code: str = Field(index=True)
    text:          str

    nakshatra: Optional["Nakshatra"] = Relationship(back_populates="translations")
