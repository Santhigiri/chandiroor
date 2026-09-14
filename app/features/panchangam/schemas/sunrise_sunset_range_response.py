from datetime import date, datetime
from typing import Dict

from pydantic import BaseModel


class SunriseSunsetDay(BaseModel):
    """One day's sunrise/sunset, in UTC."""

    sunrise: datetime
    sunset: datetime


class SunriseSunsetRangeResponse(BaseModel):
    """Sunrise/sunset for an arbitrary coordinate over an inclusive date range,
    in UTC. ``results`` is keyed by date so the frontend can look up a single
    day's value without a linear scan, mirroring the ``/month`` endpoint's
    ``Dict[date, CompactPanchangamData]`` shape."""

    latitude: float
    longitude: float
    start_date: date
    end_date: date
    results: Dict[date, SunriseSunsetDay]
