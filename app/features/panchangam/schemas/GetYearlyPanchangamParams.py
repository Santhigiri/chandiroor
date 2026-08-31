from pydantic import Field, BaseModel

# A defensive sanity ceiling only — not the real business rule. The actual
# accepted range is the admin-configured `seed_year_range` setting, enforced
# by PanchangamService (see shared/services/settings_service.py).
class GetYearlyPanchangamParams(BaseModel):
    year: int = Field(ge=1, le=9999)
