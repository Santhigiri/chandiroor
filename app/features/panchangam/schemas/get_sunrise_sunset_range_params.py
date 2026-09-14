from datetime import date

from pydantic import BaseModel, Field, model_validator

# A defensive sanity ceiling only, not the real business rule -- this endpoint
# is public and always live-computed (no DB row limits it), so an unbounded
# range is still an easy way for an anonymous caller to burn CPU even though
# get_sunrise_sunset_for_range's chunked find_discrete pass makes a large
# range cheap per-day. Mirrors _HARD_SPAN_CEILING_DAYS in
# schemas/panchangam_generation.py.
MAX_SUNRISE_SUNSET_RANGE_DAYS = 366


class GetSunriseSunsetRangeParams(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _check_range(self) -> "GetSunriseSunsetRangeParams":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        span = (self.end_date - self.start_date).days + 1
        if span > MAX_SUNRISE_SUNSET_RANGE_DAYS:
            raise ValueError(
                f"date range too large: {span} days (max {MAX_SUNRISE_SUNSET_RANGE_DAYS})"
            )
        return self
