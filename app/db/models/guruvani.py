from typing import Optional

from sqlmodel import Field, SQLModel


class Guruvani(SQLModel, table=True):
    """A single bilingual Guruvani quote. ``sort_order`` preserves display order."""

    __tablename__ = "guruvani"  # pyright: ignore[reportAssignmentType]

    id:         Optional[int] = Field(default=None, primary_key=True)
    text_en:    str
    text_ml:    str
    sort_order: int = Field(index=True)
