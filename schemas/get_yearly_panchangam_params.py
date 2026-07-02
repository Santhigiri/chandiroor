from pydantic import Field, BaseModel
from core.constants import Coordinates, DEFAULT_TIMEZONE


class GetYearlyPanchangamParams(BaseModel):
    year: int = Field(ge=2021, le=2030)
