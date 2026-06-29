"""
PanchangamRepository — get and set PanchangamData via the SQLite database.

SQL model classes are imported with a ``Row`` suffix throughout this module to
avoid name collisions with the identically-named domain types from
core/astronomy and utils.
"""
from __future__ import annotations

import datetime
from typing import Dict, Iterable, List, Optional, Sequence

from sqlalchemy import delete
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

# ── SQL model aliases ─────────────────────────────────────────────────────────
from db.models.kollavarsham_date import KollavarshamDate as KollavarshamDateRow
from db.models.nakshatra_transition import NakshatraTransition as NakshatraTransitionRow
from db.models.panchangam import Panchangam as PanchangamRow
from db.models.santhigiri_event_condition import (
    SanthigiriEventCondition as SanthigiriEventConditionRow,
)
from db.models.santhigiri_significant_date import (
    SanthigiriSignificantDate as SanthigiriSignificantDateRow,
)
from db.models.sunrise_sunset import SunriseSunset as SunriseSunsetRow
from db.models.thithi_transition import ThithiTransition as ThithiTransitionRow

# ── Domain types ──────────────────────────────────────────────────────────────
from core.astronomy.nakshatra_transition import NakshatraTransition
from core.astronomy.thithi_transition import ThithiTransition
from core.calendar.kollavarsham import KollavarshamDate
from core.constants import DEFAULT_TIMEZONE, Coordinates
from schemas.panchangam_data import PanchangamData
from utils.malayalam_masa import MalayalamMasa
from utils.nakshatra import Nakshatra
from utils.santhigiri_events import EventCondition, SanthigiriEvent, SanthigiriEventId
from utils.thithi import Thithi


# ── SQL row → domain type conversions ────────────────────────────────────────

def _row_to_panchangam_data(row: PanchangamRow) -> PanchangamData:
    kv_row = row.kollavarsham
    kv = KollavarshamDate(
        date=kv_row.date,
        kv_day=kv_row.kv_day,
        kv_month=kv_row.kv_month,
        kv_year=kv_row.kv_year,
        kv_month_name_en=kv_row.kv_month_name_en,
        kv_month_name_ml=kv_row.kv_month_name_ml,
    )

    sg_lat, sg_lon = Coordinates.SG_LATITUDE, Coordinates.SG_LONGITUDE
    ss_row = next(
        (
            s for s in row.sunrise_sunsets
            if abs(s.latitude - sg_lat) < 1e-3 and abs(s.longitude - sg_lon) < 1e-3
        ),
        row.sunrise_sunsets[0] if row.sunrise_sunsets else None,
    )

    thithi_transitions = [
        ThithiTransition(
            name=Thithi.from_id(t.thithi_id).en,
            thithi=Thithi.from_id(t.thithi_id),
            start_time=t.start_time,
            end_time=t.end_time,
        )
        for t in sorted(row.thithi_transitions, key=lambda t: t.start_time)
    ]

    nakshatra_transitions = [
        NakshatraTransition(
            name=Nakshatra.from_id(n.nakshatra_id).en,
            nakshatra=Nakshatra.from_id(n.nakshatra_id),
            start_time=n.start_time,
            end_time=n.end_time,
        )
        for n in sorted(row.nakshatra_transitions, key=lambda n: n.start_time)
    ]

    santhigiri_events = [_ssd_row_to_event(e) for e in row.santhigiri_events]

    return PanchangamData(
        date=row.date,
        kv=kv,
        thithi_transitions=thithi_transitions,
        nakshatra_transitions=nakshatra_transitions,
        is_pournami=row.is_pournami,
        thithi=Thithi.from_id(row.thithi_id),
        nakshatra=Nakshatra.from_id(row.nakshatra_id),
        sunrise=ss_row.sunrise if ss_row else None,
        sunset=ss_row.sunset if ss_row else None,
        nazhika_from_sunrise=row.nazhika_from_sunrise,
        santhigiri_significant_dates=santhigiri_events,
    )


def _ssd_row_to_event(row: SanthigiriSignificantDateRow) -> SanthigiriEvent:
    ec = row.event_condition
    if ec is not None:
        cond = EventCondition(
            nakshatra=Nakshatra.from_id(ec.nakshatra_id) if ec.nakshatra_id else None,
            thithi=Thithi.from_id(ec.thithi_id) if ec.thithi_id else None,
            ml_day=ec.ml_day,
            ml_month=MalayalamMasa.from_id(ec.ml_month) if ec.ml_month else None,
            ml_year=ec.ml_year,
            en_day=ec.en_day,
            en_month=ec.en_month,
            en_year=ec.en_year,
            occurance=ec.occurance,
            is_poornima=ec.is_poornima,
            last_occurance=ec.last_occurance,
        )
    else:
        cond = EventCondition()
    return SanthigiriEvent(
        id=SanthigiriEventId(row.event_id),
        name=row.name,
        description=row.description,
        event_condition=cond,
    )


# ── Domain type → SQL row conversions ────────────────────────────────────────

def _event_condition_to_row(event: SanthigiriEvent) -> Optional[SanthigiriEventConditionRow]:
    """Return an EventCondition row when the event carries any matching criteria."""
    c = event.event_condition
    if not any([
        c.nakshatra, c.thithi, c.ml_day, c.ml_month, c.ml_year,
        c.en_day, c.en_month, c.en_year, c.occurance, c.is_poornima, c.last_occurance,
    ]):
        return None
    return SanthigiriEventConditionRow(
        event_id=event.id.value,
        nakshatra_id=c.nakshatra.id if c.nakshatra else None,
        thithi_id=c.thithi.id if c.thithi else None,
        ml_day=c.ml_day,
        ml_month=c.ml_month.id if c.ml_month else None,
        ml_year=c.ml_year,
        en_day=c.en_day,
        en_month=c.en_month,
        en_year=c.en_year,
        occurance=c.occurance,
        is_poornima=c.is_poornima,
        last_occurance=c.last_occurance,
    )


# ── Eager-load strategy used by all getters ───────────────────────────────────

_LOAD_OPTIONS = (
    selectinload(PanchangamRow.kollavarsham),
    selectinload(PanchangamRow.sunrise_sunsets),
    selectinload(PanchangamRow.thithi_transitions),
    selectinload(PanchangamRow.nakshatra_transitions),
    selectinload(PanchangamRow.santhigiri_events).selectinload(
        SanthigiriSignificantDateRow.event_condition
    ),
)


# ── Repository ────────────────────────────────────────────────────────────────

class PanchangamRepository:
    """
    Getters and setters for PanchangamData backed by SQLite.

    Caller is responsible for committing the session.  ``upsert`` and
    ``upsert_many`` deliberately do not commit so that multiple writes can be
    batched into one transaction by the caller.  ``upsert_many`` is the
    exception: it commits once at the end for convenience.
    """

    def __init__(self, session: Session) -> None:
        self._s = session

    # ── Getters ──────────────────────────────────────────────────────────────

    def get_by_date(self, date: datetime.date) -> Optional[PanchangamData]:
        """Return PanchangamData for *date*, or None if the date is not in the DB."""
        stmt = (
            select(PanchangamRow)
            .where(PanchangamRow.date == date)
            .options(*_LOAD_OPTIONS)
        )
        row = self._s.exec(stmt).first()
        return _row_to_panchangam_data(row) if row else None

    def get_by_date_range(
        self,
        start: datetime.date,
        end: datetime.date,
    ) -> Dict[datetime.date, PanchangamData]:
        """Return a date-keyed dict for all dates in [start, end] inclusive."""
        stmt = (
            select(PanchangamRow)
            .where(PanchangamRow.date >= start, PanchangamRow.date <= end)
            .order_by(PanchangamRow.date)
            .options(*_LOAD_OPTIONS)
        )
        rows = self._s.exec(stmt).all()
        return {row.date: _row_to_panchangam_data(row) for row in rows}

    def get_by_month(self, year: int, month: int) -> Dict[datetime.date, PanchangamData]:
        """Return a date-keyed dict for every day in the given calendar month."""
        start = datetime.date(year, month, 1)
        if month == 12:
            end = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
        else:
            end = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
        return self.get_by_date_range(start, end)

    # ── Setters ──────────────────────────────────────────────────────────────

    def upsert(self, data: PanchangamData) -> None:
        """
        Write one PanchangamData to the DB, replacing any existing row for
        that date.  Does NOT commit — caller must call session.commit().
        """
        self._delete_children(data.date)

        self._s.merge(
            PanchangamRow(
                date=data.date,
                is_pournami=data.is_pournami,
                thithi_id=data.thithi.id,
                nakshatra_id=data.nakshatra.id,
                nazhika_from_sunrise=data.nazhika_from_sunrise,
            )
        )
        self._s.flush()

        self._s.add(
            KollavarshamDateRow(
                date=data.date,
                kv_day=data.kv.kv_day,
                kv_month=data.kv.kv_month,
                kv_year=data.kv.kv_year,
                kv_month_name_en=data.kv.kv_month_name_en,
                kv_month_name_ml=data.kv.kv_month_name_ml,
            )
        )
        self._s.add(
            SunriseSunsetRow(
                date=data.date,
                latitude=Coordinates.SG_LATITUDE,
                longitude=Coordinates.SG_LONGITUDE,
                timezone=DEFAULT_TIMEZONE,
                sunrise=data.sunrise,
                sunset=data.sunset,
            )
        )
        for t in data.thithi_transitions:
            self._s.add(
                ThithiTransitionRow(
                    panchangam_date=data.date,
                    thithi_id=t.thithi.id,
                    start_time=t.start_time,
                    end_time=t.end_time,
                )
            )
        for n in data.nakshatra_transitions:
            self._s.add(
                NakshatraTransitionRow(
                    panchangam_date=data.date,
                    nakshatra_id=n.nakshatra.id,
                    start_time=n.start_time,
                    end_time=n.end_time,
                )
            )
        for event in data.santhigiri_significant_dates:
            ec_row = _event_condition_to_row(event)
            ec_id: Optional[int] = None
            if ec_row is not None:
                self._s.add(ec_row)
                self._s.flush()
                ec_id = ec_row.id
            self._s.add(
                SanthigiriSignificantDateRow(
                    panchangam_date=data.date,
                    event_id=event.id.value,
                    name=event.name,
                    description=event.description,
                    event_condition_id=ec_id,
                )
            )

    def upsert_many(self, data: Iterable[PanchangamData]) -> None:
        """Write multiple PanchangamData objects and commit in one transaction."""
        for item in data:
            self.upsert(item)
        self._s.commit()

    # ── Private helpers ───────────────────────────────────────────────────────

    def _delete_children(self, date: datetime.date) -> None:
        """Delete all child rows for *date* so upsert can re-insert them cleanly."""
        existing_ssd: Sequence[SanthigiriSignificantDateRow] = self._s.exec(
            select(SanthigiriSignificantDateRow).where(
                col(SanthigiriSignificantDateRow.panchangam_date) == date
            )
        ).all()
        ec_ids = [r.event_condition_id for r in existing_ssd if r.event_condition_id is not None]

        self._s.exec(
            delete(SanthigiriSignificantDateRow).where(
                col(SanthigiriSignificantDateRow.panchangam_date) == date
            )
        )
        for ec_id in ec_ids:
            self._s.exec(
                delete(SanthigiriEventConditionRow).where(
                    col(SanthigiriEventConditionRow.id) == ec_id
                )
            )
        self._s.exec(
            delete(ThithiTransitionRow).where(col(ThithiTransitionRow.panchangam_date) == date)
        )
        self._s.exec(
            delete(NakshatraTransitionRow).where(col(NakshatraTransitionRow.panchangam_date) == date)
        )
        self._s.exec(
            delete(KollavarshamDateRow).where(col(KollavarshamDateRow.date) == date)
        )
        self._s.exec(
            delete(SunriseSunsetRow).where(col(SunriseSunsetRow.date) == date)
        )
