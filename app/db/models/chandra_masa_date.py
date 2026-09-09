import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKeyConstraint
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.db.models.chandra_masa import ChandraMasa
    from app.db.models.panchangam import Panchangam


class ChandraMasaDate(SQLModel, table=True):
    """Lunar (Amanta) calendar date corresponding to each panchangam day.

    Keyed on ``(date, location_id)`` — one row per panchangam ``(date,
    location_id)`` — because the month boundary and day count are derived
    from the local sunrise thithi and therefore depend on the location's
    coordinates.
    """

    __tablename__ = "chandra_masa_date" # pyright: ignore[reportAssignmentType]

    __table_args__ = (
        ForeignKeyConstraint(
            ["date", "location_id"],
            ["panchangam.date", "panchangam.location_id"],
            ondelete="CASCADE",
        ),
    )

    date:        datetime.date = Field(primary_key=True)
    location_id: int           = Field(primary_key=True)
    masa_id:     int  = Field(foreign_key="chandra_masa.id")  # ChandraMasa id (1–12)
    masa_day:    int  # day of the lunar (Amanta) month
    masa_type:   int  # MasaType id: 1=Nija (regular), 2=Adhika (leap), 3=Kshaya (deficit)

    masa:       Optional["ChandraMasa"] = Relationship(back_populates="chandra_masa_dates")
    panchangam: Optional["Panchangam"]  = Relationship(back_populates="chandra_masa")
