from datetime import date

from pydantic import BaseModel, Field, model_validator


# The largest span the range endpoint will serve in one request. Kept in line
# with the yearly endpoint's response size so a single call can't return an
# unbounded number of days (and, on a DB miss, trigger an unbounded number of
# live computations).
MAX_RANGE_DAYS = 366


class GetRangePanchangamParams(BaseModel):
    start: date = Field(description="First day of the range (inclusive), YYYY-MM-DD")
    end: date = Field(description="Last day of the range (inclusive), YYYY-MM-DD")

    @model_validator(mode="after")
    def _validate_range(self) -> "GetRangePanchangamParams":
        if self.end < self.start:
            raise ValueError("end must be on or after start")
        span = (self.end - self.start).days + 1
        if span > MAX_RANGE_DAYS:
            raise ValueError(
                f"range spans {span} days; the maximum is {MAX_RANGE_DAYS}"
            )
        return self
