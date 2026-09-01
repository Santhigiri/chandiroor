from pydantic import Field, BaseModel
from panchangam_astronomy.constants import Coordinates, DEFAULT_TIMEZONE

# A defensive sanity ceiling only — not the real business rule. The actual
# accepted range is the admin-configured `seed_year_range` setting, enforced
# by PanchangamService (see services/settings_service.py).
class GetMonthlyPanchangamParams(BaseModel):
    year: int = Field(ge=1, le=9999)
    month: int =  Field(ge=1,le=12)
