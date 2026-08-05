"""
PanchangamService — serves PanchangamData for the API routes.

Reads through PanchangamRepository (Postgres). A date missing from the DB falls
back to live astronomical computation so the API never 404s on an
un-migrated date; the DB is expected to already cover the seeded range.
"""
import calendar
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from core.astronomy.tuning import AstronomyTuning
from db.repository import PanchangamRepository
from schemas.panchangam_data import PanchangamData
from services.settings_service import SettingsService
from utils.location import DEFAULT_LOCATION, Location
from utils.santhigiri_events import SanthigiriEvent

_cal = calendar.Calendar(firstweekday=6)

# Grid size (decimal degrees) that arbitrary sunrise/sunset coordinates are
# snapped to before hitting get_sunrise_sunset()'s @lru_cache. This is a
# caching knob, not an accuracy one: at ~11 km per 0.1 degree, the resulting
# sunrise/sunset shift is at most ~14s even at the solstices, but it lets
# calls from many nearby callers on the same day collapse onto one cache
# entry. Must be applied here, before the cached call, not inside it.
SUNRISE_SUNSET_CACHE_GRID_DEGREES = 1


class YearOutOfRange(Exception):
    """Raised when a requested year falls outside the admin-configured
    ``seed_year_range`` setting (see ``services.settings_service``)."""

    def __init__(self, year: int, start_year: int, end_year: int) -> None:
        self.year = year
        self.start_year = start_year
        self.end_year = end_year
        super().__init__(
            f"year {year} is outside the configured range [{start_year}, {end_year}]"
        )


class PanchangamService:
    def __init__(
        self,
        repository: PanchangamRepository,
        settings: Optional[SettingsService] = None,
    ) -> None:
        self._repo = repository
        self._settings = settings
        # Cache the editable event definitions for the life of this (request-scoped)
        # service so the month/year loops don't issue one query per day.
        self._event_defs_cache: Optional[List[SanthigiriEvent]] = None

    def _event_defs(self) -> List[SanthigiriEvent]:
        if self._event_defs_cache is None:
            self._event_defs_cache = self._repo.list_event_definitions()
        return self._event_defs_cache

    def _tuning_for_year(self, year: int) -> AstronomyTuning:
        if self._settings is None:
            return AstronomyTuning()
        return self._settings.get_astronomy_tuning(year)

    def _check_year_in_range(self, year: int) -> None:
        """Enforce the admin-configured ``seed_year_range`` setting, if a
        ``SettingsService`` is available. No-op otherwise (e.g. internal
        callers like ``services.etag_service`` that build a
        ``PanchangamService`` from a repository alone)."""
        if self._settings is None:
            return
        start_year, end_year = self._settings.get_seed_year_range()
        if year < start_year or year > end_year:
            raise YearOutOfRange(year, start_year, end_year)

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
            day,
            location.latitude,
            location.longitude,
            location.timezone,
            self._tuning_for_year(day.year),
        )
        data.santhigiri_significant_dates = match_condition_based_events(
            data, self._event_defs(), location.timezone
        )
        return data

    def compute_at_instant(
        self, day: date, time_of_day: time, latitude: float, longitude: float, timezone: str
    ) -> PanchangamData:
        """Live-compute Panchangam anchored at an exact date+time+coordinate.

        Always live-computed — arbitrary coordinates are never in the seeded
        (Location-keyed) database, so this never reads through the repository.
        No santhigiri_significant_dates overlay: those are Ashram/Kerala-specific
        matches against DB event definitions and don't apply to an arbitrary
        global coordinate (PanchangamData defaults that list to empty).
        """
        from core.calendar.panchangam import get_panchangam_data_at_instant

        instant = datetime.combine(day, time_of_day, tzinfo=ZoneInfo(timezone))
        return get_panchangam_data_at_instant(
            instant, latitude, longitude, timezone, self._tuning_for_year(day.year)
        )

    def get_sunrise_sunset(
        self, day: date, latitude: float, longitude: float
    ) -> Tuple[datetime, datetime]:
        """Sunrise/sunset for an arbitrary coordinate, in UTC.

        The coordinate is snapped to a SUNRISE_SUNSET_CACHE_GRID_DEGREES grid
        before computation so that nearby callers share cache entries; this
        trades a negligible (sub-15s) accuracy cost for a much higher hit
        rate on get_sunrise_sunset()'s @lru_cache.

        Live computation only (no DB-backed table for this); raises ValueError
        if no rising/setting is found for the given date/coordinate (e.g. polar
        day/night).
        """
        from core.astronomy.sunrise_sunset import get_sunrise_sunset

        latitude = round(latitude, SUNRISE_SUNSET_CACHE_GRID_DEGREES)
        longitude = round(longitude, SUNRISE_SUNSET_CACHE_GRID_DEGREES)
        return get_sunrise_sunset(day, latitude, longitude, timezone="UTC")

    def get_by_date(
        self, day: date, location: Location = DEFAULT_LOCATION
    ) -> PanchangamData:
        return self._repo.get_by_date(day, location) or self._compute(day, location)

    def get_by_month(
        self, year: int, month: int, location: Location = DEFAULT_LOCATION
    ) -> Dict[date, PanchangamData]:
        self._check_year_in_range(year)
        days = list(_cal.itermonthdates(year, month))
        found = self._repo.get_by_date_range(days[0], days[-1], location)
        return {day: found.get(day) or self._compute(day, location) for day in days}

    def get_by_year(
        self, year: int, location: Location = DEFAULT_LOCATION
    ) -> Dict[date, PanchangamData]:
        self._check_year_in_range(year)
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        days = [start + timedelta(days=offset) for offset in range((end - start).days + 1)]
        found = self._repo.get_by_date_range(start, end, location)
        return {day: found.get(day) or self._compute(day, location) for day in days}
