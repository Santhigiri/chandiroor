from typing import TYPE_CHECKING, List

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.db.models.kollavarsham_date import KollavarshamDate


class MalayalamMasa(SQLModel, table=True):
    """One of the 12 Malayalam solar months (masa)."""

    __tablename__ = "malayalam_masa" # pyright: ignore[reportAssignmentType]

    id:   int = Field(primary_key=True)  # 1–12
    name: str = Field(unique=True)       # Python enum member name e.g. 'MEDAM'
    ml:   str
    en:   str

    kollavarsham_dates: List["KollavarshamDate"] = Relationship(back_populates="masa")
