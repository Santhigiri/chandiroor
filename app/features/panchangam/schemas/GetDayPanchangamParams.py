from pydantic import BaseModel
from datetime import date, datetime
from core.constants import Coordinates, DEFAULT_TIMEZONE

class GetPanchangamParams(BaseModel):
    date_str: date = datetime.now().date()
    time_str: str = "00:00:00"
    latitude: float = Coordinates.SG_LATITUDE
    longitude: float = Coordinates.SG_LONGITUDE
    timezone: str = DEFAULT_TIMEZONE
