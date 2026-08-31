"""Response schema describing which location a panchangam payload was computed for."""
from __future__ import annotations

from pydantic import BaseModel

from app.utils.location import Location


class LocationInfo(BaseModel):
    """Self-describing location descriptor attached to panchangam responses."""

    code: str
    label: str
    latitude: float
    longitude: float
    timezone: str

    @classmethod
    def from_location(cls, loc: Location) -> "LocationInfo":
        return cls(
            code=loc.code,
            label=loc.label,
            latitude=loc.latitude,
            longitude=loc.longitude,
            timezone=loc.timezone,
        )
