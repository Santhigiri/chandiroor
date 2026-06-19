from datetime import date, datetime
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class PanchangamDay(Base):
    """One row per Gregorian date; mirrors the PanchangamData Pydantic model."""

    __tablename__ = "panchangam_day"

    date: Mapped[date] = mapped_column(Date, primary_key=True)

    # Primary thithi for the day
    thithi_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Primary nakshatra for the day
    nakshatra_id: Mapped[int] = mapped_column(Integer, nullable=False)

    is_pournami: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    sunrise: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sunset: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    nazhika_from_sunrise: Mapped[float] = mapped_column(Float, nullable=False)

    # Kollavarsham (Malayalam calendar) fields
    kv_day: Mapped[int] = mapped_column(Integer, nullable=False)
    kv_month: Mapped[int] = mapped_column(Integer, nullable=False)
    kv_year: Mapped[int] = mapped_column(Integer, nullable=False)
    kv_month_name_en: Mapped[str] = mapped_column(String(64), nullable=False)
    kv_month_name_ml: Mapped[str] = mapped_column(String(64), nullable=False)

    thithi_transitions: Mapped[list["ThithiTransitionRow"]] = relationship(
        back_populates="day", cascade="all, delete-orphan"
    )
    nakshatra_transitions: Mapped[list["NakshatraTransitionRow"]] = relationship(
        back_populates="day", cascade="all, delete-orphan"
    )
    santhigiri_events: Mapped[list["SanthigiriDayEvent"]] = relationship(
        back_populates="day", cascade="all, delete-orphan"
    )


class ThithiTransitionRow(Base):
    """Each thithi period that overlaps a given date."""

    __tablename__ = "thithi_transition"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, ForeignKey("panchangam_day.date"), nullable=False)

    thithi_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    day: Mapped["PanchangamDay"] = relationship(back_populates="thithi_transitions")


class NakshatraTransitionRow(Base):
    """Each nakshatra period that overlaps a given date."""

    __tablename__ = "nakshatra_transition"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, ForeignKey("panchangam_day.date"), nullable=False)

    nakshatra_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    day: Mapped["PanchangamDay"] = relationship(back_populates="nakshatra_transitions")


class SanthigiriDayEvent(Base):
    """Significant Santhigiri events that fall on a given date."""

    __tablename__ = "santhigiri_day_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, ForeignKey("panchangam_day.date"), nullable=False)

    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    day: Mapped["PanchangamDay"] = relationship(back_populates="santhigiri_events")
