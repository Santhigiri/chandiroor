from __future__ import annotations

import datetime
from typing import List, Optional

from sqlalchemy import Column, Date, ForeignKey, Index, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


# ─────────────────────────────────────────────────────────────────────────────
# LOOKUP TABLES
# Seeded once from Python enums at init; never written at runtime.
# ─────────────────────────────────────────────────────────────────────────────

class Paksha(SQLModel, table=True):
    """Moon phase grouping — Shukla (waxing) or Krishna (waning)."""

    __tablename__ = "paksha"

    id:   int = Field(primary_key=True)   # 1=SHUKLA, 2=KRISHNA
    name: str = Field(unique=True)        # Python enum member name
    ml:   str                             # Malayalam label
    en:   str                             # English label

    thithis: List[Thithi] = Relationship(back_populates="paksha")


class Nakshatra(SQLModel, table=True):
    """One of the 27 lunar mansions."""

    __tablename__ = "nakshatra"

    id:   int = Field(primary_key=True)   # 1–27
    name: str = Field(unique=True)        # Python enum member name e.g. 'ASWATHI'
    ml:   str
    en:   str

    panchangams: List[Panchangam]          = Relationship(back_populates="nakshatra")
    transitions: List[NakshatraTransition] = Relationship(back_populates="nakshatra")


class Thithi(SQLModel, table=True):
    """One of the 30 lunar days (15 per paksha)."""

    __tablename__ = "thithi"

    id:        int = Field(primary_key=True)        # 1–30
    name:      str = Field(unique=True)             # Python enum member name e.g. 'PRATHAMA_SHUKLA'
    paksha_id: int = Field(foreign_key="paksha.id")
    day:       int                                  # day within paksha (1–15)
    ml:        str
    en:        str

    paksha:      Optional[Paksha]         = Relationship(back_populates="thithis")
    panchangams: List[Panchangam]         = Relationship(back_populates="thithi")
    transitions: List[ThithiTransition]  = Relationship(back_populates="thithi")


# ─────────────────────────────────────────────────────────────────────────────
# CORE FACT TABLE
# ─────────────────────────────────────────────────────────────────────────────

class Panchangam(SQLModel, table=True):
    """
    One row per calendar date.

    Holds only date-level astronomical facts. Everything location-specific
    (sunrise/sunset) or structurally separate (kollavarsham, transitions,
    events) lives in its own child table.
    """

    __tablename__ = "panchangam"

    date:                 datetime.date = Field(primary_key=True)
    is_pournami:          bool
    thithi_id:            int           = Field(foreign_key="thithi.id")
    nakshatra_id:         int           = Field(foreign_key="nakshatra.id")
    nazhika_from_sunrise: float

    thithi:                Optional[Thithi]                 = Relationship(back_populates="panchangams")
    nakshatra:             Optional[Nakshatra]               = Relationship(back_populates="panchangams")
    kollavarsham:          Optional[KollavarshamDate]        = Relationship(back_populates="panchangam")
    sunrise_sunsets:       List[SunriseSunset]               = Relationship(back_populates="panchangam")
    thithi_transitions:    List[ThithiTransition]            = Relationship(back_populates="panchangam")
    nakshatra_transitions: List[NakshatraTransition]         = Relationship(back_populates="panchangam")
    santhigiri_events:     List[SanthigiriSignificantDate]   = Relationship(back_populates="panchangam")


# ─────────────────────────────────────────────────────────────────────────────
# 1:1 CHILD — Kollavarsham (Malayalam solar calendar) date
# ─────────────────────────────────────────────────────────────────────────────

class KollavarshamDate(SQLModel, table=True):
    """Malayalam solar calendar date corresponding to each panchangam day."""

    __tablename__ = "kollavarsham_date"

    date: datetime.date = Field(
        sa_column=Column(
            Date,
            ForeignKey("panchangam.date", ondelete="CASCADE"),
            primary_key=True,
        )
    )
    kv_day:           int  # day of the Malayalam month
    kv_month:         int  # MalayalamMasa id (1–12)
    kv_year:          int  # Kollam Era year
    kv_month_name_en: str
    kv_month_name_ml: str

    panchangam: Optional[Panchangam] = Relationship(back_populates="kollavarsham")


# ─────────────────────────────────────────────────────────────────────────────
# LOCATION-SPECIFIC — sunrise & sunset vary by latitude/longitude
# ─────────────────────────────────────────────────────────────────────────────

class SunriseSunset(SQLModel, table=True):
    """
    Sunrise and sunset times for a given date and geographic location.

    Keyed on (date, latitude, longitude) so multiple locations can be
    cached without duplicating astronomical data in the panchangam table.
    """

    __tablename__ = "sunrise_sunset"
    __table_args__ = (
        UniqueConstraint("date", "latitude", "longitude", name="uq_sunrise_sunset_date_loc"),
        Index("idx_sunrise_sunset_date", "date"),
    )

    id:        Optional[int]          = Field(default=None, primary_key=True)
    date:      datetime.date          = Field(
        sa_column=Column(
            Date,
            ForeignKey("panchangam.date", ondelete="CASCADE"),
            nullable=False,
        )
    )
    latitude:  float
    longitude: float
    timezone:  str
    sunrise:   datetime.datetime
    sunset:    datetime.datetime

    panchangam: Optional[Panchangam] = Relationship(back_populates="sunrise_sunsets")


# ─────────────────────────────────────────────────────────────────────────────
# 1:MANY — transitions within a calendar day
# ─────────────────────────────────────────────────────────────────────────────

class ThithiTransition(SQLModel, table=True):
    """A thithi (lunar day) phase active during part of a calendar day."""

    __tablename__ = "thithi_transitions"
    __table_args__ = (
        # Composite covers filter-by-date + order-by-time in one scan
        Index("idx_thithi_transitions_date", "panchangam_date", "start_time"),
    )

    id:             Optional[int]           = Field(default=None, primary_key=True)
    panchangam_date: datetime.date          = Field(
        sa_column=Column(
            Date,
            ForeignKey("panchangam.date", ondelete="CASCADE"),
            nullable=False,
        )
    )
    thithi_id:  int                         = Field(foreign_key="thithi.id")
    start_time: datetime.datetime
    end_time:   Optional[datetime.datetime] = None  # NULL = open-ended last transition

    panchangam: Optional[Panchangam] = Relationship(back_populates="thithi_transitions")
    thithi:     Optional[Thithi]     = Relationship(back_populates="transitions")


class NakshatraTransition(SQLModel, table=True):
    """A nakshatra (lunar mansion) active during part of a calendar day."""

    __tablename__ = "nakshatra_transitions"
    __table_args__ = (
        Index("idx_nakshatra_transitions_date", "panchangam_date", "start_time"),
    )

    id:             Optional[int]           = Field(default=None, primary_key=True)
    panchangam_date: datetime.date          = Field(
        sa_column=Column(
            Date,
            ForeignKey("panchangam.date", ondelete="CASCADE"),
            nullable=False,
        )
    )
    nakshatra_id: int                       = Field(foreign_key="nakshatra.id")
    start_time:   datetime.datetime
    end_time:     Optional[datetime.datetime] = None

    panchangam: Optional[Panchangam]  = Relationship(back_populates="nakshatra_transitions")
    nakshatra:  Optional[Nakshatra]   = Relationship(back_populates="transitions")


# ─────────────────────────────────────────────────────────────────────────────
# 1:MANY — Santhigiri ashram significant events
# ─────────────────────────────────────────────────────────────────────────────

class SanthigiriSignificantDate(SQLModel, table=True):
    """A significant Santhigiri ashram event that falls on a panchangam date."""

    __tablename__ = "santhigiri_significant_dates"
    __table_args__ = (
        Index("idx_santhigiri_events_date", "panchangam_date"),
    )

    id:             Optional[int]  = Field(default=None, primary_key=True)
    panchangam_date: datetime.date = Field(
        sa_column=Column(
            Date,
            ForeignKey("panchangam.date", ondelete="CASCADE"),
            nullable=False,
        )
    )
    event_id:    str  # SanthigiriEventId str-enum value
    name:        str
    description: str

    panchangam: Optional[Panchangam] = Relationship(back_populates="santhigiri_events")
