"""
Getter and setter functions for PanchangamData backed by a SQL database.

Getter API mirrors the two API endpoints:
  - get_day_panchangam(db, date)          -> GET /panchangam/
  - get_monthly_panchangam(db, year, month) -> GET /panchangam/monthly

Setter API:
  - save_day_panchangam(db, data)
  - save_monthly_panchangam(db, monthly_data)
"""

from __future__ import annotations

from datetime import date
from typing import Dict, Optional

from sqlalchemy.orm import Session

from core.astronomy.nakshatra_transition import NakshatraTransition
from core.astronomy.thithi_transition import ThithiTransition
from core.calendar.kollavarsham import KollavarshamDate
from db.models import (
    NakshatraTransitionRow,
    PanchangamDay,
    SanthigiriDayEvent,
    ThithiTransitionRow,
)
from schemas.panchangam_data import PanchangamData
from utils.nakshatra import Nakshatra
from utils.santhigiri_events import SanthigiriEvent, SanthigiriEventId, EventCondition
from utils.thithi import Thithi


# ---------------------------------------------------------------------------
# Helpers: ORM row <-> Pydantic model
# ---------------------------------------------------------------------------

def _row_to_panchangam_data(row: PanchangamDay) -> PanchangamData:
    kv = KollavarshamDate(
        date=row.date,
        kv_day=row.kv_day,
        kv_month=row.kv_month,
        kv_year=row.kv_year,
        kv_month_name_en=row.kv_month_name_en,
        kv_month_name_ml=row.kv_month_name_ml,
    )

    thithi_transitions = [
        ThithiTransition(
            name=t.name,
            thithi=Thithi.from_id(t.thithi_id),
            start_time=t.start_time,
            end_time=t.end_time,
        )
        for t in row.thithi_transitions
    ]

    nakshatra_transitions = [
        NakshatraTransition(
            name=n.name,
            nakshatra=Nakshatra.from_id(n.nakshatra_id),
            start_time=n.start_time,
            end_time=n.end_time,
        )
        for n in row.nakshatra_transitions
    ]

    santhigiri_significant_dates = [
        SanthigiriEvent(
            id=SanthigiriEventId(e.event_id),
            name=e.name,
            description=e.description,
            event_condition=EventCondition(),
        )
        for e in row.santhigiri_events
    ]

    return PanchangamData(
        date=row.date,
        kv=kv,
        thithi_transitions=thithi_transitions,
        nakshatra_transitions=nakshatra_transitions,
        is_pournami=row.is_pournami,
        thithi=Thithi.from_id(row.thithi_id),
        nakshatra=Nakshatra.from_id(row.nakshatra_id),
        sunrise=row.sunrise,
        sunset=row.sunset,
        nazhika_from_sunrise=row.nazhika_from_sunrise,
        santhigiri_significant_dates=santhigiri_significant_dates,
    )


def _panchangam_data_to_row(data: PanchangamData) -> PanchangamDay:
    thithi_rows = [
        ThithiTransitionRow(
            date=data.date,
            thithi_id=t.thithi.id,
            name=t.name,
            start_time=t.start_time,
            end_time=t.end_time,
        )
        for t in data.thithi_transitions
    ]

    nakshatra_rows = [
        NakshatraTransitionRow(
            date=data.date,
            nakshatra_id=n.nakshatra.id,
            name=n.name,
            start_time=n.start_time,
            end_time=n.end_time,
        )
        for n in data.nakshatra_transitions
    ]

    event_rows = [
        SanthigiriDayEvent(
            date=data.date,
            event_id=e.id.value,
            name=e.name,
            description=e.description,
        )
        for e in data.santhigiri_significant_dates
    ]

    return PanchangamDay(
        date=data.date,
        thithi_id=data.thithi.id,
        nakshatra_id=data.nakshatra.id,
        is_pournami=data.is_pournami,
        sunrise=data.sunrise,
        sunset=data.sunset,
        nazhika_from_sunrise=data.nazhika_from_sunrise,
        kv_day=data.kv.kv_day,
        kv_month=data.kv.kv_month,
        kv_year=data.kv.kv_year,
        kv_month_name_en=data.kv.kv_month_name_en,
        kv_month_name_ml=data.kv.kv_month_name_ml,
        thithi_transitions=thithi_rows,
        nakshatra_transitions=nakshatra_rows,
        santhigiri_events=event_rows,
    )


# ---------------------------------------------------------------------------
# Getters  (mirror GET /panchangam/ and GET /panchangam/monthly)
# ---------------------------------------------------------------------------

def get_day_panchangam(db: Session, dt: date) -> Optional[PanchangamData]:
    """
    Return PanchangamData for a single date, or None if not stored.

    Mirrors GET /panchangam/?date_str=<dt>
    """
    row = db.get(PanchangamDay, dt)
    if row is None:
        return None
    return _row_to_panchangam_data(row)


def get_monthly_panchangam(
    db: Session, year: int, month: int
) -> Dict[str, PanchangamData]:
    """
    Return a dict of ISO date strings to PanchangamData for every stored
    day in the given year/month.

    Mirrors GET /panchangam/monthly?year=<year>&month=<month>
    """
    rows = (
        db.query(PanchangamDay)
        .filter(
            PanchangamDay.date >= date(year, month, 1),
            PanchangamDay.date
            < (
                date(year, month + 1, 1)
                if month < 12
                else date(year + 1, 1, 1)
            ),
        )
        .order_by(PanchangamDay.date)
        .all()
    )
    return {str(row.date): _row_to_panchangam_data(row) for row in rows}


# ---------------------------------------------------------------------------
# Setters
# ---------------------------------------------------------------------------

def save_day_panchangam(db: Session, data: PanchangamData) -> None:
    """
    Insert or replace a single day's panchangam data.

    Existing rows for the same date (including child transitions and events)
    are deleted before the new record is written, so callers can call this
    function idempotently.
    """
    existing = db.get(PanchangamDay, data.date)
    if existing is not None:
        db.delete(existing)
        db.flush()

    db.add(_panchangam_data_to_row(data))
    db.commit()


def save_monthly_panchangam(
    db: Session, monthly_data: Dict[date, PanchangamData]
) -> None:
    """
    Bulk insert or replace panchangam data for every day in monthly_data.

    Wraps all writes in a single transaction for efficiency.
    """
    dates = list(monthly_data.keys())
    if not dates:
        return

    # Remove any existing rows for these dates in one query
    existing = db.query(PanchangamDay).filter(PanchangamDay.date.in_(dates)).all()
    for row in existing:
        db.delete(row)
    db.flush()

    for data in monthly_data.values():
        db.add(_panchangam_data_to_row(data))

    db.commit()
