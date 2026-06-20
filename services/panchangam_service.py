import calendar
import datetime
from typing import Dict, Optional

from core.calendar.panchangam import get_panchangam_data
from db.repository import PanchangamRepository
from schemas.panchangam_data import PanchangamData

_cal = calendar.Calendar(firstweekday=6)


class PanchangamService:
    """
    Business logic layer between the HTTP routes and the SQLite repository.

    For dates present in the database the repository is the source of truth.
    For dates absent from the database the service falls back to live
    astronomical computation via get_panchangam_data().
    """

    def __init__(self, repo: PanchangamRepository) -> None:
        self._repo = repo

    def get_by_date(self, date: datetime.date) -> PanchangamData:
        data = self._repo.get_by_date(date)
        if data is None:
            data = get_panchangam_data(date)
        return data

    def get_by_month(
        self,
        year: int,
        month: int,
    ) -> Dict[datetime.date, PanchangamData]:
        """
        Return PanchangamData for every date in the calendar grid of the given
        month (including leading/trailing days from adjacent months, matching
        the original weekly-grid behaviour).  DB rows are preferred; missing
        dates fall back to live computation.
        """
        dates = list(_cal.itermonthdates(year, month))
        start, end = dates[0], dates[-1]
        db_data = self._repo.get_by_date_range(start, end)

        result: Dict[datetime.date, PanchangamData] = {}
        for day in dates:
            result[day] = db_data.get(day) or get_panchangam_data(day)
        return result
