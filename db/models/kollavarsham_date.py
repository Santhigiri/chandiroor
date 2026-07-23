import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKeyConstraint
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from db.models.malayalam_masa import MalayalamMasa
    from db.models.panchangam import Panchangam


class KollavarshamDate(SQLModel, table=True):
    """Malayalam solar calendar date corresponding to each panchangam day.

    Keyed on ``(date, location_id)`` — one row per panchangam ``(date,
    location_id)`` — because the Malayalam day/month is derived from the local
    sunset raasi and therefore depends on the location's coordinates.
    """

    __tablename__ = "kollavarsham_date" # pyright: ignore[reportAssignmentType]

    __table_args__ = (
        ForeignKeyConstraint(
            ["date", "location_id"],
            ["panchangam.date", "panchangam.location_id"],
            ondelete="CASCADE",
        ),
    )

    date:        datetime.date = Field(primary_key=True)
    location_id: int           = Field(primary_key=True)
    kv_day:   int  # day of the Malayalam month
    kv_month: int  = Field(foreign_key="malayalam_masa.id")  # MalayalamMasa id (1–12)
    kv_year:  int  # Kollam Era year

    masa:       Optional["MalayalamMasa"] = Relationship(back_populates="kollavarsham_dates")
    panchangam: Optional["Panchangam"]    = Relationship(back_populates="kollavarsham")
