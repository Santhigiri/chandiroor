from datetime import date, datetime

from pydantic import BaseModel


class SunriseSunsetResponse(BaseModel):
    """Sunrise/sunset for an arbitrary coordinate, in UTC."""

    latitude: float
    longitude: float
    day: date
    sunrise: datetime
    sunset: datetime
