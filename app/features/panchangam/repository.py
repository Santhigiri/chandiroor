"""
PanchangamRepository — the concrete adapter implementing PanchangamRepositoryPort
against Postgres: get/set PanchangamData via SQLModel.

SQL model classes are imported with a ``Row`` suffix throughout this module to
avoid name collisions with the identically-named domain types from
core/astronomy and utils.
"""
from __future__ import annotations

import datetime
from typing import Dict, Iterable, List, Optional, Sequence

from sqlalchemy import delete, insert
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

# ── SQL model aliases ─────────────────────────────────────────────────────────
from app.db.models.chandra_masa_date import ChandraMasaDate as ChandraMasaDateRow
from app.db.models.kollavarsham_date import KollavarshamDate as KollavarshamDateRow
from app.db.models.nakshatra_transition import NakshatraTransition as NakshatraTransitionRow
from app.db.models.panchangam import Panchangam as PanchangamRow
from app.db.models.santhigiri_event import SanthigiriEvent as SanthigiriEventRow
from app.db.models.santhigiri_event_date import (
    SanthigiriEventDate as SanthigiriEventDateRow,
)
from app.db.models.sunrise_sunset import SunriseSunset as SunriseSunsetRow
from app.db.models.thithi_transition import ThithiTransition as ThithiTransitionRow

# ── Domain types ──────────────────────────────────────────────────────────────
from app.core.astronomy.transitions import NakshatraTransition, ThithiTransition
from app.core.chandramasa.chandramasa import get_chandra_masa_date
from app.core.chandramasa.chandramasa_models import ChandraMasaDate
from app.core.kollavarsham.kollavarsham_models import KollavarshamDate
from app.features.panchangam.ports import PanchangamRepositoryPort
from app.schemas.location import LocationInfo
from app.schemas.panchangam_data import PanchangamData
from app.utils.location import Location
from app.core.kollavarsham.enums.masa import MalayalamMasa
from app.core.chandramasa.enums.masa import ChandraMasa
from app.core.astronomy.enums.nakshatra import Nakshatra
from app.utils.santhigiri_events import EventCondition, SanthigiriEvent
from app.core.astronomy.enums.thithi import Thithi

from app.db.typing_utils import col as TypedColumn


# Chunk size for IN(...)-list deletes issued by upsert_many's bulk path. Well
# under both Postgres's parameter limit and SQLite's (>=3.32.0 default of
# 32766, but older builds cap at 999) so it stays portable across the
# Postgres/Neon runtime and the in-memory SQLite test engine.
_DELETE_CHUNK_SIZE = 500


def _chunked(items: Sequence, size: int) -> Iterable[Sequence]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


# ── SQL row → domain type conversions ────────────────────────────────────────

def _row_to_panchangam_data(
    row: PanchangamRow,
    location: Location,
    santhigiri_events: List[SanthigiriEvent],
) -> PanchangamData:
    kv_row = row.kollavarsham
    if kv_row is None:
        raise ValueError("kv_row is None")
    kv = KollavarshamDate(
        date=kv_row.date,
        kv_day=kv_row.kv_day,
        kv_month=kv_row.kv_month,
        kv_year=kv_row.kv_year,
    )

    cm_row = row.chandra_masa
    if cm_row is None:
        # A row written before chandra_masa_date existed (or a DB whose seed
        # predates this feature) has no sub-row here yet -- fall back to a
        # live, self-contained computation rather than 500ing the whole day.
        # get_chandra_masa_date is @lru_cache'd and only needs date+location,
        # unlike kv_row/ss_row below which have no equivalent standalone path.
        chandra_masa = get_chandra_masa_date(
            dt=row.date,
            latitude=location.latitude,
            longitude=location.longitude,
            timezone=location.timezone,
        )
    else:
        chandra_masa = ChandraMasaDate(
            date=cm_row.date,
            masa=cm_row.masa_id,
            masa_day=cm_row.masa_day,
            masa_type=cm_row.masa_type,
        )

    # One-to-one now that panchangam is keyed by (date, location_id).
    ss_row = row.sunrise_sunset

    thithi_transitions = [
        ThithiTransition(
            thithi=Thithi.from_id(t.thithi_id),
            start_time=t.start_time,
            end_time=t.end_time,
        )
        for t in sorted(row.thithi_transitions, key=lambda t: t.start_time)
    ]

    nakshatra_transitions = [
        NakshatraTransition(
            nakshatra=Nakshatra.from_id(n.nakshatra_id),
            start_time=n.start_time,
            end_time=n.end_time,
        )
        for n in sorted(row.nakshatra_transitions, key=lambda n: n.start_time)
    ]

    if ss_row is None:
        raise ValueError("ss_row cannot be None")

    return PanchangamData(
        date=row.date,
        kv=kv,
        chandra_masa=chandra_masa,
        thithi_transitions=thithi_transitions,
        nakshatra_transitions=nakshatra_transitions,
        thithi=Thithi.from_id(row.thithi_id),
        nakshatra=Nakshatra.from_id(row.nakshatra_id),
        sunrise=ss_row.sunrise,
        sunset=ss_row.sunset,
        nazhika_from_sunrise=row.nazhika_from_sunrise,
        santhigiri_significant_dates=santhigiri_events,
        location=LocationInfo.from_location(location),
    )


def event_row_to_event(ev: SanthigiriEventRow) -> SanthigiriEvent:
    """Map an editable ``santhigiri_event`` row to its domain ``SanthigiriEvent``."""
    cond = EventCondition(
        nakshatra=Nakshatra.from_id(ev.nakshatra_id) if ev.nakshatra_id else None,
        thithi=Thithi.from_id(ev.thithi_id) if ev.thithi_id else None,
        ml_day=ev.ml_day,
        ml_month=MalayalamMasa.from_id(ev.ml_month) if ev.ml_month else None,
        ml_year=ev.ml_year,
        chandra_masa_day=ev.chandra_masa_day,
        chandra_masa_month=ChandraMasa.from_id(ev.chandra_masa_month) if ev.chandra_masa_month else None,
        en_day=ev.en_day,
        en_month=ev.en_month,
        en_year=ev.en_year,
        occurance=ev.occurance,
        is_poornima=ev.is_poornima,
        last_occurance=ev.last_occurance,
        day_offset=ev.day_offset,
    )
    return SanthigiriEvent(
        id=ev.id,
        name=ev.name,
        description=ev.description,
        event_condition=cond,
    )


def _ssd_row_to_event(row: SanthigiriEventDateRow) -> SanthigiriEvent:
    ev = row.event
    if ev is None:
        raise ValueError(f"No santhigiri_event definition for {row.event_id!r}")
    return event_row_to_event(ev)


# ── Eager-load strategy used by all getters ───────────────────────────────────

_LOAD_OPTIONS = (
    selectinload(TypedColumn(PanchangamRow.kollavarsham)),
    selectinload(TypedColumn(PanchangamRow.chandra_masa)),
    selectinload(TypedColumn(PanchangamRow.sunrise_sunset)),
    selectinload(TypedColumn(PanchangamRow.thithi_transitions)),
    selectinload(TypedColumn(PanchangamRow.nakshatra_transitions)),
)


# ── Repository ────────────────────────────────────────────────────────────────

class PanchangamRepository(PanchangamRepositoryPort):
    """
    Getters and setters for PanchangamData backed by Postgres.

    Caller is responsible for committing the session. ``upsert`` deliberately
    does not commit so that multiple writes can be batched into one
    transaction by the caller. ``upsert_many`` is the exception: it commits
    once at the end for convenience — and, unlike a loop of ``upsert()``
    calls, it writes the whole batch as a handful of set-based bulk
    statements (chunked deletes + multi-row inserts) rather than one round
    trip per day per table, which matters a great deal against a
    network-latency-bound target like Neon.
    """

    def __init__(self, session: Session) -> None:
        self._s = session

    # ── Getters ──────────────────────────────────────────────────────────────

    def get_by_date(
        self, date: datetime.date, location: Location
    ) -> Optional[PanchangamData]:
        """Return PanchangamData for *date* at *location*, or None if not in the DB."""
        stmt = (
            select(PanchangamRow)
            .where(
                PanchangamRow.date == date,
                PanchangamRow.location_id == location.id,
            )
            .options(*_LOAD_OPTIONS)
        )
        row = self._s.exec(stmt).first()
        if row is None:
            return None
        events = self._events_by_dates([date]).get(date, [])
        return _row_to_panchangam_data(row, location, events)

    def get_by_date_range(
        self,
        start: datetime.date,
        end: datetime.date,
        location: Location,
    ) -> Dict[datetime.date, PanchangamData]:
        """Return a date-keyed dict for all dates in [start, end] inclusive at *location*."""
        stmt = (
            select(PanchangamRow)
            .where(
                PanchangamRow.date >= start,
                PanchangamRow.date <= end,
                PanchangamRow.location_id == location.id,
            )
            .order_by(TypedColumn(PanchangamRow.date))
            .options(*_LOAD_OPTIONS)
        )
        rows = self._s.exec(stmt).all()
        # Ashram events are location-independent — fetch once by date and attach
        # the same list to each location's day.
        events_by_date = self._events_by_dates([row.date for row in rows])
        return {
            row.date: _row_to_panchangam_data(
                row, location, events_by_date.get(row.date, [])
            )
            for row in rows
        }

    def get_by_month(
        self, year: int, month: int, location: Location
    ) -> Dict[datetime.date, PanchangamData]:
        """Return a date-keyed dict for every day in the given calendar month at *location*."""
        start = datetime.date(year, month, 1)
        if month == 12:
            end = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
        else:
            end = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
        return self.get_by_date_range(start, end, location)

    def list_event_definitions(self) -> List[SanthigiriEvent]:
        """Return every editable Santhigiri event definition, ordered by sort_order.

        Used by the live-computation fallback to overlay condition-based events
        onto a day the DB does not have a pre-computed occurrence row for.
        """
        rows = self._s.exec(
            select(SanthigiriEventRow).order_by(TypedColumn(SanthigiriEventRow.sort_order))
        ).all()
        return [event_row_to_event(row) for row in rows]

    # ── Setters ──────────────────────────────────────────────────────────────

    def upsert(self, data: PanchangamData, location: Location) -> None:
        """
        Write one PanchangamData for *location* to the DB, replacing any existing
        row for that ``(date, location)``.  Does NOT commit — caller must call
        session.commit().
        """
        self._delete_children(data.date, location)

        self._s.merge(
            PanchangamRow(
                date=data.date,
                location_id=location.id,
                thithi_id=data.thithi.id,
                nakshatra_id=data.nakshatra.id,
                nazhika_from_sunrise=data.nazhika_from_sunrise,
            )
        )
        self._s.flush()

        self._s.add(
            KollavarshamDateRow(
                date=data.date,
                location_id=location.id,
                kv_day=data.kv.kv_day,
                kv_month=data.kv.kv_month,
                kv_year=data.kv.kv_year,
            )
        )
        self._s.add(
            ChandraMasaDateRow(
                date=data.date,
                location_id=location.id,
                masa_id=data.chandra_masa.masa,
                masa_day=data.chandra_masa.masa_day,
                masa_type=data.chandra_masa.masa_type,
            )
        )
        self._s.add(
            SunriseSunsetRow(
                date=data.date,
                location_id=location.id,
                sunrise=data.sunrise,
                sunset=data.sunset,
            )
        )
        for t in data.thithi_transitions:
            self._s.add(
                ThithiTransitionRow(
                    panchangam_date=data.date,
                    location_id=location.id,
                    thithi_id=t.thithi.id,
                    start_time=t.start_time,
                    end_time=t.end_time,
                )
            )
        for n in data.nakshatra_transitions:
            self._s.add(
                NakshatraTransitionRow(
                    panchangam_date=data.date,
                    location_id=location.id,
                    nakshatra_id=n.nakshatra.id,
                    start_time=n.start_time,
                    end_time=n.end_time,
                )
            )
        # Ashram events are location-independent: keyed by date only and shown
        # for every location. Only (re)write them when this record actually
        # carries events, so upserting a *different* location for the same date
        # with an empty list does not wipe the shared events another location
        # (or the ashram record) already established. Events are otherwise
        # cleared via the event-definition CRUD cascade or a full SQL reseed.
        if data.santhigiri_significant_dates:
            self._replace_santhigiri_events(
                data.date, data.santhigiri_significant_dates
            )

    def upsert_many(
        self, data: Iterable[PanchangamData], location: Location, *, commit: bool = True
    ) -> None:
        """
        Bulk-write many PanchangamData objects for *location* in a handful of
        set-based statements.

        Unlike ``upsert`` (used for a single day, e.g. the streaming
        ``/generate`` endpoint's per-day progress), this does not loop
        per-item: it deletes every touched date's ``panchangam`` row in
        chunked ``IN (...)`` batches — cascading (``ON DELETE CASCADE``) to
        all five child tables in the same statement — then bulk-inserts the
        new rows for every table via multi-row ``INSERT`` statements. This
        turns what would be O(days) round trips into a small constant number,
        which is what actually matters against a network-latency-bound
        target like Neon.

        Santhigiri events keep ``upsert``'s semantics: only dates whose
        PanchangamData actually carries a non-empty
        ``santhigiri_significant_dates`` are touched, so bulk-writing one
        location's range never wipes the shared (location-independent) event
        calendar another location's data already established for the same
        dates.

        Commits once at the end by default, same as before — pass
        ``commit=False`` when the caller needs this write to land atomically
        with something else in the same transaction (e.g.
        ``scripts/generate_year_spans.py``, which lets the ETag refresh right
        after do the single commit, exactly as the old per-day ``upsert()``
        loop + ``refresh_etags()`` did).
        """
        # Dedupe by date, keeping the last occurrence — matches the old
        # per-day upsert() loop's "last write wins" behavior for a caller
        # that passes the same date twice, instead of a bulk multi-row
        # INSERT tripping the (date, location_id) unique constraint.
        items = list({item.date: item for item in data}.values())
        if not items:
            return

        dates = [item.date for item in items]
        self._delete_panchangam_rows(dates, location)

        self._s.exec(
            insert(PanchangamRow),
            params=[
                {
                    "date": item.date,
                    "location_id": location.id,
                    "thithi_id": item.thithi.id,
                    "nakshatra_id": item.nakshatra.id,
                    "nazhika_from_sunrise": item.nazhika_from_sunrise,
                }
                for item in items
            ],
        )
        self._s.exec(
            insert(KollavarshamDateRow),
            params=[
                {
                    "date": item.date,
                    "location_id": location.id,
                    "kv_day": item.kv.kv_day,
                    "kv_month": item.kv.kv_month,
                    "kv_year": item.kv.kv_year,
                }
                for item in items
            ],
        )
        self._s.exec(
            insert(ChandraMasaDateRow),
            params=[
                {
                    "date": item.date,
                    "location_id": location.id,
                    "masa_id": item.chandra_masa.masa,
                    "masa_day": item.chandra_masa.masa_day,
                    "masa_type": item.chandra_masa.masa_type,
                }
                for item in items
            ],
        )
        self._s.exec(
            insert(SunriseSunsetRow),
            params=[
                {
                    "date": item.date,
                    "location_id": location.id,
                    "sunrise": item.sunrise,
                    "sunset": item.sunset,
                }
                for item in items
            ],
        )

        thithi_rows = [
            {
                "panchangam_date": item.date,
                "location_id": location.id,
                "thithi_id": t.thithi.id,
                "start_time": t.start_time,
                "end_time": t.end_time,
            }
            for item in items
            for t in item.thithi_transitions
        ]
        if thithi_rows:
            self._s.exec(insert(ThithiTransitionRow), params=thithi_rows)

        nakshatra_rows = [
            {
                "panchangam_date": item.date,
                "location_id": location.id,
                "nakshatra_id": n.nakshatra.id,
                "start_time": n.start_time,
                "end_time": n.end_time,
            }
            for item in items
            for n in item.nakshatra_transitions
        ]
        if nakshatra_rows:
            self._s.exec(insert(NakshatraTransitionRow), params=nakshatra_rows)

        self._bulk_replace_santhigiri_events(items)

        if commit:
            self._s.commit()

    def _delete_panchangam_rows(
        self, dates: Sequence[datetime.date], location: Location
    ) -> None:
        """Delete *location*'s ``panchangam`` rows for *dates* in chunked
        ``IN (...)`` batches. ``ON DELETE CASCADE`` (enforced under both
        Postgres and the SQLite test engine — see ``tests/conftest.py``)
        removes every child row (transitions, kollavarsham, chandra_masa,
        sunrise_sunset) for each deleted row in the same statement, so this
        single delete replaces what ``_delete_children`` does with five."""
        for chunk in _chunked(dates, _DELETE_CHUNK_SIZE):
            self._s.exec(
                delete(PanchangamRow).where(
                    col(PanchangamRow.date).in_(chunk),
                    col(PanchangamRow.location_id) == location.id,
                )
            )

    def _bulk_replace_santhigiri_events(
        self, items: Sequence[PanchangamData]
    ) -> None:
        """Batched equivalent of ``_replace_santhigiri_events`` for every
        item in *items* that actually carries events — dates with an empty
        list are left untouched, same as ``upsert``."""
        dated_events = [
            (item.date, item.santhigiri_significant_dates)
            for item in items
            if item.santhigiri_significant_dates
        ]
        if not dated_events:
            return

        event_dates = [d for d, _ in dated_events]
        for chunk in _chunked(event_dates, _DELETE_CHUNK_SIZE):
            self._s.exec(
                delete(SanthigiriEventDateRow).where(
                    col(SanthigiriEventDateRow.panchangam_date).in_(chunk)
                )
            )

        self._s.exec(
            insert(SanthigiriEventDateRow),
            params=[
                {"panchangam_date": d, "event_id": event.id}
                for d, events in dated_events
                for event in events
            ],
        )

    def set_event_occurrences_for_year(
        self, event_id: str, year: int, dates: Iterable[datetime.date]
    ) -> None:
        """Replace *event_id*'s occurrences within *year* with *dates*.

        Unlike :meth:`_replace_santhigiri_events` (which replaces every
        event's occurrences for one date), this replaces one event's
        occurrences across an entire year — the shape needed to regenerate a
        single event's dates without disturbing any other event's dates that
        happen to fall on the same days. Does NOT commit.
        """
        start = datetime.date(year, 1, 1)
        end = datetime.date(year, 12, 31)
        self._s.exec(
            delete(SanthigiriEventDateRow).where(
                col(SanthigiriEventDateRow.event_id) == event_id,
                col(SanthigiriEventDateRow.panchangam_date) >= start,
                col(SanthigiriEventDateRow.panchangam_date) <= end,
            )
        )
        for d in dates:
            self._s.add(SanthigiriEventDateRow(panchangam_date=d, event_id=event_id))

    # ── Private helpers ───────────────────────────────────────────────────────

    def _events_by_dates(
        self, dates: Sequence[datetime.date]
    ) -> Dict[datetime.date, List[SanthigiriEvent]]:
        """Return location-independent ashram events grouped by date.

        Events live in ``santhigiri_event_dates`` (keyed by date alone) and are
        shown identically for every location, so getters fetch them once and
        attach the same list to each location's day.
        """
        if not dates:
            return {}
        rows = self._s.exec(
            select(SanthigiriEventDateRow)
            .where(col(SanthigiriEventDateRow.panchangam_date).in_(set(dates)))
            .options(selectinload(TypedColumn(SanthigiriEventDateRow.event)))
        ).all()
        grouped: Dict[datetime.date, List[SanthigiriEvent]] = {}
        for row in rows:
            grouped.setdefault(row.panchangam_date, []).append(
                _ssd_row_to_event(row)
            )
        return grouped

    def _replace_santhigiri_events(
        self, date: datetime.date, events: Iterable[SanthigiriEvent]
    ) -> None:
        """Replace the location-independent ashram events for *date*."""
        self._s.exec(
            delete(SanthigiriEventDateRow).where(
                col(SanthigiriEventDateRow.panchangam_date) == date
            )
        )
        for event in events:
            self._s.add(
                SanthigiriEventDateRow(
                    panchangam_date=date,
                    event_id=event.id,
                )
            )

    def _delete_children(self, date: datetime.date, location: Location) -> None:
        """Delete the *location*'s child rows for *date* so upsert can re-insert cleanly.

        Santhigiri events are location-independent and handled separately by
        :meth:`_replace_santhigiri_events`.
        """
        self._s.exec(
            delete(ThithiTransitionRow).where(
                col(ThithiTransitionRow.panchangam_date) == date,
                col(ThithiTransitionRow.location_id) == location.id,
            )
        )
        self._s.exec(
            delete(NakshatraTransitionRow).where(
                col(NakshatraTransitionRow.panchangam_date) == date,
                col(NakshatraTransitionRow.location_id) == location.id,
            )
        )
        self._s.exec(
            delete(KollavarshamDateRow).where(
                col(KollavarshamDateRow.date) == date,
                col(KollavarshamDateRow.location_id) == location.id,
            )
        )
        self._s.exec(
            delete(ChandraMasaDateRow).where(
                col(ChandraMasaDateRow.date) == date,
                col(ChandraMasaDateRow.location_id) == location.id,
            )
        )
        self._s.exec(
            delete(SunriseSunsetRow).where(
                col(SunriseSunsetRow.date) == date,
                col(SunriseSunsetRow.location_id) == location.id,
            )
        )
