from datetime import date, time

from pydantic import BaseModel, Field


class GetInstantPanchangamParams(BaseModel):
    day: date
    time: time
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str
