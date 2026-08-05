from datetime import date, time

from pydantic import BaseModel, Field

from core.constants import DEFAULT_TIMEZONE


class GetPanchangamAtInstantParams(BaseModel):
    day: date = Field(default_factory=date.today)
    time_of_day: time = Field(alias="time")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str = DEFAULT_TIMEZONE

    model_config = {"populate_by_name": True}
