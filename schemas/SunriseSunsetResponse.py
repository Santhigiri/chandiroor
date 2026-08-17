from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel


class SunriseSunsetResponse(BaseModel):
    """Sunrise/sunset for an arbitrary coordinate, in UTC.

    sunrise/sunset are null when status is not "normal": at high latitudes
    the sun can stay continuously up ("polar_day") or down ("polar_night")
    for the whole day, so there is no rising/setting event to report.
    """

    latitude: float
    longitude: float
    day: date
    sunrise: Optional[datetime] = None
    sunset: Optional[datetime] = None
    status: Literal["normal", "polar_day", "polar_night"] = "normal"
