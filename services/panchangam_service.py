"""
PanchangamService — serves PanchangamData for the API routes.

Reads through PanchangamRepository (Postgres). A date missing from the DB falls
back to live astronomical computation so the API never 404s on an
un-migrated date; the DB is expected to already cover the seeded range.
"""
import calendar
from datetime import date, timedelta
from typing import Dict, List, Optional

from db.repository import PanchangamRepository
from schemas.panchangam_data import PanchangamData
from utils.location import DEFAULT_LOCATION, Location
from utils.santhigiri_events import SanthigiriEvent

_cal = calendar.Calendar(firstweekday=6)


class PanchangamService:
    def __init__(self, repository: PanchangamRepository) -> None:
        self._repo = repository
        # Cache the editable event definitions for the life of this (request-scoped)
        # service so the month/year loops don't issue one query per day.
        self._event_defs_cache: Optional[List[SanthigiriEvent]] = None

    def _event_defs(self) -> List[SanthigiriEvent]:
        if self._event_defs_cache is None:
            self._event_defs_cache = self._repo.list_event_definitions()
        return self._event_defs_cache

    def _compute(self, day: date, location: Location) -> PanchangamData:
        """Live-computation fallback using the location's coordinates/timezone.

        The astronomy stack (Skyfield + ephemeris) is imported lazily here so that
        DB-served requests never pay its import cost — only a DB miss triggers it.
        Santhigiri events are overlaid from the editable DB definitions so a
        live-computed day still carries its condition-based events.
        """
        from core.calendar.panchangam import get_panchangam_data
        from core.calendar.santhigiri_significant_dates import (
            match_condition_based_events,
        )

        data = get_panchangam_data(
            day, location.latitude, location.longitude, location.timezone
        )
        data.santhigiri_significant_dates = match_condition_based_events(
            data, self._event_defs(), location.timezone
        )
        return data

    def get_by_date(
        self, day: date, location: Location = DEFAULT_LOCATION
    ) -> PanchangamData:
        return self._repo.get_by_date(day, location) or self._compute(day, location)

    def get_by_month(
        self, year: int, month: int, location: Location = DEFAULT_LOCATION
    ) -> Dict[date, PanchangamData]:
        days = list(_cal.itermonthdates(year, month))
        found = self._repo.get_by_date_range(days[0], days[-1], location)
        return {day: found.get(day) or self._compute(day, location) for day in days}

    def get_by_year(
        self, year: int, location: Location = DEFAULT_LOCATION
    ) -> Dict[date, PanchangamData]:
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        days = [start + timedelta(days=offset) for offset in range((end - start).days + 1)]
        found = self._repo.get_by_date_range(start, end, location)
        return {day: found.get(day) or self._compute(day, location) for day in days}
