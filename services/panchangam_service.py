"""
PanchangamService — serves PanchangamData for the API routes.

Reads through PanchangamRepository (Postgres). A date missing from the DB falls
back to live astronomical computation so the API never 404s on an
un-migrated date; the DB is expected to already cover the seeded range.
"""
import calendar
from datetime import date, timedelta
from typing import Dict

from core.calendar.panchangam import get_panchangam_data
from db.repository import PanchangamRepository
from schemas.panchangam_data import PanchangamData
from utils.location import DEFAULT_LOCATION, Location

_cal = calendar.Calendar(firstweekday=6)


class PanchangamService:
    def __init__(self, repository: PanchangamRepository) -> None:
        self._repo = repository

    def _compute(self, day: date, location: Location) -> PanchangamData:
        """Live-computation fallback using the location's coordinates/timezone."""
        return get_panchangam_data(
            day, location.latitude, location.longitude, location.timezone
        )

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
