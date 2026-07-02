from pydantic import Field, BaseModel
from core.constants import Coordinates, DEFAULT_TIMEZONE


class GetMonthlyPanchangamParams(BaseModel):
    year: int = Field(ge=2021, le=2030)
    month: int =  Field(ge=1,le=12)
