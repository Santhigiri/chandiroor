import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, Date, ForeignKey
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from db.models.malayalam_masa import MalayalamMasa
    from db.models.panchangam import Panchangam


class KollavarshamDate(SQLModel, table=True):
    """Malayalam solar calendar date corresponding to each panchangam day."""

    __tablename__ = "kollavarsham_date" # pyright: ignore[reportAssignmentType]

    date: datetime.date = Field(
        sa_column=Column(
            Date,
            ForeignKey("panchangam.date", ondelete="CASCADE"),
            primary_key=True,
        )
    )
    kv_day:   int  # day of the Malayalam month
    kv_month: int  = Field(foreign_key="malayalam_masa.id")  # MalayalamMasa id (1–12)
    kv_year:  int  # Kollam Era year

    masa:       Optional["MalayalamMasa"] = Relationship(back_populates="kollavarsham_dates")
    panchangam: Optional["Panchangam"]    = Relationship(back_populates="kollavarsham")
