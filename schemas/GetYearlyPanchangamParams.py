from pydantic import Field, BaseModel
from core.constants import Coordinates, DEFAULT_TIMEZONE


class GetYearlyPanchangamParams(BaseModel):
    year: int = Field(ge=1900, le=2100)
    latitude: float = Coordinates.SG_LATITUDE
    longitude: float = Coordinates.SG_LONGITUDE
    timezone: str = DEFAULT_TIMEZONE
