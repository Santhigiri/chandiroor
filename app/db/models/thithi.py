from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

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
    # Localized display text — not seeded from the enums (which carry only
    # id/name/paksha/day); populated by db/sql/02_seed.sql on real databases,
    # left NULL in test/dev DBs seeded via db/seed.py. Kept in place (not
    # migrated away) so the v1 /api/v1/panchangam/thithi endpoint keeps
    # reading it unchanged — ThithiTranslation below is the v2 source.
    ml:        Optional[str] = None
    en:        Optional[str] = None

    paksha:      Optional["Paksha"]        = Relationship(back_populates="thithis")
    panchangams: List["Panchangam"]        = Relationship(back_populates="thithi")
    transitions: List["ThithiTransition"]  = Relationship(back_populates="thithi")
    translations: List["ThithiTranslation"] = Relationship(back_populates="thithi")


class ThithiTranslation(SQLModel, table=True):
    """One thithi's display text in one language — the v2 reference source.

    Row-per-(thithi, language_code), matching kumily's translation-table
    pattern. Coexists deliberately with ``Thithi.ml``/``Thithi.en`` above,
    which back the unchanged v1 endpoint.
    """

    __tablename__ = "thithi_translation" # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint("thithi_id", "language_code", name="uq_thithi_translation_thithi_language"),
    )

    id:            Optional[int] = Field(default=None, primary_key=True)
    thithi_id:     int = Field(index=True, foreign_key="thithi.id")
    language_code: str = Field(index=True)
    text:          str

    thithi: Optional["Thithi"] = Relationship(back_populates="translations")
